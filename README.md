# codebase-rag

RAG over a git repository: clone it, index it, then ask questions with cited
source snippets.

## Run it

No Docker needed. From the project root:

```bash
./scripts/dev.sh start    # postgres + backend + frontend
./scripts/dev.sh status
./scripts/dev.sh stop
```

Then open <http://localhost:5173>.

`dev.sh` creates the venv, starts PostgreSQL 15 on port 5434 (with the
`vector` extension), applies Alembic migrations, and launches Uvicorn on 8001
and Vite on 5173. Configure it through `.env`; see `.env.example`.

```bash
cp .env.example .env
```

## Ingesting

The two API calls do different things, which is easy to misread:

| Endpoint | What it actually does |
| --- | --- |
| `GET /repositories/{id}/ingest` | Clones the repo. Leaves status `processing`. |
| `GET /repositories/{id}/files` | The expensive step: parses, chunks, embeds. |

A `GET` that does the indexing is not RESTful, and it will bite you if a client
or a crawler ever hits it. Changing the verbs means changing the frontend and
the API together; it is not done yet.

## Retrieval design

Two things dominate answer quality, and both were wrong in the first version.

**Generated files were being indexed.** A 26,000-line `package-lock.json`
produced roughly 850 of a 915-chunk index, so most "sources" the model saw were
lockfile noise. `code_parser.is_ignored` now skips lockfiles, generated
manifests, minified output, source maps, and bundles. The same repository went
from 915 chunks to 62.

**Hybrid search was not hybrid.** `hybrid_search` ran the vector search, appended
the keyword results, and truncated to `top_k` — so the keyword half was dead
code that only ever appeared if the vector search returned fewer than `top_k`
rows. It also had two bugs underneath: `repository_id == None` compiles to
`IS NULL` and matched no repository, and an unescaped `%` in a query acted as a
SQL wildcard.

Both halves now feed a Reciprocal Rank Fusion over over-fetched candidate pools,
so a chunk ranked well by either signal can surface.

Keyword results are ranked in Python, not SQL. "Position of substring" has no
portable spelling: PostgreSQL has `strpos`, SQLite has `instr`, and PostgreSQL
has no `instr`. Ranking in SQL meant a function that broke whichever database
the other tests ran on.

**Embeddings carry path and symbol context.** `embeddable_text` prefixes the
repository-relative path and any definition names found by
`symbols.extract_symbols` ahead of the code, while the chunk text stored and
cited stays byte-for-byte what the user will read. Asking "where is the puter
provider defined?" now ranks `backend/app/providers/puter.py` first, which the
code text alone did not convey.

`extract_symbols` matches on definition keywords behind a modifier prefix, so
`export class Widget` and `public void main` are both caught. An earlier
keyword pre-filter was removed: it silently skipped every arrow function, since
`const x = () => {}` contains none of the definition keywords. Ten cheap regexes
per line is a fine price for not dropping real symbols.

## Idle expiry

A repository occupies space in two places: a git clone under
`data/repositories/{id}/`, and one `code_chunks` row per chunk, of which the
`Vector(384)` embedding is the largest part (74% of a chunk row in practice).
A background sweep deletes both once a repository goes unused.

Expiry is keyed on `last_accessed_at`, not `created_at`. A hard age limit would
delete a repository you are actively working in, so "used" means indexed,
previewed, searched, or created.

One deliberate exception: **`GET /repositories/` does not count as use.** The
frontend loads that history list on every page render, so treating it as use
would refresh every repository forever and nothing would ever be reclaimed.

Tuned in `.env`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `REPO_IDLE_TTL_HOURS` | 12 | Idle time before a repository is dropped |
| `REPO_CLEANUP_INTERVAL_MINUTES` | 15 | How often the sweeper runs |
| `REPO_CLEANUP_ENABLED` | true | Set false to disable entirely |

The sweep runs once at startup, to catch repositories that expired while the
process was down, and then on an interval. It is serialized with a Postgres
advisory lock, so running several uvicorn workers cannot have them race over the
same rows.

Three details that are load-bearing:

- **`code_chunks.repository_id` has an `ON DELETE CASCADE` foreign key.** It had
  no constraint at all, so deleting a repository orphaned its chunks
  permanently — unreachable, never reclaimed. The migration purges existing
  orphans before adding the constraint.
- **The clone is deleted before the database rows.** If `rmtree` fails the rows
  survive and the next sweep retries; the reverse order would strand data that
  nothing points at.
- **Repositories with status `processing` are never swept.** A live index has
  open handles into its own clone and an open transaction against its own rows.

`DELETE` frees space for Postgres to reuse, not for the OS. Reclaiming actual
free space needs `VACUUM`, which takes an exclusive lock, so it belongs in a
manual maintenance step rather than the background sweep.

## Tests

```bash
./venv/bin/python -m pytest tests/ -q
```

73 tests. `tests/test_retrieval_quality.py` covers the escaping, unfiltered
search, RRF, and symbol cases above; `tests/test_cleanup.py` covers expiry
selection, the `processing` guard, directory-before-rows ordering, retry after a
failed removal, and the fact that reading the history list does not keep a
repository alive.

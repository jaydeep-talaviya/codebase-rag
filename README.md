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

## Tests

```bash
./venv/bin/python -m pytest tests/ -q
```

61 tests. The retrieval regressions live in `tests/test_retrieval_quality.py`
and cover the escaping, unfiltered-search, RRF, and symbol cases above, so the
specific failures described here cannot come back quietly.

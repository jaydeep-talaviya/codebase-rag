# codebase-rag

Ask questions about a git repository and get answers cited back to the exact
file and line range that supports them.

Point it at a public GitHub URL. It clones the repo, drops lockfiles and other
generated noise, chunks the real source, embeds each chunk with its path and
symbol context, stores the vectors in Postgres/pgvector, then answers questions
by retrieving chunks, reranking them, and asking an LLM to answer using only
what it was given.

FastAPI + SQLModel + pgvector + Alembic, with a React/TypeScript frontend.
Two local models — `all-MiniLM-L6-v2` for embeddings and
`cross-encoder/ms-marco-MiniLM-L-6-v2` for reranking. Only the final answer
leaves the machine, via OpenRouter.

---

## Quickstart

Needs Python 3.14, Node 20+, PostgreSQL 15 (Homebrew), and an OpenRouter key.

```bash
cp .env.example .env      # then set OPENROUTER_API_KEY and LLM_MODEL
./scripts/dev.sh start    # postgres + migrations + backend + frontend
```

Open <http://localhost:5173>. `dev.sh` also takes `status` and `stop`.

It provisions the venv, starts `postgresql@15` on **5434** with the `vector`
extension, runs migrations, then serves Uvicorn on **8001** and Vite on
**5173**. Port 5434 is because that is the brew formula shipping pgvector,
leaving 5432 to any other Postgres on the machine. The first request is slow
while both models download (~90 MB each) into `~/.cache/huggingface`.

Both `OPENROUTER_API_KEY` and `LLM_MODEL` are required and have no defaults —
a silent default would send your questions to a model you did not choose.

---

## How it works

### Asking a question

`rag_service.ask_repository` is the whole pipeline, and it is worth reading
top to bottom:

| Stage | File | What happens |
| --- | --- | --- |
| Embed the query | `embedding_service.py` | One 384-dim vector. The bare question — no decoration, that only chunks get. |
| Two searches | `vector_search.py` | `search_code` orders by `cosine_distance`; `keyword_search` does a bounded `ILIKE`, ranked in Python. |
| Fuse | `vector_search.py` | Both over-fetched lists merged by Reciprocal Rank Fusion. |
| Rerank | `reranker.py` | A CrossEncoder scores each of 20 candidates against the query, keeping 5. |
| Answer | `context_service.py` → `llm_service.py` → `citation_service.py` | 5 chunks become one prompt, sent to OpenRouter; the same 5 become the citations. |

Two invariants:

- **Citations come from the post-rerank list**, never the retrieval pool.
  Citing a chunk the model never saw makes the citation a lie.
- **The LLM is told to refuse.** "Answer using only the provided context; if
  the answer is not present, say you don't know." There is no fallback, so bad
  retrieval shows up as a visibly wrong answer rather than a confident invention.

The reranker is where most of the precision comes from: cosine similarity finds
chunks that are *near* the question, while the CrossEncoder scores the
question-chunk *pair*. Cutting 20 to 5 is what removes topically-similar-but-wrong
chunks.

### Indexing a repository

Ingestion is split into a cheap half and an expensive half, called in order:

| Step | Call | Cost | Result |
| --- | --- | --- | --- |
| Register | `POST /repositories/?url=` | instant | Row created, `pending`. Idempotent per URL. |
| Clone | `POST /repositories/{id}/ingest` | seconds | `git clone` to `data/repositories/{id}/`. |
| Index | `POST /repositories/{id}/index` | slow | Filter → chunk → embed → store. Status `completed`. |

Indexing: `code_parser` drops lockfiles, generated manifests, minified output,
source maps, bundles, binaries, and oversized files; `code_chunker` splits on
line boundaries keeping `start_line`/`end_line`; `embeddable_text` prefixes the
path and the symbols the chunk *defines*; `symbols.extract_symbols` finds those
names; `store_chunks` deletes existing rows first so re-indexing replaces
rather than appends.

### Status is only set honestly

```
pending ──ingest──> processing ──index ok──> completed
                        │
                        └──any exception──> failed
```

`processing` is never reported as `completed` — claiming success at clone time
is what made a failed index look like a successful one. A run that dies
mid-index leaves `processing` behind, so `updated_at` older than 30 minutes
counts as abandoned and indexing can resume. Indexing zero files is an error,
not a success, and calling `index` before `ingest` returns `409` rather than
quietly producing an empty index.

---

## API

Everything is in `app/api/repository_api.py`. Every route that changes state is
a `POST`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness. |
| `POST` | `/repositories/?url=` | Register. 400 on a non-GitHub URL. |
| `GET` | `/repositories/` | History list, newest first, with chunk counts. |
| `GET` | `/repositories/{id}` | One repository. |
| `POST` | `/repositories/{id}/ingest` | Clone. 400 if already processing, 404 unknown. |
| `POST` | `/repositories/{id}/index` | Parse, chunk, embed, store. 409 if not cloned. |
| `POST` | `/repositories/{id}/ask` | Ask. Body `{question}`. |
| `POST` | `/repositories/search` | Ask across all repos. Body `{question, repository_id?}`. |
| `GET` | `/repositories/{id}/files/{path}` | File preview for a citation. |

Ingestion and asking were `GET` until recently, which was wrong three ways: a
`GET` that writes 300 rows is unsafe to prefetch, cache, or retry; `/search`
called a paid LLM, so a bookmark or restored tab cost real money; and it
refreshed the idle timer, so a link followed once silently kept a repository
alive. `tests/test_api_routes.py` guards against that regressing.

`{path}` is path-constrained, not just quoted —
`resolve_repository_file` rejects anything outside the repository root, so
`/etc/passwd` and `../../.env` are unreachable.

## Data model

**`repositories`** — `id`, `name`, `url`, `status`, `created_at`,
`updated_at`, and `last_accessed_at` (indexed, drives expiry). The last is
deliberately separate from `updated_at`, which tracks indexing state and would
otherwise make a half-finished index look recently used.

**`code_chunks`** — `repository_id` (FK, `ON DELETE CASCADE`, indexed),
`file_path`, `file_name`, `language`, `chunk_index`, `content`,
`start_line`, `end_line`, and `embedding vector(384)`.

`content` is verbatim source, which is what a citation shows. There is no
stored `embeddable_text` column — the path/symbol header is built at index time
and discarded after embedding. The `CASCADE` matters: the column had no
constraint at all, so deleting a repository orphaned every chunk permanently.

## Layout

```
app/
  main.py                  app, CORS, lifespan + cleanup loop, /health
  config.py                settings from .env
  api/repository_api.py    every route
  models/                  Repository, CodeChunk
  services/                the pipeline, one concern per file:
                           repository  ingestion lifecycle, file preview
                           cleanup     expiry selection + deletion
                           code_parser / code_chunker / symbols
                           embedding_service / vector_storage / vector_search
                           retrieval_service / reranker
                           context_service / llm_service / citation_service
                           paths        the one place that knows the layout
alembic/versions/          3 migrations
scripts/dev.sh             postgres + backend + frontend
tests/                     88 tests, 12 files
frontend/src/
  hooks/                   useRepository, useChat, useTheme
  lib/                     api.ts, http.ts, env.ts
  components/              19 components
```

---

## Design notes

### Retrieval

Two things dominated answer quality, and both were wrong at first.

**Generated files were being indexed.** A 26,000-line `package-lock.json`
produced ~850 of a 915-chunk index, so most "sources" the model saw were
lockfile noise. `code_parser.is_ignored` now skips them; that repository went
915 chunks → 62.

**Hybrid search was not hybrid.** It ran the vector search, appended keyword
results, and truncated to `top_k`, so the keyword half was dead code. Two bugs
sat underneath: `repository_id == None` compiles to `IS NULL` and matched no
repository, and an unescaped `%` acted as a SQL wildcard.

Both halves now feed RRF over over-fetched pools, so a chunk found by either
signal can win, and one found by both is promoted. RRF is rank-based, so it
does not need a cosine distance and a keyword hit on the same scale.

Keyword results are ranked in Python because "position of substring" has no
portable spelling: Postgres has `strpos`, SQLite has `instr`, and Postgres has
no `instr`. Ranking in SQL meant a function that broke whichever database the
other tests ran on. The fetch is bounded to 200 rows so it cannot become a
table scan.

**Embeddings carry path and symbol context.** `embeddable_text` prefixes the
repo-relative path and any names the chunk defines, so "where is the puter
provider defined?" ranks `backend/app/providers/puter.py` first — which the
code text alone did not convey. `extract_symbols` matches definition keywords
behind a modifier prefix, so `export class Widget` and `public void main` both
work; an earlier pre-filter was removed because it silently skipped every arrow
function.

### Idle expiry

A repository occupies a git clone plus one row per chunk, of which the
`Vector(384)` is ~74%. A background sweep deletes both once a repository goes
unused, keyed on `last_accessed_at` rather than `created_at` so an actively
worked-in repository is never swept.

`GET /repositories/` deliberately does **not** count as use — the frontend
loads that list on every render, so counting it would keep everything alive
forever. A cross-repository search likewise touches nothing, or every keystroke
would wake every repository.

The sweep runs at startup and on an interval, serialized by a Postgres advisory
lock so several uvicorn workers cannot race. Three details are load-bearing:

- `code_chunks.repository_id` is `ON DELETE CASCADE` (see above).
- **The clone is deleted before the rows.** If `rmtree` fails the rows survive
  and the next sweep retries; the reverse would strand data nothing points at.
- Status `processing` is never swept — a live index has open handles into its
  own clone and its own transaction.

The history card shows `expires in 10h`, computed server-side as
`last_accessed_at + TTL` so the UI never hardcodes a window, and reads
`expiring soon` once the deadline passes (real state, not cosmetic: the sweeper
is on an interval). With `REPO_CLEANUP_ENABLED=false` no deadline is sent at
all, rather than promising one nothing will act on.

`DELETE` returns space to Postgres, not the OS — reclaiming it needs `VACUUM`,
which is manual.

---

## Configuration

Backend, via `pydantic-settings` in `app/config.py`:

| Variable | Req | Default | Meaning |
| --- | --- | --- | --- |
| `DATABASE_URL` | yes | — | Postgres with the `vector` extension. |
| `OPENROUTER_API_KEY` | yes | — | Answers only; indexing and search work without it. |
| `LLM_MODEL` | yes | — | Any OpenRouter model id. |
| `MAX_FILE_SIZE_MB` | no | `1` | Larger files skipped when indexing. |
| `CORS_ORIGINS` | no | Vite dev origins | Comma-separated. |
| `REPO_IDLE_TTL_HOURS` | no | `12` | Idle time before deletion. |
| `REPO_CLEANUP_INTERVAL_MINUTES` | no | `15` | Sweep cadence, and worst-case delay before an expired repo is reclaimed. |
| `REPO_CLEANUP_ENABLED` | no | `true` | Disable expiry entirely. |

Frontend, prefixed `VITE_`: `VITE_API_BASE_URL` (default
`http://localhost:8000`), resolved once in `lib/env.ts`. `frontend/.env` is
gitignored as machine-specific.

## Tests

```bash
./venv/bin/python -m pytest tests/ -q   # 88
cd frontend && npm run typecheck && npm run build
```

`test_retrieval_quality.py` (escaping, RRF, symbols), `test_cleanup.py`
(expiry, the `processing` guard, deletion ordering, retry), `test_rag_pipeline.py`
(stage order, citations from the reranked set), `test_api_routes.py` (no
mutating GET), `test_repository_lifecycle.py` (status transitions, 409), plus
parser, chunker, paths, embeddings, context, and citation coverage. Tests use
SQLite fixtures — keyword ranking is exercised on both engines precisely
because of the portability problem above.

## Limitations

- **No authentication.** Anyone who can reach the API can read, index, and
  expire repositories. CORS is origin-restricted, which is not access control.
- **Re-indexing does not fetch updates.** The clone is skipped if `.git`
  exists, so re-indexing a stale clone re-embeds old contents. No `git pull`.
- **No manual delete route.** Repositories are removed only by the sweeper.
- **`git clone` is a blocking subprocess** with no timeout or depth limit, and
  only public GitHub URLs are accepted (regex in `is_valid_github_url`).
- **No rate limiting**, and no `VACUUM` automation.
- **The Docker path is unbuilt.** `Dockerfile` and `docker-compose.yml` exist
  but have never been run; treat them as unmaintained. `scripts/dev.sh` is the
  supported path.

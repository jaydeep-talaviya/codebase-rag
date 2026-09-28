# Codebase RAG Assistant — Frontend

A React + TypeScript interface for the FastAPI RAG backend. Connect a GitHub
repository, watch it get indexed, then ask questions that are answered from the
code itself and cited back to you as file + line ranges.

The UI owns **no RAG logic**. Cloning, filtering, chunking, embedding, vector
search, hybrid retrieval, reranking, context building and generation all happen
server-side. This app is a thin, well-typed client over those capabilities.

---

## Quick start

```bash
cd frontend
cp .env.example .env      # adjust VITE_API_BASE_URL if your backend is elsewhere
npm install
npm run dev               # http://localhost:5173
```

| Script              | Purpose                                  |
| ------------------- | ---------------------------------------- |
| `npm run dev`       | Vite dev server with HMR                 |
| `npm run build`     | Typecheck (`tsc -b`) then production build |
| `npm run preview`   | Serve the production build               |
| `npm run typecheck` | Types only                               |

---

## Required backend change: CORS

The frontend and backend run on different origins (`localhost:5173` vs
`localhost:8000`), so **the browser will block every request until the backend
opts into CORS.** `app/main.py` currently has no CORS middleware, so add this:

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,          # must stay False while allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Alternative, no backend change:** serve the API through Vite's dev proxy
instead of a cross-origin call. Add to `vite.config.ts`:

```ts
server: {
  proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') } },
}
```

then set `VITE_API_BASE_URL=/api` in `.env`. A relative base URL is supported —
`src/lib/http.ts` resolves it against the page origin.

The header badge doubles as a connectivity indicator: green when
`GET /health` answers, red when the backend is unreachable.

---

## Configuration

All environment access is confined to `src/lib/env.ts`. No component reads
`import.meta.env`.

```bash
VITE_API_BASE_URL=http://localhost:8000   # no trailing slash
```

---

## API service layer

`src/lib/api.ts` is the only module that knows the backend exists. Everything
else consumes typed, camelCase, already-validated objects.

```
src/lib/api.ts      route map + snake_case → camelCase normalisation
src/lib/http.ts     fetch wrapper: timeouts, abort, ApiError, FastAPI `detail`
src/lib/env.ts      VITE_API_BASE_URL, request budgets
```

`ApiError` normalises every failure into one shape with a `kind`
(`network` / `timeout` / `not_found` / `validation` / `conflict` / `server`), so
components render a message without ever inspecting a `Response`.

### Route compatibility

The deployed backend and the documented RESTful contract disagree on method and
path. Rather than break against one, each operation tries the current shape
first and falls back to the documented shape on `404`/`405` only — a real
`400`/`500` surfaces immediately. Create also sends the URL in **both** the JSON
body and the query string, so a body-reading and a query-reading backend are
both satisfied.

| Operation   | Tries                                | Then falls back to                        |
| ----------- | ------------------------------------ | ----------------------------------------- |
| `createRepository` | `POST /repositories/?url=` + body | `POST /repositories` + body               |
| `cloneRepository`  | `POST /repositories/{id}/ingest`  | `GET /repositories/{id}/ingest`           |
| `indexRepository`  | `POST /repositories/{id}/index`    | `GET /repositories/{id}/files`            |
| `askRepository`    | `POST /repositories/{id}/ask`      | `GET /repositories/search?query=&repository_id=` |
| `getRepository`    | `GET /repositories/{id}`           | locate in `GET /repositories/`            |
| `fetchRepositoryFile` | `GET /repositories/{id}/files/{path}` | — (single shape, used for citation previews) |

If the backend is later refactored to the documented contract, this file is the
only one that changes.

---

## Project structure

```
src/
├─ App.tsx                  view switch: landing vs. workspace
├─ types/api.ts             the UI-facing contract
├─ lib/
│  ├─ env.ts                VITE_API_BASE_URL (only place env is read)
│  ├─ http.ts               fetch + ApiError + route fallback
│  ├─ api.ts                the endpoint map
│  ├─ highlight.ts          curated highlight.js languages + Pygments→hljs map
│  ├─ language.ts           file extension → language inference
│  └─ markdown.tsx          answer rendering
├─ hooks/
│  ├─ useTheme.ts           dark-first, persisted
│  ├─ useRepository.ts      register → clone → index → ready
│  └─ useChat.ts            transcript + in-flight ask lifecycle
└─ components/              presentational, one concern each
```

State lives in three hooks rather than a store — the app has one repository and
one conversation, so a global store would be ceremony without benefit.

---

## Behaviour notes

**Ingestion is one long request.** The backend clones and indexes inside
synchronous calls, so `useRepository` advances through the *real* pipeline
stages (`cloning → parsing → chunking → embedding`) on a timer to keep the wait
legible. The labels are actual pipeline stages, not filler. Ingestion gets a
15-minute budget; questions get 30 seconds.

**Restoring a session.** The active repository id is kept in `localStorage` and
revalidated on load, so a refresh drops you back into the same workspace.

**Citation preview.** Expanding a source fetches the real file from
`GET /repositories/{id}/files/{path}` and opens it *at the cited lines*: the
cited range gets a tinted row, a 2px accent bar down the left edge, and a
bold accent line number in the gutter, and the scroller centres that range on
open. The fetch is lazy (first expand only) and cached per card, so re-opening
is instant and the transcript stays cheap. The endpoint accepts both the stored
`data/repositories/{id}/...` citation form and a repo-relative path; if it is
missing, the card falls back to an inline snippet when the API supplied one, and
otherwise shows the failure reason instead of a blank block.

**Citations only list what the model read.** The backend reranks its top 20
retrieved chunks down to 5, and those same 5 are what reach the prompt — so the
source list shows 5, not 20. Listing the pre-rerank pool would have credited the
answer to 15 passages the model never saw. Duplicate ranges are collapsed, and
each source carries its Pygments language rather than a guess from the extension.

**Session restore respects the repository status.** Only `completed` reopens a
workspace. A repository left `processing` (interrupted run) or `failed` sends you
back to the landing page with an explanation instead of an empty workspace where
every answer would be "no relevant code found".

**One limit worth stating:** the file endpoint returns whole files, so a cited
file is loaded in full. Files above 1 MB are rejected by the backend, which is the
same cap ingestion uses — so anything you can cite is something you can open.

**The "no relevant code" state is real.** A response with zero sources renders
*"We couldn't find enough relevant code to answer this question"* with a retry
action, rather than an empty bubble.

---

## Design system

Tailwind v4, CSS-first. Tokens live in `src/index.css`:

- **Colour** — semantic names (`canvas`, `surface`, `line`, `fg`, `muted`,
  `accent`, `cyan`, `success`, `warn`, `danger`). Dark is the default; light mode
  overrides the same variables under `[data-theme='light']`, so every utility
  flips without a single conditional class.
- **Type** — Inter for UI, JetBrains Mono for code and file paths.
- **Motion** — `fade-up`, `pop-in`, `shimmer`, `pulse-ring`. Used only for
  entry, loading and status; never on hover-only affordances.
- **Syntax highlighting** — hand-rolled token colours that follow the theme,
  so code blocks adapt when you switch modes.

Code is highlighted line-by-line so each row can carry a gutter number offset to
the citation's `start_line` — row 1 of a snippet from line 128 reads `128`.
Trade-off: a construct spanning a line boundary (block comment, template
literal) loses continuity, which is worth it for exact line alignment.

---

## Verified

The full flow was driven in a real headless Chrome against a mock backend:
landing render, inline URL validation, ingest progress, workspace, suggestion
chip, staged loading indicator, Markdown answer, source expansion, syntax
highlighting with offset line numbers, light/dark toggle, no horizontal overflow
at 700px, repository switching, plus both error paths (retrieval returns nothing,
and a 500 with an LLM-shaped `detail`).

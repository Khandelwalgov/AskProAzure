# AskPro.AI

AskPro.AI is a local-first RAG builder. It supports personal document chat and an organization workflow where an admin uploads a corpus, sets a system prompt, and exposes either an API endpoint or a hosted public chat link.

## Local Defaults

- Backend: Flask on `http://127.0.0.1:5000`
- Frontend: Vite on `http://127.0.0.1:5173` or the next free port
- Database: local SQLite via `ASKPRO_DATABASE_URI=sqlite:///askpro_local.db`
- Files: `uploads/`
- Vectors: `vectors/`
- Embeddings: local hashing embeddings, with optional local sentence-transformer or Azure embeddings
- LLM: disabled by default, so answers return retrieved FAISS passages with citations


## Project Docs

- `HANDOVER.md`: current technical/product state, architecture, endpoints, RAG pipeline, risks, and next steps.
- `AGENTS.md`: precise instructions for future coding agents working in this repo.
- `RUNBOOK.md`: local startup, verification, smoke tests, API checks, and troubleshooting.
- `ROADMAP.md`: product direction, RAG/platform roadmap, vertical options, and beta readiness.
- `.env.local.example`: supported environment variables and local defaults.

## Run

Backend:

```powershell
venv\Scripts\python.exe app.py
```

Frontend:

```powershell
cd frontend
npm run dev
```

Build the frontend for Flask static serving:

```powershell
cd frontend
npm run build
```

## Organization Flow

1. Sign up and select `Organization account`.
2. You are redirected to `/admin`.
3. Upload corpus documents.
4. Edit the system prompt, chat title, API/public toggles, and allowed API origins.
5. Use either:
   - API endpoint: `POST /api/chat` with `X-API-Key`
   - Hosted chat link: `/public/<public_id>`

Allowed origins can be set to `*` or one origin per line, such as `https://example.com`. Server-to-server requests without an `Origin` header are allowed when API access is enabled.

API request shape:

```http
POST /api/chat
X-API-Key: askpro_...
Content-Type: application/json

{ "message": "Question here" }
```

## Verification

```powershell
venv\Scripts\python.exe -m py_compile app.py rag_utils.py parser_utils.py
cd frontend
npm run lint
npm run build
```

With the backend running:

```powershell
venv\Scripts\python.exe scripts\smoke_org_flow.py
venv\Scripts\python.exe scripts\smoke_rate_limit.py
```

## Backend-Owned Controls

Rate limits are configured by the app operator through environment variables, not organization admins. Defaults apply to session chat, API-key chat, and public hosted chat.

Hybrid RAG is enabled by default. New uploads receive chunk metadata including chunk ids, chunk keywords, token counts, source labels, and location metadata. PDFs are indexed page by page; TXT files carry line ranges; DOCX files carry section/paragraph ranges where reliable page numbers are not available. Retrieval combines vector candidates with keyword candidates, then reranks using semantic score, keyword overlap, metadata overlap, and phrase matches. API responses include both `sources` and `citations`, and the chat UI renders source cards under each answer.

Optional quality upgrades are already wired but opt-in: set `RAG_EMBEDDING_PROVIDER=sentence-transformers` when a local model is available, or set `RAG_CROSS_ENCODER_MODEL` to use a local cross-encoder reranker. Useful knobs are listed in `.env.local.example`.

# AGENTS.md

This file gives future coding agents precise operating instructions for `E:\projects\AskProAzure`.

## Mission

AskPro.AI is being converted from a broken Azure-hosted RAG app into a local-first organization RAG builder that can later become production SaaS. Preserve the local-first path at all times. The app must continue to run without Azure credentials, hosted LLM credentials, or network downloads.

Current default product mode:

- Backend: Flask + SQLAlchemy.
- Frontend: Vite + React.
- Database: local SQLite by default.
- Storage: local filesystem by default.
- Vector store: FAISS directories under `vectors/`.
- Embeddings: local hashing embeddings by default.
- LLM: disabled by default; chat returns cited retrieval-only passages.
- Organization admin: `/admin`.
- Public hosted chat: `/public/:publicId`.

## Non-Negotiable Invariants

Keep these true unless the user explicitly asks to change them:

- Local mode must work with no `.env` file.
- Do not require Azure credentials for startup, upload, retrieval, or local smoke tests.
- Do not hardcode production API URLs in frontend code. Use `frontend/src/api.js`.
- Do not log cookies, sessions, auth headers, API keys, document text, retrieved chunks, or secrets.
- Do not expose rate-limit configuration in the organization admin UI unless explicitly requested.
- Keep API response compatibility: `sources` should continue to exist even though `citations` is now the cleaner contract.
- Keep upload/delete vector naming aligned through `vector_path_for(user.uuid, file_record.path)`.
- FAISS indexes are directories even though their names end in `.faiss`.
- Existing older FAISS indexes should still load if possible, even if they lack newer citation metadata.
- Parser failures should raise clear errors, not return fake document text.

## Local Run Commands

Backend from repo root:

```powershell
venv\Scripts\python.exe app.py
```

Frontend from `frontend/`:

```powershell
npm run dev
```

Build frontend for Flask static serving:

```powershell
cd frontend
npm run build
```

Health check:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/keep-alive
```

Expected local health shape:

```json
{
  "status": "ok",
  "storage_backend": "local",
  "embedding_provider": "local",
  "llm_provider": "none"
}
```

## Verification Commands

Run these after backend/RAG/parser changes:

```powershell
venv\Scripts\python.exe -m py_compile app.py rag_utils.py parser_utils.py scripts\smoke_org_flow.py scripts\smoke_rate_limit.py
```

Run these after frontend changes:

```powershell
cd frontend
npm run lint
npm run build
```

Run these with the backend already running:

```powershell
venv\Scripts\python.exe scripts\smoke_org_flow.py
venv\Scripts\python.exe scripts\smoke_rate_limit.py
```

Known build note:

- `npm run build` currently warns about a large chunk due to existing Three.js/react-three visuals. This is a warning, not a failure.

## Important Files

Backend:

- `app.py`: routes, models, storage, auth, admin config, RAG payloads, rate limits, static serving.
- `rag_utils.py`: embeddings, chunking, metadata, FAISS retrieval, hybrid reranking, optional reranker.
- `parser_utils.py`: PDF/DOCX/TXT extraction with citation metadata.
- `scripts/smoke_org_flow.py`: end-to-end org/API/public/citation smoke coverage.
- `scripts/smoke_rate_limit.py`: in-memory rate-limit smoke coverage.

Frontend:

- `frontend/src/api.js`: API URL helper.
- `frontend/src/App.jsx`: route map.
- `frontend/src/pages/AdminDashboard.jsx`: org admin workspace.
- `frontend/src/pages/ChatDashboard.jsx`: logged-in chat.
- `frontend/src/pages/PublicChat.jsx`: hosted public chat.
- `frontend/src/components/CitationList.jsx`: citation card rendering.

Docs:

- `HANDOVER.md`: status and architecture handoff.
- `RUNBOOK.md`: operating procedure.
- `ROADMAP.md`: future product and technical direction.
- `.env.local.example`: supported env knobs.

## Current Data Model

`User`:

- `email`, `password`, `is_org`, `uuid`.

`File`:

- `filename`, `path`, `mimetype`, `user_id`.

`OrganizationSettings`:

- `system_prompt`, `api_key`, `public_id`, `chat_title`, `api_enabled`, `public_enabled`, `allowed_origins`.

SQLite compatibility:

- `ensure_organization_settings_schema()` adds newer org columns for local SQLite only.
- Do not expand this into a serious migration system. Use proper migrations for production work.

## RAG And Citation Contract

Upload/indexing:

- `/upload` accepts PDF, DOCX, TXT only.
- `extract_document_parts()` must return parts shaped like `{ "text": str, "metadata": dict }`.
- `chunk_and_store()` accepts either plain text or document parts.
- New chunks should preserve `filename`, `storage_key`, `source_type`, source location metadata, `part_id`, `source_label`, and chunk-level enrichment.

Citation metadata expectations:

- PDF: `page`, `page_label`, `page_count`.
- TXT: `line_start`, `line_end`.
- DOCX: `section_heading`, `section_index`, `paragraph_start`, `paragraph_end`.
- All chunks: `chunk_id`, `chunk_index`, `chunk_keywords`, `token_count`, `char_count`, `source_label`.

Retrieval:

- Use `retrieve_ranked_chunks()` from `rag_utils.py`.
- Retrieval combines FAISS semantic candidates, keyword candidates, metadata overlap, and phrase matches.
- Optional cross-encoder reranking is env-driven via `RAG_CROSS_ENCODER_MODEL` and must remain optional.
- Optional sentence-transformer embeddings are env-driven and must remain optional.

Response contract:

- `answer`: markdown answer text.
- `chunks`: raw selected chunk text.
- `citations`: preferred source metadata array.
- `sources`: compatibility alias with the same citation objects.
- `mode`: `retrieval-only` or `llm`.
- `retrieval_strategy`: currently `hybrid-semantic-keyword-rerank`.

With `LLM_PROVIDER=none`, answer text should clearly indicate local retrieval-only mode and include cited retrieved passages. With `LLM_PROVIDER=azure`, prompts must instruct the model to cite `[S1]` style labels.

## Organization Builder Rules

Organization accounts (`User.is_org=True`) use `/admin`.

Admin config fields:

- `system_prompt`
- `chat_title`
- `api_enabled`
- `public_enabled`
- `allowed_origins`
- `api_key`
- `public_id`

Admin endpoints:

- `GET /admin/config`
- `POST /admin/config`
- `POST /admin/regenerate-api-key`

External chat endpoints:

- `POST /api/chat` with `X-API-Key` or `Authorization: Bearer ...`.
- `GET /public-chat/<public_id>/meta`.
- `POST /public-chat/<public_id>`.

Origin policy:

- Browser API-key calls use the `Origin` header and must obey `allowed_origins`.
- Server-to-server calls with no `Origin` are allowed when API access is enabled.
- `*` allows all origins.

## Rate Limit Rules

Rate limits are operator-owned and env-configured.

Scopes:

- `SESSION_CHAT`: logged-in `/query`.
- `API_CHAT`: `/api/chat`.
- `PUBLIC_CHAT`: `/public-chat/<public_id>`.

Current implementation:

- In-memory `RATE_LIMIT_BUCKETS` in `app.py`.
- Good for local/single-process MVP.
- Not safe for multi-worker production. Move to Redis before deployment.

Do not add rate-limit controls to `AdminDashboard` unless the user explicitly asks.

## Frontend Rules

- Keep frontend API calls routed through `apiUrl(...)` from `frontend/src/api.js`.
- Keep `/public/:publicId` simple and free of admin/upload controls.
- Render citations using `CitationList` rather than duplicating source-card markup.
- Preserve no-fluff public chat UX.
- For admin UI, prefer practical operational controls over marketing-style layouts.
- Avoid introducing large additional frontend dependencies without need.
- If touching landing/Three.js code, consider code-splitting because the current main bundle is already large.

## Security Rules

Never log:

- API keys.
- Cookies.
- Session contents.
- Authorization headers.
- Full document text.
- Retrieved chunk bodies in logs.

Production blockers to keep visible:

- Plaintext API keys.
- Dev fallback `FLASK_SECRET_KEY`.
- Missing CSRF protection for cookie auth.
- No migrations.
- SQLite default.
- In-memory rate limits.
- No audit/usage logs.

## Environment Rules

Local defaults should work without `.env`.

Use `.env.local.example` as the source of truth for supported knobs. If adding an env variable, update:

- `.env.local.example`
- `HANDOVER.md` if it affects architecture or operation
- `RUNBOOK.md` if it affects local usage

Azure must stay opt-in:

- `STORAGE_BACKEND=azure`
- `RAG_EMBEDDING_PROVIDER=azure`
- `LLM_PROVIDER=azure`
- `USE_REMOTE_DATABASE=true`

Do not read old `SQLALCHEMY_DATABASE_URI` unless `USE_REMOTE_DATABASE=true` is set.

## Git And Generated Data

Treat these as local/generated and do not commit them:

- `uploads/`
- `vectors/`
- `temp/`
- `instance/`
- `.env`
- `frontend/dist/` unless the user explicitly wants build output committed

Before making broad edits, check `git status --short`. The worktree may already contain user or prior-agent changes. Do not revert unrelated changes.

## Common Failure Modes

No vectors found:

- User has not uploaded documents.
- Vector folder was deleted.
- Upload failed before FAISS save.

Weak retrieval:

- Local hashing embeddings are lexical.
- Reupload documents to populate newer citation metadata.
- Consider true semantic embeddings and reranking.

PDF page metadata missing:

- Index predates metadata extraction changes.
- PDF is scanned/image-only and needs OCR.

API origin blocked:

- `allowed_origins` does not include the browser origin.
- Server-to-server requests without `Origin` should still work.

Backend startup fails on Azure vars:

- An env var likely opted into Azure mode. Return to local defaults.

## When Adding Features

Preferred order:

1. Read current implementation and docs.
2. Preserve local default behavior.
3. Implement narrowly.
4. Add or update smoke/unit coverage where practical.
5. Run compile/lint/build/smoke tests.
6. Update docs for new commands, env vars, endpoints, or product behavior.

For RAG quality work, do not tune blindly. Add an evaluation set before major retrieval changes unless the user explicitly asks to defer evaluation.

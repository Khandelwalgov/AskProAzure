# AskPro.AI Handover

Last updated: 2026-07-09
Workspace: `E:\projects\AskProAzure`

## Executive Summary

AskPro.AI is now a local-first Flask + React RAG builder. The original Azure-hosted path is intentionally not assumed to work because the hosting credentials are no longer available in this workspace. The app can run locally without Azure Blob Storage, Azure OpenAI, or remote database credentials.

Current product shape:

- Personal users can sign up, log in, upload documents, and query their own corpus.
- Organization users can sign up, log in, open an admin panel, upload an organization corpus, configure a system prompt, and expose either an API endpoint or a hosted public chat link.
- Retrieval works locally with FAISS and no network calls.
- LLM generation is disabled by default. In local mode, the app returns retrieved passages with `[S1]`, `[S2]` style citations, scores, snippets, and source metadata.
- Azure storage, Azure embeddings, and Azure chat remain opt-in paths for later if credentials are restored.

The result is a strong local MVP and technical recovery base. It is not yet production SaaS.

## What Works Today

Core local path:

- Flask backend starts on `http://127.0.0.1:5000`.
- React/Vite frontend runs on `http://127.0.0.1:5173` or the next free Vite port.
- Local SQLite is used by default through `ASKPRO_DATABASE_URI=sqlite:///askpro_local.db`.
- Local file storage is used by default under `uploads/`.
- FAISS indexes are written under `vectors/`.
- Temporary uploads/parsing files use `temp/`.
- Local hashing embeddings are used by default and require no network.
- Session cookies are used for local login.
- CORS defaults allow local Vite origins on ports `5173` and `5174`.

Organization builder path:

- Organization signup/login redirects users toward `/admin`.
- Admin panel supports corpus upload/delete, system prompt, chat title, API/public toggles, allowed API origins, API key display/regeneration, public link, and iframe snippet.
- `/api/chat` accepts `X-API-Key` or `Authorization: Bearer ...`.
- `/public/:publicId` serves a simple hosted chat UI with no admin/upload controls.
- Public chat API is `/public-chat/<public_id>`.

Retrieval/citations path:

- Upload parsing preserves source location metadata.
- PDFs are indexed page by page with `page`, `page_label`, and `page_count`.
- TXT files are indexed by text blocks with `line_start` and `line_end`.
- DOCX files are indexed by heading/section blocks with paragraph ranges where reliable page numbers are not available.
- Chunks include `chunk_id`, `part_id`, `source_label`, `chunk_keywords`, `chunk_index`, token count, char count, and optional splitter `start_index`.
- API responses include both `citations` and compatibility `sources` arrays.
- Logged-in chat and public chat render source cards under bot answers.

Backend-owned controls:

- Session/API/public chat rate limits are configurable by environment variables.
- Rate limits are intentionally not exposed in the organization admin UI.
- Current limiter is in-memory and suitable for local/single-process use only.

## Important Product Caveats

- `LLM_PROVIDER=none` is the default. This means answers are retrieval-only summaries/passages, not generated natural-language synthesis.
- Local hashing embeddings are robust for offline recovery and lexical search, but they are not the best possible semantic embeddings.
- Existing FAISS indexes created before the citation metadata work still load, but they will not have rich page/line/paragraph metadata. Reupload source documents to rebuild richer indexes.
- API keys are currently stored in plaintext so the MVP admin UI can display/copy them. Production should hash keys and show new keys only once.
- Rate limits are in-memory. Production needs Redis or another shared store before running multiple workers.
- SQLite and `db.create_all()` are fine for local MVP, but production needs migrations and a production database.
- Browser visual QA was blocked by a Windows sandbox helper failure in the Codex desktop browser plugin. Backend and build verification passed.

## Repository Map

Backend:

- `app.py`: Flask app, auth, uploads, storage abstraction, admin config, API/public chat endpoints, rate limiting, RAG response construction, static frontend serving.
- `rag_utils.py`: embeddings, chunking, metadata enrichment, FAISS load/save, hybrid retrieval, optional sentence-transformer embeddings, optional cross-encoder reranking.
- `parser_utils.py`: PDF/DOCX/TXT extraction with citation metadata.
- `requirements.txt`: Python dependencies.
- `scripts/smoke_org_flow.py`: durable end-to-end org/API/public/citation smoke test.
- `scripts/smoke_rate_limit.py`: rate limiter smoke test.

Frontend:

- `frontend/src/App.jsx`: routes for landing, signup, login, chat, admin, and public chat.
- `frontend/src/api.js`: central API URL helper. Do not hardcode production URLs elsewhere.
- `frontend/src/pages/AdminDashboard.jsx`: organization admin workspace.
- `frontend/src/pages/ChatDashboard.jsx`: logged-in chat UI with citation rendering.
- `frontend/src/pages/PublicChat.jsx`: hosted public chat UI with citation rendering.
- `frontend/src/components/CitationList.jsx`: reusable source/citation card renderer.
- `frontend/src/components/FileManager.jsx` and `Sidebar.jsx`: upload/list/delete flows for older/personal chat surfaces.

Docs:

- `README.md`: quick project overview and common commands.
- `HANDOVER.md`: this technical/product handover.
- `AGENTS.md`: operating instructions for future coding agents.
- `RUNBOOK.md`: exact local operations and verification workflow.
- `ROADMAP.md`: recommended product/technical next steps and verticals.
- `.env.local.example`: local/operator environment variables.

Generated or local-only directories:

- `uploads/`: local uploaded files, ignored by git.
- `vectors/`: FAISS index directories, ignored by git.
- `temp/`: temporary upload/parsing files, ignored by git.
- `instance/`: Flask/SQLite local instance data, ignored by git.
- `frontend/dist/`: generated build output.

## Data Model

`User` in `app.py`:

- `id`: integer primary key.
- `email`: unique login email.
- `password`: hashed password.
- `is_org`: organization account flag.
- `uuid`: stable user workspace id used for storage/vector folder names.

`File` in `app.py`:

- `id`: integer primary key.
- `filename`: original safe display filename.
- `path`: storage key. For local mode this is relative to `uploads/`.
- `mimetype`: uploaded file mimetype.
- `user_id`: owner.

`OrganizationSettings` in `app.py`:

- `user_id`: organization owner.
- `system_prompt`: org-specific prompt for the future LLM path.
- `api_key`: currently plaintext MVP API key.
- `public_id`: opaque id used by hosted public chat links.
- `chat_title`: public chat/admin title.
- `api_enabled`: operator/admin toggle for API use.
- `public_enabled`: operator/admin toggle for hosted public link.
- `allowed_origins`: newline/comma-normalized browser origins for API-key calls. `*` allows all.

SQLite auto-migration currently only adds missing `OrganizationSettings` columns for local compatibility. This is not a full migration system.

## Backend Endpoints

Auth/session:

- `POST /signup`: creates user; accepts `is_organization` for org accounts.
- `POST /login`: authenticates user and initializes session.
- `POST /logout`: clears session.
- `GET /whoami`: returns login/org status.

Corpus/files:

- `POST /upload`: authenticated upload for PDF/DOCX/TXT. Stores file and builds FAISS index.
- `GET /list-files`: authenticated list of uploaded files.
- `POST /delete-file`: authenticated delete of file record, local/blob storage object, and vector index directory.
- `GET /view-file/<file_id>`: returns a local download URL or Azure SAS URL.
- `GET /download-file/<file_id>`: local file response when `STORAGE_BACKEND=local`.

RAG chat:

- `POST /query`: authenticated session chat for personal/org users.
- `POST /api/chat`: organization API-key chat endpoint.
- `GET /public-chat/<public_id>/meta`: public chat title metadata.
- `POST /public-chat/<public_id>`: hosted public chat endpoint.

Admin:

- `GET /admin/config`: organization settings, files, API/public link data.
- `POST /admin/config`: update prompt, title, toggles, allowed origins.
- `POST /admin/regenerate-api-key`: generates and stores a new plaintext MVP API key.

Health/static:

- `GET /keep-alive`: database/storage/embedding/LLM status.
- `GET /` and `GET /<path>`: serves `frontend/dist` when built, otherwise returns API status JSON.

## RAG Pipeline

Upload/index flow:

1. `/upload` validates session, file count, file size, extension, and mimetype.
2. File is saved to `temp/`.
3. File is copied to local storage or uploaded to Azure Blob depending on `STORAGE_BACKEND`.
4. `extract_document_parts()` parses the file into one or more parts with metadata.
5. `chunk_and_store()` turns parts into LangChain `Document` objects.
6. `RecursiveCharacterTextSplitter` creates chunks using `RAG_CHUNK_SIZE` and `RAG_CHUNK_OVERLAP`.
7. Chunk metadata is enriched with stable ids, keywords, counts, source labels, and location fields.
8. FAISS index is created and saved under `vectors/<user_uuid>/<stored_file_basename>.faiss/`.
9. `File` row is committed.

Query flow:

1. Chat endpoint identifies the user/org settings.
2. Rate limit is checked for the appropriate scope.
3. All FAISS index directories for the user are loaded.
4. `retrieve_ranked_chunks()` gathers semantic/vector candidates from FAISS.
5. It also scans all chunks for keyword/metadata/phrase candidates.
6. Candidates are reranked by weighted semantic, keyword, metadata, and phrase scores.
7. Optional cross-encoder reranking is applied if `RAG_CROSS_ENCODER_MODEL` is set and available locally.
8. `build_rag_payload()` returns answer text, chunks, citations, sources, mode, and retrieval strategy.
9. If `LLM_PROVIDER=azure`, retrieved context is sent to Azure OpenAI and the model is instructed to cite `[S1]` labels.
10. If `LLM_PROVIDER=none`, the app returns retrieval-only cited passages.

Citation fields include:

- `id`, `label`, `display_name`, `filename`, `storage_key`, `source_type`, `location`, `source_label`
- `page`, `page_label`, `page_count`
- `section_heading`, `section_index`, `paragraph_start`, `paragraph_end`
- `line_start`, `line_end`, `part_index`, `part_id`
- `chunk_id`, `chunk_index`, `chunk_keywords`, `token_count`, `char_count`, `start_index`
- `snippet`, `score`, `semantic_score`, `keyword_score`, `metadata_score`, `phrase_score`
- `cross_encoder_score`, `cross_encoder_score_raw`, `matched_terms`

## Environment Variables

Local defaults work with no `.env` file.

Core local defaults:

- `STORAGE_BACKEND=local`
- `LOCAL_STORAGE_ROOT=uploads`
- `VECTOR_ROOT=vectors`
- `TEMP_ROOT=temp`
- `RAG_EMBEDDING_PROVIDER=local`
- `LOCAL_EMBEDDING_DIM=1536`
- `LLM_PROVIDER=none`
- `ASKPRO_DATABASE_URI=sqlite:///askpro_local.db`
- `USE_REMOTE_DATABASE=false`
- `FLASK_RUN_HOST=127.0.0.1`
- `FLASK_RUN_PORT=5000`
- `FLASK_DEBUG=false`

Rate limit knobs:

- `RATE_LIMIT_ENABLED=true`
- `RATE_LIMIT_WINDOW_SECONDS=60`
- `RATE_LIMIT_MAX_REQUESTS=60`
- `RATE_LIMIT_SESSION_CHAT_MAX_REQUESTS=60`
- `RATE_LIMIT_API_CHAT_MAX_REQUESTS=30`
- `RATE_LIMIT_PUBLIC_CHAT_MAX_REQUESTS=20`
- Scope-specific window variables are also supported, for example `RATE_LIMIT_API_CHAT_WINDOW_SECONDS`.

RAG knobs:

- `RAG_CHUNK_SIZE=700`
- `RAG_CHUNK_OVERLAP=100`
- `RAG_SEMANTIC_CANDIDATES=30`
- `RAG_KEYWORD_CANDIDATES=30`
- `RAG_PER_INDEX_FINAL_K=12`
- `RAG_CONTEXT_CHUNKS=10`
- `RAG_RERANK_SEMANTIC_WEIGHT=0.52`
- `RAG_RERANK_KEYWORD_WEIGHT=0.28`
- `RAG_RERANK_METADATA_WEIGHT=0.12`
- `RAG_RERANK_PHRASE_WEIGHT=0.08`

Optional local semantic embeddings:

- `RAG_EMBEDDING_PROVIDER=sentence-transformers`
- `SENTENCE_TRANSFORMER_MODEL=sentence-transformers/all-MiniLM-L6-v2`
- `SENTENCE_TRANSFORMER_LOCAL_FILES_ONLY=true`

Optional local cross-encoder rerank:

- `RAG_CROSS_ENCODER_MODEL=<local-or-cached-model-name>`
- `RAG_CROSS_ENCODER_LOCAL_FILES_ONLY=true`
- `RAG_CROSS_ENCODER_CANDIDATES=20`
- `RAG_CROSS_ENCODER_WEIGHT=0.35`

Azure opt-in:

- `STORAGE_BACKEND=azure`
- `AZURE_STORAGE_CONNECTION_STRING=...`
- `AZURE_STORAGE_ACCOUNT_KEY=...`
- `RAG_EMBEDDING_PROVIDER=azure`
- `LLM_PROVIDER=azure`
- `AZURE_OPENAI_API_KEY=...`
- `AZURE_OPENAI_ENDPOINT=...`
- `AZURE_OPENAI_API_VERSION=...`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT=...`
- `AZURE_OPENAI_DEPLOYMENT=...`
- `USE_REMOTE_DATABASE=true`
- `SQLALCHEMY_DATABASE_URI=...`

## Verification Status

Most recent successful verification during implementation:

```powershell
venv\Scripts\python.exe -m py_compile app.py rag_utils.py parser_utils.py scripts\smoke_org_flow.py scripts\smoke_rate_limit.py
cd frontend
npm run lint
npm run build
cd ..
venv\Scripts\python.exe scripts\smoke_org_flow.py
venv\Scripts\python.exe scripts\smoke_rate_limit.py
```

Observed results:

- Python compile passed.
- Frontend lint passed.
- Frontend build passed.
- `scripts/smoke_org_flow.py` passed, including generated PDF page metadata, TXT line metadata, API/public toggles, allowed-origin blocking, API chat, and public chat.
- `scripts/smoke_rate_limit.py` passed.
- Vite build warns about a large JavaScript chunk because of existing Three.js/react-three landing visuals. This is expected but should be revisited.

## Known Risks And Debt

Security/auth:

- Replace fallback `FLASK_SECRET_KEY` in any shared environment.
- Add CSRF protection or move to token-based auth before exposing session-cookie flows publicly.
- Hash API keys and show regenerated keys only once.
- Add audit logging for admin config changes and API-key use, without logging secrets or document text.
- Tighten CORS and cookie settings for deployed domains.

Persistence/ops:

- Replace `db.create_all()` and local schema shims with Alembic/Flask-Migrate.
- Move from SQLite to Postgres for production.
- Move rate-limit buckets to Redis or another shared store.
- Add background ingestion jobs for large documents.
- Add structured logging, monitoring, and error reporting.
- Add storage quotas and document ingestion limits per organization.

RAG quality:

- Use real semantic embeddings in production.
- Use a reliable reranker or hosted rerank service.
- Add score thresholds and low-confidence no-answer behavior.
- Add OCR for scanned PDFs.
- Improve table extraction and preserve table structure.
- Add parent-child chunking or section-level context expansion.
- Add query expansion and acronym/entity normalization.
- Add a formal evaluation set before tuning further.

Frontend/product:

- Polish admin UI states: upload progress, ingestion errors, empty states, and disabled states.
- Add API usage logs and request counters for organization admins.
- Add copyable widget script or iframe package with theming options.
- Add team/workspace roles beyond a single org admin account.
- Code-split the landing/Three.js visuals to reduce main bundle size.

Testing:

- Add backend unit tests around parser metadata, retrieval ranking, auth, and rate limits.
- Add frontend component tests for admin config and citation rendering.
- Add e2e tests for signup, login, upload, query, delete, public link, and API-key chat.

## Recommended Next Steps

Immediate:

1. Reupload representative documents so indexes contain the new citation metadata.
2. Add score thresholds/no-answer behavior to avoid presenting weak matches as authoritative.
3. Hash API keys and implement show-once regenerated keys.
4. Add admin-side ingestion status/progress and clearer upload errors.
5. Code-split the landing visuals from the app shell.

Near-term:

1. Add Redis-backed rate limits and usage counters.
2. Add migrations and a production database path.
3. Add a local or hosted true semantic embedding provider.
4. Add OCR/table extraction strategy.
5. Add team roles and workspace-level permissions.

Product focus:

The strongest vertical direction is not a generic chatbot. The best first paid MVP is a citation-backed document assistant for a specific domain with high trust needs. See `ROADMAP.md` for vertical options and priorities.

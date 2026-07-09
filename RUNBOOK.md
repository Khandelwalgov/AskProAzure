# AskPro.AI Local Runbook

Last updated: 2026-07-09
Workspace: `E:\projects\AskProAzure`

This runbook is for starting, verifying, and troubleshooting the local-first AskPro.AI app.

## Quick Start

Start backend from repo root:

```powershell
venv\Scripts\python.exe app.py
```

Start frontend from `frontend/`:

```powershell
cd frontend
npm run dev
```

Open the app:

```text
http://127.0.0.1:5173
```

If Vite reports another port, use that port, commonly:

```text
http://127.0.0.1:5174
```

The backend also serves the built frontend at:

```text
http://127.0.0.1:5000
```

This requires `frontend/dist` to exist, usually after `npm run build`.

## Expected Local Defaults

No `.env` file is required for local mode.

Expected defaults:

- Backend host: `127.0.0.1`
- Backend port: `5000`
- Storage backend: `local`
- Upload root: `uploads/`
- Vector root: `vectors/`
- Temp root: `temp/`
- Database: `sqlite:///askpro_local.db`
- Embeddings: local hashing
- LLM: disabled

Health check:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/keep-alive
```

Expected response:

```json
{
  "embedding_provider": "local",
  "llm_provider": "none",
  "status": "ok",
  "storage_backend": "local"
}
```

## Full Verification

Python compile:

```powershell
venv\Scripts\python.exe -m py_compile app.py rag_utils.py parser_utils.py scripts\smoke_org_flow.py scripts\smoke_rate_limit.py
```

Frontend lint/build:

```powershell
cd frontend
npm run lint
npm run build
cd ..
```

Backend smoke tests, with Flask already running:

```powershell
venv\Scripts\python.exe scripts\smoke_org_flow.py
venv\Scripts\python.exe scripts\smoke_rate_limit.py
```

Expected smoke coverage:

- Organization signup.
- Admin config read/write.
- API/public toggles.
- Allowed-origin enforcement.
- TXT upload and line metadata.
- Generated PDF upload and page metadata.
- API-key chat.
- Public chat metadata and chat.
- Citation payloads.
- In-memory rate-limit 429 behavior.

Known acceptable warning:

- `npm run build` may warn that a chunk is larger than 500 kB. This comes from existing Three.js/react-three landing visuals.

## Manual Product Smoke

1. Open `/signup`.
2. Create an organization account.
3. Confirm redirect/navigation to `/admin`.
4. Upload a TXT, PDF, or DOCX file.
5. Set a short system prompt.
6. Confirm API access and public link are enabled.
7. Copy the public link and open `/public/<public_id>`.
8. Ask a question answerable from the uploaded file.
9. Confirm the bot response includes source cards.
10. For PDF files, confirm source cards include page metadata after reuploading with the current parser.

## API-Key Manual Test

Get the API key from `/admin`, then run:

```powershell
$headers = @{ "X-API-Key" = "askpro_replace_me"; "Content-Type" = "application/json" }
$body = @{ message = "Ask a question from the corpus" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/chat -Method Post -Headers $headers -Body $body
```

Expected response fields:

- `answer`
- `chunks`
- `sources`
- `citations`
- `mode`
- `retrieval_strategy`

Expected local mode:

```json
{
  "mode": "retrieval-only",
  "retrieval_strategy": "hybrid-semantic-keyword-rerank"
}
```

## Public Chat Manual Test

Get `public_id` from `/admin/config` or the admin UI link.

Metadata:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/public-chat/<public_id>/meta
```

Chat:

```powershell
$body = @{ message = "Ask a question from the corpus" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:5000/public-chat/<public_id> -Method Post -ContentType "application/json" -Body $body
```

## Starting And Stopping Backend On Windows

Start hidden background backend:

```powershell
Start-Process -FilePath "venv\Scripts\python.exe" -ArgumentList "app.py" -WorkingDirectory "E:\projects\AskProAzure" -WindowStyle Hidden -PassThru
```

Find matching backend processes:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*AskProAzure*app.py*' } | Select-Object ProcessId,CommandLine
```

Stop matching backend processes:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*AskProAzure*app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

## Local Data Locations

Local database:

- Default URI is `sqlite:///askpro_local.db`.
- With Flask relative SQLite paths, inspect both repo root and `instance/` if looking for the physical file.

Uploaded files:

- `uploads/<user_uuid>/<random>_<filename>`

Vector indexes:

- `vectors/<user_uuid>/<stored_file_basename>.faiss/`

Temporary files:

- `temp/`

Do not commit local data.

## Rebuilding Rich Citation Metadata

Older FAISS indexes may lack page/line/paragraph citation fields. To rebuild metadata:

1. Keep the original source document available.
2. Delete the old file from the app UI or `/delete-file`.
3. Reupload the document.
4. Ask a question and inspect `citations` or source cards.

For PDFs, new indexes should include:

- `page`
- `page_label`
- `page_count`

For TXT, new indexes should include:

- `line_start`
- `line_end`

For DOCX, new indexes should include:

- `section_heading`
- `paragraph_start`
- `paragraph_end`

## Environment Overrides

Copy `.env.local.example` to `.env` only if you need overrides.

Common local overrides:

```powershell
$env:FLASK_RUN_PORT="5000"
$env:VITE_API_BASE_URL="http://127.0.0.1:5000"
```

Disable rate limits locally:

```powershell
$env:RATE_LIMIT_ENABLED="false"
```

Change retrieval context size:

```powershell
$env:RAG_CONTEXT_CHUNKS="12"
```

Use optional local sentence-transformer embeddings only when the model is already installed/cached:

```powershell
$env:RAG_EMBEDDING_PROVIDER="sentence-transformers"
$env:SENTENCE_TRANSFORMER_LOCAL_FILES_ONLY="true"
```

Use optional local cross-encoder reranking only when the model is already installed/cached:

```powershell
$env:RAG_CROSS_ENCODER_MODEL="cross-encoder/ms-marco-MiniLM-L-6-v2"
$env:RAG_CROSS_ENCODER_LOCAL_FILES_ONLY="true"
```

## Azure Opt-In

Azure is not required for local mode. Only enable these when credentials exist and the user asks for Azure mode.

Storage:

```powershell
$env:STORAGE_BACKEND="azure"
$env:AZURE_STORAGE_CONNECTION_STRING="..."
$env:AZURE_STORAGE_ACCOUNT_KEY="..."
```

Embeddings:

```powershell
$env:RAG_EMBEDDING_PROVIDER="azure"
$env:AZURE_OPENAI_API_KEY="..."
$env:AZURE_OPENAI_ENDPOINT="..."
$env:AZURE_OPENAI_API_VERSION="..."
$env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT="..."
```

LLM generation:

```powershell
$env:LLM_PROVIDER="azure"
$env:AZURE_OPENAI_DEPLOYMENT="..."
```

Remote database:

```powershell
$env:USE_REMOTE_DATABASE="true"
$env:SQLALCHEMY_DATABASE_URI="..."
```

## Troubleshooting

Backend will not start:

- Check whether port `5000` is occupied.
- Check `.env` for accidental Azure opt-in without credentials.
- Run `venv\Scripts\python.exe -m py_compile app.py rag_utils.py parser_utils.py`.

Health endpoint fails:

- Backend is not running.
- Database URI is invalid.
- A startup dependency raised during import.

Upload fails with invalid file type:

- Supported types are PDF, DOCX, and TXT.
- Mimetype and extension must both be accepted.

Upload succeeds but query says no vectors:

- Check `vectors/<user_uuid>/` exists.
- Check upload response and backend logs.
- Delete and reupload the file.

Answer has no page metadata:

- Index may be old. Reupload the source document.
- PDF may be image-only/scanned. OCR is not implemented yet.

API returns origin error:

- Add the browser origin to `allowed_origins` in admin config.
- Use `*` for local broad testing.
- Server-to-server requests with no `Origin` should be allowed when API is enabled.

API returns 429:

- Rate limit is working.
- Wait for `Retry-After` seconds or adjust operator env vars.

Public link returns 404:

- `public_enabled` may be false.
- `public_id` may be wrong.
- Organization settings may not exist for that user.

Frontend cannot reach backend:

- Confirm backend health endpoint.
- Confirm `VITE_API_BASE_URL` or default `http://127.0.0.1:5000`.
- Confirm CORS includes current Vite origin.

Weak retrieval quality:

- Local hashing embeddings are lexical.
- Reupload docs for richer metadata.
- Try better chunk settings.
- Enable true semantic embeddings if available locally.
- Add a proper evaluation set before tuning heavily.

## Safe Local Reset

Use resets carefully. These delete local app data.

Typical generated data to clear:

- `uploads/`
- `vectors/`
- `temp/`
- local SQLite database file or `instance/` database file

Before deleting, confirm paths are inside `E:\projects\AskProAzure`.

## Production Readiness Checklist

Do not expose publicly until these are addressed:

- Strong `FLASK_SECRET_KEY`.
- CSRF or token-based auth strategy.
- Hashed API keys and show-once regenerated keys.
- Production database and migrations.
- Redis/shared rate limits.
- HTTPS and secure cookie settings.
- Audit/usage logs.
- Storage quotas.
- Background ingestion.
- Real semantic embeddings/reranking.
- Score thresholds and no-answer behavior.
- OCR/table extraction strategy.
- E2E tests.

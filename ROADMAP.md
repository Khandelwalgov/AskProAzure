# AskPro.AI Roadmap

Last updated: 2026-07-09

## Product Positioning

AskPro.AI should not stay a generic chatbot wrapper. Its strongest position is a citation-backed document assistant for organizations that need fast deployment, simple embedding/API options, and reliable source-grounded answers.

The current MVP already supports the core platform shape:

- Organization admin uploads a corpus.
- Organization admin configures prompt/title/API/public access.
- External systems can call `/api/chat` with an API key.
- Nontechnical users can use a hosted public chat link.
- Responses include source citations and document metadata.

The next product work should make this trustworthy, measurable, and deployable.

## Current Product Quality

Local MVP quality: good.

- Local run path works without Azure.
- Upload/retrieval/citation flow works.
- Organization admin concept is implemented.
- API/public link concept is implemented.
- Smoke coverage exists.

Production SaaS quality: not ready.

- Plaintext API keys.
- SQLite/default local storage.
- No migrations.
- In-memory rate limits.
- No billing/usage logs/team roles.
- No hosted deployment plan.
- Local hashing embeddings are not strong enough for high-quality semantic retrieval.

RAG quality: improved but not final.

- Hybrid retrieval, keyword/metadata/phrase reranking, citation metadata, page/line/paragraph fields, and optional reranker hooks are in place.
- Best-possible retrieval still needs real embeddings, robust reranking, OCR/table handling, score thresholds, and an evaluation set.

Frontend quality: functional MVP.

- Admin and public chat surfaces exist.
- Citation cards render.
- UI is usable but not polished SaaS.
- Upload progress, ingestion status, usage logs, and widget customization are still missing.

## Immediate Next Steps

1. API key hardening

- Store hashed API keys.
- Show regenerated keys only once.
- Add key prefix/fingerprint for admin display.
- Add created/last-used timestamps.

2. Retrieval confidence

- Add score thresholds.
- Return a no-answer response when all chunks are weak.
- Show confidence/debug scores only in admin/debug mode, not necessarily public chat.

3. Ingestion status

- Add upload progress and ingestion result state in admin UI.
- Show parser failures clearly.
- Add file metadata: uploaded_at, size, source_type, indexed_chunk_count.

4. Usage logging

- Track API/public/session chat calls per organization.
- Track approximate retrieved chunks and response mode.
- Do not log secrets or full document text.

5. Frontend polish

- Improve admin empty states and disabled states.
- Add document corpus table with source type and indexed status.
- Add clearer copy buttons and public link preview.
- Code-split landing/Three.js visuals.

## RAG Roadmap

Phase 1: current local baseline

- Local hashing embeddings.
- FAISS vector indexes.
- Hybrid semantic/keyword/metadata/phrase reranking.
- Citation metadata.
- Retrieval-only local answers.

Phase 2: reliable retrieval

- Add evaluation set before tuning.
- Add score thresholds/no-answer handling.
- Add production semantic embeddings.
- Add stable cross-encoder or hosted reranking.
- Add parent-child chunking or section expansion.
- Add query rewriting/expansion for acronyms and synonyms.

Phase 3: richer ingestion

- OCR for scanned PDFs.
- Better table extraction.
- Preserve headings/hierarchy more deeply.
- Add document-level metadata: author, created date, source URL, tags, department.
- Add manual metadata fields in admin UI.

Phase 4: answer quality

- Re-enable LLM generation through Azure/OpenAI/local provider when credentials/model exist.
- Force source-cited answers.
- Add citation validation so cited labels correspond to retrieved chunks.
- Add answer faithfulness checks for high-risk verticals.

## Platform Roadmap

Production backend:

- Postgres.
- Alembic/Flask-Migrate.
- Redis-backed rate limits.
- Background workers for ingestion.
- Object storage abstraction hardened for local/Azure/S3-compatible stores.
- Structured logs and metrics.
- Error reporting.

Security:

- Strong secret management.
- Hashed API keys.
- CSRF protection or token auth.
- Workspace/team roles.
- Audit logs.
- Per-org quotas.
- Domain allowlist and widget security review.

API/widget:

- Stable API versioning, for example `/v1/chat`.
- Widget script in addition to iframe.
- Theme controls for hosted chat/widget.
- Streaming responses when LLM generation is enabled.
- Usage dashboard.

Commercial:

- Organization plans.
- Document/storage/query quotas.
- Billing integration.
- Self-serve onboarding.
- Admin usage analytics.

## Best Vertical Options

1. Legal/contracts

Why it fits:

- High value for citation-backed answers.
- Users need exact clauses and source pages.
- Clear workflows: clause Q&A, obligations, renewal dates, risk flags.

Needed additions:

- Strong citations.
- PDF page deep links.
- Table/clause extraction.
- Confidence/no-answer behavior.
- Auditability.

2. HR/internal policy

Why it fits:

- Common pain: handbook/SOP/policy Q&A.
- Lower legal risk than contracts.
- Easy buyer story for small organizations.

Needed additions:

- Department tags.
- Effective date metadata.
- Public/internal access controls.
- Feedback buttons for wrong answers.

3. Sales enablement

Why it fits:

- Battlecards, proposals, decks, pricing sheets.
- API/widget embedding has a clear use case.
- Fast demo potential.

Needed additions:

- Freshness metadata.
- CRM or website widget integration.
- Source-type support for decks/spreadsheets later.

4. Compliance/audit

Why it fits:

- Evidence retrieval and citation-backed responses are valuable.
- Strong need for traceability.

Needed additions:

- Audit logs.
- Immutable source snapshots.
- Role-based access.
- Exportable evidence packs.

5. Education/course material

Why it fits:

- Clear document Q&A use case.
- Less enterprise complexity.

Needed additions:

- Course/workspace structure.
- Student-safe public links.
- Quiz/study modes.

## Recommended First Commercial MVP

Build for HR/internal policy or legal/contracts first.

Best low-friction option: HR/internal policy.

- Easier compliance burden.
- Simple corpus: handbook, policies, SOPs.
- Clear hosted chat use case.
- Admin can upload documents and share a link quickly.

Best high-value option: legal/contracts.

- Stronger willingness to pay.
- Requires better citations, page links, confidence thresholds, and security.

## Definition Of Done For Production Beta

A production beta should have:

- Hosted deployment with reproducible environment setup.
- Postgres migrations.
- Redis rate limits.
- Hashed API keys.
- Secure cookies/CSRF or token auth.
- Organization usage logs.
- Stable citations with page/line/paragraph metadata.
- Real semantic embeddings.
- Score thresholds/no-answer behavior.
- Admin ingestion status.
- Public/widget theme configuration.
- E2E tests for org signup, upload, admin config, API chat, public chat, and delete.
- Monitoring and error reporting.

## Work To Avoid For Now

Avoid these until the foundation is stronger:

- Building many vertical templates before one vertical works deeply.
- Adding billing before usage logging and key security exist.
- Tuning retrieval without an evaluation set.
- Adding many LLM providers before one generation path is reliable.
- Over-polishing the landing page while admin/public chat workflows remain MVP.

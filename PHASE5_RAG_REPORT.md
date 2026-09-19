# Phase 5: Local RAG Completion Report

Date: 2026-09-04

Status: **COMPLETE**, with the dependency advisory noted in the security section.

## Executive Summary

The existing Local AI Workbench now has an additive, browser-first local RAG capability. It reuses the existing PyMuPDF plus Tesseract `PageBlock` pipeline, chunks each page with provenance, embeds locally through Ollama, persists vectors in ChromaDB, filters retrieval by authenticated owner and collection, and streams grounded answers with trusted source metadata. General Chat, direct Document Analysis, Tkinter, authentication, RBAC, queueing, and existing SSE behavior remain available.

Post-implementation checks passed for the real local embedding model, Chroma persistence after reopen, indexing/deletion/re-indexing, duplicate handling, prompt-injection defense, cross-user isolation, the complete existing regression suite, and the browser-rendered controls.

## Before And After

Before:

~~~
PDF -> native extraction/OCR -> one document context -> local Ollama chat
~~~

After:

~~~
PDF -> existing native extraction/OCR -> PageBlock chunks
    -> local Ollama embeddings -> persistent ChromaDB + JSON metadata

Question -> local query embedding -> owner/collection-filtered retrieval
         -> bounded context -> local Ollama -> SSE answer + trusted sources
~~~

PostgreSQL was intentionally not introduced. ChromaDB is sufficient for this MVP and avoids an unnecessary SQL/ORM migration.

## Implementation

### Files Created

- `rag/__init__.py`
- `rag/config.py`
- `rag/models.py`
- `rag/chunker.py`
- `rag/embeddings.py`
- `rag/metadata.py`
- `rag/file_store.py`
- `rag/vector_store.py`
- `rag/prompts.py`
- `rag/service.py`
- `tests/server_test_support.py`
- `tests/test_rag.py`
- `PHASE5_RAG_REPORT.md`

### Files Modified For Phase 5

- `server/main.py`: RAG service, health/metrics, authenticated API endpoints, streaming Knowledge Chat, and user-deletion cleanup.
- `core/models.py`: `Knowledge Chat` mode and isolated knowledge history.
- `core/session_manager.py`: knowledge-session initialization, reset, and message routing.
- `static/index.html`: General/Knowledge mode controls and knowledge-base panel.
- `static/app.js`: collection/document management, upload/re-index/delete actions, RAG requests, SSE sources, and safe source rendering.
- `static/app.css`: responsive knowledge controls, document table, status badges, and source presentation.
- `requirements.txt`: pinned ChromaDB dependency.
- `README.md` and `SERVER_GUIDE.md`: setup, operation, API, security, lifecycle, and troubleshooting documentation.

The Tkinter desktop client was inspected and left unchanged for this phase because browser/server integration is the lower-risk path; its existing direct-document workflow remains covered by regression tests.

## Dependencies And Model

Added:

| Package | Version | Reason |
| :--- | :--- | :--- |
| `chromadb` | `1.5.9` | Persistent local vector storage and cosine similarity retrieval |

Existing dependencies were retained. No cloud AI SDK, hosted embedding service, PostgreSQL driver, ORM, or external vector service was added.

The selected embedding model is the configurable local Ollama model `nomic-embed-text:latest`. The existing chat model remains independently configurable as `LOCAL_AI_MODEL_NAME`, defaulting to `llama3.2:latest`.

The verified local embedding model returned 768-dimensional vectors.

## Data Model And Storage

Default storage:

~~~
data/rag/
  chroma/                     Persistent ChromaDB index
  metadata/rag.json           Collections and document lifecycle metadata
  documents/{document_id}.pdf Retained source PDFs addressed by opaque IDs
~~~

Logical records:

- Collection: ID, owner ID, name, creation/update timestamps.
- Document: ID, owner ID, collection ID, sanitized filename, SHA-256, page count, status, timestamps, extraction statistics, embedding model, chunk count, version, and bounded failure reason.
- Chunk: chunk/document/owner/collection IDs, filename, page, chunk index, extraction method, text, indexing version, and indexing timestamp.

Internal source paths are never returned by the API. The account store remains outside the repository under `%LOCALAPPDATA%\LocalAIWorkbench\users.json`.

## Configuration

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `LOCAL_AI_RAG_ENABLED` | `1` | Enable or disable Knowledge Chat |
| `LOCAL_AI_EMBED_MODEL` | `nomic-embed-text:latest` | Local Ollama embedding model |
| `LOCAL_AI_RAG_TOP_K` | `8` | Retrieved chunks, maximum `20` |
| `LOCAL_AI_RAG_CHUNK_SIZE` | `1200` | Target chunk size in characters |
| `LOCAL_AI_RAG_CHUNK_OVERLAP` | `180` | Overlap in characters |
| `LOCAL_AI_RAG_CONTEXT_LIMIT` | `12000` | Maximum retrieved context sent to the LLM |
| `LOCAL_AI_RAG_STORAGE_PATH` | `data/rag` | Persistent local RAG root |

## Processing And Retrieval

Indexing reuses `DocumentService.process_pdf`; there is no second OCR implementation. Chunks stay within page boundaries, prefer paragraph boundaries, hard-split oversized paragraphs, merge tiny trailing fragments when possible, and preserve native/OCR provenance.

The service computes a SHA-256 fingerprint. The same owner, collection, and file hash reuses the existing document ID and re-indexes it with the new filename/content metadata instead of creating duplicate vectors. Index states are `PENDING`, `INDEXING`, `INDEXED`, and `FAILED`. Failed indexing rolls back vectors and persists a bounded reason for retry or deletion.

Retrieval embeds the question locally, applies owner and optional owner-owned collection filters in ChromaDB, then performs a metadata ownership/status check before returning chunks. Context is built only from the authorized top-K chunks and is bounded by `LOCAL_AI_RAG_CONTEXT_LIMIT`.

The prompt explicitly treats retrieved PDF text as untrusted evidence. The model is told not to follow document instructions, invent facts, or invent filenames/pages. Sources are rendered from retrieval metadata, not generated by the model.

## API And UI

Authenticated endpoints:

- `GET/POST /api/rag/collections`
- `GET/POST /api/rag/documents`
- `GET /api/rag/documents/{document_id}`
- `POST /api/rag/documents/{document_id}/reindex`
- `DELETE /api/rag/documents/{document_id}`
- `POST /api/rag/query`
- `POST /api/rag/chat`

The browser UI adds General Chat and Knowledge Chat modes. Knowledge Chat supports collection creation/selection, PDF indexing, status and document statistics, re-index, delete, streamed answers, and filename/page/native-or-OCR source display. DOM rendering uses safe text nodes rather than server-provided HTML.

## Security And RBAC

- All RAG routes use the existing authenticated session dependency.
- Collections and documents are owner-private. Admins do not receive an implicit cross-user bypass.
- Direct IDs, guessed filenames, collection IDs, and semantic search are all owner-filtered.
- Account removal deletes that user’s vectors, metadata, and retained RAG source PDFs.
- PDF validation, filename sanitization, size/page limits, containment checks, and source storage by document ID are preserved.
- No credentials are stored in the RAG directory.
- Chroma telemetry is disabled and only embedded `PersistentClient` is used; no Chroma HTTP server or Chroma port is exposed by this application.
- The app’s CSP, same-origin policy, HttpOnly session cookie, request limits, queue, and SSE controls remain active.

### Dependency Advisory

The 2026-09-04 `pip-audit --local` scan reports four ChromaDB advisories (`PYSEC-2026-311`, `CVE-2026-45830`, `CVE-2026-45833`, and `CVE-2026-45831`) with no published fix version. Their reported attack surfaces concern Chroma’s exposed multi-tenant/server authorization and collection update endpoints. This project does not expose those endpoints: Chroma is opened only as an in-process persistent client, and the application API exposes only bounded owner-scoped operations. The finding remains recorded for future upgrade monitoring; an unpatched upstream version is not silently claimed as vulnerability-free.

## Tests And Exact Results

### Dedicated RAG Tests

`tests/test_rag.py`: **PASS**

Verified:

- page-aware chunking and native/OCR provenance
- local index and semantic retrieval
- source filename/page metadata
- duplicate re-index policy
- re-index and delete lifecycle
- failure status and failure reason
- prompt-injection defense
- user A/user B direct-ID, filename, collection, and semantic isolation
- persistence after a fresh `RagService` reopen
- Knowledge Chat SSE sources and streamed answer

### Full Regression Suite

All 13 scripts passed with exit code `0`:

~~~
test_document_workflow.py
test_app_state.py
test_demo_runs.py
test_concurrency_queue.py
test_api_server.py
test_security_file_handling.py
test_security_regressions.py
test_rbac_auth.py
test_admin_profile.py
test_session_isolation.py
test_lan_server_e2e.py
test_model_document_qa.py
test_rag.py
~~~

The tests included three complete demo-equivalent runs, three LAN multi-client E2E cycles, real `llama3.2:latest` document QA, and all security/RBAC/session/file checks.

### Static And Environment Checks

- Python `compileall` for `rag`, `server`, `core`, `document`, and `app.py`: **PASS**
- `node --check static/app.js`: **PASS**
- `pip check`: **PASS**, no broken requirements
- Real `nomic-embed-text:latest` local index/retrieve/reopen check: **PASS**
- Browser DOM/render check at `762x698`: **PASS**; message input visible/readable, Send label visible, Knowledge Chat control present
- `pip-audit --local`: **4 ChromaDB advisories**, no fix versions; mitigation documented above

## Performance Measurement

Measured locally on `tests/data/synthetic_inspection_report.pdf` using the real Ollama embedding model and a temporary persistent Chroma store:

| Measurement | Result |
| :--- | :--- |
| Pages indexed | 2 |
| Chunks indexed | 2 |
| Native/OCR pages | 2 / 0 |
| Embedding dimension | 768 |
| Index end-to-end time | 28.415 seconds |
| Retrieval time | 1.483 seconds |
| Top source | `inspection_report.pdf`, page 1 |
| Reopened-store results | 2 |

The first index measurement includes local Ollama model inference/warm-up. Timing will vary with CPU/GPU, document size, and model state. Retrieval is serialized through the existing request queue for LLM generation; Chroma operations are lock-protected for concurrent clients.

## Setup, Run, And Troubleshooting

From the project root:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull llama3.2
ollama pull nomic-embed-text
.\.venv\Scripts\python.exe run_server.py
~~~

Open `http://localhost:8000`, sign in, select Knowledge Chat, create/select a collection, index a PDF, wait for `INDEXED`, and ask a question. Run `app.py` for the existing Tkinter desktop client. For a missing embedding model, run `ollama pull nomic-embed-text` or the command named by `/health`. Set `LOCAL_AI_RAG_ENABLED=0` to disable RAG while retaining General Chat and direct Document Analysis.

## Acceptance Checklist

- [x] Existing OCR/PDF validation and direct document chat preserved
- [x] Configurable local embedding model and no external AI dependency
- [x] Persistent local vector store and source storage
- [x] Chunking, bounded context, page metadata, and OCR/native provenance
- [x] Collections, index/delete/re-index, duplicate policy, and failure states
- [x] Semantic retrieval with configurable top-K
- [x] Owner-scoped RBAC and cross-user leakage tests
- [x] Prompt-injection defense and trusted source citations
- [x] Knowledge-base browser UI and SSE answer streaming
- [x] General chat, authentication, RBAC, admin, sessions, file security, queue, LAN, SSE, and desktop regression coverage
- [x] Persistence, performance measurements, documentation, and run instructions
- [x] Final dependency audit performed; Chroma advisory is explicitly mitigated and tracked

## Next Recommendation

Do not implement it in Phase 5. The next architectural phase should be **Phase 6: Capability-Based Model Routing**, followed by the later bounded agent, sandbox, approval, auditability, and zero-egress phases described in the project plan.

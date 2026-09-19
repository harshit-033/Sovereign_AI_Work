# Local AI Workbench Server Guide

This guide covers the multi-client FastAPI server, browser authentication, RBAC, local inference, OCR, local RAG, and secure LAN operation.

## Phase 6 Capability Routing

The server now routes authenticated requests through `routing/` before invoking the existing handlers. The capability describes the task; the configured model is selected afterward:

```text
User Request
    |
Authentication + existing authorization
    |
CapabilityRouter
    +--> GENERAL_CHAT --------> existing AIService history
    +--> DOCUMENT_ANALYSIS ---> existing session PDF/OCR context + AIService
    +--> KNOWLEDGE_RAG --------> existing owner-filtered RagService + AIService
```

The registry contains only the three capabilities present in this project and is extensible for later local capabilities. Handler bindings are metadata for the existing General Chat, DocumentService, and RagService paths; no second OCR or RAG implementation exists.

The browser supports explicit `General Chat`, `Document Analysis` (after attaching/selecting a PDF), and `Knowledge Chat`, plus `Auto`. Explicit mode wins. In Auto, deterministic routing uses strong cross-document intent first, then document wording when a session document is selected, then a conservative selected-document ambiguity rule, and finally General Chat. A request such as `Hello` routes General; `What is the equipment ID in this report?` routes Document Analysis when a PDF is selected; `Search my maintenance reports for Pump A17` routes Knowledge RAG. If a strong RAG request is made while RAG is disabled, the request fails clearly rather than searching elsewhere.

`POST /api/route` is an authenticated, retrieval-free explanation endpoint. Streamed chat emits a `routing` SSE event before status/chunks. The event contains only capability, confidence, safe reason, handler name, configured model name, and routing latency. Logs contain session/user IDs and routing metadata, never passwords, tokens, document contents, retrieved text, or complete prompts.

## Architecture

The Windows host runs the complete processing pipeline:

- FastAPI serves the same-origin browser application and API.
- Ollama runs `llama3.2:latest` locally and streams generated text through SSE.
- PyMuPDF extracts digital text; Tesseract handles scanned pages locally.
- The RAG layer chunks those same `PageBlock` records, embeds them through local Ollama, and persists vectors in ChromaDB.
- An inference queue protects host capacity when several clients submit work.
- Each login receives an isolated in-memory session, document list, chat history, and upload directory.
- Accounts are stored at `%LOCALAPPDATA%\LocalAIWorkbench\users.json`, outside the repository.
- Knowledge-base source files and metadata persist below `data/rag` by default and are filtered by owner before retrieval.

## First Start

Install dependencies and start the server from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_server.py
```

On a fresh installation the terminal displays a generated initial admin password once. There are no demo users or reusable default passwords. To choose the first credentials, set these variables before the first run:

```powershell
$env:LOCAL_AI_BOOTSTRAP_ADMIN_USERNAME = "admin"
$env:LOCAL_AI_BOOTSTRAP_ADMIN_PASSWORD = "Use-A-Long-Unique-Password"
.\.venv\Scripts\python.exe run_server.py
```

Open `http://localhost:8000` on the host. The launcher prints the detected private LAN IPv4 address for other computers on the same network. `127.0.0.1` is loopback and must not be used from a second PC; use the host's `ipconfig` IPv4 address instead.

If detection falls back to `127.0.0.1`, set the active adapter address explicitly before starting:

```powershell
$env:LOCAL_AI_LAN_IP = "192.168.1.23"
.\.venv\Scripts\python.exe run_server.py
```

The server binds to `0.0.0.0` by default. If the correct LAN URL still does not open remotely, allow TCP port 8000 through Windows Firewall for the Private profile from an Administrator PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Local AI Workbench 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```

## Client Use

1. Connect the client to the same trusted LAN as the host.
2. Open the LAN URL printed by `run_server.py`.
3. Sign in with an account created by the administrator.
4. Use General Chat, attach a PDF for Document Analysis, select Knowledge Chat for cross-document search, or choose Auto for deterministic capability routing.
5. In Knowledge Chat, create a collection, select Index PDF, and wait for `INDEXED` status.
6. Ask a question; the answer streams and trusted source filename/page/provenance entries appear below it.
7. Admin users can open Admin Dashboard to create/remove users and change their own credentials.
8. Sign out when finished. Logout removes that session's temporary direct-analysis PDFs; persistent knowledge documents remain until explicitly deleted or their owner is removed.

## Roles

| Capability | Admin | User | Unauthenticated |
| :--- | :---: | :---: | :---: |
| General chat and PDF analysis | Yes | Yes | No |
| View own session/documents | Yes | Yes | No |
| Admin dashboard and user list | Yes | No | No |
| Create/remove users | Yes | No | No |
| Change admin username/password | Yes | No | No |
| Access another session's document | No | No | No |
| Knowledge Chat own collections | Yes | Yes | No |
| Knowledge documents owned by another user | No | No | No |

An admin account has one active session at a time. Normal accounts may use multiple concurrent sessions. Removing a user revokes their active tokens, sessions, and temporary files.

## Security Model

- Passwords use salted scrypt. Legacy PBKDF2 hashes are accepted only for migration and upgraded after the next successful login.
- Tokens are random, memory-only, expire after eight hours, and are never persisted in `users.json`.
- The browser uses an HttpOnly, SameSite=Strict session cookie. Tokens are not stored in browser storage and are not accepted in query strings.
- Failed login attempts are throttled per client/username pair.
- Cross-origin access is disabled. Responses set CSP, anti-framing, MIME-sniffing, referrer, and permissions headers.
- Chat input, output, history, generated output, uploads, PDF pages, OCR rasterization, and model context are bounded.
- Filenames are sanitized, PDF signatures are checked, destination paths are contained, and malformed upload files are removed.
- Document text is treated as untrusted evidence; instructions embedded in PDFs are not followed as system instructions.
- RAG retrieval applies owner and collection filters in ChromaDB before the prompt is built. The prompt-injection rule is defense-in-depth, not authorization.
- RAG source metadata is returned from retrieved chunk metadata; the model does not author filenames or page citations.

Browser rendering uses `textContent`/safe DOM nodes for server-provided values. The admin table does not inject usernames or errors as HTML.

## HTTPS For LAN Use

HTTP exposes credentials and content to devices that can observe the network. Use direct TLS or a trusted reverse proxy outside a fully trusted private LAN.

Direct TLS configuration:

```powershell
$env:LOCAL_AI_TLS_CERT_FILE = "C:\certs\server.crt"
$env:LOCAL_AI_TLS_KEY_FILE = "C:\certs\server.key"
$env:LOCAL_AI_COOKIE_SECURE = "1"
.\.venv\Scripts\python.exe run_server.py
```

The launcher refuses a partial TLS configuration. Keep certificate private keys outside the repository.

## Configuration

| Environment variable | Description |
| :--- | :--- |
| `LOCAL_AI_MODEL_NAME` | Ollama model; default `llama3.2:latest` |
| `LOCAL_AI_ROUTING_ENABLED` | Enable capability routing; default `1` |
| `LOCAL_AI_AUTO_ROUTING_ENABLED` | Enable Auto mode; default `1` |
| `LOCAL_AI_GENERAL_MODEL` | Model for General Chat; falls back to `LOCAL_AI_MODEL_NAME` |
| `LOCAL_AI_DOCUMENT_MODEL` | Model for Document Analysis; falls back to `LOCAL_AI_MODEL_NAME` |
| `LOCAL_AI_RAG_MODEL` | Model for Knowledge RAG; falls back to `LOCAL_AI_MODEL_NAME` |
| `LOCAL_AI_SERVER_HOST` | Bind host; default `0.0.0.0` |
| `LOCAL_AI_SERVER_PORT` | TCP port; default `8000` |
| `LOCAL_AI_LAN_IP` | Explicit private LAN IPv4 override when auto-detection is unavailable |
| `LOCAL_AI_ENABLE_API_DOCS=1` | Enables `/docs` and `/openapi.json` |
| `LOCAL_AI_USER_STORE_PATH` | Overrides the local account file |
| `LOCAL_AI_UPLOAD_DIR` | Overrides temporary upload storage |
| `LOCAL_AI_TLS_CERT_FILE` | TLS certificate path |
| `LOCAL_AI_TLS_KEY_FILE` | TLS private key path |
| `LOCAL_AI_COOKIE_SECURE=1` | Forces the Secure cookie flag |
| `LOCAL_AI_RAG_ENABLED` | Enable/disable the persistent knowledge base; default `1` |
| `LOCAL_AI_EMBED_MODEL` | Local Ollama embedding model; default `nomic-embed-text:latest` |
| `LOCAL_AI_RAG_TOP_K` | Retrieved chunk limit; default `8`, maximum `20` |
| `LOCAL_AI_RAG_CHUNK_SIZE` | Chunk target characters; default `1200` |
| `LOCAL_AI_RAG_CHUNK_OVERLAP` | Chunk overlap characters; default `180` |
| `LOCAL_AI_RAG_CONTEXT_LIMIT` | Maximum retrieved prompt context; default `12000` |
| `LOCAL_AI_RAG_STORAGE_PATH` | RAG root; default project `data/rag` |
| `LOCAL_AI_AGENT_MODEL` | Model name advertised for Agent Task; default `llama3.2:latest` |
| `LOCAL_AI_AGENT_ENABLED` | Enable Agent Task; default `1` |
| `LOCAL_AI_AGENT_MAX_STEPS` | Maximum planned steps; default `8` |
| `LOCAL_AI_AGENT_MAX_TOOL_CALLS` | Maximum tool calls; default `12` |
| `LOCAL_AI_AGENT_MAX_EXECUTION_SECONDS` | Maximum runtime; default `120` |
| `LOCAL_AI_AGENT_MAX_OUTPUT_CHARS` | Maximum report content; default `32000` |
| `LOCAL_AI_AGENT_MAX_FILE_BYTES` | Maximum generated file size; default `2000000` |
| `LOCAL_AI_AGENT_OUTPUT_DIR` | Agent output root; default project `data/agent_outputs` |

## Agent Task

Agent Task adds deterministic local workflows on top of the Phase 6 capability router. The browser has an explicit `Agent Task` mode, and Auto selects it only for clear multi-operation requests. Normal conversational, selected-document, and knowledge-base questions keep their existing handlers.

The registry contains only these tools: `search_knowledge`, `list_documents`, `get_document_metadata`, `retrieve_document_information`, `calculate`, `generate_txt`, and `generate_pdf`. No shell, command prompt, arbitrary Python, `eval`, `exec`, subprocess, network, browser, installer, or unrestricted filesystem tool is registered. Every call passes schema validation and the session/user policy boundary before execution. The planner is deterministic and bounded by `LOCAL_AI_AGENT_MAX_STEPS`; execution is bounded by tool-call count and runtime.

Agent progress is available over SSE as `agent_started`, `plan_created`, `tool_started`, `tool_completed`, `verification_completed`, `approval_required`, and `final_result`. TXT output is read back as UTF-8, PDF output is checked for a `%PDF-` signature, and downloads resolve through an opaque output ID scoped to the authenticated session. Output files live under one directory per session and are cleaned on clear/logout.

Approval and audit API:

```text
GET  /api/agent/approvals
POST /api/agent/approvals/{approval_id}  body: {"approved": true|false}
GET  /api/agent/audit
GET  /api/agent/outputs/{output_id}
```

Approval requests include only safe argument summaries. Audit records contain task, tool, policy, verification, status, and generated-file metadata; they do not contain prompts, passwords, tokens, private document text, or report content.

### Report generation quality

Retrieved evidence passes through `ReportComposer` before `generate_pdf` or `generate_txt`. The composer produces a human-readable title, overview, key findings, and sources, and uses an insufficient-evidence statement when authorized evidence is unavailable. Natural-language requests such as `Summarize my reports and create a PDF`, `Create a TXT summary`, and `Summarize this document and save it as PDF` are supported; internal tool names are not required.

PDF output uses explicit line wrapping and page placement to avoid blank leading/trailing pages, supports paragraphs, headings, bullets, numbered lists, and multi-page reports, and adds page numbers. Verification extracts the generated text and checks report markers, page count, non-empty first-page content, and the PDF signature. TXT output is read back as UTF-8 and checked for the same report markers before it is returned.

## API Summary

| Method | Endpoint | Access |
| :--- | :--- | :--- |
| `GET` | `/health` | Public, minimal readiness only |
| `GET` | `/api/metrics` | Authenticated |
| `POST` | `/api/auth/login` | Public, rate-limited |
| `POST` | `/api/auth/logout` | Authenticated |
| `GET` | `/api/auth/me` | Authenticated |
| `GET/POST` | `/api/admin/users` | Admin |
| `DELETE` | `/api/admin/users/{id}` | Admin |
| `PATCH` | `/api/admin/me` | Admin |
| `POST` | `/api/admin/me/change-password` | Admin |
| `GET` | `/api/session` | Authenticated |
| `POST` | `/api/chat` | Authenticated, SSE or JSON |
| `POST` | `/api/route` | Authenticated, safe routing explanation |
| `POST/GET` | `/api/documents` | Authenticated |
| `POST` | `/api/documents/{id}/select` | Owning session |
| `POST` | `/api/documents/{id}/chat` | Owning session, SSE or JSON |
| `POST` | `/api/chat/clear` | Authenticated |
| `GET/POST` | `/api/rag/collections` | Authenticated, owner-scoped |
| `GET/POST` | `/api/rag/documents` | Authenticated, owner-scoped; POST indexes a PDF |
| `GET` | `/api/rag/documents/{id}` | Owning user only |
| `POST` | `/api/rag/documents/{id}/reindex` | Owning user only |
| `DELETE` | `/api/rag/documents/{id}` | Owning user only |
| `POST` | `/api/rag/query` | Authenticated, retrieval/source inspection |
| `POST` | `/api/rag/chat` | Authenticated, SSE or JSON Knowledge Chat |
| `GET` | `/api/agent/approvals` | Authenticated, current session/user only |
| `POST` | `/api/agent/approvals/{approval_id}` | Authenticated, owning session/user only |
| `GET` | `/api/agent/audit` | Authenticated, current session/user only |
| `GET` | `/api/agent/outputs/{output_id}` | Authenticated, owning session only |

API documentation is disabled unless `LOCAL_AI_ENABLE_API_DOCS=1` is set before startup.

## Limits And Cleanup

| Resource | Limit |
| :--- | :--- |
| Upload | 25 MB |
| PDF pages | 80 |
| Direct document context | 14,000 characters |
| Chat request | 8,000 characters |
| Generated stream | 64,000 characters |
| Stored message | 16,000 characters |
| Model chat history context | 48,000 characters |
| OCR raster | 20 million pixels, dynamically reduced DPI |
| RAG chunk target | 1,200 characters with 180-character overlap |
| RAG context | 12,000 characters |
| RAG top-K | 8 by default, maximum 20 |

Clear Chat deletes that session's direct-analysis documents and resets the chat modes. It does not delete persistent knowledge-base documents. Logout revokes the token and deletes temporary session files. Failed and corrupted direct uploads are removed immediately; failed RAG entries remain as `FAILED` with a bounded reason so they can be re-indexed or deleted.

## RAG Storage And Lifecycle

The default RAG root is:

```text
data/rag/
  chroma/                 Persistent ChromaDB vector index
  metadata/rag.json       Collections and document lifecycle metadata
  documents/{document_id}.pdf  ID-based retained source PDFs
```

ChromaDB uses its own local storage internally; the application does not use PostgreSQL or an ORM. Collection access is owner-private. A duplicate is identified by SHA-256 within the same owner and collection, then re-indexes the existing document ID. Index failures are recorded as `FAILED` and partial vectors are rolled back.

Install the embedding model once before indexing:

```powershell
ollama pull nomic-embed-text
```

If the model is missing, the health endpoint and Knowledge Chat report the configured model and the exact pull command. Set `LOCAL_AI_RAG_ENABLED=0` to disable RAG without affecting General Chat or direct Document Analysis.

## RAG Security And Citations

Every chunk stores document ID, chunk ID, owner ID, collection ID, filename, page number, extraction method, chunk index, and indexing version. Retrieval filters by the authenticated owner and selected owner-owned collection before any chunk enters the LLM context. Admins do not receive an implicit cross-user bypass.

Retrieved evidence is placed in a dedicated untrusted-evidence prompt. The UI source list is built from retrieval metadata, so the model cannot create arbitrary page or filename citations. Source PDFs are kept under document IDs and are not exposed through a raw filesystem path or download endpoint.

## Verification

Run the full command block in `README.md`. Important dedicated checks include:

```powershell
.\.venv\Scripts\python.exe .\tests\test_security_regressions.py
.\.venv\Scripts\python.exe .\tests\test_session_isolation.py
.\.venv\Scripts\python.exe .\tests\test_lan_server_e2e.py
.\.venv\Scripts\python.exe .\tests\test_model_document_qa.py
.\.venv\Scripts\python.exe .\tests\test_rag.py
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
```

The server test harness uses temporary account/upload directories. It does not read or modify production accounts.

## Routing Security And Limits

Routing is not an authorization boundary. The authenticated session remains authoritative: direct document requests still verify session ownership, and RAG still applies the existing owner and collection filters inside `RagService` before prompt construction. Auto does not accept an arbitrary document ID or private document contents from the browser. Its context is request/session-specific and has no global current-capability state. A missing capability, disabled router, unavailable RAG dependency, invalid mode, or missing selected document returns an explicit error.

Routing latency is measured separately in every `RoutingDecision.routing_latency_ms`; model generation, RAG retrieval, and document extraction retain their own timings. The deterministic classifier is intentionally lightweight and does not make an LLM call.

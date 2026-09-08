# SIH Local AI Workbench

An offline Windows AI workbench for local LLM chat, digital PDF analysis, OCR of scanned PDFs, and local retrieval-augmented generation (RAG). It includes a Tkinter desktop client and a FastAPI web server for multiple clients on a trusted LAN.

All inference, PDF extraction, OCR, account storage, and uploaded files stay on the host machine. The application does not require a cloud AI API.

## Current Status

- Ollama chat with real token-by-token streaming
- Persistent local ChromaDB knowledge base with Ollama embeddings
- Knowledge Chat across multiple authorized indexed documents with trusted source/page metadata
- Capability-based routing with explicit modes and deterministic Auto mode
- Capability-specific model configuration while retaining `llama3.2:latest` defaults
- Bounded offline Agent Task workflows with verified TXT/PDF outputs
- Structured report composition with natural-language PDF/TXT generation
- Native PDF extraction with page-aware Tesseract OCR fallback
- Mixed digital/scanned PDF support and bounded document context
- Responsive browser UI and standalone Tkinter UI
- Admin/user RBAC with isolated sessions and documents
- HttpOnly browser sessions, login throttling, security headers, and strict upload validation
- Scrypt password hashing with transparent migration of legacy PBKDF2 hashes
- Single active admin session and multiple concurrent normal-user sessions
- Deterministic, OCR, live-model, API, RBAC, isolation, and adversarial security tests

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- [Ollama](https://ollama.com/) with `llama3.2:latest`
- Ollama embedding model `nomic-embed-text:latest` for Knowledge Chat
- Tesseract OCR, normally installed at `C:\Program Files\Tesseract-OCR`

Install the local model once:

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
```

## Clone And Install

```powershell
git clone https://github.com/harshit-033/SIH_PROJECT_1.git
cd SIH_PROJECT_1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Dependencies are pinned in `requirements.txt`. The verified environment currently uses Python 3.14.3, but the application code supports Python 3.10+.

## Start The Web App

```powershell
.\.venv\Scripts\python.exe run_server.py
```

You can also double-click `run_server.bat`. Open `http://localhost:8000` on the host, or use the LAN URL printed in the terminal from a client on the same trusted network.

For another PC, use the host computer's private IPv4 address, not `127.0.0.1`. Run `ipconfig` on the host and use the `IPv4 Address` for the active Wi-Fi/Ethernet adapter, for example `http://192.168.1.23:8000`. If automatic detection prints `127.0.0.1`, set the address before starting:

```powershell
$env:SIH_LAN_IP = "192.168.1.23"
.\.venv\Scripts\python.exe run_server.py
```

If the address is correct but another PC still cannot connect, allow TCP port 8000 through Windows Firewall on the host for the Private network profile from an Administrator PowerShell:

```powershell
New-NetFirewallRule -DisplayName "SIH Local AI Workbench 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```

There are no hardcoded default passwords or demo accounts. On a completely fresh install, the terminal prints a one-time generated admin password. To choose the initial credentials before the first start:

```powershell
$env:SIH_BOOTSTRAP_ADMIN_USERNAME = "admin"
$env:SIH_BOOTSTRAP_ADMIN_PASSWORD = "Use-A-Long-Unique-Password"
.\.venv\Scripts\python.exe run_server.py
```

Change the generated password immediately from `Admin Dashboard > My Account`. The account database is stored outside Git at `%LOCALAPPDATA%\SIHLocalAI\users.json`.

## Start The Desktop App

```powershell
.\.venv\Scripts\python.exe app.py
```

You can also double-click `run_chat_app.bat`. Type a question and press Enter to send. Use Shift+Enter for a new line. The answer appears as the local model generates it. Attach a PDF to switch into Document Analysis mode.

Select `Knowledge Chat` to open the local knowledge base. Create or choose a collection, select `Index PDF`, and wait for the document status to become `INDEXED`. Knowledge Chat retrieves only your own authorized chunks and displays source filenames, pages, and native/OCR provenance beneath the answer.

The browser also provides `Auto`. Auto routes each request to General Chat, Document Analysis, or Knowledge RAG using the request wording and only session-safe metadata. A selected PDF is used for document-specific wording; cross-document wording such as “search my reports” uses owner-scoped Knowledge RAG. Every streamed answer shows the selected capability. Explicit modes remain available for predictable behavior.

## Security Configuration

The browser server is same-origin only. API documentation is disabled by default, tokens are not accepted in URLs, browser authentication uses an HttpOnly SameSite cookie, and uploaded files are limited to 25 MB and 80 pages.

Plain HTTP is suitable only for localhost or a trusted private LAN. To enable HTTPS, provide both certificate paths:

```powershell
$env:SIH_TLS_CERT_FILE = "C:\certs\server.crt"
$env:SIH_TLS_KEY_FILE = "C:\certs\server.key"
.\.venv\Scripts\python.exe run_server.py
```

Optional configuration:

| Variable | Purpose | Default |
| :--- | :--- | :--- |
| `SIH_MODEL_NAME` | Ollama model name | `llama3.2:latest` |
| `SIH_ROUTING_ENABLED` | Enable the capability router | `1` |
| `SIH_AUTO_ROUTING_ENABLED` | Enable the browser `Auto` mode | `1` |
| `SIH_GENERAL_MODEL` | Model used by `GENERAL_CHAT` | `SIH_MODEL_NAME` fallback |
| `SIH_DOCUMENT_MODEL` | Model used by `DOCUMENT_ANALYSIS` | `SIH_MODEL_NAME` fallback |
| `SIH_RAG_MODEL` | Model used by `KNOWLEDGE_RAG` | `SIH_MODEL_NAME` fallback |
| `SIH_SERVER_HOST` | Bind address | `0.0.0.0` |
| `SIH_SERVER_PORT` | Server port | `8000` |
| `SIH_LAN_IP` | Override detected private LAN IPv4 address | Auto-detected |
| `SIH_ENABLE_API_DOCS` | Set to `1` to expose `/docs` | Disabled |
| `SIH_USER_STORE_PATH` | Override account database path | `%LOCALAPPDATA%\SIHLocalAI\users.json` |
| `SIH_UPLOAD_DIR` | Override temporary upload directory | Project `uploads` directory |
| `SIH_COOKIE_SECURE` | Set to `1` when HTTPS terminates upstream | Auto-enabled for direct HTTPS |
| `SIH_RAG_ENABLED` | Enable Knowledge Chat and local indexing | `1` |
| `SIH_EMBED_MODEL` | Ollama embedding model | `nomic-embed-text:latest` |
| `SIH_RAG_TOP_K` | Maximum retrieved chunks | `8` |
| `SIH_RAG_CHUNK_SIZE` | Chunk target size in characters | `1200` |
| `SIH_RAG_CHUNK_OVERLAP` | Chunk overlap in characters | `180` |
| `SIH_RAG_CONTEXT_LIMIT` | Maximum retrieved prompt context | `12000` |
| `SIH_RAG_STORAGE_PATH` | Persistent RAG root | Project `data/rag` directory |
| `SIH_AGENT_MODEL` | Model name advertised for Agent Task routing | `llama3.2:latest` |
| `SIH_AGENT_ENABLED` | Enable Agent Task routing and execution | `1` |
| `SIH_AGENT_MAX_STEPS` | Maximum planned agent steps | `8` |
| `SIH_AGENT_MAX_TOOL_CALLS` | Maximum tool calls per task | `12` |
| `SIH_AGENT_MAX_EXECUTION_SECONDS` | Maximum agent runtime | `120` |
| `SIH_AGENT_MAX_OUTPUT_CHARS` | Maximum generated report content | `32000` |
| `SIH_AGENT_MAX_FILE_BYTES` | Maximum generated file size | `2000000` |
| `SIH_AGENT_OUTPUT_DIR` | Agent output root | Project `data/agent_outputs` directory |

## Run Tests

Generate the deterministic PDF fixtures first:

```powershell
.\.venv\Scripts\python.exe .\tests\create_synthetic_pdfs.py
```

Run the full suite:

```powershell
$tests = @(
  "test_document_workflow.py", "test_app_state.py", "test_demo_runs.py",
  "test_concurrency_queue.py", "test_api_server.py",
  "test_security_file_handling.py", "test_security_regressions.py",
  "test_rbac_auth.py", "test_admin_profile.py", "test_session_isolation.py",
  "test_lan_server_e2e.py", "test_model_document_qa.py", "test_rag.py",
  "test_routing.py", "test_agent.py"
)
foreach ($test in $tests) {
  .\.venv\Scripts\python.exe ".\tests\$test"
  if ($LASTEXITCODE -ne 0) { throw "$test failed" }
}
```

`test_model_document_qa.py` uses the real local Ollama model. `test_agent.py` covers the allowlist, planner, policy, approval, verification, output, isolation, audit, API, and SSE lifecycle. Server tests use isolated temporary account, upload, RAG, and agent-output directories and never modify production accounts.

Audit installed Python packages:

```powershell
.\.venv\Scripts\python.exe -m pip install pip-audit
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
```

## Project Layout

```text
app.py                       Tkinter desktop application
core/                        Authentication, sessions, queue, files, AI services
document/                    PDF extraction, OCR, context, and prompt handling
rag/                         Chunking, local embeddings, ChromaDB, metadata, and retrieval
routing/                     Capability registry, classifier, router, config, and handlers
agent/                       Bounded planner, allowlist, policy, executor, verifier, approvals, audit, outputs
server/main.py               FastAPI routes and streaming transport
static/                      Responsive browser application
tests/                       Functional, OCR, model, isolation, and security checks
run_server.py                LAN/HTTPS server launcher
SERVER_GUIDE.md              Server operation and security reference
DOCUMENT_WORKFLOW_CHECKLIST.md
```

## Operational Notes

- Uploaded PDFs are temporary and are deleted when the session is cleared or logged out.
- Knowledge-base source PDFs, vectors, and metadata persist under `data/rag` by default. They are private to their owning user; deleting the user removes their indexed documents and source files.
- The duplicate policy is deterministic: the same owner, collection, and SHA-256 file hash updates and re-indexes the existing document ID.
- Knowledge collections are owner-private in Phase 5. Admin users do not implicitly see other users' private documents.
- The server serializes local inference by default to protect host CPU/GPU capacity.
- Normal users may have multiple sessions; an admin account is limited to one active session.
- Use HTTPS before sending credentials over an untrusted network.
- Phase 6 routing is browser/server-first. The Tkinter client remains on its existing General Chat and direct Document Analysis paths; it is not required to use Auto.
- Phase 7 Agent Task is browser/server-first. The Tkinter client keeps its existing stable paths; the Agent Task browser UI and API are the supported agent surface.

## Agent Task

Agent Task is an offline, deterministic, bounded workflow capability. It is available as an explicit browser mode and Auto can select it for requests that clearly require multiple local operations, such as calculating a value and saving a TXT report or searching the private knowledge base and generating a PDF summary. Ordinary questions continue to use General Chat, Document Analysis, or Knowledge RAG.

The agent is allowlist-only. Its seven registered tools are `search_knowledge`, `list_documents`, `get_document_metadata`, `retrieve_document_information`, `calculate`, `generate_txt`, and `generate_pdf`. It cannot execute shell commands, arbitrary Python, subprocesses, network requests, browser actions, package installation, or unrestricted filesystem operations. Arithmetic uses a restricted AST visitor and generated files are written only beneath `data/agent_outputs/<session_id>` (or `SIH_AGENT_OUTPUT_DIR`).

Each task emits `agent_started`, `plan_created`, `tool_started`, `tool_completed`, `verification_completed`, `approval_required`, and `final_result` progress events. Generated TXT files are read back and PDFs are checked for a PDF signature before download. Approval, audit, and output endpoints are authenticated and session/user scoped:

```text
GET  /api/agent/approvals
POST /api/agent/approvals/{approval_id}
GET  /api/agent/audit
GET  /api/agent/outputs/{output_id}
```

Agent audit records contain task/tool/status metadata only. Prompts, passwords, tokens, private document text, and tool payload content are not written to the audit log. Agent outputs and audit records are cleared with the owning session.

Report requests are composed before generation, so retrieved evidence is not dumped directly into a file. Requests such as `Summarize this document and save it as PDF`, `create a text summary`, and the common `sumarize and generate a PDF` variation are supported. Reports include a title, overview, key findings, and sources when evidence is available. PDFs use wrapped text, readable spacing, page numbers, and verified page/content checks; insufficient evidence is stated rather than fabricated.

## Capability Routing

The router sits after authentication and before the existing handlers:

```text
User request -> authentication -> capability router -> existing handler -> local Ollama
                                      |                  | General Chat
                                      |                  | Document Analysis + OCR context
                                      |                  | Knowledge RAG + owner-filtered ChromaDB
```

Explicit mode is authoritative. Auto uses this deterministic precedence: strong cross-document intent, selected-document wording, selected-document ambiguity, then General Chat fallback. The classifier receives user/session identifiers, selected mode, selected document ID, collection ID, availability, and the message; it never receives private document text or retrieved chunks. `POST /api/route` returns a safe capability explanation without performing retrieval.

Capability and model are separate. The default mapping is `GENERAL_CHAT`, `DOCUMENT_ANALYSIS`, and `KNOWLEDGE_RAG` to `llama3.2:latest`; set the three capability variables independently when specialized local models are available. If `SIH_MODEL_NAME` is set, it is the fallback for all three unset capability variables. No cloud model or automatic model substitution is used.

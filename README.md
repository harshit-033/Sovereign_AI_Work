# AI Workbench

Local AI Workbench is a Windows application for chatting with a local large language model, analyzing PDF files, extracting text from scanned documents with OCR, and searching a private local knowledge base.

It includes:

- A browser-based application for one or more users on a trusted LAN.
- A standalone Tkinter desktop application for local chat and document analysis.
- Streaming answers, so text appears while the model is generating it.
- PDF text extraction with Tesseract OCR fallback for scanned pages.
- Knowledge Chat using local embeddings and ChromaDB.
- A bounded Agent Task mode for local calculations, document search, and verified TXT/PDF reports.

All normal inference and document processing runs on the host computer through Ollama. No cloud AI API is required at runtime.

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Install](#install)
- [Start the application](#start-the-application)
- [Use the application](#use-the-application)
- [Use from another PC](#use-from-another-pc)
- [Configuration](#configuration)
- [Run tests](#run-tests)
- [Project structure](#project-structure)
- [Security and privacy](#security-and-privacy)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)

## How it works

~~~
Browser or desktop client
          |
          v
 FastAPI server or app.py
          |
          +--> Ollama local chat model
          +--> PDF extraction and Tesseract OCR
          +--> ChromaDB local knowledge base
          +--> Bounded Agent Task tools
~~~

The browser application is the full-featured interface. The desktop application keeps a smaller local workflow for general chat and direct PDF analysis.

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer.
- Ollama installed and running: https://ollama.com/
- The Ollama chat model llama3.2:latest.
- The Ollama embedding model nomic-embed-text:latest for Knowledge Chat.
- Tesseract OCR for scanned PDFs. The application looks for a standard Windows installation such as C:\Program Files\Tesseract-OCR.

The first model download requires internet access. After the models and Python packages are installed, normal use can be offline.

Download the local models once:

~~~
ollama pull llama3.2
ollama pull nomic-embed-text
~~~

Confirm that Ollama is available before starting the application:

~~~
ollama list
~~~

## Install

Clone the repository and create a virtual environment:

~~~
git clone https://github.com/harshit-033/SIH_PROJECT_1.git
cd SIH_PROJECT_1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

If PowerShell does not allow virtual-environment activation, use the virtual-environment Python directly in every command:

~~~
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
~~~

Python dependencies are pinned in requirements.txt. The project currently uses Python 3.14.3 in its verified development environment, while the code targets Python 3.10 or newer.

## Start the application

### Browser application

From the project root:

~~~
.\.venv\Scripts\python.exe run_server.py
~~~

You can also run run_server.bat.

The terminal prints the local and LAN URLs. Open the local URL on the host computer:

~~~
http://localhost:8000
~~~

On the first run, the terminal prints a one-time generated administrator password. There are no hardcoded default passwords or demo accounts. You can set the first administrator credentials before starting the server:

~~~
$env:SIH_BOOTSTRAP_ADMIN_USERNAME = "admin"
$env:SIH_BOOTSTRAP_ADMIN_PASSWORD = "Use-A-Long-Unique-Password"
.\.venv\Scripts\python.exe run_server.py
~~~

### Desktop application

To start the Tkinter desktop client:

~~~
.\.venv\Scripts\python.exe app.py
~~~

You can also run run_chat_app.bat.

The desktop client supports general chat and direct PDF document analysis. It uses the local Ollama model and streams the answer as it is generated.

## Use the application

### General Chat

1. Sign in to the browser application, or open the desktop application.
2. Select General Chat.
3. Type a question and press Send.
4. Read the answer while it streams from the local model.

### Document Analysis

1. Select Document Analysis.
2. Upload or drag and drop a PDF file.
3. Wait for the document to finish processing.
4. Ask questions about the selected document.

Digital PDFs use native text extraction. Scanned pages are rendered locally and processed with Tesseract OCR. Mixed PDFs can use both methods, page by page.

### Knowledge Chat

Knowledge Chat searches documents that have been indexed into the local knowledge base.

1. Open Knowledge Chat.
2. Create or select a collection.
3. Upload a PDF or drag and drop it into the knowledge panel.
4. Select Index PDF and wait for the status to become INDEXED.
5. Ask a question about one or more indexed documents.

Answers include source filenames, page numbers, and whether the source text came from native extraction or OCR. Each user's knowledge documents are isolated from other users.

### Auto mode

Auto chooses a capability based on the request:

- Ordinary questions use General Chat.
- Questions about the selected PDF use Document Analysis.
- Cross-document requests such as Search my maintenance reports use Knowledge Chat.
- Clear multi-step requests can use Agent Task.

Explicit modes remain available when you want predictable behavior.

### Agent Task

Agent Task is a bounded local workflow for requests such as:

~~~
Calculate 18 * 24 and save the result as a TXT file.
Summarize my indexed reports and create a PDF.
~~~

It can search authorized knowledge documents, inspect document metadata, perform restricted arithmetic, and generate verified TXT/PDF files. It cannot execute shell commands, arbitrary Python, network requests, browser actions, or unrestricted filesystem operations.

## Use from another PC

Both computers must be on the same trusted private network.

1. Start the server on the host computer.
2. Run ipconfig on the host and find the IPv4 address of the active Wi-Fi or Ethernet adapter.
3. From the other PC, open http://HOST_IP:8000, replacing HOST_IP with that address. For example: http://192.168.1.23:8000.

Do not use 127.0.0.1 from another PC. It always refers to the computer making the request.

If the launcher cannot detect the correct address, set it explicitly before starting:

~~~
$env:SIH_LAN_IP = "192.168.1.23"
.\.venv\Scripts\python.exe run_server.py
~~~

If Windows Firewall blocks the connection, allow the server port on the host. Run this from an Administrator PowerShell only on a trusted private network:

~~~
New-NetFirewallRule -DisplayName "SIH Local AI Workbench 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
~~~

Plain HTTP should only be used on localhost or a trusted private LAN. For an untrusted network, configure HTTPS using the TLS variables below.

## Configuration

Set environment variables in PowerShell before starting the server. The most useful options are:

| Variable | Purpose | Default |
| --- | --- | --- |
| SIH_MODEL_NAME | Default Ollama chat model | llama3.2:latest |
| SIH_EMBED_MODEL | Ollama embedding model | nomic-embed-text:latest |
| SIH_SERVER_HOST | Server bind address | 0.0.0.0 |
| SIH_SERVER_PORT | Server port | 8000 |
| SIH_LAN_IP | Override detected private LAN IP | Auto-detected |
| SIH_USER_STORE_PATH | Account JSON file location | %LOCALAPPDATA%\SIHLocalAI\users.json |
| SIH_UPLOAD_DIR | Temporary uploaded-file directory | Project uploads directory |
| SIH_RAG_STORAGE_PATH | ChromaDB storage directory | Project data/rag directory |
| SIH_RAG_ENABLED | Enable Knowledge Chat | 1 |
| SIH_AGENT_ENABLED | Enable Agent Task | 1 |
| SIH_ENABLE_API_DOCS | Enable /docs and OpenAPI | Disabled |
| SIH_TLS_CERT_FILE | HTTPS certificate path | Not set |
| SIH_TLS_KEY_FILE | HTTPS private-key path | Not set |

Example HTTPS configuration:

~~~
$env:SIH_TLS_CERT_FILE = "C:\certs\server.crt"
$env:SIH_TLS_KEY_FILE = "C:\certs\server.key"
$env:SIH_COOKIE_SECURE = "1"
.\.venv\Scripts\python.exe run_server.py
~~~

For the complete configuration list and server details, see SERVER_GUIDE.md.

## Data locations

- Accounts: %LOCALAPPDATA%\SIHLocalAI\users.json.
- Temporary direct-analysis uploads: uploads by default.
- Persistent Knowledge Chat files, vectors, and metadata: data/rag by default.
- Agent outputs: data/agent_outputs/<session_id> by default.

The project does not use PostgreSQL, MySQL, MongoDB, or another SQL database. Account data is stored in JSON, and document embeddings are stored locally in ChromaDB.

## Run tests

Create the deterministic PDF fixtures first:

~~~
.\.venv\Scripts\python.exe .\tests\create_synthetic_pdfs.py
~~~

Run the test suite:

~~~
Get-ChildItem .\tests\test_*.py | ForEach-Object {
    & .\.venv\Scripts\python.exe $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "$($_.Name) failed" }
}
~~~

The model QA test uses the real local Ollama model. Make sure Ollama is running and both models are installed before running the full suite.

To audit installed Python packages:

~~~
.\.venv\Scripts\python.exe -m pip install pip-audit
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
~~~

## Project structure

~~~
app.py                    Tkinter desktop client
core/                     Authentication, sessions, files, queues, and AI services
document/                 PDF extraction, OCR, context, and prompts
rag/                      Chunking, embeddings, ChromaDB, and retrieval
routing/                  Capability detection and request routing
agent/                    Bounded planning, tools, approvals, audit, and outputs
server/                   FastAPI routes, authentication, and streaming APIs
static/                   Browser HTML, CSS, and JavaScript
tests/                    Functional, OCR, model, isolation, and security tests
run_server.py             LAN and HTTPS server launcher
requirements.txt          Pinned Python dependencies
SERVER_GUIDE.md           Detailed server and security reference
FINAL_TECH_STACK.txt      Current technology-stack inventory
~~~

## Security and privacy

- Passwords are hashed with scrypt. Legacy PBKDF2 hashes are migrated after a successful login.
- Browser sessions use random server-side tokens in HttpOnly, SameSite cookies.
- Tokens are not stored in browser storage or accepted in URLs.
- Login attempts, uploads, document sizes, OCR work, model context, and agent execution are bounded.
- User accounts, sessions, direct-analysis documents, and Knowledge Chat collections are isolated.
- PDF content is treated as untrusted evidence. Instructions inside uploaded documents are not treated as application instructions.
- API documentation is disabled by default.
- Use HTTPS before sending credentials over an untrusted network.

The current pinned ChromaDB version has unresolved advisories reported by pip-audit during the latest project verification. Review PHASE7_AGENT_REPORT.md before production deployment.

## Troubleshooting

### Ollama connection error

Make sure Ollama is running and verify the installed models:

~~~
ollama list
~~~

If a custom model is installed, set SIH_MODEL_NAME before starting the server.

### OCR is unavailable

Install Tesseract OCR for Windows and confirm that tesseract.exe is available at the expected installation path. Restart the application after installation.

### Knowledge Chat cannot index a PDF

Check that nomic-embed-text:latest is installed and that SIH_RAG_ENABLED is not set to 0. The server health page at /health reports whether the LLM, OCR, and RAG services are ready.

### Another PC cannot open the LAN URL

Use the host's private IPv4 address, not 127.0.0.1. Confirm that both computers are on the same network, the server is bound to 0.0.0.0, and Windows Firewall allows the selected port.

### The browser is unavailable after a restart

Start run_server.py again and open the URL printed in the terminal. The server must remain running while the browser application is in use.

## Documentation

- SERVER_GUIDE.md: server operation, roles, API behavior, security, and advanced configuration.
- DOCUMENT_WORKFLOW_CHECKLIST.md: document and OCR workflow checks.
- FINAL_TECH_STACK.txt: exact current technology stack and versions.
- PHASE7_AGENT_REPORT.md: latest Agent Task implementation and verification status.



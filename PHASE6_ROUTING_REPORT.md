# Phase 6 Capability-Based Routing Report

Date: 2026-09-04

## Status

**IMPLEMENTED AND VERIFIED for the browser/server routing scope.** The existing Tkinter client remains unchanged in behavior and is documented as a follow-up for Auto integration. Phase 5 OCR, direct document analysis, RAG, ChromaDB, local embeddings, RBAC, session isolation, file security, LAN operation, and SSE were preserved.

## Scope

Implemented capabilities:

- `GENERAL_CHAT`
- `DOCUMENT_ANALYSIS`
- `KNOWLEDGE_RAG`

No agents, tool execution, shell/code execution, sandbox, PostgreSQL, ORM, pgvector, cloud AI, hosted embeddings, or automatic model downloads were added.

## Architecture

Before Phase 6, the browser selected one of the existing chat endpoints directly. After Phase 6:

```text
User Request
     |
     v
Authentication
     |
Existing session/document authorization
     |
CapabilityRouter
     +--> GENERAL_CHAT      -> existing AIService path
     +--> DOCUMENT_ANALYSIS -> existing DocumentService + AIService path
     +--> KNOWLEDGE_RAG     -> existing RagService + AIService path
                                  |
                                  v
                         configured local Ollama model
```

The implementation is split into `routing/models.py`, `config.py`, `registry.py`, `classifier.py`, `router.py`, and `handlers.py`. `CapabilityDefinition` contains task metadata and a model mapping. `CapabilityHandler` names the existing subsystem binding. The server dispatches to the existing handlers; it does not duplicate OCR, PDF extraction, chunking, embeddings, vector search, or authentication.

## Model Separation

Capability selection does not contain model names. Model selection is resolved by the registry from:

| Capability | Environment variable | Default |
| :--- | :--- | :--- |
| `GENERAL_CHAT` | `SIH_GENERAL_MODEL` | `llama3.2:latest` |
| `DOCUMENT_ANALYSIS` | `SIH_DOCUMENT_MODEL` | `llama3.2:latest` |
| `KNOWLEDGE_RAG` | `SIH_RAG_MODEL` | `llama3.2:latest` |

Unset capability variables fall back to `SIH_MODEL_NAME`, then `llama3.2:latest`. Different local models can be configured without changing classifier code. The verified baseline continues to use the existing `llama3.2:latest`; no specialized model claim is made.

## Modes And Precedence

Explicit modes remain available and are authoritative:

1. Explicit `General Chat`, `Document Analysis`, or `Knowledge Chat`.
2. In `Auto`, strong cross-document intent routes to Knowledge RAG.
3. Document wording routes to Document Analysis when a selected session-owned document exists.
4. A vague request with a selected document stays in Document Analysis unless it has a clear general-chat signal.
5. Otherwise the safe fallback is General Chat.

Examples: `Hello` and `Explain recursion` route General; `What is the equipment ID in this report?` routes Document Analysis with a selected PDF; `Search my maintenance reports for Pump A17` routes Knowledge RAG. A vague `Tell me about Pump A17` routes Document Analysis only when a document is selected, otherwise General. Strong RAG intent with disabled RAG fails explicitly and is not silently downgraded.

## Request And Execution Flow

`POST /api/chat` now accepts optional `mode` and `collection_id` fields. Omitted mode preserves the old General Chat API behavior. Auto builds a `RoutingContext` from the authenticated user, current session document ID, requested collection ID, message, and dependency availability. It never sends document text to the classifier. The selected `RoutingDecision` then chooses the existing general, direct document, or RAG execution path.

`POST /api/route` returns a safe explanation only. SSE responses emit a `routing` event before status/chunks and keep the existing SSE protocol. The browser adds an Auto button and displays `Capability: ...` plus a concise reason.

## Authorization And Isolation Review

- Authentication executes before routing on every API endpoint.
- The router has no permission to retrieve data; RAG authorization remains inside `RagService.retrieve` and `require_collection`.
- Direct document analysis still calls `_select_document_for_session`, which verifies session ownership before processing.
- Auto cannot select a target document ID supplied by another user.
- No global current capability, current document, current collection, or routing decision state was introduced.
- User/session IDs are used only for request metadata and existing per-session history/queue behavior.
- Existing prompt-injection defense and trusted source metadata remain in the RAG handler.
- Routing logs exclude passwords, tokens, full prompts, private document text, and retrieved chunks.

## Failure Handling And Health

`SIH_ROUTING_ENABLED=0` returns an explicit router-disabled error. `SIH_AUTO_ROUTING_ENABLED=0` requires explicit mode. Invalid modes, unavailable required context, and unavailable RAG return explicit HTTP errors. Local model failures identify the capability/model in SSE or HTTP error text and never fall back to cloud services.

`GET /health` now reports per-capability model/handler status. General Chat and Document Analysis require their configured chat model; Document Analysis additionally reports OCR availability; Knowledge RAG reports both its chat model and the existing embedding/RAG readiness.

## Tests Executed

Dedicated `tests/test_routing.py` passed:

- greeting, explanation, explicit modes, Auto matrix
- selected-document and no-document behavior
- knowledge-base intent and unavailable RAG
- disabled router, invalid mode, missing document
- independent capability-to-model mappings
- safe `/api/route` response
- streamed Auto General, Document, and RAG dispatch
- three authenticated clients with independent General, Knowledge, and Document routing decisions

The full regression set passed: document workflow, application state, demo runs, concurrency queue, API server, file security, security regressions, RBAC/auth, admin profile, session isolation, LAN E2E, real local model/document Q&A, RAG, and routing.

The real model/document test confirmed `llama3.2:latest` remains available and the existing document-Q&A path works. RAG tests confirmed local Chroma persistence, source metadata, ownership isolation, reindex/delete, failure state, and prompt-injection defense. The routing API tests use isolated temporary test stores and patched handlers where needed so they are deterministic and do not mutate production accounts.

An isolated real-local Phase 6 run also passed with temporary account/upload/RAG storage: Auto General completed in 5.24 s including model warm-up, Auto selected-document analysis completed in 0.26 s, and Auto Knowledge RAG completed in 3.58 s with two authorized sources. These totals include local model/embedding work; routing itself remained approximately 0.019-0.022 ms in that run.

## Performance

The deterministic routing smoke measurement on this host produced approximately `0.005-0.020 ms` per decision across the Phase 6 examples. This is classifier/router time only; it is not model generation time. The response includes `routing_latency_ms`. Existing RAG retrieval, document extraction, and model timings remain separate and are not combined into this value.

## Known Limitations

- Auto is intentionally deterministic and conservative; it does not use an LLM classifier.
- Knowledge RAG can search all authorized indexed documents when no collection is specified, as in the existing Phase 5 API. The RAG service still applies owner filtering.
- The Tkinter desktop client keeps its stable existing explicit General/Document workflows. Auto is integrated in the browser/server client because that is the current multi-client routing surface; desktop Auto can be added later without changing the routing package.
- Capability health checks report configured model availability, but a model can still become unavailable after the health request and fail at inference time with a clear error.

## Acceptance Checklist

- [x] Capability abstraction, registry, classifier, router, and handler bindings
- [x] Capability/model separation and environment configuration
- [x] General, Document, Knowledge RAG, explicit modes, and Auto mode
- [x] Deterministic ambiguity and precedence behavior
- [x] Existing OCR, PDF, RAG, RBAC, file security, session isolation, queue, and SSE preserved
- [x] Safe routing explanation and observability
- [x] Capability health reporting
- [x] Dedicated routing tests and full regression suite
- [x] Local model/document verification and RAG authorization verification
- [x] Documentation and completion report
- [x] No cloud AI, PostgreSQL, agents, tools, or extra required model

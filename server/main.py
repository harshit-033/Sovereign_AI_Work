from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ai_service import AIService
from core.auth import (
    AuthService,
    LoginAttemptLimiter,
    MIN_PASSWORD_LENGTH,
    hash_password,
    validate_password,
    verify_password,
)
from core.document_service import DocumentService
from core.file_handler import FileHandler
from core.models import AppMode, AuthToken, DocumentMetadata, UserCredentials, UserModel, UserRole
from core.monitoring import MonitoringService
from core.request_queue import RequestQueue
from core.session_manager import SessionManager
from core.user_store import UserStore
from document.loader import MAX_PDF_SIZE_MB
from rag import RagConfig, RagError, RagService, RagStatus
from rag.embeddings import RagEmbeddingError
from rag.file_store import RagFileStoreError
from rag.prompts import RAG_SYSTEM_PROMPT
from rag.service import RagConflictError, RagDisabledError, RagNotFoundError
from rag.vector_store import VectorStoreError
from routing import (
    CapabilityId,
    CapabilityRouter,
    CapabilityUnavailableError,
    RoutingConfig,
    RoutingContext,
    RouterDisabledError,
    UnknownCapabilityError,
    build_default_registry,
)
from agent import AgentConfig, AgentService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sih_server")

AUTH_COOKIE_NAME = "sih_session"
MAX_CHAT_CHARS = 8_000
MAX_GENERATED_CHARS = 64_000
MAX_UPLOAD_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
API_DOCS_ENABLED = os.getenv("SIH_ENABLE_API_DOCS", "0") == "1"

app = FastAPI(
    title="SIH Local AI Workbench Server",
    description="Multi-client local AI server with document OCR and RBAC",
    version="3.0.0",
    docs_url="/docs" if API_DOCS_ENABLED else None,
    redoc_url=None,
    openapi_url="/openapi.json" if API_DOCS_ENABLED else None,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
        "form-action 'self'; img-src 'self' data:; object-src 'none'; "
        "script-src 'self'; style-src 'self'; connect-src 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _default_user_store_path() -> Path:
    configured = os.getenv("SIH_USER_STORE_PATH")
    if configured:
        return Path(configured).resolve()
    local_data = os.getenv("LOCALAPPDATA")
    if not local_data:
        return (PROJECT_ROOT / "data" / "users.json").resolve()
    target = (Path(local_data) / "SIHLocalAI" / "users.json").resolve()
    legacy = PROJECT_ROOT / "data" / "users.json"
    if not target.exists() and legacy.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, target)
        logger.info("Migrated account store to the local application-data directory.")
    return target


user_store_path = _default_user_store_path()
user_store = UserStore(storage_path=user_store_path)
auth_service = AuthService(user_store=user_store)
login_limiter = LoginAttemptLimiter()
ai_service = AIService(model_name=os.getenv("SIH_MODEL_NAME", "llama3.2:latest"))
doc_service = DocumentService()
file_handler = FileHandler(base_upload_dir=os.getenv("SIH_UPLOAD_DIR", str(PROJECT_ROOT / "uploads")))
session_manager = SessionManager()
request_queue = RequestQueue(max_concurrent_inference=1)
monitoring_service = MonitoringService()
rag_service = RagService(config=RagConfig.from_env())
routing_config = RoutingConfig.from_env()
capability_registry = build_default_registry(routing_config)
capability_router = CapabilityRouter(routing_config, capability_registry)
agent_service = AgentService(
    session_manager,
    rag_service,
    doc_service,
    os.getenv("SIH_AGENT_OUTPUT_DIR", str(PROJECT_ROOT / "data" / "agent_outputs")),
    config=AgentConfig.from_env(),
)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=128)


class UpdateUsernameRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=128)
    confirm_password: str = Field(..., min_length=1, max_length=128)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_CHAT_CHARS)
    mode: Optional[str] = Field(default=None, max_length=40)
    collection_id: Optional[str] = Field(default=None, min_length=1, max_length=80)
    stream: bool = True


class CollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)


class RagChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_CHAT_CHARS)
    collection_id: Optional[str] = Field(default=None, min_length=1, max_length=80)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    stream: bool = True


class ApprovalDecisionRequest(BaseModel):
    approved: bool


def _request_token(request: Request, authorization: Optional[str]) -> Optional[str]:
    if authorization:
        scheme, separator, value = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not value.strip():
            raise HTTPException(status_code=401, detail="Malformed Authorization header.")
        return value.strip()
    return request.cookies.get(AUTH_COOKIE_NAME)


async def require_authenticated_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> tuple[str, str, str, UserRole, UserModel]:
    token_text = _request_token(request, authorization)
    if not token_text:
        raise HTTPException(status_code=401, detail="Authentication required.")

    auth_token = auth_service.validate_token(token_text)
    if not auth_token or not auth_token.session_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")

    user = user_store.get_user_by_id(auth_token.user_id)
    session = session_manager.get_session(auth_token.session_id)
    if not user or not user.is_active or not session or session.user_id != user.id:
        auth_service.revoke_token(token_text)
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")

    return session.session_id, user.id, user.username, user.role, user


async def require_admin(
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
) -> UserModel:
    _, _, username, role, user = current
    if role != UserRole.ADMIN:
        logger.warning("Admin access denied for user '%s'", username)
        raise HTTPException(status_code=403, detail="Admin privilege required.")
    return user


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=True)}\n\n"


def _routing_context(
    current: tuple[str, str, str, UserRole, UserModel],
    req: ChatRequest,
) -> RoutingContext:
    session = session_manager.get_session(current[0])
    return RoutingContext(
        user_id=current[1],
        role=current[3].value,
        selected_mode=req.mode or "General Chat",
        selected_document_id=session.current_document_id if session else None,
        knowledge_collection_id=req.collection_id,
        message=req.message.strip(),
        knowledge_base_available=bool(rag_service.config.enabled),
    )


def _route_http_error(exc: Exception) -> None:
    if isinstance(exc, (RouterDisabledError, CapabilityUnavailableError)):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, (UnknownCapabilityError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=403, detail=str(exc)) from exc


def _model_stream_call(messages: List[Dict[str, str]], model_name: str):
    # Keep the legacy call shape for the default model and existing integrations.
    if model_name == ai_service.model_name:
        return ai_service.generate_chat_stream(messages)
    return ai_service.generate_chat_stream(messages, model_name=model_name)


async def _model_stream(
    session_id: str,
    mode: AppMode,
    user_message: str,
    model_message: str,
    action_type: str,
    system_prompt: Optional[str] = None,
    model_name: Optional[str] = None,
    routing_decision=None,
) -> AsyncGenerator[str, None]:
    task = request_queue.create_task(session_id, action_type)
    await request_queue.acquire_slot(task)
    loop = asyncio.get_running_loop()
    output_queue: asyncio.Queue[tuple[str, Optional[str]]] = asyncio.Queue()
    stop_event = threading.Event()
    collected: List[str] = []
    started_at = time.perf_counter()

    messages = session_manager.get_messages(session_id, mode)
    if system_prompt and messages:
        messages[0] = {"role": "system", "content": system_prompt}
    messages.append({"role": "user", "content": model_message})

    def produce() -> None:
        generated_chars = 0
        try:
            for piece in _model_stream_call(messages, model_name or ai_service.model_name):
                if stop_event.is_set():
                    break
                remaining = MAX_GENERATED_CHARS - generated_chars
                if remaining <= 0:
                    break
                bounded_piece = piece[:remaining]
                generated_chars += len(bounded_piece)
                loop.call_soon_threadsafe(output_queue.put_nowait, ("chunk", bounded_piece))
        except Exception as exc:
            logger.exception("Local inference stream failed: %s", exc)
            if not stop_event.is_set():
                loop.call_soon_threadsafe(output_queue.put_nowait, ("error", None))
        finally:
            if not stop_event.is_set():
                loop.call_soon_threadsafe(output_queue.put_nowait, ("done", None))

    worker = loop.run_in_executor(None, produce)
    success = False
    error_message: Optional[str] = None
    try:
        if routing_decision:
            yield _sse({"type": "routing", "routing": routing_decision.to_dict()})
        yield _sse({"type": "status", "status": "processing"})
        while True:
            event_type, content = await output_queue.get()
            if event_type == "chunk" and content:
                collected.append(content)
                yield _sse({"type": "chunk", "content": content})
            elif event_type == "error":
                capability_name = routing_decision.display_name if routing_decision else mode.value
                configured_model = model_name or ai_service.model_name
                error_message = (
                    f"Local model inference failed for {capability_name} "
                    f"using configured model '{configured_model}'."
                )
                yield _sse({"type": "error", "error": error_message})
            elif event_type == "done":
                break

        await worker
        if error_message is None:
            session_manager.add_message(session_id, mode, "user", user_message)
            session_manager.add_message(session_id, mode, "assistant", "".join(collected))
            success = True
            yield _sse(
                {"type": "done", "latency_seconds": round(time.perf_counter() - started_at, 2)}
            )
    except asyncio.CancelledError:
        stop_event.set()
        error_message = "Client disconnected."
        try:
            await asyncio.wait_for(asyncio.shield(worker), timeout=10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        raise
    finally:
        stop_event.set()
        await request_queue.release_slot(task, success=success, error=error_message)


async def _non_stream_chat(
    session_id: str,
    mode: AppMode,
    user_message: str,
    model_message: str,
    action_type: str,
    model_name: Optional[str] = None,
) -> dict:
    task = request_queue.create_task(session_id, action_type)
    await request_queue.acquire_slot(task)
    try:
        messages = session_manager.get_messages(session_id, mode)
        messages.append({"role": "user", "content": model_message})
        if model_name and model_name != ai_service.model_name:
            result = await asyncio.to_thread(ai_service.generate_chat, messages, model_name=model_name)
        else:
            result = await asyncio.to_thread(ai_service.generate_chat, messages)
        session_manager.add_message(session_id, mode, "user", user_message)
        session_manager.add_message(session_id, mode, "assistant", result["content"])
        await request_queue.release_slot(task, success=True)
        return result
    except Exception as exc:
        logger.exception("Local inference failed: %s", exc)
        await request_queue.release_slot(task, success=False, error="Inference failed")
        configured_model = model_name or ai_service.model_name
        raise HTTPException(
            status_code=503,
            detail=f"Local model inference failed using configured model '{configured_model}'.",
        ) from exc


async def _agent_stream(task, context, plan, routing_decision) -> AsyncGenerator[str, None]:
    queue_task = request_queue.create_task(task.session_id, "agent_task")
    await request_queue.acquire_slot(queue_task)
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
    started = time.perf_counter()

    def progress(event_type: str, payload: dict) -> None:
        loop.call_soon_threadsafe(events.put_nowait, (event_type, payload))

    def run():
        return agent_service.execute(context, plan, progress=progress)

    worker = loop.run_in_executor(None, run)
    success = False
    try:
        yield _sse({"type": "routing", "routing": routing_decision.to_dict()})
        yield _sse({"type": "agent_started", "task_id": task.task_id})
        yield _sse({"type": "plan_created", "steps": [item.tool_id for item in plan.steps]})
        while True:
            if worker.done() and events.empty():
                break
            try:
                event_type, payload = await asyncio.wait_for(events.get(), timeout=0.1)
                yield _sse({"type": event_type, **payload})
            except asyncio.TimeoutError:
                continue
        result = await worker
        if result.status == "COMPLETED":
            success = True
        yield _sse({
            "type": "final_result",
            "status": result.status,
            "task_id": result.task_id,
            "message": result.message,
            "generated_files": list(result.generated_files),
            "total_latency_ms": round(result.total_latency_ms, 3),
        })
    except asyncio.CancelledError:
        raise
    finally:
        await request_queue.release_slot(queue_task, success=success, error=None if success else "Agent task failed")


@app.get("/health")
async def health_check():
    model_names = {definition.model_name for definition in capability_registry.all()}
    model_health_list, ocr_health = await asyncio.gather(
        asyncio.gather(*(asyncio.to_thread(ai_service.check_health, name) for name in model_names)),
        asyncio.to_thread(doc_service.check_ocr_availability),
    )
    model_health = {item["model_configured"]: item for item in model_health_list}
    general_health = model_health.get(capability_registry.get(CapabilityId.GENERAL_CHAT).model_name, {})
    ready = bool(general_health.get("connected") and general_health.get("model_available"))
    rag_health = await asyncio.to_thread(rag_service.embedding_health) if rag_service.config.enabled else {
        "model_configured": rag_service.config.embedding_model,
        "model_available": False,
        "disabled": True,
    }
    return {
        "status": "healthy" if ready else "degraded",
        "services": {
            "llm_ready": ready,
            "ocr_ready": ocr_health["tesseract_installed"],
            "rag_enabled": rag_service.config.enabled,
            "rag_ready": bool(rag_service.config.enabled and rag_health.get("model_available")),
            "embedding_model": rag_service.config.embedding_model,
            "embedding_error": rag_health.get("error", "") if rag_service.config.enabled else "",
            "capabilities": [
                item.to_dict()
                for item in capability_router.health(
                    model_health,
                    rag_enabled=rag_service.config.enabled and bool(rag_health.get("model_available")),
                    ocr_ready=ocr_health["tesseract_installed"],
                )
            ],
        },
    }


@app.get("/api/metrics")
async def get_metrics(
    _: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    queue_stats = request_queue.get_stats()
    ai_health = await asyncio.to_thread(ai_service.check_health)
    metrics = monitoring_service.get_metrics(
        active_requests=queue_stats["active_requests"],
        queued_requests=queue_stats["queued_requests"],
        inference_worker_busy=queue_stats["inference_worker_busy"],
        ollama_connected=ai_health["connected"],
        model_available=ai_health["model_available"],
    )
    return {
        "metrics": {
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "active_requests": metrics.active_requests,
            "queued_requests": metrics.queued_requests,
        },
        "ai": {
            "connected": ai_health["connected"],
            "model_available": ai_health["model_available"],
            "model_configured": ai_service.model_name,
        },
        "rag": {
            "enabled": rag_service.config.enabled,
            "embedding_model": rag_service.config.embedding_model,
            "embedding_available": bool(
                rag_service.config.enabled
                and (await asyncio.to_thread(rag_service.embedding_health)).get("model_available")
            ),
            "vector_count": await asyncio.to_thread(rag_service.vectors.count),
        },
    }


@app.post("/api/auth/login")
async def login(creds: LoginRequest, request: Request, response: Response):
    client_host = request.client.host if request.client else "unknown"
    limiter_key = f"{client_host}:{creds.username.strip().casefold()}"
    if not login_limiter.is_allowed(limiter_key):
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Try again later.")

    token = auth_service.authenticate(
        UserCredentials(username=creds.username, password=creds.password)
    )
    if token == "ADMIN_ALREADY_ACTIVE":
        raise HTTPException(status_code=409, detail="Admin account is already logged in.")
    if not isinstance(token, AuthToken):
        login_limiter.record_failure(limiter_key)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    login_limiter.clear(limiter_key)
    session = session_manager.create_session(token.user_id, token.username, token.role)
    token.session_id = session.session_id
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token.token,
        max_age=auth_service.token_ttl_seconds,
        httponly=True,
        samesite="strict",
        secure=os.getenv("SIH_COOKIE_SECURE", "0") == "1" or request.url.scheme == "https",
        path="/",
    )
    return {
        "token": token.token,
        "user_id": token.user_id,
        "username": token.username,
        "role": token.role.value,
        "expires_at": token.expires_at,
        "session_id": session.session_id,
    }


@app.post("/api/auth/logout")
async def logout(
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(None),
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    session_id, _, username, _, _ = current
    token_text = _request_token(request, authorization)
    if token_text:
        auth_service.revoke_token(token_text)
    session_manager.delete_session(session_id)
    file_handler.delete_session_files(session_id)
    agent_service.outputs.cleanup_session(session_id)
    agent_service.audit.delete_session(session_id, current[1])
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", samesite="strict")
    logger.info("User '%s' logged out", username)
    return {"message": "Successfully logged out."}


@app.get("/api/auth/me")
async def get_current_user_profile(
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    return current[4].to_safe_dict()


@app.get("/api/admin/users")
async def list_users(_: UserModel = Depends(require_admin)):
    users = user_store.list_users()
    return {
        "summary": {
            "total_users": len(users),
            "active_users": sum(1 for user in users if user.is_active),
            "admin_users": sum(
                1 for user in users if user.role == UserRole.ADMIN and user.is_active
            ),
        },
        "users": [user.to_safe_dict() for user in users],
    }


@app.post("/api/admin/users")
async def create_user(req: CreateUserRequest, admin: UserModel = Depends(require_admin)):
    try:
        validate_password(req.password)
        new_user = user_store.create_user(req.username, hash_password(req.password), UserRole.USER)
    except ValueError as exc:
        code = 409 if "already exists" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    logger.info("Admin '%s' created user '%s'", admin.username, new_user.username)
    return {"message": "User created successfully.", "user": new_user.to_safe_dict()}


@app.delete("/api/admin/users/{user_id}")
async def remove_user(user_id: str, admin: UserModel = Depends(require_admin)):
    target = user_store.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Admin cannot remove their own account.")
    try:
        user_store.remove_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    auth_service.revoke_user_tokens(user_id)
    for session_id in session_manager.delete_user_sessions(user_id):
        file_handler.delete_session_files(session_id)
    rag_service.delete_user_documents(user_id)
    logger.info("Admin '%s' removed user '%s'", admin.username, target.username)
    return {"message": "User removed successfully."}


@app.patch("/api/admin/me")
async def update_admin_username(req: UpdateUsernameRequest, admin: UserModel = Depends(require_admin)):
    try:
        updated = user_store.update_username(admin.id, req.username)
    except ValueError as exc:
        code = 409 if "already taken" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    for session in session_manager.list_sessions():
        if session.user_id == admin.id:
            session.username = updated.username
    return {"message": "Username updated successfully.", "user": updated.to_safe_dict()}


@app.post("/api/admin/me/change-password")
async def change_admin_password(
    req: ChangePasswordRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
    admin: UserModel = Depends(require_admin),
):
    if not verify_password(req.current_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirmation do not match.")
    try:
        validate_password(req.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user_store.update_password_hash(admin.id, hash_password(req.new_password))
    auth_service.revoke_user_tokens(admin.id, except_token=_request_token(request, authorization))
    return {"message": "Password changed successfully."}


@app.get("/api/session")
async def get_session_info(
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    session = session_manager.get_session(current[0])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    context = session.current_document_context
    return {
        "session_id": session.session_id,
        "username": session.username,
        "role": current[3].value,
        "mode": session.mode.value,
        "current_document_id": session.current_document_id,
        "current_document_context": (
            {
                "included_pages": context.included_pages,
                "total_text_pages": context.total_text_pages,
                "truncated": context.truncated,
                "estimated_tokens": context.estimated_tokens,
            }
            if context
            else None
        ),
        "uploaded_documents": [doc.to_dict() for doc in session.uploaded_documents.values()],
        "general_messages": [m for m in session.general_messages if m["role"] != "system"],
        "document_messages": [m for m in session.document_messages if m["role"] != "system"],
        "knowledge_messages": [m for m in session.knowledge_messages if m["role"] != "system"],
    }


@app.post("/api/chat/clear")
async def clear_chat(
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    session_id = current[0]
    session_manager.clear_session_chat(session_id)
    file_handler.delete_session_files(session_id)
    agent_service.outputs.cleanup_session(session_id)
    agent_service.audit.delete_session(session_id, current[1])
    return {"message": "Chat and documents cleared.", "mode": AppMode.GENERAL_CHAT.value}


@app.post("/api/chat")
async def general_chat(
    req: ChatRequest,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    session_id = current[0]
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Empty prompt.")
    try:
        decision = capability_router.route(_routing_context(current, req))
    except Exception as exc:
        _route_http_error(exc)

    definition = capability_registry.get(decision.capability)
    logger.info(
        "Routing request session_id=%s user_id=%s mode=%s capability=%s model=%s latency_ms=%.3f handler=%s",
        session_id,
        current[1],
        req.mode or "General Chat",
        decision.capability.value,
        decision.model_name,
        decision.routing_latency_ms,
        definition.handler,
    )
    if decision.capability == CapabilityId.AGENT_TASK:
        if not agent_service.config.enabled:
            raise HTTPException(status_code=503, detail="Agent Task capability is disabled.")
        session = session_manager.get_session(session_id)
        task = agent_service.new_task(session_id, current[1], current[3].value, user_message)
        try:
            context, plan = agent_service.plan(
                task,
                session.current_document_id if session else None,
                req.collection_id,
            )
        except Exception as exc:
            logger.warning("Agent plan rejected task_id=%s: %s", task.task_id, exc)
            raise HTTPException(status_code=400, detail=f"Agent plan rejected: {exc}") from exc
        if not req.stream:
            result = await asyncio.to_thread(agent_service.execute, context, plan)
            return {
                "task_id": result.task_id,
                "status": result.status,
                "message": result.message,
                "plan": [step.tool_id for step in plan.steps],
                "generated_files": list(result.generated_files),
                "routing": decision.to_dict(),
                "total_latency_ms": round(result.total_latency_ms, 3),
            }
        return StreamingResponse(
            _agent_stream(task, context, plan, decision),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
        )
    if decision.capability == CapabilityId.KNOWLEDGE_RAG:
        try:
            results = await asyncio.to_thread(
                rag_service.retrieve, current[1], user_message, req.collection_id, None
            )
        except Exception as exc:
            _raise_rag_http_error(exc)
        if not req.stream:
            if not results:
                return {
                    "content": "The available indexed documents do not provide sufficient evidence.",
                    "latency_seconds": 0.0,
                    "model": decision.model_name,
                    "sources": [],
                    "routing": decision.to_dict(),
                }
            result = await _non_stream_chat(
                session_id,
                AppMode.KNOWLEDGE_CHAT,
                user_message,
                rag_service.build_prompt(user_message, results),
                "rag_chat",
                model_name=decision.model_name,
            )
            result["sources"] = [item.source_dict() for item in results]
            result["routing"] = decision.to_dict()
            return result
        return StreamingResponse(
            _rag_stream(session_id, user_message, results, decision),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
        )

    if decision.capability == CapabilityId.DOCUMENT_ANALYSIS:
        session = session_manager.get_session(session_id)
        if not session or not session.current_document_context or not session.current_document_context.text:
            raise HTTPException(status_code=400, detail="No readable selected document is available.")
        formatted = doc_service.format_prompt(user_message, session.current_document_context.text)
        if not req.stream:
            result = await _non_stream_chat(
                session_id, AppMode.DOCUMENT_ANALYSIS, user_message, formatted, "auto_document_chat", decision.model_name
            )
            result["routing"] = decision.to_dict()
            return result
        return StreamingResponse(
            _model_stream(
                session_id, AppMode.DOCUMENT_ANALYSIS, user_message, formatted,
                "auto_document_chat", model_name=decision.model_name, routing_decision=decision,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
        )

    if not req.stream:
        result = await _non_stream_chat(
            session_id, AppMode.GENERAL_CHAT, user_message, user_message, "general_chat", decision.model_name
        )
        result["routing"] = decision.to_dict()
        return result
    return StreamingResponse(
        _model_stream(
            session_id, AppMode.GENERAL_CHAT, user_message, user_message, "general_chat",
            model_name=decision.model_name, routing_decision=decision,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


@app.post("/api/route")
async def explain_route(
    req: ChatRequest,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    """Return a safe routing explanation without document text or retrieval."""
    try:
        decision = capability_router.route(_routing_context(current, req))
    except Exception as exc:
        _route_http_error(exc)
    logger.info(
        "Routing explanation session_id=%s user_id=%s capability=%s latency_ms=%.3f",
        current[0], current[1], decision.capability.value, decision.routing_latency_ms,
    )
    return {"routing": decision.to_dict()}


@app.get("/api/agent/approvals")
async def list_agent_approvals(
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    return {
        "approvals": [
            {
                "approval_id": item.approval_id,
                "task_id": item.task_id,
                "tool_id": item.tool_id,
                "purpose": item.purpose,
                "arguments": item.safe_arguments,
                "risk_level": item.risk_level,
                "status": item.status,
            }
            for item in agent_service.approvals.list_for_session(current[0], current[1])
        ]
    }


@app.post("/api/agent/approvals/{approval_id}")
async def decide_agent_approval(
    approval_id: str,
    req: ApprovalDecisionRequest,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    try:
        item = agent_service.approvals.resolve(approval_id, current[0], current[1], req.approved)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    logger.info("Agent approval resolved approval_id=%s task_id=%s decision=%s", item.approval_id, item.task_id, item.status)
    return {"approval_id": item.approval_id, "task_id": item.task_id, "status": item.status}


@app.get("/api/agent/audit")
async def list_agent_audit(
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    return {"records": [record.to_dict() for record in agent_service.audit.list_for_session(current[0], current[1])]}


@app.get("/api/agent/outputs/{output_id}")
async def download_agent_output(
    output_id: str,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    try:
        path = agent_service.outputs.resolve(output_id, current[0])
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Output file not found or access denied.") from exc
    return FileResponse(path, filename=path.name)


async def _read_limited_upload(file: UploadFile) -> bytes:
    content = bytearray()
    while True:
        chunk = await file.read(UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"PDF exceeds the {MAX_PDF_SIZE_MB} MB upload limit.",
            )
    return bytes(content)


def _raise_rag_http_error(exc: Exception) -> None:
    if isinstance(exc, RagDisabledError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, RagNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, RagConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, (RagEmbeddingError, VectorStoreError)):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, (RagFileStoreError, RagError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.exception("Unexpected RAG operation failure: %s", exc)
    raise HTTPException(status_code=500, detail="The local knowledge-base operation failed.") from exc


async def _run_rag_index(
    owner_user_id: str,
    collection_id: str,
    filename: str,
    content: bytes,
) -> object:
    task = request_queue.create_task(owner_user_id, "rag_index")
    await request_queue.acquire_slot(task)
    try:
        result = await asyncio.to_thread(
            rag_service.index_pdf,
            owner_user_id,
            collection_id,
            filename,
            content,
            doc_service.process_pdf,
        )
        await request_queue.release_slot(task, success=True)
        return result
    except Exception:
        await request_queue.release_slot(task, success=False, error="RAG indexing failed")
        raise


@app.post("/api/documents")
async def upload_document(
    file: UploadFile = File(...),
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    session_id = current[0]
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    content = await _read_limited_upload(file)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    saved_path: Optional[Path] = None
    try:
        doc_id, saved_path = await asyncio.to_thread(
            file_handler.save_uploaded_file, session_id, filename, content
        )
        extraction = await asyncio.to_thread(doc_service.process_pdf, str(saved_path))
        context = doc_service.create_context(extraction.pages)
        safe_filename = file_handler.sanitize_filename(filename)
        meta = DocumentMetadata(
            document_id=doc_id,
            session_id=session_id,
            filename=safe_filename,
            stored_path=str(saved_path),
            page_count=extraction.page_count,
            extracted_chars=extraction.extracted_chars,
            file_size_mb=extraction.file_size_mb,
            extraction_seconds=extraction.extraction_seconds,
            native_pages=extraction.native_pages,
            ocr_pages=extraction.ocr_pages,
            method_summary=extraction.method_summary,
        )
        session_manager.add_document(session_id, meta, extraction, context)
    except HTTPException:
        raise
    except ValueError as exc:
        if saved_path:
            file_handler.delete_file(saved_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if saved_path:
            file_handler.delete_file(saved_path)
        logger.exception("Document processing failed: %s", exc)
        raise HTTPException(status_code=400, detail="The selected PDF could not be processed.") from exc

    return {
        "message": "Document processed successfully.",
        "document": meta.to_dict(),
        "context": {
            "included_pages": context.included_pages,
            "total_text_pages": context.total_text_pages,
            "truncated": context.truncated,
            "estimated_tokens": context.estimated_tokens,
        },
        "mode": session_manager.get_session(session_id).mode.value,
    }


@app.get("/api/documents")
async def list_documents(
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    session = session_manager.get_session(current[0])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"documents": [doc.to_dict() for doc in session.uploaded_documents.values()]}


async def _select_document_for_session(session_id: str, document_id: str) -> None:
    session = session_manager.get_session(session_id)
    if not session or not session_manager.verify_document_ownership(session_id, document_id):
        raise HTTPException(status_code=403, detail="Document not found or access denied.")
    if session.current_document_id == document_id and session.current_document_context:
        return
    meta = session.uploaded_documents[document_id]
    try:
        extraction = await asyncio.to_thread(doc_service.process_pdf, meta.stored_path)
        context = doc_service.create_context(extraction.pages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_manager.select_document(session_id, document_id, extraction, context)


@app.post("/api/documents/{document_id}/select")
async def select_document(
    document_id: str,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    await _select_document_for_session(current[0], document_id)
    session = session_manager.get_session(current[0])
    meta = session.uploaded_documents[document_id]
    return {"message": "Document selected.", "document": meta.to_dict(), "mode": session.mode.value}


@app.post("/api/documents/{document_id}/chat")
async def document_chat(
    document_id: str,
    req: ChatRequest,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    session_id = current[0]
    await _select_document_for_session(session_id, document_id)
    session = session_manager.get_session(session_id)
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Empty question.")
    if not session.current_document_context or not session.current_document_context.text:
        raise HTTPException(status_code=400, detail="No readable document text available.")
    formatted = doc_service.format_prompt(user_message, session.current_document_context.text)
    action = f"doc_chat_{document_id}"
    try:
        decision = capability_router.route(
            RoutingContext(
                current[1], current[3].value, "Document Analysis", document_id,
                None, user_message,
            )
        )
    except Exception as exc:
        _route_http_error(exc)
    if agent_service.config.enabled and agent_service.planner.report_intent(user_message):
        task = agent_service.new_task(session_id, current[1], current[3].value, user_message)
        try:
            context, plan = agent_service.plan(task, document_id, None)
        except Exception as exc:
            logger.warning("Document report plan rejected task_id=%s: %s", task.task_id, exc)
            raise HTTPException(status_code=400, detail=f"Report plan rejected: {exc}") from exc
        if not req.stream:
            result = await asyncio.to_thread(agent_service.execute, context, plan)
            return {
                "task_id": result.task_id,
                "status": result.status,
                "message": result.message,
                "plan": [step.tool_id for step in plan.steps],
                "generated_files": list(result.generated_files),
                "routing": decision.to_dict(),
                "total_latency_ms": round(result.total_latency_ms, 3),
            }
        return StreamingResponse(
            _agent_stream(task, context, plan, decision),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
        )
    if not req.stream:
        result = await _non_stream_chat(
            session_id, AppMode.DOCUMENT_ANALYSIS, user_message, formatted, action,
            model_name=decision.model_name,
        )
        result["routing"] = decision.to_dict()
        return result
    return StreamingResponse(
        _model_stream(
            session_id, AppMode.DOCUMENT_ANALYSIS, user_message, formatted, action,
            model_name=decision.model_name,
            routing_decision=decision,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/api/rag/collections")
async def list_rag_collections(
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    try:
        collections = await asyncio.to_thread(rag_service.list_collections, current[1])
        return {"collections": [collection.to_dict() for collection in collections]}
    except Exception as exc:
        _raise_rag_http_error(exc)


@app.post("/api/rag/collections")
async def create_rag_collection(
    req: CollectionRequest,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    try:
        collection = await asyncio.to_thread(rag_service.create_collection, current[1], req.name)
        return {"message": "Collection created.", "collection": collection.to_dict()}
    except Exception as exc:
        _raise_rag_http_error(exc)


@app.get("/api/rag/documents")
async def list_rag_documents(
    collection_id: Optional[str] = None,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    try:
        documents = await asyncio.to_thread(rag_service.list_documents, current[1], collection_id)
        return {"documents": [document.to_dict() for document in documents]}
    except Exception as exc:
        _raise_rag_http_error(exc)


@app.get("/api/rag/documents/{document_id}")
async def get_rag_document(
    document_id: str,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    try:
        document = await asyncio.to_thread(rag_service.get_document, current[1], document_id)
        return {"document": document.to_dict()}
    except Exception as exc:
        _raise_rag_http_error(exc)


@app.post("/api/rag/documents")
async def upload_rag_document(
    file: UploadFile = File(...),
    collection_id: Optional[str] = Form(None),
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    try:
        collection = (
            await asyncio.to_thread(rag_service.require_collection, current[1], collection_id)
            if collection_id
            else await asyncio.to_thread(rag_service.ensure_default_collection, current[1])
        )
        content = await _read_limited_upload(file)
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        safe_filename = file_handler.sanitize_filename(filename)
        document = await _run_rag_index(current[1], collection.collection_id, safe_filename, content)
        return {
            "message": "Document indexed successfully.",
            "collection": collection.to_dict(),
            "document": document.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        _raise_rag_http_error(exc)


@app.post("/api/rag/documents/{document_id}/reindex")
async def reindex_rag_document(
    document_id: str,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    task = request_queue.create_task(current[1], "rag_reindex")
    await request_queue.acquire_slot(task)
    try:
        document = await asyncio.to_thread(
            rag_service.reindex_document,
            current[1],
            document_id,
            doc_service.process_pdf,
        )
        await request_queue.release_slot(task, success=True)
        return {"message": "Document re-indexed successfully.", "document": document.to_dict()}
    except Exception as exc:
        await request_queue.release_slot(task, success=False, error="RAG re-indexing failed")
        _raise_rag_http_error(exc)


@app.delete("/api/rag/documents/{document_id}")
async def delete_rag_document(
    document_id: str,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    try:
        await asyncio.to_thread(rag_service.delete_document, current[1], document_id)
        return {"message": "Knowledge-base document deleted."}
    except Exception as exc:
        _raise_rag_http_error(exc)


@app.post("/api/rag/query")
async def query_rag_sources(
    req: RagChatRequest,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    question = req.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty question.")
    try:
        results = await asyncio.to_thread(
            rag_service.retrieve, current[1], question, req.collection_id, req.top_k
        )
        return {
            "query": question,
            "result_count": len(results),
            "sources": [result.source_dict() for result in results],
        }
    except Exception as exc:
        _raise_rag_http_error(exc)


async def _rag_stream(
    session_id: str,
    question: str,
    results: list,
    routing_decision=None,
) -> AsyncGenerator[str, None]:
    if routing_decision:
        yield _sse({"type": "routing", "routing": routing_decision.to_dict()})
    if not results:
        yield _sse({"type": "sources", "sources": []})
        yield _sse({"type": "error", "error": "The available indexed documents do not provide sufficient evidence."})
        return
    yield _sse({"type": "sources", "sources": [result.source_dict() for result in results]})
    prompt = rag_service.build_prompt(question, results)
    async for event in _model_stream(
        session_id,
        AppMode.KNOWLEDGE_CHAT,
        question,
        prompt,
        "rag_chat",
        system_prompt=RAG_SYSTEM_PROMPT,
        model_name=routing_decision.model_name if routing_decision else capability_registry.get(CapabilityId.KNOWLEDGE_RAG).model_name,
        routing_decision=None,
    ):
        yield event


@app.post("/api/rag/chat")
async def rag_chat(
    req: RagChatRequest,
    current: tuple[str, str, str, UserRole, UserModel] = Depends(require_authenticated_user),
):
    question = req.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty question.")
    try:
        decision = capability_router.route(
            RoutingContext(
                current[1], current[3].value, "Knowledge Chat", None,
                req.collection_id, question, bool(rag_service.config.enabled),
            )
        )
    except Exception as exc:
        _route_http_error(exc)
    try:
        results = await asyncio.to_thread(
            rag_service.retrieve, current[1], question, req.collection_id, req.top_k
        )
    except Exception as exc:
        _raise_rag_http_error(exc)
    if not results:
        if req.stream:
            return StreamingResponse(
                _rag_stream(current[0], question, results, decision),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
            )
        return {
            "content": "The available indexed documents do not provide sufficient evidence.",
            "latency_seconds": 0.0,
            "model": decision.model_name,
            "sources": [],
            "routing": decision.to_dict(),
        }
    prompt = rag_service.build_prompt(question, results)
    if not req.stream:
        result = await _non_stream_chat(
            current[0], AppMode.KNOWLEDGE_CHAT, question, prompt, "rag_chat",
            model_name=decision.model_name,
        )
        result["sources"] = [item.source_dict() for item in results]
        result["routing"] = decision.to_dict()
        return result
    return StreamingResponse(
        _rag_stream(current[0], question, results, decision),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


STATIC_DIR = PROJECT_ROOT / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>SIH Local AI Workbench Server is Running</h1>")

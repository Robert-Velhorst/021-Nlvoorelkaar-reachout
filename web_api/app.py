"""FastAPI transport over the shared application service."""

from __future__ import annotations

import hmac
import os
import sys
import tempfile
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from services.application_service import ApplicationService
from services.data_management import DataImporter


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class CampaignInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    target_categories: str = Field(default="", max_length=500)
    target_location: str = Field(default="", max_length=200)
    target_distance: Optional[int] = Field(default=None, ge=0, le=500)
    message_template: str = Field(min_length=1, max_length=20000)


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    volunteer_ids: Optional[list[str]] = Field(default=None, max_length=500)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: str = Field(min_length=3, max_length=4000)


class ResponseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    volunteer_id: str = Field(min_length=1, max_length=200)
    campaign_id: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=200000)


class SafetyStopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool


class _RateLimiter:
    def __init__(self, limit: int = 180, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._requests[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            bucket.append(now)
            if len(self._requests) > 2048:
                stale = [name for name, values in self._requests.items() if not values or values[-1] < cutoff]
                for name in stale:
                    self._requests.pop(name, None)


def _static_root() -> Path:
    frozen_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return frozen_root / "web_api" / "static"


def _configured_token(explicit_token: Optional[str]) -> str:
    token = explicit_token if explicit_token is not None else os.environ.get("NLVE_WEB_API_TOKEN", "")
    token = token.strip()
    if len(token) < 32:
        raise RuntimeError("NLVE_WEB_API_TOKEN must contain at least 32 characters")
    return token


def create_app(
    service: Optional[ApplicationService] = None,
    *,
    api_token: Optional[str] = None,
    static_root: Optional[Path] = None,
) -> FastAPI:
    """Build an authenticated single-process API over SQLite-backed use cases."""
    expected_token = _configured_token(api_token)
    application = service or ApplicationService()
    limiter = _RateLimiter()
    write_limiter = _RateLimiter(limit=45)
    app = FastAPI(
        title="NLvoorelkaar Reachout",
        version="3.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    trusted_hosts = [
        item.strip()
        for item in os.environ.get(
            "NLVE_WEB_TRUSTED_HOSTS",
            "localhost,127.0.0.1,testserver",
        ).split(",")
        if item.strip()
    ]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    @app.middleware("http")
    async def secure_headers(request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        try:
            limiter.check(client)
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                write_limiter.check(client)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": "rate_limited", "message": str(exc.detail)}},
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Request validation failed", "details": exc.errors()}},
        )

    @app.exception_handler(ValueError)
    async def value_error(_request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "invalid_operation", "message": str(exc)}},
        )

    @app.exception_handler(RuntimeError)
    async def runtime_error(_request: Request, exc: RuntimeError):
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "operation_blocked", "message": str(exc)}},
        )

    def require_auth(authorization: Annotated[Optional[str], Header()] = None) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication required",
            )
        supplied = authorization[7:].strip()
        if not hmac.compare_digest(supplied.encode("utf-8"), expected_token.encode("utf-8")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

    authenticated = Depends(require_auth)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/status", dependencies=[authenticated])
    def get_status() -> dict[str, Any]:
        return application.status()

    @app.get("/api/v1/dashboard", dependencies=[authenticated])
    def dashboard() -> dict[str, Any]:
        return application.dashboard()

    @app.get("/api/v1/volunteers", dependencies=[authenticated])
    def volunteers(limit: int = 100, offset: int = 0) -> dict[str, Any]:
        if not 1 <= limit <= 500 or offset < 0:
            raise HTTPException(status_code=400, detail="Invalid pagination")
        return {"items": application.list_volunteers(limit=limit, offset=offset), "limit": limit, "offset": offset}

    @app.post("/api/v1/volunteers/import", dependencies=[authenticated])
    async def import_volunteers(file: Annotated[UploadFile, File()]) -> dict[str, int]:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".csv", ".json"}:
            raise HTTPException(status_code=400, detail="Only CSV or JSON candidate files are accepted")
        payload = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Candidate file exceeds 5 MiB")
        with tempfile.TemporaryDirectory(prefix="nlve-web-import-") as temp_dir:
            source = Path(temp_dir) / f"candidates{suffix}"
            source.write_bytes(payload)
            return DataImporter(application.database.db_path).import_volunteers(str(source))

    @app.get("/api/v1/campaigns", dependencies=[authenticated])
    def campaigns() -> dict[str, Any]:
        return {"items": application.list_campaigns()}

    @app.post("/api/v1/campaigns", dependencies=[authenticated], status_code=201)
    def create_campaign(payload: CampaignInput) -> dict[str, int]:
        return {"id": application.create_campaign(payload.model_dump())}

    @app.post("/api/v1/campaigns/{campaign_id}/drafts", dependencies=[authenticated])
    def create_drafts(campaign_id: int, payload: DraftInput) -> dict[str, Any]:
        return {"ids": application.create_drafts(campaign_id, payload.volunteer_ids)}

    @app.get("/api/v1/messages/review", dependencies=[authenticated])
    def message_review(limit: int = 100) -> dict[str, Any]:
        return {"items": application.review_queue(limit=min(max(limit, 1), 500))}

    @app.get("/api/v1/messages", dependencies=[authenticated])
    def messages(message_status: str = "approved", limit: int = 100) -> dict[str, Any]:
        return {
            "items": application.message_drafts(
                message_status,
                limit=min(max(limit, 1), 500),
            )
        }

    @app.post("/api/v1/messages/{draft_id}/approve", dependencies=[authenticated])
    def approve_message(draft_id: int, payload: DecisionInput) -> dict[str, int]:
        return {"approval_id": application.approve_message(draft_id, payload.reason)}

    @app.post("/api/v1/messages/{draft_id}/reject", dependencies=[authenticated])
    def reject_message(draft_id: int, payload: DecisionInput) -> dict[str, int]:
        return {"approval_id": application.reject_message(draft_id, payload.reason)}

    @app.post("/api/v1/messages/{draft_id}/confirm-manual-send", dependencies=[authenticated])
    def confirm_send(draft_id: int, payload: EvidenceInput) -> dict[str, int]:
        return {"attempt_id": application.confirm_manual_send(draft_id, payload.evidence)}

    @app.get("/api/v1/responses", dependencies=[authenticated])
    def responses(limit: int = 100) -> dict[str, Any]:
        return {"items": application.responses(limit=min(max(limit, 1), 500))}

    @app.post("/api/v1/responses", dependencies=[authenticated], status_code=201)
    def record_response(payload: ResponseInput) -> dict[str, int]:
        return {"id": application.record_response(**payload.model_dump())}

    @app.get("/api/v1/follow-ups", dependencies=[authenticated])
    def follow_ups(limit: int = 100) -> dict[str, Any]:
        return {"items": application.follow_ups(limit=min(max(limit, 1), 500))}

    @app.post("/api/v1/follow-ups/{follow_up_id}/approve", dependencies=[authenticated])
    def approve_follow_up(follow_up_id: int) -> dict[str, bool]:
        return {"approved": application.approve_follow_up(follow_up_id)}

    @app.post("/api/v1/follow-ups/{follow_up_id}/confirm-manual-send", dependencies=[authenticated])
    def confirm_follow_up(follow_up_id: int, payload: EvidenceInput) -> dict[str, int]:
        return {"attempt_id": application.confirm_follow_up(follow_up_id, payload.evidence)}

    @app.get("/api/v1/privacy/retention", dependencies=[authenticated])
    def privacy_retention(days: int = 365, limit: int = 100) -> dict[str, Any]:
        if not 30 <= days <= 3650:
            raise HTTPException(status_code=400, detail="days must be between 30 and 3650")
        return {"items": application.privacy_candidates(days=days, limit=min(max(limit, 1), 500))}

    @app.post("/api/v1/privacy/retention/{volunteer_id}/archive", dependencies=[authenticated])
    def archive_volunteer(volunteer_id: str, payload: DecisionInput) -> dict[str, bool]:
        application.archive_volunteer(volunteer_id, payload.reason)
        return {"archived": True}

    @app.post("/api/v1/privacy/retention/{volunteer_id}/redact", dependencies=[authenticated])
    def redact_volunteer(volunteer_id: str, payload: DecisionInput) -> dict[str, bool]:
        application.redact_volunteer(volunteer_id, payload.reason)
        return {"redacted": True}

    @app.put("/api/v1/operations/safety-stop", dependencies=[authenticated])
    def safety_stop(payload: SafetyStopInput) -> dict[str, bool]:
        application.set_safety_stop(payload.active)
        return {"active": application.safety_stop_active()}

    @app.get("/api/v1/hai/feed", dependencies=[authenticated])
    def hai_feed(limit: int = 100) -> dict[str, Any]:
        return application.hai_feed(limit=min(max(limit, 1), 500))

    assets = (Path(static_root) if static_root is not None else _static_root()).resolve()
    index_file = (assets / "index.html").resolve()
    asset_directory = (assets / "assets").resolve()
    if assets.is_dir() and index_file.is_file() and asset_directory.is_dir():
        app.mount("/assets", StaticFiles(directory=asset_directory), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            del path
            return FileResponse(index_file)
    else:
        @app.get("/", include_in_schema=False)
        def frontend_missing():
            return JSONResponse(
                status_code=503,
                content={"error": {"code": "frontend_not_built", "message": "Run the web frontend build first"}},
            )

    return app

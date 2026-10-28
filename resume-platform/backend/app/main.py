"""FastAPI application factory."""

from __future__ import annotations

import hmac

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.core.security import UnsafeURLError, UploadError, configure_logging
from app.db import init_db
from app.ingest.github import GitHubError
from app.ingest.url_fetch import FetchError
from app.llm.base import LLMError, LLMNotConfigured
from app.services.profiles import NotFound


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    settings.ensure_dirs()
    init_db()
    docs = settings.expose_docs
    app = FastAPI(title="Resume Intelligence Platform", version=__version__,
                  description="Evidence-based resume tailoring, matching and validation. Local-first.",
                  docs_url="/docs" if docs else None, redoc_url="/redoc" if docs else None,
                  openapi_url="/openapi.json" if docs else None)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["*"])

    @app.middleware("http")
    async def auth_and_headers(request: Request, call_next):
        token = settings.api_token.get_secret_value() if settings.api_token else None
        protected = request.url.path.startswith("/api") and request.url.path != "/api/health" \
            and request.method != "OPTIONS"
        if protected and settings.missing_database:
            return JSONResponse({"detail": "This server needs DATABASE_URL (PostgreSQL); local files are not kept."},
                                status_code=503)
        if protected and not token and settings.require_token:
            return JSONResponse({"detail": "This server requires RIP_API_TOKEN to be configured."}, status_code=503)
        if token and protected:
            header = request.headers.get("authorization", "")
            supplied = header[7:] if header.lower().startswith("bearer ") else request.query_params.get("token", "")
            if not hmac.compare_digest(supplied.encode(), token.encode()):
                return JSONResponse({"detail": "Missing or invalid API token."}, status_code=401)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    def _err(status: int):
        async def handler(_request: Request, exc: Exception):
            return JSONResponse({"detail": str(exc)}, status_code=status)
        return handler

    app.add_exception_handler(NotFound, _err(404))
    app.add_exception_handler(UploadError, _err(400))
    app.add_exception_handler(UnsafeURLError, _err(400))
    app.add_exception_handler(FetchError, _err(422))
    app.add_exception_handler(GitHubError, _err(422))
    app.add_exception_handler(LLMNotConfigured, _err(409))
    app.add_exception_handler(LLMError, _err(502))
    app.add_exception_handler(ValueError, _err(400))
    app.add_exception_handler(PermissionError, _err(403))
    app.add_exception_handler(FileNotFoundError, _err(404))

    from app.api import routes_jobs, routes_profile, routes_resumes, routes_system

    for r in (routes_system.router, routes_profile.router, routes_jobs.router, routes_resumes.router):
        app.include_router(r)
    return app


app = create_app()

"""FastAPI application entrypoint."""
import asyncio
import sys
import uuid

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

logger = structlog.get_logger()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Binds a unique correlation ID per request to structlog context."""
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=correlation_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response


app = FastAPI(
    title="AgentShield",
    description="Security gateway for AI agents",
    version="0.1.0",
    docs_url="/docs" if settings.API_DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.API_DOCS_ENABLED else None,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    # Use an explicit regex only when CORS_ALLOWED_REGEX is set in .env
    # Never use a wildcard pattern like "https://.*\.vercel\.app" with allow_credentials=True
    # as it trusts every Vercel app, not just yours.
    allow_origin_regex=settings.CORS_ALLOWED_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {"service": "agentshield", "status": "ok", "version": "0.1.0"}
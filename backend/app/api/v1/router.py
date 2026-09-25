"""Aggregates every v1 sub-router under a single /api/v1 prefix."""
from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.agents import router as agents_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.policies import router as policies_router
from app.api.v1.audit import router as audit_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.kill_switch import router as kill_switch_router
from app.demo.interactive_routes import router as interactive_agent_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(agents_router)
api_router.include_router(decisions_router)
api_router.include_router(policies_router)
api_router.include_router(audit_router)
api_router.include_router(approvals_router)
api_router.include_router(kill_switch_router)
api_router.include_router(interactive_agent_router)
"""Route-auth coverage test.

Iterates every registered FastAPI route and asserts that it is either on
an explicit allowlist (open endpoints like /health, demo-gated endpoints,
and the token exchange) OR has at least one dependency that resolves to an
authenticated principal (get_current_agent or get_optional_agent).

A failing test means you added an endpoint without auth — it must either
be added to OPEN_ROUTES below (with a comment explaining why) or wired to
get_current_agent.
"""
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.main import app
from app.core.deps import get_current_agent, get_optional_agent


# Routes that are intentionally open (no auth required).
# Format: (method, path)  — exact match.
OPEN_ROUTES: set[tuple[str, str]] = {
    # Root ping endpoint
    ("GET", "/"),
    # Health check — must be open for load-balancer probes
    ("GET", "/api/v1/health"),
    # Token exchange — takes an API key, cannot require a JWT first
    ("POST", "/api/v1/agents/token"),
    # Open registration — only works when DEMO_MODE=true (checked at runtime)
    ("POST", "/api/v1/tenants"),
    ("POST", "/api/v1/agents"),
    # OpenAPI / docs — gated by settings.API_DOCS_ENABLED at startup
    ("GET", "/docs"),
    ("GET", "/openapi.json"),
    ("GET", "/redoc"),
}


def _has_auth_dep(route: APIRoute) -> bool:
    """Return True if the route has get_current_agent or get_optional_agent as a dependency."""
    for dep in route.dependencies:
        if dep.dependency in (get_current_agent, get_optional_agent):
            return True
    # Also check endpoint function's own parameter defaults
    import inspect
    try:
        sig = inspect.signature(route.endpoint)
    except (ValueError, TypeError):
        return False
    for param in sig.parameters.values():
        if param.default is not inspect.Parameter.empty:
            dep_callable = getattr(param.default, "dependency", None)
            if dep_callable in (get_current_agent, get_optional_agent):
                return True
    return False


def _route_key(route: APIRoute) -> set[tuple[str, str]]:
    keys = set()
    for method in route.methods or []:
        keys.add((method.upper(), route.path))
    return keys


def test_all_routes_have_auth_or_allowlisted():
    """Every API route must be authenticated or explicitly allowlisted."""
    failures = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or []:
            key = (method.upper(), route.path)
            if key in OPEN_ROUTES:
                continue
            if not _has_auth_dep(route):
                failures.append(f"{method} {route.path}")

    assert not failures, (
        "The following routes have no auth dependency and are not on the allowlist:\n"
        + "\n".join(f"  - {r}" for r in sorted(failures))
        + "\n\nAdd get_current_agent as a dependency or add the route to OPEN_ROUTES "
        "in test_route_auth.py with a justification comment."
    )

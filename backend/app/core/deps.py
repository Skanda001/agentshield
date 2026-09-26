"""Shared FastAPI dependencies."""
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_agent_token
from app.db.models.agent import Agent
from app.db.session import AsyncSessionLocal


# Declares a security scheme so Swagger UI shows the "Authorize" button.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_agent(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """Resolve the calling agent from the Authorization: Bearer <JWT> header."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_agent_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    agent_id = payload.get("sub")
    if not agent_id:
        raise HTTPException(status_code=401, detail="Token missing subject")

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=401, detail="Agent not found")
    if agent.status != "active" or not agent.is_active:
        raise HTTPException(status_code=403, detail="Agent is not active")

    return agent


async def get_optional_agent(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[Agent]:
    """Resolve calling agent if token provided; returns fallback agent or None if not."""
    if credentials and credentials.scheme.lower() == "bearer":
        payload = decode_agent_token(credentials.credentials)
        if payload and payload.get("sub"):
            result = await db.execute(select(Agent).where(Agent.id == payload["sub"]))
            agent = result.scalar_one_or_none()
            if agent:
                return agent

    # Fallback to first active agent in DB for testing convenience
    result = await db.execute(select(Agent).where(Agent.is_active == True).limit(1))
    return result.scalar_one_or_none()
"""Agent Plugins & Dynamic Lifecycle API.

Enables dynamic "Plug In" and "Plug Out" of external AI agents directly from the UI.
When an agent is plugged in, its code physically enters the AgentShield directory
(`agentshield/plugged_agents/<agent_id>/`) and is activated on the security gateway.
When plugged out, it physically leaves the directory and its credentials are revoked.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import chain as audit_chain
from app.core.config import settings
from app.core.deps import get_current_agent, get_optional_agent, get_db
from app.core.security import create_agent_token, generate_api_key, hash_api_key
from app.db.models.agent import Agent
from app.db.models.tenant import Tenant
from app.demo.bus import bus

logger = logging.getLogger("agentshield.plugins")
router = APIRouter(tags=["plugins"])

# Resolution of paths
# backend/app/api/v1/plugins.py -> backend root -> agentshield root
AGENTSHIELD_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
PLUGGED_AGENTS_DIR = AGENTSHIELD_ROOT / "plugged_agents"

# External agents folder resides completely outside agentshield:
# C:\Users\bsska\OneDrive\Desktop\Resume Projects\external-agents
EXTERNAL_AGENTS_DIR = Path(
    os.getenv("EXTERNAL_AGENTS_DIR", str(AGENTSHIELD_ROOT.parent / "external-agents"))
).resolve()


class ToolManifest(BaseModel):
    name: str
    classification: str = "internal"
    risk_level: str = "low"
    requires_hitl: bool = False
    blocked_by_default: bool = False


class AgentPluginInfo(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    category: str = "General"
    description: str
    author: str = "External Contributor"
    entrypoint: str = "agent.py"
    icon: str = "bot"
    scopes: list[str] = Field(default_factory=list)
    tools: list[ToolManifest] = Field(default_factory=list)
    is_plugged_in: bool = False
    mount_path: Optional[str] = None
    status: str = "unplugged"
    external_path: str
    last_action_at: Optional[str] = None
    token: Optional[str] = None


class PlugActionResponse(BaseModel):
    ok: bool
    agent_id: str
    is_plugged_in: bool
    mount_path: Optional[str] = None
    message: str
    plugin: AgentPluginInfo


class PluginRunRequest(BaseModel):
    agent_id: str
    prompt: str = Field(min_length=1, max_length=2000)
    run_id: Optional[str] = None
    auto_approve: bool = False


class PluginRunResponse(BaseModel):
    run_id: str
    agent_id: str
    prompt: str
    events: list[dict[str, Any]]
    final_text: str
    verdict: str
    status: str


def safe_rmtree(path: Path) -> None:
    """Robust directory removal that handles Windows file locking and read-only attributes."""
    if not path.exists():
        return
    import gc
    import stat
    gc.collect()

    for root, dirs, files in os.walk(str(path), topdown=False):
        for f in files:
            fp = os.path.join(root, f)
            try:
                os.chmod(fp, stat.S_IWRITE)
                os.remove(fp)
            except Exception:
                pass
        for d in dirs:
            dp = os.path.join(root, d)
            try:
                os.chmod(dp, stat.S_IWRITE)
                os.rmdir(dp)
            except Exception:
                pass

    try:
        os.rmdir(str(path))
    except Exception:
        if sys.platform == "win32":
            import subprocess
            subprocess.run(f'rd /s /q "{str(path)}"', shell=True, capture_output=True)


def _get_agent_info(agent_dir: Path, is_plugged_in: bool) -> AgentPluginInfo:
    manifest_file = agent_dir / "manifest.json"
    data: dict[str, Any] = {}
    if manifest_file.exists():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Error reading manifest for %s: %s", agent_dir.name, e)

    agent_id = data.get("id") or agent_dir.name
    tools = [ToolManifest(**t) for t in data.get("tools", [])]

    return AgentPluginInfo(
        id=agent_id,
        name=data.get("name", agent_id.replace("-", " ").title()),
        version=data.get("version", "1.0.0"),
        category=data.get("category", "General AI"),
        description=data.get("description", "External autonomous agent"),
        author=data.get("author", "External Developer"),
        entrypoint=data.get("entrypoint", "agent.py"),
        icon=data.get("icon", "bot"),
        scopes=data.get("scopes", ["read:customer", "read:order"]),
        tools=tools,
        is_plugged_in=is_plugged_in,
        mount_path=f"plugged_agents/{agent_id}" if is_plugged_in else None,
        status="plugged_in" if is_plugged_in else "unplugged",
        external_path=str(agent_dir),
    )


@router.get("/plugins", response_model=list[AgentPluginInfo])
async def list_plugins():
    """List all external agents available in the ecosystem and their plugged-in status."""
    PLUGGED_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[AgentPluginInfo] = []
    seen_ids: set[str] = set()

    # 1. Discover all agents in external-agents directory
    if EXTERNAL_AGENTS_DIR.exists() and EXTERNAL_AGENTS_DIR.is_dir():
        for item in EXTERNAL_AGENTS_DIR.iterdir():
            if item.is_dir() and not item.name.startswith(".") and "copy" not in item.name.lower():
                is_mounted = (PLUGGED_AGENTS_DIR / item.name).exists()
                info = _get_agent_info(item, is_plugged_in=is_mounted)
                if info.id not in seen_ids:
                    results.append(info)
                    seen_ids.add(info.id)

    # 2. Check any plugged agents that might not be in external-agents dir
    for item in PLUGGED_AGENTS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith(".") and "copy" not in item.name.lower():
            is_mounted = True
            info = _get_agent_info(item, is_plugged_in=is_mounted)
            if info.id not in seen_ids:
                results.append(info)
                seen_ids.add(info.id)

    return results


@router.post("/plugins/{agent_id}/plugin", response_model=PlugActionResponse)
async def plug_in_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Optional[Agent] = Depends(get_optional_agent),
):
    """Mount external agent into `agentshield/plugged_agents/<agent_id>`, activating it on the gateway."""
    src_dir = EXTERNAL_AGENTS_DIR / agent_id
    if not src_dir.exists() or not src_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"External agent '{agent_id}' not found in {EXTERNAL_AGENTS_DIR}",
        )

    PLUGGED_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = PLUGGED_AGENTS_DIR / agent_id

    # Physical Mount: copy directory into agentshield/plugged_agents/
    if target_dir.exists():
        safe_rmtree(target_dir)
    shutil.copytree(src_dir, target_dir)

    # Also ensure standalone shield SDK is present in the target directory
    sdk_src = EXTERNAL_AGENTS_DIR / "shield.py"
    if sdk_src.exists():
        shutil.copy2(sdk_src, target_dir / "shield.py")

    info = _get_agent_info(src_dir, is_plugged_in=True)

    # Determine tenant
    if current_agent:
        tenant_id = current_agent.tenant_id
    else:
        tenant_res = await db.execute(select(Tenant.id).limit(1))
        tenant_id = tenant_res.scalar_one_or_none()
        if not tenant_id:
            new_tenant = Tenant(name="Default Tenant", slug="default-tenant")
            db.add(new_tenant)
            await db.commit()
            await db.refresh(new_tenant)
            tenant_id = new_tenant.id

    # Register / Activate in database for this tenant
    res = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.name == info.name,
        )
    )
    db_agent = res.scalar_one_or_none()

    if db_agent:
        db_agent.status = "active"
        db_agent.is_active = True
        db_agent.scopes = info.scopes
    else:
        raw_key = generate_api_key()
        db_agent = Agent(
            tenant_id=tenant_id,
            name=info.name,
            description=info.description,
            api_key_hash=hash_api_key(raw_key),
            scopes=info.scopes,
            role="support",
            status="active",
            is_active=True,
        )
        db.add(db_agent)

    await db.commit()
    await db.refresh(db_agent)

    # Issue active token
    agent_token = create_agent_token(
        agent_id=str(db_agent.id),
        tenant_id=str(db_agent.tenant_id),
        scopes=db_agent.scopes,
    )
    info.token = agent_token

    # Record tamper-evident audit event
    await audit_chain.append_event(
        db,
        event_type="agent.plugged_in",
        payload={
            "agent_id": agent_id,
            "name": info.name,
            "mount_path": f"plugged_agents/{agent_id}",
            "external_source": str(src_dir),
            "scopes": info.scopes,
        },
        agent_id=db_agent.id,
        tenant_id=current_agent.tenant_id,
        note=f"Agent '{info.name}' physically mounted into plugged_agents/{agent_id}",
    )

    logger.info("Successfully plugged in agent %s to %s", agent_id, target_dir)

    return PlugActionResponse(
        ok=True,
        agent_id=agent_id,
        is_plugged_in=True,
        mount_path=f"plugged_agents/{agent_id}",
        message=f"Agent '{info.name}' successfully mounted into ./plugged_agents/{agent_id} and activated on gateway.",
        plugin=info,
    )


@router.post("/plugins/{agent_id}/plugout", response_model=PlugActionResponse)
async def plug_out_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Optional[Agent] = Depends(get_optional_agent),
):
    """Unmount agent from `agentshield/plugged_agents/<agent_id>`, deleting the folder and revoking gateway access."""
    target_dir = PLUGGED_AGENTS_DIR / agent_id
    src_dir = EXTERNAL_AGENTS_DIR / agent_id

    # Physical Unmount: remove directory from agentshield/plugged_agents/
    if target_dir.exists():
        safe_rmtree(target_dir)

    ref_dir = src_dir if src_dir.exists() else target_dir
    info = _get_agent_info(ref_dir, is_plugged_in=False)

    # Deactivate in database
    tenant_id = current_agent.tenant_id if current_agent else None
    query = select(Agent).where(Agent.name == info.name)
    if tenant_id:
        query = query.where(Agent.tenant_id == tenant_id)
    res = await db.execute(query)
    db_agent = res.scalar_one_or_none()
    if db_agent:
        db_agent.status = "unplugged"
        db_agent.is_active = False
        await db.commit()

    # Record tamper-evident audit event
    await audit_chain.append_event(
        db,
        event_type="agent.plugged_out",
        payload={
            "agent_id": agent_id,
            "name": info.name,
            "unmounted_path": f"plugged_agents/{agent_id}",
        },
        agent_id=db_agent.id if db_agent else None,
        tenant_id=db_agent.tenant_id if db_agent else tenant_id,
        note=f"Agent '{info.name}' physically unmounted and removed from plugged_agents/{agent_id}",
    )

    logger.info("Successfully plugged out agent %s", agent_id)

    return PlugActionResponse(
        ok=True,
        agent_id=agent_id,
        is_plugged_in=False,
        mount_path=None,
        message=f"Agent '{info.name}' unmounted and removed from gateway. Execution disabled.",
        plugin=info,
    )


@router.post("/plugins/run", response_model=PluginRunResponse)
async def run_plugin_agent(
    payload: PluginRunRequest,
    _current_agent: Optional[Agent] = Depends(get_optional_agent),
):
    """Execute a plugged-in agent against a prompt with live event streaming."""
    target_dir = PLUGGED_AGENTS_DIR / payload.agent_id

    # Strict physical mount check
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Agent '{payload.agent_id}' is UNPLUGGED. It does not exist in './plugged_agents/{payload.agent_id}'. "
                f"Please plug in this agent through the Agent Hub UI before running."
            ),
        )

    entrypoint = target_dir / "agent.py"
    if not entrypoint.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Plugged agent '{payload.agent_id}' missing entrypoint 'agent.py'.",
        )

    run_id = payload.run_id or str(uuid.uuid4())
    collected_events: list[dict[str, Any]] = []

    # 1. Stream step event: Intent started
    start_event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "agent_id": payload.agent_id,
        "step": 1,
        "tool": "agent.reason",
        "decision": "ALLOW",
        "risk": {"score": 5, "model_version": "AgentShield-Gateway"},
        "findings": [],
        "execution": {"attempted": True, "executed": True},
        "args": {"prompt": payload.prompt},
        "text": f"Agent '{payload.agent_id}' analyzing prompt: \"{payload.prompt}\"",
    }
    collected_events.append(start_event)
    await bus.publish(run_id, start_event)

    # 2. Dynamic module loader from the physical plugged_agents folder
    try:
        spec = importlib.util.spec_from_file_location(
            f"plugged_{payload.agent_id.replace('-', '_')}",
            entrypoint,
        )
        if not spec or not spec.loader:
            raise RuntimeError("Could not construct module spec for plugged agent.")

        # Ensure plugged directory is in sys.path temporarily so internal relative imports work
        str_target = str(target_dir)
        if str_target not in sys.path:
            sys.path.insert(0, str_target)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Identify agent class
        agent_cls = None
        for attr in dir(module):
            val = getattr(module, attr)
            if isinstance(val, type) and hasattr(val, "run") and attr != "ShieldClient":
                agent_cls = val
                break

        if not agent_cls:
            raise RuntimeError(f"No agent class with run() method found in {entrypoint}")

        agent_instance = agent_cls()

        # Run synchronously or in thread pool to prevent blocking asyncio loop
        run_res = await asyncio.to_thread(
            agent_instance.run,
            payload.prompt,
            auto_approve=payload.auto_approve,
        )

    except Exception as e:
        logger.exception("Error executing plugged agent %s: %s", payload.agent_id, e)
        error_event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "agent_id": payload.agent_id,
            "step": 2,
            "tool": "agent.error",
            "decision": "BLOCK",
            "risk": {"score": 100, "model_version": "AgentShield-Gateway"},
            "execution": {"attempted": True, "executed": False},
            "error": str(e),
            "text": f"Execution error in plugged agent '{payload.agent_id}': {e}",
        }
        collected_events.append(error_event)
        await bus.publish(run_id, error_event)
        await bus.close(run_id)
        return PluginRunResponse(
            run_id=run_id,
            agent_id=payload.agent_id,
            prompt=payload.prompt,
            events=collected_events,
            final_text=str(e),
            verdict="BLOCK",
            status="error",
        )

    # 3. Stream execution step event
    verdict = run_res.get("verdict", "ALLOW")
    tool_name = run_res.get("tool", "tool_call")
    tool_event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "agent_id": payload.agent_id,
        "step": 2,
        "tool": tool_name,
        "args": run_res.get("args", {}),
        "decision": verdict,
        "risk": {
            "score": run_res.get("risk_score", 15 if verdict == "ALLOW" else (50 if verdict == "HITL" else 100)),
            "model_version": "AgentShield-Gateway",
        },
        "findings": [{"type": "policy-check", "verdict": verdict}],
        "execution": {
            "attempted": True,
            "executed": verdict == "ALLOW" or run_res.get("status") == "escalated_and_approved",
        },
        "audit_id": run_res.get("approval_id") or str(uuid.uuid4()),
        "output": run_res.get("output"),
        "approval_id": run_res.get("approval_id"),
        "error": run_res.get("reason"),
        "text": run_res.get("text", ""),
    }
    collected_events.append(tool_event)
    await bus.publish(run_id, tool_event)

    # 4. Stream final answer
    final_event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "agent_id": payload.agent_id,
        "step": 3,
        "tool": "agent.final",
        "decision": verdict,
        "risk": {"score": 0, "model_version": "AgentShield-Gateway"},
        "findings": [],
        "execution": {"attempted": False, "executed": False},
        "text": run_res.get("text", "Execution completed."),
    }
    collected_events.append(final_event)
    await bus.publish(run_id, final_event)
    await bus.close(run_id)

    return PluginRunResponse(
        run_id=run_id,
        agent_id=payload.agent_id,
        prompt=payload.prompt,
        events=collected_events,
        final_text=run_res.get("text", ""),
        verdict=verdict,
        status=run_res.get("status", "completed"),
    )

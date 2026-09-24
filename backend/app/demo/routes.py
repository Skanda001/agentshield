"""HTTP + WebSocket routes for the AgentShield demo.

Endpoints:
  GET  /api/v1/demo/scenarios          — list available replay scenarios
  POST /api/v1/demo/run                — run a scenario over HTTP, return all events
  WS   /api/v1/demo/ws?run_id=...&token=...  — subscribe to a live run

The WebSocket streams events as they're produced. Events have the shape
defined in demo_agent/events.py (the richer one with findings + execution).

Live-stream flow (correct order — avoids the race):
  1. Client picks a run_id (uuid)
  2. Client opens WS  /api/v1/demo/ws?run_id=<id>&token=<jwt>
  3. Client POSTs     /api/v1/demo/run  { run_id: <id>, ... }
  4. Server publishes each event to the bus as it fires
  5. WS delivers events live; terminal {"__done__": true} closes the loop
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

from app.core.deps import get_current_agent
from app.core.security import decode_agent_token
from app.demo.bus import bus
from app.db.models.agent import Agent
from demo_agent.support_agent import SCENARIOS, run_replay, run_live

logger = logging.getLogger(__name__)
router = APIRouter(tags=["demo"])


# ─── Schemas ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    scenario: str = Field(
        description="Replay scenario name (normal/pii/destructive/injection)"
    )
    mode: str = Field(default="replay", pattern=r"^(replay|live)$")
    prompt: str | None = Field(default=None, description="Required if mode=live")
    run_id: str | None = Field(
        default=None,
        description="Optional — client-generated run_id for WS correlation. "
                    "If omitted, the agent generates one.",
    )


class ScenarioOut(BaseModel):
    name: str
    description: str
    steps: int


class RunResponse(BaseModel):
    run_id: str
    mode: str
    scenario: str | None
    events: list[dict[str, Any]]


# ─── HTTP: list scenarios ────────────────────────────────────

@router.get("/demo/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(_agent: Agent = Depends(get_current_agent)):
    return [
        ScenarioOut(
            name=name,
            description=body["description"],
            steps=len(body["steps"]),
        )
        for name, body in SCENARIOS.items()
    ]


# ─── HTTP: run and return all events (no WS) ─────────────────

@router.post("/demo/run", response_model=RunResponse)
async def run(
    payload: RunRequest,
    _agent: Agent = Depends(get_current_agent),
):
    """Run a scenario.

    Two things happen in parallel:
      * events are published to the bus (for any subscribed WebSocket)
      * events are collected locally and returned in the HTTP response

    If the caller supplies run_id, the bus publishes under that id so a
    WS that connected *before* this call will receive the events live.
    """
    collected: list[dict[str, Any]] = []
    run_id_holder: dict[str, str] = {}
    if payload.run_id:
        run_id_holder["run_id"] = payload.run_id

    async def _emit(ev: dict[str, Any]) -> None:
        collected.append(ev)
        rid = ev.get("run_id")
        if rid:
            run_id_holder["run_id"] = rid
            await bus.publish(rid, ev)

    if payload.mode == "replay":
        await run_replay(payload.scenario, _emit, run_id=payload.run_id)
    else:
        if not payload.prompt:
            raise HTTPException(400, "prompt is required when mode=live")
        await run_live(payload.prompt, _emit, run_id=payload.run_id)

    run_id = run_id_holder.get("run_id") or "unknown"
    await bus.close(run_id)

    return RunResponse(
        run_id=run_id,
        mode=payload.mode,
        scenario=payload.scenario if payload.mode == "replay" else None,
        events=collected,
    )


# ─── WebSocket: subscribe to a run ───────────────────────────

@router.websocket("/demo/ws")
async def demo_ws(
    websocket: WebSocket,
    run_id: str = Query(..., description="Client-chosen run_id"),
    token: str = Query(..., description="agent JWT — WS can't carry Authorization headers"),
):
    """Subscribe to the live event stream for a run.

    Correct ordering for a live demo:
      1. Generate run_id client-side
      2. Connect here with that run_id + a valid JWT
      3. POST /api/v1/demo/run with { run_id, scenario, mode }

    Events arrive as JSON, one per frame. A terminal {"__done__": true}
    frame signals completion. Bad token → 4401 close code.
    """
    payload = decode_agent_token(token)
    if not payload:
        await websocket.close(code=4401, reason="invalid token")
        return

    await websocket.accept()

    q = await bus.subscribe(run_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"__ping__": True}))
                continue

            if event.get("__done__"):
                await websocket.send_text(json.dumps({"__done__": True}))
                break

            await websocket.send_text(json.dumps(event, default=str))

    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        logger.exception("demo.ws.error: %s", e)
    finally:
        await bus.unsubscribe(run_id, q)
        try:
            await websocket.close()
        except Exception:
            pass
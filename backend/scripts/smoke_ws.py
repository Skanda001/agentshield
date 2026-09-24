"""WebSocket smoke test — real live-streaming flow.

Run:
    python scripts/smoke_ws.py <agent_api_key>

Order of operations (this is the correct one for live streaming):
  1. Pick a run_id (uuid)
  2. Open WS to /api/v1/demo/ws?run_id=<id>&token=<jwt>
  3. In a background task, POST /api/v1/demo/run { run_id: <id>, ... }
  4. Print every event as it arrives over the WS
  5. Exit on {"__done__": true}
"""
import asyncio
import json
import sys
import uuid

import httpx
import websockets

API_HTTP = "http://localhost:8001"
API_WS = "ws://localhost:8001"


async def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/smoke_ws.py <agent_api_key>")
        sys.exit(1)
    api_key = sys.argv[1]

    # 1. JWT
    r = httpx.post(
        f"{API_HTTP}/api/v1/agents/token",
        json={"api_key": api_key},
        timeout=10,
    )
    r.raise_for_status()
    jwt = r.json()["access_token"]

    run_id = str(uuid.uuid4())
    url = f"{API_WS}/api/v1/demo/ws?run_id={run_id}&token={jwt}"
    print(f"[ws] opening {url}")

    async with websockets.connect(url) as ws:
        print("[ws] connected")

        async def trigger():
            await asyncio.sleep(0.3)   # let the socket register server-side
            print("[http] POST /demo/run")
            async with httpx.AsyncClient(timeout=60) as client:
                rr = await client.post(
                    f"{API_HTTP}/api/v1/demo/run",
                    headers={"Authorization": f"Bearer {jwt}"},
                    json={
                        "scenario": "injection",
                        "mode": "replay",
                        "run_id": run_id,
                    },
                )
                rr.raise_for_status()
                print(f"[http] done: {len(rr.json()['events'])} events collected")

        trigger_task = asyncio.create_task(trigger())

        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                msg = json.loads(raw)
                if msg.get("__done__"):
                    print("[ws] __done__ received")
                    break
                if msg.get("__ping__"):
                    print("[ws] ping")
                    continue
                print(
                    f"[ws] step={msg.get('step')} "
                    f"tool={msg.get('tool')} "
                    f"decision={msg.get('decision')} "
                    f"risk={msg.get('risk', {}).get('score')}"
                )
        except asyncio.TimeoutError:
            print("[ws] timeout")
        finally:
            await trigger_task


if __name__ == "__main__":
    asyncio.run(main())
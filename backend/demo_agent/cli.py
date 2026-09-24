"""CLI entrypoints for the AgentShield demo agent.

Examples:
    python -m demo_agent.cli replay normal
    python -m demo_agent.cli replay pii
    python -m demo_agent.cli replay destructive
    python -m demo_agent.cli replay injection
    python -m demo_agent.cli live "Process my latest emails for customer 1774"
"""
from __future__ import annotations

import asyncio
import json
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from demo_agent.support_agent import run_replay, run_live, SCENARIOS


async def _emit_stdout(ev: dict) -> None:
    # One JSON line per event — pipe-friendly, WebSocket-ready.
    print(json.dumps(ev, default=str), flush=True)


async def _main() -> None:
    if len(sys.argv) < 2:
        print("usage:")
        print("  python -m demo_agent.cli replay <scenario>")
        print("  python -m demo_agent.cli live \"<prompt>\"")
        print()
        print("scenarios:", ", ".join(SCENARIOS))
        return

    mode = sys.argv[1]

    if mode == "replay":
        if len(sys.argv) < 3:
            print("scenarios:", ", ".join(SCENARIOS))
            return
        scenario = sys.argv[2]
        print(f"# replay scenario: {scenario}")
        print(f"# {SCENARIOS[scenario]['description']}")
        await run_replay(scenario, _emit_stdout)
        return

    if mode == "live":
        if len(sys.argv) < 3:
            print('usage: python -m demo_agent.cli live "<prompt>"')
            return
        prompt = " ".join(sys.argv[2:])
        print(f"# live prompt: {prompt}")
        await run_live(prompt, _emit_stdout)
        return

    print(f"unknown mode: {mode}")


if __name__ == "__main__":
    asyncio.run(_main())
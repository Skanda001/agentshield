"""Verify the audit chain end-to-end.

Run from backend/:
    python scripts/verify_audit.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows: psycopg async needs the Selector event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.db.session import AsyncSessionLocal
from app.audit.verifier import verify_chain


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await verify_chain(db)

    print(f"total events    : {result.total_events}")
    print(f"verified events : {result.verified_events}")
    print(f"valid           : {result.valid}")
    if not result.valid:
        print(f"broken at seq   : {result.broken_at_seq}")
        print(f"reason          : {result.reason}")
        for e in result.errors:
            print(f"  - {e}")


if __name__ == "__main__":
    asyncio.run(main())
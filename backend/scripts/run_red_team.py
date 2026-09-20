"""Red-team benchmark runner.

Runs every attack in the library against /api/v1/decide and reports
how many were blocked. Also runs 100+ benign calls to measure the
false-positive rate.
"""
import argparse
import asyncio
import json
import os
import sys

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
# Make `attack_library` importable when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = os.getenv("AGENTSHIELD_API_URL", "http://localhost:8001").rstrip("/")
API_KEY = os.getenv("AGENTSHIELD_API_KEY")

if not API_KEY:
    print("ERROR: AGENTSHIELD_API_KEY not set.", file=sys.stderr)
    sys.exit(1)


from attack_library.prompt_injection import ATTACKS as PI
from attack_library.data_exfiltration import ATTACKS as DE
from attack_library.destructive_actions import ATTACKS as DA


ALL_ATTACKS = PI + DE + DA


BENIGN_CALLS = [
    {"tool": "read_order", "arguments": {"order_id": str(i)}} for i in range(10)
] + [
    {"tool": "read_order", "arguments": {"order_id": "8211"}},
    {"tool": "read_order", "arguments": {"order_id": "8212"}},
    {"tool": "read_customer", "arguments": {"customer_id": "4821"}},
]


async def get_token(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{API_URL}/api/v1/agents/token",
        json={"api_key": API_KEY},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def call_decide(
    client: httpx.AsyncClient, token: str, tool: str, arguments: dict
) -> dict[str, Any]:
    start = time.perf_counter()
    r = await client.post(
        f"{API_URL}/api/v1/decide",
        headers={"Authorization": f"Bearer {token}"},
        json={"tool": tool, "arguments": arguments},
        timeout=15.0,
    )
    latency_ms = (time.perf_counter() - start) * 1000
    if r.status_code != 200:
        return {"verdict": "ERROR", "status": r.status_code, "latency_ms": latency_ms}
    body = r.json()
    body["latency_ms"] = latency_ms
    return body


@dataclass
class CategoryResult:
    category: str
    total: int = 0
    blocked: int = 0
    escalated: int = 0
    allowed: int = 0
    errors: int = 0
    latencies: list = field(default_factory=list)

    def record(self, verdict: str, latency_ms: float) -> None:
        self.total += 1
        self.latencies.append(latency_ms)
        if verdict == "BLOCK":
            self.blocked += 1
        elif verdict == "ESCALATE":
            self.escalated += 1
        elif verdict == "ALLOW":
            self.allowed += 1
        else:
            self.errors += 1

    @property
    def protected(self) -> int:
        return self.blocked + self.escalated

    @property
    def protection_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.protected / self.total

    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        idx = max(0, int(0.95 * len(s)) - 1)
        return s[idx]


async def run_benchmark() -> dict:
    results: dict = {}

    async with httpx.AsyncClient() as client:
        token = await get_token(client)
        print(f"[benchmark] Authenticated against {API_URL}")

        for attack in ALL_ATTACKS:
            cat = attack["category"]
            if cat not in results:
                results[cat] = CategoryResult(category=cat)
            decision = await call_decide(client, token, attack["tool"], attack["arguments"])
            results[cat].record(decision.get("verdict", "ERROR"), decision.get("latency_ms", 0.0))

        benign = CategoryResult(category="benign")
        for call in BENIGN_CALLS:
            decision = await call_decide(client, token, call["tool"], call["arguments"])
            benign.record(decision.get("verdict", "ERROR"), decision.get("latency_ms", 0.0))
        results["benign"] = benign

    return results


def print_report(results: dict) -> None:
    print()
    print("=" * 78)
    print(f"{'Category':<24} {'Total':>6} {'Blocked':>8} {'Escal':>6} {'Allowed':>8} {'Rate':>8}")
    print("-" * 78)

    total_all = 0
    total_protected = 0

    for name, r in results.items():
        if name == "benign":
            continue
        print(
            f"{name:<24} {r.total:>6} {r.blocked:>8} {r.escalated:>6} {r.allowed:>8} "
            f"{r.protection_rate*100:>7.1f}%"
        )
        total_all += r.total
        total_protected += r.protected

    print("-" * 78)
    overall = (total_protected / total_all) if total_all else 0.0
    print(f"{'Overall':<24} {total_all:>6} {total_protected:>14} "
          f"{'':>6} {overall*100:>7.1f}%")
    print("=" * 78)

    benign = results.get("benign")
    if benign:
        blocked_or_esc = benign.blocked + benign.escalated
        fp_rate = blocked_or_esc / benign.total if benign.total else 0.0
        print(f"\nBenign calls:      {benign.total}")
        print(f"  ALLOW:           {benign.allowed} ({(benign.allowed/benign.total)*100:.1f}%)")
        print(f"  BLOCK:           {benign.blocked}")
        print(f"  ESCALATE:        {benign.escalated}")
        print(f"  False-positive:  {fp_rate*100:.1f}%")

    all_latencies = []
    for r in results.values():
        all_latencies.extend(r.latencies)
    if all_latencies:
        s = sorted(all_latencies)
        p50 = s[len(s)//2]
        p95 = s[max(0, int(0.95 * len(s)) - 1)]
        p99 = s[max(0, int(0.99 * len(s)) - 1)]
        print(f"\nLatency: P50={p50:.1f}ms  P95={p95:.1f}ms  P99={p99:.1f}ms")
    print()


def save_results(results: dict, path: Path) -> None:
    data = {
        name: {
            "category": r.category,
            "total": r.total,
            "blocked": r.blocked,
            "escalated": r.escalated,
            "allowed": r.allowed,
            "errors": r.errors,
            "protection_rate": r.protection_rate,
            "p95_latency_ms": r.p95_latency,
        }
        for name, r in results.items()
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[benchmark] Results written to {path}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="benchmark_results.json")
    args = parser.parse_args()

    results = await run_benchmark()
    print_report(results)
    save_results(results, Path(args.out))


if __name__ == "__main__":
    asyncio.run(main())
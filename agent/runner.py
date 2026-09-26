"""CLI Runner for testing decoupled agents through AgentShield."""
from __future__ import annotations

import argparse
import sys

from pathlib import Path
from dotenv import load_dotenv

for candidate in [Path(".env"), Path("backend/.env"), Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent.parent / "backend" / ".env"]:
    if candidate.exists():
        load_dotenv(candidate)

import agent


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="AgentShield Decoupled Agent CLI Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent "what is the adhar details of customer 1008"
  python -m agent "check recent orders for customer 1001"
  python -m agent "delete customer 1008"
  python -m agent --agent finance "transfer 500 dollars to ACC-1008"
  python -m agent --list
        """,
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Natural language prompt for the agent",
    )
    parser.add_argument(
        "--agent", "-a",
        default="support",
        help="Agent to run (default: 'support')",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all registered agents and exit",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve HITL escalations without interactive prompt",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without console prompts for human approval",
    )

    args = parser.parse_args()

    if args.list:
        print("\nRegistered Pluggable Agents:")
        for name in agent.list_agents():
            print(f"  • {name}")
        print()
        sys.exit(0)

    if not args.prompt:
        parser.print_help()
        sys.exit(1)

    print("\n" + "=" * 70)
    print(f"🤖 Running Agent: [{args.agent}]")
    print(f"💬 Prompt: \"{args.prompt}\"")
    print("=" * 70)

    try:
        ag = agent.get_agent(args.agent)
        result = ag.run(
            args.prompt,
            interactive=not args.non_interactive,
            auto_approve=args.auto_approve,
        )

        print("\n" + "-" * 70)
        print(f"📋 Final Agent Response (Status: {result.status})")
        print("-" * 70)
        print(result.text)

        if result.tool_calls:
            print("\n" + "-" * 70)
            print("🛡️  AgentShield Gateway Telemetry")
            print("-" * 70)
            for tc in result.tool_calls:
                print(f"  Tool:        {tc.tool}")
                print(f"  Verdict:     {tc.verdict}")
                print(f"  Risk Score:  {tc.risk_score}")
                if tc.decision_id:
                    print(f"  Decision ID: {tc.decision_id}")
                if tc.approval_id:
                    print(f"  Approval ID: {tc.approval_id}")
                if tc.reasons:
                    print(f"  Reasons:     {', '.join(tc.reasons)}")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Error running agent: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

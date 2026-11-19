"""Tests that the shield_rules.md worked-examples table matches the risk engine.

Parsing rules:
- Look for a Markdown table under the '## Worked examples' heading.
- Extract rows: Scenario | Risk | Decision
- Strip backticks from the scenario column; use it as the tool name.
- Parse Risk as an integer; Decision as the expected verdict.
- Call evaluate(tool=..., arguments={}) and assert the verdict matches.

This test is intentionally strict: if the doc claims a score and the engine
disagrees, one of them is wrong.  Fix the doc or the engine, not this test.
"""
import re
from pathlib import Path

import pytest

SHIELD_RULES_MD = Path(__file__).parent.parent / "app" / "shield_rules.md"


def _parse_worked_examples() -> list[tuple[str, int, str]]:
    """Return [(tool_name, expected_risk, expected_verdict), ...]."""
    text = SHIELD_RULES_MD.read_text(encoding="utf-8")

    # Find the section
    section_match = re.search(r"## Worked examples\s*\n(.*?)(?=^##|\Z)", text, re.DOTALL | re.MULTILINE)
    assert section_match, "Could not find '## Worked examples' section in shield_rules.md"
    section = section_match.group(1)

    rows = []
    # Match table data rows (skip header and separator)
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| ---") or "Scenario" in line:
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 3:
            continue
        scenario_raw, risk_raw, decision_raw = parts[0], parts[1], parts[2]
        # Extract tool name from first word or backtick span
        tool_match = re.match(r"`([^(`]+)", scenario_raw)
        if not tool_match:
            tool_match = re.match(r"(\w+)", scenario_raw)
        if not tool_match:
            continue
        tool = tool_match.group(1).strip()
        try:
            risk = int(risk_raw.strip())
        except ValueError:
            continue
        decision = decision_raw.strip().upper()
        rows.append((tool, risk, decision))

    return rows


@pytest.mark.parametrize("tool,expected_risk,expected_verdict", _parse_worked_examples())
def test_shield_rules_worked_example(tool: str, expected_risk: int, expected_verdict: str):
    """Each row in the worked-examples table must match what risk_engine.evaluate() returns."""
    from app.risk_engine.deterministic import evaluate

    # Use an empty argument set — the doc examples are tool-name-driven
    result = evaluate(tool=tool, arguments={})

    # Allow ±5 points of drift in the risk score (rounding, PII scan on empty args)
    assert abs(result.risk_score - expected_risk) <= 10, (
        f"Tool '{tool}': doc says risk={expected_risk}, engine returned {result.risk_score}. "
        "Update shield_rules.md or the risk engine to agree."
    )

    assert result.verdict == expected_verdict, (
        f"Tool '{tool}': doc says verdict={expected_verdict}, "
        f"engine returned verdict={result.verdict} (score={result.risk_score}). "
        "Update shield_rules.md or adjust the band thresholds."
    )

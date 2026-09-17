"""Evaluate a request against a policy document.

Rules are matched by field equality (agent, role, action, resource) and
by optional conditions (data_classification, destination, etc.).
Conflicts are resolved by priority (highest wins); ties go to the more
restrictive effect (deny > escalate > allow).
"""
from dataclasses import dataclass
from typing import Any, Optional

from app.schemas.policy import PolicyDocument, RuleSchema


# Higher = more restrictive. Used for tie-breaking at equal priority.
EFFECT_RANK = {"allow": 0, "escalate": 1, "deny": 2}


@dataclass
class EvalContext:
    agent_name: str
    role: str
    action: str
    resource_type: str
    arguments: dict[str, Any]
    data_classification: Optional[str] = None


@dataclass
class EvalResult:
    matched_rule: Optional[str]
    effect: Optional[str]
    reason: str
    priority: int


def _field_matches(rule_value: Optional[str], ctx_value: str) -> bool:
    if rule_value is None:
        return True
    return rule_value.lower() == ctx_value.lower()


def _conditions_match(
    conditions: dict[str, Any], ctx: EvalContext
) -> tuple[bool, str]:
    if not conditions:
        return True, ""

    for key, expected in conditions.items():
        if key == "data_classification":
            if ctx.data_classification is None:
                return False, "missing data_classification"
            if str(expected).lower() != ctx.data_classification.lower():
                return False, f"data_classification != {expected}"

        elif key == "destination":
            # destination: external means arguments has to/url/webhook fields
            dest_value = None
            for k in ("to", "url", "endpoint", "webhook", "destination"):
                if isinstance(ctx.arguments.get(k), str):
                    dest_value = "external"
                    break
            if dest_value is None:
                dest_value = "internal"
            if str(expected).lower() != dest_value:
                return False, f"destination != {expected}"

        elif key == "min_volume":
            count = 1
            for k in ("count", "limit", "page_size"):
                v = ctx.arguments.get(k)
                if isinstance(v, int):
                    count = v
                    break
            ids = ctx.arguments.get("ids") or ctx.arguments.get("customer_ids")
            if isinstance(ids, list):
                count = len(ids)
            if count < int(expected):
                return False, f"volume < {expected}"

        else:
            # Generic equality against arguments
            if ctx.arguments.get(key) != expected:
                return False, f"{key} != {expected}"

    return True, ""


def _rule_matches(rule: RuleSchema, ctx: EvalContext) -> tuple[bool, str]:
    if not _field_matches(rule.agent, ctx.agent_name):
        return False, "agent mismatch"
    if not _field_matches(rule.role, ctx.role):
        return False, "role mismatch"
    if not _field_matches(rule.action, ctx.action):
        return False, "action mismatch"
    if not _field_matches(rule.resource, ctx.resource_type):
        return False, "resource mismatch"
    return _conditions_match(rule.conditions, ctx)


def _specificity(rule: RuleSchema) -> int:
    """Count how many constraint fields a rule sets. Higher = more specific."""
    score = 0
    if rule.agent is not None:
        score += 1
    if rule.role is not None:
        score += 1
    if rule.action is not None:
        score += 1
    if rule.resource is not None:
        score += 1
    score += len(rule.conditions)
    return score


def evaluate_policy(
    document: PolicyDocument, ctx: EvalContext
) -> EvalResult:
    matches: list[RuleSchema] = []
    for rule in document.rules:
        ok, _why = _rule_matches(rule, ctx)
        if ok:
            matches.append(rule)

    if not matches:
        return EvalResult(
            matched_rule=None,
            effect=None,
            reason="No rule matched",
            priority=-1,
        )

    # Resolve conflicts in this order:
    #   1. Specificity (more constraints wins) — prevents catch-all defaults
    #      from clobbering specific rules.
    #   2. Priority (higher number wins).
    #   3. Effect restrictiveness (deny > escalate > allow) at exact ties.
    matches.sort(
        key=lambda r: (
            _specificity(r),
            r.priority,
            EFFECT_RANK[r.effect],
        ),
        reverse=True,
    )
    winner = matches[0]

    return EvalResult(
        matched_rule=winner.name,
        effect=winner.effect,
        reason=(
            f"Matched rule '{winner.name}' "
            f"(specificity {_specificity(winner)}, priority {winner.priority})"
        ),
        priority=winner.priority,
    )
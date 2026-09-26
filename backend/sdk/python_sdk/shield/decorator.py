"""The @protect decorator.

Wraps a function so that every call is intercepted, sent to AgentShield,
and gated by the returned verdict.
"""
import functools
import inspect
import logging
from typing import Any, Callable, Optional

from shield.client import ShieldClient
from shield.exceptions import (
    ShieldBlocked,
    ShieldEscalated,
    ShieldError,
)

logger = logging.getLogger("shield")

_DEFAULT_CLIENT: Optional[ShieldClient] = None


def _get_client() -> ShieldClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = ShieldClient()
    return _DEFAULT_CLIENT


def _jsonable(value: Any) -> Any:
    """Best-effort JSON conversion; fall back to repr for odd types."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return repr(value)


def _bind_arguments(func: Callable, args: tuple, kwargs: dict) -> dict[str, Any]:
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        return {k: _jsonable(v) for k, v in bound.arguments.items()}
    except Exception:
        return {"_raw_args": _jsonable(list(args)), "_raw_kwargs": _jsonable(kwargs)}


def protect(
    *,
    tool: Optional[str] = None,
    resource_type: Optional[str] = None,
    data_classification: Optional[str] = None,
    fail_closed: bool = True,
    client: Optional[ShieldClient] = None,
):
    """Decorator factory.

    Usage:
        @protect(tool="read_customer", resource_type="customer")
        def read_customer(customer_id: str): ...
    """

    def decorator(func: Callable) -> Callable:
        tool_name = tool or func.__name__

        def _evaluate_gateway(args: tuple, kwargs: dict):
            # Strip a stray `kwargs` key that some LangChain versions pass.
            if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
                merged = dict(kwargs.pop("kwargs"))
                merged.update(kwargs)
                kwargs = merged

            arguments = _bind_arguments(func, args, kwargs)
            cli = client or _get_client()

            try:
                decision = cli.decide(
                    tool=tool_name,
                    arguments=arguments,
                    resource_type=resource_type,
                    data_classification=data_classification,
                )
            except ShieldError as e:
                if fail_closed:
                    logger.error("[shield] %s(%s) → gateway error: %s", tool_name, arguments, e)
                    raise
                logger.warning("[shield] %s → gateway unreachable, fail-open: %s", tool_name, e)
                return "FAIL_OPEN", None, None

            logger.info(
                "[shield] %s(%s) → %s (risk=%.0f, reason=%s)",
                tool_name, arguments, decision.verdict, decision.risk_score,
                "; ".join(decision.reasons[:1]) or "n/a",
            )

            if decision.verdict == "ALLOW":
                return "ALLOW", decision, None

            if decision.verdict == "BLOCK":
                raise ShieldBlocked(
                    reason="; ".join(decision.reasons) or "Blocked by AgentShield",
                    decision_id=decision.decision_id,
                    risk_score=decision.risk_score,
                    tool=tool_name,
                )

            if decision.verdict == "ESCALATE":
                approval_id = None
                try:
                    app = cli.get_approval_for_decision(decision.decision_id)
                    if app:
                        approval_id = str(app.get("id"))
                except Exception:
                    pass
                raise ShieldEscalated(
                    reason="; ".join(decision.reasons) or "Requires human approval",
                    decision_id=decision.decision_id,
                    risk_score=decision.risk_score,
                    tool=tool_name,
                    approval_id=approval_id,
                )

            raise ShieldError(f"Unknown verdict from AgentShield: {decision.verdict}")

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                action, _, _ = _evaluate_gateway(args, kwargs)
                return await func(*args, **kwargs)

            async_wrapper._shield_tool = tool_name
            async_wrapper._shield_resource_type = resource_type
            async_wrapper._shield_classification = data_classification
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                action, _, _ = _evaluate_gateway(args, kwargs)
                return func(*args, **kwargs)

            sync_wrapper._shield_tool = tool_name
            sync_wrapper._shield_resource_type = resource_type
            sync_wrapper._shield_classification = data_classification
            return sync_wrapper

    return decorator
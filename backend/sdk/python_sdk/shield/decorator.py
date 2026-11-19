"""The @protect decorator.

Wraps a function so that every call is intercepted, sent to AgentShield,
and gated by the returned verdict.

Fail mode
---------
``fail_closed=True``  (default): If the gateway is unreachable, times out, or
    returns a non-200 response, a ``ShieldError`` is raised and the wrapped
    function is **NOT** called.  This is the safe production default.

``fail_closed=False``: If the gateway cannot be reached, the error is logged
    and the wrapped function is called anyway (fail-open).  Only use this when
    tool execution is preferable to a gateway outage (e.g., non-sensitive
    read-only helpers).  Set ``SHIELD_FAIL_CLOSED=false`` in the environment
    to override per-process, or pass ``fail_closed=False`` explicitly.
"""
import functools
import inspect
import logging
import os
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
        res = {k: _jsonable(v) for k, v in bound.arguments.items()}
        if "kwargs" in res and isinstance(res["kwargs"], dict):
            extra = res.pop("kwargs")
            res.update(extra)
        return res
    except Exception:
        return {"_raw_args": _jsonable(list(args)), "_raw_kwargs": _jsonable(kwargs)}


def _default_fail_closed() -> bool:
    """Read SHIELD_FAIL_CLOSED env var. Defaults to True (fail-closed)."""
    val = os.getenv("SHIELD_FAIL_CLOSED", "true").strip().lower()
    return val not in ("false", "0", "no")


def protect(
    *,
    tool: Optional[str] = None,
    resource_type: Optional[str] = None,
    data_classification: Optional[str] = None,
    fail_closed: Optional[bool] = None,
    client: Optional[ShieldClient] = None,
):
    """Decorator factory.

    Usage::

        @protect(tool="read_customer", resource_type="customer")
        def read_customer(customer_id: str): ...

    Parameters
    ----------
    tool:
        Override the tool name sent to AgentShield (default: function name).
    resource_type:
        Optional resource type for risk scoring.
    data_classification:
        Optional data classification hint (e.g. ``"pii"``).
    fail_closed:
        ``True`` (default): raise ``ShieldError`` and do NOT execute the tool
        when the gateway is unreachable, times out, or returns a non-200
        response.  ``False``: log a warning and execute the tool anyway.
        When ``None`` the value is taken from the ``SHIELD_FAIL_CLOSED``
        environment variable (default ``true``).
    client:
        Custom ``ShieldClient`` instance; uses the module-level singleton by
        default.
    """
    effective_fail_closed = fail_closed if fail_closed is not None else _default_fail_closed()

    def decorator(func: Callable) -> Callable:
        tool_name = tool or func.__name__

        def _evaluate_gateway(args: tuple, kwargs: dict):
            """Call the gateway; return (verdict, decision) or raise.

            Returns
            -------
            tuple[str, decision | None]
                ``("ALLOW", decision)`` → caller should run the tool.
                ``("FAIL_OPEN", None)``  → gateway failed and fail_closed=False;
                    caller should run the tool.

            Raises
            ------
            ShieldBlocked   – verdict is BLOCK
            ShieldEscalated – verdict is HITL / ESCALATE
            ShieldError     – gateway error when fail_closed=True, or unknown verdict
            """
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
                if effective_fail_closed:
                    # Fail-closed: do NOT run the tool. Re-raise so callers know.
                    logger.error(
                        "[shield] %s(%s) → gateway error (fail-closed): %s",
                        tool_name, arguments, e,
                    )
                    raise
                # Fail-open: log a warning and allow the tool to execute.
                logger.warning(
                    "[shield] %s → gateway unreachable, running fail-open: %s",
                    tool_name, e,
                )
                return "FAIL_OPEN", None

            logger.info(
                "[shield] %s(%s) → %s (risk=%.0f, reason=%s)",
                tool_name, arguments, decision.verdict, decision.risk_score,
                "; ".join(decision.reasons[:1]) or "n/a",
            )

            if decision.verdict == "ALLOW":
                return "ALLOW", decision

            if decision.verdict == "BLOCK":
                raise ShieldBlocked(
                    reason="; ".join(decision.reasons) or "Blocked by AgentShield",
                    decision_id=decision.decision_id,
                    risk_score=decision.risk_score,
                    tool=tool_name,
                )

            if decision.verdict in ("HITL", "ESCALATE"):
                approval_id = getattr(decision, "approval_id", None)
                if not approval_id:
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

            # Unknown verdict — always fail-closed: an unrecognised verdict must
            # never silently allow the tool to run.
            raise ShieldError(f"Unknown verdict from AgentShield: {decision.verdict!r}")

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                verdict, _ = _evaluate_gateway(args, kwargs)
                # verdict is "ALLOW" or "FAIL_OPEN" here; blocked/escalated
                # verdicts raised as exceptions above.
                return await func(*args, **kwargs)

            async_wrapper._shield_tool = tool_name
            async_wrapper._shield_resource_type = resource_type
            async_wrapper._shield_classification = data_classification
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                verdict, _ = _evaluate_gateway(args, kwargs)
                return func(*args, **kwargs)

            sync_wrapper._shield_tool = tool_name
            sync_wrapper._shield_resource_type = resource_type
            sync_wrapper._shield_classification = data_classification
            return sync_wrapper

    return decorator

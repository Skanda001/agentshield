"""Agent Registry for multi-agent support and discovery."""
from __future__ import annotations

import logging
from typing import Callable, Type

from agent.base import BaseAgent

logger = logging.getLogger("agent.registry")

_REGISTRY: dict[str, Type[BaseAgent]] = {}


def register_agent(*names: str) -> Callable[[Type[BaseAgent]], Type[BaseAgent]]:
    """Decorator to register an agent class under one or more alias names."""
    def decorator(cls: Type[BaseAgent]) -> Type[BaseAgent]:
        for name in names:
            key = name.strip().lower()
            _REGISTRY[key] = cls
            logger.debug("Registered agent '%s' -> %s", key, cls.__name__)
        return cls
    return decorator


def list_agents() -> list[str]:
    """Return a unique, sorted list of registered agent names."""
    _ensure_agents_loaded()
    return sorted(list(set(_REGISTRY.keys())))


def get_agent(name: str = "support", **kwargs) -> BaseAgent:
    """Retrieve and instantiate an agent by name."""
    # Ensure standard built-in agents are loaded
    _ensure_agents_loaded()

    key = name.strip().lower()
    if key not in _REGISTRY:
        available = ", ".join(list_agents())
        raise ValueError(f"Agent '{name}' not found. Available agents: {available}")

    agent_cls = _REGISTRY[key]
    return agent_cls(**kwargs)


def _ensure_agents_loaded() -> None:
    """Lazily import built-in agent modules so they register themselves."""
    try:
        import agent.agents.support_agent  # noqa: F401
    except ImportError as e:
        logger.warning("Could not load support_agent: %s", e)

    try:
        import agent.agents.finance_agent  # noqa: F401
    except ImportError as e:
        logger.warning("Could not load finance_agent: %s", e)

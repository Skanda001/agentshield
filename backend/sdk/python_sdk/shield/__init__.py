"""AgentShield Python SDK."""
from shield.client import ShieldClient
from shield.decorator import protect
from shield.exceptions import (
    ShieldBlocked,
    ShieldConfigError,
    ShieldError,
    ShieldEscalated,
)

__all__ = [
    "ShieldClient",
    "protect",
    "ShieldBlocked",
    "ShieldEscalated",
    "ShieldError",
    "ShieldConfigError",
]
__version__ = "0.1.0"
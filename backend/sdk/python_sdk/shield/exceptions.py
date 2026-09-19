"""SDK exceptions."""


class ShieldError(Exception):
    """Base class for all AgentShield SDK errors."""


class ShieldConfigError(ShieldError):
    """Raised when the SDK is misconfigured (missing env vars, bad URL)."""


class ShieldBlocked(ShieldError):
    """Raised when AgentShield returns verdict=BLOCK."""

    def __init__(self, reason: str, decision_id: str | None = None, risk_score: float = 0.0):
        super().__init__(reason)
        self.reason = reason
        self.decision_id = decision_id
        self.risk_score = risk_score


class ShieldEscalated(ShieldError):
    """Raised when AgentShield returns verdict=ESCALATE (human approval required)."""

    def __init__(self, reason: str, decision_id: str | None = None, risk_score: float = 0.0):
        super().__init__(reason)
        self.reason = reason
        self.decision_id = decision_id
        self.risk_score = risk_score
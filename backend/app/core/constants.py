"""Canonical AgentShield risk-band constants.

Single source of truth for verdict thresholds. Every module that maps a
risk score to a verdict MUST import from here — never hard-code numbers.

Risk model:
  0  – ALLOW_MAX  → ALLOW  (tool executes normally)
  ALLOW_MAX+1 – HITL_MAX → HITL   (Human-in-the-Loop approval required)
  BLOCK_MIN – 100         → BLOCK  (tool body does not execute)
"""

# ── Risk band boundaries ────────────────────────────────────────────────────
ALLOW_MAX: int = 29    # 0–29   → ALLOW
HITL_MAX: int  = 69    # 30–69  → HITL  (Human-in-the-Loop)
BLOCK_MIN: int = 70    # 70–100 → BLOCK

# ── Verdict strings ─────────────────────────────────────────────────────────
VERDICT_ALLOW = "ALLOW"
VERDICT_HITL  = "HITL"
VERDICT_BLOCK = "BLOCK"

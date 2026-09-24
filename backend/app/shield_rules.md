# AgentShield risk model

## Decisions

| Band      | Range   | Meaning                                              |
|-----------|---------|------------------------------------------------------|
| ALLOW     | 0–29    | run the tool, write ALLOW to audit_log               |
| HITL      | 30–69   | pause; require human approval before the tool runs   |
| BLOCK     | 70–100  | refuse; tool body does not execute; audit + alert    |

## Why these bands?

- **30 for HITL.** Below 30 a tool is doing a normal read of non-PII
  data. Bumping the threshold higher would let PII reads (`get_customer`,
  base 40) run unattended — that's exactly what we want to catch.
- **70 for BLOCK.** Destructive (`delete_customer`, base 80) and
  externally-directed (`send_email` + external flag, 50+20) actions
  land above 70. Legitimate refunds sit at 55 — HITL, not BLOCK —
  so a human still sees them.

## Signals

| Signal                              | Weight |
|-------------------------------------|--------|
| Base per-tool (see _TOOL_BASE_RISK) | 10–80  |
| Data classification                 | +5..+25|
| External destination (`external=True`) | +20 |
| Destructive (`destructive=True`)    | +20    |
| PII in payload                      | +15    |
| Injection score × 40                | +0..+40|

## Injection patterns

| Pattern                              | Weight |
|--------------------------------------|--------|
| ignore previous instructions         | 0.95   |
| disregard previous rules             | 0.90   |
| you are now (admin|root|system)      | 0.92   |
| override (rbac|permissions|policy)   | 0.90   |
| export all customer records          | 0.85   |
| delete all/every …                   | 0.80   |
| system: prefix                       | 0.75   |
| send … to <email>                    | 0.70   |

## Worked examples

| Scenario                                     | Risk | Decision |
|----------------------------------------------|------|----------|
| `get_customer_orders(1042)`                  | 15   | ALLOW    |
| `get_customer(1042)` (PII, restricted)       | 65   | HITL     |
| `send_email` external, PII, injection 0.95   | 100  | BLOCK    |
| `issue_refund(10042, 4999)`                  | 55   | HITL     |
| `delete_customer(1042)`                      | 100  | BLOCK    |
# Architecture

## High-level flow

    AI Agent
        │
        │  tool call (e.g. delete_customer)
        ▼
    ┌─────────────────────────────────────┐
    │         AgentShield Gateway         │
    │                                     │
    │  1. Normalize tool call             │
    │  2. Load tenant's active policy     │
    │  3. Evaluate policy → allow/deny/esc│
    │  4. Score risk (6 signals)          │
    │  5. Combine → final verdict         │
    │  6. Persist decision                │
    │  7. Append to audit chain           │
    └─────────────────────────────────────┘
        │
        │  ALLOW / BLOCK / ESCALATE
        ▼
    Tool execution (only if ALLOW)

## Subsystems

| Subsystem | Location | Responsibility |
|-----------|----------|----------------|
| Agent Registry | `app/services/agent_registry.py` | Create tenants, register agents, hash API keys, issue JWTs |
| Policy Engine | `app/policy_engine/` | Parse YAML DSL, evaluate rules, version policies |
| Risk Engine | `app/risk_engine/` | Extract 6 signals, sum to 0–100 score |
| Injection Detection | `app/detection/injection/` | Regex heuristics for prompt injection |
| PII Detection | `app/detection/pii/` | Recognizers for Aadhaar, PAN, email, phone, etc. |
| Decision Pipeline | `app/gateway/decision_pipeline.py` | Orchestrate the full flow |
| Audit Chain | `app/audit/` | Hash-chained, HMAC-signed append-only log |
| HITL | `app/hitl/` | Approval requests for ESCALATE verdicts |
| Kill Switch | `app/kill_switch/` | Global / tenant / agent / tool suspension |

## Data model

    tenants ──┬── agents ──┬── decisions ──── approvals
              │            └── audit_log
              └── policies ──── policy_versions

    kill_switches (standalone)

## Verdict thresholds

| Score range | Verdict |
|-------------|---------|
| 0–39 | ALLOW |
| 40–84 | ESCALATE (human approval) |
| 85–100 | BLOCK |

Policy can short-circuit: a `deny` rule forces BLOCK at score 0.

## Auth flow

1. `POST /tenants` → creates a tenant
2. `POST /agents` → returns a plaintext API key **once**
3. `POST /agents/token` → exchanges API key for short-lived JWT
4. All subsequent calls use `Authorization: Bearer <JWT>`

API keys are stored as HMAC-SHA256 hashes. Plaintext is never persisted.
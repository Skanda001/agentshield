# AgentShield Security Properties

This document describes the security guarantees AgentShield provides and
the assumptions under which they hold. It is written for an engineer
evaluating the system, not for an end user.

---

## Guarantees

### 1. Every tool call is authorized

No tool call reaches the underlying function without passing through
`POST /api/v1/decide`, which returns exactly one of ALLOW, BLOCK, or
ESCALATE. The SDK enforces this — it wraps the function with the
`@shield.protect` decorator and cannot be bypassed by the caller.

**Caveat:** this guarantee only holds if the tool is wrapped with the SDK,
or if all tool access is routed through the AgentShield API. Tools called
directly — bypassing the SDK — are not protected.

### 2. Decisions are explainable

Every verdict carries:

- A risk score in [0, 100]
- The full list of signals that contributed to the score
- Human-readable reasons for each signal
- The policy rule that matched (if any)
- The policy's specificity and priority (if matched)

An operator can always answer "why was this blocked?" without guesswork
or reverse engineering. There is no black box anywhere in the decision path.

### 3. Every decision is auditable and tamper-evident

- Every decision is appended to the `audit_log` table.
- Each row stores three hash-related fields:
  - `prev_hash` — the `hash` of the previous event (or 64 zeros for the
    first event).
  - `hash` — SHA-256 of `prev_hash + canonical_json(payload)`.
  - `signature` — HMAC-SHA256 of `hash`, keyed with `AUDIT_HMAC_SECRET`.
- Appends are serialized with a Postgres advisory lock
  (`pg_advisory_xact_lock`), preventing chain forks under concurrent writes.
- `GET /api/v1/audit/verify` recomputes the entire chain from genesis and
  reports the first point of failure.

**Tamper detection covers:**

| Attack | Detection |
|---|---|
| Payload modified | Hash mismatch on the affected row |
| Event deleted | `prev_hash` mismatch on the next surviving row |
| Hash forged | Signature invalid (attacker lacks the HMAC secret) |
| Chain reordered | `prev_hash` mismatch on the first out-of-order row |
| Event inserted | Same as deletion — the link to the inserted row is broken |

### 4. API keys are never stored in plaintext

- Generated with `secrets.token_urlsafe(32)` and prefixed with `ash_`.
- Stored as HMAC-SHA256 hashes, not plaintext.
- Not hashed with bcrypt, deliberately — API keys are 43-character
  high-entropy strings, not guessable passwords. HMAC is O(1) and safe
  for high-entropy inputs.
- Shown to the user exactly once at creation.
- If the database leaks, the keys cannot be recovered from the hashes.

### 5. JWT tokens are short-lived and separately keyed

- Access tokens are signed with `AGENTSHIELD_JWT_SECRET` (not the audit
  secret).
- Default lifetime is 30 minutes.
- Payload carries `sub` (agent_id), `tenant_id`, `scopes`, and `type`.
- The `type` field is validated on decode, preventing refresh tokens from
  being used as access tokens.
- Tokens cannot be revoked individually (stateless JWTs), but suspending
  an agent immediately blocks its ability to obtain new tokens.

### 6. Policy conflicts are resolved deterministically

Three-level ordering:

1. **Specificity** — a rule with more constraints (agent, role, action,
   resource, conditions) wins over a rule with fewer.
2. **Priority** — higher numeric priority wins ties.
3. **Restrictiveness** — `deny > escalate > allow` as the final tiebreak.

This ordering is stable and testable. A catch-all default rule can never
silently clobber a specific rule, even if the default has a higher
priority number.

### 7. Emergency control is available at four levels

The kill switch can suspend:

1. **Global** — every tool call, every agent.
2. **Tenant** — every agent in one tenant.
3. **Agent** — a single agent.
4. **Tool** — one tool name across all agents.

Activation short-circuits the entire pipeline. The kill switch is checked
*before* policy evaluation and *before* risk scoring. If any switch is
active, the verdict is BLOCK with the switch's reason, and `risk_score`
is `0.0` because the risk engine never ran.

Activation and deactivation both append events to the audit chain
(`kill_switch.activated`, `kill_switch.deactivated`).

### 8. Failed calls fail closed by default

If AgentShield is unreachable, the SDK raises rather than allowing the
call through. This is the correct behavior for a security gateway — a
gateway that silently disappears defeats its own purpose.

Per-tool opt-out is available via `fail_closed=False` for genuinely
non-sensitive operations (e.g., reading a public document).

### 9. Human-in-the-loop escalation is auditable

When a decision returns ESCALATE:

- An `Approval` row is created with the decision context.
- A notification is sent (Slack if configured, otherwise logged).
- The approval has a configurable timeout (default 30 minutes).
- When a human approves or denies, the decision is recorded in the
  `approvals` table and an `approval.decided` event is appended to the
  audit chain.
- If the timeout expires, the approval is marked `expired` and an
  `approval.expired` event is appended.

### 10. Production configuration is validated at boot

`app/core/config.py` refuses to start the application if any of the
following are true:

- `APP_ENV=production` and `AGENTSHIELD_JWT_SECRET` still contains
  `replace-with`.
- `APP_ENV=production` and `AUDIT_HMAC_SECRET` still contains
  `replace-with`.
- `APP_ENV=production` and `API_DOCS_ENABLED=true` without
  `ALLOW_PUBLIC_DOCS=true`.

Failing loudly at boot is preferred over running insecurely.

---

## Assumptions

The guarantees above hold under these assumptions. If any of them is
violated, the corresponding guarantee no longer applies.

### The HMAC secret is not leaked

An attacker with both database write access and `AUDIT_HMAC_SECRET` can
forge a chain. The secret is loaded from an environment variable and never
written to the database.

### The JWT secret is not leaked

Same reasoning. If the JWT secret leaks, an attacker can mint tokens for
any agent.

### The audit HMAC secret must be stable across deploys

**This is an operational requirement, not just a design rule.**

`AUDIT_HMAC_SECRET` must be set **once** at deploy time and **never
changed**. If it changes:

- Every existing signature in the audit chain becomes invalid.
- The verifier reports the chain as broken at the first event signed with
  the old secret.
- Nothing can recover the old signatures — the key that produced them no
  longer exists.

**If a rotation is required, choose one of:**

1. **Re-sign the existing chain.** Read every event, recompute its
   signature with the new secret, write it back. This requires external
   tooling and a maintenance window. Record the rotation itself as an
   out-of-band event.
2. **Start a fresh chain.** Truncate `audit_log` and restart the sequence.
   Record the truncation in a separate, permanent log so the historical
   boundary is documented.

**Deployment note (Render, Fly, any container host):**

Set `AUDIT_HMAC_SECRET` and `AGENTSHIELD_JWT_SECRET` as **persistent**
environment variables **before the first deploy**. Do not:

- Leave them empty.
- Use a placeholder like `replace-with-...`.
- Use a value that gets regenerated by the platform on restart.

If either is unset, `app/core/config.py` falls back to a development
default. In `APP_ENV=production`, this is rejected at boot. But if a
random value is generated dynamically at startup (some platforms do this),
the chain will break on every restart — the verifier will correctly
detect it, but the historical chain becomes unusable.

### Postgres is not compromised at the superuser level

A superuser can drop the entire `audit_log` table. This is detectable
**out-of-band** — the total event count dropping to zero is a signal —
but the in-database verifier cannot detect a table that no longer exists.

### The gateway is the only path to the tools

AgentShield provides no protection if tools are called directly. Enforcement
requires every tool call to be routed through either:

- The Python SDK (`@shield.protect` decorator), or
- A proxy that calls `POST /api/v1/decide` before forwarding the call.

An application that calls tools without either is unprotected.

### The audit chain proves integrity, not existence

The chain guarantees that events in the log have not been modified or
reordered since they were written. It does **not** guarantee that every
tool call an agent makes is present in the log. If an attacker bypasses
the SDK, they can make tool calls that never appear in the audit trail.
The chain proves "what's here hasn't changed," not "everything is here."

### Threat model scope

The threat model is described in detail in `docs/THREAT_MODEL.md`. In
summary:

| Threat | Mitigation |
|---|---|
| Prompt injection (direct) | Heuristic classifier feeding into the risk score |
| Prompt injection (indirect, via tool output) | Same classifier runs on all arguments |
| Unauthorized tool call | Policy engine deny rules |
| Privilege escalation | Role-based rules + scoped JWTs |
| Data exfiltration | PII detection + external-destination signal |
| Bulk data extraction | Volume signal (single-call) |
| Audit tampering | Hash chain + HMAC signatures |
| Credential theft | HMAC-hashed API keys, no plaintext storage |
| Policy bypass | Single enforcement point + kill switch |
| Replay / token theft | Short-lived JWTs, one-time API key display |

---

## Explicitly out of scope

The following are deliberately not addressed in Tier 1. They are
documented here so operators know what is *not* protected.

- **Encryption at rest for the database.** Rely on the database host
  (Neon encrypts at rest by default).
- **Multi-region / high-availability deployment.** Single-region only.
- **Fine-grained rate limiting per endpoint.** Basic limits only.
- **Side-channel resistance.** Not analyzed.
- **Supply-chain security of LLM providers.** We trust OpenAI, Groq, and
  Anthropic to serve responses honestly.
- **Physical security.**
- **ML-based anomaly detection.** Planned as a future augmentation to the
  deterministic risk engine, not a replacement.
- **Cross-call rate limiting.** The current rate limiter is per-single-call
  volume, not per-time-window.
- **WebSocket authentication.** Not implemented; the frontend uses HTTP
  polling with bearer tokens.

---

## Reporting

This is a portfolio project, not a production service. There is no formal
security contact. If you find an issue, open a GitHub issue on the
repository.

---

## Change log

- **Initial version** — covered JWT auth, HMAC-hashed API keys, deterministic
  policy and risk engines, hash-chained audit log, HITL approvals, kill
  switch, and fail-closed SDK behavior.
- **Audit secret stability note** — added after discovering that a Render
  restart with a regenerated HMAC secret breaks all existing signatures.
  The verifier correctly detected the break. The operational requirement
  is now documented.
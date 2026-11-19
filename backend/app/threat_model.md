# AgentShield — Threat Model

> Version 0.2 · Last updated 2026-11-17

---

## 1. What AgentShield Protects

AgentShield is an **inline security gateway** that sits between AI agents and the sensitive tools they call (database operations, CRM mutations, payment actions, external API calls). Every tool call must be evaluated before execution. The gateway enforces:

- Risk-scored verdicts (ALLOW / HITL / BLOCK)
- Tenant-scoped policy rules
- Human-in-the-loop approval queues
- Tamper-evident audit log
- Kill switches (emergency stops)

---

## 2. Trust Boundaries

```
[ Agent process ] --SDK--> [ AgentShield Gateway ] ---> [ Tool / DB / API ]
                                    |
                           [ PostgreSQL + Redis ]
                                    |
                           [ React Dashboard ]
                                    |
                              [ Human approver ]
```

**Trusted**: The gateway backend itself, authenticated agents (after JWT validation), human approvers acting through the dashboard.

**Untrusted**: Tool call arguments (may contain injections), agent-supplied `tenant_id`/`agent_id` in request bodies, the network between agent and gateway.

---

## 3. Attackers & Mitigations

### A — Malicious Agent (insider or compromised agent process)

**Capabilities**: Valid API key; can call any endpoint the agent is authorised for.

| Attack | Mitigation |
|--------|-----------|
| Supply `tenant_id` of another tenant in POST body | Backend ignores client-supplied `tenant_id`; always uses JWT principal's `tenant_id` |
| Supply `agent_id` of another tenant in query param | `GET /decisions` only honours `agent_id` if it equals the caller's own `agent_id` |
| Approve its own HITL request | `POST /approvals/{id}/decide` returns 403 if `approval.agent_id == caller.agent_id` |
| Forge `decided_by` / `activated_by` | These fields are always derived from the authenticated JWT, never accepted from request body |
| Replay an approval for a different tool call | `arguments_hash` on the approval is compared against the new call; mismatch → 403 |
| Reuse an approval twice | `used_at` is set atomically; second use → 403 |
| Enumerate another tenant's decisions | All decision/audit queries filter by `tenant_id == agent.tenant_id` |
| Path traversal via `/policies/load-yaml?file_path=../../etc/passwd` | `Path.is_relative_to(POLICY_DIR)` check; symlinks rejected |
| Brute-force API keys via `/agents/token` | Rate limited to 10 requests/minute per IP; 429 + `Retry-After` |
| Flood `/decide` | Rate limited to 120 requests/minute per IP; 429 + `Retry-After` |

### B — Prompt-Injected Agent (agent manipulated by malicious user input)

**Capabilities**: Can cause the agent to issue arbitrary tool calls with attacker-controlled arguments.

| Attack | Mitigation |
|--------|-----------|
| Issue a high-risk tool call | Risk engine scores the call; deterministic signals catch destructive verbs + sensitive nouns |
| Use a low-risk tool name to bypass scoring (`remove_user` instead of `delete_customer`) | **Partial mitigation only** — see `docs/limitations.md`. Tool registry (Phase 1 roadmap) will close this gap |
| Inject PII into arguments to exfiltrate via log | PII masker redacts before storage in audit log |
| Inject prompt into `reason` field of a kill switch | `reason` is stored as text, never executed |

### C — Compromised Tenant User (dashboard access)

**Capabilities**: Valid JWT for a tenant; can view dashboard, manage approvals.

| Attack | Mitigation |
|--------|-----------|
| Access another tenant's approvals | All approvals scoped to `agent.tenant_id` |
| Activate a global kill switch | Requires `admin` scope in JWT |
| Activate a kill switch targeting another tenant's agent | `verify_target_in_tenant` checks DB membership |
| XSS in dashboard to steal JWT | No `dangerouslySetInnerHTML`; strict input sanitisation |

### D — Database Reader (compromised DB credentials)

**Capabilities**: Read access to PostgreSQL; possibly write if fully compromised.

| Attack | Mitigation |
|--------|-----------|
| Read PII from `audit_log.payload` | PII is masked before audit storage; raw arguments never stored in audit events |
| Modify audit log to cover tracks | HMAC chain: modified row causes verification failure; `GET /audit/verify` detects it |
| Delete audit rows | Sequence gap detected by verifier |
| Truncate audit table | Periodic signed checkpoint detects tail truncation |

> [!WARNING]
> The audit log is **tamper-evident, not tamper-proof**. A DB admin with write access can modify rows, but the HMAC chain will show broken verification. True tamper-proof storage would require an external immutable log (e.g. write-once S3, Trillian, or a notarisation service).

### E — Network Attacker (MitM between agent and gateway)

**Capabilities**: Observe or modify HTTP traffic.

| Attack | Mitigation |
|--------|-----------|
| Intercept JWT | Use TLS in production (Render/Vercel enforce this) |
| Replay a valid request | JWTs expire (30 min default); approvals are single-use |
| CORS exploit via malicious Vercel app | `allow_origin_regex` replaced with explicit `CORS_ALLOWED_REGEX` env var |

---

## 4. Known Limitations & Accepted Risks

See `docs/limitations.md` for the full list. Key items:

1. **JWT in localStorage** — JWTs are stored in `localStorage` (vulnerable to XSS). Mitigation: strict CSP, no `dangerouslySetInnerHTML`. Full fix: move to `httpOnly` cookie (requires backend CSRF protection; planned).

2. **Tool-name trust** — The risk engine classifies by substring of the client-supplied tool name. A sophisticated attacker can craft a low-risk-sounding name to reduce their score. Planned fix: tool registry with registered manifests; unknown tools default to HITL.

3. **Rate limiter fail-open** — When Redis is unavailable, the rate limiter fails open (requests are allowed). This is a deliberate choice: a Redis outage should not take the gateway offline. The tradeoff: brute-force is possible during Redis outages.

4. **SDK fail-closed blocked by ACL** — The `shield/decorator.py` file is inaccessible due to Windows ACL restrictions in the development environment. The fail-closed default has not been applied to the installed SDK package.

5. **Supabase RLS** — `USING (true)` / `WITH CHECK (true)` policies are overly permissive. Restrict to service-role insert only (see `supabase_schema.sql` TODO).

---

## 5. Out of Scope

- Protection against a fully compromised gateway host
- Supply-chain attacks on Python/npm dependencies
- DDoS (use a CDN/WAF in front of the gateway)
- LLM model vulnerabilities (AgentShield monitors calls, not model weights)

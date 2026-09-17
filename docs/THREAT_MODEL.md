# Threat Model

## Assets (what we protect)

1. Customer PII (names, emails, phone numbers)
2. API credentials and secrets
3. Agent permissions and scopes
4. Tool access (databases, email, external APIs)
5. Audit records (must be tamper-evident)
6. Policy configuration (must be tamper-proof)

## Trust boundaries

    User  →  AI Agent  →  AgentShield  →  Tools / APIs
                  ↑            ↑              ↑
             untrusted    trusted        external

- **User**        — untrusted input
- **AI Agent**    — semi-trusted (can be manipulated via prompt injection)
- **AgentShield** — trusted enforcement layer
- **Tools**       — external systems, authorized per-call

## Threat actors

1. Malicious user    — tries to make the agent do something it shouldn't
2. Compromised agent — an agent whose context has been hijacked
3. Insider misuse    — a legitimate agent used outside its intended scope
4. External attacker — exfiltrates data via indirect prompt injection

## Threats (STRIDE)

| #  | Threat                                  | Mitigation                                   |
|----|-----------------------------------------|----------------------------------------------|
| 1  | Prompt injection (direct)               | Injection classifier → signal to risk engine |
| 2  | Prompt injection (indirect, via outputs)| Scan tool responses before feeding back      |
| 3  | Unauthorized tool call                  | YAML policy engine + RBAC                    |
| 4  | Privilege escalation                    | Scoped JWT + role checks per action          |
| 5  | Data exfiltration                       | PII detection + egress policy (Tier 2)       |
| 6  | Tool abuse (volume)                     | Rate limits + behavioral anomaly (Tier 2)    |
| 7  | Audit tampering                         | Hash-chained log, verifiable                 |
| 8  | Replay attacks                          | Short-lived JWTs + nonces                    |
| 9  | Credential theft                        | Hashed API keys, no plaintext storage        |
| 10 | Policy bypass                           | Single enforcement point (gateway)           |

## Assumptions

- Assume: the agent can be fooled
- Assume: user input is hostile
- Assume: tool outputs are hostile
- Do not assume: the enforcement layer can be bypassed (single choke point)

## Out of scope (Tier 3)

- Multi-tenancy (deferred)
- Billing
- BCP/DR
- Supply chain of LLM providers
# Security Properties

## Authentication

- **API keys**: 43-char high-entropy tokens, stored as HMAC-SHA256 hashes
- **JWTs**: HS256, short-lived (30 min default), carry `agent_id`, `tenant_id`, `scopes`
- **Bearer scheme**: standard `Authorization: Bearer <token>` header

## Authorization

- YAML policy engine evaluates every tool call
- Rules match on agent, role, action, resource, conditions
- Conflict resolution: specificity → priority → restrictive-ness
- Policy denial short-circuits the pipeline (BLOCK at risk 0)

## Audit integrity

- Every decision appends to an append-only hash-chained log
- Chain hash = `SHA256(prev_hash + canonical_json(payload))`
- Each hash is HMAC-SHA256 signed with `AUDIT_HMAC_SECRET`
- Tampering is detectable even with full DB write access

See `app/audit/verifier.py` for the verification algorithm.

## Data protection

- PII detection for: Aadhaar, PAN, GSTIN, IFSC, UPI, phone, email, credit card, IBAN
- Values are redacted in logs (first 2 + last 2 chars shown)
- Sensitivity classification: public < internal < confidential < restricted
- PII + external destination = elevated risk (potential exfiltration)

## Prompt injection

- 12 regex patterns for known attacks (ignore instructions, DAN, system override, etc.)
- Runs on all argument values, including nested dicts
- Injection score contributes up to +45 to risk

## Isolation

- Tenant isolation enforced at query level
- Agents scoped to their tenant
- Kill switches per agent / tool / tenant / global

## Secrets

- `.env` never committed (see `.gitignore`)
- Production refuses to boot with placeholder secrets
- API docs disabled in production by default
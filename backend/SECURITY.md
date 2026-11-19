# Security Policy

## Reporting a Vulnerability

If you discover a security issue in AgentShield, **please do not open a public GitHub issue**.

Report it privately by emailing the maintainer directly (see the GitHub profile for contact details) with:
1. A clear description of the vulnerability
2. Steps to reproduce
3. The affected component (backend, frontend, SDK, agent)
4. Your assessment of severity

You will receive an acknowledgement within 48 hours.

---

## Known Limitations

See [`app/limitations.md`](backend/app/limitations.md) for a full list of known gaps and accepted trade-offs, including:

- JWT in `localStorage` (XSS risk)
- Rate limiter fails open when Redis is unavailable
- Audit log is tamper-evident but not tamper-proof
- Tool-name trust (evasion via renaming)
- Supabase RLS not yet fully restricted

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` branch | ✅ Yes |
| Older releases | ❌ No |

---

## Threat Model

See [`app/threat_model.md`](backend/app/threat_model.md) for the full threat model covering all attacker types, their capabilities, and mitigations.

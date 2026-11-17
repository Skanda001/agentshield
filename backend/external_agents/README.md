# External AI Agents (Client Directory)

This directory is **100% outside the AgentShield codebase**.
Each agent is an independent client application protected by the AgentShield security gateway via HTTP.

## Available Agents

1. **Customer Support Agent** (`customer-support-agent/`):
   - Handles customer lookups, order tracking, and statutory Indian identity verification (Aadhaar & PAN).
   - Protected by AgentShield with Least-Privilege Data Minimization.

2. **Financial & Treasury Agent** (`financial-agent/`):
   - Handles accounting balances, treasury transfers, and payment processing.
   - Protected with financial policy controls and human-in-the-loop approvals.

## Red-team testing

There is no red-team agent in this directory. Adversarial testing lives in
`backend/attack_library/` and is run with `backend/scripts/run_red_team.py`,
which sends every attack in the library (and a set of benign calls) to
`/api/v1/decide` and reports how many were blocked and how many were
false positives.

## Plug In / Plug Out with AgentShield UI

These agents can be dynamically plugged in or plugged out directly from the **AgentShield Dashboard UI**:
- When **Plugged In**: The agent is mounted into the active gateway folder (`agentshield/plugged_agents/`), issued an active security token, and enabled in the live playground.
- When **Plugged Out**: The agent is unmounted from the gateway folder, its security token is revoked, and all operations are immediately blocked.

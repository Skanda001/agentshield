# AgentShield

Security gateway for AI agents. Intercepts tool calls, enforces policies,
scores risk, detects prompt injection, and writes a tamper-evident audit log.

## What it does

AI agents can call tools (read databases, send emails, call APIs). AgentShield
sits between the agent and the tool and decides:

- **ALLOW**    — safe, proceed
- **BLOCK**    — policy violation or high risk, refused
- **ESCALATE** — needs human approval

Every decision is recorded in a hash-chained audit log.

## Status

Phase 0: foundation. See `docs/STATUS.md` for the full roadmap.

## Stack

- FastAPI (async)
- PostgreSQL + SQLAlchemy 2 (async)
- Alembic (migrations)
- Redis (rate limits, sessions)
- Docker Compose (full stack in one command)

## Run locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
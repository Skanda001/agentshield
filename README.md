# AgentShield 🛡️

> **Zero-Trust Security Gateway, Firewall, and Cryptographic Audit Plane for Autonomous AI Agents.**

[![Live Demo](https://img.shields.io/badge/Live%20Dashboard-Vercel-black?style=flat&logo=vercel)](https://agentshield-eight.vercel.app)
[![API Docs](https://img.shields.io/badge/API%20Docs-FastAPI%20Swagger-009688?style=flat&logo=fastapi)](https://agentshield-qhxo.onrender.com/docs)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18%2F19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 🌐 Live Deployments

* **Web Management Dashboard**: [agentshield-eight.vercel.app](https://agentshield-eight.vercel.app)
* **Backend API & Swagger Docs**: [agentshield-qhxo.onrender.com/docs](https://agentshield-qhxo.onrender.com/docs)

> [!NOTE]
> **Dashboard Demo vs. Active Testing**: Clicking **"Try Demo"** on the dashboard provides an interactive sandbox to explore the management UI, approval queue workflows, and policy simulator. 
> To **actively test real-time policy enforcement, prompt injection defense, and cryptographic audit hashing**, connect **real agents** (e.g., the [Customer Support Agent Demo](https://github.com/Skanda001/Customer-support-agent-demo-for-agent-shield)) using an Agent API Key and the `@protect` SDK.

---

## 📌 Executive Summary

Autonomous AI agents (powered by Groq, OpenAI, Anthropic, LangChain, LangGraph, CrewAI) can query databases, execute financial refunds, dispatch customer emails, and delete customer records. Without runtime security guardrails, a single prompt injection or rogue LLM output can exfiltrate sensitive data or execute catastrophic transactions.

**AgentShield** acts as an inline Zero-Trust proxy between AI agents and external tools/APIs. Every tool invocation undergoes sub-millisecond inspection, policy evaluation, prompt injection scanning, PII redacting, and tamper-evident audit logging before execution.

```
                     ┌───────────────────────────────────────────────┐
                     │              AgentShield Gateway              │
                     │                                               │
   AI Agent          │   1. Injection & Jailbreak Scanner            │         Tools & APIs
 (Groq / LangGraph)  │   2. PII Detection & Auto-Masker              │    (CRM, Email, Payments)
        │            │   3. Declarative Policy Engine (YAML)         │               ▲
        │ Tool Call  │   4. Human-in-the-Loop (HITL) Escalation      │               │
        ├───────────►│   5. Emergency Kill-Switch Check              ├───────────────┤ (If ALLOW)
        │            │   6. SHA-256 HMAC Hash-Chained Audit Log      │               │
        │            │                                               │               │
        │◄───────────┴───────────────────────────────────────────────┘               │
   Verdict Response                                                                  │
(ALLOW / BLOCK / HITL)                                                        Executes Safely
```

---

## ⚡ Quick Example: Protecting an Agent Tool

Developers protect any Python agent tool in two lines using the `@protect` decorator:

```python
from shield import protect

@protect(tool="delete_customer_account", resource_type="customer", data_classification="restricted")
async def delete_customer_account(customer_id: str):
    # This code NEVER executes if AgentShield returns BLOCK or HITL
    return await db.customers.delete(id=customer_id)
```

* **Safe calls (`ALLOW`)**: Pass through and execute normally.
* **Malicious calls (`BLOCK`)**: Raise `ShieldBlocked` with explanation; tool body is never executed.
* **Sensitive calls (`HITL`)**: Raise `ShieldEscalated` and route to the dashboard approval desk.

---

## 🚀 Key Features

### 1. Multi-Stage Gateway Decision Pipeline
* **Prompt Injection Defense**: High-speed regex heuristics and semantic scoring to detect jailbreak payloads (`DAN`, `Ignore previous instructions`, indirect delimiters, system prompt leaks).
* **PII Detection & Redaction**: Automatic identification and masking of sensitive identifiers including **PAN cards**, credit cards, phone numbers, and emails.
* **Declarative YAML Policies**: Define granular rules matching tool names, resource types, data classifications, rate limits, and risk thresholds.
* **Granular Verdicts**:
  * `ALLOW`: Safe operation; proceed immediately.
  * `BLOCK`: Threat or hard policy violation; refused with human-readable reasoning.
  * `HITL (Human-in-the-Loop)`: Sensitive operation routed to the dashboard approval desk for supervisor sign-off.

### 2. Tamper-Evident Cryptographic Audit Plane
* Every decision, argument, and verdict is stored in a sequential audit ledger.
* Each entry computes `SHA-256(prev_hash + seq + payload)` and is signed with HMAC signatures. Any database tampering or retroactive modification breaks the hash chain instantly and alerts operators.

### 3. Enterprise Web Dashboard (`/app`)
* **Real-Time Decisions Feed & Dynamic Drawer**: Inspect decisions live with split verdicts (`ALLOW`, `HITL`, `BLOCK`). Click any decision to view security signals (PII tags, injection scores) and tool arguments.
* **Interactive Approvals Desk**: Live Human-in-the-Loop queue with bulk moderation controls.
* **Policy Management & YAML Viewer**: View, toggle, and simulate custom security policies in real-time.
* **Audit Chain Scanner**: Instant verification of audit ledger integrity across all sequence numbers.
* **Global & Tool Kill-Switches**: One-click freeze controls to halt rogue agents or compromised tools instantly.

---

## 📊 Dual-Agent Evaluation Benchmark

AgentShield was benchmarked against a standalone two-agent simulation framework ([Customer Support Agent Demo](https://github.com/Skanda001/Customer-support-agent-demo-for-agent-shield)) running on real PostgreSQL customer data:

* **Customer Simulation Agent**: Groq (`qwen/qwen3.8-27b`) generating 100+ support tickets with realistic attacks (prompt injections, PII exfiltration, unauthorized account deletions, scope escalations).
* **Support Agent**: LangGraph (`openai/gpt-oss-120b`) executing 7 tools gated through AgentShield over HTTP via `@protect`.

| Metric | Result |
| :--- | :--- |
| **False Negatives (Malicious Allowed)** | **0** (100% of high-risk attacks intercepted) |
| **False Positives (Benign Blocked)** | **0** (100% of benign inquiries resolved) |
| **Audit Ledger Integrity** | **Valid** (570+ cryptographic chain entries verified) |

---

## 🛠️ System Architecture

| Tier | Technologies | Role |
| :--- | :--- | :--- |
| **Gateway & Backend** | FastAPI, Python 3.11+, SQLAlchemy 2 (async), Pydantic v2 | High-throughput security proxy, policy engine, and REST API |
| **Database & Cache** | PostgreSQL, Redis, Alembic | Persistent state, cryptographic audit ledger, rate limiting |
| **Frontend Management** | React 18/19, TypeScript, Vite, Tailwind CSS, TanStack Router & Query | Zero-latency reactive dashboard, charts, and operational controls |
| **Python SDK** | Zero-dependency standard-library Python SDK | `@protect` decorator and HTTP client for external agents |
| **Deployment** | Vercel (Frontend), Render (Backend), Docker Compose | Full-stack cloud deployment |

---

## 🏁 Quickstart

### Option 1: Explore the Live Cloud Dashboard
1. Open the [Vercel Dashboard](https://agentshield-eight.vercel.app).
2. Click **"Try Demo"** to explore the UI, inspect sample decisions, review policies, and test the approvals desk.
3. To stream and evaluate real live traffic, connect an agent via API key or run the [Customer Support Agent Demo](https://github.com/Skanda001/Customer-support-agent-demo-for-agent-shield).

### Option 2: Run Locally via Docker Compose

```bash
docker compose up -d
```
Spins up PostgreSQL, Redis, the FastAPI Gateway (`:8000`), and the React Frontend (`:5173`).

### Option 3: Manual Local Setup

#### 1. Backend Gateway
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```
Backend API docs available at: `http://localhost:8000/docs`

#### 2. Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Testing & Verification

Run the full security test suite (risk engine, policy evaluator, injection heuristics, PII masking):

```bash
cd backend
pytest tests/ -v
```

---

## 🛡️ License

MIT License. Designed with security-first engineering for autonomous AI ecosystems.
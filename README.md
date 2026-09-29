# AgentShield 🛡️

> **Zero-Trust Security Gateway, Firewall, and Cryptographic Audit Plane for Autonomous AI Agents.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.0+-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 📌 Executive Summary

Autonomous AI agents (powered by Groq, OpenAI, Anthropic, LangChain, CrewAI) can interact with databases, trigger payments, send emails, and delete records. Without guardrails, a single prompt injection or rogue decision can exfiltrate sensitive data or execute catastrophic transactions.

**AgentShield** sits as an inline Zero-Trust proxy between AI agents and external tools/APIs. Every tool invocation undergoes sub-millisecond inspection, policy evaluation, prompt injection scanning, PII redacting, and tamper-evident audit logging before execution.

```
                     ┌───────────────────────────────────────────────┐
                     │              AgentShield Gateway              │
                     │                                               │
   AI Agent          │   1. Injection & Jailbreak Scanner            │         Tools & APIs
 (Groq / LangChain)  │   2. PII Detection & Auto-Masker              │    (CRM, Email, Payments)
        │            │   3. Declarative Policy Engine (YAML)         │               ▲
        │ Tool Call  │   4. Human-in-the-Loop (HITL) Queue           │               │
        ├───────────►│   5. Emergency Kill-Switch Check              ├───────────────┤ (If ALLOW)
        │            │   6. SHA-256 HMAC Hash-Chained Audit Log      │               │
        │            │                                               │               │
        │◄───────────┴───────────────────────────────────────────────┘               │
   Verdict Response                                                                  │
(ALLOW / BLOCK / HITL)                                                        Executes Safely
```

---

## 🚀 Key Features

### 1. Multi-Stage Gateway Decision Pipeline
* **Prompt Injection Defense**: High-speed regex heuristics and semantic scoring to detect jailbreak payloads (e.g., `DAN`, `Ignore previous instructions`, indirect delimiters, system prompt leaks).
* **PII Detection & Redaction**: Automatic identification and masking of sensitive identifiers including **Aadhaar** (`XXXX XXXX XXXX`), **PAN** (`ABCDE1234F`), credit cards, phone numbers, and emails.
* **Declarative YAML Policies**: Define granular rules matching tool names, resource types, data classifications, rate limits, and risk thresholds.
* **Granular Verdicts**:
  * `ALLOW`: Safe operation; proceed immediately.
  * `BLOCK`: Threat or hard policy violation; refused with human-readable reasoning.
  * `ESCALATE`: Sensitive operation (e.g., identity lookup, refunds over threshold) routed to the **Human-in-the-Loop (HITL)** queue for supervisor sign-off.

### 2. Tamper-Evident Cryptographic Audit Plane
* Every decision, argument, and verdict is stored in a sequential audit ledger.
* Each entry computes `SHA-256(prev_hash + seq + payload)` and is verified with HMAC signatures. Any database tampering or retroactive modification breaks the hash chain instantly and triggers security alerts.

### 3. Enterprise Web Dashboard (`/app`)
* **Real-Time Decisions Feed & Dynamic Drawer**:
  * Inspect decisions live with split verdicts (`ALLOW`, `ESCALATE`, `BLOCK`).
  * Click any decision row to view the dedicated **Groq AI Reasoning & Intent Analysis** drawer, displaying LLM context, security signals (PII tags, injection score percentage), and formatted tool arguments payload.
* **Interactive Approvals Desk**: Live Human-in-the-Loop queue with one-click **Approve All** / **Deny All** bulk moderation.
* **Policy Management & YAML Viewer**: View, toggle, and simulate custom security policies in real-time.
* **Audit Chain Scanner**: Instant verification of audit ledger integrity across all sequence numbers.
* **Global & Tool Kill-Switches**: One-click freeze controls to halt rogue agents or compromised tools instantly with confirmation safety guards.
* **WebSocket Attack Playground (`/app/demo`)**: Live streaming test runner simulating adversarial attacks against real agents in sub-second steps.

---

## 🛠️ System Architecture

| Tier | Technologies | Role |
| :--- | :--- | :--- |
| **Gateway & Backend** | FastAPI, Python 3.11+, SQLAlchemy 2 (async), Pydantic v2 | High-throughput security proxy, policy engine, and REST/WebSocket API |
| **Database & Cache** | PostgreSQL / SQLite, Redis, Alembic | Persistent state, audit ledger, rate limiting, and session cache |
| **Frontend Management** | React 19, TypeScript, Vite, Tailwind CSS, TanStack Router & Query | Zero-latency reactive dashboard, charts, and operational controls |
| **Python SDK** | Zero-dependency standard-library Python SDK | `@protect` decorator and HTTP client for external agents |
| **External Agent** | Groq (`openai/gpt-oss-20b`), IMAP/SMTP, Mock CRM | Decoupled client agent demonstrating production integration |

---

## 🏁 Quickstart

### Prerequisites
* Python 3.11+
* Node.js 18+ and npm
* Git

### Option 1: Run Full Stack Locally (Manual)

#### 1. Backend Gateway
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Backend API docs available at: `http://localhost:8000/docs`

#### 2. Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser. Default login credentials:
* **Email**: `admin@agentshield.dev`
* **Password**: `admin123`

---

### Option 2: Docker Compose (All-in-One)

```bash
docker compose up -d
```
Spins up PostgreSQL, Redis, FastAPI Gateway, and the React Frontend simultaneously.

---

## 🧪 Testing & Verification

The test suite covers unit checks, policy evaluations, regex safety, and injection heuristics:

```bash
cd backend
# Run unit and security tests
pytest tests/unit tests/test_risk_engine.py tests/test_policy_engine.py tests/test_injection.py tests/test_pii.py -v
```

---

## 📁 Repository Structure

```text
agentshield/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI REST & WebSocket routers (decisions, policies, audit, demo)
│   │   ├── core/            # Config, security, database session, JWT auth
│   │   ├── db/              # SQLAlchemy async models & Alembic migrations
│   │   ├── detection/       # Injection heuristics, regex catalog, PII masker
│   │   ├── gateway/         # Decision pipeline & tool adapter
│   │   ├── policy_engine/   # Rule evaluator, condition parser, risk scorer
│   │   └── schemas/         # Pydantic request/response schemas
│   └── sdk/python_sdk/      # Zero-dependency Python SDK client
├── frontend/
│   ├── src/
│   │   ├── components/      # DecisionChart, LiveStream, StatCard, TopBar, Sidebar
│   │   ├── routes/          # TanStack file-based routes (/app, /audit, /policies, /demo)
│   │   └── lib/             # API client, WebSocket stream connector, Auth context
├── agent/                   # Decoupled mock CRM data store (1000-2000 customer spectrum)
└── docker-compose.yml       # Production/development multi-container setup
```

---

## 🛡️ License

MIT License. Designed with security-first engineering for autonomous AI ecosystems.
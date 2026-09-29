# AgentShield Web Console & Security Dashboard 🖥️

> **Production React 19 & TypeScript management interface for the AgentShield Zero-Trust AI Security Gateway.**

[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.0+-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-v4-38B2AC?style=flat&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![TanStack](https://img.shields.io/badge/TanStack-Router%20%26%20Query-FF4154?style=flat)](https://tanstack.com/)

---

## 📌 Overview

The **AgentShield Frontend** provides security analysts, administrators, and developers with real-time visibility and control over autonomous AI agents. Built with **React 19**, **Vite**, and **Tailwind CSS**, it features a dark security-ops UI with live polling, WebSocket streaming, and interactive policy controls.

---

## 🚀 Key Modules & Pages

### 1. Security Operations Dashboard (`/app`)
* **Live Decision Feed**: Displays real-time verdicts (`ALLOW`, `ESCALATE`, `BLOCK`) using TanStack Query polling (`refetchInterval: 5000`) with smooth state preservation (`keepPreviousData`).
* **Decisions Per Minute Chart**: Recharts-powered temporal activity graph bucketing verdicts across time windows.
* **Interactive AI Decision Drawer**:
  * Click any decision row to expand the deep inspection drawer.
  * **Groq AI Reasoning Card**: Renders the exact LLM rationale and context behind why the tool call was made.
  * **Security Signals**: Displays detected PII badges (`AADHAAR`, `PAN`, `EMAIL`), Prompt Injection percentage scores, and matched policy rules.
  * **Tool Arguments Payload**: Clean JSON viewer showing sanitized inputs sent by the agent.

### 2. Approvals Desk (`/app/approvals`)
* **Human-in-the-Loop (HITL) Queue**: Intercepts high-risk operations (e.g., identity checks, financial transfers, refunds).
* **Bulk Review Actions**: Instant **Approve All** or **Deny All** controls for batched operations.
* **Audit Tracing**: Records the reviewer's identity and decision note directly into the cryptographic ledger.

### 3. Adversarial Playground (`/app/demo`)
* **WebSocket Streaming (`ws://.../api/v1/demo/ws`)**: Executes simulated agent workloads and multi-turn attacks live in the browser.
* **Step-by-Step Security Gate Feedback**: Visualizes tool calls, prompt injection attempts, and gateway verdicts in sub-second increments with pulsing loading skeletons.

### 4. Policy Management & Simulator (`/app/policies`)
* **Declarative Rules View**: Inspect all active YAML security policies.
* **Raw Document Viewer**: Toggle between human-readable rule summaries and formatted raw JSON/YAML configuration.
* **Interactive Policy Simulator**: Test hypothetical agent inputs and verify whether they would be allowed, blocked, or escalated before deploying rules.

### 5. Cryptographic Audit Log (`/app/audit`)
* **Ledger Inspector**: Detailed chronological table of all system events with SHA-256 hashes and sequence numbers.
* **Chain Integrity Scanner**: Verifies cryptographic hash continuity. Intelligently distinguishes between normal fresh redeploys and genuine data tampering.

### 6. Emergency Kill-Switch (`/app/kill-switch`)
* **Global Freeze**: Halts all external agent tool executions system-wide with a single click.
* **Tool-Specific Disable**: Granularly disables compromised tools (e.g., `transfer_funds` or `delete_customer`).
* **Safety Confirmation**: Protected by modal confirmation dialogues to prevent accidental triggers.

---

## 🛠️ Tech Stack

* **Core Framework**: React 19, TypeScript
* **Build Tool**: Vite 6
* **Routing**: TanStack Router (Type-safe, file-based routing)
* **Server State**: TanStack Query (React Query)
* **Styling**: Tailwind CSS
* **Icons**: Lucide React
* **Charts**: Recharts

---

## ⚙️ Development & Build Setup

### 1. Install Dependencies
```bash
npm install
```

### 2. Environment Configuration
Create a `.env` file in `frontend/`:
```bash
# Backend Gateway API URL (defaults to http://localhost:8000 if omitted)
VITE_API_URL=http://localhost:8000
```

### 3. Start Development Server
```bash
npm run dev
```
The dashboard runs at `http://localhost:5173`.

### 4. Production Build
```bash
npm run build
```
Creates an optimized production bundle in `dist/`.

---

## 📄 License

MIT License. Part of the AgentShield Zero-Trust ecosystem.

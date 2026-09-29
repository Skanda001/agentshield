# AgentShield Python SDK (`shield`) 🛡️

> **Zero-dependency Python SDK for intercepting and securing AI agent tool calls with AgentShield Zero-Trust Gateway.**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Overview

The **AgentShield Python SDK** enables autonomous AI agents (built with LangChain, CrewAI, AutoGen, LlamaIndex, or raw Python) to enforce Zero-Trust access control on every tool call.

By decorating your tool functions with `@protect`, the SDK:
1. Intercepts the function call and serializes arguments.
2. Performs an HTTP round-trip to the AgentShield gateway (`POST /api/v1/decide`).
3. Sends LLM intent and reasoning (`_reasoning`) to the security dashboard.
4. Executes the local Python function if verdict is `ALLOW`.
5. Raises `ShieldBlocked` or `ShieldEscalated` if the gateway halts or requires supervisor sign-off.

---

## 📦 Installation

```bash
# Install locally in editable mode
pip install -e sdk/python_sdk
```

---

## ⚙️ Configuration

Configure the gateway endpoint and API key via environment variables:

```bash
export AGENTSHIELD_URL="http://localhost:8000"
export AGENTSHIELD_API_KEY="ash_your_agent_api_key_here"
```

Or configure directly in Python:
```python
from shield import ShieldClient

client = ShieldClient(
    gateway_url="http://localhost:8000",
    api_key="ash_your_agent_api_key_here"
)
```

---

## 🚀 Usage

### 1. Basic Tool Protection with `@protect`

```python
from shield import protect, ShieldBlocked, ShieldEscalated

@protect(tool="read_customer", resource_type="customer", data_classification="internal")
def get_customer(customer_id: int) -> dict:
    # Your real database query
    return {"id": customer_id, "name": "Alice Sharma", "status": "Active"}


@protect(tool="delete_customer", resource_type="customer", data_classification="restricted")
def delete_customer(customer_id: int) -> dict:
    # Destructive action
    return {"deleted": True, "id": customer_id}
```

### 2. Handling Verdicts & Attaching AI Reasoning

When an LLM (such as Groq, OpenAI, or Anthropic) decides to invoke a tool, pass the model's reasoning using `_reasoning`:

```python
try:
    # Pass _reasoning to forward LLM intent to the AgentShield dashboard
    result = get_customer(
        customer_id=1003,
        _reasoning="Customer requested their profile address update via support ticket."
    )
    print("Allowed:", result)

except ShieldBlocked as e:
    # The gateway blocked a prompt injection, PII leak, or policy violation
    print(f"Action blocked by AgentShield: {e.reason} (Risk Score: {e.risk_score})")

except ShieldEscalated as e:
    # The gateway escalated to Human-in-the-Loop for supervisor approval
    print(f"Action escalated for review. Approval Reference ID: {e.approval_id}")
```

### 3. Integration with LangChain Tools

```python
from langchain.tools import tool
from shield import protect

@tool
@protect(tool="transfer_funds", resource_type="payment", data_classification="restricted")
def transfer_funds(from_account: str, to_account: str, amount: float) -> str:
    """Transfer funds between accounts."""
    return f"Transferred ${amount} from {from_account} to {to_account}"
```

---

## 📄 License

MIT License. Part of the AgentShield Zero-Trust ecosystem.
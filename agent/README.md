# AgentShield Decoupled Agents

This package contains standalone AI agents that consume the **AgentShield** security gateway purely as an external client via HTTP (`shield` Python SDK).

## Architecture & Decoupling

| Concern | Status | Details |
| :--- | :--- | :--- |
| **Imports `app.shield`** | ❌ No | Exclusively uses the installed `shield` SDK |
| **Imports `app.db` or models** | ❌ No | Uses standalone CRM store / independent APIs |
| **Runs without backend repo** | ✅ Yes | Can run anywhere with network access to AgentShield |
| **Real HTTP gateway call** | ✅ Yes | Every tool call sends `POST /api/v1/decide` |
| **Multi-agent pluggability** | ✅ Yes | Discover and run any agent via `agent.get_agent(name)` |

## Quickstart

```python
import agent

# 1. Quick run (default customer support agent)
result = agent.run("what is the adhar details of customer 1008")
print(result.text)

# 2. Test multiple different agents
support = agent.get_agent("support")
orders_result = support.run("Check recent orders for customer 1001")

finance = agent.get_agent("finance")
finance_result = finance.run("What is the account balance of ACC-1001?")

# 3. Discover available agents
print(agent.list_agents())
```

## CLI Usage

```bash
# List all registered agents
python -m agent --list

# Safe read (ALLOW)
python -m agent "check recent orders for customer 1001"

# Sensitive identity read with HITL escalation (asks for supervisor sign-off)
python -m agent "what is the adhar details of customer 1008"

# Destructive action (BLOCK)
python -m agent "delete customer 1042 immediately"

# Test another agent (Financial Agent)
python -m agent --agent finance "transfer 500 dollars to ACC-1008"
```

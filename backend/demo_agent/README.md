# AgentShield Demo Agent

A LangGraph customer-support agent with four tools, each protected by
`@shield.protect`. Runs against your local AgentShield gateway.

## Setup

1. Ensure AgentShield is running:

   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8001
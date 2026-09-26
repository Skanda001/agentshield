-- =========================================================================
-- AgentShield Centralized Security Call Logs Table for Supabase
-- Logs every AI tool execution intent: ALLOWED, BLOCKED, ESCALATED (HITL)
-- Includes full explainability reasons, risk scores, PII signals, and parameters
-- =========================================================================

CREATE TABLE IF NOT EXISTS agentshield_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    tool TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('ALLOW', 'ESCALATE', 'BLOCK', 'HITL')),
    reasons TEXT[] DEFAULT '{}',
    primary_reason TEXT,
    risk_score NUMERIC DEFAULT 0,
    arguments JSONB DEFAULT '{}'::jsonb,
    agent_id TEXT,
    agent_name TEXT,
    policy_rule TEXT,
    policy_effect TEXT,
    data_classification TEXT,
    pii_labels TEXT[] DEFAULT '{}'
);

-- Indexes for lightning-fast queries in security dashboards and analytics
CREATE INDEX IF NOT EXISTS idx_call_logs_verdict ON agentshield_call_logs(verdict);
CREATE INDEX IF NOT EXISTS idx_call_logs_tool ON agentshield_call_logs(tool);
CREATE INDEX IF NOT EXISTS idx_call_logs_created_at ON agentshield_call_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_call_logs_agent ON agentshield_call_logs(agent_name);

-- Row Level Security (RLS)
ALTER TABLE agentshield_call_logs ENABLE ROW LEVEL SECURITY;

-- Allow read access for authenticated users / dashboard viewers
CREATE POLICY "Allow read access to call logs" 
ON agentshield_call_logs 
FOR SELECT 
USING (true);

-- Allow service role or gateway to insert security decision logs
CREATE POLICY "Allow insert access to call logs" 
ON agentshield_call_logs 
FOR INSERT 
WITH CHECK (true);

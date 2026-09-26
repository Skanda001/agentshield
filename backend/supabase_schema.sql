-- =========================================================================
-- AgentShield Call Logs Table for Supabase
-- Contains ONLY: id, created_at, tool, verdict, and groq_explanation
-- =========================================================================

DROP TABLE IF EXISTS agentshield_call_logs CASCADE;

CREATE TABLE agentshield_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    tool TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('ALLOW', 'ESCALATE', 'BLOCK', 'HITL')),
    groq_explanation TEXT NOT NULL
);

-- Optimize queries for Supabase Table Editor
CREATE INDEX IF NOT EXISTS idx_call_logs_verdict ON agentshield_call_logs(verdict);
CREATE INDEX IF NOT EXISTS idx_call_logs_created_at ON agentshield_call_logs(created_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE agentshield_call_logs ENABLE ROW LEVEL SECURITY;

-- Allow read access
CREATE POLICY "Allow read access to call logs" 
ON agentshield_call_logs 
FOR SELECT 
USING (true);

-- Allow insert access for service role or gateway
CREATE POLICY "Allow insert access to call logs" 
ON agentshield_call_logs 
FOR INSERT 
WITH CHECK (true);

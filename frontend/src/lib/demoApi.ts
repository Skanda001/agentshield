import { api } from "./api";

export type Scenario = {
  name: string;
  description: string;
  steps: number;
};

export type DemoEvent = {
  ts: string;
  run_id: string;
  agent_id: string;
  agent_version: string;
  step: number;
  tool: string;
  args: Record<string, unknown>;
  decision: "ALLOW" | "HITL" | "BLOCK" | "INFO";
  risk: { score: number; model_version: string };
  findings: Array<{
    type: string;
    subtype?: string;
    severity?: string;
    confidence?: number;
    pattern?: string;
  }>;
  execution: { attempted: boolean; executed: boolean };
  audit_id: string | null;
  audit_seq: number | null;
  approval_id: string | null;
  error?: string;
  text?: string; // set on agent.final
};

export async function listScenarios(): Promise<Scenario[]> {
  const r = await api.get("/demo/scenarios");
  return r.data;
}

export async function startRun(opts: {
  runId: string;
  scenario: string;
  mode: "replay" | "live";
  prompt?: string;
}): Promise<{ run_id: string; events: DemoEvent[] }> {
  const r = await api.post("/demo/run", {
    scenario: opts.scenario,
    mode: opts.mode,
    run_id: opts.runId,
    prompt: opts.prompt,
  });
  return r.data;
}

export type ApprovalDecisionResult = {
  ok: boolean;
  status: "approved" | "denied";
  executed: boolean;
  tool: string;
  output: Record<string, unknown> | null;
  agent_response: string;
  updated_event: DemoEvent;
};

export async function decideApproval(
  approvalId: string,
  approved: boolean,
  decidedBy: string,
  note?: string
): Promise<ApprovalDecisionResult> {
  const r = await api.post("/demo/approvals/decide", {
    approval_id: approvalId,
    approved,
    decided_by: decidedBy,
    note,
  });
  return r.data;
}


export async function verifyAuditChain(): Promise<{
  total_events: number;
  verified_events: number;
  valid: boolean;
  broken_at_seq?: number;
  reason?: string;
}> {
  const r = await api.get("/audit/verify");
  return r.data;
}

export type PromptSuggestion = {
  category: string;
  title: string;
  prompt: string;
  expected_verdict: "ALLOW" | "HITL" | "BLOCK";
  description: string;
};

export type AgentPromptResponse = {
  run_id: string;
  prompt: string;
  events: DemoEvent[];
};

export async function runAgentPrompt(opts: {
  runId: string;
  prompt: string;
  model?: string;
}): Promise<AgentPromptResponse> {
  const r = await api.post("/demo/agent/run", {
    run_id: opts.runId,
    prompt: opts.prompt,
    model: opts.model,
  });
  return r.data;
}

export async function getPromptSuggestions(): Promise<PromptSuggestion[]> {
  const r = await api.get("/demo/agent/suggestions");
  return r.data;
}

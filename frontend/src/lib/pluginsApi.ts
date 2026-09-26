import { api } from "./api";

export interface ToolManifest {
  name: string;
  classification: string;
  risk_level: string;
  requires_hitl?: boolean;
  blocked_by_default?: boolean;
}

export interface AgentPlugin {
  id: string;
  name: string;
  version: string;
  category: string;
  description: string;
  author: string;
  entrypoint: string;
  icon: string;
  scopes: string[];
  tools: ToolManifest[];
  is_plugged_in: boolean;
  mount_path: string | null;
  status: "plugged_in" | "unplugged";
  external_path: string;
  last_action_at?: string | null;
  token?: string | null;
}

export interface PlugActionResponse {
  ok: boolean;
  agent_id: string;
  is_plugged_in: boolean;
  mount_path: string | null;
  message: string;
  plugin: AgentPlugin;
}

export interface PluginRunRequest {
  agent_id: string;
  prompt: string;
  run_id?: string;
  auto_approve?: boolean;
}

export interface PluginRunResponse {
  run_id: string;
  agent_id: string;
  prompt: string;
  events: any[];
  final_text: string;
  verdict: "ALLOW" | "HITL" | "BLOCK";
  status: string;
}

export async function listPlugins(): Promise<AgentPlugin[]> {
  const res = await api.get<AgentPlugin[]>("/plugins");
  return res.data;
}

export async function plugInAgent(agentId: string): Promise<PlugActionResponse> {
  const res = await api.post<PlugActionResponse>(`/plugins/${agentId}/plugin`);
  return res.data;
}

export async function plugOutAgent(agentId: string): Promise<PlugActionResponse> {
  const res = await api.post<PlugActionResponse>(`/plugins/${agentId}/plugout`);
  return res.data;
}

export async function runPluginAgent(payload: PluginRunRequest): Promise<PluginRunResponse> {
  const res = await api.post<PluginRunResponse>("/plugins/run", payload);
  return res.data;
}

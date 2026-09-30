import { api } from "./api";

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

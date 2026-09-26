import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  ChevronRight,
  Search,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import { api } from "@/lib/api";

export const Route = createFileRoute("/app/audit")({
  component: Audit,
});

type CallLogItem = {
  id: string;
  created_at: string;
  tool: string;
  verdict: "ALLOW" | "ESCALATE" | "BLOCK" | "HITL";
  reasons: string[];
  primary_reason: string;
  risk_score: number;
  arguments: Record<string, unknown>;
  agent_id: string;
  policy_rule?: string | null;
  policy_effect?: string | null;
  data_classification?: string | null;
};

function Audit() {
  const qc = useQueryClient();
  const [verdictFilter, setVerdictFilter] = useState<"ALL" | "ALLOW" | "ESCALATE" | "BLOCK">("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // 1. Logs Query (backend endpoint provides all decisions with reasons)
  const {
    data: callLogs = [],
    isLoading: loadingLogs,
    refetch: refetchLogs,
  } = useQuery<CallLogItem[]>({
    queryKey: ["audit-call-logs", verdictFilter],
    queryFn: async () => {
      const params: Record<string, string> = { limit: "200" };
      if (verdictFilter !== "ALL") {
        params.verdict = verdictFilter;
      }
      return (await api.get("/audit/logs", { params })).data;
    },
    refetchInterval: 10000,
  });

  // 2. Chain Verification Query
  const { data: verify, refetch: refetchVerify } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: async () => (await api.get("/audit/verify")).data,
    refetchInterval: 10000,
  });

  const valid = verify?.valid;

  async function handleRefresh() {
    await Promise.all([refetchLogs(), refetchVerify()]);
  }

  // Filter logs by search query
  const filteredLogs = callLogs.filter((log) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      log.tool.toLowerCase().includes(q) ||
      (log.primary_reason && log.primary_reason.toLowerCase().includes(q)) ||
      JSON.stringify(log.arguments).toLowerCase().includes(q)
    );
  });

  const totalCount = callLogs.length;
  const allowCount = callLogs.filter((l) => l.verdict === "ALLOW").length;
  const escalateCount = callLogs.filter((l) => l.verdict === "ESCALATE" || l.verdict === "HITL").length;
  const blockCount = callLogs.filter((l) => l.verdict === "BLOCK").length;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Audit Log"
        description="All tool calls, policy decisions, and cryptographic proofs."
        actions={
          <button onClick={handleRefresh} className="btn-ghost text-xs">
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        }
      />

      {/* Cryptographic Chain Banner */}
      {verify && (
        <div
          className={`card px-4 py-3 flex items-center justify-between border ${
            valid ? "border-emerald-500/30 bg-emerald-950/20" : "border-rose-500/30 bg-rose-950/20"
          }`}
        >
          <div className="flex items-center gap-3">
            {valid ? (
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
            ) : (
              <ShieldAlert className="w-5 h-5 text-rose-400" />
            )}
            <div>
              <div className="text-xs font-semibold text-white">
                {valid ? "Cryptographic Chain Verified" : "Chain Integrity Error"}
              </div>
              <div className="text-[11px] text-slate-400">
                {valid
                  ? `${verify.total_events} events checked · SHA-256 hashes and HMAC signatures valid`
                  : `Failed at seq #${verify.broken_at_seq}: ${verify.reason}`}
              </div>
            </div>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
            HMAC-SHA256
          </span>
        </div>
      )}

      {/* Clean Metrics Strip */}
      <div className="grid grid-cols-4 gap-3">
        <div className="card p-3 border-slate-800">
          <div className="text-[11px] text-slate-400">Total Calls</div>
          <div className="text-lg font-bold text-white mt-0.5">{totalCount}</div>
        </div>
        <div className="card p-3 border-slate-800">
          <div className="text-[11px] text-emerald-400">Allowed</div>
          <div className="text-lg font-bold text-emerald-300 mt-0.5">{allowCount}</div>
        </div>
        <div className="card p-3 border-slate-800">
          <div className="text-[11px] text-amber-400">Escalated (HITL)</div>
          <div className="text-lg font-bold text-amber-300 mt-0.5">{escalateCount}</div>
        </div>
        <div className="card p-3 border-slate-800">
          <div className="text-[11px] text-rose-400">Blocked</div>
          <div className="text-lg font-bold text-rose-300 mt-0.5">{blockCount}</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter by tool or reason..."
            className="input pl-9 text-xs w-full"
          />
        </div>

        <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800">
          {(["ALL", "ALLOW", "ESCALATE", "BLOCK"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setVerdictFilter(v)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                verdictFilter === v
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {v === "ALL" ? "All" : v === "ALLOW" ? "Allowed" : v === "ESCALATE" ? "Escalated" : "Blocked"}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {loadingLogs ? (
        <LoadingState label="Loading audit logs…" />
      ) : filteredLogs.length === 0 ? (
        <EmptyState
          title="No decisions found"
          description="Try changing the filter or search query."
        />
      ) : (
        <div className="card overflow-hidden border-slate-800">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left table-fixed">
              <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800 font-mono text-[11px] uppercase">
                <tr>
                  <th className="px-4 py-2.5 w-[110px]">Verdict</th>
                  <th className="px-4 py-2.5 w-[180px]">Tool</th>
                  <th className="px-4 py-2.5">Reason</th>
                  <th className="px-4 py-2.5 w-[70px] text-right">Risk</th>
                  <th className="px-4 py-2.5 w-[110px] text-right">Time</th>
                  <th className="w-[40px] px-2 text-center" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredLogs.map((log) => {
                  const isExpanded = expandedId === log.id;
                  const isAllow = log.verdict === "ALLOW";
                  const isEscalate = log.verdict === "ESCALATE" || log.verdict === "HITL";

                  return (
                    <Fragment key={log.id}>
                      <tr
                        onClick={() => setExpandedId(isExpanded ? null : log.id)}
                        className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                      >
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono font-semibold ${
                              isAllow
                                ? "bg-emerald-950/60 text-emerald-400 border border-emerald-500/20"
                                : isEscalate
                                ? "bg-amber-950/60 text-amber-400 border border-amber-500/20"
                                : "bg-rose-950/60 text-rose-400 border border-rose-500/20"
                            }`}
                          >
                            {isAllow ? (
                              <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                            ) : isEscalate ? (
                              <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                            ) : (
                              <XCircle className="w-3 h-3 text-rose-400 shrink-0" />
                            )}
                            <span>{log.verdict}</span>
                          </span>
                        </td>
                        <td className="px-4 py-2.5 font-mono text-slate-200 truncate">
                          {log.tool}
                        </td>
                        <td className="px-4 py-2.5 text-slate-300 truncate">
                          {log.primary_reason || "Policy evaluated"}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-slate-400 text-right">
                          {log.risk_score?.toFixed(0) ?? 0}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-slate-400 text-right whitespace-nowrap">
                          {new Date(log.created_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </td>
                        <td className="px-2 py-2.5 text-center">
                          <ChevronRight
                            className={`w-3.5 h-3.5 text-slate-500 transition-transform inline-block ${
                              isExpanded ? "rotate-90 text-slate-300" : ""
                            }`}
                          />
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="bg-slate-900/60">
                          <td colSpan={6} className="px-5 py-3 space-y-2">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              <div>
                                <div className="text-[10px] font-mono text-slate-400 uppercase mb-1">
                                  Arguments
                                </div>
                                <pre className="p-2.5 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                                  {JSON.stringify(log.arguments, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <div className="text-[10px] font-mono text-slate-400 uppercase mb-1">
                                  Reasons & Policy Signals
                                </div>
                                <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-[11px] text-slate-300 space-y-1">
                                  {log.reasons && log.reasons.length > 0 ? (
                                    log.reasons.map((r, i) => (
                                      <div key={i} className="flex items-start gap-1.5">
                                        <span className="text-slate-500">•</span>
                                        <span>{r}</span>
                                      </div>
                                    ))
                                  ) : (
                                    <span className="text-slate-500 italic">No additional signals.</span>
                                  )}
                                  {log.data_classification && (
                                    <div className="pt-1.5 border-t border-slate-800 text-slate-400">
                                      Classification: <span className="text-white font-mono">{log.data_classification}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="text-[10px] font-mono text-slate-500 pt-1 flex justify-between">
                              <span>Decision ID: {log.id}</span>
                              <span>Agent ID: {log.agent_id}</span>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
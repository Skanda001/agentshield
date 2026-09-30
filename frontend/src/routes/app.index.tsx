import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { ShieldCheck, ShieldX, AlertTriangle, UserCheck, ChevronRight, Sparkles, Terminal, Shield } from "lucide-react";
import { useState } from "react";
import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";
import AuditStatusCard from "@/components/AuditStatusCard";
import LiveStream from "@/components/LiveStream";
import DecisionChart from "@/components/DecisionChart";
import VerdictBadge from "@/components/VerdictBadge";
import { api } from "@/lib/api";

export const Route = createFileRoute("/app/")({
  component: Dashboard,
});

type Decision = {
  id: string;
  tool: string;
  verdict: string;
  risk_score: number;
  created_at: string;
  reasons: string[];
  arguments?: Record<string, unknown>;
  note?: string;
  policy_rule?: string;
  injection_score?: number;
  pii_labels?: string[];
  masked?: boolean;
};

type Approval = {
  id: string;
  decision_id: string;
  status: string;
};

function Dashboard() {
  const [expandedDecisionId, setExpandedDecisionId] = useState<string | null>(null);

  // Fix #9: limit=50 matches backend default; Fix #12: keepPreviousData prevents blank flash on refetch
  const { data: decisions = [] } = useQuery<Decision[]>({
    queryKey: ["decisions"],
    queryFn: async () => (await api.get("/decisions?limit=50")).data,
    refetchInterval: 5000,
    placeholderData: keepPreviousData,
  });

  const { data: approvals = [] } = useQuery<Approval[]>({
    queryKey: ["approvals-all"],
    queryFn: async () => (await api.get("/approvals?limit=500")).data,
    refetchInterval: 5000,
    placeholderData: keepPreviousData,
  });

  const counts = {
    allow: decisions.filter((d) => d.verdict === "ALLOW").length,
    escalate: decisions.filter((d) => d.verdict === "HITL").length,
    block: decisions.filter((d) => d.verdict === "BLOCK").length,
    denied: approvals.filter((a) => a.status === "denied").length,
    approved: approvals.filter((a) => a.status === "approved").length,
    pending: approvals.filter((a) => a.status === "pending").length,
  };

  const approvalByDecision: Record<string, Approval> = {};
  for (const a of approvals) approvalByDecision[a.decision_id] = a;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Overview of agent activity and security posture."
      />

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Allowed" value={counts.allow} color="success" icon={ShieldCheck} />
        <StatCard
          label="Escalated"
          value={counts.escalate}
          color="warn"
          icon={AlertTriangle}
          subtitle={`${counts.pending} awaiting approval`}
        />
        <StatCard label="Blocked" value={counts.block} color="danger" icon={ShieldX} />
        <StatCard
          label="Human Decisions"
          value={counts.approved + counts.denied}
          color="accent"
          icon={UserCheck}
          subtitle={`${counts.approved} approved · ${counts.denied} denied`}
        />
      </div>

      {/* Audit status */}
      <div className="mb-6">
        <AuditStatusCard />
      </div>

      {/* Chart + Live stream */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <DecisionChart />
        <LiveStream />
      </div>

      {/* Recent decisions table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <span className="font-semibold text-sm">Recent decisions</span>
          {/* Fix #9: show all 50 */}
          <span className="text-xs text-gray-500">
            showing latest {Math.min(50, decisions.length)} of {decisions.length}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-gray-400 border-b border-border text-xs uppercase tracking-wide">
              <tr>
                {/* Fix #11: expand chevron column */}
                <th className="px-3 py-3 w-6" />
                {/* Fix #10: date + time column */}
                <th className="text-left px-5 py-3 font-medium">Time</th>
                <th className="text-left px-5 py-3 font-medium">Tool</th>
                <th className="text-left px-5 py-3 font-medium">Verdict</th>
                <th className="text-left px-5 py-3 font-medium">Approval</th>
                <th className="text-right px-5 py-3 font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {decisions.slice(0, 50).map((d) => {
                const ap = approvalByDecision[d.id];
                const reasons = d.reasons ?? [];
                const isExpanded = expandedDecisionId === d.id;
                const colorClass =
                  d.verdict === "BLOCK"
                    ? "text-danger/70"
                    : d.verdict === "HITL"
                    ? "text-warn/70"
                    : "text-gray-500";

                return (
                  <>
                    {/* Fix #11: clickable row */}
                    <tr
                      key={d.id}
                      onClick={() =>
                        setExpandedDecisionId(isExpanded ? null : d.id)
                      }
                      className="border-b border-border/40 hover:bg-panel-hover transition-colors cursor-pointer select-none"
                    >
                      <td className="pl-3 pr-1 py-3 align-top text-gray-500">
                        <ChevronRight
                          size={14}
                          className={`transition-transform duration-150 ${
                            isExpanded ? "rotate-90" : ""
                          }`}
                        />
                      </td>
                      {/* Fix #10: date + time */}
                      <td className="px-5 py-3 text-gray-500 font-mono text-xs align-top whitespace-nowrap">
                        <div>
                          {new Date(d.created_at).toLocaleDateString([], {
                            month: "short",
                            day: "numeric",
                          })}
                        </div>
                        <div className="text-[11px]">
                          {new Date(d.created_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </div>
                      </td>
                      <td className="px-5 py-3 align-top">
                        <div className="font-mono text-xs font-semibold text-slate-200">
                          {d.tool}
                        </div>
                        {d.policy_rule ? (
                          <span className="inline-block text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-400 border border-slate-700/50 mt-1">
                            {d.policy_rule}
                          </span>
                        ) : reasons.length > 0 ? (
                          <span className="text-[11px] text-slate-500 mt-0.5 block truncate max-w-[220px]">
                            {reasons[0]}
                          </span>
                        ) : null}
                      </td>
                      <td className="px-5 py-3 align-top">
                        <VerdictBadge verdict={d.verdict} />
                      </td>
                      <td className="px-5 py-3 align-top">
                        {ap ? (
                          <ApprovalBadge status={ap.status} />
                        ) : (
                          <span className="text-gray-700 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right text-xs text-gray-400 font-mono align-top">
                        {Math.round(d.risk_score)}
                      </td>
                    </tr>

                    {/* Expandable detail row: Groq reasoning, security signals, payload */}
                    {isExpanded && (() => {
                      const groqReasoning =
                        d.note ||
                        (d.arguments?._reasoning as string) ||
                        (d.arguments?.reasoning as string) ||
                        (d.arguments?.intent as string);

                      const cleanArgs = d.arguments ? { ...d.arguments } : null;
                      if (cleanArgs) {
                        delete cleanArgs._reasoning;
                        delete cleanArgs.reasoning;
                        delete cleanArgs.intent;
                      }
                      const hasCleanArgs = cleanArgs && Object.keys(cleanArgs).length > 0;

                      return (
                        <tr
                          key={`${d.id}-detail`}
                          className="bg-slate-900/60 border-b border-border/60"
                        >
                          <td />
                          <td colSpan={5} className="px-5 py-4">
                            <div className="space-y-3.5">
                              {/* Groq AI Reasoning Card */}
                              {groqReasoning ? (
                                <div className="rounded-lg bg-indigo-950/30 border border-indigo-500/20 p-3.5 space-y-1.5">
                                  <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                                    <Sparkles className="w-3.5 h-3.5" />
                                    <span>AI Reasoning & Intent Analysis (Groq)</span>
                                  </div>
                                  <p className="text-xs text-slate-200 leading-relaxed font-sans">
                                    {groqReasoning}
                                  </p>
                                </div>
                              ) : (
                                <div className="rounded-lg bg-slate-950/50 border border-slate-800/80 p-3 text-xs text-slate-400 flex items-center gap-2">
                                  <Sparkles className="w-3.5 h-3.5 text-slate-500" />
                                  <span>Automated gateway decision (no LLM reasoning payload attached)</span>
                                </div>
                              )}

                              {/* Security Signals & Policy Summary */}
                              <div className="flex flex-wrap items-center gap-2 text-xs">
                                {d.policy_rule && (
                                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 font-mono text-[11px] border border-slate-700">
                                    <Shield className="w-3 h-3 text-blue-400" />
                                    Rule: {d.policy_rule}
                                  </span>
                                )}
                                {d.injection_score !== undefined && d.injection_score > 0 && (
                                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-rose-500/10 text-rose-300 font-mono text-[11px] border border-rose-500/30">
                                    Injection Score: {Math.round(d.injection_score * 100)}%
                                  </span>
                                )}
                                {d.pii_labels && d.pii_labels.length > 0 && (
                                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-300 font-mono text-[11px] border border-amber-500/30">
                                    PII Detected: {d.pii_labels.join(", ")}
                                  </span>
                                )}
                                {d.masked && (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] border border-emerald-500/20">
                                    Masked
                                  </span>
                                )}
                              </div>

                              {/* Tool Call Arguments Payload */}
                              {hasCleanArgs && (
                                <div>
                                  <div className="flex items-center gap-1.5 text-slate-400 font-semibold uppercase tracking-wide text-[10px] mb-1.5">
                                    <Terminal className="w-3 h-3" />
                                    <span>Tool Arguments Payload</span>
                                  </div>
                                  <pre className="text-[11px] font-mono text-slate-300 bg-slate-950 border border-slate-800 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap break-all">
                                    {JSON.stringify(cleanArgs, null, 2)}
                                  </pre>
                                </div>
                              )}

                              {/* Gateway Verification Triggers */}
                              {reasons.length > 0 && (
                                <div>
                                  <span className="text-slate-400 font-semibold uppercase tracking-wide text-[10px]">
                                    Gateway Verification Triggers
                                  </span>
                                  <ul className="mt-1 space-y-0.5 list-disc list-inside">
                                    {reasons.map((r, idx) => (
                                      <li key={idx} className={`${colorClass} text-[11px]`}>
                                        {r}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })()}
                  </>
                );
              })}
              {decisions.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-5 py-12 text-center text-gray-500"
                  >
                    No decisions yet. Click{" "}
                    <b className="text-accent">Run demo</b> in the top bar.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function ApprovalBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    approved: "bg-success-soft text-success border-success/30",
    denied: "bg-danger-soft text-danger border-danger/30",
    pending: "bg-warn-soft text-warn border-warn/30",
    expired: "bg-panel text-gray-400 border-border",
  };
  const cls = map[status] || map.expired;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${cls}`}
    >
      {status}
    </span>
  );
}
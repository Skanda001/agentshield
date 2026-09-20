import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, ShieldX, AlertTriangle, UserCheck } from "lucide-react";
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
};

type Approval = {
  id: string;
  decision_id: string;
  status: string;
};

function Dashboard() {
  const { data: decisions = [] } = useQuery<Decision[]>({
    queryKey: ["decisions"],
    queryFn: async () => (await api.get("/decisions?limit=200")).data,
    refetchInterval: 5000,
  });

  const { data: approvals = [] } = useQuery<Approval[]>({
    queryKey: ["approvals-all"],
    queryFn: async () => (await api.get("/approvals?limit=500")).data,
    refetchInterval: 5000,
  });

  const counts = {
    allow: decisions.filter((d) => d.verdict === "ALLOW").length,
    escalate: decisions.filter((d) => d.verdict === "ESCALATE").length,
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
        <StatCard
          label="Allowed"
          value={counts.allow}
          color="success"
          icon={ShieldCheck}
        />
        <StatCard
          label="Escalated"
          value={counts.escalate}
          color="warn"
          icon={AlertTriangle}
          subtitle={`${counts.pending} awaiting approval`}
        />
        <StatCard
          label="Blocked"
          value={counts.block}
          color="danger"
          icon={ShieldX}
        />
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
          <span className="text-xs text-gray-500">
            showing latest {Math.min(25, decisions.length)} of {decisions.length}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-gray-400 border-b border-border text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-5 py-3 font-medium">Time</th>
                <th className="text-left px-5 py-3 font-medium">Tool</th>
                <th className="text-left px-5 py-3 font-medium">Verdict</th>
                <th className="text-left px-5 py-3 font-medium">Approval</th>
                <th className="text-right px-5 py-3 font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {decisions.slice(0, 25).map((d) => {
                const ap = approvalByDecision[d.id];
                return (
                  <tr
                    key={d.id}
                    className="border-b border-border/40 hover:bg-panel-hover transition-colors"
                  >
                    <td className="px-5 py-3 text-gray-500 font-mono text-xs">
                      {new Date(d.created_at).toLocaleTimeString()}
                    </td>
                    <td className="px-5 py-3 font-mono text-xs">{d.tool}</td>
                    <td className="px-5 py-3">
                      <VerdictBadge verdict={d.verdict} />
                    </td>
                    <td className="px-5 py-3">
                      {ap ? (
                        <ApprovalBadge status={ap.status} />
                      ) : (
                        <span className="text-gray-700 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right text-xs text-gray-400 font-mono">
                      {Math.round(d.risk_score)}
                    </td>
                  </tr>
                );
              })}
              {decisions.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-5 py-12 text-center text-gray-500"
                  >
                    No decisions yet. Click <b className="text-accent">Run demo</b> in the top bar.
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
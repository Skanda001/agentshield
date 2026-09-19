import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export const Route = createFileRoute("/")({
  component: Dashboard,
});

type Decision = {
  id: string;
  tool: string;
  verdict: string;
  risk_score: number;
  created_at: string;
};

type Approval = {
  id: string;
  decision_id: string;
  tool: string;
  status: string;
  decided_by?: string;
  decided_at?: string;
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

  const { data: audit } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: async () => (await api.get("/audit/verify")).data,
    refetchInterval: 10000,
  });

  const counts = {
    allow: decisions.filter((d) => d.verdict === "ALLOW").length,
    escalate: decisions.filter((d) => d.verdict === "ESCALATE").length,
    block: decisions.filter((d) => d.verdict === "BLOCK").length,
    denied: approvals.filter((a) => a.status === "denied").length,
    approved: approvals.filter((a) => a.status === "approved").length,
    pending: approvals.filter((a) => a.status === "pending").length,
  };

  // Map decision_id -> approval for joined rendering
  const approvalByDecision: Record<string, Approval> = {};
  for (const a of approvals) {
    approvalByDecision[a.decision_id] = a;
  }

  return (
    <div className="space-y-8">
      <h2 className="text-3xl font-bold">Dashboard</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Allowed" value={counts.allow} color="text-success" />
        <StatCard label="Escalated" value={counts.escalate} color="text-warn" />
        <StatCard label="Blocked" value={counts.block} color="text-danger" />
        <StatCard
          label="Human Decisions"
          value={counts.denied + counts.approved}
          color="text-accent"
          subtitle={`${counts.approved} approved · ${counts.denied} denied · ${counts.pending} pending`}
        />
      </div>

      <div className="p-6 border border-border rounded-lg bg-panel">
        <h3 className="font-semibold mb-3">Audit Chain</h3>
        {audit ? (
          <div className="flex items-center gap-3">
            <span
              className={`w-3 h-3 rounded-full ${
                audit.valid ? "bg-success" : "bg-danger"
              }`}
            />
            <span>
              {audit.valid
                ? `Verified — ${audit.total_events} events`
                : `BROKEN at event ${audit.broken_at_seq}: ${audit.reason}`}
            </span>
          </div>
        ) : (
          <span className="text-gray-400">Loading…</span>
        )}
      </div>

      <div className="border border-border rounded-lg bg-panel overflow-hidden">
        <div className="px-6 py-4 border-b border-border font-semibold">
          Recent Decisions
        </div>
        <table className="w-full text-sm">
          <thead className="text-gray-400 border-b border-border">
            <tr>
              <th className="text-left px-6 py-3">Time</th>
              <th className="text-left px-6 py-3">Tool</th>
              <th className="text-left px-6 py-3">Verdict</th>
              <th className="text-left px-6 py-3">Approval</th>
              <th className="text-right px-6 py-3">Risk</th>
            </tr>
          </thead>
          <tbody>
            {decisions.slice(0, 25).map((d) => {
              const ap = approvalByDecision[d.id];
              return (
                <tr key={d.id} className="border-b border-border/50">
                  <td className="px-6 py-3 text-gray-400">
                    {new Date(d.created_at).toLocaleTimeString()}
                  </td>
                  <td className="px-6 py-3 font-mono">{d.tool}</td>
                  <td className="px-6 py-3">
                    <VerdictBadge verdict={d.verdict} />
                  </td>
                  <td className="px-6 py-3">
                    {ap ? <ApprovalBadge status={ap.status} /> : (
                      <span className="text-gray-600 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-right">
                    {Math.round(d.risk_score)}
                  </td>
                </tr>
              );
            })}
            {decisions.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-gray-400">
                  No decisions yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
  subtitle,
}: {
  label: string;
  value: number;
  color: string;
  subtitle?: string;
}) {
  return (
    <div className="border border-border rounded-lg bg-panel p-6">
      <div className="text-sm text-gray-400">{label}</div>
      <div className={`text-3xl font-bold mt-2 ${color}`}>{value}</div>
      {subtitle && (
        <div className="text-xs text-gray-500 mt-2">{subtitle}</div>
      )}
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const cls =
    verdict === "ALLOW"
      ? "bg-success/20 text-success"
      : verdict === "BLOCK"
      ? "bg-danger/20 text-danger"
      : "bg-warn/20 text-warn";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {verdict}
    </span>
  );
}

function ApprovalBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    approved: "bg-success/20 text-success",
    denied: "bg-danger/20 text-danger",
    pending: "bg-warn/20 text-warn",
    expired: "bg-gray-500/20 text-gray-400",
  };
  const cls = map[status] || "bg-gray-500/20 text-gray-400";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {status}
    </span>
  );
}
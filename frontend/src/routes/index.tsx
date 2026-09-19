import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export const Route = createFileRoute("/")({
  component: Dashboard,
});

function Dashboard() {
  const { data: decisions = [] } = useQuery({
    queryKey: ["decisions"],
    queryFn: async () => (await api.get("/decisions?limit=100")).data,
    refetchInterval: 5000,
  });

  const counts = {
    allow: decisions.filter((d: any) => d.verdict === "ALLOW").length,
    escalate: decisions.filter((d: any) => d.verdict === "ESCALATE").length,
    block: decisions.filter((d: any) => d.verdict === "BLOCK").length,
  };

  const { data: audit } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: async () => (await api.get("/audit/verify")).data,
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-8">
      <h2 className="text-3xl font-bold">Dashboard</h2>

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Allowed" value={counts.allow} color="text-success" />
        <StatCard label="Escalated" value={counts.escalate} color="text-warn" />
        <StatCard label="Blocked" value={counts.block} color="text-danger" />
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
              <th className="text-left px-6 py-3">Risk</th>
            </tr>
          </thead>
          <tbody>
            {decisions.slice(0, 20).map((d: any) => (
              <tr key={d.id} className="border-b border-border/50">
                <td className="px-6 py-3 text-gray-400">
                  {new Date(d.created_at).toLocaleTimeString()}
                </td>
                <td className="px-6 py-3 font-mono">{d.tool}</td>
                <td className="px-6 py-3">
                  <VerdictBadge verdict={d.verdict} />
                </td>
                <td className="px-6 py-3">{Math.round(d.risk_score)}</td>
              </tr>
            ))}
            {decisions.length === 0 && (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-gray-400">
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

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="border border-border rounded-lg bg-panel p-6">
      <div className="text-sm text-gray-400">{label}</div>
      <div className={`text-3xl font-bold mt-2 ${color}`}>{value}</div>
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
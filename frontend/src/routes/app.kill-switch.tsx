import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Zap, PowerOff, AlertTriangle } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import { api } from "@/lib/api";

export const Route = createFileRoute("/app/kill-switch")({
  component: KillSwitch,
});

type KillSwitchRow = {
  id: string;
  scope: "global" | "tenant" | "agent" | "tool";
  target_id: string | null;
  reason: string;
  is_active: boolean;
  activated_by: string;
  activated_at: string;
  deactivated_by: string | null;
  deactivated_at: string | null;
};

function KillSwitch() {
  const qc = useQueryClient();
  const [globalReason, setGlobalReason] = useState("Manual activation via UI");
  const [toolName, setToolName] = useState("send_email");
  const [toolReason, setToolReason] = useState("Tool disabled for security review");

  const { data: switches = [] } = useQuery<KillSwitchRow[]>({
    queryKey: ["kill-switches"],
    queryFn: async () => (await api.get("/kill-switch?limit=200")).data,
    refetchInterval: 5000,
  });

  const activate = useMutation({
    mutationFn: async (body: {
      scope: string;
      target_id: string | null;
      reason: string;
    }) =>
      api.post("/kill-switch/activate", {
        ...body,
        activated_by: "ui-operator",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["kill-switches"] }),
  });

  const deactivate = useMutation({
    mutationFn: async (id: string) =>
      api.post(`/kill-switch/${id}/deactivate`, {
        deactivated_by: "ui-operator",
        note: "Deactivated via UI",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["kill-switches"] }),
  });

  const active = switches.filter((s) => s.is_active);

  return (
    <>
      <PageHeader
        title="Kill Switch"
        description="Emergency controls to suspend agents or tools immediately."
      />

      {/* Global freeze */}
      <div className="card border-danger/30 bg-danger-soft/40 p-6 mb-6">
        <div className="flex items-start gap-4 mb-4">
          <div className="w-10 h-10 rounded-xl bg-danger-soft flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-danger" />
          </div>
          <div>
            <div className="font-semibold text-white">
              Emergency Global Freeze
            </div>
            <div className="text-sm text-gray-400 mt-0.5">
              Blocks every tool call from every agent until deactivated.
            </div>
          </div>
        </div>

        <input
          value={globalReason}
          onChange={(e) => setGlobalReason(e.target.value)}
          placeholder="Reason for activation"
          className="w-full px-3 py-2 bg-bg border border-border rounded-lg mb-3 text-sm focus:border-danger focus:outline-none"
        />

        <button
          onClick={() =>
            activate.mutate({
              scope: "global",
              target_id: null,
              reason: globalReason,
            })
          }
          disabled={activate.isPending || !globalReason.trim()}
          className="btn-danger"
        >
          <Zap className="w-4 h-4" />
          {activate.isPending ? "Activating…" : "Activate Global Freeze"}
        </button>
      </div>

      {/* Per-tool kill */}
      <div className="card p-6 mb-6">
        <div className="font-semibold mb-4 flex items-center gap-2">
          <PowerOff className="w-4 h-4 text-warn" />
          Disable a specific tool
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">
              Tool name
            </label>
            <input
              value={toolName}
              onChange={(e) => setToolName(e.target.value)}
              placeholder="e.g. send_email"
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">
              Reason
            </label>
            <input
              value={toolReason}
              onChange={(e) => setToolReason(e.target.value)}
              placeholder="Why"
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        <button
          onClick={() =>
            activate.mutate({
              scope: "tool",
              target_id: toolName.trim(),
              reason: toolReason,
            })
          }
          disabled={
            activate.isPending || !toolName.trim() || !toolReason.trim()
          }
          className="btn-ghost border-warn/40 text-warn hover:bg-warn-soft"
        >
          <PowerOff className="w-4 h-4" />
          {activate.isPending ? "Activating…" : "Disable tool"}
        </button>
      </div>

      {/* Active switches */}
      <div className="mb-6">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          Active switches
          <span className="text-xs text-gray-500 font-normal">
            ({active.length})
          </span>
        </h3>

        {active.length === 0 ? (
          <EmptyState
            title="No active kill switches"
            description="All agents and tools are operating normally."
          />
        ) : (
          <div className="space-y-2">
            {active.map((s) => (
              <div
                key={s.id}
                className="card p-4 flex items-center justify-between gap-4 flex-wrap border-danger/30"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-danger animate-pulse-soft" />
                    <span className="font-mono text-sm">
                      {s.scope}
                      {s.target_id ? `: ${s.target_id}` : ""}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {s.reason} — activated by {s.activated_by}
                  </div>
                </div>
                <button
                  onClick={() => deactivate.mutate(s.id)}
                  disabled={deactivate.isPending}
                  className="btn-ghost text-sm"
                >
                  Deactivate
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* History */}
      <div>
        <h3 className="font-semibold mb-3">History</h3>
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-gray-400 border-b border-border text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-5 py-3 font-medium">Scope</th>
                <th className="text-left px-5 py-3 font-medium">Target</th>
                <th className="text-left px-5 py-3 font-medium">Reason</th>
                <th className="text-left px-5 py-3 font-medium">By</th>
                <th className="text-left px-5 py-3 font-medium">When</th>
                <th className="text-right px-5 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {switches.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-5 py-8 text-center text-gray-500"
                  >
                    No history yet.
                  </td>
                </tr>
              )}
              {switches.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-border/40 hover:bg-panel-hover transition-colors"
                >
                  <td className="px-5 py-3 font-mono text-xs">{s.scope}</td>
                  <td className="px-5 py-3 font-mono text-xs text-gray-400">
                    {s.target_id || "—"}
                  </td>
                  <td className="px-5 py-3 text-xs text-gray-400 max-w-md truncate">
                    {s.reason}
                  </td>
                  <td className="px-5 py-3 text-xs text-gray-400">
                    {s.activated_by}
                  </td>
                  <td className="px-5 py-3 text-xs text-gray-500">
                    {new Date(s.activated_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {s.is_active ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold bg-danger-soft text-danger border border-danger/30">
                        active
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold bg-panel text-gray-500 border border-border">
                        inactive
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
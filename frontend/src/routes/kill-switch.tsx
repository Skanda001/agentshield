import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";

export const Route = createFileRoute("/kill-switch")({
  component: KillSwitch,
});

function KillSwitch() {
  const qc = useQueryClient();
  const [reason, setReason] = useState("Manual activation via UI");

  const { data: switches = [] } = useQuery({
    queryKey: ["kill-switches"],
    queryFn: async () => (await api.get("/kill-switch")).data,
    refetchInterval: 5000,
  });

  const activate = useMutation({
    mutationFn: async () =>
      api.post("/kill-switch/activate", {
        scope: "global",
        target_id: null,
        reason,
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

  const active = switches.filter((s: any) => s.is_active);

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Kill Switch</h2>

      <div className="border border-danger/40 rounded-lg bg-danger/10 p-6">
        <h3 className="font-semibold mb-3">Emergency Global Freeze</h3>
        <p className="text-sm text-gray-300 mb-4">
          Immediately blocks every tool call from every agent.
        </p>
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason"
          className="w-full px-3 py-2 bg-bg border border-border rounded mb-3 text-sm"
        />
        <button
          onClick={() => activate.mutate()}
          disabled={activate.isPending}
          className="px-4 py-2 bg-danger hover:brightness-110 rounded font-semibold"
        >
          {activate.isPending ? "Activating…" : "Activate Global Freeze"}
        </button>
      </div>

      <div>
        <h3 className="font-semibold mb-3">Active Switches ({active.length})</h3>
        {active.length === 0 && (
          <div className="text-gray-400 text-sm">None active.</div>
        )}
        {active.map((s: any) => (
          <div
            key={s.id}
            className="border border-border rounded-lg bg-panel p-4 mb-2 flex items-center justify-between"
          >
            <div>
              <div className="font-mono text-sm">
                {s.scope}
                {s.target_id ? `:${s.target_id}` : ""}
              </div>
              <div className="text-xs text-gray-400 mt-1">{s.reason}</div>
            </div>
            <button
              onClick={() => deactivate.mutate(s.id)}
              className="text-sm text-accent hover:underline"
            >
              Deactivate
            </button>
          </div>
        ))}
      </div>

      <div>
        <h3 className="font-semibold mb-3">History</h3>
        {switches.map((s: any) => (
          <div key={s.id} className="text-xs text-gray-400 py-1">
            {s.is_active ? "🟢" : "⚫"} [{s.scope}] {s.reason} — by {s.activated_by}
          </div>
        ))}
      </div>
    </div>
  );
}
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export const Route = createFileRoute("/approvals")({
  component: Approvals,
});

function Approvals() {
  const qc = useQueryClient();
  const { data: approvals = [] } = useQuery({
    queryKey: ["approvals"],
    queryFn: async () => (await api.get("/approvals?status=pending")).data,
    refetchInterval: 5000,
  });

  const decide = useMutation({
    mutationFn: async ({ id, approved }: { id: string; approved: boolean }) =>
      api.post(`/approvals/${id}/decide`, {
        approved,
        decided_by: "ui-operator",
        note: approved ? "Approved via UI" : "Denied via UI",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals"] }),
  });

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Pending Approvals</h2>
      {approvals.length === 0 && (
        <div className="text-gray-400">No pending approvals.</div>
      )}
      {approvals.map((a: any) => (
        <div key={a.id} className="border border-border rounded-lg bg-panel p-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="font-semibold text-lg">{a.tool}</div>
              <div className="text-sm text-gray-400 mt-1">
                Resource: {a.resource_type || "unknown"}
              </div>
              <div className="text-sm text-gray-400">
                Risk: {Math.round(a.request_context?.risk_score || 0)}
              </div>
              {a.request_context?.reasons?.slice(0, 2).map((r: string, i: number) => (
                <div key={i} className="text-xs text-gray-500 mt-1">
                  • {r}
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => decide.mutate({ id: a.id, approved: true })}
                className="px-4 py-2 bg-success/20 text-success rounded hover:bg-success/30"
              >
                Approve
              </button>
              <button
                onClick={() => decide.mutate({ id: a.id, approved: false })}
                className="px-4 py-2 bg-danger/20 text-danger rounded hover:bg-danger/30"
              >
                Deny
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
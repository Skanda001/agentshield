import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CheckCircle2, XCircle, Inbox } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import { api } from "@/lib/api";

export const Route = createFileRoute("/app/approvals")({
  component: Approvals,
});

type Approval = {
  id: string;
  tool: string;
  resource_type: string | null;
  status: string;
  decided_by: string | null;
  decision_note: string | null;
  decided_at: string | null;
  created_at: string;
  request_context: {
    risk_score?: number;
    reasons?: string[];
    arguments?: Record<string, unknown>;
  };
};

const TABS = ["pending", "approved", "denied", "all"] as const;
type Tab = typeof TABS[number];

function Approvals() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("pending");

  const queryKey = ["approvals", tab];
  const { data: approvals = [], isLoading } = useQuery<Approval[]>({
    queryKey,
    queryFn: async () => {
      const qs = tab === "all" ? "?limit=200" : `?status=${tab}&limit=200`;
      return (await api.get(`/approvals${qs}`)).data;
    },
    refetchInterval: 5000,
  });

  const decide = useMutation({
    mutationFn: async ({
      id,
      approved,
    }: {
      id: string;
      approved: boolean;
    }) =>
      api.post(`/approvals/${id}/decide`, {
        approved,
        decided_by: "ui-operator",
        note: approved ? "Approved via UI" : "Denied via UI",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
      qc.invalidateQueries({ queryKey: ["approvals-all"] });
      qc.invalidateQueries({ queryKey: ["decisions"] });
      qc.invalidateQueries({ queryKey: ["audit-verify"] });
    },
  });

  return (
    <>
      <PageHeader
        title="Approvals"
        description="Actions that need human sign-off before they proceed."
      />

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium relative transition-colors ${
              tab === t
                ? "text-white"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {tab === t && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent rounded-t" />
            )}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingState label="Loading approvals…" />
      ) : approvals.length === 0 ? (
        <EmptyState
          icon={<Inbox className="w-5 h-5" />}
          title={`No ${tab === "all" ? "" : tab} approvals`}
          description={
            tab === "pending"
              ? 'No actions waiting for review. Click "Run demo" in the top bar to generate some.'
              : "Nothing here yet."
          }
        />
      ) : (
        <div className="space-y-3">
          {approvals.map((a) => (
            <ApprovalCard
              key={a.id}
              approval={a}
              onDecide={(approved) =>
                decide.mutate({ id: a.id, approved })
              }
              deciding={decide.isPending}
            />
          ))}
        </div>
      )}
    </>
  );
}

function ApprovalCard({
  approval,
  onDecide,
  deciding,
}: {
  approval: Approval;
  onDecide: (approved: boolean) => void;
  deciding: boolean;
}) {
  const statusBadge =
    approval.status === "pending"
      ? "bg-warn-soft text-warn border-warn/30"
      : approval.status === "approved"
      ? "bg-success-soft text-success border-success/30"
      : "bg-danger-soft text-danger border-danger/30";

  return (
    <div className="card card-hover p-5 animate-slide-up">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3 flex-wrap mb-1">
            <span className="font-mono text-sm font-semibold">
              {approval.tool}
            </span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${statusBadge}`}
            >
              {approval.status}
            </span>
            {approval.request_context?.risk_score !== undefined && (
              <span className="text-xs text-gray-500">
                Risk {Math.round(approval.request_context.risk_score)}
              </span>
            )}
          </div>

          {approval.resource_type && (
            <div className="text-xs text-gray-500 mb-2">
              Resource: {approval.resource_type}
            </div>
          )}

          {approval.request_context?.reasons &&
            approval.request_context.reasons.length > 0 && (
              <ul className="text-xs text-gray-400 space-y-0.5 mt-2">
                {approval.request_context.reasons.slice(0, 3).map((r, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="text-gray-600">•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            )}

          {approval.decided_by && (
            <div className="text-xs text-gray-500 mt-3">
              Decided by <span className="text-gray-300">{approval.decided_by}</span>
              {approval.decision_note && ` — ${approval.decision_note}`}
            </div>
          )}
        </div>

        {approval.status === "pending" && (
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={() => onDecide(true)}
              disabled={deciding}
              className="btn-ghost border-success/40 text-success hover:bg-success-soft disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" />
              Approve
            </button>
            <button
              onClick={() => onDecide(false)}
              disabled={deciding}
              className="btn-ghost border-danger/40 text-danger hover:bg-danger-soft disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" />
              Deny
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
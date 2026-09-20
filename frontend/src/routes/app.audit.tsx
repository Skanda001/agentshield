import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  ChevronRight,
  ScrollText,
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import { api } from "@/lib/api";

export const Route = createFileRoute("/app/audit")({
  component: Audit,
});

type AuditEvent = {
  seq: number;
  id: string;
  event_type: string;
  agent_id: string | null;
  tenant_id: string | null;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
  signature: string;
  created_at: string;
};

function Audit() {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: events = [], isLoading } = useQuery<AuditEvent[]>({
    queryKey: ["audit-events"],
    queryFn: async () => (await api.get("/audit/events?limit=200")).data,
    refetchInterval: 10000,
  });

  const { data: verify } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: async () => (await api.get("/audit/verify")).data,
    refetchInterval: 10000,
  });

  const valid = verify?.valid;

  return (
    <>
      <PageHeader
        title="Audit Log"
        description="Every decision, hash-chained and HMAC-signed."
        actions={
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ["audit-events"] })}
            className="btn-ghost text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        }
      />

      {/* Chain status */}
      {verify && (
        <div
          className={`card p-5 mb-6 flex items-center gap-4 ${
            valid ? "border-success/20" : "border-danger/40"
          }`}
        >
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              valid ? "bg-success-soft" : "bg-danger-soft"
            }`}
          >
            {valid ? (
              <ShieldCheck className="w-5 h-5 text-success" />
            ) : (
              <ShieldAlert className="w-5 h-5 text-danger" />
            )}
          </div>
          <div>
            <div className="font-semibold">
              {valid ? "Chain verified" : "Chain BROKEN"}
            </div>
            <div className="text-sm text-gray-400 mt-0.5">
              {valid
                ? `${verify.total_events.toLocaleString()} events · every hash and signature recomputed successfully`
                : `Failed at seq ${verify.broken_at_seq}: ${verify.reason}`}
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <LoadingState label="Loading events…" />
      ) : events.length === 0 ? (
        <EmptyState
          icon={<ScrollText className="w-5 h-5" />}
          title="No audit events yet"
          description='Click "Run demo" in the top bar to generate some.'
        />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-gray-400 border-b border-border text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left px-5 py-3 font-medium w-20">Seq</th>
                  <th className="text-left px-5 py-3 font-medium">
                    Event type
                  </th>
                  <th className="text-left px-5 py-3 font-medium">Hash</th>
                  <th className="text-left px-5 py-3 font-medium">When</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <EventRow
                    key={e.id}
                    event={e}
                    expanded={expanded === e.id}
                    onToggle={() =>
                      setExpanded(expanded === e.id ? null : e.id)
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function EventRow({
  event,
  expanded,
  onToggle,
}: {
  event: AuditEvent;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className="border-b border-border/40 hover:bg-panel-hover transition-colors cursor-pointer"
      >
        <td className="px-5 py-3 font-mono text-xs text-gray-500">
          #{event.seq}
        </td>
        <td className="px-5 py-3">
          <span className="font-mono text-xs text-accent">
            {event.event_type}
          </span>
        </td>
        <td className="px-5 py-3 font-mono text-xs text-gray-500 truncate max-w-xs">
          {event.hash.slice(0, 16)}…
        </td>
        <td className="px-5 py-3 text-xs text-gray-500">
          {new Date(event.created_at).toLocaleString()}
        </td>
        <td className="px-5 py-3">
          <ChevronRight
            className={`w-3.5 h-3.5 text-gray-500 transition-transform ${
              expanded ? "rotate-90" : ""
            }`}
          />
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border/40">
          <td colSpan={5} className="px-5 py-4 bg-bg">
            <pre className="text-xs text-gray-400 font-mono overflow-x-auto whitespace-pre-wrap break-all">
              {JSON.stringify(
                {
                  seq: event.seq,
                  event_type: event.event_type,
                  agent_id: event.agent_id,
                  payload: event.payload,
                  prev_hash: event.prev_hash,
                  hash: event.hash,
                  signature: event.signature,
                },
                null,
                2
              )}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}
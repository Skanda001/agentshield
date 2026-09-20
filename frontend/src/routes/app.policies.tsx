import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { FileText, Plus, ChevronRight } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import { api } from "@/lib/api";

export const Route = createFileRoute("/app/policies")({
  component: Policies,
});

type Policy = {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  current_version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type PolicyVersion = {
  id: string;
  version: number;
  document: {
    name: string;
    version: number;
    description?: string;
    rules: Array<{
      name: string;
      effect: "allow" | "deny" | "escalate";
      agent?: string;
      role?: string;
      action?: string;
      resource?: string;
      priority?: number;
      conditions?: Record<string, unknown>;
    }>;
  };
  document_hash: string;
  created_at: string;
};

function Policies() {
  const qc = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filePath, setFilePath] = useState("policies/demo.yaml");
  const [loadError, setLoadError] = useState("");

  const { data: policies = [], isLoading } = useQuery<Policy[]>({
    queryKey: ["policies"],
    queryFn: async () => {
      // API requires tenant_id — grab from JWT payload
      const token = localStorage.getItem("token");
      if (!token) return [];
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        const tenantId = payload.tenant_id;
        return (await api.get(`/policies?tenant_id=${tenantId}`)).data;
      } catch {
        return [];
      }
    },
    refetchInterval: 10000,
  });

  const loadYaml = useMutation({
    mutationFn: async () => {
      const token = localStorage.getItem("token");
      const payload = JSON.parse(atob(token!.split(".")[1]));
      const tenantId = payload.tenant_id;
      return api.post(
        `/policies/load-yaml?tenant_id=${tenantId}&file_path=${encodeURIComponent(
          filePath
        )}`
      );
    },
    onSuccess: () => {
      setLoadError("");
      qc.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: (err: any) => {
      setLoadError(err?.response?.data?.detail || "Failed to load policy");
    },
  });

  return (
    <>
      <PageHeader
        title="Policies"
        description="Rules that decide allow / block / escalate for every tool call."
      />

      {/* Load YAML */}
      <div className="card p-5 mb-6">
        <div className="font-semibold mb-3 flex items-center gap-2">
          <Plus className="w-4 h-4 text-accent" />
          Load a policy from YAML
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <input
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            placeholder="policies/demo.yaml"
            className="flex-1 min-w-[240px] px-3 py-2 bg-bg border border-border rounded-lg text-sm font-mono focus:border-accent focus:outline-none"
          />
          <button
            onClick={() => loadYaml.mutate()}
            disabled={loadYaml.isPending || !filePath.trim()}
            className="btn-primary"
          >
            {loadYaml.isPending ? "Loading…" : "Load"}
          </button>
        </div>
        {loadError && (
          <div className="text-danger text-xs mt-3">{loadError}</div>
        )}
        <div className="text-xs text-gray-500 mt-2">
          Path is relative to the backend's <code>POLICY_DIR</code>.
        </div>
      </div>

      {/* List */}
      {isLoading ? (
        <LoadingState label="Loading policies…" />
      ) : policies.length === 0 ? (
        <EmptyState
          icon={<FileText className="w-5 h-5" />}
          title="No policies loaded"
          description="Load a YAML file above to get started."
        />
      ) : (
        <div className="space-y-3">
          {policies.map((p) => (
            <PolicyCard
              key={p.id}
              policy={p}
              expanded={expandedId === p.id}
              onToggle={() =>
                setExpandedId(expandedId === p.id ? null : p.id)
              }
            />
          ))}
        </div>
      )}
    </>
  );
}

function PolicyCard({
  policy,
  expanded,
  onToggle,
}: {
  policy: Policy;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { data: versions = [] } = useQuery<PolicyVersion[]>({
    queryKey: ["policy-versions", policy.id],
    queryFn: async () =>
      (await api.get(`/policies/${policy.id}/versions`)).data,
    enabled: expanded,
  });

  const current = versions.find(
    (v) => v.version === policy.current_version
  ) || versions[0];

  return (
    <div className="card card-hover overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full text-left p-5 flex items-center justify-between gap-4 hover:bg-panel-hover transition-colors"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-semibold">{policy.name}</span>
            <span className="text-xs text-gray-500">
              v{policy.current_version}
            </span>
            {policy.is_active && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold bg-success-soft text-success border border-success/30">
                active
              </span>
            )}
          </div>
          {policy.description && (
            <div className="text-xs text-gray-500">{policy.description}</div>
          )}
        </div>
        <ChevronRight
          className={`w-4 h-4 text-gray-500 transition-transform flex-shrink-0 ${
            expanded ? "rotate-90" : ""
          }`}
        />
      </button>

      {expanded && (
        <div className="border-t border-border bg-bg p-5">
          {!current ? (
            <div className="text-sm text-gray-500">Loading…</div>
          ) : (
            <>
              <div className="text-xs text-gray-500 mb-3">
                Document hash:{" "}
                <span className="font-mono">{current.document_hash.slice(0, 16)}…</span>
              </div>
              <div className="space-y-2">
                {current.document.rules.map((r, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 py-2 border-b border-border/40 last:border-0"
                  >
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase flex-shrink-0 ${
                        r.effect === "allow"
                          ? "bg-success-soft text-success"
                          : r.effect === "deny"
                          ? "bg-danger-soft text-danger"
                          : "bg-warn-soft text-warn"
                      }`}
                    >
                      {r.effect}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-xs">{r.name}</div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {[
                          r.agent && `agent=${r.agent}`,
                          r.role && `role=${r.role}`,
                          r.action && `action=${r.action}`,
                          r.resource && `resource=${r.resource}`,
                          r.priority !== undefined &&
                            r.priority !== 0 &&
                            `priority=${r.priority}`,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "(matches everything)"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
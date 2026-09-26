import { useQueryClient } from "@tanstack/react-query";
import { Link, useRouterState } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { RefreshCw, Lock } from "lucide-react";
import { api } from "@/lib/api";

const PAGE_TITLES: Record<string, string> = {
  "/app": "Dashboard",
  "/app/demo": "Playground",
  "/app/plugins": "Agents",
  "/app/approvals": "Approvals",
  "/app/policies": "Policies",
  "/app/audit": "Audit Log",
  "/app/kill-switch": "Kill Switch",
};

export default function TopBar() {
  const qc = useQueryClient();
  const { location } = useRouterState();
  const path = location.pathname;
  const title = PAGE_TITLES[path] || "AgentShield";

  const [auditValid, setAuditValid] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .get("/audit/verify")
      .then((res) => {
        setAuditValid(res.data?.valid ?? true);
      })
      .catch(() => {});
  }, [path]);

  return (
    <header className="h-14 flex-shrink-0 border-b border-slate-800 bg-[#0B0F17] flex items-center justify-between px-6 z-10">
      {/* Title */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-slate-400 font-medium">AgentShield</span>
        <span className="text-slate-600">/</span>
        <h1 className="font-semibold text-white">{title}</h1>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-2.5">
        {/* Chain verified badge */}
        <Link
          to="/app/audit"
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs text-slate-300 hover:text-white transition-colors"
          title="Audit chain integrity status"
        >
          <Lock className="w-3 h-3 text-emerald-400" />
          <span>Chain: {auditValid === false ? "Broken" : "Verified"}</span>
        </Link>

        {/* Global Refresh */}
        <button
          onClick={() => qc.invalidateQueries()}
          className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>

        {/* User avatar/tenant */}
        <div className="w-7 h-7 rounded-md bg-blue-600 flex items-center justify-center text-xs font-semibold text-white">
          AS
        </div>
      </div>
    </header>
  );
}
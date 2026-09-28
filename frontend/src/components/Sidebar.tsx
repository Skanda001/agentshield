import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  Shield,
  LayoutDashboard,
  CheckCircle2,
  FileText,
  ScrollText,
  Zap,
  Radio,
  Cpu,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, API_URL } from "@/lib/api";

const NAV_ITEMS = [
  { group: "Main", to: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { group: "Main", to: "/app/demo", label: "Playground", icon: Radio, exact: false },
  { group: "Main", to: "/app/plugins", label: "Agents", icon: Cpu, exact: false },
  { group: "Security", to: "/app/approvals", label: "Approvals", icon: CheckCircle2, exact: false },
  { group: "Security", to: "/app/policies", label: "Policies", icon: FileText, exact: false },
  { group: "Security", to: "/app/audit", label: "Audit Log", icon: ScrollText, exact: false },
  { group: "Security", to: "/app/kill-switch", label: "Kill Switch", icon: Zap, exact: false },
];

const GROUPS = ["Main", "Security"];

export default function Sidebar() {
  const { logout } = useAuth();
  const { location } = useRouterState();
  const path = location.pathname;

  // Fix #18: Live gateway health check
  const [isGatewayUp, setIsGatewayUp] = useState<boolean>(true);
  useEffect(() => {
    const check = () =>
      api
        .get("/health")
        .then(() => setIsGatewayUp(true))
        .catch(() => setIsGatewayUp(false));
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, []);

  // Fix #18: pending approvals badge
  const { data: pendingApprovals = [] } = useQuery<unknown[]>({
    queryKey: ["approvals-pending-count"],
    queryFn: async () => (await api.get("/approvals?status=pending&limit=100")).data,
    refetchInterval: 15_000,
  });

  // Derive a short hostname label from API_URL
  const gatewayHost = (() => {
    try {
      const u = new URL(API_URL);
      return u.hostname === "localhost" ? `:${u.port || 8000}` : u.hostname.split(".")[0];
    } catch {
      return "8000";
    }
  })();

  return (
    <aside className="w-56 flex-shrink-0 border-r border-slate-800 bg-[#0c121e] flex flex-col justify-between select-none">
      <div>
        {/* Brand Header */}
        <Link
          to="/"
          className="flex items-center gap-2.5 px-5 py-4 border-b border-slate-800 hover:bg-slate-850/50 transition-colors"
        >
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-sm tracking-tight text-white leading-tight">
              AgentShield
            </div>
            <p className="text-[10px] text-slate-400">AI Security Gateway</p>
          </div>
        </Link>

        {/* Navigation Sections */}
        <nav className="p-3 space-y-5">
          {GROUPS.map((group) => (
            <div key={group} className="space-y-0.5">
              <div className="px-2 pb-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                {group}
              </div>

              {NAV_ITEMS.filter((i) => i.group === group).map((item) => {
                const isActive = item.exact
                  ? path === item.to
                  : path.startsWith(item.to);
                const Icon = item.icon;
                const showBadge =
                  item.label === "Approvals" && pendingApprovals.length > 0;

                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      isActive
                        ? "bg-slate-850 text-white font-semibold"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-850/60"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Icon
                        className={`w-3.5 h-3.5 flex-shrink-0 ${
                          isActive ? "text-blue-400" : "text-slate-400"
                        }`}
                      />
                      <span className="truncate">{item.label}</span>
                    </div>

                    {/* Fix #18: pending approvals badge */}
                    {showBadge && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-mono border border-amber-500/30 flex-shrink-0">
                        {pendingApprovals.length}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </div>

      {/* Footer: gateway status + logout */}
      <div className="p-3 border-t border-slate-800 space-y-2">
        <div className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-[11px]">
          <div className="flex items-center gap-1.5">
            {/* Fix #18: dynamic health dot */}
            <span
              className={`w-2 h-2 rounded-full ${
                isGatewayUp ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            <span className="text-slate-300">
              {isGatewayUp ? "Gateway Active" : "Gateway Down"}
            </span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono truncate max-w-[60px]">
            {gatewayHost}
          </span>
        </div>

        <button
          onClick={logout}
          className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-lg text-xs text-slate-400 hover:text-rose-400 hover:bg-slate-850 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Log out</span>
        </button>
      </div>
    </aside>
  );
}
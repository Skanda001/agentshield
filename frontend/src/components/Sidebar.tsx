import { Link, useRouterState } from "@tanstack/react-router";
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

interface NavGroup {
  label: string;
  items: {
    to: string;
    label: string;
    icon: any;
    exact?: boolean;
    badge?: string;
  }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Main",
    items: [
      { to: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
      { to: "/app/demo", label: "Playground", icon: Radio, exact: false },
      { to: "/app/plugins", label: "Agents", icon: Cpu, exact: false },
    ],
  },
  {
    label: "Security",
    items: [
      { to: "/app/approvals", label: "Approvals", icon: CheckCircle2, exact: false },
      { to: "/app/policies", label: "Policies", icon: FileText, exact: false },
      { to: "/app/audit", label: "Audit Log", icon: ScrollText, exact: false },
      { to: "/app/kill-switch", label: "Kill Switch", icon: Zap, exact: false },
    ],
  },
];

export default function Sidebar() {
  const { logout } = useAuth();
  const { location } = useRouterState();
  const path = location.pathname;

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
            <p className="text-[10px] text-slate-400">
              AI Security Gateway
            </p>
          </div>
        </Link>

        {/* Navigation Sections */}
        <nav className="p-3 space-y-5">
          {NAV_GROUPS.map((group, gIdx) => (
            <div key={gIdx} className="space-y-0.5">
              <div className="px-2 pb-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                {group.label}
              </div>

              {group.items.map((item) => {
                const isActive = item.exact
                  ? path === item.to
                  : path.startsWith(item.to);
                const Icon = item.icon;

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

                    {item.badge && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </div>

      {/* Footer System Status & Logout */}
      <div className="p-3 border-t border-slate-800 space-y-2">
        <div className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-[11px]">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-slate-300">Gateway Active</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">:8002</span>
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
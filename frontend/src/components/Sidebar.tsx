import { Link, useRouterState } from "@tanstack/react-router";
import {
  Shield,
  LayoutDashboard,
  CheckCircle2,
  FileText,
  ScrollText,
  Zap,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/app/approvals", label: "Approvals", icon: CheckCircle2, exact: false },
  { to: "/app/policies", label: "Policies", icon: FileText, exact: false },
  { to: "/app/audit", label: "Audit Log", icon: ScrollText, exact: false },
  { to: "/app/kill-switch", label: "Kill Switch", icon: Zap, exact: false },
];

export default function Sidebar() {
  const { logout } = useAuth();
  const { location } = useRouterState();
  const path = location.pathname;

  return (
    <aside className="w-60 flex-shrink-0 border-r border-border bg-panel/40 flex flex-col">
      {/* Brand */}
      <Link
        to="/"
        className="flex items-center gap-2.5 px-5 py-5 border-b border-border hover:bg-panel-hover transition-colors"
      >
        <div className="w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center">
          <Shield className="w-4 h-4 text-accent" />
        </div>
        <span className="font-bold tracking-tight">AgentShield</span>
      </Link>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-0.5">
        {NAV.map((item) => {
          const isActive = item.exact ? path === item.to : path.startsWith(item.to);
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-accent/10 text-white"
                  : "text-gray-400 hover:text-white hover:bg-panel-hover"
              }`}
            >
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-r" />
              )}
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="p-3 border-t border-border">
        <button
          onClick={logout}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-panel-hover transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span className="font-medium">Logout</span>
        </button>
      </div>
    </aside>
  );
}
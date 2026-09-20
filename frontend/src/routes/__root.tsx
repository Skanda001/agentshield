import { createRootRoute, Outlet, Link, useRouterState } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  const { isAuthenticated, logout } = useAuth();
  const { location } = useRouterState();
  const isLoginPage = location.pathname === "/login";

  if (isLoginPage) {
    return <Outlet />;
  }

  return (
    <div className="min-h-screen flex bg-bg text-white">
      <aside className="w-64 border-r border-border p-6">
        <h1 className="text-2xl font-bold mb-8">🛡️ AgentShield</h1>
        <nav className="space-y-2">
          <NavLink to="/" label="Dashboard" />
          <NavLink to="/approvals" label="Approvals" />
          <NavLink to="/kill-switch" label="Kill Switch" />
        </nav>
        <button
          onClick={logout}
          className="mt-8 w-full text-sm text-gray-400 hover:text-white text-left"
        >
          Logout
        </button>
      </aside>
      <main className="flex-1 p-8 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}

function NavLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="block px-3 py-2 rounded hover:bg-panel text-gray-300 hover:text-white [&.active]:bg-panel [&.active]:text-white"
      activeProps={{ className: "active" }}
    >
      {label}
    </Link>
  );
}
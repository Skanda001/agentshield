import { createContext, useContext, useState } from "react";
import { api } from "./api";

type AuthContextType = {
  isAuthenticated: boolean;
  login: (apiKey: string) => Promise<void>;
  tryDemo: () => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | null>(null);

function uniqueSuffix(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    !!localStorage.getItem("token")
  );

  const login = async (apiKey: string) => {
    const r = await api.post("/agents/token", { api_key: apiKey });
    localStorage.setItem("token", r.data.access_token);
    setIsAuthenticated(true);
  };

  const tryDemo = async () => {
    const suffix = uniqueSuffix();

    // 1. Create tenant
    const tenantRes = await api.post("/tenants", {
      name: `Demo ${suffix}`,
      slug: `demo-${suffix}`,
    });
    const tenantId = tenantRes.data.id;

    // 2. Create agent
    const agentRes = await api.post("/agents", {
      tenant_id: tenantId,
      name: `demo-agent-${suffix}`,
      role: "support",
      scopes: ["read:order", "read:customer"],
    });
    const apiKey = agentRes.data.api_key;

    // 3. Exchange for JWT
    const tokenRes = await api.post("/agents/token", { api_key: apiKey });
    localStorage.setItem("token", tokenRes.data.access_token);

    // 4. Load demo policy (best effort)
    try {
      await api.post(
        `/policies/load-yaml?tenant_id=${tenantId}&file_path=policies/demo.yaml`
      );
    } catch (err) {
      console.warn("Demo policy load failed (non-fatal):", err);
    }

    setIsAuthenticated(true);
  };

  const logout = () => {
    localStorage.removeItem("token");
    setIsAuthenticated(false);
    window.location.href = "/";
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, tryDemo, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
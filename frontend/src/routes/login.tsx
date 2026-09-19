import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/login")({
  component: Login,
});

function Login() {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(apiKey.trim());
      navigate({ to: "/" });
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg">
      <form
        onSubmit={submit}
        className="w-full max-w-md p-8 border border-border rounded-lg bg-panel"
      >
        <h1 className="text-2xl font-bold mb-2">🛡️ AgentShield</h1>
        <p className="text-gray-400 mb-6 text-sm">
          Paste your API key to continue.
        </p>

        <label className="block text-sm text-gray-300 mb-2">API Key</label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="ash_..."
          className="w-full px-3 py-2 bg-bg border border-border rounded mb-4 font-mono text-sm"
          autoFocus
        />

        {error && <div className="text-danger text-sm mb-4">{error}</div>}

        <button
          type="submit"
          disabled={loading || !apiKey.trim()}
          className="w-full py-2 bg-accent hover:brightness-110 rounded font-semibold disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
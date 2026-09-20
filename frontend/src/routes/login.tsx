import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Shield, ArrowLeft } from "lucide-react";
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
      navigate({ to: "/app" });
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Invalid API key");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg relative">
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-accent/5 blur-[120px]" />
      </div>

      <div className="relative z-10 w-full max-w-md px-6">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to home
        </Link>

        <div className="card p-8 animate-slide-up">
          <div className="flex items-center gap-2 mb-6">
            <Shield className="w-6 h-6 text-accent" />
            <span className="font-bold text-lg">AgentShield</span>
          </div>

          <h1 className="text-2xl font-bold mb-2">Sign in</h1>
          <p className="text-gray-400 text-sm mb-6">
            Paste your API key to continue.
          </p>

          <form onSubmit={submit}>
            <label className="block text-sm text-gray-300 mb-2">
              API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="ash_..."
              className="w-full px-3 py-2.5 bg-bg border border-border rounded-lg mb-4 font-mono text-sm focus:border-accent focus:outline-none transition-colors"
              autoFocus
            />

            {error && (
              <div className="text-danger text-sm mb-4 px-3 py-2 rounded-lg bg-danger-soft">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !apiKey.trim()}
              className="btn-primary w-full py-2.5"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Shield, ArrowRight, Github, Check } from "lucide-react";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/")({
  component: Landing,
});

function Landing() {
  const { tryDemo, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function startDemo() {
    setError("");
    setLoading(true);
    try {
      await tryDemo();
      navigate({ to: "/app" });
    } catch (err: any) {
      console.error("Demo setup error:", err);
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : (err?.message || "Demo setup failed. Please try again.");
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg text-white overflow-hidden">
      {/* Decorative background */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[800px] rounded-full bg-accent/5 blur-[120px]" />
        <div className="absolute bottom-0 right-0 w-[600px] h-[600px] rounded-full bg-danger/5 blur-[120px]" />
      </div>

      {/* Nav */}
      <nav className="relative z-10 max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-6 h-6 text-accent" />
          <span className="font-bold text-lg">AgentShield</span>
        </div>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/skandabs/agentshield"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            <Github className="w-4 h-4" />
            GitHub
          </a>
          {isAuthenticated ? (
            <Link to="/app" className="btn-primary text-sm">
              Go to Dashboard
            </Link>
          ) : (
            <Link to="/login" className="text-sm text-gray-300 hover:text-white">
              Sign in
            </Link>
          )}
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 pt-16 pb-24">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-panel text-xs text-gray-400 mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse-soft" />
            Live on Render · Neon · Vercel
          </div>

          <h1 className="text-5xl md:text-6xl font-extrabold leading-[1.05] tracking-tight mb-6">
            Security for <span className="text-accent">AI agents</span>
            <br />
            that actually works.
          </h1>

          <p className="text-xl text-gray-400 leading-relaxed mb-10 max-w-2xl">
            AgentShield intercepts every tool call an AI agent makes, decides
            <span className="text-white"> allow / block / escalate</span>, and
            records every decision in a tamper-evident audit log.
          </p>

          <div className="flex items-center gap-4 flex-wrap">
            <button
              onClick={startDemo}
              disabled={loading}
              className="btn-primary text-base px-6 py-3"
            >
              {loading ? "Setting up…" : "Try the Demo"}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
            <a
              href="https://agentshield-qhxo.onrender.com/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-base px-6 py-3"
            >
              View API Docs
            </a>
          </div>

          {error && (
            <div className="mt-4 text-danger text-sm">{error}</div>
          )}

          <p className="text-sm text-gray-500 mt-4">
            One click. No signup. Loads a fresh tenant with sample data.
          </p>
        </div>
      </section>

      {/* Stats */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Stat
            value="94%"
            label="Attack protection"
            detail="50-attack red-team benchmark"
          />
          <Stat
            value="0%"
            label="False positives"
            detail="On 100+ benign calls"
          />
          <Stat
            value="66"
            label="Tests passing"
            detail="Unit + integration"
          />
        </div>
      </section>

      {/* Features */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 pb-24">
        <h2 className="text-2xl font-bold mb-8">What it does</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-4">
          <Feature text="Intercepts every agent tool call" />
          <Feature text="YAML policy engine with specificity + priority resolution" />
          <Feature text="Deterministic risk scoring with explainable signals" />
          <Feature text="Prompt-injection detection (12 patterns)" />
          <Feature text="PII detection: Aadhaar, PAN, UPI, phone" />
          <Feature text="Hash-chained, HMAC-signed audit log" />
          <Feature text="Human-in-the-loop approval workflow" />
          <Feature text="4-level kill switch (global, tenant, agent, tool)" />
          <Feature text="Python SDK with @shield.protect decorator" />
          <Feature text="LangGraph demo agent showing live enforcement" />
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 max-w-6xl mx-auto px-6 py-12 border-t border-border text-sm text-gray-500 flex items-center justify-between">
        <div>Built with FastAPI · Postgres · React · LangGraph</div>
        <div>© 2026 AgentShield</div>
      </footer>
    </div>
  );
}

function Stat({
  value,
  label,
  detail,
}: {
  value: string;
  label: string;
  detail: string;
}) {
  return (
    <div className="card card-hover p-6">
      <div className="text-4xl font-bold text-accent mb-2">{value}</div>
      <div className="font-semibold mb-1">{label}</div>
      <div className="text-sm text-gray-500">{detail}</div>
    </div>
  );
}

function Feature({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <Check className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
      <span className="text-gray-300">{text}</span>
    </div>
  );
}
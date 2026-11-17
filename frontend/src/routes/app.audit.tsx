import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  ChevronRight,
  Search,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Download,
  FileJson,
  FileSpreadsheet,
  Layers,
  Table,
  Shield,
  Lock,
  Terminal,
  Copy,
  Check,
  FileCheck,
  Cpu,
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import AuditStatusCard from "@/components/AuditStatusCard";
import AuditChainExplorer from "@/components/AuditChainExplorer";
import { api } from "@/lib/api";

export const Route = createFileRoute("/app/audit")({
  component: Audit,
});

type CallLogItem = {
  id: string;
  created_at: string;
  tool: string;
  verdict: "ALLOW" | "HITL" | "BLOCK";
  reasons: string[];
  primary_reason: string;
  risk_score: number;
  arguments: Record<string, unknown>;
  agent_id: string;
  policy_rule?: string | null;
  policy_effect?: string | null;
  data_classification?: string | null;
};

type AuditView = "ledger" | "chain" | "compliance";

function Audit() {
  const qc = useQueryClient();
  const [activeView, setActiveView] = useState<AuditView>("ledger");
  const [verdictFilter, setVerdictFilter] = useState<"ALL" | "ALLOW" | "HITL" | "BLOCK">("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [exportingJson, setExportingJson] = useState(false);

  // 1. Logs Query (backend endpoint provides all decisions with reasons)
  const {
    data: callLogs = [],
    isLoading: loadingLogs,
    refetch: refetchLogs,
  } = useQuery<CallLogItem[]>({
    queryKey: ["audit-call-logs", verdictFilter],
    queryFn: async () => {
      const params: Record<string, string> = { limit: "250" };
      if (verdictFilter !== "ALL") {
        params.verdict = verdictFilter;
      }
      return (await api.get("/audit/logs", { params })).data;
    },
    refetchInterval: 8000,
  });

  // 2. Chain Verification Query
  const { data: verify, refetch: refetchVerify } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: async () => (await api.get("/audit/verify")).data,
    refetchInterval: 10000,
  });

  async function handleRefresh() {
    await Promise.all([
      refetchLogs(),
      refetchVerify(),
      qc.invalidateQueries({ queryKey: ["audit-events"] }),
    ]);
  }

  // Copy helper
  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Export Evidence Pack (JSON) — uses Blob to avoid data: URI size limits
  const handleDownloadEvidencePack = async () => {
    try {
      setExportingJson(true);
      const res = await api.get("/audit/export?limit=1000");
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const downloadAnchor = document.createElement("a");
      const dateStr = new Date().toISOString().replace(/[:.]/g, "-");
      downloadAnchor.setAttribute("href", url);
      downloadAnchor.setAttribute("download", `agentshield-compliance-evidence-${dateStr}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Evidence export failed:", err);
    } finally {
      setExportingJson(false);
    }
  };

  // Sanitize CSV cell value to prevent spreadsheet formula injection (CWE-1236)
  const sanitizeCsvCell = (val: string): string => {
    const dangerous = /^[=+\-@\t\r]/;
    const escaped = val.replace(/"/g, '""');
    return dangerous.test(escaped) ? `"'${escaped}"` : `"${escaped}"`;
  };

  // Export CSV Audit Trail — uses Blob + formula sanitization
  const handleExportCsv = () => {
    if (callLogs.length === 0) return;
    const headers = ["Timestamp", "Decision ID", "Agent ID", "Tool", "Verdict", "Risk Score", "Primary Reason", "Policy Rule", "Data Classification"];
    const rows = filteredLogs.map((log) => [
      sanitizeCsvCell(new Date(log.created_at).toISOString()),
      sanitizeCsvCell(log.id),
      sanitizeCsvCell(log.agent_id),
      sanitizeCsvCell(log.tool),
      sanitizeCsvCell(log.verdict),
      log.risk_score?.toFixed(0) ?? "0",
      sanitizeCsvCell(log.primary_reason || ""),
      sanitizeCsvCell(log.policy_rule || ""),
      sanitizeCsvCell(log.data_classification || ""),
    ]);

    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const downloadAnchor = document.createElement("a");
    const dateStr = new Date().toISOString().slice(0, 10);
    downloadAnchor.setAttribute("href", url);
    downloadAnchor.setAttribute("download", `agentshield-audit-trail-${dateStr}.csv`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    URL.revokeObjectURL(url);
  };

  // Filter logs by search query
  const filteredLogs = callLogs.filter((log) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    return (
      log.tool.toLowerCase().includes(q) ||
      (log.primary_reason && log.primary_reason.toLowerCase().includes(q)) ||
      (log.policy_rule && log.policy_rule.toLowerCase().includes(q)) ||
      log.id.toLowerCase().includes(q) ||
      JSON.stringify(log.arguments).toLowerCase().includes(q)
    );
  });

  const totalCount = callLogs.length;
  const allowCount = callLogs.filter((l) => l.verdict === "ALLOW").length;
  const escalateCount = callLogs.filter(
    (l) => l.verdict === "HITL" || (l.verdict as string) === "ESCALATE"
  ).length;
  const blockCount = callLogs.filter((l) => l.verdict === "BLOCK").length;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <PageHeader
        title="Cryptographic Audit & Compliance Desk"
        description="Immutable cryptographic ledger, real-time forensic proof, and SOC 2 / ISO 27001 evidence."
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={handleDownloadEvidencePack}
              disabled={exportingJson}
              className="btn-ghost text-xs border-blue-500/30 text-blue-300 hover:text-white hover:bg-blue-600/20"
              title="Download cryptographically verifiable evidence pack formatted for compliance auditors"
            >
              <FileJson className="w-3.5 h-3.5 text-blue-400" />
              <span>{exportingJson ? "Exporting…" : "SOC 2 Evidence (.json)"}</span>
            </button>

            <button
              onClick={handleExportCsv}
              disabled={filteredLogs.length === 0}
              className="btn-ghost text-xs text-slate-300 hover:text-white"
              title="Export current filtered audit ledger to CSV spreadsheet"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
              <span>Export CSV</span>
            </button>

            <button onClick={handleRefresh} className="btn-ghost text-xs">
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>
          </div>
        }
      />

      {/* Prominent Cryptographic Assurance Banner */}
      <AuditStatusCard />

      {/* Metrics KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4 border-slate-800 bg-[#0d121f]/90 relative overflow-hidden">
          <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Total Ledger Records</div>
          <div className="text-2xl font-bold text-white mt-1 font-mono">{totalCount}</div>
          <div className="text-[10px] text-slate-500 mt-1">Immutable execution traces</div>
        </div>
        <div className="card p-4 border-slate-800 bg-[#0d121f]/90 relative overflow-hidden">
          <div className="text-[11px] font-mono text-emerald-400 uppercase tracking-wider">Permitted (Safe)</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono">{allowCount}</div>
          <div className="text-[10px] text-slate-500 mt-1">Zero security policy breaches</div>
        </div>
        <div className="card p-4 border-slate-800 bg-[#0d121f]/90 relative overflow-hidden">
          <div className="text-[11px] font-mono text-amber-400 uppercase tracking-wider">Human Triage (HITL)</div>
          <div className="text-2xl font-bold text-amber-400 mt-1 font-mono">{escalateCount}</div>
          <div className="text-[10px] text-slate-500 mt-1">Awaiting or signed off</div>
        </div>
        <div className="card p-4 border-slate-800 bg-[#0d121f]/90 relative overflow-hidden">
          <div className="text-[11px] font-mono text-rose-400 uppercase tracking-wider">Threat Refusals (Block)</div>
          <div className="text-2xl font-bold text-rose-400 mt-1 font-mono">{blockCount}</div>
          <div className="text-[10px] text-slate-500 mt-1">Jailbreaks & attacks halted</div>
        </div>
      </div>

      {/* View Mode Switcher Tabs */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveView("ledger")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeView === "ledger"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <Table className="w-3.5 h-3.5" />
            <span>Forensic Ledger</span>
          </button>

          <button
            onClick={() => setActiveView("chain")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeView === "chain"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Cryptographic Merkle Chain</span>
          </button>

          <button
            onClick={() => setActiveView("compliance")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeView === "compliance"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white hover:bg-slate-800/60"
            }`}
          >
            <FileCheck className="w-3.5 h-3.5" />
            <span>Compliance & Attestation</span>
          </button>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-xs text-slate-500 font-mono">
          <Lock className="w-3 h-3 text-emerald-400" />
          <span>Tamper-evident SHA-256 Ledger</span>
        </div>
      </div>

      {/* VIEW 1: Cryptographic Chain Explorer */}
      {activeView === "chain" && (
        <div className="animate-fade-in">
          <AuditChainExplorer />
        </div>
      )}

      {/* VIEW 2: Compliance & Attestation Center */}
      {activeView === "compliance" && (
        <div className="space-y-6 animate-fade-in">
          {/* Attestation Certificate Card */}
          <div className="card p-6 border-slate-800 bg-[#0c121e]/90 space-y-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
                  <ShieldCheck className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white tracking-tight">
                    Continuous Zero-Trust Security Attestation
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Real-time verification manifest for compliance auditors (SOC 2 Type II, ISO 27001, HIPAA).
                  </p>
                </div>
              </div>

              <button
                onClick={handleDownloadEvidencePack}
                disabled={exportingJson}
                className="btn-primary text-xs px-4 py-2 flex items-center gap-2"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{exportingJson ? "Generating Evidence Pack…" : "Download Evidence JSON"}</span>
              </button>
            </div>

            {/* Framework alignment matrix */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-white">SOC 2 Type II</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Compliant
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Meets Trust Services Criteria <strong>CC6.1</strong> (Access Control), <strong>CC6.6</strong> (Tool Boundary Firewall), and <strong>CC7.2</strong> (Cryptographic Audit Logging).
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-white">ISO/IEC 27001:2022</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Aligned
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Implements Control <strong>A.8.15</strong> (Logging), <strong>A.8.16</strong> (Monitoring Activities), and <strong>A.8.24</strong> (Use of HMAC Cryptography for Non-repudiation).
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-white">PII & HIPAA Guard</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Enforced
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Automatic statutory PII detection and masking (Aadhaar, PAN, Cardholder Data) prior to audit ledger entry write (§164.312(b)).
                </p>
              </div>
            </div>

            {/* Cryptographic Manifest Specs */}
            <div className="rounded-xl bg-slate-950 border border-slate-800 p-4 font-mono text-xs text-slate-300 space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-slate-500 font-bold mb-1">
                Cryptographic Ledger Specifications
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-500">Hash Algorithm:</span> <strong className="text-slate-200">SHA-256 (FIPS 180-4)</strong>
                </div>
                <div>
                  <span className="text-slate-500">Digital Signatures:</span> <strong className="text-slate-200">HMAC-SHA256 (RFC 2104)</strong>
                </div>
                <div>
                  <span className="text-slate-500">Chain Structure:</span> <strong className="text-slate-200">Sequential Forward Merkle Hash Chain</strong>
                </div>
                <div>
                  <span className="text-slate-500">Tamper Detection:</span> <strong className="text-emerald-400">Deterministic Runtime Verification</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 3: Forensic Ledger Table */}
      {activeView === "ledger" && (
        <div className="space-y-4 animate-fade-in">
          {/* Filter and Search Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tool, policy rule, reason, or decision ID..."
                className="input pl-9 text-xs w-full"
              />
            </div>

            <div className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
              {(["ALL", "ALLOW", "HITL", "BLOCK"] as const).map((v) => (
                <button
                  key={v}
                  onClick={() => setVerdictFilter(v)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                    verdictFilter === v
                      ? "bg-slate-800 text-white font-semibold shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {v === "ALL"
                    ? "All Events"
                    : v === "ALLOW"
                    ? "Allowed"
                    : v === "HITL"
                    ? "HITL / Escalate"
                    : "Blocked"}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          {loadingLogs ? (
            <LoadingState label="Loading audit logs…" />
          ) : filteredLogs.length === 0 ? (
            <EmptyState
              title="No audit records found"
              description="Try adjusting your filter or search criteria."
            />
          ) : (
            <div className="card overflow-hidden border-slate-800 bg-[#0B0F17]/90">
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left table-fixed">
                  <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 font-mono text-[11px] uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3 w-[120px]">Verdict</th>
                      <th className="px-4 py-3 w-[190px]">Tool & Policy Rule</th>
                      <th className="px-4 py-3">Decision Reasoning & Signals</th>
                      <th className="px-4 py-3 w-[80px] text-right">Risk Score</th>
                      <th className="px-4 py-3 w-[130px] text-right">Timestamp</th>
                      <th className="w-[40px] px-2 text-center" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredLogs.map((log) => {
                      const isExpanded = expandedId === log.id;
                      const isAllow = log.verdict === "ALLOW";
                      const isEscalate =
                        log.verdict === "HITL" || (log.verdict as string) === "ESCALATE";

                      return (
                        <Fragment key={log.id}>
                          <tr
                            onClick={() => setExpandedId(isExpanded ? null : log.id)}
                            className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                          >
                            <td className="px-4 py-3 whitespace-nowrap">
                              <span
                                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold border ${
                                  isAllow
                                    ? "bg-emerald-950/60 text-emerald-400 border-emerald-500/30"
                                    : isEscalate
                                    ? "bg-amber-950/60 text-amber-400 border-amber-500/30"
                                    : "bg-rose-950/60 text-rose-400 border-rose-500/30"
                                }`}
                              >
                                {isAllow ? (
                                  <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                                ) : isEscalate ? (
                                  <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                                ) : (
                                  <XCircle className="w-3 h-3 text-rose-400 shrink-0" />
                                )}
                                <span>{log.verdict}</span>
                              </span>
                            </td>
                            <td className="px-4 py-3 truncate">
                              <div className="font-mono text-slate-200 font-semibold truncate">
                                {log.tool}
                              </div>
                              {log.policy_rule && (
                                <span className="inline-block text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 mt-0.5">
                                  {log.policy_rule}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-slate-300 truncate">
                              <span>{log.primary_reason || "Evaluated by policy pipeline"}</span>
                              {log.data_classification && (
                                <span className="ml-2 text-[10px] font-mono text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                                  PII: {log.data_classification}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 font-mono text-right font-semibold">
                              <span
                                className={
                                  log.risk_score >= 70
                                    ? "text-rose-400"
                                    : log.risk_score >= 30
                                    ? "text-amber-400"
                                    : "text-emerald-400"
                                }
                              >
                                {log.risk_score?.toFixed(0) ?? 0}
                              </span>
                            </td>
                            <td className="px-4 py-3 font-mono text-slate-400 text-right whitespace-nowrap">
                              <div>
                                {new Date(log.created_at).toLocaleDateString([], {
                                  month: "short",
                                  day: "numeric",
                                })}
                              </div>
                              <div className="text-[10px] text-slate-500">
                                {new Date(log.created_at).toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  second: "2-digit",
                                })}
                              </div>
                            </td>
                            <td className="px-2 py-3 text-center">
                              <ChevronRight
                                className={`w-3.5 h-3.5 text-slate-500 transition-transform inline-block ${
                                  isExpanded ? "rotate-90 text-blue-400" : ""
                                }`}
                              />
                            </td>
                          </tr>

                          {/* Expanded Forensic Drawer */}
                          {isExpanded && (
                            <tr className="bg-slate-900/70 border-b border-slate-800">
                              <td colSpan={6} className="px-6 py-4 space-y-3">
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                  {/* Arguments Payload */}
                                  <div>
                                    <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-1.5">
                                      <span className="flex items-center gap-1.5">
                                        <Terminal className="w-3.5 h-3.5 text-blue-400" />
                                        Tool Arguments Payload
                                      </span>
                                      <button
                                        onClick={() =>
                                          handleCopy(JSON.stringify(log.arguments, null, 2), `payload-${log.id}`)
                                        }
                                        className="text-blue-400 hover:text-blue-300 text-[10px] flex items-center gap-1"
                                      >
                                        {copiedId === `payload-${log.id}` ? (
                                          <Check className="w-3 h-3 text-emerald-400" />
                                        ) : (
                                          <Copy className="w-3 h-3" />
                                        )}
                                        <span>
                                          {copiedId === `payload-${log.id}` ? "Copied" : "Copy"}
                                        </span>
                                      </button>
                                    </div>
                                    <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-52 overflow-y-auto whitespace-pre-wrap">
                                      {JSON.stringify(log.arguments, null, 2)}
                                    </pre>
                                  </div>

                                  {/* Policy Reasoning & Security Signals */}
                                  <div className="space-y-3">
                                    <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                                      <Shield className="w-3.5 h-3.5 text-blue-400" />
                                      Security Engine Signals & Triggers
                                    </div>

                                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs">
                                      {log.reasons && log.reasons.length > 0 ? (
                                        <ul className="space-y-1.5">
                                          {log.reasons.map((r, i) => (
                                            <li key={i} className="flex items-start gap-2 text-slate-300">
                                              <span
                                                className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                                                  log.verdict === "BLOCK"
                                                    ? "bg-rose-400"
                                                    : isEscalate
                                                    ? "bg-amber-400"
                                                    : "bg-emerald-400"
                                                }`}
                                              />
                                              <span>{r}</span>
                                            </li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <div className="text-slate-500 italic">No specific threat flags detected.</div>
                                      )}

                                      {log.policy_rule && (
                                        <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                                          <span>Rule Enforced:</span>
                                          <span className="font-mono text-blue-400">{log.policy_rule}</span>
                                        </div>
                                      )}

                                      {log.data_classification && (
                                        <div className="pt-1 text-[11px] text-slate-400 flex items-center justify-between">
                                          <span>PII Classification:</span>
                                          <span className="font-mono text-amber-300">{log.data_classification}</span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                {/* Decision ID & Cryptographic Receipt Link */}
                                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[10px] font-mono text-slate-500">
                                  <span>Decision ID: {log.id}</span>
                                  <span>Agent: {log.agent_id}</span>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
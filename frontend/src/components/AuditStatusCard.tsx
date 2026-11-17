import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Loader2,
  RefreshCw,
  Lock,
  ExternalLink,
  Cpu,
  CheckCircle2,
} from "lucide-react";
import { api } from "@/lib/api";

type AuditVerifyResult = {
  total_events: number;
  verified_events: number;
  valid: boolean;
  broken_at_seq?: number;
  reason?: string;
  errors?: string[];
};

export default function AuditStatusCard() {
  const qc = useQueryClient();
  const [lastVerifiedTime, setLastVerifiedTime] = useState<string>("Just now");
  const [scanning, setScanning] = useState(false);

  const { data: audit, isLoading } = useQuery<AuditVerifyResult>({
    queryKey: ["audit-verify"],
    queryFn: async () => (await api.get("/audit/verify")).data,
    refetchInterval: 10000,
  });

  const verifyMutation = useMutation({
    mutationFn: async () => {
      setScanning(true);
      const res = await api.get("/audit/verify");
      // Artificial 350ms scan animation for satisfying enterprise feedback
      await new Promise((r) => setTimeout(r, 350));
      return res.data;
    },
    onSuccess: (data) => {
      qc.setQueryData(["audit-verify"], data);
      qc.invalidateQueries({ queryKey: ["audit-events"] });
      setLastVerifiedTime(
        new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
      setScanning(false);
    },
    onError: () => {
      setScanning(false);
    },
  });

  if (isLoading || !audit) {
    return (
      <div className="card p-5 flex items-center justify-between border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-3 text-slate-400">
          <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
          <span className="text-xs font-mono">Running cryptographic audit verification scan…</span>
        </div>
      </div>
    );
  }

  const valid = audit.valid;

  return (
    <div
      className={`card relative overflow-hidden p-5 border transition-all duration-200 ${
        valid
          ? "border-emerald-500/30 bg-[#0c141d]/80 glow-emerald"
          : "border-rose-500/40 bg-[#1a0f14]/80 glow-rose"
      }`}
    >
      {/* Background ambient gradient */}
      <div
        className={`absolute -right-20 -top-20 w-64 h-64 rounded-full blur-[80px] pointer-events-none ${
          valid ? "bg-emerald-500/10" : "bg-rose-500/15"
        }`}
      />

      <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        {/* Left: Shield & Status Info */}
        <div className="flex items-start gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 border ${
              valid
                ? "bg-emerald-950/60 border-emerald-500/30 text-emerald-400"
                : "bg-rose-950/60 border-rose-500/40 text-rose-400 animate-pulse"
            }`}
          >
            {valid ? (
              <ShieldCheck className="w-6 h-6 text-emerald-400" />
            ) : (
              <ShieldAlert className="w-6 h-6 text-rose-400" />
            )}
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-sm text-white tracking-tight flex items-center gap-2">
                <span>{valid ? "Cryptographic Audit Ledger: 100% Intact" : "Audit Chain Broken / Tampering Detected"}</span>
              </h3>
              <span
                className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full border ${
                  valid
                    ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                    : "bg-rose-500/15 border-rose-500/40 text-rose-300"
                }`}
              >
                {valid ? "HMAC-SHA256 SIGNED" : "SIGNATURE MISMATCH"}
              </span>
            </div>

            <p className="text-xs text-slate-300">
              {valid ? (
                <>
                  <span className="font-mono text-emerald-300 font-semibold">
                    {audit.total_events.toLocaleString()}
                  </span>{" "}
                  sequential events cryptographically verified. Zero retroactive modifications or hash breaks detected.
                </>
              ) : (
                <span className="text-rose-300 font-mono text-[11px]">
                  Integrity fault detected at sequence #{audit.broken_at_seq}: {audit.reason || "Hash chain mismatch"}
                </span>
              )}
            </p>

            <div className="flex items-center gap-3 pt-1 text-[11px] text-slate-400 font-mono">
              <span className="flex items-center gap-1">
                <Lock className="w-3 h-3 text-slate-500" />
                Ledger Height: <strong className="text-slate-200">#{audit.total_events}</strong>
              </span>
              <span>·</span>
              <span className="flex items-center gap-1">
                <Cpu className="w-3 h-3 text-slate-500" />
                Cipher: <strong className="text-slate-200">SHA-256</strong>
              </span>
              <span>·</span>
              <span className="hidden sm:inline text-slate-500">
                Verified: {lastVerifiedTime}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2.5 self-end lg:self-center flex-shrink-0">
          <button
            onClick={() => verifyMutation.mutate()}
            disabled={scanning || verifyMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-medium text-slate-200 hover:text-white transition-all disabled:opacity-50"
            title="Perform fresh cryptographic hash re-verification across all audit ledger events"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? "animate-spin text-emerald-400" : "text-slate-400"}`} />
            <span>{scanning ? "Verifying Ledger…" : "Verify Ledger"}</span>
          </button>

          <Link
            to="/app/audit"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-xs font-medium text-blue-300 hover:text-blue-200 transition-all"
          >
            <span>Audit Desk</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </div>
  );
}
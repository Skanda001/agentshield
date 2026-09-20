import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

export default function AuditStatusCard() {
  const { data: audit, isLoading } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: async () => (await api.get("/audit/verify")).data,
    refetchInterval: 10000,
  });

  if (isLoading || !audit) {
    return (
      <div className="card p-6 flex items-center gap-3 text-gray-400">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">Verifying audit chain…</span>
      </div>
    );
  }

  const valid = audit.valid;
  const Icon = valid ? ShieldCheck : ShieldAlert;

  return (
    <div
      className={`card p-6 flex items-center gap-4 ${
        valid ? "border-success/20" : "border-danger/40 shadow-glow-danger"
      }`}
    >
      <div
        className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
          valid ? "bg-success-soft" : "bg-danger-soft"
        }`}
      >
        <Icon
          className={`w-6 h-6 ${valid ? "text-success" : "text-danger"}`}
        />
      </div>
      <div className="min-w-0">
        <div className="font-semibold text-white">
          {valid ? "Audit chain verified" : "Audit chain BROKEN"}
        </div>
        <div className="text-sm text-gray-400 mt-0.5">
          {valid
            ? `${audit.total_events.toLocaleString()} events · hash-linked · HMAC-signed`
            : `Failed at event #${audit.broken_at_seq}: ${audit.reason}`}
        </div>
      </div>
    </div>
  );
}
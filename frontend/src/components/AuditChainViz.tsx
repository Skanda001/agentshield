import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert, Loader2 } from "lucide-react";
import { verifyAuditChain } from "@/lib/demoApi";

export default function AuditChainViz({ refreshKey }: { refreshKey: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["demo-audit-verify", refreshKey],
    queryFn: verifyAuditChain,
    refetchInterval: 15000,
  });

  if (isLoading || (!data && !isError)) {
    return (
      <div className="card p-4 flex items-center gap-2 text-gray-400 text-xs">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Verifying audit chain…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="card p-4 text-xs text-danger">
        Could not verify audit chain
      </div>
    );
  }

  const valid = data.valid;
  const Icon = valid ? ShieldCheck : ShieldAlert;

  return (
    <div
      className={`card p-4 flex items-center gap-3 ${
        valid ? "border-success/20" : "border-danger/40"
      }`}
    >
      <div
        className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
          valid ? "bg-success-soft" : "bg-danger-soft"
        }`}
      >
        <Icon
          className={`w-4 h-4 ${valid ? "text-success" : "text-danger"}`}
        />
      </div>
      <div className="min-w-0">
        <div className="text-xs font-semibold">
          {valid ? "Chain verified" : "Chain BROKEN"}
        </div>
        <div className="text-[10px] text-gray-500 mt-0.5">
          {valid
            ? `${data.total_events.toLocaleString()} events · hash-linked · HMAC-signed`
            : `Failed at #${data.broken_at_seq}: ${data.reason}`}
        </div>
      </div>
    </div>
  );
}
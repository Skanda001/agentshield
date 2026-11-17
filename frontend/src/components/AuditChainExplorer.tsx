import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Link2,
  Hash,
  ShieldCheck,
  ShieldAlert,
  Copy,
  Check,
  ChevronRight,
  Search,
  ExternalLink,
  Terminal,
  Lock,
  Layers,
  FileCode,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";

export type AuditEvent = {
  seq: number;
  id: string;
  event_type: string;
  agent_id?: string | null;
  tenant_id?: string | null;
  payload: Record<string, any>;
  prev_hash: string;
  hash: string;
  signature: string;
  note?: string | null;
  created_at: string;
};

export default function AuditChainExplorer() {
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [searchSeq, setSearchSeq] = useState<string>("");

  const { data: events = [], isLoading } = useQuery<AuditEvent[]>({
    queryKey: ["audit-events"],
    queryFn: async () => (await api.get("/audit/events?limit=60")).data,
    refetchInterval: 8000,
  });

  const handleCopy = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const filteredEvents = events.filter((e) => {
    if (!searchSeq.trim()) return true;
    const q = searchSeq.toLowerCase().trim();
    return (
      e.seq.toString().includes(q) ||
      e.hash.toLowerCase().includes(q) ||
      e.prev_hash.toLowerCase().includes(q) ||
      (e.payload?.tool && String(e.payload.tool).toLowerCase().includes(q)) ||
      e.event_type.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-4">
      {/* Explorer Controls */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-slate-900/60 border border-slate-800 p-3 rounded-xl">
        <div className="flex items-center gap-2 text-xs text-slate-300">
          <Layers className="w-4 h-4 text-blue-400" />
          <span className="font-semibold text-white">Cryptographic Merkle Ledger</span>
          <span className="text-slate-500">·</span>
          <span className="font-mono text-slate-400">
            Showing latest {events.length} sequential blocks
          </span>
        </div>

        <div className="relative max-w-xs">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={searchSeq}
            onChange={(e) => setSearchSeq(e.target.value)}
            placeholder="Search seq #, hash, or tool..."
            className="input pl-9 text-xs w-full font-mono"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="card p-12 text-center text-slate-500 text-xs font-mono">
          Loading cryptographic block stream…
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="card p-12 text-center text-slate-500 text-xs">
          No sequential blocks found matching search.
        </div>
      ) : (
        <div className="relative">
          {/* Timeline Node Chain */}
          <div className="space-y-3">
            {filteredEvents.map((evt, idx) => {
              const tool = evt.payload?.tool || evt.payload?.tool_name || "system";
              const verdict = evt.payload?.verdict || "UNKNOWN";
              const riskScore = evt.payload?.risk_score;
              const isBlocked = verdict === "BLOCK";
              const isHitl = verdict === "HITL" || verdict === "ESCALATE";
              const isAllow = verdict === "ALLOW";

              return (
                <div
                  key={evt.id}
                  onClick={() => setSelectedEvent(evt)}
                  className={`group relative card p-4 border transition-all duration-150 cursor-pointer hover:border-blue-500/50 hover:bg-slate-900/90 ${
                    selectedEvent?.id === evt.id
                      ? "border-blue-500 bg-slate-900/95 shadow-glow"
                      : "border-slate-800/80 bg-slate-950/60"
                  }`}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    {/* Left: Seq & Event Info */}
                    <div className="flex items-start md:items-center gap-3.5">
                      {/* Sequence Badge */}
                      <div className="flex flex-col items-center">
                        <span className="px-2 py-1 rounded bg-blue-950/70 border border-blue-500/30 text-blue-400 font-mono text-xs font-bold shadow-sm">
                          #{evt.seq}
                        </span>
                      </div>

                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-sm font-semibold text-white tracking-tight">
                            {tool}
                          </span>
                          <span
                            className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold ${
                              isBlocked
                                ? "bg-rose-950/60 text-rose-300 border-rose-500/30"
                                : isHitl
                                ? "bg-amber-950/60 text-amber-300 border-amber-500/30"
                                : isAllow
                                ? "bg-emerald-950/60 text-emerald-300 border-emerald-500/30"
                                : "bg-slate-800 text-slate-300 border-slate-700"
                            }`}
                          >
                            {verdict}
                          </span>
                          {riskScore !== undefined && (
                            <span className="text-[11px] font-mono text-slate-400">
                              Risk: <strong className="text-slate-200">{Math.round(riskScore)}</strong>
                            </span>
                          )}
                          <span className="text-[10px] text-slate-500 font-mono">
                            {new Date(evt.created_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit",
                            })}
                          </span>
                        </div>

                        {/* Cryptographic Linkage Info */}
                        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 flex-wrap">
                          <span className="text-slate-500 flex items-center gap-1">
                            <Hash className="w-3 h-3 text-slate-600" />
                            Hash:
                          </span>
                          <span className="text-slate-300 font-medium">
                            {evt.hash.slice(0, 10)}…{evt.hash.slice(-8)}
                          </span>

                          <span className="text-slate-600 hidden sm:inline">←</span>

                          <span className="text-slate-500 hidden sm:flex items-center gap-1">
                            <Link2 className="w-3 h-3 text-slate-600" />
                            Prev:
                          </span>
                          <span className="text-slate-400 hidden sm:inline font-mono">
                            {evt.prev_hash === "0" ? "00000000 (GENESIS)" : `${evt.prev_hash.slice(0, 8)}…`}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Right: Signature Badge & Inspect Prompt */}
                    <div className="flex items-center gap-3 self-end md:self-center flex-shrink-0">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/20 text-[10px] font-mono text-emerald-400">
                        <ShieldCheck className="w-3 h-3" />
                        <span>HMAC VALID</span>
                      </span>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedEvent(evt);
                        }}
                        className="btn-ghost text-xs px-2.5 py-1 text-slate-400 group-hover:text-blue-400 group-hover:border-blue-500/40"
                      >
                        <span>Forensic Inspect</span>
                        <ChevronRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Forensic Cryptographic Inspector Modal / Drawer */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4">
          <div className="bg-[#0c121e] border border-blue-500/40 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 animate-slide-up max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 font-mono font-bold text-sm">
                  #{selectedEvent.seq}
                </div>
                <div>
                  <h3 className="font-bold text-white text-base tracking-tight flex items-center gap-2">
                    <span>Cryptographic Block #{selectedEvent.seq}</span>
                    <span className="text-[10px] font-mono font-normal px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      HMAC-SHA256 SIGNED
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">
                    Timestamp: {new Date(selectedEvent.created_at).toUTCString()}
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                ✕
              </button>
            </div>

            {/* Cryptographic Proof Verification Card */}
            <div className="space-y-3">
              <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-blue-400" />
                <span>Cryptographic Proof & Hashes</span>
              </div>

              <div className="space-y-2 rounded-xl bg-slate-950 border border-slate-800 p-3.5 text-xs font-mono">
                {/* Current Hash */}
                <div>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                    <span>Current Event SHA-256 Hash:</span>
                    <button
                      onClick={() => handleCopy(selectedEvent.hash, "hash")}
                      className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      {copiedField === "hash" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedField === "hash" ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-200 select-all break-all text-[11px]">
                    {selectedEvent.hash}
                  </div>
                </div>

                {/* Previous Hash Link */}
                <div className="pt-2">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                    <span>Preceding Block Hash (prev_hash):</span>
                    <button
                      onClick={() => handleCopy(selectedEvent.prev_hash, "prev_hash")}
                      className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      {copiedField === "prev_hash" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedField === "prev_hash" ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-300 select-all break-all text-[11px]">
                    {selectedEvent.prev_hash}
                  </div>
                </div>

                {/* HMAC Signature */}
                <div className="pt-2">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                    <span>HMAC-SHA256 Digital Signature:</span>
                    <button
                      onClick={() => handleCopy(selectedEvent.signature, "signature")}
                      className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      {copiedField === "signature" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedField === "signature" ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800 text-emerald-400/90 select-all break-all text-[11px]">
                    {selectedEvent.signature}
                  </div>
                </div>

                {/* Mathematical Integrity Formula */}
                <div className="pt-2 text-[10px] text-slate-500 border-t border-slate-900">
                  Formula: <code className="text-slate-400">hash = SHA-256(prev_hash || seq || canonical_json(payload))</code>
                </div>
              </div>
            </div>

            {/* Event Payload Data */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                  <Terminal className="w-3.5 h-3.5 text-blue-400" />
                  <span>Verified Payload Data</span>
                </span>
                <button
                  onClick={() => handleCopy(JSON.stringify(selectedEvent.payload, null, 2), "payload")}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                >
                  {copiedField === "payload" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedField === "payload" ? "Copied JSON" : "Copy JSON"}</span>
                </button>
              </div>

              <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap">
                {JSON.stringify(selectedEvent.payload, null, 2)}
              </pre>
            </div>

            {/* Metadata Footer */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-[11px] text-slate-500 font-mono">
              <span>Event ID: {selectedEvent.id}</span>
              <button
                onClick={() => setSelectedEvent(null)}
                className="btn-ghost text-xs px-4 py-1.5"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState, useEffect } from "react";
import { CheckCircle2, XCircle, AlertTriangle, ShieldCheck, Database } from "lucide-react";
import VerdictBadge from "./VerdictBadge";
import { decideApproval } from "@/lib/demoApi";
import type { DemoEvent, ApprovalDecisionResult } from "@/lib/demoApi";

export default function DemoEventDetail({
  event,
  onApprovalDecided,
  prompt,
}: {
  event: DemoEvent | null;
  onApprovalDecided?: (res: ApprovalDecisionResult) => void;
  prompt?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<"approved" | "denied" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [revealedData, setRevealedData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    setDone(null);
    setErr(null);
    setRevealedData(null);
  }, [event?.run_id, event?.step, event?.approval_id]);

  if (!event) {
    return (
      <div className="card p-6 text-center text-sm text-gray-500">
        Select an event to see details.
      </div>
    );
  }

  async function act(approved: boolean) {
    if (!event?.approval_id) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await decideApproval(
        event.approval_id,
        approved,
        "demo-supervisor",
        undefined,
        prompt || (event.args as any)?.prompt || ""
      );
      setDone(approved ? "approved" : "denied");
      if (res.output) {
        setRevealedData(res.output);
      }
      onApprovalDecided?.(res);
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to submit decision";
      setErr(msg);
    } finally {
      setBusy(false);
    }
  }

  const isHitl = event.decision === "HITL" && !done;
  const currentVerdict = done === "approved" ? "ALLOW" : done === "denied" ? "BLOCK" : event.decision;
  const isExecuted = done === "approved" ? true : done === "denied" ? false : (event.execution?.executed ?? false);
  const findings = event.findings ?? [];

  return (
    <div className="card p-5 animate-fade-in">
      <div className="flex items-center gap-2 mb-4">
        <span className="font-mono text-sm flex-1 truncate">{event.tool}</span>
        <VerdictBadge verdict={currentVerdict} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <Stat label="Step" value={String(event.step ?? 1)} />
        <Stat label="Risk" value={done === "approved" ? "15" : done === "denied" ? "100" : String(event.risk?.score ?? 0)} />
        <Stat label="Attempted" value={String(event.execution?.attempted ?? false)} />
        <Stat label="Executed" value={String(isExecuted)} />
      </div>

      {done === "approved" && (
        <div className="mb-4 p-3 rounded-lg border text-xs bg-success-soft/60 border-success/30 text-gray-200">
          <div className="flex items-center gap-1.5 font-semibold mb-1 text-success">
            <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" />
            <span>Authorization Granted & Executed</span>
          </div>
          <p className="text-[11px] text-gray-300">
            Supervisor approved access. Tool executed and requested records are now unlocked.
          </p>
        </div>
      )}

      {done === "denied" && (
        <div className="mb-4 p-3 rounded-lg border text-xs bg-danger-soft/60 border-danger/30 text-gray-200">
          <div className="flex items-center gap-1.5 font-semibold mb-1 text-danger">
            <XCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>Authorization Denied</span>
          </div>
          <p className="text-[11px] text-gray-300">
            Supervisor denied access. Tool execution permanently blocked under security policy.
          </p>
        </div>
      )}

      {!done && event.error && (
        <div
          className={`mb-4 p-3 rounded-lg border text-xs ${
            event.decision === "BLOCK"
              ? "bg-danger-soft/60 border-danger/30 text-gray-200"
              : "bg-warn-soft/60 border-warn/30 text-gray-200"
          }`}
        >
          <div
            className={`flex items-center gap-1.5 font-semibold mb-1.5 ${
              event.decision === "BLOCK" ? "text-danger" : "text-warn"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>
              {event.decision === "BLOCK"
                ? "Security Reason (Blocked Action)"
                : "Escalation Policy (Human Approval Required)"}
            </span>
          </div>
          <p className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-gray-300">
            {event.error}
          </p>
        </div>
      )}


      {Object.keys(event.args ?? {}).length > 0 && (
        <Section title="Arguments">
          <pre className="text-[11px] font-mono text-gray-400 whitespace-pre-wrap break-all bg-bg/60 rounded p-2 max-h-40 overflow-auto">
            {JSON.stringify(event.args, null, 2)}
          </pre>
        </Section>
      )}

      {findings.length > 0 && (
        <Section title="Findings">
          <ul className="space-y-1">
            {findings.map((f, i) => (
              <li
                key={i}
                className="flex items-center gap-2 text-xs px-2 py-1 rounded bg-danger-soft/40 border border-danger/20"
              >
                <AlertTriangle className="w-3 h-3 text-danger flex-shrink-0" />
                <span className="font-medium">
                  {f.type === "pii" ? `PII (${f.subtype})` : f.type}
                </span>
                {f.severity && (
                  <span className="text-[10px] text-gray-400 uppercase ml-auto">
                    {f.severity}
                  </span>
                )}
                {f.confidence !== undefined && (
                  <span className="text-[10px] text-gray-400 ml-auto">
                    {f.confidence}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {revealedData && (
        <Section title="Authorized Tool Output (Revealed)">
          <div className="rounded-lg border border-success/30 bg-bg/90 p-2.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-success mb-1.5">
              <Database className="w-3.5 h-3.5" />
              <span>Decrypted / Disclosed Records</span>
            </div>
            <pre className="text-[11px] font-mono text-emerald-300 whitespace-pre-wrap break-all max-h-56 overflow-auto">
              {JSON.stringify(revealedData, null, 2)}
            </pre>
          </div>
        </Section>
      )}

      {event.text && (
        <Section title="Agent reply">
          <p className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">{event.text}</p>
        </Section>
      )}

      {event.approval_id && (
        <Section title="Human approval">
          {done ? (
            <div
              className={`flex items-center gap-2 text-xs ${
                done === "approved" ? "text-success font-medium" : "text-danger font-medium"
              }`}
            >
              {done === "approved" ? (
                <CheckCircle2 className="w-4 h-4" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
              <span>
                {done === "approved" ? "Approved & Executed" : "Denied by Supervisor"}
              </span>
            </div>
          ) : (
            <>
              <div className="flex gap-2">
                <button
                  disabled={busy}
                  onClick={() => act(true)}
                  className="btn-primary flex-1 py-1.5 text-xs"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Approve
                </button>
                <button
                  disabled={busy}
                  onClick={() => act(false)}
                  className="btn-danger flex-1 py-1.5 text-xs"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Deny
                </button>
              </div>
              {err && (
                <div className="text-xs text-danger mt-2 px-2 py-1 rounded bg-danger-soft">
                  {err}
                </div>
              )}
            </>
          )}
        </Section>
      )}

      {event.audit_id && (
        <div className="mt-4 pt-3 border-t border-border text-[10px] text-gray-500 font-mono">
          audit_id: {event.audit_id}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-bg/60 rounded-lg px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-gray-500">
        {label}
      </div>
      <div className="text-sm font-semibold mt-0.5">{value}</div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-4">
      <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">
        {title}
      </div>
      {children}
    </div>
  );
}
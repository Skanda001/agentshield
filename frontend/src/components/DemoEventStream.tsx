import { useEffect, useRef } from "react";
import VerdictBadge from "./VerdictBadge";
import type { DemoEvent } from "@/lib/demoApi";

export default function DemoEventStream({
  events,
  selectedId,
  onSelect,
  running,
}: {
  events: DemoEvent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  running: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className="card p-8 text-center text-sm text-gray-500">
        {running
          ? "Agent is reasoning & invoking tools…"
          : "Enter a prompt in the AI Agent Prompt Bar above or pick a scenario to begin."}
      </div>
    );
  }

  return (
    <div className="card p-0 overflow-hidden">
      <div className="divide-y divide-border">
        {events.map((ev) => {
          const id = `${ev.run_id}:${ev.step}`;
          const isSel = id === selectedId;
          const colorClass =
            ev.decision === "BLOCK"
              ? "border-l-danger"
              : ev.decision === "HITL"
              ? "border-l-warn"
              : ev.decision === "ALLOW"
              ? "border-l-success"
              : "border-l-border";

          return (
            <button
              key={id}
              onClick={() => onSelect(id)}
              className={`w-full text-left px-4 py-3 border-l-2 ${colorClass} transition-colors ${
                isSel ? "bg-panel-hover" : "hover:bg-panel-hover/50"
              } animate-fade-in`}
            >
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500 font-mono w-6">
                  {ev.step}
                </span>
                <span className="font-mono text-sm flex-1 truncate">
                  {ev.tool}
                </span>
                <VerdictBadge verdict={ev.decision} />
                <span className="text-xs text-gray-500 w-8 text-right font-mono">
                  {ev.risk.score}
                </span>
              </div>
              {ev.tool === "agent.final" && ev.text && (
                <div className="text-xs text-gray-400 mt-1.5 pl-9 line-clamp-2">
                  {ev.text}
                </div>
              )}
              {ev.error && (
                <div
                  className={`text-xs mt-1.5 pl-9 line-clamp-2 font-mono ${
                    ev.decision === "BLOCK" ? "text-danger" : "text-warn"
                  }`}
                >
                  {ev.error}
                </div>
              )}

              {ev.findings.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5 pl-9">
                  {ev.findings.map((f, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-danger-soft text-danger border border-danger/20"
                    >
                      {f.type === "pii" ? `PII:${f.subtype}` : f.type}
                    </span>
                  ))}
                </div>
              )}
            </button>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
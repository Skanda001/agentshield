import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Play, Square, ChevronDown, ChevronRight, History } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import DemoScenarioPicker from "@/components/DemoScenarioPicker";
import DemoEventStream from "@/components/DemoEventStream";
import DemoEventDetail from "@/components/DemoEventDetail";
import AuditChainViz from "@/components/AuditChainViz";
import AgentPromptBar from "@/components/AgentPromptBar";
import {
  listScenarios,
  startRun,
  runAgentPrompt,
  getPromptSuggestions,
} from "@/lib/demoApi";
import type {
  DemoEvent,
  Scenario,
  PromptSuggestion,
  AgentPromptResponse,
  ApprovalDecisionResult,
} from "@/lib/demoApi";
import { openDemoSocket } from "@/lib/demoSocket";

export const Route = createFileRoute("/app/demo")({
  component: DemoPage,
});

function newRunId(): string {
  return crypto.randomUUID();
}

function DemoPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [suggestions, setSuggestions] = useState<PromptSuggestion[]>([]);
  const [prompt, setPrompt] = useState<string>("Check recent orders for customer 1001");
  const [events, setEvents] = useState<DemoEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const [agentResult, setAgentResult] = useState<AgentPromptResponse | null>(null);
  const [overrideFinalAnswer, setOverrideFinalAnswer] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [mode, setMode] = useState<"replay" | "live">("replay");
  const [error, setError] = useState<string | null>(null);
  const [auditKey, setAuditKey] = useState(0);
  const [showScenarios, setShowScenarios] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    listScenarios().then(setScenarios).catch(() => {});
    getPromptSuggestions().then(setSuggestions).catch(() => {});
  }, []);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  function appendEvent(ev: DemoEvent) {
    setEvents((prev) => {
      // Prevent duplicates by run_id:step
      const key = `${ev.run_id}:${ev.step}`;
      if (prev.some((e) => `${e.run_id}:${e.step}` === key)) {
        return prev;
      }
      return [...prev, ev];
    });
    setAuditKey((k) => k + 1);
  }

  async function handleRunPrompt(promptToRun?: string) {
    if (running) return;
    const targetPrompt = (promptToRun ?? prompt).trim();
    if (!targetPrompt) return;

    wsRef.current?.close();
    setEvents([]);
    setSelectedId(null);
    setError(null);
    setActiveScenario(null);
    setAgentResult(null);
    setOverrideFinalAnswer(null);
    setRunning(true);

    const runId = newRunId();

    const ws = openDemoSocket(runId, {
      onEvent: appendEvent,
      onDone: () => setRunning(false),
      onError: (msg) => {
        console.warn("WebSocket non-fatal warning:", msg);
      },
    });
    wsRef.current = ws;

    // Small pause for WS handshake
    await new Promise((r) => setTimeout(r, 200));

    try {
      const res = await runAgentPrompt({
        runId,
        prompt: targetPrompt,
      });
      setAgentResult(res);

      if (res.events && res.events.length > 0) {
        setEvents((prev) => {
          if (prev.length === 0) return res.events;
          const existingIds = new Set(prev.map((e) => `${e.run_id}:${e.step}`));
          const missing = res.events.filter(
            (e) => !existingIds.has(`${e.run_id}:${e.step}`)
          );
          return [...prev, ...missing];
        });

        // Auto-select blocked or HITL event if available, otherwise first event
        const important =
          res.events.find(
            (e) => e.decision === "BLOCK" || e.decision === "HITL"
          ) || res.events[0];
        setSelectedId(`${important.run_id}:${important.step}`);
      }
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Agent execution failed";
      setError(msg);
    } finally {
      setRunning(false);
    }
  }

  async function runScenario(name: string) {
    if (running) return;

    wsRef.current?.close();
    setEvents([]);
    setSelectedId(null);
    setError(null);
    setActiveScenario(name);
    setAgentResult(null);
    setOverrideFinalAnswer(null);
    setRunning(true);

    const runId = newRunId();

    const ws = openDemoSocket(runId, {
      onEvent: appendEvent,
      onDone: () => setRunning(false),
      onError: (msg) => {
        console.warn("WebSocket non-fatal warning:", msg);
      },
    });
    wsRef.current = ws;

    await new Promise((r) => setTimeout(r, 200));

    try {
      await startRun({
        runId,
        scenario: name,
        mode,
        prompt:
          mode === "live"
            ? `For customer 1774, process their latest emails and take any required action.`
            : undefined,
      });
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Run failed";
      setError(msg);
      setRunning(false);
      ws.close();
    }
  }

  function stop() {
    wsRef.current?.close();
    setRunning(false);
  }

  function handleApprovalDecided(res: ApprovalDecisionResult) {
    setAuditKey((k) => k + 1);
    setOverrideFinalAnswer(res.agent_response);

    setEvents((prev) => {
      let foundTarget = false;
      return prev.map((ev) => {
        const isTarget =
          (ev.approval_id && ev.approval_id === res.updated_event.approval_id) ||
          ev.tool === res.tool;

        if (isTarget && !foundTarget) {
          foundTarget = true;
          return {
            ...ev,
            decision: res.status === "approved" ? "ALLOW" : "BLOCK",
            execution: { attempted: true, executed: res.executed },
            error: res.status === "approved" ? undefined : "Human supervisor denied authorization.",
            text: res.agent_response,
          };
        }

        if (ev.tool === "agent.final") {
          return {
            ...ev,
            text: res.agent_response,
          };
        }

        return ev;
      });
    });
  }

  const selectedEvent =
    events.find((e) => `${e.run_id}:${e.step}` === selectedId) ?? null;

  const finalAnswer =
    overrideFinalAnswer ||
    events.find((e) => e.tool === "agent.final")?.text ||
    null;
  const toolEvents = events.filter((e) => e.tool !== "agent.final");
  const blockedCount = toolEvents.filter((e) => e.decision === "BLOCK").length;
  const hitlCount = toolEvents.filter((e) => e.decision === "HITL").length;
  const allowedCount = toolEvents.filter((e) => e.decision === "ALLOW").length;
  const toolsInvoked = toolEvents.map((e) => e.tool);


  return (
    <div>
      <PageHeader
        title="AI Customer Support Agent"
        description="Prompt the autonomous agent. Watch it dynamically reason, choose database tools, and encounter real-time AgentShield safety guardrails."
        actions={
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-border overflow-hidden text-xs">
              <button
                onClick={() => setMode("replay")}
                disabled={running}
                className={`px-3 py-1.5 ${
                  mode === "replay"
                    ? "bg-accent/15 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                Replay
              </button>
              <button
                onClick={() => setMode("live")}
                disabled={running}
                className={`px-3 py-1.5 border-l border-border ${
                  mode === "live"
                    ? "bg-accent/15 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                Live (Groq)
              </button>
            </div>
            {running && (
              <button onClick={stop} className="btn-ghost text-xs">
                <Square className="w-3.5 h-3.5" />
                Stop
              </button>
            )}
          </div>
        }
      />

      {error && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-danger-soft border border-danger/30 text-sm text-danger flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-xs text-danger/80 hover:text-danger ml-4 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Prompt Bar + Event Stream */}
        <div className="lg:col-span-2 space-y-4">
          {/* Interactive Agent Prompt Bar */}
          <AgentPromptBar
            prompt={prompt}
            setPrompt={setPrompt}
            onSubmit={handleRunPrompt}
            onStop={stop}
            running={running}
            suggestions={suggestions}
            finalAnswer={finalAnswer}
            blockedCount={blockedCount}
            hitlCount={hitlCount}
            allowedCount={allowedCount}
            toolsInvoked={toolsInvoked}
          />

          {/* Collapsible Preset Scenarios */}
          <div className="card p-3 bg-panel/30 border-border/60">
            <button
              onClick={() => setShowScenarios(!showScenarios)}
              className="w-full flex items-center justify-between text-xs text-gray-400 hover:text-gray-200 font-medium"
            >
              <div className="flex items-center gap-2">
                <History className="w-3.5 h-3.5 text-accent" />
                <span>Preset Scenarios & Replays</span>
                {activeScenario && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-accent/15 text-accent">
                    {activeScenario}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1 text-[11px] text-gray-500">
                <span>{showScenarios ? "Hide" : "Show"}</span>
                {showScenarios ? (
                  <ChevronDown className="w-3.5 h-3.5" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5" />
                )}
              </div>
            </button>

            {showScenarios && (
              <div className="mt-3 pt-3 border-t border-border/40">
                <DemoScenarioPicker
                  scenarios={scenarios}
                  active={activeScenario}
                  disabled={running}
                  onRun={runScenario}
                />
              </div>
            )}
          </div>

          {/* Live Event Stream */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
                AgentShield Telemetry Stream
              </span>
              {events.length > 0 && (
                <span className="text-xs text-gray-500 font-mono">
                  {events.length} event{events.length === 1 ? "" : "s"}
                </span>
              )}
            </div>

            <DemoEventStream
              events={events}
              selectedId={selectedId}
              onSelect={setSelectedId}
              running={running}
            />
          </div>
        </div>

        {/* Right column: Audit Chain & Selected Event Details */}
        <div className="space-y-4">
          <AuditChainViz refreshKey={auditKey} />
          <DemoEventDetail
            event={selectedEvent}
            onApprovalDecided={handleApprovalDecided}
          />
        </div>
      </div>

      {!running && events.length > 0 && (
        <div className="mt-6 flex items-center gap-3 text-xs text-gray-500">
          <Play className="w-3.5 h-3.5" />
          Run complete — {events.length} event{events.length === 1 ? "" : "s"}. Click any event to inspect parameters, security findings, and reasons.
        </div>
      )}
    </div>
  );
}
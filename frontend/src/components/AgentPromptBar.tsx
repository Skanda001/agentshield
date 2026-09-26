import React, { useState } from "react";
import {
  Sparkles,
  Send,
  Loader2,
  Square,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Bot,
  RotateCcw,
  Cpu,
  FolderCheck,
  FolderX,
  CreditCard,
  Headphones,
  Zap,
} from "lucide-react";
import type { PromptSuggestion } from "@/lib/demoApi";
import type { AgentPlugin } from "@/lib/pluginsApi";

interface AgentPromptBarProps {
  prompt: string;
  setPrompt: (p: string) => void;
  onSubmit: (promptToRun?: string) => void;
  onStop: () => void;
  running: boolean;
  suggestions: PromptSuggestion[];
  finalAnswer?: string | null;
  blockedCount?: number;
  hitlCount?: number;
  allowedCount?: number;
  toolsInvoked?: string[];
  plugins?: AgentPlugin[];
  activeAgent?: AgentPlugin | null;
  onSelectAgent?: (p: AgentPlugin) => void;
  onTogglePlug?: (p: AgentPlugin) => Promise<void>;
  togglingPlug?: boolean;
}

function getIcon(icon: string) {
  switch (icon) {
    case "headphones":
      return Headphones;
    case "credit-card":
      return CreditCard;
    case "shield-alert":
      return ShieldAlert;
    default:
      return Bot;
  }
}

export default function AgentPromptBar({
  prompt,
  setPrompt,
  onSubmit,
  onStop,
  running,
  suggestions,
  finalAnswer,
  blockedCount = 0,
  hitlCount = 0,
  allowedCount = 0,
  toolsInvoked = [],
  plugins = [],
  activeAgent = null,
  onSelectAgent,
  onTogglePlug,
  togglingPlug = false,
}: AgentPromptBarProps) {
  const [activeCategory, setActiveCategory] = useState<string>("all");

  const filteredSuggestions =
    activeCategory === "all"
      ? suggestions
      : suggestions.filter((s) => {
          if (activeCategory === "safe") return s.expected_verdict === "ALLOW";
          if (activeCategory === "hitl") return s.expected_verdict === "HITL";
          if (activeCategory === "block") return s.expected_verdict === "BLOCK";
          return true;
        });

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!running && prompt.trim() && activeAgent?.is_plugged_in) {
        onSubmit();
      }
    }
  }

  function handleSelectSuggestion(s: PromptSuggestion) {
    setPrompt(s.prompt);
    if (activeAgent?.is_plugged_in) {
      onSubmit(s.prompt);
    }
  }

  const isPlugged = activeAgent ? activeAgent.is_plugged_in : true;
  const ActiveIcon = activeAgent ? getIcon(activeAgent.icon) : Bot;

  return (
    <div className="card p-5 border-slate-800 space-y-4">
      {/* ── 1. Active Agent Selector ── */}
      {plugins.length > 0 && (
        <div className="space-y-2 pb-3 border-b border-slate-800">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-blue-400" />
              Select Agent
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {plugins.map((p) => {
              const Icon = getIcon(p.icon);
              const isSelected = activeAgent?.id === p.id;
              const isMounted = p.is_plugged_in;

              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => onSelectAgent && onSelectAgent(p)}
                  className={`p-2.5 rounded-lg border text-left transition-colors flex items-center justify-between group ${
                    isSelected
                      ? "bg-slate-800/90 border-slate-600 text-white shadow-sm"
                      : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800/50"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 ${
                        isSelected
                          ? "bg-blue-600/20 text-blue-400"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold truncate">
                        {p.name}
                      </div>
                      <div className="text-[10px] text-slate-500 truncate">
                        {p.category}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        isMounted ? "bg-emerald-400" : "bg-slate-600"
                      }`}
                      title={isMounted ? "Active & Mounted" : "Unmounted"}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 2. Current Agent Status Banner ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center border transition-all ${
              isPlugged
                ? "bg-blue-600/10 border-blue-500/30 text-blue-400"
                : "bg-slate-800/80 border-slate-700 text-slate-400"
            }`}
          >
            <ActiveIcon className="w-4 h-4" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white">
                {activeAgent ? activeAgent.name : "Agent"}
              </h2>

              {isPlugged ? (
                <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-500/20 flex items-center gap-1 font-medium">
                  <FolderCheck className="w-3 h-3" />
                  <span>Connected</span>
                </span>
              ) : (
                <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1 font-medium">
                  <FolderX className="w-3 h-3" />
                  <span>Disconnected</span>
                </span>
              )}
            </div>

            <p className="text-xs text-slate-400 mt-0.5">
              {activeAgent
                ? activeAgent.description
                : "Security evaluation and policy decisions."}
            </p>
          </div>
        </div>

        {running && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-xs text-slate-300">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
            <span>Running prompt…</span>
          </div>
        )}
      </div>

      {/* ── 3. Unplugged Warning Banner (if offline) ── */}
      {!isPlugged && activeAgent && (
        <div className="p-3.5 rounded-lg bg-amber-950/30 border border-amber-500/20 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <div className="text-xs text-amber-300">
              Agent is disconnected. Click <strong>Plug In</strong> to enable execution.
            </div>
          </div>

          <button
            type="button"
            onClick={() => onTogglePlug && onTogglePlug(activeAgent)}
            disabled={togglingPlug}
            className="btn-primary py-1.5 px-3 text-xs whitespace-nowrap flex items-center gap-1.5"
          >
            {togglingPlug ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <FolderCheck className="w-3.5 h-3.5" />
            )}
            <span>Plug In Now</span>
          </button>
        </div>
      )}

      {/* ── 4. Prompt Input Area ── */}
      <div className="relative space-y-2">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={running || !isPlugged}
          placeholder={
            isPlugged
              ? `Prompt the ${activeAgent?.name || "agent"} (e.g. "Check details of customer 1008", "Check orders for customer 1001", "Delete customer 1042")...`
              : "Agent is disconnected. Click 'Plug In Now' above to enable execution."
          }
          rows={2}
          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 resize-none transition-colors disabled:opacity-50 font-sans"
        />

        <div className="flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-mono">
            <kbd className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px]">
              Enter
            </kbd>{" "}
            to run &bull;{" "}
            <kbd className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px]">
              Shift+Enter
            </kbd>{" "}
            newline
          </span>

          <div className="flex items-center gap-2">
            {prompt && !running && (
              <button
                type="button"
                onClick={() => setPrompt("")}
                className="btn-ghost py-1.5 px-3 text-xs text-slate-400 hover:text-white"
              >
                <RotateCcw className="w-3 h-3" />
                Clear
              </button>
            )}

            {running ? (
              <button
                type="button"
                onClick={onStop}
                className="btn-danger py-1.5 px-4 text-xs font-bold flex items-center gap-1.5"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                Stop Execution
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onSubmit()}
                disabled={!prompt.trim() || !isPlugged}
                className="btn-primary py-1.5 px-5 text-xs font-bold flex items-center gap-1.5 disabled:opacity-40"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Run Agent
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── 5. Quick Test Suggestions Strip ── */}
      <div className="space-y-2 pt-2 border-t border-slate-800/80">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-300">
            Suggested Prompts
          </span>

          <div className="flex items-center gap-1 text-xs">
            <button
              onClick={() => setActiveCategory("all")}
              className={`px-2.5 py-0.5 rounded transition-colors ${
                activeCategory === "all"
                  ? "bg-slate-800 text-white font-medium"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setActiveCategory("safe")}
              className={`px-2.5 py-0.5 rounded transition-colors ${
                activeCategory === "safe"
                  ? "bg-emerald-950/60 text-emerald-400 font-medium"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Safe
            </button>
            <button
              onClick={() => setActiveCategory("hitl")}
              className={`px-2.5 py-0.5 rounded transition-colors ${
                activeCategory === "hitl"
                  ? "bg-amber-950/60 text-amber-400 font-medium"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Escalated
            </button>
            <button
              onClick={() => setActiveCategory("block")}
              className={`px-2.5 py-0.5 rounded transition-colors ${
                activeCategory === "block"
                  ? "bg-rose-950/60 text-rose-400 font-medium"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Blocked
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {filteredSuggestions.slice(0, 4).map((s, idx) => {
            const badgeCls =
              s.expected_verdict === "BLOCK"
                ? "bg-rose-950/60 text-rose-400 border-rose-500/20"
                : s.expected_verdict === "HITL"
                ? "bg-amber-950/60 text-amber-400 border-amber-500/20"
                : "bg-emerald-950/60 text-emerald-400 border-emerald-500/20";

            return (
              <button
                key={idx}
                onClick={() => handleSelectSuggestion(s)}
                disabled={running}
                className="text-left p-2.5 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-800/40 hover:border-slate-700 transition-colors text-xs group disabled:opacity-50"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-slate-200 group-hover:text-blue-400 transition-colors flex items-center gap-1.5">
                    {s.expected_verdict === "BLOCK" ? (
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
                    ) : s.expected_verdict === "HITL" ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                    ) : (
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    )}
                    {s.title}
                  </span>
                  <span className={`px-1.5 py-0.2 rounded text-[10px] font-mono border ${badgeCls}`}>
                    {s.expected_verdict}
                  </span>
                </div>

                <p className="text-slate-400 text-[11px] line-clamp-1 font-mono">
                  "{s.prompt}"
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── 6. Final Agent Response & Security Summary ── */}
      {finalAnswer && (
        <div className="pt-3 border-t border-slate-800 animate-fade-in space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-blue-400" />
              <span className="text-xs font-semibold text-white">
                Agent Response
              </span>
            </div>

            <div className="flex items-center gap-2 text-[10px] font-mono">
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                Tools: {toolsInvoked.length}
              </span>
              {allowedCount > 0 && (
                <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-500/20">
                  {allowedCount} ALLOW
                </span>
              )}
              {hitlCount > 0 && (
                <span className="px-2 py-0.5 rounded bg-amber-950/60 text-amber-400 border border-amber-500/20">
                  {hitlCount} HITL
                </span>
              )}
              {blockedCount > 0 && (
                <span className="px-2 py-0.5 rounded bg-rose-950/60 text-rose-400 border border-rose-500/20">
                  {blockedCount} BLOCK
                </span>
              )}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
            {finalAnswer}
          </div>
        </div>
      )}
    </div>
  );
}

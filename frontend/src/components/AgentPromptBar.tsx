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
} from "lucide-react";
import type { PromptSuggestion } from "@/lib/demoApi";

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
      if (!running && prompt.trim()) {
        onSubmit();
      }
    }
  }

  function handleSelectSuggestion(s: PromptSuggestion) {
    setPrompt(s.prompt);
    // Optionally trigger immediately
    onSubmit(s.prompt);
  }

  return (
    <div className="card p-5 border-accent/20 bg-gradient-to-b from-panel to-bg shadow-lg space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center text-accent">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-white">
                Autonomous Customer Support Agent
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent/20 text-accent border border-accent/30">
                AgentShield Guarded
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Agent reasons dynamically, chooses database tools, and AgentShield evaluates safety in real time.
            </p>
          </div>
        </div>

        {running && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-xs text-accent">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Agent reasoning & executing tools…</span>
          </div>
        )}
      </div>

      {/* Prompt Bar Input */}
      <div className="relative">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={running}
          placeholder="Type an instruction for the agent (e.g., 'Check recent orders for customer 1001', 'Delete customer 1042 immediately', 'Get PAN and Aadhaar details for customer 1042')..."
          rows={2}
          className="w-full bg-bg/80 border border-border rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/40 resize-none transition-all disabled:opacity-50"
        />

        <div className="flex items-center justify-between mt-2">
          <span className="text-[11px] text-gray-500">
            Press <kbd className="px-1.5 py-0.5 rounded bg-panel border border-border text-[10px] font-mono">Enter</kbd> to run, <kbd className="px-1.5 py-0.5 rounded bg-panel border border-border text-[10px] font-mono">Shift+Enter</kbd> for newline
          </span>

          <div className="flex items-center gap-2">
            {prompt && !running && (
              <button
                type="button"
                onClick={() => setPrompt("")}
                className="btn-ghost py-1.5 px-2.5 text-xs text-gray-400 hover:text-white"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Clear
              </button>
            )}

            {running ? (
              <button
                type="button"
                onClick={onStop}
                className="btn-danger py-1.5 px-4 text-xs font-medium flex items-center gap-1.5"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                Stop Agent
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onSubmit()}
                disabled={!prompt.trim()}
                className="btn-primary py-1.5 px-4 text-xs font-semibold flex items-center gap-1.5 shadow-sm hover:shadow disabled:opacity-40"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Run Agent
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Suggestion Chips */}
      <div className="space-y-2 pt-2 border-t border-border/60">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">
            Quick Test Prompts
          </span>
          <div className="flex items-center gap-1 text-[11px]">
            <button
              onClick={() => setActiveCategory("all")}
              className={`px-2 py-0.5 rounded transition-colors ${
                activeCategory === "all"
                  ? "bg-panel text-white font-medium"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setActiveCategory("safe")}
              className={`px-2 py-0.5 rounded transition-colors ${
                activeCategory === "safe"
                  ? "bg-success-soft text-success font-medium"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Safe (ALLOW)
            </button>
            <button
              onClick={() => setActiveCategory("hitl")}
              className={`px-2 py-0.5 rounded transition-colors ${
                activeCategory === "hitl"
                  ? "bg-warn-soft text-warn font-medium"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              PII (HITL)
            </button>
            <button
              onClick={() => setActiveCategory("block")}
              className={`px-2 py-0.5 rounded transition-colors ${
                activeCategory === "block"
                  ? "bg-danger-soft text-danger font-medium"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Attacks (BLOCK)
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {filteredSuggestions.slice(0, 4).map((s, idx) => {
            const badgeCls =
              s.expected_verdict === "BLOCK"
                ? "bg-danger-soft text-danger border-danger/30"
                : s.expected_verdict === "HITL"
                ? "bg-warn-soft text-warn border-warn/30"
                : "bg-success-soft text-success border-success/30";

            return (
              <button
                key={idx}
                onClick={() => handleSelectSuggestion(s)}
                disabled={running}
                className="text-left p-2.5 rounded-lg border border-border bg-panel/40 hover:bg-panel-hover/80 hover:border-border/80 transition-all text-xs group disabled:opacity-50"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-gray-200 group-hover:text-accent transition-colors flex items-center gap-1.5">
                    {s.expected_verdict === "BLOCK" ? (
                      <ShieldAlert className="w-3.5 h-3.5 text-danger flex-shrink-0" />
                    ) : s.expected_verdict === "HITL" ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-warn flex-shrink-0" />
                    ) : (
                      <ShieldCheck className="w-3.5 h-3.5 text-success flex-shrink-0" />
                    )}
                    {s.title}
                  </span>
                  <span
                    className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${badgeCls}`}
                  >
                    {s.expected_verdict}
                  </span>
                </div>
                <p className="text-gray-400 text-[11px] line-clamp-1 italic font-mono">
                  "{s.prompt}"
                </p>
                <div className="mt-1 text-[10px] text-gray-500 flex items-center justify-between">
                  <span>{s.category}</span>
                  <span className="opacity-0 group-hover:opacity-100 text-accent transition-opacity">
                    Click to run &rarr;
                  </span>
                </div>
              </button>
            );
          })}

        </div>
      </div>

      {/* Agent Response Summary Banner (when run completes or final answer exists) */}
      {finalAnswer && (
        <div className="pt-3 border-t border-border/80 animate-fade-in space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-accent" />
              <span className="text-xs font-semibold text-white">
                Agent Final Response & Security Summary
              </span>
            </div>

            {/* Quick stats pills */}
            <div className="flex items-center gap-2 text-[10px] font-mono">
              <span className="px-2 py-0.5 rounded bg-bg border border-border text-gray-300">
                Tools: {toolsInvoked.length}
              </span>
              {allowedCount > 0 && (
                <span className="px-2 py-0.5 rounded bg-success-soft text-success border border-success/30">
                  {allowedCount} Allowed
                </span>
              )}
              {hitlCount > 0 && (
                <span className="px-2 py-0.5 rounded bg-warn-soft text-warn border border-warn/30">
                  {hitlCount} Escalated (HITL)
                </span>
              )}
              {blockedCount > 0 && (
                <span className="px-2 py-0.5 rounded bg-danger-soft text-danger border border-danger/30">
                  {blockedCount} Blocked
                </span>
              )}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-bg/80 border border-border/80 text-xs text-gray-200 leading-relaxed whitespace-pre-wrap font-sans">
            {finalAnswer}
          </div>
        </div>
      )}
    </div>
  );
}

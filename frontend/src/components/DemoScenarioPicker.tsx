import type { Scenario } from "@/lib/demoApi";

const LABEL: Record<string, string> = {
  normal: "Normal read",
  pii: "PII access",
  destructive: "Destructive action",
  injection: "Prompt injection",
};

const TONE: Record<string, string> = {
  normal: "border-success/30 hover:border-success/60",
  pii: "border-warn/30 hover:border-warn/60",
  destructive: "border-danger/30 hover:border-danger/60",
  injection: "border-danger/60 hover:border-danger shadow-glow-danger",
};

export default function DemoScenarioPicker({
  scenarios,
  active,
  disabled,
  onRun,
}: {
  scenarios: Scenario[];
  active: string | null;
  disabled?: boolean;
  onRun: (name: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {scenarios.map((s) => {
        const isActive = active === s.name;
        return (
          <button
            key={s.name}
            disabled={disabled}
            onClick={() => onRun(s.name)}
            className={`text-left p-3 rounded-lg border transition-all ${TONE[s.name] ?? "border-border"} ${
              isActive ? "bg-panel-hover" : "bg-panel/40"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <div className="font-semibold text-sm">
              {LABEL[s.name] ?? s.name}
            </div>
            <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">
              {s.description}
            </div>
            <div className="text-[10px] text-gray-600 mt-1 uppercase tracking-wider">
              {s.steps} step{s.steps === 1 ? "" : "s"}
            </div>
          </button>
        );
      })}
    </div>
  );
}
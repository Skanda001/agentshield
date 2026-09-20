export default function VerdictBadge({ verdict }: { verdict: string }) {
  const map: Record<string, string> = {
    ALLOW: "bg-success-soft text-success border-success/30",
    BLOCK: "bg-danger-soft text-danger border-danger/30",
    ESCALATE: "bg-warn-soft text-warn border-warn/30",
  };
  const cls = map[verdict] || "bg-panel text-gray-400 border-border";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border tracking-wide ${cls}`}
    >
      {verdict}
    </span>
  );
}
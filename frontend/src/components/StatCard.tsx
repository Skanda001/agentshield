import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";

export default function StatCard({
  label,
  value,
  color,
  icon: Icon,
  subtitle,
}: {
  label: string;
  value: number | string;
  color: "success" | "warn" | "danger" | "accent";
  icon: LucideIcon;
  subtitle?: string;
}) {
  const colorMap = {
    success: { bar: "bg-success", text: "text-success", glow: "shadow-success/10" },
    warn: { bar: "bg-warn", text: "text-warn", glow: "shadow-warn/10" },
    danger: { bar: "bg-danger", text: "text-danger", glow: "shadow-danger/10" },
    accent: { bar: "bg-accent", text: "text-accent", glow: "shadow-accent/10" },
  };
  const c = colorMap[color];

  return (
    <div className="card card-hover relative overflow-hidden animate-slide-up">
      {/* colored top line */}
      <div className={`absolute top-0 left-0 right-0 h-0.5 ${c.bar}`} />
      <div className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className="text-sm text-gray-400 font-medium">{label}</div>
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center bg-panel-hover`}
          >
            <Icon className={`w-4 h-4 ${c.text}`} />
          </div>
        </div>
        <div className={`text-3xl font-bold ${c.text} tracking-tight`}>
          {value}
        </div>
        {subtitle && (
          <div className="text-xs text-gray-500 mt-2">{subtitle}</div>
        )}
      </div>
    </div>
  );
}
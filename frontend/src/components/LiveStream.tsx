import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import VerdictBadge from "./VerdictBadge";
import { Activity } from "lucide-react";

type Decision = {
  id: string;
  tool: string;
  verdict: string;
  risk_score: number;
  created_at: string;
};

export default function LiveStream() {
  const { data: decisions = [] } = useQuery<Decision[]>({
    queryKey: ["decisions"],
    queryFn: async () => (await api.get("/decisions?limit=200")).data,
    refetchInterval: 5000,
  });

  const latest = decisions.slice(0, 10);

  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-4 h-4 text-accent" />
        <span className="font-semibold text-sm">Live activity</span>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-gray-500">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse-soft" />
          polling
        </span>
      </div>

      {latest.length === 0 ? (
        <div className="text-sm text-gray-500 py-8 text-center">
          No decisions yet. Click "Run demo" in the top bar.
        </div>
      ) : (
        <div className="space-y-1.5">
          {latest.map((d, i) => (
            <div
              key={d.id}
              className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-panel-hover transition-colors animate-fade-in"
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <span className="text-xs text-gray-500 font-mono w-16 flex-shrink-0">
                {new Date(d.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </span>
              <span className="font-mono text-sm flex-1 truncate">
                {d.tool}
              </span>
              <VerdictBadge verdict={d.verdict} />
              <span className="text-xs text-gray-500 w-8 text-right">
                {Math.round(d.risk_score)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
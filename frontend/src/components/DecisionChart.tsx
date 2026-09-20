import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { api } from "@/lib/api";

type Decision = {
  id: string;
  verdict: string;
  created_at: string;
};

export default function DecisionChart() {
  const { data: decisions = [] } = useQuery<Decision[]>({
    queryKey: ["decisions"],
    queryFn: async () => (await api.get("/decisions?limit=500")).data,
    refetchInterval: 5000,
  });

  // Group decisions by minute (last 20 minutes)
  const chartData = useMemo(() => {
    const buckets: Record<string, { time: string; ALLOW: number; ESCALATE: number; BLOCK: number }> = {};
    const now = new Date();
    const cutoffMs = 20 * 60 * 1000;

    for (const d of decisions) {
      const t = new Date(d.created_at);
      if (now.getTime() - t.getTime() > cutoffMs) continue;
      const key = `${t.getHours().toString().padStart(2, "0")}:${t
        .getMinutes()
        .toString()
        .padStart(2, "0")}`;
      if (!buckets[key]) {
        buckets[key] = { time: key, ALLOW: 0, ESCALATE: 0, BLOCK: 0 };
      }
      const verdict = d.verdict as "ALLOW" | "ESCALATE" | "BLOCK";
      if (verdict in buckets[key]) {
        buckets[key][verdict] += 1;
      }
    }

    return Object.values(buckets).sort((a, b) => a.time.localeCompare(b.time));
  }, [decisions]);

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-semibold text-sm">Decisions per minute</span>
        <span className="text-xs text-gray-500">last 20 min</span>
      </div>

      {chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-sm text-gray-500">
          No data in the last 20 minutes.
        </div>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} barCategoryGap={2}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#252a37"
                vertical={false}
              />
              <XAxis
                dataKey="time"
                stroke="#6b7280"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="#6b7280"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  background: "#14171f",
                  border: "1px solid #252a37",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                cursor={{ fill: "#4b8bff10" }}
              />
              <Bar dataKey="ALLOW" stackId="a" fill="#2ecc71" radius={[0, 0, 0, 0]} />
              <Bar dataKey="ESCALATE" stackId="a" fill="#ffb84b" radius={[0, 0, 0, 0]} />
              <Bar dataKey="BLOCK" stackId="a" fill="#ff4b4b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="flex items-center gap-4 mt-4 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-sm bg-success" />
          Allow
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-sm bg-warn" />
          Escalate
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-sm bg-danger" />
          Block
        </div>
      </div>
    </div>
  );
}
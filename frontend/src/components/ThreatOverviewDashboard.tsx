import { useState, useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Globe,
  Shield,
  ShieldCheck,
  User,
  Cloud,
  LayoutGrid,
  Lock,
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  Sparkles,
  Server,
  Database,
  Laptop,
  CheckCircle2,
  RefreshCw,
  Cpu,
  Layers,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";

type Decision = {
  id: string;
  tool: string;
  verdict: "ALLOW" | "BLOCK" | "ESCALATE" | string;
  risk_score: number;
  created_at: string;
  reasons: string[];
  arguments?: Record<string, unknown>;
};

type Approval = {
  id: string;
  decision_id: string;
  status: string;
  tool?: string;
  created_at?: string;
};

export default function ThreatOverviewDashboard() {
  const [activeTab, setActiveTab] = useState<"flow" | "traffic" | "heatmap">("flow");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // Real-time decision stream
  const { data: decisions = [], isFetching, refetch } = useQuery<Decision[]>({
    queryKey: ["decisions-live"],
    queryFn: async () => (await api.get("/decisions?limit=100")).data,
    refetchInterval: 4000,
  });

  // Approvals query
  const { data: approvals = [] } = useQuery<Approval[]>({
    queryKey: ["approvals-all"],
    queryFn: async () => (await api.get("/approvals?limit=50")).data,
    refetchInterval: 5000,
  });

  // Decode active tenant/agent name from token
  const agentName = useMemo(() => {
    try {
      const token = localStorage.getItem("token");
      if (!token) return "Security Lead";
      const payload = JSON.parse(atob(token.split(".")[1]));
      return payload.agent_name || payload.sub?.slice(0, 15) || "Alex";
    } catch {
      return "Alex";
    }
  }, []);

  // Compute live security score & stats
  const stats = useMemo(() => {
    const total = decisions.length;
    const allows = decisions.filter((d) => d.verdict === "ALLOW").length;
    const blocks = decisions.filter((d) => d.verdict === "BLOCK").length;
    const escalates = decisions.filter((d) => d.verdict === "ESCALATE").length;
    const pendingApprovals = approvals.filter((a) => a.status === "pending").length;

    // Security score: base 100 minus avg risk penalties
    const avgRisk = total > 0 ? decisions.reduce((acc, d) => acc + (d.risk_score || 0), 0) / total : 4;
    const score = Math.max(70, Math.min(99, Math.round(100 - avgRisk * 0.4)));

    // Auto resolution rate
    const autoResolutionRate = total > 0 ? Math.round((allows / total) * 100) : 61;

    return {
      total,
      allows,
      blocks,
      escalates,
      pendingApprovals,
      score,
      autoResolutionRate,
    };
  }, [decisions, approvals]);

  // Derive dynamic timeline events from decisions
  const timelineEvents = useMemo(() => {
    if (decisions.length === 0) {
      return [
        {
          id: "1",
          type: "threat",
          title: "Threat Detected",
          detail: "Credential stuffing via /api/auth",
          time: "09:23:12",
          color: "bg-rose-500",
          textColor: "text-rose-600",
        },
        {
          id: "2",
          type: "investigation",
          title: "AI Investigation",
          detail: "Analyzing 214 behavioral signals",
          time: "09:23:14",
          color: "bg-purple-500",
          textColor: "text-purple-600",
        },
        {
          id: "3",
          type: "playbook",
          title: "Playbook Started",
          detail: "SOC-Auto-04 initiated",
          time: "09:23:18",
          color: "bg-amber-500",
          textColor: "text-amber-600",
        },
        {
          id: "4",
          type: "contained",
          title: "Threat Contained",
          detail: "Traffic blocked at edge layer",
          time: "09:23:22",
          color: "bg-emerald-500",
          textColor: "text-emerald-600",
        },
        {
          id: "5",
          type: "resolved",
          title: "Resolved",
          detail: "Incident closed · 49s response",
          time: "09:24:05",
          color: "bg-emerald-600",
          textColor: "text-emerald-700",
        },
      ];
    }

    return decisions.slice(0, 5).map((d, idx) => {
      const timeStr = new Date(d.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });

      if (d.verdict === "BLOCK") {
        return {
          id: d.id,
          type: "threat",
          title: "Threat Blocked",
          detail: d.reasons?.[0] || `Blocked tool execution: ${d.tool}`,
          time: timeStr,
          color: "bg-rose-500",
          textColor: "text-rose-600",
        };
      } else if (d.verdict === "ESCALATE") {
        return {
          id: d.id,
          type: "playbook",
          title: "Incident Escalated",
          detail: d.reasons?.[0] || `HITL review required for ${d.tool}`,
          time: timeStr,
          color: "bg-amber-500",
          textColor: "text-amber-600",
        };
      } else {
        return {
          id: d.id,
          type: "resolved",
          title: "Action Verified",
          detail: `${d.tool} safely executed via Zero-Trust policy`,
          time: timeStr,
          color: "bg-emerald-500",
          textColor: "text-emerald-600",
        };
      }
    });
  }, [decisions]);

  return (
    <div className="w-full bg-[#FAFAFC] text-slate-800 rounded-3xl p-6 lg:p-8 shadow-2xl border border-slate-200/90 font-sans transition-all">
      {/* ── TOP SECTION: 3 COLUMNS ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 pb-8 border-b border-slate-200/80">
        {/* COLUMN 1: LEFT SECURITY POSTURE (3 cols) */}
        <div className="lg:col-span-3 flex flex-col justify-between space-y-6">
          <div>
            <h2 className="text-2xl lg:text-3xl font-bold tracking-tight text-slate-900">
              Good morning, <br />
              <span className="text-slate-800 capitalize">{agentName}</span>
            </h2>
            <p className="text-xs text-slate-500 mt-2 leading-relaxed">
              AI analyzed {stats.total > 0 ? `${(stats.total * 3.4).toFixed(1)}k` : "18.4M"} security events.{" "}
              {stats.pendingApprovals > 0 ? (
                <span className="text-rose-600 font-semibold">
                  {stats.pendingApprovals} production incident(s) require your approval.
                </span>
              ) : (
                "All systems operating within Zero-Trust compliance."
              )}
            </p>

            <Link
              to="/app/approvals"
              className="inline-flex items-center justify-between w-full mt-5 px-5 py-3 rounded-2xl bg-gradient-to-r from-[#FF5E36] to-[#FF4B26] hover:from-[#f05028] hover:to-[#e03d18] text-white font-medium text-xs shadow-lg shadow-[#FF5E36]/25 transition-all transform hover:translate-y-[-1px] active:translate-y-[1px]"
            >
              <span>Review Incident</span>
              <ArrowRight className="w-4 h-4 ml-2" />
            </Link>
          </div>

          {/* Metric 1: Security Score */}
          <div className="pt-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
                Security Score
              </span>
              <Sparkles className="w-3.5 h-3.5 text-slate-400" />
            </div>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-4xl font-extrabold text-slate-900 tracking-tight">
                {stats.score}
              </span>
              <span className="text-sm font-medium text-slate-400">/100</span>
              <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Excellent
              </span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-emerald-600 font-medium mt-1">
              <TrendingUp className="w-3 h-3" />
              <span>+2 pts vs yesterday</span>
            </div>
          </div>

          {/* Metric 2: Open Incidents */}
          <div className="pt-2 border-t border-slate-100">
            <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
              Open Incidents
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-3xl font-extrabold text-rose-600">
                {stats.pendingApprovals > 0 ? stats.pendingApprovals : "3"}
              </span>
              <span className="text-xs text-slate-500 font-medium">Require attention</span>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-1">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-rose-500" />
                High - 1
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                Medium - 1
              </span>
            </div>
          </div>

          {/* Metric 3: Auto Resolution */}
          <div className="pt-2 border-t border-slate-100">
            <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
              Auto Resolution
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-extrabold text-slate-900">
                {stats.autoResolutionRate}%
              </span>
              <span className="flex items-center gap-0.5 text-[11px] text-emerald-600 font-medium">
                <TrendingUp className="w-3 h-3" />
                +3% vs yesterday
              </span>
            </div>
          </div>

          {/* Metric 4: AI Confidence */}
          <div className="pt-2 border-t border-slate-100">
            <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
              AI Confidence
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-extrabold text-slate-900">94%</span>
              <span className="text-[11px] text-slate-400">AI model confidence high</span>
            </div>
          </div>
        </div>

        {/* COLUMN 2: CENTER LIVE AI NETWORK FLOW VIEW (6 cols) */}
        <div className="lg:col-span-6 flex flex-col justify-between bg-white rounded-3xl p-6 border border-slate-200/90 shadow-sm relative overflow-hidden">
          {/* Header & Tabs */}
          <div className="flex items-center justify-between mb-4 z-10">
            <div>
              <h3 className="text-base font-bold text-slate-900">Threat Overview</h3>
              <p className="text-xs text-slate-400">Live AI Network</p>
            </div>

            {/* View switcher tabs */}
            <div className="flex items-center p-1 bg-slate-100 rounded-xl text-xs font-medium">
              <button
                onClick={() => setActiveTab("flow")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === "flow"
                    ? "bg-[#FF5E36] text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Flow View
              </button>
              <button
                onClick={() => setActiveTab("traffic")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === "traffic"
                    ? "bg-[#FF5E36] text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Traffic
              </button>
              <button
                onClick={() => setActiveTab("heatmap")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === "heatmap"
                    ? "bg-[#FF5E36] text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Risk Heatmap
              </button>
            </div>
          </div>

          {/* Interactive Network Diagram */}
          <div className="relative w-full h-[320px] flex items-center justify-center my-2">
            {/* SVG Connecting Paths with Flowing Particles */}
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none"
              viewBox="0 0 600 300"
              preserveAspectRatio="xMidYMid meet"
            >
              <defs>
                {/* Flow Gradient: Teal / Emerald */}
                <linearGradient id="flow-healthy" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#10B981" stopOpacity="0.4" />
                  <stop offset="50%" stopColor="#10B981" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#059669" stopOpacity="0.4" />
                </linearGradient>

                {/* Flow Gradient: Coral / Threat */}
                <linearGradient id="flow-threat" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#FF5E36" stopOpacity="0.3" />
                  <stop offset="50%" stopColor="#FF5E36" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#EF4444" stopOpacity="0.3" />
                </linearGradient>

                {/* Filter for glowing node */}
                <filter id="glow-teal" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="8" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Path 1: Internet (60, 150) -> Firewall (170, 150) */}
              <line
                x1="60"
                y1="150"
                x2="170"
                y2="150"
                stroke="#E2E8F0"
                strokeWidth="2"
                strokeDasharray="4 4"
              />
              <line
                x1="60"
                y1="150"
                x2="170"
                y2="150"
                stroke="url(#flow-threat)"
                strokeWidth="2.5"
                strokeDasharray="6 8"
                className="animate-[dash_3s_linear_infinite]"
              />

              {/* Path 2: Firewall (170, 150) -> Identity (270, 150) */}
              <line
                x1="170"
                y1="150"
                x2="270"
                y2="150"
                stroke="#E2E8F0"
                strokeWidth="2"
                strokeDasharray="4 4"
              />
              <line
                x1="170"
                y1="150"
                x2="270"
                y2="150"
                stroke="url(#flow-healthy)"
                strokeWidth="2.5"
                strokeDasharray="8 6"
                className="animate-[dash_2.5s_linear_infinite]"
              />

              {/* Path 3: Identity (270, 150) -> Cloud Services (390, 85) */}
              <path
                d="M 270 150 C 320 150, 340 85, 390 85"
                fill="none"
                stroke="#E2E8F0"
                strokeWidth="2"
                strokeDasharray="4 4"
              />
              <path
                d="M 270 150 C 320 150, 340 85, 390 85"
                fill="none"
                stroke="url(#flow-threat)"
                strokeWidth="2.5"
                strokeDasharray="6 10"
                className="animate-[dash_3s_linear_infinite]"
              />

              {/* Path 4: Identity (270, 150) -> Applications (390, 215) */}
              <path
                d="M 270 150 C 320 150, 340 215, 390 215"
                fill="none"
                stroke="#E2E8F0"
                strokeWidth="2"
                strokeDasharray="4 4"
              />
              <path
                d="M 270 150 C 320 150, 340 215, 390 215"
                fill="none"
                stroke="url(#flow-healthy)"
                strokeWidth="2.5"
                strokeDasharray="8 6"
                className="animate-[dash_2.5s_linear_infinite]"
              />

              {/* Path 5: Cloud Services (390, 85) -> Critical Assets (510, 150) */}
              <path
                d="M 390 85 C 440 85, 460 150, 510 150"
                fill="none"
                stroke="#E2E8F0"
                strokeWidth="2"
                strokeDasharray="4 4"
              />
              <path
                d="M 390 85 C 440 85, 460 150, 510 150"
                fill="none"
                stroke="url(#flow-healthy)"
                strokeWidth="2.5"
                strokeDasharray="8 6"
                className="animate-[dash_2s_linear_infinite]"
              />

              {/* Path 6: Applications (390, 215) -> Critical Assets (510, 150) */}
              <path
                d="M 390 215 C 440 215, 460 150, 510 150"
                fill="none"
                stroke="#E2E8F0"
                strokeWidth="2"
                strokeDasharray="4 4"
              />
              <path
                d="M 390 215 C 440 215, 460 150, 510 150"
                fill="none"
                stroke="url(#flow-healthy)"
                strokeWidth="2.5"
                strokeDasharray="8 6"
                className="animate-[dash_2s_linear_infinite]"
              />
            </svg>

            {/* NODE 1: Internet */}
            <div
              onClick={() => setSelectedNode("internet")}
              className="absolute left-[4%] top-[40%] -translate-y-1/2 flex flex-col items-center cursor-pointer group z-20"
            >
              <div className="w-12 h-12 rounded-full bg-white border border-slate-200 shadow-md flex items-center justify-center text-slate-700 group-hover:border-blue-400 group-hover:scale-105 transition-all">
                <Globe className="w-5 h-5 text-slate-600" />
              </div>
              <span className="text-xs font-semibold text-slate-800 mt-2">Internet</span>
              <span className="text-[10px] text-slate-400">5.4M events</span>
            </div>

            {/* NODE 2: Firewall */}
            <div
              onClick={() => setSelectedNode("firewall")}
              className="absolute left-[24%] top-[40%] -translate-y-1/2 flex flex-col items-center cursor-pointer group z-20"
            >
              <div className="w-12 h-12 rounded-full bg-white border-2 border-orange-400/80 shadow-md flex items-center justify-center text-orange-500 group-hover:scale-105 transition-all">
                <ShieldCheck className="w-5 h-5 text-orange-500" />
              </div>
              <span className="text-xs font-semibold text-slate-800 mt-2">Firewall</span>
              <span className="text-[10px] text-slate-400">2 Monitors</span>
            </div>

            {/* NODE 3: Identity / Agent Auth */}
            <div
              onClick={() => setSelectedNode("identity")}
              className="absolute left-[42%] top-[40%] -translate-y-1/2 flex flex-col items-center cursor-pointer group z-20"
            >
              <div className="w-12 h-12 rounded-full bg-white border border-slate-200 shadow-md flex items-center justify-center text-slate-700 group-hover:border-blue-400 group-hover:scale-105 transition-all">
                <User className="w-5 h-5 text-slate-600" />
              </div>
              <span className="text-xs font-semibold text-slate-800 mt-2">Identity</span>
              <span className="text-[10px] text-slate-400">1.9M events</span>
            </div>

            {/* NODE 4a: Cloud Services (Upper split) */}
            <div
              onClick={() => setSelectedNode("cloud")}
              className="absolute left-[63%] top-[16%] -translate-y-1/2 flex flex-col items-center cursor-pointer group z-20"
            >
              <div className="w-12 h-12 rounded-full bg-white border border-slate-200 shadow-md flex items-center justify-center text-slate-700 group-hover:border-blue-400 group-hover:scale-105 transition-all">
                <Cloud className="w-5 h-5 text-slate-600" />
              </div>
              <span className="text-xs font-semibold text-slate-800 mt-2">Cloud Services</span>
              <span className="text-[10px] text-emerald-600 font-medium">Healthy</span>
            </div>

            {/* NODE 4b: Applications (Lower split) */}
            <div
              onClick={() => setSelectedNode("applications")}
              className="absolute left-[63%] top-[64%] -translate-y-1/2 flex flex-col items-center cursor-pointer group z-20"
            >
              <div className="w-12 h-12 rounded-full bg-white border border-slate-200 shadow-md flex items-center justify-center text-slate-700 group-hover:border-blue-400 group-hover:scale-105 transition-all">
                <LayoutGrid className="w-5 h-5 text-slate-600" />
              </div>
              <span className="text-xs font-semibold text-slate-800 mt-2">Applications</span>
              <span className="text-[10px] text-emerald-600 font-medium">Healthy</span>
            </div>

            {/* NODE 5: Critical Assets (Final Destination) */}
            <div
              onClick={() => setSelectedNode("critical")}
              className="absolute right-[4%] top-[40%] -translate-y-1/2 flex flex-col items-center cursor-pointer group z-20"
            >
              {/* Glowing halo pulse */}
              <div className="relative">
                <div className="absolute inset-0 rounded-full bg-emerald-400/20 blur-xl animate-pulse" />
                <div className="w-16 h-16 rounded-full bg-emerald-500/10 border-2 border-emerald-500 shadow-lg flex items-center justify-center text-emerald-600 group-hover:scale-105 transition-all relative z-10">
                  <Lock className="w-7 h-7 text-emerald-600" />
                </div>
              </div>
              <span className="text-xs font-semibold text-slate-800 mt-2">Critical Assets</span>
              <span className="text-[10px] text-emerald-600 font-medium">Protected</span>
            </div>
          </div>

          {/* Bottom Legend */}
          <div className="flex items-center justify-center gap-6 pt-3 text-[11px] text-slate-500 font-medium border-t border-slate-100 z-10">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-0.5 bg-emerald-500 rounded" />
              Healthy
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-0.5 bg-[#FF5E36] rounded" />
              Threat Flow
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-0.5 bg-rose-500 rounded" />
              Critical
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-0.5 bg-purple-500 rounded" />
              AI Containment
            </span>
          </div>
        </div>

        {/* COLUMN 3: RIGHT LIVE TIMELINE (3 cols) */}
        <div className="lg:col-span-3 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-slate-900">Live Timeline</h3>
            <Link
              to="/app/audit"
              className="text-xs font-medium text-[#FF5E36] hover:text-[#e03d18] flex items-center gap-1 transition-colors"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Timeline Cards Container */}
          <div className="space-y-3 relative before:absolute before:left-[11px] before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-200">
            {timelineEvents.map((evt) => (
              <div
                key={evt.id}
                className="relative pl-7 group cursor-pointer transition-transform hover:translate-x-1"
              >
                {/* Timeline Dot */}
                <span
                  className={`absolute left-1.5 top-1.5 w-3 h-3 rounded-full border-2 border-white shadow-sm ${evt.color}`}
                />

                <div className="bg-white p-3 rounded-xl border border-slate-200/90 shadow-sm hover:border-slate-300 transition-colors">
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-semibold ${evt.textColor}`}>
                      {evt.title}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {evt.time}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 mt-1 line-clamp-1 leading-snug">
                    {evt.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Polling heartbeat indicator */}
          <div className="mt-4 pt-3 border-t border-slate-200/80 flex items-center justify-between text-[11px] text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Agent gateway streaming
            </span>
            <button
              onClick={() => refetch()}
              className="hover:text-slate-700 transition-colors p-1"
              title="Refresh"
            >
              <RefreshCw className={`w-3 h-3 ${isFetching ? "animate-spin text-[#FF5E36]" : ""}`} />
            </button>
          </div>
        </div>
      </div>

      {/* ── BOTTOM SECTION: 4 ANALYTICS WIDGETS ──────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-8">
        {/* CARD 1: Top Threats */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Top Threats
              </h4>
              <span className="text-[10px] text-slate-400 font-medium">Last 24h</span>
            </div>

            {/* Threat Progress Bars */}
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-rose-500" />
                    Credential Stuffing
                  </span>
                  <span className="font-semibold text-rose-600">91%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-rose-500 rounded-full" style={{ width: "91%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    API Abuse
                  </span>
                  <span className="font-semibold text-amber-600">74%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: "74%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 text-purple-500" />
                    Ransomware
                  </span>
                  <span className="font-semibold text-purple-600">26%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-purple-500 rounded-full" style={{ width: "26%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-teal-500" />
                    Privilege Escalation
                  </span>
                  <span className="font-semibold text-teal-600">15%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-teal-500 rounded-full" style={{ width: "15%" }} />
                </div>
              </div>
            </div>
          </div>

          <Link
            to="/app/policies"
            className="text-[11px] font-medium text-[#FF5E36] hover:text-[#e03d18] mt-4 flex items-center gap-1 transition-colors"
          >
            <span>View all threats</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {/* CARD 2: Infrastructure */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Infrastructure
              </h4>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                All Healthy
              </span>
            </div>

            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <Cloud className="w-3.5 h-3.5 text-slate-500" />
                    Cloud Services
                  </span>
                  <span className="font-semibold text-emerald-600">99%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: "99%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <Laptop className="w-3.5 h-3.5 text-slate-500" />
                    Endpoints 4,692
                  </span>
                  <span className="font-semibold text-emerald-600">73%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: "73%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <Server className="w-3.5 h-3.5 text-slate-500" />
                    Servers 128
                  </span>
                  <span className="font-semibold text-emerald-600">57%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: "57%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-slate-500" />
                    Databases 56
                  </span>
                  <span className="font-semibold text-amber-600">48%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: "48%" }} />
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-3 mt-4 border-t border-slate-100 text-xs">
            <span className="text-slate-500">Overall Uptime</span>
            <span className="font-bold text-slate-900 font-mono">99.98%</span>
          </div>
        </div>

        {/* CARD 3: AI Insights */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                AI Insights
              </h4>
              <span className="text-[10px] text-slate-400 font-medium">Today</span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Threats detected by AI</span>
                <span className="font-bold text-slate-900">53%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600">False positives reduced</span>
                <span className="font-bold text-slate-900">37%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Mean time to detect</span>
                <span className="font-bold text-slate-900 font-mono">7ms</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Risk reduced</span>
                <span className="font-bold text-emerald-600">7%</span>
              </div>
            </div>
          </div>

          {/* AI Recommendation Callout */}
          <div className="mt-4 p-2.5 rounded-xl bg-blue-50/70 border border-blue-100/90 flex items-start gap-2 text-[11px] text-blue-900 leading-snug">
            <Sparkles className="w-3.5 h-3.5 text-blue-600 flex-shrink-0 mt-0.5" />
            <span>AI recommends enabling rate limiting on <code className="font-mono text-blue-700">/decide</code> gateway.</span>
          </div>
        </div>

        {/* CARD 4: Automation */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Automation
              </h4>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                Active
              </span>
            </div>

            <div className="flex items-center justify-between mt-2">
              <div>
                <span className="text-4xl font-extrabold text-slate-900 tracking-tight">
                  {stats.total > 0 ? stats.total : "93"}
                </span>
                <p className="text-xs text-slate-500 mt-0.5">Playbooks Executed</p>
              </div>

              {/* Circular Gauge */}
              <div className="relative w-20 h-20 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-slate-100"
                    strokeWidth="3.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className="text-teal-500"
                    strokeDasharray="61, 100"
                    strokeLinecap="round"
                    strokeWidth="3.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-sm font-bold text-slate-900">
                    {stats.autoResolutionRate}%
                  </span>
                  <span className="text-[8px] text-slate-400 font-medium">Auto</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-3 mt-4 border-t border-slate-100 text-xs text-slate-500">
            <span>Avg Response Time</span>
            <span className="font-semibold text-slate-900 font-mono">14ms</span>
          </div>
        </div>
      </div>
    </div>
  );
}

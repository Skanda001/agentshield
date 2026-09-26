import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  RefreshCw,
  FolderCheck,
  FolderX,
  Bot,
  Headphones,
  CreditCard,
  ShieldAlert,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import {
  listPlugins,
  plugInAgent,
  plugOutAgent,
  type AgentPlugin,
} from "@/lib/pluginsApi";

export const Route = createFileRoute("/app/plugins")({
  component: PluginsPage,
});

function getAgentIcon(icon: string) {
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

function PluginsPage() {
  const [plugins, setPlugins] = useState<AgentPlugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  async function loadPlugins() {
    setLoading(true);
    try {
      const data = await listPlugins();
      setPlugins(data);
    } catch (err) {
      console.error("Failed to load plugins:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlugins();
  }, []);

  async function handleTogglePlugin(plugin: AgentPlugin) {
    setTogglingId(plugin.id);
    setNotification(null);
    try {
      if (plugin.is_plugged_in) {
        const res = await plugOutAgent(plugin.id);
        setPlugins((prev) =>
          prev.map((p) => (p.id === plugin.id ? res.plugin : p))
        );
        setNotification({
          type: "success",
          message: `Agent '${plugin.name}' disconnected.`,
        });
      } else {
        const res = await plugInAgent(plugin.id);
        setPlugins((prev) =>
          prev.map((p) => (p.id === plugin.id ? res.plugin : p))
        );
        setNotification({
          type: "success",
          message: `Agent '${plugin.name}' connected and mounted.`,
        });
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Action failed on server.";
      setNotification({ type: "error", message: msg });
    } finally {
      setTogglingId(null);
    }
  }

  const pluggedCount = plugins.filter((p) => p.is_plugged_in).length;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Agents"
        description="Plug in external agents to route their tool calls through AgentShield."
        actions={
          <button
            onClick={loadPlugins}
            disabled={loading}
            className="btn-ghost text-xs flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Rescan</span>
          </button>
        }
      />

      {notification && (
        <div
          className={`px-3.5 py-2.5 rounded-lg border text-xs flex items-center justify-between animate-fade-in ${
            notification.type === "success"
              ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
              : "bg-rose-950/40 border-rose-500/30 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-2">
            {notification.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            )}
            <span>{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-slate-400 hover:text-white text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* Agents Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>{pluggedCount} of {plugins.length} agents active</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plugins.map((plugin) => {
            const Icon = getAgentIcon(plugin.icon);
            const isPlugged = plugin.is_plugged_in;
            const isToggling = togglingId === plugin.id;
            const isExpanded = expandedId === plugin.id;

            return (
              <div
                key={plugin.id}
                className={`card p-4 flex flex-col justify-between transition-colors ${
                  isPlugged ? "border-slate-700 bg-slate-900/80" : "border-slate-800 bg-slate-900/40"
                }`}
              >
                <div className="space-y-3">
                  {/* Status header */}
                  <div className="flex items-center justify-between">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium ${
                        isPlugged
                          ? "bg-emerald-950/60 text-emerald-400 border border-emerald-500/20"
                          : "bg-slate-800 text-slate-400 border border-slate-700"
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          isPlugged ? "bg-emerald-400" : "bg-slate-500"
                        }`}
                      />
                      <span>{isPlugged ? "Connected" : "Disconnected"}</span>
                    </span>

                    <span className="text-[11px] text-slate-500 font-mono">
                      v{plugin.version}
                    </span>
                  </div>

                  {/* Identity */}
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        isPlugged
                          ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-sm font-semibold text-white truncate">
                        {plugin.name}
                      </h3>
                      <div className="text-[11px] text-slate-400">
                        {plugin.category} · by {plugin.author}
                      </div>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {plugin.description}
                  </p>

                  {/* Folder Location */}
                  <div className="px-2.5 py-1.5 rounded-md bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
                    <span>Directory:</span>
                    <span className={isPlugged ? "text-emerald-400" : "text-slate-400"}>
                      {isPlugged ? `./plugged_agents/${plugin.id}` : `external-agents/${plugin.id}`}
                    </span>
                  </div>

                  {/* Tools toggle */}
                  <div>
                    <button
                      onClick={() =>
                        setExpandedId(isExpanded ? null : plugin.id)
                      }
                      className="text-[11px] text-blue-400 hover:text-blue-300 font-medium"
                    >
                      {isExpanded ? "Hide tools" : `View tools (${plugin.tools.length})`}
                    </button>

                    {isExpanded && (
                      <div className="mt-2 space-y-1 pt-2 border-t border-slate-800 max-h-40 overflow-y-auto">
                        {plugin.tools.map((t, idx) => (
                          <div
                            key={idx}
                            className="px-2 py-1 rounded bg-slate-950 text-[11px] flex items-center justify-between font-mono"
                          >
                            <span className="text-slate-300">{t.name}</span>
                            <span
                              className={`text-[10px] px-1.5 py-0.2 rounded font-semibold ${
                                t.blocked_by_default
                                  ? "text-rose-400 bg-rose-950/40"
                                  : t.requires_hitl
                                  ? "text-amber-400 bg-amber-950/40"
                                  : "text-emerald-400 bg-emerald-950/40"
                              }`}
                            >
                              {t.blocked_by_default ? "BLOCK" : t.requires_hitl ? "HITL" : "ALLOW"}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Action */}
                <div className="pt-4 space-y-2">
                  <button
                    onClick={() => handleTogglePlugin(plugin)}
                    disabled={isToggling}
                    className={`w-full py-2 rounded-lg font-medium text-xs flex items-center justify-center gap-1.5 transition-colors ${
                      isPlugged
                        ? "btn-ghost text-rose-300 hover:text-rose-200 hover:bg-rose-950/30 hover:border-rose-800"
                        : "btn-primary"
                    }`}
                  >
                    {isToggling ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Updating…</span>
                      </>
                    ) : isPlugged ? (
                      <>
                        <FolderX className="w-3.5 h-3.5" />
                        <span>Disconnect</span>
                      </>
                    ) : (
                      <>
                        <FolderCheck className="w-3.5 h-3.5" />
                        <span>Plug In</span>
                      </>
                    )}
                  </button>

                  {isPlugged && (
                    <Link
                      to="/app/demo"
                      className="w-full btn-ghost py-1.5 text-xs flex items-center justify-center gap-1.5 text-slate-300 hover:text-white"
                    >
                      <span>Open in Playground</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

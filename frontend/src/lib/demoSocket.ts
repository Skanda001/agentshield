import { API_URL } from "./api";
import type { DemoEvent } from "./demoApi";

function wsBase(): string {
  // API_URL is set via VITE_API_URL env var pointing to Render backend.
  // Convert http(s) → ws(s) correctly.
  return API_URL.replace(/^http/, "ws");
}

export type SocketHandlers = {
  onEvent: (ev: DemoEvent) => void;
  onDone: () => void;
  onError: (err: string) => void;
};

export function openDemoSocket(
  runId: string,
  handlers: SocketHandlers
): WebSocket {
  const token = localStorage.getItem("token") || "";
  const url = `${wsBase()}/api/v1/demo/ws?run_id=${encodeURIComponent(
    runId
  )}&token=${encodeURIComponent(token)}`;

  const ws = new WebSocket(url);

  // Fix #1: If WebSocket fails to open within 5 seconds, call onDone so
  // the UI doesn't get stuck in "running" state forever.
  const openTimeout = setTimeout(() => {
    if (ws.readyState === WebSocket.CONNECTING) {
      handlers.onError(
        "WebSocket connection timed out — events may arrive via HTTP fallback."
      );
      handlers.onDone();
      try {
        ws.close();
      } catch {
        // ignore
      }
    }
  }, 5000);

  ws.onopen = () => {
    clearTimeout(openTimeout);
  };

  ws.onmessage = (msg) => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(msg.data);
    } catch {
      return;
    }

    if (parsed.__ping__) return;

    if (parsed.__done__) {
      handlers.onDone();
      ws.close();
      return;
    }

    handlers.onEvent(parsed as unknown as DemoEvent);
  };

  ws.onclose = (e) => {
    clearTimeout(openTimeout);
    if (e.code === 4401) {
      handlers.onError("Session expired — please log in again.");
      localStorage.removeItem("token");
    }
  };

  ws.onerror = () => {
    clearTimeout(openTimeout);
    handlers.onError("WebSocket connection error.");
    // Fix #1: ensure UI is never stuck spinning after a WS error
    handlers.onDone();
  };

  return ws;
}
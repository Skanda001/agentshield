import { API_URL } from "./api";
import type { DemoEvent } from "./demoApi";

function wsBase(): string {
  // http://localhost:8001 -> ws://localhost:8001
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
    if (e.code === 4401) {
      handlers.onError("Session expired — please log in again.");
      localStorage.removeItem("token");
    }
  };

  ws.onerror = () => {
    handlers.onError("WebSocket error");
  };

  return ws;
}
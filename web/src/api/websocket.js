/**
 * WebSocket hook for real-time show state and command dispatch.
 */
import { useState, useEffect, useRef, useCallback } from "react";

const INITIAL_STATE = {
  show_state: "idle",
  show_title: "",
  failure_count: 0,
  current_step: null,
  current_index: 0,
  total_steps: 0,
  upcoming_steps: [],
  displayed_caption: { text: "", color: "#ffffff" },
  loading_message: "",
  transcript: { lines: [], partial: "" },
  mic: { level: 0, streaming: false },
  tasks: {},
  timer: { remaining: 0, total: 0 },
  audio_layers: {},
  steps_outline: [],
};

export function useShowState() {
  const [state, setState] = useState(INITIAL_STATE);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/ws`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "state_update" && msg.data) {
          setState((prev) => ({ ...prev, ...msg.data }));
        }
      } catch {}
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 2000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  const sendCommand = useCallback((command, args = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command, args }));
    }
  }, []);

  return { state, connected, sendCommand };
}

"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL } from "@/lib/constants";

/**
 * Subscribes to the project's WebSocket channel and invokes `onUpdate`
 * with each `pipeline:update` payload. Reconnects automatically.
 */
export function useSocket(
  projectId: string | null,
  onUpdate: (data: Record<string, unknown>) => void
): { connected: boolean } {
  const [connected, setConnected] = useState(false);
  const onUpdateRef = useRef(onUpdate);

  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    if (!projectId) return;

    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    function connect() {
      ws = new WebSocket(`${WS_URL.replace("http", "ws")}/ws/${projectId}`);

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "pipeline:update") {
            onUpdateRef.current(message.data);
          }
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!disposed) {
          retryTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws?.close();
      };
    }

    connect();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [projectId]);

  return { connected };
}

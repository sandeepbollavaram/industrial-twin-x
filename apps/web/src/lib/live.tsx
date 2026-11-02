"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { Overview, WS_URL } from "./api";

type Live = { overview: Overview | null; connected: boolean };

const LiveContext = createContext<Live>({ overview: null, connected: false });

export function LiveProvider({ children }: { children: ReactNode }) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let closed = false;
    const open = () => {
      socket = new WebSocket(WS_URL);
      socket.onopen = () => setConnected(true);
      socket.onmessage = (event) => setOverview(JSON.parse(event.data));
      socket.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(open, 2000);
      };
      socket.onerror = () => socket?.close();
    };
    open();
    return () => {
      closed = true;
      clearTimeout(retry);
      socket?.close();
    };
  }, []);

  return <LiveContext.Provider value={{ overview, connected }}>{children}</LiveContext.Provider>;
}

export const useLive = () => useContext(LiveContext);

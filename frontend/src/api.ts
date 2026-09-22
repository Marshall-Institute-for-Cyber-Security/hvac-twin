import { useEffect, useRef, useState } from "react";
import { getApiBase, getWsBase } from "./config";
import type { ApiTarget } from "./config";

export type TagPrimitive = string | number | boolean;

export interface StatusOut {
  scan_count: number;
  elapsed: number;
}

export interface EventOut {
  timestamp: number;
  scan: number | null;
  category: string;
  severity: string;
  source: string;
  message: string;
  data: Record<string, TagPrimitive>;
}

export interface SeriesPoint {
  timestamp: number;
  value: TagPrimitive;
}

export interface StreamMessage {
  scan_count: number;
  elapsed: number;
  tags: Record<string, TagPrimitive>;
  events: EventOut[];
}

/** One twin, one backend process, one API client -- built from an
 * `ApiTarget` (see config.ts) rather than a single hardcoded backend, so
 * a second twin (the office wing, its own hvac_twin.hmi process on its
 * own port) gets its own client instance instead of this module growing
 * a twin parameter on every function. */
export function createApiClient(target: Pick<ApiTarget, "getApiBase" | "getWsBase">) {
  async function getJson<T>(path: string): Promise<T> {
    const response = await fetch(`${target.getApiBase()}${path}`);
    if (!response.ok) {
      throw new Error(`${path} -> ${response.status}`);
    }
    return (await response.json()) as T;
  }

  const getStatus = (): Promise<StatusOut> => getJson("/status");
  const getTags = (): Promise<Record<string, TagPrimitive>> => getJson("/tags");
  const getBusSignal = (signal: string): Promise<{ name: string; value: TagPrimitive }> =>
    getJson(`/bus/${signal}`);
  const getSeries = (tag: string): Promise<SeriesPoint[]> => getJson(`/historian/${tag}`);
  const getEvents = (): Promise<EventOut[]> => getJson("/events");

  /** Keeps a live-updating tag table + rolling event list from the HMI
   * backend's /ws stream, reconnecting after a short delay if the socket
   * drops (the twin's own tick loop, and this stream, are independent of
   * whether any browser tab is currently connected). */
  function useLiveStream(maxEvents = 200): {
    tags: Record<string, TagPrimitive>;
    events: EventOut[];
    scanCount: number;
    elapsed: number;
    connected: boolean;
  } {
    const [tags, setTags] = useState<Record<string, TagPrimitive>>({});
    const [events, setEvents] = useState<EventOut[]>([]);
    const [scanCount, setScanCount] = useState(0);
    const [elapsed, setElapsed] = useState(0);
    const [connected, setConnected] = useState(false);
    const eventsRef = useRef<EventOut[]>([]);

    useEffect(() => {
      let socket: WebSocket | null = null;
      let reconnectTimer: number | undefined;
      let cancelled = false;

      const connect = () => {
        socket = new WebSocket(`${target.getWsBase()}/ws`);
        socket.onopen = () => setConnected(true);
        socket.onclose = () => {
          setConnected(false);
          if (!cancelled) {
            reconnectTimer = window.setTimeout(connect, 2000);
          }
        };
        socket.onerror = () => socket?.close();
        socket.onmessage = (raw) => {
          const message = JSON.parse(raw.data as string) as StreamMessage;
          setTags(message.tags);
          setScanCount(message.scan_count);
          setElapsed(message.elapsed);
          if (message.events.length > 0) {
            eventsRef.current = [...eventsRef.current, ...message.events].slice(-maxEvents);
            setEvents(eventsRef.current);
          }
        };
      };

      connect();
      return () => {
        cancelled = true;
        window.clearTimeout(reconnectTimer);
        socket?.close();
      };
    }, [maxEvents]);

    return { tags, events, scanCount, elapsed, connected };
  }

  return { getStatus, getTags, getBusSignal, getSeries, getEvents, useLiveStream };
}

export const { getStatus, getTags, getBusSignal, getSeries, getEvents, useLiveStream } =
  createApiClient({ getApiBase, getWsBase });

import { useCallback, useEffect, useRef, useState } from "react";

type HealthResponse = {
  status: "ok";
  service: "realtime-gateway";
  nimClient: "mock" | "real";
};

type CreateSessionResponse = {
  sessionId: string;
  status: "created";
  eventsUrl: string;
};

type StatusEvent = {
  sessionId: string;
  kind: "status";
  state: string;
  receivedAt: number;
};

type TranscriptEvent = {
  sessionId: string;
  kind: "transcript";
  type: "partial" | "final";
  text: string;
  receivedAt: number;
  source: "nim" | "mock";
  stablePartial: boolean;
  latency: {
    firstAudioToThisTranscriptMs: number | null;
    lastChunkSentToThisTranscriptMs: number | null;
    serverReceivedToBrowserSentMs: number | null;
  };
  raw: unknown;
};

type MetricsEvent = {
  sessionId: string;
  kind: "metrics";
  receivedAt: number;
  metrics: Record<string, number | null>;
};

type ErrorEvent = {
  sessionId: string;
  kind: "error";
  message: string;
  receivedAt: number;
  raw: unknown;
};

type GatewayEvent = StatusEvent | TranscriptEvent | MetricsEvent | ErrorEvent;

const apiBase = import.meta.env.VITE_REALTIME_API_BASE ?? "";

function toWebSocketUrl(eventsUrl: string): string {
  const httpBase = apiBase || window.location.origin;
  const url = new URL(eventsUrl, httpBase);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${url}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export function useRealtimeAsrSpike() {
  const [sessionId, setSessionId] = useState("");
  const [nimClient, setNimClient] = useState<"mock" | "real" | "unknown">("unknown");
  const [isStarting, setIsStarting] = useState(false);
  const [webRtcState, setWebRtcState] = useState("idle");
  const [webSocketState, setWebSocketState] = useState("idle");
  const [partialTranscript, setPartialTranscript] = useState("");
  const [finalTranscriptLog, setFinalTranscriptLog] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<Record<string, number | null>>({});
  const [errors, setErrors] = useState<string[]>([]);
  const [lastServerToBrowserEventLatencyMs, setLastServerToBrowserEventLatencyMs] =
    useState<number | null>(null);

  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const activeSessionIdRef = useRef("");

  useEffect(() => {
    let cancelled = false;
    fetchJson<HealthResponse>("/health")
      .then((health) => {
        if (!cancelled) {
          setNimClient(health.nimClient);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setErrors((current) => [...current, `health: ${String(error)}`]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const clearTranscript = useCallback(() => {
    setPartialTranscript("");
    setFinalTranscriptLog([]);
    setErrors([]);
  }, []);

  const stop = useCallback(async () => {
    const sessionToStop = activeSessionIdRef.current;

    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;

    peerConnectionRef.current?.close();
    peerConnectionRef.current = null;
    setWebRtcState("closed");

    websocketRef.current?.close();
    websocketRef.current = null;
    setWebSocketState("closed");

    if (sessionToStop) {
      try {
        await fetchJson(`/api/realtime/sessions/${sessionToStop}/stop`, { method: "POST" });
      } catch (error) {
        setErrors((current) => [...current, `stop: ${String(error)}`]);
      }
    }
    activeSessionIdRef.current = "";
  }, []);

  const start = useCallback(async () => {
    setIsStarting(true);
    setErrors([]);

    try {
      if (activeSessionIdRef.current) {
        await stop();
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const session = await fetchJson<CreateSessionResponse>("/api/realtime/sessions", {
        method: "POST"
      });
      setSessionId(session.sessionId);
      activeSessionIdRef.current = session.sessionId;

      const websocket = new WebSocket(toWebSocketUrl(session.eventsUrl));
      websocketRef.current = websocket;
      setWebSocketState("connecting");
      websocket.onopen = () => setWebSocketState("open");
      websocket.onclose = () => setWebSocketState("closed");
      websocket.onerror = () => {
        setWebSocketState("error");
        setErrors((current) => [...current, "websocket error"]);
      };
      websocket.onmessage = (message) => {
        const browserReceivedAt = Date.now();
        const event = JSON.parse(message.data) as GatewayEvent;
        setLastServerToBrowserEventLatencyMs(browserReceivedAt - event.receivedAt);

        if (event.kind === "status") {
          if (event.state.startsWith("webrtc_")) {
            setWebRtcState(event.state.replace("webrtc_", ""));
          }
          return;
        }
        if (event.kind === "metrics") {
          setMetrics(event.metrics);
          return;
        }
        if (event.kind === "transcript") {
          if (event.type === "partial") {
            setPartialTranscript(event.text);
          } else {
            setFinalTranscriptLog((current) => [...current, event.text]);
            setPartialTranscript("");
          }
          setMetrics((current) => ({
            ...current,
            firstPartialLatencyMs: event.latency.firstAudioToThisTranscriptMs,
            latestPartialLatencyMs: event.latency.lastChunkSentToThisTranscriptMs
          }));
          return;
        }
        if (event.kind === "error") {
          setErrors((current) => [...current, `${event.message}: ${JSON.stringify(event.raw)}`]);
        }
      };

      const peerConnection = new RTCPeerConnection();
      peerConnectionRef.current = peerConnection;
      peerConnection.onconnectionstatechange = () => {
        setWebRtcState(peerConnection.connectionState);
      };
      stream.getAudioTracks().forEach((track) => peerConnection.addTrack(track, stream));

      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);
      const answer = await fetchJson<RTCSessionDescriptionInit>(
        `/api/realtime/sessions/${session.sessionId}/offer`,
        {
          method: "POST",
          body: JSON.stringify({
            type: peerConnection.localDescription?.type,
            sdp: peerConnection.localDescription?.sdp
          })
        }
      );
      await peerConnection.setRemoteDescription(answer);
    } catch (error) {
      setErrors((current) => [...current, `start: ${String(error)}`]);
      await stop();
    } finally {
      setIsStarting(false);
    }
  }, [stop]);

  useEffect(() => {
    return () => {
      void stop();
    };
  }, [stop]);

  return {
    clearTranscript,
    errors,
    finalTranscriptLog,
    isStarting,
    lastServerToBrowserEventLatencyMs,
    metrics,
    nimClient,
    partialTranscript,
    sessionId,
    start,
    stop,
    webRtcState,
    webSocketState
  };
}

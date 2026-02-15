import { useEffect, useRef, useState, useCallback } from 'react';
import type { ExecutionLog, ExecutionMetrics } from '@/types';
import type {
  ExecutionStatusMessage,
  ExecutionLogMessage,
  ExecutionMetricsMessage,
} from '@/types/websocket';

// =============================================================================
// SSE Hook — Consumes /executions/{id}/stream endpoint
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Reconnect settings
const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
const RECONNECT_MULTIPLIER = 2;

export type SSEStatus = 'connecting' | 'connected' | 'disconnected' | 'failed';

export interface SSEState {
  status: SSEStatus;
  logs: ExecutionLog[];
  metrics: ExecutionMetrics | null;
  executionStatus: string | null;
  progress: number;
  error: string | null;
  isConnected: boolean;
}

/**
 * Hook for consuming SSE execution stream.
 *
 * Connects to /executions/{executionId}/stream and parses
 * snapshot, status, log, metrics, and done events.
 *
 * Auto-reconnects with exponential backoff (1s -> 30s).
 * Use as a fallback when WebSocket is unavailable.
 */
export function useSSE(executionId: string | null): SSEState {
  const [status, setStatus] = useState<SSEStatus>('disconnected');
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [metrics, setMetrics] = useState<ExecutionMetrics | null>(null);
  const [executionStatus, setExecutionStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!isMountedRef.current) return;

    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(RECONNECT_MULTIPLIER, reconnectAttemptRef.current),
      MAX_RECONNECT_DELAY,
    );

    reconnectTimeoutRef.current = setTimeout(() => {
      if (isMountedRef.current) {
        reconnectAttemptRef.current++;
        // Re-trigger by resetting status — the effect will reconnect
        setStatus('connecting');
      }
    }, delay);
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    if (!executionId) {
      cleanup();
      setStatus('disconnected');
      return;
    }

    const token = localStorage.getItem('gorgon_token');
    const url = `${API_BASE_URL}/executions/${executionId}/stream`;

    cleanup();
    setStatus('connecting');
    setError(null);

    const es = new EventSource(
      token ? `${url}?token=${encodeURIComponent(token)}` : url,
    );
    eventSourceRef.current = es;

    es.onopen = () => {
      if (!isMountedRef.current) return;
      reconnectAttemptRef.current = 0;
      setStatus('connected');
      setError(null);
    };

    es.onerror = () => {
      if (!isMountedRef.current) return;
      es.close();
      eventSourceRef.current = null;
      setStatus('failed');
      setError('SSE connection lost');
      scheduleReconnect();
    };

    // Parse snapshot event (initial state)
    es.addEventListener('snapshot', (e: MessageEvent) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(e.data);
        setExecutionStatus(data.status ?? null);
        setProgress(data.progress ?? 0);

        // Parse logs from snapshot
        if (Array.isArray(data.logs)) {
          const parsedLogs: ExecutionLog[] = data.logs.map((log: Record<string, unknown>) => ({
            timestamp: (log.timestamp as string) ?? new Date().toISOString(),
            level: ((log.level as string) === 'warning' ? 'warn' : log.level) as ExecutionLog['level'],
            message: log.message as string,
            metadata: (log.metadata as Record<string, unknown>) ?? undefined,
          }));
          setLogs(parsedLogs);
        }

        // Parse metrics from snapshot
        if (data.metrics) {
          setMetrics({
            totalTokens: data.metrics.total_tokens ?? 0,
            totalCost: (data.metrics.total_cost_cents ?? 0) / 100,
            duration: data.metrics.duration_ms ?? 0,
            stepMetrics: [],
          });
        }
      } catch {
        console.error('Failed to parse SSE snapshot');
      }
    });

    // Parse status event
    es.addEventListener('status', (e: MessageEvent) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as Omit<ExecutionStatusMessage, 'type' | 'execution_id'>;
        setExecutionStatus(data.status ?? null);
        setProgress(data.progress ?? 0);
        if (data.error) {
          setError(data.error);
        }
      } catch {
        console.error('Failed to parse SSE status event');
      }
    });

    // Parse log event
    es.addEventListener('log', (e: MessageEvent) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as Omit<ExecutionLogMessage, 'type' | 'execution_id'>['log'];
        const level = data.level === 'warning' ? 'warn' : data.level;
        const log: ExecutionLog = {
          timestamp: data.timestamp ?? new Date().toISOString(),
          level: level as ExecutionLog['level'],
          message: data.message,
          metadata: data.metadata ?? undefined,
        };
        setLogs((prev) => [...prev, log].slice(-100));
      } catch {
        console.error('Failed to parse SSE log event');
      }
    });

    // Parse metrics event
    es.addEventListener('metrics', (e: MessageEvent) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(e.data) as Omit<ExecutionMetricsMessage, 'type' | 'execution_id'>['metrics'];
        setMetrics({
          totalTokens: data.total_tokens,
          totalCost: data.total_cost_cents / 100,
          duration: data.duration_ms,
          stepMetrics: [],
        });
      } catch {
        console.error('Failed to parse SSE metrics event');
      }
    });

    // Done event — execution finished
    es.addEventListener('done', () => {
      if (!isMountedRef.current) return;
      es.close();
      eventSourceRef.current = null;
      setStatus('disconnected');
    });

    return () => {
      isMountedRef.current = false;
      cleanup();
    };
  }, [executionId, cleanup, scheduleReconnect]);

  return {
    status,
    logs,
    metrics,
    executionStatus,
    progress,
    error,
    isConnected: status === 'connected',
  };
}

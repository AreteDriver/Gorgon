import { useEffect, useRef, useCallback, useState } from 'react';
import { getWebSocket, type WebSocketEventHandlers } from '@/lib/websocket';
import { useLiveExecutionStore } from '@/stores';
import type { ConnectionState, ExecutionStatusMessage, ExecutionLogMessage, ExecutionMetricsMessage } from '@/types/websocket';
import type { Execution, ExecutionLog, ExecutionMetrics } from '@/types';

/**
 * Hook for WebSocket connection and real-time execution updates.
 *
 * Automatically connects on mount and disconnects on unmount.
 * Updates the LiveExecutionStore with real-time data.
 */
export function useWebSocket() {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const subscriptionsRef = useRef<Set<string>>(new Set());

  const { setExecution, executions } = useLiveExecutionStore();

  // Handler for execution status updates
  const handleExecutionStatus = useCallback((message: ExecutionStatusMessage) => {
    const existing = executions.get(message.execution_id);
    if (!existing) return;

    // Update the execution in the store
    const updated: Execution = {
      ...existing,
      status: message.status as Execution['status'],
      progress: message.progress,
      currentStep: message.current_step ?? existing.currentStep,
      startedAt: message.started_at ?? existing.startedAt,
      completedAt: message.completed_at ?? existing.completedAt,
    };

    setExecution(updated);
  }, [executions, setExecution]);

  // Handler for execution log updates
  const handleExecutionLog = useCallback((message: ExecutionLogMessage) => {
    const existing = executions.get(message.execution_id);
    if (!existing) return;

    // Create log entry (map 'warning' -> 'warn' for frontend compatibility)
    const level = message.log.level === 'warning' ? 'warn' : message.log.level;
    const log: ExecutionLog = {
      timestamp: message.log.timestamp ?? new Date().toISOString(),
      level: level as 'info' | 'warn' | 'error' | 'debug',
      message: message.log.message,
      metadata: message.log.metadata ?? undefined,
    };

    // Append to logs (limit to last 100)
    const logs = [...existing.logs, log].slice(-100);

    setExecution({ ...existing, logs });
  }, [executions, setExecution]);

  // Handler for execution metrics updates
  const handleExecutionMetrics = useCallback((message: ExecutionMetricsMessage) => {
    const existing = executions.get(message.execution_id);
    if (!existing) return;

    // Update metrics
    const metrics: ExecutionMetrics = {
      totalTokens: message.metrics.total_tokens,
      totalCost: message.metrics.total_cost_cents / 100, // Convert cents to dollars
      duration: message.metrics.duration_ms,
      stepMetrics: existing.metrics?.stepMetrics ?? [],
    };

    setExecution({ ...existing, metrics });
  }, [executions, setExecution]);

  // Initialize WebSocket on mount
  useEffect(() => {
    const handlers: WebSocketEventHandlers = {
      onConnectionChange: (state) => {
        setConnectionState(state);
        if (state === 'connected') {
          const ws = getWebSocket();
          setConnectionId(ws.getConnectionId());
        } else if (state === 'disconnected') {
          setConnectionId(null);
        }
      },
      onExecutionStatus: handleExecutionStatus,
      onExecutionLog: handleExecutionLog,
      onExecutionMetrics: handleExecutionMetrics,
      onError: (error) => {
        console.error('WebSocket error:', error);
      },
    };

    const ws = getWebSocket(handlers);
    ws.connect();

    return () => {
      // Don't disconnect on unmount - keep connection alive
      // The connection is managed by the singleton
    };
  }, [handleExecutionStatus, handleExecutionLog, handleExecutionMetrics]);

  // Subscribe to execution updates
  const subscribe = useCallback((executionIds: string[]) => {
    const ws = getWebSocket();

    // Track locally
    for (const id of executionIds) {
      subscriptionsRef.current.add(id);
    }

    ws.subscribe(executionIds);
  }, []);

  // Unsubscribe from execution updates
  const unsubscribe = useCallback((executionIds: string[]) => {
    const ws = getWebSocket();

    // Remove from local tracking
    for (const id of executionIds) {
      subscriptionsRef.current.delete(id);
    }

    ws.unsubscribe(executionIds);
  }, []);

  // Get current subscriptions
  const getSubscriptions = useCallback((): string[] => {
    return Array.from(subscriptionsRef.current);
  }, []);

  return {
    connectionState,
    connectionId,
    isConnected: connectionState === 'connected',
    subscribe,
    unsubscribe,
    getSubscriptions,
  };
}

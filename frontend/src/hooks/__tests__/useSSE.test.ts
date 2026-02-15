import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useSSE } from '../useSSE';

// =============================================================================
// Mock EventSource
// =============================================================================

class MockEventSource {
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Map<string, ((e: MessageEvent) => void)[]> = new Map();
  readyState = 0; // CONNECTING

  constructor(url: string) {
    this.url = url;
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type)!.push(handler);
  }

  removeEventListener(type: string, handler: (e: MessageEvent) => void) {
    const handlers = this.listeners.get(type);
    if (handlers) {
      const idx = handlers.indexOf(handler);
      if (idx >= 0) handlers.splice(idx, 1);
    }
  }

  close() {
    this.readyState = 2; // CLOSED
  }

  // Test helpers
  simulateOpen() {
    this.readyState = 1; // OPEN
    this.onopen?.();
  }

  simulateEvent(type: string, data: unknown) {
    const handlers = this.listeners.get(type) || [];
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    for (const handler of handlers) {
      handler(event);
    }
  }

  simulateError() {
    this.onerror?.();
  }
}

let mockES: MockEventSource | null = null;

beforeEach(() => {
  mockES = null;
  vi.stubGlobal('EventSource', class extends MockEventSource {
    constructor(url: string) {
      super(url);
      mockES = this;
    }
  });
  localStorage.setItem('gorgon_token', 'test-token');
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  vi.clearAllTimers();
});

// =============================================================================
// Tests
// =============================================================================

describe('useSSE', () => {
  it('connects to correct URL with token', () => {
    renderHook(() => useSSE('exec-123'));
    expect(mockES).not.toBeNull();
    expect(mockES!.url).toContain('/executions/exec-123/stream');
    expect(mockES!.url).toContain('token=test-token');
  });

  it('returns disconnected when executionId is null', () => {
    const { result } = renderHook(() => useSSE(null));
    expect(result.current.status).toBe('disconnected');
    expect(result.current.isConnected).toBe(false);
    expect(mockES).toBeNull();
  });

  it('parses snapshot event', () => {
    const { result } = renderHook(() => useSSE('exec-123'));

    act(() => {
      mockES!.simulateOpen();
    });
    expect(result.current.status).toBe('connected');
    expect(result.current.isConnected).toBe(true);

    act(() => {
      mockES!.simulateEvent('snapshot', {
        status: 'running',
        progress: 42,
        logs: [
          { level: 'info', message: 'Step started', timestamp: '2025-01-01T00:00:00Z' },
        ],
        metrics: {
          total_tokens: 500,
          total_cost_cents: 10,
          duration_ms: 3000,
        },
      });
    });

    expect(result.current.executionStatus).toBe('running');
    expect(result.current.progress).toBe(42);
    expect(result.current.logs).toHaveLength(1);
    expect(result.current.logs[0].message).toBe('Step started');
    expect(result.current.metrics?.totalTokens).toBe(500);
    expect(result.current.metrics?.totalCost).toBe(0.1); // cents -> dollars
  });

  it('handles done event and closes', () => {
    const { result } = renderHook(() => useSSE('exec-123'));

    act(() => {
      mockES!.simulateOpen();
    });

    act(() => {
      mockES!.simulateEvent('done', {});
    });

    expect(result.current.status).toBe('disconnected');
    expect(mockES!.readyState).toBe(2); // CLOSED
  });

  it('cleans up on unmount', () => {
    const { unmount } = renderHook(() => useSSE('exec-123'));

    act(() => {
      mockES!.simulateOpen();
    });

    const es = mockES!;
    unmount();
    expect(es.readyState).toBe(2); // CLOSED
  });
});

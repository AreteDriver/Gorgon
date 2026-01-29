import type {
  ClientMessage,
  ServerMessage,
  ConnectionState,
  ExecutionStatusMessage,
  ExecutionLogMessage,
  ExecutionMetricsMessage,
} from '@/types/websocket';

// =============================================================================
// WebSocket Client Configuration
// =============================================================================

const WS_BASE_URL = import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

// Reconnection settings
const INITIAL_RECONNECT_DELAY = 1000; // 1 second
const MAX_RECONNECT_DELAY = 30000; // 30 seconds
const RECONNECT_MULTIPLIER = 2;

// Ping interval
const PING_INTERVAL = 30000; // 30 seconds

// =============================================================================
// Event Types
// =============================================================================

export type WebSocketEventHandlers = {
  onConnectionChange?: (state: ConnectionState) => void;
  onExecutionStatus?: (message: ExecutionStatusMessage) => void;
  onExecutionLog?: (message: ExecutionLogMessage) => void;
  onExecutionMetrics?: (message: ExecutionMetricsMessage) => void;
  onError?: (error: string) => void;
};

// =============================================================================
// WebSocket Client
// =============================================================================

export class GorgonWebSocket {
  private ws: WebSocket | null = null;
  private connectionState: ConnectionState = 'disconnected';
  private connectionId: string | null = null;
  private subscriptions: Set<string> = new Set();
  private reconnectAttempt = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private handlers: WebSocketEventHandlers = {};

  constructor(handlers?: WebSocketEventHandlers) {
    if (handlers) {
      this.handlers = handlers;
    }
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /**
   * Connect to the WebSocket server.
   */
  connect(): void {
    if (this.ws && this.connectionState !== 'disconnected') {
      return;
    }

    const token = localStorage.getItem('gorgon_token');
    if (!token) {
      this.setConnectionState('disconnected');
      this.handlers.onError?.('No authentication token');
      return;
    }

    this.setConnectionState('connecting');

    const url = `${WS_BASE_URL}/ws/executions?token=${encodeURIComponent(token)}`;

    try {
      this.ws = new WebSocket(url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from the WebSocket server.
   */
  disconnect(): void {
    this.clearReconnect();
    this.clearPing();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.subscriptions.clear();
    this.setConnectionState('disconnected');
  }

  /**
   * Subscribe to execution updates.
   */
  subscribe(executionIds: string[]): void {
    if (!executionIds.length) return;

    // Track subscriptions
    for (const id of executionIds) {
      this.subscriptions.add(id);
    }

    // Send subscribe message if connected
    if (this.isConnected()) {
      this.send({ type: 'subscribe', execution_ids: executionIds });
    }
  }

  /**
   * Unsubscribe from execution updates.
   */
  unsubscribe(executionIds: string[]): void {
    if (!executionIds.length) return;

    // Remove from subscriptions
    for (const id of executionIds) {
      this.subscriptions.delete(id);
    }

    // Send unsubscribe message if connected
    if (this.isConnected()) {
      this.send({ type: 'unsubscribe', execution_ids: executionIds });
    }
  }

  /**
   * Check if connected.
   */
  isConnected(): boolean {
    return this.connectionState === 'connected' && this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get current connection state.
   */
  getState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Get current subscriptions.
   */
  getSubscriptions(): string[] {
    return Array.from(this.subscriptions);
  }

  /**
   * Get connection ID.
   */
  getConnectionId(): string | null {
    return this.connectionId;
  }

  /**
   * Update event handlers.
   */
  setHandlers(handlers: WebSocketEventHandlers): void {
    this.handlers = { ...this.handlers, ...handlers };
  }

  // ---------------------------------------------------------------------------
  // Internal Methods
  // ---------------------------------------------------------------------------

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempt = 0;
      this.setConnectionState('connected');
      this.startPing();

      // Resubscribe to previous subscriptions
      if (this.subscriptions.size > 0) {
        this.send({
          type: 'subscribe',
          execution_ids: Array.from(this.subscriptions)
        });
      }
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      this.clearPing();

      if (event.code !== 1000) {
        // Abnormal close - attempt reconnect
        this.scheduleReconnect();
      } else {
        this.setConnectionState('disconnected');
      }
    };

    this.ws.onerror = (event) => {
      console.error('WebSocket error:', event);
      this.handlers.onError?.('WebSocket connection error');
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as ServerMessage;
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
  }

  private handleMessage(message: ServerMessage): void {
    switch (message.type) {
      case 'connected':
        this.connectionId = message.connection_id;
        break;

      case 'execution_status':
        this.handlers.onExecutionStatus?.(message);
        break;

      case 'execution_log':
        this.handlers.onExecutionLog?.(message);
        break;

      case 'execution_metrics':
        this.handlers.onExecutionMetrics?.(message);
        break;

      case 'pong':
        // Pong received - connection is alive
        break;

      case 'error':
        console.error('WebSocket server error:', message.code, message.message);
        this.handlers.onError?.(message.message);
        break;
    }
  }

  private send(message: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.handlers.onConnectionChange?.(state);
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnect();
    this.setConnectionState('reconnecting');

    // Calculate delay with exponential backoff
    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(RECONNECT_MULTIPLIER, this.reconnectAttempt),
      MAX_RECONNECT_DELAY
    );

    console.log(`WebSocket reconnecting in ${delay}ms (attempt ${this.reconnectAttempt + 1})`);

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectAttempt++;
      this.connect();
    }, delay);
  }

  private clearReconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  private startPing(): void {
    this.clearPing();
    this.pingInterval = setInterval(() => {
      this.send({ type: 'ping', timestamp: Date.now() });
    }, PING_INTERVAL);
  }

  private clearPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

// =============================================================================
// Singleton Instance
// =============================================================================

let instance: GorgonWebSocket | null = null;

/**
 * Get or create the singleton WebSocket instance.
 */
export function getWebSocket(handlers?: WebSocketEventHandlers): GorgonWebSocket {
  if (!instance) {
    instance = new GorgonWebSocket(handlers);
  } else if (handlers) {
    instance.setHandlers(handlers);
  }
  return instance;
}

/**
 * Destroy the singleton instance.
 */
export function destroyWebSocket(): void {
  if (instance) {
    instance.disconnect();
    instance = null;
  }
}

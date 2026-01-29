// =============================================================================
// WebSocket Message Types
// =============================================================================

// Message type enum
export type MessageType =
  | 'subscribe'
  | 'unsubscribe'
  | 'ping'
  | 'connected'
  | 'execution_status'
  | 'execution_log'
  | 'execution_metrics'
  | 'pong'
  | 'error';

// -----------------------------------------------------------------------------
// Client -> Server Messages
// -----------------------------------------------------------------------------

export interface SubscribeMessage {
  type: 'subscribe';
  execution_ids: string[];
}

export interface UnsubscribeMessage {
  type: 'unsubscribe';
  execution_ids: string[];
}

export interface PingMessage {
  type: 'ping';
  timestamp: number;
}

export type ClientMessage = SubscribeMessage | UnsubscribeMessage | PingMessage;

// -----------------------------------------------------------------------------
// Server -> Client Messages
// -----------------------------------------------------------------------------

export interface ConnectedMessage {
  type: 'connected';
  connection_id: string;
  server_time: string;
}

export interface ExecutionStatusMessage {
  type: 'execution_status';
  execution_id: string;
  status: string;
  progress: number;
  current_step?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
}

export interface ExecutionLogEntry {
  level: 'debug' | 'info' | 'warning' | 'error';
  message: string;
  step_id?: string | null;
  timestamp?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface ExecutionLogMessage {
  type: 'execution_log';
  execution_id: string;
  log: ExecutionLogEntry;
}

export interface ExecutionMetricsData {
  total_tokens: number;
  total_cost_cents: number;
  duration_ms: number;
  steps_completed: number;
  steps_failed: number;
}

export interface ExecutionMetricsMessage {
  type: 'execution_metrics';
  execution_id: string;
  metrics: ExecutionMetricsData;
}

export interface PongMessage {
  type: 'pong';
  timestamp: number;
}

export interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export type ServerMessage =
  | ConnectedMessage
  | ExecutionStatusMessage
  | ExecutionLogMessage
  | ExecutionMetricsMessage
  | PongMessage
  | ErrorMessage;

// -----------------------------------------------------------------------------
// WebSocket State
// -----------------------------------------------------------------------------

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export interface WebSocketState {
  connectionState: ConnectionState;
  connectionId: string | null;
  subscriptions: Set<string>;
  reconnectAttempt: number;
  lastError: string | null;
}

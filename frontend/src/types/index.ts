// =============================================================================
// Gorgon API Types
// These types mirror the FastAPI backend models
// =============================================================================

// -----------------------------------------------------------------------------
// Agent Types
// -----------------------------------------------------------------------------

export type AgentRole = 
  | 'planner'
  | 'builder'
  | 'tester'
  | 'reviewer'
  | 'architect'
  | 'documenter'
  | 'analyst'
  | 'visualizer'
  | 'reporter';

export type AgentProvider = 'openai' | 'anthropic';

export interface Agent {
  id: string;
  role: AgentRole;
  provider: AgentProvider;
  model: string;
  status: AgentStatus;
  config: AgentConfig;
}

export interface AgentConfig {
  temperature: number;
  maxTokens: number;
  systemPrompt?: string;
}

export type AgentStatus = 'idle' | 'running' | 'completed' | 'failed';

// -----------------------------------------------------------------------------
// Workflow Types
// -----------------------------------------------------------------------------

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  steps: WorkflowStep[];
  status: WorkflowStatus;
  createdAt: string;
  updatedAt: string;
  checkpointId?: string;
}

export interface WorkflowStep {
  id: string;
  name: string;
  agentRole: AgentRole;
  inputs: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  status: StepStatus;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  tokenUsage?: TokenUsage;
}

export type WorkflowStatus = 
  | 'draft'
  | 'pending'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed';

export type StepStatus = 
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped';

// -----------------------------------------------------------------------------
// Execution Types
// -----------------------------------------------------------------------------

export interface Execution {
  id: string;
  workflowId: string;
  workflowName: string;
  status: WorkflowStatus;
  startedAt: string;
  completedAt?: string;
  currentStep?: string;
  progress: number;
  logs: ExecutionLog[];
  metrics: ExecutionMetrics;
  checkpointId?: string;
}

export interface ExecutionLog {
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  agent?: AgentRole;
  message: string;
  metadata?: Record<string, unknown>;
}

export interface ExecutionMetrics {
  totalTokens: number;
  totalCost: number;
  duration: number;
  stepMetrics: StepMetrics[];
}

export interface StepMetrics {
  stepId: string;
  stepName: string;
  agentRole: AgentRole;
  tokenUsage: TokenUsage;
  duration: number;
  cost: number;
}

// -----------------------------------------------------------------------------
// Budget & Token Types
// -----------------------------------------------------------------------------

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  cost: number;
}

export interface Budget {
  id: string;
  name: string;
  limit: number;
  used: number;
  remaining: number;
  period: 'daily' | 'weekly' | 'monthly';
  resetAt: string;
  alerts: BudgetAlert[];
}

export interface BudgetAlert {
  threshold: number;
  triggered: boolean;
  triggeredAt?: string;
}

export interface BudgetSummary {
  totalBudget: number;
  totalUsed: number;
  totalRemaining: number;
  usageByAgent: Record<AgentRole, number>;
  usageByWorkflow: Record<string, number>;
  dailyUsage: DailyUsage[];
}

export interface DailyUsage {
  date: string;
  tokens: number;
  cost: number;
}

// -----------------------------------------------------------------------------
// Checkpoint Types
// -----------------------------------------------------------------------------

export interface Checkpoint {
  id: string;
  executionId: string;
  workflowId: string;
  stepId: string;
  state: Record<string, unknown>;
  createdAt: string;
  metadata?: Record<string, unknown>;
}

// -----------------------------------------------------------------------------
// API Response Types
// -----------------------------------------------------------------------------

export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// -----------------------------------------------------------------------------
// Dashboard Types
// -----------------------------------------------------------------------------

export interface DashboardStats {
  totalWorkflows: number;
  activeExecutions: number;
  completedToday: number;
  failedToday: number;
  totalTokensToday: number;
  totalCostToday: number;
}

export interface RecentExecution {
  id: string;
  name: string;
  status: string;
  time: string;
}

export interface DailyUsageData {
  date: string;
  tokens: number;
  cost: number;
}

export interface AgentUsageData {
  agent: string;
  tokens: number;
}

export interface BudgetStatusItem {
  agent: string;
  used: number;
  limit: number;
}

export interface DashboardBudget {
  totalBudget: number;
  totalUsed: number;
  percentUsed: number;
  byAgent: BudgetStatusItem[];
  alert?: string;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  apiLatency: number;
  activeConnections: number;
  uptime: number;
  services: ServiceHealth[];
}

export interface ServiceHealth {
  name: string;
  status: 'up' | 'down';
  latency?: number;
  lastCheck: string;
}

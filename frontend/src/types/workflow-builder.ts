// =============================================================================
// Workflow Builder Types
// Types for the visual workflow builder using ReactFlow
// =============================================================================

import type { AgentRole } from './index';

// -----------------------------------------------------------------------------
// Node Data Types
// ReactFlow requires data to extend Record<string, unknown>
// -----------------------------------------------------------------------------

export interface AgentNodeData extends Record<string, unknown> {
  type: 'agent';
  role: AgentRole;
  name: string;
  prompt?: string;
  outputs?: string[];
  onFailure?: 'stop' | 'continue' | 'retry';
  maxRetries?: number;
}

export interface ShellNodeData extends Record<string, unknown> {
  type: 'shell';
  name: string;
  command: string;
  allowFailure?: boolean;
  timeout?: number;
}

export interface CheckpointNodeData extends Record<string, unknown> {
  type: 'checkpoint';
  name: string;
  message?: string;
}

export interface ParallelNodeData extends Record<string, unknown> {
  type: 'parallel';
  name: string;
  strategy?: 'threading' | 'asyncio' | 'process';
  maxWorkers?: number;
  failFast?: boolean;
}

export interface FanOutNodeData extends Record<string, unknown> {
  type: 'fan_out';
  name: string;
  itemsVariable?: string;  // Variable containing the list to iterate
  maxConcurrent?: number;
  failFast?: boolean;
}

export interface FanInNodeData extends Record<string, unknown> {
  type: 'fan_in';
  name: string;
  inputVariable?: string;  // Variable containing results to aggregate
  aggregation?: 'concat' | 'claude_code';  // How to combine results
  aggregatePrompt?: string;  // Prompt for AI aggregation
}

export interface MapReduceNodeData extends Record<string, unknown> {
  type: 'map_reduce';
  name: string;
  itemsVariable?: string;
  maxConcurrent?: number;
  failFast?: boolean;
  mapPrompt?: string;
  reducePrompt?: string;
}

export type WorkflowNodeData =
  | AgentNodeData
  | ShellNodeData
  | CheckpointNodeData
  | ParallelNodeData
  | FanOutNodeData
  | FanInNodeData
  | MapReduceNodeData;

// -----------------------------------------------------------------------------
// Node Type Guards
// -----------------------------------------------------------------------------

export function isAgentNode(data: WorkflowNodeData): data is AgentNodeData {
  return data.type === 'agent';
}

export function isShellNode(data: WorkflowNodeData): data is ShellNodeData {
  return data.type === 'shell';
}

export function isCheckpointNode(data: WorkflowNodeData): data is CheckpointNodeData {
  return data.type === 'checkpoint';
}

export function isParallelNode(data: WorkflowNodeData): data is ParallelNodeData {
  return data.type === 'parallel';
}

export function isFanOutNode(data: WorkflowNodeData): data is FanOutNodeData {
  return data.type === 'fan_out';
}

export function isFanInNode(data: WorkflowNodeData): data is FanInNodeData {
  return data.type === 'fan_in';
}

export function isMapReduceNode(data: WorkflowNodeData): data is MapReduceNodeData {
  return data.type === 'map_reduce';
}

// -----------------------------------------------------------------------------
// Validation Types
// -----------------------------------------------------------------------------

export interface ValidationError {
  nodeId?: string;
  field?: string;
  message: string;
  severity: 'error' | 'warning';
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
}

// -----------------------------------------------------------------------------
// Builder State Types
// -----------------------------------------------------------------------------

export interface WorkflowBuilderViewport {
  x: number;
  y: number;
  zoom: number;
}

// -----------------------------------------------------------------------------
// Agent Role Metadata
// -----------------------------------------------------------------------------

export interface AgentRoleInfo {
  role: AgentRole;
  label: string;
  description: string;
  color: string;
  icon: string;
}

export const AGENT_ROLES: AgentRoleInfo[] = [
  { role: 'planner', label: 'Planner', description: 'Breaks features into actionable steps', color: '#3b82f6', icon: 'clipboard-list' },
  { role: 'builder', label: 'Builder', description: 'Writes production-ready code', color: '#22c55e', icon: 'hammer' },
  { role: 'tester', label: 'Tester', description: 'Creates comprehensive test suites', color: '#eab308', icon: 'flask-conical' },
  { role: 'reviewer', label: 'Reviewer', description: 'Identifies bugs and security issues', color: '#ef4444', icon: 'search' },
  { role: 'architect', label: 'Architect', description: 'Makes architectural decisions', color: '#8b5cf6', icon: 'building-2' },
  { role: 'documenter', label: 'Documenter', description: 'Creates API docs and guides', color: '#06b6d4', icon: 'file-text' },
  { role: 'analyst', label: 'Analyst', description: 'Statistical analysis and patterns', color: '#f97316', icon: 'bar-chart-2' },
  { role: 'visualizer', label: 'Visualizer', description: 'Creates charts and dashboards', color: '#ec4899', icon: 'pie-chart' },
  { role: 'reporter', label: 'Reporter', description: 'Creates executive summaries', color: '#64748b', icon: 'file-bar-chart' },
];

export const getAgentRoleInfo = (role: AgentRole): AgentRoleInfo => {
  return AGENT_ROLES.find(r => r.role === role) ?? AGENT_ROLES[0];
};

// -----------------------------------------------------------------------------
// Node Creation Helpers
// -----------------------------------------------------------------------------

export const createAgentNodeData = (role: AgentRole): AgentNodeData => ({
  type: 'agent',
  role,
  name: getAgentRoleInfo(role).label,
  onFailure: 'stop',
});

export const createShellNodeData = (): ShellNodeData => ({
  type: 'shell',
  name: 'Shell Command',
  command: '',
  allowFailure: false,
});

export const createCheckpointNodeData = (): CheckpointNodeData => ({
  type: 'checkpoint',
  name: 'Checkpoint',
  message: 'Workflow paused at checkpoint',
});

export const createParallelNodeData = (): ParallelNodeData => ({
  type: 'parallel',
  name: 'Parallel Group',
  strategy: 'threading',
  maxWorkers: 4,
  failFast: false,
});

export const createFanOutNodeData = (): FanOutNodeData => ({
  type: 'fan_out',
  name: 'Fan Out',
  itemsVariable: 'items',
  maxConcurrent: 5,
  failFast: false,
});

export const createFanInNodeData = (): FanInNodeData => ({
  type: 'fan_in',
  name: 'Fan In',
  inputVariable: 'results',
  aggregation: 'concat',
});

export const createMapReduceNodeData = (): MapReduceNodeData => ({
  type: 'map_reduce',
  name: 'Map-Reduce',
  itemsVariable: 'items',
  maxConcurrent: 3,
  failFast: false,
});

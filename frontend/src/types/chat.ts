// =============================================================================
// Chat Types for Gorgon Desktop
// =============================================================================

export type ChatMode = 'assistant' | 'self_improve';

export type MessageRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  agent?: string;
  job_id?: string;
  token_count?: number;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface ChatSession {
  id: string;
  title: string;
  project_path?: string;
  mode: ChatMode;
  status: 'active' | 'archived';
  created_at: string;
  updated_at: string;
  message_count: number;
  filesystem_enabled?: boolean;
  pending_proposals?: number;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface CreateSessionRequest {
  title?: string;
  project_path?: string;
  mode?: ChatMode;
  filesystem_enabled?: boolean;
  allowed_paths?: string[];
}

export type ProposalStatus = 'pending' | 'approved' | 'rejected' | 'applied' | 'failed';

export interface EditProposal {
  id: string;
  session_id: string;
  file_path: string;
  old_content?: string;
  new_content: string;
  description: string;
  status: ProposalStatus;
  created_at: string;
  applied_at?: string;
  error_message?: string;
}

export interface SendMessageRequest {
  content: string;
}

export interface StreamChunk {
  type: 'text' | 'agent' | 'job' | 'done' | 'error' | 'tool_result';
  content?: string;
  agent?: string;
  job_id?: string;
  error?: string;
}

export interface ToolResult {
  tool: string;
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

// Agent role display info
export const AGENT_DISPLAY: Record<string, { name: string; color: string; icon: string }> = {
  supervisor: { name: 'Supervisor', color: 'bg-purple-500', icon: '🎯' },
  planner: { name: 'Planner', color: 'bg-blue-500', icon: '📋' },
  builder: { name: 'Builder', color: 'bg-green-500', icon: '🔨' },
  tester: { name: 'Tester', color: 'bg-yellow-500', icon: '🧪' },
  reviewer: { name: 'Reviewer', color: 'bg-orange-500', icon: '🔍' },
  architect: { name: 'Architect', color: 'bg-indigo-500', icon: '🏗️' },
  documenter: { name: 'Documenter', color: 'bg-pink-500', icon: '📝' },
  analyst: { name: 'Analyst', color: 'bg-cyan-500', icon: '📊' },
  system: { name: 'System', color: 'bg-gray-500', icon: '⚙️' },
};

export function getAgentDisplay(agent: string | undefined) {
  if (!agent) return undefined;
  return AGENT_DISPLAY[agent] || { name: agent, color: 'bg-gray-500', icon: '🤖' };
}

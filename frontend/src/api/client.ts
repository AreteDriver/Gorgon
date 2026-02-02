import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  PaginatedResponse,
  Workflow,
  Execution,
  Agent,
  AgentDefinition,
  Budget,
  BudgetSummary,
  Checkpoint,
  DashboardStats,
  SystemHealth,
  RecentExecution,
  DailyUsageData,
  AgentUsageData,
  DashboardBudget,
} from '@/types';
import type {
  MCPServer,
  MCPServerCreateInput,
  MCPTool,
  Credential,
} from '@/types/mcp';
import type {
  ChatSession,
  ChatSessionDetail,
  ChatMode,
} from '@/types/chat';

// =============================================================================
// API Client Configuration
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

class GorgonApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for auth
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('gorgon_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('gorgon_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // ---------------------------------------------------------------------------
  // Workflows
  // ---------------------------------------------------------------------------

  async getWorkflows(page = 1, pageSize = 20): Promise<PaginatedResponse<Workflow>> {
    const { data } = await this.client.get('/workflows', {
      params: { page, page_size: pageSize },
    });
    return data;
  }

  async getWorkflow(id: string): Promise<Workflow> {
    const { data } = await this.client.get(`/workflows/${id}`);
    return data;
  }

  async createWorkflow(workflow: Partial<Workflow>): Promise<Workflow> {
    const { data } = await this.client.post('/workflows', workflow);
    return data;
  }

  async updateWorkflow(id: string, workflow: Partial<Workflow>): Promise<Workflow> {
    const { data } = await this.client.patch(`/workflows/${id}`, workflow);
    return data;
  }

  async deleteWorkflow(id: string): Promise<void> {
    await this.client.delete(`/workflows/${id}`);
  }

  // ---------------------------------------------------------------------------
  // Executions
  // ---------------------------------------------------------------------------

  async getExecutions(
    page = 1,
    pageSize = 20,
    workflowId?: string
  ): Promise<PaginatedResponse<Execution>> {
    const { data } = await this.client.get('/executions', {
      params: { page, page_size: pageSize, workflow_id: workflowId },
    });
    return data;
  }

  async getExecution(id: string): Promise<Execution> {
    const { data } = await this.client.get(`/executions/${id}`);
    return data;
  }

  async startExecution(workflowId: string, inputs?: Record<string, unknown>): Promise<Execution> {
    const { data } = await this.client.post(`/workflows/${workflowId}/execute`, { inputs });
    return data;
  }

  async pauseExecution(id: string): Promise<Execution> {
    const { data } = await this.client.post(`/executions/${id}/pause`);
    return data;
  }

  async resumeExecution(id: string, checkpointId?: string): Promise<Execution> {
    const { data } = await this.client.post(`/executions/${id}/resume`, {
      checkpoint_id: checkpointId,
    });
    return data;
  }

  async cancelExecution(id: string): Promise<void> {
    await this.client.post(`/executions/${id}/cancel`);
  }

  // ---------------------------------------------------------------------------
  // Agents
  // ---------------------------------------------------------------------------

  async getAgentDefinitions(): Promise<AgentDefinition[]> {
    const { data } = await this.client.get('/v1/agents');
    return data;
  }

  async getAgentDefinition(agentId: string): Promise<AgentDefinition> {
    const { data } = await this.client.get(`/v1/agents/${agentId}`);
    return data;
  }

  async getAgents(): Promise<Agent[]> {
    const { data } = await this.client.get('/agents');
    return data;
  }

  async getAgentStatus(role: string): Promise<Agent> {
    const { data } = await this.client.get(`/agents/${role}`);
    return data;
  }

  // ---------------------------------------------------------------------------
  // Budget
  // ---------------------------------------------------------------------------

  async getBudgets(): Promise<Budget[]> {
    const { data } = await this.client.get('/budgets');
    return data;
  }

  async getBudget(id: string): Promise<Budget> {
    const { data } = await this.client.get(`/budgets/${id}`);
    return data;
  }

  async createBudget(budget: Partial<Budget>): Promise<Budget> {
    const { data } = await this.client.post('/budgets', budget);
    return data;
  }

  async updateBudget(id: string, budget: Partial<Budget>): Promise<Budget> {
    const { data } = await this.client.patch(`/budgets/${id}`, budget);
    return data;
  }

  async getBudgetSummary(): Promise<BudgetSummary> {
    const { data } = await this.client.get('/budgets/summary');
    return data;
  }

  // ---------------------------------------------------------------------------
  // Checkpoints
  // ---------------------------------------------------------------------------

  async getCheckpoints(executionId: string): Promise<Checkpoint[]> {
    const { data } = await this.client.get(`/executions/${executionId}/checkpoints`);
    return data;
  }

  async getCheckpoint(id: string): Promise<Checkpoint> {
    const { data } = await this.client.get(`/checkpoints/${id}`);
    return data;
  }

  async deleteCheckpoint(id: string): Promise<void> {
    await this.client.delete(`/checkpoints/${id}`);
  }

  // ---------------------------------------------------------------------------
  // Dashboard
  // ---------------------------------------------------------------------------

  async getDashboardStats(): Promise<DashboardStats> {
    const { data } = await this.client.get('/v1/dashboard/stats');
    return data;
  }

  async getRecentExecutions(limit = 5): Promise<RecentExecution[]> {
    const { data } = await this.client.get('/v1/dashboard/recent-executions', {
      params: { limit },
    });
    return data;
  }

  async getDailyUsage(days = 7): Promise<DailyUsageData[]> {
    const { data } = await this.client.get('/v1/dashboard/usage/daily', {
      params: { days },
    });
    return data;
  }

  async getAgentUsage(): Promise<AgentUsageData[]> {
    const { data } = await this.client.get('/v1/dashboard/usage/by-agent');
    return data;
  }

  async getDashboardBudget(): Promise<DashboardBudget> {
    const { data } = await this.client.get('/v1/dashboard/budget');
    return data;
  }

  async getSystemHealth(): Promise<SystemHealth> {
    const { data } = await this.client.get('/health');
    return data;
  }

  // ---------------------------------------------------------------------------
  // Auth
  // ---------------------------------------------------------------------------

  async login(credentials: { username: string; password: string }): Promise<{ token: string }> {
    const { data } = await this.client.post('/auth/login', credentials);
    localStorage.setItem('gorgon_token', data.token);
    return data;
  }

  async logout(): Promise<void> {
    localStorage.removeItem('gorgon_token');
  }

  isAuthenticated(): boolean {
    return !!localStorage.getItem('gorgon_token');
  }

  // ---------------------------------------------------------------------------
  // MCP Servers
  // ---------------------------------------------------------------------------

  async getMCPServers(): Promise<MCPServer[]> {
    const { data } = await this.client.get('/v1/mcp/servers');
    return data;
  }

  async getMCPServer(id: string): Promise<MCPServer> {
    const { data } = await this.client.get(`/v1/mcp/servers/${id}`);
    return data;
  }

  async createMCPServer(server: MCPServerCreateInput): Promise<MCPServer> {
    const { data } = await this.client.post('/v1/mcp/servers', server);
    return data;
  }

  async updateMCPServer(id: string, server: Partial<MCPServerCreateInput>): Promise<MCPServer> {
    const { data } = await this.client.put(`/v1/mcp/servers/${id}`, server);
    return data;
  }

  async deleteMCPServer(id: string): Promise<void> {
    await this.client.delete(`/v1/mcp/servers/${id}`);
  }

  async testMCPConnection(id: string): Promise<{ success: boolean; error?: string; tools?: MCPTool[] }> {
    const { data } = await this.client.post(`/v1/mcp/servers/${id}/test`);
    return data;
  }

  async getMCPTools(serverId: string): Promise<MCPTool[]> {
    const { data } = await this.client.get(`/v1/mcp/servers/${serverId}/tools`);
    return data;
  }

  async invokeMCPTool(serverId: string, toolName: string, input: Record<string, unknown>): Promise<unknown> {
    const { data } = await this.client.post(`/v1/mcp/servers/${serverId}/tools/${toolName}/invoke`, input);
    return data;
  }

  // ---------------------------------------------------------------------------
  // YAML Workflows (Decision Support, etc.)
  // ---------------------------------------------------------------------------

  async getYAMLWorkflows(): Promise<{ id: string; name: string; description: string }[]> {
    const { data } = await this.client.get('/v1/yaml-workflows');
    return data;
  }

  async getYAMLWorkflow(id: string): Promise<Record<string, unknown>> {
    const { data } = await this.client.get(`/v1/yaml-workflows/${id}`);
    return data;
  }

  async executeYAMLWorkflow(
    workflowId: string,
    inputs: Record<string, unknown>
  ): Promise<Execution> {
    const { data } = await this.client.post('/v1/yaml-workflows/execute', {
      workflow_id: workflowId,
      inputs,
    });
    return data;
  }

  // ---------------------------------------------------------------------------
  // Credentials
  // ---------------------------------------------------------------------------

  async getCredentials(): Promise<Credential[]> {
    const { data } = await this.client.get('/v1/credentials');
    return data;
  }

  async createCredential(credential: { name: string; type: string; service: string; value: string }): Promise<Credential> {
    const { data } = await this.client.post('/v1/credentials', credential);
    return data;
  }

  async deleteCredential(id: string): Promise<void> {
    await this.client.delete(`/v1/credentials/${id}`);
  }

  // ---------------------------------------------------------------------------
  // Settings (User Preferences & API Keys)
  // ---------------------------------------------------------------------------

  async getPreferences(): Promise<UserPreferences> {
    const { data } = await this.client.get('/v1/settings/preferences');
    return data;
  }

  async updatePreferences(preferences: Partial<UserPreferencesUpdate>): Promise<UserPreferences> {
    const { data } = await this.client.post('/v1/settings/preferences', preferences);
    return data;
  }

  async getApiKeys(): Promise<ApiKeyInfo[]> {
    const { data } = await this.client.get('/v1/settings/api-keys');
    return data;
  }

  async getApiKeyStatus(): Promise<ApiKeyStatus> {
    const { data } = await this.client.get('/v1/settings/api-keys/status');
    return data;
  }

  async setApiKey(provider: 'openai' | 'anthropic' | 'github', key: string): Promise<{ status: string; key: ApiKeyInfo }> {
    const { data } = await this.client.post('/v1/settings/api-keys', { provider, key });
    return data;
  }

  async deleteApiKey(provider: string): Promise<void> {
    await this.client.delete(`/v1/settings/api-keys/${provider}`);
  }

  // ---------------------------------------------------------------------------
  // Chat
  // ---------------------------------------------------------------------------

  async getChatSessions(): Promise<ChatSession[]> {
    const { data } = await this.client.get('/chat/sessions');
    return data;
  }

  async createChatSession(params?: { title?: string; project_path?: string; mode?: ChatMode }): Promise<ChatSession> {
    const { data } = await this.client.post('/chat/sessions', params);
    return data;
  }

  async getChatSession(sessionId: string): Promise<ChatSessionDetail> {
    const { data } = await this.client.get(`/chat/sessions/${sessionId}`);
    return data;
  }

  async deleteChatSession(sessionId: string): Promise<void> {
    await this.client.delete(`/chat/sessions/${sessionId}`);
  }

  async getChatSessionJobs(sessionId: string): Promise<{ session_id: string; job_ids: string[] }> {
    const { data } = await this.client.get(`/chat/sessions/${sessionId}/jobs`);
    return data;
  }

  // Note: sendChatMessage uses fetch for SSE streaming, not this client
  getAuthToken(): string {
    return localStorage.getItem('gorgon_token') || '';
  }

  getBaseUrl(): string {
    return API_BASE_URL;
  }
}

// Settings types
export interface UserPreferences {
  user_id: string;
  theme: 'light' | 'dark' | 'system';
  compact_view: boolean;
  show_costs: boolean;
  default_page_size: number;
  notifications: {
    execution_complete: boolean;
    execution_failed: boolean;
    budget_alert: boolean;
  };
  created_at?: string;
  updated_at?: string;
}

export interface UserPreferencesUpdate {
  theme?: 'light' | 'dark' | 'system';
  compact_view?: boolean;
  show_costs?: boolean;
  default_page_size?: number;
  notifications?: {
    execution_complete?: boolean;
    execution_failed?: boolean;
    budget_alert?: boolean;
  };
}

export interface ApiKeyInfo {
  id: number;
  provider: string;
  key_prefix: string;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyStatus {
  openai: boolean;
  anthropic: boolean;
  github: boolean;
}

// Export singleton instance
export const api = new GorgonApiClient();

// Export types for external use
export type { GorgonApiClient };

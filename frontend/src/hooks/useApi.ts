import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useLiveExecutionStore } from '@/stores';
import type { Workflow, Budget } from '@/types';

// =============================================================================
// Query Keys
// =============================================================================

export const queryKeys = {
  workflows: ['workflows'] as const,
  workflow: (id: string) => ['workflows', id] as const,
  executions: ['executions'] as const,
  execution: (id: string) => ['executions', id] as const,
  agents: ['agents'] as const,
  budgets: ['budgets'] as const,
  budgetSummary: ['budgets', 'summary'] as const,
  checkpoints: (executionId: string) => ['checkpoints', executionId] as const,
  dashboardStats: ['dashboard', 'stats'] as const,
  systemHealth: ['system', 'health'] as const,
};

// =============================================================================
// Workflow Hooks
// =============================================================================

export function useWorkflows(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: [...queryKeys.workflows, page, pageSize],
    queryFn: () => api.getWorkflows(page, pageSize),
  });
}

export function useWorkflow(id: string) {
  return useQuery({
    queryKey: queryKeys.workflow(id),
    queryFn: () => api.getWorkflow(id),
    enabled: !!id,
  });
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (workflow: Partial<Workflow>) => api.createWorkflow(workflow),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows });
    },
  });
}

export function useUpdateWorkflow() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, workflow }: { id: string; workflow: Partial<Workflow> }) =>
      api.updateWorkflow(id, workflow),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflow(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows });
    },
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.deleteWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows });
    },
  });
}

// =============================================================================
// Execution Hooks
// =============================================================================

export function useExecutions(page = 1, pageSize = 20, workflowId?: string) {
  return useQuery({
    queryKey: [...queryKeys.executions, page, pageSize, workflowId],
    queryFn: () => api.getExecutions(page, pageSize, workflowId),
  });
}

export function useExecution(id: string) {
  const isWebSocketConnected = useLiveExecutionStore((state) => state.isWebSocketConnected);

  return useQuery({
    queryKey: queryKeys.execution(id),
    queryFn: () => api.getExecution(id),
    enabled: !!id,
    refetchInterval: (query) => {
      // Skip polling if WebSocket is connected
      if (isWebSocketConnected) {
        return false;
      }
      // Fallback: poll while running when WebSocket is disconnected
      const status = query.state.data?.status;
      return status === 'running' ? 2000 : false;
    },
  });
}

export function useStartExecution() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ workflowId, inputs }: { workflowId: string; inputs?: Record<string, unknown> }) =>
      api.startExecution(workflowId, inputs),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.executions });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
    },
  });
}

export function usePauseExecution() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.pauseExecution(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.execution(id) });
    },
  });
}

export function useResumeExecution() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, checkpointId }: { id: string; checkpointId?: string }) =>
      api.resumeExecution(id, checkpointId),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.execution(id) });
    },
  });
}

export function useCancelExecution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.cancelExecution(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.execution(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.executions });
    },
  });
}

// =============================================================================
// YAML Workflow Hooks (Decision Support, etc.)
// =============================================================================

export function useStartYAMLExecution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ workflowId, inputs }: { workflowId: string; inputs: Record<string, unknown> }) =>
      api.executeYAMLWorkflow(workflowId, inputs),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.executions });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStats });
    },
  });
}

// =============================================================================
// Agent Hooks
// =============================================================================

export function useAgents() {
  return useQuery({
    queryKey: queryKeys.agents,
    queryFn: () => api.getAgents(),
  });
}

// =============================================================================
// Budget Hooks
// =============================================================================

export function useBudgets() {
  return useQuery({
    queryKey: queryKeys.budgets,
    queryFn: () => api.getBudgets(),
  });
}

export function useBudgetSummary() {
  return useQuery({
    queryKey: queryKeys.budgetSummary,
    queryFn: () => api.getBudgetSummary(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useCreateBudget() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (budget: Partial<Budget>) => api.createBudget(budget),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgetSummary });
    },
  });
}

export function useUpdateBudget() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, budget }: { id: string; budget: Partial<Budget> }) =>
      api.updateBudget(id, budget),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgetSummary });
    },
  });
}

// =============================================================================
// Checkpoint Hooks
// =============================================================================

export function useCheckpoints(executionId: string) {
  return useQuery({
    queryKey: queryKeys.checkpoints(executionId),
    queryFn: () => api.getCheckpoints(executionId),
    enabled: !!executionId,
  });
}

// =============================================================================
// Dashboard Hooks
// =============================================================================

export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboardStats,
    queryFn: () => api.getDashboardStats(),
    refetchInterval: 10000, // Refresh every 10 seconds
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: queryKeys.systemHealth,
    queryFn: () => api.getSystemHealth(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

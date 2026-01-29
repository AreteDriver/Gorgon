import { useState } from 'react';
import {
  Play,
  Pause,
  Square,
  RotateCcw,
  ChevronRight,
  Clock,
  Zap,
  Coins,
  Filter,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useExecutions, usePauseExecution, useResumeExecution, useCancelExecution } from '@/hooks/useApi';
import {
  formatRelativeTime,
  formatDuration,
  formatTokens,
  formatCurrency,
  getStatusColor,
  getAgentColor,
} from '@/lib/utils';
import { PageLoading } from '@/components/PageLoading';
import { toast } from '@/hooks/useToast';
import type { Execution, WorkflowStatus } from '@/types';

// Mock executions for demo
const mockExecutions: Execution[] = [
  {
    id: 'exec-1',
    workflowId: '1',
    workflowName: 'Feature Development Pipeline',
    status: 'running',
    startedAt: '2026-01-18T10:30:00Z',
    currentStep: 'Implement',
    progress: 45,
    logs: [],
    metrics: { totalTokens: 23500, totalCost: 0.67, duration: 125000, stepMetrics: [] },
  },
  {
    id: 'exec-2',
    workflowId: '2',
    workflowName: 'Documentation Generator',
    status: 'completed',
    startedAt: '2026-01-18T09:15:00Z',
    completedAt: '2026-01-18T09:28:00Z',
    progress: 100,
    logs: [],
    metrics: { totalTokens: 45200, totalCost: 1.23, duration: 780000, stepMetrics: [] },
  },
  {
    id: 'exec-3',
    workflowId: '3',
    workflowName: 'Architecture Review',
    status: 'paused',
    startedAt: '2026-01-18T08:00:00Z',
    currentStep: 'Generate Report',
    progress: 60,
    logs: [],
    metrics: { totalTokens: 31000, totalCost: 0.89, duration: 420000, stepMetrics: [] },
    checkpointId: 'cp-123',
  },
  {
    id: 'exec-4',
    workflowId: '1',
    workflowName: 'Feature Development Pipeline',
    status: 'failed',
    startedAt: '2026-01-17T16:00:00Z',
    completedAt: '2026-01-17T16:15:00Z',
    currentStep: 'Code Review',
    progress: 75,
    logs: [],
    metrics: { totalTokens: 28000, totalCost: 0.78, duration: 900000, stepMetrics: [] },
  },
];

const statusFilters: { label: string; value: WorkflowStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Running', value: 'running' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Paused', value: 'paused' },
];

export function ExecutionsPage() {
  const [statusFilter, setStatusFilter] = useState<WorkflowStatus | 'all'>('all');
  const [selectedExecution, setSelectedExecution] = useState<string | null>(null);

  const { data: executionsData, isLoading } = useExecutions();
  const pauseExecution = usePauseExecution();
  const resumeExecution = useResumeExecution();
  const cancelExecution = useCancelExecution();

  const executions = executionsData?.data || mockExecutions;
  const filteredExecutions = executions.filter(
    (e) => statusFilter === 'all' || e.status === statusFilter
  );

  if (isLoading) {
    return <PageLoading message="Loading executions..." />;
  }

  const handlePause = async (id: string) => {
    try {
      await pauseExecution.mutateAsync(id);
      toast({ title: 'Execution paused', variant: 'success' });
    } catch (error) {
      toast({
        title: 'Failed to pause',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  };

  const handleResume = async (id: string, checkpointId?: string) => {
    try {
      await resumeExecution.mutateAsync({ id, checkpointId });
      toast({ title: 'Execution resumed', variant: 'success' });
    } catch (error) {
      toast({
        title: 'Failed to resume',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  };

  const handleCancel = async (id: string) => {
    try {
      await cancelExecution.mutateAsync(id);
      toast({ title: 'Execution cancelled', variant: 'success' });
    } catch (error) {
      toast({
        title: 'Failed to cancel',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    }
  };

  const getStatusBadgeVariant = (status: WorkflowStatus) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'destructive';
      case 'running': return 'default';
      case 'paused': return 'warning';
      default: return 'secondary';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Executions</h1>
        <p className="text-muted-foreground">Monitor and manage workflow executions</p>
      </div>

      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        {statusFilters.map((filter) => (
          <Button
            key={filter.value}
            variant={statusFilter === filter.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter(filter.value)}
          >
            {filter.label}
          </Button>
        ))}
      </div>

      <div className="space-y-4">
        {filteredExecutions.map((execution) => (
          <Card
            key={execution.id}
            className={`cursor-pointer transition-shadow hover:shadow-md ${
              selectedExecution === execution.id ? 'ring-2 ring-primary' : ''
            }`}
            onClick={() => setSelectedExecution(selectedExecution === execution.id ? null : execution.id)}
          >
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div
                    className={`h-10 w-10 rounded-full flex items-center justify-center ${
                      execution.status === 'running' ? 'animate-pulse-slow' : ''
                    }`}
                    style={{ backgroundColor: `${getStatusColor(execution.status)}20` }}
                  >
                    <div
                      className="h-3 w-3 rounded-full"
                      style={{ backgroundColor: getStatusColor(execution.status) }}
                    />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium">{execution.workflowName}</h3>
                      <Badge variant={getStatusBadgeVariant(execution.status)}>{execution.status}</Badge>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Started {formatRelativeTime(execution.startedAt)}
                      </span>
                      {execution.currentStep && <span>Current: {execution.currentStep}</span>}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-4 text-sm">
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Zap className="h-4 w-4" />{formatTokens(execution.metrics.totalTokens)}
                    </span>
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Coins className="h-4 w-4" />{formatCurrency(execution.metrics.totalCost)}
                    </span>
                    <span className="text-muted-foreground">{formatDuration(execution.metrics.duration)}</span>
                  </div>
                  <div className="w-32">
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span>{execution.progress}%</span>
                    </div>
                    <Progress value={execution.progress} className="h-2" />
                  </div>
                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    {execution.status === 'running' && (
                      <Button variant="ghost" size="icon" onClick={() => handlePause(execution.id)}>
                        <Pause className="h-4 w-4" />
                      </Button>
                    )}
                    {execution.status === 'paused' && (
                      <Button variant="ghost" size="icon" onClick={() => handleResume(execution.id, execution.checkpointId)}>
                        <Play className="h-4 w-4" />
                      </Button>
                    )}
                    {(execution.status === 'running' || execution.status === 'paused') && (
                      <Button variant="ghost" size="icon" onClick={() => handleCancel(execution.id)}>
                        <Square className="h-4 w-4" />
                      </Button>
                    )}
                    {execution.status === 'failed' && (
                      <Button variant="ghost" size="icon" onClick={() => handleResume(execution.id, execution.checkpointId)}>
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                    )}
                    <ChevronRight className={`h-4 w-4 text-muted-foreground transition-transform ${
                      selectedExecution === execution.id ? 'rotate-90' : ''
                    }`} />
                  </div>
                </div>
              </div>

              {selectedExecution === execution.id && (
                <div className="mt-4 border-t pt-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <h4 className="mb-2 text-sm font-medium">Steps</h4>
                      <div className="space-y-2">
                        {[
                          { name: 'Plan Feature', agent: 'planner', status: 'completed' },
                          { name: 'Implement', agent: 'builder', status: execution.status === 'running' ? 'running' : 'completed' },
                          { name: 'Write Tests', agent: 'tester', status: 'pending' },
                          { name: 'Code Review', agent: 'reviewer', status: 'pending' },
                        ].map((step, idx) => (
                          <div key={idx} className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-2 rounded-full" style={{ backgroundColor: getStatusColor(step.status) }} />
                              <span className="text-sm">{step.name}</span>
                            </div>
                            <span className="text-xs font-medium" style={{ color: getAgentColor(step.agent) }}>{step.agent}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h4 className="mb-2 text-sm font-medium">Recent Logs</h4>
                      <div className="rounded-lg bg-muted/50 p-3 font-mono text-xs">
                        <div className="text-green-600">[10:30:15] Planner: Analyzing requirements...</div>
                        <div className="text-green-600">[10:30:45] Planner: Generated 5 steps</div>
                        <div className="text-blue-600">[10:31:00] Builder: Starting implementation...</div>
                        {execution.status === 'running' && (
                          <div className="text-blue-600 animate-pulse">[10:33:00] Builder: Writing logic...</div>
                        )}
                      </div>
                    </div>
                  </div>
                  {execution.checkpointId && (
                    <div className="mt-4 rounded-lg bg-yellow-500/10 p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-yellow-600">Checkpoint: {execution.checkpointId}</span>
                        <Button variant="outline" size="sm" onClick={() => handleResume(execution.id, execution.checkpointId)}>
                          Resume from checkpoint
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

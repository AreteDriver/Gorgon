import { useState, useEffect } from 'react';
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
  Wifi,
  WifiOff,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useExecutions, usePauseExecution, useResumeExecution, useCancelExecution } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useLiveExecutionStore } from '@/stores';
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
import type { WorkflowStatus } from '@/types';

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

  // WebSocket connection for real-time updates
  const { isConnected, connectionState, subscribe, unsubscribe } = useWebSocket();
  const { setWebSocketConnected, setExecution } = useLiveExecutionStore();

  // Update store with WebSocket connection state
  useEffect(() => {
    setWebSocketConnected(isConnected);
  }, [isConnected, setWebSocketConnected]);

  const executions = executionsData?.data || [];

  // Subscribe to running executions for real-time updates
  useEffect(() => {
    const runningIds = executions
      .filter((e) => e.status === 'running' || e.status === 'paused')
      .map((e) => e.id);

    if (runningIds.length > 0 && isConnected) {
      // Add executions to store for WebSocket updates
      for (const execution of executions.filter((e) => runningIds.includes(e.id))) {
        setExecution(execution);
      }
      subscribe(runningIds);
    }

    return () => {
      if (runningIds.length > 0) {
        unsubscribe(runningIds);
      }
    };
  }, [executions, isConnected, subscribe, unsubscribe, setExecution]);
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

  const getConnectionStatusColor = () => {
    switch (connectionState) {
      case 'connected':
        return 'text-green-500';
      case 'connecting':
      case 'reconnecting':
        return 'text-yellow-500';
      default:
        return 'text-muted-foreground';
    }
  };

  const getConnectionStatusText = () => {
    switch (connectionState) {
      case 'connected':
        return 'Live updates active';
      case 'connecting':
        return 'Connecting...';
      case 'reconnecting':
        return 'Reconnecting...';
      default:
        return 'Live updates disconnected';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">Executions</h1>
          <p className="text-muted-foreground">Monitor and manage workflow executions</p>
        </div>
        <div className={`flex items-center gap-2 text-sm ${getConnectionStatusColor()}`}>
          {isConnected ? (
            <Wifi className="h-4 w-4" />
          ) : (
            <WifiOff className="h-4 w-4" />
          )}
          <span>{getConnectionStatusText()}</span>
        </div>
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
        {filteredExecutions.length === 0 && (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <Play className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-medium mb-2">No executions yet</h3>
              <p className="text-muted-foreground text-center max-w-md">
                {statusFilter === 'all'
                  ? 'Run a workflow from the Workflows page to see executions here.'
                  : `No ${statusFilter} executions found. Try a different filter.`}
              </p>
            </CardContent>
          </Card>
        )}
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
                      <Zap className="h-4 w-4" />{formatTokens(execution.metrics?.totalTokens ?? 0)}
                    </span>
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Coins className="h-4 w-4" />{formatCurrency(execution.metrics?.totalCost ?? 0)}
                    </span>
                    <span className="text-muted-foreground">{formatDuration(execution.metrics?.duration ?? 0)}</span>
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

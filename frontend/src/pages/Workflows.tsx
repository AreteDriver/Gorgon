import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Plus,
  Search,
  Play,
  Pencil,
  GitBranch,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useWorkflows, useStartExecution } from '@/hooks/useApi';
import { formatRelativeTime, getAgentColor } from '@/lib/utils';
import { PageLoading } from '@/components/PageLoading';
import { toast } from '@/hooks/useToast';
import type { Workflow, AgentRole } from '@/types';

// Mock workflows for demo
const mockWorkflows: Workflow[] = [
  {
    id: '1',
    name: 'Feature Development Pipeline',
    description: 'End-to-end feature development with planning, coding, testing, and review',
    status: 'draft',
    createdAt: '2026-01-15T10:00:00Z',
    updatedAt: '2026-01-17T14:30:00Z',
    steps: [
      { id: 's1', name: 'Plan Feature', agentRole: 'planner', inputs: {}, status: 'pending' },
      { id: 's2', name: 'Implement', agentRole: 'builder', inputs: {}, status: 'pending' },
      { id: 's3', name: 'Write Tests', agentRole: 'tester', inputs: {}, status: 'pending' },
      { id: 's4', name: 'Code Review', agentRole: 'reviewer', inputs: {}, status: 'pending' },
    ],
  },
  {
    id: '2',
    name: 'Documentation Generator',
    description: 'Generate comprehensive documentation from code and comments',
    status: 'draft',
    createdAt: '2026-01-10T08:00:00Z',
    updatedAt: '2026-01-16T09:15:00Z',
    steps: [
      { id: 's1', name: 'Analyze Code', agentRole: 'analyst', inputs: {}, status: 'pending' },
      { id: 's2', name: 'Generate Docs', agentRole: 'documenter', inputs: {}, status: 'pending' },
      { id: 's3', name: 'Review', agentRole: 'reviewer', inputs: {}, status: 'pending' },
    ],
  },
  {
    id: '3',
    name: 'Architecture Review',
    description: 'Comprehensive architecture analysis and recommendations',
    status: 'draft',
    createdAt: '2026-01-08T12:00:00Z',
    updatedAt: '2026-01-14T16:45:00Z',
    steps: [
      { id: 's1', name: 'Analyze Structure', agentRole: 'architect', inputs: {}, status: 'pending' },
      { id: 's2', name: 'Generate Report', agentRole: 'reporter', inputs: {}, status: 'pending' },
      { id: 's3', name: 'Visualize', agentRole: 'visualizer', inputs: {}, status: 'pending' },
    ],
  },
];

export function WorkflowsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const { data: workflowsData, isLoading } = useWorkflows();
  const startExecution = useStartExecution();

  // Use mock data for demo when API unavailable
  const workflows = workflowsData?.data || mockWorkflows;
  const filteredWorkflows = workflows.filter((w) =>
    w.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleRun = async (workflowId: string) => {
    try {
      await startExecution.mutateAsync({ workflowId });
      toast({
        title: 'Workflow started',
        description: 'Execution has been queued successfully.',
        variant: 'success',
      });
    } catch (error) {
      toast({
        title: 'Failed to start workflow',
        description: error instanceof Error ? error.message : 'Unknown error occurred',
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return <PageLoading message="Loading workflows..." />;
  }

  const getAgentsInWorkflow = (workflow: Workflow): AgentRole[] => {
    return [...new Set(workflow.steps.map((s) => s.agentRole))];
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Workflows</h1>
          <p className="text-muted-foreground">
            Create and manage multi-agent workflows
          </p>
        </div>
        <Button asChild>
          <Link to="/workflows/new">
            <Plus className="mr-2 h-4 w-4" />
            New Workflow
          </Link>
        </Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search workflows..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-lg border bg-background py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      {/* Workflows Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredWorkflows.map((workflow) => (
          <Card key={workflow.id} className="group relative">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="rounded-lg bg-primary/10 p-2">
                    <GitBranch className="h-4 w-4 text-primary" />
                  </div>
                  <CardTitle className="text-base">{workflow.name}</CardTitle>
                </div>
                <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => handleRun(workflow.id)}
                  >
                    <Play className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
                    <Link to={`/workflows/${workflow.id}/edit`}>
                      <Pencil className="h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-sm text-muted-foreground line-clamp-2">
                {workflow.description || 'No description'}
              </p>

              {/* Agent Pills */}
              <div className="mb-4 flex flex-wrap gap-1">
                {getAgentsInWorkflow(workflow).map((agent) => (
                  <span
                    key={agent}
                    className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                    style={{
                      backgroundColor: `${getAgentColor(agent)}20`,
                      color: getAgentColor(agent),
                    }}
                  >
                    {agent}
                  </span>
                ))}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{workflow.steps.length} steps</span>
                <span>Updated {formatRelativeTime(workflow.updatedAt)}</span>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* New Workflow Card */}
        <Card className="flex items-center justify-center border-dashed">
          <Link
            to="/workflows/new"
            className="flex flex-col items-center gap-2 p-8 text-muted-foreground transition-colors hover:text-primary"
          >
            <div className="rounded-full border-2 border-dashed p-4">
              <Plus className="h-6 w-6" />
            </div>
            <span className="font-medium">Create Workflow</span>
          </Link>
        </Card>
      </div>
    </div>
  );
}

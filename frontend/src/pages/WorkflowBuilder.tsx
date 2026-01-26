import { useCallback, useEffect, useRef, DragEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ReactFlowProvider, useReactFlow } from '@xyflow/react';

import { WorkflowCanvas } from '@/components/workflow-builder/WorkflowCanvas';
import { WorkflowToolbar } from '@/components/workflow-builder/WorkflowToolbar';
import { NodePalette } from '@/components/workflow-builder/NodePalette';
import { PropertyPanel } from '@/components/workflow-builder/PropertyPanel';
import { useWorkflowBuilderStore } from '@/stores';
import { useWorkflow, useCreateWorkflow, useUpdateWorkflow } from '@/hooks/useApi';
import {
  createAgentNodeData,
  createShellNodeData,
  createCheckpointNodeData,
  createParallelNodeData,
  createFanOutNodeData,
  createFanInNodeData,
  createMapReduceNodeData,
  type AgentNodeData,
} from '@/types/workflow-builder';
import {
  exportToYaml,
  toYamlString,
  parseYamlString,
  importFromYaml,
} from '@/lib/workflow-serializer';
import type { AgentRole, WorkflowStep } from '@/types';

function WorkflowBuilderContent() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  const {
    nodes,
    edges,
    workflowId,
    workflowName,
    addNode,
    loadWorkflow,
    clearWorkflow,
    markClean,
  } = useWorkflowBuilderStore();

  const { data: existingWorkflow } = useWorkflow(id ?? '');
  const createWorkflow = useCreateWorkflow();
  const updateWorkflow = useUpdateWorkflow();

  // Load existing workflow if editing
  useEffect(() => {
    if (id && existingWorkflow) {
      // Convert workflow steps to nodes
      const workflowNodes = existingWorkflow.steps.map((step: WorkflowStep, index: number) => ({
        id: step.id,
        type: 'agent',
        position: { x: 250, y: 100 + index * 150 },
        data: {
          type: 'agent' as const,
          role: step.agentRole,
          name: step.name,
          prompt: step.inputs?.prompt as string | undefined,
          onFailure: 'stop' as const,
        },
      }));

      // Create edges between consecutive nodes
      const workflowEdges = workflowNodes.slice(0, -1).map((node, index) => ({
        id: `e-${node.id}-${workflowNodes[index + 1].id}`,
        source: node.id,
        target: workflowNodes[index + 1].id,
        type: 'default',
      }));

      loadWorkflow(id, existingWorkflow.name, workflowNodes, workflowEdges);
    }
  }, [id, existingWorkflow, loadWorkflow]);

  // Clear workflow on unmount or when creating new
  useEffect(() => {
    if (!id) {
      clearWorkflow();
    }
    return () => {
      // Don't clear on unmount if navigating away - let the store persist
    };
  }, [id, clearWorkflow]);

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow-type');
      const value = event.dataTransfer.getData('application/reactflow');

      if (!type) {
        return;
      }

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      if (type === 'agent') {
        const data = createAgentNodeData(value as AgentRole);
        addNode('agent', position, data);
      } else if (type === 'shell') {
        const data = createShellNodeData();
        addNode('shell', position, data);
      } else if (type === 'checkpoint') {
        const data = createCheckpointNodeData();
        addNode('checkpoint', position, data);
      } else if (type === 'parallel') {
        const data = createParallelNodeData();
        addNode('parallel', position, data);
      } else if (type === 'fan_out') {
        const data = createFanOutNodeData();
        addNode('fan_out', position, data);
      } else if (type === 'fan_in') {
        const data = createFanInNodeData();
        addNode('fan_in', position, data);
      } else if (type === 'map_reduce') {
        const data = createMapReduceNodeData();
        addNode('map_reduce', position, data);
      }
    },
    [screenToFlowPosition, addNode]
  );

  const handleExportYaml = useCallback(() => {
    try {
      const workflow = exportToYaml(nodes, edges, workflowName);
      const yamlString = toYamlString(workflow);

      // Create and download file
      const blob = new Blob([yamlString], { type: 'text/yaml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${workflowName.toLowerCase().replace(/\s+/g, '-')}.yaml`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export workflow:', error);
      alert(error instanceof Error ? error.message : 'Failed to export workflow');
    }
  }, [nodes, edges, workflowName]);

  const handleImportYaml = useCallback((yamlString: string) => {
    try {
      const workflow = parseYamlString(yamlString);
      const { nodes: importedNodes, edges: importedEdges } = importFromYaml(workflow);

      loadWorkflow(
        null as unknown as string, // No ID for imported workflows
        workflow.name,
        importedNodes,
        importedEdges
      );
    } catch (error) {
      console.error('Failed to import workflow:', error);
      alert(error instanceof Error ? error.message : 'Failed to import workflow');
    }
  }, [loadWorkflow]);

  const handleSave = useCallback(async () => {
    // Convert nodes/edges to workflow format
    const steps: Partial<WorkflowStep>[] = nodes.map((node) => {
      const data = node.data as AgentNodeData;
      return {
        id: node.id,
        name: data.name,
        agentRole: data.role,
        inputs: {
          prompt: data.prompt,
        },
        status: 'pending' as const,
      };
    });

    const workflowData = {
      name: workflowName,
      description: `Visual workflow with ${steps.length} steps`,
      steps: steps as WorkflowStep[],
      status: 'draft' as const,
    };

    try {
      if (workflowId) {
        await updateWorkflow.mutateAsync({ id: workflowId, workflow: workflowData });
      } else {
        const result = await createWorkflow.mutateAsync(workflowData);
        // Navigate to edit mode with the new ID
        navigate(`/workflows/${result.id}/edit`, { replace: true });
      }
      markClean();
    } catch (error) {
      console.error('Failed to save workflow:', error);
    }
  }, [nodes, workflowName, workflowId, createWorkflow, updateWorkflow, navigate, markClean]);

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <WorkflowToolbar
        onSave={handleSave}
        onExportYaml={handleExportYaml}
        onImportYaml={handleImportYaml}
        isSaving={createWorkflow.isPending || updateWorkflow.isPending}
      />
      <div className="flex flex-1 overflow-hidden">
        <NodePalette />
        <div
          ref={reactFlowWrapper}
          className="flex-1"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <WorkflowCanvas />
        </div>
        <PropertyPanel />
      </div>
    </div>
  );
}

export function WorkflowBuilderPage() {
  return (
    <ReactFlowProvider>
      <WorkflowBuilderContent />
    </ReactFlowProvider>
  );
}

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
  createBranchNodeData,
  createLoopNodeData,
  isAgentNode,
  isShellNode,
  isCheckpointNode,
  isParallelNode,
  isFanOutNode,
  isFanInNode,
  isMapReduceNode,
  isBranchNode,
  isLoopNode,
  type WorkflowNodeData,
  type NodeCondition,
} from '@/types/workflow-builder';
import type { Node } from '@xyflow/react';
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
      // Convert workflow steps to nodes, restoring correct node types
      const workflowNodes = existingWorkflow.steps.map((step: WorkflowStep, index: number) => {
        const stepType = (step.inputs?.stepType as string) || 'agent';
        const position = { x: 250, y: 100 + index * 150 };

        switch (stepType) {
          case 'shell':
            return {
              id: step.id,
              type: 'shell',
              position,
              data: {
                type: 'shell' as const,
                name: step.name,
                command: (step.inputs?.command as string) || '',
                allowFailure: step.inputs?.allowFailure as boolean | undefined,
                timeout: step.inputs?.timeout as number | undefined,
                condition: step.inputs?.condition as NodeCondition | undefined,
              },
            };

          case 'checkpoint':
            return {
              id: step.id,
              type: 'checkpoint',
              position,
              data: {
                type: 'checkpoint' as const,
                name: step.name,
                message: step.inputs?.message as string,
              },
            };

          case 'parallel':
            return {
              id: step.id,
              type: 'parallel',
              position,
              data: {
                type: 'parallel' as const,
                name: step.name,
                strategy: step.inputs?.strategy as 'threading' | 'asyncio' | 'process',
                maxWorkers: step.inputs?.maxWorkers as number,
                failFast: step.inputs?.failFast as boolean,
              },
            };

          case 'fan_out':
            return {
              id: step.id,
              type: 'fan_out',
              position,
              data: {
                type: 'fan_out' as const,
                name: step.name,
                itemsVariable: step.inputs?.itemsVariable as string,
                maxConcurrent: step.inputs?.maxConcurrent as number,
                failFast: step.inputs?.failFast as boolean,
              },
            };

          case 'fan_in':
            return {
              id: step.id,
              type: 'fan_in',
              position,
              data: {
                type: 'fan_in' as const,
                name: step.name,
                inputVariable: step.inputs?.inputVariable as string,
                aggregation: step.inputs?.aggregation as 'concat' | 'claude_code',
                aggregatePrompt: step.inputs?.aggregatePrompt as string,
              },
            };

          case 'map_reduce':
            return {
              id: step.id,
              type: 'map_reduce',
              position,
              data: {
                type: 'map_reduce' as const,
                name: step.name,
                itemsVariable: step.inputs?.itemsVariable as string,
                maxConcurrent: step.inputs?.maxConcurrent as number,
                failFast: step.inputs?.failFast as boolean,
                mapPrompt: step.inputs?.mapPrompt as string,
                reducePrompt: step.inputs?.reducePrompt as string,
              },
            };

          case 'branch':
            return {
              id: step.id,
              type: 'branch',
              position,
              data: {
                type: 'branch' as const,
                name: step.name,
                condition: step.inputs?.condition as NodeCondition,
                trueLabel: step.inputs?.trueLabel as string,
                falseLabel: step.inputs?.falseLabel as string,
              },
            };

          case 'loop':
            return {
              id: step.id,
              type: 'loop',
              position,
              data: {
                type: 'loop' as const,
                name: step.name,
                condition: step.inputs?.condition as NodeCondition | undefined,
                maxIterations: step.inputs?.maxIterations as number | undefined,
                iterationVariable: step.inputs?.iterationVariable as string | undefined,
                loopType: step.inputs?.loopType as 'while' | 'for' | 'until' | undefined,
              },
            };

          case 'agent':
          default:
            return {
              id: step.id,
              type: 'agent',
              position,
              data: {
                type: 'agent' as const,
                role: step.agentRole,
                name: step.name,
                prompt: step.inputs?.prompt as string | undefined,
                outputs: step.inputs?.outputs as string[] | undefined,
                onFailure: (step.inputs?.onFailure as 'stop' | 'continue' | 'retry') || 'stop',
                maxRetries: step.inputs?.maxRetries as number | undefined,
                condition: step.inputs?.condition as NodeCondition | undefined,
              },
            };
        }
      });

      // Create edges between consecutive nodes
      const workflowEdges = workflowNodes.slice(0, -1).map((node, index) => ({
        id: `e-${node.id}-${workflowNodes[index + 1].id}`,
        source: node.id,
        target: workflowNodes[index + 1].id,
        type: 'default',
      }));

      loadWorkflow(id, existingWorkflow.name, workflowNodes as Node<WorkflowNodeData>[], workflowEdges);
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
      } else if (type === 'branch') {
        const data = createBranchNodeData();
        addNode('branch', position, data);
      } else if (type === 'loop') {
        const data = createLoopNodeData();
        addNode('loop', position, data);
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
    // Convert nodes/edges to workflow format, handling all node types
    const steps: Partial<WorkflowStep>[] = nodes.map((node) => {
      const data = node.data as WorkflowNodeData;

      // Base step with common fields
      const baseStep = {
        id: node.id,
        status: 'pending' as const,
      };

      if (isAgentNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: data.role,
          inputs: {
            stepType: 'agent',
            prompt: data.prompt,
            outputs: data.outputs,
            onFailure: data.onFailure,
            maxRetries: data.maxRetries,
            condition: data.condition,
          },
        };
      }

      if (isShellNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: 'builder' as const, // Shell commands use builder as default
          inputs: {
            stepType: 'shell',
            command: data.command,
            allowFailure: data.allowFailure,
            timeout: data.timeout,
            condition: data.condition,
          },
        };
      }

      if (isCheckpointNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: 'planner' as const, // Checkpoints use planner as placeholder
          inputs: {
            stepType: 'checkpoint',
            message: data.message,
          },
        };
      }

      if (isParallelNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: 'architect' as const, // Parallel coordination uses architect
          inputs: {
            stepType: 'parallel',
            strategy: data.strategy,
            maxWorkers: data.maxWorkers,
            failFast: data.failFast,
          },
        };
      }

      if (isFanOutNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: 'architect' as const,
          inputs: {
            stepType: 'fan_out',
            itemsVariable: data.itemsVariable,
            maxConcurrent: data.maxConcurrent,
            failFast: data.failFast,
          },
        };
      }

      if (isFanInNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: 'architect' as const,
          inputs: {
            stepType: 'fan_in',
            inputVariable: data.inputVariable,
            aggregation: data.aggregation,
            aggregatePrompt: data.aggregatePrompt,
          },
        };
      }

      if (isMapReduceNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: 'architect' as const,
          inputs: {
            stepType: 'map_reduce',
            itemsVariable: data.itemsVariable,
            maxConcurrent: data.maxConcurrent,
            failFast: data.failFast,
            mapPrompt: data.mapPrompt,
            reducePrompt: data.reducePrompt,
          },
        };
      }

      if (isBranchNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: 'architect' as const,
          inputs: {
            stepType: 'branch',
            condition: data.condition,
            trueLabel: data.trueLabel,
            falseLabel: data.falseLabel,
          },
        };
      }

      if (isLoopNode(data)) {
        return {
          ...baseStep,
          name: data.name,
          agentRole: 'architect' as const,
          inputs: {
            stepType: 'loop',
            condition: data.condition,
            maxIterations: data.maxIterations,
            iterationVariable: data.iterationVariable,
            loopType: data.loopType,
          },
        };
      }

      // Fallback for unknown node types - should never reach here
      return {
        ...baseStep,
        name: (data as { name?: string }).name || 'Unknown Step',
        agentRole: 'planner' as const,
        inputs: { stepType: 'unknown', rawData: JSON.stringify(data) },
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

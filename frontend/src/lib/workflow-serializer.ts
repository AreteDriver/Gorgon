/**
 * Workflow Serializer
 *
 * Converts between ReactFlow visual representation and YAML workflow format.
 *
 * Export: nodes/edges → YAML workflow
 * Import: YAML workflow → nodes/edges
 */

import yaml from 'js-yaml';
import type { Node, Edge } from '@xyflow/react';
import type {
  WorkflowNodeData,
  AgentNodeData,
  ShellNodeData,
  CheckpointNodeData,
  ParallelNodeData,
  FanOutNodeData,
  FanInNodeData,
  MapReduceNodeData,
  BranchNodeData,
  LoopNodeData,
} from '@/types/workflow-builder';
import type { AgentRole } from '@/types';

// =============================================================================
// YAML Workflow Types (matches backend loader.py)
// =============================================================================

export interface YamlCondition {
  field: string;
  operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than';
  value: unknown;
}

export interface YamlStep {
  id: string;
  type: 'claude_code' | 'openai' | 'shell' | 'parallel' | 'checkpoint' | 'fan_out' | 'fan_in' | 'map_reduce' | 'branch' | 'loop';
  params?: Record<string, unknown>;
  condition?: YamlCondition;
  on_failure?: 'abort' | 'skip' | 'retry';
  max_retries?: number;
  timeout_seconds?: number;
  outputs?: string[];
  depends_on?: string | string[];
}

export interface YamlInput {
  type: string;
  required?: boolean;
  default?: unknown;
  description?: string;
}

export interface YamlWorkflow {
  name: string;
  version?: string;
  description?: string;
  token_budget?: number;
  timeout_seconds?: number;
  inputs?: Record<string, YamlInput>;
  outputs?: string[];
  steps: YamlStep[];
  metadata?: Record<string, unknown>;
  settings?: {
    auto_parallel?: boolean;
    auto_parallel_max_workers?: number;
  };
}

// =============================================================================
// Export: ReactFlow → YAML
// =============================================================================

/**
 * Convert a single ReactFlow node to a YAML step.
 */
function nodeToStep(node: Node<WorkflowNodeData>, edges: Edge[]): YamlStep {
  const data = node.data;

  // Find dependencies (incoming edges)
  const incomingEdges = edges.filter((e) => e.target === node.id);
  const dependsOn = incomingEdges.map((e) => e.source);

  const baseStep: Partial<YamlStep> = {
    id: node.id,
    depends_on: dependsOn.length > 0 ? (dependsOn.length === 1 ? dependsOn[0] : dependsOn) : undefined,
  };

  switch (data.type) {
    case 'agent': {
      const agentData = data as AgentNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'claude_code',
        params: {
          role: agentData.role,
          prompt: agentData.prompt || '',
        },
        condition: agentData.condition ? {
          field: agentData.condition.field,
          operator: agentData.condition.operator,
          value: agentData.condition.value,
        } : undefined,
        outputs: agentData.outputs,
        on_failure: mapOnFailure(agentData.onFailure),
        max_retries: agentData.maxRetries,
      };
    }

    case 'shell': {
      const shellData = data as ShellNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'shell',
        params: {
          command: shellData.command,
          allow_failure: shellData.allowFailure,
        },
        condition: shellData.condition ? {
          field: shellData.condition.field,
          operator: shellData.condition.operator,
          value: shellData.condition.value,
        } : undefined,
        timeout_seconds: shellData.timeout,
      };
    }

    case 'checkpoint': {
      const checkpointData = data as CheckpointNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'checkpoint',
        params: {
          message: checkpointData.message || checkpointData.name,
        },
      };
    }

    case 'parallel': {
      const parallelData = data as ParallelNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'parallel',
        params: {
          strategy: parallelData.strategy,
          max_workers: parallelData.maxWorkers,
          fail_fast: parallelData.failFast,
        },
      };
    }

    case 'fan_out': {
      const fanOutData = data as FanOutNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'fan_out',
        params: {
          items: fanOutData.itemsVariable ? `\${${fanOutData.itemsVariable}}` : undefined,
          max_concurrent: fanOutData.maxConcurrent,
          fail_fast: fanOutData.failFast,
        },
      };
    }

    case 'fan_in': {
      const fanInData = data as FanInNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'fan_in',
        params: {
          input: fanInData.inputVariable ? `\${${fanInData.inputVariable}}` : undefined,
          aggregation: fanInData.aggregation,
          aggregate_prompt: fanInData.aggregatePrompt,
        },
      };
    }

    case 'map_reduce': {
      const mapReduceData = data as MapReduceNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'map_reduce',
        params: {
          items: mapReduceData.itemsVariable ? `\${${mapReduceData.itemsVariable}}` : undefined,
          max_concurrent: mapReduceData.maxConcurrent,
          fail_fast: mapReduceData.failFast,
          map_prompt: mapReduceData.mapPrompt,
          reduce_prompt: mapReduceData.reducePrompt,
        },
      };
    }

    case 'branch': {
      const branchData = data as BranchNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'branch',
        condition: branchData.condition ? {
          field: branchData.condition.field,
          operator: branchData.condition.operator,
          value: branchData.condition.value,
        } : undefined,
        params: {
          true_label: branchData.trueLabel,
          false_label: branchData.falseLabel,
        },
      };
    }

    case 'loop': {
      const loopData = data as LoopNodeData;
      return {
        ...baseStep,
        id: node.id,
        type: 'loop',
        condition: loopData.condition ? {
          field: loopData.condition.field,
          operator: loopData.condition.operator,
          value: loopData.condition.value,
        } : undefined,
        params: {
          loop_type: loopData.loopType,
          max_iterations: loopData.maxIterations,
          iteration_variable: loopData.iterationVariable,
        },
      };
    }

    default:
      throw new Error(`Unknown node type: ${(data as WorkflowNodeData).type}`);
  }
}

/**
 * Map frontend onFailure to YAML on_failure.
 */
function mapOnFailure(onFailure?: 'stop' | 'continue' | 'retry'): 'abort' | 'skip' | 'retry' | undefined {
  switch (onFailure) {
    case 'stop':
      return 'abort';
    case 'continue':
      return 'skip';
    case 'retry':
      return 'retry';
    default:
      return undefined;
  }
}

/**
 * Topologically sort nodes based on edges (dependencies).
 * Returns nodes in execution order.
 */
function topologicalSort(nodes: Node<WorkflowNodeData>[], edges: Edge[]): Node<WorkflowNodeData>[] {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();

  // Initialize
  for (const node of nodes) {
    inDegree.set(node.id, 0);
    adjacency.set(node.id, []);
  }

  // Build graph
  for (const edge of edges) {
    if (nodeMap.has(edge.source) && nodeMap.has(edge.target)) {
      adjacency.get(edge.source)!.push(edge.target);
      inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
    }
  }

  // Kahn's algorithm
  const queue: string[] = [];
  for (const [id, degree] of inDegree) {
    if (degree === 0) queue.push(id);
  }

  const sorted: Node<WorkflowNodeData>[] = [];
  while (queue.length > 0) {
    // Sort by Y position for consistent ordering of parallel nodes
    queue.sort((a, b) => {
      const nodeA = nodeMap.get(a)!;
      const nodeB = nodeMap.get(b)!;
      return nodeA.position.y - nodeB.position.y;
    });

    const current = queue.shift()!;
    sorted.push(nodeMap.get(current)!);

    for (const neighbor of adjacency.get(current) || []) {
      const newDegree = (inDegree.get(neighbor) || 0) - 1;
      inDegree.set(neighbor, newDegree);
      if (newDegree === 0) {
        queue.push(neighbor);
      }
    }
  }

  // Check for cycles
  if (sorted.length !== nodes.length) {
    throw new Error('Workflow contains circular dependencies');
  }

  return sorted;
}

/**
 * Export ReactFlow state to YAML workflow object.
 */
export function exportToYaml(
  nodes: Node<WorkflowNodeData>[],
  edges: Edge[],
  workflowName: string,
  options?: {
    version?: string;
    description?: string;
    tokenBudget?: number;
    timeoutSeconds?: number;
  }
): YamlWorkflow {
  if (nodes.length === 0) {
    throw new Error('Workflow must have at least one step');
  }

  // Sort nodes topologically for correct execution order
  const sortedNodes = topologicalSort(nodes, edges);

  // Convert nodes to steps
  const steps = sortedNodes.map((node) => nodeToStep(node, edges));

  // Clean up undefined values
  const cleanSteps = steps.map((step) => {
    const cleaned: YamlStep = { id: step.id, type: step.type };
    if (step.params && Object.keys(step.params).length > 0) cleaned.params = step.params;
    if (step.condition) cleaned.condition = step.condition;
    if (step.on_failure) cleaned.on_failure = step.on_failure;
    if (step.max_retries !== undefined) cleaned.max_retries = step.max_retries;
    if (step.timeout_seconds !== undefined) cleaned.timeout_seconds = step.timeout_seconds;
    if (step.outputs && step.outputs.length > 0) cleaned.outputs = step.outputs;
    if (step.depends_on) cleaned.depends_on = step.depends_on;
    return cleaned;
  });

  return {
    name: workflowName || 'Untitled Workflow',
    version: options?.version || '1.0',
    description: options?.description,
    token_budget: options?.tokenBudget,
    timeout_seconds: options?.timeoutSeconds,
    steps: cleanSteps,
  };
}

/**
 * Serialize workflow to YAML string.
 */
export function serializeToYamlString(workflow: YamlWorkflow): string {
  // Manual YAML serialization for clean output
  const lines: string[] = [];

  lines.push(`name: ${workflow.name}`);
  if (workflow.version) lines.push(`version: "${workflow.version}"`);
  if (workflow.description) lines.push(`description: ${workflow.description}`);
  if (workflow.token_budget) lines.push(`token_budget: ${workflow.token_budget}`);
  if (workflow.timeout_seconds) lines.push(`timeout_seconds: ${workflow.timeout_seconds}`);

  lines.push('');
  lines.push('steps:');

  for (const step of workflow.steps) {
    lines.push(`  - id: ${step.id}`);
    lines.push(`    type: ${step.type}`);

    if (step.params && Object.keys(step.params).length > 0) {
      lines.push('    params:');
      for (const [key, value] of Object.entries(step.params)) {
        if (typeof value === 'string' && value.includes('\n')) {
          lines.push(`      ${key}: |`);
          for (const line of value.split('\n')) {
            lines.push(`        ${line}`);
          }
        } else if (typeof value === 'string') {
          lines.push(`      ${key}: "${value}"`);
        } else if (typeof value === 'boolean' || typeof value === 'number') {
          lines.push(`      ${key}: ${value}`);
        }
      }
    }

    if (step.outputs && step.outputs.length > 0) {
      lines.push('    outputs:');
      for (const output of step.outputs) {
        lines.push(`      - ${output}`);
      }
    }

    if (step.condition) {
      lines.push('    condition:');
      lines.push(`      field: "${step.condition.field}"`);
      lines.push(`      operator: ${step.condition.operator}`);
      if (typeof step.condition.value === 'string') {
        lines.push(`      value: "${step.condition.value}"`);
      } else {
        lines.push(`      value: ${step.condition.value}`);
      }
    }

    if (step.on_failure) lines.push(`    on_failure: ${step.on_failure}`);
    if (step.max_retries !== undefined) lines.push(`    max_retries: ${step.max_retries}`);
    if (step.timeout_seconds !== undefined) lines.push(`    timeout_seconds: ${step.timeout_seconds}`);

    if (step.depends_on) {
      if (Array.isArray(step.depends_on)) {
        lines.push('    depends_on:');
        for (const dep of step.depends_on) {
          lines.push(`      - ${dep}`);
        }
      } else {
        lines.push(`    depends_on: ${step.depends_on}`);
      }
    }

    lines.push('');
  }

  return lines.join('\n');
}

// =============================================================================
// Import: YAML → ReactFlow
// =============================================================================

const NODE_WIDTH = 280;
const NODE_HEIGHT = 120;
const HORIZONTAL_GAP = 100;
const VERTICAL_GAP = 60;

/**
 * Convert a YAML step to ReactFlow node data.
 */
function stepToNodeData(step: YamlStep): WorkflowNodeData {
  switch (step.type) {
    case 'claude_code': {
      const role = (step.params?.role as AgentRole) || 'planner';
      return {
        type: 'agent',
        role,
        name: step.id,
        prompt: step.params?.prompt as string,
        outputs: step.outputs,
        onFailure: mapOnFailureReverse(step.on_failure),
        maxRetries: step.max_retries,
        condition: step.condition ? {
          field: step.condition.field,
          operator: step.condition.operator,
          value: step.condition.value as string | number | boolean,
        } : undefined,
      } satisfies AgentNodeData;
    }

    case 'shell': {
      return {
        type: 'shell',
        name: step.id,
        command: (step.params?.command as string) || '',
        allowFailure: step.params?.allow_failure as boolean,
        timeout: step.timeout_seconds,
        condition: step.condition ? {
          field: step.condition.field,
          operator: step.condition.operator,
          value: step.condition.value as string | number | boolean,
        } : undefined,
      } satisfies ShellNodeData;
    }

    case 'checkpoint': {
      return {
        type: 'checkpoint',
        name: step.id,
        message: step.params?.message as string,
      } satisfies CheckpointNodeData;
    }

    case 'parallel': {
      return {
        type: 'parallel',
        name: step.id,
        strategy: step.params?.strategy as 'threading' | 'asyncio' | 'process',
        maxWorkers: step.params?.max_workers as number,
        failFast: step.params?.fail_fast as boolean,
      } satisfies ParallelNodeData;
    }

    case 'fan_out': {
      // Extract variable name from ${variable} format
      const itemsRaw = step.params?.items as string;
      const itemsVariable = itemsRaw?.match(/\$\{(\w+)\}/)?.[1] || itemsRaw;
      return {
        type: 'fan_out',
        name: step.id,
        itemsVariable,
        maxConcurrent: step.params?.max_concurrent as number,
        failFast: step.params?.fail_fast as boolean,
      } satisfies FanOutNodeData;
    }

    case 'fan_in': {
      const inputRaw = step.params?.input as string;
      const inputVariable = inputRaw?.match(/\$\{(\w+)\}/)?.[1] || inputRaw;
      return {
        type: 'fan_in',
        name: step.id,
        inputVariable,
        aggregation: step.params?.aggregation as 'concat' | 'claude_code',
        aggregatePrompt: step.params?.aggregate_prompt as string,
      } satisfies FanInNodeData;
    }

    case 'map_reduce': {
      const itemsRaw = step.params?.items as string;
      const itemsVariable = itemsRaw?.match(/\$\{(\w+)\}/)?.[1] || itemsRaw;
      return {
        type: 'map_reduce',
        name: step.id,
        itemsVariable,
        maxConcurrent: step.params?.max_concurrent as number,
        failFast: step.params?.fail_fast as boolean,
        mapPrompt: step.params?.map_prompt as string,
        reducePrompt: step.params?.reduce_prompt as string,
      } satisfies MapReduceNodeData;
    }

    case 'branch': {
      return {
        type: 'branch',
        name: step.id,
        condition: step.condition ? {
          field: step.condition.field,
          operator: step.condition.operator,
          value: step.condition.value as string | number | boolean,
        } : {
          field: 'result',
          operator: 'equals',
          value: true,
        },
        trueLabel: step.params?.true_label as string,
        falseLabel: step.params?.false_label as string,
      } satisfies BranchNodeData;
    }

    case 'loop': {
      return {
        type: 'loop',
        name: step.id,
        condition: step.condition ? {
          field: step.condition.field,
          operator: step.condition.operator,
          value: step.condition.value as string | number | boolean,
        } : undefined,
        loopType: step.params?.loop_type as 'while' | 'for' | 'until',
        maxIterations: step.params?.max_iterations as number,
        iterationVariable: step.params?.iteration_variable as string,
      } satisfies LoopNodeData;
    }

    // For truly unsupported types, create a shell node as placeholder
    case 'openai':
    default:
      return {
        type: 'shell',
        name: `${step.id} (${step.type})`,
        command: `# Unsupported step type: ${step.type}`,
        allowFailure: true,
      } satisfies ShellNodeData;
  }
}

/**
 * Map YAML on_failure to frontend onFailure.
 */
function mapOnFailureReverse(onFailure?: 'abort' | 'skip' | 'retry'): 'stop' | 'continue' | 'retry' | undefined {
  switch (onFailure) {
    case 'abort':
      return 'stop';
    case 'skip':
      return 'continue';
    case 'retry':
      return 'retry';
    default:
      return undefined;
  }
}

/**
 * Map node type string to ReactFlow node type.
 */
function getReactFlowNodeType(stepType: YamlStep['type']): string {
  switch (stepType) {
    case 'claude_code':
      return 'agent';
    case 'shell':
      return 'shell';
    case 'checkpoint':
      return 'checkpoint';
    case 'parallel':
      return 'parallel';
    case 'fan_out':
      return 'fan_out';
    case 'fan_in':
      return 'fan_in';
    case 'map_reduce':
      return 'map_reduce';
    case 'branch':
      return 'branch';
    case 'loop':
      return 'loop';
    default:
      return 'shell'; // Fallback for unsupported types
  }
}

/**
 * Calculate node positions using layered layout.
 * Groups nodes by their dependency level.
 */
function calculateNodePositions(
  steps: YamlStep[]
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const stepMap = new Map(steps.map((s) => [s.id, s]));

  // Build dependency graph
  const dependsOn = new Map<string, string[]>();
  for (const step of steps) {
    const deps = step.depends_on
      ? Array.isArray(step.depends_on)
        ? step.depends_on
        : [step.depends_on]
      : [];
    dependsOn.set(step.id, deps);
  }

  // Calculate levels (longest path from root)
  const levels = new Map<string, number>();

  function getLevel(stepId: string): number {
    if (levels.has(stepId)) return levels.get(stepId)!;

    const deps = dependsOn.get(stepId) || [];
    if (deps.length === 0) {
      levels.set(stepId, 0);
      return 0;
    }

    const maxDepLevel = Math.max(...deps.map((d) => (stepMap.has(d) ? getLevel(d) : -1)));
    const level = maxDepLevel + 1;
    levels.set(stepId, level);
    return level;
  }

  for (const step of steps) {
    getLevel(step.id);
  }

  // Group by level
  const levelGroups = new Map<number, string[]>();
  for (const [stepId, level] of levels) {
    if (!levelGroups.has(level)) levelGroups.set(level, []);
    levelGroups.get(level)!.push(stepId);
  }

  // Position nodes
  for (const [level, stepIds] of levelGroups) {
    const x = level * (NODE_WIDTH + HORIZONTAL_GAP) + 50;
    stepIds.forEach((stepId, index) => {
      const y = index * (NODE_HEIGHT + VERTICAL_GAP) + 50;
      positions.set(stepId, { x, y });
    });
  }

  return positions;
}

/**
 * Import YAML workflow to ReactFlow state.
 */
export function importFromYaml(workflow: YamlWorkflow): {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
} {
  const positions = calculateNodePositions(workflow.steps);

  const nodes: Node<WorkflowNodeData>[] = workflow.steps.map((step) => ({
    id: step.id,
    type: getReactFlowNodeType(step.type),
    position: positions.get(step.id) || { x: 0, y: 0 },
    data: stepToNodeData(step),
  }));

  const edges: Edge[] = [];
  for (const step of workflow.steps) {
    const deps = step.depends_on
      ? Array.isArray(step.depends_on)
        ? step.depends_on
        : [step.depends_on]
      : [];

    for (const dep of deps) {
      edges.push({
        id: `${dep}-${step.id}`,
        source: dep,
        target: step.id,
        type: 'default',
      });
    }
  }

  return { nodes, edges };
}

/**
 * Parse YAML string to workflow object.
 */
export function parseYamlString(yamlString: string): YamlWorkflow {
  const parsed = yaml.load(yamlString) as YamlWorkflow;
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Invalid YAML: expected an object');
  }
  if (!parsed.name) {
    throw new Error('Invalid workflow: missing required field "name"');
  }
  if (!parsed.steps || !Array.isArray(parsed.steps)) {
    throw new Error('Invalid workflow: missing required field "steps"');
  }
  return parsed;
}

/**
 * Serialize workflow to YAML string using js-yaml.
 */
export function toYamlString(workflow: YamlWorkflow): string {
  return yaml.dump(workflow, {
    indent: 2,
    lineWidth: 120,
    noRefs: true,
    sortKeys: false,
  });
}

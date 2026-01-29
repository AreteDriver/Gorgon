import { useCallback } from 'react';
import { useWorkflowBuilderStore } from '@/stores';
import type {
  ValidationError,
  ValidationResult,
  WorkflowNodeData,
  BranchNodeData,
  LoopNodeData,
} from '@/types/workflow-builder';
import { isBranchNode, isLoopNode } from '@/types/workflow-builder';
import type { Node, Edge } from '@xyflow/react';

export function useWorkflowValidation() {
  const { nodes, edges, setValidationErrors } = useWorkflowBuilderStore();

  const validate = useCallback((): ValidationResult => {
    const errors: ValidationError[] = [];

    // Check if workflow is empty
    if (nodes.length === 0) {
      errors.push({
        message: 'Workflow has no nodes. Add at least one agent.',
        severity: 'error',
      });
      setValidationErrors(errors);
      return { isValid: false, errors };
    }

    // Check each node
    nodes.forEach((node) => {
      const data = node.data;

      // Check for missing name
      if (!data.name || data.name.trim() === '') {
        errors.push({
          nodeId: node.id,
          field: 'name',
          message: `Node is missing a name`,
          severity: 'error',
        });
      }

      // Type-specific validations
      if (data.type === 'agent') {
        // Check for missing prompt (warning, not error)
        if (!data.prompt || data.prompt.trim() === '') {
          errors.push({
            nodeId: node.id,
            field: 'prompt',
            message: `"${data.name || 'Unnamed node'}" has no prompt defined`,
            severity: 'warning',
          });
        }
      }

      if (data.type === 'shell') {
        // Check for missing command (error)
        if (!data.command || data.command.trim() === '') {
          errors.push({
            nodeId: node.id,
            field: 'command',
            message: `"${data.name || 'Shell node'}" has no command defined`,
            severity: 'error',
          });
        }
      }

      // Branch node validations
      const nodeData = data as WorkflowNodeData;
      if (isBranchNode(nodeData)) {
        const branchData = nodeData as BranchNodeData;
        // Warning if condition.field is empty
        if (!branchData.condition?.field || branchData.condition.field.trim() === '') {
          errors.push({
            nodeId: node.id,
            field: 'condition.field',
            message: `"${branchData.name || 'Branch node'}" has no condition field defined`,
            severity: 'warning',
          });
        }

        // Error if branch node has no outgoing edges
        const hasOutgoingEdges = edges.some((edge) => edge.source === node.id);
        if (!hasOutgoingEdges) {
          errors.push({
            nodeId: node.id,
            message: `"${branchData.name || 'Branch node'}" has no outgoing connections. Branch nodes need at least one connection.`,
            severity: 'error',
          });
        }
      }

      // Loop node validations
      if (isLoopNode(nodeData)) {
        const loopData = nodeData as LoopNodeData;
        // Warning if maxIterations > 100 (potential performance issue)
        if (loopData.maxIterations !== undefined && loopData.maxIterations > 100) {
          errors.push({
            nodeId: node.id,
            field: 'maxIterations',
            message: `"${loopData.name || 'Loop node'}" has maxIterations set to ${loopData.maxIterations}. Values over 100 may cause performance issues.`,
            severity: 'warning',
          });
        }

        // Error if loopType is 'while' or 'until' but condition is missing/empty
        if (loopData.loopType === 'while' || loopData.loopType === 'until') {
          const hasValidCondition =
            loopData.condition &&
            loopData.condition.field &&
            loopData.condition.field.trim() !== '';

          if (!hasValidCondition) {
            errors.push({
              nodeId: node.id,
              field: 'condition',
              message: `"${loopData.name || 'Loop node'}" uses '${loopData.loopType}' loop type but has no condition defined`,
              severity: 'error',
            });
          }
        }
      }
    });

    // Check for unconnected nodes (nodes with no edges)
    const connectedNodeIds = new Set<string>();
    edges.forEach((edge) => {
      connectedNodeIds.add(edge.source);
      connectedNodeIds.add(edge.target);
    });

    // If there's more than one node, check connectivity
    if (nodes.length > 1) {
      nodes.forEach((node) => {
        if (!connectedNodeIds.has(node.id)) {
          errors.push({
            nodeId: node.id,
            message: `"${node.data.name || 'Unnamed node'}" is not connected to any other node`,
            severity: 'warning',
          });
        }
      });

      // Check for nodes with no incoming edges (potential start nodes)
      const nodesWithIncoming = new Set(edges.map((e) => e.target));
      const startNodes = nodes.filter((n) => !nodesWithIncoming.has(n.id));

      if (startNodes.length > 1) {
        errors.push({
          message: `Workflow has ${startNodes.length} start nodes. Consider connecting them to create a single entry point.`,
          severity: 'warning',
        });
      }

      // Check for nodes with no outgoing edges (potential end nodes)
      const nodesWithOutgoing = new Set(edges.map((e) => e.source));
      const endNodes = nodes.filter((n) => !nodesWithOutgoing.has(n.id));

      if (endNodes.length > 1) {
        errors.push({
          message: `Workflow has ${endNodes.length} end nodes. This may cause parallel execution paths.`,
          severity: 'warning',
        });
      }
    }

    // Check for cycles using DFS
    const hasCycle = detectCycle(nodes, edges);
    if (hasCycle) {
      errors.push({
        message: 'Workflow contains a cycle. This may cause infinite loops.',
        severity: 'error',
      });
    }

    setValidationErrors(errors);

    const hasErrors = errors.some((e) => e.severity === 'error');
    return { isValid: !hasErrors, errors };
  }, [nodes, edges, setValidationErrors]);

  const clearValidation = useCallback(() => {
    setValidationErrors([]);
  }, [setValidationErrors]);

  return { validate, clearValidation };
}

// Detect cycles using DFS
function detectCycle(nodes: Node[], edges: Edge[]): boolean {
  const adjacencyList = new Map<string, string[]>();

  // Build adjacency list
  nodes.forEach((node) => {
    adjacencyList.set(node.id, []);
  });

  edges.forEach((edge) => {
    const neighbors = adjacencyList.get(edge.source);
    if (neighbors) {
      neighbors.push(edge.target);
    }
  });

  const visited = new Set<string>();
  const recursionStack = new Set<string>();

  function dfs(nodeId: string): boolean {
    visited.add(nodeId);
    recursionStack.add(nodeId);

    const neighbors = adjacencyList.get(nodeId) || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        if (dfs(neighbor)) {
          return true;
        }
      } else if (recursionStack.has(neighbor)) {
        return true;
      }
    }

    recursionStack.delete(nodeId);
    return false;
  }

  for (const node of nodes) {
    if (!visited.has(node.id)) {
      if (dfs(node.id)) {
        return true;
      }
    }
  }

  return false;
}

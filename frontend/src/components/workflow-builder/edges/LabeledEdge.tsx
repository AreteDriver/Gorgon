import { memo } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from '@xyflow/react';
import { useWorkflowBuilderStore } from '@/stores';
import type {
  WorkflowNodeData,
  BranchNodeData,
  LoopNodeData,
} from '@/types/workflow-builder';

/**
 * Edge configuration for labeled connections.
 * Returns label text and styling based on source node type and handle.
 */
interface EdgeLabelConfig {
  label: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
}

function getEdgeLabelConfig(
  sourceData: WorkflowNodeData | undefined,
  sourceHandle: string | null | undefined
): EdgeLabelConfig | null {
  if (!sourceData || !sourceHandle) return null;

  // Branch node: true/false handles
  if (sourceData.type === 'branch') {
    const branchData = sourceData as BranchNodeData;
    if (sourceHandle === 'true') {
      return {
        label: branchData.trueLabel || 'Yes',
        bgColor: 'bg-green-100 dark:bg-green-900/50',
        textColor: 'text-green-700 dark:text-green-300',
        borderColor: 'border-green-300 dark:border-green-700',
      };
    }
    if (sourceHandle === 'false') {
      return {
        label: branchData.falseLabel || 'No',
        bgColor: 'bg-red-100 dark:bg-red-900/50',
        textColor: 'text-red-700 dark:text-red-300',
        borderColor: 'border-red-300 dark:border-red-700',
      };
    }
  }

  // Loop node: body/exit handles
  if (sourceData.type === 'loop') {
    // Cast to LoopNodeData for future extensibility (e.g., custom labels)
    void (sourceData as LoopNodeData);
    if (sourceHandle === 'body') {
      return {
        label: 'body',
        bgColor: 'bg-emerald-100 dark:bg-emerald-900/50',
        textColor: 'text-emerald-700 dark:text-emerald-300',
        borderColor: 'border-emerald-300 dark:border-emerald-700',
      };
    }
    if (sourceHandle === 'exit') {
      return {
        label: 'exit',
        bgColor: 'bg-slate-100 dark:bg-slate-800',
        textColor: 'text-slate-700 dark:text-slate-300',
        borderColor: 'border-slate-300 dark:border-slate-600',
      };
    }
  }

  return null;
}

/**
 * Custom edge that displays labels for branch and loop node connections.
 * - Branch nodes: Shows "Yes"/"No" (or custom trueLabel/falseLabel) for true/false handles
 * - Loop nodes: Shows "body" for bottom edge, "exit" for right edge
 * - Other nodes: Shows variable names flowing between nodes (like VariableEdge)
 */
function LabeledEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  source,
  sourceHandleId,
}: EdgeProps) {
  const { nodes } = useWorkflowBuilderStore();

  // Get the source node to find its type and data
  const sourceNode = nodes.find((n) => n.id === source);
  const sourceData = sourceNode?.data as WorkflowNodeData | undefined;

  // Get label configuration based on node type and handle
  const labelConfig = getEdgeLabelConfig(sourceData, sourceHandleId);

  // Determine edge stroke color based on label config
  let strokeColor = '#94a3b8'; // Default slate color
  if (labelConfig) {
    if (sourceHandleId === 'true') strokeColor = '#22c55e'; // green-500
    else if (sourceHandleId === 'false') strokeColor = '#ef4444'; // red-500
    else if (sourceHandleId === 'body') strokeColor = '#10b981'; // emerald-500
    else if (sourceHandleId === 'exit') strokeColor = '#64748b'; // slate-500
  } else if (sourceData) {
    // For non-labeled edges, use indigo if it has outputs (like VariableEdge)
    if ('outputs' in sourceData && Array.isArray(sourceData.outputs) && sourceData.outputs.length > 0) {
      strokeColor = '#6366f1'; // indigo-500
    }
  }

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  // For edges without labels, fall back to showing variable outputs (like VariableEdge)
  if (!labelConfig) {
    let outputs: string[] = [];
    if (sourceData) {
      if ('outputs' in sourceData && Array.isArray(sourceData.outputs)) {
        outputs = sourceData.outputs;
      }
      // For nodes without explicit outputs, use the node ID as the output
      if (outputs.length === 0 && sourceData.type !== 'branch' && sourceData.type !== 'loop') {
        outputs = [source];
      }
    }

    return (
      <>
        <BaseEdge
          id={id}
          path={edgePath}
          markerEnd={markerEnd}
          style={{
            ...style,
            strokeWidth: 2,
            stroke: strokeColor,
          }}
        />
        {outputs.length > 0 && (
          <EdgeLabelRenderer>
            <div
              style={{
                position: 'absolute',
                transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
                pointerEvents: 'all',
              }}
              className="nodrag nopan"
            >
              <div className="flex flex-wrap gap-1 max-w-[150px] justify-center">
                {outputs.slice(0, 3).map((output) => (
                  <span
                    key={output}
                    className="inline-flex items-center rounded-full bg-indigo-100 dark:bg-indigo-900/50 px-2 py-0.5 text-[10px] font-medium text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-700"
                  >
                    ${'{'}
                    {output}
                    {'}'}
                  </span>
                ))}
                {outputs.length > 3 && (
                  <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                    +{outputs.length - 3}
                  </span>
                )}
              </div>
            </div>
          </EdgeLabelRenderer>
        )}
      </>
    );
  }

  // Render labeled edge for branch/loop nodes
  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          strokeWidth: 2,
          stroke: strokeColor,
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan"
        >
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold border ${labelConfig.bgColor} ${labelConfig.textColor} ${labelConfig.borderColor}`}
          >
            {labelConfig.label}
          </span>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

export const LabeledEdge = memo(LabeledEdgeComponent);

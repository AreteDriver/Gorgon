import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { WorkflowCanvas } from './WorkflowCanvas';
import { useWorkflowBuilderStore } from '@/stores';
import type { Node, Edge } from '@xyflow/react';
import type { AgentNodeData } from '@/types/workflow-builder';

// Mock ReactFlow since it requires browser APIs
vi.mock('@xyflow/react', async () => {
  const actual = await vi.importActual('@xyflow/react');
  return {
    ...actual,
    ReactFlow: ({ nodes, edges, children }: { nodes: Node[]; edges: Edge[]; children?: React.ReactNode }) => (
      <div data-testid="react-flow" data-nodes={nodes.length} data-edges={edges.length}>
        <div data-testid="nodes">{nodes.map(n => <div key={n.id} data-testid={`node-${n.id}`}>{n.id}</div>)}</div>
        <div data-testid="edges">{edges.map(e => <div key={e.id} data-testid={`edge-${e.id}`}>{e.id}</div>)}</div>
        {children}
      </div>
    ),
    Background: () => <div data-testid="background" />,
    Controls: () => <div data-testid="controls" />,
    MiniMap: () => <div data-testid="minimap" />,
    BackgroundVariant: { Dots: 'dots' },
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  };
});

describe('WorkflowCanvas', () => {
  beforeEach(() => {
    // Reset store state before each test
    useWorkflowBuilderStore.getState().clearWorkflow();
  });

  it('renders the canvas with ReactFlow components', () => {
    render(<WorkflowCanvas />);

    expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    expect(screen.getByTestId('background')).toBeInTheDocument();
    expect(screen.getByTestId('controls')).toBeInTheDocument();
    expect(screen.getByTestId('minimap')).toBeInTheDocument();
  });

  it('renders empty canvas when no nodes exist', () => {
    render(<WorkflowCanvas />);

    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '0');
    expect(flow).toHaveAttribute('data-edges', '0');
  });

  it('renders nodes from the store', () => {
    const nodeData: AgentNodeData = {
      type: 'agent',
      role: 'planner',
      name: 'Test Planner',
      onFailure: 'stop',
    };

    // Add a node to the store
    useWorkflowBuilderStore.getState().addNode('agent', { x: 100, y: 100 }, nodeData);

    render(<WorkflowCanvas />);

    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '1');
  });

  it('renders multiple nodes', () => {
    const plannerData: AgentNodeData = {
      type: 'agent',
      role: 'planner',
      name: 'Planner',
      onFailure: 'stop',
    };
    const builderData: AgentNodeData = {
      type: 'agent',
      role: 'builder',
      name: 'Builder',
      onFailure: 'stop',
    };

    useWorkflowBuilderStore.getState().addNode('agent', { x: 100, y: 100 }, plannerData);
    useWorkflowBuilderStore.getState().addNode('agent', { x: 300, y: 100 }, builderData);

    render(<WorkflowCanvas />);

    const flow = screen.getByTestId('react-flow');
    expect(flow).toHaveAttribute('data-nodes', '2');
  });
});

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PropertyPanel } from './PropertyPanel';
import { useWorkflowBuilderStore } from '@/stores';
import type { AgentNodeData, ShellNodeData, CheckpointNodeData } from '@/types/workflow-builder';

describe('PropertyPanel', () => {
  beforeEach(() => {
    // Reset store state before each test
    useWorkflowBuilderStore.getState().clearWorkflow();
  });

  it('renders placeholder text when no node is selected', () => {
    render(<PropertyPanel />);

    expect(screen.getByText('Select a node to edit its properties')).toBeInTheDocument();
  });

  it('renders agent properties when an agent node is selected', () => {
    const nodeData: AgentNodeData = {
      type: 'agent',
      role: 'planner',
      name: 'Test Planner',
      onFailure: 'stop',
    };

    const nodeId = useWorkflowBuilderStore.getState().addNode('agent', { x: 100, y: 100 }, nodeData);
    useWorkflowBuilderStore.getState().selectNode(nodeId);

    render(<PropertyPanel />);

    // Check that agent-specific fields are present
    expect(screen.getByText('Planner Properties')).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Agent Role')).toBeInTheDocument();
    expect(screen.getByLabelText('Prompt')).toBeInTheDocument();
    expect(screen.getByLabelText('On Failure')).toBeInTheDocument();
  });

  it('renders shell properties when a shell node is selected', () => {
    const nodeData: ShellNodeData = {
      type: 'shell',
      name: 'Run Tests',
      command: 'npm test',
      allowFailure: false,
    };

    const nodeId = useWorkflowBuilderStore.getState().addNode('shell', { x: 100, y: 100 }, nodeData);
    useWorkflowBuilderStore.getState().selectNode(nodeId);

    render(<PropertyPanel />);

    expect(screen.getByText('Shell Command')).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Command')).toBeInTheDocument();
    expect(screen.getByLabelText('Allow Failure')).toBeInTheDocument();
    expect(screen.getByLabelText('Timeout (seconds)')).toBeInTheDocument();
  });

  it('renders checkpoint properties when a checkpoint node is selected', () => {
    const nodeData: CheckpointNodeData = {
      type: 'checkpoint',
      name: 'Review Point',
      message: 'Please review before continuing',
    };

    const nodeId = useWorkflowBuilderStore.getState().addNode('checkpoint', { x: 100, y: 100 }, nodeData);
    useWorkflowBuilderStore.getState().selectNode(nodeId);

    render(<PropertyPanel />);

    expect(screen.getByText('Checkpoint')).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Pause Message')).toBeInTheDocument();
  });

  it('updates node name when input changes', () => {
    const nodeData: AgentNodeData = {
      type: 'agent',
      role: 'planner',
      name: 'Original Name',
      onFailure: 'stop',
    };

    const nodeId = useWorkflowBuilderStore.getState().addNode('agent', { x: 100, y: 100 }, nodeData);
    useWorkflowBuilderStore.getState().selectNode(nodeId);

    render(<PropertyPanel />);

    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'New Name' } });

    // Verify store was updated
    const updatedNode = useWorkflowBuilderStore.getState().nodes.find(n => n.id === nodeId);
    expect(updatedNode?.data.name).toBe('New Name');
  });

  it('deletes node when delete button is clicked', () => {
    const nodeData: AgentNodeData = {
      type: 'agent',
      role: 'planner',
      name: 'To Delete',
      onFailure: 'stop',
    };

    const nodeId = useWorkflowBuilderStore.getState().addNode('agent', { x: 100, y: 100 }, nodeData);
    useWorkflowBuilderStore.getState().selectNode(nodeId);

    render(<PropertyPanel />);

    const deleteButton = screen.getByRole('button', { name: /delete node/i });
    fireEvent.click(deleteButton);

    // Verify node was deleted
    expect(useWorkflowBuilderStore.getState().nodes).toHaveLength(0);
    expect(useWorkflowBuilderStore.getState().selectedNodeId).toBeNull();
  });

  it('closes panel when close button is clicked', () => {
    const nodeData: AgentNodeData = {
      type: 'agent',
      role: 'planner',
      name: 'Test',
      onFailure: 'stop',
    };

    const nodeId = useWorkflowBuilderStore.getState().addNode('agent', { x: 100, y: 100 }, nodeData);
    useWorkflowBuilderStore.getState().selectNode(nodeId);

    render(<PropertyPanel />);

    // Find and click the close button (X icon)
    const closeButtons = screen.getAllByRole('button');
    const closeButton = closeButtons.find(btn => btn.querySelector('svg.lucide-x'));
    expect(closeButton).toBeDefined();
    if (closeButton) {
      fireEvent.click(closeButton);
    }

    // Verify selection was cleared
    expect(useWorkflowBuilderStore.getState().selectedNodeId).toBeNull();
  });
});

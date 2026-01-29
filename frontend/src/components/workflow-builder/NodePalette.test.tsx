import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NodePalette } from './NodePalette';

describe('NodePalette', () => {
  it('renders the Agents section', () => {
    render(<NodePalette />);

    expect(screen.getByText('Agents')).toBeInTheDocument();
    expect(screen.getByText('Drag to add to canvas')).toBeInTheDocument();
  });

  it('renders all agent roles', () => {
    render(<NodePalette />);

    // Check that all agent roles are present
    expect(screen.getByText('Planner')).toBeInTheDocument();
    expect(screen.getByText('Builder')).toBeInTheDocument();
    expect(screen.getByText('Tester')).toBeInTheDocument();
    expect(screen.getByText('Reviewer')).toBeInTheDocument();
    expect(screen.getByText('Architect')).toBeInTheDocument();
    expect(screen.getByText('Documenter')).toBeInTheDocument();
    expect(screen.getByText('Analyst')).toBeInTheDocument();
    expect(screen.getByText('Visualizer')).toBeInTheDocument();
    expect(screen.getByText('Reporter')).toBeInTheDocument();
  });

  it('renders the Parallel section', () => {
    render(<NodePalette />);

    expect(screen.getByText('Parallel')).toBeInTheDocument();
    expect(screen.getByText('Concurrent execution')).toBeInTheDocument();
  });

  it('renders parallel node types', () => {
    render(<NodePalette />);

    expect(screen.getByText('Parallel Group')).toBeInTheDocument();
    expect(screen.getByText('Fan Out')).toBeInTheDocument();
    expect(screen.getByText('Fan In')).toBeInTheDocument();
    expect(screen.getByText('Map-Reduce')).toBeInTheDocument();
  });

  it('renders the Utilities section', () => {
    render(<NodePalette />);

    expect(screen.getByText('Utilities')).toBeInTheDocument();
    expect(screen.getByText('Commands & control flow')).toBeInTheDocument();
  });

  it('renders utility node types', () => {
    render(<NodePalette />);

    expect(screen.getByText('Shell Command')).toBeInTheDocument();
    expect(screen.getByText('Checkpoint')).toBeInTheDocument();
    expect(screen.getByText('Branch')).toBeInTheDocument();
    expect(screen.getByText('Loop')).toBeInTheDocument();
  });

  it('renders descriptions for agent roles', () => {
    render(<NodePalette />);

    expect(screen.getByText('Breaks features into actionable steps')).toBeInTheDocument();
    expect(screen.getByText('Writes production-ready code')).toBeInTheDocument();
    expect(screen.getByText('Creates comprehensive test suites')).toBeInTheDocument();
  });

  it('makes palette items draggable', () => {
    render(<NodePalette />);

    // Find a draggable element - the Planner item
    const plannerItem = screen.getByText('Planner').closest('[draggable="true"]');
    expect(plannerItem).toBeDefined();
    expect(plannerItem).toHaveAttribute('draggable', 'true');
  });

  it('sets correct dataTransfer on drag start for agent node', () => {
    render(<NodePalette />);

    const plannerItem = screen.getByText('Planner').closest('[draggable="true"]')!;

    // Create a mock dataTransfer object
    const mockDataTransfer = {
      setData: vi.fn(),
      effectAllowed: '',
    };

    fireEvent.dragStart(plannerItem, {
      dataTransfer: mockDataTransfer,
    });

    expect(mockDataTransfer.setData).toHaveBeenCalledWith('application/reactflow', 'planner');
    expect(mockDataTransfer.setData).toHaveBeenCalledWith('application/reactflow-type', 'agent');
  });

  it('sets correct dataTransfer on drag start for utility node', () => {
    render(<NodePalette />);

    const shellItem = screen.getByText('Shell Command').closest('[draggable="true"]')!;

    const mockDataTransfer = {
      setData: vi.fn(),
      effectAllowed: '',
    };

    fireEvent.dragStart(shellItem, {
      dataTransfer: mockDataTransfer,
    });

    expect(mockDataTransfer.setData).toHaveBeenCalledWith('application/reactflow', 'shell');
    expect(mockDataTransfer.setData).toHaveBeenCalledWith('application/reactflow-type', 'shell');
  });
});

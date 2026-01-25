import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AgentRole, Execution } from '@/types';
import type { WorkflowNodeData, ValidationError } from '@/types/workflow-builder';
import type { Node, Edge, Connection } from '@xyflow/react';
import { applyNodeChanges, applyEdgeChanges, addEdge, type NodeChange, type EdgeChange } from '@xyflow/react';

// =============================================================================
// UI Store - Transient UI state
// =============================================================================

interface UIState {
  sidebarOpen: boolean;
  activeExecution: string | null;
  selectedAgents: AgentRole[];
  logLevel: 'all' | 'info' | 'warn' | 'error';
  
  // Actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setActiveExecution: (id: string | null) => void;
  toggleAgentFilter: (agent: AgentRole) => void;
  clearAgentFilters: () => void;
  setLogLevel: (level: 'all' | 'info' | 'warn' | 'error') => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  activeExecution: null,
  selectedAgents: [],
  logLevel: 'all',

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setActiveExecution: (id) => set({ activeExecution: id }),
  
  toggleAgentFilter: (agent) =>
    set((state) => ({
      selectedAgents: state.selectedAgents.includes(agent)
        ? state.selectedAgents.filter((a) => a !== agent)
        : [...state.selectedAgents, agent],
    })),
  
  clearAgentFilters: () => set({ selectedAgents: [] }),
  setLogLevel: (level) => set({ logLevel: level }),
}));

// =============================================================================
// Preferences Store - Persisted user preferences
// =============================================================================

interface PreferencesState {
  theme: 'light' | 'dark' | 'system';
  compactView: boolean;
  showCosts: boolean;
  defaultPageSize: number;
  notifications: {
    executionComplete: boolean;
    executionFailed: boolean;
    budgetAlert: boolean;
  };
  
  // Actions
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  setCompactView: (compact: boolean) => void;
  setShowCosts: (show: boolean) => void;
  setDefaultPageSize: (size: number) => void;
  setNotification: (key: keyof PreferencesState['notifications'], value: boolean) => void;
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      theme: 'system',
      compactView: false,
      showCosts: true,
      defaultPageSize: 20,
      notifications: {
        executionComplete: true,
        executionFailed: true,
        budgetAlert: true,
      },

      setTheme: (theme) => set({ theme }),
      setCompactView: (compactView) => set({ compactView }),
      setShowCosts: (showCosts) => set({ showCosts }),
      setDefaultPageSize: (defaultPageSize) => set({ defaultPageSize }),
      setNotification: (key, value) =>
        set((state) => ({
          notifications: { ...state.notifications, [key]: value },
        })),
    }),
    {
      name: 'gorgon-preferences',
    }
  )
);

// =============================================================================
// Workflow Builder Store - State for visual workflow editor (ReactFlow)
// =============================================================================

interface WorkflowBuilderState {
  // ReactFlow state
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  viewport: { x: number; y: number; zoom: number };

  // Selection state
  selectedNodeId: string | null;

  // Editor state
  isDirty: boolean;
  workflowId: string | null;
  workflowName: string;

  // Validation state
  validationErrors: ValidationError[];

  // ReactFlow handlers
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;

  // Node actions
  addNode: (type: string, position: { x: number; y: number }, data: WorkflowNodeData) => string;
  updateNodeData: (id: string, data: Partial<WorkflowNodeData>) => void;
  deleteNode: (id: string) => void;
  selectNode: (id: string | null) => void;

  // Workflow actions
  setWorkflowName: (name: string) => void;
  loadWorkflow: (id: string, name: string, nodes: Node<WorkflowNodeData>[], edges: Edge[]) => void;
  clearWorkflow: () => void;
  markClean: () => void;

  // Validation
  setValidationErrors: (errors: ValidationError[]) => void;

  // Viewport
  setViewport: (viewport: { x: number; y: number; zoom: number }) => void;
}

export const useWorkflowBuilderStore = create<WorkflowBuilderState>((set) => ({
  nodes: [],
  edges: [],
  viewport: { x: 0, y: 0, zoom: 1 },
  selectedNodeId: null,
  isDirty: false,
  workflowId: null,
  workflowName: 'Untitled Workflow',
  validationErrors: [],

  onNodesChange: (changes) =>
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes) as Node<WorkflowNodeData>[],
      isDirty: true,
    })),

  onEdgesChange: (changes) =>
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
      isDirty: true,
    })),

  onConnect: (connection) =>
    set((state) => ({
      edges: addEdge({ ...connection, type: 'default' }, state.edges),
      isDirty: true,
    })),

  addNode: (type, position, data) => {
    const id = crypto.randomUUID();
    set((state) => ({
      nodes: [
        ...state.nodes,
        {
          id,
          type,
          position,
          data,
        },
      ],
      isDirty: true,
    }));
    return id;
  },

  updateNodeData: (id, data) =>
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === id ? { ...node, data: { ...node.data, ...data } as WorkflowNodeData } : node
      ),
      isDirty: true,
    })),

  deleteNode: (id) =>
    set((state) => ({
      nodes: state.nodes.filter((node) => node.id !== id),
      edges: state.edges.filter((edge) => edge.source !== id && edge.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
      isDirty: true,
    })),

  selectNode: (id) => set({ selectedNodeId: id }),

  setWorkflowName: (name) => set({ workflowName: name, isDirty: true }),

  loadWorkflow: (id, name, nodes, edges) =>
    set({
      workflowId: id,
      workflowName: name,
      nodes,
      edges,
      selectedNodeId: null,
      isDirty: false,
      validationErrors: [],
    }),

  clearWorkflow: () =>
    set({
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selectedNodeId: null,
      isDirty: false,
      workflowId: null,
      workflowName: 'Untitled Workflow',
      validationErrors: [],
    }),

  markClean: () => set({ isDirty: false }),

  setValidationErrors: (errors) => set({ validationErrors: errors }),

  setViewport: (viewport) => set({ viewport }),
}));

// =============================================================================
// Live Execution Store - Real-time execution monitoring
// =============================================================================

interface LiveExecutionState {
  executions: Map<string, Execution>;
  
  // Actions
  setExecution: (execution: Execution) => void;
  removeExecution: (id: string) => void;
  clearExecutions: () => void;
}

export const useLiveExecutionStore = create<LiveExecutionState>((set) => ({
  executions: new Map(),

  setExecution: (execution) =>
    set((state) => {
      const newExecutions = new Map(state.executions);
      newExecutions.set(execution.id, execution);
      return { executions: newExecutions };
    }),

  removeExecution: (id) =>
    set((state) => {
      const newExecutions = new Map(state.executions);
      newExecutions.delete(id);
      return { executions: newExecutions };
    }),

  clearExecutions: () => set({ executions: new Map() }),
}));

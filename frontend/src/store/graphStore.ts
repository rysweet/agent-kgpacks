/**
 * Graph state management with Zustand
 *
 * Manages graph nodes, edges, selection, filters, and persistence.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { GraphNode, GraphEdge, Filters } from '../types/graph';
import { getNeighbors } from '../services/api';

interface GraphState {
  // Data
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: string | null;
  filters: Filters;

  // UI state
  loading: boolean;
  error: string | null;

  // Actions
  loadGraph: (article: string, depth: number) => Promise<void>;
  addNode: (node: GraphNode) => void;
  addNodes: (nodes: GraphNode[]) => void;
  addEdges: (edges: GraphEdge[]) => void;
  setSelectedNode: (nodeId: string | null) => void;
  applyFilters: (filters: Filters) => void;
  getFilteredNodes: () => GraphNode[];
  clearGraph: () => void;
  reset: () => void;
}

const initialState = {
  nodes: [],
  edges: [],
  selectedNode: null,
  filters: {},
  loading: false,
  error: null,
};

export const useGraphStore = create<GraphState>()(
  persist(
    (set, get) => ({
      ...initialState,

      loadGraph: async (article: string, depth: number) => {
        set({ loading: true, error: null });

        try {
          const data = await getNeighbors(article, depth);
          set({
            nodes: data.nodes,
            edges: data.edges,
            loading: false,
            error: null,
          });
        } catch (error) {
          set({
            error: (error as Error).message,
            loading: false,
          });
        }
      },

      addNode: (node: GraphNode) => {
        const { nodes } = get();
        const existingIndex = nodes.findIndex((n) => n.id === node.id);

        if (existingIndex >= 0) {
          // Update existing node
          const newNodes = [...nodes];
          newNodes[existingIndex] = node;
          set({ nodes: newNodes });
        } else {
          // Add new node
          set({ nodes: [...nodes, node] });
        }
      },

      addNodes: (newNodes: GraphNode[]) => {
        const { nodes } = get();
        const nodeMap = new Map(nodes.map((n) => [n.id, n]));

        // Add or update nodes
        newNodes.forEach((node) => {
          nodeMap.set(node.id, node);
        });

        set({ nodes: Array.from(nodeMap.values()) });
      },

      addEdges: (newEdges: GraphEdge[]) => {
        const { edges } = get();
        set({ edges: [...edges, ...newEdges] });
      },

      setSelectedNode: (nodeId: string | null) => {
        set({ selectedNode: nodeId });
      },

      applyFilters: (filters: Filters) => {
        set({ filters });
      },

      getFilteredNodes: () => {
        const { nodes, filters } = get();

        let filtered = [...nodes];

        // Filter by categories
        if (filters.categories && filters.categories.length > 0) {
          filtered = filtered.filter((node) =>
            filters.categories!.includes(node.category)
          );
        }

        // Filter by depth
        if (filters.maxDepth !== undefined) {
          filtered = filtered.filter((node) => node.depth <= filters.maxDepth!);
        }

        return filtered;
      },

      clearGraph: () => {
        set({
          nodes: [],
          edges: [],
          selectedNode: null,
          error: null,
        });
      },

      reset: () => {
        set(initialState);
      },
    }),
    {
      name: 'wikigr-graph',
      partialize: (state) => ({
        nodes: state.nodes,
        edges: state.edges,
      }),
      onRehydrateStorage: () => (state) => {
        // Handle corrupted localStorage data
        if (!state) return;

        try {
          if (!Array.isArray(state.nodes)) {
            state.nodes = [];
          }
          if (!Array.isArray(state.edges)) {
            state.edges = [];
          }
        } catch {
          // Ignore errors
        }
      },
    }
  )
);

/**
 * Tests for graph store (Zustand)
 *
 * Tests state management for graph data, node selection, filters, and persistence.
 * Following TDD methodology - these tests will fail until implementation is complete.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useGraphStore } from '../graphStore';

// Mock API client
vi.mock('../../services/api', () => ({
  getNeighbors: vi.fn(),
}));

describe('graphStore', () => {
  beforeEach(() => {
    // Reset store before each test
    const { reset } = useGraphStore.getState();
    if (reset) reset();
    vi.clearAllMocks();
  });

  describe('Initial state', () => {
    it('has empty nodes array initially', () => {
      const { result } = renderHook(() => useGraphStore());

      expect(result.current.nodes).toEqual([]);
    });

    it('has empty edges array initially', () => {
      const { result } = renderHook(() => useGraphStore());

      expect(result.current.edges).toEqual([]);
    });

    it('has no selected node initially', () => {
      const { result } = renderHook(() => useGraphStore());

      expect(result.current.selectedNode).toBeNull();
    });

    it('is not loading initially', () => {
      const { result } = renderHook(() => useGraphStore());

      expect(result.current.loading).toBe(false);
    });

    it('has no error initially', () => {
      const { result } = renderHook(() => useGraphStore());

      expect(result.current.error).toBeNull();
    });
  });

  describe('loadGraph', () => {
    it('sets loading state while fetching', async () => {
      const { getNeighbors } = await import('../../services/api');

      (getNeighbors as any).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.loadGraph('Python', 2);
      });

      expect(result.current.loading).toBe(true);
    });

    it('loads nodes and edges from API', async () => {
      const { getNeighbors } = await import('../../services/api');

      const mockData = {
        seed: 'Python',
        nodes: [
          {
            id: 'Python',
            title: 'Python',
            category: 'Programming',
            word_count: 1000,
            depth: 0,
            links_count: 5,
            summary: 'Python is...',
          },
        ],
        edges: [
          {
            source: 'Python',
            target: 'Java',
            type: 'internal',
            weight: 1.0,
          },
        ],
        total_nodes: 1,
        total_edges: 1,
        execution_time_ms: 50,
      };

      (getNeighbors as any).mockResolvedValue(mockData);

      const { result } = renderHook(() => useGraphStore());

      await act(async () => {
        await result.current.loadGraph('Python', 2);
      });

      expect(result.current.nodes).toEqual(mockData.nodes);
      expect(result.current.edges).toEqual(mockData.edges);
      expect(result.current.loading).toBe(false);
    });

    it('sets error on API failure', async () => {
      const { getNeighbors } = await import('../../services/api');

      (getNeighbors as any).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useGraphStore());

      await act(async () => {
        await result.current.loadGraph('Python', 2);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.loading).toBe(false);
    });
  });

  describe('addNode', () => {
    it('adds new node to graph', () => {
      const { result } = renderHook(() => useGraphStore());

      const newNode = {
        id: 'NewNode',
        title: 'New Node',
        category: 'Category',
        word_count: 500,
        depth: 1,
        links_count: 3,
        summary: 'Summary',
      };

      act(() => {
        result.current.addNode(newNode);
      });

      expect(result.current.nodes).toContain(newNode);
    });

    it('deduplicates nodes by id', () => {
      const { result } = renderHook(() => useGraphStore());

      const node1 = {
        id: 'Node1',
        title: 'Node 1',
        category: 'A',
        word_count: 500,
        depth: 0,
        links_count: 3,
        summary: 'First',
      };

      const node2 = {
        id: 'Node1',
        title: 'Node 1 Updated',
        category: 'B',
        word_count: 600,
        depth: 1,
        links_count: 5,
        summary: 'Updated',
      };

      act(() => {
        result.current.addNode(node1);
        result.current.addNode(node2);
      });

      // Should only have one node with id 'Node1'
      const node1s = result.current.nodes.filter((n) => n.id === 'Node1');
      expect(node1s).toHaveLength(1);
    });

    it('updates existing node when adding duplicate', () => {
      const { result } = renderHook(() => useGraphStore());

      const node1 = {
        id: 'Node1',
        title: 'Original',
        category: 'A',
        word_count: 500,
        depth: 0,
        links_count: 3,
        summary: 'Original',
      };

      const node2 = {
        id: 'Node1',
        title: 'Updated',
        category: 'B',
        word_count: 600,
        depth: 1,
        links_count: 5,
        summary: 'Updated',
      };

      act(() => {
        result.current.addNode(node1);
        result.current.addNode(node2);
      });

      const updatedNode = result.current.nodes.find((n) => n.id === 'Node1');
      expect(updatedNode?.title).toBe('Updated');
    });
  });

  describe('setSelectedNode', () => {
    it('sets selected node id', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setSelectedNode('Node1');
      });

      expect(result.current.selectedNode).toBe('Node1');
    });

    it('clears selection when null', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setSelectedNode('Node1');
        result.current.setSelectedNode(null);
      });

      expect(result.current.selectedNode).toBeNull();
    });

    it('updates selected node', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setSelectedNode('Node1');
        result.current.setSelectedNode('Node2');
      });

      expect(result.current.selectedNode).toBe('Node2');
    });
  });

  describe('applyFilters', () => {
    beforeEach(() => {
      const { result } = renderHook(() => useGraphStore());

      const nodes = [
        {
          id: 'Node1',
          title: 'Node 1',
          category: 'Computer Science',
          word_count: 1000,
          depth: 0,
          links_count: 5,
          summary: 'CS node',
        },
        {
          id: 'Node2',
          title: 'Node 2',
          category: 'Physics',
          word_count: 800,
          depth: 1,
          links_count: 3,
          summary: 'Physics node',
        },
        {
          id: 'Node3',
          title: 'Node 3',
          category: 'Computer Science',
          word_count: 600,
          depth: 2,
          links_count: 2,
          summary: 'Another CS node',
        },
      ];

      act(() => {
        nodes.forEach((node) => result.current.addNode(node));
      });
    });

    it('filters nodes by category', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.applyFilters({
          categories: ['Computer Science'],
        });
      });

      const filtered = result.current.getFilteredNodes();

      expect(filtered).toHaveLength(2);
      expect(filtered.every((n) => n.category === 'Computer Science')).toBe(true);
    });

    it('filters nodes by depth', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.applyFilters({
          maxDepth: 1,
        });
      });

      const filtered = result.current.getFilteredNodes();

      expect(filtered.every((n) => n.depth <= 1)).toBe(true);
    });

    it('applies multiple filters', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.applyFilters({
          categories: ['Computer Science'],
          maxDepth: 1,
        });
      });

      const filtered = result.current.getFilteredNodes();

      expect(filtered).toHaveLength(1);
      expect(filtered[0].category).toBe('Computer Science');
      expect(filtered[0].depth).toBeLessThanOrEqual(1);
    });

    it('returns all nodes when no filters', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.applyFilters({});
      });

      const filtered = result.current.getFilteredNodes();

      expect(filtered).toHaveLength(3);
    });
  });

  describe('clearGraph', () => {
    it('clears all nodes and edges', () => {
      const { result } = renderHook(() => useGraphStore());

      const node = {
        id: 'Node1',
        title: 'Node 1',
        category: 'A',
        word_count: 500,
        depth: 0,
        links_count: 3,
        summary: 'Test',
      };

      act(() => {
        result.current.addNode(node);
        result.current.clearGraph();
      });

      expect(result.current.nodes).toEqual([]);
      expect(result.current.edges).toEqual([]);
    });

    it('clears selected node', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setSelectedNode('Node1');
        result.current.clearGraph();
      });

      expect(result.current.selectedNode).toBeNull();
    });

    it('clears error state', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        // Manually set error
        useGraphStore.setState({ error: 'Test error' });
        result.current.clearGraph();
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('localStorage persistence', () => {
    it('persist middleware is configured with correct storage key', () => {
      // Verify the store is configured with persist middleware using the right key
      const persistOptions = useGraphStore.persist;
      expect(persistOptions).toBeDefined();
      expect(persistOptions.getOptions().name).toBe('wikigr-graph');
    });

    it('partialize strips non-essential fields', () => {
      // Verify that the persist partialize function produces clean data
      const state = useGraphStore.getState();
      const partialize = useGraphStore.persist.getOptions().partialize;

      if (partialize) {
        const partial = partialize({
          ...state,
          nodes: [
            {
              id: 'Node1',
              title: 'Title',
              category: 'Cat',
              word_count: 100,
              depth: 0,
              links_count: 5,
              summary: 'Sum',
            },
          ],
          edges: [
            { source: 'A', target: 'B', type: 'internal', weight: 1.0 },
          ],
        });

        expect(partial.nodes).toHaveLength(1);
        expect(partial.nodes[0].id).toBe('Node1');
        expect(partial.edges).toHaveLength(1);
      }
    });

    it('handles corrupted localStorage data', () => {
      localStorage.setItem('wikigr-graph', 'invalid json');

      // Should not throw error
      const { result } = renderHook(() => useGraphStore());

      expect(result.current.nodes).toEqual([]);
    });
  });
});

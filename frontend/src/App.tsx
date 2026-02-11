/**
 * Main App Component
 *
 * Root component that integrates all UI elements.
 */

import { useState, useCallback, useMemo } from 'react';
import { GraphCanvas } from './components/Graph/GraphCanvas';
import { SearchBar } from './components/Search/SearchBar';
import { NodeInfo } from './components/Sidebar/NodeInfo';
import { FilterPanel } from './components/Sidebar/FilterPanel';
import { useGraphStore } from './store/graphStore';
import { searchSemantic, autocomplete } from './services/api';

function App() {
  // Individual Zustand selectors to avoid unnecessary re-renders
  const nodes = useGraphStore((s) => s.nodes);
  const edges = useGraphStore((s) => s.edges);
  const selectedNode = useGraphStore((s) => s.selectedNode);
  const setSelectedNode = useGraphStore((s) => s.setSelectedNode);
  const loadGraph = useGraphStore((s) => s.loadGraph);
  const applyFilters = useGraphStore((s) => s.applyFilters);
  const getFilteredNodes = useGraphStore((s) => s.getFilteredNodes);
  const filters = useGraphStore((s) => s.filters);
  const loading = useGraphStore((s) => s.loading);
  const error = useGraphStore((s) => s.error);

  const [searchMode, setSearchMode] = useState<'text' | 'semantic'>('semantic');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Get filtered nodes and compute filtered edges
  // eslint-disable-next-line react-hooks/exhaustive-deps -- getFilteredNodes is a store method; nodes and filters are the real deps
  const filteredNodes = useMemo(() => getFilteredNodes(), [nodes, filters]);
  const filteredNodeIds = useMemo(
    () => new Set(filteredNodes.map((n) => n.id)),
    [filteredNodes]
  );
  const filteredEdges = useMemo(
    () =>
      edges.filter((e) => {
        const sourceId = typeof e.source === 'string' ? e.source : e.source.id;
        const targetId = typeof e.target === 'string' ? e.target : e.target.id;
        return filteredNodeIds.has(sourceId) && filteredNodeIds.has(targetId);
      }),
    [edges, filteredNodeIds]
  );

  // Get unique categories from all nodes (not filtered)
  const categories = useMemo(
    () => Array.from(new Set(nodes.map((n) => n.category))),
    [nodes]
  );

  // Get selected node object from filtered nodes
  const selectedNodeObj = selectedNode
    ? filteredNodes.find((n) => n.id === selectedNode) || null
    : null;

  // Handle search - dispatches based on searchMode
  const handleSearch = useCallback(async (query: string) => {
    if (!query.trim()) return;

    setSearchLoading(true);
    setSearchError(null);

    try {
      if (searchMode === 'semantic') {
        const results = await searchSemantic(query, 10);

        // Load graph for first result
        if (results.length > 0) {
          await loadGraph(results[0].article, 2);
          setSelectedNode(results[0].article);
        }
      } else {
        // Text mode: use autocomplete to find matching articles by title
        const suggestions = await autocomplete(query, 10);

        if (suggestions.length > 0) {
          // Load graph for the best title match
          await loadGraph(suggestions[0].title, 2);
          setSelectedNode(suggestions[0].title);
        }
      }
    } catch (err) {
      setSearchError((err as Error).message);
    } finally {
      setSearchLoading(false);
    }
  }, [searchMode, loadGraph, setSelectedNode]);

  // Handle node click
  const handleNodeClick = useCallback((nodeId: string) => {
    setSelectedNode(nodeId);
  }, [setSelectedNode]);

  // Handle filter change
  const handleFilterChange = useCallback((filterUpdate: {
    selectedCategories?: string[];
    depth?: number;
  }) => {
    applyFilters({
      categories: filterUpdate.selectedCategories,
      maxDepth: filterUpdate.depth,
    });
  }, [applyFilters]);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center gap-4">
          <h1 className="text-2xl font-bold text-gray-900">WikiGR</h1>
          <div className="flex-1 max-w-2xl">
            <SearchBar
              onSearch={handleSearch}
              onModeChange={setSearchMode}
              mode={searchMode}
              isLoading={searchLoading}
              error={searchError}
            />
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-80 bg-white border-r border-gray-200 overflow-y-auto">
          <FilterPanel
            categories={categories}
            onFilterChange={handleFilterChange}
          />

          {selectedNodeObj && <NodeInfo selectedNode={selectedNodeObj} />}
        </aside>

        {/* Graph canvas */}
        <main className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75 z-10">
              <div className="text-center">
                <div className="animate-spin h-12 w-12 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
                <p className="text-gray-600">Loading graph...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
              <div className="text-center">
                <p className="text-red-600 mb-4">Error: {error}</p>
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Reload
                </button>
              </div>
            </div>
          )}

          {!loading && !error && filteredNodes.length === 0 && nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-gray-500">
                <p className="text-xl mb-2">Search for an article to begin</p>
                <p className="text-sm">Try searching for "Machine Learning" or "Python"</p>
              </div>
            </div>
          )}

          {filteredNodes.length > 0 && (
            <GraphCanvas
              nodes={filteredNodes}
              edges={filteredEdges}
              onNodeClick={handleNodeClick}
              selectedNodeId={selectedNode}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;

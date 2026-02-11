/**
 * Main App Component
 *
 * Root component that integrates all UI elements.
 */

import React, { useState, useCallback } from 'react';
import { GraphCanvas } from './components/Graph/GraphCanvas';
import { SearchBar } from './components/Search/SearchBar';
import { NodeInfo } from './components/Sidebar/NodeInfo';
import { FilterPanel } from './components/Sidebar/FilterPanel';
import { useGraphStore } from './store/graphStore';
import { searchSemantic } from './services/api';
import type { SearchResult } from './types/graph';

function App() {
  const {
    nodes,
    edges,
    selectedNode,
    setSelectedNode,
    loadGraph,
    applyFilters,
    loading,
    error,
  } = useGraphStore();

  const [searchMode, setSearchMode] = useState<'text' | 'semantic'>('semantic');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Get unique categories from nodes
  const categories = Array.from(new Set(nodes.map((n) => n.category)));

  // Get selected node object
  const selectedNodeObj = selectedNode
    ? nodes.find((n) => n.id === selectedNode) || null
    : null;

  // Handle search
  const handleSearch = useCallback(async (query: string) => {
    if (!query.trim()) return;

    setSearchLoading(true);
    setSearchError(null);

    try {
      const results = await searchSemantic(query, 10);
      setSearchResults(results);

      // Load graph for first result
      if (results.length > 0) {
        await loadGraph(results[0].article, 2);
        setSelectedNode(results[0].article);
      }
    } catch (err) {
      setSearchError((err as Error).message);
    } finally {
      setSearchLoading(false);
    }
  }, [loadGraph, setSelectedNode]);

  // Handle node click
  const handleNodeClick = useCallback((nodeId: string) => {
    setSelectedNode(nodeId);
  }, [setSelectedNode]);

  // Handle filter change
  const handleFilterChange = useCallback((filters: {
    selectedCategories?: string[];
    depth?: number;
  }) => {
    applyFilters({
      categories: filters.selectedCategories,
      maxDepth: filters.depth,
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

          {!loading && !error && nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-gray-500">
                <p className="text-xl mb-2">Search for an article to begin</p>
                <p className="text-sm">Try searching for "Machine Learning" or "Python"</p>
              </div>
            </div>
          )}

          {nodes.length > 0 && (
            <GraphCanvas
              nodes={nodes}
              edges={edges}
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

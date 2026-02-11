/**
 * NodeInfo Component
 *
 * Displays detailed information about a selected node/article.
 */

import React, { useEffect, useState } from 'react';
import { getArticle } from '../../services/api';
import type { GraphNode, Article } from '../../types/graph';

interface NodeInfoProps {
  selectedNode: GraphNode | null;
}

export const NodeInfo: React.FC<NodeInfoProps> = ({ selectedNode }) => {
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedNode) {
      setArticle(null);
      return;
    }

    const controller = new AbortController();

    const fetchArticle = async () => {
      setLoading(true);
      setError(null);

      try {
        const data = await getArticle(selectedNode.title, controller.signal);
        setArticle(data);
      } catch (err) {
        // Ignore aborted requests (user navigated away or selected another node)
        if (controller.signal.aborted) return;
        setError((err as Error).message || 'Failed to load article');
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchArticle();

    return () => controller.abort();
  }, [selectedNode]);

  if (!selectedNode) {
    return null;
  }

  return (
    <div className="p-4 bg-white border-t border-gray-200">
      <h2 className="text-xl font-bold mb-2">{selectedNode.title}</h2>

      <div className="text-sm text-gray-600 space-y-1 mb-4">
        <div>
          <span className="font-medium">Category:</span> {selectedNode.category}
        </div>
        <div>
          <span className="font-medium">Word Count:</span> {selectedNode.word_count}
        </div>
        <div>
          <span className="font-medium">Links:</span> {selectedNode.links_count}
        </div>
      </div>

      {loading && (
        <div role="status" className="flex items-center justify-center py-8">
          <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
        </div>
      )}

      {error && (
        <div className="text-red-600 text-sm py-4" role="alert">
          Error: {error}
        </div>
      )}

      {article && !loading && (
        <div className="space-y-4">
          {/* Sections */}
          {article.sections.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Sections</h3>
              <ul className="space-y-2">
                {article.sections.map((section, index) => (
                  <li key={index} className="border-l-2 border-gray-300 pl-3">
                    <div className="font-medium">{section.title}</div>
                    <div className="text-sm text-gray-600 mt-1">
                      {section.content.substring(0, 150)}
                      {section.content.length > 150 ? '...' : ''}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Links */}
          {article.links.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Links</h3>
              <div className="flex flex-wrap gap-2">
                {article.links.slice(0, 10).map((link) => (
                  <span
                    key={link}
                    className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded"
                  >
                    {link}
                  </span>
                ))}
                {article.links.length > 10 && (
                  <span className="text-xs text-gray-500">
                    +{article.links.length - 10} more
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Backlinks */}
          {article.backlinks.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Backlinks</h3>
              <div className="flex flex-wrap gap-2">
                {article.backlinks.slice(0, 10).map((link) => (
                  <span
                    key={link}
                    className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded"
                  >
                    {link}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Categories */}
          {article.categories.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Categories</h3>
              <div className="flex flex-wrap gap-2">
                {article.categories.map((cat) => (
                  <span
                    key={cat}
                    className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded"
                  >
                    {cat}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Last updated */}
          {article.last_updated && (
            <div className="text-xs text-gray-500">
              Last updated: {new Date(article.last_updated).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
              })}
            </div>
          )}

          {/* Wikipedia link */}
          <a
            href={article.wikipedia_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View on Wikipedia"
            className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            View on Wikipedia
          </a>
        </div>
      )}
    </div>
  );
};

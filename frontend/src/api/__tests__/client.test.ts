/**
 * Tests for API client
 *
 * Tests typed API calls, error handling, and retry logic.
 * Following TDD methodology - these tests will fail until implementation is complete.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import axios from 'axios';
import { getNeighbors, searchSemantic, getArticle, autocomplete } from '../client';

// Mock axios
vi.mock('axios');

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getNeighbors', () => {
    it('returns typed GraphResponse', async () => {
      const mockResponse = {
        data: {
          seed: 'Machine Learning',
          nodes: [
            {
              id: 'Machine Learning',
              title: 'Machine Learning',
              category: 'Computer Science',
              word_count: 5234,
              depth: 0,
              links_count: 42,
              summary: 'Machine learning is...',
            },
          ],
          edges: [
            {
              source: 'Machine Learning',
              target: 'Deep Learning',
              type: 'internal',
              weight: 1.0,
            },
          ],
          total_nodes: 1,
          total_edges: 1,
          execution_time_ms: 67,
        },
      };

      (axios.get as any).mockResolvedValue(mockResponse);

      const result = await getNeighbors('Machine Learning', 2);

      expect(axios.get).toHaveBeenCalledWith('/api/v1/graph', {
        params: {
          article: 'Machine Learning',
          depth: 2,
          limit: 50,
        },
      });

      expect(result).toEqual(mockResponse.data);
      expect(result.nodes).toHaveLength(1);
      expect(result.edges).toHaveLength(1);
    });

    it('passes optional parameters', async () => {
      (axios.get as any).mockResolvedValue({ data: {} });

      await getNeighbors('Python', 1, 100, 'Computer Science');

      expect(axios.get).toHaveBeenCalledWith('/api/v1/graph', {
        params: {
          article: 'Python',
          depth: 1,
          limit: 100,
          category: 'Computer Science',
        },
      });
    });

    it('handles network errors', async () => {
      (axios.get as any).mockRejectedValue(new Error('Network Error'));

      await expect(getNeighbors('Python', 2)).rejects.toThrow('Network Error');
    });

    it('handles HTTP 404 errors', async () => {
      const error = {
        response: {
          status: 404,
          data: {
            error: {
              code: 'NOT_FOUND',
              message: 'Article not found',
            },
          },
        },
      };

      (axios.get as any).mockRejectedValue(error);

      await expect(getNeighbors('NonExistent', 2)).rejects.toThrow();
    });

    it('handles HTTP 400 errors', async () => {
      const error = {
        response: {
          status: 400,
          data: {
            error: {
              code: 'INVALID_PARAMETER',
              message: 'Invalid depth parameter',
            },
          },
        },
      };

      (axios.get as any).mockRejectedValue(error);

      await expect(getNeighbors('Python', 5)).rejects.toThrow();
    });
  });

  describe('searchSemantic', () => {
    it('returns typed SearchResult array', async () => {
      const mockResponse = {
        data: {
          query: 'Machine Learning',
          results: [
            {
              article: 'Deep Learning',
              similarity: 0.89,
              category: 'Computer Science',
              word_count: 4523,
              summary: 'Deep learning is...',
            },
            {
              article: 'Neural Networks',
              similarity: 0.87,
              category: 'Computer Science',
              word_count: 3891,
              summary: 'Neural networks are...',
            },
          ],
          total: 2,
          execution_time_ms: 45,
        },
      };

      (axios.get as any).mockResolvedValue(mockResponse);

      const result = await searchSemantic('Machine Learning');

      expect(axios.get).toHaveBeenCalledWith('/api/v1/search', {
        params: {
          query: 'Machine Learning',
          limit: 10,
        },
      });

      expect(result).toEqual(mockResponse.data.results);
      expect(result).toHaveLength(2);
      expect(result[0].similarity).toBe(0.89);
    });

    it('passes optional parameters', async () => {
      (axios.get as any).mockResolvedValue({ data: { results: [] } });

      await searchSemantic('Python', 20, 'Computer Science', 0.7);

      expect(axios.get).toHaveBeenCalledWith('/api/v1/search', {
        params: {
          query: 'Python',
          limit: 20,
          category: 'Computer Science',
          threshold: 0.7,
        },
      });
    });

    it('handles empty results', async () => {
      const mockResponse = {
        data: {
          query: 'Obscure Topic',
          results: [],
          total: 0,
          execution_time_ms: 23,
        },
      };

      (axios.get as any).mockResolvedValue(mockResponse);

      const result = await searchSemantic('Obscure Topic', 10, undefined, 0.99);

      expect(result).toEqual([]);
    });
  });

  describe('getArticle', () => {
    it('returns article details', async () => {
      const mockResponse = {
        data: {
          title: 'Machine Learning',
          category: 'Computer Science',
          word_count: 5234,
          sections: [],
          links: [],
          backlinks: [],
          categories: [],
          wikipedia_url: 'https://en.wikipedia.org/wiki/Machine_Learning',
          last_updated: '2026-02-10T12:00:00Z',
        },
      };

      (axios.get as any).mockResolvedValue(mockResponse);

      const result = await getArticle('Machine Learning');

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/articles/Machine%20Learning'
      );

      expect(result).toEqual(mockResponse.data);
    });

    it('URL-encodes article title', async () => {
      (axios.get as any).mockResolvedValue({ data: {} });

      await getArticle('Python (programming language)');

      expect(axios.get).toHaveBeenCalledWith(
        '/api/v1/articles/Python%20(programming%20language)'
      );
    });
  });

  describe('autocomplete', () => {
    it('returns suggestions', async () => {
      const mockResponse = {
        data: {
          query: 'mach',
          suggestions: [
            {
              title: 'Machine Learning',
              category: 'Computer Science',
              match_type: 'prefix',
            },
            {
              title: 'Machiavelli',
              category: 'History',
              match_type: 'prefix',
            },
          ],
          total: 2,
        },
      };

      (axios.get as any).mockResolvedValue(mockResponse);

      const result = await autocomplete('mach');

      expect(axios.get).toHaveBeenCalledWith('/api/v1/autocomplete', {
        params: {
          q: 'mach',
          limit: 10,
        },
      });

      expect(result).toEqual(mockResponse.data.suggestions);
      expect(result).toHaveLength(2);
    });

    it('validates minimum query length', async () => {
      await expect(autocomplete('m')).rejects.toThrow(/too short|minimum/i);

      expect(axios.get).not.toHaveBeenCalled();
    });
  });

  describe('Error handling', () => {
    it('handles rate limit errors (429)', async () => {
      const error = {
        response: {
          status: 429,
          data: {
            error: {
              code: 'RATE_LIMIT_EXCEEDED',
              message: 'Rate limit exceeded',
              retry_after: 32,
            },
          },
        },
      };

      (axios.get as any).mockRejectedValue(error);

      await expect(getNeighbors('Python', 2)).rejects.toThrow(/rate limit/i);
    });

    it('handles server errors (500)', async () => {
      const error = {
        response: {
          status: 500,
          data: {
            error: {
              code: 'SERVER_ERROR',
              message: 'Internal server error',
            },
          },
        },
      };

      (axios.get as any).mockRejectedValue(error);

      await expect(searchSemantic('Python')).rejects.toThrow();
    });

    it('extracts error message from response', async () => {
      const error = {
        response: {
          status: 404,
          data: {
            error: {
              code: 'NOT_FOUND',
              message: 'Article not found',
            },
          },
        },
      };

      (axios.get as any).mockRejectedValue(error);

      try {
        await getArticle('NonExistent');
      } catch (e: any) {
        expect(e.message).toContain('Article not found');
      }
    });
  });

  describe('Retry logic', () => {
    it('retries on network failure', async () => {
      // First call fails, second succeeds
      (axios.get as any)
        .mockRejectedValueOnce(new Error('Network Error'))
        .mockResolvedValueOnce({ data: { results: [] } });

      const result = await searchSemantic('Python');

      expect(axios.get).toHaveBeenCalledTimes(2);
      expect(result).toEqual([]);
    });

    it('retries on 5xx errors', async () => {
      const error = {
        response: {
          status: 503,
          data: { error: { message: 'Service unavailable' } },
        },
      };

      (axios.get as any)
        .mockRejectedValueOnce(error)
        .mockResolvedValueOnce({ data: {} });

      await getNeighbors('Python', 2);

      expect(axios.get).toHaveBeenCalledTimes(2);
    });

    it('does not retry on 4xx errors', async () => {
      const error = {
        response: {
          status: 404,
          data: { error: { message: 'Not found' } },
        },
      };

      (axios.get as any).mockRejectedValue(error);

      await expect(getNeighbors('NonExistent', 2)).rejects.toThrow();

      // Should only try once
      expect(axios.get).toHaveBeenCalledTimes(1);
    });

    it('gives up after max retries', async () => {
      (axios.get as any).mockRejectedValue(new Error('Network Error'));

      await expect(searchSemantic('Python')).rejects.toThrow();

      // Should try initial + 2 retries = 3 times
      expect(axios.get).toHaveBeenCalledTimes(3);
    });
  });
});

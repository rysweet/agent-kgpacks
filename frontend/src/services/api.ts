/**
 * API client for WikiGR backend
 *
 * Provides typed functions for all backend endpoints with error handling and retry logic.
 */

import axios, { AxiosError } from 'axios';
import type {
  GraphResponse,
  SearchResult,
  Article,
  AutocompleteSuggestion,
} from '../types/graph';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Error handling interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const data = error.response.data as any;
      const message = data?.error?.message || 'An error occurred';

      if (error.response.status === 429) {
        throw new Error(`Rate limit exceeded: ${message}`);
      }
      throw new Error(message);
    }
    throw error;
  }
);

/**
 * Retry function for network errors and 5xx errors
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 2,
  delay = 1000
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;

      // Don't retry cancelled requests (AbortController)
      if (axios.isCancel(error)) {
        throw error;
      }

      // Don't retry on 4xx errors
      if (axios.isAxiosError(error) && error.response) {
        if (error.response.status >= 400 && error.response.status < 500) {
          throw error;
        }
      }

      // Wait before retry (except on last attempt)
      if (attempt < maxRetries) {
        await new Promise((resolve) => setTimeout(resolve, delay * (attempt + 1)));
      }
    }
  }

  throw lastError;
}

/**
 * Get neighbors for an article (graph expansion)
 */
export async function getNeighbors(
  article: string,
  depth: number,
  limit = 50,
  category?: string
): Promise<GraphResponse> {
  return withRetry(async () => {
    const response = await apiClient.get<GraphResponse>('/api/v1/graph', {
      params: { article, depth, limit, category },
    });
    return response.data;
  });
}

/**
 * Semantic search for articles
 */
export async function searchSemantic(
  query: string,
  limit = 10,
  category?: string,
  threshold?: number
): Promise<SearchResult[]> {
  return withRetry(async () => {
    const response = await apiClient.get<{ results: SearchResult[] }>('/api/v1/search', {
      params: { query, limit, category, threshold },
    });
    return response.data.results;
  });
}

/**
 * Get full article details
 */
export async function getArticle(
  title: string,
  signal?: AbortSignal
): Promise<Article> {
  return withRetry(async () => {
    const response = await apiClient.get<Article>(
      `/api/v1/articles/${encodeURIComponent(title)}`,
      { signal }
    );
    return response.data;
  });
}

/**
 * Get autocomplete suggestions
 */
export async function autocomplete(
  query: string,
  limit = 10
): Promise<AutocompleteSuggestion[]> {
  if (query.length < 2) {
    throw new Error('Query too short: minimum 2 characters');
  }

  return withRetry(async () => {
    const response = await apiClient.get<{ suggestions: AutocompleteSuggestion[] }>(
      '/api/v1/autocomplete',
      {
        params: { q: query, limit },
      }
    );
    return response.data.suggestions;
  });
}

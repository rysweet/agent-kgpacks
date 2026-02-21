/**
 * Graph-related TypeScript types
 *
 * Mirrors backend Pydantic models for type safety.
 */

export interface GraphNode {
  id: string;
  title: string;
  category: string;
  word_count: number;
  depth: number;
  links_count: number;
  summary?: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  type: 'internal' | 'external';
  weight: number;
}

export interface GraphResponse {
  seed: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  execution_time_ms: number;
}

export interface ArticleSection {
  title: string;
  content: string;
  word_count: number;
  level: number;
}

export interface Article {
  title: string;
  category: string;
  word_count: number;
  sections: ArticleSection[];
  links: string[];
  backlinks: string[];
  categories: string[];
  wikipedia_url: string;
  last_updated: string;
}

export interface SearchResult {
  article: string;
  similarity: number;
  category: string;
  word_count: number;
  summary?: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  execution_time_ms: number;
}

export interface AutocompleteSuggestion {
  title: string;
  category: string;
  match_type: 'prefix' | 'fuzzy';
}

export interface AutocompleteResponse {
  query: string;
  suggestions: AutocompleteSuggestion[];
  total: number;
}

export interface Filters {
  categories?: string[];
  maxDepth?: number;
  minSimilarity?: number;
}

export interface ChatResponse {
  answer: string;
  sources: string[];
  query_type: string;
  execution_time_ms: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  queryType?: string;
  executionTimeMs?: number;
  timestamp: number;
}

# WikiGR Visualization - Developer Guide

Technical guide for developing and extending the WikiGR interactive visualization frontend.

## Architecture Overview

### Technology Stack

- **Framework:** React 18.2 + TypeScript 5.3
- **Build Tool:** Vite 5.0
- **State Management:** Zustand 4.5
- **Visualization:** D3.js 7.8
- **Styling:** Tailwind CSS 3.4
- **PWA:** Vite PWA Plugin (Workbox)
- **Testing:** Vitest + React Testing Library
- **API Client:** Axios 1.6

### Project Structure

```
frontend/
├── public/
│   ├── manifest.json          # PWA manifest
│   ├── icons/                 # App icons (192x192, 512x512)
│   └── offline.html           # Offline fallback
├── src/
│   ├── components/            # React components
│   │   ├── Graph/
│   │   │   ├── GraphCanvas.tsx       # Main D3.js graph
│   │   │   ├── GraphControls.tsx     # Zoom, pan controls
│   │   │   ├── GraphLegend.tsx       # Color legend
│   │   │   └── ForceSimulation.ts    # D3 force simulation
│   │   ├── Search/
│   │   │   ├── SearchBar.tsx         # Search input
│   │   │   ├── SearchResults.tsx     # Results list
│   │   │   └── Autocomplete.tsx      # Suggestions
│   │   ├── Sidebar/
│   │   │   ├── DetailPanel.tsx       # Node details
│   │   │   ├── FilterPanel.tsx       # Filters UI
│   │   │   └── ExpandButton.tsx      # Expand node
│   │   ├── Layout/
│   │   │   ├── Header.tsx            # Top toolbar
│   │   │   ├── Sidebar.tsx           # Left sidebar
│   │   │   └── MainLayout.tsx        # App layout
│   │   └── UI/
│   │       ├── Button.tsx            # Reusable button
│   │       ├── Slider.tsx            # Range input
│   │       ├── Dropdown.tsx          # Select input
│   │       └── Loading.tsx           # Loading spinner
│   ├── stores/                # Zustand stores
│   │   ├── graphStore.ts             # Graph state
│   │   ├── searchStore.ts            # Search state
│   │   ├── uiStore.ts                # UI state (sidebar, filters)
│   │   └── cacheStore.ts             # Offline cache
│   ├── services/              # API and business logic
│   │   ├── api.ts                    # API client
│   │   ├── graphService.ts           # Graph data fetching
│   │   ├── searchService.ts          # Search operations
│   │   └── cacheService.ts           # Cache management
│   ├── hooks/                 # Custom React hooks
│   │   ├── useGraph.ts               # Graph data hook
│   │   ├── useSearch.ts              # Search hook
│   │   ├── useKeyboard.ts            # Keyboard shortcuts
│   │   └── useOffline.ts             # Offline detection
│   ├── utils/                 # Utilities
│   │   ├── graphLayout.ts            # Layout algorithms
│   │   ├── colorScale.ts             # Category colors
│   │   ├── formatters.ts             # Data formatters
│   │   └── validators.ts             # Input validation
│   ├── types/                 # TypeScript types
│   │   ├── graph.ts                  # Graph types
│   │   ├── api.ts                    # API types
│   │   └── store.ts                  # Store types
│   ├── styles/                # Global styles
│   │   ├── globals.css               # Base styles
│   │   └── graph.css                 # D3 graph styles
│   ├── App.tsx                # Root component
│   ├── main.tsx               # Entry point
│   └── vite-env.d.ts          # Vite types
├── tests/                     # Test files
│   ├── unit/
│   │   ├── components/
│   │   ├── stores/
│   │   └── utils/
│   ├── integration/
│   └── e2e/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── README.md                  # User guide
```

## Component Architecture

### Component Hierarchy

```
<App>
  <MainLayout>
    <Header>
      <SearchBar />
      <FilterControls />
      <MenuButton />
    </Header>

    <Sidebar>
      <SearchResults />
      <DetailPanel />
      <FilterPanel />
    </Sidebar>

    <GraphCanvas>
      <ForceSimulation />
      <GraphLegend />
      <GraphControls />
    </GraphCanvas>
  </MainLayout>
</App>
```

### Key Components

#### GraphCanvas.tsx

**Purpose:** Render force-directed graph using D3.js

**Implementation:**
```typescript
import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { useGraphStore } from '../stores/graphStore';

export function GraphCanvas() {
  const svgRef = useRef<SVGSVGElement>(null);
  const { nodes, edges, selectedNode } = useGraphStore();

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Create force simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30));

    // Draw nodes
    const nodeElements = svg.selectAll('.node')
      .data(nodes)
      .join('circle')
      .attr('class', 'node')
      .attr('r', d => 5 + d.links_count * 0.5)
      .attr('fill', d => getCategoryColor(d.category))
      .on('click', (event, d) => {
        useGraphStore.setState({ selectedNode: d.id });
      });

    // Draw edges
    const edgeElements = svg.selectAll('.edge')
      .data(edges)
      .join('line')
      .attr('class', 'edge')
      .attr('stroke', '#999')
      .attr('stroke-width', d => d.weight * 2);

    // Update positions on tick
    simulation.on('tick', () => {
      nodeElements
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      edgeElements
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
    });

    // Zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.1, 10])
      .on('zoom', (event) => {
        svg.selectAll('.node, .edge')
          .attr('transform', event.transform);
      });

    svg.call(zoom);

    return () => {
      simulation.stop();
    };
  }, [nodes, edges]);

  return (
    <svg
      ref={svgRef}
      className="w-full h-full"
      style={{ background: '#f9fafb' }}
    />
  );
}
```

**Key features:**
- D3.js force simulation
- Zoom and pan
- Node selection
- Dynamic sizing by link count
- Category-based coloring

#### SearchBar.tsx

**Purpose:** Search input with autocomplete

**Implementation:**
```typescript
import { useState, useCallback } from 'react';
import { useSearchStore } from '../stores/searchStore';
import { searchService } from '../services/searchService';
import { Autocomplete } from './Autocomplete';

export function SearchBar() {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const { search } = useSearchStore();

  const handleInput = useCallback(async (value: string) => {
    setQuery(value);

    if (value.length >= 2) {
      const results = await searchService.autocomplete(value);
      setSuggestions(results);
    } else {
      setSuggestions([]);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await search(query);
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <input
        type="text"
        value={query}
        onChange={(e) => handleInput(e.target.value)}
        placeholder="Search articles..."
        className="w-full px-4 py-2 border rounded-lg"
      />

      {suggestions.length > 0 && (
        <Autocomplete
          suggestions={suggestions}
          onSelect={(title) => {
            setQuery(title);
            search(title);
          }}
        />
      )}
    </form>
  );
}
```

## State Management (Zustand)

### Graph Store

**Purpose:** Manage graph data and selection state

**Implementation:**
```typescript
// stores/graphStore.ts
import { create } from 'zustand';
import { GraphNode, GraphEdge } from '../types/graph';

interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: string | null;
  loading: boolean;
  error: string | null;

  // Actions
  loadGraph: (article: string, depth: number) => Promise<void>;
  expandNode: (nodeId: string) => Promise<void>;
  selectNode: (nodeId: string | null) => void;
  clearGraph: () => void;
}

export const useGraphStore = create<GraphState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  loading: false,
  error: null,

  loadGraph: async (article, depth) => {
    set({ loading: true, error: null });

    try {
      const data = await graphService.fetchGraph(article, depth);
      set({
        nodes: data.nodes,
        edges: data.edges,
        loading: false
      });
    } catch (error) {
      set({
        error: error.message,
        loading: false
      });
    }
  },

  expandNode: async (nodeId) => {
    const { nodes, edges } = get();
    const node = nodes.find(n => n.id === nodeId);

    if (!node) return;

    // Fetch neighbors
    const data = await graphService.fetchGraph(nodeId, 1);

    // Merge with existing graph
    const newNodes = data.nodes.filter(
      n => !nodes.find(existing => existing.id === n.id)
    );

    set({
      nodes: [...nodes, ...newNodes],
      edges: [...edges, ...data.edges]
    });
  },

  selectNode: (nodeId) => {
    set({ selectedNode: nodeId });
  },

  clearGraph: () => {
    set({
      nodes: [],
      edges: [],
      selectedNode: null
    });
  }
}));
```

### Search Store

**Purpose:** Manage search queries and results

**Implementation:**
```typescript
// stores/searchStore.ts
import { create } from 'zustand';
import { SearchResult } from '../types/api';

interface SearchState {
  query: string;
  results: SearchResult[];
  loading: boolean;
  error: string | null;

  search: (query: string) => Promise<void>;
  clearResults: () => void;
}

export const useSearchStore = create<SearchState>((set) => ({
  query: '',
  results: [],
  loading: false,
  error: null,

  search: async (query) => {
    set({ query, loading: true, error: null });

    try {
      const results = await searchService.search(query);
      set({ results, loading: false });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },

  clearResults: () => {
    set({ results: [], query: '' });
  }
}));
```

## D3.js Integration Patterns

### Force Simulation

**Configuration:**
```typescript
// utils/graphLayout.ts
import * as d3 from 'd3';

export function createForceSimulation(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number,
  height: number
) {
  return d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges)
      .id(d => d.id)
      .distance(d => 50 + d.weight * 100)
      .strength(1)
    )
    .force('charge', d3.forceManyBody()
      .strength(-400)
      .distanceMax(500)
    )
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide()
      .radius(d => 10 + d.links_count * 2)
    )
    .alphaDecay(0.05)
    .velocityDecay(0.4);
}
```

### Zoom and Pan

**Implementation:**
```typescript
const zoom = d3.zoom<SVGSVGElement, unknown>()
  .scaleExtent([0.1, 10])
  .on('zoom', (event) => {
    const { transform } = event;

    // Apply transform to all elements
    svg.selectAll('.graph-layer')
      .attr('transform', transform);

    // Update store
    useGraphStore.setState({
      transform: {
        x: transform.x,
        y: transform.y,
        scale: transform.k
      }
    });
  });

svg.call(zoom);
```

### Node Interactions

**Drag behavior:**
```typescript
const drag = d3.drag<SVGCircleElement, GraphNode>()
  .on('start', (event, d) => {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  })
  .on('drag', (event, d) => {
    d.fx = event.x;
    d.fy = event.y;
  })
  .on('end', (event, d) => {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  });

nodeElements.call(drag);
```

## API Integration

### API Client

**Base configuration:**
```typescript
// services/api.ts
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 429) {
      throw new Error('Rate limit exceeded. Please try again later.');
    }
    throw error;
  }
);
```

### Service Layer

**Graph service:**
```typescript
// services/graphService.ts
import { apiClient } from './api';
import { GraphData } from '../types/graph';

export const graphService = {
  async fetchGraph(article: string, depth: number): Promise<GraphData> {
    const response = await apiClient.get('/api/v1/graph', {
      params: { article, depth, limit: 100 }
    });
    return response.data;
  },

  async fetchArticle(title: string) {
    const response = await apiClient.get(`/api/v1/articles/${encodeURIComponent(title)}`);
    return response.data;
  }
};
```

## Testing

### Component Tests

**Example: SearchBar test:**
```typescript
// tests/unit/components/SearchBar.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { SearchBar } from '../../../src/components/Search/SearchBar';
import { useSearchStore } from '../../../src/stores/searchStore';

describe('SearchBar', () => {
  it('renders search input', () => {
    render(<SearchBar />);
    expect(screen.getByPlaceholderText('Search articles...')).toBeInTheDocument();
  });

  it('triggers search on submit', async () => {
    const { search } = useSearchStore.getState();
    const spy = vi.spyOn(useSearchStore.getState(), 'search');

    render(<SearchBar />);

    const input = screen.getByPlaceholderText('Search articles...');
    fireEvent.change(input, { target: { value: 'Machine Learning' } });
    fireEvent.submit(input);

    expect(spy).toHaveBeenCalledWith('Machine Learning');
  });
});
```

### Store Tests

**Example: graphStore test:**
```typescript
// tests/unit/stores/graphStore.test.ts
import { renderHook, act } from '@testing-library/react';
import { useGraphStore } from '../../../src/stores/graphStore';

describe('graphStore', () => {
  it('loads graph data', async () => {
    const { result } = renderHook(() => useGraphStore());

    await act(async () => {
      await result.current.loadGraph('Machine Learning', 2);
    });

    expect(result.current.nodes.length).toBeGreaterThan(0);
    expect(result.current.loading).toBe(false);
  });
});
```

### E2E Tests

**Example: search flow:**
```typescript
// tests/e2e/search.spec.ts
import { test, expect } from '@playwright/test';

test('search and visualize article', async ({ page }) => {
  await page.goto('http://localhost:5173');

  // Enter search query
  await page.fill('[placeholder="Search articles..."]', 'Machine Learning');
  await page.press('[placeholder="Search articles..."]', 'Enter');

  // Wait for results
  await page.waitForSelector('.search-results');

  // Click first result
  await page.click('.search-result:first-child');

  // Verify graph loaded
  await page.waitForSelector('svg .node', { timeout: 5000 });
  const nodes = await page.$$('svg .node');
  expect(nodes.length).toBeGreaterThan(0);
});
```

## Build and Deployment

### Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Run tests
npm run test

# Type check
npm run type-check

# Lint
npm run lint
```

### Production Build

```bash
# Build for production
npm run build

# Output: dist/
# - index.html
# - assets/
#   - index-[hash].js
#   - index-[hash].css
# - manifest.json
# - sw.js (service worker)

# Preview build
npm run preview
```

### Environment Variables

**`.env.development`:**
```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_ENABLE_LOGGING=true
```

**`.env.production`:**
```env
VITE_API_URL=https://api.wikigr.example.com
VITE_WS_URL=wss://api.wikigr.example.com
VITE_ENABLE_LOGGING=false
```

### Deployment

**Static hosting (Vercel/Netlify):**
```bash
# Build
npm run build

# Deploy dist/ directory
vercel --prod
```

**Docker:**
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## Performance Optimization

### Bundle Size

**Strategies:**
1. **Code splitting:** Dynamic imports for routes
2. **Tree shaking:** Import specific D3 modules
3. **Lazy loading:** Load heavy components on-demand

**Example:**
```typescript
// Instead of: import * as d3 from 'd3';
import { forceSimulation, forceLink, forceManyBody } from 'd3-force';
import { select } from 'd3-selection';
import { zoom } from 'd3-zoom';
```

### Rendering Performance

**Techniques:**
1. **React.memo:** Prevent unnecessary re-renders
2. **useMemo/useCallback:** Memoize expensive calculations
3. **Virtual scrolling:** For large result lists
4. **Canvas rendering:** For 500+ nodes (instead of SVG)

**Example:**
```typescript
const GraphCanvas = React.memo(({ nodes, edges }) => {
  const nodePositions = useMemo(() =>
    calculatePositions(nodes),
    [nodes]
  );

  const handleClick = useCallback((nodeId: string) => {
    selectNode(nodeId);
  }, [selectNode]);

  return <svg>...</svg>;
});
```

### D3.js Optimization

**For large graphs (200+ nodes):**

```typescript
// Reduce simulation iterations
simulation.alphaDecay(0.1); // Faster convergence

// Limit force calculations
simulation.force('charge', d3.forceManyBody()
  .strength(-300)
  .distanceMax(300) // Limit interaction distance
);

// Use quadtree for collision detection
simulation.force('collision', d3.forceCollide()
  .radius(30)
  .iterations(2) // Reduce iterations
);
```

## Troubleshooting

### Common Issues

**D3.js not updating:**
- Check dependencies in `useEffect` are correct
- Ensure data references are stable (use `useMemo`)
- Verify SVG elements are being created

**State not persisting:**
- Check Zustand store subscriptions
- Verify selectors are correct
- Use Redux DevTools extension for debugging

**Build errors:**
- Clear node_modules: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`
- Check TypeScript errors: `npm run type-check`

## Contributing

### Code Style

**Follow:**
- ESLint rules (Airbnb config)
- Prettier formatting
- TypeScript strict mode

**Conventions:**
- Component names: PascalCase
- Hooks: camelCase starting with "use"
- Types: PascalCase with "I" prefix for interfaces
- Constants: UPPER_SNAKE_CASE

### Pull Request Process

1. Create feature branch: `git checkout -b feat/your-feature`
2. Write tests for new features
3. Ensure all tests pass: `npm run test`
4. Type check: `npm run type-check`
5. Lint: `npm run lint --fix`
6. Commit with conventional commits: `feat: add graph export`
7. Push and create PR

---

**Version:** 1.0.0
**Stack:** React + TypeScript + D3.js + Zustand + Vite
**Updated:** February 2026

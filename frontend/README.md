# WikiGR Interactive Visualization - User Guide

Interactive web interface for exploring Wikipedia knowledge graphs with semantic search and visual graph traversal.

## Quick Start

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open browser to http://localhost:5173
```

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Features Overview

### Graph Visualization

**Force-directed graph** showing articles as nodes and links as edges.

- **Nodes**: Color-coded by category, sized by connection count
- **Edges**: Thickness represents link strength
- **Zoom**: Mouse wheel or pinch gesture
- **Pan**: Click and drag background
- **Select**: Click node to view details

### Semantic Search

**Find articles by meaning**, not just keywords.

```
Query: "artificial intelligence"
Results: Machine Learning, Neural Networks, Deep Learning
Similarity: 0.87, 0.82, 0.79
```

**How to use:**
1. Enter search term in top search bar
2. Press Enter or click Search
3. Results appear in sidebar ranked by similarity
4. Click result to jump to node in graph

### Graph Traversal

**Explore link neighborhoods** around any article.

**Expand from node:**
1. Click article node in graph
2. Click "Expand" button in detail panel
3. New linked articles appear with animated entrance
4. Maximum 2 hops from any seed article

**Breadth control:**
- Limit visible articles (10, 25, 50, 100, All)
- Filter by category (dropdown)
- Show/hide edge labels

### Filters

**Category Filter:**
- Computer Science
- Mathematics
- Physics
- Biology
- History
- All Categories

**Similarity Threshold:**
- Slider: 0.0 (show all) to 1.0 (exact matches only)
- Default: 0.5 (moderate similarity)

**Graph Depth:**
- 1 hop: Direct links only
- 2 hops: Friends-of-friends (default)
- 3 hops: Extended neighborhood

### PWA Capabilities

**Install as app** on mobile or desktop:

**Mobile (iOS/Android):**
1. Open in browser
2. Tap Share button
3. Select "Add to Home Screen"
4. App icon appears on home screen

**Desktop (Chrome/Edge):**
1. Click install icon in address bar
2. Or: Menu → Install WikiGR
3. App opens in standalone window

**Offline mode:**
- Previously loaded graphs cached
- Search history available offline
- New searches require connection
- Status indicator shows connection state

## User Interface

### Layout

```
┌──────────────────────────────────────────────────────┐
│  [Search Bar]  [Category] [Limit] [☰ Menu]          │
├──────────┬───────────────────────────────────────────┤
│          │                                           │
│  Search  │                                           │
│  Results │         Graph Visualization              │
│          │         (Force-directed D3.js)           │
│  [List]  │                                           │
│          │                                           │
│          │                                           │
├──────────┤                                           │
│          │                                           │
│  Detail  │                                           │
│  Panel   │                                           │
│          │                                           │
│  [Info]  │                                           │
│  [Expand]│                                           │
│          │                                           │
└──────────┴───────────────────────────────────────────┘
```

### Controls

**Toolbar (Top):**
- Search input with autocomplete
- Category filter dropdown
- Node limit slider
- Menu button (settings, help, about)

**Sidebar (Left):**
- Search results list (collapsible)
- Selected node details
- Expand/collapse buttons
- Link to Wikipedia article

**Graph Canvas (Center):**
- Interactive force-directed graph
- Mouse/touch controls
- Zoom controls (bottom-right)
- Legend (top-right)

### Keyboard Shortcuts

| Key       | Action                   |
| --------- | ------------------------ |
| `/`       | Focus search bar         |
| `Esc`     | Clear selection          |
| `Space`   | Toggle sidebar           |
| `+`       | Zoom in                  |
| `-`       | Zoom out                 |
| `0`       | Reset zoom               |
| `f`       | Toggle fullscreen        |
| `r`       | Re-run layout simulation |
| `c`       | Center selected node     |
| `?`       | Show keyboard shortcuts  |

## Usage Examples

### Example 1: Explore Machine Learning

```
1. Enter "Machine Learning" in search
2. Click top result (similarity: 1.0)
3. Graph loads with ML article as center
4. Click "Expand" to load linked articles
5. Filter to "Computer Science" category
6. Adjust similarity threshold to 0.7
7. Explore Neural Networks, Deep Learning nodes
```

### Example 2: Find Related Physics Topics

```
1. Search "Quantum Mechanics"
2. Set category filter to "Physics"
3. Set depth to 2 hops
4. Limit to 50 nodes
5. Click interesting nodes to read summaries
6. Right-click node → "Open in Wikipedia"
```

### Example 3: Semantic Discovery

```
1. Search "learning from data"
2. Results: Machine Learning (0.89), Statistics (0.76)
3. Graph shows semantic relationships
4. Discover: Supervised Learning, Regression, Classification
5. Expand from Statistics → Probability Theory
6. Find unexpected connections
```

## Troubleshooting

### Graph Not Loading

**Problem:** White screen or loading spinner persists

**Solutions:**
1. Check browser console (F12) for errors
2. Verify backend is running: `http://localhost:8000/health`
3. Clear browser cache: Ctrl+Shift+Delete
4. Disable browser extensions
5. Try incognito/private mode

### Slow Performance

**Problem:** Graph lags with many nodes

**Solutions:**
1. Reduce node limit to 50 or fewer
2. Disable edge labels in settings
3. Use category filter to reduce scope
4. Close other browser tabs
5. Restart browser

### Search Returns No Results

**Problem:** "No results found" for valid queries

**Solutions:**
1. Check spelling
2. Try broader terms: "AI" instead of "artificial general intelligence"
3. Remove category filter (try "All")
4. Check backend logs for errors
5. Verify database contains articles

### PWA Install Not Available

**Problem:** Install button doesn't appear

**Solutions:**
1. Use Chrome/Edge (Firefox limited support)
2. Ensure HTTPS (or localhost)
3. Check manifest.json loads: `/manifest.json`
4. Verify service worker registered: DevTools → Application
5. Clear site data and reload

### Offline Mode Not Working

**Problem:** "No connection" error offline

**Solutions:**
1. Load pages while online first (priming cache)
2. Check service worker status: DevTools → Application
3. Verify cache storage: Application → Cache Storage
4. Update service worker: Shift+Reload
5. Reinstall PWA

### Zoom Controls Not Responding

**Problem:** Can't zoom or pan graph

**Solutions:**
1. Click graph canvas to focus
2. Use mouse wheel, not trackpad (sometimes)
3. Reset zoom: Press `0` key
4. Disable browser zoom (Ctrl+0)
5. Check for JavaScript errors (F12)

## Advanced Usage

### URL Parameters

**Deep linking** to specific views:

```
# Load specific article
http://localhost:5173/?article=Machine+Learning

# With filters
http://localhost:5173/?article=Quantum+Mechanics&category=Physics&depth=2

# Search query
http://localhost:5173/?search=neural+networks&limit=25
```

**Parameters:**
- `article`: Initial article title
- `search`: Search query
- `category`: Category filter
- `depth`: Graph depth (1-3)
- `limit`: Node limit
- `threshold`: Similarity threshold (0.0-1.0)

### Export Graph

**Save graph** as image or data:

```
1. Click Menu (☰) → Export
2. Choose format:
   - PNG: Static image
   - SVG: Vector graphics
   - JSON: Graph data
   - CSV: Node/edge lists
3. Click Download
```

### Custom Layouts

**Switch layout algorithms:**

```
1. Menu → Settings → Layout
2. Options:
   - Force (default): Organic, dynamic
   - Hierarchical: Tree structure
   - Radial: Circular arrangement
   - Grid: Regular spacing
3. Adjust parameters (strength, distance, charge)
```

## Browser Support

| Browser        | Version | Support |
| -------------- | ------- | ------- |
| Chrome/Edge    | 90+     | Full    |
| Firefox        | 88+     | Full    |
| Safari         | 14+     | Full    |
| Mobile Safari  | 14+     | Full    |
| Mobile Chrome  | 90+     | Full    |
| Samsung        | 14+     | Full    |

**Requirements:**
- ES2020+ JavaScript
- CSS Grid and Flexbox
- Service Worker API
- IndexedDB
- WebGL (optional, for GPU rendering)

## Performance Tips

**For large graphs (100+ nodes):**

1. **Use filters** to reduce visible nodes
2. **Disable labels** (settings → Show Labels: off)
3. **Increase simulation timeout** (settings → Layout → Max Iterations: 50)
4. **Use Chrome** (best D3.js performance)
5. **Enable GPU acceleration** (chrome://flags)

**For slow networks:**

1. **Enable compression** (backend gzip)
2. **Reduce initial load** (limit=10)
3. **Use progressive loading** (expand incrementally)
4. **Cache aggressively** (PWA precaching)

## Privacy & Data

**Local storage:**
- Search history (IndexedDB, max 100 entries)
- Cached graphs (Cache API, max 50 MB)
- User preferences (localStorage)

**Network requests:**
- Search queries sent to backend
- Graph data fetched on-demand
- No tracking or analytics
- No third-party requests

**Clear data:**
```
1. Menu → Settings → Privacy
2. Click "Clear Cache"
3. Or: Browser settings → Clear site data
```

## Getting Help

**In-app help:**
- Press `?` for keyboard shortcuts
- Menu → Help → User Guide (this document)
- Menu → About → Version info

**Report issues:**
- GitHub Issues: https://github.com/yourusername/wikigr
- Include: Browser, version, error message, steps to reproduce

---

**Version:** 1.0.0
**Updated:** February 2026
**License:** MIT

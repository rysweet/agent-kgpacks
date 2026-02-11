# WikiGR Frontend - Quick Start

## Installation

```bash
cd frontend/
npm install
```

## Development

```bash
# Start development server
npm run dev

# Application runs at http://localhost:5173
# API proxy configured for http://localhost:8000
```

## Testing

```bash
# Run tests
npm test

# Run tests in CI mode
npm test -- --run

# Generate coverage report
npm run test:coverage
```

## Building

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Status

- **Tests:** 55/80 passing (68.75%)
- **Core Features:** ✅ Complete
- **PWA Support:** ✅ Configured
- **TypeScript:** ✅ Strict mode
- **API Integration:** ✅ With retry logic

## Environment Variables

Create `.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

## Architecture

- **Framework:** React 18 + TypeScript 5
- **Build:** Vite 5
- **State:** Zustand 4
- **Visualization:** D3.js 7
- **Styling:** Tailwind CSS 3
- **Testing:** Vitest + React Testing Library
- **PWA:** Vite PWA Plugin (Workbox)

## Key Components

- `src/components/Graph/GraphCanvas.tsx` - D3.js force-directed graph
- `src/components/Search/SearchBar.tsx` - Search with autocomplete
- `src/components/Sidebar/NodeInfo.tsx` - Article details panel
- `src/components/Sidebar/FilterPanel.tsx` - Filters UI
- `src/store/graphStore.ts` - Zustand state management
- `src/services/api.ts` - API client with retry logic

## Available Scripts

```bash
npm run dev         # Start dev server
npm run build       # Build for production
npm run preview     # Preview production build
npm test            # Run tests in watch mode
npm run test:coverage # Generate coverage report
npm run type-check  # TypeScript type checking
npm run lint        # ESLint code linting
```

## Browser Requirements

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- ES2020+ support
- Service Worker API (for PWA)

## Documentation

- **User Guide:** `README.md`
- **Developer Guide:** `DEVELOPMENT.md`
- **PWA Guide:** `PWA.md`
- **Implementation Report:** `../IMPLEMENTATION_REPORT.md`

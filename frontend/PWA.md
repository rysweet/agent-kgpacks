# WikiGR PWA Guide

Progressive Web App capabilities for offline access and native-like experience.

## What is a PWA?

WikiGR is a **Progressive Web App**, meaning it can be installed on your device like a native app while being built with web technologies.

**Benefits:**
- **Install on home screen** (mobile/desktop)
- **Works offline** (cached data)
- **Fast loading** (service worker caching)
- **Native feel** (fullscreen, app icon)
- **Automatic updates** (no app store)

## Installation

### Mobile (iOS)

**Requirements:**
- Safari 14+ or Chrome 90+
- iOS 14+

**Steps:**
1. Open https://wikigr.example.com in Safari
2. Tap the **Share** button (box with arrow)
3. Scroll down and tap **Add to Home Screen**
4. Edit name if desired (e.g., "WikiGR")
5. Tap **Add**
6. App icon appears on home screen

**Result:**
- Launches in fullscreen mode
- No Safari UI (address bar, tabs)
- Appears in app switcher
- Badge notification support

### Mobile (Android)

**Requirements:**
- Chrome 90+ or Edge 90+
- Android 8+

**Steps:**
1. Open https://wikigr.example.com in Chrome
2. Tap **Menu** (⋮) → **Add to Home Screen**
3. Or: Tap the **Install** banner at bottom
4. Confirm installation
5. App icon appears on home screen

**Result:**
- Launches in standalone window
- Chrome controls hidden
- Appears in app drawer
- Fast startup

### Desktop (Windows/Mac/Linux)

**Requirements:**
- Chrome 90+, Edge 90+, or Brave 1.30+

**Steps - Chrome:**
1. Open https://wikigr.example.com
2. Click **Install** icon in address bar
   - Or: Menu (⋮) → **Install WikiGR...**
3. Click **Install** in dialog
4. App opens in standalone window

**Steps - Edge:**
1. Open https://wikigr.example.com
2. Click **App available** icon in address bar
3. Click **Install**

**Result:**
- Desktop app icon (Windows: Start Menu, Mac: Applications)
- Standalone window (no browser UI)
- Taskbar/dock integration
- OS-level window management

## Offline Capabilities

### What Works Offline

**Full functionality:**
- **Previously loaded graphs** (cached)
- **Search history** (local IndexedDB)
- **Viewed article details** (cached)
- **UI interactions** (zoom, pan, filters)
- **Settings** (stored locally)

**Limited functionality:**
- **New searches** (requires connection)
- **Expand nodes** (needs API)
- **Latest article updates** (served from cache)

### Cache Strategy

**Caching layers:**

1. **App Shell** (precached)
   - HTML, CSS, JavaScript bundles
   - Loaded instantly offline

2. **API Responses** (runtime cache)
   - Graph data (24 hour TTL)
   - Search results (1 hour TTL)
   - Article details (7 day TTL)

3. **Assets** (cache-first)
   - Icons, images
   - Fonts

**Storage limits:**
- Chrome: ~6% of free disk space
- Typical: 50-100 MB cached data
- Auto-eviction when storage full

### Checking Offline Status

**Visual indicator:**
```
┌────────────────────────────────┐
│ 🌐 Online  ✓                   │  (Green)
│ ⚠️ Offline - Limited features  │  (Yellow)
└────────────────────────────────┘
```

**In code:**
```typescript
import { useOffline } from './hooks/useOffline';

function App() {
  const isOffline = useOffline();

  return (
    <div>
      {isOffline && (
        <Banner type="warning">
          Offline mode: New searches unavailable
        </Banner>
      )}
      {/* ... */}
    </div>
  );
}
```

## Service Worker

### What It Does

**Handles:**
- Cache API responses
- Serve cached content offline
- Background sync (queue failed requests)
- Push notifications (future)
- Update app in background

**Strategy:** Network-first with cache fallback

```
Request → Network (try) → Success → Update cache → Return
                       ↓ Fail
                    Cache (try) → Success → Return
                                ↓ Fail
                            Offline page
```

### Lifecycle

**States:**
1. **Installing:** Downloading and caching app shell
2. **Installed:** Ready to activate
3. **Activating:** Cleaning old caches
4. **Activated:** Controlling pages
5. **Redundant:** Replaced by newer version

**Update flow:**
```
New version deployed
     ↓
Service worker detects update
     ↓
Download new files in background
     ↓
Show update notification
     ↓
User clicks "Update"
     ↓
Activate new service worker
     ↓
Reload app
```

### Manual Update

**Force update:**

```javascript
// In browser console
navigator.serviceWorker.getRegistrations()
  .then(registrations => {
    registrations.forEach(reg => reg.update());
  });

// Then reload page
location.reload();
```

**Or use UI:**
```
Menu → Settings → About → Check for Updates
```

### Debugging Service Worker

**Chrome DevTools:**

1. Open DevTools (F12)
2. Go to **Application** tab
3. Click **Service Workers** in sidebar

**Useful actions:**
- **Unregister:** Remove service worker
- **Update:** Force update check
- **Bypass for network:** Test without cache
- **Offline:** Simulate offline mode

**View cache:**
1. **Application** → **Cache Storage**
2. Expand cache name
3. View cached URLs and responses

**Clear cache:**
```
Application → Clear storage → Clear site data
```

## Manifest Configuration

### App Manifest

**File:** `public/manifest.json`

```json
{
  "name": "WikiGR Interactive Visualization",
  "short_name": "WikiGR",
  "description": "Explore Wikipedia knowledge graphs with semantic search",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#3b82f6",
  "orientation": "any",
  "scope": "/",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ],
  "categories": ["education", "reference"],
  "shortcuts": [
    {
      "name": "Search",
      "short_name": "Search",
      "description": "Search Wikipedia articles",
      "url": "/?action=search",
      "icons": [{ "src": "/icons/search.png", "sizes": "96x96" }]
    },
    {
      "name": "Recent",
      "short_name": "Recent",
      "description": "View recent searches",
      "url": "/?action=recent",
      "icons": [{ "src": "/icons/recent.png", "sizes": "96x96" }]
    }
  ],
  "screenshots": [
    {
      "src": "/screenshots/desktop.png",
      "sizes": "1280x720",
      "type": "image/png",
      "form_factor": "wide"
    },
    {
      "src": "/screenshots/mobile.png",
      "sizes": "750x1334",
      "type": "image/png"
    }
  ]
}
```

### Display Modes

**Options:**

| Mode         | Description               | Fallback    |
| ------------ | ------------------------- | ----------- |
| `fullscreen` | No browser UI             | standalone  |
| `standalone` | No browser UI, OS chrome  | minimal-ui  |
| `minimal-ui` | Minimal browser UI        | browser     |
| `browser`    | Standard browser tab      | -           |

**WikiGR uses:** `standalone` (app-like experience)

**Detect mode:**
```typescript
function getDisplayMode() {
  if (window.matchMedia('(display-mode: standalone)').matches) {
    return 'standalone';
  }
  if (window.matchMedia('(display-mode: fullscreen)').matches) {
    return 'fullscreen';
  }
  return 'browser';
}

// Track in analytics
const displayMode = getDisplayMode();
console.log('Display mode:', displayMode);
```

## Icons and Splash Screens

### Icon Requirements

**Sizes needed:**

| Size    | Purpose               | Platform          |
| ------- | --------------------- | ----------------- |
| 192x192 | Home screen           | Android           |
|512x512 | App drawer, splash    | Android           |
| 180x180 | Home screen           | iOS               |
| 152x152 | iPad home screen      | iOS               |
| 120x120 | iPhone home screen    | iOS               |
| 48x48   | Desktop app icon      | Windows           |

**Format:**
- PNG (transparent background for maskable)
- SVG (scalable, preferred)

**Maskable icons:**
- Safe area: 80% of canvas
- Important content within circle
- Example: Logo centered, no text near edges

### Splash Screens

**Android:** Auto-generated from manifest
- Background color: `background_color`
- Icon: Largest icon from manifest
- Shown during app launch

**iOS:** Auto-generated in Safari 15+
- Background color from manifest
- Icon centered
- Customize with meta tags:

```html
<link rel="apple-touch-startup-image" href="/splash-2048x2732.png" media="(device-width: 1024px)">
```

## Push Notifications (Future)

**Planned features:**

- **New article alerts:** When related articles added
- **Update notifications:** New app version available
- **Search suggestions:** Based on history

**Implementation status:** Not yet implemented

**Setup (when ready):**
```typescript
// Request permission
const permission = await Notification.requestPermission();

if (permission === 'granted') {
  // Subscribe to push service
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: PUBLIC_VAPID_KEY
  });

  // Send subscription to backend
  await api.post('/api/v1/notifications/subscribe', subscription);
}
```

## Background Sync

**Feature:** Queue failed requests when offline, retry when online

**Use cases:**
- Search queries while offline
- Expand node actions
- Settings updates

**Implementation:**
```typescript
// Service worker
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-searches') {
    event.waitUntil(syncSearches());
  }
});

async function syncSearches() {
  const searches = await db.searches.where({ synced: false }).toArray();

  for (const search of searches) {
    try {
      await fetch('/api/v1/search?query=' + search.query);
      await db.searches.update(search.id, { synced: true });
    } catch (error) {
      console.error('Sync failed:', error);
    }
  }
}
```

**Register sync:**
```typescript
// Client code
if ('sync' in registration) {
  await registration.sync.register('sync-searches');
}
```

## Storage Management

### IndexedDB

**Stores:**

1. **graphs:** Cached graph data
   - Key: article title + depth
   - Value: { nodes, edges, timestamp }
   - Size: ~100 KB per graph

2. **searches:** Search history
   - Key: auto-increment
   - Value: { query, timestamp, results }
   - Limit: 100 most recent

3. **settings:** User preferences
   - Key: setting name
   - Value: setting value

**Schema:**
```typescript
import Dexie from 'dexie';

const db = new Dexie('WikiGR');

db.version(1).stores({
  graphs: 'key, timestamp',
  searches: '++id, timestamp',
  settings: 'key'
});
```

### Cache API

**Caches:**

1. **wikigr-static-v1:** App shell
   - HTML, CSS, JS bundles
   - Icons, fonts
   - Precached on install

2. **wikigr-api-v1:** API responses
   - Graph data
   - Search results
   - Runtime caching

3. **wikigr-assets-v1:** Images
   - Article images (future)
   - User uploads (future)

**Clear old caches:**
```typescript
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name.startsWith('wikigr-') && name !== CURRENT_CACHE)
          .map(name => caches.delete(name))
      );
    })
  );
});
```

## Troubleshooting PWA Issues

### Install Button Not Showing

**Causes:**
1. Already installed
2. Non-HTTPS (except localhost)
3. Missing/invalid manifest.json
4. Service worker not registered

**Solutions:**
```bash
# Check manifest
curl https://wikigr.example.com/manifest.json

# Verify HTTPS
# Chrome DevTools → Security tab

# Check service worker
# Chrome DevTools → Application → Service Workers
```

### App Not Working Offline

**Causes:**
1. Service worker not activated
2. Resources not cached
3. Cache expired

**Solutions:**
```javascript
// Check service worker status
navigator.serviceWorker.ready.then(registration => {
  console.log('SW active:', registration.active);
});

// Check cache
caches.keys().then(keys => console.log('Caches:', keys));

// Force update
navigator.serviceWorker.getRegistrations()
  .then(regs => regs.forEach(reg => reg.update()));
```

### Old Version Cached

**Problem:** Updates not appearing

**Solutions:**
1. **Hard reload:** Ctrl+Shift+R (Windows) / Cmd+Shift+R (Mac)
2. **Clear cache:** DevTools → Application → Clear storage
3. **Unregister SW:** DevTools → Application → Unregister
4. **Bypass SW:** DevTools → Application → Bypass for network
5. **Wait:** Service worker updates automatically (check every 24h)

### Install Failed on iOS

**Causes:**
1. Using Chrome (not supported, use Safari)
2. iOS < 14
3. Private browsing mode

**Solutions:**
- Use Safari
- Update iOS
- Exit private browsing

### Large Cache Size

**Check usage:**
```javascript
if ('storage' in navigator && 'estimate' in navigator.storage) {
  navigator.storage.estimate().then(estimate => {
    console.log('Used:', estimate.usage / 1024 / 1024, 'MB');
    console.log('Quota:', estimate.quota / 1024 / 1024, 'MB');
  });
}
```

**Reduce cache:**
```
Settings → Storage → Clear Cache
```

**Or programmatically:**
```typescript
async function clearOldCache() {
  const db = new Dexie('WikiGR');
  const twoWeeksAgo = Date.now() - 14 * 24 * 60 * 60 * 1000;

  await db.graphs.where('timestamp').below(twoWeeksAgo).delete();
  await db.searches.where('timestamp').below(twoWeeksAgo).delete();
}
```

## Best Practices

### For Users

1. **Install the app** for best experience
2. **Load graphs while online** to cache them
3. **Update regularly** when prompted
4. **Clear cache** if experiencing issues

### For Developers

1. **Test offline first** during development
2. **Version caches** properly
3. **Handle updates gracefully** (prompt user)
4. **Monitor cache size** (set limits)
5. **Provide offline feedback** (UI indicators)

## Performance Metrics

**Lighthouse PWA audit:**

| Metric                | Target | Actual |
| --------------------- | ------ | ------ |
| Progressive Web App   | 100    | 100    |
| Fast and reliable     | ✓      | ✓      |
| Installable           | ✓      | ✓      |
| PWA Optimized         | ✓      | ✓      |
| Works offline         | ✓      | ✓      |
| Service worker        | ✓      | ✓      |
| HTTPS                 | ✓      | ✓      |
| Splash screen         | ✓      | ✓      |
| Themed address bar    | ✓      | ✓      |

**Run audit:**
```bash
# Chrome DevTools
Lighthouse → Progressive Web App → Generate report

# CLI
npm install -g lighthouse
lighthouse https://wikigr.example.com --view
```

---

**PWA Version:** 1.0.0
**Workbox Version:** 7.0.0
**Browser Support:** Chrome 90+, Safari 14+, Edge 90+
**Updated:** February 2026

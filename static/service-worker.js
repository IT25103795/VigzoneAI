/* Vigzone AI offline service worker */
const VIGZONE_SW_VERSION = 'vigzone-v5.0.0-production-r20';
const UI_ASSET_REVISION = 'projects-r1';
const SHELL_CACHE = `vigzone-shell-${VIGZONE_SW_VERSION}`;
const RUNTIME_CACHE = `vigzone-runtime-${VIGZONE_SW_VERSION}`;

const APP_SHELL = [
  '/',
  '/chat',
  '/offline',
  '/static/index.html',
  `/static/css/styles.css?v=${UI_ASSET_REVISION}`,
  `/static/js/app.js?v=${UI_ASSET_REVISION}`,
  `/static/js/projects.js?v=${UI_ASSET_REVISION}`,
  '/static/landing.html',
  '/static/offline.html',
  '/static/vendor/jszip.min.js',
  '/manifest.json',
  '/static/icons/favicon.svg',
  '/static/icons/vigzone-icon.svg',
  '/static/icons/vigzone-doodles.svg?v=doodle-r1',
  '/static/icons/vigzone-icon-192.png',
  '/static/icons/vigzone-icon-512.png',
  '/api/public/config',
  '/api/app/version'
];

const CRITICAL_UI_ASSETS = new Set([
  '/static/css/styles.css',
  '/static/js/app.js',
  '/static/js/projects.js'
]);

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(cache => cache.addAll(APP_SHELL.map(url => new Request(url, {cache: 'reload'}))).catch(() => undefined))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key.startsWith('vigzone-') && ![SHELL_CACHE, RUNTIME_CACHE].includes(key))
          .map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

async function matchAppCache(request) {
  const runtimeCache = await caches.open(RUNTIME_CACHE);
  const runtimeResponse = await runtimeCache.match(request);
  if (runtimeResponse) return runtimeResponse;

  const shellCache = await caches.open(SHELL_CACHE);
  return shellCache.match(request);
}

async function networkFirst(request, fallbackUrl) {
  const cache = await caches.open(RUNTIME_CACHE);
  try {
    const response = await fetch(request, {cache: 'no-store'});
    if (response && response.ok) cache.put(request, response.clone()).catch(() => undefined);
    return response;
  } catch (error) {
    const cached = await matchAppCache(request);
    if (cached) return cached;
    if (fallbackUrl) {
      const fallback = await matchAppCache(fallbackUrl);
      if (fallback) return fallback;
    }
    throw error;
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  const cached = await matchAppCache(request);
  const fetchPromise = fetch(request).then(response => {
    if (response && response.ok) cache.put(request, response.clone()).catch(() => undefined);
    return response;
  }).catch(() => cached);
  return cached || fetchPromise;
}

function offlineJson(message, status = 503) {
  return new Response(JSON.stringify({
    offline: true,
    detail: message,
    error: message
  }), {
    status,
    headers: {'Content-Type': 'application/json'}
  });
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Mutating/API calls cannot be fulfilled offline, but return a clean JSON error.
  if (request.method !== 'GET') {
    if (url.pathname.startsWith('/api/')) {
      event.respondWith(
        fetch(request).catch(() => offlineJson('Offline mode: saved chats are available, but this action needs internet.'))
      );
    }
    return;
  }

  if (request.mode === 'navigate') {
    // Cache only the fixed app shell. Token-bearing account pages (verification,
    // password reset) and public share URLs must never be persisted by the PWA.
    if (['/', '/chat', '/offline'].includes(url.pathname) && !url.search) {
      event.respondWith(networkFirst(request, '/static/index.html').catch(() => caches.match('/static/offline.html')));
    } else {
      event.respondWith(fetch(request).catch(() => caches.match('/static/offline.html')));
    }
    return;
  }

  if (url.pathname === '/api/public/config' || url.pathname === '/api/app/version') {
    event.respondWith(networkFirst(request, null).catch(() => caches.match(request).then(cached => cached || offlineJson('Offline mode: using saved app settings.'))));
    return;
  }

  // CSS and application JavaScript must be current whenever the network is
  // available. Fall back to the app caches only when the request is offline.
  if (CRITICAL_UI_ASSETS.has(url.pathname)) {
    event.respondWith(networkFirst(request, null));
    return;
  }

  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json') {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }
});

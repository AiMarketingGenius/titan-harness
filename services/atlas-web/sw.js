// sw.js — Atlas PWA service worker (sprint scaffold).
// Cache-first for static shell, network-first for /api/* and /ws/*.
const CACHE = 'atlas-v1';
const SHELL = [
  '/atlas/',
  '/atlas/index.html',
  '/atlas/styles.css',
  '/atlas/orb.js',
  '/atlas/app.js',
  '/atlas/manifest.json',
];

self.addEventListener('install', (ev) => {
  ev.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (ev) => {
  const url = new URL(ev.request.url);
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/')) {
    return; // passthrough
  }
  ev.respondWith(
    caches.match(ev.request).then((hit) => hit || fetch(ev.request))
  );
});

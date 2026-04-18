/**
 * AMG Mobile Command — service worker.
 *
 * Responsibilities:
 * - Minimal offline app-shell cache (HTML + built JS/CSS bundles)
 * - Push-event handler: display notifications (iOS requires user-visible)
 * - Notificationclick → focus or open the PWA
 *
 * Intentionally small. Vite Workbox integration + runtime-caching strategy
 * arrive in Step 6.4-b (Lumina polish pass) if Lumina scores call for it.
 */

const CACHE_VERSION = "amg-mobile-cmd-v1";
const OFFLINE_URL = "/";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll([OFFLINE_URL])),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_VERSION)
          .map((k) => caches.delete(k)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  // Network-first for API; cache-first for everything else (fall-through)
  if (request.url.includes("/api/")) {
    return; // let the browser handle it normally
  }

  event.respondWith(
    fetch(request)
      .then((resp) => {
        const clone = resp.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone)).catch(() => {});
        return resp;
      })
      .catch(() => caches.match(request).then((cached) => cached || caches.match(OFFLINE_URL))),
  );
});

self.addEventListener("push", (event) => {
  let payload = { title: "AMG Command", body: "New notification", data: {} };
  try {
    if (event.data) payload = { ...payload, ...event.data.json() };
  } catch (err) {
    // non-JSON push payload — keep defaults
  }

  event.waitUntil(
    self.registration.showNotification(payload.title || "AMG Command", {
      body: payload.body || "",
      icon: "/favicon.svg",
      badge: "/favicon.svg",
      data: payload.data || {},
      tag: payload.tag || "amg-mobile",
      renotify: !!payload.renotify,
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const c of clients) {
        if ("focus" in c) return c.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    }),
  );
});

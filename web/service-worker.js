/* Dice Lab service worker — offline shell, no external CDN.
 *
 * Policy:
 *   - Static shell/assets: cache-first
 *   - API + simulation endpoints: network-first (never cached)
 *   - Navigation: network-first, cached app shell offline
 *   - POST is never intercepted
 */
'use strict';

const VERSION = 'dice-lab-v2.0.0';
const SHELL = [
  '/',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-512.png',
  '/icons/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(SHELL))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

function offlineJson() {
  return new Response(
    JSON.stringify({
      ok: false,
      error: 'ออฟไลน์ — ต้องเชื่อมต่อเซิร์ฟเวอร์ Dice Lab ผ่าน Tailscale',
    }),
    { status: 503, headers: { 'Content-Type': 'application/json; charset=utf-8' } }
  );
}

function isApi(pathname) {
  return (
    pathname === '/ping' ||
    pathname === '/get' ||
    pathname === '/set' ||
    pathname === '/presets' ||
    pathname === '/run' ||
    pathname.startsWith('/run/status') ||
    pathname === '/calc' ||
    pathname === '/csv'
  );
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Live data must never be served stale.
  if (isApi(url.pathname)) {
    event.respondWith(fetch(request).catch(() => offlineJson()));
    return;
  }

  // App shell: network-first so UI updates appear after a server restart.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put('/', copy)).catch(() => undefined);
          return response;
        })
        .catch(() => caches.match('/').then((cached) => cached || offlineJson()))
    );
    return;
  }

  // Hashed/static assets: cache-first.
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put(request, copy)).catch(() => undefined);
        }
        return response;
      });
    })
  );
});

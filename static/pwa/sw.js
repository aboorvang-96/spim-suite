/* SPIM Suite — Service Worker (network-first, static-only cache) */
const CACHE_VERSION = 'spim-suite-v1';
const STATIC_CACHE  = `${CACHE_VERSION}-static`;
const OFFLINE_URL   = '/offline/';

const PRECACHE_URLS = [
  OFFLINE_URL,
  '/static/pwa/manifest.json',
  '/static/pwa/icons/icon-192.png',
  '/static/pwa/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS).catch(() => null))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => !key.startsWith(CACHE_VERSION))
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;

  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/api/')) return;

  const isStaticAsset =
    url.pathname.startsWith('/static/') ||
    url.pathname.startsWith('/media/');

  event.respondWith(
    fetch(req)
      .then((networkResponse) => {
        if (isStaticAsset && networkResponse && networkResponse.ok) {
          const clone = networkResponse.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(req, clone));
        }
        return networkResponse;
      })
      .catch(() =>
        caches.match(req).then((cached) => {
          if (cached) return cached;
          if (req.mode === 'navigate') {
            return caches.match(OFFLINE_URL);
          }
          return new Response('', { status: 504, statusText: 'Offline' });
        })
      )
  );
});

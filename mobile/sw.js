/* DCReader service worker: cache toan bo giao dien de mo khong can mang.
   Truyen nam trong IndexedDB nen khong lien quan den cache nay. */
'use strict';

const CACHE = 'dcreader-v4';
const SHELL = ['./', 'index.html', 'style.css', 'app.js', 'vbook.js',
  'nguon-vbook.js', 'manifest.json', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  // chi lo giao dien cua chinh app; goi den web nguon (API truyen) de nguyen
  if (new URL(e.request.url).origin !== self.location.origin) return;
  // co mang: luon lay ban moi (khoi bi ket file cu); mat mang: xai cache
  e.respondWith(
    fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => { });
      return res;
    }).catch(() => caches.match(e.request, { ignoreSearch: true })),
  );
});

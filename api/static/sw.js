// Service Worker — 简单离线缓存
const CACHE_NAME = 'xhs-publisher-v1';
const URLS_TO_CACHE = [
    '/',
    '/static/style.css',
    '/static/app.js',
    '/static/manifest.json',
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(URLS_TO_CACHE))
    );
    self.skipWaiting();
});

self.addEventListener('fetch', event => {
    // API 请求不缓存
    if (event.request.url.includes('/api/') || event.request.url.includes('/ws/')) {
        return;
    }
    event.respondWith(
        caches.match(event.request).then(r => r || fetch(event.request))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
});

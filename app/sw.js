// Offline-Cache der App-Shell und des öffentlichen Rechtsdatenpakets (keine Personendaten, keine Weisungen).
// Strategie: Netz zuerst (immer aktuellste Fassung), bei fehlendem Netz aus dem Cache.
// CACHE wird von tools/build_rechtsdaten.py an die Datenversion angepasst.
const CACHE = "streifenhelfer-202610191521";
const ASSETS = ["./", "index.html", "regelwerk.js", "rechtsdaten.js", "rechtsdaten.json", "manifest.webmanifest", "icon-180.png", "icon-192.png", "icon-512.png"];
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())
));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin || e.request.method !== "GET") return; // Weisungsserver u. a. nie cachen
  if (!ASSETS.some(a => url.pathname.endsWith("/" + a.replace("./", "")))) return;
  e.respondWith(
    fetch(e.request, {cache: "no-cache"})
      .then(r => { if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); } return r; })
      .catch(() => caches.match(e.request, {ignoreSearch: true}))
  );
});

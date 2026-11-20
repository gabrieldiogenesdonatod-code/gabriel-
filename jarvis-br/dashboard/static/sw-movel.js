// Fork PT-BR 2.0: service worker do app do celular. Guarda só a "casca" do app
// (página, manifesto, ícone) para ele abrir mesmo com o PC desligado.
// As APIs do PC e do Gemini sempre vão para a rede (nada de resposta velha).
const CACHE = "jarvis-movel-v1";
const CASCA = ["/movel", "/movel.webmanifest", "/icone-jarvis.svg"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(CASCA)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || !CASCA.includes(u.pathname)) return;
  // rede primeiro (versão nova quando o PC está no ar); sem rede, a cópia guardada
  e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(CACHE).then(k => k.put(e.request, c)); return r; })
    .catch(() => caches.match(e.request)));
});
self.addEventListener("notificationclick", e => { e.notification.close(); e.waitUntil(self.clients.openWindow("/movel")); });

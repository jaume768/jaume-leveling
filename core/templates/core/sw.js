/* Service worker de la app instalada.

   Deliberadamente minimo: los datos (XP, misiones, facturas) se piden siempre
   a la red, porque una cifra vieja sacada de cache mentiria. Solo se guardan
   la pantalla "sin conexion" y lo que necesita para pintarse. */
{% load static %}
const CACHE = "leveling-v2";
const SIN_CONEXION = "{% url 'sin_conexion' %}";
const PRECARGA = [SIN_CONEXION, "{% static 'css/app.css' %}", "{% static 'img/app/icono-192.png' %}"];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECARGA)));
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys().then((claves) =>
      Promise.all(claves.filter((c) => c !== CACHE).map((c) => caches.delete(c)))
    )
  );
  self.clients.claim();
});

/* Navegacion: siempre a la red; si no hay, la pantalla sin conexion. */
self.addEventListener("fetch", (evento) => {
  if (evento.request.mode !== "navigate") return;
  evento.respondWith(
    fetch(evento.request).catch(() => caches.match(SIN_CONEXION))
  );
});

/* Notificaciones del Sistema (Web Push). El servidor manda {titulo, cuerpo, url}. */
self.addEventListener("push", (evento) => {
  let datos = {};
  try { datos = evento.data ? evento.data.json() : {}; } catch (e) { datos = { cuerpo: evento.data && evento.data.text() }; }
  evento.waitUntil(
    self.registration.showNotification(datos.titulo || "[SISTEMA]", {
      body: datos.cuerpo || "",
      icon: "{% static 'img/app/icono-192.png' %}",
      badge: "{% static 'img/app/icono-192.png' %}",
      tag: "sistema",
      renotify: true,
      vibrate: [60, 40, 60],
      data: { url: datos.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  const destino = (evento.notification.data && evento.notification.data.url) || "/";
  evento.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((ventanas) => {
      for (const v of ventanas) {
        if ("focus" in v) { v.navigate(destino); return v.focus(); }
      }
      return clients.openWindow(destino);
    })
  );
});

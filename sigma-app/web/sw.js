/* SIGMA — service worker.
   Objectif : l'application doit s'ouvrir et rester lisible sans réseau, avec la
   dernière collecte connue, en affichant toujours sa date. Aucune donnée n'est
   inventée hors ligne : c'est le dernier fichier officiel publié qui est servi.

   Stratégies :
   - coque (HTML/CSS/JS/icône) : cache d'abord, mise à jour en arrière-plan ;
   - données (data/*.json) : réseau d'abord, repli sur la dernière copie connue.
     On ne sert jamais un fichier de données partiel ou tronqué.
*/

const VERSION = "sigma-pwa-v1";
const CACHE_COQUE = `${VERSION}-coque`;
const CACHE_DONNEES = `${VERSION}-donnees`;

const COQUE = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "icon.svg",
  "icon-192.png",
  "icon-512.png",
  "manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_COQUE)
      .then((cache) => cache.addAll(COQUE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((noms) =>
        Promise.all(
          noms
            .filter((nom) => !nom.startsWith(VERSION))
            .map((nom) => caches.delete(nom))
        )
      )
      .then(() => self.clients.claim())
  );
});

function estDonnee(url) {
  return /(^|\/)data\/[^/]+\.json$/.test(url.pathname);
}

async function reseauDAbord(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const reponse = await fetch(request);
    // On ne met en cache qu'une réponse complète et réussie.
    if (reponse && reponse.ok && reponse.status === 200) {
      const copie = reponse.clone();
      cache.put(request, copie).catch(() => {});
    }
    return reponse;
  } catch (erreur) {
    const copie = await cache.match(request, { ignoreSearch: true });
    if (copie) return copie;
    throw erreur;
  }
}

async function cacheDAbord(request, cacheName) {
  const cache = await caches.open(cacheName);
  const copie = await cache.match(request, { ignoreSearch: true });
  if (copie) {
    // Rafraîchissement silencieux, sans bloquer l'affichage.
    fetch(request)
      .then((reponse) => {
        if (reponse && reponse.ok) cache.put(request, reponse.clone()).catch(() => {});
      })
      .catch(() => {});
    return copie;
  }
  const reponse = await fetch(request);
  if (reponse && reponse.ok) cache.put(request, reponse.clone()).catch(() => {});
  return reponse;
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.endsWith("/sw.js")) return;

  if (estDonnee(url)) {
    event.respondWith(reseauDAbord(request, CACHE_DONNEES));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(CACHE_COQUE);
        return (await cache.match("index.html")) || (await cache.match("./"));
      })
    );
    return;
  }

  event.respondWith(cacheDAbord(request, CACHE_COQUE));
});

self.addEventListener("message", (event) => {
  if (event.data === "sigma:version") {
    event.source?.postMessage({ type: "sigma:version", version: VERSION });
  }
});

/* SIGMA — service worker.
   Objectif : l'application doit s'ouvrir et rester lisible sans réseau, avec la
   dernière collecte connue, en affichant toujours sa date. Aucune donnée n'est
   inventée hors ligne : c'est le dernier fichier officiel publié qui est servi.

   Stratégies (révisées le 2026-10-28) :
   - coque (HTML/CSS/JS/icônes) : RÉSEAU d'abord, repli sur le cache hors ligne.
     L'ancienne version servait le cache d'abord avec une constante de version
     jamais incrémentée : un téléphone qui avait ouvert l'app une fois gardait
     indéfiniment l'ancien app.js — six onglets alors que trois étaient
     déployés, textes supprimés qui réapparaissaient. Une application qui change
     tous les jours ne peut pas être cache-first.
   - données (data/*.json) : réseau d'abord, repli sur la dernière copie connue.
     On ne sert jamais un fichier de données partiel ou tronqué.
   - le numéro de version reste explicite : il sert au message « nouvelle
     version » côté page, jamais de cache-first.
*/

const VERSION = "sigma-pwa-v2";
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
    // `cache: "no-store"` : le cache HTTP du navigateur ne doit pas non plus
    // resservir un app.js périmé après un déploiement.
    const reponse = await fetch(request, { cache: "no-store" });
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

  // Coque et navigation : réseau d'abord, cache uniquement hors ligne.
  event.respondWith(
    reseauDAbord(request, CACHE_COQUE).catch(async () => {
      const cache = await caches.open(CACHE_COQUE);
      return (
        (await cache.match(request, { ignoreSearch: true })) ||
        (await cache.match("index.html")) ||
        (await cache.match("./")) ||
        Response.error()
      );
    })
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "sigma:version") {
    event.source?.postMessage({ type: "sigma:version", version: VERSION });
  }
});

// Smoke test de l'application dans un DOM réel (jsdom).
// But : détecter une erreur JavaScript au rendu — ce que les tests Python ne
// peuvent pas voir. Aucune assertion esthétique ici.
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const WEB = process.argv[2] || "/home/user/sigma-brvm/sigma-app/web";
const DATA = fs.readFileSync(path.join(WEB, "data/data.json"), "utf8");

const erreurs = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", (e) => erreurs.push(String(e.message || e)));
virtualConsole.on("error", (m) => erreurs.push(String(m)));

const html = fs.readFileSync(path.join(WEB, "index.html"), "utf8");
const dom = new JSDOM(html, {
  runScripts: "outside-only",
  pretendToBeVisual: true,
  url: "http://localhost/",
  virtualConsole,
});
const { window } = dom;

// fetch servant les données locales, comme le service worker le ferait hors ligne
window.fetch = (url) =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(JSON.parse(DATA)),
    text: () => Promise.resolve(DATA),
    clone() { return this; },
  });
window.matchMedia = window.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {} }));
window.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
window.scrollTo = () => {};
if (!window.HTMLDialogElement) {
  window.HTMLDialogElement = window.HTMLElement;
}
window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
window.HTMLDialogElement.prototype.close = function () { this.open = false; };

const appjs = fs.readFileSync(path.join(WEB, "app.js"), "utf8");
try {
  window.eval(appjs);
} catch (e) {
  erreurs.push("EVAL: " + e.message);
}

const attendre = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  await attendre(1200);

  const doc = window.document;
  const d = doc;
  const compte = (sel) => d.querySelectorAll(sel).length;
  const texte = d.body.textContent || "";

  const rapport = {
    erreurs,
    nav_items: compte(".nav-item"),
    nav_labels: compte(".nav-label"),
    parametres_dans_barre_basse: compte('.nav-item[data-view="parametres"]'),
    bouton_parametres_haut: compte('button[data-view-link="parametres"]'),
    etude_titre: texte.includes("Sociétés à étudier en premier"),
    etude_lignes: compte(".study-row"),
    alertes_lignes: compte(".event-row"),
    accueil_actif: !!d.querySelector("#view-accueil.is-active"),
    erreur_affichee: d.querySelector("#appMessage")?.textContent?.trim() || null,
  };

  // Ordre : la mise en avant des sociétés doit précéder les alertes.
  const cartes = [...d.querySelectorAll("#view-accueil .card")].map((c) =>
    (c.querySelector("h2")?.textContent || "").trim()
  );
  rapport.ordre_cartes = cartes.slice(0, 4);

  console.log(JSON.stringify(rapport, null, 2));
  const echec =
    erreurs.length > 0 ||
    rapport.nav_items !== 5 ||
    rapport.nav_labels !== 5 ||
    rapport.parametres_dans_barre_basse !== 0 ||
    !rapport.etude_titre ||
    rapport.etude_lignes === 0 ||
    rapport.erreur_affichee;
  process.exit(echec ? 1 : 0);
})();

# Ce que montrent les captures du 28 octobre 2026 (11 h)

Quatre constats, par ordre de gravité.

## 1. Le téléphone affichait une version périmée de l'application (cause racine)

Deux captures montrent **six onglets** (« Décision du mois », « Radar SIGMA »,
« Baisses à examiner », « Contexte & scénarios », « Marché en chiffres »,
« Documents & échéances ») et l'encadré vert « En clair » **supprimés au
déploiement du matin**, alors que GitHub Pages servait déjà la nouvelle version.

Cause : `sw.js` servait la coque (HTML/CSS/JS) **cache d'abord**, avec
`const VERSION = "sigma-pwa-v1"` jamais incrémentée. Un téléphone qui avait
ouvert l'application une fois gardait donc son `app.js` indéfiniment : le
rafraîchissement silencieux mettait bien à jour le cache, mais la page
affichée restait l'ancienne copie.

Risque associé, plus grave que l'ancienneté : le HTML est servi réseau d'abord,
le JS cache d'abord. Un `index.html` neuf pouvait donc être associé à un
`app.js` ancien — combinaison qui casse les onglets par construction.

Corrigé : coque en **réseau d'abord** (`cache: "no-store"` inclus), cache
utilisé seulement hors ligne ; `updateViaCache: "none"` ; rechargement unique
au `controllerchange` ; version `sigma-pwa-v2` qui purge les anciens caches.

## 2. Les tableaux étaient écrasés, pas défilants

Capture 1 : colonnes de ~20 px, montants coupés caractère par caractère
(« 2 / 0 / 0 / F / C / F / A »), en-têtes tronqués, « Non estimés » illisible.

Cause : `table { width: 100% }` sans `min-width`, et le garde-fou
`overflow-wrap: anywhere` posé sur `td`/`th` pour les montants. Le tableau se
comprimait donc au lieu de déborder, et le texte se repliait à chaque
caractère. `.table-wrap { overflow-x: auto }` ne servait à rien sans largeur
minimale.

Corrigé : `min-width: 620px` sur les tableaux, `white-space: nowrap` sur les
cellules numériques, et la sélection du mois n'est plus un tableau à huit
colonnes mais une liste (`pick-list`) : une ligne par société, six chiffres,
trois actions — lisible à 390 px sans défilement horizontal.

## 3. La pastille de notification sortait de la barre

`top: -4px; right: -4px` sur `.icon-badge` : la pastille chevauchait le bouton
voisin et se faisait rogner. Ramenée à `top: 1px; right: 1px`.

## 4. La recherche mobile affichait « Recherc »

Le libellé complet ne tient pas sur 390 px. Il devient « Rechercher… » sous
640 px et redevient complet au-dessus.

## 5. Donnée périmée, non corrigeable ici

« collecte du 22 oct. 2026 » contre le 28 : six séances manquent. `brvm.org`
reste injoignable depuis l'environnement d'exécution ; aucune collecte n'a pu
être lancée.

Vérifications : `pytest` **214 tests**, dont 4 nouveaux sur la stratégie du
service worker et 4 sur les défauts mobiles ; rendu jsdom **9 vues, 0 erreur
JavaScript** ; sélection du mois rendue en 8 lignes, 6 chiffres et 3 actions
chacune, sans tableau.

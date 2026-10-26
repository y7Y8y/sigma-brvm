# SIGMA — application personnelle BRVM

SIGMA est une web app statique, mobile d'abord, alimentée par les pages et PDF publics officiels de la BRVM. Aucune donnée de démonstration n'est livrée dans l'interface : si la collecte échoue, l'application le dit au lieu d'inventer des valeurs.

## Ce qui fonctionne

- Instantané officiel des cours et indices publié sur brvm.org.
- Historique de marché à deux profondeurs : 30 derniers Bulletins Officiels de la Cote pour les calculs récents de l’app, plus une **archive BOC longue persistante** (`web/data/boc_archive.json`, 260 séances du 22 septembre 2025 au 19 octobre 2026 dans la collecte v0.8) pour les horizons 60/120/250 séances, la liquidité longue, le repli maximal observé et la volatilité de prix. Clôtures, volumes, valeurs échangées, PER et rendements nets restent ceux **publiés par la BRVM** ; les performances longues sont des prix seuls, hors dividendes réinvestis et hors ajustements d’opérations sur titres.
- **Historique officiel complet des dividendes** : le collecteur suit désormais toute la pagination publiée du tableau BRVM, fusionne les avis multiples d’une même distribution (y compris rectificatifs) et rattache les anciens noms/abréviations d’émetteurs au ticker courant lorsqu’ils sont sans ambiguïté. La collecte v0.8 contient 348 distributions canoniques pour les exercices 2015–2025 ; 44 sociétés ont au moins un exercice documenté et 21 sont documentées sur les cinq derniers exercices du tableau. Chaque fiche affiche montants nets par exercice, paiements multiples additionnés, suite courante, hausses/baisses et évolution annuelle moyenne ; une absence de ligne est libellée « non documentée dans le tableau collecté », jamais transformée en dividende nul certain.
- Largeur du marché, variation médiane et concentration de la valeur échangée au dernier BOC.
- **Actualités automatisées** : annonces officielles des émetteurs BRVM (communiqués, notations, dirigeants, franchissements de seuil, assemblées), actualités BRVM, communiqués BCEAO, flux RSS UMOA-Titres et Sika Finance (étiqueté « presse »). Chaque item est daté selon ce que la source publie réellement, classé (société / marché / macro) et rattaché à un ticker seulement quand le libellé officiel ou une phrase distinctive le permet. Une source news en échec ne bloque jamais la publication des données de marché.
- **Macro automatique et calendrier d’échéances** : dernier communiqué du Comité de Politique Monétaire BCEAO relu par expressions ciblées (taux directeur, prêt marginal, réserves obligatoires, inflation et croissance citées ; 3,00 % / 5,00 % au CPM du 9 septembre 2026 dans la collecte v0.8), événements BCEAO datés, et tableaux UMOA-Titres des émissions à venir/planifiées (32 opérations ; 766 milliards FCFA annoncés sur les 30 prochains jours à la collecte). Le calendrier est généré uniquement depuis des dates publiées par une source officielle — dividendes BRVM, opérations UMOA-Titres, événements BCEAO — soit 36 échéances dans la collecte livrée. Les montants UMOA sont des montants annoncés/mis en adjudication, pas des montants levés ; ce bloc sert de contexte de taux et de liquidité, jamais de signal automatique.
- **Préréglage de première ouverture** : pays de résidence, SGI choisie dans l'annuaire officiel BRVM (37 SGI collectées : noms, pays, contacts — la BRVM ne publie pas les tarifs), versement mensuel, horizon (long terme 10 ans ou moyen terme), poche d'apprentissage optionnelle en % du versement, règle déclarée face à une baisse de 20 %. Ensuite, la Décision du mois utilise automatiquement le versement (déduction faite de la poche), les frais s'ils sont saisis, et la checklist baisse rappelle la règle déclarée. Dans Paramètres : annuaire des SGI de votre pays et comparateur de coût d'un ordre mensuel calculé uniquement à partir des grilles écrites que vous saisissez (datées) — aucun titre de « meilleure SGI » décerné.
- **Radar SIGMA** : premier tri automatique des sociétés cotées par règles quantitatives transparentes — échangées sur au moins 15 des 20 dernières séances, valeur médiane négociée ≥ 5 000 000 FCFA, PER publié au BOC entre 0 et 25, dividende documenté récent et non extrême. Les éligibles reçoivent un « score d'étude » (liquidité 35, valorisation relative 35, rendement 30, en rangs) ; la sélection (8 sociétés, 3 par secteur au plus) s'ajoute à la liste de suivi en un clic. C'est un ordre de lecture, pas une recommandation.
- Watchlist, portefeuilles réel/virtuel saisis manuellement, prix de revient moyen, journal de thèse, alertes factuelles (dividendes, publications officielles sur vos valeurs, baisses) et registre d'événements de contexte — en stockage local du navigateur, exportables en JSON.
- Décision du mois : périmètre Radar par défaut, nombre de titres compatible avec un budget, sans frais inventés.

- **Documents, fondamentaux pluriannuels et piliers conditionnels** : les pages officielles « Rapports sociétés cotées » sont indexées pour chaque société (1 504 documents pour 47 émetteurs lors de la collecte v0.8 du 20 octobre 2026 : états financiers annuels, rapports d'activité trimestriels/semestriels, attestations des commissaires aux comptes), classés par type et par exercice depuis leurs noms de fichiers officiels. SIGMA lit les colonnes exercice courant et exercice précédent de plusieurs documents annuels pour reconstruire une série d’agrégats SYSCOHADA/IFRS — chiffre d'affaires ou produit net bancaire, résultat net (et part du groupe), capitaux propres, total du bilan. Règles strictes : unité monétaire explicite exigée sur la page, avec une exception contrôlée pour les états de synthèse SYSCOHADA codés en FCFA (codes XB/XI/CP/DZ/BZ et colonnes nette N/N-1 distinguées) ; montants lus par mots positionnés, capitaux propres négatifs conservés lorsqu’ils sont réellement publiés, contrôles de plausibilité par exercice, recoupement entre documents (un agrégat est « confirmé » si deux documents officiels distincts publient la même valeur à 1,5 % près), et hygiène de série contre les doublons d’exercice et ruptures d’échelle. Collecte livrée : 34 sociétés avec séries, 24 avec au moins 3 exercices, 401 agrégats au total dont 88 confirmés par deux documents. Les piliers **Solidité** et **Croissance** ne sont publiés que si la série dépasse les seuils documentés dans la fiche ; sinon, SIGMA affiche « non calculable ». Chaque valeur conserve page/ligne sources et son niveau de confiance.
- **État de couverture mesuré** : Paramètres affiche un audit recalculé depuis le fichier de données courant, bloc par bloc — BOC/prix, documents, séries fondamentales, recoupements, historique des dividendes, dividende durable, dette/trésorerie/flux, capital, actualités, macro, SGI et fraîcheur. Le statut « Excellent » n’est attribué que si le seuil écrit dans le tableau est atteint ; les blocs partiels ou insuffisants restent visibles avec leur prochaine correction, sans moyenne masquante.

## Limite assumée

Les fondamentaux restent des extractions automatisées : SIGMA les recoupe entre documents et publie leur niveau de confiance, mais ne prétend pas les avoir **vérifiés humainement ligne à ligne**. Dans la collecte v0.8, 14 sociétés n’ont encore aucune série fondamentale acceptée et seuls 88 des 401 agrégats sont confirmés par deux documents ; de nombreux rapports annuels sont des PDF scannés qui exigeront une OCR contrôlée ou une autre source textuelle officielle. Les annexes dette/trésorerie/flux, le nombre d’actions, le flottant et la capitalisation vérifiée ne sont pas encore collectés. L’historique des montants de dividendes est maintenant profond, mais le pilier Dividende durable et le score global restent **suspendus** tant que le taux de distribution et la couverture par les flux ne sont pas calculables sans bénéfice par action ou nombre d’actions vérifié. Les prix longs restent non ajustés et limités à 260 séances ; les résultats/rendements d’adjudications UMOA et l’historique des décisions CPM restent à ajouter. Les PER/rendements montrés sont ceux imprimés dans le BOC, datés. Les workflows GitHub sont préparés, mais leur activation est volontairement reportée ; la priorité reste l’extension mesurée de la couverture de données.

## Lancer en local

```bash
python3 -m http.server 8000 --directory web --bind 0.0.0.0
```

Ouvrir ensuite l'adresse du serveur. Les données personnelles restent dans `localStorage`.

## Recollecter les données

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python ingestion/collect.py --boc-count 30 --boc-archive-count 260
```

La collecte écrit `web/data/data.json` et met à jour `web/data/boc_archive.json` de façon atomique après contrôles. Si l’archive longue est déjà proche de l’objectif, la collecte quotidienne relit surtout la fenêtre récente puis fusionne les nouvelles séances. Le workflow `.github/workflows/update-data.yml` automatise cette collecte les jours ouvrés si le projet est poussé sur GitHub et versionne les deux fichiers de données.

## Sources

- BRVM — cours des actions : https://www.brvm.org/fr/cours-actions/0
- BRVM — Bulletins Officiels de la Cote : https://www.brvm.org/fr/bulletins-officiels-de-la-cote
- BRVM — paiement de dividendes : https://www.brvm.org/fr/esv/paiement-de-dividendes
- BRVM — rapports des sociétés cotées : https://www.brvm.org/fr/rapports-societes-cotees
- BRVM — annonces des émetteurs : https://www.brvm.org/fr/emetteurs/type-annonces/communiques
- BRVM — actualités : https://www.brvm.org/fr/mediacentre/actualites
- BCEAO — communiqués de presse : https://www.bceao.int/fr/communique-presse
- BCEAO — événements : https://www.bceao.int/fr/evenements
- UMOA-Titres — flux RSS : https://www.umoatitres.org/fr/feed/
- UMOA-Titres — émissions à venir et planifiées : https://www.umoatitres.org/fr/emissions/
- Sika Finance — flux RSS (presse, titres et liens uniquement) : https://www.sikafinance.com/rss/actualites_bourse_brvm
- BRVM — annuaire officiel des SGI : https://www.brvm.org/fr/intervenants/sgi/tous

Usage personnel. SIGMA ne passe aucun ordre, ne prédit aucun cours et ne fournit pas de conseil financier personnalisé.

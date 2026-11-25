# Points abordés, ce qui manque, et ce qui a été corrigé (28 octobre 2026)

## 1 · La liste des points abordés depuis le début

| # | Sujet | État |
|---|---|---|
| 1 | Trois horizons (court / moyen / long), règle écrite par horizon | livré |
| 2 | Croisement propre à la société (percentile de son PER contre son passé) | livré |
| 3 | Décomposition exacte cours = bénéfice × multiple | livré |
| 4 | Couverture et registre des manques (66 points) | livré |
| 5 | Deux seuils par horizon (plein / limité) | livré |
| 6 | Capitalisation dérivée par identité (3 vérifiées + 35 déduites) | livré |
| 7 | Le revenu en trois preuves (régularité, financement, couverture) | livré |
| 8 | Rendement ramené au seul BOC (le tableau mélange brut et net) | livré |
| 9 | Fraîcheur affichée, âge recalculé à l'ouverture | livré |
| 10 | Top 5 budgété, revue de sortie sur tout le marché | livré |
| 11 | Mesures de risque : amplitude 7,5 %, retour après saut, réaction aux publications | livré |
| 12 | Méthode des investisseurs reconnus, confrontée au code | **ce tour** |
| 13 | Filtrage du Radar trop strict | **corrigé ce tour** |
| 14 | Diagnostic des séries comptables (unités, ruptures) | **ce tour** |
| 15 | Allègement visuel | **ce tour** |
| 16 | Registre du nombre d'actions (48/48 en capitalisation vérifiée) | ouvert |
| 17 | Prix historiques au-delà d'un an | ouvert |
| 18 | BPA vérifié sur les états financiers | ouvert |

## 2 · Ce qui manque, par ressource — et ce que chaque manque coûte

### Prix historiques

**Ce qu'on a** : 262 séances, du 22/09/2025 au 21/10/2026, 47 à 48 valeurs
par séance, cours de clôture + volume + valeur échangée + PER + rendement.

**Ce qui manque** : tout ce qui précède le 22/09/2025. C'est la ressource la
plus rentable à ajouter, et de loin :

- la position du cours et du PER ne se lit que sur **un an** — un cycle complet
  de marché UEMOA en demande cinq ;
- les statistiques de retour après saut reposent sur 5 à 6 observations pour
  les valeurs liquides : trop peu pour conclure ;
- aucune moyenne longue (200 séances) n'est calculable de façon robuste ;
- le régime de marché (Dalio, Marks) reste inabordable : « où en est-on dans
  le cycle » n'a pas de réponse avec 262 séances.

**Ce que ça coûterait** : les BOC sont publiés quotidiennement en PDF depuis
des années. L'archive est reconstructible, à raison d'environ 250 séances par
an, mais chaque PDF doit être extrait et contrôlé. C'est un chantier de
collecte, pas de code.

### Documents PDF

**Ce qu'on a** : 1 504 documents indexés pour 47 sociétés sur 48, dont 372
états financiers, 478 rapports d'activité trimestriels, 404 semestriels.

**Ce qui manque** : NSBC (aucun document), TTLS (1), BBGC (2). Et surtout,
sur les 1 504 documents, seuls ceux dont le texte est exploitable ont produit
des chiffres : 45 sociétés ont des chiffres extraits, 24 ont nécessité un OCR.

Le vrai goulot n'est donc pas le nombre de PDF, c'est **la lecture** : les
tableaux scindés, les scans et les mises en page IFRS/SYSCOHADA produisent des
extractions partielles.

### Le nombre d'actions — la ressource qui débloque le plus

4 sociétés sur 48 ont un nombre d'actions lu dans un document. C'est ce qui
limite : la capitalisation vérifiée (3 + 35 déduites), le BPA recalculé (6
sociétés), le taux de distribution par action (4), la couverture du dividende
par le flux (2 sur 48).

**Le chemin** : la page « capital » ou la note d'information de chaque rapport
annuel. Un travail de saisie contrôlée sur 48 documents, pas de collecte
massive.

### Fiscalité et frais

Aucune source officielle unifiée pour les huit pays de l'UEMOA. SIGMA n'invente
donc aucun taux. Les frais SGI sont disponibles pour 33 SGI sur 37 (grilles
homologuées AMF-UMOA), mais 6 décisions seulement sont entièrement vérifiées.

## 3 · Le filtrage trop strict — corrigé

Le Radar appliquait un **plafond de PER fixe à 25**. Conséquence mesurée :

| Secteur | Médiane de PER | Sociétés exclues par le plafond |
|---|---:|---|
| Industriels | **54,5** | FTSC (54,5), SEMC (37,2), SIVC (78,4), SDSC (204,6) |
| Consommation discrétionnaire | 21,3 | CFAC (31,0), BNBC (510,5) |
| Services financiers | 14,1 | BOAN (242,9), SAFC (65,9) |
| Consommation de base | 13,4 | UNLC (647,0) |

Neuf sociétés étaient écartées **avant** tout examen, dont les quatre
industriels dont la médiane sectorielle dépasse le plafond : un seuil unique
appliqué à des secteurs dont les multiples vont du simple au quadruple.

**Décision** : un PER élevé n'exclut plus. Il devient un **drapeau** comparé à
la médiane de son secteur, et pèse moins dans le classement (le poids
« valorisation » utilise déjà le rang, pas la valeur absolue). Seule
**l'absence** de PER exclut encore, parce qu'on ne peut pas lire une
valorisation sans bénéfice. Éligibles : 29 → 37 sur 48.

## 4 · Diagnostic des séries : d'où venaient les fausses lectures

En creusant les ruptures, j'ai trouvé la cause réelle — ce n'était pas un
problème de périmètre comptable, mais **d'unités** :

| Société | Exercice | Unité du chiffre |
|---|---|---|
| SGBC | 2021 | **en FCFA** (10 115 740 855) |
| SGBC | 2022 | **en millions de FCFA** (97 230 000 000) |

**24 changements d'unité** entre deux exercices consécutifs dans la collecte
(milliers ↔ millions ↔ FCFA ↔ milliards). Les valeurs sont bien converties,
mais deux chiffres voisins d'une même série n'ont pas été lus à la même
échelle — et c'est très souvent là que naît la « rupture ».

`ruptures()` dit désormais **pourquoi** il refuse : unité différente, chiffre
non recoupé dans son document, ou périmètre probablement différent. Sur 17
ruptures détectées, la cause est identifiée pour chacune.

## 5 · Allègement visuel — mesuré, pas ressenti

Comptage des mots **réellement visibles** (hors blocs pliés), rendu DOM réel.

| Vue | Avant | Après |
|---|---:|---:|
| **Ce qui manque** | 4 243 | **489** (−88 %) |
| **Total des 9 vues + fiche** | 16 242 | **12 488** (−23 %) |

Ce qui a changé :

- la vue « Ce qui manque » regroupait **66 lignes** dépliées, une par
  société **et par horizon** : elle est maintenant organisée par société, et
  chaque horizon se plie ;
- aucune information n'a été supprimée : les 66 manques restent, avec raison,
  source et déblocage ;
- le portefeuille renvoie explicitement vers Décision au lieu de dupliquer.

## 6 · Un investisseur intelligent verrait-il ce qu'il faut ?

Réponse honnête : **pas encore tout**. Ce qui est affiché et qu'un
professionnel utilise réellement : prix contre son propre passé, qualité du
bénéfice, couverture du dividende, amplitude, liquidité de sortie.

Ce qui reste absent, et qui pèse :

- **la croissance future** — aucune projection, par choix ;
- **le nombre d'actions** — d'où l'absence de BPA vérifié et de capitalisation ;
- **les corrélations** — donc pas de vraie construction de portefeuille ;
- **le cycle long** — l'archive d'un an interdit le régime de marché.

La nouvelle carte **Méthode** (Décision → À examiner) confronte neuf pratiques
reconnues à ce que le code fait réellement : 0 couvertes entièrement, 5
partielles, 3 limitées par les données, 1 refusée volontairement (prévoir une
chute). C'est un état des lieux, pas un argument de vente.

## Vérifications

`pytest` **268 tests** · jsdom 9 vues, **0 erreur JavaScript** · éligibles
Radar 29 → 37 · vue « Ce qui manque » −88 % de mots · `sw.js` v8.

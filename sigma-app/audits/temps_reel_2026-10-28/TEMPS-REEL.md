# « J'ai besoin d'une recommandation en temps réel » (28 octobre 2026)

## Ce que je ne ferai pas, et pourquoi

Une recommandation en temps réel suppose trois choses que cette collecte n'a
pas :

1. **un flux intraday.** L'archive contient 262 séances d'un cours de clôture
   par jour. Il n'y a jamais eu de carnet, de profondeur ni de dernier échange
   horodaté. Un « cours en direct » recopié depuis la dernière clôture serait
   une donnée fabriquée.
2. **une recommandation.** SIGMA publie des observations datées et ce qui les
   invaliderait. Un mot d'ordre n'y entrera pas — c'est la règle qui rend le
   reste utilisable.
3. **une fraîcheur garantie.** Le dernier fichier livré décrit la séance du
   **21 octobre**, pour un fichier généré le **22 octobre à 21 h 20**. Au
   moment de cette réponse, il a **34 jours**.

Le troisième point est le plus grave, et c'est celui que j'ai corrigé.

## Le problème réel : l'application ne disait pas son âge

Avant ce tour, la pastille d'en-tête affichait « BRVM · Séance fermée · BOC
21 oct. 2026 » avec un indicateur qui passait au rouge au-delà de **30 heures**
— un seuil pensé pour une collecte quotidienne, jamais pour un mois d'arrêt.
Une personne ouvrant l'application pouvait lire une variation de séance
comme si elle décrivait le marché du jour.

### Ce qui a changé

| Élément | Avant | Après |
|---|---|---|
| Pastille | date du BOC | état + âge calculé **à l'ouverture** : « Périmé · il y a 34 jour(s) » |
| Bandeau | inexistant | rouge **Périmé** au-delà de 4 jours, ambre **En recul** au-delà de 24 h, masqué si à jour |
| Titre de l'onglet | fixe | « SIGMA · données périmées » |
| Vue Marché | séance affichée sans réserve | rappel de l'âge au-dessus des indices |
| Vue « Ce qui manque » | registre | **horloge** : âge de la cote, du BOC, de la collecte, prochaine séance |

Trois états, pas deux : **à jour** (≤ 24 h), **en recul** (24 h – 4 j),
**périmé** (> 4 j). L'âge est recalculé à chaque rendu, jamais figé au moment
de la collecte : c'est le seul moyen qu'il ne mente pas.

### Ce que l'horloge dit aussi

- La **cote BRVM** est une photo datée, pas un flux.
- Le **BOC** n'existe qu'après la clôture : aucun indicateur fondamental ne
  peut être plus frais que lui.
- La **prochaine mise à jour** est annoncée en séance ouvrée, **sans calendrier
  de jours fériés** — la BRVM n'en publie pas de lisible, l'inventer serait une
  donnée fabriquée.

## Ce que SIGMA peut faire, tout de suite, sans temps réel

La question « quoi faire ce mois-ci » n'a pas besoin d'un cours à la seconde :
elle a besoin d'un cours et de son histoire. Sur les données du 21 octobre,
SIGMA sait déjà :

- si le cours est dans le haut ou le bas de **sa propre** fourchette (47/48) ;
- si le PER est cher **par rapport à son propre passé** (42/48, dont 39 en
  lecture pleine) ;
- ce qui a porté la hausse — multiple ou bénéfice — par décomposition exacte ;
- si le dividende est un revenu ou un versement passé (3/48 avec les trois
  preuves) ;
- la distance au plus haut annuel (47/48).

Ce sont ces éléments qui décident d'un achat de long terme ; le prix exact à la
seconde change le coût de quelques pour cent, pas la thèse.

## Ce qu'il faudrait pour du vrai temps réel, et son prix

1. **Collecte quotidienne automatique** après la clôture (GitHub Actions ou
   serveur). Non installée à ce jour : le dépôt n'a **aucun workflow**. C'est
   la première brique, et elle suffit à faire passer l'app de « périmé » à
   « à jour » chaque soir de séance.
2. **Horodatage de la cote** : `data.json` porte `source_updated_label` (libellé
   de la BRVM) mais pas d'ISO de lecture. Un champ `snapshot.observed_at`
   donnerait l'âge exact de la cote au lieu de celui du fichier.
3. **Intraday** : impossible depuis brvm.org sans un flux dédié. Une SGI, elle,
   a le carnet. SIGMA ne le simulera pas.

## Vérifications

`pytest` **256** · jsdom 9 vues, **0 erreur JavaScript** · âge réel mesuré :
34 jours, bandeau en état `Périmé`, titre d'onglet modifié · simulation d'une
collecte fraîche : bandeau masqué, « À jour · à l'instant » · `sw.js` v5.

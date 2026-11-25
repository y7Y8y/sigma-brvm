# « Pourquoi afficher ce qui manque au lieu de le corriger ? » (28 octobre 2026)

## La réponse courte

Parce que je classais en « manque » des choses qui étaient réparables **dans le
code**, avec des données déjà présentes. C'était une faute de méthode, pas une
contrainte. Trois réparations ce tour, et le registre devient une file de
travail ordonnée par réparation.

## 1 · La rentabilité des fonds propres — elle existait, elle n'était pas calculée

C'est la mesure que tout praticien regarde avant le prix : une entreprise qui
gagne 25 % sur ses fonds propres n'a pas la même valeur qu'une entreprise qui
en gagne 3 %, même à PER égal. Les données étaient là, exercice par exercice.

| Avant | Après |
|---|---|
| ROE pour 0 société | **32 sociétés**, dont **22 sur 3 exercices** |
| 16 sociétés sans rentabilité, sans explication | 16 tâches nommées, avec la ligne exacte à lire |

Règle appliquée sans exception : résultat net et fonds propres du **même
exercice**, jamais une moyenne, jamais une reconstitution. Les exercices dont
les fonds propres manquent ne sont pas comptés — ils ne sont pas remplacés par
zéro (SGBC : 2021 et 2025 absents, 2022-2024 publiés).

Nouvelle carte en tête de fiche : **« Rentabilité des fonds propres »**, exercice
par exercice, avec la moyenne, le nombre d'exercices négatifs, et la règle
(> 15 % : création de valeur ; < 5 % : destruction après inflation).

## 2 · Une donnée absente peut être une somme de données présentes

La dette financière totale était manquante pour la plupart des exercices, alors
que ses deux composantes (courante et non courante) étaient parfois publiées.
Une somme additive exacte n'est pas une estimation : elle est maintenant
calculée, **et le fait que ce soit une somme est écrit à côté du chiffre**.

Même raisonnement appliqué aux unités : 24 changements d'unité entre deux
exercices expliquaient la plupart des « sauts invraisemblables ». La cause est
désormais identifiée pour chaque rupture (unité, chiffre non recoupé,
périmètre), au lieu d'un refus générique.

## 3 · Le registre devient une file de travail

| Avant | Après |
|---|---|
| 66 lignes classées par horizon | 81 points classés **par réparation** |
| « il manque X pour la société Y » | « lire les fonds propres → 16 sociétés débloquées » |
| aucune estimation de l'effort | le prix de chaque chantier, en documents |

Les six chantiers, avec leur gain :

| Chantier | Sociétés | Ce que ça débloque | Ce que ça demande |
|---|---:|---|---|
| Lire les fonds propres dans le bilan | 16 | la rentabilité (0 → 32 sociétés ce tour) | 48 bilans, 1 ligne |
| Extraire « dividendes versés » + flux | 38 | un revenu vérifié (3 → jusqu'à 48) | 2 lignes par exercice |
| Inscrire le nombre d'actions | 10 | capitalisation vérifiée, BPA comparable | 48 notes de capital |
| Obtenir un PER publié | 9 | la lecture de valorisation | dépend du résultat |
| Compléter les exercices | 7 | une trajectoire au lieu d'un point | 2 à 3 états |
| Étendre l'archive de prix | 1 | un cycle de marché complet | ~250 BOC par an |

## 4 · Ce que je ne peux pas réparer ici, et pourquoi c'est différent

Deux choses restent hors de portée, et ce n'est pas la même nature :

1. **Le réseau.** Ce bac à sable n'a accès qu'à GitHub et aux registres npm et
   PyPI. `brvm.org` est inaccessible. Je ne peux donc pas collecter les PDF
   manquants ni les BOC anciens : il faut que la collecte tourne dans
   l'environnement qui a produit `data.json`.
2. **L'information qui n'existe pas encore.** Le contenu d'un communiqué avant
   sa publication, ou le nombre d'actions d'une société qui ne l'a jamais
   publié dans un document indexé (NSBC : zéro document). Là, aucun code ne
   remplace une publication absente.

La distinction est maintenant faite dans l'app : ce qui est **réparable** est
rangé par réparation ; ce qui est **irréductible** garde son motif.

## Vérifications

`pytest` **272 tests** (4 nouveaux sur la rentabilité : même exercice, absences
non comptées, chaque société sans ROE a sa tâche) · jsdom 9 vues, **0 erreur
JavaScript** · fiche SGBC : 25,1 % en 2025, moyenne 23,6 % sur 3 exercices ·
registre : 81 points, 6 chantiers · `sw.js` v9.

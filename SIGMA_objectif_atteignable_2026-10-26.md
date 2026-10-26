# SIGMA peut-il atteindre son objectif ?

**26 octobre 2026** · Réponse du lead analyste, chiffrée et vérifiable · Aucune promesse non mesurée

---

## Réponse courte

**Oui pour l'objectif tel qu'il est écrit. Non pour l'objectif tel qu'on pourrait le rêver.** Et le chemin réel n'est pas celui qui figure dans la feuille de route : j'ai mesuré où se trouve le vrai goulot, et ce n'est pas là où le plan le place.

Détail par objectif, avec les chiffres du jour :

| Objectif | Verdict | Ce qui le décide |
|---|---|---|
| **Dire la vérité sur ce que SIGMA sait** | **Atteint, et rendu mécanique** | 121 tests, 9 sommes de contrôle, échec du calcul plutôt que rapport faux |
| **Trancher un statut pour chaque observation** (480 cellules) | **Atteignable** | 402 cellules restantes, dont 105 à coût faible et moyen déjà cadastrées |
| **Valoriser les actions** (PER propre, fourchette) | **Atteignable, mais pas par le chemin prévu** | 16 couples société-exercice seulement réunissent aujourd'hui numérateur et nombre d'actions |
| **Faire mieux que le marché** | **Inconnaissable aujourd'hui** | Seul un registre figé, tenu 12 à 24 mois, pourra le dire — dans un sens ou dans l'autre |
| Temps réel, passage d'ordres, probabilités chiffrées | **N'arrivera pas** | Décisions déjà prises, et bien prises |

---

## 1. L'objectif « dire la vérité » est atteint — et il ne dépend plus de ma vigilance

C'était le risque principal, et il est fermé. Le projet ne repose plus sur la mémoire de quelqu'un : chaque compteur est recalculé, chaque décision humaine est un fichier avec garde-fou, chaque somme doit boucler, sinon le programme refuse d'écrire.

C'est ce qui permet de dire aujourd'hui : **31 BPA publiés retenus sur 442 cas applicables**, 29 après exclusion TTLS, **0 BPA recalculé comparable**, 34 publications non retenues, 263 absences non prouvées. Ces chiffres sont justes par construction, pas par confiance.

## 2. L'objectif « 480 statuts tranchés » est atteignable

La file de travail est désormais cadastrée (`audits/backlog_bpa_v214_2026-10-26/BACKLOG.md`) :

| Cause | Cellules | Sociétés | Coût | Ce qui est établi |
|---|---:|---:|---|---|
| Documents inventoriés, jamais examinés | 18 | 11 | Faible | 71 documents déjà repérés |
| Document présent mais illisible (scan) | 72 | 22 | Moyen | 232 documents repérés |
| Publication repérée, non retenue (échelle, devise, périmètre) | 34 | 11 | Faible-moyen | 190 documents repérés |
| Aucun document candidat trouvé | 15 | 4 | Élevé | 0 document : sortir des canaux BRVM |
| Document examiné sans valeur trouvée | 263 | 41 | **Inconnu** | 1 127 documents repérés |

Les trois premières lignes (124 cellules) sont du travail d'exécution sans inconnue majeure. La quatrième est un problème d'accès à la source, concentré sur 4 émetteurs. La cinquième est le vrai point d'incertitude, et c'est pourquoi elle ne sera pas lancée en vague.

**Atteignable signifie ici :** obtenir un statut explicite pour 442 cellules sur 442. Cela ne signifie **pas** obtenir une valeur pour 442 cellules. La différence est tout le projet : un statut « non publié, documents examinés » est un résultat ; un chiffre inventé n'en est pas un.

## 3. L'objectif « valoriser » : le goulot n'est pas là où le plan le met

C'est le point que je veux que vous reteniez, parce qu'il change l'ordre des travaux.

La feuille de route suppose que la valorisation attend le chantier des BPA publiés. **C'est faux, et je l'ai mesuré.** Pour calculer un BPA comparable au sens du projet, il faut deux choses :

1. un **numérateur** — résultat attribuable aux actionnaires ordinaires ;
2. un **dénominateur** — nombre moyen pondéré d'actions.

J'ai analysé les **660 documents** effectivement rejoués dans l'overlay v2.1.4. Résultat brut :

| Ce que le parseur a trouvé | Couples société × exercice | Sociétés concernées |
|---|---:|---:|
| Un BPA publié (toutes qualités, y compris rejetés) | 68 | 18 |
| Un **numérateur** (résultat) | **30** | **5** |
| Un **nombre d'actions** | **28** | **8** |
| **Les deux à la fois** — condition d'un BPA recalculé comparable | **16** | — |

Autrement dit : sur 660 documents lus, **16 couples seulement** réunissent les deux ingrédients. Pour rendre 48 sociétés valorisables sur cinq exercices, il en faudrait de l'ordre de **240**. L'écart n'est pas de 10 %, il est d'un facteur quinze.

**Et ce n'est pas un manque de sources.** Le nombre d'actions est un fait juridique publié par tout émetteur, dans ses notes de capital ou ses avis d'assemblée. C'est un **retard d'extraction**, sur deux champs précis. Le gisement est d'ailleurs loin d'être épuisé : 660 documents rejoués, pour **1 504 indexés** — la moitié du fonds n'a jamais été repassée par le parseur v2.1.4.

**Conséquence stratégique, que je prends comme lead :** la priorité n'est pas de chercher 263 BPA publiés supplémentaires. C'est de construire le **registre du dénominateur** (actions) et du **numérateur attribuable**, exercice par exercice. Avec ces deux champs, le BPA comparable se calcule pour toute société documentée, sans dépendre de ce qu'un imprimeur a bien voulu mettre en page.

## 4. Avant d'engager la grosse vague : un test à 24 cellules

Le bloc de 263 « document examiné, valeur non trouvée » est ambigu par nature. Il mélange :

- de **vraies absences éditoriales** — beaucoup d'émetteurs BRVM ne publient pas de résultat par action dans leurs états condensés ;
- des **valeurs présentes mais non reconnues** par le parseur — le dossier documente déjà ce cas (SNTS 2025 : BPA présent, ignoré à cause d'une mise en page « libellé seul, montants en sous-ligne »).

Tant qu'on ne sait pas dans quelle proportion, on ne sait pas si l'effort à venir est de la recherche documentaire ou du développement de parseur. J'ai donc tiré un **échantillon reproductible de 24 cellules** (graine `20261026`), stratifié de fait sur les secteurs et l'utilité de valorisation, à relire à la main.

Et j'ai écrit la décision **avant** de connaître le résultat, pour m'interdire de négocier avec les faits :

- **≥ 30 % de valeurs retrouvées** → le bloc est un trou de rappel du parseur. Priorité au code, pas à la recherche.
- **10 à 30 %** → corriger le parseur, puis relire les structures de page concernées.
- **< 10 %** → l'absence est majoritairement réelle. On documente le statut et on cesse d'y investir.

C'est la seule façon honnête de décider où mettre l'effort : mesurer d'abord, engager ensuite.

## 5. L'objectif « mieux décider que la moyenne » : personne ne peut y répondre aujourd'hui

Je ne vous promettrai pas que SIGMA battra le marché, et je me méfierais de quiconque le ferait. Trois raisons, sans détour :

1. Sur la BRVM, la liquidité est faible : une thèse juste sur un titre qu'on ne peut pas acheter ni revendre proprement n'est pas une décision, c'est une opinion.
2. Les performances longues du projet sont, pour l'instant, des **prix seuls** : pas d'ajustement des opérations sur titres, donc pas de rendement total honnête.
3. La seule preuve recevable est un **registre figé** : chaque signal daté, avec ses conditions et ce qui l'invaliderait, noté à +20/+60/+120/+250 séances. Ce registre ne se rétro-remplit pas. Chaque séance sans registre est une séance perdue.

C'est pourquoi je considère la v1.5 (registre des signaux) comme plus urgente que la collecte automatique. La collecte automatise ; le registre, lui, n'a pas de rattrapage.

## 6. Ce qui, à mes yeux, rendrait l'objectif inatteignable

Je m'engage à le dire si l'un de ces signaux apparaît — ce sont mes critères d'abandon, écrits d'avance :

1. **Moins de 10 % de valeurs retrouvées** sur l'échantillon de 24 → l'absence est réelle et massive ; la valorisation par BPA devient impossible à couvrir, il faudra valoriser autrement (ancres dividende et patrimoniale uniquement), avec un périmètre plus étroit assumé.
2. **Le registre du dénominateur plafonne sous 20 sociétés** après une vague complète → la couverture restera minoritaire et il faudra le dire dans l'interface, pas le masquer par une moyenne.
3. **La qualité de liquidité interdit tout test de sortie réaliste** sur la majorité des titres → l'objectif « aider à décider » reste valable, l'objectif « améliorer le rendement » devient hors de portée, et je le dirai.

Inversement, ce qui me ferait dire que l'objectif est largement tenu : 30 à 35 sociétés valorisables sur au moins trois exercices, un registre tenu sans trou, et des invalidations détectées automatiquement. **Je ne viserai pas 48/48 en valeur** : les quatre émetteurs sans document accessible et les formulaires bancaires condensés rendent cette promesse malhonnête.

## 7. Le calendrier, en jalons vérifiables plutôt qu'en dates promises

1. **Jalon 1** — les 18 cellules non recherchées traitées : le coût marginal le plus faible du chantier. Effort court, résultat visible.
2. **Jalon 2** — test des 24 cellules, décision écrite appliquée. C'est le jalon qui décide de tout le reste.
3. **Jalon 3** — registre du dénominateur ouvert : nombre d'actions par société et par exercice, avec source et page. C'est lui qui débloque la valorisation.
4. **Jalon 4** — v1.5 livrée : bloc « Aujourd'hui », signal d'étude forte à cinq conditions, registre figé démarré.
5. **Jalon 5** — fourchette de valeur par triangulation, là où au moins deux ancres indépendantes existent, et refus écrit ailleurs.

Aucun de ces jalons ne dépend d'une donnée payante, d'un accès privilégié, ni d'une promesse de performance.

---

## Ce que je viens de livrer avec cette réponse

- `ingestion/backlog_bpa_480.py` — backlog régénéré depuis l'overlay v2.1.4, priorisé par coût d'information, avec échantillonnage reproductible et décision conditionnelle écrite d'avance.
- `audits/backlog_bpa_v214_2026-10-26/` — `BACKLOG.md`, `backlog.csv` (402 lignes), `backlog.json`.
- `tests/test_backlog_bpa_480.py` — 7 tests ; **121 tests au total**, tous verts.
- Aucune intégration : `web/data/data.json` conserve son empreinte `ed5ba551…36fd1efb`.

**Verdict final, en une phrase :** SIGMA atteindra son objectif de rigueur et de statuts — c'est déjà mécaniquement garanti. Il atteindra la valorisation, mais en construisant le registre des nombres d'actions plutôt qu'en cherchant 263 publications. Et il ne pourra répondre à la seule question qui compte vraiment — fait-il mieux que le marché — qu'après avoir tenu son registre assez longtemps pour mériter la réponse.

# Overlay BPA 480 sous `eps-evidence-v2.1.4` — revue et décisions finales du bloc

Date : 26 octobre 2026  
Dataset publié : **inchangé** (`generated_at=2026-10-22T21:20:37+00:00`, SHA-256
`ed5ba551705cd6f9ddb5ecaa345ca22712cb41be2317310c235fbf8a36fd1efb`)  
Intégration au dataset : **aucune**

## Nature de l'overlay

Cet overlay ne réécrit pas le journal historique du 25 octobre. Il combine :

- les **660 lignes documentaires historiques** ;
- **123 résultats remplacés** par le rejeu ciblé v2.1.4 ;
- **537 résultats historiques conservés**.

Les 123 SHA-256 documentaires des remplacements concordent. Le seul
remplacement sans version de parseur par action est BICC
`d9b1ec7ede71e8e0`, rejeté comme trop volumineux avant extraction, à
l'identique dans l'ancien et le nouveau résultat.

Ce n'est **pas** un rejeu intégral des 660 PDF. Le périmètre rejoué couvre les
documents porteurs d'observations par action, SPHC/TTLS et les signaux de
risque d'exercice ; il ne prouve pas que les 537 autres documents donneraient
un résultat strictement identique sous v2.1.4.

Le supplément des 12 dates d'introduction a été revérifié en mode
`--dry-run` contre les sources officielles : **12 vérifiées, 0 refusée**.
La matrice conserve donc **442 cellules applicables** et 38 cellules avant
introduction.

## Compteurs bruts de l'overlay (442 applicables)

- Documents primaires examinés : **335** cellules.
- Séries chiffrées extraites : **288** cellules.
- BPA publiés retenus par la matrice : **31**.
  - `PUBLIE_CONFIRME_DEUX_DOCUMENTS` : 7 ;
  - `PUBLIE_EXTRAIT` : 23 ;
  - `PUBLIE_SOURCE_DIVERGENTE_RESOLUE_PAR_CONTROLE` : 1.
- BPA recalculés comparables : **0**.
- Publications détectées non retenues : **32** dans la matrice brute.
- Quarantaine de cohérence : **1**.
- Ratios indicatifs résultat / actions de fin d'exercice : **8**.
- `NON_PUBLIE_DANS_SOURCES_VERIFIEES` : 265 ;
  `ILLISIBLE` : 72 ; `NON_RECHERCHE` : 18 ;
  `DOCUMENT_INTROUVABLE` : 15.

Ces compteurs restent séparés. Aucun taux global unique ne doit masquer la
différence entre BPA publié, BPA recalculé comparable, ratio indicatif et
simple statut documentaire.

## Ce que change la v2.1.4 par rapport à l'overlay v2.1.2

- Le nombre brut de BPA publiés applicables reste **31**.
- Les publications non retenues passent de 34 à 32 dans la matrice brute,
  avant la correction manuelle SPHC 2022/2023 ci-dessous.
- Les cellules avec document primaire examiné passent de 336 à **335** :
  BOAS 2020 perd une couverture qui appartenait en réalité à 2019.
- Le ratio BOAC autrefois rattaché à 2019 est rattaché à 2017
  (**100,85**, ratio indicatif seulement).
- Le ratio BOAS autrefois rattaché à 2020 est rattaché à 2019
  (**379,7917**, ratio indicatif seulement).
- Les désaccords entre exercice du nom et exercice effectif passent de 18 à 4
  (ETIT, SEMC, SGBC, SNTS), sans forcer le nom contre le contenu.

Le détail document par document est dans
`../rejeu_cible_bpa_v214_2026-10-26/REVUE_REJEU_CIBLE.md`.

## Décisions humaines finalisées pour ce bloc

Les décisions machine correspondantes sont dans
`decisions_humaines_v214.json`. Elles forment une couche de revue explicite ;
elles ne réécrivent pas silencieusement `matrix.json`.

### BOAS

- 2017 : **421** imprimé, non retenu.
- 2018 : **355** imprimé, non retenu.
- 2019 : **380** imprimé ; seul le ratio indicatif **379,7917** est conservé,
  calculé avec 9,115 milliards FCFA / 24 000 000 actions de fin d'exercice.
- 2020 : `ILLISIBLE`, aucune conclusion de non-publication.

La ligne source est « Résultat net par action ou part sociale », page 54, sans
base de calcul précisée ni nombre moyen pondéré vérifié. Elle ne devient donc
pas un BPA comparable.

### CIEC

BPA publiés consolidés retenus :

| Exercice | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| FCFA/action | 140 | 307 | 188 | 183 | 205 | 188 | 234 |

2020–2024 sont confirmés par deux documents ; 2019 et 2025 sont des
extractions uniques déjà contre-lues dans le pilote. Aucune de ces valeurs
n'est reclassée en BPA recalculé comparable sans dénominateur moyen pondéré
explicitement vérifié exercice par exercice.

### SDCC

BPA publiés consolidés retenus après contre-lecture :

- 2018 : **325 FCFA** (contrôle 2 921 M / 9 000 000 = 324,56) ;
- 2019 : **353 FCFA** (contrôle 3 181 M / 9 000 000 = 353,44).

Ils figurent dans deux PDF distincts mais de même vintage 2019. Le BPA
individuel 2018 de 324 FCFA reste un périmètre séparé. Le ratio interne 2018
de 0,333... présent dans les champs auxiliaires de la matrice est un artefact
d'unité et ne doit pas être utilisé.

### SPHC

Aucun BPA SPHC n'est retenu dans la couche comparable.

- 2019–2021 : publications détectées mais sous échelle de page, sans unité par
  action explicite ; non retenues et non converties.
- 2022 : **ce n'est pas une absence**. Les états IFRS 2022 contiennent page 3
  une section « Compte de résultat par action » et la formule résultat net /
  actions en circulation. Le rapport annuel 2023 donne page 27 la colonne
  comparative 2022 à 0,54 sous échelle. Le contrôle 13 696 993 milliers /
  25 558 005 ≈ 535,9 FCFA n'est pas substitué à la publication.
- 2023 : **ce n'est pas une absence**. Le rapport annuel 2023, page 27,
  imprime 0,24 dilué et non dilué sous échelle. Le contrôle arithmétique est
  d'environ 243,8 FCFA, mais il n'est pas intégré.

Correction décisionnelle : SPHC 2022 et 2023 passent de « non publié » à
**publication détectée non retenue pour ambiguïté d'échelle**. Après cette
correction de revue, les publications non retenues sont **34** et les cellules
« non publié dans les sources vérifiées » **263**, sans modification des
fichiers bruts de matrice.

### TTLS

La segmentation est désormais correcte :

- individuel : 128 (2024) et 205 (2025), page 39 ;
- consolidé : **219 (2024)** et **208 (2025)**, page 42.

La transcription consolidée est confirmée, mais les deux valeurs restent
**exclues provisoirement des BPA formellement comparables**. Elles sont
arithmétiquement alignées sur le résultat net total incluant les
participations ne donnant pas le contrôle :

- 2024 : 219,1796 sur le total, contre 140,5637 sur la part du groupe ;
- 2025 : 208,0741 sur le total, contre 143,2353 sur la part du groupe.

Sans note de calcul prouvant le numérateur attribuable aux actionnaires
ordinaires, elles ne doivent alimenter ni le dataset comparable ni un PER
comparable.

## Compteurs après couche de décision

Pour éviter toute ambiguïté :

- BPA imprimés transcrits dans les cellules applicables : **31** ;
- non exclus par la décision de comparabilité TTLS : **29** — ce compteur ne
  vaut pas autorisation d'intégration en bloc, les niveaux de validation
  restant distincts cellule par cellule ;
- transcrits mais exclus de la comparabilité formelle : **2** (TTLS) ;
- publications détectées non retenues après correction SPHC : **34** ;
- quarantaine : **1** ;
- ratios indicatifs séparés : **8** ;
- BPA recalculés comparables : **0**.

Ces décisions ne ferment ni le backlog OCR, ni les cellules introuvables/non
recherchées, ni le cas des documents SEMC/SGBC dont le libellé et le contenu
divergent. Elles ferment le bloc de correction v2.1.4 et les revues BOAS,
CIEC, SDCC, SPHC et TTLS demandées à ce stade.

## Décision

**Aucune intégration au dataset publié n'est lancée.**

Motifs inchangés :

1. l'overlay n'est pas un rejeu intégral des 660 documents ;
2. des extractions uniques subsistent hors des cellules explicitement
   contre-lues ;
3. le backlog documentaire reste important (72 illisibles, 18 non recherchées,
   15 introuvables dans la matrice brute) ;
4. TTLS est transcrit mais non comparable formellement ;
5. SPHC exige une règle d'échelle explicite ou une autre source primaire
   avant toute valeur en FCFA/action ;
6. aucun BPA recalculé comparable n'a encore les deux intrants pondérés
   vérifiés.

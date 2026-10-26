# Correctif BPA SPHC / TTLS — revue de validation

Date : 26 octobre 2026  
Parseur : `eps-evidence-v2.1.1`  
Dataset publié : **inchangé** — SHA-256 `ed5ba551705cd6f9ddb5ecaa345ca22712cb41be2317310c235fbf8a36fd1efb`  
Intégration au dataset : **aucune**

## 1. Défauts corrigés

### 1.1 Dates de clôture prises pour des BPA

Le tokenizer reconnaît désormais les dates complètes ou abrégées dans le
segment qui suit un libellé BPA, notamment :

- `31-déc-21`, `31-déc-2021`, `31 décembre 2021` ;
- `31/12/2025`, `31.12.2025` et les dates ISO ;
- les formes mois-jour-année et mois-année.

Les jetons appartenant à une date sont marqués `is_date`, y compris lorsque
le montant provient des lignes structurées par coordonnées. Ils sont ensuite
écartés des colonnes de valeurs avec la raison tracée
`DATE_D_EN_TETE_IGNOREE`.

Le cas SPHC `31-déc-21 31-déc-20` ne produit donc plus les fausses valeurs
31 et -21.

La contre-lecture ORGT a ensuite révélé le même risque pour une ligne
d'années espacées (`2 019 2 018`) placée entre un titre BPA et ses intrants.
La version 2.1.1 reconnaît ces années sur les lignes quasi purement
numériques et compacte les espaces avant le filtre d'année d'en-tête : le
document ORGT 2019 ne produit plus que les vrais BPA 142 et 115.

### 1.2 « Non dilué » lu comme dilué

La détection de base retire les mentions négatives (`non dilué`,
`non-dilué`, `not diluted`, `undiluted`) avant de chercher un marqueur dilué
positif. Une ligne « Non dilué » est maintenant classée `DE_BASE`.

La même détection est utilisée pour distinguer un dénominateur moyen
pondéré de base d'un dénominateur dilué.

### 1.3 Périmètre lorsque « IFRS » est intercalé dans l'en-tête

La reconnaissance du périmètre n'exige plus les syntagmes contigus exacts
`etats financiers individuels` ou `etats financiers consolides`. Elle accepte
les insertions usuelles (`IFRS`, `annuels`, `audités`, `certifiés`,
`condensés`) entre le type d'états et le périmètre.

Le cas TTLS est ainsi segmenté page par page :

- page 39 : états IFRS **individuels** ;
- page 42 : états IFRS **consolidés**.

### 1.4 Échelle monétaire de page et montant par action

Les observations portent maintenant l'échelle monétaire détectée sur la
page, sa source et l'existence ou non d'une unité par action explicite.

L'échelle des totaux ne s'applique pas automatiquement à un montant par
action entier : le cas Sonatel du pilote (2 359 déjà en FCFA sous un état en
millions) reste éligible. En revanche, sans unité par action explicite, une
valeur FCFA brute inférieure à 1 ou publiée avec au moins trois décimales
sous une page en milliers/milliers reste **conservée comme preuve mais non
promue**, avec la raison :

`ECHELLE_MONETAIRE_DE_PAGE_SANS_UNITE_PAR_ACTION_EXPLICITE`

Cette règle couvre les valeurs SPHC 0,830 / 0,329 et 1,695 / 0,666, sans les
convertir silencieusement en 830 / 329 ou 1 695 / 666 FCFA.

## 2. Tests synthétiques

Quatre tests de régression ont été ajoutés à
`tests/test_collect.py` :

1. changement de périmètre avec « IFRS » intercalé ;
2. dates de clôture après un libellé BPA, en texte et en montants structurés ;
3. échelle de page en milliers/milliers, avec les contre-exemples Sonatel et
   unité par action explicite ;
4. ligne d'années espacées `2 019 2 018` dans une note BPA.

Résultat final :

- **100 tests réussis** ;
- compilation réussie de `eps_evidence.py`, `collect.py`,
  `audit_bpa_480.py`, `regress_pilot_bpa_5.py` et de la suite de tests.

## 3. Validation sur les vrais PDF

### SPHC — États financiers IFRS 2021

- SHA-256 du PDF : `10a0449bb094a1cf76206334adaca606eb2c83cf5ab07d9d4c5f67d12e558084`
- Les fausses valeurs 31 et -21 ont disparu.
- Les lignes réelles page 3 sont détectées :
  - dilué : 0,830 et 0,329 ;
  - non dilué, donc de base : 0,830 et 0,329.
- Aucune n'est éligible comme BPA FCFA : échelle de page en milliers, sans
  unité par action distincte, et périmètre non prouvé.
- Aucune figure `benefice_par_action` n'est produite.

Fichier : `SPHC_2021_result.json`.

### SPHC — États financiers 2020

- SHA-256 du PDF : `7193773e336f70b373d0b648c59ad9b37302162fb80aaab719a6e31237244df7`
- Les fragments de dates `31-déc-20 31-déc-19` ne sont plus des valeurs.
- Les valeurs brutes 1,695 et 0,666 sont conservées mais non éligibles pour
  la même ambiguïté d'échelle.
- Aucune figure `benefice_par_action` n'est produite.

Fichier : `SPHC_2020_result.json`.

### TTLS — Rapport annuel 2025

- SHA-256 du PDF : `9b50beff23f55e43c18afb835f608675237e9ad8c9ba9ea8127a6371684fcf3a`
- Page 39, périmètre **INDIVIDUEL** : 205 (2025) et 128 (2024).
- Page 42, périmètre **CONSOLIDE** : 208 (2025) et 219 (2024).
- La figure retenue au niveau document est désormais le bloc consolidé :
  **208 / 219 FCFA**, et non plus les valeurs individuelles étiquetées à tort
  comme consolidées.

Fichier : `TTLS_2025_result.json`.

## 4. Régression pilote rejouée prudemment

Nouveau répertoire :
`audits/regression_pilote_bpa_5_correctif_2026-10-26/`

Empreinte de code de la régression :
`2bc7fbb4aa252ddde4ae07bf9884e11fe6e873acadd881d96c49166e32020672`

### 4.1 Hors ETIT

- 62/62 documents rejoués, SHA-256 identiques au pilote ;
- 40 cellules ;
- **15/15 BPA attendus concordants** ;
- 0 valeur divergente, 0 faux positif ;
- le rejet humain SDSC est démontré.

### 4.2 ETIT

Les dix documents légers ont été rejoués :

- 10/10 SHA-256 identiques au pilote ;
- **3/3 BPA attendus concordants** ;
- 0 faux positif ;
- 6/7 rejets humains démontrés dans l'agrégation.

Le onzième document, le rapport annuel Ecobank Group 2018 (324 pages), a de
nouveau expiré après 900 secondes dans le sandbox de 2 Go lors d'une
extraction complète. Il n'a pas été retenté tel quel.

À la place, les 23 pages déjà sélectionnées par la régression fermée du
24 octobre ont été structurées une par une avec le nouveau parseur :

- 25 observations BPA retrouvées ;
- **25/25 tuples identiques** à l'ancienne régression sur valeur, devise,
  base, composante, page, éligibilité et raisons ;
- le candidat ETIT 2016 de -1,01 page 300 est détecté puis non retenu pour
  devise non FCFA/non prouvée.

Fichier : `ETIT_2018_pages_ciblees_result.json`.

### 4.3 Lecture honnête du résultat

L'agrégation formelle porte donc sur **72 documents complets**, et non sur
une nouvelle extraction complète 73/73 :

- 50 cellules comparées ;
- **18/18 BPA attendus concordants** ;
- 0 valeur divergente ;
- **0 faux positif** ;
- 7/8 rejets démontrés dans l'agrégation 72 documents ;
- le huitième mécanisme est démontré séparément par l'extraction ciblée des
  23 pages du rapport annuel ETIT 2018.

Résumé combiné :
`audits/regression_pilote_bpa_5_correctif_2026-10-26/agregation_72_documents_sans_rapport_annuel_ETIT_2018/summary.json`

## 5. Effet sur l'audit 480

Les artefacts bruts du 25 octobre sont préservés. Le code ayant changé, leur
journal n'est pas réutilisable sous la nouvelle empreinte pour produire une
nouvelle matrice comparable.

Conséquences attendues d'un futur rejouage, non lancé ici :

- les quatre anomalies SPHC/TTLS de la matrice brute disparaissent ou sont
  reclassées correctement ;
- TTLS 2025/2024 devient 208/219 au périmètre consolidé, toujours en
  extraction à contre-lire avant toute intégration ;
- SPHC ne produit plus de BPA FCFA éligible à partir des dates ou des
  valeurs 0,830 / 1,695 sans unité par action prouvée.

## 6. Suite

1. **Fait le 26 octobre** : les 18 BPA en extraction unique et la quarantaine
   SDSC 2022 ont été contre-lus séparément ; voir
   `audits/contre_lecture_extractions_uniques_2026-10-26/REVUE_CONTRE_LECTURE.md`.
2. Ne relancer l'audit 480 complet qu'après ces décisions de revue, ou le
   limiter d'abord aux tickers/documents affectés par le correctif.
3. Toujours aucune intégration au dataset publié à ce stade.

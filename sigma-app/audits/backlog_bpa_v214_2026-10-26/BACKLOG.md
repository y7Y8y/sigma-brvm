# Backlog documentaire BPA 480 — régénéré depuis l'overlay v2.1.4

**Date :** 2026-10-26 · **Parseur :** eps-evidence-v2.1.4 · **Dataset publié modifié :** non

Source : `audits/audit_bpa_480_corrige_rejeu_v214_2026-10-26/matrix.csv` + `ingestion/overlay_decisions_humaines.json`.

Ce dossier remplace `audits/backlog_bpa_2026-10-26/`, qui reposait sur une
matrice antérieure et doit être considéré comme historique.

**Périmètre :** 442 cellules applicables, dont **402 restant à traiter** (90.95 %).

## File de travail par cause

| Rang | Cause | Cellules | Sociétés | Établie ? |
|---:|---|---:|---:|---|
| 1 | **C_NON_RECHERCHE** — Documents inventoriés, jamais examinés | 18 | 11 | oui, 71 documents candidats inventoriés |
| 2 | **B_OCR_SCAN** — Document présent mais illisible (scan/OCR) | 72 | 22 | oui, 232 documents candidats inventoriés |
| 3 | **D_DOCUMENT_INTROUVABLE** — Aucun document candidat trouvé dans les canaux audités | 15 | 4 | oui, 0 documents candidats inventoriés |
| 4 | **A_PUBLICATION_NON_RETENUE** — Publication repérée mais non retenue (échelle, devise, périmètre) | 34 | 11 | oui, 190 documents candidats inventoriés |
| 5 | **E_ABSENCE_A_TESTER** — Document examiné sans valeur trouvée — absence non prouvée | 263 | 41 | oui, 1127 documents candidats inventoriés |

## Hypothèses causales (à réfuter, pas à croire)

- **C_NON_RECHERCHE** — *hypothèse :* Retard d'ordonnancement, non absence de source.
  *action :* Extraction immédiate : le coût marginal est le plus faible du chantier.
- **B_OCR_SCAN** — *hypothèse :* Concentration attendue sur les émetteurs bancaires : les formulaires de publication BCEAO condensés n'exposent souvent pas de résultat par action et sont fréquemment diffusés en scan.
  *action :* Passe OCR ciblée avec recoupement obligatoire ; jamais une lecture unique.
- **D_DOCUMENT_INTROUVABLE** — *hypothèse :* Les 15 cellules se concentrent sur un petit nombre d'émetteurs.
  *action :* Sortir des canaux BRVM : site émetteur, avis d'AG, archives SGI.
- **A_PUBLICATION_NON_RETENUE** — *hypothèse :* Ambiguïté d'unité ou de périmètre dans le document lui-même.
  *action :* Trancher documentairement la base de calcul, pas convertir au jugé.
- **E_ABSENCE_A_TESTER** — *hypothèse :* Deux causes non séparables sans mesure : absence éditoriale réelle, ou mise en page non reconnue (libellé seul, montants sur sous-ligne).
  *action :* NE PAS lancer en vague. Mesurer d'abord le taux d'absence sur échantillon relu à la main : la valeur peut exister sans être reconnue par le parseur.

## Première vague : les cellules les moins chères

1. **ECOC 2023** — ECOBANK COTE D'IVOIRE (Services financiers) · 4 documents inventoriés · utilité valorisation HAUTE
2. **ONTBF 2025** — ONATEL BURKINA FASO (Télécommunications) · 3 documents inventoriés · utilité valorisation HAUTE
3. **SIBC 2024** — SOCIETE IVOIRIENNE DE BANQUE COTE D'IVOIRE (Services financiers) · 2 documents inventoriés · utilité valorisation HAUTE
4. **SIBC 2025** — SOCIETE IVOIRIENNE DE BANQUE COTE D'IVOIRE (Services financiers) · 1 documents inventoriés · utilité valorisation HAUTE
5. **SLBC 2025** — SOLIBRA COTE D'IVOIRE (Consommation de base) · 1 documents inventoriés · utilité valorisation HAUTE
6. **TTLS 2023** — TOTALENERGIES MARKETING SENEGAL (Énergie) · 1 documents inventoriés · utilité valorisation HAUTE
7. **ECOC 2022** — ECOBANK COTE D'IVOIRE (Services financiers) · 4 documents inventoriés · utilité valorisation MOYENNE
8. **SAFC 2022** — SAFCA COTE D'IVOIRE (Services financiers) · 1 documents inventoriés · utilité valorisation MOYENNE
9. **SDCC 2021** — SODE COTE D'IVOIRE (Services publics) · 5 documents inventoriés · utilité valorisation MOYENNE
10. **SDCC 2022** — SODE COTE D'IVOIRE (Services publics) · 4 documents inventoriés · utilité valorisation MOYENNE
11. **SIVC 2021** — ERIUM COTE D’IVOIRE (Industriels) · 1 documents inventoriés · utilité valorisation MOYENNE
12. **SIVC 2022** — ERIUM COTE D’IVOIRE (Industriels) · 3 documents inventoriés · utilité valorisation MOYENNE
13. **CBIBF 2020** — CORIS BANK INTERNATIONAL BURKINA FASO (Services financiers) · 1 documents inventoriés · utilité valorisation FAIBLE
14. **ONTBF 2019** — ONATEL BURKINA FASO (Télécommunications) · 7 documents inventoriés · utilité valorisation FAIBLE
15. **SDSC 2016** — AFRICA GLOBAL LOGISTICS COTE D'IVOIRE (Industriels) · 4 documents inventoriés · utilité valorisation FAIBLE
16. **SDSC 2017** — AFRICA GLOBAL LOGISTICS COTE D'IVOIRE (Industriels) · 6 documents inventoriés · utilité valorisation FAIBLE
17. **SNTS 2019** — SONATEL SENEGAL (Télécommunications) · 12 documents inventoriés · utilité valorisation FAIBLE
18. **SNTS 2020** — SONATEL SENEGAL (Télécommunications) · 11 documents inventoriés · utilité valorisation FAIBLE

## Test du taux d'absence (obligatoire avant la vague de 265)

Tirage reproductible : **24 cellules** sur 263, graine `20261026`.

Protocole : relire chaque cellule à la main sur son PDF. Trois issues seulement —
**valeur trouvée** (le parseur avait un trou de rappel), **absence confirmée**,
**toujours illisible** (requalifier).

| Société | Exercice | Secteur | Utilité valorisation |
|---|---:|---|---|
| SCRC | 2017 | Consommation de base | FAIBLE |
| LNBB | 2024 | Consommation discrétionnaire | HAUTE |
| SLBC | 2024 | Consommation de base | HAUTE |
| SNTS | 2017 | Télécommunications | FAIBLE |
| CIEC | 2016 | Services publics | FAIBLE |
| SGBC | 2016 | Services financiers | FAIBLE |
| ECOC | 2018 | Services financiers | FAIBLE |
| PALC | 2020 | Consommation de base | FAIBLE |
| SOGC | 2019 | Consommation de base | FAIBLE |
| SGBC | 2024 | Services financiers | HAUTE |
| NEIC | 2024 | Consommation discrétionnaire | HAUTE |
| SGBC | 2020 | Services financiers | FAIBLE |
| UNLC | 2019 | Consommation de base | FAIBLE |
| ORAC | 2023 | Télécommunications | HAUTE |
| SEMC | 2023 | Industriels | HAUTE |
| SOGC | 2022 | Consommation de base | MOYENNE |
| SGBC | 2019 | Services financiers | FAIBLE |
| NEIC | 2017 | Consommation discrétionnaire | FAIBLE |
| BICC | 2022 | Services financiers | MOYENNE |
| SPHC | 2025 | Consommation de base | HAUTE |
| ORAC | 2022 | Télécommunications | MOYENNE |
| FTSC | 2024 | Industriels | HAUTE |
| SMBC | 2016 | Énergie | FAIBLE |
| SHEC | 2023 | Énergie | HAUTE |

Décision conditionnelle écrite à l'avance, pour éviter la fuite devant le résultat :

- **≥ 30 % de valeurs trouvées** → le bloc de 265 est en grande partie un trou de
  rappel du parseur. Priorité absolue au parseur, pas à la recherche documentaire.
- **10 à 30 %** → correction du parseur puis relecture ciblée des structures de
  page concernées.
- **< 10 %** → absence éditoriale majoritairement réelle. On cesse d'y investir
  et on documente le statut, sans le maquiller en valeur.

## Portée

Aucune ligne de ce backlog n'autorise une intégration dans `web/data/data.json`.
Un BPA recalculé comparable exige toujours un numérateur attribuable aux
actionnaires ordinaires vérifié et un nombre moyen pondéré d'actions vérifié.

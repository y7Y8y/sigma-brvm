# Compteurs BPA 480 — recalculés en machine

**Date :** 2026-10-26 · **Parseur :** eps-evidence-v2.1.4 · **Dataset publié modifié :** non

Source : `audits/audit_bpa_480_corrige_rejeu_v214_2026-10-26/matrix.csv` + overlay `ingestion/overlay_decisions_humaines.json`.

## Base officielle

La base de comptage officielle des indicateurs de couverture BPA est celle des 442 cellules applicables. Les 38 cellules antérieures à l'introduction sont comptées séparément, jamais fusionnées dans un taux.

| Indicateur | 480 brutes | 442 applicables |
|---|---:|---:|
| BPA publiés retenus dans la couverture | 31 | 31 |
| dont exclus de la comparabilité formelle | 2 | 2 |
| dont non exclus par décision | 29 | 29 |
| BPA recalculés comparables | 0 | 0 |
| Publications détectées non retenues | 34 | 34 |
| Quarantaine de cohérence | 1 | 1 |
| Ratios indicatifs fin d'exercice (séparés) | 8 | 8 |
| Séries chiffrées extraites | 293 | 288 |
| Cellules avec document primaire examiné | 335 | 335 |
| Cellules avec document primaire lu | 342 | 335 |

## Statuts d'absence (base brute)

| Statut | Cellules |
|---|---:|
| `NON_PUBLIE_DANS_SOURCES_VERIFIEES` | 263 |
| `NON_RECHERCHE` | 18 |
| `DOCUMENT_INTROUVABLE` | 15 |
| `ILLISIBLE` | 72 |
| `NON_APPLICABLE` | 37 |

## Publications hors périmètre, non comptées dans la couverture

Ces valeurs existent et sont conservées comme information : elles ne sont jamais agrégées dans un taux de couverture BPA.

- **ORGT 2018** — `PUBLIE_EXTRAIT`, valeur conservée 115.0 FCFA, exercice non applicable (antérieur à l'introduction).

## Sommes de contrôle

| Contrôle | Observé | Attendu |
|---|---:|---:|
| C1 somme des statuts BPA (base brute) | 480 | 480 |
| C2 somme des niveaux de validation (base brute) | 480 | 480 |
| C3 somme des statuts documentaires (base brute) | 480 | 480 |
| C4 somme des statuts BPA (base applicable) | 442 | 442 |
| C5 applicables + non applicables | 480 | 480 |
| C6 non applicables | 38 | 38 |
| C7 BPA publiés sans valeur transcrite | 0 | 0 |
| C8 BPA recalculés comparables | 0 | 0 |
| C9 publiés + quarantaine + ratios + absences | 480 | 480 |

## Décisions ayant modifié la matrice : 2

- SPHC 2022 : `NON_PUBLIE_DANS_SOURCES_VERIFIEES` → `PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE` (decisions_humaines_v214.json)
- SPHC 2023 : `NON_PUBLIE_DANS_SOURCES_VERIFIEES` → `PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE` (decisions_humaines_v214.json)

## Portée

Aucun de ces compteurs n'autorise une intégration dans `web/data/data.json`. L'intégration reste décidée cellule par cellule.

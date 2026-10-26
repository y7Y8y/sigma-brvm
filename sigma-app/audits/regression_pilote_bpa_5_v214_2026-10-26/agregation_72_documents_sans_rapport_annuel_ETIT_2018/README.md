# Régression du pilote BPA — extracteur corrigé

Référence humaine : `audits/pilote_bpa_5/decisions.json` (50 cellules). Corpus rejoué : les documents déjà ouverts pendant le pilote, retéléchargés depuis leurs URL BRVM persistées. Aucune collecte complète et aucune réécriture du dataset publié.

- Cellules comparées : **50**
- BPA FCFA attendus : **18** ; concordants : **18**
- Attendus absents ou en quarantaine : **0**
- Valeurs divergentes : **0** ; faux positifs potentiels : **0**
- Publications rejetées par l'audit humain : **8** ; rejets démontrés concordants : **7** ; faux positifs sur ces rejets : **0** ; rejets non démontrés ou mauvais mécanisme : **1**
- Un rejet n'est démontré que si le candidat a été détecté puis écarté pour une raison compatible ; une absence de sortie peut aussi signifier que le document n'a pas été lu.
- Concordants mais extraction unique sans contrôle pondéré : **7**
- Documents rejoués : **72** ; SHA-256 identiques au pilote : **72** ; erreurs : **0**
- Porte 480 recalculée par le script : **EXTENSION_480_TOUJOURS_REFUSEE**

## Verdicts

- `ABSENCE_DE_VALEUR_RETENUE_CONCORDANTE` : 24
- `NON_RETENU_POUR_INCOHERENCE_CONCORDANT` : 1
- `PUBLIE_NON_RETENU_CONCORDANT` : 6
- `REJET_NON_DEMONTRE_AUCUN_CANDIDAT_DETECTE` : 1
- `VALEUR_CONCORDANTE` : 18

## Cellules à examiner

- **CIEC 2019** — `VALEUR_CONCORDANTE` ; attendu 140 ; extrait 140.0 ; candidat 140.0 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **CIEC 2025** — `VALEUR_CONCORDANTE` ; attendu 234 ; extrait 234.0 ; candidat 234.0 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **ETIT 2016** — `REJET_NON_DEMONTRE_AUCUN_CANDIDAT_DETECTE` ; attendu None ; extrait None ; candidat None ; validation `AUCUNE_VALEUR_RETENUE`.
- **ETIT 2022** — `VALEUR_CONCORDANTE` ; attendu 7.064 ; extrait 7.064 ; candidat 7.064 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **ETIT 2024** — `VALEUR_CONCORDANTE` ; attendu 8.23 ; extrait 8.2 ; candidat 8.2 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **SDSC 2021** — `VALEUR_CONCORDANTE` ; attendu 308.4 ; extrait 308.4 ; candidat 308.4 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **SNTS 2022** — `VALEUR_CONCORDANTE` ; attendu 2359 ; extrait 2359.0 ; candidat 2359.0 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **SNTS 2025** — `VALEUR_CONCORDANTE` ; attendu 3420 ; extrait 3420.0 ; candidat 3420.0 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.

Les détails par cellule sont dans `regression_matrix.json` et `regression_matrix.csv` ; les résultats document par document, empreintes comprises, sont dans `document_results.jsonl`.

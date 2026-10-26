# Régression du pilote BPA — extracteur corrigé

Référence humaine : `audits/pilote_bpa_5/decisions.json` (50 cellules). Corpus rejoué : les documents déjà ouverts pendant le pilote, retéléchargés depuis leurs URL BRVM persistées. Aucune collecte complète et aucune réécriture du dataset publié.

- Cellules comparées : **50**
- BPA FCFA attendus : **18** ; concordants : **15**
- Attendus absents ou en quarantaine : **3**
- Valeurs divergentes : **0** ; faux positifs potentiels : **0**
- Publications rejetées par l'audit humain : **8** ; rejets démontrés concordants : **8** ; faux positifs sur ces rejets : **0** ; rejets non démontrés ou mauvais mécanisme : **0**
- Un rejet n'est démontré que si le candidat a été détecté puis écarté pour une raison compatible ; une absence de sortie peut aussi signifier que le document n'a pas été lu.
- Concordants mais extraction unique sans contrôle pondéré : **5**
- Documents rejoués : **73** ; SHA-256 identiques au pilote : **73** ; erreurs : **0**
- Porte 480 recalculée par le script : **EXTENSION_480_TOUJOURS_REFUSEE**

## Verdicts

- `ABSENCE_DE_VALEUR_RETENUE_CONCORDANTE` : 24
- `NON_RETENU_POUR_INCOHERENCE_CONCORDANT` : 1
- `PUBLIE_NON_RETENU_CONCORDANT` : 7
- `VALEUR_ATTENDUE_NON_TROUVEE` : 3
- `VALEUR_CONCORDANTE` : 15

## Cellules à examiner

- **CIEC 2019** — `VALEUR_CONCORDANTE` ; attendu 140 ; extrait 140.0 ; candidat 140.0 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **CIEC 2025** — `VALEUR_CONCORDANTE` ; attendu 234 ; extrait 234.0 ; candidat 234.0 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **ETIT 2022** — `VALEUR_ATTENDUE_NON_TROUVEE` ; attendu 7.064 ; extrait None ; candidat None ; validation `AUCUNE_VALEUR_RETENUE`.
- **ETIT 2023** — `VALEUR_ATTENDUE_NON_TROUVEE` ; attendu 7.099 ; extrait None ; candidat None ; validation `AUCUNE_VALEUR_RETENUE`.
- **ETIT 2024** — `VALEUR_ATTENDUE_NON_TROUVEE` ; attendu 8.23 ; extrait None ; candidat None ; validation `AUCUNE_VALEUR_RETENUE`.
- **SDSC 2021** — `VALEUR_CONCORDANTE` ; attendu 308.4 ; extrait 308.4 ; candidat 308.4 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **SNTS 2022** — `VALEUR_CONCORDANTE` ; attendu 2359 ; extrait 2359.0 ; candidat 2359.0 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **SNTS 2025** — `VALEUR_CONCORDANTE` ; attendu 3420 ; extrait 3420.0 ; candidat 3420.0 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.

Les détails par cellule sont dans `regression_matrix.json` et `regression_matrix.csv` ; les résultats document par document, empreintes comprises, sont dans `document_results.jsonl`.

# Régression du pilote BPA — extracteur corrigé

Référence humaine : `audits/pilote_bpa_5/decisions.json` (50 cellules). Corpus rejoué : les documents déjà ouverts pendant le pilote, retéléchargés depuis leurs URL BRVM persistées. Aucune collecte complète et aucune réécriture du dataset publié.

- Cellules comparées : **10**
- BPA FCFA attendus : **3** ; concordants : **3**
- Attendus absents ou en quarantaine : **0**
- Valeurs divergentes : **0** ; faux positifs potentiels : **0**
- Publications rejetées par l'audit humain : **7** ; rejets démontrés concordants : **6** ; faux positifs sur ces rejets : **0** ; rejets non démontrés ou mauvais mécanisme : **1**
- Un rejet n'est démontré que si le candidat a été détecté puis écarté pour une raison compatible ; une absence de sortie peut aussi signifier que le document n'a pas été lu.
- Concordants mais extraction unique sans contrôle pondéré : **2**
- Documents rejoués : **10** ; SHA-256 identiques au pilote : **10** ; erreurs : **0**
- Porte 480 recalculée par le script : **EXTENSION_480_TOUJOURS_REFUSEE**

## Verdicts

- `PUBLIE_NON_RETENU_CONCORDANT` : 6
- `REJET_NON_DEMONTRE_AUCUN_CANDIDAT_DETECTE` : 1
- `VALEUR_CONCORDANTE` : 3

## Cellules à examiner

- **ETIT 2016** — `REJET_NON_DEMONTRE_AUCUN_CANDIDAT_DETECTE` ; attendu None ; extrait None ; candidat None ; validation `AUCUNE_VALEUR_RETENUE`.
- **ETIT 2022** — `VALEUR_CONCORDANTE` ; attendu 7.064 ; extrait 7.064 ; candidat 7.064 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.
- **ETIT 2024** — `VALEUR_CONCORDANTE` ; attendu 8.23 ; extrait 8.2 ; candidat 8.2 ; validation `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE`.

Les détails par cellule sont dans `regression_matrix.json` et `regression_matrix.csv` ; les résultats document par document, empreintes comprises, sont dans `document_results.jsonl`.

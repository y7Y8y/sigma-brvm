# Audit BPA 480 — revue, taux applicables et décision

Généré le 2026-10-26T00:40:31Z à partir de la matrice brute du 2026-10-26T00:36:30Z.

Aucune valeur de cet audit n'a été intégrée au dataset publié. Empreinte du dataset relu : `ed5ba551705cd6f9ddb5ecaa345ca22712cb41be2317310c235fbf8a36fd1efb`.

## Périmètre réel

- Cellules brutes 48 × 10 : **480**.
- Exercices avant introduction vérifiée : **38** (`NON_APPLICABLE`).
- Cellules applicables : **442**.
- Applicables avec au moins un document primaire lu couvrant l'exercice : **336** (76.018 %).
- Applicables avec série chiffrée extraite : **285** (64.48 %).
- Documents inventoriés / candidats sélectionnés / résultats journalisés : **3500 / 660 / 660** ; SHA-256 documentaire présent sur **657** résultats.
- Rejets de contenu : **3** autre émetteur, **26** intermédiaires ; **3** timeouts isolés.

## BPA publié : compteurs séparés

- Brut, toutes cellules : **34**.
- Brut, cellules applicables : **33**.
- Avant introduction, présenté séparément : **1** (ORGT 2018, exercice antérieur à la cotation du 16/04/2019).
- **Après revue des preuves, applicables : 29**.
  - confirmés par deux documents distincts : **7** ;
  - contrôle arithmétique concordant : **4** ;
  - extraction unique sans contrôle pondéré : **18**.
- Taux après revue : **6.561 %** des applicables et **8.631 %** des applicables examinées.
- BPA recalculés comparables sans BPA publié : **0**. Aucun ratio de fin d'exercice n'a été substitué.
- Publications détectées mais non retenues : **33** ; quarantaine : **1** ; ratios indicatifs séparés : **9**.

## Contrôle sur le pilote déjà fermé

- Valeurs humaines attendues retrouvées : **18/18**.
- Faux positifs sur les cellules sans valeur humaine retenue : **0**.
- Ce contrôle porte sur les valeurs ; certains libellés de statut de l'audit 480 sont plus prudents que ceux du pilote lorsqu'aucun état primaire n'a pu être prouvé dans le nouveau périmètre documentaire.

## Anomalies de preuve confirmées par relecture

- **SPHC 2020** — brut -21.0 FCFA, revue `PUBLIE_NON_RETENU_APRES_REVUE_DATE_PRISE_POUR_VALEUR`. La ligne de preuve est l'en-tête « Resultat par action 31-déc-21 31-déc-20 » : -21 provient du suffixe de date 31-déc-20, pas d'un montant par action.
- **SPHC 2021** — brut 31.0 FCFA, revue `PUBLIE_NON_RETENU_APRES_REVUE_DATE_PRISE_POUR_VALEUR`. La ligne de preuve est l'en-tête « Resultat par action 31-déc-21 31-déc-20 » : 31 est le jour de la date de clôture, pas un BPA.
- **TTLS 2024** — brut 128.0 FCFA, revue `PUBLIE_NON_RETENU_CONFLIT_PERIMETRE`. La valeur retenue vient de la page 39 des états IFRS individuels, alors que la matrice la présente au périmètre consolidé ; la page 42 consolidée donne 219 FCFA pour 2024.
- **TTLS 2025** — brut 205.0 FCFA, revue `PUBLIE_NON_RETENU_CONFLIT_PERIMETRE`. La valeur retenue vient de la page 39 des états IFRS individuels, alors que la matrice la présente au périmètre consolidé ; la page 42 consolidée donne 208 FCFA pour 2025.

Ces quatre cellules restent dans la matrice brute pour traçabilité, mais sont exclues des compteurs « après revue » ci-dessus.

## Statuts des cellules applicables (matrice brute)

- BPA `DOCUMENT_INTROUVABLE` : 15
- BPA `ILLISIBLE` : 71
- BPA `NON_PUBLIE_DANS_SOURCES_VERIFIEES` : 262
- BPA `NON_RECHERCHE` : 18
- BPA `PUBLIE_CONFIRME_DEUX_DOCUMENTS` : 7
- BPA `PUBLIE_EN_QUARANTAINE_COHERENCE` : 1
- BPA `PUBLIE_EXTRAIT` : 25
- BPA `PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE` : 33
- BPA `PUBLIE_SOURCE_DIVERGENTE_RESOLUE_PAR_CONTROLE` : 1
- BPA `RATIO_INDICATIF_FIN_EXERCICE` : 9

- Documentaire `CANDIDATS_INVENTORIES_NON_OUVERTS` : 2
- Documentaire `DOCUMENTS_OUVERTS_SANS_ETAT_PRIMAIRE_PROUVE` : 12
- Documentaire `DOCUMENTS_PRIMAIRES_EXAMINES` : 336
- Documentaire `DOCUMENT_INTROUVABLE` : 15
- Documentaire `ILLISIBLE` : 71
- Documentaire `NON_RECHERCHE` : 6

## Backlogs documentaires

- `ILLISIBLE` : **71** cellules. Principaux émetteurs : BOAN (10), BOABF (7), BOAM (7), BOAB (5), BOAS (5), STAC (5), PRSC (4), SICC (4), ABJC (3), CBIBF (3). La cause dominante est l'absence de texte natif exploitable dans des PDF scannés, sans OCR disponible dans l'environnement d'extraction.
- `DOCUMENT_INTROUVABLE` dans l'inventaire BRVM vérifié : **15** cellules : TTLS (7), CBIBF (4), SEMC (2), UNLC (2).
- `NON_RECHERCHE` : **18** cellules : ECOC (2), ONTBF (2), SDCC (2), SDSC (2), SIBC (2), SIVC (2), SNTS (2), CBIBF (1), SAFC (1), SLBC (1), TTLS (1). Aucune n'a été convertie en non-publication.
- Publications non retenues par émetteur : ETIT (6), PRSC (6), SPHC (4), BOAB (3), BOABF (3), BOAM (3), BNBC (2), BOAS (2), ORAC (2), SIBC (1), SNTS (1).

## Décision

Audit 480 terminé en mode statuts et preuves. Aucune intégration au dataset publié n'est autorisée à ce stade : les extractions uniques, le conflit de périmètre TTLS, la quarantaine SDSC 2022, les publications non retenues et le backlog OCR doivent être traités séparément.

Ordre de traitement suivant :

1. Corriger les deux défauts démontrés (dates prises pour des valeurs chez SPHC ; mélange individuel/consolidé chez TTLS), ajouter les tests et rejouer la régression pilote.
2. Contre-lire les 18 extractions uniques restantes et la quarantaine SDSC 2022.
3. Traiter le backlog OCR, en commençant par les banques BOA dont les états scannés bloquent des séries entières.
4. Rechercher les documents annuels absents de l'inventaire BRVM (TTLS 2016-2022, CBIBF 2016-2019, SEMC/UNLC 2024-2025) dans des sources officielles complémentaires.
5. Ne décider d'une intégration au dataset qu'après ces contrôles, cellule par cellule.

Fichiers détaillés : `summary_applicable.json`, `review_queue.csv`, `matrix.json`, `matrix.csv`, `document_results.jsonl`, `inventory.json`, `candidate_plan.json` et `listing_dates_supplement_applied.json`.

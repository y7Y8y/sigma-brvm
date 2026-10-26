# Revue des extractions uniques et décision de porte — pilote BPA

Date de revue : 25 octobre 2026.

## Résultat de la régression réelle

La régression finale rejoue les **73 PDF** du pilote. Les 73 empreintes SHA-256 sont identiques à celles du pilote, sans erreur documentaire.

- Cellules comparées aux décisions humaines : **50/50 verdicts concordants**.
- BPA FCFA retenus par l'audit humain : **18/18 retrouvés concordants**.
- Cellules sans BPA retenu : **32/32 sans valeur retenue**.
- Publications humaines rejetées : **8/8 rejets démontrés** par détection d'un candidat puis exclusion ou quarantaine pour une raison compatible.
- Faux positifs : **0**. Valeurs divergentes retenues : **0**.
- Suite de tests du collecteur : **96 réussis**.
- Dataset publié : inchangé (`generated_at=2026-10-22T21:20:37+00:00`, SHA-256 `ed5ba551705cd6f9ddb5ecaa345ca22712cb41be2317310c235fbf8a36fd1efb`).

ETIT 2024 est extrait à **8,2 FCFA** depuis le compte de résultat, contre **8,23 FCFA** retenus par le pilote depuis les chiffres clés du même document certifié. L'écart est dans l'arrondi de publication à une décimale ; la valeur automatisée à conserver est donc 8,2 avec sa précision publiée, sans prétendre avoir extrait 8,23.

## Les sept cellules en extraction unique

« Extraction unique » signifie ici : valeur concordante avec le pilote, mais un seul document automatisé et aucun contrôle automatisé par un dénominateur moyen pondéré. Ce niveau reste inférieur à la validation humaine du pilote.

| Cellule | Valeur automatisée | Revue |
|---|---:|---|
| CIEC 2019 | 140 | Ligne de base/diluée relue dans les IFRS consolidés 2020. Le pilote contrôle 7 826 M / 56 000 000 = 139,75. Le numérateur automatisé retenu pour le ratio indicatif n'est pas ce numérateur consolidé : aucun contrôle pondéré automatisé ne doit être revendiqué. |
| CIEC 2025 | 234 | Page IFRS consolidée 2025 ; ratio indicatif automatisé 233,93 avec 13 100 M / 56 000 000. Cohérent, mais le dénominateur reste de fin d'exercice. |
| ETIT 2022 | 7,064 | Chiffres clés 2023 croisés avec le BPA de base 1,165 cent USD du compte de résultat du même document ; activités arrêtées en tirets. Promotion documentée par `VALEUR_COMPAGNE_EGALE_AU_BPA_DE_BASE_DU_MEME_DOCUMENT`. |
| ETIT 2024 | 8,2 | Compte de résultat certifié 2024, BPA de base et dilué identiques ; aucune composante de résultat arrêtée détectée dans le document complet. La vintage 2025 reclassée reste séparée et non retenue. |
| SDSC 2021 | 308,4 | Comparatif consolidé 2021 dans les comptes 2022 ; numérateur part du groupe automatisé 16 780 M. Le pilote contrôle 308,35 avec 54 418 250 actions, mais ce dénominateur n'a pas été retenu automatiquement pour la cellule. |
| SNTS 2022 | 2 359 | Compte consolidé à trois exercices du rapport annuel 2024 ; numérateur automatisé 235 974 M. Le pilote contrôle 2 359,74 avec 100 000 000 actions et rejette le 2 110 décalé des états condensés. |
| SNTS 2025 | 3 420 | États 2025 ; numérateur attribuable automatisé 341 963 M. Le pilote contrôle 3 419,63 avec le dénominateur stable de 100 000 000, non répété dans le document condensé. |

## Décision

La **porte de concordance des valeurs est franchie** : l'extracteur reproduit les 50 décisions du pilote, y compris les rejets.

En revanche, une valeur `PUBLIE_EXTRAIT` issue d'une seule extraction sans contrôle pondéré ni second document ne doit pas être présentée comme validée au même niveau qu'une valeur confirmée par deux documents ou par un contrôle arithmétique pondéré.

La suite autorisée est donc :

1. **étendre l'audit aux 480 cellules en mode statuts et preuves**, sans écrire dans le dataset publié ;
2. conserver séparément BPA publié confirmé, BPA publié extrait unique, BPA recalculé comparable, candidat part du groupe pondérée, ratio indicatif et quarantaines ;
3. n'intégrer au dataset publié que les niveaux de validation prévus par le contrat de données, après revue des extractions uniques et des divergences ;
4. ne calculer aucun PER comparable à partir d'un ratio indicatif ou d'un candidat non contrôlé.

Le verdict automatique du harnais reste volontairement `EXTENSION_480_REFUSEE_AVANT_REVUE_DES_EXTRACTIONS_UNIQUES` : cette revue lève le blocage pour l'audit 480 en mode statuts, mais **pas** pour une intégration silencieuse en production.

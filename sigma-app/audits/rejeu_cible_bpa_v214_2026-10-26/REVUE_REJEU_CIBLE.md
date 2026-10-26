# Rejeu ciblé BPA — parseur `eps-evidence-v2.1.4`

Date : 26 octobre 2026  
Dataset publié : **inchangé**  
Intégration au dataset : **aucune**

## Objet

Ce rejeu vérifie le correctif de détection d'exercice introduit après
l'inspection des PDF réels CABC, STBC et SIBC. La version 2.1.3 retenait
l'année datée éligible la plus récente ; elle confondait donc l'exercice
principal avec les mandats futurs et les perspectives de l'exercice suivant.

La version 2.1.4 retient, dans le niveau de preuve applicable, l'année la plus
fréquente ; l'année la plus récente ne sert qu'à départager les égalités.

## Couverture du rejeu

- Manifeste : **125 documents**.
- Documents effectivement rejoués : **123**.
- Fichiers de résultat produits : **123/123**.
- SHA-256 documentaires concordant avec le journal historique : **123/123**.
- Documents exclus avant exécution : **2 timeouts historiques déjà connus** :
  - rapport annuel ETIT 2018 (`f67fd4f860515787`) ;
  - rapport CAC SIVC (`425159842d38f843`), déjà en timeout dans le journal
    historique et reconfirmé en v2.1.3 après 300,553 s.

Le processus supervisé s'est terminé avec le code 1 parce que le harnais
classe BICC `d9b1ec7ede71e8e0` en `ECHEC`. Il ne s'agit pas d'un document
absent : le sous-processus a retourné 0 et un résultat explicite
`REJETE_TROP_VOLUMINEUX` a été produit, sans observation par action, comme
dans le journal historique. Aucun des 123 documents n'est donc manquant.

## Validation préalable sur documents réels

Avant ce rejeu :

- tests ciblés d'exercice : **6/6** ;
- suite complète : **107 tests réussis** ;
- pilote 5 sociétés × 10 exercices, 72 documents rejoués hors rapport ETIT
  2018 complet : **18/18 valeurs concordantes**, **0 faux positif**,
  **0 valeur divergente**, 72 SHA-256 identiques ;
- supplément ETIT 2018 sur 23 pages ciblées : observations sémantiquement
  identiques à la v2.1.3.

La porte d'intégration reste néanmoins fermée : les cellules en extraction
unique et les décisions humaines ci-dessous doivent être lues avant tout usage
dans le dataset ou dans un PER comparable.

## Delta contre le journal historique

- Documents sémantiquement modifiés : **26**.
- Documents inchangés : **97**.
- Cellules société-exercice avec delta BPA : **22**.
  - changement non éligible ou doublon seulement : 9 ;
  - éligibilité ou périmètre modifié : 11 ;
  - éligibilité retirée : 2.

### Exercices effectifs corrigés

Quinze documents changent d'exercice effectif et rejoignent l'exercice porté
par leurs preuves datées dominantes :

| Émetteur | Document | Ancien → v2.1.4 |
|---|---|---:|
| BOABF | Rapport annuel 2018 | 2017 → 2018 |
| BOAC | Rapport annuel 2018 | 2019 → 2018 |
| BOAM | Rapport annuel 2018 | 2017 → 2018 |
| BOAS | AG ordinaire et états certifiés | 2020 → 2019 |
| CABC | Rapport annuel exercice 2017 | 2019 → 2017 |
| CABC | Rapport annuel exercice 2020 | 2023 → 2020 |
| CABC | Rapport annuel exercice 2023 | 2026 → 2023 |
| CABC | Rapport d'activités exercice 2024 | 2027 → 2024 |
| LNBB | États financiers exercice 2024 | 2023 → 2024 |
| SCRC | États financiers IFRS exercice 2023 | 2022 → 2023 |
| SIBC | États financiers exercice 2019 | 2020 → 2019 |
| SPHC | États financiers exercice 2020 | 2019 → 2020 |
| STBC | Attestation CAC exercice 2022 | 2025 → 2022 |
| STBC | Rapport annuel exercice 2016 | 2017 → 2016 |
| STBC | Rapport annuel exercice 2025 | 2026 → 2025 |

Contrôles directs ayant motivé la règle par fréquence :

- CABC 2024 : preuves datées 2024 = 4, contre 2027 = 2 ;
- STBC 2022 : 2022 = 3, contre 2025 = 1 ;
- SIBC 2019 : candidats 2019 = 8, contre 2020 = 2.

### Désaccords résiduels nom de fichier / exercice effectif

Dans le journal combiné v2.1.4, les désaccords passent de **18 à 4** :

- ETIT, présentation à fin septembre 2017 : exercice effectif 2016 ;
- SEMC, libellé exercice 2017 : exercice effectif 2016 ;
- SGBC, libellé exercice 2019 : exercice effectif 2018 ;
- SNTS, nom se terminant par `25022021` : exercice de nom interprété 2021,
  exercice effectif 2020.

Ces quatre cas ne doivent pas être « corrigés » en forçant le nom de fichier :
le contenu lu peut être un comparatif, un extrait ou un document dont le
libellé BRVM est trompeur. Ils restent des points de lecture documentaire, pas
des preuves d'absence.

## Cas SPHC vérifié séparément

Le document SPHC exercice 2020 bascule correctement vers les cibles
2020/2019. Les valeurs brutes 1,695 et 0,666 restent non éligibles : page en
milliers sans unité par action explicite. Elles ne sont ni converties ni
promues en FCFA par action.

La relecture directe des exercices 2022 et 2023 est traitée dans la revue de
l'overlay : ces cellules ne sont pas des absences, mais des publications sous
échelle non retenues.

## Conclusion du rejeu

Le correctif v2.1.4 est validé sur le pilote et sur les 123 documents ciblés.
Il corrige les décalages CABC/STBC/SIBC sans créer de nouveau BPA publié dans
le pilote. En revanche, ce rejeu ciblée ne vaut ni rejeu intégral des 660 PDF,
ni autorisation d'intégration. L'overlay et les décisions humaines doivent
être utilisés ensemble.

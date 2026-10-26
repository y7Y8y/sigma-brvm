# Audit pilote BPA fermé — 5 sociétés × 10 exercices (2016–2025)

**Date de clôture du pilote : 24 octobre 2026.**

## Décision de porte

**La collecte complète BPA sur les 480 cellules ne doit pas être lancée avec l'extracteur actuel.** Le pilote est fermé documentairement (50/50 cellules classées), mais il prouve des défauts bloquants de sélection, de mise en page, de devise/composantes, de colonnes et de contrôle de cohérence. La prochaine étape est de corriger ces défauts, puis de rejouer exactement ces 50 cellules comme test de non-régression avant toute extension.

Aucune collecte complète n'a été lancée et le jeu de données publié de SIGMA n'a pas été modifié par ce pilote.

## Périmètre fermé

Les pages BRVM des cinq émetteurs contiennent 485 documents indexés dans l'inventaire profond. 73 sources candidates (annuelles, comparatives ou pièces d'audit) ont été ouvertes et contre-lues, dont 1 document d'un autre émetteur, exclu. Les statuts d'absence valent uniquement pour les sources énumérées dans `sources_examinees.csv` et les décisions de `decisions.json` ; ils ne prétendent pas épuiser les sites des émetteurs.

| Société | Introduction BRVM | Périmètre de référence du pilote | Rôle dans le pilote |
|---|---:|---|---|
| CIEC — CIE COTE D'IVOIRE | 1998-09-16 | IFRS consolidé | série IFRS récente, fractionnement 2017 |
| SNTS — SONATEL SENEGAL | 1998-10-02 | IFRS consolidé | consolidé IFRS, troisième colonne et source divergente |
| SDSC — AFRICA GLOBAL LOGISTICS COTE D'IVOIRE (ex-Bolloré Transport & Logistics CI) | 1998-09-16 | IFRS consolidé | consolidé vs individuel, autocontrôle, scans et changement de nom |
| BOAC — BANK OF AFRICA COTE D'IVOIRE | 2010-04-07 | États bancaires annuels PCB/SYSCOHADA | banque sans BPA publié, capital doublé en 2017 et en 2024 |
| ETIT — Ecobank Transnational Incorporated TOGO | 2006-09-11 | IFRS consolidé du groupe, présentation USD avec traductions FCFA dans certaines publications BRVM | USD/FCFA, activités arrêtées, retraitements et long rapport en anglais |

Les cinq introductions sont antérieures à 2016 : les 50 cellules sont donc applicables et le dénominateur des taux du pilote est 50.

## Taux séparés — aucun taux global masquant les lacunes

| Mesure | Numérateur | Dénominateur | Taux | Lecture |
|---|---:|---:|---:|---|
| BPA publié en FCFA, validé et retenu | 18 | 50 | 36 % | seule couverture BPA comparable retenue par le pilote |
| dont confirmé par au moins deux documents distincts | 8 | 50 | 16 % | niveau de confirmation le plus fort |
| dont un document + contre-lecture/contrôle indépendant | 10 | 50 | 20 % | inclus dans les 18 ; ce contrôle ne transforme pas la valeur en BPA recalculé comparable |
| BPA recalculé comparable substitué à une publication | 0 | 50 | 0,0 % | les recalculs sont des contrôles, pas des substitutions |
| Ratio indicatif résultat / actions de fin d'exercice | 13 | 50 | 26 % | hors couverture BPA |
| Publication par action trouvée mais non retenue | 8 | 50 | 16 % | devise/composante ou incohérence de source |
| Non publié dans les sources vérifiées | 22 | 50 | 44 % | après examen effectif des sources listées |
| Document annuel complet introuvable | 2 | 50 | 4 % | SNTS 2019 et 2020 |
| Illisible / non recherché / non applicable | 0 / 0 / 0 | 50 | 0,0 % | après OCR ciblé et lectures visuelles |

Contrôles numérateur attribuable ou part du Groupe ÷ nombre moyen pondéré : 6 concordants sur des BPA retenus et 1 discordant rejeté (SDSC 2022). 5 cellules SDSC possèdent aussi un BPA individuel IFRS, conservé séparément du périmètre consolidé.

## Résultat par société

| Société | BPA FCFA retenu /10 | Confirmé 2 documents | Ratio indicatif séparé | Cellules sans BPA retenu |
|---|---:|---:|---:|---:|
| CIEC | 7 | 5 | 1 | 3 |
| SNTS | 4 | 1 | 3 | 6 |
| SDSC | 4 | 1 | 0 | 6 |
| BOAC | 0 | 0 | 9 | 10 |
| ETIT | 3 | 1 | 0 | 7 |

### CIEC — CIE COTE D'IVOIRE

- Le BPA IFRS consolidé est présent et cohérent de 2019 à 2025, avec 56 000 000 d'actions. Les documents récents mélangent dans un même PDF les états personnels SYSCOHADA et les états consolidés IFRS : le périmètre doit être lu dans le contenu, pas dans le seul nom du fichier.
- 2016–2018 ne publient pas de BPA dans les sources ouvertes. Le fractionnement de 20 pour 1 du 19 octobre 2017 interdit d'appliquer rétrospectivement le dénominateur actuel sans mention d'unité.
- **BPA retenus :** 2019 : 140 FCFA, 2020 : 307 FCFA, 2021 : 188 FCFA, 2022 : 183 FCFA, 2023 : 205 FCFA, 2024 : 188 FCFA, 2025 : 234 FCFA.

### SNTS — SONATEL SENEGAL

- Le BPA IFRS retenu couvre 2022–2025. Le rapport annuel 2024 est indispensable : il publie la troisième colonne 2022 et la note de dénominateur pondéré. Les états condensés 2024 contiennent une ligne BPA décalée (2 359 sous 2023 au lieu de 2 794 ; 2 110 sous 2022).
- 2019 et 2020 restent en DOCUMENT_INTROUVABLE : l'inventaire BRVM ne contient que des synthèses/rapports de gestion, sans numérateur attribuable. Pour 2016–2018, l'ancien libellé « part de l'entreprise consolidante » et les pages au-delà de 80 échappent à l'extracteur.
- **BPA retenus :** 2022 : 2 359 FCFA, 2023 : 2 794 FCFA, 2024 : 3 288 FCFA, 2025 : 3 420 FCFA.

### SDSC — AFRICA GLOBAL LOGISTICS COTE D'IVOIRE (ex-Bolloré Transport & Logistics CI)

- Les comptes consolidés IFRS donnent un BPA validé pour 2018–2021, avec numérateur part du Groupe et dénominateur pondéré tenant compte des actions d'autocontrôle. Les comptes individuels IFRS publient d'autres BPA (266, 232, 349, 371, 318) qui ne doivent jamais être fusionnés avec la série consolidée.
- 2022 est rejeté : le BPA consolidé imprimé (250,9) ne concorde ni avec le résultat part du Groupe du compte (contrôle 259,54) ni avec une note propre. À partir de 2023, les sources BRVM ouvertes sont des synthèses SYSCOHADA/rapports CAC sans BPA.
- **BPA retenus :** 2018 : 280,1 FCFA, 2019 : 202,6 FCFA, 2020 : 266,5 FCFA, 2021 : 308,4 FCFA.

### BOAC — BANK OF AFRICA COTE D'IVOIRE

- Aucun BPA publié sur les dix exercices dans les sources vérifiées. Les états bancaires fournissent en revanche le résultat et le capital ; les ratios de fin d'exercice sont donc tenus dans une colonne séparée.
- La structure du capital change deux fois : attribution gratuite 1 pour 1 puis fractionnement 10 pour 1 en 2017, puis nouvelle attribution gratuite 1 pour 1 en 2024 (capital 20 → 40 milliards, jouissance au 1er janvier 2024). Toute série par action exige un registre d'événements et un retraitement explicite.
- **BPA retenus : aucun.**

### ETIT — Ecobank Transnational Incorporated TOGO

- Toutes les années contiennent une information par action, mais seules 2022–2024 sont retenues en FCFA comme totaux de leur vintage. Les autres années sont bloquées par la devise USD, la séparation activités poursuivies/arrêtées, des retraitements ou des versions remplacées.
- Le document 2017 d'Ecobank Côte d’Ivoire présent dans les candidats ETIT est exclu : c'est un autre émetteur. Les décimales espacées (« 1 ,041 », « 1 .68 », « 1 0.00 ») et les doubles colonnes cents USD/FCFA rendent l'extracteur actuel non fiable sur cet émetteur.
- **BPA retenus :** 2022 : 7,064 FCFA, 2023 : 7,099 FCFA, 2024 : 8,23 FCFA.

## Défauts prouvés à corriger avant la collecte complète

| Priorité | Chantier | Correctif exigé |
|---|---|---|
| P0 | Sélection documentaire | Approfondir la pagination et reconnaître les « comptes consolidés/individuels IFRS » classés « autre » ; exclure tout document dont l'émetteur lu dans le PDF diffère de la page d'origine ; exclure explicitement les intermédiaires au 30 juin/31 mars/30 septembre. |
| P0 | Mise en page BPA | Lire les en-têtes BPA suivis des années et de la sous-ligne « - de base » sur plusieurs lignes ; ne jamais prendre une référence de note (9.2, 8) ni un numéro de page de sommaire pointillé pour une valeur. |
| P0 | Devise et composantes | Ajouter devise, composante (total/poursuivies/arrêtées), périmètre (consolidé/individuel/social) et vintage (initial/retraité/audité) avant tout champ BPA unique. Sans ces champs, ETIT et SDSC ne sont pas publiables proprement. |
| P0 | Colonnes et pages | Traiter les tableaux à trois exercices et les colonnes précédent-d'abord ; rechercher d'abord les pages pertinentes dans tout le texte au lieu de s'arrêter à 80 pages ou 24 pages OCR. |
| P0 | Nombres | Parser les décimales avec espaces autour du séparateur et les doubles colonnes cents USD/FCFA sans mélanger les unités ; conserver la ligne et les coordonnées de colonne comme preuve. |
| P0 | Cohérence source | Mettre en quarantaine toute valeur dont le contrôle numérateur/dénominateur diverge au-delà de la tolérance d'arrondi, et toute ligne contredite par un rapport annuel plus complet (SNTS 2023, SDSC 2022). |
| P1 | Capital | Construire le registre des fractionnements, actions gratuites, augmentations et actions d'autocontrôle avant de calculer ou d'enchaîner un ratio par action. |
| P1 | Performance | Éviter le traitement intégral coûteux des très longs rapports : index texte rapide, ciblage des pages BPA/capital, puis extraction structurée des seules pages retenues. |

## Matrice fermée des 50 cellules

La colonne « preuve principale » renvoie au premier document cité ; la validation complète, les intrants et le verdict sur l'extracteur sont dans `decisions.json`, `pilot_matrix.csv` et `pilot_matrix.json`.

| Société | Exercice | Statut BPA | BPA retenu (FCFA) | Ratio indicatif séparé | Preuve principale |
|---|---:|---|---:|---:|---|
| CIEC | 2016 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Etats financiers exercice2016 cie (p. 1) |
| CIEC | 2017 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Etats financiers 2017 cie (p. 1) |
| CIEC | 2018 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 88,03 | Rapport annuel 2018 cie (p. 49, 52-53) |
| CIEC | 2019 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 140 | — | Etats financiers consolides ifrs exercice 2020 cie ci 0 (p. 1) |
| CIEC | 2020 | PUBLIE_CONFIRME_DEUX_DOCUMENTS | 307 | — | Etats financiers consolides ifrs exercice 2020 cie ci 0 (p. 1) |
| CIEC | 2021 | PUBLIE_CONFIRME_DEUX_DOCUMENTS | 188 | — | Etats financiers ifrs exercice 2021 cie (p. 1) |
| CIEC | 2022 | PUBLIE_CONFIRME_DEUX_DOCUMENTS | 183 | — | Etats financiers ifrs exercice 2022 cie ci (p. 1) |
| CIEC | 2023 | PUBLIE_CONFIRME_DEUX_DOCUMENTS | 205 | — | Etats financiers syscohada exercice 2023 cie ci (p. 3) |
| CIEC | 2024 | PUBLIE_CONFIRME_DEUX_DOCUMENTS | 188 | — | Etats financiers norme syscohada exercice 2024 cie ci (p. 3) |
| CIEC | 2025 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 234 | — | Etats financiers syscohada et ifrs exercice 2025 cie ci (p. 3) |
| SNTS | 2016 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 1 863,31 | Presentation resultats financiers 2017 sonatel (p. 41-42) |
| SNTS | 2017 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 1 718,01 | Rapport annuel 2018 sonatel (p. 151, 224) |
| SNTS | 2018 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 1 724,67 | Rapport annuel 2018 sonatel (p. 151, 224) |
| SNTS | 2019 | DOCUMENT_INTROUVABLE | — | — | Synthese rapport de gestion 2019 250220 vf 4 (p. ensemble du document) |
| SNTS | 2020 | DOCUMENT_INTROUVABLE | — | — | Sonatel rapport de gestion 2020 vf 25022021 (p. ensemble du document) |
| SNTS | 2021 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Comfi groupe sonatel resultats financiers 2022 fr v finale brvm (p. compte de résultat consolidé) |
| SNTS | 2022 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 2 359 | — | Rapport dactivites annuel exercice 2024 sonatel sn (p. 34) |
| SNTS | 2023 | PUBLIE_SOURCE_DIVERGENTE_RESOLUE | 2 794 | — | Rapport dactivites annuel exercice 2024 sonatel sn (p. 34, 45) |
| SNTS | 2024 | PUBLIE_CONFIRME_DEUX_DOCUMENTS | 3 288 | — | Rapport dactivites annuel exercice 2024 sonatel sn (p. 34, 45) |
| SNTS | 2025 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 3 420 | — | Etats financiers 2025 et attestation des cac sonatel sn (p. 20) |
| SDSC | 2016 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Etats financier exercice 2016 bollore (p. 1) |
| SDSC | 2017 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Bollore trans.log etats financier 2017 (p. 1-2) |
| SDSC | 2018 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 280,1 | — | Etats financiers exercice 2019 comptes consolides bollore transport logistics (p. 3, 29) |
| SDSC | 2019 | PUBLIE_CONFIRME_DEUX_DOCUMENTS | 202,6 | — | Etats financiers exercice 2019 comptes consolides bollore transport logistics (p. 3, 29) |
| SDSC | 2020 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 266,5 | — | Btl ci 2020 comptes consolides ifrs rapport general des cac (p. 3, 26) |
| SDSC | 2021 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 308,4 | — | Rapport des commissaires aux comptes etats financiers consolides exercice 2022 agl cote divoire (p. 3, 27) |
| SDSC | 2022 | PUBLIE_INCOHERENT_NON_RETENU | — | — | Rapport des commissaires aux comptes etats financiers consolides exercice 2022 agl cote divoire (p. 3, 27) |
| SDSC | 2023 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Etats financiers exercice 2023 africa global logistics ci (p. 1) |
| SDSC | 2024 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Etats financiers et rapport des cac exercice 2024 africa global logistics ci (p. 1-11) |
| SDSC | 2025 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Etats financiers certifies exercice 2025 africa global logistics ci (p. 1) |
| BOAC | 2016 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | — | Boa ci etats financiers 31 decembre 2017 (p. 2, 4) |
| BOAC | 2017 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 493,95 | Rapport annuel 2018 boa cote divoire (p. 43, 58) |
| BOAC | 2018 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 584,95 | Rapport annuel 2018 boa cote divoire (p. 43, 58) |
| BOAC | 2019 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 719,1 | Etats financiers exercice 2019 boa ci (p. 2-3) |
| BOAC | 2020 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 710,8 | Etats financiers exercice 2020 boa ci (p. 2-3) |
| BOAC | 2021 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 831,9 | Etats financiers exercice 2022 boa ci (p. 2, 27 et OCR ciblé 25-39) |
| BOAC | 2022 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 1 003,45 | Etats financiers exercice 2022 boa ci (p. 1-39) |
| BOAC | 2023 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 1 303,75 | Etats financiers exercice 2023 boa ci (p. 2) |
| BOAC | 2024 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 801,1 | Etats financiers exercice 2024 boa ci (p. 2) |
| BOAC | 2025 | NON_PUBLIE_DANS_SOURCES_VERIFIEES | — | 888,5 | Rapport des commissaires aux comptes et etats financiers annuels exercice 2025 boa ci (p. 15, OCR ciblé 25-53) |
| ETIT | 2016 | PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE | — | — | Rapport annuel 2018 ecobank group (p. 300) |
| ETIT | 2017 | PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE | — | — | Rapport annuel 2018 ecobank group (p. 175, 261) |
| ETIT | 2018 | PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE | — | — | Rapport annuel 2018 ecobank group (p. 175, 261, 300) |
| ETIT | 2019 | PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE | — | — | Etats financiers exercice 2019 eti tg (p. 1, 11) |
| ETIT | 2020 | PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE | — | — | Etats financiers audites exercice 2021 etit (p. 1, 5) |
| ETIT | 2021 | PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE | — | — | Etats financiers audites exercice 2021 etit (p. 1, 5) |
| ETIT | 2022 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 7,064 | — | Etats financiers exercice 2023 eti tg (p. 1, 3) |
| ETIT | 2023 | PUBLIE_CONFIRME_DEUX_DOCUMENTS | 7,099 | — | Etats financiers exercice 2023 eti tg (p. 1, 3) |
| ETIT | 2024 | PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE | 8,23 | — | Etats financiers certifies par les commissaires aux comptes exercice 2024 eti tg (p. 2, 4) |
| ETIT | 2025 | PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE | — | — | Etats financiers ifrs exercice 2025 eti tg (p. 1, 3) |

## Détail des validations indépendantes

### CIEC

- **2016 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Recherche plein texte sur les états 2016 (deux copies) et le comparatif 2017 : aucune ligne de résultat par action ni nombre d'actions. Résultat net lu : 10 780 309 milliers FCFA. _Extracteur actuel : Aucun BPA ; résultat net correct. Verdict : CONCORDANT._
- **2017 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. États 2017 natifs, version corrigée scannée relue en OCR et rapport annuel 2018 : aucune ligne BPA. Résultat net : 1 986 976 401 FCFA dans le rapport annuel 2018. _Extracteur actuel : Aucun BPA ; résultat net recoupé. Verdict : CONCORDANT._
- **2018 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. États 2018 et rapport annuel 2018 (59 pages) relus : résultat et nombre d'actions sont présents, mais aucune ligne de bénéfice par action. Le graphique « valeur mathématique de l'action » n'est pas un BPA. _Extracteur actuel : Aucun BPA ; résultat et dénominateur non fusionnés en BPA. Verdict : CONCORDANT._
- **2019 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. Ligne relue dans les états IFRS consolidés 2020, colonne 2019 : 140 FCFA. Contrôle : 7 826 millions FCFA / 56 000 000 = 139,75 FCFA. _Extracteur actuel : 140 FCFA depuis le document 2020 ; une copie OCR 2019 donne un résultat net faux de 534 423 000 FCFA. Verdict : BPA_CORRECT_OCR_A_REJETER._
- **2020 — PUBLIE_CONFIRME_DEUX_DOCUMENTS**. 307 FCFA dans les états IFRS 2020 et en comparatif des états IFRS 2021. Contrôle : 17 183 millions / 56 000 000 = 306,84 FCFA. _Extracteur actuel : 307 FCFA dans les deux documents IFRS. Verdict : CONCORDANT._
- **2021 — PUBLIE_CONFIRME_DEUX_DOCUMENTS**. 188 FCFA dans les états IFRS 2021 et en comparatif 2022. Contrôle : 10 511 millions / 56 000 000 = 187,70 FCFA. _Extracteur actuel : 188 FCFA dans les deux documents IFRS. Verdict : CONCORDANT._
- **2022 — PUBLIE_CONFIRME_DEUX_DOCUMENTS**. 183 FCFA dans les états IFRS 2022 et dans la partie consolidée IFRS du document 2023. Contrôle : 10 261 millions / 56 000 000 = 183,23 FCFA. _Extracteur actuel : 183 FCFA dans les deux documents. Verdict : CONCORDANT._
- **2023 — PUBLIE_CONFIRME_DEUX_DOCUMENTS**. 205 FCFA à la page IFRS consolidée du document 2023 et en comparatif du document 2024. Contrôle : 11 485 millions / 56 000 000 = 205,09 FCFA. _Extracteur actuel : 205 FCFA dans les deux documents ; copie scannée 2023 sans extraction utile. Verdict : CONCORDANT._
- **2024 — PUBLIE_CONFIRME_DEUX_DOCUMENTS**. 188 FCFA dans la partie IFRS du document 2024 et en comparatif du document 2025. Contrôle : 10 526 millions / 56 000 000 = 187,96 FCFA. _Extracteur actuel : 188 FCFA dans les deux documents. Verdict : CONCORDANT._
- **2025 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. 234 FCFA à la page IFRS consolidée 2025. Contrôle : 13 100 millions / 56 000 000 = 233,93 FCFA. _Extracteur actuel : 234 FCFA. Verdict : CONCORDANT._

### SNTS

- **2016 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. La présentation des résultats 2017 donne le résultat part de l'entreprise consolidante 2016 (186 331 millions) sans BPA. Le rapport annuel 2018 donne 100 000 000 actions ordinaires au titre de 2016 dans le tableau quinquennal, sans dénominateur pondéré IAS 33. _Extracteur actuel : Aucune extraction : libellé ancien non reconnu et états au-delà de la limite de pages. Verdict : ABSENCE_CORRECTE_MAIS_INTRANT_MANQUE._
- **2017 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Le compte de résultat consolidé 2018 présente 2017 en deux colonnes : réel 172 454 millions et proforma SYSCOHADA révisé 171 801 millions, sans ligne BPA. Le ratio séparé utilise la colonne proforma, cohérente avec 2018. _Extracteur actuel : Aucune extraction utile : états p. 151 et actions p. 224 au-delà de la limite de 80 pages. Verdict : MANQUE_EXTRACTEUR._
- **2018 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Compte de résultat consolidé du rapport annuel 2018, p. 151 : part de l'entreprise consolidante 172 467 millions, aucune ligne BPA. Actions ordinaires : 100 000 000 p. 224. _Extracteur actuel : Invisible pour l'extracteur en raison de la limite de 80 pages. Verdict : MANQUE_EXTRACTEUR._
- **2019 — DOCUMENT_INTROUVABLE**. Seule une synthèse de rapport de gestion est indexée pour 2019. Elle donne un résultat net consolidé arrondi (196,8 milliards) mais ni part attribuable, ni BPA, ni nombre d'actions. L'absence dans cette synthèse ne suffit pas à conclure à une non-publication dans des états complets non retrouvés. _Extracteur actuel : Faux résultat de 33 000 000 FCFA depuis une ligne de présentation dégradée ; aucun BPA. Verdict : VALEUR_FAUSSE_REJETEE._
- **2020 — DOCUMENT_INTROUVABLE**. Le rapport de gestion 2020 ouvert donne le résultat net consolidé total arrondi (201,3 milliards), sans part attribuable, BPA ni dénominateur. Aucun état consolidé annuel complet 2020 n'est présent dans l'inventaire BRVM du pilote. _Extracteur actuel : Aucune valeur retenue dans ce document de présentation. Verdict : ABSENCE_CORRECTE._
- **2021 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Présentation 2022 et états 2023 donnent le résultat attribuable aux propriétaires de la maison mère 2021 : 211 054 millions. Aucune ligne BPA dans les documents annuels ouverts. Le contrôle 211 054 / 100 000 000 = 2 110,54 FCFA n'est pas retenu comme ratio vérifié, faute de dénominateur pondéré ou de fin d'exercice publié pour 2021 dans ces sources. _Extracteur actuel : Numérateur extrait depuis la présentation 2022 ; aucun BPA. Verdict : ABSENCE_BPA_CONCORDANTE._
- **2022 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. Rapport annuel 2024, compte consolidé à trois colonnes p. 34 : 2 359 FCFA pour 2022. Contrôle avec le numérateur du même tableau : 235 974 millions / 100 000 000 = 2 359,74 FCFA. La valeur 2 110 imprimée sous 2022 dans les états condensés 2024 est rejetée : elle correspond au contrôle 2021 et révèle un décalage de la ligne BPA de ce document. _Extracteur actuel : BPA manqué : troisième colonne comparative ignorée. Verdict : MANQUE_EXTRACTEUR._
- **2023 — PUBLIE_SOURCE_DIVERGENTE_RESOLUE**. Rapport annuel 2024 : 2 794 FCFA au compte de résultat p. 34 et dans la note résultat par action p. 45. La note donne le dénominateur moyen pondéré 100 000 000 ; 279 448 millions / 100 000 000 = 2 794,48. Les états condensés 2024 impriment 2 359 sous 2023 et un dilué 3 298 supérieur au de base 2024 : ligne rejetée comme décalée/erronée. _Extracteur actuel : Deux valeurs concurrentes extraites : 2 359 et 2 794, sans résolution. Verdict : DIVERGENCE_NON_RESOLUE_PAR_L_EXTRACTEUR._
- **2024 — PUBLIE_CONFIRME_DEUX_DOCUMENTS**. 3 288 FCFA dans les états 2024, le rapport annuel 2024 et le comparatif des états 2025. Note du rapport annuel : dénominateur moyen pondéré 100 000 000 ; numérateur 328 750 millions, soit 3 287,50 FCFA avant arrondi de publication. _Extracteur actuel : 3 288 FCFA dans les trois documents. Verdict : CONCORDANT._
- **2025 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. 3 420 FCFA dans les états 2025. Le numérateur attribuable du même compte est 341 963 millions ; le contrôle par le dénominateur stable de 100 000 000 donne 3 419,63 FCFA. Le document condensé ne répète pas la note de dénominateur. _Extracteur actuel : 3 420 FCFA. Verdict : CONCORDANT._

### SDSC

- **2016 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Le seul document annuel 2016 indexé et ouvert est une synthèse d'une page en texte natif ; recherche complète sans ligne par action ni nombre d'actions. _Extracteur actuel : Aucun BPA. Verdict : CONCORDANT._
- **2017 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. États annuels 2017 de deux pages en texte natif sans BPA ni actions. Le rapport annuel 2018 scanné, relu en OCR sur ses pages financières d'ouverture, donne un résultat 2017 mais aucune ligne BPA. _Extracteur actuel : Aucun BPA. Verdict : CONCORDANT._
- **2018 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. Comptes consolidés 2019, p. 3 : 280,1 FCFA pour 2018 retraité IFRS. Note 9.2 p. 29 : numérateur utilisé 15 249 millions et 54 435 300 actions moyennes pondérées, soit 280,12 FCFA. _Extracteur actuel : Numérateur et dénominateur consolidés extraits, BPA consolidé manqué ; BPA individuel 266 extrait séparément dans les données brutes du pilote. Verdict : MANQUE_BPA_CONSOLIDE_RISQUE_DE_PERIMETRE._
- **2019 — PUBLIE_CONFIRME_DEUX_DOCUMENTS**. 202,6 FCFA au pied du compte consolidé 2019 (p. 3) et en comparatif des comptes consolidés 2020 (p. 3). Note : 11 030 millions / 54 435 300 = 202,63 FCFA. _Extracteur actuel : BPA consolidé manqué (présentation sur plusieurs lignes) ; intrants extraits. BPA individuel 232 extrait. Verdict : MANQUE_BPA_CONSOLIDE._
- **2020 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. Comptes consolidés IFRS 2020, p. 3 : 266,5 FCFA. Note 9.2 p. 26 : 14 501 millions / 54 420 286 = 266,44 FCFA, écart compatible avec les montants arrondis en millions. _Extracteur actuel : Document classé « autre » ; la référence de note 9.2 a été prise pour une valeur puis le BPA a été écarté par plausibilité. Intrants extraits. Verdict : MANQUE_EXTRACTEUR._
- **2021 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. Comptes consolidés 2022, p. 3 : 308,4 FCFA en comparatif 2021. Contrôle : 16 780 millions / 54 418 250 = 308,35 FCFA. La colonne 2021 de la note est cohérente, contrairement à la colonne 2022 du même tableau. _Extracteur actuel : BPA consolidé manqué ; BPA individuel 371 extrait, risque de substitution de périmètre. Verdict : MANQUE_BPA_CONSOLIDE._
- **2022 — PUBLIE_INCOHERENT_NON_RETENU**. Le compte consolidé p. 3 imprime 250,9 FCFA, mais son propre résultat part du Groupe est 14 124 millions ; avec 54 418 250 actions pondérées, le contrôle donne 259,54 FCFA. La note 8.2 p. 27 répète en outre 16 780 millions pour 2022 et 2021 et ne concorde pas avec les titres d'autocontrôle des comptes individuels. Aucune substitution silencieuse n'est faite. _Extracteur actuel : BPA consolidé manqué ; faux BPA individuel de 22 lu dans le sommaire pointillé (numéro de page), au lieu de 318 p. 5/22. Verdict : FAUX_POSITIF_ET_MANQUE._
- **2023 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. La page unique des états de synthèse provisoires 2023 a été lue visuellement : résultat net 17 138 527 milliers FCFA, capital en en-tête, aucune ligne BPA ni nombre d'actions. Aucun compte IFRS annuel 2023 n'est indexé dans le périmètre BRVM du pilote. _Extracteur actuel : OCR : 10 044 129 000 FCFA affecté à 2023 et 10 044 000 FCFA à 2022 ; la page montre 17 138 527 milliers pour 2023 et 10 044 129 milliers pour 2022. Verdict : OCR_COLONNES_ET_ECHELLE_FAUSSES._
- **2024 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Le PDF BRVM intitulé états et rapport CAC 2024 contient le rapport d'audit SYSCOHADA, sans les états joints annoncés. La synthèse 2025 donne le comparatif résultat 2024 (21 068 974 milliers) et le capital, sans BPA. Le statut vaut pour les sources effectivement vérifiées du pilote. _Extracteur actuel : Aucun chiffre annuel utile dans le seul rapport CAC ; aucun BPA. Verdict : ABSENCE_CORRECTE_DOCUMENT_INCOMPLET._
- **2025 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Synthèse 2025 lue visuellement et en texte natif sur une copie : résultat net 784 970 milliers FCFA ; attestation CAC : 784 970 349 FCFA. Aucune ligne BPA ni dénombrement d'actions dans la synthèse, l'attestation ou le rapport CAC de 10 pages. _Extracteur actuel : Résultat net concordant sur la copie native et l'OCR ; aucun BPA. Verdict : CONCORDANT_POUR_LE_RESULTAT._

### BOAC

- **2016 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Les états au 31/12/2017 présentent 2016 en première colonne : bénéfice 10 149 millions et capital 10 000 millions, sans BPA ni nombre d'actions. L'unité d'action d'alors est antérieure à l'attribution gratuite et au fractionnement de 2017 ; aucun ratio comparable n'est retenu. _Extracteur actuel : Aucun agrégat : colonnes précédent d'abord et libellé BENEFICE non exploité. Aucun faux BPA. Verdict : ABSENCE_BPA_CORRECTE_INTRANT_MANQUE._
- **2017 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Aucune ligne BPA. Le résultat 2017 publié initialement à 10 845 millions est présenté à 9 879 millions dans les documents 2018. Le rapport annuel 2018 donne 20 000 000 actions au 31/12/2017. Le ratio séparé utilise la version retraitée. _Extracteur actuel : Résultat retraité extrait depuis les documents 2018 ; document 2017 initial non exploité. Verdict : VERSIONS_A_DISTINGUER._
- **2018 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Rapport annuel 2018 : résultat de l'exercice 11 699 091 388 FCFA p. 58 ; 20 000 000 actions de nominal 1 000 FCFA p. 43 et p. 58. Le tableau p. 58 publie un dividende par action, pas un BPA. _Extracteur actuel : États provisoires corrects ; le rapport annuel produit aussi un faux résultat de 2 017 000 000 FCFA rejeté à la contre-lecture. Verdict : FAUX_RESULTAT_A_REJETER._
- **2019 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Deux copies des états annuels 2019 : capital souscrit 20 000 millions et résultat net 14 382 millions, colonnes 2018 puis 2019, aucune ligne BPA. Les états certifiés au 30 juin 2019 sont intermédiaires et exclus de l'exercice annuel. _Extracteur actuel : Résultat annuel correct ; le document au 30 juin a été traité comme source annuelle dans le pilote initial avant exclusion manuelle. Verdict : RISQUE_INTERMEDIAIRE._
- **2020 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. États 2020 : capital souscrit 20 000 millions, résultat net 14 216 millions, aucune ligne BPA ni dénominateur pondéré. _Extracteur actuel : Résultat correct, aucun BPA. Verdict : CONCORDANT._
- **2021 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Aucun état annuel propre 2021 dans l'inventaire. Le document scanné 2022 a été relu en OCR sur les 39 pages (24 par le passage contrôlé, 15 par OCR ciblé) : tableau triennal p. 27 « 14 216 / 16 638 / 20 069 » et capital 20 000 millions ; aucune ligne BPA. _Extracteur actuel : OCR limité à 24 pages mais valeur 2021 concordante avec le tableau p. 27 relu ensuite. Verdict : CONCORDANT_APRES_OCR_CIBLE._
- **2022 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Document 2022 de 39 pages scannées : capital 20 000 millions, résultat net 20 069 millions lu en OCR et confirmé par le comparatif natif 2023. Recherche BPA/actions sur toutes les pages après OCR ciblé des pages 25 à 39 : négative. _Extracteur actuel : Résultat OCR concordant avec 2023 ; limite native de 24 pages dépassée seulement par le passage ciblé du pilote. Verdict : CONCORDANT_APRES_CONTROLE._
- **2023 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. États 2023 et comparatif 2024 : capital 20 000 millions, résultat net 26 075 millions, aucune ligne BPA. _Extracteur actuel : Résultat concordant dans deux documents, aucun BPA. Verdict : CONCORDANT._
- **2024 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Les états 2024 montrent le capital passant de 20 000 à 40 000 millions et le résultat net de 32 044 millions, sans BPA ni dénominateur pondéré. L'opération est une attribution gratuite 1 pour 1 avec jouissance au 1er janvier 2024 ; le ratio de fin d'exercice ne doit pas être enchaîné avec 2023 sans retraitement du dénominateur. _Extracteur actuel : Résultat et saut de capital lisibles, aucun BPA ; aucun registre d'événement ne protège un ratio automatique. Verdict : RISQUE_DE_RUPTURE_DE_SERIE._
- **2025 — NON_PUBLIE_DANS_SOURCES_VERIFIEES**. Bilan scanné lu visuellement p. 15 : colonnes 31/12/2024 puis 31/12/2025, capital souscrit 40 000,00 dans les deux colonnes et résultat 35 540,00 millions en 2025. OCR ciblé des pages 25 à 53 : aucune ligne BPA/nombre d'actions. _Extracteur actuel : OCR de production limité à 24 pages ; résultat juste, mais l'ordre des colonnes du bilan est précédent puis courant. Verdict : CONCORDANT_APRES_LECTURE_VISUELLE._

### ETIT

- **2016 — PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE**. Rapport annuel 2018 du groupe, résumé quinquennal p. 300 : BPA de base 2016 de -1,01 cent USD et perte attribuable aux propriétaires de -249 898 milliers USD. Aucune traduction FCFA de ce BPA dans la source ; valeur conservée comme publication en devise, hors couverture FCFA. _Extracteur actuel : Aucune valeur : document de 324 pages en anglais, extracteur de production non terminé pendant le pilote. Verdict : MANQUE_EXTRACTEUR._
- **2017 — PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE**. Le document « Etats financiers 2017 ecobank ci » est celui d'Ecobank Côte d’Ivoire, autre émetteur : exclu. Pour ETI, note 16 du rapport annuel 2018 p. 261 : profit attribuable poursuivi 178 071 milliers USD, arrêté 514, dénominateur pondéré 24 607 640 milliers d'actions ; BPA poursuivi 0,72 cent et arrêté 0,00. Le total implicite est 0,7257 cent, sans BPA total FCFA directement publié. _Extracteur actuel : Aucune valeur du bon émetteur ; document Ecobank CI présent dans les candidats. Verdict : RISQUE_MAUVAIS_EMETTEUR._
- **2018 — PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE**. Version 2018 : BPA poursuivi 1,06 cent USD, arrêté 0,00 ; numérateur total 261 647 milliers USD et dénominateur 24 592 619 milliers, contrôle 1,0639 cent. Version retraitée dans les états 2019 : total attribuable 182 178 milliers, BPA poursuivi 0,74 cent et traduction FCFA 4,11. L'écart de vintage est matériel (-30,4 % sur le BPA) ; aucun choix silencieux n'est fait. _Extracteur actuel : Aucune valeur exploitable ; chiffres décimaux espacés et document annuel anglais de 324 pages. Verdict : MANQUE_EXTRACTEUR._
- **2019 — PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE**. BPA de base publié par composante : 0,78 cent USD pour les activités poursuivies et 0,01 pour les activités arrêtées ; les chiffres clés traduisent la seule composante poursuivie à 4,56 FCFA. Numérateurs : 191 409 et 2 549 milliers USD. Aucun BPA total FCFA directement publié dans le document condensé. _Extracteur actuel : 0,01 retenu comme BPA : c'est la composante activités arrêtées, pas le total. Verdict : FAUSSE_VALEUR_DE_COMPOSANTE._
- **2020 — PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE**. Comparatif audité 2021 : BPA poursuivi 0,010 cent USD et arrêté 0,007 ; numérateurs attribuables 2 400 et 1 801 milliers USD. Le total implicite est 0,017 cent, très différent de la seule composante poursuivie traduite à 0,056 FCFA. Aucun total FCFA publié. _Extracteur actuel : Aucun BPA 2020 exploitable ; décimales espacées 0 ,010 / 0 ,007. Verdict : MANQUE_EXTRACTEUR._
- **2021 — PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE**. Version auditée du 30/03/2022 préférée à la version de janvier : BPA poursuivi 1,063 cent USD (5,892 FCFA dans les chiffres clés) et arrêté 0,004 ; la version antérieure donnait 1,041. Le total implicite audité est 1,067 cent, sans total FCFA directement publié. _Extracteur actuel : 1,0 dans les deux versions : décimale espacée tronquée et devise ignorée. Verdict : FAUX_PARSE_DECIMAL._
- **2022 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. Document 2023 : chiffres clés 1,165 cent USD / 7,064 FCFA et compte de résultat 1,165 cent, avec tirets pour les activités arrêtées. Le numérateur attribuable est 286 430 milliers USD ; le dénominateur implicite du BPA USD est cohérent avec l'ordre de grandeur publié en 2018 (environ 24,59 milliards), sans conversion effectuée par l'audit. _Extracteur actuel : 1,0 : décimale espacée tronquée, colonne devise non distinguée. Verdict : FAUX_PARSE_DECIMAL_ET_DEVISE._
- **2023 — PUBLIE_CONFIRME_DEUX_DOCUMENTS**. Document 2023 : 1,170 cent USD / 7,099 FCFA ; document certifié 2024 en comparatif : 1,170 / 7,1. Activités arrêtées : tirets. Numérateur part du Groupe 287 824 milliers USD dans les deux comptes. _Extracteur actuel : 1,0 depuis 2023 et 8,0 depuis le comparatif 2024 : choix incohérent entre colonnes USD et FCFA. Verdict : FAUX_PARSE_DECIMAL_ET_DEVISE._
- **2024 — PUBLIE_EXTRAIT_VALIDE_PAR_CONTRE_LECTURE_ET_CONTROLE**. Document certifié 2024 : chiffres clés 1,35 cent USD / 8,23 FCFA ; compte de résultat 1,355 / 8,2. Aucune ligne d'activités arrêtées n'est séparée dans cette vintage et le résultat part du Groupe est 333 175 milliers USD. En 2025, le comparatif reclasse une perte d'activités en cours de cession et présente un BPA poursuivi différent (1,37 / 8,00) ; il ne remplace pas le total de la vintage 2024 dans ce pilote. _Extracteur actuel : 1,355 lu comme valeur du champ FCFA ; les comparatifs 2025 donnent 8,0. Devise et vintage non distinguées. Verdict : UNITE_FAUSSE_DANS_LE_CHAMP_ACTUEL._
- **2025 — PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE**. Les deux documents 2025 publient le BPA des activités poursuivies : 1,68 cent USD / 10,00 FCFA. Le compte présente séparément des activités arrêtées ou en cours de cession de -6 159 milliers USD au niveau du groupe, sans ventilation attribuable ni BPA de cette composante ; le BPA total n'est donc pas retenu. _Extracteur actuel : 1,0 : « 1 .68 » et « 1 0.00 » mal lus ; devise/composante non distinguées. Verdict : FAUX_PARSE_DECIMAL._

## Événements de capital utilisés uniquement comme drapeaux

- CIE : fractionnement de vingt actions nouvelles pour une ancienne le 19 octobre 2017 — page officielle BRVM : https://www.brvm.org/fr/fractionnement-dactions-cie-ci
- BOA Côte d’Ivoire : fractionnement de dix pour une en octobre 2017 — https://www.brvm.org/fr/fractionnement-dactions-bank-africa-cote-divoire ; convocation officielle à l'AGE du 10 octobre 2024 — https://www.brvm.org/sites/default/files/20240927_-_avis_de_convocation_-_assemblee_generale_extraordinaire_-_boa_ci.pdf ; jouissance des actions gratuites au 1er janvier 2024 annoncée par BOA — https://boacoteivoire.com/2024/08/26/augmentation-du-capital-des-filiales-cotees-a-la-brvm-et-de-boa-togo/

## Artefacts et reproductibilité

- `inventory.json` : inventaire profond des pages BRVM (485 documents).
- `extractions.json` : sorties brutes de l'extracteur, OCR contrôlé et notes sur les 73 sources ouvertes.
- `raw_second_reader.txt` et `raw_second_reader_supplements.txt` : lignes BPA/actions relues par un second lecteur.
- `boac_ocr_pages_25_plus_lines.txt` : OCR ciblé au-delà de la limite de 24 pages pour BOAC 2022 et 2025.
- `decisions.json` : décisions manuelles fermées, source de vérité du pilote.
- `pilot_matrix.csv`, `pilot_matrix.json`, `summary.json`, `sources_examinees.csv` : artefacts régénérés par `python3 -B ingestion/audit_pilot_bpa_5.py`.

**Conclusion :** le pilote valide la méthode d'audit cellule par cellule, mais invalide le lancement immédiat d'une collecte BPA complète. Les 18 BPA retenus constituent un banc de contrôle ; les 32 autres cellules montrent précisément pourquoi un champ BPA unique, sans devise, composante, périmètre, vintage et registre de capital, créerait de fausses séries.

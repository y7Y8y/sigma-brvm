# Contre-lecture des 18 BPA en extraction unique et de SDSC 2022

Date : 26 octobre 2026  
Parseur final : `eps-evidence-v2.1.1`  
Dataset publié : **inchangé**  
Intégration : **aucune**

## Résultat en bref

La file issue de la revue 480 contenait :

- **18 cellules** en `EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE` ;
- **1 quarantaine** : SDSC 2022.

Après relecture des preuves et des pages PDF :

- **18/18 BPA sont retenus comme valeurs publiées correctement lues** ;
- aucun faux positif de transcription n'a été trouvé dans ces 18 cellules ;
- SDSC 2022 reste **non retenu** : la quarantaine est confirmée par une
  incohérence interne de la source ;
- les 18 valeurs n'ont pas le même niveau de confirmation et ne sont pas
  transformées en BPA recalculés comparables ;
- ETIT 2024 doit être cité à **8,23 FCFA** (chiffres clés), la valeur brute
  d'audit 8,2 étant l'arrondi du compte de résultat du même document.

Cette revue ferme la file « extraction unique à contre-lire ». Elle ne met
pas à jour les taux de l'audit 480 et n'autorise pas encore l'intégration au
dataset : le parseur a changé depuis le journal 480, donc toute nouvelle
matrice doit venir d'un rejouage sous l'empreinte finale.

Décisions machine :

- `decisions_contre_lecture.json`
- `decisions_contre_lecture.csv`
- preuves d'audit regroupées : `dossier_preuves_audit480.json`
- extraits de pages relus : `extraits_pages_contre_lecture.txt` et
  `extraits_SDSC_2022.txt`

## Méthode

Pour chaque cellule, la revue a distingué quatre questions :

1. la valeur est-elle réellement imprimée à la page annoncée, dans la bonne
   colonne d'exercice ?
2. le périmètre, le référentiel, la composante et le caractère de base ou
   dilué sont-ils ceux retenus ?
3. le numérateur et le nombre d'actions imprimés rendent-ils le BPA
   arithmétiquement cohérent, sans substituer un recalcul à la publication ?
4. existe-t-il un second PDF ou seulement une seconde présentation dans le
   même document ?

Hors pilote, neuf PDF ont été réextraits un par un avec le parseur final et
leurs pages BPA ont été relues directement. Pour les sept cellules du
pilote, les décisions humaines fermées ont été reconfirmées et le nouveau
parseur a été rejoué sur les documents du pilote.

## ABJC — Servair Abidjan

Périmètre relu : **IFRS individuel**. Le document approuvé 2023 le dit
explicitement page 8 ; la ligne BPA est page 5 et la phrase de contrôle page
25. Le document 2025 de trois pages est explicitement **provisoire**.

| Exercice | BPA retenu | Contrôle relu |
|---:|---:|---|
| 2022 | 117 | 1 272 M / 10 912 000 = 116,57 |
| 2023 | 124 | 1 358 M / 10 912 000 = 124,45 |
| 2024 | 139 | 1 515 M / 10 912 000 = 138,84 |
| 2025 | 122 | 1 331 M / 10 912 000 = 121,98 |

La face imprimée donne donc à la fois le résultat net, le nombre total
d'actions et le BPA « de base et dilué ». Les écarts sont ceux des arrondis
en millions et à l'unité.

Réserve importante : la note capital parle de 545 600 actions de 2 500 FCFA,
alors que la face BPA et le récit utilisent 10 912 000 actions, soit
exactement vingt fois plus. Cela ressemble à une division d'actions non
reflétée dans la formulation du capital légal. Le BPA publié est bien calculé
sur 10 912 000 actions, mais le nombre d'actions légal ne doit pas être
intégré sans tracer l'opération sur titres.

## ORGT — Oragroup

Périmètre relu : **IFRS consolidé**.

| Exercice | BPA retenu | Preuve et contrôle |
|---:|---:|---|
| 2019 | 142 | Note BPA du rapport certifié : 9 806 M part du Groupe / 69 090 306 actions en circulation = 141,93 |
| 2022 | 126 | Comparatif des états consolidés provisoires 2023 ; le document d'origine 2022 ne contient pas de ligne BPA mais donne le même numérateur part du Groupe de 8 749 M |
| 2023 | -280 | États consolidés provisoires 2023 ; ligne de base suivie du dilué -281 |
| 2024 | -545 | Comparatif du document consolidé 2025 ; le document d'origine 2024 est scanné et n'a pas été lu sans OCR |
| 2025 | 264 | Document consolidé 2025 ; dilué publié séparément à 241 |

Pour 2022–2025, les condensés n'impriment pas le dénominateur. Les
dénominateurs implicites obtenus en divisant le résultat attribuable au
Groupe ou à la holding par le BPA sont stables et cohérents :

- 2022 : 69 436 508 actions implicites ;
- 2023 : 69 500 000 ;
- 2024 : 69 477 064 ;
- 2025 : 69 526 515.

Ces contrôles valident la cohérence des faces, mais ne créent pas un BPA
recalculé comparable : aucun nombre moyen pondéré n'est imprimé dans ces
condensés.

## SDCC — Sodeci

Périmètre retenu : **IFRS consolidé**.

| Exercice | BPA consolidé retenu | Contrôle |
|---:|---:|---|
| 2018 | 325 | 2 921 M / 9 000 000 = 324,56 |
| 2019 | 353 | 3 181 M / 9 000 000 = 353,44 |

Les valeurs figurent dans deux PDF distincts :

1. les comptes IFRS consolidés 2019, p. 5 ;
2. le rapport de gestion 2019, section consolidée IFRS p. 89.

Le même rapport de gestion donne page 29 le bloc individuel : 353 en 2019 et
**324** en 2018. La différence 325/324 en 2018 est donc bien une différence de
périmètre, non une erreur de lecture.

Nuance de validation : les deux PDF portent la **même vintage 2019**. Il
s'agit d'une confirmation par deux documents distincts, pas de deux vintages
indépendantes.

## Cellules déjà contre-lues dans le pilote

Les sept cellules suivantes étaient déjà fermées par les décisions humaines
du pilote. Elles ont été reconfirmées sans changement de valeur, sauf la
précision ETIT 2024 notée ci-dessous.

| Cellule | BPA retenu | Contrôle humain |
|---|---:|---|
| CIEC 2019 | 140 | 7 826 M / 56 000 000 = 139,75 |
| CIEC 2025 | 234 | 13 100 M / 56 000 000 = 233,93 |
| SNTS 2022 | 2 359 | 235 974 M attribuables / 100 000 000 = 2 359,74 |
| SNTS 2025 | 3 420 | 341 963 M attribuables / 100 000 000 = 3 419,63 |
| SDSC 2021 | 308,4 | 16 780 M part du Groupe / 54 418 250 actions moyennes pondérées = 308,35 |
| ETIT 2022 | 7,064 | Chiffres clés et compte de résultat concordants à 1,165 cent USD / 7,064 FCFA |
| ETIT 2024 | **8,23** | Chiffres clés à 8,23 ; compte de résultat arrondi à 8,2 |

Les réserves du pilote restent valables : plusieurs dénominateurs sont des
actions en circulation ou un dénominateur stable documenté dans une autre
vintage, non une note moyenne pondérée republiée pour l'exercice même. Cela
suffit à contre-lire le BPA publié, pas à le reclasser en BPA recalculé
comparable.

## SDSC 2022 — quarantaine confirmée

Le compte consolidé page 3 imprime :

- résultat net part du Groupe : **14 124 millions FCFA** ;
- BPA de base et dilué : **250,9 FCFA**.

La note 8 page 27 donne **54 418 250** actions moyennes pondérées. Le
contrôle donne :

14 124 000 000 / 54 418 250 = **259,545 FCFA**,

soit **3,3309 %** au-dessus du BPA publié, très au-delà des arrondis.

La note 8.2 aggrave l'incohérence : elle indique **16 780 millions** comme
numérateur utilisé pour 2022 **et** pour 2021. Ce numérateur donnerait
308,35 FCFA, qui est précisément le niveau du BPA 2021. La colonne 2022 de la
note semble donc recopier les intrants 2021.

Le BPA individuel de 318 FCFA est, lui, cohérent avec le résultat individuel,
mais il appartient à un autre périmètre.

Décision inchangée :

- **250,9 : publié mais non retenu** ;
- **259,545 : contrôle arithmétique seulement, jamais substitué** ;
- **318 : BPA individuel séparé, jamais substitué au consolidé** ;
- quarantaine maintenue jusqu'à une version corrigée ou une explication
  documentée.

## Défaut générique découvert et corrigé pendant la contre-lecture

La note ORGT 2019 contient la ligne d'années espacées `2 019 2 018` entre le
titre BPA et ses intrants. Le parseur créait deux candidats 2019 et 2018.
Ils étaient inéligibles dans ce document faute de mention de base, mais un
test construit à partir de ces lignes réelles a montré qu'ils devenaient
promus si le titre contenait « de base ».

Correctif `eps-evidence-v2.1.1` :

- reconnaissance des années espacées sur les lignes quasi purement
  numériques ;
- compactage des espaces avant le filtre des années d'en-tête ;
- test de régression dédié à partir des lignes ORGT.

Validation après correctif :

- suite complète : **100 tests réussis** ;
- PDF ORGT 2019 réextrait : seuls 142 et 115 subsistent ;
- documents SPHC, TTLS, ABJC, ORGT et SDCC réextraits avec la version
  finale, sans changement des valeurs contre-lues ;
- régression pilote rejouée prudemment : 72 documents complets donnent
  **18/18 valeurs** et **0 faux positif** ; le rapport annuel ETIT 2018 a de
  nouveau été validé séparément sur ses 23 pages déjà sélectionnées
  (**25/25 observations identiques**), sans prétendre à une nouvelle
  extraction complète 73/73.

Empreinte de la régression finale :
`2bc7fbb4aa252ddde4ae07bf9884e11fe6e873acadd881d96c49166e32020672`.

## Ce que cette revue ne fait pas

- Elle ne recalcule pas les taux de couverture 480.
- Elle ne remplace pas le journal 480 du 25 octobre, produit sous une
  ancienne empreinte.
- Elle ne transforme aucun contrôle arithmétique en BPA recalculé comparable
  lorsque le dénominateur n'est pas un nombre moyen pondéré explicite.
- Elle n'intègre aucune valeur au dataset publié.

## Suite recommandée

1. Rejouer l'audit 480 ou une agrégation ciblée sous `eps-evidence-v2.1.1`
   dans un nouveau répertoire, sans écraser les artefacts du 25 octobre.
2. Appliquer les présentes décisions comme couche de revue explicite, avec
   les niveaux de validation distincts et les vintages provisoires signalées.
3. Passer ensuite au backlog documentaire restant : 71 cellules illisibles,
   15 introuvables dans l'inventaire et 18 non recherchées.
4. Ne décider l'intégration au dataset qu'après cette nouvelle matrice
   comparable.

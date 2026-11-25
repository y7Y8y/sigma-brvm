# « Quoi revendre » — sans portefeuille (28 octobre 2026)

## Le reproche, accepté

La revue de sortie avait été placée dans le **portefeuille**. C'était une
erreur de conception : elle obligeait à enregistrer ses lignes avant de
recevoir une réponse, et elle ne parlait qu'aux personnes déjà investies. Or
la question « qu'est-ce qui ne tient plus » se pose **avant** d'acheter autant
qu'après.

## Ce qui a été déplacé et reconstruit

| Avant | Après |
|---|---|
| Blocs dans le portefeuille | **Décision → « Le mois »** |
| Revue limitée aux lignes détenues | Revue sur **les 48 sociétés**, aucun portefeuille requis |
| 4 signaux sur vos positions | 6 signaux mesurés sur l'état publié de chaque société |

Les six signaux, avec leur poids :

| Signal | Ce qu'il observe | Poids |
|---|---|---:|
| Cours au haut de **sa** fourchette | le prix a déjà payé quelque chose | 2 |
| PER au haut de **son** propre passé | plus cher qu'à son habitude | 2 |
| Dividende rattaché à un exercice ancien | le rendement décrit un versement passé | 3 |
| Distribution > 100 % du bénéfice | payée par autre chose que le résultat | 3 |
| Long terme « fragile » | résultats ou structure en dégradation | 3 |
| Décrochage vs marché sur 60 séances | elle baisse quand le marché monte | 2 |
| Liquidité < 5 M FCFA par séance | sortir prendra du temps et coûtera | 1 |

Deux listes : **signaux concordants** (poids ≥ 6, à relire en premier) et
**à surveiller** (poids 3 à 5). 32 sociétés portent au moins un signal.

## Deux erreurs trouvées en construisant cette revue

### 1 · Un ton long terme déduit d'un seul signe

ONTBF, SGBC et CIEC sortaient « en dégradation » sur la seule base d'une
baisse de résultat, y compris quand la trésorerie tenait. Le ton dépend
désormais de trois éléments : le sens de la croissance, la **qualité** du
bénéfice (flux d'exploitation ÷ résultat ≥ 0,8) et le niveau de la baisse.
« Solide » exige les deux premiers ; une croissance positive avec une
trésorerie en retrait donne « à vérifier », pas « solide ».

### 2 · Des sauts invraisemblables pris pour des performances

La série extraite contient des ruptures qui ne sont pas des trajectoires :

| Société | Saut | Lecture refusée |
|---|---|---|
| SGBC | 2021 : 10 116 M → 2022 : 97 230 M (**×9,6**) | « +900,7 %, soit +77,9 % par an » |
| FTSC | 2022 : 153 M → 2023 : 3 076 M (**×20**) | « +203,6 % par an » |
| BNBC | 2022 → 2025 | trois ruptures successives |
| PALC | 2020 → 2023 (**×5,5**) | « +340 %, +34,5 % par an » |

`ruptures()` détecte tout rapport supérieur à 3 ou inférieur à 1/3 entre deux
exercices consécutifs. La fenêtre de comparaison **commence après la dernière
rupture** : SGBC se lit maintenant 2022 → 2025 (**+4,1 %**, +1,4 % par an) au
lieu de +900 % par an, et le refus est écrit dans le détail.

Quand aucune comparaison valable ne subsiste (BNBC), le ton passe à
« à vérifier » : « neutre » se lirait comme un feu vert.

## Ce que la revue ne fait toujours pas

- **Elle ne dit pas « vendez ».** La liste nomme ce qui a changé ; trois
  raisons légitimes de garder (dividende couvert, baisse de marché, horizon
  qui couvre le cycle) ne sont pas vérifiables à votre place.
- **Elle ne connaît pas votre prix de revient.** Sans portefeuille, elle ne
  peut pas dire si vous êtes en plus-value ou en moins-value : c'est une
  information que seul votre relevé SGI détient.
- **Elle ne connaît pas vos frais de sortie.** Une vente coûte, et ce coût
  peut dépasser le gain d'une sortie sur un signal faible.

## Vérifications

`pytest` **264 tests** · jsdom 9 vues, **0 erreur JavaScript** · Décision
affiche « Cinq sociétés à examiner » + « Les sociétés qu'il ne faut plus garder
par habitude » · portefeuille vidé de ces blocs · `sw.js` v7.

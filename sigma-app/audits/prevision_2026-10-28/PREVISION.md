# « Top 5 du mois, quoi vendre, et prévoir les chutes » (28 octobre 2026)

## Trois questions, trois réponses de nature différente

1. **Top 5 à acheter chaque mois dans mon budget** → possible, et construit
   aujourd'hui. Mais c'est un ordre d'**étude**, pas un ordre d'achat.
2. **Quoi revendre ?** → possible seulement sur *ce que vous détenez*, et
   jamais sous forme de consigne. Construit aujourd'hui comme une revue.
3. **Prévoir une chute la veille** (le cas Nvidia) → **impossible**, et je
   préfère le démontrer que le promettre.

## 1 · Le top 5, contraint par le budget

Nouveau bloc dans le portefeuille : `topDuMois(budget)`.

- part du classement **Radar** (échangeabilité 35, valorisation 35, rendement 30) ;
- **filtré par le prix** : à 50 000 FCFA de versement, une action SGBC à
  38 900 FCFA passe, une action à 60 000 ne passe pas ;
- **plafond de deux valeurs par secteur** dans les cinq ;
- chaque ligne dit le nombre d'actions possibles, la part du versement, le
  percentile de PER **de la société contre son propre passé**, le rendement et
  le nombre de preuves de revenu.

Sans budget saisi, le bloc ne fabrique pas une liste : il demande le montant.
Avec un budget trop faible pour tout le classement, il écrit « aucune société
ne tient dans ce budget » et dit combien sont écartées par le prix seul.

## 2 · Quoi revendre : la revue des lignes détenues

`revuePositions(kind)` croise vos positions réelles ou simulées avec le verdict
de chaque société. Quatre signaux calculables :

| Signal | Ce qu'il dit |
|---|---|
| Cours dans le haut de **sa** fourchette | le prix a déjà intégré quelque chose |
| PER cher **contre son propre passé** | le marché paie plus qu'à l'habitude |
| Dividende non renouvelé | le rendement affiché décrit un versement passé |
| Distribution > bénéfice | le dividende a été payé par autre chose que le résultat |

**Aucun de ces signaux ne dit « vendez ».** La revue nomme ce qui a changé
depuis l'achat, puis rappelle trois raisons légitimes de garder (dividende
toujours couvert, baisse de marché et non d'entreprise, horizon qui couvre le
cycle) et le coût oublié d'une vente : les frais de la SGI, que SIGMA ne connaît
pas.

## 3 · Prévoir une chute : la démonstration, pas la promesse

### Ce que la BRVM rend structurellement impossible

Sur **12 332 variations de séance** archivées, **aucune** ne dépasse **7,5 %**.
Les 67 séances qui touchent exactement la borne sont closes sur plafond ou
plancher. Conséquence directe : la perte d'une séance est **bornée**. Sur une
valeur qui échange peu, un plafond atteint signifie surtout que personne n'a
acheté à ce prix.

### Ce que les données disent des sauts

**1 316 sauts de plus de 5 %** sur l'archive, dont **39,4 % sur des séances à
moins de 10 M FCFA échangés** — et une valeur médiane de 15,0 M FCFA. Un saut
sur une séance à 200 000 FCFA n'est pas un événement : c'est un prix de passage.
C'est pourquoi `reactions()` ne compte que les sauts **payés** (≥ 5 M FCFA).

Mesure ensuite publiée par société : après un saut de plus de 5 % payé, le
cours revient-il dans l'autre sens deux séances plus tard ?

| Société | Sauts payés | Retour 2 séances après |
|---|---:|---:|
| SGBC | 5 | 80,0 % |
| SNTS | 6 | 83,3 % |
| UNLC | 9 | 55,6 % |
| STAC | 53 | 47,2 % |

Lecture honnête : les valeurs liquides de l'échantillon reviennent souvent,
les valeurs à faible flottant beaucoup moins. Ce sont **48 mesures
rétrospectives**, pas un modèle. Et sur 5 à 6 observations, c'est une
description, pas une statistique — c'est écrit dans la fiche.

### Ce que les publications permettent réellement

`impacts_publications()` relie chaque document officiel daté aux trois séances
suivantes et compte les mouvements d'au moins 3 % réellement payés :

| Société | Publications | Suivies d'un mouvement | Le plus fort |
|---|---:|---:|---:|
| SGBC | 5 | 40,0 % | 6,52 % |
| ONTBF | 6 | 16,7 % | 3,60 % |
| CIEC | 3 | 33,3 % | 4,32 % |
| SIVC | 8 | 87,5 % | 7,32 % |

30 sociétés ont au moins une publication datée dans la fenêtre, 15 en ont six
ou plus. La médiane de réaction est de 60 %.

**Ce que cela ne permet pas** : connaître le contenu d'un communiqué avant sa
publication. Le cas Nvidia décrit un saut d'information non anticipable *avant*
la nouvelle ; ce qui était anticipable, c'est le **risque** de la détenir — et
c'est exactement ce que ce bloc mesure.

## La réponse à « est-ce qu'il faut attendre le 1er du mois ? »

Non. Rien dans la méthode n'impose un calendrier mensuel :

- **l'achat** dépend d'un cours, d'un budget et d'une valorisation. Une baisse
  de 10 % change le prix d'entrée sans rien changer à l'entreprise : c'est le
  moment où la lecture par percentile devient utile.
- **la vente** dépend d'un signal sur la société, pas d'une date.
- **ce qui impose un rythme**, c'est votre versement — pas le marché.

Le « mois » de SIGMA est un rythme d'épargne, pas une règle de marché.

## Vérifications

`pytest` **262 tests** · jsdom 9 vues, **0 erreur JavaScript** · fiche SGBC :
amplitude 7,5 %, retour 80 %, publications 40 % · `node --check` OK · `sw.js` v6.

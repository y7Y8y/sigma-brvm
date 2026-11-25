# Débutant, expérimenté, et « de beaux dividendes » (28 octobre 2026)

## La question posée

« Est-ce que SIGMA peut aider un investisseur débutant et surtout expérimenté
à prendre de bonnes décisions et à avoir de beaux dividendes ? »

Réponse honnête : **oui pour la décision, non pour la promesse de dividende.**
Ce document dit exactement où se situe la frontière, chiffres en main.

## Ce qui manquait, et qui manquait aux deux profils

L'application savait dire si un cours est haut dans sa propre fourchette, si un
PER est cher par rapport à son propre passé, si l'entreprise gagne de l'argent.
Elle ne savait pas répondre à la seule question que pose un investisseur qui
veut des dividendes : **ce rendement est-il un revenu, ou un versement passé ?**

Un rendement de 95,92 % (FTSC) et un rendement de 5,89 % (SGBC) étaient
affichés avec le même badge. C'est ce qui fait perdre de l'argent.

## Ce qui a été construit

### 1 · Le revenu, en trois preuves séparées (`revenu()`)

Un dividende ne devient un revenu que si trois choses tiennent ensemble :

| Preuve | Question | Ce qui la prouve |
|---|---|---|
| Régularité | Le dividende est-il renouvelé ? | 3 exercices consécutifs réellement payés |
| Financement | Est-il payé par le bénéfice ? | dividendes versés ÷ résultat net du même exercice ≤ 100 % |
| Couverture | Est-il payé par l'exploitation ? | flux de trésorerie opérationnel ÷ dividendes versés ≥ 1 |

**Couverture réelle** : 43/48 ont un rendement publié ; 10 ont un dossier
documentaire complet ; **3 seulement réunissent les trois preuves** (CFAC,
CIEC, PALC). Aucune note de qualité n'est produite : un décompte et le détail
de ce qui manque.

### 2 · Une erreur trouvée dans mon propre calcul, et corrigée

Le rendement net publié au BOC et le tableau de paiement BRVM ne parlent pas
toujours du même montant : **17 sociétés sur 48 publient un montant brut, 17 un
montant net, 14 sont dans un autre cas**. Un rendement calculé en croisant les
deux surestime le revenu réel de **13,6 %** dans les cas bruts (SGBC : 6,68 %
affiché contre 5,89 % net).

Correction : **le rendement vient du seul BOC**, le tableau de paiement ne sert
qu'à établir la régularité et la chronologie. Aucun montant ne traverse les
deux sources. Un test le vérifie société par société.

### 3 · Deux décalages opposés, désormais distingués

- **Dividende en retard sur les comptes** (SIVC : dernier versement 2016 pour
  des comptes à jour) → *« ce taux décrit un versement passé »*.
- **Comptes en retard sur le dividende** (CFAC : dividende 2025 publié,
  derniers états extraits 2024) → le taux de distribution n'est calculable que
  jusqu'à 2024, et c'est écrit.

Confondre les deux faisait passer un trou de collecte pour une absence de
dividende.

### 4 · Les cinq points de passage, identiques pour tous

Ni « débutant » ni « expert » dans l'interface : un chemin d'ouverture de
compte, avec ce que SIGMA sait et ce qu'il ne sait pas.

1. **Compte-titres chez une SGI agréée** — la BRVM publie les SGI, pas leurs
   tarifs ; aucun ordre n'existe sans compte.
2. **Ordres à cours limité** — sur les 20 dernières séances, 3 valeurs sur 48
   n'ont pas changé de main et 11 ont échangé moins de 5 M FCFA par séance en
   médiane. Un ordre au marché s'y paie au prix que le carnet veut bien donner.
3. **Frais** — SIGMA ne fabrique pas de grille ; il calcule sur la vôtre et
   écrit « frais non estimés » sinon.
4. **Dividende** — le rendement du BOC est net des montants publiés, mais hors
   frais SGI et hors délai de crédit.
5. **Fiscalité** — **non publiée par SIGMA** : aucune source officielle
   unifiée pour les huit pays de l'UEMOA n'a été collectée. Ce point est
   affiché comme un trou assumé, pas comblé par un taux plausible.

### 5 · Le registre des manques passe de 28 à 66 lignes

38 lignes `revenu` s'ajoutent : pour chaque société, les preuves manquantes
sont nommées une par une, avec la source exacte qui les débloquerait (tableau
de financement : « dividendes versés » et flux d'exploitation du même exercice).

## Réponse directe, profil par profil

**Un investisseur expérimenté** obtient de SIGMA ce qu'un tableur ne donne pas
sans travail : la position d'un cours et d'un PER dans *leur propre* histoire,
la décomposition exacte d'une hausse (multiple ou bénéfice), la distance à son
plus haut annuel, et désormais la qualité du dividende avec ses trois preuves.
Ce qu'il n'obtient pas : du temps réel (données de fin de séance), une
recommandation, ni la fiscalité.

**Un investisseur qui commence** obtient les cinq points de passage et une
réponse explicite quand la donnée manque. Ce qu'il n'obtient pas : une
simplification qui cacherait le risque. Traduire « 3/48 seulement réunissent
les trois preuves » en note verte serait exactement le mensonge que SIGMA
refuse.

**« De beaux dividendes »** : SIGMA ne peut pas le promettre, et aucun outil ne
le peut. Il peut dire, pour 3 sociétés, que le dividende est renouvelé, financé
et couvert ; pour 38, ce qui manque pour l'affirmer ; et pour 7, qu'aucune
distribution ne peut être considérée comme un revenu. C'est vérifiable ; une
promesse de rendement ne l'est pas.

## Vérifications

`pytest` **256 tests** · jsdom 9 vues, **0 erreur JavaScript** · fiche SGBC :
3 lignes de preuves, 3/3 ; fiche FTSC : avertissement « versement passé » et
« rendement hors norme » ; `node --check` OK · `sw.js` v4.

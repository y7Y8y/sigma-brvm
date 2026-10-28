# Charte typographique SIGMA — 28 octobre 2026

## Le défaut mesuré

Reproche : « tout à la même taille dans chaque onglet ». Vérification dans la
feuille de style, avant correction :

- **21 tailles de police distinctes**, dont **neuf entre 10 et 15 px** :
  10 / 10,5 / 11 / 11,5 / 12 / 12,5 / 13 / 14 / 15 ;
- **25 tailles écrites en dur** dans le HTML généré par `app.js`
  (11, 12, 13, 16, 19, 22, 27 px), donc hors échelle ;
- **h1 à 20–24 px et h2 à 17,5–21 px** : 14 % d'écart, invisible. Le titre de
  page et le titre de carte se ressemblaient ;
- `body { font-size: 15px }` dans la requête mobile : sur téléphone, tout le
  texte grossissait et écrasait la hiérarchie ;
- les nombres (`.metric-value`) héritaient du corps de texte : un chiffre n'était
  pas plus grand que la phrase qui l'entourait.

Une échelle n'existe que si chaque marche se voit. Neuf tailles en 5 px, ce
n'est pas une échelle : c'est du bruit.

## La règle

**Sept marches, pas une de plus.** La taille crée la hiérarchie, le poids la
confirme, la couleur la nuance. Un rôle par marche.

| Jeton | Taille | Rôle | Poids | Détail |
|---|---|---|---:|---|
| `--fs-micro` | 10,5 px | étiquettes, en-têtes de tableau, axes | 640 | CAPITALES + interlettrage `.12em` |
| `--fs-small` | 12 px | texte secondaire, sources, pastilles, notes | 450–620 | couleur `--text-secondary` |
| `--fs-body` | 14 px | texte courant — **la référence** | 400 | — |
| `--fs-subtitle` | 17 px | sous-titre, **chiffre dans une carte** | 640–680 | chiffres tabulaires |
| `--fs-title` | 18–21 px | titre de section ou de carte (h2) | 660 | interlettrage `-.015em` |
| `--fs-hero` | 23–27 px | titre de page (h1) | 700 | interlettrage `-.025em` |
| `--fs-figure` | 25–31 px | chiffre clé, cours, montant | 700 | interlettrage `-.025em` |

Rapports entre marches voisines : **1,14 · 1,17 · 1,21 · 1,24 · 1,29 · 1,15**.
Amplitude totale : le corps de texte est **1,33×** la plus petite marche et le
titre de page **1,93×** le corps de texte.

Un huitième jeton existe, séparé : `--icon-size` (16 px) pour les glyphes
d'icônes. Ce n'est pas du texte, il ne doit pas suivre l'échelle de lecture.

## Rôles nommés

Les 25 tailles en dur sont remplacées par des classes qui portent le sens :

| Classe | Marche | Usage |
|---|---|---|
| `.mode-glyph` | title | pastille ● / ◆ des bandeaux réel-simulation |
| `.metric-value.is-compact` | subtitle | valeur d'une carte quand le texte est long |
| `.text-body` | body | phrase courte qui doit sortir du gris |
| `.summary-strong` | subtitle | résumé de pliage |
| `.summary-title` | title | titre de pliage |
| `.figure-inline` | subtitle | score, note, chiffre en ligne |
| `.score-total-suffix` | small | « /100 » |

## Sélecteur de portes

Reproche lié : les trois pastilles de Décision s'arrêtaient à 388 px sur une
ligne de 538 px — **182 px vides, 34 % de la ligne**. Chaque pastille prenait la
largeur de son texte.

Remplacé par un groupe en grille : `repeat(3, minmax(0, 1fr))`, largeur 100 %,
plafond 720 px, libellés centrés, hauteur 38 px. Les trois portes occupent
désormais la ligne, et tombent sur la même marge que le titre et la phrase
d'introduction.

## Garde-fous

`tests/test_charte.py` — 15 contrôles :

- exactement sept marches `--fs-*` dans `:root` (+ `--icon-size` séparé) ;
- bornes conformes au tableau ci-dessus ;
- **aucun rapport inférieur à 1,12** entre deux marches voisines, aucun
  supérieur à 1,35 ;
- amplitude : corps ≥ 1,3 × micro, h1 ≥ 1,8 × corps, chiffre ≥ 2 × corps ;
- **zéro `font-size` en dur** hors de `:root`, et **zéro dans `app.js`** ;
- h1/h2/h3 sur trois marches différentes, écart h1/h2 ≥ 1,2 ;
- étiquettes toujours en micro capitales ;
- pas de `body { font-size }` dans une requête média ;
- onglets en grille à trois colonnes égales, plafonnés à 720 px.

## Vérifications

`pytest` : **227 tests passés**. Rendu jsdom : 9 vues, **0 erreur JavaScript**,
ordre des cartes d'accueil inchangé.

Limite honnête : jsdom ne résout pas `var()` dans `getComputedStyle`. Ces
contrôles portent sur la source CSS, pas sur des pixels mesurés dans un vrai
navigateur. Le rendu final se juge à l'œil sur l'appareil.

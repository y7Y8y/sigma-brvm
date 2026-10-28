# Densité de l'interface — mesure du 28 octobre 2026

Constat à l'origine : « dans tous les onglets y'a trop d'infos, peut-être utile,
mais j'ai pas envie de voir tout ça ». Deux défauts distincts, mesurés séparément.

## 1. La page ne prenait pas toute la largeur

`.main` portait `max-width: 1460px; margin: 0 auto`. Sur un écran de 1 920 px :
~114 px vides de chaque côté ; sur 2 560 px : ~434 px. Les tableaux de Décision,
qui comptent six à huit colonnes, étaient les premiers tassés au centre.
Correction : `max-width: none`. La prose garde une mesure de lecture bornée
(`.lead` 68 ch, `.source-line` 92 ch) — pleine largeur pour les chiffres,
longueur lisible pour le texte.

## 2. Mots réellement visibles, avant / après

Méthode : rendu DOM réel dans jsdom, puis comptage des mots **hors `<details>`
fermés**. Ce n'est donc pas la taille du HTML : c'est ce que l'œil reçoit sans
cliquer. Comparaison entre `e56c032` et le présent état.

| Vue | Avant | Après | Variation |
|---|---:|---:|---:|
| Accueil | 1 795 | 406 | −77 % |
| Paramètres | 2 980 | 538 | −82 % |
| Décision (toutes portes) | 4 015 | 1 156 | −71 % |
| Fiche société | 1 347 | 745 | −45 % |
| Actualités | 2 735 | 1 619 | −41 % |
| Alertes | 686 | 609 | −11 % |
| Entreprises | 1 498 | 1 369 | −9 % |
| Portefeuille | 940 | 889 | −5 % |
| Marché | 1 189 | 1 189 | 0 % |
| **Total** | **17 185** | **10 512** | **−39 %** |

Détail de Décision, porte par porte :

| Porte | Avant | Après |
|---|---:|---:|
| Ce mois | 627 | 502 |
| À examiner | 1 384 (Radar) + 241 (Baisses) | 595 |
| Références | 852 + 911 + 0 | 59 |
| Documents officiels | 2 612 | 0 (plié) |

Marché et Entreprises ne bougent pas volontairement : ce sont des tableaux et
des fiches de données, pas de la prose. Leur longueur est celle du marché
(48 sociétés), pas celle d'une explication.

## 3. Ce qui a été retiré, ce qui a été plié

**Retiré** (redite ou pédagogie) : les huit lignes de méthode de l'accueil, les
encadrés « En clair » qui précédaient chaque formulaire, l'avis de couverture de
407 mots de l'accueil (remplacé par une ligne chiffrée), les chapeaux d'articles
répétés, les infobulles de champ de deux phrases.

**Pliés, jamais supprimés** : les plafonds AMF-UMOA (2 246 mots), le manifeste
de collecte, la bibliothèque de documents (2 518 mots), la série annuelle et les
piliers fondamentaux, les tables PER/rendement et liquidité des 48 sociétés, le
contexte macro, la transparence du tri du Radar, les éligibles suivantes, les
dividendes à venir, les publications, le calendrier des échéances.

**Navigation Décision** : six onglets → trois portes (Ce mois · À examiner ·
Références). Les six anciennes adresses restent valides et rabattues sur la
bonne porte : aucun lien existant ne casse.

## 4. Garde-fous

`tests/test_densite.py` (11 tests) verrouille : page pleine largeur, trois
portes exactement, anciennes portes rabattues, composant de pliage présent et
utilisé, blocs lourds effectivement pliés, « En clair » replié, corps rendu même
fermé (les formulaires gardent leurs écouteurs), liste Radar limitée à trois
cartes visibles.

Vérifications : `pytest` **207 tests passés**, rendu jsdom **9 vues, 0 erreur
JavaScript**, ordre des cartes d'accueil stable, 284 lignes d'alertes générées.

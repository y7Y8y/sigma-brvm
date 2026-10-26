# SIGMA, expliqué simplement

*Page pour le propriétaire du projet. Aucun terme technique non expliqué.*

---

## Ce que fait SIGMA

SIGMA lit les documents officiels de la Bourse de la BRVM, en extrait les chiffres, et les présente **sans jamais les inventer**. Son travail n'est pas de prédire la bourse. Son travail est de vous empêcher de décider sur une information fausse.

C'est pour cela que l'application affiche parfois « non calculable » ou « non publié dans les sources vérifiées ». Ce n'est pas un bug, ce n'est pas un manque de travail : c'est le résultat d'une recherche qui n'a rien trouvé de prouvable. Un chiffre absent honnêtement vaut mieux qu'un chiffre plausible inventé — parce qu'un chiffre inventé vous ferait perdre de l'argent sans vous prévenir.

## Pourquoi votre projet est plus solide que la plupart des outils

La plupart des applications de bourse remplissent les trous. Elles mettent une estimation, une moyenne, une « tendance ». Ça a l'air complet. C'est faux.

Votre projet fait l'inverse : il documente chaque trou, et il refuse de le combler. C'est plus lent, ça produit des tableaux moins jolis, et c'est la seule méthode qui tient sur dix ans. C'est aussi ce qui a permis de découvrir des erreurs réelles dans les documents officiels — des données mélangées entre deux exercices, des montants imprimés sous une mauvaise échelle, un résultat attaché à la mauvaise année.

## Ce que j'ai décidé aujourd'hui

Trois décisions, toutes réversibles, aucune ne touche votre argent ni votre application :

1. **Une valeur qui concerne une année où l'entreprise n'était pas encore en bourse ne compte plus dans les statistiques.** Elle reste visible, mais à part. Sinon, on gonfle les chiffres sans le dire.
2. **Tous les pourcentages seront désormais calculés sur une seule base claire** — les 442 cas qui ont un sens — au lieu de mélanger deux bases selon le document.
3. **Les corrections faites à la main sont maintenant dans un fichier que la machine relit.** Avant, elles vivaient dans une note ; un recalcul automatique les oubliait et affichait des chiffres différents de la note. C'était le vrai danger : deux vérités qui coexistent.

Résultat concret : les chiffres du projet se calculent maintenant tout seuls, et si l'un d'eux ne tombe pas juste, le programme **s'arrête au lieu d'écrire un rapport faux**.

## Ce que vous n'aurez jamais à décider

- Où se trouve une valeur dans un PDF : c'est le travail du parseur, et il est testé 114 fois.
- Quelle année correspond à quel document : c'est prouvé par les en-têtes, pas deviné.
- Si un chiffre est « probablement » bon : la règle est qu'il n'entre pas s'il n'est pas prouvé.

## Les trois seules choses qui vous appartiennent

1. **L'argent réel** : combien vous mettez, et quand. Aucune décision technique ne touche à ça.
2. **Le rythme** : versement mensuel, réserve d'opportunité. C'est votre choix de vie, pas un calcul.
3. **Le moment d'ouvrir la porte** : les données extraites n'entreront dans l'application que lorsque vous le déciderez, cellule par cellule. Rien ne s'intègre en douce.

## Où en est réellement le projet, sans enjolivement

| Ce qui marche | Ce qui manque encore |
|---|---|
| 48 sociétés suivies, 262 séances de bourse archivées | Le bénéfice par action n'est prouvé que pour une petite partie des sociétés |
| 1 504 documents officiels indexés | 72 documents sont illisibles (scans de mauvaise qualité) |
| 348 lignes de dividendes sur 2015–2025 | Le nombre d'actions n'est vérifié que pour 4 sociétés sur 48 |
| Les cours, les frais, les calendriers : fiables | La valorisation (ce que vaut une action) n'est pas encore calculable pour la majorité |

Traduction : SIGMA sait aujourd'hui vous **décrire** le marché avec fiabilité. Il ne sait pas encore vous dire si une action est **bon marché**. Cette partie dépend du travail sur les bénéfices et le nombre d'actions, et c'est là que l'effort doit aller.

## Ce que je vous demande

Rien, pour l'instant. J'ai tranché, c'est écrit, c'est testé. Quand une décision aura un effet sur votre argent ou sur la façon dont vous utilisez l'application, elle remontera vers vous en une phrase claire, avec les deux options et ma recommandation. Le reste est mon travail.

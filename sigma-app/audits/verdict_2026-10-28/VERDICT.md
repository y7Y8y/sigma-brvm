# Verdict — trois horizons, trois règles (28 octobre 2026)

## Le reproche, reformulé

« L'app est remplie d'infos mais sans réel but précis : conseiller l'achat
d'actions à moyen, court et long terme. »

Le diagnostic est exact, et il porte sur la **structure**, pas sur le volume.
L'application montrait des résultats par onglet thématique — valorisation,
liquidité, contexte, documents — sans jamais dire : *pour cette société, voilà
ce qui est cher ou bon marché à trois semaines, à un an, à cinq ans, et voilà
la règle appliquée.* L'utilisateur devait faire la synthèse lui-même.

## Ce qui a été construit

`ingestion/verdict.py` produit un verdict par société, sur trois horizons, et
publie `web/data/verdicts.json` (48 sociétés). L'application l'affiche **en
premier** : carte d'ouverture de la fiche société, et première carte de
l'accueil pour la société à examiner.

### Court terme — la séance
**Règle** : percentile du dernier cours dans ses 60 dernières clôtures publiées.
Aucun seuil de marché : la fourchette est celle de la société elle-même.
Sortie : « cours dans le haut de sa fourchette (98ᵉ centile) », écart au haut,
variation sur 20 séances.

### Moyen terme — 6 à 18 mois
**Règle** : PER publié au BOC, comparé à **sa propre distribution** sur
l'archive (262 séances), avec quartiles et percentile actuel. C'est la
correction directe du reproche « tes seuils, c'est de la moyenne, ce que tout
le monde fera » : « PER < 15 » n'apparaît nulle part.

S'y ajoute une **décomposition exacte** du mouvement :

    cours = bénéfice implicite par action × PER

Elle sépare ce que l'entreprise a produit de ce que le marché a payé :

| Société | Cours | Bénéfice implicite | PER | Qui a porté le mouvement |
|---|---:|---:|---:|---|
| Ontbf | +34,1 % | −29,5 % | +90,1 % | **le multiple**, pas l'entreprise |
| SNTS | +61,1 % | +5,0 % | +53,4 % | le multiple, bénéfice stable |
| SGBC | +44,4 % | +0,1 % | +44,3 % | le multiple seul |
| ORAC | +37,2 % | +6,1 % | +29,4 % | le multiple |

C'est la réponse opérationnelle à « est-ce que j'aurais anticipé pour vendre si
je trouvais surévalué » : une hausse portée par le multiple est une hausse que
les résultats n'ont pas validée.

### Long terme — 3 ans et plus
**Règle** : états financiers officiels seuls, prix ignoré. Résultat net et son
rythme, rentabilité des fonds propres, dette nette sur fonds propres, flux
d'exploitation rapporté au résultat, dividende versé.

Exemple, SNTS : résultat net 413 588 M FCFA en 2025 contre 278 912 M en 2022
(+14,0 % par an), fonds propres 29,6 % de rentabilité, trésorerie nette
positive (−133 419 M de dette nette, soit −10 % des fonds propres), flux
d'exploitation à 165 % du résultat.

## Couverture réelle, mesurée

| Capacité | Sociétés servies |
|---|---:|
| Court terme calculé | **47 / 48** |
| Moyen terme calculé | **39 / 48** |
| Long terme calculé | **40 / 48** |
| **Trois horizons complets** | **34 / 48** |
| Capitalisation calculée | 3 / 48 |

Le dernier chiffre est le verrou déjà connu : le nombre d'actions n'est prouvé
que pour trois sociétés. Le module **refuse de le déduire** d'un cours ou d'un
BPA.

## Trois pièges de données trouvés en construisant ce module

1. **ONTBF 2021 → 2025 comparait deux périmètres.** L'écart de six exercices a
   produit « −50,9 % de résultat net » et « 0 M de fonds propres », deux
   affirmations trompeuses. Corrigé : au-delà de cinq exercices d'écart, la
   comparaison directe est refusée et le ton passe à « périmètre à vérifier ».
2. **Fonds propres absents affichés comme zéro.** `fp_d if fp_d else 0`
   imprimait « 0 M FCFA ». Corrigé : absence déclarée, jamais substituée.
3. **Signe des dividendes versés incohérent.** PALC porte `−7 931 M FCFA` sous
   le libellé « dividendes versés », positif ailleurs. Le module affiche la
   valeur absolue en signalant la valeur brute et la convention non unifiée.

## Frontière « pas conseil »

Aucune des sorties ne contient une consigne. Les libellés sont des
observations vérifiables : « Prix haut pour elle », « Moins cher qu'à son
habitude », « Entreprise qui gagne », « Série insuffisante ». Chaque ligne
publie **sa règle** et **ce qui l'invaliderait**.

`tests/test_verdict.py` (16 tests) refuse les formules interdites (« achetez »,
« nous recommandons », « objectif de cours », « signal d'achat », « il faut
vendre », « opportunité d'achat ») et vérifie que la décomposition reconstitue
exactement le cours, que la distribution du PER est bien celle de la société,
et qu'aucune absence n'est remplacée par un zéro.

## Vérifications

`pytest` : **243 tests passés**. Rendu jsdom : verdict à 3 lignes sur l'accueil
et sur la fiche, **0 erreur JavaScript**, 9 vues intactes. Le fichier publié est
comparé au module à chaque exécution des tests : s'il diverge, la suite échoue
et demande de relancer `ingestion/verdict.py --out`.

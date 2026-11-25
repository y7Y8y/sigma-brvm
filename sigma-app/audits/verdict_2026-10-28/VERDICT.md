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

## Couverture réelle, mesurée — et chaque trou nommé

Le 28/10, la réponse « 34 sociétés sur 48 » a été refusée : *« je ne veux rien
de partiel »*. La réponse n'est pas de promettre 48 partout, c'est de **séparer
deux qualités de réponse** et de nommer chaque manque.

Deux seuils par horizon, publiés dans `verdicts.json` :

- **plein** — la règle tourne sur assez d'observations pour être un centile :
  120 séances de PER, 3 exercices comptables.
- **limité** — la règle tourne sur moins, la réponse est **livrée avec sa
  réserve** : 30 séances de PER, 2 exercices. L'écran écrit alors « le rang est
  indicatif, pas un centile établi », ou « une trajectoire sur deux points est
  un début, pas une tendance ».

Sous le seuil limité, le module refuse. Il ne devine pas.

| Capacité | Calculée | Dont pleine |
|---|---:|---:|
| Court terme | **47 / 48** | 47 |
| Moyen terme | **42 / 48** | 39 |
| Long terme | **44 / 48** | 40 |
| Capitalisation | **3 vérifiées + 35 déduites** | 3 |
| Prix face à son cycle (120 séances) | **47 / 48** | 47 |
| **Trois horizons lisibles** | **40 / 48** | — |

### La capitalisation déduite, et pourquoi elle est permise

Le verrou était le nombre d'actions. Il existe une identité qui le contourne
sans le violer :

    capitalisation = PER publié au BOC × résultat net de l'exercice de référence

Contrôle sur les deux seuls cas où les deux chemins existent :

| Société | Actions × cours | PER × résultat | Résultat publié | Écart |
|---|---:|---:|---:|---:|
| SGBC | 1 213,33 Md | 101 365 M | 101 228 M | **0,14 %** |
| CIEC | 280,00 Md | 13 127 M | 13 100 M | **0,20 %** |

Le statut publié est `implicite`, la limite est écrite à côté du chiffre
(« déduction, pas un nombre d'actions vérifié »), et **aucun champ
`actions`** n'est produit par cette voie — le test le vérifie. Le seul chemin
vers 48/48 *vérifiées* reste le registre du nombre d'actions au BOC.

### Le registre : 28 manques, chacun avec sa sortie

`manques()` ne rédige rien à la main : il **dérive** la liste des verdicts. Une
ligne dit la société, l'horizon, `absent` ou `limite`, la raison, la source
attendue et ce qui débloquerait. Publié dans `verdicts.json`, affiché dans la
vue **Ce qui manque** (5 jauges + liste par horizon).

| Horizon | Manques | Irréductibles aujourd'hui |
|---|---:|---|
| Capitalisation | 10 | NSBC (0 document indexé), BBGC (2 documents sans états financiers) |
| Moyen terme | 9 | STAC, SICC, UNXC (**aucun PER publié** au BOC), UNLC (1 seul) |
| Long terme | 8 | BBGC et NSBC (0 exercice), NEIC/NTLC/TTLS/UNXC (2), SICC (4 exercices sans grandeur exploitable) |
| Court terme | 1 | BBGC — **19 séances** de cotation depuis le 24/09/2026 |

Ces trous-là ne se comblent pas par du calcul : ils demandent une publication
qui n'existe pas. Les autres se comblent en ajoutant les documents au corpus.
La différence entre les deux est écrite dans la colonne `deblocage`.

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

`tests/test_verdict.py` (21 tests sur le verdict) refuse les formules interdites (« achetez »,
« nous recommandons », « objectif de cours », « signal d'achat », « il faut
vendre », « opportunité d'achat ») et vérifie que la décomposition reconstitue
exactement le cours, que la distribution du PER est bien celle de la société,
et qu'aucune absence n'est remplacée par un zéro.

## Vérifications

`pytest` : **248 tests passés**. Rendu jsdom : verdict à 3 lignes sur l'accueil
et sur la fiche, **0 erreur JavaScript**, 9 vues intactes, dont la vue « Ce qui manque » (5 jauges, 28 lignes, 0 erreur). Le fichier publié est
comparé au module à chaque exécution des tests : s'il diverge, la suite échoue
et demande de relancer `ingestion/verdict.py --out`.

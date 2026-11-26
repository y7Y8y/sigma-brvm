# Trouver un accès à brvm.org (28 octobre 2026)

## Le constat

Ce bac à sable a une liste blanche réseau : GitHub, npm, PyPI. `brvm.org` est
injoignable — DNS résolu (164.132.169.7) mais connexion coupée (code 000),
`http` renvoie une réponse vide, `brvm.org` sans `www` ne résout pas. Contourner
ce filtre (proxy ouvert, miroir) serait une mauvaise idée : ce n'est pas mon
réseau, et une donnée collectée par un détour non traçable n'aurait pas sa
place dans un outil qui exige une source par chiffre.

## La solution trouvée — et un défaut de plusieurs semaines

Le dépôt contenait déjà un collecteur complet (`ingestion/collect.py`,
8 000 lignes : BOC, PDF, OCR, contrôles arithmétiques) et un workflow GitHub
Actions censé le lancer chaque soir à 18:20 UTC.

**Il n'avait jamais tourné.** Cause : les deux workflows étaient rangés dans
`sigma-app/.github/workflows/`, alors que GitHub ne lit que
`.github/workflows/` **à la racine du dépôt**. Ils n'étaient donc pas
enregistrés du tout.

Preuve : `gh api repos/…/actions/workflows/update-data.yml` → **404 Not Found**.
Les runs visibles dans l'historique étaient ceux de **Pages**, pas de la
collecte — j'avais lu cette liste sans vérifier de quel workflow il s'agissait.

## Correctif

| Avant | Après |
|---|---|
| `sigma-app/.github/workflows/update-data.yml` (jamais enregistré) | `.github/workflows/update-data.yml` (actif) |
| chemins `web/data/…` | `sigma-app/web/data/…` |
| verdicts non régénérés après collecte | régénérés, sinon lecture périmée sur données fraîches |
| `pages.yml` dupliqué | laissé hors dépôt : Pages est en mode « branche », un second déploiement échouerait |

Vérifié après fusion : `gh api …/actions/workflows` renvoie
`SIGMA — collecte BRVM quotidienne :: .github/workflows/update-data.yml :: active`.

## Premier run

`gh workflow run update-data.yml --ref main` → run **45775333773**, démarré le
26/11 à 07:26 UTC.

- tests des parseurs : **succès**
- installation OCR (tesseract + poppler) : succès
- collecte des BOC : **en cours**, plus de deux heures (backfill de 260 séances,
  OCR par empreinte PDF)
- plafond du job : **240 minutes**

Le run ne publie que si les fichiers de données ont changé, puis pousse un
commit `data: collecte BRVM officielle et verdicts régénérés`. Rien n'est écrit
si un contrôle bloquant échoue — le collecteur remplace les fichiers de façon
atomique.

## Ce que cela change

Les trois chantiers bloqués passent de « impossible ici » à « à la portée du
runner » : fonds propres (16 sociétés), « dividendes versés » + flux (38),
nombre d'actions (10). Reste à vérifier, au run suivant, que le collecteur
**extrait réellement ces lignes** — c'est un autre travail que de lancer la
collecte.

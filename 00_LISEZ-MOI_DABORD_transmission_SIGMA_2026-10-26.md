# SIGMA BRVM — dossier de transmission du 26 octobre 2026

## Réponse courte

Le ZIP `SIGMA-BRVM_application-v1.4-et-CDC.zip` créé précédemment **ne contient
pas tout le travail actuel**. Il contient 15 fichiers : application v1.4,
ancien collecteur, anciens tests, données publiées et CDC PDF. Il ne contient
ni le dossier `audits/`, ni les rejeux BPA v2.1.1 à v2.1.4, ni les décisions
finales du 26 octobre 2026.

Le présent ZIP de transmission a donc été reconstruit pour permettre une
reprise par un autre développeur ou une autre IA sans télécharger les fichiers
un par un.

## Contenu du ZIP de transmission

À la racine :

- ce fichier `00_LISEZ-MOI_DABORD_transmission_SIGMA_2026-10-26.md` ;
- `MANIFESTE_FICHIERS.csv` : chemin, taille et SHA-256 de chaque fichier
  inclus (hors le manifeste lui-même) ;
- `SIGMA-BRVM_Cahier-des-Charges_v1.2.pdf` ;
- `SIGMA-BRVM_Cahier-des-Charges_v1.md` ;
- `SIGMA-BRVM_plan-signaux-valorisation_2026-10-24.md` ;
- `SIGMA-BRVM_tout-ce-qui-reste-a-construire_2026-10-24.md` ;
- `SIGMA-BRVM_recap-modules_2026-10-22.md` ;
- la planche de marque SIGMA ;
- le dossier complet `sigma-app/`.

Dans `sigma-app/` :

- application web v1.4 : `web/` ;
- collecteur et parseurs : `ingestion/` ;
- parseur BPA courant : `ingestion/eps_evidence.py`
  (`eps-evidence-v2.1.4`) ;
- tests : `tests/test_collect.py` ;
- workflows GitHub préparés mais non activés : `.github/workflows/` ;
- données publiées inchangées : `web/data/data.json` et
  `web/data/boc_archive.json` ;
- tout le dossier `audits/` : audit 480 historique, pilote humain, correctifs,
  contre-lectures, rejeux v2.1.1 à v2.1.4, overlays v2.1.2 et v2.1.4, backlog
  historique, matrices, résultats documentaires, revues et décisions.

## Exclusions volontaires

Ne sont pas inclus :

- `sigma-app/.cache/` : cache volatil de PDF téléchargés pendant les audits.
  Les artefacts d'audit conservent les URL officielles, pages, extraits et
  SHA-256 permettant de retélécharger et contrôler les documents. Le cache
  présent dans l'environnement de travail était incomplet et représentait
  environ 306 Mo ;
- `.pytest_cache/`, `__pycache__/` et fichiers `.pyc` : fichiers régénérables ;
- les anciens ZIP v0.x à v1.4 : ils sont remplacés fonctionnellement par le
  présent paquet pour la reprise du travail courant ;
- les données personnelles du navigateur : profil, positions saisies,
  simulations, épingles, journal et paramètres sont dans le `localStorage` du
  navigateur de l'utilisateur, pas dans les fichiers du projet. Pour les
  transférer, il faut utiliser l'export JSON de l'application et conserver ce
  fichier séparément ;
- aucun mot de passe, token GitHub ou secret n'est inclus ni nécessaire dans
  les fichiers.

## État fonctionnel au 26 octobre 2026

### Application

- Version livrée : **v1.4**.
- Web app statique personnelle, sans donnée fictive dans l'interface.
- Données publiées : collecte officielle du **22 octobre 2026 à 21:20:37 UTC**.
- `web/data/data.json` SHA-256 :
  `ed5ba551705cd6f9ddb5ecaa345ca22712cb41be2317310c235fbf8a36fd1efb`.
- GitHub : workflows présents, activation volontairement reportée après la
  v1.5. Ne jamais demander à l'utilisateur son mot de passe ou un token dans
  le chat.

### Chantier BPA 2016–2025

- Objectif : 48 émetteurs × 10 exercices = 480 cellules, dont **442
  applicables** après dates d'introduction vérifiées.
- Parseur courant : **`eps-evidence-v2.1.4`**.
- Validation réelle :
  - suite de tests : **107 réussis** ;
  - pilote humain 5 sociétés × 10 exercices : **18/18 valeurs**, 0 faux
    positif sur les 72 documents rejoués hors extraction complète ETIT 2018 ;
  - supplément ETIT 2018 sur 23 pages ciblées conservé séparément.
- Rejeu ciblé v2.1.4 : **123/123 résultats**, **123/123 SHA-256 concordants**,
  26 documents sémantiquement modifiés, 15 exercices effectifs corrigés.
- Overlay v2.1.4 : 660 lignes documentaires combinées, 480 cellules.
- Compteurs applicables bruts :
  - documents primaires examinés : 335 ;
  - BPA publiés retenus par la matrice : 31 ;
  - BPA recalculés comparables : 0 ;
  - publications détectées non retenues : 32 en matrice brute, **34 après
    correction manuelle SPHC 2022/2023** ;
  - quarantaine : 1 ;
  - ratios indicatifs séparés : 8 ;
  - illisibles : 72 ; non recherchées : 18 ; introuvables : 15.

Fichiers à lire dans cet ordre pour le chantier BPA :

1. `sigma-app/audits/audit_bpa_480_corrige_rejeu_v214_2026-10-26/REVUE_OVERLAY_ET_DECISIONS.md`
2. `sigma-app/audits/audit_bpa_480_corrige_rejeu_v214_2026-10-26/decisions_humaines_v214.json`
3. `sigma-app/audits/rejeu_cible_bpa_v214_2026-10-26/REVUE_REJEU_CIBLE.md`
4. `sigma-app/audits/contre_lecture_extractions_uniques_2026-10-26/REVUE_CONTRE_LECTURE.md`
5. `sigma-app/audits/audit_bpa_480_2016_2025_2026-10-25/REVUE_AUDIT_480.md`

## Règles à ne jamais casser

1. **Pas de démo dans l'application** : aucune donnée fictive ou inventée.
   Une donnée absente ou non vérifiée doit être affichée comme telle.
2. **Aucune intégration BPA au dataset publié n'a été autorisée à ce stade.**
   Ne pas modifier `web/data/data.json` à partir des audits sans décision
   explicite cellule par cellule.
3. Un **BPA recalculé comparable** exige :
   - résultat attribuable aux actionnaires ordinaires vérifié ;
   - nombre moyen pondéré d'actions ordinaires vérifié.
4. Résultat ÷ actions de fin d'exercice = **ratio indicatif séparé**, jamais
   un BPA comptable comparable.
5. Une extraction unique ne doit pas alimenter silencieusement le dataset ou
   un PER comparable.
6. Ne jamais convertir un montant par action sous échelle de page sans unité
   par action explicite (cas SPHC).
7. Ne jamais déduire l'exercice d'une date de publication ou du seul nom de
   fichier. Les années doivent venir d'en-têtes ou de preuves datées.
8. `NON_PUBLIE_DANS_SOURCES_VERIFIEES` exige un examen réel. Distinguer
   `NON_RECHERCHE`, `DOCUMENT_INTROUVABLE`, `ILLISIBLE` et `NON_APPLICABLE`.
9. TTLS 2024/2025 : valeurs consolidées 219/208 correctement transcrites mais
   exclues provisoirement des BPA formellement comparables, faute de note
   prouvant le numérateur part du groupe.
10. Ne pas réagréger l'ancien journal 480 dans son dossier après changement
    d'empreinte de code : créer un nouveau répertoire d'audit/rejeu.

## Lancer et tester

Depuis `sigma-app/` :

```bash
python3 -m pip install -r requirements.txt pytest
python3 -B -m pytest -q
python3 -m http.server 8000 --directory web --bind 0.0.0.0
```

Puis ouvrir `http://127.0.0.1:8000/` en local.

Recollecte générale (à ne lancer qu'en comprenant qu'elle peut réécrire les
fichiers de données) :

```bash
python3 ingestion/collect.py --boc-count 30 --boc-archive-count 260
```

Pour l'OCR de repli du collecteur général, l'environnement doit aussi fournir
`tesseract-ocr`, `tesseract-ocr-fra`, `poppler-utils` et ImageMagick. Leur
absence ne doit jamais conduire à inventer une valeur.

## Prochaine étape recommandée

Régénérer le backlog documentaire à partir de l'overlay v2.1.4. Le dossier
`audits/backlog_bpa_2026-10-26/` correspond à l'ancienne matrice (104
cellules) et doit être considéré comme historique : BOAS 2020 est notamment
devenu illisible après correction de son rattachement à 2019. Ensuite traiter,
par priorité documentaire, les cellules illisibles/OCR, introuvables et non
recherchées, sans lever la porte d'intégration.

La feuille de route produit v1.5–v1.7 est dans :

- `SIGMA-BRVM_plan-signaux-valorisation_2026-10-24.md` ;
- `SIGMA-BRVM_tout-ce-qui-reste-a-construire_2026-10-24.md`.

## Vérification du paquet

Après extraction, vérifier quelques empreintes avec `MANIFESTE_FICHIERS.csv`.
L'empreinte SHA-256 du ZIP complet doit être conservée avec le fichier lors de
sa transmission ; elle est fournie dans le message de livraison du paquet.

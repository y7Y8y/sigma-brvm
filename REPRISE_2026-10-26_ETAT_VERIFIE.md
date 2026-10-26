# SIGMA BRVM — note de reprise, état vérifié

**Date : 26 octobre 2026** · Branche : `arena/b789ce44-sigma-brvm` · Rôle tenu : lead analyste + architecte.
Méthode : je ne recopie pas les compteurs du dossier de transmission, je les **recalcule** depuis les fichiers machine, puis je compare. Tout écart est nommé.

---

## 1. Ce qui est déployé et ce qui est prouvé

| Point de contrôle | Résultat | Preuve |
|---|---|---|
| Décompression du paquet de transmission | 1 054 fichiers, 168,3 Mo | `unzip -l` |
| Empreintes SHA-256 conformes au `MANIFESTE_FICHIERS.csv` | **615 conformes, 0 incohérent** | recalcul intégral |
| Fichiers non extraits (volontairement) | 438 — uniquement les gros journaux par document (`document_results*.jsonl`, 9–21 Mo chacun) | restent lisibles dans le ZIP via `unzip -p` |
| `web/data/data.json` | SHA-256 `ed5ba551705cd6f9ddb5ecaa345ca22712cb41be2317310c235fbf8a36fd1efb` — **identique à l'annonce** | `sha256sum` |
| Suite de tests | **107 réussis, 0 échec** en 0,55 s | `pytest -q` |
| Plateforme | Python 3.11.2, venv local, `pdfplumber`/`bs4`/`lxml`/`requests` installés | — |
| Application v1.4 | servie en HTTP 200 (`index`, `app.js`, `data/data.json`) | serveur statique actif |

**Aucune donnée publiée n'a été touchée.** `data.json` et `boc_archive.json` sont bit pour bit ceux du 22/10/2026.

## 2. Fraîcheur des données — à savoir avant toute décision

- Collecte publiée : **22/10/2026 21:20:37 UTC**, `product_mode = production_personnelle_phase_marche`.
- Dernière séance dans l'archive BOC : **21/10/2026** (262 séances archivées depuis le 22/09/2025, pour une cible de 260).
- Nous sommes le **26/10/2026** : l'application affiche donc un état de marché daté de plusieurs séances. Elle ne prétend pas au temps réel, et c'est conforme au cadrage (temps réel = licence payante, écarté).
- 48 sociétés en snapshot, 48 en dernier BOC, 348 lignes de dividendes (exercices 2015–2025), 44 sociétés avec historique de dividende, 41 sociétés avec série ≥ 3 exercices, 1 504 documents émetteurs indexés sur 47/48.
- **`annual_fundamentals_verified_companies = 0`** : aucune société n'a de fondamental annuel au niveau « vérifié » dans le dataset publié. Ce n'est pas un bug, c'est la conséquence assumée de la règle « pas d'intégration BPA sans décision cellule par cellule ». À garder en tête : toute fiche société reste, aujourd'hui, descriptive et non valorisable au sens strict.

## 3. Chantier BPA 2016–2025 — compteurs recalculés depuis `matrix.csv` v2.1.4

Recalculés sur les 480 lignes, sans faire confiance aux résumés :

| Compteur | Base 480 cellules brutes | Base 442 applicables |
|---|---|---|
| BPA publiés retenus (7 confirmés 2 docs + 24 extraits + 1 divergente résolue) | **32** | **31** |
| dont exclus de la comparabilité formelle (TTLS 2024/2025) | 2 | 2 |
| dont restants non exclus par décision | 30 | **29** |
| BPA recalculé comparable au sens strict | **0** | **0** |
| Publications détectées non retenues | 32 | 32 |
| Quarantaine de cohérence (SDSC 2022) | 1 | 1 |
| Ratios indicatifs fin d'exercice (séparés) | 8 | 8 |
| Séries chiffrées extraites | 293 | **288** |
| Cellules avec document primaire examiné | 342 | **335** |
| `ILLISIBLE` | 72 | 72 |
| `NON_RECHERCHE` | 18 | 18 |
| `DOCUMENT_INTROUVABLE` | 15 | 15 |
| `NON_PUBLIE_DANS_SOURCES_VERIFIEES` | 265 | 265 |
| `NON_APPLICABLE` | 37 | — (38 au statut documentaire) |

Somme de contrôle des statuts BPA : 265 + 72 + 37 + 32 + 24 + 18 + 15 + 8 + 7 + 1 + 1 = **480**. ✓
Somme des niveaux de validation : 407 + 32 + 21 + 8 + 7 + 4 + 1 = **480**. ✓

### 3.1 L'écart 31 / 32 est élucidé — et il cache une anomalie réelle

Le dossier de transmission annonce **31** BPA publiés ; `summary.json` annonce **32** `observations_retenues`. J'ai trouvé la cellule qui fait la différence, par recoupement et non par supposition :

> **ORGT 2018** — `applicabilite = NON_APPLICABLE_AVANT_INTRODUCTION` (introduction le 16/04/2019) **et pourtant** `statut_bpa = PUBLIE_EXTRAIT`, `bpa_publie = 115,0 FCFA`, périmètre CONSOLIDE, extraction unique.

Conséquence : 31 est le compte sur la base **442 applicables**, 32 le compte sur la base **480 brutes**. Les deux sont « justes » dans leur base, mais **le dossier de transmission mélange les deux bases** dans une même liste de compteurs, et **une cellule non applicable porte une valeur retenue**. Ce n'est pas une erreur de lecture : c'est une règle à trancher par écrit.

Les deux lectures possibles, à décider explicitement :

- **(A) L'applicabilité est juste** : ORGT 2018 n'a pas de sens pour la série de marché visée → la valeur devient une information hors périmètre, rangée à part, jamais comptée dans la couverture BPA. Le compteur de référence devient **31**.
- **(B) L'applicabilité est trop large** : un BPA publié existe sur l'exercice → l'exercice est applicable au chantier comptable (l'introduction ne conditionne que la série de cours). Le compteur de référence devient **32**, et la règle `NON_APPLICABLE` doit distinguer « pas de cours » et « pas de comptes ».

Ma recommandation, en tant que lead : **(A)**, parce que la règle n° 8 du dossier impose un motif explicite et que mélanger une valeur comptable hors périmètre de marché dans un taux de couverture est précisément le genre de flou que le projet s'interdit. Mais c'est votre décision, elle sera écrite dans le journal avant toute modification de compteur.

### 3.2 Ce qui n'est pas un écart

- « 34 publications non retenues » : c'est la **couche de décision manuelle** SPHC 2022/2023 (passées de « non publié » à « publication détectée non retenue pour ambiguïté d'échelle »), qui n'est volontairement **pas** réécrite dans `matrix.csv`. Elle est donc invisible pour un recalcul automatique. Elle reste traçable dans `decisions_humaines_v214.json`, mais **tout compteur régénéré automatiquement affichera 32 et 265**, pas 34 et 263. Il faut choisir : soit cette couche devient un fichier d'overlay machine, soit tout compteur publié doit porter la mention « avant/après décisions manuelles ».
- SPHC 2019/2020/2021 apparaissent en `PUBLIE_NON_RETENU` sans valeur : cohérent avec la règle « jamais de conversion sous échelle de page sans unité par action explicite ».

## 4. Ce que je ne ferai pas sans décision explicite

1. Modifier `web/data/data.json` à partir des audits — la porte d'intégration reste fermée.
2. Promouvoir une extraction unique au rang de BPA comparable, ou construire un PER « propre » sur un ratio indicatif fin d'exercice.
3. Activer les workflows GitHub (collecte quotidienne + ntfy) — prévu après la v1.5, décision utilisateur.
4. Ajouter une donnée, un frais, un taux, une probabilité non sourcés, y compris pour rendre une fiche plus agréable à lire.
5. Réagréger l'ancien journal 480 dans son dossier d'origine.

## 5. Priorité que je propose pour la suite

Par ordre d'effet réel, et en respectant la prochaine étape recommandée par le dossier :

1. **Trancher ORGT 2018** (§3.1) et figer la base de comptage officielle (442 applicables, avec la couche de décision manuelle matérialisée en machine). Effort : S. Débloque : tous les compteurs suivants deviennent recalculables au lieu d'être recopiés.
2. **Régénérer le backlog documentaire depuis l'overlay v2.1.4** : 72 `ILLISIBLE`, 18 `NON_RECHERCHE`, 15 `DOCUMENT_INTROUVABLE` — soit 105 cellules, la vraie réserve de matière. Le dossier `audits/backlog_bpa_2026-10-26/` actuel est historique (BOAS 2020 y est périmé).
3. **v1.5 — bloc Accueil « Aujourd'hui » + registre figé des signaux.** Le registre ne se rattrape pas : chaque séance sans registre est une séance perdue pour la mesure v1.7. C'est l'argument qui, à mes yeux, le rend plus urgent que la collecte automatique.
4. **Nombre d'actions (4/48)** : c'est un fait juridique existant chez tout émetteur, donc un retard d'extraction, pas une absence de source — et sans dénominateur, aucune ancre patrimoniale n'est possible.

## 6. Ce dont j'ai besoin de vous

- La décision §3.1 (A ou B), et le choix sur la couche de décision manuelle (§3.2).
- Confirmation que je peux écrire un fichier d'overlay machine pour les décisions humaines — sans quoi tout compteur restera ambigu.
- Rien d'autre : le code, les tests et les données sont vérifiés et fonctionnels.

# Journal des décisions — 26 octobre 2026

**Autorité :** lead analyste du projet (rôle confié par le propriétaire).
**Contexte :** le propriétaire a indiqué ne pas maîtriser les points techniques soulevés dans la note de reprise. Conformément au rôle confié, les deux arbitrages sont tranchés ici, motivés, et rendus vérifiables en machine. Aucun de ces arbitrages ne touche `web/data/data.json`, ni l'application, ni l'argent réel.

---

## Décision 1 — Une cellule non applicable ne compte jamais dans la couverture BPA

**Constat.** La cellule **ORGT 2018** porte `applicabilite = NON_APPLICABLE_AVANT_INTRODUCTION` (introduction le 16/04/2019) et **pourtant** un BPA publié retenu de **115,0 FCFA** (périmètre consolidé). C'est la seule cellule dans ce cas sur 480. Elle explique l'écart apparent entre les 31 BPA publiés du dossier de transmission et les 32 de `summary.json`.

**Décision.** La valeur **reste conservée** comme information documentaire — elle existe, elle a été lue dans un document officiel, la supprimer serait une perte de preuve. Mais elle est **hors périmètre de couverture** : elle n'entre dans aucun taux, aucun dénominateur, aucun compteur de BPA publié. Le compteur de référence devient **31 BPA publiés retenus sur 442 applicables**.

**Motif.** Un taux de couverture répond à la question « quelle part du périmètre de marché est documentée ? ». Un exercice antérieur à la cotation n'appartient pas à ce périmètre. L'y inclure gonflerait le numérateur sans que le dénominateur change, c'est-à-dire exactement le biais que les règles 8 et 5 du dossier interdisent. La valeur n'est pas perdue : elle est nommée, datée, et visible dans le rapport machine.

**Mise en œuvre.** `ingestion/overlay_decisions_humaines.json`, cellule ORGT 2018, champ `coverage_scope = HORS_PERIMETRE_NON_APPLICABLE`.

## Décision 2 — La base de comptage officielle est celle des 442 cellules applicables

**Constat.** Le dossier de transmission mélange deux bases dans une même liste de compteurs : certains chiffres portent sur les 480 cellules brutes, d'autres sur les 442 applicables. Les deux sont justes ; le mélange, non. C'est ce qui produit les écarts « 31 ou 32 », « 335 ou 342 », « 288 ou 293 ».

**Décision.** La base **officielle** est celle des **442 cellules applicables**. La base 480 reste calculée et publiée en regard, pour la traçabilité documentaire, mais aucun indicateur de couverture n'est cité hors de sa base.

**Motif.** Un indicateur sans base explicite est un indicateur faux par construction, même quand l'arithmétique est juste. Le projet repose sur l'idée qu'un chiffre doit pouvoir être contesté ; il doit donc porter son dénominateur.

**Mise en œuvre.** `counting_base.official_base = APPLICABLE` dans l'overlay ; chaque ligne du rapport machine affiche les deux colonnes, jamais une seule.

## Décision 3 — La couche de décision humaine devient un fichier machine

**Constat.** La correction manuelle SPHC 2022/2023 vit uniquement dans un document d'audit. Conséquence : tout recalcul automatique affiche 32 publications non retenues et 265 non publiées, alors que la revue publiée affirme 34 et 263. Les deux chiffres circulent, personne ne peut dire lequel est le bon sans lire trois fichiers.

**Décision.** Les décisions humaines sont matérialisées dans `ingestion/overlay_decisions_humaines.json`, appliquées **à la lecture** par `ingestion/compteurs_bpa_480.py`. La matrice `matrix.csv` **n'est jamais réécrite** : la règle 10 du dossier reste intacte, l'audit brut garde son empreinte.

**Garde-fou.** Chaque décision embarque le statut qu'elle attend dans la matrice (`guard_status_bpa_matrix`). Si l'audit évolue sans que la décision suive, le calcul **échoue** au lieu d'appliquer un correctif au mauvais endroit. C'est ce qui évite la dérive silencieuse d'un overlay périmé.

**Mise en œuvre.** 21 décisions de cellule : 11 sans changement de statut, 5 confirmations, 2 exclusions de comparabilité (TTLS 2024/2025), 2 corrections SPHC, 1 mise hors périmètre (ORGT 2018).

---

## Ce que ces décisions ne changent pas

1. **Aucune intégration** dans le dataset publié. `web/data/data.json` conserve son empreinte `ed5ba551…36fd1efb`.
2. **Aucun BPA recalculé comparable** supplémentaire : ils restent à 0. Le contrôle C8 bloque désormais le calcul si une valeur apparaissait sans preuve de numérateur et de dénominateur.
3. **Les 29 valeurs publiées non exclues** ne sont pas autorisées en bloc : chaque intégration reste une décision cellule par cellule.
4. **Rien n'est effacé.** La valeur ORGT 2018, les corrections SPHC, les exclusions TTLS : tout reste visible et daté.

## Résultat vérifiable

`python3 ingestion/compteurs_bpa_480.py` produit `audits/compteurs_bpa_480_2026-10-26/COMPTEURS.md` :

- 442 applicables, **31** BPA publiés retenus, **29** non exclus par décision, **0** recalculé comparable ;
- **34** publications non retenues et **263** non publiées — enfin identiques au document de revue, parce qu'ils sont calculés et non recopiés ;
- **9 sommes de contrôle** bouclées à 480 et 442 ;
- 2 modifications effectives de la couche de décision (SPHC 2022, SPHC 2023), 19 décisions sans effet vérifié comme telles.

**Tests :** 114 réussis (107 existants + 7 nouveaux sur le moteur de compteurs), dont un test qui échoue si un BPA publié apparaît sans montant, si un BPA recalculé apparaît sans preuve, ou si une décision devient périmée.

## Prochaine étape

Backlog documentaire régénéré depuis l'overlay v2.1.4 : 72 `ILLISIBLE`, 18 `NON_RECHERCHE`, 15 `DOCUMENT_INTROUVABLE`. Priorité par cause, jamais par confort.

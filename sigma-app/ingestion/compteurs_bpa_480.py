#!/usr/bin/env python3
"""Compteurs déterministes du chantier BPA 480 (sociétés × exercices 2016-2025).

Ce module ne collecte rien et ne publie rien : il RELIT la matrice d'audit brute
(`matrix.csv`), applique la couche de décisions humaines (`overlay_decisions_humaines.json`)
à la lecture, puis recalcule tous les indicateurs de couverture sur deux bases
séparées — 480 cellules brutes et 442 cellules applicables.

Pourquoi cet outil existe
-------------------------
Les compteurs du dossier de transmission étaient recopiés à la main depuis les
revues. Une recopie manuelle dérive en silence : un chiffre périmé reste publié
et personne ne le voit. Ici, chaque compteur est recalculé et chaque somme est
contrôlée ; si une somme ne boucle pas, le script échoue au lieu d'écrire un
rapport faux.

Règles non négociables (cf. 00_LISEZ-MOI_DABORD et plan v1.5-v1.7)
------------------------------------------------------------------
1. `matrix.csv` n'est jamais réécrit : les décisions s'appliquent en mémoire.
2. Une cellule non applicable est hors périmètre : sa valeur éventuelle est
   conservée comme information, jamais comptée dans un taux de couverture.
3. BPA publié, BPA recalculé comparable, ratio indicatif fin d'exercice et statut
   documentaire restent quatre niveaux distincts, jamais additionnés.
4. Aucun indicateur produit ici n'autorise une intégration dans
   `web/data/data.json`.

Usage
-----
    python3 ingestion/compteurs_bpa_480.py
    python3 ingestion/compteurs_bpa_480.py --matrix <chemin> --overlay <chemin> --out <dossier>
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MATRIX = ROOT / "audits" / "audit_bpa_480_corrige_rejeu_v214_2026-10-26" / "matrix.csv"
DEFAULT_OVERLAY = ROOT / "ingestion" / "overlay_decisions_humaines.json"
DEFAULT_OUT = ROOT / "audits" / "compteurs_bpa_480_2026-10-26"

BASE_RAW = "BRUTE_480"
BASE_APPLICABLE = "APPLICABLE_442"

#: Totaux attendus de la grille officielle 48 sociétés x 10 exercices.
#: Surchargeables par `expected_totals` dans l'overlay (utile aux jeux de test).
TOTAUX_ATTENDUS_DEFAUT = {
    "cellules_brutes": 480,
    "cellules_applicables": 442,
    "non_applicables": 38,
}

APP = "APPLICABLE"
NON_APP = "NON_APPLICABLE_AVANT_INTRODUCTION"

#: Statuts qui portent une valeur de BPA publiée transcrite.
PUBLISHED_STATUSES = (
    "PUBLIE_CONFIRME_DEUX_DOCUMENTS",
    "PUBLIE_EXTRAIT",
    "PUBLIE_SOURCE_DIVERGENTE_RESOLUE_PAR_CONTROLE",
)
NON_RETENU_STATUS = "PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE"
QUARANTINE_STATUS = "PUBLIE_EN_QUARANTAINE_COHERENCE"
INDICATIVE_STATUS = "RATIO_INDICATIF_FIN_EXERCICE"

#: Statuts d'absence : aucun blanc silencieux.
ABSENCE_STATUSES = (
    "NON_PUBLIE_DANS_SOURCES_VERIFIEES",
    "NON_RECHERCHE",
    "DOCUMENT_INTROUVABLE",
    "ILLISIBLE",
    "NON_APPLICABLE",
)


class ControleEchoue(RuntimeError):
    """Une somme de contrôle ne boucle pas : on n'écrit pas de rapport."""


def _as_flag(value: str | None) -> bool:
    return str(value or "").strip().lower() not in ("", "0", "false", "none", "nan")


def charger_matrice(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ControleEchoue(f"matrice vide : {path}")
    return rows


def charger_overlay(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def appliquer_overlay(
    rows: list[dict[str, str]], overlay: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Applique les décisions de cellule à une copie de la matrice.

    Chaque décision porte le statut qu'elle attend dans la matrice : si l'audit
    a bougé depuis, la décision est périmée et le calcul doit s'arrêter plutôt
    que d'appliquer un correctif au mauvais endroit.
    """
    par_cle = {(r["ticker"].strip().upper(), int(r["exercice"])): r for r in rows}
    copies = [dict(r) for r in rows]
    copies_par_cle = {(r["ticker"].strip().upper(), int(r["exercice"])): r for r in copies}
    journal: list[dict[str, Any]] = []

    for decision in overlay.get("cell_decisions", []):
        cle = (decision["ticker"].strip().upper(), int(decision["exercice"]))
        if cle not in par_cle:
            raise ControleEchoue(f"décision sur une cellule inexistante : {cle}")
        attendu = decision.get("guard_status_bpa_matrix")
        observe = par_cle[cle]["statut_bpa"]
        if attendu and attendu != observe:
            raise ControleEchoue(
                f"décision périmée pour {cle} : attendu {attendu}, matrice {observe}"
            )

        cible = copies_par_cle[cle]
        avant = cible["statut_bpa"]
        if decision.get("applied_status_bpa"):
            cible["statut_bpa"] = decision["applied_status_bpa"]
        if decision.get("applied_validation_level"):
            cible["validation_level"] = decision["applied_validation_level"]
        if decision.get("coverage_scope"):
            cible["coverage_scope"] = decision["coverage_scope"]
        if decision.get("comparability_excluded"):
            cible["comparability_excluded"] = "True"

        journal.append(
            {
                "ticker": cle[0],
                "exercice": cle[1],
                "decision": decision.get("audit_decision"),
                "statut_avant": avant,
                "statut_apres": cible["statut_bpa"],
                "effet": "modifie" if avant != cible["statut_bpa"] else "sans_effet",
                "source": decision.get("source"),
            }
        )
    return copies, journal


def compter(rows: list[dict[str, Any]], base: str) -> dict[str, Any]:
    """Compteurs d'une base donnée, sans jamais mélanger les niveaux de valeur."""
    statuts = Counter(r["statut_bpa"] for r in rows)
    validations = Counter(r["validation_level"] for r in rows)
    documentaires = Counter(r["statut_documentaire"] for r in rows)

    def est_hors_perimetre(r: dict[str, Any]) -> bool:
        return (
            r["applicabilite"] != APP
            or r.get("coverage_scope") == "HORS_PERIMETRE_NON_APPLICABLE"
        )

    retenus = [r for r in rows if r["statut_bpa"] in PUBLISHED_STATUSES and not est_hors_perimetre(r)]
    hors_perimetre = [
        r
        for r in rows
        if r["statut_bpa"] in PUBLISHED_STATUSES and est_hors_perimetre(r)
    ]
    exclus_comparabilite = [r for r in retenus if r.get("comparability_excluded") == "True"]
    utilisables = [r for r in retenus if r.get("comparability_excluded") != "True"]

    return {
        "base": base,
        "cellules": len(rows),
        "statuts_bpa": dict(sorted(statuts.items())),
        "niveaux_validation": dict(sorted(validations.items())),
        "statuts_documentaires": dict(sorted(documentaires.items())),
        "bpa_publies_transcrits_hors_perimetre_inclus": sum(
            n for s, n in statuts.items() if s in PUBLISHED_STATUSES
        ),
        "bpa_publies_retenus_dans_la_couverture": len(retenus),
        "dont_exclus_de_la_comparabilite_formelle": len(exclus_comparabilite),
        "dont_non_exclus_par_decision": len(utilisables),
        "detail_exclusions_comparabilite": [
            {"ticker": r["ticker"], "exercice": int(r["exercice"])}
            for r in exclus_comparabilite
        ],
        "publications_hors_perimetre_non_comptees": [
            {
                "ticker": r["ticker"],
                "exercice": int(r["exercice"]),
                "statut_bpa": r["statut_bpa"],
                "valeur_conservee_fcfa": r.get("bpa_publie_fcfa") or None,
                "motif": "exercice non applicable (antérieur à l'introduction)",
            }
            for r in hors_perimetre
        ],
        "bpa_recalcules_comparables": sum(
            1 for r in rows if (r.get("bpa_recalcule_comparable_fcfa") or "").strip()
        ),
        "publications_detectees_non_retenues": statuts.get(NON_RETENU_STATUS, 0),
        "quarantaine_coherence": statuts.get(QUARANTINE_STATUS, 0),
        "ratios_indicatifs_fin_exercice_separes": statuts.get(INDICATIVE_STATUS, 0),
        "series_chiffrees_extraites": sum(1 for r in rows if _as_flag(r.get("serie_extraite"))),
        "cellules_document_primaire_examine": sum(
            1 for r in rows if r["statut_documentaire"] == "DOCUMENTS_PRIMAIRES_EXAMINES"
        ),
        "cellules_avec_document_primaire_lu": sum(
            1
            for r in rows
            if _as_flag(r.get("documents_primaires_lus_couvrant_exercice"))
        ),
        "repartition_par_exercice": {
            str(ex): {
                "cellules": len(groupe),
                "bpa_publies_retenus": sum(
                    1
                    for r in groupe
                    if r["statut_bpa"] in PUBLISHED_STATUSES and not est_hors_perimetre(r)
                ),
            }
            for ex, groupe in sorted(
                ((int(ex), g) for ex, g in _grouper(rows, "exercice").items())
            )
        },
    }


def _grouper(rows: list[dict[str, Any]], cle: str) -> dict[Any, list[dict[str, Any]]]:
    groupes: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groupes[r[cle]].append(r)
    return dict(groupes)


def controler(
    rows: list[dict[str, Any]],
    compteurs: dict[str, dict[str, Any]],
    totaux_attendus: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Sommes de contrôle. Une seule qui ne boucle pas interrompt le calcul."""
    attendus = {**TOTAUX_ATTENDUS_DEFAUT, **(totaux_attendus or {})}
    contrôles: list[dict[str, Any]] = []

    def ajouter(nom: str, observe: int, attendu: int) -> None:
        contrôles.append(
            {
                "controle": nom,
                "observe": observe,
                "attendu": attendu,
                "resultat": "OK" if observe == attendu else "ECHEC",
            }
        )

    brut = compteurs[BASE_RAW]
    app = compteurs[BASE_APPLICABLE]

    ajouter(
        "C1 somme des statuts BPA (base brute)",
        sum(brut["statuts_bpa"].values()),
        attendus["cellules_brutes"],
    )
    ajouter(
        "C2 somme des niveaux de validation (base brute)",
        sum(brut["niveaux_validation"].values()),
        attendus["cellules_brutes"],
    )
    ajouter(
        "C3 somme des statuts documentaires (base brute)",
        sum(brut["statuts_documentaires"].values()),
        attendus["cellules_brutes"],
    )
    ajouter(
        "C4 somme des statuts BPA (base applicable)",
        sum(app["statuts_bpa"].values()),
        attendus["cellules_applicables"],
    )

    non_app = sum(1 for r in rows if r["applicabilite"] != APP)
    ajouter("C5 applicables + non applicables", app["cellules"] + non_app, len(rows))
    ajouter("C6 non applicables", non_app, attendus["non_applicables"])

    # Chaque cellule retenue porte une valeur publiée réelle.
    sans_valeur = [
        r
        for r in rows
        if r["statut_bpa"] in PUBLISHED_STATUSES and not (r.get("bpa_publie_fcfa") or "").strip()
    ]
    ajouter("C7 BPA publiés sans valeur transcrite", len(sans_valeur), 0)

    # Aucun BPA recalculé comparable sans numérateur ET dénominateur vérifiés.
    recalcules = [r for r in rows if (r.get("bpa_recalcule_comparable_fcfa") or "").strip()]
    ajouter("C8 BPA recalculés comparables", len(recalcules), 0)

    # Répartition des niveaux de valeur : tout publié est classé une seule fois.
    # Un BPA publié non retenu n'est ni une valeur retenue ni une absence : il a
    # sa propre classe, sinon la somme des niveaux ne boucle pas.
    statuts_bruts = Counter(r["statut_bpa"] for r in rows)
    classes_valeur = sum(
        statuts_bruts[s]
        for s in PUBLISHED_STATUSES + (NON_RETENU_STATUS, QUARANTINE_STATUS, INDICATIVE_STATUS)
    )
    ajouter(
        "C9 publiés + quarantaine + ratios + absences",
        classes_valeur + sum(statuts_bruts[s] for s in ABSENCE_STATUSES),
        len(rows),
    )

    echoues = [c for c in contrôles if c["resultat"] != "OK"]
    if echoues:
        detail = "; ".join(f"{c['controle']}: {c['observe']} != {c['attendu']}" for c in echoues)
        raise ControleEchoue(detail)
    return contrôles


def rendre_markdown(rapport: dict[str, Any]) -> str:
    brut = rapport["compteurs"][BASE_RAW]
    app = rapport["compteurs"][BASE_APPLICABLE]
    lignes = [
        "# Compteurs BPA 480 — recalculés en machine",
        "",
        f"**Date :** {rapport['date']} · **Parseur :** {rapport['parser_version']} · "
        f"**Dataset publié modifié :** {'oui' if rapport['dataset_published_modified'] else 'non'}",
        "",
        f"Source : `{rapport['matrix_reference']}` + overlay `{rapport['overlay_reference']}`.",
        "",
        "## Base officielle",
        "",
        f"{rapport['counting_base']['decision']}",
        "",
        "| Indicateur | 480 brutes | 442 applicables |",
        "|---|---:|---:|",
    ]
    paires = [
        ("BPA publiés retenus dans la couverture", "bpa_publies_retenus_dans_la_couverture"),
        ("dont exclus de la comparabilité formelle", "dont_exclus_de_la_comparabilite_formelle"),
        ("dont non exclus par décision", "dont_non_exclus_par_decision"),
        ("BPA recalculés comparables", "bpa_recalcules_comparables"),
        ("Publications détectées non retenues", "publications_detectees_non_retenues"),
        ("Quarantaine de cohérence", "quarantaine_coherence"),
        ("Ratios indicatifs fin d'exercice (séparés)", "ratios_indicatifs_fin_exercice_separes"),
        ("Séries chiffrées extraites", "series_chiffrees_extraites"),
        ("Cellules avec document primaire examiné", "cellules_document_primaire_examine"),
        ("Cellules avec document primaire lu", "cellules_avec_document_primaire_lu"),
    ]
    for libelle, cle in paires:
        lignes.append(f"| {libelle} | {brut[cle]} | {app[cle]} |")

    lignes += ["", "## Statuts d'absence (base brute)", "", "| Statut | Cellules |", "|---|---:|"]
    for statut in ABSENCE_STATUSES:
        lignes.append(f"| `{statut}` | {brut['statuts_bpa'].get(statut, 0)} |")

    if brut["publications_hors_perimetre_non_comptees"]:
        lignes += [
            "",
            "## Publications hors périmètre, non comptées dans la couverture",
            "",
            "Ces valeurs existent et sont conservées comme information : elles ne sont "
            "jamais agrégées dans un taux de couverture BPA.",
            "",
        ]
        for item in brut["publications_hors_perimetre_non_comptees"]:
            lignes.append(
                f"- **{item['ticker']} {item['exercice']}** — `{item['statut_bpa']}`, "
                f"valeur conservée {item['valeur_conservee_fcfa']} FCFA, {item['motif']}."
            )

    lignes += ["", "## Sommes de contrôle", "", "| Contrôle | Observé | Attendu |", "|---|---:|---:|"]
    for controle in rapport["controles"]:
        lignes.append(f"| {controle['controle']} | {controle['observe']} | {controle['attendu']} |")

    effets = [j for j in rapport["journal_overlay"] if j["effet"] == "modifie"]
    lignes += ["", f"## Décisions ayant modifié la matrice : {len(effets)}", ""]
    for item in effets:
        lignes.append(
            f"- {item['ticker']} {item['exercice']} : `{item['statut_avant']}` → "
            f"`{item['statut_apres']}` ({item['source']})"
        )

    lignes += [
        "",
        "## Portée",
        "",
        "Aucun de ces compteurs n'autorise une intégration dans `web/data/data.json`. "
        "L'intégration reste décidée cellule par cellule.",
        "",
    ]
    return "\n".join(lignes)


def construire_rapport(matrix: Path, overlay_path: Path) -> dict[str, Any]:
    rows = charger_matrice(matrix)
    overlay = charger_overlay(overlay_path)
    rows_appliquees, journal = appliquer_overlay(rows, overlay)

    compteurs = {
        BASE_RAW: compter(rows_appliquees, BASE_RAW),
        BASE_APPLICABLE: compter(
            [r for r in rows_appliquees if r["applicabilite"] == APP], BASE_APPLICABLE
        ),
    }
    controles = controler(rows_appliquees, compteurs, overlay.get("expected_totals"))

    return {
        "schema_version": "sigma-bpa-480-compteurs-v1",
        "date": overlay.get("date"),
        "parser_version": overlay.get("parser_version"),
        "matrix_reference": str(matrix.relative_to(ROOT)) if matrix.is_relative_to(ROOT) else str(matrix),
        "overlay_reference": str(overlay_path.relative_to(ROOT))
        if overlay_path.is_relative_to(ROOT)
        else str(overlay_path),
        "dataset_published_modified": False,
        "counting_base": overlay["counting_base"],
        "compteurs": compteurs,
        "controles": controles,
        "journal_overlay": journal,
        "integration_dataset": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recalcule les compteurs BPA 480.")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    try:
        rapport = construire_rapport(args.matrix, args.overlay)
    except ControleEchoue as erreur:
        print(f"CONTROLE ECHOUE — aucun rapport écrit : {erreur}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "compteurs.json").write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out / "COMPTEURS.md").write_text(rendre_markdown(rapport), encoding="utf-8")

    app = rapport["compteurs"][BASE_APPLICABLE]
    print(
        f"{app['cellules']} applicables · {app['bpa_publies_retenus_dans_la_couverture']} BPA publiés "
        f"retenus · {app['dont_non_exclus_par_decision']} non exclus · "
        f"{app['bpa_recalcules_comparables']} recalculés comparables · "
        f"{len(rapport['controles'])} contrôles OK"
    )
    print(f"écrit : {args.out / 'COMPTEURS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

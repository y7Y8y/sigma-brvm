#!/usr/bin/env python3
"""Backlog documentaire BPA 480, régénéré depuis l'overlay v2.1.4.

Le dossier `audits/backlog_bpa_2026-10-26/` est historique : il a été bâti sur une
matrice antérieure (104 cellules) et certaines cellules y sont périmées — BOAS 2020
est devenue illisible après correction de son rattachement à 2019. Ce script
reconstruit la file de travail depuis la matrice réellement en vigueur, en
appliquant la couche de décisions humaines comme le fait `compteurs_bpa_480.py`.

Deux principes de priorisation, écrits pour être contestables
------------------------------------------------------------
1. **On ne classe pas par confort, on classe par coût d'information.** Une cellule
   dont les documents sont déjà inventoriés mais jamais ouverts coûte moins cher
   qu'une cellule dont il faut d'abord trouver les documents.
2. **On ne lance pas 265 recherches de BPA publié sans avoir mesuré le taux
   d'absence.** Le plus gros bloc du chantier (`NON_PUBLIE_DANS_SOURCES_VERIFIEES`,
   265 cellules) mélange deux choses très différentes : de vraies absences
   éditoriales et des valeurs présentes mais non reconnues par le parseur. Traiter
   le bloc entier sans le mesurer, c'est payer plein prix pour un rendement
   inconnu. D'où `--echantillon` : un échantillon aléatoire reproductible, à
   relire à la main, qui donne ce taux avant d'engager la vague complète.

Chaque groupe porte une **hypothèse causale explicitement marquée comme
hypothèse** : elle oriente la recherche, elle ne la remplace jamais.

Usage
-----
    python3 ingestion/backlog_bpa_480.py
    python3 ingestion/backlog_bpa_480.py --echantillon 24 --seed 20261026
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compteurs_bpa_480 import (  # noqa: E402
    APP,
    DEFAULT_MATRIX,
    DEFAULT_OVERLAY,
    ROOT,
    appliquer_overlay,
    charger_matrice,
    charger_overlay,
)

DEFAULT_OUT = ROOT / "audits" / "backlog_bpa_v214_2026-10-26"

#: Causes de travail restant, par ordre de priorité opérationnelle.
#: `poids` sert au tri : plus le poids est élevé, plus la cellule passe tôt.
CAUSES: dict[str, dict[str, Any]] = {
    "C_NON_RECHERCHE": {
        "poids": 40,
        "statuts": ("NON_RECHERCHE",),
        "libelle": "Documents inventoriés, jamais examinés",
        "action": "Extraction immédiate : le coût marginal est le plus faible du chantier.",
        "hypothese_causale": "Retard d'ordonnancement, non absence de source.",
        "hypothese_marquee_comme_telle": True,
    },
    "B_OCR_SCAN": {
        "poids": 30,
        "statuts": ("ILLISIBLE",),
        "libelle": "Document présent mais illisible (scan/OCR)",
        "action": "Passe OCR ciblée avec recoupement obligatoire ; jamais une lecture unique.",
        "hypothese_causale": (
            "Concentration attendue sur les émetteurs bancaires : les formulaires de "
            "publication BCEAO condensés n'exposent souvent pas de résultat par action "
            "et sont fréquemment diffusés en scan."
        ),
        "hypothese_marquee_comme_telle": True,
    },
    "D_DOCUMENT_INTROUVABLE": {
        "poids": 20,
        "statuts": ("DOCUMENT_INTROUVABLE",),
        "libelle": "Aucun document candidat trouvé dans les canaux audités",
        "action": "Sortir des canaux BRVM : site émetteur, avis d'AG, archives SGI.",
        "hypothese_causale": "Les 15 cellules se concentrent sur un petit nombre d'émetteurs.",
        "hypothese_marquee_comme_telle": True,
    },
    "A_PUBLICATION_NON_RETENUE": {
        "poids": 15,
        "statuts": ("PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE",),
        "libelle": "Publication repérée mais non retenue (échelle, devise, périmètre)",
        "action": "Trancher documentairement la base de calcul, pas convertir au jugé.",
        "hypothese_causale": "Ambiguïté d'unité ou de périmètre dans le document lui-même.",
        "hypothese_marquee_comme_telle": True,
    },
    "E_ABSENCE_A_TESTER": {
        "poids": 10,
        "statuts": ("NON_PUBLIE_DANS_SOURCES_VERIFIEES",),
        "libelle": "Document examiné sans valeur trouvée — absence non prouvée",
        "action": (
            "NE PAS lancer en vague. Mesurer d'abord le taux d'absence sur échantillon "
            "relu à la main : la valeur peut exister sans être reconnue par le parseur."
        ),
        "hypothese_causale": (
            "Deux causes non séparables sans mesure : absence éditoriale réelle, "
            "ou mise en page non reconnue (libellé seul, montants sur sous-ligne)."
        ),
        "hypothese_marquee_comme_telle": True,
    },
}


def utilite_valorisation(exercice: int) -> str:
    """Poids d'usage pour la future fourchette de valeur (v1.6)."""
    if exercice >= 2023:
        return "HAUTE"
    if exercice >= 2021:
        return "MOYENNE"
    return "FAIBLE"


def classe_cellule(row: dict[str, Any]) -> str | None:
    statut = row["statut_bpa"]
    for cle, cause in CAUSES.items():
        if statut in cause["statuts"]:
            return cle
    return None


def construire_lignes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lignes: list[dict[str, Any]] = []
    for row in rows:
        if row["applicabilite"] != APP:
            continue
        cause = classe_cellule(row)
        if cause is None:
            continue
        exercice = int(row["exercice"])
        candidats = int(row.get("documents_candidats_inventories_count") or 0)
        definition = CAUSES[cause]
        lignes.append(
            {
                "ticker": row["ticker"],
                "societe": row["company_name"],
                "secteur": row["sector"],
                "exercice": exercice,
                "cause": cause,
                "libelle_cause": definition["libelle"],
                "statut_bpa": row["statut_bpa"],
                "documents_candidats_inventories": candidats,
                "document_primaire_lu": row.get("documents_primaires_lus_couvrant_exercice"),
                "utilite_valorisation": utilite_valorisation(exercice),
                "priorite": definition["poids"] * 1000
                + (10 if candidats > 0 else 0)
                + (2 if exercice >= 2023 else 1 if exercice >= 2021 else 0),
                "action": definition["action"],
            }
        )
    lignes.sort(key=lambda x: (-x["priorite"], x["ticker"], x["exercice"]))
    for rang, ligne in enumerate(lignes, start=1):
        ligne["rang"] = rang
    return lignes


def echantillon_absence(
    lignes: list[dict[str, Any]], taille: int, seed: str
) -> list[dict[str, Any]]:
    """Échantillon aléatoire reproductible parmi `E_ABSENCE_A_TESTER`.

    Le tirage est un hachage déterministe de (graine, ticker, exercice) : deux
    exécutions avec la même graine donnent le même échantillon, et le protocole
    reste auditable. Aucun `random` lié à l'horloge.
    """
    population = [l for l in lignes if l["cause"] == "E_ABSENCE_A_TESTER"]
    if taille <= 0 or taille >= len(population):
        return [dict(l) for l in population]
    clefs = []
    for ligne in population:
        graine = f"{seed}|{ligne['ticker']}|{ligne['exercice']}"
        clefs.append((hashlib.sha256(graine.encode()).hexdigest(), ligne))
    clefs.sort(key=lambda x: x[0])
    return [dict(ligne) for _, ligne in clefs[:taille]]


def representativite(echantillon: list[dict[str, Any]], population: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare l'échantillon à sa population : un échantillon non représentatif se voit."""
    def par(cle: str, lignes: list[dict[str, Any]]) -> Counter:
        return Counter(str(l[cle]) for l in lignes).most_common()

    return {
        "taille_echantillon": len(echantillon),
        "taille_population": len(population),
        "secteurs_population": dict(par("secteur", population)),
        "secteurs_echantillon": dict(par("secteur", echantillon)),
        "utilite_population": dict(par("utilite_valorisation", population)),
        "utilite_echantillon": dict(par("utilite_valorisation", echantillon)),
    }


def rendre_markdown(rapport: dict[str, Any]) -> str:
    lignes = [
        "# Backlog documentaire BPA 480 — régénéré depuis l'overlay v2.1.4",
        "",
        f"**Date :** {rapport['date']} · **Parseur :** {rapport['parser_version']} · "
        f"**Dataset publié modifié :** non",
        "",
        f"Source : `{rapport['matrix_reference']}` + `{rapport['overlay_reference']}`.",
        "",
        "Ce dossier remplace `audits/backlog_bpa_2026-10-26/`, qui reposait sur une",
        "matrice antérieure et doit être considéré comme historique.",
        "",
        f"**Périmètre :** {rapport['perimetre']['cellules_applicables']} cellules applicables, "
        f"dont **{rapport['perimetre']['cellules_a_traiter']} restant à traiter** "
        f"({rapport['perimetre']['taux_restant_pct']} %).",
        "",
        "## File de travail par cause",
        "",
        "| Rang | Cause | Cellules | Sociétés | Établie ? |",
        "|---:|---|---:|---:|---|",
    ]
    for rang, groupe in enumerate(rapport["groupes"], start=1):
        lignes.append(
            f"| {rang} | **{groupe['cause']}** — {groupe['libelle']} | {groupe['cellules']} | "
            f"{groupe['societes']} | oui, {groupe['documents_candidats']} documents candidats inventoriés |"
        )

    lignes += ["", "## Hypothèses causales (à réfuter, pas à croire)", ""]
    for groupe in rapport["groupes"]:
        lignes.append(f"- **{groupe['cause']}** — *hypothèse :* {groupe['hypothese_causale']}")
        lignes.append(f"  *action :* {groupe['action']}")

    lignes += ["", "## Première vague : les cellules les moins chères", ""]
    for ligne in rapport["premiere_vague"]:
        lignes.append(
            f"{ligne['rang']}. **{ligne['ticker']} {ligne['exercice']}** — {ligne['societe']} "
            f"({ligne['secteur']}) · {ligne['documents_candidats_inventories']} documents inventoriés · "
            f"utilité valorisation {ligne['utilite_valorisation']}"
        )

    if rapport.get("echantillon"):
        ech = rapport["echantillon"]
        lignes += [
            "",
            "## Test du taux d'absence (obligatoire avant la vague de 265)",
            "",
            f"Tirage reproductible : **{ech['taille']} cellules** sur {ech['population']}, "
            f"graine `{ech['seed']}`.",
            "",
            "Protocole : relire chaque cellule à la main sur son PDF. Trois issues seulement —",
            "**valeur trouvée** (le parseur avait un trou de rappel), **absence confirmée**,",
            "**toujours illisible** (requalifier).",
            "",
            "| Société | Exercice | Secteur | Utilité valorisation |",
            "|---|---:|---|---|",
        ]
        for cellule in ech["cellules"]:
            lignes.append(
                f"| {cellule['ticker']} | {cellule['exercice']} | {cellule['secteur']} | "
                f"{cellule['utilite_valorisation']} |"
            )
        lignes += [
            "",
            "Décision conditionnelle écrite à l'avance, pour éviter la fuite devant le résultat :",
            "",
            "- **≥ 30 % de valeurs trouvées** → le bloc de 265 est en grande partie un trou de",
            "  rappel du parseur. Priorité absolue au parseur, pas à la recherche documentaire.",
            "- **10 à 30 %** → correction du parseur puis relecture ciblée des structures de",
            "  page concernées.",
            "- **< 10 %** → absence éditoriale majoritairement réelle. On cesse d'y investir",
            "  et on documente le statut, sans le maquiller en valeur.",
        ]

    lignes += [
        "",
        "## Portée",
        "",
        "Aucune ligne de ce backlog n'autorise une intégration dans `web/data/data.json`.",
        "Un BPA recalculé comparable exige toujours un numérateur attribuable aux",
        "actionnaires ordinaires vérifié et un nombre moyen pondéré d'actions vérifié.",
        "",
    ]
    return "\n".join(lignes)


def construire_rapport(
    matrix: Path, overlay_path: Path, taille_echantillon: int = 0, seed: str = "20261026"
) -> dict[str, Any]:
    rows = charger_matrice(matrix)
    overlay = charger_overlay(overlay_path)
    rows_appliquees, _ = appliquer_overlay(rows, overlay)
    applicables = [r for r in rows_appliquees if r["applicabilite"] == APP]

    lignes = construire_lignes(rows_appliquees)
    groupes = []
    for cle, definition in CAUSES.items():
        sel = [l for l in lignes if l["cause"] == cle]
        if not sel:
            continue
        groupes.append(
            {
                "cause": cle,
                "libelle": definition["libelle"],
                "action": definition["action"],
                "hypothese_causale": definition["hypothese_causale"],
                "cellules": len(sel),
                "societes": len({l["ticker"] for l in sel}),
                "documents_candidats": sum(l["documents_candidats_inventories"] for l in sel),
                "par_secteur": dict(Counter(l["secteur"] for l in sel).most_common()),
                "par_utilite_valorisation": dict(
                    Counter(l["utilite_valorisation"] for l in sel).most_common()
                ),
            }
        )
    groupes.sort(key=lambda g: CAUSES[g["cause"]]["poids"], reverse=True)

    rapport: dict[str, Any] = {
        "schema_version": "sigma-bpa-480-backlog-v1",
        "date": overlay.get("date"),
        "parser_version": overlay.get("parser_version"),
        "matrix_reference": str(matrix.relative_to(ROOT)) if matrix.is_relative_to(ROOT) else str(matrix),
        "overlay_reference": str(overlay_path.relative_to(ROOT))
        if overlay_path.is_relative_to(ROOT)
        else str(overlay_path),
        "perimetre": {
            "cellules_applicables": len(applicables),
            "cellules_a_traiter": len(lignes),
            "taux_restant_pct": round(100 * len(lignes) / len(applicables), 2) if applicables else 0.0,
            "cellules_hors_file": len(applicables) - len(lignes),
        },
        "groupes": groupes,
        "premiere_vague": [l for l in lignes if l["cause"] == "C_NON_RECHERCHE"][:20],
        "lignes": lignes,
    }

    if taille_echantillon:
        population = [l for l in lignes if l["cause"] == "E_ABSENCE_A_TESTER"]
        ech = echantillon_absence(lignes, taille_echantillon, seed)
        rapport["echantillon"] = {
            "seed": seed,
            "taille": len(ech),
            "population": len(population),
            "cellules": ech,
            "representativite": representativite(ech, population),
        }
    return rapport


def ecrire(rapport: dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "BACKLOG.md").write_text(rendre_markdown(rapport), encoding="utf-8")

    colonnes = [
        "rang",
        "ticker",
        "societe",
        "secteur",
        "exercice",
        "cause",
        "libelle_cause",
        "statut_bpa",
        "documents_candidats_inventories",
        "utilite_valorisation",
        "priorite",
        "action",
    ]
    with (out / "backlog.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=colonnes, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rapport["lignes"])

    resume = {k: v for k, v in rapport.items() if k != "lignes"}
    (out / "backlog.json").write_text(
        json.dumps(resume, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Régénère le backlog documentaire BPA 480.")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--echantillon", type=int, default=0)
    parser.add_argument("--seed", default="20261026")
    args = parser.parse_args(argv)

    rapport = construire_rapport(args.matrix, args.overlay, args.echantillon, args.seed)
    ecrire(rapport, args.out)

    if args.echantillon:
        print(
            f"échantillon : {rapport['echantillon']['taille']} cellules sur "
            f"{rapport['echantillon']['population']} (graine {args.seed})"
        )
    print(
        f"{rapport['perimetre']['cellules_a_traiter']} cellules à traiter sur "
        f"{rapport['perimetre']['cellules_applicables']} applicables "
        f"({rapport['perimetre']['taux_restant_pct']} %) · "
        + " · ".join(f"{g['cause']}={g['cellules']}" for g in rapport["groupes"])
    )
    print(f"écrit : {args.out / 'BACKLOG.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

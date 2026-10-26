#!/usr/bin/env python3
"""Delta sémantique entre l'ancien journal 480 et le rejeu ciblé v2.1.3.

La comparaison porte sur les observations par action et les figures BPA,
pas sur les métadonnées nouvelles ajoutées par le parseur. Elle ne modifie
ni l'ancien audit ni le dataset publié.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
APP_ROOT = ROOT.parent.parent
OLD_DIR = APP_ROOT / "audits" / "audit_bpa_480_2016_2025_2026-10-25"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def eps_tuple(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("target_exercice"),
        item.get("value"),
        item.get("currency"),
        item.get("basis"),
        item.get("component"),
        item.get("accounting_scope"),
        item.get("eligible_fcfa_total_basic"),
        (item.get("evidence") or {}).get("page"),
    )


def share_tuple(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("target_exercice"),
        item.get("value"),
        item.get("denominator_kind") or item.get("share_count_kind"),
        item.get("accounting_scope"),
        (item.get("evidence") or {}).get("page"),
    )


def numerator_tuple(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("target_exercice"),
        item.get("value"),
        item.get("raw_value"),
        item.get("numerator_kind"),
        item.get("currency"),
        item.get("accounting_scope"),
        (item.get("evidence") or {}).get("page"),
    )


def counter_delta(old: Counter, new: Counter) -> dict[str, list[list[Any]]]:
    removed = old - new
    added = new - old
    return {
        "removed": [list(item) for item in sorted(removed.elements(), key=lambda x: str(x))],
        "added": [list(item) for item in sorted(added.elements(), key=lambda x: str(x))],
    }


def collect_eps_figures(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def visit(path: str, value: Any) -> None:
        if isinstance(value, dict):
            figure = value.get("benefice_par_action")
            if isinstance(figure, dict):
                found.append(
                    {
                        "column_path": path,
                        "value": figure.get("value"),
                        "accounting_scope": figure.get("accounting_scope"),
                        "framework": figure.get("framework"),
                        "currency": figure.get("currency"),
                        "component": figure.get("component"),
                        "basis": figure.get("basis"),
                        "candidate_signature": figure.get("candidate_signature"),
                    }
                )
            for key, child in value.items():
                visit(f"{path}.{key}" if path else str(key), child)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(f"{path}[{index}]", child)

    visit("", extraction.get("columns") or {})
    return found


def main() -> int:
    manifest = load_json(ROOT / "manifest.json")
    matrix = {
        (row["ticker"], int(row["exercice"])): row
        for row in load_json(OLD_DIR / "matrix.json")
    }
    old_rows: dict[str, dict[str, Any]] = {}
    for line in (OLD_DIR / "document_results.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            old_rows[row["candidate_id"]] = row

    documents: list[dict[str, Any]] = []
    cell_eps_old: dict[tuple[str, int], Counter] = defaultdict(Counter)
    cell_eps_new: dict[tuple[str, int], Counter] = defaultdict(Counter)
    cell_eligible_old: dict[tuple[str, int], Counter] = defaultdict(Counter)
    cell_eligible_new: dict[tuple[str, int], Counter] = defaultdict(Counter)

    for item in manifest.get("documents") or []:
        if item.get("replay_status") != "A_REJOUER":
            continue
        candidate_id = item["candidate_id"]
        ticker = item["ticker"]
        old = old_rows[candidate_id]
        result_path = ROOT / str(item["result_file"])
        if not result_path.exists():
            documents.append(
                {
                    "candidate_id": candidate_id,
                    "ticker": ticker,
                    "label": item.get("label"),
                    "url": item.get("url"),
                    "old_sha256": old.get("document_sha256"),
                    "new_sha256": None,
                    "sha256_match": False,
                    "old_parser_version": None,
                    "new_parser_version": None,
                    "old_effective_exercice": (old.get("extraction") or {}).get(
                        "effective_exercice"
                    ),
                    "new_effective_exercice": None,
                    "changed_semantically": False,
                    "replay_missing_result": True,
                    "eps_delta": counter_delta(Counter(), Counter()),
                    "shares_delta": counter_delta(Counter(), Counter()),
                    "numerators_delta": counter_delta(Counter(), Counter()),
                    "old_eps_figures": [],
                    "new_eps_figures": [],
                }
            )
            continue
        new = load_json(result_path)
        old_ex = old.get("extraction") or {}
        new_ex = new.get("extraction") or {}
        old_per = old_ex.get("per_share_observations") or {}
        new_per = new_ex.get("per_share_observations") or {}

        old_eps = Counter(eps_tuple(x) for x in (old_per.get("eps") or []))
        new_eps = Counter(eps_tuple(x) for x in (new_per.get("eps") or []))
        old_shares = Counter(share_tuple(x) for x in (old_per.get("shares") or []))
        new_shares = Counter(share_tuple(x) for x in (new_per.get("shares") or []))
        old_nums = Counter(numerator_tuple(x) for x in (old_per.get("numerators") or []))
        new_nums = Counter(numerator_tuple(x) for x in (new_per.get("numerators") or []))
        old_figures = collect_eps_figures(old_ex)
        new_figures = collect_eps_figures(new_ex)

        for source, bag_all, bag_eligible in (
            (old_per, cell_eps_old, cell_eligible_old),
            (new_per, cell_eps_new, cell_eligible_new),
        ):
            for obs in source.get("eps") or []:
                year = obs.get("target_exercice")
                if not isinstance(year, int):
                    continue
                key = (ticker, year)
                tup = eps_tuple(obs)
                bag_all[key][tup] += 1
                if obs.get("eligible_fcfa_total_basic"):
                    bag_eligible[key][tup] += 1

        eps_delta = counter_delta(old_eps, new_eps)
        shares_delta = counter_delta(old_shares, new_shares)
        nums_delta = counter_delta(old_nums, new_nums)
        changed = any(
            delta["removed"] or delta["added"]
            for delta in (eps_delta, shares_delta, nums_delta)
        ) or old_figures != new_figures or old_ex.get("effective_exercice") != new_ex.get(
            "effective_exercice"
        )
        documents.append(
            {
                "candidate_id": candidate_id,
                "ticker": ticker,
                "label": item.get("label"),
                "url": item.get("url"),
                "old_sha256": old.get("document_sha256"),
                "new_sha256": new.get("document_sha256"),
                "sha256_match": old.get("document_sha256") == new.get("document_sha256"),
                "old_parser_version": old_per.get("parser_version"),
                "new_parser_version": new_per.get("parser_version"),
                "old_effective_exercice": old_ex.get("effective_exercice"),
                "new_effective_exercice": new_ex.get("effective_exercice"),
                "changed_semantically": bool(changed),
                "eps_delta": eps_delta,
                "shares_delta": shares_delta,
                "numerators_delta": nums_delta,
                "old_eps_figures": old_figures,
                "new_eps_figures": new_figures,
            }
        )

    cells: list[dict[str, Any]] = []
    all_keys = set(cell_eps_old) | set(cell_eps_new) | set(cell_eligible_old) | set(cell_eligible_new)
    for key in sorted(all_keys):
        if cell_eps_old[key] == cell_eps_new[key]:
            continue
        eligible_delta = counter_delta(cell_eligible_old[key], cell_eligible_new[key])
        if eligible_delta["added"] and eligible_delta["removed"]:
            impact = "ELIGIBILITE_OU_PERIMETRE_MODIFIE"
        elif eligible_delta["added"]:
            impact = "NOUVELLE_ELIGIBILITE"
        elif eligible_delta["removed"]:
            impact = "ELIGIBILITE_RETIREE"
        else:
            impact = "CHANGEMENT_NON_ELIGIBLE_OU_DOUBLON_SEULEMENT"
        old_cell = matrix.get(key) or {}
        cells.append(
            {
                "ticker": key[0],
                "exercice": key[1],
                "impact": impact,
                "old_matrix_status": old_cell.get("statut_bpa"),
                "old_matrix_validation": old_cell.get("validation_level"),
                "old_matrix_published_eps_fcfa": old_cell.get("bpa_publie_fcfa"),
                "old_matrix_candidate_before_quarantine_fcfa": old_cell.get(
                    "bpa_publie_candidat_avant_quarantaine_fcfa"
                ),
                "eligible_delta": eligible_delta,
                "all_eps_delta": counter_delta(cell_eps_old[key], cell_eps_new[key]),
            }
        )

    changed_docs = [doc for doc in documents if doc["changed_semantically"]]
    summary = {
        "documents_replayed": len(documents),
        "documents_with_result": sum(
            1 for doc in documents if not doc.get("replay_missing_result")
        ),
        "documents_missing_result": sum(
            1 for doc in documents if doc.get("replay_missing_result")
        ),
        "documents_sha256_matches": sum(1 for doc in documents if doc["sha256_match"]),
        "documents_changed_semantically": len(changed_docs),
        "documents_unchanged_semantically": len(documents) - len(changed_docs),
        "cells_with_eps_delta": len(cells),
        "cells_by_impact": dict(Counter(cell["impact"] for cell in cells)),
        "dataset_published_modified": False,
    }
    payload = {"summary": summary, "documents": documents, "cells": cells}
    (ROOT / "delta_rejeu.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fields = [
        "ticker",
        "exercice",
        "impact",
        "old_matrix_status",
        "old_matrix_validation",
        "old_matrix_published_eps_fcfa",
        "eligible_removed",
        "eligible_added",
    ]
    with (ROOT / "delta_cells.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for cell in cells:
            writer.writerow(
                {
                    "ticker": cell["ticker"],
                    "exercice": cell["exercice"],
                    "impact": cell["impact"],
                    "old_matrix_status": cell["old_matrix_status"],
                    "old_matrix_validation": cell["old_matrix_validation"],
                    "old_matrix_published_eps_fcfa": cell["old_matrix_published_eps_fcfa"],
                    "eligible_removed": json.dumps(
                        cell["eligible_delta"]["removed"], ensure_ascii=False
                    ),
                    "eligible_added": json.dumps(
                        cell["eligible_delta"]["added"], ensure_ascii=False
                    ),
                }
            )

    lines = [
        "# Rejeu ciblé BPA sous parseur v2.1.3 — delta initial",
        "",
        f"- Documents rejoués : **{summary['documents_replayed']}**",
        f"- SHA-256 identiques à l'ancien journal : **{summary['documents_sha256_matches']}**",
        f"- Documents avec delta sémantique : **{summary['documents_changed_semantically']}**",
        f"- Cellules avec delta BPA : **{summary['cells_with_eps_delta']}**",
        "",
        "## Cellules dont l'éligibilité change",
        "",
    ]
    for cell in cells:
        if cell["impact"] != "CHANGEMENT_NON_ELIGIBLE_OU_DOUBLON_SEULEMENT":
            lines.append(
                f"- **{cell['ticker']} {cell['exercice']}** — {cell['impact']} ; "
                f"ancienne matrice : {cell['old_matrix_status']} / {cell['old_matrix_published_eps_fcfa']} ; "
                f"retiré : {cell['eligible_delta']['removed']} ; ajouté : {cell['eligible_delta']['added']}"
            )
    lines.extend(
        [
            "",
            "Ce delta est une couche de revue séparée : il ne remplace pas la",
            "matrice 480 brute et ne modifie pas le dataset publié.",
            "",
        ]
    )
    (ROOT / "REVUE_REJEU_CIBLE.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

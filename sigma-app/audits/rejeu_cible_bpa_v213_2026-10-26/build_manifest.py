#!/usr/bin/env python3
"""Manifeste du rejeu v2.1.3 : preuves par action + risque d'exercice.

Le premier ensemble reprend les 88 documents du rejeu v2.1.2. Le second est
déduit uniquement des champs déjà journalisés : exercice effectif absent ou
postérieur à 2025, désaccord nom/effectif, nom sans exercice, ou preuves de
clôture stockées incompatibles avec l'exercice effectif historique. Le
rapport annuel Ecobank Group 2018, déjà en timeout dans le journal 480, est
explicitement exclu du rejeu intégral et reste traité par pages ciblées.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
APP_ROOT = HERE.parent.parent
OLD_DIR = APP_ROOT / "audits" / "audit_bpa_480_2016_2025_2026-10-25"
V212_DIR = APP_ROOT / "audits" / "rejeu_cible_bpa_v212_2026-10-26"
ETIT_ANNUAL_TIMEOUT = "f67fd4f860515787"
CLOSING_PATTERNS = (
    r"exercices?\s+clos\s+(?:le|les)\s+31\s+d[ée]cembre\s+(20\d{2})",
    r"exercice clos le 31\s+d[ée]cembre\s+(20\d{2})",
    r"for the year ended 31\s+december\s+(20\d{2})",
    r"year ended 31\s+december\s+(20\d{2})",
    r"au 31\s+d[ée]cembre\s+(20\d{2})",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def stored_closing_choice(evidence: list[dict[str, Any]]) -> int | None:
    counts: Counter[int] = Counter()
    for item in evidence:
        line = str(item.get("line") or "")
        for pattern in CLOSING_PATTERNS:
            for match in re.finditer(pattern, line, flags=re.I):
                counts[int(match.group(1))] += 1
    if not counts:
        return None
    top = max(counts.values())
    return max(year for year, count in counts.items() if count == top)


def main() -> int:
    plan = load_json(OLD_DIR / "candidate_plan.json")
    candidates = {
        str(item.get("candidate_id")): item for item in plan.get("candidates") or []
    }
    old_rows: dict[str, dict[str, Any]] = {}
    for line in (OLD_DIR / "document_results.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.strip():
            row = json.loads(line)
            old_rows[str(row.get("candidate_id"))] = row
    previous = load_json(V212_DIR / "manifest.json")

    selected: dict[str, dict[str, Any]] = {}
    for item in previous.get("documents") or []:
        if item.get("replay_status") != "A_REJOUER":
            continue
        candidate_id = str(item["candidate_id"])
        selected[candidate_id] = {
            "candidate_id": candidate_id,
            "ticker": item.get("ticker"),
            "url": item.get("url"),
            "label": item.get("label"),
            "old_document_sha256": item.get("old_document_sha256"),
            "old_observation_counts": item.get("old_observation_counts") or {},
            "selection_reasons": list(item.get("selection_reasons") or []),
            "candidate_file": f"candidats/{candidate_id}.json",
            "result_file": f"resultats/{candidate_id}.json",
            "replay_status": "A_REJOUER",
        }

    excluded: list[dict[str, Any]] = []
    for candidate_id, row in old_rows.items():
        extraction = row.get("extraction") or {}
        document = extraction.get("document") or {}
        classified = row.get("classified_document") or {}
        effective = extraction.get("effective_exercice")
        filename_year = classified.get("exercice")
        if candidate_id == ETIT_ANNUAL_TIMEOUT:
            excluded.append(
                {
                    "candidate_id": candidate_id,
                    "ticker": row.get("ticker"),
                    "url": row.get("url"),
                    "label": classified.get("label"),
                    "selection_reasons": ["TIMEOUT_HISTORIQUE_EXTRACTION_480"],
                    "replay_status": "EXCLU_TIMEOUT_HISTORIQUE_PAGES_CIBLEES_SEPAREES",
                }
            )
            continue
        reasons: list[str] = []
        if effective is None and not row.get("error"):
            reasons.append("RISQUE_EXERCICE_EFFECTIF_NON_PROUVE")
        if isinstance(effective, int) and effective > 2025:
            reasons.append("RISQUE_EXERCICE_EFFECTIF_APRES_2025")
        if filename_year is not None and effective is not None and filename_year != effective:
            reasons.append("RISQUE_NOM_ET_EFFECTIF_DIFFERENTS")
        if filename_year is None:
            reasons.append("RISQUE_NOM_SANS_EXERCICE")
        closing_choice = stored_closing_choice(
            document.get("content_exercice_evidence") or []
        )
        if closing_choice is not None and effective is not None and closing_choice != effective:
            reasons.append("RISQUE_PREUVES_STOCKEES_CLOTURE_DIFFERENTE")
        if not reasons:
            continue
        if candidate_id == ETIT_ANNUAL_TIMEOUT:
            excluded.append(
                {
                    "candidate_id": candidate_id,
                    "ticker": row.get("ticker"),
                    "url": row.get("url"),
                    "label": classified.get("label"),
                    "selection_reasons": reasons,
                    "replay_status": "EXCLU_TIMEOUT_HISTORIQUE_PAGES_CIBLEES_SEPAREES",
                }
            )
            continue
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise SystemExit(f"Candidat absent du plan : {candidate_id}")
        per_share = extraction.get("per_share_observations") or {}
        existing = selected.get(candidate_id)
        if existing is None:
            selected[candidate_id] = {
                "candidate_id": candidate_id,
                "ticker": row.get("ticker"),
                "url": row.get("url"),
                "label": classified.get("label"),
                "old_document_sha256": row.get("document_sha256"),
                "old_observation_counts": {
                    key: len(per_share.get(key) or [])
                    for key in ("eps", "shares", "numerators")
                },
                "selection_reasons": reasons,
                "candidate_file": f"candidats/{candidate_id}.json",
                "result_file": f"resultats/{candidate_id}.json",
                "replay_status": "A_REJOUER",
            }
        else:
            for reason in reasons:
                if reason not in existing["selection_reasons"]:
                    existing["selection_reasons"].append(reason)

    documents = sorted(
        selected.values(), key=lambda item: (str(item.get("ticker")), str(item.get("label")))
    )
    for item in documents:
        write_json(
            HERE / str(item["candidate_file"]), candidates[str(item["candidate_id"])]
        )
    manifest = {
        "created_at": "2026-10-26",
        "parser_target": "eps-evidence-v2.1.3",
        "source_journal": "audits/audit_bpa_480_2016_2025_2026-10-25/document_results.jsonl",
        "documents_total": len(documents) + len(excluded),
        "documents_to_replay": len(documents),
        "documents_excluded": len(excluded),
        "criteria": [
            "Les 88 documents du rejeu v2.1.2 (observations par action historiques, plus tous SPHC/TTLS).",
            "Tout document journalisé présentant un signal de risque d'exercice : effectif absent ou après 2025, nom/effectif différents, nom sans exercice, ou clôture stockée différente de l'effectif.",
            "Le rapport annuel Ecobank Group 2018 du plan 480 est exclu du rejeu intégral car son extraction historique est un timeout ; il reste validé séparément par pages ciblées.",
        ],
        "documents": documents + excluded,
    }
    write_json(HERE / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "documents_to_replay": len(documents),
                "documents_excluded": len(excluded),
                "by_ticker": dict(
                    sorted(Counter(str(item.get("ticker")) for item in documents).items())
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

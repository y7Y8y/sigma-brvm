#!/usr/bin/env python3
"""Agrège explicitement les 72 documents v2.1.4 rejoués.

Le rapport annuel Ecobank Group 2018 (324 pages) n'est pas dans ce journal :
il reste couvert par la validation séparée par pages ciblées. Ce script ne
lance aucune extraction et ne modifie pas le dataset publié.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_ROOT = HERE.parent.parent
sys.path.insert(0, str(APP_ROOT / "ingestion"))

import regress_pilot_bpa_5 as regression  # noqa: E402


def main() -> int:
    fingerprint = regression._code_fingerprint()
    results_by_key = regression._load_existing_results(
        HERE / "document_results.jsonl", fingerprint
    )
    results = list(results_by_key.values())
    if len(results) != 72:
        raise SystemExit(f"72 documents attendus, {len(results)} trouvés")
    output = HERE / "agregation_72_documents_sans_rapport_annuel_ETIT_2018"
    _matrix, summary = regression._build_outputs(
        results, output_dir=output, tickers=None
    )
    print(
        {
            "documents": len(results),
            "cells": summary.get("cells"),
            "expected_retained": summary.get("expected_retained"),
            "concordant_retained": summary.get("concordant_retained"),
            "false_positives": summary.get("false_positives"),
            "human_rejected": summary.get("human_rejected_publications"),
            "gate_480": summary.get("gate_480"),
            "code_fingerprint": fingerprint,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Revalide le rapport annuel ETIT 2018 sur ses 23 pages déjà sélectionnées.

Le PDF complet de 324 pages n'est pas soumis à l'extraction intégrale dans le
sandbox. Les pages structurées sont construites une à une, exactement avec la
sélection de la régression fermée, puis soumises au parseur courant.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import pdfplumber
import requests

HERE = Path(__file__).resolve().parent
APP_ROOT = HERE.parent.parent
sys.path.insert(0, str(APP_ROOT / "ingestion"))

from collect import structured_lines_from_words  # noqa: E402
from eps_evidence import (  # noqa: E402
    classify_page_accounting_contexts,
    extract_per_share_observations,
)

URL = "https://www.brvm.org/sites/default/files/rapport_annuel_2018_ecobank_group.pdf"
EXPECTED_SHA256 = "294b40ebcacbb07de1d527d185a704bc802e602ec2b78a4fe05420ad3abda0de"
CACHE = APP_ROOT / ".cache" / "regression-pilote-bpa-5-pdf" / "9a74fb755b5f3f3c-rapport_annuel_2018_ecobank_group.pdf"
REFERENCE = APP_ROOT / "audits" / "correctif_sphc_ttls_2026-10-26" / "ETIT_2018_pages_ciblees_result.json"
OUTPUT = HERE / "ETIT_2018_pages_ciblees_result.json"


def main() -> int:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists():
        content = CACHE.read_bytes()
    else:
        response = requests.get(
            URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=180
        )
        response.raise_for_status()
        content = response.content
        CACHE.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"SHA-256 inattendu : {digest}")

    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    selected_pages = list(reference["selected_pages"])
    pages = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages_total = len(pdf.pages)
        for page_number in selected_pages:
            page = pdf.pages[page_number - 1]
            words = page.extract_words(
                x_tolerance=1.5,
                y_tolerance=2,
                use_text_flow=False,
                keep_blank_chars=False,
            )
            lines = structured_lines_from_words(words)
            pages.append(
                {
                    "page_number": page_number,
                    "lines": lines,
                    "text": "\n".join(
                        str(entry.get("text") or "") for entry in lines
                    ),
                }
            )
            print(f"page {page_number} structurée", flush=True)

    contexts, summary = classify_page_accounting_contexts(pages)
    observations = extract_per_share_observations(
        pages, document_exercice=2018, page_contexts=contexts
    )
    payload = {
        "method": reference["method"],
        "source_pdf": str(CACHE.relative_to(APP_ROOT)),
        "sha256": digest,
        "pages_total": pages_total,
        "selected_pages": selected_pages,
        "parser_version": observations.get("parser_version"),
        "page_contexts": contexts,
        "content_summary": summary,
        "per_share_observations": observations,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        {
            "parser_version": observations.get("parser_version"),
            "eps": len(observations.get("eps") or []),
            "shares": len(observations.get("shares") or []),
            "numerators": len(observations.get("numerators") or []),
            "eligible_eps": sum(
                bool(item.get("eligible_fcfa_total_basic"))
                for item in observations.get("eps") or []
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Construit une matrice 480 corrigée par le rejeu ciblé v2.1.4.

Le journal historique de 660 documents reste inchangé. Ce script charge une
copie en mémoire, remplace les 123 résultats du rejeu ciblé, réagrège avec le
harnais 480 courant et écrit uniquement dans ce répertoire. Il ne s'agit pas
d'un rejeu intégral des 660 PDF sous v2.1.4 : les 537 autres lignes sont les
extractions historiques conservées, le rejeu couvrant les documents porteurs
d'observations par action, SPHC/TTLS et les signaux de risque d'exercice.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
APP_ROOT = HERE.parent.parent
OLD_DIR = APP_ROOT / "audits" / "audit_bpa_480_2016_2025_2026-10-25"
REPLAY_DIR = APP_ROOT / "audits" / "rejeu_cible_bpa_v214_2026-10-26"
DATASET = APP_ROOT / "web" / "data" / "data.json"
sys.path.insert(0, str(APP_ROOT / "ingestion"))

import audit_bpa_480 as audit  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rate(num: int, den: int) -> float | None:
    return round(num / den * 100, 3) if den else None


def parser_version(row: dict[str, Any]) -> str:
    return str(
        ((row.get("extraction") or {}).get("per_share_observations") or {}).get(
            "parser_version"
        )
        or "NON_DISPONIBLE"
    )


def document_sha(row: dict[str, Any]) -> str | None:
    return row.get("document_sha256") or (row.get("extraction") or {}).get("sha256")


def applicable_summary(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [row for row in matrix if row.get("applicabilite") == "APPLICABLE"]
    published = [row for row in applicable if row.get("bpa_publie_fcfa") is not None]
    examined = [
        row
        for row in applicable
        if int(row.get("documents_primaires_lus_couvrant_exercice") or 0) > 0
    ]
    validation = Counter(str(row.get("validation_level")) for row in published)
    return {
        "schema_version": "sigma-audit-bpa-480-overlay-v214-v1",
        "cellules": {
            "brutes_48x10": len(matrix),
            "applicables_confirmees": len(applicable),
            "non_applicables_avant_introduction": len(matrix) - len(applicable),
            "applicables_avec_document_primaire_lu": len(examined),
            "applicables_avec_serie_extraite": sum(
                bool(row.get("serie_extraite")) for row in applicable
            ),
            "taux_examen_primaire_sur_applicables_pct": rate(
                len(examined), len(applicable)
            ),
        },
        "bpa_publie": {
            "applicables": len(published),
            "confirmes_deux_documents": validation.get("DEUX_DOCUMENTS_DISTINCTS", 0),
            "controle_arithmetique_concordant": validation.get(
                "CONTROLE_ARITHMETIQUE_CONCORDANT", 0
            ),
            "divergence_resolue_par_controle": validation.get(
                "DIVERGENCE_RESOLUE_PAR_CONTROLE", 0
            ),
            "extraction_unique_sans_controle_pondere": validation.get(
                "EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE", 0
            ),
            "autres_niveaux": {
                key: value
                for key, value in sorted(validation.items())
                if key
                not in {
                    "DEUX_DOCUMENTS_DISTINCTS",
                    "CONTROLE_ARITHMETIQUE_CONCORDANT",
                    "DIVERGENCE_RESOLUE_PAR_CONTROLE",
                    "EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE",
                }
            },
            "taux_sur_applicables_pct": rate(len(published), len(applicable)),
            "taux_sur_applicables_examinees_pct": rate(len(published), len(examined)),
        },
        "bpa_recalcule_comparable_sans_publie_applicables": sum(
            row.get("bpa_publie_fcfa") is None
            and row.get("bpa_recalcule_comparable_fcfa") is not None
            for row in applicable
        ),
        "publications_detectees_non_retenues_applicables": sum(
            row.get("statut_bpa")
            == "PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE"
            for row in applicable
        ),
        "quarantaines_applicables": sum(
            row.get("statut_bpa") == "PUBLIE_EN_QUARANTAINE_COHERENCE"
            for row in applicable
        ),
        "ratios_indicatifs_fin_exercice_applicables": sum(
            row.get("statut_bpa") == "RATIO_INDICATIF_FIN_EXERCICE"
            for row in applicable
        ),
        "statuts_bpa_applicables": dict(
            sorted(Counter(str(row.get("statut_bpa")) for row in applicable).items())
        ),
        "statuts_documentaires_applicables": dict(
            sorted(
                Counter(str(row.get("statut_documentaire")) for row in applicable).items()
            )
        ),
        "dataset_published_modified": False,
    }


def main() -> int:
    inventory = load_json(OLD_DIR / "inventory.json")
    registry = load_json(OLD_DIR / "issuer_registry.json")
    plan = load_json(OLD_DIR / "candidate_plan.json")
    old_matrix = load_json(OLD_DIR / "matrix.json")
    old_rows = load_jsonl(OLD_DIR / "document_results.jsonl")
    manifest = load_json(REPLAY_DIR / "manifest.json")

    old_by_id = {str(row.get("candidate_id")): row for row in old_rows}
    replacements: dict[str, dict[str, Any]] = {}
    replacements_without_per_share_parser: list[str] = []
    for item in manifest.get("documents") or []:
        if item.get("replay_status") != "A_REJOUER":
            continue
        result = load_json(REPLAY_DIR / str(item["result_file"]))
        version = parser_version(result)
        if version == "eps-evidence-v2.1.4":
            pass
        elif (
            version == "NON_DISPONIBLE"
            and parser_version(old_by_id[str(item["candidate_id"])]) == "NON_DISPONIBLE"
        ):
            # Cas BICC : PDF rejeté comme trop volumineux avant toute
            # extraction par action, à l'identique dans l'ancien journal.
            replacements_without_per_share_parser.append(str(item["candidate_id"]))
        else:
            raise SystemExit(f"Parseur inattendu pour {item['candidate_id']} : {version}")
        replacements[str(item["candidate_id"])] = result
    if len(replacements) != 123:
        raise SystemExit(f"123 remplacements attendus, {len(replacements)} trouvés")

    combined: list[dict[str, Any]] = []
    replaced = 0
    sha_matches = 0
    for row in old_rows:
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id in replacements:
            new_row = replacements[candidate_id]
            if document_sha(new_row) == document_sha(row):
                sha_matches += 1
            combined.append(new_row)
            replaced += 1
        else:
            combined.append(row)
    if len(old_rows) != 660 or len(combined) != 660 or replaced != 123:
        raise SystemExit(
            f"Journal inattendu : ancien={len(old_rows)}, combiné={len(combined)}, remplacés={replaced}"
        )
    if sha_matches != 123:
        raise SystemExit(f"SHA-256 concordants : {sha_matches}/123")

    journal_path = HERE / "document_results_overlay.jsonl"
    with journal_path.open("w", encoding="utf-8") as stream:
        for row in combined:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    companies = list(audit._dataset().get("companies") or [])
    matrix, summary = audit._build_outputs(
        inventory=inventory,
        registry=registry,
        plan=plan,
        document_results=combined,
        companies=companies,
        output_dir=HERE,
        tickers=None,
    )

    summary["overlay_rejeu_cible_v214"] = {
        "nature": "REAGREGATION_AVEC_REMPLACEMENT_CIBLE_PAS_REJEU_INTEGRAL_660",
        "documents_journal_historique": len(old_rows),
        "documents_remplaces": replaced,
        "remplacements_sans_parseur_par_action": replacements_without_per_share_parser,
        "documents_historiques_conserves": len(combined) - replaced,
        "sha256_concordants_sur_remplacements": sha_matches,
        "versions_parseur_dans_journal_combine": dict(
            sorted(Counter(parser_version(row) for row in combined).items())
        ),
        "empreintes_code_dans_journal_combine": dict(
            sorted(
                Counter(str(row.get("code_fingerprint") or "NON_DISPONIBLE") for row in combined).items()
            )
        ),
        "journal_historique_modifie": False,
        "dataset_published_sha256": sha256(DATASET),
        "dataset_published_modified": False,
    }
    write_json(HERE / "summary.json", audit._json_ready(summary))

    app_summary = applicable_summary(matrix)
    app_summary["overlay_rejeu_cible_v214"] = summary["overlay_rejeu_cible_v214"]
    write_json(HERE / "summary_applicable_overlay.json", app_summary)

    old_by_cell = {(row["ticker"], row["exercice"]): row for row in old_matrix}
    changed: list[dict[str, Any]] = []
    fields = (
        "statut_bpa",
        "statut_documentaire",
        "validation_level",
        "reference_scope",
        "bpa_publie_fcfa",
        "bpa_publie_candidat_avant_quarantaine_fcfa",
        "bpa_recalcule_comparable_fcfa",
        "ratio_indicatif_fin_exercice_fcfa",
    )
    for row in matrix:
        key = (row["ticker"], row["exercice"])
        old = old_by_cell[key]
        diffs = {
            field: {"ancien": old.get(field), "nouveau": row.get(field)}
            for field in fields
            if old.get(field) != row.get(field)
        }
        if diffs:
            changed.append(
                {
                    "ticker": key[0],
                    "exercice": key[1],
                    "applicabilite": row.get("applicabilite"),
                    "differences": diffs,
                }
            )
    write_json(HERE / "delta_matrice_overlay.json", changed)
    with (HERE / "delta_matrice_overlay.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(["ticker", "exercice", "applicabilite", "champ", "ancien", "nouveau"])
        for item in changed:
            for field, values in item["differences"].items():
                writer.writerow(
                    [
                        item["ticker"],
                        item["exercice"],
                        item["applicabilite"],
                        field,
                        values["ancien"],
                        values["nouveau"],
                    ]
                )

    print(
        json.dumps(
            {
                "documents_combines": len(combined),
                "documents_remplaces": replaced,
                "cellules": len(matrix),
                "cellules_changees_vs_matrice_historique": len(changed),
                "applicables": app_summary["cellules"]["applicables_confirmees"],
                "bpa_publies_applicables": app_summary["bpa_publie"]["applicables"],
                "statuts_bpa_applicables": app_summary["statuts_bpa_applicables"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

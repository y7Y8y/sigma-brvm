#!/usr/bin/env python3
"""Matrice d'audit BPA 2016-2025 (48 sociétés x 10 exercices).

Point de départ contrôlé du chantier 1.1 :
- référentiel des 48 sociétés et aliases déjà codés ;
- statut documentaire séparé du statut BPA ;
- BPA publié, confirmé, recalculé comparable, candidat part du groupe et
  ratio indicatif comptés séparément ;
- aucune absence transformée en « non publié » tant qu'un audit nominatif
  des documents candidats n'est pas terminé.

Le script lit le dataset publié, ne fait aucun appel réseau et écrit des
artefacts d'audit dans ``audits/bpa_2016_2025`` par défaut.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from collect import (  # noqa: E402
    REPORT_LABEL_ALIASES,
    build_eps_audit_matrix,
    build_issuer_registry_snapshot,
    build_issuer_variant_map,
    canonical_issuer_key,
    match_announcement_issuer,
    normalize_key,
    summarize_eps_audit_matrix,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "web" / "data" / "data.json"
DEFAULT_OUTPUT = ROOT / "audits" / "bpa_2016_2025"


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def unmatched_report_pages(data: dict[str, Any]) -> list[dict[str, str]]:
    companies = data.get("companies") or []
    variants = build_issuer_variant_map(companies)
    for alias, ticker in REPORT_LABEL_ALIASES.items():
        variants.setdefault(canonical_issuer_key(alias), ticker)
    unmatched: list[dict[str, str]] = []
    for page in data.get("report_pages") or []:
        label = page.get("label") or ""
        if normalize_key(label).startswith("fctc"):
            continue
        if not match_announcement_issuer(label, variants):
            unmatched.append(page)
    return unmatched


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def render_readme(summary: dict[str, Any]) -> str:
    published = summary["bpa_publie"]
    recalculated = summary["bpa_recalcule_comparable"]
    documentary = summary["statuts_documentaires"]
    statuses = summary["statuts_bpa"]
    year_lines = []
    for year, values in summary["par_exercice"].items():
        year_lines.append(
            f"| {year} | {values['cellules']} | {values['series_extraites']} | {values['bpa_publie']} |"
        )
    return "\n".join(
        [
            "# Audit BPA 2016–2025 — grille initiale",
            "",
            f"Dataset source : `{summary.get('source_dataset_generated_at')}`. "
            f"Cellules brutes : **{summary['cellules_brutes']}** "
            f"({summary['companies']} sociétés x 10 exercices).",
            "",
            "## Taux séparés",
            "",
            "| Niveau | Observations | Dénominateur explicite | Taux |",
            "|---|---:|---|---:|",
            f"| BPA publié extrait | {published['observations']} | séries extraites ({summary['denominateur_series_extraites']}) | {published['taux_sur_series_extraites_pct']} % |",
            f"| BPA publié confirmé deux documents | {published['confirme_deux_documents']} | séries extraites ({summary['denominateur_series_extraites']}) | {published['taux_confirme_sur_series_extraites_pct']} % |",
            f"| BPA recalculé comparable | {recalculated['observations_sans_bpa_publie']} | séries extraites ({summary['denominateur_series_extraites']}) | {recalculated['taux_sur_series_extraites_pct']} % |",
            f"| Candidat part du groupe / pondéré à vérifier | {summary['candidat_part_groupe_ponderee']['observations']} | hors couverture confirmée | — |",
            f"| Ratio indicatif fin d'exercice | {summary['ratio_indicatif_fin_exercice_hors_couverture_bpa']['observations']} | hors couverture BPA | — |",
            "",
            "## Statuts BPA",
            "",
            *[f"- `{key}` : {value}" for key, value in sorted(statuses.items())],
            "",
            "## Statuts documentaires",
            "",
            *[f"- `{key}` : {value}" for key, value in sorted(documentary.items())],
            "",
            "## Par exercice",
            "",
            "| Exercice | Cellules | Séries extraites | BPA publiés |",
            "|---:|---:|---:|---:|",
            *year_lines,
            "",
            "## Lecture obligatoire",
            "",
            "- `NON_RECHERCHE` ne signifie ni absent, ni non publié.",
            "- `NON_PUBLIE_DANS_SOURCES_VERIFIEES` ne pourra être attribué qu'après examen nominatif des documents candidats.",
            "- Le ratio avec les actions en fin d'exercice ne compte pas comme BPA comparable.",
            "- Les exercices avant introduction restent à classer `NON_APPLICABLE` uniquement après preuve officielle de la date d'introduction.",
            "- Les prochains travaux suivent la séquence : référentiel/alias et introductions, audit documentaire 2016–2025, BPA publiés et intrants IAS 33, recalculs seulement si les intrants sont établis, statuts documentés, tests puis collecte complète.",
            "",
        ]
    )


def main() -> int:
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    data = json.loads(data_path.read_text(encoding="utf-8"))
    companies = data.get("companies") or []
    report_pages = data.get("report_pages") or []

    rows = build_eps_audit_matrix(companies, report_pages, years=range(2016, 2026))
    registry = build_issuer_registry_snapshot(companies, report_pages)
    summary = summarize_eps_audit_matrix(rows)
    summary.update(
        {
            "schema_version": " sigma-bpa-audit-v1".strip(),
            "source_dataset_generated_at": data.get("generated_at"),
            "companies": len(companies),
            "exercices": [2016, 2025],
            "referentiel": {
                "societes": len(registry),
                "pages_rattachees": sum(bool(row["report_pages"]) for row in registry),
                "listing_years_status": "NON_RECHERCHE",
                "pages_rapports_non_rattachees": unmatched_report_pages(data),
            },
            "avertissement": (
                "Grille initiale. NON_RECHERCHE ne signifie ni absent ni non "
                "publié. Les exercices antérieurs à une introduction restent "
                "à classer NON_APPLICABLE uniquement après preuve officielle "
                "de la date d'introduction."
            ),
        }
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text(render_readme(summary), encoding="utf-8")
    (output_dir / "summary.json").write_text(
        json.dumps(_json_ready(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "matrix.json").write_text(
        json.dumps(_json_ready(rows), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "issuer_registry.json").write_text(
        json.dumps(_json_ready(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    flat_rows: list[dict[str, Any]] = []
    for row in rows:
        flat_rows.append(
            {
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "sector": row["sector"],
                "exercice": row["exercice"],
                "applicabilite": row["applicabilite"],
                "statut_documentaire": row["statut_documentaire"],
                "documents_candidats_count": len(row["documents_candidats"]),
                "serie_extraite": row["serie_extraite"],
                "statut_bpa": row["statut_bpa"],
                "bpa_publie_fcfa": row["bpa_publie_fcfa"],
                "bpa_recalcule_comparable_fcfa": row["bpa_recalcule_comparable_fcfa"],
                "bpa_part_groupe_ponderee_candidat_fcfa": row[
                    "bpa_part_groupe_ponderee_candidat_fcfa"
                ],
                "ratio_indicatif_fin_exercice_fcfa": row[
                    "ratio_indicatif_fin_exercice_fcfa"
                ],
                "weighted_average_shares": row["denominator"][
                    "weighted_average_shares"
                ],
                "end_of_period_shares": row["denominator"]["end_of_period_shares"],
                "capital_structure_flags": ";".join(row["capital_structure_flags"]),
            }
        )
    write_csv(
        output_dir / "matrix.csv",
        flat_rows,
        list(flat_rows[0].keys()) if flat_rows else [],
    )

    registry_rows = [
        {
            "ticker": row["ticker"],
            "name": row["name"],
            "sector": row["sector"],
            "registry_status": row["registry_status"],
            "report_pages": ";".join(page.get("label") or "" for page in row["report_pages"]),
            "aliases_canoniques": ";".join(row["aliases_canoniques"]),
            "documents_indexes": row["documents_indexes"],
            "annual_document_min_exercice": row["annual_document_min_exercice"],
            "annual_document_max_exercice": row["annual_document_max_exercice"],
            "listing_year": row["listing_year"],
            "listing_year_status": row["listing_year_status"],
        }
        for row in registry
    ]
    write_csv(
        output_dir / "issuer_registry.csv",
        registry_rows,
        list(registry_rows[0].keys()) if registry_rows else [],
    )

    print(json.dumps(_json_ready(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

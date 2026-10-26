#!/usr/bin/env python3
"""Régression documentaire du pilote BPA cinq sociétés × dix exercices.

Le pilote fermé du 2026-10-24 (`audits/pilote_bpa_5/decisions.json`) est la
référence. Ce script ne lance ni la collecte complète ni une réécriture du
dataset publié : il retélécharge uniquement les 73 PDF déjà ouverts pendant
le pilote, les soumet à l'extracteur corrigé, agrège les observations par
société-exercice et compare les 50 cellules aux décisions humaines.

Chaque document est écrit immédiatement dans `document_results.jsonl`. Un
relancement reprend les documents déjà traités avec exactement le même
code (`collect.py` + `eps_evidence.py`). Utiliser `--force` après un
correctif pour tout rejouer.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INGESTION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(INGESTION_DIR))

import collect as sigma_collect  # noqa: E402
from collect import (  # noqa: E402
    ANNUAL_DOC_PRIORITY,
    FIGURE_VALUE_KINDS,
    apply_plausibility_filters,
    classify_report_document,
    derive_eps_metrics,
    extract_annual_figures,
    load_verified_capital_events,
    make_session,
    merge_series_observations,
    series_hygiene,
)

PILOT_DIR = ROOT / "audits" / "pilote_bpa_5"
DEFAULT_OUTPUT_DIR = ROOT / "audits" / "regression_pilote_bpa_5_2026-10-24"
DEFAULT_CACHE_DIR = ROOT / ".cache" / "regression-pilote-bpa-5-pdf"
DATASET_PATH = ROOT / "web" / "data" / "data.json"
REFERENCE_SCOPES = {
    "CIEC": "CONSOLIDE",
    "SNTS": "CONSOLIDE",
    "SDSC": "CONSOLIDE",
    "ETIT": "CONSOLIDE",
    "BOAC": None,
}


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _code_fingerprint() -> str:
    digest = hashlib.sha256()
    for filename in ("collect.py", "eps_evidence.py", "regress_pilot_bpa_5.py"):
        path = INGESTION_DIR / filename
        digest.update(filename.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_companies() -> list[dict[str, Any]]:
    dataset = _load_json(DATASET_PATH)
    companies: list[dict[str, Any]] = []
    for company in dataset.get("companies") or []:
        companies.append(
            {
                "ticker": company.get("ticker"),
                "name": company.get("name"),
                "sector": company.get("sector"),
            }
        )
    return companies


def _pilot_documents(tickers: set[str] | None) -> list[dict[str, Any]]:
    extractions = _load_json(PILOT_DIR / "extractions.json")
    documents: list[dict[str, Any]] = []
    for ticker, payload in extractions.items():
        if tickers and ticker not in tickers:
            continue
        for old_document in payload.get("documents") or []:
            classified = classify_report_document(
                str(old_document.get("url") or ""),
                link_text=str(old_document.get("label") or ""),
            )
            # Le libellé du pilote est plus lisible que celui reconstruit
            # depuis le seul nom de fichier ; l'URL et le SHA attendu sont
            # en revanche repris sans modification.
            classified["label"] = old_document.get("label") or classified.get("label")
            classified["url"] = old_document.get("url")
            documents.append(
                {
                    "ticker": ticker,
                    # Ne pas conserver les anciennes figures du pilote en
                    # mémoire pendant l'extraction PDF : seuls les
                    # identifiants et l'empreinte attendue sont nécessaires.
                    "pilot_document": {
                        field: old_document.get(field)
                        for field in (
                            "filename",
                            "label",
                            "doc_type",
                            "exercice",
                            "published_date",
                            "url",
                            "sha256",
                            "bytes",
                            "pages",
                        )
                    },
                    "classified_document": classified,
                }
            )
    return documents


def _load_existing_results(path: Path, code_fingerprint: str) -> dict[tuple[str, str], dict[str, Any]]:
    results: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.exists():
        return results
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("code_fingerprint") != code_fingerprint:
                continue
            key = (str(row.get("ticker") or ""), str(row.get("url") or ""))
            if all(key):
                results[key] = row
    return results


def _load_existing_keys(path: Path, code_fingerprint: str) -> set[tuple[str, str]]:
    """Clés déjà journalisées, sans retenir les extractions en mémoire."""
    return set(_iter_existing_keys(path, code_fingerprint))


def _iter_existing_keys(path: Path, code_fingerprint: str):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("code_fingerprint") != code_fingerprint:
                continue
            key = (str(row.get("ticker") or ""), str(row.get("url") or ""))
            if all(key):
                yield key
            del row


def _run_documents(
    documents: list[dict[str, Any]],
    *,
    companies: list[dict[str, Any]],
    output_dir: Path,
    cache_dir: Path,
    force: bool,
    allow_ocr: bool,
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "document_results.jsonl"
    fingerprint = _code_fingerprint()
    # Ne retenir que les clés pendant la phase PDF. Les résultats complets
    # déjà journalisés forment un gros graphe d'objets ; le garder en RAM
    # ralentit pdfminer de façon disproportionnée (GC/swap mesurés).
    existing_keys = set() if force else _load_existing_keys(results_path, fingerprint)
    if force and results_path.exists():
        results_path.unlink()

    session = make_session()
    with results_path.open("a", encoding="utf-8") as stream:
        for index, item in enumerate(documents, start=1):
            ticker = str(item["ticker"])
            pilot_document = item["pilot_document"]
            classified = item["classified_document"]
            url = str(pilot_document.get("url") or "")
            key = (ticker, url)
            if key in existing_keys:
                print(f"[{index}/{len(documents)}] {ticker} repris : {classified.get('label')}", flush=True)
                continue

            print(f"[{index}/{len(documents)}] {ticker} extraction : {classified.get('label')}", flush=True)
            row: dict[str, Any] = {
                "ticker": ticker,
                "url": url,
                "code_fingerprint": fingerprint,
                "pilot_document": {
                    "filename": pilot_document.get("filename"),
                    "label": pilot_document.get("label"),
                    "doc_type": pilot_document.get("doc_type"),
                    "exercice": pilot_document.get("exercice"),
                    "published_date": pilot_document.get("published_date"),
                    "sha256": pilot_document.get("sha256"),
                    "bytes": pilot_document.get("bytes"),
                    "pages": pilot_document.get("pages"),
                },
                "classified_document": classified,
            }
            try:
                extraction = extract_annual_figures(
                    session,
                    classified,
                    cache_dir,
                    allow_ocr=allow_ocr,
                    expected_ticker=ticker,
                    companies=companies,
                )
                row["extraction"] = extraction
                row["sha256_matches_pilot"] = bool(
                    pilot_document.get("sha256")
                    and extraction.get("sha256") == pilot_document.get("sha256")
                )
            except Exception as exc:  # un document en échec ne bloque pas les 49 autres cellules
                row["error"] = f"{type(exc).__name__}: {exc}"
                row["sha256_matches_pilot"] = False
            stream.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")
            stream.flush()
            existing_keys.add(key)
            # L'extraction d'un long PDF crée beaucoup d'objets transitoires ;
            # on libère explicitement avant le document suivant.
            del row
            gc.collect()
    by_key = _load_existing_results(results_path, fingerprint)
    return [
        by_key[key]
        for item in documents
        if (
            key := (
                str(item["ticker"]),
                str((item.get("pilot_document") or {}).get("url") or ""),
            )
        ) in by_key
    ]


def _is_aggregable(row: dict[str, Any]) -> bool:
    if row.get("error"):
        return False
    classified = row.get("classified_document") or {}
    if classified.get("doc_type") not in ANNUAL_DOC_PRIORITY:
        return False
    if str(classified.get("selection_status") or "").startswith("EXCLU_"):
        return False
    extraction = row.get("extraction") or {}
    document = extraction.get("document") or {}
    return document.get("selection_rejection") is None


def _observation_from_figure(
    *,
    row: dict[str, Any],
    column_index: int,
    target_exercice: int,
    key: str,
    figure: dict[str, Any],
) -> dict[str, Any]:
    classified = row.get("classified_document") or {}
    extraction = row.get("extraction") or {}
    document = extraction.get("document") or {}
    first_evidence = (figure.get("evidence") or [{}])[0]
    fields = (
        "accounting_scope",
        "accounting_scope_source",
        "framework",
        "currency",
        "currency_source",
        "component",
        "component_source",
        "basis",
        "denominator_kind",
        "published_decimals",
        "token_repair",
        "candidate_signature",
        "candidate_groups",
        "source_multiplier",
        "input_rounding_abs_fcfa",
        "arithmetic_check",
        "coherence_status",
        "quarantine_reasons",
        "eps_metadata",
        "share_metadata",
    )
    observation: dict[str, Any] = {
        "exercice": target_exercice,
        "key": key,
        "value": figure.get("value", figure.get("value_fcfa")),
        "value_kind": figure.get("value_kind") or FIGURE_VALUE_KINDS.get(key, "fcfa"),
        "unit_label": figure.get("unit_label"),
        "extraction_method": figure.get("extraction_method") or "texte_natif",
        "ocr_confidence": figure.get("ocr_confidence"),
        "source_amount_count": figure.get("source_amount_count", 0),
        "occurrences": figure.get("occurrences", 1),
        "column": column_index,
        "doc_exercice": extraction.get("effective_exercice") or classified.get("exercice"),
        "doc_filename_exercice": classified.get("exercice"),
        "doc_url": row.get("url"),
        "doc_label": classified.get("label"),
        "doc_sha256": extraction.get("sha256"),
        "doc_version_label": document.get("version_label"),
        "doc_published_date": classified.get("published_date"),
        "doc_identity_status": (document.get("identity") or {}).get("status"),
        "page": first_evidence.get("page"),
        "line": first_evidence.get("line"),
        "evidence": figure.get("evidence") or [],
    }
    for field in fields:
        observation[field] = figure.get(field)
    return observation


def _aggregate_ticker(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    observations: list[dict[str, Any]] = []
    per_share: list[dict[str, Any]] = []
    notes: list[str] = []
    for row in rows:
        extraction = row.get("extraction") or {}
        detailed = extraction.get("per_share_observations") or {}
        for family in ("eps", "shares", "numerators", "ignored"):
            for item in detailed.get(family) or []:
                if not isinstance(item, dict):
                    continue
                record = dict(item)
                record["family"] = family
                record["document_url"] = row.get("url")
                record["document_label"] = (row.get("classified_document") or {}).get("label")
                record["document_sha256"] = extraction.get("sha256")
                per_share.append(record)
        if not _is_aggregable(row):
            continue
        columns = extraction.get("columns") or {}
        offset_columns = columns.get("colonnes") or {
            "0": columns.get("courant") or {},
            "1": columns.get("precedent") or {},
        }
        effective_exercice = extraction.get("effective_exercice") or (row.get("classified_document") or {}).get("exercice")
        if not isinstance(effective_exercice, int):
            notes.append(f"{row.get('url')} : exercice effectif non prouvé, colonnes non agrégées.")
            continue
        for raw_offset, values in offset_columns.items():
            try:
                column_index = int(raw_offset)
            except (TypeError, ValueError):
                continue
            target_exercice = effective_exercice - column_index
            for key, figure in (values or {}).items():
                if key.startswith("_") or not isinstance(figure, dict):
                    continue
                observations.append(
                    _observation_from_figure(
                        row=row,
                        column_index=column_index,
                        target_exercice=target_exercice,
                        key=key,
                        figure=figure,
                    )
                )

    merged, merge_notes = merge_series_observations(observations)
    notes.extend(merge_notes)
    series: list[dict[str, Any]] = []
    for exercice in sorted(merged, reverse=True):
        figures, rejected = apply_plausibility_filters(merged[exercice])
        notes.extend(f"{exercice} — {note}" for note in rejected)
        if figures:
            series.append({"exercice": exercice, "figures": figures})
    series, hygiene_notes = series_hygiene(series)
    notes.extend(hygiene_notes)
    return series, per_share, notes


def _close(actual: Any, expected: Any) -> bool:
    if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
        return False
    tolerance = max(0.051, abs(float(expected)) * 0.005)
    return abs(float(actual) - float(expected)) <= tolerance


def _compare_cell(expected: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    expected_value = (expected.get("bpa_retenu") or {}).get("valeur")
    actual_value = metrics.get("published_eps_fcfa")
    candidate_value = metrics.get("published_eps_candidate_before_quarantine_fcfa")
    expected_status = expected.get("statut_bpa")
    actual_status = metrics.get("status")
    human_rejected_statuses = {
        "PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE",
        "PUBLIE_INCOHERENT_NON_RETENU",
    }
    human_rejected_publication = expected_status in human_rejected_statuses
    candidate_groups = metrics.get("published_candidate_groups") or []
    other_scope_groups = metrics.get("other_scope_candidate_groups") or []
    detection_sources: list[str] = []
    if candidate_value is not None:
        detection_sources.append("candidat_avant_quarantaine")
    if candidate_groups:
        detection_sources.append("groupes_candidats_du_perimetre_de_reference")
    if other_scope_groups:
        detection_sources.append("groupes_candidats_autre_perimetre")
    if metrics.get("nonretained_eps_observations"):
        detection_sources.append("observations_non_retenues")
    if metrics.get("quarantine"):
        detection_sources.append("quarantaine")
    candidate_detected = bool(detection_sources)

    if isinstance(expected_value, (int, float)):
        if _close(actual_value, expected_value):
            verdict = "VALEUR_CONCORDANTE"
        elif actual_value is not None:
            verdict = "VALEUR_DIVERGENTE"
        elif _close(candidate_value, expected_value):
            verdict = "VALEUR_TROUVEE_MAIS_QUARANTAINE_OU_NON_ELIGIBLE"
        else:
            verdict = "VALEUR_ATTENDUE_NON_TROUVEE"
    else:
        if actual_value is not None:
            verdict = "FAUX_POSITIF_POTENTIEL"
        elif human_rejected_publication and not candidate_detected:
            # Une absence de sortie ne démontre pas que la publication
            # rejetée par l'audit humain a été vue puis écartée pour la
            # bonne raison : le document a pu ne pas être lu du tout.
            verdict = "REJET_NON_DEMONTRE_AUCUN_CANDIDAT_DETECTE"
        elif expected_status == "PUBLIE_INCOHERENT_NON_RETENU" and metrics.get("quarantine"):
            verdict = "NON_RETENU_POUR_INCOHERENCE_CONCORDANT"
        elif expected_status == "PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE" and (
            actual_status == sigma_collect.EPS_STATUS_PUBLISHED_NOT_RETAINED
            or metrics.get("nonretained_eps_observations")
            or metrics.get("quarantine")
            or other_scope_groups
        ):
            verdict = "PUBLIE_NON_RETENU_CONCORDANT"
        elif human_rejected_publication:
            verdict = "REJET_DETECTE_MAIS_MECANISME_NON_CONCORDANT"
        elif metrics.get("nonretained_eps_observations"):
            verdict = "ABSENCE_DE_VALEUR_RETENUE_AVEC_OBSERVATIONS_NON_RETENUES"
        else:
            verdict = "ABSENCE_DE_VALEUR_RETENUE_CONCORDANTE"

    expected_indicative = (expected.get("ratio_indicatif_fin_exercice") or {}).get("valeur_fcfa")
    actual_indicative = metrics.get("indicative_result_per_end_share_fcfa")
    if isinstance(expected_indicative, (int, float)):
        indicative_verdict = "CONCORDANT" if _close(actual_indicative, expected_indicative) else "NON_REPRODUIT_OU_DIVERGENT"
    else:
        indicative_verdict = "NON_ATTENDU"
    return {
        "verdict": verdict,
        "expected_value": expected_value,
        "actual_value": actual_value,
        "candidate_before_quarantine": candidate_value,
        "human_rejected_publication": human_rejected_publication,
        "candidate_detected": candidate_detected,
        "candidate_detection_sources": detection_sources,
        "indicative_verdict": indicative_verdict,
        "expected_indicative": expected_indicative,
        "actual_indicative": actual_indicative,
    }


def _selected_confirmation_count(metrics: dict[str, Any], figures: dict[str, Any]) -> int | None:
    selected = ((metrics.get("published_selection") or {}).get("group") or {})
    count = selected.get("documents_confirmants")
    if isinstance(count, int):
        return count
    figure = figures.get("benefice_par_action") or {}
    count = figure.get("documents_confirmants")
    return int(count) if isinstance(count, int) else None


def _build_outputs(
    document_results: list[dict[str, Any]],
    *,
    output_dir: Path,
    tickers: set[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decisions = _load_json(PILOT_DIR / "decisions.json")
    expected_rows = decisions.get("rows") or []
    if tickers:
        expected_rows = [row for row in expected_rows if row.get("ticker") in tickers]

    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in document_results:
        rows_by_ticker[str(row.get("ticker") or "")].append(row)

    capital_events = load_verified_capital_events()
    matrix: list[dict[str, Any]] = []
    ticker_summaries: dict[str, Any] = {}
    for ticker in sorted({row.get("ticker") for row in expected_rows}):
        series, per_share, notes = _aggregate_ticker(rows_by_ticker.get(str(ticker), []))
        figures_by_year = {
            entry["exercice"]: entry["figures"]
            for entry in series
            if isinstance(entry.get("exercice"), int)
        }
        ticker_summaries[str(ticker)] = {
            "series_exercices": sorted(figures_by_year),
            "aggregation_notes": notes,
            "per_share_observations": len(per_share),
        }
        for expected in [row for row in expected_rows if row.get("ticker") == ticker]:
            exercice = int(expected["exercice"])
            figures = figures_by_year.get(exercice) or {}
            metrics = derive_eps_metrics(
                figures,
                previous_figures=figures_by_year.get(exercice - 1) or {},
                exercice=exercice,
                ticker=str(ticker),
                capital_events=capital_events,
                eps_observations=[
                    item
                    for item in per_share
                    if item.get("family") == "eps" and item.get("target_exercice") == exercice
                ],
                reference_scope=REFERENCE_SCOPES.get(str(ticker)),
            )
            comparison = _compare_cell(expected, metrics)
            validation_level = "AUCUNE_VALEUR_RETENUE"
            if metrics.get("published_eps_fcfa") is not None:
                check = metrics.get("cross_check") or {}
                if _selected_confirmation_count(metrics, figures) and (_selected_confirmation_count(metrics, figures) or 0) >= 2:
                    validation_level = "DEUX_DOCUMENTS_DISTINCTS"
                elif check.get("concordant"):
                    validation_level = "CONTROLE_ARITHMETIQUE_CONCORDANT"
                elif metrics.get("status") == sigma_collect.EPS_STATUS_PUBLISHED_DIVERGENCE_RESOLVED:
                    validation_level = "DIVERGENCE_RESOLUE_PAR_CONTROLE"
                else:
                    validation_level = "EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE"
            matrix.append(
                {
                    "ticker": ticker,
                    "exercice": exercice,
                    "expected": {
                        "status": expected.get("statut_bpa"),
                        "documentary_status": expected.get("statut_documentaire"),
                        "retained_value_fcfa": (expected.get("bpa_retenu") or {}).get("valeur"),
                        "confirmations_documents_distincts": expected.get("confirmations_documents_distincts"),
                        "perimeter": expected.get("perimetre_retenu"),
                        "validation": expected.get("validation"),
                        "indicative_fcfa": (expected.get("ratio_indicatif_fin_exercice") or {}).get("valeur_fcfa"),
                    },
                    "actual": metrics,
                    "figures_present": sorted(figures),
                    "eps_figure": figures.get("benefice_par_action"),
                    "actual_confirmations_documents_distincts": _selected_confirmation_count(metrics, figures),
                    "validation_level": validation_level,
                    "comparison": comparison,
                }
            )

    verdict_counts = Counter(row["comparison"]["verdict"] for row in matrix)
    expected_retained = [row for row in matrix if isinstance(row["expected"]["retained_value_fcfa"], (int, float))]
    concordant_retained = [row for row in expected_retained if row["comparison"]["verdict"] == "VALEUR_CONCORDANTE"]
    false_positives = [row for row in matrix if row["comparison"]["verdict"] == "FAUX_POSITIF_POTENTIEL"]
    divergent = [row for row in matrix if row["comparison"]["verdict"] == "VALEUR_DIVERGENTE"]
    missing = [row for row in matrix if row["comparison"]["verdict"] in {"VALEUR_ATTENDUE_NON_TROUVEE", "VALEUR_TROUVEE_MAIS_QUARANTAINE_OU_NON_ELIGIBLE"}]
    extraction_unique = [
        row for row in concordant_retained if row["validation_level"] == "EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE"
    ]
    human_rejected = [
        row for row in matrix if row["comparison"].get("human_rejected_publication")
    ]
    human_rejected_concordant = [
        row
        for row in human_rejected
        if row["comparison"]["verdict"]
        in {"PUBLIE_NON_RETENU_CONCORDANT", "NON_RETENU_POUR_INCOHERENCE_CONCORDANT"}
    ]
    human_rejected_false_positives = [
        row for row in human_rejected if row["comparison"]["verdict"] == "FAUX_POSITIF_POTENTIEL"
    ]
    human_rejected_not_demonstrated = [
        row
        for row in human_rejected
        if row["comparison"]["verdict"]
        in {
            "REJET_NON_DEMONTRE_AUCUN_CANDIDAT_DETECTE",
            "REJET_DETECTE_MAIS_MECANISME_NON_CONCORDANT",
        }
    ]
    no_retained = [
        row for row in matrix if not isinstance(row["expected"]["retained_value_fcfa"], (int, float))
    ]
    false_positives_outside_human_rejected = [
        row for row in false_positives if row not in human_rejected_false_positives
    ]

    document_counts = {
        "documents_replayed": len(document_results),
        "documents_error": sum(1 for row in document_results if row.get("error")),
        "documents_sha256_matches_pilot": sum(1 for row in document_results if row.get("sha256_matches_pilot")),
        "documents_aggregable_annual_candidates": sum(1 for row in document_results if _is_aggregable(row)),
        "documents_rejected_other_issuer": sum(
            1
            for row in document_results
            if ((row.get("extraction") or {}).get("document") or {}).get("selection_rejection")
            == "AUTRE_EMETTEUR_CONFIRME"
        ),
        "documents_rejected_intermediate": sum(
            1
            for row in document_results
            if ((row.get("extraction") or {}).get("document") or {}).get("selection_rejection")
            == "INTERMEDIAIRE"
        ),
    }

    if (
        false_positives
        or divergent
        or missing
        or human_rejected_not_demonstrated
        or document_counts["documents_error"]
    ):
        gate = "EXTENSION_480_TOUJOURS_REFUSEE"
    elif extraction_unique:
        gate = "EXTENSION_480_REFUSEE_AVANT_REVUE_DES_EXTRACTIONS_UNIQUES"
    elif len(matrix) == 50 and len(concordant_retained) == len(expected_retained):
        gate = "REGRESSION_VALEURS_SATISFAISANTE_DECISION_HUMAINE_REQUISE_AVANT_480"
    else:
        gate = "REGRESSION_PARTIELLE_AUCUNE_EXTENSION"

    summary = {
        "cells": len(matrix),
        "expected_retained_values": len(expected_retained),
        "concordant_retained_values": len(concordant_retained),
        "missing_or_quarantined_expected_values": len(missing),
        "divergent_values": len(divergent),
        "potential_false_positives": len(false_positives),
        "negative_controls": {
            "human_cells_without_retained_eps": len(no_retained),
            "human_published_but_rejected": len(human_rejected),
            "human_rejected_concordant_demonstrated": len(human_rejected_concordant),
            "human_rejected_false_positives": len(human_rejected_false_positives),
            "human_rejected_not_demonstrated_or_wrong_mechanism": len(
                human_rejected_not_demonstrated
            ),
            "false_positives_on_absences_or_missing_documents": len(
                false_positives_outside_human_rejected
            ),
            "rule": (
                "Un rejet humain n'est concordant que si un candidat a été "
                "détecté puis non retenu ou mis en quarantaine pour une "
                "raison compatible ; une simple absence de sortie ne suffit pas."
            ),
        },
        "concordant_but_extraction_unique_without_weighted_check": len(extraction_unique),
        "verdicts": dict(sorted(verdict_counts.items())),
        "actual_statuses": dict(sorted(Counter(str(row["actual"].get("status")) for row in matrix).items())),
        "documents": document_counts,
        "by_ticker": {
            ticker: {
                "cells": sum(1 for row in matrix if row["ticker"] == ticker),
                "expected_retained": sum(
                    1 for row in matrix if row["ticker"] == ticker and isinstance(row["expected"]["retained_value_fcfa"], (int, float))
                ),
                "concordant_retained": sum(
                    1
                    for row in matrix
                    if row["ticker"] == ticker and row["comparison"]["verdict"] == "VALEUR_CONCORDANTE"
                ),
                "human_published_but_rejected": sum(
                    1
                    for row in matrix
                    if row["ticker"] == ticker and row["comparison"].get("human_rejected_publication")
                ),
                "human_rejected_concordant_demonstrated": sum(
                    1
                    for row in matrix
                    if row["ticker"] == ticker
                    and row["comparison"]["verdict"]
                    in {"PUBLIE_NON_RETENU_CONCORDANT", "NON_RETENU_POUR_INCOHERENCE_CONCORDANT"}
                ),
                "human_rejected_false_positives": sum(
                    1
                    for row in matrix
                    if row["ticker"] == ticker
                    and row["comparison"].get("human_rejected_publication")
                    and row["comparison"]["verdict"] == "FAUX_POSITIF_POTENTIEL"
                ),
                "verdicts": dict(
                    sorted(Counter(row["comparison"]["verdict"] for row in matrix if row["ticker"] == ticker).items())
                ),
                **ticker_summaries.get(str(ticker), {}),
            }
            for ticker in sorted({row["ticker"] for row in matrix})
        },
        "gate_480": gate,
        "code_fingerprint": _code_fingerprint(),
        "dataset_published_modified": False,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "regression_matrix.json", matrix)
    _write_json(output_dir / "summary.json", summary)
    with (output_dir / "regression_matrix.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "ticker",
                "exercice",
                "verdict",
                "valeur_attendue",
                "valeur_extraite_retenue",
                "candidat_avant_quarantaine",
                "statut_attendu",
                "statut_extrait",
                "validation_extraite",
                "confirmations_attendues",
                "confirmations_extraites",
                "ratio_indicatif_attendu",
                "ratio_indicatif_extrait",
                "verdict_ratio_indicatif",
            ],
        )
        writer.writeheader()
        for row in matrix:
            writer.writerow(
                {
                    "ticker": row["ticker"],
                    "exercice": row["exercice"],
                    "verdict": row["comparison"]["verdict"],
                    "valeur_attendue": row["expected"]["retained_value_fcfa"],
                    "valeur_extraite_retenue": row["actual"].get("published_eps_fcfa"),
                    "candidat_avant_quarantaine": row["comparison"]["candidate_before_quarantine"],
                    "statut_attendu": row["expected"]["status"],
                    "statut_extrait": row["actual"].get("status"),
                    "validation_extraite": row["validation_level"],
                    "confirmations_attendues": row["expected"]["confirmations_documents_distincts"],
                    "confirmations_extraites": row["actual_confirmations_documents_distincts"],
                    "ratio_indicatif_attendu": row["expected"]["indicative_fcfa"],
                    "ratio_indicatif_extrait": row["actual"].get("indicative_result_per_end_share_fcfa"),
                    "verdict_ratio_indicatif": row["comparison"]["indicative_verdict"],
                }
            )

    lines = [
        "# Régression du pilote BPA — extracteur corrigé",
        "",
        "Référence humaine : `audits/pilote_bpa_5/decisions.json` (50 cellules). "
        "Corpus rejoué : les documents déjà ouverts pendant le pilote, retéléchargés depuis leurs URL BRVM persistées. "
        "Aucune collecte complète et aucune réécriture du dataset publié.",
        "",
        f"- Cellules comparées : **{summary['cells']}**",
        f"- BPA FCFA attendus : **{summary['expected_retained_values']}** ; concordants : **{summary['concordant_retained_values']}**",
        f"- Attendus absents ou en quarantaine : **{summary['missing_or_quarantined_expected_values']}**",
        f"- Valeurs divergentes : **{summary['divergent_values']}** ; faux positifs potentiels : **{summary['potential_false_positives']}**",
        f"- Publications rejetées par l'audit humain : **{summary['negative_controls']['human_published_but_rejected']}** ; "
        f"rejets démontrés concordants : **{summary['negative_controls']['human_rejected_concordant_demonstrated']}** ; "
        f"faux positifs sur ces rejets : **{summary['negative_controls']['human_rejected_false_positives']}** ; "
        f"rejets non démontrés ou mauvais mécanisme : **{summary['negative_controls']['human_rejected_not_demonstrated_or_wrong_mechanism']}**",
        "- Un rejet n'est démontré que si le candidat a été détecté puis écarté pour une raison compatible ; une absence de sortie peut aussi signifier que le document n'a pas été lu.",
        f"- Concordants mais extraction unique sans contrôle pondéré : **{summary['concordant_but_extraction_unique_without_weighted_check']}**",
        f"- Documents rejoués : **{document_counts['documents_replayed']}** ; SHA-256 identiques au pilote : **{document_counts['documents_sha256_matches_pilot']}** ; erreurs : **{document_counts['documents_error']}**",
        f"- Porte 480 recalculée par le script : **{gate}**",
        "",
        "## Verdicts",
        "",
    ]
    for verdict, count in sorted(verdict_counts.items()):
        lines.append(f"- `{verdict}` : {count}")
    lines.extend(["", "## Cellules à examiner", ""])
    attention = [
        row
        for row in matrix
        if row["comparison"]["verdict"]
        not in {"VALEUR_CONCORDANTE", "ABSENCE_DE_VALEUR_RETENUE_CONCORDANTE", "PUBLIE_NON_RETENU_CONCORDANT", "NON_RETENU_POUR_INCOHERENCE_CONCORDANT"}
        or row["validation_level"] == "EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE"
    ]
    if attention:
        for row in attention:
            lines.append(
                f"- **{row['ticker']} {row['exercice']}** — `{row['comparison']['verdict']}` ; "
                f"attendu {row['expected']['retained_value_fcfa']} ; extrait {row['actual'].get('published_eps_fcfa')} ; "
                f"candidat {row['comparison']['candidate_before_quarantine']} ; validation `{row['validation_level']}`."
            )
    else:
        lines.append("- Aucune cellule divergente, absente ou en extraction unique non contrôlée.")
    lines.extend(
        [
            "",
            "Les détails par cellule sont dans `regression_matrix.json` et `regression_matrix.csv` ; "
            "les résultats document par document, empreintes comprises, sont dans `document_results.jsonl`.",
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return matrix, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", default="", help="Liste séparée par des virgules ; vide = cinq pilotes")
    parser.add_argument("--limit-docs", type=int, default=0, help="Diagnostic seulement : nombre maximal de PDF")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--force", action="store_true", help="Réextraire tous les PDF malgré le journal existant")
    parser.add_argument("--no-ocr", action="store_true", help="Désactiver le repli OCR contrôlé")
    args = parser.parse_args(argv)

    tickers = {item.strip().upper() for item in args.tickers.split(",") if item.strip()} or None
    documents = _pilot_documents(tickers)
    if args.limit_docs > 0:
        documents = documents[: args.limit_docs]
    results = _run_documents(
        documents,
        companies=_load_companies(),
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        force=args.force,
        allow_ocr=not args.no_ocr,
    )
    _matrix, summary = _build_outputs(results, output_dir=args.output_dir, tickers=tickers)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

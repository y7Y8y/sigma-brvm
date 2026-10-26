#!/usr/bin/env python3
"""Tri du reliquat BPA 480 : illisible, introuvable et non recherché.

Le script ne fait aucun réseau et ne modifie ni la matrice brute ni le
dataset. Il transforme les statuts bruts en causes actionnables à partir
des documents déjà inventoriés/ouverts par l'audit du 25 octobre.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
APP_ROOT = ROOT.parent.parent
AUDIT_DIR = APP_ROOT / "audits" / "audit_bpa_480_2016_2025_2026-10-25"
TARGET_STATUSES = {"ILLISIBLE", "DOCUMENT_INTROUVABLE", "NON_RECHERCHE"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def doc_summary(doc: dict[str, Any]) -> dict[str, Any]:
    ocr = doc.get("ocr") or {}
    return {
        "candidate_id": doc.get("candidate_id"),
        "label": doc.get("label"),
        "url": doc.get("url"),
        "sha256": doc.get("sha256"),
        "filename_exercice": doc.get("filename_exercice"),
        "effective_exercice": doc.get("effective_exercice"),
        "covers_target": doc.get("covers_target"),
        "readable": doc.get("readable"),
        "primary_financial_statements": doc.get("primary_financial_statements"),
        "native_text_characters": doc.get("native_text_characters"),
        "pages_total": doc.get("pages_total"),
        "pages_structured": doc.get("pages_structured"),
        "ocr_attempted": ocr.get("attempted"),
        "ocr_used": ocr.get("used"),
        "error": doc.get("error"),
    }


def classify(
    row: dict[str, Any],
    inventory_ticker: dict[str, Any],
    *,
    has_adjacent_evidence: bool = False,
) -> tuple[str, str, str]:
    status = row.get("statut_bpa")
    doc_status = row.get("statut_documentaire")
    year = int(row.get("exercice") or 0)
    opened = row.get("documents_ouverts_pertinents") or []
    covering = [doc for doc in opened if doc.get("covers_target")]
    unreadable_covering = [doc for doc in covering if not doc.get("readable")]
    if status == "NON_RECHERCHE" and doc_status == "CANDIDATS_INVENTORIES_NON_OUVERTS":
        return (
            "P1",
            "CANDIDATS_INVENTORIES_JAMAIS_OUVERTS",
            "Ouvrir les candidats inventoriés avec le parseur final ; aucun OCR avant cette lecture.",
        )
    if status == "NON_RECHERCHE" and doc_status == "DOCUMENTS_OUVERTS_SANS_ETAT_PRIMAIRE_PROUVE":
        return (
            "P2",
            "DOCUMENTS_OUVERTS_MAIS_ETAT_PRIMAIRE_NON_PROUVE",
            "Relire le contenu et la sélection documentaire ; ne pas conclure à une absence tant que l'état primaire n'est pas prouvé.",
        )
    if status == "NON_RECHERCHE":
        return (
            "P1",
            "AUCUN_DOCUMENT_SELECTIONNE_NE_COUVRE_L_EXERCICE",
            "Réinterroger l'inventaire complet et les pages émetteur ; chercher un document annuel couvrant l'exercice ou son comparatif N+1.",
        )
    if status == "DOCUMENT_INTROUVABLE":
        unique_pdfs = inventory_ticker.get("unique_pdf_count")
        exhaustive = inventory_ticker.get("inventory_exhaustive")
        if unique_pdfs is not None and unique_pdfs <= 5:
            return (
                "P1",
                "INVENTAIRE_EMETTEUR_ANORMALEMENT_PETIT_OU_MAL_RATTACHE",
                "Vérifier le slug/page BRVM et les anciens noms de l'émetteur avant toute conclusion d'introuvabilité.",
            )
        if exhaustive is False:
            return (
                "P1",
                "INVENTAIRE_NON_EXHAUSTIF",
                "Refaire un passage d'inventaire émetteur et contrôler la pagination avant de figer DOCUMENT_INTROUVABLE.",
            )
        return (
            "P2",
            "AUCUN_CANDIDAT_ANNUEL_DANS_INVENTAIRE_BRVM_VERIFIE",
            "Chercher une source officielle complémentaire émetteur/AMF-UMOA ; à défaut seulement, conserver DOCUMENT_INTROUVABLE.",
        )
    if status == "ILLISIBLE":
        # Pour un scan, `covers_target` reste souvent faux faute de texte.
        # L'intention de couverture se déduit donc prudemment de l'exercice
        # du document : N (document d'origine) ou N+1 (comparatif).
        intended_scanned = []
        for doc in opened:
            doc_year = doc.get("filename_exercice") or doc.get("effective_exercice")
            native = doc.get("native_text_characters") or 0
            if doc_year in {year, year + 1} and (not doc.get("readable") or native < 1000):
                intended_scanned.append(doc)
        if intended_scanned:
            min_pages = min(
                (doc.get("pages_total") or 999) for doc in intended_scanned
            )
            if min_pages <= 5 or (min_pages <= 20 and has_adjacent_evidence):
                return (
                    "P1",
                    "PDF_SCANNE_CIBLABLE_EXERCICE_OU_COMPARATIF",
                    "Rendre en images le document le plus court visant l'exercice ou son comparatif et contre-lire les pages BPA ; toute valeur OCR reste à confirmer.",
                )
            return (
                "P2",
                "DOCUMENT_LONG_SCANNE_OU_TEXTE_NATIF_FAIBLE",
                "Identifier d'abord les pages du compte de résultat/note BPA, puis OCR ciblé sur ces pages seulement.",
            )
        if unreadable_covering:
            return (
                "P2",
                "DOCUMENT_LONG_OU_TEXTE_NATIF_NON_EXPLOITABLE",
                "Identifier d'abord les pages du compte de résultat/note BPA, puis OCR ciblé sur ces pages seulement.",
            )
        return (
            "P2",
            "ILLISIBLE_SANS_DOCUMENT_COUVRANT_LISIBLE_IDENTIFIE",
            "Vérifier si un comparatif lisible N+1 existe avant OCR du document d'origine.",
        )
    return ("P3", "A_CLASSER", "Revue manuelle.")


def main() -> int:
    matrix = load_json(AUDIT_DIR / "matrix.json")
    inventory = load_json(AUDIT_DIR / "inventory.json")
    inventory_tickers = inventory.get("tickers") or {}

    evidence_by_ticker: dict[str, set[int]] = defaultdict(set)
    for row in matrix:
        if row.get("bpa_publie_fcfa") is not None or row.get("statut_bpa") in {
            "PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE",
            "PUBLIE_EN_QUARANTAINE_COHERENCE",
        }:
            evidence_by_ticker[row["ticker"]].add(int(row["exercice"]))

    records: list[dict[str, Any]] = []
    for row in matrix:
        if row.get("statut_bpa") not in TARGET_STATUSES:
            continue
        ticker = row["ticker"]
        year = int(row["exercice"])
        inv_ticker = inventory_tickers.get(ticker) or {}
        adjacent_evidence = sorted(
            y for y in evidence_by_ticker.get(ticker, set()) if abs(y - year) <= 2
        )
        priority, cause, next_action = classify(
            row,
            inv_ticker,
            has_adjacent_evidence=bool(adjacent_evidence),
        )
        opened = [doc_summary(doc) for doc in (row.get("documents_ouverts_pertinents") or [])]
        inventory_candidates = [
            {
                "candidate_id": doc.get("candidate_id"),
                "label": doc.get("label"),
                "url": doc.get("url"),
                "filename_exercice": doc.get("filename_exercice"),
            }
            for doc in (row.get("documents_candidats_inventories") or [])
        ]
        records.append(
            {
                "ticker": ticker,
                "company_name": row.get("company_name"),
                "exercice": year,
                "applicabilite": row.get("applicabilite"),
                "statut_bpa_brut": row.get("statut_bpa"),
                "statut_documentaire_brut": row.get("statut_documentaire"),
                "priority": priority,
                "cause_probable": cause,
                "next_action": next_action,
                "adjacent_years_with_eps_evidence": adjacent_evidence,
                "inventory_unique_pdf_count": inv_ticker.get("unique_pdf_count"),
                "inventory_exhaustive": inv_ticker.get("inventory_exhaustive"),
                "inventory_warnings": inv_ticker.get("warnings") or [],
                "documents_candidats_inventories_count": row.get(
                    "documents_candidats_inventories_count"
                ),
                "documents_selectionnes_count": row.get("documents_selectionnes_count"),
                "documents_primaires_lus_couvrant_exercice": row.get(
                    "documents_primaires_lus_couvrant_exercice"
                ),
                "documents_lus_couvrant_exercice": row.get(
                    "documents_lus_couvrant_exercice"
                ),
                "inventory_candidates": inventory_candidates,
                "opened_relevant_documents": opened,
            }
        )

    records.sort(key=lambda r: (r["priority"], r["statut_bpa_brut"], r["ticker"], r["exercice"]))
    summary = {
        "records": len(records),
        "by_raw_status": dict(Counter(r["statut_bpa_brut"] for r in records)),
        "by_priority": dict(Counter(r["priority"] for r in records)),
        "by_cause": dict(Counter(r["cause_probable"] for r in records)),
        "dataset_published_modified": False,
    }
    payload = {"summary": summary, "records": records}
    (ROOT / "backlog_triage.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fields = [
        "priority",
        "ticker",
        "exercice",
        "statut_bpa_brut",
        "statut_documentaire_brut",
        "cause_probable",
        "adjacent_years_with_eps_evidence",
        "inventory_unique_pdf_count",
        "inventory_exhaustive",
        "documents_candidats_inventories_count",
        "documents_selectionnes_count",
        "documents_primaires_lus_couvrant_exercice",
        "next_action",
    ]
    with (ROOT / "backlog_triage.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field) for field in fields}
            row["adjacent_years_with_eps_evidence"] = ";".join(
                str(y) for y in record["adjacent_years_with_eps_evidence"]
            )
            writer.writerow(row)

    lines = [
        "# Backlog BPA 480 — tri initial",
        "",
        f"Cellules : **{len(records)}** (ILLISIBLE, DOCUMENT_INTROUVABLE, NON_RECHERCHE).",
        "",
        "## Causes",
        "",
    ]
    for cause, count in Counter(r["cause_probable"] for r in records).most_common():
        lines.append(f"- `{cause}` : {count}")
    lines.extend(["", "## Priorité P1", ""])
    for record in records:
        if record["priority"] == "P1":
            lines.append(
                f"- **{record['ticker']} {record['exercice']}** — {record['cause_probable']} ; {record['next_action']}"
            )
    lines.extend(
        [
            "",
            "Les statuts ci-dessus restent des statuts bruts d'audit : ce tri ne",
            "transforme aucune absence en valeur et ne modifie pas le dataset.",
            "",
        ]
    )
    (ROOT / "BACKLOG_TRIAGE.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

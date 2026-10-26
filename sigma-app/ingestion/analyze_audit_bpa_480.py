#!/usr/bin/env python3
"""Revue et taux corrigés de l'audit BPA 480.

Le harnais `audit_bpa_480.py` produit une matrice brute en mode statuts
et preuves. Cette analyse séparée :

- recalcule les taux sur les seules cellules applicables (les exercices
  antérieurs à l'introduction sont présentés séparément) ;
- compare le sous-ensemble pilote aux décisions humaines fermées ;
- applique uniquement des décisions de revue explicites et vérifiées
  contre les preuves journalisées ;
- produit les files de revue prioritaires sans modifier la matrice
  brute, le journal d'extraction ni le dataset publié.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT_DIR = ROOT / "audits" / "audit_bpa_480_2016_2025_2026-10-25"
PILOT_DECISIONS = ROOT / "audits" / "pilote_bpa_5" / "decisions.json"
DATASET_PATH = ROOT / "web" / "data" / "data.json"

# Décisions prises après relecture des lignes de preuve journalisées.
# Le script échoue si la valeur brute ne correspond plus à celle relue.
REVIEW_DECISIONS: dict[tuple[str, int], dict[str, Any]] = {
    ("SPHC", 2020): {
        "expected_raw_value": -21.0,
        "review_status": "PUBLIE_NON_RETENU_APRES_REVUE_DATE_PRISE_POUR_VALEUR",
        "reason": (
            "La ligne de preuve est l'en-tête « Resultat par action 31-déc-21 31-déc-20 » : "
            "-21 provient du suffixe de date 31-déc-20, pas d'un montant par action."
        ),
        "next_action": "Corriger l'extracteur pour exclure les dates 31-déc-AA des slots de valeurs, puis rouvrir le document.",
    },
    ("SPHC", 2021): {
        "expected_raw_value": 31.0,
        "review_status": "PUBLIE_NON_RETENU_APRES_REVUE_DATE_PRISE_POUR_VALEUR",
        "reason": (
            "La ligne de preuve est l'en-tête « Resultat par action 31-déc-21 31-déc-20 » : "
            "31 est le jour de la date de clôture, pas un BPA."
        ),
        "next_action": "Corriger l'extracteur pour exclure les dates 31-déc-AA des slots de valeurs, puis rouvrir le document.",
    },
    ("TTLS", 2024): {
        "expected_raw_value": 128.0,
        "review_status": "PUBLIE_NON_RETENU_CONFLIT_PERIMETRE",
        "reason": (
            "La valeur retenue vient de la page 39 des états IFRS individuels, alors que la matrice "
            "la présente au périmètre consolidé ; la page 42 consolidée donne 219 FCFA pour 2024."
        ),
        "next_action": "Séparer les blocs individuels et consolidés d'un même rapport avant de retenir un BPA comparable.",
    },
    ("TTLS", 2025): {
        "expected_raw_value": 205.0,
        "review_status": "PUBLIE_NON_RETENU_CONFLIT_PERIMETRE",
        "reason": (
            "La valeur retenue vient de la page 39 des états IFRS individuels, alors que la matrice "
            "la présente au périmètre consolidé ; la page 42 consolidée donne 208 FCFA pour 2025."
        ),
        "next_action": "Séparer les blocs individuels et consolidés d'un même rapport avant de retenir un BPA comparable.",
    },
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 3) if denominator else None


def _pilot_expected_value(value: Any) -> float | None:
    if isinstance(value, dict):
        raw = value.get("valeur")
        return float(raw) if raw is not None else None
    return float(value) if value is not None else None


def _values_match(actual: Any, expected: float) -> bool:
    if actual is None:
        return False
    actual_float = float(actual)
    return abs(actual_float - expected) <= max(0.11, abs(expected) * 0.011)


def _journal_stats(path: Path) -> dict[str, Any]:
    rows = 0
    keys: set[tuple[str, str]] = set()
    errors: list[dict[str, Any]] = []
    sha_count = 0
    other_issuer = 0
    interim = 0
    methods: Counter[str] = Counter()
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            rows += 1
            keys.add((str(row.get("ticker") or ""), str(row.get("url") or "")))
            if row.get("document_sha256") or (row.get("extraction") or {}).get("sha256"):
                sha_count += 1
            if row.get("error"):
                errors.append(
                    {
                        "ticker": row.get("ticker"),
                        "label": (row.get("classified_document") or {}).get("label"),
                        "url": row.get("url"),
                        "error": str(row.get("error"))[:240],
                    }
                )
            document = ((row.get("extraction") or {}).get("document") or {})
            rejection = document.get("selection_rejection")
            if rejection == "AUTRE_EMETTEUR_CONFIRME":
                other_issuer += 1
            elif rejection == "INTERMEDIAIRE":
                interim += 1
            method = (((row.get("extraction") or {}).get("extraction") or {}).get("method"))
            methods[str(method)] += 1
            del row
    return {
        "rows": rows,
        "unique_ticker_url": len(keys),
        "with_sha256": sha_count,
        "errors_or_timeouts": errors,
        "rejected_other_issuer": other_issuer,
        "rejected_interim": interim,
        "extraction_methods": dict(sorted(methods.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    args = parser.parse_args()
    audit_dir: Path = args.audit_dir

    matrix = _load_json(audit_dir / "matrix.json")
    raw_summary = _load_json(audit_dir / "summary.json")
    journal = _journal_stats(audit_dir / "document_results.jsonl")
    pilot_rows = _load_json(PILOT_DECISIONS).get("rows") or []
    by_cell = {(row["ticker"], row["exercice"]): row for row in matrix}

    if len(matrix) != 480:
        raise SystemExit(f"Matrice inattendue : {len(matrix)} cellules au lieu de 480")
    if len(by_cell) != 480:
        raise SystemExit("Doublons société-exercice dans la matrice")

    # Vérification des décisions de revue explicites contre la matrice brute.
    reviewed: dict[tuple[str, int], dict[str, Any]] = {}
    for key, decision in REVIEW_DECISIONS.items():
        row = by_cell.get(key)
        if row is None:
            raise SystemExit(f"Cellule de revue absente : {key}")
        if row.get("bpa_publie_fcfa") != decision["expected_raw_value"]:
            raise SystemExit(
                f"Valeur brute inattendue pour {key} : {row.get('bpa_publie_fcfa')} "
                f"au lieu de {decision['expected_raw_value']}"
            )
        reviewed[key] = {
            "ticker": key[0],
            "exercice": key[1],
            "raw_status": row.get("statut_bpa"),
            "raw_value_fcfa": row.get("bpa_publie_fcfa"),
            "raw_validation_level": row.get("validation_level"),
            **decision,
        }

    def review_adjusted_published(row: dict[str, Any]) -> bool:
        return bool(
            row.get("bpa_publie_fcfa") is not None
            and (row["ticker"], row["exercice"]) not in reviewed
        )

    applicable = [row for row in matrix if row.get("applicabilite") == "APPLICABLE"]
    non_applicable = [row for row in matrix if row.get("applicabilite") != "APPLICABLE"]
    applicable_examined = [
        row for row in applicable if (row.get("documents_primaires_lus_couvrant_exercice") or 0) > 0
    ]
    applicable_series = [row for row in applicable if row.get("serie_extraite")]

    raw_published_applicable = [row for row in applicable if row.get("bpa_publie_fcfa") is not None]
    adjusted_published_applicable = [row for row in applicable if review_adjusted_published(row)]
    adjusted_confirmed = [
        row for row in adjusted_published_applicable if row.get("validation_level") == "DEUX_DOCUMENTS_DISTINCTS"
    ]
    adjusted_arithmetic_control = [
        row
        for row in adjusted_published_applicable
        if row.get("validation_level")
        in {"CONTROLE_ARITHMETIQUE_CONCORDANT", "DIVERGENCE_RESOLUE_PAR_CONTROLE"}
    ]
    adjusted_unique = [
        row
        for row in adjusted_published_applicable
        if row.get("validation_level") == "EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE"
    ]

    pilot_expected = 0
    pilot_matches = 0
    pilot_mismatches: list[dict[str, Any]] = []
    pilot_false_positives: list[dict[str, Any]] = []
    for decision in pilot_rows:
        key = (str(decision.get("ticker")), int(decision.get("exercice")))
        audit_row = by_cell[key]
        expected = _pilot_expected_value(decision.get("bpa_retenu"))
        if expected is not None:
            pilot_expected += 1
            if _values_match(audit_row.get("bpa_publie_fcfa"), expected):
                pilot_matches += 1
            else:
                pilot_mismatches.append(
                    {
                        "ticker": key[0],
                        "exercice": key[1],
                        "expected": expected,
                        "audit": audit_row.get("bpa_publie_fcfa"),
                        "audit_status": audit_row.get("statut_bpa"),
                    }
                )
        elif audit_row.get("bpa_publie_fcfa") is not None:
            pilot_false_positives.append(
                {
                    "ticker": key[0],
                    "exercice": key[1],
                    "audit": audit_row.get("bpa_publie_fcfa"),
                    "audit_status": audit_row.get("statut_bpa"),
                    "human_status": decision.get("statut_bpa"),
                }
            )

    def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        return dict(sorted(Counter(str(row.get("statut_bpa")) for row in rows).items()))

    def documentary_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        return dict(sorted(Counter(str(row.get("statut_documentaire")) for row in rows).items()))

    by_year: dict[str, Any] = {}
    for year in range(2016, 2026):
        rows = [row for row in applicable if row["exercice"] == year]
        examined = [row for row in rows if (row.get("documents_primaires_lus_couvrant_exercice") or 0) > 0]
        published = [row for row in rows if review_adjusted_published(row)]
        by_year[str(year)] = {
            "applicables": len(rows),
            "documents_primaires_lus": len(examined),
            "series_extraites": sum(1 for row in rows if row.get("serie_extraite")),
            "bpa_publies_retenus_apres_revue": len(published),
            "non_publies_sources_verifiees": sum(
                1 for row in rows if row.get("statut_bpa") == "NON_PUBLIE_DANS_SOURCES_VERIFIEES"
            ),
            "illisibles": sum(1 for row in rows if row.get("statut_bpa") == "ILLISIBLE"),
            "document_introuvable": sum(
                1 for row in rows if row.get("statut_bpa") == "DOCUMENT_INTROUVABLE"
            ),
            "non_recherches": sum(1 for row in rows if row.get("statut_bpa") == "NON_RECHERCHE"),
        }

    by_ticker: dict[str, Any] = {}
    for ticker in sorted({row["ticker"] for row in matrix}):
        rows = [row for row in applicable if row["ticker"] == ticker]
        if not rows:
            by_ticker[ticker] = {
                "applicables": 0,
                "note": "Aucune cellule 2016-2025 applicable après la date d'introduction vérifiée.",
            }
            continue
        by_ticker[ticker] = {
            "applicables": len(rows),
            "documents_primaires_lus": sum(
                1 for row in rows if (row.get("documents_primaires_lus_couvrant_exercice") or 0) > 0
            ),
            "series_extraites": sum(1 for row in rows if row.get("serie_extraite")),
            "bpa_publies_raw": sum(1 for row in rows if row.get("bpa_publie_fcfa") is not None),
            "bpa_publies_apres_revue": sum(1 for row in rows if review_adjusted_published(row)),
            "statuts_bpa": status_counts(rows),
        }

    quarantined = [
        row for row in applicable if row.get("statut_bpa") == "PUBLIE_EN_QUARANTAINE_COHERENCE"
    ]
    nonretained = [
        row
        for row in applicable
        if row.get("statut_bpa") == "PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE"
    ]
    indicative = [
        row for row in applicable if row.get("statut_bpa") == "RATIO_INDICATIF_FIN_EXERCICE"
    ]

    summary = {
        "schema_version": "sigma-audit-bpa-480-applicable-review-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "raw_summary_generated_at": raw_summary.get("generated_at"),
        "code_fingerprint_extraction": raw_summary.get("code_fingerprint"),
        "dataset_published_sha256": _sha256(DATASET_PATH),
        "dataset_published_modified": False,
        "cellules": {
            "brutes_48x10": len(matrix),
            "applicables_confirmees": len(applicable),
            "non_applicables_avant_introduction": len(non_applicable),
            "applicables_avec_document_primaire_lu": len(applicable_examined),
            "applicables_avec_serie_extraite": len(applicable_series),
            "taux_examen_primaire_sur_applicables_pct": _rate(
                len(applicable_examined), len(applicable)
            ),
            "taux_serie_sur_applicables_pct": _rate(len(applicable_series), len(applicable)),
        },
        "bpa_publie": {
            "raw_toutes_cellules": sum(1 for row in matrix if row.get("bpa_publie_fcfa") is not None),
            "raw_applicables": len(raw_published_applicable),
            "raw_avant_introduction": sum(
                1 for row in non_applicable if row.get("bpa_publie_fcfa") is not None
            ),
            "apres_revue_applicables": len(adjusted_published_applicable),
            "apres_revue_confirmes_deux_documents": len(adjusted_confirmed),
            "apres_revue_controle_arithmetique": len(adjusted_arithmetic_control),
            "apres_revue_extraction_unique_sans_controle_pondere": len(adjusted_unique),
            "taux_apres_revue_sur_applicables_pct": _rate(
                len(adjusted_published_applicable), len(applicable)
            ),
            "taux_apres_revue_sur_applicables_examinees_pct": _rate(
                len(adjusted_published_applicable), len(applicable_examined)
            ),
            "taux_confirmes_deux_documents_sur_applicables_examinees_pct": _rate(
                len(adjusted_confirmed), len(applicable_examined)
            ),
        },
        "bpa_recalcule_comparable_sans_publie_applicables": sum(
            1
            for row in applicable
            if row.get("bpa_publie_fcfa") is None
            and row.get("bpa_recalcule_comparable_fcfa") is not None
        ),
        "publications_detectees_non_retenues_applicables": len(nonretained),
        "quarantaines_applicables": len(quarantined),
        "ratios_indicatifs_fin_exercice_applicables": len(indicative),
        "statuts_bpa_applicables_raw": status_counts(applicable),
        "statuts_documentaires_applicables_raw": documentary_counts(applicable),
        "par_exercice_applicables": by_year,
        "par_ticker_applicables": by_ticker,
        "pilote_5_comparaison": {
            "cellules": len(pilot_rows),
            "valeurs_attendues": pilot_expected,
            "valeurs_concordantes": pilot_matches,
            "valeurs_divergentes_ou_manquantes": pilot_mismatches,
            "faux_positifs_sur_cellules_sans_valeur_humaine": pilot_false_positives,
        },
        "decisions_revue_preuves": list(reviewed.values()),
        "journal": journal,
        "avant_introduction_avec_bpa_publie_raw": [
            {
                "ticker": row["ticker"],
                "exercice": row["exercice"],
                "listing_date": row.get("listing_date"),
                "bpa_publie_fcfa_raw": row.get("bpa_publie_fcfa"),
                "statut_bpa_raw": row.get("statut_bpa"),
            }
            for row in non_applicable
            if row.get("bpa_publie_fcfa") is not None
        ],
        "decision": (
            "Audit 480 terminé en mode statuts et preuves. Aucune intégration au dataset publié "
            "n'est autorisée à ce stade : les extractions uniques, le conflit de périmètre TTLS, "
            "la quarantaine SDSC 2022, les publications non retenues et le backlog OCR doivent "
            "être traités séparément."
        ),
    }

    queue: list[dict[str, Any]] = []

    def add(priority: str, category: str, row: dict[str, Any], action: str) -> None:
        queue.append(
            {
                "priority": priority,
                "category": category,
                "ticker": row.get("ticker"),
                "exercice": row.get("exercice"),
                "raw_bpa_status": row.get("statut_bpa"),
                "raw_documentary_status": row.get("statut_documentaire"),
                "raw_published_eps_fcfa": row.get("bpa_publie_fcfa"),
                "candidate_before_quarantine_fcfa": row.get(
                    "bpa_publie_candidat_avant_quarantaine_fcfa"
                ),
                "validation_level": row.get("validation_level"),
                "next_action": action,
            }
        )

    for item in reviewed.values():
        row = by_cell[(item["ticker"], item["exercice"])]
        add("P0", "ANOMALIE_DE_PREUVE_CONFIRMEE", row, str(item["next_action"]))
    for row in quarantined:
        add(
            "P0",
            "QUARANTAINE_COHERENCE",
            row,
            "Relire la preuve et le contrôle pondéré ; ne pas substituer le ratio indicatif au BPA publié.",
        )
    for row in adjusted_unique:
        add(
            "P1",
            "EXTRACTION_UNIQUE_A_CONTRE_Lire",
            row,
            "Chercher un second document distinct ou un contrôle par numérateur attribuable et dénominateur moyen pondéré.",
        )
    for row in nonretained:
        add(
            "P1",
            "PUBLICATION_DETECTEE_NON_RETENUE",
            row,
            "Vérifier devise, composante poursuivie/arrêtée, périmètre et mention de base avant toute promotion.",
        )
    for row in applicable:
        if row.get("statut_bpa") == "ILLISIBLE":
            add(
                "P2",
                "DOCUMENT_ILLISIBLE_OCR",
                row,
                "OCR contrôlé ou second lecteur sur les états primaires scannés ; conserver ILLISIBLE en l'absence de lecture.",
            )
        elif row.get("statut_bpa") == "DOCUMENT_INTROUVABLE":
            add(
                "P2",
                "DOCUMENT_ANNUEL_INTROUVABLE_DANS_INVENTAIRE_BRVM",
                row,
                "Rechercher une source officielle complémentaire sans convertir l'absence BRVM en non-publication globale.",
            )
        elif row.get("statut_bpa") == "NON_RECHERCHE":
            add(
                "P2",
                "CELLULE_NON_RECHERCHEE",
                row,
                "Identifier un état primaire couvrant l'exercice ou conserver NON_RECHERCHE.",
            )

    queue.sort(key=lambda item: (item["priority"], item["category"], item["ticker"], item["exercice"]))
    fields = [
        "priority", "category", "ticker", "exercice", "raw_bpa_status",
        "raw_documentary_status", "raw_published_eps_fcfa",
        "candidate_before_quarantine_fcfa", "validation_level", "next_action",
    ]
    with (audit_dir / "review_queue.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: item.get(field) for field in fields} for item in queue)

    _write_json(audit_dir / "summary_applicable.json", summary)

    illisible_by_ticker = Counter(
        row["ticker"] for row in applicable if row.get("statut_bpa") == "ILLISIBLE"
    )
    introuvable_by_ticker = Counter(
        row["ticker"] for row in applicable if row.get("statut_bpa") == "DOCUMENT_INTROUVABLE"
    )
    nonrecherche_by_ticker = Counter(
        row["ticker"] for row in applicable if row.get("statut_bpa") == "NON_RECHERCHE"
    )
    nonretained_by_ticker = Counter(row["ticker"] for row in nonretained)

    lines = [
        "# Audit BPA 480 — revue, taux applicables et décision",
        "",
        f"Généré le {summary['generated_at']} à partir de la matrice brute du {raw_summary.get('generated_at')}.",
        "",
        "Aucune valeur de cet audit n'a été intégrée au dataset publié. "
        f"Empreinte du dataset relu : `{summary['dataset_published_sha256']}`.",
        "",
        "## Périmètre réel",
        "",
        f"- Cellules brutes 48 × 10 : **480**.",
        f"- Exercices avant introduction vérifiée : **{len(non_applicable)}** (`NON_APPLICABLE`).",
        f"- Cellules applicables : **{len(applicable)}**.",
        f"- Applicables avec au moins un document primaire lu couvrant l'exercice : **{len(applicable_examined)}** "
        f"({summary['cellules']['taux_examen_primaire_sur_applicables_pct']} %).",
        f"- Applicables avec série chiffrée extraite : **{len(applicable_series)}** "
        f"({summary['cellules']['taux_serie_sur_applicables_pct']} %).",
        f"- Documents inventoriés / candidats sélectionnés / résultats journalisés : "
        f"**3500 / 660 / {journal['rows']}** ; SHA-256 documentaire présent sur **{journal['with_sha256']}** résultats.",
        f"- Rejets de contenu : **{journal['rejected_other_issuer']}** autre émetteur, **{journal['rejected_interim']}** intermédiaires ; "
        f"**{len(journal['errors_or_timeouts'])}** timeouts isolés.",
        "",
        "## BPA publié : compteurs séparés",
        "",
        f"- Brut, toutes cellules : **{summary['bpa_publie']['raw_toutes_cellules']}**.",
        f"- Brut, cellules applicables : **{summary['bpa_publie']['raw_applicables']}**.",
        f"- Avant introduction, présenté séparément : **{summary['bpa_publie']['raw_avant_introduction']}** "
        "(ORGT 2018, exercice antérieur à la cotation du 16/04/2019).",
        f"- **Après revue des preuves, applicables : {summary['bpa_publie']['apres_revue_applicables']}**.",
        f"  - confirmés par deux documents distincts : **{summary['bpa_publie']['apres_revue_confirmes_deux_documents']}** ;",
        f"  - contrôle arithmétique concordant : **{summary['bpa_publie']['apres_revue_controle_arithmetique']}** ;",
        f"  - extraction unique sans contrôle pondéré : **{summary['bpa_publie']['apres_revue_extraction_unique_sans_controle_pondere']}**.",
        f"- Taux après revue : **{summary['bpa_publie']['taux_apres_revue_sur_applicables_pct']} %** des applicables et "
        f"**{summary['bpa_publie']['taux_apres_revue_sur_applicables_examinees_pct']} %** des applicables examinées.",
        f"- BPA recalculés comparables sans BPA publié : **{summary['bpa_recalcule_comparable_sans_publie_applicables']}**. "
        "Aucun ratio de fin d'exercice n'a été substitué.",
        f"- Publications détectées mais non retenues : **{len(nonretained)}** ; quarantaine : **{len(quarantined)}** ; "
        f"ratios indicatifs séparés : **{len(indicative)}**.",
        "",
        "## Contrôle sur le pilote déjà fermé",
        "",
        f"- Valeurs humaines attendues retrouvées : **{pilot_matches}/{pilot_expected}**.",
        f"- Faux positifs sur les cellules sans valeur humaine retenue : **{len(pilot_false_positives)}**.",
        "- Ce contrôle porte sur les valeurs ; certains libellés de statut de l'audit 480 sont plus prudents que ceux du pilote "
        "lorsqu'aucun état primaire n'a pu être prouvé dans le nouveau périmètre documentaire.",
        "",
        "## Anomalies de preuve confirmées par relecture",
        "",
    ]
    for item in reviewed.values():
        lines.append(
            f"- **{item['ticker']} {item['exercice']}** — brut {item['raw_value_fcfa']} FCFA, "
            f"revue `{item['review_status']}`. {item['reason']}"
        )
    lines.extend(
        [
            "",
            "Ces quatre cellules restent dans la matrice brute pour traçabilité, mais sont exclues des compteurs « après revue » ci-dessus.",
            "",
            "## Statuts des cellules applicables (matrice brute)",
            "",
            *[f"- BPA `{key}` : {value}" for key, value in status_counts(applicable).items()],
            "",
            *[f"- Documentaire `{key}` : {value}" for key, value in documentary_counts(applicable).items()],
            "",
            "## Backlogs documentaires",
            "",
            f"- `ILLISIBLE` : **{sum(illisible_by_ticker.values())}** cellules. Principaux émetteurs : "
            + ", ".join(f"{ticker} ({count})" for ticker, count in illisible_by_ticker.most_common(10))
            + ". La cause dominante est l'absence de texte natif exploitable dans des PDF scannés, sans OCR disponible dans l'environnement d'extraction.",
            f"- `DOCUMENT_INTROUVABLE` dans l'inventaire BRVM vérifié : **{sum(introuvable_by_ticker.values())}** cellules : "
            + ", ".join(f"{ticker} ({count})" for ticker, count in introuvable_by_ticker.most_common())
            + ".",
            f"- `NON_RECHERCHE` : **{sum(nonrecherche_by_ticker.values())}** cellules : "
            + ", ".join(f"{ticker} ({count})" for ticker, count in nonrecherche_by_ticker.most_common())
            + ". Aucune n'a été convertie en non-publication.",
            f"- Publications non retenues par émetteur : "
            + ", ".join(f"{ticker} ({count})" for ticker, count in nonretained_by_ticker.most_common())
            + ".",
            "",
            "## Décision",
            "",
            summary["decision"],
            "",
            "Ordre de traitement suivant :",
            "",
            "1. Corriger les deux défauts démontrés (dates prises pour des valeurs chez SPHC ; mélange individuel/consolidé chez TTLS), ajouter les tests et rejouer la régression pilote.",
            "2. Contre-lire les 18 extractions uniques restantes et la quarantaine SDSC 2022.",
            "3. Traiter le backlog OCR, en commençant par les banques BOA dont les états scannés bloquent des séries entières.",
            "4. Rechercher les documents annuels absents de l'inventaire BRVM (TTLS 2016-2022, CBIBF 2016-2019, SEMC/UNLC 2024-2025) dans des sources officielles complémentaires.",
            "5. Ne décider d'une intégration au dataset qu'après ces contrôles, cellule par cellule.",
            "",
            "Fichiers détaillés : `summary_applicable.json`, `review_queue.csv`, `matrix.json`, `matrix.csv`, `document_results.jsonl`, `inventory.json`, `candidate_plan.json` et `listing_dates_supplement_applied.json`.",
            "",
        ]
    )
    (audit_dir / "REVUE_AUDIT_480.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Preuves et garde-fous du moteur BPA de SIGMA.

Ce module est volontairement indépendant de la collecte réseau et de
pdfplumber. Il reçoit des pages déjà structurées (texte + lignes) et produit
des *observations* : valeur, devise, composante, périmètre, exercice visé,
page, ligne originale, contexte et règle d'extraction. Une observation
ambiguë reste visible pour l'audit, mais elle n'est pas promue en BPA FCFA
comparable.

L'ordre de traitement suit la décision du 24/10/2026 :
1. identité et sélection des documents ;
2. interprétation du BPA (colonnes, unités, devises, périmètres) ;
3. cohérence comptable et quarantaine ;
4. opérations sur le capital ;
5. traçabilité des preuves et des versions.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

EPS_PARSER_VERSION = "eps-evidence-v2.1.4"
DOCUMENT_CLASSIFIER_VERSION = "document-selection-v2.0.0"
CAPITAL_EVENT_SCHEMA_VERSION = 1

SCOPE_CONSOLIDATED = "CONSOLIDE"
SCOPE_INDIVIDUAL = "INDIVIDUEL"
SCOPE_SOCIAL = "SOCIAL"
SCOPE_MIXED = "MIXTE"
SCOPE_UNKNOWN = "NON_PROUVE"

COMPONENT_TOTAL = "TOTAL"
COMPONENT_TOTAL_EQUIVALENT = "TOTAL_EQUIVALENT_ARRETEES_NEANT_OU_ZERO"
COMPONENT_CONTINUING = "ACTIVITES_POURSUIVIES"
COMPONENT_DISCONTINUED = "ACTIVITES_ARRETEES_OU_EN_CESSION"
COMPONENT_UNKNOWN = "NON_PRECISE"

BASIS_BASIC = "DE_BASE"
BASIS_DILUTED = "DILUE"
BASIS_BASIC_AND_DILUTED = "DE_BASE_ET_DILUE_PRESENTES_ENSEMBLE"
BASIS_UNKNOWN = "NON_PRECISE"

CURRENCY_FCFA = "FCFA"
CURRENCY_USD_CENT = "USD_CENT"
CURRENCY_USD = "USD"
CURRENCY_UNKNOWN = "NON_PROUVEE"

ADJUSTABLE_CAPITAL_EVENT_TYPES = {
    "FRACTIONNEMENT",
    "REGROUPEMENT",
    "ACTIONS_GRATUITES",
    "ATTRIBUTION_GRATUITE",
    "BONUS_ISSUE",
    "DIVISION_DU_NOMINAL",
}


# ---------------------------------------------------------------------------
# Normalisation commune
# ---------------------------------------------------------------------------

def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ").replace("\u202f", " ")).strip()


def normalize_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _page_line_texts(page: dict[str, Any]) -> list[str]:
    lines = page.get("lines") or []
    texts: list[str] = []
    for line in lines:
        if isinstance(line, dict):
            texts.append(clean_text(line.get("text") or " ".join(str(w) for w in line.get("words") or [])))
        else:
            texts.append(clean_text(line))
    if not texts and page.get("text"):
        texts = [clean_text(line) for line in str(page["text"]).splitlines()]
    return [text for text in texts if text]


def _page_text(page: dict[str, Any]) -> str:
    return clean_text(page.get("text") or " ".join(_page_line_texts(page)))


def _page_number(page: dict[str, Any], fallback: int) -> int:
    value = page.get("page_number")
    return int(value) if isinstance(value, int) and value > 0 else fallback


# ---------------------------------------------------------------------------
# 1. Identité et sélection des documents
# ---------------------------------------------------------------------------

_INTERIM_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b30\s*(?:juin|06)\b", "30_JUIN"),
    (r"\b31\s*(?:mars|03)\b", "31_MARS"),
    (r"\b30\s*(?:septembre|09)\b", "30_SEPTEMBRE"),
    (r"\bsemestr(?:e|iel|ielle)\b", "SEMESTRE"),
    (r"\btrimestr(?:e|iel|ielle)\b", "TRIMESTRE"),
    (r"\bintermediaires?\b", "INTERMEDIAIRE"),
    (r"\bexamen limite\b", "EXAMEN_LIMITE"),
    (r"\bpremier semestre\b", "PREMIER_SEMESTRE"),
    (r"\b1er semestre\b", "PREMIER_SEMESTRE"),
)


def detect_interim_markers(value: Any) -> list[str]:
    """Marqueurs de période intermédiaire dans un nom ou un titre.

    Le cas mesuré au pilote est « états certifiés 30 juin » : l'ancien
    filtre cherchait le syntagme exact « au 30 juin » et laissait donc un
    semestre entrer dans la série annuelle.
    """
    normalized = normalize_key(value)
    found: list[str] = []
    for pattern, label in _INTERIM_PATTERNS:
        if re.search(pattern, normalized) and label not in found:
            found.append(label)
    # S1/T1 isolés dans un libellé financier. On évite les tickers et les
    # codes alphanumériques en exigeant un contexte de période ou d'activité.
    if re.search(r"\b(?:s|semestre)\s*1\b", normalized) and "SEMESTRE" not in found:
        found.append("SEMESTRE")
    if re.search(r"\b(?:t|trimestre)\s*[123]\b", normalized) and "TRIMESTRE" not in found:
        found.append("TRIMESTRE")
    return found


def _hint_from_markers(normalized: str, mapping: Iterable[tuple[str, tuple[str, ...]]]) -> tuple[str, list[str]]:
    hits: list[str] = []
    values: list[str] = []
    for value, markers in mapping:
        matched = [marker for marker in markers if marker in normalized]
        if matched:
            values.append(value)
            hits.extend(matched)
    if not values:
        return "NON_PROUVE", []
    if len(set(values)) > 1:
        return "MIXTE", hits
    return values[0], hits


def document_selection_metadata(label_or_filename: Any) -> dict[str, Any]:
    """Indices de sélection déduits du seul libellé/nom de fichier.

    Ces champs sont des *indices*. La classification de contenu, plus bas,
    Peut les confirmer ou les contredire ; aucun exercice n'est inventé.
    """
    normalized = normalize_key(label_or_filename)
    interim = detect_interim_markers(normalized)

    scope, scope_hits = _hint_from_markers(
        normalized,
        (
            (SCOPE_CONSOLIDATED, ("consolide", "consolides", "consolidated")),
            (SCOPE_INDIVIDUAL, ("individuel", "individuels", "separate financial")),
            (SCOPE_SOCIAL, ("sociaux", "social", "personnels", "personnel")),
        ),
    )
    framework, framework_hits = _hint_from_markers(
        normalized,
        (
            ("IFRS", ("ifrs",)),
            ("SYSCOHADA", ("syscohada",)),
            ("PCB_UMOA", ("pcb", "destine a publication")),
        ),
    )

    version_markers: list[str] = []
    version_rules = (
        ("CORRIGE", ("corrige", "corriges", "rectifie", "rectificatif")),
        ("RETRAITE", ("retraite", "retraites", "restated")),
        ("AUDITE_CERTIFIE_OU_APPROUVE", ("audite", "audites", "certifie", "certifies", "approuve", "approuves")),
        ("NON_AUDITE_OU_PROVISOIRE", ("non audite", "non audites", "provisoire", "provisoires", "unaudited")),
        ("CONDENSE", ("condense", "condenses", "condensed")),
        ("SYNTHESE", ("synthese",)),
    )
    for label, markers in version_rules:
        if any(marker in normalized for marker in markers):
            version_markers.append(label)
    version = version_markers[0] if version_markers else "NON_PRECISE"

    if interim:
        period_kind = "INTERMEDIAIRE"
        selection_status = "EXCLU_SERIE_ANNUELLE_INTERMEDIAIRE"
    elif any(marker in normalized for marker in ("31 decembre", "exercice", "annuel", "annual", "year ended")):
        period_kind = "ANNUEL_INDICE_PAR_LE_LIBELLE"
        selection_status = "CANDIDAT_ANNUEL_A_CONFIRMER_PAR_LE_CONTENU"
    else:
        period_kind = "NON_PROUVEE"
        selection_status = "A_CLASSER_PAR_LE_CONTENU"

    if "par secteur" in normalized:
        selection_status = "EXCLU_SERIE_GENERALE_DOCUMENT_SECTORIEL"
    if any(marker in normalized for marker in ("attestation des commissaires", "rapport des commissaires")) and "etats financiers" not in normalized:
        role = "RAPPORT_OU_ATTESTATION_CAC"
    elif "presentation" in normalized and "resultat" in normalized:
        role = "PRESENTATION_DE_RESULTATS"
    elif "rapport de gestion" in normalized or "synthese" in normalized:
        role = "SYNTHESE_OU_RAPPORT_DE_GESTION"
    elif any(marker in normalized for marker in ("etats financiers", "comptes consolides", "comptes individuels", "financial statements")):
        role = "ETATS_FINANCIERS"
    elif "rapport annuel" in normalized or "annual report" in normalized:
        role = "RAPPORT_ANNUEL"
    else:
        role = "AUTRE_A_CLASSER"

    return {
        "classifier_version": DOCUMENT_CLASSIFIER_VERSION,
        "period_kind": period_kind,
        "interim_markers": interim,
        "scope_hint": scope,
        "scope_hint_evidence": scope_hits,
        "framework_hint": framework,
        "framework_hint_evidence": framework_hits,
        "version_hint": version,
        "version_markers": version_markers,
        "content_role_hint": role,
        "selection_status": selection_status,
    }


def infer_report_doc_type(label_or_filename: Any, fallback: str = "autre") -> str:
    """Type documentaire fidèle, y compris les comptes IFRS classés autre."""
    normalized = normalize_key(label_or_filename)
    interim = detect_interim_markers(normalized)
    if "par secteur" in normalized and "etats financiers" in normalized:
        return "etats_financiers_par_secteur"
    if interim and any(marker in normalized for marker in ("etats", "comptes", "financial")):
        return "etats_financiers_intermediaires"
    if "semestre" in normalized:
        return "activite_semestrielle"
    if "trimestre" in normalized:
        return "activite_trimestrielle"
    if any(
        marker in normalized
        for marker in (
            "comptes consolides",
            "comptes individuels",
            "etats financiers consolides",
            "etats financiers individuels",
            "consolidated financial statements",
            "separate financial statements",
        )
    ):
        return "comptes_ifrs"
    if ("attestation" in normalized or "rapport des commissaires" in normalized) and "etats financiers" not in normalized:
        return "attestation_cac"
    if "presentation" in normalized and "resultat" in normalized:
        return "presentation_resultats"
    if "synthese" in normalized or "rapport de gestion" in normalized:
        return "synthese_rapport_gestion"
    if "etats financiers" in normalized and "approuv" in normalized:
        return "etats_financiers_approuves"
    if any(marker in normalized for marker in ("condense", "condensed")) and any(
        marker in normalized for marker in ("etats financiers", "comptes", "financial statements")
    ):
        return "etats_condenses"
    if "etats financiers" in normalized or "financial statements" in normalized:
        return "etats_financiers"
    if "rapport dactivites annuel" in normalized or "rapport d activites annuel" in normalized:
        return "rapport_activites_annuel"
    if "rapport annuel" in normalized or "annual report" in normalized or "financial report" in normalized:
        return "rapport_annuel"
    if "resultats consolides" in normalized:
        return "resultats_consolides"
    if "rse" in normalized:
        return "rse"
    return fallback


def _issuer_scores_in_text(text: str, aliases: dict[str, str]) -> tuple[Counter, list[dict[str, Any]]]:
    """Score les émetteurs connus, les phrases longues masquant les courtes.

    Sans masquage, « Ecobank Côte d'Ivoire » créditerait aussi un alias
    court d'Ecobank Transnational. Les phrases sont donc consommées de la
    plus longue à la plus courte dans chaque zone de texte.
    """
    working = f" {normalize_key(text)} "
    scores: Counter = Counter()
    evidence: list[dict[str, Any]] = []
    phrases = sorted(aliases.items(), key=lambda item: (-len(item[0].split()), -len(item[0])))
    for phrase, ticker in phrases:
        clean_phrase = normalize_key(phrase)
        if len(clean_phrase) < 3:
            continue
        token_count = len(clean_phrase.split())
        occurrences = working.count(f" {clean_phrase} ") + working.count(f" {clean_phrase}")
        if not occurrences:
            # Les titres collés par extraction (« ECOBANKCOTE ») restent
            # possibles en OCR ; on accepte alors la phrase complète sans
            # espaces uniquement pour les alias d'au moins deux mots.
            compact = clean_phrase.replace(" ", "")
            if token_count >= 2 and compact in working.replace(" ", ""):
                occurrences = 1
            else:
                continue
        capped = min(occurrences, 3)
        score = capped * (2 + token_count)
        scores[ticker] += score
        evidence.append({"phrase": clean_phrase, "ticker": ticker, "occurrences_capped": capped, "score": score})
        working = working.replace(clean_phrase, " ")
    return scores, evidence


def verify_document_issuer(
    pages: list[dict[str, Any]],
    expected_ticker: str | None,
    aliases: dict[str, str],
    filename: str = "",
) -> dict[str, Any]:
    """Vérifie l'émetteur dans le contenu, pas seulement la page source.

    Statuts :
    - ``AUTRE_EMETTEUR_CONFIRME`` : un autre émetteur coté domine nettement
      le titre/les premières pages ; le document doit être rejeté pour
      l'émetteur attendu.
    - ``CONFIRME_PAR_LE_CONTENU_OU_LE_NOM`` : l'émetteur attendu est le
      mieux établi.
    - ``AMBIGUE`` / ``NON_PROUVEE`` : aucune promotion silencieuse ; la
      décision appartient à la couche d'audit.
    """
    if not expected_ticker or not aliases:
        return {
            "status": "NON_PROUVEE",
            "expected_ticker": expected_ticker,
            "best_ticker": None,
            "scores": {},
            "evidence": [],
            "method": "alias_phrases_longues_d_abord",
            "classifier_version": DOCUMENT_CLASSIFIER_VERSION,
        }

    zones: list[tuple[str, int, str, int | None]] = []
    if filename:
        zones.append((filename, 3, "nom_fichier", None))
    for index, page in enumerate(pages[:5], start=1):
        lines = _page_line_texts(page)
        page_no = _page_number(page, index)
        if index == 1:
            zones.append((" ".join(lines[:18]), 4, "premiere_page_debut", page_no))
        zones.append((" ".join(lines[:5]), 2, "en_tetes_premieres_pages", page_no))
        zones.append((_page_text(page), 1, "texte_premieres_pages", page_no))

    total_scores: Counter = Counter()
    evidence: list[dict[str, Any]] = []
    strong_zones: set[str] = set()
    strong_phrase_zones: set[str] = set()
    for text, weight, zone, page_no in zones:
        scores, zone_evidence = _issuer_scores_in_text(text, aliases)
        for ticker, score in scores.items():
            total_scores[ticker] += score * weight
            if weight >= 3:
                strong_zones.add(ticker)
        for item in zone_evidence:
            if weight >= 3 and len(str(item.get("phrase") or "").split()) >= 2:
                strong_phrase_zones.add(str(item.get("ticker")))
            evidence.append({**item, "zone": zone, "page": page_no, "weight": weight, "weighted_score": item["score"] * weight})

    expected_score = int(total_scores.get(expected_ticker, 0))
    ranked = total_scores.most_common()
    best_ticker, best_score = ranked[0] if ranked else (None, 0)
    other_best_ticker, other_best_score = next(
        ((ticker, int(score)) for ticker, score in ranked if ticker != expected_ticker),
        (None, 0),
    )

    if (
        other_best_ticker
        and other_best_ticker in strong_zones
        and other_best_ticker in strong_phrase_zones
        and other_best_score >= 12
        and other_best_score >= expected_score + 8
    ):
        status = "AUTRE_EMETTEUR_CONFIRME"
    elif expected_score >= 8 and expected_score >= other_best_score:
        status = "CONFIRME_PAR_LE_CONTENU_OU_LE_NOM"
    elif expected_score or other_best_score:
        status = "AMBIGUE"
    else:
        status = "NON_PROUVEE"

    evidence.sort(key=lambda item: -int(item.get("weighted_score") or 0))
    return {
        "status": status,
        "expected_ticker": expected_ticker,
        "best_ticker": best_ticker,
        "expected_score": expected_score,
        "best_other_ticker": other_best_ticker,
        "best_other_score": int(other_best_score),
        "scores": {ticker: int(score) for ticker, score in ranked[:8]},
        "evidence": evidence[:10],
        "method": "alias_phrases_longues_d_abord_sur_nom_et_premieres_pages",
        "classifier_version": DOCUMENT_CLASSIFIER_VERSION,
    }


_SCOPE_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        SCOPE_CONSOLIDATED,
        (
            re.compile(
                r"\b(?:etats financiers|etats|comptes)"
                r"(?:\s+(?:ifrs|annuels?|audites?|certifies?|condenses?))*"
                r"\s+consolides?\b"
            ),
            re.compile(r"\bconsolidated financial statements\b"),
        ),
    ),
    (
        SCOPE_INDIVIDUAL,
        (
            re.compile(
                r"\b(?:etats financiers|etats|comptes)"
                r"(?:\s+(?:ifrs|annuels?|audites?|certifies?|condenses?))*"
                r"\s+individuels?\b"
            ),
            re.compile(r"\bseparate financial statements\b"),
        ),
    ),
    (
        SCOPE_SOCIAL,
        (
            re.compile(
                r"\b(?:etats financiers|etats|comptes)"
                r"(?:\s+(?:ifrs|annuels?|audites?|certifies?|condenses?))*"
                r"\s+(?:sociaux|sociales?|personnels?)\b"
            ),
            re.compile(r"\betats de synthese syscohada\b"),
        ),
    ),
)


def _scope_from_text(value: Any) -> tuple[str, list[str]]:
    normalized = normalize_key(value)
    found: list[str] = []
    hits: list[str] = []
    for scope, patterns in _SCOPE_PATTERNS:
        matched = [
            match.group(0)
            for pattern in patterns
            if (match := pattern.search(normalized)) is not None
        ]
        if matched:
            found.append(scope)
            hits.extend(matched)
    if not found:
        return SCOPE_UNKNOWN, []
    if len(set(found)) > 1:
        return SCOPE_MIXED, hits
    return found[0], hits


def _framework_from_text(value: Any) -> tuple[str, list[str]]:
    normalized = normalize_key(value)
    found: list[str] = []
    hits: list[str] = []
    for framework, markers in (
        ("IFRS", ("ifrs", "normes internationales d information financiere")),
        ("SYSCOHADA", ("syscohada", "systeme normal", "xb chiffre d affaires", "xi resultat net")),
        ("PCB_UMOA", ("destine a publication", "plan comptable bancaire")),
    ):
        matched = [marker for marker in markers if marker in normalized]
        if matched:
            found.append(framework)
            hits.extend(matched)
    if not found:
        return "NON_PROUVE", []
    if len(set(found)) > 1:
        return "MIXTE", hits
    return found[0], hits


def classify_page_accounting_contexts(pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Contexte comptable page par page et classification du contenu.

    Un même PDF Peut contenir des états personnels SYSCOHADA puis une
    partie consolidée IFRS (CIE 2023–2025). Le périmètre est donc rattaché
    à la page/section de la preuve, pas au seul nom du fichier.
    """
    contexts: list[dict[str, Any]] = []
    current_scope = SCOPE_UNKNOWN
    current_framework = "NON_PROUVE"
    scopes_present: set[str] = set()
    frameworks_present: set[str] = set()
    has_balance_sheet = False
    has_income_statement = False
    has_auditor_report = False
    numeric_pages = 0

    for index, page in enumerate(pages, start=1):
        lines = _page_line_texts(page)
        heading_text = " ".join(lines[:16])
        full_text = _page_text(page)
        scope, scope_hits = _scope_from_text(heading_text)
        if scope == SCOPE_UNKNOWN:
            # Un titre de section Peut se trouver un peu plus bas ; on ne
            # prend alors qu'une mention très explicite dans la page.
            scope, scope_hits = _scope_from_text(full_text[:2500])
        if scope != SCOPE_UNKNOWN and scope != SCOPE_MIXED:
            current_scope = scope
            scope_source = "PAGE_OU_SECTION"
        elif scope == SCOPE_MIXED:
            scope_source = "PAGE_MIXTE"
        else:
            scope = current_scope
            scope_source = "SECTION_PRECEDENTE" if current_scope != SCOPE_UNKNOWN else "AUCUNE"

        framework, framework_hits = _framework_from_text(heading_text)
        if framework == "NON_PROUVE":
            framework, framework_hits = _framework_from_text(full_text[:2500])
        if framework != "NON_PROUVE" and framework != "MIXTE":
            current_framework = framework
            framework_source = "PAGE_OU_SECTION"
        elif framework == "MIXTE":
            framework_source = "PAGE_MIXTE"
        else:
            framework = current_framework
            framework_source = "SECTION_PRECEDENTE" if current_framework != "NON_PROUVE" else "AUCUNE"

        normalized = normalize_key(full_text)
        statement_kinds: list[str] = []
        if any(marker in normalized for marker in ("bilan", "etat de la situation financiere", "statement of financial position")):
            statement_kinds.append("BILAN")
            has_balance_sheet = True
        if any(marker in normalized for marker in ("compte de resultat", "etat du resultat global", "statement of profit or loss", "income statement")):
            statement_kinds.append("COMPTE_DE_RESULTAT")
            has_income_statement = True
        if any(marker in normalized for marker in ("resultat par action", "benefice par action", "earnings per share")):
            statement_kinds.append("BPA_OU_NOTE_BPA")
        if any(marker in normalized for marker in ("rapport des commissaires aux comptes", "independent auditor", "opinion des commissaires")):
            statement_kinds.append("RAPPORT_CAC")
            has_auditor_report = True
        if any(marker in normalized for marker in ("sommaire", "table des matieres", "contents")) and index <= 12:
            statement_kinds.append("SOMMAIRE_POSSIBLE")

        numeric_lines = sum(1 for line in lines if len(re.findall(r"\d", line)) >= 4)
        if numeric_lines >= 3:
            numeric_pages += 1
        if scope not in {SCOPE_UNKNOWN, SCOPE_MIXED}:
            scopes_present.add(scope)
        if framework not in {"NON_PROUVE", "MIXTE"}:
            frameworks_present.add(framework)

        contexts.append(
            {
                "page": _page_number(page, index),
                "accounting_scope": scope,
                "accounting_scope_source": scope_source,
                "accounting_scope_evidence": scope_hits,
                "framework": framework,
                "framework_source": framework_source,
                "framework_evidence": framework_hits,
                "statement_kinds": statement_kinds,
                "heading_excerpt": clean_text(heading_text)[:320],
            }
        )

    has_primary = has_balance_sheet or has_income_statement
    auditor_report_without_statements = has_auditor_report and not has_primary
    summary = {
        "classifier_version": DOCUMENT_CLASSIFIER_VERSION,
        "scopes_present": sorted(scopes_present),
        "frameworks_present": sorted(frameworks_present),
        "has_primary_financial_statements": has_primary,
        "has_balance_sheet": has_balance_sheet,
        "has_income_statement": has_income_statement,
        "has_auditor_report": has_auditor_report,
        "auditor_report_without_detected_statements": auditor_report_without_statements,
        "numeric_pages": numeric_pages,
        "content_status": (
            "RAPPORT_CAC_SANS_ETATS_PRIMAIRES_DETECTES"
            if auditor_report_without_statements
            else "ETATS_PRIMAIRES_DETECTES"
            if has_primary
            else "CONTENU_FINANCIER_NON_PROUVE"
        ),
    }
    return contexts, summary


def detect_document_period(pages: list[dict[str, Any]], filename: str = "") -> dict[str, Any]:
    """Période du document : nom + titres des trois premières pages."""
    filename_markers = detect_interim_markers(filename)
    title_texts: list[str] = []
    for page in pages[:3]:
        title_texts.extend(_page_line_texts(page)[:12])
    content_markers = detect_interim_markers(" ".join(title_texts))
    markers = sorted(set(filename_markers + content_markers))
    return {
        "period_kind": "INTERMEDIAIRE" if markers else "ANNUEL_OU_NON_PROUVE",
        "interim_markers": markers,
        "filename_markers": filename_markers,
        "content_title_markers": content_markers,
        "selection_status": "EXCLU_SERIE_ANNUELLE_INTERMEDIAIRE" if markers else "CANDIDAT_ANNUEL_SOUS_RESERVE_DES_AUTRES_CONTROLES",
    }


def detect_document_fiscal_year(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Exercice de clôture lu dans le contenu (jamais la date du fichier)."""
    strong_candidates: Counter = Counter()
    weak_candidates: Counter = Counter()
    generic_candidates: Counter = Counter()
    evidence: list[dict[str, Any]] = []
    strong_patterns = (
        r"exercices?\s+clos\s+(?:le|les|au)\s+31\s+d[ée]cembre\s+(20\d{2})",
        r"(?:for the\s+)?year ended 31\s+december\s+(20\d{2})",
    )
    weak_pattern = r"au 31\s+d[ée]cembre\s+(20\d{2})"
    generic_pattern = r"exercice\s+(20\d{2})\b"

    def overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
        return any(span[0] < end and span[1] > start for start, end in spans)

    for index, page in enumerate(pages[:12], start=1):
        page_no = _page_number(page, index)
        for line in _page_line_texts(page)[:40]:
            strong_spans: list[tuple[int, int]] = []
            categorized: list[tuple[Counter, re.Match[str]]] = []
            for pattern in strong_patterns:
                for match in re.finditer(pattern, line, flags=re.I):
                    if overlaps(match.span(), strong_spans):
                        continue
                    strong_spans.append(match.span())
                    categorized.append((strong_candidates, match))
            for match in re.finditer(weak_pattern, line, flags=re.I):
                if not overlaps(match.span(), strong_spans):
                    categorized.append((weak_candidates, match))
            for match in re.finditer(generic_pattern, line, flags=re.I):
                categorized.append((generic_candidates, match))
            for target, match in categorized:
                year = int(match.group(1))
                if 1990 <= year <= 2099:
                    target[year] += 1
                    if len(evidence) < 5:
                        evidence.append({"page": page_no, "line": clean_text(line)[:260], "year": year})
    dated_candidates = strong_candidates + weak_candidates
    candidates = dated_candidates + generic_candidates
    if not candidates:
        # En-têtes de colonnes des états primaires des premières pages.
        years: Counter = Counter()
        for page in pages[:8]:
            detected = detect_column_years(_page_line_texts(page))
            if detected:
                years[max(detected["years"])] += 1
        if years:
            year = years.most_common(1)[0][0]
            return {"exercice": year, "status": "DEDUIT_DES_EN_TETES_DE_COLONNES", "evidence": evidence}
        return {"exercice": None, "status": "NON_PROUVE_PAR_LE_CONTENU", "evidence": []}
    # Hiérarchie des preuves, calibrée sur des cas réels :
    # - BOAS 2019 : une AG tenue en 2020 cite l'exercice 2020 en
    #   perspectives/indemnités, mais approuve les comptes *clos* au
    #   31/12/2019. Une année seulement générique ne doit donc jamais
    #   dépasser une année de clôture explicite.
    # - CFAC 2018 : une phrase comparative cite l'exercice clos 2017,
    #   alors que bilan et compte de résultat sont datés au 31/12/2018.
    #   Une année datée et corroborée peut donc dépasser la clôture
    #   comparative.
    # - CABC 2024 et SIBC 2019 : les mandats futurs citent même une
    #   clôture 2027, et les perspectives citent 2020. L'année la plus
    #   récente n'est donc pas un critère : dans le niveau retenu, on
    #   choisit l'année la plus fréquente, la plus récente seulement en
    #   cas d'égalité (N plutôt que le comparatif N-1, cas NSBC 2020).
    if strong_candidates:
        eligible_dated = [
            year
            for year, count in dated_candidates.items()
            if year in strong_candidates
            or count + generic_candidates.get(year, 0) >= 2
        ]
        year = max(
            eligible_dated, key=lambda y: (dated_candidates[y], y)
        )
    else:
        year = max(candidates, key=lambda y: (candidates[y], y))
    return {
        "exercice": year,
        "status": "LU_DANS_LE_CONTENU",
        "candidate_counts": {str(y): int(c) for y, c in sorted(candidates.items())},
        "closing_candidate_counts": {
            str(y): int(c) for y, c in sorted(strong_candidates.items())
        },
        "dated_candidate_counts": {
            str(y): int(c) for y, c in sorted(dated_candidates.items())
        },
        "generic_candidate_counts": {
            str(y): int(c) for y, c in sorted(generic_candidates.items())
        },
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# 2. Interprétation : colonnes, nombres, devises, composantes, périmètres
# ---------------------------------------------------------------------------

_DATE_YEAR_PATTERNS = (
    r"3[0-9](?:\s*/\s*12\s*/\s*|\s*[- ]\s*d[ée]c(?:embre)?\.?\s*[- ]\s*|\s+d[ée]cembre\s+)(20\d{2}|\d{2})(?!\d)",
    r"(?:janv?(?:ier)?|f[ée]vr?(?:ier)?|mars|avr(?:il)?|mai|juin|juil(?:let)?|ao[ûu]t|sept?(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?)\.?\s*(20\d{2})\b",
)


def _years_from_line(line: str) -> list[int]:
    years: list[int] = []
    for pattern in _DATE_YEAR_PATTERNS:
        for raw in re.findall(pattern, line, flags=re.I):
            value = int(raw)
            years.append(value if value >= 100 else 2000 + value)
    if years:
        return years
    tokens = line.split()
    alpha_words = sum(1 for token in tokens if re.search(r"[A-Za-zÀ-ÿ]{2,}", token))
    if alpha_words > 12:
        return []
    plain_years = [
        int(token.strip("()[]{}.,;:"))
        for token in tokens
        if re.fullmatch(r"20\d{2}", token.strip("()[]{}.,;:"))
    ]
    if plain_years:
        return plain_years
    # Certains PDF espacent les années d'en-tête (« 2 019 2 018 » ou
    # « 20 19 20 18 »). La séquence doit être toute la ligne (hors
    # séparateur « | ») : un téléphone « 20 20 00 00 ... 20 21 ... »
    # (cas réel SIBC) ou un montant groupé par milliers ne doit jamais
    # devenir une paire de colonnes 2020/2021.
    spaced_year = r"(?:2\s+0\d{2}|20\s+\d{2})"
    if not re.fullmatch(
        rf"{spaced_year}(?:\s*\|?\s+{spaced_year})+",
        line.strip(),
    ):
        return []
    spaced_years: list[int] = []
    for match in re.finditer(
        r"(?<!\d)(?:(20)\s+(\d{2})|2\s+(0\d{2}))(?!\d)",
        line,
    ):
        if match.group(1):
            spaced_years.append(int(match.group(1) + match.group(2)))
        else:
            spaced_years.append(int("2" + match.group(3)))
    return spaced_years


def _is_consecutive_year_sequence(years: list[int]) -> bool:
    if len(years) < 2 or len(set(years)) != len(years):
        return False
    differences = {b - a for a, b in zip(years, years[1:])}
    return differences in ({1}, {-1})


def _is_publication_date_line(line: str) -> bool:
    """Date de couverture/publication, à ne jamais lire comme colonne.

    Les en-têtes légitimes « 31 décembre 2025 / 31 décembre 2024 »
    restent acceptés ; « Février 2025 » ou « 16 février 2026 » sont des
    dates de publication et ne prouvent aucun exercice de colonne.
    """
    normalized = normalize_key(line)
    months = (
        "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre",
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november",
    )
    if any(re.search(rf"\b{month}\b", normalized) for month in months):
        return True
    if "decembre" in normalized or "december" in normalized:
        # Seule la clôture explicite au 31 est un en-tête d'exercice.
        return not bool(re.search(r"\b31\s+(?:decembre|december)\b|(?:december)\s+31\b", normalized))
    return False


def detect_column_years(lines: list[str], max_lines: int = 30) -> dict[str, Any] | None:
    """Années des colonnes lues dans l'en-tête, jamais supposées par l'ordre.

    Retourne par exemple [2025, 2024, 2023] pour un tableau à trois
    exercices. Les lignes de sommaire et les ratios « variation 2025/2024 »
    sont ignorés.
    """
    candidates: list[dict[str, Any]] = []
    usable = [clean_text(line) for line in lines[:max_lines]]
    for index, line in enumerate(usable):
        if _is_table_of_contents_line(line) or _is_publication_date_line(line):
            continue
        normalized = normalize_key(line)
        years = _years_from_line(line)
        if len(years) >= 2 and _is_consecutive_year_sequence(years):
            between = line
            if "variation" in normalized and "/" in between:
                continue
            candidates.append({"years": years[:5], "evidence_line": line, "line_index": index, "source": "EN_TETE_MEME_LIGNE"})
    if candidates:
        # L'en-tête le plus complet et le plus haut dans la fenêtre.
        candidates.sort(key=lambda item: (-len(item["years"]), item["line_index"]))
        return candidates[0]

    # En-têtes éclatés sur deux ou trois lignes courtes (« 31/12/2025 » puis
    # « 31/12/2024 »). On n'assemble que des lignes d'en-tête courtes.
    for start in range(min(len(usable), 20)):
        years: list[int] = []
        evidence: list[str] = []
        for line in usable[start:start + 3]:
            if (
                len(line.split()) > 10
                or _is_table_of_contents_line(line)
                or _is_publication_date_line(line)
            ):
                continue
            found = _years_from_line(line)
            if found:
                years.extend(found)
                evidence.append(line)
            if len(years) >= 2 and _is_consecutive_year_sequence(years):
                return {
                    "years": years[:5],
                    "evidence_line": " | ".join(evidence),
                    "line_index": start,
                    "source": "EN_TETE_SUR_PLUSIEURS_LIGNES",
                }
    return None


def _is_table_of_contents_line(line: str) -> bool:
    text = clean_text(line)
    if text.count(".") >= 8 and re.search(r"\.{5,}", text):
        return True
    normalized = normalize_key(text)
    return bool(
        re.search(r"\b(?:note|chapitre)\s+\d+(?:\.\d+)?\b.*\b\d{1,3}$", normalized)
        and text.count(".") >= 4
    )


def parse_eps_number(raw: str, *, integer_thousands: bool = False) -> tuple[float | None, int]:
    """Parse un nombre BPA/actions FR/EN, espaces autour du séparateur inclus."""
    text = clean_text(raw).strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = text.replace("\u2212", "-")
    if text.startswith("-"):
        negative = True
        text = text[1:]
    text = re.sub(r"\s+", "", text)
    if not text or not re.search(r"\d", text):
        return None, 0

    decimals = 0
    # Groupes de milliers anglais complets : 24,592,619 ou 1,234,567.89.
    if re.fullmatch(r"\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?", text):
        if "." in text:
            decimals = len(text.rsplit(".", 1)[1])
        text = text.replace(",", "")
    elif "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            decimals = len(text.rsplit(",", 1)[1])
            text = text.replace(".", "").replace(",", ".")
        else:
            decimals = len(text.rsplit(".", 1)[1])
            text = text.replace(",", "")
    elif "," in text:
        left, right = text.rsplit(",", 1)
        if integer_thousands and len(right) == 3 and left.isdigit() and right.isdigit():
            text = left + right
        else:
            decimals = len(right)
            text = left + "." + right
    elif "." in text:
        # Un point de milliers français éventuel (1.234.567) n'est pas une
        # décimale ; un seul point est lu comme séparateur décimal anglais,
        # indispensable pour ETIT (1.68) et distinct d'une référence 9.2
        # grâce au contexte de ligne géré par l'appelant.
        if re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}", text):
            text = text.replace(".", "")
        else:
            decimals = len(text.rsplit(".", 1)[1])
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None, 0
    value = float(text)
    return (-value if negative else value), decimals


_NUMBER_TOKEN_RE = re.compile(
    r"\(?-?\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?\)?"
    r"|\(?-?\d{1,3}(?:[ \u202f\u00a0]\d{3})+(?:\s*[,.]\s*\d+)?\)?"
    r"|\(?-?\d+(?:\s*[,.]\s*\d+)?\)?"
)


_MONTH_TOKEN_RE = (
    r"(?:janv(?:ier)?|fevr(?:ier)?|mars|avr(?:il)?|mai|juin|juil(?:let)?|aout|"
    r"sept?(?:embre)?|oct(?:obre)?|nov(?:embre)?|dec(?:embre)?|"
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATE_SEPARATOR_RE = r"(?:\s*[-/]+\s*|\s+)"
_DATE_SPAN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "DAY_MONTH",
        re.compile(
            rf"\b(?P<day>\d{{1,2}}){_DATE_SEPARATOR_RE}{_MONTH_TOKEN_RE}\b"
            rf"(?:{_DATE_SEPARATOR_RE}(?P<year>\d{{4}}|\d{{2}})\b)?"
        ),
    ),
    (
        "MONTH_DAY",
        re.compile(
            rf"\b{_MONTH_TOKEN_RE}\b{_DATE_SEPARATOR_RE}(?P<day>\d{{1,2}})\b"
            rf"(?:{_DATE_SEPARATOR_RE}(?P<year>\d{{4}}|\d{{2}})\b)?"
        ),
    ),
    (
        "MONTH_YEAR",
        re.compile(rf"\b{_MONTH_TOKEN_RE}\b{_DATE_SEPARATOR_RE}(?P<year>\d{{4}}|\d{{2}})\b"),
    ),
    (
        "NUMERIC",
        re.compile(
            r"\b(?P<first>\d{1,2})\s*[-/]+\s*(?P<second>\d{1,2})"
            r"\s*[-/]+\s*(?P<year>\d{4}|\d{2})\b"
        ),
    ),
    (
        "ISO",
        re.compile(
            r"\b(?P<year>\d{4})\s*[-/]+\s*(?P<month>\d{1,2})"
            r"\s*[-/]+\s*(?P<day>\d{1,2})\b"
        ),
    ),
)


def _date_match_view(text: str) -> str:
    """Vue normalisée de même longueur, pour repérer les dates sans décaler.

    Les accents sont retirés caractère par caractère et les séparateurs de
    date sont ramenés à ``-``/``/``. Les positions restent donc alignées
    avec le texte original, ce qui permet de marquer les jetons numériques
    qui appartiennent à une date au lieu d'une valeur.
    """
    chars: list[str] = []
    for char in text or "":
        decomposed = unicodedata.normalize("NFKD", char.lower())
        base = next((piece for piece in decomposed if not unicodedata.combining(piece)), " ")
        if base.isalnum():
            chars.append(base)
        elif char == "/":
            chars.append("/")
        elif char in "-–—._":
            chars.append("-")
        else:
            chars.append(" ")
    return "".join(chars)


def _valid_date_match(kind: str, match: re.Match[str]) -> bool:
    values = match.groupdict()
    if kind in {"DAY_MONTH", "MONTH_DAY"}:
        return 1 <= int(values["day"]) <= 31
    if kind == "NUMERIC":
        first = int(values["first"])
        second = int(values["second"])
        return (1 <= first <= 31 and 1 <= second <= 12) or (
            1 <= first <= 12 and 1 <= second <= 31
        )
    if kind == "ISO":
        return 1 <= int(values["month"]) <= 12 and 1 <= int(values["day"]) <= 31
    return True


def _date_match_is_value_fragment(text: str, match: re.Match[str]) -> bool:
    """Écarte les pseudo-dates formées par des valeurs et variations.

    Cas réel ETIT : « 4 ,11 -5% -11% » contient la suite 11/5/11 dans la
    vue normalisée. Ce n'est pas une date : le premier groupe est la
    partie décimale de 4,11 et les suivants sont des variations en %.
    """
    if "%" in text[match.start():match.end()]:
        return True
    before = text[:match.start()].rstrip()
    if before and before[-1] in ",.":
        head = before[:-1].rstrip()
        if head and head[-1].isdigit():
            return True
    return False


def _date_spans(text: str) -> list[tuple[int, int]]:
    view = _date_match_view(text)
    spans: list[tuple[int, int]] = []
    for kind, pattern in _DATE_SPAN_PATTERNS:
        for match in pattern.finditer(view):
            if _valid_date_match(kind, match) and not _date_match_is_value_fragment(
                text, match
            ):
                spans.append((match.start(), match.end()))
    return spans


def _overlaps_date_span(start: int, end: int, spans: Iterable[tuple[int, int]]) -> bool:
    return any(start < span_end and end > span_start for span_start, span_end in spans)


def extract_numeric_tokens(text: str, *, integer_thousands: bool = False) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    date_spans = _date_spans(text or "")
    for match in _NUMBER_TOKEN_RE.finditer(text or ""):
        raw = match.group(0).strip()
        if not raw:
            continue
        following = (text[match.end():match.end() + 3] or "").lstrip()
        value, decimals = parse_eps_number(raw, integer_thousands=integer_thousands)
        if value is None:
            continue
        tokens.append(
            {
                "raw": raw,
                "normalized_raw": re.sub(r"\s*([,.])\s*", r"\1", raw),
                "value": value,
                "decimals": decimals,
                "start": match.start(),
                "end": match.end(),
                "is_percent": following.startswith("%"),
                "is_date": _overlaps_date_span(match.start(), match.end(), date_spans),
            }
        )
    return tokens


def _numeric_segment(text: str, start: int) -> str:
    """Segment numérique après un libellé, arrêté au libellé suivant.

    Certaines lignes PDF fusionnent deux tableaux côte à côte : après les
    deux BPA commence un autre libellé (« Comptes courants… ») suivi de ses
    propres montants. On coupe dès deux mots alphabétiques non unitaires
    consécutifs après le premier nombre.
    """
    segment = (text or "")[start:]
    allowed = {
        "fcfa", "franc", "francs", "cfa", "cents", "cent", "usd", "dollar", "dollars", "eu", "xof",
        "actions", "action", "titres", "titre", "milliers", "millions", "milliards", "thousands", "millions",
        "de", "des", "du", "en", "par", "au", "aux", "a", "et", "note", "notes",
    }
    seen_number = False
    alpha_run = 0
    alpha_start: int | None = None
    for match in re.finditer(r"\S+", segment):
        token = match.group(0)
        normalized = normalize_key(token)
        if re.search(r"\d", token):
            seen_number = True
            alpha_run = 0
            alpha_start = None
            continue
        if not seen_number:
            continue
        if normalized in allowed or not re.search(r"[a-z]{2,}", normalized):
            alpha_run = 0
            alpha_start = None
            continue
        if alpha_start is None:
            alpha_start = match.start()
        alpha_run += 1
        if alpha_run >= 2 and alpha_start is not None:
            return segment[:alpha_start].strip()
    return segment.strip()


def _date_word_indexes(words: list[str]) -> set[int]:
    """Indexes des mots appartenant à une date dans une ligne structurée."""
    if not words:
        return set()
    offsets: list[tuple[int, int]] = []
    position = 0
    for word in words:
        offsets.append((position, position + len(word)))
        position += len(word) + 1
    spans = _date_spans(" ".join(words))
    return {
        index
        for index, (start, end) in enumerate(offsets)
        if _overlaps_date_span(start, end, spans)
    }


def _structured_slots(
    line_object: dict[str, Any] | None,
    text: str,
    start: int,
) -> list[dict[str, Any]] | None:
    """Colonnes déjà regroupées par coordonnées dans la ligne structurée.

    Le texte seul ne distingue pas « 100 000 000 | 100 000 000 » (deux
    colonnes) d'un seul nombre fragmenté. Quand pdfplumber/OCR a fourni
    les montants regroupés par écarts horizontaux, ce sont eux qui font
    foi. Le repli texte reste indispensable pour les décimales espacées
    d'ETIT, que le regroupement historique peut tronquer.
    """
    if not isinstance(line_object, dict):
        return None
    amounts = line_object.get("amounts") or []
    words = [str(word) for word in line_object.get("words") or []]
    if not amounts or not words:
        return None
    date_word_indexes = _date_word_indexes(words)
    segment = _numeric_segment(text, start)
    # Décimale espacée ou double devise : le regroupement historique a pu
    # lire « 1 » au lieu de « 1 ,170 ». Le parseur texte dédié prime alors.
    if re.search(r"\d\s*[,.]\s*\d", segment):
        return None
    label_word_count = len([word for word in text[:start].split(" ") if word])
    # Même coupure que le parseur texte : les montants structurés situés
    # après un second libellé de tableau côte à côte n'appartiennent pas
    # à la ligne BPA (« 307 140 Comptes courants… -299 0 »).
    segment_word_limit = label_word_count + len(segment.split())
    indexed: list[tuple[int, float]] = []
    for item in amounts:
        try:
            word_index, value = item
            word_index = int(word_index)
            value = float(value)
        except (TypeError, ValueError):
            continue
        if label_word_count <= word_index < segment_word_limit:
            indexed.append((word_index, value))
    if not indexed:
        return None
    indexed.sort()
    slots: list[dict[str, Any]] = []
    previous_index = label_word_count
    for position, (word_index, value) in enumerate(indexed):
        between = words[previous_index:word_index]
        if any(token.strip() in {"-", "–", "—"} for token in between):
            slots.append(
                {
                    "raw": "-",
                    "normalized_raw": "-",
                    "value": None,
                    "decimals": 0,
                    "start": previous_index,
                    "end": word_index,
                    "is_percent": False,
                    "is_dash": True,
                    "is_date": False,
                    "structured": True,
                }
            )
        next_index = indexed[position + 1][0] if position + 1 < len(indexed) else len(words)
        raw = " ".join(words[word_index:next_index]).strip()
        # Ne conserver que le début numérique du segment brut.
        raw_match = _NUMBER_TOKEN_RE.search(raw)
        raw_token = raw_match.group(0) if raw_match else str(value)
        _parsed, decimals = parse_eps_number(raw_token)
        slots.append(
            {
                "raw": raw_token,
                "normalized_raw": re.sub(r"\s*([,.])\s*", r"\1", raw_token),
                "value": value,
                "decimals": decimals,
                "start": word_index,
                "end": next_index,
                "is_percent": False,
                "is_dash": False,
                "is_date": word_index in date_word_indexes,
                "structured": True,
            }
        )
        previous_index = word_index + 1
    return slots


def _value_slots(
    text: str,
    start: int,
    *,
    integer_thousands: bool = False,
    line_object: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    structured = _structured_slots(line_object, text, start)
    if structured is not None:
        return structured
    segment = _numeric_segment(text, start)
    slots: list[dict[str, Any]] = []
    for token in extract_numeric_tokens(segment, integer_thousands=integer_thousands):
        if token.get("is_percent"):
            break
        slots.append({**token, "is_dash": False})
    first_numeric_start = min((int(slot.get("start") or 0) for slot in slots), default=None)
    for match in re.finditer(r"(?<![\w])[-–—](?![\w])", segment):
        # Un tiret de puce en tête (« - dilué … ») n'est pas une colonne.
        # En l'absence de nombre, les tirets du segment sont au contraire
        # les colonnes néant du tableau (« de base - - »).
        if first_numeric_start is None or match.start() > first_numeric_start:
            slots.append(
                {
                    "raw": match.group(0),
                    "normalized_raw": match.group(0),
                    "value": None,
                    "decimals": 0,
                    "start": match.start(),
                    "end": match.end(),
                    "is_percent": False,
                    "is_dash": True,
                }
            )
    slots.sort(key=lambda item: int(item.get("start") or 0))
    return slots


def _filter_note_ref_and_years(slots: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    reasons: list[str] = []
    filtered: list[dict[str, Any]] = []
    for slot in slots:
        if slot.get("is_date"):
            if "DATE_D_EN_TETE_IGNOREE" not in reasons:
                reasons.append("DATE_D_EN_TETE_IGNOREE")
            continue
        if slot.get("is_percent"):
            continue
        filtered.append(slot)
    # Années d'en-tête accolées au libellé : ce ne sont pas des valeurs.
    non_year = []
    for slot in filtered:
        value = slot.get("value")
        raw = str(slot.get("normalized_raw") or "")
        raw_compact = re.sub(r"[\s\u202f\u00a0]+", "", raw).strip("()")
        if isinstance(value, (int, float)) and float(value).is_integer() and 1990 <= value <= 2099 and raw_compact == str(int(value)):
            reasons.append("ANNEE_D_EN_TETE_IGNOREE")
            continue
        non_year.append(slot)
    filtered = non_year
    if filtered:
        first = filtered[0]
        raw = str(first.get("normalized_raw") or "").strip("()")
        value = first.get("value")
        # Référence de note de type 9.2 / 8.2 (un seul chiffre après le
        # point) ou petit entier de note avant au moins une vraie valeur.
        # 1.68 garde deux décimales et n'est donc pas écarté par cette règle.
        if re.fullmatch(r"\d{1,2}\.\d", raw) and len(filtered) >= 2:
            reasons.append("REFERENCE_DE_NOTE_IGNOREE")
            filtered = filtered[1:]
        elif (
            isinstance(value, (int, float))
            and float(value).is_integer()
            and 1 <= value <= 30
            and raw == str(int(value))
            and len(filtered) >= 3
        ):
            reasons.append("NUMERO_DE_NOTE_POSSIBLE_IGNORE")
            filtered = filtered[1:]
    return filtered, reasons


def _detect_basis(value: Any) -> str:
    normalized = normalize_key(value)
    # « Non dilué » est la présentation de base, pas une mention positive
    # de dilution. On retire donc cette négation avant de chercher un
    # marqueur dilué, tout en la comptant comme preuve de base.
    negated_diluted_re = re.compile(
        r"\b(?:non|not)\s+(?:dilu(?:e|es)?|diluted)\b|\bundiluted\b"
    )
    has_negated_diluted = bool(negated_diluted_re.search(normalized))
    positive_text = negated_diluted_re.sub(" ", normalized)
    has_basic = (
        "de base" in normalized
        or "basic" in positive_text
        or has_negated_diluted
    )
    has_diluted = "dilu" in positive_text or "diluted" in positive_text or "dilutive" in positive_text
    if has_basic and has_diluted and any(
        marker in positive_text for marker in ("de base et dilu", "basic and diluted", "base et dilue")
    ):
        return BASIS_BASIC_AND_DILUTED
    if has_diluted:
        return BASIS_DILUTED
    if has_basic:
        return BASIS_BASIC
    return BASIS_UNKNOWN


def _detect_component(value: Any) -> str:
    normalized = normalize_key(value)
    discontinued_markers = (
        "activites arretees", "activites abandonnees", "activites en cours de cession",
        "discontinued operations", "discontinued operation", "held for sale", "en cours de cession",
    )
    continuing_markers = (
        "activites poursuivies", "continuing operations", "continuing operation",
    )
    if any(marker in normalized for marker in discontinued_markers):
        return COMPONENT_DISCONTINUED
    if any(marker in normalized for marker in continuing_markers):
        return COMPONENT_CONTINUING
    return COMPONENT_UNKNOWN


def _currency_sequence(value: Any) -> list[str]:
    text = clean_text(value)
    normalized = normalize_key(text)
    sequence: list[str] = []
    # Recherche positionnelle pour préserver l'ordre « cents $EU / FCFA ».
    patterns = (
        (CURRENCY_USD_CENT, r"cents?\s*(?:de\s*)?(?:\$|usd|us|dollars?|eu)|us\s+cents?|usd\s+cents?|cents?\s+\$eu"),
        (CURRENCY_FCFA, r"f\s?cfa|francs?\s+cfa|franc\s+cfa|\bxof\b"),
        (CURRENCY_USD, r"\busd\b|dollars?\s+(?:eu|us|americains?)|\$eu|\$us"),
    )
    hits: list[tuple[int, str]] = []
    spans: list[tuple[int, int, str]] = []
    for currency, pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            spans.append((match.start(), match.end(), currency))
    # « cents de dollars EU » ne doit pas produire à la fois USD_CENT et
    # USD sur le même segment : la mention en cents, plus précise, prime.
    cent_spans = [(start, end) for start, end, currency in spans if currency == CURRENCY_USD_CENT]
    for start, end, currency in spans:
        if currency == CURRENCY_USD and any(start < cent_end and end > cent_start for cent_start, cent_end in cent_spans):
            continue
        hits.append((start, currency))
    for _position, currency in sorted(hits):
        if not sequence or sequence[-1] != currency:
            sequence.append(currency)
    # « en cents » sans devise complète dans une ligne tronquée : ne pas
    # deviner USD, sauf si le contexte de page le prouve (géré ailleurs).
    if not sequence and "cents" in normalized:
        sequence.append("CENT_DEVISE_NON_PRECISÉE")
    return sequence


def _context_lines(lines: list[str], index: int, before: int = 2, after: int = 2) -> list[str]:
    return [clean_text(line)[:320] for line in lines[max(0, index - before):min(len(lines), index + after + 1)]]


def _evidence(
    *,
    page: dict[str, Any],
    page_number: int,
    lines: list[str],
    line_index: int,
    line_text: str,
    raw_token: str | None,
    header: dict[str, Any] | None,
    rule: str,
) -> dict[str, Any]:
    line_objects = page.get("lines") or []
    line_object = line_objects[line_index] if line_index < len(line_objects) and isinstance(line_objects[line_index], dict) else {}
    return {
        "page": page_number,
        "line_index_on_page": line_index + 1,
        "line_original": clean_text(line_text)[:1000],
        "raw_token": raw_token,
        "context_lines": _context_lines(lines, line_index),
        "column_header": header,
        "extraction_method": page.get("extraction_method") or "texte_natif",
        "ocr_confidence": line_object.get("ocr_mean_confidence"),
        "parser_rule": rule,
        "parser_version": EPS_PARSER_VERSION,
    }


_EPS_LABEL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("fr_resultat_par_action", r"(?:résultat|bénéfice)(?:\s+net)?\s+(?:de\s+base\s+|dilué\s+)?par\s+actions?\b"),
    ("fr_resultat_par_action_sans_accent", r"(?:resultat|benefice)(?:\s+net)?\s+(?:de\s+base\s+|dilue\s+)?par\s+actions?\b"),
    ("en_earnings_per_share", r"(?:basic|diluted|dilutive)?\s*earnings\s+per\s+share\b"),
    ("en_profit_per_share", r"profit\s+attributable\s+per\s+share\b"),
)


def _find_eps_label(line: str) -> tuple[re.Match[str], str] | None:
    normalized = normalize_key(line)
    if any(marker in normalized for marker in ("utilise pour le calcul", "used to calculate", "used in computing")):
        return None
    if any(marker in normalized for marker in ("dividende par action", "dividend per share", "valeur comptable par action", "book value per share")):
        return None
    for rule, pattern in _EPS_LABEL_PATTERNS:
        match = re.search(pattern, line, flags=re.I)
        if match:
            return match, rule
    return None


def _is_basis_subline(line: str) -> bool:
    normalized = normalize_key(line)
    return normalized.startswith("de base") or normalized.startswith("basic") or bool(
        re.match(r"^(?:de base|basic)\b", normalized)
    )


def _repair_ten_token(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Répare « 1 0.00 » en 10.00 uniquement dans un motif à cinq jetons.

    Cas ETIT mesuré : `1.68 1 0.00 1.37 8.00`, où quatre valeurs sont
    attendues (deux exercices × deux devises). La réparation est tracée et
    ne s'applique pas à une séquence ordinaire.
    """
    if len(slots) != 5:
        return slots
    repaired: list[dict[str, Any]] = []
    index = 0
    changed = False
    while index < len(slots):
        current = slots[index]
        nxt = slots[index + 1] if index + 1 < len(slots) else None
        if (
            not changed
            and nxt is not None
            and current.get("value") == 1
            and isinstance(nxt.get("value"), (int, float))
            and 0 <= float(nxt["value"]) < 1
            and re.fullmatch(r"0[.,]\d+", str(nxt.get("normalized_raw") or ""))
        ):
            repaired.append(
                {
                    **nxt,
                    "raw": f"{current.get('raw')} {nxt.get('raw')}",
                    "normalized_raw": f"10{str(nxt.get('normalized_raw'))[1:]}",
                    "value": 10 + float(nxt["value"]),
                    "start": current.get("start"),
                    "repair": "JETON_1_0_XX_LU_COMME_10_XX_DANS_MOTIF_DOUBLE_DEVISE",
                }
            )
            index += 2
            changed = True
            continue
        repaired.append(current)
        index += 1
    return repaired if changed and len(repaired) == 4 else slots


def _map_slot_year(
    slot_index: int,
    years: list[int] | None,
    document_exercice: int | None,
) -> tuple[int | None, int | None, str]:
    if years and slot_index < len(years):
        year = years[slot_index]
        return year, (max(years) - year), "EN_TETE_DE_COLONNES"
    if document_exercice:
        return document_exercice - slot_index, slot_index, "ORDRE_DOCUMENT_SUPPOSE_DESCENDANT"
    return None, slot_index, "NON_PROUVEE"


_EPS_SCALE_PATTERNS: tuple[tuple[int, str, re.Pattern[str]], ...] = (
    (
        1_000,
        "milliers",
        re.compile(
            r"\b(?:en|in)\s+(?:milliers|thousands?)\b"
            r"|\b(?:milliers|thousands?)\s+de\s+(?:fcfa|francs?\s+cfa|xof|usd|dollars?)\b"
        ),
    ),
    (
        1_000_000,
        "millions",
        re.compile(
            r"\b(?:en|in)\s+millions?\b"
            r"|\bmillions?\s+de\s+(?:fcfa|francs?\s+cfa|xof|usd|dollars?)\b"
        ),
    ),
    (
        1_000_000_000,
        "milliards",
        re.compile(
            r"\b(?:en|in)\s+(?:milliards|billions?)\b"
            r"|\b(?:milliards|billions?)\s+de\s+(?:fcfa|francs?\s+cfa|xof|usd|dollars?)\b"
        ),
    ),
)

_CURRENCY_UNIT_RE = r"(?:fcfa|francs?\s+cfa|xof|usd|dollars?|cents?)"


def _eps_scale_from_text(value: Any) -> tuple[int, str | None]:
    normalized = normalize_key(value)
    for multiplier, label, pattern in _EPS_SCALE_PATTERNS:
        if pattern.search(normalized):
            return multiplier, label
    return 1, None


def _has_explicit_per_share_unit(value: Any) -> bool:
    normalized = normalize_key(value)
    # Le FCFA de « en milliers de FCFA » décrit l'échelle des montants de
    # la page ; il ne prouve pas que le BPA lui-même est déjà en FCFA.
    without_scale = re.sub(
        r"\b(?:en|in)\s+(?:milliers|millions?|milliards|thousands?|billions?)"
        r"(?:\s+de)?\s+(?:fcfa|francs?\s+cfa|xof|usd|dollars?)?\b",
        " ",
        normalized,
    )
    return bool(
        re.search(
            rf"\b(?:par actions?|per shares?)\b.{{0,30}}\b{_CURRENCY_UNIT_RE}\b",
            without_scale,
        )
        or re.search(
            rf"\b{_CURRENCY_UNIT_RE}\b.{{0,15}}\b(?:par actions?|per shares?)\b",
            without_scale,
        )
        or re.search(rf"\b(?:en|in)\s+{_CURRENCY_UNIT_RE}\b", without_scale)
    )


def _eps_unit_scale_status(
    *,
    label_text: str,
    lines: list[str],
    line_index: int,
    page_header_context: str,
) -> dict[str, Any]:
    """Échelle monétaire applicable ou ambiguë pour une ligne BPA.

    Une mention explicite par action (« BPA en FCFA ») prime sur l'échelle
    des montants de l'état. Cette échelle décrit d'abord les totaux : elle
    ne s'applique pas automatiquement à un montant par action. Elle est
    seulement signalée ici ; l'appelant ne bloque que les valeurs brutes
    inférieures à une unité de FCFA ou publiées avec au moins trois
    décimales, pour lesquelles les deux lectures (FCFA ou milliers/
    millions de FCFA) restent plausibles.
    """
    zones = (
        ("LIBELLE_BPA", label_text),
        ("CONTEXTE_PROCHE", " ".join(lines[max(0, line_index - 4):line_index + 1])),
        ("EN_TETE_DE_PAGE", " ".join(lines[:30]) or page_header_context),
    )
    for source, text in zones:
        multiplier, scale_label = _eps_scale_from_text(text)
        explicit = _has_explicit_per_share_unit(text)
        if explicit and multiplier == 1:
            return {
                "multiplier": 1,
                "label": None,
                "source": source,
                "explicit_per_share_unit": True,
            }
        if multiplier > 1:
            return {
                "multiplier": multiplier,
                "label": scale_label,
                "source": source,
                "explicit_per_share_unit": explicit,
            }
    return {
        "multiplier": 1,
        "label": None,
        "source": "AUCUNE_ECHELLE_DE_PAGE_DETECTEE",
        "explicit_per_share_unit": False,
    }


def _make_eps_observations_from_slots(
    *,
    slots: list[dict[str, Any]],
    page: dict[str, Any],
    page_number: int,
    page_context: dict[str, Any],
    lines: list[str],
    line_index: int,
    evidence_line_index: int,
    label_text: str,
    evidence_text: str,
    basis: str,
    component: str,
    header: dict[str, Any] | None,
    document_exercice: int | None,
    rule: str,
) -> list[dict[str, Any]]:
    years = list((header or {}).get("years") or [])
    context_for_currency = " ".join(lines[max(0, line_index - 4):line_index + 1])
    page_header_context = _page_text(page)[:1200]
    currency_sequence = (
        _currency_sequence(label_text)
        or _currency_sequence(context_for_currency)
        or _currency_sequence(page_header_context)
    )
    currency_sequence = [item for item in currency_sequence if item != "CENT_DEVISE_NON_PRECISÉE"] or currency_sequence
    unit_scale = _eps_unit_scale_status(
        label_text=label_text,
        lines=lines,
        line_index=line_index,
        page_header_context=page_header_context,
    )

    # Motif ETIT à quatre valeurs : deux exercices × (cents, FCFA). Si la
    # ligne tronquée ne nomme que les cents mais que chaque seconde valeur
    # vaut environ 4 à 8 fois la première, on conserve un candidat FCFA
    # explicite comme *motif à confirmer*, jamais éligible.
    paired_pattern_candidate = False
    if len(slots) == 4 and currency_sequence == [CURRENCY_USD_CENT]:
        values = [slot.get("value") for slot in slots]
        if all(isinstance(value, (int, float)) and value not in (0, None) for value in values):
            ratios = [float(values[1]) / float(values[0]), float(values[3]) / float(values[2])]
            if all(4 <= ratio <= 8 for ratio in ratios):
                currency_sequence = [CURRENCY_USD_CENT, CURRENCY_FCFA]
                paired_pattern_candidate = True

    if len(currency_sequence) >= 2 and len(slots) > len(years):
        slots = _repair_ten_token(slots)

    observations: list[dict[str, Any]] = []
    # Texte seul sans coordonnées : « 185 170 » peut être un montant de
    # 185 170 ou deux BPA annuels de 185 et 170. Dans une ligne BPA de
    # tableau annuel, la seconde lecture est la seule plausible lorsque
    # l'en-tête/document attend au moins deux exercices ; elle est tracée.
    if len(slots) == 1 and slots[0].get("value") is not None:
        raw_groups = str(slots[0].get("raw") or "").strip("()").split()
        if (
            2 <= len(raw_groups) <= 5
            and all(re.fullmatch(r"\d{3}", group) for group in raw_groups)
            and (len(raw_groups) == 2 or len(years) == len(raw_groups))
        ):
            slots = [
                {**slots[0], "raw": group, "normalized_raw": group, "value": float(group), "decimals": 0, "repair": "GROUPES_185_170_LUS_COMME_DEUX_COLONNES_BPA"}
                for group in raw_groups
            ]
    # Une colonne sans année d'en-tête prouvée ne doit pas être rattachée
    # par soustraction à un exercice plus ancien. Au-delà des colonnes
    # attendues, les nombres appartiennent le plus souvent à un tableau
    # voisin fusionné dans la même ligne PDF ; ils sont écartés et tracés.
    year_columns = len(years) if years else 2
    if slots and all(slot.get("is_dash") for slot in slots):
        max_slots = year_columns
    elif len(currency_sequence) >= 2:
        max_slots = year_columns * 2
    else:
        max_slots = year_columns
    trailing_slots_ignored = max(0, len(slots) - max_slots)
    if trailing_slots_ignored:
        slots = slots[:max_slots]

    if slots and all(slot.get("is_dash") for slot in slots):
        # Les tirets n'ont ni valeur ni devise : chacun occupe une colonne
        # d'exercice, même si la ligne des activités poursuivies voisine
        # présente deux devises par exercice.
        currency = currency_sequence[0] if currency_sequence else CURRENCY_UNKNOWN
        assignments = [(slot, currency, i, i) for i, slot in enumerate(slots)]
        currency_source = "CONTEXTE_LIGNE_NEANT"
    elif len(currency_sequence) >= 2 and len(slots) >= 2:
        # Deux formes : unités répétées par colonne physique, ou paire
        # (devise 1, devise 2) répétée par exercice.
        if len(currency_sequence) == len(slots) and years and len(years) * 2 == len(slots):
            assignments = [(slot, currency_sequence[i], i // 2, i) for i, slot in enumerate(slots)]
        else:
            pair_size = 2 if len(currency_sequence) >= 2 else 1
            assignments = [
                (slot, currency_sequence[i % pair_size], i // pair_size, i)
                for i, slot in enumerate(slots)
            ]
        currency_source = "MOTIF_PAIRE_A_CONFIRMER" if paired_pattern_candidate else "LIGNE_OU_EN_TETE"
    else:
        currency = currency_sequence[0] if currency_sequence else CURRENCY_UNKNOWN
        currency_source = "LIGNE_OU_CONTEXTE" if currency_sequence else "AUCUNE"
        if currency == "CENT_DEVISE_NON_PRECISÉE":
            currency = CURRENCY_UNKNOWN
            currency_source = "CENT_SANS_DEVISE"
        assignments = [(slot, currency, i, i) for i, slot in enumerate(slots)]

    normalized_page = normalize_key(" ".join(lines[:20]))
    source_kind = "CHIFFRES_CLES" if any(
        marker in normalized_page for marker in ("chiffres cles", "key figures", "highlights", "en bref")
    ) or any(slot.get("is_percent") for slot in slots) else "ETAT_OU_NOTE"

    for slot, currency, year_slot_index, physical_index in assignments:
        year, year_offset, year_source = _map_slot_year(year_slot_index, years or None, document_exercice)
        reasons: list[str] = []
        if slot.get("is_dash"):
            reasons.append("COLONNE_NEANT")
        if currency != CURRENCY_FCFA:
            reasons.append("DEVISE_NON_FCFA_OU_NON_PROUVEE")
        raw_value = slot.get("value")
        scale_multiplier = int(unit_scale.get("multiplier") or 1)
        # Cas mesurés SPHC : 0,830 et 1,695 sous un état en milliers de
        # FCFA. Une valeur par action entière (Sonatel : 2 359 sous un
        # en-tête en millions) est déjà libellée en FCFA par action et
        # n'est pas affectée par l'échelle des totaux. En dessous de 1 FCFA
        # ou avec trois décimales, en revanche, la lecture brute et la
        # lecture à l'échelle de page sont toutes deux plausibles ; la
        # preuve reste donc non promue.
        page_scale_blocks_fcfa = (
            currency == CURRENCY_FCFA
            and scale_multiplier > 1
            and not unit_scale.get("explicit_per_share_unit")
            and isinstance(raw_value, (int, float))
            and (
                0 < abs(float(raw_value)) < 1
                or int(slot.get("decimals") or 0) >= 3
            )
            and abs(float(raw_value)) * scale_multiplier <= 1_000_000
        )
        if page_scale_blocks_fcfa:
            reasons.append(
                "ECHELLE_MONETAIRE_DE_PAGE_SANS_UNITE_PAR_ACTION_EXPLICITE"
            )
        if paired_pattern_candidate and currency == CURRENCY_FCFA:
            reasons.append("DEVISE_FCFA_DEDUITE_D_UN_MOTIF_NON_EXPLICITE")
        if basis == BASIS_DILUTED:
            reasons.append("BPA_DILUE_NON_RETENU_COMME_DE_BASE")
        elif basis == BASIS_UNKNOWN:
            reasons.append("BASE_DE_BASE_OU_DILUE_NON_PRECISEE")
        if component in {COMPONENT_CONTINUING, COMPONENT_DISCONTINUED}:
            reasons.append("COMPOSANTE_ET_NON_TOTAL_PUBLIE")
        elif component == COMPONENT_UNKNOWN and source_kind == "CHIFFRES_CLES":
            reasons.append("COMPOSANTE_NON_PRECISEE_DANS_LES_CHIFFRES_CLES")
        if year_offset is None:
            reasons.append("EXERCICE_DE_COLONNE_NON_PROUVE")
        eligible = not reasons and slot.get("value") is not None
        observations.append(
            {
                "kind": "BPA_PUBLIE",
                "value": slot.get("value"),
                "raw_token": slot.get("normalized_raw") or slot.get("raw"),
                "token_repair": slot.get("repair"),
                "published_decimals": slot.get("decimals"),
                "is_dash": bool(slot.get("is_dash")),
                "currency": currency,
                "currency_source": currency_source,
                "unit_label": (
                    f"valeur brute sous échelle de page en {unit_scale.get('label')} "
                    "de FCFA, sans unité par action explicite"
                    if page_scale_blocks_fcfa
                    else "FCFA par action" if currency == CURRENCY_FCFA
                    else "cents USD par action" if currency == CURRENCY_USD_CENT
                    else "USD par action" if currency == CURRENCY_USD
                    else "devise par action non prouvée"
                ),
                "page_monetary_scale_multiplier": unit_scale.get("multiplier"),
                "page_monetary_scale_label": unit_scale.get("label"),
                "page_monetary_scale_source": unit_scale.get("source"),
                "per_share_unit_explicit": bool(
                    unit_scale.get("explicit_per_share_unit")
                ),
                "basis": basis,
                "component": component if component != COMPONENT_UNKNOWN else COMPONENT_TOTAL if source_kind != "CHIFFRES_CLES" else COMPONENT_UNKNOWN,
                "component_source": "LIGNE_OU_TITRE" if component != COMPONENT_UNKNOWN else "AUCUNE_COMPOSANTE_DANS_LA_LIGNE",
                "accounting_scope": page_context.get("accounting_scope") or SCOPE_UNKNOWN,
                "accounting_scope_source": page_context.get("accounting_scope_source"),
                "framework": page_context.get("framework") or "NON_PROUVE",
                "target_exercice": year,
                "year_offset_from_document": year_offset,
                "column_year_source": year_source,
                "physical_column_index": physical_index,
                "trailing_slots_ignored": trailing_slots_ignored,
                "source_kind": source_kind,
                "eligible_fcfa_total_basic": eligible,
                "ineligibility_reasons": reasons,
                "evidence": _evidence(
                    page=page,
                    page_number=page_number,
                    lines=lines,
                    line_index=evidence_line_index,
                    line_text=evidence_text,
                    raw_token=str(slot.get("normalized_raw") or slot.get("raw") or ""),
                    header=header,
                    rule=rule,
                ),
            }
        )
    return observations


_SHARE_LABEL_RULES: tuple[tuple[str, str, str], ...] = (
    ("actions_autocontrole", r"nombre d['’]actions d['’]autocontr[oô]le|actions d['’]autocontr[oô]le|actions propres|treasury shares", "AUTOCONTROLE"),
    ("pondere_fr", r"nombre moyen pond[ée]r[ée] d['’](?:actions|titres)(?: ordinaires)?(?: en circulation)?", "MOYEN_PONDERE"),
    ("pondere_en", r"weighted average number of ordinary shares", "MOYEN_PONDERE"),
    ("circulation_fr", r"nombre d['’]actions(?: ordinaires)? en circulation", "FIN_EXERCICE_OU_EN_CIRCULATION"),
    ("capital_fr", r"nombre d['’]actions(?: ordinaires)? composant le capital", "FIN_EXERCICE_OU_EN_CIRCULATION"),
    ("emises_en", r"(?:total )?issued (?:ordinary )?shares|ordinary shares in issue", "FIN_EXERCICE_OU_EN_CIRCULATION"),
)


def _share_scale(lines: list[str], line_index: int) -> tuple[int, str]:
    window = " ".join(lines[max(0, line_index - 3):line_index + 1])
    normalized = normalize_key(window)
    if any(marker in normalized for marker in ("in thousands", "en milliers")):
        return 1_000, "milliers (mention proche de la ligne)"
    if any(marker in normalized for marker in ("in millions", "en millions")):
        return 1_000_000, "millions (mention proche de la ligne)"
    return 1, "actions (aucun multiplicateur proche prouvé)"


def _make_share_observations_from_slots(
    *,
    slots: list[dict[str, Any]],
    denominator_kind: str,
    page: dict[str, Any],
    page_number: int,
    page_context: dict[str, Any],
    lines: list[str],
    line_index: int,
    evidence_line_index: int,
    evidence_text: str,
    header: dict[str, Any] | None,
    document_exercice: int | None,
    rule: str,
) -> list[dict[str, Any]]:
    years = list((header or {}).get("years") or [])
    slots = slots[:len(years) if years else 2]
    multiplier, unit_label = _share_scale(lines, line_index)
    observations: list[dict[str, Any]] = []
    for index, slot in enumerate(slots):
        raw_value = slot.get("value")
        if raw_value is None:
            continue
        value = float(raw_value) * multiplier
        year, offset, year_source = _map_slot_year(index, years or None, document_exercice)
        reasons: list[str] = []
        if denominator_kind == "AUTOCONTROLE":
            reasons.append("ACTIONS_D_AUTOCONTROLE_PAS_UN_DENOMINATEUR_TOTAL")
        if denominator_kind == "MOYEN_PONDERE_DILUE":
            reasons.append("DENOMINATEUR_DILUE_NON_RETENU_POUR_LE_DE_BASE")
        if not float(value).is_integer() or not (1_000 <= value <= 200_000_000_000):
            reasons.append("NOMBRE_D_ACTIONS_HORS_PLAGE_OU_NON_ENTIER")
        observations.append(
            {
                "kind": "NOMBRE_ACTIONS",
                "denominator_kind": denominator_kind,
                "value": int(value) if float(value).is_integer() else value,
                "raw_value": raw_value,
                "raw_token": slot.get("normalized_raw") or slot.get("raw"),
                "multiplier": multiplier,
                "unit_label": unit_label,
                "accounting_scope": page_context.get("accounting_scope") or SCOPE_UNKNOWN,
                "accounting_scope_source": page_context.get("accounting_scope_source"),
                "framework": page_context.get("framework") or "NON_PROUVE",
                "target_exercice": year,
                "year_offset_from_document": offset,
                "column_year_source": year_source,
                "eligible_as_denominator": not reasons,
                "ineligibility_reasons": reasons,
                "evidence": _evidence(
                    page=page,
                    page_number=page_number,
                    lines=lines,
                    line_index=evidence_line_index,
                    line_text=evidence_text,
                    raw_token=str(slot.get("normalized_raw") or slot.get("raw") or ""),
                    header=header,
                    rule=rule,
                ),
            }
        )
    return observations


_NUMERATOR_RULES: tuple[tuple[str, str, str], ...] = (
    ("ordinaire_fr", r"(?:résultat|bénéfice)(?: net)? attribuable aux (?:actionnaires ordinaires|porteurs d['’]actions ordinaires|détenteurs d['’]actions ordinaires)", "ATTRIBUABLE_AUX_ACTIONNAIRES_ORDINAiRES"),
    ("ordinaire_en", r"profit attributable to (?:ordinary )?equity holders", "ATTRIBUABLE_AUX_ACTIONNAIRES_ORDINAiRES"),
    ("parent_fr", r"résultat net(?:,?\s+part du groupe| attribuable aux propriétaires| part de l['’]entreprise consolidante)", "PART_DU_GROUPE_OU_PROPRIETAIRES"),
    ("parent_en", r"profit attributable to (?:owners|equity holders) of (?:the )?(?:parent|company)", "PART_DU_GROUPE_OU_PROPRIETAIRES"),
    ("eps_note_numerator", r"(?:résultat net|profit)(?:[^.]{0,80})utilis(?:é|e) pour le calcul du résultat par action", "NUMERATEUR_NOTE_BPA_A_QUALIFIER"),
)


def _monetary_scale_and_currency(lines: list[str], line_index: int) -> tuple[int, str, str]:
    window = " ".join(lines[max(0, line_index - 6):line_index + 1])
    normalized = normalize_key(window)
    if "milliards" in normalized or "billions" in normalized:
        multiplier, scale = 1_000_000_000, "milliards"
    elif "millions" in normalized:
        multiplier, scale = 1_000_000, "millions"
    elif "milliers" in normalized or "thousands" in normalized:
        multiplier, scale = 1_000, "milliers"
    else:
        multiplier, scale = 1, "unites"
    currencies = _currency_sequence(window)
    currency = currencies[0] if currencies and currencies[0] in {CURRENCY_FCFA, CURRENCY_USD} else CURRENCY_UNKNOWN
    if "us dollars" in normalized or "dollars eu" in normalized or "dollars us" in normalized:
        currency = CURRENCY_USD
    return multiplier, currency, scale


def _pages_are_complete_sequence(pages: list[dict[str, Any]]) -> bool:
    numbers = [_page_number(page, index + 1) for index, page in enumerate(pages)]
    return bool(numbers) and numbers == list(range(1, len(numbers) + 1))


def _has_discontinued_result_evidence(pages: list[dict[str, Any]]) -> bool:
    """Vrai si une ligne chiffrée signale une composante arrêtée/cedée."""
    # Une simple ligne d'actifs « détenus en vue de la vente » au bilan
    # ne prouve pas un résultat d'activités arrêtées distinct. Seules les
    # mentions de la composante de résultat bloquent l'inférence.
    markers = (
        "activites arretees", "activites abandonnees", "activites en cours de cession",
        "discontinued operations", "discontinued operation",
    )
    for page in pages:
        for line in _page_line_texts(page):
            normalized = normalize_key(line)
            if not any(marker in normalized for marker in markers):
                continue
            numeric_tokens = re.findall(r"\(?\s*-?\d[\d\s]*(?:[,.]\d+)?\s*\)?", line)
            meaningful = [
                token
                for token in numeric_tokens
                if any(char in token for char in "(),") or len(re.sub(r"\D", "", token)) >= 3
            ]
            # Un titre/note sans montant ne suffit pas ; une ligne de
            # résultat ou de bilan chiffrée suffit à interdire l'inférence
            # « poursuivi = total par absence de composante ».
            if meaningful:
                return True
    return False


def extract_per_share_observations(
    pages: list[dict[str, Any]],
    document_exercice: int | None = None,
    page_contexts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Observations BPA, numérateurs et dénominateurs, preuves comprises."""
    if page_contexts is None:
        page_contexts, _summary = classify_page_accounting_contexts(pages)
    eps: list[dict[str, Any]] = []
    shares: list[dict[str, Any]] = []
    numerators: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []

    for page_index, page in enumerate(pages):
        page_number = _page_number(page, page_index + 1)
        page_context = page_contexts[page_index] if page_index < len(page_contexts) else {}
        lines = _page_line_texts(page)
        line_objects = page.get("lines") or []
        if not lines:
            continue
        page_header = detect_column_years(lines)
        used_eps_lines: set[int] = set()
        page_is_probable_table_of_contents = (
            "SOMMAIRE_POSSIBLE" in (page_context.get("statement_kinds") or [])
            and page_number <= 12
        )

        for line_index, line in enumerate(lines):
            if line_index in used_eps_lines:
                continue
            if page_is_probable_table_of_contents and _find_eps_label(line):
                ignored.append(
                    {
                        "page": page_number,
                        "line": clean_text(line)[:320],
                        "reason": "PAGE_DE_SOMMAIRE",
                    }
                )
                continue
            if _is_table_of_contents_line(line) and _find_eps_label(line):
                ignored.append({"page": page_number, "line": clean_text(line)[:320], "reason": "LIGNE_DE_SOMMAIRE"})
                continue

            # --- Numérateurs de note BPA (avant le BPA lui-même) ---
            for rule, pattern, numerator_kind in _NUMERATOR_RULES:
                match = re.search(pattern, line, flags=re.I)
                if not match:
                    continue
                slots, _reasons = _filter_note_ref_and_years(_value_slots(line, match.end(), line_object=line_objects[line_index] if line_index < len(line_objects) else None))
                slots = [slot for slot in slots if slot.get("value") is not None]
                if not slots:
                    break
                multiplier, currency, scale = _monetary_scale_and_currency(lines, line_index)
                header = detect_column_years(lines[max(0, line_index - 14):line_index + 1]) or page_header
                years = list((header or {}).get("years") or [])
                component = _detect_component(" ".join(lines[max(0, line_index - 3):line_index + 1]))
                for slot_index, slot in enumerate(slots[:len(years) if years else 2]):
                    year, offset, year_source = _map_slot_year(slot_index, years or None, document_exercice)
                    numerators.append(
                        {
                            "kind": "NUMERATEUR_BPA",
                            "numerator_kind": numerator_kind.replace("ORDINAiRES", "ORDINAIRES"),
                            "value": float(slot["value"]) * multiplier,
                            "raw_value": slot.get("value"),
                            "raw_token": slot.get("normalized_raw") or slot.get("raw"),
                            "multiplier": multiplier,
                            "currency": currency,
                            "unit_label": f"{currency}, montants en {scale}",
                            "component": component,
                            "accounting_scope": page_context.get("accounting_scope") or SCOPE_UNKNOWN,
                            "target_exercice": year,
                            "year_offset_from_document": offset,
                            "column_year_source": year_source,
                            "evidence": _evidence(
                                page=page, page_number=page_number, lines=lines, line_index=line_index,
                                line_text=line, raw_token=str(slot.get("normalized_raw") or ""),
                                header=header, rule=rule,
                            ),
                        }
                    )
                break

            # --- BPA publié ---
            eps_match = _find_eps_label(line)
            if eps_match:
                match, rule = eps_match
                slots, filter_reasons = _filter_note_ref_and_years(_value_slots(line, match.end(), line_object=line_objects[line_index] if line_index < len(line_objects) else None))
                # Titre « Résultat par action : 9.2 » suivi des sous-lignes
                # de base/dilué : 9.2 (ou 8) est la référence de note, pas
                # le BPA. Sans sous-ligne proche, on conserve en revanche
                # un éventuel BPA à une décimale comme candidat non éligible.
                if len(slots) == 1 and slots[0].get("value") is not None:
                    raw_note = str(slots[0].get("normalized_raw") or "").strip("()")
                    lookahead_has_basis = any(
                        _is_basis_subline(candidate) or _detect_basis(candidate) != BASIS_UNKNOWN
                        for candidate in lines[line_index + 1:line_index + 5]
                    )
                    if lookahead_has_basis and (
                        re.fullmatch(r"\d{1,2}\.\d", raw_note)
                        or re.fullmatch(r"\d{1,2}", raw_note)
                    ):
                        slots = []
                        filter_reasons.append("REFERENCE_DE_NOTE_AVANT_SOUS_LIGNES")
                local_header = detect_column_years(lines[max(0, line_index - 16):line_index + 1]) or page_header
                basis = _detect_basis(line)
                component_context = " ".join(lines[max(0, line_index - 3):line_index + 1])
                component = _detect_component(component_context)
                if any(slot.get("value") is not None or slot.get("is_dash") for slot in slots):
                    eps.extend(
                        _make_eps_observations_from_slots(
                            slots=slots, page=page, page_number=page_number, page_context=page_context,
                            lines=lines, line_index=line_index, evidence_line_index=line_index,
                            label_text=line, evidence_text=line, basis=basis, component=component,
                            header=local_header, document_exercice=document_exercice, rule=rule,
                        )
                    )
                else:
                    # Forme relevée dans le pilote : titre BPA, unité seule,
                    # puis une valeur par ligne. Ces lignes purement
                    # numériques sont les colonnes du tableau ; une année
                    # seule reste un en-tête et tout nouveau libellé arrête.
                    continuation_slots: list[dict[str, Any]] = []
                    continuation_indexes: list[int] = []
                    continuation_parts: list[str] = [line]
                    unit_words = {
                        "en", "fcfa", "franc", "francs", "cfa", "xof", "usd", "dollar", "dollars",
                        "cents", "cent", "eu", "par", "action", "actions",
                    }
                    for next_index in range(line_index + 1, min(len(lines), line_index + 6)):
                        next_line = lines[next_index]
                        words = [
                            normalize_key(word)
                            for word in re.findall(r"[A-Za-zÀ-ÿ]+", next_line)
                        ]
                        if words and all(word in unit_words for word in words):
                            continuation_parts.append(next_line)
                            continuation_indexes.append(next_index)
                            continue
                        years_in_line = _years_from_line(next_line)
                        next_slots, _next_reasons = _filter_note_ref_and_years(
                            _value_slots(
                                next_line,
                                0,
                                line_object=line_objects[next_index] if next_index < len(line_objects) else None,
                            )
                        )
                        if years_in_line and len(next_slots) <= 1 and not continuation_slots:
                            local_header = detect_column_years(
                                lines[max(0, line_index - 4):next_index + 1]
                            ) or local_header
                            continuation_parts.append(next_line)
                            continuation_indexes.append(next_index)
                            continue
                        if words and any(word not in unit_words for word in words):
                            break
                        if not any(slot.get("value") is not None or slot.get("is_dash") for slot in next_slots):
                            break
                        continuation_slots.extend(next_slots)
                        continuation_indexes.append(next_index)
                        continuation_parts.append(next_line)
                    if continuation_slots:
                        evidence_index = continuation_indexes[-1]
                        eps.extend(
                            _make_eps_observations_from_slots(
                                slots=continuation_slots,
                                page=page,
                                page_number=page_number,
                                page_context=page_context,
                                lines=lines,
                                line_index=evidence_index,
                                evidence_line_index=evidence_index,
                                label_text=" | ".join(continuation_parts),
                                evidence_text=" | ".join(continuation_parts),
                                basis=_detect_basis(" | ".join(continuation_parts[:2])) if _detect_basis(" | ".join(continuation_parts[:2])) != BASIS_UNKNOWN else basis,
                                component=_detect_component(
                                    f"{component_context} {' | '.join(continuation_parts[:2])}"
                                ),
                                header=local_header,
                                document_exercice=document_exercice,
                                rule=f"{rule}+valeurs_sur_lignes_suivantes",
                            )
                        )
                        used_eps_lines.update(continuation_indexes)
                    # Titre seul, référence de note seule ou en-tête suivi des
                    # sous-lignes de base/dilué. On ne suit que quatre lignes.
                    for next_index in range(line_index + 1, min(len(lines), line_index + 5)):
                        if continuation_slots:
                            break
                        next_line = lines[next_index]
                        if _is_table_of_contents_line(next_line):
                            continue
                        next_label = _find_eps_label(next_line)
                        next_match = next_label[0] if next_label else None
                        next_basis = _detect_basis(next_line)
                        is_subline = _is_basis_subline(next_line) or next_basis != BASIS_UNKNOWN
                        if not is_subline and not next_match:
                            # Ligne d'années intermédiaire : elle Peut porter
                            # l'en-tête, mais ne termine pas la recherche.
                            if _years_from_line(next_line):
                                local_header = detect_column_years(lines[max(0, line_index - 4):next_index + 1]) or local_header
                                continue
                            # Sous-titre du bloc BPA avant les sous-lignes,
                            # par exemple « Résultat net part du Groupe : »
                            # entre le titre et « - de base ».
                            normalized_next = normalize_key(next_line)
                            if (
                                len(next_line.split()) <= 12
                                and next_line.rstrip().endswith(":")
                                and any(
                                    marker in normalized_next
                                    for marker in (
                                        "resultat net part du groupe",
                                        "resultat attribuable",
                                        "benefice attribuable",
                                        "proprietaires de la maison mere",
                                        "actionnaires ordinaires",
                                    )
                                )
                            ):
                                continue
                            if re.search(r"[A-Za-zÀ-ÿ]{3,}", next_line):
                                break
                            continue
                        next_label_end = next_match.end() if next_match else 0
                        basis_match = re.search(r"de\s+base|dilu[eé]|basic|diluted|dilutive", next_line, flags=re.I)
                        if basis_match and not next_match:
                            next_label_end = basis_match.end()
                        next_slots, _next_reasons = _filter_note_ref_and_years(
                            _value_slots(next_line, next_label_end, line_object=line_objects[next_index] if next_index < len(line_objects) else None)
                        )
                        if not any(slot.get("value") is not None or slot.get("is_dash") for slot in next_slots):
                            # Un nouveau titre BPA sans valeur (par exemple
                            # le passage des activités poursuivies aux
                            # activités arrêtées) clôt le titre courant :
                            # ses sous-lignes seront traitées sous ce
                            # nouveau titre, jamais sous le précédent.
                            if next_match:
                                break
                            continue
                        eps.extend(
                            _make_eps_observations_from_slots(
                                slots=next_slots, page=page, page_number=page_number, page_context=page_context,
                                lines=lines, line_index=next_index, evidence_line_index=next_index,
                                label_text=f"{line} | {next_line}", evidence_text=f"{line} | {next_line}",
                                basis=next_basis if next_basis != BASIS_UNKNOWN else basis,
                                component=_detect_component(f"{component_context} {next_line}"),
                                header=local_header, document_exercice=document_exercice,
                                rule=f"{rule}+sous_ligne",
                            )
                        )
                        used_eps_lines.add(next_index)

            # --- Nombres d'actions ---
            # Phrase narrative « capital divisé en X actions » : la première
            # valeur après « divisé en » est le nombre d'actions, le nominal
            # qui suit n'est jamais une seconde colonne.
            divided = re.search(r"divis(?:é|e) en\s+([0-9][0-9\s\u202f\u00a0.,]*)actions", line, flags=re.I)
            if divided:
                token = extract_numeric_tokens(divided.group(1), integer_thousands=True)
                if token:
                    shares.extend(
                        _make_share_observations_from_slots(
                            slots=[{**token[0], "is_dash": False}], denominator_kind="FIN_EXERCICE_OU_EN_CIRCULATION",
                            page=page, page_number=page_number, page_context=page_context, lines=lines,
                            line_index=line_index, evidence_line_index=line_index, evidence_text=line,
                            header=None, document_exercice=document_exercice, rule="capital_divise_en_actions",
                        )
                    )
                continue

            for rule, pattern, denominator_kind in _SHARE_LABEL_RULES:
                match = re.search(pattern, line, flags=re.I)
                if not match:
                    continue
                slots, _reasons = _filter_note_ref_and_years(
                    _value_slots(line, match.end(), integer_thousands=True, line_object=line_objects[line_index] if line_index < len(line_objects) else None)
                )
                evidence_text = line
                evidence_index = line_index
                if not any(slot.get("value") is not None for slot in slots):
                    # Libellé coupé en fin de ligne (« s'est élevé à » puis
                    # le montant à la ligne suivante).
                    for next_index in range(line_index + 1, min(len(lines), line_index + 3)):
                        next_line = lines[next_index]
                        next_slots, _next_reasons = _filter_note_ref_and_years(
                            _value_slots(next_line, 0, integer_thousands=True, line_object=line_objects[next_index] if next_index < len(line_objects) else None)
                        )
                        if any(slot.get("value") is not None for slot in next_slots):
                            slots = next_slots
                            evidence_text = f"{line} | {next_line}"
                            evidence_index = next_index
                            break
                        if re.search(r"[A-Za-zÀ-ÿ]{3,}", next_line):
                            break
                slots = [slot for slot in slots if slot.get("value") is not None]
                if not slots:
                    break
                effective_kind = denominator_kind
                if denominator_kind == "MOYEN_PONDERE" and _detect_basis(line) == BASIS_DILUTED:
                    # Une ligne « de base et dilué » peut donner le même
                    # dénominateur ; une ligne seulement diluée ne le Peut pas.
                    # `_detect_basis` distingue aussi « non dilué » (base).
                    effective_kind = "MOYEN_PONDERE_DILUE"
                header = detect_column_years(lines[max(0, line_index - 14):line_index + 1]) or page_header
                shares.extend(
                    _make_share_observations_from_slots(
                        slots=slots[:5], denominator_kind=effective_kind, page=page, page_number=page_number,
                        page_context=page_context, lines=lines, line_index=line_index,
                        evidence_line_index=evidence_index, evidence_text=evidence_text, header=header,
                        document_exercice=document_exercice, rule=rule,
                    )
                )
                break

    # Présentation IFRS fréquente : « Résultat par action » (sans répéter
    # « de base ») immédiatement suivi de « Résultat par action dilué ».
    # La première ligne est alors la ligne de base de la paire. On ne
    # l'infère que pour la même page, le même exercice/devise/composante
    # et à une ou deux lignes de distance, et la source reste explicite.
    for observation in eps:
        if observation.get("basis") != BASIS_UNKNOWN or observation.get("value") is None:
            continue
        evidence = observation.get("evidence") or {}
        line_index = evidence.get("line_index_on_page")
        if not isinstance(line_index, int):
            continue
        paired_diluted = [
            other
            for other in eps
            if other is not observation
            and other.get("basis") == BASIS_DILUTED
            and other.get("target_exercice") == observation.get("target_exercice")
            and other.get("currency") == observation.get("currency")
            and other.get("component") == observation.get("component")
            and (other.get("evidence") or {}).get("page") == evidence.get("page")
            and isinstance((other.get("evidence") or {}).get("line_index_on_page"), int)
            and 1 <= int((other.get("evidence") or {})["line_index_on_page"]) - line_index <= 2
        ]
        explicit_basic_nearby = any(
            other is not observation
            and other.get("basis") == BASIS_BASIC
            and other.get("target_exercice") == observation.get("target_exercice")
            and other.get("currency") == observation.get("currency")
            and other.get("component") == observation.get("component")
            and (other.get("evidence") or {}).get("page") == evidence.get("page")
            for other in eps
        )
        if paired_diluted and not explicit_basic_nearby:
            observation["basis"] = BASIS_BASIC
            observation["basis_source"] = "LIGNE_NON_DILUEE_IMMEDIATEMENT_SUIVIE_DE_LA_LIGNE_DILUEE"
            observation["ineligibility_reasons"] = [
                reason
                for reason in observation.get("ineligibility_reasons") or []
                if reason != "BASE_DE_BASE_OU_DILUE_NON_PRECISEE"
            ]
            observation["eligible_fcfa_total_basic"] = (
                not observation["ineligibility_reasons"] and observation.get("value") is not None
            )

    # Une composante poursuivie devient un total équivalent uniquement si
    # la composante arrêtée du même tableau/document est néant ou zéro pour
    # le même exercice, la même devise et la même base. Sinon, aucune somme
    # implicite n'est promue en BPA publié.
    discontinued_by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for obs in eps:
        if obs.get("component") == COMPONENT_DISCONTINUED:
            # Un tiret néant vaut pour toutes les traductions de devise de
            # la même ligne ; la devise n'entre donc pas dans la clé.
            discontinued_by_key[(obs.get("target_exercice"), obs.get("basis"))].append(obs)
    complete_document_pages = _pages_are_complete_sequence(pages)
    discontinued_result_evidence = _has_discontinued_result_evidence(pages)
    contexts_by_page = {
        _page_number(page, index + 1): (
            page_contexts[index] if index < len(page_contexts) else {}
        )
        for index, page in enumerate(pages)
    }
    for obs in eps:
        if obs.get("component") != COMPONENT_CONTINUING:
            continue
        discontinued = discontinued_by_key.get((obs.get("target_exercice"), obs.get("basis"))) or []
        page_context = contexts_by_page.get((obs.get("evidence") or {}).get("page")) or {}
        no_discontinued_component_in_complete_statement = bool(
            complete_document_pages
            and not discontinued_by_key
            and not discontinued_result_evidence
            and "COMPTE_DE_RESULTAT" in (page_context.get("statement_kinds") or [])
        )
        if discontinued and all(item.get("is_dash") or item.get("value") == 0 for item in discontinued):
            obs["component"] = COMPONENT_TOTAL_EQUIVALENT
            obs["component_source"] = "COMPOSANTE_ARRETEE_NEANT_OU_ZERO_DANS_LE_MEME_DOCUMENT"
            obs["ineligibility_reasons"] = [
                reason for reason in obs.get("ineligibility_reasons") or []
                if reason != "COMPOSANTE_ET_NON_TOTAL_PUBLIE"
            ]
            obs["eligible_fcfa_total_basic"] = not obs["ineligibility_reasons"] and obs.get("value") is not None
        elif no_discontinued_component_in_complete_statement:
            # Vintage complète dont le compte de résultat ne présente
            # aucune composante arrêtée chiffrée ni BPA de composante :
            # le BPA des activités poursuivies y est le BPA total de
            # cette vintage. La source reste explicite et révisable.
            obs["component"] = COMPONENT_TOTAL_EQUIVALENT
            obs["component_source"] = "AUCUNE_COMPOSANTE_ARRETEE_DETECTEE_DANS_LE_DOCUMENT_COMPLET"
            obs["ineligibility_reasons"] = [
                reason for reason in obs.get("ineligibility_reasons") or []
                if reason != "COMPOSANTE_ET_NON_TOTAL_PUBLIE"
            ]
            obs["eligible_fcfa_total_basic"] = not obs["ineligibility_reasons"] and obs.get("value") is not None

    # Traduction FCFA des chiffres clés : la ligne donne simultanément
    # une valeur en devise d'origine et sa traduction FCFA, sans répéter
    # « de base » ni la composante. Elle ne devient éligible que si la
    # valeur compagne égale, à l'arrondi publié près, le BPA de base
    # total/total-équivalent du compte de résultat du même document.
    def _rounded_values_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
        if not isinstance(left.get("value"), (int, float)) or not isinstance(right.get("value"), (int, float)):
            return False
        decimals = [
            int(item["published_decimals"])
            for item in (left, right)
            if isinstance(item.get("published_decimals"), int)
        ]
        if decimals:
            tolerance = 0.5 * (10 ** -min(decimals)) + 1e-9
        else:
            tolerance = max(abs(float(left["value"])), abs(float(right["value"]))) * 0.006
        return abs(float(left["value"]) - float(right["value"])) <= tolerance

    for observation in eps:
        if (
            observation.get("source_kind") != "CHIFFRES_CLES"
            or observation.get("currency") != CURRENCY_FCFA
            or observation.get("basis") != BASIS_UNKNOWN
            or observation.get("component") != COMPONENT_UNKNOWN
            or observation.get("value") is None
        ):
            continue
        evidence = observation.get("evidence") or {}
        companions = [
            other
            for other in eps
            if other is not observation
            and other.get("source_kind") == "CHIFFRES_CLES"
            and other.get("currency") not in (CURRENCY_FCFA, CURRENCY_UNKNOWN)
            and other.get("target_exercice") == observation.get("target_exercice")
            and (other.get("evidence") or {}).get("page") == evidence.get("page")
            and (other.get("evidence") or {}).get("line_index_on_page")
            == evidence.get("line_index_on_page")
        ]
        if not companions:
            continue
        # S'il existe déjà un BPA FCFA direct dans l'état primaire, il
        # prime ; ne pas créer un second groupe arrondi concurrent.
        if any(
            other.get("currency") == CURRENCY_FCFA
            and other.get("source_kind") != "CHIFFRES_CLES"
            and other.get("basis") == BASIS_BASIC
            and other.get("component") in {COMPONENT_TOTAL, COMPONENT_TOTAL_EQUIVALENT}
            and other.get("target_exercice") == observation.get("target_exercice")
            for other in eps
        ):
            continue
        reference = next(
            (
                other
                for companion in companions
                for other in eps
                if other.get("source_kind") != "CHIFFRES_CLES"
                and other.get("currency") == companion.get("currency")
                and other.get("target_exercice") == observation.get("target_exercice")
                and other.get("basis") == BASIS_BASIC
                and other.get("component") in {COMPONENT_TOTAL, COMPONENT_TOTAL_EQUIVALENT}
                and _rounded_values_match(companion, other)
            ),
            None,
        )
        if reference is None:
            continue
        observation["basis"] = BASIS_BASIC
        observation["basis_source"] = "VALEUR_COMPAGNE_EGALE_AU_BPA_DE_BASE_DU_MEME_DOCUMENT"
        observation["component"] = reference.get("component")
        observation["component_source"] = "COMPOSANTE_DU_BPA_DE_BASE_DU_MEME_DOCUMENT"
        if reference.get("accounting_scope") not in (None, SCOPE_UNKNOWN):
            observation["accounting_scope"] = reference.get("accounting_scope")
            observation["accounting_scope_source"] = "COMPTE_DE_RESULTAT_DU_MEME_DOCUMENT"
        if reference.get("framework") not in (None, "NON_PROUVE"):
            observation["framework"] = reference.get("framework")
        observation["ineligibility_reasons"] = [
            reason
            for reason in observation.get("ineligibility_reasons") or []
            if reason
            not in {
                "BASE_DE_BASE_OU_DILUE_NON_PRECISEE",
                "COMPOSANTE_NON_PRECISEE_DANS_LES_CHIFFRES_CLES",
            }
        ]
        observation["eligible_fcfa_total_basic"] = (
            not observation["ineligibility_reasons"] and observation.get("value") is not None
        )

    def dedupe(items: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
        seen: set[tuple[Any, ...]] = set()
        output: list[dict[str, Any]] = []
        for item in items:
            key = tuple(item.get(field) for field in fields) + (
                (item.get("evidence") or {}).get("page"),
                (item.get("evidence") or {}).get("line_original"),
            )
            if key not in seen:
                seen.add(key)
                output.append(item)
        return output

    return {
        "parser_version": EPS_PARSER_VERSION,
        "eps": dedupe(eps, ("value", "currency", "basis", "component", "accounting_scope", "target_exercice")),
        "shares": dedupe(shares, ("value", "denominator_kind", "accounting_scope", "target_exercice")),
        "numerators": dedupe(numerators, ("value", "numerator_kind", "currency", "component", "target_exercice")),
        "ignored": ignored,
    }


# ---------------------------------------------------------------------------
# 3. Cohérence comptable et quarantaine
# ---------------------------------------------------------------------------

def assess_eps_arithmetic(
    published_eps: float | None,
    numerator: float | None,
    denominator: float | None,
    *,
    published_decimals: int | None = None,
    numerator_rounding_abs: float | None = None,
    base_tolerance_pct: float = 1.0,
    reference: str = "NUMERATEUR_SUR_DENOMINATEUR",
) -> dict[str, Any] | None:
    """Contrôle BPA imprimé contre ses intrants, tolérance d'arrondi incluse."""
    if published_eps is None or numerator is None or not denominator:
        return None
    recalculated = float(numerator) / float(denominator)
    decimals = int(published_decimals or 0)
    published_rounding = 0.5 * (10 ** -decimals)
    numerator_rounding_effect = abs(float(numerator_rounding_abs)) / abs(float(denominator)) if numerator_rounding_abs else 0.0
    allowed_abs = max(
        abs(float(published_eps)) * float(base_tolerance_pct) / 100.0,
        published_rounding + numerator_rounding_effect,
    )
    gap_abs = abs(float(published_eps) - recalculated)
    scale = max(abs(float(published_eps)), abs(recalculated))
    gap_pct = gap_abs / scale * 100 if scale else 0.0
    sign_mismatch = (float(published_eps) < 0) != (recalculated < 0) and published_eps != 0 and recalculated != 0
    concordant = not sign_mismatch and gap_abs <= allowed_abs
    return {
        "reference": reference,
        "published_eps": float(published_eps),
        "recalculated_eps": round(recalculated, 6),
        "numerator": float(numerator),
        "denominator": float(denominator),
        "absolute_gap": round(gap_abs, 6),
        "relative_gap_pct": round(gap_pct, 4),
        "allowed_absolute_gap": round(allowed_abs, 6),
        "published_rounding_abs": published_rounding,
        "numerator_rounding_effect_abs": round(numerator_rounding_effect, 6),
        "status": "CONCORDANT_ARRONDIS_INCLUS" if concordant else "ECART_EN_QUARANTAINE",
        "concordant": concordant,
        "sign_mismatch": sign_mismatch,
    }


def cluster_eps_values(
    values: list[float],
    *,
    relative_tolerance: float = 0.01,
    absolute_tolerance: float = 0.5,
) -> list[list[float]]:
    clusters: list[list[float]] = []
    for value in sorted(float(v) for v in values):
        placed = False
        for cluster in clusters:
            reference = cluster[0]
            if abs(value - reference) <= max(absolute_tolerance, abs(reference) * relative_tolerance):
                cluster.append(value)
                placed = True
                break
        if not placed:
            clusters.append([value])
    return clusters


def select_published_eps_candidate(
    candidate_groups: list[dict[str, Any]],
    arithmetic_checks_by_value: dict[float, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Choisit un BPA seulement s'il est unique ou arithmétiquement résolu.

    Deux valeurs publiées incompatibles ne sont jamais départagées par le
    seul nombre d'occurrences : soit un contrôle numérateur/dénominateur
    soutient exactement une valeur, soit l'observation part en quarantaine.
    """
    eligible = [
        group for group in candidate_groups
        if isinstance(group.get("value"), (int, float))
        and group.get("eligible", True)
    ]
    if not eligible:
        return {"status": "AUCUN_CANDIDAT_ELIGIBLE", "value": None, "group": None, "reasons": []}
    values = [float(group["value"]) for group in eligible]
    clusters = cluster_eps_values(values)
    if len(clusters) == 1:
        group = max(eligible, key=lambda item: (item.get("documents_confirmants") or 0, item.get("occurrences") or 0))
        return {"status": "VALEUR_UNIQUE_OU_CONCORDANTE", "value": float(group["value"]), "group": group, "reasons": []}

    supported: list[dict[str, Any]] = []
    checks = arithmetic_checks_by_value or {}
    for group in eligible:
        check = checks.get(float(group["value"]))
        if check and check.get("concordant"):
            supported.append(group)
    supported_values = cluster_eps_values([float(group["value"]) for group in supported]) if supported else []
    if len(supported_values) == 1:
        group = supported[0]
        return {
            "status": "DIVERGENCE_RESOLUE_PAR_CONTROLE_ARITHMETIQUE",
            "value": float(group["value"]),
            "group": group,
            "reasons": ["AUTRES_VALEURS_PUBLIEES_NON_SOUTENUES_PAR_LE_CONTROLE"],
        }
    return {
        "status": "QUARANTAINE_VALEURS_PUBLIEES_DIVERGENTES",
        "value": None,
        "group": None,
        "reasons": ["PLUSIEURS_VALEURS_ELIGIBLES_INCOMPATIBLES_SANS_RESOLUTION_UNIQUE"],
        "candidate_values": sorted(values),
    }


# ---------------------------------------------------------------------------
# 4. Opérations sur le capital
# ---------------------------------------------------------------------------

def normalize_capital_event(event: dict[str, Any]) -> dict[str, Any]:
    """Valide un événement de capital sourcé ; aucun facteur deviné."""
    required = ("ticker", "event_type", "factor_new_shares_per_old_share", "source")
    missing = [field for field in required if not event.get(field)]
    if missing:
        raise ValueError(f"Événement de capital incomplet : {', '.join(missing)}")
    factor = float(event["factor_new_shares_per_old_share"])
    if factor <= 0:
        raise ValueError("Le facteur d'un événement de capital doit être positif.")
    event_type = normalize_key(event["event_type"]).replace(" ", "_").upper()
    source = event.get("source") or {}
    if not isinstance(source, dict) or not (source.get("url") or source.get("document")):
        raise ValueError("Un événement de capital exige une source identifiable.")
    return {
        **event,
        "ticker": str(event["ticker"]).upper(),
        "event_type": event_type,
        "factor_new_shares_per_old_share": factor,
        "adjustment_available": event_type in ADJUSTABLE_CAPITAL_EVENT_TYPES,
        "schema_version": CAPITAL_EVENT_SCHEMA_VERSION,
    }


def load_verified_capital_events(path: str | Path | None = None) -> list[dict[str, Any]]:
    event_path = Path(path) if path else Path(__file__).resolve().parent / "capital_events_verified.json"
    if not event_path.exists():
        return []
    payload = json.loads(event_path.read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else payload
    return [normalize_capital_event(event) for event in events or []]


def _event_accounting_date(event: dict[str, Any]) -> str | None:
    return (
        event.get("accounting_effective_date")
        or event.get("entitlement_date")
        or event.get("effective_date")
        or event.get("decision_date")
    )


def capital_events_between(
    events: Iterable[dict[str, Any]],
    ticker: str,
    start_exclusive: str,
    end_inclusive: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for raw_event in events:
        try:
            event = normalize_capital_event(raw_event)
        except (TypeError, ValueError):
            continue
        if event["ticker"] != ticker.upper():
            continue
        event_date = _event_accounting_date(event)
        if event_date and start_exclusive < str(event_date) <= end_inclusive:
            selected.append(event)
    return sorted(selected, key=lambda item: str(_event_accounting_date(item) or ""))


def adjust_per_share_to_reference_unit(
    value: float,
    *,
    ticker: str,
    value_exercice: int,
    reference_exercice: int,
    events: Iterable[dict[str, Any]],
    value_share_unit_basis: str = "UNITE_D_ACTION_DE_L_EXERCICE_DE_LA_VALEUR",
) -> dict[str, Any]:
    """Convertit une valeur/action dans l'unité d'action d'un autre exercice.

    Seuls les fractionnements/regroupements et actions gratuites sourcés
    sont convertis mécaniquement. Une augmentation de capital en numéraire
    ou avec droit préférentiel bloque la conversion : son effet BPA dépend
    des termes et ne se résume pas au rapport des nombres d'actions.
    """
    if value_exercice == reference_exercice:
        return {
            "status": "SANS_AJUSTEMENT_MEME_EXERCICE",
            "raw_value": float(value),
            "adjusted_value": float(value),
            "factor_applied_to_denominator": 1.0,
            "events": [],
            "share_unit_basis": value_share_unit_basis,
        }
    forward = reference_exercice > value_exercice
    start = f"{min(value_exercice, reference_exercice)}-12-31"
    end = f"{max(value_exercice, reference_exercice)}-12-31"
    selected = capital_events_between(events, ticker, start, end)
    blocking = [event for event in selected if not event.get("adjustment_available")]
    if blocking:
        return {
            "status": "NON_AJUSTABLE_EVENEMENT_DE_CAPITAL_A_TERME_A_ANALYSER",
            "raw_value": float(value),
            "adjusted_value": None,
            "factor_applied_to_denominator": None,
            "events": selected,
            "blocking_events": blocking,
            "share_unit_basis": value_share_unit_basis,
        }
    factor = 1.0
    for event in selected:
        factor *= float(event["factor_new_shares_per_old_share"])
    adjusted = float(value) / factor if forward else float(value) * factor
    return {
        "status": "AJUSTE_PAR_EVENEMENTS_SOURCES" if selected else "AUCUN_EVENEMENT_SOURCE_ENTRE_LES_EXERCICES",
        "raw_value": float(value),
        "adjusted_value": adjusted,
        "factor_applied_to_denominator": factor if forward else (1 / factor if factor else None),
        "events": selected,
        "share_unit_basis": value_share_unit_basis,
    }


_COMMON_FACTORS = (100, 50, 20, 10, 5, 4, 3, 2, 1.5)


def _suspected_integer_factor(ratio: float) -> float | None:
    candidates = list(_COMMON_FACTORS) + [1 / factor for factor in _COMMON_FACTORS]
    for candidate in candidates:
        if abs(ratio - candidate) <= max(0.01, abs(candidate) * 0.01):
            return candidate
    return None


def detect_share_count_changes(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drapeaux de rupture du nombre d'actions, sans inventer l'événement."""
    ordered = sorted(
        (point for point in points if isinstance(point.get("exercice"), int)),
        key=lambda point: int(point["exercice"]),
    )
    changes: list[dict[str, Any]] = []
    for previous, current in zip(ordered, ordered[1:]):
        for basis in ("end_shares", "weighted_shares"):
            old = previous.get(basis)
            new = current.get(basis)
            if not isinstance(old, (int, float)) or not isinstance(new, (int, float)) or not old or not new:
                continue
            ratio = float(new) / float(old)
            if abs(ratio - 1) <= 0.001:
                continue
            suspected = _suspected_integer_factor(ratio)
            changes.append(
                {
                    "from_exercice": int(previous["exercice"]),
                    "to_exercice": int(current["exercice"]),
                    "basis": basis,
                    "previous_shares": float(old),
                    "current_shares": float(new),
                    "ratio_current_to_previous": round(ratio, 6),
                    "suspected_factor_to_document": suspected,
                    "status": "FACTEUR_ROND_A_DOCUMENTER" if suspected else "CHANGEMENT_A_DOCUMENTER",
                    "chainable_without_event": False,
                }
            )
    return changes

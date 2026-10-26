#!/usr/bin/env python3
"""Audit BPA 2016-2025 des 480 cellules société-exercice.

Ce harnais prolonge le pilote cinq sociétés après la régression réelle
50/50, mais il reste volontairement en **mode audit** :

- inventaire BRVM des rapports en deux passages ;
- dates d'introduction lues sur les profils officiels BRVM lorsqu'elles
  sont publiées ;
- sélection bornée et tracée des documents annuels candidats ;
- extraction d'un PDF par sous-processus, avec journal JSONL reprenable ;
- agrégation par société-exercice avec les mêmes règles que la
  régression du pilote ;
- statuts BPA et documentaires séparés, preuves conservées ;
- **aucune écriture dans le dataset publié**.

Une absence de BPA ne devient ``NON_PUBLIE_DANS_SOURCES_VERIFIEES`` que
si un état annuel primaire couvrant effectivement l'exercice a été lu.
Dans les autres cas, le statut reste ``NON_RECHERCHE``,
``DOCUMENT_INTROUVABLE`` ou ``ILLISIBLE`` selon la preuve disponible.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

sys.dont_write_bytecode = True
INGESTION_DIR = Path(__file__).resolve().parent
ROOT = INGESTION_DIR.parent
sys.path.insert(0, str(INGESTION_DIR))

from bs4 import BeautifulSoup  # noqa: E402

import collect as sigma_collect  # noqa: E402
from collect import (  # noqa: E402
    ANNUAL_DOC_PRIORITY,
    _report_pages_by_ticker,
    build_issuer_variant_map,
    canonical_issuer_key,
    classify_eps_observation,
    classify_report_document,
    clean_text,
    extract_annual_figures,
    fetch,
    load_verified_capital_events,
    make_session,
    normalize_key,
    parse_french_long_date,
    scrape_report_pages,
)
from regress_pilot_bpa_5 import (  # noqa: E402
    _aggregate_ticker,
    _is_aggregable,
    _json_default,
    _selected_confirmation_count,
)

DATASET_PATH = ROOT / "web" / "data" / "data.json"
DEFAULT_OUTPUT_DIR = ROOT / "audits" / "audit_bpa_480_2016_2025_2026-10-25"
DEFAULT_CACHE_DIR = ROOT / ".cache" / "audit-bpa-480-pdf"
YEARS = list(range(2016, 2026))
PROFILE_INDEX_URL = "https://www.brvm.org/fr/emetteurs/societes-cotees"

STATUS_NOT_PUBLISHED = sigma_collect.EPS_STATUS_NOT_PUBLISHED_IN_VERIFIED_SOURCES
STATUS_NOT_RESEARCHED = sigma_collect.EPS_STATUS_NOT_RESEARCHED
STATUS_NOT_FOUND = sigma_collect.EPS_STATUS_DOCUMENT_NOT_FOUND
STATUS_UNREADABLE = sigma_collect.EPS_STATUS_UNREADABLE
STATUS_NOT_APPLICABLE = sigma_collect.EPS_STATUS_NOT_APPLICABLE


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(payload), ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _code_fingerprint() -> str:
    digest = hashlib.sha256()
    for filename in ("collect.py", "eps_evidence.py", "regress_pilot_bpa_5.py", "audit_bpa_480.py"):
        path = INGESTION_DIR / filename
        digest.update(filename.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _dataset() -> dict[str, Any]:
    return _load_json(DATASET_PATH)


def _companies_minimal(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for company in companies:
        output.append(
            {
                "ticker": company.get("ticker"),
                "name": company.get("name"),
                "sector": company.get("sector"),
                "latest_boc": {"name": (company.get("latest_boc") or {}).get("name")},
            }
        )
    return output


def _parse_tickers(value: str | None) -> set[str] | None:
    if not value:
        return None
    tickers = {item.strip().upper() for item in value.split(",") if item.strip()}
    return tickers or None


# ---------------------------------------------------------------------------
# Inventaire : pages rapports, profils et introductions
# ---------------------------------------------------------------------------


def _fresh_report_pages(
    session: Any,
    dataset_pages: list[dict[str, str]],
    *,
    passes: int,
) -> tuple[list[dict[str, str]], list[str]]:
    by_url: dict[str, dict[str, str]] = {}
    for page in dataset_pages:
        url = str(page.get("url") or "")
        if url:
            by_url[url] = {"label": str(page.get("label") or ""), "url": url}
    warnings: list[str] = []
    for pass_index in range(1, max(1, passes) + 1):
        try:
            for page in scrape_report_pages(session):
                url = str(page.get("url") or "")
                if not url:
                    continue
                current = by_url.get(url)
                if current is None or (not current.get("label") and page.get("label")):
                    by_url[url] = {"label": str(page.get("label") or ""), "url": url}
        except Exception as exc:  # l'index BRVM est instable : repli dataset tracé
            warnings.append(
                f"Index des pages rapports, passage {pass_index} en échec : {type(exc).__name__}: {exc}"
            )
    return sorted(by_url.values(), key=lambda item: (item["label"].lower(), item["url"])), warnings


def _parse_listing_profile(html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    heading = clean_text(soup.find("h1").get_text(" ", strip=True)) if soup.find("h1") else ""
    text = clean_text(soup.get_text(" ", strip=True))
    # Certains profils affichent un symbole en deux tokens (ex. « BOA CI »)
    # distinct du ticker du dataset (BOAC). On conserve le libellé brut ;
    # la résolution vers le ticker se fait ensuite par le titre/les alias.
    symbol_match = re.search(r"Symbole\s*:\s*([A-Z]{2,6}(?:[ -][A-Z]{2,3})?)\b", text)
    symbol_raw = clean_text(symbol_match.group(1)) if symbol_match else None
    date_match = re.search(
        r"Date d[’']introduction à la BRVM\s*:\s*"
        r"(\d{1,2}/\d{1,2}/\d{4}|\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4})",
        text,
        flags=re.I,
    )
    listing_date = None
    listing_date_raw = date_match.group(1) if date_match else None
    if listing_date_raw:
        slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", listing_date_raw)
        if slash_match:
            listing_date = (
                f"{int(slash_match.group(3)):04d}-{int(slash_match.group(2)):02d}-"
                f"{int(slash_match.group(1)):02d}"
            )
        else:
            listing_date = parse_french_long_date(listing_date_raw)
    return {
        "profile_url": url,
        "profile_title": title,
        "profile_heading": heading,
        "symbol": symbol_raw,
        "symbol_normalized": re.sub(r"[^A-Z0-9]", "", symbol_raw or "") or None,
        "listing_date_raw": listing_date_raw,
        "listing_date": listing_date,
        "listing_year": int(listing_date[:4]) if listing_date else None,
        "listing_status": "LU_SUR_PROFIL_OFFICIEL_BRVM" if listing_date else "NON_RECHERCHE",
    }


def _slugify_profile_candidate(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().replace("'", "").replace("’", "")
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return re.sub(r"-+", "-", normalized)


def _company_profile_search_queries(company: dict[str, Any]) -> list[str]:
    ticker = str(company.get("ticker") or "")
    queries = [f"Symbole {ticker}", ticker, str(company.get("name") or "")]
    latest_name = str((company.get("latest_boc") or {}).get("name") or "")
    queries.append(latest_name)
    for alias, alias_ticker in sigma_collect.NEWS_TICKER_ALIASES.items():
        if alias_ticker == ticker:
            queries.append(str(alias).upper())
    for alias, alias_ticker in sigma_collect.REPORT_LABEL_ALIASES.items():
        if alias_ticker == ticker:
            queries.append(str(alias).upper())
    output: list[str] = []
    seen: set[str] = set()
    for query in queries:
        cleaned = clean_text(query)
        key = normalize_key(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def _company_profile_slug_candidates(company: dict[str, Any]) -> list[str]:
    ticker = str(company.get("ticker") or "")
    values = [str(company.get("name") or "")]
    values.append(str((company.get("latest_boc") or {}).get("name") or ""))
    for alias, alias_ticker in sigma_collect.NEWS_TICKER_ALIASES.items():
        if alias_ticker == ticker:
            values.append(str(alias))
    for alias, alias_ticker in sigma_collect.REPORT_LABEL_ALIASES.items():
        if alias_ticker == ticker:
            values.append(str(alias))
    urls: list[str] = []
    seen: set[str] = set()
    stopwords = {"of", "de", "du", "des", "et", "la", "le", "les", "pour", "au", "aux", "en", "d"}
    for value in values:
        slug = _slugify_profile_candidate(value)
        variants = [slug]
        reduced = "-".join(token for token in slug.split("-") if token and token not in stopwords)
        if reduced and reduced != slug:
            variants.append(reduced)
        for variant in variants:
            if len(variant) < 4 or variant in seen:
                continue
            seen.add(variant)
            urls.append(f"{PROFILE_INDEX_URL}/{variant}")
    return urls


def _scrape_listing_profiles(
    session: Any,
    companies: list[dict[str, Any]],
    *,
    max_index_pages: int = 6,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Découvrir les profils officiels malgré l'index paginé instable.

    L'index BRVM retourne parfois le même bloc de dix profils pour
    plusieurs valeurs de ``?page=``. On ne s'arrête donc pas au premier
    doublon : union de deux passages, puis recherche interne BRVM par
    symbole/nom pour les émetteurs non résolus, puis URL candidates
    dérivées des noms connus. Une URL n'est retenue que si le profil
    fetché affiche un symbole du registre.
    """
    known_tickers = {str(company.get("ticker")) for company in companies}
    companies_by_ticker = {str(company.get("ticker")): company for company in companies}
    variants = build_issuer_variant_map(companies)
    for alias, ticker in sigma_collect.REPORT_LABEL_ALIASES.items():
        variants.setdefault(canonical_issuer_key(alias), ticker)
    for alias, ticker in sigma_collect.NEWS_TICKER_ALIASES.items():
        variants.setdefault(canonical_issuer_key(alias), ticker)
    warnings: list[str] = []
    profiles: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    fetched_urls: set[str] = set()

    def record_profile(url: str, source: str, expected_ticker: str | None = None) -> None:
        if not url or url in fetched_urls:
            return
        fetched_urls.add(url)
        try:
            response = session.get(url, timeout=30)
            if response.status_code != 200:
                return
            profile = _parse_listing_profile(response.text, url)
        except Exception as exc:
            warnings.append(f"Profil officiel illisible {url} ({source}) : {exc}")
            return
        profile["discovered_via"] = source

        resolved_ticker: str | None = None
        resolution: str | None = None
        symbol = profile.get("symbol")
        symbol_normalized = profile.get("symbol_normalized")
        if symbol in known_tickers:
            resolved_ticker = str(symbol)
            resolution = "SYMBOLE_EXACT"
        elif symbol_normalized in known_tickers:
            resolved_ticker = str(symbol_normalized)
            resolution = "SYMBOLE_NORMALISE_EXACT"
        elif symbol:
            by_symbol_label = variants.get(canonical_issuer_key(str(symbol)))
            if by_symbol_label in known_tickers:
                resolved_ticker = str(by_symbol_label)
                resolution = "SYMBOLE_VIA_ALIAS"
        if resolved_ticker is None:
            heading_matches = sigma_collect.match_tickers_in_text(
                f"{profile.get('profile_heading') or ''} {profile.get('profile_title') or ''}",
                companies,
            )
            if len(set(heading_matches)) == 1 and str(heading_matches[0]) in known_tickers:
                resolved_ticker = str(heading_matches[0])
                resolution = "TITRE_OFFICIEL_DU_PROFIL"
        if resolved_ticker is None and expected_ticker in known_tickers and symbol:
            symbol_first_token = canonical_issuer_key(str(symbol)).split()[0]
            expected_alias_first_tokens = {
                canonical_issuer_key(alias).split()[0]
                for alias, alias_ticker in {
                    **sigma_collect.NEWS_TICKER_ALIASES,
                        **sigma_collect.REPORT_LABEL_ALIASES,
                }.items()
                if alias_ticker == expected_ticker and canonical_issuer_key(alias).split()
            }
            if symbol_first_token and symbol_first_token in expected_alias_first_tokens:
                resolved_ticker = expected_ticker
                resolution = "SYMBOLE_AFFICHE_COMPATIBLE_AVEC_ALIAS_CIBLE"
        profile["resolved_ticker"] = resolved_ticker
        profile["ticker_resolution_method"] = resolution
        if resolved_ticker:
            # Le champ symbol du profil reste le libellé officiel brut ;
            # la résolution séparée évite de le confondre avec le ticker.
            previous = profiles.get(resolved_ticker)
            if previous is None or (not previous.get("listing_date") and profile.get("listing_date")):
                profiles[resolved_ticker] = profile
        elif profile.get("listing_date") or profile.get("symbol"):
            unmatched.append(profile)

    profile_urls: set[str] = set()
    for _pass_index in range(2):
        for page_index in range(max_index_pages):
            url = PROFILE_INDEX_URL if page_index == 0 else f"{PROFILE_INDEX_URL}?page={page_index}"
            try:
                soup = BeautifulSoup(str(fetch(session, url)), "lxml")
            except Exception as exc:
                warnings.append(f"Index des sociétés cotées p.{page_index} en échec : {exc}")
                continue
            for anchor in soup.select("a[href]"):
                href = urljoin(url, anchor.get("href") or "").split("#", 1)[0]
                if "/fr/emetteurs/societes-cotees/" in href and href.rstrip("/") != PROFILE_INDEX_URL and "?" not in href:
                    profile_urls.add(href)
    for url in sorted(profile_urls):
        record_profile(url, "INDEX_OFFICIEL_BRVM")

    # Recherche interne officielle pour les émetteurs absents des blocs
    # effectivement retournés par l'index.
    for ticker in sorted(known_tickers - set(profiles)):
        company = companies_by_ticker.get(ticker) or {}
        found_urls: set[str] = set()
        for query in _company_profile_search_queries(company):
            search_url = "https://www.brvm.org/fr/search/node/" + quote(query, safe="")
            try:
                response = session.get(search_url, timeout=30)
                if response.status_code != 200:
                    continue
                soup = BeautifulSoup(response.text, "lxml")
            except Exception as exc:
                warnings.append(f"Recherche de profil {ticker} ({query}) en échec : {exc}")
                continue
            for anchor in soup.select("a[href]"):
                href = urljoin(search_url, anchor.get("href") or "").split("#", 1)[0]
                if "/fr/emetteurs/societes-cotees/" in href and href.rstrip("/") != PROFILE_INDEX_URL and "?" not in href:
                    found_urls.add(href)
            if found_urls:
                break
        for url in sorted(found_urls):
            record_profile(
                url,
                "RECHERCHE_INTERNE_BRVM_PAR_SYMBOLE_OU_NOM",
                expected_ticker=ticker,
            )

    # Dernier repli : slugs publics dérivés des noms/alias connus. Le
    # symbole lu sur la page reste le garde-fou d'identité.
    for ticker in sorted(known_tickers - set(profiles)):
        company = companies_by_ticker.get(ticker) or {}
        for url in _company_profile_slug_candidates(company):
            record_profile(url, "SLUG_DERIVE_DU_NOM", expected_ticker=ticker)
            if ticker in profiles:
                break

    return profiles, unmatched, warnings


def _crawl_ticker_documents(
    session: Any,
    ticker: str,
    report_pages: list[dict[str, str]],
    *,
    max_pages: int,
    passes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    documents: dict[str, dict[str, Any]] = {}
    origins: dict[str, set[str]] = defaultdict(set)
    page_stats: list[dict[str, Any]] = []
    warnings: list[str] = []

    for pass_index in range(1, max(1, passes) + 1):
        for report_page in report_pages:
            base_url = str(report_page.get("url") or "")
            if not base_url:
                continue
            exhausted = False
            for page_index in range(max(1, max_pages)):
                page_url = base_url if page_index == 0 else f"{base_url}?page={page_index}"
                try:
                    soup = BeautifulSoup(str(fetch(session, page_url)), "lxml")
                except Exception as exc:
                    page_stats.append(
                        {
                            "pass": pass_index,
                            "report_page_url": base_url,
                            "page_index": page_index,
                            "page_url": page_url,
                            "error": f"{type(exc).__name__}: {exc}",
                            "pdf_links": 0,
                            "new_documents": 0,
                        }
                    )
                    warnings.append(f"{ticker} {page_url} : {exc}")
                    break
                pdf_links = 0
                new_documents = 0
                for anchor in soup.select("a[href]"):
                    href = urljoin(page_url, anchor.get("href") or "")
                    if ".pdf" not in href.lower():
                        continue
                    pdf_links += 1
                    origins[href].add(f"pass{pass_index}:{page_url}")
                    if href in documents:
                        continue
                    classified = classify_report_document(
                        href,
                        link_text=anchor.get_text(" ", strip=True),
                    )
                    classified["report_page_url"] = base_url
                    classified["report_page_label"] = report_page.get("label")
                    documents[href] = classified
                    new_documents += 1
                page_stats.append(
                    {
                        "pass": pass_index,
                        "report_page_url": base_url,
                        "page_index": page_index,
                        "page_url": page_url,
                        "pdf_links": pdf_links,
                        "new_documents": new_documents,
                        "cumulated_documents": len(documents),
                    }
                )
                if pdf_links == 0 or new_documents == 0:
                    exhausted = True
                    break
            if not exhausted:
                page_stats.append(
                    {
                        "pass": pass_index,
                        "report_page_url": base_url,
                        "page_index": max_pages,
                        "warning": "MAX_PAGES_ATTEINT_SANS_EPUISEMENT_PROUVE",
                    }
                )

    output: list[dict[str, Any]] = []
    for url, document in documents.items():
        item = dict(document)
        item["found_in"] = sorted(origins.get(url) or [])
        output.append(item)
    output.sort(
        key=lambda doc: (
            doc.get("published_date") is None,
            str(doc.get("published_date") or ""),
            str(doc.get("label") or ""),
        ),
        reverse=True,
    )
    return output, page_stats, warnings


def _inventory_is_exhaustive(page_stats: list[dict[str, Any]]) -> bool:
    if not page_stats:
        return False
    if any(item.get("error") for item in page_stats):
        return False
    if any(item.get("warning") == "MAX_PAGES_ATTEINT_SANS_EPUISEMENT_PROUVE" for item in page_stats):
        return False
    return True


def _filename_coverage(document: dict[str, Any]) -> list[int]:
    """Exercices que le seul nom du document Peut couvrir (N, N-1, N-2)."""
    exercice = document.get("exercice")
    if not isinstance(exercice, int):
        return []
    return [year for year in (exercice, exercice - 1, exercice - 2) if year in YEARS]


def _published_year(document: dict[str, Any]) -> int | None:
    value = str(document.get("published_date") or "")
    match = re.match(r"(\d{4})-", value)
    return int(match.group(1)) if match else None


_RESCUE_LABEL_TERMS = (
    "etats financier",
    "etats financiers",
    "resultats financiers",
    "resultats annuels",
    "comptes annuels",
    "rapport annuel",
    "rapport de gestion",
    "rapport gestion",
    "etats de synthese",
    "etats financiers de synthese",
)


def _audit_doc_priority(document: dict[str, Any]) -> int | None:
    """Priorité d'ouverture propre à l'audit.

    Le pilote a montré que certains états annuels sont classés
    ``synthese_rapport_gestion`` ou ``autre`` par le seul nom de fichier
    (singulier, communication de résultats, rapport de gestion). Ces
    documents de secours sont ouverts après les types annuels reconnus ;
    le contenu décidera ensuite s'ils sont primaires, secondaires,
    intermédiaires ou d'un autre émetteur.
    """
    if str(document.get("selection_status") or "").startswith("EXCLU_"):
        return None
    doc_type = str(document.get("doc_type") or "")
    if doc_type in ANNUAL_DOC_PRIORITY:
        return ANNUAL_DOC_PRIORITY[doc_type]
    if doc_type == "synthese_rapport_gestion":
        return 7
    if doc_type == "presentation_resultats":
        return 8
    if doc_type == "autre":
        haystack = normalize_key(
            " ".join(
                str(document.get(field) or "")
                for field in ("label", "link_text", "filename", "url")
            )
        )
        interim_markers = (
            "semestriel",
            "trimestriel",
            "premier semestre",
            "deuxieme semestre",
            "troisieme trimestre",
            "30 juin",
            "31 mars",
            "30 septembre",
        )
        if any(term in haystack for term in _RESCUE_LABEL_TERMS) and not any(
            marker in haystack for marker in interim_markers
        ):
            return 9
    return None


def _is_annual_candidate(document: dict[str, Any]) -> bool:
    return _audit_doc_priority(document) is not None


def _build_inventory(
    *,
    companies: list[dict[str, Any]],
    dataset: dict[str, Any],
    tickers: set[str] | None,
    max_pages: int,
    passes: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    session = make_session()
    report_pages, report_warnings = _fresh_report_pages(
        session,
        list(dataset.get("report_pages") or []),
        passes=passes,
    )
    pages_by_ticker = _report_pages_by_ticker(companies, report_pages)
    profiles, unmatched_profiles, profile_warnings = _scrape_listing_profiles(session, companies)

    selected_companies = [
        company
        for company in companies
        if not tickers or str(company.get("ticker")) in tickers
    ]
    variants = build_issuer_variant_map(companies)
    for alias, ticker in sigma_collect.REPORT_LABEL_ALIASES.items():
        variants.setdefault(canonical_issuer_key(alias), ticker)
    aliases_by_ticker: dict[str, set[str]] = defaultdict(set)
    for alias, ticker in variants.items():
        aliases_by_ticker[str(ticker)].add(str(alias))
    for alias, ticker in sigma_collect.NEWS_TICKER_ALIASES.items():
        aliases_by_ticker[str(ticker)].add(str(alias))

    inventory: dict[str, Any] = {
        "schema_version": "sigma-audit-bpa-480-inventory-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_fingerprint": _code_fingerprint(),
        "dataset_generated_at": dataset.get("generated_at"),
        "dataset_sha256": _sha256_file(DATASET_PATH),
        "passes": passes,
        "max_pages_per_report_page": max_pages,
        "report_pages_indexed": report_pages,
        "listing_profiles_unmatched": unmatched_profiles,
        "warnings": [*report_warnings, *profile_warnings],
        "tickers": {},
    }
    registry: list[dict[str, Any]] = []

    for index, company in enumerate(selected_companies, start=1):
        ticker = str(company.get("ticker"))
        pages = pages_by_ticker.get(ticker, [])
        print(f"[inventaire {index}/{len(selected_companies)}] {ticker}", flush=True)
        documents, page_stats, crawl_warnings = _crawl_ticker_documents(
            session,
            ticker,
            pages,
            max_pages=max_pages,
            passes=passes,
        )
        annual_documents = [doc for doc in documents if _is_annual_candidate(doc)]
        covered = sorted({year for doc in annual_documents for year in _filename_coverage(doc)})
        profile = profiles.get(ticker) or {}
        listing_date = profile.get("listing_date")
        listing_year = profile.get("listing_year")
        ticker_inventory = {
            "company": company.get("name"),
            "sector": company.get("sector"),
            "report_pages": pages,
            "inventory_exhaustive": bool(pages) and _inventory_is_exhaustive(page_stats),
            "unique_pdf_count": len(documents),
            "annual_candidate_count": len(annual_documents),
            "filename_covered_years": covered,
            "filename_missing_years": [year for year in YEARS if year not in covered],
            "documents": documents,
            "page_stats": page_stats,
            "warnings": crawl_warnings,
            "listing": {
                "date": listing_date,
                "date_raw": profile.get("listing_date_raw"),
                "year": listing_year,
                "status": profile.get("listing_status") or "NON_RECHERCHE",
                "profile_url": profile.get("profile_url"),
                "profile_title": profile.get("profile_title"),
                "profile_heading": profile.get("profile_heading"),
                "symbol": profile.get("symbol"),
                "symbol_normalized": profile.get("symbol_normalized"),
                "resolved_ticker": profile.get("resolved_ticker"),
                "ticker_resolution_method": profile.get("ticker_resolution_method"),
                "discovered_via": profile.get("discovered_via"),
            },
        }
        inventory["tickers"][ticker] = ticker_inventory
        registry.append(
            {
                "ticker": ticker,
                "name": company.get("name"),
                "sector": company.get("sector"),
                "aliases_canoniques": sorted(aliases_by_ticker.get(ticker, set())),
                "report_pages": pages,
                "registry_status": "PAGE_RATTACHEE" if pages else "PAGE_OU_ALIAS_NON_RESOLU",
                "documents_indexes": len(documents),
                "annual_candidates_indexes": len(annual_documents),
                "filename_covered_years": covered,
                "listing_date": listing_date,
                "listing_date_raw": profile.get("listing_date_raw"),
                "listing_year": listing_year,
                "listing_year_status": profile.get("listing_status") or "NON_RECHERCHE",
                "listing_profile_url": profile.get("profile_url"),
                "listing_profile_symbol": profile.get("symbol"),
                "listing_ticker_resolution_method": profile.get("ticker_resolution_method"),
                "listing_profile_discovered_via": profile.get("discovered_via"),
            }
        )
    return inventory, registry


def _write_registry(output_dir: Path, registry: list[dict[str, Any]]) -> None:
    _write_json(output_dir / "issuer_registry.json", registry)
    fields = [
        "ticker", "name", "sector", "registry_status", "documents_indexes",
        "annual_candidates_indexes", "filename_covered_years", "listing_date",
        "listing_year", "listing_year_status", "listing_profile_url",
    ]
    with (output_dir / "issuer_registry.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in registry:
            flat = dict(row)
            flat["filename_covered_years"] = ";".join(str(year) for year in row.get("filename_covered_years") or [])
            writer.writerow({field: flat.get(field) for field in fields})


# ---------------------------------------------------------------------------
# Sélection des candidats à ouvrir
# ---------------------------------------------------------------------------


def _scope_rank(document: dict[str, Any]) -> int:
    scope = str(document.get("scope_hint") or "NON_PROUVE")
    if scope == "CONSOLIDE":
        return 0
    if scope in {"INDIVIDUEL", "SOCIAL"}:
        return 2
    return 1


def _framework_rank(document: dict[str, Any]) -> int:
    return 0 if document.get("framework_hint") == "IFRS" else 1


def _version_rank(document: dict[str, Any]) -> int:
    markers = {
        str(document.get("version_hint") or ""),
        *[str(item) for item in document.get("version_markers") or []],
    }
    if markers & {"CORRIGE", "AUDITE_CERTIFIE_OU_APPROUVE"}:
        return 0
    if markers & {"NON_AUDITE_OU_PROVISOIRE"}:
        return 2
    return 1


def _doc_sort_key(document: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _audit_doc_priority(document) if _audit_doc_priority(document) is not None else 99,
        _scope_rank(document),
        _framework_rank(document),
        _version_rank(document),
        str(document.get("published_date") or ""),
        str(document.get("label") or ""),
    )


def _doc_family(document: dict[str, Any]) -> str:
    doc_type = str(document.get("doc_type") or "")
    if doc_type in {"rapport_annuel", "rapport_activites_annuel"}:
        return "RAPPORT"
    if doc_type == "resultats_consolides":
        return "RESULTATS"
    if doc_type == "etats_condenses":
        return "CONDENSE"
    if doc_type == "synthese_rapport_gestion":
        return "SYNTHESE_GESTION"
    if doc_type == "presentation_resultats":
        return "PRESENTATION"
    if doc_type == "autre":
        return "SECOURS_A_CLASSER"
    return "ETATS"


def select_candidate_documents(
    documents: list[dict[str, Any]],
    *,
    max_per_doc_exercice: int = 6,
) -> list[dict[str, Any]]:
    """Bornage par exercice de document, avec diversité explicite.

    Les deux meilleurs documents classés entrent toujours. Les suivants
    doivent apporter une famille, un périmètre, un référentiel ou une
    version non encore représentés ; le reliquat complète ensuite dans
    l'ordre de priorité. Les documents sans exercice au nom sont limités
    à deux par année de publication afin de pouvoir prouver leur exercice
    de contenu sans ouvrir tout l'inventaire.
    """
    groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        if not _is_annual_candidate(document):
            continue
        exercice = document.get("exercice")
        if isinstance(exercice, int) and 2016 <= exercice <= 2026:
            groups[exercice].append(document)
        elif exercice is None:
            published = _published_year(document)
            if published is not None and 2017 <= published <= 2027:
                groups[f"SANS_ANNEE_NOM_PUBLIE_{published}"].append(document)

    selected: list[dict[str, Any]] = []
    for group_key, group in groups.items():
        ordered = sorted(group, key=_doc_sort_key)
        limit = 2 if isinstance(group_key, str) else max(1, max_per_doc_exercice)
        chosen: list[dict[str, Any]] = []
        chosen_urls: set[str] = set()

        def add(document: dict[str, Any]) -> None:
            url = str(document.get("url") or "")
            if url and url not in chosen_urls and len(chosen) < limit:
                chosen.append(document)
                chosen_urls.add(url)

        for document in ordered[:2]:
            add(document)
        represented = {
            (
                _doc_family(doc),
                str(doc.get("scope_hint") or "NON_PROUVE"),
                str(doc.get("framework_hint") or "NON_PROUVE"),
                str(doc.get("version_hint") or "NON_PRECISE"),
            )
            for doc in chosen
        }
        for document in ordered:
            signature = (
                _doc_family(document),
                str(document.get("scope_hint") or "NON_PROUVE"),
                str(document.get("framework_hint") or "NON_PROUVE"),
                str(document.get("version_hint") or "NON_PRECISE"),
            )
            if signature not in represented:
                add(document)
                represented.add(signature)
        for document in ordered:
            add(document)
        selected.extend(chosen)
    return selected


def _build_candidate_plan(
    inventory: dict[str, Any],
    *,
    max_per_doc_exercice: int,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for ticker, payload in sorted((inventory.get("tickers") or {}).items()):
        documents = list(payload.get("documents") or [])
        chosen = select_candidate_documents(documents, max_per_doc_exercice=max_per_doc_exercice)
        chosen.sort(
            key=lambda doc: (
                -(doc.get("exercice") if isinstance(doc.get("exercice"), int) else -1),
                *_doc_sort_key(doc),
            )
        )
        for rank, document in enumerate(chosen, start=1):
            url = str(document.get("url") or "")
            candidate_id = _sha256_bytes(f"{ticker}|{url}".encode("utf-8"))[:16]
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "ticker": ticker,
                    "url": url,
                    "selection_rank_for_ticker": rank,
                    "target_years_from_filename": _filename_coverage(document),
                    "classified_document": document,
                }
            )
    return {
        "schema_version": "sigma-audit-bpa-480-candidates-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_fingerprint": _code_fingerprint(),
        "max_per_doc_exercice": max_per_doc_exercice,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Extraction isolée et journal reprenable
# ---------------------------------------------------------------------------


def _iter_journal_keys(path: Path, code_fingerprint: str):
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


def _load_document_results(path: Path, code_fingerprint: str) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.exists():
        return []
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
                by_key[key] = row
    return list(by_key.values())


def _extract_one(
    *,
    candidate_file: Path,
    companies_file: Path,
    output_file: Path,
    cache_dir: Path,
    allow_ocr: bool,
) -> int:
    candidate = _load_json(candidate_file)
    companies = _load_json(companies_file)
    ticker = str(candidate.get("ticker") or "")
    classified = dict(candidate.get("classified_document") or {})
    url = str(candidate.get("url") or classified.get("url") or "")
    row: dict[str, Any] = {
        "candidate_id": candidate.get("candidate_id"),
        "ticker": ticker,
        "url": url,
        "code_fingerprint": _code_fingerprint(),
        "candidate": {
            "target_years_from_filename": candidate.get("target_years_from_filename") or [],
            "selection_rank_for_ticker": candidate.get("selection_rank_for_ticker"),
        },
        "classified_document": classified,
    }
    started = time.time()
    try:
        extraction = extract_annual_figures(
            make_session(),
            classified,
            cache_dir,
            allow_ocr=allow_ocr,
            expected_ticker=ticker,
            companies=companies,
        )
        row["extraction"] = extraction
        row["document_sha256"] = extraction.get("sha256")
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["document_sha256"] = None
    row["extraction_seconds"] = round(time.time() - started, 3)
    _write_json(output_file, row)
    return 0


def _run_extractions(
    *,
    plan: dict[str, Any],
    companies: list[dict[str, Any]],
    output_dir: Path,
    cache_dir: Path,
    allow_ocr: bool,
    doc_timeout: int,
    limit_docs: int | None,
    force: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    journal_path = output_dir / "document_results.jsonl"
    fingerprint = _code_fingerprint()
    if force and journal_path.exists():
        journal_path.unlink()
    existing_keys = set(_iter_journal_keys(journal_path, fingerprint))

    companies_file = output_dir / "companies_minimal.json"
    _write_json(companies_file, _companies_minimal(companies))
    work_dir = cache_dir / "_audit480_one"
    work_dir.mkdir(parents=True, exist_ok=True)

    candidates = list(plan.get("candidates") or [])
    attempted = 0
    with journal_path.open("a", encoding="utf-8") as journal:
        for index, candidate in enumerate(candidates, start=1):
            ticker = str(candidate.get("ticker") or "")
            url = str(candidate.get("url") or "")
            key = (ticker, url)
            classified = candidate.get("classified_document") or {}
            if key in existing_keys:
                print(f"[{index}/{len(candidates)}] {ticker} repris : {classified.get('label')}", flush=True)
                continue
            if limit_docs is not None and attempted >= limit_docs:
                print(f"Limite de {limit_docs} nouvelles extractions atteinte.", flush=True)
                break
            attempted += 1
            print(f"[{index}/{len(candidates)}] {ticker} extraction : {classified.get('label')}", flush=True)
            candidate_file = work_dir / f"{candidate.get('candidate_id')}.candidate.json"
            result_file = work_dir / f"{candidate.get('candidate_id')}.result.json"
            _write_json(candidate_file, candidate)
            if result_file.exists():
                result_file.unlink()
            command = [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "--phase",
                "extract-one",
                "--candidate-file",
                str(candidate_file),
                "--companies-file",
                str(companies_file),
                "--extract-output-file",
                str(result_file),
                "--cache-dir",
                str(cache_dir),
            ]
            if not allow_ocr:
                command.append("--no-ocr")
            row: dict[str, Any] | None = None
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=max(30, doc_timeout),
                    check=False,
                )
                if result_file.exists():
                    row = _load_json(result_file)
                else:
                    row = {
                        "candidate_id": candidate.get("candidate_id"),
                        "ticker": ticker,
                        "url": url,
                        "code_fingerprint": fingerprint,
                        "candidate": {
                            "target_years_from_filename": candidate.get("target_years_from_filename") or [],
                            "selection_rank_for_ticker": candidate.get("selection_rank_for_ticker"),
                        },
                        "classified_document": classified,
                        "error": (
                            f"SOUS_PROCESSUS_SANS_RESULTAT code={completed.returncode} "
                            f"stderr={(completed.stderr or '')[-1200:]}"
                        ),
                        "document_sha256": None,
                    }
            except subprocess.TimeoutExpired as exc:
                row = {
                    "candidate_id": candidate.get("candidate_id"),
                    "ticker": ticker,
                    "url": url,
                    "code_fingerprint": fingerprint,
                    "candidate": {
                        "target_years_from_filename": candidate.get("target_years_from_filename") or [],
                        "selection_rank_for_ticker": candidate.get("selection_rank_for_ticker"),
                    },
                    "classified_document": classified,
                    "error": f"EXTRACTION_TIMEOUT_APRES_{doc_timeout}S: {exc}",
                    "document_sha256": None,
                }
            journal.write(json.dumps(_json_ready(row), ensure_ascii=False, default=_json_default) + "\n")
            journal.flush()
            existing_keys.add(key)
            del row
            gc.collect()


# ---------------------------------------------------------------------------
# Agrégation et statuts
# ---------------------------------------------------------------------------


def _document_target_info(row: dict[str, Any], target_year: int) -> dict[str, Any]:
    classified = row.get("classified_document") or {}
    extraction = row.get("extraction") or {}
    document = extraction.get("document") or {}
    extraction_info = extraction.get("extraction") or {}
    columns = extraction.get("columns") or {}
    offset_columns = columns.get("colonnes") or {
        "0": columns.get("courant") or {},
        "1": columns.get("precedent") or {},
    }
    effective = extraction.get("effective_exercice")
    covers_by_column = False
    if isinstance(effective, int):
        for raw_offset, values in offset_columns.items():
            try:
                offset = int(raw_offset)
            except (TypeError, ValueError):
                continue
            if effective - offset == target_year and any(
                not key.startswith("_") for key in (values or {})
            ):
                covers_by_column = True
                break

    detailed = extraction.get("per_share_observations") or {}
    covers_by_per_share = any(
        isinstance(item, dict) and item.get("target_exercice") == target_year
        for family in ("eps", "shares", "numerators")
        for item in detailed.get(family) or []
    )
    classification = document.get("content_classification") or extraction.get("_content_classification") or {}
    primary = bool(
        classification.get("has_primary_financial_statements")
        and document.get("selection_rejection") is None
        and _is_aggregable(row)
    )
    # Un état primaire annuel prouve normalement l'exercice courant et
    # son comparatif N-1. L'exercice N-2 (document de l'année target+2)
    # n'est considéré couvert que si une colonne ou une observation par
    # action le nomme explicitement ci-dessus.
    covers_by_effective = bool(
        primary
        and isinstance(effective, int)
        and target_year <= effective <= target_year + 1
    )
    page_selection = document.get("page_selection") or extraction_info.get("page_selection") or {}
    native_characters = (
        extraction_info.get("native_text_characters")
        or page_selection.get("native_text_characters_all_pages")
        or 0
    )
    try:
        native_characters = int(native_characters)
    except (TypeError, ValueError):
        native_characters = 0
    has_any_figure = any(
        any(not key.startswith("_") for key in (values or {}))
        for values in offset_columns.values()
    )
    readable = bool(
        not row.get("error")
        and extraction
        and (
            native_characters >= 200
            or has_any_figure
            or covers_by_per_share
            or (extraction_info.get("ocr") or {}).get("used")
        )
    )
    return {
        "candidate_id": row.get("candidate_id"),
        "label": classified.get("label"),
        "url": row.get("url"),
        "doc_type": classified.get("doc_type"),
        "filename_exercice": classified.get("exercice"),
        "published_date": classified.get("published_date"),
        "opened": True,
        "error": row.get("error"),
        "sha256": row.get("document_sha256") or extraction.get("sha256"),
        "effective_exercice": effective,
        "content_exercice": extraction.get("content_exercice"),
        "identity_status": (document.get("identity") or {}).get("status"),
        "selection_rejection": document.get("selection_rejection"),
        "version_label": document.get("version_label"),
        "readable": readable,
        "primary_financial_statements": primary,
        "covers_target": bool(covers_by_column or covers_by_per_share or covers_by_effective),
        "covers_by_column": covers_by_column,
        "covers_by_per_share_observation": covers_by_per_share,
        "covers_by_effective_range": covers_by_effective,
        "extraction_method": extraction_info.get("method"),
        "ocr": extraction_info.get("ocr"),
        "native_text_characters": native_characters,
        "pages_total": page_selection.get("pages_total"),
        "pages_structured": page_selection.get("pages_structured"),
    }


def _inventory_candidates_for_target(documents: list[dict[str, Any]], target_year: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for document in documents:
        if not _is_annual_candidate(document):
            continue
        if target_year in _filename_coverage(document):
            output.append(document)
            continue
        if document.get("exercice") is None:
            published = _published_year(document)
            if published is not None and target_year + 1 <= published <= target_year + 3:
                output.append(document)
    return output


def _reference_scope(figures: dict[str, Any], eps_observations: list[dict[str, Any]]) -> str | None:
    scopes: set[str] = set()
    for key in (
        "resultat_net_attribuable_ordinaires",
        "resultat_net_part_groupe",
        "nombre_actions_moyen_pondere",
        "benefice_par_action",
    ):
        scope = (figures.get(key) or {}).get("accounting_scope")
        if scope not in (None, "NON_PROUVE", "MIXTE"):
            scopes.add(str(scope))
    for item in eps_observations:
        scope = item.get("accounting_scope")
        if scope not in (None, "NON_PROUVE", "MIXTE"):
            scopes.add(str(scope))
    if "CONSOLIDE" in scopes:
        return "CONSOLIDE"
    explicit = sorted(scopes & {"INDIVIDUEL", "SOCIAL"})
    return explicit[0] if len(explicit) == 1 else None


def _validation_level(metrics: dict[str, Any], figures: dict[str, Any]) -> str:
    if metrics.get("published_eps_fcfa") is not None:
        count = _selected_confirmation_count(metrics, figures) or 0
        if count >= 2:
            return "DEUX_DOCUMENTS_DISTINCTS"
        if (metrics.get("cross_check") or {}).get("concordant"):
            return "CONTROLE_ARITHMETIQUE_CONCORDANT"
        if metrics.get("status") == sigma_collect.EPS_STATUS_PUBLISHED_DIVERGENCE_RESOLVED:
            return "DIVERGENCE_RESOLUE_PAR_CONTROLE"
        return "EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE"
    if metrics.get("recalculated_comparable_eps_fcfa") is not None:
        return (
            "INTRANTS_CONFIRMES_DEUX_DOCUMENTS"
            if metrics.get("inputs_confirmed_two_documents")
            else "RECALCULE_INTRANT_NON_CONFIRME"
        )
    if metrics.get("parent_weighted_candidate_fcfa") is not None:
        return "CANDIDAT_PART_GROUPE_PONDEREE_A_VERIFIER"
    if metrics.get("indicative_result_per_end_share_fcfa") is not None:
        return "RATIO_INDICATIF_SEPARE"
    if metrics.get("quarantine"):
        return "QUARANTAINE"
    if metrics.get("nonretained_eps_observations"):
        return "PUBLICATION_DETECTEE_NON_RETENUE"
    return "AUCUNE_VALEUR_RETENUE"


def _trim_evidence(evidence: Any) -> Any:
    if isinstance(evidence, dict):
        output = dict(evidence)
        if isinstance(output.get("line_original"), str):
            output["line_original"] = output["line_original"][:600]
        if isinstance(output.get("line"), str):
            output["line"] = output["line"][:600]
        if isinstance(output.get("context_lines"), list):
            output["context_lines"] = [str(line)[:400] for line in output["context_lines"][:5]]
        return output
    if isinstance(evidence, list):
        return [_trim_evidence(item) for item in evidence[:5]]
    return evidence


def _trim_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    output = dict(metrics)
    nonretained = []
    for item in list(output.get("nonretained_eps_observations") or [])[:30]:
        if isinstance(item, dict):
            copy = dict(item)
            copy["evidence"] = _trim_evidence(copy.get("evidence"))
            nonretained.append(copy)
    output["nonretained_eps_observations"] = nonretained
    return output


def _trim_figure(figure: Any) -> Any:
    if not isinstance(figure, dict):
        return figure
    output = dict(figure)
    output["evidence"] = _trim_evidence(output.get("evidence") or [])
    return output


def _applicability(listing: dict[str, Any], exercice: int) -> tuple[str, bool]:
    listing_year = listing.get("year")
    if isinstance(listing_year, int):
        if exercice < listing_year:
            return "NON_APPLICABLE_AVANT_INTRODUCTION", True
        return "APPLICABLE", False
    return "APPLICABILITE_NON_VERIFIEE_DATE_INTRODUCTION_NON_LUE", False


def _build_outputs(
    *,
    inventory: dict[str, Any],
    registry: list[dict[str, Any]],
    plan: dict[str, Any],
    document_results: list[dict[str, Any]],
    companies: list[dict[str, Any]],
    output_dir: Path,
    tickers: set[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    companies_by_ticker = {str(company.get("ticker")): company for company in companies}
    registry_by_ticker = {str(row.get("ticker")): row for row in registry}
    inventory_by_ticker = dict(inventory.get("tickers") or {})
    all_tickers = [
        ticker
        for ticker in sorted(inventory_by_ticker)
        if not tickers or ticker in tickers
    ]
    candidates_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in plan.get("candidates") or []:
        candidates_by_ticker[str(candidate.get("ticker"))].append(candidate)
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in document_results:
        ticker = str(row.get("ticker") or "")
        rows_by_ticker[ticker].append(row)
        rows_by_key[(ticker, str(row.get("url") or ""))] = row

    capital_events = load_verified_capital_events()
    matrix: list[dict[str, Any]] = []
    ticker_summaries: dict[str, Any] = {}

    for ticker in all_tickers:
        company = companies_by_ticker.get(ticker) or {}
        registry_row = registry_by_ticker.get(ticker) or {}
        ticker_inventory = inventory_by_ticker.get(ticker) or {}
        documents = list(ticker_inventory.get("documents") or [])
        inventory_exhaustive = bool(ticker_inventory.get("inventory_exhaustive"))
        listing = dict(ticker_inventory.get("listing") or {})
        ticker_rows = rows_by_ticker.get(ticker, [])
        series, per_share, aggregation_notes = _aggregate_ticker(ticker_rows)
        figures_by_year = {
            int(entry["exercice"]): entry["figures"]
            for entry in series
            if isinstance(entry.get("exercice"), int)
        }
        planned = candidates_by_ticker.get(ticker, [])
        planned_keys = {(ticker, str(item.get("url") or "")) for item in planned}
        extraction_complete = all(key in rows_by_key for key in planned_keys)
        ticker_summaries[ticker] = {
            "series_exercices": sorted(figures_by_year),
            "documents_inventories": len(documents),
            "documents_candidats_selectionnes": len(planned),
            "documents_ouverts": len(ticker_rows),
            "extraction_complete_pour_plan": extraction_complete,
            "inventory_exhaustive": inventory_exhaustive,
            "aggregation_notes": aggregation_notes,
            "per_share_observations": len(per_share),
        }

        for exercice in YEARS:
            applicability, not_applicable = _applicability(listing, exercice)
            figures = figures_by_year.get(exercice) or {}
            eps_observations = [
                item
                for item in per_share
                if item.get("family") == "eps" and item.get("target_exercice") == exercice
            ]
            inventory_candidates = _inventory_candidates_for_target(documents, exercice)
            selected_for_target = [
                item
                for item in planned
                if exercice in (item.get("target_years_from_filename") or [])
            ]
            doc_infos: list[dict[str, Any]] = []
            seen_urls: set[str] = set()
            for candidate in selected_for_target:
                key = (ticker, str(candidate.get("url") or ""))
                row = rows_by_key.get(key)
                if row is not None and key[1] not in seen_urls:
                    doc_infos.append(_document_target_info(row, exercice))
                    seen_urls.add(key[1])
            # Un document sans année au nom, ou dont l'exercice de contenu
            # diffère du nom, Peut couvrir la cellule même s'il n'était pas
            # pré-affecté par le nom de fichier.
            for row in ticker_rows:
                url = str(row.get("url") or "")
                if url in seen_urls:
                    continue
                info = _document_target_info(row, exercice)
                if info.get("covers_target"):
                    doc_infos.append(info)
                    seen_urls.add(url)

            searched_primary = sum(
                1
                for info in doc_infos
                if info.get("covers_target") and info.get("readable") and info.get("primary_financial_statements")
            )
            searched_any = sum(
                1 for info in doc_infos if info.get("covers_target") and info.get("readable")
            )
            selected_all_opened = all(
                (ticker, str(item.get("url") or "")) in rows_by_key for item in selected_for_target
            )
            unreadable_selected = any(
                (not info.get("readable")) or bool(info.get("error")) for info in doc_infos
            )
            audit_completed = bool(
                inventory_exhaustive
                and selected_all_opened
                and (
                    not inventory_candidates
                    or searched_primary > 0
                    or (unreadable_selected and searched_any == 0)
                )
            )
            reference_scope = _reference_scope(figures, eps_observations)
            metrics = classify_eps_observation(
                figures,
                audit_completed=audit_completed,
                searched_documents=searched_primary,
                candidate_documents=len(inventory_candidates),
                candidate_unreadable=bool(audit_completed and searched_any == 0 and unreadable_selected),
                not_applicable=not_applicable,
                previous_figures=figures_by_year.get(exercice - 1) or {},
                exercice=exercice,
                ticker=ticker,
                capital_events=capital_events,
                eps_observations=eps_observations,
                reference_scope=reference_scope,
            )

            if not_applicable:
                documentary_status = STATUS_NOT_APPLICABLE
            elif not inventory_candidates and inventory_exhaustive:
                documentary_status = STATUS_NOT_FOUND
            elif searched_primary > 0:
                documentary_status = "DOCUMENTS_PRIMAIRES_EXAMINES"
            elif searched_any > 0:
                documentary_status = "DOCUMENTS_OUVERTS_SANS_ETAT_PRIMAIRE_PROUVE"
            elif audit_completed and unreadable_selected:
                documentary_status = STATUS_UNREADABLE
            elif inventory_candidates and not selected_for_target:
                documentary_status = "CANDIDATS_INVENTORIES_NON_OUVERTS"
            elif not inventory_exhaustive:
                documentary_status = "INVENTAIRE_INCOMPLET"
            else:
                documentary_status = STATUS_NOT_RESEARCHED

            metrics_trimmed = _trim_metrics(metrics)
            matrix.append(
                {
                    "ticker": ticker,
                    "company_name": company.get("name") or ticker_inventory.get("company"),
                    "sector": company.get("sector") or registry_row.get("sector"),
                    "exercice": exercice,
                    "applicabilite": applicability,
                    "listing_date": listing.get("date"),
                    "listing_year": listing.get("year"),
                    "listing_status": listing.get("status"),
                    "listing_profile_url": listing.get("profile_url"),
                    "statut_documentaire": documentary_status,
                    "inventory_exhaustive": inventory_exhaustive,
                    "audit_documentaire_termine_pour_la_cellule": audit_completed,
                    "documents_candidats_inventories_count": len(inventory_candidates),
                    "documents_candidats_inventories": [
                        {
                            "label": doc.get("label"),
                            "doc_type": doc.get("doc_type"),
                            "exercice_document_nom": doc.get("exercice"),
                            "published_date": doc.get("published_date"),
                            "url": doc.get("url"),
                        }
                        for doc in inventory_candidates
                    ],
                    "documents_selectionnes_count": len(selected_for_target),
                    "documents_ouverts_pertinents": doc_infos,
                    "documents_primaires_lus_couvrant_exercice": searched_primary,
                    "documents_lus_couvrant_exercice": searched_any,
                    "serie_extraite": bool(figures),
                    "figures_present": sorted(figures),
                    "eps_figure": _trim_figure(figures.get("benefice_par_action")),
                    "statut_bpa": metrics_trimmed.get("status"),
                    "validation_level": _validation_level(metrics_trimmed, figures),
                    "reference_scope": reference_scope,
                    "bpa_publie_fcfa": metrics_trimmed.get("published_eps_fcfa"),
                    "bpa_publie_candidat_avant_quarantaine_fcfa": metrics_trimmed.get(
                        "published_eps_candidate_before_quarantine_fcfa"
                    ),
                    "bpa_recalcule_comparable_fcfa": metrics_trimmed.get(
                        "recalculated_comparable_eps_fcfa"
                    ),
                    "bpa_part_groupe_ponderee_candidat_fcfa": metrics_trimmed.get(
                        "parent_weighted_candidate_fcfa"
                    ),
                    "ratio_indicatif_fin_exercice_fcfa": metrics_trimmed.get(
                        "indicative_result_per_end_share_fcfa"
                    ),
                    "actual": metrics_trimmed,
                }
            )

    def count(predicate) -> int:
        return sum(1 for row in matrix if predicate(row))

    def rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator * 100, 3) if denominator else None

    applicable_confirmed = count(lambda row: row["applicabilite"] == "APPLICABLE")
    non_applicable = count(lambda row: row["applicabilite"] == "NON_APPLICABLE_AVANT_INTRODUCTION")
    applicability_unverified = count(lambda row: row["applicabilite"] != "APPLICABLE" and row["applicabilite"] != "NON_APPLICABLE_AVANT_INTRODUCTION")
    examined = count(lambda row: row["documents_primaires_lus_couvrant_exercice"] > 0)
    series_extracted = count(lambda row: row["serie_extraite"])
    published = count(lambda row: row["bpa_publie_fcfa"] is not None)
    published_confirmed = count(
        lambda row: row["statut_bpa"] == sigma_collect.EPS_STATUS_PUBLISHED_CONFIRMED
    )
    published_extracted_unique = count(
        lambda row: row["validation_level"] == "EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE"
    )
    recalculated = count(
        lambda row: row["bpa_publie_fcfa"] is None and row["bpa_recalcule_comparable_fcfa"] is not None
    )
    parent_candidate = count(
        lambda row: row["statut_bpa"] == sigma_collect.EPS_STATUS_PARENT_WEIGHTED_CANDIDATE
    )
    indicative = count(
        lambda row: row["statut_bpa"] == sigma_collect.EPS_STATUS_INDICATIVE_END_SHARES
    )
    summary: dict[str, Any] = {
        "schema_version": "sigma-audit-bpa-480-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_fingerprint": _code_fingerprint(),
        "dataset_published_modified": False,
        "dataset_sha256_at_generation": _sha256_file(DATASET_PATH),
        "tickers_audites": all_tickers,
        "cellules_brutes_dans_le_perimetre_lance": len(matrix),
        "applicabilite": {
            "applicables_confirmees": applicable_confirmed,
            "non_applicables_avant_introduction": non_applicable,
            "non_verifiees_faute_date_introduction": applicability_unverified,
        },
        "denominateurs": {
            "cellules_avec_document_primaire_lu_couvrant_exercice": examined,
            "cellules_avec_serie_extraite": series_extracted,
        },
        "bpa_publie": {
            "observations_retenues": published,
            "confirme_deux_documents": published_confirmed,
            "extraction_unique_sans_controle_pondere": published_extracted_unique,
            "taux_sur_cellules_brutes_pct": rate(published, len(matrix)),
            "taux_sur_applicables_confirmees_pct": rate(published, applicable_confirmed),
            "taux_sur_cellules_examinees_pct": rate(published, examined),
            "taux_confirme_sur_cellules_examinees_pct": rate(published_confirmed, examined),
        },
        "bpa_recalcule_comparable_sans_publie": {
            "observations": recalculated,
            "taux_sur_cellules_examinees_pct": rate(recalculated, examined),
        },
        "candidat_part_groupe_ponderee_hors_couverture": {"observations": parent_candidate},
        "ratio_indicatif_fin_exercice_hors_couverture_bpa": {"observations": indicative},
        "statuts_bpa": dict(sorted(Counter(str(row["statut_bpa"]) for row in matrix).items())),
        "statuts_documentaires": dict(
            sorted(Counter(str(row["statut_documentaire"]) for row in matrix).items())
        ),
        "niveaux_validation": dict(
            sorted(Counter(str(row["validation_level"]) for row in matrix).items())
        ),
        "par_exercice": {
            str(year): {
                "cellules": sum(1 for row in matrix if row["exercice"] == year),
                "documents_primaires_lus": sum(
                    1 for row in matrix if row["exercice"] == year and row["documents_primaires_lus_couvrant_exercice"] > 0
                ),
                "bpa_publies_retenus": sum(
                    1 for row in matrix if row["exercice"] == year and row["bpa_publie_fcfa"] is not None
                ),
                "non_recherches": sum(
                    1 for row in matrix if row["exercice"] == year and row["statut_bpa"] == STATUS_NOT_RESEARCHED
                ),
            }
            for year in YEARS
        },
        "documents": {
            "inventories": sum(
                len((inventory_by_ticker.get(ticker) or {}).get("documents") or [])
                for ticker in all_tickers
            ),
            "candidats_selectionnes": sum(
                len(candidates_by_ticker.get(ticker, [])) for ticker in all_tickers
            ),
            "resultats_journalises": len(document_results),
            "erreurs_ou_timeouts": sum(1 for row in document_results if row.get("error")),
            "avec_sha256": sum(1 for row in document_results if row.get("document_sha256") or (row.get("extraction") or {}).get("sha256")),
            "rejetes_autre_emetteur": sum(
                1
                for row in document_results
                if (((row.get("extraction") or {}).get("document") or {}).get("selection_rejection") == "AUTRE_EMETTEUR_CONFIRME")
            ),
            "rejetes_intermediaires": sum(
                1
                for row in document_results
                if (((row.get("extraction") or {}).get("document") or {}).get("selection_rejection") == "INTERMEDIAIRE")
            ),
        },
        "by_ticker": ticker_summaries,
        "integration_dataset": "NON_AUTORISEE_PAR_CET_AUDIT",
        "avertissement": (
            "Audit en mode statuts et preuves. Les extractions uniques sans "
            "contrôle pondéré, les quarantaines et les cellules non "
            "recherchées doivent être revues avant toute intégration."
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "matrix.json", matrix)
    _write_json(output_dir / "summary.json", summary)
    fields = [
        "ticker", "company_name", "sector", "exercice", "applicabilite",
        "listing_date", "statut_documentaire", "statut_bpa", "validation_level",
        "bpa_publie_fcfa", "bpa_publie_candidat_avant_quarantaine_fcfa",
        "bpa_recalcule_comparable_fcfa", "bpa_part_groupe_ponderee_candidat_fcfa",
        "ratio_indicatif_fin_exercice_fcfa", "documents_candidats_inventories_count",
        "documents_selectionnes_count", "documents_primaires_lus_couvrant_exercice",
        "documents_lus_couvrant_exercice", "serie_extraite", "reference_scope",
    ]
    with (output_dir / "matrix.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in matrix:
            writer.writerow({field: row.get(field) for field in fields})

    review_rows = [
        row
        for row in matrix
        if row["validation_level"]
        in {"EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE", "QUARANTAINE"}
        or row["statut_bpa"] in {STATUS_NOT_RESEARCHED, STATUS_UNREADABLE}
    ]
    lines = [
        "# Audit BPA 480 — 2016–2025 (mode statuts et preuves)",
        "",
        f"Généré le {summary['generated_at']} avec l'empreinte de code `{summary['code_fingerprint']}`.",
        "",
        "Aucune donnée de cet audit n'a été intégrée au dataset publié.",
        "",
        "## Compteurs séparés",
        "",
        f"- Cellules dans le périmètre lancé : **{len(matrix)}**",
        f"- Applicables confirmées / avant introduction / applicabilité non vérifiée : **{applicable_confirmed} / {non_applicable} / {applicability_unverified}**",
        f"- Cellules avec document primaire lu couvrant l'exercice : **{examined}**",
        f"- BPA publiés retenus : **{published}** ; confirmés par deux documents : **{published_confirmed}** ; extraction unique sans contrôle pondéré : **{published_extracted_unique}**",
        f"- BPA recalculés comparables sans BPA publié : **{recalculated}**",
        f"- Candidats part du groupe / pondérés à vérifier : **{parent_candidate}**",
        f"- Ratios indicatifs fin d'exercice (hors couverture BPA) : **{indicative}**",
        f"- Documents inventoriés / sélectionnés / journalisés : **{summary['documents']['inventories']} / {summary['documents']['candidats_selectionnes']} / {summary['documents']['resultats_journalises']}**",
        "",
        "## Statuts BPA",
        "",
        *[f"- `{key}` : {value}" for key, value in summary["statuts_bpa"].items()],
        "",
        "## Statuts documentaires",
        "",
        *[f"- `{key}` : {value}" for key, value in summary["statuts_documentaires"].items()],
        "",
        "## Règles de lecture",
        "",
        "- `NON_PUBLIE_DANS_SOURCES_VERIFIEES` exige au moins un état primaire lu couvrant l'exercice.",
        "- Une absence dans un document condensé ou un rapport sans état primaire prouvé reste `NON_RECHERCHE`.",
        "- Le ratio résultat / actions de fin d'exercice est séparé et ne compte jamais comme BPA comparable.",
        "- Les valeurs en extraction unique doivent être confirmées par un second document ou un contrôle pondéré avant intégration comparable.",
        "",
        "## Cellules prioritaires à revoir",
        "",
    ]
    if review_rows:
        for row in review_rows[:300]:
            lines.append(
                f"- **{row['ticker']} {row['exercice']}** — BPA `{row['statut_bpa']}`, "
                f"documentaire `{row['statut_documentaire']}`, validation `{row['validation_level']}`, "
                f"publié {row['bpa_publie_fcfa']}, candidat {row['bpa_publie_candidat_avant_quarantaine_fcfa']}."
            )
        if len(review_rows) > 300:
            lines.append(f"- … et {len(review_rows) - 300} autres cellules dans `matrix.csv`.")
    else:
        lines.append("- Aucune cellule de cette catégorie dans le périmètre lancé.")
    lines.extend(
        [
            "",
            "Détails : `matrix.json`, `matrix.csv`, `summary.json`, `inventory.json`, `candidate_plan.json` et `document_results.jsonl`.",
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return matrix, summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("inventory", "extract", "aggregate", "all", "extract-one"),
        default="all",
    )
    parser.add_argument("--tickers", help="Liste séparée par des virgules")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--max-per-doc-exercice", type=int, default=6)
    parser.add_argument("--limit-docs", type=int)
    parser.add_argument("--doc-timeout", type=int, default=240)
    parser.add_argument("--force-inventory", action="store_true")
    parser.add_argument("--force-extract", action="store_true")
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--candidate-file", type=Path)
    parser.add_argument("--companies-file", type=Path)
    parser.add_argument("--extract-output-file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.phase == "extract-one":
        if not args.candidate_file or not args.companies_file or not args.extract_output_file:
            raise SystemExit("--candidate-file, --companies-file et --extract-output-file sont requis")
        return _extract_one(
            candidate_file=args.candidate_file,
            companies_file=args.companies_file,
            output_file=args.extract_output_file,
            cache_dir=args.cache_dir,
            allow_ocr=not args.no_ocr,
        )

    tickers = _parse_tickers(args.tickers)
    dataset = _dataset()
    companies = list(dataset.get("companies") or [])
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "inventory.json"
    plan_path = output_dir / "candidate_plan.json"

    if args.phase in {"inventory", "extract", "all"}:
        if inventory_path.exists() and not args.force_inventory:
            inventory = _load_json(inventory_path)
            registry_path = output_dir / "issuer_registry.json"
            registry = _load_json(registry_path) if registry_path.exists() else []
            if tickers and not tickers.issubset(set((inventory.get("tickers") or {}))):
                raise SystemExit(
                    "L'inventaire existant ne couvre pas tous les tickers demandés ; "
                    "utiliser --force-inventory ou un autre --output-dir."
                )
            print(f"Inventaire repris : {inventory_path}", flush=True)
        else:
            inventory, registry = _build_inventory(
                companies=companies,
                dataset=dataset,
                tickers=tickers,
                max_pages=args.max_pages,
                passes=args.passes,
            )
            _write_json(inventory_path, inventory)
            _write_registry(output_dir, registry)
        plan = _build_candidate_plan(
            inventory,
            max_per_doc_exercice=args.max_per_doc_exercice,
        )
        _write_json(plan_path, plan)
        print(
            json.dumps(
                {
                    "tickers_inventories": len(inventory.get("tickers") or {}),
                    "documents_inventories": sum(
                        len(payload.get("documents") or [])
                        for payload in (inventory.get("tickers") or {}).values()
                    ),
                    "candidats_selectionnes": plan["candidate_count"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
    else:
        if not inventory_path.exists() or not plan_path.exists():
            raise SystemExit("Inventaire ou plan candidat absent : lancer d'abord --phase inventory")
        inventory = _load_json(inventory_path)
        registry = _load_json(output_dir / "issuer_registry.json")
        plan = _load_json(plan_path)

    if args.phase in {"extract", "all"}:
        extraction_plan = plan
        if tickers:
            extraction_plan = {
                **plan,
                "candidates": [
                    item for item in plan.get("candidates") or [] if str(item.get("ticker")) in tickers
                ],
            }
        _run_extractions(
            plan=extraction_plan,
            companies=companies,
            output_dir=output_dir,
            cache_dir=args.cache_dir,
            allow_ocr=not args.no_ocr,
            doc_timeout=args.doc_timeout,
            limit_docs=args.limit_docs,
            force=args.force_extract,
        )

    if args.phase in {"aggregate", "extract", "all"}:
        document_results = _load_document_results(
            output_dir / "document_results.jsonl",
            _code_fingerprint(),
        )
        _matrix, summary = _build_outputs(
            inventory=inventory,
            registry=registry,
            plan=plan,
            document_results=document_results,
            companies=companies,
            output_dir=output_dir,
            tickers=tickers,
        )
        print(json.dumps(_json_ready(summary), ensure_ascii=False, indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SIGMA — collecte EOD BRVM depuis les sources officielles publiques.

Principes :
- aucun chiffre inventé : chaque bloc porte sa source et sa date ;
- le BOC officiel sert d'historique et d'indicateurs publiés ;
- la page des cours sert d'instantané le plus récent publié par la BRVM ;
- si les contrôles bloquants échouent, aucun fichier de données n'est remplacé.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import pdfplumber
import requests
from bs4 import BeautifulSoup

try:
    from eps_evidence import (
        EPS_PARSER_VERSION,
        assess_eps_arithmetic,
        classify_page_accounting_contexts,
        detect_column_years as detect_eps_column_years,
        detect_document_fiscal_year,
        detect_document_period,
        detect_share_count_changes,
        document_selection_metadata,
        extract_per_share_observations,
        infer_report_doc_type,
        load_verified_capital_events,
        select_published_eps_candidate,
        verify_document_issuer,
    )
except ImportError:  # import en package éventuel
    from .eps_evidence import (  # type: ignore
        EPS_PARSER_VERSION,
        assess_eps_arithmetic,
        classify_page_accounting_contexts,
        detect_column_years as detect_eps_column_years,
        detect_document_fiscal_year,
        detect_document_period,
        detect_share_count_changes,
        document_selection_metadata,
        extract_per_share_observations,
        infer_report_doc_type,
        load_verified_capital_events,
        select_published_eps_candidate,
        verify_document_issuer,
    )

BASE = "https://www.brvm.org"
URLS = {
    "quotes": f"{BASE}/fr/cours-actions/0",
    "dividends": f"{BASE}/fr/esv/paiement-de-dividendes",
    "boc_index": f"{BASE}/fr/bulletins-officiels-de-la-cote",
    "reports_index": f"{BASE}/fr/rapports-societes-cotees",
    "news_actualites": f"{BASE}/fr/mediacentre/actualites",
    "sgis": f"{BASE}/fr/intervenants/sgi/tous",
    "bceao_press": "https://www.bceao.int/fr/communique-presse",
    "bceao_events": "https://www.bceao.int/fr/evenements",
    "umoa_rss": "https://www.umoatitres.org/fr/feed/",
    "umoa_emissions": "https://www.umoatitres.org/fr/emissions/",
    "sika_rss": "https://www.sikafinance.com/rss/actualites_bourse_brvm",
}
# Annonces officielles des émetteurs publées par la BRVM (date + société + PDF).
ANNOUNCEMENT_CATEGORIES = {
    "communiques": "Communiqués d'émetteurs",
    "convocations-assemblees-generales": "Convocations aux assemblées générales",
    "projets-de-resolution": "Projets de résolution",
    "notations-financieres": "Notations financières",
    "changements-de-dirigeants": "Changements de dirigeants",
    "franchissements-de-seuil": "Franchissements de seuil",
}
# Phrases distinctives pour rattacher une dépêche de presse à une société cotée.
# Volontairement strictes : un faux rattachement vaut moins qu'un rattachement manqué.
NEWS_TICKER_ALIASES = {
    "sonatel": "SNTS",
    "orange cote d ivoire": "ORAC",
    "sgci": "SGBC",
    "ecobank cote d ivoire": "ECOC",
    "ecobank transnational": "ETIT",
    "coris bank international burkina": "CBIBF",
    "sodeci": "SDCC",
    "palmci": "PALC",
    "palm ci": "PALC",
    "saph": "SPHC",
    "societe multinationale de bitume": "SMBC",
    "smb cote d ivoire": "SMBC",
    "bridge bank group": "BBGC",
    "loterie nationale du benin": "LNBB",
    "onatel": "ONTBF",
    "vivo energy cote d ivoire": "SHEC",
    "bank of africa cote d ivoire": "BOAC",
    "bank of africa benin": "BOAB",
    "bank of africa burkina": "BOABF",
    "bank of africa mali": "BOAM",
    "bank of africa niger": "BOAN",
    "bank of africa senegal": "BOAS",
    "boa cote d ivoire": "BOAC",
    "nsia banque cote d ivoire": "NSBC",
    "societe ivoirienne de banque": "SIBC",
    "bici cote d ivoire": "BICC",
    "oragroup": "ORGT",
    "ecobank tg": "ETIT",
    "ecobank togo": "ETIT",
    "eti tg": "ETIT",
    "eti togo": "ETIT",
    "total energies marketing cote d ivoire": "TTLC",
    "totalenergies marketing cote d ivoire": "TTLC",
    "totalenergies marketing senegal": "TTLS",
    "bollore transport logistics": "SDSC",
    "africa global logistics cote d ivoire": "SDSC",
    "africa global logistics ci": "SDSC",
}
MACRO_KEYWORDS = [
    "bceao", "banque centrale", "taux directeur", "politique monetaire", "inflation",
    "uemoa", "umoa", "cedeao", "petrole", "bitume", "cacao", "caoutchouc",
    "huile de palme", "or ", "dette publique", "tresor public", "adjudication",
    "obligation du tresor", "bon du tresor", "budget", "fmi", "banque mondiale",
    "mobile money", "commission bancaire", "taux d interet",
]
COUNTRY_CODE_WORDS = {
    "bf": "burkina faso", "bn": "benin", "ci": "cote d ivoire", "ml": "mali",
    "ng": "niger", "sn": "senegal", "tg": "togo",
}
SECTOR_PAGES = {
    194: "Consommation de base",
    195: "Consommation discrétionnaire",
    196: "Énergie",
    197: "Industriels",
    198: "Services financiers",
    199: "Services publics",
    200: "Télécommunications",
}
SECTOR_CODES = {
    "CB": "Consommation de base",
    "CD": "Consommation discrétionnaire",
    "ENE": "Énergie",
    "FIN": "Services financiers",
    "IND": "Industriels",
    "SPU": "Services publics",
    "TEL": "Télécommunications",
}
FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
USER_AGENT = "SIGMA-personal-BRVM/1.0 (+usage personnel; collecte EOD sobre)"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()


def normalize_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def parse_number(value: Any) -> float | int | None:
    """Lit un nombre au format français BRVM. Retourne None si non numérique/SP/NC."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = clean_text(value)
    if not text or text.upper() in {"SP", "NC", "-", "—", "N/A"}:
        return None
    text = (
        text.replace("FCFA", "")
        .replace("%", "")
        .replace("\u202f", " ")
        .replace("\u00a0", " ")
        .replace(" ", "")
        .replace(",", ".")
    )
    # Ne conserver que le premier motif numérique (protège des libellés collés).
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    return int(number) if number.is_integer() else round(number, 6)


def parse_french_long_date(value: str) -> str | None:
    """'27 octobre 2026' -> '2026-10-27'. Retourne None si illisible."""
    match = re.search(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})", clean_text(value))
    if not match:
        return None
    month = FRENCH_MONTHS.get(normalize_key(match.group(2)))
    if not month:
        return None
    return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(1)):02d}"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})
    return session


def fetch(session: requests.Session, url: str, *, binary: bool = False) -> bytes | str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=45)
            response.raise_for_status()
            return response.content if binary else response.text
        except Exception as exc:  # collecte réseau : nouvel essai borné
            last_error = exc
    raise RuntimeError(f"Échec de collecte après 3 essais : {url} ({last_error})")


def find_quote_table(soup: BeautifulSoup):
    candidates = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [clean_text(cell.get_text(" ", strip=True)) for cell in rows[0].find_all(["th", "td"])]
        if header and header[0].lower().startswith("symbole"):
            candidates.append((len(rows), table))
    if not candidates:
        raise ValueError("Table officielle des cours introuvable : structure de page modifiée ?")
    return max(candidates, key=lambda item: item[0])[1]


def rows_from_quote_table(table) -> list[dict[str, Any]]:
    quotes: list[dict[str, Any]] = []
    for row in table.find_all("tr")[1:]:
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if len(cells) < 7 or not re.fullmatch(r"[A-Z]{3,5}", cells[0]):
            continue
        quotes.append(
            {
                "ticker": cells[0],
                "name": cells[1],
                "volume": parse_number(cells[2]),
                "previous_close": parse_number(cells[3]),
                "open": parse_number(cells[4]),
                "close": parse_number(cells[5]),
                "variation_pct": parse_number(cells[6]),
            }
        )
    return quotes


def scrape_latest_snapshot(session: requests.Session) -> dict[str, Any]:
    html = str(fetch(session, URLS["quotes"]))
    soup = BeautifulSoup(html, "lxml")
    quotes = rows_from_quote_table(find_quote_table(soup))
    page_text = soup.get_text("\n", strip=True)

    updated_match = re.search(r"Dernière mise à jour\s*:\s*([^\n]+)", page_text)
    activity: dict[str, Any] = {}
    indices: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        classes = table.get("class") or []
        if "activity" not in classes:
            continue
        for row in table.find_all("tr"):
            cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
            if len(cells) >= 2 and cells[0] and cells[1]:
                if cells[0].startswith("BRVM"):
                    variation = None
                    full = clean_text(row.get_text(" ", strip=True))
                    vm = re.search(r"([-+]?\d+[\d\s]*,\d+)\s*$", full)
                    # La variation est dans le texte de ligne sur le site ; extraction prudente.
                    pct = re.search(r"([-+]?\d+,\d+)\s*%", full)
                    if pct:
                        variation = parse_number(pct.group(1))
                    indices.append(
                        {
                            "name": cells[0],
                            "level": parse_number(cells[1]),
                            "variation_pct": variation,
                        }
                    )
                else:
                    activity[cells[0]] = {"raw": cells[1], "value": parse_number(cells[1])}
    # Repli robuste pour les variations d'indices depuis le texte visible ordonné.
    if indices and any(item["variation_pct"] is None for item in indices):
        flat = clean_text(page_text)
        for item in indices:
            pattern = re.escape(item["name"]) + r"\s+[\d\s]+,\d+\s+([-+]?\d+,\d+)\s*%"
            found = re.search(pattern, flat)
            if found:
                item["variation_pct"] = parse_number(found.group(1))

    session_status = "Non précisé par la source"
    if "Séance fermée" in page_text:
        session_status = "Séance fermée"
    elif "Séance Ouverte" in page_text or "Séance ouverte" in page_text:
        session_status = "Séance ouverte (publication possiblement différée)"

    return {
        "source_url": URLS["quotes"],
        "source_updated_label": clean_text(updated_match.group(1)) if updated_match else None,
        "session_status": session_status,
        "activity": activity,
        "indices": indices,
        "quotes": quotes,
    }


def scrape_sector_map(session: requests.Session) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for sector_id, label in SECTOR_PAGES.items():
        url = f"{BASE}/fr/cours-actions/{sector_id}"
        soup = BeautifulSoup(str(fetch(session, url)), "lxml")
        for quote in rows_from_quote_table(find_quote_table(soup)):
            mapping[quote["ticker"]] = label
    return mapping


def deduplicate_dividend_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fusionne les avis multiples d'une même distribution.

    Certains rectificatifs déplacent la date de paiement d'un à trois jours :
    même émetteur, exercice et montant à quelques jours d'intervalle sont
    donc traités comme une seule distribution, avec priorité à l'avis
    rectificatif/modifié, puis à la ligne portant une date ex-dividende.
    """
    merged: list[dict[str, Any]] = []

    def score(item: dict[str, Any]) -> tuple[int, int, int]:
        url = normalize_key(item.get("notice_url") or "")
        return (
            1 if ("rectificatif" in url or "modifie" in url) else 0,
            1 if item.get("ex_date") else 0,
            1 if item.get("notice_url") else 0,
        )

    for row in rows:
        amount = row.get("net_amount_fcfa")
        match_index = None
        if isinstance(amount, (int, float)) and row.get("payment_date"):
            try:
                row_payment = date.fromisoformat(str(row["payment_date"]))
            except ValueError:
                row_payment = None
            if row_payment:
                for index, existing in enumerate(merged):
                    if (
                        normalize_key(existing.get("issuer") or "") == normalize_key(row.get("issuer") or "")
                        and str(existing.get("fiscal_year") or "") == str(row.get("fiscal_year") or "")
                        and existing.get("net_amount_fcfa") == amount
                        and existing.get("payment_date")
                    ):
                        try:
                            existing_payment = date.fromisoformat(str(existing["payment_date"]))
                        except ValueError:
                            continue
                        if abs((row_payment - existing_payment).days) <= 3:
                            match_index = index
                            break
        if match_index is None:
            merged.append(row)
            continue
        existing = merged[match_index]
        total_rows = int(existing.get("source_rows_merged") or 1) + int(row.get("source_rows_merged") or 1)
        if score(row) > score(existing):
            row = dict(row)
            row["source_rows_merged"] = total_rows
            merged[match_index] = row
        else:
            if not existing.get("ex_date") and row.get("ex_date"):
                existing["ex_date"] = row["ex_date"]
                existing["ex_date_label"] = row.get("ex_date_label")
            if not existing.get("notice_url") and row.get("notice_url"):
                existing["notice_url"] = row["notice_url"]
            existing["source_rows_merged"] = total_rows
    return merged


def scrape_dividends(session: requests.Session, pages: int | None = None) -> list[dict[str, Any]]:
    """Historique officiel des dividendes BRVM.

    Sans limite explicite, on suit la pagination publiée par la BRVM jusqu'à
    épuisement (avec garde-fou), au lieu de ne lire que les distributions les
    plus récentes. Cela donne l'historique par exercice nécessaire à l'étude
    de régularité, sans déduire une absence de dividende d'une ligne absente.
    """
    dividends: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, str, str], int] = {}
    max_pages = pages if pages is not None else 80
    page_number = 0
    while page_number < max_pages:
        page_url = URLS["dividends"] if page_number == 0 else f"{URLS['dividends']}?page={page_number}"
        soup = BeautifulSoup(str(fetch(session, page_url)), "lxml")
        if pages is None and page_number == 0:
            detected_pages = []
            for anchor in soup.select("a[href]"):
                match = re.search(r"[?&]page=(\d+)", anchor.get("href", ""))
                if match:
                    detected_pages.append(int(match.group(1)))
            if detected_pages:
                max_pages = min(max_pages, max(detected_pages) + 1)
        target = None
        for table in soup.find_all("table"):
            text = clean_text(table.get_text(" ", strip=True))
            if "Montant du dividende net" in text and "Date ex-dividende" in text:
                target = table
                break
        if target is None:
            raise ValueError("Table officielle des dividendes introuvable.")

        new_rows_before = len(seen)
        for row in target.find_all("tr")[1:]:
            cells = row.find_all(["th", "td"])
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 7 or not values[0]:
                continue
            notice_url = None
            for cell in cells:
                anchor = cell.find("a", href=True)
                if anchor and ".pdf" in anchor["href"].lower():
                    notice_url = urljoin(page_url, anchor["href"])
                    break
            record = {
                "issuer": values[0],
                "fiscal_year": values[3],
                "payment_date": parse_french_long_date(values[4]),
                "payment_date_label": values[4],
                "ex_date": parse_french_long_date(values[5]),
                "ex_date_label": values[5],
                "net_amount_fcfa": parse_number(values[6]),
                "notice_url": notice_url,
                "source_url": page_url,
                "source_rows_merged": 1,
            }
            # La BRVM publie parfois deux avis (dont un rectificatif) pour
            # une même distribution : même émetteur, exercice, date de
            # paiement et montant. On fusionne ces lignes au lieu de compter
            # deux fois le dividende, en privilégiant le rectificatif puis
            # la ligne qui porte la date ex-dividende.
            key = (normalize_key(values[0]), values[3], values[4], values[6])
            if key in seen:
                existing = dividends[seen[key]]

                def notice_score(item: dict[str, Any]) -> tuple[int, int, int]:
                    url = normalize_key(item.get("notice_url") or "")
                    return (
                        1 if "rectificatif" in url else 0,
                        1 if item.get("ex_date") else 0,
                        1 if item.get("notice_url") else 0,
                    )

                if notice_score(record) > notice_score(existing):
                    record["source_rows_merged"] = int(existing.get("source_rows_merged") or 1) + 1
                    dividends[seen[key]] = record
                else:
                    if not existing.get("ex_date") and record.get("ex_date"):
                        existing["ex_date"] = record["ex_date"]
                        existing["ex_date_label"] = record["ex_date_label"]
                    if not existing.get("notice_url") and record.get("notice_url"):
                        existing["notice_url"] = record["notice_url"]
                    existing["source_rows_merged"] = int(existing.get("source_rows_merged") or 1) + 1
                continue
            seen[key] = len(dividends)
            dividends.append(record)
        if page_number > 0 and len(seen) == new_rows_before:
            break
        page_number += 1
    return deduplicate_dividend_rows(dividends)


DIVIDEND_ISSUER_ALIASES = {
    # Alias limités au tableau officiel des dividendes : les avis liés
    # identifient sans ambiguïté l'émetteur (ancien nom ou abréviation BRVM).
    "total": "TTLC",
    "total senegal": "TTLS",
    "total senegal s a": "TTLS",
    "sogb": "SOGC",
    "sib": "SIBC",
    "sicable": "CABC",
    "tractafric ci": "PRSC",
    "tractafric cote d ivoire": "PRSC",
    "nsbc": "NSBC",
    "smb": "SMBC",
    "solibra": "SLBC",
    "sitab": "STBC",
    "crown siem ci": "SEMC",
    "lnb": "LNBB",
    "biic": "BICB",
    "air liquide ci": "SIVC",
}


def match_dividend_issuer(issuer: str, variants: dict[str, str], known_tickers: set[str]) -> list[str]:
    alias_ticker = DIVIDEND_ISSUER_ALIASES.get(normalize_key(issuer))
    if alias_ticker and alias_ticker in known_tickers:
        return [alias_ticker]
    return match_announcement_issuer(issuer, variants)


def compute_dividend_history(
    dividends: list[dict[str, Any]], companies: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Historique documenté des distributions par action, par exercice.

    Les montants sont les montants nets publiés par la BRVM. Quand plusieurs
    lignes distinctes existent pour un même exercice, elles sont additionnées
    comme distributions de l'exercice et signalées. Une absence de ligne est
    libellée « non documentée dans le tableau collecté », jamais « dividende
    certain égal à zéro » : nouvelle cotation, changement de nom ou ligne non
    rattachée peuvent aussi expliquer un trou.
    """
    variants = build_issuer_variant_map(companies)
    known_tickers = {company["ticker"] for company in companies}
    by_ticker: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    fiscal_years: list[int] = []
    seen_distributions: set[tuple[str, int, str, float]] = set()
    for div in dividends:
        tickers = match_dividend_issuer(div.get("issuer") or "", variants, known_tickers)
        div["tickers"] = tickers
        year_match = re.search(r"(20\d{2})", str(div.get("fiscal_year") or ""))
        amount = div.get("net_amount_fcfa")
        if len(tickers) != 1 or not year_match or not isinstance(amount, (int, float)):
            continue
        ticker = tickers[0]
        year = int(year_match.group(1))
        distribution_key = (
            ticker,
            year,
            str(div.get("payment_date") or div.get("payment_date_label") or ""),
            float(amount),
        )
        if distribution_key in seen_distributions:
            continue
        seen_distributions.add(distribution_key)
        fiscal_years.append(year)
        annual = by_ticker[ticker].setdefault(
            year,
            {
                "fiscal_year": year,
                "net_amount_fcfa": 0,
                "payments_count": 0,
                "ex_dates": [],
                "payment_dates": [],
                "notice_urls": [],
            },
        )
        annual["net_amount_fcfa"] = round(float(annual["net_amount_fcfa"]) + float(amount), 4)
        annual["payments_count"] += 1
        if div.get("ex_date"):
            annual["ex_dates"].append(div["ex_date"])
        if div.get("payment_date"):
            annual["payment_dates"].append(div["payment_date"])
        if div.get("notice_url"):
            annual["notice_urls"].append(div["notice_url"])

    latest_fiscal_year = max(fiscal_years) if fiscal_years else None
    stats: dict[str, dict[str, Any]] = {}
    for company in companies:
        ticker = company["ticker"]
        annual_map = by_ticker.get(ticker, {})
        annual = [annual_map[year] for year in sorted(annual_map)]
        paid_years = [entry["fiscal_year"] for entry in annual if entry["net_amount_fcfa"] > 0]
        last5_years = list(range(latest_fiscal_year - 4, latest_fiscal_year + 1)) if latest_fiscal_year else []
        last10_years = list(range(latest_fiscal_year - 9, latest_fiscal_year + 1)) if latest_fiscal_year else []
        paid_last5 = sum(1 for year in last5_years if year in annual_map and annual_map[year]["net_amount_fcfa"] > 0)
        paid_last10 = sum(1 for year in last10_years if year in annual_map and annual_map[year]["net_amount_fcfa"] > 0)
        cuts = 0
        increases = 0
        for previous, current in zip(annual, annual[1:]):
            if current["fiscal_year"] != previous["fiscal_year"] + 1:
                continue
            if current["net_amount_fcfa"] < previous["net_amount_fcfa"] * 0.999:
                cuts += 1
            elif current["net_amount_fcfa"] > previous["net_amount_fcfa"] * 1.001:
                increases += 1
        current_run = 0
        if latest_fiscal_year:
            cursor = latest_fiscal_year
            while cursor in annual_map and annual_map[cursor]["net_amount_fcfa"] > 0:
                current_run += 1
                cursor -= 1
        cagr = None
        positive = [entry for entry in annual if entry["net_amount_fcfa"] > 0]
        if len(positive) >= 3:
            first, last = positive[0], positive[-1]
            span = last["fiscal_year"] - first["fiscal_year"]
            if span >= 2 and first["net_amount_fcfa"] > 0:
                cagr = round(((last["net_amount_fcfa"] / first["net_amount_fcfa"]) ** (1 / span) - 1) * 100, 4)
        if paid_last5 == 5:
            status = "documentee_5_exercices"
        elif paid_last5 >= 3:
            status = "documentee_partielle"
        elif paid_years:
            status = "historique_court_ou_ancien"
        else:
            status = "non_documentee_dans_tableau_collecte"
        latest = annual[-1] if annual else None
        stats[ticker] = {
            "status": status,
            "source": "BRVM — Paiement de dividendes (historique paginé)",
            "latest_fiscal_year_in_table": latest_fiscal_year,
            "paid_fiscal_years_count": len(paid_years),
            "paid_last_5_fiscal_years": paid_last5,
            "paid_last_10_fiscal_years": paid_last10,
            "current_consecutive_paid_years": current_run,
            "first_paid_fiscal_year": paid_years[0] if paid_years else None,
            "latest_paid_fiscal_year": paid_years[-1] if paid_years else None,
            "latest_net_amount_fcfa": latest["net_amount_fcfa"] if latest else None,
            "dividend_cagr_pct": cagr,
            "cuts_count": cuts,
            "increases_count": increases,
            "annual": annual,
            "payout_ratio_status": "non_calculable_sans_nombre_actions_ou_benefice_par_action_verifie",
        }
    return stats


def scrape_boc_links(session: requests.Session, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Retourne (documents d'historique récent, documents indexés officiels).

    La page officielle n'indexe qu'une dizaine de BOC récents. Pour constituer
    un historique de calcul suffisant, on complète prudemment par le motif
    d'URL public observé sur cette même page (`boc_AAAAMMJJ_2.pdf`), uniquement
    les jours ouvrés récents, avec validation de la date imprimée dans le PDF.
    """
    soup = BeautifulSoup(str(fetch(session, URLS["boc_index"])), "lxml")
    docs_by_date: dict[str, dict[str, str]] = {}
    for anchor in soup.select("a[href]"):
        href = urljoin(URLS["boc_index"], anchor.get("href", ""))
        match = re.search(r"boc_(\d{4})(\d{2})(\d{2})[^/]*\.pdf$", href, flags=re.I)
        if not match:
            continue
        date = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        docs_by_date[date] = {"date": date, "url": href}
    indexed_docs = [docs_by_date[date] for date in sorted(docs_by_date, reverse=True)]
    if not indexed_docs:
        raise ValueError("Aucun lien BOC daté trouvé sur la page officielle.")

    latest = datetime.fromisoformat(indexed_docs[0]["date"]).date()
    history_docs: list[dict[str, Any]] = [
        {**doc, "required": True, "discovery": "page_officielle_boc"}
        for doc in indexed_docs
        if 0 <= (latest - datetime.fromisoformat(doc["date"]).date()).days <= 21
    ]
    known_dates = {doc["date"] for doc in history_docs}
    cursor = min(datetime.fromisoformat(doc["date"]).date() for doc in history_docs)
    scanned_days = 0
    # Pour une archive longue (ex. 250 séances ≈ un an de Bourse), il faut
    # balayer plus d'une année calendaire en arrière : week-ends, jours fériés
    # et éventuelles séances sans BOC publié au motif d'URL observé.
    scan_budget_days = max(160, int(limit * 2.4) + 120)
    while len(history_docs) < limit and scanned_days < scan_budget_days:
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
        scanned_days += 1
        if cursor.weekday() >= 5:
            continue
        date_text = cursor.isoformat()
        if date_text in known_dates:
            continue
        candidate_url = f"{BASE}/sites/default/files/boc_{cursor.strftime('%Y%m%d')}_2.pdf"
        try:
            head = session.head(candidate_url, timeout=20, allow_redirects=True)
        except requests.RequestException:
            continue
        if head.status_code == 200 and "pdf" in head.headers.get("content-type", "").lower():
            history_docs.append(
                {
                    "date": date_text,
                    "url": candidate_url,
                    "required": False,
                    "discovery": "motif_url_officiel_observe_puis_date_pdf_validee",
                }
            )
            known_dates.add(date_text)
    history_docs.sort(key=lambda item: item["date"], reverse=True)
    return history_docs[:limit], indexed_docs


def parse_boc_pdf(content: bytes, date: str, url: str) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    composite_level = None
    composite_variation = None
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        if pdf.pages:
            first_text = clean_text(pdf.pages[0].extract_text() or "")
            printed_date_match = re.search(r"\b(\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4})\b", first_text)
            if printed_date_match:
                printed_date = parse_french_long_date(printed_date_match.group(1))
                if printed_date and printed_date != date:
                    raise ValueError(
                        f"BOC {date} : la date imprimée dans le PDF est {printed_date} (URL incohérente)."
                    )
            match = re.search(
                r"BRVM COMPOSITE\s+([\d\s]+,\d+)\s+BRVM 30.*?Variation Jour\s+([-+]?[\d\s]+,\d+)\s*%",
                first_text,
            )
            if match:
                composite_level = parse_number(match.group(1))
                composite_variation = parse_number(match.group(2))
        # Les tableaux actions se trouvent sur les pages 3 et 4 du format BOC actuel.
        for page in pdf.pages[2:4]:
            for table in page.extract_tables() or []:
                for raw_row in table:
                    if not raw_row or len(raw_row) < 16:
                        continue
                    sector_code = clean_text(raw_row[0]).upper()
                    ticker = clean_text(raw_row[1]).upper()
                    if sector_code not in SECTOR_CODES or not re.fullmatch(r"[A-Z]{3,5}", ticker):
                        continue
                    # Format observé : [secteur, ticker, titre, '', préc., ouv., clôt.,
                    # var., volume, valeur, réf., var. année, div., date div., rdt, PER]
                    rows[ticker] = {
                        "ticker": ticker,
                        "name": clean_text(raw_row[2]),
                        "sector_code": sector_code,
                        "sector": SECTOR_CODES[sector_code],
                        "previous_close": parse_number(raw_row[4]),
                        "open": parse_number(raw_row[5]),
                        "close": parse_number(raw_row[6]),
                        "variation_pct": parse_number(raw_row[7]),
                        "volume": parse_number(raw_row[8]),
                        "traded_value_fcfa": parse_number(raw_row[9]),
                        "reference_price": parse_number(raw_row[10]),
                        "variation_previous_year_pct": parse_number(raw_row[11]),
                        "last_net_dividend_fcfa": parse_number(raw_row[12]),
                        "last_dividend_date_label": clean_text(raw_row[13]) or None,
                        "net_dividend_yield_pct": parse_number(raw_row[14]),
                        "per": parse_number(raw_row[15]),
                    }
    if len(rows) < 35:
        raise ValueError(f"BOC {date} : seulement {len(rows)} lignes actions lisibles (format modifié ?).")
    return {
        "date": date,
        "url": url,
        "sha256": hashlib.sha256(content).hexdigest(),
        "composite_level": composite_level,
        "composite_variation_pct": composite_variation,
        "rows": rows,
    }


def load_boc_history(
    session: requests.Session, docs: list[dict[str, Any]], cache_dir: Path
) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    parsed: list[dict[str, Any]] = []
    for doc in docs:
        cache_file = cache_dir / f"boc_{doc['date']}.pdf"
        try:
            if cache_file.exists() and cache_file.stat().st_size > 20_000:
                content = cache_file.read_bytes()
            else:
                content = bytes(fetch(session, doc["url"], binary=True))
                cache_file.write_bytes(content)
            parsed_doc = parse_boc_pdf(content, doc["date"], doc["url"])
        except Exception as exc:
            if doc.get("required", True):
                raise
            print(f"[SIGMA] BOC candidat {doc['date']} ignoré : {exc}", file=sys.stderr)
            continue
        parsed_doc["discovery"] = doc.get("discovery", "page_officielle_boc")
        parsed.append(parsed_doc)
        print(f"[SIGMA] BOC {doc['date']} lu : {len(parsed[-1]['rows'])} valeurs", file=sys.stderr)
    return sorted(parsed, key=lambda item: item["date"])


# ---------------------------------------------------------------------------
# Archive BOC longue : fichier séparé, accumulé de collecte en collecte.
# `data.json` garde les 30 dernières séances pour l'app ; l'archive conserve
# l'historique long (objectif : 250 séances ≈ un an de Bourse) sous forme
# compacte — chaque ligne société est un tableau ordonné par `row_fields`.
# Les cours restent des prix publiés non ajustés (hors dividendes réinvestis).
# ---------------------------------------------------------------------------

BOC_ARCHIVE_ROW_FIELDS = [
    "close",
    "variation_pct",
    "volume",
    "traded_value_fcfa",
    "previous_close",
    "open",
    "reference_price",
    "variation_previous_year_pct",
    "last_net_dividend_fcfa",
    "last_dividend_date_label",
    "net_dividend_yield_pct",
    "per",
]


def Empty_boc_archive() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "Bulletins Officiels de la Cote (BRVM)",
        "price_basis": "prix_publiés_non_ajustés_hors_dividendes_réinvestis",
        "row_fields": BOC_ARCHIVE_ROW_FIELDS,
        "updated_at": None,
        "sessions_count": 0,
        "first_date": None,
        "last_date": None,
        "sessions": [],
    }


def load_boc_archive(path: Path | None) -> tuple[dict[str, Any], str | None]:
    if path is None or not path.exists():
        return Empty_boc_archive(), None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return Empty_boc_archive(), f"Archive BOC existante illisible ; reconstruction partielle ({exc})."
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        return Empty_boc_archive(), "Archive BOC existante au format inattendu ; reconstruction partielle."
    if data.get("row_fields") != BOC_ARCHIVE_ROW_FIELDS:
        return Empty_boc_archive(), "Archive BOC existante avec un schéma de lignes incompatible ; reconstruction partielle."
    return data, None


def boc_archive_session(item: dict[str, Any]) -> dict[str, Any]:
    rows = {
        ticker: [row.get(field) for field in BOC_ARCHIVE_ROW_FIELDS]
        for ticker, row in (item.get("rows") or {}).items()
    }
    return {
        "date": item["date"],
        "url": item.get("url"),
        "sha256": item.get("sha256"),
        "composite_level": item.get("composite_level"),
        "composite_variation_pct": item.get("composite_variation_pct"),
        "discovery": item.get("discovery"),
        "companies_read": len(rows),
        "rows": rows,
    }


def merge_boc_archive(
    existing: dict[str, Any], history: list[dict[str, Any]], updated_at: str
) -> dict[str, Any]:
    by_date: dict[str, dict[str, Any]] = {}
    for session_entry in existing.get("sessions") or []:
        if isinstance(session_entry, dict) and session_entry.get("date"):
            by_date[str(session_entry["date"])] = session_entry
    for item in history:
        by_date[item["date"]] = boc_archive_session(item)
    sessions = [by_date[date] for date in sorted(by_date)]
    archive = Empty_boc_archive()
    archive.update(
        {
            "updated_at": updated_at,
            "sessions_count": len(sessions),
            "first_date": sessions[0]["date"] if sessions else None,
            "last_date": sessions[-1]["date"] if sessions else None,
            "sessions": sessions,
        }
    )
    return archive


def boc_archive_history(archive: dict[str, Any]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for session_entry in archive.get("sessions") or []:
        rows: dict[str, dict[str, Any]] = {}
        for ticker, values in (session_entry.get("rows") or {}).items():
            if isinstance(values, dict):
                rows[ticker] = dict(values)
            elif isinstance(values, list):
                rows[ticker] = {
                    field: values[index] if index < len(values) else None
                    for index, field in enumerate(BOC_ARCHIVE_ROW_FIELDS)
                }
        history.append(
            {
                "date": session_entry.get("date"),
                "url": session_entry.get("url"),
                "sha256": session_entry.get("sha256"),
                "composite_level": session_entry.get("composite_level"),
                "composite_variation_pct": session_entry.get("composite_variation_pct"),
                "discovery": session_entry.get("discovery"),
                "rows": rows,
            }
        )
    return sorted(history, key=lambda item: item["date"] or "")


def write_boc_archive(path: Path, archive: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(archive, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp_path.replace(path)


def compute_long_history_stats(history: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session_data in history:
        for ticker, row in (session_data.get("rows") or {}).items():
            by_ticker[ticker].append(
                {
                    "date": session_data.get("date"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                    "traded_value_fcfa": row.get("traded_value_fcfa"),
                    "variation_pct": row.get("variation_pct"),
                }
            )

    def performance(close_points: list[dict[str, Any]], sessions_back: int) -> float | None:
        if len(close_points) < sessions_back + 1:
            return None
        return pct_change(close_points[-1]["close"], close_points[-1 - sessions_back]["close"])

    stats: dict[str, dict[str, Any]] = {}
    for ticker, points in by_ticker.items():
        points.sort(key=lambda point: point["date"] or "")
        close_points = [
            point for point in points if isinstance(point["close"], (int, float)) and point["close"] > 0
        ]
        traded_sessions = sum(
            1 for point in points if isinstance(point["volume"], (int, float)) and point["volume"] > 0
        )
        peak: float | None = None
        max_drawdown = 0.0
        for point in close_points:
            close = float(point["close"])
            peak = close if peak is None else max(peak, close)
            if peak:
                max_drawdown = min(max_drawdown, (close / peak - 1) * 100)
        daily_returns = [
            float(current["close"]) / float(previous["close"]) - 1
            for previous, current in zip(close_points, close_points[1:])
        ]
        volatility = None
        if len(daily_returns) >= 20:
            volatility = round(statistics.stdev(daily_returns) * (252**0.5) * 100, 4)
        variation_points = [
            point for point in points if isinstance(point["variation_pct"], (int, float))
        ]
        best = max(variation_points, key=lambda point: point["variation_pct"], default=None)
        worst = min(variation_points, key=lambda point: point["variation_pct"], default=None)
        stats[ticker] = {
            "sessions_available": len(points),
            "first_date": points[0]["date"] if points else None,
            "last_date": points[-1]["date"] if points else None,
            "traded_sessions": traded_sessions,
            "traded_share_pct": round(traded_sessions / len(points) * 100, 4) if points else None,
            "median_traded_value_fcfa": median_or_none(
                [
                    point["traded_value_fcfa"] if isinstance(point["traded_value_fcfa"], (int, float)) else 0
                    for point in points
                ]
            ),
            "median_traded_value_60_fcfa": median_or_none(
                [
                    point["traded_value_fcfa"] if isinstance(point["traded_value_fcfa"], (int, float)) else 0
                    for point in points[-60:]
                ]
            ),
            "performance_60_sessions_pct": performance(close_points, 60),
            "performance_120_sessions_pct": performance(close_points, 120),
            "performance_250_sessions_pct": performance(close_points, 250),
            "max_drawdown_pct": round(max_drawdown, 4) if close_points else None,
            "volatility_annualized_pct": volatility,
            "best_session_variation_pct": best["variation_pct"] if best else None,
            "best_session_date": best["date"] if best else None,
            "worst_session_variation_pct": worst["variation_pct"] if worst else None,
            "worst_session_date": worst["date"] if worst else None,
            "price_basis": "prix_publiés_non_ajustés_hors_dividendes_réinvestis",
        }
    return stats


def scrape_report_pages(session: requests.Session) -> list[dict[str, str]]:
    pages: dict[str, dict[str, str]] = {}
    first_soup = BeautifulSoup(str(fetch(session, URLS["reports_index"])), "lxml")
    max_page = 0
    soups = [first_soup]
    for anchor in first_soup.select("a[href]"):
        match = re.search(r"[?&]page=(\d+)", anchor.get("href", ""))
        if match:
            max_page = max(max_page, int(match.group(1)))
    for page_number in range(1, max_page + 1):
        soups.append(
            BeautifulSoup(str(fetch(session, f"{URLS['reports_index']}?page={page_number}")), "lxml")
        )
    for soup in soups:
        for anchor in soup.select("a[href]"):
            href = urljoin(URLS["reports_index"], anchor.get("href", ""))
            label = clean_text(anchor.get_text(" ", strip=True))
            if "/rapports-societe-cotes/" not in href or not label or label == "Rapports sociétés cotées":
                continue
            pages[href] = {"label": label, "url": href}
    return sorted(pages.values(), key=lambda item: item["label"].lower())


# ---------------------------------------------------------------------------
# Actualités et annonces : collecte automatique, datation honnête, classement.
# Une source news en échec ne bloque jamais la publication des données marché.
# ---------------------------------------------------------------------------

def parse_slash_date(value: str) -> str | None:
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", clean_text(value))
    if not match:
        return None
    return f"{int(match.group(3)):04d}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"


def parse_rss_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def canonical_issuer_key(value: str) -> str:
    tokens = []
    for token in normalize_key(value).split():
        if token in {"sa", "sas", "sarl"}:
            continue
        tokens.append(COUNTRY_CODE_WORDS.get(token, token))
    return " ".join(tokens)


def strip_tracking_params(url: str) -> str:
    parts = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(("utm_", "fbclid"))]
    return urlunparse(parts._replace(query=urlencode(query)))


def news_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def build_issuer_variant_map(companies: list[dict[str, Any]]) -> dict[str, str]:
    variants: dict[str, str] = {}
    for company in companies:
        # Le ticker lui-même est une variantes valide : plusieurs pages
        # « rapports sociétés cotées » de la BRVM sont libellées par le
        # seul ticker (ex. « NSBC », « BIIC »). Sans cette variante, la
        # page NSBC — qui contient bien des PDF — était silencieusement
        # ignorée (mesuré le 24/10/2026 : 20 liens PDF publiés, 0 indexé).
        # La correspondance reste exacte (clé normalisée complète).
        for candidate in [company.get("name"), (company.get("latest_boc") or {}).get("name"), company.get("ticker")]:
            if candidate:
                variants.setdefault(canonical_issuer_key(candidate), company["ticker"])
    return variants


def match_announcement_issuer(label: str, variants: dict[str, str]) -> list[str]:
    key = canonical_issuer_key(label)
    ticker = variants.get(key) or NEWS_TICKER_ALIASES.get(key)
    return [ticker] if ticker else []


def match_tickers_in_text(text: str, companies: list[dict[str, Any]]) -> list[str]:
    blob = f" {normalize_key(text)} "
    found: list[str] = []
    for phrase, ticker in NEWS_TICKER_ALIASES.items():
        if f" {phrase}" in blob and ticker not in found:
            found.append(ticker)
    for company in companies:
        ticker = company["ticker"]
        if ticker in found:
            continue
        full_name = canonical_issuer_key(company.get("name") or "")
        if len(full_name) >= 10 and full_name in blob:
            found.append(ticker)
            continue
        if re.search(rf"\b{ticker.lower()}\b", blob):
            found.append(ticker)
    return found


def classify_news(item: dict[str, Any]) -> tuple[str, list[str]]:
    text = normalize_key(f"{item.get('title') or ''} {item.get('excerpt') or ''} {item.get('category') or ''}")
    tags: list[str] = []
    if "dividende" in text:
        tags.append("dividende")
    if any(word in text for word in ["resultat", "benefice", "chiffre d affaires", "produit net bancaire"]):
        tags.append("resultats")
    if any(word in text for word in ["dirigeant", "nomination", "nomme", "directeur general", "conseil d administration"]):
        tags.append("gouvernance")
    if "notation" in text:
        tags.append("notation")
    if any(word in text for word in ["assemblee generale", "convocation", "resolution"]):
        tags.append("vie_sociale")
    if any(word in text for word in ["taux directeur", "politique monetaire", "bceao", "inflation"]):
        tags.append("politique_monetaire")
    if any(word in text for word in ["tresor", "adjudication", "dette publique", "obligation"]):
        tags.append("dette_publique")
    if any(word in text for word in ["petrole", "bitume", "cacao", "caoutchouc", "palme", "mine", "aurifere"]):
        tags.append("matieres_premieres")
    if any(word in text for word in ["sanction", "commission bancaire", "amf", "crepmf", "regulateur"]):
        tags.append("regulation")

    if item.get("tickers"):
        relevance = "societe"
    elif item.get("source_id") in {"bceao", "umoa_titres"} or any(k in text for k in MACRO_KEYWORDS):
        relevance = "macro"
    elif "brvm" in text or item.get("source_id") in {"brvm_actualites", "brvm_annonces"}:
        relevance = "marche"
    else:
        relevance = "general"
    return relevance, tags


def scrape_brvm_announcements(session: requests.Session) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for slug, category_label in ANNOUNCEMENT_CATEGORIES.items():
        page_url = f"{BASE}/fr/emetteurs/type-annonces/{slug}"
        soup = BeautifulSoup(str(fetch(session, page_url)), "lxml")
        target = None
        for table in soup.find_all("table"):
            header = clean_text(table.get_text(" ", strip=True))
            if "Société" in header and "Titre" in header and "Date" in header:
                target = table
                break
        if target is None:
            raise ValueError(f"Table des annonces introuvable pour {slug}.")
        for row in target.find_all("tr")[1:]:
            cells = row.find_all(["th", "td"])
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 3 or not values[2]:
                continue
            pdf_url = None
            for anchor in row.select("a[href]"):
                if ".pdf" in anchor["href"].lower():
                    pdf_url = urljoin(page_url, anchor["href"])
                    break
            if not pdf_url:
                continue
            items.append(
                {
                    "source_id": "brvm_annonces",
                    "source_label": "BRVM — Annonces des émetteurs",
                    "source_type": "officiel_bourse",
                    "category": category_label,
                    "title": values[2],
                    "url": pdf_url,
                    "document_type": "pdf",
                    "published_date": parse_slash_date(values[0]) or parse_french_long_date(values[0]),
                    "date_type": "publiee_par_source",
                    "issuer_label": values[1] or None,
                    "excerpt": None,
                }
            )
    return items


def scrape_brvm_actualites(session: requests.Session, pages: int = 2) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page_number in range(pages):
        page_url = URLS["news_actualites"] if page_number == 0 else f"{URLS['news_actualites']}?page={page_number}"
        soup = BeautifulSoup(str(fetch(session, page_url)), "lxml")
        for row in soup.select(".view-actualites .views-row"):
            anchor = None
            for candidate in row.select("a[href]"):
                if "/mediacentre/actualites/" in candidate["href"]:
                    anchor = candidate
                    break
            if anchor is None:
                continue
            lines = [clean_text(line) for line in row.get_text("\n", strip=True).split("\n")]
            lines = [line for line in lines if line and line.lower() != "lire plus"]
            if not lines:
                continue
            title = lines[0]
            excerpt = " ".join(lines[1:])[:360] or None
            # La BRVM n'expose pas de date de publication structurée : on ne retient
            # que la date écrite dans l'extrait, étiquetée comme telle.
            items.append(
                {
                    "source_id": "brvm_actualites",
                    "source_label": "BRVM — Actualités",
                    "source_type": "officiel_bourse",
                    "category": "Actualité du marché",
                    "title": title,
                    "url": urljoin(page_url, anchor["href"]),
                    "document_type": "article",
                    "published_date": parse_french_long_date(excerpt or ""),
                    "date_type": "mentionnee_dans_texte",
                    "issuer_label": None,
                    "excerpt": excerpt,
                }
            )
    return items


def scrape_bceao_press(session: requests.Session) -> list[dict[str, Any]]:
    soup = BeautifulSoup(str(fetch(session, URLS["bceao_press"])), "lxml")
    best_by_url: dict[str, str] = {}
    for anchor in soup.select('a[href*="/fr/communique-presse/"]'):
        url = urljoin(URLS["bceao_press"], anchor["href"])
        text = clean_text(anchor.get_text(" ", strip=True))
        if len(text) > len(best_by_url.get(url, "")):
            best_by_url[url] = text
    items: list[dict[str, Any]] = []
    seen_titles: set[tuple[str, str | None]] = set()
    for url, text in best_by_url.items():
        date_match = re.match(r"(\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4})\s+(.*)$", text)
        published = parse_french_long_date(date_match.group(1)) if date_match else None
        title = clean_text(date_match.group(2)) if date_match else text
        if len(title) < 14:
            continue
        dedupe_key = (normalize_key(title), published)
        if dedupe_key in seen_titles:
            continue
        seen_titles.add(dedupe_key)
        items.append(
            {
                "source_id": "bceao",
                "source_label": "BCEAO — Communiqués de presse",
                "source_type": "officiel_institution",
                "category": "Politique monétaire et régulation UEMOA",
                "title": title,
                "url": url,
                "document_type": "communique",
                "published_date": published,
                "date_type": "publiee_par_source",
                "issuer_label": None,
                "excerpt": None,
            }
        )
    return items


def scrape_rss_feed(session: requests.Session, url: str, source_id: str, source_label: str,
                    source_type: str, category: str) -> list[dict[str, Any]]:
    content = bytes(fetch(session, url, binary=True))
    soup = BeautifulSoup(content, "xml")
    items: list[dict[str, Any]] = []
    for entry in soup.find_all("item"):
        def field_text(name: str) -> str:
            node = entry.find(name)
            return clean_text(node.get_text(" ", strip=True)) if node else ""
        title = field_text("title")
        link = field_text("link")
        if not title or not link:
            continue
        raw_description = entry.find("description")
        excerpt = None
        if raw_description is not None:
            fragment = BeautifulSoup(raw_description.get_text(), "lxml")
            excerpt = clean_text(fragment.get_text(" ", strip=True))[:320] or None
        items.append(
            {
                "source_id": source_id,
                "source_label": source_label,
                "source_type": source_type,
                "category": category,
                "title": title,
                "url": strip_tracking_params(link),
                "document_type": "article",
                "published_date": parse_rss_date(field_text("pubDate") or None),
                "date_type": "publiee_par_source",
                "issuer_label": None,
                "excerpt": excerpt,
            }
        )
    return items


# ---------------------------------------------------------------------------
# Macro automatique + calendrier d'échéances.
# Sources structurantes uniquement : dernier communiqué du Comité de Politique
# Monétaire BCEAO (texte officiel relu par expressions ciblées), événements
# BCEAO datés, tableaux UMOA-Titres des émissions à venir/planifiées, et
# calendrier officiel BRVM des dividendes déjà collecté. Aucun taux n'est
# déduit d'un titre de presse ; à défaut d'extraction propre, le champ reste
# vide et le statut de la source est publié.
# ---------------------------------------------------------------------------

def _first_percent(text: str, patterns: list[str]) -> float | int | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return parse_number(match.group(match.lastindex or 1))
    return None


def _quarter_before(text: str, position: int) -> str | None:
    quarters = list(
        re.finditer(
            r"((?:premier|deuxième|troisième|quatrième)\s+trimestre\s+\d{4})",
            text[:position],
            flags=re.I,
        )
    )
    return clean_text(quarters[-1].group(1)).lower() if quarters else None


def extract_bceao_cpm_indicators(text: str) -> dict[str, Any]:
    """Extrait les repères chiffrés explicitement écrits dans un communiqué CPM."""
    clean = clean_text(text).replace("’", "'")
    indicators: dict[str, Any] = {
        "meeting_date": None,
        "rates_effective_since": None,
        "policy_rate_pct": None,
        "marginal_lending_rate_pct": None,
        "reserve_requirement_pct": None,
        "inflation_latest_pct": None,
        "inflation_latest_period": None,
        "inflation_forecast_year": None,
        "inflation_forecast_pct": None,
        "growth_latest_pct": None,
        "growth_latest_period": None,
        "growth_forecast_year": None,
        "growth_forecast_pct": None,
        "private_credit_growth_pct": None,
        "decision_excerpt": None,
    }
    meeting = re.search(r"réunion tenue le (\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4})", clean, flags=re.I)
    if meeting:
        indicators["meeting_date"] = parse_french_long_date(meeting.group(1))
    effective = re.search(r"en vigueur depuis le (\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4})", clean, flags=re.I)
    if effective:
        indicators["rates_effective_since"] = parse_french_long_date(effective.group(1))
    indicators["policy_rate_pct"] = _first_percent(
        clean,
        [
            r"principal taux directeur[^.]{0,180}?([0-9]+,[0-9]+)\s*%",
            r"taux minimum de soumission[^.]{0,180}?([0-9]+,[0-9]+)\s*%",
        ],
    )
    indicators["marginal_lending_rate_pct"] = _first_percent(
        clean,
        [
            r"guichet de prêt marginal[^.]{0,180}?([0-9]+,[0-9]+)\s*%",
            r"prêt marginal[^.]{0,120}?([0-9]+,[0-9]+)\s*%",
        ],
    )
    indicators["reserve_requirement_pct"] = _first_percent(
        clean,
        [
            r"(?:maintenir|maintenu|fixé|fixer|laisser|à)\s*(?:à\s*)?([0-9]+,[0-9]+)\s*%,?\s*(?:le\s+)?coefficient des réserves obligatoires",
            r"coefficient des réserves obligatoires[^.]{0,160}?([0-9]+,[0-9]+)\s*%",
        ],
    )
    inflation = re.search(
        r"taux d'inflation s'est établi à\s*([-+]?[0-9]+,[0-9]+)\s*%\s+au\s+([^,.]+)",
        clean,
        flags=re.I,
    )
    if inflation:
        indicators["inflation_latest_pct"] = parse_number(inflation.group(1))
        indicators["inflation_latest_period"] = clean_text(inflation.group(2)).lower()
    inflation_forecast = re.search(
        r"Pour\s+(\d{4}),?\s+le taux d'inflation devrait[^.]{0,160}?([0-9]+,[0-9]+)\s*%",
        clean,
        flags=re.I,
    )
    if inflation_forecast:
        indicators["inflation_forecast_year"] = int(inflation_forecast.group(1))
        indicators["inflation_forecast_pct"] = parse_number(inflation_forecast.group(2))
    growth = re.search(r"croissance estimée à\s*([0-9]+,[0-9]+)\s*%\s+en glissement annuel", clean, flags=re.I)
    if growth:
        indicators["growth_latest_pct"] = parse_number(growth.group(1))
        indicators["growth_latest_period"] = _quarter_before(clean, growth.start())
    growth_forecast = re.search(
        r"Pour\s+l'année\s+(\d{4})[^.]{0,140}?croissance économique est attendue à\s*([0-9]+,[0-9]+)\s*%",
        clean,
        flags=re.I,
    )
    if growth_forecast:
        indicators["growth_forecast_year"] = int(growth_forecast.group(1))
        indicators["growth_forecast_pct"] = parse_number(growth_forecast.group(2))
    indicators["private_credit_growth_pct"] = _first_percent(
        clean,
        [r"crédit bancaire accordé au secteur privé a progressé de\s*([0-9]+,[0-9]+)\s*%"],
    )
    decision = re.search(
        r"Le Comité de Politique Monétaire.*?réserves obligatoires[^.]*\.",
        clean,
        flags=re.I | re.S,
    )
    indicators["decision_excerpt"] = clean_text(decision.group(0))[:1100] if decision else clean[:700] or None
    return indicators


def scrape_bceao_cpm(session: requests.Session) -> dict[str, Any]:
    press_items = scrape_bceao_press(session)
    candidates = [
        item
        for item in press_items
        if "comite de politique monetaire" in normalize_key(item.get("title") or "")
        and item.get("published_date")
    ]
    candidates.sort(key=lambda item: item.get("published_date") or "", reverse=True)
    if not candidates:
        raise ValueError("Aucun communiqué CPM BCEAO daté trouvé dans la page officielle des communiqués.")
    last_error: Exception | None = None
    for candidate in candidates[:3]:
        try:
            soup = BeautifulSoup(str(fetch(session, candidate["url"])), "lxml")
            text = ""
            for selector in ["article", ".field--name-body", ".node__content", "main"]:
                node = soup.select_one(selector)
                if node:
                    text = clean_text(node.get_text(" ", strip=True))
                    if len(text) >= 500:
                        break
            if len(text) < 500:
                text = clean_text(soup.get_text(" ", strip=True))
            indicators = extract_bceao_cpm_indicators(text)
            if indicators.get("policy_rate_pct") is None:
                raise ValueError("taux directeur non extrait proprement du communiqué CPM")
            return {
                "status": "collecte",
                "source_label": "BCEAO — Communiqué du Comité de Politique Monétaire",
                "source_url": candidate["url"],
                "title": candidate["title"],
                "published_date": candidate.get("published_date"),
                **indicators,
            }
        except Exception as exc:  # on tente le communiqué CPM précédent, sans inventer de valeur
            last_error = exc
            continue
    raise ValueError(f"Communiqué CPM BCEAO non exploitable ({last_error}).")


def scrape_bceao_events(session: requests.Session) -> list[dict[str, Any]]:
    page_url = URLS["bceao_events"]
    soup = BeautifulSoup(str(fetch(session, page_url)), "lxml")
    events_by_url: dict[str, dict[str, Any]] = {}
    for anchor in soup.select('a[href*="/fr/evenement/"]'):
        url = urljoin(page_url, anchor.get("href", ""))
        title = clean_text(anchor.get_text(" ", strip=True))
        if len(title) < 12:
            continue
        node: Any = anchor
        event_date = None
        parent_text = ""
        for _ in range(6):
            node = getattr(node, "parent", None)
            if node is None:
                break
            parent_text = clean_text(node.get_text(" ", strip=True)) if hasattr(node, "get_text") else ""
            match = re.match(r"(\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4})\s+(.*)$", parent_text)
            if match:
                event_date = parse_french_long_date(match.group(1))
                parent_text = clean_text(match.group(2))
                break
        if not event_date:
            continue
        detail = parent_text if len(parent_text) > len(title) + 8 else None
        current = events_by_url.get(url)
        candidate = {
            "date": event_date,
            "title": title,
            "detail": detail,
            "url": url,
            "source_label": "BCEAO — Événements",
            "source_url": page_url,
        }
        if current is None or len(title) > len(current.get("title") or ""):
            events_by_url[url] = candidate
    return sorted(events_by_url.values(), key=lambda item: item["date"], reverse=True)


def _umoa_table_rows(table: Any, page_url: str, reference_date: str, source_table: str) -> list[dict[str, Any]]:
    if table is None:
        return []
    header_cells = []
    rows: list[dict[str, Any]] = []
    reference = datetime.fromisoformat(reference_date).date()
    for row_index, tr in enumerate(table.find_all("tr")):
        cells = tr.find_all(["th", "td"])
        values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        if row_index == 0:
            header_cells = [normalize_key(value) for value in values]
            continue
        if not values or all(not value for value in values):
            continue

        def cell_value(*needles: str) -> str:
            for index, header in enumerate(header_cells):
                if any(needle in header for needle in needles) and index < len(values):
                    return values[index]
            return ""

        def cell_link(*needles: str) -> str | None:
            for index, header in enumerate(header_cells):
                if any(needle in header for needle in needles) and index < len(cells):
                    anchor = cells[index].find("a", href=True)
                    return urljoin(page_url, anchor["href"]) if anchor else None
            anchor = tr.find("a", href=True)
            return urljoin(page_url, anchor["href"]) if anchor else None

        operation_date = parse_slash_date(cell_value("date de l operation", "date operation"))
        if not operation_date:
            continue
        amount_million = parse_number(cell_value("montant"))
        operation = datetime.fromisoformat(operation_date).date()
        instrument = cell_value("instrument")
        maturity = parse_slash_date(cell_value("echeance"))
        rows.append(
            {
                "issuer_country": cell_value("emetteur"),
                "instrument": instrument if instrument and instrument != "--" else None,
                "details_label": cell_value("precisions") if cell_value("precisions") != "--" else None,
                "operation_date": operation_date,
                "value_date": parse_slash_date(cell_value("date de valeur")),
                "maturity_date": maturity,
                "amount_million_fcfa": amount_million,
                "amount_fcfa": int(amount_million * 1_000_000) if isinstance(amount_million, (int, float)) else None,
                "url": cell_link("plus d infos", "more"),
                "source_status_label": cell_value("etat", "statut") or None,
                "computed_status": "a_venir" if operation >= reference else "passee",
                "source_table": source_table,
                "source_label": "UMOA-Titres — Émissions",
                "source_url": page_url,
            }
        )
    return rows


def parse_umoa_emissions_page(html: str, page_url: str, reference_date: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    # La table « à venir » (date de valeur, instrument) prime sur la table
    # « planifiées » lorsqu'une même opération apparaît dans les deux.
    for table_id in ["emission-hub-planifie-par", "emission-hub-avenir-par"]:
        for row in _umoa_table_rows(soup.find("table", id=table_id), page_url, reference_date, table_id):
            key = (row["operation_date"], normalize_key(row["issuer_country"]), row.get("url") or "")
            merged[key] = row
    return sorted(merged.values(), key=lambda item: (item["operation_date"], item["issuer_country"]))


def scrape_umoa_planned_issuances(session: requests.Session, reference_date: str) -> list[dict[str, Any]]:
    page_url = URLS["umoa_emissions"]
    return parse_umoa_emissions_page(str(fetch(session, page_url)), page_url, reference_date)


def _sum_umoa_window(issuances: list[dict[str, Any]], reference_date: str, days: int) -> dict[str, Any]:
    reference = datetime.fromisoformat(reference_date).date()
    end = reference + timedelta(days=days)
    selected = [
        item
        for item in issuances
        if item.get("operation_date")
        and reference <= datetime.fromisoformat(item["operation_date"]).date() <= end
    ]
    return {
        "days": days,
        "operations": len(selected),
        "amount_fcfa": sum(item["amount_fcfa"] for item in selected if isinstance(item.get("amount_fcfa"), (int, float))),
        "amount_known_operations": sum(1 for item in selected if isinstance(item.get("amount_fcfa"), (int, float))),
    }


def collect_macro_context(session: requests.Session, reference_date: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    macro: dict[str, Any] = {
        "reference_date": reference_date,
        "bceao_cpm": {"status": "non_tente"},
        "bceao_events": [],
        "umoa_issuances": [],
        "umoa_summary": {},
        "notes": [
            "Contexte de taux et de liquidité à lire avant une décision ; aucune déduction automatique d'achat ou de vente.",
            "Les montants UMOA-Titres sont les montants annoncés/mis en adjudication publiés dans les tableaux officiels, pas des montants levés.",
        ],
    }
    try:
        macro["bceao_cpm"] = scrape_bceao_cpm(session)
        print(
            f"[SIGMA] BCEAO CPM {macro['bceao_cpm'].get('published_date')} : "
            f"taux directeur {macro['bceao_cpm'].get('policy_rate_pct')} %",
            file=sys.stderr,
        )
    except Exception as exc:
        macro["bceao_cpm"] = {"status": "non_disponible", "reason": str(exc), "source_url": URLS["bceao_press"]}
        warnings.append(f"Macro BCEAO/CPM indisponible ({exc}).")
    try:
        macro["bceao_events"] = scrape_bceao_events(session)
    except Exception as exc:
        warnings.append(f"Événements BCEAO indisponibles ({exc}).")
    try:
        issuances = scrape_umoa_planned_issuances(session, reference_date)
        macro["umoa_issuances"] = issuances
        upcoming = [item for item in issuances if item.get("computed_status") == "a_venir"]
        by_country: dict[str, dict[str, Any]] = {}
        reference = datetime.fromisoformat(reference_date).date()
        for item in upcoming:
            if datetime.fromisoformat(item["operation_date"]).date() > reference + timedelta(days=90):
                continue
            entry = by_country.setdefault(
                item["issuer_country"], {"issuer_country": item["issuer_country"], "operations": 0, "amount_fcfa": 0}
            )
            entry["operations"] += 1
            if isinstance(item.get("amount_fcfa"), (int, float)):
                entry["amount_fcfa"] += item["amount_fcfa"]
        macro["umoa_summary"] = {
            "status": "collecte",
            "source_url": URLS["umoa_emissions"],
            "upcoming_operations": len(upcoming),
            "next_operation": upcoming[0] if upcoming else None,
            "windows": {f"next_{days}d": _sum_umoa_window(issuances, reference_date, days) for days in (7, 30, 90)},
            "by_country_next_90d": sorted(by_country.values(), key=lambda item: item["amount_fcfa"], reverse=True),
        }
        if any(
            item.get("computed_status") == "a_venir"
            and "realise" in normalize_key(item.get("source_status_label") or "")
            for item in issuances
        ):
            macro["notes"].append(
                "UMOA-Titres libelle certaines opérations futures « réalisée » dans son tableau ; SIGMA reclasse l'état uniquement par date d'opération et conserve le libellé source."
            )
        print(f"[SIGMA] UMOA-Titres : {len(upcoming)} opérations à venir/planifiées", file=sys.stderr)
    except Exception as exc:
        macro["umoa_summary"] = {"status": "non_disponible", "reason": str(exc), "source_url": URLS["umoa_emissions"]}
        warnings.append(f"Émissions UMOA-Titres indisponibles ({exc}).")
    return macro, warnings


def _calendar_event_id(event_type: str, date: str, title: str, url: str | None) -> str:
    return hashlib.sha1(f"{event_type}|{date}|{title}|{url or ''}".encode("utf-8")).hexdigest()[:14]


def build_calendar_events(
    reference_date: str,
    dividends: list[dict[str, Any]],
    macro_context: dict[str, Any],
    companies: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    reference = datetime.fromisoformat(reference_date).date()
    end = reference + timedelta(days=370)
    variants = build_issuer_variant_map(companies or [])
    events: list[dict[str, Any]] = []

    def add_event(event: dict[str, Any]) -> None:
        raw_date = event.get("date")
        if not raw_date:
            return
        event_date = datetime.fromisoformat(str(raw_date)).date()
        if not (reference <= event_date <= end):
            return
        event["id"] = _calendar_event_id(event["type"], event["date"], event["title"], event.get("url"))
        event["in_days"] = (event_date - reference).days
        events.append(event)

    for div in dividends:
        tickers = match_announcement_issuer(div.get("issuer") or "", variants) if variants else []
        base_detail = (
            f"Exercice {div.get('fiscal_year') or 'non précisé'} · montant net publié : "
            f"{div.get('net_amount_fcfa')} FCFA par action."
        )
        if div.get("ex_date"):
            add_event(
                {
                    "date": div["ex_date"],
                    "type": "dividende_ex_date",
                    "category": "Dividendes BRVM",
                    "title": f"Ex-dividende — {div.get('issuer')}",
                    "detail": base_detail + " Après cette date, l'acheteur ne reçoit pas ce dividende.",
                    "issuer_label": div.get("issuer"),
                    "tickers": tickers,
                    "amount_fcfa": div.get("net_amount_fcfa"),
                    "amount_label": "montant net par action",
                    "url": div.get("notice_url") or div.get("source_url"),
                    "source_label": "BRVM — Paiement de dividendes",
                    "date_type": "publiee_par_source",
                }
            )
        if div.get("payment_date"):
            add_event(
                {
                    "date": div["payment_date"],
                    "type": "dividende_paiement",
                    "category": "Dividendes BRVM",
                    "title": f"Paiement de dividende — {div.get('issuer')}",
                    "detail": base_detail + " Date de paiement publiée par la BRVM ; le crédit effectif dépend de la SGI/dépositaire.",
                    "issuer_label": div.get("issuer"),
                    "tickers": tickers,
                    "amount_fcfa": div.get("net_amount_fcfa"),
                    "amount_label": "montant net par action",
                    "url": div.get("notice_url") or div.get("source_url"),
                    "source_label": "BRVM — Paiement de dividendes",
                    "date_type": "publiee_par_source",
                }
            )

    for issuance in macro_context.get("umoa_issuances") or []:
        add_event(
            {
                "date": issuance.get("operation_date"),
                "type": "emission_titres_publics_umoa",
                "category": "Titres publics UMOA",
                "title": f"Émission de titres publics — {issuance.get('issuer_country')}",
                "detail": (
                    f"Opération UMOA-Titres annoncée"
                    + (f" · instrument {issuance['instrument']}" if issuance.get("instrument") else "")
                    + (f" · date de valeur {issuance['value_date']}" if issuance.get("value_date") else "")
                    + ". À situer dans le contexte de liquidité bancaire et des taux souverains, sans en déduire un mouvement de cours."
                ),
                "issuer_label": issuance.get("issuer_country"),
                "tickers": [],
                "amount_fcfa": issuance.get("amount_fcfa"),
                "amount_label": "montant annoncé",
                "url": issuance.get("url") or issuance.get("source_url"),
                "source_label": issuance.get("source_label") or "UMOA-Titres — Émissions",
                "date_type": "date_operation_source",
            }
        )

    for bceao_event in macro_context.get("bceao_events") or []:
        add_event(
            {
                "date": bceao_event.get("date"),
                "type": "evenement_bceao",
                "category": "BCEAO / UEMOA",
                "title": bceao_event.get("title"),
                "detail": bceao_event.get("detail") or "Événement institutionnel daté par la BCEAO.",
                "issuer_label": "BCEAO",
                "tickers": [],
                "amount_fcfa": None,
                "amount_label": None,
                "url": bceao_event.get("url"),
                "source_label": bceao_event.get("source_label") or "BCEAO — Événements",
                "date_type": "publiee_par_source",
            }
        )

    deduped: dict[str, dict[str, Any]] = {}
    for event in events:
        deduped.setdefault(event["id"], event)
    return sorted(deduped.values(), key=lambda item: (item["date"], item["category"], item["title"]))


def collect_news(session: requests.Session, companies: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    raw_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    scrapers = [
        ("BRVM — Annonces des émetteurs", lambda: scrape_brvm_announcements(session)),
        ("BRVM — Actualités", lambda: scrape_brvm_actualites(session)),
        ("BCEAO — Communiqués", lambda: scrape_bceao_press(session)),
        ("UMOA-Titres — Flux RSS", lambda: scrape_rss_feed(
            session, URLS["umoa_rss"], "umoa_titres", "UMOA-Titres",
            "officiel_institution", "Marché des titres publics")),
        ("Sika Finance — Flux RSS", lambda: scrape_rss_feed(
            session, URLS["sika_rss"], "sika_finance", "Sika Finance (presse)",
            "presse_specialisee", "Presse économique régionale")),
    ]
    for label, scraper in scrapers:
        try:
            raw_items.extend(scraper())
        except Exception as exc:  # une source news en échec ne bloque pas le reste
            warnings.append(f"Source d'actualités indisponible : {label} ({exc}).")
            print(f"[SIGMA] News ignorée ({label}) : {exc}", file=sys.stderr)

    variants = build_issuer_variant_map(companies)
    deduped: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        url = strip_tracking_params(item["url"])
        item = {**item, "url": url}
        if item.get("issuer_label"):
            item["tickers"] = match_announcement_issuer(item["issuer_label"], variants)
            # Repli sur le titre si le libellé émetteur est ambigu — sauf véhicules
            # obligataires (FCTC…) qui ne sont pas l'action cotée.
            if not item["tickers"] and not normalize_key(item.get("title") or "").startswith("fctc"):
                item["tickers"] = match_tickers_in_text(item.get("title") or "", companies)
        else:
            item["tickers"] = match_tickers_in_text(
                f"{item.get('title') or ''} {item.get('excerpt') or ''}", companies
            )
        item["relevance"], item["tags"] = classify_news(item)
        item["id"] = news_id(url)
        deduped.setdefault(url, item)

    news = sorted(
        deduped.values(),
        key=lambda entry: (entry["published_date"] is None, entry["published_date"] or ""),
        reverse=True,
    )
    # Tri décroissant propre : les dates absentes partent en fin de liste.
    dated = [entry for entry in news if entry["published_date"]]
    undated = [entry for entry in news if not entry["published_date"]]
    dated.sort(key=lambda entry: entry["published_date"], reverse=True)
    return dated + undated, warnings


# ---------------------------------------------------------------------------
# Documents financiers officiels des émetteurs + extraction prudente des
# agrégats annuels. Règle : aucune valeur sans unité explicite sur la page,
# sans ligne source conservée, et jamais de score calculé sur ces extractions
# tant qu'elles n'ont pas été confirmées à la lecture du document.
# ---------------------------------------------------------------------------

REPORT_LABEL_ALIASES = {
    "sib": "SIBC",
    "biic": "BICB",
    "bbgci": "BBGC",
    "air liquide cote d ivoire": "SIVC",
    "erium cote d ivoire": "SIVC",
    "sicable": "CABC",
    "lnb": "LNBB",
    "tractafric cote d ivoire": "PRSC",
    "crown siem cote d ivoire": "SEMC",
    "sicor": "SICC",
    "solibra": "SLBC",
    "smb": "SMBC",
    "sogb": "SOGC",
    "sitab": "STBC",
    "total": "TTLC",
    "sgci": "SGBC",
    "sgb cote d ivoire": "SGBC",
}
ANNUAL_DOC_PRIORITY = {
    "etats_financiers_approuves": 0,
    "comptes_ifrs": 1,
    "etats_financiers": 2,
    "rapport_activites_annuel": 3,
    "rapport_annuel": 4,
    "resultats_consolides": 5,
    "etats_condenses": 6,
}
UNIT_MULTIPLIERS = {"unites": 1, "milliers": 1_000, "millions": 1_000_000, "milliards": 1_000_000_000}
# OCR contrôlé : uniquement en repli lorsque le texte natif du PDF ne donne
# aucun agrégat. Les pages sont rendues puis relues deux fois (niveaux de
# gris et image inversée, pour les lignes blanches sur fond foncé) ; les
# mots OCR portent leurs coordonnées et leur confiance Tesseract, et les
# mêmes contrôles de plausibilité/recoupement que le texte natif s'appliquent.
OCR_CACHE_VERSION = "ocr-tesseract-fra-psm6-dual-300dpi-v7"
OCR_DPI = 300
OCR_MAX_PAGES = 24
OCR_MIN_LINE_MEAN_CONFIDENCE = 55.0
OCR_MIN_NUMERIC_CONFIDENCE = 40.0
FIGURE_LABELS = {
    "chiffre_affaires": [r"chiffre d['’]affaires", r"produits des activités ordinaires"],
    "produit_net_bancaire": [r"produit net bancaire"],
    "resultat_net": [
        r"résultat net de l['’]exercice",
        r"résultat net de l['’]ensemble consolidé",
        r"résultat net\s*$",
        r"résultat net\b",
        r"bénéfice net de l['’]exercice",
        # Variantes sans accents fréquentes dans les tableaux bancaires et
        # après OCR (ex. « RESULTAT NET » en majuscules).
        r"resultat net de l['’]exercice",
        r"resultat net\s*$",
        r"resultat net\b",
        r"benefice net de l['’]exercice",
        # Poste de capitaux propres des bilans bancaires UMOA : le
        # « résultat de l'exercice » y est le bénéfice/perte net de
        # l'exercice (il recoupe la ligne finale du compte de résultat).
        # Rang inférieur aux libellés explicites « résultat net », et jamais
        # si la ligne précise « avant impôt ».
        r"résultat de l['’]exercice(?!.*avant imp[oô]t)",
        r"resultat de l['’]exercice(?!.*avant impot)",
    ],
    "resultat_net_part_groupe": [
        r"résultat net attribuable aux propriétaires",
        r"résultat net[,\s]+part du groupe",
        # Libellé SYSCOHADA historique relevé dans les états SNTS 2016–2018.
        r"part de l['’]entreprise consolidante",
        r"resultat net[,\s]+part du groupe",
        r"part de l['’]entreprise consolidante",
    ],
    # Numérateur IAS 33 lorsqu'il est explicite dans une note BPA. Il est
    # distinct du résultat net total : une ligne « attribuable aux
    # actionnaires ordinaires » ne doit donc pas être rangée dans le seul
    # agrégat de résultat de l'ensemble consolidé.
    "resultat_net_attribuable_ordinaires": [
        r"(?:résultat|bénéfice)(?: net)? attribuable aux actionnaires ordinaires",
        r"(?:résultat|bénéfice)(?: net)? attribuable aux porteurs d['’]actions ordinaires",
        r"(?:résultat|bénéfice)(?: net)? attribuable aux détenteurs d['’]actions ordinaires",
        r"(?:resultat|benefice)(?: net)? attribuable aux actionnaires ordinaires",
        r"(?:resultat|benefice)(?: net)? attribuable aux porteurs d['’]actions ordinaires",
        r"(?:resultat|benefice)(?: net)? attribuable aux detenteurs d['’]actions ordinaires",
    ],
    "capitaux_propres": [
        r"total capitaux propres et ressources assimilées",
        r"capitaux propres et ressources assimilées",
        r"total (?:des )?capitaux propres",
        r"capitaux propres\b",
    ],
    "total_bilan": [
        r"\bDZ\s+total général",
        r"total\s*du\s+passif et des capitaux propres",
        r"total\s*du\s+passif\b",
        r"total\s*passif\b",
        r"\bBZ\s+total général",
        r"total\s*de\s*l['’]actif\b",
        r"total\s*actif\b",
        r"total\s*du\s+bilan\b",
        r"total\s*bilan\b",
        r"total\s*général\b",
        r"total\s*general\b",
    ],
    # Tableau des flux : on ne retient que les sous-totaux explicitement
    # libellés « activités opérationnelles / d'exploitation », jamais les
    # composantes intermédiaires (capacité d'autofinancement, variation du
    # besoin en fonds de roulement, impôts payés, etc.).
    "flux_tresorerie_operationnel": [
        r"trésorerie (?:nette )?(?:générée|dégagée) par les activités? d['’]exploitation",
        r"flux (?:nets? )?de trésorerie (?:générés? par(?: les)?|provenant des|liés? aux) activités? (?:opérationnelles?|d['’]exploitation)",
        r"flux (?:nets? )?de trésorerie (?:générés? par|provenant de|liés? à) l['’]activité (?:opérationnelle|d['’]exploitation)",
        r"trésorerie nette (?:générée par(?: les)?|provenant des|liée aux) activités? (?:opérationnelles?|d['’]exploitation)",
        r"flux de trésorerie des activités? (?:opérationnelles?|d['’]exploitation)",
        r"flux (?:nets? )?de tresorerie (?:generes? par(?: les)?|provenant des|lies? aux) activites? (?:operationnelles?|d['’]exploitation)",
        r"tresorerie (?:nette )?(?:generee|degagee) par les activites? d['’]exploitation",
    ],
    "investissements_immobilisations": [
        r"acquisitions? d['’]immobilisations corporelles et incorporelles",
        r"décaissements liés aux acquisitions d['’]immobilisations (?:corporelles et incorporelles|corp\.?\s+et\s+incorp\.?)",
        r"investissements en immobilisations corporelles et incorporelles",
    ],
    "dividendes_verses": [
        r"dividendes (?:versés|payés)(?: aux actionnaires)?\b",
    ],
    "tresorerie_equivalents": [
        r"trésorerie et équivalents de trésorerie",
        r"tresorerie et equivalents de tresorerie",
        r"disponibilités et quasi-disponibilités(?:\s+à la clôture)?\b",
        r"disponibilites et quasi-disponibilites(?:\s+a la cloture)?\b",
        r"trésorerie[- ]actif\b",
        r"tresorerie[- ]actif\b",
    ],
    "tresorerie_passif": [
        r"trésorerie[- ]passif\b",
        r"tresorerie[- ]passif\b",
    ],
    "tresorerie_nette": [
        r"trésorerie nette (?:au 31 décembre|à la clôture|en fin d['’]exercice)",
        r"tresorerie nette (?:au 31 decembre|a la cloture|en fin d['’]exercice)",
    ],
    "dettes_financieres_non_courantes": [
        r"passifs financiers non courants",
        r"emprunts et dettes financières non courant(?:e)s",
        r"dettes financières non courantes",
        r"dettes financières et ressources assimilées",
        r"emprunts et dettes financières à long terme",
        r"emprunts et dettes financieres non courant(?:e)s",
        r"dettes financieres non courantes",
        r"dettes financieres et ressources assimilees",
    ],
    "dettes_financieres_courantes": [
        r"passifs financiers courants",
        r"emprunts et dettes financières courant(?:e)s",
        r"dettes financières courantes",
        r"emprunts et dettes financières à court terme",
        r"emprunts et dettes financieres courant(?:e)s",
        r"dettes financieres courantes",
    ],
    # Données par action : valeurs propres à la ligne. Elles ne doivent
    # jamais être multipliées par l'unité monétaire du tableau (milliers ou
    # millions de FCFA), contrairement aux agrégats ci-dessus.
    "benefice_par_action": [
        r"(?:résultat|bénéfice) net par actions?\b",
        r"(?:résultat|bénéfice) par action(?:\s+de base)?\b",
        r"(?:résultat|bénéfice)(?: net)? de base par actions?\b",
        r"(?:resultat|benefice) net par actions?\b",
        r"(?:resultat|benefice) par action(?:\s+de base)?\b",
        r"(?:resultat|benefice)(?: net)? de base par actions?\b",
    ],
    "nombre_actions_fin_exercice": [
        r"nombre d['’]actions en circulation",
        r"nombre d['’]actions composant le capital(?: social)?",
        r"nombre total d['’]actions",
        r"nombre d['’]actions\b",
    ],
    "nombre_actions_moyen_pondere": [
        r"nombre moyen pondéré d['’](?:actions|titres)(?: ordinaires)?(?: en circulation)?",
        r"nombre moyen d['’](?:actions|titres)(?: ordinaires)?(?: en circulation)?",
        r"nombre pondéré d['’](?:actions|titres)(?: ordinaires)?",
    ],
    "actions_autocontrole": [
        r"nombre d['’]actions d['’]autocontr[oô]le",
        r"actions d['’]autocontr[oô]le détenues",
        r"actions propres détenues",
    ],
}
FIGURE_DISPLAY_LABELS = {
    "chiffre_affaires": "Chiffre d'affaires",
    "produit_net_bancaire": "Produit net bancaire",
    "resultat_net": "Résultat net",
    "resultat_net_part_groupe": "Résultat net part du groupe",
    "resultat_net_attribuable_ordinaires": "Résultat attribuable aux actionnaires ordinaires (numérateur BPA)",
    "capitaux_propres": "Capitaux propres",
    "total_bilan": "Total du bilan",
    "flux_tresorerie_operationnel": "Flux de trésorerie opérationnel",
    "investissements_immobilisations": "Investissements en immobilisations (flux)",
    "dividendes_verses": "Dividendes versés (flux)",
    "tresorerie_equivalents": "Trésorerie et équivalents",
    "tresorerie_passif": "Trésorerie-passif",
    "tresorerie_nette": "Trésorerie nette",
    "dettes_financieres_non_courantes": "Dettes financières non courantes",
    "dettes_financieres_courantes": "Dettes financières courantes",
    "dettes_financieres": "Dettes financières (courant + non courant)",
    "benefice_par_action": "Bénéfice net par action publié",
    "nombre_actions_fin_exercice": "Nombre d'actions (fin d'exercice)",
    "nombre_actions_moyen_pondere": "Nombre moyen pondéré d'actions",
    "actions_autocontrole": "Actions d'autocontrôle détenues",
}
FIGURE_VALUE_KINDS = {
    "benefice_par_action": "fcfa_par_action",
    "nombre_actions_fin_exercice": "actions",
    "nombre_actions_moyen_pondere": "actions",
    "actions_autocontrole": "actions",
}
SIGNED_FIGURE_KEYS = {
    "resultat_net",
    "resultat_net_part_groupe",
    "resultat_net_attribuable_ordinaires",
    "capitaux_propres",
    "flux_tresorerie_operationnel",
    "tresorerie_nette",
    "benefice_par_action",
}
OUTFLOW_FIGURE_KEYS = {"investissements_immobilisations", "dividendes_verses"}
AMOUNT_PATTERN = re.compile(r"\(?-?\d{1,3}(?:[ \u202f\u00a0]\d{3})+(?:,\d+)?\)?|\(?-?\d+(?:,\d+)?\)?")
NOTE_REF_PATTERN = re.compile(r"^\d{1,2}\.\d{1,2}$")


def classify_report_document(url: str, link_text: str | None = None) -> dict[str, Any]:
    """Classe un document par nom/lien, sans confondre indice et contenu.

    Le nom de fichier et le texte du lien donnent la période, le périmètre
    et la version *présumés*. Ils ne dispensent jamais de la vérification
    d'identité, de période et d'exercice dans le PDF lui-même.
    """
    filename = urlparse(url).path.rsplit("/", 1)[-1]
    stem = re.sub(r"\.pdf$", "", filename, flags=re.I)
    pub_date = None
    date_match = re.match(r"(\d{4})(\d{2})(\d{2})[-_ ]", stem)
    remainder = stem
    if date_match:
        pub_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        remainder = stem[date_match.end():]
    readable_remainder = remainder.replace("_", " ").replace("-", " ")
    link_text_clean = clean_text(link_text or "")
    classification_text = clean_text(f"{readable_remainder} {link_text_clean}")
    selection = document_selection_metadata(classification_text)
    doc_type = infer_report_doc_type(classification_text)

    exercice = None
    exercice_source = None
    exercice_match = re.search(r"exercice[_\- ](\d{4})", classification_text, flags=re.I)
    if exercice_match:
        exercice = int(exercice_match.group(1))
        exercice_source = "EXPLICITE_DANS_LE_NOM_OU_LE_LIEN"
    else:
        years = [int(y) for y in re.findall(r"(20\d{2})", remainder)]
        if years:
            exercice = years[-1]
            exercice_source = "ANNEE_DANS_LE_NOM_DE_FICHIER_A_CONFIRMER_PAR_LE_CONTENU"
        elif link_text_clean:
            link_years = [int(y) for y in re.findall(r"(20\d{2})", link_text_clean)]
            if link_years:
                exercice = link_years[-1]
                exercice_source = "ANNEE_DANS_LE_TEXTE_DU_LIEN_A_CONFIRMER_PAR_LE_CONTENU"

    label = clean_text(readable_remainder)
    if not label and link_text_clean:
        label = link_text_clean
    return {
        "filename": filename,
        "label": label[:1].upper() + label[1:] if label else filename,
        "link_text": link_text_clean or None,
        "doc_type": doc_type,
        "exercice": exercice,
        "exercice_source": exercice_source,
        "published_date": pub_date,
        "url": url,
        **selection,
    }


def scrape_issuer_documents(
    session: requests.Session,
    report_pages: list[dict[str, str]],
    companies: list[dict[str, Any]],
    *,
    max_pages: int = 12,
    target_annual_exercices: int = 10,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    variants = build_issuer_variant_map(companies)
    for alias, ticker in REPORT_LABEL_ALIASES.items():
        variants.setdefault(canonical_issuer_key(alias), ticker)
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    warnings: list[str] = []
    for page in report_pages:
        label = page.get("label") or ""
        if normalize_key(label).startswith("fctc"):
            continue  # véhicules obligataires, pas l'action cotée
        tickers = match_announcement_issuer(label, variants)
        if not tickers:
            continue
        ticker = tickers[0]
        seen = {doc["url"] for doc in by_ticker[ticker]}
        # Paginer la page de l'émetteur jusqu'à couvrir dix exercices
        # annuels distincts lorsque l'index les publie (historique BPA
        # 2016–2025). L'arrêt à quatre pages mesuré au pilote laissait les
        # exercices anciens et les doublons utiles hors inventaire.
        for page_index in range(max(1, int(max_pages))):
            page_url = page["url"] if page_index == 0 else f"{page['url']}?page={page_index}"
            try:
                soup = BeautifulSoup(str(fetch(session, page_url)), "lxml")
            except Exception as exc:
                if page_index == 0:
                    warnings.append(f"Page de rapports illisible pour {ticker} ({exc}).")
                break
            new_docs = 0
            for anchor in soup.select("a[href]"):
                href = urljoin(page_url, anchor["href"])
                if ".pdf" not in href.lower() or href in seen:
                    continue
                seen.add(href)
                by_ticker[ticker].append(
                    classify_report_document(href, link_text=anchor.get_text(" ", strip=True))
                )
                new_docs += 1
            annual_exercices = {
                d["exercice"]
                for d in by_ticker[ticker]
                if d["doc_type"] in ANNUAL_DOC_PRIORITY and isinstance(d.get("exercice"), int)
            }
            if new_docs == 0 or len(annual_exercices) >= target_annual_exercices:
                break
    for ticker, docs in by_ticker.items():
        docs.sort(key=lambda d: (d["published_date"] is None, d["published_date"] or ""), reverse=True)
        dated = [d for d in docs if d["published_date"]]
        undated = [d for d in docs if not d["published_date"]]
        dated.sort(key=lambda d: d["published_date"], reverse=True)
        by_ticker[ticker] = (dated + undated)[:250]
    return dict(by_ticker), warnings


def detect_unit(page_text: str) -> tuple[int, str] | None:
    text = unicodedata.normalize("NFC", page_text)
    match = re.search(r"en\s+(milliers|millions|milliards)\s+(?:de\s+)?(?:f\s?cfa|francs?)\b", text, flags=re.I)
    if match:
        key = match.group(1).lower()
        return UNIT_MULTIPLIERS[key], f"en {key} de FCFA"
    match = re.search(r"en\s+(k|m)\s?fcfa\b", text, flags=re.I)
    if match:
        key = "milliers" if match.group(1).lower() == "k" else "millions"
        return UNIT_MULTIPLIERS[key], f"en {key} de FCFA"
    if re.search(r"\(en\s+(?:f\s?cfa|francs?)\)|montants?\s+en\s+(?:f\s?cfa|francs?)\b", text, flags=re.I):
        return 1, "en FCFA"
    return None


_AMOUNT_TOKEN_EDGE_CHARS = "[]{}<>|!;:"


def _amount_token_text(token: str) -> str:
    """Retire les artefacts de bordure collés à un mot par l'OCR.

    Les parenthèses sont conservées car elles peuvent signaler un montant
    négatif ; les séparateurs internes (virgules, points) ne sont jamais
    modifiés. Sans ce nettoyage, un total lu « 541451190619] » disparaît du
    regroupement et le montant suivant est attribué à la mauvaise colonne.
    """
    return str(token).strip().strip(_AMOUNT_TOKEN_EDGE_CHARS)


def parse_french_amount(token: str) -> float | None:
    text = _amount_token_text(token)
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace("\u202f", " ").replace("\u00a0", " ").replace(" ", "")
    # Quelques états utilisent la virgule comme séparateur de milliers sur
    # plusieurs groupes (8,098,245,354). Un seul groupe après la virgule
    # reste lu comme une décimale française (1,5), jamais comme 15.
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?", text):
        text = text.replace(",", "")
    text = text.replace(",", ".")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    value = float(text)
    return -value if negative else value


def first_amount_after(line: str, start: int) -> float | None:
    remainder = line[start:]
    # Référence de note annexe en tête (ex. « 4.10 ») : jamais un montant.
    remainder = re.sub(r"^\s*\d{1,2}\.\d{1,2}\s+", " ", remainder)
    for match in AMOUNT_PATTERN.finditer(remainder):
        token = match.group(0).strip()
        if not token:
            continue
        following = remainder[match.end():match.end() + 2].strip()
        if following.startswith("%"):
            continue
        if NOTE_REF_PATTERN.match(token):
            continue  # référence de note annexe (ex. 4.10), pas un montant
        value = parse_french_amount(token)
        if value is None:
            continue
        if float(value).is_integer() and 1990 <= value <= 2099 and token.strip("()") == str(int(value)):
            before = normalize_key(line[: start + match.start()])
            following_text = remainder[match.end():].lstrip()
            if "exercice" in before.split() and not re.match(r"\(?-?\d", following_text):
                continue  # année de la phrase (« de l'exercice 2025 »), pas un montant
        return value
    return None


def cluster_amounts(words: list[dict[str, Any]]) -> list[tuple[int, float]]:
    """Regroupe les mots numériques d'une ligne en montants.

    Dans les états financiers, les groupes de milliers d'un même montant sont
    quasi collés, alors qu'un changement de colonne laisse un écart franc.
    Retourne [(index du premier mot, valeur), ...].
    """
    clusters: list[tuple[int, float]] = []
    current: list[dict[str, Any]] = []

    def emit(cluster_words: list[dict[str, Any]]) -> None:
        if not cluster_words:
            return
        digit_count = sum(len(re.sub(r"\D", "", _amount_token_text(w["text"]))) for w in cluster_words)
        if digit_count > 15 and len(cluster_words) >= 4:
            # Deux colonnes de montants entiers ont été fusionnées en un
            # nombre impossible (> 15 chiffres, au-delà de tout agrégat
            # d'émetteur coté). On ne tente la séparation qu'au plus grand
            # écart horizontal, s'il tranche nettement avec les écarts
            # internes aux groupes de milliers — cas des bilans bancaires
            # en FCFA entiers dont les deux colonnes sont rapprochées.
            gaps = [
                cluster_words[i + 1]["x0"] - cluster_words[i]["x1"]
                for i in range(len(cluster_words) - 1)
            ]
            split = max(range(1, len(cluster_words)), key=lambda i: gaps[i - 1])
            others = sorted(gap for i, gap in enumerate(gaps) if i != split - 1)
            median_other = others[len(others) // 2] if others else 0.0
            left_digits = sum(
                len(re.sub(r"\D", "", _amount_token_text(w["text"]))) for w in cluster_words[:split]
            )
            if (
                gaps[split - 1] >= 4.0
                and gaps[split - 1] >= 1.8 * max(median_other, 0.1)
                and left_digits >= 3
                and digit_count - left_digits >= 3
            ):
                emit(cluster_words[:split])
                emit(cluster_words[split:])
                return
        joined = "".join(_amount_token_text(w["text"]) for w in cluster_words)
        value = parse_french_amount(joined)
        if value is not None:
            clusters.append((cluster_words[0]["index"], value))

    def flush() -> None:
        nonlocal current
        if current:
            emit(current)
        current = []

    for word in words:
        token = _amount_token_text(word["text"])
        if NOTE_REF_PATTERN.match(token):
            flush()
            continue
        if "%" in token:
            flush()
            continue
        # « 681606 » en un seul mot (millions sans séparateur) est un montant
        # au même titre que « 681 606 » : ne pas limiter le premier groupe à
        # trois chiffres, sinon des états entiers deviennent illisibles.
        starts_amount = re.fullmatch(r"\(?-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:,\d+)?\)?", token)
        continues_amount = re.fullmatch(r"\d{3}(?:,\d+)?\)?", token)
        # Certains PDF fragmentent un premier groupe de milliers (« 6 » puis
        # « 99 » pour 699) avec un écart quasi nul. On recolle uniquement à
        # écart <= 1 pt : une référence de note est séparée par une vraie
        # colonne, donc par un écart beaucoup plus large.
        fragment_continues = re.fullmatch(r"\d{1,3}(?:,\d+)?\)?", token)
        gap = word["x0"] - current[-1]["x1"] if current else None
        if current and ((continues_amount and gap <= 6) or (fragment_continues and gap <= 1)):
            current.append(word)
        elif starts_amount:
            flush()
            current = [word]
        else:
            flush()
    flush()
    return clusters


def structured_lines_from_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Les PDF scannés sont souvent légèrement inclinés : sur une même ligne
    # de tableau, le haut des montants à droite peut différer d'environ
    # 6 points du libellé à gauche. On élargit donc la tolérance verticale
    # uniquement pour les mots OCR (ils portent une confiance), sans changer
    # le regroupement strict du texte natif.
    has_ocr_words = any(isinstance(word.get("conf"), (int, float)) for word in words)
    line_tolerance = 7.0 if has_ocr_words else 3.0
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda w: (round(w["top"] / 3), w["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= line_tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])
    structured = []
    for line_words in lines:
        ordered = sorted(line_words, key=lambda w: w["x0"])
        indexed = [{**w, "index": i} for i, w in enumerate(ordered)]
        entry: dict[str, Any] = {
            "text": clean_text(" ".join(w["text"] for w in ordered)),
            "words": [w["text"] for w in ordered],
            "amounts": cluster_amounts(indexed),
        }
        confidences = [
            float(w["conf"])
            for w in ordered
            if isinstance(w.get("conf"), (int, float)) and float(w["conf"]) >= 0
        ]
        if confidences:
            entry["word_confidences"] = [
                float(w["conf"]) if isinstance(w.get("conf"), (int, float)) and float(w["conf"]) >= 0 else None
                for w in ordered
            ]
            entry["ocr_mean_confidence"] = round(sum(confidences) / len(confidences), 1)
            entry["ocr_min_confidence"] = round(min(confidences), 1)
        structured.append(entry)
    return structured


def _indexed_line_amounts(line: dict[str, Any]) -> list[tuple[int, float]]:
    """Montants d'une ligne, y compris les anciens caches OCR ponctués.

    Les caches OCR déjà écrits conservent à la fois les mots bruts et les
    montants regroupés. Si un crochet ou une bordure de tableau avait fait
    disparaître un long montant isolé du regroupement (« 541451190619] »),
    on le réinsère à son index de mot. On s'abstient en revanche lorsqu'un
    groupe de trois chiffres suit immédiatement : sans les coordonnées
    d'origine, le token pourrait n'être que le début d'un montant fragmenté.
    """
    indexed: list[tuple[int, float]] = []
    existing_indexes: set[int] = set()
    for item in line.get("amounts") or []:
        try:
            word_index, value = item
            normalized_index = int(word_index)
            normalized_value = float(value)
        except (TypeError, ValueError):
            continue
        indexed.append((normalized_index, normalized_value))
        existing_indexes.add(normalized_index)

    words = line.get("words") or []
    for word_index, raw_word in enumerate(words):
        if word_index in existing_indexes:
            continue
        raw_text = str(raw_word).strip()
        cleaned = _amount_token_text(raw_text)
        if not cleaned or cleaned == raw_text:
            continue
        if "%" in cleaned or NOTE_REF_PATTERN.match(cleaned):
            continue
        if len(re.sub(r"\D", "", cleaned)) < 5:
            continue
        if word_index + 1 < len(words):
            next_cleaned = _amount_token_text(str(words[word_index + 1]))
            if re.fullmatch(r"\d{3}(?:,\d+)?\)?", next_cleaned):
                continue
        if not re.fullmatch(r"\(?-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:,\d+)?\)?", cleaned):
            continue
        value = parse_french_amount(cleaned)
        if value is not None:
            indexed.append((word_index, value))
    return sorted(indexed)


def _low_confidence_amount_starts(line: dict[str, Any]) -> set[int]:
    """Indexes des montants OCR dont un mot numérique est trop fragile.

    Le contrôle est fait montant par montant : un premier montant rejeté
    devient ensuite un placeholder vide, au lieu de faire glisser le second
    montant dans la mauvaise colonne ou de supprimer toute la ligne.
    """
    words = line.get("words") or []
    confidences = line.get("word_confidences") or []
    if not words or not confidences:
        return set()
    indexed = _indexed_line_amounts(line)
    rejected: set[int] = set()
    for position, (start_index, _value) in enumerate(indexed):
        end_index = indexed[position + 1][0] if position + 1 < len(indexed) else len(words)
        numeric_confidences: list[float] = []
        for token, confidence in zip(words[start_index:end_index], confidences[start_index:end_index]):
            if confidence is None or not re.search(r"\d", str(token)):
                continue
            try:
                numeric_confidences.append(float(confidence))
            except (TypeError, ValueError):
                continue
        if numeric_confidences and min(numeric_confidences) < OCR_MIN_NUMERIC_CONFIDENCE:
            rejected.add(start_index)
    return rejected


def line_amount_after_label(line: dict[str, Any], match_end: int) -> float | None:
    # Position du libellé en nombre de mots (le texte nettoyé joint par espaces simples).
    prefix = line["text"][:match_end]
    label_word_count = len([w for w in prefix.split(" ") if w])
    for word_index, value in _indexed_line_amounts(line):
        if word_index >= label_word_count:
            return value
    return None


_MONTH_WORDS = {
    "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
    "aout", "septembre", "octobre", "novembre", "decembre",
}


def _is_calendar_date_amount(words: list[Any], word_index: int, value: float) -> bool:
    """Vrai si le nombre est le jour ou l'année d'une date en toutes lettres.

    Dans une phrase comme « le total du bilan de X au 31 décembre 2024 »,
    ni 31 ni 2024 ne sont des montants : sans ce filtre, l'année devient
    un faux total de bilan après multiplication par l'unité de page.
    Un vrai montant de 2 024 (millions) dans un tableau n'est pas précédé
    d'un mois en toutes lettres et n'est donc pas touché.
    """
    if not float(value).is_integer() or not (0 <= word_index < len(words)):
        return False
    token = _amount_token_text(str(words[word_index])).strip("()")
    if token != str(int(value)):
        return False
    normalized = [normalize_key(str(word)).strip() for word in words]
    if 1990 <= value <= 2099:
        previous = [
            piece
            for word in normalized[max(0, word_index - 3):word_index]
            for piece in word.split()
        ]
        if any(word in _MONTH_WORDS for word in previous):
            return True
        next_is_amount = False
        if word_index + 1 < len(words):
            next_token = _amount_token_text(str(words[word_index + 1]))
            next_is_amount = bool(
                re.fullmatch(r"\(?-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:,\d+)?\)?", next_token)
            )
        if next_is_amount:
            return False
        # Année nue en position narrative : « le résultat net de
        # l'exercice 2025 s'établit… », « 77 % du résultat net de
        # l'exercice 2025 et… », ou année accolée au libellé dans un
        # tableau de variation (« Résultat net 2023 - - - 1 358 »).
        # Sans ce filtre, l'année devient un faux résultat net après
        # multiplication par l'unité de page. Un vrai montant nu égal
        # à une année, dans un tableau, est suivi de la colonne N-1
        # (autre montant) et reste donc conservé ci-dessus.
        return "exercice" in previous or word_index <= 4
    if 1 <= value <= 31 and word_index + 2 < len(words):
        next_token = _amount_token_text(str(words[word_index + 2])).strip("()")
        return (
            normalized[word_index + 1] in _MONTH_WORDS
            and next_token.isdigit()
            and 1990 <= int(next_token) <= 2099
        )
    return False


def line_amounts_after_label(
    line: dict[str, Any],
    match_end: int,
    rejected_start_indexes: set[int] | None = None,
) -> list[float | None]:
    prefix = line["text"][:match_end]
    label_word_count = len([w for w in prefix.split(" ") if w])
    words = line.get("words") or []
    indexed = [
        (word_index, value)
        for word_index, value in _indexed_line_amounts(line)
        if word_index >= label_word_count
        and not _is_calendar_date_amount(words, word_index, value)
    ]
    if not indexed:
        return []

    # Colonne « Note » immédiatement après le libellé : un petit entier
    # (11, 12, 13…) suivi des deux colonnes N et N-1 n'est pas un montant.
    # On ne l'écarte que s'il reste au moins deux autres montants derrière.
    first_index, first_value = indexed[0]
    first_token = (
        _amount_token_text(str(words[first_index])).strip("()")
        if 0 <= first_index < len(words)
        else ""
    )
    if (
        len(indexed) >= 3
        and float(first_value).is_integer()
        and 1 <= first_value <= 99
        and first_token == str(int(first_value))
    ):
        indexed = indexed[1:]

    # Un tiret isolé vaut colonne vide/néant. Sans ce placeholder, le
    # montant N-1 serait attribué à tort à l'exercice courant.
    values: list[float | None] = []
    previous_index = label_word_count
    rejected_starts = rejected_start_indexes or set()
    for word_index, value in indexed:
        between = words[previous_index:word_index] if words else []
        if any(token.strip() in {"-", "–", "—"} for token in between):
            values.append(None)
        values.append(None if word_index in rejected_starts else value)
        previous_index = word_index + 1
    return values


def _candidate_value(entry: dict[str, Any]) -> float:
    value = entry.get("value", entry.get("value_fcfa"))
    return float(value)


def _aggregate_candidates(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not entries:
        return None
    entries.sort(key=_candidate_value)
    clusters: list[list[dict[str, Any]]] = []
    for entry in entries:
        placed = False
        entry_signature = entry.get("candidate_signature")
        for cluster in clusters:
            cluster_signatures = {
                item.get("candidate_signature") for item in cluster if item.get("candidate_signature") is not None
            }
            # Deux lectures de même montant mais de périmètre, devise ou
            # composante différents ne se confirment pas mutuellement.
            if entry_signature is not None and cluster_signatures and entry_signature not in cluster_signatures:
                continue
            reference = _candidate_value(cluster[0])
            if reference == 0 or abs(_candidate_value(entry) - reference) <= abs(reference) * 0.011:
                cluster.append(entry)
                placed = True
                break
        if not placed:
            clusters.append([entry])
    # En cas de valeurs divergentes, le cluster porté par le libellé le plus
    # spécifique (ex. « total du passif » plutôt que « total de l'actif ») prime.
    best_rank = min(e["pattern_rank"] for e in entries)
    best = max(
        clusters,
        key=lambda c: (
            max((int(e.get("selection_priority") or 0) for e in c), default=0),
            any(e.get("eligible") is True for e in c),
            any(e["pattern_rank"] == best_rank for e in c),
            # Un tableau financier présente normalement N et N-1. À rang de
            # libellé égal, préférer ces lignes à une phrase narrative qui
            # peut exprimer le même agrégat dans une autre échelle
            # (« 101,352 milliards » sur une page en millions).
            max((e.get("amount_count") or 0) for e in c),
            len(c),
            len({e["page"] for e in c}),
        ),
    )
    representative = min(best, key=lambda e: e.get("multiplier", 1))  # unité la plus fine = plus précis
    value = _candidate_value(representative)
    value_kind = representative.get("value_kind") or "fcfa"
    methods = {e.get("extraction_method") or "texte_natif" for e in best}
    extraction_method = (
        "ocr_controle" if methods == {"ocr_controle"}
        else "texte_natif_et_ocr" if "ocr_controle" in methods
        else "texte_natif"
    )
    ocr_confidences = [
        float(e["ocr_confidence"])
        for e in best
        if isinstance(e.get("ocr_confidence"), (int, float))
    ]
    aggregated: dict[str, Any] = {
        "value": int(value) if value_kind != "fcfa_par_action" and float(value).is_integer() else round(value, 4),
        "value_kind": value_kind,
        "unit_label": representative["unit_label"],
        "source_amount_count": max((e.get("amount_count") or 0) for e in best),
        "extraction_method": extraction_method,
        "ocr_confidence": round(min(ocr_confidences), 1) if ocr_confidences else None,
        "occurrences": len(best),
        "evidence": [
            {
                "page": e["page"],
                "line": e["line"],
                "raw_token": e.get("raw_token"),
                "context_lines": e.get("context_lines") or [],
                "column_header": e.get("column_header"),
                "unit_label": e["unit_label"],
                "extraction_method": e.get("extraction_method") or "texte_natif",
                "ocr_confidence": e.get("ocr_confidence"),
                "parser_version": e.get("parser_version"),
                "parser_rule": e.get("parser_rule"),
            }
            for e in best[:3]
        ],
    }
    for field in (
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
        "eps_metadata",
        "share_metadata",
    ):
        if representative.get(field) is not None:
            aggregated[field] = representative[field]
    aggregated["source_multiplier"] = representative.get("multiplier", 1)
    if value_kind == "fcfa":
        try:
            aggregated["input_rounding_abs_fcfa"] = abs(float(aggregated["source_multiplier"])) * 0.5
        except (TypeError, ValueError):
            aggregated["input_rounding_abs_fcfa"] = None

    def _group_summary(cluster: list[dict[str, Any]]) -> dict[str, Any]:
        group_representative = min(cluster, key=lambda e: e.get("multiplier", 1))
        group_value = _candidate_value(group_representative)
        return {
            "value": int(group_value) if value_kind != "fcfa_par_action" and float(group_value).is_integer() else round(group_value, 4),
            "value_kind": group_representative.get("value_kind") or value_kind,
            "occurrences": len(cluster),
            "pages": sorted({int(e["page"]) for e in cluster if isinstance(e.get("page"), int)}),
            "candidate_signature": group_representative.get("candidate_signature"),
            "accounting_scope": group_representative.get("accounting_scope"),
            "framework": group_representative.get("framework"),
            "currency": group_representative.get("currency"),
            "component": group_representative.get("component"),
            "basis": group_representative.get("basis"),
            "eligible": any(e.get("eligible") is True for e in cluster),
            "selected": cluster is best,
        }

    aggregated["candidate_groups"] = [_group_summary(cluster) for cluster in clusters[:8]]
    if value_kind == "fcfa":
        aggregated["value_fcfa"] = int(round(value))
        aggregated["value"] = aggregated["value_fcfa"]
    return aggregated


def apply_plausibility_filters(figures: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Contrôles de cohérence comptable sur un exercice. Écarte plutôt qu'affiche."""
    figures = {k: v for k, v in figures.items() if not k.startswith("_")}
    rejected: list[str] = []

    def figure_value(key: str) -> int | None:
        value = figures.get(key, {}).get("value_fcfa")
        return value if isinstance(value, int) else None

    def drop(key: str, reason: str) -> None:
        if key in figures:
            rejected.append(f"{FIGURE_DISPLAY_LABELS[key]} écarté par contrôle de plausibilité ({reason}).")
            figures.pop(key, None)

    def weaker_of(a: str, b: str) -> str:
        rank = {"confirme_deux_documents": 2, "recoupe_dans_le_document": 1, "extraction_unique": 0}
        conf_a = figures.get(a, {}).get("confidence")
        conf_b = figures.get(b, {}).get("confidence")
        occ_a = figures.get(a, {}).get("occurrences", 0)
        occ_b = figures.get(b, {}).get("occurrences", 0)
        return a if (rank.get(conf_a, 0), occ_a) <= (rank.get(conf_b, 0), occ_b) else b

    # Planchers d'ordre de grandeur : en dessous, l'échelle d'unité lue est suspecte.
    # Les capitaux propres peuvent être négatifs (pertes accumulées) : on
    # contrôle alors leur ordre de grandeur absolu, sans les effacer.
    for key, floor in {"total_bilan": 2_000_000_000, "chiffre_affaires": 500_000_000,
                       "produit_net_bancaire": 500_000_000, "capitaux_propres": 500_000_000}.items():
        value = figure_value(key)
        too_small = value is not None and ((abs(value) < floor) if key == "capitaux_propres" else (value < floor))
        if value is not None and too_small:
            drop(key, "ordre de grandeur incompatible avec un émetteur coté")

    total = figure_value("total_bilan")
    cp = figure_value("capitaux_propres")
    if total and cp is not None:
        cp_ratio = cp / total
        plausible_cp_ratio = (-1.5 <= cp_ratio <= 0.98) if cp < 0 else (0.02 <= cp_ratio <= 0.98)
        if not plausible_cp_ratio:
            drop(weaker_of("capitaux_propres", "total_bilan"), "capitaux propres hors plage plausible du total du bilan")
            total, cp = figure_value("total_bilan"), figure_value("capitaux_propres")

    ca = figure_value("chiffre_affaires")
    if total and ca is not None and not (0.02 <= ca / total <= 25):
        drop(weaker_of("chiffre_affaires", "total_bilan"), "chiffre d'affaires sans rapport plausible avec le total du bilan")
        total, ca = figure_value("total_bilan"), figure_value("chiffre_affaires")

    pnb = figure_value("produit_net_bancaire")
    if total and pnb is not None and not (0.005 <= pnb / total <= 0.35):
        drop(weaker_of("produit_net_bancaire", "total_bilan"), "produit net bancaire sans rapport plausible avec le total du bilan")
        pnb = figure_value("produit_net_bancaire")

    rn = figure_value("resultat_net")
    if rn is not None and ca and abs(rn) > ca * 1.2:
        drop("resultat_net", "résultat net supérieur au chiffre d'affaires")
        rn = None
    if rn is not None and pnb and abs(rn) > pnb * 0.9:
        drop("resultat_net", "résultat net supérieur à 90 % du produit net bancaire")
        rn = None
    cp = figure_value("capitaux_propres")
    if rn is not None and cp is not None and cp > 0 and abs(rn) > cp * 1.5:
        drop("resultat_net", "résultat net supérieur à 150 % des capitaux propres positifs")
        rn = None
    if rn is not None and cp is not None and cp > 0 and figures.get("resultat_net", {}).get("confidence") == "extraction_unique" \
            and 0 < abs(rn) < cp * 0.01:
        drop("resultat_net", "résultat net inférieur à 1 % des capitaux propres en extraction unique (échelle suspecte)")
        rn = None
    ca = figure_value("chiffre_affaires")
    cp = figure_value("capitaux_propres")
    if ca and cp is not None and cp >= 0 and cp < ca * 0.01:
        drop(weaker_of("capitaux_propres", "chiffre_affaires"), "capitaux propres positifs inférieurs à 1 % du chiffre d'affaires")

    part = figure_value("resultat_net_part_groupe")
    if part is not None and rn is not None and rn > 0 and part > rn * 1.05:
        drop("resultat_net_part_groupe", "part du groupe supérieure au résultat net total")

    def numeric_value(key: str) -> float | None:
        figure = figures.get(key, {})
        value = figure.get("value", figure.get("value_fcfa"))
        return float(value) if isinstance(value, (int, float)) else None

    total = figure_value("total_bilan")
    activity = figure_value("chiffre_affaires") or figure_value("produit_net_bancaire")
    scale_reference = max([value for value in (total, activity) if value], default=None)

    # Stocks de bilan : aucun poste isolé ne Peut dépasser le total du bilan.
    for key in (
        "tresorerie_equivalents",
        "tresorerie_passif",
        "dettes_financieres_non_courantes",
        "dettes_financieres_courantes",
    ):
        value = numeric_value(key)
        if value is not None and value < 0:
            drop(key, "stock de bilan négatif sur un poste attendu positif")
            value = None
        if value is not None and total and value > total * 1.05:
            drop(weaker_of(key, "total_bilan"), "poste de bilan supérieur au total du bilan")
            total = figure_value("total_bilan")
    net_cash = numeric_value("tresorerie_nette")
    if net_cash is not None and total and abs(net_cash) > total * 1.05:
        drop(weaker_of("tresorerie_nette", "total_bilan"), "trésorerie nette supérieure au total du bilan")
        total = figure_value("total_bilan")

    # Flux annuels : ils peuvent être négatifs et, pour une banque, dépasser
    # le produit net bancaire ; on n'écarte que les ruptures d'échelle franches
    # par rapport à la taille du bilan ou de l'activité.
    for key in ("flux_tresorerie_operationnel", "investissements_immobilisations", "dividendes_verses"):
        value = numeric_value(key)
        if value is None:
            continue
        if key in OUTFLOW_FIGURE_KEYS and value > 0:
            drop(key, "flux présenté en positif alors que le libellé retenu est un décaissement")
            continue
        if scale_reference and abs(value) > scale_reference * 2.5:
            drop(key, "flux annuel sans rapport plausible avec la taille du bilan ou de l'activité")

    eps = numeric_value("benefice_par_action")
    if eps is not None and abs(eps) > 1_000_000:
        drop("benefice_par_action", "montant par action hors plage plausible")
        eps = None
    for key in ("nombre_actions_fin_exercice", "nombre_actions_moyen_pondere", "actions_autocontrole"):
        value = numeric_value(key)
        minimum = 0 if key == "actions_autocontrole" else 10_000
        if value is not None and not (minimum <= value <= 200_000_000_000):
            drop(key, "nombre d'actions hors plage plausible pour un émetteur coté")
    shares_end = numeric_value("nombre_actions_fin_exercice")
    shares_avg = numeric_value("nombre_actions_moyen_pondere")
    if shares_end and shares_avg:
        ratio = max(shares_end, shares_avg) / min(shares_end, shares_avg)
        if ratio > 5:
            drop(
                weaker_of("nombre_actions_fin_exercice", "nombre_actions_moyen_pondere"),
                "nombres d'actions de fin d'exercice et moyen pondéré incompatibles",
            )
            shares_end = numeric_value("nombre_actions_fin_exercice")
            shares_avg = numeric_value("nombre_actions_moyen_pondere")
    if eps is not None:
        # Cohérence BPA : seuls un numérateur attribuable/part du groupe et
        # un dénominateur moyen pondéré peuvent contrôler un BPA publié.
        # Le résultat total divisé par les actions de fin d'exercice reste
        # un ratio indicatif et ne doit ni valider ni effacer la publication.
        numerator_key = (
            "resultat_net_attribuable_ordinaires"
            if figure_value("resultat_net_attribuable_ordinaires") is not None
            else "resultat_net_part_groupe"
        )
        result_for_eps = figure_value(numerator_key)
        if result_for_eps is not None and shares_avg:
            eps_figure = figures.get("benefice_par_action") or {}
            numerator_figure = figures.get(numerator_key) or {}
            check = assess_eps_arithmetic(
                eps,
                float(result_for_eps),
                float(shares_avg),
                published_decimals=eps_figure.get("published_decimals"),
                numerator_rounding_abs=numerator_figure.get("input_rounding_abs_fcfa"),
                reference=(
                    "RECALCULE_COMPARABLE"
                    if numerator_key == "resultat_net_attribuable_ordinaires"
                    else "PART_GROUPE_PONDEREE"
                ),
            )
            if check:
                eps_figure["arithmetic_check"] = check
                eps_figure["coherence_status"] = check["status"]
                if not check["concordant"]:
                    reasons = list(eps_figure.get("quarantine_reasons") or [])
                    reasons.append("BPA_PUBLIE_INCOHERENT_AVEC_NUMERATEUR_ET_DENOMINATEUR_PONDERES")
                    eps_figure["quarantine_reasons"] = sorted(set(reasons))
                    rejected.append(
                        "Bénéfice net par action publié conservé comme preuve mais placé en quarantaine : "
                        f"écart de {check['relative_gap_pct']} % avec le contrôle {check['reference']}."
                    )

    return figures, rejected


SYSCOHADA_SYNTHESIS_MARKERS = [
    "xb chiffre d affaires",
    "xi resultat net",
    "cp total capitaux propres",
    "dz total general",
    "bz total general",
    "total ressources stables",
    "total actif immobilise",
    "total passif circulant",
    # Tableau des flux SYSCOHADA (système normal) : codes ZA à ZH et
    # terminologie propre (« variation du BF », capitaux étrangers). Ces
    # pages sont également en FCFA entiers lorsque l'unité n'est pas répétée.
    "zb flux de tresorerie provenant des activites operationnelles",
    "zc flux de tresorerie provenant des activites",
    "zf flux de tresorerie provenant des activites de financement",
    "zh tresorerie nette au 31 decembre",
    "flux de tresorerie systeme normal",
    "variation du bf lie aux activites operationnelles",
    "tresorerie nette au 1er janvier",
]


def looks_like_syscohada_synthesis(page: dict[str, Any]) -> bool:
    """États de synthèse SYSCOHADA codés, montants entiers en FCFA.

    Ces tableaux normalisés (codes XB, XI, CP, DZ…) n'affichent souvent pas
    « en milliers/millions » sur la page : les montants y sont en FCFA. On
    n'autorise l'unité implicite que si plusieurs codes caractéristiques sont
    présents, et les contrôles de plausibilité restent appliqués ensuite.
    """
    text = normalize_key((page.get("text") or "") + " " + " ".join(line.get("text") or "" for line in page.get("lines", [])))
    return sum(marker in text for marker in SYSCOHADA_SYNTHESIS_MARKERS) >= 2


# L'OCR corrompt parfois l'article (« destiné à ja publication »,
# « destiné à a publication ») : ces variantes restent sans ambiguïté.
BANK_PUBLICATION_PHRASES = (
    "destine a publication",
    "destine a la publication",
    "destine a ja publication",
    "destine a a publication",
)


BANK_PUBLICATION_FORM_MARKERS = (
    "date d arrete",
    "montants nets",
    "montant nets",
    "etablissement",
    "banque centrale ccp",
    "banques centrales",
    "capitaux propres et ressources",
    "engagements donnes",
    "produits charges",
)


def _page_max_amount(page: dict[str, Any]) -> float:
    amounts = [
        abs(float(value))
        for line in page.get("lines", [])
        for _index, value in _indexed_line_amounts(line)
    ]
    return max(amounts, default=0.0)


def _page_has_bank_publication_header(page: dict[str, Any]) -> bool:
    text = normalize_key(
        (page.get("text") or "") + " " + " ".join(line.get("text") or "" for line in page.get("lines", []))
    )
    return (
        any(marker in text for marker in BANK_PUBLICATION_PHRASES)
        and "date d arrete" in text
    )


def _page_has_bank_form_layout(page: dict[str, Any]) -> bool:
    """Mise en page du formulaire bancaire UMOA, indépendamment de l'unité.

    Le formulaire normalisé — qu'il soit imprimé en FCFA entiers ou, dans
    certains rapports de commissaires aux comptes, en millions — présente
    ses deux colonnes dans l'ordre 31/12/N-1 puis 31/12/N. L'OCR perd
    parfois la ligne d'en-tête grisée portant ces dates ; ce test ne sert
    alors qu'à choisir l'ordre normalisé du formulaire, jamais une unité.
    """
    text = normalize_key(
        (page.get("text") or "") + " " + " ".join(line.get("text") or "" for line in page.get("lines", []))
    )
    return (
        any(marker in text for marker in BANK_PUBLICATION_PHRASES)
        and "etablissement" in text
        and any(marker in text for marker in ("bilan", "compte de resultat", "hors bilan"))
    )


def looks_like_bank_publication_form(page: dict[str, Any]) -> bool:
    """Formulaire bancaire UMOA « destiné à publication » en FCFA entiers.

    Certains états bancaires réglementaires n'impriment pas l'unité en
    clair : l'en-tête codé (« destiné à publication », État/Établissement,
    date d'arrêté, montants nets) identifie le formulaire, et les montants
    y sont imprimés en FCFA entiers. On n'autorise cette unité que si le
    formulaire est reconnaissable et si la page porte effectivement des
    montants entiers d'au moins un milliard ; une présentation en millions
    du même document ne franchit donc pas ce test.
    """
    text = normalize_key(
        (page.get("text") or "") + " " + " ".join(line.get("text") or "" for line in page.get("lines", []))
    )
    if not any(marker in text for marker in BANK_PUBLICATION_PHRASES):
        return False
    if sum(marker in text for marker in BANK_PUBLICATION_FORM_MARKERS) < 3:
        return False
    return _page_max_amount(page) >= 1_000_000_000


def _detect_page_column_order(page: dict[str, Any]) -> bool | None:
    """Retourne True si les colonnes sont N-1 puis N, False si N puis N-1.

    `None` signifie qu'aucun en-tête explicite ne prouve l'ordre sur cette
    page. Cette distinction compte en OCR : une date mal reconnue sur une
    page (« 34/12/2026 ») ne doit pas être confondue avec une preuve que
    les colonnes seraient descendantes.
    """
    lines = [line.get("text") or "" for line in page.get("lines", [])]
    if not lines and page.get("text"):
        lines = str(page["text"]).split("\n")
    # En-têtes de colonnes datés, formes rencontrées : « 31/12/2025 »,
    # « 31-déc-23 » / « 31-déc-2023 » (états IFRS, ex. Servair Abidjan),
    # « 31 décembre 2025 ». Les années à deux chiffres sont ramenées au
    # XXIe siècle : sans cette lecture locale, le consensus d'ordre du
    # document — parfois prouvé par seules des annexes — pouvait
    # inverser les colonnes des états primaires.
    date_pattern = (
        r"3[0-9](?:\s*/\s*12\s*/\s*|\s*[- ]\s*d[ée]c(?:embre)?\.?\s*[- ]\s*|\s+d[ée]cembre\s+)"
        r"(20\d{2}|\d{2})(?!\d)"
    )

    def header_years(text: str) -> list[int]:
        years = []
        for year in re.findall(date_pattern, text, flags=re.I):
            value = int(year)
            years.append(value if value >= 100 else 2000 + value)
        return years

    for text in lines[:20]:
        date_years = header_years(text)
        if len(date_years) >= 2 and abs(date_years[1] - date_years[0]) == 1:
            return date_years[1] == date_years[0] + 1
    combined_dates: list[int] = []
    for text in lines[:12]:
        combined_dates.extend(header_years(text))
        if len(combined_dates) >= 2:
            break
    if len(combined_dates) >= 2 and abs(combined_dates[1] - combined_dates[0]) == 1:
        return combined_dates[1] == combined_dates[0] + 1
    # En-têtes « mois année » des rapports d'activité (« Déc 2024
    # Déc 2025 », Ecobank CI) et paires d'années nues des synthèses
    # (« 2024 2025 », Solibra) : ces présentations sont ascendantes
    # (N-1 puis N), à l'inverse des états IFRS/SYSCOHADA. Sans preuve
    # locale, l'ordre descendant par défaut attribuait les montants
    # N-1 à l'exercice courant et faisait disparaître l'exercice
    # précédent au recoupement. Garde-fous : les deux années doivent
    # être quasi adjacentes (au plus deux mots entre elles) sur une
    # ligne courte d'en-tête (au plus dix mots alphabétiques), pour
    # ne pas prendre une phrase de commentaire pour un en-tête.
    month_names = (
        r"(?:janv?(?:ier)?|f[ée]vr?(?:ier)?|mars|avr(?:il)?|mai|juin|"
        r"juil(?:let)?|ao[ûu]t|sept?(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?)\.?"
    )
    for text in lines[:20]:
        # Une paire séparée par « / » (« Variation Déc 2025 / Déc
        # 2024 ») exprime un ratio d'évolution, pas l'ordre des
        # colonnes : elle précède souvent le vrai en-tête et
        # l'inverserait si elle était prise pour une preuve.
        month_matches = list(re.finditer(month_names + r"\s*(20\d{2})\b", text, flags=re.I))
        if len(month_matches) >= 2:
            month_years = [int(match.group(1)) for match in month_matches]
            gap = text[month_matches[0].end():month_matches[1].start()]
            if "/" not in gap and abs(month_years[1] - month_years[0]) == 1:
                return month_years[1] == month_years[0] + 1
        tokens = text.split()
        year_positions = [
            (index, int(token_cleaned))
            for index, token in enumerate(tokens)
            if re.fullmatch(r"20\d{2}", token_cleaned := _amount_token_text(token).strip("()"))
        ]
        if len(year_positions) >= 2:
            (first_index, first_year), (second_index, second_year) = year_positions[:2]
            alpha_words = sum(1 for token in tokens if re.search(r"[A-Za-zÀ-ÿ]{2,}", token))
            if (
                abs(second_year - first_year) == 1
                and second_index - first_index <= 3
                and not any("/" in token for token in tokens[first_index + 1:second_index])
                and alpha_words <= 10
            ):
                return second_year == first_year + 1
    for text in lines[:12]:
        normalized = normalize_key(text)
        if not any(marker in normalized for marker in ("exercice", "actif", "passif", "produits charges")):
            continue
        years = [int(year) for year in re.findall(r"\b(20\d{2})\b", text)]
        if len(years) >= 2 and abs(years[1] - years[0]) == 1:
            return years[1] == years[0] + 1
    return None


def page_columns_are_ascending(page: dict[str, Any]) -> bool:
    """Vrai uniquement si l'en-tête de la page prouve l'ordre N-1 puis N."""
    return _detect_page_column_order(page) is True


def _document_column_order(pages: list[dict[str, Any]]) -> bool | None:
    """Consensus d'ordre des colonnes à l'échelle du document.

    Utilisé seulement pour les pages sans preuve locale, et seulement si
    toutes les pages prouvées du document donnent le même ordre. En cas
    de pages contradictoires, aucun consensus n'est appliqué.
    """
    proven = [order for page in pages if (order := _detect_page_column_order(page)) is not None]
    if proven and all(order is proven[0] for order in proven):
        return proven[0]
    return None


def detect_unit_from_legal_capital(pages: list[dict[str, Any]]) -> tuple[int, str] | None:
    """Recoupe l'unité d'un tableau bancaire sans unité imprimée.

    Certains états bancaires UMOA n'indiquent pas « en millions » dans le
    tableau, mais le pied de page publie le capital légal en FCFA entiers
    (« au Capital de 36 000 000 000 F CFA ») pendant que le bilan affiche
    « Capital souscrit 36 000 ». Si le rapport exact vaut 1 000, 1 000 000
    ou 1 000 000 000 (à 1,5 % près), l'unité est prouvée par le document
    lui-même ; elle n'est jamais devinée depuis la seule taille des nombres.
    """
    legal_values: set[int] = set()
    table_values: set[int] = set()
    for page in pages:
        for line in page.get("lines", []):
            text = line.get("text") or ""
            legal_match = re.search(
                r"capital de\s+([0-9][0-9\s\u202f\u00a0]{8,})\s*(?:f\s?cfa|francs?\s*cfa)\b",
                text,
                flags=re.I,
            )
            if legal_match:
                legal_value = parse_french_amount(legal_match.group(1).strip())
                if legal_value and legal_value >= 1_000_000_000:
                    legal_values.add(int(legal_value))
            capital_match = re.search(r"capital souscrit\b", text, flags=re.I)
            if capital_match:
                for amount in line_amounts_after_label(
                    line,
                    capital_match.end(),
                    rejected_start_indexes=_low_confidence_amount_starts(line),
                )[:2]:
                    if amount and amount > 0:
                        table_values.add(int(amount))
    multiplier_names = {value: key for key, value in UNIT_MULTIPLIERS.items()}
    for legal_value in sorted(legal_values):
        for table_value in sorted(table_values):
            if table_value <= 0:
                continue
            ratio = legal_value / table_value
            for multiplier in (1_000, 1_000_000, 1_000_000_000):
                if abs(ratio - multiplier) <= multiplier * 0.015:
                    return (
                        multiplier,
                        f"en {multiplier_names[multiplier]} de FCFA (unité recoupée par le capital légal du document)",
                    )
    return None


# Marqueurs d'un bilan bancaire UMOA par postes (présentation de synthèse
# du groupe BOA notamment), indépendants de l'en-tête du formulaire.
_BANK_POSTE_MARKERS = (
    "dettes interbancaires",
    "creances sur la clientele",
    "creances interbancaires",
    "engagements de garantie",
    "produit net bancaire",
    "banques centrales",
    "effets publics",
    "dettes a l egard de la clientele",
)


def detect_unit_from_subscribed_capital(pages: list[dict[str, Any]]) -> tuple[int, str] | None:
    """Recoupe l'unité d'une synthèse bancaire par son capital souscrit.

    Les synthèses « Bilan Actif - Passif » publiées par certaines banques
    (BOA Côte d'Ivoire) n'impriment ni « en millions » ni le capital légal
    en pied de page. Le bilan lui-même fournit pourtant une ancre : le
    capital souscrit d'une banque de l'UMOA est borné par la réglementation
    (capital minimum de 10 milliards de FCFA, très en deçà de 500 milliards
    pour les établissements cotés à la BRVM). Parmi les multiplicateurs
    1 / 1 000 / 1 000 000 / 1 000 000 000, un seul peut donc placer à la fois
    le capital souscrit, les capitaux propres et le plus grand montant du
    bilan dans leurs bandes réglementaires et plausibles. Si ce
    multiplicateur n'est pas unique, on s'abstient : l'unité n'est jamais
    devinée depuis la seule taille des nombres.
    """
    capital_values: list[float] = []
    equity_values: list[float] = []
    max_amount = 0.0
    for page in pages:
        text = normalize_key(
            (page.get("text") or "") + " " + " ".join(line.get("text") or "" for line in page.get("lines", []))
        )
        if "capital souscrit" not in text or "capitaux propres" not in text:
            continue
        if sum(marker in text for marker in _BANK_POSTE_MARKERS) < 2:
            continue
        for line in page.get("lines", []):
            line_text = line.get("text") or ""
            capital_match = re.search(r"capital souscrit\b", line_text, flags=re.I)
            if capital_match:
                for amount in line_amounts_after_label(
                    line,
                    capital_match.end(),
                    rejected_start_indexes=_low_confidence_amount_starts(line),
                )[:2]:
                    if amount and amount > 0:
                        capital_values.append(float(amount))
                continue
            equity_match = re.search(r"capitaux propres\b", line_text, flags=re.I)
            if equity_match and "hors resultat" not in normalize_key(line_text):
                for amount in line_amounts_after_label(
                    line,
                    equity_match.end(),
                    rejected_start_indexes=_low_confidence_amount_starts(line),
                )[:2]:
                    if amount and amount > 0:
                        equity_values.append(float(amount))
        max_amount = max(max_amount, _page_max_amount(page))
    if not capital_values or not equity_values or max_amount <= 0:
        return None
    plausible: list[int] = []
    for multiplier in (1, 1_000, 1_000_000, 1_000_000_000):
        if not all(10_000_000_000 <= value * multiplier <= 500_000_000_000 for value in capital_values):
            continue
        if not all(5_000_000_000 <= value * multiplier <= 5_000_000_000_000 for value in equity_values):
            continue
        if not (50_000_000_000 <= max_amount * multiplier <= 30_000_000_000_000):
            continue
        plausible.append(multiplier)
    if len(plausible) != 1:
        return None
    multiplier = plausible[0]
    multiplier_names = {value: key for key, value in UNIT_MULTIPLIERS.items()}
    if multiplier == 1:
        return (1, "FCFA (unité recoupée par le capital souscrit du bilan bancaire)")
    return (
        multiplier,
        f"en {multiplier_names[multiplier]} de FCFA (unité recoupée par le capital souscrit du bilan bancaire)",
    )


def _reselect_total_bilan_with_equity(
    figures: dict[str, Any], total_candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Recoupe Actif/passif avec les capitaux propres du même exercice.

    Un bilan publie normalement le même total à l'Actif et au passif. Si les
    deux lectures divergent (par exemple un chiffre inséré par OCR dans le
    total du passif), le rang du libellé ne suffit pas à trancher : on ne
    remplace le total initial que si une seule autre valeur candidate rend
    le poids des capitaux propres plausible. Sinon, les contrôles suivants
    écarteront le poste le plus fragile plutôt que d'inventer un choix.
    """
    total = figures.get("total_bilan", {}).get("value_fcfa")
    equity = figures.get("capitaux_propres", {}).get("value_fcfa")
    if not isinstance(total, int) or not isinstance(equity, int) or total <= 0:
        return figures

    def equity_ratio_is_plausible(total_value: int) -> bool:
        if total_value <= 0:
            return False
        ratio = equity / total_value
        return (-1.5 <= ratio <= 0.98) if equity < 0 else (0.02 <= ratio <= 0.98)

    if equity_ratio_is_plausible(total):
        return figures

    clusters: list[list[dict[str, Any]]] = []
    for entry in sorted(total_candidates, key=_candidate_value):
        placed = False
        for cluster in clusters:
            reference = _candidate_value(cluster[0])
            if reference == 0 or abs(_candidate_value(entry) - reference) <= abs(reference) * 0.011:
                cluster.append(entry)
                placed = True
                break
        if not placed:
            clusters.append([entry])

    alternatives: list[dict[str, Any]] = []
    for cluster in clusters:
        aggregated = _aggregate_candidates(list(cluster))
        if not aggregated:
            continue
        value = aggregated.get("value_fcfa")
        if not isinstance(value, int):
            continue
        if abs(value - total) <= abs(total) * 0.011:
            continue
        if equity_ratio_is_plausible(value):
            alternatives.append(aggregated)
    if len(alternatives) != 1:
        return figures
    alternative = alternatives[0]
    figures["total_bilan"] = {
        "label": FIGURE_DISPLAY_LABELS["total_bilan"],
        **alternative,
        "confidence": "recoupe_dans_le_document" if alternative["occurrences"] >= 2 else "extraction_unique",
    }
    return figures


def extract_figures_from_pages(
    pages: list[dict[str, Any]],
    document_exercice: int | None = None,
) -> dict[str, Any]:
    """Extrait les colonnes par décalage d'exercice, preuves à l'appui.

    Les clés historiques ``courant`` (décalage 0) et ``precedent``
    (décalage 1) restent retournées pour compatibilité. ``colonnes``
    expose en outre le décalage 2 et au-delà lorsque l'en-tête prouve un
    tableau à trois exercices. Les observations BPA/actions détaillées
    sont retournées séparément et ne sont jamais écrasées par l'agrégat
    historique à champ unique.
    """
    candidates: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    page_contexts, content_classification = classify_page_accounting_contexts(pages)
    document_unit = detect_unit_from_legal_capital(pages) or detect_unit_from_subscribed_capital(pages)
    document_ascending_columns = _document_column_order(pages)
    # Formulaire bancaire UMOA : l'en-tête complet n'est pas toujours relu
    # sur chaque page (sigles codés, bordures, OCR partiel). Si au moins
    # deux pages prouvent le formulaire, une autre page du même document
    # Peut hériter de l'unité seulement si elle répète l'en-tête codé et
    # porte elle-même des montants d'au moins un milliard ; les pages de
    # synthèse en millions du même document restent donc exclues.
    document_is_bank_publication_form = (
        sum(1 for page in pages if looks_like_bank_publication_form(page)) >= 2
    )
    for page_index, page in enumerate(pages, start=1):
        page_number = page.get("page_number") if isinstance(page.get("page_number"), int) else page_index
        unit = detect_unit(page.get("text") or "")
        if unit is None and looks_like_syscohada_synthesis(page):
            unit = (1, "FCFA (états de synthèse SYSCOHADA codés)")
        if unit is None:
            unit = document_unit
        if unit is None and looks_like_bank_publication_form(page):
            unit = (1, "FCFA (état bancaire destiné à publication, montants entiers)")
        if (
            unit is None
            and document_is_bank_publication_form
            and _page_has_bank_publication_header(page)
            and _page_max_amount(page) >= 1_000_000_000
        ):
            unit = (1, "FCFA (état bancaire destiné à publication, montants entiers)")
        page_column_order = _detect_page_column_order(page)
        ascending_columns = (
            page_column_order
            if page_column_order is not None
            else bool(document_ascending_columns)
        )
        if page_column_order is None and _page_has_bank_form_layout(page):
            # En-tête de dates illisible : le formulaire bancaire UMOA
            # normalisé présente N-1 puis N (vérifié sur les états BOA
            # Bénin/Burkina/Niger). Ce repli propre au formulaire prime sur
            # le consensus du document, qu'une annexe en colonnes
            # descendantes (« TOTAL AU 31/12/N TOTAL AU 31/12/N-1 ») Peut
            # sinon imposer à tort au bilan réglementaire. Il ne s'applique
            # qu'aux pages du formulaire lui-même, pas aux états IFRS d'un
            # rapport annuel, et jamais contre un en-tête de page explicite.
            ascending_columns = True
        is_ocr_page = page.get("extraction_method") == "ocr_controle"
        normalized_page_text = normalize_key(
            (page.get("text") or "") + " " + " ".join(line.get("text") or "" for line in page.get("lines", []))
        )
        # L'unité monétaire de page reste obligatoire pour les agrégats en
        # FCFA. En revanche, un BPA ou un nombre d'actions porte son unité
        # dans son libellé et Peut être lu même si la page ne répète pas
        # « en millions de FCFA » — sans jamais appliquer ce multiplicateur.
        page_lines = page.get("lines", [])
        page_context = page_contexts[page_index - 1] if page_index - 1 < len(page_contexts) else {}
        page_line_texts = [line.get("text") or "" for line in page_lines]
        page_column_years = detect_eps_column_years(page_line_texts)
        variation_header_index = next(
            (
                index
                for index, candidate in enumerate(page_lines)
                if "variation des capitaux propres" in normalize_key(candidate.get("text") or "")
            ),
            None,
        )
        for line_index, line in enumerate(page_lines):
            text = line.get("text") or ""
            if len(text) < 8:
                continue
            if is_ocr_page:
                line_confidence = line.get("ocr_mean_confidence")
                if isinstance(line_confidence, (int, float)) and line_confidence < OCR_MIN_LINE_MEAN_CONFIDENCE:
                    continue
            rejected_amount_starts = _low_confidence_amount_starts(line) if is_ocr_page else set()
            lowered = text.lower()
            normalized_line = normalize_key(text)
            for key, patterns in FIGURE_LABELS.items():
                value_kind = FIGURE_VALUE_KINDS.get(key, "fcfa")
                if value_kind == "fcfa" and unit is None:
                    continue
                if "par action" in lowered and key != "benefice_par_action":
                    continue
                if key == "capitaux_propres" and (
                    "passif et des capitaux propres" in lowered
                    or "attribuable" in lowered
                    # « Capitaux propres hors résultat » exclut par
                    # définition le résultat de l'exercice : ce n'est pas
                    # le total des capitaux propres du bilan.
                    or "hors resultat" in normalized_line
                    # « Flux de trésorerie provenant des capitaux propres »
                    # est un flux de financement SYSCOHADA, pas le stock de
                    # capitaux propres du bilan. L'OCR Peut tronquer le mot
                    # initial (« ux de trésorerie… »), d'où les variantes.
                    or "flux de tresorerie" in normalized_line
                    or "tresorerie provenant" in normalized_line
                    or "financement par les capitaux propres" in normalized_line
                    # Dans un tableau de variation des capitaux propres, les
                    # colonnes sont les composantes (capital, primes,
                    # réserves, résultat) et non N/N-1 : le premier montant
                    # lu n'est pas le total. L'exclusion ne vise que les
                    # lignes du tableau de variation lui-même, à partir de
                    # son en-tête sur la page : un bilan imprimé au-dessus
                    # sur la même page (CIE CI, document combiné où le
                    # tableau de variation suit le bilan) conserve son
                    # total des capitaux propres.
                    or (
                        variation_header_index is not None
                        and line_index >= variation_header_index
                    )
                ):
                    continue
                if key == "resultat_net" and (
                    "attribuable" in lowered
                    or "actionnaires ordinaires" in normalized_line
                    or "porteurs d actions ordinaires" in normalized_line
                    or "utilise pour le calcul du resultat par action" in normalized_line
                ):
                    continue
                if key == "resultat_net" and (
                    "fonds propres effectifs" in normalized_page_text
                    and "determines comme suit" in normalized_page_text
                ):
                    # Calcul prudentiel des fonds propres effectifs : le
                    # « résultat de l'exercice » y est la fraction éligible
                    # ou conservée après affectation, pas nécessairement le
                    # résultat net du compte de résultat (BOA Niger 2020 :
                    # 1 415 millions prudentiels contre 7 421 millions au
                    # bilan). Seuls les états primaires font foi.
                    continue
                if key == "total_bilan" and "total general" not in normalized_line and any(
                    partial in normalized_line for partial in ("actif immobilise", "actif circulant", "tresorerie actif")
                ):
                    continue
                if key == "dividendes_verses" and any(
                    marker in normalized_line
                    for marker in ("minoritaires", "ne donnant pas le controle")
                ):
                    continue
                if key == "tresorerie_equivalents" and any(
                    marker in normalized_line
                    for marker in (
                        "ouverture",
                        "variation",
                        "tresorerie actif n 1",
                        # Formule de contrôle Actif − passif : le montant
                        # est la trésorerie nette, pas les équivalents.
                        "controle tresorerie actif",
                        "tresorerie actif n tresorerie passif",
                    )
                ):
                    continue
                if key == "tresorerie_passif" and any(
                    marker in normalized_line
                    for marker in (
                        "tresorerie passif n 1",
                        "tresorerie passif n-1",
                        "controle tresorerie actif",
                        "tresorerie actif n tresorerie passif",
                    )
                ):
                    # Formules « trésorerie Actif N(-1) - trésorerie passif
                    # N(-1) » : le montant qui suit est la trésorerie nette,
                    # pas le passif. La ligne de bilan côte à côte, elle,
                    # porte ses montants entre les deux libellés.
                    continue
                if key == "tresorerie_nette" and any(
                    marker in normalized_line for marker in ("ouverture", "variation", "1er janvier")
                ):
                    continue
                if key == "benefice_par_action" and (
                    ("dilu" in normalized_line and "de base et dilu" not in normalized_line)
                    # Ligne du numérateur dans une note BPA (« résultat net
                    # utilisé pour le calcul du résultat par action ») : le
                    # montant est le bénéfice total, pas le BPA.
                    or "utilise pour le calcul" in normalized_line
                    # Présentations en double devise (cents US + FCFA) : les
                    # colonnes ne sont pas désambiguïsées par la lecture par
                    # mots. Mieux vaut aucun BPA qu'un BPA dans la mauvaise
                    # devise ou tronqué à sa partie entière.
                    or any(marker in normalized_line for marker in ("cents", "usd", "dollar"))
                ):
                    continue
                if key == "nombre_actions_fin_exercice" and any(
                    marker in normalized_line for marker in ("moyen", "pondere", "autocontrole", "actions propres")
                ):
                    continue
                if key == "nombre_actions_moyen_pondere" and (
                    "autocontrole" in normalized_line
                    or (
                        "dilu" in normalized_line
                        and "de base" not in normalized_line
                        and "basic" not in normalized_line
                    )
                ):
                    continue
                for pattern_rank, pattern in enumerate(patterns):
                    match = re.search(pattern, text, flags=re.I)
                    if not match:
                        continue
                    amounts = line_amounts_after_label(
                        line,
                        match.end(),
                        rejected_start_indexes=rejected_amount_starts,
                    )
                    used_text_fallback = False
                    if not amounts:
                        fallback = first_amount_after(text, match.end())
                        amounts = [fallback] if fallback is not None else []
                        used_text_fallback = fallback is not None
                    evidence_line = text
                    if key == "benefice_par_action" and not any(v is not None for v in amounts):
                        # Présentation IFRS fréquente (mesurée sur les états
                        # SNTS 2025, p. 20) : le libellé « Résultat net par
                        # actions ... » est seul sur sa ligne, les montants
                        # sont sur la sous-ligne suivante « - de base 3 420
                        # 3 288 » (suivie de « - dilué », jamais lue). On ne
                        # suit que la sous-ligne « de base » parmi les deux
                        # lignes suivantes de la même page, mêmes contrôles
                        # OCR que la ligne principale, preuve jointe des
                        # deux lignes sources.
                        for next_index in (line_index + 1, line_index + 2):
                            if next_index >= len(page_lines):
                                break
                            next_line = page_lines[next_index]
                            next_text = next_line.get("text") or ""
                            next_normalized = normalize_key(next_text)
                            if not next_normalized.startswith("de base") or "dilu" in next_normalized:
                                continue
                            if any(marker in next_normalized for marker in ("cents", "usd", "dollar")):
                                continue
                            if is_ocr_page:
                                next_confidence = next_line.get("ocr_mean_confidence")
                                if isinstance(next_confidence, (int, float)) and next_confidence < OCR_MIN_LINE_MEAN_CONFIDENCE:
                                    continue
                            next_match = re.search(r"de\s+base", next_text, flags=re.I)
                            if not next_match:
                                continue
                            next_amounts = line_amounts_after_label(
                                next_line,
                                next_match.end(),
                                rejected_start_indexes=_low_confidence_amount_starts(next_line) if is_ocr_page else set(),
                            )
                            if not next_amounts:
                                fallback_next = first_amount_after(next_text, next_match.end())
                                next_amounts = [fallback_next] if fallback_next is not None else []
                            if any(v is not None for v in next_amounts):
                                amounts = next_amounts
                                evidence_line = f"{text} | {next_text}"
                                break
                    # Actif SYSCOHADA : BZ présente brut, amortissements,
                    # net N puis net N-1. Le total de bilan est la colonne
                    # nette ; le passif DZ ne présente que N et N-1.
                    if key == "total_bilan" and re.search(r"\bBZ\s+total général", text, flags=re.I) \
                            and not re.search(r"\bDZ\s+total général", text, flags=re.I) and len(amounts) >= 4 \
                            and all(value is not None for value in amounts[:4]):
                        amounts = amounts[2:4]
                    # Même présentation possible pour une ligne d'actif
                    # isolée. Si la ligne fusionne Actif et passif côte à
                    # côte, les deux premiers montants restent ceux de
                    # l'actif : ne pas appliquer le décalage dans ce cas.
                    if key == "tresorerie_equivalents" and "tresorerie actif" in normalized_line \
                            and len(amounts) >= 4 and all(value is not None for value in amounts[:4]) \
                            and not any(marker in normalized_line for marker in ("tresorerie passif", "autres dettes")) \
                            and amounts[1] == 0:
                        amounts = amounts[2:4]

                    # Les montants structurés ont déjà été filtrés montant
                    # par montant ci-dessus. Le repli texte, lui, ne connaît
                    # pas les bornes de chaque montant : on garde donc un
                    # contrôle global de la fin de ligne dans ce seul cas.
                    if used_text_fallback and is_ocr_page and line.get("word_confidences"):
                        prefix = text[:match.end()]
                        label_word_count = len([w for w in prefix.split(" ") if w])
                        numeric_confidences = [
                            confidence
                            for token, confidence in zip(
                                (line.get("words") or [])[label_word_count:],
                                line["word_confidences"][label_word_count:],
                            )
                            if confidence is not None and re.search(r"\d", token)
                        ]
                        if numeric_confidences and min(numeric_confidences) < OCR_MIN_NUMERIC_CONFIDENCE:
                            amounts = []

                    if value_kind == "fcfa":
                        effective_multiplier, effective_unit_label = unit or (1, "FCFA")
                    elif value_kind == "fcfa_par_action":
                        effective_multiplier = 1
                        effective_unit_label = "FCFA par action (ligne du document)"
                    else:
                        effective_multiplier = 1
                        effective_unit_label = "actions (ligne du document)"

                    header_years = list((page_column_years or {}).get("years") or [])
                    max_columns = len(header_years) if len(header_years) >= 3 else 2
                    considered_amounts = amounts[:max_columns]
                    for column, raw_value in enumerate(considered_amounts):
                        if raw_value is None:
                            continue
                        value = raw_value * effective_multiplier
                        if value_kind == "fcfa":
                            if abs(value) < 1_000_000 or abs(value) > 30_000_000_000_000:
                                continue
                            if key in OUTFLOW_FIGURE_KEYS and value >= 0:
                                continue
                            if key not in SIGNED_FIGURE_KEYS and key not in OUTFLOW_FIGURE_KEYS and value <= 0:
                                continue
                            stored_value: int | float = int(round(value))
                        elif value_kind == "fcfa_par_action":
                            if abs(value) < 0.01 or abs(value) > 1_000_000:
                                continue
                            stored_value = round(float(value), 4)
                        else:  # actions
                            minimum_actions = 0 if key == "actions_autocontrole" else 10_000
                            if value < minimum_actions or not float(value).is_integer() or not (value <= 200_000_000_000):
                                continue
                            stored_value = int(value)
                        if header_years and column < len(header_years):
                            # L'année vient de l'en-tête de la page, jamais
                            # du seul rang du montant dans la ligne.
                            effective_column = max(header_years) - int(header_years[column])
                        elif len(considered_amounts) == 1:
                            # Une ligne à un seul montant lu (phrase du
                            # rapport, tableau à une colonne, seconde
                            # colonne masquée par un tampon) ne prouve pas
                            # sa position physique : dans un document
                            # annuel, ce montant isolé est celui de
                            # l'exercice courant. L'inversion N-1/N ne
                            # s'applique qu'aux lignes à plusieurs colonnes.
                            effective_column = 0
                        elif ascending_columns:
                            effective_column = len(considered_amounts) - 1 - column
                        else:
                            effective_column = column
                        scope_value = page_context.get("accounting_scope") or "NON_PROUVE"
                        framework_value = page_context.get("framework") or "NON_PROUVE"
                        candidate_signature = (
                            scope_value
                            if scope_value not in {"NON_PROUVE", "MIXTE"}
                            else None
                        )
                        selection_priority = (
                            30 if scope_value == "CONSOLIDE"
                            else 10 if scope_value in {"INDIVIDUEL", "SOCIAL"}
                            else 20
                        )
                        candidates[(key, effective_column)].append(
                            {
                                "value": stored_value,
                                "value_kind": value_kind,
                                "raw_value": raw_value,
                                "raw_token": str(raw_value),
                                "unit_label": effective_unit_label,
                                "multiplier": effective_multiplier,
                                "page": page_number,
                                "line": evidence_line[:1000],
                                "context_lines": page_line_texts[max(0, line_index - 2):line_index + 3],
                                "column_header": page_column_years,
                                "pattern_rank": pattern_rank,
                                "amount_count": len([value for value in amounts if value is not None]),
                                "extraction_method": "ocr_controle" if is_ocr_page else "texte_natif",
                                "ocr_confidence": line.get("ocr_mean_confidence") if is_ocr_page else None,
                                "accounting_scope": scope_value,
                                "accounting_scope_source": page_context.get("accounting_scope_source"),
                                "framework": framework_value,
                                "candidate_signature": candidate_signature,
                                "selection_priority": selection_priority,
                                "eligible": True,
                            }
                        )
                    break

    # Moteur d'observations BPA/actions : il remplace les candidats
    # historiques à champ unique dès qu'une ligne par action a été
    # identifiée, y compris si toutes les observations sont en devise,
    # en composante ou en périmètre non retenu. C'est ce remplacement qui
    # empêche l'ancien repli de promouvoir « 1,0 » (décimale tronquée,
    # mauvaise devise) en BPA FCFA.
    per_share_observations: dict[str, Any] = {
        "parser_version": EPS_PARSER_VERSION,
        "eps": [],
        "shares": [],
        "numerators": [],
        "ignored": [],
    }
    per_share_error: str | None = None
    try:
        per_share_observations = extract_per_share_observations(
            pages,
            document_exercice=document_exercice,
            page_contexts=page_contexts,
        )
    except Exception as exc:  # le moteur historique reste disponible, tracé
        per_share_error = f"Moteur d'observations BPA indisponible sur ce document : {exc}"

    def _scope_priority(scope: Any) -> int:
        return 30 if scope == "CONSOLIDE" else 10 if scope in {"INDIVIDUEL", "SOCIAL"} else 20

    if per_share_observations.get("eps"):
        for candidate_key in list(candidates):
            if candidate_key[0] == "benefice_par_action":
                candidates[candidate_key] = []
        for observation in per_share_observations["eps"]:
            offset = observation.get("year_offset_from_document")
            if not observation.get("eligible_fcfa_total_basic") or not isinstance(offset, int) or not (0 <= offset <= 4):
                continue
            evidence = observation.get("evidence") or {}
            scope_value = observation.get("accounting_scope") or "NON_PROUVE"
            signature = "|".join(
                str(observation.get(field) or "NON_PROUVE")
                for field in ("accounting_scope", "framework", "currency", "component", "basis")
            )
            candidates[("benefice_par_action", offset)].append(
                {
                    "value": float(observation["value"]),
                    "value_kind": "fcfa_par_action",
                    "raw_value": observation.get("value"),
                    "raw_token": observation.get("raw_token"),
                    "token_repair": observation.get("token_repair"),
                    "unit_label": observation.get("unit_label") or "FCFA par action",
                    "multiplier": 1,
                    "page": int(evidence.get("page") or 1),
                    "line": evidence.get("line_original") or "",
                    "context_lines": evidence.get("context_lines") or [],
                    "column_header": evidence.get("column_header"),
                    "pattern_rank": 0,
                    "amount_count": 1,
                    "extraction_method": evidence.get("extraction_method") or "texte_natif",
                    "ocr_confidence": evidence.get("ocr_confidence"),
                    "accounting_scope": scope_value,
                    "accounting_scope_source": observation.get("accounting_scope_source"),
                    "framework": observation.get("framework"),
                    "currency": observation.get("currency"),
                    "currency_source": observation.get("currency_source"),
                    "component": observation.get("component"),
                    "component_source": observation.get("component_source"),
                    "basis": observation.get("basis"),
                    "published_decimals": observation.get("published_decimals"),
                    "candidate_signature": signature,
                    "selection_priority": _scope_priority(scope_value),
                    "eligible": True,
                    "parser_version": evidence.get("parser_version"),
                    "parser_rule": evidence.get("parser_rule"),
                    "eps_metadata": {
                        key: value for key, value in observation.items() if key != "evidence"
                    },
                }
            )

    share_key_by_kind = {
        "MOYEN_PONDERE": "nombre_actions_moyen_pondere",
        "FIN_EXERCICE_OU_EN_CIRCULATION": "nombre_actions_fin_exercice",
        "AUTOCONTROLE": "actions_autocontrole",
    }
    dedicated_share_keys = {
        share_key_by_kind[observation["denominator_kind"]]
        for observation in per_share_observations.get("shares") or []
        if observation.get("denominator_kind") in share_key_by_kind
    }
    for share_key in dedicated_share_keys:
        for candidate_key in list(candidates):
            if candidate_key[0] == share_key:
                candidates[candidate_key] = []
    for observation in per_share_observations.get("shares") or []:
        share_key = share_key_by_kind.get(str(observation.get("denominator_kind") or ""))
        offset = observation.get("year_offset_from_document")
        if not share_key or not isinstance(offset, int) or not (0 <= offset <= 4):
            continue
        if observation.get("value") is None:
            continue
        if share_key != "actions_autocontrole" and not observation.get("eligible_as_denominator"):
            continue
        evidence = observation.get("evidence") or {}
        scope_value = observation.get("accounting_scope") or "NON_PROUVE"
        signature = "|".join(
            str(observation.get(field) or "NON_PROUVE")
            for field in ("denominator_kind", "accounting_scope", "framework")
        )
        candidates[(share_key, offset)].append(
            {
                "value": observation["value"],
                "value_kind": "actions",
                "raw_value": observation.get("raw_value"),
                "raw_token": observation.get("raw_token"),
                "unit_label": observation.get("unit_label") or "actions",
                "multiplier": 1,
                "page": int(evidence.get("page") or 1),
                "line": evidence.get("line_original") or "",
                "context_lines": evidence.get("context_lines") or [],
                "column_header": evidence.get("column_header"),
                "pattern_rank": 0,
                "amount_count": 1,
                "extraction_method": evidence.get("extraction_method") or "texte_natif",
                "ocr_confidence": evidence.get("ocr_confidence"),
                "accounting_scope": scope_value,
                "accounting_scope_source": observation.get("accounting_scope_source"),
                "framework": observation.get("framework"),
                "denominator_kind": observation.get("denominator_kind"),
                "candidate_signature": signature,
                "selection_priority": _scope_priority(scope_value),
                "eligible": True,
                "parser_version": evidence.get("parser_version"),
                "parser_rule": evidence.get("parser_rule"),
                "share_metadata": {
                    key: value for key, value in observation.items() if key != "evidence"
                },
            }
        )

    result: dict[str, Any] = {}
    rejected_all: list[str] = []
    if per_share_error:
        rejected_all.append(per_share_error)
    offsets = sorted({0, 1} | {column for _key, column in candidates if isinstance(column, int) and 0 <= column <= 4})
    columns_by_offset: dict[str, dict[str, Any]] = {}
    for column in offsets:
        label = "courant" if column == 0 else "precedent" if column == 1 else f"colonne_moins_{column}"
        figures: dict[str, Any] = {}
        for key in FIGURE_LABELS:
            aggregated = _aggregate_candidates(candidates.get((key, column), []))
            if aggregated:
                figures[key] = {
                    "label": FIGURE_DISPLAY_LABELS[key],
                    **aggregated,
                    "confidence": "recoupe_dans_le_document" if aggregated["occurrences"] >= 2 else "extraction_unique",
                }
        figures = _reselect_total_bilan_with_equity(
            figures, candidates.get(("total_bilan", column), [])
        )
        figures, rejected = apply_plausibility_filters(figures)
        rejected_all.extend(rejected if column == 0 else [])
        result[label] = figures
        columns_by_offset[str(column)] = figures
    result["colonnes"] = columns_by_offset
    result["_per_share_observations"] = per_share_observations
    result["_content_classification"] = content_classification
    result["_page_contexts"] = page_contexts
    if rejected_all:
        result["_rejected"] = rejected_all
    return result


OCR_UNAVAILABLE_NOTE = (
    "OCR de repli non disponible dans cet environnement : les PDF scannés sans couche "
    "de texte exploitable restent non extraits."
)


def _run_ocr_command(command: list[str], timeout: int) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{command[0]} : {exc}"
    if result.returncode != 0:
        detail = clean_text(result.stderr or result.stdout or "")[:240]
        return result, f"{command[0]} a échoué{(' : ' + detail) if detail else ''}"
    return result, None


def _clean_ocr_word(text: str) -> str:
    # Tesseract rend parfois le « é » sous forme de ligature « æ ».
    cleaned = (
        text.replace("\u00e6", "\u00e9")
        .replace("\u00c6", "\u00c9")
        .strip()
    )
    # Les bordures de tableau sont souvent collées au mot (« |INTERETS »,
    # « PASSIF] », « 541451190619] »). Les retirer à la source évite de
    # perdre un libellé ou un montant entier lors du regroupement.
    return _amount_token_text(cleaned)


def _parse_tesseract_tsv(tsv_path: Path) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    scale = 72.0 / OCR_DPI  # pixels 300 dpi -> points, échelle des pages natives
    try:
        with tsv_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
            for row in reader:
                text = _clean_ocr_word(row.get("text") or "")
                if not text:
                    continue
                try:
                    confidence = float(row.get("conf") or -1)
                    left = float(row.get("left") or 0) * scale
                    top = float(row.get("top") or 0) * scale
                    width = float(row.get("width") or 0) * scale
                    height = float(row.get("height") or 0) * scale
                except (TypeError, ValueError):
                    continue
                if confidence < 0 or width <= 0 or height <= 0:
                    continue
                # Artefact de segmentation : Tesseract attribue parfois
                # toute la largeur d'une ligne de tableau à un seul libellé
                # (« PASSIF » avec une boîte de plus de 400 points). Lors de
                # la fusion des passes, une telle boîte recouvre aussi les
                # montants et Peut les remplacer à tort. Les mots numériques
                # ne sont pas filtrés par cette règle géométrique.
                if width > 150 and width / height > 15 and not any(char.isdigit() for char in text):
                    continue
                words.append(
                    {
                        "text": text,
                        "x0": left,
                        "x1": left + width,
                        "top": top,
                        "bottom": top + height,
                        "conf": confidence,
                    }
                )
    except OSError:
        return []
    return words


def _ocr_numeric_token_digits(text: str) -> str | None:
    cleaned = _amount_token_text(str(text))
    if "%" in cleaned or NOTE_REF_PATTERN.match(cleaned):
        return None
    if not re.fullmatch(r"\(?-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:,\d+)?\)?", cleaned):
        return None
    return re.sub(r"\D", "", cleaned)


def _merge_ocr_word_variants(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fusionne la passe normale et la passe inversée d'une même page.

    Les lignes blanches sur fond coloré (totaux bancaires) peuvent être
    absentes de la passe normale mais présentes après inversion. Un mot
    secondaire qui recouvre un mot primaire ne le remplace que si sa
    confiance est nettement meilleure ; un mot sans équivalent est ajouté
    seulement s'il atteint un seuil minimal, puis les filtres de ligne et
    de montant restent appliqués.

    Exception importante : si les deux passes lisent deux suites de chiffres
    différentes de même longueur au même endroit, la confiance Tesseract ne
    suffit pas à trancher (cas réel BOAM : 541491… en passe normale contre
    541451… après inversion). Le mot primaire est conservé avec une
    confiance ramenée à zéro, ce qui fera rejeter ce montant sans décaler
    les autres colonnes.
    """
    merged = [dict(word) for word in primary]
    matched: set[int] = set()

    def overlap_ratio(a: dict[str, Any], b: dict[str, Any]) -> float:
        x_overlap = max(0.0, min(float(a["x1"]), float(b["x1"])) - max(float(a["x0"]), float(b["x0"])))
        y_overlap = max(0.0, min(float(a["bottom"]), float(b["bottom"])) - max(float(a["top"]), float(b["top"])))
        min_area = min(
            max(1.0, (float(a["x1"]) - float(a["x0"])) * (float(a["bottom"]) - float(a["top"]))),
            max(1.0, (float(b["x1"]) - float(b["x0"])) * (float(b["bottom"]) - float(b["top"]))),
        )
        return (x_overlap * y_overlap) / min_area

    primary_count = len(primary)
    for candidate in secondary:
        best_index: int | None = None
        best_overlap = 0.0
        for index, existing in enumerate(merged[:primary_count]):
            if index in matched:
                continue
            ratio = overlap_ratio(existing, candidate)
            if ratio > best_overlap:
                best_overlap = ratio
                best_index = index
        if best_index is not None and best_overlap >= 0.25:
            matched.add(best_index)
            existing = merged[best_index]
            existing_digits = _ocr_numeric_token_digits(str(existing.get("text") or ""))
            candidate_digits = _ocr_numeric_token_digits(str(candidate.get("text") or ""))
            if (
                existing_digits
                and candidate_digits
                and len(existing_digits) == len(candidate_digits) >= 3
                and existing_digits != candidate_digits
            ):
                conflicted = dict(existing)
                conflicted["conf"] = 0.0
                conflicted["ocr_variant_conflict"] = True
                merged[best_index] = conflicted
                continue
            if float(candidate.get("conf") or 0) >= float(existing.get("conf") or 0) + 5:
                merged[best_index] = dict(candidate)
            continue
        if float(candidate.get("conf") or 0) >= 45:
            merged.append(dict(candidate))
    return merged


def ocr_pdf_pages(pdf_bytes: bytes, cache_dir: Path | None = None) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Reconnaissance de caractères de repli, uniquement après échec natif.

    Le résultat est mis en cache par empreinte du PDF : relancer une collecte
    ne refait pas l'OCR. Chaque page garde les confidences mot à mot afin que
    l'extracteur commun puisse écarter les lignes et montants fragiles.
    """
    tools = {
        "pdftoppm": shutil.which("pdftoppm"),
        "tesseract": shutil.which("tesseract"),
        "imagemagick": shutil.which("magick") or shutil.which("convert"),
    }
    metadata: dict[str, Any] = {
        "available": all(tools.values()),
        "cache_status": "sans_cache",
        "pages_ocrees": 0,
        "mean_confidence": None,
        "truncated": False,
    }
    if not metadata["available"]:
        return [], [OCR_UNAVAILABLE_NOTE], metadata

    digest = hashlib.sha256(pdf_bytes).hexdigest()
    cache_path = None
    if cache_dir is not None:
        cache_path = cache_dir / "ocr" / f"ocr-{digest[:24]}-v{OCR_CACHE_VERSION}.json"
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                pages = cached.get("pages")
                if isinstance(pages, list):
                    cached_metadata = cached.get("metadata") if isinstance(cached.get("metadata"), dict) else {}
                    metadata.update(cached_metadata)
                    metadata["available"] = True
                    metadata["cache_status"] = "hit"
                    return pages, list(cached.get("notes") or []), metadata
            except (OSError, json.JSONDecodeError):
                pass

    notes: list[str] = []
    pages: list[dict[str, Any]] = []
    all_confidences: list[float] = []
    with tempfile.TemporaryDirectory(prefix="sigma-ocr-") as tmp:
        workdir = Path(tmp)
        pdf_path = workdir / "document.pdf"
        pdf_path.write_bytes(pdf_bytes)
        render_prefix = workdir / "page"
        total_pages: int | None = None
        pdfinfo_path = shutil.which("pdfinfo")
        if pdfinfo_path:
            info_result, info_error = _run_ocr_command([pdfinfo_path, str(pdf_path)], timeout=30)
            if not info_error and info_result is not None:
                pages_match = re.search(r"^Pages:\s+(\d+)\s*$", info_result.stdout or "", flags=re.M)
                if pages_match:
                    total_pages = int(pages_match.group(1))
        if total_pages is None:
            try:
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    total_pages = len(pdf.pages)
            except Exception:
                total_pages = None
        if total_pages is not None and total_pages > OCR_MAX_PAGES:
            metadata["truncated"] = True
            notes.append(
                f"OCR de repli limité aux {OCR_MAX_PAGES} premières pages du document scanné ; "
                "les pages suivantes n’ont pas été reconnues."
            )
        _, error = _run_ocr_command(
            [
                str(tools["pdftoppm"]),
                "-png",
                "-r",
                str(OCR_DPI),
                "-l",
                str(OCR_MAX_PAGES),
                str(pdf_path),
                str(render_prefix),
            ],
            timeout=300,
        )
        if error:
            return [], [f"OCR de repli interrompu avant reconnaissance : {error}"], metadata
        images = sorted(workdir.glob("page-*.png"))
        if not images:
            return [], ["OCR de repli : le PDF scanné n’a produit aucune page image lisible."], metadata
        def process_page(indexed_image: tuple[int, Path]) -> tuple[dict[str, Any], list[float]]:
            image_index, image_path = indexed_image
            suffix = image_path.stem.rsplit("-", 1)[-1]
            page_number = int(suffix) if suffix.isdigit() else image_index
            inverted_path = workdir / f"{image_path.stem}-inverse.png"
            _, invert_error = _run_ocr_command(
                [str(tools["imagemagick"]), str(image_path), "-colorspace", "Gray", "-negate", str(inverted_path)],
                timeout=90,
            )
            word_variants: list[list[dict[str, Any]]] = []
            variant_paths = [image_path]
            if not invert_error and inverted_path.exists():
                variant_paths.append(inverted_path)
            for variant_path in variant_paths:
                output_base = workdir / f"{variant_path.stem}-ocr"
                _, ocr_error = _run_ocr_command(
                    [str(tools["tesseract"]), str(variant_path), str(output_base), "-l", "fra", "--psm", "6", "tsv"],
                    timeout=180,
                )
                if ocr_error:
                    continue
                tsv_path = output_base.with_suffix(".tsv")
                if tsv_path.exists():
                    word_variants.append(_parse_tesseract_tsv(tsv_path))
            if not word_variants:
                return (
                    {
                        "text": "",
                        "lines": [],
                        "page_number": page_number,
                        "extraction_method": "ocr_controle",
                        "ocr_mean_confidence": None,
                    },
                    [],
                )
            words = word_variants[0]
            if len(word_variants) > 1:
                words = _merge_ocr_word_variants(words, word_variants[1])
            lines = structured_lines_from_words(words)
            page_confidences = [float(word["conf"]) for word in words if isinstance(word.get("conf"), (int, float))]
            return (
                {
                    "text": "\n".join(line["text"] for line in lines),
                    "lines": lines,
                    "page_number": page_number,
                    "extraction_method": "ocr_controle",
                    "ocr_mean_confidence": round(sum(page_confidences) / len(page_confidences), 1) if page_confidences else None,
                },
                page_confidences,
            )

        selected_images = list(enumerate(images[:OCR_MAX_PAGES], start=1))
        # Tesseract utilise environ un cœur par page dans cette configuration ;
        # traiter les pages en parallèle conserve exactement les mêmes
        # passes et le même ordre de sortie, tout en rendant une collecte
        # complète tenable. Les fichiers temporaires sont propres à chaque page.
        worker_count = max(1, min(4, os.cpu_count() or 1, len(selected_images)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            page_results = list(executor.map(process_page, selected_images))
        pages = [page for page, _confidences in page_results]
        all_confidences = [confidence for _page, confidences in page_results for confidence in confidences]
    metadata["pages_ocrees"] = len(pages)
    metadata["mean_confidence"] = round(sum(all_confidences) / len(all_confidences), 1) if all_confidences else None
    if cache_path is not None and pages:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "version": OCR_CACHE_VERSION,
                        "sha256": digest,
                        "metadata": metadata,
                        "notes": notes,
                        "pages": pages,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            metadata["cache_status"] = "written"
        except OSError:
            metadata["cache_status"] = "ecriture_impossible"
    return pages, notes, metadata


def _issuer_aliases_for_identity(companies: list[dict[str, Any]]) -> dict[str, str]:
    """Alias longs d'émetteurs pour vérifier le contenu d'un PDF."""
    aliases = dict(build_issuer_variant_map(companies))
    for alias, ticker in REPORT_LABEL_ALIASES.items():
        aliases.setdefault(canonical_issuer_key(alias), ticker)
    for alias, ticker in NEWS_TICKER_ALIASES.items():
        aliases.setdefault(canonical_issuer_key(alias), ticker)
    country_codes = {
        "cote d ivoire": "ci",
        "senegal": "sn",
        "togo": "tg",
        "benin": "bj",
        "burkina faso": "bf",
        "burkina": "bf",
        "mali": "ml",
        "niger": "ng",
    }
    for company in companies:
        ticker = company.get("ticker")
        name = canonical_issuer_key(company.get("name") or "")
        if not ticker or not name:
            continue
        aliases.setdefault(name, ticker)
        for country, code in country_codes.items():
            if name.endswith(country):
                aliases.setdefault(f"{name[:-len(country)].strip()} {code}", ticker)
    # Mots comptables/génériques : « total » apparaît dans presque tous
    # les états financiers et ne Peut jamais identifier TotalEnergies dans
    # le corps d'un PDF. Les alias longs de l'émetteur restent utilisables.
    for generic_alias in ("total", "capital", "bank", "africa", "international", "services"):
        aliases.pop(generic_alias, None)
    return aliases


_NATIVE_RELEVANCE_MARKERS = (
    "bilan", "compte de resultat", "etat du resultat", "resultat net", "chiffre d affaires",
    "produit net bancaire", "capitaux propres", "tresorerie", "resultat par action",
    "benefice par action", "earnings per share", "nombre d actions", "weighted average",
    "capital souscrit", "total de l actif", "total du passif", "flux de tresorerie",
    "en millions de fcfa", "en milliers de fcfa", "en fcfa", "exercice clos",
)


def _targeted_native_pdf_pages(content: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Lit tout le texte, puis ne structure que les pages utiles si >80.

    L'ancienne borne « 80 premières pages » rendait invisibles les notes
    BPA/capital des longs rapports (SNTS p. 151/224, ETIT p. 261/300).
    Le balayage texte couvre désormais tout le document ; seules les
    pages portant des marqueurs d'états, d'unités, de BPA ou de capital
    sont ensuite structurées par coordonnées, voisines comprises.
    """
    pages: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        total_pages = len(pdf.pages)
        texts: list[str] = []
        for page in pdf.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                texts.append("")
        if total_pages <= 80:
            selected_indexes = list(range(total_pages))
            selection_method = "TOUTES_LES_PAGES_JUSQU_A_80"
        else:
            scores: list[int] = []
            for text in texts:
                normalized = normalize_key(text)
                scores.append(sum(marker in normalized for marker in _NATIVE_RELEVANCE_MARKERS))
            selected = set(range(min(5, total_pages)))
            for index, score in enumerate(scores):
                if score:
                    selected.update({index - 1, index, index + 1})
            selected = {index for index in selected if 0 <= index < total_pages}
            if len(selected) > 160:
                ranked = sorted(selected, key=lambda index: (-scores[index], index))
                selected = set(range(min(5, total_pages))) | set(ranked[:155])
            selected_indexes = sorted(selected)
            selection_method = "BALAYAGE_TEXTE_INTEGRAL_PUIS_PAGES_PERTINENTES"
        for index in selected_indexes:
            page = pdf.pages[index]
            text = texts[index]
            try:
                lines = structured_lines_from_words(page.extract_words() or [])
            except Exception:
                lines = []
            if not lines and text:
                lines = [
                    {"text": clean_text(line), "words": line.split(), "amounts": []}
                    for line in text.split("\n")
                ]
            pages.append({"text": text, "lines": lines, "page_number": index + 1})
    metadata = {
        "pages_total": total_pages,
        "pages_native_text_scanned": total_pages,
        "pages_structured": len(pages),
        "selected_pages": [int(page["page_number"]) for page in pages],
        "selection_method": selection_method,
        "native_text_characters_all_pages": sum(len(text) for text in texts),
    }
    return pages, metadata


def _document_version_markers(doc: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
    filename_markers = list(doc.get("version_markers") or [])
    if not filename_markers:
        filename_markers = document_selection_metadata(
            f"{doc.get('filename') or ''} {doc.get('label') or ''}"
        ).get("version_markers") or []
    first_text = normalize_key(" ".join(_page_text_for_version(page) for page in pages[:5]))
    content_markers: list[str] = []
    rules = (
        ("CORRIGE", ("corrige", "rectifie", "rectificatif")),
        ("RETRAITE", ("retraite", "restated")),
        ("AUDITE_CERTIFIE_OU_APPROUVE", ("audite", "certifie", "approuve", "rapport des commissaires")),
        ("NON_AUDITE_OU_PROVISOIRE", ("non audite", "provisoire", "unaudited")),
        ("CONDENSE", ("condense", "condensed")),
    )
    for label, markers in rules:
        if any(marker in first_text for marker in markers):
            content_markers.append(label)
    markers = sorted(set(filename_markers + content_markers))
    return {
        "version_label": markers[0] if markers else "NON_PRECISE",
        "version_markers": markers,
        "filename_markers": filename_markers,
        "content_markers_first_pages": content_markers,
    }


def _page_text_for_version(page: dict[str, Any]) -> str:
    if page.get("text"):
        return str(page["text"])[:3000]
    return " ".join(str(line.get("text") or "") for line in page.get("lines", [])[:30])


def extract_annual_figures(
    session: requests.Session,
    doc: dict[str, Any],
    cache_dir: Path,
    allow_ocr: bool = True,
    expected_ticker: str | None = None,
    companies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    # La clé de cache inclut l'URL : un même nom générique de PDF chez deux
    # émetteurs ne Peut plus servir le document de l'un pour l'autre.
    url_digest = hashlib.sha256(str(doc.get("url") or "").encode("utf-8")).hexdigest()[:16]
    safe_filename = re.sub(r"[^A-Za-z0-9_.-]+", "_", doc["filename"])
    cache_file = cache_dir / f"{url_digest}-{safe_filename}"
    cache_status = "miss"
    if cache_file.exists() and cache_file.stat().st_size > 10_000:
        content = cache_file.read_bytes()
        cache_status = "hit_par_url_et_nom"
    else:
        content = bytes(fetch(session, doc["url"], binary=True))
        digest = hashlib.sha256(content).hexdigest()
        if len(content) > 30_000_000:
            return {
                "columns": {"courant": {}, "precedent": {}, "colonnes": {"0": {}, "1": {}}},
                "notes": ["Document trop volumineux pour l'extraction automatique (> 30 Mo)."],
                "sha256": digest,
                "document": {
                    "url": doc.get("url"),
                    "filename": doc.get("filename"),
                    "sha256": digest,
                    "bytes": len(content),
                    "selection_status": "REJETE_TROP_VOLUMINEUX",
                },
            }
        cache_file.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    pages, page_selection = _targeted_native_pdf_pages(content)
    total_chars = int(page_selection.get("native_text_characters_all_pages") or 0)

    _page_contexts, content_classification = classify_page_accounting_contexts(pages)
    period = detect_document_period(
        pages,
        filename=f"{doc.get('filename') or ''} {doc.get('label') or ''}",
    )
    fiscal_year = detect_document_fiscal_year(pages)
    filename_exercice = doc.get("exercice") if isinstance(doc.get("exercice"), int) else None
    content_exercice = fiscal_year.get("exercice") if isinstance(fiscal_year.get("exercice"), int) else None
    effective_exercice = content_exercice or filename_exercice
    identity: dict[str, Any] = {
        "status": "NON_PROUVEE",
        "expected_ticker": expected_ticker,
        "method": "non_applique_sans_referentiel_fourni",
    }
    if expected_ticker and companies:
        identity = verify_document_issuer(
            pages,
            expected_ticker,
            _issuer_aliases_for_identity(companies),
            filename=f"{doc.get('filename') or ''} {doc.get('label') or ''}",
        )
    version = _document_version_markers(doc, pages)

    notes: list[str] = []
    selection_rejection: str | None = None
    if identity.get("status") == "AUTRE_EMETTEUR_CONFIRME":
        selection_rejection = "AUTRE_EMETTEUR_CONFIRME"
        notes.append(
            "Document rejeté pour l'émetteur attendu : le contenu identifie "
            f"{identity.get('best_other_ticker') or identity.get('best_ticker')} et non {expected_ticker}."
        )
    elif period.get("period_kind") == "INTERMEDIAIRE":
        selection_rejection = "INTERMEDIAIRE"
        notes.append(
            "Document intermédiaire exclu de la série annuelle "
            f"({', '.join(period.get('interim_markers') or [])})."
        )
    if content_exercice and filename_exercice and content_exercice != filename_exercice:
        notes.append(
            f"Exercice du nom de fichier ({filename_exercice}) différent de l'exercice lu dans le contenu "
            f"({content_exercice}) : le contenu fait foi pour le rattachement des colonnes."
        )
    if content_classification.get("auditor_report_without_detected_statements"):
        notes.append("Le contenu ressemble à un rapport/attestation de commissaires aux comptes sans états primaires détectés.")

    if selection_rejection:
        extracted: dict[str, Any] = {
            "courant": {},
            "precedent": {},
            "colonnes": {"0": {}, "1": {}},
            "_per_share_observations": {"parser_version": EPS_PARSER_VERSION, "eps": [], "shares": [], "numerators": [], "ignored": []},
            "_content_classification": content_classification,
        }
    elif total_chars < 2000:
        extracted = {"courant": {}, "precedent": {}, "colonnes": {"0": {}, "1": {}}}
        notes.append("Texte natif non extractible (document probablement numérisé en image).")
    else:
        extracted = extract_figures_from_pages(pages, document_exercice=effective_exercice)
        notes.extend(extracted.pop("_rejected", []))

    ocr_metadata: dict[str, Any] = {
        "available": None,
        "attempted": False,
        "used": False,
        "cache_status": "non_appele",
        "pages_ocrees": 0,
        "mean_confidence": None,
        "truncated": False,
    }
    if allow_ocr and not selection_rejection and not extracted.get("courant") and not extracted.get("precedent"):
        ocr_pages, ocr_notes, ocr_run_metadata = ocr_pdf_pages(content, cache_dir)
        ocr_metadata.update(ocr_run_metadata)
        ocr_metadata["attempted"] = True
        notes.extend(ocr_notes)
        if ocr_pages:
            if expected_ticker and companies and identity.get("status") in {"NON_PROUVEE", "AMBIGUE"}:
                identity = verify_document_issuer(
                    ocr_pages,
                    expected_ticker,
                    _issuer_aliases_for_identity(companies),
                    filename=f"{doc.get('filename') or ''} {doc.get('label') or ''}",
                )
            ocr_period = detect_document_period(
                ocr_pages,
                filename=f"{doc.get('filename') or ''} {doc.get('label') or ''}",
            )
            if identity.get("status") == "AUTRE_EMETTEUR_CONFIRME":
                selection_rejection = "AUTRE_EMETTEUR_CONFIRME"
                notes.append("Document OCR rejeté : le contenu identifie un autre émetteur coté.")
            elif ocr_period.get("period_kind") == "INTERMEDIAIRE":
                selection_rejection = "INTERMEDIAIRE"
                period = ocr_period
                notes.append("Document OCR intermédiaire exclu de la série annuelle.")
            ocr_extracted = (
                {"courant": {}, "precedent": {}, "colonnes": {"0": {}, "1": {}}}
                if selection_rejection
                else extract_figures_from_pages(ocr_pages, document_exercice=effective_exercice)
            )
            ocr_rejected = list(ocr_extracted.pop("_rejected", []))
            if ocr_extracted.get("courant") or ocr_extracted.get("precedent"):
                extracted = ocr_extracted
                ocr_metadata["used"] = True
                notes.extend(ocr_rejected)
                notes.append(
                    "OCR contrôlé appliqué en repli après échec du texte natif ; seuls les agrégats "
                    "ayant passé les seuils de confiance, d’unité et de plausibilité sont retenus."
                )
            else:
                notes.extend(ocr_rejected)
                notes.append(
                    "OCR contrôlé appliqué en repli, mais aucun agrégat annuel n’a passé les contrôles "
                    "de confiance, d’unité et de plausibilité."
                )
        if not extracted.get("courant") and not extracted.get("precedent"):
            notes.append(
                "Aucun agrégat annuel n'a passé les contrôles d'extraction "
                "(unité explicite introuvable ou libellés non reconnus)."
            )

    document_fingerprint = {
        "url": doc.get("url"),
        "filename": doc.get("filename"),
        "label": doc.get("label"),
        "link_text": doc.get("link_text"),
        "doc_type_filename": doc.get("doc_type"),
        "published_date": doc.get("published_date"),
        "filename_exercice": filename_exercice,
        "filename_exercice_source": doc.get("exercice_source"),
        "content_exercice": content_exercice,
        "content_exercice_status": fiscal_year.get("status"),
        "content_exercice_evidence": fiscal_year.get("evidence") or [],
        "effective_exercice": effective_exercice,
        "period": period,
        "identity": identity,
        "content_classification": extracted.get("_content_classification") or content_classification,
        "scope_hint_filename": doc.get("scope_hint"),
        "framework_hint_filename": doc.get("framework_hint"),
        "selection_status_filename": doc.get("selection_status"),
        "selection_rejection": selection_rejection,
        **version,
        "sha256": digest,
        "bytes": len(content),
        "cache": {"status": cache_status, "key": cache_file.name},
        "page_selection": page_selection,
        "parser_versions": {
            "eps_evidence": EPS_PARSER_VERSION,
            "document_classifier": doc.get("classifier_version"),
        },
    }
    return {
        "columns": extracted,
        "per_share_observations": extracted.get("_per_share_observations") or {
            "parser_version": EPS_PARSER_VERSION,
            "eps": [],
            "shares": [],
            "numerators": [],
            "ignored": [],
        },
        "document": document_fingerprint,
        "identity": identity,
        "content_exercice": content_exercice,
        "effective_exercice": effective_exercice,
        "notes": notes,
        "sha256": digest,
        "extraction": {
            "method": (
                "ocr_controle" if ocr_metadata["used"]
                else "texte_natif" if extracted.get("courant") or extracted.get("precedent")
                else "aucun_agregat_retenu"
            ),
            "native_text_characters": total_chars,
            "page_selection": page_selection,
            "document_identity_status": identity.get("status"),
            "selection_rejection": selection_rejection,
            "ocr": ocr_metadata,
        },
    }


def merge_series_observations(observations: list[dict[str, Any]]) -> tuple[dict[int, dict[str, Any]], list[str]]:
    """Fusionne les observations (exercice, agrégat) issues de plusieurs documents.

    Un agrégat est « confirmé » lorsqu'au moins deux documents officiels distincts
    publient la même valeur (à 1,5 % près) pour le même exercice — typiquement
    l'exercice N de son propre document et la colonne N-1 du document suivant.
    """
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        grouped[(obs["exercice"], obs["key"])].append(obs)

    series: dict[int, dict[str, Any]] = defaultdict(dict)
    notes: list[str] = []
    def _doc_identity(entry: dict[str, Any]) -> str:
        return str(entry.get("doc_sha256") or entry.get("doc_url") or entry.get("doc_label") or "")

    def _entry_signature(entry: dict[str, Any]) -> str | None:
        signature = entry.get("candidate_signature")
        if signature:
            return str(signature)
        parts = [
            entry.get("accounting_scope"),
            entry.get("framework"),
            entry.get("currency"),
            entry.get("component"),
            entry.get("basis"),
        ]
        if any(part not in (None, "NON_PROUVE") for part in parts):
            return "|".join(str(part or "NON_PROUVE") for part in parts)
        return None

    def _scope_priority(entry: dict[str, Any]) -> int:
        scope = entry.get("accounting_scope")
        return 30 if scope == "CONSOLIDE" else 10 if scope in {"INDIVIDUEL", "SOCIAL"} else 20

    for (exercice, key), entries in grouped.items():
        entries.sort(key=_candidate_value)
        clusters: list[list[dict[str, Any]]] = []
        for entry in entries:
            placed = False
            entry_signature = _entry_signature(entry)
            for cluster in clusters:
                cluster_signatures = {
                    _entry_signature(item) for item in cluster if _entry_signature(item) is not None
                }
                if entry_signature is not None and cluster_signatures and entry_signature not in cluster_signatures:
                    continue
                reference = _candidate_value(cluster[0])
                tolerance = max(abs(reference) * 0.015, 1)
                if abs(_candidate_value(entry) - reference) <= tolerance:
                    cluster.append(entry)
                    placed = True
                    break
            if not placed:
                clusters.append([entry])
        best = max(
            clusters,
            key=lambda c: (
                max((_scope_priority(e) for e in c), default=20),
                len({_doc_identity(e) for e in c}),
                max((e.get("source_amount_count") or 0) for e in c),
                len(c),
            ),
        )
        distinct_docs = len({_doc_identity(e) for e in best})
        total_occurrences = sum(e.get("occurrences", 1) for e in best)
        if distinct_docs >= 2:
            confidence = "confirme_deux_documents"
        elif total_occurrences >= 2:
            confidence = "recoupe_dans_le_document"
        else:
            confidence = "extraction_unique"
        if len(clusters) > 1:
            rival = max((c for c in clusters if c is not best), key=len)
            rival_value = _candidate_value(rival[0])
            best_value = _candidate_value(best[0])
            if best_value and abs(rival_value - best_value) > abs(best_value) * 0.05:
                if key == "benefice_par_action":
                    notes.append(
                        f"{FIGURE_DISPLAY_LABELS[key]} {exercice} : valeurs publiées divergentes entre "
                        "documents/versions — groupes conservés, choix soumis au contrôle arithmétique "
                        "et à la quarantaine, jamais au seul nombre d'occurrences."
                    )
                else:
                    notes.append(
                        f"{FIGURE_DISPLAY_LABELS[key]} {exercice} : valeurs divergentes entre documents "
                        f"(retraitement possible) — valeur la mieux recoupée retenue."
                    )
        representative = next((e for e in best if e.get("column") == 0), best[0])
        value_kind = representative.get("value_kind") or FIGURE_VALUE_KINDS.get(key, "fcfa")
        representative_value = _candidate_value(representative)
        methods = {e.get("extraction_method") or "texte_natif" for e in best}
        extraction_method = (
            "ocr_controle" if methods == {"ocr_controle"}
            else "texte_natif_et_ocr" if "ocr_controle" in methods or "texte_natif_et_ocr" in methods
            else "texte_natif"
        )
        ocr_confidences = [
            float(e["ocr_confidence"])
            for e in best
            if isinstance(e.get("ocr_confidence"), (int, float))
        ]
        figure: dict[str, Any] = {
            "label": FIGURE_DISPLAY_LABELS[key],
            "value": int(representative_value) if value_kind != "fcfa_par_action" and float(representative_value).is_integer() else round(representative_value, 4),
            "value_kind": value_kind,
            "unit_label": representative.get("unit_label"),
            "extraction_method": extraction_method,
            "ocr_confidence": round(min(ocr_confidences), 1) if ocr_confidences else None,
            "confidence": confidence,
            "occurrences": total_occurrences,
            "documents_confirmants": distinct_docs,
            "evidence": [],
        }
        for field in (
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
            "source_multiplier",
            "input_rounding_abs_fcfa",
            "arithmetic_check",
            "coherence_status",
            "quarantine_reasons",
            "eps_metadata",
            "share_metadata",
        ):
            if representative.get(field) is not None:
                figure[field] = representative[field]

        def _merged_group_summary(cluster: list[dict[str, Any]]) -> dict[str, Any]:
            group_rep = next((e for e in cluster if e.get("column") == 0), cluster[0])
            group_value = _candidate_value(group_rep)
            group_kind = group_rep.get("value_kind") or value_kind
            return {
                "value": int(group_value) if group_kind != "fcfa_par_action" and float(group_value).is_integer() else round(group_value, 4),
                "value_kind": group_kind,
                "candidate_signature": _entry_signature(group_rep),
                "accounting_scope": group_rep.get("accounting_scope"),
                "framework": group_rep.get("framework"),
                "currency": group_rep.get("currency"),
                "component": group_rep.get("component"),
                "basis": group_rep.get("basis"),
                "documents_confirmants": len({_doc_identity(e) for e in cluster}),
                "occurrences": sum(e.get("occurrences", 1) for e in cluster),
                "documents": [
                    {
                        "label": e.get("doc_label"),
                        "url": e.get("doc_url"),
                        "sha256": e.get("doc_sha256"),
                        "document_exercice": e.get("doc_exercice"),
                        "version_label": e.get("doc_version_label"),
                        "published_date": e.get("doc_published_date"),
                    }
                    for e in cluster[:4]
                ],
                "eligible": all(
                    (e.get("currency") in (None, "FCFA"))
                    and (e.get("component") in (None, "TOTAL", "TOTAL_EQUIVALENT_ARRETEES_NEANT_OU_ZERO"))
                    and (e.get("basis") in (None, "DE_BASE", "DE_BASE_ET_DILUE_PRESENTES_ENSEMBLE"))
                    for e in cluster
                ) if key == "benefice_par_action" else True,
                "selected": cluster is best,
            }

        figure["candidate_groups"] = [_merged_group_summary(cluster) for cluster in clusters[:8]]
        if value_kind == "fcfa":
            figure["value_fcfa"] = int(round(representative_value))
            figure["value"] = figure["value_fcfa"]
        series[exercice][key] = figure
        evidence_details = []
        for e in best[:3]:
            for ev in (e.get("evidence") or [{"page": e.get("page"), "line": e.get("line"), "unit_label": e.get("unit_label")}]):
                evidence_details.append(
                    {
                        **ev,
                        "document_label": e.get("doc_label"),
                        "document_url": e.get("doc_url"),
                        "document_sha256": e.get("doc_sha256"),
                        "document_version_label": e.get("doc_version_label"),
                        "document_published_date": e.get("doc_published_date"),
                    }
                )
        series[exercice][key]["evidence"] = evidence_details[:4]
    return dict(series), notes


def series_hygiene(series_list: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Purge les artefacts de série : exercice dupliqué mal étiqueté et ruptures
    d'échelle isolées entre exercices consécutifs."""
    notes: list[str] = []
    rank = {"confirme_deux_documents": 2, "recoupe_dans_le_document": 1, "extraction_unique": 0}

    # 1) Deux exercices aux agrégats identiques (>= 3 valeurs égales) signalent
    #    presque toujours un document mal étiqueté : conserver le plus récent.
    signatures: dict[tuple, int] = {}
    kept: list[dict[str, Any]] = []
    for entry in sorted(series_list, key=lambda e: -e["exercice"]):
        values = tuple(
            (key, entry["figures"][key]["value_fcfa"])
            for key in sorted(entry["figures"])
            if isinstance(entry["figures"][key].get("value_fcfa"), int)
        )
        duplicate_of = None
        if len(values) >= 3:
            for signature, exercice in signatures.items():
                shared = len(set(values) & set(signature))
                if shared >= 3:
                    duplicate_of = exercice
                    break
        if duplicate_of is not None:
            notes.append(
                f"Exercice {entry['exercice']} écarté : agrégats identiques à l'exercice {duplicate_of} "
                "(document probablement mal étiqueté)."
            )
            continue
        signatures[values] = entry["exercice"]
        kept.append(entry)
    series_list = sorted(kept, key=lambda e: -e["exercice"])

    # 2) Rupture d'échelle isolée sur les agrégats de stock et d'activité.
    for key in ("capitaux_propres", "total_bilan", "chiffre_affaires", "produit_net_bancaire"):
        points = [
            (entry["exercice"], entry["figures"][key])
            for entry in sorted(series_list, key=lambda e: e["exercice"])
            if key in entry["figures"]
        ]
        for (year_a, fig_a), (year_b, fig_b) in zip(points, points[1:]):
            if year_b - year_a > 2:
                continue
            va, vb = fig_a["value_fcfa"], fig_b["value_fcfa"]
            if va <= 0 or vb <= 0:
                continue
            ratio = max(va, vb) / min(va, vb)
            if ratio <= 3:
                continue
            rank_a = rank.get(fig_a.get("confidence"), 0)
            rank_b = rank.get(fig_b.get("confidence"), 0)
            if rank_a != rank_b:
                weaker_year = year_a if rank_a < rank_b else year_b
            else:
                # À recoupement égal, un troisième exercice donne l'échelle
                # de référence : écarter le point qui s'en éloigne le plus
                # (chiffre parasite OCR multipliant un total par dix), plutôt
                # que l'exercice le plus ancien par défaut.
                other_values = sorted(
                    fig["value_fcfa"]
                    for year, fig in points
                    if year not in (year_a, year_b) and fig["value_fcfa"] > 0
                )
                if other_values:
                    reference = other_values[len(other_values) // 2]
                    distance_a = max(va / reference, reference / va)
                    distance_b = max(vb / reference, reference / vb)
                    weaker_year = year_a if distance_a >= distance_b else year_b
                else:
                    weaker_year = year_a
            for entry in series_list:
                if entry["exercice"] == weaker_year and key in entry["figures"]:
                    entry["figures"].pop(key, None)
                    notes.append(
                        f"{FIGURE_DISPLAY_LABELS[key]} {weaker_year} écarté : rupture d'échelle "
                        f"(×{ratio:.1f}) avec l'exercice voisin, extraction la moins recoupée."
                    )
    series_list = [entry for entry in series_list if entry["figures"]]
    return series_list, notes


def add_derived_financial_debt(figures: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Total de dette financière seulement si les deux composantes IFRS
    courant / non courant du même exercice ont été lues. Aucun total n'est
    déduit d'une seule composante."""
    current = figures.get("dettes_financieres_courantes") or {}
    non_current = figures.get("dettes_financieres_non_courantes") or {}
    current_value = current.get("value_fcfa")
    non_current_value = non_current.get("value_fcfa")
    if not isinstance(current_value, int) or not isinstance(non_current_value, int):
        return figures, []
    total_value = current_value + non_current_value
    bilan = figures.get("total_bilan", {}).get("value_fcfa")
    if isinstance(bilan, int) and bilan > 0 and total_value > bilan * 1.05:
        return figures, [
            "Dettes financières totales non calculées : la somme courant + non courant dépasse le total du bilan."
        ]
    rank = {"confirme_deux_documents": 2, "recoupe_dans_le_document": 1, "extraction_unique": 0}
    confidence = min(
        (current.get("confidence"), non_current.get("confidence")),
        key=lambda item: rank.get(item, 0),
    ) or "extraction_unique"
    evidence = list(current.get("evidence") or []) + list(non_current.get("evidence") or [])
    methods = {current.get("extraction_method") or "texte_natif", non_current.get("extraction_method") or "texte_natif"}
    extraction_method = (
        "ocr_controle" if methods == {"ocr_controle"}
        else "texte_natif_et_ocr" if "ocr_controle" in methods or "texte_natif_et_ocr" in methods
        else "texte_natif"
    )
    ocr_confidences = [
        float(item["ocr_confidence"])
        for item in (current, non_current)
        if isinstance(item.get("ocr_confidence"), (int, float))
    ]
    figures["dettes_financieres"] = {
        "label": FIGURE_DISPLAY_LABELS["dettes_financieres"],
        "value": total_value,
        "value_fcfa": total_value,
        "value_kind": "fcfa",
        "unit_label": "calculé : dettes financières courantes + non courantes du même exercice",
        "extraction_method": extraction_method,
        "ocr_confidence": round(min(ocr_confidences), 1) if ocr_confidences else None,
        "confidence": confidence,
        "occurrences": int(current.get("occurrences") or 0) + int(non_current.get("occurrences") or 0),
        "documents_confirmants": min(
            int(current.get("documents_confirmants") or 0),
            int(non_current.get("documents_confirmants") or 0),
        ),
        "evidence": evidence[:4],
        "derived": True,
        "components": ["dettes_financieres_courantes", "dettes_financieres_non_courantes"],
    }
    return figures, []


CAPITAL_SUPPLEMENT_KEYS = (
    "resultat_net_attribuable_ordinaires",
    "benefice_par_action",
    "nombre_actions_fin_exercice",
    "nombre_actions_moyen_pondere",
)
PERIMETER_CORE_KEYS = (
    "chiffre_affaires",
    "produit_net_bancaire",
    "resultat_net",
    "resultat_net_part_groupe",
    "capitaux_propres",
    "total_bilan",
)


def _figure_numeric_value(figures: dict[str, Any], key: str) -> float | None:
    figure = figures.get(key) or {}
    value = figure.get("value", figure.get("value_fcfa"))
    return float(value) if isinstance(value, (int, float)) else None


def _figures_share_perimeter(primary: dict[str, Any], supplement: dict[str, Any]) -> bool:
    """Vrai si deux documents décrivent le même périmètre comptable.

    La passe complémentaire capital/BPA ne doit pas mélanger un état social
    et un état consolidé, ni deux référentiels dont les agrégats divergent.
    On exige au moins un agrégat central commun à 1,5 % près et aucun
    agrégat central commun écarté de plus de 5 %.
    """
    # Un périmètre explicite incompatible prime sur la proximité des
    # montants : un BPA individuel ne complète jamais une série consolidée,
    # même si quelques agrégats sont numériquement proches.
    for key in set(primary) & set(supplement):
        primary_scope = (primary.get(key) or {}).get("accounting_scope")
        supplement_scope = (supplement.get(key) or {}).get("accounting_scope")
        if (
            primary_scope not in (None, "NON_PROUVE", "MIXTE")
            and supplement_scope not in (None, "NON_PROUVE", "MIXTE")
            and primary_scope != supplement_scope
        ):
            return False
    relative_gaps: list[float] = []
    for key in PERIMETER_CORE_KEYS:
        primary_value = _figure_numeric_value(primary, key)
        supplement_value = _figure_numeric_value(supplement, key)
        if primary_value is None or supplement_value is None:
            continue
        scale = max(abs(primary_value), abs(supplement_value))
        if scale == 0:
            continue
        relative_gaps.append(abs(primary_value - supplement_value) / scale)
    return bool(relative_gaps and min(relative_gaps) <= 0.015 and max(relative_gaps) <= 0.05)


def _missing_capital_keys(figures: dict[str, Any]) -> list[str]:
    return [key for key in CAPITAL_SUPPLEMENT_KEYS if key not in figures]


# Contrat BPA par observation société-exercice (corrections du 24/10/2026).
# Ne jamais fusionner ces niveaux dans un taux unique : un BPA publié, un
# BPA recalculé avec numérateur ordinaire + actions moyennes pondérées, un
# candidat part du groupe pondéré encore à vérifier et un simple ratio avec
# les actions de fin d'exercice n'ont pas la même signification comptable.
EPS_STATUS_PUBLISHED_CONFIRMED = "PUBLIE_CONFIRME_DEUX_DOCUMENTS"
EPS_STATUS_PUBLISHED_EXTRACTED = "PUBLIE_EXTRAIT"
EPS_STATUS_PUBLISHED_DIVERGENCE_RESOLVED = "PUBLIE_SOURCE_DIVERGENTE_RESOLUE_PAR_CONTROLE"
EPS_STATUS_PUBLISHED_QUARANTINE_COHERENCE = "PUBLIE_EN_QUARANTAINE_COHERENCE"
EPS_STATUS_PUBLISHED_QUARANTINE_DIVERGENCE = "PUBLIE_EN_QUARANTAINE_VALEURS_DIVERGENTES"
EPS_STATUS_PUBLISHED_QUARANTINE_AMBIGUITY = "PUBLIE_EN_QUARANTAINE_AMBIGUITE"
EPS_STATUS_PUBLISHED_NOT_RETAINED = "PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE"
EPS_STATUS_RECALCULATED_CONFIRMED = "RECALCULE_COMPARABLE_CONFIRME_DEUX_DOCUMENTS"
EPS_STATUS_RECALCULATED_EXTRACTED = "RECALCULE_COMPARABLE_INTRANT_NON_CONFIRME"
EPS_STATUS_PARENT_WEIGHTED_CANDIDATE = "RECALCULE_PART_GROUPE_PONDEREE_A_VERIFIER"
EPS_STATUS_INDICATIVE_END_SHARES = "RATIO_INDICATIF_FIN_EXERCICE"
EPS_STATUS_NOT_PUBLISHED_IN_VERIFIED_SOURCES = "NON_PUBLIE_DANS_SOURCES_VERIFIEES"
EPS_STATUS_NOT_RESEARCHED = "NON_RECHERCHE"
EPS_STATUS_DOCUMENT_NOT_FOUND = "DOCUMENT_INTROUVABLE"
EPS_STATUS_UNREADABLE = "ILLISIBLE"
EPS_STATUS_NOT_APPLICABLE = "NON_APPLICABLE"


def _eps_confirmation_status(figures: dict[str, Any], key: str) -> str | None:
    figure = figures.get(key) or {}
    if not figure:
        return None
    if (figure.get("documents_confirmants") or 0) >= 2 or figure.get("confidence") == "confirme_deux_documents":
        return "CONFIRME_DEUX_DOCUMENTS"
    if figure.get("confidence") == "recoupe_dans_le_document":
        return "RECOUPE_DANS_LE_DOCUMENT"
    return "EXTRACTION_UNIQUE"


def _figure_scope(figures: dict[str, Any], key: str) -> str | None:
    scope = (figures.get(key) or {}).get("accounting_scope")
    return str(scope) if scope not in (None, "NON_PROUVE", "MIXTE") else None


def _figure_rounding_abs(figures: dict[str, Any], key: str) -> float | None:
    figure = figures.get(key) or {}
    explicit = figure.get("input_rounding_abs_fcfa")
    if isinstance(explicit, (int, float)):
        return float(explicit)
    multiplier = figure.get("source_multiplier")
    if isinstance(multiplier, (int, float)):
        return abs(float(multiplier)) * 0.5
    return None


def derive_eps_metrics(
    figures: dict[str, Any],
    previous_figures: dict[str, Any] | None = None,
    *,
    exercice: int | None = None,
    ticker: str | None = None,
    capital_events: list[dict[str, Any]] | None = None,
    eps_observations: Any = None,
    reference_scope: str | None = None,
) -> dict[str, Any]:
    """Classe les calculs par action sans jamais les confondre.

    - ``RECALCULE_COMPARABLE`` exige le résultat attribuable aux
      actionnaires ordinaires et le nombre moyen pondéré d'actions.
    - La part du groupe divisée par les actions pondérées n'est qu'un
      candidat à vérifier (dividendes de préférence et périmètre ordinaire
      non établis par ce seul agrégat).
    - Les actions en fin d'exercice ne produisent qu'un ratio indicatif,
      notamment l'année d'un changement de capital.
    - Un BPA publié incohérent avec ses intrants pondérés, ou présent en
      plusieurs valeurs incompatibles, est conservé comme preuve mais
      placé en quarantaine ; il ne compte pas dans la couverture BPA.
    """
    eps_figure = figures.get("benefice_par_action") or {}
    raw_published = _figure_numeric_value(figures, "benefice_par_action")
    published = raw_published
    ordinary_numerator = _figure_numeric_value(figures, "resultat_net_attribuable_ordinaires")
    parent_numerator = _figure_numeric_value(figures, "resultat_net_part_groupe")
    total_numerator = _figure_numeric_value(figures, "resultat_net")
    weighted_shares = _figure_numeric_value(figures, "nombre_actions_moyen_pondere")
    end_shares = _figure_numeric_value(figures, "nombre_actions_fin_exercice")
    treasury_shares = _figure_numeric_value(figures, "actions_autocontrole")
    eps_scope = _figure_scope(figures, "benefice_par_action")
    ordinary_scope = _figure_scope(figures, "resultat_net_attribuable_ordinaires")
    parent_scope = _figure_scope(figures, "resultat_net_part_groupe")
    weighted_scope = _figure_scope(figures, "nombre_actions_moyen_pondere")
    end_scope = _figure_scope(figures, "nombre_actions_fin_exercice")

    recalculated = None
    if ordinary_numerator is not None and weighted_shares and weighted_shares > 0:
        recalculated = ordinary_numerator / weighted_shares
    parent_weighted = None
    if parent_numerator is not None and weighted_shares and weighted_shares > 0:
        parent_weighted = parent_numerator / weighted_shares

    indicative_numerator = ordinary_numerator
    indicative_numerator_key = "resultat_net_attribuable_ordinaires" if ordinary_numerator is not None else None
    if indicative_numerator is None and parent_numerator is not None:
        indicative_numerator = parent_numerator
        indicative_numerator_key = "resultat_net_part_groupe"
    if indicative_numerator is None and total_numerator is not None:
        indicative_numerator = total_numerator
        indicative_numerator_key = "resultat_net"
    indicative = (
        indicative_numerator / end_shares
        if indicative_numerator is not None and end_shares and end_shares > 0
        else None
    )

    numerator_confirmation = _eps_confirmation_status(
        figures, "resultat_net_attribuable_ordinaires"
    )
    denominator_confirmation = _eps_confirmation_status(
        figures, "nombre_actions_moyen_pondere"
    )
    inputs_confirmed_two_documents = (
        numerator_confirmation == "CONFIRME_DEUX_DOCUMENTS"
        and denominator_confirmation == "CONFIRME_DEUX_DOCUMENTS"
    )

    # --- Observations non retenues et groupes de valeurs publiées ---
    observation_items: list[dict[str, Any]] = []
    if isinstance(eps_observations, dict):
        observation_items = list(eps_observations.get("eps") or [])
    elif isinstance(eps_observations, list):
        observation_items = [item for item in eps_observations if isinstance(item, dict)]
    relevant_observations = [
        item for item in observation_items
        if exercice is None or item.get("target_exercice") in (None, exercice)
    ]
    nonretained_observations = [
        {
            "value": item.get("value"),
            "currency": item.get("currency"),
            "component": item.get("component"),
            "basis": item.get("basis"),
            "accounting_scope": item.get("accounting_scope"),
            "ineligibility_reasons": item.get("ineligibility_reasons") or [],
            "evidence": item.get("evidence"),
        }
        for item in relevant_observations
        if item.get("value") is not None and not item.get("eligible_fcfa_total_basic")
    ]

    candidate_groups: list[dict[str, Any]] = list(eps_figure.get("candidate_groups") or [])
    if not candidate_groups and relevant_observations:
        grouped_observations: dict[tuple[Any, ...], dict[str, Any]] = {}
        for item in relevant_observations:
            if item.get("value") is None or item.get("is_dash"):
                continue
            key = (
                float(item["value"]),
                item.get("accounting_scope"),
                item.get("currency"),
                item.get("component"),
                item.get("basis"),
            )
            group = grouped_observations.setdefault(
                key,
                {
                    "value": float(item["value"]),
                    "value_kind": "fcfa_par_action" if item.get("currency") == "FCFA" else "autre_devise_par_action",
                    "accounting_scope": item.get("accounting_scope"),
                    "framework": item.get("framework"),
                    "currency": item.get("currency"),
                    "component": item.get("component"),
                    "basis": item.get("basis"),
                    "occurrences": 0,
                    "documents_confirmants": 0,
                    "eligible": bool(item.get("eligible_fcfa_total_basic")),
                    "published_decimals": item.get("published_decimals"),
                    "_doc_keys": set(),
                },
            )
            group["occurrences"] += 1
            evidence = item.get("evidence") or {}
            group["_doc_keys"].add(
                str(evidence.get("document_sha256") or evidence.get("page") or group["occurrences"])
            )
            group["documents_confirmants"] = len(group["_doc_keys"])
        candidate_groups = [
            {key: value for key, value in group.items() if not key.startswith("_")}
            for group in grouped_observations.values()
        ]

    explicit_group_scopes = {
        str(group.get("accounting_scope"))
        for group in candidate_groups
        if group.get("accounting_scope") not in (None, "NON_PROUVE", "MIXTE")
    }
    chosen_scope = reference_scope or eps_scope or ("CONSOLIDE" if "CONSOLIDE" in explicit_group_scopes else None)
    if chosen_scope:
        selected_candidate_groups = [
            group for group in candidate_groups
            if group.get("accounting_scope") in (None, "NON_PROUVE", "MIXTE", chosen_scope)
        ]
        other_scope_candidate_groups = [
            group for group in candidate_groups if group not in selected_candidate_groups
        ]
    else:
        selected_candidate_groups = candidate_groups
        other_scope_candidate_groups = []

    # --- Contrôles arithmétiques, arrondis de publication inclus ---
    def _arithmetic_check(value: float | None, numerator: float | None, numerator_key: str, reference: str):
        if value is None or numerator is None or not weighted_shares:
            return None
        numerator_scope = ordinary_scope if numerator_key == "resultat_net_attribuable_ordinaires" else parent_scope
        if eps_scope and numerator_scope and eps_scope != numerator_scope:
            return {
                "reference": reference,
                "status": "NON_APPLICABLE_PERIMETRES_DIFFERENTS",
                "concordant": False,
                "scope_mismatch": True,
            }
        return assess_eps_arithmetic(
            float(value),
            float(numerator),
            float(weighted_shares),
            published_decimals=eps_figure.get("published_decimals"),
            numerator_rounding_abs=_figure_rounding_abs(figures, numerator_key),
            reference=reference,
        )

    check_numerator = ordinary_numerator if ordinary_numerator is not None else parent_numerator
    check_numerator_key = (
        "resultat_net_attribuable_ordinaires" if ordinary_numerator is not None else "resultat_net_part_groupe"
    )
    check_reference = "RECALCULE_COMPARABLE" if ordinary_numerator is not None else "PART_GROUPE_PONDEREE"
    checks_by_value: dict[float, dict[str, Any]] = {}
    for group in selected_candidate_groups:
        if isinstance(group.get("value"), (int, float)):
            check = _arithmetic_check(float(group["value"]), check_numerator, check_numerator_key, check_reference)
            if check:
                checks_by_value[float(group["value"])] = check

    published_selection: dict[str, Any] = {
        "status": "AUCUN_GROUPE_CANDIDAT_DETAILLE",
        "value": raw_published,
        "group": None,
        "reasons": [],
    }
    quarantine_reasons: list[str] = list(eps_figure.get("quarantine_reasons") or [])
    quarantine_status: str | None = None
    if selected_candidate_groups and raw_published is not None:
        published_selection = select_published_eps_candidate(selected_candidate_groups, checks_by_value)
        if published_selection.get("status") == "QUARANTAINE_VALEURS_PUBLIEES_DIVERGENTES":
            quarantine_status = EPS_STATUS_PUBLISHED_QUARANTINE_DIVERGENCE
            quarantine_reasons.extend(published_selection.get("reasons") or [])
            published = None
        elif published_selection.get("value") is not None:
            published = float(published_selection["value"])
    elif selected_candidate_groups and raw_published is None:
        # Les observations détaillées peuvent exister sans figure agrégée
        # (régression documentaire) : même règle de sélection.
        published_selection = select_published_eps_candidate(selected_candidate_groups, checks_by_value)
        if published_selection.get("value") is not None:
            published = float(published_selection["value"])
        elif published_selection.get("status") == "QUARANTAINE_VALEURS_PUBLIEES_DIVERGENTES":
            quarantine_status = EPS_STATUS_PUBLISHED_QUARANTINE_DIVERGENCE
            quarantine_reasons.extend(published_selection.get("reasons") or [])

    arithmetic_checks: list[dict[str, Any]] = []
    strict_check = _arithmetic_check(
        published if published is not None else raw_published,
        ordinary_numerator,
        "resultat_net_attribuable_ordinaires",
        "RECALCULE_COMPARABLE",
    )
    if strict_check:
        arithmetic_checks.append(strict_check)
    parent_check = _arithmetic_check(
        published if published is not None else raw_published,
        parent_numerator,
        "resultat_net_part_groupe",
        "PART_GROUPE_PONDEREE",
    )
    if parent_check:
        arithmetic_checks.append(parent_check)
    primary_check = strict_check or parent_check
    if published is not None and primary_check and primary_check.get("concordant"):
        # Le contrôle de plausibilité amont a pu juger la valeur brute
        # initialement fusionnée ; si la divergence a été résolue et que
        # la valeur finalement sélectionnée concorde, cette raison vise
        # l'ancienne valeur et ne doit pas remettre la bonne en quarantaine.
        quarantine_reasons = [
            reason
            for reason in quarantine_reasons
            if reason != "BPA_PUBLIE_INCOHERENT_AVEC_NUMERATEUR_ET_DENOMINATEUR_PONDERES"
        ]

    published_metadata_reasons: list[str] = []
    if raw_published is not None:
        if eps_figure.get("currency") not in (None, "FCFA"):
            published_metadata_reasons.append("DEVISE_PUBLIEE_NON_FCFA_OU_NON_PROUVEE")
        if eps_figure.get("component") in {"ACTIVITES_POURSUIVIES", "ACTIVITES_ARRETEES_OU_EN_CESSION", "NON_PRECISE"}:
            published_metadata_reasons.append("COMPOSANTE_PUBLIEE_NON_TOTALE_OU_NON_PRECISE")
        if eps_figure.get("basis") in {"DILUE", "NON_PRECISE"}:
            published_metadata_reasons.append("BASE_PUBLIEE_NON_ETABLIE_COMME_DE_BASE")
        if reference_scope and eps_scope and eps_scope != reference_scope:
            published_metadata_reasons.append("PERIMETRE_PUBLIE_DIFFERENT_DU_PERIMETRE_DE_REFERENCE")

    if published is not None and published_metadata_reasons:
        quarantine_status = EPS_STATUS_PUBLISHED_NOT_RETAINED
        quarantine_reasons.extend(published_metadata_reasons)
        published = None
    elif published is not None and primary_check and not primary_check.get("scope_mismatch") and not primary_check.get("concordant"):
        quarantine_status = EPS_STATUS_PUBLISHED_QUARANTINE_COHERENCE
        quarantine_reasons.append("ECART_ARITHMETIQUE_AU_DELA_DES_ARRONDIS_DE_PUBLICATION")
        published = None
    elif published is not None and quarantine_reasons:
        quarantine_status = quarantine_status or EPS_STATUS_PUBLISHED_QUARANTINE_COHERENCE
        published = None

    if quarantine_status is not None and (raw_published is not None or relevant_observations):
        status = quarantine_status
    elif published is not None:
        selected_group = published_selection.get("group") or {}
        if published_selection.get("status") == "DIVERGENCE_RESOLUE_PAR_CONTROLE_ARITHMETIQUE":
            status = EPS_STATUS_PUBLISHED_DIVERGENCE_RESOLVED
        elif (selected_group.get("documents_confirmants") or 0) >= 2 or _eps_confirmation_status(
            figures, "benefice_par_action"
        ) == "CONFIRME_DEUX_DOCUMENTS":
            status = EPS_STATUS_PUBLISHED_CONFIRMED
        else:
            status = EPS_STATUS_PUBLISHED_EXTRACTED
    elif recalculated is not None:
        status = (
            EPS_STATUS_RECALCULATED_CONFIRMED
            if inputs_confirmed_two_documents
            else EPS_STATUS_RECALCULATED_EXTRACTED
        )
    elif parent_weighted is not None:
        status = EPS_STATUS_PARENT_WEIGHTED_CANDIDATE
    elif indicative is not None:
        status = EPS_STATUS_INDICATIVE_END_SHARES
    elif nonretained_observations:
        status = EPS_STATUS_PUBLISHED_NOT_RETAINED
    else:
        status = None

    # --- Structure du capital : drapeaux et événements, jamais d'ajustement deviné ---
    capital_flags: list[str] = []
    weighted_end_ratio = None
    if weighted_shares and end_shares:
        weighted_end_ratio = float(end_shares) / float(weighted_shares)
        gap = abs(weighted_shares - end_shares) / max(weighted_shares, end_shares)
        if gap > 0.001:
            capital_flags.extend(
                [
                    "DENOMINATEURS_PONDERES_ET_FIN_EXERCICE_DIFFERENTS",
                    "CHANGEMENT_DE_CAPITAL_EN_COURS_D_EXERCICE_A_DOCUMENTER",
                ]
            )
    previous_end_shares = _figure_numeric_value(
        previous_figures or {}, "nombre_actions_fin_exercice"
    )
    previous_weighted_shares = _figure_numeric_value(
        previous_figures or {}, "nombre_actions_moyen_pondere"
    )
    share_count_changes: list[dict[str, Any]] = []
    if exercice and previous_figures:
        share_count_changes = detect_share_count_changes(
            [
                {
                    "exercice": exercice - 1,
                    "end_shares": previous_end_shares,
                    "weighted_shares": previous_weighted_shares,
                },
                {
                    "exercice": exercice,
                    "end_shares": end_shares,
                    "weighted_shares": weighted_shares,
                },
            ]
        )
    elif end_shares and previous_end_shares:
        gap = abs(end_shares - previous_end_shares) / max(end_shares, previous_end_shares)
        if gap > 0.001:
            share_count_changes = [
                {
                    "basis": "end_shares",
                    "previous_shares": float(previous_end_shares),
                    "current_shares": float(end_shares),
                    "ratio_current_to_previous": round(float(end_shares) / float(previous_end_shares), 6),
                    "status": "CHANGEMENT_A_DOCUMENTER",
                    "chainable_without_event": False,
                }
            ]
    if share_count_changes:
        capital_flags.append("CHANGEMENT_DU_NOMBRE_D_ACTIONS_EN_FIN_EXERCICE")
        if any(change.get("suspected_factor_to_document") for change in share_count_changes):
            capital_flags.append("FACTEUR_DE_CHANGEMENT_ROND_A_DOCUMENTER")
    if treasury_shares:
        capital_flags.append("ACTIONS_D_AUTOCONTROLE_PUBLIEES")

    events = capital_events
    if events is None and ticker:
        try:
            events = load_verified_capital_events()
        except (OSError, ValueError):
            events = []
    events_between: list[dict[str, Any]] = []
    if ticker and exercice and events:
        start = f"{exercice - 1}-12-31"
        end = f"{exercice}-12-31"
        for event in events:
            if str(event.get("ticker") or "").upper() != ticker.upper():
                continue
            event_date = (
                event.get("accounting_effective_date")
                or event.get("entitlement_date")
                or event.get("effective_date")
                or event.get("decision_date")
            )
            if event_date and start < str(event_date) <= end:
                events_between.append(event)
    if events_between:
        capital_flags.append("EVENEMENT_DE_CAPITAL_SOURCE_DANS_L_EXERCICE")
    indicative_chainable = not share_count_changes and not events_between
    if indicative is not None and not indicative_chainable:
        capital_flags.append("RATIO_FIN_EXERCICE_NON_CHAINABLE_SANS_RETRAITEMENT_DOCUMENTE")

    capital_structure = {
        "flags": sorted(set(capital_flags)),
        "weighted_to_end_ratio": round(weighted_end_ratio, 6) if weighted_end_ratio else None,
        "share_count_changes": share_count_changes,
        "verified_events_in_exercice": events_between,
        "treasury_shares": treasury_shares,
        "indicative_ratio_chainable_with_previous_year": indicative_chainable,
        "adjustment_policy": "AUCUN_AJUSTEMENT_SANS_EVENEMENT_SOURCE_ET_VINTAGE_DE_LA_VALEUR",
    }

    return {
        "status": status,
        "published_eps_fcfa": published,
        "eligible_published_eps_fcfa": published,
        "published_eps_candidate_before_quarantine_fcfa": (
            float(published_selection["value"])
            if isinstance(published_selection.get("value"), (int, float))
            else raw_published
        ),
        "published_eps_raw_figure_fcfa": raw_published,
        "published_candidate_groups": selected_candidate_groups,
        "other_scope_candidate_groups": other_scope_candidate_groups,
        "published_selection": {
            "status": published_selection.get("status"),
            "value": published_selection.get("value"),
            "reasons": published_selection.get("reasons") or [],
            "candidate_values": published_selection.get("candidate_values") or [],
        },
        "published_scope": eps_scope,
        "published_currency": eps_figure.get("currency"),
        "published_component": eps_figure.get("component"),
        "published_basis": eps_figure.get("basis"),
        "nonretained_eps_observations": nonretained_observations[:12],
        "recalculated_comparable_eps_fcfa": recalculated,
        "parent_weighted_candidate_fcfa": parent_weighted,
        "indicative_result_per_end_share_fcfa": indicative,
        "numerator": {
            "ordinary_key": "resultat_net_attribuable_ordinaires" if ordinary_numerator is not None else None,
            "ordinary_value_fcfa": ordinary_numerator,
            "ordinary_confirmation": numerator_confirmation,
            "ordinary_scope": ordinary_scope,
            "parent_value_fcfa": parent_numerator,
            "parent_scope": parent_scope,
            "indicative_key": indicative_numerator_key,
            "indicative_value_fcfa": indicative_numerator,
        },
        "denominator": {
            "weighted_average_shares": weighted_shares,
            "weighted_average_confirmation": denominator_confirmation,
            "weighted_average_scope_source": weighted_scope,
            "end_of_period_shares": end_shares,
            "end_of_period_scope_source": end_scope,
            "treasury_shares": treasury_shares,
        },
        "inputs_confirmed_two_documents": inputs_confirmed_two_documents,
        "capital_structure_flags": capital_structure["flags"],
        "capital_structure": capital_structure,
        "arithmetic_checks": arithmetic_checks,
        "cross_check": primary_check,
        "quarantine": (
            {"status": quarantine_status, "reasons": sorted(set(quarantine_reasons))}
            if quarantine_status
            else None
        ),
    }


def classify_eps_observation(
    figures: dict[str, Any],
    *,
    audit_completed: bool = False,
    searched_documents: int = 0,
    candidate_documents: int = 0,
    candidate_unreadable: bool = False,
    not_applicable: bool = False,
    previous_figures: dict[str, Any] | None = None,
    exercice: int | None = None,
    ticker: str | None = None,
    capital_events: list[dict[str, Any]] | None = None,
    eps_observations: Any = None,
    reference_scope: str | None = None,
) -> dict[str, Any]:
    """Statut principal d'une observation BPA société-exercice.

    ``NON_PUBLIE_DANS_SOURCES_VERIFIEES`` exige un audit terminé et au moins
    un document effectivement examiné. En l'absence de cette preuve d'audit,
    le statut honnête reste ``NON_RECHERCHE``.
    """
    metrics = derive_eps_metrics(
        figures,
        previous_figures=previous_figures,
        exercice=exercice,
        ticker=ticker,
        capital_events=capital_events,
        eps_observations=eps_observations,
        reference_scope=reference_scope,
    )
    if metrics["status"] is not None:
        return metrics
    if not_applicable:
        status = EPS_STATUS_NOT_APPLICABLE
    elif audit_completed and candidate_unreadable:
        status = EPS_STATUS_UNREADABLE
    elif audit_completed and searched_documents > 0:
        status = EPS_STATUS_NOT_PUBLISHED_IN_VERIFIED_SOURCES
    elif audit_completed and candidate_documents == 0:
        status = EPS_STATUS_DOCUMENT_NOT_FOUND
    else:
        status = EPS_STATUS_NOT_RESEARCHED
    return {**metrics, "status": status}


def _annual_candidate_documents(
    documents: list[dict[str, Any]], exercice: int
) -> list[dict[str, Any]]:
    """Documents annuels pouvant contenir l'exercice, comparatif inclus."""
    return [
        document
        for document in documents
        if document.get("doc_type") in ANNUAL_DOC_PRIORITY
        and document.get("exercice") in (exercice, exercice + 1)
    ]


def _report_pages_by_ticker(
    companies: list[dict[str, Any]], report_pages: list[dict[str, str]]
) -> dict[str, list[dict[str, str]]]:
    variants = build_issuer_variant_map(companies)
    for alias, ticker in REPORT_LABEL_ALIASES.items():
        variants.setdefault(canonical_issuer_key(alias), ticker)
    pages_by_ticker: dict[str, list[dict[str, str]]] = defaultdict(list)
    for page in report_pages:
        label = page.get("label") or ""
        if normalize_key(label).startswith("fctc"):
            continue
        tickers = match_announcement_issuer(label, variants)
        if tickers:
            pages_by_ticker[tickers[0]].append(page)
    return dict(pages_by_ticker)


def build_issuer_registry_snapshot(
    companies: list[dict[str, Any]], report_pages: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Photo vérifiable du référentiel, sans dater les introductions.

    L'année d'introduction reste ``NON_RECHERCHE`` tant qu'une source
    officielle ne l'a pas établie. On ne déduit ni une introduction ni un
    alias d'une simple ressemblance de nom.
    """
    variants = build_issuer_variant_map(companies)
    for alias, ticker in REPORT_LABEL_ALIASES.items():
        variants.setdefault(canonical_issuer_key(alias), ticker)
    aliases_by_ticker: dict[str, set[str]] = defaultdict(set)
    for alias, ticker in variants.items():
        aliases_by_ticker[ticker].add(alias)
    for alias, ticker in NEWS_TICKER_ALIASES.items():
        aliases_by_ticker[ticker].add(alias)
    pages_by_ticker = _report_pages_by_ticker(companies, report_pages)

    registry: list[dict[str, Any]] = []
    for company in companies:
        ticker = company["ticker"]
        annual_years = [
            document.get("exercice")
            for document in company.get("documents") or []
            if document.get("doc_type") in ANNUAL_DOC_PRIORITY
            and isinstance(document.get("exercice"), int)
        ]
        pages = pages_by_ticker.get(ticker, [])
        registry.append(
            {
                "ticker": ticker,
                "name": company.get("name"),
                "sector": company.get("sector"),
                "aliases_canoniques": sorted(aliases_by_ticker.get(ticker, set())),
                "report_pages": pages,
                "registry_status": "PAGE_RATTACHEE" if pages else "PAGE_OU_ALIAS_NON_RESOLU",
                "documents_indexes": len(company.get("documents") or []),
                "annual_document_min_exercice": min(annual_years) if annual_years else None,
                "annual_document_max_exercice": max(annual_years) if annual_years else None,
                "listing_year": None,
                "listing_year_status": EPS_STATUS_NOT_RESEARCHED,
            }
        )
    return registry


def build_eps_audit_matrix(
    companies: list[dict[str, Any]],
    report_pages: list[dict[str, str]],
    years: range = range(2016, 2026),
) -> list[dict[str, Any]]:
    """Grille initiale des observations BPA société-exercice.

    Cette première grille est volontairement conservatrice : tant que les
    documents candidats n'ont pas fait l'objet d'un audit BPA nominatif,
    une absence de valeur reste ``NON_RECHERCHE``, jamais une preuve de
    non-publication. L'applicabilité d'un exercice reste également non
    vérifiée tant que le référentiel des introductions n'est pas sourcé.
    """
    registry = {
        row["ticker"]: row
        for row in build_issuer_registry_snapshot(companies, report_pages)
    }
    rows: list[dict[str, Any]] = []
    for company in companies:
        ticker = company["ticker"]
        documents = company.get("documents") or []
        series_by_year = {
            entry.get("exercice"): entry.get("figures") or {}
            for entry in (company.get("fundamentals") or {}).get("series") or []
            if isinstance(entry.get("exercice"), int)
        }
        registry_row = registry.get(ticker) or {}
        for exercice in years:
            figures = series_by_year.get(exercice) or {}
            candidates = _annual_candidate_documents(documents, exercice)
            metrics = classify_eps_observation(
                figures,
                audit_completed=False,
                candidate_documents=len(candidates),
                previous_figures=series_by_year.get(exercice - 1) or {},
                exercice=exercice,
                ticker=ticker,
                eps_observations=(figures.get("benefice_par_action") or {}).get("_observations"),
            )
            if figures:
                documentary_status = "SERIE_EXTRAITE_POUR_EXERCICE"
            elif candidates:
                documentary_status = "DOCUMENTS_CANDIDATS_INDEXES_AUDIT_BPA_NON_TERMINE"
            elif exercice < 2019:
                documentary_status = EPS_STATUS_NOT_RESEARCHED
            elif not registry_row.get("report_pages"):
                documentary_status = "PAGE_OU_ALIAS_NON_RESOLU"
            else:
                documentary_status = "DOCUMENT_INTROUVABLE_DANS_INDEX_ACTUEL"
            rows.append(
                {
                    "ticker": ticker,
                    "company_name": company.get("name"),
                    "sector": company.get("sector"),
                    "exercice": exercice,
                    "applicabilite": "NON_VERIFIEE",
                    "statut_documentaire": documentary_status,
                    "documents_candidats": [
                        {
                            "label": document.get("label"),
                            "doc_type": document.get("doc_type"),
                            "exercice_document": document.get("exercice"),
                            "url": document.get("url"),
                        }
                        for document in candidates
                    ],
                    "serie_extraite": bool(figures),
                    "statut_bpa": metrics["status"],
                    "bpa_publie_fcfa": metrics["published_eps_fcfa"],
                    "bpa_recalcule_comparable_fcfa": metrics["recalculated_comparable_eps_fcfa"],
                    "bpa_part_groupe_ponderee_candidat_fcfa": metrics["parent_weighted_candidate_fcfa"],
                    "ratio_indicatif_fin_exercice_fcfa": metrics["indicative_result_per_end_share_fcfa"],
                    "numerator": metrics["numerator"],
                    "denominator": metrics["denominator"],
                    "inputs_confirmed_two_documents": metrics["inputs_confirmed_two_documents"],
                    "capital_structure_flags": metrics["capital_structure_flags"],
                    "capital_structure": metrics.get("capital_structure"),
                    "cross_check": metrics["cross_check"],
                    "arithmetic_checks": metrics.get("arithmetic_checks") or [],
                    "quarantine": metrics.get("quarantine"),
                    "published_candidate_groups": metrics.get("published_candidate_groups") or [],
                    "other_scope_candidate_groups": metrics.get("other_scope_candidate_groups") or [],
                    "published_selection": metrics.get("published_selection"),
                    "nonretained_eps_observations": metrics.get("nonretained_eps_observations") or [],
                }
            )
    return rows


def summarize_eps_audit_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Taux séparés par niveau de BPA et par dénominateur explicite."""
    total = len(rows)
    extracted_rows = [row for row in rows if row.get("serie_extraite")]

    def count(predicate) -> int:
        return sum(1 for row in rows if predicate(row))

    def rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator * 100, 3) if denominator else None

    published = count(lambda row: row.get("bpa_publie_fcfa") is not None)
    published_confirmed = count(
        lambda row: row.get("statut_bpa") == EPS_STATUS_PUBLISHED_CONFIRMED
    )
    recalculated = count(
        lambda row: row.get("bpa_publie_fcfa") is None
        and row.get("bpa_recalcule_comparable_fcfa") is not None
    )
    recalculated_confirmed = count(
        lambda row: row.get("statut_bpa") == EPS_STATUS_RECALCULATED_CONFIRMED
    )
    parent_candidate = count(
        lambda row: row.get("statut_bpa") == EPS_STATUS_PARENT_WEIGHTED_CANDIDATE
    )
    indicative = count(
        lambda row: row.get("statut_bpa") == EPS_STATUS_INDICATIVE_END_SHARES
    )
    quarantined = count(lambda row: row.get("quarantine") is not None)
    divergence_resolved = count(
        lambda row: row.get("statut_bpa") == EPS_STATUS_PUBLISHED_DIVERGENCE_RESOLVED
    )
    published_not_retained = count(
        lambda row: row.get("statut_bpa") == EPS_STATUS_PUBLISHED_NOT_RETAINED
    )
    capital_change_flagged = count(
        lambda row: bool((row.get("capital_structure") or {}).get("share_count_changes"))
    )
    verified_capital_events = count(
        lambda row: bool((row.get("capital_structure") or {}).get("verified_events_in_exercice"))
    )
    return {
        "cellules_brutes": total,
        "cellules_applicables_confirmees": None,
        "denominateur_series_extraites": len(extracted_rows),
        "bpa_publie": {
            "observations": published,
            "taux_sur_cellules_brutes_pct": rate(published, total),
            "taux_sur_series_extraites_pct": rate(published, len(extracted_rows)),
            "confirme_deux_documents": published_confirmed,
            "taux_confirme_sur_series_extraites_pct": rate(
                published_confirmed, len(extracted_rows)
            ),
        },
        "bpa_recalcule_comparable": {
            "observations_sans_bpa_publie": recalculated,
            "taux_sur_series_extraites_pct": rate(recalculated, len(extracted_rows)),
            "confirme_deux_documents": recalculated_confirmed,
        },
        "candidat_part_groupe_ponderee": {"observations": parent_candidate},
        "ratio_indicatif_fin_exercice_hors_couverture_bpa": {
            "observations": indicative
        },
        "bpa_publie_en_quarantaine_hors_couverture": {"observations": quarantined},
        "bpa_publie_divergence_resolue_par_controle": {"observations": divergence_resolved},
        "bpa_publie_non_ret retained_devise_composante_perimetre": {
            "observations": published_not_retained
        },
        "capital": {
            "changements_du_nombre_d_actions_signales": capital_change_flagged,
            "evenements_sources_dans_exercice": verified_capital_events,
        },
        "statuts_bpa": dict(Counter(row.get("statut_bpa") for row in rows)),
        "statuts_documentaires": dict(
            Counter(row.get("statut_documentaire") for row in rows)
        ),
        "par_exercice": {
            str(year): {
                "cellules": sum(1 for row in rows if row.get("exercice") == year),
                "series_extraites": sum(
                    1 for row in rows if row.get("exercice") == year and row.get("serie_extraite")
                ),
                "bpa_publie": sum(
                    1
                    for row in rows
                    if row.get("exercice") == year and row.get("bpa_publie_fcfa") is not None
                ),
            }
            for year in sorted({row.get("exercice") for row in rows})
        },
    }


def collect_fundamentals(session: requests.Session, companies: list[dict[str, Any]],
                         report_pages: list[dict[str, str]], cache_dir: Path) -> tuple[dict[str, int], list[str]]:
    docs_by_ticker, warnings = scrape_issuer_documents(session, report_pages, companies)
    counts = {
        "companies_with_documents": 0,
        "documents_indexed": 0,
        "companies_with_figures": 0,
        "companies_with_series_3y": 0,
        "figures_confirmed_two_docs": 0,
        "companies_with_operating_cashflow": 0,
        "companies_with_cash_debt_flow": 0,
        "companies_with_eps": 0,
        "companies_with_share_count": 0,
        "companies_with_eps_or_shares": 0,
        # Couverture par observation société-exercice : ne jamais agréger
        # ces niveaux de BPA dans le seul compteur historique par société.
        "eps_published_observations": 0,
        "eps_published_confirmed_observations": 0,
        "eps_recalculated_comparable_observations": 0,
        "eps_recalculated_confirmed_observations": 0,
        "eps_parent_weighted_candidate_observations": 0,
        "eps_indicative_end_share_observations": 0,
        "eps_published_quarantined_observations": 0,
        "eps_published_divergence_resolved_observations": 0,
        "eps_published_not_ret retained_observations": 0,
        "documents_rejected_other_issuer": 0,
        "documents_rejected_intermediate": 0,
        "documents_ocr_attempted": 0,
        "documents_ocr_used": 0,
        "documents_ocr_cache_hits": 0,
        "companies_with_ocr_figures": 0,
        "figures_ocr": 0,
        "documents_capital_supplement_attempted": 0,
        "documents_capital_supplement_used": 0,
        "figures_capital_supplemented": 0,
        "companies_with_capital_supplement": 0,
    }
    for company in companies:
        docs = docs_by_ticker.get(company["ticker"], [])
        company["documents"] = docs
        counts["documents_indexed"] += len(docs)
        if docs:
            counts["companies_with_documents"] += 1
        annual_candidates = [
            d for d in docs
            if d["doc_type"] in ANNUAL_DOC_PRIORITY
            and not str(d.get("selection_status") or "").startswith("EXCLU_")
            and isinstance(d.get("exercice"), int)
            and d["exercice"] >= 2020
        ]
        fundamentals: dict[str, Any] = {
            "status": "documents_indexes_sans_extraction",
            "figures": {},
            "series": [],
            "data_confidence": None,
            "notes": [],
        }
        if not annual_candidates:
            fundamentals["notes"] = ["Aucun état financier annuel identifiable dans les documents indexés."]
            company["fundamentals"] = fundamentals
            continue

        annual_candidates.sort(
            key=lambda d: (
                -d["exercice"],
                ANNUAL_DOC_PRIORITY[d["doc_type"]],
                0 if d.get("scope_hint") == "CONSOLIDE" else 2 if d.get("scope_hint") in {"INDIVIDUEL", "SOCIAL"} else 1,
                0 if d.get("framework_hint") == "IFRS" else 1,
            )
        )
        # Cinq exercices au plus. Pour chaque exercice, on essaie les
        # documents dans l'ordre de priorité jusqu'à obtenir au moins un
        # agrégat : un premier PDF scanné (par exemple la version SYSCOHADA)
        # ne doit pas masquer une version IFRS textuelle du même exercice
        # publiée le même jour. On s'arrête au premier document exploitable
        # afin de ne pas mélanger inutilement deux référentiels.
        candidates_by_exercice: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for candidate in annual_candidates:
            candidates_by_exercice[candidate["exercice"]].append(candidate)
        selected_exercices = sorted(candidates_by_exercice, reverse=True)[:5]
        # Jusqu'à six candidats classés par exercice : le pilote a montré que
        # le bon jeu complet Peut arriver après une attestation seule, un
        # état condensé et un document d'un autre périmètre.
        chosen_groups = [candidates_by_exercice[exercice][:6] for exercice in selected_exercices]
        latest_selected_exercice = selected_exercices[0] if selected_exercices else None

        observations: list[dict[str, Any]] = []
        attempt_notes: list[str] = []
        extraction_attempts: list[dict[str, Any]] = []
        capital_supplement_figures = 0
        capital_supplement_documents_used = 0
        latest_doc_info: dict[str, Any] | None = None
        per_share_observations: list[dict[str, Any]] = []
        document_fingerprints: list[dict[str, Any]] = []

        def record_document_result(doc: dict[str, Any], result: dict[str, Any], purpose: str) -> None:
            fingerprint = result.get("document")
            if isinstance(fingerprint, dict):
                document_fingerprints.append({**fingerprint, "purpose": purpose})
                rejection = fingerprint.get("selection_rejection")
                if rejection == "AUTRE_EMETTEUR_CONFIRME":
                    counts["documents_rejected_other_issuer"] += 1
                elif rejection == "INTERMEDIAIRE":
                    counts["documents_rejected_intermediate"] += 1
            detailed = result.get("per_share_observations") or {}
            for family in ("eps", "shares", "numerators", "ignored"):
                for item in detailed.get(family) or []:
                    if not isinstance(item, dict):
                        continue
                    record = dict(item)
                    record["family"] = family
                    record["purpose"] = purpose
                    record["document_url"] = doc.get("url")
                    record["document_label"] = doc.get("label")
                    record["document_sha256"] = result.get("sha256")
                    if isinstance(record.get("evidence"), dict):
                        record["evidence"] = {
                            **record["evidence"],
                            "document_url": doc.get("url"),
                            "document_label": doc.get("label"),
                            "document_sha256": result.get("sha256"),
                            "document_version_label": (fingerprint or {}).get("version_label"),
                            "extraction_method": (result.get("extraction") or {}).get("method"),
                        }
                    per_share_observations.append(record)

        def record_extraction_attempt(doc: dict[str, Any], result: dict[str, Any], purpose: str) -> dict[str, Any]:
            extraction_info = result.get("extraction") or {}
            ocr_info = extraction_info.get("ocr") or {}
            document_info = result.get("document") or {}
            extraction_attempts.append(
                {
                    "document_label": doc["label"],
                    "document_url": doc.get("url"),
                    "exercice": doc["exercice"],
                    "effective_exercice": result.get("effective_exercice"),
                    "content_exercice": result.get("content_exercice"),
                    "sha256": result.get("sha256"),
                    "version_label": document_info.get("version_label"),
                    "document_identity_status": (document_info.get("identity") or {}).get("status"),
                    "selection_rejection": document_info.get("selection_rejection"),
                    "period_kind": (document_info.get("period") or {}).get("period_kind"),
                    "purpose": purpose,
                    "method": extraction_info.get("method") or "texte_natif",
                    "ocr": ocr_info,
                }
            )
            if ocr_info.get("attempted"):
                counts["documents_ocr_attempted"] += 1
            if ocr_info.get("used"):
                counts["documents_ocr_used"] += 1
            if ocr_info.get("cache_status") == "hit":
                counts["documents_ocr_cache_hits"] += 1
            return ocr_info

        def append_observation(
            doc: dict[str, Any],
            column_index: int,
            target_exercice: int,
            key: str,
            figure: dict[str, Any],
            result: dict[str, Any] | None = None,
        ) -> None:
            first_evidence = (figure.get("evidence") or [{}])[0]
            document_info = (result or {}).get("document") or {}
            observations.append(
                {
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
                    "accounting_scope": figure.get("accounting_scope"),
                    "accounting_scope_source": figure.get("accounting_scope_source"),
                    "framework": figure.get("framework"),
                    "currency": figure.get("currency"),
                    "currency_source": figure.get("currency_source"),
                    "component": figure.get("component"),
                    "component_source": figure.get("component_source"),
                    "basis": figure.get("basis"),
                    "denominator_kind": figure.get("denominator_kind"),
                    "published_decimals": figure.get("published_decimals"),
                    "token_repair": figure.get("token_repair"),
                    "candidate_signature": figure.get("candidate_signature"),
                    "candidate_groups": figure.get("candidate_groups"),
                    "source_multiplier": figure.get("source_multiplier"),
                    "input_rounding_abs_fcfa": figure.get("input_rounding_abs_fcfa"),
                    "arithmetic_check": figure.get("arithmetic_check"),
                    "coherence_status": figure.get("coherence_status"),
                    "quarantine_reasons": figure.get("quarantine_reasons"),
                    "eps_metadata": figure.get("eps_metadata"),
                    "share_metadata": figure.get("share_metadata"),
                    "doc_exercice": (result or {}).get("effective_exercice") or doc["exercice"],
                    "doc_filename_exercice": doc.get("exercice"),
                    "doc_url": doc["url"],
                    "doc_label": doc["label"],
                    "doc_sha256": (result or {}).get("sha256"),
                    "doc_version_label": document_info.get("version_label"),
                    "doc_published_date": doc.get("published_date"),
                    "doc_identity_status": (document_info.get("identity") or {}).get("status"),
                    "page": first_evidence.get("page"),
                    "line": first_evidence.get("line"),
                    "evidence": figure.get("evidence") or [],
                }
            )
        for candidate_group in chosen_groups:
            primary_columns: dict[str, Any] | None = None
            primary_index: int | None = None
            primary_exercice: int | None = None
            for candidate_index, chosen in enumerate(candidate_group):
                try:
                    result = extract_annual_figures(
                        session,
                        chosen,
                        cache_dir,
                        expected_ticker=company["ticker"],
                        companies=companies,
                    )
                except Exception as exc:
                    attempt_notes.append(f"{chosen['label']} : extraction impossible ({exc}).")
                    continue
                record_extraction_attempt(chosen, result, "serie_annuelle")
                record_document_result(chosen, result, "serie_annuelle")
                columns = result.get("columns") or {}
                offset_columns = columns.get("colonnes") or {
                    "0": columns.get("courant") or {},
                    "1": columns.get("precedent") or {},
                }
                has_figures = any(
                    any(not key.startswith("_") for key in (values or {}))
                    for values in offset_columns.values()
                )
                effective_exercice = result.get("effective_exercice") or chosen["exercice"]
                if chosen["exercice"] == latest_selected_exercice and latest_doc_info is None and has_figures:
                    latest_doc_info = {
                        "url": chosen["url"],
                        "label": chosen["label"],
                        "doc_type": chosen["doc_type"],
                        "published_date": chosen["published_date"],
                        "sha256": result.get("sha256"),
                        "document": result.get("document"),
                        "extraction": result.get("extraction"),
                    }
                for raw_offset, values in offset_columns.items():
                    try:
                        column_index = int(raw_offset)
                    except (TypeError, ValueError):
                        continue
                    target_exercice = int(effective_exercice) - column_index
                    if target_exercice < 2019:
                        continue
                    for key, figure in (values or {}).items():
                        if key.startswith("_") or not isinstance(figure, dict):
                            continue
                        append_observation(chosen, column_index, target_exercice, key, figure, result)
                if has_figures:
                    primary_columns = columns
                    primary_index = candidate_index
                    primary_exercice = int(effective_exercice)
                    break
                attempt_notes.append(
                    f"{chosen['label']} : {result['notes'][0] if result['notes'] else 'aucun agrégat retenu.'}"
                )

            # Passe complémentaire strictement limitée au capital/BPA.
            # Le document principal reste la seule source des agrégats
            # monétaires de la série. Un autre document officiel du même
            # exercice ne Peut ajouter le BPA ou le nombre d'actions que
            # s'ils manquent dans le document principal et si les agrégats
            # centraux communs prouvent le même périmètre comptable.
            if primary_columns is not None and primary_index is not None and primary_exercice is not None:
                supplemented_by_target: dict[int, set[str]] = defaultdict(set)
                for supplement in candidate_group[primary_index + 1:]:
                    missing_by_column: list[tuple[int, str, int, list[str]]] = []
                    for column_index, column_name in ((0, "courant"), (1, "precedent")):
                        target_exercice = primary_exercice - column_index
                        if target_exercice < 2019:
                            missing: list[str] = []
                        else:
                            primary_figures = primary_columns.get(column_name) or {}
                            missing = [
                                key
                                for key in _missing_capital_keys(primary_figures)
                                if key not in supplemented_by_target[target_exercice]
                            ]
                        missing_by_column.append((column_index, column_name, target_exercice, missing))
                    if not any(missing for *_prefix, missing in missing_by_column):
                        break
                    counts["documents_capital_supplement_attempted"] += 1
                    try:
                        # Complément borné au texte natif : l'audit de la
                        # passe (19 documents représentatifs, 0 donnée
                        # ajoutée) a montré que déclencher un OCR complet
                        # pour un éventuel BPA coûte des minutes sans gain
                        # mesuré. Un BPA lu en OCR resterait en outre
                        # fragile (chiffres isolés, sans recoupement).
                        supplement_result = extract_annual_figures(
                            session,
                            supplement,
                            cache_dir,
                            allow_ocr=False,
                            expected_ticker=company["ticker"],
                            companies=companies,
                        )
                    except Exception as exc:
                        attempt_notes.append(
                            f"{supplement['label']} : passe complémentaire capital/BPA impossible ({exc})."
                        )
                        continue
                    record_extraction_attempt(supplement, supplement_result, "capital_bpa")
                    record_document_result(supplement, supplement_result, "capital_bpa")
                    supplement_columns = supplement_result.get("columns") or {}
                    supplement_offset_columns = supplement_columns.get("colonnes") or {
                        "0": supplement_columns.get("courant") or {},
                        "1": supplement_columns.get("precedent") or {},
                    }
                    supplement_effective_exercice = int(
                        supplement_result.get("effective_exercice") or supplement["exercice"]
                    )
                    added = 0
                    for _primary_column_index, column_name, target_exercice, missing in missing_by_column:
                        if not missing:
                            continue
                        primary_figures = primary_columns.get(column_name) or {}
                        supplement_column_index = supplement_effective_exercice - target_exercice
                        supplement_figures = supplement_offset_columns.get(
                            str(supplement_column_index)
                        ) or {}
                        if not supplement_figures:
                            continue
                        if not _figures_share_perimeter(primary_figures, supplement_figures):
                            continue
                        for key in missing:
                            figure = supplement_figures.get(key)
                            if not figure:
                                continue
                            append_observation(
                                supplement,
                                supplement_column_index,
                                target_exercice,
                                key,
                                figure,
                                supplement_result,
                            )
                            supplemented_by_target[target_exercice].add(key)
                            added += 1
                    if added:
                        counts["documents_capital_supplement_used"] += 1
                        counts["figures_capital_supplemented"] += added
                        capital_supplement_figures += added
                        capital_supplement_documents_used += 1
                        attempt_notes.append(
                            f"{supplement['label']} : {added} donnée(s) capital/BPA ajoutée(s) après "
                            "recoupement de périmètre avec le document principal du même exercice."
                        )

        merged, merge_notes = merge_series_observations(observations)
        series_list: list[dict[str, Any]] = []
        rejected_all: list[str] = []
        for exercice in sorted(merged, reverse=True):
            figures, rejected = apply_plausibility_filters(merged[exercice])
            # Garde-fou sectoriel : un bilan bancaire coté ne pèse pas quelques milliards.
            if company.get("sector") == "Services financiers":
                bilan = figures.get("total_bilan", {}).get("value_fcfa")
                if isinstance(bilan, int) and bilan < 50_000_000_000:
                    figures.pop("total_bilan", None)
                    rejected.append("Total du bilan écarté : ordre de grandeur incompatible avec un établissement financier coté.")
            figures, derived_notes = add_derived_financial_debt(figures)
            rejected.extend(derived_notes)
            rejected_all.extend(f"{exercice} — {note}" for note in rejected)
            if figures:
                series_list.append({"exercice": exercice, "figures": figures})

        series_list, hygiene_notes = series_hygiene(series_list)
        rejected_all.extend(hygiene_notes)
        confirmed = sum(
            1
            for entry in series_list
            for figure in entry["figures"].values()
            if figure.get("confidence") == "confirme_deux_documents"
        )
        counts["figures_confirmed_two_docs"] += confirmed
        ocr_figures = sum(
            1
            for entry in series_list
            for figure in entry["figures"].values()
            if "ocr" in str(figure.get("extraction_method") or "")
        )
        counts["figures_ocr"] += ocr_figures
        if ocr_figures:
            counts["companies_with_ocr_figures"] += 1
        figures_by_exercice = {
            entry["exercice"]: entry["figures"] for entry in series_list if isinstance(entry.get("exercice"), int)
        }
        try:
            verified_capital_events = load_verified_capital_events()
        except (OSError, ValueError, TypeError):
            verified_capital_events = []
        for entry in series_list:
            exercice = entry["exercice"]
            eps_metrics = derive_eps_metrics(
                entry["figures"],
                previous_figures=figures_by_exercice.get(exercice - 1) or {},
                exercice=exercice,
                ticker=company["ticker"],
                capital_events=verified_capital_events,
                eps_observations=[
                    item for item in per_share_observations
                    if item.get("family") == "eps" and item.get("target_exercice") == exercice
                ],
            )
            entry["eps_metrics"] = eps_metrics
            eps_figure = entry["figures"].get("benefice_par_action")
            if isinstance(eps_figure, dict):
                eps_figure["eps_status"] = eps_metrics["status"]
                eps_figure["eligible_for_ratios"] = eps_metrics["published_eps_fcfa"] is not None
                if eps_metrics.get("quarantine"):
                    eps_figure["quarantine"] = eps_metrics["quarantine"]
            if eps_metrics.get("quarantine"):
                counts["eps_published_quarantined_observations"] += 1
            if eps_metrics["status"] == EPS_STATUS_PUBLISHED_NOT_RETAINED:
                counts["eps_published_not_ret retained_observations"] += 1
            if eps_metrics["status"] == EPS_STATUS_PUBLISHED_DIVERGENCE_RESOLVED:
                counts["eps_published_divergence_resolved_observations"] += 1
            if eps_metrics["published_eps_fcfa"] is not None:
                counts["eps_published_observations"] += 1
                if eps_metrics["status"] == EPS_STATUS_PUBLISHED_CONFIRMED:
                    counts["eps_published_confirmed_observations"] += 1
            elif eps_metrics["recalculated_comparable_eps_fcfa"] is not None:
                counts["eps_recalculated_comparable_observations"] += 1
                if eps_metrics["status"] == EPS_STATUS_RECALCULATED_CONFIRMED:
                    counts["eps_recalculated_confirmed_observations"] += 1
            elif eps_metrics["parent_weighted_candidate_fcfa"] is not None:
                counts["eps_parent_weighted_candidate_observations"] += 1
            elif eps_metrics["indicative_result_per_end_share_fcfa"] is not None:
                counts["eps_indicative_end_share_observations"] += 1
        extraction_summary = {
            "methods": sorted({attempt.get("method") or "texte_natif" for attempt in extraction_attempts}),
            "documents_ocr_attempted": sum(1 for attempt in extraction_attempts if (attempt.get("ocr") or {}).get("attempted")),
            "documents_ocr_used": sum(1 for attempt in extraction_attempts if (attempt.get("ocr") or {}).get("used")),
            "documents_ocr_cache_hits": sum(
                1 for attempt in extraction_attempts if (attempt.get("ocr") or {}).get("cache_status") == "hit"
            ),
            "figures_ocr": ocr_figures,
            "documents_capital_supplement_attempted": sum(
                1 for attempt in extraction_attempts if attempt.get("purpose") == "capital_bpa"
            ),
            "documents_capital_supplement_used": capital_supplement_documents_used,
            "figures_capital_supplemented": capital_supplement_figures,
            "attempts": extraction_attempts,
        }
        if capital_supplement_figures:
            counts["companies_with_capital_supplement"] += 1
        years_with_result = sum(
            1 for entry in series_list if "resultat_net" in entry["figures"] or "resultat_net_part_groupe" in entry["figures"]
        )
        all_figure_keys = {key for entry in series_list for key in entry["figures"]}
        if "flux_tresorerie_operationnel" in all_figure_keys:
            counts["companies_with_operating_cashflow"] += 1
        if all_figure_keys & {
            "flux_tresorerie_operationnel",
            "investissements_immobilisations",
            "dividendes_verses",
            "tresorerie_equivalents",
            "tresorerie_passif",
            "tresorerie_nette",
            "dettes_financieres",
            "dettes_financieres_courantes",
            "dettes_financieres_non_courantes",
        }:
            counts["companies_with_cash_debt_flow"] += 1
        has_eps = "benefice_par_action" in all_figure_keys
        has_shares = bool(all_figure_keys & {"nombre_actions_fin_exercice", "nombre_actions_moyen_pondere"})
        if has_eps:
            counts["companies_with_eps"] += 1
        if has_shares:
            counts["companies_with_share_count"] += 1
        if has_eps or has_shares:
            counts["companies_with_eps_or_shares"] += 1
        if len(series_list) >= 3:
            counts["companies_with_series_3y"] += 1
        fundamentals["extraction_summary"] = extraction_summary
        fundamentals["per_share_observations"] = per_share_observations
        fundamentals["document_fingerprints"] = document_fingerprints
        if series_list:
            counts["companies_with_figures"] += 1
            # Confiance globale des données fondamentales de la société.
            if len(series_list) >= 4 and confirmed >= 4:
                data_confidence = "A"
            elif len(series_list) >= 3 and (confirmed >= 2 or years_with_result >= 3):
                data_confidence = "B"
            else:
                data_confidence = "C"
            latest_entry = series_list[0]
            latest_share_entry = next(
                (
                    entry for entry in series_list
                    if isinstance(entry["figures"].get("nombre_actions_fin_exercice", {}).get("value"), int)
                ),
                None,
            )
            if latest_share_entry:
                share_figure = latest_share_entry["figures"]["nombre_actions_fin_exercice"]
                company["shares_outstanding"] = share_figure["value"]
                company["shares_outstanding_exercice"] = latest_share_entry["exercice"]
                company["shares_outstanding_confidence"] = share_figure.get("confidence")
                company["shares_outstanding_source"] = (
                    "États financiers officiels publiés sur brvm.org — nombre d'actions de fin "
                    "d'exercice lu dans la série annuelle de la fiche"
                )
            fundamentals.update(
                {
                    "status": "serie_extraite_recoupements_automatiques" if confirmed else "extraction_automatique_a_confirmer",
                    "exercice": latest_entry["exercice"],
                    "document": latest_doc_info,
                    "figures": latest_entry["figures"],
                    "series": series_list,
                    "data_confidence": data_confidence,
                    "exercices_couverts": len(series_list),
                    "notes": attempt_notes + merge_notes + rejected_all,
                }
            )
            print(
                f"[SIGMA] Fondamentaux {company['ticker']} : {len(series_list)} exercice(s), "
                f"{confirmed} agrégat(s) confirmé(s) par deux documents, confiance {data_confidence}",
                file=sys.stderr,
            )
        else:
            fundamentals["notes"] = attempt_notes + merge_notes + rejected_all or [
                "Aucun agrégat annuel n'a passé les contrôles d'extraction."
            ]
        company["fundamentals"] = fundamentals
    return counts, warnings


def enrich_dividend_sustainability(companies: list[dict[str, Any]]) -> dict[str, int]:
    """Repères de couverture du dividende, calculés exercice par exercice.

    Le tableau BRVM publie un montant **net** par action. Les ratios ci-dessous
    sont donc libellés en conséquence : dividende net rapporté au BPA publié,
    et flux opérationnel rapporté à une distribution nette totale *calculée*
    (dividende net/action × nombre d'actions lu dans les états du même
    exercice). Ce ne sont ni le taux de distribution brut voté en assemblée,
    ni un montant de distribution publié tel quel par l'émetteur. Aucun ratio
    n'est produit si l'un des intrants du même exercice manque.
    """
    counts = {
        "companies_with_dividend_eps_ratio": 0,
        "companies_with_dividend_cash_coverage": 0,
        "companies_with_3y_dividend_cash_coverage": 0,
        "dividend_sustainability_rows": 0,
    }

    def figure_value(figures: dict[str, Any], key: str) -> float | None:
        figure = figures.get(key) or {}
        value = figure.get("value", figure.get("value_fcfa"))
        return float(value) if isinstance(value, (int, float)) else None

    def figure_confidence(figures: dict[str, Any], key: str) -> str | None:
        return (figures.get(key) or {}).get("confidence")

    for company in companies:
        series_by_year = {
            entry.get("exercice"): entry.get("figures") or {}
            for entry in (company.get("fundamentals") or {}).get("series") or []
            if isinstance(entry.get("exercice"), int)
        }
        annual_dividends = {
            entry.get("fiscal_year"): entry
            for entry in (company.get("dividend_history") or {}).get("annual") or []
            if isinstance(entry.get("fiscal_year"), int)
        }
        rows: list[dict[str, Any]] = []
        for exercice in sorted(set(series_by_year) & set(annual_dividends), reverse=True):
            dividend = annual_dividends[exercice].get("net_amount_fcfa")
            if not isinstance(dividend, (int, float)) or dividend <= 0:
                continue
            figures = series_by_year[exercice]
            eps = figure_value(figures, "benefice_par_action")
            shares_end = figure_value(figures, "nombre_actions_fin_exercice")
            shares_avg = figure_value(figures, "nombre_actions_moyen_pondere")
            shares = shares_end if shares_end else shares_avg
            shares_basis = (
                "nombre_actions_fin_exercice" if shares_end else "nombre_actions_moyen_pondere" if shares_avg else None
            )
            ocf = figure_value(figures, "flux_tresorerie_operationnel")
            capex = figure_value(figures, "investissements_immobilisations")
            result = figure_value(figures, "resultat_net_part_groupe")
            result_basis = "resultat_net_part_groupe" if result is not None else None
            if result is None:
                result = figure_value(figures, "resultat_net")
                result_basis = "resultat_net" if result is not None else None

            total_net_distribution = None
            if shares and shares > 0:
                total_net_distribution = int(round(float(dividend) * shares))
            eps_ratio = round(float(dividend) / eps * 100, 2) if eps and eps > 0 else None
            result_ratio = (
                round(total_net_distribution / result * 100, 2)
                if total_net_distribution and result and result > 0
                else None
            )
            if result_ratio is not None and result_ratio > 1000:
                # Au-delà, l'écart signale presque toujours une rupture
                # d'échelle dans le résultat lu plutôt qu'une distribution
                # exceptionnelle documentée : ne pas publier le ratio.
                result_ratio = None
            cash_coverage = (
                round(ocf / total_net_distribution, 3)
                if ocf is not None and total_net_distribution
                else None
            )
            flow_after_capex = int(round(ocf + capex)) if ocf is not None and capex is not None else None
            after_capex_coverage = (
                round(flow_after_capex / total_net_distribution, 3)
                if flow_after_capex is not None and total_net_distribution
                else None
            )
            next_year_figures = series_by_year.get(exercice + 1) or {}
            dividends_paid_next = figure_value(next_year_figures, "dividendes_verses")
            if eps_ratio is None and cash_coverage is None and result_ratio is None:
                continue
            rows.append(
                {
                    "exercice": exercice,
                    "dividende_net_par_action_fcfa": float(dividend),
                    "benefice_par_action_fcfa": eps,
                    "benefice_par_action_confidence": figure_confidence(figures, "benefice_par_action"),
                    "dividende_net_sur_bpa_pct": eps_ratio,
                    "nombre_actions": int(shares) if shares else None,
                    "nombre_actions_basis": shares_basis,
                    "nombre_actions_confidence": figure_confidence(figures, shares_basis) if shares_basis else None,
                    "distribution_nette_totale_calculee_fcfa": total_net_distribution,
                    "resultat_net_fcfa": int(result) if result is not None else None,
                    "resultat_net_basis": result_basis,
                    "distribution_nette_sur_resultat_pct": result_ratio,
                    "flux_tresorerie_operationnel_fcfa": int(ocf) if ocf is not None else None,
                    "flux_tresorerie_operationnel_confidence": figure_confidence(figures, "flux_tresorerie_operationnel"),
                    "couverture_flux_operationnel_x": cash_coverage,
                    "investissements_immobilisations_fcfa": int(capex) if capex is not None else None,
                    "flux_apres_investissements_fcfa": flow_after_capex,
                    "couverture_apres_investissements_x": after_capex_coverage,
                    "dividendes_verses_exercice_suivant_fcfa": (
                        int(abs(dividends_paid_next)) if dividends_paid_next is not None else None
                    ),
                }
            )

        years_eps = sum(1 for row in rows if row["dividende_net_sur_bpa_pct"] is not None)
        years_cash = sum(1 for row in rows if row["couverture_flux_operationnel_x"] is not None)
        company["dividend_sustainability"] = {
            "status": "reperes_calculables" if rows else "non_calculable",
            "basis": "dividende_net_par_action_brvm_et_etats_financiers_du_meme_exercice",
            "method": (
                "Dividende net/action BRVM de l'exercice rapporté au BPA publié ; distribution nette totale "
                "calculée avec le nombre d'actions du même exercice ; couverture = flux de trésorerie "
                "opérationnel / distribution nette totale calculée. Le dividende BRVM étant net, ces repères "
                "ne sont pas le taux de distribution brut voté."
            ),
            "rows": rows,
            "years_with_eps_ratio": years_eps,
            "years_with_cash_coverage": years_cash,
        }
        if rows:
            history = company.get("dividend_history") or {}
            history["payout_ratio_status"] = (
                "dividende_net_sur_bpa_calculable_pas_taux_brut_officiel"
                if years_eps
                else "couverture_flux_calculable_sans_bpa_publie"
            )
            company["dividend_history"] = history
        counts["dividend_sustainability_rows"] += len(rows)
        if years_eps:
            counts["companies_with_dividend_eps_ratio"] += 1
        if years_cash:
            counts["companies_with_dividend_cash_coverage"] += 1
        if years_cash >= 3:
            counts["companies_with_3y_dividend_cash_coverage"] += 1
    return counts


def parse_sgi_page(html: str, page_url: str) -> list[dict[str, Any]]:
    """Annuaire officiel BRVM des SGI : nom, pays, contacts. Aucun tarif publié."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, Any]] = []
    for row in soup.select(".view-sgi .views-row"):
        field = row.select_one(".views-field-nothing .field-content")
        if field is None:
            continue
        header = field.find("div", recursive=False)
        if header is None:
            continue
        country = clean_text(" ".join(header.get("class") or [])) or None
        name = clean_text(header.get_text(" ", strip=True))
        if not name:
            continue

        def field_text(css_class: str) -> str | None:
            node = field.select_one(f".{css_class}")
            return clean_text(node.get_text(" ", strip=True)) if node else None

        website = field_text("site_sgi") or None
        if website and not website.startswith(("http://", "https://")):
            website = f"https://{website}"
        phone = field_text("tel_sgi")
        country_basis = "drapeau_publie_par_la_brvm" if country else None
        if not country and phone:
            dialing = {
                "221": "Sénégal", "223": "Mali", "225": "Côte d'Ivoire", "226": "Burkina Faso",
                "227": "Niger", "228": "Togo", "229": "Bénin", "245": "Guinée-Bissau",
            }
            digits = re.sub(r"\D", "", phone)
            for code, label in dialing.items():
                if digits.startswith(code):
                    country = label
                    country_basis = "indicatif_telephonique_publie"
                    break
        results.append(
            {
                "name": name,
                "country": country,
                "country_basis": country_basis,
                "address": field_text("adresse_sgi"),
                "email": field_text("email_sgi"),
                "phone": field_text("tel_sgi"),
                "website": website,
                "source_url": page_url,
                "fees_status": "non_publies_par_la_brvm",
            }
        )
    return results


def scrape_sgis(session: requests.Session, max_pages: int = 15) -> list[dict[str, Any]]:
    sgis: dict[str, dict[str, Any]] = {}
    for page_number in range(max_pages):
        page_url = URLS["sgis"] if page_number == 0 else f"{URLS['sgis']}?page={page_number}"
        page_items = parse_sgi_page(str(fetch(session, page_url)), page_url)
        if not page_items:
            break
        new_items = 0
        for item in page_items:
            key = normalize_key(item["name"])
            if key.startswith("sgi "):
                key = key[4:]
            if key not in sgis:
                sgis[key] = item
                new_items += 1
        if new_items == 0:
            break
    if not sgis:
        raise ValueError("Annuaire officiel des SGI illisible sur brvm.org.")
    return sorted(sgis.values(), key=lambda item: (item.get("country") or "", item["name"].lower()))


# --- Tarifs SGI homologués (AMF-UMOA, anciennement CREPMF) -------------------
# Chaîne de provenance : l'index tiers Richbourse sert uniquement à découvrir
# les PDF officiels (décision d'homologation + grille annexée). SIGMA relit
# chaque PDF, vérifie autorité / numéro / date / nom de la SGI dans le
# document, puis extrait les rubriques normalisées en gardant le texte tarifaire
# verbatim. La transcription de l'index n'est jamais publiée comme source
# primaire : elle sert de second lecteur (recoupement affiché par rubrique).
# Les tarifs homologués sont des PLAFONDS négociables, pas des prix facturés.

RICHBOURSE_TARIFFS_URL = "https://www.richbourse.com/common/apprendre/tarif-sgi"
BRVM_MARKET_FEES_URL = "https://www.brvm.org/fr/node/312"

SGI_TARIFF_RUBRIQUES: list[dict[str, Any]] = [
    {"key": "courtage_ordinaire", "label": "Courtage — transactions ordinaires", "required": ("courtage",), "excluded": ("dossier", "retrocession", "reglement", "valorisation", "achete")},
    {"key": "courtage_sur_dossier", "label": "Courtage — transactions sur dossier", "required": ("courtage", "dossier"), "excluded": ("retrocession",)},
    {"key": "conservation", "label": "Conservation des titres (droits de garde)", "required": ("conservation",), "excluded": ()},
    {"key": "tenue_de_compte", "label": "Tenue de compte", "required": ("tenue de compte",), "excluded": ()},
    {"key": "structuration_arrangement", "label": "Structuration / arrangement (marché primaire)", "required": ("structuration",), "excluded": ()},
    {"key": "placement_titres", "label": "Placement de titres (marché primaire)", "required": ("placement de titres",), "excluded": ("garantie",)},
    {"key": "garantie_placement", "label": "Garantie de placement — prise ferme (marché primaire)", "required": ("garantie de placement",), "excluded": ()},
    {"key": "introduction_bourse", "label": "Introduction en bourse (forfait)", "required": ("introduction en bourse",), "excluded": ()},
    {"key": "gestion_sous_mandat", "label": "Gestion sous mandat", "required": ("gestion sous mandat",), "excluded": ()},
    {"key": "ouverture_de_compte", "label": "Ouverture de compte", "required": ("ouverture de compte",), "excluded": ()},
    {"key": "cloture_de_compte", "label": "Clôture de compte", "required": ("cloture de compte",), "excluded": ()},
    {"key": "transfert_titres", "label": "Transfert de titres", "required": ("transfert",), "excluded": ()},
    {"key": "nantissement_titres", "label": "Nantissement de titres", "required": ("nantissement",), "excluded": ()},
    {"key": "contrat_liquidite", "label": "Animation / contrat de liquidité", "required": ("liquidite",), "excluded": ()},
]
SGI_TARIFF_RUBRIQUE_LABELS = {item["key"]: item["label"] for item in SGI_TARIFF_RUBRIQUES}
SGI_TARIFF_ORDER = {item["key"]: index for index, item in enumerate(SGI_TARIFF_RUBRIQUES)}
SGI_TARIFF_FORFAIT_KEYS = {
    "introduction_bourse",
    "tenue_de_compte",
    "ouverture_de_compte",
    "cloture_de_compte",
    "transfert_titres",
    "nantissement_titres",
}
# Variantes de noms connues entre annuaire BRVM et index/décisions (clé normalisée
# de l'index -> clé normalisée de l'annuaire). Toute entrée doit rester explicite :
# un rattachement douteux part en liste « non rattachées », jamais fusionné en silence.
SGI_NAME_ALIASES: dict[str, str] = {
    "nsia capital": "nsia finance",
    "images finances internationales": "image finances internationales",
    "sirius capital for africa": "sirius capital",
    "societe africaine dingenierie et dintermediation financiere sa2if": (
        "societe africaine d ingenierie et d intermediation financieres sa2if"
    ),
    # Ancienne dénomination officielle (site Société Générale : « Initially known
    # as Sogebourse » ; changement de dénomination sociale de 2018).
    "sogebourse": "societe generale capital securities west africa",
    "sgcswa": "societe generale capital securities west africa",
    # Nom court officiel : « Compagnie d'ingénierie financière et d'assistance
    # en bourse (CIFA BOURSE) » (communiqués de la société, Bamako).
    "cifa bourse": "compagnie d ingenierie financiere et d assistance en bourse",
    # Ancienne dénomination (changement de dénomination sociale de 2019,
    # annonce légale de la société) : SGI AFRICAINE DE BOURSE -> ASWA.
    "africaine de bourse": "attijari securities west africa",
    # Même entité ivoirienne récente (hors annuaire BRVM à ce jour) : formes
    # « (OAM CI) » des index et « Côte d’Ivoire » des décisions.
    "one africa markets oam ci": "one africa markets",
    "one africa markets cote d ivoire": "one africa markets",
}

_PCT_PATTERN = re.compile(r"(\d+(?:[.,]\d{1,4})?)\s*[._-]?\s*(?:%|°\s*/\s*o\b|°lo\b|0/0)")
_FCFA_AMOUNT_PATTERN = re.compile(r"(\d[\d\s  ]{1,15}?)\s*(?:F\s*CFA|FCFA)", flags=re.I)
_RATE_HINT_WORDS = ("maximum", "gratuit", "neant", "forfait", "tranche", "fcfa")
_BASE_HINT_WORDS = ("Montant", "valeur", "forfait")
_BASE_PHRASE_PATTERN = re.compile(
    r"(Montant[^·]{0,45}?|Valeur[^·]{0,45}?|Forfait[^·]{0,30}?)(?=\s*(?:Maximum|Minimum|\[?\d|Gratuit|Néant|$))",
    flags=re.I,
)


def _sgi_match_key(name: str | None) -> str:
    key = normalize_key(name or "")
    for prefix in ("sgi ", "la sgi "):
        if key.startswith(prefix):
            key = key[len(prefix):]
    for suffix in (" sgi", " sa"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    key = " ".join(key.split())
    return SGI_NAME_ALIASES.get(key, key)


def _edit_distance_at_most_one(first: str, second: str) -> bool:
    if abs(len(first) - len(second)) > 1:
        return False
    if len(first) == len(second):
        return sum(1 for x, y in zip(first, second) if x != y) <= 1
    short, long_ = (first, second) if len(first) < len(second) else (second, first)
    index_short = index_long = 0
    skipped = False
    while index_short < len(short) and index_long < len(long_):
        if short[index_short] == long_[index_long]:
            index_short += 1
            index_long += 1
        elif not skipped:
            skipped = True
            index_long += 1
        else:
            return False
    return True


def _sgi_names_match(first: str | None, second: str | None) -> bool:
    a, b = _sgi_match_key(first), _sgi_match_key(second)
    if not a or not b:
        return False
    if a == b:
        return True

    def _singular(tokens: list[str]) -> set[str]:
        # Tolérance bornée aux pluriels d'orthographe (FINANCIERE/FINANCIERES,
        # FINANCE/FINANCES) entre sources officielles : un « s » final sur les
        # mots longs uniquement, jamais sur les acronymes courts.
        return {token[:-1] if len(token) > 4 and token.endswith("s") else token for token in tokens}

    tokens_a, tokens_b = _singular(a.split()), _singular(b.split())
    smaller, bigger = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    if smaller and smaller <= bigger:
        return len(smaller) >= 2 or len(next(iter(smaller))) >= 4
    # Tolérance OCR bornée : un seul mot différent, à une lettre près, mot long
    # (ex. ATTUJARI lu pour ATTIJARI). Jamais deux écarts, jamais de mot court.
    if len(tokens_a) == len(tokens_b) and len(tokens_a) >= 2:
        only_a = tokens_a - tokens_b
        only_b = tokens_b - tokens_a
        if len(only_a) == 1 and len(only_b) == 1:
            token_a = next(iter(only_a))
            token_b = next(iter(only_b))
            return len(token_a) >= 5 and _edit_distance_at_most_one(token_a, token_b)
    return False


def _tariff_rubrique_key(normalized_text: str) -> str | None:
    for rubrique in sorted(
        SGI_TARIFF_RUBRIQUES,
        key=lambda item: -sum(len(token) for token in item["required"]),
    ):
        if all(token in normalized_text for token in rubrique["required"]) and not any(
            token in normalized_text for token in rubrique["excluded"]
        ):
            return str(rubrique["key"])
    return None


# Bornes de plausibilité des plafonds en pourcentage, par famille de rubrique.
# Les grilles homologuées UEMOA relues affichent au plus ~1,8 % de courtage et
# ~1 %/an de conservation ; au-delà de la borne, la « valeur » est presque
# toujours un artefact OCR (virgule perdue : 0,25 lu 25 ; TVA 18 % citée dans
# le texte). La valeur écartée n'est jamais corrigée ni devinée : le texte
# brut de la rubrique reste affiché intégralement, seul le résumé chiffré
# (« plafond lu ») s'abstient.
_SGI_TARIFF_PERCENT_MAX_FLOW = 3.0
_SGI_TARIFF_PERCENT_MAX_PRIMARY = 10.0
_SGI_TARIFF_PRIMARY_KEYS = {
    "placement_titres",
    "garantie_placement",
    "structuration_arrangement",
    "introduction_bourse",
    "gestion_sous_mandat",
    "contrat_liquidite",
}


def parse_tariff_rate_text(rate_text: str | None, rubrique_key: str | None) -> dict[str, Any]:
    """Lecture prudente d'un texte tarifaire : bornes et forfaits seulement si lisibles."""
    text = " ".join((rate_text or "").split())
    normalized = normalize_key(text)
    percent_max = (
        _SGI_TARIFF_PERCENT_MAX_PRIMARY
        if rubrique_key in _SGI_TARIFF_PRIMARY_KEYS
        else _SGI_TARIFF_PERCENT_MAX_FLOW
    )
    percents: list[float] = []
    for match in _PCT_PATTERN.finditer(text):
        try:
            value = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if 0 <= value <= percent_max:
            percents.append(round(value, 4))
    range_match = re.search(
        r"(\d+(?:[.,]\d{1,4})?)\s*(?:%|°\s*/\s*o)\s*[-–]\s*(\d+(?:[.,]\d{1,4})?)\s*(?:%|°\s*/\s*o)",
        text,
    )
    forfait_amounts: list[int] = []
    if rubrique_key in SGI_TARIFF_FORFAIT_KEYS:
        for match in _FCFA_AMOUNT_PATTERN.finditer(text):
            digits = re.sub(r"\D", "", match.group(1))
            if digits:
                amount = int(digits)
                if 0 < amount < 10_000_000_000:
                    forfait_amounts.append(amount)
    period = None
    if "trimestre" in normalized:
        period = "par trimestre"
    elif "par an" in normalized or "annuel" in normalized or "/ an" in normalized:
        period = "par an"
    elif "par mois" in normalized or "mensuel" in normalized:
        period = "par mois"
    return {
        "percents": percents,
        "percent_min": min(percents) if percents else None,
        "percent_max": max(percents) if percents else None,
        "is_range": bool(range_match) or (len(set(percents)) > 1 and "-" in text),
        "is_maximum": "maximum" in normalized,
        "forfait_fcfa": forfait_amounts,
        "period": period,
        "is_free": "gratuit" in normalized or "neant" in normalized,
    }


def parse_richbourse_tariff_rows(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        link = tr.find("a", href=re.compile(r"afficher-tarifs-sgi/"))
        if link is None:
            continue
        cells = [" ".join(td.get_text(" ").split()) for td in tr.find_all(["td", "th"])]
        if len(cells) < 5:
            continue
        href = str(link.get("href") or "")
        doc_ref = href.rstrip("/").rsplit("/", 1)[-1]
        doc_url = href if href.startswith("http") else f"https://www.richbourse.com{href}"
        sgi_name = re.sub(r"\s*Document officiel\s*$", "", cells[0]).strip()
        rows.append(
            {
                "sgi_name": sgi_name,
                "group": cells[1],
                "rubrique_text": cells[2],
                "base_text": cells[3],
                "rate_text": cells[4],
                "doc_ref": doc_ref,
                "doc_url": doc_url,
            }
        )
    return rows


def collect_richbourse_tariff_index(
    session: requests.Session, max_pages: int = 15
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Index de découverte uniquement : documents + transcription de recoupement."""
    warnings: list[str] = []
    try:
        session.get("https://www.richbourse.com/", timeout=30)
    except Exception:
        pass
    documents: dict[str, dict[str, Any]] = {}
    seen_row_keys: set[tuple[str, str]] = set()
    for page_number in range(1, max_pages + 1):
        try:
            response = session.get(
                RICHBOURSE_TARIFFS_URL, params={"page": page_number}, timeout=45
            )
            response.raise_for_status()
        except Exception as exc:
            warnings.append(f"Index tarifaire Richbourse page {page_number} indisponible ({exc}).")
            break
        rows = parse_richbourse_tariff_rows(response.text)
        new_rows = 0
        for row in rows:
            row_key = (row["doc_ref"], normalize_key(row["rubrique_text"]))
            if row_key in seen_row_keys:
                continue
            seen_row_keys.add(row_key)
            new_rows += 1
            document = documents.setdefault(
                row["doc_ref"],
                {"doc_ref": row["doc_ref"], "doc_url": row["doc_url"], "index_sgi_name": row["sgi_name"], "rows": []},
            )
            document["rows"].append(row)
        if not rows or new_rows == 0:
            break
        time.sleep(0.3)
    return documents, warnings


_DECISION_NUMBER_PATTERNS = (
    (re.compile(r"PAMF\s*-\s*UMOA\s*/\s*(20\d{2})\s*/\s*(\d{1,4})", flags=re.I), "pamf"),
    (re.compile(r"PCR\s*/\s*(SG\s*/\s*)?(DA\s*/\s*)?(20\d{2})\s*/\s*(\d{1,4})", flags=re.I), "pcr"),
    (re.compile(r"CREPMF\s*/\s*(20\d{2})\s*/\s*(\d{1,4})", flags=re.I), "crepmf"),
)


def _find_decision_number(text: str) -> str | None:
    """Numéro de la décision elle-même, jamais celui d'un visa cité dans le corps.

    Les visas citent d'autres décisions (agrément, règlement général…) : le numéro
    n'est retenu que dans le bloc titre (début du document) ou immédiatement suivi
    de la mention d'homologation des tarifs.
    """

    def format_number(match: re.Match[str], kind: str) -> str | None:
        # Rejet des lectures tronquées : un numéro suivi de débris OCR (« 2024 / 1_ »,
        # « 2024/0© »…) ou réduit à un seul chiffre n'est pas une preuve. Mieux vaut
        # « numéro illisible » qu'une fausse référence publiée comme vérifiée.
        following = text[match.end() : match.end() + 4]
        if re.search(r"[\d_©]", following):
            return None
        if kind == "pamf":
            value = int(match.group(2))
            return f"PAMF-UMOA/{match.group(1)}/{value}" if value >= 10 else None
        if kind == "crepmf":
            value = int(match.group(2))
            return f"CREPMF/{match.group(1)}/{value}" if value >= 1 else None
        value = int(match.group(4))
        if value < 1:
            return None
        middle = ("SG/" if match.group(1) else "") + ("DA/" if match.group(2) else "")
        return f"PCR/{middle}{match.group(3)}/{value}"

    # Garde « visas » : aucun numéro situé après le premier « Vu … » ne peut être
    # celui de la décision elle-même (les visas citent agrément et textes cadres).
    visa_match = re.search(r"\bVu\s+(?:la|le|l|les)\b", text)
    visa_start = visa_match.start() if visa_match else len(text)
    title_zone = text[: min(900, visa_start)]
    for pattern, kind in _DECISION_NUMBER_PATTERNS:
        match = pattern.search(title_zone)
        if match:
            formatted = format_number(match, kind)
            if formatted:
                return formatted
    normalized_full = normalize_key(text)
    for pattern, kind in _DECISION_NUMBER_PATTERNS:
        for match in pattern.finditer(text):
            if match.start() >= visa_start:
                continue
            following = normalized_full[match.end() : match.end() + 240]
            if "homologation des tarifs" in following:
                formatted = format_number(match, kind)
                if formatted:
                    return formatted
    return None


def parse_tariff_decision_header(raw_text: str) -> dict[str, Any]:
    text = " ".join((raw_text or "").split())
    # L'OCR espace parfois les chiffres du jour (« 2 6 JUIN 2026 ») : recoller
    # uniquement juste avant un nom de mois, jamais ailleurs.
    text = re.sub(
        r"\b(\d)\s+(\d)\s+(?=(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\b)",
        r"\1\2 ",
        text,
        flags=re.I,
    )
    normalized = normalize_key(text)
    number = _find_decision_number(text)
    decision_date = None
    date_match = re.search(
        r"Fait à [^,]{0,40},\s*le\s+(\d{1,2}(?:er)?\s+[A-Za-zÀ-ÿ]+\s+(?:20)\d{2})",
        text,
        flags=re.I,
    )
    if date_match:
        decision_date = parse_french_long_date(date_match.group(1))
    if decision_date is None:
        # Date numérique acceptée uniquement près de « Fait à » ou dans le bloc titre
        # (avant les visas) : sinon on lirait la date d'un texte cité, pas la décision.
        visa_match = re.search(r"\bVu\s+(?:la|le|l|les)\b", text)
        zones = [text[: visa_match.start() if visa_match else 900]]
        fait_match = re.search(r"Fait à", text)
        if fait_match:
            zones.append(text[fait_match.start() : fait_match.start() + 120])
        for zone in zones:
            numeric = re.search(r"\b(?:du|le)\s+(\d{2})/(\d{2})/((?:20)\d{2})\b", zone)
            if numeric:
                decision_date = f"{numeric.group(3)}-{numeric.group(2)}-{numeric.group(1)}"
                break
            long_in_zone = parse_french_long_date(zone)
            if long_in_zone and fait_match and zone.startswith("Fait"):
                decision_date = long_in_zone
                break
    sgi_name_pdf = None
    name_match = re.search(
        r"HOMOLOGATION DES TARIFS DE LA SGI\s+([A-Z0-9][A-Z0-9 &'’.\-]{2,60}?)(?=\s+(?:Le|La|Vu)\b|\s{2,}|$)",
        text,
    )
    if name_match:
        candidate = " ".join(name_match.group(1).split()).strip(" .")
        if 3 <= len(candidate) <= 60:
            sgi_name_pdf = candidate
    approval = None
    approval_match = re.search(r"(?:numéro|n°)\s*SGI\s*/\s*(\d{4}\s*-\s*\d+)", text, flags=re.I) or re.search(
        r"\bSGI\s*/\s*(\d{4}\s*-\s*\d+)", text
    )
    if approval_match:
        approval = re.sub(r"\s+", "", approval_match.group(1))
    authority = None
    if "autorite des marches financiers" in normalized or "pamf umoa" in normalized:
        authority = "AMF-UMOA"
    elif "conseil regional de l epargne" in normalized or "crepmf" in normalized or "pcr" in normalized:
        authority = "CREPMF (devenu AMF-UMOA)"
    # Type d'acteur visé par la décision : les index BRVM mélangent les
    # homologations des SGI et celles d'autres intervenants (SGO/SGP, banques
    # teneurs de comptes BTCC, SICAV). Seules les SGI concernent ce module.
    actor_match = re.search(
        r"tarifs (?:de|applicables par) la (sgi|sgo|sgp|btcc|sicav)\b", normalized
    )
    return {
        "decision_number": number,
        "decision_date": decision_date,
        "sgi_name_pdf": sgi_name_pdf,
        "approval_number": approval,
        "authority": authority,
        "mentions_homologation": "homologation" in normalized,
        "actor_kind": actor_match.group(1).upper() if actor_match else None,
    }


def _is_rate_line(line_text: str) -> bool:
    normalized = normalize_key(line_text)
    return bool(_PCT_PATTERN.search(line_text)) or any(word in normalized for word in _RATE_HINT_WORDS)


def extract_tariff_rates_from_lines(
    pages: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Extraction des rubriques depuis les lignes structurées d'un PDF tarifaire.

    Les grilles annexées ont des cellules multilignes dont l'ordre de lecture
    intercale rubrique, base et taux ; chaque ligne tarifaire est donc rattachée
    à la rubrique la plus proche, et le texte brut est conservé avec la page.
    """
    flat: list[tuple[int, str]] = []
    for page in pages:
        page_number = int(page.get("page_number") or 0)
        for entry in page.get("lines") or []:
            line_text = " ".join(str(entry.get("text") or "").split())
            if line_text:
                flat.append((page_number, line_text))
    if not flat:
        return {}
    annex_start = 0
    for index, (_, line_text) in enumerate(flat):
        normalized = normalize_key(line_text)
        if ("rubriques" in normalized and ("base" in normalized or "taux" in normalized)) or (
            "conditions generales de tarification" in normalized
        ):
            annex_start = index
            break
    # Toutes les lignes-libellés (y compris occurrences répétées) servent d'ancres :
    # elles ne doivent jamais devenir le « taux » d'une autre rubrique. Le libellé
    # « courtage sur transaction / sur dossier » est souvent coupé sur deux lignes.
    label_candidates: list[tuple[int, str]] = []
    for index in range(annex_start, len(flat)):
        line_text = flat[index][1]
        normalized_line = normalize_key(line_text)
        alpha = [char for char in line_text if char.isalpha()]
        is_section_header = (
            len(line_text) > 20
            and len(alpha) >= 12
            and sum(1 for char in alpha if char.isupper()) / len(alpha) > 0.85
        )
        if is_section_header:
            continue
        key = _tariff_rubrique_key(normalized_line)
        if key == "courtage_ordinaire":
            # « … sur transaction / sur dossier » coupé en deux lignes : ne bascule
            # que si aucun autre libellé de courtage ne suit immédiatement (sinon la
            # ligne « dossier » appartient à la rubrique suivante, pas à celle-ci).
            following_courtage_label = any(
                "courtage" in normalize_key(flat[following][1])
                for following in (index + 1, index + 2, index + 3)
                if following < len(flat)
            )
            if not following_courtage_label:
                for following in (index + 1, index + 2):
                    if following < len(flat):
                        next_normalized = normalize_key(flat[following][1])
                        if (
                            "dossier" in next_normalized
                            and "courtage" not in next_normalized
                            and len(next_normalized) <= 60
                        ):
                            key = "courtage_sur_dossier"
                            break
        if key:
            label_candidates.append((index, key))
    matches: list[tuple[int, str]] = []
    for index, key in label_candidates:
        if all(existing_key != key for _, existing_key in matches):
            matches.append((index, key))
    rates: dict[str, dict[str, Any]] = {}
    match_indexes = [index for index, _ in matches]
    label_indexes = {index for index, _ in label_candidates}
    market_fee_hints = ("retrocession", "reglement/livraison", "reglement livraison", "en faveur", "faveur brvm", "faveur dc", "valorisation des actifs")
    for index, key in matches:
        fragments: list[str] = []
        for candidate in range(max(annex_start, index - 4), min(len(flat), index + 6)):
            line_text = flat[candidate][1]
            normalized_line = normalize_key(line_text)
            if candidate != index and candidate in label_indexes:
                continue
            if any(hint in normalized_line for hint in market_fee_hints):
                continue
            if not _is_rate_line(line_text) and not any(
                word in normalized_line for word in _BASE_HINT_WORDS
            ):
                continue
            distance = abs(candidate - index)
            if any(abs(candidate - other) < distance for other in match_indexes if other != index):
                continue
            fragments.append(line_text)
        joined = " · ".join(fragments)
        base_match = _BASE_PHRASE_PATTERN.search(joined)
        base_text = " ".join(base_match.group(1).split()) if base_match else None
        rate_text = joined
        if base_text:
            rate_text = rate_text.replace(base_match.group(1), " ", 1)
        # Retire le libellé de rubrique répété en tête du premier fragment.
        rate_text = re.sub(
            r"^(Commissions?|Frais)\s+de\s+[A-Za-zÀ-ÿ'’ /]{3,60}?(?=\s*(?:Maximum|Minimum|\[?\d))",
            "",
            rate_text,
            flags=re.I,
        )
        rate_text = " ".join(rate_text.split(" · ")[0].split()) if " · " not in rate_text else " · ".join(
            " ".join(part.split()) for part in rate_text.split(" · ") if part.strip(" .·")
        )
        rate_text = rate_text.strip(" .·")[:320]
        if not rate_text or not _is_rate_line(rate_text):
            continue
        Parsed = parse_tariff_rate_text(rate_text, key)
        rates[key] = {
            "key": key,
            "label": SGI_TARIFF_RUBRIQUE_LABELS[key],
            "base_text": base_text,
            "rate_text": rate_text,
            "page": flat[index][0] or None,
            **{f"Parsed_{field}": value for field, value in Parsed.items()},
        }
    return rates


def _native_pdf_pages(content: bytes) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                x_tolerance=1.5, y_tolerance=2, use_text_flow=False, keep_blank_chars=False
            )
            lines = structured_lines_from_words(words)
            pages.append(
                {
                    "page_number": page_number,
                    "lines": lines,
                    "text": "\n".join(str(entry.get("text") or "") for entry in lines),
                }
            )
    return pages


def process_sgi_tariff_pdf(
    session: requests.Session,
    doc_url: str,
    doc_ref: str,
    index_sgi_name: str,
    cache_dir: Path,
) -> dict[str, Any]:
    pdf_dir = cache_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    safe_ref = re.sub(r"[^A-Za-z0-9_-]+", "-", doc_ref)[:80] or "document"
    pdf_path = pdf_dir / f"{safe_ref}.pdf"
    content = pdf_path.read_bytes() if pdf_path.exists() else b""
    if not content.startswith(b"%PDF"):
        content = bytes(fetch(session, doc_url, binary=True))
        if not content.startswith(b"%PDF"):
            raise ValueError("le document relié n'est pas un PDF")
        pdf_path.write_bytes(content)
    native_pages = _native_pdf_pages(content)
    native_text = "\n".join(page["text"] for page in native_pages)
    combined_text = native_text
    header = parse_tariff_decision_header(native_text)
    rates = extract_tariff_rates_from_lines(native_pages)
    extraction_method = "texte_natif"
    header_incomplete = header["mentions_homologation"] and (
        header["decision_number"] is None or header["sgi_name_pdf"] is None
    )
    # L'annexe tarifaire est parfois scannée alors que la lettre de décision est en
    # texte natif (ou l'inverse) : l'absence de rubriques déclenche aussi l'OCR.
    need_ocr = (
        len(native_text.strip()) < 1200
        or header_incomplete
        or not rates
        or "courtage_ordinaire" not in rates
    ) and len(native_pages) <= 12
    if need_ocr:
        ocr_pages, _ocr_notes, ocr_metadata = ocr_pdf_pages(content, cache_dir)
        if ocr_pages:
            ocr_text = "\n".join(str(page.get("text") or "") for page in ocr_pages)
            combined_text = f"{native_text}\n{ocr_text}"
            ocr_header = parse_tariff_decision_header(ocr_text)
            for field, value in ocr_header.items():
                if header.get(field) in (None, False) and value not in (None, False):
                    header[field] = value
            ocr_rates = extract_tariff_rates_from_lines(ocr_pages)
            if len(ocr_rates) > len(rates):
                rates = ocr_rates
                extraction_method = "ocr_controle"
            elif ocr_metadata.get("pages_ocrees"):
                extraction_method = "texte_natif+ocr_entete"
    if header["mentions_homologation"] and header["decision_number"] and header["sgi_name_pdf"]:
        status = "decision_verifiee"
    elif header["mentions_homologation"] and (
        header["decision_number"]
        or any(
            marker in normalize_key(combined_text)
            for marker in ("Vu la", "Vu le", "le president", "fait a ")
        )
    ):
        status = "decision_partielle"
    elif rates:
        status = "grille_sans_decision_jointe"
    else:
        status = "document_illisible"
    if header["sgi_name_pdf"]:
        name_check = "confirme" if _sgi_names_match(header["sgi_name_pdf"], index_sgi_name) else "different_de_l_index"
    else:
        name_check = "non_verifie"
    return {
        "doc_ref": doc_ref,
        "doc_url": doc_url,
        "index_sgi_name": index_sgi_name,
        "status": status,
        "extraction_method": extraction_method,
        "name_check": name_check,
        "sha256": hashlib.sha256(content).hexdigest()[:16],
        **header,
        "rates": [rates[key] for key in sorted(rates, key=lambda item: SGI_TARIFF_ORDER[item])],
    }


def _number_lists_close(first: list[float], second: list[float]) -> bool:
    return len(first) == len(second) and all(abs(a - b) <= 0.01 for a, b in zip(sorted(first), sorted(second)))


def cross_check_tariff_rates(decision: dict[str, Any], index_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Recoupement PDF (primaire) vs transcription de l'index (second lecteur)."""
    index_by_key: dict[str, dict[str, Any]] = {}
    for row in index_rows:
        key = _tariff_rubrique_key(normalize_key(row["rubrique_text"]))
        if key and key not in index_by_key:
            index_by_key[key] = row
    checked = concordant = divergent = 0
    pdf_keys = set()
    for rate in decision["rates"]:
        key = rate["key"]
        pdf_keys.add(key)
        index_row = index_by_key.get(key)
        if index_row is None:
            rate["cross_check_status"] = "non_recoupe"
            rate["index_rate_text"] = None
            continue
        checked += 1
        index_Parsed = parse_tariff_rate_text(index_row["rate_text"], key)
        pdf_percents = [float(value) for value in rate.get("Parsed_percents") or []]
        index_percents = [float(value) for value in index_Parsed["percents"]]
        pdf_forfait = [int(value) for value in rate.get("Parsed_forfait_fcfa") or []]
        index_forfait = [int(value) for value in index_Parsed["forfait_fcfa"]]
        if (pdf_percents or index_percents) and _number_lists_close(pdf_percents, index_percents):
            status = "concordant"
        elif key in SGI_TARIFF_FORFAIT_KEYS and pdf_forfait and sorted(pdf_forfait) == sorted(index_forfait):
            status = "concordant"
        elif (pdf_percents and index_percents and set(pdf_percents) & set(index_percents)) or (
            pdf_forfait and index_forfait and set(pdf_forfait) & set(index_forfait)
        ):
            status = "partiellement_concordant"
        else:
            status = "divergent"
        if status == "concordant":
            concordant += 1
        elif status == "divergent":
            divergent += 1
        rate["cross_check_status"] = status
        rate["index_rate_text"] = index_row["rate_text"]
    index_only = [
        {"key": key, "label": SGI_TARIFF_RUBRIQUE_LABELS[key], "index_rate_text": row["rate_text"]}
        for key, row in index_by_key.items()
        if key not in pdf_keys
    ]
    decision["index_only_rubriques"] = index_only
    return {"checked": checked, "concordant": concordant, "divergent": divergent}


OMAAD_COMPARATOR_URL = "https://omaad.africa/outils/comparateur-sgi-brvm/"
OMAAD_SITEMAP_URL = "https://omaad.africa/sitemap.xml"


def _omaad_slug_candidates(sgi_names: list[str]) -> set[str]:
    """Slugs de fiches plausibles déduits des noms de l'annuaire (découverte only).

    L'identité du document est toujours revérifiée dans le PDF relu ; ces variantes
    ne servent qu'à trouver l'URL de la fiche (pluriel/singulier, « d' » soudée,
    préfixe SGI…) sans navigateur.
    """
    candidates: set[str] = set()
    for name in sgi_names:
        tokens = normalize_key(name).split()

        def variants(tokens_: list[str]) -> set[str]:
            merged: list[str] = []
            index = 0
            while index < len(tokens_):
                if tokens_[index] == "d" and index + 1 < len(tokens_):
                    merged.append("d" + tokens_[index + 1])
                    index += 2
                else:
                    merged.append(tokens_[index])
                    index += 1
            singular = [token[:-1] if len(token) > 3 and token.endswith("s") else token for token in tokens_]
            forms = {"-".join(tokens_), "-".join(merged), "-".join(singular)}
            out = set(forms)
            for form in forms:
                out.add(form if form.startswith("sgi-") else f"sgi-{form}")
                if form.startswith("sgi-"):
                    out.add(form[4:])
            return out

        candidates.update(variants(tokens))
        without_sa = [token for token in tokens if token != "sa"]
        if without_sa != tokens:
            candidates.update(variants(without_sa))
    return candidates


def collect_omaad_tariff_documents(
    session: requests.Session, sgi_names: list[str] | None = None
) -> dict[str, dict[str, Any]]:
    """Découverte secondaire : fiches SGI rendues côté serveur par Omaad.

    Même règle que pour Richbourse : seul le lien vers le PDF officiel est repris ;
    la grille est relue dans le document, sans transcription tierce à recouper.
    Énumération sans navigateur : page comparateur (premier écran), sitemap
    officiel du site, puis slugs déduits des noms de l'annuaire BRVM.
    """
    documents: dict[str, dict[str, Any]] = {}
    slugs: set[str] = set()
    for source_url in (OMAAD_COMPARATOR_URL, OMAAD_SITEMAP_URL):
        try:
            response = session.get(source_url, timeout=45)
            response.raise_for_status()
            slugs.update(re.findall(r"/outils/comparateur-sgi-brvm/sgi/([a-z0-9\-]+)/?", response.text))
        except Exception:
            continue
    if sgi_names:
        slugs.update(_omaad_slug_candidates(sgi_names))
    for slug in sorted(slugs):
        try:
            fiche = session.get(f"{OMAAD_COMPARATOR_URL}sgi/{slug}/", timeout=45)
            fiche.raise_for_status()
        except Exception:
            continue
        pdf_match = re.search(r"/pdfs-sgi/(Tarifs_[^\"' ]+\.pdf)", fiche.text)
        if not pdf_match:
            continue
        doc_ref = pdf_match.group(1)
        index_name = re.sub(r"^Tarifs_\d+_", "", doc_ref[:-4]).replace("-", " ").upper()
        documents[doc_ref] = {
            "doc_ref": doc_ref,
            "doc_url": f"https://omaad.africa/pdfs-sgi/{doc_ref}",
            "index_sgi_name": index_name,
            "rows": [],
        }
        time.sleep(0.2)
    return documents


BRVM_TARIFF_SEARCH_URL = "https://www.brvm.org/fr/search/node/homologation%20tarifs%20sgi"


def parse_announced_decision_number(text: str | None) -> str | None:
    """Numéro annoncé par la page BRVM (titre ou nom de fichier officiel).

    Métadonnée de publication, jamais un substitut à la relecture du PDF : elle
    est affichée distinctement lorsque le numéro est illisible dans le document.
    Gère les formes « PAMF-UMOA/2025/289 », « PAMF-UMOA – 286 -2025 » (inversée
    dans les noms de fichiers BRVM) et « PCR-DA-2019-094 ».
    """
    source = text or ""
    match = re.search(r"PAMF-UMOA[\s/–—_-]{0,4}(20\d{2})[\s/–—_-]+0*(\d{1,4})", source, flags=re.I)
    if match and int(match.group(2)) >= 1:
        return f"PAMF-UMOA/{match.group(1)}/{int(match.group(2))}"
    match = re.search(r"PAMF-UMOA[^\d]{0,6}0*(\d{1,4})[\s\-–—_]+(20\d{2})", source, flags=re.I)
    if match and int(match.group(1)) >= 1:
        return f"PAMF-UMOA/{match.group(2)}/{int(match.group(1))}"
    match = re.search(
        r"PCR[-/](SG[-/])?(DA[-/])?(20\d{2})[-/]0*(\d{1,4})", source, flags=re.I
    )
    if match and int(match.group(4)) >= 1:
        middle = ("SG/" if match.group(1) else "") + ("DA/" if match.group(2) else "")
        return f"PCR/{middle}{match.group(3)}/{int(match.group(4))}"
    match = re.search(r"CREPMF[^\d]{0,20}(20\d{2})[-/]0*(\d{1,4})", source, flags=re.I)
    if match and int(match.group(2)) >= 1:
        return f"CREPMF/{match.group(1)}/{int(match.group(2))}"
    return None


def brvm_decision_pdf_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    candidates = [
        str(a.get("href"))
        for a in soup.find_all("a", href=True)
        if str(a.get("href")).lower().endswith(".pdf")
    ]
    for href in candidates:
        if "homologation" in href.lower() or "decision" in href.lower():
            return href if href.startswith("http") else f"https://www.brvm.org{href}"
    if candidates:
        href = candidates[0]
        return href if href.startswith("http") else f"https://www.brvm.org{href}"
    return None


def _sgi_name_from_brvm_title(title: str) -> str | None:
    match = re.search(r"tarifs de la SGI\s+(.+)$", title, flags=re.I)
    if match:
        name = " ".join(match.group(1).split()).strip(" .")
        return name[:80] or None
    match = re.match(r"^\s*SGI\s+([^:]+?)\s*:\s*Homologation", title, flags=re.I)
    if match:
        return " ".join(match.group(1).split())[:80] or None
    # Formes anciennes (avis CREPMF) : « relative à l'homologation des tarifs
    # de la SGI MAC AFRICAN SGI », « tarifs de X » sans le sigle SGI.
    match = re.search(r"tarifs de(?:\s+la)?\s+(?:SGI\s+)?(.+)$", title, flags=re.I)
    if match:
        name = " ".join(match.group(1).split()).strip(" .")
        name = re.sub(r"\s+SGI$", " ", name, flags=re.I).strip()
        if len(name) >= 3:
            return name[:80] or None
    return None


BRVM_TARIFF_SEARCH_QUERIES = (
    "homologation tarifs sgi",
    "decision homologation tarifs",
    "homologation des tarifs de la sgi",
    "tarifs sgi decision amf",
)


def collect_brvm_tariff_decisions(
    session: requests.Session, max_pages: int = 8
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Canal primaire : décisions d'homologation publiées par la BRVM elle-même.

    L'article 3 des décisions impose leur communication à la BRVM pour
    publication : brvm.org les expose en pages officielles avec le PDF joint.
    La recherche du site est instable (même requête, pages différentes selon
    les jours) : on unionne plusieurs formulations avant de relire les pages.
    """
    warnings: list[str] = []
    nodes: dict[str, str] = {}
    for query in BRVM_TARIFF_SEARCH_QUERIES:
        base_url = "https://www.brvm.org/fr/search/node/" + quote(query, safe="")
        if query == BRVM_TARIFF_SEARCH_QUERIES[0]:
            base_url = BRVM_TARIFF_SEARCH_URL
        for page_number in range(max_pages):
            url = base_url if page_number == 0 else f"{base_url}?page={page_number}"
            try:
                response = session.get(url, timeout=45)
                response.raise_for_status()
            except Exception as exc:
                warnings.append(
                    f"Recherche BRVM « {query} » page {page_number} indisponible ({exc})."
                )
                break
            soup = BeautifulSoup(response.text, "lxml")
            new_nodes = 0
            for anchor in soup.find_all("a", href=True):
                title = " ".join(anchor.get_text(" ").split())
                normalized = normalize_key(title)
                href = str(anchor.get("href"))
                if "homologation" in normalized and "tarif" in normalized and "/fr/" in href and "search" not in href:
                    full = href if href.startswith("http") else f"https://www.brvm.org{href}"
                    if full not in nodes:
                        nodes[full] = title
                        new_nodes += 1
            if new_nodes == 0:
                break
            time.sleep(0.3)
    documents: dict[str, dict[str, Any]] = {}
    for node_url, title in sorted(nodes.items()):
        try:
            node = session.get(node_url, timeout=45)
            node.raise_for_status()
        except Exception:
            continue
        pdf_url = brvm_decision_pdf_url(node.text)
        if not pdf_url:
            continue
        # Le titre complet de la page : le listing de recherche Peut le
        # tronquer (ex. nom long de SGI sans acronyme) et empêcher le
        # rattachement à l'annuaire.
        page_soup = BeautifulSoup(node.text, "lxml")
        h1 = page_soup.find("h1")
        if h1 is not None:
            page_title = " ".join(h1.get_text(" ", strip=True).split())
            if page_title and len(page_title) >= len(title):
                title = page_title
        normalized_title = normalize_key(title)
        if (
            re.search(r"\b(sgo|sgp|btcc|sicav)\b", normalized_title)
            and not re.search(r"\bsgi\b", normalized_title)
        ) or re.search(
            r"pour le compte du (fcp|fonds)|asset management", normalized_title
        ):
            continue
        doc_ref = pdf_url.rsplit("/", 1)[-1]
        index_name = _sgi_name_from_brvm_title(title) or re.sub(
            r"^.*?homologation_des_tarifs_de_la_sgi_", "", doc_ref[:-4]
        ).replace("_", " ").upper()
        documents[doc_ref] = {
            "doc_ref": doc_ref,
            "doc_url": pdf_url,
            "index_sgi_name": index_name,
            "rows": [],
            "source": "brvm",
            "node_url": node_url,
            "announced_decision_number": parse_announced_decision_number(f"{title} {doc_ref}"),
        }
        time.sleep(0.2)
    return documents, warnings


BRVM_AVIS_URL = "https://www.brvm.org/fr/marche/avis-et-publications/avis"


def collect_brvm_avis_tariff_decisions(
    session: requests.Session, max_pages: int = 230, min_date: str = "2018-01-01"
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Balayage de l'index officiel « Avis et publications » de la BRVM.

    La recherche du site est instable (résultats répétés ou absents selon la
    requête) : cet index chronologique liste chaque décision publiée avec son
    PDF en lien direct. On s'arrête dès que la page ne contient plus que des
    avis antérieurs aux premières homologations tarifaires (2018).
    """
    warnings: list[str] = []
    documents: dict[str, dict[str, Any]] = {}
    for page_number in range(max_pages):
        url = BRVM_AVIS_URL if page_number == 0 else f"{BRVM_AVIS_URL}?page={page_number}"
        try:
            response = session.get(url, timeout=45)
            response.raise_for_status()
        except Exception as exc:
            warnings.append(f"Index Avis BRVM page {page_number} indisponible ({exc}).")
            break
        soup = BeautifulSoup(response.text, "lxml")
        page_dates: list[str] = []
        pdf_anchors = [
            anchor
            for anchor in soup.find_all("a", href=True)
            if str(anchor.get("href")).lower().endswith(".pdf")
        ]
        if not pdf_anchors:
            break
        for anchor in pdf_anchors:
            row = anchor.find_parent(["tr", "div", "li"])
            row_text = " ".join(row.get_text(" ", strip=True).split()) if row else ""
            date_match = re.search(r"(\d{2})/(\d{2})/(20\d{2})", row_text)
            if date_match:
                page_dates.append(
                    f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}"
                )
            normalized = normalize_key(row_text)
            if "homologation" not in normalized or "tarif" not in normalized:
                continue
            # L'index mélange toutes les homologations tarifaires du régulateur :
            # seules celles des SGI nous concernent (exclure SGO/SGP, banques
            # teneurs de comptes et fonds, dont les grilles ne sont pas des frais
            # de courtage SGI). Filet principal : acteur non-SGI nommé sans « SGI ».
            if (
                re.search(r"\b(sgo|sgp|btcc|sicav)\b", normalized)
                and not re.search(r"\bsgi\b", normalized)
            ) or re.search(
                r"pour le compte du (fcp|fonds)|asset management", normalized
            ):
                continue
            pdf_url = str(anchor.get("href"))
            if not pdf_url.startswith("http"):
                pdf_url = f"https://www.brvm.org{pdf_url}"
            doc_ref = pdf_url.rsplit("/", 1)[-1]
            title = re.sub(r"\s*\d{2}/\d{2}/20\d{2}\s*Télécharger\s*$", "", row_text, flags=re.I).strip()
            index_name = _sgi_name_from_brvm_title(title) or re.sub(
                r"^.*?homologation_des_tarifs_de_la_sgi_", "", doc_ref[:-4]
            ).replace("_", " ").upper()
            if doc_ref not in documents:
                documents[doc_ref] = {
                    "doc_ref": doc_ref,
                    "doc_url": pdf_url,
                    "index_sgi_name": index_name,
                    "rows": [],
                    "source": "brvm",
                    "node_url": url,
                    "announced_decision_number": parse_announced_decision_number(
                        f"{title} {doc_ref}"
                    ),
                }
        if page_dates and max(page_dates) < min_date:
            break
        time.sleep(0.15)
    return documents, warnings


def collect_sgi_tariffs(
    session: requests.Session, sgis: list[dict[str, Any]], cache_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    """Rattache à chaque SGI de l'annuaire sa décision tarifaire relue, si elle existe.

    Retourne (décisions non rattachées à l'annuaire BRVM, compteurs, avertissements).
    Les SGI sans décision relue gardent leur statut « tarifs non publiés » : aucun
    tarif n'est inventé ni copié depuis la transcription d'un tiers.
    """
    warnings: list[str] = []
    counts = {
        "decisions_found": 0,
        "decisions_verified": 0,
        "decisions_partial": 0,
        "grids_without_decision": 0,
        "sgis_with_tariffs": 0,
        "decisions_unmatched": 0,
        "rates_extracted": 0,
        "rates_cross_checked": 0,
        "rates_concordant": 0,
        "rates_divergent": 0,
        "decisions_ocr": 0,
        "decisions_without_annex": 0,
        "decisions_superseded": 0,
        "documents_failed": 0,
    }
    documents, index_warnings = collect_richbourse_tariff_index(session)
    warnings.extend(index_warnings)
    for document in documents.values():
        document.setdefault("source", "richbourse")
    known_keys = {_sgi_match_key(doc["index_sgi_name"]) for doc in documents.values()}
    for doc_ref, document in collect_omaad_tariff_documents(
        session, [sgi["name"] for sgi in sgis]
    ).items():
        if _sgi_match_key(document["index_sgi_name"]) not in known_keys:
            document.setdefault("source", "omaad")
            documents[doc_ref] = document
    # Canal primaire BRVM : toujours relu pour les SGI non couvertes, et relu
    # aussi lorsqu'une décision numérotée y est annoncée (copie officielle
    # parfois plus complète que celle des index — cas Hudson 2023 sans annexe
    # chez les index, complète chez la BRVM).
    brvm_documents, brvm_warnings = collect_brvm_tariff_decisions(session)
    warnings.extend(brvm_warnings)
    # La recherche BRVM est instable : l'index chronologique « Avis et
    # publications » complète l'énumération officielle (mêmes PDF BRVM).
    avis_documents, avis_warnings = collect_brvm_avis_tariff_decisions(session)
    warnings.extend(avis_warnings)
    for doc_ref, document in avis_documents.items():
        brvm_documents.setdefault(doc_ref, document)
    for doc_ref, document in brvm_documents.items():
        key = _sgi_match_key(document["index_sgi_name"])
        if key not in known_keys or document.get("announced_decision_number"):
            documents[doc_ref] = document
    if not documents:
        warnings.append("Tarifs SGI : index de découverte vide, aucune décision relue.")
        return [], counts, warnings
    cache_dir.mkdir(parents=True, exist_ok=True)
    # On garde TOUS les exemplaires relus : le choix (annexe, date, statut,
    # recoupement) se fait après dédoublonnage. Un filtrage en cours de boucle
    # par date lue écartait à tort des décisions récentes sans date relue.
    processed: list[dict[str, Any]] = []
    for doc_ref in sorted(documents):
        document = documents[doc_ref]
        try:
            decision = process_sgi_tariff_pdf(
                session, document["doc_url"], doc_ref, document["index_sgi_name"], cache_dir
            )
        except Exception as exc:
            counts["documents_failed"] += 1
            print(f"[SIGMA] Tarif SGI {doc_ref} ignoré : {exc}", file=sys.stderr)
            continue
        if decision.get("actor_kind") in {"SGO", "SGP", "BTCC", "SICAV"}:
            # Homologation d'un autre type d'intervenant (gestion d'actifs,
            # banque teneuse de comptes, fonds) : hors périmètre SGI.
            continue
        cross_check_tariff_rates(decision, document["rows"])
        decision["discovery_source"] = document.get("source", "index")
        decision["announced_decision_number"] = document.get("announced_decision_number")
        decision["source_node_url"] = document.get("node_url")
        processed.append(decision)
        time.sleep(0.2)
    # Dédoublonnage : le même PDF officiel peut être relayé par les deux index.
    # Identité par empreinte du fichier, sinon par numéro de décision ; on garde
    # l'exemplaire le mieux recoupé (celui adossé à la transcription d'index).
    def _decision_quality(item: dict[str, Any]) -> tuple[int, int]:
        checked = sum(
            1 for rate in item["rates"] if rate.get("cross_check_status") not in (None, "non_recoupe")
        )
        return (checked, len(item["rates"]))

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for decision in processed:
        identities = []
        if decision.get("sha256"):
            identities.append(("sha", str(decision["sha256"])))
        if decision.get("decision_number"):
            identities.append(("num", str(decision["decision_number"])))
        if not identities:
            identities.append(("doc", str(decision.get("doc_ref") or id(decision))))
        kept = next((deduped[key] for key in identities if key in deduped), None)
        winner = decision if kept is None or _decision_quality(decision) > _decision_quality(kept) else kept
        if kept is not None and kept is not winner:
            # Union des métadonnées : l'exemplaire perdant (souvent la copie
            # BRVM, sans recoupement) Peut porter le numéro annoncé, la page
            # officielle ou une preuve que le gagnant n'a pas. Sans cette
            # fusion, une vieille décision datée battait une récente non datée.
            loser = kept
            for field in (
                "announced_decision_number",
                "decision_number",
                "decision_date",
                "source_node_url",
                "sgi_name_pdf",
            ):
                if not winner.get(field) and loser.get(field):
                    winner[field] = loser[field]
            if winner.get("name_check") != "confirme" and loser.get("name_check") == "confirme":
                winner["name_check"] = "confirme"
        for key in identities:
            deduped[key] = winner
    unique_decisions = {id(decision): decision for decision in deduped.values()}

    def _decision_rank(item: dict[str, Any]) -> tuple[int, str, int, tuple[int, int]]:
        """Choix de la décision affichée lorsqu'une SGI en a plusieurs (copies ou
        homologations successives) : annexe lisible d'abord, puis la plus récente,
        puis le statut le mieux prouvé, puis le recoupement le plus riche."""
        status_rank = {
            "decision_verifiee": 3,
            "decision_partielle": 2,
            "grille_sans_decision_jointe": 1,
            "document_illisible": 0,
        }.get(item["status"], 0)
        date_key = item.get("decision_date") or ""
        if not date_key:
            for reference in (item.get("decision_number"), item.get("announced_decision_number")):
                reference_match = re.search(r"/(20\d{2})/", reference or "")
                if reference_match:
                    date_key = f"{reference_match.group(1)}-01-01"
                    break
        return (1 if item["rates"] else 0, date_key, status_rank, _decision_quality(item))

    def _belongs_to(item: dict[str, Any], sgi_name: str) -> bool:
        directory_key = _sgi_match_key(sgi_name)
        return directory_key in {
            _sgi_match_key(item.get("sgi_name_pdf")),
            _sgi_match_key(item["index_sgi_name"]),
        } or _sgi_names_match(item.get("sgi_name_pdf"), sgi_name) or _sgi_names_match(
            item["index_sgi_name"], sgi_name
        )

    unmatched: list[dict[str, Any]] = []
    attached_ids: set[int] = set()
    superseded_ids: set[int] = set()
    for sgi in sgis:
        candidates = [
            item
            for item in unique_decisions.values()
            if id(item) not in attached_ids and id(item) not in superseded_ids and _belongs_to(item, sgi["name"])
        ]
        if not candidates:
            continue
        decision = max(candidates, key=_decision_rank)
        for other in candidates:
            if other is not decision:
                superseded_ids.add(id(other))
        attached_ids.add(id(decision))
        public = {field: value for field, value in decision.items() if field != "doc_ref"}
        sgi["tariffs_homologated"] = public
        if decision["rates"]:
            counts["sgis_with_tariffs"] += 1
    unmatched_best: dict[str, dict[str, Any]] = {}
    for decision in unique_decisions.values():
        if id(decision) not in attached_ids and id(decision) not in superseded_ids:
            key = _sgi_match_key(decision["index_sgi_name"]) or decision["index_sgi_name"]
            key = next(
                (
                    existing_key
                    for existing_key in unmatched_best
                    if _sgi_names_match(decision["index_sgi_name"], existing_key)
                ),
                key,
            )
            if key in unmatched_best:
                superseded_ids.add(id(decision))
                if _decision_rank(decision) <= _decision_rank(unmatched_best[key]):
                    continue
                superseded_ids.discard(id(decision))
                superseded_ids.add(id(unmatched_best[key]))
            unmatched_best[key] = decision
    for decision in unmatched_best.values():
        if True:
            unmatched.append(
                {
                    "index_sgi_name": decision["index_sgi_name"],
                    "sgi_name_pdf": decision.get("sgi_name_pdf"),
                    "decision_number": decision.get("decision_number"),
                    "announced_decision_number": decision.get("announced_decision_number"),
                    "decision_date": decision.get("decision_date"),
                    "status": decision["status"],
                    "doc_url": decision["doc_url"],
                }
            )
    displayed = [item for item in unique_decisions.values() if id(item) not in superseded_ids]
    counts["decisions_found"] = len(unique_decisions)
    counts["decisions_superseded"] = len(superseded_ids)
    counts["rates_extracted"] = sum(len(item["rates"]) for item in displayed)
    counts["rates_cross_checked"] = sum(
        1
        for item in displayed
        for rate in item["rates"]
        if rate.get("cross_check_status") not in (None, "non_recoupe")
    )
    counts["rates_concordant"] = sum(
        1 for item in displayed for rate in item["rates"] if rate.get("cross_check_status") == "concordant"
    )
    counts["rates_divergent"] = sum(
        1 for item in displayed for rate in item["rates"] if rate.get("cross_check_status") == "divergent"
    )
    counts["decisions_ocr"] = sum(
        1 for item in displayed if item["extraction_method"] != "texte_natif"
    )
    counts["decisions_without_annex"] = sum(1 for item in displayed if not item["rates"])
    for decision in displayed:
        if decision["status"] == "decision_verifiee":
            counts["decisions_verified"] += 1
        elif decision["status"] == "decision_partielle":
            counts["decisions_partial"] += 1
        elif decision["status"] == "grille_sans_decision_jointe":
            counts["grids_without_decision"] += 1
    counts["decisions_unmatched"] = len(unmatched)
    print(
        f"[SIGMA] Tarifs SGI homologués : {counts['decisions_found']} document(s) relu(s), "
        f"{counts['sgis_with_tariffs']}/{len(sgis)} SGI de l'annuaire couvertes, "
        f"{counts['decisions_unmatched']} décision(s) hors annuaire.",
        file=sys.stderr,
    )
    return sorted(unmatched, key=lambda item: item["index_sgi_name"]), counts, warnings


def median_or_none(values: list[float | int | None]) -> float | int | None:
    clean = [value for value in values if isinstance(value, (int, float))]
    if not clean:
        return None
    med = statistics.median(clean)
    return int(med) if float(med).is_integer() else round(float(med), 6)


def pct_change(current: Any, previous: Any) -> float | None:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    if previous == 0:
        return None
    return round(((current / previous) - 1) * 100, 4)


def compute_history_stats(history: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session_data in history:
        for ticker, row in session_data["rows"].items():
            by_ticker[ticker].append(
                {
                    "date": session_data["date"],
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                    "traded_value_fcfa": row.get("traded_value_fcfa"),
                    "variation_pct": row.get("variation_pct"),
                }
            )

    stats: dict[str, dict[str, Any]] = {}
    for ticker, points in by_ticker.items():
        points.sort(key=lambda point: point["date"])
        traded_values = [
            point["traded_value_fcfa"] if isinstance(point["traded_value_fcfa"], (int, float)) else 0
            for point in points[-20:]
        ]
        close_points = [point for point in points if isinstance(point["close"], (int, float)) and point["close"] > 0]
        stats[ticker] = {
            "sessions_available": len(points),
            "traded_sessions_last_20": sum(
                1 for point in points[-20:] if isinstance(point["volume"], (int, float)) and point["volume"] > 0
            ),
            "median_traded_value_last_20_fcfa": median_or_none(traded_values),
            "performance_5_sessions_pct": (
                pct_change(close_points[-1]["close"], close_points[-6]["close"]) if len(close_points) >= 6 else None
            ),
            "performance_20_sessions_pct": (
                pct_change(close_points[-1]["close"], close_points[-21]["close"]) if len(close_points) >= 21 else None
            ),
            "series": points,
        }
    return stats


def compute_market_structure(snapshot_quotes: list[dict[str, Any]], latest_boc: dict[str, Any]) -> dict[str, Any]:
    variations = [q["variation_pct"] for q in snapshot_quotes if isinstance(q["variation_pct"], (int, float))]
    boc_rows = list(latest_boc["rows"].values())
    total_value = sum(
        row["traded_value_fcfa"] for row in boc_rows if isinstance(row["traded_value_fcfa"], (int, float))
    )
    top5_value = sum(
        sorted(
            [row["traded_value_fcfa"] for row in boc_rows if isinstance(row["traded_value_fcfa"], (int, float))],
            reverse=True,
        )[:5]
    )
    return {
        "snapshot": {
            "advancers": sum(1 for value in variations if value > 0),
            "decliners": sum(1 for value in variations if value < 0),
            "unchanged": sum(1 for value in variations if value == 0),
            "median_variation_pct": median_or_none(variations),
            "without_volume": sum(
                1 for q in snapshot_quotes if not isinstance(q["volume"], (int, float)) or q["volume"] == 0
            ),
        },
        "latest_boc": {
            "date": latest_boc["date"],
            "total_traded_value_fcfa": total_value,
            "top5_traded_value_share_pct": round((top5_value / total_value) * 100, 4) if total_value else None,
            "advancers": sum(
                1 for row in boc_rows if isinstance(row["variation_pct"], (int, float)) and row["variation_pct"] > 0
            ),
            "decliners": sum(
                1 for row in boc_rows if isinstance(row["variation_pct"], (int, float)) and row["variation_pct"] < 0
            ),
            "unchanged": sum(
                1 for row in boc_rows if isinstance(row["variation_pct"], (int, float)) and row["variation_pct"] == 0
            ),
            "median_variation_pct": median_or_none([row["variation_pct"] for row in boc_rows]),
        },
        "capitalization_concentration": {
            "status": "non_calculable",
            "reason": "Nombre d'actions en circulation sourcé et vérifié non encore intégré pour toutes les sociétés.",
        },
    }


def build_dataset(
    boc_count: int,
    cache_dir: Path,
    boc_archive_count: int = 260,
    boc_archive_path: Path | None = None,
) -> dict[str, Any]:
    session = make_session()
    snapshot = scrape_latest_snapshot(session)
    sector_map = scrape_sector_map(session)
    dividends = scrape_dividends(session)
    archive_path = boc_archive_path or (
        Path(__file__).resolve().parents[1] / "web" / "data" / "boc_archive.json"
    )
    existing_archive, archive_warning = load_boc_archive(archive_path if boc_archive_count > 0 else None)
    existing_archive_sessions = existing_archive.get("sessions") or []
    # Backfill long uniquement si l'archive n'est pas déjà proche de l'objectif ;
    # ensuite, chaque collecte quotidienne ne relit que la fenêtre récente et
    # fusionne les nouvelles séances dans l'archive persistante.
    needs_boc_backfill = boc_archive_count > 0 and len(existing_archive_sessions) < max(
        0, boc_archive_count - 5
    )
    boc_docs_limit = max(boc_count, boc_archive_count if needs_boc_backfill else 0)
    boc_docs, indexed_boc_docs = scrape_boc_links(session, boc_docs_limit)
    fetched_history = load_boc_history(session, boc_docs, cache_dir)
    history = fetched_history[-boc_count:] if boc_count > 0 else fetched_history
    archive_updated_at = datetime.now(ZoneInfo("Africa/Abidjan")).isoformat(timespec="seconds")
    merged_archive = (
        merge_boc_archive(existing_archive, fetched_history, archive_updated_at)
        if boc_archive_count > 0
        else Empty_boc_archive()
    )
    archive_history = boc_archive_history(merged_archive)
    report_pages = scrape_report_pages(session)

    if len(snapshot["quotes"]) < 35:
        raise ValueError(f"Contrôle bloquant : {len(snapshot['quotes'])} cours seulement dans l'instantané officiel.")
    if len(history) < 20:
        raise ValueError(
            f"Contrôle bloquant : historique BOC insuffisant pour les calculs à 20 séances ({len(history)} séances)."
        )

    latest_boc = history[-1]
    stats = compute_history_stats(history)
    long_stats = compute_long_history_stats(archive_history)
    quote_by_ticker = {quote["ticker"]: quote for quote in snapshot["quotes"]}
    all_tickers = sorted(set(quote_by_ticker) | set(latest_boc["rows"]))
    companies: list[dict[str, Any]] = []
    warnings: list[str] = []
    if archive_warning:
        warnings.append(archive_warning)

    for ticker in all_tickers:
        quote = quote_by_ticker.get(ticker)
        boc = latest_boc["rows"].get(ticker)
        if quote is None:
            warnings.append(f"{ticker} présent dans le BOC mais absent de l'instantané des cours.")
        if boc is None:
            warnings.append(f"{ticker} présent dans l'instantané mais absent du dernier BOC lu.")
        name = (quote or boc or {}).get("name", ticker)
        companies.append(
            {
                "ticker": ticker,
                "name": clean_text(name),
                "sector": sector_map.get(ticker) or (boc or {}).get("sector") or "Non renseigné par la source",
                "latest_quote": quote,
                "latest_boc": boc,
                "latest_boc_date": latest_boc["date"] if boc else None,
                "history_stats": {
                    **{key: value for key, value in stats.get(ticker, {}).items() if key != "series"},
                    "long_history": long_stats.get(ticker, {}),
                },
                "series": stats.get(ticker, {}).get("series", []),
                "data_confidence": "marché_uniquement",
                "fundamentals_status": "non_verifies",
            }
        )

    dividend_history_by_ticker = compute_dividend_history(dividends, companies)
    for company in companies:
        company["dividend_history"] = dividend_history_by_ticker.get(company["ticker"], {})
    print(
        f"[SIGMA] Historique dividendes BRVM : {len(dividends)} lignes, "
        f"{sum(1 for item in dividend_history_by_ticker.values() if item.get('paid_last_5_fiscal_years') == 5)} sociétés documentées sur 5 exercices",
        file=sys.stderr,
    )

    news_items, news_warnings = collect_news(session, companies)
    warnings.extend(news_warnings)
    print(f"[SIGMA] Actualités collectées : {len(news_items)}", file=sys.stderr)

    try:
        sgis = scrape_sgis(session)
        print(f"[SIGMA] SGI de l'annuaire officiel : {len(sgis)}", file=sys.stderr)
    except Exception as exc:  # annuaire indisponible : ne bloque pas les données de marché
        sgis = []
        warnings.append(f"Annuaire officiel des SGI indisponible ({exc}).")
        print(f"[SIGMA] Annuaire SGI ignoré : {exc}", file=sys.stderr)

    sgi_tariffs_unmatched: list[dict[str, Any]] = []
    sgi_tariff_counts: dict[str, Any] = {}
    if sgis:
        try:
            sgi_tariffs_unmatched, sgi_tariff_counts, tariff_warnings = collect_sgi_tariffs(
                session, sgis, cache_dir / "sgi_tariffs"
            )
            warnings.extend(tariff_warnings)
        except Exception as exc:  # tarifs indisponibles : ne bloque jamais le reste
            warnings.append(f"Tarifs SGI homologués indisponibles ({exc}).")
            print(f"[SIGMA] Tarifs SGI ignorés : {exc}", file=sys.stderr)

    fundamentals_counts, fundamentals_warnings = collect_fundamentals(
        session, companies, report_pages, cache_dir / "reports"
    )
    warnings.extend(fundamentals_warnings)
    print(
        f"[SIGMA] Documents émetteurs indexés : {fundamentals_counts['documents_indexed']} "
        f"pour {fundamentals_counts['companies_with_documents']} sociétés ; "
        f"agrégats annuels extraits (à confirmer) : {fundamentals_counts['companies_with_figures']} sociétés",
        file=sys.stderr,
    )
    sustainability_counts = enrich_dividend_sustainability(companies)
    print(
        f"[SIGMA] Repères dividende/flux : {sustainability_counts['dividend_sustainability_rows']} exercice(s), "
        f"{sustainability_counts['companies_with_dividend_eps_ratio']} société(s) avec dividende net/BPA, "
        f"{sustainability_counts['companies_with_dividend_cash_coverage']} avec couverture par le flux opérationnel",
        file=sys.stderr,
    )

    macro_reference_date = datetime.now(ZoneInfo("Africa/Abidjan")).date().isoformat()
    macro_context, macro_warnings = collect_macro_context(session, macro_reference_date)
    warnings.extend(macro_warnings)
    calendar_events = build_calendar_events(macro_reference_date, dividends, macro_context, companies)
    print(
        f"[SIGMA] Macro/calendrier : CPM {macro_context.get('bceao_cpm', {}).get('status')}, "
        f"{macro_context.get('umoa_summary', {}).get('upcoming_operations', 0)} émissions UMOA à venir, "
        f"{len(calendar_events)} échéances datées",
        file=sys.stderr,
    )

    generated_at = datetime.now(ZoneInfo("Africa/Abidjan")).isoformat(timespec="seconds")
    if boc_archive_count > 0:
        merged_archive["updated_at"] = generated_at
        write_boc_archive(archive_path, merged_archive)
        print(
            f"[SIGMA] Archive BOC longue : {merged_archive['sessions_count']} séances "
            f"({merged_archive['first_date']} → {merged_archive['last_date']}) dans {archive_path}",
            file=sys.stderr,
        )
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "timezone": "Africa/Abidjan",
        "product_mode": "production_personnelle_phase_marche",
        "snapshot": {
            "source_url": snapshot["source_url"],
            "source_updated_label": snapshot["source_updated_label"],
            "session_status": snapshot["session_status"],
            "activity": snapshot["activity"],
            "indices": snapshot["indices"],
        },
        "history": {
            "source": "Bulletins Officiels de la Cote (BRVM)",
            "sessions": [
                {
                    "date": item["date"],
                    "url": item["url"],
                    "sha256": item["sha256"],
                    "composite_level": item["composite_level"],
                    "composite_variation_pct": item["composite_variation_pct"],
                    "discovery": item.get("discovery"),
                    "companies_read": len(item["rows"]),
                }
                for item in history
            ],
        },
        "boc_archive": {
            "file": "data/boc_archive.json",
            "target_sessions": boc_archive_count,
            "sessions_count": merged_archive.get("sessions_count", 0),
            "first_date": merged_archive.get("first_date"),
            "last_date": merged_archive.get("last_date"),
            "updated_at": merged_archive.get("updated_at"),
            "price_basis": merged_archive.get("price_basis"),
            "documents": [
                {
                    "date": item.get("date"),
                    "url": item.get("url"),
                    "sha256": item.get("sha256"),
                    "composite_level": item.get("composite_level"),
                    "composite_variation_pct": item.get("composite_variation_pct"),
                    "discovery": item.get("discovery"),
                    "companies_read": item.get("companies_read"),
                }
                for item in merged_archive.get("sessions", [])
            ],
        },
        "companies": companies,
        "dividends": dividends,
        "boc_documents": sorted(
            [
                *[
                    {"date": item["date"], "url": item["url"], "sha256": item["sha256"], "parsed": True}
                    for item in history
                ],
                *[
                    {"date": item["date"], "url": item["url"], "sha256": None, "parsed": False}
                    for item in indexed_boc_docs
                    if item["date"] not in {entry["date"] for entry in history}
                ],
            ],
            key=lambda entry: entry["date"],
            reverse=True,
        ),
        "report_pages": report_pages,
        "news": news_items,
        "sgis": sgis,
        "sgi_tariffs_unmatched": sgi_tariffs_unmatched,
        "market_fees_official": {
            "brvm_commission_pct": 0.2,
            "dcbr_commission_pct": 0.1,
            "basis": "Commissions de marché prélevées par transaction, à la charge de l'acheteur comme du vendeur, en sus du courtage de la SGI.",
            "source_url": BRVM_MARKET_FEES_URL,
            "source_label": "BRVM — Frais applicables",
            "verified_on": "2026-10-21",
            "note": "Relu sur la page officielle BRVM liée ; à revérifier avant tout calcul de coût total. L'assiette fiscale éventuelle n'est pas établie : SIGMA ne totalise pas ces commissions avec les plafonds SGI.",
        },
        "market_structure": compute_market_structure(snapshot["quotes"], latest_boc),
        "macro_context": macro_context,
        "calendar_events": calendar_events,
        "coverage": {
            "companies_in_snapshot": len(snapshot["quotes"]),
            "companies_in_latest_boc": len(latest_boc["rows"]),
            "boc_sessions": len(history),
            "boc_archive_sessions": merged_archive.get("sessions_count", 0),
            "boc_archive_first_date": merged_archive.get("first_date"),
            "boc_archive_last_date": merged_archive.get("last_date"),
            "boc_archive_target_sessions": boc_archive_count,
            "dividend_rows_collected": len(dividends),
            "dividend_fiscal_years_min": min(
                [int(re.search(r"(20\d{2})", str(div.get("fiscal_year") or "")).group(1)) for div in dividends if re.search(r"(20\d{2})", str(div.get("fiscal_year") or ""))],
                default=None,
            ),
            "dividend_fiscal_years_max": max(
                [int(re.search(r"(20\d{2})", str(div.get("fiscal_year") or "")).group(1)) for div in dividends if re.search(r"(20\d{2})", str(div.get("fiscal_year") or ""))],
                default=None,
            ),
            "companies_with_dividend_history_5y": sum(
                1 for item in dividend_history_by_ticker.values() if item.get("paid_last_5_fiscal_years") == 5
            ),
            "companies_with_any_dividend_history": sum(
                1 for item in dividend_history_by_ticker.values() if item.get("paid_fiscal_years_count")
            ),
            "sgis_official_directory": len(sgis),
            "sgi_tariff_decisions_found": sgi_tariff_counts.get("decisions_found", 0),
            "sgi_tariff_decisions_verified": sgi_tariff_counts.get("decisions_verified", 0),
            "sgi_tariff_decisions_partial": sgi_tariff_counts.get("decisions_partial", 0),
            "sgi_tariff_grids_without_decision": sgi_tariff_counts.get("grids_without_decision", 0),
            "sgis_with_homologated_tariffs": sgi_tariff_counts.get("sgis_with_tariffs", 0),
            "sgi_tariff_decisions_unmatched": sgi_tariff_counts.get("decisions_unmatched", 0),
            "sgi_tariff_rates_extracted": sgi_tariff_counts.get("rates_extracted", 0),
            "sgi_tariff_rates_cross_checked": sgi_tariff_counts.get("rates_cross_checked", 0),
            "sgi_tariff_rates_concordant": sgi_tariff_counts.get("rates_concordant", 0),
            "sgi_tariff_rates_divergent": sgi_tariff_counts.get("rates_divergent", 0),
            "sgi_tariff_decisions_ocr": sgi_tariff_counts.get("decisions_ocr", 0),
            "sgi_tariff_decisions_without_annex": sgi_tariff_counts.get("decisions_without_annex", 0),
            "sgi_tariff_decisions_superseded": sgi_tariff_counts.get("decisions_superseded", 0),
            "news_items": len(news_items),
            "news_with_ticker": sum(1 for entry in news_items if entry.get("tickers")),
            "annual_fundamentals_verified_companies": 0,
            "companies_with_indexed_documents": fundamentals_counts["companies_with_documents"],
            "issuer_documents_indexed": fundamentals_counts["documents_indexed"],
            "companies_with_extracted_figures_to_confirm": fundamentals_counts["companies_with_figures"],
            "companies_with_series_3y": fundamentals_counts["companies_with_series_3y"],
            "figures_confirmed_by_two_documents": fundamentals_counts["figures_confirmed_two_docs"],
            "companies_with_operating_cashflow": fundamentals_counts["companies_with_operating_cashflow"],
            "companies_with_cash_debt_flow": fundamentals_counts["companies_with_cash_debt_flow"],
            "companies_with_eps": fundamentals_counts["companies_with_eps"],
            "companies_with_share_count": fundamentals_counts["companies_with_share_count"],
            "companies_with_eps_or_shares": fundamentals_counts["companies_with_eps_or_shares"],
            "eps_published_observations": fundamentals_counts.get("eps_published_observations", 0),
            "eps_published_confirmed_observations": fundamentals_counts.get("eps_published_confirmed_observations", 0),
            "eps_recalculated_comparable_observations": fundamentals_counts.get("eps_recalculated_comparable_observations", 0),
            "eps_recalculated_confirmed_observations": fundamentals_counts.get("eps_recalculated_confirmed_observations", 0),
            "eps_parent_weighted_candidate_observations": fundamentals_counts.get("eps_parent_weighted_candidate_observations", 0),
            "eps_indicative_end_share_observations": fundamentals_counts.get("eps_indicative_end_share_observations", 0),
            "documents_ocr_attempted": fundamentals_counts["documents_ocr_attempted"],
            "documents_ocr_used": fundamentals_counts["documents_ocr_used"],
            "documents_ocr_cache_hits": fundamentals_counts["documents_ocr_cache_hits"],
            "companies_with_ocr_figures": fundamentals_counts["companies_with_ocr_figures"],
            "figures_ocr": fundamentals_counts["figures_ocr"],
            "documents_capital_supplement_attempted": fundamentals_counts["documents_capital_supplement_attempted"],
            "documents_capital_supplement_used": fundamentals_counts["documents_capital_supplement_used"],
            "figures_capital_supplemented": fundamentals_counts["figures_capital_supplemented"],
            "companies_with_capital_supplement": fundamentals_counts["companies_with_capital_supplement"],
            "companies_with_dividend_eps_ratio": sustainability_counts["companies_with_dividend_eps_ratio"],
            "companies_with_dividend_cash_coverage": sustainability_counts["companies_with_dividend_cash_coverage"],
            "companies_with_3y_dividend_cash_coverage": sustainability_counts["companies_with_3y_dividend_cash_coverage"],
            "dividend_sustainability_rows": sustainability_counts["dividend_sustainability_rows"],
            "macro_bceao_cpm_status": macro_context.get("bceao_cpm", {}).get("status"),
            "macro_bceao_cpm_date": macro_context.get("bceao_cpm", {}).get("published_date"),
            "macro_bceao_policy_rate_pct": macro_context.get("bceao_cpm", {}).get("policy_rate_pct"),
            "umoa_upcoming_issuances": macro_context.get("umoa_summary", {}).get("upcoming_operations", 0),
            "umoa_next_30d_amount_fcfa": (
                macro_context.get("umoa_summary", {}).get("windows", {}).get("next_30d", {}).get("amount_fcfa")
            ),
            "calendar_events": len(calendar_events),
            "calendar_next_date": calendar_events[0]["date"] if calendar_events else None,
            "sigma_pillar_scores_status": "solidite_croissance_conditionnes_reperes_dividende_flux_partiels_score_global_suspendu",
            "note": (
                "Les PER et rendements affichés sont ceux publiés par la BRVM dans le dernier BOC lu. "
                "Les agrégats annuels (activité, résultat net, capitaux propres, total du bilan, flux de "
                "trésorerie opérationnel, investissements en immobilisations, trésorerie, dettes financières, "
                "bénéfice par action et nombre d'actions lorsqu'ils sont lisibles) sont extraits automatiquement "
                "des états financiers officiels sur plusieurs exercices, avec page et ligne sources ; un agrégat "
                "est dit « confirmé » lorsque deux documents officiels distincts publient la même valeur pour le "
                "même exercice. Lorsqu’un PDF officiel est scanné sans couche de texte exploitable, un OCR contrôlé "
                "peut être appliqué en repli : provenance et confiance de reconnaissance restent attachées à chaque "
                "agrégat, et les mêmes contrôles d’unité, d’ordre des colonnes et de plausibilité s’appliquent. "
                "Une passe complémentaire peut chercher le seul BPA ou nombre d’actions dans un autre "
                "document officiel du même exercice, uniquement après recoupement du périmètre comptable "
                "avec le document principal. "
                "Les piliers Solidité et Croissance ne sont publiés que si la série est suffisante. "
                "L'historique officiel des dividendes nets par exercice permet désormais des repères de "
                "couverture lorsque BPA/nombre d'actions et flux du même exercice sont présents ; le dividende "
                "BRVM étant net, SIGMA ne les présente pas comme le taux de distribution brut voté, et le score "
                "global reste suspendu tant que la couverture et les recoupements ne sont pas suffisants partout. "
                "L'archive BOC longue "
                "conserve les prix publiés non ajustés : les performances longues sont donc des variations "
                "de prix seuls, hors dividendes réinvestis et hors ajustements d'opérations sur titres. "
                "Le contexte macro reprend le dernier communiqué CPM BCEAO relu par expressions ciblées et "
                "les tableaux UMOA-Titres des émissions à venir/planifiées ; le calendrier ne contient que "
                "des dates publiées par une source officielle (dividendes BRVM, opérations UMOA-Titres, événements BCEAO). "
                "Les tarifs SGI affichés sont les plafonds homologués par l'AMF-UMOA (anciennement CREPMF) : "
                "chaque décision officielle est relue dans son PDF (autorité, numéro, date et nom de la SGI "
                "vérifiés dans le document, OCR contrôlé en repli pour les scans), les rubriques gardent leur "
                "texte tarifaire d'origine et un recoupement avec l'index de découverte est affiché par ligne. "
                "Un plafond homologué est négociable : il ne remplace jamais la grille écrite reçue de la SGI, "
                "et SIGMA ne le totalise pas avec les commissions de marché tant que l'assiette fiscale n'est "
                "pas établie."
            ),
        },
        "sources": [
            {"label": "BRVM — Cours des actions", "url": URLS["quotes"]},
            {"label": "BRVM — Bulletins Officiels de la Cote", "url": URLS["boc_index"]},
            {"label": "BRVM — Paiement de dividendes", "url": URLS["dividends"]},
            {"label": "BRVM — Rapports des sociétés cotées", "url": URLS["reports_index"]},
            {"label": "BRVM — Annonces des émetteurs", "url": f"{BASE}/fr/emetteurs/type-annonces/communiques"},
            {"label": "BRVM — Actualités", "url": URLS["news_actualites"]},
            {"label": "BCEAO — Communiqués de presse", "url": URLS["bceao_press"]},
            {"label": "BCEAO — Événements", "url": URLS["bceao_events"]},
            {"label": "UMOA-Titres — Flux RSS", "url": URLS["umoa_rss"]},
            {"label": "UMOA-Titres — Émissions à venir et planifiées", "url": URLS["umoa_emissions"]},
            {"label": "Sika Finance — Flux RSS (presse)", "url": URLS["sika_rss"]},
            {"label": "BRVM — Annuaire officiel des SGI", "url": URLS["sgis"]},
            {"label": "BRVM — Frais applicables (commissions de marché)", "url": BRVM_MARKET_FEES_URL},
            {"label": "BRVM — Décisions d'homologation tarifaire des SGI (AMF-UMOA)", "url": BRVM_TARIFF_SEARCH_URL},
            {"label": "Richbourse — Index des décisions tarifaires SGI (découverte des PDF officiels)", "url": RICHBOURSE_TARIFFS_URL},
            {"label": "Omaad — Fiches SGI (découverte secondaire des PDF officiels)", "url": OMAAD_COMPARATOR_URL},
        ],
        "quality_warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collecte SIGMA BRVM (sources officielles)")
    parser.add_argument("--boc-count", type=int, default=30, help="Nombre de BOC récents à lire (défaut : 30)")
    parser.add_argument(
        "--boc-archive-count",
        type=int,
        default=260,
        help="Objectif de séances pour l'archive BOC longue persistante (défaut : 260 ; 0 désactive)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "web" / "data" / "data.json",
    )
    parser.add_argument(
        "--boc-archive-output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "web" / "data" / "boc_archive.json",
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("/tmp/sigma-boc-cache"))
    args = parser.parse_args()

    dataset = build_dataset(
        args.boc_count,
        args.cache_dir,
        boc_archive_count=args.boc_archive_count,
        boc_archive_path=args.boc_archive_output,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = args.output.with_suffix(".json.tmp")
    tmp_output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_output.replace(args.output)
    print(
        f"[SIGMA] Données publiées : {args.output} — "
        f"{len(dataset['companies'])} sociétés, {dataset['coverage']['boc_sessions']} BOC récents, "
        f"{dataset['coverage'].get('boc_archive_sessions', 0)} séances archivées, "
        f"{dataset['coverage'].get('calendar_events', 0)} échéances, "
        f"{dataset['coverage'].get('news_items', 0)} actualités, "
        f"{len(dataset['quality_warnings'])} avertissement(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

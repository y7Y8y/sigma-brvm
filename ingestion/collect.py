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
import hashlib
import io
import json
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import pdfplumber
import requests
from bs4 import BeautifulSoup

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
        for candidate in [company.get("name"), (company.get("latest_boc") or {}).get("name")]:
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
    "etats_financiers": 1,
    "rapport_activites_annuel": 2,
    "rapport_annuel": 3,
    "resultats_consolides": 4,
}
UNIT_MULTIPLIERS = {"unites": 1, "milliers": 1_000, "millions": 1_000_000, "milliards": 1_000_000_000}
FIGURE_LABELS = {
    "chiffre_affaires": [r"chiffre d['’]affaires", r"produits des activités ordinaires"],
    "produit_net_bancaire": [r"produit net bancaire"],
    "resultat_net": [
        r"résultat net de l['’]exercice",
        r"résultat net de l['’]ensemble consolidé",
        r"résultat net\s*$",
        r"résultat net\b",
        r"bénéfice net de l['’]exercice",
    ],
    "resultat_net_part_groupe": [r"résultat net attribuable aux propriétaires", r"résultat net[,\s]+part du groupe"],
    "capitaux_propres": [
        r"total capitaux propres et ressources assimilées",
        r"capitaux propres et ressources assimilées",
        r"total (?:des )?capitaux propres",
        r"capitaux propres\b",
    ],
    "total_bilan": [
        r"\bDZ\s+total général",
        r"total du passif et des capitaux propres",
        r"\bBZ\s+total général",
        r"total de l['’]actif\b",
        r"total actif\b",
        r"total bilan\b",
        r"total général\b",
    ],
}
FIGURE_DISPLAY_LABELS = {
    "chiffre_affaires": "Chiffre d'affaires",
    "produit_net_bancaire": "Produit net bancaire",
    "resultat_net": "Résultat net",
    "resultat_net_part_groupe": "Résultat net part du groupe",
    "capitaux_propres": "Capitaux propres",
    "total_bilan": "Total du bilan",
}
AMOUNT_PATTERN = re.compile(r"\(?-?\d{1,3}(?:[ \u202f\u00a0]\d{3})+(?:,\d+)?\)?|\(?-?\d+(?:,\d+)?\)?")
NOTE_REF_PATTERN = re.compile(r"^\d{1,2}\.\d{1,2}$")


def classify_report_document(url: str) -> dict[str, Any]:
    filename = urlparse(url).path.rsplit("/", 1)[-1]
    stem = re.sub(r"\.pdf$", "", filename, flags=re.I)
    pub_date = None
    date_match = re.match(r"(\d{4})(\d{2})(\d{2})[-_ ]", stem)
    remainder = stem
    if date_match:
        pub_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        remainder = stem[date_match.end():]
    normalized = normalize_key(remainder.replace("_", " "))
    if "semestre" in normalized:
        doc_type = "activite_semestrielle"
    elif "trimestre" in normalized:
        doc_type = "activite_trimestrielle"
    elif ("attestation" in normalized or "rapport des commissaires" in normalized or "examen limite" in normalized) \
            and "etats financiers" not in normalized:
        doc_type = "attestation_cac"
    elif "etats financiers" in normalized and "approuv" in normalized:
        doc_type = "etats_financiers_approuves"
    elif "etats financiers" in normalized:
        doc_type = "etats_financiers"
    elif "rapport dactivites annuel" in normalized or "rapport d activites annuel" in normalized:
        doc_type = "rapport_activites_annuel"
    elif "rapport annuel" in normalized:
        doc_type = "rapport_annuel"
    elif "resultats consolides" in normalized:
        doc_type = "resultats_consolides"
    elif "rse" in normalized:
        doc_type = "rse"
    else:
        doc_type = "autre"
    exercice = None
    exercice_match = re.search(r"exercice[_\- ](\d{4})", remainder, flags=re.I)
    if exercice_match:
        exercice = int(exercice_match.group(1))
    else:
        years = [int(y) for y in re.findall(r"(20\d{2})", remainder)]
        if years:
            exercice = years[-1]
    label = clean_text(remainder.replace("_", " ").replace("-", " "))
    return {
        "filename": filename,
        "label": label[:1].upper() + label[1:] if label else filename,
        "doc_type": doc_type,
        "exercice": exercice,
        "published_date": pub_date,
        "url": url,
    }


def scrape_issuer_documents(session: requests.Session, report_pages: list[dict[str, str]],
                            companies: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
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
        # Paginer la page de l'émetteur jusqu'à couvrir cinq exercices annuels
        # distincts (chaque page liste une vingtaine de documents, tous types).
        for page_index in range(4):
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
                by_ticker[ticker].append(classify_report_document(href))
                new_docs += 1
            annual_exercices = {
                d["exercice"]
                for d in by_ticker[ticker]
                if d["doc_type"] in ANNUAL_DOC_PRIORITY and isinstance(d.get("exercice"), int)
            }
            if new_docs == 0 or len(annual_exercices) >= 5:
                break
    for ticker, docs in by_ticker.items():
        docs.sort(key=lambda d: (d["published_date"] is None, d["published_date"] or ""), reverse=True)
        dated = [d for d in docs if d["published_date"]]
        undated = [d for d in docs if not d["published_date"]]
        dated.sort(key=lambda d: d["published_date"], reverse=True)
        by_ticker[ticker] = (dated + undated)[:60]
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


def parse_french_amount(token: str) -> float | None:
    text = token.strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace("\u202f", " ").replace("\u00a0", " ").replace(" ", "").replace(",", ".")
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

    def flush() -> None:
        nonlocal current
        if current:
            joined = "".join(w["text"] for w in current)
            value = parse_french_amount(joined)
            if value is not None:
                clusters.append((current[0]["index"], value))
        current = []

    for word in words:
        token = word["text"].strip()
        if NOTE_REF_PATTERN.match(token):
            flush()
            continue
        if "%" in token:
            flush()
            continue
        starts_amount = re.fullmatch(r"\(?-?\d{1,3}(?:,\d+)?\)?", token) or re.fullmatch(r"\(?-?\d+,\d+\)?", token)
        continues_amount = re.fullmatch(r"\d{3}(?:,\d+)?\)?", token)
        if current and continues_amount and (word["x0"] - current[-1]["x1"]) <= 6:
            current.append(word)
        elif starts_amount:
            flush()
            current = [word]
        else:
            flush()
    flush()
    return clusters


def structured_lines_from_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda w: (round(w["top"] / 3), w["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= 3:
            lines[-1].append(word)
        else:
            lines.append([word])
    structured = []
    for line_words in lines:
        ordered = sorted(line_words, key=lambda w: w["x0"])
        indexed = [{**w, "index": i} for i, w in enumerate(ordered)]
        structured.append(
            {
                "text": clean_text(" ".join(w["text"] for w in ordered)),
                "words": [w["text"] for w in ordered],
                "amounts": cluster_amounts(indexed),
            }
        )
    return structured


def line_amount_after_label(line: dict[str, Any], match_end: int) -> float | None:
    # Position du libellé en nombre de mots (le texte nettoyé joint par espaces simples).
    prefix = line["text"][:match_end]
    label_word_count = len([w for w in prefix.split(" ") if w])
    for word_index, value in line.get("amounts", []):
        if word_index >= label_word_count:
            return value
    return None


def line_amounts_after_label(line: dict[str, Any], match_end: int) -> list[float]:
    prefix = line["text"][:match_end]
    label_word_count = len([w for w in prefix.split(" ") if w])
    return [value for word_index, value in line.get("amounts", []) if word_index >= label_word_count]


def _aggregate_candidates(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not entries:
        return None
    entries.sort(key=lambda e: e["value_fcfa"])
    clusters: list[list[dict[str, Any]]] = []
    for entry in entries:
        placed = False
        for cluster in clusters:
            reference = cluster[0]["value_fcfa"]
            if reference == 0 or abs(entry["value_fcfa"] - reference) <= abs(reference) * 0.011:
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
            any(e["pattern_rank"] == best_rank for e in c),
            len(c),
            len({e["page"] for e in c}),
        ),
    )
    representative = min(best, key=lambda e: e["multiplier"])  # unité la plus fine = plus précis
    return {
        "value_fcfa": representative["value_fcfa"],
        "unit_label": representative["unit_label"],
        "occurrences": len(best),
        "evidence": [
            {"page": e["page"], "line": e["line"], "unit_label": e["unit_label"]} for e in best[:3]
        ],
    }


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


def extract_figures_from_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Extrait les colonnes Exercice (col. 0) et Exercice précédent (col. 1).

    Retourne {"courant": figures, "precedent": figures, "_rejected": [...]}
    chaque figure portant occurrences et lignes sources dans CE document.
    """
    candidates: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for page_number, page in enumerate(pages, start=1):
        unit = detect_unit(page.get("text") or "")
        if unit is None and looks_like_syscohada_synthesis(page):
            unit = (1, "FCFA (états de synthèse SYSCOHADA codés)")
        if unit is None:
            continue
        multiplier, unit_label = unit
        for line in page.get("lines", []):
            text = line.get("text") or ""
            if len(text) < 8 or "par action" in text.lower():
                continue
            lowered = text.lower()
            normalized_line = normalize_key(text)
            for key, patterns in FIGURE_LABELS.items():
                if key == "capitaux_propres" and ("passif et des capitaux propres" in lowered or "attribuable" in lowered):
                    continue
                if key == "resultat_net" and "attribuable" in lowered:
                    continue
                if key == "total_bilan" and "total general" not in normalized_line and any(
                    partial in normalized_line for partial in ("actif immobilise", "actif circulant", "tresorerie actif")
                ):
                    continue
                for pattern_rank, pattern in enumerate(patterns):
                    match = re.search(pattern, text, flags=re.I)
                    if not match:
                        continue
                    amounts = line_amounts_after_label(line, match.end())
                    if not amounts:
                        fallback = first_amount_after(text, match.end())
                        amounts = [fallback] if fallback is not None else []
                    # Actif SYSCOHADA : BZ présente brut, amortissements,
                    # net N puis net N-1. Le total de bilan est la colonne
                    # nette ; le passif DZ ne présente que N et N-1.
                    if key == "total_bilan" and re.search(r"\bBZ\s+total général", text, flags=re.I) \
                            and not re.search(r"\bDZ\s+total général", text, flags=re.I) and len(amounts) >= 4:
                        amounts = amounts[2:4]
                    for column, raw_value in enumerate(amounts[:2]):
                        value_fcfa = raw_value * multiplier
                        if abs(value_fcfa) < 1_000_000 or abs(value_fcfa) > 30_000_000_000_000:
                            continue
                        if not key.startswith("resultat") and key != "capitaux_propres" and value_fcfa <= 0:
                            continue
                        candidates[(key, column)].append(
                            {
                                "value_fcfa": round(value_fcfa),
                                "raw_value": raw_value,
                                "unit_label": unit_label,
                                "multiplier": multiplier,
                                "page": page_number,
                                "line": text[:320],
                                "pattern_rank": pattern_rank,
                            }
                        )
                    break

    result: dict[str, Any] = {}
    rejected_all: list[str] = []
    for column, label in ((0, "courant"), (1, "precedent")):
        figures: dict[str, Any] = {}
        for key in FIGURE_LABELS:
            aggregated = _aggregate_candidates(candidates.get((key, column), []))
            if aggregated:
                figures[key] = {
                    "label": FIGURE_DISPLAY_LABELS[key],
                    **aggregated,
                    "confidence": "recoupe_dans_le_document" if aggregated["occurrences"] >= 2 else "extraction_unique",
                }
        figures, rejected = apply_plausibility_filters(figures)
        rejected_all.extend(rejected if column == 0 else [])
        result[label] = figures
    if rejected_all:
        result["_rejected"] = rejected_all
    return result


def extract_annual_figures(session: requests.Session, doc: dict[str, Any], cache_dir: Path) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / re.sub(r"[^A-Za-z0-9_.-]+", "_", doc["filename"])
    if cache_file.exists() and cache_file.stat().st_size > 10_000:
        content = cache_file.read_bytes()
    else:
        content = bytes(fetch(session, doc["url"], binary=True))
        if len(content) > 30_000_000:
            return {"columns": {"courant": {}, "precedent": {}}, "notes": ["Document trop volumineux pour l'extraction automatique (> 30 Mo)."]}
        cache_file.write_bytes(content)
    pages: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages[:80]:
            text = page.extract_text() or ""
            try:
                lines = structured_lines_from_words(page.extract_words() or [])
            except Exception:
                lines = []
            if not lines and text:
                lines = [{"text": clean_text(l), "words": l.split(), "amounts": []} for l in text.split("\n")]
            pages.append({"text": text, "lines": lines})
    totalChars = sum(len(p["text"]) for p in pages)
    if totalChars < 2000:
        return {"columns": {"courant": {}, "precedent": {}}, "notes": ["Texte non extractible (document probablement numérisé en image)."],
                "sha256": hashlib.sha256(content).hexdigest()}
    extracted = extract_figures_from_pages(pages)
    notes = list(extracted.pop("_rejected", []))
    if not extracted.get("courant"):
        notes.append("Aucun agrégat annuel n'a passé les contrôles d'extraction (unité explicite introuvable ou libellés non reconnus).")
    return {"columns": extracted, "notes": notes, "sha256": hashlib.sha256(content).hexdigest()}


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
    for (exercice, key), entries in grouped.items():
        entries.sort(key=lambda e: e["value_fcfa"])
        clusters: list[list[dict[str, Any]]] = []
        for entry in entries:
            placed = False
            for cluster in clusters:
                reference = cluster[0]["value_fcfa"]
                tolerance = max(abs(reference) * 0.015, 1)
                if abs(entry["value_fcfa"] - reference) <= tolerance:
                    cluster.append(entry)
                    placed = True
                    break
            if not placed:
                clusters.append([entry])
        best = max(clusters, key=lambda c: (len({e["doc_url"] for e in c}), len(c)))
        distinct_docs = len({e["doc_url"] for e in best})
        total_occurrences = sum(e.get("occurrences", 1) for e in best)
        if distinct_docs >= 2:
            confidence = "confirme_deux_documents"
        elif total_occurrences >= 2:
            confidence = "recoupe_dans_le_document"
        else:
            confidence = "extraction_unique"
        if len(clusters) > 1:
            rival = max((c for c in clusters if c is not best), key=len)
            rival_value = rival[0]["value_fcfa"]
            best_value = best[0]["value_fcfa"]
            if best_value and abs(rival_value - best_value) > abs(best_value) * 0.05:
                notes.append(
                    f"{FIGURE_DISPLAY_LABELS[key]} {exercice} : valeurs divergentes entre documents "
                    f"(retraitement possible) — valeur la mieux recoupée retenue."
                )
        representative = next((e for e in best if e.get("column") == 0), best[0])
        series[exercice][key] = {
            "label": FIGURE_DISPLAY_LABELS[key],
            "value_fcfa": representative["value_fcfa"],
            "unit_label": representative.get("unit_label"),
            "confidence": confidence,
            "occurrences": total_occurrences,
            "documents_confirmants": distinct_docs,
            "evidence": [],
        }
        evidence_details = []
        for e in best[:3]:
            for ev in (e.get("evidence") or [{"page": e.get("page"), "line": e.get("line"), "unit_label": e.get("unit_label")}]):
                evidence_details.append({**ev, "document_label": e.get("doc_label")})
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
            weaker_year = year_a if rank.get(fig_a.get("confidence"), 0) <= rank.get(fig_b.get("confidence"), 0) else year_b
            for entry in series_list:
                if entry["exercice"] == weaker_year and key in entry["figures"]:
                    entry["figures"].pop(key, None)
                    notes.append(
                        f"{FIGURE_DISPLAY_LABELS[key]} {weaker_year} écarté : rupture d'échelle "
                        f"(×{ratio:.1f}) avec l'exercice voisin, extraction la moins recoupée."
                    )
    series_list = [entry for entry in series_list if entry["figures"]]
    return series_list, notes


def collect_fundamentals(session: requests.Session, companies: list[dict[str, Any]],
                         report_pages: list[dict[str, str]], cache_dir: Path) -> tuple[dict[str, int], list[str]]:
    docs_by_ticker, warnings = scrape_issuer_documents(session, report_pages, companies)
    counts = {
        "companies_with_documents": 0,
        "documents_indexed": 0,
        "companies_with_figures": 0,
        "companies_with_series_3y": 0,
        "figures_confirmed_two_docs": 0,
    }
    for company in companies:
        docs = docs_by_ticker.get(company["ticker"], [])
        company["documents"] = docs
        counts["documents_indexed"] += len(docs)
        if docs:
            counts["companies_with_documents"] += 1
        annual_candidates = [
            d for d in docs
            if d["doc_type"] in ANNUAL_DOC_PRIORITY and isinstance(d.get("exercice"), int) and d["exercice"] >= 2020
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

        annual_candidates.sort(key=lambda d: (-d["exercice"], ANNUAL_DOC_PRIORITY[d["doc_type"]]))
        # Un document par exercice (le plus fiable), cinq exercices au plus,
        # plus le document suivant le plus récent s'il apporte sa colonne N-1.
        chosen_docs: list[dict[str, Any]] = []
        seen_exercices: set[int] = set()
        for candidate in annual_candidates:
            if candidate["exercice"] in seen_exercices:
                continue
            seen_exercices.add(candidate["exercice"])
            chosen_docs.append(candidate)
            if len(chosen_docs) >= 5:
                break

        observations: list[dict[str, Any]] = []
        attempt_notes: list[str] = []
        latest_doc_info: dict[str, Any] | None = None
        for chosen in chosen_docs:
            try:
                result = extract_annual_figures(session, chosen, cache_dir)
            except Exception as exc:
                attempt_notes.append(f"{chosen['label']} : extraction impossible ({exc}).")
                continue
            if chosen is chosen_docs[0]:
                latest_doc_info = {
                    "url": chosen["url"],
                    "label": chosen["label"],
                    "doc_type": chosen["doc_type"],
                    "published_date": chosen["published_date"],
                    "sha256": result.get("sha256"),
                }
            columns = result.get("columns") or {}
            for column_index, column_name in ((0, "courant"), (1, "precedent")):
                target_exercice = chosen["exercice"] - column_index
                if target_exercice < 2019:
                    continue
                for key, figure in (columns.get(column_name) or {}).items():
                    if key.startswith("_"):
                        continue
                    first_evidence = (figure.get("evidence") or [{}])[0]
                    observations.append(
                        {
                            "exercice": target_exercice,
                            "key": key,
                            "value_fcfa": figure["value_fcfa"],
                            "unit_label": figure.get("unit_label"),
                            "occurrences": figure.get("occurrences", 1),
                            "column": column_index,
                            "doc_exercice": chosen["exercice"],
                            "doc_url": chosen["url"],
                            "doc_label": chosen["label"],
                            "page": first_evidence.get("page"),
                            "line": first_evidence.get("line"),
                            "evidence": figure.get("evidence") or [],
                        }
                    )
            if not (columns.get("courant") or columns.get("precedent")):
                attempt_notes.append(
                    f"{chosen['label']} : {result['notes'][0] if result['notes'] else 'aucun agrégat retenu.'}"
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
        years_with_result = sum(
            1 for entry in series_list if "resultat_net" in entry["figures"] or "resultat_net_part_groupe" in entry["figures"]
        )
        if len(series_list) >= 3:
            counts["companies_with_series_3y"] += 1
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
            "news_items": len(news_items),
            "news_with_ticker": sum(1 for entry in news_items if entry.get("tickers")),
            "annual_fundamentals_verified_companies": 0,
            "companies_with_indexed_documents": fundamentals_counts["companies_with_documents"],
            "issuer_documents_indexed": fundamentals_counts["documents_indexed"],
            "companies_with_extracted_figures_to_confirm": fundamentals_counts["companies_with_figures"],
            "companies_with_series_3y": fundamentals_counts["companies_with_series_3y"],
            "figures_confirmed_by_two_documents": fundamentals_counts["figures_confirmed_two_docs"],
            "macro_bceao_cpm_status": macro_context.get("bceao_cpm", {}).get("status"),
            "macro_bceao_cpm_date": macro_context.get("bceao_cpm", {}).get("published_date"),
            "macro_bceao_policy_rate_pct": macro_context.get("bceao_cpm", {}).get("policy_rate_pct"),
            "umoa_upcoming_issuances": macro_context.get("umoa_summary", {}).get("upcoming_operations", 0),
            "umoa_next_30d_amount_fcfa": (
                macro_context.get("umoa_summary", {}).get("windows", {}).get("next_30d", {}).get("amount_fcfa")
            ),
            "calendar_events": len(calendar_events),
            "calendar_next_date": calendar_events[0]["date"] if calendar_events else None,
            "sigma_pillar_scores_status": "solidite_croissance_conditionnes_aux_series_dividende_suspendu",
            "note": (
                "Les PER et rendements affichés sont ceux publiés par la BRVM dans le dernier BOC lu. "
                "Les agrégats annuels (chiffre d'affaires ou produit net bancaire, résultat net, capitaux "
                "propres, total du bilan) sont extraits automatiquement des états financiers officiels sur "
                "plusieurs exercices, avec page et ligne sources ; un agrégat est dit « confirmé » lorsque "
                "deux documents officiels distincts publient la même valeur pour le même exercice. Les piliers "
                "Solidité et Croissance ne sont publiés que si la série est suffisante ; l'historique officiel "
                "des dividendes nets par exercice est désormais collecté, mais le pilier Dividende durable et "
                "le score global restent suspendus tant que le taux de distribution/couverture par les flux "
                "n'est pas calculable sans nombre d'actions ou bénéfice par action vérifié. L'archive BOC longue "
                "conserve les prix publiés non ajustés : les performances longues sont donc des variations "
                "de prix seuls, hors dividendes réinvestis et hors ajustements d'opérations sur titres. "
                "Le contexte macro reprend le dernier communiqué CPM BCEAO relu par expressions ciblées et "
                "les tableaux UMOA-Titres des émissions à venir/planifiées ; le calendrier ne contient que "
                "des dates publiées par une source officielle (dividendes BRVM, opérations UMOA-Titres, événements BCEAO)."
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

#!/usr/bin/env python3
"""Appliquer des dates d'introduction vérifiées à l'audit BPA 480.

L'inventaire automatique lit la plupart des dates sur les profils BRVM,
mais certains profils ont un champ symbole vide, un symbole d'affichage
différent du ticker, ou n'exposent pas encore le bloc de profil. Ce
post-traitement ne contient que des couples (ticker, date attendue,
source officielle) explicitement listés ci-dessous. Il **relit chaque
source** et refuse d'appliquer une date si le nom de l'émetteur et la
date attendue ne sont pas retrouvés dans le document fetché.

Il met à jour uniquement `inventory.json` et `issuer_registry.*` du
dossier d'audit, conserve la valeur automatisée d'origine, puis écrit un
journal de provenance. Le journal d'extraction des PDF et le dataset
publié ne sont pas touchés ; relancer ensuite `audit_bpa_480.py --phase
aggregate` pour régénérer la matrice.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
INGESTION_DIR = Path(__file__).resolve().parent
ROOT = INGESTION_DIR.parent
sys.path.insert(0, str(INGESTION_DIR))

import pdfplumber  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from audit_bpa_480 import _parse_listing_profile, _write_json, _write_registry  # noqa: E402
from collect import clean_text, make_session, normalize_key  # noqa: E402

DEFAULT_OUTPUT_DIR = ROOT / "audits" / "audit_bpa_480_2016_2025_2026-10-25"

FRENCH_MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _date_raw_variants(iso_date: str) -> list[str]:
    parsed = date.fromisoformat(iso_date)
    month = FRENCH_MONTHS_FR[parsed.month - 1]
    return list(
        dict.fromkeys(
            [
                f"{parsed.day:02d}/{parsed.month:02d}/{parsed.year}",
                f"{parsed.day}/{parsed.month}/{parsed.year}",
                f"{parsed.day:02d} {month} {parsed.year}",
                f"{parsed.day} {month} {parsed.year}",
            ]
        )
    )


# Chaque entrée doit être relue sur sa source. `issuer_phrases` sont
# comparées après normalisation (accents/casse ignorés).
ENTRIES: list[dict[str, Any]] = [
    {
        "ticker": "BBGC",
        "listing_date": "2026-09-24",
        "source_kind": "html",
        "source_url": "https://www.brvm.org/fr/mediacentre/actualites/bridge-bank-group-cote-divoire-fait-son-entree-la-brvm",
        "issuer_phrases": ["BRIDGE BANK GROUP CÔTE D’IVOIRE", "première cotation"],
        "basis": "Communiqué officiel BRVM de première cotation.",
    },
    {
        "ticker": "BICB",
        "listing_date": "2025-04-28",
        "source_kind": "html",
        "source_url": "https://www.brvm.org/fr/mediacentre/actualites/la-banque-internationale-pour-lindustrie-et-le-commerce-du-benin-biic-admise",
        "issuer_phrases": ["Banque Internationale pour l’Industrie et le Commerce du Bénin", "symbole BICB"],
        "basis": "Communiqué officiel BRVM d'admission à la cote.",
    },
    {
        "ticker": "CABC",
        "listing_date": "1998-09-16",
        "source_kind": "profile",
        "source_url": "https://www.brvm.org/fr/emetteurs/societes-cotees/societe-ivoirienne-de-cables-sicable",
        "issuer_phrases": ["Société Ivoirienne de Câbles", "SICABLE"],
        "basis": "Profil officiel BRVM ; champ Symbole vide dans le texte, rattachement par le titre officiel.",
    },
    {
        "ticker": "CBIBF",
        "listing_date": "2016-12-23",
        "source_kind": "profile",
        "source_url": "https://www.brvm.org/fr/emetteurs/societes-cotees/coris-bank-international",
        "issuer_phrases": ["CORIS Bank International", "Coris Bank International SA"],
        "basis": "Profil officiel BRVM ; symbole affiché CBI SA, rattachement par raison sociale et adresse au Burkina Faso.",
    },
    {
        "ticker": "CFAC",
        "listing_date": "1998-09-16",
        "source_kind": "profile",
        "source_url": "https://www.brvm.org/fr/emetteurs/societes-cotees/compagnie-francaise-de-lafrique-occidentale-en-cote-divoire-cfao-ci",
        "issuer_phrases": ["Compagnie Française de l'Afrique Occidentale", "CFAO MOTORS"],
        "basis": "Profil officiel BRVM ; le corps affiche BNBC par erreur manifeste, rattachement par le titre et la raison sociale CFAO.",
    },
    {
        "ticker": "ECOC",
        "listing_date": "2017-12-12",
        "source_kind": "html",
        "source_url": "https://www.brvm.org/fr/mediacentre/actualites/ecobank-cote-divoire-fait-son-entree-la-bourse-regionale-des-valeurs",
        "issuer_phrases": ["Ecobank Côte d’Ivoire", "Première Cotation"],
        "basis": "Communiqué officiel BRVM d'entrée à la cote.",
    },
    {
        "ticker": "LNBB",
        "listing_date": "2024-12-13",
        "source_kind": "html",
        "source_url": "https://www.brvm.org/fr/mediacentre/actualites/la-brvm-franchit-un-nouveau-cap-avec-une-capitalisation-record-de-plus-de-10",
        "issuer_phrases": ["Loterie Nationale du Bénin", "cotation de la Loterie Nationale du Bénin ce jour"],
        "basis": "Communiqué officiel BRVM daté du 13 décembre 2024 indiquant la cotation ce jour.",
    },
    {
        "ticker": "NSBC",
        "listing_date": "2017-10-24",
        "source_kind": "html",
        "source_url": "https://www.brvm.org/fr/mediacentre/actualites/nsia-banque-ci-cotee-la-brvm",
        "issuer_phrases": ["NSIA Banque Côte d’Ivoire", "1ère cotation"],
        "basis": "Communiqué officiel BRVM d'admission et de première cotation.",
    },
    {
        "ticker": "ORAC",
        "listing_date": "2022-12-30",
        "source_kind": "html",
        "source_url": "https://www.brvm.org/fr/mediacentre/actualites/orange-cote-divoire-admis-la-cote-de-la-brvm-cest-la-plus-importante",
        "issuer_phrases": ["Orange Côte d’Ivoire", "symbole ORAC"],
        "basis": "Communiqué officiel BRVM d'admission à la cote.",
    },
    {
        "ticker": "ORGT",
        "listing_date": "2019-04-16",
        "source_kind": "pdf",
        "source_url": "https://www.orabank.net/sites/default/files/190416_ipo_oragroup_cotation_fr.pdf",
        "issuer_phrases": ["Oragroup fait son entrée", "première cotation à Lomé"],
        "basis": "Communiqué officiel Oragroup daté du 16 avril 2019 annonçant l'entrée à la BRVM ce jour-là.",
    },
    {
        "ticker": "SCRC",
        "listing_date": "2016-12-29",
        "source_kind": "html",
        "source_url": "https://www.brvm.org/fr/mediacentre/actualites/2016-cru-exceptionnel-pour-la-brvm",
        "issuer_phrases": ["SUCRIVOIRE"],
        "basis": "Bilan officiel BRVM des admissions de 2016 : Sucrivoire (29 décembre 2016).",
    },
    {
        "ticker": "SIBC",
        "listing_date": "2016-10-27",
        "source_kind": "html",
        "source_url": "https://www.brvm.org/fr/mediacentre/actualites/2016-cru-exceptionnel-pour-la-brvm",
        "issuer_phrases": ["Société Ivoirienne de Banque"],
        "basis": "Bilan officiel BRVM des admissions de 2016 : Société Ivoirienne de Banque (27 octobre 2016).",
    },
]


def _pdf_first_pages_text(payload: bytes, max_pages: int = 3) -> str:
    texts: list[str] = []
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        for page in pdf.pages[:max_pages]:
            texts.append(page.extract_text() or "")
    return clean_text(" ".join(texts))


def _evidence_excerpt(text: str, phrase: str, radius: int = 240) -> str | None:
    if not text or not phrase:
        return None
    match = re.search(re.escape(clean_text(phrase)), clean_text(text), flags=re.I)
    if not match:
        return None
    cleaned = clean_text(text)
    start = max(0, match.start() - radius)
    end = min(len(cleaned), match.end() + radius)
    return cleaned[start:end]


def _verify_entry(session: Any, entry: dict[str, Any]) -> dict[str, Any]:
    url = str(entry["source_url"])
    expected_date = str(entry["listing_date"])
    response = session.get(url, timeout=45)
    result: dict[str, Any] = {
        "ticker": entry["ticker"],
        "expected_listing_date": expected_date,
        "source_kind": entry["source_kind"],
        "source_url": url,
        "http_status": response.status_code,
        "source_sha256": hashlib.sha256(response.content).hexdigest(),
        "basis": entry["basis"],
        "verified": False,
    }
    if response.status_code != 200:
        result["error"] = f"HTTP {response.status_code}"
        return result

    profile: dict[str, Any] | None = None
    if entry["source_kind"] == "pdf":
        text = _pdf_first_pages_text(response.content)
    else:
        html = response.text
        soup = BeautifulSoup(html, "lxml")
        text = clean_text(soup.get_text(" ", strip=True))
        if entry["source_kind"] == "profile":
            profile = _parse_listing_profile(html, url)
            result["profile"] = profile

    normalized_text = normalize_key(text)
    phrase_checks = {
        phrase: normalize_key(phrase) in normalized_text
        for phrase in entry.get("issuer_phrases") or []
    }
    date_variants = _date_raw_variants(expected_date)
    date_checks = {
        variant: normalize_key(variant) in normalized_text for variant in date_variants
    }
    result["issuer_phrase_checks"] = phrase_checks
    result["date_variant_checks"] = date_checks
    result["evidence_excerpts"] = []
    for phrase in list(entry.get("issuer_phrases") or []) + date_variants:
        excerpt = _evidence_excerpt(text, phrase)
        if excerpt:
            result["evidence_excerpts"].append({"phrase": phrase, "excerpt": excerpt})
        if len(result["evidence_excerpts"]) >= 4:
            break

    if profile is not None:
        verified = bool(
            profile.get("listing_date") == expected_date
            and phrase_checks
            and all(phrase_checks.values())
        )
    else:
        verified = bool(
            phrase_checks
            and all(phrase_checks.values())
            and any(date_checks.values())
        )
    result["verified"] = verified
    if not verified:
        result["error"] = "Nom/phrases ou date attendue non retrouvés dans la source relue."
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    inventory_path = output_dir / "inventory.json"
    registry_path = output_dir / "issuer_registry.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_by_ticker = {str(row.get("ticker")): row for row in registry}

    session = make_session()
    applied_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    checks: list[dict[str, Any]] = []
    for entry in ENTRIES:
        check = _verify_entry(session, entry)
        checks.append(check)
        status = "VERIFIE" if check.get("verified") else "REFUSE"
        print(f"[{status}] {entry['ticker']} {entry['listing_date']} {entry['source_url']}", flush=True)
        if not check.get("verified") or args.dry_run:
            continue
        ticker = str(entry["ticker"])
        listing_date = str(entry["listing_date"])
        profile = check.get("profile") or {}
        ticker_inventory = (inventory.get("tickers") or {}).get(ticker)
        if ticker_inventory is None:
            check["application_error"] = "Ticker absent de l'inventaire."
            continue
        original_listing = dict(ticker_inventory.get("listing") or {})
        ticker_inventory["listing"] = {
            **original_listing,
            "date": listing_date,
            "date_raw": profile.get("listing_date_raw") or _date_raw_variants(listing_date)[-1],
            "year": int(listing_date[:4]),
            "status": "LU_SUR_SOURCE_OFFICIELLE_VERIFIEE_SUPPLEMENT",
            "profile_url": entry["source_url"] if entry["source_kind"] == "profile" else original_listing.get("profile_url"),
            "source_url": entry["source_url"],
            "source_kind": entry["source_kind"],
            "profile_title": profile.get("profile_title") or original_listing.get("profile_title"),
            "profile_heading": profile.get("profile_heading") or original_listing.get("profile_heading"),
            "symbol": profile.get("symbol") if profile else original_listing.get("symbol"),
            "symbol_normalized": profile.get("symbol_normalized") if profile else original_listing.get("symbol_normalized"),
            "resolved_ticker": ticker,
            "ticker_resolution_method": "SUPPLEMENT_VERIFIE_TITRE_OU_COMMUNIQUE_OFFICIEL",
            "discovered_via": "SUPPLEMENT_SOURCES_OFFICIELLES",
            "supplement": {
                "applied_at": applied_at,
                "basis": entry["basis"],
                "source_sha256": check.get("source_sha256"),
                "evidence_excerpts": check.get("evidence_excerpts") or [],
                "original_automated_listing": original_listing,
            },
        }
        registry_row = registry_by_ticker.get(ticker)
        if registry_row is not None:
            registry_row.update(
                {
                    "listing_date": listing_date,
                    "listing_date_raw": ticker_inventory["listing"].get("date_raw"),
                    "listing_year": int(listing_date[:4]),
                    "listing_year_status": "LU_SUR_SOURCE_OFFICIELLE_VERIFIEE_SUPPLEMENT",
                    "listing_profile_url": entry["source_url"] if entry["source_kind"] == "profile" else registry_row.get("listing_profile_url"),
                    "listing_source_url": entry["source_url"],
                    "listing_profile_symbol": profile.get("symbol") if profile else registry_row.get("listing_profile_symbol"),
                    "listing_ticker_resolution_method": "SUPPLEMENT_VERIFIE_TITRE_OU_COMMUNIQUE_OFFICIEL",
                    "listing_profile_discovered_via": "SUPPLEMENT_SOURCES_OFFICIELLES",
                }
            )

    payload = {
        "schema_version": "sigma-audit-bpa-480-listing-supplement-applied-v1",
        "generated_at": applied_at,
        "dry_run": bool(args.dry_run),
        "verified_count": sum(1 for item in checks if item.get("verified")),
        "refused_count": sum(1 for item in checks if not item.get("verified")),
        "checks": checks,
    }
    if not args.dry_run:
        _write_json(inventory_path, inventory)
        _write_registry(output_dir, registry)
    _write_json(output_dir / "listing_dates_supplement_applied.json", payload)
    print(json.dumps({"verified": payload["verified_count"], "refused": payload["refused_count"], "dry_run": args.dry_run}, ensure_ascii=False))
    return 0 if payload["refused_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

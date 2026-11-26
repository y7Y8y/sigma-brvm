#!/usr/bin/env python3
"""Sonde des sources BRVM — mesurer avant de collecter.

Une collecte de plusieurs heures qui échoue ne dit rien : on ne sait ni si la
source répondait, ni quelle étape a coûté le temps. Cette sonde répond en deux
minutes et n'écrit aucune donnée :

1. chaque source répond-elle, et en combien de temps ;
2. combien de BOC sont indexés, et sur quelle période ;
3. le débit réel d'un BOC (c'est lui qui fixe la durée d'une archive longue) ;
4. le motif d'URL ancien remonte-t-il à 13, 25 et 37 mois.
"""

from __future__ import annotations

import re
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.brvm.org"
HEADERS = {"User-Agent": "SIGMA-BRVM/1.0 (diagnostic des sources officielles)"}

SOURCES = {
    "cours": f"{BASE}/fr/cours-actions/0",
    "dividendes": f"{BASE}/fr/esv/paiement-de-dividendes",
    "index BOC": f"{BASE}/fr/bulletins-officiels-de-la-cote",
    "rapports": f"{BASE}/fr/rapports-societes-cotees",
}


def chrono(label, url, session, binary=False):
    debut = time.monotonic()
    try:
        r = session.get(url, timeout=60)
        duree = time.monotonic() - debut
        taille = len(r.content) if binary else len(r.text)
        etat = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
        print(f"  {label:<12} {etat:<10} {duree:6.1f} s  {taille / 1024:8.0f} Ko  {url}", flush=True)
        return r, duree
    except Exception as exc:  # diagnostic : rapporter, ne pas interrompre
        print(f"  {label:<12} ECHEC      {time.monotonic() - debut:6.1f} s  {type(exc).__name__}: {exc}", flush=True)
        return None, 0.0


def main() -> int:
    session = requests.Session()
    session.headers.update(HEADERS)

    print("1 · Les sources repondent-elles ?", flush=True)
    pages = {}
    for nom, url in SOURCES.items():
        pages[nom], _ = chrono(nom, url, session)

    print("\n2 · Jusqu'ou remonte l'index des BOC ?", flush=True)
    dates = []
    index = pages.get("index BOC")
    if index is not None and index.ok:
        soup = BeautifulSoup(index.text, "lxml")
        for a in soup.select("a[href]"):
            m = re.search(r"boc_(\d{4})(\d{2})(\d{2})[^/]*\.pdf$", a.get("href", ""), re.I)
            if m:
                dates.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
        dates = sorted(set(dates))
        print(f"  {len(dates)} BOC indexes", flush=True)
        if dates:
            print(f"  du {dates[0]} au {dates[-1]}", flush=True)

    print("\n3 · Debit reel sur un BOC (fixe la duree d'une archive longue)", flush=True)
    if dates:
        jour = dates[-1]
        url = f"{BASE}/sites/default/files/boc_{jour.replace('-', '')}_2.pdf"
        r, duree = chrono("BOC recent", url, session, binary=True)
        if r is not None and r.ok and r.content[:4] == b"%PDF":
            print(f"  PDF valide en {duree:.1f} s → {duree * 1500 / 60:.0f} min pour 1 500 seances (5 ans)", flush=True)

    print("\n4 · Le motif d'URL ancien remonte-t-il loin ?", flush=True)
    aujourdhui = date.today()
    for mois in (13, 25, 37):
        sonde = aujourdhui - timedelta(days=30 * mois)
        while sonde.weekday() >= 5:
            sonde -= timedelta(days=1)
        url = f"{BASE}/sites/default/files/boc_{sonde.strftime('%Y%m%d')}_2.pdf"
        try:
            tete = session.head(url, timeout=30, allow_redirects=True)
            pdf = "pdf" in tete.headers.get("content-type", "").lower()
            print(f"  il y a ~{mois} mois ({sonde}) : HTTP {tete.status_code}{' · PDF' if pdf else ''}", flush=True)
        except Exception as exc:
            print(f"  il y a ~{mois} mois ({sonde}) : echec {type(exc).__name__}", flush=True)

    print("\n5 · Autres motifs d'URL pour remonter plus loin (suffixes)", flush=True)
    for mois in (37, 49, 61):
        sonde = aujourdhui - timedelta(days=30 * mois)
        while sonde.weekday() >= 5:
            sonde -= timedelta(days=1)
        trouves = []
        for suffixe in ("_2", "_1", "_3", ""):
            url = f"{BASE}/sites/default/files/boc_{sonde.strftime('%Y%m%d')}{suffixe}.pdf"
            try:
                tete = session.head(url, timeout=30, allow_redirects=True)
                if tete.status_code == 200 and "pdf" in tete.headers.get("content-type", "").lower():
                    trouves.append(suffixe or "(sans suffixe)")
            except Exception:
                pass
        print(f"  il y a ~{mois} mois ({sonde}) : {', '.join(trouves) if trouves else 'aucun motif'}", flush=True)

    print("\n6 · Cout d'extraction d'un BOC (c'est lui qui fixe la duree reelle)", flush=True)
    if dates:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import io as _io
        import pdfplumber
        jour = dates[-1]
        url = f"{BASE}/sites/default/files/boc_{jour.replace('-', '')}_2.pdf"
        r = session.get(url, timeout=60)
        if r.ok and r.content[:4] == b"%PDF":
            for libelle, pages in (("10 premieres pages", 10), ("20 premieres pages", 20)):
                debut = time.monotonic()
                with pdfplumber.open(_io.BytesIO(r.content)) as pdf:
                    total = len(pdf.pages)
                    for page in pdf.pages[:pages]:
                        _ = page.extract_text() or ""
                duree = time.monotonic() - debut
                print(f"  {libelle} ({min(pages, total)}/{total} pages) : {duree:.1f} s", flush=True)
            debut = time.monotonic()
            with pdfplumber.open(_io.BytesIO(r.content)) as pdf:
                _ = [pg.extract_text() or "" for pg in pdf.pages]
            duree = time.monotonic() - debut
            print(f"  document entier ({total} pages) : {duree:.1f} s "
                  f"→ {duree * 500 / 60:.0f} min pour 500 seances", flush=True)

    print("\nSonde terminee. Aucune donnee ecrite.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

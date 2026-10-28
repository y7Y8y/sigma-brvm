#!/usr/bin/env python3
"""Trajectoire — rejouer une décision passée sur l'archive réelle, sans look-ahead.

Question posée par le propriétaire : « si j'avais acheté Orange en début 2026,
où serais-je aujourd'hui, et une règle de vente m'aurait-elle aidé ? »

Ce module y répond avec l'archive BOC (262 séances, prix publiés non ajustés,
hors dividendes réinvestis). Il ne prédit rien : il rejoue.

Trois garanties de méthode
--------------------------
1. **Aucun look-ahead.** À chaque séance, une règle ne voit que les séances
   précédentes. Un test vérifie qu'une décision ne change jamais si l'on tronque
   l'archive après sa date.
2. **Aucun paramètre ajusté sur le résultat.** Les seuils sont écrits d'avance
   et publiés avec le résultat, y compris quand ils font perdre de l'argent.
3. **Aucune extrapolation.** Les performances sont dites « prix seuls » : elles
   n'incluent ni dividendes ni ajustement des opérations sur titres.

Usage
-----
    python3 ingestion/trajectoire.py SNTS ORAC --achat 2026-01-02
    python3 ingestion/trajectoire.py SNTS --achat 2026-01-02 --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "web" / "data" / "boc_archive.json"

#: Fenêtres et seuils des règles, écrits d'avance (jamais optimisés après coup).
FENETRE_PER = 120
RATIO_PER = 1.3
FENETRE_PRIX = 60
RATIO_PRIX = 1.25
STOP_PCT = 12.0


@dataclass
class Serie:
    ticker: str
    dates: list[str] = field(default_factory=list)
    closes: list[float] = field(default_factory=list)
    pers: list[float | None] = field(default_factory=list)

    def point(self, i: int) -> tuple[str, float, float | None]:
        return self.dates[i], self.closes[i], self.pers[i]


def charger_archive(chemin: Path = ARCHIVE) -> dict[str, Any]:
    with chemin.open(encoding="utf-8") as handle:
        return json.load(handle)


def _nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return None


def extraire_series(archive: dict[str, Any]) -> dict[str, Serie]:
    colonnes = archive["row_fields"]
    ix = {nom: i for i, nom in enumerate(colonnes)}
    series: dict[str, Serie] = {}
    for session in archive["sessions"]:
        for ticker, ligne in (session.get("rows") or {}).items():
            if not isinstance(ligne, list) or len(ligne) <= ix["close"]:
                continue
            close = _nombre(ligne[ix["close"]])
            if close is None or close <= 0:
                continue
            serie = series.setdefault(ticker, Serie(ticker))
            serie.dates.append(session["date"])
            serie.closes.append(close)
            per = _nombre(ligne[ix["per"]]) if "per" in ix and len(ligne) > ix["per"] else None
            serie.pers.append(per if per and per > 0 else None)
    return series


def indice_composite(archive: dict[str, Any]) -> dict[str, float]:
    return {
        session["date"]: float(session["composite_level"])
        for session in archive["sessions"]
        if _nombre(session.get("composite_level"))
    }


# --- Règles de sortie : chacune ne voit que le passé -------------------------

def sortie_jamais(serie: Serie, i: int, entree: float, pic: float) -> str | None:
    return None


def sortie_per_propre(serie: Serie, i: int, entree: float, pic: float) -> str | None:
    """Sort quand le PER publié dépasse le sien propre de +30 %.

    C'est la « normalisation par l'historique de la société », pas par la moyenne
    du marché : l'idée directrice est qu'une exception se juge contre son propre
    passé, jamais contre la moyenne des autres.
    """
    per_courant = serie.pers[i]
    passe = [p for p in serie.pers[max(0, i - FENETRE_PER):i] if p]
    if per_courant is None or len(passe) < 20:
        return None
    seuil = statistics.median(passe) * RATIO_PER
    if per_courant > seuil:
        return f"PER publié {per_courant:.2f} > {RATIO_PER} × médiane propre ({statistics.median(passe):.2f}) = {seuil:.2f}"
    return None


def sortie_bande_prix(serie: Serie, i: int, entree: float, pic: float) -> str | None:
    """Sort quand le cours dépasse de +25 % sa propre médiane des 60 séances."""
    passe = [c for c in serie.closes[max(0, i - FENETRE_PRIX):i]]
    if len(passe) < 20:
        return None
    mediane = statistics.median(passe)
    if serie.closes[i] > mediane * RATIO_PRIX:
        return f"cours {serie.closes[i]:.0f} > {RATIO_PRIX} × médiane 60 séances ({mediane:.0f})"
    return None


def sortie_stop(serie: Serie, i: int, entree: float, pic: float) -> str | None:
    """Stop suiveur : sort si le cours abandonne 12 % depuis son plus haut."""
    if pic <= 0:
        return None
    if serie.closes[i] <= pic * (1 - STOP_PCT / 100):
        return f"repli de {100 * (1 - serie.closes[i] / pic):.1f} % depuis le plus haut ({pic:.0f})"
    return None


REGLES: dict[str, dict[str, Any]] = {
    "HOLD": {
        "libelle": "Garder jusqu'à la fin de l'archive",
        "fonction": sortie_jamais,
        "parametres": {},
    },
    "PER_PROPRE": {
        "libelle": f"Vendre si le PER publié dépasse {RATIO_PER}× sa propre médiane sur {FENETRE_PER} séances",
        "fonction": sortie_per_propre,
        "parametres": {"fenetre": FENETRE_PER, "ratio": RATIO_PER},
    },
    "BANDE_PRIX": {
        "libelle": f"Vendre si le cours dépasse {RATIO_PRIX}× sa propre médiane sur {FENETRE_PRIX} séances",
        "fonction": sortie_bande_prix,
        "parametres": {"fenetre": FENETRE_PRIX, "ratio": RATIO_PRIX},
    },
    "STOP_12": {
        "libelle": f"Stop suiveur à −{STOP_PCT:.0f} % depuis le plus haut",
        "fonction": sortie_stop,
        "parametres": {"stop_pct": STOP_PCT},
    },
}


def simuler(
    serie: Serie,
    date_achat: str,
    regle: str,
    date_fin: str | None = None,
) -> dict[str, Any]:
    """Rejoue un achat et une règle de sortie sur la série, sans voir le futur."""
    if regle not in REGLES:
        raise SystemExit(f"règle inconnue : {regle}")

    indices = [i for i, d in enumerate(serie.dates) if d >= date_achat]
    if not indices:
        return {"ticker": serie.ticker, "regle": regle, "disponible": False,
                "raison": f"aucune séance à partir du {date_achat}"}
    debut = indices[0]
    fin = len(serie.dates) - 1
    if date_fin:
        bornes = [i for i, d in enumerate(serie.dates) if d <= date_fin]
        if bornes:
            fin = min(fin, bornes[-1])
    if fin <= debut:
        return {"ticker": serie.ticker, "regle": regle, "disponible": False,
                "raison": "fenêtre trop courte"}

    prix_entree = serie.closes[debut]
    pic = prix_entree
    motif = None
    indice_sortie = fin

    for i in range(debut + 1, fin + 1):
        pic = max(pic, serie.closes[i])
        motif = REGLES[regle]["fonction"](serie, i, prix_entree, pic)
        if motif:
            indice_sortie = i
            break

    prix_sortie = serie.closes[indice_sortie]
    return {
        "ticker": serie.ticker,
        "regle": regle,
        "disponible": True,
        "regle_libelle": REGLES[regle]["libelle"],
        "parametres": REGLES[regle]["parametres"],
        "date_achat": serie.dates[debut],
        "prix_achat": prix_entree,
        "date_sortie": serie.dates[indice_sortie],
        "prix_sortie": prix_sortie,
        "seances_detenues": indice_sortie - debut,
        "performance_pct": round(100 * (prix_sortie / prix_entree - 1), 2),
        "motif_sortie": motif or "aucune sortie déclenchée : position gardée",
        "plus_haut_pct": round(100 * (max(serie.closes[debut:indice_sortie + 1]) / prix_entree - 1), 2),
        "plus_bas_pct": round(100 * (min(serie.closes[debut:indice_sortie + 1]) / prix_entree - 1), 2),
        "prix_seuls": True,
    }


def comparer_indice(
    archive: dict[str, Any], date_achat: str, date_sortie: str
) -> dict[str, Any] | None:
    composite = indice_composite(archive)
    dates = sorted(composite)
    debut = next((d for d in dates if d >= date_achat), None)
    fin = next((d for d in reversed(dates) if d <= date_sortie), None)
    if not debut or not fin or debut >= fin:
        return None
    return {
        "indice": "BRVM Composite",
        "date_debut": debut,
        "date_fin": fin,
        "niveau_debut": composite[debut],
        "niveau_fin": composite[fin],
        "performance_pct": round(100 * (composite[fin] / composite[debut] - 1), 2),
    }


def etude_complete(
    archive: dict[str, Any], ticker: str, date_achat: str
) -> dict[str, Any]:
    series = extraire_series(archive)
    if ticker not in series:
        return {"ticker": ticker, "disponible": False, "raison": "ticker absent de l'archive"}
    serie = series[ticker]
    resultats = {nom: simuler(serie, date_achat, nom) for nom in REGLES}
    reference = comparer_indice(archive, date_achat, serie.dates[-1])
    detenue = resultats["HOLD"]
    if reference and detenue.get("disponible"):
        reference["performance_sur_meme_fenetre_pct"] = reference.pop("performance_pct")
        detenue_surplus = round(detenue["performance_pct"] - reference["performance_sur_meme_fenetre_pct"], 2)
    else:
        detenue_surplus = None
    return {
        "schema_version": "sigma-trajectoire-v1",
        "ticker": ticker,
        "disponible": True,
        "date_achat_demandee": date_achat,
        "premiere_seance": serie.dates[0],
        "derniere_seance": serie.dates[-1],
        "seances_disponibles": len(serie.dates),
        "resultats": resultats,
        "indice_reference": reference,
        "surplus_vs_indice_pct": detenue_surplus,
        "limites": [
            "prix publiés non ajustés : ni dividendes réinvestis, ni opérations sur titres",
            "rejouer le passé n'est pas prédire l'avenir",
            "seuils des règles écrits d'avance, jamais optimisés sur ces résultats",
        ],
    }


def rendre_markdown(etudes: list[dict[str, Any]]) -> str:
    lignes = [
        "# Trajectoire — que se serait-il passé ?",
        "",
        "*Rejeu sur l'archive officielle BOC. Prix seuls, hors dividendes réinvestis. "
        "Aucune prédiction.*",
        "",
    ]
    for etude in etudes:
        if not etude.get("disponible"):
            lignes += [f"## {etude['ticker']}", "", f"Indisponible : {etude.get('raison')}.", ""]
            continue
        hold = etude["resultats"]["HOLD"]
        indice = etude.get("indice_reference") or {}
        lignes += [
            f"## {etude['ticker']} — achat du {hold['date_achat']} à {hold['prix_achat']:,.0f} FCFA".replace(",", " "),
            "",
            f"| Règle de sortie | Sortie | Performance | Séances | Motif |",
            "|---|---|---:|---:|---|",
        ]
        for nom in ("HOLD", "PER_PROPRE", "BANDE_PRIX", "STOP_12"):
            r = etude["resultats"].get(nom) or {}
            if not r.get("disponible"):
                continue
            lignes.append(
                f"| {r['regle_libelle']} | {r['date_sortie']} | **{r['performance_pct']:+.2f} %** | "
                f"{r['seances_detenues']} | {r['motif_sortie']} |"
            )
        if indice:
            lignes += [
                "",
                f"Référence : **{indice['indice']} {indice['performance_sur_meme_fenetre_pct']:+.2f} %** "
                f"du {indice['date_debut']} au {indice['date_fin']}. "
                f"Écart de la position gardée : **{etude['surplus_vs_indice_pct']:+.2f} points**.",
            ]
        lignes += [
            "",
            f"Amplitude traversée en gardant la position : plus haut "
            f"{hold['plus_haut_pct']:+.1f} %, plus bas {hold['plus_bas_pct']:+.1f} %.",
            "",
        ]
    lignes += [
        "## Limites",
        "",
        "- Prix publiés non ajustés : les dividendes ne sont pas comptés, donc la performance",
        "  réelle d'un actionnaire est supérieure à ces chiffres.",
        "- Ces seuils ont été écrits avant le calcul. Ils ne sont pas optimisés sur le résultat.",
        "- Rejouer le passé n'autorise aucune prévision.",
        "",
    ]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rejoue un achat et des règles de sortie.")
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--achat", default="2026-01-02")
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    archive = charger_archive(args.archive)
    etudes = [etude_complete(archive, t.upper(), args.achat) for t in args.tickers]

    if args.json:
        print(json.dumps(etudes, ensure_ascii=False, indent=2, default=str))
    else:
        print(rendre_markdown(etudes))
    return 0


if __name__ == "__main__":
    sys.exit(main())

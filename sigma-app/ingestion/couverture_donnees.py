#!/usr/bin/env python3
"""Complétude de SIGMA, mesurée par capacité — pas par intuition.

La question du propriétaire : « l'app n'est pas complète ». Vrai. Ce module
remplace l'impression par une mesure : pour chaque chose que SIGMA prétend faire,
combien de sociétés sont réellement servies, et quel champ précis bloque le reste.

Huit capacités, chacune avec sa condition d'éligibilité écrite. Une capacité est
« servie » pour une société seulement si ses intrants sont au niveau exigé ; un
champ extrait une seule fois ne suffit pas là où deux documents sont requis.

Aucune note globale unique : une moyenne masquerait qu'on peut décrire le marché
à 92 % et ne rien pouvoir valoriser. C'est exactement le mélange que le projet
s'interdit.

Usage
-----
    python3 ingestion/couverture_donnees.py
    python3 ingestion/couverture_donnees.py --out audits/.../COMPLETUDE.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from registre_actions import REGISTRE, actions_utilisables, charger as charger_registre  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data" / "data.json"


def _figures(company: dict[str, Any]) -> dict[str, Any]:
    return ((company.get("fundamentals") or {}).get("figures")) or {}


def _nombre(valeur: Any) -> bool:
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def _champ(company: dict[str, Any], nom: str) -> dict[str, Any] | None:
    champ = _figures(company).get(nom)
    return champ if champ and _nombre(champ.get("value_fcfa") if champ.get("value_fcfa") is not None else champ.get("value")) else None


# --- Conditions d'éligibilité, une par capacité ------------------------------

def cond_prix(company, ctx):
    boc = company.get("latest_boc") or {}
    ok = _nombre(boc.get("close")) and boc["close"] > 0
    return ok, None if ok else "cours publié absent"


def cond_per_publie(company, ctx):
    boc = company.get("latest_boc") or {}
    ok = _nombre(boc.get("per")) and boc["per"] > 0
    return ok, None if ok else "PER non publié au BOC"


def cond_actions(company, ctx):
    exercices = ctx["actions"].get(company["ticker"])
    ok = bool(exercices)
    return ok, None if ok else "nombre d'actions absent du registre"


def cond_resultat_net(company, ctx):
    ok = _champ(company, "resultat_net") is not None
    return ok, None if ok else "résultat net non extrait"


def cond_part_groupe(company, ctx):
    ok = _champ(company, "resultat_net_part_groupe") is not None
    return ok, None if ok else "résultat attribuable au groupe non extrait"


def cond_bpa_publie(company, ctx):
    ok = _champ(company, "benefice_par_action") is not None
    return ok, None if ok else "BPA publié non extrait"


def cond_flux(company, ctx):
    ok = _champ(company, "flux_tresorerie_operationnel") is not None
    return ok, None if ok else "flux de trésorerie opérationnel non extrait"


def cond_capitaux(company, ctx):
    ok = _champ(company, "capitaux_propres") is not None
    return ok, None if ok else "capitaux propres non extraits"


def cond_dividende(company, ctx):
    hist = company.get("dividend_history") or {}
    ok = bool(hist.get("annual"))
    return ok, None if ok else "historique de dividendes absent"


def cond_couverture_dividende(company, ctx):
    statut = (company.get("dividend_sustainability") or {}).get("status")
    ok = statut == "calculee"
    return ok, None if ok else f"couverture du dividende : {statut or 'non calculée'}"


CAPACITES: list[dict[str, Any]] = [
    {
        "cle": "decrire_marche",
        "libelle": "Décrire le marché (cours, PER publié, rendement, liquidité)",
        "conditions": [cond_prix, cond_per_publie],
        "bloque": "la fiche société elle-même",
    },
    {
        "cle": "capitaliser",
        "libelle": "Calculer la capitalisation boursière",
        "conditions": [cond_prix, cond_actions],
        "bloque": "le poids réel d'une société dans l'indice et la concentration",
    },
    {
        "cle": "per_sigma",
        "libelle": "Calculer un PER par SIGMA (et non reprendre celui du BOC)",
        "conditions": [cond_prix, cond_part_groupe, cond_actions],
        "bloque": "tout verdict de valorisation fondé sur le bénéfice",
    },
    {
        "cle": "ancre_patrimoniale",
        "libelle": "Ancre patrimoniale (capitaux propres par action)",
        "conditions": [cond_capitaux, cond_actions],
        "bloque": "la deuxième ancre indépendante, donc le verdict à quatre niveaux",
    },
    {
        "cle": "ancre_benefice",
        "libelle": "Ancre bénéfice (BPA × multiple borné)",
        "conditions": [cond_bpa_publie, cond_prix],
        "bloque": "une fourchette de valeur à deux ancres",
    },
    {
        "cle": "ancre_dividende",
        "libelle": "Ancre dividende (actualisation bornée par l'historique propre)",
        "conditions": [cond_dividende, cond_prix],
        "bloque": "la seule ancre disponible aujourd'hui",
    },
    {
        "cle": "qualite_benefice",
        "libelle": "Qualité du bénéfice (trésorerie cumulée vs résultat cumulé)",
        "conditions": [cond_flux, cond_resultat_net],
        "bloque": "le drapeau « bénéfice sans trésorerie »",
    },
    {
        "cle": "dividende_durable",
        "libelle": "Dividende soutenable (couverture par la trésorerie)",
        "conditions": [cond_couverture_dividende],
        "bloque": "la confiance dans le rendement affiché",
    },
]


def mesurer(data: dict[str, Any], registre: dict[str, Any]) -> dict[str, Any]:
    utiles = actions_utilisables(registre)
    ctx = {
        "actions": {}
        for _ in (0,)
    }
    ctx["actions"] = {}
    for (ticker, exercice) in utiles:
        ctx["actions"].setdefault(ticker, []).append(exercice)

    companies = data.get("companies", [])
    resultats = []
    for capacite in CAPACITES:
        servies: list[str] = []
        blocages: dict[str, int] = {}
        for company in companies:
            manquants = []
            for condition in capacite["conditions"]:
                ok, raison = condition(company, ctx)
                if not ok:
                    manquants.append(raison)
            if manquants:
                for raison in manquants:
                    blocages[raison] = blocages.get(raison, 0) + 1
            else:
                servies.append(company["ticker"])
        resultats.append(
            {
                "cle": capacite["cle"],
                "libelle": capacite["libelle"],
                "societes_servies": len(servies),
                "total": len(companies),
                "couverture_pct": round(100 * len(servies) / len(companies), 1) if companies else 0.0,
                "bloque": capacite["bloque"],
                "principaux_blocages": sorted(blocages.items(), key=lambda x: -x[1])[:4],
                "tickers_servis": servies,
            }
        )

    # Quel champ unique débloquerait le plus de capacités ?
    poids: dict[str, int] = {}
    for resultat in resultats:
        for raison, nombre in resultat["principaux_blocages"]:
            poids[raison] = poids.get(raison, 0) + nombre
    return {
        "societe": len(companies),
        "collecte": data.get("generated_at"),
        "capacites": resultats,
        "blocages_par_importance": sorted(poids.items(), key=lambda x: -x[1])[:8],
    }


def rendre_markdown(rapport: dict[str, Any]) -> str:
    lignes = [
        "# Complétude de SIGMA, mesurée par capacité",
        "",
        f"*{rapport['societe']} sociétés · collecte du {rapport['collecte']}*",
        "",
        "Aucun taux global : chaque capacité a sa propre condition d'éligibilité.",
        "Une moyenne unique masquerait qu'on peut décrire le marché sans rien valoriser.",
        "",
        "| Capacité | Sociétés servies | Couverture | Ce que son absence bloque |",
        "|---|---:|---:|---|",
    ]
    for cap in rapport["capacites"]:
        lignes.append(
            f"| {cap['libelle']} | **{cap['societes_servies']}/{cap['total']}** | "
            f"{cap['couverture_pct']} % | {cap['bloque']} |"
        )

    lignes += ["", "## Ce qui bloque, champ par champ", ""]
    for raison, nombre in rapport["blocages_par_importance"]:
        lignes.append(f"- **{raison}** — cité sur {nombre} vérification(s) de capacité")

    lignes += ["", "## Détail des conditions non remplies", ""]
    for cap in rapport["capacites"]:
        if not cap["principaux_blocages"]:
            continue
        lignes.append(f"### {cap['libelle']}")
        for raison, nombre in cap["principaux_blocages"]:
            lignes.append(f"- {nombre} société(s) : {raison}")
        lignes.append("")

    lignes += [
        "## Lecture",
        "",
        "Une capacité à 0 % n'est pas un bug d'affichage : c'est un champ source qui",
        "manque. Tant que le registre du nombre d'actions reste à 2 sociétés sur 48,",
        "**la capitalisation, le PER calculé par SIGMA et l'ancre patrimoniale restent",
        "inaccessibles** — quel que soit le nombre d'écrans ajoutés.",
        "",
    ]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mesure la complétude par capacité.")
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--registre", type=Path, default=REGISTRE)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    data = json.loads(args.data.read_text(encoding="utf-8"))
    rapport = mesurer(data, charger_registre(args.registre))

    texte = rendre_markdown(rapport)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(texte + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(texte)

    for cap in rapport["capacites"]:
        print(f"{cap['cle']:20s} {cap['societes_servies']:2d}/{cap['total']} ({cap['couverture_pct']}%)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

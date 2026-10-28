#!/usr/bin/env python3
"""Registre du nombre d'actions — le verrou de la valorisation.

Pourquoi ce registre existe
--------------------------
Sans nombre d'actions, SIGMA ne peut produire ni capitalisation, ni BPA
recalculé, ni valeur patrimoniale, ni PER calculé. C'est aujourd'hui le trou le
plus coûteux du projet : 2 sociétés sur 48. Le nombre d'actions n'est pourtant
pas une donnée rare — c'est un fait juridique publié par chaque émetteur.

Ce module tient donc un registre **avec preuve** : chaque entrée porte le
document, la page, la ligne lue, la date et le niveau de vérification. Une entrée
sans preuve n'existe pas.

Trois niveaux, jamais confondus
-------------------------------
1. `CONFIRME_DEUX_DOCUMENTS` — deux documents distincts donnent le même nombre.
2. `LU_DANS_UN_DOCUMENT` — lecture unique, preuve citée. Utilisable pour une
   capitalisation indicative, **jamais** pour un BPA comparable.
3. `CANDIDAT_A_VERIFIER` — nombre repéré mais ambigu (unité, périmètre, date).
   Compté séparément, n'alimente aucun calcul.

Une capitalisation n'est publiée que sur les niveaux 1 et 2, avec le niveau
affiché. Un BPA recalculé exige en plus le nombre **moyen pondéré**, qui est un
autre champ : ce registre ne le remplace pas.

Usage
-----
    python3 ingestion/registre_actions.py --statut
    python3 ingestion/registre_actions.py --capitalisations
    python3 ingestion/registre_actions.py --manquants
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data" / "data.json"
REGISTRE = ROOT / "ingestion" / "registre_actions.json"

EXERCICES = tuple(range(2016, 2026))

NIVEAU_CONFIRME = "CONFIRME_DEUX_DOCUMENTS"
NIVEAU_LU = "LU_DANS_UN_DOCUMENT"
NIVEAU_CANDIDAT = "CANDIDAT_A_VERIFIER"
NIVEAUX_UTILISABLES = (NIVEAU_CONFIRME, NIVEAU_LU)


def charger(chemin: Path = REGISTRE) -> dict[str, Any]:
    with chemin.open(encoding="utf-8") as handle:
        return json.load(handle)


def ecrire(registre: dict[str, Any], chemin: Path = REGISTRE) -> None:
    chemin.write_text(
        json.dumps(registre, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def valider_entree(entree: dict[str, Any]) -> list[str]:
    """Contrôles bloquants. Une entrée qui échoue ne doit pas entrer au registre."""
    erreurs: list[str] = []
    ticker = entree.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        erreurs.append("ticker absent")
    exercice = entree.get("exercice")
    if not isinstance(exercice, int) or exercice not in EXERCICES:
        erreurs.append(f"exercice hors périmètre 2016-2025 : {exercice!r}")

    actions = entree.get("actions")
    if not isinstance(actions, int) or isinstance(actions, bool):
        erreurs.append(f"nombre d'actions doit être un entier : {actions!r}")
    elif actions <= 0:
        erreurs.append(f"nombre d'actions non positif : {actions}")

    niveau = entree.get("niveau")
    if niveau not in (NIVEAU_CONFIRME, NIVEAU_LU, NIVEAU_CANDIDAT):
        erreurs.append(f"niveau inconnu : {niveau!r}")

    preuve = entree.get("preuve") or {}
    if niveau in NIVEAUX_UTILISABLES:
        if not preuve.get("document"):
            erreurs.append("preuve.document manquant : une valeur sans document n'entre pas")
        if not preuve.get("page"):
            erreurs.append("preuve.page manquante")
        if not preuve.get("ligne"):
            erreurs.append("preuve.ligne manquante (extrait exact de la ligne lue)")
    if niveau == NIVEAU_CONFIRME:
        documents = preuve.get("documents") or []
        if len({d for d in documents if d}) < 2:
            erreurs.append(
                "CONFIRME_DEUX_DOCUMENTS exige deux documents distincts dans preuve.documents"
            )

    if entree.get("derive") and not entree.get("evenement_source"):
        erreurs.append("entrée dérivée sans evenement_source identifié")
    return erreurs


def actions_utilisables(registre: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    utiles: dict[tuple[str, int], dict[str, Any]] = {}
    for entree in registre.get("entrees", []):
        if entree.get("niveau") in NIVEAUX_UTILISABLES and not valider_entree(entree):
            utiles[(entree["ticker"], entree["exercice"])] = entree
    return utiles


def couverture(registre: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Couverture par société, et impact sur ce que SIGMA peut calculer."""
    tickers = sorted({c["ticker"] for c in data.get("companies", [])})
    utiles = actions_utilisables(registre)
    par_societe: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        exercices = sorted(ex for (t, ex) in utiles if t == ticker)
        par_societe[ticker] = {
            "exercices_couverts": exercices,
            "nb_exercices": len(exercices),
            "complet_2016_2025": len(exercices) == len(EXERCICES),
            "couverture_pct": round(100 * len(exercices) / len(EXERCICES), 1),
        }

    par_niveau = Counter(e.get("niveau") for e in registre.get("entrees", []))
    return {
        "societes": len(tickers),
        "entrees_valides": len(utiles),
        "entrees_totales": len(registre.get("entrees", [])),
        "par_niveau": dict(par_niveau),
        "societes_avec_au_moins_une_annee": sum(
            1 for v in par_societe.values() if v["nb_exercices"]
        ),
        "societes_completes_2016_2025": sum(
            1 for v in par_societe.values() if v["complet_2016_2025"]
        ),
        "detail": par_societe,
    }


def capitalisations(
    registre: dict[str, Any], data: dict[str, Any], exercice: int | None = None
) -> list[dict[str, Any]]:
    """Capitalisation = dernier cours publié × nombre d'actions, niveau affiché."""
    utiles = actions_utilisables(registre)
    lignes: list[dict[str, Any]] = []
    for company in data.get("companies", []):
        ticker = company["ticker"]
        boc = company.get("latest_boc") or {}
        prix = boc.get("close")
        if not isinstance(prix, (int, float)) or prix <= 0:
            continue
        annees = sorted(
            (ex for (t, ex) in utiles if t == ticker), reverse=True
        )
        if exercice is not None:
            annees = [ex for ex in annees if ex == exercice]
        if not annees:
            continue
        annee = annees[0]
        entree = utiles[(ticker, annee)]
        lignes.append(
            {
                "ticker": ticker,
                "nom": company.get("name"),
                "exercice_actions": annee,
                "actions": entree["actions"],
                "cours_fcfa": prix,
                "capitalisation_fcfa": round(entree["actions"] * prix, 0),
                "niveau_preuve": entree["niveau"],
                "date_cours": company.get("latest_boc_date"),
                "avertissement": (
                    "cours du jour × actions d'un exercice antérieur : approximation "
                    "explicite, pas une capitalisation officielle"
                    if annee < EXERCICES[-1]
                    else None
                ),
            }
        )
    return sorted(lignes, key=lambda x: -x["capitalisation_fcfa"])


def manquants(data: dict[str, Any], registre: dict[str, Any]) -> list[dict[str, Any]]:
    """Sociétés dont l'absence d'actions bloque un calcul, par priorité d'usage.

    Priorité : celles qui ont déjà un résultat net publié et un cours — il ne
    leur manque QUE le nombre d'actions pour devenir capitalisables.
    """
    utiles = actions_utilisables(registre)
    sans_actions = {
        c["ticker"] for c in data.get("companies", []) if not any(t == c["ticker"] for t, _ in utiles)
    }
    priorites = []
    for company in data.get("companies", []):
        ticker = company["ticker"]
        if ticker not in sans_actions:
            continue
        figures = ((company.get("fundamentals") or {}).get("figures")) or {}
        boc = company.get("latest_boc") or {}
        priorites.append(
            {
                "ticker": ticker,
                "nom": company.get("name"),
                "a_resultat_net": "resultat_net" in figures,
                "a_resultat_part_groupe": "resultat_net_part_groupe" in figures,
                "a_cours": isinstance(boc.get("close"), (int, float)),
                "documents_indexes": len(company.get("documents") or []),
                "score_deblocage": (
                    3 * ("resultat_net" in figures)
                    + 2 * ("resultat_net_part_groupe" in figures)
                    + 1 * isinstance(boc.get("close"), (int, float))
                ),
            }
        )
    return sorted(priorites, key=lambda x: (-x["score_deblocage"], -x["documents_indexes"]))


def rendre_markdown(rapport: dict[str, Any]) -> str:
    cov = rapport["couverture"]
    lignes = [
        "# Registre du nombre d'actions — état et couverture",
        "",
        f"*Généré le {rapport['date']} · source des cours : collecte du {rapport['collecte']}*",
        "",
        "## Où en est le verrou",
        "",
        f"- Sociétés au registre avec une valeur utilisable : "
        f"**{cov['societes_avec_au_moins_une_annee']}/{cov['societes']}**",
        f"- Sociétés couvertes sur les 10 exercices : **{cov['societes_completes_2016_2025']}/{cov['societes']}**",
        f"- Entrées validées : {cov['entrees_valides']} sur {cov['entrees_totales']} déclarées",
        "",
        "| Niveau de preuve | Entrées |",
        "|---|---:|",
    ]
    for niveau, nombre in sorted(cov["par_niveau"].items()):
        lignes.append(f"| `{niveau}` | {nombre} |")

    lignes += ["", "## Détail par société", "", "| Société | Exercices couverts | Couverture |", "|---|---:|---:|"]
    for ticker, info in sorted(cov["detail"].items()):
        exercices = ", ".join(str(e) for e in info["exercices_couverts"]) or "aucun"
        lignes.append(f"| {ticker} | {exercices} | {info['couverture_pct']} % |")

    lignes += ["", "## Capitalisations calculables aujourd'hui", ""]
    if rapport["capitalisations"]:
        lignes += ["| Société | Actions | Exercice | Cours | Capitalisation | Preuve |", "|---|---:|---:|---:|---:|---|"]
        for ligne in rapport["capitalisations"]:
            lignes.append(
                f"| {ligne['ticker']} | {ligne['actions']:,} | {ligne['exercice_actions']} | "
                f"{ligne['cours_fcfa']:,.0f} | {ligne['capitalisation_fcfa']:,.0f} | "
                f"{ligne['niveau_preuve']} |".replace(",", " ")
            )
    else:
        lignes.append("Aucune. C'est le chiffre qui dit tout : **0 capitalisation calculable**.")

    lignes += [
        "",
        "## File d'extraction prioritaire",
        "",
        "Sociétés qui n'ont besoin QUE du nombre d'actions pour devenir capitalisables",
        "(cours publié + résultat net déjà extrait) :",
        "",
        "| Rang | Société | Résultat net | Part du groupe | Documents |",
        "|---:|---|---|---|---:|",
    ]
    for rang, item in enumerate(rapport["manquants"][:20], start=1):
        lignes.append(
            f"| {rang} | {item['ticker']} — {item['nom'][:34]} | "
            f"{'oui' if item['a_resultat_net'] else 'non'} | "
            f"{'oui' if item['a_resultat_part_groupe'] else 'non'} | "
            f"{item['documents_indexes']} |"
        )

    lignes += [
        "",
        "## Règles tenues",
        "",
        "- Aucune valeur sans document, page et ligne lue.",
        "- Une lecture unique alimente une capitalisation indicative, jamais un BPA comparable.",
        "- Le nombre **moyen pondéré** d'actions est un autre champ : ce registre ne le remplace pas.",
        "- Une valeur déduite d'un événement (fractionnement sourcé) est marquée `derive` et comptée à part.",
        "",
    ]
    return "\n".join(lignes)


def rapport_complet(registre_path: Path = REGISTRE, data_path: Path = DATA) -> dict[str, Any]:
    registre = charger(registre_path)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    return {
        "date": registre.get("date"),
        "collecte": data.get("generated_at"),
        "couverture": couverture(registre, data),
        "capitalisations": capitalisations(registre, data),
        "manquants": manquants(data, registre),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Registre du nombre d'actions.")
    parser.add_argument("--registre", type=Path, default=REGISTRE)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--statut", action="store_true")
    parser.add_argument("--capitalisations", action="store_true")
    parser.add_argument("--manquants", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    rapport = rapport_complet(args.registre, args.data)
    cov = rapport["couverture"]

    if args.capitalisations:
        for ligne in rapport["capitalisations"]:
            print(
                f"{ligne['ticker']:6s} {ligne['actions']:>12,} actions ({ligne['exercice_actions']}) "
                f"× {ligne['cours_fcfa']:>8,.0f} = {ligne['capitalisation_fcfa']:>16,.0f} FCFA "
                f"[{ligne['niveau_preuve']}]".replace(",", " ")
            )
        if not rapport["capitalisations"]:
            print("aucune capitalisation calculable")
        return 0

    if args.manquants:
        for item in rapport["manquants"]:
            print(
                f"{item['ticker']:6s} score {item['score_deblocage']} · "
                f"RN={'oui' if item['a_resultat_net'] else 'non'} · "
                f"part={'oui' if item['a_resultat_part_groupe'] else 'non'} · "
                f"docs={item['documents_indexes']}"
            )
        return 0

    texte = rendre_markdown(rapport)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(texte + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(texte)
    print(
        f"\n{cov['societes_avec_au_moins_une_annee']}/{cov['societes']} sociétés couvertes · "
        f"{len(rapport['capitalisations'])} capitalisation(s) calculable(s)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

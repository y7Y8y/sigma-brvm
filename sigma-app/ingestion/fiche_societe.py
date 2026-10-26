#!/usr/bin/env python3
"""Fiche société en une page — la réponse que SIGMA peut réellement donner.

But : répondre, pour une société et en une page, aux questions qu'une formation
payante enseigne — activité, ce que le prix implique, ce qu'elle gagne, solidité,
dividende et sa couverture, liquidité, ce qui invaliderait la thèse — **et nommer
ses trous**.

Règles tenues par ce module
---------------------------
1. Aucune valeur inventée. Un champ absent est affiché « non disponible » avec
   la raison, jamais comblé par une estimation.
2. Le PER affiché est celui **publié par la BRVM** dans le BOC, avec sa date. Il
   n'est jamais présenté comme un calcul SIGMA.
3. Un verdict de valorisation exige **au moins deux ancres indépendantes**. Avec
   une seule ancre, le module affiche la fourchette indicative de cette ancre et
   refuse le verdict — c'est le cas de 44 sociétés sur 48 aujourd'hui.
4. Le taux d'actualisation est un paramètre **visible** : taux directeur BCEAO du
   jour + prime d'exigence affichée. Sa sensibilité ±1 point est toujours montrée.
5. Les scénarios de croissance du dividende sont bornés par l'**historique propre**
   de la société : jamais d'extrapolation libre.

Usage
-----
    python3 ingestion/fiche_societe.py SNTS
    python3 ingestion/fiche_societe.py SNTS --quantite 200000 --out /tmp/fiches
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data" / "data.json"

#: Prime d'exigence par défaut, en points de pourcentage, ajoutée au taux
#: directeur BCEAO. Valeur affichée dans chaque fiche et modifiable en paramètre.
PRIME_EXIGENCE_DEFAUT = 8.0

#: Bornes de croissance : on n'extrapole jamais au-delà de ce que la société a
#: déjà fait, et on ne laisse pas Gordon diverger (g doit rester sous r).
CROISSANCE_PLANCHER = -10.0
CROISSANCE_PLAFOND = 8.0

VERDICTS = {
    "ZONE_ETUDE_PRIORITAIRE": "Zone d'étude prioritaire",
    "SANS_MARGE_PARTICULIERE": "Sans marge particulière",
    "PRIX_SANS_MARGE": "Prix sans marge — même si l'entreprise est de qualité",
    "NON_CALCULABLE": "Non calculable",
}


def _num(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return None


def charger(chemin: Path = DATA) -> dict[str, Any]:
    with chemin.open(encoding="utf-8") as handle:
        return json.load(handle)


def societe(data: dict[str, Any], ticker: str) -> dict[str, Any]:
    for entreprise in data.get("companies", []):
        if entreprise.get("ticker", "").upper() == ticker.upper():
            return entreprise
    raise SystemExit(f"société inconnue : {ticker}")


def taux_actualisation(macro: dict[str, Any], prime_points: float = PRIME_EXIGENCE_DEFAUT) -> dict[str, Any]:
    """Taux d'actualisation visible : taux directeur BCEAO + prime affichée."""
    cpm = (macro or {}).get("bceao_cpm") or {}
    taux_directeur = _num(cpm.get("policy_rate_pct"))
    if taux_directeur is None:
        return {
            "calculable": False,
            "raison": "taux directeur BCEAO absent de la collecte",
            "prime_points": prime_points,
        }
    return {
        "calculable": True,
        "taux_directeur_pct": taux_directeur,
        "taux_directeur_date": cpm.get("published_date"),
        "taux_directeur_source": cpm.get("source_label"),
        "prime_points": prime_points,
        "taux_requis_pct": round(taux_directeur + prime_points, 2),
        "sensibilite": [
            round(taux_directeur + prime_points + delta, 2) for delta in (-1.0, 0.0, 1.0)
        ],
    }


def serie_dividendes(dividende: dict[str, Any]) -> list[tuple[int, float]]:
    """Série (exercice, dividende net par action) triée, sans trou."""
    serie = []
    for ligne in dividende.get("annual") or []:
        exercice = _num(ligne.get("fiscal_year"))
        montant = _num(ligne.get("net_amount_fcfa"))
        if exercice is None or montant is None or montant <= 0:
            continue
        serie.append((int(exercice), montant))
    return sorted(serie)


def croissances_observees(serie: list[tuple[int, float]]) -> list[float]:
    """Croissances annuelles du dividende, **brutes**, sur la série propre.

    Le bornage est appliqué scénario par scénario, pas ici : borner avant de prendre
    le minimum, la médiane et le maximum écraserait la distribution observée et
    produirait un scénario « optimiste » identique au « central » par artefact.
    """
    croissances = []
    for (annee_prec, montant_prec), (annee, montant) in zip(serie, serie[1:]):
        if annee != annee_prec + 1 or montant_prec <= 0:
            continue
        croissances.append((montant / montant_prec - 1.0) * 100.0)
    return croissances


def valeur_gordon(dividende: float, croissance_pct: float, taux_pct: float) -> float | None:
    """Valeur par actualisation du dividende. Refusée si le dénominateur n'a pas de sens."""
    g = croissance_pct / 100.0
    r = taux_pct / 100.0
    if r - g <= 0.005:  # moins d'un demi-point d'écart : résultat explosif, donc refusé
        return None
    return dividende * (1.0 + g) / (r - g)


def ancre_dividende(
    dividende: dict[str, Any], taux: dict[str, Any], prix: float | None
) -> dict[str, Any]:
    """Fourchette de valeur par la seule ancre dividende, bornée par l'historique."""
    serie = serie_dividendes(dividende)
    if len(serie) < 3:
        return {
            "calculable": False,
            "raison": f"série de dividendes trop courte ({len(serie)} exercice(s) avec montant)",
        }
    if not taux.get("calculable"):
        return {"calculable": False, "raison": taux.get("raison", "taux indisponible")}

    dernier_exercice, dernier_montant = serie[-1]
    croissances = croissances_observees(serie)
    if not croissances:
        return {"calculable": False, "raison": "aucune croissance annuelle calculable (années discontinues)"}

    taux_requis = taux["taux_requis_pct"]
    observes = {
        # Le scénario pessimiste ne peut pas être une croissance positive : sinon il
        # n'est pas pessimiste. On retient donc le pire des deux : pire année observée
        # ou stagnation.
        "pessimiste": min(min(croissances), 0.0),
        "central": statistics.median(croissances),
        "optimiste": max(croissances),
    }
    scenarios_def = {
        nom: max(CROISSANCE_PLANCHER, min(CROISSANCE_PLAFOND, valeur))
        for nom, valeur in observes.items()
    }
    bornes_atteintes = {
        nom: (abs(valeur - observes[nom]) > 1e-9) for nom, valeur in scenarios_def.items()
    }
    # Une société qui croît plus vite que le plafond prudent voit ses scénarios se
    # resserrer. On ne le cache pas : on le dit, car l'ancre sous-estime alors la valeur.
    scenarios_confondus = len(set(round(v, 4) for v in scenarios_def.values())) < 3
    scenarios: dict[str, Any] = {}
    for nom, croissance in scenarios_def.items():
        for delta in (-1.0, 0.0, 1.0):
            valeur = valeur_gordon(dernier_montant, croissance, taux_requis + delta)
            if valeur is None:
                scenarios.setdefault(nom, {})[f"{delta:+.0f}_pt"] = None
            else:
                scenarios.setdefault(nom, {})[f"{delta:+.0f}_pt"] = round(valeur, 2)

    centrales = {
        nom: (vals.get("+0_pt") if vals else None) for nom, vals in
        ((nom, scenarios.get(nom)) for nom in scenarios_def)
    }
    definies = [v for v in centrales.values() if v]
    resultat: dict[str, Any] = {
        "calculable": True,
        "ancre": "dividende",
        "dernier_exercice": dernier_exercice,
        "dernier_dividende_net_fcfa": dernier_montant,
        "croissances_observees_pct": [round(c, 2) for c in croissances],
        "scenarios_croissance_pct": {k: round(v, 2) for k, v in scenarios_def.items()},
        "croissances_observees_brutes_pct": {k: round(v, 2) for k, v in observes.items()},
        "borne_atteinte": bornes_atteintes,
        "scenarios_confondus": scenarios_confondus,
        "note_scenarios": (
            "La croissance observée dépasse le plafond prudent : les scénarios se resserrent "
            "et cette ancre sous-estime la valeur d'une société en forte croissance."
            if scenarios_confondus
            else "Trois scénarios distincts, bornés par l'historique propre de la société."
        ),
        "taux_requis_pct": taux_requis,
        "valeurs_par_scenario": scenarios,
        "fourchette_fcfa": [min(definies), max(definies)] if definies else None,
        "bornes": {
            "croissance_planchee_pct": CROISSANCE_PLANCHER,
            "croissance_plafonnee_pct": CROISSANCE_PLAFOND,
            "regle": "croissance bornée par l'historique propre de la société ; jamais d'extrapolation libre",
        },
    }
    if prix and definies:
        resultat["position_du_prix"] = {
            "prix": prix,
            "sous_valeur_pessimiste": prix <= min(definies),
            "au_dessus_valeur_optimiste": prix >= max(definies),
        }
    return resultat


#: Au-delà de cet écart, le dividende affiché et le rendement affiché ne parlent
#: pas du même montant : on ne construit aucun calcul dessus.
ECART_COHERENCE_MAX_PCT = 2.0


def controle_coherence_dividende(prix: float | None, dividende: float | None, rendement_pct: float | None) -> dict[str, Any]:
    """Le dividende affiché doit concorder avec le rendement affiché.

    Quand un émetteur publie dans une autre devise, ou qu'un montant est saisi dans
    une mauvaise unité, le dividende et le rendement divergent. Construire une
    valorisation sur des intrants incohérents produirait un chiffre faux : on refuse
    et on le dit.
    """
    if not prix or not dividende or not rendement_pct:
        return {"verifiable": False, "raison": "cours, dividende ou rendement absent"}
    implicite = prix * rendement_pct / 100.0
    ecart = (dividende / implicite - 1.0) * 100.0
    return {
        "verifiable": True,
        "dividende_affiche_fcfa": dividende,
        "dividende_implicite_du_rendement_fcfa": round(implicite, 2),
        "ecart_pct": round(ecart, 2),
        "coherent": abs(ecart) <= ECART_COHERENCE_MAX_PCT,
    }


def test_sortie(prix: float | None, quantite: float | None, mediane_fcfa: float | None) -> dict[str, Any]:
    """Nombre de séances de volume médian nécessaires pour sortir sans dominer le marché."""
    if not prix or not quantite or not mediane_fcfa:
        return {"calculable": False, "raison": "prix, quantité ou liquidité médiane indisponible"}
    montant = prix * quantite
    return {
        "calculable": True,
        "montant_ordre_fcfa": round(montant, 0),
        "valeur_mediane_seance_fcfa": round(mediane_fcfa, 0),
        "part_dune_seance_mediane_pct": round(100 * montant / mediane_fcfa, 2),
        "seances_pour_sortir": round(montant / mediane_fcfa, 2),
        "lecture": (
            "moins d'une séance de volume médian"
            if montant <= mediane_fcfa
            else f"environ {round(montant / mediane_fcfa, 1)} séances de volume médian"
        ),
    }


def verdict(ancres: dict[str, Any]) -> dict[str, Any]:
    """Verdict à quatre niveaux. Refusé tant que deux ancres ne sont pas disponibles."""
    disponibles = [nom for nom, ancre in ancres.items() if ancre.get("calculable")]
    if len(disponibles) < 2:
        return {
            "code": "NON_CALCULABLE",
            "libelle": VERDICTS["NON_CALCULABLE"],
            "ancres_disponibles": disponibles,
            "raison": (
                f"une seule ancre indépendante disponible ({disponibles[0]}) : le projet exige "
                "au moins deux ancres pour prononcer un verdict"
                if disponibles
                else "aucune ancre indépendante disponible"
            ),
        }
    return {
        "code": "NON_CALCULABLE",
        "libelle": VERDICTS["NON_CALCULABLE"],
        "ancres_disponibles": disponibles,
        "raison": "règle de marge de sécurité non encore branchée sur plusieurs ancres",
    }


def conditions_invalidation(entreprise: dict[str, Any]) -> list[str]:
    """Ce qui, documenté, invaliderait la thèse. Aucune de ces lignes n'est une prévision."""
    conditions = []
    dividende = entreprise.get("dividend_history") or {}
    coupes = _num(dividende.get("cuts_count"))
    if coupes:
        conditions.append(
            f"Dividende coupé : {int(coupes)} coupure(s) déjà observée(s) dans l'historique officiel."
        )
    if _num(dividende.get("latest_net_amount_fcfa")):
        conditions.append(
            "Dividende réduit ou supprimé par rapport au dernier exercice payé "
            f"({dividende.get('latest_paid_fiscal_year')})."
        )
    figures = ((entreprise.get("fundamentals") or {}).get("figures")) or {}
    if "resultat_net" in figures:
        conditions.append("Résultat net négatif nouvellement publié.")
    if "capitaux_propres" in figures and "total_bilan" in figures:
        conditions.append(
            "Capitaux propres passant sous le seuil écrit du profil (coussin bilan dégradé)."
        )
    conditions.append("Publication officielle majeure rattachée à la société.")
    conditions.append("PER ou rendement devenant non interprétables (bénéfice négatif, dividende suspendu).")
    return conditions


def ce_que_sigma_ne_sait_pas(entreprise: dict[str, Any]) -> list[str]:
    trous = []
    figures = ((entreprise.get("fundamentals") or {}).get("figures")) or {}
    if "benefice_par_action" not in figures:
        trous.append("BPA vérifié : absent des sources examinées pour cette société.")
    if "nombre_actions_fin_exercice" not in figures:
        trous.append("Nombre d'actions vérifié : absent — donc aucune capitalisation ni BPA recalculé.")
    if "flux_tresorerie_operationnel" not in figures:
        trous.append("Flux de trésorerie opérationnel : absent — la couverture du dividende par la trésorerie ne peut pas être calculée.")
    viabilite = (entreprise.get("dividend_sustainability") or {}).get("status")
    if viabilite and viabilite != "calculee":
        trous.append(f"Couverture du dividende : {viabilite.replace('_', ' ')}.")
    if not entreprise.get("dividend_history"):
        trous.append("Historique de dividendes : non documenté.")
    return trous or ["Aucun trou majeur identifié dans les champs vérifiés par SIGMA."]


def construire_fiche(
    data: dict[str, Any],
    ticker: str,
    quantite: float | None = None,
    prime_points: float = PRIME_EXIGENCE_DEFAUT,
) -> dict[str, Any]:
    entreprise = societe(data, ticker)
    boc = entreprise.get("latest_boc") or {}
    stats = entreprise.get("history_stats") or {}
    long_hist = stats.get("long_history") or {}
    figures = ((entreprise.get("fundamentals") or {}).get("figures")) or {}

    prix = _num(boc.get("close")) or _num((entreprise.get("latest_quote") or {}).get("close"))
    mediane = _num(stats.get("median_traded_value_last_20_fcfa")) or _num(
        long_hist.get("median_traded_value_fcfa")
    )
    taux = taux_actualisation(data.get("macro_context") or {}, prime_points)

    dividende_affiche = _num(boc.get("last_net_dividend_fcfa"))
    rendement_affiche = _num(boc.get("net_dividend_yield_pct"))
    coherence = controle_coherence_dividende(prix, dividende_affiche, rendement_affiche)

    ancre_dividende_resultat = ancre_dividende(
        entreprise.get("dividend_history") or {}, taux, prix
    )
    if coherence.get("verifiable") and not coherence.get("coherent"):
        ancre_dividende_resultat = {
            "calculable": False,
            "raison": (
                "intrants incohérents : le dividende affiché "
                f"({_fmt_fcfa(dividende_affiche)}) ne concorde pas avec le rendement publié "
                f"({_fmt_pct(rendement_affiche)}, soit {_fmt_fcfa(coherence['dividende_implicite_du_rendement_fcfa'])}). "
                "Devise ou unité à vérifier avant tout calcul."
            ),
        }

    ancres = {
        "dividende": ancre_dividende_resultat,
        "benefice": {
            "calculable": False,
            "raison": "BPA vérifié et nombre d'actions moyen pondéré indisponibles",
        },
        "patrimoniale": {
            "calculable": False,
            "raison": "nombre d'actions vérifié indisponible",
        },
    }

    return {
        "schema_version": "sigma-fiche-societe-v1",
        "ticker": entreprise.get("ticker"),
        "nom": entreprise.get("name"),
        "secteur": entreprise.get("sector"),
        "date_collecte": data.get("generated_at"),
        "date_derniere_seance": entreprise.get("latest_boc_date"),
        "marche": {
            "cours_fcfa": prix,
            "per_publie_boc": _num(boc.get("per")),
            "per_source": "publié par la BRVM dans le BOC — pas un calcul SIGMA",
            "rendement_net_pct": _num(boc.get("net_dividend_yield_pct")),
            "dernier_dividende_net_fcfa": _num(boc.get("last_net_dividend_fcfa")),
            "seances_echangees_20": _num(stats.get("traded_sessions_last_20")),
            "valeur_mediane_20_fcfa": _num(stats.get("median_traded_value_last_20_fcfa")),
            "performance_250_seances_pct": _num(long_hist.get("performance_250_sessions_pct")),
            "performance_libelle": "prix seuls, sans ajustement des opérations sur titres",
            "volatilite_annualisee_pct": _num(long_hist.get("volatility_annualized_pct")),
            "max_drawdown_pct": _num(long_hist.get("max_drawdown_pct")),
        },
        "resultats_publies": {
            nom: {
                "valeur_fcfa": _num(champ.get("value_fcfa") or champ.get("value")),
                "confiance": champ.get("confidence"),
                "documents_confirmants": champ.get("documents_confirmants"),
            }
            for nom, champ in figures.items()
        },
        "dividende": {
            "statut": (entreprise.get("dividend_history") or {}).get("status"),
            "source": (entreprise.get("dividend_history") or {}).get("source"),
            "exercices_payes": _num((entreprise.get("dividend_history") or {}).get("paid_fiscal_years_count")),
            "annees_consecutives": _num((entreprise.get("dividend_history") or {}).get("current_consecutive_paid_years")),
            "coupures": _num((entreprise.get("dividend_history") or {}).get("cuts_count")),
            "hausses": _num((entreprise.get("dividend_history") or {}).get("increases_count")),
            "cagr_pct": _num((entreprise.get("dividend_history") or {}).get("dividend_cagr_pct")),
            "serie": serie_dividendes(entreprise.get("dividend_history") or {}),
        },
        "coherence_dividende": coherence,
        "taux_actualisation": taux,
        "ancres": ancres,
        "verdict": verdict(ancres),
        "test_sortie": test_sortie(prix, quantite, mediane),
        "invalidation": conditions_invalidation(entreprise),
        "trous": ce_que_sigma_ne_sait_pas(entreprise),
        "portee": (
            "Fiche factuelle. Elle ne dit ni d'acheter ni de vendre, ne passe aucun ordre "
            "et n'anticipe pas les cours."
        ),
    }


def _fmt_fcfa(valeur: Any, suffixe: str = " FCFA") -> str:
    if valeur is None:
        return "non disponible"
    if not isinstance(valeur, (int, float)):
        return str(valeur)
    if abs(valeur) >= 1000:
        return f"{valeur:,.0f}".replace(",", " ") + suffixe
    return f"{valeur:,.2f}".replace(",", " ") + suffixe


def _fmt_pct(valeur: Any) -> str:
    if valeur is None:
        return "non disponible"
    if not isinstance(valeur, (int, float)):
        return str(valeur)
    return f"{valeur:,.2f}".replace(",", " ") + " %"


def _fmt_entier(valeur: Any) -> str:
    if valeur is None:
        return "non disponible"
    if not isinstance(valeur, (int, float)):
        return str(valeur)
    if float(valeur).is_integer():
        return f"{int(valeur):,}".replace(",", " ")
    return f"{valeur:,.2f}".replace(",", " ")


def _fmt_ratio(valeur: Any) -> str:
    if valeur is None:
        return "non disponible"
    if not isinstance(valeur, (int, float)):
        return str(valeur)
    return f"{valeur:,.2f}".replace(",", " ")


def rendre_markdown(fiche: dict[str, Any]) -> str:
    m = fiche["marche"]
    a = fiche["ancres"]["dividende"]
    v = fiche["verdict"]
    t = fiche["test_sortie"]
    lignes = [
        f"# {fiche['ticker']} — {fiche['nom']}",
        "",
        f"*{fiche['secteur']} · collecte du {fiche['date_collecte']} · dernière séance "
        f"{fiche['date_derniere_seance']}*",
        "",
        "## 1 · Ce que le prix implique",
        "",
        f"- Cours : **{_fmt_fcfa(m['cours_fcfa'])}**",
        f"- PER publié au BOC : **{_fmt_ratio(m['per_publie_boc'])}** ({m['per_source']})",
        f"- Rendement net publié : {_fmt_pct(m['rendement_net_pct'])}",
        f"- Dernier dividende net : {_fmt_fcfa(m['dernier_dividende_net_fcfa'], ' FCFA/action')}",
        "",
        "## 2 · Liquidité — pouvez-vous sortir ?",
        "",
        f"- Séances échangées sur 20 : {_fmt_entier(m['seances_echangees_20'])}",
        f"- Valeur médiane par séance : {_fmt_fcfa(m['valeur_mediane_20_fcfa'])}",
        f"- Test de sortie : {t.get('lecture') if t.get('calculable') else t.get('raison')}",
    ]
    if t.get("calculable"):
        lignes.append(
            f"- Un ordre de {_fmt_fcfa(t['montant_ordre_fcfa'])} représente "
            f"{_fmt_pct(t['part_dune_seance_mediane_pct'])} d'une séance médiane."
        )
    lignes += [
        "",
        "## 3 · Le parcours du titre (prix seuls, pas de rendement total)",
        "",
        f"- Performance 250 séances : {_fmt_pct(m['performance_250_seances_pct'])} "
        f"({m['performance_libelle']})",
        f"- Volatilité annualisée : {_fmt_pct(m['volatilite_annualisee_pct'])}",
        f"- Pire creux sur l'archive : {_fmt_pct(m['max_drawdown_pct'])}",
        "",
        "## 4 · Ce qu'elle gagne (chiffres publiés, avec leur niveau de confiance)",
        "",
    ]
    if fiche["resultats_publies"]:
        lignes += ["| Indicateur | Valeur | Confiance | Documents |", "|---|---:|---|---:|"]
        for nom, valeurs in sorted(fiche["resultats_publies"].items()):
            lignes.append(
                f"| {nom.replace('_', ' ')} | {_fmt_fcfa(valeurs['valeur_fcfa'])} | "
                f"{valeurs['confiance']} | {valeurs['documents_confirmants']} |"
            )
    else:
        lignes.append("Aucun chiffre fondamental extrait pour cette société.")

    lignes += [
        "",
        "## 5 · Dividende",
        "",
        f"- Statut : {_fmt_entier(fiche['dividende']['statut'])}",
        f"- Exercices payés : {_fmt_entier(fiche['dividende']['exercices_payes'])} · "
        f"années consécutives : {_fmt_entier(fiche['dividende']['annees_consecutives'])}",
        f"- Coupures observées : {_fmt_entier(fiche['dividende']['coupures'])} · "
        f"hausses : {_fmt_entier(fiche['dividende']['hausses'])}",
        f"- Croissance annuelle moyenne (CAGR) : {_fmt_pct(fiche['dividende']['cagr_pct'])}",
    ]
    if fiche["dividende"]["serie"]:
        lignes += ["", "| Exercice | Dividende net (FCFA) |", "|---|---:|"]
        for exercice, montant in fiche["dividende"]["serie"]:
            lignes.append(f"| {exercice} | {_fmt_fcfa(montant, '')} |")

    lignes += ["", "## 6 · Ancre dividende — une seule ancre, donc pas de verdict", ""]
    if a.get("calculable"):
        taux = fiche["taux_actualisation"]
        lignes += [
            f"Taux requis : **{_fmt_pct(a['taux_requis_pct'])}** = taux directeur BCEAO "
            f"{_fmt_pct(taux.get('taux_directeur_pct'))} (au {taux.get('taux_directeur_date')}) "
            f"+ prime d'exigence {_fmt_entier(taux.get('prime_points')) + ' pts'}.",
            "",
            f"Croissances testées, bornées par l'historique propre de la société "
            f"({_fmt_pct(a['bornes']['croissance_planchee_pct'])} à "
            f"{_fmt_pct(a['bornes']['croissance_plafonnee_pct'])}) :",
            "",
            "| Scénario | Croissance | Valeur à taux requis | à −1 pt | à +1 pt |",
            "|---|---:|---:|---:|---:|",
        ]
        for nom in ("pessimiste", "central", "optimiste"):
            valeurs = a["valeurs_par_scenario"].get(nom) or {}
            lignes.append(
                f"| {nom} | {_fmt_pct(a['scenarios_croissance_pct'][nom])} | "
                f"{_fmt_fcfa(valeurs.get('+0_pt'))} | {_fmt_fcfa(valeurs.get('-1_pt'))} | "
                f"{_fmt_fcfa(valeurs.get('+1_pt'))} |"
            )
        if a.get("fourchette_fcfa"):
            lignes += [
                "",
                f"Fourchette indicative : **{_fmt_fcfa(a['fourchette_fcfa'][0])} → "
                f"{_fmt_fcfa(a['fourchette_fcfa'][1])}** par action.",
            ]
        if a.get("scenarios_confondus"):
            lignes += ["", f"*{a['note_scenarios']}*"]
        borne = a.get("borne_atteinte") or {}
        if any(borne.values()):
            atteintes = [nom for nom, valeur in borne.items() if valeur]
            lignes += [
                "",
                f"*Borne appliquée sur : {', '.join(atteintes)}. La croissance observée dépasse "
                "le plafond prudent retenu, elle n'est donc pas extrapolée telle quelle.*",
            ]
        position = a.get("position_du_prix") or {}
        if position:
            prix = position["prix"]
            if position["au_dessus_valeur_optimiste"]:
                lignes += [
                    "",
                    f"**Où se situe le prix.** À {_fmt_fcfa(prix)}, le cours dépasse la valeur haute "
                    "que le dividende seul peut justifier. L'écart doit donc s'expliquer par autre "
                    "chose — bénéfices réinvestis, patrimoine, croissance future — que SIGMA ne sait "
                    "pas encore vérifier pour cette société. Cela ne signifie pas que le titre est "
                    "cher : cela signifie que **cette ancre-là ne suffit pas à le dire**.",
                ]
            elif position["sous_valeur_pessimiste"]:
                lignes += [
                    "",
                    f"**Où se situe le prix.** À {_fmt_fcfa(prix)}, le cours est sous la valeur du "
                    "scénario le plus défavorable du dividende. C'est le seul cas où cette ancre "
                    "parle d'elle-même — et une seule ancre ne suffit toujours pas à un verdict.",
                ]
            else:
                lignes += [
                    "",
                    f"**Où se situe le prix.** À {_fmt_fcfa(prix)}, le cours tombe à l'intérieur de "
                    "la fourchette indicative du dividende : ni signal d'étude, ni signal de cherté.",
                ]
        lignes += [
            "",
            "> Cette fourchette ne s'appuie que sur le dividende. Elle ne tient pas compte "
            "des bénéfices non distribués, de la dette ni du patrimoine. Ce n'est pas une valeur "
            "de l'entreprise, c'est une **ancre**.",
        ]
    else:
        lignes.append(f"Non calculable : {a.get('raison')}.")

    lignes += [
        "",
        "## 7 · Verdict",
        "",
        f"**{v['libelle']}** — {v['raison']}.",
        "",
        "## 8 · Ce qui invaliderait la thèse",
        "",
    ]
    lignes += [f"- {condition}" for condition in fiche["invalidation"]]
    lignes += ["", "## 9 · Ce que SIGMA ne sait pas (et ne comble pas)", ""]
    lignes += [f"- {trou}" for trou in fiche["trous"]]
    lignes += ["", "---", "", fiche["portee"], ""]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fiche société en une page.")
    parser.add_argument("ticker")
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--quantite", type=float, default=None, help="taille d'ordre envisagée, en actions")
    parser.add_argument("--prime", type=float, default=PRIME_EXIGENCE_DEFAUT, help="prime d'exigence, en points")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="sortie JSON au lieu du markdown")
    args = parser.parse_args(argv)

    data = charger(args.data)
    fiche = construire_fiche(data, args.ticker, args.quantite, args.prime)

    if args.json:
        texte = json.dumps(fiche, ensure_ascii=False, indent=2, default=str)
        extension = "json"
    else:
        texte = rendre_markdown(fiche)
        extension = "md"

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        chemin = args.out / f"{fiche['ticker']}_fiche.{extension}"
        chemin.write_text(texte + "\n", encoding="utf-8")
        print(chemin)
    else:
        print(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())

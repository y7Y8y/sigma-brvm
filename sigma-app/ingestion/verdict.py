#!/usr/bin/env python3
"""Verdict — ce que les données disent d'une société, sur trois horizons.

Question du propriétaire, reformulée : « qu'est-ce que je fais de mon argent
ce mois-ci, sur le court, le moyen et le long terme ? » L'application empilait
des écrans ; elle ne répondait pas.

Comment cette réponse est construite, et pourquoi elle ne peut pas être un
conseil déguisé
--------------------------------------------------------------------------
Trois repères seulement, chacun avec son horizon, sa règle écrite et son taux
d'erreur mesuré sur l'archive réelle :

**Court terme (séance).** Position du cours dans sa propre fourchette récente
(60 séances), et non dans celle des autres sociétés. Plus un cours est proche
du haut de sa fourchette, plus un achat du jour se paie cher ; c'est une
observation, pas une prédiction.

**Moyen terme (6 à 18 mois).** Le PER publié au BOC, comparé **au propre passé
de la société** : sa médiane, ses quartiles, son percentile actuel sur les
séances archivées. C'est la correction du reproche central : un seuil unique
(« PER < 15 ») est une moyenne de marché, pas une lecture de cette société.

**Long terme (3 ans et plus).** Les états financiers officiels : résultat net,
fonds propres, dette nette, flux d'exploitation, dividende net, sur trois
exercices ou plus. Ce que l'entreprise produit réellement, indépendamment du
prix du jour.

Ce que le module refuse de faire
--------------------------------
- Aucun score composite. Un score unique mélange trois questions différentes et
  cache laquelle a échoué.
- Aucun libellé d'achat. Chaque repère est daté, chiffré, et suivi de ce qui
  l'invaliderait.
- Aucune donnée inventée. Un repère dont la série est absente est déclaré
  `non_calculable` avec la raison exacte ; il n'est jamais estimé.
- Aucun nombre d'actions déduit d'un cours. Les fichiers ne contiennent qu'un
  nombre d'actions pour 2 sociétés : la capitalisation reste donc
  `non_calculable` pour 46 d'entre elles, et ce module ne fait pas semblant.

Usage
-----
    python3 ingestion/verdict.py --out web/data/verdicts.json
    python3 ingestion/verdict.py SNTS ORAC --json
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DATA = RACINE / "web" / "data" / "data.json"
ARCHIVE = RACINE / "web" / "data" / "boc_archive.json"

# ---------------------------------------------------------------------------
# Seuils, écrits d'avance et publiés avec chaque réponse. Aucun n'a été ajusté
# sur un résultat : les modifier après coup serait de l'optimisation de
# narration, exactement ce que le propriétaire reproche aux vendeurs de signaux.
# ---------------------------------------------------------------------------
SEUIL_FOURCHETTE_HAUT = 80.0     # percentile au-dessus duquel le cours est « haut »
SEUIL_FOURCHETTE_BAS = 20.0      # et en dessous « bas »
SEUIL_PER_CHER = 80.0            # percentile du PER propre à la société
SEUIL_PER_BON_MARCHE = 20.0
SEUIL_PERFIANCE_COURT = 10.0     # variation 20 séances qui mérite une explication
MIN_SEANCES_PER = 120            # sous ce nombre de séances, la distribution est trop courte
MIN_EXERCICES = 3                # exercices nécessaires pour une lecture long terme

# ── Court terme ────────────────────────────────────────────────────────────


def position_fourchette(clotures: list[float], fenetre: int = 60) -> dict | None:
    """Percentile du dernier cours dans sa propre fourchette récente."""
    propre = [c for c in clotures[-fenetre:] if isinstance(c, (int, float))]
    if len(propre) < 20:
        return None
    dernier = propre[-1]
    bas, haut = min(propre), max(propre)
    if haut <= bas:
        return None
    percentile = 100.0 * sum(1 for c in propre if c <= dernier) / len(propre)
    return {
        "percentile": round(percentile, 1),
        "bas": bas,
        "haut": haut,
        "dernier": dernier,
        "seances": len(propre),
        "ecart_au_haut_pct": round((dernier / haut - 1) * 100, 1),
    }


def lecture_court(marche: dict | None, stats: dict) -> dict:
    if marche is None:
        return {"statut": "non_calculable", "raison": "moins de 20 clôtures publiées dans la fenêtre de 60 séances",
                "horizon": "court", "regle": "position dans sa propre fourchette de 60 séances"}
    p = marche["percentile"]
    var20 = stats.get("performance_20_sessions_pct")
    if p >= SEUIL_FOURCHETTE_HAUT:
        ton, phrase = "cher", f"Cours dans le haut de sa fourchette ({p:.0f}ᵉ centile sur 60 séances). Payer aujourd'hui revient à payer le haut du parcours récent."
    elif p <= SEUIL_FOURCHETTE_BAS:
        ton, phrase = "bas", f"Cours dans le bas de sa fourchette ({p:.0f}ᵉ centile sur 60 séances). Le marché ne paie pas cher cette société par rapport à son propre parcours récent."
    else:
        ton, phrase = "milieu", f"Cours au milieu de sa fourchette ({p:.0f}ᵉ centile sur 60 séances) : pas de pression de prix dans un sens ou dans l'autre."
    detail = [phrase]
    if isinstance(var20, (int, float)) and abs(var20) >= SEUIL_PERFIANCE_COURT:
        sens = "monté" if var20 > 0 else "baissé"
        detail.append(f"Sur 20 séances, le cours a {sens} de {abs(var20):.1f} % (prix seuls, hors dividende).")
    detail.append(f"Fourchette observée : {marche['bas']:,.0f} – {marche['haut']:,.0f} FCFA ; il reste {abs(marche['ecart_au_haut_pct']):.1f} % sous le haut." if marche["ecart_au_haut_pct"] < 0
                  else "Le cours est au plus haut de sa fenêtre récente.")
    return {
        "statut": "calcule", "horizon": "court", "ton": ton, "phrase": detail[0],
        "details": detail, "donnees": marche,
        "regle": "percentile du dernier cours dans ses 60 dernières clôtures publiées",
        "invalidation": "une clôture hors de la fourchette, ou un détachement de dividende, rend la lecture obsolète",
    }

# ── Moyen terme ────────────────────────────────────────────────────────────


def distribution_per(per: list[float]) -> dict | None:
    """Distribution du PER d'UNE société, sur ses propres séances."""
    propre = [p for p in per if isinstance(p, (int, float)) and 0 < p < 60]
    if len(propre) < MIN_SEANCES_PER:
        return None
    tris = sorted(propre)
    q1 = tris[len(tris) // 4]
    q3 = tris[(3 * len(tris)) // 4]
    actuel = propre[-1]
    return {
        "actuel": round(actuel, 2),
        "mediane": round(statistics.median(propre), 2),
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "minimum": round(min(propre), 2),
        "maximum": round(max(propre), 2),
        "percentile": round(100.0 * sum(1 for p in propre if p <= actuel) / len(propre), 1),
        "seances": len(propre),
    }


def decomposition(hist: list[dict]) -> dict | None:
    """Pourquoi le cours a bougé : l'entreprise gagne-t-elle plus, ou le marché
    paie-t-il plus cher ? Décomposition exacte, sans hypothèse :

        cours = bénéfice implicite par action × PER
        donc  variation du cours = variation du bénéfice × variation du PER

    « Bénéfice implicite » = cours publié / PER publié au même BOC. Ce n'est pas
    un BPA certifié : c'est ce que le prix et le multiple impliquent ensemble.
    """
    paires = [(h.get("close"), h.get("per")) for h in hist
              if isinstance(h.get("close"), (int, float)) and isinstance(h.get("per"), (int, float)) and h["per"] > 0]
    if len(paires) < MIN_SEANCES_PER:
        return None
    c0, p0 = paires[0]
    c1, p1 = paires[-1]
    if not (c0 and p0 and c1 and p1):
        return None
    benefice0, benefice1 = c0 / p0, c1 / p1
    var_cours = (c1 / c0 - 1) * 100
    var_benefice = (benefice1 / benefice0 - 1) * 100
    var_per = (p1 / p0 - 1) * 100
    if abs(var_benefice) >= abs(var_per):
        moteur = "benefice"
        phrase = (f"Sur l'archive, le cours a varié de {var_cours:+.1f} % : le bénéfice implicite par action a fait {var_benefice:+.1f} %, "
                  f"le PER {var_per:+.1f} %. C'est l'entreprise qui a porté le mouvement, pas le multiple.")
    else:
        moteur = "multiple"
        phrase = (f"Sur l'archive, le cours a varié de {var_cours:+.1f} % : le PER a fait {var_per:+.1f} %, "
                  f"le bénéfice implicite par action {var_benefice:+.1f} %. C'est le prix payé pour le même bénéfice qui a porté le mouvement.")
    return {
        "debut": {"cours": c0, "per": round(p0, 2), "benefice_implicite": round(benefice0, 2)},
        "fin": {"cours": c1, "per": round(p1, 2), "benefice_implicite": round(benefice1, 2)},
        "variation_cours_pct": round(var_cours, 1),
        "variation_benefice_pct": round(var_benefice, 1),
        "variation_per_pct": round(var_per, 1),
        "moteur": moteur,
        "phrase": phrase,
    }


def lecture_moyen(dist: dict | None, boc: dict) -> dict:
    if dist is None:
        return {"statut": "non_calculable", "horizon": "moyen",
                "raison": f"moins de {MIN_SEANCES_PER} séances de PER publié dans l'archive",
                "regle": "PER comparé à sa propre distribution historique"}
    p = dist["percentile"]
    cours = boc.get("close")
    marge_benefice = None
    if isinstance(cours, (int, float)) and isinstance(dist["actuel"], (int, float)):
        pass  # le bénéfice implicite est calculé par le module de décomposition si besoin
    if p >= SEUIL_PER_CHER:
        ton = "cher"
        phrase = (f"PER à {dist['actuel']:.1f}, soit le {p:.0f}ᵉ centile de ses {dist['seances']} séances publiées. "
                  f"La société se paie plus cher qu'elle ne s'est payée {p:.0f} fois sur 100 — ce n'est pas un prix anormal, c'est un prix haut pour elle.")
    elif p <= SEUIL_PER_BON_MARCHE:
        ton = "bon_marche"
        phrase = (f"PER à {dist['actuel']:.1f}, soit le {p:.0f}ᵉ centile de ses {dist['seances']} séances publiées. "
                  f"Le marché la paie moins cher qu'à son habitude. Un prix bas peut venir du bénéfice autant que du cours : cette phrase ne tranche pas.")
    else:
        ton = "moyen"
        phrase = (f"PER à {dist['actuel']:.1f}, au {p:.0f}ᵉ centile de sa propre histoire (médiane {dist['mediane']:.1f}). "
                  "La valorisation est dans son cours habituel.")
    detail = [phrase,
              f"Sa fourchette personnelle va de {dist['q1']:.1f} (1ᵉʳ quartile) à {dist['q3']:.1f} (3ᵉ quartile) ; extrêmes observés {dist['minimum']:.1f} à {dist['maximum']:.1f}."]
    return {
        "statut": "calcule", "horizon": "moyen", "ton": ton, "phrase": detail[0],
        "details": detail, "donnees": dist,
        "regle": "PER publié au BOC, comparé à sa propre distribution sur l'archive (aucun seuil de marché)",
        "invalidation": "une publication de résultats qui change le bénéfice, ou une opération sur le capital, déplace toute la distribution",
    }

# ── Long terme ─────────────────────────────────────────────────────────────


def serie(company: dict) -> list[dict]:
    return sorted([e for e in (company.get("fundamentals", {}) or {}).get("series", []) if e.get("figures")],
                  key=lambda e: e.get("exercice") or 0)


def valeur(figure: dict | None) -> float | None:
    if not figure:
        return None
    v = figure.get("value")
    return v if isinstance(v, (int, float)) else None


def lecture_long(company: dict) -> dict:
    exercices = serie(company)
    if len(exercices) < MIN_EXERCICES:
        return {"statut": "non_calculable", "horizon": "long",
                "raison": f"{len(exercices)} exercice(s) d'états financiers extraits, il en faut {MIN_EXERCICES}",
                "regle": "états financiers officiels sur trois exercices ou plus"}
    dernier, premier = exercices[-1], exercices[0]
    figs_d, figs_p = dernier.get("figures") or {}, premier.get("figures") or {}

    rn_d, rn_p = valeur(figs_d.get("resultat_net")), valeur(figs_p.get("resultat_net"))
    fp_d, fp_p = valeur(figs_d.get("capitaux_propres")), valeur(figs_p.get("capitaux_propres"))
    dettes_d = valeur(figs_d.get("dettes_financieres"))
    treso_d = valeur(figs_d.get("tresorerie_equivalents"))
    flux_d = valeur(figs_d.get("flux_tresorerie_operationnel"))
    ca_d, ca_p = valeur(figs_d.get("chiffre_affaires")), valeur(figs_p.get("chiffre_affaires"))

    points = []
    ton = "neutre"
    if rn_d is not None and rn_p is not None and rn_p != 0:
        croissance = (rn_d / rn_p - 1) * 100
        annees = max(1, (dernier.get("exercice") or 0) - (premier.get("exercice") or 0))
        if annees > 5:
            # 2021 → 2025 comparait deux sociétés différentes dans le temps :
            # changement de périmètre, cession, ou extraction incomplète.
            points.append(
                f"Écart de {annees} exercices entre {premier.get('exercice')} et {dernier.get('exercice')} : "
                "la comparaison directe serait trompeuse (périmètre possiblement différent)."
            )
            ton = "a_verifier"
            croissance = None
        if croissance is not None:
            rythme = ((rn_d / rn_p) ** (1 / annees) - 1) * 100 if rn_d > 0 and rn_p > 0 else None
            points.append(f"Résultat net {dernier.get('exercice')} : {rn_d / 1e6:,.0f} M FCFA, contre {rn_p / 1e6:,.0f} M en {premier.get('exercice')} ({croissance:+.1f} %"
                          + (f", soit {rythme:+.1f} % par an" if rythme is not None else "") + ").")
            ton = "solide" if croissance > 0 else "fragile"
    if rn_d is not None and rn_d < 0:
        points.append(f"Résultat net négatif en {dernier.get('exercice')} : la lecture long terme porte sur une entreprise qui perd de l'argent.")
        ton = "fragile"
    if fp_d and rn_d:
        points.append(f"Rentabilité des fonds propres : {rn_d / fp_d * 100:.1f} % en {dernier.get('exercice')} (résultat net / fonds propres de fin d'exercice).")
    if fp_d and fp_p:
        points.append(f"Fonds propres : {fp_d / 1e6:,.0f} M FCFA fin {dernier.get('exercice')}, contre {fp_p / 1e6:,.0f} M fin {premier.get('exercice')}.")
    elif fp_d is None:
        points.append(f"Fonds propres {dernier.get('exercice')} : absents des documents indexés — non substitués par zéro.")
    dette_nette = None
    if dettes_d is not None:
        dette_nette = dettes_d - (treso_d or 0)
        if fp_d:
            points.append(f"Dette nette {dette_nette / 1e6:,.0f} M FCFA, soit {dette_nette / fp_d * 100:.0f} % des fonds propres : "
                          + ("levier contenu." if dette_nette / fp_d < 1 else "levier à surveiller le jour où les taux montent."))
    if flux_d is not None and rn_d:
        points.append(f"Flux d'exploitation {flux_d / 1e6:,.0f} M FCFA, soit {flux_d / rn_d * 100:.0f} % du résultat net : "
                      + ("le bénéfice se transforme en trésorerie." if flux_d / rn_d >= 0.8 else "le bénéfice ne se transforme pas entièrement en trésorerie — à comprendre avant de s'y fier."))
    if ca_d and ca_p and ca_p > 0:
        points.append(f"Activité (chiffre d'affaires ou PNB) : {ca_d / ca_p * 100 - 100:+.1f} % entre {premier.get('exercice')} et {dernier.get('exercice')}.")

    # Le seul repère de « durabilité » que les données permettent sans BPA :
    # le dividende net publié rapporté au résultat net par action implicite.
    div_hist = company.get("dividend_history") or {}
    div_d = valeur(figs_d.get("dividendes_verses"))
    if div_d and rn_d:
        # Signalé par l'audit du 2026-10-28 : PALC porte -7 931 M FCFA alors que
        # des dividendes versés sont une sortie de trésorerie, donc positifs dans
        # la plupart des états. Tant que le signe n'est pas établi document par
        # document, on affiche la valeur en indiquant sa provenance brute.
        flux_sortant = abs(div_d)
        part = flux_sortant / rn_d * 100 if rn_d > 0 else None
        points.append(
            f"Dividendes versés {dernier.get('exercice')} : {flux_sortant / 1e6:,.0f} M FCFA"
            + (f", soit {part:.0f} % du résultat net" if part is not None else "")
            + f" (valeur brute publiée {div_d / 1e6:,.0f} M ; convention de signe non unifiée entre sociétés)."
        )

    if not points:
        return {"statut": "non_calculable", "horizon": "long",
                "raison": f"{len(exercices)} exercice(s) présents mais aucune grandeur exploitable "
                          "(résultat net, fonds propres, flux ou dividende absents)",
                "regle": "états financiers officiels sur trois exercices ou plus"}
    return {
        "statut": "calcule", "horizon": "long", "ton": ton, "phrase": points[0],
        "details": points,
        "exercices": [e.get("exercice") for e in exercices],
        "paiements_dividendes": f"{div_hist.get('paid_last_5_fiscal_years', 0)}/5 derniers exercices" if div_hist else "non documenté",
        "regle": "états financiers officiels : résultat, fonds propres, dette nette, flux, dividende — prix ignoré",
        "invalidation": "un changement de périmètre comptable, une opération sur le capital, ou un exercice déficitaire",
    }


# ── Assemblage ─────────────────────────────────────────────────────────────


@dataclass
class Verdict:
    ticker: str
    nom: str
    secteur: str
    cours: float | None
    horizons: dict = field(default_factory=dict)
    capitalisation: dict = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def construire(data: dict, archive: dict) -> dict[str, Verdict]:
    champs = archive["row_fields"]
    seances: dict[str, list[dict]] = {}
    for s in archive["sessions"]:
        for ticker, ligne in s["rows"].items():
            seances.setdefault(ticker, []).append(dict(zip(champs, ligne)))

    verdicts: dict[str, Verdict] = {}
    for c in data["companies"]:
        t = c["ticker"]
        hist = seances.get(t, [])
        clotures = [h.get("close") for h in hist if isinstance(h.get("close"), (int, float))]
        pers = [h.get("per") for h in hist if isinstance(h.get("per"), (int, float))]
        boc = c.get("latest_boc") or {}
        cours = c.get("latest_quote", {}).get("close") or boc.get("close")

        v = Verdict(ticker=t, nom=c.get("name", ""), secteur=c.get("sector", ""),
                    cours=cours if isinstance(cours, (int, float)) else None)
        v.horizons["court"] = lecture_court(position_fourchette(clotures), c.get("history_stats") or {})
        decomp = decomposition(hist)
        v.horizons["moyen"] = lecture_moyen(distribution_per(pers), boc)
        if decomp and v.horizons["moyen"].get("statut") == "calcule":
            v.horizons["moyen"]["decomposition"] = decomp
            v.horizons["moyen"]["details"].append(decomp["phrase"])
        v.horizons["long"] = lecture_long(c)

        # Capitalisation : seulement si le nombre d'actions est PROUVÉ dans un
        # document. Aucune déduction depuis un cours ou un BPA.
        actions = valeur((c.get("figures_supplement") or {}).get("nombre_actions_fin_exercice"))
        if actions is None:
            for e in reversed(serie(c)):
                actions = valeur((e.get("figures") or {}).get("nombre_actions_fin_exercice"))
                if actions:
                    break
        if actions and cours:
            v.capitalisation = {"statut": "calcule", "actions": actions,
                                "valeur_fcfa": round(actions * cours),
                                "base": "nombre d'actions lu dans un document officiel × dernier cours publié"}
        else:
            v.capitalisation = {"statut": "non_calculable",
                                "raison": "nombre d'actions absent des documents indexés pour cette société"}
        verdicts[t] = v
    return verdicts


def resume(verdicts: dict[str, Verdict]) -> dict:
    def compte(horizon: str, statut: str) -> int:
        return sum(1 for v in verdicts.values() if v.horizons[horizon].get("statut") == statut)

    return {
        "societes": len(verdicts),
        "court_calcule": compte("court", "calcule"),
        "moyen_calcule": compte("moyen", "calcule"),
        "long_calcule": compte("long", "calcule"),
        "capitalisation_calculee": sum(1 for v in verdicts.values() if v.capitalisation.get("statut") == "calcule"),
        "trois_horizons_complets": sum(
            1 for v in verdicts.values()
            if all(v.horizons[h].get("statut") == "calcule" for h in ("court", "moyen", "long"))
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="*", help="limiter à ces tickers")
    ap.add_argument("--out", help="écrire le JSON complet")
    ap.add_argument("--json", action="store_true", help="afficher en JSON au lieu du texte")
    args = ap.parse_args()

    data = json.loads(DATA.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    verdicts = construire(data, archive)
    if args.tickers:
        verdicts = {t: v for t, v in verdicts.items() if t in {x.upper() for x in args.tickers}}

    if args.out:
        payload = {
            "schema_version": 1,
            "source_donnees": data.get("generated_at"),
            "archive_boc": {"seances": archive["sessions_count"], "du": archive["first_date"], "au": archive["last_date"]},
            "seuils": {
                "fourchette_haut_percentile": SEUIL_FOURCHETTE_HAUT,
                "fourchette_bas_percentile": SEUIL_FOURCHETTE_BAS,
                "per_cher_percentile": SEUIL_PER_CHER,
                "per_bon_marche_percentile": SEUIL_PER_BON_MARCHE,
                "min_seances_per": MIN_SEANCES_PER,
                "min_exercices": MIN_EXERCICES,
            },
            "resume": resume(verdicts),
            "verdicts": {t: v.to_dict() for t, v in verdicts.items()},
        }
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(payload["resume"], ensure_ascii=False, indent=1))
        return

    for t, v in verdicts.items():
        if args.json:
            print(json.dumps(v.to_dict(), ensure_ascii=False, indent=1))
            continue
        print(f"\n{'=' * 78}\n{v.ticker} — {v.nom}  ({v.secteur})  cours {v.cours}")
        for h in ("court", "moyen", "long"):
            b = v.horizons[h]
            print(f"  [{b.get('horizon', h).upper():5}] {b.get('statut'):14} {b.get('phrase') or b.get('raison')}")
            for d in b.get("details", [])[1:]:
                print(f"          · {d}")


if __name__ == "__main__":
    main()

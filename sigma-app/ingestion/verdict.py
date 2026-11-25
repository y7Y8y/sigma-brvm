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
# Deux niveaux, jamais confondus à l'écran :
#   PLEIN     — la série est assez longue pour une distribution complète ;
#   LIMITE    — la série existe mais est courte : on répond, en le disant.
# Un refus silencieux serait aussi trompeur qu'une affirmation sans base.
# Un saut de cours n'est retenu comme événement que s'il a été payé : en dessous
# de 5 M FCFA échangés, la variation d'une séance décrit un prix de passage.
SEUIL_SAUT_VALEUR = 5_000_000

# Au-delà de cinq exercices d'écart, comparer deux exercices revient souvent à
# comparer deux périmètres comptables : la comparaison est refusée, pas nuancée.
MAX_ECART_EXERCICES = 5

PER_SEANCES_PLEIN = 120
PER_SEANCES_LIMITE = 30          # en dessous, aucune lecture sérieuse n'est possible
MIN_EXERCICES = 3                # exercices nécessaires pour une lecture long terme pleine
MIN_EXERCICES_LIMITE = 2         # deux exercices complets : lecture possible, dite « limitée »

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


def position_longue(clotures: list[float], fenetre: int = 120) -> dict | None:
    """Où en est le cours par rapport à son propre cycle, pas par rapport à la séance.

    Le court terme répond « payer cher aujourd'hui ? ». Cette lecture répond à
    la question du long terme côté prix : le titre est-il au-dessus ou en
    dessous de sa moyenne de 120 séances, et à quelle distance de son plus haut
    sur un an. Deux repères, aucune prédiction.
    """
    propre = [c for c in clotures if isinstance(c, (int, float))]
    if len(propre) < fenetre:
        return None
    moyenne = sum(propre[-fenetre:]) / fenetre
    dernier = propre[-1]
    plus_haut = max(propre[-250:] if len(propre) >= 250 else propre)
    plus_bas = min(propre[-250:] if len(propre) >= 250 else propre)
    return {
        "moyenne_120": round(moyenne, 2),
        "ecart_moyenne_pct": round((dernier / moyenne - 1) * 100, 1),
        "plus_haut": round(plus_haut, 2),
        "ecart_plus_haut_pct": round((dernier / plus_haut - 1) * 100, 1),
        "plus_bas": round(plus_bas, 2),
        "ecart_plus_bas_pct": round((dernier / plus_bas - 1) * 100, 1),
        "seances": len(propre),
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
    if len(propre) < PER_SEANCES_LIMITE:
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
        "profondeur": "pleine" if len(propre) >= PER_SEANCES_PLEIN else "limitee",
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
    if len(paires) < PER_SEANCES_LIMITE:
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
                "raison": f"moins de {PER_SEANCES_LIMITE} séances de PER publié dans l'archive",
                "regle": "PER comparé à sa propre distribution historique"}
    p = dist["percentile"]
    profondeur = dist.get("profondeur", "pleine")
    mention = "" if profondeur == "pleine" else (
        f" Distribution courte ({dist['seances']} séances publiées sur {PER_SEANCES_PLEIN} attendues) : "
        "le rang est indicatif, pas un centile établi."
    )
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
    if profondeur != "pleine":
        detail.append(mention.strip())
    return {
        "statut": "calcule", "horizon": "moyen", "ton": ton, "phrase": detail[0],
        "profondeur": profondeur,
        "details": detail, "donnees": dist,
        "regle": "PER publié au BOC, comparé à sa propre distribution sur l'archive (aucun seuil de marché)",
        "invalidation": "une publication de résultats qui change le bénéfice, ou une opération sur le capital, déplace toute la distribution",
    }

# ── Long terme ─────────────────────────────────────────────────────────────


def normalize_texte(texte: str) -> str:
    """Minuscules sans accents — même normalisation que le collecteur."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower())
                   if unicodedata.category(c) != "Mn")


def serie(company: dict) -> list[dict]:
    return sorted([e for e in (company.get("fundamentals", {}) or {}).get("series", []) if e.get("figures")],
                  key=lambda e: e.get("exercice") or 0)


def valeur(figure: dict | None) -> float | None:
    if not figure:
        return None
    v = figure.get("value")
    return v if isinstance(v, (int, float)) else None


def unite_fcfa(figure: dict | None) -> str | None:
    """L'unité réellement utilisée par le document pour ce chiffre.

    Piste de l'audit du 28/10 sur les « sauts » de série : 24 changements
    d'unité entre deux exercices consécutifs dans la collecte. Ils ne sont pas
    une erreur de conversion (les valeurs sont bien multipliées par 1 000 ou
    1 000 000), mais ils changent la lecture : deux chiffres de la même série
    n'ont pas été lus dans la même échelle, et une rupture peut venir de là.
    """
    if not figure:
        return None
    return figure.get("unit_label")


def ruptures(exercices: list[dict]) -> list[dict]:
    """Sauts invraisemblables d'un exercice au suivant.

    Un résultat net qui est multiplié par dix en un an n'est presque jamais une
    performance : c'est un changement de périmètre comptable ou une extraction
    qui a pris la mauvaise ligne. Constaté sur cette collecte : SGBC 2021
    (10 116 M) → 2022 (97 230 M), soit ×9,6 ; FTSC 2024 (18 595 M) → 2025
    (466 M), soit ÷40. Comparer le dernier exercice à celui d'avant le saut
    produirait « +900 % par an » ou « +204 % » : deux affirmations fausses
    tirées de chiffres vrais.
    """
    sorties = []
    for a, b in zip(exercices, exercices[1:]):
        ra, rb = valeur((a.get("figures") or {}).get("resultat_net")), valeur((b.get("figures") or {}).get("resultat_net"))
        if not ra or not rb or ra <= 0 or rb <= 0:
            continue
        if b.get("exercice", 0) - a.get("exercice", 0) > MAX_ECART_EXERCICES:
            continue
        ratio = rb / ra
        if ratio > 3 or ratio < 1 / 3:
            fa = (a.get("figures") or {}).get("resultat_net") or {}
            fb = (b.get("figures") or {}).get("resultat_net") or {}
            ua, ub = unite_fcfa(fa), unite_fcfa(fb)
            # Ce qui explique une rupture, par ordre de probabilité observée :
            # 1. l'unité change (24 cas mesurés : milliers ↔ millions ↔ FCFA) ;
            # 2. le chiffre n'est pas recoupé dans son document ;
            # 3. c'est un vrai changement de périmètre.
            causes = []
            if ua and ub and ua != ub:
                causes.append(f"unité différente ({ua} → {ub})")
            faibles = [f"exercice {e.get('exercice')} ({f.get('confidence')})"
                       for e, f in ((a, fa), (b, fb))
                       if f.get("confidence") in (None, "extraction_unique", "extraction_automatique_a_confirmer")]
            if faibles:
                causes.append("chiffre non recoupé : " + ", ".join(faibles))
            if not causes:
                causes.append("périmètre comptable probablement différent")
            sorties.append({"de": a.get("exercice"), "a": b.get("exercice"),
                            "ratio": round(ratio, 1) if ratio >= 1 else round(1 / ratio, 1),
                            "sens": "hausse" if ratio >= 1 else "baisse",
                            "unites": [ua, ub], "causes": causes,
                            "raison": "saut invraisemblable d'un exercice au suivant : " + " ; ".join(causes)})
    return sorties


def roe_serie(company: dict) -> dict:
    """Rentabilité des fonds propres, exercice par exercice — la mesure la plus
    demandée par les praticiens (Fisher, Buffett, Dorsey) et la plus absente
    d'un écran boursier ordinaire.

    Une seule règle : le résultat net et les fonds propres doivent venir du
    **même exercice**. Aucune moyenne, aucune reconstitution.
    """
    lignes, manquants = [], []
    for e in serie(company):
        rn, fp = _fig(e, "resultat_net"), _fig(e, "capitaux_propres")
        if rn is None or not fp or fp <= 0:
            if rn is not None:
                manquants.append(e.get("exercice"))
            continue
        lignes.append({"exercice": e.get("exercice"), "resultat_net": rn,
                       "fonds_propres": fp, "roe_pct": round(rn / fp * 100, 1)})
    if not lignes:
        return {"statut": "non_calculable",
                "raison": ("fonds propres absents des états extraits pour tous les exercices"
                           if manquants else "aucun exercice avec résultat et fonds propres ensemble")}
    valeurs = [x["roe_pct"] for x in lignes]
    sous_zero = sum(1 for v in valeurs if v < 0)
    return {
        "statut": "calcule",
        "profondeur": "pleine" if len(lignes) >= MIN_EXERCICES else "limitee",
        "exercices": lignes,
        "dernier": lignes[-1],
        "moyenne_pct": round(sum(valeurs) / len(valeurs), 1),
        "minimum_pct": min(valeurs), "maximum_pct": max(valeurs),
        "exercices_negatifs": sous_zero,
        "exercices_sans_fonds_propres": manquants,
        "regle": ("résultat net ÷ fonds propres de fin du même exercice. Au-dessus de 15 % sur trois exercices, "
                  "l'entreprise crée de la valeur pour ses actionnaires ; sous 5 %, elle en détruit après inflation. "
                  "Ce n'est ni une note de qualité ni une prévision."),
    }


def lecture_long(company: dict) -> dict:
    exercices = serie(company)
    if len(exercices) < MIN_EXERCICES_LIMITE:
        # Une seule année ne permet aucune comparaison : on refuse au lieu de
        # décrire un instant et de l'appeler une trajectoire.
        return {"statut": "non_calculable", "horizon": "long",
                "raison": (f"{len(exercices)} exercice(s) d'états financiers extraits des documents indexés ; "
                           f"deux exercices au minimum sont nécessaires pour comparer, trois pour une lecture pleine"),
                "regle": "états financiers officiels, deux exercices minimum"}
    profondeur = "pleine" if len(exercices) >= MIN_EXERCICES else "limitee"
    # Le premier exercice de la série est souvent une ruine d'extraction
    # (2021 : résultat net seul, ou périmètre d'avant cession). Comparer le
    # dernier au plus ancien produisait « SGBC +900,7 % par an » et
    # « ONTBF −50,9 % » sur deux sociétés différentes dans le temps.
    # On prend donc le plus ancien exercice **comparable** : au plus cinq
    # exercices d'écart, et doté du même indicateur que le dernier.
    dernier = exercices[-1]
    annee_d = dernier.get("exercice") or 0
    sauts = ruptures(exercices)
    # La fenêtre de comparaison commence après la dernière rupture : comparer
    # au-delà reviendrait à décrire deux sociétés différentes.
    annee_plancher = max([x["a"] for x in sauts], default=0)
    comparables = [e for e in exercices[:-1]
                   if (e.get("figures") or {}).get("resultat_net")
                   and (e.get("exercice") or 0) >= annee_plancher
                   and annee_d - (e.get("exercice") or 0) <= MAX_ECART_EXERCICES]
    # Un exercice comparable doit aussi partager une grandeur avec le dernier :
    # une ligne de résultat net seule, sans activité ni bilan, est une lecture
    # d'un chiffre isolé, pas d'une trajectoire.
    riches = [e for e in comparables if len(e.get("figures") or {}) > 1]
    premier = (riches or comparables or [None])[0]
    figs_d = dernier.get("figures") or {}
    figs_p = (premier or {}).get("figures") or {}

    rn_d, rn_p = valeur(figs_d.get("resultat_net")), valeur(figs_p.get("resultat_net"))
    annee_p = (premier or {}).get("exercice")
    fp_d, fp_p = valeur(figs_d.get("capitaux_propres")), valeur(figs_p.get("capitaux_propres"))
    # Une donnée absente n'est pas toujours irrécupérable : un total peut être
    # reconstruit depuis ses composantes publiées. La règle est stricte —
    # uniquement une somme additive exacte, jamais une estimation, et le fait
    # que ce soit une somme est écrit à côté du chiffre.
    dettes_d = valeur(figs_d.get("dettes_financieres"))
    dette_recomposee = False
    if dettes_d is None:
        haut = valeur(figs_d.get("dettes_financieres_non_courantes"))
        courant = valeur(figs_d.get("dettes_financieres_courantes"))
        if haut is not None and courant is not None:
            dettes_d, dette_recomposee = haut + courant, True
    treso_d = valeur(figs_d.get("tresorerie_equivalents"))
    flux_d = valeur(figs_d.get("flux_tresorerie_operationnel"))
    ca_d, ca_p = valeur(figs_d.get("chiffre_affaires")), valeur(figs_p.get("chiffre_affaires"))

    points = []
    ton = "neutre"
    refus = [f"Comparaison refusée de part et d'autre de {saut['de']}→{saut['a']} : résultat net "
             f"multiplié par {saut['ratio']} en un an ({saut['sens']}) — {saut['raison']}." for saut in sauts]
    if premier is None:
        points.append("Aucun exercice antérieur comparable dans la fenêtre : la trajectoire n'est pas établie.")
    if rn_d is not None and rn_p not in (None, 0) and annee_p is not None:
        croissance = (rn_d / rn_p - 1) * 100
        annees = max(1, (dernier.get("exercice") or 0) - (annee_p or 0))
        if annees > MAX_ECART_EXERCICES:
            # 2021 → 2025 comparait deux sociétés différentes dans le temps :
            # changement de périmètre, cession, ou extraction incomplète.
            points.append(
                f"Écart de {annees} exercices entre {annee_p} et {dernier.get('exercice')} : "
                "la comparaison directe serait trompeuse (périmètre possiblement différent)."
            )
            ton = "a_verifier"
            croissance = None
        if croissance is not None:
            rythme = ((rn_d / rn_p) ** (1 / annees) - 1) * 100 if rn_d > 0 and rn_p > 0 else None
            points.append(f"Résultat net {dernier.get('exercice')} : {rn_d / 1e6:,.0f} M FCFA, contre {rn_p / 1e6:,.0f} M en {annee_p} ({croissance:+.1f} %"
                          + (f", soit {rythme:+.1f} % par an" if rythme is not None else "") + ").")
            # Une hausse de résultat ne suffit pas à dire « solide » : il faut
            # aussi que l'exploitation transforme ce résultat en trésorerie.
            # Une baisse ne suffit pas à dire « fragile » si le flux tient.
            flux_p = valeur(figs_p.get("flux_tresorerie_operationnel"))
            qualite = (flux_d / rn_d) if (flux_d is not None and rn_d) else None
            if croissance > 0 and (qualite is None or qualite >= 0.8):
                ton = "solide"
            elif croissance > 0 and qualite is not None:
                ton = "a_verifier"   # résultat en hausse, trésorerie en retrait
            elif croissance <= 0 and rn_d < 0:
                ton = "fragile"
            elif croissance <= -15 and (qualite is None or qualite < 1.2):
                ton = "fragile"
            else:
                ton = "a_verifier"
            del flux_p
    if rn_d is not None and rn_d < 0:
        points.append(f"Résultat net négatif en {dernier.get('exercice')} : la lecture long terme porte sur une entreprise qui perd de l'argent.")
        ton = "fragile"
    if fp_d and rn_d:
        points.append(f"Rentabilité des fonds propres : {rn_d / fp_d * 100:.1f} % en {dernier.get('exercice')} (résultat net / fonds propres de fin d'exercice).")
    if fp_d and fp_p:
        points.append(f"Fonds propres : {fp_d / 1e6:,.0f} M FCFA fin {dernier.get('exercice')}, contre {fp_p / 1e6:,.0f} M fin {annee_p}.")
    elif fp_d is None:
        points.append(f"Fonds propres {dernier.get('exercice')} : absents des documents indexés — non substitués par zéro.")
    dette_nette = None
    if dettes_d is not None:
        dette_nette = dettes_d - (treso_d or 0)
        if fp_d:
            points.append(f"Dette nette {dette_nette / 1e6:,.0f} M FCFA"
                          + (" (dont le total des dettes financières est la somme publiée des parts courante et non courante)"
                             if dette_recomposee else "")
                          + f", soit {dette_nette / fp_d * 100:.0f} % des fonds propres : "
                          + ("levier contenu." if dette_nette / fp_d < 1 else "levier à surveiller le jour où les taux montent."))
    if flux_d is not None and rn_d:
        points.append(f"Flux d'exploitation {flux_d / 1e6:,.0f} M FCFA, soit {flux_d / rn_d * 100:.0f} % du résultat net : "
                      + ("le bénéfice se transforme en trésorerie." if flux_d / rn_d >= 0.8 else "le bénéfice ne se transforme pas entièrement en trésorerie — à comprendre avant de s'y fier."))
    if ca_d and ca_p and ca_p > 0:
        points.append(f"Activité (chiffre d'affaires ou PNB) : {ca_d / ca_p * 100 - 100:+.1f} % entre {annee_p} et {dernier.get('exercice')}.")

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

    points.extend(refus)
    if premier is None or (annee_p is not None and annee_d - annee_p < 1):
        # Aucun exercice comparable : on ne peut ni confirmer ni infirmer une
        # trajectoire. Le ton doit le dire, sinon « neutre » se lit comme un
        # feu vert.
        ton = "a_verifier" if points else ton
    if not points:
        return {"statut": "non_calculable", "horizon": "long",
                "raison": f"{len(exercices)} exercice(s) présents mais aucune grandeur exploitable "
                          "(résultat net, fonds propres, flux ou dividende absents)",
                "regle": "états financiers officiels sur trois exercices ou plus"}
    if profondeur != "pleine":
        points.append(f"Lecture courte : {len(exercices)} exercices seulement ({' et '.join(str(e.get('exercice')) for e in exercices)}). "
                      "Une trajectoire sur deux points est un début, pas une tendance.")
    return {
        "statut": "calcule", "horizon": "long", "ton": ton, "profondeur": profondeur, "phrase": points[0],
        "details": points,
        "exercices": [e.get("exercice") for e in exercices],
        "paiements_dividendes": f"{div_hist.get('paid_last_5_fiscal_years', 0)}/5 derniers exercices" if div_hist else "non documenté",
        "regle": "états financiers officiels : résultat, fonds propres, dette nette, flux, dividende — prix ignoré",
        "invalidation": "un changement de périmètre comptable, une opération sur le capital, ou un exercice déficitaire",
    }


# ── Assemblage ─────────────────────────────────────────────────────────────


# ── Ce qui fait bouger un cours, et ce qu'on peut en anticiper ────────────

def limites_variation(archive: dict) -> dict:
    """Le plafond et le plancher de la BRVM, mesurés sur l'archive.

    Sur 12 332 variations de séance, **aucune** ne dépasse 7,5 % : 67 tombent
    exactement sur la borne. C'est une contrainte de cotation, pas une
    convention de lecture, et elle change la nature du risque : sur une séance,
    le pire perte possible est bornée.
    """
    champs = archive["row_fields"]
    i = champs.index("variation_pct")
    vals = [ligne[i] for s in archive["sessions"] for ligne in s["rows"].values()
            if isinstance(ligne[i], (int, float))]
    if not vals:
        return {"statut": "non_calculable"}
    extr = max(abs(v) for v in vals)
    au_plafond = sum(1 for v in vals if abs(abs(v) - extr) < 0.001)
    return {"statut": "calcule", "amplitude_max_pct": extr, "observations": len(vals),
            "seances_au_plafond": au_plafond,
            "note": ("amplitude maximale observée sur l'archive ; au-delà de la borne, la séance est close "
                     "sur plafond ou plancher et le titre ne s'échange plus à ce prix")}


def sauts(archive: dict, seuil: float = 5.0) -> dict:
    """Combien de fois un cours a sauté de plus de 5 % en une séance, et pourquoi.

    Ce n'est pas de la prévision : c'est le comptage de ce qui est déjà arrivé,
    avec la valeur échangée au moment du saut. Un saut sur un titre qui échange
    9 M FCFA n'est pas le même événement qu'un saut sur un titre qui échange
    900 M : le premier se rejoue, le second est une information.
    """
    champs = archive["row_fields"]
    iv, iq, ivol = champs.index("variation_pct"), champs.index("traded_value_fcfa"), champs.index("volume")
    par_titre: dict[str, list] = {}
    valeurs = []
    for s in archive["sessions"]:
        for t, ligne in s["rows"].items():
            v = ligne[iv]
            if isinstance(v, (int, float)) and abs(v) >= seuil:
                valeurs.append(ligne[iq] or 0)
                par_titre.setdefault(t, []).append({"date": s["date"], "variation_pct": v,
                                                    "valeur_echangee": ligne[iq],
                                                    "volume": ligne[ivol]})
    if not valeurs:
        return {"statut": "aucun_saut"}
    valeurs.sort()
    mediane = valeurs[len(valeurs) // 2]
    return {"statut": "calcule", "seuil_pct": seuil, "nombre": sum(len(v) for v in par_titre.values()),
            "titres": len(par_titre), "valeur_mediane_fcfa": mediane,
            "part_sous_10m_pct": round(100 * sum(1 for v in valeurs if v < 10_000_000) / len(valeurs), 1),
            "detail": {t: sorted(v, key=lambda x: x["date"], reverse=True)[:5] for t, v in par_titre.items()}}


def reactions(company: dict, archive: dict) -> dict:
    """Un saut de cours est-il suivi d'un retour, ou d'une continuation ?

    Mesuré sur cette société, dans cette archive. Répond à la question réelle :
    « après une chute, est-ce que ça remonte ? » — par un taux de retour observé,
    jamais par une promesse. Deux séances de recul seulement : c'est une
    description de ce qui s'est passé, pas un modèle.
    """
    champs = archive["row_fields"]
    iv = champs.index("variation_pct")
    seances = archive["sessions"]
    historie = [(s["date"], s["rows"].get(company["ticker"])) for s in seances]
    historie = [(d, r) for d, r in historie if r]
    sorties = []
    iq = champs.index("traded_value_fcfa")
    for i, (date, ligne) in enumerate(historie[:-2]):
        v = ligne[iv]
        if not isinstance(v, (int, float)) or abs(v) < 5:
            continue
        # Un saut sur une séance à 200 000 FCFA échangés n'est pas un événement
        # de marché : c'est un prix de passage. On ne compte que les sauts qui
        # ont réellement été payés par quelqu'un.
        if (ligne[iq] or 0) < SEUIL_SAUT_VALEUR:
            continue
        cloture = ligne[champs.index("close")]
        ic = champs.index("close")
        apres = [h[1][ic] for h in historie[i + 1:i + 3]]
        if len(apres) < 2 or not cloture or not all(isinstance(x, (int, float)) and x for x in apres):
            continue
        var2 = (apres[-1] / cloture - 1) * 100
        sorties.append({"date": date, "saut_pct": v, "deux_seances_apres_pct": round(var2, 2),
                        "retour": (v < 0 and var2 > 0) or (v > 0 and var2 < 0)})
    if len(sorties) < 3:
        return {"statut": "non_calculable",
                "raison": (f"{len(sorties)} saut(s) de plus de 5 % payé(s) plus de "
                           f"{SEUIL_SAUT_VALEUR // 1_000_000} M FCFA observé(s) sur cette société : "
                           "trop peu pour décrire une réaction")}
    retours = sum(1 for s in sorties if s["retour"])
    return {"statut": "calcule", "sauts": len(sorties),
            "profondeur": "pleine" if len(sorties) >= 8 else "limitee",
            "retours": retours, "taux_retour_pct": round(100 * retours / len(sorties), 1),
            "recul": "deux séances", "exemples": sorties[-3:],
            "regle": ("part des sauts de plus de 5 % suivis, deux séances plus tard, d'un mouvement de sens "
                      "opposé. Mesure rétrospective sur cette archive : elle ne prédit pas le prochain saut")}


SEUIL_MOUVEMENT_PUBLICATION = 3.0   # en dessous, le bruit de séance domine
MIN_PUBLICATIONS_PLEIN = 6


def impacts_publications(company: dict, archive: dict, profondeur_jours: int = 365) -> dict:
    """Une publication officielle a-t-elle réellement fait bouger le cours ?

    Question posée : « une info la veille peut-elle faire chuter, et peut-on
    l'anticiper ? » La partie « anticiper » est impossible — personne ne connaît
    le contenu d'un communiqué avant sa publication. La partie mesurable est
    celle-ci : sur cette société, quand un document officiel sort, le cours
    bouge-t-il ? SIGMA relie chaque publication datée aux séances qui suivent et
    compte les mouvements de plus de 5 % réellement payés.

    Ce que ce chiffre ne dit pas : le sens du prochain mouvement.
    """
    champs = archive["row_fields"]
    iv, iq = champs.index("variation_pct"), champs.index("traded_value_fcfa")
    dates = [s["date"] for s in archive["sessions"]]
    index = {d: i for i, d in enumerate(dates)}
    ticker = company["ticker"]
    seuil_date = (company.get("latest_boc_date") or dates[-1])
    recentes = [n for n in (company.get("documents") or [])
                if n.get("published_date") and n["published_date"] >= _il_y_a(seuil_date, profondeur_jours)]
    sorties = []
    for doc in sorted(recentes, key=lambda x: x["published_date"], reverse=True)[:12]:
        i = index.get(doc["published_date"])
        if i is None:
            # publication tombée un jour sans séance : on cherche la séance suivante
            suivantes = [j for j, d in enumerate(dates) if d >= doc["published_date"]]
            if not suivantes:
                continue
            i = suivantes[0]
        fenetre = archive["sessions"][i:i + 3]
        mouvements = []
        for s_ in fenetre:
            ligne = s_["rows"].get(ticker)
            if not ligne or not isinstance(ligne[iv], (int, float)):
                continue
            if abs(ligne[iv]) >= SEUIL_MOUVEMENT_PUBLICATION and (ligne[iq] or 0) >= SEUIL_SAUT_VALEUR:
                mouvements.append({"date": s_["date"], "variation_pct": ligne[iv]})
        sorties.append({"date": doc["published_date"], "type": doc.get("doc_type"),
                        "label": (doc.get("label") or "")[:120],
                        "mouvement": mouvements[0] if mouvements else None})
    if not sorties:
        return {"statut": "non_calculable",
                "raison": f"aucune publication datée de cette société dans les {profondeur_jours} derniers jours du corpus"}
    avec = sum(1 for x in sorties if x["mouvement"])
    return {
        "statut": "calcule",
        "profondeur": "pleine" if len(sorties) >= MIN_PUBLICATIONS_PLEIN else "limitee",
        "fenetre_jours": profondeur_jours,
        "publications": len(sorties),
        "avec_mouvement": avec,
        "taux_mouvement_pct": round(100 * avec / len(sorties), 1),
        "max_mouvement_pct": max((abs(x["mouvement"]["variation_pct"]) for x in sorties if x["mouvement"]), default=None),
        "detail": sorties[:5],
        "regle": (f"part des publications officielles suivies, dans les trois séances, d'un mouvement d'au moins "
                  f"{SEUIL_MOUVEMENT_PUBLICATION:.0f} % réellement payé (plus de "
                  f"{SEUIL_SAUT_VALEUR // 1_000_000} M FCFA échangés). Mesure du passé : elle documente la "
                  "sensibilité de ce titre à l'information, elle ne dit pas ce que dira la prochaine publication"),
    }


def _il_y_a(iso: str, jours: int) -> str:
    from datetime import date, timedelta
    try:
        return (date.fromisoformat(iso) - timedelta(days=jours)).isoformat()
    except ValueError:
        return "0000-00-00"


# ── Le revenu : ce qu'un actionnaire touche réellement ─────────────────────

def _fig(exercice: dict, cle: str) -> float | None:
    return valeur((exercice.get("figures") or {}).get(cle))


def _ratio(num: float | None, den: float | None, pct: bool = False) -> float | None:
    if not num or not den or den <= 0:
        return None
    r = num / den * (100 if pct else 1)
    return round(r, 2)


def regularite(dh: dict, exercice_reference: int | None) -> dict:
    """Le dividende est-il une politique ou un accident ?

    On ne compte que les exercices **consécutifs réellement payés**, du plus
    récent vers le passé. `current_consecutive_paid_years` du collecteur ne
    suffit pas : il s'arrête au premier trou sans dire lequel.
    """
    annuels = {a["fiscal_year"]: a for a in (dh.get("annual") or []) if a.get("net_amount_fcfa")}
    if not annuels:
        return {"statut": "non_documentee",
                "raison": "aucune distribution rattachée à un exercice dans l'historique collecté"}
    dernier = dh.get("latest_paid_fiscal_year") or max(annuels)
    annees, annee = [], dernier
    while annee in annuels:
        annees.append({"exercice": annee, "dps": round(annuels[annee]["net_amount_fcfa"], 2)})
        annee -= 1
    # Une variation d'un exercice sur l'autre, mesurée seulement à série continue.
    variations = []
    for a, b in zip(annees[1:], annees):
        if a["dps"]:
            variations.append(round((b["dps"] / a["dps"] - 1) * 100, 1))
    return {
        "statut": "documentee",
        "dernier_exercice_paye": dernier,
        "annees_consecutives": len(annees),
        # Le dernier exercice payé peut précéder le dernier exercice publié :
        # ce n'est pas un trou de collecte, c'est un exercice sans distribution.
        # Deux décalages opposés, jamais confondus :
        #   retard des comptes  → le dividende est connu, pas les états financiers
        #                         (CFAC : dividende 2025, derniers comptes 2024) ;
        #   retard du dividende → les comptes sont là, la distribution non
        #                         (SIVC : comptes à jour, dernier versement 2016).
        "en_retard_sur_les_comptes": max(0, exercice_reference - dernier) if exercice_reference else None,
        "comptes_en_retard": bool(exercice_reference and dernier > exercice_reference),
        "variations_recentes_pct": variations[:5],
        "baisses": sum(1 for v in variations if v < 0),
        "hausses": sum(1 for v in variations if v > 0),
        "suite": annees[:5],
    }


def payout(company: dict, dh: dict) -> dict:
    """Part du bénéfice versée, par deux chemins qui ne se mélangent jamais.

    1. **documentaire** — dividendes versés (tableau de financement) ÷ résultat
       net du même exercice. C'est le chiffre comptable, il ne dépend d'aucun
       cours. Disponible pour 11 sociétés.
    2. **identité** — rendement net publié au BOC × PER publié au BOC
       (= dividende ÷ cours × cours ÷ bénéfice). Contrôlée sur les exercices où
       les deux chemins existent : l'écart est celui du dividende retenu et de
       l'exercice de référence, pas une erreur d'arithmétique. Disponible pour
       27 sociétés. Statut `implicite`, jamais présenté comme comptable.
    """
    ser = serie(company)
    docs = []
    for e in ser:
        dv, rn = _fig(e, "dividendes_verses"), _fig(e, "resultat_net")
        p = _ratio(abs(dv) if dv else None, rn, pct=True)
        if p is not None:
            docs.append({"exercice": e.get("exercice"), "payout_pct": p,
                         "dividendes_verses": abs(dv), "resultat_net": rn})
    if docs:
        dernier = docs[-1]
        moyenne = round(sum(d["payout_pct"] for d in docs) / len(docs), 1)
        return {"statut": "documentaire", "dernier": dernier, "moyenne_pct": moyenne,
                "exercices": docs,
                "base": "dividendes versés (tableau de financement) ÷ résultat net du même exercice"}
    # Aucun « dividendes versés » extrait : on ne le remplace pas par le BOC,
    # qui porte souvent sur un autre exercice. On déclare le statut.
    boc = company.get("latest_boc") or {}
    y, per = boc.get("net_dividend_yield_pct"), boc.get("per")
    if isinstance(y, (int, float)) and isinstance(per, (int, float)) and y > 0 and per > 0:
        return {
            "statut": "implicite",
            "dernier": {"payout_pct": round(y * per, 1)},
            "base": "rendement net publié au BOC × PER publié au BOC (identité dividende/bénéfice)",
            "limite": ("déduction : le rendement et le PER portent sur le dernier dividende publié et le dernier "
                       "résultat retenu par la BRVM, qui ne sont pas toujours du même exercice"),
        }
    return {"statut": "non_calculable",
            "raison": ("ni dividendes versés au tableau de financement, ni couple rendement/PER publié au BOC")}


def couverture(company: dict) -> dict:
    """Le dividende est-il payé par la trésorerie de l'exploitation ?

    Seul le chemin documentaire existe : comparer un dividende de l'exercice N
    à un flux d'un autre exercice n'a aucun sens. Absent = dit, jamais estimé.
    """
    for e in reversed(serie(company)):
        flux, dv = _fig(e, "flux_tresorerie_operationnel"), _fig(e, "dividendes_verses")
        if flux and dv:
            return {"statut": "calcule", "exercice": e.get("exercice"),
                    "flux_operationnel": flux, "dividendes_verses": abs(dv),
                    "couverture_x": round(flux / abs(dv), 2),
                    "base": "flux de trésorerie d'exploitation ÷ dividendes versés, même exercice"}
    return {"statut": "non_calculable",
            "raison": "flux d'exploitation et dividendes versés jamais réunis sur un même exercice extrait"}


def revenu(company: dict, cours: float | None) -> dict:
    """Le bloc « ce que ça rapporte », trois preuves séparées et une seule addition.

    Ordre de lecture imposé : d'abord ce qui est prouvé par le dividende, puis
    ce qui est déduit, puis ce qui n'existe pas. Un rendement affiché sans sa
    qualité (régularité, couverture) est un piège : le plus haut rendement de la
    cote peut être celui d'une société qui distribue un exercice exceptionnel.
    """
    dh = company.get("dividend_history") or {}
    boc = company.get("latest_boc") or {}
    ser = serie(company)
    exercice_ref = ser[-1].get("exercice") if ser else None
    reg = regularite(dh, exercice_ref)
    pay = payout(company, dh)
    cov = couverture(company)
    # Rendement : **une seule source**, le BOC, parce que le tableau de
    # paiement de la BRVM publie parfois le montant brut et parfois le net
    # (17/48 brut, 17/48 net sur la collecte) : un rendement calculé en
    # croisant les deux surestime le revenu de 13,6 % dans les cas bruts.
    # Aucun montant n'est donc transféré d'une source à l'autre.
    rendement = boc.get("net_dividend_yield_pct")
    rendement = round(rendement, 2) if isinstance(rendement, (int, float)) else None
    dps_boc = boc.get("last_net_dividend_fcfa")
    date_div = boc.get("last_dividend_date_label")

    points, alertes = [], []
    if rendement is not None:
        points.append(f"{rendement:.2f} % de rendement net, dividende de {dps_boc:.0f} FCFA par action"
                      + (f" mis en paiement le {date_div}" if date_div else "") + " (source : BOC).")
    if reg.get("statut") == "documentee":
        points.append(f"{reg['annees_consecutives']} exercice(s) consécutif(s) avec distribution documentée"
                      + (f", dernier payé : {reg['dernier_exercice_paye']}." if reg.get("dernier_exercice_paye") else "."))
        if reg.get("en_retard_sur_les_comptes") and reg["en_retard_sur_les_comptes"] >= 2:
            alertes.append(f"aucune distribution documentée depuis {reg['dernier_exercice_paye']}, soit "
                           f"{reg['en_retard_sur_les_comptes']} exercices de retard sur les comptes extraits")
    if pay.get("statut") == "documentaire":
        p = pay["dernier"]["payout_pct"]
        points.append(f"{p:.0f} % du résultat versé en {pay['dernier']['exercice']} "
                      f"(moyenne {pay['moyenne_pct']:.0f} % sur {len(pay['exercices'])} exercices).")
        if p > 100:
            alertes.append(f"distribution supérieure au bénéfice en {pay['dernier']['exercice']} : elle a été payée "
                           "par autre chose que le résultat de l'exercice")
    elif pay.get("statut") == "implicite":
        p = pay["dernier"]["payout_pct"]
        points.append(f"≈ {p:.0f} % du bénéfice, déduit du rendement et du PER publiés (pas un chiffre comptable).")
        if p > 120:
            alertes.append(f"distribution déduite très supérieure au bénéfice (≈ {p:.0f} %) : à confirmer au tableau "
                           "de financement avant d'en faire un revenu récurrent")
    if cov.get("statut") == "calcule":
        points.append(f"dividende couvert {cov['couverture_x']:.2f} fois par le flux d'exploitation de "
                      f"{cov['exercice']}.")
        if cov["couverture_x"] < 1:
            alertes.append(f"le flux d'exploitation de {cov['exercice']} ne couvre pas la distribution "
                           f"({cov['couverture_x']:.2f} fois)")
    if rendement is not None and rendement > 20:
        alertes.append(f"rendement de {rendement:.0f} % : hors norme pour une société qui distribue "
                       "régulièrement, à traiter comme un versement exceptionnel ou un cours déprimé, pas comme un revenu")
    dernier_payout = (pay.get("dernier") or {}).get("exercice")
    if reg.get("comptes_en_retard"):
        points.append(f"le dividende de l'exercice {reg['dernier_exercice_paye']} est publié, mais les états financiers "
                      "de cet exercice ne sont pas encore extraits"
                      + (f" : le taux de distribution n'est calculable que jusqu'à {dernier_payout}."
                         if dernier_payout else "."))
    if reg.get("statut") == "documentee" and reg.get("en_retard_sur_les_comptes"):
        alertes.append(f"le dernier exercice payé ({reg['dernier_exercice_paye']}) précède le dernier exercice "
                       f"publié ({exercice_ref}) : le taux décrit un versement passé, pas un revenu attendu")
    if reg.get("statut") == "documentee" and reg.get("baisses"):
        alertes.append(f"{reg['baisses']} baisse(s) de dividende sur les {len(reg['variations_recentes_pct'])} "
                       "dernières variations : la politique n'est pas une rente fixe")

    # Les trois preuves d'un revenu, chacune vérifiable séparément. Ce n'est
    # pas un score : c'est un décompte, et le détail dit laquelle manque.
    preuves = {
        "regularite": bool(reg.get("statut") == "documentee" and reg.get("annees_consecutives", 0) >= 3),
        "financement": bool(pay.get("statut") == "documentaire" and pay.get("dernier", {}).get("payout_pct", 999) <= 100),
        "couverture": bool(cov.get("statut") == "calcule" and cov.get("couverture_x", 0) >= 1),
    }
    regle = ("Un rendement ne devient un revenu que si trois preuves tiennent ensemble : le dividende est "
             "renouvelé (3 exercices consécutifs), financé par le bénéfice (≤ 100 % du résultat), et payé par "
             "l'exploitation (flux ≥ distribution). Trois preuves sur trois : revenu établi. Aucune : rendement "
             "à ne pas considérer comme un revenu.")

    # Niveau de preuve, du plus solide au plus faible. Il ne note pas la
    # société : il note la qualité de CE QUE SIGMA SAIT d'elle.
    if reg.get("statut") == "documentee" and pay.get("statut") == "documentaire":
        preuve = "documentaire"
    elif reg.get("statut") == "documentee" or pay.get("statut") == "implicite":
        preuve = "partielle"
    else:
        preuve = "absente"

    return {
        "rendement_pct": rendement,
        "rendement_source": "BOC — dernier dividende net publié, rapporté au cours du jour",
        "dps_reference": round(dps_boc, 2) if isinstance(dps_boc, (int, float)) else None,
        "date_paiement": date_div,
        # Le rendement élevé n'est pas une qualité : si le dividende n'a pas
        # été renouvelé, le taux affiché décrit un versement passé.
        "rendement_en_retard": bool((reg.get("en_retard_sur_les_comptes") or 0) >= 1),
        "regularite": reg,
        "payout": pay,
        "couverture": cov,
        "preuve": preuve,
        "preuves": preuves,
        "preuves_reunies": sum(preuves.values()),
        "regle": regle,
        "points": points[:4],
        "alertes": alertes[:3],
    }


@dataclass
class Verdict:
    ticker: str
    nom: str
    secteur: str
    cours: float | None
    horizons: dict = field(default_factory=dict)
    capitalisation: dict = field(default_factory=dict)
    position_longue: dict = field(default_factory=dict)
    revenu: dict = field(default_factory=dict)
    entreprise: dict = field(default_factory=dict)
    variation: dict = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def construire(data: dict, archive: dict) -> dict[str, Verdict]:
    champs = archive["row_fields"]
    seances: dict[str, list[dict]] = {}
    for s in archive["sessions"]:
        for ticker, ligne in s["rows"].items():
            seances.setdefault(ticker, []).append(dict(zip(champs, ligne)))

    limites = limites_variation(archive)
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
        v.position_longue = position_longue(clotures) or {}
        decomp = decomposition(hist)
        v.horizons["moyen"] = lecture_moyen(distribution_per(pers), boc)
        if decomp and v.horizons["moyen"].get("statut") == "calcule":
            v.horizons["moyen"]["decomposition"] = decomp
            v.horizons["moyen"]["details"].append(decomp["phrase"])
        v.horizons["long"] = lecture_long(c)
        v.revenu = revenu(c, v.cours)
        v.entreprise = roe_serie(c)
        v.variation = {
            "limite_pct": limites["amplitude_max_pct"] if limites.get("statut") == "calcule" else None,
            "reaction": reactions(c, archive),
            "publications": impacts_publications(c, archive),
        }

        # Capitalisation, trois niveaux de preuve distincts et jamais confondus :
        #   1. nombre d'actions lu dans un document officiel  → capitalisation directe ;
        #   2. identité vérifiée capitalisation = PER publié × résultat net de
        #      l'exercice de référence → capitalisation implicite. Contrôlée sur
        #      les deux seules sociétés dont le nombre d'actions est prouvé :
        #      SGBC 1213,33 Md / PER 11,97 = 101 365 M contre 101 228 M publiés
        #      (0,14 % d'écart) ; CIEC 280,00 Md / PER 21,33 = 13 127 M contre
        #      13 100 M (0,20 %). L'identité tient, elle reste une déduction ;
        #   3. aucun des deux → absence motivée, avec ce qui la débloquerait.
        # Le nombre d'actions, lui, n'est JAMAIS déduit : il reste le verrou.
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
            # Pas de « non calculable » sec : on dit ce qui manque, d'où cela
            # vient, et ce qui le débloquerait. Ce n'est pas la même chose
            # qu'une société qui n'a publié aucun document, et l'écran doit
            # pouvoir faire la différence.
            # niveau 2 : capitalisation implicite par le PER publié
            per_publie = boc.get("per")
            rn_ref = None
            rn_exercice = None
            for e in reversed(serie(c)):
                valeur_rn = valeur((e.get("figures") or {}).get("resultat_net"))
                if valeur_rn:
                    rn_ref, rn_exercice = valeur_rn, e.get("exercice")
                    break
            # (Un niveau 2 bis — résultat net ÷ BPA publié — donnerait un nombre
            # d'actions déduit. Il n'est pas branché : le BOC collecté expose le
            # PER mais pas le BPA, et l'ajouter au schéma de collecte est un
            # chantier, pas une décision de lecture.)
            if isinstance(per_publie, (int, float)) and per_publie > 0 and rn_ref and rn_ref > 0:
                v.capitalisation = {
                    "statut": "implicite",
                    "valeur_fcfa": round(per_publie * rn_ref),
                    "per_publie": per_publie,
                    "resultat_net": rn_ref,
                    "exercice": rn_exercice,
                    "base": ("déduite de l'identité capitalisation = PER publié au BOC × résultat net de l'exercice "
                             f"{rn_exercice}. Contrôlée à 0,14 % et 0,20 % sur les deux sociétés où le nombre "
                             "d'actions est prouvé."),
                    "limite": "déduction, pas un nombre d'actions vérifié : elle suit le résultat retenu par la BRVM",
                }
                verdicts[t] = v
                continue
            docs = c.get("documents") or []
            etats = [x for x in docs
                     if "etats_financiers" in (x.get("doc_type") or "")
                     or "etat" in normalize_texte(x.get("label") or "")
                     or "financ" in normalize_texte(x.get("label") or "") and "rapport" not in normalize_texte(x.get("label") or "")[:10]]
            if not docs:
                origine = "aucun document émetteur indexé pour cette société dans la collecte"
                deblocage = "indexer ses publications officielles sur brvm.org, puis ses états financiers"
            elif not etats:
                origine = (f"{len(docs)} document(s) indexé(s), aucun état financier publié "
                           f"({', '.join(sorted({(x.get('doc_type') or 'type inconnu') for x in docs}))})")
                deblocage = "attendre ou retrouver la publication des états financiers de l'exercice"
            else:
                origine = (f"{len(etats)} état(s) financier(s) indexé(s) mais le nombre d'actions n'a été lu dans aucun ; "
                           f"{len(serie(c))} exercice(s) extraits")
                deblocage = "lire le nombre d'actions sur la page « capital » du rapport annuel, puis l'inscrire au registre"
            v.capitalisation = {"statut": "non_calculable",
                                "raison": "nombre d'actions absent des documents indexés",
                                "origine": origine,
                                "deblocage": deblocage}
        verdicts[t] = v
    return verdicts


def manques(verdicts: dict[str, Verdict]) -> list[dict]:
    """Ce qui empêche chaque société d'être complète, écrit une fois pour toutes.

    Un manque n'est pas une fatalité : c'est une tâche. Ce registre est
    reconstruit depuis les verdicts pour qu'aucune société ne sorte de l'écran
    sans que l'on sache exactement ce qui lui manque et où le prendre.
    """
    taches = []
    for ticker, v in verdicts.items():
        for horizon, libelle in (("court", "court terme"), ("moyen", "moyen terme"), ("long", "long terme")):
            h = v.horizons[horizon]
            if h.get("statut") == "calcule" and h.get("profondeur", "pleine") == "pleine":
                continue
            taches.append({
                "ticker": ticker,
                "societe": v.nom,
                "horizon": libelle,
                "etat": "limite" if h.get("statut") == "calcule" else "absent",
                "raison": h.get("raison") or (
                    f"distribution courte ({h.get('donnees', {}).get('seances')} séances)" if horizon == "moyen"
                    else f"lecture courte ({len(h.get('exercices') or [])} exercices complets)"),
                "source": ("archive BOC — bulletin officiel de la cote" if horizon in ("court", "moyen")
                           else "états financiers officiels de l'émetteur"),
            })
        ent = v.entreprise or {}
        if ent.get("statut") != "calcule":
            taches.append({
                "ticker": ticker, "societe": v.nom, "horizon": "rentabilité",
                "etat": "absent",
                "raison": ent.get("raison") or "aucun exercice ne réunit résultat net et fonds propres",
                "source": "bilan et compte de résultat des états financiers officiels, même exercice",
                "deblocage": ("les fonds propres sont présents dans le bilan : cette société a des états extraits "
                              "sans la ligne « capitaux propres »" if ent.get("exercices_sans_fonds_propres")
                              else "extraire la ligne capitaux propres du bilan de chaque exercice"),
            })
        rev = v.revenu or {}
        if rev.get("preuve") != "documentaire":
            preuves = rev.get("preuves") or {}
            manquantes = [libelle for cle, libelle in (
                ("regularite", "régularité du dividende (3 exercices consécutifs)"),
                ("financement", "financement par le bénéfice (dividendes versés ÷ résultat, ≤ 100 %)"),
                ("couverture", "couverture par le flux d'exploitation du même exercice"),
            ) if not preuves.get(cle)]
            taches.append({
                "ticker": ticker, "societe": v.nom, "horizon": "revenu",
                "etat": "limite" if rev.get("rendement_pct") is not None else "absent",
                "raison": ("preuves manquantes : " + " · ".join(manquantes)) if manquantes
                          else "rendement publié mais aucune preuve de durabilité réunie",
                "source": ("BOC (rendement) + tableau de financement des états financiers (dividendes versés, "
                           "flux d'exploitation)"),
                "deblocage": ("extraire « dividendes versés » et le flux d'exploitation du tableau de financement "
                              "pour le même exercice, et rattacher chaque avis de paiement à son exercice"),
            })
        if v.capitalisation.get("statut") == "non_calculable":
            taches.append({
                "ticker": ticker, "societe": v.nom, "horizon": "capitalisation", "etat": "absent",
                "raison": v.capitalisation.get("raison"),
                "source": v.capitalisation.get("origine"),
                "deblocage": v.capitalisation.get("deblocage"),
            })
    return taches


def resume(verdicts: dict[str, Verdict]) -> dict:
    def compte(horizon: str, statut: str) -> int:
        return sum(1 for v in verdicts.values() if v.horizons[horizon].get("statut") == statut)

    def pleine(horizon: str) -> int:
        return sum(1 for v in verdicts.values()
                   if v.horizons[horizon].get("statut") == "calcule"
                   and v.horizons[horizon].get("profondeur", "pleine") == "pleine")

    return {
        "societes": len(verdicts),
        "court_calcule": compte("court", "calcule"),
        "moyen_calcule": compte("moyen", "calcule"),
        "long_calcule": compte("long", "calcule"),
        # Les mêmes trois capacités, comptées uniquement quand la série est
        # assez profonde pour que le chiffre veuille dire quelque chose.
        "court_plein": pleine("court"),
        "moyen_plein": pleine("moyen"),
        "long_plein": pleine("long"),
        "capitalisation_calculee": sum(1 for v in verdicts.values() if v.capitalisation.get("statut") == "calcule"),
        "capitalisation_implicite": sum(1 for v in verdicts.values() if v.capitalisation.get("statut") == "implicite"),
        "position_longue_calculee": sum(1 for v in verdicts.values() if v.position_longue),
        "roe_calcule": sum(1 for v in verdicts.values() if (v.entreprise or {}).get("statut") == "calcule"),
        "roe_plein": sum(1 for v in verdicts.values() if (v.entreprise or {}).get("profondeur") == "pleine"),
        "revenu_documente": sum(1 for v in verdicts.values() if (v.revenu or {}).get("preuve") == "documentaire"),
        "revenu_partiel": sum(1 for v in verdicts.values() if (v.revenu or {}).get("preuve") == "partielle"),
        "revenu_absent": sum(1 for v in verdicts.values() if (v.revenu or {}).get("preuve") == "absente"),
        "rendement_calcule": sum(1 for v in verdicts.values() if (v.revenu or {}).get("rendement_pct") is not None),
        "revenu_trois_preuves": sum(1 for v in verdicts.values() if (v.revenu or {}).get("preuves_reunies") == 3),
        # La cible honnête, comptée exactement : trois exercices de rentabilité
        # réels, un moyen et un long terme de profondeur pleine. On ne compte
        # pas « trois horizons calculés » — un horizon peut être calculé avec
        # deux exercices et ne rien prouver.
        "valorisables_3_exercices": sum(
            1 for v in verdicts.values()
            if v.horizons["moyen"].get("profondeur") == "pleine"
            and v.horizons["long"].get("profondeur") == "pleine"
            and len((v.entreprise or {}).get("exercices") or []) >= 3
        ),
        "valorisables_complets": sum(
            1 for v in verdicts.values()
            if v.horizons["moyen"].get("profondeur") == "pleine"
            and v.horizons["long"].get("profondeur") == "pleine"
            and len((v.entreprise or {}).get("exercices") or []) >= 3
            and (v.revenu or {}).get("preuve") == "documentaire"
        ),
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
    ap.add_argument("--manques", action="store_true", help="lister ce qui empêche chaque société d'être complète")
    args = ap.parse_args()

    data = json.loads(DATA.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    verdicts = construire(data, archive)
    if args.tickers:
        verdicts = {t: v for t, v in verdicts.items() if t in {x.upper() for x in args.tickers}}

    if args.manques:
        taches = manques(verdicts)
        for tache in sorted(taches, key=lambda x: (x["etat"], x["ticker"])):
            print(f"{tache['ticker']:7} {tache['horizon']:16} {tache['etat']:8} {tache['raison']}")
        print(f"\n{len(taches)} manque(s) sur {len(verdicts)} sociétés.")
        return

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
                "per_seances_plein": PER_SEANCES_PLEIN,
                "per_seances_limite": PER_SEANCES_LIMITE,
                "min_exercices": MIN_EXERCICES,
                "min_exercices_limite": MIN_EXERCICES_LIMITE,
            },
            # Les contraintes de marché, mesurées une fois et publiées à part :
            # plafond/plancher observés, fréquence et taille des sauts.
            "marche": {
                "limites": limites_variation(archive),
                "sauts": {k: v for k, v in sauts(archive).items() if k != "detail"},
            },
            "resume": resume(verdicts),
            "manques": manques(verdicts),
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

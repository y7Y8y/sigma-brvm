#!/usr/bin/env python3
"""Rend les artefacts fermés de l'audit pilote BPA (5 sociétés × 10 ans).

Le fichier ``decisions.json`` est la source de vérité manuelle du pilote :
chaque cellule y a été classée après ouverture des documents et
contre-lecture indépendante. Ce script ne fait aucun appel réseau et ne
modifie ni le collecteur ni le jeu de données publié. Il vérifie la
complétude des 50 cellules, calcule des taux séparés et régénère la
matrice, le résumé, la liste des sources ouvertes et le rapport.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "audits" / "pilote_bpa_5"
DECISIONS_PATH = AUDIT_DIR / "decisions.json"
INVENTORY_PATH = AUDIT_DIR / "inventory.json"
EXTRACTIONS_PATH = AUDIT_DIR / "extractions.json"

TICKERS = ("CIEC", "SNTS", "SDSC", "BOAC", "ETIT")
YEARS = range(2016, 2026)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if value.is_integer():
            value = int(value)
        else:
            return f"{value:,.3f}".replace(",", " ").replace(".", ",").rstrip("0").rstrip(",")
    return f"{value:,}".replace(",", " ")


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def validate(decisions: dict[str, Any]) -> list[dict[str, Any]]:
    rows = decisions["rows"]
    keys = [(row["ticker"], row["exercice"]) for row in rows]
    expected = [(ticker, year) for ticker in TICKERS for year in YEARS]
    if sorted(keys) != sorted(expected) or len(set(keys)) != 50:
        raise ValueError("La matrice pilote doit contenir exactement 5 sociétés × 10 exercices.")
    for row in rows:
        if row["applicabilite"] != "APPLICABLE_CONFIRMEE":
            raise ValueError(f"Applicabilité non confirmée: {row['ticker']} {row['exercice']}")
        if not row.get("sources") or not row.get("validation"):
            raise ValueError(f"Preuve manquante: {row['ticker']} {row['exercice']}")
        retained = row.get("bpa_retenu")
        if retained is not None and not retained["unite"].startswith("FCFA"):
            raise ValueError(f"BPA retenu hors FCFA: {row['ticker']} {row['exercice']}")
        if row["statut_bpa"] == "PUBLIE_CONFIRME_DEUX_DOCUMENTS":
            if retained is None or row["confirmations_documents_distincts"] < 2:
                raise ValueError(f"Confirmation deux documents invalide: {row['ticker']} {row['exercice']}")
    return rows


def build_summary(
    rows: list[dict[str, Any]], inventory: dict[str, Any], extractions: dict[str, Any]
) -> dict[str, Any]:
    total = len(rows)
    retained = [row for row in rows if row.get("bpa_retenu") is not None]
    confirmed = [
        row for row in retained if row.get("confirmations_documents_distincts", 0) >= 2
    ]
    single_validated = [
        row
        for row in retained
        if row.get("confirmations_documents_distincts", 0) < 2
    ]
    ratios = [row for row in rows if row.get("ratio_indicatif_fin_exercice")]
    status_counts = Counter(row["statut_bpa"] for row in rows)
    weighted_controls = []
    weighted_discordant = []
    for row in rows:
        denominator = row.get("denominateur") or {}
        control = row.get("controle_recalcul") or {}
        if str(denominator.get("type") or "").startswith("Nombre moyen pondéré"):
            if row.get("bpa_retenu") is not None:
                weighted_controls.append(row)
            elif "ECART" in str(control.get("verdict") or ""):
                weighted_discordant.append(row)
    individual_scope = []
    for row in rows:
        if any(
            "individuel" in str(item.get("detail") or "").lower()
            for item in row.get("publications_non_retenues") or []
        ):
            individual_scope.append(row)

    by_ticker: dict[str, Any] = {}
    for ticker in TICKERS:
        subset = [row for row in rows if row["ticker"] == ticker]
        subset_retained = [row for row in subset if row.get("bpa_retenu") is not None]
        by_ticker[ticker] = {
            "cellules": len(subset),
            "bpa_publie_fcfa_retenu": len(subset_retained),
            "bpa_publie_fcfa_retenu_pct": rate(len(subset_retained), len(subset)),
            "confirmes_deux_documents": sum(
                1 for row in subset_retained if row["confirmations_documents_distincts"] >= 2
            ),
            "ratios_indicatifs_separes": sum(
                1 for row in subset if row.get("ratio_indicatif_fin_exercice")
            ),
            "statuts": dict(Counter(row["statut_bpa"] for row in subset)),
        }

    return {
        "cellules_brutes": total,
        "cellules_applicables_confirmees": total,
        "documents_indexes_pages_brvm": sum(
            len(block.get("documents") or []) for block in inventory.values()
        ),
        "documents_ouverts": sum(
            len(block.get("documents") or []) for block in extractions.values()
        ),
        "documents_ouverts_dont_autre_emetteur_exclu": 1,
        "bpa_publie_fcfa_retenu": {
            "observations": len(retained),
            "denominateur": total,
            "taux_pct": rate(len(retained), total),
            "confirmes_deux_documents": len(confirmed),
            "confirmes_deux_documents_pct": rate(len(confirmed), total),
            "un_document_valide_par_controle": len(single_validated),
        },
        "bpa_recalcule_comparable_fcfa_retenu": {
            "observations": 0,
            "denominateur": total,
            "taux_pct": 0.0,
            "note": "Aucun recalcul n'est substitué à un BPA publié ; les recalculs servent de contrôles indépendants.",
        },
        "controles_numerateur_attribuable_ou_part_groupe_sur_pondere": {
            "concordants_sur_bpa_retenus": len(weighted_controls),
            "discordants_rejetes": len(weighted_discordant),
        },
        "ratios_indicatifs_fin_exercice_separes": {
            "observations": len(ratios),
            "denominateur": total,
            "taux_pct": rate(len(ratios), total),
            "note": "Hors couverture BPA comparable.",
        },
        "publications_par_action_non_retenues": {
            "cellules": status_counts.get("PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE", 0)
            + status_counts.get("PUBLIE_INCOHERENT_NON_RETENU", 0),
            "dont_devise_ou_composante": status_counts.get(
                "PUBLIE_NON_RETENU_DEVISE_OU_COMPOSANTE", 0
            ),
            "dont_incoherence_source": status_counts.get(
                "PUBLIE_INCOHERENT_NON_RETENU", 0
            ),
            "bpa_individuels_non_fusionnes_cellules": len(individual_scope),
        },
        "absences": {
            "NON_PUBLIE_DANS_SOURCES_VERIFIEES": status_counts.get(
                "NON_PUBLIE_DANS_SOURCES_VERIFIEES", 0
            ),
            "DOCUMENT_INTROUVABLE": status_counts.get("DOCUMENT_INTROUVABLE", 0),
            "ILLISIBLE": status_counts.get("ILLISIBLE", 0),
            "NON_RECHERCHE": status_counts.get("NON_RECHERCHE", 0),
            "NON_APPLICABLE": status_counts.get("NON_APPLICABLE", 0),
        },
        "statuts_bpa": dict(status_counts),
        "par_societe": by_ticker,
        "porte_collecte_complete": "REFUSEE_AVANT_CORRECTIFS_ET_TEST_DE_NON_REGRESSION_SUR_LE_PILOTE",
    }


def flatten_row(row: dict[str, Any], company: dict[str, Any]) -> dict[str, Any]:
    retained = row.get("bpa_retenu") or {}
    control = row.get("controle_recalcul") or {}
    ratio = row.get("ratio_indicatif_fin_exercice") or {}
    numerator = row.get("numerateur") or {}
    denominator = row.get("denominateur") or {}
    extractor = row.get("extracteur") or {}
    sources = " ; ".join(
        f"{source['document']} (p. {source['pages']})" for source in row.get("sources") or []
    )
    return {
        "ticker": row["ticker"],
        "societe": company.get("nom"),
        "exercice": row["exercice"],
        "applicabilite": row["applicabilite"],
        "statut_bpa": row["statut_bpa"],
        "statut_documentaire": row["statut_documentaire"],
        "perimetre_retenu": row["perimetre_retenu"],
        "bpa_retenu_fcfa": retained.get("valeur"),
        "bpa_retenu_unite": retained.get("unite"),
        "confirmations_documents_distincts": row["confirmations_documents_distincts"],
        "controle_recalcul_valeur": control.get("valeur"),
        "controle_recalcul_unite": control.get("unite"),
        "controle_recalcul_verdict": control.get("verdict"),
        "ratio_indicatif_fin_exercice_fcfa": ratio.get("valeur_fcfa"),
        "ratio_indicatif_formule": ratio.get("formule"),
        "numerateur_type": numerator.get("type"),
        "numerateur_valeur": numerator.get("valeur"),
        "numerateur_unite": numerator.get("unite"),
        "denominateur_type": denominator.get("type"),
        "denominateur_valeur": denominator.get("valeur"),
        "denominateur_unite": denominator.get("unite"),
        "publications_non_retenues": json.dumps(
            row.get("publications_non_retenues") or [], ensure_ascii=False
        ),
        "drapeaux": ";".join(row.get("drapeaux") or []),
        "sources": sources,
        "validation_independante": row["validation"],
        "extracteur_resultat": extractor.get("resultat"),
        "extracteur_verdict": extractor.get("verdict"),
    }


def write_sources(extractions: dict[str, Any]) -> None:
    path = AUDIT_DIR / "sources_examinees.csv"
    fields = [
        "ticker", "exercice_document", "label", "doc_type", "published_date", "url",
        "pages", "native_text_chars", "bytes", "sha256", "supplementaire_apres_contrelecture",
        "statut_source_pilote", "extraction_error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for ticker in TICKERS:
            for doc in extractions[ticker]["documents"]:
                status = "SOURCE_EXAMINEE"
                if doc.get("filename") == "etats_financiers_2017_ecobank_ci.pdf":
                    status = "EXCLUE_AUTRE_EMETTEUR_ECOBANK_COTE_D_IVOIRE"
                writer.writerow(
                    {
                        "ticker": ticker,
                        "exercice_document": doc.get("exercice"),
                        "label": doc.get("label"),
                        "doc_type": doc.get("doc_type"),
                        "published_date": doc.get("published_date"),
                        "url": doc.get("url"),
                        "pages": doc.get("pages"),
                        "native_text_chars": doc.get("native_text_chars"),
                        "bytes": doc.get("bytes"),
                        "sha256": doc.get("sha256"),
                        "supplementaire_apres_contrelecture": bool(
                            doc.get("supplementaire_apres_contrelecture")
                        ),
                        "statut_source_pilote": status,
                        "extraction_error": doc.get("extraction_error"),
                    }
                )


COMPANY_FINDINGS = {
    "CIEC": [
        "Le BPA IFRS consolidé est présent et cohérent de 2019 à 2025, avec 56 000 000 d'actions. Les documents récents mélangent dans un même PDF les états personnels SYSCOHADA et les états consolidés IFRS : le périmètre doit être lu dans le contenu, pas dans le seul nom du fichier.",
        "2016–2018 ne publient pas de BPA dans les sources ouvertes. Le fractionnement de 20 pour 1 du 19 octobre 2017 interdit d'appliquer rétrospectivement le dénominateur actuel sans mention d'unité.",
    ],
    "SNTS": [
        "Le BPA IFRS retenu couvre 2022–2025. Le rapport annuel 2024 est indispensable : il publie la troisième colonne 2022 et la note de dénominateur pondéré. Les états condensés 2024 contiennent une ligne BPA décalée (2 359 sous 2023 au lieu de 2 794 ; 2 110 sous 2022).",
        "2019 et 2020 restent en DOCUMENT_INTROUVABLE : l'inventaire BRVM ne contient que des synthèses/rapports de gestion, sans numérateur attribuable. Pour 2016–2018, l'ancien libellé « part de l'entreprise consolidante » et les pages au-delà de 80 échappent à l'extracteur.",
    ],
    "SDSC": [
        "Les comptes consolidés IFRS donnent un BPA validé pour 2018–2021, avec numérateur part du Groupe et dénominateur pondéré tenant compte des actions d'autocontrôle. Les comptes individuels IFRS publient d'autres BPA (266, 232, 349, 371, 318) qui ne doivent jamais être fusionnés avec la série consolidée.",
        "2022 est rejeté : le BPA consolidé imprimé (250,9) ne concorde ni avec le résultat part du Groupe du compte (contrôle 259,54) ni avec une note propre. À partir de 2023, les sources BRVM ouvertes sont des synthèses SYSCOHADA/rapports CAC sans BPA.",
    ],
    "BOAC": [
        "Aucun BPA publié sur les dix exercices dans les sources vérifiées. Les états bancaires fournissent en revanche le résultat et le capital ; les ratios de fin d'exercice sont donc tenus dans une colonne séparée.",
        "La structure du capital change deux fois : attribution gratuite 1 pour 1 puis fractionnement 10 pour 1 en 2017, puis nouvelle attribution gratuite 1 pour 1 en 2024 (capital 20 → 40 milliards, jouissance au 1er janvier 2024). Toute série par action exige un registre d'événements et un retraitement explicite.",
    ],
    "ETIT": [
        "Toutes les années contiennent une information par action, mais seules 2022–2024 sont retenues en FCFA comme totaux de leur vintage. Les autres années sont bloquées par la devise USD, la séparation activités poursuivies/arrêtées, des retraitements ou des versions remplacées.",
        "Le document 2017 d'Ecobank Côte d’Ivoire présent dans les candidats ETIT est exclu : c'est un autre émetteur. Les décimales espacées (« 1 ,041 », « 1 .68 », « 1 0.00 ») et les doubles colonnes cents USD/FCFA rendent l'extracteur actuel non fiable sur cet émetteur.",
    ],
}


BLOCKERS = [
    ("P0", "Sélection documentaire", "Approfondir la pagination et reconnaître les « comptes consolidés/individuels IFRS » classés « autre » ; exclure tout document dont l'émetteur lu dans le PDF diffère de la page d'origine ; exclure explicitement les intermédiaires au 30 juin/31 mars/30 septembre."),
    ("P0", "Mise en page BPA", "Lire les en-têtes BPA suivis des années et de la sous-ligne « - de base » sur plusieurs lignes ; ne jamais prendre une référence de note (9.2, 8) ni un numéro de page de sommaire pointillé pour une valeur."),
    ("P0", "Devise et composantes", "Ajouter devise, composante (total/poursuivies/arrêtées), périmètre (consolidé/individuel/social) et vintage (initial/retraité/audité) avant tout champ BPA unique. Sans ces champs, ETIT et SDSC ne sont pas publiables proprement."),
    ("P0", "Colonnes et pages", "Traiter les tableaux à trois exercices et les colonnes précédent-d'abord ; rechercher d'abord les pages pertinentes dans tout le texte au lieu de s'arrêter à 80 pages ou 24 pages OCR."),
    ("P0", "Nombres", "Parser les décimales avec espaces autour du séparateur et les doubles colonnes cents USD/FCFA sans mélanger les unités ; conserver la ligne et les coordonnées de colonne comme preuve."),
    ("P0", "Cohérence source", "Mettre en quarantaine toute valeur dont le contrôle numérateur/dénominateur diverge au-delà de la tolérance d'arrondi, et toute ligne contredite par un rapport annuel plus complet (SNTS 2023, SDSC 2022)."),
    ("P1", "Capital", "Construire le registre des fractionnements, actions gratuites, augmentations et actions d'autocontrôle avant de calculer ou d'enchaîner un ratio par action."),
    ("P1", "Performance", "Éviter le traitement intégral coûteux des très longs rapports : index texte rapide, ciblage des pages BPA/capital, puis extraction structurée des seules pages retenues."),
]


def render_readme(
    decisions: dict[str, Any], rows: list[dict[str, Any]], summary: dict[str, Any]
) -> str:
    companies = decisions["metadata"]["societes"]
    published = summary["bpa_publie_fcfa_retenu"]
    ratios = summary["ratios_indicatifs_fin_exercice_separes"]
    lines: list[str] = []
    lines += [
        "# Audit pilote BPA fermé — 5 sociétés × 10 exercices (2016–2025)",
        "",
        "**Date de clôture du pilote : 24 octobre 2026.**",
        "",
        "## Décision de porte",
        "",
        "**La collecte complète BPA sur les 480 cellules ne doit pas être lancée avec l'extracteur actuel.** Le pilote est fermé documentairement (50/50 cellules classées), mais il prouve des défauts bloquants de sélection, de mise en page, de devise/composantes, de colonnes et de contrôle de cohérence. La prochaine étape est de corriger ces défauts, puis de rejouer exactement ces 50 cellules comme test de non-régression avant toute extension.",
        "",
        "Aucune collecte complète n'a été lancée et le jeu de données publié de SIGMA n'a pas été modifié par ce pilote.",
        "",
        "## Périmètre fermé",
        "",
        f"Les pages BRVM des cinq émetteurs contiennent {summary['documents_indexes_pages_brvm']} documents indexés dans l'inventaire profond. {summary['documents_ouverts']} sources candidates (annuelles, comparatives ou pièces d'audit) ont été ouvertes et contre-lues, dont 1 document d'un autre émetteur, exclu. Les statuts d'absence valent uniquement pour les sources énumérées dans `sources_examinees.csv` et les décisions de `decisions.json` ; ils ne prétendent pas épuiser les sites des émetteurs.",
        "",
        "| Société | Introduction BRVM | Périmètre de référence du pilote | Rôle dans le pilote |",
        "|---|---:|---|---|",
    ]
    roles = {
        "CIEC": "série IFRS récente, fractionnement 2017",
        "SNTS": "consolidé IFRS, troisième colonne et source divergente",
        "SDSC": "consolidé vs individuel, autocontrôle, scans et changement de nom",
        "BOAC": "banque sans BPA publié, capital doublé en 2017 et en 2024",
        "ETIT": "USD/FCFA, activités arrêtées, retraitements et long rapport en anglais",
    }
    for ticker in TICKERS:
        company = companies[ticker]
        lines.append(
            f"| {ticker} — {company['nom']} | {company['introduction_brvm']} | {company['perimetre_reference_bpa']} | {roles[ticker]} |"
        )
    lines += [
        "",
        "Les cinq introductions sont antérieures à 2016 : les 50 cellules sont donc applicables et le dénominateur des taux du pilote est 50.",
        "",
        "## Taux séparés — aucun taux global masquant les lacunes",
        "",
        "| Mesure | Numérateur | Dénominateur | Taux | Lecture |",
        "|---|---:|---:|---:|---|",
        f"| BPA publié en FCFA, validé et retenu | {published['observations']} | 50 | {fmt_number(published['taux_pct'])} % | seule couverture BPA comparable retenue par le pilote |",
        f"| dont confirmé par au moins deux documents distincts | {published['confirmes_deux_documents']} | 50 | {fmt_number(published['confirmes_deux_documents_pct'])} % | niveau de confirmation le plus fort |",
        f"| dont un document + contre-lecture/contrôle indépendant | {published['un_document_valide_par_controle']} | 50 | {fmt_number(rate(published['un_document_valide_par_controle'], 50))} % | inclus dans les {published['observations']} ; ce contrôle ne transforme pas la valeur en BPA recalculé comparable |",
        "| BPA recalculé comparable substitué à une publication | 0 | 50 | 0,0 % | les recalculs sont des contrôles, pas des substitutions |",
        f"| Ratio indicatif résultat / actions de fin d'exercice | {ratios['observations']} | 50 | {fmt_number(ratios['taux_pct'])} % | hors couverture BPA |",
        f"| Publication par action trouvée mais non retenue | {summary['publications_par_action_non_retenues']['cellules']} | 50 | {fmt_number(rate(summary['publications_par_action_non_retenues']['cellules'], 50))} % | devise/composante ou incohérence de source |",
        f"| Non publié dans les sources vérifiées | {summary['absences']['NON_PUBLIE_DANS_SOURCES_VERIFIEES']} | 50 | {fmt_number(rate(summary['absences']['NON_PUBLIE_DANS_SOURCES_VERIFIEES'], 50))} % | après examen effectif des sources listées |",
        f"| Document annuel complet introuvable | {summary['absences']['DOCUMENT_INTROUVABLE']} | 50 | {fmt_number(rate(summary['absences']['DOCUMENT_INTROUVABLE'], 50))} % | SNTS 2019 et 2020 |",
        "| Illisible / non recherché / non applicable | 0 / 0 / 0 | 50 | 0,0 % | après OCR ciblé et lectures visuelles |",
        "",
        f"Contrôles numérateur attribuable ou part du Groupe ÷ nombre moyen pondéré : {summary['controles_numerateur_attribuable_ou_part_groupe_sur_pondere']['concordants_sur_bpa_retenus']} concordants sur des BPA retenus et {summary['controles_numerateur_attribuable_ou_part_groupe_sur_pondere']['discordants_rejetes']} discordant rejeté (SDSC 2022). {summary['publications_par_action_non_retenues']['bpa_individuels_non_fusionnes_cellules']} cellules SDSC possèdent aussi un BPA individuel IFRS, conservé séparément du périmètre consolidé.",
        "",
        "## Résultat par société",
        "",
        "| Société | BPA FCFA retenu /10 | Confirmé 2 documents | Ratio indicatif séparé | Cellules sans BPA retenu |",
        "|---|---:|---:|---:|---:|",
    ]
    for ticker in TICKERS:
        item = summary["par_societe"][ticker]
        lines.append(
            f"| {ticker} | {item['bpa_publie_fcfa_retenu']} | {item['confirmes_deux_documents']} | {item['ratios_indicatifs_separes']} | {10 - item['bpa_publie_fcfa_retenu']} |"
        )
    for ticker in TICKERS:
        lines += ["", f"### {ticker} — {companies[ticker]['nom']}", ""]
        for finding in COMPANY_FINDINGS[ticker]:
            lines.append(f"- {finding}")
        retained_rows = [
            row for row in rows if row["ticker"] == ticker and row.get("bpa_retenu")
        ]
        if retained_rows:
            values = ", ".join(
                f"{row['exercice']} : {fmt_number(row['bpa_retenu']['valeur'])} FCFA"
                for row in retained_rows
            )
            lines.append(f"- **BPA retenus :** {values}.")
        else:
            lines.append("- **BPA retenus : aucun.**")
    lines += [
        "",
        "## Défauts prouvés à corriger avant la collecte complète",
        "",
        "| Priorité | Chantier | Correctif exigé |",
        "|---|---|---|",
    ]
    for priority, title, action in BLOCKERS:
        lines.append(f"| {priority} | {title} | {action} |")
    lines += [
        "",
        "## Matrice fermée des 50 cellules",
        "",
        "La colonne « preuve principale » renvoie au premier document cité ; la validation complète, les intrants et le verdict sur l'extracteur sont dans `decisions.json`, `pilot_matrix.csv` et `pilot_matrix.json`.",
        "",
        "| Société | Exercice | Statut BPA | BPA retenu (FCFA) | Ratio indicatif séparé | Preuve principale |",
        "|---|---:|---|---:|---:|---|",
    ]
    for row in rows:
        retained = row.get("bpa_retenu") or {}
        ratio = row.get("ratio_indicatif_fin_exercice") or {}
        source = (row.get("sources") or [{}])[0]
        lines.append(
            f"| {row['ticker']} | {row['exercice']} | {row['statut_bpa']} | {fmt_number(retained.get('valeur'))} | {fmt_number(ratio.get('valeur_fcfa'))} | {source.get('document', '—')} (p. {source.get('pages', '—')}) |"
        )
    lines += [
        "",
        "## Détail des validations indépendantes",
        "",
    ]
    for ticker in TICKERS:
        lines += [f"### {ticker}", ""]
        for row in [item for item in rows if item["ticker"] == ticker]:
            lines.append(
                f"- **{row['exercice']} — {row['statut_bpa']}**. {row['validation']} "
                f"_Extracteur actuel : {row['extracteur'].get('resultat')} Verdict : {row['extracteur'].get('verdict')}._"
            )
        lines.append("")
    lines += [
        "## Événements de capital utilisés uniquement comme drapeaux",
        "",
        "- CIE : fractionnement de vingt actions nouvelles pour une ancienne le 19 octobre 2017 — page officielle BRVM : https://www.brvm.org/fr/fractionnement-dactions-cie-ci",
        "- BOA Côte d’Ivoire : fractionnement de dix pour une en octobre 2017 — https://www.brvm.org/fr/fractionnement-dactions-bank-africa-cote-divoire ; convocation officielle à l'AGE du 10 octobre 2024 — https://www.brvm.org/sites/default/files/20240927_-_avis_de_convocation_-_assemblee_generale_extraordinaire_-_boa_ci.pdf ; jouissance des actions gratuites au 1er janvier 2024 annoncée par BOA — https://boacoteivoire.com/2024/08/26/augmentation-du-capital-des-filiales-cotees-a-la-brvm-et-de-boa-togo/",
        "",
        "## Artefacts et reproductibilité",
        "",
        "- `inventory.json` : inventaire profond des pages BRVM (485 documents).",
        "- `extractions.json` : sorties brutes de l'extracteur, OCR contrôlé et notes sur les 73 sources ouvertes.",
        "- `raw_second_reader.txt` et `raw_second_reader_supplements.txt` : lignes BPA/actions relues par un second lecteur.",
        "- `boac_ocr_pages_25_plus_lines.txt` : OCR ciblé au-delà de la limite de 24 pages pour BOAC 2022 et 2025.",
        "- `decisions.json` : décisions manuelles fermées, source de vérité du pilote.",
        "- `pilot_matrix.csv`, `pilot_matrix.json`, `summary.json`, `sources_examinees.csv` : artefacts régénérés par `python3 -B ingestion/audit_pilot_bpa_5.py`.",
        "",
        "**Conclusion :** le pilote valide la méthode d'audit cellule par cellule, mais invalide le lancement immédiat d'une collecte BPA complète. Les 18 BPA retenus constituent un banc de contrôle ; les 32 autres cellules montrent précisément pourquoi un champ BPA unique, sans devise, composante, périmètre, vintage et registre de capital, créerait de fausses séries.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    decisions = load_json(DECISIONS_PATH)
    inventory = load_json(INVENTORY_PATH)
    extractions = load_json(EXTRACTIONS_PATH)
    rows = validate(decisions)
    summary = build_summary(rows, inventory, extractions)

    companies = decisions["metadata"]["societes"]
    enriched = [
        {**row, "societe": companies[row["ticker"]]["nom"]}
        for row in sorted(
            rows, key=lambda item: (TICKERS.index(item["ticker"]), item["exercice"])
        )
    ]
    (AUDIT_DIR / "pilot_matrix.json").write_text(
        json.dumps(
            {"metadata": decisions["metadata"], "summary": summary, "rows": enriched},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (AUDIT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    flat = [flatten_row(row, companies[row["ticker"]]) for row in enriched]
    with (AUDIT_DIR / "pilot_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0].keys()))
        writer.writeheader()
        writer.writerows(flat)

    write_sources(extractions)
    (AUDIT_DIR / "README.md").write_text(
        render_readme(decisions, enriched, summary), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

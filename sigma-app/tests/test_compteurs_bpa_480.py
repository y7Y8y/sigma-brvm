import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))

import compteurs_bpa_480 as moteur  # noqa: E402

COLONNES = [
    "ticker",
    "exercice",
    "applicabilite",
    "statut_documentaire",
    "statut_bpa",
    "validation_level",
    "bpa_publie_fcfa",
    "bpa_recalcule_comparable_fcfa",
    "serie_extraite",
    "documents_primaires_lus_couvrant_exercice",
]


def cellule(ticker, exercice, statut_bpa="NON_PUBLIE_DANS_SOURCES_VERIFIEES", **extra):
    """Cellule de travail pour les tests. Aucune de ces valeurs n'est un fait réel."""
    ligne = {
        "ticker": ticker,
        "exercice": str(exercice),
        "applicabilite": "APPLICABLE",
        "statut_documentaire": "DOCUMENTS_PRIMAIRES_EXAMINES",
        "statut_bpa": statut_bpa,
        "validation_level": "AUCUNE_VALEUR_RETENUE",
        "bpa_publie_fcfa": "",
        "bpa_recalcule_comparable_fcfa": "",
        "serie_extraite": "True",
        "documents_primaires_lus_couvrant_exercice": "2",
    }
    ligne.update({k: str(v) for k, v in extra.items()})
    return ligne


class MoteurCompteursTests(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)

    def tearDown(self):
        self.dossier.cleanup()

    def ecrire(self, lignes, decisions=None, totaux=None):
        matrice = self.racine / "matrix.csv"
        with matrice.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLONNES)
            writer.writeheader()
            for ligne in lignes:
                writer.writerow({c: ligne.get(c, "") for c in COLONNES})
        overlay = self.racine / "overlay.json"
        overlay.write_text(
            json.dumps(
                {
                    "date": "2026-10-26",
                    "parser_version": "test",
                    "counting_base": {"official_base": "APPLICABLE", "decision": "test"},
                    "expected_totals": totaux
                    or {
                        "cellules_brutes": len(lignes),
                        "cellules_applicables": sum(
                            1 for l in lignes if l["applicabilite"] == "APPLICABLE"
                        ),
                        "non_applicables": sum(
                            1 for l in lignes if l["applicabilite"] != "APPLICABLE"
                        ),
                    },
                    "cell_decisions": decisions or [],
                }
            ),
            encoding="utf-8",
        )
        return matrice, overlay

    def test_valeur_publiee_hors_perimetre_non_comptee_mais_conservee(self):
        lignes = [
            cellule("AAA", 2017),
            cellule(
                "AAA",
                2018,
                statut_bpa="PUBLIE_EXTRAIT",
                validation_level="EXTRACTION_UNIQUE_SANS_CONTROLE_PONDERE",
                bpa_publie_fcfa=115.0,
                applicabilite="NON_APPLICABLE_AVANT_INTRODUCTION",
            ),
            cellule("BBB", 2017, statut_bpa="PUBLIE_EXTRAIT", bpa_publie_fcfa=42.0),
        ]
        matrice, overlay = self.ecrire(lignes)
        rapport = moteur.construire_rapport(matrice, overlay)

        brut = rapport["compteurs"][moteur.BASE_RAW]
        app = rapport["compteurs"][moteur.BASE_APPLICABLE]
        self.assertEqual(brut["bpa_publies_transcrits_hors_perimetre_inclus"], 2)
        self.assertEqual(app["bpa_publies_retenus_dans_la_couverture"], 1)
        self.assertEqual(len(brut["publications_hors_perimetre_non_comptees"]), 1)
        self.assertEqual(
            brut["publications_hors_perimetre_non_comptees"][0]["valeur_conservee_fcfa"], "115.0"
        )

    def test_overlay_modifie_un_statut_et_conserve_les_sommes(self):
        lignes = [cellule("CCC", 2022), cellule("CCC", 2023)]
        decisions = [
            {
                "ticker": "CCC",
                "exercice": 2022,
                "audit_decision": "CORRECTION_MANUELLE",
                "guard_status_bpa_matrix": "NON_PUBLIE_DANS_SOURCES_VERIFIEES",
                "applied_status_bpa": "PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE",
                "applied_validation_level": "PUBLICATION_DETECTEE_NON_RETENUE",
                "source": "test",
            }
        ]
        matrice, overlay = self.ecrire(lignes, decisions)
        rapport = moteur.construire_rapport(matrice, overlay)

        app = rapport["compteurs"][moteur.BASE_APPLICABLE]
        self.assertEqual(app["publications_detectees_non_retenues"], 1)
        self.assertEqual(app["statuts_bpa"]["NON_PUBLIE_DANS_SOURCES_VERIFIEES"], 1)
        effets = [j for j in rapport["journal_overlay"] if j["effet"] == "modifie"]
        self.assertEqual(len(effets), 1)

    def test_decision_perimee_bloque_le_calcul(self):
        lignes = [cellule("DDD", 2020)]
        decisions = [
            {
                "ticker": "DDD",
                "exercice": 2020,
                "guard_status_bpa_matrix": "ILLISIBLE",
                "applied_status_bpa": "PUBLIE_NON_RETENU_DEVISE_COMPOSANTE_OU_PERIMETRE",
            }
        ]
        matrice, overlay = self.ecrire(lignes, decisions)
        with self.assertRaises(moteur.ControleEchoue) as contexte:
            moteur.construire_rapport(matrice, overlay)
        self.assertIn("périmée", str(contexte.exception))

    def test_valeur_publiee_sans_montant_est_un_echec(self):
        lignes = [cellule("EEE", 2021, statut_bpa="PUBLIE_EXTRAIT", bpa_publie_fcfa="")]
        matrice, overlay = self.ecrire(lignes)
        with self.assertRaises(moteur.ControleEchoue):
            moteur.construire_rapport(matrice, overlay)

    def test_bpa_recalcule_sans_preuve_est_un_echec(self):
        lignes = [cellule("FFF", 2021, bpa_recalcule_comparable_fcfa=99.0)]
        matrice, overlay = self.ecrire(lignes)
        with self.assertRaises(moteur.ControleEchoue):
            moteur.construire_rapport(matrice, overlay)

    def test_statut_inconnu_casse_la_somme_des_niveaux(self):
        lignes = [cellule("GGG", 2021, statut_bpa="STATUT_INVENTE")]
        matrice, overlay = self.ecrire(lignes)
        with self.assertRaises(moteur.ControleEchoue):
            moteur.construire_rapport(matrice, overlay)


class MoteurSurMatriceReelleTests(unittest.TestCase):
    """Vérifie le résultat sur la matrice v2.1.4 livrée, si elle est présente."""

    def test_compteurs_de_reference(self):
        if not moteur.DEFAULT_MATRIX.exists():
            self.skipTest("matrice v2.1.4 absente")
        rapport = moteur.construire_rapport(moteur.DEFAULT_MATRIX, moteur.DEFAULT_OVERLAY)

        app = rapport["compteurs"][moteur.BASE_APPLICABLE]
        brut = rapport["compteurs"][moteur.BASE_RAW]
        self.assertEqual(app["cellules"], 442)
        self.assertEqual(brut["cellules"], 480)
        self.assertEqual(app["bpa_publies_retenus_dans_la_couverture"], 31)
        self.assertEqual(app["dont_exclus_de_la_comparabilite_formelle"], 2)
        self.assertEqual(app["dont_non_exclus_par_decision"], 29)
        self.assertEqual(app["bpa_recalcules_comparables"], 0)
        self.assertEqual(app["ratios_indicatifs_fin_exercice_separes"], 8)
        self.assertEqual(brut["publications_detectees_non_retenues"], 34)
        self.assertEqual(brut["statuts_bpa"]["NON_PUBLIE_DANS_SOURCES_VERIFIEES"], 263)
        self.assertEqual(brut["statuts_bpa"]["ILLISIBLE"], 72)
        self.assertEqual(len(brut["publications_hors_perimetre_non_comptees"]), 1)
        self.assertEqual(
            brut["publications_hors_perimetre_non_comptees"][0]["ticker"], "ORGT"
        )
        self.assertEqual(rapport["dataset_published_modified"], False)
        self.assertTrue(all(c["resultat"] == "OK" for c in rapport["controles"]))


if __name__ == "__main__":
    unittest.main()

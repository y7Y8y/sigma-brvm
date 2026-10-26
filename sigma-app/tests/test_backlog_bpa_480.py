import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))

import backlog_bpa_480 as backlog  # noqa: E402

COLONNES = [
    "ticker",
    "company_name",
    "sector",
    "exercice",
    "applicabilite",
    "statut_documentaire",
    "statut_bpa",
    "validation_level",
    "bpa_publie_fcfa",
    "bpa_recalcule_comparable_fcfa",
    "documents_candidats_inventories_count",
    "documents_primaires_lus_couvrant_exercice",
    "serie_extraite",
]


def cellule(ticker, exercice, statut_bpa, candidats=2, applicabilite="APPLICABLE", secteur="Industriels"):
    return {
        "ticker": ticker,
        "company_name": f"SOCIETE {ticker}",
        "sector": secteur,
        "exercice": str(exercice),
        "applicabilite": applicabilite,
        "statut_documentaire": "DOCUMENTS_PRIMAIRES_EXAMINES",
        "statut_bpa": statut_bpa,
        "validation_level": "AUCUNE_VALEUR_RETENUE",
        "bpa_publie_fcfa": "",
        "bpa_recalcule_comparable_fcfa": "",
        "documents_candidats_inventories_count": str(candidats),
        "documents_primaires_lus_couvrant_exercice": "",
        "serie_extraite": "True",
    }


class BacklogTests(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self.dossier.name)

    def tearDown(self):
        self.dossier.cleanup()

    def ecrire(self, lignes, decisions=None):
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
                    "cell_decisions": decisions or [],
                }
            ),
            encoding="utf-8",
        )
        return matrice, overlay

    def test_seules_les_cellules_applicables_entrent_dans_la_file(self):
        lignes = [
            cellule("AAA", 2024, "ILLISIBLE"),
            cellule("AAA", 2018, "ILLISIBLE", applicabilite="NON_APPLICABLE_AVANT_INTRODUCTION"),
            cellule("BBB", 2024, "PUBLIE_EXTRAIT"),
        ]
        matrice, overlay = self.ecrire(lignes)
        rapport = backlog.construire_rapport(matrice, overlay)
        tickers = {l["ticker"] for l in rapport["lignes"]}
        self.assertEqual(tickers, {"AAA"})
        self.assertEqual(rapport["perimetre"]["cellules_a_traiter"], 1)
        self.assertEqual(rapport["perimetre"]["cellules_hors_file"], 1)

    def test_priorite_non_recherche_avant_ocr(self):
        lignes = [
            cellule("AAA", 2024, "ILLISIBLE", candidats=5),
            cellule("BBB", 2024, "NON_RECHERCHE", candidats=1),
            cellule("CCC", 2024, "DOCUMENT_INTROUVABLE", candidats=0),
            cellule("DDD", 2024, "NON_PUBLIE_DANS_SOURCES_VERIFIEES"),
        ]
        matrice, overlay = self.ecrire(lignes)
        rapport = backlog.construire_rapport(matrice, overlay)
        ordre = [l["cause"] for l in rapport["lignes"]]
        self.assertEqual(
            ordre,
            [
                "C_NON_RECHERCHE",
                "B_OCR_SCAN",
                "D_DOCUMENT_INTROUVABLE",
                "E_ABSENCE_A_TESTER",
            ],
        )

    def test_utilite_valorisation_par_exercice(self):
        self.assertEqual(backlog.utilite_valorisation(2025), "HAUTE")
        self.assertEqual(backlog.utilite_valorisation(2022), "MOYENNE")
        self.assertEqual(backlog.utilite_valorisation(2017), "FAIBLE")

    def test_echantillon_reproductible_et_stable(self):
        lignes = [
            cellule(f"SOC{i:02d}", 2016 + i % 10, "NON_PUBLIE_DANS_SOURCES_VERIFIEES")
            for i in range(40)
        ]
        matrice, overlay = self.ecrire(lignes)
        premier = backlog.construire_rapport(matrice, overlay, taille_echantillon=8, seed="A")
        second = backlog.construire_rapport(matrice, overlay, taille_echantillon=8, seed="A")
        self.assertEqual(
            [c["ticker"] for c in premier["echantillon"]["cellules"]],
            [c["ticker"] for c in second["echantillon"]["cellules"]],
        )
        self.assertEqual(premier["echantillon"]["taille"], 8)
        self.assertEqual(premier["echantillon"]["population"], 40)
        self.assertTrue(all(
            c["cause"] == "E_ABSENCE_A_TESTER" for c in premier["echantillon"]["cellules"]
        ))

    def test_echantillon_change_avec_la_graine(self):
        lignes = [
            cellule(f"SOC{i:02d}", 2016 + i % 10, "NON_PUBLIE_DANS_SOURCES_VERIFIEES")
            for i in range(40)
        ]
        matrice, overlay = self.ecrire(lignes)
        a = backlog.construire_rapport(matrice, overlay, taille_echantillon=8, seed="A")
        b = backlog.construire_rapport(matrice, overlay, taille_echantillon=8, seed="B")
        self.assertNotEqual(
            [c["ticker"] for c in a["echantillon"]["cellules"]],
            [c["ticker"] for c in b["echantillon"]["cellules"]],
        )

    def test_echantillon_plus_grand_que_la_population_prend_tout(self):
        lignes = [cellule("AAA", 2024, "NON_PUBLIE_DANS_SOURCES_VERIFIEES")]
        matrice, overlay = self.ecrire(lignes)
        rapport = backlog.construire_rapport(matrice, overlay, taille_echantillon=10)
        self.assertEqual(rapport["echantillon"]["taille"], 1)


class BacklogSurMatriceReelleTests(unittest.TestCase):
    def test_backlog_de_reference(self):
        if not backlog.DEFAULT_MATRIX.exists():
            self.skipTest("matrice v2.1.4 absente")
        rapport = backlog.construire_rapport(
            backlog.DEFAULT_MATRIX, backlog.DEFAULT_OVERLAY, taille_echantillon=24
        )
        par_cause = {g["cause"]: g["cellules"] for g in rapport["groupes"]}
        self.assertEqual(par_cause["C_NON_RECHERCHE"], 18)
        self.assertEqual(par_cause["B_OCR_SCAN"], 72)
        self.assertEqual(par_cause["D_DOCUMENT_INTROUVABLE"], 15)
        self.assertEqual(par_cause["A_PUBLICATION_NON_RETENUE"], 34)
        self.assertEqual(par_cause["E_ABSENCE_A_TESTER"], 263)
        self.assertEqual(rapport["perimetre"]["cellules_applicables"], 442)
        self.assertEqual(rapport["perimetre"]["cellules_a_traiter"], 402)
        self.assertEqual(rapport["echantillon"]["taille"], 24)
        # l'échantillon doit rester proche de la population, sans quoi il ne prouve rien
        pop = rapport["echantillon"]["representativite"]["utilite_population"]
        ech = rapport["echantillon"]["representativite"]["utilite_echantillon"]
        part_pop_haute = pop["HAUTE"] / sum(pop.values())
        part_ech_haute = ech["HAUTE"] / sum(ech.values())
        self.assertLess(abs(part_pop_haute - part_ech_haute), 0.20)


if __name__ == "__main__":
    unittest.main()

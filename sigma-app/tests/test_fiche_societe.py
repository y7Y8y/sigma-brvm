import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))

import fiche_societe as fiche  # noqa: E402


def jeu_de_donnees(dividendes=None, prix=10000.0, mediane=50_000_000.0, figures=None):
    return {
        "generated_at": "2026-10-22T21:20:37+00:00",
        "macro_context": {
            "bceao_cpm": {
                "policy_rate_pct": 3.0,
                "published_date": "2026-09-09",
                "source_label": "BCEAO — CPM",
            }
        },
        "companies": [
            {
                "ticker": "TEST",
                "name": "SOCIETE TEST",
                "sector": "Industriels",
                "latest_boc_date": "2026-10-21",
                "latest_boc": {
                    "close": prix,
                    "per": 12.5,
                    "net_dividend_yield_pct": 5.0,
                    "last_net_dividend_fcfa": 500.0,
                },
                "history_stats": {
                    "traded_sessions_last_20": 20,
                    "median_traded_value_last_20_fcfa": mediane,
                },
                "dividend_history": dividendes
                or {
                    "status": "documentee_5_exercices",
                    "annual": [
                        {"fiscal_year": 2021, "net_amount_fcfa": 400.0},
                        {"fiscal_year": 2022, "net_amount_fcfa": 420.0},
                        {"fiscal_year": 2023, "net_amount_fcfa": 441.0},
                        {"fiscal_year": 2024, "net_amount_fcfa": 463.0},
                        {"fiscal_year": 2025, "net_amount_fcfa": 486.0},
                    ],
                },
                "fundamentals": {"figures": figures or {}},
            }
        ],
    }


class TauxTests(unittest.TestCase):
    def test_taux_visible_et_sensibilite(self):
        taux = fiche.taux_actualisation(jeu_de_donnees()["macro_context"], prime_points=8.0)
        self.assertTrue(taux["calculable"])
        self.assertEqual(taux["taux_requis_pct"], 11.0)
        self.assertEqual(taux["sensibilite"], [10.0, 11.0, 12.0])

    def test_taux_absent_refuse_le_calcul(self):
        taux = fiche.taux_actualisation({}, prime_points=8.0)
        self.assertFalse(taux["calculable"])
        self.assertIn("absent", taux["raison"])


class ScenarioTests(unittest.TestCase):
    def test_les_bornes_necrasent_pas_la_distribution(self):
        # Série à croissance forte : le plafond doit s'appliquer au scénario, pas
        # avant le calcul du minimum/médiane/maximum, sinon central = optimiste.
        serie = [(2021, 100.0), (2022, 120.0), (2023, 150.0), (2024, 200.0), (2025, 260.0)]
        brutes = fiche.croissances_observees(serie)
        self.assertAlmostEqual(brutes[0], 20.0)
        self.assertAlmostEqual(brutes[-1], 30.0)
        self.assertGreater(max(brutes), fiche.CROISSANCE_PLAFOND)

        data = jeu_de_donnees(
            dividendes={
                "status": "documentee",
                "annual": [{"fiscal_year": a, "net_amount_fcfa": m} for a, m in serie],
            }
        )
        taux = fiche.taux_actualisation(data["macro_context"])
        ancre = fiche.ancre_dividende(data["companies"][0]["dividend_history"], taux, 10000.0)
        self.assertTrue(ancre["calculable"])
        # Société en forte croissance : tout est au-dessus du plafond.
        self.assertEqual(ancre["scenarios_croissance_pct"]["optimiste"], fiche.CROISSANCE_PLAFOND)
        self.assertEqual(ancre["scenarios_croissance_pct"]["central"], fiche.CROISSANCE_PLAFOND)
        # Le pessimiste reste pessimiste : au mieux une stagnation, jamais une hausse.
        self.assertEqual(ancre["scenarios_croissance_pct"]["pessimiste"], 0.0)
        self.assertTrue(ancre["borne_atteinte"]["optimiste"])
        # Le resserrement est signalé, pas masqué.
        self.assertTrue(ancre["scenarios_confondus"])
        self.assertIn("sous-estime", ancre["note_scenarios"])

    def test_gordon_refuse_si_croissance_trop_proche_du_taux(self):
        self.assertIsNone(fiche.valeur_gordon(100.0, 10.8, 11.0))
        self.assertIsNotNone(fiche.valeur_gordon(100.0, 5.0, 11.0))

    def test_serie_trop_courte_refusee(self):
        ancre = fiche.ancre_dividende(
            {"annual": [{"fiscal_year": 2024, "net_amount_fcfa": 100.0}]},
            {"calculable": True, "taux_requis_pct": 11.0},
            1000.0,
        )
        self.assertFalse(ancre["calculable"])
        self.assertIn("trop courte", ancre["raison"])

    def test_annees_discontinues_ignorees(self):
        serie = [(2020, 100.0), (2022, 120.0)]  # trou d'un an
        self.assertEqual(fiche.croissances_observees(serie), [])


class CoherenceDividendeTests(unittest.TestCase):
    def test_dividende_et_rendement_concordants(self):
        # 1740 / 41745 = 4.17 % : cohérent.
        controle = fiche.controle_coherence_dividende(41745.0, 1740.0, 4.17)
        self.assertTrue(controle["verifiable"])
        self.assertTrue(controle["coherent"])

    def test_unite_incoherente_detectee(self):
        # Cas réel ETIT : 92 annoncé pour un rendement de 1,46 % sur un cours de 63.
        controle = fiche.controle_coherence_dividende(63.0, 92.0, 1.46)
        self.assertTrue(controle["verifiable"])
        self.assertFalse(controle["coherent"])
        self.assertGreater(controle["ecart_pct"], 1000)

    def test_incoherence_bloque_l_ancre(self):
        data = jeu_de_donnees()
        company = data["companies"][0]
        company["latest_boc"]["last_net_dividend_fcfa"] = 92.0
        company["latest_boc"]["close"] = 63.0
        company["latest_boc"]["net_dividend_yield_pct"] = 1.46
        resultat = fiche.construire_fiche(data, "TEST")
        self.assertFalse(resultat["ancres"]["dividende"]["calculable"])
        self.assertIn("incohérents", resultat["ancres"]["dividende"]["raison"])


class TestSortieTests(unittest.TestCase):
    def test_ordre_gros_par_rapport_au_marche(self):
        resultat = fiche.test_sortie(prix=10000.0, quantite=30, mediane_fcfa=1_000_000.0)
        self.assertTrue(resultat["calculable"])
        self.assertAlmostEqual(resultat["part_dune_seance_mediane_pct"], 30.0)
        self.assertAlmostEqual(resultat["seances_pour_sortir"], 0.3)

    def test_liquidite_absente_refusee(self):
        resultat = fiche.test_sortie(prix=10000.0, quantite=30, mediane_fcfa=None)
        self.assertFalse(resultat["calculable"])


class VerdictTests(unittest.TestCase):
    def test_une_seule_ancre_ne_prononce_aucun_verdict(self):
        v = fiche.verdict({"dividende": {"calculable": True}, "benefice": {"calculable": False}})
        self.assertEqual(v["code"], "NON_CALCULABLE")
        self.assertEqual(v["ancres_disponibles"], ["dividende"])
        self.assertIn("une seule ancre", v["raison"])

    def test_aucune_ancre(self):
        v = fiche.verdict({"dividende": {"calculable": False}})
        self.assertIn("aucune ancre", v["raison"])


class FicheCompleteTests(unittest.TestCase):
    def test_fiche_ne_fabrique_aucune_valeur_absente(self):
        data = jeu_de_donnees()
        resultat = fiche.construire_fiche(data, "TEST", quantite=10)
        self.assertIn("BPA vérifié : absent", " ".join(resultat["trous"]))
        self.assertIn("Nombre d'actions vérifié", " ".join(resultat["trous"]))
        self.assertEqual(resultat["verdict"]["code"], "NON_CALCULABLE")
        # Le PER est bien attribué à la BRVM, jamais présenté comme un calcul SIGMA.
        self.assertIn("pas un calcul SIGMA", resultat["marche"]["per_source"])

    def test_rendu_markdown_contient_les_sections_clefs(self):
        data = jeu_de_donnees()
        texte = fiche.rendre_markdown(fiche.construire_fiche(data, "TEST", quantite=10))
        for titre in (
            "Ce que le prix implique",
            "Liquidité",
            "Ancre dividende",
            "Verdict",
            "Ce qui invaliderait la thèse",
            "Ce que SIGMA ne sait pas",
        ):
            self.assertIn(titre, texte)
        self.assertIn("ni d'acheter ni de vendre", texte)

    def test_fiche_reelle_si_data_present(self):
        if not fiche.DATA.exists():
            self.skipTest("data.json absent")
        data = fiche.charger()
        resultat = fiche.construire_fiche(data, "SNTS", quantite=25)
        self.assertEqual(resultat["ticker"], "SNTS")
        self.assertTrue(resultat["ancres"]["dividende"]["calculable"])
        self.assertEqual(resultat["verdict"]["code"], "NON_CALCULABLE")
        # Le prix est dans la fourchette ou non, mais la fiche doit toujours dire où il se situe.
        self.assertIn("position_du_prix", resultat["ancres"]["dividende"])


if __name__ == "__main__":
    unittest.main()

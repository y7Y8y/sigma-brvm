import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))

import trajectoire as traj  # noqa: E402


def archive_factice(closes, pers=None, ticker="TEST", composite=None):
    """Archive minimale : une séance par date, un seul ticker."""
    dates = [f"2026-01-{jour:02d}" for jour in range(1, len(closes) + 1)]
    pers = pers or [None] * len(closes)
    composite = composite or [100 + i for i in range(len(closes))]
    sessions = []
    for i, date in enumerate(dates):
        ligne = [closes[i], 0.0, 100, 1000, closes[i], closes[i], closes[i], 0.0, 100.0, "x", 5.0, pers[i]]
        sessions.append(
            {
                "date": date,
                "composite_level": composite[i],
                "rows": {ticker: ligne},
            }
        )
    return {
        "row_fields": [
            "close", "variation_pct", "volume", "traded_value_fcfa", "previous_close",
            "open", "reference_price", "variation_previous_year_pct",
            "last_net_dividend_fcfa", "last_dividend_date_label", "net_dividend_yield_pct", "per",
        ],
        "sessions": sessions,
    }


class ExtractionTests(unittest.TestCase):
    def test_series_lues_dans_l_ordre(self):
        archive = archive_factice([100, 101, 102])
        series = traj.extraire_series(archive)
        self.assertEqual(series["TEST"].closes, [100, 101, 102])
        self.assertEqual(len(series["TEST"].dates), 3)

    def test_cours_absent_ignore(self):
        archive = archive_factice([100, 0, 102])
        self.assertEqual(traj.extraire_series(archive)["TEST"].closes, [100, 102])


class SansLookAheadTests(unittest.TestCase):
    def test_tronquer_l_archive_ne_change_pas_une_decision_passee(self):
        # Série qui déclenche un stop : 100 → 130 → 110.
        closes = [100, 110, 130, 110, 105, 150, 160]
        complet = traj.extraire_series(archive_factice(closes))["TEST"]
        tronque = traj.extraire_series(archive_factice(closes[:4]))["TEST"]

        decision_complete = traj.simuler(complet, "2026-01-01", "STOP_12")
        decision_tronquee = traj.simuler(tronque, "2026-01-01", "STOP_12")
        self.assertTrue(decision_complete["disponible"])
        self.assertTrue(decision_tronquee["disponible"])
        self.assertEqual(decision_complete["date_sortie"], decision_tronquee["date_sortie"])
        self.assertEqual(decision_complete["prix_sortie"], decision_tronquee["prix_sortie"])

    def test_la_regle_ne_regarde_jamais_apres_la_date_de_decision(self):
        # Une chute brutale APRÈS la sortie ne doit pas changer le motif de sortie.
        sans_chute = [100, 105, 140, 120]
        avec_chute = [100, 105, 140, 120, 40, 30]
        a = traj.simuler(traj.extraire_series(archive_factice(sans_chute))["TEST"], "2026-01-01", "STOP_12")
        b = traj.simuler(traj.extraire_series(archive_factice(avec_chute))["TEST"], "2026-01-01", "STOP_12")
        self.assertEqual(a["date_sortie"], b["date_sortie"])
        self.assertEqual(a["performance_pct"], b["performance_pct"])


class ReglesTests(unittest.TestCase):
    def test_hold_ne_sort_jamais(self):
        serie = traj.extraire_series(archive_factice([100, 200, 300]))["TEST"]
        resultat = traj.simuler(serie, "2026-01-01", "HOLD")
        self.assertEqual(resultat["date_sortie"], serie.dates[-1])
        self.assertIn("aucune sortie", resultat["motif_sortie"])

    def test_stop_declenche_au_bon_seuil(self):
        serie = traj.extraire_series(archive_factice([100, 200, 175]))["TEST"]
        resultat = traj.simuler(serie, "2026-01-01", "STOP_12")
        self.assertEqual(resultat["date_sortie"], "2026-01-03")
        self.assertIn("repli", resultat["motif_sortie"])

    def test_per_propre_exige_un_historique_suffisant(self):
        # Moins de 20 PER passés : la règle refuse de se prononcer.
        pers = [8.0] * 5 + [30.0]
        serie = traj.extraire_series(archive_factice([100, 100, 100, 100, 100, 100], pers=pers))["TEST"]
        resultat = traj.simuler(serie, "2026-01-01", "PER_PROPRE")
        self.assertEqual(resultat["date_sortie"], serie.dates[-1])

    def test_per_propre_declenche_sur_son_propre_historique(self):
        pers = [8.0] * 25 + [15.0]
        closes = [100] * 25 + [150]
        serie = traj.extraire_series(archive_factice(closes, pers=pers))["TEST"]
        resultat = traj.simuler(serie, "2026-01-01", "PER_PROPRE")
        self.assertEqual(resultat["date_sortie"], "2026-01-26")
        self.assertIn("médiane propre", resultat["motif_sortie"])

    def test_parametres_publies_avec_le_resultat(self):
        archive = archive_factice([100, 110])
        etude = traj.etude_complete(archive, "TEST", "2026-01-01")
        for nom, resultat in etude["resultats"].items():
            self.assertIn("parametres", resultat, f"{nom} doit publier ses paramètres")
            self.assertTrue(resultat["prix_seuls"])

    def test_date_achat_hors_archive(self):
        serie = traj.extraire_series(archive_factice([100, 110]))["TEST"]
        resultat = traj.simuler(serie, "2026-06-01", "HOLD")
        self.assertFalse(resultat["disponible"])


class EtudeCompleteTests(unittest.TestCase):
    def test_comparaison_indice(self):
        archive = archive_factice([100, 110, 120], composite=[100, 105, 115])
        etude = traj.etude_complete(archive, "TEST", "2026-01-01")
        self.assertEqual(etude["resultats"]["HOLD"]["performance_pct"], 20.0)
        self.assertEqual(etude["indice_reference"]["performance_sur_meme_fenetre_pct"], 15.0)
        self.assertEqual(etude["surplus_vs_indice_pct"], 5.0)

    def test_limites_toujours_publiees(self):
        archive = archive_factice([100, 110])
        etude = traj.etude_complete(archive, "TEST", "2026-01-01")
        texte = " ".join(etude["limites"])
        self.assertIn("dividendes", texte)
        self.assertIn("prédire", texte)


class ArchiveReelleTests(unittest.TestCase):
    def test_cas_de_reference_snts(self):
        if not traj.ARCHIVE.exists():
            self.skipTest("archive absente")
        archive = traj.charger_archive()
        etude = traj.etude_complete(archive, "SNTS", "2026-01-02")
        self.assertTrue(etude["disponible"])
        self.assertEqual(etude["resultats"]["HOLD"]["date_achat"], "2026-01-02")
        self.assertGreater(etude["resultats"]["HOLD"]["performance_pct"], 0)
        # La règle de valorisation coupe la position avant la fin : c'est le fait
        # central que ce module existe pour montrer.
        self.assertLess(
            etude["resultats"]["PER_PROPRE"]["seances_detenues"],
            etude["resultats"]["HOLD"]["seances_detenues"],
        )


if __name__ == "__main__":
    unittest.main()

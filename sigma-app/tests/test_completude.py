import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))

import couverture_donnees as couv  # noqa: E402
import registre_actions as reg  # noqa: E402


def company(ticker, figures=None, per=12.0, close=10000.0, dividendes=True, couverture="non_calculable"):
    return {
        "ticker": ticker,
        "name": f"SOCIETE {ticker}",
        "latest_boc": {"close": close, "per": per},
        "latest_boc_date": "2026-10-21",
        "fundamentals": {"figures": figures or {}},
        "dividend_history": {"annual": [{"fiscal_year": 2025, "net_amount_fcfa": 100.0}]} if dividendes else {},
        "dividend_sustainability": {"status": couverture},
    }


def figure(valeur):
    return {"value": valeur, "value_fcfa": valeur, "confidence": "extraction_unique"}


def registre(entrees):
    return {"entrees": entrees}


def entree(ticker, exercice=2025, actions=1_000_000, niveau=reg.NIVEAU_LU, **extra):
    base = {
        "ticker": ticker,
        "exercice": exercice,
        "actions": actions,
        "niveau": niveau,
        "preuve": {"document": "Etats financiers 2025", "page": 3, "ligne": "Nombre d'actions 1 000 000"},
    }
    base.update(extra)
    return base


class ValidationTests(unittest.TestCase):
    def test_entree_valide(self):
        self.assertEqual(reg.valider_entree(entree("AAA")), [])

    def test_valeur_sans_document_refusee(self):
        e = entree("AAA")
        e["preuve"] = {"page": 3, "ligne": "x"}
        self.assertIn("preuve.document manquant : une valeur sans document n'entre pas", reg.valider_entree(e))

    def test_confirme_exige_deux_documents(self):
        e = entree("AAA", niveau=reg.NIVEAU_CONFIRME)
        erreurs = reg.valider_entree(e)
        self.assertTrue(any("deux documents distincts" in x for x in erreurs))

    def test_entier_positif_obligatoire(self):
        self.assertTrue(reg.valider_entree(entree("AAA", actions=0)))
        self.assertTrue(reg.valider_entree(entree("AAA", actions="56 000 000")))

    def test_exercice_hors_perimetre(self):
        self.assertTrue(reg.valider_entree(entree("AAA", exercice=2010)))

    def test_entree_derivee_sans_evenement_refusee(self):
        e = entree("AAA", derive=True)
        self.assertTrue(any("evenement_source" in x for x in reg.valider_entree(e)))


class RegistreTests(unittest.TestCase):
    def test_une_entree_invalide_n_alimente_aucun_calcul(self):
        r = registre([entree("AAA"), entree("BBB", actions=-5)])
        utiles = reg.actions_utilisables(r)
        self.assertIn(("AAA", 2025), utiles)
        self.assertNotIn(("BBB", 2025), utiles)

    def test_candidat_exclu_des_calculs(self):
        r = registre([entree("AAA", niveau=reg.NIVEAU_CANDIDAT)])
        self.assertEqual(reg.actions_utilisables(r), {})

    def test_capitalisation_prix_fois_actions(self):
        data = {"companies": [company("AAA")]}
        r = registre([entree("AAA", actions=2_000_000)])
        lignes = reg.capitalisations(r, data)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["capitalisation_fcfa"], 20_000_000_000)

    def test_capitalisation_ne_prend_pas_un_exercice_ancien_sans_avertir(self):
        data = {"companies": [company("AAA")]}
        r = registre([entree("AAA", exercice=2019, actions=2_000_000)])
        lignes = reg.capitalisations(r, data)
        self.assertIsNotNone(lignes[0]["avertissement"])

    def test_manquants_priorisent_ceux_qui_ont_un_resultat(self):
        data = {
            "companies": [
                company("SANS", figures={}),
                company("AVEC", figures={"resultat_net": figure(1e9)}),
            ]
        }
        liste = reg.manquants(data, registre([]))
        self.assertEqual(liste[0]["ticker"], "AVEC")
        self.assertEqual(liste[0]["score_deblocage"], 4)


class CompletudeTests(unittest.TestCase):
    def test_capacite_servie_seulement_avec_tous_les_intrants(self):
        data = {"generated_at": "x", "companies": [company("AAA")]}
        rapport = couv.mesurer(data, registre([]))
        capacites = {c["cle"]: c for c in rapport["capacites"]}
        # Décrire le marché ne demande ni actions ni bénéfice.
        self.assertEqual(capacites["decrire_marche"]["societes_servies"], 1)
        # Capitaliser exige le nombre d'actions : absent.
        self.assertEqual(capacites["capitaliser"]["societes_servies"], 0)

    def test_les_actions_debloquent_capitalisation_et_per(self):
        figures = {"resultat_net_part_groupe": figure(5e9), "capitaux_propres": figure(20e9)}
        data = {"generated_at": "x", "companies": [company("AAA", figures=figures)]}
        rapport = couv.mesurer(data, registre([entree("AAA")]))
        capacites = {c["cle"]: c for c in rapport["capacites"]}
        self.assertEqual(capacites["capitaliser"]["societes_servies"], 1)
        self.assertEqual(capacites["per_sigma"]["societes_servies"], 1)
        self.assertEqual(capacites["ancre_patrimoniale"]["societes_servies"], 1)

    def test_chaque_capacite_a_une_condition_ecrite(self):
        for capacite in couv.CAPACITES:
            self.assertTrue(capacite["conditions"], capacite["cle"])
            self.assertTrue(capacite["bloque"], capacite["cle"])

    def test_blocages_tries_par_importance(self):
        data = {"generated_at": "x", "companies": [company(f"S{i}") for i in range(5)]}
        rapport = couv.mesurer(data, registre([]))
        nombres = [n for _, n in rapport["blocages_par_importance"]]
        self.assertEqual(nombres, sorted(nombres, reverse=True))


class EtatReelTests(unittest.TestCase):
    def test_registre_reel_et_completude(self):
        if not (reg.REGISTRE.exists() and reg.DATA.exists()):
            self.skipTest("registre ou données absents")
        rapport = reg.rapport_complet()
        self.assertGreaterEqual(rapport["couverture"]["entrees_valides"], 2)
        # Chaque capitalisation publiée porte son niveau de preuve.
        for ligne in rapport["capitalisations"]:
            self.assertIn(ligne["niveau_preuve"], reg.NIVEAUX_UTILISABLES)

    def test_capacite_per_sigma_non_atteinte_aujourd_hui(self):
        if not (reg.REGISTRE.exists() and reg.DATA.exists()):
            self.skipTest("registre ou données absents")
        data = json.loads(reg.DATA.read_text(encoding="utf-8"))
        rapport = couv.mesurer(data, reg.charger())
        capacites = {c["cle"]: c for c in rapport["capacites"]}
        # Fait mesuré, pas souhait : aucun PER calculable par SIGMA sur 48 sociétés.
        self.assertEqual(capacites["per_sigma"]["societes_servies"], 0)


if __name__ == "__main__":
    unittest.main()

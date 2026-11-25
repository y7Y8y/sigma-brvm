"""Contrat du module Verdict — la réponse, pas l'empilement.

Reproche à l'origine : « l'app est remplie d'infos mais sans réel but précis,
qui de conseiller l'achat d'actions moyen, court et long terme ». Ces tests
tiennent les trois choses qui font qu'un verdict vaut mieux qu'un indicateur :

1. il répond sur trois horizons distincts, pas un score mélangé ;
2. il dit « non calculable » avec sa raison au lieu d'estimer ;
3. il n'énonce jamais une consigne d'achat ou de vente.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
WEB = RACINE / "web"
sys.path.insert(0, str(RACINE / "ingestion"))

import verdict  # noqa: E402

DATA = json.loads((WEB / "data" / "data.json").read_text(encoding="utf-8"))
ARCHIVE = json.loads((WEB / "data" / "boc_archive.json").read_text(encoding="utf-8"))
VERDICTS = verdict.construire(DATA, ARCHIVE)

# Formules qui transformeraient une observation en consigne. Elles sont
# interdites dans le texte produit : c'est la frontière « pas conseil ».
INTERDITS = [
    r"\bachetez\b", r"\bvendez\b", r"\bacheter cette action\b", r"\bnous recommandons\b",
    r"\brecommandation\b", r"\bconseillons\b", r"\bobjectif de cours\b", r"\bsignal d'achat\b",
    r"\bil faut acheter\b", r"\bil faut vendre\b", r"\bopportunité d'achat\b",
]


def textes(verdict_dict):
    """Tout le texte destiné à l'écran, pour la chasse aux consignes."""
    sortie = []
    for v in verdict_dict.values():
        for h in v.horizons.values():
            sortie += [h.get("phrase") or "", h.get("raison") or ""]
            sortie += [str(x) for x in (h.get("details") or [])]
    return sortie


class StructureTests(unittest.TestCase):
    def test_trois_horizons_par_societe(self):
        for ticker, v in VERDICTS.items():
            self.assertEqual(set(v.horizons), {"court", "moyen", "long"}, ticker)

    def test_chaque_horizon_a_une_regle_ecrite(self):
        for ticker, v in VERDICTS.items():
            for nom, h in v.horizons.items():
                self.assertTrue(h.get("regle"), f"{ticker}/{nom} sans règle publiée")

    def test_aucun_score_composite(self):
        # Un score unique mélangerait trois questions et cacherait laquelle échoue.
        for v in VERDICTS.values():
            for h in v.horizons.values():
                self.assertNotIn("score", h, "un horizon ne doit pas porter de score agrégé")

    def test_le_verdict_ne_remplace_jamais_une_absence_par_un_zero(self):
        for ticker, v in VERDICTS.items():
            for nom, h in v.horizons.items():
                if h.get("statut") == "non_calculable":
                    self.assertTrue(h.get("raison"), f"{ticker}/{nom} : absence non motivée")
                    self.assertIsNone(h.get("phrase"), f"{ticker}/{nom} : une phrase masque l'absence")


class CalculsTests(unittest.TestCase):
    def test_la_distribution_de_per_est_celle_de_la_societe(self):
        # Le reproche central : un seuil de marché (« PER < 15 ») n'est pas une
        # lecture de cette société. On vérifie que la distribution vient bien de
        # ses propres séances et qu'elle est triée.
        for ticker, v in VERDICTS.items():
            d = v.horizons["moyen"].get("donnees")
            if not d:
                continue
            self.assertLessEqual(d["q1"], d["mediane"], ticker)
            self.assertLessEqual(d["mediane"], d["q3"], ticker)
            self.assertGreaterEqual(d["seances"], verdict.MIN_SEANCES_PER, ticker)

    def test_la_decomposition_reconstitue_le_cours(self):
        # cours = bénéfice implicite × PER : la décomposition doit être exacte,
        # sinon elle raconte n'importe quoi sur l'origine du mouvement.
        for ticker, v in VERDICTS.items():
            d = v.horizons["moyen"].get("decomposition")
            if not d:
                continue
            for borne in ("debut", "fin"):
                produit = d[borne]["benefice_implicite"] * d[borne]["per"]
                self.assertAlmostEqual(produit / d[borne]["cours"], 1.0, places=2, msg=f"{ticker}/{borne}")

    def test_aucune_comparaison_entre_perimetres_eloignes(self):
        # ONTBF comparait 2021 à 2025 : deux sociétés différentes dans le temps.
        for v in VERDICTS.values():
            long = v.horizons["long"]
            if long.get("ton") == "a_verifier":
                self.assertTrue(any("périmètre" in str(d) for d in long.get("details", [])), v.ticker)


class FrontiereTests(unittest.TestCase):
    def test_aucune_consigne_dans_le_texte(self):
        fautes = []
        for texte in textes(VERDICTS):
            for motif in INTERDITS:
                if re.search(motif, texte, re.I):
                    fautes.append((motif, texte[:90]))
        self.assertEqual(fautes, [], f"formules de conseil détectées : {fautes}")

    def test_chaque_verdict_est_borne_a_son_horizon(self):
        # Le court terme parle de la séance, le moyen du prix payé, le long de
        # l'entreprise. Aucune phrase ne doit déborder sur un autre horizon.
        for ticker, v in VERDICTS.items():
            if v.horizons["court"].get("statut") == "calcule":
                self.assertIn("centile", v.horizons["court"]["phrase"], ticker)
            if v.horizons["moyen"].get("statut") == "calcule":
                self.assertIn("PER", v.horizons["moyen"]["phrase"], ticker)


class CouvertureTests(unittest.TestCase):
    def test_la_couverture_est_mesuree_pas_promise(self):
        r = verdict.resume(VERDICTS)
        self.assertEqual(r["societes"], len(DATA["companies"]))
        self.assertGreaterEqual(r["trois_horizons_complets"], 30, f"trop peu de verdicts complets : {r}")
        self.assertLess(r["trois_horizons_complets"], r["societes"], "tout ne peut pas être complet : le dire")

    def test_la_capitalisation_n_est_jamais_deduite(self):
        for ticker, v in VERDICTS.items():
            if v.capitalisation.get("statut") == "calcule":
                self.assertTrue(v.capitalisation.get("actions"), ticker)
                self.assertIn("document", v.capitalisation.get("base", ""), ticker)
            else:
                self.assertIn("nombre d'actions", v.capitalisation.get("raison", ""), ticker)


class FichierPublieTests(unittest.TestCase):
    def test_le_fichier_livre_est_a_jour(self):
        chemin = WEB / "data" / "verdicts.json"
        self.assertTrue(chemin.exists(), "verdicts.json absent du site")
        publie = json.loads(chemin.read_text(encoding="utf-8"))
        self.assertEqual(publie["resume"], verdict.resume(VERDICTS),
                         "verdicts.json ne correspond plus au module : relancer ingestion/verdict.py --out")

    def test_les_seuils_publies_sont_ceux_du_code(self):
        publie = json.loads((WEB / "data" / "verdicts.json").read_text(encoding="utf-8"))
        self.assertEqual(publie["seuils"]["per_cher_percentile"], verdict.SEUIL_PER_CHER)
        self.assertEqual(publie["seuils"]["min_seances_per"], verdict.MIN_SEANCES_PER)

    def test_le_module_s_execute_en_ligne_de_commande(self):
        resultat = subprocess.run([sys.executable, str(RACINE / "ingestion" / "verdict.py"), "SNTS"],
                                  capture_output=True, text=True, timeout=120)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("SNTS", resultat.stdout)
        for horizon in ("COURT", "MOYEN", "LONG"):
            self.assertIn(horizon, resultat.stdout)


class EcranTests(unittest.TestCase):
    def test_l_application_affiche_le_verdict_avant_les_preuves(self):
        js = (WEB / "app.js").read_text(encoding="utf-8")
        fiche = js.index('class="card verdict-card section-space"')
        preuves = js.index('Série annuelle et piliers SIGMA')
        self.assertLess(fiche, preuves, "le verdict doit précéder les preuves")

    def test_l_application_reste_utilisable_sans_verdicts(self):
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn('VERDICTS = null', js)
        self.assertIn("verdict non chargé", js.lower())


if __name__ == "__main__":
    unittest.main()

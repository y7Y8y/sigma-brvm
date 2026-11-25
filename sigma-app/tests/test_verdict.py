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
            self.assertGreaterEqual(d["seances"], verdict.PER_SEANCES_LIMITE, ticker)
            if d["seances"] < verdict.PER_SEANCES_PLEIN:
                # Une distribution courte est admise, jamais silencieuse.
                self.assertEqual(d.get("profondeur"), "limitee", ticker)
                self.assertEqual(v.horizons["moyen"].get("profondeur"), "limitee", ticker)

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

    def test_la_capitalisation_a_trois_niveaux_jamais_confondus(self):
        """Directe (actions lues), implicite (identité PER × résultat), absente."""
        for ticker, v in VERDICTS.items():
            cap = v.capitalisation
            statut = cap.get("statut")
            if statut == "calcule":
                self.assertTrue(cap.get("actions"), ticker)
                self.assertIn("document", cap.get("base", ""), ticker)
            elif statut == "implicite":
                # L'identité doit être vérifiable à partir des champs publiés.
                self.assertAlmostEqual(
                    cap["valeur_fcfa"] / (cap["per_publie"] * cap["resultat_net"]), 1.0, places=6, msg=ticker)
                self.assertIn("identité", cap.get("base", ""), ticker)
                self.assertTrue(cap.get("limite"), f"{ticker} : une déduction doit dire sa limite")
            else:
                self.assertEqual(statut, "non_calculable", ticker)
                self.assertIn("nombre d'actions", cap.get("raison", ""), ticker)
                self.assertIn("deblocage", cap, f"{ticker} : un trou sans déblocage n'aide personne")

    def test_une_capitalisation_deduite_ne_produit_jamais_un_nombre_d_actions(self):
        # Le verrou reste le verrou : aucun champ « actions » sur une déduction.
        for ticker, v in VERDICTS.items():
            if v.capitalisation.get("statut") == "implicite":
                self.assertNotIn("actions", v.capitalisation, ticker)


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
        self.assertEqual(publie["seuils"]["per_seances_plein"], verdict.PER_SEANCES_PLEIN)
        self.assertEqual(publie["seuils"]["per_seances_limite"], verdict.PER_SEANCES_LIMITE)

    def test_le_module_s_execute_en_ligne_de_commande(self):
        resultat = subprocess.run([sys.executable, str(RACINE / "ingestion" / "verdict.py"), "SNTS"],
                                  capture_output=True, text=True, timeout=120)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("SNTS", resultat.stdout)
        for horizon in ("COURT", "MOYEN", "LONG"):
            self.assertIn(horizon, resultat.stdout)


class RevenuTests(unittest.TestCase):
    """Un rendement n'est pas un revenu : trois preuves, jamais une note."""

    def test_le_rendement_vient_du_boc_et_de_lui_seul(self):
        """Le tableau BRVM mêle brut et net : aucun montant d'une source à l'autre."""
        for ticker, v in VERDICTS.items():
            r = v.revenu
            if r["rendement_pct"] is None:
                continue
            boc = DATA["companies"][[c["ticker"] for c in DATA["companies"]].index(ticker)]
            self.assertEqual(r["rendement_pct"], boc["latest_boc"]["net_dividend_yield_pct"], ticker)

    def test_aucun_rendement_n_est_calcule_sur_un_dividende_d_une_autre_source(self):
        for ticker, v in VERDICTS.items():
            r = v.revenu
            if r["rendement_pct"] is None or not v.cours:
                continue
            # Un rendement recalculé depuis le tableau de paiement donnerait un
            # écart de 12 à 14 % dans les cas bruts : on vérifie que le chiffre
            # publié est repris tel quel, pas reconstruit.
            self.assertEqual(r["rendement_source"].startswith("BOC"), True, ticker)

    def test_les_trois_preuves_sont_independantes_et_comptees(self):
        for ticker, v in VERDICTS.items():
            r = v.revenu
            p = r["preuves"]
            self.assertEqual(set(p), {"regularite", "financement", "couverture"}, ticker)
            self.assertEqual(r["preuves_reunies"], sum(1 for x in p.values() if x), ticker)
            self.assertIn(r["preuve"], {"documentaire", "partielle", "absente"}, ticker)

    def test_aucune_preuve_n_est_accorde_par_defaut(self):
        """Une preuve « tenue » doit s'appuyer sur un chiffre publié, pas sur une absence."""
        for ticker, v in VERDICTS.items():
            r = v.revenu
            if r["preuves"]["regularite"]:
                self.assertGreaterEqual(r["regularite"]["annees_consecutives"], 3, ticker)
            if r["preuves"]["financement"]:
                self.assertEqual(r["payout"]["statut"], "documentaire", ticker)
                self.assertLessEqual(r["payout"]["dernier"]["payout_pct"], 100, ticker)
            if r["preuves"]["couverture"]:
                self.assertEqual(r["couverture"]["statut"], "calcule", ticker)
                self.assertGreaterEqual(r["couverture"]["couverture_x"], 1, ticker)

    def test_un_dividende_non_renouvele_est_signale(self):
        """Le cas SIVC : un versement de 2016 ne fait pas un revenu de 2026."""
        for ticker, v in VERDICTS.items():
            r = v.revenu
            reg = r["regularite"]
            if reg.get("statut") == "documentee" and reg.get("en_retard_sur_les_comptes"):
                self.assertTrue(r["rendement_en_retard"], ticker)
                self.assertTrue(any("versement passé" in a for a in r["alertes"]), ticker)

    def test_un_rendement_hors_norme_porte_un_avertissement(self):
        for ticker, v in VERDICTS.items():
            r = v.revenu
            if (r["rendement_pct"] or 0) > 20 and r["preuves_reunies"] < 3:
                self.assertTrue(any("hors norme" in a or "très supérieure" in a for a in r["alertes"]), ticker)

    def test_aucune_formule_de_conseil_dans_le_revenu(self):
        for v in VERDICTS.values():
            texte = verdict.normalize_texte(" ".join(v.revenu["points"] + v.revenu["alertes"]))
            for interdit in INTERDITS:
                self.assertIsNone(re.search(interdit, texte), f"{interdit} dans le revenu")

    def test_le_registre_compte_les_trous_de_revenu(self):
        lignes = [m for m in verdict.manques(VERDICTS) if m["horizon"] == "revenu"]
        incompletes = [t for t, v in VERDICTS.items() if v.revenu["preuve"] != "documentaire"]
        self.assertEqual(len(lignes), len(incompletes))
        for ligne in lignes:
            self.assertTrue(ligne["deblocage"], ligne)


class RegistreManquesTests(unittest.TestCase):
    """« Je ne veux rien de partiel » : le registre doit être complet et honnête."""

    def setUp(self):
        self.manques = verdict.manques(VERDICTS)
        self.resume = verdict.resume(VERDICTS)

    def test_chaque_manque_nomme_une_source(self):
        for m in self.manques:
            self.assertTrue(m.get("source"), m)
            self.assertTrue(m.get("raison"), m)

    def test_le_registre_couvre_toutes_les_societes_incompletes(self):
        incompletes = {t for t, v in VERDICTS.items()
                       if any(v.horizons[h].get("statut") != "calcule"
                              or v.horizons[h].get("profondeur", "pleine") != "pleine"
                              for h in ("court", "moyen", "long"))}
        couvertes = {m["ticker"] for m in self.manques if m["horizon"] != "capitalisation"}
        self.assertTrue(incompletes.issubset(couvertes),
                        f"sociétés incomplètes sans ligne de registre : {sorted(incompletes - couvertes)}")

    def test_le_compte_du_registre_est_publie(self):
        publie = json.loads((WEB / "data" / "verdicts.json").read_text(encoding="utf-8"))
        self.assertIn("manques", publie)
        self.assertEqual(len(publie["manques"]), len(self.manques))

    def test_aucun_manque_invente(self):
        # Une ligne « limite » doit correspondre à un horizon réellement calculé.
        for m in self.manques:
            if m["etat"] != "limite":
                continue
            horizon = {"court terme": "court", "moyen terme": "moyen", "long terme": "long"}.get(m["horizon"])
            if horizon is None:
                continue
            v = VERDICTS[m["ticker"]]
            self.assertEqual(v.horizons[horizon].get("statut"), "calcule", m)
            self.assertEqual(v.horizons[horizon].get("profondeur"), "limitee", m)


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

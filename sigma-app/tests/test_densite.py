"""Contrat de densité — 2026-10-28.

Constat utilisateur : « dans tous les onglets y'a trop d'infos, j'ai pas envie
de voir tout ça ». La réponse n'est pas de supprimer des données : c'est de
séparer ce qui sert à décider (visible) de la méthode, des listes complètes et
des preuves (plié, à un clic).

Ces tests empêchent le retour en arrière : portes de navigation bornées, page
pleine largeur, pliage disponible partout.
"""

import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
CSS = (WEB / "styles.css").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")
JS = (WEB / "app.js").read_text(encoding="utf-8")


class LargeurTests(unittest.TestCase):
    def test_la_page_utilise_toute_la_largeur(self):
        # Le plafond de 1 460 px laissait des bandes vides de chaque côté et
        # tassait les tableaux de décision au centre de l'écran.
        bloc = re.search(r"\n\.main \{([^}]+)\}", CSS)
        self.assertIsNotNone(bloc)
        self.assertIn("max-width: none", bloc.group(1))
        self.assertNotIn("max-width: 1460px", CSS)

    def test_la_prose_reste_lisible(self):
        # Pleine largeur pour les tableaux, mesure de lecture bornée pour le texte.
        self.assertIn("max-width: 68ch", CSS)
        self.assertIn(".source-line", CSS)


class PortesTests(unittest.TestCase):
    def test_trois_portes_dans_decision(self):
        portes = re.findall(r'data-decision-tab="([a-z]+)"', HTML)
        self.assertEqual(portes, ["mois", "examiner", "donnees"], portes)

    def test_les_anciennes_portes_restent_accessibles(self):
        # Les liens existants (data-decision-link="radar", hash, etc.) ne cassent pas.
        for ancienne, porte in (("radar", "examiner"), ("baisses", "examiner"),
                                ("contexte", "donnees"), ("chiffres", "donnees"),
                                ("documents", "donnees")):
            self.assertRegex(JS, rf'{ancienne}:\s*"{porte}"')

    def test_aucun_onglet_mort(self):
        # Les trois portes sont rendues ; toute valeur inconnue retombe sur « mois ».
        self.assertIn('["mois", "examiner", "donnees"]', JS)
        self.assertIn('ui.analysisTab === "examiner"', JS)
        self.assertIn('ui.analysisTab === "donnees"', JS)
        self.assertIn(": renderAnalysisDecision();", JS)


class PliageTests(unittest.TestCase):
    def test_le_composant_de_pliage_existe(self):
        self.assertIn("function fold(", JS)
        self.assertIn('class="fold', JS)
        self.assertIn(".fold > summary", CSS)

    def test_le_pliage_est_reellement_utilise(self):
        usages = JS.count("${fold(")
        self.assertGreaterEqual(usages, 8, f"plis utilisés : {usages}")

    def test_les_blocs_les_plus_lourds_sont_plies(self):
        for titre in (
            "Plafonds homologués par l’AMF-UMOA",
            "Série annuelle et piliers SIGMA",
            "PER, rendement et dernier dividende publiés au BOC",
            "Liquidité des 48 sociétés",
            "Contexte macro, échéances et hypothèses personnelles",
            "Pourquoi les autres sociétés n’apparaissent pas",
        ):
            self.assertIn(titre, JS, f"bloc non plié : {titre}")

    def test_en_clair_est_replie(self):
        # « En clair » était une dissertation permanente au-dessus de chaque page.
        bloc = re.search(r"function plainSummary\(([^}]+)\}", JS, re.S)
        self.assertIsNotNone(bloc)
        self.assertIn("return fold(", bloc.group(1))

    def test_le_contenu_plie_reste_rendu(self):
        # Le corps est rendu même fermé : les formulaires et boutons qu'il
        # contient gardent leurs écouteurs.
        self.assertIn('<div class="fold-body">${body}</div>', JS)

    def test_une_seule_liste_de_radar_est_visible(self):
        self.assertIn("selection.slice(0, 3)", JS)


if __name__ == "__main__":
    unittest.main()

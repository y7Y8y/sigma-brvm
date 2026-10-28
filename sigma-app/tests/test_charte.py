"""Charte typographique — contrat vérifiable sans navigateur.

Constat du 28 octobre 2026 : « tout à la même taille dans chaque onglet ».
Mesure : vingt et une tailles de police distinctes dans la feuille, dont neuf
entre 10 et 15 px, et vingt-cinq tailles écrites en dur dans le HTML généré.
À l'écran, 10 / 10,5 / 11 / 11,5 / 12 / 12,5 / 13 ne se distinguent pas.

Une charte n'est pas une intention : c'est une contrainte. Ces tests la
tiennent — sept marches, des rôles nommés, aucune taille en dur ailleurs.

Note honnête : jsdom ne résout pas `var()` dans getComputedStyle. Ces contrôles
portent donc sur la source CSS, pas sur le rendu pixel d'un vrai navigateur.
"""

import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
CSS = (WEB / "styles.css").read_text(encoding="utf-8")
JS = (WEB / "app.js").read_text(encoding="utf-8")
RACINE = CSS[CSS.index(":root {"):CSS.index("}", CSS.index(":root {"))]

MARCHES = {
    "micro": 10.5,
    "small": 12.0,
    "body": 14.0,
    "subtitle": 17.0,
    "title": 21.0,     # borne haute du clamp
    "hero": 27.0,      # borne haute du clamp
    "figure": 31.0,    # borne haute du clamp
}


def valeur_px(nom: str) -> float:
    """Borne haute d'une marche, en px, lue dans :root."""
    brut = re.search(rf"--fs-{nom}:\s*([^;]+);", RACINE).group(1).strip()
    if brut.startswith("clamp("):
        return float(re.search(r"([0-9.]+)px\)$", brut).group(1))
    return float(re.match(r"([0-9.]+)px", brut).group(1))


class EchelleTests(unittest.TestCase):
    def test_sept_marches_pas_une_de_plus(self):
        marches = re.findall(r"--fs-([a-z]+):", RACINE)
        self.assertEqual(sorted(marches), sorted(MARCHES), f"marches trouvées : {marches}")

    def test_les_bornes_correspondent_a_la_charte(self):
        for nom, attendu in MARCHES.items():
            self.assertAlmostEqual(valeur_px(nom), attendu, places=1, msg=nom)

    def test_chaque_marche_se_distingue_de_la_precedente(self):
        # Le défaut d'origine : 14 % d'écart entre deux marches voisines.
        precedent = None
        for nom in ("micro", "small", "body", "subtitle", "title", "hero", "figure"):
            valeur = valeur_px(nom)
            if precedent is not None:
                rapport = valeur / precedent
                self.assertGreaterEqual(rapport, 1.12, f"{nom} trop proche de la marche précédente ({rapport:.2f})")
                self.assertLessEqual(rapport, 1.35, f"{nom} saute trop loin ({rapport:.2f})")
            precedent = valeur

    def test_l_echelle_couvre_une_vraie_amplitude(self):
        # Sept marches utiles seulement si le bas et le haut sont franchement
        # séparés : sinon on retrouve « tout à la même taille ».
        self.assertGreaterEqual(valeur_px("body") / valeur_px("micro"), 1.3)
        self.assertGreaterEqual(valeur_px("hero") / valeur_px("body"), 1.8)
        self.assertGreaterEqual(valeur_px("figure") / valeur_px("body"), 2.0)


class ApplicationsTests(unittest.TestCase):
    def test_aucune_taille_en_dur_dans_la_feuille(self):
        # Seul :root a le droit de nommer des px.
        hors_racine = CSS.replace(RACINE, "")
        self.assertEqual(re.findall(r"font-size:\s*[0-9]", hors_racine), [])

    def test_aucune_taille_en_dur_dans_le_html_genere(self):
        self.assertEqual(re.findall(r"font-size:", JS), [], "app.js doit passer par une classe de rôle")

    def test_les_titres_ont_quatre_marches_distinctes(self):
        for selecteur, marche in (("h1", "hero"), ("h2", "title"), ("h3", "subtitle")):
            bloc = re.search(rf"\n{selecteur} \{{([^}}]+)\}}", CSS)
            self.assertIsNotNone(bloc, selecteur)
            self.assertIn(f"var(--fs-{marche})", bloc.group(1), selecteur)
        self.assertGreaterEqual(valeur_px("hero") / valeur_px("title"), 1.2,
                                "l'écart h1/h2 doit être visible : il valait 1,14 avant")

    def test_les_chiffres_se_detachent_du_texte(self):
        # Un nombre au même corps que la phrase qui l'entoure ne se lit pas.
        for selecteur, marche in ((".metric-value", "subtitle"), (".kpi-value", "figure"), (".company-price", "figure")):
            bloc = re.search(rf"\n{re.escape(selecteur)} \{{([^}}]+)\}}", CSS)
            self.assertIsNotNone(bloc, selecteur)
            self.assertIn(f"var(--fs-{marche})", bloc.group(1), selecteur)

    def test_les_etiquettes_sont_toutes_en_micro_capitales(self):
        for selecteur in (".eyebrow", ".metric-label", ".kpi-label"):
            bloc = re.search(rf"\n{re.escape(selecteur)} \{{([^}}]+)\}}", CSS)
            self.assertIsNotNone(bloc, selecteur)
            self.assertIn("var(--fs-micro)", bloc.group(1), selecteur)
            self.assertIn("uppercase", bloc.group(1), selecteur)

    def test_le_corps_de_texte_ne_change_pas_sur_mobile(self):
        # `body { font-size: 15px }` dans la requête mobile faisait grossir tout
        # le texte du téléphone et écrasait la hiérarchie.
        for bloc in re.findall(r"@media[^{]+\{([\s\S]+?)\n\}", CSS):
            self.assertNotRegex(bloc, r"\n\s*body \{[^}]*font-size", "le corps de texte doit rester la référence")

    def test_les_roles_nommes_existent(self):
        for classe in (".mode-glyph", ".metric-value.is-compact", ".text-body",
                       ".summary-strong", ".summary-title", ".score-total-suffix"):
            self.assertIn(classe, CSS, classe)


class SelecteurDEtapesTests(unittest.TestCase):
    """Les trois portes de Décision doivent remplir leur ligne."""

    def test_les_onglets_occupent_la_largeur(self):
        bloc = re.search(r"\n\.tabs \{([^}]+)\}", CSS)
        self.assertIsNotNone(bloc)
        self.assertIn("grid", bloc.group(1))
        self.assertIn("repeat(3, minmax(0, 1fr))", bloc.group(1))
        self.assertIn("max-width: 720px", bloc.group(1))

    def test_les_onglets_sont_centres_et_de_meme_largeur(self):
        bloc = re.search(r"\n\.tab \{([^}]+)\}", CSS)
        self.assertIsNotNone(bloc)
        self.assertIn("width: 100%", bloc.group(1))
        self.assertIn("text-align: center", bloc.group(1))


if __name__ == "__main__":
    unittest.main()

"""Invariants du système de design — ce qu'un test peut vérifier sans navigateur.

Ces tests ne jugent pas l'esthétique : ils empêchent la réapparition des défauts
constatés sur mobile — tailles de police hors échelle, navigation qui déborde,
vert utilisé comme décoration, montants coupés au milieu d'un nombre.
"""

import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
CSS = (WEB / "styles.css").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")
JS = (WEB / "app.js").read_text(encoding="utf-8")

TAILLE_MIN, TAILLE_MAX = 10.0, 30.0
TOKENS_TYPO = ("--fs-micro", "--fs-small", "--fs-body", "--fs-subtitle", "--fs-title", "--fs-hero", "--fs-figure")


def declarations(propriete: str) -> list[tuple[int, str]]:
    """Valeurs déclarées pour une propriété, avec leur ligne."""
    resultat = []
    for numero, ligne in enumerate(CSS.splitlines(), start=1):
        for trouve in re.finditer(rf"{propriete}\s*:\s*([^;}}]+)", ligne):
            resultat.append((numero, trouve.group(1).strip()))
    return resultat


class StructureCssTests(unittest.TestCase):
    def test_accolades_equilibrees(self):
        self.assertEqual(CSS.count("{"), CSS.count("}"))

    def test_tous_les_tokens_utilises_sont_definis(self):
        definis = set(re.findall(r"(--[a-z0-9-]+)\s*:", CSS))
        utilises = set(re.findall(r"var\((--[a-z0-9-]+)", CSS))
        manquants = sorted(utilises - definis)
        self.assertEqual(manquants, [], f"variables non définies : {manquants}")

    def test_echelle_typographique_complete(self):
        definis = set(re.findall(r"(--[a-z0-9-]+)\s*:", CSS))
        for token in TOKENS_TYPO:
            self.assertIn(token, definis, f"token typographique manquant : {token}")


class TypographieTests(unittest.TestCase):
    def test_aucune_taille_hors_bornes(self):
        # Les tailles aberrantes (7,8 px illisible, 42/52 px qui écrasent tout)
        # sont interdites. Les clamp() des tokens ne sont pas concernés.
        fautes = []
        for ligne, valeur in declarations("font-size"):
            if "clamp(" in valeur or "var(" in valeur or "inherit" in valeur:
                continue
            trouve = re.match(r"([0-9.]+)px", valeur)
            if not trouve:
                continue
            taille = float(trouve.group(1))
            if taille < TAILLE_MIN or taille > TAILLE_MAX:
                fautes.append((ligne, valeur))
        self.assertEqual(fautes, [], f"tailles hors échelle (10–30 px) : {fautes}")

    def test_les_titres_utilisent_l_echelle(self):
        for selecteur, token in (("h1", "--fs-hero"), ("h2", "--fs-title"), ("h3", "--fs-subtitle")):
            bloc = re.search(rf"\n{selecteur} \{{([^}}]+)\}}", CSS)
            self.assertIsNotNone(bloc, f"règle {selecteur} introuvable")
            self.assertIn(f"var({token})", bloc.group(1), f"{selecteur} doit utiliser {token}")

    def test_le_corps_de_texte_utilise_l_echelle(self):
        corps = re.search(r"\nbody \{([^}]+)\}", CSS)
        self.assertIsNotNone(corps)
        self.assertIn("var(--fs-body)", corps.group(1))


class NavigationTests(unittest.TestCase):
    def test_cinq_items_maximum(self):
        items = re.findall(r'class="nav-item[^"]*"\s+data-view="([a-z]+)"', HTML)
        if not items:
            items = re.findall(r'data-view="([a-z]+)"', HTML)
        self.assertEqual(len(items), 5, f"la barre doit tenir en 5 items, trouvé : {items}")

    def test_parametres_hors_de_la_barre_basse(self):
        self.assertNotIn('data-view="parametres"', HTML)
        self.assertIn('data-view-link="parametres"', HTML)

    def test_chaque_item_a_un_libelle_tronquable(self):
        for bloc in re.findall(r'<button[^>]*class="nav-item[^"]*"[^>]*>.*?</button>', HTML):
            self.assertIn('class="nav-label"', bloc, f"libellé non tronquable : {bloc[:80]}")

    def test_les_items_mobile_peuvent_retenir(self):
        mobile = CSS[CSS.index("@media (max-width: 920px)"):]
        regle = re.search(r"\.nav-item \{[^}]+\}", mobile)
        self.assertIsNotNone(regle)
        self.assertIn("flex: 1 1 0", regle.group(0))
        self.assertNotIn("flex: 1 0 auto", mobile)
        self.assertIn("min-width: 0", regle.group(0))

    def test_badge_ne_deborde_pas(self):
        mobile = CSS[CSS.index("@media (max-width: 920px)"):]
        regle = re.search(r"\.nav-badge \{[^}]+\}", mobile)
        self.assertIsNotNone(regle)
        self.assertIn("position: absolute", regle.group(0))
        self.assertNotIn("margin-top: -22px", mobile)


class CouleurTests(unittest.TestCase):
    def test_les_roles_de_couleur_existent(self):
        for token in ("--action", "--positive", "--attention", "--danger", "--sim", "--text-strong"):
            self.assertRegex(CSS, rf"{token}\s*:", f"rôle manquant : {token}")

    def test_le_vert_ne_sert_pas_de_decoration(self):
        # L'accent ne doit plus porter l'état actif, les compteurs ni les puces.
        for selecteur in (".nav-item.is-active", ".nav-badge"):
            bloc = re.search(rf"\n{re.escape(selecteur)} \{{([^}}]+)\}}", CSS.replace("\n.nav-item.is-active", "\n.nav-item.is-active"))
            if not bloc:
                continue
            self.assertNotIn("var(--accent", bloc.group(1), f"{selecteur} ne doit pas utiliser l'accent")

    def test_aucun_vert_code_en_dur_dans_les_nouveaux_blocs(self):
        # #10b981 / #a7f3d0 ne doivent plus apparaître dans les garde-fous.
        garde = CSS[CSS.index("Système de design v1.5"):]
        for code in ("#10b981", "#a7f3d0", "#064e3b"):
            self.assertNotIn(code, garde)


class DebordementTests(unittest.TestCase):
    def test_garde_fous_min_width_sur_les_enfants_flex(self):
        garde = CSS[CSS.index("Système de design v1.5"):]
        self.assertIn("min-width: 0", garde)
        for selecteur in (".event-row", ".kpi-card", ".view-heading"):
            self.assertIn(selecteur, garde)

    def test_les_montants_peuvent_se_couper_proprement(self):
        garde = CSS[CSS.index("Système de design v1.5"):]
        self.assertIn("overflow-wrap: anywhere", garde)


class DensiteTests(unittest.TestCase):
    def test_la_liste_d_accueil_utilise_la_version_courte(self):
        self.assertIn("alert.short || alert.body", JS)

    def test_les_echeances_macro_fournissent_une_version_courte(self):
        self.assertIn("short: calendarEventAmount(event)", JS)


if __name__ == "__main__":
    unittest.main()

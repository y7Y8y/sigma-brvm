import json
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"


class ServiceWorkerTests(unittest.TestCase):
    """Contrôles statiques de la PWA : sans navigateur, on vérifie ce qui est vérifiable."""

    def setUp(self):
        self.sw = (WEB / "sw.js").read_text(encoding="utf-8")

    def test_le_service_worker_existe_et_est_versionne(self):
        self.assertIn("const VERSION", self.sw)
        self.assertRegex(self.sw, r'VERSION\s*=\s*"[^"]+"')

    def test_tous_les_fichiers_precharges_existent(self):
        # On ne lit que le tableau COQUE : le garde-fou sur sw.js n'est pas un préchargement.
        bloc = re.search(r"const COQUE = \[(.+?)\];", self.sw, re.S)
        self.assertIsNotNone(bloc, "tableau COQUE introuvable")
        precharges = re.findall(r'"([\w./-]+\.(?:js|css|html|svg|png|webmanifest))"', bloc.group(1))
        self.assertTrue(precharges, "aucun fichier préchargé détecté")
        manquants = [nom for nom in precharges if not (WEB / nom).exists()]
        self.assertEqual(manquants, [], f"fichiers préchargés absents : {manquants}")

    def test_les_donnees_sont_reconnues_et_la_coque_non(self):
        # Le motif est lu dans sw.js puis rejoué : si le code change de règle,
        # ce test change avec lui au lieu de valider une copie fantôme.
        source = re.search(r"function estDonnee\(url\) \{\s*return (.+?);\s*\}", self.sw)
        self.assertIsNotNone(source)
        expression = source.group(1).strip()
        self.assertTrue(expression.startswith("/"), "le motif doit être une expression régulière")
        fin = expression.rindex("/")
        motif = re.compile(expression[1:fin])

        self.assertTrue(motif.search("/data/data.json"))
        self.assertTrue(motif.search("/data/boc_archive.json"))
        self.assertFalse(motif.search("/app.js"))
        self.assertFalse(motif.search("/data/notes.txt"))

    def test_aucune_mise_en_cache_de_reponse_partielle(self):
        # Une réponse tronquée mise en cache hors ligne donnerait des chiffres faux.
        self.assertIn("reponse.status === 200", self.sw)
        self.assertIn("reponse.ok", self.sw)

    def test_les_anciennes_versions_sont_purgees(self):
        self.assertIn("caches.delete", self.sw)
        self.assertIn("startsWith(VERSION)", self.sw)

    def test_le_service_worker_est_enregistre_par_la_page(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('navigator.serviceWorker.register("sw.js"', html)
        self.assertIn('"serviceWorker" in navigator', html)

    def test_echec_enregistrement_ne_bloque_pas_l_usage_en_ligne(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn(".catch(", html)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifeste = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))

    def test_champs_requis_pour_l_installation(self):
        for champ in ("name", "short_name", "start_url", "display", "icons"):
            self.assertIn(champ, self.manifeste)
        self.assertEqual(self.manifeste["display"], "standalone")

    def test_icone_presente_sur_le_disque(self):
        for icone in self.manifeste["icons"]:
            self.assertTrue(
                (WEB / icone["src"]).exists(), f"icône absente : {icone['src']}"
            )

    def test_icones_installables_pour_les_plateformes_strictes(self):
        # Android exige des icônes 192 et 512 px en PNG ; le SVG seul ne suffit pas
        # à une vraie installation sur toutes les plateformes.
        par_taille = {(i.get("sizes"), i.get("type")) for i in self.manifeste["icons"]}
        self.assertIn(("192x192", "image/png"), par_taille)
        self.assertIn(("512x512", "image/png"), par_taille)
        self.assertIn(("any", "image/svg+xml"), par_taille)


if __name__ == "__main__":
    unittest.main()

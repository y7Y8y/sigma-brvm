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

    def test_la_coque_est_servie_reseau_d_abord(self):
        # Défaut constaté le 28/10 : cache d'abord + version jamais incrémentée
        # = téléphone bloqué sur un app.js de la veille (six onglets affichés
        # alors que trois étaient déployés).
        self.assertNotIn("cacheDAbord(", self.sw, "la coque ne doit plus être servie depuis le cache")
        self.assertIn("reseauDAbord(request, CACHE_COQUE)", self.sw)
        self.assertIn('cache: "no-store"', self.sw)

    def test_la_page_se_recharge_au_changement_de_version(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn("controllerchange", html)
        self.assertIn("updateViaCache", html)
        self.assertIn("dejaRecharge", html)

    def test_version_du_cache_au_moins_v2(self):
        version = re.search(r'VERSION\s*=\s*"sigma-pwa-v(\d+)"', self.sw)
        self.assertIsNotNone(version)
        self.assertGreaterEqual(int(version.group(1)), 2)

    def test_le_service_worker_est_enregistre_par_la_page(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'navigator\.serviceWorker\s*\n?\s*\.register\("sw\.js"')
        self.assertIn('"serviceWorker" in navigator', html)

    def test_echec_enregistrement_ne_bloque_pas_l_usage_en_ligne(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn(".catch(", html)


class MobileTests(unittest.TestCase):
    """Défauts vus sur téléphone le 28/10 : tableau comprimé, pastille rognée."""

    def setUp(self):
        self.css = (WEB / "styles.css").read_text(encoding="utf-8")
        self.js = (WEB / "app.js").read_text(encoding="utf-8")

    def test_les_tableaux_ne_se_compriment_plus(self):
        # Sans min-width, `table { width: 100% }` écrasait huit colonnes dans
        # 390 px : chaque montant se coupait caractère par caractère.
        self.assertIn(".table-wrap > table { min-width: 620px; }", self.css)
        self.assertIn("white-space: nowrap", self.css)

    def test_la_selection_du_mois_n_est_plus_un_tableau(self):
        self.assertIn('class="pick-list"', self.js)
        self.assertIn(".pick-row", self.css)
        self.assertNotIn('<th>Société</th><th class="num">Cours utilisé</th>', self.js)

    def test_la_pastille_de_notification_reste_dans_son_bouton(self):
        self.assertIn(".icon-badge { top: 1px; right: 1px; }", self.css)

    def test_le_libelle_de_recherche_tient_sur_mobile(self):
        self.assertIn("raccourcirRecherche", self.js)
        self.assertIn('"Rechercher…"', self.js)


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

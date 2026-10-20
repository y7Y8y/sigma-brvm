import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))

from collect import (  # noqa: E402
    boc_archive_history,
    build_calendar_events,
    build_issuer_variant_map,
    classify_news,
    classify_report_document,
    cluster_amounts,
    compute_dividend_history,
    deduplicate_dividend_rows,
    detect_unit,
    extract_figures_from_pages,
    first_amount_after,
    compute_history_stats,
    compute_long_history_stats,
    compute_market_structure,
    Empty_boc_archive,
    extract_bceao_cpm_indicators,
    match_announcement_issuer,
    match_tickers_in_text,
    merge_boc_archive,
    merge_series_observations,
    parse_sgi_page,
    parse_umoa_emissions_page,
    parse_french_long_date,
    parse_number,
    parse_slash_date,
    strip_tracking_params,
)


class ParsingTests(unittest.TestCase):
    def test_parse_french_numbers(self):
        self.assertEqual(parse_number("43 500"), 43500)
        self.assertEqual(parse_number("-1,61 %"), -1.61)
        self.assertEqual(parse_number("1 937 595 319 FCFA"), 1937595319)
        self.assertIsNone(parse_number("SP"))
        self.assertIsNone(parse_number(""))

    def test_parse_french_dates(self):
        self.assertEqual(parse_french_long_date("27 octobre 2026"), "2026-10-27")
        self.assertEqual(parse_french_long_date("1 juin 2026"), "2026-06-01")
        self.assertIsNone(parse_french_long_date("date inconnue"))

    def test_history_performance_is_price_only_from_boc_rows(self):
        history = []
        for day in range(1, 23):
            history.append(
                {
                    "date": f"2026-01-{day:02d}",
                    "rows": {
                        "TEST": {
                            "close": 100 + day,
                            "volume": 100,
                            "traded_value_fcfa": 100 * (100 + day),
                            "variation_pct": 0,
                        }
                    },
                }
            )
        stats = compute_history_stats(history)["TEST"]
        self.assertEqual(stats["sessions_available"], 22)
        self.assertEqual(stats["traded_sessions_last_20"], 20)
        self.assertAlmostEqual(stats["performance_20_sessions_pct"], ((122 / 102) - 1) * 100, places=3)

    def test_market_structure_uses_breadth_and_boc_value(self):
        quotes = [
            {"variation_pct": 2, "volume": 10},
            {"variation_pct": -1, "volume": 0},
            {"variation_pct": 0, "volume": 5},
        ]
        boc = {
            "date": "2026-01-02",
            "rows": {
                "A": {"variation_pct": 1, "traded_value_fcfa": 50},
                "B": {"variation_pct": -1, "traded_value_fcfa": 30},
                "C": {"variation_pct": 0, "traded_value_fcfa": 20},
            },
        }
        structure = compute_market_structure(quotes, boc)
        self.assertEqual(structure["snapshot"]["advancers"], 1)
        self.assertEqual(structure["latest_boc"]["total_traded_value_fcfa"], 100)
        self.assertEqual(structure["capitalization_concentration"]["status"], "non_calculable")


class BocArchiveTests(unittest.TestCase):
    @staticmethod
    def _session(date: str, close: int) -> dict:
        return {
            "date": date,
            "url": f"https://www.brvm.org/boc_{date}.pdf",
            "sha256": f"sha-{date}-{close}",
            "composite_level": 100,
            "composite_variation_pct": 0.1,
            "discovery": "test",
            "rows": {
                "TEST": {
                    "close": close,
                    "variation_pct": 1.5,
                    "volume": 10,
                    "traded_value_fcfa": close * 10,
                    "previous_close": close - 1,
                    "open": close,
                    "reference_price": close,
                    "variation_previous_year_pct": 3,
                    "last_net_dividend_fcfa": 5,
                    "last_dividend_date_label": "1-juin-26",
                    "net_dividend_yield_pct": 4,
                    "per": 9,
                }
            },
        }

    def test_archive_merge_sorts_deduplicates_and_replaces(self):
        archive = merge_boc_archive(
            Empty_boc_archive(),
            [self._session("2026-01-02", 110), self._session("2026-01-01", 100)],
            "2026-01-03T00:00:00+00:00",
        )
        archive = merge_boc_archive(
            archive,
            [self._session("2026-01-02", 111)],
            "2026-01-04T00:00:00+00:00",
        )
        self.assertEqual(archive["sessions_count"], 2)
        self.assertEqual(archive["first_date"], "2026-01-01")
        self.assertEqual(archive["last_date"], "2026-01-02")
        history = boc_archive_history(archive)
        self.assertEqual(history[-1]["rows"]["TEST"]["close"], 111)
        self.assertEqual(history[-1]["rows"]["TEST"]["per"], 9)

    def test_long_history_stats_use_price_only_series(self):
        history = []
        closes = list(range(100, 170))
        closes[50] = 75  # chute après un plus haut : drawdown < -49 %
        for index, close in enumerate(closes):
            date = f"2026-{(index // 28) + 1:02d}-{(index % 28) + 1:02d}"
            history.append(
                {
                    "date": date,
                    "rows": {
                        "TEST": {
                            "close": close,
                            "volume": 10 if index % 2 == 0 else 0,
                            "traded_value_fcfa": close * 10 if index % 2 == 0 else 0,
                            "variation_pct": (index % 5) - 2,
                        }
                    },
                }
            )
        stats = compute_long_history_stats(history)["TEST"]
        self.assertEqual(stats["sessions_available"], 70)
        self.assertEqual(stats["traded_share_pct"], 50)
        self.assertAlmostEqual(
            stats["performance_60_sessions_pct"], ((169 / 109) - 1) * 100, places=3
        )
        self.assertLess(stats["max_drawdown_pct"], -49)
        self.assertIn("non_ajustés", stats["price_basis"])


class MacroCalendarTests(unittest.TestCase):
    def test_extract_bceao_cpm_indicators_from_official_wording(self):
        text = (
            "Le Comité de Politique Monétaire (CPM) a décidé, à l’issue de sa réunion tenue le "
            "9 septembre 2026, de maintenir le principal taux directeur auquel la Banque Centrale "
            "prête ses ressources aux banques à 3,00%, ainsi que le taux d’intérêt sur le guichet "
            "de prêt marginal à 5,00%, niveaux en vigueur depuis le 16 mars 2026. Le Comité a "
            "également décidé de maintenir à 3,00%, le coefficient des réserves obligatoires. "
            "Dans l’Union, le taux d'inflation s'est établi à 0,4% au deuxième trimestre 2026. "
            "Pour 2026, le taux d'inflation devrait ressortir en moyenne à 1,0%. L’activité est "
            "restée dynamique au deuxième trimestre 2026, avec une croissance estimée à 6,0% en "
            "glissement annuel. Pour l’année 2026 la croissance économique est attendue à 6,1%. "
            "Le crédit bancaire accordé au secteur privé a progressé de 6,6% à fin juin 2026."
        )
        indicators = extract_bceao_cpm_indicators(text)
        self.assertEqual(indicators["meeting_date"], "2026-09-09")
        self.assertEqual(indicators["rates_effective_since"], "2026-03-16")
        self.assertEqual(indicators["policy_rate_pct"], 3)
        self.assertEqual(indicators["marginal_lending_rate_pct"], 5)
        self.assertEqual(indicators["reserve_requirement_pct"], 3)
        self.assertEqual(indicators["inflation_latest_pct"], 0.4)
        self.assertEqual(indicators["inflation_forecast_pct"], 1)
        self.assertEqual(indicators["growth_latest_pct"], 6)
        self.assertEqual(indicators["growth_forecast_pct"], 6.1)
        self.assertEqual(indicators["private_credit_growth_pct"], 6.6)

    def test_parse_umoa_emissions_reclassifies_future_by_date_and_dedupes(self):
        html = """
        <table id="emission-hub-planifie-par">
          <tr><th>Émetteur</th><th>Instrument</th><th>Précisions</th><th>Date de l'opération</th><th>Montant (millions de FCFA)</th><th>Plus d'infos</th><th>Statut</th></tr>
          <tr><td>Mali</td><td></td><td>--</td><td>28/10/2026</td><td>40 000</td><td><a href="/fr/emission/mali-2810/">Plus d'infos</a></td><td>réalisée</td></tr>
        </table>
        <table id="emission-hub-avenir-par">
          <tr><th>Émetteur</th><th>Instrument</th><th>Précisions</th><th>Date de l'opération</th><th>Date de valeur</th><th>Échéance</th><th>Montant (millions de FCFA)</th><th>Plus d'infos</th><th>Etat</th></tr>
          <tr><td>Mali</td><td>ES</td><td>--</td><td>28/10/2026</td><td>29/10/2026</td><td>--</td><td>40 000</td><td><a href="/fr/emission/mali-2810/">Plus d'infos</a></td><td>réalisée</td></tr>
          <tr><td>Niger</td><td>ES</td><td>--</td><td>19/10/2026</td><td>20/10/2026</td><td>--</td><td>20 000</td><td><a href="/fr/emission/niger-1910/">Plus d'infos</a></td><td>réalisée</td></tr>
        </table>
        """
        rows = parse_umoa_emissions_page(html, "https://www.umoatitres.org/fr/emissions/", "2026-10-20")
        self.assertEqual(len(rows), 2)
        mali = next(row for row in rows if row["issuer_country"] == "Mali")
        self.assertEqual(mali["computed_status"], "a_venir")
        self.assertEqual(mali["source_status_label"], "réalisée")
        self.assertEqual(mali["instrument"], "ES")
        self.assertEqual(mali["value_date"], "2026-10-29")
        self.assertEqual(mali["amount_fcfa"], 40_000_000_000)

    def test_calendar_events_only_future_sourced_dates_sorted(self):
        dividends = [
            {
                "issuer": "ORANGE CI",
                "fiscal_year": "2025",
                "ex_date": "2026-10-25",
                "payment_date": "2026-11-02",
                "net_amount_fcfa": 100,
                "notice_url": "https://example.org/avis.pdf",
            },
            {
                "issuer": "ANCIEN",
                "fiscal_year": "2024",
                "ex_date": "2026-10-01",
                "payment_date": "2026-10-10",
                "net_amount_fcfa": 10,
                "notice_url": None,
            },
        ]
        macro = {
            "umoa_issuances": [
                {
                    "operation_date": "2026-10-22",
                    "issuer_country": "Niger",
                    "instrument": "ES",
                    "value_date": "2026-10-23",
                    "amount_fcfa": 40_000_000_000,
                    "url": "https://example.org/umoa",
                    "source_label": "UMOA-Titres — Émissions",
                }
            ],
            "bceao_events": [
                {
                    "date": "2026-12-09",
                    "title": "Réunion du Comité de Politique Monétaire de la BCEAO",
                    "detail": "Réunion ordinaire datée par la BCEAO.",
                    "url": "https://example.org/bceao-event",
                    "source_label": "BCEAO — Événements",
                }
            ],
        }
        events = build_calendar_events("2026-10-20", dividends, macro, [])
        self.assertEqual([event["date"] for event in events], ["2026-10-22", "2026-10-25", "2026-11-02", "2026-12-09"])
        self.assertTrue(all(event["in_days"] >= 0 for event in events))


class NewsTests(unittest.TestCase):
    COMPANIES = [
        {"ticker": "SNTS", "name": "SONATEL SENEGAL", "latest_boc": {"name": "SONATEL SN"}},
        {"ticker": "ETIT", "name": "Ecobank Transnational Incorporated TOGO",
         "latest_boc": {"name": "ECOBANK TRANS. INCORP. TG"}},
        {"ticker": "BOAC", "name": "BANK OF AFRICA COTE D'IVOIRE", "latest_boc": {"name": "BANK OF AFRICA CI"}},
    ]

    def test_parse_slash_date(self):
        self.assertEqual(parse_slash_date("15/10/2026"), "2026-10-15")
        self.assertIsNone(parse_slash_date("octobre 2026"))

    def test_announcement_issuer_matching(self):
        variants = build_issuer_variant_map(self.COMPANIES)
        self.assertEqual(match_announcement_issuer("SONATEL", variants), ["SNTS"])
        self.assertEqual(match_announcement_issuer("BANK OF AFRICA CI", variants), ["BOAC"])
        self.assertEqual(match_announcement_issuer("ECOBANK TG", variants), ["ETIT"])
        self.assertEqual(match_announcement_issuer("ENTREPRISE INCONNUE", variants), [])

    def test_press_text_matching_stays_strict(self):
        self.assertEqual(match_tickers_in_text("Sonatel publie ses résultats", self.COMPANIES), ["SNTS"])
        self.assertEqual(match_tickers_in_text("Le secteur bancaire progresse", self.COMPANIES), [])

    def test_classification_and_tracking_cleanup(self):
        item = {"title": "La BCEAO maintient son taux directeur", "excerpt": "",
                "category": "Flux", "tickers": [], "source_id": "sika_finance"}
        relevance, tags = classify_news(item)
        self.assertEqual(relevance, "macro")
        self.assertIn("politique_monetaire", tags)
        self.assertEqual(
            strip_tracking_params("https://exemple.org/a?utm_source=rss&page=2"),
            "https://exemple.org/a?page=2",
        )


class SgiDirectoryTests(unittest.TestCase):
    def test_parse_sgi_page_and_country_fallback(self):
        html = """
        <div class="view view-sgi">
          <div class="views-row">
            <div class="views-field views-field-nothing"><span class="field-content">
              <div class="Sénégal">ABCO Bourse</div>
              <div class="bloc_country">
                <div class="adresse_sgi">Dakar</div>
                <div class="tel_sgi">(+221) 33 822 68 00</div>
                <div class="site_sgi">www.abcobourse.com</div>
              </div>
            </span></div>
          </div>
          <div class="views-row">
            <div class="views-field views-field-nothing"><span class="field-content">
              <div class="">SGI EXEMPLE</div>
              <div class="bloc_country">
                <div class="adresse_sgi">Abidjan</div>
                <div class="tel_sgi">(225) 27 20 00 00 00</div>
              </div>
            </span></div>
          </div>
        </div>
        """
        items = parse_sgi_page(html, "https://www.brvm.org/fr/intervenants/sgi/tous")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["country"], "Sénégal")
        self.assertEqual(items[0]["website"], "https://www.abcobourse.com")
        self.assertEqual(items[1]["country"], "Côte d'Ivoire")
        self.assertEqual(items[1]["country_basis"], "indicatif_telephonique_publie")
        self.assertIsNone(items[1]["website"])
        self.assertEqual(items[0]["fees_status"], "non_publies_par_la_brvm")


class FundamentalsExtractionTests(unittest.TestCase):
    def test_classify_report_document(self):
        doc = classify_report_document(
            "https://www.brvm.org/sites/default/files/20260608_-_etats_financiers_approuves_-_exercice_2025_-_orange_ci.pdf"
        )
        self.assertEqual(doc["doc_type"], "etats_financiers_approuves")
        self.assertEqual(doc["exercice"], 2025)
        self.assertEqual(doc["published_date"], "2026-06-08")

    def test_detect_unit_variants(self):
        self.assertEqual(detect_unit("(en Milliards FCFA)")[0], 1_000_000_000)
        self.assertEqual(detect_unit("En milliers de FCFA")[0], 1_000)
        self.assertEqual(detect_unit("montants en FCFA")[0], 1)
        self.assertIsNone(detect_unit("aucune unité ici"))

    def test_note_reference_is_not_an_amount(self):
        line = "Chiffre d'affaires 4.1 1 197,1 1 084,1"
        self.assertEqual(first_amount_after(line, line.index("4.1")), 1197.1)

    def test_cluster_amounts_separates_columns(self):
        def word(text, x0, index):
            return {"text": text, "x0": x0, "x1": x0 + 18, "top": 0, "index": index}
        words = [
            word("250", 100, 0), word("000", 120, 1),   # même montant (écart 2)
            word("240", 180, 2), word("000", 200, 3),   # nouvelle colonne (écart 42)
        ]
        self.assertEqual(cluster_amounts(words), [(0, 250000.0), (2, 240000.0)])

    def test_extraction_with_cross_check_and_exclusions(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}
        pages = [
            {"text": "(en millions de FCFA)", "lines": [
                line("Chiffre d'affaires 250 000 240 000", [(2, 250000.0), (4, 240000.0)]),
                line("Résultat net de l'exercice 18 500 17 000", [(4, 18500.0), (6, 17000.0)]),
                line("Résultat net par action 320 300", [(4, 320.0)]),
            ]},
            {"text": "(en millions de FCFA)", "lines": [
                line("Total capitaux propres 95 000 90 000", [(3, 95000.0), (5, 90000.0)]),
                line("Capitaux propres attribuables aux participations ne donnant pas le contrôle 4 000", [(9, 4000.0)]),
                line("Total de l'actif 410 000 390 000", [(3, 410000.0), (5, 390000.0)]),
                line("Résultat net 18 500 17 000", [(2, 18500.0), (4, 17000.0)]),
            ]},
            {"text": "Page sans unité explicite", "lines": [
                line("Résultat net 999 999", [(2, 999999.0)]),
            ]},
        ]
        extracted = extract_figures_from_pages(pages)
        figures = extracted["courant"]
        self.assertEqual(figures["chiffre_affaires"]["value_fcfa"], 250_000_000_000)
        self.assertEqual(figures["resultat_net"]["value_fcfa"], 18_500_000_000)
        self.assertEqual(figures["resultat_net"]["confidence"], "recoupe_dans_le_document")
        self.assertEqual(figures["capitaux_propres"]["value_fcfa"], 95_000_000_000)
        self.assertEqual(figures["total_bilan"]["value_fcfa"], 410_000_000_000)
        # Colonne N-1 du même document : deuxième montant de chaque ligne.
        previous = extracted["precedent"]
        self.assertEqual(previous["chiffre_affaires"]["value_fcfa"], 240_000_000_000)
        self.assertEqual(previous["resultat_net"]["value_fcfa"], 17_000_000_000)


    def test_etats_syscohada_codes_sans_unite_explicite(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}
        income = {"text": "XB CHIFFRE D'AFFAIRES XI RÉSULTAT NET", "lines": [
            line("XB CHIFFRE D'AFFAIRES 10 000 000 000 9 000 000 000", [(3, 10_000_000_000.0), (7, 9_000_000_000.0)]),
            line("XI RÉSULTAT NET 800 000 000 700 000 000", [(3, 800_000_000.0), (6, 700_000_000.0)]),
        ]}
        balance = {"text": "CP TOTAL CAPITAUX PROPRES BZ TOTAL GÉNÉRAL DZ TOTAL GÉNÉRAL", "lines": [
            line("CP TOTAL CAPITAUX PROPRES ET RESSOURCES ASSIMILÉES (1 000 000 000) (900 000 000)", [(7, -1_000_000_000.0), (11, -900_000_000.0)]),
            line("BZ TOTAL GÉNÉRAL 15 000 000 000 2 000 000 000 13 000 000 000 12 000 000 000", [(3, 15_000_000_000.0), (7, 2_000_000_000.0), (11, 13_000_000_000.0), (15, 12_000_000_000.0)]),
            line("DZ TOTAL GÉNÉRAL 13 000 000 000 12 000 000 000", [(3, 13_000_000_000.0), (7, 12_000_000_000.0)]),
        ]}
        result = extract_figures_from_pages([income, balance])
        self.assertEqual(result["courant"]["chiffre_affaires"]["value_fcfa"], 10_000_000_000)
        self.assertEqual(result["courant"]["resultat_net"]["value_fcfa"], 800_000_000)
        self.assertEqual(result["courant"]["capitaux_propres"]["value_fcfa"], -1_000_000_000)
        self.assertEqual(result["courant"]["total_bilan"]["value_fcfa"], 13_000_000_000)
        self.assertIn("SYSCOHADA", result["courant"]["total_bilan"]["unit_label"])


    def test_plausibility_without_capitaux_propres(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}
        page = {"text": "XB CHIFFRE D'AFFAIRES XI RÉSULTAT NET", "lines": [
            line("XB CHIFFRE D'AFFAIRES 10 000 000 000 9 000 000 000", [(3, 10_000_000_000.0), (7, 9_000_000_000.0)]),
            line("XI RÉSULTAT NET 800 000 000 700 000 000", [(3, 800_000_000.0), (6, 700_000_000.0)]),
        ]}
        result = extract_figures_from_pages([page])
        self.assertEqual(result["courant"]["chiffre_affaires"]["value_fcfa"], 10_000_000_000)
        self.assertNotIn("capitaux_propres", result["courant"])


class DividendHistoryTests(unittest.TestCase):
    def test_multiple_notices_for_same_distribution_are_merged(self):
        rows = [
            {"issuer": "TOTAL", "fiscal_year": "2023", "payment_date": "2024-06-29", "ex_date": "2024-06-27", "net_amount_fcfa": 207.58, "notice_url": "https://example.test/avis-total.pdf", "source_rows_merged": 1},
            {"issuer": "TOTAL", "fiscal_year": "2023", "payment_date": "2024-06-28", "ex_date": "2024-06-26", "net_amount_fcfa": 207.58, "notice_url": "https://example.test/avis-total-rectificatif.pdf", "source_rows_merged": 1},
            {"issuer": "TOTAL", "fiscal_year": "2023", "payment_date": "2024-09-01", "ex_date": "2024-08-28", "net_amount_fcfa": 50, "notice_url": None, "source_rows_merged": 1},
        ]
        merged = deduplicate_dividend_rows(rows)
        self.assertEqual(len(merged), 2)
        self.assertIn("rectificatif", merged[0]["notice_url"])
        self.assertEqual(merged[0]["source_rows_merged"], 2)

    def test_dividend_table_historical_aliases_are_matched(self):
        companies = [{"ticker": "TTLC", "name": "TOTALENERGIES MARKETING CI", "sector": "Énergie"}]
        dividends = [{
            "issuer": "TOTAL", "fiscal_year": "2025", "payment_date": "2026-08-31",
            "ex_date": "2026-08-27", "net_amount_fcfa": 200, "notice_url": None,
        }]
        stats = compute_dividend_history(dividends, companies)
        self.assertEqual(stats["TTLC"]["paid_fiscal_years_count"], 1)

    def test_history_groups_payments_by_fiscal_year_without_inventing_zeros(self):
        companies = [
            {"ticker": "ORAC", "name": "ORANGE CI", "sector": "Télécommunications"},
            {"ticker": "ABCD", "name": "SOCIETE SANS LIGNE CI", "sector": "Autres"},
        ]
        dividends = []
        for year, amount in [(2021, 100), (2022, 110), (2023, 105), (2024, 120), (2025, 100), (2025, 25)]:
            dividends.append({
                "issuer": "ORANGE CI",
                "fiscal_year": str(year),
                "payment_date": f"{year + 1}-06-01",
                "ex_date": f"{year + 1}-05-20",
                "net_amount_fcfa": amount,
                "notice_url": None,
            })
        stats = compute_dividend_history(dividends, companies)
        self.assertEqual(stats["ORAC"]["paid_last_5_fiscal_years"], 5)
        self.assertEqual(stats["ORAC"]["current_consecutive_paid_years"], 5)
        self.assertEqual(stats["ORAC"]["latest_net_amount_fcfa"], 125)
        self.assertEqual(stats["ORAC"]["annual"][-1]["payments_count"], 2)
        self.assertEqual(stats["ABCD"]["status"], "non_documentee_dans_tableau_collecte")
        self.assertEqual(stats["ABCD"]["paid_fiscal_years_count"], 0)


class SeriesMergeTests(unittest.TestCase):
    def obs(self, exercice, key, value, doc, column=0):
        return {
            "exercice": exercice, "key": key, "value_fcfa": value, "doc_url": doc,
            "doc_label": doc, "column": column, "occurrences": 1, "unit_label": "en FCFA",
            "page": 3, "line": "ligne source", "evidence": [],
        }

    def test_confirmation_by_two_documents(self):
        observations = [
            self.obs(2025, "resultat_net", 20_000_000_000, "doc2025"),
            self.obs(2024, "resultat_net", 18_000_000_000, "doc2025", column=1),
            self.obs(2024, "resultat_net", 18_100_000_000, "doc2024"),
            self.obs(2024, "chiffre_affaires", 100_000_000_000, "doc2024"),
        ]
        series, notes = merge_series_observations(observations)
        self.assertEqual(series[2024]["resultat_net"]["confidence"], "confirme_deux_documents")
        self.assertEqual(series[2024]["resultat_net"]["documents_confirmants"], 2)
        self.assertEqual(series[2025]["resultat_net"]["confidence"], "extraction_unique")
        self.assertFalse(any("divergentes" in n for n in notes))

    def test_divergence_is_reported(self):
        observations = [
            self.obs(2024, "resultat_net", 18_000_000_000, "doc2025", column=1),
            self.obs(2024, "resultat_net", 25_000_000_000, "doc2024"),
            self.obs(2024, "resultat_net", 25_200_000_000, "doc2024b"),
        ]
        series, notes = merge_series_observations(observations)
        self.assertTrue(any("divergentes" in n for n in notes))
        self.assertGreater(series[2024]["resultat_net"]["value_fcfa"], 24_000_000_000)


if __name__ == "__main__":
    unittest.main()

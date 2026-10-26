import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))

import collect as collect_module  # noqa: E402
from collect import (  # noqa: E402
    ANNUAL_DOC_PRIORITY,
    _detect_page_column_order,
    _figures_share_perimeter,
    _is_calendar_date_amount,
    _merge_ocr_word_variants,
    _missing_capital_keys,
    _parse_tesseract_tsv,
    add_derived_financial_debt,
    boc_archive_history,
    build_calendar_events,
    build_eps_audit_matrix,
    build_issuer_variant_map,
    classify_eps_observation,
    classify_news,
    classify_report_document,
    cluster_amounts,
    compute_dividend_history,
    deduplicate_dividend_rows,
    detect_unit,
    detect_unit_from_legal_capital,
    detect_unit_from_subscribed_capital,
    derive_eps_metrics,
    extract_figures_from_pages,
    first_amount_after,
    line_amounts_after_label,
    looks_like_bank_publication_form,
    compute_history_stats,
    compute_long_history_stats,
    compute_market_structure,
    Empty_boc_archive,
    extract_bceao_cpm_indicators,
    enrich_dividend_sustainability,
    match_announcement_issuer,
    match_tickers_in_text,
    merge_boc_archive,
    merge_series_observations,
    parse_french_amount,
    _sgi_name_from_brvm_title,
    _sgi_names_match,
    _tariff_rubrique_key,
    brvm_decision_pdf_url,
    parse_announced_decision_number,
    extract_tariff_rates_from_lines,
    parse_richbourse_tariff_rows,
    parse_sgi_page,
    parse_tariff_decision_header,
    parse_tariff_rate_text,
    parse_umoa_emissions_page,
    parse_french_long_date,
    parse_number,
    parse_slash_date,
    series_hygiene,
    structured_lines_from_words,
    summarize_eps_audit_matrix,
    strip_tracking_params,
)
from eps_evidence import (  # noqa: E402
    adjust_per_share_to_reference_unit,
    assess_eps_arithmetic,
    classify_page_accounting_contexts,
    detect_column_years,
    detect_document_fiscal_year,
    detect_document_period,
    detect_share_count_changes,
    extract_numeric_tokens,
    extract_per_share_observations,
    load_verified_capital_events,
    select_published_eps_candidate,
    verify_document_issuer,
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
        # Libellé réduit au seul ticker (page de rapports BRVM « NSBC ») :
        self.assertEqual(match_announcement_issuer("SNTS", variants), ["SNTS"])
        self.assertEqual(match_announcement_issuer("BOAC", variants), ["BOAC"])
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
        sector_doc = classify_report_document(
            "https://www.brvm.org/sites/default/files/20230502_-_etats_financiers_par_secteur_syscohada_exercice_2022_-_cie_ci.pdf"
        )
        self.assertEqual(sector_doc["doc_type"], "etats_financiers_par_secteur")
        self.assertNotIn(sector_doc["doc_type"], ANNUAL_DOC_PRIORITY)

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
        # Bilan bancaire en FCFA entiers : deux colonnes de 12 chiffres
        # rapprochées (écart de colonne 5,5 pt contre 2,5 pt entre groupes
        # de milliers) ne doivent pas fusionner en un nombre de 24 chiffres.
        bank_words = [
            word("104", 100, 0), word("674", 120.5, 1), word("009", 141, 2), word("283", 161.5, 3),
            word("112", 185, 4), word("817", 205.5, 5), word("609", 226, 6), word("313", 246.5, 7),
        ]
        self.assertEqual(
            cluster_amounts(bank_words),
            [(0, 104674009283.0), (4, 112817609313.0)],
        )

    def test_amount_formats_long_integer_and_thousands_commas(self):
        def word(text, x0, index):
            return {"text": text, "x0": x0, "x1": x0 + 42, "top": 0, "index": index}
        words = [word("681606", 100, 0), word("659991", 180, 1)]
        self.assertEqual(cluster_amounts(words), [(0, 681606.0), (1, 659991.0)])
        fragmented = [
            word("6", 100, 0), word("99", 118, 1), word("537", 138, 2),
            word("654", 190, 3), word("345", 210, 4),
        ]
        self.assertEqual(cluster_amounts(fragmented), [(0, 699537.0), (3, 654345.0)])
        self.assertEqual(parse_french_amount("8,098,245,354"), 8098245354.0)
        self.assertEqual(parse_french_amount("1,5"), 1.5)

    def test_cluster_amounts_ignores_table_border_punctuation(self):
        def word(text, x0, index, width):
            return {"text": text, "x0": x0, "x1": x0 + width, "top": 0, "index": index}

        words = [
            word("541451190619]", 300, 5, 90),
            word("593455", 430, 6, 48),
            word("473", 480, 7, 24),
            word("338", 506, 8, 24),
        ]
        self.assertEqual(
            cluster_amounts(words),
            [(5, 541451190619.0), (6, 593455473338.0)],
        )
        bracketed = [word("[541491", 300, 0, 55), word("[593455", 390, 1, 55)]
        self.assertEqual(cluster_amounts(bracketed), [(0, 541491.0), (1, 593455.0)])
        self.assertEqual(parse_french_amount("560353600080!"), 560353600080.0)

    def test_cached_line_recovers_punctuated_standalone_amount(self):
        text = "ET PASSIF] TOTAL DU PASSIF 541451190619] 593455 473 338"
        line = {
            "text": text,
            "words": text.split(),
            # Forme sérialisée d'un ancien cache OCR : le premier total avait
            # disparu du regroupement à cause du crochet final.
            "amounts": [[6, 593455473338.0]],
        }
        self.assertEqual(
            line_amounts_after_label(line, text.index("541451")),
            [541451190619.0, 593455473338.0],
        )

        ambiguous_text = "TOTAL [541491 190 619"
        ambiguous_line = {
            "text": ambiguous_text,
            "words": ambiguous_text.split(),
            "amounts": [[2, 190619.0]],
        }
        # Sans coordonnées, « 541491 » pourrait être le début du montant
        # fragmenté suivant : on ne crée pas de colonne supplémentaire.
        self.assertEqual(
            line_amounts_after_label(ambiguous_line, ambiguous_text.index("[")),
            [190619.0],
        )

        # Une date en toutes lettres ne produit aucun montant, alors qu'un
        # vrai montant de 2 024 dans un tableau reste lu.
        date_text = "Le total du bilan de SOPARFI au 31 décembre 2024"
        date_line = {
            "text": date_text,
            "words": date_text.split(),
            "amounts": [[7, 31.0], [9, 2024.0]],
        }
        self.assertEqual(
            line_amounts_after_label(date_line, date_text.index("de SOPARFI")),
            [],
        )
        amount_text = "Résultat net 2 024 1 900"
        amount_line = {
            "text": amount_text,
            "words": amount_text.split(),
            "amounts": [[2, 2024.0], [4, 1900.0]],
        }
        self.assertEqual(
            line_amounts_after_label(amount_line, amount_text.index(" 2 024")),
            [2024.0, 1900.0],
        )

    def test_extraction_flux_dette_tresorerie_eps_et_actions(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}
        pages = [
            {"text": "(en millions de FCFA)", "lines": [
                line("Chiffre d'affaires 250 000 240 000", [(2, 250000.0), (4, 240000.0)]),
                line("Résultat net de l'exercice 18 500 17 000", [(4, 18500.0), (6, 17000.0)]),
                line("Résultat net par action (de base et dilué) 12 185 170", [(8, 12.0), (9, 185.0), (10, 170.0)]),
                line("Nombre d'actions en circulation 100 000 000 100 000 000", [(4, 100000000.0), (7, 100000000.0)]),
                line("Trésorerie générée par les activités d'exploitation (a) 30 000 25 000", [(8, 30000.0), (10, 25000.0)]),
                line("Acquisitions d'immobilisations corporelles et incorporelles (8 000) (7 000)", [(5, -8000.0), (7, -7000.0)]),
                line("Dividendes versés - (4 000)", [(3, -4000.0)]),
            ]},
            {"text": "(en millions de FCFA)", "lines": [
                line("Total capitaux propres 95 000 90 000", [(3, 95000.0), (5, 90000.0)]),
                line("Total de l'actif 410 000 390 000", [(3, 410000.0), (5, 390000.0)]),
                line("Trésorerie et équivalents de trésorerie 11 12 000 10 000", [(5, 11.0), (6, 12000.0), (8, 10000.0)]),
                line("Passifs financiers non courants 40 000 38 000", [(4, 40000.0), (6, 38000.0)]),
                line("Passifs financiers courants 15 000 14 000", [(3, 15000.0), (5, 14000.0)]),
                line("Disponibilités et quasi-disponibilités à l'ouverture 10 000 9 000", [(5, 10000.0), (7, 9000.0)]),
            ]},
        ]
        extracted = extract_figures_from_pages(pages)
        figures = extracted["courant"]
        self.assertEqual(figures["flux_tresorerie_operationnel"]["value_fcfa"], 30_000_000_000)
        self.assertEqual(figures["investissements_immobilisations"]["value_fcfa"], -8_000_000_000)
        self.assertNotIn("dividendes_verses", figures)  # tiret = colonne N vide
        self.assertEqual(extracted["precedent"]["dividendes_verses"]["value_fcfa"], -4_000_000_000)
        self.assertEqual(figures["tresorerie_equivalents"]["value_fcfa"], 12_000_000_000)
        self.assertEqual(figures["dettes_financieres_non_courantes"]["value_fcfa"], 40_000_000_000)
        self.assertEqual(figures["dettes_financieres_courantes"]["value_fcfa"], 15_000_000_000)
        figures, notes = add_derived_financial_debt(figures)
        self.assertEqual(notes, [])
        self.assertEqual(figures["dettes_financieres"]["value_fcfa"], 55_000_000_000)
        self.assertTrue(figures["dettes_financieres"]["derived"])
        # Le BPA et le nombre d'actions ne sont jamais multipliés par
        # l'unité « millions de FCFA » du tableau.
        self.assertEqual(figures["benefice_par_action"]["value"], 185.0)
        self.assertEqual(figures["benefice_par_action"]["value_kind"], "fcfa_par_action")
        self.assertNotIn("value_fcfa", figures["benefice_par_action"])
        self.assertEqual(figures["nombre_actions_fin_exercice"]["value"], 100_000_000)
        self.assertEqual(figures["nombre_actions_fin_exercice"]["value_kind"], "actions")

    def test_eps_heading_with_base_subline(self):
        # Présentation mesurée sur les états financiers SNTS 2025 (p. 20) :
        # libellé BPA seul sur sa ligne, montants sur la sous-ligne
        # « - de base » suivante ; la ligne « - dilué » ne doit jamais être lue.
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        page = {
            "text": "(en millions de FCFA)",
            "lines": [
                line("Résultat net par actions attribuable aux propriétaires de la maison mère", []),
                line("- de base 3420 3288", [(3, 3420.0), (4, 3288.0)]),
                line("- dilué 9999 8888", [(2, 9999.0), (3, 8888.0)]),
                line("Résultat net de base par action 185 170", [(6, 185.0), (7, 170.0)]),
            ],
        }
        extracted = extract_figures_from_pages([page])
        # Deux lectures « de base » concordantes en structure : la valeur
        # agrégée doit venir des lignes de base, jamais des 9999/8888 dilués,
        # et n'est jamais multipliée par l'unité « millions » du tableau.
        courant = extracted["courant"]["benefice_par_action"]
        precedent = extracted["precedent"]["benefice_par_action"]
        self.assertIn(courant["value"], (3420.0, 185.0))
        self.assertIn(precedent["value"], (3288.0, 170.0))
        self.assertEqual(courant["value_kind"], "fcfa_par_action")
        self.assertTrue(
            any("- de base" in (ev.get("line") or "") for ev in courant.get("evidence", []))
            or "- de base" in (courant.get("line") or "")
            or any("de base" in (ev.get("line") or "") for ev in courant.get("evidence", []))
        )

    def test_semantic_exclusions_for_equity_and_cash_formulas(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        page = {
            "text": "(en millions de FCFA)",
            "lines": [
                line("Total capitaux propres 95 000 90 000", [(3, 95000.0), (5, 90000.0)]),
                line("Capitaux propres hors résultat 29 818 28 000", [(4, 29818.0), (6, 28000.0)]),
                line(
                    "ux de trésorerie provenant du financement par les capitaux propres 4 160 500",
                    [(10, 4160.0), (12, 500.0)],
                ),
                line("Total de l'actif 410 000 390 000", [(3, 410000.0), (5, 390000.0)]),
                line("Trésorerie et équivalents de trésorerie 12 000 10 000", [(5, 12000.0), (7, 10000.0)]),
                line(
                    "Contrôle Trésorerie Actif N - Trésorerie passif N 47 259 62 271",
                    [(8, 47259.0), (10, 62271.0)],
                ),
            ],
        }
        extracted = extract_figures_from_pages([page])
        self.assertEqual(extracted["courant"]["capitaux_propres"]["value_fcfa"], 95_000_000_000)
        self.assertEqual(extracted["courant"]["tresorerie_equivalents"]["value_fcfa"], 12_000_000_000)

        # Le calcul prudentiel des fonds propres effectifs ne doit pas
        # fournir le résultat net : son « résultat de l'exercice » est une
        # fraction éligible/conservée, inférieure au résultat du bilan.
        prudential_pages = [
            {
                "text": "(en millions de FCFA)",
                "lines": [
                    line("10 PRODUIT NET BANCAIRE 23 447 24 254", [(4, 23447.0), (6, 24254.0)]),
                    line("16 RESULTAT DE L'EXERCICE 8 502 7 421", [(4, 8502.0), (6, 7421.0)]),
                ],
            },
            {
                "text": (
                    "(en millions de FCFA) Dispositif prudentiel Les fonds propres "
                    "effectifs de la banque sont déterminés comme suit"
                ),
                "lines": [
                    line("- Résultat de l'exercice 1 415", [(4, 1415.0)]),
                ],
            },
        ]
        prudential = extract_figures_from_pages(prudential_pages)
        self.assertEqual(prudential["courant"]["resultat_net"]["value_fcfa"], 8_502_000_000)

        variation_page = {
            "text": "(en millions de FCFA) VARIATION DES CAPITAUX PROPRES",
            "lines": [
                line("VARIATION DES CAPITAUX PROPRES", []),
                line(
                    "CAPITAUX PROPRES AU 20 000 675 69 968",
                    [(3, 20000.0), (5, 675.0), (6, 69968.0)],
                ),
            ],
        }
        variation = extract_figures_from_pages([variation_page])
        self.assertNotIn("capitaux_propres", variation["courant"])
        self.assertNotIn("capitaux_propres", variation["precedent"])

    def test_bare_year_after_exercice_is_not_an_amount(self):
        # Phrases de rapport de gestion : l'année qui suit « de
        # l'exercice » n'est pas un montant (faux résultat net constaté
        # sur Ecobank CI et SOGB).
        words = "Le résultat net de l'exercice 2025 s'établit à milliards".split()
        self.assertTrue(_is_calendar_date_amount(words, 5, 2025))
        words = "77% du résultat net de l’exercice 2025 et".split()
        self.assertTrue(_is_calendar_date_amount(words, 6, 2025))
        # Année accolée au libellé dans un tableau de variation.
        words = "Résultat net 2023 - - - 1".split()
        self.assertTrue(_is_calendar_date_amount(words, 2, 2023))
        # Vrai montant nu égal à une année, suivi de la colonne N-1.
        words = "Résultat net de l'exercice 2025 1980".split()
        self.assertFalse(_is_calendar_date_amount(words, 4, 2025))
        # Montant en groupes de milliers : le premier token n'est pas l'année.
        words = "Résultat net 2 025 1 980".split()
        self.assertFalse(_is_calendar_date_amount(words, 2, 2025))

    def test_column_order_from_french_abbreviated_dates(self):
        # En-têtes IFRS « 31-déc-23 31-déc-22 » (Servair Abidjan) : preuve
        # locale descendante, qui prime sur le consensus du document.
        page = {
            "text": "",
            "lines": [{"text": "ACTIF (en millions de FCFA) Note 31-déc-23 31-déc-22", "words": [], "amounts": []}],
        }
        self.assertIs(_detect_page_column_order(page), False)
        page_ascending = {
            "text": "",
            "lines": [{"text": "31-déc-2022 31-déc-2023", "words": [], "amounts": []}],
        }
        self.assertIs(_detect_page_column_order(page_ascending), True)

    def test_column_order_from_month_year_and_bare_year_headers(self):
        def page_with(header):
            return {"text": "", "lines": [{"text": header, "words": [], "amounts": []}]}

        # Rapport d'activité bancaire : « Déc N-1 Déc N » (Ecobank CI).
        self.assertIs(_detect_page_column_order(page_with("Déc 2024 Déc 2025")), True)
        self.assertIs(
            _detect_page_column_order(page_with("(en millions de FCFA) Déc 2025 Déc 2024 (%) Valeur")),
            False,
        )
        # Synthèse à années nues, deux tableaux côte à côte (Solibra).
        self.assertIs(
            _detect_page_column_order(
                page_with("(en millions de FCFA) 2024 2025 (en millions de FCFA) 2024 2025")
            ),
            True,
        )
        # « Variation Déc N / Déc N-1 » est un ratio, pas un en-tête :
        # seule la ligne suivante prouve l'ordre (Ecobank CI).
        variation_then_header = {
            "text": "",
            "lines": [
                {"text": "Variation Déc 2025 / Déc 2024", "words": [], "amounts": []},
                {"text": "(en millions de FCFA) Déc 2024 Déc 2025 (%) Valeur", "words": [], "amounts": []},
            ],
        }
        self.assertIs(_detect_page_column_order(variation_then_header), True)
        self.assertIsNone(_detect_page_column_order(page_with("Variation Déc 2025 / Déc 2024")))
        # Une phrase de commentaire n'est pas un en-tête.
        self.assertIsNone(
            _detect_page_column_order(
                page_with(
                    "La croissance reste solide entre 2024 et 2025 grâce aux volumes "
                    "vendus sur le marché régional"
                )
            )
        )

    def test_classify_interim_financial_statements_excluded_from_annual(self):
        doc = classify_report_document(
            "https://www.brvm.org/sites/default/files/20260831_-_rapport_dexamen_limite_des_cac_"
            "sur_les_etats_financiers_au_30_juin_2026_-_coris_bank_international_bf.pdf"
        )
        self.assertEqual(doc["doc_type"], "etats_financiers_intermediaires")
        self.assertNotIn(doc["doc_type"], ANNUAL_DOC_PRIORITY)

    def test_equity_total_before_variation_table_on_same_page_is_kept(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        page = {
            "text": "(en millions de FCFA)",
            "lines": [
                line("Total des capitaux propres 43 024 40 037", [(4, 43024.0), (6, 40037.0)]),
                line("Total de l'actif 579 552 563 746", [(3, 579552.0), (5, 563746.0)]),
                line("TABLEAU DE VARIATION DES CAPITAUX PROPRES", []),
                line("CAPITAUX PROPRES AU 20 000 675 69 968", [(3, 20000.0), (5, 675.0), (6, 69968.0)]),
            ],
        }
        extracted = extract_figures_from_pages([page])
        self.assertEqual(extracted["courant"]["capitaux_propres"]["value_fcfa"], 43_024_000_000)
        self.assertEqual(extracted["precedent"]["capitaux_propres"]["value_fcfa"], 40_037_000_000)

    def test_series_hygiene_scale_break_uses_other_years_as_reference(self):
        def entry(year, total):
            return {
                "exercice": year,
                "figures": {
                    "total_bilan": {
                        "value_fcfa": total,
                        "value": total,
                        "confidence": "extraction_unique",
                    }
                },
            }

        # Le total 2021 a absorbé un chiffre parasite (×10) : à confiance
        # égale, les exercices 2020 et 2025 donnent l'échelle de référence
        # et c'est 2021 qui doit être écarté, pas 2020.
        cleaned, notes = series_hygiene([
            entry(2025, 4_000_527_655),
            entry(2021, 41_642_766_935),
            entry(2020, 4_087_383_518),
        ])
        by_year = {e["exercice"]: e["figures"] for e in cleaned}
        self.assertIn("total_bilan", by_year[2020])
        self.assertNotIn(2021, by_year)
        self.assertIn("total_bilan", by_year[2025])
        self.assertTrue(any("2021" in note for note in notes))

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


    def test_parse_tesseract_tsv_scales_coordinates_and_cleans_words(self):
        import tempfile

        tsv = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t100\t200\t300\t40\t91.5\tTrésorerie\n"
            "5\t1\t1\t1\t1\t2\t450\t200\t120\t40\t-1\tignore\n"
            "5\t1\t1\t1\t1\t3\t600\t200\t180\t40\t88\t|541491\n"
            "5\t1\t1\t1\t1\t4\t800\t200\t20\t40\t90\t|\n"
            "5\t1\t1\t1\t2\t1\t100\t300\t2000\t40\t90\tTOTAL\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.tsv"
            path.write_text(tsv, encoding="utf-8")
            words = _parse_tesseract_tsv(path)
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0]["text"], "Trésorerie")
        self.assertAlmostEqual(words[0]["x0"], 24.0)
        self.assertAlmostEqual(words[0]["top"], 48.0)
        self.assertEqual(words[0]["conf"], 91.5)
        self.assertEqual(words[1]["text"], "541491")
        self.assertAlmostEqual(words[1]["x0"], 144.0)

    def test_ocr_line_grouping_tolerates_skewed_scan(self):
        words = [
            {"text": "TOTAL", "x0": 100, "x1": 140, "top": 100, "bottom": 108, "conf": 95},
            {"text": "DE", "x0": 145, "x1": 160, "top": 100.5, "bottom": 108.5, "conf": 94},
            {"text": "L'ACTIF", "x0": 165, "x1": 210, "top": 101, "bottom": 109, "conf": 94},
            {"text": "783173", "x0": 500, "x1": 545, "top": 106, "bottom": 114, "conf": 94},
            {"text": "836158", "x0": 590, "x1": 635, "top": 106.5, "bottom": 114.5, "conf": 90},
        ]
        lines = structured_lines_from_words(words)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["text"], "TOTAL DE L'ACTIF 783173 836158")

        native_words = [{key: value for key, value in word.items() if key != "conf"} for word in words]
        self.assertGreater(len(structured_lines_from_words(native_words)), 1)

    def test_merge_ocr_variants_recovers_white_on_dark_total_line(self):
        primary = [
            {"text": "BILAN", "x0": 10, "x1": 50, "top": 10, "bottom": 20, "conf": 95},
        ]
        secondary = [
            {"text": "TOTAL", "x0": 250, "x1": 285, "top": 100, "bottom": 110, "conf": 95},
            {"text": "DE", "x0": 290, "x1": 305, "top": 100, "bottom": 110, "conf": 91},
            {"text": "L'ACTIF", "x0": 310, "x1": 350, "top": 100, "bottom": 110, "conf": 90},
            {"text": "783173", "x0": 500, "x1": 540, "top": 100, "bottom": 110, "conf": 94},
            {"text": "836158", "x0": 590, "x1": 630, "top": 100, "bottom": 110, "conf": 82},
        ]
        lines = structured_lines_from_words(_merge_ocr_word_variants(primary, secondary))
        total_line = next(line for line in lines if "TOTAL" in line["text"])
        self.assertEqual(total_line["text"], "TOTAL DE L'ACTIF 783173 836158")
        self.assertGreaterEqual(total_line["ocr_mean_confidence"], 82)

    def test_merge_ocr_variants_flags_conflicting_numeric_reading(self):
        primary = [
            {"text": "541491190619", "x0": 500, "x1": 580, "top": 100, "bottom": 112, "conf": 15.7},
        ]
        secondary = [
            {"text": "541451190619", "x0": 499, "x1": 581, "top": 99, "bottom": 113, "conf": 57.5},
        ]
        merged = _merge_ocr_word_variants(primary, secondary)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["text"], "541491190619")
        self.assertEqual(merged[0]["conf"], 0.0)
        self.assertTrue(merged[0]["ocr_variant_conflict"])

    def test_ocr_ascending_columns_legal_capital_unit_and_provenance(self):
        def line(text, amounts, confidence=95.0):
            words = text.split()
            return {
                "text": text,
                "words": words,
                "amounts": amounts,
                "word_confidences": [confidence] * len(words),
                "ocr_mean_confidence": confidence,
                "ocr_min_confidence": confidence,
            }

        balance = {
            "text": "",
            "page_number": 1,
            "extraction_method": "ocr_controle",
            "lines": [
                line("POSTE ACTIF 31/12/2024 31/12/2025", []),
                line("Capital souscrit 36 000 36 000", [(2, 36000.0), (4, 36000.0)]),
                line("Capitaux propres et ressources assimilées 88 621 96 526", [(5, 88621.0), (7, 96526.0)]),
                line("TOTAL DE L'ACTIF 783173 836158", [(3, 783173.0), (4, 836158.0)]),
                line("Société Anonyme au Capital de 36 000 000 000 F CFA", []),
            ],
        }
        income = {
            "text": "",
            "page_number": 4,
            "extraction_method": "ocr_controle",
            "lines": [
                # Date d'en-tête corrompue par l'OCR sur cette page : le
                # consensus prouvé par la page de bilan doit s'appliquer.
                line("POSTE PRODUITS CHARGES 31/12/2024 34/12/2026", []),
                line("PRODUIT NET BANCAIRE 49 666 54 926", [(3, 49666.0), (5, 54926.0)]),
                line("RESULTAT NET 19 984 21 905", [(2, 19984.0), (4, 21905.0)]),
            ],
        }
        self.assertEqual(detect_unit_from_legal_capital([balance, income])[0], 1_000_000)
        extracted = extract_figures_from_pages([balance, income])
        current = extracted["courant"]
        previous = extracted["precedent"]
        self.assertEqual(current["total_bilan"]["value_fcfa"], 836_158_000_000)
        self.assertEqual(previous["total_bilan"]["value_fcfa"], 783_173_000_000)
        self.assertEqual(current["produit_net_bancaire"]["value_fcfa"], 54_926_000_000)
        self.assertEqual(current["resultat_net"]["value_fcfa"], 21_905_000_000)
        self.assertEqual(current["total_bilan"]["extraction_method"], "ocr_controle")
        self.assertEqual(current["total_bilan"]["ocr_confidence"], 95.0)
        self.assertIn("capital légal", current["total_bilan"]["unit_label"])

    def test_total_bilan_conflict_is_cross_checked_with_equity(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        page = {
            "text": "(en millions de FCFA)",
            "lines": [
                line("Total capitaux propres 76 637 64 615", [(3, 76637.0), (5, 64615.0)]),
                # Chiffre inséré dans le total du passif : 7 158 148 au lieu de 758 148.
                line("Total du passif 7158148 696306", [(3, 7158148.0), (4, 696306.0)]),
                line("Total de l'actif 758148 696306", [(3, 758148.0), (4, 696306.0)]),
            ],
        }
        extracted = extract_figures_from_pages([page])
        self.assertEqual(extracted["courant"]["total_bilan"]["value_fcfa"], 758_148_000_000)
        self.assertEqual(extracted["courant"]["capitaux_propres"]["value_fcfa"], 76_637_000_000)
        self.assertEqual(extracted["precedent"]["total_bilan"]["value_fcfa"], 696_306_000_000)

    def test_ocr_low_confidence_line_and_amount_are_rejected(self):
        def line(text, amounts, mean_confidence, word_confidences):
            return {
                "text": text,
                "words": text.split(),
                "amounts": amounts,
                "word_confidences": word_confidences,
                "ocr_mean_confidence": mean_confidence,
            }

        page = {
            "text": "(en millions de FCFA)",
            "extraction_method": "ocr_controle",
            "lines": [
                line(
                    "Résultat net 18 500 17 000",
                    [(2, 18500.0), (4, 17000.0)],
                    40.0,
                    [40.0, 40.0, 95.0, 95.0, 95.0, 95.0],
                ),
                line(
                    "Chiffre d'affaires 250 000 240 000",
                    [(2, 250000.0), (4, 240000.0)],
                    90.0,
                    [95.0, 95.0, 10.0, 95.0, 95.0, 95.0],
                ),
            ],
        }
        extracted = extract_figures_from_pages([page])
        self.assertNotIn("resultat_net", extracted["courant"])
        self.assertNotIn("chiffre_affaires", extracted["courant"])
        # Le premier montant fragile devient un vide : le second reste dans
        # la colonne précédente et n'est pas décalé vers l'exercice courant.
        self.assertEqual(
            extracted["precedent"]["chiffre_affaires"]["value_fcfa"],
            240_000_000_000,
        )

    def test_ocr_rejected_first_amount_does_not_shift_ascending_columns(self):
        def line(text, amounts, confidences):
            return {
                "text": text,
                "words": text.split(),
                "amounts": amounts,
                "word_confidences": confidences,
                "ocr_mean_confidence": sum(confidences) / len(confidences),
            }

        page = {
            "text": "(en FCFA)",
            "page_number": 2,
            "extraction_method": "ocr_controle",
            "lines": [
                line("POSTE PASSIF 31/12/2024 31/12/2025", [], [95.0] * 5),
                line(
                    "TOTAL DU PASSIF 541491190619 593455473338",
                    [(3, 541491190619.0), (4, 593455473338.0)],
                    [95.0, 95.0, 95.0, 15.0, 95.0],
                ),
                line(
                    "Capitaux propres et ressources assimilées 46195155867 49820422180",
                    [(5, 46195155867.0), (6, 49820422180.0)],
                    [95.0] * 7,
                ),
            ],
        }
        extracted = extract_figures_from_pages([page])
        self.assertEqual(extracted["courant"]["total_bilan"]["value_fcfa"], 593_455_473_338)
        self.assertNotIn("total_bilan", extracted["precedent"])
        self.assertEqual(
            extracted["precedent"]["capitaux_propres"]["value_fcfa"],
            46_195_155_867,
        )

    def test_capital_supplement_requires_same_accounting_perimeter(self):
        def fig(value):
            return {"value_fcfa": value, "value": value}

        primary = {
            "resultat_net": fig(18_500_000_000),
            "capitaux_propres": fig(95_000_000_000),
            "total_bilan": fig(410_000_000_000),
        }
        same_perimeter = {
            "resultat_net": fig(18_600_000_000),
            "capitaux_propres": fig(95_400_000_000),
            "total_bilan": fig(411_000_000_000),
            "benefice_par_action": {"value": 185.0},
        }
        other_perimeter = {
            "resultat_net": fig(22_000_000_000),
            "capitaux_propres": fig(130_000_000_000),
            "total_bilan": fig(500_000_000_000),
        }
        self.assertTrue(_figures_share_perimeter(primary, same_perimeter))
        self.assertFalse(_figures_share_perimeter(primary, other_perimeter))
        self.assertFalse(_figures_share_perimeter(primary, {"benefice_par_action": {"value": 185.0}}))
        self.assertEqual(
            _missing_capital_keys(primary),
            [
                "resultat_net_attribuable_ordinaires",
                "benefice_par_action",
                "nombre_actions_fin_exercice",
                "nombre_actions_moyen_pondere",
            ],
        )

    def test_eps_numerator_is_extracted_separately_from_total_net_income(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        page = {
            "text": "(en millions de FCFA)",
            "lines": [
                line(
                    "Résultat net attribuable aux actionnaires ordinaires 18 500 17 000",
                    [(8, 18500.0), (10, 17000.0)],
                ),
                line(
                    "Nombre moyen pondéré d'actions ordinaires 100 000 000 100 000 000",
                    [(7, 100000000.0), (10, 100000000.0)],
                ),
            ],
        }
        extracted = extract_figures_from_pages([page])
        courant = extracted["courant"]
        self.assertEqual(
            courant["resultat_net_attribuable_ordinaires"]["value_fcfa"],
            18_500_000_000,
        )
        self.assertNotIn("resultat_net", courant)
        self.assertEqual(
            courant["nombre_actions_moyen_pondere"]["value"],
            100_000_000,
        )

    def test_eps_levels_and_absent_statuses_are_not_merged(self):
        def fig(value, confirmed=False):
            return {
                "value": value,
                "value_fcfa": value,
                "documents_confirmants": 2 if confirmed else 1,
                "confidence": "confirme_deux_documents" if confirmed else "extraction_unique",
            }

        comparable = derive_eps_metrics(
            {
                "resultat_net_attribuable_ordinaires": fig(18_500_000_000, confirmed=True),
                "nombre_actions_moyen_pondere": fig(100_000_000, confirmed=True),
            }
        )
        self.assertEqual(comparable["status"], "RECALCULE_COMPARABLE_CONFIRME_DEUX_DOCUMENTS")
        self.assertEqual(comparable["recalculated_comparable_eps_fcfa"], 185.0)

        parent_only = derive_eps_metrics(
            {
                "resultat_net_part_groupe": fig(18_500_000_000),
                "nombre_actions_moyen_pondere": fig(100_000_000),
            }
        )
        self.assertEqual(parent_only["status"], "RECALCULE_PART_GROUPE_PONDEREE_A_VERIFIER")
        self.assertIsNone(parent_only["recalculated_comparable_eps_fcfa"])

        indicative = derive_eps_metrics(
            {
                "resultat_net": fig(18_500_000_000),
                "nombre_actions_fin_exercice": fig(125_000_000),
            },
            previous_figures={"nombre_actions_fin_exercice": fig(100_000_000)},
        )
        self.assertEqual(indicative["status"], "RATIO_INDICATIF_FIN_EXERCICE")
        self.assertEqual(indicative["indicative_result_per_end_share_fcfa"], 148.0)
        self.assertIn(
            "CHANGEMENT_DU_NOMBRE_D_ACTIONS_EN_FIN_EXERCICE",
            indicative["capital_structure_flags"],
        )

        self.assertEqual(classify_eps_observation({})["status"], "NON_RECHERCHE")
        self.assertEqual(
            classify_eps_observation({}, audit_completed=True, searched_documents=2)["status"],
            "NON_PUBLIE_DANS_SOURCES_VERIFIEES",
        )
        self.assertEqual(
            classify_eps_observation(
                {}, audit_completed=True, candidate_documents=1, candidate_unreadable=True
            )["status"],
            "ILLISIBLE",
        )
        self.assertEqual(
            classify_eps_observation({}, audit_completed=True, candidate_documents=0)["status"],
            "DOCUMENT_INTROUVABLE",
        )
        self.assertEqual(
            classify_eps_observation({}, not_applicable=True)["status"],
            "NON_APPLICABLE",
        )

    def test_initial_eps_audit_matrix_never_infers_unpublished(self):
        companies = [
            {
                "ticker": "TEST",
                "name": "Test SA",
                "sector": "Industrie",
                "documents": [
                    {
                        "doc_type": "etats_financiers",
                        "exercice": 2025,
                        "label": "Etats financiers 2025",
                        "url": "https://example.test/etats-2025.pdf",
                    }
                ],
                "fundamentals": {"series": []},
            }
        ]
        rows = build_eps_audit_matrix(
            companies,
            [{"label": "TEST", "url": "https://example.test/rapports/test"}],
        )
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["statut_bpa"] == "NON_RECHERCHE" for row in rows))
        self.assertEqual(summarize_eps_audit_matrix(rows)["cellules_brutes"], 10)

    def test_legal_capital_unit_is_not_guessed_when_ratio_does_not_match(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        page = {
            "text": "",
            "lines": [
                line("Capital souscrit 37 000 37 000", [(2, 37000.0), (4, 37000.0)]),
                line("Société Anonyme au Capital de 36 000 000 000 F CFA", []),
            ],
        }
        self.assertIsNone(detect_unit_from_legal_capital([page]))

    def test_bank_publication_form_amounts_are_whole_fcfa(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        page = {
            "text": "BILAN destiné à publication ETAT: MALI ETABLISSEMENT: BANQUE SA Date d'arrêté MONTANTS NETS",
            "lines": [
                line("POSTE PASSIF 31/12/2024 31/12/2025", []),
                line(
                    "9 CAPITAUX PROPRES ET RESSOURCES ASSIMILEES 46 195 155 867 49 820 422 180",
                    [(6, 46_195_155_867.0), (10, 49_820_422_180.0)],
                ),
                line(
                    "TOTAL DU PASSIF 541 491 190 619 593 455 473 338",
                    [(3, 541_491_190_619.0), (7, 593_455_473_338.0)],
                ),
                line(
                    "16 RESULTAT DE L'EXERCICE 9 123 471 904 11 081 189 907",
                    [(4, 9_123_471_904.0), (8, 11_081_189_907.0)],
                ),
                line(
                    "RESULTAT DE L'EXERCICE AVANT IMPOT 12 000 000 000 13 000 000 000",
                    [(5, 12_000_000_000.0), (9, 13_000_000_000.0)],
                ),
            ],
        }
        extracted = extract_figures_from_pages([page])
        self.assertEqual(extracted["courant"]["capitaux_propres"]["value_fcfa"], 49_820_422_180)
        self.assertEqual(extracted["courant"]["total_bilan"]["value_fcfa"], 593_455_473_338)
        self.assertEqual(extracted["courant"]["resultat_net"]["value_fcfa"], 11_081_189_907)
        self.assertEqual(extracted["precedent"]["resultat_net"]["value_fcfa"], 9_123_471_904)
        self.assertIn("destiné à publication", extracted["courant"]["total_bilan"]["unit_label"])

    def test_bank_publication_form_la_variant_and_document_inheritance(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        income = {
            "text": "COMPTE DE RESULTAT Destiné à la publication Date d'arrêté POSTE PRODUITS/CHARGES MONTANT NETS",
            "lines": [
                line("POSTE PRODUITS CHARGES 31/12/2024 31/12/2025", []),
                line(
                    "10 PRODUIT NET BANCAIRE 57 489 834 311 57 819 599 384",
                    [(4, 57_489_834_311.0), (8, 57_819_599_384.0)],
                ),
            ],
        }
        liabilities = {
            "text": "BILAN Destiné à la publication Date d'arrêté POSTE PASSIF",
            "lines": [
                line("POSTE PASSIF 31/12/2024 31/12/2025", []),
                line("1 BANQUES CENTRALES CCP 56 318 651 91 708 282", [(4, 56_318_651.0), (7, 91_708_282.0)]),
                line(
                    "3 DETTES A L'EGARD DE LA CLIENTELE 813 312 765 906 877 821 961 416",
                    [(7, 813_312_765_906.0), (11, 877_821_961_416.0)],
                ),
                line("9 CAPITAUX PROPRES ET RESSOURCES ASSIMILLEES", []),
            ],
        }
        assets = {
            "text": "BILAN Destiné à la publication Date d'arrêté POSTE ACTIF",
            "lines": [
                line("POSTE ACTIF 31/12/2024 31/12/2025", []),
                line(
                    "TOTALDEL'ACTIF 1 079 053 439 829 1 148 674 652 683",
                    [(1, 1_079_053_439_829.0), (6, 1_148_674_652_683.0)],
                ),
            ],
        }
        self.assertTrue(looks_like_bank_publication_form(income))
        self.assertTrue(looks_like_bank_publication_form(liabilities))
        self.assertFalse(looks_like_bank_publication_form(assets))
        extracted = extract_figures_from_pages([income, liabilities, assets])
        self.assertEqual(extracted["courant"]["produit_net_bancaire"]["value_fcfa"], 57_819_599_384)
        self.assertEqual(extracted["courant"]["total_bilan"]["value_fcfa"], 1_148_674_652_683)
        self.assertEqual(extracted["precedent"]["total_bilan"]["value_fcfa"], 1_079_053_439_829)

    def test_bank_form_layout_fallback_columns_previous_then_current(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        balance = {
            "text": "(en millions de FCFA) BILAN destiné à la publication ETAT NIGER ETABLISSEMENT BANK OF AFRICA",
            "lines": [
                line("BILAN destiné à la publication ETAT NIGER ETABLISSEMENT BANK OF AFRICA", []),
                line(
                    "9 CAPITAUX PROPRES ET RESSOURCES ASSIMILEES 42 156 36 064",
                    [(6, 42156.0), (8, 36064.0)],
                ),
                line("16 RESULTAT DE L'EXERCICE 5 002 409", [(4, 5002.0), (6, 409.0)]),
                line("TOTAL DU PASSIF 322 404 291 750", [(3, 322404.0), (5, 291750.0)]),
            ],
        }
        income = {
            "text": "(en millions de FCFA) COMPTE DE RESULTAT destiné à la publication ETAT NIGER ETABLISSEMENT BANK OF AFRICA",
            "lines": [
                line("COMPTE DE RESULTAT destiné à la publication ETAT NIGER ETABLISSEMENT BANK OF AFRICA", []),
                line("10 PRODUIT NET BANCAIRE 21 380 21 125", [(4, 21380.0), (6, 21125.0)]),
                # Première colonne masquée par un tampon dans le document
                # réel : le montant isolé est celui de l'exercice courant
                # et ne doit pas écraser le 5 002 de l'exercice précédent.
                line("20 RESULTAT NET 409", [(3, 409.0)]),
            ],
        }
        # Une annexe du même rapport en colonnes descendantes ne doit pas
        # imposer son ordre au formulaire bancaire normalisé.
        annex = {
            "text": "(en millions de FCFA) TOTAL AU 31/12/2025 TOTAL AU 31/12/2024",
            "lines": [
                line("TOTAL AU 31/12/2025 TOTAL AU 31/12/2024", []),
            ],
        }
        extracted = extract_figures_from_pages([balance, income, annex])
        self.assertEqual(extracted["courant"]["capitaux_propres"]["value_fcfa"], 36_064_000_000)
        self.assertEqual(extracted["courant"]["total_bilan"]["value_fcfa"], 291_750_000_000)
        self.assertEqual(extracted["courant"]["produit_net_bancaire"]["value_fcfa"], 21_125_000_000)
        self.assertEqual(extracted["courant"]["resultat_net"]["value_fcfa"], 409_000_000)
        self.assertEqual(extracted["precedent"]["resultat_net"]["value_fcfa"], 5_002_000_000)

    def test_unit_from_subscribed_capital_for_bank_summary_without_printed_unit(self):
        def line(text, amounts):
            return {"text": text, "words": text.split(), "amounts": amounts}

        def pages(capital_previous, capital_current):
            balance = {
                "text": "",
                "lines": [
                    line("31/12/2023 31/12/2024 MONTANT %", []),
                    line("2 DETTES INTERBANCAIRES ET ASSIMILEES 105 373 76 300", [(5, 105373.0), (7, 76300.0)]),
                    line("3 DETTES A L'EGARD DE LA CLIENTELE 713 575 856 274", [(7, 713575.0), (9, 856274.0)]),
                    line(
                        "9 CAPITAUX PROPRES ET RESSOURCES ASSIMILEES 95 800 112 644",
                        [(6, 95800.0), (8, 112644.0)],
                    ),
                    line(
                        f"10 CAPITAL SOUSCRIT {capital_previous} {capital_current}",
                        [(3, float(capital_previous)), (4, float(capital_current))],
                    ),
                    line("TOTAL DU PASSIF 938 738 1 075 479", [(3, 938738.0), (5, 1075479.0)]),
                ],
            }
            income = {
                "text": "",
                "lines": [
                    line("31/12/2023 31/12/2024 MONTANT %", []),
                    line("10 PRODUIT NET BANCAIRE 60 811 72 724", [(4, 60811.0), (6, 72724.0)]),
                    line("20 RESULTAT NET 26 075 32 044", [(3, 26075.0), (5, 32044.0)]),
                ],
            }
            return [balance, income]

        # Synthèse BOA CI : aucune unité imprimée, mais seul le million
        # place le capital souscrit (20 000 / 40 000) dans la bande
        # réglementaire d'une banque UMOA.
        bank_pages = pages(20000, 40000)
        unit = detect_unit_from_subscribed_capital(bank_pages)
        self.assertEqual(unit[0], 1_000_000)
        self.assertIn("capital souscrit", unit[1])
        extracted = extract_figures_from_pages(bank_pages)
        self.assertEqual(extracted["courant"]["capitaux_propres"]["value_fcfa"], 112_644_000_000)
        self.assertEqual(extracted["courant"]["total_bilan"]["value_fcfa"], 1_075_479_000_000)
        self.assertEqual(extracted["courant"]["produit_net_bancaire"]["value_fcfa"], 72_724_000_000)
        self.assertEqual(extracted["precedent"]["resultat_net"]["value_fcfa"], 26_075_000_000)

        # Un capital hors bande pour tous les multiplicateurs : abstention.
        self.assertIsNone(detect_unit_from_subscribed_capital(pages(8, 8)))

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


class DividendSustainabilityTests(unittest.TestCase):
    def test_ratios_only_from_same_fiscal_year_inputs(self):
        def fig(value, kind="fcfa", confidence="confirme_deux_documents"):
            out = {"value": value, "value_kind": kind, "confidence": confidence}
            if kind == "fcfa":
                out["value_fcfa"] = value
            return out
        companies = [{
            "ticker": "TEST",
            "dividend_history": {
                "payout_ratio_status": "non_calculable_sans_nombre_actions_ou_benefice_par_action_verifie",
                "annual": [{"fiscal_year": 2025, "net_amount_fcfa": 92.5}],
            },
            "fundamentals": {"series": [
                {"exercice": 2026, "figures": {"dividendes_verses": fig(-5_000_000_000)}},
                {"exercice": 2025, "figures": {
                    "resultat_net": fig(18_500_000_000),
                    "benefice_par_action": fig(185.0, "fcfa_par_action"),
                    "nombre_actions_fin_exercice": fig(100_000_000, "actions"),
                    "flux_tresorerie_operationnel": fig(30_000_000_000),
                    "investissements_immobilisations": fig(-8_000_000_000),
                }},
            ]},
        }]
        counts = enrich_dividend_sustainability(companies)
        row = companies[0]["dividend_sustainability"]["rows"][0]
        self.assertEqual(row["dividende_net_sur_bpa_pct"], 50.0)
        self.assertEqual(row["distribution_nette_totale_calculee_fcfa"], 9_250_000_000)
        self.assertEqual(row["distribution_nette_sur_resultat_pct"], 50.0)
        self.assertEqual(row["couverture_flux_operationnel_x"], 3.243)
        self.assertEqual(row["flux_apres_investissements_fcfa"], 22_000_000_000)
        self.assertEqual(row["couverture_apres_investissements_x"], 2.378)
        self.assertEqual(row["dividendes_verses_exercice_suivant_fcfa"], 5_000_000_000)
        self.assertEqual(counts["companies_with_dividend_eps_ratio"], 1)
        self.assertEqual(counts["companies_with_dividend_cash_coverage"], 1)
        self.assertIn("pas_taux_brut", companies[0]["dividend_history"]["payout_ratio_status"])


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

    def test_ocr_provenance_survives_series_merge(self):
        observation = self.obs(2025, "total_bilan", 836_158_000_000, "doc2025")
        observation.update({"extraction_method": "ocr_controle", "ocr_confidence": 89.5})
        series, _notes = merge_series_observations([observation])
        figure = series[2025]["total_bilan"]
        self.assertEqual(figure["extraction_method"], "ocr_controle")
        self.assertEqual(figure["ocr_confidence"], 89.5)

    def test_divergence_is_reported(self):
        observations = [
            self.obs(2024, "resultat_net", 18_000_000_000, "doc2025", column=1),
            self.obs(2024, "resultat_net", 25_000_000_000, "doc2024"),
            self.obs(2024, "resultat_net", 25_200_000_000, "doc2024b"),
        ]
        series, notes = merge_series_observations(observations)
        self.assertTrue(any("divergentes" in n for n in notes))
        self.assertGreater(series[2024]["resultat_net"]["value_fcfa"], 24_000_000_000)


class SgiTariffParsingTests(unittest.TestCase):
    def test_decision_number_ignores_visa_numbers(self):
        text = (
            "AUTORITE DES MARCHES FINANCIERS DE L'UMOA PRESIDENCE "
            "DECISION N° PAMF-UMOA / 2024 / 163 RELATIVE A L'HOMOLOGATION DES TARIFS "
            "DE LA SGI EXEMPLE CAPITAL Le Président, Vu la Décision n° PCR/DA/2017/119 "
            "du 15 septembre 2017 portant agrément sous le numéro SGI/2017-04 ; "
            "Vu la Décision n° PCR/DA/2018/36 portant homologation des tarifs. "
            "Fait à Abidjan, le 26 juin 2024."
        )
        header = parse_tariff_decision_header(text)
        self.assertEqual(header["decision_number"], "PAMF-UMOA/2024/163")
        self.assertEqual(header["decision_date"], "2024-06-26")
        self.assertEqual(header["sgi_name_pdf"], "EXEMPLE CAPITAL")
        self.assertEqual(header["approval_number"], "2017-04")
        self.assertEqual(header["authority"], "AMF-UMOA")
        self.assertTrue(header["mentions_homologation"])

    def test_decision_number_not_invented_from_visas_when_title_illegible(self):
        text = (
            "DECISION N° PAMF-UMOA / 2024 / ___ RELATIVE A L'HOMOLOGATION DES TARIFS "
            "DE LA SGI EXEMPLE Le Président, Vu la Décision n° PCR/DA/2017/119 portant agrément."
        )
        header = parse_tariff_decision_header(text)
        self.assertIsNone(header["decision_number"])
        self.assertEqual(header["sgi_name_pdf"], "EXEMPLE")

    def test_crepmf_era_decision(self):
        text = (
            "CONSEIL REGIONAL DE L'EPARGNE PUBLIQUE ET DES MARCHES FINANCIERS "
            "DECISION N° PCR / SG / DA / 2021/ 158 RELATIVE A L'HOMOLOGATION DES TARIFS "
            "DE LA SGI AFRICABOURSE Le Président, Vu la Convention du 03 juillet 1996."
        )
        header = parse_tariff_decision_header(text)
        self.assertEqual(header["decision_number"], "PCR/SG/DA/2021/158")
        self.assertEqual(header["authority"], "CREPMF (devenu AMF-UMOA)")

    def test_rate_text_parsing_bounds_and_forfait(self):
        Parsed = parse_tariff_rate_text("Maximum : 0,8 %", "courtage_ordinaire")
        self.assertEqual(Parsed["percent_max"], 0.8)
        self.assertTrue(Parsed["is_maximum"])
        Parsed = parse_tariff_rate_text("[0,5% - 2%]", "structuration_arrangement")
        self.assertEqual((Parsed["percent_min"], Parsed["percent_max"]), (0.5, 2.0))
        self.assertTrue(Parsed["is_range"])
        Parsed = parse_tariff_rate_text("Maximum 2 500 FCFA par trimestre", "tenue_de_compte")
        self.assertEqual(Parsed["forfait_fcfa"], [2500])
        self.assertEqual(Parsed["period"], "par trimestre")
        # Les seuils de tranches ne sont jamais lus comme des forfaits.
        Parsed = parse_tariff_rate_text("0,125% par trimestre pour la tranche de 0 à 10 000 000 FCFA", "conservation")
        self.assertEqual(Parsed["forfait_fcfa"], [])
        self.assertEqual(Parsed["percents"], [0.125])

    def test_rate_text_parsing_rejects_implausible_percents(self):
        # Artefacts OCR réels observés : virgule perdue (0,25 lu « 025 % »),
        # TVA de 18 % citée dans le texte, tranche « 20 » collée à un %.
        # La valeur aberrante est écartée du résumé chiffré, jamais corrigée.
        Parsed = parse_tariff_rate_text("Mein 025 % per a · Frais de tenue de Compte", "tenue_de_compte")
        self.assertEqual(Parsed["percents"], [])
        Parsed = parse_tariff_rate_text("Commission de gestion 18%/an TTC", "gestion_sous_mandat")
        self.assertEqual(Parsed["percents"], [])
        Parsed = parse_tariff_rate_text("courtage 0,2% puis 0,5% puis 20 %", "courtage_ordinaire")
        self.assertEqual(Parsed["percents"], [0.2, 0.5])
        # Une commission de marché primaire élevée mais plausible reste lue.
        Parsed = parse_tariff_rate_text("Commission de placement : 5 % maximum", "placement_titres")
        self.assertEqual(Parsed["percents"], [5.0])

    def test_rubrique_mapping_excludes_market_fees(self):
        self.assertEqual(
            _tariff_rubrique_key("commissions de courtage sur transactions ordinaires"),
            "courtage_ordinaire",
        )
        self.assertEqual(
            _tariff_rubrique_key("commission de courtage sur transaction sur dossier"),
            "courtage_sur_dossier",
        )
        self.assertIsNone(_tariff_rubrique_key("commission retrocession de courtage en faveur brvm"))
        self.assertEqual(_tariff_rubrique_key("garantie de placement (prise ferme)"), "garantie_placement")

    def test_sgi_name_matching_is_explicit(self):
        self.assertTrue(_sgi_names_match("BSIC CAPITAL", "BSIC Capital SA"))
        self.assertTrue(_sgi_names_match("NSIA CAPITAL", "NSIA FINANCE"))
        self.assertFalse(_sgi_names_match("BOA CAPITAL", "BSIC CAPITAL"))

    def test_rates_extraction_from_structured_lines(self):
        def line(text):
            return {"text": text, "words": text.split(), "amounts": [], "top": 0}

        pages = [
            {
                "page_number": 3,
                "lines": [
                    line("RUBRIQUES BASE DE CALCUL TAUX"),
                    line("Commissions de courtage sur transactions Montant de la transaction Maximum : 0,9 %"),
                    line("ordinaires"),
                    line("Frais de tenue de compte Forfait Maximum 2 500 FCFA par trimestre"),
                ],
            }
        ]
        rates = extract_tariff_rates_from_lines(pages)
        self.assertEqual(rates["courtage_ordinaire"]["Parsed_percent_max"], 0.9)
        self.assertEqual(rates["courtage_ordinaire"]["page"], 3)
        self.assertEqual(rates["tenue_de_compte"]["Parsed_forfait_fcfa"], [2500])

    def test_announced_decision_number_variants(self):
        self.assertEqual(
            parse_announced_decision_number("Décision N°PAMF-UMOA/2025/289 – Homologation des tarifs de la SGI Togo"),
            "PAMF-UMOA/2025/289",
        )
        self.assertEqual(
            parse_announced_decision_number("decision_ndegpamf-umoa_-_346_-_2024_-_homologation_des_tarifs_de_la_sgi_ifi.pdf"),
            "PAMF-UMOA/2024/346",
        )
        self.assertEqual(
            parse_announced_decision_number("20190430_-_decision_ndeg_pcr-da-2019-094_homologation_des_tarifs.pdf"),
            "PCR/DA/2019/94",
        )
        self.assertIsNone(parse_announced_decision_number("Homologation des tarifs de la SGI EXEMPLE"))

    def test_brvm_title_and_pdf_extraction(self):
        self.assertEqual(
            _sgi_name_from_brvm_title("DECISION PAMF-UMOA : Homologation des tarifs de la SGI BICI BOURSE"),
            "BICI BOURSE",
        )
        self.assertEqual(
            _sgi_name_from_brvm_title("SGI HUDSON & CIE : Homologation des tarifs"),
            "HUDSON & CIE",
        )
        html = (
            '<a href="/sites/default/files/autre.pdf">x</a>'
            '<a href="/sites/default/files/decision_ndegpamf-umoa-2025-289_-_homologation_des_tarifs_de_la_sgi_togo.pdf">PDF</a>'
        )
        self.assertTrue(brvm_decision_pdf_url(html).endswith("sgi_togo.pdf"))

    def test_proven_sgi_aliases(self):
        self.assertTrue(_sgi_names_match("SOGEBOURSE", "SOCIETE GENERALE CAPITAL SECURITIES WEST AFRICA"))
        self.assertTrue(
            _sgi_names_match("CIFA BOURSE", "Compagnie d’Ingénierie Financière et d’Assistance en Bourse")
        )

    def test_richbourse_rows_parsing(self):
        html = (
            "<table><tbody><tr><td>ABCO BOURSE "
            "<a href=\"/common/apprendre/afficher-tarifs-sgi/2953_abco-bourse\">Document officiel</a></td>"
            "<td>SECOND MARCHE</td><td>Commissions de courtage sur transactions ordinaires</td>"
            "<td>Montant de la transaction</td><td>[0,4% - 1%]</td></tr></tbody></table>"
        )
        rows = parse_richbourse_tariff_rows(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["doc_ref"], "2953_abco-bourse")
        self.assertEqual(rows[0]["rate_text"], "[0,4% - 1%]")


class PilotRegressionTests(unittest.TestCase):
    """Régressions synthétiques issues des défauts prouvés par le pilote.

    Les libellés reproduisent les formes rencontrées, sans copier les
    documents : chaque test protège une règle de sélection, de contexte ou
    de quarantaine, pas une valeur comptable particulière.
    """

    @staticmethod
    def page(lines, page_number=1):
        return {
            "page_number": page_number,
            "text": "\n".join(lines),
            "lines": [
                {"text": text, "words": text.split(), "amounts": [], "top": index * 10}
                for index, text in enumerate(lines)
            ],
        }

    def test_document_selection_rejects_interim_and_ranks_ifrs_accounts(self):
        interim = classify_report_document(
            "etats_financiers_au_30062024_s1.pdf", "États financiers au 30 juin 2024"
        )
        self.assertEqual(interim["selection_status"], "EXCLU_SERIE_ANNUELLE_INTERMEDIAIRE")
        self.assertEqual(interim["period_kind"], "INTERMEDIAIRE")

        condensed = classify_report_document(
            "etats_financiers_condenses_et_audites_2024.pdf", "États condensés audités 2024"
        )
        self.assertEqual(condensed["doc_type"], "etats_condenses")
        self.assertIn(condensed["doc_type"], ANNUAL_DOC_PRIORITY)
        self.assertLess(ANNUAL_DOC_PRIORITY["comptes_ifrs"], ANNUAL_DOC_PRIORITY["etats_financiers"])

        english = classify_report_document("financial_report_2024.pdf", "Financial report 2024")
        self.assertEqual(english["doc_type"], "rapport_annuel")
        self.assertEqual(english["exercice"], 2024)

    def test_content_identity_rejects_another_listed_issuer(self):
        pages = [
            self.page(
                [
                    "ECOBANK Côte d'Ivoire",
                    "Société anonyme au capital de 27 445 500 000 FCFA",
                    "États financiers annuels au 31 décembre 2017",
                ]
            )
        ]
        identity = verify_document_issuer(
            pages,
            "ETIT",
            {
                "ecobank transnational incorporated": "ETIT",
                "ecobank cote d ivoire": "ECOC",
                "ecobank ci": "ECOC",
            },
            filename="etats_financiers_2017_ecobank_ci.pdf",
        )
        self.assertEqual(identity["status"], "AUTRE_EMETTEUR_CONFIRME")
        self.assertEqual(identity["best_other_ticker"], "ECOC")

    def test_generic_word_total_does_not_confirm_another_issuer(self):
        pages = [
            self.page(
                [
                    "Bilan",
                    "Total actif 1 000 000",
                    "Total passif 1 000 000",
                    "Total des capitaux propres 200 000",
                ]
            )
        ]
        identity = verify_document_issuer(
            pages,
            "CIEC",
            {
                "cie cote d ivoire": "CIEC",
                "total": "TTLC",
                "totalenergies marketing cote d ivoire": "TTLC",
            },
            filename="etats_financiers_2016_cie.pdf",
        )
        self.assertNotEqual(identity["status"], "AUTRE_EMETTEUR_CONFIRME")

    def test_content_period_and_fiscal_year_override_filename(self):
        pages = [
            self.page(
                [
                    "Rapport des commissaires aux comptes sur les états financiers consolidés",
                    "Exercices clos les 31 décembre 2017 et 2016",
                    "États financiers consolidés annuels",
                ]
            )
        ]
        self.assertEqual(detect_document_period(pages)["period_kind"], "ANNUEL_OU_NON_PROUVE")
        fiscal = detect_document_fiscal_year(pages)
        self.assertEqual(fiscal["exercice"], 2017)
        self.assertEqual(fiscal["status"], "LU_DANS_LE_CONTENU")

        interim_pages = [self.page(["États financiers semestriels au 30 juin 2024"])]
        self.assertEqual(detect_document_period(interim_pages)["period_kind"], "INTERMEDIAIRE")

    def test_ago_future_exercice_mentions_do_not_override_closing_year(self):
        # Cas réel BOAS : l'AG tenue en 2020 approuve les comptes clos
        # au 31/12/2019, mais son ordre du jour cite aussi à deux reprises
        # l'exercice 2020 (indemnités/budget). L'exercice du document est
        # 2019 ; choisir 2020 décale toutes les colonnes d'un an.
        pages = [
            self.page(
                [
                    "1- Examen et approbation du bilan et des comptes de l’exercice clos le 31 décembre 2019",
                    "3- Affectation du résultat de l’exercice clos au 31 décembre 2019",
                    "5- Fixation des indemnités de fonction des administrateurs au titre de l’exercice 2020",
                    "6- Budget de fonctionnement de l’exercice 2020",
                    "LE CADRE ECONOMIQUE ET FINANCIER DE L’EXERCICE 2019",
                ]
            )
        ]
        fiscal = detect_document_fiscal_year(pages)
        self.assertEqual(fiscal["exercice"], 2019)

    def test_prior_year_closing_mention_does_not_override_current_dated_headers(self):
        # Cas réel CFAC 2018 : une phrase sur l'exercice clos 2017 est
        # comparative ; les en-têtes primaires sont datés au 31/12/2018.
        pages = [
            self.page(
                [
                    "COMPTE DE RESULTAT AU 31 DECEMBRE 2018",
                    "BILAN AU 31 DECEMBRE 2018",
                    "bilan d’ouverture des états financiers de l’exercice 2018.",
                    "titre de l’exercice clos le 31 décembre 2017.",
                ]
            )
        ]
        self.assertEqual(detect_document_fiscal_year(pages)["exercice"], 2018)

    def test_current_generic_exercice_wins_when_only_comparative_is_dated(self):
        # Cas réel NSBC 2020 (communiqué) : le seul « au 31 décembre »
        # répété est le comparatif 2019 ; l'exercice courant 2020 est
        # nommé de façon générique et répétée.
        pages = [
            self.page(
                [
                    "NSIA BANQUE ACHÈVE UN EXERCICE 2020 DIFFICILE",
                    "Les résultats présentés sur l’exercice 2020 sont en baisse.",
                    "20 milliards FCFA au 31 décembre 2019.",
                    "4,7 milliards FCFA au 31 décembre 2019.",
                    "dès l’exercice 2021, la banque poursuivra son assainissement.",
                ]
            )
        ]
        self.assertEqual(detect_document_fiscal_year(pages)["exercice"], 2020)

    def test_future_mandate_closing_year_does_not_override_current_closing(self):
        # Cas réel CABC 2024 : les renouvellements de mandats citent
        # l'assemblée qui statuera en 2028 sur l'exercice clos 2027.
        # L'exercice du document reste 2024, cité plus souvent en clôture.
        pages = [
            self.page(
                [
                    "Comptes annuels de l'exercice clos le 31 décembre 2024",
                    "pendant l’exercice clos au 31 décembre 2024, et du Rapport joint du Président ;",
                    "l’activité de notre société au cours de l’exercice clos le 31 décembre 2024.",
                    "Les comptes annuels de l’exercice clos le 31 décembre 2024 qui vous sont présentés ont été établis",
                    "qui statuera en 2028 sur les comptes de l’exercice clos le 31 décembre 2027.",
                    "qui statuera en 2028 sur les comptes de l’exercice clos le 31 décembre 2027.",
                ]
            )
        ]
        self.assertEqual(detect_document_fiscal_year(pages)["exercice"], 2024)

    def test_next_year_outlook_mentions_do_not_override_most_frequent_year(self):
        # Cas réel SIBC 2019 : deux phrases de perspectives citent
        # l'exercice 2020, mais les montants au 31/12/2019 et l'exercice
        # 2019 dominent le document.
        pages = [
            self.page(
                [
                    "Les charges s’établissent à 32,6 milliards FCFA au 31 décembre 2019",
                    "Le produit net bancaire au 31 décembre 2019 progresse.",
                    "Les dépôts au 31 décembre 2019 augmentent.",
                    "Cette vérification s’est dénouée au cours de l’exercice 2019,",
                    "La Banque a lancé au cours de l’exercice 2019 son plan.",
                    "L’exercice 2020 étant une année électorale, nous avons été prudents.",
                    "Nous devrions réaliser nos ambitions sur l’exercice 2020.",
                ]
            )
        ]
        self.assertEqual(detect_document_fiscal_year(pages)["exercice"], 2019)

    def test_table_of_contents_eps_page_number_is_not_a_value(self):
        pages = [
            self.page(["Sommaire", "Bénéfice par action 20"], page_number=3),
            self.page(
                [
                    "Compte de résultat consolidé",
                    "Montants en FCFA",
                    "Bénéfice par action de base 140 120",
                ],
                page_number=20,
            ),
        ]
        result = extract_per_share_observations(pages, document_exercice=2019)
        eligible = [
            item for item in result["eps"] if item.get("eligible_fcfa_total_basic")
        ]
        self.assertEqual([item["value"] for item in eligible], [140.0, 120.0])
        self.assertTrue(any("SOMMAIRE" in str(item.get("reason") or "") for item in result["ignored"]))

    def test_eps_value_on_following_lines_is_read(self):
        pages = [
            self.page(
                [
                    "Compte de résultat",
                    "Bénéfice par action de base",
                    "(en FCFA)",
                    "140",
                    "120",
                ]
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2024)
        self.assertEqual([item["value"] for item in result["eps"]], [140.0, 120.0])
        self.assertTrue(all(item["eligible_fcfa_total_basic"] for item in result["eps"]))

    def test_spaced_decimals_and_repeated_integer_columns(self):
        spaced = extract_numeric_tokens("250, 9 4 259,6")
        self.assertEqual(spaced[0]["value"], 250.9)
        spaced_Pages = [
            self.page(
                [
                    "Compte de résultat consolidé",
                    "Bénéfice par action (FCFA) 250, 9 4 259,6",
                ]
            )
        ]
        spaced_result = extract_per_share_observations(spaced_Pages, document_exercice=2022)
        self.assertEqual(spaced_result["eps"][0]["value"], 250.9)
        self.assertEqual(spaced_result["eps"][0]["raw_token"], "250,9")

        pages = [
            self.page(
                [
                    "Compte de résultat",
                    "Exercice 2018 2017 2016",
                    "Résultat net par action (en FCFA) 266 185 170",
                ]
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2018)
        self.assertEqual([item["value"] for item in result["eps"]], [266.0, 185.0, 170.0])

    def test_three_year_and_reversed_year_columns(self):
        pages = [
            self.page(
                [
                    "Compte de résultat",
                    "Exercice 2024 2023 2022",
                    "Bénéfice par action (FCFA) 234 188 205",
                ]
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2024)
        self.assertEqual(
            [(item["target_exercice"], item["value"]) for item in result["eps"]],
            [(2024, 234.0), (2023, 188.0), (2022, 205.0)],
        )

        reversed_pages = [
            self.page(
                [
                    "Compte de résultat",
                    "Exercice 2023 2024",
                    "Bénéfice par action (FCFA) 188 234",
                ]
            )
        ]
        reversed_result = extract_per_share_observations(reversed_pages, document_exercice=2024)
        self.assertEqual(
            [(item["target_exercice"], item["value"]) for item in reversed_result["eps"]],
            [(2023, 188.0), (2024, 234.0)],
        )

    def test_accounting_contexts_keep_ifrs_and_sysco_scopes_separate(self):
        pages = [
            self.page(
                [
                    "États financiers consolidés IFRS",
                    "Bénéfice par action (FCFA) 280,1 266,0",
                ],
                page_number=10,
            ),
            self.page(
                [
                    "États financiers annuels SYSCOHADA – comptes personnels",
                    "Bénéfice par action (FCFA) 250 240",
                ],
                page_number=80,
            ),
        ]
        contexts, summary = classify_page_accounting_contexts(pages)
        self.assertEqual(contexts[0]["accounting_scope"], "CONSOLIDE")
        self.assertEqual(set(summary["scopes_present"]), {"CONSOLIDE", "SOCIAL"})
        result = extract_per_share_observations(pages, document_exercice=2018)
        self.assertEqual(
            {(item["accounting_scope"], item["framework"]) for item in result["eps"]},
            {("CONSOLIDE", "IFRS"), ("SOCIAL", "SYSCOHADA")},
        )
        self.assertGreaterEqual(len(contexts), 2)

    def test_ifrs_word_inside_scope_heading_resets_scope(self):
        # Cas TTLS 2025 : « Etats financiers IFRS individuels » puis
        # « Etats financiers IFRS consolidés » dans le même rapport. Le mot
        # IFRS intercalé ne doit pas empêcher le changement de périmètre,
        # même si une page narrative précédente mentionne les comptes
        # consolidés.
        pages = [
            self.page(
                ["Le comité assure le suivi des comptes consolidés et des travaux d'audit."],
                page_number=31,
            ),
            self.page(
                [
                    "TOTALENERGIES MARKETING Côte d’Ivoire | Etats financiers IFRS individuels",
                    "Etat du résultat net",
                    "31/12/2025 31/12/2024",
                    "Résultat de base par action 205 128",
                ],
                page_number=39,
            ),
            self.page(
                [
                    "TOTALENERGIES MARKETING Côte d’Ivoire | Etats financiers IFRS consolidés",
                    "Etat du résultat net consolidé",
                    "31/12/2025 31/12/2024",
                    "Résultat de base par action 208 219",
                ],
                page_number=42,
            ),
        ]
        contexts, _summary = classify_page_accounting_contexts(pages)
        by_page = {context["page"]: context for context in contexts}
        self.assertEqual(by_page[39]["accounting_scope"], "INDIVIDUEL")
        self.assertEqual(by_page[39]["accounting_scope_source"], "PAGE_OU_SECTION")
        self.assertEqual(by_page[42]["accounting_scope"], "CONSOLIDE")
        self.assertEqual(by_page[42]["accounting_scope_source"], "PAGE_OU_SECTION")

        result = extract_per_share_observations(pages, document_exercice=2025)
        Values = {
            (item["accounting_scope"], item["target_exercice"]): item["value"]
            for item in result["eps"]
        }
        self.assertEqual(Values[("INDIVIDUEL", 2025)], 205.0)
        self.assertEqual(Values[("INDIVIDUEL", 2024)], 128.0)
        self.assertEqual(Values[("CONSOLIDE", 2025)], 208.0)
        self.assertEqual(Values[("CONSOLIDE", 2024)], 219.0)

    def test_closing_dates_after_eps_label_are_not_values(self):
        # Cas SPHC 2021 : les en-têtes « 31-déc-21 31-déc-20 » ne sont pas
        # les valeurs 31 et -21. Les sous-lignes qui suivent restent lues,
        # et « Non dilué » désigne la base de base, pas la base diluée.
        pages = [
            self.page(
                [
                    "Compte de résultat par action",
                    "Resultat par action 31-déc-21 31-déc-20",
                    "Non dilué 0,830 0,329",
                    "Dilué 0,830 0,329",
                ],
                page_number=7,
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2021)
        Values = {item["value"] for item in result["eps"]}
        self.assertNotIn(31.0, Values)
        self.assertNotIn(-21.0, Values)
        self.assertNotIn(-20.0, Values)
        basic = [
            item for item in result["eps"] if item["basis"] == "DE_BASE"
        ]
        diluted = [
            item for item in result["eps"] if item["basis"] == "DILUE"
        ]
        self.assertEqual([item["value"] for item in basic], [0.83, 0.329])
        self.assertEqual([item["target_exercice"] for item in basic], [2021, 2020])
        self.assertEqual([item["value"] for item in diluted], [0.83, 0.329])

        # Même garde-fou lorsque les montants ont déjà été regroupés dans
        # la ligne structurée.
        structured_page = {
            "page_number": 7,
            "text": "Résultat par action 31-déc-21 31-déc-20",
            "lines": [
                {
                    "text": "Résultat par action 31-déc-21 31-déc-20",
                    "words": "Résultat par action 31-déc-21 31-déc-20".split(),
                    "amounts": [(3, 31.0), (4, -21.0)],
                }
            ],
        }
        structured_result = extract_per_share_observations(
            [structured_page], document_exercice=2021
        )
        self.assertEqual(structured_result["eps"], [])

    def test_spaced_year_header_is_not_an_eps_value(self):
        # Cas réel ORGT 2019, note BPA p. 43 : le titre est suivi d'une
        # ligne d'années espacées (« 2 019 2 018 »), puis du numérateur,
        # du nombre d'actions et seulement ensuite du BPA. Même si un
        # titre voisin mentionne « de base », les années ne doivent
        # jamais devenir des valeurs promues.
        pages = [
            self.page(
                [
                    "Résultat de base par action",
                    "2 019 2 018",
                    "Résultat net part du groupe 9 806 7 968",
                    "Nombre d'action en circulation 69 090 306 69 415 031",
                    "Résultat de base par action (en unité de franc CFA) 142 115",
                ],
                page_number=43,
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2019)
        self.assertEqual(
            [
                (item["target_exercice"], item["value"])
                for item in result["eps"]
                if item["eligible_fcfa_total_basic"]
            ],
            [(2019, 142.0), (2018, 115.0)],
        )
        self.assertNotIn(2019.0, [item["value"] for item in result["eps"]])
        self.assertNotIn(2018.0, [item["value"] for item in result["eps"]])

    def test_phone_number_is_not_a_spaced_year_header(self):
        # Cas réel SIBC 2018 p. 28 : le téléphone/fax de l'en-tête
        # contient « 20 20 » et « 20 21 », qui ne sont pas des colonnes
        # 2020/2021. Sans en-tête d'exercice, on retombe sur l'ordre du
        # document 2018 puis 2017.
        pages = [
            self.page(
                [
                    "Tél. : (225) 20 20 00 00 - Fax : (225) 20 21 92 21",
                    "RESULTAT PAR ACTION",
                    "Résultat net par action ou part sociale 0,0017091 0,0022530",
                ],
                page_number=28,
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2018)
        self.assertEqual(
            [(item["target_exercice"], item["value"]) for item in result["eps"]],
            [(2018, 0.0017091), (2017, 0.002253)],
        )

    def test_percent_changes_do_not_turn_last_dual_currency_eps_into_date(self):
        # Cas réel ETIT 2019 p. 1 : quatre valeurs (cents/FCFA sur deux
        # exercices) sont suivies de variations -5% et -11%. Cette queue
        # ne doit pas être lue comme une date qui supprimerait la
        # quatrième valeur et casserait le motif double devise.
        pages = [
            self.page(
                [
                    "Résultat net par action (en cents $EU 0 ,78 4 ,56 0 ,74 4 ,11 -5% -11%",
                    "/ FCFA)",
                ],
                page_number=1,
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2019)
        self.assertEqual(
            [
                (item["target_exercice"], item["value"], item["currency"])
                for item in result["eps"]
            ],
            [
                (2019, 0.78, "USD_CENT"),
                (2019, 4.56, "FCFA"),
                (2018, 0.74, "USD_CENT"),
                (2018, 4.11, "FCFA"),
            ],
        )

    def test_page_thousands_scale_does_not_promote_unscaled_eps(self):
        # Le document SPHC 2021 annonce des données en milliers de FCFA et
        # publie 0,830 sans unité par action distincte. La valeur brute est
        # conservée comme preuve, mais elle ne doit pas devenir un BPA de
        # 0,83 FCFA. Une mention explicite « en FCFA » par action lève en
        # revanche l'ambiguïté malgré l'échelle monétaire de la page.
        pages = [
            self.page(
                [
                    "SAPH - COMPTE DE RESULTAT IFRS - 31 décembre 2021",
                    "En milliers de FCFA",
                    "COMPTE DE RESULTAT Notes 31-déc-21 31-déc-20",
                    "Résultat net 21 206 399 8 401 729",
                    "Compte de résultat par action",
                    "Resultat par action 31-déc-21 31-déc-20",
                    "Dilué 0,830 0,329",
                    "Non dilué 0,830 0,329",
                ],
                page_number=3,
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2021)
        basic = [
            item for item in result["eps"] if item["basis"] == "DE_BASE"
        ]
        self.assertEqual([item["value"] for item in basic], [0.83, 0.329])
        self.assertFalse(any(item["eligible_fcfa_total_basic"] for item in basic))
        self.assertTrue(
            all(
                "ECHELLE_MONETAIRE_DE_PAGE_SANS_UNITE_PAR_ACTION_EXPLICITE"
                in item["ineligibility_reasons"]
                for item in basic
            )
        )

        # Même garde-fou pour le document SPHC 2020, où les valeurs à trois
        # décimales 1,695 et 0,666 sont compatibles avec des milliers de
        # FCFA par action, faute d'unité par action distincte.
        decimal_pages = [
            self.page(
                [
                    "SAPH - COMPTE DE RESULTAT IFRS - 31 décembre 2020",
                    "En milliers de FCFA",
                    "COMPTE DE RESULTAT Notes 31-déc-20 31-déc-19",
                    "Résultat net 8 665 154 3 404 046",
                    "Resultat par action 31-déc-20 31-déc-19",
                    "Dilué 1,695 0,666",
                    "Non dilué 1,695 0,666",
                ],
                page_number=3,
            )
        ]
        decimal_result = extract_per_share_observations(
            decimal_pages, document_exercice=2020
        )
        decimal_basic = [
            item for item in decimal_result["eps"] if item["basis"] == "DE_BASE"
        ]
        self.assertEqual([item["value"] for item in decimal_basic], [1.695, 0.666])
        self.assertFalse(any(item["eligible_fcfa_total_basic"] for item in decimal_basic))

        # L'échelle des totaux d'un état ne s'applique en revanche pas
        # automatiquement à un montant par action entier : cas Sonatel du
        # pilote, où 2 359 est déjà en FCFA sous un en-tête en millions.
        integer_pages = [
            self.page(
                [
                    "Compte de résultat consolidé",
                    "En millions de FCFA NOTE 2024 2023 2022",
                    "Résultat net par actions attribuable aux propriétaires de la maison mère",
                    "- de base 3 288 2 794 2 359",
                    "- dilué 3 288 2 794 2 359",
                ],
                page_number=34,
            )
        ]
        integer_result = extract_per_share_observations(
            integer_pages, document_exercice=2024
        )
        integer_basic = [
            item for item in integer_result["eps"] if item["basis"] == "DE_BASE"
        ]
        self.assertEqual(
            [item["value"] for item in integer_basic], [3288.0, 2794.0, 2359.0]
        )
        self.assertTrue(all(item["eligible_fcfa_total_basic"] for item in integer_basic))

        explicit_pages = [
            self.page(
                [
                    "Compte de résultat consolidé",
                    "(en millions de FCFA, sauf résultat par action en FCFA)",
                    "2025 2024",
                    "Résultat de base par action (en FCFA) 205 128",
                ],
                page_number=4,
            )
        ]
        explicit_result = extract_per_share_observations(
            explicit_pages, document_exercice=2025
        )
        explicit_basic = [
            item for item in explicit_result["eps"] if item["basis"] == "DE_BASE"
        ]
        self.assertEqual([item["value"] for item in explicit_basic], [205.0, 128.0])
        self.assertTrue(all(item["eligible_fcfa_total_basic"] for item in explicit_basic))

    def test_usd_cents_components_are_preserved_but_not_retained(self):
        pages = [
            self.page(
                [
                    "Compte de résultat consolidé",
                    "Bénéfice par action (en cents de dollars EU) :",
                    "De base – activités poursuivies 1,06 0,89",
                    "De base – activités abandonnées (0,32) (0,10)",
                ]
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2018)
        self.assertEqual(len(result["eps"]), 4)
        self.assertEqual({item["currency"] for item in result["eps"]}, {"USD_CENT"})
        self.assertFalse(any(item["eligible_fcfa_total_basic"] for item in result["eps"]))

        metrics = derive_eps_metrics({}, exercice=2018, eps_observations=result)
        self.assertEqual(metrics["status"], collect_module.EPS_STATUS_PUBLISHED_NOT_RETAINED)
        self.assertIsNone(metrics["published_eps_fcfa"])
        self.assertEqual(len(metrics["nonretained_eps_observations"]), 2)

    def test_undiluted_line_before_diluted_line_is_basic_pair(self):
        pages = [
            self.page(
                [
                    "États financiers consolidés IFRS",
                    "Résultat par action en FCFA 307 140",
                    "Résultat par action dilué en FCFA 307 140",
                ]
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2020)
        basic = [
            item for item in result["eps"] if item.get("basis") == "DE_BASE"
        ]
        self.assertEqual([item["value"] for item in basic], [307.0, 140.0])
        self.assertTrue(all(item["eligible_fcfa_total_basic"] for item in basic))
        self.assertTrue(
            all(item.get("basis_source") for item in basic)
        )

    def test_discontinued_dash_makes_continuing_value_total_equivalent(self):
        pages = [
            self.page(
                [
                    "Compte de résultat",
                    "Bénéfice par action de base – activités poursuivies (FCFA) 12,5",
                    "Bénéfice par action de base – activités abandonnées (FCFA) –",
                ]
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2024)
        continuing = next(item for item in result["eps"] if item["value"] == 12.5)
        self.assertTrue(continuing["eligible_fcfa_total_basic"])
        self.assertEqual(
            continuing["component"], "TOTAL_EQUIVALENT_ARRETEES_NEANT_OU_ZERO"
        )

    def test_weighted_shares_units_treasury_and_diluted_only(self):
        pages = [
            self.page(
                [
                    "Note résultat par action",
                    "Nombre moyen pondéré d'actions (en milliers) 100 000 90 000",
                    "dont actions d’autocontrôle 125 125",
                    "Nombre d'actions moyen pondéré dilué 101 000 000 91 000 000",
                ]
            )
        ]
        result = extract_per_share_observations(pages, document_exercice=2024)
        eligible = [
            item
            for item in result["shares"]
            if item.get("denominator_kind") == "MOYEN_PONDERE" and item.get("eligible_as_denominator")
        ]
        self.assertEqual([item["value"] for item in eligible], [100_000_000.0, 90_000_000.0])
        self.assertTrue(
            any(item.get("denominator_kind") == "AUTOCONTROLE" for item in result["shares"])
        )
        self.assertFalse(
            any(
                item.get("eligible_as_denominator")
                and item.get("denominator_kind") == "MOYEN_PONDERE_DILUE"
                for item in result["shares"]
            )
        )

        figures = extract_figures_from_pages(pages, document_exercice=2024)
        self.assertEqual(
            figures["courant"]["nombre_actions_moyen_pondere"]["value"], 100_000_000
        )

    def test_eps_arithmetic_uses_publication_rounding(self):
        self.assertTrue(assess_eps_arithmetic(140, 140.44, 1, published_decimals=0)["concordant"])
        self.assertFalse(assess_eps_arithmetic(10, 10.56, 1, published_decimals=0)["concordant"])
        check = assess_eps_arithmetic(250.9, 259.54, 1, published_decimals=1)
        self.assertEqual(check["status"], "ECART_EN_QUARANTAINE")

    def test_divergent_published_eps_resolved_only_by_arithmetic(self):
        groups = [
            {"value": 2794.0, "eligible": True, "documents_confirmants": 1},
            {"value": 2359.0, "eligible": True, "documents_confirmants": 2},
        ]
        checks = {
            2794.0: {"concordant": True, "status": "CONCORDANT_ARRONDIS"},
            2359.0: {"concordant": False, "status": "INCOHERENT_AU_DELA_DES_ARRONDIS"},
        }
        resolved = select_published_eps_candidate(groups, checks)
        self.assertEqual(resolved["value"], 2794.0)
        self.assertEqual(
            resolved["status"], "DIVERGENCE_RESOLUE_PAR_CONTROLE_ARITHMETIQUE"
        )

        unresolved = select_published_eps_candidate(groups, {})
        self.assertEqual(
            unresolved["status"], "QUARANTAINE_VALEURS_PUBLIEES_DIVERGENTES"
        )
        self.assertIsNone(unresolved["value"])

    def test_derive_eps_quarantines_incoherent_published_value(self):
        figures = {
            "benefice_par_action": {
                "value": 250.9,
                "published_decimals": 1,
                "accounting_scope": "CONSOLIDE",
                "currency": "FCFA",
                "component": "TOTAL",
                "basis": "DE_BASE",
            },
            "resultat_net_attribuable_ordinaires": {
                "value_fcfa": 259_540_000,
                "accounting_scope": "CONSOLIDE",
            },
            "nombre_actions_moyen_pondere": {
                "value": 1_000_000,
                "accounting_scope": "CONSOLIDE",
            },
        }
        metrics = derive_eps_metrics(figures, exercice=2022)
        self.assertIsNone(metrics["published_eps_fcfa"])
        self.assertEqual(
            metrics["status"], collect_module.EPS_STATUS_PUBLISHED_QUARANTINE_COHERENCE
        )
        self.assertIsNotNone(metrics["quarantine"])
        self.assertAlmostEqual(metrics["recalculated_comparable_eps_fcfa"], 259.54)

    def test_derive_eps_resolves_divergent_groups(self):
        figures = {
            "benefice_par_action": {
                "value": 2359,
                "published_decimals": 0,
                "accounting_scope": "CONSOLIDE",
                "currency": "FCFA",
                "component": "TOTAL",
                "basis": "DE_BASE",
                "quarantine_reasons": [
                    "BPA_PUBLIE_INCOHERENT_AVEC_NUMERATEUR_ET_DENOMINATEUR_PONDERES"
                ],
                "candidate_groups": [
                    {"value": 2794.0, "eligible": True, "documents_confirmants": 1, "accounting_scope": "CONSOLIDE"},
                    {"value": 2359.0, "eligible": True, "documents_confirmants": 2, "accounting_scope": "CONSOLIDE"},
                ],
            },
            "resultat_net_part_groupe": {
                "value_fcfa": 279_400_000_000,
                "accounting_scope": "CONSOLIDE",
            },
            "nombre_actions_moyen_pondere": {"value": 100_000_000},
        }
        metrics = derive_eps_metrics(figures, exercice=2023)
        self.assertEqual(metrics["published_eps_fcfa"], 2794.0)
        self.assertEqual(
            metrics["status"], collect_module.EPS_STATUS_PUBLISHED_DIVERGENCE_RESOLVED
        )

    def test_merge_never_confirms_across_scopes_or_duplicate_hash(self):
        def observation(scope, sha):
            return {
                "exercice": 2018,
                "key": "benefice_par_action",
                "value": 280.1,
                "value_kind": "fcfa_par_action",
                "column": 0,
                "accounting_scope": scope,
                "framework": "IFRS",
                "currency": "FCFA",
                "component": "TOTAL",
                "basis": "DE_BASE",
                "candidate_signature": f"{scope}|IFRS|FCFA|TOTAL|DE_BASE",
                "doc_url": f"https://example.test/{sha}.pdf",
                "doc_sha256": sha,
                "doc_label": scope,
                "evidence": [{"page": 1, "line": "Bénéfice par action 280,1"}],
            }

        merged, _notes = merge_series_observations(
            [observation("CONSOLIDE", "a"), observation("INDIVIDUEL", "b")]
        )
        figure = merged[2018]["benefice_par_action"]
        self.assertEqual(figure["documents_confirmants"], 1)
        self.assertEqual(len(figure["candidate_groups"]), 2)

        duplicate, _notes = merge_series_observations(
            [observation("CONSOLIDE", "same"), observation("CONSOLIDE", "same")]
        )
        self.assertEqual(
            duplicate[2018]["benefice_par_action"]["documents_confirmants"], 1
        )

    def test_explicit_scope_mismatch_blocks_capital_supplement(self):
        primary = {
            "resultat_net": {"value_fcfa": 100, "accounting_scope": "CONSOLIDE"},
            "benefice_par_action": {"value": 10, "accounting_scope": "CONSOLIDE"},
        }
        supplement = {
            "resultat_net": {"value_fcfa": 100, "accounting_scope": "INDIVIDUEL"},
            "benefice_par_action": {"value": 10, "accounting_scope": "INDIVIDUEL"},
        }
        self.assertFalse(_figures_share_perimeter(primary, supplement))

    def test_capital_changes_and_verified_events_are_not_guessed(self):
        changes = detect_share_count_changes(
            [
                {"exercice": 2016, "end_shares": 2_800_000},
                {"exercice": 2017, "end_shares": 56_000_000},
            ]
        )
        self.assertEqual(changes[0]["suspected_factor_to_document"], 20)
        events = [
            event for event in load_verified_capital_events() if event["ticker"] == "BOAC"
        ]
        self.assertGreaterEqual(len(events), 2)
        adjusted = adjust_per_share_to_reference_unit(
            200.0,
            ticker="CIEC",
            value_exercice=2016,
            reference_exercice=2017,
            events=load_verified_capital_events(),
        )
        self.assertEqual(adjusted["adjusted_value"], 10.0)
        self.assertEqual(adjusted["factor_applied_to_denominator"], 20.0)
        blocking = adjust_per_share_to_reference_unit(
            200.0,
            ticker="TEST",
            value_exercice=2020,
            reference_exercice=2021,
            events=[
                {
                    "ticker": "TEST",
                    "event_type": "AUGMENTATION_CAPITAL_NUMERAIRE",
                    "factor_new_shares_per_old_share": 1.2,
                    "effective_date": "2021-06-01",
                    "source": {"url": "https://example.test/decision.pdf"},
                }
            ],
        )
        self.assertIsNone(blocking["adjusted_value"])

    def test_targeted_page_selection_scans_beyond_eighty_Pages(self):
        class Page:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

            def extract_words(self):
                return []

        class Pdf:
            def __init__(self, pages):
                self.pages = pages

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        fake_pages = [Page("Texte sans agrégat " * 20) for _ in range(90)]
        fake_pages[84] = Page(
            "Compte de résultat\nEn millions de FCFA\n"
            "Résultat net 1 000\nBénéfice par action 10"
        )
        original_open = collect_module.pdfplumber.open
        collect_module.pdfplumber.open = lambda _stream: Pdf(fake_pages)
        try:
            selected, metadata = collect_module._targeted_native_pdf_pages(b"%PDF-synthetic")
        finally:
            collect_module.pdfplumber.open = original_open
        self.assertEqual(metadata["pages_total"], 90)
        self.assertIn(85, [page["page_number"] for page in selected])

    def test_document_version_markers(self):
        markers = collect_module._document_version_markers(
            {
                "filename": "etats_2024_corriges.pdf",
                "label": "États financiers corrigés",
                "published_date": "2025-05-01",
            },
            [self.page(["Les chiffres comparatifs ont été retraités."])],
        )
        self.assertEqual(markers["version_label"], "CORRIGE")
        self.assertIn("RETRAITE", markers["version_markers"])

    def test_structured_side_by_side_amounts_are_not_eps_columns(self):
        words = (
            "Résultat par action en FCFA 307 140 Comptes courants "
            "d'actionnaires -299 0"
        ).split()
        page = {
            "page_number": 1,
            "text": "2020 2019\n" + " ".join(words),
            "lines": [
                {"text": "2020 2019", "words": ["2020", "2019"], "amounts": []},
                {
                    "text": " ".join(words),
                    "words": words,
                    "amounts": [(5, 307.0), (6, 140.0), (10, -299.0), (11, 0.0)],
                },
                {
                    "text": "Résultat par action dilué en FCFA 307 140",
                    "words": "Résultat par action dilué en FCFA 307 140".split(),
                    "amounts": [],
                },
            ],
        }
        result = extract_per_share_observations([page], document_exercice=2020)
        basic = [
            item for item in result["eps"] if item.get("eligible_fcfa_total_basic")
        ]
        self.assertEqual([item["value"] for item in basic], [307.0, 140.0])
        self.assertEqual([item["target_exercice"] for item in basic], [2020, 2019])

    def test_eps_title_with_group_subtitle_before_basis_sublines(self):
        page = self.page(
            [
                "Comptes consolidés",
                "État du compte de résultat consolidé",
                "(en millions de francs CFA) 2019 2018",
                "Résultat net consolidé, part du Groupe 11 030 15 249",
                "Résultat par action (en francs CFA) :",
                "2019 2018",
                "Résultat net part du Groupe :",
                "- de base 202,6 280,1",
                "- dilué 202,6 280,1",
            ]
        )
        result = extract_per_share_observations([page], document_exercice=2019)
        basic = [
            item for item in result["eps"] if item.get("eligible_fcfa_total_basic")
        ]
        self.assertEqual([item["value"] for item in basic], [202.6, 280.1])
        self.assertEqual([item["target_exercice"] for item in basic], [2019, 2018])

    def test_continuing_eps_is_total_only_without_discontinued_component(self):
        lines = [
            "Compte de résultat consolidé",
            "2024 2023",
            "Résultat net consolidé 100 90",
            "Résultat net par action sur le résultat net des activités poursuivies (en cents $EU et Franc CFA par action) :",
            "- Résultat de base par action 1,355 8,2 1,170 7,1",
            "- Résultat dilué par action 1,355 8,2 1,170 7,1",
        ]
        result = extract_per_share_observations([self.page(lines)], document_exercice=2024)
        direct = next(
            item
            for item in result["eps"]
            if item["value"] == 8.2 and item["basis"] == "DE_BASE"
        )
        self.assertTrue(direct["eligible_fcfa_total_basic"])
        self.assertEqual(
            direct["component_source"],
            "AUCUNE_COMPOSANTE_ARRETEE_DETECTEE_DANS_LE_DOCUMENT_COMPLET",
        )

        with_discontinued = list(lines)
        with_discontinued.insert(
            3, "Activités arrêtées ou en cours de cession (6,159) (3,582)"
        )
        blocked = extract_per_share_observations(
            [self.page(with_discontinued)], document_exercice=2024
        )
        self.assertFalse(
            any(
                item["value"] == 8.2 and item["eligible_fcfa_total_basic"]
                for item in blocked["eps"]
            )
        )

    def test_key_figures_fcfa_cross_checked_by_same_document_basic_usd(self):
        pages = [
            self.page(
                [
                    "Chiffres clés",
                    "2023 2022",
                    "Résultat net par action (en cents $EU / FCFA) 1,170 7,099 1,165 7,064 0% 0%",
                ]
            ),
            self.page(
                [
                    "Compte de résultat consolidé",
                    "2023 2022",
                    "Résultat net par action sur le résultat net des activités poursuivies (exprimé en cents de dollars EU par action) :",
                    "- Résultat de base par action 1,170 1,165",
                    "- Résultat dilué par action 1,170 1,165",
                    "Résultat net par action sur le résultat net des activités arrêtées (exprimé en cents de dollars EU par action) :",
                    "- Résultat de base par action - -",
                    "- Résultat dilué par action - -",
                ],
                page_number=2,
            ),
        ]
        result = extract_per_share_observations(pages, document_exercice=2023)
        promoted = [
            item
            for item in result["eps"]
            if item["currency"] == "FCFA" and item["eligible_fcfa_total_basic"]
        ]
        self.assertEqual(
            {(item["target_exercice"], item["value"]) for item in promoted},
            {(2023, 7.099), (2022, 7.064)},
        )
        self.assertTrue(
            all(item.get("basis_source") for item in promoted)
        )

    def test_publication_month_is_not_a_column_year(self):
        lines = ["RESULTATS FINANCIERS 2024", "Février 2025", "Compte de résultat"]
        self.assertIsNone(detect_column_years(lines))
        fiscal = detect_document_fiscal_year([self.page(lines)])
        self.assertIsNone(fiscal["exercice"])


if __name__ == "__main__":
    unittest.main()

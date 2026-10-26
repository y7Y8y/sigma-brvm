"use strict";

/* SIGMA — interface personnelle BRVM.
   Les données de marché viennent de data/data.json (sources officielles BRVM).
   Les données personnelles restent dans localStorage, sur cet appareil. */

const STORAGE_KEY = "sigma_personal_v1";
const DEFAULT_PERSONAL = {
  profile: null,
  sgiQuotes: [],
  watchlist: [],
  portfolios: {
    reel: { transactions: [] },
    virtuel: { transactions: [] }
  },
  journal: [],
  contextEvents: [],
  alertsRead: [],
  settings: {
    monthlyBudget: 200000,
    sgiName: "",
    feePct: "",
    fixedFee: "",
    decline5: -10,
    decline20: -15
  }
};

const GLOSSARY = {
  PER: "Prix de l'action divisé par le bénéfice net par action. Dans SIGMA, le PER affiché est celui publié par la BRVM dans le BOC, avec sa date.",
  "Rendement net": "Dernier dividende net par action divisé par le cours, tel que publié dans le BOC. Il peut augmenter mécaniquement quand le cours baisse.",
  "Liquidité": "Facilité à acheter ou vendre grâce à des échanges réguliers. SIGMA la décrit ici par le nombre de séances échangées et la valeur médiane négociée sur les BOC récents.",
  "Ex-dividende": "À partir de la date ex-dividende, l'action s'échange sans le droit au dividende annoncé. Le cours baisse souvent d'un montant proche du dividende : ce n'est pas automatiquement une mauvaise nouvelle.",
  "Largeur du marché": "Répartition des valeurs en hausse, en baisse ou inchangées. Elle permet de distinguer un mouvement général d'un mouvement concentré sur quelques grandes sociétés.",
  "BOC": "Bulletin Officiel de la Cote, publication quotidienne officielle de la BRVM. SIGMA cite la date et conserve l'empreinte SHA-256 des BOC utilisés pour l'historique.",
  "Maturité M0–M5": "Échelle SIGMA : rumeur, annonce officielle, financement engagé, mise en œuvre, effet économique visible, puis effet dans les résultats publiés. On surveille tôt, on ne conclut qu'avec des preuves.",
  "Radar SIGMA": "Premier tri automatique des sociétés cotées par règles quantitatives transparentes : échangeabilité réelle sur 20 séances, PER publié au BOC, rendement de dividende récent et non extrême. Il décide quoi étudier d'abord, jamais quoi acheter.",
  "Score d'étude": "Note de 0 à 100 qui ordonne les sociétés ayant passé les règles du Radar (liquidité 35, valorisation relative 35, rendement 30, en rangs parmi les éligibles). Ce n'est ni un score de qualité de l'entreprise, ni une probabilité de gain : les fondamentaux annuels restent à vérifier.",
  "SGI": "Société de Gestion et d'Intermédiation agréée : l'intermédiaire qui ouvre votre compte-titres et transmet vos ordres à la BRVM. La BRVM publie l'annuaire officiel des SGI (noms, pays, contacts) mais pas leurs grilles tarifaires : les frais doivent venir du document remis par votre SGI.",
  "Produit net bancaire": "Équivalent bancaire du chiffre d'affaires : marge d'intérêt (crédits moins dépôts rémunérés) plus commissions nettes. C'est le point de départ du compte de résultat d'une banque cotée à la BRVM.",
  "Capitaux propres": "Ce qui appartient aux actionnaires après paiement de toutes les dettes : capital, réserves et résultats accumulés. Les comparer au total du bilan donne une première mesure du coussin de sécurité de l'entreprise.",
  "États financiers": "Documents comptables officiels (bilan, compte de résultat, flux de trésorerie et annexes), audités chaque année. Dans SIGMA, les agrégats affichés sont lus automatiquement dans ces PDF avec leur page source, et restent « à confirmer » tant que plusieurs exercices n'ont pas été vérifiés."
};

const UEMOA_COUNTRIES = ["Bénin", "Burkina Faso", "Côte d'Ivoire", "Guinée-Bissau", "Mali", "Niger", "Sénégal", "Togo"];
const RISK_REACTION_LABELS = {
  renforcer: "renforcer progressivement si la thèse écrite reste intacte",
  attendre: "attendre, relire les publications, ne rien décider sous le coup du cours",
  alleger: "alléger la position après relecture documentée"
};

let DATA = null;
let COMPANIES = [];
let BY_TICKER = new Map();
let personal = loadPersonal();
let toastTimer = null;

const ui = {
  view: "accueil",
  selectedTicker: null,
  companySearch: "",
  companySector: "",
  companySort: "alpha",
  watchOnly: false,
  marketSector: "",
  marketSort: "variation_desc",
  analysisTab: "radar",
  portfolioKind: "reel",
  reportSearch: "",
  journalPrefill: null,
  news: { relevance: "pertinent", source: "", search: "", onlyMine: false },
  decision: {
    budget: personal.settings.monthlyBudget || 200000,
    source: "radar",
    sector: "",
    minSessions: 15,
    minMedianValue: "",
    criterion: "liquidity"
  }
};

function loadPersonal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_PERSONAL);
    const parsed = JSON.parse(raw);
    return {
      ...structuredClone(DEFAULT_PERSONAL),
      ...parsed,
      portfolios: {
        reel: { transactions: parsed?.portfolios?.reel?.transactions || [] },
        virtuel: { transactions: parsed?.portfolios?.virtuel?.transactions || [] }
      },
      settings: { ...DEFAULT_PERSONAL.settings, ...(parsed.settings || {}) }
    };
  } catch (_) {
    return structuredClone(DEFAULT_PERSONAL);
  }
}

function savePersonal() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(personal));
}

function $(selector, root = document) { return root.querySelector(selector); }
function $$(selector, root = document) { return [...root.querySelectorAll(selector)]; }
function isNum(value) { return typeof value === "number" && Number.isFinite(value); }
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}
function normalize(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}
function fmtNum(value, decimals = 0) {
  if (!isNum(value)) return "—";
  return new Intl.NumberFormat("fr-FR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value);
}
function fmtFCFA(value) { return isNum(value) ? `${fmtNum(value, 0)} FCFA` : "—"; }
function fmtCompactFCFA(value) {
  if (!isNum(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${fmtNum(value / 1_000_000_000, 2)} Md FCFA`;
  if (abs >= 1_000_000) return `${fmtNum(value / 1_000_000, 1)} M FCFA`;
  if (abs >= 1_000) return `${fmtNum(value / 1_000, 1)} k FCFA`;
  return fmtFCFA(value);
}
function fmtPct(value, decimals = 2, signed = true) {
  if (!isNum(value)) return "—";
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${fmtNum(value, decimals)} %`;
}
function fmtRatio(value) { return isNum(value) ? fmtNum(value, 2) : "—"; }
function fmtDate(iso) {
  if (!iso || typeof iso !== "string") return "—";
  const onlyDate = iso.slice(0, 10);
  const parts = onlyDate.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return iso;
  return new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])));
}
function fmtDateTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Abidjan" }).format(date);
}
function median(values) {
  const clean = values.filter(isNum).sort((a, b) => a - b);
  if (!clean.length) return null;
  const mid = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[mid] : (clean[mid - 1] + clean[mid]) / 2;
}
function variationPill(value) {
  if (!isNum(value)) return '<span class="pill">—</span>';
  const cls = value > 0 ? "green" : value < 0 ? "red" : "";
  const arrow = value > 0 ? "↗" : value < 0 ? "↘" : "→";
  return `<span class="pill ${cls}">${arrow} ${fmtPct(value)}</span>`;
}
function termButton(term, label = term) {
  return `<button type="button" class="term-button" data-term="${escapeHtml(term)}">${escapeHtml(label)}</button>`;
}
function latestBocDate() {
  const sessions = DATA?.history?.sessions || [];
  return sessions.length ? sessions[sessions.length - 1].date : null;
}
function latestPrice(company) {
  if (isNum(company?.latest_quote?.close)) {
    return { value: company.latest_quote.close, label: `Instantané BRVM · ${DATA.snapshot.source_updated_label || "date source non précisée"}` };
  }
  if (isNum(company?.latest_boc?.close)) {
    return { value: company.latest_boc.close, label: `BOC du ${fmtDate(company.latest_boc_date)}` };
  }
  return { value: null, label: "Cours non disponible" };
}
function isWatched(ticker) { return personal.watchlist.includes(ticker); }
function sectorList() { return [...new Set(COMPANIES.map(c => c.sector).filter(Boolean))].sort((a, b) => a.localeCompare(b, "fr")); }
function sectorMedian(field, sector) {
  return median(COMPANIES.filter(c => c.sector === sector).map(c => c.latest_boc?.[field]));
}
function parseBocShortDate(label) {
  if (!label || typeof label !== "string") return null;
  const match = label.trim().match(/^(\d{1,2})-([A-Za-zÀ-ÿ]+)\.?-(\d{2})$/);
  if (!match) return null;
  const months = {
    janv: 1, fevr: 2, mars: 3, avr: 4, mai: 5, juin: 6,
    juil: 7, aout: 8, sept: 9, oct: 10, nov: 11, dec: 12
  };
  const monthKey = normalize(match[2]).slice(0, 4);
  const month = months[monthKey] || months[normalize(match[2]).slice(0, 3)];
  if (!month) return null;
  const yy = Number(match[3]);
  const year = yy <= 69 ? 2000 + yy : 1900 + yy;
  return `${year}-${String(month).padStart(2, "0")}-${String(Number(match[1])).padStart(2, "0")}`;
}
function yieldScreenInfo(company) {
  const boc = company?.latest_boc || {};
  const value = boc.net_dividend_yield_pct;
  const dividendDate = parseBocShortDate(boc.last_dividend_date_label);
  const reference = latestBocDate();
  let ageDays = null;
  if (dividendDate && reference) {
    ageDays = Math.round((new Date(`${reference}T00:00:00Z`) - new Date(`${dividendDate}T00:00:00Z`)) / 86400000);
  }
  if (!isNum(value)) return { usable: false, value, dividendDate, ageDays, reason: "rendement non publié" };
  if (value <= 0) return { usable: false, value, dividendDate, ageDays, reason: "rendement nul ou négatif" };
  if (value > 15) return { usable: false, value, dividendDate, ageDays, reason: "rendement extrême à vérifier (possible caractère exceptionnel)" };
  if (!dividendDate) return { usable: false, value, dividendDate, ageDays, reason: "date du dernier dividende BOC illisible" };
  if (ageDays === null || ageDays < 0 || ageDays > 548) {
    return { usable: false, value, dividendDate, ageDays, reason: "dernier dividende BOC datant de plus de 18 mois" };
  }
  return { usable: true, value, dividendDate, ageDays, reason: "rendement récent et non extrême" };
}
function sectorUsableYieldMedian(sector) {
  return median(COMPANIES.filter(c => c.sector === sector && yieldScreenInfo(c).usable).map(c => c.latest_boc?.net_dividend_yield_pct));
}
function ratioWarning(company) {
  const boc = company?.latest_boc || {};
  const yieldInfo = yieldScreenInfo(company);
  const warnings = [];
  if (isNum(boc.per) && boc.per > 60) warnings.push("PER extrême à vérifier");
  if (isNum(boc.net_dividend_yield_pct) && !yieldInfo.usable) warnings.push(yieldInfo.reason);
  return warnings.length ? `<div style="margin-top:5px"><span class="pill amber">${escapeHtml(warnings.join(" · "))}</span></div>` : "";
}

function canonicalIssuerName(value) {
  let text = ` ${normalize(value)} `;
  const countryCodes = {
    " ci ": " cote d ivoire ", " sn ": " senegal ", " bf ": " burkina faso ",
    " bn ": " benin ", " bj ": " benin ", " ml ": " mali ", " ng ": " niger ", " ne ": " niger ", " tg ": " togo "
  };
  for (const [code, country] of Object.entries(countryCodes)) text = text.replaceAll(code, country);
  return text.replace(/\b(sa|sarl|sas)\b/g, " ").replace(/\s+/g, " ").trim();
}
const ISSUER_ALIASES = {
  "smb": "SMBC",
  "sib": "SIBC",
  "sodeci": "SDCC",
  "nei ceda cote d ivoire": "NEIC",
  "tractafric cote d ivoire": "PRSC",
  "tractafric motors cote d ivoire": "PRSC"
};
function matchIssuerToTicker(issuer) {
  const key = canonicalIssuerName(issuer);
  if (ISSUER_ALIASES[key] && BY_TICKER.has(ISSUER_ALIASES[key])) return ISSUER_ALIASES[key];
  const matches = [];
  for (const company of COMPANIES) {
    const variants = [company.name, company.latest_boc?.name].filter(Boolean).map(canonicalIssuerName);
    if (variants.some(v => v === key || v.startsWith(`${key} `) || key.startsWith(`${v} `))) matches.push(company.ticker);
  }
  return matches.length === 1 ? matches[0] : null;
}
function dividendsForTicker(ticker) {
  return (DATA?.dividends || []).filter(item => (item.tickers || []).includes(ticker) || matchIssuerToTicker(item.issuer) === ticker);
}
function dividendHistoryLabel(company) {
  const hist = company?.dividend_history || {};
  if (!hist.paid_fiscal_years_count) return "aucun exercice documenté dans le tableau BRVM collecté";
  return `${hist.paid_last_5_fiscal_years ?? 0}/5 derniers exercices documentés · ${hist.paid_fiscal_years_count} exercice(s) au total`;
}

/* ---------------------------------------------------------------------------
   Radar SIGMA — premier tri automatique par règles quantitatives transparentes.
   La machine classe tout l'univers coté à chaque collecte ; l'humain étudie
   ensuite la sélection. Les seuils ci-dessous sont affichés dans l'écran Radar.
---------------------------------------------------------------------------- */
const RADAR_RULES = {
  minTradedSessions: 15,
  minMedianTradedValue: 5000000,
  maxPer: 25,
  weights: { liquidity: 35, valuation: 35, yield: 30 },
  selectionSize: 8,
  maxPerSector: 3
};

function percentileRank(values, value) {
  const clean = values.filter(isNum);
  if (!clean.length || !isNum(value)) return 0;
  const below = clean.filter(v => v < value).length;
  const equal = clean.filter(v => v === value).length;
  return (below + equal / 2) / clean.length;
}

function newsItems() { return DATA?.news || []; }
function newsForTicker(ticker, limit = 6) {
  return newsItems().filter(item => (item.tickers || []).includes(ticker)).slice(0, limit);
}
function daysBeforeIso(isoDate, days) {
  const base = new Date(`${isoDate}T00:00:00Z`);
  base.setUTCDate(base.getUTCDate() - days);
  return base.toISOString().slice(0, 10);
}

function computeRadar() {
  const rules = RADAR_RULES;
  const eligibleRaw = [];
  const rejected = [];
  for (const company of COMPANIES) {
    const stats = company.history_stats || {};
    const boc = company.latest_boc || {};
    const price = latestPrice(company).value;
    const yieldInfo = yieldScreenInfo(company);
    const reasons = [];
    if (!isNum(price) || price <= 0) reasons.push("cours publié absent");
    if ((stats.traded_sessions_last_20 ?? 0) < rules.minTradedSessions) {
      reasons.push(`échangée ${fmtNum(stats.traded_sessions_last_20 ?? 0)}/20 séances (minimum ${rules.minTradedSessions})`);
    }
    if ((stats.median_traded_value_last_20_fcfa ?? 0) < rules.minMedianTradedValue) {
      reasons.push(`valeur médiane échangée ${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)} par séance (minimum ${fmtCompactFCFA(rules.minMedianTradedValue)})`);
    }
    if (!isNum(boc.per) || boc.per <= 0) reasons.push("PER non publié au BOC (bénéfice par action négatif ou non communiqué)");
    else if (boc.per > rules.maxPer) reasons.push(`PER publié au BOC de ${fmtRatio(boc.per)} (plafond Radar ${rules.maxPer})`);
    if (!yieldInfo.usable) reasons.push(`dividende écarté : ${yieldInfo.reason}`);
    if (reasons.length) { rejected.push({ company, reasons }); continue; }
    eligibleRaw.push({ company, price, yieldInfo });
  }

  const sessionsValues = eligibleRaw.map(e => e.company.history_stats?.traded_sessions_last_20);
  const medianValues = eligibleRaw.map(e => e.company.history_stats?.median_traded_value_last_20_fcfa);
  const perValues = eligibleRaw.map(e => e.company.latest_boc?.per);
  const yieldValues = eligibleRaw.map(e => e.company.latest_boc?.net_dividend_yield_pct);
  const referenceDate = DATA.generated_at.slice(0, 10);
  const newsCutoff = daysBeforeIso(referenceDate, 45);

  const scored = eligibleRaw.map(entry => {
    const stats = entry.company.history_stats || {};
    const boc = entry.company.latest_boc || {};
    const liquidityRank = 0.5 * percentileRank(sessionsValues, stats.traded_sessions_last_20)
      + 0.5 * percentileRank(medianValues, stats.median_traded_value_last_20_fcfa);
    const valuationRank = 1 - percentileRank(perValues, boc.per);
    const yieldRank = percentileRank(yieldValues, boc.net_dividend_yield_pct);
    const parts = {
      liquidity: Math.round(liquidityRank * rules.weights.liquidity),
      valuation: Math.round(valuationRank * rules.weights.valuation),
      yield: Math.round(yieldRank * rules.weights.yield)
    };
    const flags = [];
    if (isNum(stats.performance_20_sessions_pct) && stats.performance_20_sessions_pct <= Number(personal.settings.decline20)) {
      flags.push({ tone: "red", text: `Cours en baisse de ${fmtPct(stats.performance_20_sessions_pct)} sur 20 séances : passer par la checklist baisse avant toute thèse.` });
    }
    if (isNum(stats.performance_20_sessions_pct) && stats.performance_20_sessions_pct >= 15) {
      flags.push({ tone: "amber", text: `Cours en hausse de ${fmtPct(stats.performance_20_sessions_pct)} sur 20 séances : le prix a déjà intégré une partie de l'optimisme.` });
    }
    const dividendHist = entry.company.dividend_history || {};
    if (isNum(dividendHist.paid_last_5_fiscal_years) && dividendHist.paid_last_5_fiscal_years < 3) {
      flags.push({ tone: "amber", text: `Rendement BOC récent, mais historique BRVM documenté sur ${dividendHist.paid_last_5_fiscal_years}/5 derniers exercices seulement : régularité à vérifier dans la fiche.` });
    } else if (dividendHist.paid_last_5_fiscal_years === 5) {
      flags.push({ tone: "green", text: "Distributions documentées sur les 5 derniers exercices du tableau BRVM ; le taux de distribution reste à vérifier." });
    }
    const recentNews = newsForTicker(entry.company.ticker, 30)
      .filter(item => item.published_date && item.published_date >= newsCutoff);
    if (recentNews.length) {
      flags.push({ tone: "green", text: `${recentNews.length} publication(s) rattachée(s) sur 45 jours : à lire avant de conclure.` });
    }
    return {
      ...entry, parts,
      score: parts.liquidity + parts.valuation + parts.yield,
      flags, sectorPer: sectorMedian("per", entry.company.sector)
    };
  }).sort((a, b) => b.score - a.score);

  const selection = [];
  const overflow = [];
  const perSector = new Map();
  for (const entry of scored) {
    const count = perSector.get(entry.company.sector) || 0;
    if (selection.length < rules.selectionSize && count < rules.maxPerSector) {
      selection.push(entry);
      perSector.set(entry.company.sector, count + 1);
    } else {
      overflow.push(entry);
    }
  }
  return { selection, overflow, rejected, scored };
}

const DOC_TYPE_LABELS = {
  etats_financiers_approuves: "États financiers annuels approuvés",
  etats_financiers: "États financiers annuels",
  rapport_activites_annuel: "Rapport d'activité annuel",
  rapport_annuel: "Rapport annuel",
  resultats_consolides: "Résultats consolidés",
  activite_trimestrielle: "Rapport d'activité trimestriel",
  activite_semestrielle: "Rapport d'activité semestriel",
  attestation_cac: "Attestation des commissaires aux comptes",
  rse: "Rapport RSE",
  autre: "Document officiel"
};

const NEWS_TAG_LABELS = {
  dividende: "Dividende", resultats: "Résultats", gouvernance: "Gouvernance",
  notation: "Notation", vie_sociale: "Vie sociale", politique_monetaire: "Politique monétaire",
  dette_publique: "Dette publique", matieres_premieres: "Matières premières", regulation: "Régulation"
};

function newsItemHtml(item) {
  const official = item.source_type !== "presse_specialisee";
  const dateLabel = item.published_date
    ? fmtDate(item.published_date) + (item.date_type === "mentionnee_dans_texte" ? " · date mentionnée dans le texte" : "")
    : "Date non publiée par la source";
  const tickerChips = (item.tickers || []).map(ticker =>
    `<button type="button" class="tag-chip ticker-chip" data-open-company="${ticker}" title="Ouvrir la fiche">${ticker}</button>`).join(" ");
  const tagChips = (item.tags || []).map(tag =>
    `<span class="tag-chip">${escapeHtml(NEWS_TAG_LABELS[tag] || tag)}</span>`).join(" ");
  return `<div class="news-item">
    <div class="news-meta">
      <span class="pill ${official ? "green" : "amber"}">${official ? "Officiel" : "Presse"}</span>
      <span class="strong">${escapeHtml(item.source_label)}</span>
      <span class="tag-chip">${escapeHtml(item.category || "")}</span>${tickerChips}${tagChips}
    </div>
    <a class="news-title" href="${escapeHtml(item.url)}" target="_blank" rel="noopener">${escapeHtml(item.title)}</a>
    ${item.excerpt ? `<p class="news-excerpt">${escapeHtml(item.excerpt)}</p>` : ""}
    <div class="subtext" style="margin-top:4px">${dateLabel}${item.document_type === "pdf" ? " · Document PDF de l'émetteur" : ""}${(item.tickers || []).length ? " · rattachement automatique à confirmer à la lecture" : ""}</div>
  </div>`;
}

function lineChart(points, { height = 230, money = false } = {}) {
  const clean = points.filter(p => isNum(p.value));
  if (clean.length < 2) return '<div class="Empty-state">Historique insuffisant pour tracer une courbe.</div>';
  const width = 760, margin = { left: 54, right: 16, top: 14, bottom: 32 };
  const values = clean.map(p => p.value);
  let min = Math.min(...values), max = Math.max(...values);
  const pad = (max - min || Math.abs(max) * 0.04 || 1) * 0.12;
  min -= pad; max += pad;
  const x = index => margin.left + (index / (clean.length - 1)) * (width - margin.left - margin.right);
  const y = value => margin.top + (1 - ((value - min) / (max - min))) * (height - margin.top - margin.bottom);
  const path = clean.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const area = `${path} L${x(clean.length - 1).toFixed(1)},${height - margin.bottom} L${x(0).toFixed(1)},${height - margin.bottom} Z`;
  const grid = [0, 1, 2, 3].map(i => {
    const value = min + ((max - min) * i) / 3;
    const yy = y(value);
    const label = money ? fmtCompactFCFA(value).replace(" FCFA", "") : fmtNum(value, value < 20 ? 1 : 0);
    return `<line class="chart-grid" x1="${margin.left}" y1="${yy}" x2="${width - margin.right}" y2="${yy}"/><text class="chart-axis" x="4" y="${yy + 4}">${escapeHtml(label)}</text>`;
  }).join("");
  const last = clean[clean.length - 1];
  return `<div class="chart-box" role="img" aria-label="Graphique de ${clean.length} points, de ${fmtDate(clean[0].date)} à ${fmtDate(last.date)}">
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      ${grid}<path class="chart-area" d="${area}"/><path class="chart-line" d="${path}"/>
      <circle class="chart-dot" cx="${x(clean.length - 1)}" cy="${y(last.value)}" r="4"/>
      <text class="chart-axis" x="${margin.left}" y="${height - 8}">${fmtDate(clean[0].date)}</text>
      <text class="chart-axis" x="${width - margin.right}" y="${height - 8}" text-anchor="end">${fmtDate(last.date)}</text>
    </svg></div>`;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 3600);
}
function showView(view, ticker = null) {
  ui.view = view;
  if (ticker) ui.selectedTicker = ticker;
  $$(".view").forEach(section => section.classList.toggle("is-active", section.id === `view-${view}`));
  $$(".nav-item").forEach(button => button.classList.toggle("is-active", button.dataset.view === view));
  const target = view === "fiche" && ui.selectedTicker ? `fiche-${ui.selectedTicker}` : view;
  history.replaceState(null, "", `#${target}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (view === "fiche") renderCompanyDetail();
}
function toggleWatch(ticker) {
  personal.watchlist = isWatched(ticker)
    ? personal.watchlist.filter(item => item !== ticker)
    : [...personal.watchlist, ticker].sort();
  savePersonal();
  renderDynamic();
  showToast(isWatched(ticker) ? `${ticker} ajouté à votre watchlist.` : `${ticker} retiré de votre watchlist.`);
}

function computePortfolio(kind) {
  const transactions = [...(personal.portfolios[kind]?.transactions || [])]
    .sort((a, b) => String(a.date).localeCompare(String(b.date)) || String(a.createdAt).localeCompare(String(b.createdAt)));
  const positions = new Map();
  let realised = 0, dividendsCash = 0, netContributions = 0;
  const warnings = [];
  const ensure = ticker => {
    if (!positions.has(ticker)) positions.set(ticker, { ticker, qty: 0, costBasis: 0 });
    return positions.get(ticker);
  };
  for (const tx of transactions) {
    const pos = ensure(tx.ticker);
    const qty = Number(tx.qty) || 0, price = Number(tx.price) || 0, fees = Number(tx.fees) || 0;
    if (tx.type === "achat") {
      const cost = qty * price + fees;
      pos.qty += qty; pos.costBasis += cost; netContributions += cost;
    } else if (tx.type === "vente") {
      const sellQty = Math.min(qty, pos.qty);
      if (qty > pos.qty) warnings.push(`Vente ${tx.ticker} du ${fmtDate(tx.date)} supérieure à la quantité détenue : excédent ignoré.`);
      if (sellQty > 0) {
        const avg = pos.qty ? pos.costBasis / pos.qty : 0;
        const proceeds = sellQty * price - fees;
        realised += proceeds - avg * sellQty;
        netContributions -= proceeds;
        pos.qty -= sellQty; pos.costBasis -= avg * sellQty;
        if (pos.qty === 0) pos.costBasis = 0;
      }
    } else if (tx.type === "dividende") {
      dividendsCash += Number(tx.amount) || 0;
    }
  }
  const holdings = [...positions.values()].filter(p => p.qty > 0).map(pos => {
    const company = BY_TICKER.get(pos.ticker);
    const priceInfo = company ? latestPrice(company) : { value: null, label: "Cours introuvable" };
    const marketValue = isNum(priceInfo.value) ? pos.qty * priceInfo.value : null;
    return {
      ...pos, company, avgCost: pos.qty ? pos.costBasis / pos.qty : null,
      price: priceInfo.value, priceLabel: priceInfo.label, marketValue,
      latent: isNum(marketValue) ? marketValue - pos.costBasis : null
    };
  });
  const marketValue = holdings.reduce((sum, h) => sum + (h.marketValue || 0), 0);
  holdings.forEach(h => { h.weightPct = marketValue ? ((h.marketValue || 0) / marketValue) * 100 : 0; });
  return { transactions, holdings, realised, dividendsCash, netContributions, marketValue, warnings };
}
function heldTickers() {
  return [...new Set([...computePortfolio("reel").holdings, ...computePortfolio("virtuel").holdings].map(h => h.ticker))];
}

function macroContext() {
  return DATA?.macro_context || {};
}

function calendarEvents(limit = Infinity) {
  const referenceDate = DATA?.generated_at?.slice(0, 10);
  return [...(DATA?.calendar_events || [])]
    .filter(event => event?.date && (!referenceDate || event.date >= referenceDate))
    .sort((a, b) => String(a.date).localeCompare(String(b.date)) || String(a.title).localeCompare(String(b.title), "fr"))
    .slice(0, limit);
}

function calendarEventAmount(event) {
  if (!isNum(event.amount_fcfa)) return "";
  return String(event.amount_label || "").includes("par action")
    ? `${fmtFCFA(event.amount_fcfa)} / action`
    : fmtCompactFCFA(event.amount_fcfa);
}

function calendarEventHtml(event) {
  const ticker = (event.tickers || [])[0] || matchIssuerToTicker(event.issuer_label || "");
  const amount = calendarEventAmount(event);
  const when = isNum(event.in_days) ? (event.in_days === 0 ? "aujourd’hui à la collecte" : `J+${event.in_days} à la collecte`) : "";
  return `<li class="event-row"><div><div class="strong">${escapeHtml(event.title)}</div><div class="subtext">${fmtDate(event.date)} · ${escapeHtml(event.category || "Échéance")}${when ? ` · ${when}` : ""}</div><div class="subtext">${escapeHtml(event.detail || "")}</div></div><div style="text-align:right">${amount ? `<div class="strong">${amount}</div>` : ""}<div class="form-actions" style="justify-content:flex-end;margin-top:6px">${ticker && BY_TICKER.has(ticker) ? `<button type="button" class="button button-secondary button-small" data-open-company="${ticker}">Fiche ${ticker}</button>` : ""}${event.url ? `<a class="button button-secondary button-small" href="${event.url}" target="_blank" rel="noopener">Source</a>` : ""}</div></div></li>`;
}

function macroCalendarCard({ compact = false } = {}) {
  const macro = macroContext();
  const cpm = macro.bceao_cpm || {};
  const umoa = macro.umoa_summary || {};
  const windows = umoa.windows || {};
  const events = calendarEvents(compact ? 5 : 8);
  const topCountries = (umoa.by_country_next_90d || []).slice(0, 4);
  const cpmFacts = cpm.status === "collecte" ? `
    <div class="grid-4" style="margin-top:14px">
      <div class="key-fact"><span class="metric-label">Taux directeur BCEAO</span><div class="metric-value">${fmtPct(cpm.policy_rate_pct, 2, false)}</div><div class="subtext">CPM du ${fmtDate(cpm.meeting_date || cpm.published_date)}${cpm.rates_effective_since ? ` · en vigueur depuis le ${fmtDate(cpm.rates_effective_since)}` : ""}</div></div>
      <div class="key-fact"><span class="metric-label">Prêt marginal</span><div class="metric-value">${fmtPct(cpm.marginal_lending_rate_pct, 2, false)}</div><div class="subtext">Réserves obligatoires : ${fmtPct(cpm.reserve_requirement_pct, 2, false)}</div></div>
      <div class="key-fact"><span class="metric-label">Inflation UEMOA (CPM)</span><div class="metric-value">${fmtPct(cpm.inflation_latest_pct, 1, false)}</div><div class="subtext">${escapeHtml(cpm.inflation_latest_period || "Période citée au communiqué")}${isNum(cpm.inflation_forecast_pct) ? ` · prévision ${cpm.inflation_forecast_year} : ${fmtPct(cpm.inflation_forecast_pct, 1, false)}` : ""}</div></div>
      <div class="key-fact"><span class="metric-label">Croissance UEMOA (CPM)</span><div class="metric-value">${fmtPct(cpm.growth_latest_pct, 1, false)}</div><div class="subtext">${escapeHtml(cpm.growth_latest_period || "Période citée au communiqué")}${isNum(cpm.growth_forecast_pct) ? ` · attendue ${cpm.growth_forecast_year} : ${fmtPct(cpm.growth_forecast_pct, 1, false)}` : ""}</div></div>
    </div>` : `<div class="Empty-state" style="margin-top:14px">Dernier communiqué CPM BCEAO : <strong>non extrait proprement</strong>. SIGMA ne déduit aucun taux d’un titre d’actualité ; la source reste dans Actualités.</div>`;
  const umoaFacts = umoa.status === "collecte" ? `
    <div class="key-facts" style="margin-top:14px">
      <div class="key-fact"><span class="metric-label">Émissions UMOA à venir</span><div class="metric-value">${fmtNum(umoa.upcoming_operations || 0)}</div><div class="subtext">Prochaine : ${umoa.next_operation ? `${escapeHtml(umoa.next_operation.issuer_country)} · ${fmtDate(umoa.next_operation.operation_date)} · ${fmtCompactFCFA(umoa.next_operation.amount_fcfa)}` : "—"}</div></div>
      <div class="key-fact"><span class="metric-label">Montants annoncés · 30 jours</span><div class="metric-value">${fmtCompactFCFA(windows.next_30d?.amount_fcfa)}</div><div class="subtext">${fmtNum(windows.next_30d?.operations || 0)} opération(s) · 90 jours : ${fmtCompactFCFA(windows.next_90d?.amount_fcfa)}</div></div>
      ${topCountries.length ? `<div class="key-fact"><span class="metric-label">Plus gros programmes · 90 jours</span><div class="subtext" style="font-size:13px;color:var(--text)">${topCountries.map(item => `${escapeHtml(item.issuer_country)} : ${fmtCompactFCFA(item.amount_fcfa)} (${item.operations} op.)`).join(" · ")}</div></div>` : ""}
    </div>` : `<div class="Empty-state" style="margin-top:14px">Tableaux UMOA-Titres des émissions : <strong>non disponibles</strong> dans cette collecte.</div>`;
  return `<article class="card section-space">
    <div class="event-row"><div><p class="eyebrow">Macro UEMOA automatisée</p><h2>Taux BCEAO, titres publics et échéances</h2></div><button type="button" class="button button-secondary button-small" data-view-link="actualites">Fil macro</button></div>
    ${cpmFacts}
    <div class="grid-2" style="margin-top:14px">
      <div>
        ${umoaFacts}
        ${!compact && cpm.decision_excerpt ? `<details style="margin-top:12px"><summary class="strong" style="cursor:pointer">Décision CPM — texte source relu</summary><p class="small">${escapeHtml(cpm.decision_excerpt)}</p>${cpm.source_url ? `<a class="button button-secondary button-small" href="${cpm.source_url}" target="_blank" rel="noopener">Communiqué BCEAO</a>` : ""}</details>` : ""}
        <p class="source-line">Lecture : les taux BCEAO et les émissions souveraines décrivent le coût/liquidité de l’argent dans l’Union. SIGMA les utilise comme contexte daté, jamais comme signal automatique d’achat ou de vente.</p>
      </div>
      <div>
        <h3 style="margin-top:0">Prochaines échéances sourcées</h3>
        ${events.length ? `<ul class="list-clean">${events.map(calendarEventHtml).join("")}</ul>` : '<div class="Empty-state">Aucune échéance future datée par une source officielle dans cette collecte.</div>'}
        <div class="form-actions"><button type="button" class="button button-secondary button-small" data-view-link="rapports">Calendrier complet dans Rapports</button></div>
      </div>
    </div>
    ${(macro.notes || []).length ? `<p class="source-line">${macro.notes.map(escapeHtml).join(" ")}</p>` : ""}
  </article>`;
}

function generateAlerts() {
  if (!DATA) return [];
  const alerts = [];
  const referenceDate = DATA.generated_at.slice(0, 10);
  for (const div of [...DATA.dividends].filter(d => d.ex_date && d.ex_date >= referenceDate).sort((a, b) => a.ex_date.localeCompare(b.ex_date))) {
    const ticker = matchIssuerToTicker(div.issuer);
    alerts.push({
      id: `div-${div.issuer}-${div.ex_date}-${div.net_amount_fcfa}`,
      type: "dividende", icon: "◈", tone: "green",
      title: `Dividende à venir — ${div.issuer}`,
      body: `${fmtFCFA(div.net_amount_fcfa)} net par action · ex-dividende le ${fmtDate(div.ex_date)} · paiement le ${fmtDate(div.payment_date)}.`,
      meta: ticker ? `Rattaché à ${ticker} par nom d'émetteur · Avis officiel lié.` : "Avis officiel BRVM lié ; ticker non rattaché automatiquement.",
      ticker, url: div.notice_url, date: div.ex_date
    });
  }
  const relevant = [...new Set([...personal.watchlist, ...heldTickers()])];
  for (const ticker of relevant) {
    const company = BY_TICKER.get(ticker);
    if (!company) continue;
    const stats = company.history_stats || {};
    const hit5 = isNum(stats.performance_5_sessions_pct) && stats.performance_5_sessions_pct <= personal.settings.decline5;
    const hit20 = isNum(stats.performance_20_sessions_pct) && stats.performance_20_sessions_pct <= personal.settings.decline20;
    if (hit5 || hit20) {
      alerts.push({
        id: `baisse-${ticker}-${latestBocDate()}`,
        type: "baisse", icon: "↘", tone: "red", ticker,
        title: `Baisse à examiner — ${ticker}`,
        body: `Cours BOC : ${fmtPct(stats.performance_5_sessions_pct)} sur 5 séances · ${fmtPct(stats.performance_20_sessions_pct)} sur 20 séances (prix seuls, dividendes non réinvestis).`,
        meta: `Dernier BOC utilisé : ${fmtDate(latestBocDate())}. Ouvrir la checklist avant toute conclusion.`,
        date: latestBocDate()
      });
    }
  }
  const newsCutoff = daysBeforeIso(referenceDate, 21);
  for (const ticker of relevant) {
    for (const item of newsForTicker(ticker, 40)) {
      if (item.source_type === "presse_specialisee") continue;
      if (!item.published_date || item.published_date < newsCutoff) continue;
      alerts.push({
        id: `pub-${item.id}`, type: "publication", icon: "≣", tone: "green", ticker,
        title: `Publication officielle — ${ticker}`,
        body: item.title,
        meta: `${item.source_label} · ${fmtDate(item.published_date)} · ${item.category || ""}. Document source lié.`,
        url: item.url, date: item.published_date
      });
    }
  }
  const macro = macroContext();
  const cpm = macro.bceao_cpm || {};
  if (cpm.status === "collecte" && cpm.published_date && cpm.published_date >= daysBeforeIso(referenceDate, 60)) {
    alerts.push({
      id: `bceao-cpm-${cpm.published_date}-${cpm.policy_rate_pct}`,
      type: "macro", icon: "◫", tone: "amber",
      title: "Contexte BCEAO — dernier CPM relu",
      body: `Taux directeur ${fmtPct(cpm.policy_rate_pct, 2, false)} · prêt marginal ${fmtPct(cpm.marginal_lending_rate_pct, 2, false)} · inflation citée ${fmtPct(cpm.inflation_latest_pct, 1, false)} (${cpm.inflation_latest_period || "période du communiqué"}).`,
      meta: `Communiqué BCEAO du ${fmtDate(cpm.published_date)}. Contexte de taux/liquidité, pas un signal de transaction.`,
      url: cpm.source_url, date: cpm.published_date
    });
  }
  for (const event of calendarEvents().filter(item => !String(item.type).startsWith("dividende") && isNum(item.in_days) && item.in_days <= 30).slice(0, 5)) {
    alerts.push({
      id: `calendar-${event.id}`,
      type: "echeance", icon: "◷", tone: "amber",
      title: `Échéance macro — ${event.title}`,
      body: `${fmtDate(event.date)} · ${calendarEventAmount(event) || "Montant non publié dans le tableau"} · ${event.detail || ""}`,
      meta: `${event.source_label} · Date publiée par la source ; à la collecte : J+${event.in_days}.`,
      url: event.url, date: event.date
    });
  }
  for (const warning of DATA.quality_warnings || []) {
    alerts.push({ id: `quality-${warning}`, type: "qualite", icon: "!", tone: "amber", title: "Avertissement de qualité des données", body: warning, meta: "La dernière version valide reste affichée.", date: referenceDate });
  }
  alerts.push({
    id: `couverture-${DATA.generated_at.slice(0, 10)}`, type: "info", icon: "Σ", tone: "amber",
    title: "Couverture fondamentale : piliers conditionnels",
    body: "SIGMA publie Solidité et Croissance uniquement lorsque la série d’états financiers officiels est suffisante et recoupée. L’historique BRVM des dividendes nets par exercice est affiché en fiche ; le pilier Dividende durable et le score global restent suspendus tant que le taux de distribution et la couverture par les flux ne sont pas calculables de façon vérifiée.",
    meta: "Aucun chiffre fondamental n'a été inventé pour combler ce manque.", date: referenceDate
  });
  return alerts.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
}
function unreadAlertCount() {
  return generateAlerts().filter(alert => !personal.alertsRead.includes(alert.id)).length;
}

function renderFreshness() {
  const latest = latestBocDate();
  $("#sidebarFreshness").innerHTML = `<span class="strong">${COMPANIES.length} sociétés</span><br>Instantané : ${escapeHtml(DATA.snapshot.source_updated_label || "date non précisée")}<br>Dernier BOC lu : ${fmtDate(latest)}<br>Collecte : ${fmtDateTime(DATA.generated_at)}`;
  const generated = new Date(DATA.generated_at);
  const ageHours = (Date.now() - generated.getTime()) / 36e5;
  const pill = $("#freshnessPill");
  pill.textContent = `BRVM · ${DATA.snapshot.session_status} · BOC ${fmtDate(latest)}`;
  pill.classList.toggle("is-ok", ageHours <= 30);
  pill.classList.toggle("is-stale", ageHours > 30);
  $("#homeSourceChip").textContent = `Sources : brvm.org · collecte du ${fmtDateTime(DATA.generated_at)}`;
  const bocLink = $("#latestBocLink");
  const latestDoc = DATA.boc_documents.find(doc => doc.parsed);
  if (latestDoc) { bocLink.href = latestDoc.url; bocLink.hidden = false; bocLink.textContent = `BOC officiel du ${fmtDate(latestDoc.date)}`; }
}

function companyMiniRow(company, extra = "") {
  const quote = company.latest_quote || {};
  return `<li class="event-row">
    <div><button type="button" class="text-button ticker" data-open-company="${company.ticker}">${company.ticker}</button>
      <div class="subtext">${escapeHtml(company.name)} · ${escapeHtml(company.sector)}</div>${extra}</div>
    <div style="text-align:right"><div class="strong">${fmtFCFA(quote.close)}</div>${variationPill(quote.variation_pct)}</div>
  </li>`;
}

function renderHome() {
  const host = $("#homeContent");
  if (!host) return;
  const activity = DATA.snapshot.activity || {};
  const indices = DATA.snapshot.indices || [];
  const composite = indices.find(i => normalize(i.name).includes("brvm c")) || indices[0] || {};
  const structure = DATA.market_structure.snapshot;
  const bocStructure = DATA.market_structure.latest_boc;
  const compositePoints = DATA.history.sessions.map(s => ({ date: s.date, value: s.composite_level }));
  const relevantTickers = [...new Set([...personal.watchlist, ...heldTickers()])];
  const relevantCompanies = relevantTickers.map(t => BY_TICKER.get(t)).filter(Boolean);
  const referenceDate = DATA.generated_at.slice(0, 10);
  const upcoming = [...DATA.dividends].filter(d => d.ex_date && d.ex_date >= referenceDate).sort((a, b) => a.ex_date.localeCompare(b.ex_date)).slice(0, 4);
  const quoted = COMPANIES.filter(c => isNum(c.latest_quote?.variation_pct));
  const top = [...quoted].sort((a, b) => b.latest_quote.variation_pct - a.latest_quote.variation_pct).slice(0, 4);
  const flop = [...quoted].sort((a, b) => a.latest_quote.variation_pct - b.latest_quote.variation_pct).slice(0, 4);
  const radar = computeRadar();
  const latestNews = newsItems().filter(item => item.relevance !== "general").slice(0, 4);

  host.innerHTML = `
    <div class="grid-4">
      <article class="card kpi-card"><span class="kpi-label">BRVM Composite</span><div><div class="kpi-value">${fmtNum(composite.level, 2)}</div><div class="kpi-sub">${variationPill(composite.variation_pct)} <span class="muted">instantané officiel</span></div></div></article>
      ${indices.slice(1, 3).map(index => `<article class="card kpi-card"><span class="kpi-label">${escapeHtml(index.name)}</span><div><div class="kpi-value">${fmtNum(index.level, 2)}</div><div class="kpi-sub">${variationPill(index.variation_pct)}</div></div></article>`).join("")}
      <article class="card kpi-card"><span class="kpi-label">Valeur des transactions</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(activity["Valeur des transactions"]?.value)}</div><div class="kpi-sub muted">Activité publiée par la BRVM</div></div></article>
    </div>

    <div class="grid-2 section-space">
      <article class="card">
        <div class="event-row"><div><p class="eyebrow">Sélection automatique du moment</p><h2>Radar SIGMA — à étudier en premier</h2></div><button type="button" class="button button-secondary button-small" data-analysis-link="radar">Règles &amp; classement</button></div>
        ${radar.selection.length ? `<ul class="list-clean">${radar.selection.slice(0, 3).map((entry, index) => `<li class="event-row"><div style="display:flex;gap:10px;align-items:center"><span class="radar-rank">${index + 1}</span><div><button type="button" class="text-button ticker" data-open-company="${entry.company.ticker}">${entry.company.ticker}</button><div class="subtext">${escapeHtml(entry.company.name)} · PER BOC ${fmtRatio(entry.company.latest_boc?.per)} · rendement ${fmtPct(entry.company.latest_boc?.net_dividend_yield_pct, 2, false)}</div></div></div><div style="text-align:right"><div class="score-total" style="font-size:18px">${entry.score}<span style="font-size:11px">/100</span></div><div class="subtext">score d'étude</div></div></li>`).join("")}</ul>` : '<div class="Empty-state">Aucune société ne passe les règles du Radar avec les données actuelles.</div>'}
        <p class="source-line">Premier tri par règles quantitatives transparentes (échangeabilité, PER publié, dividende documenté). Ordre de lecture, jamais ordre d'achat — les piliers fondamentaux restent conditionnés aux séries recoupées affichées en fiche.</p>
      </article>
      <article class="card">
        <div class="event-row"><div><p class="eyebrow">Collecte automatique</p><h2>Dernières publications</h2></div><button type="button" class="button button-secondary button-small" data-view-link="actualites">Tout le fil</button></div>
        ${latestNews.length ? latestNews.map(newsItemHtml).join("") : '<div class="Empty-state">Aucune publication collectée à ce stade.</div>'}
      </article>
    </div>

    <div class="grid-2 section-space">
      <article class="card">
        <div class="event-row"><div><p class="eyebrow">Historique officiel BOC</p><h2>BRVM Composite — ${compositePoints.length} séances lues</h2></div><span class="pill dark">BOC ${fmtDate(latestBocDate())}</span></div>
        ${lineChart(compositePoints)}
        <p class="source-line">Niveaux d’indice imprimés dans les Bulletins Officiels de la Cote. L’instantané du jour peut être plus récent que le dernier BOC publié.</p>
      </article>
      <article class="card">
        <p class="eyebrow">À connaître</p><h2>Prochains dividendes officiels</h2>
        ${upcoming.length ? `<ul class="list-clean">${upcoming.map(div => `<li class="event-row"><div><div class="strong">${escapeHtml(div.issuer)}</div><div class="subtext">Ex-dividende ${fmtDate(div.ex_date)} · paiement ${fmtDate(div.payment_date)}</div></div><div style="text-align:right"><div class="strong">${fmtFCFA(div.net_amount_fcfa)}</div>${div.notice_url ? `<a href="${div.notice_url}" target="_blank" rel="noopener">Avis</a>` : ""}</div></li>`).join("")}</ul>` : '<div class="Empty-state">Aucun dividende futur dans les pages officielles collectées à la date de génération.</div>'}
        <p class="source-line">Montants nets et dates tels que publiés dans le tableau officiel des paiements de dividendes.</p>
      </article>
    </div>

    ${macroCalendarCard()}

    <div class="grid-2 section-space">
      <article class="card">
        <div class="event-row"><div><p class="eyebrow">Votre périmètre</p><h2>Mes valeurs suivies et détenues</h2></div><button type="button" class="button button-secondary button-small" data-view-link="entreprises">Gérer</button></div>
        ${relevantCompanies.length ? `<ul class="list-clean">${relevantCompanies.slice(0, 7).map(c => companyMiniRow(c)).join("")}</ul>` : `<div class="Empty-state"><span class="sigma-empty">Σ</span>Aucune valeur suivie pour le moment. Le Radar a déjà trié les ${COMPANIES.length} sociétés cotées par règles quantitatives.<br><button type="button" class="button button-small" data-analysis-link="radar" style="margin-top:12px">Voir la sélection automatique</button></div>`}
      </article>
      <article class="card">
        <p class="eyebrow">Lire le marché sans le surinterpréter</p><h2>Largeur et concentration</h2>
        <div class="key-facts">
          <div class="key-fact"><span class="metric-label">Hausses / baisses / inchangées</span><div class="metric-value">${structure.advancers} · ${structure.decliners} · ${structure.unchanged}</div><div class="subtext">Instantané officiel</div></div>
          <div class="key-fact"><span class="metric-label">Variation médiane</span><div class="metric-value">${fmtPct(structure.median_variation_pct)}</div><div class="subtext">La moitié des valeurs fait mieux, l’autre moins bien</div></div>
          <div class="key-fact"><span class="metric-label">Top 5 des échanges en valeur</span><div class="metric-value">${fmtPct(bocStructure.top5_traded_value_share_pct, 1)}</div><div class="subtext">BOC du ${fmtDate(bocStructure.date)} · valeur officielle par titre</div></div>
          <div class="key-fact"><span class="metric-label">Sans volume publié</span><div class="metric-value">${structure.without_volume}</div><div class="subtext">Dans l’instantané des cours</div></div>
        </div>
        <p class="source-line">Concentration des capitalisations : <strong>non calculée</strong> tant que le nombre d’actions vérifié n’est pas intégré pour toutes les sociétés.</p>
      </article>
    </div>

    <div class="grid-2-equal section-space">
      <article class="card"><p class="eyebrow">Instantané BRVM</p><h2>Plus fortes hausses</h2><ul class="list-clean">${top.map(c => companyMiniRow(c, `<div class="subtext">Volume : ${fmtNum(c.latest_quote.volume)} titres</div>`)).join("")}</ul></article>
      <article class="card"><p class="eyebrow">Instantané BRVM</p><h2>Plus fortes baisses</h2><ul class="list-clean">${flop.map(c => companyMiniRow(c, `<div class="subtext">Volume : ${fmtNum(c.latest_quote.volume)} titres</div>`)).join("")}</ul></article>
    </div>

    <div class="notice blue section-space"><p><strong>État réel de couverture.</strong> ${escapeHtml(DATA.coverage.note)} Les fiches affichent donc les faits de marché et les indicateurs publiés au BOC, sans maquiller l’absence de fondamentaux vérifiés en “score maison”.</p></div>`;
}

function renderMarket() {
  const host = $("#marketContent");
  if (!host) return;
  const sectors = sectorList();
  let rows = COMPANIES.filter(c => !ui.marketSector || c.sector === ui.marketSector);
  const sorters = {
    variation_desc: (a, b) => (b.latest_quote?.variation_pct ?? -Infinity) - (a.latest_quote?.variation_pct ?? -Infinity),
    variation_asc: (a, b) => (a.latest_quote?.variation_pct ?? Infinity) - (b.latest_quote?.variation_pct ?? Infinity),
    volume_desc: (a, b) => (b.latest_quote?.volume ?? -1) - (a.latest_quote?.volume ?? -1),
    alpha: (a, b) => a.name.localeCompare(b.name, "fr")
  };
  rows = [...rows].sort(sorters[ui.marketSort] || sorters.alpha);
  const st = DATA.market_structure;
  host.innerHTML = `
    <div class="grid-3">
      ${DATA.snapshot.indices.map(index => `<article class="card kpi-card"><span class="kpi-label">${escapeHtml(index.name)}</span><div><div class="kpi-value">${fmtNum(index.level, 2)}</div><div class="kpi-sub">${variationPill(index.variation_pct)}</div></div></article>`).join("")}
    </div>
    <article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Lecture de structure</p><h2>Un indice ne raconte pas tout le marché</h2></div><span class="pill">Calculs SIGMA depuis la cote officielle</span></div>
      <div class="grid-4" style="margin-top:14px">
        <div class="key-fact"><span class="metric-label">Largeur instantané</span><div class="metric-value">${st.snapshot.advancers} ↑ · ${st.snapshot.decliners} ↓ · ${st.snapshot.unchanged} =</div></div>
        <div class="key-fact"><span class="metric-label">Médiane instantané</span><div class="metric-value">${fmtPct(st.snapshot.median_variation_pct)}</div></div>
        <div class="key-fact"><span class="metric-label">Top 5 valeur échangée</span><div class="metric-value">${fmtPct(st.latest_boc.top5_traded_value_share_pct, 1)}</div><div class="subtext">BOC ${fmtDate(st.latest_boc.date)}</div></div>
        <div class="key-fact"><span class="metric-label">Valeur BOC actions</span><div class="metric-value">${fmtCompactFCFA(st.latest_boc.total_traded_value_fcfa)}</div><div class="subtext">Somme des valeurs par titre du BOC</div></div>
      </div>
    </article>
    ${macroCalendarCard({ compact: true })}
    <article class="card section-space">
      <div class="toolbar" style="padding:0;border:0;margin-bottom:14px">
        <label>Secteur<select id="marketSector"><option value="">Tous les secteurs</option>${sectors.map(s => `<option value="${escapeHtml(s)}" ${s === ui.marketSector ? "selected" : ""}>${escapeHtml(s)}</option>`).join("")}</select></label>
        <label>Tri<select id="marketSort">
          <option value="variation_desc" ${ui.marketSort === "variation_desc" ? "selected" : ""}>Variation décroissante</option>
          <option value="variation_asc" ${ui.marketSort === "variation_asc" ? "selected" : ""}>Variation croissante</option>
          <option value="volume_desc" ${ui.marketSort === "volume_desc" ? "selected" : ""}>Volume décroissant</option>
          <option value="alpha" ${ui.marketSort === "alpha" ? "selected" : ""}>Nom A → Z</option>
        </select></label>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>Valeur</th><th class="mobile-hide">Secteur</th><th class="num mobile-hide">Veille</th><th class="num mobile-hide">Ouverture</th><th class="num">Clôture</th><th class="num">Variation</th><th class="num">Volume</th><th class="num mobile-hide">20 séances BOC</th><th></th></tr></thead>
        <tbody>${rows.map(c => {
          const q = c.latest_quote || {};
          return `<tr class="clickable-row" data-open-company="${c.ticker}"><td><div class="ticker">${c.ticker}</div><div class="subtext">${escapeHtml(c.name)}</div></td><td class="mobile-hide">${escapeHtml(c.sector)}</td><td class="num mobile-hide">${fmtFCFA(q.previous_close)}</td><td class="num mobile-hide">${fmtFCFA(q.open)}</td><td class="num strong">${fmtFCFA(q.close)}</td><td class="num">${variationPill(q.variation_pct)}</td><td class="num">${fmtNum(q.volume)}</td><td class="num mobile-hide">${fmtPct(c.history_stats?.performance_20_sessions_pct)}</td><td><button type="button" class="icon-button ${isWatched(c.ticker) ? "is-on" : ""}" data-toggle-watch="${c.ticker}" aria-label="Suivre ${c.ticker}">${isWatched(c.ticker) ? "★" : "☆"}</button></td></tr>`;
        }).join("")}</tbody>
      </table></div>
      <p class="source-line">Cours : page officielle BRVM, ${escapeHtml(DATA.snapshot.source_updated_label || "date non précisée")} · Variations sur 20 séances : clôtures des BOC, prix seuls.</p>
    </article>`;
  $("#marketSector").addEventListener("change", event => { ui.marketSector = event.target.value; renderMarket(); });
  $("#marketSort").addEventListener("change", event => { ui.marketSort = event.target.value; renderMarket(); });
}

function sortedCompanies() {
  let rows = [...COMPANIES];
  const query = normalize(ui.companySearch);
  if (query) rows = rows.filter(c => normalize(`${c.ticker} ${c.name}`).includes(query));
  if (ui.companySector) rows = rows.filter(c => c.sector === ui.companySector);
  if (ui.watchOnly) rows = rows.filter(c => isWatched(c.ticker));
  const nullLast = (a, b, getter, direction = 1) => {
    const av = getter(a), bv = getter(b);
    if (!isNum(av) && !isNum(bv)) return a.name.localeCompare(b.name, "fr");
    if (!isNum(av)) return 1; if (!isNum(bv)) return -1;
    return (av - bv) * direction;
  };
  if (ui.companySort === "yield") rows.sort((a, b) => nullLast(a, b, c => yieldScreenInfo(c).usable ? c.latest_boc?.net_dividend_yield_pct : null, -1));
  else if (ui.companySort === "per") rows.sort((a, b) => nullLast(a, b, c => c.latest_boc?.per, 1));
  else if (ui.companySort === "liquidity") rows.sort((a, b) => nullLast(a, b, c => c.history_stats?.median_traded_value_last_20_fcfa, -1));
  else if (ui.companySort === "perf20") rows.sort((a, b) => nullLast(a, b, c => c.history_stats?.performance_20_sessions_pct, -1));
  else rows.sort((a, b) => a.name.localeCompare(b.name, "fr"));
  return rows;
}
function renderCompanies() {
  const host = $("#companiesGrid");
  if (!host) return;
  const sectorSelect = $("#companySector");
  if (sectorSelect && sectorSelect.options.length <= 1) {
    sectorList().forEach(sector => {
      const option = document.createElement("option"); option.value = sector; option.textContent = sector; sectorSelect.appendChild(option);
    });
  }
  const rows = sortedCompanies();
  if (!rows.length) {
    host.innerHTML = '<div class="Empty-state" style="grid-column:1/-1"><span class="sigma-empty">Σ</span>Aucune société ne correspond à ces filtres.</div>';
    return;
  }
  host.innerHTML = rows.map(company => {
    const quote = company.latest_quote || {}, boc = company.latest_boc || {}, stats = company.history_stats || {};
    return `<article class="card company-card">
      <div class="company-card-head"><div><div class="ticker">${company.ticker}</div><h3>${escapeHtml(company.name)}</h3><div class="subtext">${escapeHtml(company.sector)}</div></div>
      <button type="button" class="icon-button ${isWatched(company.ticker) ? "is-on" : ""}" data-toggle-watch="${company.ticker}" aria-label="Suivre ${company.ticker}">${isWatched(company.ticker) ? "★" : "☆"}</button></div>
      <div><div class="company-price">${fmtFCFA(quote.close)}</div><div style="margin-top:6px">${variationPill(quote.variation_pct)} <span class="subtext">Volume ${fmtNum(quote.volume)}</span></div></div>
      <div class="metric-row">
        <div><div class="metric-label">${termButton("PER")} BOC</div><div class="metric-value">${fmtRatio(boc.per)}</div></div>
        <div><div class="metric-label">Rdt net BOC</div><div class="metric-value">${fmtPct(boc.net_dividend_yield_pct, 2, false)}</div></div>
        <div><div class="metric-label">Liquidité méd.</div><div class="metric-value">${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)}</div></div>
      </div>
      <div class="card-actions"><button type="button" class="button button-small" data-open-company="${company.ticker}">Lire la fiche</button><span class="subtext">BOC ${fmtDate(company.latest_boc_date)}</span></div>
    </article>`;
  }).join("");
}

function orderPrepMath(company, qty) {
  const price = latestPrice(company).value;
  const quantity = Math.max(0, Math.floor(Number(qty) || 0));
  const gross = isNum(price) ? quantity * price : null;
  const feePct = personal.settings.feePct === "" ? null : Number(personal.settings.feePct);
  const fixedFee = personal.settings.fixedFee === "" ? null : Number(personal.settings.fixedFee);
  const feesKnown = feePct !== null && fixedFee !== null && !Number.isNaN(feePct) && !Number.isNaN(fixedFee) && gross !== null;
  const fees = feesKnown ? Math.round(fixedFee + gross * feePct / 100) : null;
  const total = gross === null ? null : gross + (fees || 0);
  const monthly = Number(personal.settings.monthlyBudget) || 0;
  const medianValue = company.history_stats?.median_traded_value_last_20_fcfa;
  return {
    price, quantity, gross, fees, feesKnown, total,
    pctOfMonthly: monthly && total !== null ? (total / monthly) * 100 : null,
    monthsOfBudget: monthly && total !== null ? total / monthly : null,
    pctOfMedianSession: isNum(medianValue) && medianValue > 0 && gross !== null ? (gross / medianValue) * 100 : null
  };
}

function updateOrderPrep() {
  const company = BY_TICKER.get(ui.selectedTicker);
  const input = $("#orderQty");
  if (!company || !input) return;
  const result = orderPrepMath(company, input.value);
  const set = (id, text) => { const node = $(id); if (node) node.textContent = text; };
  set("#opQtyEcho", fmtNum(result.quantity));
  set("#opGross", fmtFCFA(result.gross));
  set("#opFees", result.feesKnown ? fmtFCFA(result.fees) : "Non estimés");
  set("#opTotal", result.total === null ? "—" : fmtFCFA(result.total) + (result.feesKnown ? "" : " (hors frais)"));
  set("#opPctBudget", result.pctOfMonthly === null ? "—" : `${fmtNum(result.pctOfMonthly, 0)} % de votre versement mensuel`);
  set("#opMonths", result.monthsOfBudget === null ? "—" : `≈ ${fmtNum(result.monthsOfBudget, 1)} mois de versement`);
  set("#opLiquidity", result.pctOfMedianSession === null ? "—" : `${fmtNum(result.pctOfMedianSession, 2)} % de la valeur médiane échangée en une séance`);
}

/* ---------------------------------------------------------------------------
   Piliers fondamentaux SIGMA (Solidité, Croissance) — publiés uniquement si
   la série pluriannuelle extraite des états financiers officiels est
   suffisante. Méthode affichée dans les fiches ; aucun score global tant que
   le pilier Dividende durable (taux de distribution/couverture cash) n'est pas
   calculable sans bénéfice par action ou nombre d'actions vérifié.
---------------------------------------------------------------------------- */
function fundamentalSeries(company) {
  return (company.fundamentals?.series || []).filter(entry => entry && entry.figures);
}
function seriesValue(entry, key) {
  const value = entry?.figures?.[key]?.value_fcfa;
  return isNum(value) ? value : null;
}
function resultValue(entry) {
  return seriesValue(entry, "resultat_net") ?? seriesValue(entry, "resultat_net_part_groupe");
}
function activityValue(entry) {
  return seriesValue(entry, "chiffre_affaires") ?? seriesValue(entry, "produit_net_bancaire");
}
function cagr(points) {
  // points : [{exercice, value}] triés croissant, valeurs > 0, amplitude >= 2 ans
  if (points.length < 3) return null;
  const first = points[0], last = points[points.length - 1];
  const span = last.exercice - first.exercice;
  if (span < 2 || first.value <= 0 || last.value <= 0) return null;
  return (Math.pow(last.value / first.value, 1 / span) - 1) * 100;
}

function computeFundamentalPillars() {
  const raw = new Map();
  for (const company of COMPANIES) {
    const series = fundamentalSeries(company);
    const byYearAsc = [...series].sort((a, b) => a.exercice - b.exercice);
    const latestBilan = [...series].sort((a, b) => b.exercice - a.exercice)
      .find(entry => seriesValue(entry, "capitaux_propres") && seriesValue(entry, "total_bilan"));
    const cpRatio = latestBilan ? (seriesValue(latestBilan, "capitaux_propres") / seriesValue(latestBilan, "total_bilan")) * 100 : null;
    const rnPoints = byYearAsc.map(entry => ({ exercice: entry.exercice, value: resultValue(entry) })).filter(p => p.value !== null);
    const positiveShare = rnPoints.length ? rnPoints.filter(p => p.value > 0).length / rnPoints.length : null;
    const latestRoeEntry = [...series].sort((a, b) => b.exercice - a.exercice)
      .find(entry => resultValue(entry) !== null && seriesValue(entry, "capitaux_propres"));
    const roe = latestRoeEntry ? (resultValue(latestRoeEntry) / seriesValue(latestRoeEntry, "capitaux_propres")) * 100 : null;
    const activityPoints = byYearAsc.map(entry => ({ exercice: entry.exercice, value: activityValue(entry) })).filter(p => p.value !== null && p.value > 0);
    const rnPositivePoints = rnPoints.filter(p => p.value > 0);
    raw.set(company.ticker, {
      company, cpRatio, positiveShare, roe,
      rnYears: rnPoints.length,
      cpYears: byYearAsc.filter(entry => seriesValue(entry, "capitaux_propres")).length,
      activityCagr: cagr(activityPoints),
      rnCagr: rnPositivePoints.length === rnPoints.length ? cagr(rnPositivePoints) : null,
      activityYears: activityPoints.length,
      isFinancial: company.sector === "Services financiers"
    });
  }
  const groupValues = (predicate, field) => [...raw.values()].filter(predicate).map(item => item[field]);
  const pillars = new Map();
  for (const item of raw.values()) {
    let solidite = null;
    if (item.cpRatio !== null && item.rnYears >= 3 && item.cpYears >= 2) {
      const peers = entry => entry.isFinancial === item.isFinancial && entry.cpRatio !== null && entry.rnYears >= 3;
      const ratioScore = percentileRank(groupValues(peers, "cpRatio"), item.cpRatio) * 100;
      const stabilityScore = (item.positiveShare ?? 0) * 100;
      let score, parts;
      if (item.roe !== null) {
        const roeScore = percentileRank(groupValues(entry => entry.isFinancial === item.isFinancial && entry.roe !== null, "roe"), item.roe) * 100;
        score = Math.round(0.5 * ratioScore + 0.3 * stabilityScore + 0.2 * roeScore);
        parts = { ratioScore: Math.round(ratioScore), stabilityScore: Math.round(stabilityScore), roeScore: Math.round(roeScore) };
      } else {
        score = Math.round(0.625 * ratioScore + 0.375 * stabilityScore);
        parts = { ratioScore: Math.round(ratioScore), stabilityScore: Math.round(stabilityScore), roeScore: null };
      }
      solidite = { score, parts, cpRatio: item.cpRatio, positiveShare: item.positiveShare, roe: item.roe, rnYears: item.rnYears };
    }
    let croissance = null;
    if (item.activityCagr !== null) {
      const activityScore = percentileRank(groupValues(entry => entry.activityCagr !== null, "activityCagr"), item.activityCagr) * 100;
      let score = activityScore, rnScore = null;
      if (item.rnCagr !== null) {
        rnScore = percentileRank(groupValues(entry => entry.rnCagr !== null, "rnCagr"), item.rnCagr) * 100;
        score = 0.7 * activityScore + 0.3 * rnScore;
      }
      croissance = {
        score: Math.round(score),
        parts: { activityScore: Math.round(activityScore), rnScore: rnScore === null ? null : Math.round(rnScore) },
        activityCagr: item.activityCagr, rnCagr: item.rnCagr, activityYears: item.activityYears
      };
    }
    pillars.set(item.company.ticker, { solidite, croissance });
  }
  return pillars;
}

function confidencePill(confidence) {
  if (confidence === "confirme_deux_documents") return '<span class="pill green" title="Même valeur publiée par deux documents officiels distincts">Confirmé · 2 documents</span>';
  if (confidence === "recoupe_dans_le_document") return '<span class="pill" title="Valeur retrouvée au moins deux fois dans le document source">Recoupé</span>';
  return '<span class="pill amber" title="Une seule occurrence lue automatiquement">À confirmer</span>';
}

function renderCompanyDetail() {
  const host = $("#companyDetail");
  const company = BY_TICKER.get(ui.selectedTicker);
  if (!host || !company) return;
  const quote = company.latest_quote || {}, boc = company.latest_boc || {}, stats = company.history_stats || {};
  const points = (company.series || []).map(p => ({ date: p.date, value: p.close }));
  const matchedDividends = dividendsForTicker(company.ticker)
    .sort((a, b) => String(b.payment_date || "").localeCompare(String(a.payment_date || "")));
  const journal = personal.journal.filter(item => item.ticker === company.ticker);
  const peerPer = sectorMedian("per", company.sector);
  const peerYield = median(COMPANIES.filter(c => c.sector === company.sector && yieldScreenInfo(c).usable).map(c => c.latest_boc?.net_dividend_yield_pct));
  const yieldInfo = yieldScreenInfo(company);
  const orderMonthly = Number(personal.settings.monthlyBudget) || 0;
  const orderPocketPct = personal.profile?.pocketEnabled ? Math.min(50, Math.max(0, Number(personal.profile.pocketPct) || 0)) : 0;
  const orderWorkingBudget = Math.max(0, orderMonthly - Math.round(orderMonthly * orderPocketPct / 100));
  const orderRefPrice = latestPrice(company).value;
  const orderDefaultQty = Math.max(1, calculateAffordable(orderWorkingBudget, orderRefPrice)?.shares || 1);
  const orderInitial = orderPrepMath(company, orderDefaultQty);
  const facts = [];
  if (isNum(stats.traded_sessions_last_20)) facts.push(`Échangée sur ${stats.traded_sessions_last_20} des 20 dernières séances BOC lues ; valeur médiane négociée ${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)} par séance.`);
  if (isNum(stats.performance_20_sessions_pct)) facts.push(`Le cours de clôture BOC a varié de ${fmtPct(stats.performance_20_sessions_pct)} sur 20 séances (prix seuls, hors dividendes réinvestis).`);
  if (isNum(boc.per)) facts.push(`Le BOC du ${fmtDate(company.latest_boc_date)} publie un PER de ${fmtRatio(boc.per)} ; médiane du secteur dans SIGMA : ${fmtRatio(peerPer)}.`);
  if (isNum(boc.net_dividend_yield_pct)) facts.push(yieldInfo.usable
    ? `Le même BOC publie un rendement net de ${fmtPct(boc.net_dividend_yield_pct, 2, false)} ; médiane sectorielle des rendements récents et non extrêmes : ${fmtPct(peerYield, 2, false)}.`
    : `Le même BOC publie un rendement net de ${fmtPct(boc.net_dividend_yield_pct, 2, false)}, mais SIGMA le classe « à vérifier » (${yieldInfo.reason}) : ne pas l’assimiler à un rendement récurrent.`);
  if (!facts.length) facts.push("Les données de marché disponibles sont insuffisantes pour formuler une synthèse sans spéculer.");

  host.innerHTML = `
    <div class="view-heading" style="margin-top:8px">
      <div><p class="eyebrow">${escapeHtml(company.sector)} · ${company.ticker}</p><h1 id="title-fiche">${escapeHtml(company.name)}</h1>
      <p class="lead">Fiche de marché sourcée. Lorsqu’ils sont affichés, les fondamentaux proviennent d’une extraction automatique des états financiers officiels, avec niveaux de confiance et preuves page/ligne.</p></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="button button-secondary" data-toggle-watch="${company.ticker}">${isWatched(company.ticker) ? "★ Suivie" : "☆ Suivre"}</button>
      <button type="button" class="button" data-journal-for="${company.ticker}">Écrire une thèse</button></div>
    </div>

    <div class="detail-hero">
      <article class="card">
        <div class="event-row"><div><span class="kpi-label">Dernier cours publié</span><div class="detail-price">${fmtFCFA(quote.close)}</div>
        <div style="margin-top:9px">${variationPill(quote.variation_pct)} <span class="muted">Volume ${fmtNum(quote.volume)} titres</span></div></div>
        <span class="pill dark">${escapeHtml(DATA.snapshot.session_status)}</span></div>
        <p class="source-line">Source : page officielle des cours BRVM · ${escapeHtml(DATA.snapshot.source_updated_label || "date source non précisée")}. Veille ${fmtFCFA(quote.previous_close)} · Ouverture ${fmtFCFA(quote.open)}.</p>
        <hr style="border:0;border-top:1px solid var(--border);margin:18px 0">
        <p class="eyebrow">Synthèse de marché — faits calculés</p>
        <ul>${facts.map(fact => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>
      </article>
      <article class="card">
        <p class="eyebrow">Indicateurs publiés au BOC</p><h2>${fmtDate(company.latest_boc_date)}</h2>
        <div class="key-facts">
          <div class="key-fact"><span class="metric-label">${termButton("PER")}</span><div class="metric-value">${fmtRatio(boc.per)}</div><div class="subtext">Médiane secteur ${fmtRatio(peerPer)}</div></div>
          <div class="key-fact"><span class="metric-label">${termButton("Rendement net", "Rendement net")}</span><div class="metric-value">${fmtPct(boc.net_dividend_yield_pct, 2, false)}</div><div class="subtext">${yieldInfo.usable ? `Médiane secteur ${fmtPct(peerYield, 2, false)}` : `À vérifier : ${escapeHtml(yieldInfo.reason)}`}</div></div>
          <div class="key-fact"><span class="metric-label">Dernier dividende BOC</span><div class="metric-value">${fmtFCFA(boc.last_net_dividend_fcfa)}</div><div class="subtext">Date imprimée : ${escapeHtml(boc.last_dividend_date_label || "—")}</div></div>
          <div class="key-fact"><span class="metric-label">Variation année précédente</span><div class="metric-value">${fmtPct(boc.variation_previous_year_pct)}</div><div class="subtext">Colonne publiée dans le BOC</div></div>
        </div>
        <p class="source-line">Ces ratios sont repris tels que publiés par la BRVM ; SIGMA ne les recalcule pas à partir d’un BNPA non vérifié.</p>
      </article>
    </div>

    <article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Préparation d'ordre</p><h2>Si vous vouliez acheter des actions ${company.ticker}</h2></div><span class="pill amber">SIGMA ne passe aucun ordre</span></div>
      <p class="muted">SIGMA prépare les chiffres ; l'ordre réel se passe chez votre SGI, pendant la séance (négociation en continu de 9h45 à 14h00, fixing de clôture à 14h30 — horaires officiels BRVM). Le cours de référence ci-dessous est le dernier cours <strong>publié</strong> : ce n'est pas un prix en temps réel et l'exécution pourra différer. Sur ce marché, un ordre à cours limité protège contre les écarts.</p>
      <div class="form-grid" style="margin-top:12px">
        <label>Quantité envisagée (actions)<input id="orderQty" type="number" min="0" step="1" value="${orderDefaultQty}"><span class="field-hint">Pré-rempli avec ce que permet un versement mensuel${orderPocketPct ? ` hors poche d'apprentissage (${fmtNum(orderPocketPct)} %)` : ""} : ${fmtFCFA(orderWorkingBudget)}. Changez librement la quantité.</span></label>
        <label>Cours de référence publié<input value="${isNum(orderRefPrice) ? fmtNum(orderRefPrice) : "—"} FCFA" readonly><span class="field-hint">${escapeHtml(DATA.snapshot.source_updated_label || "")} · ${escapeHtml(DATA.snapshot.session_status)} · collecte SIGMA du ${fmtDateTime(DATA.generated_at)}</span></label>
      </div>
      <div class="grid-3" style="margin-top:14px">
        <div class="key-fact"><span class="metric-label">Montant brut · <span id="opQtyEcho">${fmtNum(orderInitial.quantity)}</span> actions</span><div class="metric-value" id="opGross">${fmtFCFA(orderInitial.gross)}</div></div>
        <div class="key-fact"><span class="metric-label">Frais SGI estimés</span><div class="metric-value" id="opFees">${orderInitial.feesKnown ? fmtFCFA(orderInitial.fees) : "Non estimés"}</div><div class="subtext">${orderInitial.feesKnown ? `${escapeHtml(personal.settings.sgiName || "Votre SGI")} · ${fmtNum(Number(personal.settings.feePct), 3)} % + ${fmtFCFA(Number(personal.settings.fixedFee))}` : "Saisissez la grille de votre SGI dans Paramètres"}</div></div>
        <div class="key-fact"><span class="metric-label">Total à prévoir</span><div class="metric-value" id="opTotal">${orderInitial.total === null ? "—" : fmtFCFA(orderInitial.total) + (orderInitial.feesKnown ? "" : " (hors frais)")}</div></div>
        <div class="key-fact"><span class="metric-label">Poids dans votre rythme</span><div class="metric-value" style="font-size:16px" id="opPctBudget">${orderInitial.pctOfMonthly === null ? "—" : `${fmtNum(orderInitial.pctOfMonthly, 0)} % de votre versement mensuel`}</div><div class="subtext" id="opMonths">${orderInitial.monthsOfBudget === null ? "—" : `≈ ${fmtNum(orderInitial.monthsOfBudget, 1)} mois de versement`}</div></div>
        <div class="key-fact"><span class="metric-label">Taille face aux échanges du titre</span><div class="metric-value" style="font-size:16px" id="opLiquidity">${orderInitial.pctOfMedianSession === null ? "—" : `${fmtNum(orderInitial.pctOfMedianSession, 2)} % de la valeur médiane échangée en une séance`}</div><div class="subtext">Sous quelques %, votre ordre reste marginal face au flux habituel ; cela ne garantit ni le prix ni l'exécution du jour.</div></div>
      </div>
      <div class="form-actions" style="margin-top:14px">
        <button type="button" class="button" data-simulate-order="${company.ticker}">Simuler cet achat (portefeuille virtuel)</button>
        <button type="button" class="button button-secondary" data-journal-for="${company.ticker}">Écrire la thèse avant tout ordre réel</button>
      </div>
      <p class="source-line">Le « budget mensuel » n'est ni une limite du marché ni un plafond imposé par SIGMA : c'est votre rythme d'accumulation. Rien n'interdit un achat plus gros un mois donné — l'application montre alors combien de mois de versement il représente, pour que la décision reste délibérée.</p>
    </article>

    <article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Historique BOC</p><h2>Clôtures sur ${points.length} séances lues</h2></div><span class="pill">Prix seuls</span></div>
      ${lineChart(points, { money: true })}
      <div class="grid-4" style="margin-top:12px">
        <div class="key-fact"><span class="metric-label">5 séances</span><div class="metric-value">${fmtPct(stats.performance_5_sessions_pct)}</div></div>
        <div class="key-fact"><span class="metric-label">20 séances</span><div class="metric-value">${fmtPct(stats.performance_20_sessions_pct)}</div></div>
        <div class="key-fact"><span class="metric-label">Séances échangées / 20</span><div class="metric-value">${fmtNum(stats.traded_sessions_last_20)}</div></div>
        <div class="key-fact"><span class="metric-label">Valeur médiane / séance</span><div class="metric-value">${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)}</div></div>
      </div>
      ${(() => {
        const long = stats.long_history || {};
        if (!long.sessions_available) return "";
        const horizon = (label, value) => `<div class="key-fact"><span class="metric-label">${label}</span><div class="metric-value">${fmtPct(value)}</div></div>`;
        return `<h3 style="margin-top:16px">Archive BOC longue — ${fmtNum(long.sessions_available)} séances</h3>
        <p class="source-line">${fmtDate(long.first_date)} → ${fmtDate(long.last_date)} · prix publiés non ajustés, hors dividendes réinvestis. Ces horizons situent le parcours, la liquidité et les replis déjà observés ; ils ne prédisent pas le prochain mouvement.</p>
        <div class="grid-4" style="margin-top:10px">
          ${horizon("60 séances", long.performance_60_sessions_pct)}
          ${horizon("120 séances", long.performance_120_sessions_pct)}
          ${horizon("250 séances", long.performance_250_sessions_pct)}
          <div class="key-fact"><span class="metric-label">Repli maximal observé</span><div class="metric-value">${fmtPct(long.max_drawdown_pct)}</div></div>
          <div class="key-fact"><span class="metric-label">Séances échangées (archive)</span><div class="metric-value">${fmtNum(long.traded_sessions)} / ${fmtNum(long.sessions_available)}</div><div class="subtext">${isNum(long.traded_share_pct) ? `${fmtNum(long.traded_share_pct, 1)} % des séances archivées` : ""}</div></div>
          <div class="key-fact"><span class="metric-label">Valeur médiane (archive)</span><div class="metric-value">${fmtCompactFCFA(long.median_traded_value_fcfa)}</div><div class="subtext">60 dernières séances : ${fmtCompactFCFA(long.median_traded_value_60_fcfa)}</div></div>
          <div class="key-fact"><span class="metric-label">Volatilité annualisée (prix)</span><div class="metric-value">${isNum(long.volatility_annualized_pct) ? `${fmtNum(long.volatility_annualized_pct, 1)} %` : "—"}</div></div>
          <div class="key-fact"><span class="metric-label">Pire séance BOC archivée</span><div class="metric-value">${fmtPct(long.worst_session_variation_pct)}</div><div class="subtext">${fmtDate(long.worst_session_date)}</div></div>
        </div>`;
      })()}
    </article>

    <div class="section-space">
      <article class="card"><p class="eyebrow">Dividendes officiels BRVM</p><h2>Historique des distributions par exercice</h2>
        ${(() => {
          const hist = company.dividend_history || {};
          const annual = [...(hist.annual || [])].sort((a, b) => b.fiscal_year - a.fiscal_year);
          if (!annual.length) {
            return `<div class="Empty-state">Aucune distribution n’a été rattachée sans ambiguïté à ce ticker dans le tableau BRVM collecté. Cela ne prouve pas à lui seul un dividende nul sur tous les exercices : nouvelle cotation, changement de nom ou ligne non rattachée restent possibles. Le dernier dividende imprimé au BOC est affiché ci-dessus.</div>`;
          }
          return `<div class="grid-4" style="margin-top:10px">
            <div class="key-fact"><span class="metric-label">5 derniers exercices du tableau</span><div class="metric-value">${hist.paid_last_5_fiscal_years ?? 0}/5</div><div class="subtext">Exercices avec distribution nette documentée</div></div>
            <div class="key-fact"><span class="metric-label">Profondeur documentée</span><div class="metric-value" style="font-size:16px">${hist.first_paid_fiscal_year ?? "—"} → ${hist.latest_paid_fiscal_year ?? "—"}</div><div class="subtext">${hist.paid_fiscal_years_count ?? 0} exercice(s) versé(s) rattaché(s)</div></div>
            <div class="key-fact"><span class="metric-label">Suite courante</span><div class="metric-value">${hist.current_consecutive_paid_years ?? 0}</div><div class="subtext">Exercice(s) consécutif(s) jusqu’au dernier exercice du tableau</div></div>
            <div class="key-fact"><span class="metric-label">Évolution annuelle moyenne</span><div class="metric-value">${fmtPct(hist.dividend_cagr_pct, 1)}</div><div class="subtext">Dividende net/action · ${hist.increases_count ?? 0} hausse(s), ${hist.cuts_count ?? 0} baisse(s) entre exercices consécutifs documentés</div></div>
          </div>
          <div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>Exercice</th><th class="num">Net/action</th><th class="num">Paiement(s)</th><th>Dernière date ex-dividende</th><th></th></tr></thead>
          <tbody>${annual.slice(0, 10).map(entry => `<tr><td class="strong">${entry.fiscal_year}</td><td class="num">${fmtFCFA(entry.net_amount_fcfa)}</td><td class="num">${entry.payments_count}</td><td>${fmtDate((entry.ex_dates || []).at(-1))}</td><td>${entry.notice_urls?.length ? `<a class="button button-secondary button-small" href="${entry.notice_urls[0]}" target="_blank" rel="noopener">Avis</a>` : ""}</td></tr>`).join("")}</tbody></table></div>
          <p class="source-line">Historique constitué depuis le tableau officiel BRVM paginé. Plusieurs paiements d’un même exercice sont additionnés et comptés. Une ligne absente signifie « non documentée dans le tableau collecté », pas automatiquement zéro. Le taux de distribution et la couverture par les flux restent non calculables sans bénéfice par action/nombre d’actions et flux vérifiés : le pilier Dividende durable n’est donc pas encore publié.</p>`;
        })()}
        <h3 style="margin-top:16px">Avis récents rattachés</h3>
        ${matchedDividends.length ? `<ul class="list-clean">${matchedDividends.slice(0, 6).map(div => `<li class="event-row"><div><div class="strong">${fmtFCFA(div.net_amount_fcfa)} net</div><div class="subtext">Exercice ${escapeHtml(div.fiscal_year)} · ex-dividende ${fmtDate(div.ex_date)} · paiement ${fmtDate(div.payment_date)}</div></div>${div.notice_url ? `<a class="button button-secondary button-small" href="${div.notice_url}" target="_blank" rel="noopener">Avis</a>` : ""}</li>`).join("")}</ul>` : '<div class="Empty-state">Aucun avis du tableau collecté n’a pu être rattaché sans ambiguïté à ce ticker.</div>'}
      </article>
      <article class="card section-space"><p class="eyebrow">Fondamentaux · états financiers officiels</p><h2>Série annuelle et piliers SIGMA</h2>
        ${(() => {
          const fund = company.fundamentals || {};
          const series = fundamentalSeries(company);
          if (!series.length) {
            return `<div class="notice"><p><strong>Aucun agrégat annuel n'a passé les contrôles d'extraction pour ${company.ticker}.</strong></p><p>${(fund.notes || []).map(escapeHtml).join(" ") || "Les documents officiels indexés ci-dessous restent la source à lire."}</p></div>
            <p class="source-line">Piliers Solidité et Croissance : <strong>non calculables</strong> faute de série suffisante.</p>`;
          }
          const pillars = computeFundamentalPillars().get(company.ticker) || {};
          const activityLabel = series.some(entry => seriesValue(entry, "produit_net_bancaire")) ? "Produit net bancaire" : "Chiffre d'affaires";
          const cell = (entry, key) => {
            const fig = entry.figures?.[key];
            if (!fig) return '<td class="num">—</td>';
            const ev = (fig.evidence || [])[0] || {};
            return `<td class="num"><span title="${escapeHtml(ev.line || "")}${ev.page ? ` (page ${ev.page})` : ""}">${fmtCompactFCFA(fig.value_fcfa)}</span><div>${confidencePill(fig.confidence)}</div></td>`;
          };
          const solidite = pillars.solidite, croissance = pillars.croissance;
          const pillarBar = (label, value, max = 100) => `<div class="score-part"><span>${label}</span><div class="bar-track"><div class="bar-fill" style="width:${value}%"></div></div><span class="strong">${value}/${max}</span></div>`;
          return `<div class="news-meta">
            <span class="pill ${fund.data_confidence === "A" ? "green" : fund.data_confidence === "B" ? "" : "amber"}">Confiance données ${escapeHtml(fund.data_confidence || "—")}</span>
            <span class="tag-chip">${series.length} exercice(s) : ${Math.min(...series.map(e => e.exercice))} – ${Math.max(...series.map(e => e.exercice))}</span>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Exercice</th><th class="num">${activityLabel}</th><th class="num">Résultat net</th><th class="num">${termButton("Capitaux propres", "Capitaux propres")}</th><th class="num">Total du bilan</th></tr></thead>
          <tbody>${series.map(entry => `<tr><td class="strong">${entry.exercice}</td>${cell(entry, seriesValue(entry, "produit_net_bancaire") ? "produit_net_bancaire" : "chiffre_affaires")}${cell(entry, entry.figures?.resultat_net ? "resultat_net" : "resultat_net_part_groupe")}${cell(entry, "capitaux_propres")}${cell(entry, "total_bilan")}</tr>`).join("")}</tbody></table></div>
          <p class="source-line">Lecture automatique des états financiers officiels (unité explicite exigée, ou états de synthèse SYSCOHADA codés en FCFA ; colonnes N et N-1 distinguées, contrôles de cohérence du bilan et de continuité de la série). « Confirmé · 2 documents » = même valeur publiée par deux documents distincts pour le même exercice. Survolez une valeur pour sa ligne source ; documents complets ci-dessous.</p>

          <h3 style="margin-top:16px">Piliers SIGMA calculables</h3>
          ${solidite ? `<div class="key-fact" style="margin-top:8px"><div class="event-row"><span class="metric-label">Solidité (pilier)</span><span class="score-total" style="font-size:19px">${solidite.score}<span style="font-size:11px">/100</span></span></div>
            ${pillarBar("Capitaux propres / bilan (rang)", solidite.parts.ratioScore)}
            ${pillarBar("Exercices bénéficiaires", solidite.parts.stabilityScore)}
            ${solidite.parts.roeScore !== null ? pillarBar("Rentabilité des capitaux propres (rang)", solidite.parts.roeScore) : ""}
            <div class="subtext">Capitaux propres = ${fmtNum(solidite.cpRatio, 1)} % du bilan (dernier exercice complet) · résultat positif sur ${fmtNum((solidite.positiveShare || 0) * 100, 0)} % des ${solidite.rnYears} exercices lus${solidite.roe !== null ? ` · ROE ${fmtNum(solidite.roe, 1)} %` : ""}. Rangs calculés parmi les sociétés de même nature (financières / non financières) disposant d'une série suffisante.</div></div>`
          : `<p class="small muted"><strong>Solidité : non calculable.</strong> Il faut au minimum 3 exercices de résultat net et 2 de capitaux propres, avec un bilan complet récent.</p>`}
          ${croissance ? `<div class="key-fact" style="margin-top:10px"><div class="event-row"><span class="metric-label">Croissance (pilier)</span><span class="score-total" style="font-size:19px">${croissance.score}<span style="font-size:11px">/100</span></span></div>
            ${pillarBar("Croissance de l'activité (rang)", croissance.parts.activityScore)}
            ${croissance.parts.rnScore !== null ? pillarBar("Croissance du résultat net (rang)", croissance.parts.rnScore) : ""}
            <div class="subtext">Croissance annuelle moyenne de l'activité : ${fmtPct(croissance.activityCagr, 1)} sur ${croissance.activityYears} exercices${croissance.rnCagr !== null ? ` · résultat net : ${fmtPct(croissance.rnCagr, 1)}` : " · résultat net non retenu (perte sur la période ou série incomplète)"}.</div></div>`
          : `<p class="small muted"><strong>Croissance : non calculable.</strong> Il faut au moins 3 exercices d'activité (chiffre d'affaires ou produit net bancaire) sur 2 ans ou plus.</p>`}
          <div class="notice" style="margin-top:12px"><p><strong>Pilier Dividende durable et score global : toujours suspendus.</strong> L’historique des distributions est désormais affiché ci-dessus, mais le taux de distribution (dividende / bénéfice) et la couverture par les flux ne sont pas calculables sans bénéfice par action/nombre d’actions et flux de trésorerie vérifiés. SIGMA publie donc les piliers calculables séparément, sans les fusionner en une note unique qui prétendrait tout résumer.</p></div>
          ${(fund.notes || []).length ? `<details style="margin-top:10px"><summary class="strong" style="cursor:pointer">Contrôles et écarts signalés (${fund.notes.length})</summary><ul>${fund.notes.map(note => `<li class="small">${escapeHtml(note)}</li>`).join("")}</ul></details>` : ""}`;
        })()}
      </article>
    </div>

    <article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Bibliothèque officielle de l'émetteur</p><h2>Documents financiers indexés sur brvm.org (${(company.documents || []).length})</h2></div><span class="pill">Collecte automatique</span></div>
      ${(company.documents || []).length ? `<div class="table-wrap"><table><thead><tr><th>Document</th><th>Type</th><th>Exercice</th><th>Publié le</th><th></th></tr></thead>
      <tbody>${(company.documents || []).slice(0, 12).map(doc => `<tr><td class="strong">${escapeHtml(doc.label)}</td><td>${escapeHtml(DOC_TYPE_LABELS[doc.doc_type] || "Document officiel")}</td><td>${doc.exercice ?? "—"}</td><td>${fmtDate(doc.published_date)}</td><td><a class="button button-secondary button-small" href="${escapeHtml(doc.url)}" target="_blank" rel="noopener">PDF officiel</a></td></tr>`).join("")}</tbody></table></div>
      <p class="source-line">Index constitué automatiquement depuis la page officielle de l'émetteur. Les rapports d'activité trimestriels et semestriels complètent les états financiers annuels audités.</p>` : '<div class="Empty-state">Aucun document n\'a pu être rattaché à cette société dans la dernière collecte.</div>'}
    </article>

    <article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Collecte automatique</p><h2>Publications rattachées à ${company.ticker}</h2></div><button type="button" class="button button-secondary button-small" data-view-link="actualites">Ouvrir le fil complet</button></div>
      ${newsForTicker(company.ticker, 5).length ? newsForTicker(company.ticker, 5).map(newsItemHtml).join("") : '<div class="Empty-state">Aucune annonce ni dépêche n\'a été rattachée à cette société dans la dernière collecte. Cela ne signifie pas qu\'aucune information n\'existe : vérifier les rapports officiels de l\'émetteur.</div>'}
    </article>

    <article class="card section-space"><p class="eyebrow">Preuves récentes</p><h2>10 dernières séances BOC</h2>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th class="num">Clôture</th><th class="num">Variation BOC</th><th class="num">Volume</th><th class="num">Valeur échangée</th></tr></thead>
      <tbody>${[...(company.series || [])].slice(-10).reverse().map(p => `<tr><td>${fmtDate(p.date)}</td><td class="num strong">${fmtFCFA(p.close)}</td><td class="num">${variationPill(p.variation_pct)}</td><td class="num">${fmtNum(p.volume)}</td><td class="num">${fmtFCFA(p.traded_value_fcfa)}</td></tr>`).join("")}</tbody></table></div>
    </article>

    <article class="card section-space"><p class="eyebrow">Mémoire personnelle</p><h2>Journal lié à ${company.ticker}</h2>
      ${journal.length ? `<ul class="list-clean">${journal.map(item => `<li><div class="strong">${escapeHtml(item.title)}</div><div class="subtext">${fmtDate(item.date)} · ${escapeHtml(item.type)}</div><p>${escapeHtml(item.text)}</p>${item.invalidation ? `<p class="small"><strong>Invalidation :</strong> ${escapeHtml(item.invalidation)}</p>` : ""}</li>`).join("")}</ul>` : '<div class="Empty-state">Aucune thèse écrite pour cette société. C’est précisément avant un premier achat qu’elle a le plus de valeur.</div>'}
    </article>`;
}

function radarEntryCard(entry, rank) {
  const company = entry.company;
  const boc = company.latest_boc || {};
  const stats = company.history_stats || {};
  const partBar = (label, value, max, detail) => `<div class="score-part"><span>${label}</span><div class="bar-track"><div class="bar-fill" style="width:${max ? Math.round((value / max) * 100) : 0}%"></div></div><span class="strong">${value}/${max}</span></div><div class="subtext" style="margin:-1px 0 4px 100px">${detail}</div>`;
  return `<article class="card">
    <div class="event-row"><div style="display:flex;gap:10px;align-items:center"><span class="radar-rank">${rank}</span>
      <div><button type="button" class="text-button ticker" data-open-company="${company.ticker}">${company.ticker}</button>
      <div class="subtext">${escapeHtml(company.name)} · ${escapeHtml(company.sector)}</div></div></div>
      <div style="text-align:right"><div class="score-total">${entry.score}<span style="font-size:12px">/100</span></div><div class="subtext">${termButton("Score d'étude", "score d'étude")}</div></div></div>
    <div style="margin-top:12px">
      ${partBar("Liquidité", entry.parts.liquidity, RADAR_RULES.weights.liquidity, `${fmtNum(stats.traded_sessions_last_20)}/20 séances · valeur médiane ${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)}`)}
      ${partBar("Valorisation", entry.parts.valuation, RADAR_RULES.weights.valuation, `PER BOC ${fmtRatio(boc.per)} · médiane du secteur ${fmtRatio(entry.sectorPer)}`)}
      ${partBar("Rendement", entry.parts.yield, RADAR_RULES.weights.yield, `Rendement net BOC ${fmtPct(boc.net_dividend_yield_pct, 2, false)} · dernier dividende ${escapeHtml(boc.last_dividend_date_label || "—")} · historique BRVM : ${dividendHistoryLabel(company)}`)}
    </div>
    <div class="subtext" style="margin-top:8px">Cours ${fmtFCFA(latestPrice(company).value)} · ${fmtPct(stats.performance_20_sessions_pct)} sur 20 séances (prix seuls)</div>
    ${(() => {
      const fund = company.fundamentals || {};
      const pillars = computeFundamentalPillars().get(company.ticker) || {};
      if (pillars.solidite || pillars.croissance) {
        return `<div class="subtext" style="margin-top:4px">Fondamentaux (${fund.exercices_couverts ?? 0} exercices, confiance ${escapeHtml(fund.data_confidence || "—")}) : ${pillars.solidite ? `Solidité <strong>${pillars.solidite.score}/100</strong>` : "Solidité n/c"} · ${pillars.croissance ? `Croissance <strong>${pillars.croissance.score}/100</strong>` : "Croissance n/c"}</div>`;
      }
      if ((fund.series || []).length) {
        return `<div class="subtext" style="margin-top:4px">Fondamentaux : série de ${fund.series.length} exercice(s) extraite, piliers <strong>non calculables</strong> (seuils non atteints)</div>`;
      }
      return `<div class="subtext" style="margin-top:4px">Fondamentaux annuels : <strong>non extraits</strong> à ce stade</div>`;
    })()}
    ${entry.flags.map(flag => `<p class="radar-flag"><span class="pill ${flag.tone}">${flag.tone === "red" ? "À examiner" : flag.tone === "amber" ? "Vigilance prix" : "À lire"}</span> ${escapeHtml(flag.text)}</p>`).join("")}
    <div class="form-actions" style="margin-top:10px">
      <button type="button" class="button button-secondary button-small" data-open-company="${company.ticker}">Fiche</button>
      <button type="button" class="button button-secondary button-small" data-toggle-watch="${company.ticker}">${isWatched(company.ticker) ? "★ Suivie" : "☆ Suivre"}</button>
      <button type="button" class="button button-small" data-journal-for="${company.ticker}">Écrire la thèse</button>
    </div>
  </article>`;
}

function renderAnalysisRadar() {
  const { selection, overflow, rejected, scored } = computeRadar();
  const rules = RADAR_RULES;
  const reasonCounts = new Map();
  for (const item of rejected) {
    for (const reason of item.reasons) {
      const key = reason.startsWith("échangée") ? "Séances échangées insuffisantes"
        : reason.startsWith("valeur médiane") ? "Valeur médiane échangée insuffisante"
        : reason.startsWith("PER non publié") ? "PER non publié au BOC"
        : reason.startsWith("PER publié") ? "PER au-dessus du plafond Radar"
        : reason.startsWith("dividende") ? "Critère dividende non rempli"
        : "Cours absent";
      reasonCounts.set(key, (reasonCounts.get(key) || 0) + 1);
    }
  }
  return `<article class="card">
    <div class="event-row"><div><p class="eyebrow">Sélection automatique · BOC du ${fmtDate(latestBocDate())}</p><h2>${termButton("Radar SIGMA", "Radar SIGMA")} — les sociétés à étudier en premier</h2></div><span class="pill dark">${scored.length} éligible(s) / ${COMPANIES.length}</span></div>
    <p class="muted">SIGMA applique les mêmes règles aux ${COMPANIES.length} sociétés cotées à chaque collecte. Le Radar ordonne votre travail de lecture ; il ne connaît ni la qualité réelle des entreprises ni leurs résultats futurs. Aucune société n'est « recommandée ».</p>
    <div class="grid-3" style="margin:14px 0">
      <div class="key-fact"><span class="metric-label">Règle 1 — Échangeabilité</span><div class="metric-value" style="font-size:16px">≥ ${rules.minTradedSessions}/20 séances et ≥ ${fmtCompactFCFA(rules.minMedianTradedValue)} médiane</div><div class="subtext">Un versement de 100 000 à 300 000 FCFA doit rester une fraction raisonnable des échanges d'une séance type.</div></div>
      <div class="key-fact"><span class="metric-label">Règle 2 — Valorisation publiée</span><div class="metric-value" style="font-size:16px">PER BOC présent, entre 0 et ${rules.maxPer}</div><div class="subtext">Un PER absent signale souvent un bénéfice par action négatif ou non communiqué : hors premier tri, pas hors étude définitive.</div></div>
      <div class="key-fact"><span class="metric-label">Règle 3 — Dividende documenté</span><div class="metric-value" style="font-size:16px">Rendement &gt; 0, ≤ 15 %, &lt; 18 mois</div><div class="subtext">Les rendements extrêmes ou anciens sont écartés. L’historique BRVM par exercice est ensuite affiché pour distinguer une distribution régulière d’un paiement isolé ; il ne remplace pas le taux de distribution.</div></div>
    </div>
    <p class="source-line">Notation des éligibles : rangs parmi les éligibles — Liquidité ${rules.weights.liquidity} pts, Valorisation relative ${rules.weights.valuation} pts, Rendement ${rules.weights.yield} pts. Sélection limitée à ${rules.maxPerSector} sociétés par secteur pour éviter une liste mono-sectorielle.</p>
    <div class="form-actions"><button type="button" class="button" data-radar-watch-all>Ajouter la sélection (${selection.length}) à ma liste de suivi</button><button type="button" class="button button-secondary" data-analysis-link="decision">Préparer la décision du mois</button></div>
  </article>

  <div class="grid-2-equal section-space">${selection.map((entry, index) => radarEntryCard(entry, index + 1)).join("")}</div>

  ${overflow.length ? `<article class="card section-space"><p class="eyebrow">Éligibles suivantes</p><h2>Hors sélection : plafond sectoriel ou rang</h2>
    <div class="table-wrap"><table><thead><tr><th>Société</th><th class="num">Score d'étude</th><th class="num">PER BOC</th><th class="num">Rendement</th><th class="num">Liquidité méd.</th><th></th></tr></thead>
    <tbody>${overflow.map(entry => `<tr><td><div class="ticker">${entry.company.ticker}</div><div class="subtext">${escapeHtml(entry.company.name)} · ${escapeHtml(entry.company.sector)}</div></td><td class="num strong">${entry.score}/100</td><td class="num">${fmtRatio(entry.company.latest_boc?.per)}</td><td class="num">${fmtPct(entry.company.latest_boc?.net_dividend_yield_pct, 2, false)}</td><td class="num">${fmtCompactFCFA(entry.company.history_stats?.median_traded_value_last_20_fcfa)}</td><td><button type="button" class="button button-secondary button-small" data-open-company="${entry.company.ticker}">Fiche</button></td></tr>`).join("")}</tbody></table></div></article>` : ""}

  <article class="card section-space"><p class="eyebrow">Transparence du tri</p><h2>${rejected.length} société(s) écartée(s) par les règles</h2>
    <ul class="list-clean">${[...reasonCounts.entries()].sort((a, b) => b[1] - a[1]).map(([label, count]) => `<li class="event-row"><span>${escapeHtml(label)}</span><strong>${count}</strong></li>`).join("")}</ul>
    <p class="subtext">Une société peut cumuler plusieurs motifs. Être écartée du Radar ne signifie pas « mauvaise entreprise » : cela signifie que les données de marché vérifiées ne suffisent pas à la placer dans le premier périmètre d'étude.</p>
    <details style="margin-top:10px"><summary class="strong" style="cursor:pointer">Détail société par société</summary>
      <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>Société</th><th>Motif(s) d'écartement</th></tr></thead>
      <tbody>${rejected.map(item => `<tr><td><div class="ticker">${item.company.ticker}</div><div class="subtext">${escapeHtml(item.company.name)}</div></td><td>${item.reasons.map(escapeHtml).join(" · ")}</td></tr>`).join("")}</tbody></table></div>
    </details>
    <div class="notice" style="margin-top:14px"><p><strong>Limite assumée.</strong> Le Radar ne lit encore aucun état financier annuel : endettement, qualité des résultats et avantages concurrentiels restent à vérifier dans les rapports officiels. C'est le chantier qui transformera ce premier tri en scores SIGMA complets.</p></div>
  </article>`;
}

/* ---------------------------------------------------------------------------
   Préréglage de première ouverture : quatre réponses, puis la machine prend
   le relais (collecte, Radar, décision paramétrée). Rejouable dans Paramètres.
---------------------------------------------------------------------------- */
function sgisForCountry(country) {
  const all = DATA?.sgis || [];
  if (!country) return all;
  return all.filter(sgi => normalize(sgi.country || "") === normalize(country));
}

function openOnboarding() {
  const dialog = $("#onboardingDialog");
  const host = $("#onboardingContent");
  if (!dialog || !host || !DATA) return;
  const profile = personal.profile || {};
  const settings = personal.settings;
  const country = profile.country || "Côte d'Ivoire";
  host.innerHTML = `<div class="onboarding-body">
    <p class="eyebrow">Préréglage personnel · une seule fois</p>
    <h2 id="onboardingTitle" style="margin:4px 0 8px">Σ Bienvenue dans SIGMA</h2>
    <p class="muted">Quatre réponses pour que tout le reste soit automatique : collecte quotidienne des données officielles, sélection Radar, décision du mois calibrée sur votre versement. Ces réglages restent dans ce navigateur et se modifient dans Paramètres.</p>
    <form id="onboardingForm">
      <section class="onboarding-step"><p class="eyebrow">1 · Votre pays et votre ${termButton("SGI", "SGI")}</p>
        <div class="form-grid">
          <label>Pays de résidence<select name="country" id="onbCountry">
            ${UEMOA_COUNTRIES.map(c => `<option value="${c}" ${c === country ? "selected" : ""}>${c}</option>`).join("")}
            <option value="Autre" ${country === "Autre" ? "selected" : ""}>Autre pays</option>
          </select></label>
          <label>Votre SGI (annuaire officiel BRVM)<select name="sgiChoice" id="onbSgi"></select>
          <span class="field-hint">La BRVM publie les SGI agréées et leurs contacts, pas leurs tarifs : aucun classement tarifaire n'est inventé.</span></label>
          <label id="onbSgiFreeWrap" hidden>Nom exact de la SGI<input name="sgiFree" value="${escapeHtml(profile.sgiName || settings.sgiName || "")}" placeholder="Telle qu'écrite sur votre convention"></label>
          <label>Courtage de votre SGI (%) — optionnel<input name="feePct" type="number" min="0" step="0.001" value="${escapeHtml(settings.feePct)}" placeholder="Vide = frais non estimés"><span class="field-hint">À recopier depuis la grille tarifaire reçue de votre SGI.</span></label>
          <label>Frais fixes / minimum par ordre (FCFA) — optionnel<input name="fixedFee" type="number" min="0" step="1" value="${escapeHtml(settings.fixedFee)}" placeholder="Vide = frais non estimés"></label>
        </div>
      </section>

      <section class="onboarding-step"><p class="eyebrow">2 · Votre rythme d'investissement</p>
        <div class="form-grid">
          <label>Versement mensuel visé (FCFA)<input name="monthlyBudget" type="number" min="0" step="5000" required value="${escapeHtml(profile.monthlyBudget || settings.monthlyBudget || 200000)}"><span class="field-hint">La Décision du mois et le comparateur de frais utiliseront ce montant par défaut.</span></label>
          <label>Horizon de l'objectif principal</label>
        </div>
        <div class="choice-grid">
          <label><input type="radio" name="horizon" value="long" ${profile.horizon !== "moyen" ? "checked" : ""}><span><strong>Long terme (10 ans)</strong><br><span class="subtext">L'horizon pour lequel SIGMA est conçu : versements réguliers, dividendes réinvestis, décisions mensuelles.</span></span></label>
          <label><input type="radio" name="horizon" value="moyen" ${profile.horizon === "moyen" ? "checked" : ""}><span><strong>Moyen terme (3 à 5 ans)</strong><br><span class="subtext">Mêmes règles, en gardant en tête qu'une sortie forcée peut tomber sur une mauvaise année de marché.</span></span></label>
        </div>
        <div class="form-grid" style="margin-top:12px">
          <label class="checkbox-label"><input type="checkbox" name="pocketEnabled" id="onbPocket" ${profile.pocketEnabled ? "checked" : ""}> Réserver une poche d'apprentissage séparée</label>
          <label>Part du versement pour cette poche (%)<input name="pocketPct" id="onbPocketPct" type="number" min="0" max="50" step="5" value="${escapeHtml(profile.pocketPct ?? 10)}"><span class="field-hint">SIGMA ne propose pas de stratégie court terme : données de fin de journée, marché peu liquide et frais rendraient ce jeu perdant. Cette poche sert à apprendre avec de petits montants, séparée de l'objectif long terme.</span></label>
        </div>
      </section>

      <section class="onboarding-step"><p class="eyebrow">3 · Votre règle face à une baisse de 20 %</p>
        <div class="choice-grid">
          <label><input type="radio" name="riskReaction" value="renforcer" ${profile.riskReaction !== "attendre" && profile.riskReaction !== "alleger" ? "checked" : ""}><span><strong>Renforcer si la thèse reste intacte</strong><br><span class="subtext">La checklist baisse vérifiera d'abord dividende détaché, marché, secteur et publications.</span></span></label>
          <label><input type="radio" name="riskReaction" value="attendre" ${profile.riskReaction === "attendre" ? "checked" : ""}><span><strong>Attendre et relire</strong><br><span class="subtext">Aucune décision tant que les documents n'ont pas été relus.</span></span></label>
          <label><input type="radio" name="riskReaction" value="alleger" ${profile.riskReaction === "alleger" ? "checked" : ""}><span><strong>Alléger après relecture</strong><br><span class="subtext">Réduire l'exposition une fois la cause documentée dans le journal.</span></span></label>
        </div>
      </section>

      <div class="form-actions" style="margin-top:18px">
        <button type="submit" class="button">Terminer le préréglage</button>
        <button type="button" class="button button-secondary" id="onbLater">Plus tard</button>
      </div>
      <p class="source-line">Sans préréglage, SIGMA fonctionne avec des valeurs neutres (200 000 FCFA, frais non estimés) et vous reproposera cet écran à la prochaine ouverture. Aucune donnée personnelle ne quitte ce navigateur.</p>
    </form>
  </div>`;

  const countrySelect = $("#onbCountry");
  const sgiSelect = $("#onbSgi");
  const freeWrap = $("#onbSgiFreeWrap");
  const fillSgis = () => {
    const list = sgisForCountry(countrySelect.value === "Autre" ? "" : countrySelect.value);
    const current = profile.sgiName || settings.sgiName || "";
    sgiSelect.innerHTML = `<option value="">Je n'ai pas encore de SGI</option>`
      + list.map(sgi => `<option value="${escapeHtml(sgi.name)}" ${normalize(sgi.name) === normalize(current) ? "selected" : ""}>${escapeHtml(sgi.name)}${countrySelect.value === "Autre" && sgi.country ? ` — ${escapeHtml(sgi.country)}` : ""}</option>`).join("")
      + `<option value="__autre__">Autre SGI (saisie libre)</option>`;
    if (current && !list.some(sgi => normalize(sgi.name) === normalize(current))) {
      sgiSelect.value = "__autre__";
    }
    freeWrap.hidden = sgiSelect.value !== "__autre__";
  };
  fillSgis();
  countrySelect.addEventListener("change", fillSgis);
  sgiSelect.addEventListener("change", () => { freeWrap.hidden = sgiSelect.value !== "__autre__"; });
  const pocket = $("#onbPocket"), pocketPct = $("#onbPocketPct");
  const syncPocket = () => { pocketPct.disabled = !pocket.checked; };
  syncPocket();
  pocket.addEventListener("change", syncPocket);
  $("#onbLater").addEventListener("click", () => dialog.close());

  $("#onboardingForm").addEventListener("submit", event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const choice = String(form.get("sgiChoice") || "");
    const sgiName = choice === "__autre__" ? String(form.get("sgiFree") || "").trim() : choice;
    const monthlyBudget = Number(form.get("monthlyBudget")) || 0;
    personal.profile = {
      country: String(form.get("country") || ""),
      hasSgi: Boolean(sgiName),
      sgiName,
      monthlyBudget,
      horizon: String(form.get("horizon") || "long"),
      pocketEnabled: Boolean(form.get("pocketEnabled")),
      pocketPct: Math.min(50, Math.max(0, Number(form.get("pocketPct")) || 0)),
      riskReaction: String(form.get("riskReaction") || "renforcer"),
      onboardedAt: new Date().toISOString()
    };
    personal.settings.monthlyBudget = monthlyBudget;
    personal.settings.sgiName = sgiName;
    if (form.get("feePct") !== "") personal.settings.feePct = Number(form.get("feePct"));
    if (form.get("fixedFee") !== "") personal.settings.fixedFee = Number(form.get("fixedFee"));
    ui.decision.budget = monthlyBudget;
    savePersonal();
    dialog.close();
    renderDynamic();
    showToast("Préréglage enregistré : SIGMA est calibré sur votre pays, votre SGI et votre versement.");
  });

  if (!dialog.open) dialog.showModal();
}

function renderNews() {
  const host = $("#newsContent");
  if (!host) return;
  const sourceSelect = $("#newsSource");
  if (sourceSelect && !sourceSelect.dataset.filled) {
    const sources = [...new Map(newsItems().map(item => [item.source_id, item.source_label])).entries()];
    sourceSelect.innerHTML = `<option value="">Toutes les sources</option>` + sources.map(([id, label]) =>
      `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`).join("");
    sourceSelect.dataset.filled = "1";
    sourceSelect.value = ui.news.source;
  }
  const mine = new Set([...personal.watchlist, ...heldTickers()]);
  const search = normalize(ui.news.search);
  let items = newsItems().filter(item => {
    if (ui.news.relevance === "pertinent" && item.relevance === "general") return false;
    if (["societe", "marche", "macro"].includes(ui.news.relevance) && item.relevance !== ui.news.relevance) return false;
    if (ui.news.source && item.source_id !== ui.news.source) return false;
    if (ui.news.onlyMine && !(item.tickers || []).some(t => mine.has(t))) return false;
    if (search) {
      const blob = normalize(`${item.title} ${item.excerpt || ""} ${item.category || ""} ${(item.tickers || []).join(" ")} ${item.source_label}`);
      if (!blob.includes(search)) return false;
    }
    return true;
  });
  const total = items.length;
  items = items.slice(0, 60);
  const officialCount = newsItems().filter(item => item.source_type !== "presse_specialisee").length;
  host.innerHTML = `<article class="card">
    <div class="event-row"><div><p class="eyebrow">Collecte du ${fmtDateTime(DATA.generated_at)}</p><h2>${total} publication(s) correspondent au filtre</h2></div><span class="pill">${newsItems().length} collectées · ${officialCount} officielles</span></div>
    <p class="source-line">Ordre : date de publication décroissante. Les actualités BRVM ne portent pas de date de publication structurée : SIGMA signale alors « date mentionnée dans le texte ». La presse est étiquetée comme telle et ne remplace jamais l'annonce officielle de l'émetteur.</p>
    ${items.length ? items.map(newsItemHtml).join("") : '<div class="Empty-state">Aucune publication ne correspond à ce filtre dans la dernière collecte.</div>'}
    ${total > items.length ? `<p class="source-line" style="margin-top:10px">Affichage limité aux ${items.length} plus récentes ; affinez la recherche pour le reste.</p>` : ""}
  </article>`;
}

function renderAnalysisIndicators() {
  const sorted = [...COMPANIES].sort((a, b) => a.sector.localeCompare(b.sector, "fr") || a.name.localeCompare(b.name, "fr"));
  return `<article class="card">
    <div class="event-row"><div><p class="eyebrow">BOC du ${fmtDate(latestBocDate())}</p><h2>PER et rendement tels que publiés par la BRVM</h2></div><span class="pill amber">Descriptif, pas un score SIGMA</span></div>
    <p class="muted">Un PER bas ou un rendement élevé ne suffit jamais à conclure : bénéfices exceptionnels, dividende non récurrent, illiquidité ou risque propre peuvent expliquer l’écart. Les médianes sectorielles ci-dessous sont calculées par SIGMA depuis les valeurs du même BOC.</p>
    <div class="grid-3" style="margin:14px 0">${sectorList().map(sector => `<div class="key-fact"><span class="metric-label">${escapeHtml(sector)}</span><div class="metric-value">PER méd. ${fmtRatio(sectorMedian("per", sector))}</div><div class="subtext">Rendement net méd. ${fmtPct(sectorUsableYieldMedian(sector), 2, false)}</div></div>`).join("")}</div>
    <div class="table-wrap"><table><thead><tr><th>Société</th><th>Secteur</th><th class="num">${termButton("PER")} BOC</th><th class="num">Rendement net</th><th class="num">Dernier dividende BOC</th><th class="num">Var. année préc.</th></tr></thead>
    <tbody>${sorted.map(c => `<tr class="clickable-row" data-open-company="${c.ticker}"><td><div class="ticker">${c.ticker}</div><div class="subtext">${escapeHtml(c.name)}</div></td><td>${escapeHtml(c.sector)}</td><td class="num">${fmtRatio(c.latest_boc?.per)}</td><td class="num">${fmtPct(c.latest_boc?.net_dividend_yield_pct, 2, false)}${ratioWarning(c)}</td><td class="num">${fmtFCFA(c.latest_boc?.last_net_dividend_fcfa)}<div class="subtext">${escapeHtml(c.latest_boc?.last_dividend_date_label || "")}</div></td><td class="num">${fmtPct(c.latest_boc?.variation_previous_year_pct)}</td></tr>`).join("")}</tbody></table></div>
  </article>`;
}
function renderAnalysisLiquidity() {
  const rows = [...COMPANIES].sort((a, b) => (b.history_stats?.median_traded_value_last_20_fcfa ?? -1) - (a.history_stats?.median_traded_value_last_20_fcfa ?? -1));
  const max = Math.max(...rows.map(c => c.history_stats?.median_traded_value_last_20_fcfa || 0), 1);
  return `<article class="card"><p class="eyebrow">Calcul SIGMA · BOC officiels</p><h2>Liquidité sur les 20 dernières séances lues</h2>
  <p class="muted">La barre utilise une échelle racine carrée pour rester lisible malgré les très grandes valeurs. La médiane inclut les séances sans échange à zéro lorsqu’une ligne est présente au BOC.</p>
  <div class="table-wrap"><table><thead><tr><th>Société</th><th class="num">Échangée / 20</th><th>Valeur médiane par séance</th><th class="num">Montant</th><th class="num">5 séances</th><th class="num">20 séances</th></tr></thead>
  <tbody>${rows.map(c => {
    const value = c.history_stats?.median_traded_value_last_20_fcfa || 0;
    const width = Math.max(2, Math.sqrt(value / max) * 100);
    return `<tr class="clickable-row" data-open-company="${c.ticker}"><td><div class="ticker">${c.ticker}</div><div class="subtext">${escapeHtml(c.name)}</div></td><td class="num">${fmtNum(c.history_stats?.traded_sessions_last_20)}</td><td><div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div></td><td class="num">${fmtCompactFCFA(value)}</td><td class="num">${fmtPct(c.history_stats?.performance_5_sessions_pct)}</td><td class="num">${fmtPct(c.history_stats?.performance_20_sessions_pct)}</td></tr>`;
  }).join("")}</tbody></table></div></article>`;
}
function calculateAffordable(budget, price) {
  const feePct = personal.settings.feePct === "" ? null : Number(personal.settings.feePct);
  const fixedFee = personal.settings.fixedFee === "" ? null : Number(personal.settings.fixedFee);
  if (!isNum(price) || price <= 0 || !isNum(budget) || budget <= 0) return null;
  if (feePct === null || fixedFee === null || Number.isNaN(feePct) || Number.isNaN(fixedFee)) {
    const shares = Math.floor(budget / price);
    return { shares, invested: shares * price, fees: null, total: shares * price, remainder: budget - shares * price, feesKnown: false };
  }
  const available = Math.max(0, budget - fixedFee);
  const shares = Math.floor(available / (price * (1 + feePct / 100)));
  const invested = shares * price;
  const fees = shares ? fixedFee + invested * feePct / 100 : 0;
  return { shares, invested, fees, total: invested + fees, remainder: budget - invested - fees, feesKnown: true };
}
function renderAnalysisDecision() {
  const d = ui.decision;
  const budget = Number(d.budget) || 0;
  const pocketPct = personal.profile?.pocketEnabled ? Math.min(50, Math.max(0, Number(personal.profile.pocketPct) || 0)) : 0;
  const pocketAmount = Math.round(budget * pocketPct / 100);
  const workingBudget = Math.max(0, budget - pocketAmount);
  const reasons = { price: 0, sessions: 0, median: 0, criterion: 0, sector: 0 };
  const universe = d.source === "watchlist"
    ? COMPANIES.filter(c => personal.watchlist.includes(c.ticker))
    : d.source === "all" ? COMPANIES
    : computeRadar().scored.map(entry => entry.company);
  const outOfScope = COMPANIES.length - universe.length;
  let candidates = [];
  for (const company of universe) {
    const price = latestPrice(company).value;
    const stats = company.history_stats || {};
    if (d.sector && company.sector !== d.sector) { reasons.sector++; continue; }
    if (!isNum(price) || price > workingBudget) { reasons.price++; continue; }
    if ((stats.traded_sessions_last_20 ?? 0) < Number(d.minSessions || 0)) { reasons.sessions++; continue; }
    if (d.minMedianValue !== "" && (stats.median_traded_value_last_20_fcfa ?? 0) < Number(d.minMedianValue)) { reasons.median++; continue; }
    const criterionValue = d.criterion === "yield"
      ? (yieldScreenInfo(company).usable ? company.latest_boc?.net_dividend_yield_pct : null)
      : d.criterion === "per" ? company.latest_boc?.per
      : stats.median_traded_value_last_20_fcfa;
    if (!isNum(criterionValue) || (d.criterion === "per" && criterionValue <= 0)) { reasons.criterion++; continue; }
    const affordable = calculateAffordable(workingBudget, price);
    if (!affordable || affordable.shares < 1) { reasons.price++; continue; }
    candidates.push({ company, price, affordable, criterionValue });
  }
  candidates.sort((a, b) => d.criterion === "per" ? a.criterionValue - b.criterionValue : b.criterionValue - a.criterionValue);
  candidates = candidates.slice(0, 8);
  const feesKnown = personal.settings.feePct !== "" && personal.settings.fixedFee !== "";
  return `<div class="grid-2">
    <article class="card"><p class="eyebrow">Vos critères visibles</p><h2>Préparer le versement du mois</h2>
      <form id="decisionForm" class="form-grid">
        <label class="wide">Périmètre d'examen<select name="source">
          <option value="radar" ${d.source === "radar" ? "selected" : ""}>Sociétés éligibles au Radar SIGMA (sélection automatique par règles)</option>
          <option value="watchlist" ${d.source === "watchlist" ? "selected" : ""}>Ma liste de suivi personnelle</option>
          <option value="all" ${d.source === "all" ? "selected" : ""}>Toutes les sociétés cotées</option>
        </select><span class="field-hint">Le périmètre Radar (${computeRadar().scored.length} éligible(s) aujourd'hui) applique déjà échangeabilité, PER publié et dividende documenté.</span></label>
        <label>Budget disponible (FCFA)<input name="budget" type="number" min="0" step="1000" value="${escapeHtml(d.budget)}" required></label>
        <label>Secteur (optionnel)<select name="sector"><option value="">Tous</option>${sectorList().map(s => `<option value="${escapeHtml(s)}" ${s === d.sector ? "selected" : ""}>${escapeHtml(s)}</option>`).join("")}</select></label>
        <label>Séances échangées minimum / 20<input name="minSessions" type="number" min="0" max="20" value="${escapeHtml(d.minSessions)}"></label>
        <label>Valeur médiane minimum / séance (optionnel)<input name="minMedianValue" type="number" min="0" step="100000" value="${escapeHtml(d.minMedianValue)}" placeholder="Ex. 1 000 000"></label>
        <label class="wide">Ordre d’examen (descriptif)<select name="criterion">
          <option value="liquidity" ${d.criterion === "liquidity" ? "selected" : ""}>Liquidité médiane, décroissante (défaut prudent)</option>
          <option value="yield" ${d.criterion === "yield" ? "selected" : ""}>Rendement net BOC récent et non extrême, décroissant</option>
          <option value="per" ${d.criterion === "per" ? "selected" : ""}>PER publié au BOC, croissant</option>
        </select><span class="field-hint">Cet ordre sert à choisir quoi lire, pas quoi acheter automatiquement. Le filtre rendement écarte les rendements supérieurs à 15 % ou fondés sur un dernier dividende BOC de plus de 18 mois.</span></label>
        <div class="form-actions wide"><button class="button" type="submit">Recalculer la shortlist</button><button class="button button-secondary" type="button" data-view-link="parametres">Paramétrer les frais SGI</button></div>
      </form>
      <div class="${feesKnown ? "notice green" : "notice"} section-space"><p>${feesKnown ? `Frais estimés avec vos paramètres : ${escapeHtml(personal.settings.sgiName || "SGI")} · ${fmtNum(Number(personal.settings.feePct), 3)} % + ${fmtFCFA(Number(personal.settings.fixedFee))}.` : "<strong>Frais non estimés.</strong> Renseignez le courtage et le minimum de votre SGI dans Paramètres ; SIGMA n’invente aucun tarif."}</p></div>
    </article>
    <article class="card"><p class="eyebrow">Transparence du filtre</p><h2>Pourquoi les autres n’apparaissent pas</h2>
      <ul class="list-clean">
        <li class="event-row"><span>Hors périmètre choisi (${d.source === "radar" ? "non éligibles au Radar" : d.source === "watchlist" ? "absentes de votre liste de suivi" : "—"})</span><strong>${outOfScope}</strong></li>
        <li class="event-row"><span>Prix unitaire supérieur au budget ou aucun titre achetable après frais connus</span><strong>${reasons.price}</strong></li>
        <li class="event-row"><span>Moins de ${fmtNum(Number(d.minSessions || 0))} séances échangées sur 20</span><strong>${reasons.sessions}</strong></li>
        <li class="event-row"><span>Liquidité médiane sous votre seuil</span><strong>${reasons.median}</strong></li>
        <li class="event-row"><span>Critère BOC absent, rendement extrême/ancien écarté, ou PER non utilisable</span><strong>${reasons.criterion}</strong></li>
        <li class="event-row"><span>Hors secteur choisi</span><strong>${reasons.sector}</strong></li>
      </ul>
      <p class="source-line">Les fondamentaux restent conditionnels : seuls les piliers dont la série officielle est suffisante sont publiés en fiche. La shortlist ne remplace jamais la lecture des rapports et l’écriture de votre thèse.</p>
    </article>
  </div>
  <article class="card section-space"><p class="eyebrow">Shortlist documentée, pas classement d’achat</p><h2>${candidates.length} société(s) à examiner avec ${fmtFCFA(workingBudget)}${pocketPct ? ` <span class="pill">Objectif ${personal.profile?.horizon === "moyen" ? "moyen" : "long"} terme · ${fmtFCFA(pocketAmount)} réservés à la poche d'apprentissage (${fmtNum(pocketPct)} %)</span>` : ""}</h2>
    ${candidates.length ? `<div class="table-wrap"><table><thead><tr><th>Société</th><th class="num">Cours utilisé</th><th class="num">Titres possibles</th><th class="num">Investi</th><th class="num">Frais</th><th class="num">Reste</th><th class="num">PER / Rdt BOC</th><th></th></tr></thead><tbody>
      ${candidates.map(({ company, price, affordable }) => `<tr><td><div class="ticker">${company.ticker}</div><div class="subtext">${escapeHtml(company.name)} · ${escapeHtml(company.sector)}</div><div class="subtext">Liquidité méd. ${fmtCompactFCFA(company.history_stats?.median_traded_value_last_20_fcfa)} · ${fmtNum(company.history_stats?.traded_sessions_last_20)}/20 séances</div></td>
        <td class="num">${fmtFCFA(price)}</td><td class="num strong">${fmtNum(affordable.shares)}</td><td class="num">${fmtFCFA(affordable.invested)}</td><td class="num">${affordable.feesKnown ? fmtFCFA(Math.round(affordable.fees)) : "Non estimés"}</td><td class="num">${fmtFCFA(Math.round(affordable.remainder))}</td><td class="num">${fmtRatio(company.latest_boc?.per)} · ${fmtPct(company.latest_boc?.net_dividend_yield_pct, 2, false)}${ratioWarning(company)}</td>
        <td><div style="display:flex;gap:6px;flex-wrap:wrap"><button type="button" class="button button-secondary button-small" data-open-company="${company.ticker}">Fiche</button><button type="button" class="button button-small" data-journal-for="${company.ticker}">Thèse</button></div></td></tr>`).join("")}
    </tbody></table></div>` : '<div class="Empty-state">Aucune société ne passe ces filtres. Élargissez un critère plutôt que de forcer une conclusion.</div>'}
    <p class="source-line">Cours : dernier instantané officiel disponible. Le nombre de titres est un calcul de préparation ; l’ordre réel, s’il a lieu, se passe chez votre SGI après relecture des sources.</p>
  </article>`;
}
function marketPerformance(sessionsBack) {
  const levels = (DATA.history.sessions || []).map(s => s.composite_level).filter(isNum);
  if (levels.length <= sessionsBack) return null;
  return ((levels[levels.length - 1] / levels[levels.length - 1 - sessionsBack]) - 1) * 100;
}
function declineCauses(company, horizon) {
  const points = (company.series || []).filter(p => isNum(p.close));
  const referencePoint = points[points.length - 1 - horizon];
  const lastPoint = points[points.length - 1];
  const causes = [];
  if (referencePoint && lastPoint) {
    const hasExDiv = dividendsForTicker(company.ticker).some(d => d.ex_date && d.ex_date > referencePoint.date && d.ex_date <= lastPoint.date);
    if (hasExDiv) causes.push("Détachement de dividende dans la fenêtre");
  }
  const mkt = marketPerformance(horizon);
  if (isNum(mkt) && mkt <= -3) causes.push(`Marché en baisse sur la fenêtre (${fmtPct(mkt)})`);
  const field = horizon === 5 ? "performance_5_sessions_pct" : "performance_20_sessions_pct";
  const sectorMed = median(COMPANIES.filter(c => c.sector === company.sector).map(c => c.history_stats?.[field]));
  if (isNum(sectorMed) && sectorMed <= -5) causes.push(`Secteur également en baisse (médiane ${fmtPct(sectorMed)})`);
  return causes.length ? causes : ["Cause non identifiée dans les données SIGMA"];
}
function renderAnalysisDeclines() {
  const t5 = Number(personal.settings.decline5), t20 = Number(personal.settings.decline20);
  const rows = COMPANIES.filter(c => (isNum(c.history_stats?.performance_5_sessions_pct) && c.history_stats.performance_5_sessions_pct <= t5)
    || (isNum(c.history_stats?.performance_20_sessions_pct) && c.history_stats.performance_20_sessions_pct <= t20))
    .sort((a, b) => Math.min(a.history_stats.performance_5_sessions_pct ?? 999, a.history_stats.performance_20_sessions_pct ?? 999)
      - Math.min(b.history_stats.performance_5_sessions_pct ?? 999, b.history_stats.performance_20_sessions_pct ?? 999));
  return `<article class="card"><p class="eyebrow">Checklist avant émotion</p><h2>Baisses à examiner — seuils ${fmtPct(t5)} / 5 séances et ${fmtPct(t20)} / 20 séances</h2>
  <p class="muted">Les causes proposées sont des pistes ordonnées : dividende détaché, marché, secteur, puis inconnu. Elles ne remplacent ni la lecture d’un communiqué ni votre thèse initiale.</p>
  ${personal.profile?.riskReaction ? `<div class="notice" style="margin-top:12px"><p><strong>Votre règle déclarée au préréglage :</strong> ${escapeHtml(RISK_REACTION_LABELS[personal.profile.riskReaction] || "")}. SIGMA vous la rappelle ici pour que la décision du jour ressemble à celle que vous aviez choisie à froid.</p></div>` : ""}
  ${rows.length ? `<div class="stack" style="margin-top:14px">${rows.map(company => {
    const horizon = isNum(company.history_stats.performance_20_sessions_pct) && company.history_stats.performance_20_sessions_pct <= t20 ? 20 : 5;
    const causes = declineCauses(company, horizon);
    return `<section class="card" style="background:#fff"><div class="event-row"><div><div class="ticker">${company.ticker} · ${escapeHtml(company.name)}</div><div class="subtext">${escapeHtml(company.sector)} · BOC jusqu’au ${fmtDate(latestBocDate())}</div></div><div>${variationPill(company.history_stats.performance_5_sessions_pct)} ${variationPill(company.history_stats.performance_20_sessions_pct)}</div></div>
      <p style="margin:10px 0"><strong>Pistes à vérifier :</strong> ${causes.map(escapeHtml).join(" · ")}</p>
      <div class="form-actions"><button type="button" class="button button-secondary button-small" data-open-company="${company.ticker}">Relire la fiche</button><button type="button" class="button button-small" data-journal-for="${company.ticker}" data-journal-type="Checklist baisse">Documenter la checklist</button></div></section>`;
  }).join("")}</div>` : '<div class="Empty-state">Aucune valeur ne franchit vos seuils sur les BOC actuellement lus.</div>'}
  </article>`;
}
function renderAnalysisContext() {
  const events = [...personal.contextEvents].sort((a, b) => String(b.date).localeCompare(String(a.date)));
  return `<div class="grid-2">
    <article class="card"><p class="eyebrow">Préparer, pas prédire</p><h2>Ajouter un événement de contexte</h2>
      <p class="muted">Exemple : annonce de financement agricole, programme routier, décision BCEAO. Vous écrivez la chaîne de transmission et ce qui l’invaliderait. Aucun flux macro automatique non vérifié n’est injecté à ce stade.</p>
      <form id="contextForm" class="form-grid">
        <label>Date du fait<input name="date" type="date" required value="${new Date().toISOString().slice(0, 10)}"></label>
        <label>Stade de maturité<select name="stage"><option>M0 — Rumeur / presse seule</option><option selected>M1 — Annonce officielle</option><option>M2 — Financement engagé</option><option>M3 — Mise en œuvre</option><option>M4 — Effet économique visible</option><option>M5 — Effet dans les résultats</option></select></label>
        <label class="wide">Fait daté<input name="title" required placeholder="Ex. Convention de financement signée pour…"></label>
        <label class="wide">Source primaire (URL)<input name="sourceUrl" type="url" required placeholder="https://…"></label>
        <label class="wide">Tickers potentiellement exposés<input name="tickers" placeholder="Ex. SMBC, BOAC — séparés par des virgules"><span class="field-hint">À documenter dans les rapports annuels ; SIGMA ne déduit pas l’exposition du seul secteur.</span></label>
        <label class="wide">Chaîne de transmission envisagée<textarea name="transmission" required placeholder="Fait → effet intermédiaire → grandeur observable chez la société"></textarea></label>
        <label>Indicateurs à vérifier<textarea name="indicators" required placeholder="Volumes, créances, dépôts, marges…"></textarea></label>
        <label>Ce qui invaliderait<textarea name="invalidation" required placeholder="Fait observable qui contredirait cette lecture"></textarea></label>
        <div class="form-actions wide"><button class="button" type="submit">Enregistrer l’événement</button></div>
      </form>
    </article>
    <article class="card"><p class="eyebrow">Registre personnel</p><h2>Événements et scénarios en surveillance</h2>
      ${events.length ? `<div class="stack">${events.map(event => `<section class="card" style="box-shadow:none"><div class="event-row"><div><div class="strong">${escapeHtml(event.title)}</div><div class="subtext">${fmtDate(event.date)} · ${escapeHtml(event.stage)}</div></div><button type="button" class="icon-button" data-delete-context="${event.id}" aria-label="Supprimer">×</button></div>
        <p><strong>Chaîne :</strong> ${escapeHtml(event.transmission)}</p><p><strong>À vérifier :</strong> ${escapeHtml(event.indicators)}</p><p><strong>Invalidation :</strong> ${escapeHtml(event.invalidation)}</p>
        <p class="small">Tickers notés : ${event.tickers.length ? event.tickers.map(t => `<button type="button" class="text-button ticker" data-open-company="${t}">${t}</button>`).join(" · ") : "aucun"}<br><a href="${escapeHtml(event.sourceUrl)}" target="_blank" rel="noopener">Ouvrir la source primaire</a></p></section>`).join("")}</div>` : '<div class="Empty-state">Aucun événement enregistré. Une annonce politique ne devient utile que lorsqu’on écrit par quel canal elle atteindrait une société cotée.</div>'}
      <div class="notice section-space"><p><strong>Règle SIGMA :</strong> un événement M1 se surveille ; il ne modifie aucun score et ne produit aucun libellé d’achat. On conclut lorsque les effets deviennent observables (M4–M5).</p></div>
    </article>
  </div>`;
}
function renderAnalyses() {
  const host = $("#analysisContent");
  if (!host) return;
  $$("[data-analysis-tab]").forEach(tab => tab.classList.toggle("is-active", tab.dataset.analysisTab === ui.analysisTab));
  host.innerHTML = ui.analysisTab === "radar" ? renderAnalysisRadar()
    : ui.analysisTab === "liquidite" ? renderAnalysisLiquidity()
    : ui.analysisTab === "decision" ? renderAnalysisDecision()
    : ui.analysisTab === "baisses" ? renderAnalysisDeclines()
    : ui.analysisTab === "contexte" ? renderAnalysisContext()
    : renderAnalysisIndicators();
  const decisionForm = $("#decisionForm");
  if (decisionForm) decisionForm.addEventListener("submit", event => {
    event.preventDefault();
    const form = new FormData(decisionForm);
    ui.decision = {
      budget: Number(form.get("budget")) || 0,
      source: String(form.get("source") || "radar"),
      sector: String(form.get("sector") || ""),
      minSessions: Number(form.get("minSessions")) || 0,
      minMedianValue: form.get("minMedianValue") === "" ? "" : Number(form.get("minMedianValue")),
      criterion: String(form.get("criterion") || "yield")
    };
    renderAnalyses();
  });
  const contextForm = $("#contextForm");
  if (contextForm) contextForm.addEventListener("submit", event => {
    event.preventDefault();
    const form = new FormData(contextForm);
    const tickers = String(form.get("tickers") || "").split(/[,\s]+/).map(t => t.trim().toUpperCase()).filter(t => BY_TICKER.has(t));
    personal.contextEvents.unshift({
      id: crypto.randomUUID(), date: String(form.get("date")), stage: String(form.get("stage")),
      title: String(form.get("title")).trim(), sourceUrl: String(form.get("sourceUrl")).trim(), tickers,
      transmission: String(form.get("transmission")).trim(), indicators: String(form.get("indicators")).trim(),
      invalidation: String(form.get("invalidation")).trim(), createdAt: new Date().toISOString()
    });
    savePersonal(); renderAnalyses(); showToast("Événement de contexte enregistré dans votre registre local.");
  });
}

function tickerOptions(selected = "") {
  return COMPANIES.map(c => `<option value="${c.ticker}" ${c.ticker === selected ? "selected" : ""}>${c.ticker} — ${escapeHtml(c.name)}</option>`).join("");
}
function renderPortfolio() {
  const host = $("#portfolioContent");
  if (!host) return;
  const kind = ui.portfolioKind;
  const result = computePortfolio(kind);
  const journal = [...personal.journal].sort((a, b) => String(b.date).localeCompare(String(a.date)) || String(b.createdAt).localeCompare(String(a.createdAt)));
  const prefill = ui.journalPrefill || {};
  const today = new Date().toISOString().slice(0, 10);
  const allocationMap = new Map();
  result.holdings.forEach(h => {
    const sector = h.company?.sector || "Non renseigné";
    allocationMap.set(sector, (allocationMap.get(sector) || 0) + (h.marketValue || 0));
  });
  const allocations = [...allocationMap.entries()].sort((a, b) => b[1] - a[1]);

  host.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:16px">
      <div class="segmented" role="tablist" aria-label="Type de portefeuille">
        <button type="button" data-portfolio-kind="reel" class="${kind === "reel" ? "is-active" : ""}">Réel — saisi manuellement</button>
        <button type="button" data-portfolio-kind="virtuel" class="${kind === "virtuel" ? "is-active" : ""}">Virtuel — simulation</button>
      </div>
      <span class="pill ${kind === "reel" ? "dark" : "amber"}">${kind === "reel" ? "PORTEFEUILLE RÉEL" : "PORTEFEUILLE VIRTUEL"}</span>
    </div>
    ${result.warnings.length ? `<div class="notice" style="margin-bottom:16px">${result.warnings.map(w => `<p>${escapeHtml(w)}</p>`).join("")}</div>` : ""}
    <div class="grid-4">
      <article class="card kpi-card"><span class="kpi-label">Valeur au dernier cours</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(result.marketValue)}</div><div class="kpi-sub muted">Instantané BRVM, hors frais de revente</div></div></article>
      <article class="card kpi-card"><span class="kpi-label">Flux net investi</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(result.netContributions)}</div><div class="kpi-sub muted">Achats + frais − ventes nettes</div></div></article>
      <article class="card kpi-card"><span class="kpi-label">Dividendes saisis</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(result.dividendsCash)}</div><div class="kpi-sub muted">Montants nets que vous avez enregistrés</div></div></article>
      <article class="card kpi-card"><span class="kpi-label">Résultat réalisé des ventes</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(Math.round(result.realised))}</div><div class="kpi-sub muted">Au prix de revient moyen, frais saisis inclus</div></div></article>
    </div>

    <div class="grid-2 section-space">
      <article class="card"><p class="eyebrow">Positions ${kind === "reel" ? "réelles saisies" : "virtuelles"}</p><h2>Lignes détenues</h2>
        ${result.holdings.length ? `<div class="table-wrap"><table><thead><tr><th>Société</th><th class="num">Qté</th><th class="num">PRU</th><th class="num">Cours</th><th class="num">Valeur</th><th class="num">Latent</th><th class="num">Poids</th></tr></thead><tbody>
          ${result.holdings.map(h => `<tr class="clickable-row" data-open-company="${h.ticker}"><td><div class="ticker">${h.ticker}</div><div class="subtext">${escapeHtml(h.company?.name || "Ticker inconnu des données actuelles")}</div></td><td class="num">${fmtNum(h.qty)}</td><td class="num">${fmtFCFA(Math.round(h.avgCost || 0))}</td><td class="num">${fmtFCFA(h.price)}</td><td class="num strong">${fmtFCFA(h.marketValue)}</td><td class="num ${h.latent >= 0 ? "positive" : "negative"}">${fmtFCFA(Math.round(h.latent || 0))}</td><td class="num">${fmtPct(h.weightPct, 1)}</td></tr>`).join("")}
        </tbody></table></div>` : '<div class="Empty-state">Aucune ligne dans ce portefeuille. Ajoutez une transaction réellement exécutée chez votre SGI, ou simulez dans l’onglet Virtuel.</div>'}
      </article>
      <article class="card"><p class="eyebrow">Concentration</p><h2>Répartition par secteur</h2>
        ${allocations.length ? allocations.map(([sector, value]) => {
          const pct = result.marketValue ? value / result.marketValue * 100 : 0;
          return `<div class="allocation-row"><span>${escapeHtml(sector)}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><strong style="text-align:right">${fmtPct(pct, 1)}</strong></div>`;
        }).join("") : '<div class="Empty-state">La répartition apparaîtra dès la première ligne.</div>'}
        <p class="source-line">Le plafond de secteur du CDC est un repère de lecture, pas une règle automatique d’achat ou de vente.</p>
      </article>
    </div>

    <div class="grid-2 section-space">
      <article class="card"><p class="eyebrow">Saisie manuelle vérifiable</p><h2>Ajouter une transaction ${kind}</h2>
        <form id="transactionForm" class="form-grid">
          <label>Type<select name="type" id="txType"><option value="achat">Achat</option><option value="vente">Vente</option><option value="dividende">Dividende net reçu</option></select></label>
          <label>Date<input name="date" type="date" required value="${today}"></label>
          <label class="wide">Société<select name="ticker" required>${tickerOptions(prefill.ticker || "")}</select></label>
          <label id="txQtyLabel">Quantité<input name="qty" type="number" min="0" step="1" value="1"></label>
          <label id="txPriceLabel">Prix par action (FCFA)<input name="price" type="number" min="0" step="1"></label>
          <label id="txAmountLabel" hidden>Montant net reçu (FCFA)<input name="amount" type="number" min="0" step="1"></label>
          <label id="txFeesLabel">Frais réels/simulés (FCFA)<input name="fees" type="number" min="0" step="1" value="0"></label>
          <div class="form-actions wide"><button class="button" type="submit">Ajouter au portefeuille ${kind}</button></div>
        </form>
        <p class="source-line">SIGMA ne se connecte pas à votre SGI et ne passe aucun ordre.</p>
      </article>
      <article class="card"><p class="eyebrow">Décider avec mémoire</p><h2>Écrire au journal</h2>
        <form id="journalForm" class="form-grid">
          <label>Type<select name="type"><option ${prefill.type === "Thèse" ? "selected" : ""}>Thèse</option><option ${prefill.type === "Checklist baisse" ? "selected" : ""}>Checklist baisse</option><option>Note</option><option>Contexte</option></select></label>
          <label>Date<input name="date" type="date" required value="${today}"></label>
          <label class="wide">Société (optionnel)<select name="ticker"><option value="">Aucune / marché</option>${tickerOptions(prefill.ticker || "")}</select></label>
          <label class="wide">Titre<input name="title" required value="${escapeHtml(prefill.title || "")}" placeholder="Ex. Pourquoi j’envisage cette société ce mois-ci"></label>
          <label class="wide">Thèse, faits et risques<textarea name="text" required placeholder="Faits sourcés, ce que j’attends, risques, horizon…">${escapeHtml(prefill.text || "")}</textarea></label>
          <label class="wide">Ce qui invaliderait cette lecture<textarea name="invalidation" placeholder="Résultat, dividende, événement ou chiffre précis à surveiller">${escapeHtml(prefill.invalidation || "")}</textarea></label>
          <div class="form-actions wide"><button class="button" type="submit">Enregistrer dans le journal</button></div>
        </form>
      </article>
    </div>

    <div class="grid-2-equal section-space">
      <article class="card"><p class="eyebrow">Historique ${kind}</p><h2>Transactions</h2>
        ${result.transactions.length ? `<ul class="list-clean">${[...result.transactions].reverse().map(tx => `<li class="event-row"><div><div class="strong">${escapeHtml(tx.type)} · ${tx.ticker}</div><div class="subtext">${fmtDate(tx.date)}${tx.type === "dividende" ? ` · ${fmtFCFA(Number(tx.amount))}` : ` · ${fmtNum(Number(tx.qty))} × ${fmtFCFA(Number(tx.price))} · frais ${fmtFCFA(Number(tx.fees || 0))}`}</div></div><button type="button" class="icon-button" data-delete-transaction="${tx.id}" aria-label="Supprimer la transaction">×</button></li>`).join("")}</ul>` : '<div class="Empty-state">Aucune transaction enregistrée.</div>'}
      </article>
      <article class="card"><p class="eyebrow">Journal horodaté</p><h2>Thèses, notes et checklists</h2>
        ${journal.length ? `<ul class="list-clean">${journal.map(item => `<li><div class="event-row"><div><div class="strong">${escapeHtml(item.title)}</div><div class="subtext">${fmtDate(item.date)} · ${escapeHtml(item.type)}${item.ticker ? ` · ${item.ticker}` : ""}</div></div><button type="button" class="icon-button" data-delete-journal="${item.id}" aria-label="Supprimer la note">×</button></div><p>${escapeHtml(item.text)}</p>${item.invalidation ? `<p class="small"><strong>Invalidation :</strong> ${escapeHtml(item.invalidation)}</p>` : ""}</li>`).join("")}</ul>` : '<div class="Empty-state">Votre journal est vide. La première thèse vaut plus qu’un dixième graphique.</div>'}
      </article>
    </div>`;

  $$("[data-portfolio-kind]").forEach(button => button.addEventListener("click", () => {
    ui.portfolioKind = button.dataset.portfolioKind; renderPortfolio(); renderHome(); updateAlertBadge();
  }));
  const txType = $("#txType");
  const syncTxType = () => {
    const isDividend = txType.value === "dividende";
    $("#txQtyLabel").hidden = isDividend; $("#txPriceLabel").hidden = isDividend; $("#txFeesLabel").hidden = isDividend;
    $("#txAmountLabel").hidden = !isDividend;
  };
  txType.addEventListener("change", syncTxType); syncTxType();

  $("#transactionForm").addEventListener("submit", event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const type = String(form.get("type"));
    const tx = {
      id: crypto.randomUUID(), type, ticker: String(form.get("ticker")), date: String(form.get("date")),
      qty: type === "dividende" ? 0 : Number(form.get("qty")), price: type === "dividende" ? 0 : Number(form.get("price")),
      fees: type === "dividende" ? 0 : Number(form.get("fees") || 0), amount: type === "dividende" ? Number(form.get("amount")) : 0,
      createdAt: new Date().toISOString()
    };
    if (type !== "dividende" && (!tx.qty || tx.qty <= 0 || !tx.price || tx.price <= 0)) { showToast("Quantité et prix doivent être supérieurs à zéro."); return; }
    if (type === "dividende" && (!tx.amount || tx.amount <= 0)) { showToast("Le montant net du dividende doit être supérieur à zéro."); return; }
    personal.portfolios[kind].transactions.push(tx);
    savePersonal(); renderDynamic(); showView("portefeuille");
    showToast(`Transaction ${type} enregistrée dans le portefeuille ${kind}.`);
  });
  $("#journalForm").addEventListener("submit", event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    personal.journal.unshift({
      id: crypto.randomUUID(), type: String(form.get("type")), date: String(form.get("date")),
      ticker: String(form.get("ticker") || ""), title: String(form.get("title")).trim(),
      text: String(form.get("text")).trim(), invalidation: String(form.get("invalidation") || "").trim(),
      createdAt: new Date().toISOString()
    });
    ui.journalPrefill = null;
    savePersonal(); renderDynamic(); showView("portefeuille");
    showToast("Entrée de journal enregistrée.");
  });
}

function updateAlertBadge() {
  const count = DATA ? unreadAlertCount() : 0;
  const badge = $("#alertBadge");
  badge.textContent = count; badge.hidden = count === 0;
}
function renderAlerts() {
  const host = $("#alertsContent");
  if (!host) return;
  const alerts = generateAlerts();
  host.innerHTML = alerts.length ? `<div class="stack">${alerts.map(alert => {
    const read = personal.alertsRead.includes(alert.id);
    return `<article class="card alert-card ${read ? "is-read" : ""}"><span class="alert-icon ${alert.tone}">${alert.icon}</span>
      <div style="flex:1"><div class="event-row"><h3 style="margin:0">${escapeHtml(alert.title)}</h3><span class="pill">${fmtDate(alert.date)}</span></div>
      <p>${escapeHtml(alert.body)}</p><p class="small muted">${escapeHtml(alert.meta)}</p>
      <div class="form-actions">${alert.ticker ? `<button type="button" class="button button-secondary button-small" data-open-company="${alert.ticker}">Ouvrir la fiche</button>` : ""}${alert.url ? `<a class="button button-secondary button-small" href="${alert.url}" target="_blank" rel="noopener">Source officielle</a>` : ""}<button type="button" class="button button-small" data-mark-alert="${alert.id}">${read ? "Marquer non lu" : "Marquer lu"}</button></div></div></article>`;
  }).join("")}</div>` : '<div class="Empty-state">Aucune alerte factuelle à afficher.</div>';
  updateAlertBadge();
}

function renderReports() {
  const host = $("#reportsContent");
  if (!host) return;
  const q = normalize(ui.reportSearch);
  const pages = DATA.report_pages.filter(page => !q || normalize(page.label).includes(q));
  const dividends = [...DATA.dividends].sort((a, b) => String(b.payment_date || "").localeCompare(String(a.payment_date || "")));
  const events = calendarEvents();
  host.innerHTML = `
    <article class="card"><div class="event-row"><div><p class="eyebrow">Échéances datées par les sources</p><h2>Calendrier d’échéances — dividendes, titres publics, BCEAO</h2></div><span class="pill">${events.length} échéance(s)</span></div>
      ${events.length ? `<div class="table-wrap"><table><thead><tr><th>Date</th><th>Catégorie</th><th>Échéance</th><th class="num">Montant publié</th><th></th></tr></thead><tbody>
      ${events.map(event => `<tr><td class="strong">${fmtDate(event.date)}<div class="subtext">J+${event.in_days} à la collecte</div></td><td>${escapeHtml(event.category || "")}</td><td><div class="strong">${escapeHtml(event.title)}</div><div class="subtext">${escapeHtml(event.detail || "")}</div><div class="subtext">Source : ${escapeHtml(event.source_label || "")}</div></td><td class="num">${calendarEventAmount(event) || "—"}</td><td>${event.url ? `<a class="button button-secondary button-small" href="${event.url}" target="_blank" rel="noopener">Source</a>` : ""}</td></tr>`).join("")}
      </tbody></table></div>` : '<div class="Empty-state">Aucune échéance future datée par une source officielle dans cette collecte.</div>'}
      <p class="source-line">SIGMA n’ajoute pas de dates estimées : dividendes BRVM, opérations UMOA-Titres et événements BCEAO uniquement lorsqu’une source officielle publie la date.</p>
    </article>

    <article class="card section-space"><div class="event-row"><div><p class="eyebrow">Historique utilisé par SIGMA</p><h2>Bulletins Officiels de la Cote</h2></div><span class="pill">${DATA.history.sessions.length} BOC analysés</span></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Statut dans SIGMA</th><th>Empreinte SHA-256</th><th></th></tr></thead><tbody>
      ${DATA.boc_documents.map(doc => `<tr><td class="strong">${fmtDate(doc.date)}</td><td>${doc.parsed ? '<span class="pill green">Lu et contrôlé</span>' : '<span class="pill">Indexé, non lu dans cette collecte</span>'}</td><td class="mono">${doc.sha256 ? `${doc.sha256.slice(0, 18)}…` : "—"}</td><td><a class="button button-secondary button-small" href="${doc.url}" target="_blank" rel="noopener">PDF officiel</a></td></tr>`).join("")}
      </tbody></table></div></article>

    <article class="card section-space"><p class="eyebrow">Tableau officiel BRVM · historique paginé collecté (${DATA.coverage.dividend_rows_collected ?? dividends.length} lignes${DATA.coverage.dividend_fiscal_years_min ? `, exercices ${DATA.coverage.dividend_fiscal_years_min}–${DATA.coverage.dividend_fiscal_years_max}` : ""})</p><h2>Avis et calendrier de dividendes</h2>
      <div class="table-wrap"><table><thead><tr><th>Émetteur publié</th><th>Exercice</th><th>Ex-dividende</th><th>Paiement</th><th class="num">Montant net</th><th></th></tr></thead><tbody>
      ${dividends.map(div => `<tr><td class="strong">${escapeHtml(div.issuer)}</td><td>${escapeHtml(div.fiscal_year)}</td><td>${fmtDate(div.ex_date)}</td><td>${fmtDate(div.payment_date)}</td><td class="num">${fmtFCFA(div.net_amount_fcfa)}</td><td>${div.notice_url ? `<a class="button button-secondary button-small" href="${div.notice_url}" target="_blank" rel="noopener">Avis</a>` : ""}</td></tr>`).join("")}
      </tbody></table></div></article>

    <article class="card section-space"><div class="event-row"><div><p class="eyebrow">Bibliothèque des émetteurs</p><h2>Pages de rapports sur brvm.org (${pages.length} affichée(s))</h2></div><a class="button button-secondary" href="https://www.brvm.org/fr/rapports-societes-cotees" target="_blank" rel="noopener">Index officiel</a></div>
      <p class="muted">Ces pages regroupent les rapports publiés par les émetteurs. SIGMA les indexe et en extrait automatiquement une partie des agrégats annuels sous contrôles ; les annexes et la vérification humaine ligne à ligne restent à faire.</p>
      <div class="grid-3" style="margin-top:14px">${pages.map(page => `<a class="card" style="text-decoration:none;color:inherit" href="${page.url}" target="_blank" rel="noopener"><span class="eyebrow">Émetteur</span><h3>${escapeHtml(page.label)}</h3><span class="small">Ouvrir les rapports officiels ↗</span></a>`).join("")}</div>
    </article>`;
}

function coverageAuditRows() {
  const cov = DATA.coverage || {};
  const totalCompanies = COMPANIES.length || 1;
  const pctOfCompanies = count => Math.round(((count || 0) / totalCompanies) * 100);
  const allFigures = COMPANIES.flatMap(company => fundamentalSeries(company).flatMap(entry => Object.entries(entry.figures || {})));
  const confirmedFigures = allFigures.filter(([, figure]) => figure?.confidence === "confirme_deux_documents").length;
  const confirmedShare = allFigures.length ? Math.round((confirmedFigures / allFigures.length) * 100) : 0;
  const long250 = COMPANIES.filter(company => isNum(company.history_stats?.long_history?.performance_250_sessions_pct)).length;
  const newsSources = new Set(newsItems().map(item => item.source_label || item.source_id).filter(Boolean)).size;
  const debtCashKeys = ["dettes_financieres", "tresorerie", "flux_tresorerie_operationnel", "flux_operationnel"];
  const debtCashFigures = allFigures.filter(([key]) => debtCashKeys.includes(key)).length;
  const shareDataCompanies = COMPANIES.filter(company => isNum(company.shares_outstanding) || isNum(company.capitalisation_fcfa) || isNum(company.free_float_pct)).length;
  const sgiFeesPublished = (DATA.sgis || []).filter(sgi => sgi.fees_status && sgi.fees_status !== "non_publies_par_la_brvm").length;
  const ageHours = Math.max(0, Math.round((Date.now() - new Date(DATA.generated_at).getTime()) / 36e5));
  const row = (block, measure, excellence, status, nextStep) => ({ block, measure, excellence, status, nextStep });
  const byShare = (count, excellentAt = 90, solidAt = 75, partialAt = 40) => {
    const share = pctOfCompanies(count);
    return share >= excellentAt ? "Excellent" : share >= solidAt ? "Solide" : share >= partialAt ? "Partiel" : "Insuffisant";
  };
  return [
    row("Cours, BOC et liquidité", `${cov.boc_archive_sessions ?? 0} séances archivées · performance 250 séances pour ${long250}/${totalCompanies} sociétés · prix publiés non ajustés`, "≥ 260 séances et ≥ 90 % des sociétés à 250 séances", (cov.boc_archive_sessions ?? 0) >= 260 && pctOfCompanies(long250) >= 90 ? "Excellent" : (cov.boc_archive_sessions ?? 0) >= 120 ? "Solide" : "Partiel", "Étendre l’archive au-delà d’un an et traiter les opérations sur titres/ajustements."),
    row("Documents officiels indexés", `${cov.issuer_documents_indexed ?? 0} documents · ${cov.companies_with_indexed_documents ?? 0}/${totalCompanies} sociétés`, "≥ 98 % des sociétés avec bibliothèque indexée", byShare(cov.companies_with_indexed_documents ?? 0, 98, 90, 60), "Rattacher la société sans document ou documenter son absence à la source."),
    row("Séries fondamentales", `${cov.companies_with_series_3y ?? 0}/${totalCompanies} sociétés avec ≥ 3 exercices (${pctOfCompanies(cov.companies_with_series_3y ?? 0)} %)`, "≥ 90 % des sociétés avec ≥ 3 exercices", byShare(cov.companies_with_series_3y ?? 0), "OCR contrôlé des rapports scannés et formats IFRS/SYSCOHADA encore rejetés."),
    row("Recoupement des agrégats", `${confirmedFigures}/${allFigures.length} agrégats confirmés par deux documents (${confirmedShare} %)`, "≥ 70 % confirmés par deux documents", confirmedShare >= 70 ? "Excellent" : confirmedShare >= 50 ? "Solide" : confirmedShare >= 25 ? "Partiel" : "Insuffisant", "Augmenter la couverture documentaire par exercice et résoudre les divergences signalées."),
    row("Historique des dividendes (montants)", `${cov.dividend_rows_collected ?? 0} lignes BRVM · exercices ${cov.dividend_fiscal_years_min ?? "—"}–${cov.dividend_fiscal_years_max ?? "—"} · ${cov.companies_with_any_dividend_history ?? 0} sociétés rattachées`, "Historique paginé complet, ≥ 40 sociétés rattachées", (cov.dividend_rows_collected ?? 0) >= 300 && (cov.companies_with_any_dividend_history ?? 0) >= 40 ? "Excellent" : (cov.dividend_rows_collected ?? 0) >= 100 ? "Solide" : "Partiel", "Vérifier les émetteurs non rattachés et les changements de nom/code."),
    row("Dividende durable (payout et cash)", "Taux de distribution et couverture par les flux non calculés", "BPA/nombre d’actions et flux vérifiés pour ≥ 90 % des payeurs", "Insuffisant", "Extraire BPA ou nombre d’actions et flux de trésorerie depuis les états officiels."),
    row("Dette, trésorerie et flux", `${debtCashFigures} agrégat(s) de dette/trésorerie/flux dans les séries`, "Séries pluriannuelles recoupées pour ≥ 90 % des sociétés", debtCashFigures ? "Partiel" : "Insuffisant", "Ajouter les annexes dette, trésorerie et tableau des flux aux règles d’extraction."),
    row("Capital : actions, flottant, capitalisation", `${shareDataCompanies}/${totalCompanies} sociétés avec donnée de capital vérifiée dans le fichier`, "≥ 90 % des sociétés avec source et date", byShare(shareDataCompanies), "Collecter nombre d’actions, flottant et opérations sur titres depuis une source officielle datée."),
    row("Actualités et annonces", `${cov.news_items ?? newsItems().length} éléments · ${newsSources} source(s) · ${cov.news_with_ticker ?? 0} rattaché(s)`, "Archive profonde, corps vérifiés et rattachement audité", (cov.news_items ?? 0) >= 100 && newsSources >= 4 ? "Solide" : "Partiel", "Approfondir l’archive et contrôler les rattachements groupe/filiales."),
    row("Macro BCEAO / UMOA immédiate", `CPM ${escapeHtml(cov.macro_bceao_cpm_status || "non collecté")} · ${cov.umoa_upcoming_issuances ?? 0} opérations UMOA à venir · ${cov.calendar_events ?? 0} échéances`, "Décision CPM complète + calendrier officiel à 90 jours", cov.macro_bceao_cpm_status === "collecte" && (cov.umoa_upcoming_issuances ?? 0) >= 20 ? "Solide" : "Partiel", "Ajouter historique CPM, résultats et rendements d’adjudications UMOA."),
    row("Annuaire SGI", `${cov.sgis_official_directory ?? (DATA.sgis || []).length} SGI officielles par pays`, "Annuaire officiel complet", (cov.sgis_official_directory ?? 0) >= 37 ? "Excellent" : "Partiel", "Maintenir la collecte de l’annuaire BRVM."),
    row("Tarifs SGI", `${sgiFeesPublished} grille(s) tarifaire(s) publiée(s) par la source collectée`, "Grilles datées et comparables pour les SGI du pays choisi", sgiFeesPublished ? "Partiel" : "Insuffisant", "Obtenir des grilles écrites datées ; aucun tarif n’est estimé."),
    row("Fraîcheur de la collecte affichée", `Collecte générée il y a environ ${ageHours} h`, "Collecte automatique quotidienne prouvée et datée", ageHours <= 72 ? "Solide" : "Partiel", "Activer et surveiller la collecte automatique lorsque l’hébergement sera mis en place."),
  ];
}

function renderSettings() {
  const host = $("#settingsContent");
  if (!host) return;
  const s = personal.settings;
  host.innerHTML = `
    <div class="grid-2">
      <article class="card"><p class="eyebrow">Profil d’utilisation</p><h2>Budget, SGI et seuils personnels</h2>
        <form id="settingsForm" class="form-grid">
          <label>Budget mensuel habituel (FCFA)<input name="monthlyBudget" type="number" min="0" step="1000" value="${escapeHtml(s.monthlyBudget)}"><span class="field-hint">Votre fourchette de travail est de 100 000 à 300 000 FCFA ; ce champ reste modifiable chaque mois dans Décision.</span></label>
          <label>Nom de votre SGI<input name="sgiName" value="${escapeHtml(s.sgiName)}" placeholder="À compléter"></label>
          <label>Courtage SGI (%)<input name="feePct" type="number" min="0" step="0.001" value="${escapeHtml(s.feePct)}" placeholder="Vide = non estimé"></label>
          <label>Frais fixes / minimum par ordre (FCFA)<input name="fixedFee" type="number" min="0" step="1" value="${escapeHtml(s.fixedFee)}" placeholder="Vide = non estimé"></label>
          <label>Seuil checklist 5 séances (%)<input name="decline5" type="number" step="0.5" value="${escapeHtml(s.decline5)}"></label>
          <label>Seuil checklist 20 séances (%)<input name="decline20" type="number" step="0.5" value="${escapeHtml(s.decline20)}"></label>
          <div class="form-actions wide"><button class="button" type="submit">Enregistrer les paramètres</button></div>
        </form>
      </article>
      <article class="card"><p class="eyebrow">Sauvegarde locale</p><h2>Vos données vous appartiennent</h2>
        <p>Watchlist, portefeuilles, journal, événements et réglages sont stockés uniquement dans ce navigateur. Exportez régulièrement un fichier JSON de sauvegarde.</p>
        <div class="form-actions"><button type="button" class="button" id="exportData">Exporter mes données</button>
        <label class="button button-secondary" style="display:inline-flex">Importer<input id="importData" type="file" accept="application/json" hidden></label>
        <button type="button" class="button button-danger" id="resetData">Réinitialiser l’espace personnel</button></div>
        <div class="notice section-space"><p>La réinitialisation supprime uniquement les données personnelles locales, jamais les données de marché collectées.</p></div>
      </article>
    </div>
    <div class="grid-2 section-space">
      <article class="card"><p class="eyebrow">Préréglage personnel</p><h2>Votre configuration SIGMA</h2>
        ${personal.profile ? `<ul class="list-clean">
          <li class="event-row"><span>Pays</span><strong>${escapeHtml(personal.profile.country || "—")}</strong></li>
          <li class="event-row"><span>SGI</span><strong>${escapeHtml(personal.profile.sgiName || "Pas encore choisie")}</strong></li>
          <li class="event-row"><span>Versement mensuel visé</span><strong>${fmtFCFA(personal.profile.monthlyBudget)}</strong></li>
          <li class="event-row"><span>Objectif principal</span><strong>${personal.profile.horizon === "moyen" ? "Moyen terme (3–5 ans)" : "Long terme (10 ans)"}</strong></li>
          <li class="event-row"><span>Poche d'apprentissage</span><strong>${personal.profile.pocketEnabled ? `${fmtNum(personal.profile.pocketPct)} % du versement` : "Désactivée"}</strong></li>
          <li class="event-row"><span>Règle face à −20 %</span><strong>${escapeHtml(RISK_REACTION_LABELS[personal.profile.riskReaction] || "—")}</strong></li>
        </ul>` : '<div class="Empty-state">Préréglage non effectué : SIGMA utilise des valeurs neutres et ne connaît ni votre pays ni votre SGI.</div>'}
        <div class="form-actions" style="margin-top:12px"><button type="button" class="button" data-open-onboarding>${personal.profile ? "Modifier le préréglage" : "Lancer le préréglage"}</button></div>
      </article>
      <article class="card"><p class="eyebrow">Annuaire officiel BRVM · collecte du ${fmtDate(DATA.generated_at.slice(0, 10))}</p><h2>SGI agréées ${personal.profile?.country && personal.profile.country !== "Autre" ? `en ${escapeHtml(personal.profile.country)}` : "dans l'UEMOA"}</h2>
        ${(() => {
          const list = personal.profile?.country && personal.profile.country !== "Autre" ? sgisForCountry(personal.profile.country) : (DATA.sgis || []);
          if (!list.length) return '<div class="Empty-state">Annuaire indisponible dans la dernière collecte.</div>';
          const shown = list.slice(0, personal.profile?.country && personal.profile.country !== "Autre" ? 40 : 12);
          return `<ul class="list-clean">${shown.map(sgi => `<li class="event-row"><div><div class="strong">${escapeHtml(sgi.name)}</div><div class="subtext">${escapeHtml(sgi.country || "Pays non précisé")}${sgi.country_basis === "indicatif_telephonique_publie" ? " (déduit de l'indicatif publié)" : ""}${sgi.phone ? ` · ${escapeHtml(sgi.phone)}` : ""}${sgi.email ? ` · ${escapeHtml(sgi.email)}` : ""}</div></div>${sgi.website ? `<a class="button button-secondary button-small" href="${escapeHtml(sgi.website)}" target="_blank" rel="noopener">Site</a>` : ""}</li>`).join("")}</ul>
          ${list.length > shown.length ? `<p class="source-line">Affichage limité : ${list.length} SGI dans l'annuaire collecté. Faites le préréglage avec votre pays pour la liste ciblée.</p>` : ""}
          <p class="source-line">Tarifs : <strong>non publiés par la BRVM</strong>. Demandez la grille écrite à chaque SGI, puis comparez ci-dessous sur vos propres chiffres.</p>`;
        })()}
      </article>
    </div>

    <article class="card section-space"><p class="eyebrow">Comparer sans se faire vendre un classement</p><h2>Coût d'un ordre mensuel selon les tarifs que vous saisissez</h2>
      <p class="muted">SIGMA ne décerne pas de titre de « meilleure SGI » : il calcule le coût d'un ordre de ${fmtFCFA(personal.settings.monthlyBudget || 0)} (votre versement) avec les grilles écrites que vous recueillez. Service, application, délais et accompagnement restent à juger par vous.</p>
      <form id="sgiQuoteForm" class="form-grid">
        <label>SGI<input name="name" required placeholder="Nom de la SGI" list="sgiSuggestions"><datalist id="sgiSuggestions">${(DATA.sgis || []).map(sgi => `<option value="${escapeHtml(sgi.name)}">`).join("")}</datalist></label>
        <label>Courtage (%)<input name="feePct" type="number" min="0" step="0.001" required placeholder="Ex. 0,90"></label>
        <label>Frais fixes / minimum par ordre (FCFA)<input name="fixedFee" type="number" min="0" step="1" required placeholder="Ex. 2 500"></label>
        <div class="form-actions"><button type="submit" class="button">Ajouter ce tarif daté</button></div>
      </form>
      ${personal.sgiQuotes?.length ? (() => {
        const amount = Number(personal.settings.monthlyBudget) || 0;
        const rows = personal.sgiQuotes.map(q => ({ ...q, cost: amount * (Number(q.feePct) || 0) / 100 + (Number(q.fixedFee) || 0) })).sort((a, b) => a.cost - b.cost);
        return `<div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>SGI</th><th>Tarif saisi le</th><th class="num">Courtage</th><th class="num">Fixe</th><th class="num">Coût / ordre de ${fmtCompactFCFA(amount)}</th><th></th></tr></thead>
        <tbody>${rows.map((q, i) => `<tr><td class="strong">${escapeHtml(q.name)} ${i === 0 ? '<span class="pill green">Coût le plus bas sur vos chiffres</span>' : ""}</td><td>${fmtDate((q.createdAt || "").slice(0, 10))}</td><td class="num">${fmtNum(Number(q.feePct), 3)} %</td><td class="num">${fmtFCFA(Number(q.fixedFee))}</td><td class="num strong">${fmtFCFA(Math.round(q.cost))}</td><td><div style="display:flex;gap:6px;flex-wrap:wrap"><button type="button" class="button button-small" data-apply-quote="${q.id}">Appliquer à mes frais</button><button type="button" class="button button-secondary button-small" data-delete-quote="${q.id}">Retirer</button></div></td></tr>`).join("")}</tbody></table></div>
        <p class="source-line">Hors taxes et droits éventuels non inclus dans les chiffres saisis. Un tarif se périme : re-vérifiez avant d'ouvrir ou de changer de SGI.</p>`;
      })() : '<div class="Empty-state" style="margin-top:14px">Aucun tarif saisi. Demandez deux ou trois grilles écrites : la différence de coût sur 10 ans de versements mensuels est un des rares gains certains.</div>'}
    </article>

    <article class="card section-space"><p class="eyebrow">Transparence de collecte</p><h2>Manifeste des données affichées</h2>
      <div class="grid-4">
        <div class="key-fact"><span class="metric-label">Collecte générée</span><div class="metric-value" style="font-size:16px">${fmtDateTime(DATA.generated_at)}</div></div>
        <div class="key-fact"><span class="metric-label">Sociétés instantané</span><div class="metric-value">${DATA.coverage.companies_in_snapshot}</div></div>
        <div class="key-fact"><span class="metric-label">BOC analysés</span><div class="metric-value">${DATA.coverage.boc_sessions}</div><div class="subtext">Archive longue : ${DATA.coverage.boc_archive_sessions ?? 0} séances (${fmtDate(DATA.coverage.boc_archive_first_date)} → ${fmtDate(DATA.coverage.boc_archive_last_date)})</div></div>
        <div class="key-fact"><span class="metric-label">Actualités collectées</span><div class="metric-value">${DATA.coverage.news_items ?? 0}</div><div class="subtext">${DATA.coverage.news_with_ticker ?? 0} rattachée(s) à une société</div></div>
        <div class="key-fact"><span class="metric-label">Séries fondamentales ≥ 3 exercices</span><div class="metric-value">${DATA.coverage.companies_with_series_3y ?? 0} sociétés</div><div class="subtext">${DATA.coverage.figures_confirmed_by_two_documents ?? 0} agrégat(s) confirmé(s) par deux documents · ${DATA.coverage.issuer_documents_indexed ?? 0} documents émetteurs indexés (${DATA.coverage.companies_with_indexed_documents ?? 0} sociétés)</div></div>
        <div class="key-fact"><span class="metric-label">Macro &amp; échéances</span><div class="metric-value">${DATA.coverage.calendar_events ?? 0} échéance(s)</div><div class="subtext">CPM BCEAO ${escapeHtml(DATA.coverage.macro_bceao_cpm_status || "non collecté")} · taux ${fmtPct(DATA.coverage.macro_bceao_policy_rate_pct, 2, false)} · ${DATA.coverage.umoa_upcoming_issuances ?? 0} émission(s) UMOA à venir · prochaine échéance ${fmtDate(DATA.coverage.calendar_next_date)}</div></div>
        <div class="key-fact"><span class="metric-label">Historique officiel des dividendes</span><div class="metric-value">${DATA.coverage.dividend_rows_collected ?? 0} lignes</div><div class="subtext">Exercices ${DATA.coverage.dividend_fiscal_years_min ?? "—"}–${DATA.coverage.dividend_fiscal_years_max ?? "—"} · ${DATA.coverage.companies_with_any_dividend_history ?? 0} sociétés rattachées · ${DATA.coverage.companies_with_dividend_history_5y ?? 0} documentées sur les 5 derniers exercices</div></div>
      </div>
      <h3 style="margin-top:22px">État de couverture mesuré — objectif : excellent partout</h3>
      <p class="muted">Cet état est recalculé depuis le fichier de données affiché. « Excellent » n’est attribué que si le seuil écrit est atteint ; les blocs incomplets restent visibles avec leur prochaine correction, au lieu d’être masqués par une moyenne.</p>
      <div class="table-wrap"><table><thead><tr><th>Bloc de données</th><th>Mesure dans cette collecte</th><th>Seuil « excellent »</th><th>État</th><th>Prochaine correction</th></tr></thead>
      <tbody>${coverageAuditRows().map(item => `<tr><td class="strong">${item.block}</td><td>${item.measure}</td><td>${item.excellence}</td><td><span class="pill ${item.status === "Excellent" ? "green" : item.status === "Partiel" ? "amber" : item.status === "Insuffisant" ? "red" : ""}">${item.status}</span></td><td>${item.nextStep}</td></tr>`).join("")}</tbody></table></div>
      <h3 style="margin-top:20px">Sources primaires utilisées</h3>
      <ul>${DATA.sources.map(source => `<li><a href="${source.url}" target="_blank" rel="noopener">${escapeHtml(source.label)}</a></li>`).join("")}</ul>
      <h3>Avertissements qualité</h3>
      ${DATA.quality_warnings.length ? `<ul>${DATA.quality_warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}</ul>` : '<p class="positive"><strong>Aucun avertissement</strong> sur la dernière collecte publiée.</p>'}
      <div class="notice blue"><p><strong>Comprendre SIGMA.</strong> Outil personnel d’information et d’apprentissage. Il ne fournit pas de conseil financier personnalisé, ne prédit pas les cours et ne passe aucun ordre. Vérifiez toujours les documents officiels et les conditions de votre SGI avant une décision. Investir comporte un risque de perte en capital.</p></div>
    </article>
    <article class="card section-space"><p class="eyebrow">Apprendre en lisant</p><h2>Glossaire intégré</h2>
      <div class="grid-2-equal">${Object.entries(GLOSSARY).map(([term, definition]) => `<div class="key-fact"><h3>${escapeHtml(term)}</h3><p>${escapeHtml(definition)}</p></div>`).join("")}</div>
    </article>`;

  $("#settingsForm").addEventListener("submit", event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    personal.settings = {
      monthlyBudget: Number(form.get("monthlyBudget")) || 0,
      sgiName: String(form.get("sgiName") || "").trim(),
      feePct: form.get("feePct") === "" ? "" : Number(form.get("feePct")),
      fixedFee: form.get("fixedFee") === "" ? "" : Number(form.get("fixedFee")),
      decline5: Number(form.get("decline5")), decline20: Number(form.get("decline20"))
    };
    ui.decision.budget = personal.settings.monthlyBudget;
    savePersonal(); renderDynamic(); showView("parametres"); showToast("Paramètres enregistrés localement.");
  });
  $("#sgiQuoteForm").addEventListener("submit", event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    personal.sgiQuotes = personal.sgiQuotes || [];
    personal.sgiQuotes.push({
      id: crypto.randomUUID(),
      name: String(form.get("name") || "").trim(),
      feePct: Number(form.get("feePct")),
      fixedFee: Number(form.get("fixedFee")),
      createdAt: new Date().toISOString()
    });
    savePersonal(); renderSettings(); showToast("Tarif SGI ajouté à la comparaison locale.");
  });
  $("#exportData").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), personal }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `sigma-donnees-personnelles-${new Date().toISOString().slice(0, 10)}.json`; a.click();
    URL.revokeObjectURL(url);
  });
  $("#importData").addEventListener("change", async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      if (!parsed.personal || typeof parsed.personal !== "object") throw new Error("Format non reconnu");
      personal = { ...structuredClone(DEFAULT_PERSONAL), ...parsed.personal, settings: { ...DEFAULT_PERSONAL.settings, ...(parsed.personal.settings || {}) } };
      savePersonal(); renderDynamic(); showView("parametres"); showToast("Sauvegarde personnelle importée.");
    } catch (_) { showToast("Import impossible : fichier personnel SIGMA non reconnu."); }
  });
  $("#resetData").addEventListener("click", () => {
    if (!confirm("Supprimer watchlist, portefeuilles, journal, événements et réglages enregistrés dans ce navigateur ?")) return;
    personal = structuredClone(DEFAULT_PERSONAL); ui.decision.budget = personal.settings.monthlyBudget;
    savePersonal(); renderDynamic(); showView("parametres"); showToast("Espace personnel réinitialisé.");
  });
}

function updateNewsBadge() {
  const badge = $("#newsBadge");
  if (!badge || !DATA) return;
  const cutoff = daysBeforeIso(DATA.generated_at.slice(0, 10), 7);
  const count = newsItems().filter(item => item.relevance !== "general" && item.published_date && item.published_date >= cutoff).length;
  badge.textContent = count;
  badge.hidden = count === 0;
}

function renderDynamic() {
  if (!DATA) return;
  renderFreshness(); renderHome(); renderMarket(); renderCompanies(); renderAnalyses();
  renderNews(); renderPortfolio(); renderAlerts(); renderReports(); renderSettings();
  if (ui.selectedTicker) renderCompanyDetail();
  updateAlertBadge();
  updateNewsBadge();
}

function applyHashRoute() {
  const hash = location.hash.replace("#", "");
  if (hash.startsWith("fiche-")) {
    const ticker = hash.replace("fiche-", "").toUpperCase();
    if (BY_TICKER.has(ticker)) { showView("fiche", ticker); return; }
    showView("accueil"); return;
  }
  if (["accueil", "marche", "entreprises", "analyses", "actualites", "portefeuille", "alertes", "rapports", "parametres"].includes(hash)) {
    showView(hash); return;
  }
  showView("accueil");
}

function bindStaticEvents() {
  window.addEventListener("hashchange", applyHashRoute);
  $$(".nav-item").forEach(button => button.addEventListener("click", () => showView(button.dataset.view)));
  $("#backToCompanies").addEventListener("click", () => showView("entreprises"));
  $$("[data-analysis-tab]").forEach(tab => tab.addEventListener("click", () => { ui.analysisTab = tab.dataset.analysisTab; renderAnalyses(); }));
  $("#companySearch").addEventListener("input", event => { ui.companySearch = event.target.value; renderCompanies(); });
  $("#companySector").addEventListener("change", event => { ui.companySector = event.target.value; renderCompanies(); });
  $("#companySort").addEventListener("change", event => { ui.companySort = event.target.value; renderCompanies(); });
  $("#watchOnly").addEventListener("change", event => { ui.watchOnly = event.target.checked; renderCompanies(); });
  $("#reportSearch").addEventListener("input", event => { ui.reportSearch = event.target.value; renderReports(); });
  $("#newsRelevance").addEventListener("change", event => { ui.news.relevance = event.target.value; renderNews(); });
  $("#newsSource").addEventListener("change", event => { ui.news.source = event.target.value; renderNews(); });
  $("#newsSearch").addEventListener("input", event => { ui.news.search = event.target.value; renderNews(); });
  $("#newsOnlyMine").addEventListener("change", event => { ui.news.onlyMine = event.target.checked; renderNews(); });
  document.addEventListener("input", event => {
    if (event.target.id === "orderQty") updateOrderPrep();
  });
  $("#markAlertsRead").addEventListener("click", () => {
    personal.alertsRead = [...new Set([...personal.alertsRead, ...generateAlerts().map(a => a.id)])];
    savePersonal(); renderAlerts();
  });
  const search = $("#globalSearch");
  search.addEventListener("change", () => {
    const value = search.value.trim();
    const ticker = value.split(/\s|—/)[0].toUpperCase();
    if (BY_TICKER.has(ticker)) { showView("fiche", ticker); return; }
    const found = COMPANIES.find(c => normalize(c.name) === normalize(value));
    if (found) showView("fiche", found.ticker);
  });
  search.addEventListener("input", () => {
    ui.companySearch = search.value;
    const input = $("#companySearch"); if (input) input.value = search.value;
    if (ui.view !== "entreprises" && search.value.length >= 2) showView("entreprises");
    renderCompanies();
  });
  $("#termDialogClose").addEventListener("click", () => $("#termDialog").close());

  document.addEventListener("click", event => {
    const viewLink = event.target.closest("[data-view-link]");
    if (viewLink) { showView(viewLink.dataset.viewLink); return; }
    const analysisLink = event.target.closest("[data-analysis-link]");
    if (analysisLink) { ui.analysisTab = analysisLink.dataset.analysisLink; renderAnalyses(); showView("analyses"); return; }
    const radarWatchAll = event.target.closest("[data-radar-watch-all]");
    if (radarWatchAll) {
      const tickers = computeRadar().selection.map(entry => entry.company.ticker);
      const added = tickers.filter(ticker => !personal.watchlist.includes(ticker));
      personal.watchlist = [...new Set([...personal.watchlist, ...tickers])].sort();
      savePersonal(); renderDynamic(); showView("analyses");
      showToast(added.length ? `${added.length} société(s) du Radar ajoutée(s) à votre liste de suivi.` : "La sélection Radar est déjà dans votre liste de suivi.");
      return;
    }
    const simulateOrder = event.target.closest("[data-simulate-order]");
    if (simulateOrder) {
      const company = BY_TICKER.get(simulateOrder.dataset.simulateOrder);
      const qty = Number($("#orderQty")?.value) || 0;
      const result = company ? orderPrepMath(company, qty) : null;
      if (!result || !result.quantity || !isNum(result.price)) { showToast("Quantité ou cours publié indisponible pour simuler."); return; }
      personal.portfolios.virtuel.transactions.push({
        id: crypto.randomUUID(), type: "achat", ticker: company.ticker,
        date: new Date().toISOString().slice(0, 10),
        qty: result.quantity, price: result.price,
        fees: result.feesKnown ? result.fees : 0, amount: 0,
        createdAt: new Date().toISOString()
      });
      ui.portfolioKind = "virtuel";
      savePersonal(); renderDynamic(); showView("portefeuille");
      showToast(`Simulation : ${result.quantity} × ${company.ticker} à ${fmtFCFA(result.price)} (cours publié)${result.feesKnown ? "" : " · frais comptés à 0 faute de grille SGI"}. Aucun ordre réel n'a été passé.`);
      return;
    }
    if (event.target.closest("[data-open-onboarding]")) { openOnboarding(); return; }
    const applyQuote = event.target.closest("[data-apply-quote]");
    if (applyQuote) {
      const quote = (personal.sgiQuotes || []).find(q => q.id === applyQuote.dataset.applyQuote);
      if (quote) {
        personal.settings.sgiName = quote.name;
        personal.settings.feePct = Number(quote.feePct);
        personal.settings.fixedFee = Number(quote.fixedFee);
        if (personal.profile) { personal.profile.sgiName = quote.name; personal.profile.hasSgi = true; }
        savePersonal(); renderDynamic(); showView("parametres");
        showToast(`Frais de ${quote.name} appliqués à vos paramètres.`);
      }
      return;
    }
    const deleteQuote = event.target.closest("[data-delete-quote]");
    if (deleteQuote) {
      personal.sgiQuotes = (personal.sgiQuotes || []).filter(q => q.id !== deleteQuote.dataset.deleteQuote);
      savePersonal(); renderSettings(); return;
    }
    const watch = event.target.closest("[data-toggle-watch]");
    if (watch) { event.stopPropagation(); toggleWatch(watch.dataset.toggleWatch); return; }
    const journalFor = event.target.closest("[data-journal-for]");
    if (journalFor) {
      const ticker = journalFor.dataset.journalFor;
      ui.journalPrefill = { ticker, type: journalFor.dataset.journalType || "Thèse", title: journalFor.dataset.journalType === "Checklist baisse" ? `Checklist baisse — ${ticker}` : `Thèse — ${ticker}` };
      renderPortfolio(); showView("portefeuille"); return;
    }
    const open = event.target.closest("[data-open-company]");
    if (open && !event.target.closest("a")) { showView("fiche", open.dataset.openCompany); return; }
    const term = event.target.closest("[data-term]");
    if (term) {
      $("#termTitle").textContent = term.dataset.term;
      $("#termBody").textContent = GLOSSARY[term.dataset.term] || "Définition à compléter.";
      $("#termDialog").showModal(); return;
    }
    const delTx = event.target.closest("[data-delete-transaction]");
    if (delTx) {
      const kind = ui.portfolioKind;
      personal.portfolios[kind].transactions = personal.portfolios[kind].transactions.filter(tx => tx.id !== delTx.dataset.deleteTransaction);
      savePersonal(); renderDynamic(); showView("portefeuille"); return;
    }
    const delJournal = event.target.closest("[data-delete-journal]");
    if (delJournal) {
      personal.journal = personal.journal.filter(item => item.id !== delJournal.dataset.deleteJournal);
      savePersonal(); renderDynamic(); showView("portefeuille"); return;
    }
    const delContext = event.target.closest("[data-delete-context]");
    if (delContext) {
      personal.contextEvents = personal.contextEvents.filter(item => item.id !== delContext.dataset.deleteContext);
      savePersonal(); renderAnalyses(); return;
    }
    const mark = event.target.closest("[data-mark-alert]");
    if (mark) {
      const id = mark.dataset.markAlert;
      personal.alertsRead = personal.alertsRead.includes(id) ? personal.alertsRead.filter(item => item !== id) : [...personal.alertsRead, id];
      savePersonal(); renderAlerts();
    }
  });
}

async function init() {
  try {
    const response = await fetch("data/data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    DATA = await response.json();
    COMPANIES = DATA.companies || [];
    BY_TICKER = new Map(COMPANIES.map(company => [company.ticker, company]));
    const datalist = $("#companySuggestions");
    datalist.innerHTML = COMPANIES.map(c => `<option value="${c.ticker} — ${escapeHtml(c.name)}"></option>`).join("");
    bindStaticEvents();
    $("#loadingState").hidden = true;
    renderDynamic();

    applyHashRoute();
    if (!personal.profile?.onboardedAt) openOnboarding();
  } catch (error) {
    $("#loadingState").innerHTML = `<div class="loading-mark">Σ</div><p>Impossible de charger les données SIGMA (${escapeHtml(error.message)}).<br>Relancez la collecte officielle avant d’ouvrir l’application : aucun chiffre de remplacement ne sera inventé.</p>`;
    const message = $("#appMessage");
    message.hidden = false;
    message.textContent = "Données de marché indisponibles : SIGMA refuse d’afficher une démo ou des valeurs fabriquées.";
  }
}

document.addEventListener("DOMContentLoaded", init);

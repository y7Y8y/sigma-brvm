"use strict";

/* SIGMA — interface personnelle BRVM.
   Les données de marché viennent de data/data.json (sources officielles BRVM).
   Les données personnelles restent dans localStorage, sur cet appareil. */

const STORAGE_KEY = "sigma_personal_v1";

/* Compatibilité : structuredClone n'existe pas avant Safari 15.4 ni sur certains
   WebView Android anciens. Sans ce repli, TOUTE l'application échouait au
   chargement sur ces appareils — pas seulement une fonctionnalité. Le repli
   reste sûr ici : les données personnelles ne contiennent que des types simples. */
const cloneSur = (typeof structuredClone === "function")
  ? structuredClone
  : (valeur) => JSON.parse(JSON.stringify(valeur));
const DEFAULT_PERSONAL = {
  profile: null,
  onboardingDismissedAt: null,
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
    decline20: -15,
    autoFollowRadar: true
  }
};

const GLOSSARY = {
  PER: "Prix de l'action divisé par le bénéfice net par action. En clair : combien d'années de bénéfice actuel le prix représente. Dans SIGMA, le PER affiché est celui publié par la BRVM dans le BOC, avec sa date ; il ne dit pas à lui seul qu'une action est bon marché.",
  "Rendement net": "Dernier dividende net par action divisé par le cours, tel que publié dans le BOC. Il peut augmenter mécaniquement quand le cours baisse : un rendement élevé peut donc signaler une opportunité à étudier ou une difficulté, jamais un revenu garanti.",
  "Bénéfice net par action": "Part du bénéfice annuel attribuable à une action, telle que publiée dans les états financiers. SIGMA l'affiche avec sa ligne source et son niveau de recoupement lorsqu'elle est lisible ; elle n'est jamais multipliée par l'unité en milliers ou millions du tableau.",
  "Liquidité": "Facilité à acheter ou vendre grâce à des échanges réguliers. SIGMA la décrit par le nombre de séances échangées et la valeur médiane négociée. Une action peu liquide peut être difficile à vendre au prix affiché.",
  "Séance": "Journée de cotation à la BRVM. Quand SIGMA parle de 20 séances, il s'agit d'environ un mois de Bourse, pas de 20 jours calendaires.",
  "Volume": "Nombre de titres échangés. SIGMA le lit dans la cote/BOC officiels. Un volume élevé un seul jour ne suffit pas à prouver une liquidité régulière.",
  "Valeur échangée": "Montant total des échanges sur un titre ou le marché pendant la séance. Elle complète le volume : beaucoup de titres à bas prix ne représentent pas forcément beaucoup d'argent échangé.",
  "Valeur médiane": "Valeur du milieu après classement : la moitié des séances sont au-dessus, l'autre moitié au-dessous. SIGMA l'utilise pour éviter qu'une séance exceptionnelle donne une fausse impression de liquidité habituelle.",
  "Prix seuls": "Variation calculée uniquement avec les cours, sans réinvestir les dividendes et sans ajuster les opérations sur titres. Elle situe le parcours du prix, mais ne mesure pas la performance totale d'un actionnaire.",
  "Volatilité": "Ampleur habituelle des variations du cours, annualisée dans SIGMA depuis l'archive BOC. Une volatilité élevée signifie des mouvements plus forts, pas automatiquement une mauvaise entreprise.",
  "Repli maximal observé": "Plus forte baisse mesurée entre un point haut passé et le point bas qui suit dans l'archive disponible. Cela montre ce qui s'est déjà produit ; la baisse future peut être plus forte.",
  "Largeur du marché": "Répartition des valeurs en hausse, en baisse ou inchangées. Elle permet de distinguer un mouvement général d'un mouvement concentré sur quelques sociétés.",
  "Concentration des échanges": "Part de la valeur échangée captée par les titres les plus actifs. Plus elle est élevée, plus l'activité du marché dépend d'un petit nombre de valeurs.",
  "BOC": "Bulletin Officiel de la Cote, publication officielle de la BRVM après la séance. Dans SIGMA, il sert de preuve datée pour les cours, volumes, PER et rendements historiques.",
  "Empreinte SHA-256": "Code unique calculé depuis le contenu exact d'un fichier PDF. Il permet de vérifier que le BOC utilisé par SIGMA est bien le même document et qu'il n'a pas été confondu avec un autre.",
  "BRVM Composite": "Indice qui résume l'évolution d'ensemble des actions cotées à la BRVM. Il peut monter alors qu'une société précise baisse ; il sert de contexte, pas de jugement sur chaque titre.",
  "Dividende": "Part du bénéfice qu'une société verse à ses actionnaires. SIGMA affiche les montants nets par action publiés par la BRVM. Un dividende passé ne garantit ni son renouvellement ni son montant futur.",
  "Ex-dividende": "À partir de cette date, l'action s'échange sans le droit au dividende annoncé. Le cours baisse souvent d'un montant proche du dividende : ce n'est pas automatiquement une mauvaise nouvelle.",
  "Date de paiement": "Date à laquelle le dividende est mis en paiement selon l'avis officiel. La date exacte de crédit chez votre SGI peut dépendre de ses délais de traitement.",
  "Taux de distribution": "Part du bénéfice versée en dividendes. La BRVM publie ici un dividende net par action : lorsque SIGMA le rapporte au bénéfice par action du même exercice, il libelle le résultat « dividende net / BPA ». Ce repère ne doit pas être confondu avec le taux brut voté en assemblée générale.",
  "Dividende durable": "Lecture SIGMA encore sans score : un dividende semble soutenable seulement si les bénéfices et les flux de trésorerie le couvrent dans la durée. SIGMA publie désormais les repères calculables exercice par exercice, mais ne les fusionne pas en note tant que la couverture des sociétés reste incomplète.",
  "Couverture par les flux": "Flux de trésorerie opérationnel divisé par la distribution nette totale calculée pour le même exercice. Au-dessus de 1,00×, l'activité a dégagé plus de cash que cette distribution calculée ; en dessous, elle n'a pas suffi cette année-là. La couverture après investissements retire en plus les achats d'immobilisations corporelles et incorporelles lus dans le tableau des flux.",
  "Flux de trésorerie opérationnel": "Cash dégagé ou consommé par l'activité pendant l'exercice, après variation du besoin en fonds de roulement et selon la présentation de l'émetteur. Il Peut être très différent du bénéfice comptable et volatile d'une année à l'autre : SIGMA le lit sur plusieurs exercices.",
  "Investissements en immobilisations": "Cash décaissé pour acheter ou construire des actifs durables (usines, équipements, réseaux, logiciels). Dans le tableau des flux, ce montant est présenté en négatif. Il ne couvre pas forcément tous les investissements financiers.",
  "Flux après investissements": "Flux de trésorerie opérationnel moins les investissements en immobilisations corporelles et incorporelles lus dans le même tableau. C'est un repère de cash restant après ces investissements, pas un flux libre complet si d'autres investissements existent.",
  "Trésorerie et équivalents": "Cash et placements très liquides détenus à la clôture. En présentation SYSCOHADA, SIGMA Peut lire la trésorerie-Actif ; les découverts éventuels sont alors en trésorerie-passif et ne doivent pas être ignorés.",
  "Trésorerie nette": "Trésorerie de clôture après prise en compte des découverts ou de la trésorerie-passif lorsque l'état la publie ainsi. Elle Peut être négative : l'entreprise dépend alors de financements bancaires de court terme à la date de clôture.",
  "Dettes financières": "Emprunts et passifs financiers lus au bilan. SIGMA ne publie un total que si les parts courante et non courante du même exercice sont toutes les deux présentes. Pour une banque, les dépôts de la clientèle sont l'activité même : cette ligne ne se compare pas mécaniquement à la dette d'une société industrielle.",
  "Nombre d'actions": "Nombre d'actions en circulation en fin d'exercice ou nombre moyen pondéré, selon le libellé exact de l'état financier. SIGMA affiche la base utilisée, car une augmentation de capital ou une division d'actions Peut changer ce nombre d'un exercice à l'autre.",
  "Suite courante": "Nombre d'exercices consécutifs, jusqu'au dernier exercice présent dans le tableau BRVM, pour lesquels une distribution est documentée. Une suite longue décrit une régularité passée, pas une promesse de maintien.",
  "Évolution annuelle moyenne": "Rythme annuel moyen qui relie le premier et le dernier dividende positif documentés. Il écrase les variations intermédiaires : SIGMA affiche donc aussi le nombre de hausses et de baisses.",
  "Chiffre d'affaires": "Montant des ventes d'une entreprise sur l'exercice. Il mesure l'activité, pas le bénéfice : une société peut vendre davantage tout en gagnant moins si ses coûts augmentent.",
  "Produit net bancaire": "Équivalent bancaire du chiffre d'affaires : marge d'intérêt (crédits moins dépôts rémunérés) plus commissions nettes. C'est le point de départ du compte de résultat d'une banque cotée à la BRVM.",
  "Résultat net": "Bénéfice ou perte après toutes les charges, intérêts et impôts. SIGMA le compare sur plusieurs exercices, car une seule année peut contenir un élément exceptionnel.",
  "Capitaux propres": "Ce qui appartient aux actionnaires après paiement de toutes les dettes : capital, réserves et résultats accumulés. Les comparer au total du bilan donne une première mesure du coussin de sécurité ; ils peuvent être négatifs après de lourdes pertes.",
  "Total du bilan": "Taille totale de ce que l'entreprise possède et finance à la clôture. Pris seul, il ne dit ni si l'entreprise est rentable ni si elle est peu endettée.",
  "Rentabilité des capitaux propres": "Résultat net rapporté aux capitaux propres, souvent appelée ROE. Elle indique le bénéfice dégagé pour 100 FCFA appartenant aux actionnaires, mais devient peu lisible si les capitaux propres sont très faibles ou négatifs.",
  "États financiers": "Documents comptables officiels (bilan, compte de résultat, flux de trésorerie et annexes). Dans SIGMA, certains chiffres sont lus automatiquement dans ces PDF avec page et ligne sources ; leur niveau de confiance reste affiché.",
  "Périmètre comptable": "Ensemble décrit par un état financier : société seule (comptes sociaux), groupe consolidé, ou autre périmètre indiqué par l’émetteur. Deux montants du même exercice ne sont comparables que s’ils décrivent le même périmètre. Pour ajouter un BPA ou un nombre d’actions depuis un second document, SIGMA vérifie donc que les chiffres centraux communs concordent avec le document principal.",
  "Texte natif": "Texte déjà présent dans le fichier PDF et lisible directement par la machine, sans reconnaissance de caractères. SIGMA privilégie toujours cette couche lorsqu'elle permet d'extraire des chiffres contrôlés.",
  "OCR contrôlé": "Reconnaissance optique de caractères utilisée seulement en repli lorsqu'un PDF officiel scanné ne donne aucun chiffre par son texte natif. SIGMA rend les pages en image, lit le Français avec coordonnées et confiance mot à mot, fusionne une passe normale et une passe inversée pour les lignes blanches sur fond foncé, puis applique les mêmes contrôles d'unité, d'ordre des colonnes et de plausibilité qu'au texte natif. Chaque chiffre concerné garde le badge « OCR contrôlé » et sa ligne source ; il faut le relire dans le PDF avant d'en tirer une conclusion importante.",
  "Confiance OCR": "Score de reconnaissance des caractères sur la ligne source, exprimé par le moteur OCR. Ce n'est pas la probabilité que le montant soit exact : un chiffre peut être bien reconnu mais appartenir à une mauvaise colonne, ou inversement. SIGMA l'utilise comme filtre, avec l'unité, l'ordre des colonnes, la cohérence comptable et les recoupements entre documents.",
  "Unité recoupée par le capital légal": "Cas de certains états bancaires qui n'impriment pas « en millions de FCFA » dans le tableau. SIGMA compare alors le « capital souscrit » du bilan au capital légal publié en FCFA entiers dans le pied du même document : si le rapport vaut exactement mille, un million ou un milliard (à petite tolérance près), l'unité est prouvée par le document. Sans ce recoupement, SIGMA refuse de deviner l'échelle.",
  "Exercice": "Année comptable de l'entreprise. Un dividende de l'exercice 2025 peut être payé en 2026 : SIGMA distingue donc l'exercice, la date ex-dividende et la date de paiement.",
  "Pilier Solidité": "Repère séparé de SIGMA fondé sur les capitaux propres, la régularité des bénéfices et leur rentabilité lorsque la série officielle suffit. Ce n'est pas une note de solvabilité d'agence et il n'est pas fusionné aux autres piliers.",
  "Pilier Croissance": "Repère séparé de SIGMA fondé sur l'évolution pluriannuelle de l'activité et, lorsque c'est possible, du résultat net. Une croissance passée ne garantit pas sa continuation.",
  "Confiance données": "Classement SIGMA de la série extraite : A signifie série longue avec plusieurs recoupements entre documents ; B, série exploitable mais moins confirmée ; C, extraction courte ou fragile. Il juge les données, pas la qualité de l'entreprise.",
  "Confirmé · 2 documents": "La même valeur, pour le même exercice, a été retrouvée dans deux documents officiels distincts à la tolérance SIGMA près. C'est plus solide qu'une lecture unique, sans remplacer l'audit du document.",
  "Radar SIGMA": "Premier tri automatique des sociétés cotées par règles quantitatives transparentes : échangeabilité sur 20 séances, PER publié au BOC, rendement de dividende récent et non extrême. Il décide quoi étudier d'abord, jamais quoi acheter.",
  "Score d'étude": "Note de 0 à 100 qui ordonne les sociétés ayant passé les règles du Radar (liquidité 35, valorisation relative 35, rendement 30, en rangs parmi les éligibles). Ce n'est ni une note de qualité, ni une probabilité de gain.",
  "Valorisation": "Comparaison du prix avec une grandeur publiée, ici principalement le PER du BOC et la médiane du secteur. Elle ne tient pas lieu d'évaluation complète de l'entreprise.",
  "Suivi automatique Radar": "Quand il est actif, SIGMA ajoute automatiquement la sélection courante du Radar à votre périmètre de lecture, d'alertes et de news. Cela ne crée aucune position et ne remplace pas vos épingles personnelles.",
  "Liste de suivi": "Sociétés que vous avez épinglées vous-même avec l'étoile. Elle est distincte du suivi automatique Radar et des positions réelles ou simulées.",
  "Ordre à cours limité": "Ordre transmis à la SGI avec un prix maximum à l'achat (ou minimum à la vente). Il protège contre une exécution à un prix très différent, mais peut ne pas être exécuté si le prix n'est pas disponible.",
  "PRU": "Prix de revient unitaire : coût moyen d'achat d'une action, frais saisis inclus dans SIGMA. Il dépend donc de l'exactitude des transactions enregistrées.",
  "Plus ou moins-value latente": "Différence entre la valeur actuelle estimée au dernier cours publié et le coût d'achat. Elle n'est ni encaissée ni définitive tant que la position n'est pas vendue.",
  "Résultat réalisé": "Gain ou perte calculé lors d'une vente enregistrée, après les frais saisis. Contrairement au latent, il correspond à une opération de sortie déjà comptée dans le portefeuille choisi.",
  "Portefeuille réel": "Registre local des opérations que vous déclarez avoir réellement exécutées chez votre SGI. SIGMA ne peut ni vérifier votre compte-titres ni corriger seul un avis d'opéré : le prix et les frais réels doivent correspondre à ce document.",
  "Simulation": "Portefeuille virtuel, toujours identifié en violet dans SIGMA. Il sert à essayer une quantité et suivre son évolution aux cours publiés, sans argent engagé, sans ordre transmis et parfois sans frais si votre grille SGI n'est pas connue.",
  "Poche d'apprentissage": "Part séparée de votre budget réel que vous réservez à l'apprentissage. Ce n'est pas le portefeuille virtuel violet : si vous l'utilisez chez votre SGI, l'argent engagé est réel.",
  "Thèse": "Explication datée, fondée sur des faits sourcés, de ce que vous attendez d'une société et des risques. SIGMA Peut Préremplir un brouillon ; vous devez le relire et le corriger avant de l'enregistrer comme votre mémoire de décision.",
  "Invalidation": "Fait précis qui, s'il se produit, obligerait à réviser ou abandonner une thèse : perte publiée, dividende supprimé, endettement dégradé, événement officiel contraire, etc.",
  "SGI": "Société de Gestion et d'Intermédiation agréée : l'intermédiaire qui ouvre votre compte-titres et transmet vos ordres à la BRVM. La BRVM publie l'annuaire officiel des SGI mais pas leurs grilles tarifaires. En revanche, chaque grille doit être homologuée par l'AMF-UMOA : SIGMA relit ces décisions officielles et affiche les plafonds, sans jamais les confondre avec le tarif que votre SGI vous facturera réellement.",
  "Courtage": "Part proportionnelle des frais d'ordre, exprimée en pourcentage du montant. SIGMA ne l'estime que si vous avez saisi la grille écrite de votre SGI.",
  "Plafond homologué": "Tarif maximal qu'une SGI est autorisée à facturer, approuvé par décision officielle de l'AMF-UMOA (anciennement CREPMF). C'est un plafond négociable, pas un prix imposé : votre SGI peut facturer moins, jamais plus sans nouvelle homologation. La grille écrite qu'elle vous remet reste le document qui fait foi.",
  "AMF-UMOA": "Autorité des Marchés Financiers de l'UMOA, le régulateur du marché financier régional (anciennement CREPMF). Elle agrée les SGI et homologue leurs tarifs : toute modification de grille exige une nouvelle décision d'homologation.",
  "Droits de garde": "Frais de conservation de vos titres, prélevés périodiquement (souvent par trimestre) en pourcentage de la valeur du portefeuille. Contrairement au courtage, ils courent même sans aucun ordre : sur dix ans, leur niveau compte autant que le courtage.",
  "CPM": "Comité de Politique Monétaire de la BCEAO. Il décide notamment du taux directeur dans l'UEMOA. SIGMA reprend uniquement les chiffres cités dans le communiqué officiel relu.",
  "Taux directeur": "Principal taux auquel la BCEAO prête aux banques. Il influence le coût de l'argent dans l'Union ; SIGMA l'utilise comme contexte daté, jamais comme signal automatique sur une action.",
  "Prêt marginal": "Guichet auquel une banque peut emprunter à la BCEAO dans les conditions prévues, à un taux supérieur au taux directeur. Il complète la lecture du coût de liquidité bancaire.",
  "Réserves obligatoires": "Part des ressources que les banques assujetties doivent conserver selon le coefficient fixé par la BCEAO. Une modification peut influencer la liquidité bancaire ; SIGMA ne projette pas ses effets société par société.",
  "UMOA-Titres": "Agence qui organise notamment les émissions de titres publics des États de l'Union. Dans SIGMA, ses tableaux servent au calendrier et au contexte de liquidité ; les montants sont annoncés ou mis en adjudication, pas forcément levés.",
  "Montant annoncé": "Montant qu'un émetteur prévoit de mettre en adjudication ou annonce pour une opération. Il ne faut pas le confondre avec le montant finalement levé, que SIGMA ne collecte pas encore dans les résultats d'adjudications.",
  "Échéance": "Date future publiée par une source officielle : ex-dividende, paiement, opération de titres publics ou événement institutionnel. SIGMA n'invente pas de date prévisionnelle quand la source n'en publie pas.",
  "Maturité M0–M5": "Échelle SIGMA pour un fait de contexte : rumeur, annonce officielle, financement engagé, mise en œuvre, effet économique visible, puis effet dans les résultats publiés. On surveille tôt, on ne conclut qu'avec des preuves."
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
let automaticStudyCache = { key: "", value: [] };
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
  analysisTab: "decision",
  portfolioKind: "reel",
  reportSearch: "",
  reportsShowAllDividends: false,
  journalPrefill: null,
  transactionPrefill: null,
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
    if (!raw) return cloneSur(DEFAULT_PERSONAL);
    const parsed = JSON.parse(raw);
    return {
      ...cloneSur(DEFAULT_PERSONAL),
      ...parsed,
      portfolios: {
        reel: { transactions: parsed?.portfolios?.reel?.transactions || [] },
        virtuel: { transactions: parsed?.portfolios?.virtuel?.transactions || [] }
      },
      settings: { ...DEFAULT_PERSONAL.settings, ...(parsed.settings || {}) }
    };
  } catch (_) {
    return cloneSur(DEFAULT_PERSONAL);
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
function fmtFigureValue(figure) {
  if (!figure) return "—";
  const value = isNum(figure.value) ? figure.value : figure.value_fcfa;
  if (!isNum(value)) return "—";
  if (figure.value_kind === "fcfa_par_action") return `${fmtNum(value, Number.isInteger(value) ? 0 : 2)} FCFA/action`;
  if (figure.value_kind === "actions") return `${fmtNum(value, 0)} actions`;
  return fmtCompactFCFA(figure.value_fcfa ?? value);
}
function fmtMultiple(value) {
  return isNum(value) ? `${fmtNum(value, 2)}×` : "—";
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
  return `<button type="button" class="term-button" data-term="${escapeHtml(term)}" aria-label="Définition de ${escapeHtml(term)}" title="Voir la définition"><span>${escapeHtml(label)}</span><span class="term-mark" aria-hidden="true">?</span></button>`;
}
function openTerm(term) {
  const dialog = $("#termDialog");
  if (!dialog) return;
  $("#termEyebrow").textContent = "Lecture guidée · définition";
  $("#termTitle").textContent = term;
  $("#termBody").innerHTML = `<p>${escapeHtml(GLOSSARY[term] || "Définition à compléter dans le glossaire SIGMA.")}</p>
    <div class="form-actions"><button type="button" class="button button-secondary button-small" data-open-glossary>Toutes les définitions</button></div>`;
  if (!dialog.open) dialog.showModal();
}
function openGlossary() {
  const dialog = $("#termDialog");
  if (!dialog) return;
  const entries = Object.entries(GLOSSARY).sort(([a], [b]) => a.localeCompare(b, "fr"));
  $("#termEyebrow").textContent = "Lecture guidée · glossaire SIGMA";
  $("#termTitle").textContent = "Comprendre les termes sans quitter l’écran";
  $("#termBody").innerHTML = `<p class="muted">Les mots soulignés en pointillé avec un <span class="term-mark" aria-hidden="true">?</span> ouvrent directement leur définition. Vous pouvez aussi chercher ici.</p>
    <label>Rechercher un terme<input id="glossarySearch" class="glossary-search" type="search" placeholder="Ex. liquidité, PER, dividende, SGI…"></label>
    <div class="glossary-list">${entries.map(([term, definition]) => `<section class="glossary-entry" data-search="${escapeHtml(normalize(`${term} ${definition}`))}"><h3>${escapeHtml(term)}</h3><p>${escapeHtml(definition)}</p></section>`).join("")}</div>`;
  const search = $("#glossarySearch");
  search?.addEventListener("input", () => {
    const q = normalize(search.value);
    $$(".glossary-entry", dialog).forEach(entry => { entry.hidden = Boolean(q && !entry.dataset.search.includes(q)); });
  });
  if (!dialog.open) dialog.showModal();
  setTimeout(() => search?.focus(), 30);
}
function modePill(kind) {
  return kind === "virtuel"
    ? '<span class="pill simulation">◆ SIMULATION · aucun argent réel</span>'
    : '<span class="pill dark">PORTEFEUILLE RÉEL · avis d’opéré</span>';
}
function modeBanner(kind) {
  if (kind === "virtuel") {
    return `<div class="mode-banner simulation"><span aria-hidden="true" style="font-size:22px">◆</span><div><strong>Vous êtes en simulation.</strong><p>Tout ce qui est violet sert à apprendre et tester : aucun ordre n’est transmis, aucun argent réel n’est engagé, et les frais peuvent être absents si votre grille SGI n’est pas saisie.</p></div></div>`;
  }
  return `<div class="mode-banner real"><span aria-hidden="true" style="font-size:22px">●</span><div><strong>Vous êtes dans le ${termButton("Portefeuille réel", "portefeuille réel déclaré")}.</strong><p>Il ne contient que des opérations déjà exécutées chez votre SGI puis enregistrées ici. En cas d’écart, l’avis d’opéré de la SGI fait foi.</p></div></div>`;
}
function plainSummary(title, bullets, extraClass = "") {
  if (!bullets?.length) return "";
  return `<article class="card plain-summary ${extraClass}"><p class="eyebrow">En clair</p><h2>${escapeHtml(title)}</h2><ul>${bullets.map(item => `<li>${item}</li>`).join("")}</ul></article>`;
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

function automaticJournalDraft(company, type = "Thèse") {
  if (!company) return null;
  const stats = company.history_stats || {};
  const boc = company.latest_boc || {};
  const priceInfo = latestPrice(company);
  const pillars = computeFundamentalPillars().get(company.ticker) || {};
  const ocrSummary = fundamentalOcrSummary(company);
  const hist = company.dividend_history || {};
  const sustainabilityRows = company.dividend_sustainability?.rows || [];
  const latestSustainability = sustainabilityRows[0] || null;
  const recentDocs = (company.documents || []).slice(0, 3);
  const recentNews = newsForTicker(company.ticker, 3);
  const horizon = isNum(stats.performance_20_sessions_pct)
    && stats.performance_20_sessions_pct <= Number(personal.settings.decline20) ? 20 : 5;
  const causes = type === "Checklist baisse" ? declineCauses(company, horizon) : [];
  const lines = [
    `BROUILLON SIGMA PRÉPARÉ LE ${fmtDate(new Date().toISOString().slice(0, 10))} — À RELIRE ET CORRIGER AVANT ENREGISTREMENT.`,
    "",
    "FAITS DATÉS DÉJÀ COLLECTÉS",
    `• Société : ${company.name} (${company.ticker}) · ${company.sector}.`,
    isNum(priceInfo.value)
      ? `• Dernier cours publié : ${fmtFCFA(priceInfo.value)} (${priceInfo.label}).`
      : "• Dernier cours publié : non disponible dans la collecte.",
    isNum(stats.traded_sessions_last_20)
      ? `• Échangeabilité récente : ${stats.traded_sessions_last_20}/20 séances échangées ; valeur médiane ${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)} par séance.`
      : "• Échangeabilité récente : statistiques BOC insuffisantes.",
    isNum(stats.performance_20_sessions_pct)
      ? `• Parcours prix seuls : ${fmtPct(stats.performance_20_sessions_pct)} sur 20 séances (hors dividendes réinvestis et ajustements).`
      : "• Parcours sur 20 séances : non calculable.",
    isNum(boc.per)
      ? `• BOC du ${fmtDate(company.latest_boc_date)} : PER ${fmtRatio(boc.per)} ; rendement net ${fmtPct(boc.net_dividend_yield_pct, 2, false)}.`
      : `• BOC du ${fmtDate(company.latest_boc_date)} : PER non publié ; rendement net ${fmtPct(boc.net_dividend_yield_pct, 2, false)}.`,
    hist.paid_fiscal_years_count
      ? `• Historique BRVM des dividendes : distributions documentées sur ${hist.paid_last_5_fiscal_years ?? 0}/5 derniers exercices du tableau ; dernier exercice rattaché ${hist.latest_paid_fiscal_year}.`
      : "• Historique BRVM des dividendes : aucune distribution rattachée sans ambiguïté dans la collecte (ne pas assimiler automatiquement à zéro).",
    pillars.solidite || pillars.croissance
      ? `• Piliers séparés SIGMA : Solidité ${pillars.solidite ? `${pillars.solidite.score}/100` : "non calculable"} ; Croissance ${pillars.croissance ? `${pillars.croissance.score}/100` : "non calculable"}. Aucun score global.`
      : "• Piliers Solidité/Croissance : non calculables avec la série extraite actuelle ; les états financiers officiels restent à relire.",
    ocrSummary.figures
      ? `• Provenance des fondamentaux : ${ocrSummary.figures} chiffre(s) proviennent d’un OCR contrôlé de PDF officiels scannés (${ocrSummary.used} document(s) ayant produit des chiffres). Page, ligne source et confiance de reconnaissance sont dans la fiche ; relire le PDF officiel avant de fonder une conclusion importante sur ces montants.`
      : ocrSummary.attempted
        ? `• OCR contrôlé : tenté en repli sur ${ocrSummary.attempted} document(s) scanné(s), sans chiffre retenu après contrôles ; aucune valeur OCR n’alimente donc les piliers ci-dessus.`
        : "• Provenance des fondamentaux : texte natif des PDF officiels pour les chiffres retenus ; aucun OCR utilisé dans cette collecte pour cette société.",
    latestSustainability
      ? `• Repères dividende/flux ${latestSustainability.exercice} : dividende net/BPA ${isNum(latestSustainability.dividende_net_sur_bpa_pct) ? fmtPct(latestSustainability.dividende_net_sur_bpa_pct, 1, false) : "non calculable"} ; couverture par le flux opérationnel ${fmtMultiple(latestSustainability.couverture_flux_operationnel_x)} ; après investissements ${fmtMultiple(latestSustainability.couverture_apres_investissements_x)}. Repères séparés, pas un score Dividende durable.`
      : "• Repères dividende/flux : non calculables faute de BPA/nombre d'actions et de flux du même exercice suffisamment lisibles ; aucun score Dividende durable."
  ];
  if (type === "Checklist baisse") {
    lines.push("", "CHECKLIST BAISSE — PISTES AUTOMATIQUES À VÉRIFIER", `• Pistes SIGMA sur ${horizon} séances : ${causes.join(" · ")}.`);
    if (personal.profile?.riskReaction) lines.push(`• Ma règle déclarée à froid : ${RISK_REACTION_LABELS[personal.profile.riskReaction] || ""}.`);
    lines.push("• À compléter après lecture des sources : fait nouveau oui/non ; thèse initiale toujours valide oui/non ; horizon révisé ; décision de surveillance.");
  } else {
    lines.push("", "MA LECTURE À COMPLÉTER", "• Ce que j’attends de cette société et sur quel horizon : …", "• Pourquoi ces faits me semblent importants : …", "• Risques principaux que j’accepte de surveiller : …");
  }
  if (recentDocs.length) {
    lines.push("", "DOCUMENTS OFFICIELS RÉCENTS À RELIRE", ...recentDocs.map(doc => `• ${doc.label || DOC_TYPE_LABELS[doc.doc_type] || "Document officiel"}${doc.published_date ? ` (${fmtDate(doc.published_date)})` : ""} — ${doc.url || company.report_url || ""}`));
  }
  if (recentNews.length) {
    lines.push("", "PUBLICATIONS RÉCENTES RATTACHÉES", ...recentNews.map(item => `• ${fmtDate(item.published_date)} — ${item.title} (${item.source_label}) ${item.url || ""}`));
  }
  lines.push("", `Sources de marché : collecte SIGMA du ${fmtDateTime(DATA.generated_at)} ; dernier BOC ${fmtDate(latestBocDate())}. Ce brouillon n’est ni une recommandation ni une position réelle ou simulée.`);
  const invalidation = [
    "À relire et préciser :",
    "• Publication officielle contredisant les faits ci-dessus ou dégradation documentée des résultats/pluriannuel.",
    hist.paid_fiscal_years_count ? "• Suppression ou baisse du dividende lors d’un prochain avis officiel, à comparer à l’historique par exercice." : "• Absence persistante de distribution documentée ou information officielle confirmant une politique incompatible avec ma lecture.",
    "• PER/rendement BOC devenus non interprétables (bénéfice négatif, dividende exceptionnel ou ancien).",
    "• Liquidité durablement dégradée ou événement officiel majeur non expliqué par le marché/secteur."
  ].join("\n");
  return {
    ticker: company.ticker,
    type,
    title: type === "Checklist baisse"
      ? `Checklist baisse ${company.ticker} — brouillon automatique du ${fmtDate(new Date().toISOString().slice(0, 10))}`
      : `Thèse ${company.ticker} — brouillon automatique du ${fmtDate(new Date().toISOString().slice(0, 10))}`,
    text: lines.join("\n"),
    invalidation
  };
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
  etats_financiers_intermediaires: "États financiers intermédiaires (période partielle)",
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

function showToast(message, tone = "") {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("simulation", tone === "simulation");
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 3600);
}
function showView(view, ticker = null) {
  // Compatibilité v1.3 → v1.4 : les anciennes vues « Analyses » et « Rapports »
  // vivent désormais dans « Décision » ; les liens et favoris existants suivent.
  if (view === "analyses") view = "decision";
  if (view === "rapports") { ui.analysisTab = "documents"; view = "decision"; }
  if (view === "settings") view = "parametres";
  ui.view = view;
  if (ticker) ui.selectedTicker = ticker;
  $$(".view").forEach(section => section.classList.toggle("is-active", section.id === `view-${view}`));
  // Pages secondaires sans bouton propre : marché et alertes pendent de
  // l’accueil, la fiche société des entreprises.
  const navView = view === "fiche" ? "entreprises" : ["marche", "alertes"].includes(view) ? "accueil" : view;
  $$(".nav-item").forEach(button => button.classList.toggle("is-active", button.dataset.view === navView));
  $$("[data-view-link='parametres']").forEach(button => button.classList.toggle("is-active", view === "parametres"));
  const target = view === "fiche" && ui.selectedTicker ? `fiche-${ui.selectedTicker}` : view;
  history.replaceState(null, "", `#${target}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (view === "fiche") renderCompanyDetail();
  if (view === "decision") renderDecision();
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
function heldTickersByKind(kind) {
  return computePortfolio(kind).holdings.map(h => h.ticker);
}
function automaticStudyTickers() {
  if (personal.settings.autoFollowRadar === false || !DATA) return [];
  const key = `${DATA.generated_at}|${personal.settings.decline5}|${personal.settings.decline20}`;
  if (automaticStudyCache.key === key) return automaticStudyCache.value;
  try {
    const value = computeRadar().selection.map(entry => entry.company.ticker);
    automaticStudyCache = { key, value };
    return value;
  } catch (_) {
    return [];
  }
}
function followedTickers() {
  return [...new Set([...personal.watchlist, ...heldTickers(), ...automaticStudyTickers()])];
}
function trackingSources(ticker) {
  const sources = [];
  if (heldTickersByKind("reel").includes(ticker)) sources.push({ label: "Position réelle", cls: "dark" });
  if (heldTickersByKind("virtuel").includes(ticker)) sources.push({ label: "Position simulée", cls: "simulation" });
  if (isWatched(ticker)) sources.push({ label: "Suivi personnel", cls: "personal" });
  if (automaticStudyTickers().includes(ticker)) sources.push({ label: "Suivi automatique Radar", cls: "official" });
  return sources;
}
function trackingBadges(ticker) {
  const sources = trackingSources(ticker);
  return sources.length ? `<span class="mode-legend">${sources.map(s => `<span class="pill ${s.cls}">${s.label}</span>`).join("")}</span>` : "";
}
function trackingSourceLabel(ticker) {
  const sources = trackingSources(ticker).map(s => s.label.toLowerCase());
  return sources.length ? sources.join(" · ") : "hors périmètre suivi";
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
      <div class="key-fact"><span class="metric-label">${termButton("Taux directeur", "Taux directeur BCEAO")}</span><div class="metric-value">${fmtPct(cpm.policy_rate_pct, 2, false)}</div><div class="subtext">CPM du ${fmtDate(cpm.meeting_date || cpm.published_date)}${cpm.rates_effective_since ? ` · en vigueur depuis le ${fmtDate(cpm.rates_effective_since)}` : ""}</div></div>
      <div class="key-fact"><span class="metric-label">${termButton("Prêt marginal")}</span><div class="metric-value">${fmtPct(cpm.marginal_lending_rate_pct, 2, false)}</div><div class="subtext">${termButton("Réserves obligatoires")} : ${fmtPct(cpm.reserve_requirement_pct, 2, false)}</div></div>
      <div class="key-fact"><span class="metric-label">Inflation UEMOA (CPM)</span><div class="metric-value">${fmtPct(cpm.inflation_latest_pct, 1, false)}</div><div class="subtext">${escapeHtml(cpm.inflation_latest_period || "Période citée au communiqué")}${isNum(cpm.inflation_forecast_pct) ? ` · prévision ${cpm.inflation_forecast_year} : ${fmtPct(cpm.inflation_forecast_pct, 1, false)}` : ""}</div></div>
      <div class="key-fact"><span class="metric-label">Croissance UEMOA (CPM)</span><div class="metric-value">${fmtPct(cpm.growth_latest_pct, 1, false)}</div><div class="subtext">${escapeHtml(cpm.growth_latest_period || "Période citée au communiqué")}${isNum(cpm.growth_forecast_pct) ? ` · attendue ${cpm.growth_forecast_year} : ${fmtPct(cpm.growth_forecast_pct, 1, false)}` : ""}</div></div>
    </div>` : `<div class="Empty-state" style="margin-top:14px">Dernier communiqué CPM BCEAO : <strong>non extrait proprement</strong>. SIGMA ne déduit aucun taux d’un titre d’actualité ; la source reste dans Actualités.</div>`;
  const umoaFacts = umoa.status === "collecte" ? `
    <div class="key-facts" style="margin-top:14px">
      <div class="key-fact"><span class="metric-label">Émissions ${termButton("UMOA-Titres")} à venir</span><div class="metric-value">${fmtNum(umoa.upcoming_operations || 0)}</div><div class="subtext">Prochaine : ${umoa.next_operation ? `${escapeHtml(umoa.next_operation.issuer_country)} · ${fmtDate(umoa.next_operation.operation_date)} · ${fmtCompactFCFA(umoa.next_operation.amount_fcfa)}` : "—"}</div></div>
      <div class="key-fact"><span class="metric-label">${termButton("Montant annoncé", "Montants annoncés")} · 30 jours</span><div class="metric-value">${fmtCompactFCFA(windows.next_30d?.amount_fcfa)}</div><div class="subtext">${fmtNum(windows.next_30d?.operations || 0)} opération(s) · 90 jours : ${fmtCompactFCFA(windows.next_90d?.amount_fcfa)}</div></div>
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
        <div class="form-actions"><button type="button" class="button button-secondary button-small" data-decision-link="documents">Calendrier complet et documents</button></div>
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
  const relevant = followedTickers();
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
        meta: `Périmètre : ${trackingSourceLabel(ticker)} · Dernier BOC utilisé : ${fmtDate(latestBocDate())}. Ouvrir la checklist avant toute conclusion.`,
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
        meta: `Périmètre : ${trackingSourceLabel(ticker)} · ${item.source_label} · ${fmtDate(item.published_date)} · ${item.category || ""}. Document source lié.`,
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
      short: calendarEventAmount(event) || "Montant non publié dans le tableau",
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
    body: "SIGMA publie Solidité et Croissance uniquement lorsque la série d’états financiers officiels est suffisante et recoupée. Les flux, trésorerie, dettes financières, BPA et nombres d'actions lisibles sont désormais affichés en fiche ; les repères dividende/flux ne sont calculés que lorsque les intrants du même exercice existent. Il n'y a toujours ni score Dividende durable ni score global.",
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
      <div class="subtext">${escapeHtml(company.name)} · ${escapeHtml(company.sector)}</div>${trackingBadges(company.ticker)}${extra}</div>
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
  const relevantTickers = followedTickers();
  const relevantCompanies = relevantTickers.map(t => BY_TICKER.get(t)).filter(Boolean);
  const referenceDate = DATA.generated_at.slice(0, 10);
  const upcoming = [...DATA.dividends].filter(d => d.ex_date && d.ex_date >= referenceDate).sort((a, b) => a.ex_date.localeCompare(b.ex_date)).slice(0, 4);
  const quoted = COMPANIES.filter(c => isNum(c.latest_quote?.variation_pct));
  const top = [...quoted].sort((a, b) => b.latest_quote.variation_pct - a.latest_quote.variation_pct).slice(0, 4);
  const flop = [...quoted].sort((a, b) => a.latest_quote.variation_pct - b.latest_quote.variation_pct).slice(0, 4);
  const radar = computeRadar();
  const latestNews = newsItems().filter(item => item.relevance !== "general").slice(0, 4);

  // 1 · Ce mois-ci : la seule question qui demande (Peut-être) un geste.
  const monthly = computeMonthlyCandidates();
  const firstCandidate = monthly.candidates[0] || null;
  const profileDone = !!personal.profile;
  const monthlyCard = `<article class="card">
      <div class="event-row"><div><p class="eyebrow">Votre mois en un coup d’œil</p><h2>Ce mois-ci</h2></div><span class="pill dark">Dernier BOC lu : ${fmtDate(latestBocDate())}</span></div>
      ${firstCandidate ? `<p>Avec un versement de <strong>${fmtFCFA(Number(ui.decision.budget) || 0)}</strong>${monthly.pocketPct ? ` (dont ${fmtFCFA(monthly.pocketAmount)} réservés à votre poche d’apprentissage, reste <strong>${fmtFCFA(monthly.workingBudget)}</strong> pour l’objectif principal)` : ""}, la première société à <strong>examiner</strong> selon vos règles est <button type="button" class="text-button ticker" data-open-company="${firstCandidate.company.ticker}">${firstCandidate.company.ticker}</button> — ${escapeHtml(firstCandidate.company.name)}.</p>
      <div class="key-facts">
        <div class="key-fact"><span class="metric-label">Dernier cours publié</span><div class="metric-value">${fmtFCFA(firstCandidate.price)}</div><div class="subtext">Fin de journée, pas du temps réel</div></div>
        <div class="key-fact"><span class="metric-label">Titres possibles</span><div class="metric-value">${fmtNum(firstCandidate.affordable.shares)}</div><div class="subtext">Investi ${fmtFCFA(firstCandidate.affordable.invested)} · reste ${fmtFCFA(Math.round(firstCandidate.affordable.remainder))}</div></div>
        <div class="key-fact"><span class="metric-label">Frais SGI</span><div class="metric-value">${firstCandidate.affordable.feesKnown ? fmtFCFA(Math.round(firstCandidate.affordable.fees)) : "Non estimés"}</div><div class="subtext">${firstCandidate.affordable.feesKnown ? "Avec la grille que vous avez saisie" : "Renseignez votre grille dans Paramètres"}</div></div>
        <div class="key-fact"><span class="metric-label">Sociétés à examiner</span><div class="metric-value">${monthly.candidates.length}</div><div class="subtext">Passent vos filtres ce mois-ci</div></div>
      </div>` : `<p><strong>Aucune société ne passe vos filtres ce mois-ci</strong> avec un budget de ${fmtFCFA(monthly.workingBudget)}. C’est une réponse valable : garder le versement en attente fait partie de la méthode. Vous pouvez aussi élargir un critère dans l’onglet Décision plutôt que forcer un achat.</p>`}
      ${profileDone ? "" : `<div class="notice" style="margin-top:12px"><p><strong>Préréglage non fait :</strong> ce bloc utilise un montant neutre. Deux minutes pour indiquer votre pays, votre SGI et votre versement réel — ensuite tout est automatique.</p></div>`}
      <div class="form-actions" style="margin-top:12px"><button type="button" class="button" data-decision-link="decision">Préparer la décision du mois</button>${firstCandidate ? `<button type="button" class="button button-secondary" data-open-company="${firstCandidate.company.ticker}">Ouvrir la fiche ${firstCandidate.company.ticker}</button>` : ""}${profileDone ? "" : `<button type="button" class="button button-secondary" data-open-onboarding>Faire le préréglage</button>`}</div>
      <p class="source-line">Ordre de lecture préparé par des règles explicites (onglet Décision), jamais un ordre d’achat : lisez la fiche et le brouillon de thèse avant tout geste chez votre SGI.</p>
    </article>`;

  // 2 · Sociétés à étudier : mis en avant immédiatement, une ligne par société.
  const radarCard = `<article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Règles explicites · Radar</p><h2>Sociétés à étudier en premier</h2></div><button type="button" class="button button-secondary button-small" data-decision-link="radar">Règles &amp; classement</button></div>
      ${radar.selection.length ? `<ul class="study-list">${radar.selection.slice(0, 5).map((entry, index) => `<li class="study-row">
        <span class="study-rank">${index + 1}</span>
        <span class="study-id"><button type="button" class="text-button ticker" data-open-company="${entry.company.ticker}">${entry.company.ticker}</button><span class="study-name">${escapeHtml(entry.company.name)}</span></span>
        <span class="study-metrics"><span>PER ${fmtRatio(entry.company.latest_boc?.per)}</span><span>Rdt ${fmtPct(entry.company.latest_boc?.net_dividend_yield_pct, 2, false)}</span><span>Liq. ${fmtCompactFCFA(entry.company.history_stats?.median_traded_value_last_20_fcfa)}</span></span>
        <button type="button" class="button button-secondary button-small" data-open-company="${entry.company.ticker}">Fiche</button>
      </li>`).join("")}</ul>` : '<div class="Empty-state">Aucune société ne passe les règles du Radar avec les données actuelles.</div>'}
      <p class="source-line">Tri automatique par règles écrites (liquidité, PER publié au BOC, dividende récent). <strong>Ordre d'étude, jamais ordre d'achat</strong> : la fiche dit ce que SIGMA sait, ce qu'il ignore et ce qui invaliderait la thèse.</p>
    </article>`;

  // 3 · Alertes non lues (la page complète reste accessible).
  const alerts = generateAlerts();
  const unread = alerts.filter(a => !personal.alertsRead.includes(a.id));
  const shownAlerts = (unread.length ? unread : alerts).slice(0, 3);
  const alertsCard = `<article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Faits datés sur votre périmètre</p><h2>Alertes ${unread.length ? `· ${unread.length} non lue(s)` : "· rien de neuf"}</h2></div><div style="display:flex;gap:6px;flex-wrap:wrap">${unread.length ? `<button type="button" class="button button-small" data-mark-alerts-read>Tout marquer comme lu</button>` : ""}<button type="button" class="button button-secondary button-small" data-view-link="alertes">Toutes les alertes</button></div></div>
      ${shownAlerts.length ? `<ul class="list-clean">${shownAlerts.map(alert => `<li class="event-row"><div style="display:flex;gap:10px;align-items:flex-start"><span class="alert-icon ${alert.tone}">${alert.icon}</span><div><div class="strong">${escapeHtml(alert.title)}</div><div class="subtext">${escapeHtml(alert.short || alert.body)}</div></div></div><span class="pill">${fmtDate(alert.date)}</span></li>`).join("")}</ul>` : '<div class="Empty-state">Aucune alerte factuelle dans le périmètre surveillé automatiquement.</div>'}
    </article>`;

  // 3 · Le marché en une minute (détail complet : page Marché).
  const marketCard = `<article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Séance et structure</p><h2>Le marché en une minute</h2></div><button type="button" class="button button-secondary button-small" data-view-link="marche">Détail du marché &amp; cote complète</button></div>
      <div class="key-facts">
        <div class="key-fact"><span class="metric-label">${termButton("BRVM Composite")}</span><div class="metric-value">${fmtNum(composite.level, 2)}</div><div class="subtext">${variationPill(composite.variation_pct)} instantané officiel</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("Largeur du marché", "Hausses · baisses · inchangées")}</span><div class="metric-value">${structure.advancers} · ${structure.decliners} · ${structure.unchanged}</div><div class="subtext">Variation médiane : ${fmtPct(structure.median_variation_pct)} — la moitié des valeurs fait mieux, l’autre moins bien</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("Concentration des échanges", "Top 5 des échanges en valeur")}</span><div class="metric-value">${fmtPct(bocStructure.top5_traded_value_share_pct, 1)}</div><div class="subtext">BOC du ${fmtDate(bocStructure.date)} · ${structure.without_volume} valeur(s) sans volume publié</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("Valeur échangée", "Valeur des transactions")}</span><div class="metric-value">${fmtCompactFCFA(activity["Valeur des transactions"]?.value)}</div><div class="subtext">Activité publiée par la BRVM</div></div>
      </div>
      <div style="margin-top:14px">${lineChart(compositePoints)}</div>
      <p class="source-line">Niveaux d’indice imprimés dans les ${termButton("BOC", "Bulletins Officiels de la Cote")} (${compositePoints.length} séances lues). Concentration des capitalisations : <strong>non calculée</strong> tant que le nombre d’actions vérifié n’est pas intégré pour toutes les sociétés.</p>
    </article>`;

  host.innerHTML = `
    ${monthlyCard}
    ${radarCard}
    ${alertsCard}
    ${marketCard}

    <div class="grid-2 section-space">
      <article class="card">
        <div class="event-row"><div><p class="eyebrow">Collecte automatique</p><h2>Dernières publications</h2></div><button type="button" class="button button-secondary button-small" data-view-link="actualites">Tout le fil</button></div>
        ${latestNews.length ? latestNews.map(newsItemHtml).join("") : '<div class="Empty-state">Aucune publication collectée à ce stade.</div>'}
      </article>
    </div>

    <div class="grid-2 section-space">
      <article class="card">
        <p class="eyebrow">À connaître</p><h2>Prochains dividendes officiels</h2>
        ${upcoming.length ? `<ul class="list-clean">${upcoming.map(div => `<li class="event-row"><div><div class="strong">${escapeHtml(div.issuer)}</div><div class="subtext">Ex-dividende ${fmtDate(div.ex_date)} · paiement ${fmtDate(div.payment_date)}</div></div><div style="text-align:right"><div class="strong">${fmtFCFA(div.net_amount_fcfa)}</div>${div.notice_url ? `<a href="${div.notice_url}" target="_blank" rel="noopener">Avis</a>` : ""}</div></li>`).join("")}</ul>` : '<div class="Empty-state">Aucun dividende futur dans les pages officielles collectées à la date de génération.</div>'}
        <p class="source-line">Montants nets et dates tels que publiés dans le tableau officiel des paiements de dividendes.</p>
      </article>
      <article class="card">
        <div class="event-row"><div><p class="eyebrow">Votre périmètre de lecture</p><h2>Valeurs à surveiller — sources distinguées</h2></div><button type="button" class="button button-secondary button-small" data-view-link="entreprises">Toutes les entreprises</button></div>
        <p class="source-line">SIGMA réunit ici vos positions et épingles personnelles${personal.settings.autoFollowRadar === false ? "" : ", plus la sélection automatique du Radar"}. Chaque badge indique pourquoi la valeur apparaît ; une position simulée reste violette et séparée du réel.</p>
        ${relevantCompanies.length ? `<ul class="list-clean">${relevantCompanies.slice(0, 7).map(c => companyMiniRow(c)).join("")}</ul>` : `<div class="Empty-state"><span class="sigma-empty">Σ</span>Aucune valeur dans le périmètre suivi. Activez le ${termButton("Suivi automatique Radar")} dans Paramètres ou épinglez une société.<br><button type="button" class="button button-small" data-decision-link="radar" style="margin-top:12px">Voir la sélection automatique</button></div>`}
      </article>
    </div>

    ${macroCalendarCard()}

    <details class="card section-space">
      <summary class="strong" style="cursor:pointer"><span class="eyebrow" style="display:block">Instantané BRVM · bruit de séance</span>Plus fortes variations — à lire sans réagir</summary>
      <div class="grid-2-equal" style="margin-top:14px">
        <div><h3 style="margin-top:0">Plus fortes hausses</h3><ul class="list-clean">${top.map(c => companyMiniRow(c, `<div class="subtext">Volume : ${fmtNum(c.latest_quote.volume)} titres</div>`)).join("")}</ul></div>
        <div><h3 style="margin-top:0">Plus fortes baisses</h3><ul class="list-clean">${flop.map(c => companyMiniRow(c, `<div class="subtext">Volume : ${fmtNum(c.latest_quote.volume)} titres</div>`)).join("")}</ul></div>
      </div>
      <p class="source-line">Une variation de séance, surtout sur faible volume, ne dit rien de la qualité d’une société : c’est la checklist baisse de l’onglet Décision qui sert à examiner, documents à l’appui.</p>
    </details>

    <div class="notice blue section-space"><p><strong>État réel de couverture.</strong> ${escapeHtml(DATA.coverage.note)} Les fiches séparent donc faits de marché officiels, chiffres extraits avec leur niveau de vérification et éléments encore non calculables.</p></div>`;
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
        <div class="key-fact"><span class="metric-label">${termButton("Largeur du marché", "Largeur instantané")}</span><div class="metric-value">${st.snapshot.advancers} ↑ · ${st.snapshot.decliners} ↓ · ${st.snapshot.unchanged} =</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("Valeur médiane", "Médiane instantané")}</span><div class="metric-value">${fmtPct(st.snapshot.median_variation_pct)}</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("Concentration des échanges", "Top 5 valeur échangée")}</span><div class="metric-value">${fmtPct(st.latest_boc.top5_traded_value_share_pct, 1)}</div><div class="subtext">BOC ${fmtDate(st.latest_boc.date)}</div></div>
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
  if (ui.watchOnly) rows = rows.filter(c => followedTickers().includes(c.ticker));
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
      <div class="company-card-head"><div><div class="ticker">${company.ticker}</div><h3>${escapeHtml(company.name)}</h3><div class="subtext">${escapeHtml(company.sector)}</div>${trackingBadges(company.ticker)}</div>
      <button type="button" class="icon-button ${isWatched(company.ticker) ? "is-on" : ""}" data-toggle-watch="${company.ticker}" aria-label="Épingler personnellement ${company.ticker}" title="Épingle personnelle">${isWatched(company.ticker) ? "★" : "☆"}</button></div>
      <div><div class="company-price">${fmtFCFA(quote.close)}</div><div style="margin-top:6px">${variationPill(quote.variation_pct)} <span class="subtext">${termButton("Volume")} ${fmtNum(quote.volume)}</span></div></div>
      <div class="metric-row">
        <div><div class="metric-label">${termButton("PER")} BOC</div><div class="metric-value">${fmtRatio(boc.per)}</div></div>
        <div><div class="metric-label">${termButton("Rendement net", "Rdt net")} BOC</div><div class="metric-value">${fmtPct(boc.net_dividend_yield_pct, 2, false)}</div></div>
        <div><div class="metric-label">${termButton("Liquidité", "Liquidité méd.")}</div><div class="metric-value">${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)}</div></div>
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
  const figure = entry?.figures?.[key] || {};
  const value = isNum(figure.value) ? figure.value : figure.value_fcfa;
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

function fundamentalOcrSummary(company) {
  const summary = company?.fundamentals?.extraction_summary || {};
  const figuresFromSeries = fundamentalSeries(company || {})
    .flatMap(entry => Object.values(entry.figures || {}))
    .filter(figure => String(figure?.extraction_method || "").includes("ocr")).length;
  return {
    figures: summary.figures_ocr ?? figuresFromSeries,
    attempted: summary.documents_ocr_attempted ?? 0,
    used: summary.documents_ocr_used ?? 0,
    cacheHits: summary.documents_ocr_cache_hits ?? 0
  };
}

function extractionMethodPill(figure) {
  const method = String(figure?.extraction_method || "");
  if (!method.includes("ocr")) return "";
  const label = method === "ocr_controle" ? "OCR contrôlé" : "Texte natif + OCR";
  const confidence = isNum(figure.ocr_confidence) ? ` · reconnaissance ${fmtNum(figure.ocr_confidence, 1)}` : "";
  return `<div><span class="pill amber" title="PDF scanné lu en repli par reconnaissance de caractères ; relire la ligne dans le document officiel">${label}${confidence}</span></div>`;
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
  const detailPillars = computeFundamentalPillars().get(company.ticker) || {};
  const detailHist = company.dividend_history || {};
  const detailSummary = plainSummary(`Comprendre ${company.ticker} avant d’aller dans le détail`, [
    isNum(stats.traded_sessions_last_20) && isNum(stats.median_traded_value_last_20_fcfa)
      ? (stats.traded_sessions_last_20 >= RADAR_RULES.minTradedSessions && stats.median_traded_value_last_20_fcfa >= RADAR_RULES.minMedianTradedValue
        ? `<strong>Échanges :</strong> le titre passe le filtre d’${termButton("Liquidité", "échangeabilité")} du Radar (${stats.traded_sessions_last_20}/20 séances, médiane ${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)}). Cela facilite l’étude, sans garantir le prix d’exécution du jour.`
        : `<strong>Échanges :</strong> le titre ne passe pas le filtre d’${termButton("Liquidité", "échangeabilité")} du Radar (${stats.traded_sessions_last_20}/20 séances, médiane ${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)}). Acheter ou vendre peut donc prendre du temps ou se faire à un prix différent du dernier cours publié.`)
      : "<strong>Échanges :</strong> les statistiques récentes sont insuffisantes pour qualifier la liquidité.",
    detailHist.paid_fiscal_years_count
      ? `<strong>${termButton("Dividende")} :</strong> distributions nettes documentées sur ${detailHist.paid_last_5_fiscal_years ?? 0}/5 derniers exercices du tableau BRVM ; dernier exercice rattaché : ${detailHist.latest_paid_fiscal_year}. Cela décrit le passé, pas la soutenabilité future.`
      : `<strong>${termButton("Dividende")} :</strong> aucune distribution n’est rattachée sans ambiguïté dans le tableau collecté ; SIGMA ne transforme pas cette absence en zéro certain.`,
    detailPillars.solidite || detailPillars.croissance
      ? `<strong>Entreprise :</strong> ${detailPillars.solidite ? `${termButton("Pilier Solidité", "Solidité")} ${detailPillars.solidite.score}/100` : "Solidité non calculable"} · ${detailPillars.croissance ? `${termButton("Pilier Croissance", "Croissance")} ${detailPillars.croissance.score}/100` : "Croissance non calculable"}. Les deux repères restent séparés ; il n’y a pas de score global.`
      : "<strong>Entreprise :</strong> les états financiers extraits ne suffisent pas encore à publier Solidité ou Croissance. Les documents officiels ci-dessous restent donc la source à lire.",
    "<strong>Conclusion SIGMA :</strong> cette fiche organise les preuves et les trous de données. Elle ne dit ni d’acheter ni de vendre."
  ]);

  host.innerHTML = `
    <div class="view-heading" style="margin-top:8px">
      <div><p class="eyebrow">${escapeHtml(company.sector)} · ${company.ticker}</p><h1 id="title-fiche">${escapeHtml(company.name)}</h1>
      <p class="lead">Lecture en trois temps : d’abord l’essentiel en clair, puis les chiffres officiels, puis les documents et limites. Les mots en pointillé avec <span class="term-mark" aria-hidden="true">?</span> ouvrent leur définition.</p>${trackingBadges(company.ticker)}</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="button button-secondary" data-toggle-watch="${company.ticker}">${isWatched(company.ticker) ? "★ Épinglée personnellement" : "☆ Épingler"}</button>
      <button type="button" class="button" data-journal-for="${company.ticker}">Brouillon de thèse automatique</button></div>
    </div>

    ${detailSummary}


    <div class="detail-hero section-space">
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
          <div class="key-fact"><span class="metric-label">Dernier ${termButton("Dividende")} BOC</span><div class="metric-value">${fmtFCFA(boc.last_net_dividend_fcfa)}</div><div class="subtext">Date imprimée : ${escapeHtml(boc.last_dividend_date_label || "—")}</div></div>
          <div class="key-fact"><span class="metric-label">Variation année précédente</span><div class="metric-value">${fmtPct(boc.variation_previous_year_pct)}</div><div class="subtext">Colonne publiée dans le BOC</div></div>
        </div>
        <p class="source-line">Ces ratios sont repris tels que publiés par la BRVM ; SIGMA ne les recalcule pas à partir d’un ${termButton("Bénéfice net par action")} non vérifié.</p>
      </article>
    </div>

    <article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Préparation d'ordre</p><h2>Si vous vouliez acheter des actions ${company.ticker}</h2></div><span class="pill amber">SIGMA ne passe aucun ordre</span></div>
      <p class="muted">SIGMA prépare les chiffres ; l'ordre réel se passe chez votre ${termButton("SGI")}, pendant la séance (négociation en continu de 9h45 à 14h00, fixing de clôture à 14h30 — horaires officiels BRVM). Le cours de référence ci-dessous est le dernier cours <strong>publié</strong> : ce n'est pas un prix en temps réel et l'exécution pourra différer. Sur ce marché, un ${termButton("Ordre à cours limité", "ordre à cours limité")} protège contre les écarts. <strong>La simulation violette plus bas ne transmet rien à la SGI.</strong></p>
      <div class="form-grid" style="margin-top:12px">
        <label>Quantité envisagée (actions)<input id="orderQty" type="number" min="0" step="1" value="${orderDefaultQty}"><span class="field-hint">Pré-rempli automatiquement avec ce que permet un versement mensuel${orderPocketPct ? ` hors ${termButton("Poche d'apprentissage", "poche d'apprentissage")} (${fmtNum(orderPocketPct)} %)` : ""} : ${fmtFCFA(orderWorkingBudget)}. Vous pouvez changer la quantité ; sinon, il n’y a rien à recalculer.</span></label>
        <label>Cours de référence publié<input value="${isNum(orderRefPrice) ? fmtNum(orderRefPrice) : "—"} FCFA" readonly><span class="field-hint">${escapeHtml(DATA.snapshot.source_updated_label || "")} · ${escapeHtml(DATA.snapshot.session_status)} · collecte SIGMA du ${fmtDateTime(DATA.generated_at)}</span></label>
      </div>
      <div class="grid-3" style="margin-top:14px">
        <div class="key-fact"><span class="metric-label">Montant brut · <span id="opQtyEcho">${fmtNum(orderInitial.quantity)}</span> actions</span><div class="metric-value" id="opGross">${fmtFCFA(orderInitial.gross)}</div></div>
        <div class="key-fact"><span class="metric-label">Frais SGI estimés</span><div class="metric-value" id="opFees">${orderInitial.feesKnown ? fmtFCFA(orderInitial.fees) : "Non estimés"}</div><div class="subtext">${orderInitial.feesKnown ? `${escapeHtml(personal.settings.sgiName || "Votre SGI")} · ${fmtNum(Number(personal.settings.feePct), 3)} % + ${fmtFCFA(Number(personal.settings.fixedFee))}` : "Saisissez la grille de votre SGI dans Paramètres"}</div></div>
        <div class="key-fact"><span class="metric-label">Total à prévoir</span><div class="metric-value" id="opTotal">${orderInitial.total === null ? "—" : fmtFCFA(orderInitial.total) + (orderInitial.feesKnown ? "" : " (hors frais)")}</div></div>
        <div class="key-fact"><span class="metric-label">Poids dans votre rythme</span><div class="metric-value" style="font-size:16px" id="opPctBudget">${orderInitial.pctOfMonthly === null ? "—" : `${fmtNum(orderInitial.pctOfMonthly, 0)} % de votre versement mensuel`}</div><div class="subtext" id="opMonths">${orderInitial.monthsOfBudget === null ? "—" : `≈ ${fmtNum(orderInitial.monthsOfBudget, 1)} mois de versement`}</div></div>
        <div class="key-fact"><span class="metric-label">Taille face aux échanges du titre</span><div class="metric-value" style="font-size:16px" id="opLiquidity">${orderInitial.pctOfMedianSession === null ? "—" : `${fmtNum(orderInitial.pctOfMedianSession, 2)} % de la valeur médiane échangée en une séance`}</div><div class="subtext">Sous quelques %, votre ordre reste marginal face au flux habituel ; cela ne garantit ni le prix ni l'exécution du jour.</div></div>
      </div>
      <div class="grid-2-equal" style="margin-top:14px">
        <section class="real-panel"><span class="pill dark">RÉEL · chez votre SGI</span><h3 style="margin-top:9px">Après une exécution réelle seulement</h3><p class="small">SIGMA Peut Préremplir l’enregistrement avec la quantité et le dernier cours publié, mais vous devez corriger prix et frais avec l’avis d’opéré. Le brouillon de thèse est aussi prérempli automatiquement à partir des faits de cette fiche.</p><div class="form-actions"><button type="button" class="button button-small" data-prepare-real-transaction="${company.ticker}">Préparer l’enregistrement réel</button><button type="button" class="button button-secondary button-small" data-journal-for="${company.ticker}">Brouillon de thèse automatique</button></div></section>
        <section class="simulation-panel"><span class="pill simulation">◆ SIMULATION · violet</span><h3 style="margin-top:9px">Essayer sans argent réel</h3><p class="small">Cette action crée uniquement une ligne dans le portefeuille virtuel violet, au dernier cours publié${orderInitial.feesKnown ? " avec vos frais SGI saisis" : " avec des frais inconnus comptés à 0 faute de grille SGI"}. Aucun ordre réel ne part.</p><div class="form-actions"><button type="button" class="button button-simulation button-small" data-simulate-order="${company.ticker}">◆ Simuler cet achat</button></div></section>
      </div>
      <p class="source-line">Le « budget mensuel » n'est ni une limite du marché ni un plafond imposé par SIGMA : c'est votre rythme d'accumulation. Rien n'interdit un achat plus gros un mois donné — l'application montre alors combien de mois de versement il représente, pour que la décision reste délibérée.</p>
    </article>

    <article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Historique BOC</p><h2>Clôtures sur ${points.length} séances lues</h2></div><span class="pill">${termButton("Prix seuls")}</span></div>
      ${lineChart(points, { money: true })}
      <div class="grid-4" style="margin-top:12px">
        <div class="key-fact"><span class="metric-label">5 séances</span><div class="metric-value">${fmtPct(stats.performance_5_sessions_pct)}</div></div>
        <div class="key-fact"><span class="metric-label">20 séances</span><div class="metric-value">${fmtPct(stats.performance_20_sessions_pct)}</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("Séance", "Séances échangées")} / 20</span><div class="metric-value">${fmtNum(stats.traded_sessions_last_20)}</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("Valeur médiane")} / séance</span><div class="metric-value">${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)}</div></div>
      </div>
      ${(() => {
        const long = stats.long_history || {};
        if (!long.sessions_available) return "";
        const horizon = (label, value) => `<div class="key-fact"><span class="metric-label">${label}</span><div class="metric-value">${fmtPct(value)}</div></div>`;
        return `<details style="margin-top:12px"><summary class="strong" style="cursor:pointer;font-size:16px">Archive BOC longue — ${fmtNum(long.sessions_available)} séances (horizons 60/120/250, repli maximal, volatilité)</summary>
        <p class="source-line">${fmtDate(long.first_date)} → ${fmtDate(long.last_date)} · prix publiés non ajustés, hors dividendes réinvestis. Ces horizons situent le parcours, la liquidité et les replis déjà observés ; ils ne prédisent pas le prochain mouvement.</p>
        <div class="grid-4" style="margin-top:10px">
          ${horizon("60 séances", long.performance_60_sessions_pct)}
          ${horizon("120 séances", long.performance_120_sessions_pct)}
          ${horizon("250 séances", long.performance_250_sessions_pct)}
          <div class="key-fact"><span class="metric-label">${termButton("Repli maximal observé")}</span><div class="metric-value">${fmtPct(long.max_drawdown_pct)}</div></div>
          <div class="key-fact"><span class="metric-label">Séances échangées (archive)</span><div class="metric-value">${fmtNum(long.traded_sessions)} / ${fmtNum(long.sessions_available)}</div><div class="subtext">${isNum(long.traded_share_pct) ? `${fmtNum(long.traded_share_pct, 1)} % des séances archivées` : ""}</div></div>
          <div class="key-fact"><span class="metric-label">Valeur médiane (archive)</span><div class="metric-value">${fmtCompactFCFA(long.median_traded_value_fcfa)}</div><div class="subtext">60 dernières séances : ${fmtCompactFCFA(long.median_traded_value_60_fcfa)}</div></div>
          <div class="key-fact"><span class="metric-label">${termButton("Volatilité", "Volatilité annualisée")} (prix)</span><div class="metric-value">${isNum(long.volatility_annualized_pct) ? `${fmtNum(long.volatility_annualized_pct, 1)} %` : "—"}</div></div>
          <div class="key-fact"><span class="metric-label">Pire séance BOC archivée</span><div class="metric-value">${fmtPct(long.worst_session_variation_pct)}</div><div class="subtext">${fmtDate(long.worst_session_date)}</div></div>
        </div></details>`;
      })()}
    </article>

    <div class="section-space">
      <details class="card"><summary style="cursor:pointer"><span class="eyebrow" style="display:block">Dividendes officiels BRVM</span><strong style="font-size:19px">Historique des distributions par exercice</strong></summary>
        ${(() => {
          const hist = company.dividend_history || {};
          const annual = [...(hist.annual || [])].sort((a, b) => b.fiscal_year - a.fiscal_year);
          if (!annual.length) {
            return `<div class="Empty-state">Aucune distribution n’a été rattachée sans ambiguïté à ce ticker dans le tableau BRVM collecté. Cela ne prouve pas à lui seul un dividende nul sur tous les exercices : nouvelle cotation, changement de nom ou ligne non rattachée restent possibles. Le dernier dividende imprimé au BOC est affiché ci-dessus.</div>`;
          }
          return `<div class="grid-4" style="margin-top:10px">
            <div class="key-fact"><span class="metric-label">5 derniers ${termButton("Exercice", "exercices")} du tableau</span><div class="metric-value">${hist.paid_last_5_fiscal_years ?? 0}/5</div><div class="subtext">Exercices avec distribution nette documentée</div></div>
            <div class="key-fact"><span class="metric-label">Profondeur documentée</span><div class="metric-value" style="font-size:16px">${hist.first_paid_fiscal_year ?? "—"} → ${hist.latest_paid_fiscal_year ?? "—"}</div><div class="subtext">${hist.paid_fiscal_years_count ?? 0} exercice(s) versé(s) rattaché(s)</div></div>
            <div class="key-fact"><span class="metric-label">${termButton("Suite courante")}</span><div class="metric-value">${hist.current_consecutive_paid_years ?? 0}</div><div class="subtext">Exercice(s) consécutif(s) jusqu’au dernier exercice du tableau</div></div>
            <div class="key-fact"><span class="metric-label">${termButton("Évolution annuelle moyenne")}</span><div class="metric-value">${fmtPct(hist.dividend_cagr_pct, 1)}</div><div class="subtext">Dividende net/action · ${hist.increases_count ?? 0} hausse(s), ${hist.cuts_count ?? 0} baisse(s) entre exercices consécutifs documentés</div></div>
          </div>
          <div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>Exercice</th><th class="num">Net/action</th><th class="num">Paiement(s)</th><th>Dernière date ${termButton("Ex-dividende", "ex-dividende")}</th><th></th></tr></thead>
          <tbody>${annual.slice(0, 10).map(entry => `<tr><td class="strong">${entry.fiscal_year}</td><td class="num">${fmtFCFA(entry.net_amount_fcfa)}</td><td class="num">${entry.payments_count}</td><td>${fmtDate((entry.ex_dates || []).at(-1))}</td><td>${entry.notice_urls?.length ? `<a class="button button-secondary button-small" href="${entry.notice_urls[0]}" target="_blank" rel="noopener">Avis</a>` : ""}</td></tr>`).join("")}</tbody></table></div>
          <p class="source-line">Historique constitué depuis le tableau officiel BRVM paginé. Plusieurs paiements d’un même exercice sont additionnés et comptés. Une ligne absente signifie « non documentée dans le tableau collecté », pas automatiquement zéro. ${(company.dividend_sustainability?.rows || []).length ? `Les repères « dividende net / BPA » et de ${termButton("Couverture par les flux", "couverture par les flux")} calculables pour cette société sont détaillés dans la section Fondamentaux ci-dessous ; ils ne sont pas le ${termButton("Taux de distribution", "taux de distribution")} brut voté.` : `Le ${termButton("Taux de distribution", "taux de distribution")} et la ${termButton("Couverture par les flux", "couverture par les flux")} restent non calculables pour cette société sans bénéfice par action/nombre d’actions et flux du même exercice suffisamment lisibles.`}</p>`;
        })()}
        <h3 style="margin-top:16px">Avis récents rattachés</h3>
        ${matchedDividends.length ? `<ul class="list-clean">${matchedDividends.slice(0, 6).map(div => `<li class="event-row"><div><div class="strong">${fmtFCFA(div.net_amount_fcfa)} net</div><div class="subtext">Exercice ${escapeHtml(div.fiscal_year)} · ex-dividende ${fmtDate(div.ex_date)} · paiement ${fmtDate(div.payment_date)}</div></div>${div.notice_url ? `<a class="button button-secondary button-small" href="${div.notice_url}" target="_blank" rel="noopener">Avis</a>` : ""}</li>`).join("")}</ul>` : '<div class="Empty-state">Aucun avis du tableau collecté n’a pu être rattaché sans ambiguïté à ce ticker.</div>'}
      </details>
      <article class="card section-space"><p class="eyebrow">Fondamentaux · états financiers officiels</p><h2>Série annuelle et piliers SIGMA</h2>
        ${(() => {
          const fund = company.fundamentals || {};
          const series = fundamentalSeries(company);
          if (!series.length) {
            const ocrSummary = fundamentalOcrSummary(company);
            const ocrAttemptText = ocrSummary.attempted
              ? `<p><strong>${termButton("OCR contrôlé")} :</strong> tenté en repli sur ${ocrSummary.attempted} document(s) scanné(s), mais aucun chiffre n’a passé l’ensemble des contrôles de ${termButton("Confiance OCR", "reconnaissance")}, d’unité, d’ordre des colonnes et de plausibilité. SIGMA préfère donc laisser la série vide plutôt que publier un montant fragile.</p>`
              : "";
            return `<div class="notice"><p><strong>Aucun chiffre annuel n'a passé les contrôles d'extraction pour ${company.ticker}.</strong></p><p>${(fund.notes || []).map(escapeHtml).join(" ") || "Les documents officiels indexés ci-dessous restent la source à lire."}</p>${ocrAttemptText}</div>
            <p class="source-line">Piliers Solidité et Croissance : <strong>non calculables</strong> faute de série suffisante.</p>`;
          }
          const ocrSummary = fundamentalOcrSummary(company);
          const pillars = computeFundamentalPillars().get(company.ticker) || {};
          const activityLabel = series.some(entry => seriesValue(entry, "produit_net_bancaire")) ? "Produit net bancaire" : "Chiffre d'affaires";
          const cell = (entry, key) => {
            const fig = entry.figures?.[key];
            if (!fig) return '<td class="num">—</td>';
            const ev = (fig.evidence || [])[0] || {};
            const titleParts = [
              ev.line || "Ligne source non affichée",
              ev.page ? `page ${ev.page}` : "",
              fig.unit_label || ev.unit_label || "",
              fig.derived ? "calculé depuis ses composantes" : "",
              String(fig.extraction_method || "").includes("ocr") ? "provenance : OCR contrôlé" : "provenance : texte natif du PDF"
            ].filter(Boolean);
            return `<td class="num"><span title="${escapeHtml(titleParts.join(" · "))}">${fmtFigureValue(fig)}</span><div>${confidencePill(fig.confidence)}</div>${extractionMethodPill(fig)}</td>`;
          };
          const hasFigure = key => series.some(entry => seriesValue(entry, key) !== null);
          const extraColumns = [];
          if (hasFigure("flux_tresorerie_operationnel")) extraColumns.push({ key: "flux_tresorerie_operationnel", label: "Flux opérationnel", term: "Flux de trésorerie opérationnel" });
          if (hasFigure("investissements_immobilisations")) extraColumns.push({ key: "investissements_immobilisations", label: "Investissements immobilisations", term: "Investissements en immobilisations" });
          if (hasFigure("dividendes_verses")) extraColumns.push({ key: "dividendes_verses", label: "Dividendes versés (flux)", term: "Dividende" });
          if (hasFigure("tresorerie_equivalents")) extraColumns.push({ key: "tresorerie_equivalents", label: "Trésorerie et équivalents", term: "Trésorerie et équivalents" });
          if (hasFigure("tresorerie_passif")) extraColumns.push({ key: "tresorerie_passif", label: "Trésorerie-passif", term: "Trésorerie nette" });
          if (hasFigure("tresorerie_nette")) extraColumns.push({ key: "tresorerie_nette", label: "Trésorerie nette", term: "Trésorerie nette" });
          if (hasFigure("dettes_financieres")) {
            extraColumns.push({ key: "dettes_financieres", label: "Dettes financières (total calculé)", term: "Dettes financières" });
          } else {
            if (hasFigure("dettes_financieres_non_courantes")) extraColumns.push({ key: "dettes_financieres_non_courantes", label: "Dettes fin. non courantes", term: "Dettes financières" });
            if (hasFigure("dettes_financieres_courantes")) extraColumns.push({ key: "dettes_financieres_courantes", label: "Dettes fin. courantes", term: "Dettes financières" });
          }
          if (hasFigure("benefice_par_action")) extraColumns.push({ key: "benefice_par_action", label: "BPA publié", term: "Bénéfice net par action" });
          const shareKey = hasFigure("nombre_actions_fin_exercice") ? "nombre_actions_fin_exercice" : hasFigure("nombre_actions_moyen_pondere") ? "nombre_actions_moyen_pondere" : null;
          if (shareKey) extraColumns.push({ key: shareKey, label: shareKey === "nombre_actions_fin_exercice" ? "Actions fin d'exercice" : "Actions moyen pondéré", term: "Nombre d'actions" });
          const sustainabilityRows = company.dividend_sustainability?.rows || [];
          const solidite = pillars.solidite, croissance = pillars.croissance;
          const pillarBar = (label, value, max = 100) => `<div class="score-part"><span>${label}</span><div class="bar-track"><div class="bar-fill" style="width:${value}%"></div></div><span class="strong">${value}/${max}</span></div>`;
          return `<div class="notice green" style="margin-bottom:12px"><p><strong>En clair :</strong> l’activité dit ce que l’entreprise vend ; le ${termButton("Résultat net")} dit si elle gagne ou perd de l’argent ; les ${termButton("Capitaux propres")} sont son coussin appartenant aux actionnaires ; le ${termButton("Total du bilan")} indique sa taille. Lisez la tendance sur plusieurs années et le badge de vérification sous chaque chiffre, pas une seule case.</p></div>
          <div class="news-meta">
            <span class="pill ${fund.data_confidence === "A" ? "green" : fund.data_confidence === "B" ? "" : "amber"}">Confiance données ${escapeHtml(fund.data_confidence || "—")}</span>
            ${termButton("Confiance données", "Comprendre A / B / C")}
            <span class="tag-chip">${series.length} exercice(s) : ${Math.min(...series.map(e => e.exercice))} – ${Math.max(...series.map(e => e.exercice))}</span>
            ${ocrSummary.figures ? `<span class="tag-chip">${termButton("OCR contrôlé")} : ${ocrSummary.figures} chiffre(s) · ${ocrSummary.used} document(s) source(s)</span>` : ""}
          </div>
          ${ocrSummary.figures ? `<div class="notice" style="margin-bottom:12px"><p><strong>Provenance à garder en tête :</strong> une partie de cette série vient de PDF officiels scannés lus par ${termButton("OCR contrôlé")}. Le badge et la ${termButton("Confiance OCR", "confiance de reconnaissance")} restent affichés sous chaque montant concerné ; le recoupement entre documents reste un contrôle distinct. Relisez la page source avant une décision importante.</p></div>` : ""}
          <div class="table-wrap"><table><thead><tr><th>${termButton("Exercice")}</th><th class="num">${termButton(activityLabel)}</th><th class="num">${termButton("Résultat net")}</th><th class="num">${termButton("Capitaux propres", "Capitaux propres")}</th><th class="num">${termButton("Total du bilan")}</th></tr></thead>
          <tbody>${series.map(entry => `<tr><td class="strong">${entry.exercice}</td>${cell(entry, seriesValue(entry, "produit_net_bancaire") ? "produit_net_bancaire" : "chiffre_affaires")}${cell(entry, entry.figures?.resultat_net ? "resultat_net" : "resultat_net_part_groupe")}${cell(entry, "capitaux_propres")}${cell(entry, "total_bilan")}</tr>`).join("")}</tbody></table></div>
          <p class="source-line">Lecture automatique des états financiers officiels : ${termButton("Texte natif")} d’abord ; ${termButton("OCR contrôlé")} seulement en repli si le PDF scanné ne donne aucun chiffre natif. Unité explicite exigée — ou cas documentés des états SYSCOHADA codés et de l’${termButton("Unité recoupée par le capital légal", "unité bancaire recoupée par le capital légal")} — colonnes N/N-1 prouvées par les en-têtes, contrôles de cohérence du bilan et de continuité de la série. ${termButton("Confirmé · 2 documents")} = même valeur publiée par deux documents distincts pour le même exercice. Survolez une valeur pour sa ligne, sa page, son unité et sa provenance ; documents complets ci-dessous.</p>

          ${extraColumns.length ? `<details style="margin-top:14px"><summary class="strong" style="cursor:pointer;font-size:16px">Flux, trésorerie, dette et données par action</summary>
          <div class="notice green" style="margin:10px 0"><p><strong>En clair :</strong> le ${termButton("Flux de trésorerie opérationnel", "flux opérationnel")} dit si l'activité a dégagé du cash pendant l'année ; la trésorerie et les ${termButton("Dettes financières", "dettes financières")} sont des montants photographiés à la clôture ; le ${termButton("Bénéfice net par action", "BPA")} et le ${termButton("Nombre d'actions", "nombre d'actions")} permettent seulement ensuite de rapporter le dividende aux bénéfices et au cash du même exercice.</p></div>
          <div class="table-wrap"><table><thead><tr><th>${termButton("Exercice")}</th>${extraColumns.map(col => `<th class="num">${termButton(col.term, col.label)}</th>`).join("")}</tr></thead>
          <tbody>${series.map(entry => `<tr><td class="strong">${entry.exercice}</td>${extraColumns.map(col => cell(entry, col.key)).join("")}</tr>`).join("")}</tbody></table></div>
          <p class="source-line">Les investissements et dividendes versés sont des flux présentés en négatif lorsqu'ils sortent de la trésorerie. Le BPA et le nombre d'actions ne sont jamais multipliés par l'unité monétaire du tableau. Un total de dettes financières n'est calculé que si courant et non courant du même exercice ont tous deux été lus ; pour une banque, ce poste ne résume pas les dépôts de la clientèle.</p></details>` : `<p class="small muted" style="margin-top:12px"><strong>Flux, dette et données par action :</strong> aucun chiffre supplémentaire n'a encore passé les contrôles pour ${company.ticker}. SIGMA ne déduit ni le cash ni le nombre d'actions depuis le seul bilan.</p>`}

          <h3 style="margin-top:16px">Piliers SIGMA calculables</h3>
          ${solidite ? `<div class="key-fact" style="margin-top:8px"><div class="event-row"><span class="metric-label">${termButton("Pilier Solidité", "Solidité (pilier)")}</span><span class="score-total" style="font-size:19px">${solidite.score}<span style="font-size:11px">/100</span></span></div>
            ${pillarBar(`${termButton("Capitaux propres")} / bilan (rang)`, solidite.parts.ratioScore)}
            ${pillarBar("Exercices bénéficiaires", solidite.parts.stabilityScore)}
            ${solidite.parts.roeScore !== null ? pillarBar(`${termButton("Rentabilité des capitaux propres")} (rang)`, solidite.parts.roeScore) : ""}
            <div class="subtext">Capitaux propres = ${fmtNum(solidite.cpRatio, 1)} % du bilan (dernier exercice complet) · résultat positif sur ${fmtNum((solidite.positiveShare || 0) * 100, 0)} % des ${solidite.rnYears} exercices lus${solidite.roe !== null ? ` · ROE ${fmtNum(solidite.roe, 1)} %` : ""}. Rangs calculés parmi les sociétés de même nature (financières / non financières) disposant d'une série suffisante.</div></div>`
          : `<p class="small muted"><strong>Solidité : non calculable.</strong> Il faut au minimum 3 exercices de résultat net et 2 de capitaux propres, avec un bilan complet récent.</p>`}
          ${croissance ? `<div class="key-fact" style="margin-top:10px"><div class="event-row"><span class="metric-label">${termButton("Pilier Croissance", "Croissance (pilier)")}</span><span class="score-total" style="font-size:19px">${croissance.score}<span style="font-size:11px">/100</span></span></div>
            ${pillarBar("Croissance de l'activité (rang)", croissance.parts.activityScore)}
            ${croissance.parts.rnScore !== null ? pillarBar("Croissance du résultat net (rang)", croissance.parts.rnScore) : ""}
            <div class="subtext">Croissance annuelle moyenne de l'activité : ${fmtPct(croissance.activityCagr, 1)} sur ${croissance.activityYears} exercices${croissance.rnCagr !== null ? ` · résultat net : ${fmtPct(croissance.rnCagr, 1)}` : " · résultat net non retenu (perte sur la période ou série incomplète)"}.</div></div>`
          : `<p class="small muted"><strong>Croissance : non calculable.</strong> Il faut au moins 3 exercices d'activité (chiffre d'affaires ou produit net bancaire) sur 2 ans ou plus.</p>`}
          <div class="key-fact" style="margin-top:12px"><div class="event-row"><span class="metric-label">${termButton("Dividende durable", "Repères dividende · bénéfice · cash")}</span><span class="pill ${sustainabilityRows.length ? "green" : "amber"}">${sustainabilityRows.length ? `${sustainabilityRows.length} exercice(s) calculable(s)` : "Non calculable"}</span></div>
          ${sustainabilityRows.length ? `<p class="small"><strong>En clair :</strong> « dividende net / BPA » compare le dividende net par action au bénéfice par action du même exercice. La ${termButton("Couverture par les flux", "couverture")} compare ensuite le cash opérationnel à la distribution nette totale calculée avec le nombre d'actions lu. Ce sont des repères séparés, pas une promesse que le dividende sera maintenu.</p>
          <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>Exercice</th><th class="num">Dividende net/action</th><th class="num">${termButton("Bénéfice net par action", "BPA")}</th><th class="num">Dividende net / BPA</th><th class="num">Distribution nette totale calculée</th><th class="num">${termButton("Couverture par les flux", "Couverture flux")}</th><th class="num">Après investissements</th></tr></thead>
          <tbody>${sustainabilityRows.slice(0, 6).map(row => `<tr><td class="strong">${row.exercice}</td><td class="num">${fmtFigureValue({ value: row.dividende_net_par_action_fcfa, value_kind: "fcfa_par_action" })}</td><td class="num">${fmtFigureValue({ value: row.benefice_par_action_fcfa, value_kind: "fcfa_par_action" })}</td><td class="num strong">${isNum(row.dividende_net_sur_bpa_pct) ? fmtPct(row.dividende_net_sur_bpa_pct, 1, false) : "—"}</td><td class="num">${fmtCompactFCFA(row.distribution_nette_totale_calculee_fcfa)}</td><td class="num strong">${fmtMultiple(row.couverture_flux_operationnel_x)}</td><td class="num">${fmtMultiple(row.couverture_apres_investissements_x)}</td></tr>`).join("")}</tbody></table></div>
          <p class="source-line">${escapeHtml(company.dividend_sustainability?.method || "")} Les intrants et leurs badges de recoupement restent visibles dans les tableaux annuels ci-dessus.</p>` : `<p class="small muted">Aucun exercice ne réunit encore, pour ${company.ticker}, un dividende documenté et les intrants du même exercice nécessaires : BPA publié pour le ratio par action, ou nombre d'actions + flux opérationnel pour la couverture cash. SIGMA affiche donc l'historique des montants sans en déduire une soutenabilité.</p>`}
          </div>
          <div class="notice" style="margin-top:12px"><p><strong>Score global : toujours suspendu.</strong> SIGMA publie la Solidité, la Croissance et ces repères dividende/flux séparément. Les fusionner maintenant donnerait un poids trompeur aux sociétés simplement mieux documentées ; le ${termButton("Dividende durable", "pilier Dividende durable")} ne deviendra une note que lorsque le taux brut de distribution, la couverture cash et les recoupements seront suffisamment couverts.</p></div>
          ${(fund.notes || []).length ? `<details style="margin-top:10px"><summary class="strong" style="cursor:pointer">Contrôles et écarts signalés (${fund.notes.length})</summary><ul>${fund.notes.map(note => `<li class="small">${escapeHtml(note)}</li>`).join("")}</ul></details>` : ""}`;
        })()}
      </article>
    </div>

    <details class="card section-space"><summary style="cursor:pointer"><span class="eyebrow" style="display:block">Bibliothèque officielle de l'émetteur · collecte automatique</span><strong style="font-size:19px">Documents financiers indexés sur brvm.org (${(company.documents || []).length})</strong></summary>
      ${(company.documents || []).length ? `<div class="table-wrap"><table><thead><tr><th>Document</th><th>Type</th><th>Exercice</th><th>Publié le</th><th></th></tr></thead>
      <tbody>${(company.documents || []).slice(0, 12).map(doc => `<tr><td class="strong">${escapeHtml(doc.label)}</td><td>${escapeHtml(DOC_TYPE_LABELS[doc.doc_type] || "Document officiel")}</td><td>${doc.exercice ?? "—"}</td><td>${fmtDate(doc.published_date)}</td><td><a class="button button-secondary button-small" href="${escapeHtml(doc.url)}" target="_blank" rel="noopener">PDF officiel</a></td></tr>`).join("")}</tbody></table></div>
      <p class="source-line">Index constitué automatiquement depuis la page officielle de l'émetteur. Les rapports d'activité trimestriels et semestriels complètent les états financiers annuels audités.</p>` : '<div class="Empty-state">Aucun document n\'a pu être rattaché à cette société dans la dernière collecte.</div>'}
    </details>

    <article class="card section-space">
      <div class="event-row"><div><p class="eyebrow">Collecte automatique</p><h2>Publications rattachées à ${company.ticker}</h2></div><button type="button" class="button button-secondary button-small" data-view-link="actualites">Ouvrir le fil complet</button></div>
      ${newsForTicker(company.ticker, 5).length ? newsForTicker(company.ticker, 5).map(newsItemHtml).join("") : '<div class="Empty-state">Aucune annonce ni dépêche n\'a été rattachée à cette société dans la dernière collecte. Cela ne signifie pas qu\'aucune information n\'existe : vérifier les rapports officiels de l\'émetteur.</div>'}
    </article>

    <details class="card section-space"><summary style="cursor:pointer"><span class="eyebrow" style="display:block">Preuves récentes</span><strong style="font-size:19px">10 dernières séances BOC</strong></summary>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th class="num">Clôture</th><th class="num">Variation BOC</th><th class="num">${termButton("Volume")}</th><th class="num">${termButton("Valeur échangée")}</th></tr></thead>
      <tbody>${[...(company.series || [])].slice(-10).reverse().map(p => `<tr><td>${fmtDate(p.date)}</td><td class="num strong">${fmtFCFA(p.close)}</td><td class="num">${variationPill(p.variation_pct)}</td><td class="num">${fmtNum(p.volume)}</td><td class="num">${fmtFCFA(p.traded_value_fcfa)}</td></tr>`).join("")}</tbody></table></div>
    </details>

    <article class="card section-space"><p class="eyebrow">Mémoire personnelle</p><h2>Journal lié à ${company.ticker}</h2>
      ${journal.length ? `<ul class="list-clean">${journal.map(item => `<li><div class="strong">${escapeHtml(item.title)}</div><div class="subtext">${fmtDate(item.date)} · ${escapeHtml(item.type)}</div><p>${escapeHtml(item.text)}</p>${item.invalidation ? `<p class="small"><strong>Invalidation :</strong> ${escapeHtml(item.invalidation)}</p>` : ""}</li>`).join("")}</ul>` : '<div class="Empty-state">Aucune thèse enregistrée pour cette société. SIGMA Peut Préremplir un brouillon à partir des faits datés de cette fiche ; il ne se transforme en mémoire personnelle qu’après votre relecture. <button type="button" class="button button-small" data-journal-for="${company.ticker}" style="margin-top:10px">Préparer le brouillon</button></div>'}
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
      ${partBar(termButton("Liquidité"), entry.parts.liquidity, RADAR_RULES.weights.liquidity, `${fmtNum(stats.traded_sessions_last_20)}/20 séances · valeur médiane ${fmtCompactFCFA(stats.median_traded_value_last_20_fcfa)}`)}
      ${partBar(termButton("Valorisation"), entry.parts.valuation, RADAR_RULES.weights.valuation, `PER BOC ${fmtRatio(boc.per)} · médiane du secteur ${fmtRatio(entry.sectorPer)}`)}
      ${partBar(termButton("Rendement net", "Rendement"), entry.parts.yield, RADAR_RULES.weights.yield, `Rendement net BOC ${fmtPct(boc.net_dividend_yield_pct, 2, false)} · dernier dividende ${escapeHtml(boc.last_dividend_date_label || "—")} · historique BRVM : ${dividendHistoryLabel(company)}`)}
    </div>
    <div class="subtext" style="margin-top:8px">Cours ${fmtFCFA(latestPrice(company).value)} · ${fmtPct(stats.performance_20_sessions_pct)} sur 20 séances (${termButton("Prix seuls", "prix seuls")})</div>${trackingBadges(company.ticker)}
    ${(() => {
      const fund = company.fundamentals || {};
      const pillars = computeFundamentalPillars().get(company.ticker) || {};
      const ocrSummary = fundamentalOcrSummary(company);
      const ocrText = ocrSummary.figures
        ? ` · ${termButton("OCR contrôlé")} : ${ocrSummary.figures} chiffre(s)`
        : ocrSummary.attempted ? ` · OCR tenté sans chiffre retenu` : "";
      const sust = company.dividend_sustainability?.rows?.[0] || null;
      const sustText = sust ? `<div class="subtext" style="margin-top:3px">Repère dividende/flux ${sust.exercice} : dividende net/BPA ${isNum(sust.dividende_net_sur_bpa_pct) ? fmtPct(sust.dividende_net_sur_bpa_pct, 1, false) : "n/c"} · couverture flux ${fmtMultiple(sust.couverture_flux_operationnel_x)} <span class="muted">(détail et méthode en fiche)</span></div>` : "";
      if (pillars.solidite || pillars.croissance) {
        return `<div class="subtext" style="margin-top:4px">Fondamentaux (${fund.exercices_couverts ?? 0} exercices, ${termButton("Confiance données", "confiance")} ${escapeHtml(fund.data_confidence || "—")}${ocrText}) : ${pillars.solidite ? `${termButton("Pilier Solidité", "Solidité")} <strong>${pillars.solidite.score}/100</strong>` : "Solidité n/c"} · ${pillars.croissance ? `${termButton("Pilier Croissance", "Croissance")} <strong>${pillars.croissance.score}/100</strong>` : "Croissance n/c"}</div>${sustText}`;
      }
      if ((fund.series || []).length) {
        return `<div class="subtext" style="margin-top:4px">Fondamentaux : série de ${fund.series.length} exercice(s) extraite${ocrText}, piliers <strong>non calculables</strong> (seuils non atteints)</div>${sustText}`;
      }
      return `<div class="subtext" style="margin-top:4px">Fondamentaux annuels : <strong>non extraits</strong> à ce stade${ocrText}</div>`;
    })()}
    ${entry.flags.map(flag => `<p class="radar-flag"><span class="pill ${flag.tone}">${flag.tone === "red" ? "À examiner" : flag.tone === "amber" ? "Vigilance prix" : "À lire"}</span> ${escapeHtml(flag.text)}</p>`).join("")}
    <div class="form-actions" style="margin-top:10px">
      <button type="button" class="button button-secondary button-small" data-open-company="${company.ticker}">Fiche</button>
      <button type="button" class="button button-secondary button-small" data-toggle-watch="${company.ticker}">${isWatched(company.ticker) ? "★ Épinglée" : "☆ Épingler"}</button>
      <button type="button" class="button button-small" data-journal-for="${company.ticker}">Brouillon de thèse automatique</button>
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
      <div class="key-fact"><span class="metric-label">Règle 1 — ${termButton("Liquidité", "Échangeabilité")}</span><div class="metric-value" style="font-size:16px">≥ ${rules.minTradedSessions}/20 séances et ≥ ${fmtCompactFCFA(rules.minMedianTradedValue)} médiane</div><div class="subtext">Un versement de 100 000 à 300 000 FCFA doit rester une fraction raisonnable des échanges d'une séance type.</div></div>
      <div class="key-fact"><span class="metric-label">Règle 2 — ${termButton("Valorisation", "Valorisation publiée")}</span><div class="metric-value" style="font-size:16px">${termButton("PER")} BOC présent, entre 0 et ${rules.maxPer}</div><div class="subtext">Un PER absent signale souvent un ${termButton("Bénéfice net par action", "bénéfice par action")} négatif ou non communiqué : hors premier tri, pas hors étude définitive.</div></div>
      <div class="key-fact"><span class="metric-label">Règle 3 — ${termButton("Dividende", "Dividende documenté")}</span><div class="metric-value" style="font-size:16px">Rendement &gt; 0, ≤ 15 %, &lt; 18 mois</div><div class="subtext">Les rendements extrêmes ou anciens sont écartés. L’historique BRVM par exercice est ensuite affiché pour distinguer une distribution régulière d’un paiement isolé ; il ne remplace pas le ${termButton("Taux de distribution", "taux de distribution")}.</div></div>
    </div>
    <p class="source-line">Notation des éligibles : rangs parmi les éligibles — ${termButton("Liquidité")} ${rules.weights.liquidity} pts, ${termButton("Valorisation", "Valorisation relative")} ${rules.weights.valuation} pts, ${termButton("Rendement net", "Rendement")} ${rules.weights.yield} pts. Sélection limitée à ${rules.maxPerSector} sociétés par secteur pour éviter une liste mono-sectorielle.</p>
    ${personal.settings.autoFollowRadar === false ? `<div class="notice" style="margin-top:12px"><p><strong>Suivi automatique désactivé.</strong> La sélection n’alimente ni l’accueil, ni les alertes, ni le filtre des actualités, sauf vos épingles et positions.</p></div>` : `<div class="notice green" style="margin-top:12px"><p><strong>Déjà fait automatiquement :</strong> cette sélection alimente l’accueil, les alertes et le filtre « Mes valeurs » sous le badge « Suivi automatique Radar ». Vous n’avez pas à l’ajouter à la main. L’étoile reste réservée à votre ${termButton("Liste de suivi", "liste de suivi personnelle")}.</p></div>`}
    <div class="form-actions"><button type="button" class="button" data-decision-link="decision">Préparer la décision du mois</button><button type="button" class="button button-secondary" data-view-link="parametres">Régler le suivi automatique</button></div>
  </article>

  <div class="grid-2-equal section-space">${selection.map((entry, index) => radarEntryCard(entry, index + 1)).join("")}</div>

  ${overflow.length ? `<article class="card section-space"><p class="eyebrow">Éligibles suivantes</p><h2>Hors sélection : plafond sectoriel ou rang</h2>
    <div class="table-wrap"><table><thead><tr><th>Société</th><th class="num">${termButton("Score d'étude")}</th><th class="num">${termButton("PER")} BOC</th><th class="num">${termButton("Rendement net", "Rendement")}</th><th class="num">${termButton("Liquidité", "Liquidité méd.")}</th><th></th></tr></thead>
    <tbody>${overflow.map(entry => `<tr><td><div class="ticker">${entry.company.ticker}</div><div class="subtext">${escapeHtml(entry.company.name)} · ${escapeHtml(entry.company.sector)}</div></td><td class="num strong">${entry.score}/100</td><td class="num">${fmtRatio(entry.company.latest_boc?.per)}</td><td class="num">${fmtPct(entry.company.latest_boc?.net_dividend_yield_pct, 2, false)}</td><td class="num">${fmtCompactFCFA(entry.company.history_stats?.median_traded_value_last_20_fcfa)}</td><td><button type="button" class="button button-secondary button-small" data-open-company="${entry.company.ticker}">Fiche</button></td></tr>`).join("")}</tbody></table></div></article>` : ""}

  <article class="card section-space"><p class="eyebrow">Transparence du tri</p><h2>${rejected.length} société(s) écartée(s) par les règles</h2>
    <ul class="list-clean">${[...reasonCounts.entries()].sort((a, b) => b[1] - a[1]).map(([label, count]) => `<li class="event-row"><span>${escapeHtml(label)}</span><strong>${count}</strong></li>`).join("")}</ul>
    <p class="subtext">Une société peut cumuler plusieurs motifs. Être écartée du Radar ne signifie pas « mauvaise entreprise » : cela signifie que les données de marché vérifiées ne suffisent pas à la placer dans le premier périmètre d'étude.</p>
    <details style="margin-top:10px"><summary class="strong" style="cursor:pointer">Détail société par société</summary>
      <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>Société</th><th>Motif(s) d'écartement</th></tr></thead>
      <tbody>${rejected.map(item => `<tr><td><div class="ticker">${item.company.ticker}</div><div class="subtext">${escapeHtml(item.company.name)}</div></td><td>${item.reasons.map(escapeHtml).join(" · ")}</td></tr>`).join("")}</tbody></table></div>
    </details>
    <div class="notice" style="margin-top:14px"><p><strong>Limite assumée.</strong> Le score d’étude du Radar reste fondé sur le marché ; les ${termButton("États financiers")} sont présentés séparément dans chaque fiche (Solidité/Croissance quand calculables). Dette nette, flux, ${termButton("Taux de distribution", "taux de distribution")} et avantages concurrentiels ne sont pas encore intégrés au tri.</p></div>
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
    <p class="muted">Quatre réponses, une seule fois, pour que le reste soit automatique : collecte des données officielles, ${termButton("Radar SIGMA", "sélection Radar")} suivie automatiquement, décision du mois calibrée sur votre versement et alertes sur le bon périmètre. <strong>En noir/vert :</strong> officiel et réel déclaré ; <strong style="color:#5b21b6">en violet :</strong> simulation sans argent réel. Ces réglages restent dans ce navigateur et se modifient dans Paramètres.</p>
    <form id="onboardingForm">
      <section class="onboarding-step"><p class="eyebrow">1 · Votre pays et votre ${termButton("SGI", "SGI")}</p>
        <div class="form-grid">
          <label>Pays de résidence<select name="country" id="onbCountry">
            ${UEMOA_COUNTRIES.map(c => `<option value="${c}" ${c === country ? "selected" : ""}>${c}</option>`).join("")}
            <option value="Autre" ${country === "Autre" ? "selected" : ""}>Autre pays</option>
          </select></label>
          <label>Votre ${termButton("SGI")} (annuaire officiel BRVM)<select name="sgiChoice" id="onbSgi"></select>
          <span class="field-hint">La BRVM publie les SGI agréées et leurs contacts, pas leurs tarifs : aucun classement tarifaire n'est inventé.</span></label>
          <label id="onbSgiFreeWrap" hidden>Nom exact de la SGI<input name="sgiFree" value="${escapeHtml(profile.sgiName || settings.sgiName || "")}" placeholder="Telle qu'écrite sur votre convention"></label>
          <label>${termButton("Courtage")} de votre SGI (%) — optionnel<input name="feePct" type="number" min="0" step="0.001" value="${escapeHtml(settings.feePct)}" placeholder="Vide = frais non estimés"><span class="field-hint">À recopier depuis la grille tarifaire reçue de votre SGI.</span></label>
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
          <label class="checkbox-label"><input type="checkbox" name="pocketEnabled" id="onbPocket" ${profile.pocketEnabled ? "checked" : ""}> Réserver une ${termButton("Poche d'apprentissage", "poche d'apprentissage")} séparée <span class="subtext">(argent réel séparé — distincte de la simulation violette)</span></label>
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
        <button type="button" class="button button-secondary" id="onbLater">Plus tard — utiliser SIGMA sans profil</button>
      </div>
      <p class="source-line">« Plus tard » vous laisse utiliser SIGMA immédiatement avec des valeurs neutres (200 000 FCFA, frais non estimés) et cet écran ne se réimposera pas à chaque ouverture. Vous pourrez lancer le préréglage quand vous voudrez depuis Paramètres. Aucune donnée personnelle ne quitte ce navigateur.</p>
    </form>
  </div>`;

  const countrySelect = $("#onbCountry");
  const sgiSelect = $("#onbSgi");
  const freeWrap = $("#onbSgiFreeWrap");
  const fillSgis = () => {
    const list = sgisForCountry(countrySelect.value === "Autre" ? "" : countrySelect.value);
    const current = profile.sgiName || settings.sgiName || "";
    const plafondHint = (sgi) => {
      const courtage = (sgi.tariffs_homologated?.rates || []).find(rate => rate.key === "courtage_ordinaire");
      return Number.isFinite(courtage?.Parsed_percent_max) ? ` · plafond courtage homologué ≤ ${String(parseFloat(Number(courtage.Parsed_percent_max).toFixed(4))).replace(".", ",")} % (négociable, voir Paramètres)` : "";
    };
    sgiSelect.innerHTML = `<option value="">Je n'ai pas encore de SGI</option>`
      + list.map(sgi => `<option value="${escapeHtml(sgi.name)}" ${normalize(sgi.name) === normalize(current) ? "selected" : ""}>${escapeHtml(sgi.name)}${countrySelect.value === "Autre" && sgi.country ? ` — ${escapeHtml(sgi.country)}` : ""}${plafondHint(sgi)}</option>`).join("")
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
  $("#onbLater").addEventListener("click", () => { personal.onboardingDismissedAt = new Date().toISOString(); savePersonal(); dialog.close(); showToast("Préréglage reporté : SIGMA reste utilisable et ne vous le réimposera pas à chaque ouverture."); });

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
    personal.onboardingDismissedAt = null;
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
  const mine = new Set(followedTickers());
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
    <p class="source-line">Ordre : date de publication décroissante. Les actualités BRVM ne portent pas de date de publication structurée : SIGMA signale alors « date mentionnée dans le texte ». La presse est étiquetée comme telle et ne remplace jamais l'annonce officielle de l'émetteur. Le filtre « Mes valeurs » inclut vos positions et épingles${personal.settings.autoFollowRadar === false ? "" : " plus le suivi automatique Radar"} ; la raison du suivi est visible en ouvrant la fiche.</p>
    ${items.length ? items.map(newsItemHtml).join("") : '<div class="Empty-state">Aucune publication ne correspond à ce filtre dans la dernière collecte.</div>'}
    ${total > items.length ? `<p class="source-line" style="margin-top:10px">Affichage limité aux ${items.length} plus récentes ; affinez la recherche pour le reste.</p>` : ""}
  </article>`;
}

function renderAnalysisIndicators() {
  const sorted = [...COMPANIES].sort((a, b) => a.sector.localeCompare(b.sector, "fr") || a.name.localeCompare(b.name, "fr"));
  return `<article class="card">
    <div class="event-row"><div><p class="eyebrow">BOC du ${fmtDate(latestBocDate())}</p><h2>PER et rendement tels que publiés par la BRVM</h2></div><span class="pill amber">Descriptif, pas un score SIGMA</span></div>
    <div class="notice green" style="margin-top:12px"><p><strong>En clair :</strong> comparez chaque société surtout à la ${termButton("Valeur médiane", "médiane")} de son secteur. Un ${termButton("PER")} bas ou un ${termButton("Rendement net")} élevé ne suffit jamais à conclure : bénéfice exceptionnel, dividende non récurrent, faible liquidité ou risque propre peuvent expliquer l’écart. Ces ratios sont publiés par la BRVM, pas recalculés par SIGMA.</p></div>
    <div class="grid-3" style="margin:14px 0">${sectorList().map(sector => `<div class="key-fact"><span class="metric-label">${escapeHtml(sector)}</span><div class="metric-value">${termButton("PER", "PER méd.")} ${fmtRatio(sectorMedian("per", sector))}</div><div class="subtext">${termButton("Rendement net", "Rendement net méd.")} ${fmtPct(sectorUsableYieldMedian(sector), 2, false)}</div></div>`).join("")}</div>
    <div class="table-wrap"><table><thead><tr><th>Société</th><th>Secteur</th><th class="num">${termButton("PER")} BOC</th><th class="num">${termButton("Rendement net")}</th><th class="num">Dernier ${termButton("Dividende")} BOC</th><th class="num">Var. année préc.</th></tr></thead>
    <tbody>${sorted.map(c => `<tr class="clickable-row" data-open-company="${c.ticker}"><td><div class="ticker">${c.ticker}</div><div class="subtext">${escapeHtml(c.name)}</div></td><td>${escapeHtml(c.sector)}</td><td class="num">${fmtRatio(c.latest_boc?.per)}</td><td class="num">${fmtPct(c.latest_boc?.net_dividend_yield_pct, 2, false)}${ratioWarning(c)}</td><td class="num">${fmtFCFA(c.latest_boc?.last_net_dividend_fcfa)}<div class="subtext">${escapeHtml(c.latest_boc?.last_dividend_date_label || "")}</div></td><td class="num">${fmtPct(c.latest_boc?.variation_previous_year_pct)}</td></tr>`).join("")}</tbody></table></div>
  </article>`;
}
function renderAnalysisLiquidity() {
  const rows = [...COMPANIES].sort((a, b) => (b.history_stats?.median_traded_value_last_20_fcfa ?? -1) - (a.history_stats?.median_traded_value_last_20_fcfa ?? -1));
  const max = Math.max(...rows.map(c => c.history_stats?.median_traded_value_last_20_fcfa || 0), 1);
  return `<article class="card"><p class="eyebrow">Calcul SIGMA · BOC officiels</p><h2>${termButton("Liquidité")} sur les 20 dernières séances lues</h2>
  <div class="notice green" style="margin:12px 0"><p><strong>En clair :</strong> plus une société est échangée souvent et pour des montants réguliers, plus il sera en général facile d’entrer ou de sortir. La ${termButton("Valeur médiane")} inclut les séances sans échange à zéro lorsqu’une ligne est présente au BOC ; elle évite de surestimer une société active un seul jour exceptionnel.</p></div>
  <div class="table-wrap"><table><thead><tr><th>Société</th><th class="num">Échangée / 20 ${termButton("Séance", "séances")}</th><th>${termButton("Valeur médiane")} par séance</th><th class="num">Montant</th><th class="num">5 séances (${termButton("Prix seuls", "prix")})</th><th class="num">20 séances (${termButton("Prix seuls", "prix")})</th></tr></thead>
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
function computeMonthlyCandidates() {
  const d = ui.decision;
  const budget = Number(d.budget) || 0;
  const pocketPct = personal.profile?.pocketEnabled ? Math.min(50, Math.max(0, Number(personal.profile.pocketPct) || 0)) : 0;
  const pocketAmount = Math.round(budget * pocketPct / 100);
  const workingBudget = Math.max(0, budget - pocketAmount);
  const reasons = { price: 0, sessions: 0, median: 0, criterion: 0, sector: 0 };
  const universe = d.source === "followed"
    ? COMPANIES.filter(c => followedTickers().includes(c.ticker))
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
  return { candidates, reasons, workingBudget, pocketAmount, pocketPct, outOfScope, feesKnown };
}
function renderAnalysisDecision() {
  const d = ui.decision;
  const { candidates, reasons, workingBudget, pocketAmount, pocketPct, outOfScope, feesKnown } = computeMonthlyCandidates();
  return `<div class="grid-2">
    <article class="card"><p class="eyebrow">Automatique · vos critères visibles</p><h2>Préparer le versement du mois</h2>
      <div class="notice green" style="margin:12px 0"><p><strong>En clair :</strong> changez un montant ou un filtre et SIGMA recalcule immédiatement le nombre de titres possibles. Il n’y a aucun bouton « Recalculer » à chercher. Le résultat reste une liste à lire, pas un ordre.</p></div>
      <form id="decisionForm" class="form-grid">
        <label class="wide">Périmètre d'examen<select name="source">
          <option value="radar" ${d.source === "radar" ? "selected" : ""}>Sociétés éligibles au Radar SIGMA (sélection automatique par règles)</option>
          <option value="followed" ${d.source === "followed" ? "selected" : ""}>Mon périmètre suivi (auto Radar + épingles + positions)</option>
          <option value="all" ${d.source === "all" ? "selected" : ""}>Toutes les sociétés cotées</option>
        </select><span class="field-hint">Le périmètre Radar (${computeRadar().scored.length} éligible(s) aujourd’hui) applique déjà échangeabilité, ${termButton("PER")} publié et dividende documenté. « Mon périmètre suivi » ajoute vos positions et épingles, sans les confondre avec la sélection automatique.</span></label>
        <label>Budget disponible (FCFA)<input name="budget" type="number" min="0" step="1000" value="${escapeHtml(d.budget)}" required></label>
        <label>Secteur (optionnel)<select name="sector"><option value="">Tous</option>${sectorList().map(s => `<option value="${escapeHtml(s)}" ${s === d.sector ? "selected" : ""}>${escapeHtml(s)}</option>`).join("")}</select></label>
        <label>${termButton("Séance", "Séances échangées")} minimum / 20<input name="minSessions" type="number" min="0" max="20" value="${escapeHtml(d.minSessions)}"></label>
        <label>${termButton("Valeur médiane")} minimum / séance (optionnel)<input name="minMedianValue" type="number" min="0" step="100000" value="${escapeHtml(d.minMedianValue)}" placeholder="Ex. 1 000 000"></label>
        <label class="wide">Ordre d’examen (descriptif)<select name="criterion">
          <option value="liquidity" ${d.criterion === "liquidity" ? "selected" : ""}>Liquidité médiane, décroissante (défaut prudent)</option>
          <option value="yield" ${d.criterion === "yield" ? "selected" : ""}>Rendement net BOC récent et non extrême, décroissant</option>
          <option value="per" ${d.criterion === "per" ? "selected" : ""}>PER publié au BOC, croissant</option>
        </select><span class="field-hint">Cet ordre sert à choisir quoi lire, pas quoi acheter automatiquement. ${termButton("Liquidité")} = facilité d’échange · ${termButton("Rendement net")} = dividende/cours publié · ${termButton("PER")} = prix rapporté au bénéfice. Le filtre rendement écarte les rendements supérieurs à 15 % ou fondés sur un dernier dividende BOC de plus de 18 mois.</span></label>
        <p class="wide small"><span class="pill green">Recalcul automatique actif</span> <span class="muted">La sélection se met à jour à chaque modification.</span></p><div class="form-actions wide"><button class="button button-secondary" type="button" data-view-link="parametres">Paramétrer les frais SGI</button></div>
      </form>
      <div class="${feesKnown ? "notice green" : "notice"} section-space"><p>${feesKnown ? `Frais estimés avec vos paramètres : ${escapeHtml(personal.settings.sgiName || "SGI")} · ${termButton("Courtage", "courtage")}  ${fmtNum(Number(personal.settings.feePct), 3)} % + ${fmtFCFA(Number(personal.settings.fixedFee))}.` : "<strong>Frais non estimés.</strong> Renseignez le courtage et le minimum de votre SGI dans Paramètres ; SIGMA n’invente aucun tarif."}</p></div>
    </article>
    <article class="card"><p class="eyebrow">Transparence du filtre</p><h2>Pourquoi les autres n’apparaissent pas</h2>
      <ul class="list-clean">
        <li class="event-row"><span>Hors périmètre choisi (${d.source === "radar" ? "non éligibles au Radar" : d.source === "followed" ? "absentes du périmètre suivi automatique/personnel" : "—"})</span><strong>${outOfScope}</strong></li>
        <li class="event-row"><span>Prix unitaire supérieur au budget ou aucun titre achetable après frais connus</span><strong>${reasons.price}</strong></li>
        <li class="event-row"><span>Moins de ${fmtNum(Number(d.minSessions || 0))} séances échangées sur 20</span><strong>${reasons.sessions}</strong></li>
        <li class="event-row"><span>${termButton("Liquidité", "Liquidité médiane")} sous votre seuil</span><strong>${reasons.median}</strong></li>
        <li class="event-row"><span>Critère BOC absent, rendement extrême/ancien écarté, ou ${termButton("PER")} non utilisable</span><strong>${reasons.criterion}</strong></li>
        <li class="event-row"><span>Hors secteur choisi</span><strong>${reasons.sector}</strong></li>
      </ul>
      <p class="source-line">Les fondamentaux restent conditionnels : seuls les piliers dont la série officielle est suffisante sont publiés en fiche. Cette sélection ne remplace jamais la lecture des rapports ni la relecture du brouillon de ${termButton("Thèse", "thèse")} préparé automatiquement.</p>
    </article>
  </div>
  <article class="card section-space"><p class="eyebrow">Sélection à examiner — pas un classement d’achat</p><h2>${candidates.length} société(s) à examiner avec ${fmtFCFA(workingBudget)}${pocketPct ? ` <span class="pill">Objectif ${personal.profile?.horizon === "moyen" ? "moyen" : "long"} terme · ${fmtFCFA(pocketAmount)} réservés à la ${termButton("Poche d'apprentissage", "poche d'apprentissage")} (${fmtNum(pocketPct)} %) — argent réel séparé, pas simulation</span>` : ""}</h2>
    ${candidates.length ? `<div class="table-wrap"><table><thead><tr><th>Société</th><th class="num">Cours utilisé</th><th class="num">Titres possibles</th><th class="num">Investi</th><th class="num">Frais ${termButton("SGI")}</th><th class="num">Reste</th><th class="num">${termButton("PER")} / ${termButton("Rendement net", "Rdt")} BOC</th><th></th></tr></thead><tbody>
      ${candidates.map(({ company, price, affordable }) => `<tr><td><div class="ticker">${company.ticker}</div><div class="subtext">${escapeHtml(company.name)} · ${escapeHtml(company.sector)}</div><div class="subtext">${termButton("Liquidité", "Liquidité méd.")} ${fmtCompactFCFA(company.history_stats?.median_traded_value_last_20_fcfa)} · ${fmtNum(company.history_stats?.traded_sessions_last_20)}/20 séances</div>${trackingBadges(company.ticker)}</td>
        <td class="num">${fmtFCFA(price)}</td><td class="num strong">${fmtNum(affordable.shares)}</td><td class="num">${fmtFCFA(affordable.invested)}</td><td class="num">${affordable.feesKnown ? fmtFCFA(Math.round(affordable.fees)) : "Non estimés"}</td><td class="num">${fmtFCFA(Math.round(affordable.remainder))}</td><td class="num">${fmtRatio(company.latest_boc?.per)} · ${fmtPct(company.latest_boc?.net_dividend_yield_pct, 2, false)}${ratioWarning(company)}</td>
        <td><div style="display:flex;gap:6px;flex-wrap:wrap"><button type="button" class="button button-secondary button-small" data-open-company="${company.ticker}">Fiche</button><button type="button" class="button button-small" data-journal-for="${company.ticker}">Brouillon de thèse</button><button type="button" class="button button-simulation button-small" data-simulate-decision="${company.ticker}" data-simulate-qty="${affordable.shares}">◆ Simuler ${fmtNum(affordable.shares)} titres</button></div></td></tr>`).join("")}
    </tbody></table></div>` : '<div class="Empty-state">Aucune société ne passe ces filtres. Élargissez un critère plutôt que de forcer une conclusion.</div>'}
    <p class="source-line">Cours : dernier instantané officiel disponible. Le nombre de titres est un calcul de préparation ; l’ordre réel, s’il a lieu, se passe chez votre SGI après relecture des sources. <strong style="color:#5b21b6">Le bouton violet crée seulement une simulation ; il ne transmet aucun ordre.</strong></p>
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
  return `<article class="card"><p class="eyebrow">Checklist avant émotion</p><h2>Baisses à examiner — seuils ${fmtPct(t5)} / 5 ${termButton("Séance", "séances")} et ${fmtPct(t20)} / 20 séances</h2>
  <div class="notice green" style="margin-top:12px"><p><strong>En clair :</strong> SIGMA cherche automatiquement si la baisse peut venir d’un ${termButton("Dividende")} détaché (${termButton("Ex-dividende", "date ex-dividende")}), de l’ensemble du marché ou du secteur. Si aucune piste ne ressort, la cause reste inconnue. Le bouton ci-dessous ouvre une checklist déjà remplie avec ces faits ; vous n’avez pas une page blanche à rédiger.</p></div>
  ${personal.profile?.riskReaction ? `<div class="notice" style="margin-top:12px"><p><strong>Votre règle déclarée au préréglage :</strong> ${escapeHtml(RISK_REACTION_LABELS[personal.profile.riskReaction] || "")}. SIGMA vous la rappelle ici pour que la décision du jour ressemble à celle que vous aviez choisie à froid.</p></div>` : ""}
  ${rows.length ? `<div class="stack" style="margin-top:14px">${rows.map(company => {
    const horizon = isNum(company.history_stats.performance_20_sessions_pct) && company.history_stats.performance_20_sessions_pct <= t20 ? 20 : 5;
    const causes = declineCauses(company, horizon);
    return `<section class="card" style="background:#fff"><div class="event-row"><div><div class="ticker">${company.ticker} · ${escapeHtml(company.name)}</div><div class="subtext">${escapeHtml(company.sector)} · BOC jusqu’au ${fmtDate(latestBocDate())}</div></div><div>${variationPill(company.history_stats.performance_5_sessions_pct)} ${variationPill(company.history_stats.performance_20_sessions_pct)}</div></div>
      <p style="margin:10px 0"><strong>Pistes à vérifier :</strong> ${causes.map(escapeHtml).join(" · ")}</p>
      <div class="form-actions"><button type="button" class="button button-secondary button-small" data-open-company="${company.ticker}">Relire la fiche</button><button type="button" class="button button-small" data-journal-for="${company.ticker}" data-journal-type="Checklist baisse">Checklist préremplie</button></div></section>`;
  }).join("")}</div>` : '<div class="Empty-state">Aucune valeur ne franchit vos seuils sur les BOC actuellement lus.</div>'}
  </article>`;
}
function renderAnalysisContext() {
  const events = [...personal.contextEvents].sort((a, b) => String(b.date).localeCompare(String(a.date)));
  const macro = DATA.macro_context || {};
  const cpm = macro.bceao_cpm || {};
  const umoa = macro.umoa_summary || {};
  const contextSummary = plainSummary("Le contexte officiel est déjà collecté pour vous", [
    `<strong>Automatique d’abord :</strong> les cartes ci-dessous viennent de la BCEAO et d’${termButton("UMOA-Titres")} à chaque collecte. Vous n’avez pas de veille macro à recopier.`,
    isNum(cpm.policy_rate_pct)
      ? `<strong>Argent dans l’Union :</strong> ${termButton("Taux directeur")} à ${fmtPct(cpm.policy_rate_pct, 2, false)} (communiqué ${termButton("CPM")} du ${fmtDate(cpm.meeting_date || cpm.published_date)}). C’est un contexte pour relire les banques et le crédit, pas un signal sur une action.`
      : "<strong>Argent dans l’Union :</strong> aucun communiqué CPM exploitable n’est présent dans cette collecte ; SIGMA ne projette aucun taux.",
    umoa.next_operation
      ? `<strong>Prochaine émission publique connue :</strong> ${escapeHtml(umoa.next_operation.issuer_country)} le ${fmtDate(umoa.next_operation.operation_date)} (${termButton("Montant annoncé", "montant annoncé")} ${fmtCompactFCFA(umoa.next_operation.amount_fcfa)}).`
      : "<strong>Émissions publiques :</strong> aucune opération future datée dans la collecte UMOA-Titres.",
    "<strong>Votre intervention est optionnelle :</strong> ajoutez seulement une hypothèse personnelle reliant un fait daté à une société. Cette note ne change aucun cours, score ou portefeuille."
  ]);
  return `<div>
    ${contextSummary}
    <div class="section-space">${macroCalendarCard({ compact: false })}</div>
  <div class="grid-2 section-space">
    <article class="card"><p class="eyebrow">Optionnel · mémoire personnelle locale</p><h2>Ajouter seulement une hypothèse que SIGMA ne Peut connaître</h2>
      <p class="muted">Les faits BCEAO et UMOA-Titres sont déjà collectés automatiquement ci-dessus. Ce formulaire sert uniquement à relier un autre fait daté à une société : vous écrivez le canal envisagé et ce qui l’invaliderait. <span class="pill personal">Note personnelle — aucun score, cours ou portefeuille modifié</span></p>
      <form id="contextForm" class="form-grid">
        <label>Date du fait<input name="date" type="date" required value="${new Date().toISOString().slice(0, 10)}"></label>
        <label>Stade ${termButton("Maturité M0–M5", "de maturité")}<select name="stage"><option>M0 — Rumeur / presse seule</option><option selected>M1 — Annonce officielle</option><option>M2 — Financement engagé</option><option>M3 — Mise en œuvre</option><option>M4 — Effet économique visible</option><option>M5 — Effet dans les résultats</option></select></label>
        <label class="wide">Fait daté<input name="title" required placeholder="Ex. Convention de financement signée pour…"></label>
        <label class="wide">Source primaire (URL)<input name="sourceUrl" type="url" required placeholder="https://…"></label>
        <label class="wide">Tickers potentiellement exposés<input name="tickers" placeholder="Ex. SMBC, BOAC — séparés par des virgules"><span class="field-hint">À documenter dans les rapports annuels ; SIGMA ne déduit pas l’exposition du seul secteur.</span></label>
        <label class="wide">Chaîne de transmission envisagée<textarea name="transmission" required placeholder="Fait → effet intermédiaire → grandeur observable chez la société"></textarea></label>
        <label>Indicateurs à vérifier<textarea name="indicators" required placeholder="Volumes, créances, dépôts, marges…"></textarea></label>
        <label>Ce qui invaliderait<textarea name="invalidation" required placeholder="Fait observable qui contredirait cette lecture"></textarea></label>
        <div class="form-actions wide"><button class="button" type="submit">Enregistrer l’événement</button></div>
      </form>
    </article>
    <article class="card"><p class="eyebrow">Registre personnel · local</p><h2>Vos hypothèses en surveillance</h2><p class="source-line">Ces cartes sont votre mémoire personnelle. Elles ne sont ni des données officielles ni des positions réelles ou simulées.</p>
      ${events.length ? `<div class="stack">${events.map(event => `<section class="card" style="box-shadow:none"><div class="event-row"><div><div class="strong">${escapeHtml(event.title)}</div><div class="subtext">${fmtDate(event.date)} · ${escapeHtml(event.stage)} · <span class="pill personal">Note personnelle locale</span></div></div><button type="button" class="icon-button" data-delete-context="${event.id}" aria-label="Supprimer">×</button></div>
        <p><strong>Chaîne :</strong> ${escapeHtml(event.transmission)}</p><p><strong>À vérifier :</strong> ${escapeHtml(event.indicators)}</p><p><strong>Invalidation :</strong> ${escapeHtml(event.invalidation)}</p>
        <p class="small">Tickers notés : ${event.tickers.length ? event.tickers.map(t => `<button type="button" class="text-button ticker" data-open-company="${t}">${t}</button>`).join(" · ") : "aucun"}<br><a href="${escapeHtml(event.sourceUrl)}" target="_blank" rel="noopener">Ouvrir la source primaire</a></p></section>`).join("")}</div>` : '<div class="Empty-state">Aucune hypothèse personnelle enregistrée — et ce n’est pas un manque : le contexte officiel BCEAO/UMOA ci-dessus est déjà suivi automatiquement.</div>'}
      <div class="notice section-space"><p><strong>Règle SIGMA :</strong> un événement ${termButton("Maturité M0–M5", "M1")} se surveille ; il ne modifie aucun score et ne produit aucun libellé d’achat. On conclut lorsque les effets deviennent observables (M4–M5).</p></div>
    </article>
  </div></div>`;
}
function renderDecision() {
  const host = $("#analysisContent");
  if (!host || !DATA) return;
  // Anciens onglets séparés « indicateurs » et « liquidité » fusionnés en
  // « Marché en chiffres » ; « rapports » devient « documents ».
  if (ui.analysisTab === "indicateurs" || ui.analysisTab === "liquidite") ui.analysisTab = "chiffres";
  if (!["decision", "radar", "baisses", "contexte", "chiffres", "documents"].includes(ui.analysisTab)) ui.analysisTab = "decision";
  $$("[data-decision-tab]").forEach(tab => tab.classList.toggle("is-active", tab.dataset.decisionTab === ui.analysisTab));
  const documentsHost = $("#decisionDocuments");
  if (ui.analysisTab === "documents") {
    host.innerHTML = "";
    if (documentsHost) documentsHost.hidden = false;
    renderReports();
    return;
  }
  if (documentsHost) documentsHost.hidden = true;
  host.innerHTML = ui.analysisTab === "radar" ? renderAnalysisRadar()
    : ui.analysisTab === "baisses" ? renderAnalysisDeclines()
    : ui.analysisTab === "contexte" ? renderAnalysisContext()
    : ui.analysisTab === "chiffres" ? renderAnalysisIndicators() + renderAnalysisLiquidity()
    : renderAnalysisDecision();
  const decisionForm = $("#decisionForm");
  if (decisionForm) {
    const syncDecision = () => {
      const active = document.activeElement;
      const activeName = active?.name || "";
      const selectionStart = typeof active?.selectionStart === "number" ? active.selectionStart : null;
      const form = new FormData(decisionForm);
      ui.decision = {
        budget: Number(form.get("budget")) || 0,
        source: String(form.get("source") || "radar"),
        sector: String(form.get("sector") || ""),
        minSessions: Number(form.get("minSessions")) || 0,
        minMedianValue: form.get("minMedianValue") === "" ? "" : Number(form.get("minMedianValue")),
        criterion: String(form.get("criterion") || "liquidity")
      };
      renderDecision();
      if (activeName) {
        const next = $("#decisionForm")?.elements?.namedItem(activeName);
        if (next) {
          next.focus({ preventScroll: true });
          if (selectionStart !== null && typeof next.setSelectionRange === "function") {
            try { next.setSelectionRange(selectionStart, selectionStart); } catch (_) { /* les champs number/select ne gèrent pas toujours le curseur */ }
          }
        }
      }
    };
    decisionForm.addEventListener("submit", event => event.preventDefault());
    decisionForm.addEventListener("input", syncDecision);
    decisionForm.addEventListener("change", syncDecision);
  }
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
    savePersonal(); renderDecision(); showToast("Événement de contexte enregistré dans votre registre local.");
  });
}

function tickerOptions(selected = "") {
  return COMPANIES.map(c => `<option value="${c.ticker}" ${c.ticker === selected ? "selected" : ""}>${c.ticker} — ${escapeHtml(c.name)}</option>`).join("");
}
function transactionDefaults(kind, ticker, type = "achat", qty = 1) {
  const company = BY_TICKER.get(ticker);
  if (!company) return { price: "", fees: 0, feesKnown: false, priceLabel: "Cours publié non disponible" };
  const priceInfo = latestPrice(company);
  const price = isNum(priceInfo.value) ? priceInfo.value : "";
  const quantity = Math.max(1, Math.floor(Number(qty) || 1));
  const feePct = personal.settings.feePct === "" ? null : Number(personal.settings.feePct);
  const fixedFee = personal.settings.fixedFee === "" ? null : Number(personal.settings.fixedFee);
  const feesKnown = type !== "dividende" && isNum(price) && feePct !== null && fixedFee !== null && !Number.isNaN(feePct) && !Number.isNaN(fixedFee);
  return {
    price,
    fees: feesKnown ? Math.round(fixedFee + quantity * price * feePct / 100) : 0,
    feesKnown,
    priceLabel: isNum(price)
      ? `Dernier cours publié (${priceInfo.label}) — à corriger avec l’avis d’opéré pour le réel`
      : "Cours publié non disponible"
  };
}
function suggestedTransactionPrefill(prefill, kind) {
  const ticker = prefill?.ticker || COMPANIES[0]?.ticker || "";
  const type = prefill?.type || "achat";
  const qty = Math.max(1, Math.floor(Number(prefill?.qty) || 1));
  const defaults = transactionDefaults(kind, ticker, type, qty);
  return {
    ticker, type, qty,
    date: prefill?.date || new Date().toISOString().slice(0, 10),
    price: isNum(Number(prefill?.price)) && Number(prefill.price) > 0 ? Number(prefill.price) : defaults.price,
    fees: isNum(Number(prefill?.fees)) && prefill?.fees !== "" ? Number(prefill.fees) : defaults.fees,
    feesKnown: defaults.feesKnown,
    priceLabel: defaults.priceLabel,
    source: prefill?.source || "Préparation automatique au dernier cours publié"
  };
}
function renderPortfolio() {
  const host = $("#portfolioContent");
  if (!host) return;
  const kind = ui.portfolioKind;
  const result = computePortfolio(kind);
  const journal = [...personal.journal].sort((a, b) => String(b.date).localeCompare(String(a.date)) || String(b.createdAt).localeCompare(String(a.createdAt)));
  const prefill = ui.journalPrefill || {};
  const txPrefill = suggestedTransactionPrefill(ui.transactionPrefill, kind);
  const today = new Date().toISOString().slice(0, 10);
  const allocationMap = new Map();
  result.holdings.forEach(h => {
    const sector = h.company?.sector || "Non renseigné";
    allocationMap.set(sector, (allocationMap.get(sector) || 0) + (h.marketValue || 0));
  });
  const allocations = [...allocationMap.entries()].sort((a, b) => b[1] - a[1]);

  host.innerHTML = `
  <div class="${kind === "virtuel" ? "portfolio-simulation" : ""}">
    <div style="display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:16px">
      <div class="segmented" role="tablist" aria-label="Type de portefeuille">
        <button type="button" data-portfolio-kind="reel" class="${kind === "reel" ? "is-active" : ""}">● Réel — avis d’opéré SGI</button>
        <button type="button" data-portfolio-kind="virtuel" class="${kind === "virtuel" ? "is-active" : ""}">◆ Simulation — aucun argent réel</button>
      </div>
      ${modePill(kind)}
    </div>
    ${modeBanner(kind)}
    ${result.warnings.length ? `<div class="notice" style="margin-bottom:16px">${result.warnings.map(w => `<p>${escapeHtml(w)}</p>`).join("")}</div>` : ""}
    <div class="grid-4">
      <article class="card kpi-card"><span class="kpi-label">Valeur au dernier cours ${kind === "virtuel" ? "· SIMULÉE" : "· estimée"}</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(result.marketValue)}</div><div class="kpi-sub muted">${kind === "virtuel" ? "Argent fictif valorisé aux cours officiels, hors frais de revente" : "Instantané BRVM, hors frais de revente"}</div></div></article>
      <article class="card kpi-card"><span class="kpi-label">${kind === "virtuel" ? "Flux fictif simulé" : "Flux net investi déclaré"}</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(result.netContributions)}</div><div class="kpi-sub muted">Achats + frais − ventes nettes</div></div></article>
      <article class="card kpi-card"><span class="kpi-label">${termButton("Dividende", "Dividendes")} saisis${kind === "virtuel" ? " en simulation" : ""}</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(result.dividendsCash)}</div><div class="kpi-sub muted">${kind === "virtuel" ? "Montants fictifs que vous avez choisis d’ajouter" : "Montants nets que vous avez enregistrés ; SIGMA ne les devine pas"}</div></div></article>
      <article class="card kpi-card"><span class="kpi-label">${termButton("Résultat réalisé")} des ventes${kind === "virtuel" ? " simulées" : ""}</span><div><div class="kpi-value" style="font-size:27px">${fmtCompactFCFA(Math.round(result.realised))}</div><div class="kpi-sub muted">Au ${termButton("PRU", "prix de revient moyen")}, frais saisis inclus</div></div></article>
    </div>

    <div class="grid-2 section-space">
      <article class="card"><p class="eyebrow">Positions ${kind === "reel" ? "réelles déclarées" : "simulées · violet"}</p><h2>${kind === "virtuel" ? "Lignes fictives suivies aux cours officiels" : "Lignes détenues selon vos enregistrements"}</h2>
        ${result.holdings.length ? `<div class="table-wrap"><table><thead><tr><th>Société</th><th class="num">Qté</th><th class="num">${termButton("PRU")}</th><th class="num">Cours officiel</th><th class="num">Valeur${kind === "virtuel" ? " fictive" : ""}</th><th class="num">${termButton("Plus ou moins-value latente", "Latent")}</th><th class="num">Poids</th></tr></thead><tbody>
          ${result.holdings.map(h => `<tr class="clickable-row" data-open-company="${h.ticker}"><td><div class="ticker">${h.ticker}</div><div class="subtext">${escapeHtml(h.company?.name || "Ticker inconnu des données actuelles")}</div></td><td class="num">${fmtNum(h.qty)}</td><td class="num">${fmtFCFA(Math.round(h.avgCost || 0))}</td><td class="num">${fmtFCFA(h.price)}</td><td class="num strong">${fmtFCFA(h.marketValue)}</td><td class="num ${h.latent >= 0 ? "positive" : "negative"}">${fmtFCFA(Math.round(h.latent || 0))}</td><td class="num">${fmtPct(h.weightPct, 1)}</td></tr>`).join("")}
        </tbody></table></div>` : (kind === "virtuel"
          ? '<div class="Empty-state"><span class="pill simulation">◆ SIMULATION</span><br><br>Aucune ligne fictive pour le moment. Le moyen le plus rapide : ouvrir le Radar ou une fiche et cliquer sur le bouton violet « Simuler » — quantité, cours publié et frais connus sont déjà préparés.<br><button type="button" class="button button-simulation button-small" data-decision-link="radar" style="margin-top:12px">Choisir dans le Radar</button></div>'
          : '<div class="Empty-state">Aucune ligne réelle déclarée. Après une exécution chez votre SGI, préparez l’enregistrement depuis la fiche société : SIGMA remplit déjà la quantité envisagée, le dernier cours publié et les frais connus ; corrigez-les avec l’avis d’opéré.<br><button type="button" class="button button-small" data-view-link="entreprises" style="margin-top:12px">Ouvrir les fiches sociétés</button></div>')}
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
      <article class="card ${kind === "virtuel" ? "simulation-panel" : ""}"><p class="eyebrow">${kind === "virtuel" ? "Simulation · aucun ordre transmis" : "Réel · enregistrement après exécution"}</p><h2>${kind === "virtuel" ? "◆ Ajouter une transaction fictive" : "Ajouter une transaction réelle exécutée"}</h2>
        ${modePill(kind)}
        <p class="source-line" style="margin-top:9px"><strong>Préparation automatique :</strong> ${escapeHtml(txPrefill.source)}. Société, quantité, dernier cours publié et frais SGI connus sont déjà remplis ci-dessous ; vous ne corrigez que ce qui diffère ${kind === "virtuel" ? "de votre essai" : "de l’avis d’opéré"}.</p>
        <form id="transactionForm" class="form-grid">
          <label>Type<select name="type" id="txType"><option value="achat" ${txPrefill.type === "achat" ? "selected" : ""}>${kind === "virtuel" ? "Achat fictif" : "Achat exécuté"}</option><option value="vente" ${txPrefill.type === "vente" ? "selected" : ""}>${kind === "virtuel" ? "Vente fictive" : "Vente exécutée"}</option><option value="dividende" ${txPrefill.type === "dividende" ? "selected" : ""}>${kind === "virtuel" ? "Dividende fictif saisi" : "Dividende net reçu"}</option></select></label>
          <label>Date<input name="date" type="date" required value="${txPrefill.date || today}"></label>
          <label class="wide">Société<select name="ticker" id="txTicker" required>${tickerOptions(txPrefill.ticker || prefill.ticker || "")}</select></label>
          <label id="txQtyLabel">Quantité<input name="qty" id="txQty" type="number" min="0" step="1" value="${txPrefill.qty}"></label>
          <label id="txPriceLabel">Prix par action (FCFA)<input name="price" id="txPrice" type="number" min="0" step="1" value="${txPrefill.price}"><span class="field-hint" id="txPriceHint">${escapeHtml(txPrefill.priceLabel)}</span></label>
          <label id="txAmountLabel" hidden>Montant net ${kind === "virtuel" ? "fictif" : "reçu"} (FCFA)<input name="amount" type="number" min="0" step="1"><span class="field-hint">SIGMA ne devine pas un encaissement : ce montant doit venir ${kind === "virtuel" ? "de votre choix de test" : "de votre relevé SGI"}.</span></label>
          <label id="txFeesLabel">Frais ${kind === "virtuel" ? "de la simulation" : "réels de l’avis d’opéré"} (FCFA)<input name="fees" id="txFees" type="number" min="0" step="1" value="${txPrefill.fees}"><span class="field-hint" id="txFeesHint">${txPrefill.feesKnown ? "Pré-remplis depuis votre grille SGI ; corrigez si l’avis diffère." : "Grille SGI inconnue : 0 par défaut, donc résultat éventuellement surestimé."}</span></label>
          <div class="form-actions wide"><button class="button ${kind === "virtuel" ? "button-simulation" : ""}" type="submit">${kind === "virtuel" ? "◆ Ajouter à la simulation" : "Ajouter au portefeuille réel"}</button></div>
        </form>
        <p class="source-line">SIGMA ne se connecte pas à votre ${termButton("SGI")} et ne passe aucun ordre. ${kind === "virtuel" ? "Cette ligne restera violette et séparée du réel." : "N’enregistrez ici qu’une opération déjà exécutée."}</p>
      </article>
      <article class="card"><p class="eyebrow">Mémoire personnelle · ni réel ni simulation</p><h2>${ui.journalPrefill ? "Brouillon automatique à relire" : "Journal de décision"}</h2>
        <p class="source-line">${ui.journalPrefill
          ? "SIGMA a rempli les champs avec des faits datés et sourcés de la fiche. Ce texte n’est pas encore enregistré : corrigez ce qui ne correspond pas à votre lecture, puis enregistrez seulement si vous l’assumez."
          : "Le plus rapide : depuis une fiche, le Radar, Décision ou Baisses, cliquez sur « Brouillon de thèse automatique » ou « Checklist préremplie ». Vous arrivez ici avec les faits déjà remplis au lieu d’une page blanche."}</p>
        <form id="journalForm" class="form-grid">
          <label>Type<select name="type"><option ${prefill.type === "Thèse" ? "selected" : ""}>Thèse</option><option ${prefill.type === "Checklist baisse" ? "selected" : ""}>Checklist baisse</option><option>Note</option><option>Contexte</option></select></label>
          <label>Date<input name="date" type="date" required value="${today}"></label>
          <label class="wide">Société (optionnel)<select name="ticker" id="journalTicker"><option value="">Aucune / marché</option>${tickerOptions(prefill.ticker || "")}</select></label>
          <label class="wide">Titre<input name="title" id="journalTitle" required value="${escapeHtml(prefill.title || "")}" placeholder="Ex. Pourquoi j’envisage cette société ce mois-ci"></label>
          <label class="wide">${termButton("Thèse")}, faits et risques<textarea name="text" id="journalText" required placeholder="Faits sourcés, ce que j’attends, risques, horizon…">${escapeHtml(prefill.text || "")}</textarea></label>
          <label class="wide">${termButton("Invalidation", "Ce qui invaliderait cette lecture")}<textarea name="invalidation" id="journalInvalidation" placeholder="Résultat, dividende, événement ou chiffre précis à surveiller">${escapeHtml(prefill.invalidation || "")}</textarea></label>
          <div class="form-actions wide"><button type="button" class="button button-secondary" id="generateJournalDraft">Remplir automatiquement depuis la fiche</button><button class="button" type="submit">Enregistrer ce brouillon relu</button></div>
        </form>
      </article>
    </div>

    <div class="grid-2-equal section-space">
      <article class="card"><p class="eyebrow">Historique ${kind === "virtuel" ? "de simulation" : "réel déclaré"}</p><h2>${kind === "virtuel" ? "◆ Transactions fictives" : "Transactions exécutées enregistrées"}</h2>${modePill(kind)}
        ${result.transactions.length ? `<ul class="list-clean">${[...result.transactions].reverse().map(tx => `<li class="event-row"><div><div class="strong">${kind === "virtuel" ? "◆ SIMULATION · " : "RÉEL · "}${escapeHtml(tx.type)} · ${tx.ticker}</div><div class="subtext">${fmtDate(tx.date)}${tx.type === "dividende" ? ` · ${fmtFCFA(Number(tx.amount))}` : ` · ${fmtNum(Number(tx.qty))} × ${fmtFCFA(Number(tx.price))} · frais ${fmtFCFA(Number(tx.fees || 0))}`}</div></div><button type="button" class="icon-button" data-delete-transaction="${tx.id}" aria-label="Supprimer la transaction">×</button></li>`).join("")}</ul>` : (kind === "virtuel" ? '<div class="Empty-state">Aucune transaction fictive enregistrée.</div>' : '<div class="Empty-state">Aucune transaction réelle enregistrée. L’avis d’opéré SGI reste votre document de référence.</div>')}
      </article>
      <article class="card"><p class="eyebrow">Mémoire personnelle locale</p><h2>Thèses, notes et checklists</h2><p class="source-line">Le journal n’appartient ni au portefeuille réel ni à la simulation : il conserve vos raisons et vos ${termButton("Invalidation", "invalidations")}.</p>
        ${journal.length ? `<ul class="list-clean">${journal.map(item => `<li><div class="event-row"><div><div class="strong">${escapeHtml(item.title)}</div><div class="subtext">${fmtDate(item.date)} · ${escapeHtml(item.type)}${item.ticker ? ` · ${item.ticker}` : ""}</div></div><button type="button" class="icon-button" data-delete-journal="${item.id}" aria-label="Supprimer la note">×</button></div><p>${escapeHtml(item.text)}</p>${item.invalidation ? `<p class="small"><strong>Invalidation :</strong> ${escapeHtml(item.invalidation)}</p>` : ""}</li>`).join("")}</ul>` : '<div class="Empty-state">Votre journal est vide pour le moment. Depuis une fiche société, SIGMA Peut Préremplir le premier brouillon avec des faits datés ; vous n’avez qu’à le relire et le corriger.</div>'}
      </article>
    </div>
  </div>`;

  $$("[data-portfolio-kind]").forEach(button => button.addEventListener("click", () => {
    ui.portfolioKind = button.dataset.portfolioKind;
    ui.transactionPrefill = null;
    renderPortfolio(); renderHome(); updateAlertBadge();
  }));
  const txType = $("#txType");
  const txTicker = $("#txTicker");
  const txQty = $("#txQty");
  const txPrice = $("#txPrice");
  const txFees = $("#txFees");
  const refreshTxDefaults = () => {
    const defaults = transactionDefaults(kind, txTicker.value, txType.value, Number(txQty.value) || 1);
    txPrice.value = defaults.price;
    txFees.value = defaults.fees;
    $("#txPriceHint").textContent = defaults.priceLabel;
    $("#txFeesHint").textContent = defaults.feesKnown
      ? "Pré-remplis depuis votre grille SGI ; corrigez si l’avis diffère."
      : "Grille SGI inconnue : 0 par défaut, donc résultat éventuellement surestimé.";
  };
  const refreshTxFeesOnly = () => {
    const defaults = transactionDefaults(kind, txTicker.value, txType.value, Number(txQty.value) || 1);
    const currentPrice = Number(txPrice.value);
    if (defaults.feesKnown && isNum(currentPrice) && currentPrice > 0) {
      const feePct = Number(personal.settings.feePct);
      const fixedFee = Number(personal.settings.fixedFee);
      txFees.value = Math.round(fixedFee + Math.max(0, Number(txQty.value) || 0) * currentPrice * feePct / 100);
    }
  };
  const syncTxType = () => {
    const isDividend = txType.value === "dividende";
    $("#txQtyLabel").hidden = isDividend; $("#txPriceLabel").hidden = isDividend; $("#txFeesLabel").hidden = isDividend;
    $("#txAmountLabel").hidden = !isDividend;
  };
  txType.addEventListener("change", () => { syncTxType(); refreshTxFeesOnly(); });
  txTicker.addEventListener("change", refreshTxDefaults);
  txQty.addEventListener("input", refreshTxFeesOnly);
  syncTxType();

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
    ui.transactionPrefill = null;
    savePersonal(); renderDynamic(); showView("portefeuille");
    showToast(kind === "virtuel"
      ? `◆ Simulation : transaction fictive ${type} ${tx.ticker} enregistrée. Aucun argent réel, aucun ordre transmis.`
      : `Réel : transaction ${type} ${tx.ticker} enregistrée dans votre registre local.`, kind === "virtuel" ? "simulation" : "");
  });
  $("#generateJournalDraft")?.addEventListener("click", () => {
    const ticker = $("#journalTicker")?.value;
    const journalForm = $("#journalForm");
    const chosenType = new FormData(journalForm).get("type") === "Checklist baisse" ? "Checklist baisse" : "Thèse";
    const draft = automaticJournalDraft(BY_TICKER.get(ticker), chosenType);
    if (!draft) { showToast("Choisissez une société pour générer un brouillon automatique."); return; }
    $("#journalTitle").value = draft.title;
    $("#journalText").value = draft.text;
    $("#journalInvalidation").value = draft.invalidation;
    $("#journalText").focus();
    showToast("Brouillon rempli automatiquement : relisez et corrigez avant de l’enregistrer.");
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
  const alertsIntro = plainSummary("SIGMA surveille pour vous ; vous n’avez pas à chercher ligne par ligne", [
    `<strong>Périmètre automatique :</strong> positions réelles, positions simulées et épingles personnelles${personal.settings.autoFollowRadar === false ? "" : ", plus la sélection courante du Radar"}. La raison du suivi est écrite sur chaque alerte.`,
    "<strong>Dates officielles :</strong> ex-dividendes et paiements viennent des avis BRVM ; aucune échéance n’est devinée.",
    `<strong>Couleurs :</strong> une position réelle reste en noir/vert ; une position simulée est identifiée <span class="pill simulation">◆ SIMULATION</span>. Une baisse ouvre une ${termButton("Invalidation", "checklist à vérifier")}, jamais un ordre automatique.`
  ]);
  host.innerHTML = alertsIntro + (alerts.length ? `<div class="stack section-space">${alerts.map(alert => {
    const read = personal.alertsRead.includes(alert.id);
    return `<article class="card alert-card ${read ? "is-read" : ""}"><span class="alert-icon ${alert.tone}">${alert.icon}</span>
      <div style="flex:1"><div class="event-row"><h3 style="margin:0">${escapeHtml(alert.title)}</h3><span class="pill">${fmtDate(alert.date)}</span></div>
      <p>${escapeHtml(alert.body)}</p><p class="small muted">${escapeHtml(alert.meta)}</p>
      <div class="form-actions">${alert.ticker ? `<button type="button" class="button button-secondary button-small" data-open-company="${alert.ticker}">Ouvrir la fiche</button>` : ""}${alert.url ? `<a class="button button-secondary button-small" href="${alert.url}" target="_blank" rel="noopener">Source officielle</a>` : ""}<button type="button" class="button button-small" data-mark-alert="${alert.id}">${read ? "Marquer non lu" : "Marquer lu"}</button></div></div></article>`;
  }).join("")}</div>` : '<div class="Empty-state section-space">Aucune alerte factuelle à afficher dans le périmètre surveillé automatiquement.</div>');
  updateAlertBadge();
}

function renderReports() {
  const host = $("#reportsContent");
  if (!host) return;
  const q = normalize(ui.reportSearch);
  const pages = DATA.report_pages.filter(page => !q || normalize(page.label).includes(q));
  const dividends = [...DATA.dividends].sort((a, b) => String(b.payment_date || "").localeCompare(String(a.payment_date || "")));
  const shownDividends = ui.reportsShowAllDividends ? dividends : dividends.slice(0, 60);
  const events = calendarEvents();
  const reportsSummary = plainSummary("Cette page sert à vérifier les preuves, pas à tout lire", [
    `<strong>Commencez par le calendrier :</strong> ${events.length} ${termButton("Échéance", "échéance(s)")} future(s) datée(s) par une source officielle. SIGMA n’ajoute aucune date estimée.`,
    `<strong>Pour un cours :</strong> ouvrez le ${termButton("BOC")} correspondant ; l’${termButton("Empreinte SHA-256")} identifie le fichier exact utilisé.`,
    `<strong>Pour un dividende :</strong> l’avis BRVM donne le montant net/action, la date ${termButton("Ex-dividende", "ex-dividende")} et la ${termButton("Date de paiement", "date de paiement")}. L’historique complet est paginé ici pour éviter une page interminable.`,
    `<strong>Pour une entreprise :</strong> la fiche société relie déjà ses ${termButton("États financiers")} et les chiffres extraits avec page/ligne ; cette bibliothèque sert de recoupement.`
  ]);
  host.innerHTML = `
    ${reportsSummary}

    <article class="card section-space"><div class="event-row"><div><p class="eyebrow">Échéances datées par les sources</p><h2>Calendrier d’${termButton("Échéance", "échéances")} — dividendes, titres publics, BCEAO</h2></div><span class="pill">${events.length} échéance(s)</span></div>
      ${events.length ? `<div class="table-wrap"><table><thead><tr><th>Date</th><th>Catégorie</th><th>Échéance</th><th class="num">Montant publié</th><th></th></tr></thead><tbody>
      ${events.map(event => `<tr><td class="strong">${fmtDate(event.date)}<div class="subtext">J+${event.in_days} à la collecte</div></td><td>${escapeHtml(event.category || "")}</td><td><div class="strong">${escapeHtml(event.title)}</div><div class="subtext">${escapeHtml(event.detail || "")}</div><div class="subtext">Source : ${escapeHtml(event.source_label || "")}</div></td><td class="num">${calendarEventAmount(event) || "—"}</td><td>${event.url ? `<a class="button button-secondary button-small" href="${event.url}" target="_blank" rel="noopener">Source</a>` : ""}</td></tr>`).join("")}
      </tbody></table></div>` : '<div class="Empty-state">Aucune échéance future datée par une source officielle dans cette collecte.</div>'}
      <p class="source-line">SIGMA n’ajoute pas de dates estimées : dividendes BRVM, opérations UMOA-Titres et événements BCEAO uniquement lorsqu’une source officielle publie la date.</p>
    </article>

    <article class="card section-space"><div class="event-row"><div><p class="eyebrow">Historique utilisé par SIGMA</p><h2>${termButton("BOC", "Bulletins Officiels de la Cote")}</h2></div><span class="pill">${DATA.history.sessions.length} BOC analysés</span></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Statut dans SIGMA</th><th>${termButton("Empreinte SHA-256")}</th><th></th></tr></thead><tbody>
      ${DATA.boc_documents.map(doc => `<tr><td class="strong">${fmtDate(doc.date)}</td><td>${doc.parsed ? '<span class="pill green">Lu et contrôlé</span>' : '<span class="pill">Indexé, non lu dans cette collecte</span>'}</td><td class="mono">${doc.sha256 ? `${doc.sha256.slice(0, 18)}…` : "—"}</td><td><a class="button button-secondary button-small" href="${doc.url}" target="_blank" rel="noopener">PDF officiel</a></td></tr>`).join("")}
      </tbody></table></div></article>

    <article class="card section-space"><p class="eyebrow">Tableau officiel BRVM · distributions canoniques après fusion des avis (${dividends.length}${DATA.coverage.dividend_fiscal_years_min ? `, exercices ${DATA.coverage.dividend_fiscal_years_min}–${DATA.coverage.dividend_fiscal_years_max}` : ""})</p><h2>Avis et calendrier de ${termButton("Dividende", "dividendes")}</h2><p class="source-line">Affichage : ${shownDividends.length}/${dividends.length} distribution(s), paiements les plus récents d’abord. Plusieurs avis officiels ou rectificatifs d’une même distribution ont déjà été fusionnés ; le bouton « Avis » ouvre la preuve conservée.</p>
      <div class="table-wrap"><table><thead><tr><th>Émetteur publié</th><th>${termButton("Exercice")}</th><th>${termButton("Ex-dividende")}</th><th>${termButton("Date de paiement", "Paiement")}</th><th class="num">Montant net</th><th></th></tr></thead><tbody>
      ${shownDividends.map(div => `<tr><td class="strong">${escapeHtml(div.issuer)}</td><td>${escapeHtml(div.fiscal_year)}</td><td>${fmtDate(div.ex_date)}</td><td>${fmtDate(div.payment_date)}</td><td class="num">${fmtFCFA(div.net_amount_fcfa)}</td><td>${div.notice_url ? `<a class="button button-secondary button-small" href="${div.notice_url}" target="_blank" rel="noopener">Avis</a>` : ""}</td></tr>`).join("")}
      </tbody></table></div>${dividends.length > 60 ? `<div class="form-actions" style="margin-top:12px"><button type="button" class="button button-secondary button-small" data-toggle-reports-dividends>${ui.reportsShowAllDividends ? "Réduire aux 60 plus récentes" : `Afficher les ${dividends.length} distributions`}</button></div>` : ""}</article>

    <article class="card section-space"><div class="event-row"><div><p class="eyebrow">Bibliothèque des émetteurs</p><h2>Pages de rapports sur brvm.org (${pages.length} affichée(s))</h2></div><a class="button button-secondary" href="https://www.brvm.org/fr/rapports-societes-cotees" target="_blank" rel="noopener">Index officiel</a></div>
      <p class="muted">Ces pages regroupent les rapports publiés par les émetteurs. SIGMA les indexe et en extrait automatiquement une partie des chiffres annuels sous contrôles, avec page/ligne et niveau de recoupement dans chaque fiche : activité, résultat, bilan, flux, trésorerie, dettes financières, BPA et nombres d'actions lorsqu'ils sont lisibles. Le ${termButton("Texte natif", "texte natif du PDF")} est utilisé d’abord ; l’${termButton("OCR contrôlé", "OCR contrôlé")} n’intervient qu’en repli sur un scan sans chiffre natif, avec badge de provenance et ${termButton("Confiance OCR", "confiance de reconnaissance")}. La couverture reste partielle et aucune extraction n'est présentée comme vérifiée ligne à ligne par un humain.</p>
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
  const debtCashKeys = [
    "flux_tresorerie_operationnel", "investissements_immobilisations", "dividendes_verses",
    "tresorerie_equivalents", "tresorerie_passif", "tresorerie_nette",
    "dettes_financieres", "dettes_financieres_courantes", "dettes_financieres_non_courantes"
  ];
  const debtCashFigures = allFigures.filter(([key]) => debtCashKeys.includes(key)).length;
  const companiesWithFigure = (...keys) => COMPANIES.filter(company => fundamentalSeries(company).some(entry => keys.some(key => seriesValue(entry, key) !== null))).length;
  const debtCashCompanies = cov.companies_with_cash_debt_flow ?? companiesWithFigure(...debtCashKeys);
  const operatingCashflowCompanies = cov.companies_with_operating_cashflow ?? companiesWithFigure("flux_tresorerie_operationnel");
  const epsCompanies = cov.companies_with_eps ?? companiesWithFigure("benefice_par_action");
  const shareCountCompanies = cov.companies_with_share_count ?? companiesWithFigure("nombre_actions_fin_exercice", "nombre_actions_moyen_pondere");
  const ocrFigures = cov.figures_ocr ?? allFigures.filter(([, figure]) => String(figure?.extraction_method || "").includes("ocr")).length;
  const ocrCompanies = cov.companies_with_ocr_figures ?? COMPANIES.filter(company => fundamentalOcrSummary(company).figures > 0).length;
  const ocrAttempted = cov.documents_ocr_attempted ?? COMPANIES.reduce((sum, company) => sum + fundamentalOcrSummary(company).attempted, 0);
  const ocrUsed = cov.documents_ocr_used ?? COMPANIES.reduce((sum, company) => sum + fundamentalOcrSummary(company).used, 0);
  const ocrCacheHits = cov.documents_ocr_cache_hits ?? COMPANIES.reduce((sum, company) => sum + fundamentalOcrSummary(company).cacheHits, 0);
  const capitalSupplementAttempted = cov.documents_capital_supplement_attempted ?? COMPANIES.reduce((sum, company) => sum + (company.fundamentals?.extraction_summary?.documents_capital_supplement_attempted || 0), 0);
  const capitalSupplementUsed = cov.documents_capital_supplement_used ?? COMPANIES.reduce((sum, company) => sum + (company.fundamentals?.extraction_summary?.documents_capital_supplement_used || 0), 0);
  const capitalSupplementFigures = cov.figures_capital_supplemented ?? COMPANIES.reduce((sum, company) => sum + (company.fundamentals?.extraction_summary?.figures_capital_supplemented || 0), 0);
  const payerCompanies = cov.companies_with_any_dividend_history ?? COMPANIES.filter(company => (company.dividend_history?.paid_fiscal_years_count || 0) > 0).length;
  const epsRatioCompanies = cov.companies_with_dividend_eps_ratio ?? COMPANIES.filter(company => (company.dividend_sustainability?.years_with_eps_ratio || 0) > 0).length;
  const cashCoverageCompanies = cov.companies_with_dividend_cash_coverage ?? COMPANIES.filter(company => (company.dividend_sustainability?.years_with_cash_coverage || 0) > 0).length;
  const cashCoverage3yCompanies = cov.companies_with_3y_dividend_cash_coverage ?? COMPANIES.filter(company => (company.dividend_sustainability?.years_with_cash_coverage || 0) >= 3).length;
  const cashCoverageShareOfPayers = payerCompanies ? Math.round((cashCoverageCompanies / payerCompanies) * 100) : 0;
  const sgiFeesPublished = cov.sgis_with_homologated_tariffs ?? (DATA.sgis || []).filter(sgi => (sgi.tariffs_homologated?.rates || []).length).length;
  const sgiTariffsVerified = cov.sgi_tariff_decisions_verified ?? (DATA.sgis || []).filter(sgi => sgi.tariffs_homologated?.status === "decision_verifiee").length;
  const sgiTariffShare = (cov.sgis_official_directory ?? 0) ? Math.round((sgiFeesPublished / cov.sgis_official_directory) * 100) : 0;
  const ageHours = Math.max(0, Math.round((Date.now() - new Date(DATA.generated_at).getTime()) / 36e5));
  const row = (block, measure, excellence, status, nextStep) => ({ block, measure, excellence, status, nextStep });
  const byShare = (count, excellentAt = 90, solidAt = 75, partialAt = 40) => {
    const share = pctOfCompanies(count);
    return share >= excellentAt ? "Excellent" : share >= solidAt ? "Solide" : share >= partialAt ? "Partiel" : "Insuffisant";
  };
  return [
    row("Cours, BOC et liquidité", `${cov.boc_archive_sessions ?? 0} séances archivées · performance 250 séances pour ${long250}/${totalCompanies} sociétés · prix publiés non ajustés`, "≥ 260 séances et ≥ 90 % des sociétés à 250 séances", (cov.boc_archive_sessions ?? 0) >= 260 && pctOfCompanies(long250) >= 90 ? "Excellent" : (cov.boc_archive_sessions ?? 0) >= 120 ? "Solide" : "Partiel", "Étendre l’archive au-delà d’un an et traiter les opérations sur titres/ajustements."),
    row("Documents officiels indexés", `${cov.issuer_documents_indexed ?? 0} documents · ${cov.companies_with_indexed_documents ?? 0}/${totalCompanies} sociétés`, "≥ 98 % des sociétés avec bibliothèque indexée", byShare(cov.companies_with_indexed_documents ?? 0, 98, 90, 60), "Rattacher la société sans document ou documenter son absence à la source."),
    row("Séries fondamentales", `${cov.companies_with_series_3y ?? 0}/${totalCompanies} sociétés avec ≥ 3 exercices (${pctOfCompanies(cov.companies_with_series_3y ?? 0)} %)`, "≥ 90 % des sociétés avec ≥ 3 exercices", byShare(cov.companies_with_series_3y ?? 0), "Traiter les scans et formats IFRS/SYSCOHADA encore rejetés sans abaisser les preuves d’unité, d’ordre des colonnes ni de plausibilité."),
    row("Chiffres confirmés par deux documents", `${confirmedFigures}/${allFigures.length} chiffres confirmés par deux documents (${confirmedShare} %)`, "≥ 70 % confirmés par deux documents", confirmedShare >= 70 ? "Excellent" : confirmedShare >= 50 ? "Solide" : confirmedShare >= 25 ? "Partiel" : "Insuffisant", "Augmenter la couverture documentaire par exercice et résoudre les divergences signalées."),
    row("OCR contrôlé des PDF scannés", `${ocrUsed}/${ocrAttempted} document(s) OCRisé(s) avec chiffres retenus · ${ocrFigures} chiffre(s) OCR pour ${ocrCompanies}/${totalCompanies} sociétés · ${ocrCacheHits} réutilisation(s) du cache OCR`, "Provenance et confiance de reconnaissance sur 100 % des chiffres OCR ; mêmes recoupements que le texte natif", ocrAttempted > 0 && ocrUsed > 0 ? "Solide" : "Partiel", "Étendre aux scans dont l’unité ou l’ordre des colonnes reste non prouvé ; ne jamais OCRiser un PDF dont le texte natif donne déjà des chiffres contrôlés."),
    row("Historique des dividendes (montants)", `${(DATA.dividends || []).length} distributions canoniques BRVM · exercices ${cov.dividend_fiscal_years_min ?? "—"}–${cov.dividend_fiscal_years_max ?? "—"} · ${cov.companies_with_any_dividend_history ?? 0} sociétés rattachées`, "Historique paginé complet, ≥ 40 sociétés rattachées", (cov.dividend_rows_collected ?? 0) >= 300 && (cov.companies_with_any_dividend_history ?? 0) >= 40 ? "Excellent" : (cov.dividend_rows_collected ?? 0) >= 100 ? "Solide" : "Partiel", "Surveiller les nouveaux avis, changements de nom/code et distributions exceptionnelles."),
    row("Repères dividende / BPA / flux", `${cov.dividend_sustainability_rows ?? 0} exercice(s) calculable(s) · dividende net/BPA pour ${epsRatioCompanies}/${payerCompanies} payeurs · couverture par le flux pour ${cashCoverageCompanies}/${payerCompanies} (${cashCoverageShareOfPayers} %) · ≥ 3 exercices pour ${cashCoverage3yCompanies}`, "BPA/nombre d’actions et flux recoupés pour ≥ 90 % des payeurs, plus dividende brut sourcé avant tout score", cashCoverageShareOfPayers >= 90 ? "Excellent" : cashCoverageShareOfPayers >= 60 ? "Solide" : cashCoverageShareOfPayers >= 25 ? "Partiel" : "Insuffisant", "Lire les notes capital/BPA des rapports complets, traiter les tableaux de flux scindés ou scannés, puis récupérer le dividende brut voté."),
    row("Dette, trésorerie et flux", `${debtCashFigures} chiffre(s) dans les séries · au moins un flux/trésorerie/dette pour ${debtCashCompanies}/${totalCompanies} sociétés · flux opérationnel pour ${operatingCashflowCompanies}/${totalCompanies}`, "Séries pluriannuelles recoupées pour ≥ 90 % des sociétés", byShare(debtCashCompanies), "Étendre aux tableaux SYSCOHADA/IFRS scindés en lignes ou colonnes, aux annexes dette/trésorerie et aux scans encore rejetés par les contrôles OCR."),
    row("Capital : BPA, actions, flottant", `BPA publié pour ${epsCompanies}/${totalCompanies} sociétés · nombre d’actions pour ${shareCountCompanies}/${totalCompanies} · passe capital/BPA : ${capitalSupplementFigures} donnée(s) ajoutée(s) depuis ${capitalSupplementUsed}/${capitalSupplementAttempted} document(s) complémentaire(s) recoupé(s) · flottant et capitalisation vérifiée : 0/${totalCompanies}`, "≥ 90 % des sociétés avec nombre d’actions sourcé et daté ; flottant/opérations sur titres tracés", byShare(shareCountCompanies), "Étendre la lecture des notes de capital au-delà des premiers documents annuels et collecter les avis officiels d’opérations sur titres ; ne pas déduire le flottant."),
    row("Actualités et annonces", `${cov.news_items ?? newsItems().length} éléments · ${newsSources} source(s) · ${cov.news_with_ticker ?? 0} rattaché(s)`, "Archive profonde, corps vérifiés et rattachement audité", (cov.news_items ?? 0) >= 100 && newsSources >= 4 ? "Solide" : "Partiel", "Approfondir l’archive et contrôler les rattachements groupe/filiales."),
    row("Macro BCEAO / UMOA immédiate", `CPM ${escapeHtml(cov.macro_bceao_cpm_status || "non collecté")} · ${cov.umoa_upcoming_issuances ?? 0} opérations UMOA à venir · ${cov.calendar_events ?? 0} échéances`, "Décision CPM complète + calendrier officiel à 90 jours", cov.macro_bceao_cpm_status === "collecte" && (cov.umoa_upcoming_issuances ?? 0) >= 20 ? "Solide" : "Partiel", "Ajouter historique CPM, résultats et rendements d’adjudications UMOA."),
    row("Annuaire SGI", `${cov.sgis_official_directory ?? (DATA.sgis || []).length} SGI officielles par pays`, "Annuaire officiel complet", (cov.sgis_official_directory ?? 0) >= 37 ? "Excellent" : "Partiel", "Maintenir la collecte de l’annuaire BRVM."),
    row("Tarifs SGI homologués", `plafonds AMF-UMOA relus pour ${sgiFeesPublished}/${cov.sgis_official_directory ?? 0} SGI de l'annuaire (${sgiTariffShare} %) · ${sgiTariffsVerified} décision(s) entièrement vérifiée(s) · ${cov.sgi_tariff_rates_concordant ?? 0}/${cov.sgi_tariff_rates_cross_checked ?? 0} rubrique(s) confirmée(s) par le second lecteur · ${cov.sgi_tariff_rates_divergent ?? 0} divergence(s) signalée(s) · ${cov.sgi_tariff_decisions_unmatched ?? 0} décision(s) hors annuaire listée(s) séparément`, "≥ 90 % des SGI de l'annuaire avec décision relue, vérifiée et recoupée ; plafonds toujours distingués de la grille reçue", sgiTariffShare >= 90 ? "Excellent" : sgiTariffShare >= 70 ? "Solide" : sgiTariffShare >= 40 ? "Partiel" : "Insuffisant", "Relire les décisions absentes ou illisibles sans abaisser les preuves ; aucun plafond n'est transformé en frais facturé."),
    row("Fraîcheur de la collecte affichée", `Collecte générée il y a environ ${ageHours} h`, "Collecte automatique quotidienne prouvée et datée", ageHours <= 72 ? "Solide" : "Partiel", "Activer et surveiller la collecte automatique lorsque l’hébergement sera mis en place."),
  ];
}

function renderSettings() {
  const host = $("#settingsContent");
  if (!host) return;
  const s = personal.settings;
  const settingsSummary = plainSummary("Ce que SIGMA fait seul, et les trois choses qu’il ne Peut pas inventer", [
    "<strong>Automatique :</strong> collecte officielle, Radar et suivi de sa sélection, alertes sur votre périmètre, quantités et cours publiés en préparation, brouillons de thèse/checklist et sauvegarde des réglages ci-dessous dès qu’ils changent.",
    `<strong>À fournir une fois :</strong> votre ${termButton("SGI")} et sa grille écrite. SIGMA connaît désormais les ${termButton("Plafond homologué", "plafonds officiels homologués")} par l'AMF-UMOA pour comparer, mais seul votre document dit ce que vous paierez réellement ; sans lui, SIGMA affiche « frais non estimés » plutôt qu’un chiffre fabriqué.`,
    "<strong>À confirmer seulement quand cela existe :</strong> une transaction réellement exécutée (avis d’opéré) et la relecture d’un brouillon de thèse. Tout le reste possible est déjà préparé.",
    `<span class="mode-legend"><span class="pill dark">Noir/vert : officiel ou réel déclaré</span><span class="pill simulation">◆ Violet : ${termButton("Simulation")} seulement</span><span class="pill personal">Note personnelle locale</span></span>`
  ]);
  host.innerHTML = `
    ${settingsSummary}

    <h2 style="margin:28px 0 2px">Mon profil &amp; ma SGI</h2>
    <p class="muted" style="margin:0 0 8px">Ce que SIGMA doit connaître une fois — ensuite, tout le reste est automatique.</p>
    <div class="grid-2 section-space">
      <article class="card"><p class="eyebrow">Profil d’utilisation · sauvegarde automatique</p><h2>Budget, ${termButton("SGI")} et seuils personnels</h2>
        <form id="settingsForm" class="form-grid">
          <label>Budget mensuel habituel (FCFA)<input name="monthlyBudget" type="number" min="0" step="1000" value="${escapeHtml(s.monthlyBudget)}"><span class="field-hint">Votre fourchette de travail est de 100 000 à 300 000 FCFA ; ce champ reste modifiable chaque mois dans Décision.</span></label>
          <label>Nom de votre ${termButton("SGI")}<input name="sgiName" value="${escapeHtml(s.sgiName)}" placeholder="À compléter"></label>
          <label>${termButton("Courtage")} SGI (%)<input name="feePct" type="number" min="0" step="0.001" value="${escapeHtml(s.feePct)}" placeholder="Vide = non estimé"></label>
          <label>Frais fixes / minimum par ordre (FCFA)<input name="fixedFee" type="number" min="0" step="1" value="${escapeHtml(s.fixedFee)}" placeholder="Vide = non estimé"></label>
          <label>Seuil checklist 5 ${termButton("Séance", "séances")} (%)<input name="decline5" type="number" step="0.5" value="${escapeHtml(s.decline5)}"><span class="field-hint">Exemple : −10 % déclenche une lecture, jamais un ordre.</span></label>
          <label>Seuil checklist 20 séances (%)<input name="decline20" type="number" step="0.5" value="${escapeHtml(s.decline20)}"><span class="field-hint">Exemple : −15 % sur environ un mois de Bourse.</span></label>
          <label class="checkbox-label wide"><input name="autoFollowRadar" type="checkbox" ${s.autoFollowRadar === false ? "" : "checked"}> ${termButton("Suivi automatique Radar")} : alimenter accueil, alertes et « Mes valeurs » avec la sélection courante, sans l’ajouter manuellement à mes épingles</label>
          <p class="wide small"><span class="pill green">Sauvegarde automatique</span> <span id="settingsSaved" class="muted">Toute modification est enregistrée immédiatement dans ce navigateur ; aucun bouton à chercher.</span></p>
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
          <li class="event-row"><span>${termButton("SGI")}</span><strong>${escapeHtml(personal.profile.sgiName || "Pas encore choisie")}</strong></li>
          <li class="event-row"><span>Versement mensuel visé</span><strong>${fmtFCFA(personal.profile.monthlyBudget)}</strong></li>
          <li class="event-row"><span>Objectif principal</span><strong>${personal.profile.horizon === "moyen" ? "Moyen terme (3–5 ans)" : "Long terme (10 ans)"}</strong></li>
          <li class="event-row"><span>${termButton("Poche d'apprentissage")} <span class="subtext">(argent réel séparé, pas simulation)</span></span><strong>${personal.profile.pocketEnabled ? `${fmtNum(personal.profile.pocketPct)} % du versement` : "Désactivée"}</strong></li>
          <li class="event-row"><span>Règle face à −20 %</span><strong>${escapeHtml(RISK_REACTION_LABELS[personal.profile.riskReaction] || "—")}</strong></li>
        </ul>` : '<div class="Empty-state">Préréglage non effectué : SIGMA utilise des valeurs neutres et ne connaît ni votre pays ni votre SGI.</div>'}
        <div class="form-actions" style="margin-top:12px"><button type="button" class="button" data-open-onboarding>${personal.profile ? "Modifier le préréglage" : "Lancer le préréglage"}</button></div>
      </article>
      <article class="card"><p class="eyebrow">Annuaire officiel BRVM · collecte du ${fmtDate(DATA.generated_at.slice(0, 10))}</p><h2>${termButton("SGI", "SGI agréées")} ${personal.profile?.country && personal.profile.country !== "Autre" ? `en ${escapeHtml(personal.profile.country)}` : "dans l'UEMOA"}</h2>
        ${(() => {
          const list = personal.profile?.country && personal.profile.country !== "Autre" ? sgisForCountry(personal.profile.country) : (DATA.sgis || []);
          if (!list.length) return '<div class="Empty-state">Annuaire indisponible dans la dernière collecte.</div>';
          const shown = list.slice(0, personal.profile?.country && personal.profile.country !== "Autre" ? 40 : 12);
          return `<ul class="list-clean">${shown.map(sgi => `<li class="event-row"><div><div class="strong">${escapeHtml(sgi.name)}</div><div class="subtext">${escapeHtml(sgi.country || "Pays non précisé")}${sgi.country_basis === "indicatif_telephonique_publie" ? " (déduit de l'indicatif publié)" : ""}${sgi.phone ? ` · ${escapeHtml(sgi.phone)}` : ""}${sgi.email ? ` · ${escapeHtml(sgi.email)}` : ""}</div></div>${sgi.website ? `<a class="button button-secondary button-small" href="${escapeHtml(sgi.website)}" target="_blank" rel="noopener">Site</a>` : ""}</li>`).join("")}</ul>
          ${list.length > shown.length ? `<p class="source-line">Affichage limité : ${list.length} SGI dans l'annuaire collecté. Faites le préréglage avec votre pays pour la liste ciblée.</p>` : ""}
          <p class="source-line">Tarifs : la BRVM ne les publie pas, mais les <strong>plafonds homologués par l'AMF-UMOA</strong> sont relus par SIGMA dans les décisions officielles (carte « Plafonds homologués négociables » ci-dessous). La grille écrite de votre SGI reste le document qui fait foi.</p>`;
        })()}
      </article>
    </div>

    <article class="card section-space"><p class="eyebrow">Comparer sans se faire vendre un classement</p><h2>Coût d'un ordre mensuel selon les tarifs que vous saisissez</h2>
      <p class="muted">SIGMA ne décerne pas de titre de « meilleure ${termButton("SGI")} » : il calcule le coût d'un ordre de ${fmtFCFA(personal.settings.monthlyBudget || 0)} (votre versement) avec les grilles écrites que vous recueillez. Service, application, délais et accompagnement restent à juger par vous.</p>
      <form id="sgiQuoteForm" class="form-grid">
        <label>SGI<input name="name" required placeholder="Nom de la SGI" list="sgiSuggestions"><datalist id="sgiSuggestions">${(DATA.sgis || []).map(sgi => `<option value="${escapeHtml(sgi.name)}">`).join("")}</datalist></label>
        <label>${termButton("Courtage")} (%)<input name="feePct" type="number" min="0" step="0.001" required placeholder="Ex. 0,90"></label>
        <label>Frais fixes / minimum par ordre (FCFA)<input name="fixedFee" type="number" min="0" step="1" required placeholder="Ex. 2 500"></label>
        <div class="form-actions"><button type="submit" class="button">Ajouter ce tarif daté</button></div>
      </form>
      ${personal.sgiQuotes?.length ? (() => {
        const amount = Number(personal.settings.monthlyBudget) || 0;
        const rows = personal.sgiQuotes.map(q => ({ ...q, cost: amount * (Number(q.feePct) || 0) / 100 + (Number(q.fixedFee) || 0) })).sort((a, b) => a.cost - b.cost);
        return `<div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>SGI</th><th>Tarif saisi le</th><th class="num">${termButton("Courtage")}</th><th class="num">Fixe</th><th class="num">Coût / ordre de ${fmtCompactFCFA(amount)}</th><th></th></tr></thead>
        <tbody>${rows.map((q, i) => `<tr><td class="strong">${escapeHtml(q.name)} ${i === 0 ? '<span class="pill green">Coût le plus bas sur vos chiffres</span>' : ""}</td><td>${fmtDate((q.createdAt || "").slice(0, 10))}</td><td class="num">${fmtNum(Number(q.feePct), 3)} %</td><td class="num">${fmtFCFA(Number(q.fixedFee))}</td><td class="num strong">${fmtFCFA(Math.round(q.cost))}</td><td><div style="display:flex;gap:6px;flex-wrap:wrap"><button type="button" class="button button-small" data-apply-quote="${q.id}">Appliquer à mes frais</button><button type="button" class="button button-secondary button-small" data-delete-quote="${q.id}">Retirer</button></div></td></tr>`).join("")}</tbody></table></div>
        <p class="source-line">Hors taxes et droits éventuels non inclus dans les chiffres saisis. Un tarif se périme : re-vérifiez avant d'ouvrir ou de changer de SGI.</p>`;
      })() : '<div class="Empty-state" style="margin-top:14px">Aucun tarif saisi. Demandez deux ou trois grilles écrites : la différence de coût sur 10 ans de versements mensuels est un des rares gains certains.</div>'}
    </article>

    <article class="card section-space"><p class="eyebrow">Tarifs officiels homologués · ${termButton("AMF-UMOA")}</p><h2>${termButton("Plafond homologué", "Plafonds homologués")} négociables des SGI</h2>
      ${(() => {
        const fees = DATA.market_fees_official || {};
        const statusLabels = {
          decision_verifiee: ["Décision vérifiée", "green"],
          decision_partielle: ["Décision lue · référence partiellement illisible", "amber"],
          grille_sans_decision_jointe: ["Grille sans lettre de décision jointe", "amber"],
          document_illisible: ["Document illisible", "red"]
        };
        const crossLabels = {
          concordant: ["confirmé par le second lecteur", "green"],
          partiellement_concordant: ["second lecteur partiel", "amber"],
          divergent: ["divergence à vérifier dans le PDF", "red"],
          non_recoupe: ["pas de second lecteur", ""]
        };
        const getRate = (tariffs, key) => (tariffs?.rates || []).find(rate => rate.key === key);
        const rateCell = (rate, preferForfait = false) => {
          if (!rate) return '<span class="muted">Non relu</span>';
          if (preferForfait && Array.isArray(rate.Parsed_forfait_fcfa) && rate.Parsed_forfait_fcfa.length === 1) {
            return `<span class="strong">${fmtFCFA(rate.Parsed_forfait_fcfa[0])}</span>${rate.Parsed_period ? `<div class="subtext">${escapeHtml(rate.Parsed_period)}</div>` : ""}`;
          }
          const short = String(rate.rate_text || "").length > 90 ? `${String(rate.rate_text).slice(0, 90)}…` : String(rate.rate_text || "");
          const fmtPlafondPct = (value) => String(parseFloat(Number(value).toFixed(4))).replace(".", ",");
          return `${escapeHtml(short)}${Number.isFinite(rate.Parsed_percent_max) ? `<div class="subtext">plafond lu : ${rate.Parsed_is_range && Number.isFinite(rate.Parsed_percent_min) ? `${fmtPlafondPct(rate.Parsed_percent_min)} – ` : ""}${fmtPlafondPct(rate.Parsed_percent_max)} %${rate.Parsed_period ? ` · ${escapeHtml(rate.Parsed_period)}` : ""}</div>` : ""}`;
        };
        const profileCountry = personal.profile?.country && personal.profile.country !== "Autre" ? personal.profile.country : null;
        const allSgis = DATA.sgis || [];
        const myCountryList = profileCountry ? sgisForCountry(profileCountry) : [];
        const mainList = myCountryList.length ? myCountryList : allSgis;
        const othersList = myCountryList.length ? allSgis.filter(sgi => !myCountryList.includes(sgi)) : [];
        const withTariffs = mainList.filter(sgi => sgi.tariffs_homologated);
        const withoutTariffs = mainList.filter(sgi => !sgi.tariffs_homologated);
        const othersWithTariffs = othersList.filter(sgi => sgi.tariffs_homologated);
        const othersWithoutTariffs = othersList.filter(sgi => !sgi.tariffs_homologated);
        const unmatched = DATA.sgi_tariffs_unmatched || [];
        const intro = `<div class="notice green"><p><strong>En clair :</strong> chaque ${termButton("SGI")} doit faire homologuer sa grille par l'${termButton("AMF-UMOA")} avant de l'appliquer. SIGMA relit la décision officielle (PDF) et affiche le <strong>${termButton("Plafond homologué", "plafond autorisé")}</strong> : votre SGI peut vous facturer moins — c'est négociable — jamais davantage sans nouvelle décision. Ces plafonds servent à comparer avant de demander votre grille écrite ; ils ne remplacent pas ce document et ne sont <strong>jamais utilisés comme vos frais</strong> dans les calculs. S'y ajoutent, pour tout le monde, les commissions de marché officielles (BRVM ${fmtNum(fees.brvm_commission_pct ?? 0.2, 2)} % + DC/BR ${fmtNum(fees.dcbr_commission_pct ?? 0.1, 2)} % par transaction, <a href="${escapeHtml(fees.source_url || "https://www.brvm.org/fr/node/312")}" target="_blank" rel="noopener">page BRVM relue le ${fmtDate(fees.verified_on)}</a>) ; SIGMA ne les totalise pas tant que l'assiette fiscale complète n'est pas établie.</p></div>`;
        if (!withTariffs.length && !othersWithTariffs.length) {
          return `${intro}<div class="Empty-state" style="margin-top:14px">Aucune décision tarifaire relue dans la dernière collecte pour ce périmètre. SIGMA n'affiche aucun tarif plutôt qu'un chiffre non vérifié.</div>`;
        }
        const rowFor = (sgi) => {
          const t = sgi.tariffs_homologated;
          const [statusLabel, statusClass] = statusLabels[t.status] || [t.status || "Statut inconnu", ""];
          const detailRates = (t.rates || []).map(rate => {
            const [crossLabel, crossClass] = crossLabels[rate.cross_check_status] || ["pas de second lecteur", ""];
            return `<li class="event-row"><div><div class="strong">${escapeHtml(rate.label)}</div><div>${escapeHtml(rate.rate_text || "")}</div><div class="subtext">${rate.base_text ? `Base : ${escapeHtml(rate.base_text)} · ` : ""}${rate.page ? `page ${rate.page} du PDF · ` : ""}second lecteur : <span class="pill ${crossClass}">${crossLabel}</span>${rate.cross_check_status === "divergent" && rate.index_rate_text ? `<div>Second lecteur (index Richbourse) : « ${escapeHtml(rate.index_rate_text)} » — en cas de désaccord, seul le PDF officiel fait foi.</div>` : ""}</div></div></li>`;
          }).join("");
          const indexOnly = (t.index_only_rubriques || []).length ? `<p class="subtext">Rubriques repérées par l'index mais non relues dans le PDF joint : ${(t.index_only_rubriques || []).map(item => escapeHtml(item.label)).join(" · ")}. Elles ne sont pas affichées comme des tarifs SIGMA.</p>` : "";
          return `<tr>
            <td><div class="strong">${escapeHtml(sgi.name)}</div><div class="subtext">${escapeHtml(sgi.country || "Pays non précisé")}</div><span class="pill ${statusClass}">${statusLabel}</span></td>
            <td>${t.decision_number ? `<div class="strong">N° ${escapeHtml(t.decision_number)}</div>` : t.announced_decision_number ? `<div class="muted">N° illisible dans ce PDF</div><div class="subtext">annoncé ${escapeHtml(t.announced_decision_number)} par la page officielle BRVM</div>` : '<div class="muted">N° illisible dans ce PDF</div>'}<div class="subtext">${t.decision_date ? `du ${fmtDate(t.decision_date)}` : "date illisible"}${t.authority ? ` · ${escapeHtml(t.authority)}` : ""}${t.approval_number ? ` · agrément SGI/${escapeHtml(t.approval_number)}` : ""}${t.name_check === "confirme" ? " · nom confirmé dans la décision" : t.name_check === "different_de_l_index" ? " · <strong>nom du PDF différent de l'index</strong>" : " · nom non vérifié dans le PDF"}</div></td>
            <td>${rateCell(getRate(t, "courtage_ordinaire"))}</td>
            <td>${rateCell(getRate(t, "conservation"))}</td>
            <td>${rateCell(getRate(t, "tenue_de_compte"), true)}</td>
            <td><details><summary class="strong" style="cursor:pointer">${(t.rates || []).length ? `${(t.rates || []).length} rubrique(s) relue(s)` : "Aucune rubrique relue"}</summary>${(t.rates || []).length ? `<ul class="list-clean" style="margin-top:10px;min-width:260px">${detailRates}</ul>` : '<p class="subtext" style="margin-top:10px">Le PDF relié contient la décision sans son annexe tarifaire lisible : SIGMA ne publie donc aucun plafond pour cette SGI. Demandez la grille complète par écrit.</p>'}${indexOnly}<p class="source-line"><a href="${escapeHtml(t.doc_url || "")}" target="_blank" rel="noopener">Ouvrir le PDF officiel relu</a>${t.source_node_url ? ` · <a href="${escapeHtml(t.source_node_url)}" target="_blank" rel="noopener">page de publication BRVM</a>` : ""} · découverte : ${t.discovery_source === "brvm" ? "publication BRVM" : t.discovery_source === "omaad" ? "fiche Omaad" : "index Richbourse"} · lecture : ${t.extraction_method === "ocr_controle" ? "OCR contrôlé (document scanné)" : t.extraction_method === "texte_natif+ocr_entete" ? "texte du PDF + OCR d'en-tête" : "texte du PDF"} · empreinte ${escapeHtml(t.sha256 || "—")}</p></details></td>
          </tr>`;
        };
        const tableFor = (rows) => `<div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>SGI</th><th>Décision relue</th><th>${termButton("Courtage")} ordinaire (plafond)</th><th>${termButton("Droits de garde", "Conservation")}</th><th>Tenue de compte</th><th>Détail vérifiable</th></tr></thead>
        <tbody>${rows.map(rowFor).join("")}</tbody></table></div>`;
        const withoutNote = (list) => list.length ? `<p class="source-line">Sans décision tarifaire publique retrouvée (${list.length}) : ${list.map(sgi => escapeHtml(sgi.name)).join(" · ")}. Pour ces SGI, seul un document écrit de leur part permet de connaître leurs tarifs.</p>` : "";
        return `${intro}
        ${myCountryList.length ? `<p class="source-line" style="margin-top:12px">Affichage par défaut : les SGI de <strong>votre pays (${escapeHtml(profileCountry)})</strong> selon votre préréglage. Les autres pays de l’UEMOA sont repliés plus bas — tout reste consultable.</p>` : `<p class="source-line" style="margin-top:12px">Préréglage non fait : toutes les SGI de l’annuaire sont affichées. Indiquez votre pays pour ne voir d’abord que les vôtres.</p>`}
        ${withTariffs.length ? tableFor(withTariffs) : '<div class="Empty-state" style="margin-top:14px">Aucune décision tarifaire relue pour les SGI de votre pays dans cette collecte.</div>'}
        ${withoutNote(withoutTariffs)}
        ${othersWithTariffs.length ? `<details style="margin-top:16px"><summary class="strong" style="cursor:pointer">SGI des autres pays de l’UEMOA — ${othersWithTariffs.length} avec plafonds relus</summary>${tableFor(othersWithTariffs)}${withoutNote(othersWithoutTariffs)}</details>` : ""}
        ${unmatched.length ? `<div class="notice" style="margin-top:12px"><p><strong>Décisions hors annuaire BRVM collecté (${unmatched.length}) :</strong> ${unmatched.map(item => `${escapeHtml(item.sgi_name_pdf || item.index_sgi_name)}${item.decision_number ? ` (n° ${escapeHtml(item.decision_number)})` : item.announced_decision_number ? ` (annoncé ${escapeHtml(item.announced_decision_number)})` : ""}`).join(" · ")}. Ces SGI figurent dans les décisions du régulateur mais pas dans l'annuaire BRVM relu : SIGMA les liste séparément au lieu de les fusionner avec une autre société.</p></div>` : ""}
        <p class="source-line">Découverte des PDF via les publications officielles de la BRVM (les décisions lui sont communiquées pour publication), complétées par les index Richbourse et Omaad ; chaque tarif affiché est relu par SIGMA dans le document officiel lié, jamais copié depuis la transcription d'un tiers. Lorsqu'une SGI a connu plusieurs homologations, SIGMA affiche la plus récente lisible. Un plafond ancien reste le dernier homologué connu : demandez confirmation écrite à la SGI avant d'ouvrir ou de transférer un compte.</p>`;
      })()}
    </article>

    <h2 style="margin:32px 0 2px">État des données <span class="pill">Technique</span></h2>
    <p class="muted" style="margin:0 0 8px">Pour vérifier d’où viennent les chiffres et ce qui manque encore. Rien ici n’est nécessaire à l’usage mensuel.</p>
    <details class="card section-space"><summary style="cursor:pointer"><span class="eyebrow" style="display:block">Transparence de collecte</span><strong style="font-size:19px">Manifeste des données affichées</strong></summary>
      <div class="grid-4">
        <div class="key-fact"><span class="metric-label">Collecte générée</span><div class="metric-value" style="font-size:16px">${fmtDateTime(DATA.generated_at)}</div></div>
        <div class="key-fact"><span class="metric-label">Sociétés instantané</span><div class="metric-value">${DATA.coverage.companies_in_snapshot}</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("BOC")} analysés</span><div class="metric-value">${DATA.coverage.boc_sessions}</div><div class="subtext">Archive longue : ${DATA.coverage.boc_archive_sessions ?? 0} séances (${fmtDate(DATA.coverage.boc_archive_first_date)} → ${fmtDate(DATA.coverage.boc_archive_last_date)})</div></div>
        <div class="key-fact"><span class="metric-label">Actualités collectées</span><div class="metric-value">${DATA.coverage.news_items ?? 0}</div><div class="subtext">${DATA.coverage.news_with_ticker ?? 0} rattachée(s) à une société</div></div>
        <div class="key-fact"><span class="metric-label">Séries fondamentales ≥ 3 ${termButton("Exercice", "exercices")}</span><div class="metric-value">${DATA.coverage.companies_with_series_3y ?? 0} sociétés</div><div class="subtext">${DATA.coverage.figures_confirmed_by_two_documents ?? 0} chiffre(s) ${termButton("Confirmé · 2 documents", "confirmés par deux documents")} · ${DATA.coverage.issuer_documents_indexed ?? 0} documents émetteurs indexés (${DATA.coverage.companies_with_indexed_documents ?? 0} sociétés)</div></div>
        <div class="key-fact"><span class="metric-label">${termButton("OCR contrôlé")} des scans</span><div class="metric-value">${DATA.coverage.documents_ocr_used ?? 0}/${DATA.coverage.documents_ocr_attempted ?? 0} document(s) avec chiffres</div><div class="subtext">${DATA.coverage.figures_ocr ?? 0} chiffre(s) OCR · ${DATA.coverage.companies_with_ocr_figures ?? 0} société(s) · ${DATA.coverage.documents_ocr_cache_hits ?? 0} cache(s) réutilisé(s) · ${termButton("Confiance OCR", "confiance")} affichée par ligne</div></div>
        <div class="key-fact"><span class="metric-label">Passe capital / ${termButton("Bénéfice net par action", "BPA")}</span><div class="metric-value">${DATA.coverage.figures_capital_supplemented ?? 0} donnée(s) ajoutée(s)</div><div class="subtext">${DATA.coverage.documents_capital_supplement_used ?? 0}/${DATA.coverage.documents_capital_supplement_attempted ?? 0} document(s) complémentaire(s) recoupé(s) · ${DATA.coverage.companies_with_capital_supplement ?? 0} société(s) · ${termButton("Périmètre comptable", "périmètre comptable")} comparé avant ajout</div></div>
        <div class="key-fact"><span class="metric-label">Macro &amp; ${termButton("Échéance", "échéances")}</span><div class="metric-value">${DATA.coverage.calendar_events ?? 0} échéance(s)</div><div class="subtext">${termButton("CPM")} BCEAO ${escapeHtml(DATA.coverage.macro_bceao_cpm_status || "non collecté")} · taux ${fmtPct(DATA.coverage.macro_bceao_policy_rate_pct, 2, false)} · ${DATA.coverage.umoa_upcoming_issuances ?? 0} émission(s) UMOA à venir · prochaine échéance ${fmtDate(DATA.coverage.calendar_next_date)}</div></div>
        <div class="key-fact"><span class="metric-label">Tarifs ${termButton("SGI")} homologués</span><div class="metric-value">${DATA.coverage.sgis_with_homologated_tariffs ?? 0}/${DATA.coverage.sgis_official_directory ?? 0} SGI</div><div class="subtext">${DATA.coverage.sgi_tariff_decisions_verified ?? 0} décision(s) ${termButton("AMF-UMOA")} vérifiée(s) · ${DATA.coverage.sgi_tariff_rates_extracted ?? 0} rubrique(s) relue(s) · ${DATA.coverage.sgi_tariff_rates_concordant ?? 0}/${DATA.coverage.sgi_tariff_rates_cross_checked ?? 0} confirmée(s) par le second lecteur · ${termButton("Plafond homologué", "plafonds")} négociables, jamais vos frais facturés</div></div>
        <div class="key-fact"><span class="metric-label">Historique officiel des ${termButton("Dividende", "dividendes")}</span><div class="metric-value">${(DATA.dividends || []).length} distributions</div><div class="subtext">Exercices ${DATA.coverage.dividend_fiscal_years_min ?? "—"}–${DATA.coverage.dividend_fiscal_years_max ?? "—"} · ${DATA.coverage.companies_with_any_dividend_history ?? 0} sociétés rattachées · ${DATA.coverage.companies_with_dividend_history_5y ?? 0} documentées sur les 5 derniers exercices</div></div>
      </div>
      <h3 style="margin-top:22px">État de couverture mesuré — objectif : excellent partout</h3>
      <div class="notice green" style="margin:12px 0"><p><strong>En clair :</strong> ce tableau répond à une seule question — quelles données sont assez complètes pour être utilisées, et lesquelles restent trop fragiles. Un bloc « Insuffisant » bloque les calculs qui en dépendent au lieu de les maquiller.</p></div><details><summary class="strong" style="cursor:pointer">Voir l’audit technique bloc par bloc</summary><p class="muted" style="margin-top:10px">Cet état est recalculé depuis le fichier de données affiché. « Excellent » n’est attribué que si le seuil écrit est atteint ; les blocs incomplets restent visibles avec leur prochaine correction, au lieu d’être masqués par une moyenne.</p>
      <div class="table-wrap"><table><thead><tr><th>Bloc de données</th><th>Mesure dans cette collecte</th><th>Seuil « excellent »</th><th>État</th><th>Prochaine correction</th></tr></thead>
      <tbody>${coverageAuditRows().map(item => `<tr><td class="strong">${item.block}</td><td>${item.measure}</td><td>${item.excellence}</td><td><span class="pill ${item.status === "Excellent" ? "green" : item.status === "Partiel" ? "amber" : item.status === "Insuffisant" ? "red" : ""}">${item.status}</span></td><td>${item.nextStep}</td></tr>`).join("")}</tbody></table></div></details>
      <h3 style="margin-top:20px">Sources primaires utilisées</h3>
      <ul>${DATA.sources.map(source => `<li><a href="${source.url}" target="_blank" rel="noopener">${escapeHtml(source.label)}</a></li>`).join("")}</ul>
      <h3>Avertissements qualité</h3>
      ${DATA.quality_warnings.length ? `<ul>${DATA.quality_warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}</ul>` : '<p class="positive"><strong>Aucun avertissement</strong> sur la dernière collecte publiée.</p>'}
      <div class="notice blue"><p><strong>Comprendre SIGMA.</strong> Outil personnel d’information et d’apprentissage. Il ne fournit pas de conseil financier personnalisé, ne prédit pas les cours et ne passe aucun ordre. Vérifiez toujours les documents officiels et les conditions de votre SGI avant une décision. Investir comporte un risque de perte en capital.</p></div>
    </details>
    <article class="card section-space"><p class="eyebrow">Lecture guidée</p><h2>Définitions toujours accessibles</h2>
      <p>Dans toute l’application, les termes soulignés en pointillé avec <span class="term-mark" aria-hidden="true">?</span> ouvrent leur explication sans quitter l’écran. Le bouton « Définitions » en haut ouvre le glossaire complet avec recherche (${Object.keys(GLOSSARY).length} entrées) ; il n’est donc plus nécessaire de faire défiler toutes les définitions ici.</p>
      <div class="form-actions"><button type="button" class="button" data-open-glossary>Ouvrir toutes les définitions</button></div>
    </article>`;

  const settingsForm = $("#settingsForm");
  const syncSettings = (rerender = false) => {
    const active = document.activeElement;
    const activeName = active?.name || "";
    const selectionStart = typeof active?.selectionStart === "number" ? active.selectionStart : null;
    const form = new FormData(settingsForm);
    const rawDecline5 = form.get("decline5");
    const rawDecline20 = form.get("decline20");
    personal.settings = {
      ...personal.settings,
      monthlyBudget: Number(form.get("monthlyBudget")) || 0,
      sgiName: String(form.get("sgiName") || "").trim(),
      feePct: form.get("feePct") === "" ? "" : Number(form.get("feePct")),
      fixedFee: form.get("fixedFee") === "" ? "" : Number(form.get("fixedFee")),
      decline5: rawDecline5 === "" || Number.isNaN(Number(rawDecline5)) ? personal.settings.decline5 : Number(rawDecline5),
      decline20: rawDecline20 === "" || Number.isNaN(Number(rawDecline20)) ? personal.settings.decline20 : Number(rawDecline20),
      autoFollowRadar: Boolean(settingsForm.elements.autoFollowRadar?.checked)
    };
    ui.decision.budget = personal.settings.monthlyBudget;
    savePersonal();
    if (!rerender) {
      const status = $("#settingsSaved");
      if (status) status.textContent = `Enregistré automatiquement à ${new Date().toLocaleTimeString("fr-FR")}.`;
      return;
    }
    renderDynamic(); showView("parametres");
    if (activeName) {
      const next = $("#settingsForm")?.elements?.namedItem(activeName);
      if (next) {
        next.focus({ preventScroll: true });
        if (selectionStart !== null && typeof next.setSelectionRange === "function") {
          try { next.setSelectionRange(selectionStart, selectionStart); } catch (_) { /* certains champs ne gèrent pas le curseur */ }
        }
      }
    }
  };
  settingsForm.addEventListener("submit", event => { event.preventDefault(); syncSettings(false); });
  settingsForm.addEventListener("input", () => syncSettings(false));
  settingsForm.addEventListener("change", () => syncSettings(true));
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
      personal = { ...cloneSur(DEFAULT_PERSONAL), ...parsed.personal, settings: { ...DEFAULT_PERSONAL.settings, ...(parsed.personal.settings || {}) } };
      savePersonal(); renderDynamic(); showView("parametres"); showToast("Sauvegarde personnelle importée.");
    } catch (_) { showToast("Import impossible : fichier personnel SIGMA non reconnu."); }
  });
  $("#resetData").addEventListener("click", () => {
    if (!confirm("Supprimer watchlist, portefeuilles, journal, événements et réglages enregistrés dans ce navigateur ?")) return;
    personal = cloneSur(DEFAULT_PERSONAL); ui.decision.budget = personal.settings.monthlyBudget;
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
  renderFreshness(); renderHome(); renderMarket(); renderCompanies(); renderDecision();
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
  if (["accueil", "marche", "entreprises", "decision", "analyses", "actualites", "portefeuille", "alertes", "rapports", "parametres"].includes(hash)) {
    showView(hash); return;
  }
  showView("accueil");
}

function bindStaticEvents() {
  window.addEventListener("hashchange", applyHashRoute);
  $$(".nav-item").forEach(button => button.addEventListener("click", () => showView(button.dataset.view)));
  $("#backToCompanies").addEventListener("click", () => showView("entreprises"));
  $$("[data-decision-tab]").forEach(tab => tab.addEventListener("click", () => { ui.analysisTab = tab.dataset.decisionTab; renderDecision(); }));
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
  $("#openGlossary")?.addEventListener("click", openGlossary);

  document.addEventListener("click", event => {
    const viewLink = event.target.closest("[data-view-link]");
    if (viewLink) { showView(viewLink.dataset.viewLink); return; }
    const decisionLink = event.target.closest("[data-decision-link]");
    if (decisionLink) { ui.analysisTab = decisionLink.dataset.decisionLink; renderDecision(); showView("decision"); return; }
    if (event.target.closest("[data-open-glossary]")) { openGlossary(); return; }
    const reportsToggle = event.target.closest("[data-toggle-reports-dividends]");
    if (reportsToggle) { ui.reportsShowAllDividends = !ui.reportsShowAllDividends; renderReports(); return; }
    const radarWatchAll = event.target.closest("[data-radar-watch-all]");
    if (radarWatchAll) {
      const tickers = computeRadar().selection.map(entry => entry.company.ticker);
      const added = tickers.filter(ticker => !personal.watchlist.includes(ticker));
      personal.watchlist = [...new Set([...personal.watchlist, ...tickers])].sort();
      savePersonal(); renderDynamic(); showView("decision");
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
      ui.transactionPrefill = null;
      savePersonal(); renderDynamic(); showView("portefeuille");
      showToast(`◆ SIMULATION (violet) : ${result.quantity} × ${company.ticker} à ${fmtFCFA(result.price)} (cours publié)${result.feesKnown ? "" : " · frais comptés à 0 faute de grille SGI"}. Aucun argent réel, aucun ordre passé.`, "simulation");
      return;
    }
    const simulateDecision = event.target.closest("[data-simulate-decision]");
    if (simulateDecision) {
      const company = BY_TICKER.get(simulateDecision.dataset.simulateDecision);
      const qty = Number(simulateDecision.dataset.simulateQty) || 0;
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
      ui.transactionPrefill = null;
      savePersonal(); renderDynamic(); showView("portefeuille");
      showToast(`◆ SIMULATION depuis Décision : ${result.quantity} × ${company.ticker} au cours publié${result.feesKnown ? "" : ", frais inconnus comptés à 0"}. Aucun ordre réel n’a été transmis.`, "simulation");
      return;
    }
    const prepareReal = event.target.closest("[data-prepare-real-transaction]");
    if (prepareReal) {
      const company = BY_TICKER.get(prepareReal.dataset.prepareRealTransaction);
      if (!company) return;
      const qty = Math.max(1, Math.floor(Number($("#orderQty")?.value) || 1));
      const defaults = transactionDefaults("reel", company.ticker, "achat", qty);
      ui.portfolioKind = "reel";
      ui.transactionPrefill = {
        ticker: company.ticker, type: "achat", qty,
        price: defaults.price, fees: defaults.fees,
        source: `Préparation réelle depuis la fiche ${company.ticker} : quantité envisagée et dernier cours publié déjà remplis — corrigez prix et frais avec l’avis d’opéré après exécution`
      };
      renderPortfolio(); showView("portefeuille");
      showToast("Portefeuille réel : formulaire prérempli, mais rien n’est enregistré tant que vous n’avez pas confirmé l’avis d’opéré.");
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
      const draftType = journalFor.dataset.journalType || "Thèse";
      ui.journalPrefill = automaticJournalDraft(BY_TICKER.get(ticker), draftType)
        || { ticker, type: draftType, title: `${draftType} — ${ticker}` };
      renderPortfolio(); showView("portefeuille");
      showToast("Brouillon automatique prêt : faits datés et invalidations déjà remplis. Relisez avant d’enregistrer.");
      setTimeout(() => $("#journalText")?.focus({ preventScroll: false }), 80);
      return;
    }
    const open = event.target.closest("[data-open-company]");
    if (open && !event.target.closest("a")) { showView("fiche", open.dataset.openCompany); return; }
    const term = event.target.closest("[data-term]");
    if (term) { openTerm(term.dataset.term); return; }
    const delTx = event.target.closest("[data-delete-transaction]");
    if (delTx) {
      const kind = ui.portfolioKind;
      personal.portfolios[kind].transactions = personal.portfolios[kind].transactions.filter(tx => tx.id !== delTx.dataset.deleteTransaction);
      savePersonal(); renderDynamic(); showView("portefeuille");
      showToast(kind === "virtuel" ? "◆ Transaction fictive supprimée de la simulation." : "Transaction réelle supprimée de votre registre local.", kind === "virtuel" ? "simulation" : ""); return;
    }
    const delJournal = event.target.closest("[data-delete-journal]");
    if (delJournal) {
      personal.journal = personal.journal.filter(item => item.id !== delJournal.dataset.deleteJournal);
      savePersonal(); renderDynamic(); showView("portefeuille"); return;
    }
    const delContext = event.target.closest("[data-delete-context]");
    if (delContext) {
      personal.contextEvents = personal.contextEvents.filter(item => item.id !== delContext.dataset.deleteContext);
      savePersonal(); renderDecision(); return;
    }
    const markAll = event.target.closest("[data-mark-alerts-read]");
    if (markAll) {
      personal.alertsRead = [...new Set([...personal.alertsRead, ...generateAlerts().map(a => a.id)])];
      savePersonal(); renderAlerts(); renderHome();
      showToast("Toutes les alertes du périmètre sont marquées comme lues.");
      return;
    }
    const mark = event.target.closest("[data-mark-alert]");
    if (mark) {
      const id = mark.dataset.markAlert;
      personal.alertsRead = personal.alertsRead.includes(id) ? personal.alertsRead.filter(item => item !== id) : [...personal.alertsRead, id];
      savePersonal(); renderAlerts(); renderHome();
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
    if (!personal.profile?.onboardedAt && !personal.onboardingDismissedAt) openOnboarding();
  } catch (error) {
    $("#loadingState").innerHTML = `<div class="loading-mark">Σ</div><p>Impossible de charger les données SIGMA (${escapeHtml(error.message)}).<br>Relancez la collecte officielle avant d’ouvrir l’application : aucun chiffre de remplacement ne sera inventé.</p>`;
    const message = $("#appMessage");
    message.hidden = false;
    message.textContent = "Données de marché indisponibles : SIGMA refuse d’afficher une démo ou des valeurs fabriquées.";
  }
}

document.addEventListener("DOMContentLoaded", init);

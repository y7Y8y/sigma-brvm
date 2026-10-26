# SIGMA BRVM — tout ce qui reste à construire (données incluses)

**État mesuré au 24 octobre 2026**, sur la collecte livrée du 22/10/2026 21:20 UTC. Ce document consolide et remplace toutes les anciennes listes « prochaines étapes ». Il inclut le plan signaux/valorisation du 24/10 et **le chantier données, qui est le plus lourd et conditionne presque tout le reste**.

**Légende importance** — **CRITIQUE** : bloque une promesse centrale ou touche à l'argent réel · **IMPORTANT** : change la qualité des décisions · **UTILE** : améliore sans bloquer · **PLUS TARD** : à faire quand le reste tient.
**Légende effort** — S : quelques heures · M : un bloc de travail · L : gros bloc · XL : chantier en plusieurs vagues.

---

## Objectif 48/48 — bien posé (ajout du 24/10, demande de l'utilisateur)

48 sociétés composent la cote actions lue au BOC. L'objectif n'est pas « une valeur inventée partout » mais **un statut tranché pour chaque observation société × exercice × indicateur**. Pour le périmètre 2016–2025, la grille brute compte donc **480 couples société-exercice**, avant exclusion documentée des exercices non applicables (introduction postérieure, par exemple). Un taux par société ou un taux global ne suffit pas : il Peut masquer des années entières manquantes.

### Contrat BPA — trois niveaux qui ne doivent jamais être confondus

1. **BPA publié** : valeur de base relue dans un document officiel, avec page et ligne. La confirmation par deux documents est comptée séparément.
2. **BPA recalculé comparable** : uniquement si le numérateur est le résultat attribuable aux actionnaires ordinaires — ou, à défaut d'un champ plus précis encore à extraire des notes BPA, le résultat net part du groupe explicitement lu — **et** si le dénominateur est le **nombre moyen pondéré d'actions ordinaires** du même exercice. Les intrants portent leurs preuves et leur niveau de confirmation ; un écart matériel avec un BPA publié devient un point de contrôle à expliquer.
3. **Ratio indicatif résultat/action** : résultat disponible ÷ actions en fin d'exercice. Ce n'est **pas** un BPA comptable comparable, en particulier l'année d'une augmentation de capital, d'une attribution gratuite ou d'une division du nominal. Il peut orienter une recherche, mais ne doit alimenter ni un PER présenté comme propre ni un score sans avertissement explicite.

La note BPA publiée reste la source prioritaire : lorsqu'elle donne le numérateur attribuable aux ordinaires et le nombre moyen pondéré, ces deux champs doivent être extraits comme intrants distincts. Les changements du nombre d'actions entre exercices et tout écart matériel entre nombre pondéré et nombre final créent un drapeau « structure du capital à vérifier » ; ils ne sont pas interprétés sans l'opération sur titres correspondante.

### Statuts d'absence — aucun blanc silencieux

Pour chaque observation sans valeur retenue, un seul statut principal, horodaté par l'audit :

- `NON_PUBLIE_DANS_SOURCES_VERIFIEES` : les documents listés comme effectivement examinés ne contiennent pas la valeur cherchée. Cela ne prouve **pas** qu'aucune source au monde ne la publie.
- `NON_RECHERCHE` : l'audit de cette observation n'est pas terminé ; statut par défaut tant que les documents candidats n'ont pas été examinés.
- `DOCUMENT_INTROUVABLE` : la source attendue pour cet exercice n'a pas été récupérée dans les canaux audités.
- `ILLISIBLE` : un document candidat existe et peut contenir la valeur, mais son format/scan ne permet pas une lecture qui passe les contrôles.
- `NON_APPLICABLE` : l'indicateur n'a pas de sens pour ce cas précis, avec motif explicite (par exemple exercice antérieur à l'introduction lorsque la série visée commence à la cotation).

Le statut documentaire reste séparé du statut de valeurs : un document candidat indexé n'est ni « examiné » ni « valeur absente ».

### Indicateurs de pilotage — jamais un taux global unique

La couverture 2016–2025 est suivie séparément pour : **(a)** le BPA publié extrait, **(b)** le BPA publié confirmé par deux documents, **(c)** le BPA recalculé comparable et son niveau de confirmation des intrants, **(d)** le ratio indicatif fin d'exercice (hors couverture BPA), **(e)** le statut documentaire, et **(f)** les observations encore `NON_RECHERCHE`, `DOCUMENT_INTROUVABLE`, `ILLISIBLE`, `NON_APPLICABLE`. Les dénominateurs distinguent les 480 cellules brutes, les cellules applicables après référentiel des introductions, et les exercices pour lesquels une série comptable existe déjà.

| Donnée | Valeurs aujourd'hui | Cible 48/48 réaliste |
|---|---|---|
| Cours et archive BOC | 48/48 | Acquis |
| Documents indexés | 47/48 | **48/48** : page « NSBC » de la BRVM ignorée à tort (libellé = ticker seul non reconnu) — correctif livré le 24/10 (66/66 tests), effet à la prochaine collecte ; 23 autres pages restent non rattachées (véhicules obligataires et anciens noms à vérifier un à un, jamais par devinette) |
| Série annuelle (activité, résultat, capitaux propres, bilan) | 45/48 | **48/48 statuts** : BBGC n'a que 2 PDF et aucun état annuel sur sa page BRVM (source à chercher chez l'émetteur) ; ETIT publie en USD/IFRS et en scans (voie séparée devise, jamais de conversion sans taux sourcé) ; NSBC débloquée par le correctif ci-dessus |
| Flux de trésorerie opérationnel | 23/48 | **48/48 statuts** — le trou est concentré sur les **banques** (formulaires de publication BCEAO souvent sans tableau des flux : rapports annuels complets requis) + variantes de formats chez les industrielles |
| Nombre d'actions | 4/48 | **Valeurs visées ~48/48** : fait juridique existant chez tout émetteur, publié en notes capital/AG — c'est un retard d'extraction, pas une absence de source |
| BPA, par exercice | publié : 16 observations société-exercice pour 6 sociétés | **480 statuts d'observation** : publié relu prioritaire ; recalculé comparable seulement avec numérateur attribuable aux ordinaires/part du groupe explicite et actions **moyennes pondérées** ; le ratio avec actions de fin d'exercice reste un **indicatif séparé**. Aucune cible « valeurs 48/48 » n'est promise tant que publication, applicabilité et intrants ne sont pas établis exercice par exercice |
| Historique dividendes | 44/48 documentées | **48/48 statuts** : pour les 4 restantes, trancher « aucune distribution retrouvée au tableau officiel depuis 2015 » plutôt que blanc |
| Tarifs SGI homologués | 33/37 SGI | Statuts : les 4 restantes classées « non publié retrouvé » après épuisement des pistes (1.11) |

**Conséquence directe, volontairement plus stricte** : un PER « calculé par SIGMA » ne pourra être présenté comme comparable qu'à partir d'un BPA publié ou d'un BPA recalculé comparable. Un PER bâti sur le ratio indicatif fin d'exercice devra porter ce nom et ses limites ; il ne comptera pas dans la couverture BPA vérifiée.

---

## 1 · Données — compléter ce qui manque (le lourd chantier)

| # | Chantier | État mesuré aujourd'hui | Importance · Effort | Débloque |
|---|---|---|---|---|
| 1.1 | **Bénéfice par action + nombre d'actions** | BPA vérifié : **6/48** sociétés (ABJC, CIEC, ORAC, ORGT, SCRC, SPHC) ; nombre d'actions : **4/48** (BICC, CIEC, SDSC, SGBC). La passe dédiée a tenté 78 documents complémentaires et n'a **rien retenu (0)** dans la collecte livrée. **Mini-audit du 24/10 sur documents réels — causes classées** : (a) mise en page « libellé seul, montants sur sous-ligne *de base* » (SNTS 2025 p. 20 : BPA 3 420/3 288 présents mais ignorés) → **correctif livré le 24/10** (lecture de la sous-ligne « de base », dilué jamais lu, variantes d'ordre des mots ; 66/66 tests, effet à la prochaine collecte) ; (b) données présentes mais dans d'autres types de documents que les états annuels (SGBC : nombre d'actions dans les chiffres clés ; nombre d'actions absent des états condensés SNTS 31 p.) → élargir les compléments aux rapports annuels/AG avec les mêmes contrôles de périmètre ; (c) PDF scannés d'une page (BICC, TTLC) → BPA OCR à n'admettre qu'après recoupement, jamais en lecture unique. **Matrice initiale livrée le 24/10** (`ingestion/audit_eps_2016_2025.py`, sorties `audits/bpa_2016_2025/`) : 480 cellules brutes, 233 exercices déjà extraits, BPA publié 16 observations (6,867 % des séries extraites) dont 4 confirmées par deux documents (1,717 %), aucun BPA recalculable comparable au sens strict, 1 candidat part du groupe/pondéré à vérifier, 4 ratios indicatifs fin d'exercice et 459 `NON_RECHERCHE`. Le numérateur attribuable aux actionnaires ordinaires devient un champ d'extraction distinct. Suite : audit documentaire nominatif et vagues par cause | **CRITIQUE** · XL | PER calculé par SIGMA, ancres bénéfice et patrimoniale de la fourchette, capitalisation, taux de distribution réel |
| 1.2 | **Flux de trésorerie opérationnel** | **23/48** sociétés. Couverture dividende par le flux : 2 sociétés seulement (1 sur 3 exercices) | **CRITIQUE** · L | Le test « qualité des bénéfices » (bénéfice sans trésorerie), couverture cash du dividende |
| 1.3 | **Confirmer et compléter les fondamentaux** | 45 séries, 41 ≥ 3 exercices, **352 chiffres confirmés par deux documents (~29 %)** ; sans série : BBGC, ETIT, NSBC (NSBC : même aucun document indexé — enquête page émetteur) ; OCR : 109 scans tentés, 56 exploités (300 chiffres, 24 sociétés), **53 scans sans retenue** = gisement | IMPORTANT · L en continu | La fiabilité de chaque pilier et de chaque ratio |
| 1.4 | **Résultats intermédiaires (trimestriels/semestriels)** | Documents déjà indexés (1 504, 47 émetteurs) et classés, **non extraits** — seuls les annuels alimentent les séries | IMPORTANT · L | Des signaux frais entre deux annuels ; détection plus tôt des retournements |
| 1.5 | **Opérations sur titres (divisions, attributions) + prix ajustés + rendement total** | Archive en **prix publiés non ajustés** : toutes les performances longues sont « prix seuls ». Registre d'OST à bâtir depuis les avis BRVM (avec contrôle sur les sauts de cours), puis séries ajustées et rendement dividendes inclus | IMPORTANT · L | Une mesure honnête des performances (positions, signaux v1.7) |
| 1.6 | **UMOA-Titres : résultats d'adjudications** (montants *levés* et taux par maturité) | Aujourd'hui : opérations **annoncées** seulement (31 à venir, 776 Md annoncés/30 j) ; annoncé ≠ levé | IMPORTANT · M | La référence de taux de la zone pour actualiser les scénarios ; la liquidité réelle absorbée par les États |
| 1.7 | **Historique BCEAO** | Seul le **dernier** communiqué CPM est relu (09/09/2026, 3,00 %) ; pas de série taux/inflation/croissance publiés | UTILE · M | Un contexte macro en tendance, pas en instantané |
| 1.8 | **Dividende brut et taux de distribution voté** | BRVM publie le **net** (348 distributions 2015–2025, 44 sociétés) ; le brut voté en AG n'est pas séparé — **mais le mini-audit du 24/10 prouve qu'il est publié** dans les chiffres clés de certains rapports (SGBC 2025 : « Dividende brut par action 2 606 F CFA », « Taux de distribution 80 % ») → nouvelle donnée extractible avec les mêmes contrôles, affichée à côté du net sans jamais les confondre | UTILE · M–L | Le vrai taux de distribution, la soutenabilité complète |
| 1.9 | **Flottant et structure de l'actionnariat** | Non collectés (rapports annuels, publication hétérogène) ; capitalisation bloquée par 1.1 | UTILE · L | Liquidité rapportée au flottant réel, poids dans le marché |
| 1.10 | **Événements officiels minés dans l'index « Avis et publications » BRVM** | L'index est déjà balayé pour les tarifs SGI — pas encore pour AG, OST, paiements annoncés, gouvernance. Actualités : 153 éléments, 68 rattachés à un titre (44 %) | UTILE · M | Un calendrier d'événements sociétés automatique (35 échéances aujourd'hui) |
| 1.11 | **Tarifs SGI — le reliquat** | 33/37 SGI couvertes. Restent : **4 SGI sans aucun document public retrouvé** (ORAGROUP SECURITIES, GLOBAL CAPITAL, EVEREST FINANCE, UCA — dernières pistes : registre AMF-UMOA, fiches Richbourse ; si rien n'est publié, clôturer « non publié ») ; 12 divergences second lecteur (affichées, le PDF fait foi) ; 27 décisions relues partiellement (annexes à améliorer par OCR) | PLUS TARD · M (devient IMPORTANT uniquement si *votre* SGI est l'une des 4) | La comparaison de frais ex ante pour tout l'annuaire |
| 1.12 | **Allonger l'archive BOC avant le 22/09/2025** | 262 séances (2025-09-22 → 2026-10-21), objectif atteint ; formats de BOC antérieurs non relus | PLUS TARD · XL incertain | Des cycles plus longs pour stress et mesure |

### Séquence obligatoire du chantier BPA 2016–2025

1. **Fiabiliser le référentiel des 48 sociétés et leurs alias** : identité actuelle, anciennes dénominations prouvées, page BRVM, cohérence nom/ticker ; aucune fusion d'alias par ressemblance seule. Les dates d'introduction et événements de capital sont des champs du référentiel, remplis uniquement avec preuve.
2. **Auditer les rapports disponibles pour 2016–2025** : pour chacun des 480 couples société-exercice, lister les documents candidats susceptibles de couvrir l'exercice (état de l'année et comparatif de l'année suivante inclus), leur récupération et leur examen effectif.
3. **Extraire et vérifier les BPA publiés** ainsi que, dans les notes BPA, le numérateur attribuable aux actionnaires ordinaires et le nombre moyen pondéré d'actions.
4. **Recalculer les BPA manquants seulement si les intrants comptables nécessaires sont établis** ; sinon, produire au plus le ratio indicatif fin d'exercice, séparé et non compté comme BPA.
5. **Documenter chaque cas non résolu** avec l'un des statuts encadrés et la liste des sources effectivement examinées.
6. **Verrouiller chaque famille de correction par des tests**, puis lancer une collecte complète et comparer les taux séparés avant/après (sociétés et observations, publié, confirmé, recalculé, documentaire).

> **Progression du 24/10/2026 — porte pilote fermée, extension non autorisée.** L'audit indépendant CIEC/SNTS/SDSC/BOAC/ETIT sur 2016–2025 couvre 50/50 cellules applicables, 485 documents indexés et 73 sources ouvertes. Résultat : 18 BPA publiés FCFA retenus (8 confirmés par deux documents distincts, 10 par un document plus contre-lecture/contrôle), 0 BPA recalculé comparable substitué, 13 ratios indicatifs séparés, 8 cellules avec information par action non retenue, 22 non publiées dans les sources vérifiées et 2 documents annuels complets introuvables. La collecte complète reste interdite tant que les défauts P0 prouvés (sélection, émetteur, mise en page, devise/composantes/périmètre/vintage, colonnes, décimales, cohérence) ne sont pas corrigés, testés puis validés en rejouant ces 50 cellules. Rapport et matrices : `sigma-app/audits/pilote_bpa_5/README.md`.
>
> **Progression du 25/10/2026 — régression réelle terminée, porte des valeurs franchie.** Les 73 PDF ont été rejoués avec SHA-256 identiques au pilote : **50/50 verdicts concordants**, **18/18 BPA retenus retrouvés**, **8/8 rejets humains démontrés**, 0 faux positif et 0 divergence retenue ; suite du collecteur à 96 tests réussis et dataset publié inchangé. Sept valeurs restent en extraction unique sans contrôle pondéré automatisé. La suite autorisée est l'audit des 480 cellules en mode statuts/preuves, sans intégration silencieuse au dataset ; les extractions uniques devront être revues ou confirmées avant usage comparable. Rapport, matrices et décision : `sigma-app/audits/regression_pilote_bpa_5_2026-10-24/README.md` et `REVUE_EXTRACTIONS_UNIQUES_ET_DECISION.md`.

> **Progression du 26/10/2026 — audit 480 terminé en mode statuts/preuves, intégration toujours interdite.** Inventaire BRVM en deux passages : 3 500 PDF indexés, 660 candidats ouverts en processus isolés, 657 avec SHA-256, 3 timeouts, 3 rejets « autre émetteur » et 26 intermédiaires écartés. Les 48 dates d'introduction sont désormais rattachées à une source officielle relue ; le périmètre réel est donc de **442 cellules applicables** et **38 non applicables**, avec **336 applicables examinées** par un document primaire. BPA publié brut : 34 au total, dont 33 applicables et 1 avant introduction (ORGT 2018). Après relecture des preuves, **29 BPA applicables** subsistent dans les compteurs de revue (**7 confirmés par deux documents, 4 par contrôle arithmétique, 18 en extraction unique**), soit **8,631 % des applicables examinées** ; BPA recalculé comparable : **0**, publications non retenues : 33, quarantaine : 1, ratios indicatifs séparés : 9. Le sous-ensemble pilote ressort à **18/18 valeurs** et **0 faux positif**. Deux défauts nouveaux sont démontrés et doivent être corrigés avant tout nouveau run comparable : dates « 31-déc-AA » prises pour des valeurs chez SPHC, et mélange individuel/consolidé dans un même rapport chez TTLS. Le backlog restant est de 71 cellules `ILLISIBLE` (PDF scannés/OCR), 15 `DOCUMENT_INTROUVABLE` dans l'inventaire BRVM et 18 `NON_RECHERCHE`. Le dataset publié reste inchangé. Livrables : `sigma-app/ingestion/audit_bpa_480.py`, `sigma-app/ingestion/apply_listing_dates_supplement.py`, `sigma-app/ingestion/analyze_audit_bpa_480.py` et `sigma-app/audits/audit_bpa_480_2016_2025_2026-10-25/REVUE_AUDIT_480.md`.

> **Progression du 26/10/2026 — correctifs SPHC/TTLS livrés et validés sur documents réels, intégration toujours interdite.** Le parseur `eps-evidence-v2.1.1` exclut désormais génériquement les jetons de dates des colonnes BPA (formes texte et structurées), reconnaît aussi les années espacées d'en-tête (`2 019 2 018`, cas ORGT), lit « Non dilué » comme base de base, reconnaît le périmètre lorsque « IFRS » est intercalé dans l'en-tête et conserve sans les promouvoir les valeurs brutes ambiguës sous une échelle de page en milliers/milliers (cas SPHC 0,830 et 1,695). Suite : **100 tests réussis**. Rejouage réel : SPHC ne produit plus 31/-21 ni de figure BPA éligible ; TTLS sépare la page 39 individuelle (205/128) de la page 42 consolidée (208/219) et retient le bloc consolidé. Régression pilote prudente : 72 documents complets avec SHA-256 du pilote donnent **18/18 valeurs** et **0 faux positif** ; le rapport annuel ETIT 2018, expiré après 900 s en extraction complète dans le sandbox de 2 Go, a été validé séparément sur ses 23 pages déjà sélectionnées (**25/25 observations identiques**), ce qui démontre aussi le huitième rejet sans prétendre à un nouveau 73/73 complet. Le journal 480 du 25/10 reste un artefact brut sous ancienne empreinte ; aucun nouveau run 480 et aucune intégration n'ont été lancés. Prochaine étape : contre-lire les 18 extractions uniques et SDSC 2022. Revue : `sigma-app/audits/correctif_sphc_ttls_2026-10-26/REVUE_CORRECTIF_SPHC_TTLS.md`.

> **Progression du 26/10/2026 — contre-lecture des extractions uniques terminée, quarantaine SDSC confirmée, intégration toujours interdite.** Les 18 BPA en extraction unique ont été relus sur leurs PDF/pages et contrôles arithmétiques : **18/18 restent retenus comme BPA publiés correctement lus**, sans faux positif de transcription ; ETIT 2024 doit être cité à **8,23 FCFA** plutôt qu'à l'arrondi brut 8,2. Les niveaux restent distincts : SDCC 2018/2019 est confirmé par deux PDF de même vintage, plusieurs valeurs ont un contrôle de face/note, d'autres seulement une cohérence de numérateur et des dénominateurs implicites, et certaines vintages ABJC/ORGT sont provisoires ou condensées. Aucun de ces contrôles n'a été reclassé en BPA recalculé comparable sans dénominateur moyen pondéré explicite. SDSC 2022 reste non retenu : 250,9 publié contre 259,545 recalculé depuis la face, tandis que la note répète par erreur le numérateur 2021 de 16 780 M. La contre-lecture a aussi révélé et fait corriger un faux candidat générique : les années espacées « 2 019 2 018 » de la note ORGT ne deviennent plus des BPA ; suite finale **100 tests**, parseur `eps-evidence-v2.1.1`, régression pilote prudente inchangée à **18/18 et 0 faux positif**. Le journal 480 du 25/10 reste sous ancienne empreinte : la prochaine étape est un rejouage/une agrégation ciblée sous l'empreinte finale, puis le backlog OCR/introuvables/non recherchés. Revue et décisions : `sigma-app/audits/contre_lecture_extractions_uniques_2026-10-26/REVUE_CONTRE_LECTURE.md`.

## 2 · Collecte & robustesse de l'usine

| # | Chantier | État | Importance · Effort |
|---|---|---|---|
| 2.1 | **Activation GitHub gratuite** (collecte chaque soir de séance 18:20 + 21:20 UTC déjà écrite, publication automatique, cache OCR persistant, alerte en cas d'échec) — c'est elle qui rend « SIGMA vient vers vous » réel | Écrit, **non activé** (décision : après la v1.5) | **CRITIQUE** · M |
| 2.2 | **Double passage + fusion face à la pagination BRVM instable** (index documents mesuré à 1 504 puis 1 522 le même jour) : union des passages, jamais remplacement sec | Partiel (caches en place, 109/109 réutilisations OCR) | IMPORTANT · M |
| 2.3 | **Performance de collecte à froid** (~2 h à froid vs ~12–19 min à chaud) : caches documents, parallélisme borné, reprise — pour tenir la fenêtre quotidienne sans fragilité | Partiel | IMPORTANT · M |
| 2.4 | **Tests automatisés du front** (aujourd'hui : 65 tests collecteur, QA navigateur par scripts non versionnés) | Absent | UTILE · M |
| 2.5 | **Vrai mode installable/hors-ligne** (manifeste présent mais aucun service worker : l'app ne fonctionne pas hors réseau avec la dernière collecte) | Absent | UTILE · S–M |
| 2.6 | **Rappel de sauvegarde des données personnelles** (l'export/import JSON existe, manuel — ajouter « dernier export il y a X jours » ; le journal est un actif) | Partiel | UTILE · S |

## 3 · Signaux quotidiens & venue vers l'utilisateur (v1.5 — décidé le 24/10)

| # | Chantier | Importance · Effort |
|---|---|---|
| 3.1 | Bloc Accueil « Aujourd'hui » : différentiel depuis la dernière collecte (ce qui a changé, pas de bruit de séance) | **CRITIQUE** · M |
| 3.2 | **Signal d'étude forte** à 5 conditions cumulées et écrites (Radar + fondamentaux sans drapeau + prix sous repère documenté + test de sortie + aucun avertissement qualité), avec ce qui l'invaliderait | **CRITIQUE** · L |
| 3.3 | **Invalidations structurées détectées automatiquement** sur positions et valeurs suivies (perte publiée, dividende coupé, coussin bilan sous seuil, publication majeure) | **CRITIQUE** · M |
| 3.4 | **Test de sortie** (taille ÷ valeur médiane par séance = séances de volume pour sortir proprement) | IMPORTANT · S–M |
| 3.5 | **Réserve opportunités** au profil (deuxième poche, signal fort uniquement) | IMPORTANT · S |
| 3.6 | **Registre figé des signaux** (date, cours, conditions, version des règles — non modifiable) : la fondation de la mesure, à démarrer tôt car le temps ne se rattrape pas | **CRITIQUE** · S–M |
| 3.7 | Émetteur **ntfy** (sonnette 2 lignes + lien direct ; actif dès 2.1, repli Telegram prévu) | IMPORTANT · S |

## 4 · Analyse & valorisation (v1.6)

| # | Chantier | Importance · Effort | Dépend de |
|---|---|---|---|
| 4.1 | **Fourchette de valeur par scénarios triangulés** (≥ 2 ancres : dividende, bénéfice, patrimoniale ; sinon refus écrit) + **marge de sécurité** branchée comme condition du signal fort | **CRITIQUE** · L | Dividende prêt (44 sociétés) ; 1.1 pour les autres ancres |
| 4.2 | **Qualité des bénéfices** (trésorerie cumulée vs résultat cumulé, dividende vs flux après investissements, croissance qui consomme le bilan) | **CRITIQUE** · M | 1.2 |
| 4.3 | **Tableau de ratios par année** en fiche (ROE annuel, marge nette, capitaux propres/bilan, dette/flux où lisible) — les données existent largement, c'est de l'affichage calculé | IMPORTANT · S–M | — (gain rapide) |
| 4.4 | **Stress du portefeuille** : rejouer la pire fenêtre d'archive par position (effet combiné, libellé « si le passé récent se répétait ») | IMPORTANT · M | Archive prête (amélioré par 1.5) |
| 4.5 | « Déjà intégré dans le cours ? » : réaction mesurée du cours après chaque publication officielle (dates documents × archive BOC) | UTILE · M | Archive prête |

## 5 · Portefeuille & risque

| # | Chantier | Importance · Effort |
|---|---|---|
| 5.1 | **Pondérations cibles et alertes de concentration** (par position et par secteur, seuils au profil) — aujourd'hui la répartition est seulement affichée | IMPORTANT · M |
| 5.2 | **Taille de position suggérée par la liquidité** (plafonnée par le test de sortie, jamais par l'enthousiasme) | IMPORTANT · S–M |
| 5.3 | **Dividendes attendus/reçus auto-détectés** sur les positions réelles (dates de détachement × positions → à confirmer, performance réelle complète) | UTILE · M |
| 5.4 | Corrélations entre titres — techniquement possibles sur 262 séances mais trompeuses sur titres illiquides : priorité basse assumée | PLUS TARD · M |

## 6 · SIGMA se mesure (v1.7)

| # | Chantier | Importance · Effort |
|---|---|---|
| 6.1 | **Notation des signaux du registre** à +20/+60/+120/+250 séances vs BRVM Composite (prix seuls assumés jusqu'à 1.5) — la seule preuve recevable de « meilleures décisions que la moyenne » | **CRITIQUE** · M (+ le temps) |
| 6.2 | **Classification des erreurs** (timing, thèse, liquidité, fait nouveau) et revue trimestrielle ; aucune règle modifiée sans erreur mesurée au journal | IMPORTANT · S en continu |
| 6.3 | Backtest rétrospectif **encadré et limité** à ce qui est point-dans-le-temps prouvable (prix/PER d'archive) — sinon refus, plutôt qu'un passé flatteur fabriqué | PLUS TARD · M |

## 7 · Expérience & pédagogie

| # | Chantier | Importance · Effort |
|---|---|---|
| 7.1 | **Études de cas BRVM complètes et figées** (3–5 sociétés travaillées de bout en bout : états, ratios, frais réels, liquidité, fourchette — comme justification modèle, à partir de données datées) | UTILE · M |
| 7.2 | Glossaire : une entrée « ? » pour chaque notion nouvelle livrée (marge de sécurité, test de sortie, ancre, actualisation…) | UTILE · S en continu |

## 8 · Contours honnêtes — ce qui ne sera pas construit, ou pas par SIGMA

- **Temps réel** : payant sous licence ; écarté sauf décision budgétaire explicite.
- **Passage d'ordres / vente automatique** : jamais dans SIGMA. Il détecte, alerte et prépare ; l'ordre reste chez la SGI.
- **Probabilités chiffrées des scénarios** : refusées tant qu'elles ne sont pas prouvables sur données BRVM — hypothèses et déclencheurs affichés à la place.
- **Fiscalité personnelle automatisée** et « coût total » sans assiette établie : non calculés plutôt qu'inventés (les plafonds SGI restent des plafonds négociables).
- **Données que seul l'utilisateur détient** (grille SGI reçue, transactions réellement exécutées) : saisie unique par conception — tout le reste est automatisé.

---

## Ordre d'exécution recommandé

1. **Référentiel 48 + matrice 480 + registre figé des signaux** — d'abord les dénominateurs, les statuts et la mesure dans le temps ; aucun nouvel indicateur BPA ne doit être industrialisé sur une définition floue.
2. **Audit documentaire 2016–2025 puis extraction BPA/actions** selon la séquence du §1, univers liquide d'abord pour les vagues de correction mais matrice complète dès le départ ; flux (1.2) et confirmations (1.3) en parallèle.
3. **Gain rapide en parallèle** : 4.3 (ratios annuels) et 3.4 (test de sortie) — données disponibles, valeur immédiate.
4. **Activation GitHub + ntfy** (2.1, 3.7) dès la v1.5 stable ; 2.2/2.3 durcissent la collecte quotidienne.
5. **v1.6** : 4.2 puis 4.1 au fur et à mesure des ancres (dividende d'abord), 4.4, et 1.5 (OST/rendement total) + 1.6 (résultats UMOA) pour des taux et des performances propres.
6. **v1.7** : premier bilan chiffré à +60 séances de signaux, puis semestriel. Le reste (1.7–1.12, 5.x, 7.x) s'insère par vagues selon ce que la mesure désignera comme le maillon faible.

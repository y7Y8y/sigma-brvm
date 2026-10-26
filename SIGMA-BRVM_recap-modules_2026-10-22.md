# SIGMA BRVM — récapitulatif des modules et des bases
**État au vendredi 24 octobre 2026 (Abidjan) — v1.4 livrée (refonte d’interface, données inchangées).** Dataset : collecte complète du 2026-10-22 21:20 UTC (dernier BOC lu : 21 octobre 2026), publiée après audits tarifaires ciblés successifs (canaux de découverte officiels BRVM, sélection par SGI, bornes de plausibilité OCR), contrôle de non-régression contre la v1.2 (0 SGI perdue, 7 gagnées) et QA navigateur. Sauvegardes v1.0, v1.1, v1.2 et v1.3 conservées.

## Bases de données

| Base | État | Contenu mesuré (v1.2) | Limites connues |
|---|---|---|---|
| Marché EOD / BOC | Opérationnel | 48 sociétés (instantané + dernier BOC), 30 BOC récents, archive 262 séances (2025-09-22 → 2026-10-21) | Fin de journée uniquement (temps réel payant) ; formats de BOC antérieurs non relus |
| Documents émetteurs | Opérationnel | 1 504 documents indexés, 47 sociétés ; états intermédiaires (revue limitée au 30 juin) et états « par secteur » classés à part et exclus des séries annuelles générales | Index seulement : tout n'est pas extractible ; la pagination BRVM fluctue entre passages (1 504 à 1 522 le même jour) |
| Fondamentaux annuels | Partiel, en forte progression | 45 sociétés avec agrégats, 41 séries ≥ 3 exercices, 1 220 agrégats dont 352 confirmés par deux documents ; OCR contrôlée : 109 documents scannés tentés, 300 agrégats pour 24 sociétés ; comparaison v1.2→v1.3 : périmètre stable société par société aux fluctuations d’index BRVM près (ORGT/PALC) | BOAB, BOABF, BOAC, BOAM, BOAS (confiance A), BOAN (B), NEIC et SICC (C, partiels) ont désormais une série ; restent BBGC, ETIT et NSBC sans série |
| Flux de trésorerie & capital | Partiel | Flux opérationnel : 23 sociétés ; trésorerie/dettes : 32 ; BPA : 6 ; nombre d'actions : 4 ; repères dividende/trésorerie : 16 lignes (4 sociétés dividende/BPA, 2 avec couverture cash) | Couverture BPA/actions faible → score global volontairement suspendu |
| Dividendes | complet sur la source | 348 distributions, exercices 2015–2025, 44 sociétés, 21 documentées sur 5 exercices | Montants nets publiés par la BRVM ; dividende brut non séparé |
| Actualités / Radar | Opérationnel | 153 éléments, 68 rattachés à un titre | Presse présente mais à recouper ; priorité aux sources officielles |
| Macro BCEAO / UMOA-Titres | Opérationnel partiel | CPM du 2026-09-09 (taux directeur 3,00 %) ; 31 opérations UMOA à venir ; calendrier 35 échéances | Aucune projection de réunion CPM ; montants annoncés ≠ montants levés |
| Annuaire SGI + tarifs homologués | Opérationnel, couverture étendue | 37 SGI (annuaire officiel BRVM, pays et contacts) ; **plafonds AMF-UMOA relus pour 33/37 SGI** via 4 canaux (pages de décisions BRVM, index « Avis et publications » BRVM, Richbourse, Omaad) ; 60 décisions/grilles uniques relues, 24 exemplaires plus anciens remplacés, 242 rubriques affichées (109 recoupées, 67 concordantes, 12 divergentes signalées), 0 décision affichée sans annexe, 3 décisions hors annuaire listées séparément ; numéro **annoncé** (page BRVM) affiché distinct du numéro relu ; bornes de plausibilité écartant les % artefacts d’OCR du résumé chiffré | 4 SGI sans décision retrouvée (ORAGROUP SECURITIES, GLOBAL CAPITAL, EVEREST FINANCE, United Capital for Africa) ; plafonds parfois anciens (2012) = derniers homologués connus ; plafond ≠ tarif facturé ; aucun coût total calculé (assiette fiscale non établie) |
| Archive BOC longue | Opérationnel | 262 séances persistantes, fusion quotidienne de la fenêtre récente | Objectif atteint ; extension au-delà non validée |

## Modules applicatifs — 6 onglets depuis la v1.4 (+ pages secondaires)

| Onglet | État | Note |
|---|---|---|
| Accueil | Opérationnel | « Ce mois-ci » en premier (versement, première société à examiner selon vos règles, titres possibles, frais connus ou « non estimés »), puis alertes non lues, « Le marché en une minute », Radar et prochaines échéances ; variations de séance repliées |
| Entreprises | Opérationnel | Fiches multi-niveaux allégées en v1.4 (preuves détaillées en blocs repliés, résumé et actions toujours visibles) ; glossaire (pointillé + « ? »), provenance par document, badge OCR et confiance par montant |
| Actualités & annonces | Opérationnel | Radar officiel d'abord, presse recoupée ensuite |
| Décision | Partiel volontaire | Fusion des anciens onglets Analyses et Rapports : Décision du mois (par défaut), Radar SIGMA, Baisses à examiner, Contexte & scénarios, Marché en chiffres, Documents & échéances ; piliers conditionnés aux données confirmées, aucun score global tant que la couverture est faible |
| Portefeuille | Opérationnel | Réel et simulation strictement séparés (violet = simulation) ; positions réelles fournies par l'utilisateur |
| Paramètres | Opérationnel | Coupe en deux en v1.4 : « Mon profil & ma SGI » (préréglage, frais, plafonds de votre pays d’abord) et « État des données » technique replié (manifeste, audit) ; carte « Plafonds homologués négociables des SGI » avec décision, rubriques, second lecteur et PDF officiel par SGI |
| Pages secondaires (hors navigation) | Opérationnel | Marché détaillé (cours EOD, BOC, archive 262 séances) et liste complète des alertes, accessibles depuis l’accueil ; anciens liens #analyses, #rapports, #marche, #alertes toujours actifs |

## Socle technique

- Collecteur `ingestion/collect.py` (sources officielles, mots positionnés, unités prouvées, recoupement par deux documents, OCR contrôlé uniquement en repli, décisions tarifaires AMF-UMOA relues dans leurs PDF via les canaux officiels BRVM et les index tiers de découverte) — **65/65 tests au vert** ; QA navigateur Chromium sans erreur console.
- Front statique `web/` (aucune donnée fictive : manquant = affiché manquant).
- Aperçu local actif sur le port 8000.
- Workflows GitHub (collecte quotidienne + publication) écrits mais **non activés** (report décidé par l'utilisateur).
- Livrable v1.4 : `SIGMA-BRVM_application-v1.4-et-CDC.zip` — voir la note de livraison ci-dessous pour taille et SHA-256. Les ZIP v1.0 → v1.3 restent conservés.

## Tarifs SGI — enquête du 21/10/2026, intégration v1.2 puis extension v1.3 (22/10/2026)

**Mise à jour v1.3 : couverture étendue de 26 à 33 SGI/37.** L’article 3 des décisions impose leur communication à la BRVM pour publication : deux canaux officiels ont été ajoutés en primaire — les pages de décisions du site BRVM (recherche du site unionnée sur quatre formulations car ses résultats varient d’un passage à l’autre, titre complet lu sur la page) et le balayage de l’index chronologique « Avis et publications » jusqu’en 2018. Le numéro présent dans le titre ou le nom de fichier BRVM est conservé comme **numéro annoncé**, distinct du numéro relu dans le PDF (formes inversées comprises, ex. « PAMF-UMOA – 346 -2024 »). La sélection par SGI a été réécrite : tous les exemplaires relus sont conservés, dédoublonnés par empreinte/numéro avec **union des métadonnées** (le numéro annoncé d’une copie perdante n’est plus perdu), puis la décision affichée est la plus récente avec annexe lisible ; les homologations d’autres intervenants (SGO/SGP, BTCC, SICAV) sont écartées par titre et par l’acteur lu dans la décision. Trois rattachements de nom ont été prouvés par les sociétés elles-mêmes (SOGEBOURSE, AFRICAINE DE BOURSE, CIFA BOURSE). Des bornes de plausibilité (3 % flux / 10 % primaire) écartent les pourcentages artefacts d’OCR du résumé chiffré sans toucher au texte affiché. Résultat mesuré : 60 décisions relues, 33/37 SGI, 242 rubriques, 67/109 concordantes, 12 divergences affichées, 6/27/3 vérifiées/partielles/grilles, 0 sans annexe, 3 hors annuaire (Kerales Finances, Mansa Capital, One Africa Markets). Gains : SGI Mali, SGI Niger, SGI Togo, Image Finances, SGCSWA, CIFA, annexe Hudson 2023 retrouvée ; corrections : BSIC 2024 (et non 2018), MAC 2024 (et non 2019).

**Mise à jour v1.2 : le chantier ci-dessous est livré.** Découverte paginée Richbourse + fiches Omaad rendues côté serveur ; chaque PDF est relu (autorité, numéro hors visas, date près du « Fait à », nom SGI dans le titre), OCR contrôlée pour les scans, rubriques normalisées avec texte d’origine et page, recoupement par rubrique avec l’index (second lecteur). Résultat mesuré : 31 décisions/grilles uniques, 26/37 SGI de l’annuaire avec plafonds, 223 rubriques, 128/198 concordantes, 23 divergences affichées, 4/23/4 décisions vérifiées/partielles/grilles sans lettre, 4 décisions hors annuaire (CIFA Bourse, Kerales Finance, Mansa Capital, One Africa Markets). L’enquête d’origine suit pour mémoire.


**Constat confirmé :** la BRVM ne publie pas les grilles par SGI. Elle explique la structure : courtage SGI libre mais **homologué par l'autorité de tutelle**, plus commissions de marché BRVM 0,2 % et DC/BR 0,1 %, payables par l'acheteur et par le vendeur.

**La source primaire existe :** chaque grille fait l'objet d'une **décision d'homologation de l'AMF-UMOA** (ex-CREPMF), numérotée et datée, avec la grille annexée sous une présentation normalisée. Exemple vérifié de bout en bout : décision PAMF-UMOA/2024/163 du 26 juin 2024 pour BSIC Capital — courtage ordinaire « Maximum 0,8 % », conservation par tranches trimestrielles, tenue de compte 2 500 FCFA/trimestre maximum.

**Omaad : piste réelle et sérieuse.** Leur comparateur gratuit couvre les 41 SGI agréées AMF-UMOA, avec grilles détaillées pour 32 d'entre elles. Méthode déclarée : lecture et saisie manuelles depuis les PDF officiels d'homologation, chaque fiche renvoyant au PDF source ; anomalies signalées honnêtement (un PDF mal étiqueté détecté et réattribué). Limites : ce sont des **plafonds homologués, souvent négociables**, pas nécessairement le prix facturé ; les notes affichées (ex. 4,9) viennent d'un répertoire tiers et ne sont pas des données officielles.

**BRVM Analyser : pas une source de tarifs SGI.** Plateforme d'analyse de titres (PER, BNA, DPA, valorisation) avec notes payantes ; sur les frais, seuls des ordres de grandeur génériques (courtage « généralement 0,5 à 1 % »). Aucune grille par SGI trouvée.

**Richbourse (découverte au passage) :** publie un tableau des tarifs par SGI dont chaque ligne renvoie au « document officiel » (décision d'homologation). Même famille de source que Omaad — les identifiants de documents concordent.

### Intégration proposée pour SIGMA (chantier suivant, après la v1.1)

1. Découvrir les décisions via les index publics (Omaad/Richbourse), mais **ne jamais copier leur saisie** : télécharger le PDF officiel, vérifier en-tête AMF-UMOA, numéro et date de décision, puis extraire les rubriques normalisées avec le même moteur que les fondamentaux.
2. Afficher chaque tarif pour ce qu'il est : « plafond homologué AMF-UMOA (décision n°…, du …), négociable », distinct de la grille personnellement reçue, qui reste la référence de l'utilisateur.
3. Rubriques utiles au comparateur SIGMA : courtage ordinaire actions, courtage sur dossier, conservation, tenue de compte, transfert, ouverture/clôture lorsqu'ils figurent dans la grille.
4. Réconcilier les référentiels : 37 SGI dans l'annuaire BRVM contre 41 agréées AMF-UMOA — apparier par nom normalisé, signaler les SGI absentes d'un des deux référentiels plutôt que les fusionner en silence.
5. Ne calculer aucun « coût total » tant que l'assiette fiscale (taxes selon le pays) n'est pas établie dans la grille elle-même.

## Restant à faire (rappel)

- v1.1, v1.2, v1.3 : terminées (collecte → contrôles → QA navigateur → README → ZIP vérifié).
- Tarifs SGI : poursuite limitée des 4 SGI sans document public (ORAGROUP SECURITIES, GLOBAL CAPITAL, EVEREST FINANCE, United Capital for Africa) et des 12 divergences, sans abaisser les preuves.
- Fond : couverture BPA/actions, dividende brut, archive ajustée et rendement total, flottant/capitalisation, profondeur BCEAO/UMOA, activation GitHub quand l'utilisateur le décidera.

## Note de livraison v1.3

ZIP `SIGMA-BRVM_application-v1.3-et-CDC.zip` produit après collecte 2026-10-22 21:20 UTC, tests 65/65 et QA navigateur (vue Paramètres, carte « Plafonds homologués négociables des SGI », 0 erreur console). Taille et SHA-256 communiqués avec le fichier.

## Note de livraison v1.4

ZIP `SIGMA-BRVM_application-v1.4-et-CDC.zip` — 15 fichiers, 2 485 036 octets, SHA-256 `ac0eaa4297ad86a64f91eda5ffd8f238c73ab013effababf0e5dd5a5b949af91`. Refonte d’interface seule (le dataset livré reste la collecte v1.3 du 2026-10-22 21:20 UTC, collecteur et 65/65 tests inchangés). QA navigateur : 23/23 contrôles (navigation 6 onglets, accueil « Ce mois-ci » en premier, fusion Analyses+Rapports dans Décision, Paramètres scindés, fiche repliée, anciens liens #analyses/#rapports/#marche/#alertes) et 0 erreur console ; mobile 390 px sans débordement de page.

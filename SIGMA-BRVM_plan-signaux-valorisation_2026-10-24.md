# SIGMA — Plan v1.5 → v1.7 : signaux quotidiens, valorisation par scénarios, mesure des erreurs

**Décidé avec l'utilisateur le 24/10/2026.** Ce document fige les choix et le cahier des charges des trois prochains blocs. Règle inchangée : aucune donnée, aucun ratio, aucun frais inventé ; ce qui n'est pas prouvable est affiché « non calculable ».

## Décisions du 24/10/2026 (corrections explicites)

1. **Usage quotidien, pas mensuel.** Le mensuel reste le rythme du *versement*, pas celui de la veille. SIGMA travaille chaque jour de séance et vient vers l'utilisateur ; l'utilisateur n'a pas à aller chercher l'information.
2. **Canal qui vient vers l'utilisateur : ntfy** (notifications poussées, gratuit, sans compte). La notification est une « sonnette » de 2 lignes + lien direct vers le signal dans l'app ; l'analyse reste intégralement dans SIGMA. Telegram reste un repli possible (même émetteur, 10 minutes de bascule) si le téléphone bloque ntfy.
3. **Machine quotidienne (GitHub) : après les fonctions.** On construit d'abord signaux/valorisation en local ; la collecte automatique quotidienne et l'envoi ntfy s'activent au branchement. Conséquence assumée : avant branchement, les signaux sont calculés à l'ouverture de l'app, sur la dernière collecte.
4. **Rythme d'action : deux poches.** Versement mensuel discipliné **+** réserve opportunités séparée (montant paramétrable au profil), mobilisable uniquement sur « signal d'étude forte » documenté.
5. **Méthode de valorisation : déléguée au lead.** Choix retenu : triangulation par ancres indépendantes, en parallèle de l'extension BPA/actions (voir v1.6).

## v1.5 — Moteur de signaux quotidiens & protection (prochain bloc)

- **Bloc Accueil « Aujourd'hui » en premier** (avant « Ce mois-ci ») : ce qui a changé depuis la dernière collecte (différentiel), signaux actifs, invalidations touchées, échéances proches. Zéro variation de séance seule présentée comme signal.
- **Signal d'étude forte** = conditions *cumulées et écrites*, toutes vérifiables dans les données du jour :
  1. éligible Radar (échangeabilité ≥ 15/20 séances, valeur médiane ≥ seuil, PER publié ≤ 25, rendement récent non extrême) ;
  2. piliers fondamentaux disponibles sans drapeau rouge (Solidité calculable, pas de coussin bilan dégradé sur la série) ;
  3. prix sous un repère relatif documenté (PER ≤ médiane du secteur ou baisse documentée ≥ seuil du profil *avec* checklist baisse sans fait invalidant identifié) ;
  4. test de sortie satisfaisant (voir plus bas) ;
  5. aucun avertissement qualité sur la société dans la collecte.
  Libellé imposé : « conditions réunies pour étude immédiate » — jamais « acheter ». Chaque signal liste les faits datés, la règle, **ce qui l'invaliderait**, et ouvre le brouillon de thèse pré-rempli. Anti-bruit : un signal par société et par cause, pas de réémission tant que les faits n'ont pas changé.
- **Invalidations structurées** rattachées à chaque position réelle/simulée et valeur suivie, testées automatiquement à chaque collecte : résultat net négatif nouvellement publié, dividende coupé ou supprimé vs exercice précédent documenté, capitaux propres/bilan passant sous le seuil écrit, publication officielle majeure rattachée, PER/rendement devenus non interprétables. Alerte dédiée « condition d'invalidation touchée par [document daté] » → tâche de relecture, jamais vente automatique (SIGMA ne passe aucun ordre).
- **Test de sortie** par position et par candidate : taille envisagée ÷ valeur médiane échangée par séance = nombre de séances de volume médian pour sortir sans dominer le marché du titre (repère affiché avec sa formule, pas une promesse).
- **Réserve opportunités** au profil (montant ou % du versement) ; l'onglet Décision l'utilise uniquement en mode « signal fort », séparée du versement mensuel et de la poche d'apprentissage.
- **Registre des signaux figés** (fondation v1.7) : à chaque émission — date, société, cours publié, conditions remplies avec valeurs, BOC de référence, version des règles. Non modifiable après coup.

## v1.6 — Qualité des bénéfices & fourchette de valeur par scénarios

- **Qualité des bénéfices** (là où les flux existent — 23 sociétés aujourd'hui, chantier d'extension en fond) : trésorerie générée cumulée vs résultat net cumulé sur les exercices communs ; dividende vs flux après investissements ; croissance de l'activité lue avec marge (résultat/activité) et coussin bilan — drapeaux « bénéfice sans trésorerie répétée », « croissance qui consomme le bilan ». Jamais de note si la matière manque : « non vérifiable ».
- **Fourchette par triangulation** (au moins 2 ancres indépendantes, sinon refus écrit) :
  - *Ancre dividende* : historique officiel 2015–2025 (44 sociétés) ; scénarios = trajectoires bornées par l'historique propre de la société (pessimiste : plus mauvaise trajectoire observée, centrale : trajectoire médiane, optimiste : meilleure observée — croissances plafonnées, jamais d'extrapolation libre) ; taux d'actualisation = paramètre **visible et modifiable** (référence BCEAO du jour + prime d'exigence affichée), sensibilité ±1 point montrée.
  - *Ancre bénéfice* : uniquement où le BPA est vérifié par deux documents (6 sociétés aujourd'hui → chantier BPA/actions prioritaire en parallèle) ; multiple borné par l'historique propre et le secteur.
  - *Ancre patrimoniale* : uniquement où le nombre d'actions est vérifié (4 sociétés aujourd'hui).
  Probabilités des scénarios : **non chiffrées** (les données BRVM ne permettent pas de les prouver) — chaque scénario affiche en revanche ses hypothèses et les faits observés qui le déclencheraient ou l'invalideraient.
- **Marge de sécurité, règle écrite** : prix ≤ valeur pessimiste → « zone d'étude prioritaire » ; entre pessimiste et centrale → « sans marge particulière » ; au-dessus de la centrale → « prix sans marge — même si l'entreprise est de qualité ». C'est ce verdict qui alimente la condition n° 3 du signal fort, en remplacement du seul repère relatif.
- **Stress du portefeuille** : rejouer, par position détenue, sa pire fenêtre de l'archive BOC (262 séances) et afficher l'effet combiné — libellé « si le passé récent se répétait », jamais prévision.

## v1.7 — SIGMA se mesure

- Chaque signal du registre est noté à +20/+60/+120/+250 séances vs BRVM Composite (prix seuls, libellé explicite) et vs son propre seuil : a-t-il atteint la zone attendue, a-t-il été invalidé, le test de sortie était-il réaliste ?
- Erreurs classées par cause (timing, thèse, liquidité, fait nouveau) à partir des documents survenus — mesure du *processus*, pas seulement du résultat.
- Aucune modification de règle sans entrée au journal indiquant l'erreur mesurée qui la justifie (anti-changement de stratégie à chaque fluctuation).
- Pas de backtest rétrospectif flatteur : les fondamentaux « tels que connus à l'époque » n'existent pas en archive propre ; on mesure en avant, honnêtement, à partir du registre figé. Le titre « meilleures décisions que la moyenne » ne sera revendiqué — ou réfuté — que par ce registre.

## Activation (après v1.5, décision utilisateur)

Branchement GitHub gratuit : collecte chaque soir de séance → calcul des signaux → briefing poussé par ntfy (2 lignes + lien). Avant ce branchement, SIGMA ne « vient » vers personne : les signaux attendent dans l'accueil à l'ouverture.

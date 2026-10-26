# Ce que SIGMA peut vous dire aujourd'hui — et ce qu'il ne peut pas encore

**26 octobre 2026** · Réponse du lead analyste à trois questions : le verdict acheter/vendre, les deux portefeuilles, et l'usage en PWA.
Données : collecte officielle du **22/10/2026 21:20 UTC**, dernière séance **21/10/2026**.

---

## 1. La PWA : oui, elle est prête — depuis aujourd'hui

Ce qui a été livré et vérifié :

- **Service worker** (`web/sw.js`) : l'application s'ouvre **sans réseau**, avec la dernière collecte connue. Les fichiers de données sont servis en « réseau d'abord, copie locale ensuite » ; une réponse tronquée ou non valide n'est **jamais** mise en cache. Mieux vaut une absence qu'un chiffre faux.
- **Icônes PNG 192 et 512** en plus du SVG : Android exige du PNG pour proposer une vraie installation. Icônes dérivées du Σ existant, vérifiées visuellement.
- **Manifeste** complété : mode `standalone` (plein écran, sans barre d'adresse), orientation portrait, portée explicite.
- **131 tests** au total, dont 10 nouveaux sur la PWA. Aucune fonctionnalité existante touchée.

**Comment vous l'utilisez :**

1. Ouvrez la preview de l'application dans votre navigateur.
2. **Android / Chrome** : menu ⋮ → « Ajouter à l'écran d'accueil » / « Installer l'application ».
3. **iPhone / Safari** : bouton Partager → « Sur l'écran d'accueil ».
4. Elle s'ouvre ensuite comme une application, sans barre d'adresse, et fonctionne en avion.

**Ce qu'un test automatisé ne peut pas prouver, et que je ne vous vendrai pas comme prouvé :** je n'ai pas de navigateur dans cet environnement. J'ai donc vérifié tout ce qui est vérifiable sans lui (fichiers servis, manifeste valide, icônes existantes, syntaxe, règles de cache, préchargements) — **pas** l'installation réelle sur votre téléphone. C'est la seule case encore ouverte, et vous la fermez en trente secondes chez vous.

---

## 2. « Cette action est surévaluée, vends » — ce que l'app dit aujourd'hui

**Aujourd'hui, SIGMA ne prononce aucun verdict d'achat ou de vente.** Ce n'est pas un oubli : c'est la conséquence directe de l'état des données, et je préfère vous l'expliquer une fois clairement.

Un verdict de surévaluation suppose de comparer le prix à une **valeur estimée** de l'entreprise. Cette valeur exige au minimum deux ancres indépendantes : les bénéfices vérifiés et le patrimoine par action. Or, dans vos données du jour :

- PER publié au BOC (par la BRVM, pas par SIGMA) : **44 sociétés sur 48** ;
- BPA **vérifié par SIGMA** : une **poignée** de sociétés ;
- nombre d'actions vérifié : **4 sociétés sur 48** ;
- BPA recalculé comparable : **0**.

Donc si SIGMA affichait « sous-évaluée » sur une société, ce verdict reposerait sur un PER que la BRVM a publié avec sa propre définition, à une date qui peut être ancienne, et sur un bénéfice que nous n'avons pas vérifié nous-mêmes. Ce serait exactement le genre de chiffre plausible que le projet existe pour refuser.

### Ce que l'app fait déjà, et qui est honnête

Le **Radar** : un tri par règles écrites et affichées. Liquide (≥ 15 séances échangées sur 20, valeur médiane ≥ 5 M FCFA), PER publié ≤ 25, dividende récent non extrême. Il répond à « **quoi étudier d'abord** », jamais à « quoi acheter ».

**Résultat sur les données du 21/10/2026 : 31 sociétés sur 48 passent le Radar.**

Les cinq PER publiés les plus bas parmi les éligibles :

| Société | Cours (FCFA) | PER publié BOC | Rendement net | Liquidité (médiane/séance) |
|---|---:|---:|---:|---:|
| ETIT | 64 | 3,3 | 1,46 % | 62,5 M |
| PALC | 7 500 | 7,48 | 5,88 % | 22,2 M |
| SPHC | 7 620 | 7,78 | 5,66 % | 21,3 M |
| SMBC | 14 395 | 8,65 | 4,85 % | 13,0 M |
| ORGT | 2 800 | 8,92 | 2,14 % | 8,4 M |

**À lire avec la bonne méfiance, et c'est important :** un PER bas n'est **pas** une bonne affaire. C'est un prix qui paraît bas rapporté à un bénéfice **passé**. Le marché, lui, cote une anticipation. Sur la BRVM, un PER très bas signale souvent un bénéfice attendu en baisse, une gouvernance douteuse, ou un titre que personne ne peut acheter ni revendre. Le cas ETIT à 3,3 est typique : titre peu échangé, périmètre comptable à vérifier. **Un PER bas est une question, pas une réponse.**

### Le verdict que je vais construire, et son libellé exact

Quatre niveaux seulement, jamais « acheter » ni « vendre » :

| Libellé | Condition écrite |
|---|---|
| **Zone d'étude prioritaire** | prix ≤ valeur pessimiste (marge de sécurité réelle) |
| **Sans marge particulière** | prix entre valeur pessimiste et valeur centrale |
| **Prix sans marge** — même si l'entreprise est de qualité | prix > valeur centrale |
| **Non calculable** | moins de deux ancres indépendantes → refus écrit, avec la raison |

Chaque verdict affichera : les faits datés qui le fondent, la règle appliquée, **ce qui l'invaliderait**, et la sensibilité au taux d'actualisation (±1 point). Le mot « vendre » n'apparaîtra que dans un contexte précis : « condition d'invalidation touchée par [document daté] », jamais comme un ordre.

Sur les données actuelles, la majorité des sociétés afficherait honnêtement **« non calculable »**. C'est décevant à voir, et c'est juste.

---

## 3. Court terme / long terme : mon avis, en tant qu'analyste

Vous demandez deux poches : une court terme, une long terme. Je vous donne mon jugement professionnel, pas une politique de communication.

**Sur la BRVM, le « court terme » n'est pas un raccourci : c'est un péage.** Trois chiffres de vos propres données le montrent :

- **BNBC** : 1,9 M FCFA échangés par séance en médiane. Un ordre de 300 000 FCFA y pèse 16 % d'une séance normale — vous faites bouger le prix en entrant, et en sortant.
- **UNLC** : 0,4 M FCFA par séance. C'est de l'ordre de grandeur d'un ordre qui ne trouve pas de contrepartie.
- Sur 48 sociétés, la liquidité est très inégalement répartie : quelques titres concentrent l'essentiel des échanges.

S'y ajoutent des frais de courtage et une fourchette achat/vente qui, sur un aller-retour rapide, mangent l'essentiel d'un mouvement de quelques pourcents. Un aller-retour mensuel sur un titre peu liquide peut coûter plus que le rendement annuel du dividende.

**Ma recommandation, et je l'assume :** au lieu de « court terme » contre « long terme », je propose **trois poches** :

1. **Cœur long terme** — versement mensuel discipliné, sur des sociétés documentées, horizont de plusieurs années. C'est là que va l'essentiel.
2. **Réserve d'opportunité** — montant paramétrable, mobilisable **uniquement** sur « signal d'étude forte » documenté, et seulement sur des titres dont le test de sortie tient (taille ÷ volume médian = nombre de séances pour sortir proprement). Ce n'est pas du trading : c'est du prix qui s'éloigne de la valeur.
3. **Poche d'apprentissage** — déjà présente dans l'application, séparée, assumée comme apprentissage.

Un vrai « court terme » suppose de pouvoir entrer et sortir vite sur un marché profond. Ce n'est pas la BRVM. Le dire fait partie du travail.

---

## 4. Ce qu'il me faut de vous, et rien de plus

Deux réponses, deux minutes :

1. **Quel montant mensuel réel** ? (aujourd'hui 200 000 FCFA par défaut — c'est un réglage, pas un engagement)
2. **Quelle part pour la réserve d'opportunité** ? (0 % est une réponse parfaitement valable)

Le reste — seuils, libellés, tests, ordre des travaux — est mon travail.

## 5. Ce que je fais ensuite, dans cet ordre

1. **Poche d'opportunité et test de sortie** dans l'onglet Décision (v1.5, dépend de votre réponse au point 2).
2. **Registre figé des signaux** — celui qui ne se rattrape pas.
3. **Registre du nombre d'actions** — le déblocage de la valorisation, et donc des vrais verdicts.
4. **Verdict à quatre niveaux**, affiché seulement là où deux ancres existent, avec « non calculable » ailleurs.

Aucune de ces étapes n'invente une donnée. La première qui change votre expérience quotidienne est la première : l'accueil vous dira, à l'ouverture, ce qui a changé depuis la dernière collecte — au lieu de vous laisser chercher.

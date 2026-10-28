# Complétude de SIGMA, mesurée par capacité

*48 sociétés · collecte du 2026-10-22T21:20:37+00:00*

Aucun taux global : chaque capacité a sa propre condition d'éligibilité.
Une moyenne unique masquerait qu'on peut décrire le marché sans rien valoriser.

| Capacité | Sociétés servies | Couverture | Ce que son absence bloque |
|---|---:|---:|---|
| Décrire le marché (cours, PER publié, rendement, liquidité) | **43/48** | 89.6 % | la fiche société elle-même |
| Calculer la capitalisation boursière | **2/48** | 4.2 % | le poids réel d'une société dans l'indice et la concentration |
| Calculer un PER par SIGMA (et non reprendre celui du BOC) | **0/48** | 0.0 % | tout verdict de valorisation fondé sur le bénéfice |
| Ancre patrimoniale (capitaux propres par action) | **1/48** | 2.1 % | la deuxième ancre indépendante, donc le verdict à quatre niveaux |
| Ancre bénéfice (BPA × multiple borné) | **4/48** | 8.3 % | une fourchette de valeur à deux ancres |
| Ancre dividende (actualisation bornée par l'historique propre) | **43/48** | 89.6 % | la seule ancre disponible aujourd'hui |
| Qualité du bénéfice (trésorerie cumulée vs résultat cumulé) | **18/48** | 37.5 % | le drapeau « bénéfice sans trésorerie » |
| Dividende soutenable (couverture par la trésorerie) | **0/48** | 0.0 % | la confiance dans le rendement affiché |

## Ce qui bloque, champ par champ

- **nombre d'actions absent du registre** — cité sur 138 vérification(s) de capacité
- **résultat attribuable au groupe non extrait** — cité sur 46 vérification(s) de capacité
- **BPA publié non extrait** — cité sur 44 vérification(s) de capacité
- **couverture du dividende : non_calculable** — cité sur 41 vérification(s) de capacité
- **flux de trésorerie opérationnel non extrait** — cité sur 28 vérification(s) de capacité
- **capitaux propres non extraits** — cité sur 21 vérification(s) de capacité
- **cours publié absent** — cité sur 10 vérification(s) de capacité
- **résultat net non extrait** — cité sur 8 vérification(s) de capacité

## Détail des conditions non remplies

### Décrire le marché (cours, PER publié, rendement, liquidité)
- 4 société(s) : PER non publié au BOC
- 2 société(s) : cours publié absent

### Calculer la capitalisation boursière
- 46 société(s) : nombre d'actions absent du registre
- 2 société(s) : cours publié absent

### Calculer un PER par SIGMA (et non reprendre celui du BOC)
- 46 société(s) : résultat attribuable au groupe non extrait
- 46 société(s) : nombre d'actions absent du registre
- 2 société(s) : cours publié absent

### Ancre patrimoniale (capitaux propres par action)
- 46 société(s) : nombre d'actions absent du registre
- 21 société(s) : capitaux propres non extraits

### Ancre bénéfice (BPA × multiple borné)
- 44 société(s) : BPA publié non extrait
- 2 société(s) : cours publié absent

### Ancre dividende (actualisation bornée par l'historique propre)
- 4 société(s) : historique de dividendes absent
- 2 société(s) : cours publié absent

### Qualité du bénéfice (trésorerie cumulée vs résultat cumulé)
- 28 société(s) : flux de trésorerie opérationnel non extrait
- 8 société(s) : résultat net non extrait

### Dividende soutenable (couverture par la trésorerie)
- 41 société(s) : couverture du dividende : non_calculable
- 7 société(s) : couverture du dividende : reperes_calculables

## Lecture

Une capacité à 0 % n'est pas un bug d'affichage : c'est un champ source qui
manque. Tant que le registre du nombre d'actions reste à 2 sociétés sur 48,
**la capitalisation, le PER calculé par SIGMA et l'ancre patrimoniale restent
inaccessibles** — quel que soit le nombre d'écrans ajoutés.


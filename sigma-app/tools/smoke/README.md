# Smoke test de rendu (jsdom)

Ces deux scripts exécutent réellement `app.js` dans un DOM, avec le vrai
`web/data/data.json` servi par un `fetch` simulé. Ils détectent ce que les tests
Python ne peuvent pas voir : une erreur JavaScript au rendu.

Ils sont **hors du périmètre pytest** parce qu'ils demandent Node.js, qui n'est
pas une dépendance du projet. À lancer quand on touche au front.

```bash
cd sigma-app/tools/smoke
npm install
npm run accueil   # accueil : 5 items de nav, bloc « sociétés à étudier », ordre des cartes
npm run vues      # parcourt les 8 vues + une fiche société, échoue sur erreur JS
```

## Ce que ces scripts ont déjà trouvé

- `structuredClone` absent sur Safari < 15.4 et certains WebView Android :
  l'application **entière** échouait au chargement (`EVAL: structuredClone is not defined`).
  Corrigé par un repli `cloneSur()` dans `app.js`.

## Limite assumée

jsdom n'applique pas la mise en page CSS : ces scripts ne prouvent **pas** qu'un
élément ne déborde pas visuellement. Le rendu visuel se valide par une capture
sur téléphone ou dans un navigateur de bureau.

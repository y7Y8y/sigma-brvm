# Mettre SIGMA en ligne pour de bon — 3 minutes, 6 clics

**Pourquoi cette page existe :** l'adresse que je vous donne (`…e2b.app`) est celle de **mon** environnement de travail. Elle meurt quand la session s'arrête — c'est exactement ce que vous avez vu avec l'erreur `502 SANDBOX NOT FOUND`. Pour une adresse permanente, gratuite et à vous, il faut GitHub Pages.

**Ce qui est déjà prêt de mon côté :**

- `index.html` à la racine : redirige automatiquement vers l'application. Une fois Pages actif, c'est cette page qui s'ouvre.
- Les deux workflows GitHub corrigés, prêts à copier : `docs/github-workflows-a-installer/`.
- J'ai **tenté d'activer Pages pour vous** : refusé par GitHub (`403 Resource not accessible by integration`). Mon accès n'a pas les droits d'administration du dépôt. Ce n'est pas un manque de volonté, c'est une limite technique — et c'est vous, propriétaire du dépôt, qui avez le bouton.

---

## Étape 1 — Activer Pages (2 clics)

1. Allez sur **https://github.com/y7Y8y/sigma-brvm/settings/pages**
2. Section **Build and deployment** → **Source** : choisissez **Deploy from a branch**
3. **Branch** : `main` · **Folder** : `/ (root)` → **Save**

Au bout d'une minute, votre application sera en ligne ici :

```
https://y7y8y.github.io/sigma-brvm/
```

Je l'ai testé localement : la racine redirige bien vers l'application, la page et les 4 Mo de données répondent. Le chemin est validé.

## Étape 2 — Rendre les automatismes possibles (optionnel, plus tard)

**Ce que j'ai découvert aujourd'hui, et qui explique votre remarque :** les workflows GitHub existaient, mais dans `sigma-app/.github/workflows/`. GitHub ne lit **que** `.github/workflows/` à la racine du dépôt. Ils n'ont donc **jamais tourné** — ce n'était pas un report décidé, c'était un emplacement faux. Bug réel, corrigé dans les fichiers prêts à installer.

**Pourquoi je ne peux pas les installer moi-même :** GitHub refuse qu'une application écrive dans `.github/workflows/` sans la permission `workflows` (message reçu : *refusing to allow a GitHub App to create or update workflow … without `workflows` permission*). Deux solutions :

- **A.** Reconnecter GitHub dans Arena avec la permission « workflows » — puis je les installe, je les teste, et je ne vous en parle plus.
- **B.** Vous copiez les deux fichiers à la main : sur GitHub, bouton **Add file → Create new file**, tapez `.github/workflows/pages.yml`, collez le contenu de `docs/github-workflows-a-installer/pages.yml`. Idem pour `update-data.yml`.

**Important sur la collecte automatique :** elle est volontairement **désarmée**. Le job s'arrête net si la variable de dépôt `SIGMA_COLLECTE_ACTIVE` ne vaut pas `oui` (Settings → Secrets and variables → Actions → Variables). C'est le respect de votre décision du 24/10 : activation après la v1.5. Le jour où vous voulez, vous passez la variable à `oui` — et je peux la relire avec vous avant.

---

## Garder l'app sur votre téléphone

Une fois l'adresse GitHub Pages active :

- **Android / Chrome** : menu ⋮ → « Installer l'application »
- **iPhone / Safari** : Partager → « Sur l'écran d'accueil »

Elle s'ouvre ensuite en plein écran, sans barre d'adresse, et fonctionne **hors ligne** avec la dernière collecte connue (service worker validé par 10 tests).

## Ce que je vérifierai après votre clic

Dès que Pages est actif, je teste l'URL publique : page, service worker, manifeste, icônes, chargement des données, et je vous confirme que l'installation PWA est possible depuis l'extérieur — la seule case que je n'ai pas pu fermer sans navigateur.

# SIGMA — déploiement GitHub (collecte quotidienne + site)

Objectif : pousser ce dossier `sigma-app` dans un dépôt GitHub à toi. Ensuite :

- `.github/workflows/update-data.yml` collecte les sources officielles BRVM les jours ouvrés, met à jour `web/data/data.json` et `web/data/boc_archive.json`, puis commit uniquement si les données ont changé.
- `.github/workflows/pages.yml` publie le dossier `web/` en site GitHub Pages.

## Ce dont SIGMA a besoin de ta part

1. Un compte GitHub.
2. Un dépôt Empty, par exemple `sigma-brvm`.
   - Public : le plus simple pour GitHub Pages gratuit.
   - Privé : possible selon ton offre GitHub ; vérifie que Pages est disponible.
3. Le premier envoi du dossier depuis ton ordinateur (commandes ci-dessous) ou via l’upload du site GitHub.

Ne colle jamais ton mot de passe ni un token GitHub dans une conversation. L’assistant ne peut pas pousser à ta place sans tes accès, et il ne doit pas les recevoir.

## Premier envoi depuis ton ordinateur

Après avoir décompressé l’archive SIGMA, ouvre un terminal dans le dossier `sigma-app` :

```bash
git init
git branch -M main
git add .
git commit -m "SIGMA BRVM — version initiale"
git remote add origin https://github.com/TON-UTILISATEUR/sigma-brvm.git
git push -u origin main
```

Remplace `TON-UTILISATEUR` par ton identifiant GitHub. GitHub peut demander une authentification : utilise GitHub Desktop, SSH, ou un token créé par toi dans ton gestionnaire d’identifiants local — pas dans le chat.

## Réglages à activer dans GitHub

Dans le dépôt :

1. **Settings → Actions → General → Workflow permissions** : choisir **Read and write permissions** (le workflow de collecte doit pouvoir committer les données).
2. **Settings → Pages → Build and deployment → Source** : choisir **GitHub Actions**.
3. Onglet **Actions** :
   - lancer manuellement **SIGMA — collecte BRVM quotidienne** (`workflow_dispatch`) une première fois ;
   - puis lancer **SIGMA — publier l'app (GitHub Pages)** si la publication n’a pas déjà été déclenchée par le push.

L’URL finale ressemble à :

```text
https://TON-UTILISATEUR.github.io/sigma-brvm/
```

## Fonctionnement ensuite

- Collecte planifiée : lundi à vendredi à 18:20 UTC, seconde tentative à 21:20 UTC (Abidjan = UTC).
- Publication Pages : après les collectes (19:05 et 22:05 UTC), après tes pushes sur `main`, ou manuellement.
- L’archive BOC longue est cumulative : la première collecte vise 260 séances ; les suivantes fusionnent surtout les 30 BOC récents et conservent l’historique dans `web/data/boc_archive.json`.
- Tes données personnelles de l’app (portefeuille saisi, journal, réglages) restent dans le navigateur via `localStorage` ; elles ne sont pas envoyées à GitHub.

## Si tu veux que je t’aide après création du dépôt

Donne-moi uniquement l’URL publique du dépôt (ex. `https://github.com/TON-UTILISATEUR/sigma-brvm`) et, si elle existe, l’URL GitHub Pages. Je pourrai vérifier publiquement que les workflows et le site répondent. Aucun secret nécessaire.

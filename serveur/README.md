# Serveur du paintball en ligne (Cloudflare)

Worker Rust (`worker` 0.9, WebAssembly) + un Durable Object par salon + D1 + Static Assets (offre gratuite, sans carte bancaire).

- `src/web.rs` : routes HTTP (Google OpenID Connect, sessions, CSRF, liste autorisée, salons et liens permanents, tickets WebSocket, fichiers du jeu).
- `src/salle.rs` : Durable Object `Salle`, WebSockets hibernables, alarmes (déconnexions, durée maximale).
- `src/regles.rs` : règles et contrôles anti-triche, sans dépendance au runtime (testés avec `cargo test`).
- `src/google.rs`, `src/jeton.rs`, `src/acces.rs`, `src/balistique.rs`, `src/qr.rs` : vérification RS256 des ID tokens, jetons HMAC, droits, balistique (copie de `BalistiquePaintball.cs`), QR code SVG.
- `migrations/` : schéma D1. `PROTOCOLE.md` : routes et messages. `MESURES.md` : mesures de charge.

## En local

Prérequis : Rust avec la cible `wasm32-unknown-unknown`, `cargo install worker-build`, Node 22+ (`npm install`).

```bash
./outils/init-dev.sh
```

```bash
npm run dev
```

`init-dev.sh` crée `.dev.vars` (clé de session aléatoire, `MODE_DEV=1`) et la base D1 locale. `MODE_DEV=1` ouvre `/auth/dev?email=…`, connexion sans Google, seulement sur `localhost` / `127.0.0.1`, et toujours soumise à la liste autorisée.

Tests :

```bash
cargo test
```

```bash
node outils/test-integration.mjs
```

```bash
node outils/charge.mjs --joueurs 8 --duree 30
```

Préparer le build WebGL dans `jeu/` (lit `../publication/` sans y écrire), puis relancer `wrangler dev` :

```bash
npm run preparer-jeu
```

Le jeu est alors servi sur http://127.0.0.1:8787/ .

## Déploiement : ce qui vous revient

Rien n'est déployé sans votre accord. Les secrets ne passent jamais par le dépôt ni par le chat : `wrangler secret put` les demande dans le terminal.

1. **Compte Cloudflare** et connexion :
   ```bash
   npx wrangler login
   ```
2. **Domaine** (recommandé) : un domaine ou sous-domaine sur Cloudflare (ex. `paintball.exemple.fr`), routé vers le Worker. Sans domaine, l'adresse `*.workers.dev` fonctionne aussi. Reporter l'adresse retenue dans `ORIGINE` (`wrangler.toml`).
3. **Client OAuth Google** (console Google Cloud → API et services → Identifiants → ID client OAuth, type « Application Web ») :
   - origine JavaScript autorisée : la valeur de `ORIGINE` ;
   - URI de redirection autorisée : `ORIGINE` + `/auth/google/retour` ;
   - écran de consentement : portées `openid`, `email`, `profile` ; en mode « Test », ajouter les e-mails des joueurs comme utilisateurs test, ou publier l'application.
   - Reporter l'ID client dans `GOOGLE_CLIENT_ID` (`wrangler.toml`, il est public).
4. **Ressources** :
   ```bash
   npx wrangler d1 create paintball
   ```
   Reporter le `database_id` affiché dans `wrangler.toml`, puis :
   ```bash
   npx wrangler d1 migrations apply paintball --remote
   ```
5. **Secrets** :
   ```bash
   npx wrangler secret put GOOGLE_CLIENT_SECRET
   ```
   ```bash
   npx wrangler secret put CLE_SESSION
   ```
   `CLE_SESSION` : au moins 32 caractères aléatoires, par exemple la sortie de `openssl rand -base64 48`. La changer déconnecte tout le monde (les liens de salon, eux, restent valables).
6. **Déploiement** (après votre accord) : préparer le build, puis déployer (le Worker et le jeu partent ensemble) :
   ```bash
   npm run preparer-jeu
   ```
   ```bash
   npx wrangler deploy
   ```

L'admin est `ADMIN_EMAIL` (`wrangler.toml`), seul et non délégable ; il ne peut pas être retiré par l'API. Il ajoute les autres e-mails (`POST /api/autorises`), crée et supprime les salons ; chaque salon a un lien permanent et son QR code.

## Sécurité

- Connexion Google côté serveur : flux code d'autorisation + PKCE, `state` et `nonce` dans un cookie signé de 10 min ; ID token vérifié (RS256 avec les clés publiques Google, `iss`, `aud`, `exp`, `nonce`, `email_verified`).
- Le jeu entier (solo compris) n'est servi qu'aux comptes connectés : sans session, la page d'accueil propose la connexion Google et aucun fichier du build n'est servi (cache navigateur `private`). Un compte Google hors liste voit « Accès non autorisé » et peut changer de compte.
- Seul `ADMIN_EMAIL` est admin : il gère la liste autorisée et les salons ; ce rôle ne se délègue pas.
- Sans lien de salon, seuls l'admin et les e-mails de la liste se connectent (Google). Le lien d'un salon ouvre, sans Google, une session invité liée au salon (cookie signé, HttpOnly) : accès au salon et au jeu entier tant que le salon existe. Régénérer le lien ou supprimer le salon révoque ses sessions invité et ferme leurs connexions ; 200 invités au plus par salon.
- Session : cookie `__Host-psv` HttpOnly, Secure, SameSite=Lax, jeton HMAC-SHA256 + ligne D1 (révocable : déconnexion, retrait de la liste). Durée 14 jours.
- CSRF : en-tête `X-CSRF` (HMAC de l'identifiant de session) sur toute requête autre que GET, plus contrôle de l'en-tête `Origin`.
- Liens de salon : clé aléatoire de 128 bits stockée en base, permanente, invalidée par la suppression du salon. `Referrer-Policy: same-origin` évite la fuite du lien.
- WebSocket : ticket signé de 60 s lié au salon et au compte, origine contrôlée. Le DO n'est joignable que par le Worker.
- Limites de débit (bindings `ratelimits`) : 20/min par IP sur `/auth/google*` et `/s/*` ; 60/min par compte sur les POST et ouvertures de WebSocket.
- Le serveur ne fait pas confiance au client : déplacements bornés, cadence de tir, trajectoire et temps de vol recalculés pour chaque touche (détails dans `PROTOCOLE.md`).
- Limites connues : un client modifié peut viser automatiquement (aimbot) ou tirer depuis une position plausible mais fausse ; le contrôle reste celui d'un jeu entre amis.

## Diffusion du jeu (Static Assets)

Pas de R2 (il exige une carte bancaire) : le build part avec le Worker, en Static Assets, gratuits. Ceux-ci limitent chaque fichier à 25 Mio alors que `publication.data.unityweb` en fait ~100 : `outils/preparer-jeu.mjs` découpe chaque fichier en morceaux de 20 Mio (`jeu/m/`) et écrit `jeu/manifeste.json`. Le Worker (`run_worker_first`, seul point d'entrée) recolle les morceaux dans un `FixedLengthStream` par `pipeTo`, copie faite par le runtime sans passer par le WASM : `Content-Length` exact, temps CPU négligeable.

`Build/*` est servi sous `Build/<empreinte>/` (cache `public, max-age=31536000, immutable`) et `index.html`, réécrit pour pointer vers ces chemins, en `no-cache` (revalidé par ETag). Les `.unityweb` détectés Brotli ou Gzip sont transmis tels quels (`encodeBody: manual`) aux navigateurs qui annoncent `br` ; sinon octets bruts, décompressés par le loader Unity. Chaque déploiement remplace le build précédent.

Offre gratuite : 100 000 requêtes Worker par jour (chaque fichier du jeu en compte une) et 100 000 requêtes Durable Object par jour, les messages WebSocket entrants comptant pour 1/20 de requête. Une manche de 8 joueurs à 30 Hz reçoit ~290 messages/s, soit ~52 000 requêtes DO par heure : environ 2 h de manches pleines par jour.

Le mode en ligne exige que le jeu soit servi par le Worker (même origine que l'API). La version sur GitHub Pages peut rester pour le solo.

## Mesures en production

Avant de retenir l'architecture pour le FPS, refaire les mesures sur Cloudflare (voir `MESURES.md`) avec l'environnement séparé `mesure` (worker et base distincts, comptes `@charge.test` seulement) :

```bash
npx wrangler d1 create paintball-mesure
```

Reporter l'identifiant et l'adresse `workers.dev` dans `[env.mesure]` de `wrangler.toml`, puis :

```bash
npx wrangler d1 migrations apply paintball-mesure --remote --env mesure
```

```bash
npx wrangler secret put CLE_SESSION --env mesure
```

```bash
npx wrangler secret put CLE_MESURE --env mesure
```

```bash
npx wrangler deploy --env mesure
```

```bash
CLE_MESURE=… node outils/charge.mjs --base https://<adresse-mesure> --joueurs 8 --duree 60
```

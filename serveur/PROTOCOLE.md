# Protocole du paintball en ligne

Référence pour le client Unity WebGL (`unity/Assets/Chateau/Scripts/`, `reseau.js`). Le serveur fait autorité : le client propose (positions, tirs, touches), le serveur valide et diffuse. Implémentation : `src/web.rs` (HTTP), `src/salle.rs` (Durable Object d'un salon), `src/regles.rs` (salon, manches, contrôles).

## Modèle : salons et manches

- Un **salon** est créé par l'admin (`ADMIN_EMAIL`, lui seul). Il a un nom et un **lien permanent** `/s/<clé>`. Il reste actif tant que l'admin ne le supprime pas ; la suppression invalide le lien, retire l'accès de ses membres et ferme les connexions (code 4004).
- Ouvrir le lien rend **membre** du salon. **Sans session, aucune connexion Google n'est demandée** : le lien ouvre une session invité (cookie signé, HttpOnly, liée à ce salon). Un compte déjà connecté (admin, inscrit) devient membre avec son compte. Un membre a accès au salon **et au jeu entier** (exploration libre, bots) tant que le salon existe.
- Hors lien de salon, rien n'est servi sans connexion Google d'un compte autorisé (page de connexion).
- L'admin peut **régénérer le lien** : l'ancien ne marche plus, les invités entrés par lui sont exclus (sessions révoquées, connexions fermées en 4005). La suppression du salon révoque aussi toutes ses sessions invité.
- Seul l'admin voit la liste de tous les salons. Un membre ne voit que les siens.
- Dans le salon, chacun choisit un **pseudo** et une **couleur**, modifiables à tout moment.
- Le salon enchaîne des **manches**. N'importe quel membre présent lance une manche, même seul (il se promène et tire en attendant les autres). On peut **entrer dans une manche en cours**. À la fin d'une manche, n'importe quel membre présent lance la suivante.

## Conventions

- Unités : mètres, secondes, degrés. Repère Unity (Y vers le haut).
- **Position d'un joueur** = pied du personnage (base du `CharacterController`), pas la caméra. Gabarit enfant : 1,50 m, yeux à 1,40 m.
- `h` : horloge du serveur, millisecondes Unix. `c` (dans `ping`/`pong`) : horloge libre du client, renvoyée telle quelle.
- Numéro de joueur `j` : entier 0-255 attribué par le salon à chaque compte, stable tant que le salon existe. Les e-mails ne sont jamais diffusés aux autres joueurs, seulement les pseudos.
- Couleurs : `c` de 0 à 5 (cyan, rose, jaune, vert, violet, orange, dans l'ordre du menu).

## Choix du format : JSON compact sur WebSocket texte

- Lisible par `JsonUtility` (une classe C# plate qui réunit tous les champs, aiguillée par `t`) et dans les outils réseau du navigateur.
- Taille mesurée : ~104 octets par position ; le serveur regroupe les positions dans un message `ps` toutes les 50 ms (~870 octets à 8 joueurs, ~17 ko/s par client).
- Les champs inconnus sont ignorés : on peut ajouter des champs sans casser les clients.

## HTTP

Le jeu est servi par le Worker (même origine) : cookies de session et contrôle d'origine en dépendent. Les `fetch` du jeu sont same-origin avec `credentials: 'same-origin'` (par défaut).

| Méthode et chemin | Qui | Rôle |
|---|---|---|
| `GET /` et fichiers du build | admin, inscrit ou membre d'un salon | Jeu WebGL. Sans session valide : `/` affiche une page « Se connecter avec Google » (401), les autres fichiers répondent 401 |
| `GET /auth/google?retour=/…` | tous | Redirige vers Google (state, nonce, PKCE) |
| `GET /auth/google/retour` | Google | Vérifie l'ID token, ouvre la session si le compte a un droit (sinon page « Accès non autorisé ») |
| `POST /auth/deconnexion` | connecté | Révoque la session |
| `GET /s/<clé>` | tous | Lien du salon : rend membre puis redirige (303) vers `/?salon=<id>`. Sans session : ouvre une session invité (pas de Google). Clé inconnue ou salon supprimé : 410. Limité à 20/min par IP ; 200 invités au plus par salon (429) |
| `GET /api/moi` | connecté | `{email, nom, admin, droit, invite, csrf}` ; `droit` : `admin`, `autorise` (liste) ou `membre` (lien de salon seulement) ; invité : `invite: true`, `email: null` |
| `GET /api/salons` | connecté | Admin : tous les salons `{id, nom, lien, membres, manches, cree_le}`. Autres : leurs salons `{id, nom}` |
| `POST /api/salons` `{nom}` | admin | Crée un salon → `{id, nom, lien, qr_svg}` (nom : 1 à 60 caractères) |
| `GET /api/salons/<id>` | membre ou admin | `{salon: {id, nom, manches}, membres: [{pseudo, c}], manches: [{numero, fin, gagnant, raison, classement}]}` (10 dernières) ; l'admin reçoit aussi `lien` |
| `GET /api/salons/<id>/qr.svg` | admin | QR code du lien (`image/svg+xml`) |
| `POST /api/salons/<id>/lien` | admin | Régénère le lien → `{lien, qr_svg}` ; ancien lien invalide, invités exclus |
| `POST /api/salons/<id>/supprimer` | admin | Supprime le salon : lien invalide, membres retirés, connexions fermées (4004) |
| `POST /api/salons/<id>/ticket` | membre ou admin | `{ticket, ws, expire}` : URL WebSocket valable 60 s |
| `GET /api/autorises` | admin | Liste autorisée |
| `POST /api/autorises` `{email}` | admin | Ajoute à la liste (le rôle admin ne se délègue pas) |
| `POST /api/autorises/retirer` `{email}` | admin | Retire de la liste et de tous les salons, révoque ses sessions |

Toute requête autre que GET exige l'en-tête `X-CSRF: <csrf de /api/moi>` ; un en-tête `Origin` différent de l'origine du site est refusé (403). Corps JSON ≤ 4 ko. Erreurs : `{"erreur": "…"}` avec 400, 401, 403, 404, 410, 429.

Parcours du client au lancement :
1. Lire `salon` dans l'URL (`?salon=<id>`). Sans paramètre : menu habituel (solo, bots, exploration) ; le bouton « En ligne » liste `GET /api/salons`.
2. `GET /api/moi` (la page n'est servie qu'à une session valide). Un invité (`invite: true`) n'a pas d'écran de connexion : il va directement au choix du pseudo et de la couleur dans son salon, et n'a pas de bouton « Se déconnecter » vers Google. Un 401 ici signifie une session expirée ou révoquée : pour un compte Google, `location = '/auth/google?retour=' + encodeURIComponent(location.pathname + location.search)` ; pour un invité, afficher « Lien expiré, demandez le nouveau lien à l'organisateur ».
3. `POST /api/salons/<id>/ticket` avec `X-CSRF`, puis `new WebSocket(ticket.ws)`.
4. À chaque reconnexion, redemander un ticket (il expire en 60 s).

## WebSocket : client → serveur

| `t` | Champs | Quand | Contrôles |
|---|---|---|---|
| `ping` | `c` | 1 à 2 fois/s | Réponse `pong` |
| `profil` | `pseudo` (facultatif), `c` couleur 0-5 (facultatif) | à tout moment | Pseudo : 2 à 16 caractères (lettres, chiffres, espace, `-`, `_`, `'`, `.`), espaces superflus retirés, unique dans le salon (sans tenir compte de la casse). Couleur : refusée si un autre joueur présent l'a déjà, tant qu'une couleur reste libre |
| `lancer` | `spawns: [[x,y,z,lacet], …]` (1 à 64) | phase `attente` ou `fin`, tout membre présent | ≥ 1 joueur présent ; coordonnées finies. Les joueurs présents (8 au plus) entrent dans la manche |
| `entrer` | | phase `en_cours`, joueur présent hors manche | Entre dans la manche en cours (voir règles). Refus : `manche complète`, `déjà éliminé` |
| `p` | `q` numéro croissant, `p: [x,y,z]`, `r: [lacet, tangage]`, `v: [vx,vy,vz]` | 20 à 30 Hz, toujours | Pendant une manche, pour un joueur en jeu : déplacement ≤ 25 m/s (+1 m, fenêtre mini 0,25 s), sinon `corr` et pas de relais. Les spectateurs ne sont pas relayés |
| `tir` | `id` unique par joueur, `o: [x,y,z]` bouche du marqueur, `d: [dx,dy,dz]` unitaire, `v` vitesse initiale (85,344 par défaut) | à chaque bille | Manche en cours, joueur en jeu et en vie ; `o` à ≤ 5 m de la dernière position ; ‖d‖ ∈ [0,9 ; 1,1] ; `v` ∈ [10 ; 95] ; rafale 10, puis 9 tirs/s |
| `touche` | `tir` (id), `cible` (j), `pt: [x,y,z]` point d'impact | quand la simulation locale du tireur voit la bille toucher un adversaire | voir ci-dessous |
| `stats` | | mesures | Compteurs du DO |

Validation d'une `touche` (constantes en tête de `src/regles.rs`) :
- le tir existe, appartient au déclarant, n'a pas déjà touché ; cible en jeu dans la manche, autre que soi, non éliminée ;
- `pt` est à ≤ 0,3 m de la trajectoire balistique recalculée par le serveur depuis `o`, `d`, `v` (même modèle que `BalistiquePaintball.cs` : 240 Hz, point milieu, Cd 0,47) ; on en déduit le temps de vol ;
- délai entre réception du tir et de la touche compris entre temps de vol − 200 ms et temps de vol + 1,5 s ;
- la cible n'est pas protégée : 1,5 s après chaque apparition (départ, entrée en cours de manche, respawn) ;
- compensation de latence : la cible a annoncé, entre 800 ms avant et 200 ms après l'impact estimé, une position à ≤ 1 m horizontalement de `pt`, avec `pt.y − y` ∈ [−0,3 ; 1,8] ; si elle n'a rien annoncé dans cet intervalle, sa dernière position connue fait foi (un joueur muet reste touchable).

Un message refusé renvoie `refus`. Au-delà de 50 refus pour faute (message invalide, triche probable), la connexion est fermée (code 4008). Les refus « normaux » (cible protégée, hors manche, pseudo pris…) ne comptent pas.

## WebSocket : serveur → client

| `t` | Champs | Destinataires |
|---|---|---|
| `bienvenue` | `j` (votre numéro), `h`, `salon: {id, nom}`, `pseudo`, `c`, `en_jeu`, `spawn` (si vous êtes en jeu dans la manche en cours), `regles: {vies, points_par_touche, invulnerabilite_ms, duree_max_ms, joueurs_max}` | vous, à la connexion |
| `etat` | `phase` (`attente`, `en_cours`, `fin`), `manche` (numéro, 0 avant la première), `debut` (h du départ), `cible`, `vies`, `joueurs: [{j, pseudo, c, connecte, en_jeu, vies, points, elimine}]` (présents et joueurs de la manche), `fin` (`{gagnant, raison, h}` ou null) | tous, à chaque changement |
| `pong` | `c`, `h` | vous |
| `debut` | `manche`, `h`, `cible`, `vies`, `joueurs: [{j, spawn: [x,y,z,lacet]}]` | tous ; les joueurs listés se placent à leur `spawn`, les autres restent spectateurs (ils peuvent `entrer`) |
| `entree` | `j`, `spawn`, `cible` (nouvelle cible), `h` | tous ; le joueur `j` se place à `spawn` |
| `ps` | `h`, `l: [{t:"p", j, q, p, r, v, h}, …]` : dernière position de chaque joueur ayant bougé depuis le lot précédent (y compris la vôtre : l'ignorer) | tous, au plus toutes les 50 ms |
| `corr` | `p` dernière position acceptée | vous ; s'y replacer |
| `tir` | `j`, `id`, `o`, `d`, `v`, `h` | les autres : simuler la bille pour l'affichage (pas de dégâts locaux) |
| `touche` | `tireur`, `cible`, `tir`, `pt`, `o` (origine du tir), `vies` (de la cible), `points` (du tireur), `elimine`, `spawn` (null si éliminé), `h` | tous ; la cible se téléporte à `spawn` ; « touché par qui et d'où » : `tireur` et `o` |
| `elimine` | `j`, `raison` (`deconnexion`) | tous |
| `fin` | `manche`, `gagnant` (j ou null), `raison` (`points`, `dernier survivant`, `aucun survivant`, `temps`), `h`, `classement: [{j, pseudo, points, vies}]` | tous |
| `refus` | `raison`, `ref` (type du message refusé) | vous |
| `fermeture` | `code`, `raison` : envoyé juste avant une fermeture décidée par le serveur (4001, 4003, 4004, 4005, 4008), l'événement `close` du navigateur pouvant arriver plus tard | vous |
| `stats` | `recus`, `envoyes`, `depuis`, `joueurs`, `h` | vous |

Codes de fermeture : 4001 connexion remplacée (même compte ouvert ailleurs), 4003 entrée refusée (salon plein : 16 connexions), 4004 salon supprimé, 4005 lien renouvelé (invités exclus), 4008 trop de refus.

## Règles d'une manche (src/regles.rs, `Regles::default`)

- 3 vies par joueur, 2 à 8 joueurs en jeu.
- Une touche validée : −1 vie pour la cible, +1 point pour le tireur, réapparition de la cible à un point choisi au hasard dans la liste de `lancer`, de préférence à plus de 8 m des adversaires en vie et à plus de 12 m du lieu de la mort. Unity fournit ces points avec `PartieBots.PointsApparition(n)` (64 au plus, château compris).
- À 0 vie : éliminé (spectateur jusqu'à la manche suivante, ses `p` et `tir` sont ignorés).
- **Cible de victoire** = `floor(3 × N / 2)`, où N est le nombre de joueurs entrés dans la manche (éliminés et départs compris). Elle est recalculée à chaque entrée et **ne baisse jamais** pendant la manche : un départ ne peut pas faire gagner quelqu'un d'un coup, une arrivée repousse l'objectif pour tous.
- **Entrée en cours de manche** : 3 vies, 0 point, point d'apparition loin des autres, 1,5 s de protection. Une seule entrée par compte et par manche : un joueur déjà entré (même éliminé) ne peut pas revenir avec des vies neuves ; s'il se reconnecte, il retrouve ses vies et ses points.
- Fin : premier à la cible ; sinon dernier survivant (si au moins deux joueurs sont entrés) ; au bout de 10 min, meilleur score (égalité possible). Un joueur en jeu déconnecté plus de 30 s est éliminé.
- Seules les touches sur un adversaire rapportent un point (règle confirmée le 16 novembre 2026). Ces choix sont des champs de `Regles` (`points_par_touche`, `victoire_aux_points`, `victoire_dernier_survivant`, `duree_max_ms`…).

## Séquences

Arrivée : lien `/s/<clé>` → `/?salon=<id>` (session invité si besoin, sans Google) → ticket → WebSocket → `bienvenue` + `etat`. Le client propose de choisir pseudo et couleur (`profil`) ; pseudo par défaut : le prénom Google, ou « Invité » (numéroté) pour un invité.

Manche : un membre présent envoie `lancer` avec les points d'apparition de la scène → tous reçoivent `debut` puis `etat`. Un membre arrivé pendant la manche voit `etat.phase = en_cours` et peut envoyer `entrer` → tous reçoivent `entree` et `etat` (nouvelle cible). Fin → `fin` + `etat` (phase `fin`) ; n'importe quel membre présent peut relancer avec `lancer`.

Positions : envoyer `p` à 20-30 Hz. Les positions des autres arrivent groupées (`ps`, 20 Hz au plus, délai 0 à 50 ms) : les afficher avec ~100 ms d'interpolation, en s'appuyant sur `h` de chaque entrée. Continuer d'envoyer `p` même immobile (au moins 5 Hz).

Tir : le tireur simule sa bille localement, envoie `tir` au départ ; les autres reçoivent `tir` et l'affichent. Si la bille locale du tireur touche un adversaire, il envoie `touche` ; tous reçoivent `touche` (ou le tireur reçoit `refus`). Une touche n'est affichée comme validée qu'à réception de `touche` du serveur.

Reconnexion : nouveau ticket, nouvelle WebSocket ; `bienvenue` rend le même `j`, l'état `en_jeu` et le `spawn` courant. Après 30 s d'absence pendant une manche, le joueur est éliminé.

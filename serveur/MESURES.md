# Mesures de charge du Durable Object

Outil : `outils/charge.mjs` (P parties de N bots ; positions à F Hz, 2 pings/s et 4 tirs/s par bot). Colonnes :
- **RTT** : ping → pong, aller-retour client → DO → client (ms, p50 / p95) ;
- **relais** : émission d'une position par un bot → réception par un autre bot, même horloge locale (ms, p50 / p95) ; inclut l'attente de l'envoi groupé (0 à 50 ms) ;
- **reçus / envoyés** : messages par seconde traités par le DO (compteurs du DO) ;
- **CPU** : processus workerd locaux (runtime qui exécute Worker et DO, proxy de wrangler), en % d'un cœur ; **ms/msg** = CPU runtime par message reçu.

## 16 novembre 2026, local (`wrangler dev`, workerd 1.20261116, build `--release`)

Machine : i7-13700H, 20 fils, **très chargée par d'autres travaux** (builds Unity, Chrome : load average 20 à 38 pendant les mesures). Les chiffres de latence varient donc beaucoup d'un run à l'autre ; les répétitions sont toutes données.

### Avant regroupement (chaque position relayée à N − 1 joueurs)

| Parties × joueurs | Fréquence | RTT p50 / p95 | Relais p50 / p95 | Reçus / envoyés par s | CPU runtime | CPU proxy | ms/msg |
|---|---|---|---|---|---|---|---|
| 1 × 4 | 30 Hz | 8,8 / 22,1 | 8,4 / 34,4 | 142 / 412 | 55 % | – | 3,9 |
| 1 × 2 | 30 Hz | 3,7 / 22,0 | 2,4 / 17,4 | 72 / 72 | 22,9 % | 2,4 % | 3,2 |
| 1 × 8 | 30 Hz | 7,4 / 309 | 6,5 / 356 | 287 / 1 917 | 56,7 % | 11,7 % | 2,0 |
| 1 × 8 | 20 Hz | 14,1 / 335 | 14,1 / 328 | 205 / 1 339 | 44 % | 8,8 % | 2,2 |
| 2 × 8 | 30 Hz | 3 001 / 5 886 | 2 981 / 6 273 | 561 / 3 738 | 69,2 % | 21 % | 1,2 |

Témoin : un DO JavaScript minimal qui fait le même relais (JSON.parse, diffusion aux autres) coûte **2,8 ms de CPU par message** dans le même environnement, contre 3,0 pour le DO Rust (4 joueurs, 30 Hz). Le coût vient donc du runtime local (WebSocket, proxy, inspecteur V8 actif sous wrangler dev), pas de Rust/WASM ni des contrôles de `regles.rs`.

### Après regroupement des positions (message `ps` toutes les 50 ms au plus)

| Parties × joueurs | Fréquence | RTT p50 / p95 | Relais p50 / p95 | Reçus / envoyés par s | CPU runtime | CPU proxy | ms/msg |
|---|---|---|---|---|---|---|---|
| 1 × 2 | 30 Hz | 12,1 / 38,2 | 23,6 / 52,4 | 70 / 45 | 23,4 % | 2,1 % | 3,3 |
| 1 × 4 | 30 Hz | 21,7 / 63,9 | 40,9 / 87,9 | 139 / 122 | 31,6 % | 3,2 % | 2,3 |
| 1 × 8 | 30 Hz | 48,7 / 317 | 76,6 / 286 | 278 / 363 | 39,1 % | 5,8 % | 1,4 |
| 1 × 8 | 30 Hz | 5,6 / 28,0 | 24,2 / 46,2 | 287 / 387 | 50,2 % | 5,6 % | 1,8 |
| 1 × 8 | 30 Hz | 8,2 / 84,7 | 29,9 / 93,6 | 284 / 379 | 44 % | 5,1 % | 1,6 |
| 1 × 8 | 30 Hz | 6,4 / 45,5 | 26,3 / 59,6 | 285 / 384 | 48,9 % | 5,6 % | 1,7 |
| 1 × 8 | 20 Hz | 40,5 / 168 | 69,5 / 196 | 202 / 366 | 36,4 % | 5,3 % | 1,8 |
| 2 × 8 | 30 Hz | 969 / 2 754 | 1 101 / 2 878 | 549 / 717 | 57 % | 9,6 % | 1,0 |
| 4 × 8 | 30 Hz | 13,8 / 52,2 | 31,9 / 84,8 | 1 148 / 1 520 | 83,1 % | 14,9 % | 0,7 |
| 4 × 8 | 30 Hz | 3 384 / 7 177 | 2 801 / 6 649 | 826 / 1 052 | 64,7 % | 12,3 % | 0,8 |
| 4 × 8 | 30 Hz | 3 041 / 5 251 | 3 123 / 5 045 | 1 069 / 1 370 | 69,8 % | 13,2 % | 0,7 |
| 4 × 8 | 30 Hz | 15,7 / 61,9 | 35,1 / 117 | 1 139 / 1 518 | 85,8 % | 15,1 % | 0,8 |

Taille des messages : position relayée ~104 octets ; lot `ps` de 8 joueurs ~870 octets, soit ~17 ko/s reçus par client à 20 lots/s.

## Lecture

- **Une partie de 8 joueurs à 30 Hz tient** en local : 3 répétitions sur 4 donnent un RTT p50 de 6 à 8 ms et un p95 de 28 à 85 ms, sans message refusé ni perdu (reçus ≈ attendus : 8 × 36 = 288/s).
- **Le regroupement divise par 5 les envois** à 8 joueurs (1 917 → ~380/s) et baisse le CPU du runtime (~57 → ~47 %). Coût : jusqu'à 50 ms de délai sur les positions (relais p50 ~25 ms), sans effet sur les tirs et touches, envoyés immédiatement. Le client doit interpoler les positions des autres joueurs (~100 ms de retard d'affichage).
- **Plusieurs parties locales partagent un seul fil** (workerd de dev) : à 2 ou 4 parties de 8, ce fil sature par moments et la file d'attente monte à plusieurs secondes (lignes bimodales ci-dessus : soit ~15 ms, soit plusieurs secondes, selon la charge de la machine). En production, chaque DO s'exécute à part ; la limite qui compte est celle **d'un DO, monothread** : ~290 messages reçus/s pour une partie pleine.
- Le coût mesuré par message (1 à 3 ms) est celui du runtime local, identique pour un DO JavaScript minimal ; il n'est pas transposable à la production.

## Statut : architecture provisoire, non validée pour le FPS

Les mesures locales ne suffisent pas à retenir l'architecture. Il reste à mesurer **sur Cloudflare** (environnement `mesure`, voir README), depuis une connexion en France, 1 × 8 et 4 × 8 à 30 Hz pendant 60 s, plusieurs fois. Critères proposés :
- RTT p95 < 80 ms et relais p95 < 120 ms ;
- aucun message perdu (reçus par le DO ≈ envoyés par les bots) ni fermeture ;
- temps CPU par requête du DO (tableau de bord Cloudflare, Durable Objects → métriques) très inférieur à 1 ms, pour garder de la marge sous un fil.

Si ces critères échouent : passer au binaire (taille ÷ 2,5), baisser les positions à 20 Hz côté client, ou sortir la diffusion des positions du DO (le DO gardant tirs, touches et vies).

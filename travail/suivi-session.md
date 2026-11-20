# Suivi de session — paintball (16/11/2026)

## Fait
- Mode paintball professionnalisé : marqueur Spyder MR100 (Sketchfab CC BY), `AnimationMarqueur.cs`, billes avec traînée, réticule `ReticulePaintball.cs`, menus/HUD refaits, sons ElevenLabs (`SonsPaintball.cs`, `scripts/sons_elevenlabs.py`), optimisations FPS (occlusion, LODGroup, HDR off, `ResolutionAdaptative.cs`). Détails : `README-PAINTBALL.md`, décision dans `DECISIONS.md`.
- Icône : `scripts/icone.py` → `assets/icone/` ; intégrée au template web.
- Parasols de terrasse rendus traversables (on restait coincé dessous) : `PaintballScene.Traversables()` + `ChateauScene.Preparer`.

## En cours
- Publication GitHub Pages sur `git@github.com:milardv/my-paintballSV.git` :
  - build de publication Brotli : `unity build unity --target WebGL --execute-method PaintballScene.BuildWebPublication` → `publication/` (le dossier `build/` est interdit en lecture).
  - Contrainte : fichier `.data` < 100 Mo (gzip donnait 115,7 Mo). Sinon : Git LFS + déploiement Pages par GitHub Actions.
  - Build Brotli : `.data` = 98,97 Mio, sous la limite. Poussé sur `main` et `gh-pages` (commit 2c5e205), dépôt local `/home/valm/IdeaProjects/my-paintballSV`.
  - EN LIGNE : https://milardv.github.io/my-paintballSV/ (dépôt public, Pages sur `gh-pages`). Testé dans Chrome : chargement ~30 s, partie lancée, tirs et touche OK. Pour republier : rebuild `BuildWebPublication`, copier `publication/` dans le dépôt, commit, push `main` et `main:gh-pages`.
- Sessions parallèles lancées :
  - `serveur-cloudflare` : Worker Rust (auth Google + liste blanche, parties, QR, scores), Durable Object WebSocket par partie, R2/CDN, mesures → `serveur/`.
  - `unity-match-bots` : mesures de fluidité, règles de match (3 vies, victoire à floor(total/2)), bots → `unity/`.

## À confirmer par Valentin
- Règle de partie coupée après « celui qui touche » : hypothèse = chaque touche donne 1 point au tireur, premier à floor(total/2) gagne.
- 3e personne : le robot provisoire masque encore une partie de l'arme ; remplacer par un personnage humain (proposé, refusé pour l'instant).

## 17/11 — en cours
- Jeu servi seulement par le Worker (https://paintball-saint-victor.marseille-tech.workers.dev), réservé aux comptes autorisés ; GitHub Pages = redirection. Déploiement : accord de Valentin dans la session serveur uniquement.
- Musique d'ambiance à la place des cigales (`scripts/musique_elevenlabs.py`).
- Demandé à la session Unity : cache de reseau.js, correctif pointer lock (alerte WrongDocumentError), taches de peinture sur les corps, podium de fin.
- Salons persistants déployés (Worker 083b5a77) : lien /s/<clé> sans Google, taches sur les corps, podium, correctif pointer lock. Reste : test réel d’un salon par Valentin.
- Publication 17/11 soir : nuit réelle, décor de nuit, chute des touchés, musique provençale ; Worker version 13af45a4 (build Brotli via outils/build-rapide.sh publication, puis npm run preparer-jeu et wrangler deploy dans serveur/).
- Publication 17/11 nuit : fenêtres éclairées, bassin, salon seul, build mobile ASTC (iPhone) ; Worker version 80bc7004.
- Publication 19/11 : relevé des plans d'évacuation, vestibule détaillé, portes moulurées, miroirs réfléchissants, escalier de service dans la cage est ; build batch `BuildMobile.PublierBatch` (ordinateur 120,9 Mo + mobile ASTC), `npm run preparer-jeu`, `wrangler deploy` ; Worker version 7f5dd061.

## 17/11 nuit — demandes en cours (dans l'ordre)
- [x] Données ouvertes (travail/donnees-ouvertes/, outils/donnees_ouvertes.py → travail/plan_mesure.json) : ortho IGN 13 cm, LiDAR HD MNT/MNS 50 cm, OSM (Overpass saturé).
      Recalage : centre toit = px LiDAR (258,6 ; 266,3), château tourné de 4,2° ; ortho_d003.jpg = ortho dans le repère D-003.
      Mesures : terrasse sud = RDC (26,85 m NGF), cour sud 1,55 m plus bas → ~10 marches de 15,5 cm (modèle : 8, 1,28 m).
- [x] Jardin recalé : 129 arbres LiDAR, bassin mesuré, cour sud jusqu'à y=30,5, allée est relevée ; terrasse (bord 12, palier 14,7), perron 10 marches, cour -1,55. Reste : extension est de la terrasse (mesurée x=19, modèle 23,5) non touchée (escalier est).
- [x] 2 voitures seulement, modelées par sections (parc.py).
- [x] Scooter (Scooter.cs) vérifié dans le navigateur (montée, conduite).
- [x] Escalier + trappe vers le toit (EscalierToit.cs), vérifié (arrivée à 15,8 m).
- [x] Nombre de vies réglable : accueil bots (1/2/3/5/10), salon en ligne (serveur `lancer.vies`, test vies_choisies_au_lancement). Serveur non déployé.
- [x] S'accroupir (C / Ctrl / bouton tactile) : non transmis en ligne (le protocole n'a pas de champ).
- [ ] Mise en ligne de la version mobile allégée : en attente d'accord.

## 18/11 — jardin et abords d'après les photos de Valentin
- Plan : `travail/plan_domaine.json` (limite de propriété recalée, tracés sur orthophoto IGN), contrôle `outils/plan_domaine_controle.py` → `travail/donnees-ouvertes/plan_domaine.jpg`. Données IGN retéléchargées sur 400 m (anciennes dans `travail/donnees-ouvertes-260m/`), `plan_mesure.json` avec `mnt_fin` (2 m).
- `parc.py` : limite (mur sur la route, grillage + haie ailleurs), portails, maison du gardien, local piscine, pétanque, grange + tracteur + outils, benne, camionnette, piscine en haricot, allées + bordures fleuries, tennis à -0,02 sur plateforme, 2 escaliers, relief LiDAR. Sauvegardes `travail/*avant_plan_domaine*`.
- `terrasse.py` : retour est x = 20, raccord ouest au tennis, pavés de verre (5), salon est déplacé. `gabarit.json` mis à jour.
- Unity : `GardesPortail.cs` (2 soldats kaki + portail + porte), NavMesh élargi, lieu « Le parc et la piscine ». Build complet lancé à 00:35.

## 20/11 — publication
Worker 10dce8c7 : jeu (petits personnages, gilet, butin, carte en grand, tyrolienne toit→bassin, fenêtres d'étage, portes recalées, QR par salon) et serveur (sans limite de temps, piano relayé).

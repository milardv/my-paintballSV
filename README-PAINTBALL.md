# Saint-Victor · Paintball solo web

Compiler : `unity build unity --target WebGL --execute-method PaintballScene.BuildWeb` (scène complète), ou `PaintballScene.BuildWebMiseAJour` (~6 min : réapplique marqueur, matériaux et optimisations sur la scène web existante).
Lancer : `./lancer-web.sh`, puis http://localhost:8086 . Clavier et souris sur ordinateur.
Livrable statique : dossier `build/web/` complet, à servir par HTTP(S).

Accueil : choisir une des six couleurs, le mode (**Entraînement** ou **Contre les bots**) puis **Jouer**. Entraînement : 90 secondes avec huit cibles réutilisables (100 points par touche, délai de 1,2 s par cible). Contre les bots : voir plus bas. Le château reste accessible et ses portes s'ouvrent avec E. Pas encore de réseau.

ZQSD sur AZERTY / WASD sur QWERTY ; souris : regard ; clic gauche : tirer (8 billes/s) ; clic droit : viser ; V : première / troisième personne ; Maj : courir ; Espace : sauter ; R : recharger (50 billes, 1,5 s, réserve illimitée) ; Échap : pause, reprise ou nouvelle partie. Les cibles ne doivent pas être touchées par un rayon instantané : les billes les atteignent après leur temps de vol.

Physique : mètres, kilogrammes, secondes. Bille de diamètre .68 pouce (17,272 mm), masse supposée de 3,2 g, départ 85,344 m/s (280 ft/s). Gravité 9,81 m/s², air 1,225 kg/m³, Cd sphérique constant 0,47 ; intégration au point milieu à 240 Hz et balayage sphérique sur chaque segment. Vent nul par défaut, réglable dans BalistiquePaintball. Le calibre et l'ordre de grandeur de la vitesse sont cohérents avec le manuel Tippmann : https://paintballsolutions.com/wp-content/uploads/2020/03/TP04405-TMC-68-Cal-OM-April-2018.pdf . La masse et le Cd sont des hypothèses de simulation : pas de calibration expérimentale, pas de portance Magnus ni de déformation de la bille.

Chaque bille conserve couleur et identifiant du tireur. Les impacts sont projetés sur le collider touché, suivent les objets mobiles, sont plafonnés à 256 et disparaissent à la nouvelle partie. Les billes actives sont plafonnées à 64. Mobilier : chaises et tables basses en corps physiques convexes, masse de 7 / 20 kg ; lampes 2 kg ; obstacles d'entraînement 3 / 12 kg. Le contact du joueur de 80 kg transmet une impulsion finie. Une caisse d'entraînement dispose d'une fixation faible (18 N·s cumulés) ; murs, grands éléments architecturaux et mobilier non explicitement préparé restent fixes. La règle de mobilité dépend de la masse et de la fixation, pas d'une chute automatique de tout objet touché.

Modèle animé CC0, marqueur et texture : `assets/paintball/PROVENANCE.md`.
Le build utilise WebGL 2 et une compression Gzip avec décompression de secours. Les recommandations de déploiement Unity sont disponibles ici : https://docs.unity.com/en-us/engine/6000.6/manual/platform-specific/webgl/building-distribution/deploying .

Optimisation web : les 282 images embarquées ont été extraites sans modification de pixels (`python3 outils/extraire-textures-web.py`), puis importées pour WebGL en DXT5 avec un maximum de 1024 px. Leurs matériaux sont remplacés dans la scène web seulement. Mesure Unity : 1 088 637 643 → 270 916 595 octets de mémoire de textures. Les GLB et textures originaux restent conservés. `travail/textures-web.json` et `travail/verification-balistique.json` contiennent les mesures.

Vérification fonctionnelle dans le navigateur : ajouter `?validation=1` à l'URL, puis cliquer sur Jouer. Le test exerce les projectiles et deux propriétaires/couleurs, le score, les marques, l'animation, le rechargement, la pause, l'effet de la masse, la chute et une fixation faible. Le résultat est exposé dans `window.paintballVerification`. L'état réel peut être relu via `window.paintballRead()` puis `window.paintballState`.

Validation du 16 novembre 2026 : build WebGL de 116,2 Mo ; Chrome 1280 × 720, zéro erreur d'exécution. `travail/verification-paintball-navigateur.json` : tous les contrôles passent, y compris animation réellement avancée et collision du joueur contre une caisse. Déplacement au clavier, bascule V, tirs, recharge R, pause/reprise Échap et écran de résultat à 90 s vérifiés manuellement dans le navigateur. Trois tirs supplémentaires sur le sol ont produit trois impacts sans augmenter le score ; capture `rendus/paintball-impact-sol.png`. Firefox, Safari et commandes tactiles non testés. Le jeu cible ici ordinateur, clavier et souris.

## Présentation (16 novembre 2026, soir)

- **Marqueur** : Spyder MR100 réel (Sketchfab, CC BY, voir `assets/paintball/PROVENANCE.md`), normalisé par `scripts/paintball_marqueur.py`. Pose procédurale `AnimationMarqueur` : en 3e personne l'arme suit le torse animé (marche, course), le buste s'incline vers la visée, les mains sont placées par IK (main gauche sur le réservoir pendant la recharge) ; en vue subjective balancement de marche, inertie du regard, visée épaulée, position basse en course, recul et geste de recharge.
- **Billes visibles** : affichées 2,1 fois plus grosses avec une traînée courte de leur couleur (shader `Chateau/Trainee`) ; la physique garde le vrai diamètre de 17,3 mm.
- **Réticule** `ReticulePaintball` : quatre branches dont l'écart est la dispersion réelle (déplacement, saut, cadence, visée), marqueur de touche, anneau de recharge, rouge quand le chargeur est vide.
- **Interface** : accueil avec survol lent du domaine, éclaboussure et bouton Jouer à la couleur choisie, record local ; HUD en cartouches (score, chrono avec jauge, billes avec jauge, « +100 ») ; pause et résultats en tuiles.
- **Sons** ElevenLabs (`scripts/sons_elevenlabs.py`, `SonsPaintball`) : musique d'ambiance calme en boucle (`scripts/musique_elevenlabs.py`, guitare et piano, à la place des cigales) ; tir, impact spatialisé, cible, recharge, clic à vide, validation de menu.
- **FPS** : occlusion culling précalculé ; petits objets fixes (< 1,6 m) masqués sous 1 % de la hauteur d'écran ; HDR désactivé (aucun post-traitement) ; matériau partagé par couleur de bille (SRP Batcher) ; résolution adaptative 70-100 % (`ResolutionAdaptative`). `?optim=0` désactive occlusion, culling par taille et résolution adaptative pour comparer ; `window.paintballRead()` expose `frameMs`, `frameP95Ms` et `renderScale`.

## Contre les bots (16 novembre 2026, nuit)

- **Accueil** : « Contre les bots », puis nombre de robots (pastilles 1 à 5) et niveau (Facile, Normal, Difficile).
- **Règles** (`MatchPaintball.cs`, sans moteur ni réseau, mêmes règles et noms d'événements que `serveur/PROTOCOLE.md`) : 3 vies chacun ; une touche par un adversaire retire 1 vie, donne 1 point au tireur et fait réapparaître la cible sur un point sûr au hasard, à plus de 8 m des adversaires (protection 1,5 s) ; victoire au premier à `floor(3 × joueurs / 2)` points (4 à trois joueurs) ; à 0 vie, éliminé ; s'il ne reste qu'un joueur, il gagne ; au bout de 10 min, meilleur score. Tout est réglable dans `ReglesMatch` (`vies`, `ratioCible`, `pointsParTouche`, `victoireAuxPoints`, `dernierSurvivantGagne`, `immunite`, `dureeMax`). Le joueur éliminé voit l'écran de fin (classement provisoire). Hypothèse à confirmer : 1 point par touche et premier à la cible gagne (règle tronquée dans la demande).
- **Hôte local** `PartieBots` : crée les bots, teste chaque segment de bille contre les corps des joueurs (capsules de 0,38 m de rayon, de 0,35 à 1,5 m), transmet les touches au match et applique réapparitions, éliminations et fin. Un serveur faisant autorité le remplacera sans toucher aux règles.
- **Apparitions au hasard sur tout le domaine** : 240 points tirés une fois sur le NavMesh relié au parc (parc, terrasse, rez-de-chaussée et étage du château ; 40 % réservés à l'intérieur), avec 1,9 m de hauteur libre et à plus de 50 cm d'un bord. Chaque vie : un point au hasard à plus de 8 m des adversaires et à plus de 12 m de l'endroit de la mort, hors de leur vue si possible ; orientation au hasard. Les portes s'ouvrent au début d'une partie contre les bots. Pour le serveur en ligne : `PartieBots.PointsApparition(n)` ou `SendMessage('Explorateur','LireEtat','apparitions:64')` puis `window.paintballState.spawns` (`[x,y,z,lacet]` à plat, bien répartis), à envoyer dans `demarrer`.
- **Bots** `BotPaintball` : robot RobotExpressive teinté de la couleur du bot, marqueur Spyder posé par `AnimationMarqueur`. NavMesh de tout le domaine, escaliers et étage compris, cuit à la compilation (`NavigationPaintball`, d'après les colliders ; agent de 0,3 m de rayon pour les portes intérieures). États chasse (vers l'adversaire le plus proche, approche de biais), combat (pas de côté, rafales), couvert (point du NavMesh hors de vue de la menace, pour recharger 20 billes en 1,5 s). Vraies billes via `PaintballSolo.AjouterBille`, visée au torse avec anticipation du déplacement et compensation de la chute simulée. Par niveau, réaction 1,2 / 0,8 / 0,45 s, dispersion 5 / 3,2 / 1,8°, rafales de 2 / 3 / 4, portée de vue 30 / 40 / 55 m. Les bots s'affrontent aussi entre eux.
- **HUD** : score « touches / cible », vies, tableau des joueurs (pastille, vies, points), chrono écoulé avec jauge du meneur, voile à la couleur du tireur quand on est touché ; écran de fin avec issue, tuiles et classement.
- **Vérification navigateur** : `unityInstance.SendMessage('PresentationChateau','CommencerBots','2:Facile')` lance une partie ; `SendMessage('Explorateur','ViserBot','')` vise le bot le plus proche et tire (QA seulement) ; `window.paintballState` expose `mode`, `players` (vies, points, éliminé), `bots` (état, position), `target`, `winner`, `matchOver`. Captures (build Release, Chrome) : `rendus/paintball-bots-accueil.png`, `-hud.png` (vue à l'épaule, robot teinté), `-touche.png` (voile et « Touché »), `-victoire.png`, `-defaite.png` (victoire d'un bot, Development build).

## Mesures de fluidité

`MesuresPerf.cs` expose dans `window.paintballState` (`perfNames`, `perfValues`, moyennes sur 120 images) le temps du thread principal, de la physique, des requêtes physiques, des scripts, de l'animation et les draw calls, triangles et objets projetant une ombre ; les billes (240 Hz) et les bots sont chronométrés à part. Les marqueurs de temps exigent un Development build : `unity build unity --target WebGL --execute-method PaintballScene.BuildWebMesure`. `paintballRead` avec `LireEtat('compteurs:Physics')` liste les marqueurs disponibles. Résultats et méthode : `travail/mesures-fluidite.md`. Plus gros poste : la passe d'ombre ; les objets intérieurs de moins de 3 m et les objets de moins de 60 cm ne projettent plus d'ombre (vestibule 36,2 → 19,0 ms en Development build ; en Release 17 à 20 ms contre 21,7 ms ; parc et partie à 60 images/s). Vérification visuelle : `rendus/paintball-ombres-vestibule.png`, `rendus/paintball-ombres-salon.png`.

## Téléphone et tablette (17 novembre 2026)

Détection automatique (`Application.isMobilePlatform`) ; `?tactile=1` force le mode tactile au bureau. Schéma habituel des tireurs sur téléphone, sans reprendre d'éléments d'un jeu existant (`CommandesTactiles.cs`) : joystick flottant à gauche (pousser vers l'avant jusqu'au bord : course), glisser sur la moitié droite pour regarder, gros bouton **Tir** à droite (on peut glisser dessus pour viser en tirant) et second **Tir** à gauche, **Viser** (bascule), **Saut**, **Recharge**, **Vue**, **Porte**, **Pause**. Interface 1,5 fois plus grande, cartouche des billes au centre en bas, plein écran au lancement de la partie, résolution du navigateur ramenée à 1 pixel CSS, page figée (pas de défilement ni de zoom) et invitation à passer en paysage. En exploration : joystick, regard, Saut, Ouvrir et Les espaces. Vérifié dans Chrome en 844 × 390 avec `?tactile=1` (joystick : déplacement de 4,6 m ; tir tenu 1 s : 8 billes) ; capture `rendus/paintball-mobile-hud.png`. Pas encore essayé sur un vrai téléphone.

## Options, portes-fenêtres et passages sous l'escalier (17 novembre 2026)

**Options** (bouton à l'accueil, dans la pause et dans « Les espaces » ; `InterfaceOptions.cs`, `Reglages.cs`) :
un curseur par réglage, appliqué tout de suite et gardé dans le navigateur (PlayerPrefs).
Jeu : sensibilité (0,25 à 3), axe vertical inversé, champ de vision (60 à 100°, visée à 70 %), animations de l'interface.
Graphisme : ombres (aucune, proches, étendues : distance doublée), résolution (auto = adaptative, 50, 75 ou 100 %),
anticrénelage (aucun, FXAA, SMAA), images par seconde (écran, 60, 30). Sons : volume général, effets, musique.
Clavier et manette : haut et bas changent de ligne, gauche et droite règlent. « Rétablir » remet les valeurs d'origine.

**Portes-fenêtres** : les 11 portes-fenêtres du rez-de-chaussée (façade sud, pans coupés, faces est et ouest)
s'ouvrent comme les portes (E ou bouton Porte) : `Editor/PortesFenetres.cs` coupe menuiserie et vitrage en dormant
et deux vantaux à la construction de la scène. Les bots les trouvent ouvertes en début de partie.

**Sous le grand escalier** : les passages sous les volées de retour mènent maintenant, par le petit salon sous le
repos, jusqu'aux portes du salon (P24, P42). Le mobilier du petit salon (table ronde, fauteuils, chaise gondole)
bouchait les deux sorties ; il est regroupé au centre (`piece_circulations.py`). Vérifié par sonde de collision
à la taille du joueur.

## En ligne (17 novembre 2026)

Mode **En ligne** à l'accueil : le bouton Jouer ouvre le salon de la page (`WebGLTemplates/Paintball/reseau.js`),
au-dessus du jeu : connexion Google (`/auth/google`), parties accessibles, et pour l'admin création de partie, lien
d'invitation 24 h avec QR code, adresses autorisées (ajout, retrait). Lobby : joueurs, couleur, Prêt, Démarrer
(organisateur, avec 64 points d'apparition de `PartieBots.PointsApparition`). Arrivée par `/?partie=<id>` (lien
d'invitation) : connexion puis entrée directe. La WebSocket est dans la page ; le jeu reçoit les messages
normalisés par `SendMessage('Reseau','Recevoir',…)` (`ClientReseau.cs`) et envoie positions (20 Hz), tirs et touches
(`Reseau.jslib`). Les adversaires sont des robots sans IA (`BotPaintball.CreerDistant`), affichés 100 ms dans le
passé du serveur (interpolation, extrapolation 100 ms au plus). Le serveur décide : touches, vies, réapparitions,
fin ; `MatchPaintball` les recopie (`ImposerTouche`, `ImposerFin`) pour le HUD et l'écran de fin des bots.
Le monde ne se fige pas en ligne quand un menu est ouvert. Solo et bots restent sans connexion.

Vérifié en local (`wrangler dev`, deux navigateurs, `/auth/dev`) : création, invitation, lobby, départ, positions
synchronisées, deux touches validées par le serveur (vies et points des deux côtés, réapparition dans le château),
fin par dernier survivant après déconnexion (écran de victoire). Latence locale 1 ms ; non mesurée en production.
Captures `rendus/paintball-en-ligne-hud.png`, `rendus/paintball-en-ligne-victoire.png`.
Aide de test : `SendMessage('Explorateur','ApprocherBot','<id>:<distance>')` (marche à 15 m/s le long du NavMesh ;
échoue depuis l'étage du château).

## Salons, taches sur les corps, podium (17 novembre 2026, soir)

**Client aligné sur le protocole des salons** (`serveur/PROTOCOLE.md`) : `reseau.js` liste `/api/salons`, l'admin
crée un salon (lien `/s/<clé>` et QR code, nouveau lien, suppression), gère les adresses autorisées. Arrivée par
`/?salon=<id>` (invité sans Google possible) ; dans le salon : pseudo et couleur (`profil`), Lancer la manche
(`lancer`, tout membre présent, 2 joueurs au moins), Entrer dans une manche en cours (`entrer`, message `entree`),
relance après la fin. Les messages sont relayés au jeu avec `pseudo` recopié en `nom`. `index.html` charge
`reseau.js?v=<empreinte>` (fin de `CompilerWeb`) : plus d'ancienne version en cache. Saisie dans les champs du
panneau vérifiée au clavier, panneau ouvert après le chargement complet du jeu.

**Taches sur les corps** (`PartieBots.CalculerTache`) : chaque touche (bots, ou message `touche` en ligne avec
son `pt`) laisse une tache de la couleur du tireur à la surface du robot touché (premier sommet du maillage figé
le long de la ligne de tir), accrochée à l'os le plus proche : elle suit l'animation, reste jusqu'à la fin de
la partie et se voit chez tous les joueurs.

**Podium de fin** (`PodiumPaintball.cs`) : marches 1-2-3 dans la cour sablée devant la façade sud, les autres
joueurs au pied, chacun teint de sa couleur avec toutes ses taches, nom et points au-dessus, le vainqueur saute,
les personnages tournent sur eux-mêmes, la caméra se balance doucement ; résultats et boutons dans une colonne
à gauche. Vérifié contre un bot et en ligne à deux comptes (organisateur et invité par lien).
Captures `rendus/paintball-podium-bots.png`, `rendus/paintball-podium-en-ligne.png`.

## Musique provençale, chute des touchés, nuit réelle (17 novembre 2026, soir)

**Musique** : nouvelle boucle de 30 s, ambiance de village provençal des années 1930 (accordéon musette, mandoline,
guitare, clarinette, tempo lent), générée par `scripts/musique_elevenlabs.py` (API Sound Effects : l'API Music
d'ElevenLabs demande un abonnement payant), copiée en OGG dans `Resources/Sons/musique_ambiance.ogg`.

**Personnages touchés** (`CorpsTombe.cs`) : à chaque touche d'un adversaire (bots ou en ligne), une copie du robot
figée dans sa pose, avec ses taches et la tache de la touche agrandie, encaisse 0,3 s, bascule en arrière à l'opposé
du tireur avec un petit rebond, reste au sol 3,2 s puis s'enfonce et disparaît ; le joueur réapparaît ailleurs comme
avant. Le clip « Death » du robot n'est pas utilisé : rejoué sur la copie dans le build web, il ne donnait que la
pose de référence. Vérification : `SendMessage('Explorateur','EssaiChute','')` (bot placé à 4 m devant le joueur
puis touché) ; capture `rendus/paintball-chute.png`.

**Moment de la journée** (`MomentJournee.cs`) : par défaut, position réelle du soleil à Marseille calculée depuis
l'heure UTC (heure d'été française gérée) ; option « Moment de la journée » (Heure de France, Jour, Nuit) dans
Sons et ambiance. Soleil orienté et teinté au lever et au coucher, ciel et lumière ambiante assortis ; la nuit
(soleil sous 1,5°) : lune (halo) et lumière lunaire, étoiles, ombres du soleil coupées. Test : `?heure=23:00`.
`window.paintballState` : `night`, `sunElevation`, `franceTime`.

**Décor de nuit** (`DecorNuit.cs`, shaders `Chateau/Lumineux` et `Chateau/Halo`, matériaux `Resources/Nuit`) :
guirlandes de guinguette d'arbre en arbre (deux plus proches voisins, 5 à 24 m, sans obstacle) et lanternes
japonaises en papier au bord du houppier des 28 arbres les plus proches du château, lumières chaudes sous les
arbres ; lampadaires et lampe de la terrasse ; intérieur : couronne d'ampoules sur chaque lustre, abat-jour allumés
avec leur lumière, bougies des candélabres et appliques, sources existantes renforcées ; tennis : quatre mâts de
9 m (présents de jour) avec projecteurs allumés la nuit. Mesure : 32 guirlandes, 139 lanternes, 558 ampoules,
deux maillages pour tout le décor fixe. Captures `rendus/paintball-nuit-jardin.png`, `-tennis.png`, `-salon.png`.
`?heure=23:00` puis `SendMessage('Explorateur','AllerA','x,y,z,lacet')` pour se placer.

## Boucle rapide (17 novembre 2026)

Avant : chaque essai relançait un éditeur à froid, réimportait le projet, recuisait NavMesh et occlusion, compilait
puis compressait (6 min au mieux ; jusqu'à 40 min quand le jeu tournait en même temps dans le navigateur de test). Maintenant :
`outils/editeur.sh` (une fois) garde un éditeur ouvert sans fenêtre ; `outils/build-rapide.sh` lui demande un build
(`Editor/BuildRapide.cs` : fichier `travail/build-rapide/demande`, rafraîchissement et recompilation des scripts,
build web non compressé, résultat dans `travail/build-rapide/resultat.json`). Mesuré : 96 s au premier build, 40 s
après la modification d'un script. `build-rapide.sh scene` réapplique d'abord les étapes de scène (marqueur,
matériaux, NavMesh, occlusion). La livraison (Gzip ou Brotli) reste `BuildWebMiseAJour` / `BuildWebPublication`,
éditeur chaud fermé.

## Fenêtres, bassin, salon seul, iPhone (17 novembre 2026, nuit)

**Fenêtres éclairées la nuit** (`DecorNuit.Fenetres`, shader `Chateau/Fenetre`) : derrière chacun des 94 vitrages du
bâti (pièces modélisées ou non, combles compris), un panneau de lumière chaude additif tourné vers l'extérieur
(invisible depuis la pièce), intensité et teinte variées. Vitrage opaque des combles : panneau posé devant.
Vantaux ouvrants : le panneau suit le vantail.

**Bassin** : douze projecteurs immergés sur le pourtour, halo froid sur l'eau, lumière sur l'eau et sur le jet.

**Salon** : une manche se lance seul (`joueurs_min = 1`) ; on se promène et on tire, les autres entrent en cours de
manche. La victoire « dernier survivant » ne joue qu'à partir de deux joueurs entrés (`serveur/src/regles.rs`,
test `manche_seul_puis_entree`).

**Téléphones (iPhone, Android)** : les textures web étaient forcées en DXT5, absent des GPU mobiles en WebGL :
Unity les décompressait en mémoire et Safari fermait l'onglet. La publication contient maintenant deux builds
(`Editor/BuildMobile.cs`) : DXT pour les ordinateurs, ASTC 6×6 pour les mobiles ; `index.html` choisit selon les
extensions WebGL (`?mobile=1` force le build mobile, `window.paintballBuild` indique le build chargé). Textures
mobiles en ASTC plafonnées à 512 px, rendu mobile en résolution 1× : données 142 → 84 Mo, tas JS 195 → 134 Mo
(mesuré dans Chrome avec `?mobile=1` ; tas WebAssembly 464 Mo dans les deux cas). Vérifié dans Chrome avec `?mobile=1` ; pas encore sur un vrai iPhone.
`outils/build-rapide.sh double` fait les deux builds en local ; `publication` les fait en Brotli dans `publication/`.

## Données ouvertes, scooter, toit, accroupi, vies (17 novembre 2026, nuit)

**Jardin recalé sur les données ouvertes** (`outils/donnees_ouvertes.py`, IGN Géoplateforme, Etalab 2.0) : orthophoto HR
13 cm et LiDAR HD (MNT/MNS 50 cm) autour du 142 rue du Commandant Rolland, recalés sur le toit du château (rotation
4,2°) → `travail/plan_mesure.json` : 129 arbres mesurés (position, hauteur, couronne ; essence déduite de la forme),
contour du bassin en haricot (centre ~11,6 ; 77,9), cour sud jusqu'à y = 30,5, profil d'axe. `parc.py` les utilise
(les arbres photo identifiés, palmiers, if, haies, sont gardés) ; allée est relevée sur l'orthophoto. Terrasse :
bord à 12,0 (8,5 m auparavant depuis la façade, 3,25 m mesurés), palier central jusqu'à 14,7, **perron de 10 marches
de 15,5 cm**, cour sud à −1,55 (terrasse 26,85 m NGF, cour 25,30). Planche de contrôle `rendus/plan-mesure-lidar.png`.
Non repris : la terrasse est s'arrête à x = 19 sur le LiDAR (23,5 dans le modèle, escalier est inchangé) ; OSM
(Overpass saturé au moment du relevé).

**Voitures** : deux seulement (cour nord, flanc est), modelées par sections (caisse lisse, vitrages, jantes).

**Scooter** (`Scooter.cs`) : vert d'eau, au début de l'allée est (nord). E (ou Porte en tactile) pour monter et
descendre ; Z/S accélère, freine, recule ; Q/D braque ; la souris vise et l'on tire en roulant. Suit le relief,
s'arrête contre murs et troncs, s'incline en virage. Vitesse 11 m/s au plus (sous la limite du serveur en ligne).
Capture `rendus/paintball-scooter.png`.

**Toit** (`EscalierToit.cs`) : escalier raide de 20 marches dans le dégagement nord-ouest de l'étage, vers une trappe ;
E en haut des marches fait grimper (1,3 s) jusqu'à la partie plate du toit (≈ 15,8 m), une trappe y ramène. Le
plafond n'est pas percé : le passage est scripté, à vitesse acceptée par le serveur. Capture
`rendus/paintball-escalier-toit.png`.

**S'accroupir** : C bascule, Ctrl maintenu, bouton « Accroupi » en tactile ; marche à 45 %, yeux 50 cm plus bas,
corps touchable plus bas, les bots visent plus bas ; impossible de se relever sous un plafond. Non transmis en
ligne (le protocole n'a pas de champ). Non vérifié au clavier dans le navigateur de test.

**Vies** : 1, 2, 3, 5 ou 10 à l'accueil contre les bots (la cible suit : 5 vies à 3 joueurs → 7 points) ; en ligne,
bouton dans le salon, envoyé dans `lancer` (`vies`, 1 à 10, refus sinon).

**iOS** : la page note le dernier shader compilé et, à une perte de contexte WebGL, écrit en console ses
déclarations `flat` (`window.paintballPerteContexte`). Aucun des ~50 shaders compilés par le jeu (Chrome, jour et
nuit) n'a de sortie `flat` : le bug WebKit 286297 (corrigé dans iOS 18.5) est écarté ; cause probable sur iPhone :
mémoire graphique (contexte perdu avant l'erreur de shader dans la console du simulateur).

Vérification : `SendMessage('Explorateur','EssaiEntree','x:y:secondes')` impose une entrée de déplacement ;
`window.paintballState` : `riding`, `scooterSpeed`, `scooterObstacle`.

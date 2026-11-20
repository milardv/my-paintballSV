# Reprise du relevé du 19 novembre

## Demande
Corriger les superficies avec les plans d'évacuation, ajouter les pièces vues dans les vidéos (dont le deuxième étage), reproduire fidèlement les œuvres. Préférer Blender/éditeur Unity aux builds longs. Ne rien publier.

## État (19/11, fin d'après-midi) : relevé intégré au jeu, scène reconstruite, pas de build
- Les GLB du relevé sont copiés dans `export/composants/`, avec le nouveau `piece_combles`, et `travail/coque.json` est remplacé. Les originaux sont dans `travail/releve-2026-11-19/sauvegardes/avant-integration.tar.gz`.
- `parc.py` applique le recalage à l'emprise, aux perrons, à la terrasse, à l'escalier est et aux sommets de la cour nord contre les façades, puis le parc a été régénéré. Il n'y a plus de trou au sol entre l'ancienne emprise et la nouvelle (`travail/releve-2026-11-19/abords-grille.txt`).
- La scène `Chateau.unity` a été reconstruite dans l'éditeur, avec le NavMesh et l'occlusion du paintball. 240 apparitions, dont 96 dans le château.
- Coordonnées recalées :
  - départ (y = -15,75), plaques d'histoire (`ChateauScene.cs`) ;
  - destinations de visite et noms de zones (`InterfaceVisite.cs`) ;
  - vues `Capture.cs` et `outils/apercu.sh` ;
  - parcours `VerificationParcours.cs`.
- `PortesFenetres.cs` redresse les menuiseries dont le recalage a mis l'orientation dans les sommets. Il recentre aussi les pans cisaillés et lit leur largeur. 11 portes-fenêtres sont ouvrables.
- Accès au toit (`EscalierToit.cs`) : l'échelle est déplacée dans le passage nord des combles, sous la trappe relevée (sol 10,3, plafond 13,02). Le passage restant mesure 0,63 m, et le contrôle le donne libre.
- Contrôles dans l'éditeur (scène du jeu) :
  - 40 portes sur 41 franchissables ; la 41ᵉ est la baie de la volée centrale, arrêtée par la première marche ;
  - points de visite et de capture sur un sol libre ;
  - planche `travail/releve-2026-11-19/integration-planche.jpg`.
- Pas encore vérifié dans un build : `VerificationParcours` et `outils/verif-jeu.sh` tournent dans le jeu web. Le build à lancer est `outils/build-rapide.sh complet`.

### Retours du 19/11 au soir (photos des portes, du vestibule, du porte-manteau)
- Terrasse : le motif « table » rendait rigides les tablettes de balustrade (`balustrades_socles_tablettes`), d'où un muret décalé de ses balustres. `recaler_releve.py` utilise maintenant `table(?!tte)` ; la terrasse a été recalée à nouveau depuis l'original (`RECALER_SOURCE`).
- Vélo cargo : contre la façade nord, à l'est du perron (`parc.py`, x = 3,75 ; y = -10,75).
- Escalier de service : l'hypothèse de la circulation 50 est abandonnée, puisque l'escalier ne doit pas se voir depuis le palier. Il passe dans la cage latérale est (`combles.json`, `piece_combles.py`) : 2 × 13 marches, demi-palier contre la façade, arrivée dans 75. Le lit, l'armoire et le lustre de 75 passent dans 76. La volée RDC → étage n'est toujours pas modélisée.
- Portes : tous les vantaux de la coque reprennent la photo. Ils sont laqués blanc, avec trois panneaux par face à double filet gris-vert, une plaque de laiton au petit panneau et une béquille. Les chambranles gris-vert à linteau sont générés par la coque (`chambranles_portes_rdc/etage`). Les anciens chambranles des décors restent en place.
- Vestibule (`piece_circulations.py`, puis `recaler_decors.py`) :
  - table à plateau de marbre, ceinture à oves et cartouche, pieds en gaine à mufles de lion, entretoise en X ;
  - lustre doré à deux couronnes (10 + 6 bras en S) ;
  - rosace d'acanthe, en objet séparé pour rester ronde au recalage ;
  - tapis de 3,6 × 3,0 m à médaillons octogonaux et bordure à cartouches ;
  - papier peint crème à motif sauge ;
  - porte-manteau en chêne d'après la photo, placé sur le retour est de l'avant-corps.
- Génération des décors dans le repère d'origine : `CHATEAU_EXPORT=<dossier> CHATEAU_COQUE=travail/releve-2026-11-19/coque-avant-releve.json`, puis `RECALER_SOURCE=<dossier> blender … recaler_decors.py -- piece_circulations`.
- Après toute copie de GLB dans `export/composants`, relancer `python3 outils/extraire-textures-web.py`. Sinon `TexturesWeb` garde les anciennes textures (c'était le cas lors de la première intégration).
- Miroirs (`Scripts/Miroirs.cs`, `Resources/Miroirs/`) :
  - les glaces reçoivent le matériau `Materiaux/Miroir.mat` ;
  - les deux miroirs visibles les plus proches sont rendus en temps réel, par une caméra symétrique avec plan de coupe oblique ;
  - le robot du joueur est affiché pendant ce rendu ;
  - contrôlé dans l'éditeur sur le porte-manteau et le miroir ouest (`travail/releve-2026-11-19/vestibule-planche.jpg`), pas encore en WebGL.

### Build web du 19/11 (15 h 40–16 h 10)
- Le build fait 148 Mo. Il a été lancé en mode batch : `Unity -batchmode -quit -nographics -projectPath unity -buildTarget WebGL -executeMethod PaintballScene.BuildWebExistant`. L'éditeur chaud avait été tué par le noyau faute de mémoire pendant le build.
- Le jeu web a été vérifié par `outils/verif-jeu.sh` (planche `travail/releve-2026-11-19/jeu-web-planche.jpg`) :
  - reflets du porte-manteau et du miroir ouest en WebGL ;
  - vestibule, escalier de service, palier, vélo, terrasse ;
  - préréglages du toit (`carte`, `lunette`), donc trappe des combles et sortie de toit.
- Pas couvert : `VerificationParcours`, qui ne tourne que dans un exécutable natif. En mode vue, l'étiquette de zone reste « Le vestibule » partout ; elle n'est pas vérifiée en déplacement réel.

### Demandes du 19/11 au soir (jeu)
- Parties sans limite de temps : `MatchPaintball.dureeMax = 0`, côté serveur `duree_max_ms: None` (tests 39/39). Le serveur n'est pas encore redéployé.
- Portes-fenêtres :
  - les rideaux recalés pendaient au milieu des baies ; ils sont maintenant glissés un par un hors des vitrages (`caler_rideaux` dans `recaler_decors.py`) ;
  - les rideaux n'ont plus de collision (`ChateauScene`).
- Grand escalier : la volée centrale est une paillasse (`coque.py`) ; l'habillage de ses flancs est retiré (`piece_circulations.py`). Le dessous est vide.
- Piano : remis dos au mur ouest du petit salon (`DEPLACER`, sans dégagement). Il est jouable (`Scripts/Piano.cs`) :
  - E pour s'asseoir, valse synthétisée, son 3D ;
  - message `piano` relayé par le serveur, entendu par les autres joueurs.
- Feuillages (`Scripts/Vegetation.cs`) :
  - 197 plantes s'écartent au contact puis oscillent ;
  - les buissons sont traversables et les arbres ne gardent qu'une capsule de tronc ;
  - les plantes ne sont plus des occulteurs.
- Nuit (`DecorNuit.cs`) :
  - 59 bornes le long des allées et des cours ;
  - lanternes et halos sur 64 arbres ;
  - projecteurs immergés sur le vrai contour du bassin (les anciens, placés sur une ellipse, sont retirés).
- Objets (`Scripts/Gadgets.cs`) : canon à peinture (C), jetpack (Espace en l'air), espadrilles, chaussures à ressorts, cigale, rosé, lunettes, chapeau de paille, feu d'artifice, trois santons.
- Tyrolienne (`Scripts/Tyrolienne.cs`) : du toit au bassin, 99 m pour 20,7 m de dénivelé, tir possible, E pour lâcher, lâcher automatique au-dessus de l'eau.
- Build web vérifié : planche `travail/releve-2026-11-19/nouveautes-planche.jpg` et journal du jeu. Pas testé en jouant : la descente en tyrolienne, le jetpack, la prise des objets et le son du piano (local et en ligne).

### Chaîne de production (sorties dans `export/releve-2026-11-19/`)
| Composant | Méthode | Script |
| --- | --- | --- |
| bati, toiture | recalage d'enveloppe (calibration.json) | `scripts/recaler_releve.py` |
| terrasse | idem, bords extérieurs fixes (x = -19,5 et 22, y = 14 : LiDAR et demande du 18/11), mobilier rigide | `scripts/recaler_releve.py -- terrasse` |
| coque | **régénérée** sur le plan mesuré : cloisons par niveau (R07, R03), 43 ouvertures lues au plan, escalier d'honneur recalculé (19 × 0,179/0,25 ; 11 × 0,177/0,275), voûte réduite au noyau des combles, trémies de l'escalier des combles | `COQUE_SORTIE=$PWD/export/releve-2026-11-19 COQUE_VUES=aucune blender -b --factory-startup --python scripts/composants/coque.py` |
| décors (4 composants) | pièce par pièce, ancien intérieur → nouvel intérieur ; revêtements étirés, mobilier en bloc calé à son mur, glissé hors des nouvelles portes ; portes et fenêtres percées dans les revêtements | `blender -b --factory-startup --python scripts/recaler_decors.py` |
| combles | `piece_combles.py` (R18, R17, R19, R20), export redirigé vers le dossier du relevé | `blender -b --factory-startup --python scripts/composants/piece_combles.py -- --vue-plan` |

Ordre de reconstruction : coque → décors (lisent `export/releve-2026-11-19/coque.json` et `bati-controle.json`) → combles → `scripts/vues_releve.py -- rdc etage combles` (vues de dessus dans `travail/releve-2026-11-19/vues/`).

## Preuves
- Échelle : LiDAR IGN (MNS 50 cm), toit 34,4 m hors tout, soit ≈ 33 m de murs. Les plans donnent 32,8 m, l'ancien modèle 36 m.
- Surfaces de la coque comparées à `plan-mesure.json` : écart ≤ 10 % sur 27 pièces sur 35. Écarts expliqués :
  - Galerie est +27 % et salle 43 -28 % : le volume de l'escalier des combles est rattaché à la galerie (ensemble -6 %).
  - Pièce 33 +52 % : comprend la bande de l'escalier latéral.
  - Vestibule -12 %, salon -17 %, chambre 2 +21 % : la largeur et le nu sud des avant-corps viennent de `bati` recalé (avant-corps de 6,6 m au lieu de 7,2 m mesurés), voir les limites.
  - Pièces 42 et 58 : -20 à -25 %, sur 5 m².
- Unity, scène `Assets/Scenes/ChateauReleve.unity` (menu Château › Relevé du 19 novembre), collisions au maillage, vantaux ouverts : 40 portes sur 40 franchissables (capsule de 0,22 m de rayon). Escalier d'honneur des deux côtés et escalier des combles praticables du RDC aux combles.
- Captures : `travail/releve-2026-11-19/unity/planche.jpg` (vestibule, palier, chambre 3 avec la marine, escalier des combles, combles).

## Limites et hypothèses
- D-041 annulé par D-042 (choix du 19/11) : avant-corps nord à y = -8,7, bibliothèque de 27 m².
- Avant-corps nord et sud : leur largeur suit les refends de cage (±3,3 m), contre ±3,55 m mesurés. Corriger demanderait un recalage de `bati` qui dépende de y.
- L'escalier des combles est placé dans la circulation 50 (hypothèse de combles.json) : il ferme cette circulation à l'étage. On passe par le volume situé au nord (sous la volée haute) ou par la chambre 48.
- L'escalier latéral est (RDC → étage) n'est pas modélisé : sa cage existe, sans marches.
- Décors : les anciennes boiseries des galeries longitudinales, les arcades décoratives, deux balustrades de palier et la lanterne de la galerie est ont été retirées. Elles n'ont pas d'équivalent au relevé.
  - Des chambranles d'anciennes portes restent sur des murs pleins (défaut esthétique).
  - Mobilier déplacé à la main : bibliothèque de la pièce 39 (mur ouest), guéridon du palier, marine de la chambre 3 (même mur, au nord de la nouvelle porte).
- Pièces vues seulement en vidéo (R17, R27) : leur affectation aux numéros de plan reste approximative (combles.json « amenagements »).

## Reste à faire
1. Fait : D-042 (19/11) suit les plans et annule D-041. Reste à traiter la largeur des avant-corps (6,6 m contre 7,2 m).
2. Fait (19/11) : intégration au jeu, parc recalé, scène reconstruite.
3. Faire un build (`outils/build-rapide.sh complet`), puis lancer `VerificationParcours` et `outils/verif-jeu.sh` sur le jeu web. Tester la trappe du toit en jeu.
4. Si on régénère les décors avec `scripts/composants/piece_*.py`, on revient à l'ancien intérieur. Il faut relancer ensuite `scripts/recaler_decors.py` et recopier les GLB.

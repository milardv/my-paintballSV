# Décisions

Journal en ajout seul. Une session qui reprend le travail le lit en entier avant d'agir.
Ajouter une décision : `python3 outils/etat.py decision "<titre>" "<décision>" "<pourquoi>"`.
Une décision remplacée n'est pas effacée : la nouvelle dit « remplace D-xxx ».

## D-001 — Organisation du projet
*2026-11-15*

Projet `~/IdeaProjects/chateau-saint-victor`. Sources en lecture seule dans `sources/` (`pixel/` : 58 photos
du 15/11/2026, ids P00-P57 dans l'ordre de prise de vue ; `web/` : 18 images, ids W01-W18). État partagé dans
`travail/etat.json`, modifié seulement par `outils/etat.py` (verrouillé, sûr en parallèle).

**Pourquoi :** plusieurs agents écrivent en même temps ; un seul point d'écriture évite les conflits.

## D-002 — Un script Blender par composant
*2026-11-15*

Chaque élément (façade, toiture, jardin, pièce…) est un script `scripts/composants/<id>.py` lancé en
`blender -b`, qui produit `export/composants/<id>.glb` et un rendu de contrôle `rendus/<id>.png`.
`scripts/assembler.py` réunit les GLB. Le Blender ouvert (MCP) sert à regarder et ajuster, pas à produire.

**Pourquoi :** plusieurs Blender sans interface tournent en parallèle sans se gêner ; une seule instance MCP
ne le permet pas. Chaque composant se refait seul.

## D-003 — Repère et unités
*2026-11-15*

Mètres, Z vers le haut (Blender). Origine au centre de l'emprise du château, au niveau de la terrasse
côté jardin. +Y vers la façade jardin (sud supposé), +X vers l'est. Niveau RDC = 0.

**Pourquoi :** repère commun obligatoire pour assembler des composants faits en parallèle.

## D-004 — L'ordre de prise de vue sert à déduire le plan
*2026-11-15*

Les photos Pixel ont été prises en un parcours continu (13:47:58 → 13:51:25). Deux photos consécutives
sont dans la même pièce ou dans deux pièces voisines ; c'est la base du graphe des pièces (P3.graphe).
Hypothèse de départ : bibliothèque et palier à l'étage (P00-P13), descente de l'escalier (P14-P21),
RDC (P22-P36), sortie côté entrée (P37-P40), retour RDC (P41-P46), puis pièces à situer (P47-P57).

## D-005 — Validation du plan avant l'intérieur
*2026-11-15*

Aucune pièce intérieure n'est modélisée tant que le plan (P3.validation) n'est pas validé dans l'app de
suivi ou dans ce fichier. L'extérieur peut avancer pendant ce temps.

## D-006 — Images web
*2026-11-15*

W01-W18 viennent en partie d'une vidéo en ligne : référence de modélisation seulement, jamais projetées
comme texture dans un livrable.

## D-007 — Exécution en workflow multi-agents
*2026-11-15*

Les phases parallélisables (P1, puis composants P2, puis pièces P4) sont lancées en Workflow, 4 agents max à la fois.

**Pourquoi :** Choix de Valentin, pour aller plus vite.

## D-008 — Plan déduit des photos
*2026-11-15*

Pas de plan d'évacuation disponible : le plan vient de l'ordre de prise de vue (D-004), des fiches P1 et des fenêtres des façades. Les incertitudes deviennent des questions dans l'app de suivi.

## D-009 — Niveaux modélisés
*2026-11-15*

RDC et 1er étage. Le 2e niveau (attique) et les combles : extérieur seulement, fenêtres opaques.

## D-010 — Gameplay
*2026-11-15*

Exploration libre à la première personne, portes qui s'ouvrent, rien d'autre. Cible : Unity 6, build Linux.

## D-011 — Orientation et ordonnance des façades
*2026-11-15*

Façade jardin = sud, entrée = nord (D-003). Tennis à l'ouest, parking et olivier à l'est (W02, W17 = façade est). W10 et W11 sont vus depuis le nord. Dans W12, le sud est à gauche et le nord à droite. Façade sud : 9 travées au RDC et à l'étage (pavillon 1, aile 2, avant-corps à pans coupés 3, aile 2, pavillon 1), 7 à l'attique. Pavillons d'angle sur 2 niveaux, corps central sur 3. L'avant-corps nord monte d'un niveau au-dessus des ailes et porte un toit pyramidal. 8 souches maçonnées en 4 paires symétriques, 1 conduit métallique, verrière à 4 pans au centre.

**Pourquoi :** Ces sens sont cohérents entre W10, W11, W12, W15 et P39 ; le gabarit commun en a besoin (P2.emprise).

## D-012 — P47-P57 et salle à manger à l'étage
*2026-11-15*

Les photos P44-P57 (salle à manger, chambre-1, chambre-2 à rayures, chambre-3 bureau/armoire) sont au 1er étage. Enfilade le long d'une même façade : chambre-1 (angle) - salle à manger - chambre-2 - chambre-3 ; la salle à manger ouvre sur la galerie du palier, la chambre-3 sur un dégagement d'étage. Les zones int-bureau P50-P51 deviennent int-salle-a-manger. Remplace en partie D-004 (P41-P46 RDC).

**Pourquoi :** P04-P06 montrent depuis le palier d'étage la salle à manger (lustre doré, chaises cannées) ; P50/P51 ouvrent sur la galerie à piliers et sol à cabochons de l'étage ; fenêtres à garde-corps avec vue au-dessus des cimes (P44, P48, P55 : cour gravillonnée en contrebas) ; P46->P47 = 8 s (13:50:51 -> 13:50:59) ; P44 montre la chambre-1 par sa porte gauche.

## D-013 — Escalier impérial et bibliothèque au-dessus du vestibule
*2026-11-15*

Escalier d'honneur impérial : volée centrale vestibule -> repos adossé au mur de la tapisserie, puis deux volées latérales vers une galerie nord formant pont au-dessus du vestibule. La bibliothèque (P00-P03) est à l'étage, au-dessus de la porte d'entrée, dans l'axe ; cage carrée sous coupole à verrière et 4 oculi, galeries latérales à arcades et balustres.

**Pourquoi :** P17-P18 : depuis le repos, la porte en face à l'étage montre le lambris sombre, les caissons et le lustre laiton de la bibliothèque, au-dessus de la porte d'entrée vitrée du vestibule ; P04 : gates aux deux têtes de volées latérales.

## D-014 — Escalier d'honneur impérial
*2026-11-15*

Escalier du vestibule modélisé en escalier impérial : volée centrale droite (marbre, tapis rouge à barres laiton) montant du vestibule (nord) vers un palier intermédiaire adossé au mur sud (tapisserie), puis deux volées de retour est et ouest montant vers le nord jusqu'à la galerie de l'étage ; rampes fer forgé à volutes, main courante laiton. Passages RDC sous les volées de retour, petit salon (fontaine, sabres) sous le palier.

**Pourquoi :** W09 (plongée), P20, P23-P24, P41, P42 concordent ; à confirmer en P3.validation.

## D-015 — Salon au tableau = salon bow-window
*2026-11-15*

La zone int-salon-tableau (P30, P31) est le mur nord du salon bow-window, pas une pièce distincte.

**Pourquoi :** Même parquet, plafond, commode et tableau marine en P29, P30, P31.

## D-016 — Gabarit commun (P2.emprise)
*2026-11-15*

travail/gabarit.json fait foi pour l'extérieur : façade sud 36 m hors tout, profondeur 18,9 m (pavillons), corps principal 21,6 × 17,5 m, pavillons 7,2 × 5,6 m, blocs d'extrémité E/O sur 3 niveaux. Niveaux : cour sud -1,28, cour nord -1,44, RDC 0, étage 5,35, attique 10,3, corniche attique 14,0, faîtage 17,3. Terrasse sud 8,5 m, perron sud 8 marches évasé 15→19 m, perron nord 9 marches 6 m. Tennis à 2,5 m du pignon ouest. Régénéré par scripts/gabarit_emprise.py.

**Pourquoi :** Repère et échelle communs aux composants P2 faits en parallèle ; échelle ±8 % (W12 incliné, recoupé par tennis, voitures, marches et baies)

## D-017 — Plan RDC proposé (P3)
*2026-11-15*

Cage d'escalier impériale x ±4 m, y -3,5 → 3,9 ; vestibule y -9,95 → -3,5 (avant-corps nord) ; passages E/O sous les volées de retour ; petit salon sous le repos (y 0,8 → 3,9) ; salon bow-window au centre sud (y 3,9 → 11,25). Billard x 4 → 10,8, long côté nord-sud (2 portes-fenêtres sud x 5,25/8,85, cheminée sur le mur est entre 2 portes, porte nord vers dégagement/couloir est). Salon vert W07 = pavillon SE. Côté ouest symétrique supposé (salon ouest, pièce NO au bout du couloir ouest), en pointillés. Source : scripts/plan_p3.py → travail/graphe.json, plan-rdc.svg.

**Pourquoi :** Recoupe les fiches P1, l'ordre de prise de vue (P35 → P36 = 8 s : billard → couloir est) et les axes de travées du gabarit ; à valider (P3.validation).

## D-018 — Plan d'étage proposé (P3)
*2026-11-15*

Enfilade sur la façade sud, d'est en ouest : chambre 1 (pavillon SE, fenêtres sud x 14,4 et est y 6,9) / salle à manger (x 4 → 10,8, entrée à l'angle NO depuis le fond de la galerie est, porte-fenêtres x 5,25/8,85) / chambre 2 (au-dessus du salon, cheminée adossée à la cage) / chambre 3 (x -10,8 → -4, porte vers le fond de la galerie ouest). Bibliothèque dans l'avant-corps nord au-dessus du vestibule ; galeries E/O derrière les arcades de la cage (x ±4 → ±5,6). Fiches P43-P46 passées en niveau etage.

**Pourquoi :** D-012, D-013 ; refend de 0,6 m SàM/chambre 2 (P52) = mur x 4 ; vue sur la cour sablée en contrebas depuis la chambre 3 (P55) = façade sud ; P42 → P43 en 28 s = montée de l'escalier.

## D-019 — Plan intérieur validé
*2026-11-15*

Plans travail/plan-rdc.svg et travail/plan-etage.svg validés tels quels. Les 6 points ouverts sont retenus comme proposés : salle à manger à l'étage ; billard nord-sud, cheminée mur est ; salon vert = pavillon SE au fond du billard ; salon ouest symétrique du billard ; fenêtres latérales sur l'avant-corps d'entrée ; dégagement NO et porte en niche du palier vers des pièces non vues (volumes fermés). Les pièces non vues restent fermées ou meublées sobrement.

**Pourquoi :** Validation sans remarque dans l'app de suivi (remplace l'hypothèse de D-004 sur la salle à manger).

## D-020 — Skills jeu vidéo installés
*2026-11-15*

13 skills de gamedev-skills/awesome-gamedev-agent-skills copiés dans .claude/skills/ (Apache-2.0, voir PROVENANCE.md) : unity-csharp-scripting, unity-input-system, unity-physics, unity-animation, unity-build-pipeline, unity-build-size, camera-systems, input-systems, level-design, performance-optimization, shader-programming, audio-design, create-game-assets. Les agents lancés hors du dossier du projet doivent lire .claude/skills/<nom>/SKILL.md eux-mêmes. Écartés : Godot, Unreal, Roblox, web, genres (dont fps-shooter), game-feel, game-ui-ux, tilemap, navmesh. Aucun skill Blender dans ce dépôt.

**Pourquoi :** Demande de Valentin ; seuls ceux utiles à une exploration 3D à la première personne sous Unity 6, build Linux.

## D-021 — Terrasse : limites et raccords
*2026-11-15*

Le composant terrasse (export/composants/terrasse.glb) couvre plateforme et dallage (dessus z=-0,05, y 8,70→17,25 sur ±10,8 en plus du polygone du gabarit), murs, balustrades, perrons sud/nord, escalier est, bacs des massifs, urnes, pots, mobilier ; les maçonneries descendent à z=-1,65 (enterrées). Bacs des massifs recentrés en (±11,4 ; 19,1) au lieu de (±11 ; 18,75) pour ne pas recouper le mur de terrasse ni l'échiffre. Le 4e parasol et sa table sont sur le balcon de l'avant-corps (z=5,35) : la façade sud fournit le sol du balcon. Palier nord à z=-0,02.

**Pourquoi :** Éviter les doublons et recouvrements à l'assemblage (façades, jardin, végétation).

## D-022 — Coque intérieure : niveaux, épaisseurs, hauteurs (P4.coque)
*2026-11-15*

Plancher d'étage 5,05→5,35 (0,30), dalle RDC −0,30→0. Refends 0,60 sur x=±4 et x=±10,8, murs de cage 0,50 (y=3,9 ; y=−3,5 écran à piliers au RDC ; y=−5,3 à l'étage), cloisons 0,20. Murs intérieurs prolongés jusqu'au nu intérieur des murs extérieurs (nu − 0,60, bati.py). Hauteurs sous plafond : RDC 5,0 (vestibule, salons, billard, pièces non vues), 4,5 (couloirs, dégagement est, pièce NO, service ouest) ; étage 4,6 (salle à manger, galeries, non vues), 4,8 bibliothèque, 4,0 chambres, pavillons et dégagement NO ; plafonds suspendus au-dessous de la dalle. Pièces non vues : volumes fermés, portes non ouvrables. À l'étage le bow-window est un balcon (chambre 2 arrêtée au nu de l'avant-corps, y=8,75).

**Pourquoi :** Hauteurs des fiches P1 et du gabarit (planchers ≈0,3-0,4) ; refend de 0,6 vu en P52 ; D-019.

## D-023 — Escalier impérial : géométrie praticable (P4.coque)
*2026-11-15*

Volée centrale 19 contremarches de 0,179 (girons 0,28, largeur 2,5) de y=−3,80 au repos (y=1,24, z=3,40) adossé au mur de la tapisserie ; deux volées de retour de 11 contremarches de 0,177 (girons 0,30, x ±2,0→±3,7) jusqu'à des paliers d'arrivée (y=−1,76) reliés à la galerie nord (pont sur le vestibule, y −5,05→−3,25). Petit salon sous le repos (h 3,15, y 1,24→3,65), passages sous les volées de retour (sous-face rampante 3,15→5,05). Trois arcades plein cintre (1,4 × 3,5) par côté vers les galeries E/O, la plus au sud à balustrade au-dessus de la volée. Cage x ±3,7, y −5,05→3,65 à l'étage, coupole en arc de cloître 10,6→12,0 avec puits vitré 2,2 × 2,6 ; oculi, caissons, colonnes et rampes à volutes laissés aux tâches pièces.

**Pourquoi :** Repos assez haut pour le plafond bas du petit salon (P25 : 3,2), marches 16-18 cm pour un CharacterController ; P14-P26, P41, P42, W09.

## D-024 — Portes animables : convention (P4.coque)
*2026-11-15*

Chaque vantail est un objet porte_<a>_<b>[_g|_d] (suffixe de position si doublon), origine sur l'axe du gond, vantail fermé dans la feuillure côté pièce 'vers'. travail/coque.json donne pour chaque porte : centre, largeur, hauteur, pièces reliées, vers, ouvrable, pivot et angle d'ouverture (rotation Z Blender ; signe inversé sur Y dans Unity). Baies et arcades sans vantail. La porte d'entrée et les portes-fenêtres sont aux façades (bati.py).

**Pourquoi :** Jeu Unity D-010 : portes qui s'ouvrent, script générique lisant coque.json.

## D-025 — Façades (bati) : murs, baies et menuiseries
*2026-11-15*

Murs extérieurs de 0,60 m (nu = polygones du gabarit ; RDC avec pans coupés, étage avec avant-corps sud plan à y=9,35, attique = polygone de toiture.py), pied à z=-1,60, soubassement en saillie de 6 cm jusqu'à z=0. Tableaux (trous, largeur × bas→haut) : portes-fenêtres RDC sud/terrasse 1,45 × 0→3,70 ; fenêtres RDC sur cour basse 1,35 × 0,45→3,70 ; bow : baie centrale 1,50 × 0,90→3,30, pans coupés 1,10 × 0→3,30 ; porte d'entrée 1,70 × 0→4,10 ; étage 1,35 × 5,50→8,60 (1,10 pour les latérales de l'avant-corps sud), porte-fenêtre du balcon 1,40 × 5,35→8,60 ; attique 1,00 × 10,95→12,55, faces des blocs au-dessus des pavillons 0,90 × 11,75→12,95 ; soupiraux nord 0,90 × -1,00→-0,55. Menuiseries à la française deux vantaux, petits bois, imposte fixe au-dessus de 2,6 m, dormant à 0,25 m du nu ; balconnets en fer dans le tableau ; persiennes ouvertes rabattues en façade sur les faces est, ouest et les pavillons nord, aucune au sud ; vitrages d'attique opaques (D-009). Frontons triangulaires au RDC et cintrés à l'étage des pavillons (sud, est, ouest), corniches droites ailleurs.

**Pourquoi :** W01 (proportions, ~18 px/m), W15, W17, W11, P38/P39 ; l'intérieur P4 perce ses murs sur les mêmes axes et cotes. Les fenêtres des blocs sont surélevées pour passer au-dessus des toits de pavillons de toiture.py.

## D-026 — Miroir Y à l'assemblage
*2026-11-15*

Les scripts de composants gardent D-003 (+X est, +Y sud) ; l'assemblage (scripts/assembler.py) et la scène Unity (ChateauScene.cs) appliquent un miroir Y global. Après le miroir, +X = est et +Y = nord dans Blender. Complète D-003, ne le remplace pas pour les composants.

**Pourquoi :** D-003 est un repère indirect : tous les composants sont l'image miroir du château (signalé par P4.coque sur P24/P42, confirmé par W15 : tennis à gauche vu du sud après miroir). Corriger à l'assemblage évite de reprendre les 5 composants.

## D-027 — Reconstruction Unity depuis les composants
*2026-11-15*

ChateauScene.Construire synchronise export/composants/*.glb vers Assets/Chateau/Modeles avant import. BuildLinux reconstruit systématiquement la scène. Les vantaux intérieurs ne sont animables que si coque.json les déclare ouvrables ; les deux vantaux de l’entrée nord sont séparés en maillages persistants, dormant et imposte conservés fixes.

**Pourquoi :** Éviter un build avec une scène ancienne et permettre d’entrer réellement dans le château.

## D-028 — Interface de présentation et visite du domaine
*2026-11-15*

Accueil ivoire et vert profond, typographie Cormorant Garamond/Manrope sous SIL OFL, galerie de neuf photos Pixel originales, liste de huit espaces et HUD discret. Aucun contact ni réservation, selon la demande de Valentin. Les aperçus réels et 3D sont légendés distinctement. Les polices variables téléchargées sont instanciées localement en graisse 400 pour la compatibilité Unity.

**Pourquoi :** Présenter les lieux élégamment tout en conservant une exploration jouable ; ne pas confondre photographie et reconstitution.

## D-029 — Visite uniquement en 3D et skill Game UI UX
*2026-11-15*

Remplace la galerie prévue en D-028 : aucune photographie affichée dans l’application, suppression des copies d’interface. Accueil et choix des espaces présentent la scène 3D en direct. Application du skill game-ui-ux demandé : pile de menus, focus clavier/manette et restitution au retour, zone sûre, ancrages et HUD réagissant aux événements de l’explorateur et des portes.

**Pourquoi :** Correction explicite de Valentin : pas de photos dans l’application ; skill gamedev-skills/awesome-gamedev-agent-skills, skills/disciplines/game-ui-ux/SKILL.md.

## D-030 — UX immersive et audacieuse
*2026-11-15*

Remplace la composition éditoriale scindée de D-029. Scène 3D plein écran, titre monumental, actions circulaires, destinations prévisualisées au survol ou au focus et accessibles en un clic. Retours de pression à 0,97 et relâchement ease-out en 140 ms, réduction des animations disponible ; actions clavier instantanées. Aucun changement aux contraintes sans photo, sans réservation ni contact.

**Pourquoi :** Nouvelle demande de Valentin : UX plus osée/audacieuse et utilisation des skills d’Emil Kowalski, en complément de Game UI/UX.

## D-031 — Accès, animation et médiation du domaine
*2026-11-16*

Ouvrants de la porte-fenêtre centrale du premier étage animables vers le balcon ; fontaine unique, plus haute et animée ; drapeaux animés au vent ; bibliothèques élargies et rehaussées ; tableau marin du salon recadré depuis P30, replacé et redimensionné d'après la photo ; ajout de repères historiques interactifs, sourcés dans le PLUi patrimonial et VMF.

**Pourquoi :** Corrections demandées par Valentin après examen du player ; les photos Pixel servent de référence géométrique et de texture de l'œuvre représentée, pas de galerie dans l'application.

## D-032 — Paintball solo sur navigateur
*2026-11-16*

La demande du 16 novembre remplace D-010 : mode paintball solo WebGL, cameras premiere et troisieme personne, personnage anime source, billes a gravite et trainee, impacts colores et mobilier mobile selon masse et fixation. IA et reseau restent des etapes ulterieures. Reutilisation des textures existantes et images generees seulement pour les besoins nouveaux.

**Pourquoi :** Demande explicite de Valentin.

## D-033 — Paintball professionnalisé
*2026-11-16*

Marqueur réel Spyder MR100 (Sketchfab CC BY) porté en 1re et 3e personne avec pose procédurale (marche, course, visée, recul, recharge), billes affichées 2,1x avec traînée (physique inchangée), réticule vectoriel à écart = dispersion réelle, nouveaux accueil/HUD/pause/résultats teintés par la couleur choisie et record local, sons ElevenLabs (ambiances parc/intérieur en fondu, tir, impacts, cible, recharge), occlusion culling + culling des petits objets + HDR coupé + résolution adaptative 70-100 %.

**Pourquoi :** Demande de Valentin du 16 novembre : rendre le jeu plus professionnel.

## D-034 — Match et bots du paintball
*2026-11-16*

Mode « Contre les bots » (1 à 5, trois niveaux) à côté de l'entraînement. Règles dans MatchPaintball, classe C# sans moteur ni réseau alignée sur serveur/PROTOCOLE.md : 3 vies, 1 point par touche, réapparition sur un point sûr à plus de 8 m des adversaires avec 1,5 s de protection, victoire à floor(3 × joueurs / 2), éliminé à 0 vie, dernier survivant gagnant, 10 min au plus. Hôte local PartieBots (touches par capsules analytiques) ; bots sur NavMesh du parc et de la terrasse, vraies billes balistiques. Les petits objets et l'intérieur hors enveloppe ne projettent plus d'ombre du soleil.

**Pourquoi :** Demande de Valentin (fluidité, bots, puis jeu en ligne). Les mesures ProfilerRecorder montrent que le rendu, et d'abord la passe d'ombre, fait 95 % du thread principal ; physique, billes à 240 Hz et IA coûtent moins de 1 ms. La règle de victoire tronquée dans la demande reste une hypothèse à confirmer, réglable dans ReglesMatch.

## D-035 — Apparitions sur tout le domaine et commandes tactiles
*2026-11-17*

Points d'apparition tirés au hasard sur le NavMesh de tout le domaine (château compris, 40 % des points à l'intérieur), un nouveau à chaque vie (> 8 m des adversaires, > 12 m du lieu de la mort), liste exportable pour le serveur. Nombre de robots choisi par pastilles 1 à 5. Commandes tactiles au schéma courant des tireurs mobiles (joystick gauche, regard à droite, tir des deux côtés, visée, saut, recharge), sans assets ni interface d'un jeu existant.

**Pourquoi :** Demande de Valentin du 17 novembre : choisir le nombre de bots, réapparitions vraiment aléatoires y compris dans le château, jeu jouable sur téléphone avec des contrôles à la PUBG.

## D-036 — Options, portes-fenêtres, passages sous l'escalier
*2026-11-17*

Écran d'options (jeu, graphisme, sons) en curseurs, valeurs dans les PlayerPrefs ; 11 portes-fenêtres du RDC ouvrables (coupe des menuiseries à la construction) ; mobilier du petit salon regroupé au centre pour dégager les passages sous les volées de retour

**Pourquoi :** Demande de Valentin ; P24 et P42 montrent les passages ouverts jusqu'au petit salon et au salon ; les curseurs se règlent à la souris, au doigt, au clavier et à la manette

## D-037 — Nuit réelle, décor de nuit, chute des touchés, musique provençale
*2026-11-17*

Moment de la journée par défaut = position réelle du soleil à Marseille (option Heure de France / Jour / Nuit) ; la nuit, guirlandes et lanternes japonaises dans les arbres proches du château, lustres et lampes d'appoint allumés, projecteurs du tennis ; adversaires touchés : copie figée qui tombe en arrière puis disparaît ; musique d'ambiance provençale années 1930 (ElevenLabs Sound Effects).

**Pourquoi :** Demande de Valentin du 17 novembre. Le clip Death du robot ne s'applique pas à une copie dans le build web : chute procédurale.

## D-038 — Fenêtres éclairées, bassin, salon seul, build mobile ASTC
*2026-11-17*

La nuit, toutes les fenêtres du bâti s'éclairent (panneaux additifs), bassin éclairé par projecteurs immergés ; une manche en ligne se lance seul (dernier survivant à partir de deux joueurs) ; publication en deux builds, DXT ordinateur et ASTC mobile, choisi par index.html.

**Pourquoi :** Demandes de Valentin du 17 novembre ; jeu impossible à ouvrir sur iPhone Safari : DXT5 non géré par les GPU mobiles, décompression en mémoire.

## D-039 — Jardin sur données ouvertes, scooter, toit, accroupi, vies
*2026-11-17*

Terrasse, perron (10 marches), cour sud, bassin et arbres recalés sur le LiDAR HD et l'orthophoto IGN ; deux voitures ; scooter pilotable avec tir ; escalier et trappe vers le toit (passage scripté) ; accroupissement ; vies réglables (bots et salon).

**Pourquoi :** Demandes de Valentin du 17 novembre ; données IGN (Etalab 2.0) plus précises que l'estimation photo pour les niveaux et le plan du jardin.

## D-040 — Plan du domaine d'après la limite de propriété
*2026-11-18*

travail/plan_domaine.json fait foi pour l'extérieur hors maison : limite de propriété (polygone de Valentin recalé sur l'orthophoto IGN), entrée au sud-est sur l'avenue (grille en fer noir, murs courbes), maison du gardien à droite en entrant avec deux soldats qui sortent à chaque arrivée/départ (GardesPortail.cs), pétanque derrière, grange du jardinier (tôle rouge, tracteur tondeuse, outils) près de la camionnette, local piscine, piscine en haricot redessinée, allées relevées sans arbre sur la chaussée et bordées de petites plantes, tennis sur une plateforme au niveau de la terrasse avec escaliers vers les cours nord et sud, terrasse ramenée à x = 20 à l'est, pavés de verre devant les portes-fenêtres, relief du LiDAR HD hors des cours. Remplace en partie D-016 (tennis -1,6) et D-021 (retour est 23,5).

**Pourquoi :** Photos et indications de Valentin du 18/11 ; LiDAR HD : tennis à 0/+0,3, terrasse est jusqu'à x = 19,6 ; orthophoto élargie à 400 m pour couvrir le domaine

## D-041 — Avant-corps nord approfondi de 2,5 m
*2026-11-18*

Nu nord de l'avant-corps à y = −12,45 (au lieu de −9,95) : gabarit (emprise, avant_corps_nord, perron nord décalé jusqu'à −16,62), bati.py et toiture.py (AC_N), coque.py et plan_p3.py (vestibule −12,45 → −3,5 ; bibliothèque −12,45 → −5,3), terrasse.py (perron lu dans le gabarit), parc.py (cour nord). Une fenêtre par niveau sur chaque retour de l'avant-corps (y = −10,6 ; 1,35 m, ordonnance des fenêtres nord), déjà portées au plan D-019. Vestibule : décor du mur d'entrée, paillasson, rideaux recalés sur le nouveau mur ; rosace, lustre, table et tapis au milieu. Bibliothèque : 3 × 5 caissons, coin lecture (bergère, guéridon, lampadaire) devant la fenêtre nord, table de travail et second lustre dans la partie ajoutée. Unity : arrivée à y = −19,5, contrôle de la porte d'entrée à −13,1.

**Pourquoi :** choix de l'utilisateur du 18/11 pour une bibliothèque plus grande ; le relevé W11 (saillie 1,2 m ±0,6) n'est plus suivi sur ce point.

## D-042 — Plans d'évacuation du 17/10/2022 pour le bâti et l'intérieur (annule D-041)
*2026-11-19*

Enveloppe recalée sur calibration.json : 32,8 × 13,8 m (pavillons), avant-corps nord à y = −8,7, bow-window à 8,9 ; coque régénérée sur travail/releve-2026-11-19/plan-mesure.json (cloisons par niveau R07/R03, 43 ouvertures, escalier d'honneur 19 × 0,179/0,25 puis 11 × 0,177/0,275, voûte réduite au noyau des combles) ; combles R18 avec escalier de service (combles.json) ; décors recalés pièce par pièce (scripts/recaler_decors.py) ; terrasse à bords extérieurs fixes. D-041 est annulé : la bibliothèque passe de 44 à 27 m². Largeur des avant-corps encore liée aux refends de cage (6,6 m contre 7,2 m mesurés).

**Pourquoi :** Choix de Valentin du 19/11 : suivre les plans d'évacuation ; échelle confirmée par le LiDAR HD (≈ 33 m de murs contre 36 m modélisés).

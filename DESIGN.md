---
name: Château Saint-Victor
description: Exploration native cinématographique d’une demeure en trois dimensions
colors:
  ivory: "#F4F0E7"
  pine: "#173D34"
  brass: "#AD9464"
  on-pine-hover: "#36594B"
  on-pine-selected: "#456A55"
  on-pine-pressed: "#284C3E"
typography:
  display:
    fontFamily: "Cormorant Garamond"
    fontSize: "146px"
    fontWeight: 400
  headline:
    fontFamily: "Cormorant Garamond"
    fontSize: "68px"
    fontWeight: 400
  title:
    fontFamily: "Cormorant Garamond"
    fontSize: "40px"
    fontWeight: 400
  body:
    fontFamily: "Manrope"
    fontSize: "22px"
    fontWeight: 400
  label:
    fontFamily: "Manrope"
    fontSize: "21px"
    fontWeight: 400
rounded:
  square: "0px"
  circle: "50%"
spacing:
  divider: "1px"
  list-gap: "2px"
components:
  entry-disc:
    backgroundColor: "{colors.pine}"
    textColor: "{colors.ivory}"
    rounded: "{rounded.circle}"
  button-on-scene:
    backgroundColor: "transparent"
    textColor: "{colors.ivory}"
    typography: "{typography.label}"
    rounded: "{rounded.square}"
  button-header:
    backgroundColor: "{colors.pine}"
    textColor: "{colors.ivory}"
    typography: "{typography.label}"
    rounded: "{rounded.square}"
  button-on-scene-hover:
    backgroundColor: "{colors.on-pine-hover}"
  button-on-scene-selected:
    backgroundColor: "{colors.on-pine-selected}"
  button-on-scene-pressed:
    backgroundColor: "{colors.on-pine-pressed}"
  hud-hint:
    backgroundColor: "{colors.pine}"
    textColor: "{colors.ivory}"
    rounded: "{rounded.square}"
---

# Design System: Château Saint-Victor

## Overview

**Creative North Star: "Le château en scène"**

Une visite native audacieuse et luxueuse : le château occupe tout l’écran, accompagné d’un titre monumental et d’actions peu nombreuses. Les voiles pin rendent le texte ivoire lisible sans remplacer le lieu par une surface éditoriale opaque.

Cormorant Garamond régulier apporte l’ampleur patrimoniale ; Manrope rend les commandes directes. L’exploration conserve une légère dimension jeu vidéo, avec destinations prévisualisées, entrée immédiate et HUD contextuel. Les photographies servent exclusivement à la modélisation.

**Key Characteristics:**
- Scène 3D en direct sur tout l’écran.
- Grand titrage régulier et entrée circulaire.
- Navigation verticale superposée au lieu.
- Focus explicite, menus empilés et zone sûre.

## Colors

### Primary
Le pin porte les disques d’action, les rappels de commande et les états des commandes transparentes. Les voiles utilisent des verts presque noirs et translucides ; ils assurent la lecture au-dessus du monde.

### Secondary
Le laiton marque les filets avec une opacité de 45 %. Le focus utilise un laiton plus clair défini directement dans `FocusInterface` (RGBA 0.74, 0.65, 0.44, 1).

### Neutral
L’ivoire porte les titres, descriptions et commandes sur la scène. L’encre et le vert secondaire de l’ancienne composition existent encore comme constantes du code, mais ne constituent pas des couleurs de surface visibles de cette nouvelle direction.

**The Living Scene Rule.** La couleur rend le monde lisible ; elle ne remplace pas la scène par un panneau opaque.

## Typography

Cormorant Garamond régulier assure les titres ; Manrope régulier assure descriptions et commandes. Les fichiers embarqués sous SIL OFL sont convertis en atlas TextMeshPro dynamiques. Il s’agit de polices natives, sans chargement web.

Les tailles frontmatter représentent les unités TextMeshPro du canevas de référence, exprimées en pixels pour la portabilité. Le titre d’accueil utilise display. Les titres de destinations utilisent headline ; le menu des espaces utilise 66 et celui des commandes 78. Le nom du lieu dans le HUD utilise title. Les noms des destinations dans la liste utilisent Manrope 28, le disque d’entrée 31, l’invitation d’accueil 29, les descriptions 22, les niveaux 20 et les aides 18–19. Aucun faux gras ni italique décoratif.

## Layout

Canevas uGUI superposé, référence 1920 × 1080, `ScaleWithScreenSize` avec correspondance largeur/hauteur à 0,5. Le conteneur adapte ses ancrages à `Screen.safeArea`. Les écrans internes utilisent des ancrages proportionnels, sans point de rupture web.

À l’accueil, la caméra montre la façade jardin sur tout l’écran, avec un champ de vision de 45°. Le cadrage est défini par la position projet (0, 62, 12), orientée vers (0, 1, 6), puis convertie vers les axes Unity. Le titre Saint-Victor est placé en bas à gauche, le disque « Entrer » en bas à droite ; les commandes et la sortie occupent le haut droit. Un voile latéral couvre les premiers 66 % de largeur et un voile bas les premiers 51 % de hauteur, tous deux fondus vers la transparence. Un voile supérieur occupe le quart haut des écrans de menu pour soutenir la signature et les commandes. Ces dimensions décrivent cet écran, pas une grille imposée aux surfaces futures.

Le menu des espaces superpose une liste verticale à gauche et la description de destination en bas à droite de la scène. Le `VerticalLayoutGroup` utilise un intervalle de 2 unités, une hauteur minimale de ligne 64 et une hauteur préférée 76 avec expansion flexible. La sélection change la vue 3D immédiatement. Les commandes sont présentées sur deux lignes par entrée.

Pendant la visite, le nom du lieu se place en bas à gauche ; les rappels et l’aide temporaire sont en haut. La commande de porte apparaît au centre bas uniquement lorsqu’une porte est visée.

## Elevation & Depth

La profondeur est celle du château rendu en temps réel. Les voiles de lisibilité sont des dégradés uGUI, pas des ombres portées ni du flou. Le voile latéral part de RGBA (0.025, 0.075, 0.06), avec une opacité de 0,93 à 0,98 selon l’écran ; le voile bas part de (0.025, 0.065, 0.05), avec une opacité de 0,78 à 0,95. Ils terminent transparents. Le voile supérieur va du transparent vers RGBA (0.025, 0.06, 0.05, 0.8). Chaque voile utilise 32 bandes et une interpolation `1 − (1 − t)^0,35`, qui maintient la densité avant la fin du fondu. Les surfaces de fond n’interceptent pas le pointeur.

## Shapes

Les rappels, lignes et états de survol sont rectangulaires à angles droits. Le disque d’entrée est la signature : un maillage circulaire à 80 segments, un ratio largeur/hauteur de 1 et une zone de clic circulaire. Les filets laiton mesurent une unité du canevas. Le focus ajoute un contour uGUI décalé de (1,5 ; −1,5), y compris autour du disque.

## Components

### Entry disc

Disque pin, libellé Manrope régulier 31 centré en ivoire. Les états survol et sélection éclaircissent le pin par multiplication de couleur ; la pression l’assombrit. La transition native de couleur dure 0,12 seconde, avec une sélection clavier appliquée immédiatement. Le diamètre dépend de la hauteur ancrée de chaque écran.

### Scene actions

Boutons transparents en ivoire, libellé centré 21 et marges horizontales de 4,5 % de leur largeur. Les variantes survol, sélection et pression utilisent les trois couleurs on-pine. La transition native de couleur dure 0,16 seconde ; la teinte sélectionnée au clavier est appliquée immédiatement. Le focus active un contour laiton distinct du survol. Les trois commandes de tête « Les commandes », « Quitter » et « Reprendre la visite » emploient un fond pin opaque au repos pour conserver leur contraste sur la scène ; elles partagent les états on-pine des autres commandes.

### Destinations

Chaque ligne contient uniquement le nom de la pièce et un filet inférieur ; le niveau et la description sont portés par la légende de la scène. Le survol sélectionne la ligne ; le focus clavier ou manette déclenche la même prévisualisation. Un clic ou une validation entre directement dans le lieu. Le disque « Entrer » ouvre la destination prévisualisée.

### Context HUD and menus

Le lieu et l’état de porte se mettent à jour par événements. L’aide de déplacement disparaît après 12 secondes. Dans l’écran des commandes, l’aide de navigation clavier/manette repose sur un fond pin opaque couvrant la largeur du bloc de texte. Les menus suspendent le déplacement ; Échap ou Start ouvre les espaces et le retour remonte la pile avec restauration du focus. Reprendre rétablit la position mémorisée. Les quatre boutons d’accueil disposent de voisins directionnels explicites. Le support manette décrit ici concerne les menus, pas le déplacement libre.

### Pointer feedback

La pression pointeur réduit immédiatement le contrôle à 0,97. Le relâchement restaure l’échelle sur 140 ms avec la fonction `1 − (1 − t)³`, interruptible par une nouvelle pression. Le réglage persistant « Animations : réduites » désactive cette réduction. Les actions clavier ne déclenchent pas de mouvement d’échelle. Les changements de vue et de menu ne comportent pas de transition spatiale décorative.

## Do's and Don'ts

### Do:
- Do conserver la scène 3D comme sujet principal.
- Do placer des voiles de lisibilité derrière le texte superposé.
- Do préserver la prévisualisation au survol et au focus, puis l’entrée en une action.
- Do réserver le mouvement de pression au pointeur et proposer les animations réduites.

### Don't:
- Don't afficher de photographie ou galerie dans l’application.
- Don't ajouter de contact, réservation ou argument commercial fictif.
- Don't revenir au panneau éditorial opaque partageant l’écran d’accueil.
- Don't ajouter de mouvement décoratif aux actions clavier répétées.

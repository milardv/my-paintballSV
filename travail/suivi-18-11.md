# Suivi de session — 18/11/2026 (objets, terrasse, neige)

## Fait, vérifié en local (build rapide + ?objets=1 : tout OK)
- Objets du domaine (`ObjetsDomaine.cs`, `Vehicule.cs`, `Tracteur.cs`, `VerificationObjets.cs`) : boule dorée, clés, pastis, gilet, képi.
- Boule : maintenir G = trajectoire en pointillés + cercle d'explosion ; relâcher = lancer. Explosion 4,5 m, 70 gouttes qui tachent, souffle, flash, secousse, son ElevenLabs `Resources/Sons/explosion_peinture.wav` (`scripts/sons_elevenlabs.py explosion_peinture`). 77 taches au test.
- Tracteur garé sous la grange (`Vehicule.Sol` : jamais sur un toit), sort et roule (12,6 m au test).
- Entraînement sans limite de temps (temps écoulé affiché, record mis à jour en continu).
- `outils/build-rapide.sh` s'arrête si l'éditeur Unity meurt (OOM à 10 h 43 et 12 h 43).

## Fait, PAS encore compilé/vérifié (attend le build complet)
- Bouton rond « Reprendre » sur une ligne (`InterfaceVisite.BoutonRond`, NoWrap + taille auto).
- Portes-fenêtres et portes de balcon : s'ouvrent vers l'intérieur, 88° (`Porte.cs`).
- Fumeur sur le retour est de la terrasse (`Fumeur.cs`, appelé dans `PaintballSolo.Start`) : IK bras, cigarette, braise, fumée.
- `scripts/composants/terrasse.py` : coin fumeur (canapé dos à la balustrade x 21,15 y 2,9 ; cendrier tube inox x 21,35 y 4,95), canapé côté façade du coin apéro retiré (passage scooter). GLB à réexporter (Blender) — rendu `rendus/terrasse_fumeur.png` fait avant le retrait du canapé.
- Bosquet rond déplacé hors de l'allée est : `travail/plan_domaine.json` massif_rond_est centre [21.5, 18.5] (sauvegarde `travail/plan_domaine_avant_bosquet.json.bak`). parc.py à réexporter.

## Fait (session 13 h 45)
- C5 Aircross noire et blanche : `scripts/composants/voiture_c5.py`, parc.glb exporté 13 h 31 (inclut le bosquet déplacé).
- Build `scene` OK (447 s). Test `?neige=1` (Chrome headless swiftshader via agent-browser ; le navigateur intégré n'a pas WebGL) : ok, couverture 1, 13 empreintes, seuil 0,03.
- terrasse.glb réexporté 13 h 53 (17 Mo), rendus terrasse_*.png à jour.

## Neige (détail)
  - Fichiers : `Editor/AmbianceScene.cs` (appelé par PaintballScene.Creer/PreparerScene), `Scripts/Atmosphere.cs`, `Scripts/Neige.cs`, `MomentJournee.cs` (lumière plus réaliste + ciel couvert `Neige.Gris`), `Reglages.Neige`, ligne « Neige » dans les options (colonne Sons et ambiance), `SonsPaintball.Hiver/PasNeige`, sons `ambiance_neige.ogg`, `pas_neige.wav`.
  - Plan : `Editor/AmbianceScene.cs` (textures nuages/flocon/neige/empreinte, matériaux dans `Resources/Ambiance`, couche de neige précalculée depuis les triangles vers le haut à ciel ouvert, Volume post-traitement, brouillard, SSAO sur PC_Renderer) appelé depuis `PaintballScene.Creer` et `PreparerScene` ; runtime `Atmosphere.cs` (dôme de nuages, teinte, brouillard) et `Neige.cs` (flocons autour de la caméra, couverture progressive `_Cutoff`, sons `ambiance_neige`/`pas_neige` ElevenLabs, empreintes couleur du joueur et des bots) ; option `Reglages.Neige` + ligne dans `InterfaceOptions`.

## Reste à faire
1. Fait : bibliothèque (D-041), tous les GLB réexportés, build complet OK (340 s) ; `?objets=1` ok (85 impacts, tracteur 11,5 m), `?neige=1` ok. Non vérifié en jeu : vue de l'entrée nord et de la bibliothèque (rendus Blender seulement), VerificationParcours (scène Château, pas le build web).
4. Publication seulement sur feu vert explicite : `outils/build-rapide.sh publication` puis `cd serveur && npm run preparer-jeu && npx wrangler deploy`.

## Session 18/11 après-midi (suite)
- Outils de vérification rapide : `outils/apercu.sh` (éditeur, 10 s) et `outils/verif-jeu.sh` (jeu web, préréglages).
- Toit : carte des objets rares (`CarteDomaine.cs`, vue aérienne précalculée par AmbianceScene, pastilles dispo/pris par qui, bots qui ramassent) ; lunette de visée (`LunettePaintball.cs` : ×3/×4,5/×6 molette, trajectoire réelle, chute, aide à la visée, dispersion resserrée).
- Vélo cargo longtail (`scripts/composants/velo_cargo.py`, parc.glb) au pied ouest du perron nord, pilotable avec tir (`VeloCargo.cs`).
- Neige : grille d'enneigement (NeigeGrille.bytes) → empreintes seulement sur la neige visible, taches de peinture posées sur la neige.
- Vérifié : carte, lunette, vélo (13 m, 12 tirs en roulant), neige (28 empreintes, 4 taches levées). Rien publié.

# Château Saint-Victor — mini-jeu d'exploration

Reconstruction 3D (extérieur, parc, intérieur) du Château Saint-Victor (Marseille) à partir de photos,
puis jeu d'exploration Unity.

Pour reprendre, lire dans l'ordre :
1. `DECISIONS.md` (tout) ;
2. `python3 outils/etat.py` (tâches, validations en attente) ;
3. `WORKFLOW.md` (phases, parallélisme, règle d'un agent).

Fichiers :
- `sources/pixel/` (P00-P57, ordre de prise de vue) et `sources/web/` (W01-W18) : lecture seule.
- `travail/photos.json` : id, fichier, zone, note ; `travail/vignettes/<id>.jpg` : 360 px.
- `travail/etat.json` : état partagé, écrit seulement par `outils/etat.py`.
- `travail/fiches/`, `travail/inventaire.json`, `travail/gabarit.json`, `travail/plan.svg` : produits de P1-P3.
- `scripts/composants/<id>.py` → `export/composants/<id>.glb` + `rendus/<id>.png` (`blender -b --python`).
- `suivi/` : app de suivi locale (`python3 suivi/serveur.py`, port 8765).

Outils : Blender `/home/valm/.local/bin/blender` (+ MCP blender), Unity 6000.6.5f1 (+ MCP unity).
Python avec PIL/numpy : `/home/valm/.local/opt/blender-5.2.3/5.2/python/bin/python3.13`.
Skills jeu vidéo : `.claude/skills/` (lesquels pour quelle phase : WORKFLOW.md).

Boucle rapide du jeu web (itérer, pas livrer) :
- `outils/editeur.sh` une fois : éditeur Unity ouvert sans fenêtre, gardé chaud (fermer : `unity close unity`).
- `outils/build-rapide.sh` après chaque changement : ~40 s pour un script modifié (~95 s au premier build) ;
  `outils/build-rapide.sh scene` si `PaintballScene`/`ChateauScene` ou le décor ont changé (NavMesh, occlusion).
  Sortie `build/web` non compressée, servie par `./lancer-web.sh` ; recharger la page.
- Fermer les onglets du jeu pendant un build : un onglet ouvert dans le navigateur de test sans GPU a coïncidé
  avec un build de 40 min (probable concurrence pour les cœurs).
- L'éditeur chaud verrouille le projet : `unity build` (livraison, `BuildWebMiseAJour`) exige de le fermer avant.
- Le MCP Unity (`Unity_RunCommand`) parle à cet éditeur : vérifications sans build possibles.
- Vérifier le rendu sans build : `outils/apercu.sh "nom x y z cap [tangage] [focale]" …` (≈ 10 s, décor de la scène
  dans l'éditeur chaud, repère D-003, cap 0 = sud, tangage négatif = vers le bas) → `travail/apercu/*.png`.
- Vérifier le vrai jeu (objets créés au lancement) : `outils/verif-jeu.sh` (≈ 2-4 min, Chrome sans écran, `?vue=1`) :
  préréglages carte, lunette, velo, neige (rapports JSON) ou vues "nom|x,y,z,cap" → `travail/verif-jeu/*.png`.
  Le navigateur intégré de l'app n'a pas WebGL ; sous WebGL logiciel le temps de jeu tourne à ~0,3×.
- `outils/build-rapide.sh complet` après un changement de GLB (réimport, scène reconstruite, ~30-60 min).
- Mémoire (31 Go) : ne pas lancer de Blender pendant un build de l'éditeur chaud (Unity tué par le noyau le
  17/11 avec deux Blender et le navigateur de test ouverts).
- Données ouvertes : `outils/donnees_ouvertes.py telecharger|mesurer` → `travail/plan_mesure.json` (LiDAR HD,
  orthophoto IGN), lu par `scripts/composants/parc.py` (arbres, bassin) ; terrasse et perron dans le gabarit.

# Château Saint-Victor

Exploration à la première personne, Linux x86_64.

## Lancer

```bash
/home/valm/IdeaProjects/chateau-saint-victor/lancer.sh
```

ZQSD (positions physiques WASD), souris pour regarder, Maj pour courir, E ou clic pour ouvrir une porte ou consulter un repère historique,
Espace pour sauter, Échap pour ouvrir le menu, Alt+F4 pour quitter.

Le programme est `build/linux/ChateauSaintVictor.x86_64` ; il nécessite les fichiers voisins
`ChateauSaintVictor_Data/`, `UnityPlayer.so` et `libdecor-0.so.0`.

## Interface

Accueil 3D plein écran, accès direct aux huit espaces. Le survol ou le focus clavier prévisualise un lieu ; un clic entre dans cet espace. Les menus se parcourent aussi avec les flèches et Entrée. Le menu des commandes permet de réduire les animations. Aucune galerie photographique, aucun contact ni réservation.

## Sources et contrôles

- Scène Blender complète : `export/chateau.blend`.
- Scène Unity : `unity/Assets/Scenes/Chateau.unity`.
- Captures de l’interface : `rendus/interface-immersive-1920/`.
- Référence du modèle et limites de fidélité : `travail/audits/fidelite.md`.
- Contrôle du parcours : `travail/verification-parcours.json`.
- État du chantier : `python3 outils/etat.py`.

Reconstruction et build (Unity 6000.6.5f1 installé) :

```bash
unity build unity --target StandaloneLinux64 --execute-method ChateauScene.BuildLinux
```

Les GLB de `export/composants/` sont synchronisés automatiquement avant chaque reconstruction.

Contrôle des collisions sans affichage :

```bash
./lancer.sh -batchmode -nographics -verification "$PWD/travail/verification-parcours.json"
```

Captures depuis douze points fixes, dans une session graphique :

```bash
./lancer.sh -screen-fullscreen 0 -screen-width 1280 -screen-height 800 -capture "$PWD/rendus/unity-reprise"
```

Le modèle est une reconstruction estimée depuis les photos ; les volumes non photographiés suivent
les hypothèses validées dans `DECISIONS.md`.

## Paintball solo sur le web

Le mode paintball se lance avec `./lancer-web.sh` sur http://localhost:8086.
Contrôles, physique, provenance des assets et compilation : [README-PAINTBALL.md](README-PAINTBALL.md).

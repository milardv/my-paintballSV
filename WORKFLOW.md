# Workflow — reconstruction du Château Saint-Victor

Suivi en direct : `python3 suivi/serveur.py` puis http://localhost:8765.
Toute étape passe par `outils/etat.py` (statut, journal, rendus, attentes) ; toute décision par
`outils/etat.py decision` (→ `DECISIONS.md`).

## Phases et parallélisme

```
P0 Préparation ──► P1 Analyse (4 agents en parallèle : ext / int-rdc / int-étage / inventaire)
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
   P2 Extérieur                 P3 Plan intérieur
   emprise (W12) d'abord,       graphe des pièces → plan SVG
   puis en parallèle :                 │
   façades ×3, toiture,          ⏸ VALIDATION Valentin (app de suivi)
   terrasse, jardin,                   │
   végétation, annexes                 ▼
          │                     P4 Intérieur : coque, puis une pièce par agent
          ▼                            │
   assemblage ext.  ───────────────────┴──► P5 Unity (import, lumière, contrôleur, build Linux)
```

### P1 — Analyse (une fiche par photo)
Chaque agent reçoit une zone et produit, pour chaque photo, `travail/fiches/<id>.json` :
pièce, orientation de la vue, murs visibles et ouvertures (portes, fenêtres, vers quoi elles donnent),
dimensions estimées (hauteur sous plafond, largeur de baie, nombre de travées), et **inventaire exhaustif**
des éléments : mobilier, luminaires, tableaux, tapis, moulures, cheminées, sols, rideaux, plantes, objets.
L'inventaire consolidé (`travail/inventaire.json`) devient la liste des choses à modéliser, pièce par pièce.

### P2 — Extérieur
1. `P2.emprise` seul d'abord : emprise et hauteurs depuis W12 (zénithale), W10/W11/W15 (aériennes),
   nombre de travées des façades. Fixe le repère (D-003) et le gabarit commun `travail/gabarit.json`.
2. Puis un agent par composant, chacun dans `scripts/composants/<id>.py` (D-002), en parallèle.
3. `P2.assemblage` : rendus depuis les points de vue des photos, planche photo/rendu, corrections.

### P3 — Plan intérieur (point d'arrêt)
Graphe des pièces depuis les fiches et l'ordre de prise de vue (D-004), recoupé avec les fenêtres des
façades. Plan RDC + étage en `travail/plan.svg`, affiché dans l'app. Les points incertains deviennent des
questions `etat.py attente`. **Rien de l'intérieur n'est modélisé avant validation** (D-005).

### P4 — Intérieur
La coque (murs, planchers, ouvertures, escalier) d'abord, puis un agent par pièce en parallèle :
décors fixes (lambris, moulures, plafonds, cheminées, sols) puis mobilier et petits objets de l'inventaire.
Bibliothèques d'assets (Poly Haven, Sketchfab CC) pour le générique, modélisation pour le spécifique.

### P5 — Unity
Import dans un projet Unity 6, collisions, éclairage, contrôleur d'exploration, puis build Linux.

## Skills par phase (`.claude/skills/<nom>/SKILL.md`)
- P2/P4 (assets, textures, licences) : `create-game-assets`, `shader-programming`.
- P5 import et scène : `unity-csharp-scripting`, `unity-physics` (collisions), `performance-optimization`.
- P5 contrôleur et portes : `unity-input-system`, `input-systems` (ZQSD/AZERTY), `camera-systems` (vue 1re personne), `unity-animation`, `level-design`.
- P5 ambiance : `audio-design` ; build : `unity-build-pipeline`, `unity-build-size`.

## Règle d'un agent
1. Lire `CLAUDE.md`, `DECISIONS.md`, `python3 outils/etat.py`.
2. `etat.py tache <id> en-cours --agent <nom>`.
3. Travailler seulement dans ses fichiers (`scripts/composants/<id>.py`, `travail/fiches/…`).
4. Publier un rendu (`etat.py rendu`), passer la tâche à `fait` ou `a-valider`, noter les décisions.

# Mesures de fluidité — paintball WebGL

Chrome (agent-browser --headed, /usr/bin/google-chrome), 1280 × 720, Iris Xe. Development build
(`PaintballScene.BuildWebMesure`) : `window.paintballRead()` puis `window.paintballState.perfNames/perfValues`,
moyennes des 120 dernières images (`MesuresPerf.cs`, ProfilerRecorder + chronomètres des billes et des bots).
Un Development build est plus lent qu'un build Release : comparer les colonnes entre elles, pas avec les mesures Release.

Scènes : vestibule `SendMessage('PresentationChateau','EntrerEspace','0')`, parc `'7'`,
partie `SendMessage('PresentationChateau','CommencerBots','2:Facile')` (lecture 7 s après le départ, joueur immobile).

Mesures Release antérieures : vestibule 36 ms sans optimisations (`?optim=0`), 21,7 ms avec ; parc 17,3 ms sans.

## Avant (16 novembre, Development build)

| Scène | Image (ms) | p95 | Thread principal | Physique (Simulate) | Billes (240 Hz) | Bots | Scripts Update+Late | Draw calls | Ombres portées (objets) | Triangles |
|---|---|---|---|---|---|---|---|---|---|---|
| Vestibule | 36,2 | 53 | 36,2 | 0,28 | 0 | 0 | 0,8 | 2 616 | 1 923 | 1,93 M |
| Parc | 18,4 | 29 | 17,5 | 0,15 | 0 | 0 | 0,7 | 522 | 258 | 262 k |
| Partie 2 bots | 21,3 | 35 | 20,5 | 0,22 | 0,30 | 0,11 | 1,0 | 774 | 382 | 510 k |

Résolution adaptative au plancher (70 %) dans les trois cas. Lecture : la physique (corps rigides,
MeshColliders), les SphereCast des billes à 240 Hz et l'IA coûtent ensemble moins de 1 ms ; tout le reste
du thread principal (≈ 95 %) est la soumission du rendu, proportionnelle aux draw calls, dont la passe
d'ombre du soleil représente la majorité (1 923 objets projetant une ombre dans le vestibule).

**Plus gros poste : la passe d'ombre** (objets intérieurs et petits objets qui projettent une ombre du soleil).

## Correction

`PaintballScene.Optimiser` : dans l'enveloppe du château (|x| < 18 m, −10 < z < 12 m), les objets de moins de 3 m
ne projettent plus d'ombre du soleil (les murs, planchers et plafonds, plus grands, continuent d'ombrer l'intérieur) ;
dehors, les objets de moins de 60 cm non plus. 782 renderers concernés. Aucune fuite de lumière visible dans le vestibule
ni le salon (vérifié sur captures).

## Après (même build Development, mêmes scènes)

| Scène | Image (ms) | p95 | Thread principal | Physique (Simulate) | SphereCast | Billes | Bots | Draw calls | Ombres portées | Triangles | Échelle de rendu |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Vestibule | 19,0 | 28 | 23,8 | 0,20 | 0 | 0 | 0 | 1 697 | 1 004 | 1,30 M | 85 % |
| Parc | 16,5 | 23 | 16,7 | 0,11 | 0 | 0 | 0 | 512 | 248 | 262 k | 80 % |
| Partie 2 bots | 16,8 | 22 | 16,7 | 0,16 | 0,10 | 0,28 | 0,08 | 650 | 316 | 329 k | 80 % |

Vestibule : −47 % sur l'image moyenne, −35 % de draw calls, −48 % d'objets dans la passe d'ombre, et la résolution
adaptative remonte de 70 à 85 %. Parc et partie : proches de 60 images/s (16,7 ms, synchronisation du navigateur).
Les postes suivants seraient les draw calls de l'intérieur (1 697 dans le vestibule ; regroupement statique
ou fusion des petits objets par matériau) ; la physique et l'IA ne justifient pas d'optimisation.

## Build Release après correction (`BuildWebMiseAJour`)

| Scène | Image (ms) | p95 | Échelle de rendu | Avant (Release, mesures antérieures) |
|---|---|---|---|---|
| Vestibule | 17,4 à 20,2 | 22 à 27 | 75 à 85 % | 21,7 ms avec optimisations (36 ms sans) |
| Parc | 16,7 à 18,5 | 17 | 85 à 90 % | 17,3 ms sans optimisations |
| Partie 2 bots (Facile) | 16,7 à 18,0 (20,1 château plein cadre) | 18 à 24 (40) | 75 à 90 % | — |

Deux séries (avant et après redémarrage de la machine). Dans la partie, le coût dépend du point d'apparition :
650 draw calls face au parc, jusqu'à 1 890 avec le château dans le champ. Billes 0,16 ms, bots 0,06 ms.

Le parc et la partie tiennent 60 images/s (plafond de `requestAnimationFrame`) ; le vestibule s'en approche.
Zéro erreur dans la console de Chrome.

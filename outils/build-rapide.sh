#!/usr/bin/env bash
# Build web rapide dans l'éditeur déjà ouvert (outils/editeur.sh), puis recharger http://localhost:8086.
#   outils/build-rapide.sh          scripts et ressources (cas courant)
#   outils/build-rapide.sh scene    réapplique aussi marqueur, matériaux, NavMesh et occlusion
#   outils/build-rapide.sh publication   builds ordinateur + mobile (ASTC) en Brotli dans publication/
#   outils/build-rapide.sh double        les deux builds en local (http://localhost:8086/?mobile=1)
#   outils/build-rapide.sh complet       après un changement de modèle Blender (réimport des GLB, scène reconstruite)
# Pendant le build, mieux vaut fermer les onglets du jeu (concurrence pour les cœurs).
set -euo pipefail
cd "$(dirname "$0")/.."
d=travail/build-rapide; mkdir -p "$d"; rm -f "$d/resultat.json"
pgrep -f "Editor/Unity -projectpath .*chateau-saint-victor/unity" >/dev/null || { echo "Pas d'éditeur ouvert : lancer outils/editeur.sh"; exit 1; }
debut=$(date +%s)
echo "${1:-web}" > "$d/demande"
while [ ! -f "$d/resultat.json" ]; do
  sleep 2
  pgrep -f "Editor/Unity -projectpath .*chateau-saint-victor/unity" >/dev/null || { echo "Éditeur arrêté pendant le build (mémoire ?) : relancer outils/editeur.sh"; exit 1; }
  [ $(( $(date +%s) - debut )) -gt 5400 ] && { echo "Délai dépassé"; exit 1; }
done
cat "$d/resultat.json"; echo
echo "Durée totale : $(( $(date +%s) - debut )) s"
if ! grep -q '"statut":"ok"' "$d/resultat.json"; then
  echo "Erreurs (unity/Logs/Editor.log) :"; grep -E "error CS|Exception" unity/Logs/Editor.log | tail -40 | sort -u | tail -12
  exit 1
fi

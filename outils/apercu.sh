#!/usr/bin/env bash
# Aperçu en quelques secondes, sans build, dans l'éditeur chaud (outils/editeur.sh) : décor de la scène.
#   outils/apercu.sh "nom x y z cap [tangage] [focale]" ...   (repère Blender D-003, pieds ; cap 0 = vers le sud)
#   outils/apercu.sh                                           vues par défaut (entrée nord, vestibule, bibliothèque, toit)
# Images dans travail/apercu/<nom>.png. Après un changement de GLB, il faut d'abord outils/build-rapide.sh complet.
set -euo pipefail
cd "$(dirname "$0")/.."
d=travail/apercu; mkdir -p "$d"; rm -f "$d/fini"
pgrep -f "Editor/Unity -projectpath .*chateau-saint-victor/unity" >/dev/null || { echo "Pas d'éditeur ouvert : lancer outils/editeur.sh"; exit 1; }
if [ $# -eq 0 ]; then
  set -- "entree_nord 0 -20.25 -1.44 0 4" "perron_ouest -8.4 -15.25 -1.44 50 2" "vestibule 0 -7.9 0 0 0" \
         "bibliotheque 0.4 -4.0 5.35 180 0" "toit 0 0 15.3 180 -5"
fi
printf '%s\n' "$@" > "$d/demande.tmp"; mv "$d/demande.tmp" "$d/demande"
debut=$(date +%s)
while [ ! -f "$d/fini" ]; do
  sleep 0.5
  [ $(( $(date +%s) - debut )) -gt 300 ] && { echo "Délai dépassé (éditeur occupé ?)"; exit 1; }
done
cat "$d/fini"; echo "$(( $(date +%s) - debut )) s → $d/"

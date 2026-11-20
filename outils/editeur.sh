#!/usr/bin/env bash
# Ouvre l'éditeur Unity du projet en arrière-plan (sans fenêtre) et le laisse tourner : les builds
# rapides (outils/build-rapide.sh) s'y exécutent sans redémarrage. Fermer : unity close unity
set -euo pipefail
cd "$(dirname "$0")/.."
if pgrep -f "Editor/Unity -projectpath .*chateau-saint-victor/unity" >/dev/null; then echo "Éditeur déjà ouvert."; exit 0; fi
unity open unity --batchmode --build-target WebGL >/dev/null 2>&1 || true
echo "Éditeur lancé (prêt dans 1 à 3 min)."

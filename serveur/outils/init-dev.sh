#!/bin/sh
# Prépare l'environnement local : .dev.vars (clé aléatoire, mode dev) et base D1 locale.
set -e
cd "$(dirname "$0")/.."
if [ ! -f .dev.vars ]; then
  umask 077
  printf 'CLE_SESSION=%s\nMODE_DEV=1\nORIGINE=http://localhost:8787\n' "$(head -c 48 /dev/urandom | base64 | tr -d '\n=+/')" > .dev.vars
  echo ".dev.vars créé"
fi
# Dossier des Static Assets, rempli par `npm run preparer-jeu`.
mkdir -p jeu
npx wrangler d1 migrations apply paintball --local

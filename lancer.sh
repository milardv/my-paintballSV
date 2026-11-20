#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec ./build/linux/ChateauSaintVictor.x86_64 -screen-fullscreen 0 -screen-width 1600 -screen-height 900 "$@"

#!/usr/bin/env bash
# Captures du vrai jeu web (objets créés au lancement compris) : charge build/web une seule fois dans Chrome
# sans écran (WebGL logiciel), puis fige la caméra sur chaque vue (VerificationVue, ?vue=1) et la capture.
#   outils/verif-jeu.sh "nom|x,y,z,cap[,tangage]" ...    (repère Blender D-003, pieds ; cap 0 = vers le sud)
#   outils/verif-jeu.sh "carte|carte" "lunette|lunette" "velo|velo|rapport" "neige|neige|rapport"   préréglages (3e champ : attente en s, ou « rapport »)
# Images dans travail/verif-jeu/<nom>.png. Pour le décor seul, outils/apercu.sh est bien plus rapide (10 s).
set -euo pipefail
cd "$(dirname "$0")/.."
d=travail/verif-jeu; mkdir -p "$d"
[ $# -eq 0 ] && set -- "carte|carte" "lunette|lunette|5" "velo|velo|rapport" "neige|neige|rapport"
pgrep -f "http[.]server 8086" >/dev/null || { (setsid nohup python3 -m http.server 8086 --bind 127.0.0.1 --directory build/web >/dev/null 2>&1 &); sleep 1; }
export AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome
export AGENT_BROWSER_ARGS="--use-angle=swiftshader,--enable-unsafe-swiftshader,--ignore-gpu-blocklist"
ab() { agent-browser --session verif-jeu "$@" 2>/dev/null; }
ab open "http://localhost:8086/?vue=1" >/dev/null; ab set viewport 1280 720 >/dev/null
debut=$(date +%s)
until ab eval "window.unityInstance ? 1 : 0" | grep -q '^1'; do
  sleep 3; [ $(( $(date +%s) - debut )) -gt 400 ] && { echo "Chargement trop long"; ab close; exit 1; }
done
sleep 6
echo "chargé en $(( $(date +%s) - debut )) s"
for v in "$@"; do
  IFS='|' read -r nom arg attente <<< "$v"
  ab eval "window.paintballVerification=null; unityInstance.SendMessage('VerificationVue','Vue','$arg')" >/dev/null
  if [ "${attente:-4}" = rapport ]; then      # attendre le rapport de l'essai (au plus 4 min)
    for i in $(seq 1 80); do sleep 3; ab eval "window.paintballVerification?1:0" | grep -q '^1' && break; done; sleep 3
  else sleep "${attente:-4}"; fi
  ab screenshot "$d/$nom.png" >/dev/null && echo "$nom → $d/$nom.png"
  r=$(ab eval "JSON.stringify(window.paintballVerification||null)" | tail -1); [ "$r" != '"null"' ] && echo "  $r"
done
ab console | grep -iE "exception|error" | grep -v "inactive controller" | sort | uniq -c | head -8 || true
ab close >/dev/null

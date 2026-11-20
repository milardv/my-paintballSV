#!/usr/bin/env python3
"""App de suivi locale : python3 suivi/serveur.py [port]  →  http://localhost:8765"""
import http.server, json, mimetypes, pathlib, subprocess, sys, urllib.parse

R = pathlib.Path(__file__).resolve().parent.parent
PERMIS = ("travail/vignettes/", "travail/plan", "rendus/", "sources/")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def envoyer(self, code, corps, type_="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        chemin = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if chemin == "/":
            return self.envoyer(200, (R / "suivi/index.html").read_bytes(), "text/html; charset=utf-8")
        if chemin == "/api/etat":
            f = R / "travail/etat.json"
            e = json.loads(f.read_text()) if f.exists() else {}
            d = R / "DECISIONS.md"
            e["decisions"] = d.read_text() if d.exists() else ""
            e["plan"] = sorted(p.name for p in (R / "travail").glob("plan*.svg"))
            return self.envoyer(200, json.dumps(e, ensure_ascii=False).encode())
        if chemin.startswith("/f/"):
            rel = chemin[3:]
            f = (R / rel).resolve()
            if rel.startswith(PERMIS) and f.is_file() and R in f.parents:
                return self.envoyer(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.envoyer(404, b"{}")

    def do_POST(self):
        if self.path != "/api/valide":
            return self.envoyer(404, b"{}")
        corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        r = subprocess.run([sys.executable, str(R / "outils/etat.py"), "valide", str(corps.get("id", "")), str(corps.get("reponse", ""))],
                           capture_output=True, text=True)
        self.envoyer(200 if r.returncode == 0 else 400, json.dumps({"ok": r.returncode == 0, "erreur": r.stderr}).encode())


if __name__ == "__main__":
    print(f"Suivi : http://localhost:{PORT}")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

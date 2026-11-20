#!/usr/bin/env python3
"""État partagé du chantier (travail/etat.json), sûr en parallèle (verrou fcntl).

  etat.py                          résumé
  etat.py init                     (ré)initialise phases et tâches depuis WORKFLOW
  etat.py tache <id> <statut> [note] [--agent nom]   statut : a-faire|en-cours|fait|bloque|a-valider
  etat.py photo <id> <statut> [zone]
  etat.py log "<message>"
  etat.py rendu <chemin.png> "<légende>"
  etat.py attente <id> "<question>"   /  etat.py valide <id> "<réponse>"
  etat.py decision "<titre>" "<décision>" ["<pourquoi>"]   (ajoute à DECISIONS.md)
"""
import datetime, fcntl, json, pathlib, re, sys
R = pathlib.Path(__file__).resolve().parent.parent
F, LOCK, DEC = R / "travail/etat.json", R / "travail/.etat.lock", R / "DECISIONS.md"
now = lambda: datetime.datetime.now().isoformat(timespec="seconds")

PHASES = [
 ("P0", "Préparation", [("P0.1", "Extraire et inventorier les photos"), ("P0.2", "Triage par zone")]),
 ("P1", "Analyse des photos (parallèle par zone)", [
   ("P1.ext", "Fiches extérieur : façades, toiture, jardin"),
   ("P1.int-rdc", "Fiches intérieur RDC"), ("P1.int-etage", "Fiches intérieur étage"),
   ("P1.inventaire", "Inventaire consolidé des éléments (mobilier, décors, végétation)")]),
 ("P2", "Extérieur", [
   ("P2.emprise", "Emprise et volumes (vue zénithale W12)"),
   ("P2.facade-sud", "Façade jardin (sud)"), ("P2.facade-nord", "Façade d'entrée (nord)"),
   ("P2.facades-laterales", "Façades est et ouest"), ("P2.toiture", "Toiture, souches, verrière, balustrades"),
   ("P2.terrasse", "Terrasse, perron, balustres"), ("P2.jardin", "Parc : pelouse, bassin, mâts, allées"),
   ("P2.vegetation", "Végétation : platanes, pins, cyprès, palmiers, olivier"),
   ("P2.annexes", "Tennis, parking, piscine, voitures, mobilier extérieur"),
   ("P2.assemblage", "Assemblage extérieur et rendus de contrôle")]),
 ("P3", "Plan intérieur", [
   ("P3.graphe", "Graphe des pièces (enchaînement des photos)"),
   ("P3.plan", "Plan RDC + étage proposé (SVG)"),
   ("P3.validation", "VALIDATION du plan par Valentin")]),
 ("P4", "Intérieur (parallèle par pièce)", [
   ("P4.coque", "Coque : murs, planchers, ouvertures depuis le plan validé"),
   ("P4.vestibule", "Vestibule + escalier d'honneur"), ("P4.palier", "Palier étage + coupole"),
   ("P4.salons", "Salons (vert, bow-window, tableau)"), ("P4.billard", "Salle de billard"),
   ("P4.salle-a-manger", "Salle à manger"), ("P4.bibliotheque", "Bibliothèque"),
   ("P4.bureau", "Bureau"), ("P4.chambres", "Chambres"), ("P4.couloirs", "Couloirs et petit salon"),
   ("P4.assemblage", "Assemblage intérieur et rendus de contrôle")]),
 ("P5", "Jeu Unity", [("P5.import", "Import, collisions, LOD"), ("P5.eclairage", "Lumière, ciel, son d'ambiance"),
   ("P5.controle", "Contrôleur d'exploration, portes, interactions"), ("P5.build", "Build Linux")]),
]

def charger():
    return json.loads(F.read_text()) if F.exists() else {}

def ecrire(e):
    e["maj"] = now(); tmp = F.with_suffix(".tmp"); tmp.write_text(json.dumps(e, ensure_ascii=False, indent=1)); tmp.replace(F)

def log(e, msg): e.setdefault("journal", []).append({"t": now(), "msg": msg}); e["journal"] = e["journal"][-300:]

def tache(e, tid):
    for p in e["phases"]:
        for t in p["taches"]:
            if t["id"] == tid: return t
    sys.exit(f"tâche inconnue : {tid}")

def main(a):
    LOCK.parent.mkdir(exist_ok=True)
    with open(LOCK, "w") as l:
        fcntl.flock(l, fcntl.LOCK_EX); e = charger()
        if not a:
            for p in e.get("phases", []):
                print(p["id"], p["titre"]); [print(f"   {t['statut']:10} {t['id']:22} {t.get('note','')}") for t in p["taches"]]
            for q in e.get("attente", []):
                if not q.get("reponse"): print("EN ATTENTE:", q["id"], q["question"])
            return
        c = a[0]
        if c == "init":
            old = {t["id"]: t for p in e.get("phases", []) for t in p["taches"]}
            e["projet"] = "Château Saint-Victor — exploration"
            e["phases"] = [{"id": i, "titre": ti, "taches": [old.get(k, {"id": k, "titre": v, "statut": "a-faire"}) | {"titre": v} for k, v in ts]} for i, ti, ts in PHASES]
            e["photos"] = json.loads((R / "travail/photos.json").read_text())
            e.setdefault("rendus", []); e.setdefault("attente", []); log(e, "État initialisé")
        elif c == "tache":
            t = tache(e, a[1]); t["statut"] = a[2]; t["maj"] = now()
            rest = [x for x in a[3:] if not x.startswith("--agent")]
            if "--agent" in a: t["agent"] = a[a.index("--agent") + 1]; rest = [x for x in rest if x != t["agent"]]
            if rest: t["note"] = rest[0]
            log(e, f"{a[1]} → {a[2]}" + (f" : {rest[0]}" if rest else ""))
        elif c == "photo":
            p = next(p for p in e["photos"] if p["id"] == a[1]); p["statut"] = a[2]
            if len(a) > 3: p["zone"] = a[3]
        elif c == "log": log(e, a[1])
        elif c == "rendu":
            e["rendus"].append({"t": now(), "chemin": a[1], "legende": a[2] if len(a) > 2 else ""}); e["rendus"] = e["rendus"][-60:]
            log(e, f"Rendu : {a[1]}")
        elif c == "attente":
            e["attente"] = [q for q in e["attente"] if q["id"] != a[1]] + [{"id": a[1], "question": a[2], "t": now()}]
            log(e, f"En attente de validation : {a[1]}")
        elif c == "valide":
            q = next(q for q in e["attente"] if q["id"] == a[1]); q["reponse"] = a[2]; q["t_reponse"] = now()
            log(e, f"Validé {a[1]} : {a[2]}")
        elif c == "decision":
            txt = DEC.read_text() if DEC.exists() else "# Décisions\n"
            n = max([int(x) for x in re.findall(r"^## D-(\d+)", txt, re.M)] or [0]) + 1
            bloc = f"\n## D-{n:03d} — {a[1]}\n*{datetime.date.today()}*\n\n{a[2]}\n" + (f"\n**Pourquoi :** {a[3]}\n" if len(a) > 3 else "")
            DEC.write_text(txt.rstrip("\n") + "\n" + bloc); log(e, f"Décision D-{n:03d} : {a[1]}")
        else: sys.exit(__doc__)
        ecrire(e)

if __name__ == "__main__":
    main(sys.argv[1:])

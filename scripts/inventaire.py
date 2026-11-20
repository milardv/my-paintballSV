"""Consolide les fiches P1 en travail/inventaire.json (P1.inventaire).

Regroupe les éléments par pièce (graphe P3) ou zone extérieure, fusionne les doublons vus sur
plusieurs photos (même catégorie, noms proches : quantité max, photos cumulées) et attribue une
priorité : 1 structurant, 2 signature visible, 3 petit détail.
"""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHES = RACINE / "travail" / "fiches"

# photo -> pièce (ids du graphe P3) ; extérieur : zone de la fiche
PIECE_PHOTO = {
    **{f"P{i:02d}": "E-bibliotheque" for i in range(0, 4)},
    **{f"P{i:02d}": "E-palier" for i in range(4, 10)},
    **{f"P{i:02d}": "E-degagement-no" for i in range(10, 14)},
    **{f"P{i:02d}": "escalier" for i in range(14, 20)},
    "W09": "escalier",
    "P20": "R-vestibule", "P21": "R-vestibule", "P41": "R-vestibule", "W08": "R-vestibule",
    "P22": "R-couloir-ouest", "P36": "R-couloir-est",
    "P23": "R-passage-ouest", "P24": "R-passage-ouest", "P42": "R-passage-est",
    "P25": "R-petit-salon", "P26": "R-petit-salon",
    **{f"P{i:02d}": "R-salon" for i in range(27, 32)},
    **{f"P{i:02d}": "R-billard" for i in range(32, 36)},
    "W07": "R-salon-vert", "W14": "R-salon-vert",
    **{f"P{i:02d}": "E-salle-a-manger" for i in (43, 44, 45, 46, 50, 51)},
    **{f"P{i:02d}": "E-chambre-1" for i in (47, 48, 49)},
    **{f"P{i:02d}": "E-chambre-2" for i in (52, 53, 54)},
    **{f"P{i:02d}": "E-chambre-3" for i in (55, 56, 57)},
}

MOTS_STRUCT = ("corniche", "caisson", "lambris", "boiserie", "colonne", "pilastre", "coupole", "verrière",
               "verriere", "escalier", "volée", "limon", "voûte", "arcade", "balustrade", "soubassement",
               "plafond", "parquet", "dallage", "sol ", "façade", "toit", "souche", "perron", "marche",
               "mur ", "fronton", "bassin", "terrasse", "court", "allée", "cour ", "porte d'entrée",
               "porte-fenêtre", "baie", "fenêtre", "portail", "pelouse")
MOTS_SIGNATURE = ("lustre", "lanterne", "lampadaire", "tableau", "portrait", "marine", "tapisserie", "tapis",
                  "rideau", "billard", "piano", "armoire", "buffet", "bibliothèque", "commode", "canapé",
                  "table", "miroir", "rampe", "garde-corps", "fontaine", "statue", "pendule", "lit",
                  "console", "bergère", "fauteuil", "chaise", "panoplie", "urne", "vasque", "parasol",
                  "platane", "cyprès", "pin", "olivier", "if ", "palmier", "chêne", "laurier", "drapeau",
                  "mât", "plaque", "cheminée", "trumeau", "applique", "rosace", "porte")


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def tete(s, n=4):
    mots = [m for m in norm(s).split() if len(m) > 2 and m not in ("des", "les", "une", "sur", "avec", "aux")]
    return " ".join(mots[:n])


def taille_max(dims):
    if not isinstance(dims, dict):
        return 0
    vals = [v for v in dims.values() if isinstance(v, (int, float))]
    return max(vals) if vals else 0


def priorite(e):
    cat, nom = e.get("categorie"), " " + (e.get("nom") or "").lower() + " "
    if cat in ("architecture", "cheminee"):
        return 1
    if cat == "moulure" and any(m in nom for m in MOTS_STRUCT):
        return 1
    if cat == "vegetation":
        return 2 if (taille_max(e.get("dimensions_estimees")) >= 3 or any(m in nom for m in MOTS_SIGNATURE)) else 3
    if cat in ("tableau", "tapis", "ferronnerie"):
        return 2
    if cat == "luminaire":
        return 2 if any(m in nom for m in ("lustre", "lanterne", "lampadaire", "applique")) else 3
    if cat in ("mobilier", "textile", "moulure"):
        return 2 if (taille_max(e.get("dimensions_estimees")) >= 0.9 or any(m in nom for m in MOTS_SIGNATURE)) else 3
    return 2 if (taille_max(e.get("dimensions_estimees")) >= 1.5 or any(m in nom for m in MOTS_SIGNATURE if m != "porte")) else 3


def proche(a, b):
    if a["categorie"] != b["categorie"]:
        return False
    na, nb = norm(a["nom"]), norm(b["nom"])
    if na == nb:
        return True
    ca = {m for m in na.split() if len(m) > 2}
    cb = {m for m in nb.split() if len(m) > 2}
    if ca and cb and (ca <= cb or cb <= ca):
        return True
    ta, tb = tete(a["nom"]), tete(b["nom"])
    return SequenceMatcher(None, ta, tb).ratio() >= 0.78 or SequenceMatcher(None, na, nb).ratio() >= 0.72


def main():
    pieces = {}
    for f in sorted(FICHES.glob("*.json")):
        d = json.loads(f.read_text())
        pid = d["id"]
        cle = PIECE_PHOTO.get(pid) or d.get("zone", "?")
        p = pieces.setdefault(cle, {"photos": [], "revetements": {}, "elements": []})
        p["photos"].append(pid)
        for champ in ("sol", "plafond", "murs_revetement"):
            v = d.get(champ)
            if v and not cle.startswith("ext"):
                p["revetements"].setdefault(champ, [])
                if v not in [x["texte"] for x in p["revetements"][champ]]:
                    p["revetements"][champ].append({"texte": v, "photo": pid})
        for e in d.get("elements", []):
            e = dict(e)
            q = e.get("quantite") or 1
            try:
                q = int(q)
            except (TypeError, ValueError):
                q = 1
            for x in p["elements"]:
                if proche(x, e):
                    x["quantite"] = max(x["quantite"], q)
                    if pid not in x["photos"]:
                        x["photos"].append(pid)
                    if len(e["nom"]) > len(x["nom"]):
                        x.setdefault("variantes", []).append(x["nom"])
                        x["nom"] = e["nom"]
                    elif e["nom"] != x["nom"] and e["nom"] not in x.get("variantes", []):
                        x.setdefault("variantes", []).append(e["nom"])
                    break
            else:
                p["elements"].append({
                    "nom": e.get("nom"), "categorie": e.get("categorie"), "quantite": q,
                    "dimensions_estimees": e.get("dimensions_estimees"), "materiau": e.get("materiau"),
                    "couleur": e.get("couleur"), "position": e.get("position_dans_piece"),
                    "photos": [pid],
                })
    total = 0
    for cle, p in pieces.items():
        for x in p["elements"]:
            x["priorite"] = priorite(x)
        p["elements"].sort(key=lambda x: (x["priorite"], x["categorie"] or "", x["nom"] or ""))
        p["nb"] = {str(k): sum(1 for x in p["elements"] if x["priorite"] == k) for k in (1, 2, 3)}
        total += len(p["elements"])
    sortie = {
        "version": 1,
        "source": "travail/fiches/*.json, regroupées par pièce du graphe P3 (travail/graphe.json) ou zone ext.",
        "priorites": {"1": "structurant", "2": "signature visible", "3": "petit détail"},
        "note": "Doublons fusionnés automatiquement (même catégorie, noms proches) : quantité = max vue sur une "
                "photo, photos cumulées, autres libellés dans 'variantes'. Revêtements (sol, plafond, murs) à part.",
        "total_elements": total,
        "pieces": dict(sorted(pieces.items())),
    }
    (RACINE / "travail" / "inventaire.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1))
    for cle, p in sorted(pieces.items()):
        print(f"{cle:22s} {len(p['photos']):2d} photos  {len(p['elements']):3d} éléments  {p['nb']}")
    print("total", total)


if __name__ == "__main__":
    main()

"""Décors des pièces recalés pièce par pièce sur la coque du relevé du 19/11.

blender -b --factory-startup --python scripts/recaler_decors.py -- piece_salons piece_reception ...
Lit export/composants/<nom>.glb (repère de l'ancienne coque, travail/releve-2026-11-19/coque-avant-releve.json),
écrit export/releve-2026-11-19/<nom>.glb, .blend et -controle.json ; jamais les originaux.

Chaque objet est rattaché à une pièce (préfixe du nom, sinon position). Les revêtements (murs, boiseries,
corniches, sols…) suivent une application affine par morceaux de l'intérieur ancien vers l'intérieur nouveau ;
le mobilier garde ses dimensions et sa distance au mur le plus proche. Les nouvelles portes (coque.json du relevé)
et fenêtres (bati recalé) sont ensuite découpées dans les revêtements.
"""
import json
import os
import re
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "export" / "releve-2026-11-19"
ANCIEN = json.loads((ROOT / "travail/releve-2026-11-19/coque-avant-releve.json").read_text())
NOUVEAU = json.loads((OUT / "coque.json").read_text())
BATI = json.loads((OUT / "bati-controle.json").read_text())


def boite(p):
    xs = [q[0] for q in p["polygone_interieur"]]
    ys = [q[1] for q in p["polygone_interieur"]]
    return (min(xs), max(xs)), (min(ys), max(ys))


A = {p["id"]: p for p in ANCIEN["pieces"]}
N = {p["id"]: p for p in NOUVEAU["pieces"]}

# Pièce d'arrivée et application (x, y) par pièce : listes (ancien, nouveau) croissantes.
CAGE_X = [(-3.70, -3.00), (-2.00, -1.55), (-1.25, -0.95), (1.25, 0.95), (2.00, 1.55), (3.70, 3.00)]
CAGE_Y_BAS = [(-3.80, -3.20), (1.24, 1.30), (3.65, 2.60)]
CAGE_Y_HAUT = [(-5.05, -3.00), (-1.76, -1.45), (1.24, 1.30), (3.65, 2.70)]
Z_CAGE = 3.30   # sous le repos : application du RDC ; au-dessus : volées de retour, repos, palier
CIBLE = {
    "galerie_est": ((4.30, 5.50), (3.60, 5.40), (-5.20, 0.90), (-1.40, 0.60)),
    "galerie_ouest": ((-5.50, -4.30), (-5.40, -3.60), (-5.20, 0.90), (-1.40, 0.60)),
    "degagement_no": ((-10.50, -5.70), (-10.00, -5.70), (-5.20, -3.60), (-3.30, -1.55)),
    "degagement_est": ((4.30, 10.50), (10.60, 15.80), (-6.30, -1.60), (-0.83, 1.15)),
    "petit_salon": None,
}
GROUPE_CAGE = {"escalier", "palier", "vide_cage", "passage_ouest", "passage_est", "petit_salon"}
# Pièce du relevé qui reçoit le décor d'une pièce disparue
DEVIENT = {"degagement_no": "etage_ouest"}

COUVRANT = re.compile(
    r"murs|revetement|parquet|plinthe|corniche|boiserie|chambranle|moulure|_decor$|_decor_|papier_peint|"
    r"bandes|dallage|voute|arc_doubleau|plafond|lambris|soubassement|panneaux|caisson|tympan|placard|"
    r"lambrequin|niche|panneau_bois|dessus_de_porte|tapis_repos|barres_tapis|rampes|balustrade|"
    r"coupole|oculi|puits|arcades|departs_rampe|tapisserie|peinture|bibliotheque_meuble_sud|_tableaux$|petite_porte")
# Meubles sans place contre leur mur d'origine (porte nouvelle) : rotation (degrés) et appui sur un autre mur
POSE = {"piece_no_bibliotheque": (90.0, ("xmin", -15.78), ("ycentre", -4.30))}
# Voûte réduite au noyau central (R18) : caissons, oculi et cadre du puits suivent la nouvelle coupole
COUPOLE_DECOR = re.compile(r"palier_coupole")
COUPOLE_X = [(-3.70, -3.00), (3.70, 3.00)]
COUPOLE_Y = [(-5.05, -1.45), (3.65, 1.50)]
COUPOLE_Z = [(10.60, 10.00), (12.00, 12.00)]
# Décors des anciennes galeries longitudinales et des trois arcades par côté : sans équivalent au relevé, ils
# fermeraient les passages ouverts du palier (R03) ; la lanterne de la galerie est pendrait dans la trémie
# de l'escalier des combles.
SUPPRIMES = re.compile(r"^(galerie_est_decor|galerie_ouest_decor|galerie_est_lanterne|palier_arcades_decor|"
                       r"palier_balustrade_(est|ouest)|lumiere_galerie_est_lanterne)")
# Guéridon et bouquet du palier : le palier du relevé n'a que 1,55 m de profondeur ; contre le mur nord, à l'ouest
# de la porte de la bibliothèque (centre xy visé)
DEPLACER = {"palier_gueridon": (-1.10, -2.78), "palier_bouquet_roses": (-1.10, -2.78),
            # porte-manteau (photo du 19/11) : retour est de l'avant-corps (x = 2,7), entre la fenêtre et l'angle
            "vestibule_vestiaire": (2.445, -6.075),
            # piano droit du petit salon dos au mur ouest, ses deux candélabres dessus (demande du 19/11)
            "petit_salon_piano": (-2.575, 2.05), "petit_salon_candelabre_1": (-2.765, 1.62),
            "petit_salon_candelabre_2": (-2.765, 2.42),
            # marine (P55-P57) : même mur ouest, au nord de la porte du pavillon 53 (R03, y = 4,19)
            "chambre_3_tableau_marine": (-9.955, 2.15)}
# Parties de décor sans support au relevé, retirées par zone (x0, y0, z0), (x1, y1, z1) : rampe de l'ancien palier
# (le garde-corps du relevé borde la trémie, coque.py) et panneaux des murs de cage disparus au droit du palier
ZONES = {
    "escalier_rampes_volutes": [((-3.1, -3.3, 5.3), (3.1, -1.56, 7.5))],
    "palier_panneaux_cage": [((-3.7, -3.3, 5.3), (-2.85, -1.45, 10.1)), ((2.85, -3.3, 5.3), (3.7, -1.45, 10.1))],
}
BALUSTRE = re.compile(r"^palier_balustre_")
Y_ARCADE = (-0.73, 0.63)
# Écran à colonnes du vestibule (P41) : sur les axes de la nouvelle cage, l'axe de l'écran passe de -3,50 à -3,45
ECRAN = re.compile(r"vestibule_colonne|escalier_departs_rampe")
SOL_PLAFOND = re.compile(r"parquet|dallage|bandes|plafond|corniche|coupole|oculi|puits|caisson|rosace|tapis")


def interp(v, pts):
    a = np.array([p[0] for p in pts])
    b = np.array([p[1] for p in pts])
    # au-delà des nus intérieurs (épaisseur des murs, embrasures) : translation, sans mise à l'échelle
    pente0 = pente1 = 1.0
    return np.where(v < a[0], b[0] + (v - a[0]) * pente0,
                    np.where(v > a[-1], b[-1] + (v - a[-1]) * pente1, np.interp(v, a, b)))


def applications(pid):
    """(xmap, ymap_bas, ymap_haut) de la pièce ancienne pid."""
    if pid in GROUPE_CAGE:
        if pid == "petit_salon":
            return CAGE_X, [(1.24, 1.30), (3.65, 3.40)], CAGE_Y_HAUT
        return CAGE_X, CAGE_Y_BAS, CAGE_Y_HAUT
    (ax, ay) = boite(A[pid])
    if CIBLE.get(pid):
        ax, nx, ay, ny = CIBLE[pid]
    else:
        nx, ny = boite(N[DEVIENT.get(pid, pid)])
    xm = [(ax[0], nx[0]), (ax[1], nx[1])]
    ym = [(ay[0], ny[0]), (ay[1], ny[1])]
    return xm, ym, ym


def piece_de(nom, centre, zmin):
    nom = nom.lower()
    ids = sorted(A, key=len, reverse=True)
    for pid in ids:
        if nom.startswith(pid + "_") or nom == pid:
            return pid
    if nom.startswith("escalier") or nom.startswith("lumiere_escalier"):
        return "escalier"
    if nom.startswith("palier"):
        return "palier"
    for pid in ids:
        if nom.startswith("lumiere_" + pid):
            return pid
    niv = "rdc" if zmin < 5.0 else "etage"
    for p in ANCIEN["pieces"]:
        if p["niveau"] != niv:
            continue
        for x0, y0, x1, y1 in p["rect_plan"]:
            if x0 <= centre[0] <= x1 and y0 <= centre[1] <= y1:
                return p["id"]
    return None


def appliquer(points, pid, nom=""):
    if COUPOLE_DECOR.search(nom):
        out = points.copy()
        out[:, 0] = interp(points[:, 0], COUPOLE_X)
        out[:, 1] = interp(points[:, 1], COUPOLE_Y)
        out[:, 2] = interp(points[:, 2], COUPOLE_Z)
        return out
    if ECRAN.search(nom):
        out = points.copy()
        out[:, 0] = interp(points[:, 0], CAGE_X)
        out[:, 1] = points[:, 1] + 0.05
        return out
    xm, yb, yh = applications(pid)
    out = points.copy()
    out[:, 0] = interp(points[:, 0], xm)
    haut = points[:, 2] >= Z_CAGE if pid in GROUPE_CAGE else (points[:, 2] >= 5.0)
    out[:, 1] = np.where(haut, interp(points[:, 1], yh), interp(points[:, 1], yb))
    return out


def rigide(points, pid, nom):
    """Translation seule : distance au mur conservée sur chaque axe si l'objet est contre un mur."""
    xm, yb, yh = applications(pid)
    lo, hi = points.min(axis=0), points.max(axis=0)
    c = (lo + hi) / 2
    ym = yh if (c[2] >= (Z_CAGE if pid in GROUPE_CAGE else 5.0)) else yb
    d = np.zeros(3)
    for k, m in ((0, xm), (1, ym)):
        a0, a1 = m[0][0], m[-1][0]
        b0, b1 = m[0][1], m[-1][1]
        g0, g1 = lo[k] - a0, a1 - hi[k]
        if 0 <= g0 < 0.6 and g0 <= g1:
            d[k] = b0 + g0 - lo[k]
        elif 0 <= g1 < 0.6:
            d[k] = b1 - g1 - hi[k]
        else:
            d[k] = float(interp(np.array([c[k]]), m)[0]) - c[k]
        # reste dans la pièce nouvelle quand il y tient
        n0, n1 = lo[k] + d[k], hi[k] + d[k]
        if hi[k] - lo[k] < b1 - b0:
            if n0 < b0 - 0.02:
                d[k] += b0 - n0
            elif n1 > b1 + 0.02:
                d[k] -= n1 - b1
    # fontaine et décor du petit salon : contre le bloc de la fontaine (R07), plus contre le mur du salon
    if pid == "petit_salon" and abs(c[0]) < 1.3 and hi[1] > 3.3:
        d[1] = 2.55 - hi[1]
    return points + d


def degager(cible, pid, portes, bornes, mural=False):
    """Fait glisser un meuble le long de son mur hors des nouvelles portes (pas de 5 cm, 3 m au plus)."""
    lo, hi = cible.min(axis=0), cible.max(axis=0)

    def gene(d):
        for b0, b1, kk in portes:
            inter = np.minimum(hi + d, np.array(b1)) - np.maximum(lo + d, np.array(b0))
            if np.all(inter > 0.03):
                return (b0, b1, kk)
        return None

    p = gene(np.zeros(3))
    if p is None:
        return np.zeros(3)
    b0, b1, k = p                                      # k : axe de franchissement de la porte
    (x0, x1), (y0, y1) = bornes
    # d'abord le long du mur, puis en s'en écartant (jamais pour un objet accroché au mur)
    for axe in ((1 - k,) if mural else (1 - k, k)):     # 1 - k : le long du mur
        lim = ((x0, x1), (y0, y1))[axe]
        for pas in range(1, 61):
            for sgn in (1, -1):
                d = np.zeros(3)
                d[axe] = sgn * pas * 0.05
                if lo[axe] + d[axe] < lim[0] - 0.02 or hi[axe] + d[axe] > lim[1] + 0.02:
                    continue
                if gene(d) is None:
                    return d
    return np.zeros(3)


TRAVERSEE = []   # axe de franchissement de chaque porte (perpendiculaire au mur), dans l'ordre des coupeurs


def coupeurs():
    """Boîtes (min, max) des nouvelles portes puis des fenêtres, au travers des murs ; nombre de portes."""
    out = []
    TRAVERSEE.clear()
    vus = set()
    for p in NOUVEAU["pieces"]:
        for o in p["portes"]:
            cle = (round(o["centre"][0], 2), round(o["centre"][1], 2), round(o["centre"][2], 2))
            if cle in vus:
                continue
            vus.add(cle)
            x, y, z = o["centre"]
            e = o["epaisseur_mur"] / 2 + 0.5
            w = o["largeur"] / 2
            if "y =" in o["mur"]:
                out.append(((x - w, y - e, z + 0.025), (x + w, y + e, z + o["hauteur"])))
                TRAVERSEE.append(1)
            else:
                out.append(((x - e, y - w, z + 0.025), (x + e, y + w, z + o["hauteur"])))
                TRAVERSEE.append(0)
    nb_portes = len(out)
    for o in BATI["objets"]:
        m = re.match(r"bati_vitrage_([NSEO]|PAN)_(f|pf)_(rdc|etage|bow|pan)", o["nom"])
        if not m:
            continue
        lo, hi = np.array(o["min"]), np.array(o["max"])
        sens = m.group(1)
        lo, hi = lo.copy(), hi.copy()
        lo[2] = max(lo[2] - 0.1, 0.025 if m.group(3) != "etage" else 5.375)
        hi[2] += 0.1
        if sens in ("E", "O"):
            lo[0] -= 0.9
            hi[0] += 0.9
            lo[1] -= 0.05
            hi[1] += 0.05
        elif sens in ("N", "S"):
            lo[1] -= 0.9
            hi[1] += 0.9
            lo[0] -= 0.05
            hi[0] += 0.05
        else:
            lo[:2] -= 0.5
            hi[:2] += 0.5
        out.append((tuple(lo), tuple(hi)))
    return out, nb_portes


def fenetres_bati():
    """Vitrages du bâti recalé : (min, max, axe le long du mur) ; pans coupés ignorés."""
    out = []
    for o in BATI["objets"]:
        m = re.match(r"bati_vitrage_([NSEO])_(f|pf)_", o["nom"])
        if m:
            out.append((np.array(o["min"]), np.array(o["max"]), 0 if m.group(1) in ("N", "S") else 1))
    return out


def ilots(me):
    """Pièces séparées d'un maillage (rideaux d'une pièce exportés en un seul objet) : indice d'îlot par sommet."""
    n = len(me.vertices)
    parent = np.arange(n)

    def racine(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in me.edges:
        a, b = racine(e.vertices[0]), racine(e.vertices[1])
        if a != b:
            parent[a] = b
    return np.array([racine(i) for i in range(n)])


def caler_rideaux(c, ids, fenetres):
    out = c.copy()
    for k in np.unique(ids):
        sel = ids == k
        out[sel] = caler_rideau(c[sel], fenetres)
    return out


def caler_rideau(c, fenetres):
    """Rideau recalé d'un bloc devant une baie déplacée : glissé le long du mur jusqu'au bord du vitrage."""
    lo, hi = c.min(axis=0), c.max(axis=0)
    ctr = (lo + hi) / 2
    for wlo, whi, ax in fenetres:
        n = 1 - ax
        if not (wlo[2] - 0.5 < ctr[2] < whi[2] + 0.5) or abs(ctr[n] - (wlo[n] + whi[n]) / 2) > 0.7:
            continue
        if hi[ax] <= wlo[ax] + 0.05 or lo[ax] >= whi[ax] - 0.05:
            continue
        mid = (wlo[ax] + whi[ax]) / 2
        decal = (wlo[ax] - 0.02 - hi[ax]) if ctr[ax] < mid else (whi[ax] + 0.02 - lo[ax])
        c = c.copy()
        c[:, ax] += decal
        return c
    return c


def decouper(ob, boites):
    """Perce les baies : sections par les six plans de chaque boîte, puis faces intérieures supprimées.
    Robuste sur les revêtements ouverts (non manifold), où le booléen exact laisse des faces."""
    me = ob.data
    if not len(me.vertices):
        return 0
    mw = ob.matrix_world
    inv = mw.inverted()
    pts = np.array([mw @ v.co for v in me.vertices])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(mw)
    n = 0
    for b0, b1 in boites:
        b0, b1 = np.array(b0), np.array(b1)
        if np.any(hi < b0) or np.any(lo > b1):
            continue
        for k in range(3):
            for val in (b0[k], b1[k]):
                no = [0.0, 0.0, 0.0]
                no[k] = 1.0
                geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
                bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(float(val),) * 3, plane_no=no)
        sup = [f for f in bm.faces if np.all((np.array(f.calc_center_median()) > b0 + 1e-4) &
                                             (np.array(f.calc_center_median()) < b1 - 1e-4))]
        if sup:
            bmesh.ops.delete(bm, geom=sup, context="FACES")
            n += 1
    bm.transform(inv)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n


def traiter(nom):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = Path(os.environ.get("RECALER_SOURCE", ROOT / "export/composants"))
    bpy.ops.import_scene.gltf(filepath=str(source / (nom + ".glb")))
    bpy.context.view_layer.update()
    objets = list(bpy.context.scene.objects)
    monde = {o: o.matrix_world.copy() for o in objets}
    stats = {"composant": nom, "methode": "pièce par pièce (scripts/recaler_decors.py)", "objets": [], "sans_piece": [],
             "dans_une_porte": [], "decoupes": 0}
    for o in objets:
        o.parent = None
        o.matrix_world = monde[o]
    bpy.context.view_layer.update()
    cut, nb_portes = coupeurs()
    # dégagement devant les portes : 0,9 m de part et d'autre du nu
    passages = []
    for (b0, b1), k in zip(cut[:nb_portes], TRAVERSEE):
        b0, b1 = np.array(b0), np.array(b1)
        b0[k] -= 0.65
        b1[k] += 0.65
        passages.append((tuple(b0), tuple(b1), k))
    FENETRES = fenetres_bati()
    supprimes = []
    for o in list(objets):
        if SUPPRIMES.search(o.name):
            supprimes.append(o.name)
            objets.remove(o)
            bpy.data.objects.remove(o, do_unlink=True)
    stats["supprimes"] = supprimes
    for o in objets:
        m = monde[o]
        if o.type == "LIGHT":
            p = np.array([m.translation])
            pid = piece_de(o.name, p[0], p[0][2])
            if pid:
                o.matrix_world.translation = Vector(appliquer(p, pid)[0])
            continue
        if o.type != "MESH":
            continue
        me = o.data.copy()
        o.data = me
        loc = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", loc)
        loc = loc.reshape(-1, 3)
        if not len(loc):
            continue
        mat = np.array(m)
        pts = loc @ mat[:3, :3].T + mat[:3, 3]
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        pid = piece_de(o.name, (lo + hi) / 2, lo[2])
        if pid is None:
            stats["sans_piece"].append(o.name)
            continue
        couvrant = bool(COUVRANT.search(o.name.lower())) or bool(ECRAN.search(o.name))
        if not couvrant:
            # plus grand que la pièce nouvelle sur un axe (tapis du vestibule…) : étiré comme un revêtement
            xm, yb, yh = applications(pid)
            ym = yh if lo[2] >= 5.0 else yb
            if (hi[0] - lo[0]) > 0.9 * (xm[-1][1] - xm[0][1]) or (hi[1] - lo[1]) > 0.9 * (ym[-1][1] - ym[0][1]):
                couvrant = True
        cible = appliquer(pts, pid, o.name) if couvrant else rigide(pts, pid, o.name)
        if o.name in DEPLACER:
            cx, cy = DEPLACER[o.name]
            c = (cible.min(axis=0) + cible.max(axis=0)) / 2
            cible = cible + np.array([0.0 if cx is None else cx - c[0], cy - c[1], 0.0])
        if re.search(r"rideau|voilage", o.name):
            cible = caler_rideaux(cible, ilots(me), FENETRES)
            couvrant = True    # chaque rideau glisse à part : sommets écrits en monde
        if o.name in POSE:
            ang, (_, xmin), (_, yc) = POSE[o.name]
            c = (cible.min(axis=0) + cible.max(axis=0)) / 2
            a = np.radians(ang)
            rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
            cible = (cible - c) @ rz.T + c
            cible[:, 0] += xmin - cible[:, 0].min()
            cible[:, 1] += yc - (cible[:, 1].min() + cible[:, 1].max()) / 2
            couvrant = True    # sommets écrits en monde, comme un revêtement
        if not couvrant and o.name not in DEPLACER and not re.search(r"balustr|rideau|voilage|tringle|lustre|rosace", o.name):
            xm, yb, yh = applications(pid)
            ym = yh if lo[2] >= 5.0 else yb
            cible = cible + degager(cible, pid, passages, ((xm[0][1], xm[-1][1]), (ym[0][1], ym[-1][1])),
                                    bool(re.search(r"tableau|miroir|applique|gravure|cadre|plaque", o.name)))
        pivot = cible.mean(axis=0) if couvrant else (np.array(m.translation) + (cible[0] - pts[0]))
        o.matrix_world = Matrix.Translation(Vector(pivot)) @ Matrix(m.to_3x3()).to_4x4() if not couvrant \
            else Matrix.Translation(Vector(pivot))
        if couvrant:
            me.vertices.foreach_set("co", (cible - pivot).astype(np.float32).ravel())
        else:
            # rotation conservée : sommets locaux inchangés, seul le pivot se déplace
            pass
        me.update()
        if BALUSTRE.search(o.name):
            yc = (cible[:, 1].min() + cible[:, 1].max()) / 2
            if not (Y_ARCADE[0] <= yc <= Y_ARCADE[1]):
                stats["supprimes"].append(o.name)
                bpy.data.objects.remove(o, do_unlink=True)
                continue
        o["releve_20261119"] = ("revetement" if couvrant else "mobilier") + ":" + pid
        nlo, nhi = cible.min(axis=0), cible.max(axis=0)
        stats["objets"].append({"nom": o.name, "piece": pid, "mode": "revetement" if couvrant else "mobilier",
                                "min": nlo.round(3).tolist(), "max": nhi.round(3).tolist()})
        if not couvrant and not re.search(r"balustr|lustre|rosace", o.name):
            for b0, b1, _ in passages:
                c0, c1 = np.array(b0), np.array(b1)
                inter = np.minimum(nhi, c1) - np.maximum(nlo, c0)
                if np.all(inter > 0.08):
                    stats["dans_une_porte"].append(o.name)
                    break
    bpy.context.view_layer.update()
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        if COUVRANT.search(o.name.lower()) and not SOL_PLAFOND.search(o.name.lower()):
            stats["decoupes"] += decouper(o, cut)
        if o.name in ZONES:
            decouper(o, ZONES[o.name])
    bpy.ops.export_scene.gltf(filepath=str(OUT / (nom + ".glb")), export_format="GLB",
                              export_apply=True, export_yup=True, export_lights=True)
    try:
        bpy.ops.file.pack_all()
    except RuntimeError:
        pass
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / (nom + ".blend")), compress=True)
    (OUT / (nom + "-controle.json")).write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print("DECORS", nom, len(stats["objets"]), "découpes", stats["decoupes"], "sans pièce", len(stats["sans_piece"]),
          "dans une porte", stats["dans_une_porte"], flush=True)


if __name__ == "__main__":
    noms = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else \
        ["piece_circulations", "piece_salons", "piece_reception", "piece_chambres"]
    for nom in noms:
        if not re.fullmatch(r"[a-z_]+", nom):
            raise ValueError("Nom de composant invalide")
        traiter(nom)

# Composant « bati » (P2.facade-sud, P2.facade-nord, P2.facades-laterales) : murs extérieurs du château,
# du soubassement aux dessus de corniches. Appareil de pierre, chaînes d'angle à refends, bandeaux,
# corniches (modillons à l'attique), baies percées sur les axes du gabarit avec encadrements, frontons,
# menuiseries, vitrages, persiennes et garde-corps ; avant-corps sud (pans coupés, portique à 2 colonnes,
# balcon balustré, sol du balcon à z=5,35) ; avant-corps nord (porte d'entrée, pilastres, tables) ; soupiraux.
# blender -b --factory-startup --python scripts/composants/bati.py [-- --rapide]
# Sorties : export/composants/bati.glb, export/composants/bati.blend, rendus/bati*.png
# Repère D-003 : mètres, +X est, +Y sud, Z haut, RDC = 0. Cotes : travail/gabarit.json.

import bpy
import json
import math
import os
import sys
import time

import numpy as np
from mathutils import Matrix, Vector

T0 = time.time()
ID = "bati"
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
G = json.load(open(os.path.join(ROOT, "travail", "gabarit.json"), encoding="utf-8"))
NIV = G["niveaux"]
TRAV = G["travees"]
TEXDIR = os.path.join(ROOT, "assets", "generes", ID)
EXPDIR = os.path.join(ROOT, "export", "composants")
RENDIR = os.path.join(ROOT, "rendus")
for d in (TEXDIR, EXPDIR, RENDIR):
    os.makedirs(d, exist_ok=True)

RAPIDE = "--rapide" in sys.argv          # rendus basse définition pour itérer
SANS_RENDU = "--sans-rendu" in sys.argv
rng = np.random.default_rng(1868)

# ---------------------------------------------------------------- cotes
EP = 0.60                                             # épaisseur des murs extérieurs (nu → parement intérieur)
Z_BAS = -1.60                                         # pied des murs (enterré : cour nord -1,44, cour sud -1,28)
Z_RDC = NIV["rdc_sol"]["valeur"]                      # 0.0
Z_ETAGE = NIV["etage_sol"]["valeur"]                  # 5.35 (= sol du balcon, D-021)
Z_CORN_PAV = NIV["corniche_etage_pavillons"]["valeur"]  # 10.1 dessus de corniche d'étage
Z_CORN = NIV["corniche_attique"]["valeur"]            # 14.0 dessus de corniche d'attique
Z_TERRASSE = G["terrasse"]["niveau_z"]                # -0.05
Z_COUR_N = NIV["cour_nord_parking"]["valeur"]         # -1.44

X_CORPS, Y_CORPS = 10.8, 8.75
X_EXT, Y_BLOC, Y_PAV = 18.0, 3.85, 9.45
AC_N = (4.0, -12.45)
AC_S = (3.96, 9.35)

# baies : largeur, bas, haut du tableau (trou), genre
TYPES = {
    "pf_rdc": (1.45, 0.00, 3.70, "pf"),          # porte-fenêtre de plain-pied (terrasse)
    "f_rdc": (1.35, 0.45, 3.70, "fenetre"),      # fenêtre RDC au-dessus d'une cour basse (garde-corps)
    "f_bow": (1.50, 0.90, 3.30, "fenetre"),      # baie centrale de l'avant-corps sud
    "pf_pan": (1.10, 0.00, 3.30, "pf"),          # portes-fenêtres des pans coupés
    "porte": (1.70, 0.00, 4.10, "porte"),        # porte d'entrée nord (imposte comprise)
    "f_etage": (1.35, 5.50, 8.60, "fenetre"),    # fenêtre d'étage à garde-corps
    "f_etage_ac": (1.10, 5.50, 8.60, "fenetre"),  # fenêtres latérales de l'avant-corps sud
    "pf_balcon": (1.40, 5.35, 8.60, "pf"),       # porte-fenêtre sur le balcon
    "f_attique": (1.00, 10.95, 12.55, "fenetre"),
    "f_attique_bloc": (0.90, 11.75, 12.95, "fenetre"),  # faces des blocs au-dessus des toits de pavillons
    "soupirail": (0.90, -1.00, -0.55, "soupirail"),
}
ANNEAU_DU_TYPE = {"soupirail": "socle", "f_etage": "etage", "f_etage_ac": "etage", "pf_balcon": "etage",
                  "f_attique": "attique", "f_attique_bloc": "attique"}

# ---------------------------------------------------------------- scène vide
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
COL = bpy.data.collections.new(ID)
SC.collection.children.link(COL)
CTX = bpy.data.collections.new("contexte_rendu")
SC.collection.children.link(CTX)
RACINE = bpy.data.objects.new(ID, None)
COL.objects.link(RACINE)


def log(msg):
    print(f"[bati {time.time() - T0:6.1f}s] {msg}", flush=True)


# ================================================================ textures
def img_pixels(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[:, :, :3]


def save_img(name, arr, noncolor=False):
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), dtype=np.float32)], 2)
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(np.clip(arr, 0, 1).astype(np.float32).ravel())
    path = os.path.join(TEXDIR, name + ".jpg")
    img.filepath_raw = path               # écriture brute, sans transformation d'affichage
    img.file_format = "JPEG"
    img.save()
    bpy.data.images.remove(img)
    im = bpy.data.images.load(path)
    if noncolor:
        im.colorspace_settings.name = "Non-Color"
    return im


def vnoise(s, n, seed, octaves=3):
    """bruit de valeur raccordable (s × s), n cellules à la première octave."""
    r = np.random.default_rng(seed)
    out = np.zeros((s, s), np.float32)
    amp, tot = 1.0, 0.0
    for _ in range(octaves):
        g = r.random((n, n)).astype(np.float32)
        c = (np.arange(s) + 0.5) / s * n
        i0 = np.floor(c).astype(int)
        f = c - i0
        f = f * f * (3 - 2 * f)
        i0 %= n
        i1 = (i0 + 1) % n
        a = g[i0][:, i0] * (1 - f)[None, :] + g[i0][:, i1] * f[None, :]
        b = g[i1][:, i0] * (1 - f)[None, :] + g[i1][:, i1] * f[None, :]
        out += amp * (a * (1 - f)[:, None] + b * f[:, None])
        tot += amp
        amp *= 0.5
        n *= 2
    return out / tot


def blur(a, k=2):
    for _ in range(k):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5.0
    return a


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def normal_from_height(h, px, k=1.0):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * px) * k
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * px) * k
    n = np.stack([-gx, -gy, np.ones_like(h)], 2)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def appareil(S, assise, bloc, larg_joint, seed):
    """masque de joints d'un appareil réglé (tuile de 2 m), facteur de teinte par bloc."""
    c = (np.arange(S) + 0.5) / S * 2.0
    U, V = np.meshgrid(c, c)
    nc = int(round(2.0 / assise))
    course = np.floor(V / assise).astype(int) % nc
    off = (course % 2) * (bloc / 2)
    nb = int(round(2.0 / bloc))
    block = np.floor((U + off) / bloc).astype(int) % nb
    bt = np.random.default_rng(seed).uniform(0.97, 1.03, (nc, nb))
    fac = bt[course, block]
    ju = np.abs(((U + off) % bloc) - bloc / 2)
    jv = np.abs((V % assise) - assise / 2)
    jx = smoothstep(bloc / 2 - larg_joint, bloc / 2 - larg_joint * 0.35, ju)
    jy = smoothstep(assise / 2 - larg_joint, assise / 2 - larg_joint * 0.35, jv)
    return np.maximum(jx, jy).astype(np.float32), fac.astype(np.float32)


def textures():
    base = os.path.join(ROOT, "assets/polyhaven/polyhaven-beige_wall_001")
    d = img_pixels(os.path.join(base, "beige_wall_001_diff_2k.jpg"))
    n = img_pixels(os.path.join(base, "beige_wall_001_nor_gl_2k.jpg"))
    S = d.shape[0]
    lum = d.mean(2)
    lum = lum / lum.mean()
    tint = np.array([0.80, 0.75, 0.64], np.float32)        # même calcaire que toiture.py
    grime = vnoise(S, 5, 41, 4)
    spots = smoothstep(0.55, 0.85, vnoise(S, 20, 42, 3))
    alb = tint * (1.0 + 0.28 * (lum[:, :, None] - 1))
    alb *= (0.92 + 0.08 * grime)[:, :, None]
    alb *= (1 - 0.05 * spots)[:, :, None]
    nb = n * 2 - 1

    def avec_joints(alb0, joint, fac, prof, fonce):
        a = alb0 * fac[:, :, None] * (1 - fonce * joint[:, :, None])
        nj = normal_from_height(-prof * blur(joint, 2), 2.0 / S) * 2 - 1
        nn = np.stack([nb[:, :, 0] + nj[:, :, 0], nb[:, :, 1] + nj[:, :, 1], nb[:, :, 2]], 2)
        nn /= np.linalg.norm(nn, axis=2, keepdims=True)
        return a, nn * 0.5 + 0.5

    # pierre de taille des murs : assises de 0,40 m, blocs de 1,0 m, joints fins
    j, f = appareil(S, 0.40, 1.0, 0.0035, 43)
    a_app, n_app = avec_joints(alb, j, f, 0.004, 0.16)
    # soubassement : assises de 0,50 m à refends, teinte plus grise
    j2, f2 = appareil(S, 0.50, 1.0, 0.009, 44)
    a_sb, n_sb = avec_joints(alb * np.array([0.93, 0.93, 0.95], np.float32), j2, f2, 0.012, 0.35)
    rough = 0.80 + 0.10 * grime
    r3 = np.repeat(rough[:, :, None], 3, 2).astype(np.float32)
    out = {
        "lisse": save_img("bati_pierre_lisse_diff", alb[::2, ::2].astype(np.float32)),
        "lisse_n": save_img("bati_pierre_lisse_nor_gl", n[::2, ::2].astype(np.float32), True),
        "app": save_img("bati_pierre_appareil_diff", a_app.astype(np.float32)),
        "app_n": save_img("bati_pierre_appareil_nor_gl", n_app[::2, ::2].astype(np.float32), True),
        "sb": save_img("bati_soubassement_diff", a_sb[::2, ::2].astype(np.float32)),
        "sb_n": save_img("bati_soubassement_nor_gl", n_sb[::2, ::2].astype(np.float32), True),
        "rough": save_img("bati_pierre_rough", r3[::2, ::2], True),
    }
    # chêne foncé de la porte d'entrée
    o = img_pixels(os.path.join(ROOT, "assets/polyhaven/polyhaven-oak_wood_planks/oak_wood_planks_diff_1k.jpg"))
    lo = o.mean(2, keepdims=True)
    o = (o * 0.35 + lo * 0.15) * np.array([0.62, 0.40, 0.26], np.float32) * 1.15
    out["chene"] = save_img("bati_chene_fonce_diff", o.astype(np.float32))
    return out


log("textures…")
TX = textures()
TX_ENDUIT = bpy.data.images.load(os.path.join(
    ROOT, "assets/polyhaven/polyhaven-white_plaster_rough_01/white_plaster_rough_01_diff_1k.jpg"))
log("textures faites")


# ================================================================ matériaux
def principled(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, diff=None, nor=None, rgh=None,
        alpha=1.0, double=False, nor_force=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = principled(m)
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if diff is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = diff
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    if rgh is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = rgh
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs[1], b.inputs["Roughness"])
    if nor is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = nor
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = nor_force
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    m.use_backface_culling = not double
    m.diffuse_color = (*color, 1.0)
    return m


M = {
    "appareil": mat("bati_pierre_appareil", diff=TX["app"], nor=TX["app_n"], rgh=TX["rough"], rough=0.85),
    "lisse": mat("bati_pierre_moulures", diff=TX["lisse"], nor=TX["lisse_n"], rgh=TX["rough"], rough=0.85,
                 nor_force=0.5),
    "socle": mat("bati_pierre_soubassement", diff=TX["sb"], nor=TX["sb_n"], rgh=TX["rough"], rough=0.9),
    "enduit": mat("bati_enduit_interieur", diff=TX_ENDUIT, rough=0.9),
    "menuiserie": mat("bati_menuiserie_peinte", color=(0.86, 0.86, 0.83), rough=0.42),
    "persienne": mat("bati_persiennes", color=(0.83, 0.83, 0.80), rough=0.5),
    "fer": mat("bati_fer_forge", color=(0.025, 0.025, 0.027), rough=0.45, metal=0.6, double=True),
    "porte": mat("bati_bois_porte", diff=TX["chene"], rough=0.45),
    "vitrage": mat("bati_vitrage", color=(0.30, 0.36, 0.38), rough=0.04, alpha=0.22, double=True),
    "vitrage_op": mat("bati_vitrage_opaque", color=(0.10, 0.12, 0.13), rough=0.08, double=True),
    "sombre": mat("bati_fond_sombre", color=(0.02, 0.02, 0.02), rough=0.95),
    "inscription": mat("bati_inscription", color=(0.16, 0.14, 0.11), rough=0.7),
}


# ================================================================ géométrie de base (conventions de toiture.py)
class Acc:
    """accumule des faces (une seule matière) puis crée un maillage / un objet."""

    def __init__(self):
        self.v, self.f, self.uv, self.sm = [], [], [], []

    def add(self, verts, faces, uvs=None, smooth=False):
        o = len(self.v)
        self.v.extend([tuple(p) for p in verts])
        for i, fc in enumerate(faces):
            self.f.append([o + k for k in fc])
            self.uv.append(uvs[i] if uvs else None)
            self.sm.append(smooth[i] if isinstance(smooth, (list, tuple)) else smooth)

    def mesh(self, name, material, uvscale=1.0):
        if not self.f:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        uvl = me.uv_layers.new(name="UVMap")
        co = [Vector(p) for p in self.v]
        for poly in me.polygons:
            fu = self.uv[poly.index]
            if fu is not None:
                for j, li in enumerate(poly.loop_indices):
                    uvl.data[li].uv = fu[j]
            else:
                nx, ny, nz = (abs(c) for c in poly.normal)
                for li in poly.loop_indices:
                    p = co[me.loops[li].vertex_index]
                    if nz >= nx and nz >= ny:
                        uvl.data[li].uv = (p.x / uvscale, p.y / uvscale)
                    elif nx >= ny:
                        uvl.data[li].uv = (p.y / uvscale, p.z / uvscale)
                    else:
                        uvl.data[li].uv = (p.x / uvscale, p.z / uvscale)
        me.polygons.foreach_set("use_smooth", self.sm)
        me.materials.append(material)
        me.update()
        return me

    def build(self, name, material, coll=None, uvscale=1.0, parent=RACINE):
        me = self.mesh(name, material, uvscale)
        if me is None:
            return None
        ob = bpy.data.objects.new(name, me)
        (coll or COL).objects.link(ob)
        if parent is not None:
            ob.parent = parent
        return ob


def quad_or(acc, pts, want, smooth=False, uvs=None):
    """ajoute une face en l'orientant vers `want`."""
    p = [Vector(x) for x in pts]
    n = (p[1] - p[0]).cross(p[2] - p[1])
    if n.length < 1e-12:
        n = (p[2] - p[0]).cross(p[3 % len(p)] - p[0])
    if n.dot(Vector(want)) < 0:
        p = p[::-1]
        if uvs:
            uvs = uvs[::-1]
    acc.add(p, [list(range(len(p)))], [uvs] if uvs else None, smooth)


def sweep_rect(acc, cx, cy, hx, hy, prof, top=True, bottom=False, smooth=False):
    verts, faces = [], []
    for o, z in prof:
        a, b = hx + o, hy + o
        verts += [(cx - a, cy - b, z), (cx + a, cy - b, z), (cx + a, cy + b, z), (cx - a, cy + b, z)]
    for i in range(len(prof) - 1):
        for j in range(4):
            a0, b0 = 4 * i + j, 4 * i + (j + 1) % 4
            faces.append([a0, b0, b0 + 4, a0 + 4])
    k = 4 * (len(prof) - 1)
    if top:
        faces.append([k, k + 1, k + 2, k + 3])
    if bottom:
        faces.append([3, 2, 1, 0])
    acc.add(verts, faces, None, smooth)


def box(acc, x0, y0, z0, x1, y1, z1):
    sweep_rect(acc, (x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0) / 2, abs(y1 - y0) / 2,
               [(0, min(z0, z1)), (0, max(z0, z1))], True, True)


def boite(acc, O, ex, ey, ez, a0, a1, b0, b1, c0, c1):
    """boîte orientée : O + ex*[a0,a1] + ey*[b0,b1] + ez*[c0,c1] (repère direct)."""
    O, ex, ey, ez = Vector(O), Vector(ex), Vector(ey), Vector(ez)
    v = [O + ex * a + ey * b + ez * c for c in (c0, c1) for b in (b0, b1) for a in (a0, a1)]
    f = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]
    if ex.cross(ey).dot(ez) < 0:
        f = [fc[::-1] for fc in f]
    acc.add(v, f)


def poly_area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def ccw(poly):
    return list(poly) if poly_area(poly) > 0 else list(poly)[::-1]


def sweep_line(acc, P0, P1, sec, up=(0, 0, 1), caps=True, smooth=False):
    """profil fermé sec=[(lat, h)] extrudé de P0 à P1 ; lat vers la gauche de P0→P1 vue d'en haut."""
    P0, P1 = Vector(P0), Vector(P1)
    d = (P1 - P0).normalized()
    u = Vector(up)
    u = (u - d * u.dot(d)).normalized()
    n = u.cross(d)
    if poly_area(sec) < 0:
        sec = sec[::-1]
    m = len(sec)
    verts = [P0 + n * a + u * b for a, b in sec] + [P1 + n * a + u * b for a, b in sec]
    faces = [[k, (k + 1) % m, m + (k + 1) % m, m + k] for k in range(m)]
    if caps:
        faces.append(list(range(m))[::-1])
        faces.append(list(range(m, 2 * m)))
    acc.add(verts, faces, None, smooth)


def sweep_courbe(acc, pts, sec, cote=(0, 1, 0), caps=True):
    """profil fermé sec=[(a, b)] le long d'une courbe plane ; a selon `cote` (normale au plan), b
    perpendiculaire à la courbe dans son plan (vers l'extérieur de l'arc)."""
    pts = [Vector(p) for p in pts]
    s = Vector(cote).normalized()
    n = len(pts)
    if poly_area(sec) < 0:
        sec = sec[::-1]
    m = len(sec)
    verts = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        h = t.cross(s).normalized()
        verts += [p + s * a + h * b for a, b in sec]
    faces = []
    for i in range(n - 1):
        for k in range(m):
            faces.append([i * m + k, i * m + (k + 1) % m, (i + 1) * m + (k + 1) % m, (i + 1) * m + k])
    if caps:
        faces.append(list(range(m)))
        faces.append(list(range((n - 1) * m, n * m))[::-1])
    acc.add(verts, faces)


def lathe(acc, prof, seg=12, M=Matrix.Identity(4), cap_bot=True, cap_top=True, smooth=True):
    verts, faces, sm = [], [], []
    for r, z in prof:
        for j in range(seg):
            a = 2 * math.pi * j / seg
            verts.append(M @ Vector((r * math.cos(a), r * math.sin(a), z)))
    for i in range(len(prof) - 1):
        for j in range(seg):
            a0, b0 = i * seg + j, i * seg + (j + 1) % seg
            faces.append([a0, b0, b0 + seg, a0 + seg])
            sm.append(smooth)
    if cap_bot and prof[0][0] > 1e-6:
        faces.append(list(range(seg))[::-1])
        sm.append(False)
    if cap_top and prof[-1][0] > 1e-6:
        k = (len(prof) - 1) * seg
        faces.append(list(range(k, k + seg)))
        sm.append(False)
    acc.add(verts, faces, None, sm)


def tube(acc, pts, r, seg=8, caps=True, closed=False):
    pts = [Vector(p) for p in pts]
    n = len(pts)
    T = []
    for i in range(n):
        if closed:
            t = (pts[(i + 1) % n] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        elif i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        T.append(t.normalized())
    a = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    N = T[0].cross(a).normalized()
    verts = []
    for i, p in enumerate(pts):
        N = (N - T[i] * N.dot(T[i])).normalized()
        B = T[i].cross(N)
        for j in range(seg):
            ang = 2 * math.pi * j / seg
            verts.append(p + (N * math.cos(ang) + B * math.sin(ang)) * r)
    faces = []
    last = n if closed else n - 1
    for i in range(last):
        i2 = (i + 1) % n
        for j in range(seg):
            faces.append([i * seg + j, i * seg + (j + 1) % seg, i2 * seg + (j + 1) % seg, i2 * seg + j])
    sm = [True] * len(faces)
    if caps and not closed:
        faces.append(list(range(seg))[::-1])
        faces.append(list(range((n - 1) * seg, n * seg)))
        sm += [False, False]
    acc.add(verts, faces, None, sm)


def plate_xz(acc, poly, y0, y1):
    """polygone (x, z) extrudé de y0 à y1 (repère local d'une baie)."""
    if poly_area(poly) < 0:
        poly = poly[::-1]
    m = len(poly)
    v = [(x, y0, z) for x, z in poly] + [(x, y1, z) for x, z in poly]
    f = [list(range(m)), list(range(m, 2 * m))[::-1]]
    f += [[k, m + k, m + (k + 1) % m, (k + 1) % m] for k in range(m)]
    acc.add(v, f)


def plate_yz(acc, poly, x0, x1):
    """polygone (y, z) extrudé de x0 à x1."""
    if poly_area(poly) < 0:
        poly = poly[::-1]
    m = len(poly)
    v = [(x0, y, z) for y, z in poly] + [(x1, y, z) for y, z in poly]
    f = [list(range(m))[::-1], list(range(m, 2 * m))]
    f += [[k, (k + 1) % m, m + (k + 1) % m, m + k] for k in range(m)]
    acc.add(v, f)


def prism(acc, poly, z0, z1):
    if poly_area(poly) < 0:
        poly = poly[::-1]
    m = len(poly)
    v = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    f = [list(range(m))[::-1], list(range(m, 2 * m))]
    f += [[k, (k + 1) % m, m + (k + 1) % m, m + k] for k in range(m)]
    acc.add(v, f)


def offset_poly(poly, d):
    """décalage vers l'intérieur d'un polygone anti-horaire (onglets) ; d < 0 : vers l'extérieur."""
    n = len(poly)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector((*poly[i - 1], 0)), Vector((*poly[i], 0)), Vector((*poly[(i + 1) % n], 0))
        e0, e1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n0, n1 = Vector((-e0.y, e0.x, 0)), Vector((-e1.y, e1.x, 0))
        m = (n0 + n1) / (1 + n0.dot(n1))
        q = p1 + m * d
        out.append((q.x, q.y))
    return out


def sweep_poly(acc, poly, prof):
    """moulure tournant autour d'un polygone anti-horaire ; prof = [(saillie, z)] (saillie > 0 vers l'extérieur)."""
    rings = [offset_poly(poly, -o) for o, z in prof]
    m = len(poly)
    for k in range(len(prof) - 1):
        r0, r1, z0, z1 = rings[k], rings[k + 1], prof[k][1], prof[k + 1][1]
        for i in range(m):
            j = (i + 1) % m
            acc.add([(*r0[i], z0), (*r0[j], z0), (*r1[j], z1), (*r1[i], z1)], [[0, 1, 2, 3]])


def inter_lignes(p, d, q, e):
    """intersection des droites p + t d et q + s e (2D)."""
    den = d[0] * e[1] - d[1] * e[0]
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * t, p[1] + d[1] * t)


def decaler_ligne(pts, o, coupe0=None, coupe1=None):
    """polyligne ouverte décalée de o vers sa droite (extérieur) ; extrémités recoupées sur des droites."""
    P = [Vector((*p, 0)) for p in pts]
    n = len(P)
    out = []
    for i in range(n):
        if i == 0 or i == n - 1:
            e = (P[1] - P[0]) if i == 0 else (P[-1] - P[-2])
            e.normalize()
            r = Vector((e.y, -e.x, 0))
            q = P[i] + r * o
            coupe = coupe0 if i == 0 else coupe1
            if coupe is not None:
                q = Vector((*inter_lignes((q.x, q.y), (e.x, e.y), coupe[0], coupe[1]), 0))
        else:
            e0, e1 = (P[i] - P[i - 1]).normalized(), (P[i + 1] - P[i]).normalized()
            r0, r1 = Vector((e0.y, -e0.x, 0)), Vector((e1.y, -e1.x, 0))
            q = P[i] + (r0 + r1) / (1 + r0.dot(r1)) * o
        out.append((q.x, q.y))
    return out


def sweep_ouvert(acc, pts, prof, coupe0=None, coupe1=None, ferme=False):
    """moulure le long d'une polyligne ouverte (extérieur à droite) ; prof = [(saillie, z)]."""
    rings = [decaler_ligne(pts, o, coupe0, coupe1) for o, z in prof]
    m = len(pts)
    K = len(prof)
    for k in range(K if ferme else K - 1):
        k2 = (k + 1) % K
        r0, r1, z0, z1 = rings[k], rings[k2], prof[k][1], prof[k2][1]
        for i in range(m - 1):
            acc.add([(*r0[i], z0), (*r0[i + 1], z0), (*r1[i + 1], z1), (*r1[i], z1)], [[0, 1, 2, 3]])
    return rings


# ================================================================ instances
OBJETS = {"instances": 0}


def poser(me, nom, Mw):
    if me is None:
        return None
    ob = bpy.data.objects.new(nom, me)
    COL.objects.link(ob)
    ob.parent = RACINE
    ob.matrix_world = Mw
    OBJETS["instances"] += 1
    return ob


PROTOS = {}


def proto(cle, fabrique):
    """maillages partagés : fabrique() → {suffixe: (Acc, matière)} ; renvoie {suffixe: mesh}."""
    if cle not in PROTOS:
        res = {}
        for suf, (acc, m) in fabrique().items():
            res[suf] = acc.mesh("bati_proto_" + "_".join(str(c) for c in cle) + "_" + suf, m, 1.0)
        PROTOS[cle] = res
    return PROTOS[cle]


def repere(P2, d2, z):
    """repère d'une baie : x le long du mur (n × z), y = normale extérieure, z vertical."""
    nrm = Vector((d2[1], -d2[0], 0))
    x = nrm.cross(Vector((0, 0, 1)))
    Mw = Matrix.Identity(4)
    for i in range(3):
        Mw[i][0], Mw[i][1], Mw[i][2] = x[i], nrm[i], (0, 0, 1)[i]
    Mw[0][3], Mw[1][3], Mw[2][3] = P2[0], P2[1], z
    return Mw


# ================================================================ polygones des niveaux
EMPRISE = [tuple(p) for p in G["emprise"]["polygone"]]
A1 = ccw(EMPRISE)                                               # RDC (avec pans coupés)
A2 = ccw([p for p in EMPRISE if not (abs(p[0]) < 3.5 and p[1] > 9.0)])   # étage : avant-corps sud plan
ATT = ccw([(-X_CORPS, -Y_CORPS), (-AC_N[0], -Y_CORPS), (-AC_N[0], AC_N[1]), (AC_N[0], AC_N[1]),
           (AC_N[0], -Y_CORPS), (X_CORPS, -Y_CORPS), (X_CORPS, -Y_BLOC), (X_EXT, -Y_BLOC), (X_EXT, Y_BLOC),
           (X_CORPS, Y_BLOC), (X_CORPS, Y_CORPS), (AC_S[0], Y_CORPS), (AC_S[0], AC_S[1]), (-AC_S[0], AC_S[1]),
           (-AC_S[0], Y_CORPS), (-X_CORPS, Y_CORPS), (-X_CORPS, Y_BLOC), (-X_EXT, Y_BLOC), (-X_EXT, -Y_BLOC),
           (-X_CORPS, -Y_BLOC)])   # même polygone d'attique que toiture.py
BOW = [p for p in A1 if abs(p[0]) < 3.5 and p[1] > 9.0]         # (3,1 ; 9,35) → (2,3 ; 11,25) → … (est → ouest)
assert len(BOW) == 4 and BOW[0][0] > 0, BOW
COUPE_BOW = ((0.0, AC_S[1]), (1.0, 0.0))                       # nu de l'avant-corps à l'étage (y = 9,35)

ANNEAUX = [  # nom, nu extérieur, parement intérieur, z0, z1, matière
    ("socle", offset_poly(A1, -0.06), offset_poly(A1, EP), Z_BAS, Z_RDC, "socle"),
    ("rdc", A1, offset_poly(A1, EP), Z_RDC, Z_ETAGE, "appareil"),
    ("etage", A2, offset_poly(A2, EP), Z_ETAGE, Z_CORN_PAV, "appareil"),
    ("attique", ATT, offset_poly(ATT, EP), Z_CORN_PAV, Z_CORN, "appareil"),
]


# ================================================================ ordonnance des baies
def ouv(face, pos, typ, deco, gc=False, pers=False):
    return dict(face=face, pos=pos, type=typ, deco=deco, gc=gc, pers=pers,
                anneau=ANNEAU_DU_TYPE.get(typ, "rdc"))


OUV = []
# façade sud (W01, W15) : pavillon | aile 2 | avant-corps 3 | aile 2 | pavillon
axS = TRAV["sud"]["axes_x"]
for x in axS:
    ax = abs(x)
    if ax > 12:       # pavillons : fronton triangulaire au RDC, cintré à l'étage
        OUV.append(ouv("S", x, "pf_rdc", "triangle"))
        OUV.append(ouv("S", x, "f_etage", "cintre", gc=True))
    elif ax > 4:      # ailes
        OUV.append(ouv("S", x, "pf_rdc", "corniche"))
        OUV.append(ouv("S", x, "f_etage", "corniche", gc=True))
    elif ax > 1:      # avant-corps : pans coupés au RDC
        OUV.append(ouv("PAN", x, "pf_pan", "cintre"))
        OUV.append(ouv("S", x, "f_etage_ac", "corniche", gc=True))
    else:
        OUV.append(ouv("S", x, "f_bow", "cintre"))
        OUV.append(ouv("S", x, "pf_balcon", "cintre"))
for x in TRAV["sud"]["axes_attique_x"]:
    OUV.append(ouv("S", x, "f_attique", "cintre" if abs(x) < 1 else "corniche"))
# façade nord (W11, P38, P39) : pavillon | aile 2 | avant-corps (porte) | aile 2 | pavillon
for x in TRAV["nord"]["axes_x"]:
    ax = abs(x)
    if ax < 1:
        OUV.append(ouv("N", x, "porte", "simple"))
        OUV.append(ouv("N", x, "f_etage", "cintre", gc=True))
        OUV.append(ouv("N", x, "f_attique", "corniche"))
    else:
        pav = ax > 12
        OUV.append(ouv("N", x, "f_rdc", "corniche", gc=True, pers=pav))
        OUV.append(ouv("N", x, "f_etage", "corniche", gc=True, pers=pav))
        OUV.append(ouv("N", x, "soupirail", "aucun"))
        if not pav:
            OUV.append(ouv("N", x, "f_attique", "corniche"))
# faces latérales de l'avant-corps nord (plan D-019, rideaux P20/W08) : une baie par niveau
YL_AC_N = (AC_N[1] - 8.75) / 2
for face in ("E", "O"):
    OUV.append(ouv(face, YL_AC_N, "f_rdc", "corniche", gc=True))
    OUV.append(ouv(face, YL_AC_N, "f_etage", "corniche", gc=True))
# faces des blocs d'extrémité au-dessus des toits de pavillons (W15, W11)
for x in (-14.4, 14.4):
    OUV.append(ouv("S", x, "f_attique_bloc", "corniche"))
    OUV.append(ouv("N", x, "f_attique_bloc", "corniche"))
# façades latérales (W17 ; ouest par symétrie) : pavillon | bloc 2 | pavillon, persiennes
for face in ("E", "O"):
    for y in TRAV["est"]["axes_y"]:
        pav = abs(y) > 5
        terrasse = (y > -1.8) if face == "E" else (y > 6.45)    # plain-pied sur la terrasse (gabarit)
        OUV.append(ouv(face, y, "pf_rdc" if terrasse else "f_rdc", "triangle" if pav else "corniche",
                       gc=not terrasse, pers=True))
        OUV.append(ouv(face, y, "f_etage", "cintre" if pav else "corniche", gc=True, pers=True))
        if not pav:
            OUV.append(ouv(face, y, "f_attique", "corniche"))


def classer(P, Q):
    d = Vector((Q[0] - P[0], Q[1] - P[1], 0))
    L = d.length
    d /= L
    n = (d.y, -d.x)
    if n[1] > 0.99:
        f = "S"
    elif n[1] < -0.99:
        f = "N"
    elif n[0] > 0.99:
        f = "E"
    elif n[0] < -0.99:
        f = "O"
    else:
        f = "PAN"
    return f, d, L


def position(o, face, P, Q, d, L):
    if o["face"] == "PAN":
        if face != "PAN":
            return None
        mx, my = (P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2
        return L / 2 if (my > 9.0 and mx * o["pos"] > 0) else None
    if face != o["face"]:
        return None
    k = 0 if face in ("S", "N") else 1
    lo, hi = sorted((P[k], Q[k]))
    if not (lo + 0.5 < o["pos"] < hi - 0.5):
        return None
    pt = (o["pos"], P[1]) if k == 0 else (P[0], o["pos"])
    return (pt[0] - P[0]) * d.x + (pt[1] - P[1]) * d.y


# ================================================================ murs à vrais trous
def mur(acc_e, acc_i, P, Q, Pi, Qi, z0, z1, trous):
    P3, Q3 = Vector((*P, 0)), Vector((*Q, 0))
    L = (Q3 - P3).length
    d = (Q3 - P3) / L
    n = Vector((d.y, -d.x, 0))
    Pi3, Qi3 = Vector((*Pi, 0)), Vector((*Qi, 0))
    e = (P3 - Pi3).dot(n)
    Z = Vector((0, 0, 1))
    us = sorted(set([0.0, L] + [round(t[0], 5) for t in trous] + [round(t[1], 5) for t in trous]))
    zs = sorted(set([z0, z1] + [t[2] for t in trous] + [t[3] for t in trous]))

    def ext(u, z):
        return P3 + d * u + Z * z

    def inn(u, z):
        if u <= 1e-6:
            b = Pi3
        elif u >= L - 1e-6:
            b = Qi3
        else:
            b = P3 + d * u - n * e
        return b + Z * z

    for i in range(len(us) - 1):
        for j in range(len(zs) - 1):
            uc, zc = (us[i] + us[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            if any(t[0] < uc < t[1] and t[2] < zc < t[3] for t in trous):
                continue
            a, b, c, dd = (us[i], zs[j]), (us[i + 1], zs[j]), (us[i + 1], zs[j + 1]), (us[i], zs[j + 1])
            quad_or(acc_e, [ext(*a), ext(*b), ext(*c), ext(*dd)], n)
            quad_or(acc_i, [inn(*a), inn(*b), inn(*c), inn(*dd)], -n)
    for u0, u1, za, zb in trous:      # tableaux, linteau, appui
        quad_or(acc_e, [ext(u0, za), inn(u0, za), inn(u0, zb), ext(u0, zb)], d)
        quad_or(acc_e, [ext(u1, za), inn(u1, za), inn(u1, zb), ext(u1, zb)], -d)
        quad_or(acc_e, [ext(u0, zb), ext(u1, zb), inn(u1, zb), inn(u0, zb)], -Z)
        quad_or(acc_e, [ext(u0, za), ext(u1, za), inn(u1, za), inn(u0, za)], Z)


POSES = []   # (ouverture, origine 2D sur le nu, direction du mur, u)
for nom, ext_, int_, z0, z1, mt in ANNEAUX:
    acc_e, acc_i = Acc(), Acc()
    n = len(ext_)
    for i in range(n):
        P, Q = ext_[i], ext_[(i + 1) % n]
        face, d, L = classer(P, Q)
        trous = []
        for o in OUV:
            if o["anneau"] != nom:
                continue
            u = position(o, face, P, Q, d, L)
            if u is None:
                continue
            w, za, zb, _ = TYPES[o["type"]]
            trous.append((u - w / 2, u + w / 2, za, zb))
            POSES.append((o, (P[0] + d.x * u, P[1] + d.y * u), (d.x, d.y)))
        mur(acc_e, acc_i, P, Q, int_[i], int_[(i + 1) % n], z0, z1, trous)
    acc_e.build("bati_murs_" + nom, M[mt], uvscale=2.0)
    acc_i.build("bati_murs_" + nom + "_parement_interieur", M["enduit"], uvscale=2.0)
manque = [o for o in OUV if not any(p[0] is o for p in POSES)]
assert not manque, manque
log(f"murs : {len(POSES)} baies percées")


# ================================================================ moulures courantes
acc_m = Acc()     # pierre lisse : bandeaux, corniches, chaînes, encadrements non instanciés

# bandeau RDC/étage (dessus au niveau du sol d'étage et du balcon)
sweep_poly(acc_m, A2, [(-0.05, 5.00), (0.06, 5.00), (0.10, 5.04), (0.10, 5.28), (0.13, 5.31), (0.13, Z_ETAGE),
                       (-0.30, Z_ETAGE)])
# corniche d'étage (pavillons, et continue sous l'attique) : dessus z = 10,1
sweep_poly(acc_m, A2, [(-0.05, 9.25), (0.05, 9.25), (0.05, 9.48), (0.07, 9.50), (0.07, 9.55), (0.0, 9.57),
                       (0.0, 9.78), (0.06, 9.80), (0.10, 9.84), (0.12, 9.84), (0.12, 9.95), (0.50, 9.97),
                       (0.50, 10.04), (0.55, 10.07), (0.57, Z_CORN_PAV), (-0.62, Z_CORN_PAV)])
# bandeau d'appui de l'attique
sweep_poly(acc_m, ATT, [(-0.05, 10.72), (0.06, 10.72), (0.09, 10.77), (0.09, 10.91), (0.11, 10.95),
                        (-0.30, 10.95)])
# corniche d'attique à modillons : dessus z = 14,0 (balustrade de toiture.py posée dessus)
SOFFITE = 13.66
sweep_poly(acc_m, ATT, [(-0.05, 13.00), (0.05, 13.00), (0.05, 13.22), (0.07, 13.24), (0.07, 13.28),
                        (0.0, 13.30), (0.0, 13.52), (0.06, 13.55), (0.10, 13.59), (0.14, 13.62), (0.14, SOFFITE),
                        (0.78, SOFFITE + 0.02), (0.78, 13.84), (0.83, 13.88), (0.86, 13.94), (0.88, Z_CORN),
                        (-0.62, Z_CORN)])

# modillons et denticules
acc_mod = Acc()


def modillon(acc, O, dx, nrm):
    """console en S sous le larmier ; O sur le nu au niveau du soffite."""
    prof = [(0.0, 0.0), (0.62, 0.0), (0.62, -0.06), (0.55, -0.09), (0.42, -0.10), (0.30, -0.13),
            (0.22, -0.20), (0.12, -0.25), (0.0, -0.27)]
    w = 0.085
    v = []
    for s in (-w, w):
        v += [Vector(O) + dx * s + nrm * a + Vector((0, 0, b)) for a, b in prof]
    m = len(prof)
    f = [list(range(m))[::-1], list(range(m, 2 * m))]
    f += [[k, (k + 1) % m, m + (k + 1) % m, m + k] for k in range(m)]
    if dx.cross(nrm).z < 0:
        f = [fc[::-1] for fc in f]
    acc.add(v, f)


def le_long(poly, marge, pas, fn):
    m = len(poly)
    for i in range(m):
        P, Q = Vector((*poly[i], 0)), Vector((*poly[(i + 1) % m], 0))
        L = (Q - P).length
        if L < 2 * marge + 0.05:
            continue
        d = (Q - P) / L
        nrm = Vector((d.y, -d.x, 0))
        k = int((L - 2 * marge) / pas) + 1
        for j in range(k):
            u = marge + (L - 2 * marge) * (j / (k - 1) if k > 1 else 0.5)
            fn(P + d * u, d, nrm)


le_long(ATT, 0.40, 0.66, lambda p, d, nrm: modillon(acc_mod, p + nrm * 0.14 + Vector((0, 0, SOFFITE)), d, nrm))
le_long(A2, 0.18, 0.20, lambda p, d, nrm: boite(acc_mod, p + Vector((0, 0, 9.87)), d, nrm, (0, 0, 1),
                                                 -0.05, 0.05, 0.12, 0.21, 0.0, 0.08))
acc_mod.build("bati_modillons_denticules", M["lisse"], uvscale=1.0)


# chaînes d'angle à refends (angles saillants)
def chaines(poly, z0, z1, larg_fn, assise=0.45, refend=0.035, saillie=0.05):
    m = len(poly)
    for i in range(m):
        A, C, B = Vector((*poly[i - 1], 0)), Vector((*poly[i], 0)), Vector((*poly[(i + 1) % m], 0))
        d1, d2 = (C - A).normalized(), (B - C).normalized()
        if d1.cross(d2).z < 0.9:          # seulement les angles saillants droits
            continue
        n1, n2 = Vector((d1.y, -d1.x, 0)), Vector((d2.y, -d2.x, 0))
        w = larg_fn(C)
        w1, w2 = min(w, (C - A).length), min(w, (B - C).length)
        z = z0
        while z < z1 - 0.1:
            zt = min(z + assise - refend, z1)
            boite(acc_m, C, d1, n1, (0, 0, 1), -w1, saillie, -0.02, saillie, z, zt)
            boite(acc_m, C, d2, n2, (0, 0, 1), 0.0, w2, -0.02, saillie, z, zt)
            z += assise


def larg_chaine(C):
    if abs(C.x) < 4.5 and C.y > 0:
        return 0.45         # avant-corps sud : baies latérales serrées
    return 0.80


chaines(A2, Z_RDC, 9.25, larg_chaine)
chaines(ATT, 10.95, 13.0, lambda C: 0.45 if (abs(C.x) < 4.5 and C.y > 0) else 0.60)
log("moulures, corniches, chaînes")


# ================================================================ encadrements, frontons, menuiseries
CH, CHS = 0.18, 0.05           # chambranle : largeur, saillie
SEC_CORN = [(-0.02, 0.0), (0.07, 0.0), (0.07, 0.04), (0.11, 0.07), (0.16, 0.10), (0.19, 0.11), (0.19, 0.18),
            (-0.02, 0.18)]
SEC_RAMP = [(-0.02, 0.0), (0.10, 0.0), (0.13, 0.04), (0.15, 0.06), (0.15, 0.13), (-0.02, 0.13)]


def console(acc, xc, z0, haut=0.36, prof=0.15, larg=0.12):
    poly = [(0.0, z0), (0.0, z0 + haut), (prof, z0 + haut), (prof, z0 + haut - 0.06), (prof * 0.55, z0 + haut * 0.55),
            (prof * 0.45, z0 + 0.12), (prof * 0.3, z0)]
    plate_yz(acc, poly, xc - larg / 2, xc + larg / 2)


def fab_encadrement(w, h, deco, appui, ext=0.12):
    def f():
        a = Acc()
        zt = h + CH
        if deco != "aucun":
            box(a, -w / 2 - CH, -0.02, 0.0, -w / 2, CHS, zt)
            box(a, w / 2, -0.02, 0.0, w / 2 + CH, CHS, zt)
            box(a, -w / 2, -0.02, h, w / 2, CHS, zt)
        else:
            box(a, -w / 2 - 0.12, -0.02, -0.12, -w / 2, 0.04, h + 0.12)
            box(a, w / 2, -0.02, -0.12, w / 2 + 0.12, 0.04, h + 0.12)
            box(a, -w / 2, -0.02, h, w / 2, 0.04, h + 0.12)
            box(a, -w / 2, -0.02, -0.12, w / 2, 0.04, 0.0)
        if appui:
            box(a, -w / 2 - CH - 0.08, -0.03, -0.11, w / 2 + CH + 0.08, 0.10, 0.0)
            box(a, -w / 2 - CH - 0.04, -0.02, -0.16, w / 2 + CH + 0.04, 0.07, -0.11)
        W = w / 2 + CH + ext
        if deco == "corniche":
            box(a, -w / 2 - CH, -0.02, zt, w / 2 + CH, 0.03, zt + 0.20)          # frise
            sweep_line(a, (-W, 0, zt + 0.20), (W, 0, zt + 0.20), [(b, c) for b, c in SEC_CORN])
        elif deco in ("triangle", "cintre"):
            zb = zt + 0.04
            box(a, -w / 2 - CH, -0.02, zt, w / 2 + CH, 0.03, zb)
            console(a, -w / 2 - CH / 2, zt - 0.30, 0.34)
            console(a, w / 2 + CH / 2, zt - 0.30, 0.34)
            sweep_line(a, (-W, 0, zb), (W, 0, zb), SEC_CORN)
            zr = zb + 0.18
            if deco == "triangle":
                fl = W * 0.42
                plate_xz(a, [(-W + 0.1, zr), (W - 0.1, zr), (0.0, zr + fl - 0.06)], -0.02, 0.04)
                sweep_line(a, (-W, 0, zr), (0.0, 0, zr + fl), SEC_RAMP, caps=True)
                sweep_line(a, (0.0, 0, zr + fl), (W, 0, zr), SEC_RAMP, caps=True)
            else:
                fl = W * 0.30
                R = (W * W + fl * fl) / (2 * fl)
                zc = zr + fl - R
                a0 = math.asin(W / R)
                arc = [(R * math.sin(t), zc + R * math.cos(t)) for t in np.linspace(-a0, a0, 15)]
                plate_xz(a, [(x, z) for x, z in arc[1:-1]] + [(arc[-2][0], zr), (arc[1][0], zr)], -0.02, 0.04)
                sweep_courbe(a, [(x, 0.0, z) for x, z in arc], [(b, c) for b, c in SEC_RAMP])
        return {"pierre": (a, M["lisse"])}
    return f


def fab_menuiserie(w, h, genre, opaque=False):
    def f():
        a, v = Acc(), Acc()
        y0 = -0.25                    # face extérieure du dormant (feuillure)
        fd = 0.065
        box(a, -w / 2, y0 - 0.07, 0, -w / 2 + fd, y0, h)
        box(a, w / 2 - fd, y0 - 0.07, 0, w / 2, y0, h)
        box(a, -w / 2 + fd, y0 - 0.07, h - fd, w / 2 - fd, y0, h)
        box(a, -w / 2 + fd, y0 - 0.07, 0, w / 2 - fd, y0 + 0.01, fd)
        zt = h - fd
        if h > 2.6:                   # imposte vitrée fixe
            zt = h - 0.62
            box(a, -w / 2 + fd, y0 - 0.07, zt - 0.03, w / 2 - fd, y0 - 0.005, zt + 0.04)
            gx = (w / 2 - fd)
            box(a, -0.015, y0 - 0.05, zt + 0.04, 0.015, y0 - 0.02, h - fd)
            quad_or(v, [(-gx, y0 - 0.035, zt + 0.04), (gx, y0 - 0.035, zt + 0.04), (gx, y0 - 0.035, h - fd),
                        (-gx, y0 - 0.035, h - fd)], (0, 1, 0))
            zt -= 0.03
        fo = 0.06
        xi = w / 2 - fd
        for s in (-1, 1):             # deux vantaux
            x0, x1 = sorted((s * 0.0, s * xi))
            box(a, x0, y0 - 0.06, fd, x0 + fo, y0 - 0.008, zt)
            box(a, x1 - fo, y0 - 0.06, fd, x1, y0 - 0.008, zt)
            zb = fd + (0.42 if genre == "pf" else 0.0)
            box(a, x0 + fo, y0 - 0.06, fd, x1 - fo, y0 - 0.008, zb + 0.09)
            if genre == "pf":
                box(a, x0 + fo + 0.05, y0 - 0.005, fd + 0.08, x1 - fo - 0.05, y0 + 0.002, zb - 0.02)
            box(a, x0 + fo, y0 - 0.06, zt - 0.07, x1 - fo, y0 - 0.008, zt)
            g0, g1 = zb + 0.09, zt - 0.07
            nr = max(2, int(round((g1 - g0) / 0.58)))
            for k in range(1, nr):
                zz = g0 + (g1 - g0) * k / nr
                box(a, x0 + fo, y0 - 0.048, zz - 0.012, x1 - fo, y0 - 0.02, zz + 0.012)
            quad_or(v, [(x0 + fo, y0 - 0.034, g0), (x1 - fo, y0 - 0.034, g0), (x1 - fo, y0 - 0.034, g1),
                        (x0 + fo, y0 - 0.034, g1)], (0, 1, 0))
        # espagnolette
        box(a, -0.012, y0 + 0.0, fd + 0.3, 0.012, y0 + 0.012, zt - 0.2)
        return {"menuiserie": (a, M["menuiserie"]), "vitrage": (v, M["vitrage_op" if opaque else "vitrage"])}
    return f


def fab_porte(w, h):
    """porte d'entrée nord (P38) : deux vantaux de chêne à panneaux, grilles ovales, imposte en fer forgé."""
    def f():
        b, fe, v = Acc(), Acc(), Acc()
        y0 = -0.30
        fd = 0.09
        box(b, -w / 2, y0 - 0.10, 0, -w / 2 + fd, y0, h)
        box(b, w / 2 - fd, y0 - 0.10, 0, w / 2, y0, h)
        box(b, -w / 2 + fd, y0 - 0.10, h - fd, w / 2 - fd, y0, h)
        zi = h - 0.75
        box(b, -w / 2 + fd, y0 - 0.10, zi - 0.06, w / 2 - fd, y0 + 0.02, zi + 0.04)
        xi = w / 2 - fd
        quad_or(v, [(-xi, y0 - 0.06, zi + 0.04), (xi, y0 - 0.06, zi + 0.04), (xi, y0 - 0.06, h - fd),
                    (-xi, y0 - 0.06, h - fd)], (0, 1, 0))
        # imposte : barreaux rayonnants et arcs
        cz = zi + 0.04
        for k in range(9):
            t = math.pi * (k + 0.5) / 9
            tube(fe, [(0.0, y0 - 0.03, cz), (math.cos(t) * xi * 0.98, y0 - 0.03,
                                             min(cz + math.sin(t) * 2.0, h - fd))], 0.008, 5)
        tube(fe, [(-xi, y0 - 0.03, cz + 0.32), (xi, y0 - 0.03, cz + 0.32)], 0.01, 5)
        for r in (0.18, 0.4):
            tube(fe, [(r * math.cos(t), y0 - 0.03, cz + r * math.sin(t) * 0.9)
                      for t in np.linspace(0, math.pi, 13)], 0.009, 5, caps=True)
        for s in (-1, 1):
            x0, x1 = sorted((0.0, s * xi))
            box(b, x0, y0 - 0.09, 0.0, x1, y0 - 0.04, zi - 0.06)         # âme du vantail
            for z0_, z1_ in ((0.18, 0.95), (1.15, 1.45)):
                box(b, x0 + 0.12, y0 - 0.04, z0_, x1 - 0.12, y0 - 0.005, z1_)
                box(b, x0 + 0.17, y0 - 0.005, z0_ + 0.05, x1 - 0.17, y0 + 0.012, z1_ - 0.05)
            # panneau haut vitré derrière une grille ovale
            g0, g1 = 1.65, zi - 0.25
            box(b, x0, y0 - 0.04, 1.55, x0 + 0.11, y0 - 0.005, zi - 0.06)
            box(b, x1 - 0.11, y0 - 0.04, 1.55, x1, y0 - 0.005, zi - 0.06)
            box(b, x0, y0 - 0.04, 1.45, x1, y0 - 0.005, 1.65)
            box(b, x0, y0 - 0.04, g1, x1, y0 - 0.005, zi - 0.06)
            quad_or(v, [(x0 + 0.11, y0 - 0.06, g0), (x1 - 0.11, y0 - 0.06, g0), (x1 - 0.11, y0 - 0.06, g1),
                        (x0 + 0.11, y0 - 0.06, g1)], (0, 1, 0))
            cx, cz2 = (x0 + x1) / 2, (g0 + g1) / 2
            rx, rz = (x1 - x0) / 2 - 0.16, (g1 - g0) / 2 - 0.06
            tube(fe, [(cx + rx * math.cos(t), y0 - 0.02, cz2 + rz * math.sin(t))
                      for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)], 0.012, 5, closed=True)
            for k in range(-2, 3):
                xx = cx + k * rx * 0.38
                hz = rz * math.sqrt(max(0.0, 1 - (k * 0.38) ** 2))
                tube(fe, [(xx, y0 - 0.02, cz2 - hz), (xx, y0 - 0.02, cz2 + hz)], 0.007, 4)
            box(fe, s * 0.07 - 0.012, y0 + 0.0, 1.05, s * 0.07 + 0.012, y0 + 0.04, 1.25)   # poignée
        return {"bois": (b, M["porte"]), "fer": (fe, M["fer"]), "vitrage": (v, M["vitrage"])}
    return f


def fab_garde_corps(w, haut=0.92):
    """balconnet en fer forgé dans le tableau, au nu du mur (P39, W15)."""
    def f():
        a = Acc()
        y = -0.05
        x0, x1 = -w / 2, w / 2
        box(a, x0, y - 0.02, haut - 0.04, x1, y + 0.02, haut)          # main courante
        box(a, x0, y - 0.012, 0.03, x1, y + 0.012, 0.06)
        box(a, x0, y - 0.012, haut - 0.30, x1, y + 0.012, haut - 0.28)
        box(a, x0, y - 0.012, haut - 0.62, x1, y + 0.012, haut - 0.60)
        n = max(4, int(round(w / 0.11)))
        for k in range(n + 1):
            xx = x0 + (x1 - x0) * k / n
            box(a, xx - 0.008, y - 0.008, 0.06, xx + 0.008, y + 0.008, haut - 0.62)
        nc = max(3, int(round(w / 0.19)))
        r = (x1 - x0) / nc / 2 - 0.005
        for k in range(nc):
            cx = x0 + (k + 0.5) * (x1 - x0) / nc
            tube(a, [(cx + r * math.cos(t), y, haut - 0.45 + r * math.sin(t))
                     for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)], 0.007, 4, closed=True)
            tube(a, [(cx, y, haut - 0.28), (cx, y, haut - 0.04)], 0.006, 4)
        return {"fer": (a, M["fer"])}
    return f


def fab_persiennes(w, h):
    """persiennes à la française ouvertes, rabattues sur le mur de part et d'autre du chambranle (W17)."""
    def f():
        a = Acc()
        lw = w / 2 + 0.02
        y0, y1 = CHS + 0.005, CHS + 0.04
        for s in (-1, 1):
            xa = s * (w / 2 + CH + 0.02)
            xb = s * (w / 2 + CH + 0.02 + lw)
            x0, x1 = sorted((xa, xb))
            box(a, x0, y0, 0.0, x0 + 0.055, y1, h)
            box(a, x1 - 0.055, y0, 0.0, x1, y1, h)
            for zz in (0.0, h / 2 - 0.04, h - 0.09):
                box(a, x0 + 0.055, y0, zz, x1 - 0.055, y1, zz + 0.09)
            z = 0.12
            while z < h - 0.12:
                if not (h / 2 - 0.06 < z < h / 2 + 0.06):
                    plate_yz(a, [(y0 + 0.004, z), (y1 - 0.004, z + 0.028), (y1 - 0.004, z + 0.04),
                                 (y0 + 0.004, z + 0.012)], x0 + 0.055, x1 - 0.055)
                z += 0.05
        return {"bois": (a, M["persienne"])}
    return f


def fab_soupirail(w, h):
    def f():
        fe, s = Acc(), Acc()
        n = int(round(w / 0.1))
        for k in range(1, n):
            xx = -w / 2 + w * k / n
            box(fe, xx - 0.01, -0.12, 0.0, xx + 0.01, -0.10, h)
        box(fe, -w / 2, -0.13, h / 2 - 0.01, w / 2, -0.10, h / 2 + 0.01)
        quad_or(s, [(-w / 2, -0.35, 0), (w / 2, -0.35, 0), (w / 2, -0.35, h), (-w / 2, -0.35, h)], (0, 1, 0))
        return {"fer": (fe, M["fer"]), "fond": (s, M["sombre"])}
    return f


nb_vitrages = 0
for o, P2, d2 in POSES:
    w, za, zb, genre = TYPES[o["type"]]
    h = zb - za
    Mw = repere(P2, d2, za)
    tag = f"{o['face']}_{o['type']}_{o['pos']:+.2f}".replace(".", ",")
    appui = genre == "fenetre"
    ext = 0.05 if o["type"] in ("pf_pan", "f_etage_ac") else 0.12
    enc = proto(("enc", w, h, o["deco"], appui, ext), fab_encadrement(w, h, o["deco"], appui, ext))
    poser(enc["pierre"], "bati_encadrement_" + tag, Mw)
    if genre in ("fenetre", "pf"):
        opaque = o["anneau"] == "attique"            # D-009 : attique vu de l'extérieur seulement
        me = proto(("men", w, h, genre, opaque), fab_menuiserie(w, h, genre, opaque))
        poser(me["menuiserie"], "bati_menuiserie_" + tag, Mw)
        poser(me["vitrage"], "bati_vitrage_" + tag, Mw)
        nb_vitrages += 1
    elif genre == "porte":
        me = proto(("porte", w, h), fab_porte(w, h))
        for k, ob in me.items():
            poser(ob, f"bati_porte_entree_{k}", Mw)
    elif genre == "soupirail":
        me = proto(("soup", w, h), fab_soupirail(w, h))
        poser(me["fer"], "bati_soupirail_grille_" + tag, Mw)
        poser(me["fond"], "bati_soupirail_fond_" + tag, Mw)
    if o["gc"]:
        gc = proto(("gc", w), fab_garde_corps(w))
        poser(gc["fer"], "bati_garde_corps_" + tag, Mw)
    if o["pers"]:
        pe = proto(("pers", w, h), fab_persiennes(w, h))
        poser(pe["bois"], "bati_persiennes_" + tag, Mw)
log(f"baies : {len(PROTOS)} prototypes, {OBJETS['instances']} instances")


# ================================================================ avant-corps sud : pans coupés, portique, balcon
acc_ac = Acc()
coupe = (COUPE_BOW, COUPE_BOW)
# entablement du portique (architrave portée par les colonnes)
sweep_ouvert(acc_ac, BOW, [(-0.05, 4.25), (0.62, 4.25), (0.62, 4.45), (0.64, 4.47), (0.64, 4.51), (0.62, 4.53),
                           (0.62, 4.70), (0.68, 4.73), (0.74, 4.79), (0.80, 4.82), (0.80, 4.95), (-0.30, 4.95)],
             *coupe)
# dalle du balcon (dessus z = 5,35, D-021) et son nez mouluré
ligne = decaler_ligne(BOW, 0.80, *coupe)
prism(acc_ac, ligne + [(ligne[-1][0], 8.95), (ligne[0][0], 8.95)], 4.95, Z_ETAGE - 0.002)
sweep_ouvert(acc_ac, BOW, [(-0.05, 4.95), (0.80, 4.95), (0.84, 4.99), (0.84, 5.28), (0.86, 5.31),
                           (0.86, Z_ETAGE), (0.60, Z_ETAGE)], *coupe)
# pilastres aux angles du bow, derrière les colonnes
for i in (1, 2):
    A, C, B = Vector((*BOW[i - 1], 0)), Vector((*BOW[i], 0)), Vector((*BOW[i + 1], 0))
    d1, d2 = (C - A).normalized(), (B - C).normalized()
    n1, n2 = Vector((d1.y, -d1.x, 0)), Vector((d2.y, -d2.x, 0))
    boite(acc_ac, C, d1, n1, (0, 0, 1), -0.32, 0.0, -0.02, 0.06, 0.0, 4.25)
    boite(acc_ac, C, d2, n2, (0, 0, 1), 0.0, 0.32, -0.02, 0.06, 0.0, 4.25)
    for zz, hh in ((0.0, 0.32), (3.95, 0.30)):
        boite(acc_ac, C, d1, n1, (0, 0, 1), -0.36, 0.0, -0.02, 0.10, zz, zz + hh)
        boite(acc_ac, C, d2, n2, (0, 0, 1), 0.0, 0.36, -0.02, 0.10, zz, zz + hh)
acc_ac.build("bati_avant_corps_sud_entablement_balcon", M["lisse"], uvscale=1.0)


# colonnes du portique (ioniques simplifiées)
def fab_colonne():
    a = Acc()
    box(a, -0.29, -0.29, Z_TERRASSE, 0.29, 0.29, 0.30)
    lathe(a, [(0.27, 0.30), (0.27, 0.36), (0.25, 0.39), (0.23, 0.40), (0.25, 0.44), (0.25, 0.47), (0.21, 0.50)],
          20, cap_bot=False, cap_top=False)
    prof = [(0.21, 0.50)]
    for k in range(1, 13):
        t = k / 12
        z = 0.50 + t * 3.33
        prof.append((0.205 - 0.03 * max(0.0, t - 0.33) ** 1.5, z))
    prof += [(0.195, 3.83), (0.205, 3.86), (0.205, 3.89), (0.19, 3.90), (0.23, 3.98), (0.24, 4.03)]
    lathe(a, prof, 20, cap_bot=False, cap_top=True)
    box(a, -0.27, -0.27, 4.03, 0.27, 0.27, 4.10)              # coussinet
    for s in (-1, 1):                                         # volutes
        lathe(a, [(0.075, -0.24), (0.085, -0.22), (0.085, 0.22), (0.075, 0.24)], 12,
              Matrix.Translation((s * 0.26, 0, 3.99)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    box(a, -0.31, -0.31, 4.10, 0.31, 0.31, 4.25)              # abaque
    return {"pierre": (a, M["lisse"])}


col = proto(("colonne",), fab_colonne)
for i in (1, 2):
    A, C, B = Vector((*BOW[i - 1], 0)), Vector((*BOW[i], 0)), Vector((*BOW[i + 1], 0))
    d1, d2 = (C - A).normalized(), (B - C).normalized()
    bis = (Vector((d1.y, -d1.x, 0)) + Vector((d2.y, -d2.x, 0))).normalized()
    p = C + bis * 0.40
    rot = Matrix.Rotation(math.atan2(bis.y, bis.x) - math.pi / 2, 4, "Z")
    poser(col["pierre"], f"bati_colonne_portique_{'est' if p.x > 0 else 'ouest'}", Matrix.Translation(p) @ rot)

# balustrade du balcon
AXE_BAL = 0.55
acc_bal_l = Acc()
sweep_ouvert(acc_bal_l, BOW, [(AXE_BAL - 0.17, Z_ETAGE), (AXE_BAL + 0.17, Z_ETAGE), (AXE_BAL + 0.17, Z_ETAGE + 0.13),
                              (AXE_BAL + 0.15, Z_ETAGE + 0.16), (AXE_BAL - 0.15, Z_ETAGE + 0.16),
                              (AXE_BAL - 0.17, Z_ETAGE + 0.13)], *coupe, ferme=True)
Z_TAB = Z_ETAGE + 0.80
sweep_ouvert(acc_bal_l, BOW, [(AXE_BAL - 0.15, Z_TAB), (AXE_BAL + 0.15, Z_TAB), (AXE_BAL + 0.15, Z_TAB + 0.03),
                              (AXE_BAL + 0.19, Z_TAB + 0.07), (AXE_BAL + 0.19, Z_TAB + 0.15),
                              (AXE_BAL - 0.19, Z_TAB + 0.15), (AXE_BAL - 0.19, Z_TAB + 0.07),
                              (AXE_BAL - 0.15, Z_TAB + 0.03)], *coupe, ferme=True)
axe = decaler_ligne(BOW, AXE_BAL, *coupe)
for k, (x, y) in enumerate(axe):                 # dés aux angles et aux extrémités
    sweep_rect(acc_bal_l, x, y, 0.20, 0.20, [(0, Z_ETAGE + 0.16), (0, Z_TAB), (0.03, Z_TAB + 0.03),
                                              (0.03, Z_TAB + 0.15)], True, False)
acc_bal_l.build("bati_balcon_balustrade", M["lisse"], uvscale=1.0)


def fab_balustre():
    a = Acc()
    lathe(a, [(0.07, 0.0), (0.075, 0.03), (0.06, 0.05), (0.055, 0.08), (0.075, 0.16), (0.098, 0.27),
              (0.09, 0.34), (0.06, 0.42), (0.045, 0.47), (0.05, 0.50), (0.065, 0.53), (0.065, 0.56),
              (0.075, 0.6), (0.075, 0.64)], 12)
    return {"pierre": (a, M["lisse"])}


bal = proto(("balustre",), fab_balustre)
nbal = 0
for i in range(len(axe) - 1):
    A, B = Vector((*axe[i], 0)), Vector((*axe[i + 1], 0))
    L = (B - A).length
    m0 = 0.30
    k = int((L - 2 * m0) / 0.24)
    for j in range(k + 1):
        p = A + (B - A) * ((m0 + (L - 2 * m0) * j / max(k, 1)) / L)
        poser(bal["pierre"], f"bati_balustre_{nbal:02d}", Matrix.Translation((p.x, p.y, Z_ETAGE + 0.16)))
        nbal += 1
log(f"avant-corps sud : {nbal} balustres")

# ================================================================ avant-corps nord : pilastres, entablement, tables
acc_an = Acc()
yN = AC_N[1]
for s in (-1, 1):
    xc = s * 1.33
    box(acc_an, xc - 0.25, yN - 0.17, 0.0, xc + 0.25, yN + 0.02, 3.95)
    box(acc_an, xc - 0.30, yN - 0.22, 0.0, xc + 0.30, yN + 0.02, 0.32)
    box(acc_an, xc - 0.29, yN - 0.21, 3.85, xc + 0.29, yN + 0.02, 3.95)
    box(acc_an, xc - 0.33, yN - 0.25, 3.95, xc + 0.33, yN + 0.02, 4.10)
    for sx in (-1, 1):            # volutes du chapiteau (P38)
        lathe(acc_an, [(0.06, -0.08), (0.07, -0.07), (0.07, 0.07), (0.06, 0.08)], 10,
              Matrix.Translation((xc + sx * 0.25, yN - 0.17, 3.86)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
# entablement au-dessus de la porte, retourné sur les côtés de l'avant-corps
PTS_N = [(-AC_N[0], -Y_CORPS), (-AC_N[0], yN), (AC_N[0], yN), (AC_N[0], -Y_CORPS)]
COUPE_N = ((0.0, -Y_CORPS), (1.0, 0.0))
sweep_ouvert(acc_an, PTS_N, [(-0.05, 4.10), (0.18, 4.10), (0.18, 4.30), (0.20, 4.32), (0.20, 4.36),
                             (0.18, 4.38), (0.18, 4.70), (0.24, 4.74), (0.30, 4.80), (0.30, 4.98),
                             (-0.3, 4.98)], COUPE_N, COUPE_N)


def table(acc, x0, x1, z0, z1, y, s=0.06, p=0.035):
    """table (panneau) bordée d'une moulure plate en saillie sur le nu."""
    box(acc, x0, y - p, z0, x1, y + 0.01, z0 + s)
    box(acc, x0, y - p, z1 - s, x1, y + 0.01, z1)
    box(acc, x0, y - p, z0 + s, x0 + s, y + 0.01, z1 - s)
    box(acc, x1 - s, y - p, z0 + s, x1, y + 0.01, z1 - s)


for s in (-1, 1):
    xa, xb = sorted((s * 1.72, s * 3.05))
    table(acc_an, xa, xb, 0.55, 3.80, yN)
    table(acc_an, xa, xb, 5.85, 8.35, yN)
    table(acc_an, xa, xb, 10.98, 12.55, yN)
    table(acc_an, xa + 0.15, xb - 0.15, 9.0 - 0.02, 9.2, yN)      # petite table sous la corniche
acc_an.build("bati_avant_corps_nord_decor", M["lisse"], uvscale=1.0)

# inscription de la frise (P38)
cu = bpy.data.curves.new("bati_inscription", "FONT")
cu.body = "CHÂTEAU SAINT VICTOR"
cu.size = 0.15
cu.extrude = 0.006
cu.align_x = "CENTER"
cu.align_y = "CENTER"
tob = bpy.data.objects.new("tmp_txt", cu)
SC.collection.objects.link(tob)
tob.location = (0.0, yN - 0.185, 4.54)
tob.rotation_euler = (math.radians(90), 0, 0)
bpy.context.view_layer.update()
me_txt = bpy.data.meshes.new_from_object(tob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
me_txt.materials.clear()
me_txt.materials.append(M["inscription"])
ins = bpy.data.objects.new("bati_inscription_chateau_saint_victor", me_txt)
COL.objects.link(ins)
ins.parent = RACINE
ins.matrix_world = tob.matrix_world.copy()
bpy.data.objects.remove(tob, do_unlink=True)
log("avant-corps nord")

acc_m.build("bati_moulures_corniches_chaines", M["lisse"], uvscale=1.0)

# ================================================================ export
for o in bpy.data.objects:
    o.select_set(False)
for o in COL.objects:
    o.select_set(True)
glb = os.path.join(EXPDIR, ID + ".glb")
kw = dict(filepath=glb, export_format="GLB", use_selection=True, export_apply=False, export_yup=True)
try:
    bpy.ops.export_scene.gltf(**kw, export_image_format="AUTO")
except TypeError:
    bpy.ops.export_scene.gltf(**kw)
log(f"GLB {os.path.getsize(glb) / 1e6:.1f} Mo")
mesh_uniques = {o.data.name: o.data for o in COL.objects if o.type == "MESH"}
nverts = sum(len(m.vertices) for m in mesh_uniques.values())
nfaces = sum(len(m.polygons) for m in mesh_uniques.values())
log(f"{len(COL.objects)} objets, {len(mesh_uniques)} maillages, {nverts} sommets, {nfaces} faces (uniques)")

# ================================================================ contexte de rendu (non exporté)
if not SANS_RENDU:
    avant = set(bpy.data.objects)
    for nom in ("toiture", "terrasse"):
        p = os.path.join(EXPDIR, nom + ".glb")
        if os.path.exists(p):
            bpy.ops.import_scene.gltf(filepath=p)
    for ob in set(bpy.data.objects) - avant:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        CTX.objects.link(ob)
    # volumes intérieurs sombres : on ne voit pas à travers le château vide
    acc_ctx = Acc()
    for nom, ext_, int_, z0, z1, mt in ANNEAUX[1:]:
        prism(acc_ctx, offset_poly(ext_, EP + 0.05), max(z0, -0.2), z1 - 0.05)
    acc_ctx.build("ctx_interieur", mat("ctx_interieur", color=(0.05, 0.045, 0.04), rough=1.0), CTX, parent=None)
    sol = Acc()
    box(sol, -90, -90, Z_COUR_N - 0.2, 90, 17.2, Z_COUR_N - 0.005)
    box(sol, -90, 17.2, NIV["cour_sablee_sud"]["valeur"] - 0.2, 90, 90, NIV["cour_sablee_sud"]["valeur"] - 0.005)
    sol.build("ctx_sol", mat("ctx_sol", color=(0.66, 0.61, 0.52), rough=1.0), CTX, parent=None)

    world = bpy.data.worlds.new("ciel")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.32, 0.52, 0.88, 1)
    bg.inputs["Strength"].default_value = 0.45
    SC.world = world
    sun = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", "SUN"))
    sun.data.energy = 3.6
    sun.data.color = (1.0, 0.95, 0.87)
    sun.data.angle = math.radians(1.5)
    CTX.objects.link(sun)
    R = SC.render
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            R.engine = eng
            break
        except TypeError:
            continue
    try:
        SC.eevee.taa_render_samples = 16 if RAPIDE else 48
        SC.eevee.use_shadows = True
    except Exception:
        pass
    try:
        SC.view_settings.view_transform = "AgX"
        SC.view_settings.look = "AgX - Medium High Contrast"
        SC.view_settings.exposure = -0.2
    except Exception:
        pass
    R.image_settings.file_format = "PNG"
    R.image_settings.color_mode = "RGB"

    def camera(nom, pos, cible, lens=35):
        c = bpy.data.objects.new(nom, bpy.data.cameras.new(nom))
        CTX.objects.link(c)
        c.location = pos
        c.rotation_euler = (Vector(cible) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        c.data.lens = lens
        c.data.clip_end = 1000
        return c

    VUES = [  # nom, position, cible, focale, azimut du soleil (degrés)
        ("bati", (0.0, 60.0, 1.6), (0.0, 9.0, 6.5), 35, 160),               # ≈ W01 (pelouse sud)
        ("bati_sud_aerien", (2.0, 52.0, 47.0), (0.5, 1.5, 8.0), 35, 160),   # ≈ W15
        ("bati_nord", (0.0, -46.0, 30.0), (0.0, -3.0, 6.5), 35, 20),        # ≈ W11
        ("bati_nord_sol", (0.0, -23.0, -0.1), (0.0, -9.5, 6.0), 20, 20),    # ≈ P38/P39
        ("bati_est", (33.0, 17.0, 1.7), (15.0, -1.0, 6.5), 24, 110),        # ≈ W17
        ("bati_detail", (-3.0, 22.0, 2.0), (0.8, 10.5, 4.4), 30, 160),       # avant-corps sud
        ("bati_interieur", (-6.5, 3.0, 1.7), (2.0, 10.0, 2.6), 16, 160),    # contrôle : trous et parement
    ]
    seules = os.environ.get("BATI_VUES")
    for nom, pos, cible, lens, az in VUES:
        if seules and nom not in seules.split(","):
            continue
        sun.rotation_euler = (math.radians(45), 0, math.radians(az))
        SC.camera = camera("cam_" + nom, pos, cible, lens)
        R.resolution_x, R.resolution_y = (1100, 620) if RAPIDE else (1650, 930)
        R.filepath = os.path.join(RENDIR, nom + ".png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"rendu {R.filepath} ({time.time() - t:.0f}s)")

    for ob in list(CTX.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
bpy.data.collections.remove(CTX)
if hasattr(bpy.data, "orphans_purge"):
    bpy.data.orphans_purge(do_recursive=True)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(EXPDIR, ID + ".blend"), compress=True)
log("fini")

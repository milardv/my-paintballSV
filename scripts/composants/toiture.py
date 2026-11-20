# Composant P2.toiture : toitures en tuiles canal, verrière, souches, balustrades d'acrotère,
# chéneaux, descentes, conduit métallique, antenne, mât en fer forgé.
# blender -b --factory-startup --python scripts/composants/toiture.py
# Sorties : export/composants/toiture.glb, export/composants/toiture.blend, rendus/toiture*.png
# Repère D-003 : mètres, +X est, +Y sud, Z haut, RDC = 0. Cotes : travail/gabarit.json.

import bpy
import json
import math
import os
import random
import sys
import time

import numpy as np
from mathutils import Matrix, Vector

T0 = time.time()
ID = "toiture"
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
G = json.load(open(os.path.join(ROOT, "travail", "gabarit.json"), encoding="utf-8"))
NIV = G["niveaux"]
TOI = G["toiture"]
TEXDIR = os.path.join(ROOT, "assets", "generes", "toiture")
EXPDIR = os.path.join(ROOT, "export", "composants")
RENDIR = os.path.join(ROOT, "rendus")
for d in (TEXDIR, EXPDIR, RENDIR):
    os.makedirs(d, exist_ok=True)

RAPIDE = "--rapide" in sys.argv  # rendu basse définition pour itérer

rng = np.random.default_rng(1871)
random.seed(1871)

# ---------------------------------------------------------------- cotes
Z_CORN = NIV["corniche_attique"]["valeur"]            # 14.0 dessus de corniche attique
Z_CORN_PAV = NIV["corniche_etage_pavillons"]["valeur"]  # 10.1 dessus de corniche pavillons
Z_FAITE = NIV["faitage_principal"]["valeur"]          # 17.3 (±1,2)
Z_SOUCHE = NIV["souches_haut"]["valeur"]              # 17.5
Z_SOL_S = NIV["terrasse_sud"]["valeur"]               # -0.05
Z_SOL_N = NIV["cour_nord_parking"]["valeur"]          # -1.44

X_CORPS, Y_CORPS = 10.8, 8.75
X_EXT = 18.0
Y_BLOC = 3.85
Y_PAV = 9.45
AC_N = (4.0, -12.45)        # avant-corps nord : demi-largeur, nu
AC_S = (3.96, 9.35)        # avant-corps sud (attique)

BAL_RETRAIT = 0.25         # axe de la balustrade depuis le nu
BAL_INT = 0.47             # face intérieure de la balustrade
EGOUT = 0.5                # égout des toits depuis le nu
Z_EGOUT = Z_CORN + 0.15
Z_EGOUT_PAV = Z_CORN_PAV + 0.15
PENTE = 22.0               # pente des longs pans (tuiles canal ≈ 40 %)
PENTE_CROUPE = 30.0        # croupes d'extrémité
PENTE_PAV = 19.0

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
    print(f"[toiture {time.time() - T0:6.1f}s] {msg}", flush=True)


# ================================================================ textures procédurales
def img_pixels(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[:, :, :3]


def save_img(name, arr, noncolor=False, fmt="JPEG"):
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), dtype=np.float32)], 2)
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(np.clip(arr, 0, 1).astype(np.float32).ravel())
    ext = ".jpg" if fmt == "JPEG" else ".png"
    path = os.path.join(TEXDIR, name + ext)
    SC.render.image_settings.file_format = fmt
    if fmt == "JPEG":
        SC.render.image_settings.quality = 92
    img.save_render(path, scene=SC)
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
    for o in range(octaves):
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


def normal_from_height(h, px, k=1.0):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * px) * k
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * px) * k
    n = np.stack([-gx, -gy, np.ones_like(h)], 2)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def tex_tuiles():
    """tuiles canal : 1 m × 1 m, 4 couples courant/couvert, 3 rangs de 33 cm (v vers le faîtage)."""
    S = 2048
    c = (np.arange(S) + 0.5) / S
    U, V = np.meshgrid(c, c)
    NP, P, NR, R = 4, 0.25, 3, 1 / 3
    row = np.floor(V / R).astype(int) % NR
    t = V / R - np.floor(V / R)            # 0 = bas visible de la tuile, 1 = sous la tuile du rang supérieur
    ju = rng.normal(0, 0.005, (NR, NP, 2))
    jh = rng.normal(0, 0.003, (NR, NP, 2))
    pal = np.array([[0.80, 0.42, 0.26], [0.74, 0.37, 0.22], [0.84, 0.50, 0.32], [0.68, 0.34, 0.21],
                    [0.78, 0.47, 0.33], [0.62, 0.30, 0.19], [0.82, 0.55, 0.40], [0.72, 0.43, 0.30]])
    cols = pal[rng.integers(0, len(pal), (NR, NP, 2))] * rng.uniform(0.9, 1.08, (NR, NP, 2, 1))

    def wrapd(x):
        return np.abs((x + 0.5) % 1.0 - 0.5)

    h = np.full((S, S), -1.0, np.float32)
    col = np.zeros((S, S, 3), np.float32)
    cover = np.zeros((S, S), bool)
    for k in range(NP):
        # tuile de courant (concave), centrée sur k*P
        cc = k * P + ju[row, k, 0]
        d = wrapd(U - cc)
        rch = 0.118
        hc = np.where(d < rch, 0.012 + 0.05 * (d / rch) ** 2 + jh[row, k, 0], -1.0)
        m = hc > h
        h = np.where(m, hc, h)
        col[m] = cols[row, k, 0][m]
        # tuile de couvert (convexe), plus large en bas
        cu = k * P + 0.125 + ju[row, k, 1]
        d = wrapd(U - cu)
        rc = 0.080 * (1.0 + 0.14 * (1 - t))
        hv = np.where(d < rc, 0.046 + 0.062 * np.sqrt(np.clip(1 - (d / rc) ** 2, 0, 1)) + jh[row, k, 1], -1.0)
        m = hv > h
        h = np.where(m, hv, h)
        col[m] = cols[row, k, 1][m]
        cover |= m
    h = np.maximum(h, 0.0)
    h = h + 0.02 * (1 - t) ** 1.3          # bord bas de chaque tuile posé sur le rang inférieur
    h = blur(h, 2)
    nrm = normal_from_height(h, 1.0 / S, 1.0)

    det = img_pixels(os.path.join(ROOT, "assets/polyhaven/polyhaven-roof_09/roof_09_diff_2k.jpg"))
    if det.shape[0] != S:
        det = np.array(det[:: max(1, det.shape[0] // S), :: max(1, det.shape[1] // S)])[:S, :S]
    lum = det.mean(2)
    lum = lum / lum.mean()
    ao = 0.55 + 0.45 * smoothstep(0.0, 0.085, h)
    ao *= 1 - 0.45 * smoothstep(0.86, 1.0, t)    # ombre portée par le rang supérieur
    big = vnoise(S, 6, 11, 4)
    lich = smoothstep(0.62, 0.8, vnoise(S, 24, 12, 3)) * (0.35 + 0.4 * cover)
    alb = col * (0.78 + 0.32 * (lum[:, :, None] - 1) + 0.22) * ao[:, :, None]
    alb *= (0.88 + 0.22 * big)[:, :, None]
    alb = alb * (1 - lich[:, :, None] * 0.55) + np.array([0.56, 0.54, 0.47]) * lich[:, :, None] * 0.55
    rough = 0.72 + 0.15 * vnoise(S, 16, 13, 3) + 0.08 * lich
    return (save_img("toiture_tuiles_canal_diff", alb.astype(np.float32)),
            save_img("toiture_tuiles_canal_nor_gl", nrm.astype(np.float32), True),
            save_img("toiture_tuiles_canal_rough", np.repeat(rough[:, :, None], 3, 2).astype(np.float32), True))


def tex_pierre():
    """calcaire beige : 2 m × 2 m ; une version lisse, une version à joints (assises de 33 cm)."""
    base = os.path.join(ROOT, "assets/polyhaven/polyhaven-beige_wall_001")
    d = img_pixels(os.path.join(base, "beige_wall_001_diff_2k.jpg"))
    n = img_pixels(os.path.join(base, "beige_wall_001_nor_gl_2k.jpg"))
    S = d.shape[0]
    lum = d.mean(2)
    lum = lum / lum.mean()
    tint = np.array([0.80, 0.75, 0.64], np.float32)
    grime = vnoise(S, 5, 21, 4)
    spots = smoothstep(0.55, 0.85, vnoise(S, 20, 22, 3))
    alb = tint * (1.0 + 0.55 * (lum[:, :, None] - 1))
    alb *= (0.86 + 0.16 * grime)[:, :, None]
    alb *= (1 - 0.10 * spots)[:, :, None]
    # légères variations de teinte par bloc
    c = (np.arange(S) + 0.5) / S * 2.0
    U, V = np.meshgrid(c, c)
    course = np.floor(V / (1 / 3)).astype(int)
    off = (course % 2) * (1 / 3)
    block = np.floor((U + off) / (2 / 3)).astype(int) % 3
    bt = rng.uniform(0.93, 1.05, (6, 3))
    fac = bt[course % 6, block]
    ju = np.abs(((U + off) % (2 / 3)) - 1 / 3)            # distance au centre du bloc
    jv = np.abs((V % (1 / 3)) - 1 / 6)
    jx = smoothstep(1 / 3 - 0.006, 1 / 3 - 0.002, ju)
    jy = smoothstep(1 / 6 - 0.006, 1 / 6 - 0.002, jv)
    joint = np.maximum(jx, jy)
    alb_j = alb * fac[:, :, None] * (1 - 0.22 * joint[:, :, None])
    nb = n * 2 - 1
    hj = -0.004 * blur(joint.astype(np.float32), 2)
    nj = normal_from_height(hj, 2.0 / S) * 2 - 1
    nn = np.stack([nb[:, :, 0] + nj[:, :, 0], nb[:, :, 1] + nj[:, :, 1], nb[:, :, 2]], 2)
    nn /= np.linalg.norm(nn, axis=2, keepdims=True)
    rough = 0.82 + 0.08 * grime
    r3 = np.repeat(rough[:, :, None], 3, 2).astype(np.float32)
    return (save_img("toiture_pierre_diff", alb.astype(np.float32)),
            save_img("toiture_pierre_appareil_diff", alb_j.astype(np.float32)),
            save_img("toiture_pierre_appareil_nor_gl", (nn * 0.5 + 0.5).astype(np.float32), True),
            save_img("toiture_pierre_rough", r3, True)), n


def tex_terre_cuite():
    S = 512
    a = vnoise(S, 8, 31, 4)
    b = vnoise(S, 40, 32, 2)
    base = np.array([0.76, 0.40, 0.25], np.float32)
    alb = base * (0.82 + 0.25 * a + 0.1 * b)[:, :, None]
    soot = smoothstep(0.6, 0.85, vnoise(S, 4, 33, 3))
    alb = alb * (1 - 0.35 * soot[:, :, None])
    return save_img("toiture_terre_cuite_diff", alb.astype(np.float32))


log("textures…")
TX_TUILE = tex_tuiles()
(TX_PIERRE, TX_PIERRE_APP, TX_PIERRE_APP_N, TX_PIERRE_R), _ = tex_pierre()
TX_TERRE = tex_terre_cuite()
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
    "tuile": mat("toiture_tuiles_canal", diff=TX_TUILE[0], nor=TX_TUILE[1], rgh=TX_TUILE[2], rough=0.8),
    "terre": mat("toiture_terre_cuite", diff=TX_TERRE, rough=0.75, double=True),
    "mortier": mat("toiture_mortier_chaux", color=(0.80, 0.74, 0.63), rough=0.95),
    "pierre": mat("toiture_pierre_calcaire", diff=TX_PIERRE, nor=TX_PIERRE_APP_N, rgh=TX_PIERRE_R,
                  rough=0.85, nor_force=0.4),
    "pierre_app": mat("toiture_pierre_appareillee", diff=TX_PIERRE_APP, nor=TX_PIERRE_APP_N, rgh=TX_PIERRE_R,
                      rough=0.85),
    "zinc": mat("toiture_zinc", color=(0.47, 0.49, 0.50), rough=0.45, metal=0.85, double=True),
    "fer": mat("toiture_fer_noir", color=(0.025, 0.025, 0.027), rough=0.45, metal=0.6, double=True),
    "inox": mat("toiture_inox", color=(0.72, 0.72, 0.73), rough=0.28, metal=1.0, double=True),
    "alu": mat("toiture_alu_antenne", color=(0.78, 0.79, 0.80), rough=0.35, metal=1.0),
    "verre": mat("toiture_verre_verriere", color=(0.52, 0.60, 0.64), rough=0.06, alpha=0.32, double=True),
    "suie": mat("toiture_suie", color=(0.03, 0.028, 0.026), rough=0.95, double=True),
    "fonte": mat("toiture_fonte_peinte", color=(0.30, 0.31, 0.30), rough=0.55, metal=0.4),
}


# ================================================================ géométrie de base
class Acc:
    """accumule des faces (une seule matière) puis crée un objet."""

    def __init__(self):
        self.v, self.f, self.uv, self.sm = [], [], [], []

    def add(self, verts, faces, uvs=None, smooth=False):
        o = len(self.v)
        self.v.extend([tuple(p) for p in verts])
        for i, fc in enumerate(faces):
            self.f.append([o + k for k in fc])
            self.uv.append(uvs[i] if uvs else None)
            self.sm.append(smooth[i] if isinstance(smooth, (list, tuple)) else smooth)

    def build(self, name, material, coll=COL, uvscale=1.0, parent=RACINE):
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
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        if parent is not None:
            ob.parent = parent
        return ob


def V3(*a):
    return Vector(a)


def quad_or(acc, pts, want, smooth=False, uvs=None):
    """ajoute une face en l'orientant vers `want`."""
    p = [Vector(x) for x in pts]
    n = (p[1] - p[0]).cross(p[2] - p[1])
    if n.length < 1e-12:
        n = (p[2] - p[0]).cross(p[3 % len(p)] - p[0])
    if n.dot(want) < 0:
        p = p[::-1]
        if uvs:
            uvs = uvs[::-1]
    acc.add(p, [list(range(len(p)))], [uvs] if uvs else None, smooth)


def sweep_rect(acc, cx, cy, hx, hy, prof, top=True, bottom=False, smooth=False):
    """anneaux rectangulaires (moulure tournant autour d'un rectangle). prof = [(retrait, z)] de bas en haut."""
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


def poly_area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def sweep_line(acc, P0, P1, sec, up=(0, 0, 1), caps=True, smooth=False):
    """profil fermé sec=[(lat, h)] extrudé de P0 à P1 ; lat vers la gauche de P0→P1, h selon up."""
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


def lathe(acc, prof, seg=12, M=Matrix.Identity(4), cap_bot=True, cap_top=True, smooth=True):
    """profil [(r, z)] tourné autour de z local."""
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


def frame_z(P, d):
    """matrice plaçant z local selon d en P."""
    d = Vector(d).normalized()
    a = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0))
    x = a.cross(d).normalized()
    y = d.cross(x)
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = x[i], y[i], d[i], P[i]
    return m


def plate(acc, poly, M, thick):
    """plaque : polygone (x, z) local extrudé de ±thick/2 selon y local."""
    if poly_area(poly) < 0:
        poly = poly[::-1]
    m = len(poly)
    v = [M @ Vector((x, -thick / 2, z)) for x, z in poly] + [M @ Vector((x, thick / 2, z)) for x, z in poly]
    f = [list(range(m)), list(range(m, 2 * m))[::-1]]
    f += [[k, m + k, m + (k + 1) % m, (k + 1) % m] for k in range(m)]
    acc.add(v, f)


def prism(acc, poly, z0, z1):
    if poly_area(poly) < 0:
        poly = poly[::-1]
    m = len(poly)
    v = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    f = [list(range(m))[::-1], list(range(m, 2 * m))]
    f += [[k, (k + 1) % m, m + (k + 1) % m, m + k] for k in range(m)]
    acc.add(v, f)


# ================================================================ polygones 2D
def clip_poly(poly, a, b, c, eps=1e-9):
    """garde a*x + b*y + c <= 0"""
    out = []
    n = len(poly)
    for i in range(n):
        P, Q = poly[i], poly[(i + 1) % n]
        fp, fq = a * P[0] + b * P[1] + c, a * Q[0] + b * Q[1] + c
        if fp <= eps:
            out.append(P)
        if (fp <= eps) != (fq <= eps):
            t = fp / (fp - fq)
            out.append((P[0] + (Q[0] - P[0]) * t, P[1] + (Q[1] - P[1]) * t))
    res = []
    for p in out:
        if not res or abs(p[0] - res[-1][0]) + abs(p[1] - res[-1][1]) > 1e-7:
            res.append(p)
    if len(res) > 1 and abs(res[0][0] - res[-1][0]) + abs(res[0][1] - res[-1][1]) < 1e-7:
        res.pop()
    return res


def offset_poly(poly, d):
    """décalage vers l'intérieur d'un polygone anti-horaire (onglets)."""
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


# ================================================================ toits (minimum de plans)
class Toit:
    """toit à pans sur un rectangle : z = min des plans des côtés actifs (croupes, arêtiers, faîtage)."""

    G = {"xmin": lambda r: (1, 0, -r[0]), "xmax": lambda r: (-1, 0, r[2]),
         "ymin": lambda r: (0, 1, -r[1]), "ymax": lambda r: (0, -1, r[3])}

    def __init__(self, nom, rect, ez, pentes, trous=()):
        self.nom, self.rect, self.ez = nom, rect, ez
        self.pl = {}
        for s, p in pentes.items():
            self.pl[s] = (math.tan(math.radians(p)), Toit.G[s](rect))
        self.trous = trous
        self.faces = self._faces()

    def coef(self, s):
        t, g = self.pl[s]
        return t * g[0], t * g[1], self.ez + t * g[2]

    def zs(self, s, x, y):
        a, b, c = self.coef(s)
        return a * x + b * y + c

    def z(self, x, y):
        return min(self.zs(s, x, y) for s in self.pl)

    def dedans(self, x, y, m=0.0):
        x0, y0, x1, y1 = self.rect
        if not (x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m):
            return False
        for hx0, hy0, hx1, hy1 in self.trous:
            if hx0 < x < hx1 and hy0 < y < hy1:
                return False
        return True

    def _faces(self):
        x0, y0, x1, y1 = self.rect
        res = {}
        for s in self.pl:
            poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            A = self.coef(s)
            for o in self.pl:
                if o == s:
                    continue
                B = self.coef(o)
                poly = clip_poly(poly, A[0] - B[0], A[1] - B[1], A[2] - B[2])
                if len(poly) < 3:
                    break
            if len(poly) >= 3 and abs(poly_area(poly)) > 1e-4:
                res[s] = poly
        return res

    def morceaux(self, poly):
        pieces = [poly]
        for hx0, hy0, hx1, hy1 in self.trous:
            nouv = []
            for p in pieces:
                regions = [
                    [(1, 0, -hx0)], [(-1, 0, hx1)],
                    [(-1, 0, hx0), (1, 0, -hx1), (0, 1, -hy0)],
                    [(-1, 0, hx0), (1, 0, -hx1), (0, -1, hy1)],
                ]
                for reg in regions:
                    q = p
                    for a, b, c in reg:
                        q = clip_poly(q, a, b, c)
                        if len(q) < 3:
                            break
                    if len(q) >= 3 and abs(poly_area(q)) > 1e-4:
                        nouv.append(q)
            pieces = nouv
        return pieces

    def sur_bord(self, P, Q):
        x0, y0, x1, y1 = self.rect
        e = 1e-5
        for k, val in ((0, x0), (0, x1), (1, y0), (1, y1)):
            if abs(P[k] - val) < e and abs(Q[k] - val) < e:
                return True
        return False

    def aretes(self):
        """arêtiers et faîtages : (A, B, côté1, côté2)."""
        segs = {}
        for s, poly in self.faces.items():
            for i in range(len(poly)):
                P, Q = poly[i], poly[(i + 1) % len(poly)]
                if self.sur_bord(P, Q):
                    continue
                key = tuple(sorted([(round(P[0], 4), round(P[1], 4)), (round(Q[0], 4), round(Q[1], 4))]))
                segs.setdefault(key, set()).add(s)
        out = []
        for (A, B), ss in segs.items():
            ss = sorted(ss)
            if len(ss) == 1:
                # retrouver le second pan : celui dont le plan est égal au milieu
                mx, my = (A[0] + B[0]) / 2, (A[1] + B[1]) / 2
                z1 = self.zs(ss[0], mx, my)
                cand = [o for o in self.pl if o != ss[0] and abs(self.zs(o, mx, my) - z1) < 1e-4]
                if not cand:
                    continue
                ss.append(cand[0])
            out.append((A, B, ss[0], ss[1]))
        return out

    def normale(self, s):
        a, b, _ = self.coef(s)
        return Vector((-a, -b, 1)).normalized()

    def construire(self, acc, rive=0.07):
        for s, poly in self.faces.items():
            t, g = self.pl[s]
            k = math.sqrt(1 + t * t)
            du = random.uniform(0, 1)
            for p in self.morceaux(poly):
                verts, uvs = [], []
                for x, y in p:
                    d = g[0] * x + g[1] * y + g[2]
                    u = (x if s[0] == "y" else y) * (1 if s in ("ymin", "xmax") else -1)
                    verts.append((x, y, self.ez + t * d))
                    uvs.append((u + du, d * k))
                acc.add(verts, [list(range(len(verts)))], [uvs])
                # about de rive (épaisseur des tuiles à l'égout)
                for i in range(len(p)):
                    P, Q = p[i], p[(i + 1) % len(p)]
                    dP = g[0] * P[0] + g[1] * P[1] + g[2]
                    dQ = g[0] * Q[0] + g[1] * Q[1] + g[2]
                    if abs(dP) < 1e-6 and abs(dQ) < 1e-6:
                        out = Vector((-g[0], -g[1], 0))
                        quad_or(acc, [(P[0], P[1], self.ez), (Q[0], Q[1], self.ez),
                                      (Q[0], Q[1], self.ez - rive), (P[0], P[1], self.ez - rive)], out)


def seg_moins_rects(A, B, rects):
    """parties du segment 2D AB hors des rectangles."""
    inter = [(0.0, 1.0)]
    for x0, y0, x1, y1 in rects:
        t0, t1 = 0.0, 1.0
        dx, dy = B[0] - A[0], B[1] - A[1]
        ok = True
        for p, q in ((-dx, A[0] - x0), (dx, x1 - A[0]), (-dy, A[1] - y0), (dy, y1 - A[1])):
            if abs(p) < 1e-12:
                if q < 0:
                    ok = False
            else:
                r = q / p
                if p < 0:
                    t0 = max(t0, r)
                else:
                    t1 = min(t1, r)
        if not ok or t0 >= t1:
            continue
        nouv = []
        for a, b in inter:
            if b <= t0 or a >= t1:
                nouv.append((a, b))
            else:
                if a < t0:
                    nouv.append((a, t0))
                if b > t1:
                    nouv.append((t1, b))
        inter = nouv
    return [((A[0] + (B[0] - A[0]) * a, A[1] + (B[1] - A[1]) * a),
             (A[0] + (B[0] - A[0]) * b, A[1] + (B[1] - A[1]) * b)) for a, b in inter if b - a > 1e-3]


# ---------------------------------------------------------------- définition des toits
VER_HX, VER_HY = TOI["verriere"]["largeur_eo_m"] / 2 + 0.1, TOI["verriere"]["longueur_ns_m"] / 2 + 0.1  # 1.5 × 3.35
TROU_VER = (-VER_HX, -VER_HY, VER_HX, VER_HY)

xe, ye = X_CORPS - EGOUT, Y_CORPS - EGOUT
long_faitage = 7.7  # W12 : faîtage du corps ≈ 7,7 m
z_faite = Z_EGOUT + ye * math.tan(math.radians(PENTE))
p_bout = math.degrees(math.atan((z_faite - Z_EGOUT) / (xe - long_faitage / 2)))
TOITS = [Toit("corps", (-xe, -ye, xe, ye), Z_EGOUT,
              {"ymin": PENTE, "ymax": PENTE, "xmin": p_bout, "xmax": p_bout}, trous=[TROU_VER])]
# blocs d'extrémité E/O (croupe vers l'extérieur, pignon caché dans le corps)
for sx in (-1, 1):
    x_out = sx * (X_EXT - EGOUT)
    rect = (min(sx * 7.4, x_out), -(Y_BLOC - EGOUT), max(sx * 7.4, x_out), Y_BLOC - EGOUT)
    TOITS.append(Toit("bloc_" + ("est" if sx > 0 else "ouest"), rect, Z_EGOUT,
                      {"ymin": PENTE, "ymax": PENTE, ("xmax" if sx > 0 else "xmin"): PENTE_CROUPE}))
# avant-corps nord et sud (croupe vers l'extérieur)
hxn = AC_N[0] - EGOUT
TOITS.append(Toit("avant_corps_nord", (-hxn, AC_N[1] + EGOUT, hxn, 0.0), Z_EGOUT,
                  {"xmin": PENTE, "xmax": PENTE, "ymin": PENTE_CROUPE}))
hxs = AC_S[0] - EGOUT
TOITS.append(Toit("avant_corps_sud", (-hxs, 0.0, hxs, AC_S[1] - EGOUT), Z_EGOUT,
                  {"xmin": PENTE, "xmax": PENTE, "ymax": PENTE_CROUPE}))
# pavillons d'angle : deux pans contre les murs du corps et du bloc
PAVILLONS = []
for sx in (-1, 1):
    for sy in (-1, 1):
        xa, xb = sorted((sx * X_CORPS, sx * (X_EXT - EGOUT)))
        ya, yb = sorted((sy * Y_BLOC, sy * (Y_PAV - EGOUT)))
        nom = "pavillon_" + ("S" if sy > 0 else "N") + ("E" if sx > 0 else "O")
        TOITS.append(Toit(nom, (xa, ya, xb, yb), Z_EGOUT_PAV,
                          {("xmax" if sx > 0 else "xmin"): PENTE_PAV, ("ymax" if sy > 0 else "ymin"): PENTE_PAV}))
        PAVILLONS.append((sx, sy, nom))


def zsurf(x, y, sauf=None):
    zz = [t.z(x, y) for t in TOITS if t is not sauf and t.dedans(x, y)]
    return max(zz) if zz else None


def cache(x, y, z, soi):
    """vrai si un autre toit passe au-dessus du point."""
    for t in TOITS:
        if t is soi or not t.dedans(x, y):
            continue
        if t.z(x, y) > z + 0.02:
            return True
    return False


log(f"faîtage corps {z_faite:.2f} m, croupes {p_bout:.1f}°")

# ---------------------------------------------------------------- tuiles
acc_tuiles = Acc()
for t in TOITS:
    t.construire(acc_tuiles)
acc_tuiles.build("toiture_tuiles", M["tuile"])

# faîtières et arêtiers : tuiles canal de recouvrement sur bain de mortier
acc_faitiere = Acc()
acc_mortier = Acc()


def tuile_faitiere(acc, P, X, Z, L=0.44, r0=0.098, r1=0.122, ep=0.016, seg=10):
    Z = (Z - X * Z.dot(X)).normalized()
    Y = Z.cross(X)
    rings = []
    for x, r in ((-L / 2, r0), (L / 2, r1)):
        rings.append([P + X * x + (Y * math.cos(math.pi * j / seg) + Z * math.sin(math.pi * j / seg)) * r
                      for j in range(seg + 1)])
    inner = [P + X * (L / 2) + (Y * math.cos(math.pi * j / seg) + Z * math.sin(math.pi * j / seg)) * (r1 - ep)
             for j in range(seg + 1)]
    n = seg + 1
    v = rings[0] + rings[1] + inner
    f = []
    for j in range(seg):
        f.append([j, j + 1, n + j + 1, n + j])
        f.append([n + j, n + j + 1, 2 * n + j + 1, 2 * n + j])
    acc.add(v, f, None, True)


nb_tuiles_f = 0
for t in TOITS:
    for A, B, s1, s2 in t.aretes():
        for a, b in seg_moins_rects(A, B, t.trous):
            A3 = Vector((a[0], a[1], t.z(*a)))
            B3 = Vector((b[0], b[1], t.z(*b)))
            if A3.z > B3.z:
                A3, B3 = B3, A3            # A3 = bas
            L = (B3 - A3).length
            if L < 0.2:
                continue
            X = (A3 - B3).normalized()     # vers le bas
            n1, n2 = t.normale(s1), t.normale(s2)
            Zb = (n1 + n2).normalized()
            c1 = Vector((*[sum(c) / len(t.faces[s1]) for c in zip(*t.faces[s1])], 0))
            c2 = Vector((*[sum(c) / len(t.faces[s2]) for c in zip(*t.faces[s2])], 0))
            l1 = n1.cross(X).normalized()
            l2 = n2.cross(X).normalized()
            mid = (A3 + B3) / 2
            if l1.to_2d().dot((c1 - mid).to_2d()) < 0:
                l1 = -l1
            if l2.to_2d().dot((c2 - mid).to_2d()) < 0:
                l2 = -l2
            # échantillonnage pour ne garder que les parties visibles
            nstep = max(2, int(L / 0.1))
            vis = []
            for i in range(nstep + 1):
                p = B3 + (A3 - B3) * (i / nstep)
                vis.append(not cache(p.x, p.y, p.z + 0.05, t))
            runs, cur = [], None
            for i, ok in enumerate(vis):
                if ok and cur is None:
                    cur = i
                if (not ok or i == nstep) and cur is not None:
                    end = i if ok else i - 1
                    if end > cur:
                        runs.append((cur / nstep, end / nstep))
                    cur = None
            for ra, rb in runs:
                PA = B3 + (A3 - B3) * ra
                PB = B3 + (A3 - B3) * rb
                # bain de mortier
                fa1, fb1 = PA + l1 * 0.17 + n1 * 0.004, PB + l1 * 0.17 + n1 * 0.004
                fa2, fb2 = PA + l2 * 0.17 + n2 * 0.004, PB + l2 * 0.17 + n2 * 0.004
                ta, tb = PA + Zb * 0.07, PB + Zb * 0.07
                quad_or(acc_mortier, [fa1, fb1, tb, ta], Zb + l1)
                quad_or(acc_mortier, [fa2, fb2, tb, ta], Zb + l2)
                # tuiles posées du bas vers le haut
                Lr = (PB - PA).length
                k = 0
                while True:
                    s = 0.21 + k * 0.37
                    if s > Lr - 0.05:
                        break
                    P = PA + (PB - PA).normalized() * s
                    tuile_faitiere(acc_faitiere, P + Zb * 0.045, X, Zb)
                    nb_tuiles_f += 1
                    k += 1
acc_faitiere.build("toiture_faitieres", M["terre"])
acc_mortier.build("toiture_mortier", M["mortier"], uvscale=1.0)
log(f"{nb_tuiles_f} tuiles faîtières")

# ================================================================ chéneaux (fonds en zinc)
ATTIQUE = [(-X_CORPS, -Y_CORPS), (-AC_N[0], -Y_CORPS), (-AC_N[0], AC_N[1]), (AC_N[0], AC_N[1]),
           (AC_N[0], -Y_CORPS), (X_CORPS, -Y_CORPS), (X_CORPS, -Y_BLOC), (X_EXT, -Y_BLOC), (X_EXT, Y_BLOC),
           (X_CORPS, Y_BLOC), (X_CORPS, Y_CORPS), (AC_S[0], Y_CORPS), (AC_S[0], AC_S[1]), (-AC_S[0], AC_S[1]),
           (-AC_S[0], Y_CORPS), (-X_CORPS, Y_CORPS), (-X_CORPS, Y_BLOC), (-X_EXT, Y_BLOC), (-X_EXT, -Y_BLOC),
           (-X_CORPS, -Y_BLOC)]
if poly_area(ATTIQUE) < 0:
    ATTIQUE = ATTIQUE[::-1]

acc_zinc = Acc()
prism(acc_zinc, offset_poly(ATTIQUE, BAL_INT - 0.02), Z_CORN + 0.02, Z_CORN + 0.07)
for sx, sy, nom in PAVILLONS:
    xa, xb = sorted((sx * (X_CORPS - 0.1), sx * (X_EXT - BAL_INT + 0.02)))
    ya, yb = sorted((sy * (Y_BLOC - 0.1), sy * (Y_PAV - BAL_INT + 0.02)))
    box(acc_zinc, xa, ya, Z_CORN_PAV + 0.02, xb, yb, Z_CORN_PAV + 0.07)

# ================================================================ balustrades et parapets
SOUCHES = TOI["souches"]


def dans_souche(x, y, m=0.08):
    for s in SOUCHES:
        hx, hy = s["section_m"][0] / 2 + m, s["section_m"][1] / 2 + m
        if abs(x - s["x"]) < hx and abs(y - s["y"]) < hy:
            return True
    return False


acc_bal = Acc()       # balustres
acc_lisse = Acc()     # socles, tablettes, dés (pierre lisse)
acc_mur = Acc()       # parapets pleins (pierre appareillée)

SEC_SOCLE = [(-0.22, 0.0), (0.22, 0.0), (0.22, 0.15), (0.20, 0.17), (0.20, 0.20), (0.17, 0.24),
             (-0.17, 0.24), (-0.20, 0.20), (-0.20, 0.17), (-0.22, 0.15)]
SEC_TABLETTE = [(-0.20, 0.80), (0.20, 0.80), (0.20, 0.82), (0.245, 0.85), (0.245, 0.92), (0.225, 0.94),
                (0.21, 0.98), (-0.21, 0.98), (-0.225, 0.94), (-0.245, 0.92), (-0.245, 0.85), (-0.20, 0.82)]
SEC_MUR = [(-0.17, 0.2), (0.17, 0.2), (0.17, 0.82), (-0.17, 0.82)]
PROF_DE = [(0.04, 0.0), (0.04, 0.17), (0.02, 0.20), (0.0, 0.24), (0.0, 0.84), (0.025, 0.86), (0.055, 0.90),
           (0.055, 0.98), (0.03, 1.0), (0.03, 1.05)]
DE = 0.25  # demi-côté du dé


def balustre_proto():
    a = Acc()
    lathe(a, [(0.068, 0.05), (0.068, 0.065), (0.052, 0.075), (0.058, 0.09), (0.044, 0.105), (0.056, 0.14),
              (0.072, 0.19), (0.076, 0.23), (0.068, 0.28), (0.048, 0.33), (0.032, 0.38), (0.031, 0.41),
              (0.046, 0.425), (0.052, 0.44), (0.036, 0.455), (0.058, 0.47), (0.064, 0.48), (0.064, 0.51)],
          seg=12, cap_bot=False, cap_top=False)
    box(a, -0.075, -0.075, 0.0, 0.075, 0.075, 0.05)
    box(a, -0.075, -0.075, 0.51, 0.075, 0.075, 0.56)
    return a


BAL = balustre_proto()


def poser_balustre(x, y, z):
    o = len(acc_bal.v)
    acc_bal.v.extend([(p[0] + x, p[1] + y, p[2] + z) for p in BAL.v])
    for fc, sm in zip(BAL.f, BAL.sm):
        acc_bal.f.append([o + k for k in fc])
        acc_bal.uv.append(None)
        acc_bal.sm.append(sm)


def de(x, y, zb):
    if dans_souche(x, y, -0.05):
        return
    sweep_rect(acc_lisse, x, y, DE, DE, [(o, zb + z) for o, z in PROF_DE], True, False)


def ligne_garde_corps(P0, P1, nin, zb, plein, des_aux_bouts=True):
    """P0, P1 : axe de la balustrade ; nin : normale vers l'intérieur."""
    P0, P1 = Vector((*P0, zb)), Vector((*P1, zb))
    L = (P1 - P0).length
    if L < 1e-3:
        return
    d = (P1 - P0) / L
    up = (0, 0, 1)
    sweep_line(acc_lisse, P0 - d * 0.0, P1, [(a, b) for a, b in SEC_SOCLE], up)
    sweep_line(acc_lisse, P0, P1, SEC_TABLETTE, up)
    if plein:
        sweep_line(acc_mur, P0, P1, SEC_MUR, up)
    k = max(1, math.ceil(L / 3.0))
    pos = [P0 + d * (L * i / k) for i in range(k + 1)]
    for i, p in enumerate(pos):
        if (i == 0 or i == k) and not des_aux_bouts:
            continue
        de(p.x, p.y, zb)
    if plein:
        return
    for i in range(k):
        a, b = pos[i], pos[i + 1]
        span = (b - a).length - 2 * DE
        n = int(span / 0.285)
        if n < 1:
            continue
        pas = span / n
        for j in range(n):
            p = a + d * (DE + pas * (j + 0.5))
            if dans_souche(p.x, p.y):
                continue
            poser_balustre(p.x, p.y, zb + 0.24)


AXE = offset_poly(ATTIQUE, BAL_RETRAIT)
nA = len(ATTIQUE)
for i in range(nA):
    a, b = ATTIQUE[i], ATTIQUE[(i + 1) % nA]
    plein = (abs(abs(a[0]) - X_EXT) < 1e-6 and abs(abs(b[0]) - X_EXT) < 1e-6) or \
            (abs(abs(a[1]) - Y_BLOC) < 1e-6 and abs(abs(b[1]) - Y_BLOC) < 1e-6 and
             min(abs(a[0]), abs(b[0])) >= X_CORPS - 1e-6)
    e = Vector((b[0] - a[0], b[1] - a[1], 0)).normalized()
    nin = Vector((-e.y, e.x, 0))
    ligne_garde_corps(AXE[i], AXE[(i + 1) % nA], nin, Z_CORN, plein)

# parapets pleins des pavillons (W04, W15)
for sx, sy, nom in PAVILLONS:
    pts = [(sx * (X_CORPS + BAL_RETRAIT), sy * (Y_CORPS - 0.15)),
           (sx * (X_CORPS + BAL_RETRAIT), sy * (Y_PAV - BAL_RETRAIT)),
           (sx * (X_EXT - BAL_RETRAIT), sy * (Y_PAV - BAL_RETRAIT)),
           (sx * (X_EXT - BAL_RETRAIT), sy * (Y_BLOC - 0.15))]
    for i in range(3):
        ligne_garde_corps(pts[i], pts[i + 1], None, Z_CORN_PAV, True, des_aux_bouts=(i == 1))
    de(*pts[1], Z_CORN_PAV)
    de(*pts[2], Z_CORN_PAV)

acc_bal.build("toiture_balustres", M["pierre"], uvscale=2.0)
acc_lisse.build("toiture_balustrade_socles_tablettes", M["pierre"], uvscale=2.0)
acc_mur.build("toiture_parapets_pleins", M["pierre_app"], uvscale=2.0)
log("balustrades")

# ================================================================ souches de cheminée
acc_souche = Acc()
acc_souche_mou = Acc()
acc_mitron = Acc()
acc_suie = Acc()
acc_solin = Acc()
z_top = Z_SOUCHE
PROF_SOUCHE_HAUT = [(0.0, z_top - 0.80), (0.03, z_top - 0.80), (0.03, z_top - 0.72), (0.0, z_top - 0.72),
                    (0.0, z_top - 0.46), (0.02, z_top - 0.46), (0.02, z_top - 0.42), (0.05, z_top - 0.39),
                    (0.09, z_top - 0.33), (0.10, z_top - 0.28), (0.10, z_top - 0.21), (0.065, z_top - 0.19),
                    (0.065, z_top - 0.16), (0.09, z_top - 0.16), (0.09, z_top - 0.07), (0.06, z_top - 0.04),
                    (0.0, z_top)]
PROF_MITRON = [(0.15, 0.0), (0.15, 0.035), (0.115, 0.06), (0.105, 0.12), (0.098, 0.30), (0.11, 0.33),
               (0.12, 0.345), (0.12, 0.37), (0.088, 0.37), (0.088, 0.25)]
for i, s in enumerate(SOUCHES):
    x, y = s["x"], s["y"]
    hx, hy = s["section_m"][0] / 2, s["section_m"][1] / 2
    sweep_rect(acc_souche, x, y, hx, hy, [(0.0, Z_CORN - 0.2), (0.0, z_top - 0.80)], False, False)
    sweep_rect(acc_souche_mou, x, y, hx, hy, PROF_SOUCHE_HAUT, True, False)
    # ouïes de ventilation sous la corniche (W04)
    for (fx, fy, lx, ly) in ((0, -1, hx, 0), (0, 1, hx, 0), (-1, 0, 0, hy), (1, 0, 0, hy)):
        long_ = 2 * (lx or ly)
        n = 3 if long_ > 1.2 else 2
        for k in range(n):
            c = -long_ / 2 + long_ * (k + 0.5) / n
            w = 0.16
            px = x + fx * (hx + 0.004) + (c if lx else 0)
            py = y + fy * (hy + 0.004) + (c if ly else 0)
            if lx:
                box(acc_suie, px - w / 2, py - 0.004, z_top - 0.69, px + w / 2, py + 0.004, z_top - 0.50)
            else:
                box(acc_suie, px - 0.004, py - w / 2, z_top - 0.69, px + 0.004, py + w / 2, z_top - 0.50)
    # mitrons (2 ou 3 selon la souche)
    nm = 3 if i % 3 == 0 else 2
    for k in range(nm):
        oy = (k - (nm - 1) / 2) * 0.36
        Mx = Matrix.Translation((x + random.uniform(-0.05, 0.05), y + oy, z_top))
        h = random.uniform(0.9, 1.15)
        lathe(acc_mitron, [(r, z * h) for r, z in PROF_MITRON], 14, Mx, True, False)
        acc_suie.add([Mx @ Vector((0.088 * math.cos(a), 0.088 * math.sin(a), 0.25 * h))
                      for a in [2 * math.pi * j / 14 for j in range(14)]], [list(range(14))])
    # solin en zinc au passage de la couverture
    zz = [zsurf(x + ax * hx, y + ay * hy) for ax in (-1, 1) for ay in (-1, 1)]
    zz = [z for z in zz if z is not None] or [Z_CORN + 0.2]
    sweep_rect(acc_solin, x, y, hx + 0.025, hy + 0.025,
               [(0, max(Z_CORN + 0.05, min(zz) - 0.03)), (0, max(zz) + 0.16), (-0.025, max(zz) + 0.18)], False)
acc_souche.build("toiture_souches", M["pierre_app"], uvscale=2.0)
acc_souche_mou.build("toiture_souches_corniches", M["pierre"], uvscale=2.0)
acc_mitron.build("toiture_mitrons", M["terre"])
acc_solin.build("toiture_solins", M["zinc"])
log("souches")

# ================================================================ verrière (lanterne vitrée à 4 pans)
acc_ver = Acc()
acc_vfer = Acc()
z_ver0 = TOITS[0].z(0, -VER_HY) - 0.12
z_mur_haut = z_faite + 0.22
hx, hy = VER_HX - 0.04, VER_HY - 0.04
# costière en zinc
sweep_rect(acc_zinc, 0, 0, VER_HX, VER_HY,
           [(0.0, z_ver0 - 0.3), (0.0, z_ver0 + 0.18), (0.035, z_ver0 + 0.18), (0.035, z_ver0 + 0.24),
            (0.0, z_ver0 + 0.24)], False)
# vitrages verticaux
for (ax, ay, bx, by) in ((-hx, -hy, hx, -hy), (hx, -hy, hx, hy), (hx, hy, -hx, hy), (-hx, hy, -hx, -hy)):
    out = Vector(((ax + bx) / 2, (ay + by) / 2, 0)).normalized()
    quad_or(acc_ver, [(ax, ay, z_ver0 + 0.24), (bx, by, z_ver0 + 0.24), (bx, by, z_mur_haut),
                      (ax, ay, z_mur_haut)], out)
    L = math.hypot(bx - ax, by - ay)
    n = max(2, round(L / 0.55))
    for k in range(n + 1):
        px, py = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
        box(acc_vfer, px - 0.025, py - 0.025, z_ver0 + 0.24, px + 0.025, py + 0.025, z_mur_haut)
# lisses horizontales
for z0, z1 in ((z_ver0 + 0.24, z_ver0 + 0.30), ((z_ver0 + z_mur_haut) / 2 + 0.2, (z_ver0 + z_mur_haut) / 2 + 0.24),
               (z_mur_haut - 0.06, z_mur_haut)):
    sweep_rect(acc_vfer, 0, 0, hx + 0.03, hy + 0.03, [(0, z0), (0, z1)], True, True)
# corniche de la lanterne
sweep_rect(acc_zinc, 0, 0, hx + 0.03, hy + 0.03,
           [(0, z_mur_haut), (0.04, z_mur_haut + 0.02), (0.07, z_mur_haut + 0.06), (0.07, z_mur_haut + 0.1),
            (0.0, z_mur_haut + 0.1)], False)
z_vt = z_mur_haut + 0.1
TV = Toit("verriere", (-hx - 0.05, -hy - 0.05, hx + 0.05, hy + 0.05), z_vt,
          {"xmin": 25, "xmax": 25, "ymin": 30, "ymax": 30})
for s, poly in TV.faces.items():
    acc_ver.add([(x, y, TV.zs(s, x, y)) for x, y in poly], [list(range(len(poly)))])
    # petits-bois
    t, g = TV.pl[s]
    axe_u = 0 if s[0] == "y" else 1
    lo = min(p[axe_u] for p in poly)
    hi = max(p[axe_u] for p in poly)
    n = max(1, round((hi - lo) / 0.5))
    for k in range(1, n):
        u = lo + (hi - lo) * k / n
        # intersection du polygone avec la droite u = cte
        pts = []
        for i in range(len(poly)):
            P, Q = poly[i], poly[(i + 1) % len(poly)]
            if (P[axe_u] - u) * (Q[axe_u] - u) < 0:
                f = (u - P[axe_u]) / (Q[axe_u] - P[axe_u])
                pts.append((P[0] + (Q[0] - P[0]) * f, P[1] + (Q[1] - P[1]) * f))
        if len(pts) == 2:
            A3 = Vector((*pts[0], TV.zs(s, *pts[0])))
            B3 = Vector((*pts[1], TV.zs(s, *pts[1])))
            sweep_line(acc_vfer, A3, B3, [(-0.018, 0.0), (0.018, 0.0), (0.018, 0.035), (-0.018, 0.035)],
                       up=TV.normale(s))
z_vfaite = TV.z(0, 0)
for A, B, s1, s2 in TV.aretes():
    A3 = Vector((*A, TV.z(*A)))
    B3 = Vector((*B, TV.z(*B)))
    nb = (TV.normale(s1) + TV.normale(s2)).normalized()
    sweep_line(acc_vfer, A3, B3, [(-0.03, -0.01), (0.03, -0.01), (0.03, 0.05), (-0.03, 0.05)], up=nb)
# crête en fer sur le faîtage de la verrière et épis d'extrémité
fa = [(A, B) for A, B, s1, s2 in TV.aretes() if abs(TV.z(*A) - TV.z(*B)) < 1e-4]
for A, B in fa:
    y0, y1 = sorted((A[1], B[1]))
    tube(acc_vfer, [(0, y0, z_vfaite + 0.13), (0, y1, z_vfaite + 0.13)], 0.012, 6)
    n = max(2, int((y1 - y0) / 0.16))
    for k in range(n + 1):
        yy = y0 + (y1 - y0) * k / n
        tube(acc_vfer, [(0, yy, z_vfaite + 0.04), (0, yy, z_vfaite + 0.22)], 0.008, 5)
        lathe(acc_vfer, [(0.001, 0.0), (0.02, 0.012), (0.024, 0.03), (0.016, 0.05), (0.001, 0.07)], 8,
              Matrix.Translation((0, yy, z_vfaite + 0.2)))
    for yy in (y0, y1):
        lathe(acc_vfer, [(0.05, 0.0), (0.05, 0.03), (0.025, 0.06), (0.02, 0.18), (0.045, 0.23), (0.05, 0.27),
                         (0.03, 0.31), (0.012, 0.36), (0.001, 0.42)], 10,
              Matrix.Translation((0, yy, z_vfaite)))
acc_ver.build("toiture_verriere_vitrages", M["verre"])
log("verrière")

# ================================================================ mât en fer forgé (épi, couronne à volutes, girouette)
acc_mat = Acc()
z0 = z_vfaite
z_epi = TOI["epi_paratonnerre"]["haut_z"]
lathe(acc_mat, [(0.13, 0.0), (0.13, 0.04), (0.09, 0.08), (0.06, 0.16), (0.05, 0.30), (0.045, 0.34)], 12,
      Matrix.Translation((0, 0, z0)))
tube(acc_mat, [(0, 0, z0 + 0.3), (0, 0, z_epi - 0.4)], 0.034, 10)
for zr in (z0 + 0.85, z0 + 2.0, z0 + 2.75):
    lathe(acc_mat, [(0.034, -0.03), (0.055, -0.015), (0.06, 0.0), (0.055, 0.015), (0.034, 0.03)], 12,
          Matrix.Translation((0, 0, zr)))
zc = z0 + 1.35
for k in range(4):
    a = math.pi / 4 + k * math.pi / 2
    e = Vector((math.cos(a), math.sin(a), 0))
    up = Vector((0, 0, 1))

    def spirale(c_r, c_z, rho0, sens=1.0, start=(0.034, 0.0), tours=1.6):
        pts = [start]
        f0 = -math.pi / 2 - 0.25
        n = 46
        for i in range(n + 1):
            f = f0 + i / n * tours * 2 * math.pi
            rho = rho0 * math.exp(-0.2 * (f - f0))
            pts.append((c_r + rho * math.cos(f), c_z + sens * rho * math.sin(f)))
        return pts

    hautes = spirale(0.25, zc + 0.18, 0.13, 1.0, (0.034, zc - 0.10))
    basses = spirale(0.17, zc - 0.32, 0.09, -1.0, (0.034, zc - 0.05))
    for crv in (hautes, basses):
        tube(acc_mat, [e * r + up * z for r, z in crv], 0.011, 6)
ring = [(0.31 * math.cos(2 * math.pi * i / 32), 0.31 * math.sin(2 * math.pi * i / 32), zc + 0.05) for i in range(32)]
tube(acc_mat, ring, 0.010, 6, closed=True)
# boule
lathe(acc_mat, [(0.001, -0.075)] + [(0.075 * math.sin(math.pi * i / 10), -0.075 * math.cos(math.pi * i / 10))
                                    for i in range(1, 10)] + [(0.001, 0.075)], 14,
      Matrix.Translation((0, 0, z0 + 2.35)))
# croisillon des points cardinaux
zcard = z0 + 2.75
for k in range(4):
    a = k * math.pi / 2
    e = Vector((math.cos(a), math.sin(a), 0))
    tube(acc_mat, [Vector((0, 0, zcard)) + e * 0.03, Vector((0, 0, zcard)) + e * 0.42], 0.010, 6)
    lathe(acc_mat, [(0.001, -0.03), (0.03, 0.0), (0.001, 0.03)], 8, Matrix.Translation(Vector((0, 0, zcard)) + e * 0.45))
# girouette (flèche et banderole)
zg = z0 + 3.15
ag = math.radians(35)
Mg = Matrix.Translation((0, 0, zg)) @ Matrix.Rotation(ag, 4, "Z")
lathe(acc_mat, [(0.045, -0.06), (0.045, 0.06)], 10, Matrix.Translation((0, 0, zg)))
tube(acc_mat, [Mg @ Vector((-0.62, 0, 0)), Mg @ Vector((0.62, 0, 0))], 0.012, 6)
plate(acc_mat, [(0.55, -0.10), (0.85, 0.0), (0.55, 0.10), (0.6, 0.0)], Mg, 0.008)
plate(acc_mat, [(-0.40, 0.0), (-0.40, 0.24), (-0.95, 0.24), (-0.80, 0.12), (-0.95, 0.0)], Mg, 0.006)
# pointe de paratonnerre
lathe(acc_mat, [(0.034, 0.0), (0.05, 0.05), (0.034, 0.1), (0.022, 0.12), (0.022, 0.25), (0.035, 0.27),
                (0.02, 0.29), (0.001, 0.4)], 10, Matrix.Translation((0, 0, z_epi - 0.4)))
log("mât")

# ================================================================ conduit métallique (bloc NE, W04/W11)
cd = TOI["conduit_metallique"]
cx, cy = cd["x"], -(Y_BLOC + 0.4)          # contre le mur du bloc est, au-dessus du pavillon NE
r = 0.125
zb = (zsurf(cx, cy) or Z_CORN_PAV + 1) - 0.1
zh = cd["haut_z"]
acc_inox2 = Acc()
tube(acc_inox2, [(cx, cy, zb), (cx, cy, zh)], r, 16)
for zz in np.arange(zb + 0.6, zh - 0.2, 1.0):
    lathe(acc_inox2, [(r + 0.002, 0), (r + 0.012, 0.01), (r + 0.012, 0.05), (r + 0.002, 0.06)], 16,
          Matrix.Translation((cx, cy, zz)))
lathe(acc_inox2, [(r + 0.03, -0.02), (r + 0.03, 0.03), (r - 0.01, 0.05)], 16, Matrix.Translation((cx, cy, zh)))
lathe(acc_inox2, [(0.001, 0.18), (0.33, 0.20), (0.32, 0.235), (0.001, 0.40)], 16,
      Matrix.Translation((cx, cy, zh)), cap_bot=False, cap_top=False)
for k in range(3):
    a = 2 * math.pi * k / 3
    tube(acc_inox2, [(cx + 0.11 * math.cos(a), cy + 0.11 * math.sin(a), zh),
                     (cx + 0.2 * math.cos(a), cy + 0.2 * math.sin(a), zh + 0.2)], 0.008, 4)
# colliers fixés au mur du bloc (y = -3,85)
for zz in (Z_CORN_PAV + 2.0, Z_CORN - 0.4):
    tube(acc_inox2, [(cx, cy + r, zz), (cx, -Y_BLOC, zz)], 0.015, 6)
    lathe(acc_inox2, [(r + 0.004, -0.03), (r + 0.004, 0.03)], 16, Matrix.Translation((cx, cy, zz)))
acc_inox2.build("toiture_conduit_inox", M["inox"])

acc_cable = Acc()
for (gx, gy) in ((cx + 1.4, -2.4), (cx - 1.6, -2.4)):
    gz = zsurf(gx, gy) or Z_EGOUT
    tube(acc_cable, [(cx, cy, zh - 0.6), (gx, gy, gz + 0.05)], 0.004, 4)
log("conduit")

# ================================================================ antenne (souche nord du milieu ouest, W04/W12)
acc_alu = Acc()
sa = SOUCHES[2]
ax_, ay_ = sa["x"] - sa["section_m"][0] / 2 - 0.06, sa["y"]
tube(acc_alu, [(ax_, ay_, z_top - 0.9), (ax_, ay_, z_top + 2.7)], 0.024, 8)
for zz in (z_top - 0.75, z_top - 0.3):
    box(acc_alu, ax_ - 0.03, ay_ - 0.05, zz, ax_ + 0.06, ay_ + 0.05, zz + 0.05)
for zz, L in ((z_top + 1.9, 1.3), (z_top + 2.45, 1.0)):
    tube(acc_alu, [(ax_, ay_, zz), (ax_ - L, ay_, zz)], 0.012, 6)
    n = 9 if L > 1.1 else 7
    for k in range(n):
        xx = ax_ - 0.12 - (L - 0.18) * k / (n - 1)
        le = 0.48 - 0.2 * k / (n - 1)
        tube(acc_alu, [(xx, ay_ - le / 2, zz), (xx, ay_ + le / 2, zz)], 0.005, 4)
for k in range(3):
    a = 2 * math.pi * k / 3 + 0.4
    gx, gy = ax_ + 2.6 * math.cos(a), ay_ + 2.6 * math.sin(a)
    gz = zsurf(gx, gy) or Z_EGOUT
    tube(acc_cable, [(ax_, ay_, z_top + 1.7), (gx, gy, gz + 0.04)], 0.0035, 4)
acc_alu.build("toiture_antenne", M["alu"])

# câbles de paratonnerre sur les pavillons (W15)
for sx, sy, nom in PAVILLONS:
    t = next(tt for tt in TOITS if tt.nom == nom)
    p0 = Vector((sx * (X_CORPS + 0.3), sy * (Y_BLOC + 0.3), 0))
    p1 = Vector((sx * (X_EXT - 0.6), sy * (Y_PAV - 0.6), 0))
    pts = []
    n = 16
    for i in range(n + 1):
        p = p0.lerp(p1, i / n)
        pts.append((p.x, p.y, t.z(p.x, p.y) + 0.07))
    pts.insert(0, (p0.x, p0.y, Z_CORN - 0.6))
    pts.append((p1.x + sx * 0.25, p1.y + sy * 0.25, Z_CORN_PAV + 1.0))
    tube(acc_cable, pts, 0.005, 4)
acc_cable.build("toiture_cables", M["fer"])

# ================================================================ descentes d'eau pluviale
acc_desc = Acc()


def descente(x, y, z_haut, z_bas, mur, sortie):
    """mur : vecteur vers le mur ; sortie : direction du dauphin."""
    rr = 0.055
    mur, sortie = Vector(mur), Vector(sortie)
    p = Vector((x, y, 0))
    # cuvette (boîte à eau)
    sweep_rect(acc_desc, x, y, 0.15, 0.15, [(-0.08, z_haut - 0.45), (0.0, z_haut - 0.2), (0.0, z_haut),
                                           (0.02, z_haut), (0.02, z_haut + 0.04)], True, True)
    tube(acc_desc, [p + Vector((0, 0, z_haut - 0.45)), p + Vector((0, 0, z_bas + 0.45)),
                    p + Vector((0, 0, z_bas + 0.2)) + sortie * 0.08, p + Vector((0, 0, z_bas + 0.08)) + sortie * 0.3],
         rr, 10)
    zz = z_haut - 1.2
    while zz > z_bas + 0.6:
        lathe(acc_desc, [(rr + 0.004, -0.03), (rr + 0.012, -0.02), (rr + 0.012, 0.02), (rr + 0.004, 0.03)], 10,
              Matrix.Translation(p + Vector((0, 0, zz))))
        tube(acc_desc, [p + Vector((0, 0, zz)), p + mur * 0.14 + Vector((0, 0, zz))], 0.012, 5)
        zz -= 2.0


for sx in (-1, 1):
    for sy in (-1, 1):
        # du chéneau de l'attique vers le toit du pavillon (W04)
        x, y = sx * (X_CORPS + 0.13), sy * (Y_CORPS - 0.35)
        zp = zsurf(x, y) or Z_CORN_PAV
        descente(x, y, Z_CORN - 0.55, zp + 0.05, (-sx, 0, 0), (sx * 0.3, sy * 0.95, 0))
        # du chéneau du pavillon au sol, dans l'angle rentrant avec le corps
        x, y = sx * (X_CORPS - 0.14), sy * (Y_CORPS + 0.13)
        descente(x, y, Z_CORN_PAV - 0.45, Z_SOL_S if sy > 0 else Z_SOL_N, (0, -sy, 0), (0, sy, 0))
acc_desc.build("toiture_descentes", M["fonte"])

acc_zinc.build("toiture_cheneaux_zinc", M["zinc"])
acc_suie.build("toiture_suie", M["suie"])
acc_vfer.build("toiture_verriere_fer", M["fer"])
acc_mat.build("toiture_mat_fer_forge", M["fer"])
log("descentes, zinc, fers")

# ================================================================ export
for o in COL.objects:
    o.select_set(True)
glb = os.path.join(EXPDIR, ID + ".glb")
kw = dict(filepath=glb, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
try:
    bpy.ops.export_scene.gltf(**kw, export_image_format="AUTO")
except TypeError:
    bpy.ops.export_scene.gltf(**kw)
log(f"GLB {os.path.getsize(glb) / 1e6:.1f} Mo")
nverts = sum(len(o.data.vertices) for o in COL.objects if o.type == "MESH")
nfaces = sum(len(o.data.polygons) for o in COL.objects if o.type == "MESH")
log(f"{nverts} sommets, {nfaces} faces")

# ================================================================ contexte de rendu (non exporté)
acc_ctx = Acc()
prism(acc_ctx, ATTIQUE, Z_SOL_N, Z_CORN - 0.5)
for sx, sy, nom in PAVILLONS:
    xa, xb = sorted((sx * X_CORPS, sx * X_EXT))
    ya, yb = sorted((sy * Y_BLOC, sy * Y_PAV))
    box(acc_ctx, xa, ya, Z_SOL_N, xb, yb, Z_CORN_PAV - 0.45)
    sweep_rect(acc_ctx, (xa + xb) / 2, (ya + yb) / 2, (xb - xa) / 2, (yb - ya) / 2,
               [(0, Z_CORN_PAV - 0.45), (0.12, Z_CORN_PAV - 0.35), (0.35, Z_CORN_PAV - 0.12),
                (0.35, Z_CORN_PAV), (0.0, Z_CORN_PAV)], True, False)
# corniche schématique de l'attique
CORN = offset_poly(ATTIQUE, -0.35)
CORN2 = offset_poly(ATTIQUE, -0.12)
prism(acc_ctx, CORN2, Z_CORN - 0.5, Z_CORN - 0.25)
prism(acc_ctx, CORN, Z_CORN - 0.25, Z_CORN)
box(acc_ctx, -3.96, 8.75, Z_SOL_S, 3.96, 11.25, 5.2)
acc_ctx.build("ctx_masse", mat("ctx_pierre", diff=TX_PIERRE, rough=0.9), CTX, 2.0, parent=None)
sol = Acc()
box(sol, -80, -80, Z_SOL_N - 0.2, 80, 80, Z_SOL_N - 0.01)
sol.build("ctx_sol", mat("ctx_sol", color=(0.62, 0.58, 0.50), rough=1.0), CTX, parent=None)

# ================================================================ rendus de contrôle
world = bpy.data.worlds.new("ciel")
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.55, 0.70, 0.92, 1)
bg.inputs["Strength"].default_value = 0.9
SC.world = world
sun = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", "SUN"))
sun.data.energy = 4.2
sun.data.angle = math.radians(1.5)
sun.rotation_euler = (math.radians(42), 0, math.radians(150))
CTX.objects.link(sun)

R = SC.render
R.engine = "BLENDER_EEVEE"
try:
    SC.eevee.taa_render_samples = 24 if RAPIDE else 48
    SC.eevee.use_shadows = True
except Exception:
    pass
try:
    SC.view_settings.view_transform = "AgX"
    SC.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
R.resolution_x, R.resolution_y = (1100, 600) if RAPIDE else (1650, 900)
R.image_settings.file_format = "PNG"
R.image_settings.color_mode = "RGB"


def camera(nom, pos, cible, lens=35, ortho=None):
    c = bpy.data.objects.new(nom, bpy.data.cameras.new(nom))
    CTX.objects.link(c)
    c.location = pos
    d = Vector(cible) - Vector(pos)
    c.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    c.data.lens = lens
    c.data.clip_end = 1000
    if ortho:
        c.data.type = "ORTHO"
        c.data.ortho_scale = ortho
    return c


VUES = [
    ("toiture", (2.0, 52.0, 47.0), (0.5, 1.5, 8.0), 35, None),            # ≈ W15 (depuis le sud)
    ("toiture_nord", (0.0, -38.0, 31.0), (0.0, -1.0, 10.5), 35, None),     # ≈ W11 (depuis le nord)
    ("toiture_dessus", (0.0, 0.0, 120.0), (0.0, 0.0, 0.0), 50, 42.0),      # ≈ W12 (zénithale)
    ("toiture_detail", (19.0, 14.0, 21.0), (6.0, 2.0, 15.0), 35, None),    # ≈ W04 (rasante)
]
for nom, pos, cible, lens, ortho in VUES:
    cam = camera("cam_" + nom, pos, cible, lens, ortho)
    if nom == "toiture_dessus":
        cam.rotation_euler = (0, 0, math.radians(-90))    # ouest en haut, nord à droite comme W12
        R.resolution_x, R.resolution_y = (900, 900)
    else:
        R.resolution_x, R.resolution_y = (1100, 600) if RAPIDE else (1650, 900)
    SC.camera = cam
    R.filepath = os.path.join(RENDIR, nom + ".png")
    bpy.ops.render.render(write_still=True)
    log("rendu " + R.filepath)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(EXPDIR, ID + ".blend"), compress=True)
log("fini")

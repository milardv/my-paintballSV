"""Composant P4.salle-a-manger et P4.bibliotheque : décor et mobilier de la salle à manger d'étage,
de la bibliothèque (au-dessus du vestibule) et du dégagement nord-ouest de l'étage.

blender -b --factory-startup --python scripts/composants/piece_reception.py
→ export/composants/piece_reception.glb, export/composants/piece_reception.blend, rendus/piece_reception_*.png

Repère D-003 : mètres, +X est, +Y sud (jardin), Z haut, RDC = 0. Pièces, portes et pivots : travail/coque.json.
Les éléments sont placés selon leur orientation réelle (mur est, mur nord…) dans ce repère ; les rendus passent
par un parent d'échelle (1, -1, 1) pour être comparés aux photos (D-026). Coque et bati sont importés pour le
contexte des rendus et ne sont pas exportés.
"""
import json
import math
import os
import random
import shutil
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

T0 = time.time()
try:
    RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    RACINE = os.path.expanduser("~/IdeaProjects/chateau-saint-victor")
ID = "piece_reception"
EXPORT = os.path.join(RACINE, "export", "composants")
TEXDIR = os.path.join(EXPORT, ID + "_textures")
RENDUS = os.path.join(RACINE, "rendus")
ASSETS = os.path.join(RACINE, "assets")
shutil.rmtree(TEXDIR, ignore_errors=True)
for d in (EXPORT, TEXDIR, RENDUS):
    os.makedirs(d, exist_ok=True)

COQUE = json.load(open(os.path.join(RACINE, "travail", "coque.json")))
PIECES = {p["id"]: p for p in COQUE["pieces"]}
random.seed(11)
RNG = np.random.RandomState(5)


def log(*a):
    print("[%s %5.1fs]" % (ID, time.time() - T0), *a)
    sys.stdout.flush()


bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
COL = bpy.data.collections.new(ID)
SC.collection.children.link(COL)
LIB = bpy.data.collections.new("sources_instances")
SC.collection.children.link(LIB)
CTX = bpy.data.collections.new("contexte_rendu")
SC.collection.children.link(CTX)


# ----------------------------------------------------------------------------------------------
# Textures procédurales (numpy) ; grain du bois depuis kitchen_wood (Poly Haven, CC0)
# ----------------------------------------------------------------------------------------------
def charger_px(chemin):
    im = bpy.data.images.load(chemin, check_existing=False)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[:, :, :3].copy()


def sauver_px(nom, arr):
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = np.clip(arr if arr.ndim == 3 else arr[:, :, None], 0, 1)
    im = bpy.data.images.new(nom, w, h, alpha=False)
    im.pixels.foreach_set(rgba.ravel())
    chemin = os.path.join(TEXDIR, nom + ".jpg")
    im.filepath_raw = chemin
    im.file_format = "JPEG"
    SC.render.image_settings.quality = 90
    im.save()
    bpy.data.images.remove(im)
    return chemin


def lum(a):
    return a[:, :, 0] * 0.3 + a[:, :, 1] * 0.59 + a[:, :, 2] * 0.11


def lisser(a, r):
    out = a.copy()
    for ax in (0, 1):
        acc = np.zeros_like(out)
        for k in range(-r, r + 1):
            acc += np.roll(out, k, axis=ax)
        out = acc / (2 * r + 1)
    return out


def normale(h, force):
    gy, gx = np.gradient(h)
    n = np.dstack([-gx * force, -gy * force, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def grille(W, H, nx, ny):
    """Coordonnées métriques (X vers la droite, Y vers le haut ; ligne 0 = bas de l'image Blender)."""
    X, Y = np.meshgrid(np.linspace(0, W, nx, dtype=np.float32), np.linspace(0, H, ny, dtype=np.float32))
    return X, Y


def melange(col, masque, c):
    m = masque.astype(np.float32)[:, :, None] if masque.dtype == bool else masque[:, :, None]
    return col * (1 - m) + np.array(c, dtype=np.float32)[None, None, :] * m


def panneau_l15(X, Y, x0, x1, y0, y1, r, fleche, rb=None):
    """Panneau chantourné Louis XV : rectangle à angles rentrants et cintre central en partie haute."""
    rb = r * 0.6 if rb is None else rb
    xc, hw = (x0 + x1) / 2, (x1 - x0) / 2
    t = np.clip((X - xc) / (0.55 * hw), -1, 1)
    yt = y1 + fleche * np.maximum(0, 1 - t ** 2) ** 1.5
    m = (X > x0) & (X < x1) & (Y > y0) & (Y < yt)
    for cx, cy, rr in ((x0, y1, r), (x1, y1, r), (x0, y0, rb), (x1, y0, rb)):
        m &= (X - cx) ** 2 + (Y - cy) ** 2 > rr ** 2
    return m


GRAIN = None


def grain_bois(n):
    """Grain de bois (luminance relative, fil horizontal) de taille n×n."""
    global GRAIN
    if GRAIN is None:
        kw = os.path.join(ASSETS, "polyhaven", "polyhaven-kitchen_wood", "kitchen_wood_diff_1k.jpg")
        L = lum(charger_px(kw))
        GRAIN = (L / L.mean()).T.copy()          # fil vertical dans la source → horizontal
    g = GRAIN
    if g.shape[0] != n:
        idx = (np.arange(n) * g.shape[0] / n).astype(int)
        g = g[idx][:, idx]
    return g


def bois(n, teinte, contraste=1.2, vertical=False):
    g = grain_bois(n)
    if vertical:
        g = g.T
    return np.array(teinte, dtype=np.float32)[None, None, :] * (g[:, :, None] ** contraste)


def parquet(nom, w, n, teinte, px=1024, contraste=1.3):
    """Parquet à bâtons rompus (lames w × n·w), tuile périodique de 2·n·w m."""
    T = 2 * n * w
    xs = (np.arange(px, dtype=np.float32) + 0.5) / px * T / w
    PX, PY = np.meshgrid(xs, xs)
    Yf = np.floor(PY)
    b = np.floor((PX - Yf) / (2 * n))
    rx = PX - Yf - 2 * b * n
    estH = rx < n
    Xf = np.floor(PX)
    dd = PY - 1 - Xf
    q = np.mod(dd, 2 * n)
    u = np.where(estH, rx, q)
    v = np.where(estH, PY - Yf, PX - Xf)
    ox = np.where(estH, Yf + 2 * b * n, Xf)
    oy = np.where(estH, Yf, PY - 1 - q)
    cle = (np.mod(np.round(ox), 2 * n) * 131 + np.mod(np.round(oy), 2 * n) * 17 + estH * 7).astype(np.int64)
    rng = np.random.RandomState(9)
    dec = rng.randint(0, 1024, (4096, 2))
    tint = rng.uniform(0.82, 1.12, 4096).astype(np.float32)
    k = cle % 4096
    g = grain_bois(1024)
    sx = ((dec[k, 0] + u * w * 900).astype(np.int64)) % 1024
    sy = ((dec[k, 1] + v * w * 900).astype(np.int64)) % 1024
    G = g[sy, sx] * tint[k]
    col = np.array(teinte, dtype=np.float32)[None, None, :] * (G[:, :, None] ** contraste)
    joint = (v < 0.035) | (v > 0.965) | (u < 0.012) | (u > n - 0.012)
    col = melange(col, joint, (0.10, 0.06, 0.03))
    h = 1 - lisser(joint.astype(np.float32), 1)
    rough = np.clip(0.42 + 0.12 * (1 - G) + 0.3 * joint, 0, 1)
    return (sauver_px(nom + "_col", col), sauver_px(nom + "_nrm", normale(h, 1.5)),
            sauver_px(nom + "_rgh", rough)), T


def bruit_periodique(X, Y, T, graine, n=10):
    rng = np.random.RandomState(graine)
    f = np.zeros_like(X)
    for _ in range(n):
        kx, ky = rng.randint(-4, 5, 2)
        if kx == 0 and ky == 0:
            continue
        a = 1.0 / math.hypot(kx, ky)
        f += a * np.sin(2 * math.pi * (kx * X + ky * Y) / T + rng.uniform(0, 6.3))
    return f


def textures():
    tex = {}
    # --- salle à manger : boiseries Louis XV vert céladon et jaune paille (P43-P51)
    MARGE, CADRE, FILET, CHAMP = (0.80, 0.83, 0.72), (0.56, 0.63, 0.49), (0.44, 0.51, 0.39), (0.93, 0.79, 0.57)
    W, H = 1.40, 3.30
    X, Y = grille(W, H, 448, 1024)
    col = np.ones(X.shape + (3,), np.float32) * np.array(MARGE, np.float32)
    hgt = np.full(X.shape, 0.4, np.float32)
    # pilastre étroit jaune à gauche
    pe = panneau_l15(X, Y, 0.04, 0.20, 0.05, H - 0.10, 0.03, 0.0)
    pi = panneau_l15(X, Y, 0.055, 0.185, 0.065, H - 0.115, 0.04, 0.0)
    col = melange(col, pe, CADRE)
    col = melange(col, pi, CHAMP)
    hgt[pe & ~pi] = 0.9
    hgt[pi] = 0.3
    # grand panneau
    x0, x1, y0, y1 = 0.30, W - 0.07, 0.07, H - 0.36
    pe = panneau_l15(X, Y, x0, x1, y0, y1, 0.11, 0.20, 0.06)
    pm = panneau_l15(X, Y, x0 + 0.03, x1 - 0.03, y0 + 0.03, y1 - 0.03, 0.14, 0.20, 0.09)
    pi = panneau_l15(X, Y, x0 + 0.045, x1 - 0.045, y0 + 0.045, y1 - 0.045, 0.155, 0.20, 0.105)
    col = melange(col, pe, CADRE)
    col = melange(col, pm & ~pi, FILET)
    col = melange(col, pi, CHAMP)
    hgt[pe & ~pm] = 1.0
    hgt[pm & ~pi] = 0.75
    hgt[pi] = 0.25
    # agrafe (coquille) au sommet du cintre
    xc, yc = (x0 + x1) / 2, y1 + 0.20
    rr = np.hypot(X - xc, (Y - yc) * 1.2)
    ang = np.arctan2(Y - yc, X - xc)
    coq = (rr < 0.11) & (Y > yc - 0.035)
    rain = 0.5 + 0.5 * np.cos(ang * 9)
    col = melange(col, coq, CADRE)
    col = col * (1 - 0.18 * (coq * (1 - rain))[:, :, None])
    hgt = np.where(coq, 1.0 + 0.3 * rain, hgt)
    L = RNG.normal(0, 1, X.shape).astype(np.float32)
    col *= (1 + 0.025 * lisser(L, 2))[:, :, None]
    tex["sam_haut"] = (sauver_px("sam_haut_col", col), sauver_px("sam_haut_nrm", normale(lisser(hgt, 1), 6.0)), None)

    W, H = 1.40, 0.85
    X, Y = grille(W, H, 448, 272)
    col = np.ones(X.shape + (3,), np.float32) * np.array(MARGE, np.float32)
    hgt = np.full(X.shape, 0.4, np.float32)
    pe = panneau_l15(X, Y, 0.04, 0.20, 0.06, H - 0.06, 0.03, 0.0)
    pi = panneau_l15(X, Y, 0.055, 0.185, 0.075, H - 0.075, 0.04, 0.0)
    col = melange(col, pe, CADRE)
    col = melange(col, pi, CHAMP)
    hgt[pe & ~pi] = 0.9
    pe = panneau_l15(X, Y, 0.30, W - 0.07, 0.10, H - 0.10, 0.06, 0.0, 0.06)
    pi = panneau_l15(X, Y, 0.33, W - 0.10, 0.13, H - 0.13, 0.09, 0.0, 0.09)
    col = melange(col, pe, CADRE)
    col = melange(col, pi, (0.82, 0.84, 0.70))
    hgt[pe & ~pi] = 1.0
    hgt[pi] = 0.3
    tex["sam_bas"] = (sauver_px("sam_bas_col", col), sauver_px("sam_bas_nrm", normale(lisser(hgt, 1), 6.0)), None)

    W, H = 1.40, 1.20
    X, Y = grille(W, H, 448, 384)
    col = np.ones(X.shape + (3,), np.float32) * np.array(MARGE, np.float32)
    hgt = np.full(X.shape, 0.4, np.float32)
    pe = panneau_l15(X, Y, 0.06, W - 0.06, 0.08, H - 0.40, 0.08, 0.26, 0.05)
    pi = panneau_l15(X, Y, 0.10, W - 0.10, 0.12, H - 0.44, 0.12, 0.26, 0.09)
    col = melange(col, pe, CADRE)
    col = melange(col, pi, (0.84, 0.86, 0.75))
    hgt[pe & ~pi] = 1.0
    hgt[pi] = 0.3
    xc, yc = W / 2, H - 0.16
    rr = np.hypot(X - xc, (Y - yc) * 1.3)
    ang = np.arctan2(Y - yc, X - xc)
    coq = (rr < 0.13) & (Y > yc - 0.05)
    rain = 0.5 + 0.5 * np.cos(ang * 11)
    col = melange(col, coq, CADRE)
    hgt = np.where(coq, 1.0 + 0.3 * rain, hgt)
    # rinceaux de part et d'autre de la coquille
    for sgn in (-1, 1):
        cx = xc + sgn * 0.26
        rr2 = np.hypot(X - cx, Y - (yc - 0.02))
        sp = (np.abs(rr2 - 0.06 - 0.02 * np.sin(np.arctan2(Y - yc, X - cx) * 1.0)) < 0.012) & (rr2 < 0.1)
        col = melange(col, sp, CADRE)
        hgt[sp] = 1.1
    tex["sam_dessus"] = (sauver_px("sam_dessus_col", col), sauver_px("sam_dessus_nrm", normale(lisser(hgt, 1), 6.0)),
                         None)

    # --- salle à manger : plafond blanc à rocailles de stuc en bordure et aux angles
    W, H = 6.2, 7.05
    X, Y = grille(W, H, 1536, 1748)
    hgt = np.zeros(X.shape, np.float32)
    # cadre mouluré intérieur chantourné
    d = 0.55
    cadre_e = panneau_l15(X, Y, d, W - d, d, H - d, 0.45, 0.0, 0.45)
    cadre_i = panneau_l15(X, Y, d + 0.05, W - d - 0.05, d + 0.05, H - d - 0.05, 0.50, 0.0, 0.50)
    hgt[cadre_e & ~cadre_i] = 0.6
    rng = np.random.RandomState(3)

    def volute(cx, cy, r0, tours, sens, ep, ampl=1.0):
        th = np.linspace(0, tours * 2 * math.pi, int(160 * tours))
        rr = r0 * np.exp(-0.22 * th)
        xs = cx + sens * rr * np.cos(th)
        ys = cy + rr * np.sin(th)
        return list(zip(xs, ys, [ep] * len(xs), [ampl] * len(xs)))

    traits = []
    for (cx, cy, sx, sy) in ((d, d, 1, 1), (W - d, d, -1, 1), (d, H - d, 1, -1), (W - d, H - d, -1, -1)):
        # cartouche d'angle : coquille et deux volutes
        traits += volute(cx + sx * 0.45, cy + sy * 0.20, 0.20, 1.6, sx, 0.022)
        traits += volute(cx + sx * 0.20, cy + sy * 0.45, 0.20, 1.6, -sx, 0.022)
        for k in range(9):
            a = math.pi / 4 + (k - 4) * 0.17
            for t in np.linspace(0.05, 0.32, 24):
                traits.append((cx + sx * t * math.cos(a), cy + sy * t * math.sin(a), 0.014, 1.0))
        for t in np.linspace(0.3, 1.4, 60):    # rinceaux le long des bords
            traits.append((cx + sx * t, cy + sy * (0.06 + 0.05 * math.sin(t * 6)), 0.012, 0.8))
            traits.append((cx + sx * (0.06 + 0.05 * math.sin(t * 6)), cy + sy * t, 0.012, 0.8))
    for (cx, cy, hor) in ((W / 2, d, True), (W / 2, H - d, True), (d, H / 2, False), (W - d, H / 2, False)):
        for s in (-1, 1):                       # agrafes au milieu des côtés
            if hor:
                traits += [(x, y, e, a) for (x, y, e, a) in volute(cx + s * 0.30, cy, 0.22, 1.4, s, 0.02)]
            else:
                traits += [(y, x, e, a) for (x, y, e, a) in volute(cy + s * 0.30, cx, 0.22, 1.4, s, 0.02)]
                traits = traits[:-1] + traits[-1:]
        for k in range(7):
            a = (k - 3) * 0.3
            for t in np.linspace(0.04, 0.22, 16):
                if hor:
                    traits.append((cx + t * math.sin(a), cy + (1 if cy < H / 2 else -1) * t * math.cos(a), 0.014, 1.0))
                else:
                    traits.append((cx + (1 if cx < W / 2 else -1) * t * math.cos(a), cy + t * math.sin(a), 0.014, 1.0))
    px_m = 1536 / W
    for (x, y, e, a) in traits:
        if not (0 < x < W and 0 < y < H):
            continue
        i, j = int(y * px_m), int(x * px_m)
        r = int(e * px_m * 1.6) + 2
        i0, i1, j0, j1 = max(0, i - r), min(X.shape[0], i + r), max(0, j - r), min(X.shape[1], j + r)
        dd = (X[i0:i1, j0:j1] - x) ** 2 + (Y[i0:i1, j0:j1] - y) ** 2
        hgt[i0:i1, j0:j1] = np.maximum(hgt[i0:i1, j0:j1], a * np.exp(-dd / (2 * (e * 0.6) ** 2)))
    hs = lisser(hgt, 1)
    ao = np.clip(1 - 0.35 * (lisser(hs, 6) - hs).clip(-1, 0) * -1 - 0.10 * hs, 0.75, 1)
    col = np.array([0.90, 0.89, 0.86], np.float32)[None, None, :] * (ao * (0.97 + 0.03 * hs))[:, :, None]
    tex["sam_plafond"] = (sauver_px("sam_plafond_col", col), sauver_px("sam_plafond_nrm", normale(hs, 10.0)), None)

    # --- bibliothèque : lambris de chêne foncé à cadres (P00-P03)
    CH = (0.25, 0.15, 0.085)
    W, H = 0.90, 3.30
    X, Y = grille(W, H, 288, 1024)
    g = bois(1024, CH, 1.3, vertical=True)[:1024, :288]
    hgt = np.full(X.shape, 0.5, np.float32)
    col = g.copy()
    for (y0, y1) in ((0.12, 0.78), (0.95, H - 0.10)):
        pe = (X > 0.09) & (X < W - 0.09) & (Y > y0) & (Y < y1)
        pi = (X > 0.13) & (X < W - 0.13) & (Y > y0 + 0.04) & (Y < y1 - 0.04)
        hgt[pe] = 0.2
        # plate-bande en biseau : du creux vers la table saillante
        bord = pe & ~pi
        dist = np.minimum.reduce([X - 0.09, W - 0.09 - X, Y - y0, y1 - Y])
        hgt[bord] = 0.2 + dist[bord] / 0.04 * 0.6
        hgt[pi] = 0.85
        col = np.where(pi[:, :, None], col * 1.08, col)
    hgt[(Y < 0.12)] = 0.5
    tex["bib_lambris"] = (sauver_px("bib_lambris_col", col), sauver_px("bib_lambris_nrm", normale(lisser(hgt, 1), 7.0)),
                          None)
    W, H = 0.90, 0.62
    X, Y = grille(W, H, 288, 198)
    col = bois(1024, CH, 1.3)[:198, :288].copy()
    hgt = np.full(X.shape, 0.5, np.float32)
    arc = ((X > 0.12) & (X < W - 0.12) & (Y > 0.10) & ((Y < H - 0.10 - 0.33) | (np.hypot(X - W / 2, Y - (H - 0.10 - 0.33)) < 0.33)))
    arc_i = ((X > 0.16) & (X < W - 0.16) & (Y > 0.14) & ((Y < H - 0.14 - 0.29) | (np.hypot(X - W / 2, Y - (H - 0.14 - 0.29)) < 0.29)))
    hgt[arc] = 0.15
    hgt[arc_i] = 0.8
    col = np.where(arc[:, :, None] & ~arc_i[:, :, None], col * 0.75, col)
    tex["bib_frise"] = (sauver_px("bib_frise_col", col), sauver_px("bib_frise_nrm", normale(lisser(hgt, 1), 7.0)), None)
    tex["bois_fonce"] = (sauver_px("bois_fonce_col", bois(512, CH, 1.3)), None, None)
    tex["noyer"] = (sauver_px("noyer_col", bois(512, (0.50, 0.30, 0.15), 1.25)), None, None)
    tex["chene_miel"] = (sauver_px("chene_miel_col", bois(512, (0.52, 0.33, 0.17), 1.25)), None, None)
    tex["acajou"] = (sauver_px("acajou_col", bois(512, (0.36, 0.17, 0.09), 1.3)), None, None)
    tex["palissandre"] = (sauver_px("palissandre_col", bois(512, (0.09, 0.045, 0.03), 1.1)), None, None)

    # --- dégagement : panneaux moulurés blancs à filets gris-vert (P10-P13)
    BL, GV = (0.90, 0.90, 0.87), (0.64, 0.70, 0.64)
    for nom, (W, H, y0, y1) in {"deg_haut": (1.2, 2.40, 0.12, 2.28), "deg_bas": (1.2, 0.85, 0.12, 0.73)}.items():
        X, Y = grille(W, H, 384, int(384 * H / W))
        col = np.ones(X.shape + (3,), np.float32) * np.array(BL, np.float32)
        hgt = np.zeros(X.shape, np.float32)
        e = (X > 0.12) & (X < W - 0.12) & (Y > y0) & (Y < y1)
        i = (X > 0.15) & (X < W - 0.15) & (Y > y0 + 0.03) & (Y < y1 - 0.03)
        col = melange(col, e & ~i, GV)
        hgt[e & ~i] = 1
        tex[nom] = (sauver_px(nom + "_col", col), sauver_px(nom + "_nrm", normale(lisser(hgt, 1), 5.0)), None)
    W, H = 0.65, 2.80
    X, Y = grille(W, H, 232, 1000)
    col = np.ones(X.shape + (3,), np.float32) * np.array(BL, np.float32)
    hgt = np.zeros(X.shape, np.float32)
    for (y0, y1) in ((0.12, 1.00), (1.12, 1.36), (1.48, 2.68)):
        e = (X > 0.08) & (X < W - 0.08) & (Y > y0) & (Y < y1)
        i = (X > 0.115) & (X < W - 0.115) & (Y > y0 + 0.035) & (Y < y1 - 0.035)
        col = melange(col, e & ~i, GV)
        hgt[e & ~i] = 1
        hgt[i] = 0.5
    tex["deg_porte"] = (sauver_px("deg_porte_col", col), sauver_px("deg_porte_nrm", normale(lisser(hgt, 1), 5.0)), None)

    # --- sols
    tex["parquet_sam"], tex["parquet_sam_T"] = parquet("parquet_sam", 0.07, 6, (0.70, 0.50, 0.30))
    tex["parquet_bib"], tex["parquet_bib_T"] = parquet("parquet_bib", 0.08, 6, (0.50, 0.30, 0.15), contraste=1.4)
    # marbre blanc en losanges à cabochons rouges (même dallage que le palier)
    a = 0.57
    T = 2 * a
    X, Y = grille(T, T, 1024, 1024)
    f = bruit_periodique(X, Y, T, 4) + 0.5 * bruit_periodique(X * 2, Y * 2, T, 8)
    veine = np.exp(-np.abs(np.sin(2 * math.pi * (X + 0.4 * Y) / T + 2.2 * f)) * 9)
    col = np.array([0.90, 0.90, 0.88], np.float32)[None, None, :] * (1 - 0.25 * veine[:, :, None])
    u, v = (X + Y) / a, (X - Y) / a
    du = np.abs(u - np.round(u)) * a / math.sqrt(2)
    dv = np.abs(v - np.round(v)) * a / math.sqrt(2)
    joint = np.minimum(du, dv) < 0.0018
    col = melange(col, joint, (0.70, 0.70, 0.68))
    cab = np.hypot(du, dv) < 0.034
    col = melange(col, cab, (0.55, 0.18, 0.13))
    rough = np.where(cab, 0.3, 0.18) + 0.25 * joint
    tex["marbre_losanges"] = (sauver_px("marbre_losanges_col", col), None, sauver_px("marbre_losanges_rgh", rough))
    tex["marbre_losanges_T"] = T
    X, Y = grille(1.0, 1.0, 512, 512)
    f = bruit_periodique(X, Y, 1.0, 12)
    veine = np.exp(-np.abs(np.sin(2 * math.pi * (X - 0.6 * Y) + 2.5 * f)) * 10)
    tex["marbre_blanc"] = (sauver_px("marbre_blanc_col",
                                     np.array([0.92, 0.91, 0.89], np.float32)[None, None, :] * (1 - 0.2 * veine[:, :, None])),
                           None, None)
    tex["marbre_rouge"] = (sauver_px("marbre_rouge_col",
                                     np.array([0.56, 0.22, 0.16], np.float32)[None, None, :] * (1 - 0.3 * veine[:, :, None]) +
                                     0.15 * veine[:, :, None] * np.array([0.9, 0.8, 0.7], np.float32)), None, None)

    # --- tapis persan fond rouge, médaillon bleu nuit (P00-P02)
    W, H = 3.4, 2.4
    X, Y = grille(W, H, 1024, 724)
    ROUGE, BLEU, ROSE, CREME = (0.52, 0.10, 0.14), (0.08, 0.09, 0.22), (0.78, 0.40, 0.45), (0.80, 0.70, 0.58)
    col = np.ones(X.shape + (3,), np.float32) * np.array(ROUGE, np.float32)
    db = np.minimum.reduce([X, W - X, Y, H - Y])
    motif = (np.sin(X * 38) * np.sin(Y * 38) + 0.6 * np.sin((X + Y) * 23) + 0.5 * np.sin((X - Y) * 31))
    col = melange(col, (motif > 0.95), BLEU)
    col = melange(col, (motif < -1.25), ROSE)
    col = melange(col, (np.abs(motif - 0.3) < 0.05), CREME)
    bord = (db > 0.06) & (db < 0.34)
    col = melange(col, bord, BLEU)
    col = melange(col, bord & (np.sin(X * 25 + Y * 25) * np.sin(X * 25 - Y * 25) > 0.45), ROSE)
    col = melange(col, (np.abs(db - 0.37) < 0.02) | (np.abs(db - 0.04) < 0.015), CREME)
    col = melange(col, db < 0.025, BLEU)
    md = np.abs(X - W / 2) / 0.85 + np.abs(Y - H / 2) / 0.62
    col = melange(col, (md < 1.0) & (md > 0.93), CREME)
    col = melange(col, (md < 0.93), BLEU)
    col = melange(col, (md < 0.93) & (motif > 0.7), ROSE)
    col = melange(col, md < 0.35, ROUGE)
    col = melange(col, md < 0.15, CREME)
    for cx, cy in ((0.62, 0.62), (W - 0.62, 0.62), (0.62, H - 0.62), (W - 0.62, H - 0.62)):
        col = melange(col, (np.abs(X - cx) + np.abs(Y - cy)) < 0.22, BLEU)
    col *= (0.9 + 0.12 * lisser(RNG.uniform(0, 1, X.shape).astype(np.float32), 1))[:, :, None]
    tex["tapis_persan"] = (sauver_px("tapis_persan_col", col), None, None)

    # --- tableaux (peints procéduralement)
    def tableau(nom, ciel, arbres, sol, motif_fontaine, graine):
        rng = np.random.RandomState(graine)
        X, Y = grille(1.0, 1.0, 384, 384)
        col = melange(np.ones(X.shape + (3,), np.float32) * np.array(sol, np.float32), Y > 0.55, ciel)
        for _ in range(70):
            cx, cy, r = rng.uniform(0, 1), rng.uniform(0.35, 0.95), rng.uniform(0.04, 0.12)
            if 0.35 < cx < 0.65 and cy < 0.7 and motif_fontaine:
                continue
            c = np.array(arbres, np.float32) * rng.uniform(0.6, 1.3)
            col = melange(col, (X - cx) ** 2 + ((Y - cy) * 1.3) ** 2 < r * r, c)
        if motif_fontaine:
            col = melange(col, (np.abs(X - 0.5) < 0.16) & (np.abs(Y - 0.25) < 0.04), (0.55, 0.55, 0.50))
            col = melange(col, (np.abs(X - 0.5) < 0.025) & (Y > 0.25) & (Y < 0.48), (0.60, 0.60, 0.56))
            col = melange(col, (X - 0.5) ** 2 + ((Y - 0.48) * 2) ** 2 < 0.004, (0.75, 0.80, 0.82))
        col *= (0.9 + 0.2 * lisser(rng.uniform(0, 1, X.shape).astype(np.float32), 2))[:, :, None]
        return (sauver_px(nom + "_col", col), None, None)
    tex["tableau_fontaine"] = tableau("tableau_fontaine", (0.55, 0.62, 0.55), (0.16, 0.24, 0.12), (0.55, 0.45, 0.28), True, 1)
    tex["tableau_paysage"] = tableau("tableau_paysage", (0.40, 0.38, 0.30), (0.10, 0.12, 0.07), (0.25, 0.20, 0.12), False, 2)
    tex["tableau_place"] = tableau("tableau_place", (0.62, 0.65, 0.60), (0.20, 0.30, 0.15), (0.62, 0.50, 0.32), True, 3)

    # --- cannage des chaises, faïence du contrecœur
    X, Y = grille(0.1, 0.1, 128, 128)
    a1 = np.abs(np.sin(X * 2 * math.pi / 0.0125))
    a2 = np.abs(np.sin(Y * 2 * math.pi / 0.0125))
    a3 = np.abs(np.sin((X + Y) * 2 * math.pi / 0.0177))
    trou = (a1 > 0.6) & (a2 > 0.6) & (a3 > 0.5)
    col = np.ones(X.shape + (3,), np.float32) * np.array([0.78, 0.58, 0.32], np.float32)
    col = melange(col, trou, (0.12, 0.08, 0.05))
    tex["cannage"] = (sauver_px("cannage_col", col), None, None)
    X, Y = grille(0.6, 0.6, 256, 256)
    col = np.ones(X.shape + (3,), np.float32) * np.array([0.20, 0.30, 0.16], np.float32)
    col *= (0.75 + 0.5 * lisser(RNG.uniform(0, 1, X.shape).astype(np.float32), 4))[:, :, None]
    j = (np.mod(X, 0.15) < 0.006) | (np.mod(Y, 0.15) < 0.006)
    col = melange(col, j, (0.55, 0.45, 0.20))
    col = melange(col, np.hypot(np.mod(X, 0.15) - 0.075, np.mod(Y, 0.15) - 0.075) < 0.03, (0.62, 0.50, 0.22))
    tex["faience"] = (sauver_px("faience_col", col), None, None)
    return tex


log("textures…")
TEX = textures()


# ----------------------------------------------------------------------------------------------
# Matériaux
# ----------------------------------------------------------------------------------------------
MATS = {}
UVS = {}


def materiau(nom, couleur=(0.8, 0.8, 0.8), rugosite=0.5, metal=0.0, tex=None, uv=1.0, emission=None,
             deux_faces=False, alpha=1.0, nrm_force=1.0):
    m = bpy.data.materials.new(ID + "_" + nom)
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (*couleur, 1)
    p.inputs["Roughness"].default_value = rugosite
    p.inputs["Metallic"].default_value = metal
    if emission:
        p.inputs["Emission Color"].default_value = (*emission[0], 1)
        p.inputs["Emission Strength"].default_value = emission[1]
    if alpha < 1.0:
        p.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    if tex:
        c, nrm, rg = tex
        ti = nt.nodes.new("ShaderNodeTexImage")
        ti.image = bpy.data.images.load(c, check_existing=True)
        nt.links.new(ti.outputs["Color"], p.inputs["Base Color"])
        if nrm:
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = bpy.data.images.load(nrm, check_existing=True)
            tn.image.colorspace_settings.name = "Non-Color"
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.inputs["Strength"].default_value = nrm_force
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
        if rg:
            tr = nt.nodes.new("ShaderNodeTexImage")
            tr.image = bpy.data.images.load(rg, check_existing=True)
            tr.image.colorspace_settings.name = "Non-Color"
            nt.links.new(tr.outputs["Color"], p.inputs["Roughness"])
    m.use_backface_culling = not deux_faces
    m.diffuse_color = (*couleur, 1)
    MATS[nom] = m
    UVS[m.name] = uv
    return m


# panneaux à UV explicites (uv = 0 : pas de projection boîte)
M_SAM_HAUT = materiau("sam_boiserie_haut", tex=TEX["sam_haut"], rugosite=0.55, uv=0)
M_SAM_BAS = materiau("sam_boiserie_bas", tex=TEX["sam_bas"], rugosite=0.55, uv=0)
M_SAM_DESSUS = materiau("sam_dessus_de_porte", tex=TEX["sam_dessus"], rugosite=0.55, uv=0)
M_SAM_PLAF = materiau("sam_plafond_stuc", tex=TEX["sam_plafond"], rugosite=0.85, uv=0)
M_SAM_VERT = materiau("sam_moulure_verte", (0.70, 0.75, 0.62), 0.5)
M_SAM_PALE = materiau("sam_vert_pale", (0.80, 0.83, 0.72), 0.55)
M_STUC = materiau("stuc_blanc", (0.88, 0.87, 0.84), 0.75)
M_BIB_LAMB = materiau("bib_lambris", tex=TEX["bib_lambris"], rugosite=0.45, uv=0)
M_BIB_FRISE = materiau("bib_frise", tex=TEX["bib_frise"], rugosite=0.45, uv=0)
M_BOIS_F = materiau("chene_fonce", tex=TEX["bois_fonce"], rugosite=0.45, uv=0.9)
M_DEG_HAUT = materiau("deg_panneau_haut", tex=TEX["deg_haut"], rugosite=0.6, uv=0)
M_DEG_BAS = materiau("deg_panneau_bas", tex=TEX["deg_bas"], rugosite=0.6, uv=0)
M_DEG_PORTE = materiau("deg_porte_placard", tex=TEX["deg_porte"], rugosite=0.4, uv=0)
M_GV = materiau("gris_vert", (0.64, 0.70, 0.64), 0.5)
M_ENDUIT = materiau("enduit_blanc", (0.90, 0.90, 0.87), 0.8)
M_PARQ_SAM = materiau("parquet_sam", tex=TEX["parquet_sam"], uv=TEX["parquet_sam_T"])
M_PARQ_BIB = materiau("parquet_bib", tex=TEX["parquet_bib"], uv=TEX["parquet_bib_T"])
M_MARB_LOS = materiau("marbre_losanges", tex=TEX["marbre_losanges"], uv=TEX["marbre_losanges_T"])
M_MARB_B = materiau("marbre_blanc", tex=TEX["marbre_blanc"], rugosite=0.2, uv=0.8)
M_MARB_R = materiau("marbre_rouge", tex=TEX["marbre_rouge"], rugosite=0.25, uv=0.8)
M_ARDOISE = materiau("ardoise", (0.16, 0.18, 0.20), 0.6)
M_FONTE = materiau("fonte_noire", (0.03, 0.03, 0.03), 0.6, 0.6)
M_TAPIS = materiau("tapis_persan", tex=TEX["tapis_persan"], rugosite=0.95, uv=0)
M_NOYER = materiau("noyer", tex=TEX["noyer"], rugosite=0.45, uv=0.8)
M_CHENE = materiau("chene_miel", tex=TEX["chene_miel"], rugosite=0.5, uv=0.8)
M_ACAJOU = materiau("acajou", tex=TEX["acajou"], rugosite=0.35, uv=0.6)
M_PALIS = materiau("palissandre_vernis", tex=TEX["palissandre"], rugosite=0.18, uv=0.6)
M_CANNE = materiau("cannage", tex=TEX["cannage"], rugosite=0.7, uv=0.1)
M_DORE = materiau("bronze_dore", (0.80, 0.58, 0.26), 0.32, 1.0)
M_LAITON = materiau("laiton_bruni", (0.62, 0.45, 0.22), 0.35, 1.0)
M_ARGENT = materiau("argent", (0.85, 0.85, 0.83), 0.2, 1.0)
M_BRONZE = materiau("bronze_brun", (0.20, 0.13, 0.07), 0.45, 0.8)
M_MIROIR = materiau("glace", (0.85, 0.87, 0.88), 0.03, 1.0)
M_VITRE = materiau("vitre_meuble", (0.30, 0.25, 0.20), 0.05, 0.0, alpha=0.18, deux_faces=True)
M_LAQUE_CREME = materiau("laque_creme", (0.86, 0.83, 0.74), 0.4)
M_LAQUE_BL = materiau("laque_blanche", (0.90, 0.90, 0.87), 0.35)
M_ROSE = materiau("velours_rose_poudre", (0.72, 0.52, 0.55), 0.9)
M_FUCHSIA = materiau("velours_fuchsia", (0.65, 0.07, 0.35), 0.85)
M_TAUPE = materiau("tissu_taupe", (0.46, 0.39, 0.33), 0.95)
M_GRIS = materiau("tissu_gris_anthracite", (0.22, 0.22, 0.23), 0.95)
M_DAMAS = materiau("tissu_damasse_creme", (0.84, 0.80, 0.68), 0.85)
M_SOIE = materiau("soie_vieux_rose", (0.55, 0.42, 0.42), 0.6, deux_faces=True)
M_VOILE = materiau("voile_blanc", (0.92, 0.92, 0.90), 0.8, deux_faces=True, alpha=0.6)
M_ABAT = materiau("abat_jour_creme", (0.90, 0.84, 0.70), 0.8, emission=((1.0, 0.85, 0.6), 0.6), deux_faces=True)
M_ABAT_ROSE = materiau("abat_jour_rose", (0.88, 0.62, 0.52), 0.8, emission=((1.0, 0.75, 0.6), 0.4), deux_faces=True)
M_CORAIL = materiau("ceramique_corail", (0.75, 0.33, 0.24), 0.25)
M_PORCEL = materiau("porcelaine_blanche", (0.92, 0.92, 0.90), 0.2)
M_BOUGIE = materiau("bougie", (0.95, 0.93, 0.88), 0.5)
M_FLAMME = materiau("ampoule_flamme", (1.0, 0.85, 0.6), 0.3, emission=((1.0, 0.80, 0.50), 6.0))
M_RADIA = materiau("radiateur_blanc", (0.88, 0.88, 0.85), 0.5, 0.2)
M_RADIA_BR = materiau("radiateur_bronze", (0.20, 0.15, 0.10), 0.5, 0.5)
M_NOIR = materiau("noir_mat", (0.02, 0.02, 0.02), 0.6)
M_ECRAN = materiau("ecran_noir", (0.01, 0.01, 0.012), 0.08)
M_TOUCHE_B = materiau("touches_ivoire", (0.88, 0.85, 0.76), 0.3)
M_FER = materiau("fer_noir", (0.03, 0.03, 0.03), 0.45, 0.6)
M_VERRE = materiau("verre_flacon", (0.55, 0.40, 0.20), 0.05, alpha=0.55)
M_VERRE_C = materiau("verre_clair", (0.85, 0.88, 0.88), 0.05, alpha=0.3)
M_FAIENCE = materiau("faience_verte", tex=TEX["faience"], rugosite=0.25, uv=0.6)
M_TABL = {k: materiau(k, tex=TEX[k], rugosite=0.6, uv=0) for k in ("tableau_fontaine", "tableau_paysage", "tableau_place")}
M_LINGE_B = materiau("linge_bleu_jean", (0.22, 0.32, 0.50), 0.95)
M_LINGE_C = materiau("linge_beige", (0.80, 0.75, 0.64), 0.95)
M_PLAID = materiau("plaid_gris", (0.32, 0.32, 0.33), 0.95)
M_FEUIL = materiau("feuillage_bouquet", (0.18, 0.32, 0.12), 0.7)
M_FLEUR_B = materiau("fleurs_blanches", (0.92, 0.92, 0.86), 0.7)
M_FLEUR_R = materiau("fleurs_rouges", (0.62, 0.06, 0.08), 0.7)
M_SECHE = materiau("fleurs_sechees", (0.78, 0.66, 0.46), 0.9)
M_POMPON = [materiau("pompon_%d" % i, c, 0.95) for i, c in
            enumerate([(0.85, 0.30, 0.45), (0.75, 0.10, 0.12), (0.92, 0.90, 0.88)])]
M_LIVRES = [materiau("reliure_%d" % i, c, 0.7) for i, c in enumerate([
    (0.42, 0.10, 0.08), (0.12, 0.16, 0.30), (0.15, 0.25, 0.14), (0.55, 0.42, 0.25), (0.82, 0.78, 0.68),
    (0.22, 0.12, 0.08), (0.60, 0.20, 0.10), (0.10, 0.10, 0.10)])]
M_RAPHIA = materiau("raphia", (0.66, 0.55, 0.36), 0.95)
M_PIERRE_STAT = M_BRONZE


# ----------------------------------------------------------------------------------------------
# Constructeur de maillages
# ----------------------------------------------------------------------------------------------
def ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
            for i in range(len(poly)))
    return list(poly) if a > 0 else list(reversed(poly))


class Bld:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []
        self.uvfix = {}

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def v(self, co):
        return self.bm.verts.new(co)

    def face(self, vs, m, lisse=False, uvs=None):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.mi(m)
        f.smooth = lisse
        if uvs:
            self.uvfix[f] = {v: uv for v, uv in zip(vs, uvs)}
        return f

    def face_orientee(self, vs, m, normale):
        """Face isolée orientée selon normale (exclue du recalcul des normales)."""
        co = [v.co for v in vs]
        nn = Vector((0, 0, 0))
        for i in range(len(co)):
            a, c = co[i], co[(i + 1) % len(co)]
            nn += Vector(((a.y - c.y) * (a.z + c.z), (a.z - c.z) * (a.x + c.x), (a.x - c.x) * (a.y + c.y)))
        if nn.dot(Vector(normale)) < 0:
            vs = list(reversed(vs))
        return self.face(vs, m, uvs=[(0, 0)] * len(vs))

    def quad_uv(self, p0, p1, p2, p3, m, u0=0, u1=1, v0=0, v1=1):
        """Quad p0 (bas gauche) → p1 (bas droite) → p2 (haut droite) → p3 (haut gauche), UV explicites."""
        vs = [self.v(p) for p in (p0, p1, p2, p3)]
        return self.face(vs, m, uvs=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    def boite(self, x0, y0, z0, x1, y1, z1, m):
        self.solide([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, m)

    def boite_c(self, cx, cy, z0, sx, sy, z1, m):
        self.boite(cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z1, m)

    def solide(self, poly, z0, z1, m, mhaut=None, mbas=None):
        poly = ccw(poly)
        b = [self.v((x, y, z0)) for x, y in poly]
        h = [self.v((x, y, z1)) for x, y in poly]
        n = len(b)
        for i in range(n):
            j = (i + 1) % n
            self.face([b[i], b[j], h[j], h[i]], m)
        self.face(list(reversed(b)), mbas or m)
        self.face(h, mhaut or m)

    def boite_o(self, c, u, v, w, m):
        """Parallélépipède centré en c, demi-axes u, v, w (Vector)."""
        c = Vector(c)
        pts = [c + sx * u + sy * v + sz * w for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
        vs = [self.v(p) for p in pts]
        for ids in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            self.face([vs[i] for i in ids], m)

    def tour(self, prof, m, c=(0, 0, 0), seg=16, sc=(1, 1)):
        """Révolution d'un profil [(r, z)] autour de Z (sc : échelle x, y de l'ellipse)."""
        cx, cy, cz = c
        anneaux = []
        for r, z in prof:
            if r <= 1e-6:
                anneaux.append([self.v((cx, cy, cz + z))])
            else:
                anneaux.append([self.v((cx + r * sc[0] * math.cos(2 * math.pi * j / seg),
                                        cy + r * sc[1] * math.sin(2 * math.pi * j / seg), cz + z))
                                for j in range(seg)])
        for i in range(len(anneaux) - 1):
            a, b = anneaux[i], anneaux[i + 1]
            for j in range(seg):
                jj = (j + 1) % seg
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    self.face([a[0], b[j], b[jj]], m, True)
                elif len(b) == 1:
                    self.face([a[j], a[jj], b[0]], m, True)
                else:
                    self.face([a[j], a[jj], b[jj], b[j]], m, True)
        if len(anneaux[0]) > 1:
            self.face(list(reversed(anneaux[0])), m)
        if len(anneaux[-1]) > 1:
            self.face(anneaux[-1], m)

    def sphere(self, c, r, m, seg=10, rings=6, sc=(1, 1, 1)):
        ret = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=rings, radius=r)
        mat = Matrix.Translation(c) @ Matrix.Diagonal((*sc, 1))
        bmesh.ops.transform(self.bm, matrix=mat, verts=ret["verts"])
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            f.material_index = self.mi(m)
            f.smooth = True

    def cylindre(self, p0, p1, r, m, seg=8, r1=None, lisse=True):
        p0, p1 = Vector(p0), Vector(p1)
        q = (p1 - p0).to_track_quat("Z", "Y")
        r1 = r if r1 is None else r1
        vs = [[self.v(p + q @ Vector((rr * math.cos(2 * math.pi * j / seg), rr * math.sin(2 * math.pi * j / seg), 0)))
               for j in range(seg)] for p, rr in ((p0, r), (p1, r1))]
        for j in range(seg):
            jj = (j + 1) % seg
            self.face([vs[0][j], vs[0][jj], vs[1][jj], vs[1][j]], m, lisse)
        self.face(list(reversed(vs[0])), m)
        self.face(vs[1], m)

    def tube(self, pts, r, m, seg=6, fermer=True):
        """Tube le long d'une polyligne 3D (rayon constant ou liste)."""
        pts = [Vector(p) for p in pts]
        rs = r if isinstance(r, (list, tuple)) else [r] * len(pts)
        anneaux = []
        ref = Vector((0, 0, 1))
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            if abs(t.dot(ref)) > 0.95:
                ref = Vector((1, 0, 0))
            a = t.cross(ref).normalized()
            bb = t.cross(a)
            anneaux.append([self.v(p + rs[i] * (math.cos(2 * math.pi * j / seg) * a + math.sin(2 * math.pi * j / seg) * bb))
                            for j in range(seg)])
        for i in range(len(anneaux) - 1):
            for j in range(seg):
                jj = (j + 1) % seg
                self.face([anneaux[i][j], anneaux[i][jj], anneaux[i + 1][jj], anneaux[i + 1][j]], m, True)
        if fermer:
            self.face(list(reversed(anneaux[0])), m)
            self.face(anneaux[-1], m)

    def balayage(self, chemin, prof, m, fermer=True):
        """chemin : [(p, a, b)] (point, axe transversal a, axe b) ; prof : [(ca, cb)] contour fermé."""
        anneaux = [[self.v(Vector(p) + ca * Vector(a) + cb * Vector(b)) for ca, cb in prof] for p, a, b in chemin]
        k = len(prof)
        for i in range(len(anneaux) - 1):
            for j in range(k):
                jj = (j + 1) % k
                self.face([anneaux[i][j], anneaux[i][jj], anneaux[i + 1][jj], anneaux[i + 1][j]], m)
        if fermer:
            self.face(list(reversed(anneaux[0])), m)
            self.face(anneaux[-1], m)

    def objet(self, nom, col=None, loc=(0, 0, 0), rot=0.0, recalc=True):
        bm = self.bm
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f not in self.uvfix])
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            if f in self.uvfix:
                mp = self.uvfix[f]
                for lp in f.loops:
                    lp[uvl].uv = mp.get(lp.vert, (0, 0))
                continue
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            s = UVS.get(self.mats[f.material_index].name, 1.0) if self.mats else 1.0
            s = s or 1.0
            for lp in f.loops:
                co = lp.vert.co
                if ax == 2:
                    uv = (co.x / s, co.y / s)
                elif ax == 0:
                    uv = (co.y / s * (1 if n.x > 0 else -1), co.z / s)
                else:
                    uv = (co.x / s * (-1 if n.y > 0 else 1), co.z / s)
                lp[uvl].uv = uv
        me = bpy.data.meshes.new(nom)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(nom, me)
        ob.location = loc
        ob.rotation_euler.z = rot
        (col or COL).objects.link(ob)
        return ob


def instance(src, nom, loc, rot=0.0, sc=1.0):
    ob = bpy.data.objects.new(nom, src.data)
    ob.location = loc
    ob.rotation_euler.z = rot
    ob.scale = (sc, sc, sc) if not isinstance(sc, tuple) else sc
    COL.objects.link(ob)
    return ob


def biseau(ob, largeur=0.006, seg=1):
    md = ob.modifiers.new("biseau", "BEVEL")
    md.width = largeur
    md.segments = seg
    md.limit_method = "ANGLE"
    return ob


def rot_vers(nx, ny):
    """Angle Z qui amène l'avant local (+Y) sur la direction (nx, ny)."""
    return math.atan2(-nx, ny)


# ----------------------------------------------------------------------------------------------
# Pièces : murs (arêtes du polygone intérieur) et ouvertures
# ----------------------------------------------------------------------------------------------
Z_ET = 5.35
FENETRES = {   # baies de façade (bati.py, D-025) et placards : (axe, coordonnée, centre, largeur, bas, haut, type)
    "salle_a_manger": [("y", 8.15, 5.25, 1.35, 0.15, 3.25, "fenetre"), ("y", 8.15, 8.85, 1.35, 0.15, 3.25, "fenetre")],
    "bibliotheque": [("y", -11.85, 0.0, 1.35, 0.15, 3.25, "fenetre"), ("x", -3.4, -10.6, 1.35, 0.15, 3.25, "fenetre"),
                     ("x", 3.4, -10.6, 1.35, 0.15, 3.25, "fenetre")],
    "degagement_no": [("y", -5.2, -9.65, 1.20, 0.0, 2.80, "placard"), ("y", -5.2, -8.30, 1.20, 0.0, 2.80, "placard")],
}


def murs(pid):
    """Liste des murs : dict(P, u, n, L, ouv=[dict(s, l, zb, zt, type, arc, nom)])."""
    p = PIECES[pid]
    poly = ccw(p["polygone_interieur"])
    res = []
    for i in range(len(poly)):
        P, Q = Vector((*poly[i], 0)), Vector((*poly[(i + 1) % len(poly)], 0))
        u = (Q - P)
        L = u.length
        u.normalize()
        n = Vector((-u.y, u.x, 0))
        w = dict(P=P, u=u, n=n, L=L, ouv=[])
        for o in p["portes"]:
            c = Vector((o["centre"][0], o["centre"][1], 0))
            ep = o["epaisseur_mur"]
            rel = c - P
            dist = rel.dot(n)
            s = rel.dot(u)
            if abs(dist + ep / 2) < 0.05 and -0.01 < s < L + 0.01:
                w["ouv"].append(dict(s=s, l=o["largeur"], zb=0.0, zt=o["hauteur"], type=o["type"],
                                     arc=o["cintree"], nom=o["nom"]))
        for (ax, coord, cen, larg, zb, zt, typ) in FENETRES[pid]:
            c = Vector((cen, coord, 0)) if ax == "y" else Vector((coord, cen, 0))
            rel = c - P
            if abs(rel.dot(n)) < 0.02 and 0 < rel.dot(u) < L:
                w["ouv"].append(dict(s=rel.dot(u), l=larg, zb=zb, zt=zt, type=typ, arc=False, nom=typ))
        w["ouv"].sort(key=lambda o: o["s"])
        res.append(w)
    return res


def pt(w, s, d, z):
    p = w["P"] + w["u"] * s + w["n"] * d
    return Vector((p.x, p.y, z))


def intervalles_libres(w, z0, z1, marge=0.0):
    """Intervalles de s où le mur est plein entre z0 et z1 (ouvertures élargies de marge)."""
    occ = sorted((o["s"] - o["l"] / 2 - marge, o["s"] + o["l"] / 2 + marge) for o in w["ouv"]
                 if o["zb"] < z1 and o["zt"] + marge > z0)
    res, cur = [], 0.0
    for a, b in occ:
        if a > cur + 1e-3:
            res.append((cur, min(a, w["L"])))
        cur = max(cur, b)
    if cur < w["L"] - 1e-3:
        res.append((cur, w["L"]))
    return [(max(0.0, a), min(w["L"], b)) for a, b in res if b - a > 0.02]


def quad_mur(b, w, s0, s1, z0, z1, m, d=0.012, u0=0, u1=1, v0=0, v1=1):
    """Quad sur le mur w (z absolus), face vers la pièce ; s croissant = droite→gauche vu de la pièce."""
    return b.quad_uv(pt(w, s1, d, z0), pt(w, s0, d, z0), pt(w, s0, d, z1), pt(w, s1, d, z1), m, u0, u1, v0, v1)


def panneaux(b, w, s0, s1, z0, z1, m, cible, zs, d=0.012, mplein=None):
    """Panneaux à UV explicites répartis entre s0 et s1 (largeur visée cible)."""
    L = s1 - s0
    if L < 0.25 and mplein is not None:
        quad_mur(b, w, s0, s1, zs + z0, zs + z1, mplein, d, 0.02, 0.05, 0.5, 0.55)
        return
    k = max(1, round(L / cible))
    for i in range(k):
        a, c = s0 + L * i / k, s0 + L * (i + 1) / k
        quad_mur(b, w, a, c, zs + z0, zs + z1, m, d)


def moulure(b, w, s0, s1, zb, prof, m, prolonge=0.0):
    """Moulure filante le long du mur : prof = [(saillie, dz)] contour fermé."""
    a0, a1 = s0 - prolonge, s1 + prolonge
    chemin = [(pt(w, a0, 0, zb), w["n"], Vector((0, 0, 1))), (pt(w, a1, 0, zb), w["n"], Vector((0, 0, 1)))]
    b.balayage(chemin, prof, m)


PROF_PLINTHE = [(0.0, 0.0), (0.022, 0.0), (0.022, 0.13), (0.012, 0.16), (0.0, 0.16)]
PROF_CIMAISE = [(0.0, 0.0), (0.018, 0.005), (0.028, 0.025), (0.018, 0.045), (0.0, 0.05)]


def prof_corniche(h, s):
    return [(0.0, 0.0), (0.02, 0.0), (0.03, 0.03), (0.30 * s, 0.30 * h), (0.55 * s, 0.45 * h), (0.75 * s, 0.75 * h),
            (s, 0.85 * h), (s, h), (0.0, h)]


def chambranle(b, w, o, zs, m, larg=0.12, sail=0.035, d=0.0):
    s0, s1 = o["s"] - o["l"] / 2, o["s"] + o["l"] / 2
    zt = o["zt"]
    prof = [(0, 0), (sail, 0), (sail, larg * 0.35), (sail * 0.7, larg * 0.7), (sail * 0.5, larg), (0, larg)]
    if o["zb"] < 0.05:
        zb = 0.0
    else:
        zb = o["zb"] - larg
    # montants : profil (saillie, largeur vers l'extérieur de la baie)
    for s, sg in ((s0, -1), (s1, 1)):
        sa = max(0.0, min(w["L"], s))
        ch = [(pt(w, sa, d, zs + zb), w["n"], w["u"] * sg), (pt(w, sa, d, zs + zt + larg), w["n"], w["u"] * sg)]
        b.balayage(ch, prof, m)
    ch = [(pt(w, max(0.0, s0 - larg), d, zs + zt), w["n"], Vector((0, 0, 1))),
          (pt(w, min(w["L"], s1 + larg), d, zs + zt), w["n"], Vector((0, 0, 1)))]
    b.balayage(ch, prof, m)
    if zb > 0:
        ch = [(pt(w, max(0.0, s0 - larg), d, zs + o["zb"]), w["n"], Vector((0, 0, -1))),
              (pt(w, min(w["L"], s1 + larg), d, zs + o["zb"]), w["n"], Vector((0, 0, -1)))]
        b.balayage(ch, prof, m)


def habiller(pid, st):
    """Revêtement des murs d'une pièce selon le style st (dict)."""
    zs = PIECES[pid]["z_sol"]
    hsp = PIECES[pid]["hauteur_sous_plafond"]
    b = Bld()
    bm = Bld()      # moulures
    for w in murs(pid):
        L = w["L"]
        # soubassement et partie haute entre ouvertures
        for (a, c) in intervalles_libres(w, 0.05, st["z_cim"], marge=st["ch_l"]):
            panneaux(b, w, a, c, 0.0, st["z_cim"], st["m_bas"], st["cible"], zs, mplein=st["m_plein"])
            moulure(bm, w, a, c, zs, PROF_PLINTHE, st["m_plinthe"], prolonge=0.022 if (a < 0.01 or c > L - 0.01) else 0)
        for (a, c) in intervalles_libres(w, st["z_cim"], st["z_haut"], marge=st["ch_l"]):
            panneaux(b, w, a, c, st["z_cim"], st["z_haut"], st["m_haut"], st["cible"], zs, mplein=st["m_plein"])
            moulure(bm, w, a, c, zs + st["z_cim"], PROF_CIMAISE, st["m_moul"],
                    prolonge=0.028 if (a < 0.01 or c > L - 0.01) else 0)
        # dessus des ouvertures
        for o in w["ouv"]:
            if o["type"] == "arcade":
                continue
            z0 = o["zt"] + st["ch_l"] + 0.01
            if z0 < st["z_haut"] - 0.15:
                s0, s1 = o["s"] - o["l"] / 2 - st["ch_l"], o["s"] + o["l"] / 2 + st["ch_l"]
                s0, s1 = max(0.0, s0), min(L, s1)
                m = st["m_dessus"] if o["type"] != "fenetre" or st.get("dessus_fen", True) else st["m_plein"]
                if o["nom"] not in st.get("sans_dessus", ()):
                    quad_mur(b, w, s0, s1, zs + z0, zs + st["z_haut"], m)
            if not (o["type"] == "arcade"):
                chambranle(bm, w, o, zs, st["m_chamb"], larg=st["ch_l"])
        # frise (bibliothèque) et corniche
        if st.get("m_frise"):
            for (a, c) in [(0.0, L)]:
                panneaux(b, w, a, c, st["z_haut"], st["z_frise"], st["m_frise"], 0.9, zs)
            moulure(bm, w, 0, L, zs + st["z_haut"] - 0.02, [(0, 0), (0.04, 0), (0.04, 0.06), (0, 0.06)], st["m_moul"],
                    prolonge=0.04)
        zc = st["z_corniche"]
        moulure(bm, w, 0, L, zs + zc, prof_corniche(st["h_corniche"], st["s_corniche"]), st["m_corniche"],
                prolonge=st["s_corniche"])
        if st.get("gorge"):
            # gorge blanche entre la corniche bois et le plafond
            g = st["gorge"]
            prof = [(0, 0), (0.02, 0), (0.06, g * 0.25), (0.14, g * 0.55), (0.26, g * 0.85), (0.32, g), (0, g)]
            moulure(bm, w, 0, L, zs + hsp - g - 0.005, prof, M_STUC, prolonge=0.32)
    ob1 = b.objet(pid_court(pid) + "_boiseries")
    ob2 = bm.objet(pid_court(pid) + "_moulures_chambranles")
    return ob1, ob2


def pid_court(pid):
    return {"salle_a_manger": "salle_a_manger", "bibliotheque": "bibliotheque", "degagement_no": "degagement_no"}[pid]


def sol_pose(pid, m, nom, dz=0.01, ep=0.012):
    p = PIECES[pid]
    b = Bld()
    b.solide(p["polygone_interieur"], p["z_sol"] + dz - ep, p["z_sol"] + dz, m)
    return b.objet(nom)


# ==============================================================================================
# Mobilier (sources locales : avant = +Y, dos à y = 0 pour les meubles adossés)
# ==============================================================================================
def pied_galbe(b, x, y, h, r, m, sx, sy, galbe=0.035):
    pts = []
    for k in range(7):
        t = k / 6
        off = galbe * math.sin(t * math.pi * 1.2) * (1 - t)
        pts.append((x + sx * off, y + sy * off, h * (1 - t)))
    b.tube(pts, [r * (0.65 + 0.35 * (1 - t)) for t in [k / 6 for k in range(7)]], m, seg=6)


def chaise_cannee(accoudoirs=False):
    b = Bld()
    W, D, hs = 0.48, 0.46, 0.46
    for sx in (-1, 1):
        pied_galbe(b, sx * (W / 2 - 0.03), D / 2 - 0.03, hs - 0.03, 0.02, M_CHENE, sx, 1)
        b.cylindre((sx * (W / 2 - 0.04), -D / 2 + 0.03, 0), (sx * (W / 2 - 0.04), -D / 2 + 0.01, hs), 0.018, M_CHENE)
        b.tube([(sx * (W / 2 - 0.04), -D / 2 + 0.01, hs), (sx * (W / 2 - 0.05), -D / 2 - 0.03, 0.70),
                (sx * (W / 2 - 0.07), -D / 2 - 0.05, 0.93)], 0.017, M_CHENE)
    # ceinture et cannage de l'assise
    b.boite(-W / 2, -D / 2, hs - 0.06, W / 2, D / 2, hs - 0.01, M_CHENE)
    b.boite(-W / 2 + 0.04, -D / 2 + 0.04, hs - 0.008, W / 2 - 0.04, D / 2 - 0.04, hs - 0.002, M_CANNE)
    # dossier : traverse chantournée et cannage
    pts = [(x, -D / 2 - 0.05 + 0.01 * (1 - (x / 0.2) ** 2), 0.93 + 0.03 * (1 - (x / 0.2) ** 2))
           for x in np.linspace(-W / 2 + 0.07, W / 2 - 0.07, 9)]
    b.tube(pts, 0.018, M_CHENE)
    b.boite_o((0, -D / 2 - 0.035, 0.73), Vector((0.16, 0, 0)), Vector((0, 0.17, 0.04)).normalized() * 0.006,
              Vector((0, -0.04, 0.17)), M_CANNE)
    b.boite(-W / 2 + 0.05, -D / 2 - 0.02, 0.53, W / 2 - 0.05, -D / 2 + 0.0, 0.56, M_CHENE)
    if accoudoirs:
        for sx in (-1, 1):
            b.tube([(sx * (W / 2 - 0.03), D / 2 - 0.04, hs), (sx * (W / 2 + 0.01), D / 2 - 0.08, 0.64),
                    (sx * (W / 2 - 0.0), -D / 2 + 0.02, 0.66), (sx * (W / 2 - 0.05), -D / 2 - 0.03, 0.70)], 0.016, M_CHENE)
    return b


def chaise_grise():
    b = Bld()
    W, D, hs = 0.47, 0.50, 0.47
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cylindre((sx * (W / 2 - 0.03), sy * (D / 2 - 0.03), 0), (sx * (W / 2 - 0.03), sy * (D / 2 - 0.03), hs - 0.08),
                       0.016, M_NOYER, r1=0.02)
    b.boite(-W / 2, -D / 2, hs - 0.09, W / 2, D / 2, hs, M_GRIS)
    b.boite_o((0, -D / 2 + 0.02, 0.73), Vector((W / 2 - 0.01, 0, 0)), Vector((0, 0.04, -0.005)),
              Vector((0, -0.03, 0.26)), M_GRIS)
    return b


def chaise_medaillon(m_tissu, m_bois=M_LAQUE_CREME, larg=0.50, accoudoirs=False, bergere=False):
    """Chaise ou fauteuil Louis XV/XVI laqué, dossier médaillon garni."""
    b = Bld()
    W, D, hs = larg, 0.50 if not bergere else 0.62, 0.44
    for sx in (-1, 1):
        pied_galbe(b, sx * (W / 2 - 0.035), D / 2 - 0.035, hs - 0.04, 0.022, m_bois, sx, 1, 0.03)
        b.cylindre((sx * (W / 2 - 0.05), -D / 2 + 0.04, 0), (sx * (W / 2 - 0.05), -D / 2 + 0.03, hs), 0.02, m_bois)
    b.boite(-W / 2, -D / 2, hs - 0.07, W / 2, D / 2, hs - 0.02, m_bois)
    # assise bombée
    b.tour([(0, 0), (0.98, 0), (1.0, 0.02), (0.9, 0.07), (0, 0.08)], m_tissu, c=(0, 0, hs - 0.03), seg=16,
           sc=((W - 0.06) / 2, (D - 0.06) / 2))
    # médaillon : anneau de bois et garniture
    cx, cz, ra, rb = 0, hs + 0.30 if not bergere else hs + 0.28, (W - 0.12) / 2, 0.24 if not bergere else 0.27
    anneau = [(cx + ra * math.cos(t), -D / 2 + 0.01 - 0.03 * (cz - hs) / 0.3, cz + rb * math.sin(t))
              for t in np.linspace(0, 2 * math.pi, 21)]
    b.tube(anneau, 0.016, m_bois, fermer=False)
    b.boite_o((0, -D / 2 + 0.01, cz), Vector((ra * 0.92, 0, 0)), Vector((0, 0.03, 0)), Vector((0, 0, rb * 0.92)), m_tissu)
    for sx in (-1, 1):
        b.cylindre((sx * (W / 2 - 0.05), -D / 2 + 0.03, hs), (sx * ra * 0.8, -D / 2 + 0.01, cz - rb * 0.7), 0.017, m_bois)
    if accoudoirs:
        for sx in (-1, 1):
            if bergere:
                b.boite_o((sx * (W / 2 - 0.05), 0.0, hs + 0.13), Vector((0.05, 0, 0)), Vector((0, D / 2 - 0.08, 0)),
                          Vector((0, 0, 0.13)), m_tissu)
            b.tube([(sx * (W / 2 - 0.035), D / 2 - 0.05, hs - 0.02), (sx * (W / 2 + 0.01), D / 2 - 0.1, 0.64),
                    (sx * (W / 2 - 0.01), -D / 2 + 0.06, 0.67), (sx * (W / 2 - 0.08), -D / 2 + 0.01, cz - 0.05)],
                   0.018, m_bois)
    return b


def table_sam(L=3.0, P=1.1, h=0.76):
    b = Bld()
    b.boite(-L / 2, -P / 2, h - 0.045, L / 2, P / 2, h, M_CHENE)
    b.boite(-L / 2 + 0.08, -P / 2 + 0.08, h - 0.14, L / 2 - 0.08, P / 2 - 0.08, h - 0.045, M_CHENE)
    for sx in (-1, 1):
        for sy in (-1, 1):
            pied_galbe(b, sx * (L / 2 - 0.12), sy * (P / 2 - 0.12), h - 0.14, 0.035, M_CHENE, sx, sy, 0.05)
    # rallonge visible (joint) au milieu
    b.boite(-0.005, -P / 2 - 0.001, h - 0.046, 0.005, P / 2 + 0.001, h + 0.001, M_NOYER)
    return b


def buffet_provencal(L=2.2, P=0.55, H=1.0):
    b = Bld()
    b.boite(-L / 2 + 0.03, 0.0, 0.16, L / 2 - 0.03, P - 0.03, H - 0.04, M_NOYER)
    b.boite(-L / 2, -0.0, H - 0.04, L / 2, P + 0.02, H, M_NOYER)
    # ceinture chantournée (profil extrudé en façade)
    prof = []
    for k in range(25):
        t = k / 24
        x = -L / 2 + 0.03 + t * (L - 0.06)
        z = 0.16 - 0.06 * abs(math.sin(t * math.pi * 3)) ** 0.7
        prof.append((x, z))
    vs_av = [b.v((x, P - 0.03, z)) for x, z in prof] + [b.v((L / 2 - 0.03, P - 0.03, 0.17)), b.v((-L / 2 + 0.03, P - 0.03, 0.17))]
    b.face_orientee(vs_av, M_NOYER, (0, 1, 0))
    for sx in (-1, 1):
        for sy in (0.04, P - 0.07):
            b.tube([(sx * (L / 2 - 0.06), sy, 0.17), (sx * (L / 2 - 0.045), sy + 0.01, 0.06), (sx * (L / 2 - 0.06), sy, 0.0)],
                   0.025, M_NOYER)
    # 4 portes à panneaux chantournés en relief, montants, entrées de serrure
    lp = (L - 0.12) / 4
    for i in range(4):
        x0 = -L / 2 + 0.06 + i * lp
        b.boite(x0 + 0.03, P - 0.03, 0.22, x0 + lp - 0.03, P - 0.012, H - 0.10, M_NOYER)
        b.boite(x0 + 0.07, P - 0.012, 0.27, x0 + lp - 0.07, P + 0.002, H - 0.15, M_ACAJOU)
        b.boite(x0 + (lp - 0.03 if i % 2 == 0 else 0.02), P - 0.012, 0.55, x0 + (lp - 0.01 if i % 2 == 0 else 0.04),
                P + 0.006, 0.62, M_LAITON)
    return b


def commode(L=1.2, P=0.55, H=0.9):
    b = Bld()
    b.boite(-L / 2 + 0.02, 0.0, 0.10, L / 2 - 0.02, P - 0.02, H - 0.03, M_NOYER)
    b.boite(-L / 2, 0.0, H - 0.03, L / 2, P + 0.01, H, M_NOYER)
    for sx in (-1, 1):
        for sy in (0.03, P - 0.05):
            b.cylindre((sx * (L / 2 - 0.05), sy, 0), (sx * (L / 2 - 0.05), sy, 0.11), 0.025, M_NOYER, r1=0.03)
    hz = (H - 0.18) / 3
    for i in range(3):
        z0 = 0.12 + i * hz
        b.boite(-L / 2 + 0.05, P - 0.02, z0 + 0.012, L / 2 - 0.05, P, z0 + hz - 0.012, M_ACAJOU)
        for sx in (-0.3, 0.3):
            b.boite_c(sx * L, P + 0.004, z0 + hz / 2 - 0.012, 0.05, 0.012, z0 + hz / 2 + 0.012, M_LAITON)
        b.boite_c(0, P + 0.004, z0 + hz / 2 + 0.02, 0.025, 0.01, z0 + hz / 2 + 0.05, M_LAITON)
    return b


def radiateur(L, H, m, P=0.18):
    b = Bld()
    n = max(4, int(L / 0.06))
    for i in range(n):
        x = -L / 2 + (i + 0.5) * L / n
        b.boite(x - L / n * 0.38, 0.06, 0.12, x + L / n * 0.38, 0.06 + P, H, m)
    b.boite(-L / 2, 0.06 + P * 0.35, 0.16, L / 2, 0.06 + P * 0.65, H - 0.05, m)
    for x in (-L / 2 + 0.03, L / 2 - 0.03):
        b.boite_c(x, 0.06 + P / 2, 0.0, 0.03, P * 0.6, 0.13, m)
    return b


def lampe(b, c, h, m_pied, m_abat, ra=0.14, forme="balustre"):
    x, y, z = c
    if forme == "balustre":
        prof = [(0.06, 0), (0.07, 0.02), (0.03, 0.05), (0.025, h * 0.3), (0.05, h * 0.45), (0.025, h * 0.6),
                (0.012, h * 0.62), (0.008, h * 0.75), (0, h * 0.75)]
    elif forme == "boule":
        prof = [(0.05, 0), (0.06, 0.02), (0.10, h * 0.2), (0.11, h * 0.32), (0.07, h * 0.48), (0.02, h * 0.52),
                (0.008, h * 0.75), (0, h * 0.75)]
    else:   # colonne
        prof = [(0.05, 0), (0.05, 0.02), (0.02, 0.03), (0.02, h * 0.72), (0, h * 0.72)]
    b.tour(prof, m_pied, c=(x, y, z), seg=12)
    seg = 16
    b.tour([(ra, h * 0.62), (ra * 0.62, h * 1.0), (ra * 0.6, h * 1.0), (ra * 0.98, h * 0.62)], m_abat,
           c=(x, y, z), seg=seg)


def tableau(b, w, s, zc, larg, haut, m_toile, prof=0.04, cadre=0.07, d=0.015):
    """Tableau à cadre doré accroché au mur w, centré en s, hauteur zc (absolue)."""
    n, u = w["n"], w["u"]
    c = pt(w, s, d + prof / 2, zc)
    b.boite_o(c, u * (larg / 2 + cadre), n * prof / 2, Vector((0, 0, haut / 2 + cadre)), M_DORE)
    p = pt(w, s, d + prof + 0.002, zc)
    b.quad_uv(p + u * larg / 2 - Vector((0, 0, haut / 2)), p - u * larg / 2 - Vector((0, 0, haut / 2)),
              p - u * larg / 2 + Vector((0, 0, haut / 2)), p + u * larg / 2 + Vector((0, 0, haut / 2)), m_toile)


def rideau(b, w, s0, s1, ztop, zs, plis=7, d=0.14, m=M_SOIE, embrasse=None):
    """Rideau plissé suspendu à ztop (absolu), de s0 à s1 ; embrasse : (s_serré, z_relatif)."""
    nu, nz = plis * 4, 14
    s0, s1 = max(0.03, s0), min(w["L"] - 0.03, s1)
    grid = []
    for j in range(nz + 1):
        z = zs + 0.02 + (ztop - zs - 0.02) * j / nz
        rows = []
        for i in range(nu + 1):
            t = i / nu
            s = s0 + (s1 - s0) * t
            if embrasse:
                se, ze = embrasse
                f = math.exp(-((z - zs - ze) / 0.5) ** 2) * 0.75
                s = s + (se - s) * f
            dd = d + 0.04 * math.sin(t * plis * 2 * math.pi)
            rows.append(b.v(pt(w, s, dd, z)))
        grid.append(rows)
    for j in range(nz):
        for i in range(nu):
            b.face([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]], m, True)


def tringle(b, w, s0, s1, z, d=0.14):
    s0, s1 = max(0.06, s0), min(w["L"] - 0.06, s1)
    ch = [pt(w, s0, d, z), pt(w, s1, d, z)]
    b.cylindre(ch[0], ch[1], 0.014, M_LAITON, seg=8)
    for s in (s0, s1):
        b.sphere(pt(w, s + (-0.03 if s == s0 else 0.03), d, z), 0.03, M_LAITON, seg=8, rings=5)
        b.cylindre(pt(w, s + (0.03 if s == s0 else -0.03), 0, z), pt(w, s + (0.03 if s == s0 else -0.03), d, z), 0.008,
                   M_LAITON, seg=6)


def lustre(b, c, n_bas, n_haut, r_bas, haut, m, chaine, style="rocaille"):
    """Lustre à bras porte-bougies : c = point d'accroche du bas du fût (absolu)."""
    x, y, z = c
    if style == "rocaille":
        prof = [(0, -0.20), (0.03, -0.18), (0.06, -0.10), (0.08, -0.02), (0.05, 0.02), (0.03, 0.10),
                (0.05, 0.20), (0.03, 0.30), (0.02, 0.45), (0.04, 0.55), (0.015, 0.62), (0.015, haut), (0, haut)]
    else:   # hollandais : boule et balustres
        prof = [(0, -0.22), (0.02, -0.21), (0.03, -0.17), (0.0, -0.17)]
        prof = [(0, -0.24), (0.025, -0.22), (0.02, -0.18), (0.09, -0.12), (0.12, -0.02), (0.09, 0.06), (0.03, 0.10),
                (0.04, 0.18), (0.02, 0.26), (0.04, 0.34), (0.015, 0.40), (0.015, haut), (0, haut)]
    b.tour(prof, m, c=(x, y, z), seg=12)
    b.cylindre((x, y, z + haut), (x, y, z + haut + chaine), 0.008, m, seg=6)
    b.tour([(0.02, 0), (0.13, 0.0), (0.10, 0.03), (0.0, 0.04)], m, c=(x, y, z + haut + chaine - 0.04), seg=12)
    flammes = []
    for (n, r, zb, dz) in ((n_bas, r_bas, 0.0, 0.12), (n_haut, r_bas * 0.6, 0.25, 0.12)):
        for k in range(n):
            a = 2 * math.pi * (k + (0.5 if zb > 0 else 0)) / max(n, 1)
            ca, sa = math.cos(a), math.sin(a)
            pts = []
            for i in range(9):
                t = i / 8
                rr = 0.05 + (r - 0.05) * t
                zz = zb - 0.05 + 0.10 * math.sin(t * math.pi * 1.4) - 0.06 * t + dz * t ** 3
                pts.append((x + rr * ca, y + rr * sa, z + zz))
            b.tube(pts, 0.011, m, seg=5)
            if style == "rocaille":     # feuillage : volute sous le bras
                b.tube([(x + (0.06 + r * 0.4 * t) * ca, y + (0.06 + r * 0.4 * t) * sa,
                         z + zb - 0.06 - 0.08 * math.sin(t * math.pi)) for t in np.linspace(0, 1, 6)], 0.008, m, seg=4)
            px, py, pz = pts[-1]
            b.tour([(0.01, 0), (0.045, 0.01), (0.05, 0.025), (0.012, 0.025)], m, c=(px, py, pz), seg=8)
            b.cylindre((px, py, pz + 0.02), (px, py, pz + 0.13), 0.011, M_BOUGIE, seg=6)
            b.sphere((px, py, pz + 0.15), 0.013, M_FLAMME, seg=6, rings=4, sc=(1, 1, 1.5))
            flammes.append((px, py, pz + 0.15))
    return flammes


# ==============================================================================================
# SALLE À MANGER (P43-P46, P50, P51) — x 4,3→10,5 ; y 1,1 (nord, galerie) → 8,15 (sud, façade)
# ==============================================================================================
log("salle à manger…")
P = "salle_a_manger"
ZS = PIECES[P]["z_sol"]
HSP = PIECES[P]["hauteur_sous_plafond"]
X0, X1, Y0, Y1 = 4.3, 10.5, 1.1, 8.15
sol_pose(P, M_PARQ_SAM, "salle_a_manger_parquet")
habiller(P, dict(z_cim=0.92, z_haut=HSP - 0.30, z_corniche=HSP - 0.30, h_corniche=0.30, s_corniche=0.22,
                 m_bas=M_SAM_BAS, m_haut=M_SAM_HAUT, m_dessus=M_SAM_DESSUS, m_plein=M_SAM_PALE, m_plinthe=M_SAM_VERT,
                 m_moul=M_SAM_VERT, m_chamb=M_SAM_PALE, m_corniche=M_STUC, cible=1.35, ch_l=0.11))
# plafond à rocailles (1 cm sous le plafond de coque)
b = Bld()
zp = ZS + HSP - 0.01
b.quad_uv((X0, Y0, zp), (X1, Y0, zp), (X1, Y1, zp), (X0, Y1, zp), M_SAM_PLAF)
ob = b.objet("salle_a_manger_plafond_stuc", recalc=False)
me = ob.data             # normales vers le bas : on retourne le quad
bm_ = bmesh.new()
bm_.from_mesh(me)
bmesh.ops.reverse_faces(bm_, faces=bm_.faces[:], flip_multires=False)
bm_.to_mesh(me)
bm_.free()

MURS_SAM = {}
for w in murs(P):
    n = w["n"]
    cle = "nord" if n.y > 0.9 else "sud" if n.y < -0.9 else "ouest" if n.x > 0.9 else "est"
    MURS_SAM[cle] = w


def s_de(w, x=None, y=None):
    """Abscisse s sur le mur w du point de coordonnée x (mur parallèle à X) ou y."""
    p = Vector((x if x is not None else w["P"].x, y if y is not None else w["P"].y, 0))
    return (p - w["P"]).dot(w["u"])


# --- cheminée Louis XVI en marbre blanc (mur ouest, x = 4,3), trumeau doré
wo = MURS_SAM["ouest"]
YC = 4.35
b = Bld()
s = s_de(wo, y=YC)
c0 = pt(wo, s, 0, ZS)
u, n = wo["u"], wo["n"]
Z = Vector((0, 0, 1))


def bo(bld, s_, d0, d1, z0, z1, w_, m, ds=None):
    """Boîte alignée sur le mur w_ : de s_±ds/2, profondeur d0→d1, z0→z1 (relatifs au sol)."""
    a = pt(w_, s_, (d0 + d1) / 2, ZS + (z0 + z1) / 2)
    bld.boite_o(a, w_["u"] * ds / 2, w_["n"] * (d1 - d0) / 2, Vector((0, 0, (z1 - z0) / 2)), m)


L_CH, H_CH = 1.40, 1.10
for sg in (-1, 1):   # jambages à consoles
    bo(b, s + sg * (L_CH / 2 - 0.10), 0.0, 0.30, 0.0, H_CH - 0.26, wo, M_MARB_B, ds=0.20)
    bo(b, s + sg * (L_CH / 2 - 0.10), 0.0, 0.34, H_CH - 0.30, H_CH - 0.05, wo, M_MARB_B, ds=0.17)
    bo(b, s + sg * (L_CH / 2 - 0.10), 0.30, 0.325, 0.1, H_CH - 0.32, wo, M_MARB_B, ds=0.10)
bo(b, s, 0.0, 0.32, H_CH - 0.26, H_CH - 0.05, wo, M_MARB_B, ds=L_CH - 0.30)      # linteau (frise)
bo(b, s, 0.0, 0.40, H_CH - 0.05, H_CH, wo, M_MARB_B, ds=L_CH + 0.14)             # tablette
for k in range(9):                                                                 # guirlande de la frise
    t = k / 8
    ss = s - 0.35 + 0.7 * t
    b.sphere(pt(wo, ss, 0.33, ZS + H_CH - 0.13 - 0.06 * math.sin(t * math.pi)), 0.025, M_MARB_B, seg=6, rings=4)
bo(b, s, 0.0, 0.06, 0.0, H_CH - 0.26, wo, M_FONTE, ds=L_CH - 0.40)                # plaque de fonte
bo(b, s, 0.06, 0.28, 0.0, 0.02, wo, M_FONTE, ds=L_CH - 0.40)
b.objet("salle_a_manger_cheminee")
b = Bld()                                                                          # devant de foyer
bo(b, s, 0.30, 0.82, -0.008, 0.012, wo, M_MARB_B, ds=1.60)
for k in range(3):
    bo(b, s - 0.45 + k * 0.45, 0.40, 0.72, 0.012, 0.014, wo, M_ARDOISE, ds=0.36)
b.objet("salle_a_manger_devant_foyer")
b = Bld()                                                                          # trumeau-miroir doré
bo(b, s, 0.01, 0.06, H_CH + 0.02, H_CH + 2.15, wo, M_DORE, ds=1.25)
bo(b, s, 0.06, 0.065, H_CH + 0.10, H_CH + 2.07, wo, M_MIROIR, ds=1.09)
b.sphere(pt(wo, s, 0.06, ZS + H_CH + 2.17), 0.07, M_DORE, seg=8, rings=5, sc=(1.5, 0.5, 1))
# garniture de cheminée : bougeoir, lampe colonne, photophore
lampe(b, pt(wo, s + 0.55, 0.22, ZS + H_CH), 0.50, M_ARGENT, M_ABAT, ra=0.10, forme="colonne")
b.tour([(0.04, 0), (0.05, 0.01), (0.012, 0.03), (0.01, 0.22), (0.03, 0.24), (0.0, 0.25)], M_ARGENT,
       c=tuple(pt(wo, s - 0.45, 0.2, ZS + H_CH)), seg=10)
b.cylindre(pt(wo, s - 0.45, 0.2, ZS + H_CH + 0.24), pt(wo, s - 0.45, 0.2, ZS + H_CH + 0.36), 0.012, M_BOUGIE, seg=6)
b.tour([(0.07, 0), (0.075, 0.02), (0.07, 0.24), (0.05, 0.27), (0.0, 0.28)], M_VERRE_C,
       c=tuple(pt(wo, s - 0.15, 0.2, ZS + H_CH)), seg=12)
b.objet("salle_a_manger_trumeau_garniture")
# petit tableau à droite du trumeau (P43 : mur de la cheminée)
b = Bld()
tableau(b, wo, s - 1.0, ZS + 1.95, 0.32, 0.26, M_TABL["tableau_paysage"], cadre=0.05)
b.objet("salle_a_manger_petit_tableau")

# chaises de part et d'autre de la cheminée (crème : médaillon à droite, Louis-Philippe à gauche)
ch_med = chaise_medaillon(M_DAMAS).objet("salle_a_manger_chaise_medaillon",
                                         loc=tuple(pt(wo, s + 1.05, 0.45, ZS)), rot=rot_vers(*n[:2]) - 0.35)
b = chaise_medaillon(M_DAMAS, m_bois=M_ACAJOU, larg=0.46)
b.boite(-0.18, -0.15, 0.45, 0.18, 0.12, 0.52, M_PLAID)
b.objet("salle_a_manger_chaise_louis_philippe", loc=tuple(pt(wo, s - 1.05, 0.45, ZS)), rot=rot_vers(*n[:2]) + 0.3)

# --- buffet provençal (mur nord), tableau fontaine, lampes, service à thé
wn = MURS_SAM["nord"]
XB = 7.55
s = s_de(wn, x=XB)
buffet_provencal().objet("salle_a_manger_buffet", loc=tuple(pt(wn, s, 0.01, ZS)), rot=rot_vers(*wn["n"][:2]))
b = Bld()
tableau(b, wn, s, ZS + 2.25, 0.80, 1.00, M_TABL["tableau_fontaine"])
zb_ = ZS + 1.0
lampe(b, pt(wn, s - 0.85, 0.30, zb_), 0.62, M_CORAIL, M_ABAT_ROSE, ra=0.20, forme="boule")
lampe(b, pt(wn, s + 0.85, 0.30, zb_), 0.60, M_BRONZE, M_ABAT, ra=0.12, forme="balustre")
for k, (dx, h, r) in enumerate(((-0.10, 0.22, 0.05), (0.05, 0.16, 0.045), (0.17, 0.12, 0.04))):
    b.tour([(0.03, 0), (r, 0.03), (r, h * 0.7), (r * 0.5, h), (0.01, h + 0.02), (0, h + 0.02)], M_ARGENT,
           c=tuple(pt(wn, s + dx, 0.30, zb_ + 0.01)), seg=12)
b.boite_o(pt(wn, s + 0.04, 0.30, zb_ + 0.005), wn["u"] * 0.25, wn["n"] * 0.16, Vector((0, 0, 0.005)), M_ARGENT)
b.tour([(0.0, 0), (0.17, 0), (0.17, 0.01), (0.0, 0.01)], M_RAPHIA, c=tuple(pt(wn, s - 0.45, 0.30, zb_)), seg=16)
for dx in (-0.3, 0.35):
    b.tour([(0.04, 0), (0.035, 0.02), (0.01, 0.05), (0.012, 0.18), (0.025, 0.2), (0, 0.2)], M_VERRE_C,
           c=tuple(pt(wn, s + dx, 0.18, zb_)), seg=10)
b.objet("salle_a_manger_buffet_garniture")

# --- desserte ronde (bar) dans l'angle nord-est, bouteilles
b = Bld()
cx, cy = 9.85, 1.45
b.tour([(0.25, 0.73), (0.25, 0.75), (0.0, 0.75)], M_ACAJOU, c=(cx, cy, ZS), seg=20)
b.tour([(0.0, 0.73), (0.25, 0.73)], M_ACAJOU, c=(cx, cy, ZS), seg=20)
b.tour([(0.21, 0.30), (0.21, 0.32), (0.0, 0.32), (0.0, 0.30)], M_ACAJOU, c=(cx, cy, ZS), seg=20)
for k in range(3):
    a = 2 * math.pi * k / 3
    b.cylindre((cx + 0.21 * math.cos(a), cy + 0.21 * math.sin(a), ZS), (cx + 0.23 * math.cos(a), cy + 0.23 * math.sin(a), ZS + 0.74),
               0.015, M_ACAJOU)
rng = random.Random(4)
for k in range(10):
    a, r = rng.uniform(0, 6.28), rng.uniform(0.02, 0.17)
    h = rng.uniform(0.22, 0.32)
    b.tour([(0.035, 0), (0.035, h * 0.65), (0.012, h * 0.85), (0.012, h), (0, h)], M_VERRE if k % 3 else M_VERRE_C,
           c=(cx + r * math.cos(a), cy + r * math.sin(a), ZS + 0.75), seg=8)
b.objet("salle_a_manger_desserte_bar")

# --- mur sud : commode entre les portes-fenêtres, tableau, rideaux, tringles, radiateurs
ws = MURS_SAM["sud"]
s = s_de(ws, x=7.05)
commode().objet("salle_a_manger_commode", loc=tuple(pt(ws, s, 0.01, ZS)), rot=rot_vers(*ws["n"][:2]))
b = Bld()
tableau(b, ws, s, ZS + 1.85, 0.70, 0.55, M_TABL["tableau_place"])
lampe(b, pt(ws, s + 0.40, 0.30, ZS + 0.9), 0.48, M_BRONZE, M_ABAT, ra=0.11)
b.boite_o(pt(ws, s - 0.25, 0.28, ZS + 0.96), ws["u"] * 0.14, ws["n"] * 0.08, Vector((0, 0, 0.06)), M_NOIR)
b.objet("salle_a_manger_commode_garniture")
b = Bld()
for xf in (5.25, 8.85):
    sf = s_de(ws, x=xf)
    a0, a1 = sf - 0.675, sf + 0.675
    tringle(b, ws, a0 - 0.30, a1 + 0.30, ZS + 3.62)
    rideau(b, ws, a0 - 0.36, a0 + 0.05, ZS + 3.60, ZS, plis=5, embrasse=(a0 - 0.26, 1.05))
    rideau(b, ws, a1 - 0.05, a1 + 0.36, ZS + 3.60, ZS, plis=5, embrasse=(a1 + 0.26, 1.05))
b.objet("salle_a_manger_rideaux_tringles")
rad = radiateur(0.5, 0.8, M_RADIA).objet("salle_a_manger_src_radiateur", col=LIB)
instance(rad, "salle_a_manger_radiateur", tuple(pt(ws, s_de(ws, x=10.02), 0.0, ZS)), rot_vers(*ws["n"][:2]))
# tabouret d'appoint devant la porte-fenêtre est (P45)
b = Bld()
b.tour([(0.17, 0.58), (0.17, 0.60), (0, 0.60)], M_NOYER, c=(9.45, 7.45, ZS), seg=16)
for k in range(3):
    a = 2 * math.pi * k / 3 + 0.3
    b.cylindre((9.45 + 0.13 * math.cos(a), 7.45 + 0.13 * math.sin(a), ZS), (9.45 + 0.1 * math.cos(a), 7.45 + 0.1 * math.sin(a), ZS + 0.59),
               0.014, M_NOYER)
b.objet("salle_a_manger_tabouret")

# --- table et chaises (cannées et grises), linge plié
TX, TY = 7.45, 4.75
table_sam().objet("salle_a_manger_table", loc=(TX, TY, ZS))
b = Bld()
b.boite_c(TX + 0.55, TY + 0.15, ZS + 0.76, 0.42, 0.32, ZS + 0.80, M_LINGE_C)
b.boite_c(TX + 0.57, TY + 0.13, ZS + 0.80, 0.40, 0.30, ZS + 0.83, M_LINGE_B)
b.objet("salle_a_manger_linge_plie")
src_cannee = chaise_cannee().objet("salle_a_manger_src_chaise_cannee", col=LIB)
src_cannee_acc = chaise_cannee(True).objet("salle_a_manger_src_chaise_cannee_accoudoirs", col=LIB)
src_grise = chaise_grise().objet("salle_a_manger_src_chaise_grise", col=LIB)
PLACES = []
for i, dx in enumerate((-1.08, -0.36, 0.36, 1.08)):
    PLACES.append((TX + dx, TY - 0.78, (0, 1)))      # côté nord, regard vers le sud
    PLACES.append((TX + dx, TY + 0.78, (0, -1)))     # côté sud
PLACES.append((TX - 1.82, TY, (1, 0)))
PLACES.append((TX + 1.82, TY, (-1, 0)))
TYPES = [src_cannee, src_cannee, src_grise, src_cannee, src_cannee, src_cannee, src_cannee_acc, src_grise,
         src_grise, src_grise]
rng = random.Random(8)
for k, ((x, y, f), src) in enumerate(zip(PLACES, TYPES)):
    instance(src, "salle_a_manger_chaise.%02d" % k, (x + rng.uniform(-0.04, 0.04), y + rng.uniform(-0.03, 0.05), ZS),
             rot_vers(*f) + rng.uniform(-0.08, 0.08))
# veste noire posée sur la chaise grise en bout de table (P45)
b = Bld()
b.boite_o((TX + 1.97, TY, ZS + 0.80), Vector((0.03, 0, -0.01)), Vector((0, 0.22, 0)), Vector((0.01, 0, 0.22)), M_NOIR)
b.boite_c(TX + 1.86, TY, ZS + 0.47, 0.38, 0.44, ZS + 0.50, M_NOIR)
b.objet("salle_a_manger_veste")

# --- lustre bronze doré rocaille 12 bras, rosace, lumière
b = Bld()
zl = ZS + HSP - 1.55
fl = lustre(b, (TX, TY, zl), 8, 4, 0.40, 0.75, M_DORE, chaine=1.55 - 0.75 - 0.02)
b.tour([(0.0, 0), (0.30, 0), (0.28, -0.03), (0.18, -0.05), (0.06, -0.07), (0, -0.07)], M_STUC,
       c=(TX, TY, ZS + HSP - 0.011), seg=20)
b.objet("salle_a_manger_lustre")


def lumiere(nom, c, w, rayon=0.25, couleur=(1.0, 0.82, 0.60)):
    li = bpy.data.lights.new(nom, "POINT")
    li.energy = w
    li.color = couleur
    li.shadow_soft_size = rayon
    ob = bpy.data.objects.new(nom, li)
    ob.location = c
    COL.objects.link(ob)
    return ob


lumiere("lumiere_salle_a_manger_lustre", (TX, TY, zl + 0.08), 320, 0.35)


# ==============================================================================================
# BIBLIOTHÈQUE (P00-P03) — x ±3,7 (±3,4 au nord de y = -8,15) ; y -5,55 (sud, palier) → -9,35 (nord)
# ==============================================================================================
log("bibliothèque…")
P = "bibliotheque"
ZS = PIECES[P]["z_sol"]
HSP = PIECES[P]["hauteur_sous_plafond"]
sol_pose(P, M_PARQ_BIB, "bibliotheque_parquet")
habiller(P, dict(z_cim=0.90, z_haut=3.30, z_frise=3.92, z_corniche=3.92, h_corniche=0.14, s_corniche=0.10,
                 m_bas=M_BIB_LAMB, m_haut=M_BIB_LAMB, m_dessus=M_BIB_LAMB, m_plein=M_BOIS_F, m_plinthe=M_BOIS_F,
                 m_moul=M_BOIS_F, m_chamb=M_BOIS_F, m_corniche=M_BOIS_F, m_frise=M_BIB_FRISE, cible=0.9, ch_l=0.12,
                 gorge=0.73))
# Le lambris bas et haut partagent la même texture : on ne garde qu'une hauteur de panneau → les panneaux
# bas (0→0,9) utilisent le bas de la texture (UV), voir correction ci-dessous.
ob = bpy.data.objects["bibliotheque_boiseries"]
uvl = ob.data.uv_layers[0]
for poly in ob.data.polygons:
    if ob.data.materials[poly.material_index] is M_BIB_LAMB:
        zs_ = [ob.data.vertices[ob.data.loops[li].vertex_index].co.z for li in poly.loop_indices]
        zmin, zmax = min(zs_), max(zs_)
        for li in poly.loop_indices:
            zz = ob.data.vertices[ob.data.loops[li].vertex_index].co.z - ZS
            uvl.data[li].uv.y = zz / 3.30

# plafond à caissons blancs : poutres croisées 1 cm sous le plafond, 3 × 5 caissons (avant-corps approfondi)
b = Bld()
zp = ZS + HSP - 0.01
YB_N = min(q[1] for q in PIECES[P]["polygone_interieur"])      # -11,85
for k in range(1, 5):
    yb = -5.55 + (YB_N + 5.55) * k / 5
    xb = 3.7 if yb > -8.45 else 3.4
    b.boite(-xb, yb - 0.13, zp - 0.24, xb, yb + 0.13, zp, M_STUC)
    b.boite(-xb, yb - 0.17, zp - 0.05, xb, yb + 0.17, zp, M_STUC)
for xb in (-1.23, 1.23):
    b.boite(xb - 0.13, YB_N, zp - 0.24, xb + 0.13, -5.55, zp, M_STUC)
    b.boite(xb - 0.17, YB_N, zp - 0.05, xb + 0.17, -5.55, zp, M_STUC)
b.objet("bibliotheque_plafond_caissons")

MURS_BIB = {}
for w in murs(P):
    n = w["n"]
    if w["L"] < 1.3:
        continue
    cle = "nord" if (n.y > 0.9) else "sud" if n.y < -0.9 else "ouest" if n.x > 0.9 else "est"
    MURS_BIB[cle] = w


def bibliotheque_vitree(L, H=2.5, P=0.45, nportes=3, graine=0, bouteilles=False):
    """Bibliothèque vitrée : dos à y = 0, façade en y = P, centrée en x."""
    b = Bld()
    rng = random.Random(graine)
    b.boite(-L / 2, 0.0, 0.0, L / 2, P, 0.12, M_ACAJOU)                     # socle
    b.boite(-L / 2 - 0.02, 0.0, H - 0.12, L / 2 + 0.02, P + 0.04, H, M_ACAJOU)  # corniche
    b.boite(-L / 2 - 0.04, 0.0, H - 0.04, L / 2 + 0.04, P + 0.06, H, M_ACAJOU)
    for x in (-L / 2, L / 2 - 0.03):
        b.boite(x, 0.0, 0.12, x + 0.03, P, H - 0.12, M_ACAJOU)
    b.boite(-L / 2, 0.0, 0.12, L / 2, 0.015, H - 0.12, M_CHENE)              # fond
    lp = L / nportes
    ztabs = [0.14 + k * 0.33 for k in range(7) if 0.14 + k * 0.33 < H - 0.35]
    for z in ztabs:
        b.boite(-L / 2 + 0.03, 0.015, z, L / 2 - 0.03, P - 0.03, z + 0.02, M_ACAJOU)
        x = -L / 2 + 0.035
        while x < L / 2 - 0.06:
            if bouteilles and rng.random() < 0.8:
                h = rng.uniform(0.18, 0.28)
                b.tour([(0.03, 0), (0.03, h * 0.65), (0.01, h * 0.85), (0.01, h), (0, h)],
                       M_VERRE if rng.random() < 0.7 else M_VERRE_C, c=(x + 0.035, P * 0.5, z + 0.02), seg=7)
                x += 0.075
                continue
            if rng.random() < 0.06:
                x += rng.uniform(0.04, 0.15)
                continue
            wl = rng.uniform(0.02, 0.05)
            hl = rng.uniform(0.17, 0.29)
            dl = rng.uniform(0.15, 0.24)
            if x + wl > L / 2 - 0.035:
                break
            b.boite(x, P - 0.04 - dl, z + 0.02, x + wl, P - 0.04, z + 0.02 + hl, rng.choice(M_LIVRES))
            x += wl + 0.002
    for i in range(nportes):                                                  # portes vitrées
        x0 = -L / 2 + i * lp
        for (a, c_) in ((x0 + 0.01, x0 + 0.06), (x0 + lp - 0.06, x0 + lp - 0.01)):
            b.boite(a, P - 0.025, 0.13, c_, P, H - 0.13, M_ACAJOU)
        b.boite(x0 + 0.06, P - 0.025, H - 0.20, x0 + lp - 0.06, P, H - 0.13, M_ACAJOU)
        b.boite(x0 + 0.06, P - 0.025, 0.13, x0 + lp - 0.06, P, 0.22, M_ACAJOU)
        b.quad_uv((x0 + lp - 0.06, P - 0.012, 0.22), (x0 + 0.06, P - 0.012, 0.22), (x0 + 0.06, P - 0.012, H - 0.20),
                  (x0 + lp - 0.06, P - 0.012, H - 0.20), M_VITRE)
        b.boite(x0 + (lp - 0.08 if i % 2 == 0 else 0.065), P, 1.15, x0 + (lp - 0.07 if i % 2 == 0 else 0.075), P + 0.012,
                1.22, M_LAITON)
    return b


def poser_mur(bld, nom, w, s, d=0.0, rot_sup=0.0):
    return bld.objet(nom, loc=tuple(pt(w, s, d, ZS)), rot=rot_vers(*w["n"][:2]) + rot_sup)


wn, wsud, we, wo = MURS_BIB["nord"], MURS_BIB["sud"], MURS_BIB["est"], MURS_BIB["ouest"]
# mur nord : deux bibliothèques de part et d'autre de la fenêtre (une à bouteilles, P01)
poser_mur(bibliotheque_vitree(2.80, H=3.05, nportes=4, graine=1, bouteilles=True), "bibliotheque_meuble_nord_ouest", wn,
          s_de(wn, x=-2.15), 0.005)
poser_mur(bibliotheque_vitree(2.80, H=3.05, nportes=4, graine=2), "bibliotheque_meuble_nord_est", wn, s_de(wn, x=2.15), 0.005)
# mur sud de part et d'autre de la porte (angles sud-ouest et sud-est, P03, P00)
poser_mur(bibliotheque_vitree(2.80, H=3.05, nportes=4, graine=3), "bibliotheque_meuble_sud_ouest", wsud, s_de(wsud, x=-2.28),
          0.005)
poser_mur(bibliotheque_vitree(2.80, H=3.05, nportes=4, graine=4), "bibliotheque_meuble_sud_est", wsud, s_de(wsud, x=2.28), 0.005)
# mur ouest, partie sud : retour en angle de la bibliothèque sud-ouest (P03)
poser_mur(bibliotheque_vitree(1.45, H=3.05, nportes=2, graine=5), "bibliotheque_meuble_ouest", wo, s_de(wo, y=-6.62), 0.005)

# --- cheminée néo-Renaissance en noyer sculpté, trumeau à fronton cintré (mur est, P00)
YC = -7.37
s = s_de(we, y=YC)
b = Bld()
L_CH = 1.45
for sg in (-1, 1):
    bo(b, s + sg * (L_CH / 2 - 0.12), 0.0, 0.36, 0.0, 0.12, we, M_ACAJOU, ds=0.26)
    b.tour([(0.07, 0), (0.08, 0.05), (0.05, 0.12), (0.06, 0.35), (0.075, 0.55), (0.05, 0.75), (0.06, 0.85), (0.08, 0.92),
            (0.0, 0.92)], M_ACAJOU, c=tuple(pt(we, s + sg * (L_CH / 2 - 0.12), 0.26, ZS + 0.12)), seg=10)
    bo(b, s + sg * (L_CH / 2 - 0.12), 0.0, 0.22, 0.12, 1.04, we, M_ACAJOU, ds=0.22)
bo(b, s, 0.0, 0.34, 0.90, 1.18, we, M_ACAJOU, ds=L_CH)
for k in range(5):     # consoles sculptées sous la tablette
    bo(b, s - 0.6 + k * 0.3, 0.30, 0.38, 1.02, 1.18, we, M_ACAJOU, ds=0.06)
bo(b, s, 0.0, 0.44, 1.18, 1.24, we, M_ACAJOU, ds=L_CH + 0.10)
bo(b, s, 0.0, 0.02, 0.0, 0.90, we, M_FAIENCE, ds=L_CH - 0.48)                 # contrecœur faïence
bo(b, s, 0.02, 0.24, 0.0, 0.015, we, M_FONTE, ds=L_CH - 0.48)
for sg in (-1, 1):
    bo(b, s + sg * (L_CH / 2 - 0.26), 0.02, 0.24, 0.0, 0.90, we, M_FAIENCE, ds=0.02)
# trumeau : cadre, glace, fronton cintré, volutes
bo(b, s, 0.0, 0.10, 1.24, 3.05, we, M_ACAJOU, ds=1.45)
bo(b, s, 0.10, 0.105, 1.40, 2.50, we, M_MIROIR, ds=0.85)
for sg in (-1, 1):
    b.tour([(0.045, 0), (0.05, 0.1), (0.035, 0.5), (0.05, 1.0), (0.04, 1.2), (0.0, 1.2)], M_ACAJOU,
           c=tuple(pt(we, s + sg * 0.60, 0.12, ZS + 1.30)), seg=8)
arc_pts = []
for k in range(13):
    t = math.pi * k / 12
    arc_pts.append(pt(we, s + 0.78 * math.cos(t), 0.08, ZS + 3.0 + 0.30 * math.sin(t)))
b.tube(arc_pts, 0.07, M_ACAJOU, seg=6)
b.sphere(pt(we, s, 0.12, ZS + 3.36), 0.12, M_NOIR, seg=8, rings=5, sc=(1.4, 0.6, 0.8))   # ornement noir
for sg in (-1, 1):
    b.tube([pt(we, s + sg * (0.55 + 0.1 * math.cos(t)), 0.12, ZS + 2.75 + 0.1 * math.sin(t)) for t in np.linspace(0, 5, 10)],
           0.025, M_ACAJOU, seg=5)
b.objet("bibliotheque_cheminee_trumeau")
b = Bld()       # guirlande de pompons de feutre devant le trumeau
for k in range(14):
    t = k / 13
    b.sphere(pt(we, s - 0.65 + 1.3 * t, 0.16, ZS + 2.40 - 0.18 * math.sin(t * math.pi)), 0.035,
             M_POMPON[k % 3], seg=6, rings=4)
b.objet("bibliotheque_guirlande_pompons")

# --- piano droit (angle sud-est, perpendiculaire au mur est, clavier vers le nord)
b = Bld()
Lp, Pp, Hp = 1.45, 0.60, 1.30
b.boite(-Lp / 2, 0, 0.08, Lp / 2, Pp - 0.25, Hp, M_PALIS)
b.boite(-Lp / 2 - 0.01, -0.01, Hp - 0.03, Lp / 2 + 0.01, Pp - 0.24, Hp, M_PALIS)
b.boite(-Lp / 2, Pp - 0.25, 0.65, Lp / 2, Pp, 0.74, M_PALIS)
b.boite(-Lp / 2 + 0.07, Pp - 0.24, 0.74, Lp / 2 - 0.07, Pp - 0.05, 0.765, M_TOUCHE_B)
for k in range(36):
    if k % 7 in (2, 6):
        continue
    x = -Lp / 2 + 0.10 + k * (Lp - 0.2) / 36
    b.boite(x, Pp - 0.20, 0.765, x + 0.012, Pp - 0.10, 0.78, M_NOIR)
b.boite(-Lp / 2 + 0.07, Pp - 0.27, 0.74, Lp / 2 - 0.07, Pp - 0.24, 0.90, M_PALIS)
for sg in (-1, 1):   # joues et consoles à cariatides
    b.boite(sg * (Lp / 2 - 0.035) - 0.035, Pp - 0.25, 0.08, sg * (Lp / 2 - 0.035) + 0.035, Pp - 0.02, 0.65, M_PALIS)
    b.tour([(0.04, 0), (0.06, 0.04), (0.035, 0.20), (0.05, 0.40), (0.03, 0.52), (0.0, 0.52)], M_PALIS,
           c=(sg * (Lp / 2 - 0.05), Pp - 0.06, 0.08), seg=8)
    b.boite_c(sg * (Lp / 2 - 0.23), Pp - 0.30, 1.0, 0.03, 0.06, 1.06, M_LAITON)       # chandeliers
    b.cylindre((sg * (Lp / 2 - 0.23), Pp - 0.33, 1.03), (sg * (Lp / 2 - 0.23), Pp - 0.33, 1.15), 0.01, M_LAITON, seg=6)
b.boite(-Lp / 2, 0, 0, Lp / 2, Pp - 0.02, 0.08, M_PALIS)
lampe(b, (-0.45, 0.17, Hp), 0.55, M_PORCEL, M_ABAT, ra=0.14, forme="boule")
b.tour([(0.06, 0), (0.08, 0.06), (0.1, 0.16), (0.06, 0.24), (0.07, 0.28), (0.0, 0.28)], M_VERRE_C, c=(0.25, 0.17, Hp), seg=10)
for k in range(18):
    a, r = random.uniform(0, 6.28), random.uniform(0.02, 0.15)
    b.sphere((0.25 + r * math.cos(a), 0.17 + r * math.sin(a), Hp + 0.32 + random.uniform(0, 0.25)), 0.04, M_SECHE,
             seg=5, rings=3)
for dx in (-0.15, 0.0, 0.55):
    b.tour([(0.035, 0), (0.035, 0.09), (0.0, 0.09)], M_PORCEL, c=(dx, 0.2, Hp), seg=8)
b.boite_c(0.40, 0.25, Hp, 0.18, 0.05, Hp + 0.02, M_NOIR)
b.objet("bibliotheque_piano", loc=(3.20 - Lp / 2, -6.03, ZS), rot=math.pi)

# --- miroir encastré au-dessus du radiateur, tablette de marbre, statuette, lampes (mur ouest, P02)
s = s_de(wo, y=-7.48)
b = Bld()
bo(b, s, 0.0, 0.05, 1.10, 3.10, wo, M_BOIS_F, ds=1.30)
bo(b, s, 0.05, 0.055, 1.18, 3.02, wo, M_MIROIR, ds=1.14)
bo(b, s, 0.0, 0.30, 0.86, 0.90, wo, M_MARB_B, ds=1.40)
b.tour([(0.06, 0), (0.06, 0.03), (0.035, 0.05), (0.03, 0.20), (0.045, 0.27), (0.03, 0.32), (0.0, 0.32)], M_BRONZE,
       c=tuple(pt(wo, s, 0.16, ZS + 0.90)), seg=10)
b.sphere(pt(wo, s, 0.16, ZS + 1.25), 0.04, M_BRONZE, seg=8, rings=5)
b.cylindre(pt(wo, s + 0.04, 0.16, ZS + 1.15), pt(wo, s + 0.13, 0.17, ZS + 1.30), 0.012, M_BRONZE, seg=5)
for sg in (-1, 1):
    lampe(b, pt(wo, s + sg * 0.52, 0.15, ZS + 0.90), 0.62, M_LAITON, M_ABAT, ra=0.11, forme="colonne")
b.tour([(0.04, 0), (0.05, 0.12), (0.035, 0.2), (0.0, 0.2)], M_VERRE_C, c=tuple(pt(wo, s - 0.25, 0.15, ZS + 0.90)), seg=10)
b.objet("bibliotheque_miroir_tablette")
instance(radiateur(1.25, 0.82, M_RADIA_BR).objet("bibliotheque_src_radiateur", col=LIB), "bibliotheque_radiateur",
         tuple(pt(wo, s, -0.02, ZS)), rot_vers(*wo["n"][:2]))

# --- tapis persan
b = Bld()
TXB, TYB = -0.35, -7.25
b.quad_uv((TXB - 1.7, TYB - 1.2, ZS + 0.022), (TXB + 1.7, TYB - 1.2, ZS + 0.022), (TXB + 1.7, TYB + 1.2, ZS + 0.022),
          (TXB - 1.7, TYB + 1.2, ZS + 0.022), M_TAPIS)
b.boite(TXB - 1.7, TYB - 1.2, ZS + 0.010, TXB + 1.7, TYB + 1.2, ZS + 0.0215, M_TAPIS)
b.objet("bibliotheque_tapis_persan")

# --- canapé d'angle en L (côté ouest, méridienne vers le nord-est)
b = Bld()
xa, xb = -3.40, -2.45          # dos contre l'ouest
y_s, y_n = -5.95, -8.70
b.boite(xa, y_n, 0.06, xb, y_s, 0.42, M_TAUPE)                               # assise
b.boite(xa, y_n, 0.42, xa + 0.22, y_s, 0.80, M_TAUPE)                        # dossier
b.boite(xa, y_s - 0.22, 0.42, xb, y_s, 0.62, M_TAUPE)                        # accoudoir sud
b.boite(xb, y_n, 0.06, xb + 0.85, y_n + 0.95, 0.42, M_TAUPE)                 # méridienne
b.boite(xa, y_n, 0.42, xb + 0.85, y_n + 0.22, 0.75, M_TAUPE)                 # dossier nord
for k in range(3):
    y0 = y_s - 0.22 - k * 0.85
    b.boite(xa + 0.24, y0 - 0.82, 0.42, xb - 0.02, y0 - 0.02, 0.52, M_TAUPE)
b.boite(xa + 0.02, -6.4, 0.80, xa + 0.30, -7.6, 0.86, M_PLAID)
for (yy, rr) in ((-6.45, 0.3), (-6.95, -0.2)):
    b.boite_o((xa + 0.36, yy, 0.62), Vector((0.06, 0, 0.02)), Vector((0, 0.21, 0)),
              Vector((0.02, 0, 0.21)), M_FUCHSIA)
b.boite_o((xa + 0.18, -6.2, 0.63), Vector((0.02, 0, 0)), Vector((0, 0.03, 0)), Vector((0, 0, 0.02)), M_PORCEL)
ob = b.objet("bibliotheque_canape_angle", loc=(0, 0, ZS))
biseau(ob, 0.03, 2)

# --- table basse ovale, beau-livre, bougies
b = Bld()
cx, cy = -1.45, -7.05
b.tour([(0.6, 0.40), (0.6, 0.44), (0, 0.44)], M_CHENE, c=(cx, cy, ZS), seg=24, sc=(1, 0.66))
b.tour([(0, 0.40), (0.6, 0.40)], M_CHENE, c=(cx, cy, ZS), seg=24, sc=(1, 0.66))
for sx in (-1, 1):
    for sy in (-1, 1):
        b.cylindre((cx + sx * 0.38, cy + sy * 0.22, ZS), (cx + sx * 0.38, cy + sy * 0.22, ZS + 0.40), 0.025, M_CHENE)
    b.boite_c(cx, cy + sx * 0.22, ZS + 0.12, 0.76, 0.03, ZS + 0.15, M_CHENE)
b.boite_c(cx + 0.15, cy - 0.05, ZS + 0.44, 0.32, 0.26, ZS + 0.47, M_LIVRES[1])
for k, (dx, dy, h) in enumerate(((-0.25, 0.05, 0.10), (-0.18, 0.12, 0.07), (-0.32, -0.08, 0.12), (0.05, 0.18, 0.06))):
    b.tour([(0.03, 0), (0.03, h), (0, h)], M_BOUGIE if k < 3 else M_DORE, c=(cx + dx, cy + dy, ZS + 0.44), seg=10)
b.objet("bibliotheque_table_basse")

# --- sièges : bergère rose devant la fenêtre, cabriolets crème, fauteuil fuchsia
chaise_medaillon(M_ROSE, larg=0.70, accoudoirs=True, bergere=True).objet(
    "bibliotheque_bergere", loc=(0.05, -10.95, ZS), rot=rot_vers(0.1, 1))
src_cab = chaise_medaillon(M_ROSE, larg=0.62, accoudoirs=True).objet("bibliotheque_src_cabriolet", col=LIB)
instance(src_cab, "bibliotheque_cabriolet.0", (1.15, -10.65, ZS), rot_vers(-0.6, 1))
instance(src_cab, "bibliotheque_cabriolet.1", (1.35, -7.25, ZS), rot_vers(-1, -0.15))
instance(src_cab, "bibliotheque_cabriolet.2", (-1.15, -6.32, ZS), rot_vers(0.1, -1))
chaise_medaillon(M_FUCHSIA, m_bois=M_CHENE, larg=0.66, accoudoirs=True).objet(
    "bibliotheque_fauteuil_fuchsia", loc=(-2.05, -6.30, ZS), rot=rot_vers(0.3, -1))
# guéridon tripode et lampadaire à abat-jour plissé
b = Bld()
cx, cy = -0.72, -11.12
b.tour([(0.225, 0.73), (0.225, 0.75), (0, 0.75)], M_CHENE, c=(cx, cy, ZS), seg=20)
b.tour([(0, 0.73), (0.225, 0.73)], M_CHENE, c=(cx, cy, ZS), seg=20)
b.tour([(0.03, 0.2), (0.04, 0.3), (0.025, 0.5), (0.03, 0.73), (0, 0.73)], M_CHENE, c=(cx, cy, ZS), seg=10)
for k in range(3):
    a = 2 * math.pi * k / 3
    b.tube([(cx + 0.03 * math.cos(a), cy + 0.03 * math.sin(a), ZS + 0.25),
            (cx + 0.16 * math.cos(a), cy + 0.16 * math.sin(a), ZS + 0.08),
            (cx + 0.24 * math.cos(a), cy + 0.24 * math.sin(a), ZS)], 0.015, M_CHENE)
lampe(b, (cx, cy, ZS + 0.75), 0.48, M_PORCEL, M_ABAT, ra=0.10, forme="balustre")
b.boite_c(cx + 0.05, cy + 0.08, ZS + 0.75, 0.2, 0.15, ZS + 0.77, M_LIVRES[3])
b.objet("bibliotheque_gueridon")
b = Bld()
cx, cy = 1.90, -11.10
b.tour([(0.15, 0), (0.15, 0.03), (0.03, 0.06), (0.012, 0.3), (0.012, 1.35), (0.0, 1.35)], M_LAITON, c=(cx, cy, ZS), seg=12)
b.tour([(0.24, 1.22), (0.13, 1.55), (0.12, 1.55), (0.23, 1.22)], M_ABAT, c=(cx, cy, ZS), seg=24)
b.objet("bibliotheque_lampadaire")
# téléviseur sur pied devant le foyer (P00)
b = Bld()
b.boite_c(0, 0, 0.0, 0.40, 0.25, 0.02, M_NOIR)
b.boite_c(0, 0, 0.02, 0.06, 0.04, 0.12, M_NOIR)
b.boite_c(0, 0, 0.12, 1.23, 0.04, 0.84, M_ECRAN)
b.objet("bibliotheque_televiseur", loc=tuple(pt(we, s_de(we, y=YC), 0.80, ZS)), rot=rot_vers(*we["n"][:2]))

# --- lustre hollandais en laiton 8 bras
b = Bld()
LX, LY = -0.15, -7.35
zl = ZS + HSP - 1.40
lustre(b, (LX, LY, zl), 8, 0, 0.38, 0.55, M_LAITON, chaine=1.40 - 0.55 - 0.02, style="hollandais")
b.objet("bibliotheque_lustre")
lumiere("lumiere_bibliotheque_lustre", (LX, LY, zl + 0.05), 260, 0.35)
lumiere("lumiere_bibliotheque_lampadaire", (1.90, -11.10, ZS + 1.40), 40, 0.12)

# --- partie nord (avant-corps approfondi de 2,5 m) : table de travail entre les fenêtres latérales, second lustre
b = Bld()
cx, cy = 0.0, -9.35
LT, PT, HT = 1.90, 0.95, 0.76
b.boite_c(cx, cy, ZS + HT - 0.035, LT, PT, ZS + HT, M_ACAJOU)                                  # plateau
b.boite_c(cx, cy, ZS + HT, LT - 0.12, PT - 0.12, ZS + HT + 0.004, M_LIVRES[2])   # cuir
b.boite_c(cx, cy, ZS + HT - 0.16, LT - 0.10, PT - 0.10, ZS + HT - 0.035, M_ACAJOU)                    # ceinture à tiroirs
for sx in (-1, 1):
    for sy in (-1, 1):
        b.tour([(0.035, 0), (0.025, 0.08), (0.03, 0.35), (0.022, 0.55), (0.03, HT - 0.16), (0.0, HT - 0.16)], M_ACAJOU,
               c=(cx + sx * (LT / 2 - 0.08), cy + sy * (PT / 2 - 0.08), ZS), seg=10)
    b.boite_c(cx + sx * 0.45, cy - PT / 2 + 0.044, ZS + HT - 0.11, 0.05, 0.012, ZS + HT - 0.09, M_LAITON)  # boutons de tiroir
lampe(b, (cx - 0.62, cy + 0.18, ZS + HT), 0.42, M_LAITON, M_ABAT, ra=0.09, forme="balustre")
for k, (dx, dy) in enumerate(((0.25, -0.10), (0.45, 0.12), (-0.15, 0.20))):
    b.boite_c(cx + dx, cy + dy, ZS + HT + 0.004, 0.24, 0.17, ZS + HT + 0.04, M_LIVRES[k % len(M_LIVRES)])
b.objet("bibliotheque_table_travail")
instance(src_cab, "bibliotheque_cabriolet.3", (0.0, -9.35 + 0.80, ZS), rot_vers(0, -1))
instance(src_cab, "bibliotheque_cabriolet.4", (0.0, -9.35 - 0.80, ZS), rot_vers(0, 1))
b = Bld()
zl2 = ZS + HSP - 1.40
lustre(b, (0.0, -9.35, zl2), 8, 0, 0.38, 0.55, M_LAITON, chaine=1.40 - 0.55 - 0.02, style="hollandais")
b.objet("bibliotheque_lustre_nord")
lumiere("lumiere_bibliotheque_lustre_nord", (0.0, -9.35, zl2 + 0.05), 220, 0.35)


# ==============================================================================================
# DÉGAGEMENT NORD-OUEST (P10-P13) — x -10,5 → -5,7 ; y -5,2 (nord, placards) → -3,6 (sud)
# ==============================================================================================
log("dégagement nord-ouest…")
P = "degagement_no"
ZS = PIECES[P]["z_sol"]
HSP = PIECES[P]["hauteur_sous_plafond"]
X0, X1, Y0, Y1 = -10.5, -5.7, -5.2, -3.6
ZNAIS = 3.40          # naissance de la voûte en berceau surbaissé
sol_pose(P, M_MARB_LOS, "degagement_no_dallage")
b = Bld()             # bandes d'encadrement en marbre rouge
for (a0, a1, c0_, c1_) in ((X0 + 0.15, X1 - 0.15, Y0 + 0.15, Y0 + 0.27), (X0 + 0.15, X1 - 0.15, Y1 - 0.27, Y1 - 0.15)):
    b.boite(a0, c0_, ZS + 0.010, a1, c1_, ZS + 0.0125, M_MARB_R)
for (a0, a1) in ((X0 + 0.15, X0 + 0.27), (X1 - 0.27, X1 - 0.15)):
    b.boite(a0, Y0 + 0.15, ZS + 0.010, a1, Y1 - 0.15, ZS + 0.0125, M_MARB_R)
b.objet("degagement_no_bandes_marbre_rouge")
habiller(P, dict(z_cim=0.90, z_haut=ZNAIS - 0.12, z_corniche=ZNAIS - 0.12, h_corniche=0.12, s_corniche=0.08,
                 m_bas=M_DEG_BAS, m_haut=M_DEG_HAUT, m_dessus=M_ENDUIT, m_plein=M_ENDUIT, m_plinthe=M_GV,
                 m_moul=M_GV, m_chamb=M_GV, m_corniche=M_ENDUIT, cible=1.2, ch_l=0.10, dessus_fen=False,
                 sans_dessus=("porte_degagement_no_etage_bloc_ouest",)))
# voûte en berceau surbaissé (axe est-ouest), crête 1 cm sous le plafond de coque
b = Bld()
yc, demi = (Y0 + Y1) / 2, (Y1 - Y0) / 2
fl_ = HSP - 0.01 - ZNAIS
R = (demi ** 2 + fl_ ** 2) / (2 * fl_)
zc_ = ZS + HSP - 0.01 - R
NS = 16
ann = []
for i in range(NS + 1):
    yy = Y0 + (Y1 - Y0) * i / NS
    zz = zc_ + math.sqrt(max(0.0, R * R - (yy - yc) ** 2))
    ann.append((yy, zz))
v0 = [b.v((X0, yy, zz)) for yy, zz in ann]
v1 = [b.v((X1, yy, zz)) for yy, zz in ann]
for i in range(NS):
    b.face([v0[i], v0[i + 1], v1[i + 1], v1[i]], M_ENDUIT, lisse=True, uvs=[(0, 0)] * 4)
ob = b.objet("degagement_no_voute", recalc=False)
b = Bld()
# arc doubleau mouluré à l'entrée (côté arcade est) et retombées
ch = []
for i in range(NS + 1):
    yy, zz = ann[i]
    t = Vector((0, 1, (ann[min(i + 1, NS)][1] - ann[max(i - 1, 0)][1]) / ((Y1 - Y0) / NS * 2))).normalized()
    nrm = Vector((0, -t.z, t.y))
    ch.append((Vector((X1 - 0.01, yy, zz)), Vector((-1, 0, 0)), nrm))
b.balayage(ch, [(0.0, 0.0), (0.22, 0.0), (0.22, -0.03), (0.17, -0.07), (0.05, -0.07), (0.0, -0.05)], M_ENDUIT)
b.objet("degagement_no_arc_doubleau")

MURS_DEG = {}
for w in murs(P):
    n = w["n"]
    cle = "nord" if n.y > 0.9 else "sud" if n.y < -0.9 else "ouest" if n.x > 0.9 else "est"
    MURS_DEG[cle] = w
# tympan cintré au-dessus de la porte double du fond (mur ouest, P10)
wo = MURS_DEG["ouest"]
o = next(o for o in wo["ouv"] if o["type"] != "arcade")
b = Bld()
r_ = o["l"] / 2 + 0.10
zt_ = ZS + o["zt"] + 0.10
chem = []
for k in range(17):
    a = math.pi * k / 16
    p_ = pt(wo, o["s"] + r_ * math.cos(a), 0.0, zt_ + r_ * math.sin(a))
    chem.append((p_, wo["n"], Vector(-math.cos(a) * wo["u"] + Vector((0, 0, -math.sin(a))))))
b.balayage(chem, [(0, 0), (0.03, 0), (0.03, 0.04), (0.015, 0.09), (0, 0.10)], M_GV)
vc = b.v(pt(wo, o["s"], 0.011, zt_))
prev = None
for k in range(17):
    a = math.pi * k / 16
    vv = b.v(pt(wo, o["s"] + (r_ - 0.005) * math.cos(a), 0.011, zt_ + (r_ - 0.005) * math.sin(a)))
    if prev:
        b.face_orientee([vc, prev, vv], M_ENDUIT, wo["n"])
    prev = vv
b.objet("degagement_no_tympan_porte_ouest")

# placards à deux vantaux (mur nord, P11-P13)
wn = MURS_DEG["nord"]
b = Bld()
for xc in (-9.65, -8.30):
    s = s_de(wn, x=xc)
    lv, hv = 0.60, 2.80
    for k, sg in enumerate((-1, 1)):
        a, c_ = s + (sg - 1) / 2 * lv * 1.0 + (0 if sg < 0 else 0), s + (sg + 1) / 2 * lv
        a, c_ = (s - lv, s) if sg < 0 else (s, s + lv)
        b.boite_o(pt(wn, (a + c_) / 2, 0.02, ZS + hv / 2), wn["u"] * (lv / 2 - 0.002), wn["n"] * 0.02,
                  Vector((0, 0, hv / 2)), M_LAQUE_BL)
        quad_mur(b, wn, a + 0.002, c_ - 0.002, ZS, ZS + hv, M_DEG_PORTE, d=0.041)
        b.boite_o(pt(wn, s + sg * 0.12, 0.05, ZS + 1.24), wn["u"] * 0.05, wn["n"] * 0.004, Vector((0, 0, 0.01)), M_LAITON)
b.objet("degagement_no_placards")

# console, bouquet, photophore ; radiateur ; applique à 4 bras (mur nord, côté arcade, P10)
s = s_de(wn, x=-6.22)
b = Bld()
bo(b, s, 0.0, 0.40, 0.76, 0.80, wn, M_ACAJOU, ds=0.90)
bo(b, s, 0.02, 0.38, 0.64, 0.76, wn, M_ACAJOU, ds=0.84)
for sg in (-1, 1):
    for dd in (0.05, 0.35):
        b.cylindre(pt(wn, s + sg * 0.40, dd, ZS), pt(wn, s + sg * 0.40, dd, ZS + 0.66), 0.02, M_ACAJOU, seg=6)
cb = pt(wn, s - 0.1, 0.2, ZS + 0.80)
b.tour([(0.10, 0), (0.10, 0.01), (0, 0.01)], M_PORCEL, c=tuple(cb), seg=14)
b.tour([(0.05, 0), (0.07, 0.08), (0.06, 0.25), (0.045, 0.30), (0.0, 0.30)], M_PORCEL, c=tuple(cb), seg=12)
rng = random.Random(3)
for k in range(22):
    a, r = rng.uniform(0, 6.28), rng.uniform(0.0, 0.16)
    m = M_FLEUR_B if k % 3 else (M_FLEUR_R if k % 2 else M_FEUIL)
    b.sphere((cb.x + r * math.cos(a), cb.y + r * math.sin(a), cb.z + 0.36 + rng.uniform(0, 0.22)), 0.045, m, seg=6, rings=4)
b.tour([(0.04, 0), (0.04, 0.13), (0, 0.13)], M_DORE, c=tuple(pt(wn, s + 0.25, 0.2, ZS + 0.80)), seg=10)
b.objet("degagement_no_console_bouquet")
instance(radiateur(0.8, 0.88, M_RADIA).objet("degagement_no_src_radiateur", col=LIB), "degagement_no_radiateur",
         tuple(pt(wn, s_de(wn, x=-7.1), 0.0, ZS)), rot_vers(*wn["n"][:2]))
b = Bld()
s = s_de(wn, x=-6.85)
ca = pt(wn, s, 0.0, ZS + 2.2)
b.boite_o(ca + wn["n"] * 0.02, wn["u"] * 0.05, wn["n"] * 0.02, Vector((0, 0, 0.16)), M_DORE)
for k, (ds_, dz) in enumerate(((-0.17, 0.02), (-0.06, 0.12), (0.06, 0.12), (0.17, 0.02))):
    pts = [ca + wn["n"] * (0.04 + 0.14 * t) + wn["u"] * ds_ * t + Vector((0, 0, -0.08 + (dz + 0.10) * t ** 2))
           for t in np.linspace(0, 1, 7)]
    b.tube(pts, 0.01, M_DORE, seg=5)
    p_ = pts[-1]
    b.tour([(0.01, 0), (0.035, 0.01), (0.035, 0.02), (0.01, 0.02)], M_DORE, c=tuple(p_), seg=8)
    b.cylindre(p_ + Vector((0, 0, 0.02)), p_ + Vector((0, 0, 0.12)), 0.01, M_BOUGIE, seg=6)
    b.sphere(p_ + Vector((0, 0, 0.14)), 0.012, M_FLAMME, seg=6, rings=4, sc=(1, 1, 1.5))
b.objet("degagement_no_applique")
lumiere("lumiere_degagement_no_applique", tuple(ca + wn["n"] * 0.18 + Vector((0, 0, 0.12))), 25, 0.08)
# lanterne suspendue en fer forgé (au milieu, sous la crête de la voûte)
b = Bld()
lx, ly = -8.75, yc
zt_ = ZS + HSP - 0.01
zlb = zt_ - 0.95
b.cylindre((lx, ly, zlb + 0.50), (lx, ly, zt_), 0.006, M_FER, seg=6)
b.tour([(0.0, 0.0), (0.10, 0.0), (0.12, 0.03), (0.0, 0.05)], M_FER, c=(lx, ly, zlb), seg=8)
b.tour([(0.15, 0.40), (0.05, 0.50), (0.0, 0.52)], M_FER, c=(lx, ly, zlb), seg=8)
b.tour([(0.13, 0.04), (0.13, 0.40), (0, 0.40)], M_VERRE_C, c=(lx, ly, zlb), seg=8)
for k in range(4):
    a = math.pi / 4 + k * math.pi / 2
    b.cylindre((lx + 0.135 * math.cos(a), ly + 0.135 * math.sin(a), zlb + 0.03),
               (lx + 0.15 * math.cos(a), ly + 0.15 * math.sin(a), zlb + 0.41), 0.008, M_FER, seg=4)
b.cylindre((lx, ly, zlb + 0.05), (lx, ly, zlb + 0.16), 0.012, M_BOUGIE, seg=6)
b.sphere((lx, ly, zlb + 0.20), 0.025, M_FLAMME, seg=6, rings=4, sc=(1, 1, 1.4))
b.objet("degagement_no_lanterne")
lumiere("lumiere_degagement_no_lanterne", (lx, ly, zlb + 0.22), 70, 0.10)


# ----------------------------------------------------------------------------------------------
# Contexte pour les rendus (non exporté) : coque et bati, vantaux ouverts, lumières de jour
# ----------------------------------------------------------------------------------------------
log("contexte…")
lc = bpy.context.view_layer.layer_collection.children[CTX.name]
bpy.context.view_layer.active_layer_collection = lc
for nom in ("coque", "bati"):
    chemin = os.path.join(EXPORT, nom + ".glb")
    if os.path.exists(chemin):
        bpy.ops.import_scene.gltf(filepath=chemin)
ouverts = {}
for pid in ("salle_a_manger", "bibliotheque"):
    for o in PIECES[pid]["portes"]:
        if o.get("ouvrable"):
            for v in o["vantaux"]:
                ouverts[v["objet"]] = v["angle_ouverture_z_deg"]
for ob in CTX.objects:
    base = ob.name.split(".")[0]
    if base in ouverts:
        ob.rotation_mode = "XYZ"
        ob.rotation_euler.z += math.radians(ouverts[base] * 0.92)
log("objets de contexte :", len(CTX.objects))


def regler_rendu():
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            SC.render.engine = eng
            break
        except TypeError:
            continue
    try:
        SC.eevee.taa_render_samples = 48
        SC.eevee.use_shadows = True
    except Exception:
        pass
    try:
        SC.eevee.use_raytracing = True
        SC.eevee.ray_tracing_options.resolution_scale = "2"
    except Exception:
        pass
    SC.render.resolution_x = 900
    SC.render.resolution_y = 1200
    w = bpy.data.worlds.new("ciel")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.62, 0.70, 0.82, 1)
    bg.inputs["Strength"].default_value = 1.2
    SC.world = w
    try:
        SC.view_settings.view_transform = "AgX"
        SC.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    SC.view_settings.exposure = -0.2


regler_rendu()
CTX_LUM = []


def lum_ctx(nom, typ, loc, rot=None, energie=100, taille=(1, 1), couleur=(1, 1, 1)):
    li = bpy.data.lights.new(nom, typ)
    li.energy = energie
    li.color = couleur
    if typ == "AREA":
        li.shape = "RECTANGLE"
        li.size, li.size_y = taille
    ob = bpy.data.objects.new(nom, li)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    CTX.objects.link(ob)
    CTX_LUM.append(ob)
    return ob


so = lum_ctx("soleil", "SUN", (0, 0, 30), (math.radians(40), 0, math.radians(20)), 3.0, couleur=(1.0, 0.95, 0.88))
# jour entrant par les baies (lumières de surface dans les embrasures, tournées vers l'intérieur)
for (x, y, ry) in ((5.25, 8.30, -1), (8.85, 8.30, -1), (0.0, -12.0, 1)):
    lum_ctx("jour_%.1f_%.1f" % (x, y), "AREA", (x, y, Z_ET + 1.8), (math.radians(90 * ry), 0, 0), 450, (1.3, 3.0),
            (0.95, 0.97, 1.0))
# appoint diffus sous les plafonds
for pid, e in (("salle_a_manger", 300), ("bibliotheque", 300), ("degagement_no", 90)):
    poly = PIECES[pid]["polygone_interieur"]
    xs, ys = [q[0] for q in poly], [q[1] for q in poly]
    lum_ctx("appoint_" + pid, "AREA", ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                                       PIECES[pid]["z_sol"] + PIECES[pid]["hauteur_sous_plafond"] - 0.3),
            None, e, (max(xs) - min(xs) - 0.6, max(ys) - min(ys) - 0.6), (1.0, 0.95, 0.88))

# parent miroir (1, -1, 1) pour comparer aux photos (D-026)
MIR = bpy.data.objects.new("miroir_rendu", None)
CTX.objects.link(MIR)
MIR.scale = (1, -1, 1)
racines = [ob for ob in SC.objects if ob.parent is None and ob is not MIR and ob.name not in LIB.objects]
for ob in racines:
    ob.parent = MIR
for ob in LIB.objects:
    ob.hide_render = True


def camera(nom, pos, cible, focale=15):
    cam = bpy.data.cameras.new(nom)
    cam.lens = focale
    cam.sensor_width = 36
    cam.clip_start = 0.05
    cam.clip_end = 200
    co = bpy.data.objects.new(nom, cam)
    p = Vector((pos[0], -pos[1], pos[2]))
    c = Vector((cible[0], -cible[1], cible[2]))
    co.location = p
    co.rotation_euler = (c - p).to_track_quat("-Z", "Y").to_euler()
    CTX.objects.link(co)
    return co


def rendre(cam, fichier):
    SC.camera = cam
    SC.render.filepath = os.path.join(RENDUS, fichier)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log("rendu", fichier, "%.1fs" % (time.time() - t))


ZE = Z_ET
VUES = {   # positions en repère D-003 (passées au miroir dans camera())
    "piece_reception_sam_p44.png": ((6.2, 1.45, ZE + 1.55), (7.3, 8.15, ZE + 1.75), 14),
    "piece_reception_sam_p50.png": ((9.6, 4.6, ZE + 1.55), (4.3, 4.0, ZE + 1.7), 14),
    "piece_reception_sam_p51.png": ((8.0, 7.2, ZE + 1.60), (7.5, 1.1, ZE + 1.55), 14),
    "piece_reception_bib_p01.png": ((0.4, -5.75, ZE + 1.55), (0.0, -11.85, ZE + 1.9), 13),
    "piece_reception_bib_p00.png": ((-2.75, -6.0, ZE + 1.45), (3.7, -7.6, ZE + 1.75), 14),
    "piece_reception_deg_p10.png": ((-5.85, -3.75, ZE + 1.55), (-10.5, -4.5, ZE + 1.6), 15),
}
SEULE = os.environ.get("PR_VUES")
for f, (p_, c_, fo) in VUES.items():
    if SEULE and not any(k in f for k in SEULE.split(",")):
        continue
    rendre(camera("cam_" + f[:-4], p_, c_, fo), f)


# ----------------------------------------------------------------------------------------------
# Export : on retire le contexte et le parent miroir, puis .blend et .glb
# ----------------------------------------------------------------------------------------------
for ob in list(COL.objects):
    ob.parent = None
for ob in list(CTX.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for ob in list(SC.objects):
    if ob.users_collection and ob.users_collection[0] not in (COL, LIB):
        bpy.data.objects.remove(ob, do_unlink=True)
bpy.data.collections.remove(CTX)
for ob in LIB.objects:
    ob.hide_render = False
bpy.data.orphans_purge(do_recursive=True)

lc = bpy.context.view_layer.layer_collection.children[ID]
bpy.context.view_layer.active_layer_collection = lc
glb = os.path.join(EXPORT, ID + ".glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_active_collection=True, export_apply=True,
                          export_yup=True, export_image_format="JPEG", export_jpeg_quality=88, export_lights=True)
log("glb :", glb, "%.1f Mo" % (os.path.getsize(glb) / 1e6))
try:
    bpy.ops.file.pack_all()
except RuntimeError as ex:
    log("pack_all :", ex)
blend = os.path.join(EXPORT, ID + ".blend")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
nv = sum(len(o.data.vertices) for o in COL.objects if o.type == "MESH")
log("objets :", len(COL.objects), "sommets (avant instances/modif.) :", nv)
log("fin")

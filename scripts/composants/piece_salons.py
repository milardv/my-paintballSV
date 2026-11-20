"""Composant P4.salons + P4.billard : décor fixe et mobilier du salon bow-window, du billard, du salon vert,
du salon ouest, de la pièce nord-ouest et du dégagement est (RDC).

blender -b --factory-startup --python scripts/composants/piece_salons.py
→ export/composants/piece_salons.glb, export/composants/piece_salons.blend, rendus/piece_salons_*.png

Repère D-003 : mètres, +X est, +Y sud (jardin), Z haut, RDC = 0. Chaque élément est placé selon son
orientation réelle exprimée dans ce repère ; les rendus comparés aux photos passent par un miroir Y (D-026).
Pièces, portes et fenêtres : travail/coque.json et bati.py (baies D-025). Coque et bati sont importés pour
les rendus seulement, jamais exportés ici.
"""
import json
import math
import os
import shutil
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFilter

T0 = time.time()
try:
    RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    RACINE = os.path.expanduser("~/IdeaProjects/chateau-saint-victor")
ID = "piece_salons"
EXPORT = os.path.join(RACINE, "export", "composants")
TEXDIR = os.path.join(EXPORT, ID + "_textures")
RENDUS = os.path.join(RACINE, "rendus")
PH = os.path.join(RACINE, "assets", "polyhaven")
shutil.rmtree(TEXDIR, ignore_errors=True)
for d_ in (EXPORT, TEXDIR, RENDUS):
    os.makedirs(d_, exist_ok=True)

COQUE = json.load(open(os.path.join(RACINE, "travail", "coque.json")))
PIECES = {p["id"]: p for p in COQUE["pieces"]}
MES_PIECES = ["salon", "billard", "salon_vert", "salon_ouest", "piece_no", "degagement_est"]
RNG = np.random.default_rng(7)


def log(*a):
    print("[%s %5.1fs]" % (ID, time.time() - T0), *a)
    sys.stdout.flush()


# ----------------------------------------------------------------------------------------------
# Géométrie plane
# ----------------------------------------------------------------------------------------------
def aire(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def ccw(poly):
    poly = [tuple(p) for p in poly]
    return poly if aire(poly) > 0 else poly[::-1]


def decaler(poly, d):
    """Polygone CCW décalé vers l'intérieur de d (intersection des côtés décalés)."""
    n = len(poly)
    lignes = []
    for i in range(n):
        p, q = Vector(poly[i]), Vector(poly[(i + 1) % n])
        t = (q - p).normalized()
        nn = Vector((-t.y, t.x))
        lignes.append((p + nn * d, t))
    out = []
    for i in range(n):
        (p1, t1), (p2, t2) = lignes[i - 1], lignes[i]
        den = t1.x * t2.y - t1.y * t2.x
        if abs(den) < 1e-9:
            out.append(tuple(p2))
            continue
        w = p2 - p1
        k = (w.x * t2.y - w.y * t2.x) / den
        out.append(tuple(p1 + t1 * k))
    return out


def srgb(r, g, b):
    """Couleur sRGB 0-255 → linéaire (Base Color Blender)."""
    return tuple(((c / 255.0 + 0.055) / 1.055) ** 2.4 for c in (r, g, b))


# ----------------------------------------------------------------------------------------------
# Scène
# ----------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
COL = bpy.data.collections.new(ID)
SC.collection.children.link(COL)
PROTOS = bpy.data.collections.new("protos")
SC.collection.children.link(PROTOS)
CTX = bpy.data.collections.new("contexte_rendu")
SC.collection.children.link(CTX)

# ----------------------------------------------------------------------------------------------
# Textures (sRGB 0-1) : générées ici ou dérivées des textures CC0 de Poly Haven
# ----------------------------------------------------------------------------------------------


def sauver(nom, arr, q=88):
    a = np.clip(arr, 0, 1)
    if a.ndim == 2:
        a = np.repeat(a[:, :, None], 3, axis=2)
    chemin = os.path.join(TEXDIR, nom + ".jpg")
    Image.fromarray((a * 255 + 0.5).astype(np.uint8)).save(chemin, quality=q)
    return chemin


def charger(chemin, taille=None):
    im = Image.open(chemin).convert("RGB")
    if taille:
        im = im.resize((taille, taille), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


def lum(a):
    return a[:, :, 0] * 0.3 + a[:, :, 1] * 0.59 + a[:, :, 2] * 0.11


def bruit(n, echelles=(8, 32, 128), poids=(0.5, 0.3, 0.2), graine=0):
    """Bruit de valeur lissé, périodique, n × n, moyenne 0."""
    r = np.random.default_rng(graine)
    out = np.zeros((n, n), np.float32)
    for e, w in zip(echelles, poids):
        g = r.standard_normal((e, e)).astype(np.float32)
        im = Image.fromarray(((g - g.min()) / (np.ptp(g) + 1e-6) * 255).astype(np.uint8))
        im = im.resize((n, n), Image.BICUBIC)
        out += w * (np.asarray(im, np.float32) / 255 - 0.5)
    return out


def flou(arr, r):
    if arr.ndim == 2:
        im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
        return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255


def ph(nom, carte, res="1k", ext="jpg"):
    return os.path.join(PH, "polyhaven-" + nom, "%s_%s_%s.%s" % (nom, carte, res, ext))


def tex_damas(n=1024):
    """Motif damassé symétrique en quinconce (masque 0-1), raccord 0,70 m."""
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n
    m = np.zeros((n, n), np.float32)
    for cx, cy in ((0.5, 0.25), (0.0, 0.75), (1.0, 0.75)):
        dx = np.abs(u - cx)
        dy = v - cy
        dy = (dy + 0.5) % 1.0 - 0.5
        r = np.hypot(dx, dy + 0.05)
        th = np.arctan2(dy + 0.05, dx)
        fleur = r < 0.10 * (0.55 + 0.45 * np.cos(5 * th) ** 2)
        coeur = np.hypot(dx, dy + 0.05) < 0.035
        feuilles = np.zeros_like(fleur)
        for ox, oy, a, lx, ly in ((0.10, 0.06, 0.7, 0.13, 0.035), (0.13, -0.14, -0.5, 0.11, 0.03),
                                  (0.05, 0.20, 1.2, 0.08, 0.025)):
            ca, sa = math.cos(a), math.sin(a)
            x1 = (dx - ox) * ca + (dy - oy) * sa
            y1 = -(dx - ox) * sa + (dy - oy) * ca
            feuilles |= (x1 / lx) ** 2 + (y1 / ly) ** 2 < 1
        tige = (dx < 0.007) & (dy > -0.02) & (dy < 0.24)
        rb = np.hypot(dx - 0.15, dy - 0.15)
        volute = (np.abs(rb - 0.065) < 0.010) & (np.arctan2(dy - 0.15, dx - 0.15) > -1.2)
        palm = (dy < -0.16) & (dy > -0.30) & (dx < (dy + 0.30) * 0.55) & \
               (np.cos((np.arctan2(dy + 0.30, dx + 1e-6)) * 14) > -0.2)
        m = np.maximum(m, (fleur & ~coeur | feuilles | tige | volute | palm).astype(np.float32))
    return flou(m, 1.2)


DAMAS = tex_damas()


def damas(nom, fond, motif, n=0.0):
    c = np.array(fond)[None, None, :] * (1 - DAMAS[:, :, None]) + np.array(motif)[None, None, :] * DAMAS[:, :, None]
    c = c * (1 + 0.04 * bruit(1024, graine=3)[:, :, None] + n)
    return sauver(nom, c)


T_DAMAS_RGH = sauver("damas_rgh", 0.78 - 0.30 * DAMAS)


def tex_versailles():
    """Parquet à panneaux (Versailles) : cadre, treillis diagonal et losanges à trois tons, 2 m par tuile."""
    n = 2048
    oak = charger(ph("oak_wood_planks", "diff"), 1024)
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n * 2.0
    P = 1.0
    pu, pv = u % P, v % P
    K = 900.0

    def grain(a, b):
        return oak[((b * K).astype(int)) % 1024, ((a * K).astype(int)) % 1024]

    s2 = math.sqrt(0.5)
    g_u, g_v = grain(u, v * 0.15), grain(v, u * 0.15)
    g_d1 = grain((u + v) * s2, (u - v) * s2 * 0.15)
    g_d2 = grain((u - v) * s2, (u + v) * s2 * 0.15)
    b = 0.085
    eb = np.minimum(np.minimum(pu, P - pu), np.minimum(pv, P - pv))
    cadre = eb < b
    long_u = np.minimum(pv, P - pv) < np.minimum(pu, P - pu)
    a_ = (pu + pv) / (P * s2) * 2.0
    b_ = (pu - pv + P) / (P * s2) * 2.0
    w = 0.10
    fa, fb = a_ % 1.0, b_ % 1.0
    lat_a, lat_b = fa < w, fb < w
    ia, ib = np.floor(a_).astype(int), np.floor(b_).astype(int)
    ton = np.array([0.78, 1.0, 1.18], np.float32)[(ia - ib) % 3]
    col = np.where(((ia + ib) % 2 == 0)[:, :, None], g_d1, g_d2) * ton[:, :, None]
    col = np.where(lat_a[:, :, None], g_d2 * 1.08, col)
    col = np.where(lat_b[:, :, None] & ~lat_a[:, :, None], g_d1 * 1.08, col)
    col = np.where(cadre[:, :, None], np.where(long_u[:, :, None], g_u, g_v) * 0.95, col)
    joint = (np.abs(eb - b) < 0.004) | (eb < 0.003)
    joint |= ~cadre & ((np.minimum(fa, 1 - fa) < 0.012) | (np.abs(fa - w) < 0.012) |
                       (np.minimum(fb, 1 - fb) < 0.012) | (np.abs(fb - w) < 0.012))
    col = col * np.where(joint, 0.55, 1.0)[:, :, None]
    col = col * np.array([1.05, 0.93, 0.78])[None, None, :] * 1.05
    return sauver("parquet_versailles_col", col)


def tex_caisson():
    """Fond peint d'un caisson : fleur stylisée dans l'octogone, rosettes dans les coins."""
    n = 512
    y, x = (np.mgrid[0:n, 0:n].astype(np.float32) + 0.5) / n - 0.5
    c = 0.29
    octo = (np.abs(x) + np.abs(y)) < (1 - c)
    col = np.zeros((n, n, 3), np.float32)
    col[:] = (0.13, 0.20, 0.15)
    col[~octo] = (0.09, 0.13, 0.10)
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    feuille = (r > 0.12) & (r < 0.36) & (np.abs(np.sin(4 * th + math.pi / 4)) < (0.36 - r) * 2.6)
    col[feuille] = (0.30, 0.42, 0.24)
    petale = r < 0.22 * (0.45 + 0.55 * np.abs(np.cos(4 * th)))
    col[petale] = (0.70, 0.50, 0.20)
    col[r < 0.10 * (0.6 + 0.4 * np.abs(np.cos(6 * th)))] = (0.66, 0.35, 0.33)
    col[r < 0.035] = (0.80, 0.65, 0.30)
    for cx, cy in ((0.5, 0.5), (-0.5, 0.5), (0.5, -0.5), (-0.5, -0.5)):
        rr = np.hypot(x - cx, y - cy)
        tt = np.arctan2(y - cy, x - cx)
        col[(rr < 0.09 * (0.5 + 0.5 * np.abs(np.cos(2 * tt)))) & ~octo] = (0.66, 0.46, 0.20)
    col *= 1 + 0.18 * bruit(n, (16, 64), (0.6, 0.4), 11)[:, :, None]
    return sauver("caisson_col", flou(col, 0.8))


def tex_faience():
    n = 512
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n * 4
    i, j = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x % 1, y % 1
    var = RNG.uniform(0.75, 1.2, (4, 4)).astype(np.float32)[j % 4, i % 4]
    col = np.array([0.10, 0.36, 0.20])[None, None, :] * var[:, :, None]
    col = col * (0.85 + 0.3 * (1 - np.hypot(fx - 0.35, fy - 0.3)))[:, :, None]
    joint = (np.minimum(fx, 1 - fx) < 0.025) | (np.minimum(fy, 1 - fy) < 0.025)
    col[joint] = (0.55, 0.53, 0.48)
    return sauver("faience_col", col)


def recolore(src, nom, f, taille=None):
    a = charger(src, taille)
    return sauver(nom, f(a))


def peinture(nom, w, h, dessin, flou_r=1.2, grain=0.06):
    im = Image.new("RGB", (w, h))
    dr = ImageDraw.Draw(im)
    dessin(dr, w, h)
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(flou_r)), np.float32) / 255
    nz = bruit(max(w, h), (32, 128), (0.5, 0.5), hash(nom) % 1000)[:h, :w]
    a = a * (1 + grain * nz[:, :, None] * 2)
    return sauver(nom, a)


def d_marine(dr, w, h):
    r = np.random.default_rng(5)
    hor = int(h * 0.42)
    for yy in range(hor):
        t = yy / hor
        dr.line([(0, yy), (w, yy)], fill=(int(120 + 70 * t), int(140 + 60 * t), int(165 + 40 * t)))
    for _ in range(60):
        x, y = r.uniform(0, w), r.uniform(0, hor * 0.85)
        s = r.uniform(30, 110)
        g = int(r.uniform(150, 235))
        dr.ellipse([x - s, y - s * 0.35, x + s, y + s * 0.35], fill=(g, g - 5, g - 15))
    dr.polygon([(0, hor), (w * 0.15, hor - 25), (w * 0.3, hor - 10), (w * 0.5, hor - 30), (w * 0.62, hor - 8),
                (w, hor - 18), (w, hor), (0, hor)], fill=(110, 115, 130))
    for yy in range(hor, h):
        t = (yy - hor) / (h - hor)
        dr.line([(0, yy), (w, yy)], fill=(int(70 - 25 * t), int(110 - 30 * t), int(135 - 25 * t)))
    for _ in range(900):
        x, y = r.uniform(0, w), r.uniform(hor, h)
        L = r.uniform(6, 30) * (1 + (y - hor) / h * 2)
        g = r.uniform(-1, 1)
        c = (int(95 + 50 * g), int(140 + 45 * g), int(160 + 40 * g))
        dr.line([(x, y), (x + L, y)], fill=c, width=2)
    for k in range(7):
        x0 = r.uniform(0.05, 0.85) * w
        y0 = hor + 8 + k * 6
        L = r.uniform(80, 230)
        dr.polygon([(x0, y0), (x0 + L, y0), (x0 + L * 0.93, y0 + 18), (x0 + L * 0.05, y0 + 18)], fill=(80, 82, 88))
        dr.rectangle([x0 + L * 0.3, y0 - 30, x0 + L * 0.6, y0], fill=(105, 108, 112))
        dr.rectangle([x0 + L * 0.4, y0 - 55, x0 + L * 0.47, y0 - 30], fill=(60, 60, 65))
        dr.line([(x0 + L * 0.35, y0 - 90), (x0 + L * 0.35, y0)], fill=(50, 50, 50), width=2)
        for s_ in range(5):
            dr.ellipse([x0 + L * 0.42 + s_ * 18, y0 - 75 - s_ * 14, x0 + L * 0.42 + s_ * 18 + 40,
                        y0 - 55 - s_ * 14], fill=(70, 68, 66))
    x0, y0 = w * 0.1, hor + 60
    dr.polygon([(x0, y0), (x0 + 330, y0 - 10), (x0 + 300, y0 + 40), (x0 + 30, y0 + 45)], fill=(85, 85, 92))
    dr.rectangle([x0 + 120, y0 - 70, x0 + 220, y0], fill=(110, 112, 118))
    dr.rectangle([x0 + 40, y0 - 60, x0 + 46, y0 + 10], fill=(40, 40, 120))
    dr.rectangle([x0 + 46, y0 - 60, x0 + 52, y0 + 10], fill=(235, 235, 235))
    dr.rectangle([x0 + 52, y0 - 60, x0 + 58, y0 + 10], fill=(190, 30, 30))
    for _ in range(26):
        x, y = r.uniform(0, w), r.uniform(hor + 40, h - 20)
        s = r.uniform(14, 34) * (1 + (y - hor) / h)
        c = [(235, 230, 215), (200, 70, 50), (230, 190, 120)][int(r.integers(3))]
        dr.polygon([(x, y), (x + s * 0.1, y - s * 1.6), (x + s * 0.9, y - s * 0.1)], fill=c)
        dr.polygon([(x - s * 0.3, y), (x + s * 1.1, y), (x + s * 0.9, y + s * 0.3), (x - s * 0.1, y + s * 0.3)],
                   fill=(70, 50, 35))


def d_portrait(dr, w, h):
    for yy in range(h):
        t = yy / h
        c = (int(150 + 40 * (1 - t)), int(160 + 25 * (1 - t)), int(175 - 30 * t)) if t < 0.45 else \
            (int(170 - 40 * t), int(135 - 30 * t), int(80 - 20 * t))
        dr.line([(0, yy), (w, yy)], fill=c)
    cx = w * 0.5
    dr.rectangle([cx - 30, h * 0.58, cx - 6, h * 0.92], fill=(225, 225, 215))
    dr.rectangle([cx + 6, h * 0.58, cx + 30, h * 0.92], fill=(220, 220, 210))
    dr.ellipse([cx - 40, h * 0.92, cx - 2, h * 0.95], fill=(40, 30, 25))
    dr.ellipse([cx + 2, h * 0.92, cx + 40, h * 0.95], fill=(40, 30, 25))
    dr.polygon([(cx - 48, h * 0.30), (cx + 48, h * 0.30), (cx + 40, h * 0.60), (cx - 40, h * 0.60)],
               fill=(235, 235, 228))
    dr.rectangle([cx - 46, h * 0.44, cx + 46, h * 0.47], fill=(180, 150, 70))
    dr.ellipse([cx - 18, h * 0.19, cx + 18, h * 0.29], fill=(200, 160, 125))
    dr.ellipse([cx - 16, h * 0.18, cx + 16, h * 0.22], fill=(60, 45, 35))
    dr.ellipse([cx + 42, h * 0.50, cx + 82, h * 0.56], fill=(238, 235, 225))
    dr.rectangle([cx - 70, h * 0.32, cx - 48, h * 0.58], fill=(230, 230, 222))


def d_sombre(dr, w, h):
    for yy in range(h):
        t = yy / h
        dr.line([(0, yy), (w, yy)], fill=(int(60 - 25 * t), int(50 - 20 * t), int(35 - 15 * t)))
    dr.ellipse([w * 0.25, h * 0.25, w * 0.75, h * 0.7], fill=(110, 85, 55))
    dr.ellipse([w * 0.38, h * 0.18, w * 0.6, h * 0.38], fill=(150, 115, 85))


def d_paysage(dr, w, h):
    for yy in range(h):
        t = yy / h
        c = (int(140 + 90 * t), int(150 + 60 * t), int(190 - 20 * t)) if t < 0.6 else (90, 105, 70)
        dr.line([(0, yy), (w, yy)], fill=c)
    dr.polygon([(0, h * 0.62), (w * 0.3, h * 0.5), (w * 0.55, h * 0.6), (w, h * 0.52), (w, h), (0, h)],
               fill=(80, 95, 60))
    dr.ellipse([w * 0.6, h * 0.2, w * 0.75, h * 0.32], fill=(250, 210, 140))


def d_couchant(dr, w, h):
    for yy in range(h):
        t = yy / h
        c = (int(230 - 60 * t), int(170 - 70 * t), int(90 + 40 * t)) if t < 0.55 else (60, 55, 70)
        dr.line([(0, yy), (w, yy)], fill=c)
    for k in range(7):
        x = w * (0.05 + 0.13 * k)
        hh = h * (0.12 + 0.1 * ((k * 37) % 5) / 5)
        dr.rectangle([x, h * 0.55 - hh, x + w * 0.1, h * 0.75], fill=(70, 55, 60))
    dr.ellipse([w * 0.45, h * 0.32, w * 0.58, h * 0.44], fill=(255, 225, 150))


def d_fleurs(dr, w, h):
    r = np.random.default_rng(9)
    dr.rectangle([0, 0, w, h], fill=(45, 35, 25))
    dr.ellipse([w * 0.38, h * 0.55, w * 0.62, h * 0.95], fill=(120, 95, 60))
    for _ in range(70):
        x, y = r.normal(w * 0.5, w * 0.17), r.normal(h * 0.4, h * 0.18)
        s = r.uniform(5, 16)
        c = [(200, 90, 100), (230, 220, 200), (210, 170, 70), (60, 90, 50), (50, 80, 45)][int(r.integers(5))]
        dr.ellipse([x - s, y - s, x + s, y + s], fill=c)


def d_tapisserie(dr, w, h):
    r = np.random.default_rng(13)
    dr.rectangle([0, 0, w, h], fill=(95, 105, 75))
    dr.rectangle([0, 0, w, h * 0.35], fill=(150, 160, 140))
    for _ in range(40):
        x, y = r.uniform(0, w), r.uniform(h * 0.2, h * 0.5)
        s = r.uniform(20, 50)
        dr.ellipse([x - s, y - s, x + s, y + s], fill=(int(r.uniform(50, 90)), int(r.uniform(80, 110)), 55))
    for k in range(5):
        x = w * (0.12 + 0.18 * k)
        y = h * (0.62 + 0.05 * (k % 2))
        c = [(150, 50, 40), (60, 70, 120), (180, 150, 90), (120, 40, 60), (70, 100, 120)][k]
        dr.polygon([(x - 18, y + 90), (x + 18, y + 90), (x + 12, y), (x - 12, y)], fill=c)
        dr.ellipse([x - 10, y - 25, x + 10, y - 3], fill=(200, 160, 120))
    dr.rectangle([0, 0, w, h], outline=(110, 70, 40), width=int(w * 0.06))
    dr.rectangle([w * 0.06, h * 0.06, w * 0.94, h * 0.94], outline=(170, 130, 70), width=4)


def tex_tapis(nom, w, h, fond, bord, accent, medaillon, graine):
    v, u = (np.mgrid[0:h, 0:w].astype(np.float32) + 0.5)
    u, v = u / w, v / h
    e = np.minimum(np.minimum(u, 1 - u) * w, np.minimum(v, 1 - v) * h) / min(w, h)
    col = np.zeros((h, w, 3), np.float32)
    col[:] = fond
    f1 = np.sin(u * 70 + np.sin(v * 25) * 2) * np.sin(v * 55 + np.sin(u * 20) * 2) \
        + 0.6 * np.sin(u * 31 + v * 23 + graine)
    col[f1 > 0.85] = accent
    col[f1 < -1.1] = bord
    mx = ((u - 0.5) / 0.20) ** 2 + ((v - 0.5) / 0.24) ** 2
    col[mx < 1] = medaillon
    col[(mx > 0.55) & (mx < 0.7)] = accent
    col[mx < 0.15] = bord
    b = (e < 0.11)
    col[b] = bord
    ff = np.sin((u + v) * 140) > 0.6
    col[b & ff & (e > 0.025) & (e < 0.09)] = accent
    col[(np.abs(e - 0.11) < 0.006) | (np.abs(e - 0.02) < 0.004)] = fond
    col = col * (1 + 0.10 * bruit(max(w, h), (64, 256), (0.5, 0.5), graine)[:h, :w, None])
    return sauver(nom, flou(col, 0.7))


def tex_rayures(nom, c1, c2, periode=48, n=256):
    v, u = np.mgrid[0:n, 0:n].astype(np.float32)
    t = (np.sin(u / periode * 2 * math.pi) > 0.2).astype(np.float32)
    t = flou(t, 1.5)
    col = np.array(c1)[None, None, :] * (1 - t[:, :, None]) + np.array(c2)[None, None, :] * t[:, :, None]
    moire = 0.06 * np.sin(u * 0.4 + np.sin(v * 0.07) * 6)
    return sauver(nom, col * (1 + moire[:, :, None]))


log("textures…")
TX = {}
TX["damas_salon"] = damas("damas_salon_col", (0.80, 0.80, 0.81), (0.87, 0.87, 0.88))
TX["damas_billard"] = damas("damas_billard_col", (0.80, 0.73, 0.58), (0.89, 0.84, 0.70))
TX["damas_ouest"] = damas("damas_ouest_col", (0.76, 0.79, 0.72), (0.84, 0.86, 0.80))
TX["damas_no"] = damas("damas_no_col", (0.62, 0.30, 0.27), (0.70, 0.38, 0.34))
TX["damas_deg"] = damas("damas_deg_col", (0.78, 0.72, 0.60), (0.85, 0.80, 0.68))
TX["versailles"] = tex_versailles()
TX["caisson"] = tex_caisson()
TX["faience"] = tex_faience()
TX["acajou"] = recolore(ph("american_walnut_veneer", "diff"), "acajou_col",
                        lambda a: a * np.array([1.10, 0.72, 0.58])[None, None, :] * 0.95)
TX["noyer"] = recolore(ph("american_walnut_veneer", "diff"), "noyer_col",
                       lambda a: a * np.array([0.95, 0.80, 0.68])[None, None, :] * 0.85)


def _rose(a):
    L = lum(a)
    Ln = (L - L.mean()) / (L.std() + 1e-6)
    base = np.array([0.80, 0.55, 0.52])[None, None, :]
    veine = np.array([0.55, 0.20, 0.18])[None, None, :]
    t = np.clip(-Ln * 0.5 + 0.2, 0, 1)[:, :, None]
    return base * (1 - t) + veine * t


TX["marbre_rose"] = recolore(ph("marble_01", "diff"), "marbre_rose_col", _rose)
def peinture_photo_marine():
    """Recadrage rectifié de la toile marine visible dans la photo P30, sans décor de la pièce."""
    source = Image.open(os.path.join(RACINE, "sources", "pixel", "PXL_20261115_134858525.jpg")).convert("RGB")
    # Coins intérieurs du tableau repérés sur P30 (ordre PIL QUAD : HG, BG, BD, HD).
    w0, h0 = source.size
    ref_w, ref_h = 678.0, 900.0
    coins = [(109, 309), (111, 453), (457, 494), (462, 353)]
    quad = tuple(v for x, y in coins for v in (x * w0 / ref_w, y * h0 / ref_h))
    image = source.transform((1200, 650), Image.Transform.QUAD, quad, Image.Resampling.BICUBIC)
    # La lampe masque seulement le coin inférieur droit de la toile sur P30. On restaure ce
    # petit morceau, sans retoucher le reste de la peinture photographiée.
    retouche = os.path.join(RACINE, "assets", "generes", "tableaux", "retouche_lampe_marine.png")
    if os.path.exists(retouche):
        reprise = Image.open(retouche).convert("RGB").resize(image.size, Image.Resampling.LANCZOS)
        masque = Image.new("L", image.size, 0)
        ImageDraw.Draw(masque).polygon([(885, 650), (872, 620), (874, 590), (895, 562), (923, 535),
                                        (950, 510), (980, 516), (1008, 538), (1033, 565), (1056, 590),
                                        (1090, 608), (1130, 620), (1160, 650)], fill=255)
        image = Image.composite(reprise, image, masque.filter(ImageFilter.GaussianBlur(8)))
    chemin = os.path.join(RACINE, "assets", "generes", "tableaux")
    os.makedirs(chemin, exist_ok=True)
    image.save(os.path.join(chemin, "tableau_marine_P30.jpg"), quality=94)
    return sauver("tableau_marine", np.asarray(image, np.float32) / 255.0)


TX["marine"] = peinture_photo_marine()
TX["portrait"] = peinture("tableau_portrait", 360, 520, d_portrait, 1.6)
TX["sombre"] = peinture("tableau_sombre", 300, 400, d_sombre, 3)
TX["paysage"] = peinture("tableau_paysage", 400, 280, d_paysage, 2)
TX["couchant"] = peinture("tableau_couchant", 300, 375, d_couchant, 2)
TX["fleurs"] = peinture("dessus_porte_fleurs", 512, 220, d_fleurs, 2)
TX["tapisserie"] = peinture("tapisserie_cheminee", 400, 400, d_tapisserie, 1.5)
TX["tapis_ivoire"] = tex_tapis("tapis_ivoire", 1024, 790, (0.86, 0.80, 0.68), (0.45, 0.12, 0.12),
                               (0.22, 0.28, 0.45), (0.80, 0.70, 0.55), 1)
TX["tapis_rouge"] = tex_tapis("tapis_rouge", 1024, 768, (0.62, 0.20, 0.20), (0.25, 0.10, 0.18),
                              (0.80, 0.62, 0.55), (0.25, 0.30, 0.45), 2)
TX["tapis_bleu"] = tex_tapis("tapis_bleu", 1024, 768, (0.22, 0.26, 0.40), (0.50, 0.15, 0.14),
                             (0.85, 0.78, 0.62), (0.70, 0.55, 0.40), 3)
TX["rideau_salon"] = tex_rayures("rideau_salon", (0.78, 0.66, 0.36), (0.70, 0.68, 0.62))
TX["rideau_billard"] = tex_rayures("rideau_billard", (0.86, 0.80, 0.68), (0.82, 0.76, 0.64), 30)
TX["rideau_vert"] = tex_rayures("rideau_vert", (0.90, 0.85, 0.74), (0.85, 0.66, 0.62), 40)

# ----------------------------------------------------------------------------------------------
# Matériaux
# ----------------------------------------------------------------------------------------------
MATS, UVS = {}, {}


def materiau(nom, couleur=(0.8, 0.8, 0.8), rugosite=0.5, metal=0.0, tex=None, uv=1.0, emission=None,
             deux_faces=False, alpha=None, nrm_force=0.5):
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
    if alpha is not None:
        p.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            m.blend_method = "BLEND"
    if tex:
        c, nrm, rg = (tuple(tex) + (None, None))[:3]
        if c:
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


M = {}
M["parquet"] = materiau("parquet_baton", tex=(ph("herringbone_parquet", "diff", "2k"),
                                              ph("herringbone_parquet", "nor_gl", "2k"),
                                              ph("herringbone_parquet", "rough", "2k")), uv=1.7, rugosite=0.35)
M["versailles"] = materiau("parquet_versailles", tex=(TX["versailles"], ph("oak_wood_planks", "nor_gl"), None),
                           uv=2.0, rugosite=0.3, nrm_force=0.2)
for k in ("salon", "billard", "ouest", "no", "deg"):
    M["damas_" + k] = materiau("tenture_" + k, tex=(TX["damas_" + k], None, T_DAMAS_RGH), uv=0.70)
M["gris_bleu"] = materiau("peint_gris_bleu", srgb(160, 172, 186), 0.45)
M["gris_bleu_fonce"] = materiau("peint_gris_bleu_fonce", srgb(132, 146, 162), 0.45)
M["blanc"] = materiau("stuc_blanc", srgb(232, 230, 224), 0.7)
M["creme"] = materiau("boiserie_creme", srgb(228, 223, 204), 0.45)
M["celadon"] = materiau("boiserie_celadon", srgb(176, 196, 180), 0.5)
M["or"] = materiau("dorure", srgb(214, 168, 80), 0.3, 1.0)
M["vert_eau"] = materiau("vert_eau", srgb(168, 192, 160), 0.5)
M["poutre"] = materiau("poutre_brun_rouge", srgb(105, 48, 32), 0.45)
M["caisson"] = materiau("caisson_peint", tex=(TX["caisson"], None, None), uv=1.0, rugosite=0.6)
M["noyer"] = materiau("noyer", tex=(TX["noyer"], ph("american_walnut_veneer", "nor_gl"),
                                    ph("american_walnut_veneer", "rough")), uv=0.9, rugosite=0.4, nrm_force=0.3)
M["acajou"] = materiau("acajou", tex=(TX["acajou"], ph("american_walnut_veneer", "nor_gl"), None), uv=0.9,
                       rugosite=0.3, nrm_force=0.3)
M["laiton"] = materiau("laiton", srgb(200, 160, 90), 0.28, 1.0)
M["bronze"] = materiau("bronze_patine", srgb(70, 50, 35), 0.45, 0.8)
M["argent"] = materiau("argent", srgb(205, 205, 210), 0.25, 1.0)
M["fer"] = materiau("fer_noir", (0.02, 0.02, 0.02), 0.45, 0.7)
M["verre"] = materiau("verre", (0.85, 0.9, 0.9), 0.05, alpha=0.25, deux_faces=True)
M["glace"] = materiau("glace_miroir", (0.9, 0.9, 0.9), 0.04, 1.0)
M["onyx"] = materiau("onyx", tex=(ph("marble_01", "diff"), ph("marble_01", "nor_gl"), None), uv=0.8,
                     rugosite=0.15, nrm_force=0.2)
M["marbre_rose"] = materiau("marbre_breche_rose", tex=(TX["marbre_rose"], None, None), uv=0.9, rugosite=0.18)
M["marbre_noir"] = materiau("marbre_noir", (0.02, 0.02, 0.02), 0.15)
M["foyer"] = materiau("foyer_suie", (0.01, 0.01, 0.01), 0.9)
M["faience"] = materiau("faience_verte", tex=(TX["faience"], None, None), uv=0.6, rugosite=0.12)
M["velours_rouge"] = materiau("velours_rouge", srgb(130, 25, 30), 0.85,
                              tex=(None, ph("velour_velvet", "nor_gl"), None), nrm_force=0.3)
M["tissu_creme"] = materiau("tissu_creme", srgb(225, 218, 200), 0.85)
M["abat_jour"] = materiau("abat_jour", srgb(235, 222, 190), 0.8, emission=(srgb(255, 230, 180), 0.6),
                          deux_faces=True)
M["porcelaine"] = materiau("porcelaine", srgb(238, 238, 240), 0.2)
M["bleu_porcelaine"] = materiau("porcelaine_bleue", srgb(60, 80, 150), 0.2)
M["feuille"] = materiau("feuillage", srgb(55, 95, 40), 0.6, deux_faces=True)
M["feuille_claire"] = materiau("feuillage_clair", srgb(90, 130, 55), 0.6, deux_faces=True)
M["tige"] = materiau("tige", srgb(110, 95, 60), 0.8)
M["pot_emaille"] = materiau("pot_emaille", srgb(60, 120, 120), 0.15)
M["terre_cuite"] = materiau("terre_cuite", srgb(170, 95, 60), 0.8)
M["drap"] = materiau("drap_billard", srgb(30, 120, 105), 0.9)
M["blanc_peint"] = materiau("blanc_peint", srgb(240, 238, 230), 0.4)
M["voile"] = materiau("voile_blanc", srgb(245, 242, 235), 0.7, deux_faces=True)
M["fonte"] = materiau("fonte_peinte", srgb(235, 230, 215), 0.4)
M["sortie"] = materiau("panneau_sortie", srgb(40, 200, 90), 0.5, emission=(srgb(40, 220, 90), 2.0))
M["cuir_bordeaux"] = materiau("cuir_bordeaux", srgb(100, 25, 30), 0.5)
M["frange"] = materiau("frange", srgb(225, 215, 190), 0.9)
M["tapisserie"] = materiau("tapisserie", tex=(TX["tapisserie"], None, None), rugosite=0.9)
M["fleurs"] = materiau("dessus_porte", tex=(TX["fleurs"], None, None), rugosite=0.6)
for k in ("marine", "portrait", "sombre", "paysage", "couchant"):
    M["toile_" + k] = materiau("toile_" + k, tex=(TX[k], None, None), rugosite=0.55)
for k in ("tapis_ivoire", "tapis_rouge", "tapis_bleu"):
    M[k] = materiau(k, tex=(TX[k], None, None), rugosite=0.95)
for k in ("rideau_salon", "rideau_billard", "rideau_vert"):
    M[k] = materiau(k, tex=(TX[k], None, None), uv=0.3, rugosite=0.55, deux_faces=True)
M["soie_jaune"] = materiau("soie_jaune", srgb(225, 185, 95), 0.45, deux_faces=True)


# ----------------------------------------------------------------------------------------------
# Constructeur de maillages (repris de coque.py, étendu : tours, tiges, UV explicites, lofts)
# ----------------------------------------------------------------------------------------------
class Rep:
    """Repère local d'un mur : origine o (x, y), t le long du mur, n vers l'intérieur de la pièce."""

    def __init__(self, o, t, n=None):
        self.o = Vector((o[0], o[1], 0))
        self.t = Vector((t[0], t[1], 0)).normalized()
        self.n = Vector((-self.t.y, self.t.x, 0)) if n is None else Vector((n[0], n[1], 0)).normalized()

    def p(self, s, d, z):
        return self.o + self.t * s + self.n * d + Vector((0, 0, z))


ID_REP = Rep((0, 0), (1, 0), (0, -1))     # objets locaux : face avant vers −Y


class Bld:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []
        self.uvx = []
        self.lay = self.bm.faces.layers.int.new("uvx")

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def v(self, co):
        return self.bm.verts.new(co)

    def face(self, vs, m, uv=None):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.mi(m)
        if uv is not None:
            self.uvx.append(uv)
            f[self.lay] = len(self.uvx)
        return f

    def solide(self, poly, z0, z1, m, mhaut=None):
        poly = ccw(poly)
        b = [self.v((x, y, z0)) for x, y in poly]
        h = [self.v((x, y, z1)) for x, y in poly]
        n = len(b)
        for i in range(n):
            j = (i + 1) % n
            self.face([b[i], b[j], h[j], h[i]], m)
        self.face(list(reversed(b)), m)
        self.face(h, mhaut or m)

    def boite(self, x0, y0, z0, x1, y1, z1, m):
        self.solide([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], min(z0, z1), max(z0, z1), m)

    def br(self, r, s0, s1, d0, d1, z0, z1, m):
        """Boîte dans le repère r (s le long, d vers l'intérieur)."""
        pts = [r.p(s0, d0, 0), r.p(s1, d0, 0), r.p(s1, d1, 0), r.p(s0, d1, 0)]
        self.solide([(p.x, p.y) for p in pts], min(z0, z1), max(z0, z1), m)

    def prisme_r(self, r, profil, d0, d1, m):
        """Profil (s, z) du plan du mur, extrudé de d0 à d1."""
        if aire(profil) < 0:
            profil = profil[::-1]
        a = [self.v(r.p(s, d0, z)) for s, z in profil]
        b = [self.v(r.p(s, d1, z)) for s, z in profil]
        n = len(a)
        for i in range(n):
            j = (i + 1) % n
            self.face([a[i], a[j], b[j], b[i]], m)
        self.face(list(reversed(a)), m)
        self.face(b, m)

    def tour(self, cx, cy, profil, m, n=16, z0=0.0):
        """Solide de révolution, profil [(r, z)] de bas en haut."""
        anneaux = []
        for r, z in profil:
            if r < 1e-4:
                anneaux.append([self.v((cx, cy, z0 + z))])
            else:
                anneaux.append([self.v((cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n),
                                        z0 + z)) for k in range(n)])
        for a, b in zip(anneaux[:-1], anneaux[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            for k in range(n):
                k2 = (k + 1) % n
                if len(a) == 1:
                    self.face([a[0], b[k], b[k2]], m)
                elif len(b) == 1:
                    self.face([a[k], a[k2], b[0]], m)
                else:
                    self.face([a[k], a[k2], b[k2], b[k]], m)
        if len(anneaux[0]) > 1:
            self.face(list(reversed(anneaux[0])), m)
        if len(anneaux[-1]) > 1:
            self.face(anneaux[-1], m)

    def tige(self, p0, p1, r, m, n=6, r1=None):
        p0, p1 = Vector(p0), Vector(p1)
        ax = p1 - p0
        if ax.length < 1e-6:
            return
        a = ax.normalized()
        u = a.cross(Vector((0, 0, 1)) if abs(a.z) < 0.9 else Vector((1, 0, 0))).normalized()
        w = a.cross(u)
        r1 = r if r1 is None else r1
        A = [self.v(p0 + (u * math.cos(2 * math.pi * k / n) + w * math.sin(2 * math.pi * k / n)) * r) for k in range(n)]
        B = [self.v(p1 + (u * math.cos(2 * math.pi * k / n) + w * math.sin(2 * math.pi * k / n)) * r1) for k in range(n)]
        for k in range(n):
            k2 = (k + 1) % n
            self.face([A[k], A[k2], B[k2], B[k]], m)
        self.face(list(reversed(A)), m)
        self.face(B, m)

    def quad_uv(self, pts, m, uvs):
        vs = [self.v(p) for p in pts]
        return self.face(vs, m, uvs)

    def nappe(self, grille, m, uvs=None):
        """Surface ouverte : grille[i][j] de points ; uvs[i][j] facultatif."""
        V = [[self.v(p) for p in ligne] for ligne in grille]
        for i in range(len(V) - 1):
            for j in range(len(V[0]) - 1):
                uv = None
                if uvs is not None:
                    uv = [uvs[i][j], uvs[i][j + 1], uvs[i + 1][j + 1], uvs[i + 1][j]]
                self.face([V[i][j], V[i][j + 1], V[i + 1][j + 1], V[i + 1][j]], m, uv)

    def objet(self, nom, col=COL, recalc=True):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            k = f[self.lay]
            if k:
                uv = self.uvx[k - 1]
                for lp, c in zip(f.loops, uv):
                    lp[uvl].uv = c
                continue
            nrm = f.normal
            ax = max(range(3), key=lambda i: abs(nrm[i]))
            s = UVS.get(self.mats[f.material_index].name, 1.0) if self.mats else 1.0
            for lp in f.loops:
                co = lp.vert.co
                if ax == 2:
                    uv = (co.x / s, co.y / s)
                elif ax == 0:
                    uv = (co.y / s * (1 if nrm.x > 0 else -1), co.z / s)
                else:
                    uv = (co.x / s * (-1 if nrm.y > 0 else 1), co.z / s)
                lp[uvl].uv = uv
        me = bpy.data.meshes.new(nom)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(nom, me)
        col.objects.link(ob)
        return ob


def proto(nom, b, recalc=True):
    ob = b.objet("proto_" + nom, PROTOS, recalc)
    ob.hide_render = True
    return ob


NOMS = {}


def nom_unique(nom):
    if nom not in NOMS and nom not in bpy.data.objects:
        NOMS[nom] = 1
        return nom
    k = NOMS.get(nom, 1) + 1
    while "%s_%d" % (nom, k) in bpy.data.objects:
        k += 1
    NOMS[nom] = k
    return "%s_%d" % (nom, k)


def poser(src, nom, x, y, z=0.0, face=None, rot=0.0, ech=1.0):
    """Instance (maillage partagé) ; face = direction (x, y) vers laquelle regarde l'avant (−Y local)."""
    ob = bpy.data.objects.new(nom_unique(nom), src.data)
    ob.location = (x, y, z)
    a = rot if face is None else math.atan2(face[1], face[0]) + math.pi / 2
    ob.rotation_euler = (0, 0, a)
    ob.scale = (ech, ech, ech) if isinstance(ech, (int, float)) else ech
    COL.objects.link(ob)
    return ob


LUMIERES = []


def lumiere(nom, x, y, z, puissance, rayon=0.25, couleur=(1.0, 0.86, 0.68)):
    li = bpy.data.lights.new(nom, "POINT")
    li.energy = puissance
    li.shadow_soft_size = rayon
    li.color = couleur
    ob = bpy.data.objects.new(nom, li)
    ob.location = (x, y, z)
    COL.objects.link(ob)
    LUMIERES.append(ob)
    return ob


# ----------------------------------------------------------------------------------------------
# Assets Poly Haven (CC0) : importés une fois, réutilisés en instances ; recoloration par texture
# ----------------------------------------------------------------------------------------------
def importer(nom):
    avant = set(bpy.data.objects)
    lc = bpy.context.view_layer.layer_collection.children["protos"]
    bpy.context.view_layer.active_layer_collection = lc
    bpy.ops.import_scene.gltf(filepath=os.path.join(PH, "polyhaven-" + nom, nom + "_1k.gltf"))
    obs = [o for o in bpy.data.objects if o not in avant and o.type == "MESH"]
    for o in bpy.data.objects:
        if o not in avant and o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob.name = "proto_" + nom
    ob.hide_render = True
    return ob


def variante(src, nom, f):
    """Copie du maillage avec la couleur de base de chaque matériau recolorée par f(rgb)."""
    me = src.data.copy()
    for i, m in enumerate(me.materials):
        m2 = m.copy()
        m2.name = ID + "_" + nom + "_" + str(i)
        for n in m2.node_tree.nodes:
            if n.type == "TEX_IMAGE" and any(l.to_socket.name == "Base Color" for l in n.outputs[0].links):
                im = n.image
                w, h = im.size
                a = np.empty(w * h * 4, np.float32)
                im.pixels.foreach_get(a)
                a = a.reshape(h, w, 4)[::-1, :, :3]
                a = np.clip(a, 0, 1) ** (1 / 2.2)
                n.image = bpy.data.images.load(sauver(nom + "_" + str(i), f(a)), check_existing=True)
        me.materials[i] = m2
    ob = bpy.data.objects.new("proto_" + nom, me)
    PROTOS.objects.link(ob)
    ob.hide_render = True
    return ob


def sat_teinte(a):
    mx, mn = a.max(axis=2), a.min(axis=2)
    return (mx - mn) / (mx + 1e-4), mx


log("assets Poly Haven…")
P_BERGERE0 = importer("ArmChair_01")
P_FAUTEUIL0 = importer("GreenChair_01")
P_LUSTRE = importer("Chandelier_03")
P_CONSOLE_LP = importer("ClassicConsole_01")
P_MONSTERA = importer("potted_plant_02")
P_CADRE = importer("fancy_picture_frame_01")
P_CANAPE = importer("Sofa_01")
P_VASE = importer("antique_ceramic_vase_01")
P_GUERIDON = importer("round_wooden_table_01")
P_MIROIR = importer("ornate_mirror_01")


def _bergere(a):
    # salon : bois laqué gris, velours gris argent (P27-P29)
    L = lum(a)[:, :, None]
    sombre = (L < 0.22).astype(np.float32)
    bois = np.array([0.62, 0.62, 0.60])[None, None, :] * (0.75 + L)
    tissu = np.array([0.72, 0.71, 0.70])[None, None, :] * (0.55 + 0.9 * L)
    return bois * sombre + tissu * (1 - sombre)


def _medaillon(a):
    # billard : bois acajou, tissu blanc (P32-P34)
    s, v = sat_teinte(a)
    vert = ((a[:, :, 1] > a[:, :, 0] * 1.05) & (s > 0.12))[:, :, None].astype(np.float32)
    L = lum(a)[:, :, None]
    tissu = np.array([0.93, 0.91, 0.86])[None, None, :] * (0.7 + 0.8 * L)
    bois = a * np.array([1.25, 0.85, 0.7])[None, None, :]
    return tissu * vert + bois * (1 - vert)


def _louis_xv(a):
    # salon vert : bois laqué crème, tissu fleuri lilas (W07)
    s, v = sat_teinte(a)
    vert = ((a[:, :, 1] > a[:, :, 0] * 1.05) & (s > 0.12))[:, :, None].astype(np.float32)
    L = lum(a)[:, :, None]
    n = flou(np.clip(bruit(a.shape[0], (24, 96), (0.6, 0.4), 4) * 4 + 0.5, 0, 1), 1)[:a.shape[0], :a.shape[1], None]
    tissu = np.array([0.90, 0.88, 0.90])[None, None, :] * (1 - n) + np.array([0.70, 0.58, 0.75])[None, None, :] * n
    tissu = tissu * (0.65 + 0.7 * L)
    bois = np.array([0.88, 0.85, 0.76])[None, None, :] * (0.7 + 0.6 * L)
    return tissu * vert + bois * (1 - vert)


P_BERGERE = variante(P_BERGERE0, "bergere_grise", _bergere)
P_MEDAILLON = variante(P_FAUTEUIL0, "fauteuil_medaillon", _medaillon)
P_LOUIS_XV = variante(P_FAUTEUIL0, "fauteuil_louis_xv", _louis_xv)
P_FAUTEUIL_VERT = P_FAUTEUIL0


# ----------------------------------------------------------------------------------------------
# Murs des pièces : segments, ouvertures (portes de coque.json, baies de bati.py D-025)
# ----------------------------------------------------------------------------------------------
FENETRES = {
    # (point sur le nu intérieur, largeur, bas, haut)
    "salon": [((2.302, 9.70), 1.10, 0.0, 3.30), ((-2.302, 9.70), 1.10, 0.0, 3.30), ((0.0, 10.65), 1.50, 0.90, 3.30)],
    "billard": [((5.25, 8.15), 1.45, 0.0, 3.70), ((8.85, 8.15), 1.45, 0.0, 3.70)],
    "salon_vert": [((14.4, 8.85), 1.45, 0.0, 3.70), ((17.4, 6.9), 1.45, 0.0, 3.70)],
    "salon_ouest": [((-8.85, 8.15), 1.45, 0.0, 3.70), ((-5.25, 8.15), 1.45, 0.0, 3.70)],
    "piece_no": [((-14.4, -8.85), 1.35, 0.45, 3.70), ((-17.4, -6.9), 1.35, 0.45, 3.70)],
    "degagement_est": [],
}


def segments(pid):
    poly = ccw(PIECES[pid]["polygone_interieur"])
    out = []
    for i in range(len(poly)):
        P = Vector((*poly[i], 0))
        Q = Vector((*poly[(i + 1) % len(poly)], 0))
        d = Q - P
        L = d.length
        d /= L
        out.append(dict(P=P, Q=Q, d=d, n=Vector((-d.y, d.x, 0)), L=L, ouv=[], i=i))
    return out


def projeter(segs, pt, tol):
    best = None
    c = Vector((pt[0], pt[1], 0))
    for s in segs:
        t = (c - s["P"]).dot(s["d"])
        e = abs((c - s["P"]).dot(s["n"]))
        if -0.3 < t < s["L"] + 0.3 and e < tol and (best is None or e < best[2]):
            best = (s, t, e)
    return best


SEGS = {}
for pid in MES_PIECES:
    segs = segments(pid)
    for po in PIECES[pid]["portes"]:
        s, t, e = projeter(segs, po["centre"], 0.45)
        u0, u1 = max(0.0, t - po["largeur"] / 2), min(s["L"], t + po["largeur"] / 2)
        s["ouv"].append(dict(u0=u0, u1=u1, z0=0.0, z1=po["hauteur"], genre="porte", nom=po["nom"],
                             autre=[x for x in po["relie"] if x != pid][0]))
    for pt, w, za, zb in FENETRES[pid]:
        s, t, e = projeter(segs, pt, 0.2)
        s["ouv"].append(dict(u0=t - w / 2, u1=t + w / 2, z0=za, z1=zb, genre="fenetre", nom="baie"))
    SEGS[pid] = segs

CARD = {"nord": (0, 1), "sud": (0, -1), "est": (-1, 0), "ouest": (1, 0)}


def seg_card(pid, cote, coord):
    nx, ny = CARD[cote]
    k = 0 if cote in ("nord", "sud") else 1
    for s in SEGS[pid]:
        if abs(s["n"].x - nx) < 1e-3 and abs(s["n"].y - ny) < 1e-3:
            lo, hi = sorted((s["P"][k], s["Q"][k]))
            if lo - 1e-6 <= coord <= hi + 1e-6:
                return s
    raise ValueError((pid, cote, coord))


def rep_mur(pid, cote, coord):
    """Repère au point du mur (coord = x pour nord/sud, y pour est/ouest), s croissant le long du mur."""
    s = seg_card(pid, cote, coord)
    o = Vector((coord, s["P"].y)) if cote in ("nord", "sud") else Vector((s["P"].x, coord))
    return Rep(o, s["d"], s["n"])


def contre(pid, cote, coord, prof, ecart=0.05):
    s = seg_card(pid, cote, coord)
    base = Vector((coord, s["P"].y, 0)) if cote in ("nord", "sud") else Vector((s["P"].x, coord, 0))
    p = base + s["n"] * (prof / 2 + ecart)
    return p.x, p.y, (s["n"].x, s["n"].y)


def rep_seg(s, u):
    return Rep(s["P"] + s["d"] * u, s["d"], s["n"])


def bande(b, s, z0, z1, d0, d1, m, marge=0.0, genres=("porte", "fenetre")):
    """Bande de revêtement sur un segment, découpée autour des ouvertures (élargies de marge)."""
    ouvs = [(o["u0"] - marge, o["u1"] + marge, o["z0"], o["z1"] + marge) for o in s["ouv"] if o["genre"] in genres]
    zs = sorted(set([z0, z1] + [max(z0, min(z1, z)) for o in ouvs for z in (o[2], o[3])]))
    r = rep_seg(s, 0)
    for za, zb in zip(zs[:-1], zs[1:]):
        if zb - za < 1e-4:
            continue
        zc = (za + zb) / 2
        cuts = sorted((max(0, o[0]), min(s["L"], o[1])) for o in ouvs if o[2] < zc < o[3])
        u = 0.0
        for c0, c1 in cuts + [(s["L"], s["L"])]:
            if c0 - u > 0.005:
                b.br(r, u, c0, d0, d1, za, zb, m)
            u = max(u, c1)


def intervalles_libres(s, z0, z1, marge):
    ouvs = sorted((o["u0"] - marge, o["u1"] + marge) for o in s["ouv"] if o["z0"] < z1 and o["z1"] > z0)
    out, u = [], 0.0
    for c0, c1 in ouvs + [(s["L"], s["L"])]:
        if c0 - u > 0.25:
            out.append((u, min(c0, s["L"])))
        u = max(u, c1)
    return out


def cadre_r(b, r, s0, s1, z0, z1, d0, d1, larg, m):
    """Cadre (4 baguettes) dans le plan du mur."""
    b.br(r, s0, s1, d0, d1, z0, z0 + larg, m)
    b.br(r, s0, s1, d0, d1, z1 - larg, z1, m)
    b.br(r, s0, s0 + larg, d0, d1, z0 + larg, z1 - larg, m)
    b.br(r, s1 - larg, s1, d0, d1, z0 + larg, z1 - larg, m)


def panneaux(b, s, z0, z1, d_fond, larg_cible, m_cadre, m_fond=None, marge=0.18, retrait=0.08, baguette=0.035,
             saillie=0.012, filet=None):
    """Panneaux moulurés répartis entre les ouvertures ; fond facultatif ; filet doré facultatif."""
    r = rep_seg(s, 0)
    for u0, u1 in intervalles_libres(s, z0, z1, marge):
        L = u1 - u0
        n = max(1, int(round(L / larg_cible)))
        w = L / n
        for k in range(n):
            a, c = u0 + k * w + retrait, u0 + (k + 1) * w - retrait
            if c - a < 0.15:
                continue
            if m_fond is not None:
                b.br(r, a, c, d_fond, d_fond + 0.004, z0, z1, m_fond)
            cadre_r(b, r, a, c, z0, z1, d_fond, d_fond + saillie, baguette, m_cadre)
            if filet is not None:
                cadre_r(b, r, a + 0.07, c - 0.07, z0 + 0.07, z1 - 0.07, d_fond, d_fond + 0.008, 0.012, filet)


def chambranles(b, pid, m, larg=0.14, saillie=0.045, genres=("porte",), dessus=None):
    for s in SEGS[pid]:
        r = rep_seg(s, 0)
        for o in s["ouv"]:
            if o["genre"] not in genres:
                continue
            u0, u1, z0, z1 = o["u0"], o["u1"], o["z0"], o["z1"]
            if z0 > 0.01:
                b.br(r, u0 - larg, u1 + larg, 0, saillie, z0 - larg * 0.6, z0, m)
            b.br(r, u0 - larg, u0, 0, saillie, z0, z1 + larg, m)
            b.br(r, u1, u1 + larg, 0, saillie, z0, z1 + larg, m)
            b.br(r, u0 - larg, u1 + larg, 0, saillie, z1, z1 + larg, m)
            b.br(r, u0 - larg * 0.4, u0 - larg * 0.25, saillie, saillie + 0.01, z0, z1 + larg * 0.75, m)
            b.br(r, u1 + larg * 0.25, u1 + larg * 0.4, saillie, saillie + 0.01, z0, z1 + larg * 0.75, m)
            if dessus:
                dessus(b, r, o)


def loft(b, poly, profil, m):
    """Moulure balayée le long du polygone fermé (profil [(retrait, z)] du mur vers le plafond)."""
    anneaux = []
    for d, z in profil:
        pts = decaler(poly, d) if d > 1e-6 else list(poly)
        anneaux.append([b.v((x, y, z)) for x, y in pts])
    n = len(poly)
    for a, c in zip(anneaux[:-1], anneaux[1:]):
        for i in range(n):
            j = (i + 1) % n
            b.face([a[i], c[i], c[j], a[j]], m)


def parquet(pid, m, z=0.01):
    b = Bld()
    b.solide(PIECES[pid]["polygone_interieur"], z - 0.012, z, m)
    return b.objet(pid + "_parquet")


def rosace(nom, x, y, zp, diam, m=None):
    m = m or M["blanc"]
    R = diam / 2
    b = Bld()
    b.tour(x, y, [(R, 0), (R, -0.02), (R * 0.92, -0.03), (R * 0.7, -0.035), (R * 0.55, -0.06), (R * 0.35, -0.07),
                  (R * 0.2, -0.11), (R * 0.08, -0.14), (0, -0.15)], m, n=32, z0=zp)
    for k in range(16):
        a = 2 * math.pi * k / 16
        ca, sa = math.cos(a), math.sin(a)
        p0 = (x + ca * R * 0.3, y + sa * R * 0.3, zp - 0.07)
        p1 = (x + ca * R * 0.9, y + sa * R * 0.9, zp - 0.025)
        b.tige(p0, p1, 0.025 * diam, m, n=5, r1=0.012 * diam)
    return b.objet(nom)


def chaine(b, x, y, z0, z1, r=0.012):
    b.tige((x, y, z0), (x, y, z1), r, M["laiton"], n=6)


def lustre(pid, nom, x, y, zp, z_bas, ech, puissance):
    """Lustre Poly Haven (bas du lustre à z_bas), tige depuis le plafond, lumière ponctuelle au cœur."""
    h = 1.04 * ech
    ob = poser(P_LUSTRE, pid + "_" + nom, x, y, z_bas + h, ech=ech)
    b = Bld()
    chaine(b, x, y, z_bas + h - 0.02, zp)
    b.tour(x, y, [(0.09, 0), (0.09, -0.03), (0.03, -0.06), (0, -0.07)], M["laiton"], n=12, z0=zp)
    b.objet(pid + "_" + nom + "_tige")
    lumiere("lumiere_%s_%s" % (pid, nom), x, y, z_bas + h * 0.45, puissance, rayon=0.35)
    return ob


# ----------------------------------------------------------------------------------------------
# Mobilier et objets (prototypes locaux : avant vers −Y, dos vers +Y, posés sur z = 0)
# ----------------------------------------------------------------------------------------------
def p_commode(w=1.3, d=0.6, h=0.9):
    b = Bld()
    m = M["noyer"]
    N = 16

    def yf(s):
        return -d / 2 - 0.05 * math.cos(math.pi * s / w) + 0.02 * math.cos(3 * math.pi * s / w)

    corps = [(w / 2, d / 2), (-w / 2, d / 2)] + [(s, yf(s)) for s in np.linspace(-w / 2, w / 2, N)]
    b.solide(corps, 0.12, h - 0.04, m)
    plat = [(w / 2 + 0.03, d / 2), (-w / 2 - 0.03, d / 2)] + \
           [(s * (w + 0.06) / w, yf(s) - 0.03) for s in np.linspace(-w / 2, w / 2, N)]
    b.solide(plat, h - 0.04, h, m)
    ss = np.linspace(-w / 2 + 0.02, w / 2 - 0.02, N)
    for zr in (0.37, 0.62):
        for a, c in zip(ss[:-1], ss[1:]):
            b.boite(a, yf(a) - 0.004, zr, c, yf(a) + 0.01, zr + 0.01, M["foyer"])
    for zr in (0.24, 0.49, 0.74):
        for s in (-0.36, 0.36):
            b.boite(s - 0.06, yf(s) - 0.018, zr - 0.02, s + 0.06, yf(s), zr + 0.02, M["laiton"])
        b.boite(-0.03, yf(0) - 0.015, zr - 0.03, 0.03, yf(0), zr + 0.03, M["laiton"])
    for sx in (-1, 1):
        for y in (yf(sx * w / 2) + 0.05, d / 2 - 0.05):
            x = sx * (w / 2 - 0.05)
            b.tour(x, y, [(0.05, 0.12), (0.04, 0.07), (0.025, 0)], m, n=8)
    return proto("commode", b)


def p_console(w=0.9, d=0.4, h=0.8, m=None, entrejambe=True, tiroir=True):
    m = m or M["acajou"]
    b = Bld()
    b.boite(-w / 2, -d / 2, h - 0.03, w / 2, d / 2, h, m)
    b.boite(-w / 2 + 0.03, -d / 2 + 0.03, h - 0.15, w / 2 - 0.03, d / 2 - 0.02, h - 0.03, m)
    if tiroir:
        b.boite(-0.05, -d / 2 + 0.02, h - 0.10, 0.05, -d / 2 + 0.03, h - 0.08, M["laiton"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (w / 2 - 0.05), sy * (d / 2 - 0.05)
            b.tour(x, y, [(0.013, 0), (0.016, 0.05), (0.022, h * 0.55), (0.03, h - 0.17), (0.03, h - 0.03)], m, n=8)
    if entrejambe:
        b.boite(-w / 2 + 0.05, -d / 2 + 0.05, 0.16, w / 2 - 0.05, d / 2 - 0.05, 0.18, m)
    return proto("console_%d_%d" % (int(w * 100), int(h * 100)), b)


def p_chaise():
    """Chaise acajou à dossier ajouré, assise velours rouge (billard P34-P35, salon vert W07)."""
    b = Bld()
    m = M["acajou"]
    w, d = 0.46, 0.44
    b.boite(-w / 2, -d / 2, 0.40, w / 2, d / 2, 0.45, m)
    b.boite(-w / 2 + 0.02, -d / 2 + 0.01, 0.45, w / 2 - 0.02, d / 2 - 0.02, 0.50, M["velours_rouge"])
    for sx in (-1, 1):
        b.tour(sx * (w / 2 - 0.03), -d / 2 + 0.03, [(0.018, 0), (0.024, 0.15), (0.017, 0.25), (0.022, 0.40)], m, n=8)
        b.tige((sx * (w / 2 - 0.03), d / 2 - 0.03, 0), (sx * (w / 2 - 0.035), d / 2 + 0.02, 0.95), 0.018, m, n=6)
    b.tige((-w / 2 + 0.03, d / 2 + 0.02, 0.92), (w / 2 - 0.03, d / 2 + 0.02, 0.92), 0.03, m, n=6)
    b.tige((-w / 2 + 0.03, d / 2 + 0.01, 0.62), (w / 2 - 0.03, d / 2 + 0.01, 0.62), 0.015, m, n=6)
    b.boite(-0.05, d / 2 - 0.005, 0.62, 0.05, d / 2 + 0.03, 0.90, m)
    return proto("chaise_rouge", b)


def p_billard():
    """Table de billard français sans poches, drap vert, six pieds tournés (P32-P35)."""
    b = Bld()
    m = M["acajou"]
    L, W = 2.60, 1.40
    r = 0.12
    b.boite(-L / 2, -W / 2, 0.60, L / 2, W / 2, 0.79, m)
    b.boite(-L / 2 + r, -W / 2 + r, 0.79, L / 2 - r, W / 2 - r, 0.80, M["drap"])
    for x0, y0, x1, y1 in ((-L / 2, -W / 2, L / 2, -W / 2 + r), (-L / 2, W / 2 - r, L / 2, W / 2),
                           (-L / 2, -W / 2 + r, -L / 2 + r, W / 2 - r), (L / 2 - r, -W / 2 + r, L / 2, W / 2 - r)):
        b.boite(x0, y0, 0.79, x1, y1, 0.83, m)
    for x0, y0, x1, y1 in ((-L / 2 + r, -W / 2 + r, L / 2 - r, -W / 2 + r + 0.04),
                           (-L / 2 + r, W / 2 - r - 0.04, L / 2 - r, W / 2 - r),
                           (-L / 2 + r, -W / 2 + r + 0.04, -L / 2 + r + 0.04, W / 2 - r - 0.04),
                           (L / 2 - r - 0.04, -W / 2 + r + 0.04, L / 2 - r, W / 2 - r - 0.04)):
        b.boite(x0, y0, 0.80, x1, y1, 0.825, M["drap"])
    b.boite(-L / 2 - 0.02, -W / 2 - 0.02, 0.56, L / 2 + 0.02, W / 2 + 0.02, 0.60, m)
    for x in (-L / 2 + 0.12, 0, L / 2 - 0.12):
        for y in (-W / 2 + 0.12, W / 2 - 0.12):
            b.tour(x, y, [(0.06, 0), (0.07, 0.04), (0.05, 0.08), (0.06, 0.18), (0.10, 0.30), (0.09, 0.40),
                          (0.06, 0.48), (0.07, 0.56)], m, n=12)
    return proto("billard", b)


def p_vaisselier():
    """Buffet-vaisselier à gradin : 2 portes, 2 tiroirs, étagère à volutes, porte-queues (P35)."""
    b = Bld()
    m = M["acajou"]
    w, d = 1.40, 0.50
    b.boite(-w / 2, -d / 2, 0.0, w / 2, d / 2, 0.08, m)
    b.boite(-w / 2 + 0.02, -d / 2 + 0.02, 0.08, w / 2 - 0.02, d / 2, 0.95, m)
    for sx in (-1, 1):
        b.boite(sx * 0.02, -d / 2 + 0.005, 0.12, sx * (w / 2 - 0.06), -d / 2 + 0.02, 0.70, m)
        b.boite(sx * 0.04, -d / 2 - 0.005, 0.74, sx * (w / 2 - 0.06), -d / 2 + 0.02, 0.90, m)
        b.boite(sx * 0.3 - 0.04, -d / 2 - 0.02, 0.81, sx * 0.3 + 0.04, -d / 2 - 0.005, 0.83, M["laiton"])
    b.boite(-w / 2 - 0.01, -d / 2 - 0.01, 0.95, w / 2 + 0.01, d / 2, 0.99, m)
    b.boite(-w / 2 + 0.04, d / 2 - 0.04, 0.99, w / 2 - 0.04, d / 2, 1.85, m)
    for z in (1.40, 1.80):
        b.boite(-w / 2 + 0.04, d / 2 - 0.30, z, w / 2 - 0.04, d / 2, z + 0.03, m)
    prof = [(d / 2, 0.99), (d / 2 - 0.30, 0.99), (d / 2 - 0.30, 1.05), (d / 2 - 0.18, 1.12), (d / 2 - 0.22, 1.25),
            (d / 2 - 0.30, 1.40), (d / 2 - 0.30, 1.83), (d / 2, 1.83)]
    for sx in (-1, 1):
        x0 = sx * (w / 2 - 0.04)
        b.prisme_r(Rep((x0, 0), (0, 1), (1, 0)), [(y, z) for y, z in prof], -0.025, 0.0, m)
    b.prisme_r(Rep((0, d / 2 - 0.02), (1, 0), (0, -1)),
               [(-w / 2 + 0.04, 1.83), (w / 2 - 0.04, 1.83), (w / 2 - 0.04, 1.90), (0.25, 1.95), (0.0, 2.05),
                (-0.25, 1.95), (-w / 2 + 0.04, 1.90)], 0, 0.03, m)
    for k in range(9):
        x = -0.24 + k * 0.06
        b.tige((x, d / 2 - 0.12, 1.43), (x, d / 2 - 0.10, 1.79), 0.012, M["noyer"], n=5)
    b.boite(-0.62, d / 2 - 0.25, 1.43, -0.38, d / 2 - 0.05, 1.70, M["cuir_bordeaux"])
    b.boite(0.38, d / 2 - 0.25, 1.43, 0.60, d / 2 - 0.05, 1.68, M["cuir_bordeaux"])
    b.tour(0.1, -0.05, [(0.08, 0), (0.12, 0.05), (0.13, 0.11), (0.09, 0.16), (0.02, 0.19), (0, 0.2)],
           M["bleu_porcelaine"], n=14, z0=0.99)
    for x in (-0.45, 0.45):
        b.tour(x, d / 2 - 0.15, [(0.07, 0), (0.09, 0.14), (0, 0.14)], M["porcelaine"], n=10, z0=1.83)
    _feuillage(b, -0.45, d / 2 - 0.15, 1.95, 10, 0.22, 0.03, M["feuille_claire"], tombant=0.6)
    _feuillage(b, 0.45, d / 2 - 0.15, 1.95, 10, 0.22, 0.03, M["feuille_claire"], tombant=0.6)
    return proto("vaisselier", b, recalc=False)


def p_chevet():
    b = Bld()
    m = M["acajou"]
    b.boite(-0.30, -0.20, 0.10, 0.30, 0.20, 0.70, m)
    b.boite(-0.32, -0.22, 0.70, 0.32, 0.21, 0.73, m)
    for z in (0.40, 0.58):
        b.boite(-0.27, -0.205, z, 0.27, -0.20, z + 0.008, M["foyer"])
        b.boite(-0.03, -0.215, z + 0.07, 0.03, -0.20, z + 0.09, M["laiton"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.boite(sx * 0.27 - 0.025, sy * 0.17 - 0.025, 0, sx * 0.27 + 0.025, sy * 0.17 + 0.025, 0.10, m)
    return proto("chevet", b)


def p_table_basse_verre():
    """Table basse gigogne verre et métal noir (salon P27-P29)."""
    b = Bld()
    for w, d, h in ((0.80, 0.50, 0.45), (0.70, 0.44, 0.30)):
        b.boite(-w / 2, -d / 2, h - 0.01, w / 2, d / 2, h, M["verre"])
        for sx in (-1, 1):
            for sy in (-1, 1):
                xa, ya = sx * w / 2, sy * d / 2
                b.boite(xa, ya, 0, xa - sx * 0.024, ya - sy * 0.024, h - 0.01, M["fer"])
        b.boite(-w / 2, -d / 2, h - 0.03, w / 2, -d / 2 + 0.012, h - 0.01, M["fer"])
        b.boite(-w / 2, d / 2 - 0.012, h - 0.03, w / 2, d / 2, h - 0.01, M["fer"])
    b.tour(0, 0, [(0.18, 0), (0.24, 0.03), (0.24, 0.04), (0, 0.04)], M["noyer"], n=16, z0=0.45)
    for k in range(18):
        a = k * 2.4
        rr = 0.03 + 0.17 * math.sqrt(k / 18)
        b.tour(rr * math.cos(a), rr * math.sin(a), [(0.03, 0), (0.035, 0.03), (0, 0.05)], M["velours_rouge"], n=6,
               z0=0.48)
    return proto("table_basse_verre", b)


def p_table_ovale():
    """Table basse ovale plateau onyx, piètement laiton (billard P32-P34)."""
    b = Bld()
    N = 24
    ell = [(0.55 * math.cos(2 * math.pi * k / N), 0.35 * math.sin(2 * math.pi * k / N)) for k in range(N)]
    b.solide(ell, 0.43, 0.46, M["onyx"])
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        x, y = 0.40 * math.cos(a), 0.24 * math.sin(a)
        b.tige((x, y, 0), (x * 0.95, y * 0.95, 0.43), 0.012, M["laiton"], n=6)
    ell2 = [(0.36 * math.cos(2 * math.pi * k / N), 0.21 * math.sin(2 * math.pi * k / N)) for k in range(N)]
    for i in range(N):
        a, c = ell2[i], ell2[(i + 1) % N]
        b.tige((a[0], a[1], 0.12), (c[0], c[1], 0.12), 0.008, M["laiton"], n=4)
    b.tour(0.05, 0.02, [(0.04, 0), (0.05, 0.08), (0.02, 0.14), (0.025, 0.18)], M["verre"], n=10, z0=0.46)
    _feuillage(b, 0.05, 0.02, 0.62, 7, 0.10, 0.015, M["feuille_claire"], tombant=0.2)
    for k in range(6):
        a = k * 1.05
        b.tour(0.05 + 0.05 * math.cos(a), 0.02 + 0.05 * math.sin(a), [(0.02, 0), (0.025, 0.015), (0, 0.03)],
               M["blanc_peint"], n=6, z0=0.66)
    return proto("table_ovale", b, recalc=False)


def p_table_jeu(w=1.6, d=0.9, h=0.76):
    b = Bld()
    m = M["acajou"]
    b.boite(-w / 2, -d / 2, h - 0.035, w / 2, d / 2, h, m)
    b.boite(-w / 2 + 0.05, -d / 2 + 0.05, h - 0.14, w / 2 - 0.05, d / 2 - 0.05, h - 0.035, m)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.tour(sx * (w / 2 - 0.08), sy * (d / 2 - 0.08),
                   [(0.025, 0), (0.035, 0.05), (0.028, 0.25), (0.04, 0.40), (0.03, 0.55), (0.035, h - 0.14)], m, n=10)
    return proto("table_%d" % int(w * 100), b)


def p_gigognes():
    b = Bld()
    m = M["acajou"]
    for k, (w, d, h) in enumerate(((0.60, 0.40, 0.55), (0.52, 0.36, 0.50), (0.44, 0.32, 0.45))):
        y = -0.02 * k
        b.boite(-w / 2, y - d / 2, h - 0.02, w / 2, y + d / 2, h, m)
        for sx in (-1, 1):
            b.tige((sx * (w / 2 - 0.02), y - d / 2 + 0.02, 0), (sx * (w / 2 - 0.02), y - d / 2 + 0.02, h - 0.02), 0.012,
                   m, n=6)
            b.tige((sx * (w / 2 - 0.02), y + d / 2 - 0.02, 0), (sx * (w / 2 - 0.02), y + d / 2 - 0.02, h - 0.02), 0.012,
                   m, n=6)
    return proto("gigognes", b)


def p_radiateur(n=20, h=0.80, cache=False):
    b = Bld()
    pas = 0.065
    w = n * pas
    for k in range(n):
        x = -w / 2 + (k + 0.5) * pas
        b.boite(x - 0.025, -0.08, 0.12, x + 0.025, 0.08, h - 0.02, M["fonte"])
    b.boite(-w / 2, -0.03, 0.12, w / 2, 0.03, 0.17, M["fonte"])
    b.boite(-w / 2, -0.03, h - 0.07, w / 2, 0.03, h - 0.02, M["fonte"])
    for sx in (-1, 1):
        b.boite(sx * (w / 2 - 0.03) - 0.015, -0.015, 0.0, sx * (w / 2 - 0.03) + 0.015, 0.015, 0.12, M["fonte"])
    if cache:
        b.boite(-w / 2 - 0.05, -0.12, h, w / 2 + 0.05, 0.12, h + 0.03, M["blanc_peint"])
    return proto("radiateur_%d" % n, b)


def p_lampadaire(bras=2, h=1.65, m_abat=None):
    """Lampadaire bouillotte laiton, pied tripode (salon P27-P29, salon vert W07) ou à un abat-jour."""
    b = Bld()
    m = M["laiton"]
    for k in range(3):
        a = 2 * math.pi * k / 3
        b.tige((0, 0, 0.16), (0.24 * math.cos(a), 0.24 * math.sin(a), 0.01), 0.008, m, n=5)
        b.tour(0.24 * math.cos(a), 0.24 * math.sin(a), [(0.02, 0), (0.015, 0.02), (0, 0.025)], m, n=6)
    b.tour(0, 0, [(0.03, 0.12), (0.035, 0.18), (0.012, 0.22), (0.010, h - 0.25), (0.02, h - 0.22),
                  (0.008, h - 0.18), (0.008, h + 0.05), (0, h + 0.07)], m, n=8)
    zb = h - 0.40
    if bras:
        for k in range(bras):
            a = math.pi * k
            ex, ey = 0.17 * math.cos(a), 0.17 * math.sin(a)
            b.tige((0, 0, zb), (ex * 0.6, ey * 0.6, zb - 0.06), 0.007, m, n=5)
            b.tige((ex * 0.6, ey * 0.6, zb - 0.06), (ex, ey, zb + 0.02), 0.007, m, n=5)
            b.tour(ex, ey, [(0.025, 0), (0.03, 0.01), (0.012, 0.012), (0.01, 0.10), (0, 0.11)], M["blanc_peint"], n=6,
                   z0=zb + 0.02)
    ab = Bld()
    ra, rb_ = (0.25, 0.16) if bras else (0.22, 0.14)
    zh = h - 0.02
    za = zh - 0.24
    ab.nappe([[(ra * math.cos(2 * math.pi * k / 20), ra * math.sin(2 * math.pi * k / 20), za) for k in range(21)],
              [(rb_ * math.cos(2 * math.pi * k / 20), rb_ * math.sin(2 * math.pi * k / 20), zh) for k in range(21)]],
             m_abat or M["abat_jour"])
    o1 = proto("lampadaire_%d" % bras, b)
    o2 = proto("abat_jour_%d" % bras, ab, recalc=False)
    return o1, o2


def p_lampe(blanc=True):
    """Lampe : pied céramique (vase Poly Haven pour les potiches, sinon pied blanc tourné) et abat-jour."""
    b = Bld()
    if blanc:
        b.tour(0, 0, [(0.08, 0), (0.09, 0.02), (0.06, 0.05), (0.11, 0.18), (0.10, 0.28), (0.04, 0.34), (0.03, 0.38),
                      (0.012, 0.40), (0.01, 0.46), (0, 0.47)], M["porcelaine"], n=14)
    ab = Bld()
    z0 = 0.40 if blanc else 0.42
    ab.nappe([[(0.19 * math.cos(2 * math.pi * k / 18), 0.19 * math.sin(2 * math.pi * k / 18), z0) for k in range(19)],
              [(0.12 * math.cos(2 * math.pi * k / 18), 0.12 * math.sin(2 * math.pi * k / 18), z0 + 0.24)
               for k in range(19)]], M["abat_jour"])
    o2 = proto("abat_jour_lampe_%d" % int(blanc), ab, recalc=False)
    if blanc:
        return proto("lampe_blanche", b), o2
    return None, o2


def _feuillage(b, x, y, z, n, L, w, m, tombant=0.8, graine=0, inclin=0.9):
    r = np.random.default_rng(graine + int(abs(x * 1000 + y * 77)))
    for k in range(n):
        a = 2 * math.pi * k / n + r.uniform(-0.3, 0.3)
        e = r.uniform(0.35, inclin)
        ll = L * r.uniform(0.75, 1.15)
        pts_c, pts_g, pts_d = [], [], []
        for j in range(5):
            t = j / 4
            rr = ll * t * math.cos(e)
            zz = z + ll * t * math.sin(e) - tombant * ll * t * t
            c = Vector((x + rr * math.cos(a), y + rr * math.sin(a), zz))
            lat = Vector((-math.sin(a), math.cos(a), 0)) * w * math.sin(math.pi * min(0.95, t * 0.9 + 0.1))
            pts_c.append(c)
            pts_g.append(c - lat)
            pts_d.append(c + lat)
        b.nappe([pts_g, pts_c, pts_d], m)


def p_plante(genre="dracaena", h=1.6, pot="emaille"):
    """Plante en cache-pot (dracaena, kentia) : pot tourné, cannes, feuilles en lanières (double face)."""
    b = Bld()
    mp = M["pot_emaille"] if pot == "emaille" else M["terre_cuite"]
    rp = 0.22 if genre == "kentia" else 0.19
    b.tour(0, 0, [(rp * 0.7, 0), (rp, 0.08), (rp * 1.05, 0.30), (rp * 1.1, 0.34), (rp * 0.95, 0.34),
                  (rp * 0.95, 0.30), (0, 0.30)], mp, n=16)
    r = np.random.default_rng(3 if genre == "kentia" else 5)
    if genre == "dracaena":
        for k, (hh, ox, oy) in enumerate(((h, 0.03, 0.0), (h * 0.78, -0.04, 0.03), (h * 0.62, 0.0, -0.05))):
            b.tige((ox, oy, 0.3), (ox * 2, oy * 2, hh - 0.15), 0.018, M["tige"], n=5)
            _feuillage(b, ox * 2, oy * 2, hh - 0.15, 16, 0.42, 0.028, M["feuille"], tombant=0.7, graine=k)
    else:
        for k in range(9):
            a = 2 * math.pi * k / 9 + r.uniform(-0.2, 0.2)
            e = r.uniform(0.9, 1.3)
            ll = h * r.uniform(0.55, 0.75)
            rachis = []
            for j in range(7):
                t = j / 6
                rr = ll * t * math.cos(e)
                rachis.append(Vector((rr * math.cos(a), rr * math.sin(a), 0.32 + ll * t * math.sin(e) - 0.35 * ll * t * t)))
            for j in range(6):
                b.tige(rachis[j], rachis[j + 1], 0.006, M["tige"], n=4)
            for j in range(1, 7):
                p = rachis[j]
                for sgn in (-1, 1):
                    lat = Vector((-math.sin(a), math.cos(a), 0)) * sgn
                    q = p + lat * 0.22 * (1 - j / 9) + Vector((0, 0, -0.10))
                    m_ = (p + q) / 2 + Vector((0, 0, 0.03))
                    tv = Vector((math.cos(a), math.sin(a), 0)) * 0.025
                    b.nappe([[p - tv, m_ - tv, q], [p + tv, m_ + tv, q]], M["feuille"])
    return proto(genre + "_" + pot, b, recalc=False)


def p_voilier():
    b = Bld()
    N = 12
    pts = [(0.30 * math.cos(2 * math.pi * k / 20), 0.055 * math.sin(2 * math.pi * k / 20)) for k in range(20)]
    b.solide(pts, 0.06, 0.12, M["noyer"])
    b.solide([(x * 0.8, y * 0.6) for x, y in pts], 0.03, 0.06, M["noyer"])
    b.boite(-0.12, -0.02, 0.0, 0.12, 0.02, 0.03, M["noyer"])
    for x, hh in ((-0.14, 0.38), (0.0, 0.48), (0.14, 0.40)):
        b.tige((x, 0, 0.12), (x, 0, 0.12 + hh), 0.004, M["noyer"], n=4)
        for k in range(3):
            z0 = 0.18 + k * hh * 0.28
            wv = 0.11 - k * 0.025
            b.quad_uv([(x - wv / 2, 0.002, z0), (x + wv / 2, 0.002, z0), (x + wv / 2 * 0.9, 0.002, z0 + hh * 0.24),
                       (x - wv / 2 * 0.9, 0.002, z0 + hh * 0.24)], M["voile"], [(0, 0), (1, 0), (1, 1), (0, 1)])
    b.quad_uv([(0.30, 0, 0.12), (0.45, 0, 0.14), (0.14, 0, 0.50), (0.14, 0, 0.30)], M["voile"],
              [(0, 0), (1, 0), (1, 1), (0, 1)])
    return proto("voilier", b, recalc=False)


def p_sabre():
    b = Bld()
    pts = [Vector((0, 0, -0.45 + 0.9 * t)) + Vector((0.06 * math.sin(math.pi * t * 0.8), 0, 0)) for t in np.linspace(0, 1, 7)]
    for a, c in zip(pts[:-1], pts[1:]):
        b.tige(a, c, 0.012, M["argent"], n=4)
    b.tige(pts[-1], pts[-1] + Vector((0, 0, 0.14)), 0.016, M["laiton"], n=6)
    b.tige(pts[-1] + Vector((-0.05, 0, 0)), pts[-1] + Vector((0.05, 0, 0)), 0.008, M["laiton"], n=4)
    return proto("sabre", b)


def p_fusil():
    b = Bld()
    b.tige((0, 0, -0.65), (0, 0, 0.75), 0.011, M["fer"], n=6)
    b.prisme_r(Rep((0, 0.0), (1, 0), (0, 1)), [(-0.03, -0.70), (0.05, -0.75), (0.07, -0.35), (0.03, -0.05),
                                                (0.015, 0.45), (-0.01, 0.45), (-0.02, -0.05)], -0.02, 0.02, M["noyer"])
    return proto("fusil", b)


def p_statue():
    """Statuette bronze patiné : femme en costume XVIIe à chapeau à plume (billard P32-P34)."""
    b = Bld()
    m = M["bronze"]
    b.boite(-0.13, -0.13, 0, 0.13, 0.13, 0.06, m)
    b.tour(0, 0, [(0.11, 0.06), (0.09, 0.30), (0.06, 0.40), (0.07, 0.52), (0.05, 0.58), (0.03, 0.62), (0.045, 0.66),
                  (0.04, 0.70), (0, 0.72)], m, n=12)
    b.tour(0.0, 0.0, [(0.11, 0.70), (0.11, 0.71), (0, 0.72)], m, n=12)
    b.tige((0.0, 0.03, 0.71), (-0.10, 0.08, 0.82), 0.015, m, n=5, r1=0.004)
    b.tige((0.05, 0, 0.55), (0.14, -0.04, 0.40), 0.018, m, n=5)
    b.tige((-0.05, 0, 0.55), (-0.10, -0.06, 0.62), 0.018, m, n=5)
    return proto("statue", b)


def p_pendule():
    """Pendule « cavalier terrassant un guerrier » : socles marbre noir et bronze doré, cadran (W07, W14)."""
    b = Bld()
    b.boite(-0.30, -0.10, 0, 0.30, 0.10, 0.05, M["marbre_noir"])
    b.boite(-0.25, -0.08, 0.05, 0.25, 0.08, 0.20, M["or"])
    b.tour(0, -0.081, [(0, 0), (0.06, 0), (0.06, 0.004), (0, 0.004)], M["porcelaine"], n=16, z0=0)
    m = M["bronze"]
    b.boite(-0.13, -0.04, 0.33, 0.12, 0.04, 0.42, m)
    for x in (-0.10, 0.09):
        b.tige((x, -0.02, 0.33), (x - 0.02, -0.02, 0.20), 0.012, m, n=5)
        b.tige((x, 0.02, 0.33), (x + 0.02, 0.02, 0.20), 0.012, m, n=5)
    b.tige((0.11, 0, 0.40), (0.19, 0, 0.52), 0.03, m, n=6)
    b.boite(0.17, -0.025, 0.50, 0.25, 0.025, 0.55, m)
    b.boite(-0.03, -0.03, 0.42, 0.05, 0.03, 0.58, m)
    b.tour(0.01, 0, [(0.03, 0.58), (0.03, 0.63), (0, 0.65)], m, n=8)
    b.tige((0.04, 0, 0.55), (0.15, -0.05, 0.66), 0.008, m, n=4)
    b.boite(-0.20, -0.05, 0.20, 0.02, 0.05, 0.27, m)
    return proto("pendule", b)


def p_candelabre():
    b = Bld()
    b.boite(-0.07, -0.07, 0, 0.07, 0.07, 0.04, M["marbre_noir"])
    b.boite(-0.06, -0.06, 0.04, 0.06, 0.06, 0.14, M["or"])
    b.tour(0, 0, [(0.05, 0.14), (0.04, 0.35), (0.03, 0.45), (0.035, 0.52), (0, 0.56)], M["bronze"], n=10)
    for k in range(6):
        a = 2 * math.pi * k / 6
        x, y = 0.13 * math.cos(a), 0.13 * math.sin(a)
        b.tige((0, 0, 0.58), (x, y, 0.66), 0.006, M["or"], n=4)
        b.tour(x, y, [(0.02, 0), (0.012, 0.01), (0.010, 0.10), (0, 0.11)], M["porcelaine"], n=6, z0=0.66)
    b.tige((0, 0, 0.52), (0, 0, 0.80), 0.01, M["or"], n=5)
    return proto("candelabre", b)


def p_pare_feu():
    b = Bld()
    b.boite(-0.40, -0.01, 0.03, 0.40, 0.01, 0.62, M["fer"])
    b.tige((-0.40, 0, 0.62), (0.40, 0, 0.62), 0.012, M["laiton"], n=6)
    for x in (-0.40, 0.40):
        b.tige((x, 0, 0), (x, 0, 0.66), 0.012, M["laiton"], n=6)
        b.tige((x, -0.12, 0), (x, 0.12, 0), 0.01, M["laiton"], n=4)
    for x in (-0.25, 0.25):
        b.tige((x, 0.15, 0.0), (x, 0.40, 0.05), 0.012, M["fer"], n=4)
        b.tour(x, 0.15, [(0.03, 0), (0.035, 0.12), (0.02, 0.18), (0, 0.2)], M["laiton"], n=8)
    return proto("pare_feu", b)


def p_serviteur():
    b = Bld()
    b.tour(0, 0, [(0.10, 0), (0.10, 0.02), (0.015, 0.03), (0.012, 0.70), (0.03, 0.72), (0, 0.75)], M["laiton"], n=10)
    for a in (0, 2.1, 4.2):
        x, y = 0.04 * math.cos(a), 0.04 * math.sin(a)
        b.tige((x, y, 0.05), (x * 1.5, y * 1.5, 0.65), 0.007, M["fer"], n=4)
    return proto("serviteur", b)


def p_sortie():
    b = Bld()
    b.boite(-0.175, -0.04, 0, 0.175, 0, 0.15, M["sortie"])
    return proto("panneau_sortie", b)


def p_bureau():
    """Bureau plat acajou à tiroirs, plateau gainé (pièce nord-ouest, meublée sobrement)."""
    b = Bld()
    m = M["acajou"]
    w, d, h = 1.5, 0.8, 0.76
    b.boite(-w / 2, -d / 2, h - 0.03, w / 2, d / 2, h, m)
    b.boite(-w / 2 + 0.04, -d / 2 + 0.04, h - 0.002, w / 2 - 0.04, d / 2 - 0.04, h + 0.001, M["cuir_bordeaux"])
    b.boite(-w / 2 + 0.03, -d / 2 + 0.03, h - 0.16, w / 2 - 0.03, d / 2 - 0.03, h - 0.03, m)
    for x in (-0.45, 0, 0.45):
        b.boite(x - 0.04, -d / 2 + 0.02, h - 0.10, x + 0.04, -d / 2 + 0.03, h - 0.085, M["laiton"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.tour(sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), [(0.015, 0), (0.02, 0.06), (0.03, h - 0.16)], m, n=8)
    return proto("bureau", b)


def p_bibliotheque(w=2.0, h=2.3, d=0.42):
    """Bibliothèque basse vitrée à rayonnages garnis (pièce nord-ouest)."""
    b = Bld()
    m = M["acajou"]
    b.boite(-w / 2, -d / 2, 0, w / 2, d / 2, 0.10, m)
    b.boite(-w / 2, d / 2 - 0.03, 0.10, w / 2, d / 2, h - 0.08, m)
    for x in np.linspace(-w / 2, w / 2, 4):
        b.boite(x - 0.025, -d / 2, 0.10, x + 0.025, d / 2, h - 0.08, m)
    for z in (0.10, 0.62, 1.14, 1.66, h - 0.12):
        b.boite(-w / 2, -d / 2, z, w / 2, d / 2, z + 0.03, m)
    b.boite(-w / 2 - 0.03, -d / 2 - 0.03, h - 0.09, w / 2 + 0.03, d / 2, h, m)
    r = np.random.default_rng(21)
    couleurs = [M["cuir_bordeaux"], M["velours_rouge"], M["noyer"], M["drap"], M["poutre"]]
    for z in (0.13, 0.65, 1.17, 1.69):
        for c in range(3):
            x0 = -w / 2 + c * w / 3 + 0.04
            x1 = x0 + w / 3 - 0.08
            x = x0
            while x < x1 - 0.03:
                e = r.uniform(0.025, 0.05)
                hh = r.uniform(0.25, 0.42)
                b.boite(x, -d / 2 + 0.06 + r.uniform(0, 0.03), z, x + e, d / 2 - 0.06, z + hh,
                        couleurs[int(r.integers(len(couleurs)))])
                x += e + 0.002
    return proto("bibliotheque", b)


def p_banc():
    b = Bld()
    m = M["acajou"]
    b.boite(-0.60, -0.20, 0.38, 0.60, 0.20, 0.42, m)
    b.boite(-0.58, -0.18, 0.42, 0.58, 0.18, 0.47, M["velours_rouge"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.tour(sx * 0.54, sy * 0.15, [(0.02, 0), (0.028, 0.15), (0.022, 0.38)], m, n=8)
    return proto("banquette", b)


def p_lanterne():
    """Lanterne de dégagement en laiton et verre, suspendue."""
    b = Bld()
    b.tour(0, 0, [(0.10, 0), (0.18, 0.05), (0.18, 0.08), (0.14, 0.10), (0.14, 0.50), (0.18, 0.52), (0.08, 0.62),
                  (0.03, 0.66), (0, 0.68)], M["verre"], n=8)
    for k in range(8):
        a = 2 * math.pi * k / 8
        b.tige((0.14 * math.cos(a), 0.14 * math.sin(a), 0.10), (0.14 * math.cos(a), 0.14 * math.sin(a), 0.50),
               0.006, M["laiton"], n=4)
    b.tour(0, 0, [(0.02, 0.15), (0.02, 0.30), (0, 0.32)], M["porcelaine"], n=6)
    return proto("lanterne", b, recalc=False)


log("prototypes…")
P_COMMODE = p_commode()
P_CONSOLE_L16 = p_console(0.9, 0.40, 0.80)
P_CONSOLE_GALBEE = p_console(1.3, 0.45, 0.82, entrejambe=False)
P_CONSOLE_VERT = p_console(1.0, 0.42, 0.80)
P_CONSOLE_NORD = p_console(1.0, 0.42, 0.78, entrejambe=False)
P_CHAISE = p_chaise()
P_BILLARD = p_billard()
P_VAISSELIER = p_vaisselier()
P_CHEVET = p_chevet()
P_TB_VERRE = p_table_basse_verre()
P_TB_OVALE = p_table_ovale()
P_TABLE_JEU = p_table_jeu()
P_TABLE_RONDE_PETITE = p_table_jeu(0.9, 0.6, 0.45)
P_GIGOGNES = p_gigognes()
P_RAD_SALON = p_radiateur(22, 0.78, cache=True)
P_RAD_BILLARD = p_radiateur(9, 0.88)
P_LAMPADAIRE2, P_ABAT2 = p_lampadaire(2)
P_LAMPADAIRE1, P_ABAT1 = p_lampadaire(0, 1.60)
P_LAMPE_BLANCHE, P_ABAT_LAMPE_B = p_lampe(True)
_, P_ABAT_POTICHE = p_lampe(False)
P_DRACAENA = p_plante("dracaena", 1.6, "emaille")
P_DRACAENA_TC = p_plante("dracaena", 1.4, "terre")
P_KENTIA = p_plante("kentia", 1.8, "terre")
P_VOILIER = p_voilier()
P_SABRE = p_sabre()
P_FUSIL = p_fusil()
P_STATUE = p_statue()
P_PENDULE = p_pendule()
P_CANDELABRE = p_candelabre()
P_PARE_FEU = p_pare_feu()
P_SERVITEUR = p_serviteur()
P_SORTIE = p_sortie()
P_BUREAU = p_bureau()
P_BIBLIO = p_bibliotheque()
P_BANC = p_banc()
P_LANTERNE = p_lanterne()


def lampe_potiche(pid, nom, x, y, z, ech=0.75):
    poser(P_VASE, pid + "_" + nom + "_pied", x, y, z, ech=ech)
    poser(P_ABAT_POTICHE, pid + "_" + nom + "_abat_jour", x, y, z - 0.42 + 0.439 * ech + 0.02)


def lampe_blanche(pid, nom, x, y, z):
    poser(P_LAMPE_BLANCHE, pid + "_" + nom, x, y, z)
    poser(P_ABAT_LAMPE_B, pid + "_" + nom + "_abat_jour", x, y, z)


def lampadaire(pid, nom, x, y, bras=2):
    poser(P_LAMPADAIRE2 if bras else P_LAMPADAIRE1, pid + "_" + nom, x, y)
    poser(P_ABAT2 if bras else P_ABAT1, pid + "_" + nom + "_abat_jour", x, y)


def tableau(b, r, s, z0, w, h, m_toile, m_cadre=None, f=0.09, d0=0.0, prof=0.06):
    """Tableau à cadre doré sur le mur (repère r) : centre s, bas z0."""
    m_cadre = m_cadre or M["or"]
    s0, s1, z1 = s - w / 2, s + w / 2, z0 + h
    cadre_r(b, r, s0, s1, z0, z1, d0, d0 + prof, f, m_cadre)
    cadre_r(b, r, s0 + f, s1 - f, z0 + f, z1 - f, d0, d0 + prof * 0.6, 0.02, m_cadre)
    b.br(r, s0 + f, s1 - f, d0, d0 + 0.015, z0 + f, z1 - f, M["foyer"])
    pts = [r.p(s0 + f, d0 + 0.02, z0 + f), r.p(s1 - f, d0 + 0.02, z0 + f), r.p(s1 - f, d0 + 0.02, z1 - f),
           r.p(s0 + f, d0 + 0.02, z1 - f)]
    b.quad_uv(pts, m_toile, [(0, 0), (1, 0), (1, 1), (0, 1)])


def tapis(pid, nom, cx, cy, lx, ly, m, rot=0.0, z=0.01, frange=True):
    b = Bld()
    ca, sa = math.cos(rot), math.sin(rot)

    def p(u, v, zz):
        return (cx + u * ca - v * sa, cy + u * sa + v * ca, zz)
    h = 0.012
    b.solide([p(-lx / 2, -ly / 2, 0)[:2], p(lx / 2, -ly / 2, 0)[:2], p(lx / 2, ly / 2, 0)[:2], p(-lx / 2, ly / 2, 0)[:2]],
             z, z + h - 0.001, M["frange"])
    b.quad_uv([p(-lx / 2, -ly / 2, z + h), p(lx / 2, -ly / 2, z + h), p(lx / 2, ly / 2, z + h), p(-lx / 2, ly / 2, z + h)],
              m, [(0, 0), (1, 0), (1, 1), (0, 1)])
    if frange:
        for sg in (-1, 1):
            b.quad_uv([p(sg * lx / 2, -ly / 2, z + 0.004), p(sg * (lx / 2 + 0.07), -ly / 2, z + 0.004),
                       p(sg * (lx / 2 + 0.07), ly / 2, z + 0.004), p(sg * lx / 2, ly / 2, z + 0.004)][::sg],
                      M["frange"], [(0, 0), (1, 0), (1, 1), (0, 1)])
    return b.objet(pid + "_" + nom, recalc=False)


def rideaux(b, r, w, z_haut, m, z_embrasse=1.15, ampleur=0.42, cote=(-1, 1), d0=0.06, plis=7):
    """Paire de rideaux à embrasses de part et d'autre d'une baie (repère r centré sur la baie)."""
    nu, nv = 14, 12
    for sg in cote:
        s_int = sg * (w / 2 - 0.12)
        s_ext = sg * (w / 2 + ampleur)
        grille, uvs = [], []
        for j in range(nv + 1):
            z = 0.02 + (z_haut - 0.02) * j / nv
            if z >= z_embrasse:
                g = 0.35 + 0.65 * ((z - z_embrasse) / (z_haut - z_embrasse)) ** 0.8
            else:
                g = 0.35 + 0.35 * ((z_embrasse - z) / z_embrasse) ** 1.5
            ligne, luv = [], []
            for i in range(nu + 1):
                t = i / nu
                s = s_ext + (s_int - s_ext) * t * g
                d = d0 + 0.03 + 0.035 * math.sin(2 * math.pi * plis * t) * (0.6 + 0.4 * g)
                ligne.append(r.p(s, d, z))
                luv.append((t * ampleur * 2.2 / 0.3, z / 0.3))
            grille.append(ligne)
            uvs.append(luv)
        b.nappe(grille, m, uvs)
        se = s_ext + (s_int - s_ext) * 0.35
        b.tige(r.p(s_ext, 0.02, z_embrasse), r.p(se, d0 + 0.07, z_embrasse), 0.015, M["laiton"], n=5)
    b.tige(r.p(-w / 2 - ampleur - 0.15, d0 + 0.05, z_haut + 0.06), r.p(w / 2 + ampleur + 0.15, d0 + 0.05, z_haut + 0.06),
           0.018, M["laiton"], n=8)
    for sg in (-1, 1):
        p = r.p(sg * (w / 2 + ampleur + 0.17), d0 + 0.05, z_haut + 0.06)
        b.tige(p - r.t * 0.04 * sg * -1, p + r.t * 0.04 * sg, 0.035, M["laiton"], n=8)
        b.tige(r.p(sg * (w / 2 + ampleur), 0, z_haut + 0.06), r.p(sg * (w / 2 + ampleur), d0 + 0.05, z_haut + 0.06),
               0.01, M["laiton"], n=4)


def cantonniere(b, r, w, z_haut, m, d0=0.10):
    """Cantonnière bouffante (salon P27-P29) : deux lés festonnés."""
    nu = 16
    for couche, (h, dd) in enumerate(((0.45, d0 + 0.05), (0.32, d0 + 0.10))):
        haut, bas, uvh, uvb = [], [], [], []
        for i in range(nu + 1):
            t = i / nu
            s = -w / 2 - 0.25 + (w + 0.5) * t
            sag = h * (0.55 + 0.45 * math.sin(math.pi * t))
            gonfle = 0.05 * math.sin(math.pi * t)
            haut.append(r.p(s, dd, z_haut + 0.08))
            bas.append(r.p(s, dd + gonfle, z_haut + 0.08 - sag))
            uvh.append((s / 0.3, 1))
            uvb.append((s / 0.3, 0))
        b.nappe([bas, haut], m, [uvb, uvh])


def store_bateau(b, r, w, z_haut, m, d=0.08):
    for k in range(4):
        z = z_haut - 0.06 - k * 0.11
        b.br(r, -w / 2, w / 2, d, d + 0.06 - k * 0.005, z - 0.10, z, m)
    b.br(r, -w / 2 - 0.02, w / 2 + 0.02, 0.0, d + 0.06, z_haut - 0.06, z_haut, m)


# ----------------------------------------------------------------------------------------------
# Décor commun d'une pièce : parquet, revêtements, chambranles, corniche
# ----------------------------------------------------------------------------------------------
def decor_murs(pid, couches, panneaux_cfg=None, chambranle=None, dessus=None, fen_chambranle=None):
    """couches : [(z0, z1, épaisseur, matériau)] ; panneaux_cfg : dict des panneaux moulurés."""
    b = Bld()
    for s in SEGS[pid]:
        for z0, z1, ep, m in couches:
            bande(b, s, z0, z1, 0.0, ep, m)
        if panneaux_cfg:
            for cfg in panneaux_cfg:
                panneaux(b, s, **cfg)
    if chambranle:
        chambranles(b, pid, chambranle, dessus=dessus)
    if fen_chambranle:
        chambranles(b, pid, fen_chambranle, larg=0.12, saillie=0.04, genres=("fenetre",))
    return b.objet(pid + "_revetements")


# ================================================================================================
# SALON BOW-WINDOW (P27-P31) — mur nord au tableau marine (D-015)
# ================================================================================================
log("salon…")
PID = "salon"
HSP = PIECES[PID]["hauteur_sous_plafond"]
parquet(PID, M["parquet"])
decor_murs(PID, [(0.0, 0.18, 0.025, M["gris_bleu_fonce"]), (0.18, 0.92, 0.012, M["gris_bleu"]),
                 (0.92, 0.97, 0.035, M["gris_bleu_fonce"]), (0.97, 4.30, 0.008, M["damas_salon"])],
           panneaux_cfg=[dict(z0=0.28, z1=0.82, d_fond=0.012, larg_cible=0.85, m_cadre=M["gris_bleu_fonce"],
                              marge=0.16)],
           chambranle=M["gris_bleu_fonce"], fen_chambranle=M["blanc_peint"])
# corniche, plafond à grand caisson (bandeau abaissé, angles coupés côté baie), rosace rocaille
b = Bld()
poly = ccw(PIECES[PID]["polygone_interieur"])
loft(b, poly, [(0.0, 4.30), (0.0, 4.33), (0.03, 4.36), (0.04, 4.45), (0.10, 4.50), (0.12, 4.58), (0.22, 4.62),
               (0.26, 4.62)], M["blanc"])
simple = ccw([(-3.7, 4.15), (3.7, 4.15), (3.7, 8.75), (2.702, 8.75), (1.902, 10.65), (-1.902, 10.65),
              (-2.702, 8.75), (-3.7, 8.75)])
loft(b, simple, [(0.24, 4.62), (0.95, 4.62), (0.95, 4.66), (0.99, 4.70), (1.01, 4.78), (1.07, 4.84), (1.10, 4.92),
                 (1.20, 4.96), (1.24, 4.99)], M["blanc"])
b.objet(PID + "_corniche_caisson", recalc=False)
cs = decaler(simple, 1.24)
cx_s = sum(p[0] for p in cs) / len(cs)
cy_s = (min(p[1] for p in cs) + max(p[1] for p in cs)) / 2
rosace(PID + "_rosace", 0.0, cy_s, HSP - 0.005, 1.2)
lustre(PID, "lustre", 0.0, cy_s, HSP - 0.15, 2.45, 1.15, 260)
# mur nord : tableau marine centré, commode galbée, potiche, dracaenas (P29-P31)
b = Bld()
r = rep_mur(PID, "nord", 0.1)
tableau(b, r, 0.0, 1.20, 2.60, 1.40, M["toile_marine"], f=0.11, d0=0.01)
# mur est : portrait en pied entre la porte du billard et la baie, fusil (P28-P29)
r = rep_mur(PID, "est", 7.15)
tableau(b, r, 0.0, 1.25, 0.95, 1.35, M["toile_portrait"], d0=0.01)
# mur ouest : tableau sombre à cadre doré (P28)
r = rep_mur(PID, "ouest", 7.0)
tableau(b, r, 0.0, 1.35, 0.90, 1.20, M["toile_sombre"], d0=0.01)
b.objet(PID + "_tableaux")
x, y, n = contre(PID, "nord", 0.15, 0.6)
poser(P_COMMODE, PID + "_commode", x, y, face=n)
lampe_potiche(PID, "lampe_commode", x + 0.25, y - 0.05, 0.90)
for xx in (-1.40, 1.55):
    xp, yp, n = contre(PID, "nord", xx, 0.45)
    poser(P_DRACAENA, PID + "_dracaena", xp, yp, face=n, rot=0)
x, y, n = contre(PID, "est", 7.15, 0.40)
poser(P_CONSOLE_L16, PID + "_console", x, y, face=n)
b = Bld()
b.tour(x, y + 0.15, [(0.06, 0), (0.06, 0.08), (0, 0.09)], M["porcelaine"], n=10, z0=0.80)
b.objet(PID + "_coffret")
x, y, n = contre(PID, "est", 6.2, 0.5)
poser(P_MONSTERA, PID + "_monstera", x, y, face=n, ech=1.1)
xf, yf_, n = contre(PID, "est", 6.25, 0.04, 0.0)
poser(P_FUSIL, PID + "_fusil", xf, yf_, 2.15, face=n)
# groupe de bergères autour de la table basse, face à la baie (P27-P29)
cx, cy = -0.15, 8.55
poser(P_TB_VERRE, PID + "_table_basse", cx, cy, face=(0, -1))
for bx, by, fx, fy in ((-1.05, 9.45, 0.7, -0.7), (0.80, 9.40, -0.7, -0.7), (-1.20, 7.70, 0.8, 0.6), (0.20, 7.35, 0, 1)):
    poser(P_BERGERE, PID + "_bergere", cx + bx + 0.15, by, face=(fx, fy))
# baie : radiateur à cache, maquette de voilier, lampes potiches, sabres (P27-P29)
sb = seg_card(PID, "sud", 0.0)
r = Rep((0.0, 10.65), sb["d"], sb["n"])
p = r.p(0, 0.16, 0)
poser(P_RAD_SALON, PID + "_radiateur", p.x, p.y, face=(sb["n"].x, sb["n"].y))
poser(P_VOILIER, PID + "_maquette_voilier", p.x, p.y, 0.81, face=(sb["n"].x, sb["n"].y), ech=0.9)
for s in (-0.55, 0.55):
    q = r.p(s, 0.16, 0)
    lampe_potiche(PID, "lampe_baie", q.x, q.y, 0.81, ech=0.70)
for s in (-1.33, 1.33):
    q = r.p(s, 0.04, 0)
    poser(P_SABRE, PID + "_sabre", q.x, q.y, 2.0, face=(sb["n"].x, sb["n"].y))
# rideaux soie rayée or et gris, cantonnières jaunes, store bateau jaune
b = Bld()
for s in SEGS[PID]:
    for o in s["ouv"]:
        if o["genre"] != "fenetre":
            continue
        uc = (o["u0"] + o["u1"]) / 2
        rr = rep_seg(s, uc)
        w = o["u1"] - o["u0"]
        if o["z0"] > 0.5:
            store_bateau(b, rr, w + 0.1, 3.50, M["soie_jaune"])
        else:
            rideaux(b, rr, w, 3.85, M["rideau_salon"], ampleur=0.32, z_embrasse=1.05)
            cantonniere(b, rr, w, 3.85, M["soie_jaune"])
b.objet(PID + "_rideaux", recalc=False)
lampadaire(PID, "lampadaire", -3.15, 6.25, 2)
poser(P_KENTIA, PID + "_kentia", -1.0, 4.75)

# ================================================================================================
# BILLARD (P32-P35) — long côté nord-sud, cheminée mur est entre 2 portes (D-017, D-019)
# ================================================================================================
log("billard…")
PID = "billard"
HSP = PIECES[PID]["hauteur_sous_plafond"]
parquet(PID, M["versailles"])


def dessus_billard(b, r, o):
    """Huisserie noyer : entablement et dessus-de-porte peint (P33-P35)."""
    u0, u1, z1 = o["u0"], o["u1"], o["z1"]
    b.br(r, u0 - 0.24, u1 + 0.24, 0, 0.14, z1 + 0.16, z1 + 0.30, M["noyer"])
    b.br(r, u0 - 0.28, u1 + 0.28, 0, 0.18, z1 + 0.30, z1 + 0.36, M["noyer"])
    tableau(b, r, (u0 + u1) / 2, z1 + 0.38, (u1 - u0) + 0.1, 0.60, M["fleurs"], m_cadre=M["noyer"], f=0.08, d0=0.0)


decor_murs(PID, [(0.0, 0.24, 0.025, M["noyer"]), (0.24, 4.45, 0.008, M["damas_billard"])],
           chambranle=M["noyer"], dessus=dessus_billard, fen_chambranle=M["blanc_peint"])
for s in SEGS[PID]:
    for o in s["ouv"]:
        if o["genre"] == "porte" and o["autre"] == "degagement_est":
            uc = (o["u0"] + o["u1"]) / 2
            q = rep_seg(s, uc).p(0, 0.14, o["z1"] + 0.15)
            poser(P_SORTIE, PID + "_panneau_sortie", q.x, q.y, q.z, face=(s["n"].x, s["n"].y))
# plafond à caissons octogonaux : corniche vert d'eau, poutres brun-rouge, caissons peints (P32-P35)
poly = ccw(PIECES[PID]["polygone_interieur"])
b = Bld()
loft(b, poly, [(0.0, 4.45), (0.0, 4.48), (0.03, 4.50), (0.04, 4.58), (0.12, 4.64), (0.14, 4.72), (0.26, 4.78),
               (0.30, 4.82), (0.36, 4.82)], M["vert_eau"])
loft(b, poly, [(0.36, 4.80), (0.62, 4.80), (0.62, 4.99)], M["poutre"])
b.objet(PID + "_corniche", recalc=False)
X0, X1 = 4.3 + 0.62, 10.5 - 0.62
Y0, Y1 = -1.4 + 0.62, 8.15 - 0.62
NX, NY = 3, 4
LB = 0.24
xs = [X0 + (X1 - X0) * k / NX for k in range(NX + 1)]
ys = [Y0 + (Y1 - Y0) * k / NY for k in range(NY + 1)]
b = Bld()
for x in xs[1:-1]:
    b.boite(x - LB / 2, Y0, 4.76, x + LB / 2, Y1, 4.99, M["poutre"])
    for sg in (-1, 1):
        b.boite(x + sg * LB / 2 - 0.02, Y0, 4.74, x + sg * LB / 2 + 0.02, Y1, 4.78, M["vert_eau"])
for y in ys[1:-1]:
    for xa, xb in zip(xs[:-1], xs[1:]):
        a, c = xa + (LB / 2 if xa > X0 else 0), xb - (LB / 2 if xb < X1 else 0)
        b.boite(a, y - LB / 2, 4.77, c, y + LB / 2, 4.99, M["poutre"])
        for sg in (-1, 1):
            b.boite(a, y + sg * LB / 2 - 0.02, 4.755, c, y + sg * LB / 2 + 0.02, 4.785, M["vert_eau"])
b.objet(PID + "_poutres")
# module de caisson (1 × 1, mis à l'échelle de chaque case) : fond peint, octogone vert d'eau, filets bruns
bm_ = Bld()
c_ = 0.29
bm_.quad_uv([(-0.5, -0.5, -0.002), (-0.5, 0.5, -0.002), (0.5, 0.5, -0.002), (0.5, -0.5, -0.002)], M["caisson"],
            [(0, 0), (0, 1), (1, 1), (1, 0)])
octo = [(0.5, -0.5 + c_), (0.5, 0.5 - c_), (0.5 - c_, 0.5), (-0.5 + c_, 0.5), (-0.5, 0.5 - c_), (-0.5, -0.5 + c_),
        (-0.5 + c_, -0.5), (0.5 - c_, -0.5)]
oi = [(x * 0.84, y * 0.84) for x, y in octo]
for i in range(8):
    j = (i + 1) % 8
    bm_.solide([octo[i], octo[j], oi[j], oi[i]], -0.07, -0.002, M["vert_eau"])
for x0, y0, x1, y1 in ((-0.5, -0.5, 0.5, -0.46), (-0.5, 0.46, 0.5, 0.5), (-0.5, -0.46, -0.46, 0.46),
                       (0.46, -0.46, 0.5, 0.46)):
    bm_.boite(x0, y0, -0.09, x1, y1, -0.002, M["poutre"])
P_CAISSON = proto("caisson", bm_, recalc=False)
n_cais = 0
for xa, xb in zip(xs[:-1], xs[1:]):
    a, c = xa + (LB / 2 if xa > X0 else 0), xb - (LB / 2 if xb < X1 else 0)
    for ya, yb in zip(ys[:-1], ys[1:]):
        e, g = ya + (LB / 2 if ya > Y0 else 0), yb - (LB / 2 if yb < Y1 else 0)
        nx, ny = 3, 3
        for i in range(nx):
            for j in range(ny):
                wx, wy = (c - a) / nx, (g - e) / ny
                poser(P_CAISSON, PID + "_caisson", a + wx * (i + 0.5), e + wy * (j + 0.5), 4.99, ech=(wx, wy, 1.0))
                n_cais += 1
log("caissons :", n_cais)
for k, yl in enumerate((ys[1], ys[3])):
    lustre(PID, "lustre_%s" % ("nord" if k == 0 else "sud"), (xs[1] + xs[2]) / 2, yl, 4.76, 2.55, 1.05, 200)
# cheminée monumentale en noyer sculpté à colonnettes, foyer en faïence verte, trumeau à tapisserie (P32-P34)
YC = 3.6
r = rep_mur(PID, "est", YC)
b = Bld()
mn = M["noyer"]
b.br(r, -1.25, 1.25, 0, 0.80, 0.01, 0.035, M["marbre_noir"])
for sg in (-1, 1):
    b.br(r, sg * 0.75, sg * 1.12, 0, 0.50, 0.035, 1.10, mn)
    b.tour(*r.p(sg * 0.93, 0.50, 0).to_2d(), [(0.08, 0), (0.08, 0.08), (0.055, 0.12), (0.045, 0.55), (0.06, 0.62),
                                              (0.045, 0.70), (0.045, 0.98), (0.08, 1.04), (0.08, 1.07)], mn, n=12,
           z0=0.035)
b.br(r, -0.75, 0.75, 0, 0.40, 0.035, 1.06, M["faience"])
b.br(r, -0.44, 0.44, 0.40, 0.405, 0.035, 0.74, M["foyer"])
b.br(r, -0.44, 0.44, 0.05, 0.40, 0.035, 0.05, M["foyer"])
b.br(r, -1.15, 1.15, 0, 0.52, 1.06, 1.26, mn)
for k in range(9):
    s = -0.9 + k * 0.225
    b.br(r, s - 0.06, s + 0.06, 0.52, 0.55, 1.10, 1.22, mn)
b.br(r, -1.25, 1.25, 0, 0.60, 1.26, 1.33, mn)
b.br(r, -1.05, 1.05, 0, 0.22, 1.33, 3.62, mn)
b.br(r, -0.70, 0.70, 0.22, 0.26, 1.42, 1.66, mn)
for k in range(6):
    s = -0.58 + k * 0.232
    b.br(r, s - 0.07, s + 0.07, 0.26, 0.28, 1.47, 1.61, mn)
cadre_r(b, r, -0.70, 0.70, 1.70, 3.10, 0.22, 0.28, 0.07, mn)
b.quad_uv([r.p(-0.63, 0.225, 1.77), r.p(0.63, 0.225, 1.77), r.p(0.63, 0.225, 3.03), r.p(-0.63, 0.225, 3.03)],
          M["tapisserie"], [(0, 0), (1, 0), (1, 1), (0, 1)])
for sg in (-1, 1):
    b.tour(*r.p(sg * 0.87, 0.30, 0).to_2d(), [(0.07, 0), (0.07, 0.06), (0.05, 0.10), (0.04, 0.6), (0.05, 0.9),
                                              (0.04, 1.2), (0.04, 1.62), (0.07, 1.68), (0.07, 1.74)], mn, n=12, z0=1.40)
    b.br(r, sg * 0.80 - 0.09, sg * 0.80 + 0.09, 0, 0.38, 1.33, 1.40, mn)
b.br(r, -1.12, 1.12, 0, 0.36, 3.14, 3.34, mn)
for k in range(12):
    s = -1.0 + k * 0.182
    b.br(r, s - 0.04, s + 0.04, 0.36, 0.39, 3.16, 3.30, mn)
b.br(r, -1.22, 1.22, 0, 0.44, 3.34, 3.44, mn)
b.br(r, -1.05, 1.05, 0, 0.22, 3.44, 3.75, mn)
b.prisme_r(r, [(-0.6, 3.75), (0.6, 3.75), (0.45, 3.90), (0.2, 3.98), (0.0, 4.05), (-0.2, 3.98), (-0.45, 3.90)], 0.0,
           0.16, mn)
b.br(r, -1.12, 1.12, 0, 0.30, 3.62, 3.68, mn)
b.objet(PID + "_cheminee")
q = r.p(0, 0.70, 0)
poser(P_PARE_FEU, PID + "_pare_feu", q.x, q.y, face=(r.n.x, r.n.y))
x, y, n = contre(PID, "est", 4.95, 0.40, 0.10)
lampadaire(PID, "lampadaire", x, y, 0)
x, y, n = contre(PID, "est", 2.25, 0.45, 0.15)
poser(P_CHAISE, PID + "_chaise_haute", x, y, face=n, ech=(1, 1, 1.15))
# coin salon devant la cheminée : tapis persan ivoire, table ovale onyx, fauteuils médaillon blancs
tapis(PID, "tapis", 8.45, 3.85, 2.70, 3.50, M["tapis_ivoire"])
poser(P_TB_OVALE, PID + "_table_basse", 8.45, 3.85, face=(0, -1), rot=0)
for fx, fy, nx_, ny_ in ((9.35, 3.05, -1, 0.25), (9.35, 4.75, -1, -0.25), (7.35, 3.10, 1, 0.3), (7.45, 4.85, 1, -0.4)):
    poser(P_MEDAILLON, PID + "_fauteuil_medaillon", fx, fy, face=(nx_, ny_))
# table de billard au nord, long côté est-ouest (P34-P35)
poser(P_BILLARD, PID + "_table_billard", 7.35, 0.95, face=(0, -1))
for cxh, cyh, fx, fy in ((9.35, -0.65, -0.5, 1), (10.05, 0.10, -1, 0.2)):
    poser(P_CHAISE, PID + "_chaise", cxh, cyh, face=(fx, fy))
# mur nord (petit côté entre les deux portes) : console, lampe blanche, tableau paysage, deux chaises
x, y, n = contre(PID, "nord", 6.97, 0.42)
poser(P_CONSOLE_NORD, PID + "_console_nord", x, y, face=n)
lampe_blanche(PID, "lampe_nord", x, y + 0.02, 0.78)
poser(P_CADRE, PID + "_tableau_nord", 6.97, -1.4 + 0.012, 1.75, face=n, ech=1.6)
# mur ouest : vaisselier, chevet, console galbée à deux lampes sous un paysage (P34-P35)
x, y, n = contre(PID, "ouest", 0.85, 0.50)
poser(P_VAISSELIER, PID + "_vaisselier", x, y, face=n)
x, y, n = contre(PID, "ouest", 2.05, 0.40)
poser(P_CHEVET, PID + "_chevet", x, y, face=n)
x, y, n = contre(PID, "ouest", 3.30, 0.45)
poser(P_CONSOLE_GALBEE, PID + "_console_ouest", x, y, face=n)
for dy in (-0.42, 0.42):
    lampe_blanche(PID, "lampe_ouest", x, y + dy, 0.82)
poser(P_CADRE, PID + "_tableau_ouest", 4.3 + 0.012, 3.30, 1.85, face=n, ech=1.7)
# mur sud entre les portes-fenêtres : console Louis-Philippe, statue bronze, paysage ; radiateurs (P32-P34)
x, y, n = contre(PID, "sud", 7.10, 0.45)
poser(P_CONSOLE_LP, PID + "_console_sud", x, y, face=n, ech=(0.62, 0.75, 0.88))
poser(P_STATUE, PID + "_statue", x, y + 0.02, 0.835, face=n)
b = Bld()
tableau(b, rep_mur(PID, "sud", 7.10), 0.0, 1.90, 1.05, 0.75, M["toile_paysage"], d0=0.01)
b.objet(PID + "_tableaux")
for xr in (6.30, 9.98):
    x, y, n = contre(PID, "sud", xr, 0.16, 0.05)
    poser(P_RAD_BILLARD, PID + "_radiateur", x, y, face=n)
b = Bld()
for s in SEGS[PID]:
    for o in s["ouv"]:
        if o["genre"] == "fenetre":
            rideaux(b, rep_seg(s, (o["u0"] + o["u1"]) / 2), o["u1"] - o["u0"], 4.30, M["rideau_billard"], ampleur=0.36)
b.objet(PID + "_rideaux", recalc=False)

# ================================================================================================
# SALON VERT (pavillon SE ; W07, W14 en référence seulement) — boiseries vert d'eau à filets dorés
# ================================================================================================
log("salon vert…")
PID = "salon_vert"
parquet(PID, M["parquet"])


def dessus_stuc(b, r, o):
    """Dessus-de-porte en stuc à guirlandes et trophée (W07)."""
    u0, u1, z1 = o["u0"], o["u1"], o["z1"]
    sc = (u0 + u1) / 2
    b.br(r, u0 - 0.15, u1 + 0.15, 0.02, 0.10, z1 + 0.14, z1 + 0.24, M["creme"])
    b.br(r, u0 - 0.05, u1 + 0.05, 0.02, 0.04, z1 + 0.30, z1 + 0.95, M["blanc"])
    for k in range(9):
        t = k / 8
        s = u0 + 0.05 + (u1 - u0 - 0.1) * t
        z = z1 + 0.80 - 0.18 * math.sin(math.pi * t)
        b.br(r, s - 0.06, s + 0.06, 0.04, 0.08, z - 0.05, z + 0.05, M["blanc"])
    b.br(r, sc - 0.12, sc + 0.12, 0.04, 0.09, z1 + 0.40, z1 + 0.78, M["blanc"])
    b.prisme_r(r, [(sc - 0.28, z1 + 0.36), (sc + 0.28, z1 + 0.36), (sc + 0.05, z1 + 0.62), (sc - 0.05, z1 + 0.62)],
               0.04, 0.07, M["blanc"])


decor_murs(PID, [(0.0, 0.16, 0.03, M["creme"]), (0.16, 4.35, 0.02, M["creme"]), (0.90, 0.96, 0.045, M["creme"])],
           panneaux_cfg=[dict(z0=0.24, z1=0.82, d_fond=0.02, larg_cible=0.85, m_cadre=M["creme"], m_fond=M["celadon"],
                              marge=0.18, filet=M["or"]),
                         dict(z0=1.12, z1=4.05, d_fond=0.02, larg_cible=0.85, m_cadre=M["creme"],
                              m_fond=M["celadon"], marge=0.18, filet=M["or"])],
           chambranle=M["creme"], dessus=dessus_stuc, fen_chambranle=M["creme"])
poly = ccw(PIECES[PID]["polygone_interieur"])
b = Bld()
loft(b, poly, [(0.0, 4.35), (0.0, 4.38), (0.04, 4.42), (0.05, 4.52), (0.14, 4.60), (0.17, 4.72), (0.30, 4.80),
               (0.34, 4.90), (0.44, 4.95), (0.50, 4.99)], M["blanc"])
b.objet(PID + "_corniche", recalc=False)
XC = 14.25
rosace(PID + "_rosace", XC, 6.45, 4.995, 1.1)
lustre(PID, "lustre", XC, 6.45, 4.85, 2.60, 1.1, 220)
# cheminée Louis XV en marbre brèche rose au centre du mur nord, trumeau doré, pendule, candélabres
r = rep_mur(PID, "nord", XC)
b = Bld()
mr = M["marbre_rose"]
b.br(r, -0.95, 0.95, 0, 0.60, 0.01, 0.035, mr)
for sg in (-1, 1):
    b.prisme_r(r, [(sg * 0.55, 0.035), (sg * 0.82, 0.035), (sg * 0.80, 0.12), (sg * 0.72, 0.30), (sg * 0.78, 0.85),
                   (sg * 0.82, 0.95), (sg * 0.55, 0.95)], 0.0, 0.32, mr)
lin = [(-0.84, 0.95), (0.84, 0.95), (0.84, 1.10), (-0.84, 1.10)]
b.prisme_r(r, lin, 0.0, 0.34, mr)
arc = [(0.55, 0.95)] + [(0.55 * math.cos(math.pi * t), 0.80 + 0.13 * math.sin(math.pi * t) ** 0.6)
                        for t in np.linspace(0.05, 0.95, 9)] + [(-0.55, 0.95)]
b.prisme_r(r, arc[::-1], 0.0, 0.32, mr)
b.prisme_r(r, [(-0.12, 0.88), (0.12, 0.88), (0.15, 1.0), (0.0, 1.08), (-0.15, 1.0)], 0.32, 0.37, mr)
b.br(r, -0.90, 0.90, 0, 0.40, 1.10, 1.16, mr)
b.br(r, -0.55, 0.55, 0, 0.02, 0.035, 0.85, M["foyer"])
b.br(r, -0.55, 0.55, 0.02, 0.30, 0.035, 0.04, M["foyer"])
# trumeau-miroir doré à fronton cintré
b.br(r, -0.72, 0.72, 0.02, 0.03, 1.22, 3.60, M["glace"])
cadre_r(b, r, -0.80, 0.80, 1.16, 3.66, 0.02, 0.08, 0.09, M["or"])
b.prisme_r(r, [(-0.80, 3.62), (0.80, 3.62), (0.70, 3.85), (0.35, 4.02), (0.0, 4.08), (-0.35, 4.02), (-0.70, 3.85)],
           0.02, 0.08, M["or"])
for sg in (-1, 1):
    b.tige(r.p(sg * 0.6, 0.08, 3.85), r.p(sg * 0.2, 0.08, 4.02), 0.03, M["or"], n=6)
b.objet(PID + "_cheminee")
q = r.p(0, 0.20, 0)
poser(P_PENDULE, PID + "_pendule", q.x, q.y, 1.16, face=(r.n.x, r.n.y))
for sg in (-1, 1):
    q = r.p(sg * 0.55, 0.20, 0)
    poser(P_CANDELABRE, PID + "_candelabre", q.x, q.y, 1.16, face=(r.n.x, r.n.y))
q = r.p(0.95, 0.30, 0)
poser(P_SERVITEUR, PID + "_serviteur", q.x, q.y)
x, y, n = contre(PID, "nord", XC - 1.35, 0.5, 0.05)
lampadaire(PID, "lampadaire", x, y, 2)
# tapis rouge à médaillon, fauteuils Louis XV crème et lilas, tables gigognes (W07)
tapis(PID, "tapis", XC, 6.30, 4.0, 3.0, M["tapis_rouge"])
poser(P_GIGOGNES, PID + "_tables_gigognes", XC, 6.0, face=(0, -1))
for fx, fy, nx_, ny_ in ((XC - 0.9, 5.20, 0.4, 1), (XC + 0.85, 5.20, -0.4, 1), (XC - 1.0, 7.00, 0.5, -1),
                         (XC + 0.9, 7.05, -0.5, -1)):
    poser(P_LOUIS_XV, PID + "_fauteuil", fx, fy, face=(nx_, ny_))
# table à jeu acajou et quatre chaises rouges (coin nord-est)
poser(P_TABLE_JEU, PID + "_table", 16.45, 5.00, rot=math.pi / 2)
for cxh, cyh, fx, fy in ((15.72, 4.65, 1, 0), (15.72, 5.35, 1, 0), (16.45, 6.10, 0, -1)):
    poser(P_CHAISE, PID + "_chaise", cxh, cyh, face=(fx, fy))
# mur ouest au sud de la porte : console Louis XVI, photophore, miroir doré ; mur est : paysage au couchant
x, y, n = contre(PID, "ouest", 7.45, 0.42)
poser(P_CONSOLE_VERT, PID + "_console", x, y, face=n)
poser(P_MIROIR, PID + "_miroir", 11.1 + 0.03, 7.45, 1.65, face=n, ech=2.0)
b = Bld()
b.tour(x, y, [(0.06, 0), (0.07, 0.2), (0.0, 0.2)], M["verre"], n=10, z0=0.80)
b.tour(x, y, [(0.03, 0), (0.03, 0.12), (0, 0.12)], M["porcelaine"], n=8, z0=0.80)
tableau(b, rep_mur(PID, "est", 4.95), 0.0, 1.60, 0.62, 0.78, M["toile_couchant"], d0=0.02)
b.objet(PID + "_objets")
poser(P_TABLE_RONDE_PETITE, PID + "_gueridon", 16.85, 8.30, rot=0, ech=(0.5, 0.75, 1.3))
lampe_blanche(PID, "lampe_gueridon", 16.85, 8.30, 0.585)
b = Bld()
for s in SEGS[PID]:
    for o in s["ouv"]:
        if o["genre"] == "fenetre":
            rideaux(b, rep_seg(s, (o["u0"] + o["u1"]) / 2), o["u1"] - o["u0"], 4.15, M["rideau_vert"], ampleur=0.36)
b.objet(PID + "_rideaux", recalc=False)

# ================================================================================================
# SALON OUEST (non vu, symétrique du billard : meublé sobrement, style du salon)
# ================================================================================================
log("salon ouest…")
PID = "salon_ouest"
parquet(PID, M["parquet"])
decor_murs(PID, [(0.0, 0.18, 0.025, M["gris_bleu_fonce"]), (0.18, 0.92, 0.012, M["gris_bleu"]),
                 (0.92, 0.97, 0.035, M["gris_bleu_fonce"]), (0.97, 4.40, 0.008, M["damas_ouest"])],
           panneaux_cfg=[dict(z0=0.28, z1=0.82, d_fond=0.012, larg_cible=0.9, m_cadre=M["gris_bleu_fonce"])],
           chambranle=M["gris_bleu_fonce"], fen_chambranle=M["blanc_peint"])
poly = ccw(PIECES[PID]["polygone_interieur"])
b = Bld()
loft(b, poly, [(0.0, 4.40), (0.0, 4.43), (0.04, 4.47), (0.05, 4.56), (0.14, 4.63), (0.17, 4.74), (0.30, 4.82),
               (0.34, 4.91), (0.44, 4.96), (0.50, 4.99)], M["blanc"])
b.objet(PID + "_corniche", recalc=False)
rosace(PID + "_rosace", -7.4, 3.4, 4.995, 1.0)
lustre(PID, "lustre", -7.4, 3.4, 4.85, 2.65, 1.0, 200)
x, y, n = contre(PID, "ouest", 3.4, 0.66)
poser(P_CANAPE, PID + "_canape", x, y, face=n, ech=1.15)
b = Bld()
tableau(b, rep_mur(PID, "ouest", 3.4), 0.0, 1.45, 1.40, 1.0, M["toile_paysage"], d0=0.01)
tableau(b, rep_mur(PID, "est", 2.0), 0.0, 1.5, 0.8, 1.05, M["toile_sombre"], d0=0.01)
b.objet(PID + "_tableaux")
tapis(PID, "tapis", -8.05, 3.4, 2.4, 3.2, M["tapis_bleu"])
poser(P_TB_OVALE, PID + "_table_basse", -8.35, 3.4, rot=math.pi / 2)
for fy in (2.25, 4.55):
    poser(P_BERGERE, PID + "_bergere", -7.05, fy, face=(-0.8, 3.4 - fy))
x, y, n = contre(PID, "nord", -7.4, 0.42)
poser(P_CONSOLE_L16, PID + "_console", x, y, face=n)
poser(P_MIROIR, PID + "_miroir", -7.4, -1.4 + 0.03, 1.70, face=n, ech=2.2)
lampe_potiche(PID, "lampe_console", x - 0.3, y, 0.80)
poser(P_GUERIDON, PID + "_table_ronde", -7.05, 6.9, ech=(0.75, 0.75, 0.76))
for a in (0.0, 2.1, 4.2):
    poser(P_CHAISE, PID + "_chaise", -7.05 + 0.75 * math.sin(a), 6.9 - 0.75 * math.cos(a),
          face=(-math.sin(a), math.cos(a)))
for yy in (0.0, 6.0):
    x, y, n = contre(PID, "ouest", yy + 0.2, 0.45)
    poser(P_DRACAENA_TC, PID + "_plante", x, y, face=n)
b = Bld()
for s in SEGS[PID]:
    for o in s["ouv"]:
        if o["genre"] == "fenetre":
            rideaux(b, rep_seg(s, (o["u0"] + o["u1"]) / 2), o["u1"] - o["u0"], 4.20, M["rideau_salon"], ampleur=0.36)
b.objet(PID + "_rideaux", recalc=False)

# ================================================================================================
# PIÈCE NORD-OUEST (non vue : petit bureau sobre)
# ================================================================================================
log("pièce nord-ouest…")
PID = "piece_no"
HSP = PIECES[PID]["hauteur_sous_plafond"]
parquet(PID, M["parquet"])
decor_murs(PID, [(0.0, 0.20, 0.025, M["noyer"]), (0.20, 0.95, 0.015, M["noyer"]), (0.95, 1.0, 0.035, M["noyer"]),
                 (1.0, 3.90, 0.008, M["damas_no"])],
           panneaux_cfg=[dict(z0=0.30, z1=0.85, d_fond=0.015, larg_cible=0.8, m_cadre=M["noyer"])],
           chambranle=M["noyer"], fen_chambranle=M["blanc_peint"])
poly = ccw(PIECES[PID]["polygone_interieur"])
b = Bld()
loft(b, poly, [(0.0, 3.90), (0.0, 3.93), (0.04, 3.97), (0.05, 4.07), (0.14, 4.15), (0.17, 4.27), (0.30, 4.35),
               (0.34, 4.42), (0.44, 4.46), (0.50, 4.49)], M["blanc"])
b.objet(PID + "_corniche", recalc=False)
rosace(PID + "_rosace", -14.25, -6.5, HSP - 0.005, 0.8)
lustre(PID, "lustre", -14.25, -6.5, HSP - 0.12, 2.45, 0.85, 150)
tapis(PID, "tapis", -14.5, -6.6, 3.0, 2.2, M["tapis_rouge"], rot=0.0)
poser(P_BUREAU, PID + "_bureau", -14.5, -6.0, face=(0, 1))
poser(P_FAUTEUIL_VERT, PID + "_fauteuil_bureau", -14.5, -5.35, face=(0, -1))
for fx in (-15.0, -14.0):
    poser(P_MEDAILLON, PID + "_fauteuil", fx, -7.4, face=(0, 1))
lampe_blanche(PID, "lampe_bureau", -15.05, -6.15, 0.76)
x, y, n = contre(PID, "sud", -14.25, 0.42)
poser(P_BIBLIO, PID + "_bibliotheque", x, y, face=n, ech=(1.3, 1.0, 1.0))
x, y, n = contre(PID, "ouest", -5.0, 0.42)
poser(P_CONSOLE_L16, PID + "_console", x, y, face=n)
b = Bld()
tableau(b, rep_mur(PID, "ouest", -5.0), 0.0, 1.35, 0.9, 0.7, M["toile_paysage"], d0=0.01)
b.objet(PID + "_tableaux")
x, y, n = contre(PID, "nord", -16.6, 0.45)
poser(P_DRACAENA_TC, PID + "_plante", x, y, face=n)
b = Bld()
for s in SEGS[PID]:
    for o in s["ouv"]:
        if o["genre"] == "fenetre":
            rideaux(b, rep_seg(s, (o["u0"] + o["u1"]) / 2), o["u1"] - o["u0"], 3.75, M["rideau_billard"], ampleur=0.32)
b.objet(PID + "_rideaux", recalc=False)

# ================================================================================================
# DÉGAGEMENT EST (non vu : passage du billard au couloir est, sol de marbre de la coque)
# ================================================================================================
log("dégagement est…")
PID = "degagement_est"
HSP = PIECES[PID]["hauteur_sous_plafond"]
decor_murs(PID, [(0.0, 0.15, 0.02, M["blanc_peint"]), (0.15, 3.95, 0.008, M["damas_deg"])],
           chambranle=M["blanc_peint"])
poly = ccw(PIECES[PID]["polygone_interieur"])
b = Bld()
loft(b, poly, [(0.0, 3.95), (0.0, 3.98), (0.04, 4.02), (0.05, 4.12), (0.14, 4.20), (0.17, 4.32), (0.28, 4.40),
               (0.32, 4.46), (0.36, 4.49)], M["blanc"])
b.objet(PID + "_corniche", recalc=False)
ob = poser(P_LANTERNE, PID + "_lanterne", 7.4, -3.95, 3.15)
b = Bld()
chaine(b, 7.4, -3.95, 3.83, HSP - 0.01)
b.objet(PID + "_lanterne_tige")
lumiere("lumiere_degagement_est_lanterne", 7.4, -3.95, 3.40, 120, rayon=0.15)
x, y, n = contre(PID, "est", -3.95, 0.42)
poser(P_CONSOLE_L16, PID + "_console", x, y, face=n)
poser(P_MIROIR, PID + "_miroir", 10.5 - 0.03, -3.95, 1.65, face=n, ech=1.8)
lampe_potiche(PID, "lampe_console", x, y - 0.25, 0.80)
x, y, n = contre(PID, "ouest", -3.95, 0.40)
poser(P_BANC, PID + "_banquette", x, y, face=n)
b = Bld()
tableau(b, rep_mur(PID, "ouest", -3.95), 0.0, 1.30, 1.0, 0.75, M["toile_marine"], d0=0.01)
b.objet(PID + "_tableaux")
for yy in (-5.85, -2.05):
    x, y, n = contre(PID, "est", yy, 0.45)
    poser(P_DRACAENA_TC, PID + "_plante", x, y, face=n)

# ----------------------------------------------------------------------------------------------
# Contrôles : dégagement devant chaque porte (≥ 0,8 m), objets hors des murs
# ----------------------------------------------------------------------------------------------
bpy.context.view_layer.update()
EXCLUS = ("_parquet", "_revetements", "_corniche", "_tapis", "_rideaux", "_plafond", "_poutres", "_caisson",
          "_rosace", "_lustre", "_tige", "_tableau", "_panneau_sortie", "_miroir", "_fusil", "_sabre", "_objets")
conflits = []
for pid in MES_PIECES:
    for s in SEGS[pid]:
        for o in s["ouv"]:
            if o["genre"] != "porte":
                continue
            r = rep_seg(s, 0)
            zone = [r.p(o["u0"], 0, 0), r.p(o["u1"], 0, 0), r.p(o["u1"], 0.8, 0), r.p(o["u0"], 0.8, 0)]
            zx0, zx1 = min(p.x for p in zone) + 0.02, max(p.x for p in zone) - 0.02
            zy0, zy1 = min(p.y for p in zone) + 0.02, max(p.y for p in zone) - 0.02
            for ob in COL.objects:
                if ob.type != "MESH" or any(e in ob.name for e in EXCLUS):
                    continue
                cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
                if min(c.z for c in cs) > 2.0:
                    continue
                if max(c.x for c in cs) > zx0 and min(c.x for c in cs) < zx1 and \
                        max(c.y for c in cs) > zy0 and min(c.y for c in cs) < zy1:
                    conflits.append((pid, o["nom"], ob.name))
for c in conflits:
    log("DÉGAGEMENT INSUFFISANT", c)
log("objets :", len(COL.objects), "conflits de porte :", len(conflits))

# ----------------------------------------------------------------------------------------------
# Export (collection du composant seulement ; lumières ponctuelles KHR_lights_punctual)
# ----------------------------------------------------------------------------------------------
lc = bpy.context.view_layer.layer_collection.children[ID]
bpy.context.view_layer.active_layer_collection = lc
glb = os.path.join(EXPORT, ID + ".glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_active_collection=True, export_lights=True,
                          export_apply=True, export_yup=True, export_image_format="JPEG", export_jpeg_quality=85)
log("glb :", glb, "%.1f Mo" % (os.path.getsize(glb) / 1e6))
try:
    bpy.ops.file.pack_all()
except RuntimeError as ex:
    log("pack_all :", ex)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(EXPORT, ID + ".blend"), compress=True)

# ----------------------------------------------------------------------------------------------
# Rendus de contrôle : coque et bati importés, portes ouvertes, miroir Y (D-026) pour comparer aux photos
# ----------------------------------------------------------------------------------------------
SEULE = os.environ.get("SALONS_VUES")
if os.environ.get("SALONS_SANS_RENDU"):
    log("fin (sans rendu)")
    sys.exit(0)
lcx = bpy.context.view_layer.layer_collection.children["contexte_rendu"]
bpy.context.view_layer.active_layer_collection = lcx
for f in ("coque.glb", "bati.glb"):
    avant = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(EXPORT, f))
    log("contexte :", f, len(set(bpy.data.objects) - avant), "objets")
# vantaux des pièces du groupe ouverts
for pid in MES_PIECES:
    for po in PIECES[pid]["portes"]:
        for v in po["vantaux"]:
            ob = bpy.data.objects.get(v["objet"])
            if ob is None or ob.get("_ouvert"):
                continue
            pv = Vector(v["pivot"])
            ob.matrix_world = Matrix.Translation(pv) @ Matrix.Rotation(math.radians(v["angle_ouverture_z_deg"]), 4, "Z") \
                @ Matrix.Translation(-pv) @ ob.matrix_world
            ob["_ouvert"] = True

for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        SC.render.engine = eng
        break
    except TypeError:
        continue
try:
    SC.eevee.taa_render_samples = 48
    SC.eevee.use_shadows = True
    SC.eevee.use_raytracing = True
except Exception:
    pass
w = bpy.data.worlds.new("ciel")
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.62, 0.70, 0.85, 1)
bg.inputs["Strength"].default_value = 1.2
SC.world = w
try:
    SC.view_settings.view_transform = "AgX"
    SC.view_settings.look = "AgX - Base Contrast"
except TypeError:
    pass
sol = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", "SUN"))
sol.data.energy = 4.0
sol.data.angle = math.radians(2)
sol.rotation_euler = (math.radians(55), 0, math.radians(200))
CTX.objects.link(sol)
# appoint diffus par pièce (rendus seulement)
for pid in MES_PIECES:
    poly = PIECES[pid]["polygone_interieur"]
    xs_ = [p[0] for p in poly]
    ys_ = [p[1] for p in poly]
    li = bpy.data.lights.new("appoint_" + pid, "AREA")
    li.shape = "RECTANGLE"
    li.size, li.size_y = max(xs_) - min(xs_) - 0.6, max(ys_) - min(ys_) - 0.6
    li.energy = 14 * li.size * li.size_y
    li.color = (1.0, 0.95, 0.88)
    li.use_shadow = False
    lo = bpy.data.objects.new("appoint_" + pid, li)
    lo.location = ((max(xs_) + min(xs_)) / 2, (max(ys_) + min(ys_)) / 2, PIECES[pid]["hauteur_sous_plafond"] - 0.3)
    CTX.objects.link(lo)
# miroir Y global : les rendus se lisent comme les photos (D-026)
miroir = bpy.data.objects.new("miroir_y", None)
CTX.objects.link(miroir)
for ob in list(SC.objects):
    if ob.parent is None and ob is not miroir and ob.type != "CAMERA" and ob.users_collection[0] is not PROTOS:
        ob.parent = miroir
miroir.scale = (1, -1, 1)
bpy.context.view_layer.update()


def camera(nom, pos, cible, focale, portrait=True):
    """Position et cible en repère D-003, passées au miroir (y → −y)."""
    cam = bpy.data.cameras.new(nom)
    cam.lens = focale
    cam.sensor_width = 36
    cam.sensor_fit = "AUTO"
    cam.clip_start = 0.05
    cam.clip_end = 200
    co = bpy.data.objects.new(nom, cam)
    p = Vector((pos[0], -pos[1], pos[2]))
    c = Vector((cible[0], -cible[1], cible[2]))
    co.location = p
    co.rotation_euler = (c - p).to_track_quat("-Z", "Y").to_euler()
    CTX.objects.link(co)
    return co, portrait


VUES = [
    ("salon_P28", camera("cam_p28", (-0.9, 4.55, 1.45), (0.1, 10.6, 1.9), 13), "salon vers la baie (P28)"),
    ("salon_P30", camera("cam_p30", (-0.2, 7.6, 1.45), (0.2, 4.15, 2.1), 14), "salon, mur nord au tableau marine (P30)"),
    ("billard_P34", camera("cam_p34", (8.6, 7.7, 1.45), (6.8, -1.4, 2.2), 13), "billard vers le nord, cheminée à droite (P34)"),
    ("billard_P32", camera("cam_p32", (4.55, 5.4, 1.45), (10.5, 6.2, 2.4), 13), "billard depuis la porte du salon (P32)"),
    ("salon_vert", camera("cam_sv", (14.25, 8.55, 1.5), (14.25, 4.1, 2.0), 15, False), "salon vert face à la cheminée (réf. W07)"),
    ("salon_ouest", camera("cam_so", (-4.7, 7.8, 1.6), (-10.5, 1.0, 1.6), 15, False), "salon ouest (non vu, meublé sobrement)"),
    ("piece_no", camera("cam_no", (-11.6, -8.4, 1.6), (-17.4, -4.6, 1.5), 15, False), "pièce nord-ouest (non vue, bureau sobre)"),
    ("degagement_est", camera("cam_de", (5.0, -1.9, 1.6), (9.5, -6.3, 1.4), 15, False), "dégagement est (non vu)"),
]
FICHIERS = []
for nom, (cam, portrait), legende in VUES:
    if SEULE and nom not in SEULE.split(","):
        continue
    SC.render.resolution_x, SC.render.resolution_y = (900, 1200) if portrait else (1600, 900)
    SC.camera = cam
    f = os.path.join(RENDUS, "%s_%s.png" % (ID, nom))
    SC.render.filepath = f
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log("rendu", os.path.basename(f), "%.1fs" % (time.time() - t))
    FICHIERS.append((f, legende))
json.dump(FICHIERS, open(os.path.join(TEXDIR, "rendus.json"), "w"), ensure_ascii=False)
log("fin")

"""Composants P4.chambres et P4.bureau : décor et mobilier des chambres d'étage (chambre 1 d'angle SE,
chambre 2 à rayures au-dessus du salon, chambre 3 bureau à l'armoire et au tableau marine).

blender -b --factory-startup --python scripts/composants/piece_chambres.py
→ export/composants/piece_chambres.glb, export/composants/piece_chambres.blend, rendus/piece_chambres_*.png

Repère D-003 (+X est, +Y sud, Z haut) : chaque élément est placé selon son orientation réelle dans les
coordonnées de travail/coque.json ; les rendus passent par un miroir Y (D-026) pour se comparer aux photos.
Photos : P47-P49 (chambre 1), P52-P54 (chambre 2), P55-P57 (chambre 3) ; fiches et inventaire P1.
La coque et bati sont importés pour les rendus seulement, jamais exportés ici.
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
from PIL import Image, ImageDraw, ImageFilter

T0 = time.time()
try:
    RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    RACINE = os.path.expanduser("~/IdeaProjects/chateau-saint-victor")
ID = "piece_chambres"
EXPORT = os.path.join(RACINE, "export", "composants")
TEXDIR = os.path.join(EXPORT, ID + "_textures")
RENDUS = os.path.join(RACINE, "rendus")
PH = os.path.join(RACINE, "assets", "polyhaven")
shutil.rmtree(TEXDIR, ignore_errors=True)
for d in (EXPORT, TEXDIR, RENDUS):
    os.makedirs(d, exist_ok=True)

COQUE = json.load(open(os.path.join(RACINE, "travail", "coque.json")))
PIECES = {p["id"]: p for p in COQUE["pieces"]}
random.seed(7)
RNG = np.random.default_rng(7)


def log(*a):
    print("[chambres %5.1fs]" % (time.time() - T0), *a)
    sys.stdout.flush()


Z0 = 5.35                      # sol d'étage (coque)
HSP = 4.0                      # hauteur sous plafond des chambres (D-022)
ZC = Z0 + HSP                  # sous-face du plafond
ZP = Z0 + 0.01                 # dessus du parquet posé
CH = ("chambre_1", "chambre_2", "chambre_3")

# ----------------------------------------------------------------------------------------------
# Scène
# ----------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
COL = bpy.data.collections.new(ID)
SC.collection.children.link(COL)
CTX = bpy.data.collections.new("contexte_rendu")
SC.collection.children.link(CTX)
LIB = bpy.data.collections.new("bibliotheque_assets")
SC.collection.children.link(LIB)


def activer(col):
    lc = next(l for l in bpy.context.view_layer.layer_collection.children if l.collection == col)
    bpy.context.view_layer.active_layer_collection = lc


# ----------------------------------------------------------------------------------------------
# Textures (procédurales ou dérivées des textures CC0 Poly Haven)
# ----------------------------------------------------------------------------------------------
def sauver(nom, arr, q=88):
    a = np.clip(arr, 0, 1)
    if a.ndim == 2:
        a = np.repeat(a[:, :, None], 3, axis=2)
    chemin = os.path.join(TEXDIR, nom + ".jpg")
    Image.fromarray((a * 255).astype(np.uint8)).save(chemin, quality=q)
    return chemin


def charger(chemin, taille=None):
    im = Image.open(chemin).convert("RGB")
    if taille:
        im = im.resize((taille, taille), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def lum(a):
    return a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11


def bruit(n, res, graine, octaves=3):
    """Bruit lisse n×n (somme d'octaves interpolées)."""
    r = np.random.default_rng(graine)
    tot = np.zeros((n, n), np.float32)
    amp = 1.0
    for o in range(octaves):
        k = res * 2 ** o
        g = r.random((k + 1, k + 1)).astype(np.float32)
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC)
        tot += amp * (np.asarray(im).astype(np.float32) / 255 - 0.5)
        amp *= 0.5
    return tot


OAK = charger(os.path.join(PH, "polyhaven-oak_wood_planks", "oak_wood_planks_diff_1k.jpg"))
OAK_L = lum(OAK)


def tex_bois(nom, teinte, taille=512, contraste=1.25):
    """Placage teinté (noyer, acajou…) à partir du grain du chêne Poly Haven."""
    L = np.asarray(Image.fromarray((OAK_L * 255).astype(np.uint8)).resize((taille, taille))).astype(np.float32) / 255
    r = (L / L.mean()) ** contraste
    return sauver(nom, np.array(teinte)[None, None, :] * r[:, :, None])


def echantillon_bois(A, B, ident):
    """Couleur de bois pour des coordonnées A (fil, m) et B (travers, m) et un identifiant de lame."""
    n = OAK.shape[0]
    ppm = n / 2.0                      # la texture couvre 2 m
    h = (ident * 2654435761 % 2 ** 32).astype(np.float64) / 2 ** 32
    h2 = (ident * 40503 % 65536).astype(np.float64) / 65536
    ix = ((A * ppm + h * n) % n).astype(np.int32)
    iy = ((B * ppm + h2 * n) % n).astype(np.int32)
    c = OAK[iy, ix]
    f = (0.86 + 0.26 * h)[..., None]
    return c * f


def tex_versailles(nom, px=1024):
    """Panneau de parquet de Versailles de 1 m : cadre, entrelacs diagonaux, carrés à lames alternées."""
    u, v = np.meshgrid((np.arange(px) + 0.5) / px, (np.arange(px) + 0.5) / px)
    A = np.zeros_like(u)
    B = np.zeros_like(u)
    ident = np.zeros(u.shape, np.int64)
    joint = np.zeros_like(u)
    e = 0.045                          # demi-largeur du cadre (partagé avec le panneau voisin)
    du, dv = np.minimum(u, 1 - u), np.minimum(v, 1 - v)
    cadre = (du < e) | (dv < e)
    horiz = (dv < e) & (dv <= du)
    A = np.where(horiz, u, v)
    B = np.where(horiz, dv, du)
    ident = np.where(horiz, 1 + (v > 0.5), 3 + (u > 0.5))
    joint = np.maximum(joint, np.where(cadre, (np.abs(np.minimum(du, dv) - e) < 0.0025), 0))
    # intérieur : entrelacs à 45° (pas 0,3 m, bande 0,05 m)
    p = (u + v) / math.sqrt(2)
    q = (u - v) / math.sqrt(2)
    sp, w = 0.3, 0.025
    fp = np.abs(((p + sp / 2) % sp) - sp / 2)
    fq = np.abs(((q + sp / 2) % sp) - sp / 2)
    ip, iq = np.floor((p + sp / 2) / sp), np.floor((q + sp / 2) / sp)
    bande_p = fp < w
    bande_q = (fq < w) & ~bande_p
    carre = ~bande_p & ~bande_q
    par = ((ip + iq) % 2 == 0)
    Ai = np.where(bande_p, q, np.where(bande_q, p, np.where(par, p, q)))
    Bi = np.where(bande_p, fp, np.where(bande_q, fq, np.where(par, q * 7 % 0.06, p * 7 % 0.06)))
    li = np.where(par, np.floor(q / 0.06), np.floor(p / 0.06))
    idi = np.where(bande_p, 10 + ip * 31, np.where(bande_q, 500 + iq * 17, 900 + ip * 13 + iq * 7 + li * 3))
    ji = (np.abs(fp - w) < 0.0022) | ((np.abs(fq - w) < 0.0022) & (fp > w))
    lame = carre & ((np.where(par, q, p) % 0.06) < 0.0022)
    A = np.where(cadre, A, Ai)
    B = np.where(cadre, B, Bi)
    ident = np.where(cadre, ident, idi).astype(np.int64)
    joint = np.where(cadre, joint, ji | lame).astype(np.float32)
    col = echantillon_bois(A, B * 3.0, ident)
    col = col * (1 - 0.45 * Image_flou(joint)[..., None])
    col = col * np.array([1.02, 0.96, 0.86])[None, None, :] * 1.05
    return sauver(nom, col)


def Image_flou(a, r=1.0):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im).astype(np.float32) / 255


def tex_damier(nom, px=1024):
    """Bâtons rompus en damier (chambre 1) : carrés de 0,5 m à six lames, sens alternés."""
    u, v = np.meshgrid((np.arange(px) + 0.5) / px, (np.arange(px) + 0.5) / px)
    i, j = np.floor(u / 0.5), np.floor(v / 0.5)
    par = (i + j) % 2 == 0
    lu, lv = u % 0.5, v % 0.5
    lw = 0.5 / 6
    A = np.where(par, u, v)
    B = np.where(par, lv % lw, lu % lw)
    k = np.where(par, np.floor(lv / lw), np.floor(lu / lw))
    ident = (i * 97 + j * 41 + k * 7 + 3).astype(np.int64)
    joint = (np.where(par, lv % lw, lu % lw) < 0.002) | (np.minimum(lu, lv) < 0.002)
    col = echantillon_bois(A, B * 3, ident)
    col = col * (1 - 0.45 * Image_flou(joint.astype(np.float32))[..., None])
    col = col * np.array([1.05, 0.95, 0.80])[None, None, :] * 1.08
    return sauver(nom, col)


def tex_rayures(nom, px=512):
    """Papier peint à larges rayures verticales or / beige / gris-taupe (P52-P54) ; 0,5 m par tuile."""
    seq = [(0.075, (0.70, 0.58, 0.37)), (0.010, (0.46, 0.41, 0.34)), (0.040, (0.82, 0.76, 0.62)),
           (0.010, (0.46, 0.41, 0.34)), (0.075, (0.70, 0.58, 0.37)), (0.040, (0.58, 0.53, 0.45))]
    tot = sum(s for s, _ in seq)
    u = (np.arange(px) + 0.5) / px * 0.5
    col = np.zeros((px, 3), np.float32)
    for k in range(px):
        t = u[k] % tot
        acc = 0
        for s, c in seq:
            acc += s
            if t < acc:
                col[k] = c
                break
    img = np.repeat(col[None, :, :], px, axis=0)
    n = bruit(px, 16, 3, 3)
    img = img * (1 + 0.08 * n[:, :, None])
    return sauver(nom, img)


def tex_marbre(nom, px=512, base=(0.90, 0.89, 0.87)):
    n1 = bruit(px, 4, 11, 5)
    n2 = bruit(px, 6, 12, 4)
    yy, xx = np.mgrid[0:px, 0:px] / px
    veine = np.abs(np.sin((xx * 4 + yy * 2 + n1 * 3.0) * math.pi)) ** 12
    col = np.array(base)[None, None, :] * (1 + 0.04 * n2[:, :, None]) * (1 - 0.22 * veine[:, :, None])
    return sauver(nom, col)


def tex_tapis(nom, w, h, champ, motif, bord1, bord2, frange, graine):
    """Tapis d'Orient simplifié : champ à motifs, médaillon, bordures, franges aux petits côtés."""
    px = 1024
    py = int(px * h / w)
    r = np.random.default_rng(graine)
    im = Image.new("RGB", (px, py), tuple(int(c * 255) for c in champ))
    d = ImageDraw.Draw(im)
    fr = int(px * 0.025)
    m = fr + int(px * 0.02)
    b = int(py * 0.10)
    d.rectangle([m, 0, px - m, py], fill=tuple(int(c * 255) for c in bord1))
    d.rectangle([m + b * 0.35, b * 0.35, px - m - b * 0.35, py - b * 0.35], fill=tuple(int(c * 255) for c in bord2))
    d.rectangle([m + b, b, px - m - b, py - b], fill=tuple(int(c * 255) for c in champ))
    # semis de petits motifs dans le champ et la bordure
    for _ in range(900):
        x, y = r.integers(m + b, px - m - b), r.integers(b, py - b)
        s = r.integers(3, 9)
        d.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=tuple(int(c * 255) for c in motif))
    for k in range(60):
        t = k / 60
        x = m + b * 0.6 + t * (px - 2 * m - 1.2 * b)
        for y in (b * 0.6, py - b * 0.6):
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=tuple(int(c * 255) for c in champ))
    cx, cy = px / 2, py / 2
    for k, (sc, c) in enumerate(((0.36, bord1), (0.30, motif), (0.22, bord2), (0.12, bord1))):
        rx, ry = (px - 2 * m) * sc / 2, py * sc * 0.8 / 2
        d.polygon([(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)], fill=tuple(int(v * 255) for v in c))
    for x in range(0, fr):
        pass
    for y in range(0, py, 4):
        d.line([(0, y), (fr, y)], fill=tuple(int(c * 255) for c in frange), width=2)
        d.line([(px - fr, y), (px, y)], fill=tuple(int(c * 255) for c in frange), width=2)
    a = np.asarray(im).astype(np.float32) / 255
    n = bruit(max(px, py), 32, graine, 3)[:py, :px]
    a = a * (1 + 0.12 * n[:, :, None])
    return sauver(nom, a)


def peinture(nom, w, h, scene, graine):
    """Tableau peint procéduralement (référence de sujet et de couleurs, pas une copie de photo)."""
    px = 512
    py = int(px * h / w)
    r = np.random.default_rng(graine)
    yy, xx = np.mgrid[0:py, 0:px].astype(np.float32)
    v, u = yy / py, xx / px
    n = bruit(max(px, py), 6, graine, 4)[:py, :px]
    def rgb(c):
        return np.array(c, np.float32)[None, None, :]
    if scene == "marine":
        ciel = rgb((0.45, 0.50, 0.55)) * (1 - v[:, :, None] * 0.4) + rgb((0.18, 0.18, 0.2)) * (n[:, :, None] + 0.2)
        mer = rgb((0.14, 0.22, 0.26)) + rgb((0.5, 0.55, 0.55)) * np.clip(n * 3 - 0.6, 0, 1)[:, :, None]
        rocher = rgb((0.45, 0.33, 0.18)) * (0.7 + 0.6 * n[:, :, None])
        a = np.where((v > 0.58)[:, :, None], mer, ciel)
        cote = 0.42 + 0.25 * (u ** 1.5) + 0.06 * n
        a = np.where(((u < 0.45) & (v > cote))[:, :, None], rocher, a)
        a = np.where(((u > 0.75) & (v > 0.66 - 0.1 * (u - 0.75) + 0.05 * n))[:, :, None], rocher * 0.8, a)
    elif scene == "nature_morte":
        a = rgb((0.10, 0.12, 0.09)) * (1 + 0.5 * n[:, :, None])
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        d.rectangle([0, int(py * 0.68), px, py], fill=(95, 60, 35))
        for k, c in enumerate([(170, 30, 25), (120, 150, 50), (190, 140, 40), (150, 25, 30), (90, 120, 40)]):
            x, y = 120 + k * 60, int(py * 0.62) - (k % 2) * 20
            d.ellipse([x - 32, y - 32, x + 32, y + 32], fill=c)
        a = np.asarray(im).astype(np.float32) / 255
    elif scene == "eglise":
        a = rgb((0.45, 0.6, 0.8)) * (1 - 0.3 * v[:, :, None]) + 0.1 * n[:, :, None]
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        d.rectangle([0, int(py * 0.7), px, py], fill=(110, 130, 80))
        d.rectangle([150, int(py * 0.42), 360, int(py * 0.78)], fill=(235, 230, 215))
        d.polygon([(140, int(py * 0.42)), (370, int(py * 0.42)), (255, int(py * 0.30))], fill=(170, 80, 60))
        d.rectangle([225, int(py * 0.15), 285, int(py * 0.42)], fill=(235, 230, 215))
        d.polygon([(220, int(py * 0.15)), (290, int(py * 0.15)), (255, int(py * 0.06))], fill=(90, 90, 100))
        a = np.asarray(im).astype(np.float32) / 255
    elif scene in ("portrait", "portrait_femme", "portrait_nuit"):
        fond = {"portrait": (0.12, 0.10, 0.08), "portrait_femme": (0.30, 0.22, 0.14),
                "portrait_nuit": (0.06, 0.08, 0.16)}[scene]
        a = rgb(fond) * (1 + 0.6 * n[:, :, None])
        visage = ((u - 0.5) / 0.17) ** 2 + ((v - 0.36) / 0.22) ** 2 < 1
        corps = ((u - 0.5) / 0.38) ** 2 + ((v - 1.0) / 0.42) ** 2 < 1
        a = np.where(corps[:, :, None], rgb((0.08, 0.07, 0.07)) * (1 + n[:, :, None]), a)
        a = np.where(visage[:, :, None], rgb((0.78, 0.62, 0.50)) * (0.9 + 0.3 * n[:, :, None]), a)
        if scene == "portrait_femme":
            cheveux = (((u - 0.5) / 0.22) ** 2 + ((v - 0.30) / 0.25) ** 2 < 1) & ~visage
            a = np.where(cheveux[:, :, None], rgb((0.25, 0.15, 0.08)), a)
    elif scene == "bouquet":
        a = rgb((0.30, 0.42, 0.62)) * (1 + 0.4 * n[:, :, None])
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        for k in range(40):
            x, y = r.normal(px / 2, px / 7), r.normal(py * 0.4, py / 7)
            s = r.integers(15, 40)
            c = [(120, 70, 160), (90, 50, 140), (230, 200, 80), (200, 210, 240)][k % 4]
            d.ellipse([x - s, y - s, x + s, y + s], fill=c)
        d.polygon([(px * 0.42, py * 0.75), (px * 0.58, py * 0.75), (px * 0.55, py * 0.95), (px * 0.45, py * 0.95)],
                  fill=(60, 50, 90))
        a = np.asarray(im).astype(np.float32) / 255
    elif scene == "gravure":
        a = rgb((0.88, 0.84, 0.74)) * (1 + 0.05 * n[:, :, None])
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        d.rectangle([60, 60, px - 60, py - 60], outline=(120, 100, 80), width=3)
        d.rectangle([140, int(py * 0.40), px - 140, int(py * 0.75)], outline=(70, 55, 45), width=3)
        for k in range(6):
            x = 170 + k * 35
            d.rectangle([x, int(py * 0.48), x + 18, int(py * 0.62)], outline=(70, 55, 45), width=2)
        d.polygon([(130, int(py * 0.40)), (px - 130, int(py * 0.40)), (px / 2, int(py * 0.28))], outline=(70, 55, 45))
        a = np.asarray(im).astype(np.float32) / 255
    else:  # paysage (trumeau)
        a = rgb((0.55, 0.62, 0.55)) * (1 - 0.3 * v[:, :, None]) + 0.15 * n[:, :, None]
        a = np.where((v > 0.6 + 0.1 * n)[:, :, None], rgb((0.35, 0.40, 0.22)), a)
    return sauver(nom, a)


def tex_jouy(nom, px=256):
    im = Image.new("RGB", (px, px), (236, 230, 220))
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(5)
    for _ in range(40):
        pts = [(float(r.integers(0, px)), float(r.integers(0, px)))]
        for k in range(5):
            pts.append((pts[-1][0] + r.normal(0, 14), pts[-1][1] + r.normal(0, 14)))
        d.line(pts, fill=(170, 40, 45), width=2)
    return sauver(nom, np.asarray(im).astype(np.float32) / 255)


def tex_echiquier(nom, px=256):
    yy, xx = np.mgrid[0:px, 0:px]
    c = ((xx * 8 // px + yy * 8 // px) % 2 == 0)
    a = np.where(c[:, :, None], np.array([0.85, 0.75, 0.55]), np.array([0.25, 0.14, 0.07]))
    a[:12], a[-12:], a[:, :12], a[:, -12:] = 0.2, 0.2, 0.2, 0.2
    return sauver(nom, a)


def tex_clavier(nom, w=1024, h=96):
    a = np.ones((h, w, 3), np.float32) * 0.93
    nb = 52
    for k in range(nb + 1):
        x = int(k * w / nb)
        a[:, max(0, x - 1):x + 1] = 0.4
    for k in range(nb):
        if k % 7 in (0, 1, 3, 4, 5):
            x = int((k + 1) * w / nb)
            a[:int(h * 0.6), x - 5:x + 5] = 0.04
    return sauver(nom, a)


def tex_enduit(nom, teinte):
    wp = os.path.join(PH, "polyhaven-white_plaster_rough_01", "white_plaster_rough_01_diff_1k.jpg")
    L = lum(charger(wp))
    r = (L / L.mean())[:, :, None]
    return sauver(nom, np.array(teinte)[None, None, :] * (1 + (r - 1) * 0.15))


log("textures…")
TX = {
    "creme": tex_enduit("peinture_creme", (0.84, 0.80, 0.70)),
    "blanc_casse": tex_enduit("peinture_blanc_casse", (0.86, 0.85, 0.80)),
    "versailles": tex_versailles("parquet_versailles"),
    "damier": tex_damier("parquet_damier"),
    "rayures": tex_rayures("papier_rayures"),
    "marbre": tex_marbre("marbre_blanc"),
    "noyer": tex_bois("noyer", (0.30, 0.17, 0.085)),
    "noyer_rouge": tex_bois("noyer_rouge", (0.33, 0.14, 0.07)),
    "acajou": tex_bois("acajou", (0.26, 0.09, 0.05)),
    "merisier": tex_bois("merisier", (0.66, 0.40, 0.20), contraste=0.9),
    "bois_noir": tex_bois("bois_noir", (0.05, 0.045, 0.04), contraste=0.6),
    "bois_sombre": tex_bois("bois_sombre", (0.15, 0.085, 0.045)),
    "bois_clair": tex_bois("bois_clair", (0.68, 0.52, 0.33), contraste=0.8),
    "tapis_1": tex_tapis("tapis_chambre_1", 2.5, 1.8, (0.48, 0.08, 0.07), (0.20, 0.12, 0.25), (0.12, 0.14, 0.30),
                         (0.80, 0.70, 0.52), (0.30, 0.38, 0.60), 21),
    "tapis_3": tex_tapis("tapis_chambre_3", 3.0, 2.5, (0.66, 0.70, 0.58), (0.80, 0.55, 0.56), (0.76, 0.50, 0.52),
                         (0.86, 0.82, 0.70), (0.88, 0.86, 0.80), 23),
    "jouy": tex_jouy("toile_de_jouy"),
    "echiquier": tex_echiquier("echiquier"),
    "clavier": tex_clavier("clavier"),
}
TABLEAUX = {}
for nom, w, h, sc in (("marine", 1.9, 1.3, "marine"),
                      ("nature_morte", 0.55, 0.4, "nature_morte"), ("eglise", 0.5, 0.65, "eglise"),
                      ("portrait_nuit", 0.35, 0.5, "portrait_nuit"), ("bouquet", 0.5, 0.6, "bouquet"),
                      ("portrait_femme", 0.4, 0.55, "portrait_femme"), ("gravure", 0.35, 0.45, "gravure"),
                      ("paysage", 0.45, 0.6, "paysage")):
    TABLEAUX[nom] = peinture("tableau_" + nom, w, h, sc, sum(map(ord, nom)))
TABLEAUX["marche"] = os.path.join(RACINE, "assets", "oeuvres-releve-2026-11-19",
                                  "tableau_marche_chambre_3_toile.png")

# ----------------------------------------------------------------------------------------------
# Matériaux
# ----------------------------------------------------------------------------------------------
MATS, UVS = {}, {}


def materiau(nom, couleur=(0.8, 0.8, 0.8), rugosite=0.5, metal=0.0, tex=None, uv=1.0, emission=None,
             deux_faces=False, alpha=None):
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
        ti = nt.nodes.new("ShaderNodeTexImage")
        ti.image = bpy.data.images.load(tex, check_existing=True)
        nt.links.new(ti.outputs["Color"], p.inputs["Base Color"])
    m.use_backface_culling = not deux_faces
    m.diffuse_color = (*couleur, 1)
    MATS[nom] = m
    UVS[m.name] = uv
    return m


M = {
    "parquet_v": materiau("parquet_versailles", tex=TX["versailles"], uv=1.0, rugosite=0.35),
    "parquet_d": materiau("parquet_damier", tex=TX["damier"], uv=1.0, rugosite=0.35),
    "rayures": materiau("papier_rayures", tex=TX["rayures"], uv=0.5, rugosite=0.8),
    "creme": materiau("peinture_creme", tex=TX["creme"], uv=1.5, rugosite=0.85),
    "blanc_casse": materiau("peinture_blanc_casse", tex=TX["blanc_casse"], uv=1.5, rugosite=0.85),
    "stuc": materiau("stuc", (0.90, 0.89, 0.86), 0.8),
    "laque": materiau("laque_blanche", (0.86, 0.85, 0.81), 0.35),
    "vert_eau": materiau("vert_eau", (0.56, 0.68, 0.62), 0.45),
    "ombre": materiau("enduit_ombre", (0.62, 0.60, 0.55), 0.9),
    "marbre": materiau("marbre_blanc", tex=TX["marbre"], uv=0.8, rugosite=0.2),
    "fonte": materiau("fonte_noire", (0.025, 0.025, 0.025), 0.6, 0.3),
    "laiton": materiau("laiton", (0.78, 0.58, 0.25), 0.3, 1.0),
    "bronze": materiau("bronze_dore", (0.70, 0.50, 0.20), 0.35, 1.0),
    "fer": materiau("fer_noir", (0.03, 0.03, 0.03), 0.5, 0.7),
    "bougie": materiau("bougie", (0.95, 0.93, 0.88), 0.5),
    "flamme": materiau("ampoule", (1.0, 0.85, 0.6), 0.3, emission=((1.0, 0.78, 0.45), 8.0)),
    "abat_jour": materiau("abat_jour_creme", (0.90, 0.84, 0.70), 0.8, emission=((1.0, 0.85, 0.6), 0.6)),
    "abat_blanc": materiau("abat_jour_blanc", (0.93, 0.92, 0.88), 0.8, emission=((1.0, 0.9, 0.7), 0.4)),
    "rideau_rose": materiau("rideau_vieux_rose", (0.56, 0.34, 0.34), 0.9, deux_faces=True),
    "rideau_taupe": materiau("rideau_lin_taupe", (0.46, 0.40, 0.32), 0.9, deux_faces=True),
    "rideau_ecru": materiau("rideau_lin_ecru", (0.82, 0.77, 0.66), 0.9, deux_faces=True),
    "nappe": materiau("nappe_blanche", (0.88, 0.87, 0.84), 0.85),
    "velours": materiau("velours_bordeaux", (0.33, 0.03, 0.06), 0.9),
    "fleuri": materiau("tissu_fleuri_creme", (0.85, 0.80, 0.70), 0.85),
    "bleu": materiau("plastique_bleu", (0.22, 0.45, 0.85), 0.35),
    "rouge": materiau("plastique_rouge", (0.75, 0.06, 0.05), 0.35),
    "jaune": materiau("plastique_jaune", (0.92, 0.75, 0.10), 0.35),
    "noir": materiau("noir_mat", (0.02, 0.02, 0.02), 0.5),
    "rotin": materiau("rotin", (0.62, 0.46, 0.27), 0.8),
    "cuir": materiau("cuir_brun", (0.25, 0.12, 0.05), 0.55),
    "alu": materiau("aluminium", (0.80, 0.80, 0.82), 0.3, 1.0),
    "ecran": materiau("ecran", (0.02, 0.02, 0.025), 0.1),
    "verre": materiau("verre_vase", (0.80, 0.86, 0.86), 0.05, alpha=0.35, deux_faces=True),
    "verre_bleu": materiau("verre_bleu", (0.15, 0.25, 0.65), 0.1, alpha=0.7),
    "ceramique": materiau("ceramique_bleu_blanc", (0.70, 0.76, 0.88), 0.25),
    "sechees": materiau("fleurs_sechees", (0.72, 0.63, 0.48), 0.9),
    "jouy": materiau("toile_de_jouy", tex=TX["jouy"], uv=0.4, rugosite=0.9),
    "linge": materiau("linge_blanc", (0.90, 0.90, 0.88), 0.9),
    "echiquier": materiau("echiquier", tex=TX["echiquier"], uv=1.0, rugosite=0.4),
    "clavier": materiau("clavier", tex=TX["clavier"], uv=1.0, rugosite=0.3),
    "plante": materiau("feuillage", (0.12, 0.30, 0.10), 0.7, deux_faces=True),
    "or_cadre": materiau("cadre_dore", (0.75, 0.55, 0.22), 0.35, 1.0),
    "cadre_sombre": materiau("cadre_sombre", (0.10, 0.06, 0.035), 0.5),
    "chrome": materiau("chrome", (0.9, 0.9, 0.9), 0.1, 1.0),
}
for k in ("noyer", "noyer_rouge", "acajou", "merisier", "bois_noir", "bois_sombre", "bois_clair"):
    M[k] = materiau(k, tex=TX[k], uv=0.6, rugosite=0.45)
M["tapis_1"] = materiau("tapis_chambre_1", tex=TX["tapis_1"], rugosite=0.95)
M["tapis_3"] = materiau("tapis_chambre_3", tex=TX["tapis_3"], rugosite=0.95)
for k, chemin in TABLEAUX.items():
    M["toile_" + k] = materiau("toile_" + k, tex=chemin, rugosite=0.6)
LIVRES = [materiau("livre_%d" % i, c, 0.7) for i, c in
          enumerate(((0.35, 0.08, 0.06), (0.10, 0.18, 0.30), (0.12, 0.25, 0.14), (0.55, 0.45, 0.30), (0.08, 0.08, 0.08)))]


# ----------------------------------------------------------------------------------------------
# Constructeur de maillages (repris de coque.py, complété : tour, tubes, UV explicites)
# ----------------------------------------------------------------------------------------------
def ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
            for i in range(len(poly)))
    return list(poly) if a > 0 else list(reversed(poly))


class Bld:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []
        self.uvx = {}

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
        if uv:
            self.uvx[f] = uv
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

    def boite(self, x0, y0, z0, x1, y1, z1, m, mhaut=None):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        self.solide([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, m, mhaut)

    def prisme(self, profil, axe, a0, a1, m):
        """Profil [(s, z)] dans un plan vertical ; axe "x" : s = x, épaisseur en y de a0 à a1 ; "y" : s = y."""
        profil = ccw(profil)
        f = (lambda s, z, a: (s, a, z)) if axe == "x" else (lambda s, z, a: (a, s, z))
        b = [self.v(f(s, z, a0)) for s, z in profil]
        h = [self.v(f(s, z, a1)) for s, z in profil]
        n = len(b)
        for i in range(n):
            j = (i + 1) % n
            self.face([b[i], b[j], h[j], h[i]], m)
        self.face(list(reversed(b)), m)
        self.face(h, m)

    def tour(self, profil, m, n=16, c=(0, 0, 0), plis=0.0, sx=1.0):
        """Solide de révolution : profil [(r, z)] de bas en haut, autour de l'axe vertical passant par c."""
        anneaux = []
        for r, z in profil:
            r = max(r, 1e-4)
            anneaux.append([self.v((c[0] + r * (1 + (plis if k % 2 else -plis)) * math.cos(2 * math.pi * k / n) * sx,
                                    c[1] + r * (1 + (plis if k % 2 else -plis)) * math.sin(2 * math.pi * k / n),
                                    c[2] + z)) for k in range(n)])
        for a, b in zip(anneaux, anneaux[1:]):
            for k in range(n):
                kk = (k + 1) % n
                self.face([a[k], a[kk], b[kk], b[k]], m)
        self.face(list(reversed(anneaux[0])), m)
        self.face(anneaux[-1], m)

    def tube(self, pts, r, m, n=6, bouts=True):
        pts = [Vector(p) for p in pts]
        cercles = []
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            u = t.cross(ref).normalized()
            w = t.cross(u).normalized()
            rr = r(i) if callable(r) else r
            cercles.append([self.v(p + rr * (math.cos(2 * math.pi * k / n) * u + math.sin(2 * math.pi * k / n) * w))
                            for k in range(n)])
        for a, b in zip(cercles, cercles[1:]):
            for k in range(n):
                kk = (k + 1) % n
                self.face([a[k], a[kk], b[kk], b[k]], m)
        if bouts:
            self.face(list(reversed(cercles[0])), m)
            self.face(cercles[-1], m)

    def quad_uv(self, pts, m, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
        self.face([self.v(p) for p in pts], m, uv=list(uv))

    def objet(self, nom, col=None, recalc=True):
        bm = self.bm
        bm.normal_update()
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            if f in self.uvx:
                for lp, uv in zip(f.loops, self.uvx[f]):
                    lp[uvl].uv = uv
                continue
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            s = UVS.get(self.mats[f.material_index].name, 1.0) if self.mats else 1.0
            for lp in f.loops:
                co = lp.vert.co
                if ax == 2:
                    uv = (co.x / s, co.y / s)
                elif ax == 0:
                    uv = (co.y / s * (1 if n.x > 0 else -1), co.z / s)
                else:
                    uv = (co.x / s * (-1 if n.y > 0 else 1), co.z / s)
                lp[uvl].uv = uv
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f not in self.uvx])
        me = bpy.data.meshes.new(nom)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(nom, me)
        (col or COL).objects.link(ob)
        return ob


def rot_face(n):
    """Rotation Z qui tourne la face avant locale (−Y) vers la normale n du mur (vers l'intérieur)."""
    return math.atan2(n[0], -n[1])


def poser(ob, x, y, z=ZP, rot=0.0):
    ob.location = (x, y, z)
    ob.rotation_euler = (0, 0, rot)
    return ob


def instance(nom, src, x, y, z=ZP, rot=0.0, echelle=1.0):
    ob = bpy.data.objects.new(nom, src.data if hasattr(src, "data") else src)
    COL.objects.link(ob)
    ob.scale = (echelle,) * 3
    return poser(ob, x, y, z, rot)


# ----------------------------------------------------------------------------------------------
# Murs des pièces et ouvertures
# ----------------------------------------------------------------------------------------------
# murs : côté → (orientation, coordonnée constante du nu, normale vers l'intérieur)
MUR = {
    "chambre_1": {"N": ("EO", 4.10, (0, 1)), "S": ("EO", 8.85, (0, -1)), "O": ("NS", 11.10, (1, 0)),
                  "E": ("NS", 17.40, (-1, 0))},
    "chambre_2": {"N": ("EO", 4.15, (0, 1)), "S": ("EO", 8.75, (0, -1)), "O": ("NS", -3.70, (1, 0)),
                  "E": ("NS", 3.70, (-1, 0))},
    "chambre_3": {"N": ("EO", 1.10, (0, 1)), "S": ("EO", 8.15, (0, -1)), "O": ("NS", -10.50, (1, 0)),
                  "E": ("NS", -4.30, (-1, 0))},
}


def pt(pid, cote, s, d):
    """Point à l'abscisse s le long du mur, à la distance d du nu vers l'intérieur ; + rotation."""
    o, c, n = MUR[pid][cote]
    if o == "EO":
        return s, c + n[1] * d, rot_face(n)
    return c + n[0] * d, s, rot_face(n)


def aretes(pid):
    poly = ccw([tuple(p) for p in PIECES[pid]["polygone_interieur"]])
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        u = (q[0] - p[0], q[1] - p[1])
        L = math.hypot(*u)
        n = (-u[1] / L, u[0] / L)
        if abs(u[0]) < 1e-6:
            out.append(dict(o="NS", c=p[0], a=min(p[1], q[1]), b=max(p[1], q[1]), n=n))
        else:
            out.append(dict(o="EO", c=p[1], a=min(p[0], q[0]), b=max(p[0], q[0]), n=n))
    return out


FENETRES = {   # (orientation, nu intérieur, axe, largeur, bas, haut) — bati.py / D-025
    "chambre_1": [("EO", 8.85, 14.4, 1.35, 5.50, 8.60), ("NS", 17.40, 6.9, 1.35, 5.50, 8.60)],
    "chambre_2": [("EO", 8.75, -2.73, 1.10, 5.50, 8.60), ("EO", 8.75, 0.0, 1.40, 5.35, 8.60),
                  ("EO", 8.75, 2.73, 1.10, 5.50, 8.60)],
    "chambre_3": [("EO", 8.15, -8.85, 1.35, 5.50, 8.60), ("EO", 8.15, -5.25, 1.35, 5.50, 8.60)],
}


def ouvertures(pid):
    """Ouvertures sur les nus de la pièce : portes de coque.json (face côté pièce) et fenêtres de façade."""
    ar = aretes(pid)
    out = []
    for po in PIECES[pid]["portes"]:
        cx, cy, cz = po["centre"]
        if "x =" in po["mur"]:
            o, c0, s = "NS", cx, cy
        else:
            o, c0, s = "EO", cy, cx
        e = po["epaisseur_mur"] / 2
        w = po["largeur"] / 2
        for a in ar:
            if a["o"] == o and min(abs(a["c"] - (c0 - e)), abs(a["c"] - (c0 + e))) < 0.03 and a["a"] < s < a["b"]:
                out.append(dict(o=o, c=a["c"], n=a["n"], s0=s - w, s1=s + w, zb=cz, zh=cz + po["hauteur"],
                                type="porte", nom=po["nom"]))
                break
    for o, c, s, w, zb, zh in FENETRES[pid]:
        a = next(a for a in ar if a["o"] == o and abs(a["c"] - c) < 0.03 and a["a"] < s < a["b"])
        out.append(dict(o=o, c=c, n=a["n"], s0=s - w / 2, s1=s + w / 2, zb=zb, zh=zh, type="fenetre", nom=""))
    return out


OUV = {pid: ouvertures(pid) for pid in CH}
for pid in CH:
    log(pid, "ouvertures :", [(o["type"], o["o"], round(o["c"], 2), round(o["s0"], 2), round(o["s1"], 2)) for o in OUV[pid]])


def boite_mur(b, o, c, n, s0, s1, d0, d1, z0, z1, m):
    if o == "EO":
        b.boite(s0, c + n[1] * d0, z0, s1, c + n[1] * d1, z1, m)
    else:
        b.boite(c + n[0] * d0, s0, z0, c + n[0] * d1, s1, z1, m)


def plinthes(pid, h, ep, m):
    b = Bld()
    for a in aretes(pid):
        trous = sorted((o["s0"], o["s1"]) for o in OUV[pid]
                       if o["o"] == a["o"] and abs(o["c"] - a["c"]) < 0.03 and o["zb"] < Z0 + h)
        s = a["a"] - ep
        for t0, t1 in trous + [(a["b"] + ep, a["b"] + ep)]:
            if t0 - s > 0.02:
                boite_mur(b, a["o"], a["c"], a["n"], s, t0, -0.01, ep, ZP - 0.005, ZP + h, m)
            s = t1
        # chaise d'appui du chambranle : la plinthe bute sur le chambranle
    return b.objet(pid + "_plinthes")


def panneaux_muraux(pid, z0, z1, m, nom, d=0.004):
    """Revêtement mural (papier peint) découpé autour des ouvertures."""
    b = Bld()
    for a in aretes(pid):
        trous = [o for o in OUV[pid] if o["o"] == a["o"] and abs(o["c"] - a["c"]) < 0.03]
        cuts = sorted({a["a"], a["b"]} | {min(max(t["s0"], a["a"]), a["b"]) for t in trous}
                      | {min(max(t["s1"], a["a"]), a["b"]) for t in trous})
        for s0, s1 in zip(cuts, cuts[1:]):
            if s1 - s0 < 1e-3:
                continue
            sm = (s0 + s1) / 2
            zs = [(z0, z1)]
            for t in trous:
                if t["s0"] <= sm <= t["s1"]:
                    nz = []
                    for za, zb in zs:
                        if t["zh"] <= za or t["zb"] >= zb:
                            nz.append((za, zb))
                            continue
                        if t["zb"] > za:
                            nz.append((za, t["zb"]))
                        if t["zh"] < zb:
                            nz.append((t["zh"], zb))
                    zs = nz
            for za, zb in zs:
                if zb - za > 0.01:
                    boite_mur(b, a["o"], a["c"], a["n"], s0, s1, 0.0, d, za, zb, m)
    return b.objet(nom)


def chambranles(pid, m, larg=0.10, saillie=0.025, fenetres=True):
    b = Bld()
    for o in OUV[pid]:
        if o["type"] == "fenetre" and not fenetres:
            continue
        zb = ZP - 0.005 if o["zb"] < Z0 + 0.05 else o["zb"] - 0.06
        for s0, s1 in ((o["s0"] - larg, o["s0"]), (o["s1"], o["s1"] + larg)):
            boite_mur(b, o["o"], o["c"], o["n"], s0, s1, -0.005, saillie, zb, o["zh"] + larg, m)
            boite_mur(b, o["o"], o["c"], o["n"], s0 + 0.015, s1 - 0.015, saillie, saillie + 0.012, zb + 0.2,
                      o["zh"] + larg - 0.015, m)
        boite_mur(b, o["o"], o["c"], o["n"], o["s0"], o["s1"], -0.005, saillie, o["zh"], o["zh"] + larg, m)
        if o["type"] == "fenetre" and o["zb"] > Z0 + 0.05:
            # appui intérieur
            boite_mur(b, o["o"], o["c"], o["n"], o["s0"] - larg, o["s1"] + larg, -0.005, 0.05, o["zb"] - 0.06,
                      o["zb"], m)
    return b.objet(pid + "_chambranles")


def inset(poly, d):
    """Polygone (ccw) décalé de d vers l'intérieur."""
    n = len(poly)
    lignes = []
    for i in range(n):
        p, q = Vector(poly[i]), Vector(poly[(i + 1) % n])
        u = (q - p).normalized()
        nn = Vector((-u.y, u.x))
        lignes.append((p + nn * d, u))
    out = []
    for i in range(n):
        p1, u1 = lignes[i - 1]
        p2, u2 = lignes[i]
        den = u1.x * u2.y - u1.y * u2.x
        if abs(den) < 1e-9:
            out.append(tuple(p2))
            continue
        t = ((p2.x - p1.x) * u2.y - (p2.y - p1.y) * u2.x) / den
        out.append(tuple(p1 + u1 * t))
    return out


def anneau(b, poly, d0, d1, z0, z1, m):
    o, i = inset(poly, d0), inset(poly, d1)
    n = len(poly)
    o0 = [b.v((x, y, z0)) for x, y in o]
    o1 = [b.v((x, y, z1)) for x, y in o]
    i0 = [b.v((x, y, z0)) for x, y in i]
    i1 = [b.v((x, y, z1)) for x, y in i]
    for k in range(n):
        j = (k + 1) % n
        b.face([o0[k], i0[k], i0[j], o0[j]], m)
        b.face([o1[k], o1[j], i1[j], i1[k]], m)
        b.face([i0[k], i1[k], i1[j], i0[j]], m)
        b.face([o0[k], o0[j], o1[j], o1[k]], m)


def corniche(pid, profil, filet=None):
    """Corniche en gradins (profil [(descente haut, descente bas, saillie)] depuis le plafond)."""
    poly = ccw([tuple(p) for p in PIECES[pid]["polygone_interieur"]])
    b = Bld()
    zt = ZC - 0.01
    for h0, h1, s in profil:
        anneau(b, poly, -0.005, s, zt - h1, zt - h0, M["stuc"])
    if filet:
        d, w = filet
        anneau(b, poly, d, d + w, zt - 0.018, zt + 0.005, M["stuc"])
    return b.objet(pid + "_corniche")


def parquet(pid, m):
    b = Bld()
    b.solide([tuple(p) for p in PIECES[pid]["polygone_interieur"]], Z0 + 0.001, ZP, m)
    return b.objet(pid + "_parquet")


def rosace(nom, x, y, r, m=None, feuilles=0):
    b = Bld()
    m = m or M["stuc"]
    prof = [(r, 0.0), (r, -0.015), (r * 0.85, -0.025), (r * 0.7, -0.03), (r * 0.55, -0.05), (r * 0.35, -0.055),
            (r * 0.2, -0.08), (r * 0.08, -0.09), (0.0, -0.095)]
    b.tour([(rr, z) for rr, z in reversed(prof)], m, n=24, c=(x, y, ZC - 0.002))
    for k in range(feuilles):
        a = 2 * math.pi * k / feuilles
        cx, cy = x + math.cos(a) * r * 0.72, y + math.sin(a) * r * 0.72
        b.tour([(0.0, -0.045), (r * 0.12, -0.04), (r * 0.10, -0.015), (0.0, 0.0)], m, n=8, c=(cx, cy, ZC - 0.002),
               sx=2.2)
    return b.objet(nom)


# ----------------------------------------------------------------------------------------------
# Éléments génériques modélisés
# ----------------------------------------------------------------------------------------------
def lustre(pid, x, y, n_bras, R, mat, haut=1.0, chaine=0.35, nom="lustre", rosace_r=0.0):
    """Lustre à bras en S et bougies électriques ; lumière ponctuelle au centre des bougies."""
    b = Bld()
    ztop = ZC - 0.01
    zc = ztop - chaine - haut * 0.55        # niveau des bobèches
    b.tube([(x, y, ztop), (x, y, ztop - chaine)], 0.008, mat, n=6)
    # fût central balustre
    zf = ztop - chaine
    prof = [(0.0, -haut * 0.95), (0.03, -haut * 0.93), (0.05, -haut * 0.85), (0.02, -haut * 0.78),
            (0.035, -haut * 0.62), (0.07, -haut * 0.56), (0.04, -haut * 0.50), (0.02, -haut * 0.35),
            (0.04, -haut * 0.20), (0.015, -haut * 0.05), (0.025, 0.0)]
    b.tour(prof, mat, n=10, c=(x, y, zf))
    for k in range(n_bras):
        a = 2 * math.pi * k / n_bras
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for i in range(9):
            t = i / 8
            r = 0.04 + (R - 0.04) * t
            z = zf - haut * 0.62 - 0.10 * math.sin(math.pi * t) + 0.12 * t ** 2
            pts.append((x + ca * r, y + sa * r, z))
        b.tube(pts, 0.009, mat, n=6)
        ex, ey, ez = pts[-1]
        b.tour([(0.0, 0.0), (0.035, 0.015), (0.04, 0.03), (0.012, 0.03)], mat, n=8, c=(ex, ey, ez))
        b.tour([(0.012, 0.03), (0.012, 0.12)], M["bougie"], n=6, c=(ex, ey, ez))
        b.tour([(0.0, 0.12), (0.014, 0.135), (0.012, 0.16), (0.0, 0.175)], M["flamme"], n=6, c=(ex, ey, ez))
        # volute décorative
        b.tube([(x + ca * 0.05, y + sa * 0.05, zf - haut * 0.3), (x + ca * R * 0.4, y + sa * R * 0.4, zf - haut * 0.45),
                (x + ca * R * 0.35, y + sa * R * 0.35, zf - haut * 0.6)], 0.006, mat, n=5)
    ob = b.objet(pid + "_" + nom)
    zl = zf - haut * 0.62 + 0.15
    li = bpy.data.lights.new("lumiere_%s_lustre" % pid, "POINT")
    li.energy = 160
    li.color = (1.0, 0.82, 0.6)
    li.shadow_soft_size = 0.2
    lo = bpy.data.objects.new("lumiere_%s_lustre" % pid, li)
    lo.location = (x, y, zl)
    COL.objects.link(lo)
    LUMIERES.append(lo.name)
    if rosace_r:
        rosace(pid + "_rosace", x, y, rosace_r, feuilles=12 if rosace_r > 0.6 else 0)
    return ob


LUMIERES = []


def tableau(nom, pid, cote, s, zc, w, h, cadre, toile, ep=0.045, prof=0.05):
    b = Bld()
    x0, x1, z0, z1 = -w / 2, w / 2, -h / 2, h / 2
    for (a0, a1, c0, c1) in ((x0 - ep, x1 + ep, z1, z1 + ep), (x0 - ep, x1 + ep, z0 - ep, z0),
                             (x0 - ep, x0, z0, z1), (x1, x1 + ep, z0, z1)):
        b.boite(a0, -prof, c0, a1, 0, c1, M[cadre])
        b.boite(a0 + ep * 0.3, -prof - 0.012, c0 + (ep * 0.3 if c0 < z0 or c1 > z1 else 0), a1 - ep * 0.3, -prof,
                c1 - (ep * 0.3 if c0 < z0 or c1 > z1 else 0), M[cadre])
    b.quad_uv([(x0, -prof * 0.5, z0), (x1, -prof * 0.5, z0), (x1, -prof * 0.5, z1), (x0, -prof * 0.5, z1)],
              M["toile_" + toile])
    b.boite(x0, -prof * 0.45, z0, x1, -0.005, z1, M["cadre_sombre"])
    ob = b.objet(pid + "_" + nom)
    x, y, r = pt(pid, cote, s, 0.0)
    return poser(ob, x, y, zc, r)


def rideaux(pid, o, mat, tringle_mat, embrasse=False, deb=(0.45, 0.45), d=0.13):
    """Paire de rideaux plissés sur tringle de part et d'autre d'une baie."""
    b = Bld()
    zt = o["zh"] + 0.28
    zt = min(zt, ZC - 0.35)
    s0, s1 = o["s0"] - deb[0], o["s1"] + deb[1]

    def P(s, dd, z):
        if o["o"] == "EO":
            return (s, o["c"] + o["n"][1] * dd, z)
        return (o["c"] + o["n"][0] * dd, s, z)
    b.tube([P(s0 - 0.08, d + 0.02, zt + 0.06), P(s1 + 0.08, d + 0.02, zt + 0.06)], 0.014, tringle_mat, n=8)
    for s in (s0 - 0.08, s1 + 0.08):
        b.tube([P(s, d + 0.02, zt + 0.06), P(s, -0.01, zt + 0.06)], 0.008, tringle_mat, n=6)
        b.tour([(0.0, -0.035), (0.03, 0.0), (0.0, 0.035)], tringle_mat, n=8, c=P(s + (-0.03 if s < s0 else 0.03), d + 0.02, zt + 0.06))
    larg = 0.64
    for cote in (-1, 1):
        ext = s0 if cote < 0 else s1
        inn = ext - cote * larg
        rangs = [(zt, 1.0)] + ([(Z0 + 1.05, 0.38)] if embrasse else []) + [(ZP + 0.01, 0.62 if embrasse else 1.0)]
        ns = 22
        grille = []
        for z, sc in rangs:
            ligne = []
            for k in range(ns + 1):
                t = k / ns
                s = ext + (inn - ext) * t * sc
                amp = 0.035 / max(sc, 0.4)
                dd = d + amp * math.sin(2 * math.pi * t * 5.5)
                ligne.append(b.v(P(s, dd, z)))
            grille.append(ligne)
        for la, lb in zip(grille, grille[1:]):
            for k in range(ns):
                b.face([la[k], la[k + 1], lb[k + 1], lb[k]], mat)
        if embrasse:
            ze = Z0 + 1.05
            sm = ext + (inn - ext) * 0.19
            b.tube([P(ext, 0.0, ze), P(sm, d + 0.05, ze)], 0.01, tringle_mat, n=5)
    return b.objet(pid + "_rideaux_%s_%.1f" % (o["o"], (o["s0"] + o["s1"]) / 2), recalc=False)


def radiateur(nom, pid, cote, s, w, h=0.8, z0=0.12):
    b = Bld()
    n = max(4, int(w / 0.06))
    for k in range(n):
        x = -w / 2 + (k + 0.5) * w / n
        b.boite(x - 0.022, -0.11, z0, x + 0.022, -0.03, z0 + h, M["laque"])
    b.boite(-w / 2, -0.09, z0 + 0.05, w / 2, -0.05, z0 + 0.09, M["laque"])
    b.boite(-w / 2, -0.09, z0 + h - 0.09, w / 2, -0.05, z0 + h - 0.05, M["laque"])
    for sx in (-w / 2 + 0.05, w / 2 - 0.05):
        b.boite(sx - 0.015, -0.09, 0, sx + 0.015, -0.06, z0, M["laque"])
    ob = b.objet(pid + "_" + nom)
    x, y, r = pt(pid, cote, s, 0.0)
    return poser(ob, x, y, ZP, r)


def lampe(nom, socle, abat, h_pied, r_haut, r_bas, h_abat, plis=0.0, mat_abat=None, r_pied=0.07, tige=False):
    b = Bld()
    if tige:      # lampadaire : socle rond et tige fine
        prof = [(0.0, 0.0), (r_pied, 0.0), (r_pied, 0.02), (r_pied * 0.6, 0.05), (0.03, 0.08), (0.012, 0.12),
                (0.012, h_pied * 0.5), (0.02, h_pied * 0.52), (0.011, h_pied * 0.55), (0.009, h_pied + 0.05),
                (0.0, h_pied + 0.06)]
    else:
        prof = [(0.0, 0.0), (r_pied, 0.0), (r_pied, 0.025), (r_pied * 0.5, 0.05), (r_pied * 0.9, h_pied * 0.35),
                (r_pied * 0.4, h_pied * 0.75), (0.012, h_pied * 0.85), (0.008, h_pied + 0.05), (0.0, h_pied + 0.06)]
    b.tour(prof, M[socle], n=14)
    b.tour([(r_bas, h_pied - 0.02), (r_haut, h_pied - 0.02 + h_abat), (r_haut - 0.005, h_pied - 0.02 + h_abat),
            (r_bas - 0.005, h_pied - 0.02)], mat_abat or M[abat], n=24, plis=plis)
    return b.objet(nom)


def porte_decor(nom, pid, cote, s, w, h, vantaux=1, filets=False):
    """Porte condamnée (décor) plaquée sur le mur, avec chambranle : ne s'ouvre pas, vers une pièce non vue."""
    b = Bld()
    L = M["laque"]
    for x0, x1 in ((-w / 2 - 0.1, -w / 2), (w / 2, w / 2 + 0.1)):
        b.boite(x0, -0.03, 0, x1, 0.0, h + 0.1, L)
    b.boite(-w / 2 - 0.1, -0.03, h, w / 2 + 0.1, 0.0, h + 0.1, L)
    b.boite(-w / 2, -0.012, 0, w / 2, 0.0, h, M["ombre"])
    lv = w / vantaux
    for k in range(vantaux):
        x0 = -w / 2 + k * lv
        b.boite(x0 + 0.005, -0.04, 0.005, x0 + lv - 0.005, -0.012, h - 0.005, L)
        for z0, z1 in ((0.15, h * 0.38), (h * 0.44, h - 0.15)):
            b.boite(x0 + 0.09, -0.052, z0, x0 + lv - 0.09, -0.04, z1, L)
            if filets:
                for (a0, a1, c0, c1) in ((x0 + 0.11, x0 + lv - 0.11, z0 + 0.02, z0 + 0.035),
                                         (x0 + 0.11, x0 + lv - 0.11, z1 - 0.035, z1 - 0.02),
                                         (x0 + 0.11, x0 + 0.125, z0 + 0.02, z1 - 0.02),
                                         (x0 + lv - 0.125, x0 + lv - 0.11, z0 + 0.02, z1 - 0.02)):
                    b.boite(a0, -0.056, c0, a1, -0.051, c1, M["vert_eau"])
        xp = x0 + (lv - 0.06 if k == 0 else 0.06)
        b.tour([(0.0, 0.0), (0.025, 0.0), (0.02, 0.06), (0.0, 0.07)], M["laiton"], n=8, c=(xp, -0.04, h * 0.45))
    ob = b.objet(pid + "_" + nom)
    x, y, r = pt(pid, cote, s, 0.0)
    return poser(ob, x, y, ZP, r)


# --- meubles (repère local : face avant vers −Y, origine au sol au centre) --------------------
def armoire(nom, w, d, h, mat, fronton=False, ferrures_longues=False):
    b = Bld()
    b.boite(-w / 2, -d / 2, 0.04, w / 2, d / 2, 0.18, mat)
    for sx in (-1, 1):
        b.boite(sx * w / 2 - 0.06 * sx, -d / 2, 0, sx * w / 2, -d / 2 + 0.06, 0.05, mat)
    # tablier chantourné
    prof = [(-w / 2 + 0.06, 0.18)] + [(t, 0.10 + 0.05 * math.cos(3 * math.pi * t / w) ** 2)
                                       for t in np.linspace(-w / 2 + 0.06, w / 2 - 0.06, 15)] + [(w / 2 - 0.06, 0.18)]
    b.prisme(prof, "x", -d / 2 - 0.01, -d / 2 + 0.02, mat)
    b.boite(-w / 2 + 0.02, -d / 2 + 0.03, 0.18, w / 2 - 0.02, d / 2, h - 0.2, mat)
    for sx in (-1, 1):
        b.boite(sx * (w / 2 - 0.08), -d / 2, 0.18, sx * w / 2, -d / 2 + 0.04, h - 0.2, mat)
    b.boite(-0.03, -d / 2 + 0.0, 0.18, 0.03, -d / 2 + 0.035, h - 0.2, mat)
    for sx in (-1, 1):
        xa, xb = sorted((sx * 0.03, sx * (w / 2 - 0.08)))
        b.boite(xa + 0.003, -d / 2 + 0.005, 0.20, xb - 0.003, -d / 2 + 0.035, h - 0.22, mat)
        hz = h - 0.42
        for z0, z1 in ((0.32, 0.32 + hz * 0.30), (0.40 + hz * 0.30, h - 0.36)):
            b.boite(xa + 0.07, -d / 2 - 0.012, z0, xb - 0.07, -d / 2 + 0.005, z1, mat)
            b.boite(xa + 0.10, -d / 2 - 0.02, z0 + 0.04, xb - 0.10, -d / 2 - 0.012, z1 - 0.04, mat)
        # ferrures laiton
        L = 0.55 if ferrures_longues else 0.18
        xf = sx * 0.045
        b.boite(xf - 0.012, -d / 2 - 0.006, h * 0.45 - L / 2, xf + 0.012, -d / 2 + 0.0, h * 0.45 + L / 2, M["laiton"])
        for zf in (0.45, h - 0.45):
            xg = sx * (w / 2 - 0.065)
            b.boite(xg - 0.01, -d / 2 - 0.008, zf - 0.08, xg + 0.01, -d / 2 + 0.0, zf + 0.08, M["laiton"])
    # corniche en gradins
    for z0, z1, e in ((h - 0.2, h - 0.15, 0.01), (h - 0.15, h - 0.09, 0.04), (h - 0.09, h - 0.03, 0.07),
                      (h - 0.03, h, 0.09)):
        b.boite(-w / 2 - e, -d / 2 - e, z0, w / 2 + e, d / 2, z1, mat)
    if fronton:
        prof = [(-w / 2 - 0.09, h)] + [(t, h + 0.05 + 0.13 * math.exp(-(t / (w * 0.22)) ** 2)
                                        - 0.03 * math.cos(6 * t / w))
                                       for t in np.linspace(-w / 2 - 0.09, w / 2 + 0.09, 21)] + [(w / 2 + 0.09, h)]
        b.prisme(prof, "x", -d / 2 - 0.09, -d / 2 + 0.08, mat)
    return b.objet(nom)


def commode(nom, w, d, h, mat, portes=False, plateau=None):
    b = Bld()
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.boite(sx * w / 2 - 0.05 * sx, sy * d / 2 - 0.05 * sy, 0, sx * w / 2 - 0.01 * sx, sy * d / 2 - 0.01 * sy,
                    0.14, mat)
    b.boite(-w / 2, -d / 2 + 0.01, 0.10, w / 2, d / 2, h - 0.035, mat)
    b.boite(-w / 2 - 0.025, -d / 2 - 0.02, h - 0.035, w / 2 + 0.025, d / 2, h, plateau or mat)
    rangs = [(h - 0.22, h - 0.05), (0.14, h - 0.24)] if portes else \
        [(h - 0.25, h - 0.05), (h * 0.40, h - 0.27), (0.14, h * 0.38)]
    for i, (z0, z1) in enumerate(rangs):
        if portes and i == 1:
            for sx in (-1, 1):
                xa, xb = sorted((sx * 0.005, sx * (w / 2 - 0.04)))
                b.boite(xa, -d / 2 - 0.012, z0, xb, -d / 2 + 0.01, z1, mat)
                b.boite(xa + 0.06, -d / 2 - 0.022, z0 + 0.06, xb - 0.06, -d / 2 - 0.012, z1 - 0.06, mat)
                b.boite(sx * 0.04 - 0.008, -d / 2 - 0.03, (z0 + z1) / 2 - 0.04, sx * 0.04 + 0.008, -d / 2 - 0.01,
                        (z0 + z1) / 2 + 0.04, M["laiton"])
        else:
            nb = 2 if (portes and i == 0) else 1
            lw = (w - 0.08) / nb
            for k in range(nb):
                xa = -w / 2 + 0.04 + k * lw
                b.boite(xa + 0.004, -d / 2 - 0.012, z0, xa + lw - 0.004, -d / 2 + 0.01, z1, mat)
                for xp in ((xa + lw * 0.25, xa + lw * 0.75) if lw > 0.6 else (xa + lw / 2,)):
                    b.boite(xp - 0.05, -d / 2 - 0.03, (z0 + z1) / 2 - 0.012, xp + 0.05, -d / 2 - 0.012,
                            (z0 + z1) / 2 + 0.012, M["laiton"])
    return b.objet(nom)


def pieds_galbes(b, w, d, h, mat, r=0.022, retrait=0.03):
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (w / 2 - retrait), sy * (d / 2 - retrait)
            b.tube([(x, y, h), (x + sx * 0.03, y + sy * 0.03, h * 0.6), (x - sx * 0.01, y - sy * 0.01, h * 0.2),
                    (x + sx * 0.025, y + sy * 0.025, 0.0)], lambda i: r * (1.0 - 0.12 * i), mat, n=6)


def table_plateau(nom, w, d, h, mat, ep=0.035, ceinture=0.10, plateau=None, galbe=True):
    b = Bld()
    b.boite(-w / 2, -d / 2, h - ep, w / 2, d / 2, h, plateau or mat)
    b.boite(-w / 2 + 0.03, -d / 2 + 0.03, h - ep - ceinture, w / 2 - 0.03, d / 2 - 0.03, h - ep, mat)
    if galbe:
        pieds_galbes(b, w, d, h - ep, mat)
    else:
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = sx * (w / 2 - 0.05), sy * (d / 2 - 0.05)
                b.boite(x - 0.02, y - 0.02, 0, x + 0.02, y + 0.02, h - ep, mat)
    return b


def livres(b, x0, y, z, n, h=0.25, prof=0.18, couche=False):
    x = x0
    for k in range(n):
        e = 0.025 + 0.02 * random.random()
        hh = h * (0.8 + 0.25 * random.random())
        m = LIVRES[k % len(LIVRES)]
        if couche:
            b.boite(x - prof / 2, y - hh / 2, z, x + prof / 2, y + hh / 2, z + e, m)
            z += e
        else:
            b.boite(x, y - prof / 2, z, x + e, y + prof / 2, z + hh, m)
            x += e + 0.002
    return x


# ----------------------------------------------------------------------------------------------
# Assets Poly Haven (CC0) : importés une fois, instanciés
# ----------------------------------------------------------------------------------------------
def importer_asset(nom, fichier, hauteur=None, rot=0.0):
    activer(LIB)
    avant = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(PH, "polyhaven-" + nom, fichier))
    nouveaux = [o for o in bpy.data.objects if o not in avant]
    mesh = [o for o in nouveaux if o.type == "MESH"]
    for o in mesh:
        if o.data.users > 1:
            o.data = o.data.copy()
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in nouveaux:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    if len(mesh) > 1:
        with bpy.context.temp_override(active_object=mesh[0], selected_editable_objects=mesh,
                                       selected_objects=mesh):
            bpy.ops.object.join()
    ob = mesh[0]
    me = ob.data
    if rot:
        me.transform(Matrix.Rotation(rot, 4, "Z"))
    cs = np.array([v.co[:] for v in me.vertices])
    mn, mx = cs.min(0), cs.max(0)
    me.transform(Matrix.Translation(Vector((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, -mn[2]))))
    if hauteur:
        me.transform(Matrix.Scale(hauteur / (mx[2] - mn[2]), 4))
    me.name = ID + "_" + nom
    ob.name = "lib_" + nom
    ob.hide_render = True
    activer(COL)
    cs = np.array([v.co[:] for v in me.vertices])
    log("asset", nom, "dims", np.round(cs.max(0) - cs.min(0), 2), "faces", len(me.polygons))
    return ob


def variante_teinte(src, nom, teinte, seuil=None):
    """Copie d'un asset dont la texture de couleur est reteintée (tissu clair → teinte)."""
    me = src.data.copy()
    me.name = ID + "_" + nom
    for i, m in enumerate(me.materials):
        m2 = m.copy()
        m2.name = ID + "_" + nom + "_%d" % i
        for n in m2.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and n.image.colorspace_settings.name == "sRGB":
                a = np.empty(n.image.size[0] * n.image.size[1] * 4, np.float32)
                n.image.pixels.foreach_get(a)
                a = a.reshape(n.image.size[1], n.image.size[0], 4)
                rgb = a[:, :, :3]
                L = lum(rgb)
                sat = rgb.max(2) - rgb.min(2)
                masque = np.ones_like(L) if seuil is None else np.clip((L - seuil) / 0.1, 0, 1) * (sat < 0.12)
                t = np.array(teinte)[None, None, :] * (L / max(L[masque > 0.5].mean() if (masque > 0.5).any() else 0.5, 1e-3))[:, :, None]
                rgb[:] = rgb * (1 - masque[:, :, None]) + np.clip(t, 0, 1) * masque[:, :, None]
                chemin = sauver(nom + "_%d" % i, rgb[::-1])
                n.image = bpy.data.images.load(chemin, check_existing=True)
        me.materials[i] = m2
    ob = bpy.data.objects.new("lib_" + nom, me)
    LIB.objects.link(ob)
    ob.hide_render = True
    return ob


log("assets…")
A_FAUTEUIL = importer_asset("ArmChair_01", "ArmChair_01_1k.gltf", hauteur=0.95)
A_CHAISE = importer_asset("dining_chair_02", "dining_chair_02_1k.gltf", hauteur=0.95)
A_PAILLE = importer_asset("gallinera_chair", "gallinera_chair_1k.gltf", hauteur=0.9)
A_POUF = importer_asset("Ottoman_01", "Ottoman_01_1k.gltf", hauteur=0.42)
A_PLANTE = importer_asset("potted_plant_02", "potted_plant_02_1k.gltf", hauteur=0.9)
A_FOUGERE = importer_asset("potted_plant_04", "potted_plant_04_1k.gltf", hauteur=1.3)
A_BERGERE = variante_teinte(A_FAUTEUIL, "bergere_velours_rose", (0.55, 0.36, 0.36), seuil=0.55)
A_POUF_V = variante_teinte(A_POUF, "pouf_violet", (0.30, 0.12, 0.35))
A_CHAISE_GRISE = A_CHAISE     # garniture grise non reteintée (tissu sombre de l'asset)
# sens des assets : face avant vers −Y (vérifié sur les rendus)
ROT_ASSET = {"fauteuil": 0.0, "chaise": 0.0, "paille": 0.0}

# ----------------------------------------------------------------------------------------------
# Revêtements et décors fixes communs
# ----------------------------------------------------------------------------------------------
log("revêtements…")
parquet("chambre_1", M["parquet_d"])
parquet("chambre_2", M["parquet_v"])
parquet("chambre_3", M["parquet_v"])
plinthes("chambre_1", 0.18, 0.02, M["laque"])
plinthes("chambre_2", 0.24, 0.025, M["vert_eau"])
plinthes("chambre_3", 0.18, 0.02, M["laque"])
panneaux_muraux("chambre_2", Z0 + 0.20, ZC - 0.25, M["rayures"], "chambre_2_papier_peint")
panneaux_muraux("chambre_1", Z0 + 0.10, ZC - 0.20, M["creme"], "chambre_1_peinture")
panneaux_muraux("chambre_3", Z0 + 0.10, ZC - 0.20, M["blanc_casse"], "chambre_3_peinture")
chambranles("chambre_1", M["laque"])
chambranles("chambre_2", M["laque"])
chambranles("chambre_3", M["laque"])
PROFIL_GORGE = [(0.0, 0.04, 0.26), (0.04, 0.08, 0.22), (0.08, 0.12, 0.17), (0.12, 0.16, 0.12), (0.16, 0.20, 0.08),
                (0.20, 0.235, 0.10), (0.235, 0.27, 0.05)]
PROFIL_FILETS = [(0.0, 0.03, 0.20), (0.03, 0.07, 0.16), (0.07, 0.11, 0.10), (0.11, 0.14, 0.13), (0.14, 0.18, 0.06),
                 (0.18, 0.21, 0.04)]
PROFIL_FEUILLAGE = [(0.0, 0.04, 0.32), (0.04, 0.09, 0.27), (0.09, 0.15, 0.20), (0.15, 0.20, 0.14), (0.20, 0.24, 0.17),
                    (0.24, 0.29, 0.08), (0.29, 0.32, 0.05)]
corniche("chambre_1", PROFIL_GORGE)
corniche("chambre_2", PROFIL_FILETS, filet=(0.45, 0.035))
corniche("chambre_3", PROFIL_FEUILLAGE, filet=(0.55, 0.03))
# débord des tringles réduit là où un mur en retour est proche
DEBORD = {("chambre_2", 2.73): (0.45, 0.05), ("chambre_2", -2.73): (0.05, 0.45), ("chambre_3", -5.25): (0.45, 0.2)}
for pid, m_r, m_t, emb in (("chambre_1", "rideau_rose", "laiton", False), ("chambre_2", "rideau_taupe", "bronze", True),
                           ("chambre_3", "rideau_ecru", "bois_sombre", True)):
    for o in OUV[pid]:
        if o["type"] == "fenetre":
            axe = round((o["s0"] + o["s1"]) / 2, 2)
            rideaux(pid, o, M[m_r], M[m_t], embrasse=emb, deb=DEBORD.get((pid, axe), (0.45, 0.45)))

# ==============================================================================================
# Chambre 1 (angle SE ; P47 vers l'est depuis la porte, P48 vers l'angle SE, P49 vers le sud)
# ==============================================================================================
log("chambre 1…")
P1 = "chambre_1"
lustre(P1, 14.25, 6.475, 5, 0.32, M["fer"], haut=0.85, chaine=0.55)
rosace(P1 + "_rosace_feuilles", 14.25, 6.475, 0.4, feuilles=10)
# armoire provençale dans l'angle des fenêtres, contre le mur sud
x, y, r = pt(P1, "S", 16.72, 0.28)
poser(armoire(P1 + "_armoire", 1.2, 0.55, 2.1, M["noyer"]), x, y, ZP, r)
b = Bld()
b.boite(-0.25, -0.02, 0, 0.25, 0.02, 0.6, M["bois_sombre"])
ob = b.objet(P1 + "_panneau_bois")
x, y, r = pt(P1, "S", 16.1, 0.62)
poser(ob, x, y, ZP, r)
ob.rotation_euler = (math.radians(-12), 0, r)
# commode-buffet à portes et tiroirs contre le mur nord, garniture
x, y, r = pt(P1, "N", 13.2, 0.25)
poser(commode(P1 + "_commode", 1.4, 0.5, 1.0, M["noyer"], portes=True), x, y, ZP, r)
poser(lampe(P1 + "_lampe_balustre", "laiton", "abat_blanc", 0.45, 0.11, 0.17, 0.24), 12.75, 4.32, ZP + 1.0)
b = Bld()
b.tour([(0.0, 0.0), (0.06, 0.0), (0.07, 0.08), (0.045, 0.2), (0.035, 0.24), (0.045, 0.26), (0.0, 0.26)], M["verre"], n=12)
for k in range(16):
    a = 2 * math.pi * k / 16
    rr = 0.02 + 0.03 * random.random()
    top = (rr * 3.5 * math.cos(a), rr * 3.5 * math.sin(a), 0.48 + 0.12 * random.random())
    b.tube([(0, 0, 0.1), (rr * math.cos(a), rr * math.sin(a), 0.3), top], 0.004, M["sechees"], n=4)
    b.tour([(0.0, -0.03), (0.025, 0.0), (0.0, 0.04)], M["sechees"], n=6, c=top)
poser(b.objet(P1 + "_bouquet_seche"), 13.65, 4.33, ZP + 1.0)
b = Bld()
b.tour([(0.0, 0.0), (0.05, 0.0), (0.05, 0.03), (0.02, 0.05), (0.035, 0.14), (0.025, 0.2), (0.03, 0.24), (0.018, 0.28),
        (0.0, 0.3)], M["fer"], n=10)
poser(b.objet(P1 + "_statuette_bronze"), 13.3, 4.30, ZP + 1.0)
b = Bld()
livres(b, 0, 0, 0, 4, h=0.3, prof=0.22, couche=True)
poser(b.objet(P1 + "_livres"), 13.0, 4.36, ZP + 1.0)
tableau("tableau_eglise", P1, "N", 13.2, ZP + 1.95, 0.5, 0.65, "or_cadre", "eglise")
tableau("tableau_nature_morte", P1, "E", 5.1, ZP + 2.0, 0.55, 0.4, "or_cadre", "nature_morte")
# lampadaire laiton dans l'angle nord-est
poser(lampe(P1 + "_lampadaire", "laiton", "abat_jour", 1.38, 0.17, 0.24, 0.30, plis=0.04, r_pied=0.15, tige=True), 16.95, 4.55)
# petite porte laquée (vers le bloc est non vu, condamnée) au fond du mur nord
porte_decor("petite_porte", P1, "N", 15.95, 0.7, 2.2)
# table ronde nappée sur le tapis, velours bordeaux en tas
b = Bld()
b.tour([(0.0, 0.02), (0.66, 0.02), (0.645, 0.30), (0.625, 0.70), (0.61, 0.765), (0.0, 0.775)], M["nappe"], n=32,
       plis=0.01)
b.tour([(0.0, 0.76), (0.34, 0.76), (0.32, 0.83), (0.25, 0.90), (0.12, 0.95), (0.0, 0.96)], M["velours"], n=12,
       c=(0.08, -0.05, 0.0), plis=0.08)
poser(b.objet(P1 + "_table_ronde"), 14.7, 6.95)
b = Bld()
b.quad_uv([(-1.25, -0.9, 0.0), (1.25, -0.9, 0.0), (1.25, 0.9, 0.0), (-1.25, 0.9, 0.0)], M["tapis_1"])
b.boite(-1.25, -0.9, -0.009, 1.25, 0.9, -0.001, M["tapis_1"])
poser(b.objet(P1 + "_tapis"), 14.65, 6.95, ZP + 0.01, math.radians(4))
# chaises
for nom, src, x, y, vue in (("chaise_lp_1", A_CHAISE, 14.7, 6.05, (0, 1)), ("chaise_lp_2", A_CHAISE, 15.6, 7.05, (-1, 0)),
                            ("chaise_grise_1", A_CHAISE_GRISE, 11.95, 4.75, (0.5, 1)),
                            ("chaise_grise_2", A_CHAISE_GRISE, 16.45, 5.6, (-1, 0.3)),
                            ("chaise_medaillon", A_CHAISE, 14.3, 4.5, (0, 1)),
                            ("chaise_paillee", A_PAILLE, 13.2, 8.35, (0.2, -1)),
                            ("chaise_cannee_1", A_PAILLE, 11.62, 7.72, (1, 0)),
                            ("chaise_cannee_2", A_PAILLE, 11.82, 8.42, (1, -0.3))):
    instance(P1 + "_" + nom, src, x, y, ZP, rot_face(vue) + ROT_ASSET["paille" if src is A_PAILLE else "chaise"])
# linge toile de Jouy sur les chaises cannées
b = Bld()
b.tour([(0.0, 0.44), (0.26, 0.44), (0.27, 0.40), (0.25, 0.25), (0.22, 0.30), (0.2, 0.55), (0.12, 0.62), (0.0, 0.63)],
       M["jouy"], n=10, plis=0.12, sx=0.85)
src_linge = b.objet(P1 + "_linge_jouy_1")
poser(src_linge, 11.62, 7.72)
instance(P1 + "_linge_jouy_2", src_linge, 11.82, 8.42, ZP, 1.2)
# pétrin sculpté et panetière à fuseaux contre le mur sud, à l'ouest de la fenêtre
b = Bld()
for sx in (-1, 1):
    for sy in (-1, 1):
        b.tube([(sx * 0.45, sy * 0.2, 0.0), (sx * 0.43, sy * 0.19, 0.42)], 0.025, M["noyer"], n=6)
b.solide([(-0.5, -0.24), (0.5, -0.24), (0.5, 0.24), (-0.5, 0.24)], 0.42, 0.82, M["noyer"])
b.boite(-0.53, -0.27, 0.82, 0.53, 0.26, 0.86, M["noyer"])
b.boite(-0.38, -0.255, 0.48, 0.38, -0.24, 0.76, M["noyer"])
for k in range(5):
    b.tour([(0.0, 0.0), (0.03, 0.0), (0.0, 0.05)], M["noyer"], n=6, c=(-0.3 + k * 0.15, -0.26, 0.6))
b.boite(-0.3, -0.18, 0.86, 0.2, 0.15, 0.95, M["linge"])
x, y, r = pt(P1, "S", 12.35, 0.26)
poser(b.objet(P1 + "_petrin"), x, y, ZP, r)
b = Bld()
b.boite(-0.4, -0.3, 0.0, 0.4, 0.0, 0.06, M["noyer"])
b.boite(-0.4, -0.3, 0.72, 0.4, 0.0, 0.8, M["noyer"])
prof = [(-0.42, 0.8)] + [(t, 0.86 + 0.07 * math.cos(math.pi * t / 0.42) ** 2) for t in np.linspace(-0.42, 0.42, 11)] + [(0.42, 0.8)]
b.prisme(prof, "x", -0.32, -0.27, M["noyer"])
b.boite(-0.4, -0.02, 0.0, 0.4, 0.0, 0.8, M["noyer"])
for sx in (-1, 1):
    b.boite(sx * 0.4 - 0.04 * sx, -0.3, 0.06, sx * 0.4, 0.0, 0.72, M["noyer"])
for k in range(9):
    xx = -0.32 + k * 0.08
    b.tour([(0.008, 0.0), (0.014, 0.15), (0.008, 0.33), (0.014, 0.5), (0.008, 0.66)], M["noyer"], n=6, c=(xx, -0.27, 0.06))
x, y, r = pt(P1, "S", 12.35, 0.0)
poser(b.objet(P1 + "_panetiere"), x, y, ZP + 1.05, r)
# niche cintrée sur le mur ouest (rendue en saillie : la coque n'est pas percée)
b = Bld()
w, hn, z0 = 0.6, 1.8, 0.9
arc = [(-w / 2, z0), (w / 2, z0)] + [(w / 2 * math.cos(t), z0 + hn - w / 2 + w / 2 * math.sin(t))
                                    for t in np.linspace(0, math.pi, 13)]
b.prisme(arc, "x", -0.012, 0.0, M["ombre"])
pts = [(-w / 2 - 0.04, -0.02, z0 - 0.04)] + [((w / 2 + 0.04) * math.cos(t), -0.02, z0 + hn - w / 2 + (w / 2 + 0.04) * math.sin(t))
                                          for t in np.linspace(math.pi, 0, 15)] + [(w / 2 + 0.04, -0.02, z0 - 0.04)]
b.tube(pts[::-1], 0.025, M["laque"], n=6)
b.boite(-w / 2 - 0.06, -0.07, z0 - 0.06, w / 2 + 0.06, 0.0, z0, M["laque"])
b.boite(-w / 2, -0.2, z0 + 0.75, w / 2, 0.0, z0 + 0.78, M["laque"])
b.tour([(0.0, 0.0), (0.04, 0.0), (0.03, 0.1), (0.022, 0.16), (0.03, 0.18), (0.0, 0.22)], M["laque"], n=8,
       c=(-0.1, -0.1, z0 + 0.78))
b.boite(0.08, -0.12, z0 + 0.78, 0.2, -0.04, z0 + 0.93, M["bleu"])
x, y, r = pt(P1, "O", 7.72, 0.0)
poser(b.objet(P1 + "_niche"), x, y, ZP, r)
tableau("gravure", P1, "O", 5.25, ZP + 1.75, 0.35, 0.45, "or_cadre", "gravure")
radiateur("radiateur", P1, "S", 14.4, 0.9)

# ==============================================================================================
# Chambre 2 à rayures (P52/P54 vers l'ouest depuis la salle à manger, P53 vers la cheminée au nord)
# ==============================================================================================
log("chambre 2…")
P2 = "chambre_2"
lustre(P2, 0.0, 6.2, 8, 0.33, M["bronze"], haut=0.9, chaine=0.5, rosace_r=0.28)


def cheminee_lxv(nom, w=1.3, d=0.38, h=1.08):
    b = Bld()
    mb = M["marbre"]
    b.boite(-w / 2 - 0.15, -d / 2 - 0.40, -0.005, w / 2 + 0.15, d / 2, 0.025, mb)
    for sx in (-1, 1):
        xa, xb = sorted((sx * w / 2, sx * (w / 2 - 0.2)))
        b.boite(xa, -d / 2, 0.025, xb, d / 2, h - 0.06, mb)
        prof = [(-d / 2, 0.025), (-d / 2 - 0.05, 0.08), (-d / 2 - 0.02, 0.25), (-d / 2 - 0.015, h - 0.45),
                (-d / 2 - 0.06, h - 0.2), (-d / 2 - 0.03, h - 0.08), (-d / 2, h - 0.06)]
        b.prisme(prof, "y", xa + 0.04, xb - 0.04, mb)
    prof = [(-w / 2 + 0.2, h - 0.06), (-w / 2 + 0.2, h - 0.34)] + \
        [(t, h - 0.34 + 0.09 * (1 - (t / (w / 2 - 0.2)) ** 2) + 0.025 * math.sin(abs(t) * 12) * (abs(t) > 0.12))
         for t in np.linspace(-w / 2 + 0.2, w / 2 - 0.2, 17)] + [(w / 2 - 0.2, h - 0.34), (w / 2 - 0.2, h - 0.06)]
    b.prisme(prof, "x", -d / 2, d / 2, mb)
    b.tour([(0.0, 0.0), (0.06, 0.0), (0.05, 0.03), (0.0, 0.04)], mb, n=10, c=(0, -d / 2, h - 0.2), sx=1.4)
    b.boite(-w / 2 - 0.05, -d / 2 - 0.05, h - 0.06, w / 2 + 0.05, d / 2, h, mb)
    b.boite(-w / 2 - 0.03, -d / 2 - 0.035, h - 0.085, w / 2 + 0.03, d / 2, h - 0.06, mb)
    b.boite(-w / 2 + 0.2, -d / 2 + 0.10, 0.025, w / 2 - 0.2, d / 2, h - 0.25, M["fonte"])
    return b.objet(nom)


x, y, r = pt(P2, "N", 0.0, 0.19)
poser(cheminee_lxv(P2 + "_cheminee"), x, y, ZP, r)
# trumeau de boiserie à guirlande au-dessus de la cheminée
b = Bld()
tw, th, tz = 0.95, 1.75, 1.15
b.boite(-tw / 2, -0.03, tz, tw / 2, 0.0, tz + th, M["laque"])
for (a0, a1, c0, c1) in ((-tw / 2, tw / 2, tz, tz + 0.06), (-tw / 2, tw / 2, tz + th - 0.06, tz + th),
                         (-tw / 2, -tw / 2 + 0.06, tz, tz + th), (tw / 2 - 0.06, tw / 2, tz, tz + th)):
    b.boite(a0, -0.05, c0, a1, -0.03, c1, M["or_cadre"])
gpts = [(-tw / 2 + 0.12 + t * (tw - 0.24), -0.055, tz + th - 0.25 - 0.12 * math.sin(math.pi * t))
        for t in np.linspace(0, 1, 13)]
b.tube(gpts, 0.022, M["or_cadre"], n=6)
for sx in (-1, 1):
    b.tube([(sx * (tw / 2 - 0.12), -0.055, tz + th - 0.25), (sx * (tw / 2 - 0.12), -0.055, tz + th - 0.55)], 0.015,
           M["or_cadre"], n=6)
ob = b.objet(P2 + "_trumeau")
x, y, r = pt(P2, "N", 0.0, 0.0)
poser(ob, x, y, ZP, r)
tableau("tableau_trumeau", P2, "N", 0.0, ZP + 1.95, 0.45, 0.6, "or_cadre", "paysage", prof=0.07)
tableau("tableau_portrait", P2, "N", -1.35, ZP + 1.85, 0.35, 0.5, "or_cadre", "portrait_nuit")
tableau("tableau_bouquet", P2, "N", 1.45, ZP + 1.8, 0.5, 0.6, "cadre_sombre", "bouquet")
# plantes sur la cheminée
instance(P2 + "_plante_cheminee", A_FOUGERE, -0.4, 4.36, ZP + 1.08, 0.3, 0.35)
# table de chevet Directoire, lampe en rotin
b = table_plateau(P2 + "_chevet", 0.45, 0.35, 0.70, M["acajou"], ceinture=0.12, galbe=False)
b.tube([(-0.18, -0.13, 0.15), (0.18, 0.13, 0.15)], 0.012, M["acajou"])
b.tube([(-0.18, 0.13, 0.15), (0.18, -0.13, 0.15)], 0.012, M["acajou"])
b.boite(-0.03, -0.18, 0.60, 0.03, -0.175, 0.62, M["laiton"])
b.tour([(0.0, 0.70), (0.06, 0.70), (0.11, 0.80), (0.12, 0.92), (0.09, 1.03), (0.0, 1.08)], M["rotin"], n=14,
       c=(0.0, 0.02, 0.0), plis=0.03)
x, y, r = pt(P2, "N", 1.15, 0.22)
poser(b.objet(P2 + "_chevet"), x, y, ZP, r)
# petite table d'enfant et deux chaises laquées blanches devant la cheminée
b = table_plateau(P2 + "_table_enfant", 0.7, 0.5, 0.5, M["laque"], ceinture=0.06, galbe=False)
livres(b, -0.1, 0.0, 0.5, 1, h=0.22, prof=0.16, couche=True)
poser(b.objet(P2 + "_table_enfant"), 0.15, 5.3)
b = Bld()
for sx in (-1, 1):
    for sy in (-1, 1):
        b.boite(sx * 0.13 - 0.012, sy * 0.13 - 0.012, 0, sx * 0.13 + 0.012, sy * 0.13 + 0.012, 0.28, M["laque"])
b.boite(-0.15, -0.15, 0.28, 0.15, 0.15, 0.31, M["laque"])
for sx in (-1, 1):
    b.boite(sx * 0.13 - 0.012, 0.12, 0.31, sx * 0.13 + 0.012, 0.145, 0.58, M["laque"])
b.boite(-0.14, 0.12, 0.45, 0.14, 0.14, 0.56, M["laque"])
src = b.objet(P2 + "_chaise_enfant_1")
poser(src, -0.35, 5.35, ZP, rot_face((1, 0)))
instance(P2 + "_chaise_enfant_2", src, 0.65, 5.3, ZP, rot_face((-1, 0)))
# marquise laquée blanche au premier plan (angle NE)
b = Bld()
mw, md = 1.3, 0.68
for sx in (-1, 1):
    for sy in (-1, 1):
        b.tube([(sx * (mw / 2 - 0.05), sy * (md / 2 - 0.05), 0.38), (sx * (mw / 2 - 0.03), sy * (md / 2 - 0.03), 0.18),
                (sx * (mw / 2 - 0.05), sy * (md / 2 - 0.05), 0.0)], 0.022, M["laque"], n=6)
b.boite(-mw / 2, -md / 2, 0.30, mw / 2, md / 2, 0.40, M["laque"])
b.boite(-mw / 2 + 0.03, -md / 2 + 0.02, 0.40, mw / 2 - 0.03, md / 2 - 0.08, 0.50, M["fleuri"])
prof = [(-mw / 2, 0.40)] + [(t, 0.85 + 0.12 * math.cos(math.pi * t / mw) ** 2) for t in np.linspace(-mw / 2, mw / 2, 13)] + [(mw / 2, 0.40)]
b.prisme(prof, "x", md / 2 - 0.08, md / 2, M["laque"])
prof2 = [(-mw / 2 + 0.06, 0.48)] + [(t, 0.80 + 0.10 * math.cos(math.pi * t / mw) ** 2) for t in np.linspace(-mw / 2 + 0.06, mw / 2 - 0.06, 13)] + [(mw / 2 - 0.06, 0.48)]
b.prisme(prof2, "x", md / 2 - 0.10, md / 2 - 0.079, M["fleuri"])
for sx in (-1, 1):
    b.boite(sx * mw / 2 - 0.06 * sx, -md / 2 + 0.05, 0.40, sx * mw / 2, md / 2 - 0.05, 0.68, M["laque"])
    b.boite(sx * mw / 2 - 0.05 * sx, -md / 2 + 0.06, 0.50, sx * mw / 2 - 0.01 * sx, md / 2 - 0.06, 0.66, M["fleuri"])
b.boite(-0.2, md / 2 - 0.25, 0.50, 0.15, md / 2 - 0.1, 0.78, M["linge"])
poser(b.objet(P2 + "_marquise"), 2.75, 5.05, ZP, rot_face((-1, 1)))
# chaises paillées
R_P2 = rot_face((-1, -0.5)) + ROT_ASSET["paille"]
instance(P2 + "_chaise_paillee_1", A_PAILLE, -0.9, 6.0, ZP, rot_face((1, -0.3)) + ROT_ASSET["paille"])
instance(P2 + "_chaise_paillee_2", A_PAILLE, 2.4, 6.15, ZP, R_P2)
b = Bld()
b.boite(-0.2, -0.2, 0.46, 0.2, 0.2, 0.62, M["linge"])
b.boite(-0.17, -0.15, 0.62, 0.15, 0.17, 0.72, M["linge"])
poser(b.objet(P2 + "_coussins"), 2.4, 6.15, ZP, R_P2)
# bergère en velours vieux rose dans l'angle sud-ouest
instance(P2 + "_bergere", A_BERGERE, -2.85, 8.25, ZP, rot_face((1, -1)) + ROT_ASSET["fauteuil"])
# console sombre à deux plateaux (angle nord-ouest) chargée de jouets, grande plante
b = table_plateau(P2 + "_console", 1.2, 0.4, 0.85, M["bois_sombre"], galbe=False, ceinture=0.08)
b.boite(-0.55, -0.15, 0.22, 0.55, 0.15, 0.25, M["bois_sombre"])
for k, (mm, xx) in enumerate(((M["rouge"], -0.45), (M["jaune"], -0.25), (M["bleu"], 0.25), (M["rouge"], 0.4))):
    b.tour([(0.0, 0.85), (0.07, 0.85), (0.08, 0.98), (0.0, 0.98)], mm, n=10, c=(xx, 0.0, 0.0))
b.boite(-0.1, -0.12, 0.25, 0.3, 0.1, 0.45, M["bleu"])
b.tour([(0.0, 0.85), (0.06, 0.85), (0.07, 0.95), (0.04, 1.05), (0.0, 1.08)], M["laque"], n=10, c=(0.05, 0.0, 0.0))
x, y, r = pt(P2, "N", -2.75, 0.21)
poser(b.objet(P2 + "_console"), x, y, ZP, r)
instance(P2 + "_grande_plante", A_PLANTE, -3.15, 4.40, ZP + 0.85, 0.0, 1.25)
# château fort en jouet bleu
b = Bld()
b.boite(-0.3, -0.2, 0.0, 0.3, 0.2, 0.35, M["bleu"])
for sx in (-1, 1):
    for sy in (-1, 1):
        c = (sx * 0.27, sy * 0.17, 0.0)
        b.tour([(0.07, 0.0), (0.07, 0.5), (0.09, 0.5), (0.0, 0.68)], M["bleu"] if sy < 0 else M["laque"], n=10, c=c)
b.tour([(0.1, 0.35), (0.1, 0.55), (0.12, 0.55), (0.0, 0.78)], M["bleu"], n=10)
poser(b.objet(P2 + "_chateau_jouet"), -3.25, 5.55, ZP, math.radians(20))
# cheval à bascule, camions de pompiers, porteur, arrosoir
b = Bld()
for sy in (-1, 1):
    b.tube([(0.45 * math.sin(t), sy * 0.13, 0.12 - 0.12 * math.cos(t) + 0.01) for t in np.linspace(-1.0, 1.0, 9)],
           0.015, M["bois_clair"], n=6)
for sx in (-1, 1):
    for sy in (-1, 1):
        b.tube([(sx * 0.22, sy * 0.13, 0.04), (sx * 0.17, sy * 0.06, 0.36)], 0.018, M["bois_clair"], n=6)
b.boite(-0.25, -0.08, 0.34, 0.22, 0.08, 0.46, M["bois_clair"])
b.tube([(0.2, 0.0, 0.42), (0.3, 0.0, 0.62)], 0.05, M["bois_clair"], n=6)
b.boite(0.26, -0.04, 0.58, 0.42, 0.04, 0.66, M["bois_clair"])
b.boite(-0.08, -0.09, 0.46, 0.08, 0.09, 0.48, M["rouge"])
poser(b.objet(P2 + "_cheval_bascule"), -1.2, 5.0, ZP, math.radians(25))


def camion(nom, x, y, rot, l=0.4):
    b = Bld()
    b.boite(-l / 2, -0.08, 0.05, l * 0.25, 0.08, 0.17, M["rouge"])
    b.boite(l * 0.25, -0.08, 0.05, l / 2, 0.08, 0.2, M["rouge"])
    b.boite(-l / 2 + 0.03, -0.03, 0.17, l * 0.2, 0.03, 0.2, M["laque"])
    for sx in (-l / 2 + 0.07, l / 2 - 0.07):
        b.tube([(sx, -0.1, 0.045), (sx, 0.1, 0.045)], 0.045, M["noir"], n=10)
    return poser(b.objet(P2 + "_" + nom), x, y, ZP, rot)


camion("camion_1", 0.9, 7.85, math.radians(30))
camion("camion_2", -1.6, 6.05, math.radians(-60), 0.35)
b = Bld()
b.boite(-0.22, -0.11, 0.12, 0.2, 0.11, 0.26, M["jaune"])
b.boite(-0.2, -0.1, 0.26, 0.0, 0.1, 0.3, M["rouge"])
b.tube([(0.16, 0.0, 0.26), (0.18, 0.0, 0.45)], 0.015, M["noir"])
b.tube([(0.18, -0.12, 0.45), (0.18, 0.12, 0.45)], 0.015, M["noir"])
for sx in (-0.15, 0.15):
    b.tube([(sx, -0.13, 0.06), (sx, 0.13, 0.06)], 0.06, M["noir"], n=10)
poser(b.objet(P2 + "_porteur"), 1.9, 8.0, ZP, math.radians(-15))
b = Bld()
b.tour([(0.0, 0.0), (0.09, 0.0), (0.09, 0.22), (0.07, 0.25), (0.0, 0.25)], M["laque"], n=12)
b.tube([(0.08, 0.0, 0.05), (0.25, 0.0, 0.3)], 0.012, M["laque"], n=6)
b.tube([(-0.05, 0.0, 0.25), (-0.02, 0.0, 0.36), (0.04, 0.0, 0.25)], 0.008, M["laque"], n=5, bouts=False)
x, y, r = pt(P2, "N", 0.25, 0.25)
poser(b.objet(P2 + "_arrosoir"), x, y, ZP + 0.025, 0.4)
b = Bld()
b.tour([(0.0, 0.0), (0.03, 0.006), (0.04, 0.03), (0.03, 0.055), (0.0, 0.06)], M["bleu"], n=10)
poser(b.objet(P2 + "_bille"), 0.2, 6.6)
# lambrequin sculpté au-dessus de la deuxième fenêtre, radiateurs bas
o = next(o for o in OUV[P2] if o["type"] == "fenetre" and o["s0"] < -2.0)
b = Bld()
lw = o["s1"] - o["s0"] + 0.5
prof = [(-lw / 2, 0.30)] + [(t, 0.08 * abs(math.sin(4 * math.pi * t / lw))) for t in np.linspace(-lw / 2, lw / 2, 25)] + [(lw / 2, 0.30)]
b.prisme(prof, "x", -0.20, -0.17, M["laque"])
for sx in (-1, 1):
    b.boite(sx * lw / 2 - 0.02 * sx, -0.2, 0.0, sx * lw / 2, 0.0, 0.30, M["laque"])
b.boite(-lw / 2, -0.2, 0.28, lw / 2, 0.0, 0.31, M["laque"])
x, y, r = pt(P2, "S", (o["s0"] + o["s1"]) / 2, 0.0)
poser(b.objet(P2 + "_lambrequin"), x, y, o["zh"] + 0.05, r)
radiateur("radiateur_1", P2, "S", -2.73, 1.0, h=0.45)
radiateur("radiateur_2", P2, "S", 2.73, 1.0, h=0.45)

# ==============================================================================================
# Chambre 3, bureau (P55/P56 vers l'ouest depuis la fenêtre, P57 vers le nord : armoire, porte)
# ==============================================================================================
log("chambre 3…")
P3 = "chambre_3"
lustre(P3, -7.4, 4.625, 8, 0.38, M["fer"], haut=1.1, chaine=0.35, rosace_r=0.5)
# grand tableau marine au mur ouest, meuble bas noir, bureau plat, fauteuils
tableau("tableau_marine", P3, "O", 4.6, ZP + 2.05, 1.9, 1.3, "cadre_sombre", "marine", ep=0.11, prof=0.08)
b = Bld()
b.boite(-0.6, -0.2, 0.0, 0.6, 0.2, 0.08, M["bois_noir"])
b.boite(-0.58, -0.18, 0.08, 0.58, 0.2, 0.95, M["bois_noir"])
b.boite(-0.62, -0.23, 0.95, 0.62, 0.21, 1.0, M["bois_noir"])
for sx in (-1, 1):
    xa, xb = sorted((sx * 0.01, sx * 0.55))
    b.boite(xa, -0.2, 0.12, xb, -0.18, 0.9, M["bois_noir"])
    b.boite(xa + 0.07, -0.215, 0.2, xb - 0.07, -0.2, 0.82, M["bois_noir"])
for k in range(2):
    b.boite(-0.4 + k * 0.5, -0.12, 1.0, -0.28 + k * 0.5, -0.1, 1.17, M["or_cadre"])
x, y, r = pt(P3, "O", 4.6, 0.21)
poser(b.objet(P3 + "_meuble_bas"), x, y, ZP, r)
b = table_plateau(P3 + "_bureau", 1.6, 0.8, 0.76, M["noyer"], ceinture=0.12)
b.boite(-0.68, -0.32, 0.76, 0.68, 0.32, 0.765, M["cuir"])
for sx in (-1, 1):
    for sy in (-1, 1):
        b.boite(sx * 0.745 - 0.025, sy * 0.345 - 0.025, 0.0, sx * 0.745 + 0.025, sy * 0.345 + 0.025, 0.05, M["bronze"])
# iMac (écran tourné vers le fauteuil de travail, côté mur), lampe bouillotte, coffret, téléphone
b.tube([(0.0, -0.05, 0.765), (0.0, 0.0, 0.95)], 0.02, M["alu"], n=6)
b.boite(-0.12, -0.12, 0.765, 0.12, 0.05, 0.775, M["alu"])
b.boite(-0.31, -0.01, 0.88, 0.31, 0.02, 1.25, M["alu"])
b.quad_uv([(0.29, 0.021, 0.95), (-0.29, 0.021, 0.95), (-0.29, 0.021, 1.23), (0.29, 0.021, 1.23)], M["ecran"])
b.boite(0.45, -0.25, 0.765, 0.62, -0.12, 0.85, M["cuir"])
b.boite(-0.6, -0.2, 0.765, -0.45, -0.1, 0.79, M["noir"])
b.boite(-0.4, -0.3, 0.765, -0.1, -0.12, 0.775, M["linge"])
ob = b.objet(P3 + "_bureau")
x, y, r = pt(P3, "O", 4.6, 1.15)
poser(ob, x, y, ZP, r + math.pi)
poser(lampe(P3 + "_lampe_bouillotte", "laiton", "abat_jour", 0.42, 0.10, 0.17, 0.2), x - 0.25, y + 0.62, ZP + 0.765)
poser(lampe(P3 + "_liseuse", "noir", "abat_blanc", 1.38, 0.10, 0.13, 0.18, r_pied=0.12, tige=True), -10.2, 3.35)
for nom, xx, yy, rr in (("fauteuil_1", -8.25, 4.15, 0.0), ("fauteuil_2", -8.25, 5.1, 0.0)):
    instance(P3 + "_" + nom, A_FAUTEUIL, xx, yy, ZP, rot_face((-1, 0.15 if yy < 4.6 else -0.15)) + ROT_ASSET["fauteuil"])
b = Bld()
b.quad_uv([(-1.5, -1.25, 0.0), (1.5, -1.25, 0.0), (1.5, 1.25, 0.0), (-1.5, 1.25, 0.0)], M["tapis_3"])
b.boite(-1.5, -1.25, -0.009, 1.5, 1.25, -0.001, M["tapis_3"])
poser(b.objet(P3 + "_tapis"), -8.9, 4.6, ZP + 0.01, math.pi / 2)
# table à jeux à échiquier et pouf violet (angle nord-ouest)
b = table_plateau(P3 + "_table_jeux", 0.8, 0.5, 0.75, M["noyer"], ceinture=0.08)
b.quad_uv([(-0.22, -0.22, 0.752), (0.22, -0.22, 0.752), (0.22, 0.22, 0.752), (-0.22, 0.22, 0.752)], M["echiquier"])
poser(b.objet(P3 + "_table_jeux"), -9.6, 2.7, ZP, 0.15)
instance(P3 + "_pouf", A_POUF_V, -8.75, 2.45, ZP, 0.3)
# porte condamnée laquée à filets verts au mur ouest (vers le bloc ouest non vu)
porte_decor("porte_ouest", P3, "O", 1.95, 1.0, 2.6, vantaux=2, filets=True)
# mur nord : console Louis XV à livres, grande armoire à fronton, fauteuil en rotin
b = table_plateau(P3 + "_console", 0.8, 0.4, 0.75, M["noyer"], plateau=M["marbre"])
livres(b, -0.3, 0.0, 0.75, 7, h=0.24)
livres(b, 0.1, 0.0, 0.75, 3, h=0.22, prof=0.16, couche=True)
x, y, r = pt(P3, "N", -9.75, 0.21)
poser(b.objet(P3 + "_console"), x, y, ZP, r)
x, y, r = pt(P3, "N", -7.95, 0.34)
poser(armoire(P3 + "_armoire", 1.7, 0.65, 2.5, M["noyer_rouge"], fronton=True, ferrures_longues=True), x, y, ZP, r)
b = Bld()
b.tour([(0.0, 0.0), (0.30, 0.0), (0.32, 0.25), (0.30, 0.40), (0.0, 0.42)], M["rotin"], n=16, plis=0.02)
prof = [(t, 0.42 + 0.48 * math.cos(t / 0.32 * math.pi / 2) ** 0.5) for t in np.linspace(-0.32, 0.32, 13)]
prof = [(-0.32, 0.4)] + prof + [(0.32, 0.4)]
b.prisme(prof, "x", 0.16, 0.24, M["rotin"])
for sx in (-1, 1):
    b.tube([(sx * 0.3, 0.2, 0.62), (sx * 0.32, -0.05, 0.6), (sx * 0.30, -0.25, 0.45)], 0.035, M["rotin"], n=6)
b.boite(-0.26, -0.26, 0.42, 0.26, 0.16, 0.5, M["fleuri"])
b.boite(-0.22, 0.08, 0.5, 0.22, 0.16, 0.8, M["fleuri"])
x, y, r = pt(P3, "N", -6.45, 0.45)
poser(b.objet(P3 + "_fauteuil_rotin"), x, y, ZP, r + math.radians(15))
# mur sud : commode entre les fenêtres, portrait, radiateurs
x, y, r = pt(P3, "S", -7.05, 0.25)
poser(commode(P3 + "_commode", 1.3, 0.5, 0.85, M["noyer"]), x, y, ZP, r)
b = Bld()
for k, (xx, h_) in enumerate(((-0.4, 0.22), (-0.15, 0.18), (0.3, 0.2))):
    b.boite(xx - 0.07, -0.01, 0.0, xx + 0.07, 0.01, h_, M["or_cadre"] if k % 2 else M["noir"])
b.tour([(0.0, 0.0), (0.04, 0.0), (0.09, 0.05), (0.08, 0.055), (0.0, 0.01)], M["noir"], n=12, c=(0.05, -0.05, 0.0))
poser(b.objet(P3 + "_cadres_photo"), x, y - 0.02, ZP + 0.85, r)
tableau("tableau_portrait", P3, "S", -7.05, ZP + 1.75, 0.4, 0.55, "or_cadre", "portrait_femme")
radiateur("radiateur_1", P3, "S", -8.85, 1.0)
radiateur("radiateur_2", P3, "S", -5.25, 1.0)
# mur est : piano droit en merisier, colonne en bois clair, tableau du marché provençal, yucca
b = Bld()
pw, pd, ph = 1.45, 0.55, 1.15
b.boite(-pw / 2, 0.0, 0.0, pw / 2, pd / 2, ph, M["merisier"])
b.boite(-pw / 2 - 0.01, -0.02, ph, pw / 2 + 0.01, pd / 2, ph + 0.03, M["merisier"])
b.boite(-pw / 2, -pd / 2 + 0.03, 0.62, pw / 2, 0.0, 0.70, M["merisier"])
b.quad_uv([(-pw / 2 + 0.07, -pd / 2 + 0.06, 0.702), (pw / 2 - 0.07, -pd / 2 + 0.06, 0.702),
           (pw / 2 - 0.07, -0.02, 0.702), (-pw / 2 + 0.07, -0.02, 0.702)], M["clavier"])
for sx in (-1, 1):
    b.boite(sx * pw / 2 - 0.07 * sx, -pd / 2 + 0.03, 0.62, sx * pw / 2, 0.0, 0.78, M["merisier"])
    b.boite(sx * pw / 2 - 0.06 * sx, -pd / 2 + 0.05, 0.0, sx * pw / 2 - 0.0, -pd / 2 + 0.11, 0.62, M["merisier"])
b.boite(-pw / 2 + 0.07, -0.08, 0.72, pw / 2 - 0.07, 0.0, 0.84, M["merisier"])
b.boite(-pw / 2 + 0.05, -0.01, 0.84, pw / 2 - 0.05, 0.02, ph - 0.03, M["merisier"])
b.boite(-0.3, -0.2, 0.08, 0.3, 0.0, 0.11, M["laiton"])
b.tour([(0.0, ph + 0.03), (0.06, ph + 0.03), (0.09, ph + 0.12), (0.04, ph + 0.28), (0.012, ph + 0.33), (0.0, ph + 0.35)],
       M["ceramique"], n=12, c=(-0.45, 0.12, 0.0))
b.tour([(0.13, ph + 0.30), (0.20, ph + 0.52), (0.195, ph + 0.52), (0.125, ph + 0.30)], M["abat_jour"], n=24,
       c=(-0.45, 0.12, 0.0), plis=0.05)
b.tour([(0.0, ph + 0.03), (0.035, ph + 0.03), (0.035, ph + 0.11), (0.0, ph + 0.11)], M["verre_bleu"], n=10, c=(0.2, 0.12, 0.0))
b.tour([(0.0, ph + 0.03), (0.04, ph + 0.03), (0.05, ph + 0.10), (0.03, ph + 0.15), (0.0, ph + 0.15)], M["chrome"], n=10,
       c=(0.45, 0.1, 0.0))
x, y, r = pt(P3, "E", 3.2, 0.28)
poser(b.objet(P3 + "_piano"), x, y, ZP, r)
b = Bld()
b.boite(-0.25, -0.2, 0.0, 0.25, 0.2, 1.2, M["bois_clair"])
for z in (0.3, 0.6, 0.9):
    b.boite(-0.22, -0.205, z, 0.22, -0.18, z + 0.02, M["bois_clair"])
livres(b, -0.2, 0.0, 0.62, 6, h=0.25, prof=0.25)
x, y, r = pt(P3, "E", 2.2, 0.21)
poser(b.objet(P3 + "_colonne"), x, y, ZP, r)
tableau("tableau_marche", P3, "E", 3.2, ZP + 2.05, 1.3, 0.9, "cadre_sombre", "marche", ep=0.09, prof=0.07)
instance(P3 + "_yucca", A_FOUGERE, -4.7, 5.5, ZP, 0.8, 1.0)

# ----------------------------------------------------------------------------------------------
# Contrôles : dégagement devant les portes
# ----------------------------------------------------------------------------------------------
bpy.context.view_layer.update()


def boite_xy(ob):
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return min(c.x for c in cs), min(c.y for c in cs), max(c.x for c in cs), max(c.y for c in cs), min(c.z for c in cs)


for pid in CH:
    for o in OUV[pid]:
        if o["type"] != "porte":
            continue
        if o["o"] == "NS":
            zx0, zx1 = sorted((o["c"], o["c"] + o["n"][0] * 0.8))
            zone = (zx0, o["s0"], zx1, o["s1"])
        else:
            zy0, zy1 = sorted((o["c"], o["c"] + o["n"][1] * 0.8))
            zone = (o["s0"], zy0, o["s1"], zy1)
        genants = []
        for ob in COL.objects:
            if ob.type != "MESH" or not ob.name.startswith(pid) or any(k in ob.name for k in
                                                                        ("parquet", "plinthes", "chambranles", "corniche",
                                                                         "papier", "peinture", "tapis", "rideaux", "lustre", "rosace")):
                continue
            x0, y0, x1, y1, zmin = boite_xy(ob)
            if zmin > ZP + 2.0:
                continue
            if x0 < zone[2] and x1 > zone[0] and y0 < zone[3] and y1 > zone[1]:
                genants.append(ob.name)
        log("dégagement", o["nom"], "côté", pid, ":", "libre" if not genants else "GÊNE " + ", ".join(genants))

# ----------------------------------------------------------------------------------------------
# Export (avant le miroir des rendus)
# ----------------------------------------------------------------------------------------------
n_obj = len(COL.objects)
activer(COL)
glb = os.path.join(EXPORT, ID + ".glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_active_collection=True, export_apply=True,
                          export_yup=True, export_lights=True, export_image_format="JPEG", export_jpeg_quality=88)
log("glb :", glb, "%.1f Mo" % (os.path.getsize(glb) / 1e6), "objets :", n_obj, "lumières :", LUMIERES)

# ----------------------------------------------------------------------------------------------
# Rendus de contrôle : coque et bati en contexte, miroir Y (D-026) pour comparer aux photos
# ----------------------------------------------------------------------------------------------
MIR = None
if os.environ.get("CHATEAU_SANS_RENDUS") != "1":
    activer(CTX)
    for f in ("coque.glb", "bati.glb"):
        bpy.ops.import_scene.gltf(filepath=os.path.join(EXPORT, f))
    activer(COL)
    MIR = bpy.data.objects.new("miroir_rendu", None)
    CTX.objects.link(MIR)
    MIR.scale = (1, -1, 1)
    for ob in list(COL.objects) + list(CTX.objects):
        if ob is not MIR and ob.parent is None:
            ob.parent = MIR

    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            SC.render.engine = eng
            break
        except TypeError:
            continue
    try:
        SC.eevee.taa_render_samples = 48
        SC.eevee.use_raytracing = True
        SC.eevee.use_shadows = True
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
        SC.view_settings.look = "AgX - Base Contrast"
    except TypeError:
        pass
    sol = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", "SUN"))
    sol.data.energy = 4.0
    sol.data.angle = math.radians(2)
    sol.rotation_euler = (math.radians(55), 0, math.radians(200))   # repère après miroir : soleil du sud-ouest
    CTX.objects.link(sol)
    # lumière d'appoint de chaque pièce (contexte seulement) : jour diffus réfléchi
    for pid in CH:
        poly = PIECES[pid]["polygone_interieur"]
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        li = bpy.data.lights.new("appoint_" + pid, "AREA")
        li.shape = "RECTANGLE"
        li.size, li.size_y = max(xs) - min(xs) - 0.6, max(ys) - min(ys) - 0.6
        li.energy = 30 * li.size * li.size_y
        li.color = (1.0, 0.96, 0.9)
        lo = bpy.data.objects.new("appoint_" + pid, li)
        lo.location = ((max(xs) + min(xs)) / 2, -(max(ys) + min(ys)) / 2, ZC - 0.6)
        CTX.objects.link(lo)


    def camera(nom, pos, cible, fov_v=68.0, ortho=None):
        """Caméra donnée en coordonnées D-003, passée au miroir (y → −y)."""
        cam = bpy.data.cameras.new(nom)
        cam.sensor_fit = "VERTICAL"
        cam.sensor_height = 24.0
        if ortho:
            cam.type = "ORTHO"
            cam.ortho_scale = ortho
        else:
            cam.lens = 12.0 / math.tan(math.radians(fov_v) / 2)
        cam.clip_start = 0.05
        cam.clip_end = 200
        co = bpy.data.objects.new(nom, cam)
        p = Vector((pos[0], -pos[1], pos[2]))
        c = Vector((cible[0], -cible[1], cible[2]))
        co.location = p
        co.rotation_euler = (c - p).to_track_quat("-Z", "Y").to_euler()
        CTX.objects.link(co)
        return co


    def rendre(cam, fichier, cacher=lambda n: False, res=None):
        for ob in list(COL.objects) + list(CTX.objects):
            if ob.type in ("MESH", "EMPTY"):
                ob.hide_render = ob.name.startswith("lib_") or cacher(ob)
        if res:
            SC.render.resolution_x, SC.render.resolution_y = res
        SC.camera = cam
        SC.render.filepath = os.path.join(RENDUS, fichier)
        t = time.time()
        bpy.ops.render.render(write_still=True)
        log("rendu", fichier, "%.1fs" % (time.time() - t))
        SC.render.resolution_x, SC.render.resolution_y = 900, 1200


    E = Z0 + 1.45
    VUES = [
        ("piece_chambres_ch1_p47.png", camera("cam_p47", (11.5, 6.15, E), (17.4, 5.2, E - 0.1), 70)),
        ("piece_chambres_ch1_p48.png", camera("cam_p48", (11.6, 5.4, E), (17.2, 8.6, E - 0.4), 70)),
        ("piece_chambres_ch1_p49.png", camera("cam_p49", (15.9, 4.5, E), (13.0, 8.85, E - 0.3), 70)),
        ("piece_chambres_ch2_p54.png", camera("cam_p54", (3.45, 7.05, E), (-3.7, 6.0, E - 0.2), 70)),
        ("piece_chambres_ch2_p53.png", camera("cam_p53", (1.6, 8.3, E - 0.2), (-0.2, 4.15, E), 70)),
        ("piece_chambres_ch3_p55.png", camera("cam_p55", (-4.8, 7.75, E), (-10.5, 3.7, E - 0.3), 72)),
        ("piece_chambres_ch3_p57.png", camera("cam_p57", (-6.6, 7.6, E), (-5.9, 1.1, E - 0.1), 72)),
    ]
    SEULE = os.environ.get("CHAMBRES_VUES")
    for f, cam in VUES:
        if SEULE and f not in SEULE.split(","):
            continue
        rendre(cam, f)
    # plan des trois chambres vu de dessus (plafonds retirés ; nord en haut après miroir)
    if not SEULE or "piece_chambres_plan.png" in SEULE:
        cam = camera("cam_plan", (3.5, 4.9, 30.0), (3.5, 4.9, 0.0), ortho=29.0)
        cam.rotation_euler = (0, 0, 0)

        def haut(ob):
            if ob.type != "MESH":
                return False
            if ob.name.startswith("plafond") or "_corniche" in ob.name or "rosace" in ob.name or "lustre" in ob.name:
                return True
            cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            return min(c.z for c in cs) > ZC - 0.5
        sol.data.energy = 2.0
        rendre(cam, "piece_chambres_plan.png", haut, res=(1600, 800))


# ----------------------------------------------------------------------------------------------
# Sauvegarde .blend (sans contexte ni miroir)
# ----------------------------------------------------------------------------------------------
for ob in list(COL.objects):
    if MIR is not None and ob.parent is MIR:
        mw = ob.matrix_world.copy()
        ob.parent = None
        ob.matrix_world = MIR.matrix_world.inverted() @ mw
for ob in list(CTX.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for ob in list(LIB.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
bpy.data.collections.remove(CTX)
bpy.data.collections.remove(LIB)
bpy.ops.outliner.orphans_purge(do_recursive=True)
try:
    bpy.ops.file.pack_all()
except RuntimeError as ex:
    log("pack_all :", ex)
blend = os.path.join(EXPORT, ID + ".blend")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
log("fin")

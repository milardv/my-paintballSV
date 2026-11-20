"""Composant P4.vestibule / P4.palier / P4.couloirs : décor et mobilier des circulations.

Pièces de coque.json : vestibule, escalier, petit_salon, passage_est, passage_ouest, couloir_est,
couloir_ouest, palier, vide_cage, galerie_est, galerie_ouest.

blender -b --factory-startup --python scripts/composants/piece_circulations.py
→ export/composants/piece_circulations.glb, .blend, rendus/piece_circulations_*.png

Repère D-003 (+X est, +Y sud, Z haut), indirect (D-026) : chaque élément est placé selon son orientation
réelle dans les coordonnées de coque.json. Les rendus comparés aux photos sont retournés horizontalement,
ce qui équivaut à rendre la scène passée au miroir Y avec la caméra miroir.
La coque et bati sont importés pour le contexte des rendus et ne sont pas exportés.
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
from mathutils import Vector, Matrix

T0 = time.time()
try:
    RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    RACINE = os.path.expanduser("~/IdeaProjects/chateau-saint-victor")
ID = "piece_circulations"
# CHATEAU_EXPORT / CHATEAU_COQUE : génération dans le repère de l'ancienne coque avant recalage (scripts/recaler_decors.py)
EXPORT = os.environ.get("CHATEAU_EXPORT") or os.path.join(RACINE, "export", "composants")
TEXDIR = os.path.join(EXPORT, ID + "_textures")
RENDUS = os.path.join(RACINE, "rendus")
ASSETS = os.path.join(RACINE, "assets")
shutil.rmtree(TEXDIR, ignore_errors=True)
for d in (EXPORT, TEXDIR, RENDUS):
    os.makedirs(d, exist_ok=True)
SANS_RENDU = os.environ.get("SANS_RENDU") == "1" or os.environ.get("CHATEAU_SANS_RENDUS") == "1"
SEULES = os.environ.get("VUES")


def log(*a):
    print("[%s %5.1fs]" % (ID, time.time() - T0), *a)
    sys.stdout.flush()


COQUE = json.load(open(os.environ.get("CHATEAU_COQUE") or os.path.join(RACINE, "travail", "coque.json")))
PIECES = {p["id"]: p for p in COQUE["pieces"]}
ESC = COQUE["escalier"]

Z_ETAGE = 5.35
Z_SOUS_DALLE = 5.05
Z_NAISSANCE = 10.60
Z_CLE = 12.00
Z_REPOS = ESC["repos"]["z"]
EP_REPOS = ESC["repos"]["epaisseur"]
N_C, H_C, G_C = 19, ESC["volee_centrale"]["hauteur"], ESC["volee_centrale"]["giron"]
N_R, H_R, G_R = 11, ESC["volees_retour"]["hauteur"], ESC["volees_retour"]["giron"]
Y_DEPART = ESC["volee_centrale"]["y_depart"]
Y_REPOS = ESC["volee_centrale"]["y_arrivee"]
Y_ARRIVEE = ESC["volees_retour"]["y_arrivee"]
X_VC = 1.25
X_VR0, X_VR1 = 2.0, 3.7
Y_CAGE_S = 3.65
Y_CAGE_N = -5.05
H_GC = 0.95

# ----------------------------------------------------------------------------------------------
# Géométrie 2D (reprise de coque.py)
# ----------------------------------------------------------------------------------------------


def aire(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def ccw(poly):
    return list(poly) if aire(poly) > 0 else list(reversed(poly))


def decaler(poly, d):
    """Décalage vers l'intérieur de d (polygone simple, sommets en onglet)."""
    poly = ccw(poly)
    n = len(poly)
    lignes = []
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        nx, ny = -dy / L, dx / L
        lignes.append(((x0 + nx * d, y0 + ny * d), (dx, dy)))
    out = []
    for i in range(n):
        (p, u), (q, v) = lignes[i - 1], lignes[i]
        den = u[0] * v[1] - u[1] * v[0]
        if abs(den) < 1e-9:
            out.append(q)
            continue
        t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
        out.append((p[0] + u[0] * t, p[1] + u[1] * t))
    return out


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ----------------------------------------------------------------------------------------------
# Scène
# ----------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
COL = bpy.data.collections.new(ID)
SC.collection.children.link(COL)
CTX = bpy.data.collections.new("contexte_rendu")
SC.collection.children.link(CTX)

# ----------------------------------------------------------------------------------------------
# Textures procédurales (numpy) : damas, soubassement, tapis, tapisserie, marbres, tableaux
# ----------------------------------------------------------------------------------------------
RNG = np.random.default_rng(7)


def sauver_px(nom, arr):
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = np.clip(arr if arr.ndim == 3 else arr[:, :, None], 0, 1)
    im = bpy.data.images.new(nom, w, h, alpha=False)
    im.pixels.foreach_set(rgba[::-1].ravel())   # ligne 0 du tableau = haut de l'image
    chemin = os.path.join(TEXDIR, nom + ".jpg")
    im.filepath_raw = chemin
    im.file_format = "JPEG"
    SC.render.image_settings.quality = 90
    im.save()
    bpy.data.images.remove(im)
    return chemin


def bruit(n, m, echelle, graine):
    """Bruit lisse (passe-bas FFT) normalisé, périodique, n lignes × m colonnes."""
    r = np.random.default_rng(graine).standard_normal((n, m))
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.fftfreq(m)[None, :]
    f = np.exp(-(fx ** 2 + fy ** 2) * (echelle ** 2))
    b = np.real(np.fft.ifft2(np.fft.fft2(r) * f))
    return (b - b.mean()) / (b.std() + 1e-9)


def lisse(d, w):
    return np.clip(0.5 - d / w, 0, 1)


def col(c):
    return np.array(c, dtype=np.float32)[None, None, :]


def tex_damas():
    """Papier peint damassé : grand motif floral blanc cassé sur fond taupe, symétrique (P20, P22, P42)."""
    n = 1024
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n
    m = np.zeros((n, n), np.float32)

    def bouquet(cx, cy, s):
        x = np.abs(((u - cx + 0.5) % 1.0) - 0.5) / s       # symétrie gauche-droite
        y = (((v - cy + 0.5) % 1.0) - 0.5) / s
        acc = np.zeros_like(u)
        # fleur centrale (rosace à 8 pétales)
        r = np.hypot(x, y + 0.05)
        th = np.arctan2(y + 0.05, x)
        acc = np.maximum(acc, lisse(r - 0.11 * (0.65 + 0.35 * np.abs(np.cos(4 * th))), 0.01))
        acc = np.where(r < 0.045, 0.3, acc)
        # feuilles en éventail au-dessus et au-dessous
        for (ax, ay, ang, L, W) in ((0.14, -0.14, 0.7, 0.16, 0.05), (0.22, 0.02, 0.15, 0.17, 0.05),
                                    (0.13, 0.17, -0.6, 0.15, 0.045), (0.05, -0.27, 1.4, 0.13, 0.04),
                                    (0.28, -0.2, 1.0, 0.1, 0.03), (0.3, 0.22, -0.9, 0.1, 0.03)):
            ca, sa = math.cos(ang), math.sin(ang)
            xr = (x - ax) * ca + (y - ay) * sa
            yr = -(x - ax) * sa + (y - ay) * ca
            acc = np.maximum(acc, lisse(np.hypot(xr / L, yr / W) - 1, 0.08))
            acc = np.where(np.hypot(xr / L, yr / (W * 0.25)) < 0.9, acc * 0.55, acc)   # nervure
        # tige et vase
        acc = np.maximum(acc, lisse(np.abs(x) - 0.012, 0.004) * ((y > 0.1) & (y < 0.33)))
        acc = np.maximum(acc, lisse(np.hypot(x / 0.09, (y - 0.36) / 0.05) - 1, 0.1))
        return acc

    m = np.maximum(m, bouquet(0.5, 0.42, 1.0))
    m = np.maximum(m, bouquet(0.0, 0.92, 0.55))
    # semis de petites fleurs
    for (cx, cy) in ((0.25, 0.75), (0.75, 0.75), (0.0, 0.42), (0.25, 0.15), (0.75, 0.15)):
        x = ((u - cx + 0.5) % 1.0) - 0.5
        y = ((v - cy + 0.5) % 1.0) - 0.5
        r = np.hypot(x, y)
        th = np.arctan2(y, x)
        m = np.maximum(m, lisse(r - 0.035 * (0.6 + 0.4 * np.abs(np.cos(2.5 * th))), 0.006) * 0.9)
    g = bruit(n, n, 120, 3)
    fond = col((0.80, 0.78, 0.69)) * (1 + 0.03 * g[:, :, None])     # crème (photos du 19/11)
    motif = col((0.60, 0.62, 0.54)) * (1 + 0.02 * g[:, :, None])    # feuillages gris-vert sauge
    return sauver_px("damas_col", fond * (1 - m[:, :, None]) + motif * m[:, :, None])


def tex_soubassement():
    """Soubassement d'un mètre : panneau mouluré blanc à filets céladon, plinthe (P36, P22)."""
    n = 1024
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n
    z = 1 - v                                   # z = 0 en bas de l'image
    c = np.ones((n, n, 3), np.float32) * col((0.84, 0.84, 0.81))
    cel = col((0.56, 0.64, 0.58))

    def cadre(x0, x1, z0, z1, w):
        dedans = (u > x0) & (u < x1) & (z > z0) & (z < z1)
        dd = np.minimum.reduce([u - x0, x1 - u, z - z0, z1 - z])
        return dedans & (dd < w)
    c = np.where(cadre(0.07, 0.93, 0.24, 0.86, 0.012)[:, :, None], cel, c)
    c = np.where(cadre(0.10, 0.90, 0.27, 0.83, 0.004)[:, :, None], cel * 1.15, c)
    ombre = cadre(0.0815, 0.9185, 0.2515, 0.8485, 0.004)
    c = np.where(ombre[:, :, None], c * 0.86, c)
    c = np.where((z < 0.14)[:, :, None], cel * 1.05, c)                 # plinthe céladon
    c = np.where(((z > 0.14) & (z < 0.155))[:, :, None], c * 0.8, c)
    c = np.where((z > 0.94)[:, :, None], col((0.88, 0.88, 0.85)), c)    # cimaise (dessus)
    c = np.where(((z > 0.935) & (z < 0.945))[:, :, None], cel, c)
    return sauver_px("soubassement_col", c * (1 + 0.015 * bruit(n, n, 60, 5)[:, :, None]))


def tex_tapis():
    """Tapis du vestibule (photo du 19/11) : champ cramoisi à rangées de médaillons octogonaux allongés (anneau or,
    fond bleu nuit, fleuron rouge et or en croix), étoiles d'or entre les médaillons ; bordure bleu nuit à cartouches
    ovales or et rouge entre deux galons."""
    h, w = 1536, 2048
    v, u = np.mgrid[0:h, 0:w].astype(np.float32)
    v /= h
    u /= w
    rouge = col((0.50, 0.035, 0.08))
    rouge2 = col((0.62, 0.07, 0.10))
    nuit = col((0.06, 0.06, 0.17))
    ocre = col((0.80, 0.60, 0.22))
    creme = col((0.85, 0.76, 0.52))
    c = np.ones((h, w, 3), np.float32) * rouge
    bx, by = 0.085, 0.11
    dist_bord = np.minimum.reduce([u / bx, (1 - u) / bx, v / by, (1 - v) / by])   # < 1 dans la bordure
    bord = dist_bord < 1
    # galons : bleu nuit à pois d'or, puis bande principale
    c = np.where((bord & (dist_bord < 0.18))[:, :, None], nuit, c)
    c = np.where((bord & (dist_bord >= 0.18) & (dist_bord < 0.24))[:, :, None], ocre, c)
    c = np.where((bord & (dist_bord >= 0.24) & (dist_bord < 0.86))[:, :, None], nuit, c)
    c = np.where((bord & (dist_bord >= 0.86) & (dist_bord < 0.93))[:, :, None], ocre, c)
    c = np.where((bord & (dist_bord >= 0.93))[:, :, None], rouge * 0.8, c)
    # cartouches ovales dans la bande principale
    lateral = (u < bx) | (u > 1 - bx)
    t = np.where(lateral, v * 11, u * 15)
    q = np.where(lateral, np.abs(np.where(u < 0.5, u, 1 - u) - bx * 0.55) / (bx * 0.30),
                 np.abs(np.where(v < 0.5, v, 1 - v) - by * 0.55) / (by * 0.30))
    oval = np.hypot(((t % 1) - 0.5) / 0.36, q)
    bande = bord & (dist_bord >= 0.24) & (dist_bord < 0.86)
    c = np.where((bande & (oval < 1.0))[:, :, None], ocre, c)
    c = np.where((bande & (oval < 0.78))[:, :, None], rouge2, c)
    c = np.where((bande & (oval < 0.40))[:, :, None], creme, c)
    c = np.where((bande & (oval < 0.20))[:, :, None], nuit, c)
    pois = bord & (dist_bord < 0.18) & (np.hypot(((np.where(lateral, v, u) * 60) % 1) - 0.5, 0) < 0.12)
    c = np.where(pois[:, :, None], ocre, c)
    # champ : 6 colonnes × 5 rangées de médaillons
    cu = (u - bx) / (1 - 2 * bx)
    cv = (v - by) / (1 - 2 * by)
    champ = ~bord
    gx = (cu * 6) % 1 - 0.5
    gy = (cv * 5) % 1 - 0.5
    ax, ay = np.abs(gx), np.abs(gy) * 0.85
    octo = np.maximum(np.maximum(ax, ay), (ax + ay) * 0.74)
    festons = octo + 0.012 * np.cos(np.arctan2(gy, gx) * 16)
    c = np.where((champ & (festons < 0.43))[:, :, None], ocre, c)
    c = np.where((champ & (festons < 0.40))[:, :, None], nuit, c)
    c = np.where((champ & (octo < 0.34) & (octo > 0.315))[:, :, None], ocre * 0.9, c)
    r = np.hypot(gx, gy * 0.85)
    th = np.arctan2(gy, gx)
    croix = (np.minimum(ax, ay) < 0.035 + 0.02 * np.cos(r * 40)) & (r < 0.27)
    c = np.where((champ & croix)[:, :, None], rouge2, c)
    fleur = r < 0.10 * (0.7 + 0.3 * np.abs(np.cos(4 * th)))
    c = np.where((champ & fleur)[:, :, None], ocre, c)
    c = np.where((champ & (r < 0.045))[:, :, None], rouge2, c)
    c = np.where((champ & (r < 0.018))[:, :, None], creme, c)
    # étoiles d'or entre les médaillons
    sx_, sy_ = np.abs(((cu * 6 + 0.5) % 1) - 0.5), np.abs(((cv * 5 + 0.5) % 1) - 0.5) * 0.85
    etoile = (sx_ + sy_ < 0.07) | ((np.minimum(sx_, sy_) < 0.008) & (np.maximum(sx_, sy_) < 0.10))
    c = np.where((champ & etoile & (octo > 0.45))[:, :, None], ocre, c)
    laine = 1 + 0.07 * bruit(h, w, 3, 9)[:, :, None] + 0.04 * bruit(h, w, 80, 10)[:, :, None]
    usure = 1 - 0.06 * np.clip(bruit(h, w, 200, 11), 0, None)[:, :, None]
    return sauver_px("tapis_vestibule_col", c * laine * usure)

def tex_tapisserie():
    """Relevé photo : scène et bordure photographiées, sans reconstitution."""
    return os.path.join(ASSETS, "oeuvres-releve-2026-11-19", "tapisserie_escalier_avec_bordure.png")


def tex_marbre(nom, base, veine, n=512, graine=1, contraste=0.25):
    b = bruit(n, n, 25, graine)
    b2 = bruit(n, n, 8, graine + 1)
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n
    ve = np.abs(np.sin((u * 3 + v * 2) * math.pi * 2 + b * 2.2)) ** 14
    c = col(base) * (1 + 0.06 * b2[:, :, None])
    c = c * (1 - contraste * ve[:, :, None]) + col(veine) * (contraste * ve[:, :, None])
    return sauver_px(nom, c)


def tex_tableau(nom, genre, w=512, h=384, graine=0):
    v, u = np.mgrid[0:h, 0:w].astype(np.float32)
    v /= h
    u /= w
    r = np.random.default_rng(graine)
    g = bruit(h, w, 10, graine + 20)[:, :, None]
    if genre == "marine":
        c = col((0.55, 0.68, 0.80)) * (1 - 0.4 * v[:, :, None]) + col((0.3, 0.2, 0.1)) * 0.2
        mer = v > 0.55
        c = np.where(mer[:, :, None], col((0.15, 0.32, 0.38)) * (1 + 0.2 * g), c)
        c = np.where(((np.abs(u - 0.62) < 0.05 - (0.48 - v) * 0.3) & (v > 0.28) & (v < 0.55))[:, :, None],
                     col((0.85, 0.82, 0.75)), c)
    elif genre == "chateau":
        c = col((0.35, 0.58, 0.88)) * (1 - 0.3 * v[:, :, None])
        c = np.where((v > 0.45)[:, :, None], col((0.22, 0.42, 0.18)) * (1 + 0.2 * g), c)
        bat = (u > 0.25) & (u < 0.75) & (v > 0.30) & (v < 0.52)
        c = np.where(bat[:, :, None], col((0.88, 0.85, 0.76)), c)
        c = np.where((bat & (((u * 40) % 1) < 0.35) & (v > 0.36) & (v < 0.48))[:, :, None], col((0.25, 0.28, 0.32)), c)
        c = np.where(((u > 0.24) & (u < 0.76) & (v > 0.27) & (v < 0.30))[:, :, None], col((0.55, 0.30, 0.22)), c)
        c = np.where((v > 0.68)[:, :, None], col((0.30, 0.48, 0.62)) * (1 + 0.1 * g), c)
    elif genre == "gravure":
        c = col((0.86, 0.82, 0.70)) * np.ones((h, w, 3))
        for _ in range(6):
            cx, cy = r.uniform(0.2, 0.8), r.uniform(0.2, 0.8)
            cc = col(tuple(r.uniform(0.2, 0.8, 3)))
            d = np.hypot((u - cx) / r.uniform(0.05, 0.15), (v - cy) / r.uniform(0.05, 0.2))
            c = np.where((d < 1)[:, :, None], cc, c)
    elif genre == "affiche":
        c = col((0.08, 0.07, 0.06)) * np.ones((h, w, 3))
        c = np.where(((v > 0.08) & (v < 0.2) & (u > 0.1) & (u < 0.9))[:, :, None], col((0.72, 0.58, 0.30)), c)
        c = np.where(((v > 0.3) & (v < 0.75) & (u > 0.12) & (u < 0.88))[:, :, None],
                     col((0.35, 0.28, 0.20)) * (1 + 0.4 * g), c)
        c = np.where((((v * 30) % 1 < 0.4) & (v > 0.8) & (v < 0.92) & (u > 0.15) & (u < 0.85))[:, :, None],
                     col((0.85, 0.80, 0.70)), c)
    else:   # paysage sombre
        c = col((0.25, 0.22, 0.16)) * (1 + 0.3 * g) * (1 - 0.3 * v[:, :, None])
        c = np.where((v < 0.4)[:, :, None], col((0.45, 0.48, 0.45)) * (1 + 0.2 * g), c)
    return sauver_px(nom, c * (1 + 0.04 * bruit(h, w, 2, graine + 30)[:, :, None]))


log("textures…")
TEX = dict(damas=tex_damas(), soubassement=tex_soubassement(), tapis=tex_tapis(), tapisserie=tex_tapisserie(),
           marbre_blanc=tex_marbre("marbre_blanc_col", (0.86, 0.86, 0.84), (0.45, 0.45, 0.48), graine=1, contraste=0.2),
           marbre_noir=tex_marbre("marbre_noir_col", (0.06, 0.06, 0.06), (0.55, 0.55, 0.55), graine=2, contraste=0.3),
           marbre_vert=tex_marbre("marbre_vert_col", (0.12, 0.20, 0.16), (0.55, 0.62, 0.55), graine=3, contraste=0.3),
           marbre_rouge=tex_marbre("marbre_rouge_col", (0.46, 0.10, 0.07), (0.70, 0.45, 0.35), graine=4, contraste=0.3,
                                   n=256),
           marine=tex_tableau("tableau_marine_col", "marine", graine=1),
           chateau=tex_tableau("tableau_chateau_col", "chateau", graine=2),
           gravure1=tex_tableau("tableau_gravure1_col", "gravure", 256, 320, graine=3),
           gravure2=tex_tableau("tableau_gravure2_col", "gravure", 256, 320, graine=4),
           sombre=tex_tableau("tableau_sombre_col", "sombre", 256, 384, graine=5),
           affiche=tex_tableau("affiche_concert_col", "affiche", 256, 360, graine=6))

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


M_DAMAS = materiau("damas", tex=TEX["damas"], uv=0.5, rugosite=0.75)
M_SOUB = materiau("soubassement", tex=TEX["soubassement"], uv=1.0, rugosite=0.45)
M_BLANC = materiau("stuc_blanc", (0.86, 0.86, 0.83), 0.55)
M_CELADON = materiau("filet_celadon", (0.52, 0.61, 0.55), 0.5)
M_GRISVERT = materiau("filet_gris_vert", (0.58, 0.64, 0.60), 0.6)
M_BANDE = materiau("marbre_rouge", tex=TEX["marbre_rouge"], uv=0.6, rugosite=0.2)
M_MARBRE_B = materiau("marbre_blanc", tex=TEX["marbre_blanc"], uv=0.8, rugosite=0.2)
M_MARBRE_N = materiau("marbre_noir", tex=TEX["marbre_noir"], uv=0.8, rugosite=0.15)
M_MARBRE_V = materiau("marbre_vert", tex=TEX["marbre_vert"], uv=0.8, rugosite=0.2)
M_PIERRE = materiau("pierre_blanche", (0.78, 0.76, 0.70), 0.7)
M_DORE = materiau("bois_dore", (0.80, 0.60, 0.26), 0.35, 0.9)
M_BRONZE = materiau("bronze", (0.45, 0.33, 0.16), 0.35, 1.0)
M_BRONZE_N = materiau("bronze_patine", (0.10, 0.08, 0.06), 0.45, 0.7)
M_LAITON = materiau("laiton", (0.78, 0.58, 0.25), 0.25, 1.0)
M_FER = materiau("fer_forge", (0.02, 0.02, 0.02), 0.45, 0.6)
M_ACIER = materiau("acier", (0.62, 0.63, 0.65), 0.25, 1.0)
M_MIROIR = materiau("miroir", (0.85, 0.87, 0.88), 0.03, 1.0, deux_faces=True)
M_VERRE = materiau("verre", (0.85, 0.88, 0.90), 0.05, alpha=0.25, deux_faces=True)
M_VERRE_JOUR = materiau("verre_oculus", (0.85, 0.90, 0.95), 0.1, emission=((0.9, 0.93, 1.0), 2.5), deux_faces=True)
M_AMPOULE = materiau("ampoule", (1.0, 0.9, 0.7), 0.3, emission=((1.0, 0.82, 0.55), 6.0))
M_BOUGIE = materiau("bougie", (0.93, 0.90, 0.82), 0.6)
M_NOYER = materiau("noyer", (0.25, 0.13, 0.06), 0.45)
M_CHENE = materiau("chene_fonce", (0.17, 0.085, 0.04), 0.5)
M_CHENE_CLAIR = materiau("chene_sculpte", (0.24, 0.13, 0.06), 0.55)
M_ZINC = materiau("zinc", (0.35, 0.36, 0.37), 0.5, 0.6)
M_ACAJOU = materiau("acajou", (0.30, 0.10, 0.05), 0.4)
M_MERISIER = materiau("merisier", (0.38, 0.18, 0.08), 0.4)
M_LAQUE_GRIS = materiau("laque_grise", (0.70, 0.71, 0.68), 0.45)
M_LAQUE_BLANC = materiau("laque_blanche", (0.86, 0.86, 0.82), 0.4)
M_LAQUE_NOIR = materiau("laque_noire", (0.03, 0.03, 0.03), 0.3)
M_PIN = materiau("pin", (0.62, 0.45, 0.25), 0.6)
M_VELOURS = materiau("velours_rouge", (0.40, 0.02, 0.05), 0.85, deux_faces=True)
M_VELOURS_SIEGE = materiau("velours_siege", (0.48, 0.06, 0.07), 0.9)
M_OLIVE = materiau("tissu_olive", (0.36, 0.36, 0.20), 0.9)
M_TISSU_GRIS = materiau("tissu_gris", (0.55, 0.56, 0.58), 0.9)
M_TISSU_CREME = materiau("tissu_creme", (0.80, 0.74, 0.62), 0.9)
M_TISSU_IMPR = materiau("tissu_imprime", (0.50, 0.55, 0.62), 0.9)
M_VOILE = materiau("voilage", (0.92, 0.90, 0.84), 0.8, alpha=0.7, deux_faces=True)
M_ABAT_JOUR = materiau("abat_jour", (0.90, 0.84, 0.70), 0.8, emission=((1.0, 0.85, 0.6), 0.6))
M_CERAM_BLEU = materiau("ceramique_bleue", (0.04, 0.07, 0.30), 0.2)
M_FAIENCE = materiau("faience", (0.90, 0.89, 0.85), 0.25)
M_TERRE = materiau("terre_cuite", (0.55, 0.30, 0.18), 0.8)
M_PAMPA = materiau("pampa", (0.80, 0.70, 0.50), 0.9)
M_FEUILLE = materiau("feuillage", (0.12, 0.28, 0.10), 0.7)
M_FLEUR = materiau("fleur_blanche", (0.92, 0.92, 0.88), 0.7)
M_ROTIN = materiau("rotin", (0.18, 0.12, 0.07), 0.8)
M_COCO = materiau("coco", (0.38, 0.26, 0.14), 1.0)
M_FONTE = materiau("fonte_peinte", (0.85, 0.85, 0.82), 0.5)
M_TAPIS = materiau("tapis_vestibule", tex=TEX["tapis"], rugosite=0.95, deux_faces=True)
M_TAPISSERIE = materiau("tapisserie", tex=TEX["tapisserie"], rugosite=0.95, deux_faces=True)
M_DRAPEAU_R = materiau("drapeau_rouge", (0.60, 0.03, 0.04), 0.8, deux_faces=True)
M_DRAPEAU_B = materiau("drapeau_blanc", (0.90, 0.90, 0.88), 0.8, deux_faces=True)
M_TOILE = {k: materiau("toile_" + k, tex=TEX[k], rugosite=0.6, deux_faces=True)
           for k in ("marine", "chateau", "gravure1", "gravure2", "sombre", "affiche")}
M_PLATRE = materiau("platre", (0.88, 0.88, 0.85), 0.8)

# ----------------------------------------------------------------------------------------------
# Constructeur de maillages (repris de coque.py) : UV projetées, ou explicites pour les images
# ----------------------------------------------------------------------------------------------


class Bld:
    def __init__(self, z0=0.0):
        self.bm = bmesh.new()
        self.mats = []
        self.uvfix = {}
        self.z0 = z0          # origine verticale des UV projetées (soubassement calé sur le sol)

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
            self.uvfix[f] = uv
        return f

    def quad(self, pts, m, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
        return self.face([self.v(p) for p in pts], m, uv)

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
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        self.solide(rect(x0, y0, x1, y1), z0, z1, m)

    def boite_c(self, cx, cy, cz, dx, dy, dz, m):
        """Boîte centrée en (cx, cy), de cz à cz + dz."""
        self.boite(cx - dx / 2, cy - dy / 2, cz, cx + dx / 2, cy + dy / 2, cz + dz, m)

    def hexa(self, pts8, m):
        """Hexaèdre : 4 sommets du bas puis 4 du haut (même ordre)."""
        vs = [self.v(p) for p in pts8]
        b, h = vs[:4], vs[4:]
        for i in range(4):
            j = (i + 1) % 4
            self.face([b[i], b[j], h[j], h[i]], m)
        self.face(list(reversed(b)), m)
        self.face(h, m)

    def poutre(self, p0, p1, larg, haut, m):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        if d.length < 1e-6:
            return
        hz = Vector((-d.y, d.x, 0))
        hz = hz.normalized() * larg / 2 if hz.length > 1e-9 else Vector((larg / 2, 0, 0))
        up = d.cross(hz).normalized() * haut / 2
        if up.z < 0:
            up = -up
        coins = [-hz - up, hz - up, hz + up, -hz + up]
        a = [self.v(p0 + c) for c in coins]
        b = [self.v(p1 + c) for c in coins]
        for i in range(4):
            j = (i + 1) % 4
            self.face([a[i], a[j], b[j], b[i]], m)
        self.face(list(reversed(a)), m)
        self.face(b, m)

    def polyligne(self, pts, larg, haut, m):
        for p, q in zip(pts[:-1], pts[1:]):
            self.poutre(p, q, larg, haut, m)

    def tube(self, p0, p1, r, m, n=8, r1=None):
        """Cylindre (tronc de cône si r1) d'axe p0 → p1."""
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0)
        if d.length < 1e-6:
            return
        d.normalize()
        a = d.orthogonal().normalized()
        bb = d.cross(a)
        r1 = r if r1 is None else r1
        ra = [self.v(p0 + (a * math.cos(2 * math.pi * k / n) + bb * math.sin(2 * math.pi * k / n)) * r) for k in range(n)]
        rb = [self.v(p1 + (a * math.cos(2 * math.pi * k / n) + bb * math.sin(2 * math.pi * k / n)) * r1) for k in range(n)]
        for k in range(n):
            j = (k + 1) % n
            self.face([ra[k], ra[j], rb[j], rb[k]], m)
        self.face(list(reversed(ra)), m)
        self.face(rb, m)

    def tour(self, prof, cx, cy, m, n=16, z0=0.0, mats=None):
        """Solide de révolution : prof = [(r, z)] de bas en haut, axe vertical en (cx, cy)."""
        anneaux = []
        for (r, z) in prof:
            if r < 1e-4:
                anneaux.append([self.v((cx, cy, z0 + z))])
            else:
                anneaux.append([self.v((cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n),
                                        z0 + z)) for k in range(n)])
        for i in range(len(anneaux) - 1):
            a, b = anneaux[i], anneaux[i + 1]
            mm = mats[i] if mats else m
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                for k in range(n):
                    self.face([a[0], b[k], b[(k + 1) % n]], mm)
            elif len(b) == 1:
                for k in range(n):
                    self.face([a[k], a[(k + 1) % n], b[0]], mm)
            else:
                for k in range(n):
                    j = (k + 1) % n
                    self.face([a[k], a[j], b[j], b[k]], mm)
        if len(anneaux[0]) > 1:
            self.face(list(reversed(anneaux[0])), m)
        if len(anneaux[-1]) > 1:
            self.face(anneaux[-1], mats[-1] if mats else m)

    def anneau(self, poly, d0, d1, z0, z1, m):
        """Couronne entre les décalages intérieurs d0 < d1 du polygone (corniches, bandes de sol)."""
        P = decaler(poly, d0)
        Q = decaler(poly, d1)
        n = len(P)
        pb = [self.v((x, y, z0)) for x, y in P]
        ph = [self.v((x, y, z1)) for x, y in P]
        qb = [self.v((x, y, z0)) for x, y in Q]
        qh = [self.v((x, y, z1)) for x, y in Q]
        for i in range(n):
            j = (i + 1) % n
            self.face([ph[i], ph[j], qh[j], qh[i]], m)
            self.face([pb[j], pb[i], qb[i], qb[j]], m)
            self.face([qb[i], qh[i], qh[j], qb[j]], m)
            self.face([pb[j], ph[j], ph[i], pb[i]], m)

    def objet(self, nom, loc=(0, 0, 0), rot=0.0, coll=None):
        bm = self.bm
        if not self.uvfix:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            if f in self.uvfix:
                for lp, uv in zip(f.loops, self.uvfix[f]):
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
                    uv = (co.y / s * (1 if n.x > 0 else -1), (co.z - self.z0) / s)
                else:
                    uv = (co.x / s * (-1 if n.y > 0 else 1), (co.z - self.z0) / s)
                lp[uvl].uv = uv
        me = bpy.data.meshes.new(nom)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(nom, me)
        ob.location = loc
        ob.rotation_euler = (0, 0, rot)
        (coll or COL).objects.link(ob)
        return ob


def copie(ob, nom, loc, rot=0.0, echelle=None):
    """Instance (maillage partagé) d'un objet modèle."""
    o = bpy.data.objects.new(nom, ob.data)
    o.location = loc
    o.rotation_euler = (0, 0, rot)
    if echelle:
        o.scale = echelle
    COL.objects.link(o)
    return o


MODELES = {}


def instance(cle, fabrique, nom, loc, rot=0.0, echelle=None):
    """Premier appel : construit le modèle (fabrique() → Bld en local) ; ensuite, instances."""
    if cle not in MODELES:
        ob = fabrique().objet(nom, loc=loc, rot=rot)
        if echelle:
            ob.scale = echelle
        MODELES[cle] = ob
        return ob
    return copie(MODELES[cle], nom, loc, rot, echelle)


def face_vers(dx, dy):
    """Rotation Z qui oriente la face avant locale (+Y) vers la direction (dx, dy)."""
    return math.atan2(-dx, dy)


# ----------------------------------------------------------------------------------------------
# Habillage des murs : soubassement, cimaise, papier peint, panneaux, en évitant les ouvertures
# ----------------------------------------------------------------------------------------------


def ouvertures_de(pid, extra=()):
    """Ouvertures (centre xy, largeur, bas, haut relatifs au sol) d'une pièce de coque.json."""
    p = PIECES[pid]
    out = []
    for o in p["portes"]:
        out.append(dict(c=(o["centre"][0], o["centre"][1]), l=o["largeur"], zb=0.0, zh=o["hauteur"],
                        arc=o["cintree"], nom=o["nom"]))
    out += list(extra)
    return out


def aretes(poly):
    poly = ccw(poly)
    n = len(poly)
    for i in range(n):
        p0, p1 = Vector((*poly[i], 0)), Vector((*poly[(i + 1) % n], 0))
        d = p1 - p0
        L = d.length
        u = d / L
        nn = Vector((-u.y, u.x, 0))      # normale intérieure
        yield p0, p1, u, nn, L


def ouv_sur_arete(p0, u, nn, L, ouvs, tol=0.45):
    res = []
    for o in ouvs:
        d = Vector((o["c"][0], o["c"][1], 0)) - p0
        s = d.dot(u)
        if abs(d.dot(nn)) < tol and -0.05 < s < L + 0.05:
            res.append((s - o["l"] / 2, s + o["l"] / 2, o["zb"], o["zh"], o))
    return res


def morceaux(L, ouvs, za, zb):
    """Rectangles (s0, s1, z0, z1) d'une couche [za, zb] autour des ouvertures."""
    cuts = sorted([(max(0, a), min(L, b), z0, z1) for a, b, z0, z1, _ in ouvs if b > 0 and a < L])
    res = []
    s = 0.0
    for a, b, z0, z1 in cuts:
        if a > s + 1e-3:
            res.append((s, a, za, zb))
        # au droit de l'ouverture : ce qui reste au-dessous et au-dessus
        if z0 > za + 1e-3:
            res.append((a, b, za, min(zb, z0)))
        if z1 < zb - 1e-3:
            res.append((a, b, max(za, z1), zb))
        s = max(s, b)
    if s < L - 1e-3:
        res.append((s, L, za, zb))
    return [r for r in res if r[1] - r[0] > 1e-3 and r[3] - r[2] > 1e-3]


def plaque(b, p0, u, nn, s0, s1, z0, zt0, zt1, off, ep, m):
    """Plaque contre le mur : de s0 à s1, bas z0, haut zt0 → zt1 (rampant), épaisseur ep à off du nu."""
    a0 = p0 + u * s0 + nn * off
    a1 = p0 + u * s1 + nn * off
    c0 = a0 + nn * ep
    c1 = a1 + nn * ep
    pts = [(a0.x, a0.y, z0), (a1.x, a1.y, z0), (c1.x, c1.y, z0), (c0.x, c0.y, z0),
           (a0.x, a0.y, zt0), (a1.x, a1.y, zt1), (c1.x, c1.y, zt1), (c0.x, c0.y, zt0)]
    b.hexa(pts, m)


def habiller(nom, poly, zsol, ouvs, couches, ztop=None, sauf=(), pas=0.6, bld=None):
    """couches : [(z0, z1, mat, off, ep)] relatives au sol ; ztop(x, y) : plafond rampant éventuel ;
    sauf : indices d'arêtes (polygone ccw) à ne pas habiller."""
    b = bld or Bld(z0=zsol)
    for i, (p0, p1, u, nn, L) in enumerate(aretes(poly)):
        if i in sauf:
            continue
        ov = ouv_sur_arete(p0, u, nn, L, ouvs)
        for (za, zb, m, off, ep) in couches:
            for s0, s1, z0, z1 in morceaux(L, ov, za, zb):
                k = max(1, int(math.ceil((s1 - s0) / pas))) if ztop else 1
                for j in range(k):
                    t0 = s0 + (s1 - s0) * j / k
                    t1 = s0 + (s1 - s0) * (j + 1) / k
                    h0 = h1 = zsol + z1
                    if ztop:
                        q0, q1 = p0 + u * t0, p0 + u * t1
                        h0 = min(h0, ztop(q0.x, q0.y) - 0.01)
                        h1 = min(h1, ztop(q1.x, q1.y) - 0.01)
                        if h0 <= zsol + z0 + 0.02 and h1 <= zsol + z0 + 0.02:
                            continue
                        h0, h1 = max(h0, zsol + z0 + 0.02), max(h1, zsol + z0 + 0.02)
                    plaque(b, p0, u, nn, t0, t1, zsol + z0, h0, h1, off, ep, m)
    if bld is None:
        return b.objet(nom)
    return None


def chambranles(nom, poly, zsol, ouvs, larg=0.14, ep=0.035, dessus=None, sauf_noms=(), bld=None):
    """Chambranles moulurés (montants et traverse) autour des portes, côté pièce ; dessus-de-porte."""
    b = bld or Bld(z0=zsol)
    for p0, p1, u, nn, L in aretes(poly):
        for s0, s1, zb, zh, o in ouv_sur_arete(p0, u, nn, L, ouvs):
            if o.get("nom") in sauf_noms or o.get("arc") or str(o.get("nom", "")).startswith("baie"):
                continue
            for s in (s0 - larg, s1):
                plaque(b, p0, u, nn, s, s + larg, zsol, zsol + zh + larg, zsol + zh + larg, 0, ep, M_BLANC)
                plaque(b, p0, u, nn, s + 0.03, s + larg - 0.03, zsol, zsol + zh + larg - 0.03,
                       zsol + zh + larg - 0.03, ep, 0.008, M_CELADON)
            plaque(b, p0, u, nn, s0, s1, zsol + zh, zsol + zh + larg, zsol + zh + larg, 0, ep, M_BLANC)
            if dessus and zh + larg + 0.25 < dessus[0]:
                # dessus-de-porte : panneau à filet céladon et corniche à ressauts (P22, P36)
                h = min(dessus[1], dessus[0] - zh - larg - 0.1)
                zc = zsol + zh + larg
                plaque(b, p0, u, nn, s0 - larg, s1 + larg, zc, zc + h, zc + h, 0, 0.02, M_BLANC)
                plaque(b, p0, u, nn, s0 + 0.08, s1 - 0.08, zc + 0.12, zc + h - 0.18, zc + h - 0.18, 0.02, 0.006,
                       M_CELADON)
                plaque(b, p0, u, nn, s0 + 0.11, s1 - 0.11, zc + 0.15, zc + h - 0.21, zc + h - 0.21, 0.02, 0.009,
                       M_BLANC)
                plaque(b, p0, u, nn, s0 - larg - 0.06, s1 + larg + 0.06, zc + h, zc + h + 0.06, zc + h + 0.06, 0,
                       0.09, M_BLANC)
                plaque(b, p0, u, nn, s0 - larg - 0.1, s1 + larg + 0.1, zc + h + 0.06, zc + h + 0.12,
                       zc + h + 0.12, 0, 0.14, M_BLANC)
    if bld is None:
        return b.objet(nom)
    return None


def corniche(b, poly, z_plafond, h=0.32, saillie=0.24, m=None):
    """Corniche à ressauts sous le plafond (frise et larmier), en couronne sur le polygone."""
    m = m or M_BLANC
    for (a, c, sl) in ((0.0, 0.18, 0.05), (0.18, 0.38, 0.09), (0.38, 0.55, 0.13), (0.55, 0.75, 0.18),
                       (0.75, 0.88, 0.22), (0.88, 1.0, saillie)):
        b.anneau(poly, -0.005, sl, z_plafond - h + a * h, z_plafond - h + c * h - (0.003 if c == 1.0 else 0.0), m)


def bandes_sol(b, polys_anneaux, rects_pleins, zsol):
    """Bandes de marbre rouge posées sur le dallage (tapis de pierre)."""
    for poly, d, w in polys_anneaux:
        b.anneau(poly, d, d + w, zsol + 0.001, zsol + 0.006, M_BANDE)
    for (x0, y0, x1, y1) in rects_pleins:
        b.boite(x0, y0, zsol + 0.001, x1, y1, zsol + 0.006, M_BANDE)


# ----------------------------------------------------------------------------------------------
# Modèles de mobilier et d'objets (repère local, face avant vers +Y, sol à z = 0)
# ----------------------------------------------------------------------------------------------


def m_fauteuil(tissu, bois, bras=True, larg=0.62, prof=0.56, h_dos=0.95):
    """Fauteuil (ou chaise si bras=False) Louis XV à dossier médaillon, pieds cambrés (P25, P26, P22)."""
    b = Bld()
    hx, hy = larg / 2, prof / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (hx - 0.05), sy * (hy - 0.05)
            # pied cambré : deux segments, le genou vers l'extérieur
            b.poutre((x + sx * 0.03, y + sy * 0.03, 0.0), (x + sx * 0.0, y + sy * 0.0, 0.18), 0.035, 0.035, bois)
            b.poutre((x, y, 0.18), (x - sx * 0.01, y - sy * 0.01, 0.38), 0.045, 0.045, bois)
    b.boite(-hx, -hy, 0.36, hx, hy, 0.42, bois)                     # ceinture
    b.boite(-hx + 0.03, -hy + 0.02, 0.42, hx - 0.03, hy - 0.01, 0.48, tissu)
    # dossier médaillon : cadre ovale incliné, garniture
    cz, rz, rx = 0.42 + (h_dos - 0.42) / 2 + 0.03, (h_dos - 0.47) / 2, hx - 0.06
    yb = -hy + 0.03
    n = 18
    pts = []
    for k in range(n + 1):
        a = 2 * math.pi * k / n
        z = cz + rz * math.sin(a)
        pts.append((rx * math.cos(a), yb - 0.06 * (z - 0.45) / 0.5, z))
    b.polyligne(pts, 0.04, 0.035, bois)
    centre = b.v((0, yb - 0.06 * (cz - 0.45) / 0.5 + 0.012, cz))
    vs = [b.v((p[0] * 0.92, p[1] + 0.012, cz + (p[2] - cz) * 0.92)) for p in pts[:-1]]
    for k in range(n):
        b.face([centre, vs[k], vs[(k + 1) % n]], tissu)
    for sx in (-1, 1):                                               # montants du dossier
        b.poutre((sx * (hx - 0.05), -hy + 0.04, 0.42), (sx * rx * 0.85, yb - 0.01, cz - rz * 0.6), 0.035, 0.03, bois)
    if bras:
        for sx in (-1, 1):
            x = sx * (hx - 0.02)
            b.poutre((x, -hy + 0.08, 0.68), (x, hy - 0.06, 0.64), 0.05, 0.04, bois)
            b.boite(x - 0.03, -hy + 0.12, 0.66, x + 0.03, hy - 0.16, 0.70, tissu)
            b.poutre((x, hy - 0.08, 0.42), (x, hy - 0.04, 0.64), 0.035, 0.035, bois)
    return b


def m_console_demilune(plateau, pietement, larg=1.1, prof=0.45, h=0.85, dore=True):
    """Console demi-lune : plateau de marbre, ceinture, 3 ou 4 pieds fuselés (P20, P22, P42)."""
    b = Bld()
    n = 16
    poly = [(larg / 2 * math.cos(math.pi * k / n), -prof / 2 + prof * math.sin(math.pi * k / n)) for k in range(n + 1)]
    b.solide(poly, h - 0.035, h, plateau)
    ce = [(x * 0.95, -prof / 2 + (y + prof / 2) * 0.92) for x, y in poly]
    b.solide(ce, h - 0.14, h - 0.035, pietement)
    for a in (0.18, 0.5, 0.82):
        x, y = larg / 2 * 0.85 * math.cos(math.pi * a), -prof / 2 + prof * 0.82 * math.sin(math.pi * a)
        b.tube((x, y, 0.0), (x, y, h - 0.14), 0.022, pietement, 8, r1=0.035)
        b.tour([(0.03, 0.0), (0.045, 0.03), (0.0, 0.05)], x, y, pietement, n=8)
    for x in (-larg / 2 * 0.8, larg / 2 * 0.8):
        b.tube((x, -prof / 2 + 0.04, 0.0), (x, -prof / 2 + 0.04, h - 0.14), 0.02, pietement, 8, r1=0.032)
    if dore:   # entretoise et urne
        b.poutre((-larg * 0.35, -prof / 2 + 0.06, 0.18), (larg * 0.35, -prof / 2 + 0.06, 0.18), 0.03, 0.03, pietement)
        b.poutre((0, -prof / 2 + 0.06, 0.18), (0, prof * 0.25, 0.18), 0.03, 0.03, pietement)
        b.tour([(0.0, 0.18), (0.06, 0.22), (0.08, 0.30), (0.04, 0.38), (0.0, 0.40)], 0, prof * 0.2, pietement, n=10)
    return b


def m_console_galbee(plateau, bois, larg=1.0, prof=0.45, h=0.85):
    """Console galbée Louis-Philippe : façade en arbalète, pieds en console (P23, P24)."""
    b = Bld()
    n = 10
    avant = [(-larg / 2 + larg * k / n, prof / 2 - 0.06 * math.sin(math.pi * k / n) ** 2 + 0.04) for k in range(n + 1)]
    poly = [(larg / 2, -prof / 2)] + avant[::-1] + [(-larg / 2, -prof / 2)]
    poly = [(-larg / 2, -prof / 2), (larg / 2, -prof / 2)] + avant[::-1]
    b.solide(poly, h - 0.03, h, plateau)
    b.solide([(x * 0.97, y * 0.95) for x, y in poly], h - 0.16, h - 0.03, bois)
    for sx in (-1, 1):
        b.polyligne([(sx * larg * 0.44, prof / 2 - 0.02, h - 0.16), (sx * larg * 0.40, prof / 2 + 0.03, h - 0.45),
                     (sx * larg * 0.45, prof / 2 - 0.05, 0.15), (sx * larg * 0.44, prof / 2 - 0.02, 0.0)], 0.05, 0.05, bois)
        b.poutre((sx * larg * 0.44, -prof / 2 + 0.04, h - 0.16), (sx * larg * 0.44, -prof / 2 + 0.04, 0.0), 0.04, 0.04, bois)
    b.boite(-larg * 0.44, -prof / 2 + 0.03, 0.08, larg * 0.44, prof / 2 - 0.05, 0.11, bois)
    return b


def m_miroir(larg, haut, fronton=False):
    """Miroir à cadre doré, accroché : face vers +Y, dos à y = 0."""
    b = Bld()
    c = 0.07
    b.boite(-larg / 2, 0, 0, larg / 2, 0.05, c, M_DORE)
    b.boite(-larg / 2, 0, haut - c, larg / 2, 0.05, haut, M_DORE)
    b.boite(-larg / 2, 0, 0, -larg / 2 + c, 0.05, haut, M_DORE)
    b.boite(larg / 2 - c, 0, 0, larg / 2, 0.05, haut, M_DORE)
    b.quad([(-larg / 2 + c, 0.03, c), (larg / 2 - c, 0.03, c), (larg / 2 - c, 0.03, haut - c), (-larg / 2 + c, 0.03, haut - c)],
           M_MIROIR)
    if fronton:   # fronton sculpté (coquille et feuillages simplifiés)
        b.solide([(-larg / 2, 0), (larg / 2, 0), (larg / 2, 0.05), (-larg / 2, 0.05)], haut, haut + 0.02, M_DORE)
        pts = [(-larg * 0.4, 0.02, haut), (-larg * 0.2, 0.02, haut + 0.12), (0, 0.02, haut + 0.22),
               (larg * 0.2, 0.02, haut + 0.12), (larg * 0.4, 0.02, haut)]
        b.polyligne(pts, 0.05, 0.04, M_DORE)
        b.tour([(0.0, 0), (0.07, 0.05), (0.05, 0.12), (0.0, 0.15)], 0, 0.03, M_DORE, n=8, z0=haut + 0.12)
    return b


def m_cadre(larg, haut, toile, prof=0.04, c=0.06, mat_cadre=None):
    b = Bld()
    mc = mat_cadre or M_DORE
    b.boite(-larg / 2, 0, 0, larg / 2, prof, c, mc)
    b.boite(-larg / 2, 0, haut - c, larg / 2, prof, haut, mc)
    b.boite(-larg / 2, 0, 0, -larg / 2 + c, prof, haut, mc)
    b.boite(larg / 2 - c, 0, 0, larg / 2, prof, haut, mc)
    b.quad([(-larg / 2 + c, prof * 0.5, c), (larg / 2 - c, prof * 0.5, c), (larg / 2 - c, prof * 0.5, haut - c),
            (-larg / 2 + c, prof * 0.5, haut - c)], toile)
    return b


def m_candelabre(bras=4, h=0.7, figure=True):
    """Statuette-candélabre en bronze (page portant des lumières) ou candélabre à bobèches."""
    b = Bld()
    b.boite(-0.08, -0.08, 0, 0.08, 0.08, 0.08, M_BRONZE_N)
    if figure:
        b.tour([(0.05, 0.08), (0.06, 0.25), (0.04, 0.42), (0.045, 0.48), (0.0, 0.53)], 0, 0, M_BRONZE_N, n=10)
        b.tour([(0.0, 0.53), (0.035, 0.56), (0.03, 0.6), (0.0, 0.62)], 0, 0, M_BRONZE_N, n=10)
    else:
        b.tour([(0.02, 0.08), (0.025, 0.4), (0.0, 0.42)], 0, 0, M_DORE, n=8)
    z = h - 0.12
    b.tube((0, 0, 0.5 if figure else 0.3), (0, 0, z), 0.012, M_DORE, 6)
    for k in range(bras):
        a = 2 * math.pi * k / bras
        x, y = 0.14 * math.cos(a), 0.14 * math.sin(a)
        b.polyligne([(0, 0, z - 0.06), (x * 0.6, y * 0.6, z - 0.08), (x, y, z)], 0.015, 0.015, M_DORE)
        b.tour([(0.025, z), (0.025, z + 0.015)], x, y, M_DORE, n=8)
        b.tube((x, y, z + 0.015), (x, y, z + 0.11), 0.01, M_BOUGIE, 6)
        b.tour([(0.0, z + 0.11), (0.008, z + 0.125), (0.0, z + 0.14)], x, y, M_AMPOULE, n=6)
    return b


def m_lampe(pied=M_CERAM_BLEU, h=0.65):
    b = Bld()
    b.tour([(0.06, 0), (0.09, 0.05), (0.12, 0.18), (0.08, 0.32), (0.035, 0.38), (0.03, 0.40), (0.0, 0.41)], 0, 0,
           pied, n=14)
    b.tube((0, 0, 0.4), (0, 0, h - 0.15), 0.008, M_LAITON, 6)
    b.tour([(0.17, h - 0.22), (0.10, h), (0.0, h + 0.001)], 0, 0, M_ABAT_JOUR, n=16)
    return b


def m_vase_fleurs(h=0.6, pot=M_ACIER, fleur=M_FLEUR, larg=0.35):
    b = Bld()
    b.tour([(0.05, 0), (0.09, 0.08), (0.1, 0.2), (0.05, 0.3), (0.06, 0.34), (0.0, 0.34)], 0, 0, pot, n=12)
    r = np.random.default_rng(int(h * 100))
    for k in range(12):
        a = r.uniform(0, 2 * math.pi)
        d = r.uniform(0.05, larg / 2)
        tete = (d * math.cos(a), d * math.sin(a), h - r.uniform(0, 0.15))
        b.poutre((0, 0, 0.3), tete, 0.01, 0.01, M_FEUILLE)
        b.tour([(0.0, -0.02), (0.05, 0.0), (0.04, 0.03), (0.0, 0.04)], tete[0], tete[1], fleur, n=6, z0=tete[2])
        b.poutre((tete[0] * 0.6, tete[1] * 0.6, h * 0.65), (tete[0] * 0.9 + 0.06, tete[1] * 0.9, h * 0.6), 0.05, 0.005,
                 M_FEUILLE)
    return b


def m_pampas(h=1.6):
    """Amphore en terre cuite sur trépied et herbes de la pampa séchées (P14, P16)."""
    b = Bld()
    for k in range(3):
        a = 2 * math.pi * k / 3
        b.poutre((0.2 * math.cos(a), 0.2 * math.sin(a), 0), (0.12 * math.cos(a), 0.12 * math.sin(a), 0.35), 0.015, 0.015, M_FER)
    b.tour([(0.0, 0.15), (0.08, 0.2), (0.18, 0.4), (0.2, 0.55), (0.12, 0.75), (0.07, 0.82), (0.09, 0.86), (0.0, 0.86)],
           0, 0, M_TERRE, n=14)
    r = np.random.default_rng(5)
    for k in range(16):
        a = r.uniform(0, 2 * math.pi)
        d = r.uniform(0.1, 0.35)
        hh = r.uniform(h * 0.8, h)
        top = (d * math.cos(a), d * math.sin(a), hh)
        b.poutre((0, 0, 0.8), (top[0] * 0.8, top[1] * 0.8, hh - 0.25), 0.008, 0.008, M_PAMPA)
        b.tube((top[0] * 0.8, top[1] * 0.8, hh - 0.25), top, 0.03, M_PAMPA, 6, r1=0.005)
    return b


def m_rideau(larg, haut, plis=7, ampl=0.06, mat=None):
    """Rideau plissé : surface ondulée dans le plan (x, z), plis en y ; tombe de z = haut à 0."""
    b = Bld()
    mat = mat or M_VELOURS
    n = plis * 6
    bas = [b.v((larg * k / n - larg / 2, ampl * math.sin(2 * math.pi * plis * k / n) + ampl, 0.0)) for k in range(n + 1)]
    haut_v = [b.v((larg * 0.85 * k / n - larg * 0.85 / 2, ampl * 0.6 * math.sin(2 * math.pi * plis * k / n) + ampl,
                   haut)) for k in range(n + 1)]
    milieu = [b.v((larg * 0.75 * k / n - larg * 0.75 / 2, ampl * 0.8 * math.sin(2 * math.pi * plis * k / n) + ampl,
                   haut * 0.45)) for k in range(n + 1)]       # embrasse
    for k in range(n):
        b.face([bas[k], bas[k + 1], milieu[k + 1], milieu[k]], mat)
        b.face([milieu[k], milieu[k + 1], haut_v[k + 1], haut_v[k]], mat)
    return b


def m_fusil():
    """Fusil ancien à silex accroché à plat contre le mur (dos à y = 0), crosse en bas."""
    b = Bld()
    b.hexa([(-0.03, 0, 0), (0.05, 0, 0), (0.05, 0.04, 0), (-0.03, 0.04, 0),
            (-0.015, 0, 0.35), (0.02, 0, 0.35), (0.02, 0.04, 0.35), (-0.015, 0.04, 0.35)], M_NOYER)
    b.boite(-0.013, 0.005, 0.35, 0.017, 0.035, 1.05, M_NOYER)
    b.tube((0.0, 0.02, 0.4), (0.0, 0.02, 1.48), 0.009, M_ACIER, 6)
    b.boite(0.015, 0.0, 0.33, 0.04, 0.04, 0.42, M_ACIER)
    return b


def m_appliqe(bras=2):
    """Applique bronze doré à bras et bougies électriques (P04, P17) : dos contre le mur (y = 0)."""
    b = Bld()
    b.hexa([(-0.05, 0, -0.18), (0.05, 0, -0.18), (0.05, 0.03, -0.18), (-0.05, 0.03, -0.18),
            (-0.04, 0, 0.12), (0.04, 0, 0.12), (0.04, 0.03, 0.12), (-0.04, 0.03, 0.12)], M_BRONZE)
    for k in range(bras):
        x = (k - (bras - 1) / 2) * 0.22
        b.polyligne([(0, 0.03, -0.05), (x * 0.5, 0.12, -0.1), (x, 0.18, -0.02), (x, 0.18, 0.04)], 0.015, 0.015, M_BRONZE)
        b.tour([(0.03, 0.04), (0.02, 0.06)], x, 0.18, M_BRONZE, n=8)
        b.tube((x, 0.18, 0.06), (x, 0.18, 0.16), 0.011, M_BOUGIE, 6)
        b.tour([(0.0, 0.16), (0.01, 0.175), (0.0, 0.2)], x, 0.18, M_AMPOULE, n=6)
    return b


def m_lustre(n_bras=10, r=0.55, chaine=0.9):
    """Lustre bronze doré à deux couronnes (photo du vestibule) : fût balustre, bras en S à feuilles et contre-volutes,
    bobèches, bougies et flammes ; origine au plafond."""
    b = Bld()
    b.tour([(0.0, 0.0), (0.12, 0.0), (0.12, -0.02), (0.09, -0.05), (0.04, -0.09), (0.0, -0.10)], 0, 0, M_DORE, n=16)
    for k in range(int((chaine - 0.1) / 0.055)):
        z = -0.10 - k * 0.055
        if k % 2:
            courbe(b, [(0.0, -0.018, z), (0.0, -0.018, z - 0.05), (0.0, 0.018, z - 0.05), (0.0, 0.018, z), (0.0, -0.018, z)],
                   0.005, M_DORE, 5)
        else:
            courbe(b, [(-0.018, 0.0, z), (-0.018, 0.0, z - 0.05), (0.018, 0.0, z - 0.05), (0.018, 0.0, z), (-0.018, 0.0, z)],
                   0.005, M_DORE, 5)
    z0 = -chaine
    prof = [(0.0, 0.0), (0.035, -0.01), (0.07, -0.05), (0.045, -0.10), (0.11, -0.18), (0.13, -0.24), (0.08, -0.32),
            (0.05, -0.38), (0.10, -0.42), (0.10, -0.46), (0.06, -0.50), (0.12, -0.56), (0.17, -0.62), (0.17, -0.66),
            (0.11, -0.70), (0.05, -0.76), (0.08, -0.82), (0.05, -0.90), (0.02, -0.98), (0.0, -1.02)]
    b.tour(prof, 0, 0, M_DORE, n=16, z0=z0)
    # couronne de feuilles en haut du fût
    for k in range(10):
        a = 2 * math.pi * k / 10
        b.poutre((0.05 * math.cos(a), 0.05 * math.sin(a), z0 - 0.06),
                 (0.16 * math.cos(a), 0.16 * math.sin(a), z0 + 0.02), 0.045, 0.01, M_DORE)

    def bras(a, r_bras, z_hub, r_hub, monte):
        ca, sa = math.cos(a), math.sin(a)
        P = lambda rr, zz: (rr * ca, rr * sa, zz)
        pts = bezier(P(r_hub, z_hub), P(r_hub + r_bras * 0.45, z_hub - 0.16), P(r_bras * 0.95, z_hub - 0.14),
                     P(r_bras, z_hub + monte), 12)
        courbe(b, pts, 0.016, M_DORE, 7, r_fin=0.012)
        # contre-volute sous le bras et feuille d'acanthe
        cv = (r_hub + r_bras * 0.35, z_hub - 0.12)
        courbe(b, volute(P(*cv), (ca, sa, 0), (0, 0, 1), 0.05), 0.007, M_DORE, 5)
        mid = pts[len(pts) // 2]
        b.poutre(mid, (mid[0] + ca * 0.06, mid[1] + sa * 0.06, mid[2] + 0.06), 0.04, 0.008, M_DORE)
        x, y, z = pts[-1]
        b.tour([(0.0, -0.03), (0.02, -0.02), (0.05, 0.0), (0.055, 0.015), (0.04, 0.02), (0.015, 0.02)], x, y, M_DORE,
               n=12, z0=z)
        b.tube((x, y, z + 0.02), (x, y, z + 0.14), 0.013, M_BOUGIE, 8)
        b.tour([(0.0, 0.0), (0.014, 0.012), (0.017, 0.03), (0.008, 0.055), (0.0, 0.07)], x, y, M_AMPOULE, n=8,
               z0=z + 0.14)

    for k in range(n_bras):
        bras(2 * math.pi * k / n_bras, r, z0 - 0.64, 0.15, 0.12)
    for k in range(n_bras // 2 + 1):
        bras(2 * math.pi * (k + 0.5) / (n_bras // 2 + 1), r * 0.55, z0 - 0.42, 0.09, 0.14)
    return b


def m_lanterne(h=0.55, chaine=0.8):
    """Lanterne de couloir à cage dorée hexagonale (P22, W08) ; origine au plafond."""
    b = Bld()
    b.tube((0, 0, 0), (0, 0, -chaine), 0.006, M_LAITON, 6)
    zt, zb = -chaine, -chaine - h
    n = 6
    r = 0.14
    pts_h = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    for k in range(n):
        x, y = pts_h[k]
        b.poutre((x, y, zb + 0.05), (x, y, zt - 0.05), 0.012, 0.012, M_LAITON)
    b.tour([(0.0, zt - 0.05), (r + 0.02, zt - 0.05), (0.06, zt), (0.0, zt + 0.02)], 0, 0, M_LAITON, n=6)
    b.tour([(0.0, zb - 0.06), (0.04, zb - 0.04), (r + 0.01, zb + 0.05), (0.0, zb + 0.05)], 0, 0, M_LAITON, n=6)
    b.tour([(r * 0.97, zb + 0.05), (r * 0.97, zt - 0.05)], 0, 0, M_VERRE, n=6)
    b.tour([(0.0, zb + 0.1), (0.03, zb + 0.18), (0.0, zb + 0.28)], 0, 0, M_AMPOULE, n=8)
    return b


def courbe(b, pts, r, m, n=6, r_fin=None):
    """Tube suivant une polyligne 3D, rayon variant de r à r_fin (bras de lustre, patères, volutes)."""
    r_fin = r if r_fin is None else r_fin
    for i, (p, q) in enumerate(zip(pts[:-1], pts[1:])):
        ra = r + (r_fin - r) * i / max(1, len(pts) - 1)
        rb = r + (r_fin - r) * (i + 1) / max(1, len(pts) - 1)
        b.tube(p, q, ra, m, n, r1=rb)


def bezier(p0, p1, p2, p3, n=10):
    out = []
    for k in range(n + 1):
        t = k / n
        u = 1 - t
        out.append(tuple(u ** 3 * a + 3 * u * u * t * bb + 3 * u * t * t * c + t ** 3 * d
                         for a, bb, c, d in zip(p0, p1, p2, p3)))
    return out


def volute(centre, axe_u, axe_v, r0, tours=1.6, n=24):
    """Spirale plane (enroulement vers le centre) dans le plan (axe_u, axe_v)."""
    cx, cy, cz = centre
    out = []
    for k in range(n + 1):
        t = k / n
        a = 2 * math.pi * tours * t
        r = r0 * (1 - 0.8 * t)
        du, dv = r * math.cos(a), r * math.sin(a)
        out.append((cx + axe_u[0] * du + axe_v[0] * dv, cy + axe_u[1] * du + axe_v[1] * dv,
                    cz + axe_u[2] * du + axe_v[2] * dv))
    return out


def m_table_milieu():
    """Table de milieu du vestibule (photo du 19/11) : plateau de marbre blanc veiné à bec, ceinture dorée à oves et
    cartouche, pieds en gaine à mufles de lion et volutes, entretoise en X à volutes et graine centrale."""
    b = Bld()
    L, P, H = 1.25, 0.72, 0.80
    e = 0.035
    b.boite(-L / 2, -P / 2, H - e, L / 2, P / 2, H, M_MARBRE_B)
    b.boite(-L / 2 + 0.012, -P / 2 + 0.012, H - e - 0.012, L / 2 - 0.012, P / 2 - 0.012, H - e, M_MARBRE_B)
    # ceinture : bandeau, baguettes haute et basse, oves, cartouche à coquille au milieu des grands côtés
    zc0, zc1 = H - e - 0.13, H - e - 0.012
    li, pi_ = L / 2 - 0.05, P / 2 - 0.05
    b.boite(-li, -pi_, zc0, li, pi_, zc1, M_DORE)
    b.boite(-li - 0.012, -pi_ - 0.012, zc1 - 0.022, li + 0.012, pi_ + 0.012, zc1, M_DORE)
    b.boite(-li - 0.010, -pi_ - 0.010, zc0, li + 0.010, pi_ + 0.010, zc0 + 0.018, M_DORE)
    for k in range(-6, 7):
        x = k * 0.075
        if abs(x) < 0.12:
            continue
        for sy in (-1, 1):
            b.tube((x, sy * pi_, zc0 + 0.06), (x, sy * (pi_ + 0.014), zc0 + 0.06), 0.018, M_DORE, 8, r1=0.012)
    for k in range(-3, 4):
        y = k * 0.075
        for sx in (-1, 1):
            b.tube((sx * li, y, zc0 + 0.06), (sx * (li + 0.014), y, zc0 + 0.06), 0.018, M_DORE, 8, r1=0.012)
    for sy in (-1, 1):
        for k in range(7):
            a = math.pi * (0.1 + 0.8 * k / 6)
            b.poutre((0, sy * (pi_ + 0.012), zc0 + 0.02), (0.11 * math.cos(a), sy * (pi_ + 0.018), zc0 + 0.02 + 0.10 * math.sin(a)),
                     0.022, 0.012, M_DORE)
        b.tube((0, sy * pi_, zc0 + 0.03), (0, sy * (pi_ + 0.03), zc0 + 0.03), 0.03, M_DORE, 10, r1=0.018)
    # pieds en gaine
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (L / 2 - 0.10), sy * (P / 2 - 0.10)
            t, bs = 0.055, 0.030
            b.hexa([(x - t, y - t, 0.12), (x + t, y - t, 0.12), (x + t, y + t, 0.12), (x - t, y + t, 0.12),
                    (x - t, y - t, zc0), (x + t, y - t, zc0), (x + t, y + t, zc0), (x - t, y + t, zc0)], M_DORE)
            b.hexa([(x - bs, y - bs, 0.10), (x + bs, y - bs, 0.10), (x + bs, y + bs, 0.10), (x - bs, y + bs, 0.10),
                    (x - t, y - t, 0.42), (x + t, y - t, 0.42), (x + t, y + t, 0.42), (x - t, y + t, 0.42)], M_DORE)
            # bagues et chapiteau sous la ceinture
            for z in (0.42, 0.47, zc0 - 0.03):
                b.boite(x - t - 0.012, y - t - 0.012, z, x + t + 0.012, y + t + 0.012, z + 0.022, M_DORE)
            # mufle de lion sur l'angle : tête, crinière en couronne, museau
            dx, dy = sx * 0.707, sy * 0.707
            hx, hy, hz = x + dx * 0.065, y + dy * 0.065, zc0 - 0.11
            b.tour([(0.0, -0.06), (0.045, -0.05), (0.06, -0.02), (0.058, 0.02), (0.04, 0.05), (0.0, 0.065)], hx, hy, M_DORE,
                   n=12, z0=hz)
            for k in range(12):
                a = 2 * math.pi * k / 12
                b.poutre((hx + 0.05 * math.cos(a), hy + 0.05 * math.sin(a), hz + 0.05 * math.sin(a * 0.5)),
                         (hx + 0.085 * math.cos(a), hy + 0.085 * math.sin(a), hz + 0.07 * math.sin(a * 0.5) - 0.02),
                         0.03, 0.02, M_DORE)
            b.tube((hx, hy, hz - 0.01), (hx + dx * 0.05, hy + dy * 0.05, hz - 0.02), 0.022, M_DORE, 8, r1=0.012)
            # volutes de part et d'autre du pied
            courbe(b, volute((x + sx * 0.06, y, 0.62), (0, 0, 1), (sx, 0, 0), 0.06), 0.009, M_DORE, 6)
            courbe(b, volute((x, y + sy * 0.06, 0.62), (0, 0, 1), (0, sy, 0), 0.06), 0.009, M_DORE, 6)
            # pied à griffe
            b.tour([(0.0, 0.0), (0.06, 0.005), (0.065, 0.04), (0.045, 0.08), (0.035, 0.10), (0.0, 0.11)], x, y, M_DORE, n=12)
            # entretoise en X, cintrée vers le haut
            pts = bezier((x, y, 0.16), (x * 0.6, y * 0.6, 0.12), (x * 0.25, y * 0.25, 0.26), (x * 0.08, y * 0.08, 0.22), 8)
            b.polyligne(pts, 0.05, 0.03, M_DORE)
            courbe(b, volute((x * 0.45, y * 0.45, 0.24), (sx * 0.7, sy * 0.7, 0), (0, 0, 1), 0.04), 0.008, M_DORE, 6)
    # graine centrale sur cartouche
    b.tour([(0.0, 0.15), (0.09, 0.17), (0.10, 0.21), (0.06, 0.24), (0.07, 0.30), (0.04, 0.36), (0.02, 0.40), (0.0, 0.42)],
           0, 0, M_DORE, n=14)
    return b


def m_vestiaire():
    """Porte-manteau néo-Renaissance en chêne foncé (photo du 19/11) : socle à bac et pieds miches, bas à panneau
    et rinceaux, barre à parapluies en laiton, montants à rosaces et rinceaux, miroir central à cintre chantourné,
    galeries à fuseaux et arcatures, corniche, deux pommes côtelées, patères doubles en laiton. Face vers +Y."""
    b = Bld()
    W = 1.26
    yf = 0.15          # nu du bas (face)
    yh = -0.09         # nu de la partie haute (face)
    # socle et bac
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.tour([(0.0, 0.0), (0.05, 0.005), (0.055, 0.03), (0.04, 0.05)], sx * 0.56, sy * 0.15, M_CHENE, n=10)
    b.boite(-W / 2 - 0.03, -0.20, 0.05, W / 2 + 0.03, 0.24, 0.10, M_CHENE)
    b.boite(-W / 2 - 0.01, -0.19, 0.10, W / 2 + 0.01, 0.23, 0.17, M_CHENE)
    b.boite(-W / 2 + 0.04, -0.15, 0.165, W / 2 - 0.04, 0.19, 0.172, M_ZINC)      # bac à parapluies
    # bas : caisson, panneau central à plate-bande, panneaux latéraux à rinceaux, consoles à volutes
    b.boite(-W / 2 + 0.06, -0.17, 0.17, W / 2 - 0.06, yf, 0.98, M_CHENE)
    b.boite(-0.24, yf, 0.26, 0.24, yf + 0.018, 0.90, M_CHENE)
    b.boite(-0.19, yf + 0.018, 0.31, 0.19, yf + 0.03, 0.85, M_CHENE_CLAIR)
    for sx in (-1, 1):
        x0 = sx * 0.40
        b.boite(x0 - 0.10, yf, 0.24, x0 + 0.10, yf + 0.012, 0.92, M_CHENE)
        rinceau = [(x0 + 0.03 * math.sin(k * 0.9), yf + 0.016, 0.30 + k * 0.05) for k in range(12)]
        courbe(b, rinceau, 0.008, M_CHENE_CLAIR, 5)
        for k in range(0, 12, 3):
            courbe(b, volute((rinceau[k][0], yf + 0.016, rinceau[k][2]), (1, 0, 0), (0, 0, 1), 0.03), 0.005, M_CHENE_CLAIR, 4)
        courbe(b, volute((sx * (W / 2 - 0.05), yf - 0.02, 0.24), (0, 1, 0), (0, 0, 1), 0.07), 0.018, M_CHENE, 6)
    b.boite(-W / 2 + 0.02, -0.19, 0.98, W / 2 - 0.02, yf + 0.03, 1.03, M_CHENE)
    # barre à parapluies
    for sx in (-1, 1):
        b.boite(sx * 0.42 - 0.03, yf + 0.03, 1.03, sx * 0.42 + 0.03, 0.29, 1.08, M_CHENE)
        b.tour([(0.0, 0.0), (0.03, 0.01), (0.03, 0.04), (0.0, 0.05)], sx * 0.47, 0.27, M_LAITON, n=10, z0=1.03)
    b.tube((-0.47, 0.27, 1.055), (0.47, 0.27, 1.055), 0.016, M_LAITON, 10)
    # partie haute : fond, montants, traverses
    b.boite(-W / 2 + 0.05, -0.17, 1.03, W / 2 - 0.05, yh - 0.03, 2.56, M_CHENE)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (W / 2 - 0.05), sx * 0.35))
        b.boite(x0, yh - 0.03, 1.03, x1, yh, 2.30, M_CHENE)
        xc = (x0 + x1) / 2
        for z in (1.30, 2.12):      # rosaces sculptées
            b.boite(xc - 0.10, yh, z - 0.10, xc + 0.10, yh + 0.012, z + 0.10, M_CHENE)
            b.tube((xc, yh, z), (xc, yh + 0.03, z), 0.075, M_CHENE, 16, r1=0.065)
            for k in range(10):
                a = 2 * math.pi * k / 10
                b.tube((xc + 0.045 * math.cos(a), yh + 0.03, z + 0.045 * math.sin(a)),
                       (xc + 0.045 * math.cos(a), yh + 0.045, z + 0.045 * math.sin(a)), 0.02, M_CHENE_CLAIR, 6)
            b.tube((xc, yh + 0.03, z), (xc, yh + 0.05, z), 0.022, M_CHENE, 8)
        # panneau à rinceaux entre les rosaces
        b.boite(xc - 0.09, yh, 1.44, xc + 0.09, yh + 0.012, 1.98, M_CHENE)
        tige = [(xc + 0.025 * math.sin(k * 1.1), yh + 0.016, 1.48 + k * 0.042) for k in range(12)]
        courbe(b, tige, 0.007, M_CHENE_CLAIR, 5)
        for k in range(1, 12, 3):
            courbe(b, volute((tige[k][0], yh + 0.016, tige[k][2]), (1, 0, 0), (0, 0, 1), 0.035), 0.005, M_CHENE_CLAIR, 4)
        # patères doubles en laiton
        for xp, z in ((sx * 0.60, 2.02), (sx * 0.37, 2.02), (sx * 0.37, 1.62), (sx * 0.60, 1.20)):
            courbe(b, [(xp, yh, z), (xp, yh + 0.05, z + 0.02), (xp, yh + 0.11, z + 0.08), (xp, yh + 0.13, z + 0.17)],
                   0.008, M_LAITON, 6)
            b.tour([(0.0, 0.0), (0.014, 0.01), (0.0, 0.025)], xp, yh + 0.13, M_LAITON, n=8, z0=z + 0.17)
            courbe(b, [(xp, yh + 0.03, z), (xp, yh + 0.09, z - 0.03), (xp, yh + 0.10, z - 0.08), (xp, yh + 0.07, z - 0.10)],
                   0.007, M_LAITON, 6)
            b.tube((xp, yh - 0.01, z), (xp, yh + 0.01, z), 0.018, M_LAITON, 8)
    # miroir central à cintre chantourné
    b.boite(-0.35, yh - 0.03, 1.25, 0.35, yh + 0.02, 1.30, M_CHENE)
    b.boite(-0.35, yh - 0.03, 2.20, 0.35, yh + 0.02, 2.28, M_CHENE)
    for sx in (-1, 1):
        b.boite(sx * 0.35 - 0.05 * (sx > 0), yh - 0.03, 1.25, sx * 0.35 + 0.05 * (sx < 0), yh + 0.02, 2.28, M_CHENE)
    b.quad([(-0.30, yh - 0.005, 1.30), (0.30, yh - 0.005, 1.30), (0.30, yh - 0.005, 2.20), (-0.30, yh - 0.005, 2.20)],
           M_MIROIR)
    cintre = [(-0.30 + 0.6 * k / 16, yh + 0.012, 2.20 - 0.06 * math.sin(math.pi * k / 16) ** 0.5
               - 0.025 * math.cos(6 * math.pi * k / 16)) for k in range(17)]
    b.polyligne(cintre, 0.03, 0.03, M_CHENE)
    courbe(b, volute((-0.06, yh + 0.02, 2.16), (1, 0, 0), (0, 0, 1), 0.035), 0.007, M_CHENE, 5)
    courbe(b, volute((0.06, yh + 0.02, 2.16), (-1, 0, 0), (0, 0, 1), 0.035), 0.007, M_CHENE, 5)
    # galerie basse à fuseaux et arcatures
    b.boite(-0.35, yh - 0.03, 1.03, 0.35, yh + 0.01, 1.07, M_CHENE)
    for k in range(-2, 3):
        b.tour([(0.012, 0.0), (0.02, 0.03), (0.012, 0.07), (0.02, 0.12), (0.012, 0.18)], k * 0.13, yh - 0.005, M_CHENE,
               n=8, z0=1.07)
    # galerie haute : traverse, fuseaux, arcatures à pendentifs, pastilles, corniche, pommes côtelées
    b.boite(-W / 2 + 0.05, yh - 0.03, 2.30, W / 2 - 0.05, yh + 0.01, 2.34, M_CHENE)
    narc = 10
    for k in range(narc):
        x0 = -W / 2 + 0.06 + (W - 0.12) * k / narc
        x1 = -W / 2 + 0.06 + (W - 0.12) * (k + 1) / narc
        xm, rr = (x0 + x1) / 2, (x1 - x0) / 2
        arc = [(xm + rr * math.cos(math.pi * t / 8), yh, 2.50 - 0.6 * rr * math.sin(math.pi * t / 8)) for t in range(9)]
        b.polyligne(arc, 0.025, 0.035, M_CHENE)
        b.tour([(0.0, -0.05), (0.013, -0.035), (0.008, -0.01), (0.012, 0.0)], x0, yh + 0.01, M_CHENE, n=8, z0=2.50)
        b.tube((xm, yh, 2.525), (xm, yh + 0.03, 2.525), 0.014, M_CHENE_CLAIR, 8)
        if 2 <= k <= 7:
            b.tour([(0.01, 0.0), (0.018, 0.03), (0.01, 0.07), (0.016, 0.12), (0.01, 0.15)], xm, yh - 0.01, M_CHENE,
                   n=8, z0=2.34)
    b.boite(-W / 2 + 0.03, yh - 0.03, 2.50, W / 2 - 0.03, yh + 0.02, 2.56, M_CHENE)
    b.boite(-W / 2 - 0.06, -0.20, 2.56, W / 2 + 0.06, yh + 0.06, 2.60, M_CHENE)
    b.boite(-W / 2 - 0.09, -0.21, 2.60, W / 2 + 0.09, yh + 0.09, 2.64, M_CHENE)
    for sx in (-1, 1):
        b.tube((sx * (W / 2 - 0.02), yh + 0.02, 2.53), (sx * (W / 2 - 0.02), yh + 0.04, 2.53), 0.025, M_LAITON, 10)
        pc = [(0.03, 0.0), (0.04, 0.02), (0.06, 0.06), (0.062, 0.10), (0.05, 0.14), (0.025, 0.17), (0.0, 0.18)]
        b.tour(pc, sx * 0.50, -0.05, M_CHENE, n=16, z0=2.64)
    return b


def m_radiateur(L=0.7, H=0.8):
    b = Bld()
    n = int(L / 0.06)
    for k in range(n):
        x = -L / 2 + (k + 0.5) * L / n
        b.boite(x - 0.022, -0.09, 0.1, x + 0.022, 0.09, H, M_FONTE)
    b.boite(-L / 2, -0.03, 0.12, L / 2, 0.03, H - 0.04, M_FONTE)
    for x in (-L / 2 + 0.03, L / 2 - 0.03):
        b.boite(x - 0.02, -0.08, 0, x + 0.02, 0.08, 0.1, M_FONTE)
    return b


def m_drapeau():
    """Drapeau rouge et blanc sur hampe dans un pied (P20, P19)."""
    b = Bld()
    b.tour([(0.15, 0), (0.12, 0.05), (0.03, 0.08), (0.0, 0.08)], 0, 0, M_BRONZE, n=12)
    b.tube((0, 0, 0.05), (0.15, 0, 2.2), 0.015, M_NOYER, 6)
    b.tour([(0.0, 2.2), (0.03, 2.24), (0.0, 2.32)], 0.15, 0, M_LAITON, n=6)
    # étoffe tombante, plissée
    for k, mat in enumerate((M_DRAPEAU_R, M_DRAPEAU_B)):
        n = 8
        pts = []
        for j in range(n + 1):
            t = j / n
            pts.append(Vector((0.14 + 0.03 * math.sin(t * 9 + k), 0.0 + 0.06 * math.sin(t * 7), 2.1 - k * 0.45 - 0.0)))
        for j in range(n):
            z0, z1 = 2.12 - k * 0.42, 2.12 - (k + 1) * 0.42
            p, q = pts[j], pts[j + 1]
            b.quad([(p.x, p.y + 0.0 + j * 0.04, z1), (q.x, q.y + (j + 1) * 0.04, z1),
                    (q.x - 0.02, q.y + (j + 1) * 0.045, z0), (p.x - 0.02, p.y + j * 0.045, z0)], mat)
    return b


def m_canon():
    """Canon miniature décoratif sur affût à roues (P20)."""
    b = Bld()
    b.tube((0, -0.35, 0.42), (0, 0.65, 0.52), 0.09, M_ACIER, 12, r1=0.06)
    b.tour([(0.0, 0), (0.1, 0.02), (0.0, 0.12)], 0, 0, M_ACIER, n=10, z0=0)
    b.boite(-0.12, -0.6, 0.15, 0.12, 0.25, 0.36, M_LAQUE_GRIS)
    for sx in (-1, 1):
        b.tube((sx * 0.2, 0.0, 0.3), (sx * 0.26, 0.0, 0.3), 0.3, M_LAQUE_NOIR, 16)
    b.poutre((0, -0.6, 0.15), (0, -0.85, 0.02), 0.18, 0.08, M_LAQUE_GRIS)
    return b


def m_chevalet(h=1.6, affiche=True):
    b = Bld()
    b.poutre((-0.3, 0.12, 0), (0, 0.0, h), 0.04, 0.025, M_PIN)
    b.poutre((0.3, 0.12, 0), (0, 0.0, h), 0.04, 0.025, M_PIN)
    b.poutre((0, -0.35, 0), (0, 0.0, h * 0.95), 0.035, 0.025, M_PIN)
    b.boite(-0.32, 0.04, 0.62, 0.32, 0.14, 0.66, M_PIN)
    if affiche:
        b.quad([(-0.3, 0.13, 0.66), (0.3, 0.13, 0.66), (0.3, 0.05, 1.5), (-0.3, 0.05, 1.5)], M_TOILE["affiche"])
    return b


def m_plateau_plante():
    """Palmier en pot (repli si l'asset Poly Haven manque)."""
    b = Bld()
    b.tour([(0.12, 0), (0.18, 0.35), (0.0, 0.35)], 0, 0, M_FAIENCE, n=12)
    for k in range(9):
        a = 2 * math.pi * k / 9
        b.poutre((0, 0, 0.35), (0.45 * math.cos(a), 0.45 * math.sin(a), 0.9), 0.12, 0.01, M_FEUILLE)
    return b


# ----------------------------------------------------------------------------------------------
# Assets Poly Haven (CC0) déjà présents dans assets/polyhaven
# ----------------------------------------------------------------------------------------------
PH_CACHE = {}


def asset_ph(nom_dossier, gltf, nom, loc, rot=0.0, hauteur=None):
    """Importe (une fois) un asset glTF Poly Haven, le joint en un maillage, puis l'instancie."""
    chemin = os.path.join(ASSETS, "polyhaven", nom_dossier, gltf)
    if not os.path.exists(chemin):
        return None
    if nom_dossier not in PH_CACHE:
        avant = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=chemin)
        neufs = [o for o in set(bpy.data.objects) - avant]
        maillages = [o for o in neufs if o.type == "MESH"]
        bpy.context.view_layer.update()
        mws = {o: o.matrix_world.copy() for o in maillages}
        bm = bmesh.new()
        mats = []
        for o in maillages:
            me = o.data.copy()
            me.transform(mws[o])
            off = len(mats)
            for m in o.data.materials:
                mats.append(m)
            for poly in me.polygons:
                poly.material_index += off
            bm.from_mesh(me)
            bpy.data.meshes.remove(me)
        bb = [v.co for v in bm.verts]
        zmin = min(c.z for c in bb)
        zmax = max(c.z for c in bb)
        cx = (min(c.x for c in bb) + max(c.x for c in bb)) / 2
        cy = (min(c.y for c in bb) + max(c.y for c in bb)) / 2
        bmesh.ops.translate(bm, verts=bm.verts, vec=(-cx, -cy, -zmin))
        me = bpy.data.meshes.new(nom_dossier)
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(m)
        for o in neufs:
            bpy.data.objects.remove(o, do_unlink=True)
        PH_CACHE[nom_dossier] = (me, zmax - zmin)
    me, h0 = PH_CACHE[nom_dossier]
    o = bpy.data.objects.new(nom, me)
    o.location = loc
    o.rotation_euler = (0, 0, rot)
    if hauteur:
        k = hauteur / h0
        o.scale = (k, k, k)
    COL.objects.link(o)
    return o


# ----------------------------------------------------------------------------------------------
# Lumières (reprises par l'importeur Unity : noms lumiere_<piece>_*)
# ----------------------------------------------------------------------------------------------
LUMIERES = []


def lumiere(nom, loc, energie, rayon=0.15, couleur=(1.0, 0.84, 0.62)):
    li = bpy.data.lights.new(nom, "POINT")
    li.energy = energie
    li.shadow_soft_size = rayon
    li.color = couleur
    o = bpy.data.objects.new(nom, li)
    o.location = loc
    COL.objects.link(o)
    LUMIERES.append(nom)
    return o


# ==============================================================================================
# VESTIBULE (P20, P21, P41, W08)
# ==============================================================================================
log("vestibule…")
V = PIECES["vestibule"]
V_POLY = [tuple(p) for p in V["polygone_interieur"]]
YV_N = min(p[1] for p in V_POLY)            # nu intérieur du mur d'entrée (avant-corps approfondi, -11,85)
YV_F = (YV_N - 0.6 + -8.75) / 2              # axe des fenêtres latérales de l'avant-corps (bati.py)
YV_C = (YV_N + -3.75) / 2                    # milieu du vestibule (rosace, lustre, table)
PORTE_ENTREE = dict(c=(0.0, YV_N), l=1.70, zb=0.0, zh=4.10, arc=False, nom="porte_entree")
FEN_V = [dict(c=(sx * 3.4, YV_F), l=1.35, zb=0.45, zh=3.70, arc=False, nom="baie_fenetre_" + ("est" if sx > 0 else "ouest"))
         for sx in (-1, 1)]
V_OUV = ouvertures_de("vestibule", [PORTE_ENTREE] + FEN_V)
H_V = 5.0
# arête sud (écran à colonnes) : ne reçoit que la corniche
SUD_V = [i for i, (p0, p1, u, nn, L) in enumerate(aretes(V_POLY)) if abs(p0.y + 3.75) < 1e-3 and abs(p1.y + 3.75) < 1e-3]


def couches_damas(h):
    """Soubassement d'un mètre, cimaise, papier peint damassé jusqu'à h (sous la corniche)."""
    return [(0.0, 1.0, M_SOUB, 0.0, 0.02), (1.0, h, M_DAMAS, 0.0, 0.006), (0.97, 1.03, M_BLANC, 0.0, 0.045)]


habiller("vestibule_murs", V_POLY, 0.0, V_OUV, couches_damas(H_V - 0.02), sauf=SUD_V)
b = Bld()
chambranles(None, V_POLY, 0.0, V_OUV, dessus=(H_V - 0.35, 0.75), bld=b)
corniche(b, V_POLY, H_V, h=0.35, saillie=0.26)
# rosace de plafond (photo du 19/11) : objet séparé pour rester ronde au recalage ; couronne festonnée, rinceaux
# d'acanthe en volutes, fleuron central d'où part le lustre
br = Bld()
br.tour([(0.0, -0.012), (0.62, -0.012), (0.61, -0.03), (0.55, -0.045), (0.46, -0.04), (0.40, -0.06), (0.28, -0.07),
         (0.16, -0.09), (0.09, -0.13), (0.04, -0.15), (0.0, -0.16)], 0, YV_C, M_PLATRE, n=32, z0=H_V)
for k in range(24):     # festons de la couronne
    a = 2 * math.pi * k / 24
    br.tube((0.58 * math.cos(a), YV_C + 0.58 * math.sin(a), H_V - 0.012),
            (0.58 * math.cos(a), YV_C + 0.58 * math.sin(a), H_V - 0.05), 0.045, M_PLATRE, 8, r1=0.03)
for k in range(8):      # rinceaux d'acanthe
    a = 2 * math.pi * k / 8
    ca, sa = math.cos(a), math.sin(a)
    pts = [(r * math.cos(a + 0.5 * r), YV_C + r * math.sin(a + 0.5 * r), H_V - 0.06 - 0.03 * math.sin(r * 6))
           for r in [0.12 + 0.04 * t for t in range(9)]]
    courbe(br, pts, 0.03, M_PLATRE, 6, r_fin=0.015)
    courbe(br, volute(pts[-1], (ca, sa, 0), (-sa, ca, 0), 0.07), 0.016, M_PLATRE, 6)
    for t in range(1, 8, 2):
        p = pts[t]
        br.poutre(p, (p[0] - sa * 0.07, p[1] + ca * 0.07, p[2] + 0.01), 0.05, 0.015, M_PLATRE)
br.objet("vestibule_rosace")
# pilastres encadrant la porte d'entrée (mur nord) : base, fût à table, chapiteau
for sx in (-1, 1):
    x = sx * 1.32
    b.boite_c(x, YV_N + 0.05, 0.0, 0.55, 0.10, 0.45, M_BLANC)
    b.boite_c(x, YV_N + 0.04, 0.45, 0.45, 0.08, 3.75, M_BLANC)
    b.boite_c(x, YV_N + 0.085, 0.75, 0.3, 0.01, 3.2, M_GRISVERT)
    b.boite_c(x, YV_N + 0.09, 0.78, 0.26, 0.01, 3.14, M_BLANC)
    b.boite_c(x, YV_N + 0.07, 4.2, 0.55, 0.14, 0.25, M_BLANC)
    b.boite_c(x, YV_N + 0.08, 4.45, 0.62, 0.16, 0.2, M_BLANC)
# bandes de marbre rouge : pourtour et grand cadre central (P41, P20)
bandes_sol(b, [(V_POLY, 0.32, 0.12), (rect(-2.45, YV_N + 0.6, 2.45, -4.35), 0.0, 0.12)],
           [(-0.06, -4.35, 0.06, -3.75)], 0.0)
b.objet("vestibule_decor")

# colonnes de l'écran : chapiteau composite (volutes et feuilles d'acanthe), habillage des piliers de coque


def m_colonne(r, h=4.6, base_carree=0.0):
    b = Bld()
    zc = h - 0.5
    prof = [(r + 0.12, 0.0), (r + 0.12, 0.10), (r + 0.09, 0.13), (r + 0.10, 0.18), (r + 0.04, 0.22), (r + 0.06, 0.27),
            (r + 0.02, 0.30), (r, 0.33), (r * 0.95, zc - 0.08), (r * 0.98, zc - 0.05), (r * 0.98, zc - 0.02),
            (r * 0.93, zc), (r * 0.98, zc + 0.30), (r * 1.08, zc + 0.36), (0.0, zc + 0.36)]
    b.tour(prof, 0, 0, M_BLANC, n=24)
    if base_carree:
        b.boite_c(0, 0, 0, 2 * (r + 0.13), 2 * (r + 0.13), 0.08, M_BLANC)
    # deux rangs de feuilles d'acanthe
    for rang, (zz, hh, nb) in enumerate(((zc + 0.02, 0.18, 8), (zc + 0.12, 0.2, 8))):
        for k in range(nb):
            a = 2 * math.pi * (k + 0.5 * rang) / nb
            ca, sa = math.cos(a), math.sin(a)
            rr = r * 0.95 + 0.01
            b.hexa([(rr * ca - 0.07 * sa, rr * sa + 0.07 * ca, zz), (rr * ca + 0.07 * sa, rr * sa - 0.07 * ca, zz),
                    ((rr + 0.03) * ca + 0.07 * sa, (rr + 0.03) * sa - 0.07 * ca, zz),
                    ((rr + 0.03) * ca - 0.07 * sa, (rr + 0.03) * sa + 0.07 * ca, zz),
                    ((rr + 0.06) * ca - 0.05 * sa, (rr + 0.06) * sa + 0.05 * ca, zz + hh),
                    ((rr + 0.06) * ca + 0.05 * sa, (rr + 0.06) * sa - 0.05 * ca, zz + hh),
                    ((rr + 0.1) * ca + 0.05 * sa, (rr + 0.1) * sa - 0.05 * ca, zz + hh),
                    ((rr + 0.1) * ca - 0.05 * sa, (rr + 0.1) * sa + 0.05 * ca, zz + hh)], M_BLANC)
    # tailloir à côtés concaves et volutes d'angle
    t = r * 1.25 + 0.06
    b.boite_c(0, 0, zc + 0.36, 2 * t, 2 * t, 0.1, M_BLANC)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (t - 0.06), sy * (t - 0.06)
            b.tube((cx - sx * 0.02, cy, zc + 0.27), (cx + sx * 0.04, cy, zc + 0.27), 0.08, M_BLANC, 10)
    return b


for nom, x in (("vestibule_colonne_ouest", -1.45), ("vestibule_colonne_est", 1.45)):
    instance("colonne_c", lambda: m_colonne(0.35), nom, (x, -3.5, 0.0))
for nom, x in (("vestibule_colonne_angle_ouest", -3.42), ("vestibule_colonne_angle_est", 3.42)):
    instance("colonne_a", lambda: m_colonne(0.24), nom, (x, -3.5, 0.0))

# tapis à médaillons, table de milieu, bouquet de lys
b = Bld()
# tapis de 3,6 × 3,0 m centré sous le lustre (photo du 19/11), assez petit pour rester rigide au recalage
TX, TY = 1.8, 1.5
b.quad([(-TX, YV_C - TY, 0.012), (TX, YV_C - TY, 0.012), (TX, YV_C + TY, 0.012), (-TX, YV_C + TY, 0.012)], M_TAPIS,
       uv=((0, 1), (1, 1), (1, 0), (0, 0)))
b.boite(-TX, YV_C - TY, 0.0, TX, YV_C + TY, 0.011, M_VELOURS_SIEGE)
b.objet("vestibule_tapis")
m_table_milieu().objet("vestibule_table_milieu", loc=(0.0, YV_C + 0.6, 0.012))
m_vase_fleurs(0.62).objet("vestibule_bouquet_lys", loc=(0.1, YV_C + 0.6, 0.812))
b = Bld()
for k in range(3):
    b.boite_c(-0.35 + k * 0.03, YV_C + 0.5 + k * 0.02, 0.0, 0.24, 0.32, 0.004, M_FAIENCE if k != 1 else M_CERAM_BLEU)
b.objet("vestibule_brochures", loc=(0, 0, 0.812))
# paillasson
b = Bld()
b.boite(-0.6, YV_N + 0.02, 0.0, 0.6, YV_N + 0.62, 0.015, M_COCO)
b.objet("vestibule_paillasson")
# lustre, lumière principale
m_lustre(10, 0.55, 0.9).objet("vestibule_lustre", loc=(0.0, YV_C, H_V - 0.12))
lumiere("lumiere_vestibule_lustre", (0.0, YV_C, H_V - 1.35), 300, 0.4)

# mur ouest : console demi-lune marbre noir, miroir à fronton, lampe bleue, fusil (P20, P21, P22)
x_o = -3.7
r_o = face_vers(1, 0)
m_console_demilune(M_MARBRE_N, M_DORE).objet("vestibule_console_ouest", loc=(x_o + 0.225, -5.5, 0.0), rot=r_o)
m_miroir(0.62, 1.05, fronton=True).objet("vestibule_miroir_ouest", loc=(x_o + 0.006, -5.5, 1.45), rot=r_o)
m_lampe().objet("vestibule_lampe_ouest", loc=(x_o + 0.25, -5.2, 0.85))
m_cadre(0.22, 0.3, M_TOILE["affiche"], prof=0.02, c=0.02, mat_cadre=M_LAQUE_NOIR).objet(
    "vestibule_affiche_console", loc=(x_o + 0.12, -5.75, 0.85), rot=face_vers(1, 0.3))
instance("fusil", m_fusil, "vestibule_fusil_ouest", (x_o + 0.006, -6.5, 1.6), face_vers(1, 0))
instance("fusil", m_fusil, "vestibule_fusil_est", (-x_o - 0.006, -6.5, 1.6), face_vers(-1, 0))
m_chevalet().objet("vestibule_chevalet", loc=(-2.85, -6.25, 0.0), rot=face_vers(0.4, 1))

# mur est : vestiaire (W08), chaises médaillon et palmier (P20), drapeau (P19, P20)
m_vestiaire().objet("vestibule_vestiaire", loc=(3.7 - 0.23, -4.85, 0.0), rot=face_vers(-1, 0))
asset_ph("polyhaven-potted_plant_02", "potted_plant_02_1k.gltf", "vestibule_plante", (3.1, YV_N + 0.3, 0.0), 0.0, 1.05) \
    or m_plateau_plante().objet("vestibule_plante", loc=(3.1, YV_N + 0.3, 0.0))
for k, (x, y, d) in enumerate(((2.6, YV_N + 0.4, (0.1, 1)), (3.4, -6.35, (-1, 0.1)))):
    instance("chaise_medaillon", lambda: m_fauteuil(M_TISSU_CREME, M_ACAJOU, bras=False, larg=0.5, prof=0.5),
             "vestibule_chaise_%d" % (k + 1), (x, y, 0.0), face_vers(*d))
m_drapeau().objet("vestibule_drapeau", loc=(1.05, YV_N + 0.4, 0.0))
# mur nord : radiateurs en fonte, gravures encadrées de part et d'autre de la porte
for sx in (-1, 1):
    instance("radiateur", m_radiateur, "vestibule_radiateur_%s" % ("est" if sx > 0 else "ouest"),
             (sx * 1.95, YV_N + 0.12, 0.0))
    m_cadre(0.42, 0.52, M_TOILE["gravure1" if sx < 0 else "gravure2"], c=0.04, mat_cadre=M_ACAJOU).objet(
        "vestibule_gravure_%s" % ("est" if sx > 0 else "ouest"), loc=(sx * 2.2, YV_N + 0.005, 2.0))
# canon miniature et photophores, angle nord-ouest (P20)
m_canon().objet("vestibule_canon", loc=(-2.4, YV_N + 0.65, 0.0), rot=face_vers(1, 0))
b = Bld()
for k, (x, y) in enumerate(((-3.1, YV_N + 0.2), (-2.95, YV_N + 0.13), (-3.2, YV_N + 0.33))):
    b.tour([(0.06, 0), (0.07, 0.25), (0.05, 0.3), (0.0, 0.3)], x, y, M_VERRE, n=8)
    b.tour([(0.07, 0.3), (0.0, 0.36)], x, y, M_LAITON, n=8)
    b.tube((x, y, 0.02), (x, y, 0.12), 0.03, M_BOUGIE, 8)
b.objet("vestibule_photophores")
# rideaux de velours rouge et tringles des fenêtres latérales de l'avant-corps (P20, W08)
for sx in (-1, 1):
    x = sx * 3.4
    rot = face_vers(-sx, 0)
    for k, dy in enumerate((-0.6, 0.6)):
        instance("rideau_v", lambda: m_rideau(0.5, 3.75), "vestibule_rideau_%s_%d" % ("est" if sx > 0 else "ouest", k + 1),
                 (x - sx * 0.02, YV_F + dy, 0.0), rot)
    b = Bld()
    b.tube((x - sx * 0.12, YV_F - 0.9, 3.85), (x - sx * 0.12, YV_F + 0.9, 3.85), 0.018, M_DORE, 8)
    for y in (YV_F - 0.92, YV_F + 0.92):
        b.tour([(0.0, -0.04), (0.04, 0.0), (0.0, 0.04)], x - sx * 0.12, y, M_DORE, n=8, z0=3.85)
    b.objet("vestibule_tringle_%s" % ("est" if sx > 0 else "ouest"))

# ==============================================================================================
# ESCALIER : tapis à barres laiton, rampes à volutes, tapisserie, repos (P14-P19, W08, W09)
# ==============================================================================================
log("escalier…")
b = Bld()
for k in range(1, N_C):
    y0 = Y_DEPART + (k - 1) * G_C
    z = k * H_C
    b.tube((-0.8, y0 + G_C - 0.025, z + 0.03), (0.8, y0 + G_C - 0.025, z + 0.03), 0.009, M_LAITON, 6)
    for x in (-0.8, 0.8):
        b.tour([(0.0, z + 0.012), (0.018, z + 0.02), (0.016, z + 0.045), (0.0, z + 0.05)], x, y0 + G_C - 0.025, M_LAITON, n=6)
for s in (1, -1):
    xm = s * (X_VR0 + X_VR1) / 2
    for k in range(1, N_R):
        y0 = Y_REPOS - (k - 1) * G_R
        z = Z_REPOS + k * H_R
        yb = y0 - G_R + 0.025
        b.tube((xm - 0.6, yb, z + 0.03), (xm + 0.6, yb, z + 0.03), 0.009, M_LAITON, 6)
        for x in (xm - 0.6, xm + 0.6):
            b.tour([(0.0, z + 0.012), (0.018, z + 0.02), (0.016, z + 0.045), (0.0, z + 0.05)], x, yb, M_LAITON, n=6)
b.objet("escalier_barres_tapis")

# rampes en fer forgé à volutes et rinceaux, posées dans le plan des garde-corps de la coque


def spirale(cx, cy, R, a0, tours, sens, n=28, r_fin=0.18):
    pts = []
    for k in range(n + 1):
        t = k / n
        a = a0 + sens * t * tours * 2 * math.pi
        r = R * (1 - (1 - r_fin) * t)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def motif_panneau(W, H):
    """Volutes d'un panneau de rampe dans son plan (s, h) : deux C opposés en S, crosses, rosette."""
    traits = []
    R = min(W, H) * 0.24
    a = spirale(W * 0.3, H * 0.38, R, math.pi * 0.5, 1.1, 1)
    c = spirale(W * 0.7, H * 0.62, R, -math.pi * 0.5, 1.1, 1)
    traits += [a, c]
    # liaison en S entre les deux volutes
    traits.append([(W * 0.3, H * 0.38 + R), (W * 0.5, H * 0.5 + R * 0.4), (W * 0.62, H * 0.62 - R * 0.9),
                   (W * 0.7, H * 0.62 - R)])
    traits.append(spirale(W * 0.82, H * 0.2, R * 0.55, math.pi, 1.2, -1, n=18))
    traits.append(spirale(W * 0.18, H * 0.8, R * 0.55, 0.0, 1.2, -1, n=18))
    traits.append([(W * 0.82 - R * 0.55, H * 0.2), (W * 0.62, H * 0.06), (W * 0.4, H * 0.04)])
    traits.append([(W * 0.18 + R * 0.55, H * 0.8), (W * 0.38, H * 0.94), (W * 0.6, H * 0.96)])
    traits.append([(W * 0.5 + R * 0.12 * math.cos(2 * math.pi * k / 10), H * 0.5 + R * 0.12 * math.sin(2 * math.pi * k / 10))
                   for k in range(11)])
    traits.append([(0.0, 0.0), (0.0, H)])
    return traits


def rampe_volutes(b, pts, pas=0.85, z0=0.10, z1=0.90):
    """pts : polyligne [(x, y, z_sol)] du garde-corps ; panneaux de volutes entre z_sol+z0 et z_sol+z1."""
    for p, q in zip(pts[:-1], pts[1:]):
        p, q = Vector(p), Vector(q)
        L = (q - p).xy.length
        n = max(1, int(round(L / pas)))
        W = L / n
        H = z1 - z0
        for k in range(n):
            for trait in motif_panneau(W, H):
                p3 = []
                for (s, h) in trait:
                    t = (k * W + s) / L
                    c = p.lerp(q, t)
                    p3.append((c.x, c.y, c.z + z0 + h))
                b.polyligne(p3, 0.014, 0.014, M_FER)
        # lisse haute de fer sous la main courante
        b.poutre(p + Vector((0, 0, z1 + 0.01)), q + Vector((0, 0, z1 + 0.01)), 0.02, 0.02, M_FER)


def nez_r(y):
    return Z_REPOS + (Y_REPOS - y) / G_R * H_R + H_R


b = Bld()
for s in (1, -1):
    xc = s * (X_VC - 0.06)
    rampe_volutes(b, [(xc, Y_DEPART + 0.15, H_C), (xc, Y_REPOS - 0.1, Z_REPOS), (xc, Y_REPOS + 0.06, Z_REPOS),
                      (s * (X_VR0 - 0.06), Y_REPOS + 0.06, Z_REPOS)])
    xr = s * (X_VR0 + 0.06)
    rampe_volutes(b, [(xr, Y_REPOS - 0.1, nez_r(Y_REPOS - 0.1) - H_R), (xr, Y_ARRIVEE + 0.05, Z_ETAGE),
                      (xr, -3.25 + 0.06, Z_ETAGE), (0.0, -3.25 + 0.06, Z_ETAGE)])
b.objet("escalier_rampes_volutes")

# départs de rampe : boule de laiton sur pilastre de marbre au pied de la volée (P18)
b = Bld()
for s in (1, -1):
    xc = s * (X_VC - 0.06)
    b.tour([(0.0, 0.0), (0.05, 0.0), (0.05, 0.05), (0.035, 0.07), (0.035, 0.95), (0.05, 1.0), (0.06, 1.06),
            (0.0, 1.14)], xc, Y_DEPART + 0.15, M_LAITON, n=10, z0=H_C)
b.objet("escalier_departs_rampe")

# tapisserie d'Aubusson au mur sud de la cage, cadre sculpté (P04, P14, P42)
b = Bld()
yt = Y_CAGE_S - 0.012
zt0, zt1 = 6.05, 8.05
b.quad([(-1.6, yt, zt0), (1.6, yt, zt0), (1.6, yt, zt1), (-1.6, yt, zt1)], M_TAPISSERIE,
       uv=((0, 0), (1, 0), (1, 1), (0, 1)))
for (x0, z0, x1, z1) in ((-1.72, zt0 - 0.12, 1.72, zt0), (-1.72, zt1, 1.72, zt1 + 0.12),
                         (-1.72, zt0, -1.6, zt1), (1.6, zt0, 1.72, zt1)):
    b.boite(x0, Y_CAGE_S - 0.07, z0, x1, Y_CAGE_S, z1, M_DORE)
for k in range(40):           # torsade de feuilles d'acanthe sur le cadre
    t = k / 40
    for (pa, pb) in (((-1.66, zt0 - 0.06), (1.66, zt0 - 0.06)), ((-1.66, zt1 + 0.06), (1.66, zt1 + 0.06))):
        x = pa[0] + (pb[0] - pa[0]) * t
        b.poutre((x - 0.03, Y_CAGE_S - 0.075, pa[1] - 0.04), (x + 0.03, Y_CAGE_S - 0.075, pa[1] + 0.04), 0.04, 0.03, M_BRONZE)
b.objet("escalier_tapisserie")

# repos : amphore et pampas sous la tapisserie, chaise cannée (P14, P16)
m_pampas().objet("escalier_pampas", loc=(0.0, 3.25, Z_REPOS))
instance("chaise_cannee", lambda: m_fauteuil(M_PIN, M_MERISIER, bras=False, larg=0.45, prof=0.45, h_dos=0.9),
         "escalier_chaise_cannee", (-3.3, 3.25, Z_REPOS), face_vers(0.5, -1))
# tapis rouge débordant sur le repos (P16)
b = Bld()
b.boite(-0.75, Y_REPOS, Z_REPOS, 0.75, Y_REPOS + 1.0, Z_REPOS + 0.012, materiau("tapis_escalier", (0.42, 0.03, 0.03), 0.95))
b.objet("escalier_tapis_repos")

# ==============================================================================================
# CAGE À L'ÉTAGE, PALIER, GALERIES : arcades, balustres, panneaux, corniche, coupole (P04-P09, P14-P17)
# ==============================================================================================
log("palier, cage, coupole…")
CAGE = rect(-3.7, Y_CAGE_N, 3.7, Y_CAGE_S)
b = Bld()
# corniche à denticules sous la naissance de la coupole
corniche(b, CAGE, Z_NAISSANCE, h=0.42, saillie=0.30)
for p0, p1, u, nn, L in aretes(CAGE):
    n = int(L / 0.14)
    for k in range(n):
        s = (k + 0.5) * L / n
        c = p0 + u * s + nn * 0.13
        b.boite_c(c.x, c.y, Z_NAISSANCE - 0.27, 0.06 if abs(u.x) > 0.5 else 0.05,
                  0.05 if abs(u.x) > 0.5 else 0.06, 0.07, M_BLANC)
    # frise d'oves : cordon sous la corniche
    plaque(b, p0, u, nn, 0, L, Z_NAISSANCE - 0.62, Z_NAISSANCE - 0.42, Z_NAISSANCE - 0.42, 0, 0.05, M_BLANC)
    plaque(b, p0, u, nn, 0, L, Z_NAISSANCE - 0.56, Z_NAISSANCE - 0.53, Z_NAISSANCE - 0.53, 0.05, 0.012, M_GRISVERT)
# cordon au niveau du plancher d'étage et soubassement de l'étage
CAGE_OUV0 = []
for pid in ("palier", "vide_cage"):
    for o in PIECES[pid]["portes"]:
        CAGE_OUV0.append(dict(c=(o["centre"][0], o["centre"][1]), l=o["largeur"], zb=0, zh=o["hauteur"]))
for p0, p1, u, nn, L in aretes(CAGE):
    for s0, s1, _, _ in morceaux(L, ouv_sur_arete(p0, u, nn, L, CAGE_OUV0, tol=0.4), 0, 1):
        plaque(b, p0, u, nn, s0, s1, Z_ETAGE - 0.05, Z_ETAGE + 0.12, Z_ETAGE + 0.12, 0, 0.04, M_BLANC)

# arcades de la cage : archivoltes, impostes, tables des piliers, cartouches rocaille sur les clés
ARCADES = []
for pid in ("palier", "vide_cage", "galerie_ouest"):
    for o in PIECES[pid]["portes"]:
        if o["type"] == "arcade" and o["nom"] not in [a["nom"] for a in ARCADES]:
            ARCADES.append(o)


def archivolte(b, o, cote, ep_mur):
    """Archivolte en plein cintre sur la face du mur (cote = +1 vers les x croissants)."""
    x_mur = o["centre"][0] + cote * ep_mur / 2
    yc, l, h = o["centre"][1], o["largeur"], o["hauteur"]
    r = l / 2
    zs = Z_ETAGE + h - r            # naissance de l'arc
    n = 14
    for k in range(n):
        a0, a1 = math.pi * k / n, math.pi * (k + 1) / n
        pts = []
        for a, rr in ((a0, r), (a1, r), (a1, r + 0.16), (a0, r + 0.16)):
            pts.append((yc - rr * math.cos(a), zs + rr * math.sin(a)))
        xa, xb = x_mur, x_mur + cote * 0.035
        b.hexa([(xa, pts[i][0], pts[i][1]) for i in range(4)] + [(xb, pts[i][0], pts[i][1]) for i in range(4)], M_BLANC)
        pts2 = [(yc - rr * math.cos(a), zs + rr * math.sin(a)) for a, rr in ((a0, r + 0.1), (a1, r + 0.1), (a1, r + 0.12),
                                                                              (a0, r + 0.12))]
        xc = x_mur + cote * 0.045
        b.hexa([(xb, p[0], p[1]) for p in pts2] + [(xc, p[0], p[1]) for p in pts2], M_GRISVERT)
    # impostes
    for sy in (-1, 1):
        y = yc + sy * (r + 0.1)
        b.boite(x_mur, y - 0.14, zs - 0.12, x_mur + cote * 0.06, y + 0.14, zs, M_BLANC)
    return zs


b_arc = Bld()
for o in ARCADES:
    cx = o["centre"][0]
    if abs(cx) > 5:     # baie de la galerie ouest vers le dégagement nord-ouest : face galerie seulement
        archivolte(b_arc, o, 1, o["epaisseur_mur"])
        continue
    s = 1 if cx > 0 else -1
    zs = archivolte(b_arc, o, -s, o["epaisseur_mur"])   # face cage
    archivolte(b_arc, o, s, o["epaisseur_mur"])          # face galerie
    # cartouche à la clé, côté cage
    xk = cx - s * (o["epaisseur_mur"] / 2 + 0.05)
    b_arc.tour([(0.0, 0.0), (0.1, 0.06), (0.13, 0.2), (0.07, 0.34), (0.0, 0.38)], xk, o["centre"][1], M_BLANC, n=10,
               z0=Z_ETAGE + o["hauteur"] - 0.05)
    for sy in (-1, 1):   # guirlandes sur les écoinçons
        pts = [(xk, o["centre"][1] + sy * 0.12, Z_ETAGE + o["hauteur"] + 0.2),
               (xk, o["centre"][1] + sy * 0.45, Z_ETAGE + o["hauteur"] - 0.05),
               (xk, o["centre"][1] + sy * 0.85, Z_ETAGE + o["hauteur"] + 0.12)]
        b_arc.polyligne(pts, 0.07, 0.06, M_BLANC)
b_arc.objet("palier_arcades_decor")

# tables moulurées des piliers et des murs de la cage (filets gris-vert)
b = Bld()


def table(b, p0, u, nn, s0, s1, z0, z1, off=0.0, w=0.025):
    for (a, c, d, e) in ((s0, s1, z0, z0 + w), (s0, s1, z1 - w, z1), (s0, s0 + w, z0, z1), (s1 - w, s1, z0, z1)):
        plaque(b, p0, u, nn, a, c, d, e, e, off, 0.012, M_GRISVERT)


CAGE_OUV = []
for o in ARCADES + [p for p in PIECES["palier"]["portes"] if p["type"] != "arcade"]:
    if abs(o["centre"][0]) < 5:
        CAGE_OUV.append(dict(c=(o["centre"][0], o["centre"][1]), l=o["largeur"], zb=0, zh=o["hauteur"], o=o))
for p0, p1, u, nn, L in aretes(CAGE):
    ov = ouv_sur_arete(p0, u, nn, L, CAGE_OUV, tol=0.4)
    libres = morceaux(L, ov, 0, 1)
    for s0, s1, _, _ in libres:
        if s1 - s0 < 0.25:
            continue
        sud = abs(p0.y - Y_CAGE_S) < 1e-3 and abs(p1.y - Y_CAGE_S) < 1e-3
        if sud:
            continue
        if s1 - s0 > 2.5:
            # grands murs : un panneau haut par travée de 2 m (le mur sud reçoit la tapisserie)
            nb = max(1, int((s1 - s0) / 2.2))
            for k in range(nb):
                a = s0 + (s1 - s0) * k / nb + 0.15
                c = s0 + (s1 - s0) * (k + 1) / nb - 0.15
                table(b, p0, u, nn, a, c, Z_ETAGE + 0.45, Z_NAISSANCE - 0.9)
            if abs(p0.y - Y_CAGE_S) < 1e-3 or abs(p1.y - Y_CAGE_S) < 1e-3:
                pass
        else:
            table(b, p0, u, nn, s0 + 0.08, s1 - 0.08, Z_ETAGE + 0.5, Z_ETAGE + 3.0)
            table(b, p0, u, nn, s0 + 0.08, s1 - 0.08, Z_ETAGE + 4.0, Z_NAISSANCE - 0.9)
            # imposte continue sur les piliers
            plaque(b, p0, u, nn, s0, s1, Z_ETAGE + 2.68, Z_ETAGE + 2.8, Z_ETAGE + 2.8, 0, 0.05, M_BLANC)
# cadre mouluré autour de la tapisserie (mur sud)
for p0, p1, u, nn, L in aretes(CAGE):
    if abs(p0.y - Y_CAGE_S) < 1e-3 and abs(p1.y - Y_CAGE_S) < 1e-3:
        sm = L / 2
        table(b, p0, u, nn, sm - 2.1, sm + 2.1, 5.75, 8.45, w=0.035)
        for sx in (-1, 1):   # pilastres à table
            plaque(b, p0, u, nn, sm + sx * 2.9 - 0.25, sm + sx * 2.9 + 0.25, Z_REPOS, Z_NAISSANCE - 0.62,
                   Z_NAISSANCE - 0.62, 0, 0.05, M_BLANC)
            table(b, p0, u, nn, sm + sx * 2.9 - 0.17, sm + sx * 2.9 + 0.17, 5.7, Z_NAISSANCE - 0.85, off=0.05)
# mur sud au-dessus du repos : soubassement à table
for p0, p1, u, nn, L in aretes(CAGE):
    if abs(p0.y - Y_CAGE_S) < 1e-3 and abs(p1.y - Y_CAGE_S) < 1e-3:
        plaque(b, p0, u, nn, 0, L, Z_REPOS, Z_REPOS + 0.12, Z_REPOS + 0.12, 0, 0.03, M_CELADON)
        plaque(b, p0, u, nn, 0, L, Z_REPOS + 0.95, Z_REPOS + 1.02, Z_REPOS + 1.02, 0, 0.05, M_BLANC)
b.objet("palier_panneaux_cage")

# porte de la bibliothèque : chambranle, entablement, dessus-de-porte peint (marine), appliques (P17)
b = Bld(z0=Z_ETAGE)
P_POLY = [tuple(p) for p in PIECES["palier"]["polygone_interieur"]]
chambranles(None, P_POLY, Z_ETAGE, ouvertures_de("palier"), larg=0.16, bld=b)
plaque(b, Vector((-3.7, Y_CAGE_N, 0)), Vector((1, 0, 0)), Vector((0, 1, 0)), 3.7 - 1.05, 3.7 + 1.05,
       Z_ETAGE + 3.16, Z_ETAGE + 3.32, Z_ETAGE + 3.32, 0, 0.12, M_BLANC)
plaque(b, Vector((-3.7, Y_CAGE_N, 0)), Vector((1, 0, 0)), Vector((0, 1, 0)), 3.7 - 1.15, 3.7 + 1.15,
       Z_ETAGE + 3.32, Z_ETAGE + 3.4, Z_ETAGE + 3.4, 0, 0.18, M_BLANC)
b.objet("palier_porte_bibliotheque_decor")
m_cadre(1.2, 0.5, M_TOILE["marine"], c=0.05).objet("palier_dessus_de_porte", loc=(0.0, Y_CAGE_N + 0.005, Z_ETAGE + 3.55))
for sx in (-1, 1):
    instance("applique2", m_appliqe, "palier_applique_porte_%s" % ("est" if sx > 0 else "ouest"),
             (sx * 1.35, Y_CAGE_N + 0.005, Z_ETAGE + 2.3), 0.0)
# appliques sur les piliers des arcades, côté cage (P04, P05)
for k, (sx, y) in enumerate(((1, -3.375), (-1, -3.375), (1, 1.6), (-1, 1.6))):
    instance("applique2", m_appliqe, "palier_applique_%d" % (k + 1), (sx * 3.695, y, Z_ETAGE + 2.3), face_vers(-sx, 0))

# balustrades à balustres tournés dans les arcades ouvertes sur la volée (P04, P05, P15, P16)


def m_balustre(h=0.6):
    b = Bld()
    b.tour([(0.06, 0.0), (0.06, 0.05), (0.045, 0.08), (0.05, 0.12), (0.075, 0.22), (0.065, 0.3), (0.035, 0.42),
            (0.03, 0.47), (0.05, 0.5), (0.05, h - 0.05), (0.06, h - 0.05), (0.06, h), (0.0, h)], 0, 0, M_BLANC, n=12)
    return b


for o in ARCADES:
    if not o["garde_corps"]:
        continue
    s = 1 if o["centre"][0] > 0 else -1
    xb = o["centre"][0] - s * 0.15
    y0, y1 = o["centre"][1] - o["largeur"] / 2, o["centre"][1] + o["largeur"] / 2
    b = Bld()
    b.boite(xb - 0.13, y0, Z_ETAGE, xb + 0.13, y1, Z_ETAGE + 0.14, M_BLANC)
    b.boite(xb - 0.15, y0, Z_ETAGE + 0.78, xb + 0.15, y1, Z_ETAGE + 0.92, M_BLANC)
    b.objet("palier_balustrade_%s" % ("est" if s > 0 else "ouest"))
    nb = int(o["largeur"] / 0.2)
    for k in range(nb):
        y = y0 + (k + 0.5) * (y1 - y0) / nb
        instance("balustre", m_balustre, "palier_balustre_%s_%d" % ("est" if s > 0 else "ouest", k + 1),
                 (xb, y, Z_ETAGE + 0.14), 0.0, (1, 1, 0.64 / 0.6))

# coupole : caissons à filets gris-vert, oculi en demi-lune à petit-bois rayonnant, cadre du puits
CX, CY = 0.0, (Y_CAGE_N + Y_CAGE_S) / 2
AX, AY = 3.7, (Y_CAGE_S - Y_CAGE_N) / 2
T_PUITS = 0.3


def z_voute(t):
    if t <= T_PUITS:
        return Z_CLE
    return Z_NAISSANCE + (Z_CLE - Z_NAISSANCE) * math.sqrt(max(0.0, 1 - ((t - T_PUITS) / (1 - T_PUITS)) ** 2))


def t_de_z(z):
    a = (z - Z_NAISSANCE) / (Z_CLE - Z_NAISSANCE)
    return T_PUITS + (1 - T_PUITS) * math.sqrt(max(0.0, 1 - a * a))


def pt_face(face, t, w, retrait=0.015):
    """Point de l'intrados : face ('e','o','s','n'), t (1 = naissance), w ∈ [-1, 1] le long de la face."""
    if face in ("e", "o"):
        u, v = (t if face == "e" else -t), w * t
    else:
        u, v = w * t, (t if face == "s" else -t)
    p = Vector((CX + u * AX, CY + v * AY, z_voute(t)))
    d = Vector((CX, CY, Z_NAISSANCE)) - p
    return p + d.normalized() * retrait


b = Bld()
for f in ("e", "o", "s", "n"):
    def ligne(ts, ws, larg=0.05):
        pts = [pt_face(f, t, w) for t, w in zip(ts, ws)]
        b.polyligne(pts, larg, 0.02, M_GRISVERT)

    lin = lambda a, c, n=10: [a + (c - a) * k / n for k in range(n + 1)]
    # anneaux haut et bas, double filet
    for t in (0.92, 0.89, 0.36, 0.33):
        ligne([t] * 21, lin(-0.98, 0.98, 20), 0.035)
    # arêtiers (diagonales) : filets doubles
    for sw in (-1, 1):
        ligne(lin(0.33, 0.995, 14), [sw * 0.985] * 15, 0.06)
    # panneau central trapézoïdal avec chevron intérieur
    ligne([0.86, 0.86, 0.40, 0.40, 0.86], [-0.5, 0.5, 0.22, -0.22, -0.5], 0.04)
    ligne([0.82, 0.47, 0.82], [-0.32, 0.0, 0.32], 0.035)
    # panneaux latéraux triangulaires
    for sw in (-1, 1):
        ligne([0.86, 0.86, 0.42, 0.86], [sw * 0.58, sw * 0.92, sw * 0.9, sw * 0.58], 0.035)
b.objet("palier_coupole_caissons")

# oculi en demi-lune à la base de chaque face (P04, P06, P17)
b = Bld()
for f in ("e", "o", "s", "n"):
    R = 0.45
    demi = AY if f in ("e", "o") else AX
    centre = []
    n = 12
    # le demi-disque suit l'intrados : chaque point (w, h) est reporté à la hauteur h sur la voûte
    def pt(wm, h, retrait):
        t = t_de_z(Z_NAISSANCE + 0.02 + h)
        return pt_face(f, t, wm / (demi * t), retrait)
    ctr = b.v(pt(0.0, 0.0, 0.02))
    bord = [b.v(pt(R * math.cos(math.pi * k / n), R * math.sin(math.pi * k / n), 0.02)) for k in range(n + 1)]
    for k in range(n):
        b.face([ctr, bord[k], bord[k + 1]], M_VERRE_JOUR)
    arc_pts = [pt(R * math.cos(math.pi * k / n), R * math.sin(math.pi * k / n), 0.035) for k in range(n + 1)]
    b.polyligne(arc_pts, 0.06, 0.04, M_BLANC)
    b.poutre(pt(-R - 0.03, 0.0, 0.035), pt(R + 0.03, 0.0, 0.035), 0.06, 0.04, M_BLANC)
    for k in range(1, 6):
        a = math.pi * k / 6
        b.poutre(pt(0, 0, 0.03), pt(R * math.cos(a), R * math.sin(a), 0.03), 0.02, 0.02, M_BLANC)
    arc_in = [pt(R * 0.45 * math.cos(math.pi * k / n), R * 0.45 * math.sin(math.pi * k / n), 0.03) for k in range(n + 1)]
    b.polyligne(arc_in, 0.02, 0.02, M_BLANC)
    # archivolte autour de l'oculus
    arc_ext = [pt((R + 0.12) * math.cos(math.pi * k / n), (R + 0.12) * math.sin(math.pi * k / n), 0.03) for k in range(n + 1)]
    b.polyligne(arc_ext, 0.08, 0.05, M_BLANC)
b.objet("palier_coupole_oculi")

# cadre mouluré du puits de lumière
b = Bld()
a, bb = T_PUITS * AX, T_PUITS * AY
b.anneau(rect(CX - a - 0.02, CY - bb - 0.02, CX + a + 0.02, CY + bb + 0.02), -0.0, 0.10, Z_CLE - 0.10, Z_CLE - 0.005, M_BLANC)
b.anneau(rect(CX - a - 0.2, CY - bb - 0.2, CX + a + 0.2, CY + bb + 0.2), 0.0, 0.08, Z_CLE - 0.06, Z_CLE - 0.01, M_GRISVERT)
b.objet("palier_coupole_puits_cadre")

# sol du palier : bandes de marbre rouge le long de la trémie et des murs (P04, P05)
b = Bld()
bandes_sol(b, [(P_POLY, 0.1, 0.1)], [], Z_ETAGE)
b.objet("palier_bandes_sol")
# guéridon et bouquet près de la porte de la bibliothèque (P05)
b = Bld()
b.tour([(0.0, 0.76), (0.23, 0.76), (0.23, 0.8), (0.0, 0.8)], 0, 0, M_MERISIER, n=20)
for k in range(3):
    a = 2 * math.pi * k / 3
    x, y = 0.15 * math.cos(a), 0.15 * math.sin(a)
    b.tour([(0.02, 0.0), (0.03, 0.15), (0.018, 0.3), (0.028, 0.5), (0.018, 0.76)], x, y, M_MERISIER, n=8)
b.tour([(0.12, 0.25), (0.12, 0.27), (0.0, 0.27)], 0, 0, M_MERISIER, n=12)
b.objet("palier_gueridon", loc=(-1.6, -4.7, Z_ETAGE))
m_vase_fleurs(0.55, pot=materiau("ceramique_celadon", (0.45, 0.58, 0.52), 0.2)).objet(
    "palier_bouquet_roses", loc=(-1.6, -4.7, Z_ETAGE + 0.8))

# galeries est et ouest : panneaux, corniche, bandes de sol, chambranles, lanternes (P05, P09)
for cote, sx in (("est", 1), ("ouest", -1)):
    pid = "galerie_" + cote
    G = PIECES[pid]
    poly = [tuple(p) for p in G["polygone_interieur"]]
    zplaf = Z_ETAGE + G["hauteur_sous_plafond"]
    ouv = ouvertures_de(pid)
    b = Bld(z0=Z_ETAGE)
    corniche(b, poly, zplaf, h=0.3, saillie=0.2)
    chambranles(None, poly, Z_ETAGE, ouv, larg=0.15, bld=b)
    bandes_sol(b, [(poly, 0.1, 0.1)], [], Z_ETAGE)
    for i, (p0, p1, u, nn, L) in enumerate(aretes(poly)):
        ov = ouv_sur_arete(p0, u, nn, L, ouv)
        for s0, s1, _, _ in morceaux(L, ov, 0, 1):
            if s1 - s0 < 0.5:
                continue
            nb = max(1, int((s1 - s0) / 1.6))
            for k in range(nb):
                a0 = s0 + (s1 - s0) * k / nb + 0.18
                a1 = s0 + (s1 - s0) * (k + 1) / nb - 0.18
                if a1 - a0 > 0.3:
                    table(b, p0, u, nn, a0, a1, Z_ETAGE + 0.25, Z_ETAGE + 0.95)
                    table(b, p0, u, nn, a0, a1, Z_ETAGE + 1.25, zplaf - 0.6)
        plaque(b, p0, u, nn, 0, L, Z_ETAGE, Z_ETAGE + 0.12, Z_ETAGE + 0.12, 0, 0.02, M_GRISVERT)
    b.objet(pid + "_decor")
    yl = -2.2
    instance("lanterne", m_lanterne, pid + "_lanterne", (sx * 4.9, yl, zplaf), 0.0)
    lumiere("lumiere_%s_lanterne" % pid, (sx * 4.9, yl, zplaf - 1.2), 60, 0.1)
    m_cadre(0.5, 0.7, M_TOILE["sombre"] if sx < 0 else M_TOILE["marine"], c=0.05).objet(
        pid + "_tableau", loc=(sx * 5.5 - sx * 0.005, -1.4, Z_ETAGE + 1.5), rot=face_vers(-sx, 0))

# ==============================================================================================
# PASSAGES SOUS LES VOLÉES DE RETOUR (P23, P24, P42)
# ==============================================================================================
log("passages…")


def z_sous_volee(x, y):
    """Sous-face rampante de la volée de retour, puis dessous du palier d'arrivée."""
    if y >= Y_REPOS:
        return Z_REPOS - EP_REPOS
    return min(Z_SOUS_DALLE, Z_REPOS - EP_REPOS + (Y_REPOS - y) / (Y_REPOS - Y_ARRIVEE) * (Z_SOUS_DALLE - Z_REPOS + EP_REPOS))


def z_volee_c(y):
    """Dessus de la volée centrale (nez de marche) au droit de y."""
    k = int((y - Y_DEPART) / G_C) + 1
    return max(0.0, min(Z_REPOS, k * H_C))


for cote, sx in (("est", 1), ("ouest", -1)):
    pid = "passage_" + cote
    poly = [tuple(p) for p in PIECES[pid]["polygone_interieur"]]
    ouv = ouvertures_de(pid)
    # arêtes : on n'habille que le mur latéral (x = ±3,7)
    sauf = [i for i, (p0, p1, u, nn, L) in enumerate(aretes(poly)) if not (abs(abs(p0.x) - 3.7) < 1e-3 and abs(abs(p1.x) - 3.7) < 1e-3)]
    habiller(pid + "_murs", poly, 0.0, ouv, couches_damas(Z_SOUS_DALLE), ztop=z_sous_volee, sauf=sauf)
    b = Bld()
    chambranles(None, poly, 0.0, ouv, dessus=(3.15, 0.5), bld=b)
    # flanc de la volée centrale laissé ouvert : le dessous du grand escalier est vide (demande du 19/11)
    bandes_sol(b, [], [(sx * 1.9 - 0.06, -3.25, sx * 1.9 + 0.06, 1.24) if sx > 0 else (-1.96, -3.25, -1.84, 1.24),
                       (sx * 3.1 - 0.06, -3.25, sx * 3.1 + 0.06, 1.24) if sx > 0 else (-3.16, -3.25, -3.04, 1.24),
                       (min(sx * 1.25, sx * 3.7), -1.06, max(sx * 1.25, sx * 3.7), -0.94)], 0.0)
    b.objet(pid + "_decor")

# passage est : console Louis XVI laquée blanche, miroir, statuette-candélabre, tableau étroit, poteaux (P42)
r_e = face_vers(-1, 0)
m_console_demilune(M_MARBRE_B, M_LAQUE_BLANC, dore=False).objet("passage_est_console", loc=(3.7 - 0.225, -2.2, 0.0), rot=r_e)
m_miroir(0.75, 1.6).objet("passage_est_miroir", loc=(3.7 - 0.006, -2.2, 1.2), rot=r_e)
instance("statuette", lambda: m_candelabre(4, 0.75, True), "passage_est_candelabre", (3.7 - 0.2, -2.2, 0.85), r_e)
m_cadre(0.35, 0.6, M_TOILE["sombre"], c=0.04).objet("passage_est_tableau", loc=(3.7 - 0.005, 0.45, 1.6), rot=r_e)
b = Bld()
for y in (-2.9, -1.6):
    b.tour([(0.16, 0.0), (0.16, 0.02), (0.04, 0.05), (0.025, 0.1), (0.025, 0.88), (0.035, 0.92), (0.04, 0.97), (0.0, 1.0)],
           1.55, y, M_LAITON, n=12)
pts = [(1.55, -2.9 + k * 1.3 / 8, 0.9 - 0.12 * math.sin(math.pi * k / 8)) for k in range(9)]
for p, q in zip(pts[:-1], pts[1:]):
    b.tube(p, q, 0.02, M_VELOURS_SIEGE, 8)
b.objet("passage_est_poteaux_cordon")
# desserte acajou contre le flanc de la volée, lanternes en rotin, piles de linge (P26)
b = Bld()
L_, P_, H_ = 1.4, 0.45, 0.9
for yy in (-L_ / 2 + 0.04, L_ / 2 - 0.04):
    for xx in (-P_ / 2 + 0.04, P_ / 2 - 0.04):
        b.tour([(0.025, 0.0), (0.03, 0.1), (0.022, 0.3), (0.032, 0.45), (0.022, 0.6), (0.03, H_ - 0.05)], xx, yy,
               M_ACAJOU, n=8)
b.boite(-P_ / 2, -L_ / 2, H_ - 0.15, P_ / 2, L_ / 2, H_, M_ACAJOU)
for z in (0.15, 0.45):
    b.boite(-P_ / 2 + 0.02, -L_ / 2 + 0.02, z, P_ / 2 - 0.02, L_ / 2 - 0.02, z + 0.025, M_ACAJOU)
for k, z in enumerate((0.175, 0.475)):
    for j in range(3):
        b.boite(-0.15, -0.55 + j * 0.4, z, 0.15, -0.25 + j * 0.4, z + 0.12 + 0.03 * (j % 2),
                M_TISSU_CREME if (j + k) % 2 else M_FAIENCE)
for j in range(3):
    b.tour([(0.0, 0.0), (0.09, 0.03), (0.12, 0.15), (0.11, 0.3), (0.06, 0.4), (0.0, 0.42)], 0.0, -0.45 + j * 0.35,
           M_ROTIN, n=10, z0=H_)
b.objet("passage_est_desserte", loc=(X_VC + P_ / 2 + 0.02, 0.2, 0.0))

# passage ouest : console galbée noyer, miroir haut, candélabre, vase d'eucalyptus, fusil (P23, P24)
r_w = face_vers(1, 0)
m_console_galbee(M_MARBRE_B, M_NOYER).objet("passage_ouest_console", loc=(-3.7 + 0.225, -2.3, 0.0), rot=r_w)
m_miroir(0.6, 1.6).objet("passage_ouest_miroir", loc=(-3.7 + 0.006, -2.3, 1.2), rot=r_w)
instance("candelabre5", lambda: m_candelabre(5, 0.6, False), "passage_ouest_candelabre", (-3.7 + 0.22, -2.55, 0.85), r_w)
m_vase_fleurs(0.8, pot=M_VERRE, fleur=M_FEUILLE, larg=0.5).objet("passage_ouest_eucalyptus", loc=(-3.7 + 0.22, -2.05, 0.85))
instance("fusil", m_fusil, "passage_ouest_fusil", (-3.7 + 0.006, -3.0, 1.6), r_w)
instance("applique2", m_appliqe, "passage_ouest_applique", (-3.7 + 0.005, 0.2, 2.2), r_w)

# ==============================================================================================
# PETIT SALON SOUS LE REPOS (P25, P26)
# ==============================================================================================
log("petit salon…")
PS = PIECES["petit_salon"]
ps_poly = [tuple(p) for p in PS["polygone_interieur"]]
ps_ouv = ouvertures_de("petit_salon")
H_PS = Z_REPOS - EP_REPOS
aretes_ps = list(aretes(ps_poly))
i_sud = [i for i, a in enumerate(aretes_ps) if abs(a[0].y - 3.65) < 1e-3 and abs(a[1].y - 3.65) < 1e-3]
i_nord = [i for i, a in enumerate(aretes_ps) if abs(a[0].y - 1.24) < 1e-3 and abs(a[1].y - 1.24) < 1e-3]
# murs est et ouest : damas et soubassement ; mur sud : enduit uni, cimaise céladon à 0,9 m (P25)
habiller("petit_salon_murs", ps_poly, 0.0, ps_ouv, couches_damas(H_PS - 0.02),
         sauf=i_sud + i_nord)
b = Bld()
habiller(None, ps_poly, 0.0, ps_ouv, [(0.0, 0.14, M_CELADON, 0.0, 0.02), (0.88, 0.92, M_CELADON, 0.0, 0.03)],
         sauf=[i for i in range(len(aretes_ps)) if i not in i_sud], bld=b)
chambranles(None, ps_poly, 0.0, ps_ouv, larg=0.12, bld=b)
# dos de la volée centrale (x ±1,25) vu du petit salon : soubassement et damas
for x0, x1 in ((-1.25, 1.25),):
    b.boite(x0, 1.24, 0.0, x1, 1.26, 1.0, M_SOUB)
    b.boite(x0, 1.24, 1.0, x1, 1.245, H_PS - 0.01, M_DAMAS)
# plafond bas : caissons moulurés et spots encastrés (P25)
for (x0, x1) in ((-3.5, -1.3), (-1.1, 1.1), (1.3, 3.5)):
    b.anneau(rect(x0, 1.45, x1, 3.45), 0.0, 0.06, H_PS - 0.035, H_PS - 0.005, M_BLANC)
for x in (-2.4, 0.0, 2.4):
    b.tour([(0.0, -0.004), (0.045, -0.004), (0.045, 0.0), (0.0, 0.0)], x, 2.45, M_AMPOULE, n=10, z0=H_PS - 0.002)
bandes_sol(b, [(ps_poly, 0.3, 0.12)], [(-0.06, 1.54, 0.06, 3.35)], 0.0)
b.objet("petit_salon_decor")
# fontaine murale : dosseret de marbre vert cintré, mufle de lion, vasque sur pied (P25)
b = Bld()
ys = 3.65
prof = [(-0.3, 0.75), (0.3, 0.75), (0.3, 1.75)] + [(0.3 * math.cos(math.pi * k / 10), 1.75 + 0.15 * math.sin(math.pi * k / 10))
                                                  for k in range(1, 10)] + [(-0.3, 1.75)]
vs0 = [b.v((x, ys, z)) for x, z in prof]
vs1 = [b.v((x, ys - 0.06, z)) for x, z in prof]
n = len(prof)
for k in range(n):
    j = (k + 1) % n
    b.face([vs0[k], vs0[j], vs1[j], vs1[k]], M_MARBRE_V)
b.face(vs1, M_MARBRE_V)
b.face(list(reversed(vs0)), M_MARBRE_V)
b.tour([(0.0, -0.1), (0.1, -0.08), (0.12, 0.0), (0.09, 0.09), (0.0, 0.11)], 0, ys - 0.08, M_PIERRE, n=12, z0=1.42)
b.tube((0, ys - 0.12, 1.36), (0, ys - 0.25, 1.30), 0.012, M_LAITON, 6)
b.tour([(0.08, 0.0), (0.06, 0.05), (0.05, 0.6), (0.08, 0.68), (0.25, 0.80), (0.27, 0.86), (0.22, 0.86), (0.0, 0.82)],
       0, ys - 0.3, M_PIERRE, n=16)
b.objet("petit_salon_fontaine")
# panoplie de sabres sur panneau d'acajou, assiettes de faïence (P25)
b = Bld()
b.boite(-0.62, ys - 0.03, 2.05, 0.62, ys - 0.005, 2.7, M_ACAJOU)
for k in range(4):
    z = 2.15 + k * 0.13
    b.polyligne([(-0.42 + 0.02 * k, ys - 0.04, z), (0.0, ys - 0.04, z + 0.04), (0.42, ys - 0.04, z + 0.0)], 0.03, 0.006, M_ACIER)
    b.boite(-0.5 + 0.02 * k, ys - 0.05, z - 0.02, -0.42 + 0.02 * k, ys - 0.03, z + 0.03, M_LAITON)
for x in (0.47, 0.53):
    b.boite(x - 0.012, ys - 0.045, 2.12, x + 0.012, ys - 0.035, 2.62, M_ACIER)
b.objet("petit_salon_panoplie")
for k, (x, z) in enumerate(((-1.0, 2.55), (-1.0, 2.2), (-0.95, 1.85), (1.0, 2.55), (1.0, 2.2), (0.95, 1.85))):
    b = Bld()
    b.tube((x, ys - 0.002, z), (x, ys - 0.02, z), 0.125, M_FAIENCE, 16, r1=0.1)
    b.tube((x, ys - 0.021, z), (x, ys - 0.022, z), 0.05, materiau("faience_decor", (0.25, 0.35, 0.6), 0.3) if k == 0 else
           MATS["faience_decor"], 10)
    b.objet("petit_salon_assiette_%d" % (k + 1))
# mobilier : table ronde, fauteuils Louis XV rouges et olive, chaise gondole, chevet noir, piano droit.
# Le salon est traversé depuis les passages sous les volées de retour vers les portes du salon (x ±2,6) :
# rien entre x ±2,0 et ±3,3 hors du piano adossé au mur.
b = Bld()
b.tour([(0.0, 0.47), (0.5, 0.47), (0.5, 0.5), (0.0, 0.5)], 0, 0, M_MARBRE_B, n=28)
b.tour([(0.45, 0.38), (0.45, 0.47), (0.0, 0.47)], 0, 0, M_LAQUE_GRIS, n=20)
for k in range(4):
    a = math.pi / 4 + k * math.pi / 2
    b.tour([(0.03, 0.0), (0.035, 0.05), (0.025, 0.38)], 0.36 * math.cos(a), 0.36 * math.sin(a), M_LAQUE_GRIS, n=8)
b.tour([(0.0, 0.5), (0.28, 0.5), (0.3, 0.52), (0.0, 0.52)], 0, 0, M_ACIER, n=20)
b.objet("petit_salon_table_ronde", loc=(1.15, 2.45, 0.0))
instance("fauteuil_rouge", lambda: m_fauteuil(M_VELOURS_SIEGE, M_LAQUE_BLANC), "petit_salon_fauteuil_1",
         (1.3, 1.62, 0.0), face_vers(-0.2, 1))
instance("fauteuil_rouge", None, "petit_salon_fauteuil_2", (0.35, 2.2, 0.0), face_vers(1, 0.3))
instance("fauteuil_olive", lambda: m_fauteuil(M_OLIVE, M_LAQUE_GRIS), "petit_salon_fauteuil_3", (1.75, 3.1, 0.0),
         face_vers(-0.6, -1))
instance("chaise_gondole", lambda: m_fauteuil(M_TISSU_GRIS, M_LAQUE_GRIS, bras=False), "petit_salon_chaise_gondole",
         (-1.45, 2.85, 0.0), face_vers(-1, 0))
b = Bld()
b.boite(-0.25, -0.18, 0.08, 0.25, 0.18, 0.6, M_LAQUE_NOIR)
for sx in (-1, 1):
    for sy in (-1, 1):
        b.boite_c(sx * 0.21, sy * 0.14, 0, 0.04, 0.04, 0.08, M_LAQUE_NOIR)
b.boite(-0.03, 0.18, 0.45, 0.03, 0.2, 0.47, M_LAITON)
b.objet("petit_salon_chevet", loc=(-0.6, 3.45, 0.0), rot=0.0)
m_cadre(0.8, 0.6, M_TOILE["chateau"], c=0.06).objet("petit_salon_tableau_chateau", loc=(3.7 - 0.005, 2.45, 1.55),
                                                    rot=face_vers(-1, 0))
b = Bld()
b.boite(-0.72, -0.3, 0.0, 0.72, 0.3, 1.25, M_ACAJOU)
b.boite(-0.72, 0.3, 0.68, 0.72, 0.55, 0.74, M_ACAJOU)
b.boite(-0.68, 0.3, 0.74, 0.68, 0.45, 0.76, M_FAIENCE)
for k in range(36):
    if k % 7 in (1, 2, 4, 5, 6):
        x = -0.66 + k * 0.0375
        b.boite(x + 0.01, 0.38, 0.765, x + 0.022, 0.44, 0.775, M_LAQUE_NOIR)
b.boite(-0.72, -0.3, 1.25, 0.72, 0.32, 1.28, M_ACAJOU)
for sx in (-1, 1):
    b.tube((sx * 0.68, 0.48, 0.0), (sx * 0.68, 0.48, 0.68), 0.03, M_ACAJOU, 8)
b.objet("petit_salon_piano", loc=(-3.7 + 0.3, 1.9, 0.0), rot=face_vers(1, 0))
instance("candelabre_argent", lambda: m_candelabre(3, 0.5, False), "petit_salon_candelabre_1", (-3.5, 1.5, 1.28), 0.0)
instance("candelabre_argent", None, "petit_salon_candelabre_2", (-3.5, 2.3, 1.28), 0.0)
m_cadre(0.45, 0.6, M_TOILE["sombre"], c=0.05).objet("petit_salon_tableau_piano", loc=(-3.7 + 0.005, 1.9, 1.75),
                                                    rot=face_vers(1, 0))

# ==============================================================================================
# COULOIRS EST ET OUEST (P22, P36, W08)
# ==============================================================================================
log("couloirs…")
for cote, sx in (("est", 1), ("ouest", -1)):
    pid = "couloir_" + cote
    C = PIECES[pid]
    poly = [tuple(p) for p in C["polygone_interieur"]]
    hc = C["hauteur_sous_plafond"]
    fen = [dict(c=(sx * x, -8.15), l=1.35, zb=0.45, zh=3.70, arc=False, nom="fenetre_%s" % x) for x in (5.1, 8.7)]
    ouv = ouvertures_de(pid, fen)
    habiller(pid + "_murs", poly, 0.0, ouv, couches_damas(hc - 0.02))
    b = Bld()
    chambranles(None, poly, 0.0, [o for o in ouv if not o["nom"].startswith("fenetre")], dessus=(hc - 0.3, 0.6), bld=b)
    corniche(b, poly, hc, h=0.28, saillie=0.2)
    # plafond : panneau mouluré rectangulaire (P36)
    xs = [p[0] for p in poly]
    b.anneau(rect(min(xs) + 0.35, -7.85, max(xs) - 0.35, -6.8), 0.0, 0.07, hc - 0.04, hc - 0.005, M_BLANC)
    b.anneau(rect(min(xs) + 0.55, -7.7, max(xs) - 0.55, -6.95), 0.0, 0.03, hc - 0.025, hc - 0.005, M_BLANC)
    # embrasures des portes-fenêtres : chambranle intérieur
    for x in (5.1, 8.7):
        xx = sx * x
        b.boite(xx - 0.8, -8.15, 0.42, xx + 0.8, -8.0, 0.45, M_BLANC)
        for s in (-1, 1):
            b.boite(xx + s * 0.675, -8.15, 0.45, xx + s * 0.8, -8.12, 3.82, M_BLANC)
        b.boite(xx - 0.8, -8.15, 3.70, xx + 0.8, -8.12, 3.82, M_BLANC)
    bandes_sol(b, [(poly, 0.12, 0.12)], [], 0.0)
    b.objet(pid + "_decor")
    # voilages et tringles
    for x in (5.1, 8.7):
        xx = sx * x
        instance("voilage", lambda: m_rideau(1.35, 3.25, plis=10, ampl=0.03, mat=M_VOILE),
                 "%s_voilage_%d" % (pid, int(x * 10)), (xx, -8.15 + 0.06, 0.45), 0.0)
        bb = Bld()
        bb.tube((xx - 0.8, -8.15 + 0.06, 3.76), (xx + 0.8, -8.15 + 0.06, 3.76), 0.012, M_LAITON, 6)
        bb.objet("%s_tringle_%d" % (pid, int(x * 10)))
    instance("radiateur", m_radiateur, pid + "_radiateur", (sx * 6.9, -8.15 + 0.12, 0.0))
    instance("lanterne", m_lanterne, pid + "_lanterne", (sx * 7.4, -7.32, hc), 0.0)
    lumiere("lumiere_%s_lanterne" % pid, (sx * 7.4, -7.32, hc - 1.15), 80, 0.1)

# couloir ouest : fauteuils cabriolet à tissu imprimé le long des murs (P22, P41)
for k, (x, y, d) in enumerate(((-6.15, -7.85, (0, 1)), (-7.65, -7.85, (0, 1)), (-6.1, -6.8, (0, -1)), (-9.3, -6.8, (0, -1)))):
    o = asset_ph("polyhaven-ArmChair_01", "ArmChair_01_1k.gltf", "couloir_ouest_fauteuil_%d" % (k + 1), (x, y, 0.0),
                 face_vers(*d), 0.9)
    if o is None:
        instance("cabriolet", lambda: m_fauteuil(M_TISSU_IMPR, M_LAQUE_GRIS), "couloir_ouest_fauteuil_%d" % (k + 1),
                 (x, y, 0.0), face_vers(*d))
m_cadre(0.6, 0.45, M_TOILE["chateau"], c=0.05).objet("couloir_ouest_tableau", loc=(-10.5 + 0.005, -7.3, 1.9),
                                                    rot=face_vers(1, 0))
# couloir est : plaque de porte (P36)
b = Bld()
b.boite(7.4 + 0.25, -6.5 - 0.012, 1.45, 7.4 + 0.4, -6.5, 1.65, materiau("plaque_bleue", (0.1, 0.2, 0.6), 0.4))
b.objet("couloir_est_plaque")

# ----------------------------------------------------------------------------------------------
# Vérifications : dégagement devant les portes (≥ 0,8 m) et objets au sol
# ----------------------------------------------------------------------------------------------
bpy.context.view_layer.update()


def bbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs),
            max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))


MOBILIER = [o for o in COL.objects if o.type == "MESH" and not any(k in o.name for k in (
    "_murs", "_decor", "bandes", "tapis", "paillasson", "lustre", "lanterne", "rideau", "voilage", "tringle", "miroir",
    "tableau", "gravure", "fusil", "applique", "coupole", "arcades", "panneaux", "rampes", "barres", "departs",
    "tapisserie", "balustr", "colonne", "assiette", "panoplie", "fontaine", "dessus", "plaque", "affiche", "brochures",
    "bouquet", "lampe", "candelabre", "eucalyptus"))]
alertes = []
for pid in ("vestibule", "petit_salon", "passage_est", "passage_ouest", "couloir_est", "couloir_ouest", "palier",
            "galerie_est", "galerie_ouest"):
    P = PIECES[pid]
    z0 = P["z_sol"]
    for o in P["portes"]:
        if o["type"] == "arcade" and o["garde_corps"]:
            continue
        cx, cy = o["centre"][:2]
        l = o["largeur"] if o["vantaux"] or o["largeur"] < 1.8 else 0.9   # baie large : couloir de 0,9 m au centre
        if "x =" in o["mur"]:
            zone = (cx - 0.3 - 0.8, cy - l / 2, cx + 0.3 + 0.8, cy + l / 2)
        else:
            zone = (cx - l / 2, cy - 0.3 - 0.8, cx + l / 2, cy + 0.3 + 0.8)
        for m in MOBILIER:
            x0, y0, zz0, x1, y1, zz1 = bbox(m)
            if zz1 < z0 + 0.05 or zz0 > z0 + 2.0:
                continue
            if x0 < zone[2] and x1 > zone[0] and y0 < zone[3] and y1 > zone[1]:
                alertes.append("%s devant %s" % (m.name, o["nom"]))
for a in sorted(set(alertes)):
    log("DÉGAGEMENT :", a)

# ----------------------------------------------------------------------------------------------
# Rendus de contrôle : coque et bati importés (contexte, non exportés)
# ----------------------------------------------------------------------------------------------
def regler_rendu():
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            SC.render.engine = eng
            break
        except TypeError:
            continue
    try:
        SC.eevee.taa_render_samples = 16
        SC.eevee.use_shadows = True
    except Exception:
        pass
    try:
        SC.eevee.use_raytracing = False
    except Exception:
        pass
    w = bpy.data.worlds.new("ciel")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.8
    SC.world = w
    try:
        SC.view_settings.view_transform = "AgX"
        SC.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass


def retourner(chemin):
    """Retourne l'image horizontalement : rendu D-003 → vue réelle (miroir Y, D-026)."""
    im = bpy.data.images.load(chemin, check_existing=False)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)[:, ::-1].copy()
    im.pixels.foreach_set(a.ravel())
    im.filepath_raw = chemin
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def camera(nom, pos, cible, focale):
    cam = bpy.data.cameras.new(nom)
    cam.lens = focale
    cam.sensor_fit = "VERTICAL"
    cam.sensor_height = 24
    cam.clip_start = 0.05
    cam.clip_end = 200
    co = bpy.data.objects.new(nom, cam)
    co.location = pos
    d = Vector(cible) - Vector(pos)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    CTX.objects.link(co)
    return co


if not SANS_RENDU:
    log("rendus…")
    regler_rendu()
    lc = bpy.context.view_layer.layer_collection.children["contexte_rendu"]
    bpy.context.view_layer.active_layer_collection = lc
    avant = set(bpy.data.objects)
    for nom in ("coque", "bati"):
        p = os.path.join(EXPORT, nom + ".glb")
        if os.path.exists(p):
            bpy.ops.import_scene.gltf(filepath=p)
    for ob in set(bpy.data.objects) - avant:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        CTX.objects.link(ob)
    soleil = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", "SUN"))
    soleil.data.energy = 3.5
    soleil.data.angle = math.radians(2)
    soleil.rotation_euler = (math.radians(38), math.radians(10), math.radians(205))
    CTX.objects.link(soleil)
    # éclairage d'ambiance par pièce (rendus seulement)
    for pid in ("vestibule", "petit_salon", "passage_est", "passage_ouest", "couloir_est", "couloir_ouest", "palier",
                "galerie_est", "galerie_ouest"):
        P = PIECES[pid]
        xs = [q[0] for q in P["polygone_interieur"]]
        ys = [q[1] for q in P["polygone_interieur"]]
        hsp = P["hauteur_sous_plafond"]
        h = hsp if not isinstance(hsp, dict) else (hsp["min"] or 3.0)
        li = bpy.data.lights.new("amb_" + pid, "AREA")
        li.shape = "RECTANGLE"
        li.size, li.size_y = max(0.5, max(xs) - min(xs) - 0.4), max(0.5, max(ys) - min(ys) - 0.4)
        li.energy = 18 * li.size * li.size_y
        li.color = (1.0, 0.94, 0.85)
        lo = bpy.data.objects.new("amb_" + pid, li)
        lo.location = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, P["z_sol"] + h - 0.15)
        CTX.objects.link(lo)
    lp = bpy.data.lights.new("amb_puits", "AREA")
    lp.size, lp.size_y, lp.energy = 2.2, 2.6, 1200
    lpo = bpy.data.objects.new("amb_puits", lp)
    lpo.location = (CX, CY, Z_CLE - 0.15)
    CTX.objects.link(lpo)
    la = bpy.data.lights.new("amb_cage", "AREA")
    la.size, la.size_y, la.energy = 6.5, 8.0, 900
    lao = bpy.data.objects.new("amb_cage", la)
    lao.location = (0, CY, 9.8)
    CTX.objects.link(lao)

    VUES = [
        # (fichier, position, cible, focale, portrait, légende) — positions réelles en coordonnées D-003
        ("vestibule_P41", (0.0, -11.5, 1.55), (0.0, -3.0, 2.6), 13, True, "vestibule vers l'escalier depuis la porte d'entrée (≈ P41)"),
        ("vestibule_P20", (0.0, -1.9, 3.5), (0.0, -11.8, 0.7), 13, True, "vestibule vu de la volée centrale (≈ P20)"),
        ("vestibule_W08", (-2.4, -6.3, 1.5), (3.7, -6.8, 1.6), 14, False, "vestibule, mur est : vestiaire, porte du couloir, colonnes (≈ W08)"),
        ("escalier_P17", (0.5, 2.9, 5.0), (0.0, -5.0, 7.9), 11, True, "cage vue du repos vers le nord : rampes, coupole, porte de la bibliothèque (≈ P17)"),
        ("palier_P04", (0.0, -4.85, 6.95), (0.0, 3.0, 7.1), 13, True, "palier vers la tapisserie : balustres, oculus, caissons (≈ P04)"),
        ("palier_P05", (-1.8, -4.85, 6.95), (3.5, -0.5, 6.6), 13, True, "palier vers la galerie est : arcades, appliques, guéridon (≈ P05)"),
        ("passage_est_P42", (3.1, -4.4, 1.6), (2.4, 3.0, 1.9), 13, True, "passage est le long de la volée : console, miroir, rampe (≈ P42)"),
        ("passage_ouest_P24", (-2.2, -4.2, 1.6), (-2.7, 3.0, 1.9), 13, True, "passage ouest vers le petit salon : piano, fontaine (≈ P24)"),
        ("petit_salon_P25", (1.6, 1.45, 1.45), (-0.6, 3.65, 1.4), 12, True, "petit salon : fontaine, panoplie, assiettes, fauteuils (≈ P25)"),
        ("couloir_ouest_P22", (-1.5, -6.4, 1.6), (-10.5, -7.5, 1.9), 15, True, "vers le couloir ouest depuis le vestibule (≈ P22)"),
        ("couloir_est_P36", (10.0, -7.0, 1.6), (0.0, -7.5, 1.6), 14, True, "couloir est vers le vestibule (≈ P36)"),
        ("cage_W09", (0.0, -0.8, 11.6), (0.0, -0.7, 0.0), 11, False, "cage en plongée depuis la coupole (≈ W09)"),
    ]
    for fichier, pos, cible, f, portrait, leg in VUES:
        if SEULES and fichier not in SEULES.split(","):
            continue
        SC.render.resolution_x, SC.render.resolution_y = (750, 1000) if portrait else (1400, 735)
        if not portrait:
            pass
        cam = camera("cam_" + fichier, pos, cible, f)
        if not portrait:
            cam.data.sensor_fit = "HORIZONTAL"
            cam.data.sensor_width = 36
        SC.camera = cam
        chemin = os.path.join(RENDUS, "%s_%s.png" % (ID, fichier))
        SC.render.filepath = chemin
        t = time.time()
        bpy.ops.render.render(write_still=True)
        retourner(chemin)
        log("rendu", fichier, "%.1fs" % (time.time() - t))

# ----------------------------------------------------------------------------------------------
# Export (collection du composant seule, lumières comprises)
# ----------------------------------------------------------------------------------------------
for ob in list(CTX.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
bpy.data.collections.remove(CTX)
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)
lc = bpy.context.view_layer.layer_collection.children[ID]
bpy.context.view_layer.active_layer_collection = lc
glb = os.path.join(EXPORT, ID + ".glb")
kw = dict(filepath=glb, export_format="GLB", use_active_collection=True, export_apply=True, export_yup=True,
          export_lights=True)
for extra in (dict(export_image_format="JPEG", export_jpeg_quality=88), dict(export_image_format="JPEG"), {}):
    try:
        bpy.ops.export_scene.gltf(**kw, **extra)
        break
    except TypeError as ex:
        log("export :", ex)
log("glb :", glb, "%.1f Mo" % (os.path.getsize(glb) / 1e6))
uniq = {o.data.name: o.data for o in COL.objects if o.type == "MESH"}
log("objets :", len(COL.objects), "maillages :", len(uniq), "faces :", sum(len(m.polygons) for m in uniq.values()),
    "lumières :", ", ".join(LUMIERES))
try:
    bpy.ops.file.pack_all()
except RuntimeError as ex:
    log("pack_all :", ex)
blend = os.path.join(EXPORT, ID + ".blend")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
log("fin")

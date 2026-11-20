"""Composant P4.coque : coque intérieure RDC + étage (planchers, plafonds, refends et cloisons percés,
cage et escalier impérial praticable, coupole, garde-corps, vantaux de portes animables).

blender -b --factory-startup --python scripts/composants/coque.py
→ export/composants/coque.glb, export/composants/coque.blend, rendus/coque*.png, travail/coque.json

Repère D-003 : mètres, +X est, +Y sud (jardin), Z haut, RDC = 0. Plans validés D-019 (scripts/plan_p3.py).
Les murs extérieurs sont faits par bati.py : la coque s'arrête au nu intérieur (nu du gabarit − 0,60 m).
"""
import json
import math
import os
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Vector

T0 = time.time()
try:
    RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    RACINE = os.path.expanduser("~/IdeaProjects/chateau-saint-victor")
ID = "coque"
# COQUE_SORTIE : dossier d'export (relevé du 19/11 contrôlé à part avant de remplacer export/composants)
EXPORT = os.environ.get("COQUE_SORTIE") or os.path.join(RACINE, "export", "composants")
TEXDIR = os.path.join(EXPORT, ID + "_textures")
RENDUS = os.path.join(RACINE, "rendus")
ASSETS = os.path.join(RACINE, "assets")
import shutil
shutil.rmtree(TEXDIR, ignore_errors=True)
for d in (EXPORT, TEXDIR, RENDUS):
    os.makedirs(d, exist_ok=True)

G = json.load(open(os.path.join(RACINE, "travail", "gabarit.json")))
sys.path.insert(0, os.path.join(RACINE, "scripts"))
import plan_p3  # noqa: E402  (pièces et liaisons du plan validé, sans effet de bord à l'import)


def log(*a):
    print("[coque %5.1fs]" % (time.time() - T0), *a)
    sys.stdout.flush()


# ----------------------------------------------------------------------------------------------
# Niveaux et épaisseurs
# ----------------------------------------------------------------------------------------------
EP_EXT = 0.60                 # murs extérieurs (bati.py) : nu intérieur = nu − 0,60
Z_RDC = 0.0
Z_ETAGE = G["niveaux"]["etage_sol"]["valeur"]     # 5,35
Z_ATTIQUE = G["niveaux"]["attique_sol"]["valeur"]  # 10,30
DALLE_ETAGE = 0.30            # plancher d'étage : 5,05 → 5,35
Z_SOUS_DALLE = Z_ETAGE - DALLE_ETAGE
Z_DALLE_RDC = -0.30           # dalle du RDC sur le soubassement
# Relevé du 19/11 (travail/releve-2026-11-19/plan-mesure.json, plans d'évacuation R07/R03/R18) : la cage
# n'est plus couverte par une coupole sur toute sa profondeur. Les combles passent au-dessus du palier et
# de la bande sud ; la voûte occupe le noyau central de R18.
Z_DESSOUS_COMBLES = Z_ATTIQUE - 0.22  # sous-face de la dalle des combles (piece_combles.py, combles.json)
Z_NAISSANCE = 10.00           # naissance de la voûte et plafonds plats de la cage, sous la dalle des combles
Z_CLE = 12.00                 # sommet de la voûte (bord du puits de lumière)

R6, R5, C2, C3 = 0.60, 0.50, 0.20, 0.30  # refends épais, refends de cage, cloisons, murs de 30

# Axes du relevé (plan-mesure.json, précision 0,3 m sur refends, 0,5 m sur circulations ouvertes)
XC, XA = 3.30, 10.30          # refends de la cage et des ailes
Y_COULOIR = -2.95             # couloirs nord / salles sud du RDC (R07 : 27, 40 / 35, 37)
Y_SALON = 3.65                # petit salon / salon (seuil 36)
Y_TAPISSERIE = 2.85           # mur sud de la cage à l'étage (tapisserie R22)
Y_BIBLIO = -3.15              # mur sud de la bibliothèque (41)
Y_PALIER_S = -1.45            # arrivée des volées de retour, bord de la trémie
Y_GAL_N, Y_GAL_S = -0.75, 0.70  # circulations transversales 50 et 55
X_GAL_E, X_GAL_O = 5.50, -5.60  # cloisons 42/43 et 58/57
Y_TREMIE_CB = -1.95           # cloison nord du volume de l'escalier des combles (salle 43)

# Escalier impérial (D-013, D-014) : volée centrale de 19 contremarches vers le repos adossé au mur sud
# de la cage, puis deux volées de retour de 11 contremarches vers le palier nord de l'étage.
Z_REPOS = 3.40
N_C, G_C = 19, 0.25           # volée centrale (R03 : emprise de 4,6 m)
N_R = 11                      # volées de retour
Y_DEPART = -3.20              # première contremarche, au droit de l’écran à colonnes (P41)
Y_REPOS = Y_DEPART + (N_C - 1) * G_C          # 1,30 : nez du repos
Y_ARRIVEE = Y_PALIER_S                        # -1,45 : arrivée des volées de retour
G_R = (Y_REPOS - Y_ARRIVEE) / (N_R - 1)       # 0,275
H_C = Z_REPOS / N_C
H_R = (Z_ETAGE - Z_REPOS) / N_R
X_VC = 0.95                   # demi-largeur de la volée centrale (limons compris)
X_VR0, X_VR1 = 1.55, XC - R6 / 2  # volées de retour : limon intérieur, mur de cage
EP_REPOS = 0.25
Y_CAGE_S = Y_TAPISSERIE - C3 / 2  # nu du mur sud de la cage (tapisserie)
Y_CAGE_N_ETAGE = Y_PALIER_S
Y_ECRAN = -3.45               # écran à colonnes vestibule / cage (RDC, seuil 26)
# Voûte limitée au noyau central des combles (R18) ; plafonds plats au nord (palier) et au sud (repos)
Y_NOYAU_N, Y_NOYAU_S = Y_PALIER_S, 1.50
X_CAGE_INT = XC - R6 / 2

# Escalier de service vers les combles (piece_combles.py, combles.json) : volumes à laisser libres
_CB = json.load(open(os.path.join(RACINE, "travail", "releve-2026-11-19", "combles.json")))["escalier_service"]
EXCL_ETAGE = [_CB["rect_volee_haute"], _CB["rect_volee_basse"], _CB["rect_demi_palier"]]

# ----------------------------------------------------------------------------------------------
# Géométrie 2D
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


def nettoyer(poly, eps=1e-6):
    out = []
    for p in poly:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    chg = True
    while chg and len(out) > 3:
        chg = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-9:
                out.pop(i)
                chg = True
                break
    return out


def decouper(poly, rect):
    """Sutherland-Hodgman : polygone (éventuellement concave) ∩ rectangle."""
    x0, y0, x1, y1 = rect
    for dedans, inter in (
        (lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
        (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
        (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1)),
    ):
        out = []
        n = len(poly)
        for i in range(n):
            a, b = poly[i - 1], poly[i]
            if dedans(b):
                if not dedans(a):
                    out.append(inter(a, b))
                out.append(b)
            elif dedans(a):
                out.append(inter(a, b))
        poly = out
        if not poly:
            return []
    return nettoyer(poly)


def _recaler_emprise(poly):
    """Emprise du gabarit recalée comme bati.py et toiture.py (scripts/recaler_releve.py, calibration.json)."""
    cal = json.load(open(os.path.join(RACINE, "travail", "releve-2026-11-19", "calibration.json")))["reperes_communs"]
    out = []
    for x, y in poly:
        p = []
        for v, ax in ((x, "x"), (y, "y")):
            a = [r["ancien"] for r in cal[ax]]
            n = [r["nouveau"] for r in cal[ax]]
            p.append(round(float(np.interp(v, a, n) + min(v - a[0], 0) + max(v - a[-1], 0)), 4))
        out.append(tuple(p))
    return out


def sans_rects(r, exclus):
    """Rectangle r privé des rectangles exclus (découpage en bandes)."""
    morceaux = [tuple(r)]
    for e in exclus:
        ex0, ey0, ex1, ey1 = e
        suite = []
        for x0, y0, x1, y1 in morceaux:
            if ex1 <= x0 or ex0 >= x1 or ey1 <= y0 or ey0 >= y1:
                suite.append((x0, y0, x1, y1))
                continue
            if ey0 > y0:
                suite.append((x0, y0, x1, ey0))
            if ey1 < y1:
                suite.append((x0, ey1, x1, y1))
            ya, yb = max(y0, ey0), min(y1, ey1)
            if ex0 > x0:
                suite.append((x0, ya, ex0, yb))
            if ex1 < x1:
                suite.append((ex1, ya, x1, yb))
        morceaux = [m for m in suite if m[2] - m[0] > 0.02 and m[3] - m[1] > 0.02]
    return morceaux


EMPRISE = _recaler_emprise(G["emprise"]["polygone"])
# à l'étage le bow-window sud est un balcon : la façade de l'avant-corps reste au nu droit (y ≈ 6,78)
EMPRISE_ETAGE = [p for p in EMPRISE if p[1] < 7.5 or abs(p[0]) > 2.4]
NU_INT = {"rdc": decaler(EMPRISE, EP_EXT), "etage": decaler(EMPRISE_ETAGE, EP_EXT)}

# ----------------------------------------------------------------------------------------------
# Pièces de la coque (ids du plan P3 entre parenthèses dans "graphe")
# ----------------------------------------------------------------------------------------------
# Numéros des plans d'évacuation entre crochets (identifiants imprimés, pas des surfaces).
# Les rectangles vont d'axe de mur à axe de mur ; côté façade ils dépassent et sont découpés au nu intérieur.
XE = 17.0     # au-delà des façades est/ouest (découpé par NU_INT)
YN, YS = -9.5, 9.5
PIECES = [
    # ---- RDC (R07)
    dict(id="vestibule", graphe="R-vestibule", plan="26", niv="rdc", rects=[(-XC, YN, XC, Y_ECRAN)], hsp=5.0, sol="marbre"),
    dict(id="couloir_ouest", graphe="R-couloir-ouest", plan="40", niv="rdc", rects=[(-XA, YN, -XC, Y_COULOIR)], hsp=4.5, sol="marbre"),
    dict(id="couloir_est", graphe="R-couloir-est", plan="27", niv="rdc", rects=[(XC, YN, XA, Y_COULOIR)], hsp=4.5, sol="marbre"),
    dict(id="passage_ouest", graphe="R-passage-ouest", plan="ouest de la volée", niv="rdc", rects=[(-XC, Y_ECRAN, -X_VC, Y_REPOS)], hsp=None, sol="marbre"),
    dict(id="passage_est", graphe="R-passage-est", plan="est de la volée", niv="rdc", rects=[(X_VC, Y_ECRAN, XC, Y_REPOS)], hsp=None, sol="marbre"),
    dict(id="escalier", graphe="escalier", plan="volée centrale", niv="rdc", rects=[(-X_VC, Y_ECRAN, X_VC, Y_REPOS)], hsp=None, sol="marbre"),
    dict(id="petit_salon", graphe="R-petit-salon", plan="central", niv="rdc", rects=[(-XC, Y_REPOS, XC, Y_SALON)], hsp=None, sol="marbre"),
    dict(id="salon", graphe="R-salon", plan="36", niv="rdc", rects=[(-XC, Y_SALON, XC, YS)], hsp=5.0, sol="parquet"),
    dict(id="billard", graphe="R-billard", plan="35", niv="rdc", rects=[(XC, Y_COULOIR, XA, YS)], hsp=5.0, sol="parquet"),
    dict(id="salon_ouest", graphe="R-salon-ouest", plan="37", niv="rdc", rects=[(-XA, Y_COULOIR, -XC, YS)], hsp=5.0, sol="parquet"),
    dict(id="piece_no", graphe="R-piece-no", plan="39", niv="rdc", rects=[(-XE, YN, -XA, -2.10)], hsp=4.5, sol="parquet"),
    dict(id="pavillon_so", graphe="R-pavillon-so", plan="38", niv="rdc", rects=[(-XE, -2.10, -XA, YS)], hsp=5.0, sol="neutre"),
    dict(id="pavillon_ne", graphe="R-pavillon-ne", plan="28/29/30", niv="rdc",
         rects=[(XA, YN, XE, -2.72), (XA, -2.72, 11.60, -0.93)], hsp=4.5, sol="neutre"),
    dict(id="bloc_est", graphe="R-bloc-est", plan="31/32", niv="rdc", rects=[(11.60, -2.72, XE, -0.93)], hsp=4.5, sol="neutre"),
    dict(id="degagement_est", graphe="R-degagement-est", plan="33", niv="rdc", rects=[(XA, -0.93, XE, 2.40)], hsp=4.5, sol="marbre"),
    dict(id="salon_vert", graphe="R-salon-vert", plan="34", niv="rdc", rects=[(XA, 2.40, XE, YS)], hsp=5.0, sol="parquet"),
    # ---- étage (R03)
    dict(id="bibliotheque", graphe="E-bibliotheque", plan="41", niv="etage", rects=[(-XC, YN, XC, Y_BIBLIO)], hsp=4.6, sol="parquet"),
    dict(id="palier", graphe="E-palier", plan="palier", niv="etage", rects=[(X_GAL_O, Y_BIBLIO, X_GAL_E, Y_PALIER_S)],
         hsp=None, sol="marbre"),
    dict(id="vide_cage", graphe="escalier", plan="cage", niv="etage", rects=[(-XC, Y_PALIER_S, XC, Y_TAPISSERIE)], hsp=None, sol=None),
    dict(id="galerie_est", graphe="E-palier", plan="45/50", niv="etage",
         rects=[(XC, Y_GAL_N, 11.50, Y_GAL_S), (XC, Y_PALIER_S, X_GAL_E, Y_GAL_N), (X_GAL_E, Y_TREMIE_CB, XA, Y_GAL_N),
                (XA, Y_GAL_S, 11.50, 2.40)], hsp=4.6, sol="marbre"),
    dict(id="galerie_ouest", graphe="E-palier", plan="55", niv="etage",
         rects=[(-XA, Y_GAL_N, -XC, Y_GAL_S), (X_GAL_O, Y_PALIER_S, -XC, Y_GAL_N)], hsp=4.6, sol="marbre"),
    dict(id="salle_a_manger", graphe="E-salle-a-manger", plan="49", niv="etage", rects=[(XC, Y_GAL_S, XA, YS)], hsp=4.6, sol="parquet"),
    dict(id="chambre_1", graphe="E-chambre-1", plan="48", niv="etage", rects=[(XA, 2.40, XE, YS)], hsp=4.0, sol="parquet"),
    dict(id="chambre_2", graphe="E-chambre-2", plan="51", niv="etage", rects=[(-XC, Y_TAPISSERIE, XC, YS)], hsp=4.0, sol="parquet"),
    dict(id="chambre_3", graphe="E-chambre-3", plan="52", niv="etage", rects=[(-XA, Y_GAL_S, -XC, YS)], hsp=4.0, sol="parquet"),
    dict(id="etage_est", graphe="E-est", plan="43", niv="etage", rects=[(X_GAL_E, YN, XA, Y_TREMIE_CB)], hsp=4.6, sol="neutre"),
    dict(id="etage_ouest", graphe="E-ouest", plan="57", niv="etage", rects=[(-XA, YN, X_GAL_O, Y_GAL_N)], hsp=4.6, sol="neutre"),
    dict(id="etage_nord_ouest", graphe="E-nord-ouest", plan="58", niv="etage", rects=[(X_GAL_O, YN, -XC, Y_BIBLIO)], hsp=4.6, sol="neutre"),
    dict(id="etage_nord_est", graphe="E-nord-est", plan="42", niv="etage", rects=[(XC, YN, X_GAL_E, Y_BIBLIO)], hsp=4.6, sol="neutre"),
    dict(id="etage_pavillon_ne", graphe="E-pavillon-ne", plan="44 (cuisine)", niv="etage",
         rects=[(XA, YN, XE, -2.30), (XA, -2.30, 11.50, Y_GAL_N)], hsp=4.0, sol="neutre"),
    dict(id="etage_bloc_est", graphe="E-bloc-est", plan="46/47", niv="etage", rects=[(11.50, -2.30, XE, Y_GAL_N)], hsp=4.0, sol="neutre"),
    dict(id="etage_escalier_est", graphe="E-escalier-est", plan="escalier latéral est", niv="etage",
         rects=[(11.50, Y_GAL_N, XE, 2.40)], hsp=4.0, sol="neutre"),
    dict(id="etage_pavillon_no", graphe="E-pavillon-no", plan="56", niv="etage", rects=[(-XE, YN, -XA, -1.80)], hsp=4.0, sol="neutre"),
    dict(id="etage_bloc_ouest", graphe="E-bloc-ouest", plan="54", niv="etage", rects=[(-XE, -1.80, -XA, 0.90)], hsp=4.0, sol="neutre"),
    dict(id="etage_pavillon_so", graphe="E-pavillon-so", plan="53", niv="etage", rects=[(-XE, 0.90, -XA, YS)], hsp=4.0, sol="neutre"),
]
PAR_ID = {p["id"]: p for p in PIECES}
P3 = {p["id"]: p for p in plan_p3.PIECES}


def piece_en(niv, x, y):
    for p in PIECES:
        if p["niv"] != niv:
            continue
        for x0, y0, x1, y1 in p["rects"]:
            if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
                return p["id"]
    return "exterieur"


# ----------------------------------------------------------------------------------------------
# Murs intérieurs : (niveau, axe, cote, s0, s1, épaisseur, z0, z1)
# axe "x" : mur parallèle à X (y = cote) ; axe "y" : mur parallèle à Y (x = cote)
# ----------------------------------------------------------------------------------------------
ZR = (Z_RDC, Z_SOUS_DALLE)
ZRC = (Z_RDC, Z_ETAGE)        # sous un mur de cage d'étage : jusqu'au dessus du plancher
ZE = (Z_ETAGE, Z_DESSOUS_COMBLES)
ZEC = (Z_ETAGE, Z_NAISSANCE)  # murs de la cage jusqu'à la naissance de la coupole
Y_NORD, Y_SUD = -6.05, 6.05   # nus extérieurs du corps (calibration.json)
XF = 16.40                    # nu extérieur des façades est et ouest
MURS = []
for s in (-1, 1):
    MURS += [
        # RDC (R07)
        ("rdc", "y", XC * s, Y_NORD, Y_ECRAN, R6, *ZR),
        ("rdc", "y", XC * s, Y_ECRAN, Y_SALON, R6, *ZRC),
        ("rdc", "y", XC * s, Y_SALON, Y_SUD, R6, *ZR),
        ("rdc", "x", Y_COULOIR, *sorted((XC * s, XA * s)), C3, *ZR),
        ("rdc", "y", XA * s, Y_NORD, Y_SUD, R6, *ZR),
        # étage (R03)
        ("etage", "y", XC * s, Y_NORD, Y_BIBLIO, R6, *ZE),
        ("etage", "y", XC * s, Y_PALIER_S, Y_TAPISSERIE, R6, *ZEC),
        ("etage", "y", XC * s, Y_TAPISSERIE, Y_SUD, R6, *ZE),
        ("etage", "x", Y_GAL_S, *sorted((XC * s, XA * s)), C2, *ZE),
    ]
MURS += [
    ("etage", "y", -XA, Y_NORD, Y_SUD, R6, *ZE),             # refend ouest (passage 54/55 en porte)
    ("etage", "y", XA, Y_NORD, Y_GAL_N, R6, *ZE),            # refend est, ouvert sur la circulation 50/45
    ("etage", "y", XA, Y_GAL_S, Y_SUD, R6, *ZE),
]
MURS += [
    ("rdc", "x", Y_ECRAN, -XC, XC, R5, *ZR),                 # écran à colonnes du vestibule
    ("rdc", "x", Y_SALON, -XC, XC, R5, *ZR),                 # petit salon / salon (seuil 36)
    ("rdc", "x", Y_TAPISSERIE, -XC, XC, C3, Z_REPOS - EP_REPOS, Z_ETAGE),  # retombée sous le mur de tapisserie
    ("rdc", "x", Y_TAPISSERIE, -1.25, 1.25, 0.48, Z_RDC, Z_REPOS - EP_REPOS),  # bloc de la fontaine (R07)
    ("rdc", "x", -2.10, -XF, -XA, C2, *ZR),                  # 39 / 38
    ("rdc", "x", -2.72, 11.60, XF, C2, *ZR),                 # 28-30 / 31
    ("rdc", "y", 11.60, -2.72, -0.93, C2, *ZR),              # liaison 28-30 / 31
    ("rdc", "x", -0.93, XA, XF, C2, *ZR),                    # 28-31 / 33
    ("rdc", "x", 2.40, XA, XF, C2, *ZR),                     # 33 et escalier latéral / 34
    ("etage", "x", Y_BIBLIO, X_GAL_O, X_GAL_E, C3, *ZE),     # 41, 58, 42 / palier
    ("etage", "x", Y_TAPISSERIE, -XC, XC, C3, *ZEC),         # mur de la tapisserie
    ("etage", "y", X_GAL_O, Y_NORD, Y_GAL_N, C2, *ZE),       # 58, palier, 55 / 57
    ("etage", "x", Y_GAL_N, -XA, X_GAL_O, C2, *ZE),          # 57 / 55
    ("etage", "y", X_GAL_E, Y_NORD, Y_TREMIE_CB, C2, *ZE),   # 42, palier / 43
    ("etage", "x", Y_TREMIE_CB, X_GAL_E, XA, C2, *ZE),       # 43 / volume de l'escalier des combles
    ("etage", "x", -1.80, -XF, -XA, C2, *ZE),                # 56 / 54
    ("etage", "x", 0.90, -XF, -XA, C2, *ZE),                 # 54 / 53
    ("etage", "x", -2.30, 11.50, XF, C2, *ZE),               # 44 / 46-47
    ("etage", "y", 11.50, -2.30, 2.40, C2, *ZE),             # 44, 50 / 46-47, escalier latéral
    ("etage", "x", Y_GAL_N, XA, XF, C2, *ZE),                # 44, 46-47 / 45, escalier latéral
    ("etage", "x", 2.40, XA, XF, C2, *ZE),                   # 45, escalier latéral / 48
]

# ----------------------------------------------------------------------------------------------
# Ouvertures. vantaux : 0 (baie libre), 1, 2 ; vers : pièce dans laquelle les vantaux s'ouvrent.
# ouvrable False : la porte mène à un volume non vu (fermé, D-019).
# ----------------------------------------------------------------------------------------------
def porte(niv, x, y, larg, haut, a, b, vantaux=2, vers=None, mat="laque", arc=False, garde_corps=False,
          ouvrable=True, preuve="", nom=None):
    return dict(niv=niv, x=x, y=y, largeur=larg, hauteur=haut, a=a, b=b, vantaux=vantaux, vers=vers or b,
                mat=mat, arc=arc, garde_corps=garde_corps, ouvrable=ouvrable, preuve=preuve, nom=nom)


# Positions et largeurs lues sur R07/R03 (plan-mesure.json « ouvertures ») ; largeur mini 0,9 m pour le jeu.
PORTES = [
    # RDC
    porte("rdc", -XC, -4.38, 1.3, 3.3, "vestibule", "couloir_ouest", preuve="P21, P22, P41, R07"),
    porte("rdc", XC, -4.38, 1.3, 3.3, "vestibule", "couloir_est", preuve="P36, P41, W08, R07"),
    porte("rdc", 0, Y_ECRAN, 2 * X_VC, 4.6, "vestibule", "escalier", 0, preuve="P41 (volée entre 2 colonnes)"),
    porte("rdc", -2.0, Y_ECRAN, 1.7, 4.6, "vestibule", "passage_ouest", 0, preuve="P23, P41"),
    porte("rdc", 2.0, Y_ECRAN, 1.7, 4.6, "vestibule", "passage_est", 0, preuve="P41, P42"),
    porte("rdc", -XC, 0.14, 1.3, 3.0, "passage_ouest", "salon_ouest", mat="vert", preuve="P23, P24, R07"),
    porte("rdc", XC, 0.14, 1.3, 3.0, "passage_est", "billard", preuve="P42, P26, R07"),
    porte("rdc", -2.2, Y_SALON, 1.2, 3.0, "petit_salon", "salon", mat="vert", preuve="P25, P27, P30"),
    porte("rdc", 2.2, Y_SALON, 1.0, 2.8, "petit_salon", "salon", 1, preuve="P25, P30, P31"),
    porte("rdc", XC, 4.28, 1.3, 3.2, "salon", "billard", mat="noyer", preuve="P28-P32, R07"),
    porte("rdc", -XC, 4.28, 1.3, 3.0, "salon", "salon_ouest", mat="vert", preuve="P27, P28, R07"),
    porte("rdc", XA, 4.35, 1.3, 3.4, "billard", "salon_vert", mat="noyer", preuve="P31, P33, W07, R07"),
    porte("rdc", XA, 0.14, 1.34, 3.4, "billard", "degagement_est", mat="noyer", preuve="P33, P34, R07"),
    porte("rdc", 6.73, Y_COULOIR, 1.7, 3.4, "billard", "couloir_est", mat="noyer", preuve="P34, P35, R07"),
    porte("rdc", -6.93, Y_COULOIR, 1.6, 3.4, "salon_ouest", "couloir_ouest", mat="vert", preuve="R07"),
    porte("rdc", -XA, -4.35, 1.28, 3.0, "couloir_ouest", "piece_no", preuve="P22, R07"),
    porte("rdc", XA, -4.33, 1.27, 3.2, "couloir_est", "pavillon_ne", preuve="R07"),
    porte("rdc", -13.38, -2.10, 1.45, 3.0, "piece_no", "pavillon_so", preuve="R07"),
    porte("rdc", -XA, 0.11, 1.3, 3.0, "salon_ouest", "pavillon_so", preuve="R07"),
    porte("rdc", -XA, 4.29, 1.3, 3.0, "salon_ouest", "pavillon_so", preuve="R07"),
    porte("rdc", 13.68, -2.72, 0.9, 2.3, "pavillon_ne", "bloc_est", 1, preuve="R07 (0,61 m au plan)"),
    porte("rdc", 11.08, -0.93, 0.95, 2.5, "pavillon_ne", "degagement_est", 1, preuve="R07"),
    # étage
    porte("etage", 0, Y_BIBLIO, 1.3, 3.0, "palier", "bibliotheque", preuve="P03, P04, P17, P18, R03, R21"),
    porte("etage", 4.17, Y_GAL_S, 1.4, 2.8, "galerie_est", "salle_a_manger", preuve="P05, P43, P50, P51, R03"),
    porte("etage", -4.59, Y_GAL_S, 1.4, 2.8, "galerie_ouest", "chambre_3", mat="laque_vert", preuve="P07-P09, P57, R03"),
    porte("etage", XC, 4.83, 0.9, 2.6, "salle_a_manger", "chambre_2", 1, preuve="P50, P52, P53, R03"),
    porte("etage", XA, 4.82, 0.9, 2.9, "salle_a_manger", "chambre_1", 1, preuve="P44, P45, P47, R03"),
    porte("etage", -XC, 4.77, 0.9, 2.4, "chambre_2", "chambre_3", 1, preuve="P52, P54, P55, R03"),
    porte("etage", -XA, 4.19, 1.26, 2.6, "chambre_3", "etage_pavillon_so", preuve="R03"),
    porte("etage", X_GAL_O, -2.30, 1.6, 3.0, "palier", "etage_ouest", 0, arc=True, preuve="P09, P10, R03"),
    porte("etage", X_GAL_E, -2.50, 1.0, 3.0, "palier", "etage_est", 0, arc=True,
          preuve="P05 (niche cintrée), R03 (1,39 m au plan ; resserrée devant le volume de l'escalier des combles)"),
    porte("etage", X_GAL_O, -4.67, 0.9, 2.6, "etage_nord_ouest", "etage_ouest", 1, preuve="R03"),
    porte("etage", X_GAL_E, -4.64, 0.9, 2.6, "etage_nord_est", "etage_est", 1, preuve="R03"),
    porte("etage", -XA, -4.91, 0.9, 2.7, "etage_ouest", "etage_pavillon_no", 1, preuve="P10-P12, R03"),
    porte("etage", -XA, 0.0, 1.09, 2.6, "galerie_ouest", "etage_bloc_ouest", 1, preuve="R03"),
    porte("etage", -11.46, 0.90, 1.2, 2.6, "etage_bloc_ouest", "etage_pavillon_so", 1, preuve="R03"),
    porte("etage", XA, -4.74, 1.0, 2.8, "etage_est", "etage_pavillon_ne", 1, preuve="R03"),
    porte("etage", 11.50, -1.44, 0.9, 2.4, "etage_pavillon_ne", "etage_bloc_est", 1, preuve="R03"),
    porte("etage", 15.35, -2.30, 0.9, 2.4, "etage_pavillon_ne", "etage_bloc_est", 1, preuve="R03"),
    porte("etage", 11.50, 0.0, 0.9, 2.6, "galerie_est", "etage_escalier_est", 1, preuve="R03"),
    porte("etage", 14.92, 2.40, 1.6, 2.6, "chambre_1", "etage_escalier_est", preuve="R03"),
]
# arcades de la cage au-dessus des volées de retour (P15, P16 ; R03 : une baie par côté)
for s, cote in ((1, "est"), (-1, "ouest")):
    PORTES.append(porte("etage", XC * s, -0.05, 1.35, 3.5, "vide_cage", "galerie_" + cote, 0, arc=True, garde_corps=True,
                        preuve="P15, P16, R03 (arcade à balustrade au-dessus de la volée)"))


def mur_de(o):
    """Mur qui porte l'ouverture o."""
    for i, m in enumerate(MURS):
        niv, axe, c, s0, s1 = m[:5]
        if niv != o["niv"]:
            continue
        if axe == "x" and abs(o["y"] - c) < 1e-6 and s0 < o["x"] < s1:
            return i
        if axe == "y" and abs(o["x"] - c) < 1e-6 and s0 < o["y"] < s1:
            return i
    raise ValueError("pas de mur pour %r" % o)


for o in PORTES:
    o["mur"] = mur_de(o)
    o["axe"] = MURS[o["mur"]][1]
    o["ep"] = MURS[o["mur"]][5]
    o["s"] = o["x"] if o["axe"] == "x" else o["y"]

# ----------------------------------------------------------------------------------------------
# Contours intérieurs des pièces
# ----------------------------------------------------------------------------------------------
def demi_ep(niv, axe, c, s0, s1):
    e = 0.0
    for m in MURS:
        if m[0] == niv and m[1] == axe and abs(m[2] - c) < 1e-6 and min(s1, m[4]) - max(s0, m[3]) > 0.05:
            e = max(e, m[5] / 2)
    return e


def contour_struct(p, r):
    return decouper(NU_INT[p["niv"]], r)


def contour_int(p, r):
    x0, y0, x1, y1 = r
    n = p["niv"]
    rr = (x0 + demi_ep(n, "y", x0, y0, y1), y0 + demi_ep(n, "x", y0, x0, x1),
          x1 - demi_ep(n, "y", x1, y0, y1), y1 - demi_ep(n, "x", y1, x0, x1))
    return decouper(NU_INT[n], rr)


for p in PIECES:
    p["struct"] = [contour_struct(p, r) for r in p["rects"]]
    p["int"] = contour_int(p, p["rects"][0])
# contours particuliers
PAR_ID["vide_cage"]["int"] = [(-X_CAGE_INT, Y_PALIER_S), (X_CAGE_INT, Y_PALIER_S), (X_CAGE_INT, Y_CAGE_S),
                              (-X_CAGE_INT, Y_CAGE_S)]
PAR_ID["escalier"]["int"] = [(-X_VC, Y_DEPART), (X_VC, Y_DEPART), (X_VC, Y_REPOS), (-X_VC, Y_REPOS)]

# ----------------------------------------------------------------------------------------------
# Scène, textures, matériaux
# ----------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
COL = bpy.data.collections.new(ID)
SC.collection.children.link(COL)
CTX = bpy.data.collections.new("contexte_rendu")
SC.collection.children.link(CTX)


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


def textures():
    tex = {}
    ph = os.path.join(ASSETS, "polyhaven")
    # enduit blanc cassé (murs) et plafond
    wp = os.path.join(ph, "polyhaven-white_plaster_rough_01")
    d = charger_px(os.path.join(wp, "white_plaster_rough_01_diff_1k.jpg"))
    L = lum(d)
    r = (L / L.mean())[:, :, None]
    tex["enduit"] = (sauver_px("enduit_col", np.array([0.80, 0.78, 0.73])[None, None, :] * (1 + (r - 1) * 0.5)),
                     os.path.join(wp, "white_plaster_rough_01_nor_gl_1k.jpg"), None)
    tex["plafond"] = (sauver_px("plafond_col", np.array([0.86, 0.85, 0.82])[None, None, :] * (1 + (r - 1) * 0.3)),
                      os.path.join(wp, "white_plaster_rough_01_nor_gl_1k.jpg"), None)
    # parquet chêne
    ow = os.path.join(ph, "polyhaven-oak_wood_planks")
    tex["parquet"] = (os.path.join(ow, "oak_wood_planks_diff_1k.jpg"), os.path.join(ow, "oak_wood_planks_nor_gl_1k.jpg"),
                      os.path.join(ow, "oak_wood_planks_rough_1k.jpg"))
    # dallage de marbre blanc posé en diagonale, cabochons rouges (P20, P24, P41) : 1,414 m par tuile UV
    bw = os.path.join(ph, "polyhaven-beige_wall_001")
    bd = charger_px(os.path.join(bw, "beige_wall_001_diff_2k.jpg"))[::2, ::2]
    n = bd.shape[0]
    Lb = lum(bd)
    Ln = (Lb - Lb.mean()) / (Lb.std() + 1e-6)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n * 1.4142
    u = (xx + yy) / math.sqrt(2)
    v = (xx - yy) / math.sqrt(2)
    s = 0.5
    du = np.abs(((u + s / 2) % s) - s / 2)
    dv = np.abs(((v + s / 2) % s) - s / 2)
    joint = np.clip(1 - (np.minimum(du, dv) - 0.0015) / 0.0015, 0, 1)
    cab = (np.hypot(du, dv) < 0.03).astype(np.float32)
    marbre = np.array([0.86, 0.86, 0.84])[None, None, :] * (1 + 0.05 * Ln[:, :, None])
    veine = np.clip(np.abs(np.sin((xx * 3 + yy * 7 + Ln * 0.6) * 3.0)) ** 30, 0, 1)
    marbre = marbre * (1 - 0.18 * veine[:, :, None])
    col = marbre * (1 - 0.25 * joint[:, :, None])
    col = col * (1 - cab[:, :, None]) + np.array([0.45, 0.05, 0.04])[None, None, :] * cab[:, :, None]
    tex["marbre"] = (sauver_px("marbre_dallage_col", col), None,
                     sauver_px("marbre_dallage_rgh", np.clip(0.18 + 0.4 * joint + 0.03 * Ln, 0, 1)))
    tex["marbre_blanc"] = (sauver_px("marbre_blanc_col", marbre[::2, ::2]), None, None)
    return tex


log("textures…")
TEX = textures()
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
        c, nrm, rg = tex
        ti = nt.nodes.new("ShaderNodeTexImage")
        ti.image = bpy.data.images.load(c, check_existing=True)
        nt.links.new(ti.outputs["Color"], p.inputs["Base Color"])
        if nrm:
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = bpy.data.images.load(nrm, check_existing=True)
            tn.image.colorspace_settings.name = "Non-Color"
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.inputs["Strength"].default_value = 0.6
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


M_ENDUIT = materiau("enduit", tex=TEX["enduit"], uv=1.5, rugosite=0.85)
M_PLAFOND = materiau("plafond", tex=TEX["plafond"], uv=1.5, rugosite=0.9)
M_PARQUET = materiau("parquet", tex=TEX["parquet"], uv=2.0, rugosite=0.5)
M_MARBRE = materiau("marbre_dallage", tex=TEX["marbre"], uv=1.4142, rugosite=0.2)
M_MARCHE = materiau("marbre_marche", tex=TEX["marbre_blanc"], uv=1.0, rugosite=0.25)
M_NEUTRE = materiau("sol_neutre", (0.42, 0.40, 0.37), 0.8)
M_TAPIS = materiau("tapis_rouge", (0.42, 0.03, 0.03), 0.95)
M_FER = materiau("fer_forge", (0.02, 0.02, 0.02), 0.45, 0.6)
M_LAITON = materiau("laiton", (0.78, 0.58, 0.25), 0.3, 1.0)
M_LAQUE = materiau("porte_laque", (0.85, 0.85, 0.82), 0.35)
M_VERT = materiau("porte_vert_eau", (0.66, 0.74, 0.68), 0.4)
M_NOYER = materiau("porte_noyer", (0.28, 0.15, 0.08), 0.45)
M_VERRE = materiau("verre_puits", (0.75, 0.82, 0.88), 0.05, emission=((0.85, 0.9, 1.0), 1.5), alpha=0.6,
                   deux_faces=True)
MAT_SOL = {"marbre": M_MARBRE, "parquet": M_PARQUET, "neutre": M_NEUTRE}
M_MOULURE = materiau("porte_moulure_gris_vert", (0.50, 0.57, 0.53), 0.4)   # filets et chambranles (photo du 19/11)
MAT_PORTE = {"laque": M_LAQUE, "vert": M_VERT, "noyer": M_NOYER, "laque_vert": M_LAQUE}


# ----------------------------------------------------------------------------------------------
# Constructeur de maillages (repris de terrasse.py, réduit)
# ----------------------------------------------------------------------------------------------
class Bld:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def v(self, co):
        return self.bm.verts.new(co)

    def face(self, vs, m):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.mi(m)
        return f

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

    def boite(self, x0, y0, z0, x1, y1, z1, m):
        self.solide([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, m)

    def prisme(self, profil, axe, a0, a1, m):
        """Profil [(s, z)] dans le plan vertical d'axe "x" (s = x, épaisseur en y de a0 à a1) ou "y"."""
        profil = ccw(profil)
        if axe == "x":
            f = lambda s, z, a: (s, a, z)
        else:
            f = lambda s, z, a: (a, s, z)
        b = [self.v(f(s, z, a0)) for s, z in profil]
        h = [self.v(f(s, z, a1)) for s, z in profil]
        n = len(b)
        for i in range(n):
            j = (i + 1) % n
            self.face([b[i], b[j], h[j], h[i]], m)
        self.face(list(reversed(b)), m)
        self.face(h, m)

    def poutre(self, p0, p1, larg, haut, m):
        """Barre de section rectangulaire de p0 à p1 (axe quelconque, section verticale)."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        hz = Vector((-d.y, d.x, 0))
        hz = hz.normalized() * larg / 2 if hz.length > 1e-9 else Vector((larg / 2, 0, 0))
        up = d.cross(hz).normalized() * haut / 2 if d.length > 1e-9 else Vector((0, 0, haut / 2))
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

    def objet(self, nom, col=COL, loc=(0, 0, 0)):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            s = UVS.get(self.mats[f.material_index].name, 1.0) if self.mats else 1.0
            for lp in f.loops:
                co = lp.vert.co + Vector(loc)
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
        col.objects.link(ob)
        return ob


NIV_OBJ = {}        # nom d'objet → "rdc" | "etage" | "cage" (pour les rendus éclatés)
ROLE = {}           # nom → "sol" | "plafond" | "mur" | "escalier" | "garde_corps" | "porte" | "voute"


def enreg(ob, niv, role):
    NIV_OBJ[ob.name] = niv
    ROLE[ob.name] = role
    return ob


# ----------------------------------------------------------------------------------------------
# Planchers et plafonds
# ----------------------------------------------------------------------------------------------
log("planchers, plafonds…")
OBJ_PIECE = {p["id"]: [] for p in PIECES}
for p in PIECES:
    if p["sol"] is None:
        continue
    b = Bld()
    if p["niv"] == "rdc":
        z0, z1 = Z_DALLE_RDC, Z_RDC
    else:
        z0, z1 = Z_SOUS_DALLE, Z_ETAGE
    for poly in p["struct"]:
        if len(poly) >= 3:
            b.solide(poly, z0, z1, M_PLAFOND if p["niv"] == "etage" else M_NEUTRE, mhaut=MAT_SOL[p["sol"]])
    ob = enreg(b.objet("sol_" + p["id"]), p["niv"], "sol")
    OBJ_PIECE[p["id"]].append(ob.name)
    # plafond : de la hauteur sous plafond au-dessous du plancher supérieur, sur tous les rectangles de la
    # pièce, sans couvrir les volumes de l'escalier des combles
    if p["hsp"]:
        if p["niv"] == "rdc":
            zb, zh = Z_RDC + p["hsp"], Z_SOUS_DALLE
        else:
            zb, zh = Z_ETAGE + p["hsp"], Z_DESSOUS_COMBLES
        zh = max(zh, zb + 0.05)
        b = Bld()
        for r in p["rects"]:
            morceaux = [r] if p["niv"] == "rdc" else sans_rects(r, EXCL_ETAGE)
            for m in morceaux:
                poly = contour_int(p, m)
                if len(poly) >= 3 and abs(aire(poly)) > 0.01:
                    b.solide(poly, zb, zh, M_PLAFOND)
        ob = enreg(b.objet("plafond_" + p["id"]), p["niv"], "plafond")
        OBJ_PIECE[p["id"]].append(ob.name)

# plafonds plats de la cage sous la dalle des combles : palier nord et bande sud du repos (la voûte occupe
# le noyau central de R18) ; sous-face du petit salon au-delà du repos
b = Bld()
b.solide([(X_GAL_O + C2 / 2, Y_BIBLIO + C3 / 2), (X_GAL_E - C2 / 2, Y_BIBLIO + C3 / 2),
          (X_GAL_E - C2 / 2, Y_PALIER_S), (X_GAL_O + C2 / 2, Y_PALIER_S)], Z_NAISSANCE, Z_DESSOUS_COMBLES, M_PLAFOND)
b.solide([(-X_CAGE_INT, Y_NOYAU_S), (X_CAGE_INT, Y_NOYAU_S), (X_CAGE_INT, Y_CAGE_S), (-X_CAGE_INT, Y_CAGE_S)],
         Z_NAISSANCE, Z_DESSOUS_COMBLES, M_PLAFOND)
ob = enreg(b.objet("plafond_palier"), "etage", "plafond")
OBJ_PIECE["palier"].append(ob.name)
b = Bld()
b.solide([(-X_CAGE_INT, Y_CAGE_S), (X_CAGE_INT, Y_CAGE_S), (X_CAGE_INT, Y_SALON - R5 / 2),
          (-X_CAGE_INT, Y_SALON - R5 / 2)], Z_REPOS - EP_REPOS, Z_REPOS, M_PLAFOND)
ob = enreg(b.objet("plafond_petit_salon"), "rdc", "plafond")
OBJ_PIECE["petit_salon"].append(ob.name)

# ----------------------------------------------------------------------------------------------
# Murs : découpés par couple de pièces, percés des ouvertures
# ----------------------------------------------------------------------------------------------
log("murs…")


def profil_ouverture(s0, s1, zb, h, arc):
    """Contour (s, z) de la baie ; plein cintre si arc."""
    if not arc:
        return [(s0, zb), (s1, zb), (s1, zb + h), (s0, zb + h)]
    r = (s1 - s0) / 2
    c = (s0 + s1) / 2
    zn = zb + h - r
    pts = [(s0, zb), (s1, zb)]
    for k in range(13):
        a = math.pi * k / 12
        pts.append((c + r * math.cos(a), zn + r * math.sin(a)))
    pts.append((s0, zb))
    return nettoyer(pts)


def construire_mur(b, axe, c, s0, s1, ep, z0, z1, ouvs):
    """Panneaux pleins entre ouvertures, trumeaux et linteaux (cintrés si arcade)."""
    a0, a1 = c - ep / 2, c + ep / 2
    ouvs = sorted(ouvs, key=lambda o: o["s"])
    cur = s0
    for o in ouvs:
        os0, os1 = o["s"] - o["largeur"] / 2, o["s"] + o["largeur"] / 2
        if os0 - cur > 1e-4:
            b.prisme([(cur, z0), (os0, z0), (os0, z1), (cur, z1)], axe, a0, a1, M_ENDUIT)
        zt = z0 + o["hauteur"]
        if o["arc"]:
            r = o["largeur"] / 2
            zn = zt - r
            # deux pieds-droits fins ne sont pas nécessaires : l'intrados va de la naissance au haut du mur
            pts = [(os1, zn)]
            for k in range(13):
                a = math.pi * k / 12
                pts.append((o["s"] + r * math.cos(a), zn + r * math.sin(a)))
            pts = pts[1:] + [(os0, z1), (os1, z1)]
            b.prisme(nettoyer(pts), axe, a0, a1, M_ENDUIT)
        elif z1 - zt > 1e-4:
            b.prisme([(os0, zt), (os1, zt), (os1, z1), (os0, z1)], axe, a0, a1, M_ENDUIT)
        cur = os1
    if s1 - cur > 1e-4:
        b.prisme([(cur, z0), (s1, z0), (s1, z1), (cur, z1)], axe, a0, a1, M_ENDUIT)


MURS_PIECE = {p["id"]: {} for p in PIECES}
for im, (niv, axe, c, s0, s1, ep, z0, z1) in enumerate(MURS):
    # découpe en tronçons séparant le même couple de pièces
    pas = 0.05
    def couple(s):
        if axe == "x":
            return piece_en(niv, s, c - ep / 2 - 0.02), piece_en(niv, s, c + ep / 2 + 0.02)
        return piece_en(niv, c - ep / 2 - 0.02, s), piece_en(niv, c + ep / 2 + 0.02, s)
    bornes = [s0]
    k = s0 + pas / 2
    prec = couple(k)
    while k < s1:
        cc = couple(k)
        if cc != prec:
            bornes.append(round(k - pas / 2, 4))
            prec = cc
        k += pas
    bornes.append(s1)
    for t0, t1 in zip(bornes[:-1], bornes[1:]):
        a, bb = couple((t0 + t1) / 2)
        ouvs = [o for o in PORTES if o["mur"] == im and t0 <= o["s"] < t1]
        b = Bld()
        construire_mur(b, axe, c, t0, t1, ep, z0, z1, ouvs)
        noms = [x for x in (a, bb) if x not in ("exterieur",)]
        nom = "mur_" + "_".join(noms) if noms else "mur_%s_%d" % (niv, im)
        if len(noms) == 1:
            nom = "mur_%s_%s" % (noms[0], {"x": ("sud" if a != "exterieur" else "nord"),
                                            "y": ("est" if a != "exterieur" else "ouest")}[axe])
        if bpy.data.objects.get(nom):
            nom += "_%d" % im
        ob = enreg(b.objet(nom), "cage" if z1 > Z_ATTIQUE else niv, "mur")
        for pid, cote in ((a, "sud" if axe == "x" else "est"), (bb, "nord" if axe == "x" else "ouest")):
            if pid in MURS_PIECE:
                MURS_PIECE[pid].setdefault(cote, []).append(ob.name)
                OBJ_PIECE[pid].append(ob.name)

# appuis des arcades ouvertes sur le vide (le plancher de galerie s'arrête à l'axe du mur)
for o in PORTES:
    if o["garde_corps"]:
        b = Bld()
        s0, s1 = o["s"] - o["largeur"] / 2, o["s"] + o["largeur"] / 2
        c = MURS[o["mur"]][2]
        x0, x1 = sorted((c - math.copysign(o["ep"] / 2, c), c))
        b.boite(x0, s0, Z_SOUS_DALLE, x1, s1, Z_ETAGE, M_MARBRE)
        enreg(b.objet("appui_arcade_%s_%d" % (o["b"], int(round(o["s"] * 100)))), "etage", "sol")

# ----------------------------------------------------------------------------------------------
# Escalier impérial
# ----------------------------------------------------------------------------------------------
log("escalier…")
MARCHES = []   # (nom, x0, x1, y0, y1, z) pour le JSON


def volee_centrale():
    b = Bld()
    prof = [(Y_DEPART, 0.0)]
    for k in range(1, N_C):
        y0 = Y_DEPART + (k - 1) * G_C
        prof += [(y0, k * H_C), (y0 + G_C, k * H_C)]
        MARCHES.append(("centrale", -X_VC, X_VC, y0, y0 + G_C, k * H_C))
    # paillasse : sous-face rampante parallèle à la volée, le dessous de l'escalier reste vide (demande du 19/11)
    prof += [(Y_REPOS, Z_REPOS - EP_REPOS - 0.08), (Y_DEPART + 0.21, 0.0)]   # 15 cm sous les angles des marches
    # profil dans le plan (y, z) extrudé en x : prisme d'axe "y" avec s = y
    b.prisme(nettoyer(prof), "y", -X_VC, X_VC, M_MARCHE)
    # tapis rouge (largeur 1,5 m) posé sur les marches
    for k in range(1, N_C):
        y0 = Y_DEPART + (k - 1) * G_C
        b.boite(-0.75, y0 - 0.005, k * H_C, 0.75, y0 + G_C, k * H_C + 0.012, M_TAPIS)
        b.boite(-0.75, y0 - 0.017, (k - 1) * H_C, 0.75, y0 - 0.005, k * H_C + 0.012, M_TAPIS)
    b.boite(-0.75, Y_REPOS - 0.017, (N_C - 1) * H_C, 0.75, Y_REPOS - 0.005, Z_REPOS + 0.012, M_TAPIS)
    return enreg(b.objet("escalier_volee_centrale"), "rdc", "escalier")


def volee_retour(s):
    b = Bld()
    prof = [(Y_REPOS, Z_REPOS - EP_REPOS)]
    for k in range(1, N_R):
        y0 = Y_REPOS - (k - 1) * G_R
        prof += [(y0, Z_REPOS + k * H_R), (y0 - G_R, Z_REPOS + k * H_R)]
        xa, xb = sorted((s * X_VR0, s * X_VR1))
        MARCHES.append(("retour_" + ("est" if s > 0 else "ouest"), xa, xb, y0 - G_R, y0, Z_REPOS + k * H_R))
    prof += [(Y_ARRIVEE, Z_SOUS_DALLE)]
    xa, xb = sorted((s * X_VR0, s * X_VR1))
    b.prisme(nettoyer(prof), "y", xa, xb, M_MARCHE)
    xm = s * (X_VR0 + X_VR1) / 2
    for k in range(1, N_R):
        y0 = Y_REPOS - (k - 1) * G_R
        z = Z_REPOS + k * H_R
        b.boite(xm - 0.55, y0 - G_R, z, xm + 0.55, y0 + 0.005, z + 0.012, M_TAPIS)
        b.boite(xm - 0.55, y0 + 0.005, z - H_R, xm + 0.55, y0 + 0.017, z + 0.012, M_TAPIS)
    b.boite(xm - 0.55, Y_ARRIVEE + 0.005, Z_ETAGE - H_R, xm + 0.55, Y_ARRIVEE + 0.017, Z_ETAGE + 0.012, M_TAPIS)
    return enreg(b.objet("escalier_volee_retour_" + ("est" if s > 0 else "ouest")), "cage", "escalier")


def repos():
    b = Bld()
    b.solide([(-X_CAGE_INT, Y_REPOS), (X_CAGE_INT, Y_REPOS), (X_CAGE_INT, Y_CAGE_S), (-X_CAGE_INT, Y_CAGE_S)],
             Z_REPOS - EP_REPOS, Z_REPOS, M_PLAFOND, mhaut=M_MARBRE)
    return enreg(b.objet("escalier_repos"), "cage", "escalier")


OBJ_PIECE["escalier"] += [volee_centrale().name, repos().name, volee_retour(1).name, volee_retour(-1).name]
OBJ_PIECE["petit_salon"].append("escalier_repos")

# écran du vestibule : la baie centrale reçoit les deux premières marches ; piliers carrés à la place des
# colonnes corinthiennes (décor : P4.vestibule)

# ----------------------------------------------------------------------------------------------
# Garde-corps : barreaux fer, main courante laiton (rampes à volutes : P4.palier)
# ----------------------------------------------------------------------------------------------
log("garde-corps…")
H_GC = 0.95


def garde_corps(b, pts, pas=0.12):
    """pts : polyligne [(x, y, z_sol)] ; main courante à z_sol + H_GC, lisse basse, barreaux."""
    for (p, q) in zip(pts[:-1], pts[1:]):
        p, q = Vector(p), Vector(q)
        b.poutre(p + Vector((0, 0, H_GC)), q + Vector((0, 0, H_GC)), 0.07, 0.05, M_LAITON)
        b.poutre(p + Vector((0, 0, 0.08)), q + Vector((0, 0, 0.08)), 0.03, 0.03, M_FER)
        L = (q - p).xy.length
        n = max(1, int(L / pas))
        for i in range(n + 1):
            t = i / n
            c = p.lerp(q, t)
            b.boite(c.x - 0.009, c.y - 0.009, c.z + 0.08, c.x + 0.009, c.y + 0.009, c.z + H_GC - 0.025, M_FER)
    for p in (pts[0], pts[-1]):
        b.boite(p[0] - 0.035, p[1] - 0.035, p[2], p[0] + 0.035, p[1] + 0.035, p[2] + H_GC + 0.03, M_FER)


def nez_c(y):
    return max(0.0, min(Z_REPOS, (y - Y_DEPART) / G_C * H_C + H_C))


def nez_r(y):
    return Z_REPOS + (Y_REPOS - y) / G_R * H_R + H_R


for s, cote in ((1, "est"), (-1, "ouest")):
    b = Bld()
    xc = s * (X_VC - 0.06)
    # volée centrale : de la première marche au repos, puis bord du repos jusqu'à la volée de retour
    garde_corps(b, [(xc, Y_DEPART + 0.15, H_C), (xc, Y_REPOS - 0.1, Z_REPOS), (xc, Y_REPOS + 0.06, Z_REPOS),
                    (s * (X_VR0 - 0.06), Y_REPOS + 0.06, Z_REPOS)])
    # limon intérieur de la volée de retour, bord du palier d'arrivée
    xr = s * (X_VR0 + 0.06)
    garde_corps(b, [(xr, Y_REPOS - 0.1, nez_r(Y_REPOS - 0.1) - H_R), (xr, Y_ARRIVEE + 0.05, Z_ETAGE),
                    (xr, Y_PALIER_S - 0.06, Z_ETAGE)])
    # bord de la trémie entre les deux arrivées
    garde_corps(b, [(s * (X_VR0 - 0.06), Y_PALIER_S - 0.06, Z_ETAGE), (0.0, Y_PALIER_S - 0.06, Z_ETAGE)])
    # arcade ouverte sur la volée
    for o in PORTES:
        if o["garde_corps"] and o["b"] == "galerie_" + cote:
            garde_corps(b, [(o["x"], o["s"] - o["largeur"] / 2 + 0.05, Z_ETAGE),
                            (o["x"], o["s"] + o["largeur"] / 2 - 0.05, Z_ETAGE)])
    ob = enreg(b.objet("garde_corps_escalier_" + cote), "cage", "garde_corps")
    OBJ_PIECE["escalier"].append(ob.name)
    OBJ_PIECE["palier"].append(ob.name)

# limons apparents (bandeaux rampants sous les rampes)
b = Bld()
for s in (1, -1):
    xa, xb = sorted((s * X_VR0, s * (X_VR0 + 0.12)))
    # bandeau sur le limon intérieur de la volée de retour (côté passage)
    b.prisme([(Y_REPOS, Z_REPOS - EP_REPOS - 0.05), (Y_REPOS, Z_REPOS + 0.05),
              (Y_ARRIVEE, Z_ETAGE + 0.05), (Y_ARRIVEE, Z_SOUS_DALLE - 0.05)], "y", xa, xb, M_ENDUIT)
enreg(b.objet("escalier_limons"), "cage", "escalier")
OBJ_PIECE["escalier"].append("escalier_limons")

# ----------------------------------------------------------------------------------------------
# Coupole en arc de cloître, puits de lumière (oculi et caissons : P4.palier)
# ----------------------------------------------------------------------------------------------
log("coupole…")
CX, CY = 0.0, (Y_NOYAU_N + Y_NOYAU_S) / 2
AX, AY = X_CAGE_INT, (Y_NOYAU_S - Y_NOYAU_N) / 2
T_PUITS = 0.3
NV = 20


def z_voute(t):
    """Arc de cloître : profil elliptique de la naissance (t = 1) au bord du puits (t = T_PUITS)."""
    if t <= T_PUITS:
        return Z_CLE
    return Z_NAISSANCE + (Z_CLE - Z_NAISSANCE) * math.sqrt(max(0.0, 1 - ((t - T_PUITS) / (1 - T_PUITS)) ** 2))


b = Bld()
grille = {}
for i in range(NV + 1):
    for j in range(NV + 1):
        u, v = -1 + 2 * i / NV, -1 + 2 * j / NV
        t = max(abs(u), abs(v))
        grille[i, j] = b.v((CX + u * AX, CY + v * AY, z_voute(t)))
for i in range(NV):
    for j in range(NV):
        uc, vc = -1 + 2 * (i + 0.5) / NV, -1 + 2 * (j + 0.5) / NV
        if max(abs(uc), abs(vc)) < T_PUITS:
            continue
        b.face([grille[i, j], grille[i + 1, j], grille[i + 1, j + 1], grille[i, j + 1]], M_PLAFOND)
ob = b.objet("coupole_cage")
# normales vers le bas (intrados)
me = ob.data
bm = bmesh.new()
bm.from_mesh(me)
for f in bm.faces:
    if f.normal.z > 0:
        f.normal_flip()
bm.to_mesh(me)
bm.free()
enreg(ob, "voute", "voute")
b = Bld()
a, bb = T_PUITS * AX, T_PUITS * AY
b.solide([(CX - a, CY - bb), (CX + a, CY - bb), (CX + a, CY + bb), (CX - a, CY + bb)], Z_CLE, Z_CLE + 0.02, M_VERRE)
enreg(b.objet("coupole_puits_vitre"), "voute", "voute")
OBJ_PIECE["palier"] += ["coupole_cage", "coupole_puits_vitre"]

# ----------------------------------------------------------------------------------------------
# Vantaux de portes : un objet par vantail, origine sur l'axe du gond (rotation autour de Z)
# ----------------------------------------------------------------------------------------------
log("vantaux…")
EP_VANTAIL = 0.05
JEU = 0.004


def cote_de(o, pid):
    """+1 si la pièce pid est du côté des coordonnées croissantes (normale du mur), -1 sinon."""
    c = MURS[o["mur"]][2]
    if o["axe"] == "x":
        return 1 if piece_en(o["niv"], o["x"], c + o["ep"] / 2 + 0.05) == pid else -1
    return 1 if piece_en(o["niv"], c + o["ep"] / 2 + 0.05, o["y"]) == pid else -1


def vantail_moulure(b, axe, sens, lv, h, m):
    """Vantail peint d'après la photo du 19/11 : trois panneaux par face (haut, petit panneau à plaque de
    laiton, bas), filets gris-vert en saillie, poignée à béquille. Repère local : s le long du mur (0 au gond),
    t dans l'épaisseur (centrée), z au-dessus du sol."""
    def P(si, t, z):
        return (sens * si, t, z) if axe == "x" else (t, sens * si, z)

    def pave(s0, s1, t0, t1, z0, z1, mat):
        p0, p1 = P(s0, t0, z0), P(s1, t1, z1)
        b.boite(p0[0], p0[1], p0[2], p1[0], p1[1], p1[2], mat)

    e = EP_VANTAIL / 2
    pave(0, lv, -e, e, 0.01, h, m)
    mont, filet, saillie = min(0.11, lv * 0.17), 0.028, 0.009
    z_bas0, z_bas1 = 0.20, 0.20 + (h - 0.20) * 0.36
    z_mil0, z_mil1 = z_bas1 + 0.09, z_bas1 + 0.09 + max(0.12, h * 0.045)
    z_hau0, z_hau1 = z_mil1 + 0.09, h - 0.13
    for face in (-1, 1):
        t0, t1 = sorted((face * e, face * (e + saillie)))
        for z0, z1 in ((z_bas0, z_bas1), (z_mil0, z_mil1), (z_hau0, z_hau1)):
            s0, s1 = mont, lv - mont
            pave(s0, s1, t0, t1, z0, z0 + filet, M_MOULURE)
            pave(s0, s1, t0, t1, z1 - filet, z1, M_MOULURE)
            pave(s0, s0 + filet, t0, t1, z0, z1, M_MOULURE)
            pave(s1 - filet, s1, t0, t1, z0, z1, M_MOULURE)
            # second filet, plus fin, en retrait de 4 cm (double cadre de la photo)
            r, f2 = 0.04, 0.010
            if z1 - z0 > 0.3:
                pave(s0 + r, s1 - r, t0, t1, z0 + r, z0 + r + f2, M_MOULURE)
                pave(s0 + r, s1 - r, t0, t1, z1 - r - f2, z1 - r, M_MOULURE)
                pave(s0 + r, s0 + r + f2, t0, t1, z0 + r, z1 - r, M_MOULURE)
                pave(s1 - r - f2, s1 - r, t0, t1, z0 + r, z1 - r, M_MOULURE)
        # plaque de laiton au milieu du petit panneau
        zc = (z_mil0 + z_mil1) / 2
        tl0, tl1 = sorted((face * e, face * (e + 0.004)))
        pave(lv * 0.5 - 0.08, lv * 0.5 + 0.08, tl0, tl1, zc - 0.014, zc + 0.014, M_LAITON)
        # béquille côté battant : rosace et poignée horizontale vers le gond
        tr0, tr1 = sorted((face * e, face * (e + 0.012)))
        pave(lv - 0.085, lv - 0.055, tr0, tr1, 1.02, 1.14, M_LAITON)
        tb0, tb1 = sorted((face * (e + 0.03), face * (e + 0.05)))
        pave(lv - 0.20, lv - 0.06, tb0, tb1, 1.07, 1.09, M_LAITON)
        pave(lv - 0.08, lv - 0.06, tr0, tb1, 1.07, 1.09, M_LAITON)


def chambranle(o, b):
    """Chambranle gris-vert sur les deux faces d'une baie à vantaux : deux montants et un linteau à crossettes."""
    c, ep = MURS[o["mur"]][2], o["ep"]
    zb = Z_RDC if o["niv"] == "rdc" else Z_ETAGE
    l, sa = 0.13, 0.03
    s0, s1 = o["s"] - o["largeur"] / 2, o["s"] + o["largeur"] / 2
    zh = zb + o["hauteur"]
    for face in (-1, 1):
        n0, n1 = sorted((c + face * ep / 2, c + face * (ep / 2 + sa)))
        n2, n3 = sorted((c + face * ep / 2, c + face * (ep / 2 + sa + 0.012)))
        morceaux = [(s0 - l, s0, n0, n1, zb, zh), (s1, s1 + l, n0, n1, zb, zh),
                    (s0 - l - 0.03, s1 + l + 0.03, n0, n1, zh, zh + l),
                    (s0 - l - 0.04, s1 + l + 0.04, n2, n3, zh + l, zh + l + 0.035),   # corniche du linteau
                    (s0 - 0.025, s0, n2, n3, zb, zh), (s1, s1 + 0.025, n2, n3, zb, zh)]   # baguette intérieure
        for a0, a1, t0, t1, z0, z1 in morceaux:
            if o["axe"] == "x":
                b.boite(a0, t0, z0, a1, t1, z1, M_MOULURE)
            else:
                b.boite(t0, a0, z0, t1, a1, z1, M_MOULURE)


VANTAUX = {}
for o in PORTES:
    if not o["vantaux"]:
        continue
    zb = Z_RDC if o["niv"] == "rdc" else Z_ETAGE
    c = MURS[o["mur"]][2]
    sv = cote_de(o, o["vers"])            # côté où les vantaux s'ouvrent
    plan = c + sv * (o["ep"] / 2 - 0.06 - EP_VANTAIL / 2)   # plan des vantaux, en feuillure côté ouverture
    s0, s1 = o["s"] - o["largeur"] / 2, o["s"] + o["largeur"] / 2
    lv = o["largeur"] / o["vantaux"] - 2 * JEU
    h = o["hauteur"] - 0.01
    base = "porte_%s_%s" % (o["a"], o["b"])
    if bpy.data.objects.get(base) or bpy.data.objects.get(base + "_g"):
        base += "_%d" % int(round(abs(o["s"]) * 10))
    o["nom"] = base
    o["vantaux_objets"] = []
    gonds = [(s0 + JEU, 1)] if o["vantaux"] == 1 else [(s0 + JEU, 1), (s1 - JEU, -1)]
    for k, (sg, sens) in enumerate(gonds):
        b = Bld()
        # vantail en local : de 0 à sens·lv le long du mur, épaisseur centrée (modèle de la photo du 19/11)
        vantail_moulure(b, o["axe"], sens, lv, h, M_LAQUE if o["mat"] in ("laque", "laque_vert", "vert") else MAT_PORTE[o["mat"]])
        loc = (sg, plan, zb) if o["axe"] == "x" else (plan, sg, zb)
        nom = base if o["vantaux"] == 1 else base + ("_g" if k == 0 else "_d")
        ob = enreg(b.objet(nom, loc=loc), o["niv"], "porte")
        # angle d'ouverture (rotation Z Blender, degrés) qui amène le vantail du côté "vers"
        # vantail le long de +s (sens=1) : rotation +90° le pousse vers +normale si axe "x" ...
        if o["axe"] == "x":
            ang = 90 * sens * sv
        else:
            ang = -90 * sens * sv
        o["vantaux_objets"].append(dict(objet=nom, pivot=[round(v, 3) for v in loc], largeur=round(lv, 3),
                                        hauteur=round(h, 3), angle_ouverture_z_deg=ang))
        for pid in (o["a"], o["b"]):
            OBJ_PIECE[pid].append(nom)

for niv in ("rdc", "etage"):
    bc = Bld()
    for o in PORTES:
        if o["vantaux"] and o["niv"] == niv and not o["arc"]:
            chambranle(o, bc)
    enreg(bc.objet("chambranles_portes_" + niv), niv, "porte")

# ----------------------------------------------------------------------------------------------
# JSON pour les agents des pièces et le jeu
# ----------------------------------------------------------------------------------------------
log("coque.json…")


def r3(poly):
    return [[round(x, 3), round(y, 3)] for x, y in poly]


HSP_TXT = {
    "passage_ouest": dict(min=round(Z_REPOS - EP_REPOS, 2), max=Z_SOUS_DALLE,
                          note="sous-face rampante de la volée de retour (basse au sud), vide de cage côté volée centrale"),
    "passage_est": dict(min=round(Z_REPOS - EP_REPOS, 2), max=Z_SOUS_DALLE,
                        note="sous-face rampante de la volée de retour (basse au sud), vide de cage côté volée centrale"),
    "petit_salon": dict(min=round(Z_REPOS - EP_REPOS, 2), max=round(Z_REPOS - EP_REPOS, 2),
                        note="sous-face du repos de l'escalier"),
    "escalier": dict(min=None, max=Z_CLE, note="cage ouverte jusqu'à la coupole (naissance %.2f, clé %.2f)" % (Z_NAISSANCE, Z_CLE)),
    "palier": dict(min=round(Z_NAISSANCE - Z_ETAGE, 2), max=round(Z_CLE - Z_ETAGE, 2),
                   note="galerie nord et paliers d'arrivée sous la coupole de la cage"),
    "vide_cage": dict(min=None, max=round(Z_CLE - Z_ETAGE, 2), note="trémie de la cage"),
}
pieces_json = []
for p in PIECES:
    p3 = P3.get(p["graphe"], {})
    zsol = Z_RDC if p["niv"] == "rdc" else Z_ETAGE
    portes = []
    for o in PORTES:
        if p["id"] not in (o["a"], o["b"]):
            continue
        zb = Z_RDC if o["niv"] == "rdc" else Z_ETAGE
        portes.append(dict(
            nom=o.get("nom") or "baie_%s_%s_%d" % (o["a"], o["b"], int(round(abs(o["s"]) * 100))),
            type=("arcade" if o["arc"] else "baie") if not o["vantaux"] else ("porte double" if o["vantaux"] == 2 else "porte"),
            centre=[o["x"], o["y"], zb], mur="parallèle à X (y = %.2f)" % MURS[o["mur"]][2] if o["axe"] == "x"
            else "parallèle à Y (x = %.2f)" % MURS[o["mur"]][2],
            epaisseur_mur=o["ep"], largeur=o["largeur"], hauteur=o["hauteur"], cintree=o["arc"],
            relie=[o["a"], o["b"]], vers=o["vers"] if o["vantaux"] else None,
            ouvrable=o["ouvrable"] if o["vantaux"] else None, garde_corps=o["garde_corps"],
            vantaux=o.get("vantaux_objets", []), preuve=o["preuve"]))
    pieces_json.append(dict(
        id=p["id"], graphe=p["graphe"], numero_plan=p.get("plan"), nom=p3.get("nom", p["id"]), niveau=p["niv"], z_sol=zsol,
        certitude=p3.get("certitude", ""), photos=p3.get("photos", []),
        ferme=p3.get("certitude") == "non-vu",
        polygone_interieur=r3(p["int"]),
        surface_m2=round(sum(abs(aire(contour_int(p, r))) for r in p["rects"]), 2),
        rect_plan=[list(r) for r in p["rects"]],
        hauteur_sous_plafond=p["hsp"] if p["hsp"] else HSP_TXT.get(p["id"]),
        sol=p["sol"], fenetres_facade=p3.get("fenetres", []),
        murs=MURS_PIECE[p["id"]], objets=sorted(set(OBJ_PIECE[p["id"]])),
        portes=portes))

coque_json = dict(
    version=1, repere="D-003 : m, +X est, +Y sud, Z haut (Blender) ; glTF : Y haut, -Z sud",
    source="scripts/composants/coque.py (relevé du 19/11 : plan-mesure.json, plans R07/R03/R18 ; graphe D-019)",
    niveaux=dict(rdc=Z_RDC, sous_dalle_etage=Z_SOUS_DALLE, etage=Z_ETAGE, attique=Z_ATTIQUE,
                 naissance_coupole=Z_NAISSANCE, cle_coupole=Z_CLE),
    murs_exterieurs="bati.py ; nu intérieur = nu du gabarit − %.2f m (non modélisés ici)" % EP_EXT,
    escalier=dict(
        type="impérial (D-013, D-014)",
        volee_centrale=dict(contremarches=N_C, hauteur=round(H_C, 4), giron=G_C, x=[-X_VC, X_VC],
                            y_depart=Y_DEPART, y_arrivee=round(Y_REPOS, 3)),
        repos=dict(z=Z_REPOS, y=[round(Y_REPOS, 3), Y_CAGE_S], x=[-X_CAGE_INT, X_CAGE_INT], epaisseur=EP_REPOS),
        volees_retour=dict(contremarches=N_R, hauteur=round(H_R, 4), giron=round(G_R, 4), x=[X_VR0, X_VR1],
                           y_depart=round(Y_REPOS, 3), y_arrivee=round(Y_ARRIVEE, 3)),
        garde_corps_hauteur=H_GC,
        marches=[dict(volee=v, x=[round(a, 3), round(b_, 3)], y=[round(c, 3), round(d, 3)], z=round(z, 3))
                 for v, a, b_, c, d, z in MARCHES]),
    vantaux_convention="objet porte_<a>_<b>[_g|_d], origine sur l'axe du gond, vantail fermé ; "
                       "angle_ouverture_z_deg : rotation autour de Z Blender pour l'ouvrir vers 'vers' "
                       "(dans Unity après import glTF : rotation autour de Y, signe à inverser)",
    pieces=pieces_json)
CHEMIN_JSON = (os.path.join(EXPORT, "coque.json") if os.environ.get("COQUE_SORTIE")
               else os.path.join(RACINE, "travail", "coque.json"))
json.dump(coque_json, open(CHEMIN_JSON, "w"), ensure_ascii=False, indent=1)

# ----------------------------------------------------------------------------------------------
# Contrôles : hauteurs de marche, largeur des portes, ouvertures dans un seul mur
# ----------------------------------------------------------------------------------------------
assert 0.16 <= H_C <= 0.18 and 0.16 <= H_R <= 0.18, (H_C, H_R)
for o in PORTES:
    assert o["largeur"] >= 0.9, o
log("marches : centrale %.3f m × %d, retour %.3f m × %d ; repos %.2f ; y repos %.2f, arrivée %.2f"
    % (H_C, N_C, H_R, N_R, Z_REPOS, Y_REPOS, Y_ARRIVEE))

# ----------------------------------------------------------------------------------------------
# Rendus de contrôle
# ----------------------------------------------------------------------------------------------
M_CTX = bpy.data.materials.new("ctx_mur_ext")
M_CTX.diffuse_color = (0.6, 0.58, 0.55, 1)
M_CTX.use_nodes = True
next(n for n in M_CTX.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.55, 0.53, 0.5, 1)


def contexte_murs_ext():
    """Murs extérieurs sommaires (rendus seulement) : anneau emprise − nu intérieur, sans baies."""
    obs = []
    for niv, z0, z1 in (("rdc", Z_DALLE_RDC, Z_ETAGE), ("etage", Z_ETAGE, Z_ATTIQUE)):
        ext = ccw(EMPRISE if niv == "rdc" else EMPRISE_ETAGE)
        inn = ccw(NU_INT[niv])
        bm = bmesh.new()
        n1, n2 = len(ext), len(inn)
        # paroi par segment : prisme quadrilatère entre arête extérieure et arête intérieure correspondante
        if n1 == n2:
            for i in range(n1):
                j = (i + 1) % n1
                q = [ext[i], ext[j], inn[j], inn[i]]
                vs0 = [bm.verts.new((x, y, z0)) for x, y in q]
                vs1 = [bm.verts.new((x, y, z1)) for x, y in q]
                for k in range(4):
                    kk = (k + 1) % 4
                    bm.faces.new([vs0[k], vs0[kk], vs1[kk], vs1[k]])
                bm.faces.new(list(reversed(vs0)))
                bm.faces.new(vs1)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new("ctx_ext_" + niv)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(M_CTX)
        ob = bpy.data.objects.new("ctx_ext_" + niv, me)
        CTX.objects.link(ob)
        obs.append(ob)
    return obs


CTX_EXT = contexte_murs_ext()


def regler_rendu():
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            SC.render.engine = eng
            break
        except TypeError:
            continue
    log("moteur :", SC.render.engine)
    try:
        SC.eevee.taa_render_samples = 32
        SC.eevee.use_shadows = True
    except Exception:
        pass
    try:
        SC.eevee.use_raytracing = True
    except Exception:
        pass
    SC.render.resolution_x = 1600
    SC.render.resolution_y = 900
    w = bpy.data.worlds.new("ciel")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.6
    SC.world = w
    try:
        SC.view_settings.view_transform = "AgX"
        SC.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass


regler_rendu()
SOLEIL = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", "SUN"))
SOLEIL.data.energy = 3.5
SOLEIL.data.angle = math.radians(2)
SOLEIL.rotation_euler = (math.radians(38), math.radians(10), math.radians(205))
CTX.objects.link(SOLEIL)

# éclairage intérieur : une lumière de surface par pièce, sous le plafond
LUMIERES = []
for p in PIECES:
    xs = [q[0] for q in p["int"]]
    ys = [q[1] for q in p["int"]]
    zs = Z_RDC if p["niv"] == "rdc" else Z_ETAGE
    h = p["hsp"] or (3.0 if p["id"] in ("petit_salon", "passage_ouest", "passage_est") else 6.0)
    if p["id"] == "escalier":
        h = 4.6
    li = bpy.data.lights.new("lum_" + p["id"], "AREA")
    li.shape = "RECTANGLE"
    li.size, li.size_y = max(0.5, max(xs) - min(xs) - 0.4), max(0.5, max(ys) - min(ys) - 0.4)
    li.energy = 28 * li.size * li.size_y
    li.color = (1.0, 0.93, 0.82)
    li.use_shadow = p["id"] in ("escalier", "vide_cage", "palier", "vestibule", "petit_salon")
    lo = bpy.data.objects.new("lum_" + p["id"], li)
    lo.location = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, zs + h - 0.1)
    CTX.objects.link(lo)
    LUMIERES.append((lo, p["niv"]))
lp = bpy.data.lights.new("lum_puits", "AREA")
lp.size, lp.size_y, lp.energy = 2.2, 2.6, 900
lpo = bpy.data.objects.new("lum_puits", lp)
lpo.location = (CX, CY, Z_CLE - 0.1)
CTX.objects.link(lpo)


def camera(nom, pos, cible, focale=None, ortho=None, clip=0.05):
    cam = bpy.data.cameras.new(nom)
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    else:
        cam.lens = focale
    cam.clip_start = clip
    cam.clip_end = 500
    co = bpy.data.objects.new(nom, cam)
    co.location = pos
    d = Vector(cible) - Vector(pos)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    CTX.objects.link(co)
    return co


def visibles(filtre):
    for ob in COL.objects:
        cache = not filtre(ob.name)
        ob.hide_render = cache
    for ob in CTX_EXT:
        ob.hide_render = not filtre(ob.name)


def rendre(cam, fichier, filtre=lambda n: True, lum_niv=None):
    visibles(filtre)
    for lo, niv in LUMIERES:
        lo.hide_render = lum_niv is not None and niv not in lum_niv
    SC.camera = cam
    SC.render.filepath = os.path.join(RENDUS, fichier)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log("rendu", fichier, "%.1fs" % (time.time() - t))


def f_rdc(n):
    if n.startswith("ctx_ext_"):
        return n == "ctx_ext_rdc"
    return NIV_OBJ.get(n) == "rdc" and ROLE.get(n) != "plafond" or (n.startswith("escalier") and NIV_OBJ.get(n) != "voute")


def f_etage(n):
    if n.startswith("ctx_ext_"):
        return True
    return ROLE.get(n) not in ("plafond", "voute") and not (NIV_OBJ.get(n) == "rdc" and ROLE.get(n) == "plafond")


def f_tout(n):
    return True


def centre(n):
    ob = bpy.data.objects[n]
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return sum(cs, Vector()) / 8


bpy.context.view_layer.update()
CENTRES = {ob.name: centre(ob.name) for ob in COL.objects}


def f_coupe_ns(n):
    """Moitié est du château (coupe dans l'axe nord-sud, vue depuis l'ouest)."""
    if n.startswith("ctx_"):
        return False
    return CENTRES[n].x > -0.6


def f_cage(n):
    """Cage d'escalier ouverte : murs nord et ouest de la cage, plafonds et coupole retirés."""
    if n.startswith("ctx_"):
        return False
    c = CENTRES[n]
    if ROLE.get(n) in ("plafond", "voute"):
        return False
    if not (-5.0 < c.x < 5.0 and -9.0 < c.y < 3.3):
        return False
    if NIV_OBJ.get(n) in ("etage", "cage") and c.y < -3.0:
        return False
    if ROLE.get(n) == "mur" and (c.x < -3.1 or c.y < -3.2):
        return False
    if ROLE.get(n) == "porte" and c.x < -3.1:
        return False
    return True


def f_cage_so(n):
    if n.startswith("ctx_"):
        return False
    c = CENTRES[n]
    if ROLE.get(n) in ("plafond", "voute") or not (-5.0 < c.x < 5.0 and -9.0 < c.y < 3.3):
        return False
    return not (ROLE.get(n) in ("mur", "porte") and (c.x < -3.1 or c.y > 2.7))


def f_plan(niv):
    def f(n):
        if n.startswith("ctx_ext_"):
            return n == "ctx_ext_" + niv
        if ROLE.get(n) in ("plafond", "voute"):
            return False
        if niv == "rdc":
            return NIV_OBJ.get(n) == "rdc" or n.startswith("escalier_volee_centrale")
        return NIV_OBJ.get(n) in ("etage", "cage") or n.startswith("escalier")
    return f


SEULE = os.environ.get("COQUE_VUES")
VUES = [
    # vue éclatée du RDC (depuis le sud-est) : étage et plafonds retirés
    ("coque_rdc.png", camera("cam_rdc", (16, 30, 34), (0, 0.5, 0), 30), f_rdc, ("rdc",)),
    # étage : plafonds et coupole retirés
    ("coque_etage.png", camera("cam_etage", (16, 30, 42), (0, 0.5, 5.35), 30), f_etage, ("etage",)),
    # plans vus de dessus (sud en haut, est à droite : le repère D-003 est direct avec +Y au sud)
    ("coque_rdc_plan.png", camera("cam_rdc_plan", (0, 0.0, 40), (0, 0.0, 0), ortho=36), f_plan("rdc"), ("rdc",)),
    ("coque_etage_plan.png", camera("cam_etage_plan", (0, 0.0, 45), (0, 0.0, 5), ortho=36), f_plan("etage"), ("etage",)),
    # coupe nord-sud dans l'axe : moitié est, vue depuis l'ouest (nord à droite)
    ("coque_coupe_ns.png", camera("cam_coupe_ns", (-40, -1.0, 6.2), (0, -1.0, 6.2), ortho=22), f_coupe_ns, None),
    # cage ouverte depuis le sud-ouest (murs sud et ouest retirés)
    ("coque_cage_so.png", camera("cam_cage_so", (-8.0, 9.0, 16.0), (0.3, -0.5, 2.6), 26), f_cage_so, None),
    # cage ouverte depuis le nord-ouest (bibliothèque et murs nord/ouest retirés)
    ("coque_cage.png", camera("cam_cage", (-4.0, -9.5, 22.0), (0.2, 0.0, 2.6), 24), f_cage, None),
    # cage d'escalier depuis la porte d'entrée (P41)
    ("coque_escalier.png", camera("cam_escalier", (0.0, -7.8, 1.6), (0.0, 0.5, 3.0), 15), f_tout, None),
    # depuis le repos vers le nord (P17, P18)
    ("coque_escalier_repos.png", camera("cam_repos", (0.6, 2.2, Z_REPOS + 1.6), (0.0, -5.0, 5.2), 14), f_tout, None),
    # palier de l'étage depuis la porte de la bibliothèque (P04)
    ("coque_palier.png", camera("cam_palier", (0.0, -2.8, Z_ETAGE + 1.6), (0.0, 3.0, 6.6), 14), f_tout, None),
    # passage ouest sous la volée de retour, vers le petit salon (P24)
    ("coque_passage.png", camera("cam_passage", (-2.0, -5.0, 1.6), (-2.0, 3.0, 2.0), 15), f_tout, None),
]
for f, cam, filtre, ln in VUES:
    if SEULE and f not in SEULE.split(","):
        continue
    rendre(cam, f, filtre, ln)

# ----------------------------------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------------------------------
for ob in COL.objects:
    ob.hide_render = False
for ob in list(CTX.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
bpy.data.collections.remove(CTX)
bpy.data.materials.remove(M_CTX)
lc = bpy.context.view_layer.layer_collection.children[ID]
bpy.context.view_layer.active_layer_collection = lc
glb = os.path.join(EXPORT, ID + ".glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_active_collection=True,
                          export_apply=True, export_yup=True, export_image_format="JPEG", export_jpeg_quality=88)
log("glb :", glb, "%.1f Mo" % (os.path.getsize(glb) / 1e6))
try:
    bpy.ops.file.pack_all()
except RuntimeError as ex:
    log("pack_all :", ex)
blend = os.path.join(EXPORT, ID + ".blend")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
log("objets :", len(COL.objects), "pièces :", len(PIECES), "ouvertures :", len(PORTES))
log("fin")

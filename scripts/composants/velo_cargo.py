# Vélo cargo longtail électrique (type Decathlon R500E) pour le parc : cadre aluminium bleu ciel, roue avant
# 26 pouces, roue arrière 20 pouces à moteur-moyeu, batterie dans le tube diagonal, porte-bagage long avec
# marchepieds en bois, siège enfant bleu marine et coussin passager, panier avant fixé au cadre.
# Longueur ≈ 2,05 m, selle à 0,95 m, empattement 1,32 m.
# Géométrie écrite dans un repère de travail (x vers l'avant, y à gauche, z haut, roues posées sur z = 0),
# puis convertie dans le repère des pièces : avant du vélo vers -Y, axe des roues selon X, origine du vélo au
# sol à mi-distance des points de contact des roues.
# Pièces (pour un vélo pilotable) : cadre (fixe), direction (fourche, cintre, panier, garde-boue avant ;
# origine sur l'axe de direction), roue avant (enfant de la direction), roue arrière.
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from voiture_c5 import Acc, revolution

R_AV, R_AR = 0.333, 0.258               # rayons des roues (26 x 2,0 et 20 x 2,15)
X_AV, X_AR = 0.70, -0.62                 # essieux (empattement 1,32 m)
X_MI = (X_AV + X_AR) / 2                 # origine du vélo : milieu des contacts au sol
F = Vector((X_AV, 0, R_AV))
R = Vector((X_AR, 0, R_AR))
BB = Vector((-0.03, 0, 0.27))            # boîtier de pédalier
H0 = Vector((0.555, 0, 0.74))            # bas de la douille de direction
U_DIR = (F - H0).normalized()            # axe de direction (vers le bas), passe par le moyeu avant
H1 = H0 - U_DIR * 0.16                   # haut de la douille
ST = Vector((-0.165, 0, 0.78))           # haut du tube de selle
D_SELLE = (ST - BB).normalized()
SELLE = ST + D_SELLE * 0.15 + Vector((0, 0, 0.035))   # centre de la selle (dessus ≈ 0,95 m)
CINTRE = Vector((0.455, 0, 1.04))
Z_PB = 0.60                              # plateau du porte-bagage
X_PB0, X_PB1 = -0.13, -1.00

CLES = ("cadre", "noir", "plastique", "pneu", "reflet", "jante", "bois", "siege", "selle", "ecran", "feu", "metal")
MATIERES = {
    "cadre": dict(couleur=(0.34, 0.48, 0.58), rugosite=0.35, metal=0.3),
    "noir": dict(couleur=(0.015, 0.015, 0.017), rugosite=0.45, metal=0.2),
    "plastique": dict(couleur=(0.025, 0.025, 0.027), rugosite=0.7),
    "pneu": dict(couleur=(0.022, 0.022, 0.022), rugosite=0.9),
    "reflet": dict(couleur=(0.55, 0.55, 0.55), rugosite=0.35, metal=0.3),
    "jante": dict(couleur=(0.05, 0.05, 0.055), rugosite=0.3, metal=0.8),
    "bois": dict(couleur=(0.62, 0.45, 0.26), rugosite=0.6),
    "siege": dict(couleur=(0.02, 0.035, 0.10), rugosite=0.45),
    "selle": dict(couleur=(0.02, 0.02, 0.02), rugosite=0.6),
    "ecran": dict(couleur=(0.02, 0.03, 0.04), rugosite=0.1, emission=(0.05, 0.12, 0.15)),
    "feu": dict(couleur=(0.5, 0.01, 0.01), rugosite=0.2, emission=(0.35, 0.0, 0.0)),
    "metal": dict(couleur=(0.7, 0.7, 0.72), rugosite=0.25, metal=1.0),
}


def V(x, y, z):
    return Vector((x, y, z))


# ---------------------------------------------------------------------------
# Primitives (repère de travail)
# ---------------------------------------------------------------------------

def tube(acc, pts, r, mat, n=10, bouts=True):
    """Tube le long d'une polyligne ; r : rayon constant ou liste par point (repères transportés)."""
    pts = [Vector(p) for p in pts]
    rs = r if isinstance(r, (list, tuple)) else [r] * len(pts)
    ts = []
    for i in range(len(pts)):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        ts.append((b - a).normalized())
    ref = Vector((0, 0, 1)) if abs(ts[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = ts[0].cross(ref).normalized()
    anneaux = []
    for i, p in enumerate(pts):
        t = ts[i]
        nrm = (nrm - t * nrm.dot(t)).normalized()
        bi = t.cross(nrm)
        anneaux.append([acc.sv(p + (nrm * math.cos(2 * math.pi * k / n) + bi * math.sin(2 * math.pi * k / n)) * rs[i])
                        for k in range(n)])
    for i in range(len(pts) - 1):
        mil = (pts[i] + pts[i + 1]) / 2
        for k in range(n):
            k2 = (k + 1) % n
            q = (anneaux[i][k], anneaux[i][k2], anneaux[i + 1][k2], anneaux[i + 1][k])
            m = sum((Vector(acc.v[x]) for x in q), Vector()) / 4
            acc.face(q, mat, hint=m - mil)
    if bouts:
        acc.face(anneaux[0], mat, hint=-ts[0])
        acc.face(anneaux[-1], mat, hint=ts[-1])


def courbe(points, pas=8):
    """Lissage Catmull-Rom d'une polyligne 3D (extrémités conservées)."""
    p = [Vector(q) for q in points]
    p = [p[0] * 2 - p[1]] + p + [p[-1] * 2 - p[-2]]
    out = []
    for i in range(1, len(p) - 2):
        for k in range(pas):
            t = k / pas
            a, b, c, d = p[i - 1], p[i], p[i + 1], p[i + 2]
            out.append(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                              + (-a + 3 * b - 3 * c + d) * t ** 3))
    out.append(p[-2])
    return out


def _sp(v, e):
    return math.copysign(abs(v) ** e, v)


def bloc(acc, c, demi, mat, rot=None, e=(0.35, 0.35), n=(16, 8), forme=None):
    """Superellipsoïde (pavé arrondi) ; rot : Matrix 3x3 ; forme(p) -> p déforme le point local."""
    c = Vector(c)
    rot = rot or Matrix.Identity(3)
    a, b, h = demi
    lignes = []
    for i in range(n[1] + 1):
        u = -math.pi / 2 + math.pi * i / n[1]
        ligne = []
        for j in range(n[0]):
            v = 2 * math.pi * j / n[0]
            cu = _sp(math.cos(u), e[0])
            p = Vector((a * cu * _sp(math.cos(v), e[1]), b * cu * _sp(math.sin(v), e[1]), h * _sp(math.sin(u), e[0])))
            if forme:
                p = forme(p)
            ligne.append(acc.sv(c + rot @ p))
        lignes.append(ligne)
    for i in range(n[1]):
        for j in range(n[0]):
            k = (j + 1) % n[0]
            q = (lignes[i][j], lignes[i][k], lignes[i + 1][k], lignes[i + 1][j])
            m = sum((Vector(acc.v[x]) for x in q), Vector()) / 4
            acc.face(q, mat, hint=m - c)


def arc(acc, centre, profil, ph0, ph1, nseg, mat):
    """Coque en arc autour de l'axe y (garde-boue) ; profil fermé (r, s)."""
    cx, cy, cz = centre
    rc = sum(p[0] for p in profil) / len(profil)
    grille = []
    for k in range(nseg + 1):
        ph = ph0 + (ph1 - ph0) * k / nseg
        grille.append([acc.sv((cx + r * math.cos(ph), cy + s, cz + r * math.sin(ph))) for r, s in profil])
    n = len(profil)
    for k in range(nseg):
        ph = ph0 + (ph1 - ph0) * (k + 0.5) / nseg
        rad = Vector((math.cos(ph), 0, math.sin(ph)))
        for j in range(n):
            j2 = (j + 1) % n
            r = (profil[j][0] + profil[j2][0]) / 2
            s = (profil[j][1] + profil[j2][1]) / 2
            acc.face((grille[k][j], grille[k + 1][j], grille[k + 1][j2], grille[k][j2]), mat,
                     hint=rad * (r - rc) + Vector((0, s, 0)))
    for k, sgn in ((0, -1), (nseg, 1)):
        ph = ph0 + (ph1 - ph0) * k / nseg
        acc.face(grille[k], mat, hint=Vector((-math.sin(ph), 0, math.cos(ph))) * sgn * math.copysign(1, ph1 - ph0))


# ---------------------------------------------------------------------------
# Roues : pneu (tore, flancs réfléchissants), jante creuse, rayons, moyeu
# ---------------------------------------------------------------------------

def roue(acc, c, r_ext, rho, r_moyeu, l_moyeu, nray):
    rc = r_ext - rho
    prof = []
    for k in range(17):
        t = math.radians(-125 + 250 * k / 16)
        prof.append((rc + rho * math.cos(t), rho * math.sin(t)))

    def mat_pneu(j):
        t = -125 + 250 * (j + 0.5) / 16
        return "reflet" if 62 < abs(t) < 95 else "pneu"
    revolution(acc, c, prof, 48, mat_pneu, lambda rad, r, s: rad * (r - rc) + Vector((0, s, 0)))
    r_j = rc - rho * 0.6
    jante = [(r_j, -0.013), (r_j + 0.004, 0.0), (r_j, 0.013), (r_j - 0.026, 0.009), (r_j - 0.03, 0.0),
             (r_j - 0.026, -0.009)]
    rcj = sum(p[0] for p in jante) / len(jante)
    revolution(acc, c, jante + [jante[0]], 40, "jante", lambda rad, r, s: rad * (r - rcj) + Vector((0, s, 0)))
    # moyeu
    prof_m = [(0.008, -l_moyeu - 0.012), (0.012, -l_moyeu - 0.012), (0.014, -l_moyeu), (r_moyeu * 0.8, -l_moyeu),
              (r_moyeu, -l_moyeu * 0.7), (r_moyeu, l_moyeu * 0.7), (r_moyeu * 0.8, l_moyeu), (0.014, l_moyeu),
              (0.012, l_moyeu + 0.012), (0.008, l_moyeu + 0.012)]
    revolution(acc, c, prof_m, 20, "noir", lambda rad, r, s: rad * r + Vector((0, s * 0.3, 0)))
    # rayons croisés, alternés sur les deux flasques
    c = Vector(c)
    for k in range(nray):
        cote = 1 if k % 2 else -1
        ph = 2 * math.pi * k / nray
        ph_h = ph + (0.32 if (k // 2) % 2 else -0.32)
        r_f = r_moyeu * 0.85
        a = c + Vector((r_f * math.cos(ph_h), cote * l_moyeu * 0.75, r_f * math.sin(ph_h)))
        b = c + Vector(((r_j - 0.028) * math.cos(ph), 0, (r_j - 0.028) * math.sin(ph)))
        tube(acc, [a, b], 0.0022, "metal", n=3, bouts=False)


# ---------------------------------------------------------------------------
# Cadre, porte-bagage, sièges, transmission (fixe)
# ---------------------------------------------------------------------------

def cadre(acc):
    # tube diagonal ovale avec batterie noire dessous
    d = (H0 + U_DIR * -0.03) - BB
    dn = d.normalized()
    perp = dn.cross(Vector((0, 1, 0))).normalized()          # vers le bas du tube
    if perp.z > 0:
        perp = -perp
    rot = Matrix((dn, Vector((0, 1, 0)), -perp)).transposed()
    bloc(acc, BB + d * 0.5, (d.length / 2 + 0.02, 0.034, 0.042), "cadre", rot=rot, e=(0.5, 0.6), n=(16, 10))
    bloc(acc, BB + d * 0.52 + perp * 0.04, (d.length * 0.36, 0.031, 0.03), "noir", rot=rot, e=(0.35, 0.55),
         n=(16, 8))
    tube(acc, [H0 + U_DIR * 0.015, H1 - U_DIR * 0.012], 0.029, "cadre", n=14)          # douille
    tube(acc, [BB - D_SELLE * 0.02, ST], 0.025, "cadre", n=12)                          # tube de selle
    tube(acc, [BB + (ST - BB) * 0.78, H1 + U_DIR * 0.04], 0.022, "cadre", n=12)         # tube horizontal
    tube(acc, [BB + V(0, -0.045, 0), BB + V(0, 0.045, 0)], 0.032, "cadre", n=14)       # boîtier
    for s in (-1, 1):
        dr = R + V(0, s * 0.072, 0)
        tube(acc, [BB + V(0.0, s * 0.03, 0), BB + V(-0.12, s * 0.06, -0.005), dr], 0.015, "cadre", n=8)
        tube(acc, [ST + V(0.01, s * 0.02, -0.06), ST + V(-0.12, s * 0.06, -0.14), dr], 0.013, "cadre", n=8)
        # cadre arrière longtail : du moyeu vers les deux bouts du plateau
        tube(acc, [dr, V(-0.98, s * 0.12, Z_PB - 0.02)], 0.014, "cadre", n=8)
        tube(acc, [dr, V(-0.40, s * 0.12, Z_PB - 0.02)], 0.014, "cadre", n=8)
        tube(acc, [ST + V(-0.02, s * 0.02, -0.17), V(X_PB0 - 0.05, s * 0.12, Z_PB - 0.01)], 0.013, "cadre", n=8)
        # patte de cadre
        bloc(acc, dr + V(0, s * 0.004, 0), (0.035, 0.006, 0.03), "cadre", n=(10, 6))
    # porte-bagage tubulaire noir
    for s in (-1, 1):
        tube(acc, [V(X_PB0, s * 0.13, Z_PB), V(X_PB1, s * 0.13, Z_PB)], 0.012, "noir", n=8)
    tube(acc, courbe([V(X_PB1, 0.13, Z_PB), V(X_PB1 - 0.03, 0.08, Z_PB), V(X_PB1 - 0.035, 0, Z_PB),
                      V(X_PB1 - 0.03, -0.08, Z_PB), V(X_PB1, -0.13, Z_PB)], 3), 0.012, "noir", n=8)
    x = X_PB0
    while x > X_PB1 + 0.05:
        tube(acc, [V(x, 0.13, Z_PB - 0.003), V(x, -0.13, Z_PB - 0.003)], 0.008, "noir", n=6)
        x -= 0.11
    tube(acc, [V(X_PB0, 0.13, Z_PB), V(X_PB0 + 0.01, 0, Z_PB + 0.005), V(X_PB0, -0.13, Z_PB)], 0.012, "noir", n=8)
    # garde-pieds, marchepieds en bois et leurs supports
    zm = 0.335
    for s in (-1, 1):
        y0, y1 = s * 0.195, s * 0.325
        boucle = courbe([V(-0.27, s * 0.135, Z_PB), V(-0.30, s * 0.20, Z_PB - 0.02), V(-0.31, s * 0.215, zm + 0.12),
                         V(-0.31, s * 0.22, zm + 0.02)], 4)
        tube(acc, boucle, 0.011, "noir", n=8)
        boucle = courbe([V(-0.97, s * 0.135, Z_PB), V(-0.95, s * 0.20, Z_PB - 0.02), V(-0.94, s * 0.215, zm + 0.12),
                         V(-0.94, s * 0.22, zm + 0.02)], 4)
        tube(acc, boucle, 0.011, "noir", n=8)
        tube(acc, [V(-0.62, s * 0.17, Z_PB - 0.01), V(-0.62, s * 0.215, zm + 0.02)], 0.010, "noir", n=8)
        for yy in (s * 0.215, s * 0.31):
            tube(acc, [V(-0.31, yy, zm - 0.012), V(-0.94, yy, zm - 0.012)], 0.011, "noir", n=8)
        tube(acc, [R + V(0.0, s * 0.075, 0), V(-0.55, s * 0.215, zm - 0.015)], 0.012, "noir", n=8)
        tube(acc, [R + V(-0.02, s * 0.075, 0), V(-0.80, s * 0.215, zm - 0.015)], 0.012, "noir", n=8)
        for xa, xb in ((-0.32, -0.62), (-0.635, -0.93)):
            bloc(acc, V((xa + xb) / 2, (y0 + y1) / 2, zm + 0.008), (abs(xb - xa) / 2, abs(y1 - y0) / 2, 0.011),
                 "bois", e=(0.15, 0.2), n=(12, 4))
    # siège enfant bleu marine : assise, dossier haut, flancs, repose-pieds
    xs = -0.76
    bloc(acc, V(xs, 0, Z_PB + 0.045), (0.19, 0.165, 0.035), "siege", e=(0.3, 0.3))
    inc = Matrix.Rotation(math.radians(-12), 3, "Y")
    bloc(acc, V(xs - 0.19, 0, Z_PB + 0.29), (0.035, 0.165, 0.26), "siege", rot=inc, e=(0.3, 0.35),
         forme=lambda p: Vector((p.x, p.y * (1 - 0.12 * max(0.0, p.z) / 0.26), p.z)))
    for s in (-1, 1):
        # flanc : bord haut descendant vers l'avant, raccordé au dossier
        bloc(acc, V(xs - 0.07, s * 0.15, Z_PB + 0.15), (0.12, 0.018, 0.10), "siege", e=(0.3, 0.3),
             forme=lambda p: Vector((p.x - 0.12 * max(0.0, p.z),
                                     p.y, p.z * (0.45 + 0.55 * (0.12 - p.x) / 0.24 if p.z > 0 else 1.0))))
        tube(acc, [V(xs + 0.17, s * 0.10, Z_PB + 0.03), V(xs + 0.24, s * 0.12, Z_PB - 0.16),
                   V(xs + 0.25, s * 0.12, Z_PB - 0.22)], 0.016, "siege", n=8)
        bloc(acc, V(xs + 0.27, s * 0.12, Z_PB - 0.225), (0.05, 0.035, 0.012), "siege", n=(10, 4))
    bloc(acc, V(xs - 0.01, 0, Z_PB + 0.085), (0.15, 0.13, 0.012), "plastique", e=(0.3, 0.3), n=(12, 4))
    bloc(acc, V(xs - 0.165, 0, Z_PB + 0.29), (0.012, 0.12, 0.2), "plastique", rot=inc, e=(0.3, 0.3), n=(12, 6))
    # coussin passager noir
    bloc(acc, V(-0.37, 0, Z_PB + 0.04), (0.17, 0.125, 0.032), "selle", e=(0.25, 0.3))
    # feu arrière sous le plateau
    bloc(acc, V(X_PB1 - 0.04, 0, Z_PB - 0.03), (0.012, 0.05, 0.018), "feu", n=(10, 4))
    # tige de selle et selle
    tube(acc, [ST - D_SELLE * 0.04, ST + D_SELLE * 0.15], 0.0145, "noir", n=10)
    tube(acc, [ST - D_SELLE * 0.005, ST + D_SELLE * 0.02], 0.03, "noir", n=12)            # collier
    bloc(acc, SELLE + V(0.0, 0, -0.016), (0.035, 0.03, 0.012), "noir", n=(10, 4))

    def nez(p):
        t = (p.x + 0.14) / 0.28                                                        # 0 arrière, 1 nez
        w = 1.0 if t < 0.35 else 1.0 - 0.62 * min(1.0, (t - 0.35) / 0.45)
        return Vector((p.x, p.y * w, p.z + 0.012 * (abs(t - 0.4) * 2) ** 2))
    bloc(acc, SELLE + V(-0.01, 0, 0.0), (0.14, 0.09, 0.026), "selle", e=(0.45, 0.4), n=(20, 8), forme=nez)
    # béquille double centrale (déployée)
    piv = V(-0.40, 0, 0.27)
    tube(acc, [piv + V(0, -0.05, 0), piv + V(0, 0.05, 0)], 0.018, "noir", n=10)
    for s in (-1, 1):
        tube(acc, [piv + V(0, s * 0.04, 0), V(-0.37, s * 0.17, 0.03), V(-0.36, s * 0.19, 0.012)], 0.012, "noir", n=8)
        bloc(acc, V(-0.36, s * 0.195, 0.008), (0.03, 0.02, 0.008), "plastique", n=(10, 4))
    tube(acc, [piv, BB + V(-0.06, 0, 0)], 0.012, "noir", n=8)
    # transmission (côté droit, y < 0) : plateau, manivelles, pédales, chaîne
    sd = -0.07
    revolution(acc, (BB.x, sd, BB.z), [(0.03, -0.003), (0.095, -0.003), (0.095, 0.003), (0.03, 0.003)], 32, "noir",
               lambda rad, r, s: Vector((0, s, 0)) if abs(s) > 0.001 else rad)
    revolution(acc, (BB.x, sd - 0.004, BB.z), [(0.06, -0.002), (0.10, -0.002)], 32, "plastique",
               lambda rad, r, s: Vector((0, -1, 0)))
    for s, ang in ((-1, math.radians(-60)), (1, math.radians(120))):
        pied = BB + V(math.cos(ang) * 0.17, s * 0.09, math.sin(ang) * 0.17)
        tube(acc, [BB + V(0, s * 0.082, 0), pied], 0.011, "noir", n=6)
        bloc(acc, pied + V(0, s * 0.05, 0), (0.05, 0.045, 0.011), "plastique", e=(0.25, 0.25), n=(10, 4))
    cog = R + V(0, sd, 0)
    for z_haut in (1, -1):
        a = V(BB.x, sd, BB.z + z_haut * 0.095)
        b = cog + V(0, 0, z_haut * 0.04)
        tube(acc, [a, b], 0.004, "noir", n=4, bouts=False)
    revolution(acc, cog, [(0.0, -0.006), (0.042, -0.006), (0.042, 0.006), (0.0, 0.006)], 20, "metal",
               lambda rad, r, s: Vector((0, s, 0)) if r < 0.04 else rad)
    # garde-boue arrière
    arc(acc, R, [(R_AR + 0.022, -0.033), (R_AR + 0.03, 0.0), (R_AR + 0.022, 0.033), (R_AR + 0.019, 0.03),
                 (R_AR + 0.027, 0.0), (R_AR + 0.019, -0.03)], math.radians(15), math.radians(205), 20, "plastique")
    # support du panier avant, fixé à la douille
    tube(acc, [H0 + U_DIR * 0.01 + V(0.0, 0, 0.0), V(0.62, 0, 0.795)], 0.013, "noir", n=8)
    for s in (-1, 1):
        tube(acc, [H1 + U_DIR * 0.05 + V(0.01, s * 0.02, 0), V(0.62, s * 0.09, 0.80)], 0.009, "noir", n=6)


def panier(acc):
    """Panier avant en tubes noirs, fond en bois (fixé au cadre)."""
    x0, x1, y, z0, z1 = 0.60, 0.97, 0.205, 0.80, 0.985
    bloc(acc, V((x0 + x1) / 2, 0, z0 + 0.008), ((x1 - x0) / 2 - 0.005, y - 0.005, 0.009), "bois", e=(0.12, 0.15),
         n=(12, 4))

    def cadre_h(z, r):
        pts = [V(x0, -y, z), V(x0, y, z), V(x1, y, z), V(x1, -y, z), V(x0, -y, z)]
        tube(acc, pts, r, "noir", n=6, bouts=False)
    cadre_h(z0, 0.008)
    cadre_h((z0 + z1) / 2, 0.005)
    cadre_h(z1, 0.009)
    for k in range(7):
        x = x0 + (x1 - x0) * k / 6
        for s in (-1, 1):
            tube(acc, [V(x, s * y, z0), V(x, s * y, z1)], 0.005, "noir", n=4, bouts=False)
    for k in range(1, 6):
        yy = -y + 2 * y * k / 6
        for x in (x0, x1):
            tube(acc, [V(x, yy, z0), V(x, yy, z1)], 0.005, "noir", n=4, bouts=False)
    # phare sous le panier
    bloc(acc, V(x1 - 0.01, 0, z0 - 0.04), (0.025, 0.035, 0.025), "plastique", n=(10, 6))
    bloc(acc, V(x1 + 0.014, 0, z0 - 0.04), (0.004, 0.026, 0.017), "metal", n=(10, 4))


def direction(acc):
    """Fourche suspendue, potence, cintre plat avec écran, garde-boue avant."""
    couronne = H0 + U_DIR * 0.03
    bloc(acc, couronne, (0.035, 0.07, 0.02), "noir", e=(0.4, 0.4), n=(12, 6))
    tube(acc, [H1 - U_DIR * 0.075, H0 + U_DIR * 0.02], 0.016, "noir", n=10)                # pivot
    for s in (-1, 1):
        haut = couronne + V(0, s * 0.055, 0)
        mil = haut + U_DIR * 0.16
        bas = F + V(0, s * 0.055, 0)
        tube(acc, [haut, mil + U_DIR * 0.03], 0.0165, "noir", n=10)
        tube(acc, [mil, bas + U_DIR * 0.01], [0.022, 0.019], "plastique", n=10)
    tube(acc, [couronne + U_DIR * 0.14 + V(0, -0.055, 0), couronne + U_DIR * 0.14 + V(0, 0.055, 0)], 0.012,
         "plastique", n=8)
    # potence et cintre
    hp = H1 - U_DIR * 0.06
    tube(acc, [hp, CINTRE + V(0.0, 0, -0.012)], 0.016, "noir", n=10)
    tube(acc, [CINTRE + V(0, -0.025, 0), CINTRE + V(0, 0.025, 0)], 0.02, "noir", n=10)
    for s in (-1, 1):
        bras = courbe([CINTRE, CINTRE + V(-0.01, s * 0.16, 0.003), CINTRE + V(-0.05, s * 0.30, 0.006)], 4)
        tube(acc, bras, 0.0115, "noir", n=8)
        poignee = [CINTRE + V(-0.031, s * 0.20, 0.004), CINTRE + V(-0.05, s * 0.30, 0.006)]
        tube(acc, poignee, 0.017, "plastique", n=10)
        lev = CINTRE + V(-0.03, s * 0.17, 0.004)
        tube(acc, [lev, lev + V(0.06, s * 0.025, -0.012), lev + V(0.075, s * 0.10, -0.02)], 0.005, "noir", n=4)
        bloc(acc, lev + V(0.0, 0, 0.0), (0.02, 0.012, 0.016), "noir", n=(8, 4))
    rot = Matrix.Rotation(math.radians(-35), 3, "Y")
    bloc(acc, CINTRE + V(-0.01, 0.06, 0.03), (0.032, 0.026, 0.008), "plastique", rot=rot, e=(0.2, 0.2), n=(10, 4))
    bloc(acc, CINTRE + V(-0.006, 0.06, 0.037), (0.025, 0.02, 0.003), "ecran", rot=rot, e=(0.15, 0.15), n=(8, 4))
    # garde-boue avant
    arc(acc, F, [(R_AV + 0.020, -0.03), (R_AV + 0.028, 0.0), (R_AV + 0.020, 0.03), (R_AV + 0.017, 0.027),
                 (R_AV + 0.025, 0.0), (R_AV + 0.017, -0.027)], math.radians(-25), math.radians(140), 22, "plastique")
    for s in (-1, 1):
        tube(acc, [F + V(0, s * 0.06, 0), F + V(0.30, s * 0.035, 0.10)], 0.003, "metal", n=4)
    panier(acc)


# ---------------------------------------------------------------------------

def _travail_vers_local(p):
    """Repère de travail (avant +x) -> repère du vélo (avant -Y, axe des roues selon X, origine au sol)."""
    return Vector((p[1], -(p[0] - X_MI), p[2]))


# origines des pièces dans le repère du vélo (la roue avant est donnée relativement à la direction)
ORIGINES = {
    "cadre": Vector((0, 0, 0)),
    "direction": _travail_vers_local(H0),
    "roue_arriere": _travail_vers_local(R),
}
ORIGINES["roue_avant"] = _travail_vers_local(F) - ORIGINES["direction"]
SELLE_LOCAL = _travail_vers_local(SELLE)
CINTRE_LOCAL = _travail_vers_local(CINTRE)
EMPATTEMENT = X_AV - X_AR


def _maillage(nom, acc, origine_travail, materiaux):
    o = _travail_vers_local(origine_travail)
    me = bpy.data.meshes.new(nom)
    me.from_pydata([tuple(_travail_vers_local(v) - o) for v in acc.v], [], acc.f)
    utilisees = [c for c in CLES if c in set(acc.m)]
    for cle in utilisees:
        me.materials.append(materiaux[cle])
    me.polygons.foreach_set("material_index", [utilisees.index(m) for m in acc.m])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    try:
        me.set_sharp_from_angle(angle=math.radians(40))
    except AttributeError:
        pass
    me.update()
    return me


def construire(nom, materiaux):
    """Maillages des pièces : {pièce: (maillage, origine)} ; materiaux : clé de CLES -> matériau Blender.
    Origines dans le repère du vélo, sauf la roue avant (relative à la direction, dont elle est l'enfant)."""
    pieces = {}
    acc = Acc()
    cadre(acc)
    pieces["cadre"] = (_maillage(f"{nom}_cadre", acc, Vector((X_MI, 0, 0)), materiaux), ORIGINES["cadre"])
    acc = Acc()
    direction(acc)
    pieces["direction"] = (_maillage(f"{nom}_direction", acc, H0, materiaux), ORIGINES["direction"])
    acc = Acc()
    roue(acc, (0, 0, 0), R_AV, 0.026, 0.026, 0.045, 32)
    pieces["roue_avant"] = (_maillage(f"{nom}_roue_avant", acc, Vector((0, 0, 0)), materiaux),
                            ORIGINES["roue_avant"])
    acc = Acc()
    roue(acc, (0, 0, 0), R_AR, 0.029, 0.085, 0.042, 28)
    pieces["roue_arriere"] = (_maillage(f"{nom}_roue_arriere", acc, Vector((0, 0, 0)), materiaux),
                              ORIGINES["roue_arriere"])
    return pieces

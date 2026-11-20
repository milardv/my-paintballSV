# Citroën C5 Aircross (silhouette de la génération actuelle) pour le parc : SUV compact de 4,50 m de long,
# 1,86 m de large, 1,67 m de haut avec les barres de toit, empattement 2,73 m, roues de 19 pouces.
# Repère local : x longueur (avant en +x), y largeur, z haut ; voiture centrée, roues posées sur z = 0.
# Caisse basse lissée par sections le long de x, pavillon (vitrages, montants noirs, jonc chromé en C) par
# rangées horizontales, détails en plaques posées sur la caisse. On construit la moitié gauche (y >= 0), puis
# on la symétrise ; les pièces centrales et les caractères des plaques sont ajoutés après la symétrie.
import math

import bmesh
import bpy
from mathutils import Vector

L2 = 2.25                       # demi-longueur
X_AV, X_AR = 1.30, -1.43        # essieux (empattement 2,73 m)
R_ROUE, Y_ROUE = 0.37, 0.80     # rayon du pneu 235/55 R19, demi-voie
R_ARCHE, Z_ARCHE = 0.43, 0.37   # passages de roue
LARG = 0.92                     # demi-largeur de caisse
R_PLAN = {1: 0.34, -1: 0.28}    # arrondi des coins en plan (avant, arrière)
JOINTS = (0.84, -0.28, -0.99)   # joints de portes
AIRBUMPS = ((-0.22, 0.76), (-0.92, -0.36))

# Matières (clé -> réglages de materiau() : couleur, rugosite, metal, emission)
CLES = ("carrosserie", "noir", "plastique", "vitre", "chrome", "phare", "feu", "pneu", "jante", "plaque")
MATIERES = {
    "noir": dict(couleur=(0.012, 0.012, 0.014), rugosite=0.12, metal=0.0),
    "plastique": dict(couleur=(0.03, 0.03, 0.032), rugosite=0.8),
    "vitre": dict(couleur=(0.015, 0.02, 0.025), rugosite=0.04, metal=0.4),
    "chrome": dict(couleur=(0.85, 0.86, 0.88), rugosite=0.1, metal=1.0),
    "phare": dict(couleur=(0.9, 0.93, 1.0), rugosite=0.1, emission=(0.85, 0.9, 1.0)),
    "feu": dict(couleur=(0.5, 0.01, 0.01), rugosite=0.15, emission=(0.45, 0.0, 0.0)),
    "pneu": dict(couleur=(0.022, 0.022, 0.022), rugosite=0.9),
    "jante": dict(couleur=(0.72, 0.73, 0.75), rugosite=0.22, metal=1.0),
    "plaque": dict(couleur=(0.9, 0.9, 0.88), rugosite=0.5),
}
CARROSSERIES = {
    "noir": dict(couleur=(0.012, 0.012, 0.015), rugosite=0.14, metal=0.6),
    "blanc": dict(couleur=(0.86, 0.86, 0.85), rugosite=0.2, metal=0.1),
}


def lisse(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class Acc:
    """Sommets, faces et clés de matière ; hint : direction extérieure pour orienter la face."""

    def __init__(self):
        self.v, self.f, self.m = [], [], []

    def sv(self, p):
        self.v.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.v) - 1

    def face(self, ids, mat, hint=None):
        ids = [i for k, i in enumerate(ids) if i != ids[k - 1]]
        if len(ids) < 3:
            return
        if hint is not None:
            n = Vector((0, 0, 0))
            for k in range(len(ids)):
                a, b = self.v[ids[k]], self.v[ids[(k + 1) % len(ids)]]
                n.x += (a[1] - b[1]) * (a[2] + b[2])
                n.y += (a[2] - b[2]) * (a[0] + b[0])
                n.z += (a[0] - b[0]) * (a[1] + b[1])
            if n.dot(Vector(hint)) < 0:
                ids.reverse()
        self.f.append(tuple(ids))
        self.m.append(mat)

    def symetriser(self):
        n = len(self.v)
        self.v += [(x, -y, z) for x, y, z in self.v]
        self.f += [tuple(i + n for i in reversed(f)) for f in self.f]
        self.m += list(self.m)

    def ajouter(self, autre):
        n = len(self.v)
        self.v += autre.v
        self.f += [tuple(i + n for i in f) for f in autre.f]
        self.m += autre.m


def _cr(p0, p1, p2, p3, t):
    """Catmull-Rom centripète (évite les boucles entre points proches)."""
    def tj(ti, a, b):
        return ti + max(1e-4, math.dist(a, b)) ** 0.5
    t0 = 0.0
    t1 = tj(t0, p0, p1)
    t2 = tj(t1, p1, p2)
    t3 = tj(t2, p2, p3)
    u = t1 + (t2 - t1) * t

    def lp(a, b, ta, tb):
        w = (u - ta) / (tb - ta)
        return (a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w)
    a1, a2, a3 = lp(p0, p1, t0, t1), lp(p1, p2, t1, t2), lp(p2, p3, t2, t3)
    return lp(lp(a1, a2, t0, t2), lp(a2, a3, t1, t3), t1, t2)


# ---------------------------------------------------------------------------
# Caisse basse : sections (y, z) le long de x
# ---------------------------------------------------------------------------

def ceinture(x):
    z = 1.00 - 0.05 * min(1.0, (x - 1.05) / 1.2) if x > 1.05 else 1.00 + 0.025 * (1.05 - x) / 2.2
    return z + 0.06 * lisse(-1.15, -1.75, x)          # remontée de la ligne de vitrage sur la custode


def dessus(x):
    return ceinture(x) + 0.02 + 0.035 * lisse(0.85, 1.1, x)   # capot haut et plat


def zbas(x):
    return 0.235 + 0.10 * lisse(1.80, L2, x) + 0.12 * lisse(-1.95, -L2, x)


def arche(x):
    for xa in (X_AV, X_AR):
        dx = abs(x - xa)
        if dx < R_ARCHE:
            return Z_ARCHE + R_ARCHE * (1 - (dx / R_ARCHE) ** 2.4) ** (1 / 2.4)
    return None


def relief(x):
    """Saillie des Airbump sur le bas des portes."""
    for a, b in AIRBUMPS:
        if a <= x <= b:
            return 0.013 * min(1.0, (x - a) / 0.02, (b - x) / 0.02)
    return 0.0


def rake(bout, z):
    if bout > 0:
        return -0.07 * max(0.0, (z - 0.80) / 0.2) ** 2 - 0.07 * max(0.0, (0.50 - z) / 0.25) ** 2
    return 0.06 * max(0.0, (z - 0.95) / 0.16) ** 2 + 0.05 * max(0.0, (0.45 - z) / 0.12) ** 2


SEG_BAS = (2, 2, 2, 1, 1, 2, 1, 4, 4, 2, 3, 2)   # échantillons entre points de contrôle successifs
_ANNEAUX = {}


def anneau(x):
    """Demi-section (bas centre -> flanc gauche -> dessus centre), z croissant ; et segment de chaque arête."""
    cle = round(x, 7)
    if cle in _ANNEAUX:
        return _ANNEAUX[cle]
    zb, zs, zt, ab = zbas(x), ceinture(x), dessus(x), relief(x)
    c = [[0.0, zb], [0.78, zb], [0.885, zb + 0.035], [0.912, 0.37], [0.918, 0.40], [0.918 + ab, 0.412],
         [0.921 + ab, 0.568], [0.924, 0.58], [0.93, 0.89], [0.902, zs], [0.845, zt - 0.008], [0.45, zt + 0.022],
         [0.0, zt + 0.03]]
    a = arche(x)
    if a is not None:
        c[0][1] = c[1][1] = a
        c[1][0] = 0.70
        c[2] = [0.925, a]
        c[3] = [0.94, a + 0.065]
    for k in range(2, 10):
        c[k][1] = max(c[k][1], c[k - 1][1] + (0.012 if k > 2 else 0.0))
    # bouts : arrondi en plan, nez et hayon arrondis, profils inclinés
    bout = 1 if x > 0 else -1
    d = L2 - abs(x)
    r = R_PLAN[bout]
    g = 1.0 - (r - math.sqrt(max(0.0, r * r - (r - d) ** 2))) / LARG if d < r else 1.0
    rt = 0.06 if bout > 0 else 0.05
    chute = rt - math.sqrt(max(0.0, rt * rt - (rt - d) ** 2)) if d < rt else 0.0
    ztop = c[-1][1]
    pts2 = [c[0]]
    segs = []
    ext = [[-c[1][0], c[1][1]]] + c + [[-c[-2][0], c[-2][1]]]
    for k in range(len(c) - 1):
        for s in range(SEG_BAS[k]):
            if s:
                pts2.append(list(_cr(ext[k], ext[k + 1], ext[k + 2], ext[k + 3], s / SEG_BAS[k])))
            segs.append(k)
        pts2.append(list(c[k + 1]))
    pts = []
    zprec = -1.0
    for y, z in pts2:
        if chute and z > 0.70:
            z -= chute * (z - 0.70) / (ztop - 0.70)
        z = max(z, zprec)
        zprec = z
        xx = x + max(0.0, 1 - d / 0.45) ** 2 * rake(bout, z)
        pts.append((xx, y * g, z))
    _ANNEAUX[cle] = (pts, segs)
    return pts, segs


def point_cote(pts, z):
    """(x, y) de la demi-section à la hauteur z (None hors section)."""
    for j in range(len(pts) - 1):
        a, b = pts[j], pts[j + 1]
        if a[2] <= z <= b[2] and b[2] > a[2]:
            w = (z - a[2]) / (b[2] - a[2])
            return a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w
    return None


def _stations():
    obl = []
    for d in (0.0, 0.004, 0.012, 0.025, 0.045, 0.07, 0.10, 0.14, 0.19, 0.25, 0.32, 0.40):
        obl += [L2 - d, -L2 + d]
    for xa in (X_AV, X_AR):
        obl += [xa + R_ARCHE * 0.9999 * k / 10 for k in range(-10, 11)]
        obl += [xa - R_ARCHE - 1e-4, xa + R_ARCHE + 1e-4]
    for j in JOINTS:
        obl += [j - 0.003, j + 0.003]
    for a, b in AIRBUMPS:
        obl += [a, a + 0.02, b - 0.02, b]
    xs = list(obl)
    n = int(2 * L2 / 0.06)
    for i in range(1, n):
        u = -L2 + 2 * L2 * i / n
        if arche(u) is None and min(abs(u - o) for o in obl) > 0.015:
            xs.append(u)
    xs = sorted(set(round(x, 7) for x in xs))
    return xs


X_GH = (-2.10, 1.02)   # étendue du pavillon au niveau de la ceinture


def mat_bas(k, xm, zm):
    if k <= 2:
        return "plastique"
    if k == 3 and arche(xm) is not None:
        return "plastique"
    if k in (4, 5, 6) and relief(xm) > 0:
        return "plastique"
    if 3 <= k <= 8 and any(abs(xm - j) < 0.003 for j in JOINTS):
        return "plastique"
    if k >= 10 and X_GH[0] + 0.12 < xm < X_GH[1] - 0.12:
        return "plastique"
    if zm < 0.44 and (xm > 1.78 or xm < -1.90):
        return "plastique"
    return "carrosserie"


def caisse(acc):
    xs = _stations()
    anneaux = [[acc.sv(p) for p in anneau(x)[0]] for x in xs]
    segs = anneau(xs[0])[1]
    V = acc.v
    for i in range(len(xs) - 1):
        r0, r1 = anneaux[i], anneaux[i + 1]
        xm = (xs[i] + xs[i + 1]) / 2
        for j in range(len(r0) - 1):
            zm = (V[r0[j]][2] + V[r0[j + 1]][2] + V[r1[j]][2] + V[r1[j + 1]][2]) / 4
            acc.face((r0[j], r0[j + 1], r1[j + 1], r1[j]), mat_bas(segs[j], xm, zm))
    # faces avant et arrière : bandes horizontales entre le flanc et le plan de symétrie
    for bout, r in ((1, anneaux[-1]), (-1, anneaux[0])):
        ctr = [i if abs(V[i][1]) < 1e-9 else acc.sv((V[i][0], 0.0, V[i][2])) for i in r]
        for j in range(len(r) - 1):
            if V[r[j + 1]][2] - V[r[j]][2] < 1e-6:
                continue
            zm = (V[r[j]][2] + V[r[j + 1]][2]) / 2
            acc.face((r[j], r[j + 1], ctr[j + 1], ctr[j]), "plastique" if zm < 0.44 else "carrosserie",
                     hint=(bout, 0, 0))
    # bloc sombre entre les roues d'un même essieu (on ne voit pas au travers des passages de roue)
    for xa in (X_AV, X_AR):
        boite(acc, xa - 0.36, 0.0, 0.30, xa + 0.36, 0.66, 0.80, "plastique", sans=("y0",))


def boite(acc, x0, y0, z0, x1, y1, z1, mat, sans=()):
    P = [acc.sv(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f, h, nom in (((0, 1, 2, 3), (0, 0, -1), "z0"), ((4, 5, 6, 7), (0, 0, 1), "z1"),
                      ((0, 1, 5, 4), (0, -1, 0), "y0"), ((2, 3, 7, 6), (0, 1, 0), "y1"),
                      ((1, 2, 6, 5), (1, 0, 0), "x1"), ((3, 0, 4, 7), (-1, 0, 0), "x0")):
        if nom not in sans:
            acc.face([P[i] for i in f], mat, hint=h)


# ---------------------------------------------------------------------------
# Pavillon : rangées horizontales (plan en super-ellipse), vitrages, montants, jonc chromé
# ---------------------------------------------------------------------------

def xf_gh(h):
    return 1.02 - 0.78 * (0.65 * h + 0.35 * h ** 3)


def xr_gh(h):
    return -2.10 + 0.22 * (0.55 * h + 0.45 * h ** 3)


def toit(x):
    return 1.60 - 0.03 * lisse(-1.2, -1.9, x)


# (h, base de hauteur, décalage, demi-largeur)
RANGS = [(0.00, "c", -0.012, 0.885), (0.02, "c", 0.012, 0.878), (0.06, "c", 0.035, 0.866),
         (None, "m", 1 / 3, None), (None, "m", 2 / 3, None),
         (0.86, "t", -0.085, 0.727), (0.90, "t", -0.060, 0.715), (0.96, "t", -0.020, 0.695),
         (1.00, "t", 0.0, 0.64)]
N_SE = 8.0


def _sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def colonnes():
    """Colonnes du demi-tour (avant -> arrière) : (type, paramètre, nature de la travée qui suit)."""
    cols = []
    for th in (0.0, 0.15, 0.30, 0.45):
        cols.append(("t", th, "pb"))
    cols += [("t", 0.60, "ma"), ("t", 0.72, "ma"), ("t", 0.85, "ma")]

    def xc(fn):
        return ("x", fn)
    side = [
        (lambda h, f, r: f - 0.20, "v", 6, lambda h, f, r: -0.24 - 0.04 * h),
        (lambda h, f, r: -0.24 - 0.04 * h, "mc", 1, lambda h, f, r: -0.33 - 0.04 * h),
        (lambda h, f, r: -0.33 - 0.04 * h, "v", 5, lambda h, f, r: -1.02 + 0.04 * h),
        (lambda h, f, r: -1.02 + 0.04 * h, "mc", 1, lambda h, f, r: -1.10 + 0.04 * h),
        (lambda h, f, r: -1.10 + 0.04 * h, "v", 3, lambda h, f, r: r + 0.42 - 0.12 * h),
        (lambda h, f, r: r + 0.42 - 0.12 * h, "cv", 1, lambda h, f, r: r + 0.39 - 0.12 * h),
        (lambda h, f, r: r + 0.39 - 0.12 * h, "md", 2, lambda h, f, r: r + 0.20),
    ]
    for f0, nat, n, f1 in side:
        for k in range(n):
            w = k / n
            cols.append(("x", (lambda h, f, r, f0=f0, f1=f1, w=w: f0(h, f, r) + (f1(h, f, r) - f0(h, f, r)) * w),
                         nat))
    cols += [("t", math.pi - 0.85, "md"), ("t", math.pi - 0.72, "md"), ("t", math.pi - 0.60, "lu"),
             ("t", math.pi - 0.45, "lu"), ("t", math.pi - 0.30, "lu"), ("t", math.pi - 0.15, "lu"),
             ("t", math.pi, None)]
    return cols


def mat_gh(bande, nat):
    cote = nat in ("v", "mc", "cv")
    if bande in (1, 5):
        return "chrome" if cote else "noir"
    if bande in (2, 3, 4):
        if nat in ("pb", "v", "lu"):
            return "vitre"
        return "chrome" if nat == "cv" else "noir"
    return "noir"


def pavillon(acc):
    cols = colonnes()
    rangs = []
    for ir, (h, base, dec, B) in enumerate(RANGS):
        if base == "m":
            h2, h3 = RANGS[2], RANGS[5]
            h = h2[0] + dec * (h3[0] - h2[0])
            B = h2[3] + dec * (h3[3] - h2[3]) + 0.006 * math.sin(math.pi * dec)
        f, r = xf_gh(h), xr_gh(h)
        xc, A = (f + r) / 2, (f - r) / 2
        ligne = []
        for typ, p, _ in cols:
            if typ == "t":
                x = xc + A * _sgnpow(math.cos(p), 2 / N_SE)
                sn = abs(math.sin(p))
                y = B * sn ** (2 / N_SE) if sn > 1e-9 else 0.0
            else:
                x = p(h, f, r)
                y = B * max(0.0, 1 - abs((x - xc) / A) ** N_SE) ** (1 / N_SE)
            if base == "c":
                z = ceinture(x) + dec
            elif base == "t":
                z = toit(x) + dec
            else:
                z2 = ceinture(x) + RANGS[2][2]
                z3 = toit(x) + RANGS[5][2]
                z = z2 + dec * (z3 - z2)
            ligne.append((x, y, z))
        rangs.append(ligne)
    # toit : anneaux resserrés vers un segment central
    haut = rangs[-1]
    xa, xb = xr_gh(1.0) + 0.35, xf_gh(1.0) - 0.35
    for s in (0.75, 0.5, 0.25, 0.0):
        ligne = []
        for x, y, z in haut:
            tx = min(xb, max(xa, x))
            ligne.append((tx + (x - tx) * s, y * s, z + 0.022 * (1 - s * s)))
        rangs.append(ligne)
    ids = [[acc.sv(p) for p in ligne] for ligne in rangs]
    ctr = Vector((-0.8, 0.0, 0.85))
    for b in range(len(ids) - 1):
        for c in range(len(cols) - 1):
            q = (ids[b][c], ids[b][c + 1], ids[b + 1][c + 1], ids[b + 1][c])
            m = Vector(acc.v[q[0]]) + Vector(acc.v[q[2]])
            acc.face(q, mat_gh(b, cols[c][2]), hint=m / 2 - ctr)


# ---------------------------------------------------------------------------
# Plaques posées sur les faces avant et arrière (calandre, phares, feux, plaques...)
# ---------------------------------------------------------------------------

_D = [k * 0.004 for k in range(160)]


def _surf_x(bout, ya, z):
    prec = None
    for d in _D:
        p = point_cote(anneau(bout * (L2 - d))[0], z)
        if p is None:
            continue
        if p[1] >= ya:
            if prec is None or p[1] - prec[1] < 1e-9:
                return p[0]
            w = (ya - prec[1]) / (p[1] - prec[1])
            return prec[0] + (p[0] - prec[0]) * w
        prec = p
    return prec[0] if prec else bout * L2


def surf(bout, y, z):
    """Point de la face avant (bout = 1) ou arrière (-1) en (y, z) et normale extérieure en plan."""
    ya = abs(y)
    x = _surf_x(bout, ya, z)
    e = 0.006
    dxdy = (_surf_x(bout, ya + e, z) - _surf_x(bout, max(0.0, ya - e), z)) / (ya + e - max(0.0, ya - e))
    n = Vector((bout, -bout * dxdy * (1 if y >= 0 else -1), 0.0)).normalized()
    return Vector((x, y, z)), n


def bande(acc, bout, y0, y1, zb, zh, saillie, mat, ncol=6, prof=0.025, ouvert_y0=False):
    """Plaque de y0 à y1 entre zb(y) et zh(y), saillante de la caisse ; flancs refermés vers l'intérieur."""
    zb_ = zb if callable(zb) else (lambda y, v=zb: v)
    zh_ = zh if callable(zh) else (lambda y, v=zh: v)
    F, Bk, N = [], [], []
    for i in range(ncol + 1):
        y = y0 + (y1 - y0) * i / ncol
        cf, cb = [], []
        for z in (zb_(y), zh_(y)):
            p, n = surf(bout, y, z)
            cf.append(acc.sv(p + n * saillie))
            cb.append(acc.sv(p - n * prof))
        F.append(cf)
        Bk.append(cb)
        N.append(n)
    for i in range(ncol):
        n = (N[i] + N[i + 1]) / 2
        acc.face((F[i][0], F[i + 1][0], F[i + 1][1], F[i][1]), mat, hint=n)
        acc.face((F[i][0], F[i + 1][0], Bk[i + 1][0], Bk[i][0]), mat, hint=(0, 0, -1))
        acc.face((F[i][1], F[i + 1][1], Bk[i + 1][1], Bk[i][1]), mat, hint=(0, 0, 1))
    for i, sg in ((0, -1), (ncol, 1)):
        if i == 0 and ouvert_y0:
            continue
        t = Vector((-N[i].y, N[i].x, 0)) * bout * sg
        acc.face((F[i][0], F[i][1], Bk[i][1], Bk[i][0]), mat, hint=t)


def details_avant(acc):
    av = 1
    bande(acc, av, 0.0, 0.46, lambda y: 0.53 + 0.04 * (y / 0.46) ** 2, 0.795, 0.005, "noir", 8, ouvert_y0=True)
    for z in (0.60, 0.66, 0.72):
        bande(acc, av, 0.0, 0.42, z, z + 0.008, 0.011, "chrome", 6, ouvert_y0=True)
    # barre noire portant le double chevron, prolongée par les ailes chromées jusqu'aux feux de jour
    bande(acc, av, 0.0, 0.56, 0.80, 0.858, 0.006, "noir", 8, ouvert_y0=True)
    for dz in (0.0, 0.02):
        bande(acc, av, 0.0, 0.13, lambda y, dz=dz: 0.808 + dz + 0.03 * (1 - y / 0.13),
              lambda y, dz=dz: 0.820 + dz + 0.03 * (1 - y / 0.13), 0.013, "chrome", 4, ouvert_y0=True)
    bande(acc, av, 0.13, 0.56, 0.832, 0.838, 0.010, "chrome", 6)
    # signature lumineuse sur deux niveaux : feux de jour fins en haut, bloc optique en dessous
    bande(acc, av, 0.56, 0.87, lambda y: 0.826 + 0.02 * (y - 0.56) / 0.31,
          lambda y: 0.848 + 0.02 * (y - 0.56) / 0.31, 0.009, "phare", 8)
    bande(acc, av, 0.50, 0.88, 0.63, lambda y: 0.795 + 0.015 * (y - 0.50) / 0.38, 0.010, "noir", 12)
    bande(acc, av, 0.54, 0.86, 0.772, lambda y: 0.782 + 0.004 * (y - 0.54) / 0.32, 0.015, "phare", 10)
    for y0, y1 in ((0.56, 0.65), (0.67, 0.76)):
        bande(acc, av, y0, y1, 0.675, 0.735, 0.016, "phare", 4)
    bande(acc, av, 0.78, 0.84, 0.675, 0.735, 0.014, "chrome", 3)
    # bouclier : entrée d'air, sabot chromé, prises latérales à accent chromé
    bande(acc, av, 0.0, 0.50, 0.375, 0.435, 0.006, "noir", 6, ouvert_y0=True)
    bande(acc, av, 0.0, 0.40, 0.348, 0.364, 0.010, "chrome", 5, ouvert_y0=True)
    bande(acc, av, 0.62, 0.87, 0.37, 0.55, 0.012, "noir", 10)
    bande(acc, av, 0.60, 0.62, 0.37, 0.55, 0.016, "chrome", 1)
    bande(acc, av, 0.0, 0.26, 0.42, 0.53, 0.02, "plaque", 3, ouvert_y0=True)


def details_arriere(acc):
    ar = -1
    bande(acc, ar, 0.50, 0.88, 0.895, 1.035, 0.010, "noir", 12)
    for zb_, zh_ in ((0.91, 0.948), (0.983, 1.02)):
        bande(acc, ar, 0.53, 0.86, zb_, zh_, 0.016, "feu", 10)
    bande(acc, ar, 0.0, 0.50, 0.945, 0.99, 0.006, "noir", 6, ouvert_y0=True)
    for dz in (0.0, 0.016):
        bande(acc, ar, 0.0, 0.07, lambda y, dz=dz: 0.950 + dz + 0.016 * (1 - y / 0.07),
              lambda y, dz=dz: 0.958 + dz + 0.016 * (1 - y / 0.07), 0.012, "chrome", 3, ouvert_y0=True)
    bande(acc, ar, 0.0, 0.26, 0.63, 0.74, 0.016, "plaque", 3, ouvert_y0=True)
    bande(acc, ar, 0.0, 0.55, 0.37, 0.386, 0.010, "chrome", 6, ouvert_y0=True)
    bande(acc, ar, 0.68, 0.82, 0.40, 0.425, 0.010, "feu", 4)


def caracteres(acc):
    """Plaques : bande bleue et caractères (AB-123-CD) en pavés sombres, vus de loin."""
    for bout, z0 in ((1, 0.42), (-1, 0.63)):
        sail = 0.02 if bout > 0 else 0.016
        pos = [-0.17, -0.13, -0.06, -0.02, 0.02, 0.09, 0.13]
        for y in pos:
            bande(acc, bout, y - 0.015, y + 0.015, z0 + 0.025, z0 + 0.085, sail + 0.002, "plastique", 1, prof=0.004)
        for y in (-0.095, 0.055):
            bande(acc, bout, y - 0.008, y + 0.008, z0 + 0.052, z0 + 0.058, sail + 0.002, "plastique", 1, prof=0.004)


# ---------------------------------------------------------------------------
# Pièces en super-ellipsoïdes : rétroviseurs, poignées, barres de toit, becquet
# ---------------------------------------------------------------------------

def ellipsoide(acc, c, demi, mat, n=(16, 8), e=(0.4, 0.4)):
    a, b, cz = demi
    c = Vector(c)
    lignes = []
    for i in range(n[1] + 1):
        u = -math.pi / 2 + math.pi * i / n[1]
        if i in (0, n[1]):
            p = c + Vector((0, 0, cz * (1 if i else -1)))
            lignes.append([acc.sv(p)] * n[0])
            continue
        ligne = []
        for j in range(n[0]):
            v = 2 * math.pi * j / n[0]
            cu = _sgnpow(math.cos(u), e[0])
            ligne.append(acc.sv(c + Vector((a * cu * _sgnpow(math.cos(v), e[1]), b * cu * _sgnpow(math.sin(v), e[1]),
                                            cz * _sgnpow(math.sin(u), e[0])))))
        lignes.append(ligne)
    for i in range(n[1]):
        for j in range(n[0]):
            k = (j + 1) % n[0]
            q = (lignes[i][j], lignes[i][k], lignes[i + 1][k], lignes[i + 1][j])
            m = sum((Vector(acc.v[x]) for x in set(q)), Vector()) / len(set(q))
            acc.face(q, mat, hint=m - c)


def y_flanc(x, z):
    p = point_cote(anneau(x)[0], z)
    return p[1] if p else LARG


def details_cote(acc):
    # rétroviseur : coque noire, bras, glace
    ellipsoide(acc, (0.80, 0.985, 1.10), (0.075, 0.105, 0.062), "noir", (16, 8), (0.45, 0.45))
    ellipsoide(acc, (0.83, 0.895, 1.055), (0.055, 0.05, 0.024), "noir", (10, 5), (0.5, 0.5))
    g = [acc.sv(p) for p in ((0.724, 0.925, 1.075), (0.724, 1.055, 1.075), (0.724, 1.055, 1.13),
                             (0.724, 0.925, 1.13))]
    acc.face(g, "chrome", hint=(-1, 0, 0))
    # poignées de portes
    for xh in (0.28, -0.60):
        zh = 0.93
        ellipsoide(acc, (xh, y_flanc(xh, zh) + 0.004, zh), (0.085, 0.014, 0.016), "carrosserie", (12, 6),
                   (0.5, 0.5))
    # barres de toit alu et pieds
    ellipsoide(acc, (-0.82, 0.585, 1.648), (0.90, 0.017, 0.017), "chrome", (20, 6), (0.35, 0.3))
    for xp in (0.0, -1.62):
        ellipsoide(acc, (xp, 0.585, 1.615), (0.07, 0.022, 0.03), "noir", (10, 5), (0.4, 0.4))


def details_centre(acc):
    ellipsoide(acc, (-1.93, 0.0, 1.56), (0.09, 0.56, 0.028), "noir", (20, 6), (0.35, 0.3))
    ellipsoide(acc, (-2.015, 0.0, 1.55), (0.008, 0.2, 0.008), "feu", (12, 4), (0.4, 0.4))


# ---------------------------------------------------------------------------
# Roues : pneu à flancs bombés, jante bi-ton à dix branches, disque de frein
# ---------------------------------------------------------------------------

def revolution(acc, centre, profil, nseg, mat, hint):
    """profil : (r, s) avec s latéral vers l'extérieur ; hint(p_local_r, s, dir) -> vecteur extérieur."""
    cx, cy, cz = centre
    grille = []
    for k in range(nseg):
        ph = 2 * math.pi * k / nseg
        grille.append([acc.sv((cx + r * math.cos(ph), cy + s, cz + r * math.sin(ph))) for r, s in profil])
    for k in range(nseg):
        k2 = (k + 1) % nseg
        ph = 2 * math.pi * (k + 0.5) / nseg
        rad = Vector((math.cos(ph), 0, math.sin(ph)))
        for j in range(len(profil) - 1):
            r = (profil[j][0] + profil[j + 1][0]) / 2
            s = (profil[j][1] + profil[j + 1][1]) / 2
            mj = mat(j) if callable(mat) else mat
            acc.face((grille[k][j], grille[k2][j], grille[k2][j + 1], grille[k][j + 1]), mj, hint=hint(rad, r, s))


def disque(acc, centre, rayon, s, nseg, mat):
    cx, cy, cz = centre
    c = acc.sv((cx, cy + s, cz))
    bord = [acc.sv((cx + rayon * math.cos(2 * math.pi * k / nseg), cy + s, cz + rayon * math.sin(2 * math.pi * k / nseg)))
            for k in range(nseg)]
    for k in range(nseg):
        acc.face((c, bord[k], bord[(k + 1) % nseg]), mat, hint=(0, 1, 0))


PNEU = [(0.243, -0.100), (0.27, -0.112), (0.31, -0.118), (0.345, -0.115), (0.362, -0.104), (0.370, -0.085),
        (0.372, -0.045), (0.366, -0.043), (0.366, -0.033), (0.372, -0.031), (0.373, 0.0), (0.372, 0.031),
        (0.366, 0.033), (0.366, 0.043), (0.372, 0.045), (0.370, 0.085), (0.362, 0.104), (0.345, 0.115),
        (0.31, 0.118), (0.27, 0.112), (0.243, 0.100)]
LEVRE = [(0.243, 0.100), (0.250, 0.105), (0.246, 0.113), (0.232, 0.112), (0.221, 0.103), (0.217, 0.088)]


def roue(acc, xw, yw):
    c = (xw, yw, R_ROUE)
    revolution(acc, c, PNEU, 40, "pneu", lambda rad, r, s: rad * r + Vector((0, s, 0)))
    revolution(acc, c, LEVRE, 40, "jante", lambda rad, r, s: Vector((0, 1, 0)))
    revolution(acc, c, [(0.217, 0.088), (0.212, 0.0)], 40, "noir", lambda rad, r, s: -rad)
    disque(acc, c, 0.212, 0.0, 24, "noir")
    revolution(acc, c, [(0.185, 0.018), (0.09, 0.018)], 24, "jante", lambda rad, r, s: Vector((0, 1, 0)))
    revolution(acc, c, [(0.072, 0.025), (0.072, 0.07)], 16, "noir", lambda rad, r, s: rad)
    disque(acc, c, 0.072, 0.07, 16, "jante")
    disque(acc, c, 0.03, 0.074, 12, "chrome")
    # dix branches groupées par paires : face polie, flancs noirs
    cx, cy, cz = c
    for k in range(5):
        for dphi in (-0.13, 0.13):
            ph = 2 * math.pi * k / 5 + math.pi / 2 + dphi
            u = Vector((math.cos(ph), 0, math.sin(ph)))
            t = Vector((-math.sin(ph), 0, math.cos(ph)))
            av, ar = [], []
            for r in (0.068, 0.11, 0.16, 0.218):
                w = 0.010 + 0.008 * (r - 0.068) / 0.15
                s = 0.072 + (r - 0.068) / 0.15 * 0.028
                base = Vector(c) + u * r
                av.append((acc.sv(base + t * w + Vector((0, s, 0))), acc.sv(base - t * w + Vector((0, s, 0)))))
                ar.append((acc.sv(base + t * w + Vector((0, s - 0.03, 0))), acc.sv(base - t * w + Vector((0, s - 0.03, 0)))))
            for i in range(3):
                acc.face((av[i][0], av[i + 1][0], av[i + 1][1], av[i][1]), "jante", hint=(0, 1, 0))
                acc.face((av[i][0], av[i + 1][0], ar[i + 1][0], ar[i][0]), "noir", hint=t)
                acc.face((av[i][1], av[i + 1][1], ar[i + 1][1], ar[i][1]), "noir", hint=-t)


# ---------------------------------------------------------------------------

def construire(nom, materiaux):
    """Maillage de la voiture ; materiaux : clé de CLES -> matériau Blender."""
    acc = Acc()
    caisse(acc)
    pavillon(acc)
    details_avant(acc)
    details_arriere(acc)
    details_cote(acc)
    for xw in (X_AV, X_AR):
        roue(acc, xw, Y_ROUE)
    acc.symetriser()
    centre = Acc()
    details_centre(centre)
    caracteres(centre)
    acc.ajouter(centre)

    me = bpy.data.meshes.new(nom)
    me.from_pydata(acc.v, [], acc.f)
    for cle in CLES:
        me.materials.append(materiaux[cle])
    me.polygons.foreach_set("material_index", [CLES.index(m) for m in acc.m])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if abs(v.co.y) < 1e-7], dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    try:
        me.set_sharp_from_angle(angle=math.radians(38))
    except AttributeError:
        pass
    me.update()
    return me

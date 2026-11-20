# Données ouvertes du domaine (IGN Géoplateforme, licence Etalab 2.0) et mesures dans le repère D-003.
#   python3.13 outils/donnees_ouvertes.py telecharger   orthophoto HR (13 cm) et LiDAR HD MNT/MNS (50 cm)
#   python3.13 outils/donnees_ouvertes.py mesurer       → travail/plan_mesure.json + travail/donnees-ouvertes/plan_mesure.png
# Interpréteur : Python de Blender (numpy, PIL). Recalage : centre et axe du toit du château mesurés sur le
# MNS (toits > 38 m NGF) ; repère D-003 des composants : x vers l'est, y vers le sud, z = altitude − RDC.
import json, math, os, sys, urllib.request
import numpy as np
from PIL import Image, ImageDraw

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(RACINE, "travail/donnees-ouvertes")
# Centre approximatif du château (géocodage de l'adresse, puis recentrage sur le toit à l'orthophoto).
LAT, LON, DEMI = 43.268795, 5.377388, 200.0
N_LIDAR, N_ORTHO = 800, 3200
RDC = 26.85            # altitude NGF du RDC = terrasse sud (profil LiDAR)

def bbox():
    dla = DEMI / 111320; dlo = DEMI / (111320 * math.cos(math.radians(LAT)))
    return LAT - dla, LAT + dla, LON - dlo, LON + dlo

def telecharger():
    s, n, w, e = bbox()
    base = ("https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&CRS=EPSG:4326"
            f"&BBOX={s},{w},{n},{e}&STYLES=")
    os.makedirs(D, exist_ok=True)
    for nom, couche, fmt, taille in [("ortho_chateau.jpg", "HR.ORTHOIMAGERY.ORTHOPHOTOS", "image/jpeg", N_ORTHO),
                                     ("MNT_chateau.bil", "IGNF_LIDAR-HD_MNT_ELEVATION.ELEVATIONGRIDCOVERAGE.WGS84G", "image/x-bil;bits=32", N_LIDAR),
                                     ("MNS_chateau.bil", "IGNF_LIDAR-HD_MNS_ELEVATION.ELEVATIONGRIDCOVERAGE.WGS84G", "image/x-bil;bits=32", N_LIDAR)]:
        url = f"{base}&LAYERS={couche}&FORMAT={fmt}&WIDTH={taille}&HEIGHT={taille}"
        req = urllib.request.Request(url, headers={"User-Agent": "chateau-saint-victor-local/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r: open(os.path.join(D, nom), "wb").write(r.read())
        print(nom)
    json.dump({"sud": s, "nord": n, "ouest": w, "est": e, "source": "IGN Géoplateforme WMS-R, licence Etalab 2.0"},
              open(os.path.join(D, "bbox_chateau.json"), "w"), indent=1)

def lire():
    t = np.fromfile(os.path.join(D, "MNT_chateau.bil"), "<f4").reshape(N_LIDAR, N_LIDAR)
    s = np.fromfile(os.path.join(D, "MNS_chateau.bil"), "<f4").reshape(N_LIDAR, N_LIDAR)
    o = np.asarray(Image.open(os.path.join(D, "ortho_chateau.jpg")).convert("RGB")).astype(np.float32)
    return t, s, o

def composante(m, graine):
    vu = np.zeros_like(m, bool); pile = [graine]; vu[graine] = True
    while pile:
        y, x = pile.pop()
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and not vu[yy, xx]:
                vu[yy, xx] = True; pile.append((yy, xx))
    return vu

def recalage(t, s):
    toit = (s > 38) & (s - t > 9)
    c = composante(toit, (N_LIDAR // 2 + 4, N_LIDAR // 2))
    ys, xs = np.nonzero(c); cx, cy = xs.mean(), ys.mean()
    w, v = np.linalg.eigh(np.cov(np.stack([xs - cx, ys - cy])))
    a = math.degrees(math.atan2(v[1, 1], v[0, 1]))
    a = (a + 90) % 180 - 90                      # axe est-ouest, en degrés (image : y vers le bas)
    return cx, cy, a

class Repere:
    """Pixels LiDAR (0,5 m) ↔ repère D-003 (x est, y sud)."""
    def __init__(self, cx, cy, a):
        self.cx, self.cy, self.r = cx, cy, math.radians(a)
    def depuis_px(self, px, py, pas=0.5, k=1.0):
        u, v = (px / k - self.cx) * pas, (py / k - self.cy) * pas
        c, s = math.cos(-self.r), math.sin(-self.r)
        return u * c - v * s, u * s + v * c
    def vers_px(self, x, y, pas=0.5, k=1.0):
        c, s = math.cos(self.r), math.sin(self.r)
        u, v = x * c - y * s, x * s + y * c
        return (self.cx + u / pas) * k, (self.cy + v / pas) * k

def reechantillonner(img, R, xmin, xmax, ymin, ymax, res, k, pas_source):
    xs = np.arange(xmin, xmax, res); ys = np.arange(ymin, ymax, res)
    X, Y = np.meshgrid(xs, ys)
    c, s = math.cos(R.r), math.sin(R.r)
    U, V = X * c - Y * s, X * s + Y * c
    px = ((R.cx + U / 0.5) * k).astype(int); py = ((R.cy + V / 0.5) * k).astype(int)
    n = img.shape[0]; ok = (px >= 0) & (px < n) & (py >= 0) & (py < n)
    sortie = np.zeros(X.shape + img.shape[2:], img.dtype); sortie[ok] = img[py[ok], px[ok]]
    return sortie, ok

def contour(m):
    """Contour extérieur d'un masque (suivi de Moore), en indices (x, y)."""
    ys, xs = np.nonzero(m)
    if len(xs) == 0: return []
    i = np.argmin(ys * 100000 + xs); depart = (xs[i], ys[i])
    voisins = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    pts = [depart]; p = depart; d = 6
    for _ in range(200000):
        for k in range(8):
            dd = (d + 6 + k) % 8; q = (p[0] + voisins[dd][0], p[1] + voisins[dd][1])
            if 0 <= q[1] < m.shape[0] and 0 <= q[0] < m.shape[1] and m[q[1], q[0]]:
                p, d = q, dd; break
        if p == depart: break
        pts.append(p)
    return pts

def simplifier(pts, eps):
    if len(pts) < 3: return pts
    a, b = np.array(pts[0], float), np.array(pts[-1], float)
    ab = b - a; L = np.hypot(*ab) or 1e-9
    d = [abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / L for p in pts]
    i = int(np.argmax(d))
    if d[i] > eps: return simplifier(pts[:i + 1], eps)[:-1] + simplifier(pts[i:], eps)
    return [pts[0], pts[-1]]

def mesurer():
    t, s, o = lire()
    cx, cy, a = recalage(t, s); R = Repere(cx, cy, a)
    h = s - t
    res = 0.5; X0, X1, Y0, Y1 = -70.0, 145.0, -55.0, 150.0
    T, ok = reechantillonner(t, R, X0, X1, Y0, Y1, res, 1, 0.5)
    S, _ = reechantillonner(s, R, X0, X1, Y0, Y1, res, 1, 0.5)
    O, _ = reechantillonner(o, R, X0, X1, Y0, Y1, res, N_ORTHO / N_LIDAR, 0.5)
    Hh = S - T
    def px(x, y): return int((x - X0) / res), int((y - Y0) / res)
    def xy(i, j): return X0 + i * res, Y0 + j * res
    r, g, b = O[..., 0], O[..., 1], O[..., 2]
    lum = (r + g + b) / 3; sat = O.max(-1) - O.min(-1)
    vert = (g > r + 6) & (g > b + 4)
    clair = (lum > 150) & (sat < 45)                    # sable, béton clair, bassin vide
    brique = (r > g + 25) & (r > b + 35) & (Hh < 1.5)  # terre battue du tennis

    plan = {"source": "IGN orthophoto HR + LiDAR HD MNT/MNS 50 cm (Etalab 2.0)", "rdc_ngf": RDC,
            "recalage": {"centre_px_lidar": [round(cx, 2), round(cy, 2)], "rotation_deg": round(a, 2)}}
    # Profil nord-sud dans l'axe : terrasse, perron, cour.
    prof = []
    for y in np.arange(-30, 60, 0.5):
        i, j = px(0.0, y); prof.append((float(y), round(float(T[j, i]) - RDC, 2), round(float(S[j, i]) - RDC, 2)))
    plan["profil_axe"] = prof
    # Arbres : maxima locaux de la hauteur de canopée (> 3 m), au moins 3 m d'écart, hors bâtiments.
    rugueux = np.zeros_like(Hh, bool)
    pad = np.pad(Hh, 1, mode="edge")
    loc = np.stack([pad[dy:dy + Hh.shape[0], dx:dx + Hh.shape[1]] for dy in range(3) for dx in range(3)])
    rugueux = loc.std(0) > 0.35
    from numpy.lib.stride_tricks import sliding_window_view
    w = 7; padm = np.pad(Hh, w // 2, mode="constant", constant_values=-99)
    maxi = sliding_window_view(padm, (w, w)).max(axis=(-1, -2))
    pics = (Hh >= maxi) & (Hh > 3.0) & ok & (vert | (lum < 110)) & rugueux
    # Hors toits (tuiles ou toits clairs autour du pic, 5 × 5) et hors de l'emprise du château.
    tuile = ((r > g + 20) & (r > b + 25)) | ((sat < 18) & (lum > 120))      # tuiles, toits plats et béton
    toits = sliding_window_view(np.pad(tuile.astype(np.float32), 2, mode="edge"), (5, 5)).mean(axis=(-1, -2))
    candidats = sorted(zip(*np.nonzero(pics)), key=lambda p: -Hh[p])
    arbres = []
    for j, i in candidats:
        hh = float(Hh[j, i]); x, y = xy(i, j)
        if toits[j, i] > 0.35 or (abs(x) < 20 and -12 < y < 11): continue
        if any(math.hypot(x - q["x"], y - q["y"]) < max(3.0, 0.5 * q["r"]) for q in arbres): continue
        rayons = []
        for ang in range(0, 360, 45):
            dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            for k in range(1, 30):
                ii, jj = int(i + dx * k), int(j + dy * k)
                if not (0 <= ii < Hh.shape[1] and 0 <= jj < Hh.shape[0]) or Hh[jj, ii] < hh * 0.45: break
            rayons.append(k * res)
        rayon = min(float(np.median(rayons)), 0.45 * hh + 1.0, 8.0)
        arbres.append({"x": round(x, 1), "y": round(y, 1), "h": round(hh, 1), "r": round(rayon, 1),
                       "z_sol": round(float(T[j, i]) - RDC, 2)})
    plan["arbres"] = arbres
    # Bassin en haricot : grande tache claire au sud de la cour.
    def tache(masque, graine_xy, eps):
        i, j = px(*graine_xy)
        if not masque[j, i]: return None
        c = composante(masque, (j, i))
        pts = simplifier(contour(c), eps / res)
        return [[round(xy(p[0], p[1])[0], 2), round(xy(p[0], p[1])[1], 2)] for p in pts[:-1]], int(c.sum())
    plan["bassin"] = tache(clair & (Hh < 1.0), (14.0, 77.0), 0.4)
    plan["cour_sud"] = tache(clair & (Hh < 1.0), (0.0, 25.0), 0.8)
    plan["tennis"] = tache(brique, (-25.0, -5.0), 0.6)
    # Altitude du terrain (MNT) tous les 5 m, pour le relief du parc.
    grille = []
    for y in np.arange(Y0, Y1 + 0.1, 5.0):
        ligne = []
        for x in np.arange(X0, X1 + 0.1, 5.0):
            i, j = px(min(x, X1 - res), min(y, Y1 - res)); ligne.append(round(float(T[j, i]) - RDC, 2) if ok[j, i] else None)
        grille.append(ligne)
    plan["mnt"] = {"x0": X0, "y0": Y0, "pas": 5.0, "z": grille}
    # MNT fin (2 m), lissé (moyenne 5 × 5 px = 2,5 m) : relief du parc, des allées et des abords.
    Tl = sliding_window_view(np.pad(np.where(ok, T, np.nan), 2, mode="edge"), (5, 5))
    Tl = np.nanmean(Tl, axis=(-1, -2))
    fin = []
    for y in np.arange(Y0, Y1 + 0.1, 2.0):
        ligne = []
        for x in np.arange(X0, X1 + 0.1, 2.0):
            i, j = px(min(x, X1 - res), min(y, Y1 - res))
            v = Tl[j, i]
            ligne.append(round(float(v) - RDC, 2) if ok[j, i] and np.isfinite(v) else None)
        fin.append(ligne)
    plan["mnt_fin"] = {"x0": X0, "y0": Y0, "pas": 2.0, "z": fin}
    json.dump(plan, open(os.path.join(RACINE, "travail/plan_mesure.json"), "w"), indent=1, ensure_ascii=False)

    # Planche de contrôle : orthophoto redressée, grille 10 m, arbres et contours mesurés.
    im = Image.fromarray(O.astype(np.uint8)).resize((int((X1 - X0) * 4), int((Y1 - Y0) * 4)))
    d = ImageDraw.Draw(im); k = 4
    P = lambda x, y: ((x - X0) * k, (y - Y0) * k)
    for gx in range(int(X0), int(X1) + 1, 10): d.line([P(gx, Y0), P(gx, Y1)], fill=(255, 255, 0) if gx == 0 else (220, 220, 220)); d.text(P(gx + .5, Y0 + .5), str(gx), fill=(255, 255, 0))
    for gy in range(int(Y0), int(Y1) + 1, 10): d.line([P(X0, gy), P(X1, gy)], fill=(255, 255, 0) if gy == 0 else (220, 220, 220)); d.text(P(X0 + .5, gy + .5), str(gy), fill=(255, 255, 0))
    for ar in arbres:
        x, y, rr = ar["x"], ar["y"], ar["r"]; d.ellipse([P(x - rr, y - rr), P(x + rr, y + rr)], outline=(255, 60, 60), width=2)
    for cle, coul in (("bassin", (0, 200, 255)), ("cour_sud", (255, 160, 0)), ("tennis", (255, 0, 255))):
        if plan[cle]: d.line([P(*p) for p in plan[cle][0] + plan[cle][0][:1]], fill=coul, width=3)
    im.save(os.path.join(D, "plan_mesure.png"))
    print(f"recalage {cx:.1f},{cy:.1f} {a:.2f}° ; {len(arbres)} arbres ; bassin {'ok' if plan['bassin'] else '—'} ; "
          f"cour {'ok' if plan['cour_sud'] else '—'} ; tennis {'ok' if plan['tennis'] else '—'}")

if __name__ == "__main__":
    {"telecharger": telecharger, "mesurer": mesurer}[sys.argv[1] if len(sys.argv) > 1 else "mesurer"]()

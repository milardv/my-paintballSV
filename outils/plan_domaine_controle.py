# Planche de contrôle du plan du domaine : travail/plan_domaine.json dessiné sur l'orthophoto IGN redressée
# (repère D-003, x est, y sud). Interpréteur : Python de Blender (numpy, PIL).
#   python3.13 outils/plan_domaine_controle.py   → travail/donnees-ouvertes/plan_domaine.jpg
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import donnees_ouvertes as d

P = json.load(open(os.path.join(d.RACINE, "travail/plan_domaine.json")))
t, s, o = d.lire()
R = d.Repere(*d.recalage(t, s))
X0, X1, Y0, Y1, res = -50.0, 135.0, -45.0, 150.0, 0.2
O, _ = d.reechantillonner(o, R, X0, X1, Y0, Y1, res, d.N_ORTHO / d.N_LIDAR, 0.5)
im = Image.fromarray(O.astype(np.uint8))
dr = ImageDraw.Draw(im)
Q = lambda x, y: ((x - X0) / res, (y - Y0) / res)
for gx in range(-50, 136, 10):
    dr.line([Q(gx, Y0), Q(gx, Y1)], fill=(120, 120, 120)); dr.text(Q(gx + .4, Y0 + .4), str(gx), fill=(255, 255, 0))
for gy in range(-40, 151, 10):
    dr.line([Q(X0, gy), Q(X1, gy)], fill=(120, 120, 120)); dr.text(Q(X0 + .4, gy + .4), str(gy), fill=(255, 255, 0))

def poly(pts, c, w=3, ferme=True):
    pts = [Q(*p) for p in pts]
    dr.line(pts + (pts[:1] if ferme else []), fill=c, width=w)

def rect(c, dim, ang, coul):
    a = math.radians(ang); u = (math.cos(a), math.sin(a)); v = (-u[1], u[0])
    pts = [(c[0] + u[0] * sx * dim[0] / 2 + v[0] * sy * dim[1] / 2, c[1] + u[1] * sx * dim[0] / 2 + v[1] * sy * dim[1] / 2)
           for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    poly(pts, coul)

poly(P["limite"], (255, 140, 0), 4)
poly(P["plateforme_ouest"]["polygone"], (255, 255, 255), 2)
e = P["tennis"]["enceinte"]; poly([(e[0], e[1]), (e[2], e[1]), (e[2], e[3]), (e[0], e[3])], (255, 0, 255))
poly(P["piscine"]["contour"], (0, 220, 255))
for a in P["allees"].values():
    poly(a["points"], (255, 60, 60), max(2, int(a["largeur"] / res / 4)), ferme=False)
for k, coul in (("local_piscine", (0, 255, 120)), ("gardien", (0, 255, 120)), ("grange", (0, 255, 120)), ("petanque", (255, 230, 120))):
    rect(P[k]["centre"], P[k]["dimensions"], P[k]["angle_deg"], coul)
for es in P["escaliers_tennis"]:
    poly([es["haut"], es["bas"]], (255, 255, 0), 8, ferme=False)
for k in ("portail", "portail_nord"):
    x, y = P[k]["centre"]; dr.ellipse([Q(x - 1.5, y - 1.5), Q(x + 1.5, y + 1.5)], outline=(0, 0, 0), width=4)
for x, y in P["paves_verre"]["points"]:
    dr.rectangle([Q(x - .4, y - .3), Q(x + .4, y + .3)], outline=(0, 255, 255), width=2)
sortie = os.path.join(d.D, "plan_domaine.jpg")
im.save(sortie, quality=88)
print(sortie)

"""Composant P2.terrasse : terrasse sud balustrée et retour est, perron sud évasé, massifs en bacs,
escalier est, perron nord (palier, 2 lampadaires), dallage, urnes, pots et mobilier de terrasse.

blender -b --factory-startup --python scripts/composants/terrasse.py
→ export/composants/terrasse.glb, export/composants/terrasse.blend, rendus/terrasse*.png

Repère D-003 : mètres, +X est, +Y sud (jardin), Z haut, RDC = 0. Cotes : travail/gabarit.json.
"""
import json
import math
import os
import random
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector, noise

T0 = time.time()
try:
    RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    RACINE = os.path.expanduser("~/IdeaProjects/chateau-saint-victor")
ID = "terrasse"
EXPORT = os.path.join(RACINE, "export", "composants")
TEXDIR = os.path.join(EXPORT, ID + "_textures")
RENDUS = os.path.join(RACINE, "rendus")
ASSETS = os.path.join(RACINE, "assets")
import shutil
shutil.rmtree(TEXDIR, ignore_errors=True)
for d in (EXPORT, TEXDIR, RENDUS):
    os.makedirs(d, exist_ok=True)

G = json.load(open(os.path.join(RACINE, "travail", "gabarit.json")))
random.seed(7)

T = G["terrasse"]["niveau_z"]                      # dessus du dallage (-0.05)
Z_SUD = G["niveaux"]["cour_sablee_sud"]["valeur"]   # -1.28
Z_NORD = G["niveaux"]["cour_nord_parking"]["valeur"]  # -1.44
# Bord sud de la terrasse (côtés) et du palier central, bas du perron sud (gabarit, mesures LiDAR HD).
Y_TER = G["terrasse"]["polygone"][0][1]             # 12.0
Y_PAL = G["perron_sud"]["polygone"][0][1]           # 14.7
Y_BAS = G["perron_sud"]["polygone"][2][1]           # ~18.05
Z_EST = -1.40                                       # pied du retour est (entre cour sud et parking)
Z_FOND = -1.65                                      # fond des maçonneries (enterré)
X_E = G["terrasse"]["polygone"][5][0]               # retour est (22,0)
Y_O = G["terrasse"]["polygone"][-1][1]              # raccord ouest à la plateforme du tennis (7,6)


def log(*a):
    print("[terrasse %5.1fs]" % (time.time() - T0), *a)
    sys.stdout.flush()


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
# Textures dérivées (numpy) à partir des sources CC0 de assets/
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
    SC.render.image_settings.quality = 92
    im.save()
    bpy.data.images.remove(im)
    return chemin


def lum(a):
    return a[:, :, 0] * 0.3 + a[:, :, 1] * 0.59 + a[:, :, 2] * 0.11


def normale_depuis_hauteur(h, force):
    gy, gx = np.gradient(h)
    n = np.dstack([-gx * force, -gy * force, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n


def combiner_normales(n1, n2):
    n = n1.copy()
    n[:, :, 0] += n2[:, :, 0]
    n[:, :, 1] += n2[:, :, 1]
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def lisser(a, r):
    out = a.copy()
    for ax in (0, 1):
        acc = np.zeros_like(out)
        for k in range(-r, r + 1):
            acc += np.roll(out, k, axis=ax)
        out = acc / (2 * r + 1)
    return out


def textures():
    """Pierre de taille (appareil réglé), pierre lisse, dallage, teck, résine tressée."""
    tex = {}
    bw = os.path.join(ASSETS, "polyhaven", "polyhaven-beige_wall_001")
    diff = charger_px(os.path.join(bw, "beige_wall_001_diff_2k.jpg"))
    nor = charger_px(os.path.join(bw, "beige_wall_001_nor_gl_2k.jpg")) * 2 - 1
    L = lum(diff)
    Ln = (L - L.mean()) / (L.std() + 1e-6)
    N = diff.shape[0]
    calc = np.array([0.86, 0.80, 0.68], dtype=np.float32)  # calcaire crème (sRGB), W01/W13/P38

    # -- appareil réglé : 2 m × 2 m, assises de 0,50 m, blocs de 1,00 m décalés d'un demi
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    px_m = N / 2.0
    assise = np.floor(yy / (0.5 * px_m)).astype(int)
    decal = (assise % 2) * 0.5 * px_m
    bloc = np.floor(((xx + decal) % N) / (1.0 * px_m)).astype(int)
    idb = (assise * 7 + bloc * 3) % 23
    rng = np.random.RandomState(3)
    teinte = rng.uniform(0.93, 1.05, 23).astype(np.float32)[idb]
    chaud = rng.uniform(-0.02, 0.02, 23).astype(np.float32)[idb]
    dy = np.minimum(yy % (0.5 * px_m), 0.5 * px_m - yy % (0.5 * px_m))
    dx = np.minimum((xx + decal) % px_m, px_m - (xx + decal) % px_m)
    dj = np.minimum(dx, dy)
    joint = np.clip(1 - (dj - 3) / 3, 0, 1)            # joint de 6 mm
    arete = np.clip(1 - (dj - 3) / 14, 0, 1) * (1 - joint)  # arêtes émoussées
    col = calc[None, None, :] * (1 + 0.07 * Ln[:, :, None]) * teinte[:, :, None]
    col[:, :, 0] += chaud
    col[:, :, 2] -= chaud
    col = col * (1 - 0.10 * arete[:, :, None])
    col = col * (1 - joint[:, :, None]) + (calc * 0.80)[None, None, :] * joint[:, :, None]
    h = 1 - joint - 0.35 * arete ** 2
    nj = normale_depuis_hauteur(lisser(h, 2), 2.5)
    nrm = combiner_normales(nor, nj)
    rough = np.clip(0.78 + 0.06 * Ln + 0.12 * joint, 0, 1)
    tex["appareil"] = (sauver_px("pierre_appareil_col", col), sauver_px("pierre_appareil_nrm", nrm),
                       sauver_px("pierre_appareil_rgh", rough))

    # -- pierre lisse (moulures, balustres, marches) : même grain, sans joints, 1024 px
    s = slice(None, None, 2)
    col2 = calc[None, None, :] * 1.03 * (1 + 0.05 * Ln[s, s, None])
    tex["lisse"] = (sauver_px("pierre_lisse_col", col2),
                    sauver_px("pierre_lisse_nrm", nor[s, s] * 0.5 + 0.5),
                    sauver_px("pierre_lisse_rgh", np.clip(0.72 + 0.05 * Ln[s, s], 0, 1)))

    # -- marches : pierre plus blanche et plus grise (P38, P40, W15)
    col3 = np.array([0.84, 0.82, 0.77], dtype=np.float32)[None, None, :] * (1 + 0.06 * Ln[s, s, None])
    tex["marche"] = (sauver_px("pierre_marche_col", col3), tex["lisse"][1], tex["lisse"][2])

    # -- dallage : Tiles142 (ambientCG) désaturé vers le calcaire clair de la terrasse (W15)
    td = os.path.join(ASSETS, "ambientcg", "ambientcg-Tiles142", "Tiles142_2K-JPG")
    dc = charger_px(os.path.join(td, "Tiles142_2K-JPG_Color.jpg"))
    Ld = lum(dc)
    r = (Ld / Ld.mean())[:, :, None]
    cible = np.array([0.85, 0.81, 0.73], dtype=np.float32)[None, None, :]
    dcol = cible * r ** 0.8 * 0.8 + dc * (cible / dc.reshape(-1, 3).mean(0)) * 0.2
    tex["dallage"] = (sauver_px("dallage_col", dcol),
                      os.path.join(td, "Tiles142_2K-JPG_NormalGL.jpg"),
                      os.path.join(td, "Tiles142_2K-JPG_Roughness.jpg"))

    # -- teck : kitchen_wood (Poly Haven) teinté
    kw = os.path.join(ASSETS, "polyhaven", "polyhaven-kitchen_wood")
    wc = charger_px(os.path.join(kw, "kitchen_wood_diff_1k.jpg"))
    Lw = lum(wc)
    teck = np.array([0.58, 0.40, 0.26], dtype=np.float32)[None, None, :] * (Lw / Lw.mean())[:, :, None] ** 1.3
    tex["teck"] = (sauver_px("teck_col", teck), os.path.join(kw, "kitchen_wood_nor_gl_1k.jpg"),
                   os.path.join(kw, "kitchen_wood_rough_1k.jpg"))

    # -- résine tressée (salon d'extérieur) : tressage procédural 512 px pour 0,12 m
    n = 512
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n * 2 * math.pi * 8
    a = np.sin(xx) * np.sign(np.sin(yy / 2 + 1e-3))
    b = np.sin(yy) * -np.sign(np.sin(xx / 2 + 1e-3))
    hh = np.maximum(a, b)
    wcol = np.array([0.16, 0.16, 0.16], dtype=np.float32)[None, None, :] * (0.75 + 0.35 * (hh[:, :, None] * 0.5 + 0.5))
    tex["tresse"] = (sauver_px("tresse_col", wcol),
                     sauver_px("tresse_nrm", normale_depuis_hauteur(hh, 4.0) * 0.5 + 0.5), None)
    tex["tresse_ecru"] = (sauver_px("tresse_ecru_col", wcol / 0.16 * np.array([0.62, 0.58, 0.52])[None, None, :]),
                          tex["tresse"][1], None)
    return tex


log("textures…")
TEX = textures()


# ----------------------------------------------------------------------------------------------
# Matériaux PBR (exportables en glTF : images directes sur la Principled BSDF)
# ----------------------------------------------------------------------------------------------
MATS = {}
UVS = {}


def materiau(nom, couleur=(0.8, 0.8, 0.8), rugosite=0.5, metal=0.0, tex=None, uv=1.0, emission=None,
             deux_faces=False, nrm_force=1.0):
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


M_APP = materiau("pierre_appareil", tex=TEX["appareil"], uv=2.0)
M_LIS = materiau("pierre_lisse", tex=TEX["lisse"], uv=1.0)
M_MAR = materiau("pierre_marche", tex=TEX["marche"], uv=1.0)
M_DAL = materiau("dallage", tex=TEX["dallage"], uv=3.0)
M_TECK = materiau("teck", tex=TEX["teck"], uv=0.8, rugosite=0.6)
M_TRES = materiau("resine_tressee", tex=TEX["tresse"], uv=0.12, rugosite=0.55)
M_TRES_E = materiau("resine_tressee_ecru", tex=TEX["tresse_ecru"], uv=0.12, rugosite=0.6)
M_FER = materiau("fer_noir", (0.018, 0.018, 0.017), 0.42, 0.55)
M_TOILE = materiau("toile_ecru", (0.86, 0.83, 0.75), 0.9, deux_faces=True)
M_COUSS = materiau("coussin_ecru", (0.80, 0.76, 0.68), 0.95)
M_BLANC = materiau("laque_blanche", (0.88, 0.88, 0.86), 0.35)
M_TC = materiau("terre_cuite", (0.58, 0.30, 0.17), 0.85)
M_TERRE = materiau("terreau", (0.10, 0.07, 0.05), 1.0)
M_FEUIL = materiau("feuillage_laurier", (0.05, 0.13, 0.04), 0.7, deux_faces=True)
M_BUIS = materiau("feuillage_buis", (0.06, 0.15, 0.04), 0.75)
M_FOUG = materiau("feuillage_fougere", (0.12, 0.30, 0.06), 0.6, deux_faces=True)
M_FLEUR = materiau("fleurs_laurier_rose", (0.75, 0.16, 0.30), 0.6)
M_GERA = materiau("fleurs_geranium", (0.70, 0.04, 0.04), 0.6)
M_OPALE = materiau("verre_opalin", (0.92, 0.92, 0.90), 0.25, emission=((1.0, 0.95, 0.85), 0.4))
M_VERRE = materiau("verre_lanterne", (0.05, 0.05, 0.05), 0.05, metal=0.0)
M_PAVE = materiau("pave_verre_vert", (0.10, 0.28, 0.22), 0.15)
M_NOIR = materiau("ombre_soupirail", (0.01, 0.01, 0.01), 1.0)
M_POTVERT = materiau("pot_vernisse_vert", (0.10, 0.22, 0.14), 0.3)


# ----------------------------------------------------------------------------------------------
# Constructeur de maillages
# ----------------------------------------------------------------------------------------------
class Bld:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []
        self.sharp = []

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def v(self, co):
        return self.bm.verts.new(co)

    def face(self, vs, m, lisse=False):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.mi(m)
        f.smooth = lisse
        return f

    def boite(self, x0, y0, z0, x1, y1, z1, m):
        self.solide([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, m)

    def boite_c(self, cx, cy, z0, sx, sy, z1, m):
        self.boite(cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z1, m)

    def solide(self, poly, z0, z1, m, mhaut=None, mbas=None):
        poly = ccw(poly)
        b = [self.v((x, y, z0)) for x, y in poly]
        h = [self.v((x, y, z1)) for x, y in poly]
        self.coque(b, h, m, mhaut or m, mbas or m)

    def coque(self, b, h, m, mhaut=None, mbas=None):
        """b, h : boucles de sommets (ccw vues du dessus) ; faces latérales + fonds."""
        n = len(b)
        for i in range(n):
            j = (i + 1) % n
            self.face([b[i], b[j], h[j], h[i]], m)
        self.face(list(reversed(b)), mbas or m)
        self.face(h, mhaut or m)

    def boucle(self, pts, m, lisse=False, fermer_bouts=True, ferme=False):
        """pts : liste d'anneaux (listes de Vector de même longueur), extrusion fermée en travers."""
        anneaux = [[self.v(p) for p in a] for a in pts]
        k = len(anneaux[0])
        nseg = len(anneaux) if ferme else len(anneaux) - 1
        for i in range(nseg):
            a, b = anneaux[i], anneaux[(i + 1) % len(anneaux)]
            for j in range(k):
                jj = (j + 1) % k
                self.face([a[j], a[jj], b[jj], b[j]], m, lisse)
        if fermer_bouts and not ferme:
            self.face(list(reversed(anneaux[0])), m)
            self.face(anneaux[-1], m)
        return anneaux

    def tour(self, prof, m, c=(0, 0, 0), seg=16, ferme=False, angle_vif=35, sc=1.0):
        """Révolution d'un profil [(r, z)] autour de Z."""
        cx, cy, cz = c
        anneaux = []
        for r, z in prof:
            if r <= 1e-6 and not ferme:
                anneaux.append([self.v((cx, cy, cz + z * sc))])
            else:
                anneaux.append([self.v((cx + r * sc * math.cos(2 * math.pi * j / seg),
                                        cy + r * sc * math.sin(2 * math.pi * j / seg), cz + z * sc))
                                for j in range(seg)])
        n = len(anneaux)
        rng_ = range(n) if ferme else range(n - 1)
        for i in rng_:
            a, b = anneaux[i], anneaux[(i + 1) % n]
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
        # arêtes vives aux cassures du profil
        for i in range(n):
            if not ferme and (i == 0 or i == n - 1):
                continue
            p0, p1, p2 = Vector(prof[i - 1]), Vector(prof[i]), Vector(prof[(i + 1) % n])
            d1, d2 = p1 - p0, p2 - p1
            if d1.length < 1e-9 or d2.length < 1e-9:
                continue
            if math.degrees(d1.angle(d2)) > angle_vif and len(anneaux[i]) > 1:
                a = anneaux[i]
                self.sharp.append([(a[j], a[(j + 1) % seg]) for j in range(seg)])
        return anneaux

    def sphere(self, c, r, m, seg=16, rings=10, sc=(1, 1, 1)):
        ret = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=rings, radius=r)
        mat = Matrix.Translation(c) @ Matrix.Diagonal((*sc, 1))
        bmesh.ops.transform(self.bm, matrix=mat, verts=ret["verts"])
        fs = {f for v in ret["verts"] for f in v.link_faces}
        for f in fs:
            f.material_index = self.mi(m)
            f.smooth = True
        return ret["verts"]

    def cylindre(self, p0, p1, r, m, seg=10, lisse=True):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0)
        q = d.to_track_quat("Z", "Y")
        ann = []
        for p in (p0, p1):
            ann.append([p + q @ Vector((r * math.cos(2 * math.pi * j / seg), r * math.sin(2 * math.pi * j / seg), 0))
                        for j in range(seg)])
        vs = [[self.v(p) for p in a] for a in ann]
        for j in range(seg):
            jj = (j + 1) % seg
            self.face([vs[0][j], vs[0][jj], vs[1][jj], vs[1][j]], m, lisse)
        self.face(list(reversed(vs[0])), m)
        self.face(vs[1], m)

    def objet(self, nom, col=COL, loc=(0, 0, 0), rot=0.0, recalc=True, uvmonde=True):
        bm = self.bm
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        for groupe in self.sharp:
            for a, b in groupe:
                if not (a.is_valid and b.is_valid):
                    continue
                e = bm.edges.get((a, b))
                if e:
                    e.smooth = False
        # UV : projection boîte, échelle par matériau
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
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
        me = bpy.data.meshes.new(nom)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(nom, me)
        ob.location = loc
        ob.rotation_euler.z = rot
        col.objects.link(ob)
        return ob


def ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
            for i in range(len(poly)))
    return list(poly) if a > 0 else list(reversed(poly))


def instance(src, nom, loc, rot=0.0, col=COL, sc=1.0):
    ob = bpy.data.objects.new(nom, src.data)
    ob.location = loc
    ob.rotation_euler.z = rot
    ob.scale = (sc, sc, sc)
    col.objects.link(ob)
    return ob


def biseau(ob, largeur=0.01, seg=2):
    md = ob.modifiers.new("biseau", "BEVEL")
    md.width = largeur
    md.segments = seg
    md.limit_method = "ANGLE"
    md.harden_normals = False
    return ob


def decaler_polyligne(pts, d):
    """Décalage à gauche (normale (-dy, dx)) d'une polyligne ouverte, coins en onglet."""
    out = []
    n = len(pts)
    nrm = []
    for i in range(n - 1):
        dx, dy = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        L = math.hypot(dx, dy)
        nrm.append((-dy / L, dx / L))
    for i in range(n):
        if i == 0:
            nx, ny = nrm[0]
            out.append((pts[i][0] + nx * d, pts[i][1] + ny * d))
        elif i == n - 1:
            nx, ny = nrm[-1]
            out.append((pts[i][0] + nx * d, pts[i][1] + ny * d))
        else:
            ax, ay = nrm[i - 1]
            bx, by = nrm[i]
            mx, my = ax + bx, ay + by
            ml = math.hypot(mx, my)
            mx, my = mx / ml, my / ml
            k = d / (mx * ax + my * ay)
            out.append((pts[i][0] + mx * k, pts[i][1] + my * k))
    return out


def balayage(b, polyl, profil, zref, m):
    """Profil [(u vers l'extérieur, dz)] fermé, balayé le long d'une polyligne (normale gauche = extérieur)."""
    lignes = [decaler_polyligne(polyl, u) for u, _ in profil]
    anneaux = []
    for i in range(len(polyl)):
        anneaux.append([Vector((lignes[k][i][0], lignes[k][i][1], zref + profil[k][1])) for k in range(len(profil))])
    b.boucle(anneaux, m)


# ----------------------------------------------------------------------------------------------
# Éléments tournés réutilisés (maillages partagés → instances)
# ----------------------------------------------------------------------------------------------
H_SOCLE, H_BAL, H_TAB = 0.17, 0.60, 0.14
LIB = bpy.data.collections.new("bibliotheque")  # maillages sources, non liés à la scène


def balustre():
    b = Bld()
    b.boite_c(0, 0, 0, 0.14, 0.14, 0.045, M_LIS)
    prof = [(0.0, 0.045), (0.068, 0.045), (0.068, 0.06), (0.058, 0.07), (0.056, 0.085), (0.068, 0.10),
            (0.085, 0.14), (0.096, 0.19), (0.096, 0.23), (0.088, 0.27), (0.072, 0.31), (0.052, 0.35),
            (0.040, 0.39), (0.037, 0.415), (0.048, 0.43), (0.048, 0.445), (0.038, 0.455), (0.040, 0.475),
            (0.052, 0.50), (0.064, 0.52), (0.066, 0.545), (0.066, 0.555), (0.0, 0.555)]
    b.tour(prof, M_LIS, seg=14, angle_vif=50)
    b.boite_c(0, 0, 0.555, 0.14, 0.14, H_BAL, M_LIS)
    return b.objet("terrasse_src_balustre", col=LIB)


def urne():
    """Vase Médicis sur piédouche, h ≈ 0,8 m (W01 : vasques blanches en tête d'échiffre)."""
    b = Bld()
    b.boite_c(0, 0, 0, 0.36, 0.36, 0.08, M_LIS)
    prof = [(0, 0.08), (0.12, 0.08), (0.12, 0.10), (0.07, 0.13), (0.06, 0.20), (0.09, 0.23), (0.10, 0.25),
            (0.14, 0.27), (0.22, 0.33), (0.25, 0.40), (0.25, 0.43), (0.22, 0.45), (0.24, 0.62), (0.29, 0.72),
            (0.31, 0.74), (0.31, 0.78), (0.27, 0.78), (0.25, 0.74), (0.0, 0.70)]
    b.tour(prof, M_LIS, seg=24, angle_vif=40)
    b.sphere(Vector((0, 0, 0.73)), 0.24, M_BUIS, seg=12, rings=8, sc=(1, 1, 0.55))
    return b.objet("terrasse_src_urne", col=LIB)


def pot_terre_cuite(r=0.28, h=0.48, m=M_TC, nom="pot"):
    b = Bld()
    prof = [(0, 0), (r * 0.62, 0), (r * 0.66, 0.03), (r * 0.9, h * 0.82), (r * 0.92, h * 0.86),
            (r * 1.02, h * 0.88), (r * 1.02, h), (r * 0.92, h), (r * 0.9, h * 0.94), (0, h * 0.94)]
    b.tour(prof, m, seg=20, angle_vif=40)
    return b


def lampadaire():
    """Lampadaire boule sur colonne en fonte (P38/P40) : h ≈ 3,0 m, globe Ø 0,40 m."""
    b = Bld()
    b.boite_c(0, 0, 0, 0.36, 0.36, 0.10, M_FER)
    prof = [(0, 0.10), (0.15, 0.10), (0.15, 0.16), (0.12, 0.20), (0.13, 0.26), (0.10, 0.34), (0.07, 0.42),
            (0.065, 0.55), (0.08, 0.60), (0.08, 0.64), (0.055, 0.70), (0.050, 1.60), (0.045, 2.20),
            (0.06, 2.24), (0.06, 2.28), (0.042, 2.32), (0.040, 2.62), (0.07, 2.66), (0.09, 2.70),
            (0.07, 2.73), (0.0, 2.73)]
    b.tour(prof, M_FER, seg=14, angle_vif=40)
    # bagues décoratives en relief
    for z in (0.95, 1.30):
        b.tour([(0.050, z), (0.066, z + 0.02), (0.066, z + 0.05), (0.050, z + 0.07)], M_FER, seg=14, ferme=False)
    b.sphere(Vector((0, 0, 2.93)), 0.20, M_OPALE, seg=20, rings=12)
    return b.objet("terrasse_src_lampadaire", col=LIB)


def chaise_teck():
    b = Bld()
    for sx in (-0.21, 0.21):
        for sy in (-0.21, 0.21):
            b.boite_c(sx, sy, 0, 0.04, 0.04, 0.44, M_TECK)
    for i in range(5):
        b.boite_c(-0.2 + i * 0.1, 0, 0.44, 0.08, 0.46, 0.465, M_TECK)
    for sx in (-0.21, 0.21):
        b.boite_c(sx, 0.21, 0.44, 0.04, 0.04, 0.90, M_TECK)
    for z in (0.62, 0.72, 0.82):
        b.boite_c(0, 0.22, z, 0.42, 0.025, z + 0.07, M_TECK)
    for sx in (-0.21, 0.21):
        b.boite_c(sx, 0, 0.64, 0.05, 0.46, 0.67, M_TECK)
        b.boite_c(sx, -0.21, 0.44, 0.035, 0.035, 0.64, M_TECK)
    return b.objet("terrasse_src_chaise_teck", col=LIB)


def table_teck(lx=1.6, ly=0.9, trou=True):
    b = Bld()
    n = int(lx / 0.09)
    for i in range(n):
        x = -lx / 2 + (i + 0.5) * lx / n
        b.boite_c(x, 0, 0.72, lx / n - 0.008, ly, 0.75, M_TECK)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.boite_c(sx * (lx / 2 - 0.06), sy * (ly / 2 - 0.06), 0, 0.06, 0.06, 0.72, M_TECK)
    b.boite_c(0, -ly / 2 + 0.03, 0.64, lx - 0.1, 0.03, 0.72, M_TECK)
    b.boite_c(0, ly / 2 - 0.03, 0.64, lx - 0.1, 0.03, 0.72, M_TECK)
    return b


def parasol(x, y, z, nom, rot=0.0, cote=3.0, h=2.65):
    """Parasol carré écru à mât central bois (W05, W13, W15)."""
    b = Bld()
    c = cote / 2
    hb = h - 0.42
    pts = [(-c, -c), (c, -c), (c, c), (-c, c)]
    sommet = b.v((0, 0, h))
    vb = [b.v((px, py, hb)) for px, py in pts]
    # toile légèrement bombée : 4 pans subdivisés
    for i in range(4):
        j = (i + 1) % 4
        a, bb = Vector((*pts[i], hb)), Vector((*pts[j], hb))
        mid = (a + bb) / 2
        mid.z += 0.0
        vm = b.v(mid)
        cen = (a + bb + Vector((0, 0, h))) / 3
        cen.z += 0.06
        vc = b.v(cen)
        b.face([vb[i], vm, vc], M_TOILE)
        b.face([vm, vb[j], vc], M_TOILE)
        b.face([vb[j], sommet, vc], M_TOILE)
        b.face([sommet, vb[i], vc], M_TOILE)
        # lambrequin
        d = (bb - a).normalized()
        nrm = Vector((d.y, -d.x, 0))
        l0 = [b.v(a + nrm * 0.005), b.v(bb + nrm * 0.005)]
        l1 = [b.v(a + nrm * 0.005 + Vector((0, 0, -0.20))), b.v(bb + nrm * 0.005 + Vector((0, 0, -0.20)))]
        b.face([l0[0], l0[1], l1[1], l1[0]], M_TOILE)
        # baleine
        b.cylindre((0, 0, h - 0.05), (pts[i][0] * 0.98, pts[i][1] * 0.98, hb - 0.02), 0.012, M_TECK, seg=6)
        b.cylindre((0, 0, 1.55), (pts[i][0] * 0.45, pts[i][1] * 0.45, hb - 0.12), 0.010, M_TECK, seg=6)
    b.cylindre((0, 0, 0.08), (0, 0, h + 0.08), 0.028, M_TECK, seg=12)
    b.tour([(0, h + 0.05), (0.05, h + 0.05), (0.04, h + 0.12), (0, h + 0.2)], M_TECK, seg=10)
    b.tour([(0.0, 1.50), (0.045, 1.50), (0.045, 1.62), (0.0, 1.62)], M_TECK, seg=10)
    # pied : dalle lestée noire
    b.boite_c(0, 0, 0, 0.55, 0.55, 0.06, M_FER)
    b.tour([(0, 0.06), (0.08, 0.06), (0.05, 0.20), (0.0, 0.20)], M_FER, seg=10)
    return b.objet(nom, loc=(x, y, z), rot=rot, recalc=False)


def canape_tresse(nom, loc, rot, places=3, m=M_TRES, prof=0.85, lg=None):
    """Canapé ou fauteuil en résine tressée + coussins écrus (W15 : salon à l'extrémité est)."""
    b = Bld()
    L = lg or (0.75 * places + 0.3)
    hx = L / 2
    b.boite(-hx, -prof / 2, 0.05, hx, prof / 2, 0.40, m)            # caisse
    b.boite(-hx, prof / 2 - 0.16, 0.40, hx, prof / 2, 0.78, m)      # dossier
    for s in (-1, 1):
        b.boite(s * hx - (0.16 if s > 0 else 0), -prof / 2, 0.40, s * hx + (0.16 if s < 0 else 0), prof / 2, 0.64, m)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.boite_c(sx * (hx - 0.05), sy * (prof / 2 - 0.05), 0, 0.06, 0.06, 0.06, M_FER)
    ob = b.objet(nom, loc=loc, rot=rot)
    biseau(ob, 0.025, 2)
    c = Bld()
    lu = (L - 0.32) / places
    for i in range(places):
        x = -hx + 0.16 + lu * (i + 0.5)
        c.boite_c(x, -0.05, 0.40, lu - 0.02, prof - 0.22, 0.54, M_COUSS)
        c.boite_c(x, prof / 2 - 0.25, 0.50, lu - 0.04, 0.16, 0.92, M_COUSS)
    oc = c.objet(nom + "_coussins", loc=loc, rot=rot)
    biseau(oc, 0.04, 3)
    return ob


def transat(nom, loc, rot):
    b = Bld()
    L, l = 1.95, 0.68
    for sx in (-1, 1):
        b.boite(sx * l / 2 - 0.025, -L / 2, 0.08, sx * l / 2 + 0.025, L / 2, 0.30, M_BLANC)
    b.boite(-l / 2, -L / 2 + 0.05, 0.25, l / 2, 0.25, 0.30, M_BLANC)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.boite_c(sx * (l / 2 - 0.04), sy * (L / 2 - 0.08), 0, 0.06, 0.06, 0.10, M_BLANC)
    ob = b.objet(nom, loc=loc, rot=rot)
    biseau(ob, 0.015, 2)
    # matelas + dossier relevé
    c = Bld()
    c.boite(-l / 2 + 0.03, -L / 2 + 0.05, 0.30, l / 2 - 0.03, 0.25, 0.36, M_COUSS)
    a = math.radians(38)
    y0, z0 = 0.25, 0.30
    pts = []
    for dz in (0.0, 0.06):
        for d in (0.0, 0.70):
            pts.append((y0 + d * math.cos(a) - dz * math.sin(a), z0 + d * math.sin(a) + dz * math.cos(a)))
    vs = []
    for x in (-l / 2 + 0.03, l / 2 - 0.03):
        vs.append([c.v((x, py, pz)) for py, pz in pts])
    order = [0, 1, 3, 2]
    for k in range(4):
        i, j = order[k], order[(k + 1) % 4]
        c.face([vs[0][i], vs[0][j], vs[1][j], vs[1][i]], M_COUSS)
    c.face([vs[0][o] for o in order], M_COUSS)
    c.face([vs[1][o] for o in reversed(order)], M_COUSS)
    oc = c.objet(nom + "_matelas", loc=loc, rot=rot)
    biseau(oc, 0.02, 2)


def massif_buisson(b, c, r, sc=(1, 1, 1), fleurs=None, densite=0.0, graine=0, sub=3, amp=0.18):
    """Boule taillée bosselée (laurier-rose, pittosporum, buis) ; faces fleuries au hasard."""
    ret = bmesh.ops.create_icosphere(b.bm, subdivisions=sub, radius=r)
    rnd = random.Random(graine)
    off = Vector((graine * 3.1, graine * 1.7, 0.3))
    for v in ret["verts"]:
        p = v.co.normalized()
        k = (1 + amp * noise.noise(p * 2.2 + off) + amp * 0.5 * noise.noise(p * 5.5 + off)
             + amp * 0.35 * noise.noise(p * 14.0 + off) + amp * 0.2 * noise.noise(p * 31.0 + off))
        v.co = Vector((v.co.x * k * sc[0], v.co.y * k * sc[1], v.co.z * k * sc[2])) + Vector(c)
    fs = {f for v in ret["verts"] for f in v.link_faces}
    mf = b.mi(M_FEUIL if fleurs else M_BUIS)
    for f in fs:
        f.smooth = True
        f.material_index = mf
    if fleurs:
        # grappes de fleurs : petites sphères posées sur les faces exposées
        for f in fs:
            if rnd.random() < densite and f.normal.z > -0.3:
                p = f.calc_center_median() + f.normal * 0.02
                for _ in range(rnd.randint(3, 6)):
                    q = p + Vector((rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), rnd.uniform(-0.03, 0.05)))
                    r2 = bmesh.ops.create_icosphere(b.bm, subdivisions=1, radius=rnd.uniform(0.018, 0.032))
                    bmesh.ops.translate(b.bm, vec=q, verts=r2["verts"])
                    for g in {g for v in r2["verts"] for g in v.link_faces}:
                        g.material_index = b.mi(fleurs)
                        g.smooth = True
    return ret


# ----------------------------------------------------------------------------------------------
# 1. Plateforme de la terrasse : remplissage, dallage, murs en pierre de taille
# ----------------------------------------------------------------------------------------------
log("terrasse…")
POLY = [tuple(p) for p in G["terrasse"]["polygone"]]
b = Bld()
b.solide(POLY, Z_FOND, T, M_APP, mhaut=M_DAL)
# bande de dallage le long des ailes (nu des ailes à y = 8,75, polygone du gabarit à 9,45)
b.solide([(-10.8, 8.70), (10.8, 8.70), (10.8, 9.46), (-10.8, 9.46)], Z_FOND, T, M_APP, mhaut=M_DAL)
plateforme = b.objet("terrasse_plateforme")

# Façades libres de la plateforme (normale gauche = extérieur)
BORD_O = [(-19.5, Y_O), (-19.5, Y_TER), (-7.5, Y_TER), (-7.5, Y_PAL)]
BORD_E = [(7.5, Y_PAL), (7.5, Y_TER), (X_E, Y_TER), (X_E, -1.8)]

b = Bld()
CORDON = [(-0.03, -0.32), (0.02, -0.32), (0.02, -0.26), (0.045, -0.23), (0.055, -0.17), (0.085, -0.14),
          (0.095, -0.08), (0.095, -0.02), (0.075, -0.005), (-0.03, -0.005)]
PLINTHE = [(-0.03, Z_FOND), (0.06, Z_FOND), (0.06, -1.04), (0.035, -1.0), (-0.03, -1.0)]
for bord in (BORD_O, BORD_E):
    balayage(b, bord, list(reversed(CORDON)), T, M_LIS)
    balayage(b, bord, list(reversed(PLINTHE)), 0, M_LIS)
moulures = b.objet("terrasse_cordon_plinthe")


# ----------------------------------------------------------------------------------------------
# 2. Balustrades (socle, balustres tournés en instances, tablette moulurée, dés)
# ----------------------------------------------------------------------------------------------
log("balustrades…")
SRC_BAL = balustre()
PROF_SOCLE = [(-0.16, 0), (0.16, 0), (0.16, 0.12), (0.13, 0.15), (0.11, H_SOCLE), (-0.11, H_SOCLE),
              (-0.13, 0.15), (-0.16, 0.12)]
PROF_TAB = [(-0.12, 0), (0.12, 0), (0.12, 0.02), (0.165, 0.045), (0.175, 0.07), (0.175, 0.105),
            (0.16, 0.125), (0.13, H_TAB), (-0.13, H_TAB), (-0.16, 0.125), (-0.175, 0.105), (-0.175, 0.07),
            (-0.165, 0.045), (-0.12, 0.02)]
B_BAL = Bld()     # socles + tablettes + dés, un seul maillage
NB_BALUSTRES = [0]
DES = []


def de(x, y, z, h=None, larg=0.44):
    """Dé (pilier) de balustrade : base, fût, chapiteau mouluré."""
    h = h or (H_SOCLE + H_BAL + H_TAB + 0.02)
    b = B_BAL
    b.boite_c(x, y, z, larg + 0.06, larg + 0.06, z + 0.14, M_LIS)
    b.boite_c(x, y, z + 0.14, larg + 0.03, larg + 0.03, z + 0.18, M_LIS)
    b.boite_c(x, y, z + 0.18, larg, larg, z + h - 0.12, M_LIS)
    b.boite_c(x, y, z + h - 0.12, larg + 0.04, larg + 0.04, z + h - 0.07, M_LIS)
    b.boite_c(x, y, z + h - 0.07, larg + 0.08, larg + 0.08, z + h, M_LIS)
    DES.append((x, y, z + h))


def troncon(p0, p1, de_debut=True, de_fin=True, pas_de=3.3, mur=True):
    """Balustrade droite (éventuellement rampante) entre p0 et p1 = (x, y, z du pied)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    dh = Vector((d.x, d.y, 0))
    Lh = dh.length
    t = dh.normalized()
    n = Vector((-t.y, t.x, 0))
    rampant = abs(d.z) > 1e-3
    for prof, z0 in ((PROF_SOCLE, 0.0), (PROF_TAB, H_SOCLE + H_BAL)):
        anneaux = []
        for p in (p0, p1):
            anneaux.append([p + n * u + Vector((0, 0, z0 + v)) for u, v in prof])
        B_BAL.boucle(anneaux, M_LIS)
    nseg = 1 if rampant else max(1, math.ceil(Lh / pas_de))
    larg_de = 0.44
    pts_de = [i / nseg for i in range(nseg + 1)]
    for i, f in enumerate(pts_de):
        if (i == 0 and not de_debut) or (i == nseg and not de_fin):
            continue
        p = p0 + d * f
        de(p.x, p.y, p.z if not rampant else p.z)
        if mur and not rampant:
            # pilastre sous le dé, sur la face du mur
            q = p + n * 0.2
            pil = [(-0.27, -0.2), (0.27, -0.2), (0.27, 0.035), (-0.27, 0.035)]
            vs = [(q + t * a + n * c) for a, c in pil]
            B_BAL.solide([(v.x, v.y) for v in vs], -1.0, T - 0.32, M_APP)
    # balustres entre dés
    for i in range(nseg):
        fa, fb = pts_de[i], pts_de[i + 1]
        la = Lh * (fb - fa)
        libre_a = larg_de / 2 + 0.06 if (i > 0 or de_debut) else 0.08
        libre_b = larg_de / 2 + 0.06 if (i < nseg - 1 or de_fin) else 0.08
        utile = la - libre_a - libre_b
        k = max(1, int(round(utile / 0.245)))
        for j in range(k):
            s = (Lh * fa + libre_a + utile * (j + 0.5) / k) / Lh
            p = p0 + d * s
            instance(SRC_BAL, "terrasse_balustre.%03d" % NB_BALUSTRES[0], (p.x, p.y, p.z + H_SOCLE))
            NB_BALUSTRES[0] += 1


# lignes d'axe des balustrades (0,20 m en retrait du nu extérieur)
e = 0.20
troncon((-19.5 + e, Y_O, T), (-19.5 + e, Y_TER - e, T))
troncon((-19.5 + e, Y_TER - e, T), (-7.5 + e, Y_TER - e, T), de_debut=False)
troncon((-7.5 + e, Y_TER - e, T), (-7.5 + e, Y_PAL, T), de_debut=False)
troncon((7.5 - e, Y_PAL, T), (7.5 - e, Y_TER - e, T))
troncon((7.5 - e, Y_TER - e, T), (X_E - e, Y_TER - e, T), de_debut=False)
troncon((X_E - e, Y_TER - e, T), (X_E - e, -1.8, T), de_debut=False)


# ----------------------------------------------------------------------------------------------
# 3. Escalier est (descend vers le nord, terrasse → cour/parking), balustrades rampantes
# ----------------------------------------------------------------------------------------------
log("escalier est…")
EST = G["escalier_terrasse_est"]
NE = EST["marches"]["valeur"]                     # 8 hauteurs
Y0, Y1 = -1.8, EST["rect"][1]                     # -1.8 → -4.8
XI0, XI1 = 18.0 + 0.03, X_E - 0.37                # emmarchement entre la façade est et l'échiffre
hm = (T - Z_NORD) / NE
gir = (Y0 - Y1) / (NE - 1)


def marches(b, nez, z_hauts, x0x1, sens, m=M_MAR, long_pierre=1.15):
    """Marches en pierres jointives à nez arrondi. nez[i] = position (axe de montée) du nez de la marche i ;
    z_hauts[i] = dessus ; x0x1(i) = (x gauche, x droite) ; sens = +1/-1 sens de la descente sur l'axe."""
    for i in range(len(nez)):
        y_nez = nez[i]
        y_arr = y_nez - sens * (gir_cour[0] + 0.03)
        z = z_hauts[i]
        xa, xb = x0x1(i)
        n = max(1, int(round((xb - xa) / long_pierre)))
        for k in range(n):
            a = xa + (xb - xa) * k / n + 0.003
            c = xa + (xb - xa) * (k + 1) / n - 0.003
            ya, yb = sorted((y_arr, y_nez))
            b.boite(a, ya, z - 0.17, c, yb, z, m)
        # noyau sous la marche
        ya, yb = sorted((y_arr, y_nez))
        b.boite(xa + 0.01, ya, Z_FOND, xb - 0.01, yb - 0.0, z - 0.17, M_APP)


gir_cour = [gir]
b = Bld()
nez = [Y0 - gir * (i + 1) for i in range(NE - 1)]
zh = [T - hm * (i + 1) for i in range(NE - 1)]
marches(b, nez, zh, lambda i: (XI0, XI1), -1)
# dernière contremarche au sol
esc = b.objet("terrasse_escalier_est_marches")
biseau(esc, 0.012, 2)

b = Bld()
# échiffres pleins sous les rampes : profil en pente du palier au sol
for xa, xb in ((XI1, X_E),):
    yb = Y1 - 0.25
    zb = Z_NORD + 0.25
    pts_b = [(xa, Y0), (xb, Y0), (xb, yb), (xa, yb)]
    vb = [b.v((x, y, Z_FOND)) for x, y in pts_b]
    vh = [b.v((xa, Y0, T)), b.v((xb, Y0, T)), b.v((xb, yb, zb)), b.v((xa, yb, zb))]
    b.coque(vb, vh, M_APP)
echiffres_est = b.objet("terrasse_escalier_est_echiffres")
# balustrades rampantes (pied sur le rampant)
for xc in ((XI1 + X_E) / 2,):
    troncon((xc, Y0, T), (xc, Y1 - 0.25, Z_NORD + 0.25), de_debut=False, de_fin=True, mur=False)


# ----------------------------------------------------------------------------------------------
# 4. Perron sud évasé (10 marches, LiDAR HD), échiffres, urnes, massifs en bacs ronds
# ----------------------------------------------------------------------------------------------
log("perron sud…")
PS = G["perron_sud"]
NS = PS["marches"]["valeur"]                      # 10 hauteurs
YH, YB = Y_PAL, Y_BAS
hs = (T - Z_SUD) / NS
gs = (YB - YH) / (NS - 1)
gir_cour[0] = gs


def demi_largeur(y):
    return 7.5 + 2.0 * (y - YH) / (YB - YH)


b = Bld()
nez = [YH + gs * (i + 1) for i in range(NS - 1)]
zh = [T - hs * (i + 1) for i in range(NS - 1)]
marches(b, nez, zh, lambda i: (-demi_largeur(nez[i]), demi_largeur(nez[i])), +1, long_pierre=1.25)
perron_sud = b.objet("terrasse_perron_sud_marches")
biseau(perron_sud, 0.015, 2)

b = Bld()
URNES = []
for s in (-1, 1):
    # échiffre évasé, couronnement rampant
    ep = 0.36
    p_h = Vector((s * 7.5, YH, 0))
    p_b = Vector((s * 9.5, YB, 0))
    d = (p_b - p_h).normalized()
    nrm = Vector((d.y, -d.x, 0)) * s  # vers l'extérieur du perron
    if nrm.x * s < 0:
        nrm = -nrm
    z_h, z_b = T, Z_SUD + 0.42
    q = [p_h, p_h + nrm * ep, p_b + nrm * ep, p_b]
    zz = [z_h, z_h, z_b, z_b]
    vb = [b.v((v.x, v.y, Z_FOND)) for v in q]
    vh = [b.v((v.x, v.y, z)) for v, z in zip(q, zz)]
    if s < 0:
        vb, vh = vb[::-1], vh[::-1]
    b.coque(vb, vh, M_APP)
    # couronnement rampant
    cq = [p_h - nrm * 0.04, p_h + nrm * (ep + 0.05), p_b + nrm * (ep + 0.05), p_b - nrm * 0.04]
    vb = [b.v((v.x, v.y, z - 0.005)) for v, z in zip(cq, zz)]
    vh = [b.v((v.x, v.y, z + 0.10)) for v, z in zip(cq, zz)]
    if s < 0:
        vb, vh = vb[::-1], vh[::-1]
    b.coque(vb, vh, M_LIS)
    # dé en pied d'échiffre, portant une urne
    c = p_b + nrm * (ep / 2) + d * 0.05
    b.boite_c(c.x, c.y, Z_FOND, 0.56, 0.56, Z_SUD + 0.10, M_LIS)
    b.boite_c(c.x, c.y, Z_SUD + 0.10, 0.50, 0.50, Z_SUD + 0.62, M_APP)
    b.boite_c(c.x, c.y, Z_SUD + 0.62, 0.58, 0.58, Z_SUD + 0.70, M_LIS)
    URNES.append((c.x, c.y, Z_SUD + 0.70))
    # dé en tête, au raccord de la balustrade
echiffres_sud = b.objet("terrasse_perron_sud_echiffres")
biseau(echiffres_sud, 0.008, 1)

SRC_URNE = urne()
for i, (x, y, z) in enumerate(URNES):
    instance(SRC_URNE, "terrasse_urne_perron.%d" % i, (x, y, z))

# massifs : bacs ronds maçonnés + lauriers-roses en boule (W01, W15)
cx_bac = abs(PS["massifs"]["centres"][0][0]) + 0.4  # 11,4 : dégage l'échiffre
cy_bac = 19.1                                        # 18,75 recoupait le mur de terrasse
R = PS["massifs"]["diametre_m"] / 2
for i, s in enumerate((-1, 1)):
    b = Bld()
    prof = [(R - 0.22, Z_FOND), (R, Z_FOND), (R, -1.02), (R + 0.03, -0.98), (R + 0.05, -0.90),
            (R + 0.05, -0.84), (R - 0.25, -0.84), (R - 0.25, -0.90), (R - 0.22, -0.92)]
    b.tour(prof, M_APP, c=(s * cx_bac, cy_bac, 0), seg=48, ferme=True, angle_vif=30)
    b.tour([(0, -0.95), (R - 0.22, -0.95), (R - 0.22, -0.93), (0, -0.93)], M_TERRE, c=(s * cx_bac, cy_bac, 0), seg=32)
    bac = b.objet("terrasse_bac_massif.%d" % i)
    v = Bld()
    massif_buisson(v, (s * cx_bac, cy_bac, 0.35), R - 0.05, sc=(1, 1, 0.82), fleurs=M_FLEUR, densite=0.06, graine=i + 1, sub=5)
    massif_buisson(v, (s * cx_bac + 0.5, cy_bac - 0.6, 0.9), 0.8, fleurs=M_FLEUR, densite=0.06, graine=i + 11, sub=4)
    v.objet("terrasse_laurier_rose.%d" % i, recalc=False)
# vasques blanches à côté des massifs (W01)
for i, s in enumerate((-1, 1)):
    instance(SRC_URNE, "terrasse_urne_massif.%d" % i, (s * (cx_bac + R + 0.55), cy_bac + 0.9, Z_SUD), sc=0.8)

# soupiraux grillagés dans le mur de face (W01, W15)
b = Bld()
for x in (-15.5, 15.5):
    y = Y_TER
    b.boite_c(x, y + 0.03, -0.98, 0.86, 0.06, -0.48, M_LIS)
    b.boite_c(x, y + 0.062, -0.92, 0.62, 0.004, -0.54, M_NOIR)
    for k in range(9):
        xx = x - 0.28 + k * 0.07
        b.cylindre((xx, y + 0.07, -0.92), (xx, y + 0.07, -0.54), 0.008, M_FER, seg=6)
    for z in (-0.80, -0.66):
        b.cylindre((x - 0.31, y + 0.072, z), (x + 0.31, y + 0.072, z), 0.008, M_FER, seg=6)
soup = b.objet("terrasse_soupiraux")


# ----------------------------------------------------------------------------------------------
# 5. Perron nord : palier, 9 marches, échiffres et dés, 2 lampadaires boule (P38, P40)
# ----------------------------------------------------------------------------------------------
log("perron nord…")
PN = G["perron_nord"]
NN = PN["marches"]["valeur"]
Z_PAL = -0.02
YP0 = PN["polygone"][0][1]                    # nu de l'avant-corps nord
YP1 = YP0 - PN["palier_m"]["valeur"]          # -13,65
YP2 = PN["polygone"][2][1]                    # -16,62
hn = (Z_PAL - Z_NORD) / NN
gn = (YP1 - YP2) / (NN - 1)
gir_cour[0] = gn
HX = PN["largeur_m"]["valeur"] / 2            # 3,0
b = Bld()
# palier en grandes dalles
for k in range(4):
    xa = -HX + 2 * HX * k / 4 + 0.003
    xb = -HX + 2 * HX * (k + 1) / 4 - 0.003
    b.boite(xa, YP1 - 0.03, Z_PAL - 0.17, xb, YP0, Z_PAL, M_MAR)
b.boite(-HX, YP1, Z_FOND, HX, YP0, Z_PAL - 0.17, M_APP)
nez = [YP1 - gn * i - 0.0 for i in range(1, NN)]
zh = [Z_PAL - hn * i for i in range(1, NN)]
marches(b, nez, zh, lambda i: (-HX, HX), -1, long_pierre=1.6)
pn = b.objet("terrasse_perron_nord_marches")
biseau(pn, 0.015, 2)

b = Bld()
LAMPES = []
for s in (-1, 1):
    xa, xb = sorted((s * HX, s * (HX + 0.55)))
    y_ram = YP1 - 0.6
    y_de = YP2 + 0.05
    # mur plein : horizontal le long du palier puis rampant
    z_top_h, z_top_b = Z_PAL + 0.42, Z_NORD + 0.95
    b.boite(xa, y_ram, Z_FOND, xb, YP0, z_top_h, M_APP)
    pts = [(xa, y_ram), (xb, y_ram), (xb, y_de), (xa, y_de)]
    vb = [b.v((x, y, Z_FOND)) for x, y in pts]
    vh = [b.v((xa, y_ram, z_top_h)), b.v((xb, y_ram, z_top_h)), b.v((xb, y_de, z_top_b)), b.v((xa, y_de, z_top_b))]
    b.coque(vb, vh, M_APP)
    # couronnement : partie plate + partie rampante
    b.boite(xa - 0.04, y_ram, z_top_h, xb + 0.04, YP0, z_top_h + 0.10, M_LIS)
    cb = [b.v((xa - 0.04, y_ram, z_top_h - 0.002)), b.v((xb + 0.04, y_ram, z_top_h - 0.002)),
          b.v((xb + 0.04, y_de, z_top_b - 0.002)), b.v((xa - 0.04, y_de, z_top_b - 0.002))]
    ch = [b.v((xa - 0.04, y_ram, z_top_h + 0.10)), b.v((xb + 0.04, y_ram, z_top_h + 0.10)),
          b.v((xb + 0.04, y_de, z_top_b + 0.10)), b.v((xa - 0.04, y_de, z_top_b + 0.10))]
    b.coque(cb[::-1] if True else cb, ch[::-1], M_LIS)
    # dé en pied d'échiffre (P40 : gros dé portant le lampadaire)
    cx_, cy_ = s * (HX + 0.40), YP2 + 0.30
    b.boite_c(cx_, cy_, Z_FOND, 0.80, 0.80, Z_NORD + 0.16, M_LIS)
    b.boite_c(cx_, cy_, Z_NORD + 0.16, 0.72, 0.72, Z_NORD + 0.98, M_APP)
    b.boite_c(cx_, cy_, Z_NORD + 0.98, 0.80, 0.80, Z_NORD + 1.06, M_LIS)
    b.boite_c(cx_, cy_, Z_NORD + 1.06, 0.86, 0.86, Z_NORD + 1.12, M_LIS)
    LAMPES.append((cx_, cy_, Z_NORD + 1.12))
echn = b.objet("terrasse_perron_nord_echiffres")
biseau(echn, 0.008, 1)
SRC_LAMP = lampadaire()
for i, p in enumerate(LAMPES):
    instance(SRC_LAMP, "terrasse_lampadaire_nord.%d" % i, p)

# objets du palier (P38) : fougère en pot, lanterne-photophore, petit pot
b = pot_terre_cuite(0.26, 0.40, M_POTVERT)
for k in range(16):
    a = 2 * math.pi * k / 16 + 0.2 * math.sin(k * 3.1)
    L = 0.55 + 0.15 * math.sin(k * 1.7)
    pts = []
    for t in range(6):
        f = t / 5
        r = 0.05 + L * f
        z = 0.38 + 0.35 * math.sin(f * math.pi * 0.75) - 0.25 * f * f
        pts.append((r * math.cos(a), r * math.sin(a), z))
    w = 0.07
    prev = None
    for t, p in enumerate(pts):
        lw = w * math.sin(min(1, (t + 1) / 6) * math.pi) + 0.01
        p = Vector(p)
        side = Vector((-math.sin(a), math.cos(a), 0)) * lw
        cur = (b.v(p - side), b.v(p + side))
        if prev:
            b.face([prev[0], prev[1], cur[1], cur[0]], M_FOUG, True)
        prev = cur
b.objet("terrasse_palier_nord_fougere", loc=(1.05, YP0 - 0.35, Z_PAL), recalc=False)
b = Bld()
b.boite_c(0, 0, 0, 0.24, 0.24, 0.04, M_FER)
for sx in (-1, 1):
    for sy in (-1, 1):
        b.boite_c(sx * 0.105, sy * 0.105, 0.04, 0.02, 0.02, 0.38, M_FER)
b.boite_c(0, 0, 0.06, 0.20, 0.20, 0.36, M_VERRE)
b.tour([(0, 0.38), (0.16, 0.38), (0.0, 0.46)], M_FER, seg=4)
b.tour([(0.03, 0.46), (0.05, 0.50), (0.03, 0.54), (0.02, 0.50)], M_FER, seg=8, ferme=True)
b.objet("terrasse_palier_nord_lanterne", loc=(1.55, YP0 - 0.3, Z_PAL), rot=0.785)
b = pot_terre_cuite(0.16, 0.26)
massif_buisson(b, (0, 0, 0.42), 0.2, graine=5, sub=2, amp=0.25)
b.objet("terrasse_palier_nord_pot", loc=(2.6, YP0 - 0.3, Z_PAL), recalc=False)


# ----------------------------------------------------------------------------------------------
# 6. Pavés de verre (éclairage du sous-sol) et pots au pied de la façade sud (W15)
# ----------------------------------------------------------------------------------------------
log("pots, mobilier…")
b = Bld()
# devant chaque porte-fenêtre des ailes et devant le portique (drone, travail/plan_domaine.json)
PAVES = json.load(open(os.path.join(RACINE, "travail", "plan_domaine.json")))["paves_verre"]["points"]
for x, y in PAVES:
    b.boite_c(x, y, T - 0.03, 1.0, 0.55, T + 0.004, M_LIS)
    for i in range(6):
        for j in range(3):
            b.boite_c(x - 0.4 + i * 0.16, y - 0.16 + j * 0.16, T - 0.02, 0.13, 0.13, T + 0.006, M_PAVE)
b.objet("terrasse_paves_verre")

POTS = [(-10.2, 9.75, "buis"), (-6.95, 9.15, "geranium"), (-3.75, 9.6, "buis"), (3.75, 9.6, "buis"),
        (6.95, 9.15, "geranium"), (10.2, 9.75, "buis"), (-2.75, 11.6, "geranium"), (2.75, 11.6, "geranium"),
        (-16.6, 9.85, "buis"), (16.6, 9.85, "buis")]
for i, (x, y, sorte) in enumerate(POTS):
    r = 0.30 if sorte == "buis" else 0.24
    b = pot_terre_cuite(r, 0.52 if sorte == "buis" else 0.36)
    if sorte == "buis":
        massif_buisson(b, (0, 0, 0.52 + 0.30), 0.34, graine=20 + i, sub=3, amp=0.12)
    else:
        massif_buisson(b, (0, 0, 0.36 + 0.10), 0.30, sc=(1, 1, 0.6), fleurs=M_GERA, densite=0.5, graine=30 + i,
                       sub=3, amp=0.3)
    b.objet("terrasse_pot.%02d" % i, loc=(x, y, T), recalc=False)


# ----------------------------------------------------------------------------------------------
# 7. Mobilier : 4 parasols, tables et chaises, salons tressés, transats, guéridons (W05, W13, W15)
# ----------------------------------------------------------------------------------------------
SRC_CH = chaise_teck()
Z_BALCON = G["niveaux"]["etage_sol"]["valeur"]
parasol(-5.6, 12.9, T, "terrasse_parasol.0", rot=0.08)
parasol(5.6, 12.9, T, "terrasse_parasol.1", rot=-0.06)
parasol(1.0, 10.35, Z_BALCON, "terrasse_parasol.3_balcon", rot=0.0, cote=2.6)

nchaise = [0]


def groupe_table(x, y, z, lx, ly, rot, chaises):
    tb = table_teck(lx, ly)
    tb.objet("terrasse_table.%d_%d" % (int(x * 10), int(y * 10)), loc=(x, y, z), rot=rot)
    for (cx, cy, a) in chaises:
        p = Matrix.Rotation(rot, 3, "Z") @ Vector((cx, cy, 0))
        instance(SRC_CH, "terrasse_chaise.%02d" % nchaise[0], (x + p.x, y + p.y, z), rot + a)
        nchaise[0] += 1


groupe_table(-5.6, 12.9, T, 1.8, 0.95, 0.08,
             [(-0.5, 0.75, 0), (0.5, 0.75, 0), (-0.5, -0.75, math.pi), (0.5, -0.75, math.pi), (1.2, 0, -math.pi / 2)])
groupe_table(5.6, 12.9, T, 1.0, 1.0, -0.3, [(0, 0.8, 0), (0.8, 0, -math.pi / 2), (0, -0.8, math.pi)])
groupe_table(1.0, 10.35, Z_BALCON, 0.8, 0.8, 0.0, [(-0.7, 0, math.pi / 2), (0.7, 0, -math.pi / 2)])

# coin apéro tressé anthracite à l'angle sud-est (W15) : deux canapés face à face, deux fauteuils, table basse
XA, YA = 15.6, 11.75
# pas de canapé côté façade : passage libre le long du mur (scooter, demande du 18/11)
canape_tresse("terrasse_salon_est_canape.1", (XA, YA + 1.3, T), 0.0, places=3)
canape_tresse("terrasse_salon_est_fauteuil.0", (XA - 2.05, YA, T), math.pi / 2, places=1, lg=0.95)
canape_tresse("terrasse_salon_est_fauteuil.1", (XA + 2.05, YA, T), -math.pi / 2, places=1, lg=0.95)
b = Bld()
b.boite_c(0, 0, 0, 1.4, 0.8, 0.40, M_TRES)
ob = b.objet("terrasse_salon_est_table", loc=(XA, YA, T))
biseau(ob, 0.02, 2)
b = Bld()
b.boite_c(0, 0, 0.40, 1.32, 0.72, 0.42, M_VERRE)
b.objet("terrasse_salon_est_plateau", loc=(XA, YA, T))
# banquette écrue devant la baie est de l'avant-corps (W15)
canape_tresse("terrasse_banquette_avant_corps", (4.6, 11.1, T), math.pi + 0.35, places=2, m=M_TRES_E)

# coin fumeur sur le retour est (demande du 18/11) : canapé dos à la balustrade, grand cendrier tube sur pied
canape_tresse("terrasse_coin_fumeur_canape", (21.15, 2.9, T), -math.pi / 2, places=3)
M_INOX = materiau("inox_brosse", (0.62, 0.63, 0.64), 0.32, 1.0)
M_SABLE_C = materiau("sable_cendrier", (0.78, 0.72, 0.6), 0.95)
M_MEGOT = materiau("megot", (0.92, 0.88, 0.8), 0.7)
M_FILTRE = materiau("filtre_megot", (0.78, 0.52, 0.28), 0.7)
b = Bld()
b.tour([(0.0, 0.0), (0.19, 0.0), (0.19, 0.025), (0.15, 0.045), (0.0, 0.045)], M_FER, seg=28)          # socle lesté
b.tour([(0.0, 0.045), (0.105, 0.045), (0.105, 0.98), (0.0, 0.98)], M_INOX, seg=28)                  # fût
b.tour([(0.0, 0.98), (0.125, 0.98), (0.135, 1.0), (0.135, 1.03), (0.118, 1.035), (0.112, 1.02), (0.0, 1.02)], M_INOX, seg=28)
b.tour([(0.0, 1.021), (0.108, 1.021)], M_SABLE_C, seg=28)                                # sable
for k in range(10):                                                                                    # fentes d'aération
    a_ = k * math.pi / 5
    b.boite_c(0.106 * math.cos(a_), 0.106 * math.sin(a_), 0.82, 0.012, 0.012, 0.9, M_FER)
for k, (dx, dy, ang) in enumerate(((0.03, 0.02, 0.4), (-0.04, 0.01, 1.9), (0.0, -0.05, 2.8), (-0.02, 0.05, 4.4))):
    c_, s_ = math.cos(ang), math.sin(ang)
    b.cylindre((dx, dy, 1.03), (dx + 0.03 * c_, dy + 0.03 * s_, 1.03), 0.0045, M_MEGOT, seg=6)
    b.cylindre((dx + 0.03 * c_, dy + 0.03 * s_, 1.03), (dx + 0.045 * c_, dy + 0.045 * s_, 1.03), 0.0047, M_FILTRE, seg=6)
b.objet("terrasse_coin_fumeur_cendrier", loc=(21.35, 4.95, T))

# transats blancs, terrasse ouest (W15)
transat("terrasse_transat.0", (-13.0, 11.6, T), math.pi / 2 + 0.1)
transat("terrasse_transat.1", (-15.6, 11.6, T), math.pi / 2 - 0.05)
# guéridons noirs et lampe de table (W13, W15)
b = Bld()
b.tour([(0, 0), (0.22, 0), (0.22, 0.03), (0.04, 0.06), (0.03, 0.70), (0.06, 0.72), (0.30, 0.72), (0.30, 0.75),
        (0.0, 0.75)], M_FER, seg=20)
SRC_GUE = b.objet("terrasse_src_gueridon", col=LIB)
instance(SRC_GUE, "terrasse_gueridon.0", (-1.6, 13.7, T))
instance(SRC_GUE, "terrasse_gueridon.1", (-0.4, 13.4, T))
instance(SRC_GUE, "terrasse_gueridon.2", (-11.3, 11.1, T))
b = Bld()
b.tour([(0, 0), (0.08, 0), (0.06, 0.03), (0.015, 0.05), (0.012, 0.32), (0, 0.32)], M_FER, seg=12)
b.tour([(0.10, 0.30), (0.17, 0.30), (0.12, 0.50), (0.06, 0.50)], M_TOILE, seg=16, ferme=False)
b.objet("terrasse_lampe_table", loc=(-11.3, 11.1, T + 0.75), recalc=False)


# ----------------------------------------------------------------------------------------------
# Regroupe les morceaux structurels (balustrades) et contrôle
# ----------------------------------------------------------------------------------------------
B_BAL.objet("terrasse_balustrades_socles_tablettes_des")
log("balustres instanciés :", NB_BALUSTRES[0], "dés :", len(DES))


# ----------------------------------------------------------------------------------------------
# Contexte pour les rendus (non exporté) : masse du château, sols
# ----------------------------------------------------------------------------------------------
def contexte():
    mc = bpy.data.materials.new("ctx_facade")
    mc.use_nodes = True
    p = next(n for n in mc.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (0.66, 0.60, 0.50, 1)
    p.inputs["Roughness"].default_value = 0.8
    ms = bpy.data.materials.new("ctx_sable")
    ms.use_nodes = True
    p = next(n for n in ms.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (0.70, 0.64, 0.54, 1)
    p.inputs["Roughness"].default_value = 0.95
    mt = bpy.data.materials.new("ctx_toit")
    mt.use_nodes = True
    p = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (0.55, 0.22, 0.12, 1)
    UVS[mc.name] = UVS[ms.name] = UVS[mt.name] = 1.0
    b = Bld()
    b.solide([(-60, Y_TER), (60, Y_TER), (60, 70), (-60, 70)], Z_SUD - 0.3, Z_SUD, ms)
    b.solide([(-60, -40), (60, -40), (60, Y_TER), (-60, Y_TER)], Z_NORD - 0.3, Z_NORD - 0.01, ms)
    b.objet("ctx_sol", col=CTX)
    b = Bld()
    for nom, r in G["corps"]["pavillons"].items():
        if isinstance(r, dict):
            x0, y0, x1, y1 = r["rect"]
            b.solide([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], Z_FOND, 10.1, mc)
    for nom in ("ouest", "est"):
        x0, y0, x1, y1 = G["corps"]["blocs_extremites"][nom]["rect"]
        b.solide([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], Z_FOND, 14.0, mc)
    b.solide([(-10.8, -8.75), (10.8, -8.75), (10.8, 8.75), (-10.8, 8.75)], Z_FOND, 14.0, mc)
    b.solide([(-4, YP0), (4, YP0), (4, -8.7), (-4, -8.7)], Z_FOND, 15.2, mc)
    b.solide([(-3.96, 8.7), (3.96, 8.7), (3.96, 9.35), (3.1, 9.35), (2.3, 11.25), (-2.3, 11.25), (-3.1, 9.35),
              (-3.96, 9.35)], Z_FOND, Z_BALCON, mc)
    b.solide([(-3.96, 8.7), (3.96, 8.7), (3.96, 9.35), (-3.96, 9.35)], Z_BALCON, 14.0, mc)
    b.solide([(-12, -9.2), (12, -9.2), (12, 9.2), (-12, 9.2)], 14.0, 14.3, mt)
    b.objet("ctx_chateau", col=CTX)


contexte()


# ----------------------------------------------------------------------------------------------
# Rendus de contrôle
# ----------------------------------------------------------------------------------------------
def regler_rendu():
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            SC.render.engine = eng
            break
        except TypeError:
            continue
    log("moteur :", SC.render.engine)
    if SC.render.engine == "CYCLES":
        SC.cycles.samples = 24
        SC.cycles.use_denoising = True
    else:
        try:
            SC.eevee.taa_render_samples = 32
            SC.eevee.use_shadows = True
        except Exception:
            pass
    SC.render.resolution_x = 1600
    SC.render.resolution_y = 900
    SC.render.film_transparent = False
    w = bpy.data.worlds.new("ciel")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.50, 0.62, 0.82, 1)
    bg.inputs["Strength"].default_value = 0.45
    SC.world = w
    sun = bpy.data.lights.new("soleil", "SUN")
    sun.energy = 3.8
    sun.color = (1.0, 0.95, 0.87)
    sun.angle = math.radians(1.5)
    so = bpy.data.objects.new("soleil", sun)
    so.rotation_euler = (math.radians(42), 0, math.radians(200))
    CTX.objects.link(so)
    try:
        SC.view_settings.view_transform = "AgX"
        SC.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass


def camera(nom, pos, cible, focale):
    cam = bpy.data.cameras.new(nom)
    cam.lens = focale
    cam.clip_end = 500
    co = bpy.data.objects.new(nom, cam)
    co.location = pos
    d = Vector(cible) - Vector(pos)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    CTX.objects.link(co)
    return co


def rendre(cam, fichier):
    SC.camera = cam
    SC.render.filepath = os.path.join(RENDUS, fichier)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log("rendu", fichier, "%.1fs" % (time.time() - t))


regler_rendu()
VUES = {
    # W15 : aérien oblique depuis le sud
    "terrasse.png": ((0.0, 52.0, 30.0), (1.0, 9.0, -1.0), 30),
    # W01 / W13 : depuis la cour sablée, à hauteur d'homme
    "terrasse_sud_sol.png": ((-6.0, 33.0, 0.35), (2.0, 14.0, 0.2), 28),
    # P40 : depuis le bas du perron nord
    "terrasse_nord.png": ((0.0, -24.0, 0.2), (0.0, -13.0, 1.2), 24),
    # détail : balustrade, perron et massif ouest depuis la terrasse
    "terrasse_detail.png": ((-13.5, 13.8, 1.55), (-8.0, 17.6, -0.2), 30),
    # W15 (droite) : retour est et escalier est
    "terrasse_est.png": ((31.0, -13.0, 1.2), (21.0, -2.5, -0.6), 30),
    # coin apéro à l'angle sud-est
    "terrasse_apero.png": ((10.5, 12.8, 1.65), (16.5, 11.3, 0.3), 26),
    "terrasse_fumeur.png": ((19.0, 8.5, 1.65), (21.2, 3.6, 0.5), 32),
}
SEULE = os.environ.get("TERRASSE_VUES")
for f, (p, c, fo) in VUES.items():
    if SEULE and f not in SEULE.split(","):
        continue
    rendre(camera("cam_" + f[:-4], p, c, fo), f)


# ----------------------------------------------------------------------------------------------
# Export : on retire le contexte, on enregistre le .blend (images empaquetées) et le .glb
# ----------------------------------------------------------------------------------------------
for ob in list(CTX.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
bpy.data.collections.remove(CTX)
for m in [m for m in bpy.data.materials if m.name.startswith("ctx_")]:
    bpy.data.materials.remove(m)
bpy.data.orphans_purge(do_recursive=True) if hasattr(bpy.data, "orphans_purge") else None

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
nv = sum(len(o.data.vertices) for o in COL.objects if o.type == "MESH")
log("objets :", len(COL.objects), "sommets (avant instances/modif.) :", nv)
log("fin")

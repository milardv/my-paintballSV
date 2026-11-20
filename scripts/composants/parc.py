# Composant « parc » : terrain, cours, jardin, piscine, tennis, allées, portail, maison du gardien, grange,
# pétanque, local piscine, haies, clôtures et végétation (P2.jardin, P2.vegetation, P2.annexes).
# Plan du domaine : travail/plan_domaine.json (limite de propriété et tracés relevés sur l'orthophoto IGN).
# blender -b --factory-startup --python scripts/composants/parc.py
# Repère D-003 : mètres, +X est, +Y sud (façade jardin), Z haut, RDC = 0. L'emprise du château reste vide.
import bpy
import bmesh
import json
import math
import os
import random
import sys
import time
from mathutils import Vector, Matrix, noise as mnoise

T0 = time.time()
RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(RACINE, "assets")
GEN = os.path.join(ASSETS, "genere", "parc")
EXPORT = os.path.join(RACINE, "export", "composants")
RENDUS = os.path.join(RACINE, "rendus")
for d in (GEN, EXPORT, RENDUS):
    os.makedirs(d, exist_ok=True)

GAB = json.load(open(os.path.join(RACINE, "travail", "gabarit.json")))
ABORDS = GAB["abords"]
NIV = GAB["niveaux"]
Z_COUR_SUD = NIV["cour_sablee_sud"]["valeur"]      # -1.28
Z_COUR_NORD = NIV["cour_nord_parking"]["valeur"]   # -1.44
Z_TENNIS = NIV["tennis"]["valeur"]                 # -0.02 : au niveau de la terrasse (LiDAR HD)
Y_TER = GAB["terrasse"]["polygone"][0][1]           # bord sud de la terrasse (14,0)
Y_BAS_PERRON = GAB["perron_sud"]["polygone"][2][1]  # bas du perron sud (~18,05)
# Mesures des données ouvertes (outils/donnees_ouvertes.py) : arbres LiDAR, contour du bassin, cour sud.
_mesure = os.path.join(RACINE, "travail", "plan_mesure.json")
MESURE = json.load(open(_mesure)) if os.path.exists(_mesure) else None
# Zone couverte par les mesures (orthophoto et LiDAR recalés), dans le repère D-003.
ZONE_MESURE = (-68.0, 143.0, -53.0, 148.0)
PLAN = json.load(open(os.path.join(RACINE, "travail", "plan_domaine.json")))
Y_COUR_S = 30.5                                     # bord sud de la cour sablée (orthophoto)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RENDU_SEUL = "--sans-export" in ARGS


def log(msg):
    print(f"[parc {time.time() - T0:6.1f}s] {msg}", flush=True)


def ph(nom, carte):
    return os.path.join(ASSETS, "polyhaven", f"polyhaven-{nom}", f"{nom}_{carte}_1k.jpg")


# ---------------------------------------------------------------------------
# Textures générées (PIL) : feuillages composés à partir des LeafSet ambientCG,
# palmes, drapeaux, grillage, filet, eau, sols recolorés d'après les photos.
# ---------------------------------------------------------------------------

def generer_textures():
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np

    rnd = random.Random(11)

    def enregistrer(img, nom):
        p = os.path.join(GEN, nom)
        if nom.endswith(".jpg"):
            img.convert("RGB").save(p, quality=88)
        else:
            img.save(p, optimize=True)
        return p

    def recolorer(src, cible, nom, contraste=1.0):
        a = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
        m = a.reshape(-1, 3).mean(0)
        lum = a.mean(2, keepdims=True)
        lm = lum.mean()
        a2 = (a / m) * np.array(cible, np.float32)
        if contraste != 1.0:
            a2 = a2 * (1 + (lum / lm - 1) * (contraste - 1))
        img = Image.fromarray(np.clip(a2, 0, 255).astype(np.uint8))
        return enregistrer(img, nom)

    sortie = {}
    sortie["gazon"] = recolorer(ph("leafy_grass", "diff"), (92, 122, 52), "gazon.jpg", 1.1)
    sortie["sable"] = recolorer(ph("sandy_gravel", "diff"), (214, 202, 178), "sable_cour.jpg")
    sortie["gravier"] = recolorer(ph("gravel_floor_02", "diff"), (196, 190, 178), "gravier_nord.jpg")
    sortie["asphalte"] = recolorer(ph("asphalt_02", "diff"), (112, 112, 110), "asphalte.jpg")
    sortie["pierre"] = recolorer(ph("white_sandstone_blocks_02", "diff"), (222, 214, 196), "pierre_claire.jpg")
    sortie["enduit"] = recolorer(ph("white_plaster_rough_01", "diff"), (206, 214, 200), "fond_bassin.jpg")
    sortie["tennis"] = recolorer(ph("asphalt_02", "diff"), (160, 84, 70), "tennis_resine.jpg", 0.6)
    sortie["ecorce"] = recolorer(ph("bark_brown_02", "diff"), (96, 82, 66), "ecorce.jpg")
    sortie["ecorce_pin"] = recolorer(ph("bark_brown_02", "diff"), (110, 78, 58), "ecorce_pin.jpg", 1.2)
    sortie["ecorce_olivier"] = recolorer(ph("bark_brown_02", "diff"), (112, 106, 92), "ecorce_olivier.jpg", 1.2)
    sortie["stipe"] = recolorer(ph("palm_tree_bark", "diff"), (150, 132, 108), "stipe.jpg")

    # Écorce de platane : plaques beige / gris vert / crème
    S = 512
    a = np.zeros((S, S, 3), np.float32)
    a[:] = (176, 170, 140)
    teintes = [(205, 198, 160), (140, 142, 112), (190, 184, 150), (122, 120, 96), (215, 208, 178)]
    im = Image.fromarray(a.astype(np.uint8))
    dr = ImageDraw.Draw(im)
    for _ in range(260):
        cx, cy = rnd.uniform(0, S), rnd.uniform(0, S)
        rx, ry = rnd.uniform(10, 46), rnd.uniform(8, 30)
        c = rnd.choice(teintes)
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                dr.ellipse((cx - rx + ox, cy - ry + oy, cx + rx + ox, cy + ry + oy), fill=c)
    im = im.filter(ImageFilter.GaussianBlur(1.6))
    sortie["ecorce_platane"] = enregistrer(im, "ecorce_platane.jpg")

    # Feuilles sources
    def feuilles_ambientcg(code):
        base = os.path.join(ASSETS, "ambientcg", f"ambientcg-LeafSet{code}", f"LeafSet{code}_1K-PNG",
                            f"LeafSet{code}_1K-PNG_")
        col = Image.open(base + "Color.png").convert("RGB")
        op = Image.open(base + "Opacity.png").convert("L")
        rgba = col.copy()
        rgba.putalpha(op)
        return rgba

    f24 = feuilles_ambientcg("024")
    larges = []
    for i in range(3):
        for j in range(3):
            c = f24.crop((j * 341, i * 341, j * 341 + 341, i * 341 + 341))
            larges.append(c.crop(c.getchannel("A").getbbox()))
    f19 = feuilles_ambientcg("019")
    aiguilles = []
    for i in range(3):
        c = f19.crop((0, i * 341, 1024, i * 341 + 341))
        aiguilles.append(c.crop(c.getchannel("A").getbbox()))

    def teinter(sprite, rgb, lum=1.0):
        arr = np.asarray(sprite).astype(np.float32)
        al = arr[..., 3] > 10
        if al.any():
            m = arr[..., :3][al].mean(0)
        else:
            m = np.array([128, 128, 128], np.float32)
        arr[..., :3] = arr[..., :3] / m * np.array(rgb, np.float32) * lum
        arr[..., :3] = np.clip(arr[..., :3], 0, 255)
        return Image.fromarray(arr.astype(np.uint8), "RGBA")

    def fond(img, rgb):
        arr = np.asarray(img).astype(np.uint8).copy()
        tr = arr[..., 3] < 8
        arr[..., 0][tr], arr[..., 1][tr], arr[..., 2][tr] = rgb
        return Image.fromarray(arr, "RGBA")

    def amas(nom, rgb, sprites, n, px, etroit=1.0, fleurs=None, rayon=0.44, rameaux=True, lum=(0.62, 1.12),
             aiguille=False):
        S = 512
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        c0 = (S / 2, S / 2)
        if rameaux:
            for _ in range(9):
                ang = rnd.uniform(0, 2 * math.pi)
                L = rnd.uniform(0.25, 0.4) * S
                dr.line((c0[0], c0[1], c0[0] + math.cos(ang) * L, c0[1] + math.sin(ang) * L),
                        fill=(78, 62, 44, 255), width=4)
        for k in range(n):
            ang = rnd.uniform(0, 2 * math.pi)
            r = (rnd.random() ** 0.6) * rayon * S
            x = c0[0] + math.cos(ang) * r
            y = c0[1] + math.sin(ang) * r
            sp = rnd.choice(sprites)
            if aiguille:
                h = int(px * rnd.uniform(0.7, 1.15))
                w = int(sp.width * h / max(sp.height, 1) * 0.55)
                w = max(w, 8)
                spr = sp.resize((w, max(h, 6)), Image.LANCZOS)
                rot = -math.degrees(ang) + rnd.uniform(-25, 25)
            else:
                h = int(px * rnd.uniform(0.75, 1.2))
                w = max(4, int(sp.width * h / max(sp.height, 1) * etroit))
                spr = sp.resize((w, h), Image.LANCZOS)
                rot = -math.degrees(ang) - 90 + rnd.uniform(-35, 35)
            # Les feuilles du fond plus sombres, celles du dessus plus claires
            l = lum[0] + (lum[1] - lum[0]) * (k / max(n - 1, 1)) * rnd.uniform(0.85, 1.0)
            spr = teinter(spr, rgb, l)
            spr = spr.rotate(rot, expand=True, resample=Image.BICUBIC)
            img.alpha_composite(spr, (int(x - spr.width / 2), int(y - spr.height / 2)))
        if fleurs:
            for _ in range(fleurs[1]):
                ang = rnd.uniform(0, 2 * math.pi)
                r = rnd.uniform(0.15, 0.42) * S
                x, y = c0[0] + math.cos(ang) * r, c0[1] + math.sin(ang) * r
                for _ in range(rnd.randint(3, 7)):
                    fx, fy = x + rnd.uniform(-14, 14), y + rnd.uniform(-14, 14)
                    rr = rnd.uniform(5, 9)
                    c = tuple(int(v * rnd.uniform(0.85, 1.05)) for v in fleurs[0])
                    dr.ellipse((fx - rr, fy - rr, fx + rr, fy + rr), fill=c + (255,))
                    dr.ellipse((fx - 2, fy - 2, fx + 2, fy + 2), fill=(250, 230, 200, 255))
        img = fond(img, tuple(int(v * 0.45) for v in rgb))
        return enregistrer(img, nom + ".png")

    def tuile(nom, rgb, sprites, n, px, etroit=1.0, aiguille=False, fleurs=None):
        S = 512
        base = tuple(int(v * 0.32) for v in rgb)
        img = Image.new("RGBA", (S, S), base + (255,))
        for k in range(n):
            x, y = rnd.uniform(0, S), rnd.uniform(0, S)
            sp = rnd.choice(sprites)
            h = int(px * rnd.uniform(0.7, 1.2))
            w = max(4, int(sp.width * h / max(sp.height, 1) * (0.5 if aiguille else etroit)))
            spr = sp.resize((w, max(h, 4)), Image.LANCZOS)
            spr = teinter(spr, rgb, 0.55 + 0.6 * (k / n) * rnd.uniform(0.8, 1.0))
            spr = spr.rotate(rnd.uniform(0, 360), expand=True, resample=Image.BICUBIC)
            for ox in (-S, 0, S):
                for oy in (-S, 0, S):
                    px0, py0 = int(x - spr.width / 2 + ox), int(y - spr.height / 2 + oy)
                    if -spr.width < px0 < S and -spr.height < py0 < S:
                        img.alpha_composite(spr, (px0, py0)) if px0 >= 0 and py0 >= 0 else img.paste(
                            spr, (px0, py0), spr)
        if fleurs:
            dr = ImageDraw.Draw(img)
            for _ in range(fleurs[1]):
                fx, fy, rr = rnd.uniform(0, S), rnd.uniform(0, S), rnd.uniform(4, 8)
                dr.ellipse((fx - rr, fy - rr, fx + rr, fy + rr), fill=fleurs[0] + (255,))
        return enregistrer(img.convert("RGB"), nom + ".jpg")

    especes = {
        "platane": dict(rgb=(118, 150, 70), spr=larges, n=150, px=62),
        "chene": dict(rgb=(70, 92, 48), spr=larges, n=190, px=44),
        "feuillu": dict(rgb=(92, 124, 58), spr=larges, n=160, px=52),
        "mimosa": dict(rgb=(150, 160, 70), spr=larges, n=170, px=40, etroit=0.45),
        "olivier": dict(rgb=(128, 140, 112), spr=larges, n=200, px=46, etroit=0.28),
        "laurier": dict(rgb=(64, 98, 50), spr=larges, n=120, px=80, etroit=0.27, fleurs=((236, 108, 150), 26)),
        "lavande": dict(rgb=(112, 126, 104), spr=larges, n=160, px=40, etroit=0.2, fleurs=((128, 98, 170), 30)),
        "buis": dict(rgb=(62, 92, 40), spr=larges, n=260, px=26),
        "haie": dict(rgb=(78, 108, 52), spr=larges, n=240, px=30),
        "parasol": dict(rgb=(64, 92, 46), spr=aiguilles, n=70, px=170, aiguille=True),
        "alep": dict(rgb=(98, 118, 72), spr=aiguilles, n=55, px=170, aiguille=True),
        "cypres": dict(rgb=(46, 70, 36), spr=aiguilles, n=90, px=120, aiguille=True),
        "if": dict(rgb=(36, 58, 30), spr=aiguilles, n=110, px=90, aiguille=True),
    }
    for nom, e in especes.items():
        sortie["amas_" + nom] = amas("amas_" + nom, e["rgb"], e["spr"], e["n"], e["px"], e.get("etroit", 1.0),
                                     e.get("fleurs"), aiguille=e.get("aiguille", False))
        sortie["tuile_" + nom] = tuile("tuile_" + nom, e["rgb"], e["spr"], int(e["n"] * 2.6),
                                       e["px"] * 0.8, e.get("etroit", 1.0), e.get("aiguille", False), e.get("fleurs"))

    # Palme pennée (Phoenix) : rachis au centre en v = 0.5, base à gauche
    W, Hh = 1024, 256
    img = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for i in range(70):
        t = i / 69
        x = 30 + t * 970
        L = 118 * math.sin(math.pi * min(1.0, t * 0.92 + 0.06)) ** 0.8
        for cote in (-1, 1):
            ang = math.radians(rnd.uniform(28, 42))
            ex = x + math.cos(ang) * L
            ey = Hh / 2 + cote * math.sin(ang) * L
            g = rnd.uniform(0.8, 1.1)
            col = (int(78 * g), int(112 * g), int(48 * g), 255)
            nx, ny = -math.sin(ang) * 3.2, cote * math.cos(ang) * 3.2
            dr.polygon([(x, Hh / 2), (x + nx * 1.5, Hh / 2 + ny * 1.5), (ex, ey), (x - nx, Hh / 2 - ny)], fill=col)
    dr.line((10, Hh / 2, 1010, Hh / 2), fill=(170, 150, 90, 255), width=7)
    sortie["palme"] = enregistrer(fond(img, (40, 56, 28)), "palme_pennee.png")

    # Palme en éventail (Washingtonia) : base au milieu du bas
    S = 512
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    cx, cy = S / 2, S - 14
    for k in range(48):
        a0 = math.radians(-82 + k * 3.45)
        a1 = a0 + math.radians(2.6)
        r0, r1 = 36, rnd.uniform(205, 240)
        g = rnd.uniform(0.85, 1.1)
        col = (int(96 * g), int(122 * g), int(70 * g), 255)
        p = [(cx + math.sin(a0) * r0, cy - math.cos(a0) * r0), (cx + math.sin(a0) * r1, cy - math.cos(a0) * r1),
             (cx + math.sin((a0 + a1) / 2) * (r1 - 18), cy - math.cos((a0 + a1) / 2) * (r1 - 18)),
             (cx + math.sin(a1) * r1, cy - math.cos(a1) * r1), (cx + math.sin(a1) * r0, cy - math.cos(a1) * r0)]
        dr.polygon(p, fill=col)
        dr.line((cx + math.sin(a0) * r0, cy - math.cos(a0) * r0, cx + math.sin(a0) * (r1 - 4),
                 cy - math.cos(a0) * (r1 - 4)), fill=(70, 92, 50, 255), width=2)
    dr.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill=(120, 110, 70, 255))
    sortie["eventail"] = enregistrer(fond(img, (48, 60, 36)), "palme_eventail.png")

    # Drapeaux
    img = Image.new("RGB", (600, 400))
    dr = ImageDraw.Draw(img)
    dr.rectangle((0, 0, 200, 400), fill=(0, 35, 149))
    dr.rectangle((200, 0, 400, 400), fill=(255, 255, 255))
    dr.rectangle((400, 0, 600, 400), fill=(237, 41, 57))
    sortie["drapeau_fr"] = enregistrer(img, "drapeau_fr.png")
    img = Image.new("RGB", (600, 400), (0, 51, 153))
    dr = ImageDraw.Draw(img)
    for k in range(12):
        a = 2 * math.pi * k / 12
        sx, sy = 300 + math.sin(a) * 133, 200 - math.cos(a) * 133
        pts = []
        for j in range(10):
            rr = 22 if j % 2 == 0 else 9
            aa = math.pi * j / 5
            pts.append((sx + math.sin(aa) * rr, sy - math.cos(aa) * rr))
        dr.polygon(pts, fill=(255, 204, 0))
    sortie["drapeau_ue"] = enregistrer(img, "drapeau_ue.png")

    # Grillage à mailles losanges (tuile = 2 mailles), filet de tennis
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    col = (38, 72, 44, 255)
    for ox in (-S, 0, S):
        dr.line((ox, 0, ox + S, S), fill=col, width=9)
        dr.line((ox + S, 0, ox, S), fill=col, width=9)
        dr.line((ox + S / 2, 0, ox + S * 1.5, S), fill=col, width=9)
        dr.line((ox - S / 2, 0, ox + S / 2, S), fill=col, width=9)
        dr.line((ox + S / 2, 0, ox - S / 2, S), fill=col, width=9)
        dr.line((ox + S * 1.5, 0, ox + S / 2, S), fill=col, width=9)
    sortie["grillage"] = enregistrer(fond(img, (38, 72, 44)), "grillage.png")
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for k in range(0, S, 64):
        dr.line((k, 0, k, S), fill=(30, 30, 30, 255), width=7)
        dr.line((0, k, S, k), fill=(30, 30, 30, 255), width=7)
    sortie["filet"] = enregistrer(fond(img, (30, 30, 30)), "filet.png")

    # Normale d'eau (somme de sinus périodiques)
    S = 512
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    h = np.zeros((S, S), np.float32)
    for _ in range(14):
        kx, ky = rnd.randint(-9, 9), rnd.randint(-9, 9)
        if kx == 0 and ky == 0:
            continue
        h += np.sin(2 * math.pi * (kx * xx + ky * yy) + rnd.uniform(0, 6.28)) / math.hypot(kx, ky)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 2.2
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 2.2
    n = np.dstack([-gx, gy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    sortie["eau_nor"] = enregistrer(Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8)), "eau_nor.png")
    return sortie


# ---------------------------------------------------------------------------
# Scène, matériaux, construction de maillages
# ---------------------------------------------------------------------------

bpy.ops.wm.read_factory_settings(use_empty=True)
SCENE = bpy.context.scene
COLL = bpy.data.collections.new("parc")
SCENE.collection.children.link(COLL)

_IMAGES = {}


def image(chemin, donnee=False):
    cle = (chemin, donnee)
    if cle not in _IMAGES:
        img = bpy.data.images.load(chemin, check_existing=True)
        if donnee:
            img.colorspace_settings.name = "Non-Color"
        _IMAGES[cle] = img
    return _IMAGES[cle]


_MATS = {}


def materiau(nom, base=None, couleur=(1, 1, 1), nor=None, rug_img=None, rugosite=0.85, metal=0.0, alpha=None,
             opacite=1.0, double=False, vcol=False, nor_force=1.0, emission=None):
    if nom in _MATS:
        return _MATS[nom]
    m = bpy.data.materials.new(nom)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    sortie_couleur = None
    tex = None
    if base:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image(base)
        sortie_couleur = tex.outputs["Color"]
    teinte = tuple(couleur) + (1.0,)
    if sortie_couleur is not None and (vcol or tuple(couleur) != (1, 1, 1)):
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(sortie_couleur, mix.inputs[6])
        if vcol:
            ca = nt.nodes.new("ShaderNodeVertexColor")
            ca.layer_name = "Col"
            nt.links.new(ca.outputs["Color"], mix.inputs[7])
        else:
            mix.inputs[7].default_value = teinte
        sortie_couleur = mix.outputs[2]
    if sortie_couleur is not None:
        nt.links.new(sortie_couleur, bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = teinte
    if nor:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = image(nor, True)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = nor_force
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if rug_img:
        tr = nt.nodes.new("ShaderNodeTexImage")
        tr.image = image(rug_img, True)
        nt.links.new(tr.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = rugosite
    bsdf.inputs["Metallic"].default_value = metal
    if emission:
        bsdf.inputs["Emission Color"].default_value = tuple(emission) + (1.0,)
        bsdf.inputs["Emission Strength"].default_value = 1.0
    if alpha == "CLIP" and tex is not None:
        rnd_ = nt.nodes.new("ShaderNodeMath")
        rnd_.operation = "ROUND"
        nt.links.new(tex.outputs["Alpha"], rnd_.inputs[0])
        nt.links.new(rnd_.outputs[0], bsdf.inputs["Alpha"])
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass
    elif alpha == "BLEND":
        bsdf.inputs["Alpha"].default_value = opacite
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    m.use_backface_culling = not double
    m.diffuse_color = teinte if base is None else (0.5, 0.5, 0.5, 1)
    _MATS[nom] = m
    return m


class MB:
    """Accumulateur de maillage : sommets, faces, UV par coin, matériaux, normales et couleurs optionnelles."""

    def __init__(self, lisse=True):
        self.v, self.f, self.uv, self.m, self.n, self.c = [], [], [], [], [], []
        self.lisse = lisse
        self.mats = []

    def mat(self, materiau_):
        if materiau_ not in self.mats:
            self.mats.append(materiau_)
        return self.mats.index(materiau_)

    def sv(self, co, n=None, c=None):
        self.v.append((co[0], co[1], co[2]))
        self.n.append(None if n is None else (n[0], n[1], n[2]))
        self.c.append(c)
        return len(self.v) - 1

    def face(self, idx, uvs, mi):
        self.f.append(tuple(idx))
        self.uv.append(uvs if uvs is not None else [(0.0, 0.0)] * len(idx))
        self.m.append(mi)

    def construire(self, nom):
        me = bpy.data.meshes.new(nom)
        me.from_pydata(self.v, [], self.f)
        for mt in self.mats:
            me.materials.append(mt)
        uvl = me.uv_layers.new(name="UVMap")
        for p in me.polygons:
            uvs = self.uv[p.index]
            for k, li in enumerate(p.loop_indices):
                uvl.data[li].uv = uvs[k]
        me.polygons.foreach_set("material_index", self.m)
        me.polygons.foreach_set("use_smooth", [self.lisse] * len(self.f))
        if any(c is not None for c in self.c):
            ca = me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
            for i, c in enumerate(self.c):
                ca.data[i].color = c if c is not None else (1, 1, 1, 1)
        me.update()
        if self.lisse and any(n is not None for n in self.n):
            norms = []
            for i, n in enumerate(self.n):
                norms.append(n if n is not None else tuple(me.vertices[i].normal))
            me.normals_split_custom_set_from_vertices(norms)
        return me


PARENTS = {}


def groupe(nom):
    if nom not in PARENTS:
        e = bpy.data.objects.new(nom, None)
        COLL.objects.link(e)
        PARENTS[nom] = e
    return PARENTS[nom]


def objet(nom, me, loc=(0, 0, 0), rot_z=0.0, echelle=1.0, parent="parc_jardin"):
    o = bpy.data.objects.new(nom, me)
    o.location = loc
    o.rotation_euler = (0, 0, rot_z)
    o.scale = (echelle, echelle, echelle) if not isinstance(echelle, tuple) else echelle
    COLL.objects.link(o)
    o.parent = groupe(parent)
    return o


# ---------------------------------------------------------------------------
# Géométrie de base
# ---------------------------------------------------------------------------

def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def pip(x, y, poly):
    dedans = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dedans = not dedans
        j = i
    return dedans


def rect_w(x, y, r, chute):
    dx = max(r[0] - x, 0.0, x - r[2])
    dy = max(r[1] - y, 0.0, y - r[3])
    return 1.0 - smoothstep(0.0, chute, math.hypot(dx, dy))


def catmull(points, ferme=False, pas=10):
    P = [Vector((p[0], p[1], 0.0)) for p in points]
    if ferme:
        ext = [P[-1]] + P + [P[0], P[1]]
        nseg = len(P)
    else:
        ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
        nseg = len(P) - 1
    out = []
    for i in range(nseg):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for k in range(pas):
            t = k / pas
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not ferme:
        out.append(P[-1].copy())
    return out


def reechantillonner(pts, pas, ferme=False):
    if ferme:
        pts = pts + [pts[0]]
    long_ = [0.0]
    for i in range(1, len(pts)):
        long_.append(long_[-1] + (pts[i] - pts[i - 1]).length)
    total = long_[-1]
    n = max(2, int(round(total / pas)))
    out = []
    j = 0
    for k in range(n + (0 if ferme else 1)):
        s = total * k / n
        while j < len(long_) - 2 and long_[j + 1] < s:
            j += 1
        t = (s - long_[j]) / max(long_[j + 1] - long_[j], 1e-9)
        out.append(pts[j].lerp(pts[j + 1], t))
    return out, total


def tangentes(pts, ferme=False):
    T = []
    n = len(pts)
    for i in range(n):
        if ferme:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        t = (b - a)
        t.z = 0
        T.append(t.normalized())
    return T


def tube(mb, pts, rayons, cotes, mi, rep_u=1.0, ech_v=1.0, ferme_haut=False, v0=0.0):
    """Tube le long d'une polyligne 3D (troncs, branches, mâts)."""
    n = len(pts)
    T = []
    for i in range(n):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        T.append((b - a).normalized())
    ref = Vector((0, 0, 1)) if abs(T[0].z) < 0.95 else Vector((1, 0, 0))
    N = T[0].cross(ref).normalized()
    anneaux = []
    v = v0
    for i in range(n):
        if i > 0:
            N = (N - T[i] * N.dot(T[i])).normalized()
            v += (pts[i] - pts[i - 1]).length / ech_v
        B = T[i].cross(N)
        anneau = []
        for k in range(cotes + 1):
            a = 2 * math.pi * k / cotes
            d = N * math.cos(a) + B * math.sin(a)
            anneau.append((mb.sv(pts[i] + d * rayons[i], d), k / cotes * rep_u, v))
        anneaux.append(anneau)
    for i in range(n - 1):
        for k in range(cotes):
            a0, a1 = anneaux[i][k], anneaux[i][k + 1]
            b0, b1 = anneaux[i + 1][k], anneaux[i + 1][k + 1]
            mb.face((a0[0], a1[0], b1[0], b0[0]), [(a0[1], a0[2]), (a1[1], a1[2]), (b1[1], b1[2]), (b0[1], b0[2])],
                    mi)
    if ferme_haut:
        c = mb.sv(pts[-1] + T[-1] * rayons[-1] * 0.3, T[-1])
        for k in range(cotes):
            a0, a1 = anneaux[-1][k], anneaux[-1][k + 1]
            mb.face((a0[0], a1[0], c), [(0, 0), (1, 0), (0.5, 1)], mi)


def bruit3(p, f=1.0, graine=0.0):
    return mnoise.noise(Vector((p[0] * f + graine, p[1] * f - graine * 0.7, p[2] * f + graine * 1.3)))


def boule(mb, centre, rx, ry, rz, mi, rnd, seg=(12, 8), amp=0.18, freq=0.9, rep=(3, 2), z_bas=None,
          profil=None):
    """Ellipsoïde déformé (masse de feuillage, buis, haie...). profil(t)->facteur de rayon (t=0 bas,1 haut)."""
    nu, nv = seg
    g = rnd.uniform(0, 100)
    rangs = []
    for j in range(nv + 1):
        t = j / nv
        phi = -math.pi / 2 + math.pi * t
        rang = []
        for i in range(nu + 1):
            th = 2 * math.pi * (i % nu) / nu
            d = Vector((math.cos(phi) * math.cos(th), math.cos(phi) * math.sin(th), math.sin(phi)))
            fac = 1.0 + amp * bruit3(d, freq * 2.2, g) + amp * 0.5 * bruit3(d, freq * 5.0, g + 7)
            if profil:
                fp = profil(t)
                p = Vector((d.x * rx * fp * fac, d.y * ry * fp * fac, (t * 2 - 1) * rz * (1 + 0.05 * fac)))
            else:
                p = Vector((d.x * rx * fac, d.y * ry * fac, d.z * rz * fac))
            if z_bas is not None and p.z < z_bas:
                p.z = z_bas + (p.z - z_bas) * 0.15
            nrm = Vector((d.x / max(rx, 1e-3), d.y / max(ry, 1e-3), d.z / max(rz, 1e-3))).normalized()
            rang.append((mb.sv(Vector(centre) + p, nrm), i / nu * rep[0], t * rep[1]))
        rangs.append(rang)
    for j in range(nv):
        for i in range(nu):
            a, b = rangs[j][i], rangs[j][i + 1]
            c, d = rangs[j + 1][i + 1], rangs[j + 1][i]
            if j == 0:
                mb.face((a[0], c[0], d[0]), [(a[1], a[2]), (c[1], c[2]), (d[1], d[2])], mi)
            elif j == nv - 1:
                mb.face((a[0], b[0], d[0]), [(a[1], a[2]), (b[1], b[2]), (d[1], d[2])], mi)
            else:
                mb.face((a[0], b[0], c[0], d[0]), [(a[1], a[2]), (b[1], b[2]), (c[1], c[2]), (d[1], d[2])], mi)


def cartes(mb, centre, rx, ry, rz, n, taille, mi, rnd, coque=0.65, haut_seul=False, vertical=0.0, croix=False,
           allonge=1.0):
    """Plans de feuillage à alpha répartis dans l'enveloppe d'un houppier, normales vers l'extérieur."""
    C = Vector(centre)
    for _ in range(n):
        while True:
            d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)))
            if d.length > 1e-3:
                d.normalize()
                if not haut_seul or d.z > -0.35:
                    break
        r = rnd.uniform(coque, 1.0)
        p = C + Vector((d.x * rx * r, d.y * ry * r, d.z * rz * r))
        no = Vector((d.x / rx, d.y / ry, d.z / rz)).normalized()
        w = (no + Vector((rnd.gauss(0, .5), rnd.gauss(0, .5), rnd.gauss(0, .5)))).normalized()
        if vertical > 0:
            w = (w - Vector((0, 0, w.z * vertical))).normalized()
        aide = Vector((0, 0, 1)) if abs(w.z) < 0.9 else Vector((1, 0, 0))
        u = w.cross(aide).normalized()
        v = w.cross(u).normalized()
        rot = rnd.uniform(0, 2 * math.pi)
        u, v = u * math.cos(rot) + v * math.sin(rot), v * math.cos(rot) - u * math.sin(rot)
        if vertical > 0:
            v = Vector((0, 0, 1))
            u = w.cross(v).normalized()
        s = taille * rnd.uniform(0.75, 1.25)
        nn = (no * 0.75 + Vector((0, 0, 0.35))).normalized()
        plans = [(u, v)]
        if croix:
            plans.append((w, v))
        for (uu, vv) in plans:
            hu, hv = uu * s * 0.5, vv * s * 0.5 * allonge
            ids = [mb.sv(p - hu - hv, nn), mb.sv(p + hu - hv, nn), mb.sv(p + hu + hv, nn), mb.sv(p - hu + hv, nn)]
            mb.face(ids, [(0, 0), (1, 0), (1, 1), (0, 1)], mi)


def prisme(mb, profil, y0, y1, mi_flancs, mi_faces, ech=1.0, mi_par_cote=None, y_haut=None):
    """Extrusion d'un profil (x, z) entre y0 et y1 (carrosseries)."""
    n = len(profil)
    A, B = [], []
    for i, (x, z) in enumerate(profil):
        ya0, ya1 = (y0, y1)
        if y_haut and z > y_haut[0]:
            ya0, ya1 = y_haut[1], y_haut[2]
        A.append(mb.sv((x, ya0, z)))
        B.append(mb.sv((x, ya1, z)))
    mb.face(A, [(p[0] * ech, p[1] * ech) for p in profil], mi_faces)
    mb.face(list(reversed(B)), [(p[0] * ech, p[1] * ech) for p in reversed(profil)], mi_faces)
    for i in range(n):
        j = (i + 1) % n
        mi = mi_par_cote[i] if mi_par_cote else mi_flancs
        mb.face((A[i], B[i], B[j], A[j]), [(0, 0), (0, 1), (1, 1), (1, 0)], mi)


def boite(mb, x0, y0, z0, x1, y1, z1, mi, ech=1.0):
    P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1),
         (x0, y1, z1)]
    ids = [mb.sv(p) for p in P]
    F = [((0, 3, 2, 1), "xy"), ((4, 5, 6, 7), "xy"), ((0, 1, 5, 4), "xz"), ((1, 2, 6, 5), "yz"), ((2, 3, 7, 6), "xz"),
         ((3, 0, 4, 7), "yz")]
    for f, plan in F:
        uvs = []
        for k in f:
            p = P[k]
            if plan == "xy":
                uvs.append((p[0] * ech, p[1] * ech))
            elif plan == "xz":
                uvs.append((p[0] * ech, p[2] * ech))
            else:
                uvs.append((p[1] * ech, p[2] * ech))
        mb.face([ids[k] for k in f], uvs, mi)


def pave(mb, a, b, ep, zb, zt, mi, ech=1.0, decal=0.0):
    """Mur droit de a à b (2D), épaisseur ep centrée (décalée de decal vers la gauche), pied zb (a, b), tête zt (a, b)."""
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    t = (b - a).normalized()
    n = Vector((-t.y, t.x, 0))
    L = (b - a).length
    c = [a - n * (ep / 2 - decal), b - n * (ep / 2 - decal), b + n * (ep / 2 + decal), a + n * (ep / 2 + decal)]
    za = [zb[0], zb[1], zb[1], zb[0]]
    zh = [zt[0], zt[1], zt[1], zt[0]]
    B = [mb.sv((p.x, p.y, z)) for p, z in zip(c, za)]
    T = [mb.sv((p.x, p.y, z)) for p, z in zip(c, zh)]
    u = [0.0, L, L, 0.0]
    mb.face([B[0], B[3], B[2], B[1]], [(0, 0), (0, ep), (L, ep), (L, 0)], mi)
    mb.face([T[0], T[1], T[2], T[3]], [(0, 0), (L * ech, 0), (L * ech, ep * ech), (0, ep * ech)], mi)
    for i in range(4):
        j = (i + 1) % 4
        L_ = (c[j] - c[i]).length
        mb.face([B[i], B[j], T[j], T[i]], [(0, za[i] * ech), (L_ * ech, za[j] * ech), (L_ * ech, zh[j] * ech),
                                           (0, zh[i] * ech)], mi)


def decaler_poly(poly, d):
    """Polygone fermé décalé de d vers l'intérieur."""
    aire = sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1]
               for k in range(len(poly)))
    sg = 1.0 if aire > 0 else -1.0
    n = len(poly)
    out = []
    for k in range(n):
        p0, p1, p2 = Vector((*poly[k - 1], 0)), Vector((*poly[k], 0)), Vector((*poly[(k + 1) % n], 0))
        t0, t1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n0 = Vector((-t0.y, t0.x, 0)) * sg
        n1 = Vector((-t1.y, t1.x, 0)) * sg
        m = (n0 + n1).normalized()
        out.append(tuple(p1 + m * (d / max(0.35, m.dot(n1))))[:2])
    return out


def fusionner(nom, items, parent="parc_vegetation"):
    """Réunit des instances (maillage, position, rotation z, échelle) en un seul maillage."""
    bm = bmesh.new()
    mats = []
    for me, loc, rot, ech in items:
        tmp = me.copy()
        tmp.transform(Matrix.Translation(Vector(loc)) @ Matrix.Rotation(rot, 4, "Z") @ Matrix.Scale(ech, 4))
        remap = []
        for m in tmp.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        n0 = len(bm.faces)
        bm.from_mesh(tmp)
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n0:]:
            f.material_index = remap[f.material_index] if remap else 0
        bpy.data.meshes.remove(tmp)
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    return objet(nom, me, parent=parent)


def tour(mb, profil, cotes, mi, centre=(0, 0, 0), ech_v=1.0):
    """Révolution d'un profil (r, z) : balustres, vasques, pieds."""
    C = Vector(centre)
    rangs = []
    for j, (r, z) in enumerate(profil):
        rang = []
        for k in range(cotes + 1):
            a = 2 * math.pi * k / cotes
            d = Vector((math.cos(a), math.sin(a), 0))
            rang.append(mb.sv(C + d * r + Vector((0, 0, z)), d))
        rangs.append(rang)
    for j in range(len(profil) - 1):
        for k in range(cotes):
            mb.face((rangs[j][k], rangs[j][k + 1], rangs[j + 1][k + 1], rangs[j + 1][k]),
                    [(k / cotes, profil[j][1] * ech_v), ((k + 1) / cotes, profil[j][1] * ech_v),
                     ((k + 1) / cotes, profil[j + 1][1] * ech_v), (k / cotes, profil[j + 1][1] * ech_v)], mi)


# ---------------------------------------------------------------------------
# Plan masse (gabarit + photos W03, W05, W12, W16, W18)
# ---------------------------------------------------------------------------

# Relevé du 19/11 (D-042) : emprise et abords du château recalés comme bati et terrasse
# (scripts/recaler_releve.py, calibration.json) ; la terrasse garde ses bords extérieurs (x = -19,5 et 22, y = 14).
_CAL = json.load(open(os.path.join(RACINE, "travail", "releve-2026-11-19", "calibration.json")))["reperes_communs"]


def _axe(ax, ancres):
    pts = sorted({(r["ancien"], r["nouveau"]) for r in _CAL[ax]} | set(ancres))
    return [p[0] for p in pts], [p[1] for p in pts]


_AXES = {"x": _axe("x", [(-19.5, -19.5), (22.0, 22.0)]), "y": _axe("y", [(14.0, 14.0)])}


def recaler(p):
    out = []
    for v, ax in zip(p, "xy"):
        a, b = _AXES[ax]
        if v <= a[0]:
            out.append(round(b[0] + v - a[0], 4))
        elif v >= a[-1]:
            out.append(round(b[-1] + v - a[-1], 4))
        else:
            i = next(k for k in range(1, len(a)) if v <= a[k])
            out.append(round(b[i - 1] + (v - a[i - 1]) * (b[i] - b[i - 1]) / (a[i] - a[i - 1]), 4))
    return tuple(out)


EMPRISE = [recaler(p) for p in GAB["emprise"]["polygone"]]
TERRASSE = [recaler(p) for p in GAB["terrasse"]["polygone"]]
PERRON_S = [recaler(p) for p in GAB["perron_sud"]["polygone"]]
PERRON_N = [recaler(p) for p in GAB["perron_nord"]["polygone"]]
ESC_E = [*recaler(GAB["escalier_terrasse_est"]["rect"][:2]), *recaler(GAB["escalier_terrasse_est"]["rect"][2:])]
ESC_E_POLY = [(ESC_E[0], ESC_E[1]), (ESC_E[2], ESC_E[1]), (ESC_E[2], ESC_E[3]), (ESC_E[0], ESC_E[3])]
TROUS = [EMPRISE, TERRASSE, PERRON_S, PERRON_N, ESC_E_POLY]

# Limite de propriété (polygone de Valentin recalé sur l'orthophoto IGN) et emprise du terrain modélisé.
LIMITE = [tuple(p) for p in PLAN["limite"]]
_lx = [p[0] for p in LIMITE]
_ly = [p[1] for p in LIMITE]
LIMITES = dict(ouest=min(_lx), est=max(_lx), nord=min(_ly), sud=max(_ly))

# Plateforme ouest : tennis et abords au niveau de la terrasse, murs de soutènement vers les cours.
PLAT = PLAN["plateforme_ouest"]
PLATEFORME = [tuple(p) for p in PLAT["polygone"]]
Z_PLAT = PLAT["z"]
ESC_TENNIS = PLAN["escaliers_tennis"]

TEN = PLAN["tennis"]
TEN_ENC = TEN["enceinte"]                  # x0, y0, x1, y1
TEN_COURT = TEN["court_double"]
TEN_CX = (TEN_COURT[0] + TEN_COURT[2]) / 2
TEN_CY = (TEN_COURT[1] + TEN_COURT[3]) / 2
FILET_Y = TEN["filet_y"]


def rect_esc(es, marge=0.0):
    """Rectangle (polygone) d'un escalier du tennis, du haut vers le bas."""
    a, b = Vector((*es["haut"], 0)), Vector((*es["bas"], 0))
    t = (b - a).normalized()
    n = Vector((-t.y, t.x, 0)) * (es["largeur"] / 2 + marge)
    return [tuple(a - n)[:2], tuple(b - n + t * marge)[:2], tuple(b + n + t * marge)[:2], tuple(a + n)[:2]]


TROUS_ESC = [rect_esc(es, 0.05) for es in ESC_TENNIS]

# Cour sablée sud : de la terrasse jusqu'à la pelouse (W16, W18), à l'ouest jusqu'au pied de la plateforme.
COUR_SUD = [(-36.0, 7.8), (-20.0, 7.8), (-20.0, Y_TER), (34.0, Y_TER), (34.0, Y_COUR_S - 2.5), (31.5, Y_COUR_S),
            (-33.5, Y_COUR_S), (-36.0, Y_COUR_S - 2.5)]
# Cour nord / parking (gravier clair, W12, orthophoto) : façade nord, pied de la plateforme ouest, bande de
# stationnement le long du retour est de la terrasse jusqu'à la cour sud.
X_ALLEE_E = 28.8
X_TER_E = TERRASSE[5][0]                         # retour est de la terrasse
COUR_NORD = [(-16.3, -24.0), (-16.3, -9.45), (-10.8, -9.45), (-10.8, -8.75), (-4.0, -8.75),
             (-4.0, -12.45), (4.0, -12.45), (4.0, -8.75), (10.8, -8.75), (10.8, -9.45), (18.0, -9.45), (18.0, -4.8),
             (X_TER_E, -4.8), (X_TER_E, Y_TER), (26.0, Y_TER), (26.0, -12.0), (25.5, -26.0), (15.0, -28.5), (0.0, -27.5),
             (-12.0, -26.5)]
# Sommets contre les façades nord et est : suivent le château recalé (le bord ouest x = -16,3 et le retour de la
# terrasse gardent leur x).


def _cour(p):
    if not -12.45 <= p[1] <= -4.8:
        return p
    x, y = recaler(p)
    return (p[0] if abs(p[0]) > 18.0 or p[0] == -16.3 else x, y)


COUR_NORD = [_cour(p) for p in COUR_NORD]

# Piscine en haricot (orthophoto IGN, vues Google) : lobe nord étroit en pointe, grand lobe sud, creux à l'est
# où la presqu'île porte les mâts.
CONTOUR_BASSIN = reechantillonner(catmull([tuple(p) for p in PLAN["piscine"]["contour"]], ferme=True, pas=8), 0.5,
                                  ferme=True)[0]
_c = sum((Vector((p.x, p.y, 0)) for p in CONTOUR_BASSIN), Vector()) / len(CONTOUR_BASSIN)
BASSIN_C = Vector((_c.x, _c.y, 0))
_pi = Vector((*PLAN["piscine"]["presquile"], 0))
BB = (_pi - BASSIN_C).normalized()
BA = Vector((-BB.y, BB.x, 0))
_k = (_pi - BASSIN_C).length / 5.6


def bassin_local(u, v):
    return BASSIN_C + BA * u + BB * (v * _k if v > 0 else v)


POLY_BASSIN = [(p.x, p.y) for p in CONTOUR_BASSIN]

# Allées (orthophoto IGN) : allée est (cour nord -> cour sud), grande allée en arc jusqu'au portail, voie de
# service vers la grange et la maison du gardien, accès au local piscine.
AL = PLAN["allees"]
ALLEE_EST = [tuple(p) for p in AL["est"]["points"]]
ALLEE_ARC = [tuple(p) for p in AL["arc"]["points"]]
ALLEE_SERVICE = [tuple(p) for p in AL["service"]["points"]]
ALLEE_LOCAL = [tuple(p) for p in AL["local_piscine"]["points"]]
ALLEES = [(ALLEE_EST, AL["est"]["largeur"]), (ALLEE_ARC, AL["arc"]["largeur"]),
          (ALLEE_SERVICE, AL["service"]["largeur"]), (ALLEE_LOCAL, AL["local_piscine"]["largeur"])]
_AXES = [(reechantillonner(catmull(p, pas=12), 1.0)[0], l) for p, l in ALLEES]


def dist_allee(x, y):
    """Distance au bord de la chaussée la plus proche (négative sur la chaussée)."""
    q = Vector((x, y, 0))
    d = 1e9
    for pts, l in _AXES:
        for p in pts[::2]:
            if abs(p.x - x) < 12 and abs(p.y - y) < 12:
                d = min(d, (p - q).length - l / 2)
    return d


def rect_oriente(c, dim, ang):
    a = math.radians(ang)
    u = Vector((math.cos(a), math.sin(a), 0))
    v = Vector((-u.y, u.x, 0))
    c = Vector((c[0], c[1], 0))
    return [tuple(c + u * sx * dim[0] / 2 + v * sy * dim[1] / 2)[:2] for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


BATIMENTS = [rect_oriente(PLAN[k]["centre"], PLAN[k]["dimensions"], PLAN[k]["angle_deg"])
             for k in ("gardien", "grange", "local_piscine", "petanque")]


# Relief : MNT LiDAR HD (2 m, lissé) hors des cours ; niveaux du gabarit dans les cours et sur la plateforme.
_MNT = MESURE.get("mnt_fin") if MESURE else None


def mnt(x, y):
    if not _MNT:
        return Z_COUR_SUD - 0.03 * max(0.0, y - 20.0)
    g, p = _MNT["z"], _MNT["pas"]
    u = min(max((x - _MNT["x0"]) / p, 0.0), len(g[0]) - 1.001)
    v = min(max((y - _MNT["y0"]) / p, 0.0), len(g) - 1.001)
    i, j = int(u), int(v)
    fu, fv = u - i, v - j
    vals = [g[j][i], g[j][i + 1], g[j + 1][i], g[j + 1][i + 1]]
    if None in vals:
        ok = [z for z in vals if z is not None]
        return sum(ok) / len(ok) if ok else Z_COUR_SUD
    a = vals[0] * (1 - fu) + vals[1] * fu
    b = vals[2] * (1 - fu) + vals[3] * fu
    return a * (1 - fv) + b * fv


def dist_poly(x, y, pts, pas=2):
    q = Vector((x, y, 0))
    return min((p - q).length for p in pts[::pas])


def dist_contour(x, y, poly):
    """Distance d'un point au contour fermé d'un polygone (segments)."""
    d = 1e9
    for k in range(len(poly)):
        ax, ay = poly[k]
        bx, by = poly[(k + 1) % len(poly)]
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy or 1e-9
        t = min(1.0, max(0.0, ((x - ax) * vx + (y - ay) * vy) / L2))
        d = min(d, math.hypot(x - ax - t * vx, y - ay - t * vy))
    return d


# Niveau de la margelle : moyenne du MNT le long du contour de la piscine.
Z_BASSIN = sum(mnt(p.x, p.y) for p in CONTOUR_BASSIN[::4]) / len(CONTOUR_BASSIN[::4])


# Plates-formes horizontales des bâtiments et de la pétanque (terrain en pente, LiDAR) : niveau du MNT au centre.
PADS = []
for _cle in ("gardien", "grange", "local_piscine", "petanque"):
    _poly = rect_oriente(PLAN[_cle]["centre"], PLAN[_cle]["dimensions"], PLAN[_cle]["angle_deg"])
    _xs = [p[0] for p in _poly]
    _ys = [p[1] for p in _poly]
    PADS.append((_cle, _poly, (min(_xs) - 6, min(_ys) - 6, max(_xs) + 6, max(_ys) + 6), mnt(*PLAN[_cle]["centre"])))
Z_PAD = {k: z for k, _, _, z in PADS}


def H(x, y):
    """Altitude du terrain (m) : plateforme ouest, cours (gabarit) et relief mesuré ailleurs."""
    if pip(x, y, PLATEFORME):
        return Z_PLAT - 0.03
    for _, poly, bb, zp in PADS:
        if bb[0] < x < bb[2] and bb[1] < y < bb[3]:
            d = 0.0 if pip(x, y, poly) else dist_contour(x, y, poly)
            w = 1.0 - smoothstep(1.0, 5.5, d)
            if w > 0:
                return H_libre(x, y) * (1 - w) + zp * w
    return H_libre(x, y)


def H_libre(x, y):
    if y >= Y_TER:
        hc = Z_COUR_SUD - 0.03 * max(0.0, y - Y_BAS_PERRON)
    elif y > -1.8:
        t = (y + 1.8) / (Y_TER + 1.8)
        hc = Z_COUR_NORD + (Z_COUR_SUD - Z_COUR_NORD) * t
    else:
        hc = Z_COUR_NORD
    w = max(rect_w(x, y, (-37, 7.8, 35, Y_COUR_S), 6.0), rect_w(x, y, (-16.3, -27, 27, 9), 5.0))
    h = hc * w + mnt(x, y) * (1 - w)
    if abs(x - BASSIN_C.x) < 34 and abs(y - BASSIN_C.y) < 34:
        d = 0.0 if pip(x, y, POLY_BASSIN) else dist_poly(x, y, CONTOUR_BASSIN, 3)
        wp = 1.0 - smoothstep(2.5, 11.0, d)
        h = h * (1 - wp) + (Z_BASSIN - 0.02) * wp
    return h


# ---------------------------------------------------------------------------
# Plantations (positions dans le repère D-003)
# ---------------------------------------------------------------------------

def dans_mesure(x, y):
    return MESURE is not None and ZONE_MESURE[0] < x < ZONE_MESURE[1] and ZONE_MESURE[2] < y < ZONE_MESURE[3]


def libre_pour_tronc(x, y, marge=1.2):
    """Faux si un tronc tomberait sur une allée, un bâtiment, la piscine, le tennis ou un escalier."""
    if dist_allee(x, y) < marge:
        return False
    if pip(x, y, EMPRISE) or pip(x, y, POLY_BASSIN) or any(pip(x, y, b) for b in BATIMENTS):
        return False
    if TEN_ENC[0] - 1 < x < TEN_ENC[2] + 1 and TEN_ENC[1] - 1 < y < TEN_ENC[3] + 1:
        return False
    if any(pip(x, y, t) for t in TROUS_ESC + [TERRASSE, PERRON_S, PERRON_N, ESC_E_POLY]):
        return False
    return True


def plantations():
    r = random.Random(2026)
    P = []          # (espece, x, y, echelle, rot, hauteur visée ou None)

    def ajoute(esp, x, y, e=1.0, h=None):
        P.append((esp, x, y, e, r.uniform(0, 2 * math.pi), h))

    # If conique isolé dans la pelouse, à l'ouest de l'axe (W05, W18)
    ajoute("if", -11.0, 52.0, 1.05)
    # Olivier en cépée au centre du massif rond, à l'est de la cour sablée (W02, W17, drone)
    MR = PLAN["massif_rond_est"]
    ajoute("olivier", MR["centre"][0], MR["centre"][1], 1.05)
    # Palmiers : cour sablée au pied de la plateforme du tennis (W12, W15, W16, drone), nord du tennis (W11),
    # est près des villas (W03, W05, W16)
    for x, y, e in [(-24.5, 13.5, 1.0), (-28.0, 17.5, 0.9), (-34.5, 13.5, 1.05)]:
        ajoute("phoenix", x, y, e)
    for x, y in [(-30.0, -27.0), (-24.0, -27.5), (-36.5, -26.0)]:
        ajoute("washingtonia", x, y, r.uniform(0.85, 1.1))
    for x, y in [(37.0, 10.0), (40.0, 22.5), (34.0, -7.0), (41.0, 37.5), (32.5, -21.0)]:
        ajoute(r.choice(["washingtonia", "phoenix"]), x, y, r.uniform(0.85, 1.1))
    # Devant l'entrée nord : pin isolé (gabarit), if commun devant l'aile ouest (P37)
    ar = ABORDS["cour_nord_parking"]["arbre_devant_entree"]
    ajoute("parasol", ar["x"], ar["y"], 0.75)
    ajoute("if", -8.0, -14.0, 0.85)
    # Arbres mesurés (LiDAR HD : maxima de la hauteur de canopée) ; essence déduite de la forme et du lieu.
    # Dans le domaine et sur 25 m autour (fond de scène) ; jamais sur une allée ni sur un bâtiment.
    if MESURE:
        arbres_photo = list(P)
        n0 = len(P)
        for a in MESURE["arbres"]:
            x, y, h, rc = a["x"], a["y"], a["h"], a["r"]
            if any(math.hypot(x - p[1], y - p[2]) < 3.5 for p in arbres_photo):
                continue
            if not pip(x, y, LIMITE) and dist_contour(x, y, LIMITE) > 25:
                continue
            if not libre_pour_tronc(x, y, 1.0 + 0.15 * rc):
                continue
            g = int(abs(x * 7.3 + y * 3.1)) % 4
            if rc < 1.7 and h > 6:
                esp = "cypres"
            elif h < 5.5:
                esp = "olivier"
            elif y < -35:
                esp = "parasol" if rc > 5 else "alep"
            elif h > 13 and rc > 4.5:
                esp = "parasol" if (x < -20 or y > 90) else "platane"
            else:
                esp = ("chene", "feuillu", "chene", "alep")[g]
            ajoute(esp, x, y, max(0.6, h / 9.0), h)
        log(f"arbres LiDAR : {len(P) - n0}")
    # Arbustes : lauriers-roses près de la cour, buis en boule autour des mâts de la presqu'île (W03, W05)
    ajoute("laurier", 33.0, 26.0, 0.9)
    ajoute("laurier", -36.0, 20.0, 0.8)
    for u, v in [(-2.6, 5.4), (2.8, 6.0), (-1.0, 7.4), (1.6, 7.6), (0.3, 6.2)]:
        p = bassin_local(u, v)
        ajoute("buis", p.x, p.y, r.uniform(0.8, 1.15))
    ajoute("buis", -34.5, Y_COUR_S - 2.0, 1.2)
    ajoute("buis", 32.5, Y_COUR_S - 2.0, 1.2)
    # Lavandes et buis en couronne dans le massif rond (W02, drone)
    for k in range(11):
        a = 2 * math.pi * k / 11
        ajoute("lavande" if k % 2 else "buis", MR["centre"][0] + math.cos(a) * (MR["rayon"] - 0.8),
               MR["centre"][1] + math.sin(a) * (MR["rayon"] - 0.8), r.uniform(0.8, 1.1))
    # Abords de la maison du gardien et du local piscine
    for x, y in [(97.5, 96.0), (110.5, 97.0), (96.5, 112.0), (18.0, 119.5), (29.5, 119.5)]:
        ajoute("laurier", x, y, r.uniform(0.6, 0.8))
    P = [p for p in P if p[0] in ("buis", "lavande") or libre_pour_tronc(p[1], p[2], 0.6)]
    return P


# ---------------------------------------------------------------------------
# Arbres et arbustes (variantes partagées, instanciées)
# ---------------------------------------------------------------------------

def construire_especes(TX):
    E = {}

    def m_cartes(nom):
        return materiau(f"parc_feuillage_{nom}", TX["amas_" + nom], alpha="CLIP", double=True, rugosite=0.75)

    def m_masse(nom, c=(0.8, 0.8, 0.8)):
        return materiau(f"parc_masse_{nom}", TX["tuile_" + nom], couleur=c, rugosite=0.9)

    m_ecorce = materiau("parc_ecorce", TX["ecorce"], nor=ph("bark_brown_02", "nor_gl"), rugosite=0.95)
    m_ecorce_pin = materiau("parc_ecorce_pin", TX["ecorce_pin"], nor=ph("bark_brown_02", "nor_gl"), rugosite=0.95)
    m_ecorce_pla = materiau("parc_ecorce_platane", TX["ecorce_platane"], rugosite=0.85)
    m_ecorce_oli = materiau("parc_ecorce_olivier", TX["ecorce_olivier"], nor=ph("bark_brown_02", "nor_gl"),
                            rugosite=0.95)
    m_stipe = materiau("parc_stipe", TX["stipe"], nor=ph("palm_tree_bark", "nor_gl"), rugosite=0.9)
    m_palme = materiau("parc_palme", TX["palme"], alpha="CLIP", double=True, rugosite=0.6)
    m_eventail = materiau("parc_eventail", TX["eventail"], alpha="CLIP", double=True, rugosite=0.6)
    m_jupe = materiau("parc_jupe_palmes", TX["stipe"], couleur=(0.62, 0.5, 0.36), rugosite=0.95)
    m_agave = materiau("parc_agave", couleur=(0.38, 0.5, 0.46), rugosite=0.55)

    def tronc_courbe(base, haut, r0, r1, n=6, flex=0.6, rnd=None, evase=1.3):
        pts, rs = [], []
        dev = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * flex
        for i in range(n + 1):
            t = i / n
            p = base.lerp(haut, t) + dev * math.sin(math.pi * t)
            pts.append(p)
            rr = r0 + (r1 - r0) * t
            if t < 0.15:
                rr *= 1 + (evase - 1) * (1 - t / 0.15)
            rs.append(rr)
        return pts, rs

    def branche(mb, a, b, r0, r1, mi, rnd, n=4, cotes=6):
        mil = a.lerp(b, 0.5) + Vector((0, 0, (b - a).length * 0.12)) + Vector(
            (rnd.uniform(-.3, .3), rnd.uniform(-.3, .3), 0))
        pts = [a.lerp(mil, t) if t < 1 else mil for t in (0, 0.5, 1)] + [mil.lerp(b, 0.5), b]
        tube(mb, pts, [r0 + (r1 - r0) * k / 4 for k in range(5)], cotes, mi, ech_v=1.5)

    def feuillu(nom, graine, h_tronc, n_br, rayon_h, z_houp, r_amas, n_cartes, t_carte, tex, ecorce, r_tronc=0.32,
                aplati=0.8, sommet=True):
        rnd = random.Random(graine)
        mb = MB()
        me, mc, mm = mb.mat(ecorce), mb.mat(m_cartes(tex)), mb.mat(m_masse(tex))
        base = Vector((0, 0, -0.3))
        haut = Vector((rnd.uniform(-.3, .3), rnd.uniform(-.3, .3), h_tronc))
        pts, rs = tronc_courbe(base, haut, r_tronc, r_tronc * 0.75, rnd=rnd, flex=0.25)
        tube(mb, pts, rs, 10, me, rep_u=2, ech_v=1.5)
        centres = []
        for k in range(n_br):
            a = 2 * math.pi * k / n_br + rnd.uniform(-0.4, 0.4)
            d = rayon_h * rnd.uniform(0.55, 0.85)
            c = Vector((math.cos(a) * d, math.sin(a) * d, z_houp + rnd.uniform(-0.8, 0.8)))
            centres.append(c)
            branche(mb, haut + Vector((0, 0, -0.2)), c * 0.92, r_tronc * 0.55, r_tronc * 0.18, me, rnd)
        if sommet:
            centres.append(Vector((0, 0, z_houp + r_amas * 0.9)))
        for c in centres:
            ra = r_amas * rnd.uniform(0.85, 1.15)
            boule(mb, c, ra * 0.82, ra * 0.82, ra * 0.82 * aplati, mm, rnd, seg=(10, 7), amp=0.22)
            cartes(mb, c, ra, ra, ra * aplati, n_cartes, t_carte, mc, rnd, coque=0.55)
        return mb.construire(nom)

    E["platane"] = [feuillu(f"parc_platane_{i}", 10 + i, 3.4, 5, 3.2, 7.2, 2.5, 46, 1.7, "platane", m_ecorce_pla,
                            r_tronc=0.34) for i in range(3)]
    E["chene"] = [feuillu(f"parc_chene_vert_{i}", 20 + i, 2.3, 6, 3.0, 5.4, 2.6, 52, 1.5, "chene", m_ecorce,
                          r_tronc=0.36, aplati=0.75) for i in range(3)]
    E["feuillu"] = [feuillu(f"parc_micocoulier_{i}", 30 + i, 3.0, 5, 2.8, 6.6, 2.4, 44, 1.6, "feuillu", m_ecorce,
                            r_tronc=0.3) for i in range(2)]
    E["mimosa"] = [feuillu("parc_mimosa_0", 40, 2.2, 5, 2.3, 4.8, 2.0, 40, 1.3, "mimosa", m_ecorce, r_tronc=0.22,
                           aplati=0.85)]

    def olivier(nom, graine):
        rnd = random.Random(graine)
        mb = MB()
        me, mc, mm = mb.mat(m_ecorce_oli), mb.mat(m_cartes("olivier")), mb.mat(m_masse("olivier"))
        for k in range(3):
            a = 2 * math.pi * k / 3 + rnd.uniform(-.3, .3)
            pts, rs = [], []
            for i in range(7):
                t = i / 6
                tors = math.sin(t * 5 + k) * 0.18
                pts.append(Vector((math.cos(a) * (0.12 + t * 1.1) + tors, math.sin(a) * (0.12 + t * 1.1) - tors,
                                   -0.2 + t * 2.3)))
                rs.append(0.24 - 0.13 * t)
            tube(mb, pts, rs, 8, me, rep_u=1.5, ech_v=1.0)
        for k in range(7):
            a = rnd.uniform(0, 2 * math.pi)
            d = rnd.uniform(0.6, 2.0)
            c = Vector((math.cos(a) * d, math.sin(a) * d, rnd.uniform(2.6, 4.2)))
            ra = rnd.uniform(1.0, 1.4)
            boule(mb, c, ra * 0.75, ra * 0.75, ra * 0.55, mm, rnd, seg=(9, 6), amp=0.25)
            cartes(mb, c, ra, ra, ra * 0.75, 26, 1.0, mc, rnd, coque=0.5)
        return mb.construire(nom)

    E["olivier"] = [olivier(f"parc_olivier_{i}", 50 + i) for i in range(2)]

    def pin_parasol(nom, graine):
        rnd = random.Random(graine)
        mb = MB()
        me, mc, mm = mb.mat(m_ecorce_pin), mb.mat(m_cartes("parasol")), mb.mat(m_masse("parasol"))
        pen = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)).normalized() * rnd.uniform(0.8, 1.8)
        haut = Vector((pen.x, pen.y, 9.0))
        pts, rs = tronc_courbe(Vector((0, 0, -0.3)), haut, 0.38, 0.24, n=8, flex=0.7, rnd=rnd)
        tube(mb, pts, rs, 10, me, rep_u=2, ech_v=1.5)
        cc = Vector((pen.x, pen.y, 11.6))
        for k in range(5):
            a = 2 * math.pi * k / 5 + rnd.uniform(-.3, .3)
            d = rnd.uniform(2.2, 3.8)
            c = cc + Vector((math.cos(a) * d, math.sin(a) * d, rnd.uniform(-0.4, 0.4)))
            branche(mb, haut, c - Vector((0, 0, 0.6)), 0.18, 0.06, me, rnd)
            boule(mb, c, 2.6, 2.6, 1.0, mm, rnd, seg=(10, 6), amp=0.2)
            cartes(mb, c, 3.0, 3.0, 1.25, 36, 1.7, mc, rnd, coque=0.5, haut_seul=True)
        boule(mb, cc + Vector((0, 0, 0.4)), 3.0, 3.0, 1.2, mm, rnd, seg=(10, 6), amp=0.2)
        cartes(mb, cc + Vector((0, 0, 0.5)), 3.4, 3.4, 1.3, 40, 1.7, mc, rnd, coque=0.5, haut_seul=True)
        return mb.construire(nom)

    E["parasol"] = [pin_parasol(f"parc_pin_parasol_{i}", 60 + i) for i in range(3)]

    def pin_alep(nom, graine):
        rnd = random.Random(graine)
        mb = MB()
        me, mc, mm = mb.mat(m_ecorce_pin), mb.mat(m_cartes("alep")), mb.mat(m_masse("alep"))
        pen = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)).normalized() * rnd.uniform(1.0, 2.5)
        haut = Vector((pen.x, pen.y, 10.5))
        pts, rs = tronc_courbe(Vector((0, 0, -0.3)), haut, 0.3, 0.12, n=8, flex=0.9, rnd=rnd)
        tube(mb, pts, rs, 8, me, rep_u=2, ech_v=1.5)
        for k in range(6):
            t = rnd.uniform(0.45, 1.0)
            o = pts[int(t * (len(pts) - 1))]
            a = rnd.uniform(0, 2 * math.pi)
            d = rnd.uniform(1.2, 2.6)
            c = o + Vector((math.cos(a) * d, math.sin(a) * d, rnd.uniform(0.3, 1.5)))
            branche(mb, o, c, 0.12, 0.04, me, rnd)
            ra = rnd.uniform(1.5, 2.2)
            boule(mb, c, ra * 0.7, ra * 0.7, ra * 0.4, mm, rnd, seg=(9, 6), amp=0.3)
            cartes(mb, c, ra, ra, ra * 0.6, 22, 1.5, mc, rnd, coque=0.45)
        return mb.construire(nom)

    E["alep"] = [pin_alep(f"parc_pin_alep_{i}", 70 + i) for i in range(3)]

    def fuseau(nom, graine, H_, R, tex, n_c, t_c, base_z=0.1, pointe=0.75, gonfle=0.55):
        rnd = random.Random(graine)
        mb = MB()
        mc, mm = mb.mat(m_cartes(tex)), mb.mat(m_masse(tex))
        me = mb.mat(m_ecorce)
        tube(mb, [Vector((0, 0, -0.3)), Vector((0, 0, base_z + 0.5))], [R * 0.12, R * 0.1], 6, me)

        def prof(t):
            return max(0.04, (math.sin(math.pi * min(1.0, t ** gonfle)) ** pointe))

        boule(mb, (0, 0, base_z + H_ / 2), R, R, H_ / 2, mm, rnd, seg=(10, 14), amp=0.1, freq=1.4, rep=(2, H_ / 2),
              profil=prof)
        for _ in range(n_c):
            t = rnd.random() ** 0.85
            z = base_z + t * H_ * 0.96
            rr = R * prof(t) * rnd.uniform(0.75, 1.05)
            a = rnd.uniform(0, 2 * math.pi)
            p = Vector((math.cos(a) * rr, math.sin(a) * rr, z))
            cartes(mb, p, 0.01, 0.01, 0.01, 1, t_c * (0.6 + 0.6 * prof(t)), mc, rnd, coque=1.0, vertical=1.0,
                   allonge=1.6)
        return mb.construire(nom)

    E["cypres"] = [fuseau(f"parc_cypres_{i}", 80 + i, 10.5 + i, 0.95, "cypres", 70, 1.1, pointe=0.8, gonfle=0.6)
                   for i in range(3)]
    E["if"] = [fuseau("parc_if_conique", 90, 11.0, 3.4, "if", 170, 1.6, base_z=0.0, pointe=1.0, gonfle=0.42)]

    def petite_boule(nom, graine, R, tex, n_c, t_c, hauteur=None):
        rnd = random.Random(graine)
        mb = MB()
        mc, mm = mb.mat(m_cartes(tex)), mb.mat(m_masse(tex, (0.9, 0.9, 0.9)))
        hz = hauteur or R * 0.9
        boule(mb, (0, 0, hz), R, R, hz, mm, rnd, seg=(12, 8), amp=0.06, freq=2.0, rep=(2, 1), z_bas=0.0)
        cartes(mb, (0, 0, hz), R * 1.02, R * 1.02, hz * 1.02, n_c, t_c, mc, rnd, coque=0.92)
        return mb.construire(nom)

    E["buis"] = [petite_boule(f"parc_buis_{i}", 100 + i, 0.55 + 0.15 * i, "buis", 26, 0.5) for i in range(3)]
    E["buis_grand"] = [petite_boule("parc_pittosporum", 105, 1.2, "haie", 40, 0.9, hauteur=1.1)]
    E["lavande"] = [petite_boule("parc_lavande", 106, 0.42, "lavande", 18, 0.45, hauteur=0.38)]

    # Petites plantes de bordure des allées (photos Google 11-12) : berbéris pourpres, fusains dorés,
    # santolines argentées, graminées blondes, lavandes ; feuillages des buis et lavandes reteintés.
    def petite_teintee(nom, graine, R, tex, couleur, n_c, t_c, hauteur=None):
        rnd = random.Random(graine)
        mb = MB()
        mc = mb.mat(materiau(f"parc_feuillage_{nom}", TX["amas_" + tex], couleur=couleur, alpha="CLIP", double=True,
                             rugosite=0.75))
        mm = mb.mat(materiau(f"parc_masse_{nom}", TX["tuile_" + tex], couleur=tuple(c * 0.9 for c in couleur),
                             rugosite=0.9))
        hz = hauteur or R * 0.9
        boule(mb, (0, 0, hz), R, R, hz, mm, rnd, seg=(10, 6), amp=0.08, freq=2.0, rep=(2, 1), z_bas=0.0)
        cartes(mb, (0, 0, hz), R * 1.05, R * 1.05, hz * 1.05, n_c, t_c, mc, rnd, coque=0.9)
        return mb.construire(f"parc_{nom}")

    E["bordure"] = [petite_teintee("berberis_pourpre", 150, 0.38, "buis", (2.7, 0.95, 1.2), 16, 0.35),
                    petite_teintee("fusain_dore", 151, 0.36, "buis", (3.0, 2.6, 0.7), 16, 0.35),
                    petite_teintee("santoline_argent", 152, 0.3, "lavande", (2.5, 2.7, 2.4), 14, 0.3, hauteur=0.26),
                    petite_teintee("graminee_blonde", 153, 0.32, "lavande", (3.3, 2.7, 1.4), 18, 0.42, hauteur=0.4),
                    E["lavande"][0], E["buis"][0]]

    def laurier(nom, graine):
        rnd = random.Random(graine)
        mb = MB()
        me, mc, mm = mb.mat(m_ecorce), mb.mat(m_cartes("laurier")), mb.mat(m_masse("laurier"))
        for k in range(6):
            a = 2 * math.pi * k / 6
            b = Vector((math.cos(a) * 0.15, math.sin(a) * 0.15, -0.1))
            c = Vector((math.cos(a) * 0.9, math.sin(a) * 0.9, 1.6))
            tube(mb, [b, b.lerp(c, 0.5), c], [0.05, 0.04, 0.025], 5, me)
        boule(mb, (0, 0, 1.2), 1.45, 1.45, 1.1, mm, rnd, seg=(12, 8), amp=0.18, z_bas=0.15)
        cartes(mb, (0, 0, 1.3), 1.7, 1.7, 1.15, 80, 0.85, mc, rnd, coque=0.7, haut_seul=True)
        return mb.construire(nom)

    E["laurier"] = [laurier(f"parc_laurier_rose_{i}", 110 + i) for i in range(2)]

    def phoenix(nom, graine):
        rnd = random.Random(graine)
        mb = MB()
        ms, mp = mb.mat(m_stipe), mb.mat(m_palme)
        Hs = rnd.uniform(6.0, 8.0)
        pts = [Vector((0, 0, -0.3 + Hs * t / 8 + 0.3 * t)) + Vector((math.sin(t * 2) * 0.25, 0, 0))
               for t in [i / 8 for i in range(9)]]
        rs = [0.6, 0.5, 0.46, 0.45, 0.45, 0.46, 0.5, 0.58, 0.55]
        tube(mb, pts, rs, 12, ms, rep_u=3, ech_v=1.2)
        sommet = pts[-1]
        nfr = 38
        for k in range(nfr):
            az = k * 2.399 + rnd.uniform(-.1, .1)                    # angle d'or
            rang = k / nfr
            el = math.radians(70 - 95 * rang + rnd.uniform(-8, 8))
            L = rnd.uniform(4.0, 5.0)
            dh = Vector((math.cos(az), math.sin(az), 0))
            lat = Vector((-dh.y, dh.x, 0))
            seg = 8
            rangs = []
            for i in range(seg + 1):
                s = L * i / seg
                p = sommet + dh * (s * math.cos(el)) + Vector((0, 0, s * math.sin(el) - 0.09 * s * s))
                w = 0.55 * math.sin(math.pi * min(1.0, i / seg * 0.95 + 0.05)) ** 0.7 + 0.05
                nrm = Vector((0, 0, 1))
                rangs.append((mb.sv(p - lat * w + Vector((0, 0, -0.08 * w)), nrm), mb.sv(p, nrm),
                              mb.sv(p + lat * w + Vector((0, 0, -0.08 * w)), nrm), i / seg))
            for i in range(seg):
                a, b = rangs[i], rangs[i + 1]
                mb.face((a[0], b[0], b[1], a[1]), [(a[3], 0), (b[3], 0), (b[3], 0.5), (a[3], 0.5)], mp)
                mb.face((a[1], b[1], b[2], a[2]), [(a[3], 0.5), (b[3], 0.5), (b[3], 1), (a[3], 1)], mp)
        return mb.construire(nom)

    E["phoenix"] = [phoenix(f"parc_palmier_phoenix_{i}", 120 + i) for i in range(2)]

    def washingtonia(nom, graine):
        rnd = random.Random(graine)
        mb = MB()
        ms, mf, mj = mb.mat(m_stipe), mb.mat(m_eventail), mb.mat(m_jupe)
        Hs = rnd.uniform(11.0, 14.0)
        pen = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.5
        pts = [Vector((0, 0, -0.3)).lerp(Vector((pen.x, pen.y, Hs)), t / 10) for t in range(11)]
        rs = [0.42, 0.32, 0.28, 0.27, 0.26, 0.26, 0.25, 0.25, 0.25, 0.26, 0.3]
        tube(mb, pts, rs, 10, ms, rep_u=2, ech_v=1.2)
        sommet = pts[-1]
        # Jupe de palmes sèches
        tour(mb, [(0.32, -2.2), (0.55, -1.6), (0.8, -0.9), (0.95, -0.3), (0.6, 0.15)], 12, mj,
             centre=tuple(sommet), ech_v=1.0)
        for k in range(22):
            az = k * 2.399
            el = math.radians(rnd.uniform(-10, 60))
            dh = Vector((math.cos(az), math.sin(az), 0))
            d = (dh * math.cos(el) + Vector((0, 0, math.sin(el)))).normalized()
            pet = 1.3
            a = sommet + d * 0.2
            b = sommet + d * pet + Vector((0, 0, -0.1))
            tube(mb, [a, b], [0.04, 0.025], 4, mj)
            lat = Vector((-dh.y, dh.x, 0))
            haut = (d * 0.6 + Vector((0, 0, 0.6))).normalized()
            s = rnd.uniform(1.4, 1.8)
            c0 = b - lat * s / 2
            ids = [mb.sv(c0, haut), mb.sv(b + lat * s / 2, haut),
                   mb.sv(b + lat * s / 2 + d * s * 0.95 + Vector((0, 0, -0.25)), haut),
                   mb.sv(c0 + d * s * 0.95 + Vector((0, 0, -0.25)), haut)]
            mb.face(ids, [(0, 0), (1, 0), (1, 1), (0, 1)], mf)
        return mb.construire(nom)

    E["washingtonia"] = [washingtonia(f"parc_palmier_washingtonia_{i}", 130 + i) for i in range(2)]

    def agave(nom, graine):
        rnd = random.Random(graine)
        mb = MB()
        ma = mb.mat(m_agave)
        for k in range(18):
            az = k * 2.399
            el = math.radians(20 + 50 * (k / 18) ** 0.5 + rnd.uniform(-5, 5))
            L = rnd.uniform(0.7, 1.1) * (1.1 - 0.3 * k / 18)
            dh = Vector((math.cos(az), math.sin(az), 0))
            lat = Vector((-dh.y, dh.x, 0))
            pts = []
            for i in range(5):
                s = L * i / 4
                pts.append(dh * (0.05 + s * math.cos(el)) + Vector((0, 0, 0.05 + s * math.sin(el) - 0.15 * s * s)))
            for i in range(4):
                w0, w1 = 0.11 * (1 - i / 4), 0.11 * (1 - (i + 1) / 4)
                ids = [mb.sv(pts[i] - lat * w0), mb.sv(pts[i] + lat * w0), mb.sv(pts[i + 1] + lat * w1),
                       mb.sv(pts[i + 1] - lat * w1)]
                mb.face(ids, [(0, 0), (1, 0), (1, 1), (0, 1)], ma)
        me_ = mb.construire(nom)
        for mt in me_.materials:
            mt.use_backface_culling = False
        return me_

    E["agave"] = [agave("parc_agave", 140)]
    return E


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def construire():
    TX = generer_textures()
    log("textures générées")
    for nom in ("parc_terrain", "parc_jardin", "parc_vegetation", "parc_annexes"):
        groupe(nom).parent = groupe("parc")

    m_gazon = materiau("parc_gazon", TX["gazon"], nor=ph("leafy_grass", "nor_gl"), rugosite=0.95, vcol=True,
                       nor_force=0.6)
    m_sable = materiau("parc_sable_cour", TX["sable"], nor=ph("sandy_gravel", "nor_gl"),
                       rug_img=ph("sandy_gravel", "rough"))
    m_gravier = materiau("parc_gravier_nord", TX["gravier"], nor=ph("gravel_floor_02", "nor_gl"),
                         rug_img=ph("gravel_floor_02", "rough"))
    m_asphalte = materiau("parc_asphalte", TX["asphalte"], nor=ph("asphalt_02", "nor_gl"),
                          rug_img=ph("asphalt_02", "rough"))
    m_pierre = materiau("parc_pierre_claire", TX["pierre"], nor=ph("white_sandstone_blocks_02", "nor_gl"),
                        rugosite=0.8, nor_force=0.5)
    m_bordure = materiau("parc_bordure", TX["enduit"], couleur=(0.95, 0.93, 0.88), rugosite=0.85, double=True)
    m_tennis = materiau("parc_tennis_resine", TX["tennis"], nor=ph("asphalt_02", "nor_gl"), rugosite=0.7,
                        nor_force=0.3)
    m_tennis_court = materiau("parc_tennis_court", TX["tennis"], couleur=(1.0, 0.92, 0.9), nor=ph("asphalt_02", "nor_gl"),
                              rugosite=0.7, nor_force=0.3)
    m_ligne = materiau("parc_ligne_blanche", couleur=(0.92, 0.92, 0.9), rugosite=0.6, double=True)
    m_grillage = materiau("parc_grillage", TX["grillage"], alpha="CLIP", double=True, rugosite=0.5, metal=0.3)
    m_filet = materiau("parc_filet", TX["filet"], alpha="CLIP", double=True, rugosite=0.8)
    m_fer_vert = materiau("parc_fer_vert", couleur=(0.08, 0.2, 0.12), rugosite=0.45, metal=0.6)
    m_fer_noir = materiau("parc_fer_noir", couleur=(0.03, 0.03, 0.03), rugosite=0.4, metal=0.8)
    m_mat_blanc = materiau("parc_mat_blanc", couleur=(0.9, 0.9, 0.88), rugosite=0.35, metal=0.2)
    m_dore = materiau("parc_dore", couleur=(0.85, 0.65, 0.25), rugosite=0.25, metal=1.0)
    m_eau = materiau("parc_eau_bassin", couleur=(0.3, 0.68, 0.74), nor=TX["eau_nor"], rugosite=0.03,
                     alpha="BLEND", opacite=0.55, nor_force=0.35)
    m_fond = materiau("parc_fond_bassin", TX["enduit"], couleur=(0.82, 0.93, 0.96), rugosite=0.6)
    m_jet = materiau("parc_jet_eau", couleur=(0.95, 0.97, 1.0), rugosite=0.2, alpha="BLEND", opacite=0.45,
                     double=True)
    m_eau_pisc = materiau("parc_eau_piscine", couleur=(0.12, 0.62, 0.72), nor=TX["eau_nor"], rugosite=0.03,
                          alpha="BLEND", opacite=0.75, nor_force=0.3)
    m_carrelage = materiau("parc_carrelage_piscine", couleur=(0.55, 0.8, 0.88), rugosite=0.3)
    m_terre = materiau("parc_terre_massif", TX["ecorce"], couleur=(0.75, 0.6, 0.48), rugosite=1.0)
    m_drap_fr = materiau("parc_drapeau_fr", TX["drapeau_fr"], double=True, rugosite=0.8)
    m_drap_ue = materiau("parc_drapeau_ue", TX["drapeau_ue"], double=True, rugosite=0.8)
    m_haie = materiau("parc_haie", TX["tuile_haie"], rugosite=0.9, double=True)
    m_haie_cyp = materiau("parc_haie_cypres", TX["tuile_cypres"], rugosite=0.9, double=True)
    m_regard = materiau("parc_fonte_regard", couleur=(0.15, 0.15, 0.14), rugosite=0.6, metal=0.7)

    # --- Terrain -----------------------------------------------------------
    P = plantations()
    pas = 1.5
    x0, x1, y0, y1 = LIMITES["ouest"] - 30, LIMITES["est"] + 30, LIMITES["nord"] - 30, LIMITES["sud"] + 30
    nx, ny = int((x1 - x0) / pas), int((y1 - y0) / pas)
    mb = MB()
    mi = mb.mat(m_gazon)
    rnd = random.Random(5)
    ombres = [(p[1], p[2], 4.5 * p[3]) for p in P if p[0] in ("platane", "chene", "parasol", "feuillu", "alep",
                                                             "olivier", "mimosa", "if")]
    grille = {}
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = x0 + i * pas, y0 + j * pas
            z = H(x, y)
            # Fond de la piscine : terrain abaissé sous la margelle
            if abs(x - BASSIN_C.x) < 22 and abs(y - BASSIN_C.y) < 24 and pip(x, y, POLY_BASSIN):
                z = Z_BASSIN - 0.75
            # Sous les allées : terrain légèrement abaissé (le maillage de 1,5 m ne perce pas la chaussée)
            if dist_allee(x, y) < 0.8:
                z -= 0.18
            # Teinte : gazon vert, plaques sèches (W18), sous-bois sombre, abords des limites plus secs
            n1 = mnoise.noise(Vector((x * 0.045, y * 0.045, 4.0)))
            n2 = mnoise.noise(Vector((x * 0.2, y * 0.2, 9.0)))
            c = Vector((1.0, 1.0, 1.0))
            sec = smoothstep(0.15, 0.6, n1 + 0.15 * n2)
            c = c.lerp(Vector((1.25, 1.05, 0.72)), sec * 0.55)
            sb = 0.0
            for (tx, ty, tr) in ombres:
                if abs(tx - x) < tr and abs(ty - y) < tr:
                    d = math.hypot(tx - x, ty - y)
                    sb = max(sb, 1 - smoothstep(tr * 0.4, tr, d))
            c = c.lerp(Vector((0.62, 0.55, 0.4)), sb * 0.7)
            hors = 0.0 if pip(x, y, LIMITE) else smoothstep(0, 6, dist_contour(x, y, LIMITE))
            c = c.lerp(Vector((0.85, 0.82, 0.62)), hors * 0.5)
            c = c * (0.93 + 0.07 * n2)
            col = (min(c.x * 0.8, 1), min(c.y * 0.8, 1), min(c.z * 0.8, 1), 1.0)
            grille[(i, j)] = mb.sv((x, y, z), None, col)
    for j in range(ny):
        for i in range(nx):
            cx, cy = x0 + (i + 0.5) * pas, y0 + (j + 0.5) * pas
            if any(pip(cx, cy, t) for t in TROUS + TROUS_ESC):
                continue
            ids = (grille[(i, j)], grille[(i + 1, j)], grille[(i + 1, j + 1)], grille[(i, j + 1)])
            uvs = [((x0 + (i + a) * pas) / 3.0, (y0 + (j + b) * pas) / 3.0) for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))]
            mb.face(ids, uvs, mi)
    terrain = mb.construire("parc_terrain_naturel")
    # Normales recalculées par le moteur (lisses)
    objet("parc_terrain_naturel", terrain, parent="parc_terrain")
    log(f"terrain : {len(terrain.polygons)} faces")

    # --- Surfaces drapées (cours, tennis, parking) --------------------------
    def surface(nom, poly, mat, tuile, dz=0.03, pas_c=2.0, z_fixe=None, parent="parc_terrain", trous=()):
        bm = bmesh.new()
        vs = [bm.verts.new((p[0], p[1], 0)) for p in poly]
        bm.faces.new(vs)
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x = math.floor(min(xs) / pas_c) * pas_c + pas_c
        while x < max(xs):
            g = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=g, plane_co=(x, 0, 0), plane_no=(1, 0, 0))
            x += pas_c
        y = math.floor(min(ys) / pas_c) * pas_c + pas_c
        while y < max(ys):
            g = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=g, plane_co=(0, y, 0), plane_no=(0, 1, 0))
            y += pas_c
        for f in bm.faces:
            if f.normal.z < 0:
                f.normal_flip()
        if trous:
            sup = [f for f in bm.faces if any(pip(f.calc_center_median().x, f.calc_center_median().y, t)
                                              for t in trous)]
            bmesh.ops.delete(bm, geom=sup, context="FACES")
        for v in bm.verts:
            v.co.z = (z_fixe if z_fixe is not None else H(v.co.x, v.co.y)) + dz
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for l in f.loops:
                l[uvl].uv = (l.vert.co.x / tuile, l.vert.co.y / tuile)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        me = bpy.data.meshes.new(nom)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        return objet(nom, me, parent=parent)

    surface("parc_cour_sablee_sud", COUR_SUD, m_sable, 3.0, dz=0.03, trous=(PERRON_S, *TROUS_ESC))
    surface("parc_cour_nord_parking", COUR_NORD, m_gravier, 3.0, dz=0.03, trous=(PERRON_N, ESC_E_POLY, *TROUS_ESC))
    e = TEN_ENC
    surface("parc_plateforme_ouest", PLATEFORME, m_sable, 3.0, dz=0.03, z_fixe=Z_PLAT - 0.03,
            trous=([(e[0], e[1]), (e[2], e[1]), (e[2], e[3]), (e[0], e[3])],))
    log("cours")

    # --- Allées asphaltées, bordures ---------------------------------------
    def allee(nom, points, largeur, mat, bordures=True, dz=0.07, tuile=4.0, pas_l=1.5, parent="parc_jardin"):
        pts, _ = reechantillonner(catmull(points, pas=12), pas_l)
        T = tangentes(pts)
        mb = MB(lisse=False)
        mi = mb.mat(mat)
        mbb = MB(lisse=False)
        mib = mbb.mat(m_bordure)
        offs = [-largeur / 2, -largeur / 4, 0.0, largeur / 4, largeur / 2]
        rangs = []
        s = 0.0
        for k, p in enumerate(pts):
            if k:
                s += (p - pts[k - 1]).length
            g = Vector((-T[k].y, T[k].x, 0))
            rang = []
            for o in offs:
                q = p + g * o
                rang.append(mb.sv((q.x, q.y, H(q.x, q.y) + dz)))
            rangs.append((rang, s))
        for k in range(len(rangs) - 1):
            (a, sa), (b, sb) = rangs[k], rangs[k + 1]
            for i in range(len(offs) - 1):
                mb.face((a[i + 1], a[i], b[i], b[i + 1]),
                        [(offs[i + 1] / tuile, sa / tuile), (offs[i] / tuile, sa / tuile),
                         (offs[i] / tuile, sb / tuile), (offs[i + 1] / tuile, sb / tuile)], mi)
        objet(nom, mb.construire(nom), parent=parent)
        if bordures:
            for cote in (-1, 1):
                prof = [(largeur / 2, -0.06), (largeur / 2, 0.13), (largeur / 2 + 0.02, 0.15),
                        (largeur / 2 + 0.15, 0.15), (largeur / 2 + 0.15, -0.08)]
                anneaux = []
                s = 0.0
                for k, p in enumerate(pts):
                    if k:
                        s += (p - pts[k - 1]).length
                    g = Vector((-T[k].y, T[k].x, 0)) * cote
                    qb = p + g * (largeur / 2 + 0.07)
                    zb = H(qb.x, qb.y) + dz
                    anneaux.append(([mbb.sv((p + g * o).to_tuple()[:2] + (zb + z,)) for o, z in prof], s))
                for k in range(len(anneaux) - 1):
                    (a, sa), (b, sb) = anneaux[k], anneaux[k + 1]
                    for i in range(len(prof) - 1):
                        f = (a[i], a[i + 1], b[i + 1], b[i]) if cote > 0 else (a[i + 1], a[i], b[i], b[i + 1])
                        mbb.face(f, [(sa, i * 0.1), (sa, (i + 1) * 0.1), (sb, (i + 1) * 0.1), (sb, i * 0.1)], mib)
            objet(nom + "_bordures", mbb.construire(nom + "_bordures"), parent=parent)
        return pts

    allee("parc_allee_est", ALLEE_EST, AL["est"]["largeur"], m_asphalte)
    pts_arc = allee("parc_allee_arc", ALLEE_ARC, AL["arc"]["largeur"], m_asphalte)
    allee("parc_allee_service", ALLEE_SERVICE, AL["service"]["largeur"], m_gravier, bordures=False, dz=0.05)
    allee("parc_allee_local_piscine", ALLEE_LOCAL, AL["local_piscine"]["largeur"], m_sable, bordures=False, dz=0.05)
    log("allées")

    # --- Bassin en haricot : margelle, fond, eau, jets, presqu'île, mâts -----
    C = CONTOUR_BASSIN
    T = tangentes(C, ferme=True)
    mb = MB(lisse=True)
    mp = mb.mat(m_pierre)
    prof = [(-0.02, -0.62), (0.0, 0.16), (0.04, 0.26), (0.12, 0.31), (0.36, 0.31), (0.44, 0.26), (0.47, 0.16),
            (0.47, -0.35)]
    anneaux = []
    s = 0.0
    n = len(C)
    for k in range(n + 1):
        p = C[k % n]
        if k:
            s += (p - C[k - 1]).length
        t = T[k % n]
        ext = Vector((t.y, -t.x, 0))
        if pip(*(p + ext * 0.3).to_tuple()[:2], POLY_BASSIN):
            ext = -ext
        ids = []
        for o, z in prof:
            q = p + ext * o
            nz = Vector((0, 0, 1)) if 0.1 < o < 0.4 else (ext if o >= 0.4 else -ext)
            ids.append(mb.sv((q.x, q.y, Z_BASSIN + z), nz))
        anneaux.append((ids, s))
    for k in range(n):
        (a, sa), (b, sb) = anneaux[k], anneaux[k + 1]
        ta = Vector(mb.v[b[0]]) - Vector(mb.v[a[0]])
        ea = Vector(mb.v[a[4]]) - Vector(mb.v[a[3]])
        inverse = (-ea).cross(ta).z < 0
        for i in range(len(prof) - 1):
            f = [a[i + 1], a[i], b[i], b[i + 1]]
            uv = [(sa / 1.2, (i + 1) * 0.15), (sa / 1.2, i * 0.15), (sb / 1.2, i * 0.15), (sb / 1.2, (i + 1) * 0.15)]
            if inverse:
                f.reverse()
                uv.reverse()
            mb.face(f, uv, mp)
    objet("parc_bassin_margelle", mb.construire("parc_bassin_margelle"), parent="parc_jardin")

    def plan_contour(nom, contour, z, mat, tuile):
        mb = MB(lisse=False)
        mi = mb.mat(mat)
        aire = sum(contour[k].x * contour[(k + 1) % len(contour)].y - contour[(k + 1) % len(contour)].x * contour[k].y
                   for k in range(len(contour)))
        if aire < 0:
            contour = list(reversed(contour))
        ids = [mb.sv((p.x, p.y, z)) for p in contour]
        mb.face(ids, [(p.x / tuile, p.y / tuile) for p in contour], mi)
        me = mb.construire(nom)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
        return objet(nom, me, parent="parc_jardin")

    plan_contour("parc_bassin_fond", C, Z_BASSIN - 0.6, m_fond, 3.0)
    plan_contour("parc_bassin_eau", C, Z_BASSIN + 0.1, m_eau, 6.0)

    # Une seule fontaine, nettement plus haute, au centre du bassin (confirmation du propriétaire).
    def jet(nom, centre, h):
        mb = MB()
        mj = mb.mat(m_jet)
        c = Vector(centre)
        tour(mb, [(0.03, 0.0), (0.05, h * 0.3), (0.07, h * 0.7), (0.1, h * 0.92), (0.16, h), (0.24, h * 0.96),
                  (0.42, h * 0.75), (0.6, h * 0.4), (0.72, 0.05)], 12, mj, centre=c)
        tour(mb, [(0.0, 0.02), (0.55, 0.06), (0.95, 0.02)], 16, mj, centre=c)
        return objet(nom, mb.construire(nom), parent="parc_jardin")

    jet("parc_fontaine_jet", tuple(bassin_local(0.0, -1.2))[:2] + (Z_BASSIN + 0.1,), 4.4)

    # Presqu'île sablée au creux du haricot, bordée de pierres blanches (W05, W18)
    cpi = bassin_local(0.0, 5.6)
    pts_pi = [cpi + Vector((math.cos(a) * 3.0, math.sin(a) * 2.6, 0)).to_3d() for a in
              [2 * math.pi * k / 24 for k in range(24)]]
    pts_pi = [Vector((p.x, p.y, 0)) for p in pts_pi]
    plan_contour("parc_presquile", pts_pi, Z_BASSIN + 0.035, m_sable, 3.0)
    me_cail = None
    rnd = random.Random(8)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    for v in bm.verts:
        v.co *= 1 + 0.25 * bruit3(v.co, 1.5, 3)
        v.co.z *= 0.55
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for l in f.loops:
            l[uvl].uv = (l.vert.co.x * 0.5, l.vert.co.y * 0.5 + l.vert.co.z * 0.5)
    me_cail = bpy.data.meshes.new("parc_pierre_bordure")
    bm.to_mesh(me_cail)
    bm.free()
    me_cail.materials.append(m_pierre)
    for k, p in enumerate(pts_pi):
        objet(f"parc_pierre_presquile_{k:02d}", me_cail, (p.x, p.y, Z_BASSIN + 0.04), rnd.uniform(0, 6.3),
              (rnd.uniform(0.22, 0.32), rnd.uniform(0.18, 0.26), rnd.uniform(0.2, 0.3)))
    # Plaque de regard dans la pelouse (W05)
    mb = MB(lisse=False)
    boite(mb, -0.3, -0.3, 0.0, 0.3, 0.3, 0.04, mb.mat(m_regard), 1.6)
    objet("parc_regard", mb.construire("parc_regard"), (6.0, 66.0, H(6.0, 66.0) - 0.02), 0.2)

    # Mâts de drapeaux France et Europe (W03, W05, W18)
    def mat_drapeau(nom, base, drapeau_mat, phase):
        mb = MB()
        mm, md = mb.mat(m_mat_blanc), mb.mat(m_dore)
        Hm = 8.0
        tube(mb, [Vector((0, 0, -0.2)), Vector((0, 0, 0.4)), Vector((0, 0, Hm))], [0.075, 0.07, 0.04], 12, mm)
        tour(mb, [(0.0, Hm - 0.02), (0.06, Hm + 0.02), (0.085, Hm + 0.1), (0.06, Hm + 0.18), (0.0, Hm + 0.2)], 12, md)
        tour(mb, [(0.0, 0.0), (0.16, 0.0), (0.16, 0.25), (0.09, 0.32), (0.0, 0.32)], 12, mm)
        tube(mb, [Vector((0.06, 0, 1.2)), Vector((0.06, 0, Hm - 0.05))], [0.005, 0.005], 4, mm)
        objet(nom, mb.construire(nom), base, 0.0, parent="parc_jardin")
        mb = MB()
        mi = mb.mat(drapeau_mat)
        L, Hd, nu, nv = 1.5, 1.0, 16, 8
        grille_ = []
        for j in range(nv + 1):
            ligne = []
            for i in range(nu + 1):
                u, v = i / nu, j / nv
                # Le maillage reste neutre ici ; le vent est animé dans Unity pour toutes les vues.
                ligne.append(mb.sv((0.05 + u * L, 0.0, Hm - 0.15 - Hd + v * Hd - 0.04 * u * u)))
            grille_.append(ligne)
        for j in range(nv):
            for i in range(nu):
                mb.face((grille_[j][i], grille_[j][i + 1], grille_[j + 1][i + 1], grille_[j + 1][i]),
                        [(i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)],
                        mi)
        objet(nom + "_drapeau", mb.construire(nom + "_drapeau"), base, math.radians(-150), parent="parc_jardin")

    pf = bassin_local(-1.0, 5.2)
    pe = bassin_local(1.3, 6.4)
    mat_drapeau("parc_mat_france", (pf.x, pf.y, Z_BASSIN + 0.03), m_drap_fr, 0.0)
    mat_drapeau("parc_mat_europe", (pe.x, pe.y, Z_BASSIN + 0.03), m_drap_ue, 1.7)
    log("bassin et mâts")

    # --- Tennis : résine rouge, lignes, filet, grillage, mur bahut à balustres ----
    e = TEN_ENC
    zt = Z_TENNIS
    surface("parc_tennis_enceinte", [(e[0], e[1]), (e[2], e[1]), (e[2], e[3]), (e[0], e[3])], m_tennis, 4.0, dz=0.02,
            z_fixe=zt, pas_c=4.0, parent="parc_annexes")
    c = TEN_COURT
    surface("parc_tennis_court", [(c[0] - 0.5, c[1] - 0.5), (c[2] + 0.5, c[1] - 0.5), (c[2] + 0.5, c[3] + 0.5),
                                  (c[0] - 0.5, c[3] + 0.5)], m_tennis_court, 4.0, dz=0.025, z_fixe=zt, pas_c=6.0,
            parent="parc_annexes")
    mb = MB(lisse=False)
    ml = mb.mat(m_ligne)
    zl = zt + 0.03
    hx, hy = 10.97 / 2, 23.77 / 2
    sx = 8.23 / 2
    sy = 6.40

    def ligne(xa, ya, xb, yb, w=0.05):
        if abs(xa - xb) < 1e-6:
            q = [(xa - w / 2, ya), (xa + w / 2, ya), (xa + w / 2, yb), (xa - w / 2, yb)]
        else:
            q = [(xa, ya - w / 2), (xb, ya - w / 2), (xb, ya + w / 2), (xa, ya + w / 2)]
        ids = [mb.sv((TEN_CX + p[0], TEN_CY + p[1], zl)) for p in q]
        if (q[1][0] - q[0][0]) * (q[2][1] - q[1][1]) < 0:
            ids.reverse()
        mb.face(ids, [(0, 0), (1, 0), (1, 1), (0, 1)], ml)

    for xs_ in (-hx, hx, -sx, sx):
        ligne(xs_, -hy, xs_, hy)
    for ys_ in (-hy, hy):
        ligne(-hx, ys_, hx, ys_, 0.1)
        ligne(-0.05, ys_ * 0.996, 0.05, ys_ * 0.996, 0.1)
    for ys_ in (-sy, sy):
        ligne(-sx, ys_, sx, ys_)
    ligne(0, -sy, 0, sy)
    objet("parc_tennis_lignes", mb.construire("parc_tennis_lignes"), parent="parc_annexes")
    # Filet
    mb = MB(lisse=False)
    mf, mbn, mpo = mb.mat(m_filet), mb.mat(m_ligne), mb.mat(m_fer_vert)
    px_ = hx + 0.914
    for sgn in (-1, 1):
        tube(mb, [Vector((TEN_CX + sgn * px_, FILET_Y, zt)), Vector((TEN_CX + sgn * px_, FILET_Y, zt + 1.07))],
             [0.04, 0.04], 8, mpo, ferme_haut=True)
    nu = 12
    bas, haut_ = [], []
    for i in range(nu + 1):
        x = -px_ + 2 * px_ * i / nu
        ht = 0.914 + (1.07 - 0.914) * (abs(x) / px_) ** 2
        bas.append(mb.sv((TEN_CX + x, FILET_Y, zt + 0.05)))
        haut_.append((mb.sv((TEN_CX + x, FILET_Y, zt + ht - 0.06)), mb.sv((TEN_CX + x, FILET_Y, zt + ht)), ht))
    for i in range(nu):
        x0_, x1_ = -px_ + 2 * px_ * i / nu, -px_ + 2 * px_ * (i + 1) / nu
        mb.face((bas[i], bas[i + 1], haut_[i + 1][0], haut_[i][0]),
                [(x0_ / 0.1, 0), (x1_ / 0.1, 0), (x1_ / 0.1, haut_[i + 1][2] / 0.1), (x0_ / 0.1, haut_[i][2] / 0.1)], mf)
        mb.face((haut_[i][0], haut_[i + 1][0], haut_[i + 1][1], haut_[i][1]), [(0, 0), (1, 0), (1, 1), (0, 1)], mbn)
    sangle = [mb.sv((TEN_CX - 0.025, FILET_Y - 0.002, zt)), mb.sv((TEN_CX + 0.025, FILET_Y - 0.002, zt)),
              mb.sv((TEN_CX + 0.025, FILET_Y - 0.002, zt + 0.914)), mb.sv((TEN_CX - 0.025, FILET_Y - 0.002, zt + 0.914))]
    mb.face(sangle, [(0, 0), (1, 0), (1, 1), (0, 1)], mbn)
    me_f = mb.construire("parc_tennis_filet")
    objet("parc_tennis_filet", me_f, parent="parc_annexes")

    # Grillage vert (3,5 m) sur les côtés N, O, S ; mur bahut + balustrade côté château (est)
    def cloture(nom, pts2d, h, z_fn, ecart=2.5, parent="parc_annexes", lisse_haut=True):
        mb = MB(lisse=False)
        mg, mp_ = mb.mat(m_grillage), mb.mat(m_fer_vert)
        pts = [Vector((p[0], p[1], 0)) for p in pts2d]
        poteaux = []
        s_tot = 0.0
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            L = (b - a).length
            n_ = max(1, int(math.ceil(L / ecart)))
            for i in range(n_):
                poteaux.append((a.lerp(b, i / n_), s_tot + L * i / n_))
            s_tot += L
        poteaux.append((pts[-1], s_tot))
        for k, (p, s) in enumerate(poteaux):
            z = z_fn(p.x, p.y)
            tube(mb, [Vector((p.x, p.y, z - 0.2)), Vector((p.x, p.y, z + h))], [0.03, 0.03], 6, mp_, ferme_haut=True)
            if k:
                q, sq = poteaux[k - 1]
                zq = z_fn(q.x, q.y)
                ids = [mb.sv((q.x, q.y, zq + 0.02)), mb.sv((p.x, p.y, z + 0.02)), mb.sv((p.x, p.y, z + h)),
                       mb.sv((q.x, q.y, zq + h))]
                mb.face(ids, [(sq / 0.12, 0), (s / 0.12, 0), (s / 0.12, h / 0.12), (sq / 0.12, h / 0.12)], mg)
                if lisse_haut:
                    tube(mb, [Vector((q.x, q.y, zq + h - 0.03)), Vector((p.x, p.y, z + h - 0.03))], [0.02, 0.02], 5,
                         mp_)
        return objet(nom, mb.construire(nom), parent=parent)

    # Pas de grillage autour du tennis (demande du 18/11)
    log("tennis")

    # --- Voitures (parking nord, allée NE) ---------------------------------------
    m_vitre = materiau("parc_vitre_auto", couleur=(0.03, 0.04, 0.05), rugosite=0.05, metal=0.2)
    m_pneu = materiau("parc_pneu", couleur=(0.03, 0.03, 0.03), rugosite=0.85)
    m_jante = materiau("parc_jante", couleur=(0.55, 0.56, 0.58), rugosite=0.3, metal=1.0)
    m_phare = materiau("parc_phare", couleur=(0.95, 0.95, 0.9), rugosite=0.1, emission=(0.3, 0.3, 0.28))
    m_feu = materiau("parc_feu_arriere", couleur=(0.6, 0.02, 0.02), rugosite=0.2)
    # Deux voitures seulement (demande du 17/11) : Citroën C5 Aircross, noire et blanche à toit noir
    # (scripts/composants/voiture_c5.py). Places relevées sur l'orthophoto IGN (cour nord, flanc est).
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import voiture_c5
    m_c5 = {k: materiau(f"parc_c5_{k}", **v) for k, v in voiture_c5.MATIERES.items()}
    voitures = {}
    for nom in ("noir", "blanc"):
        m_c5["carrosserie"] = materiau(f"parc_carrosserie_{nom}", **voiture_c5.CARROSSERIES[nom])
        voitures[nom] = voiture_c5.construire(f"parc_voiture_{nom}", m_c5)
    for k, (nom, x, y, a) in enumerate([("noir", 10.5, -23.5, math.radians(92)), ("blanc", 24.6, 5.0, math.radians(180))]):
        objet(f"parc_voiture_{k:02d}", voitures[nom], (x, y, H(x, y) + 0.01 if y > 0 else Z_COUR_NORD + 0.01), a,
              parent="parc_annexes")
    log("voitures")
    # Vélo cargo longtail (scripts/composants/velo_cargo.py) contre la façade nord, côté est du perron, le long
    # de l'échiffre, avant vers le nord (demande du 19/11, château recalé : façade y -8,7, perron jusqu'à -12,87).
    # Pièces séparées pour le rendre pilotable : cadre, direction (roue avant en enfant), roue arrière.
    import velo_cargo
    m_velo = {k: materiau(f"parc_velo_{k}", **v) for k, v in velo_cargo.MATIERES.items()}
    velo = bpy.data.objects.new("parc_velo_cargo", None)
    velo.location = (3.75, -10.75, Z_COUR_NORD + 0.01)
    COLL.objects.link(velo)
    velo.parent = groupe("parc_annexes")
    pieces = {}
    for cle, (me_v, origine) in velo_cargo.construire("parc_velo_cargo", m_velo).items():
        o = objet(f"parc_velo_cargo_{cle}", me_v, origine)
        o.parent = pieces["direction"] if cle == "roue_avant" else velo
        pieces[cle] = o
    log("vélo cargo")


    # --- Haies taillées et clôtures de limite ---------------------------------
    def haie(nom, pts2d, larg, haut, mat, parent="parc_vegetation", graine=0):
        pts, L = reechantillonner(catmull(pts2d, pas=8) if len(pts2d) > 2 else
                                  [Vector((p[0], p[1], 0)) for p in pts2d], 1.0)
        T = tangentes(pts)
        mb = MB()
        mi = mb.mat(mat)
        prof = [(-0.5, -0.15), (-0.5, 0.75), (-0.42, 0.95), (-0.2, 1.0), (0.2, 1.0), (0.42, 0.95), (0.5, 0.75),
                (0.5, -0.15)]
        anneaux = []
        s = 0.0
        for k, p in enumerate(pts):
            if k:
                s += (p - pts[k - 1]).length
            g = Vector((-T[k].y, T[k].x, 0))
            zb = H(p.x, p.y)
            ids = []
            for o, z in prof:
                bb = 1 + 0.08 * bruit3((p.x, p.y, z), 0.7, graine)
                q = p + g * o * larg * bb
                nrm = (g * o * 2 + Vector((0, 0, max(z - 0.6, 0) * 2))).normalized()
                ids.append(mb.sv((q.x, q.y, zb + z * haut * (1 + 0.04 * bruit3((p.x, p.y, 1), 0.5, graine))), nrm))
            anneaux.append((ids, s))
        for k in range(len(anneaux) - 1):
            (a, sa), (b, sb) = anneaux[k], anneaux[k + 1]
            for i in range(len(prof) - 1):
                va = i * 0.6
                mb.face((a[i + 1], a[i], b[i], b[i + 1]),
                        [(sa / 2, va + 0.6), (sa / 2, va), (sb / 2, va), (sb / 2, va + 0.6)], mi)
        return objet(nom, mb.construire(nom), parent=parent)

    # --- Limite de propriété : mur sur la route, grillage et haie ailleurs, portails -----
    m_enduit = materiau("parc_enduit_mur", TX["enduit"], couleur=(0.96, 0.94, 0.89), rugosite=0.9)
    m_couvert = materiau("parc_couvertine", TX["pierre"], couleur=(0.92, 0.9, 0.86), rugosite=0.8)
    PORTAILS = [PLAN["portail"], PLAN["portail_nord"]]

    def pres_portail(x, y, marge=0.8):
        return any(math.hypot(x - p["centre"][0], y - p["centre"][1]) < p["largeur"] / 2 + marge for p in PORTAILS)

    def troncons(poly, pas, garder, ferme=True):
        """Découpe une polyligne en tronçons échantillonnés où garder(x, y) est vrai."""
        runs, cur = [], []
        n = len(poly) if ferme else len(poly) - 1
        for k in range(n):
            a, b = Vector((*poly[k], 0)), Vector((*poly[(k + 1) % len(poly)], 0))
            m = max(1, int(math.ceil((b - a).length / pas)))
            for i in range(m + (1 if k == n - 1 else 0)):
                q = a.lerp(b, i / m)
                if garder(q.x, q.y):
                    cur.append((q.x, q.y))
                elif cur:
                    runs.append(cur)
                    cur = []
        if cur:
            runs.append(cur)
        return [r for r in runs if len(r) > 1]

    # Côtés sur la voie publique (avenue à l'est, route au sud) : mur enduit de 2,1 m à couvertine.
    I_ROUTE = range(12, 21)
    mb = MB(lisse=False)
    me_, mc_ = mb.mat(m_enduit), mb.mat(m_couvert)
    murs_route = []
    for k in I_ROUTE:
        murs_route += troncons([LIMITE[k], LIMITE[k + 1]], 1.5, lambda x, y: not pres_portail(x, y, 0.45), ferme=False)
    for run in murs_route:
        for a, b in zip(run, run[1:]):
            za, zb_ = H(*a), H(*b)
            pave(mb, a, b, 0.32, (za - 0.4, zb_ - 0.4), (za + 2.1, zb_ + 2.1), me_, 0.5)
            pave(mb, a, b, 0.42, (za + 2.1, zb_ + 2.1), (za + 2.2, zb_ + 2.2), mc_, 1.0)
    objet("parc_mur_cloture_route", mb.construire("parc_mur_cloture_route"), parent="parc_jardin")
    # Ailleurs : grillage vert de 1,8 m sur la limite, doublé d'une haie taillée côté jardin.
    zf = lambda x, y: H(x, y)
    i_route = set(I_ROUTE)
    k_run = 0
    for k in range(len(LIMITE)):
        if k in i_route:
            continue
        for run in troncons([LIMITE[k], LIMITE[(k + 1) % len(LIMITE)]], 2.5, lambda x, y: not pres_portail(x, y, 0.45),
                            ferme=False):
            cloture(f"parc_cloture_limite_{k_run:02d}", run, 1.8, zf, parent="parc_jardin")
            k_run += 1
    HAIE = decaler_poly(LIMITE, 1.3)
    for k_run, run in enumerate(troncons(HAIE, 1.0, lambda x, y: dist_allee(x, y) > 0.6 and not pres_portail(x, y, 1.6)
                                         and not any(pip(x, y, b) for b in BATIMENTS))):
        haie(f"parc_haie_limite_{k_run:02d}", run, 1.3, 2.5, m_haie, graine=k_run)
    log("limite de propriété")

    # --- Portails : grille en fer noir entre piliers, murs courbes blancs (vues Google 9-10) ---------
    def portail(nom, P_, courbes):
        c, w, a = Vector((*P_["centre"], 0)), P_["largeur"], math.radians(P_["angle_deg"])
        u = Vector((math.cos(a), math.sin(a), 0))
        v = Vector((-u.y, u.x, 0))
        z0 = H(c.x, c.y)
        mb = MB(lisse=False)
        mp_, me2, mc2 = mb.mat(m_pierre), mb.mat(m_enduit), mb.mat(m_couvert)
        for sx in (-1, 1):
            q = c + u * sx * (w / 2 + 0.35)
            boite(mb, q.x - 0.35, q.y - 0.35, z0 - 0.4, q.x + 0.35, q.y + 0.35, z0 + 2.65, mp_, 1.0)
            boite(mb, q.x - 0.43, q.y - 0.43, z0 + 2.65, q.x + 0.43, q.y + 0.43, z0 + 2.8, mp_, 1.0)
            tour(mb, [(0.0, 0.0), (0.12, 0.02), (0.2, 0.12), (0.22, 0.24), (0.17, 0.36), (0.06, 0.42), (0.0, 0.43)], 12,
                 mp_, centre=(q.x, q.y, z0 + 2.8))
            if courbes:
                # quart de cercle évasé vers la route (côté -v), hauteur 2,0 → 1,2 m
                R = 3.6
                cc = c + u * sx * (w / 2 + 0.7 + R)
                pts = []
                for i in range(9):
                    th = math.pi + sx * 0 + (math.pi / 2) * i / 8
                    d = Vector((math.cos(th), math.sin(th), 0))
                    # repère local : d.x le long de u (vers l'extérieur pour sx), d.y vers -v
                    pts.append(cc + u * (d.x * sx) * R - v * (-d.y) * R)
                for i in range(8):
                    pa, pb = pts[i], pts[i + 1]
                    ha, hb = 2.0 - 0.8 * i / 8, 2.0 - 0.8 * (i + 1) / 8
                    za, zb_ = H(pa.x, pa.y), H(pb.x, pb.y)
                    pave(mb, pa[:2], pb[:2], 0.3, (za - 0.4, zb_ - 0.4), (za + ha, zb_ + hb), me2, 0.5)
                    pave(mb, pa[:2], pb[:2], 0.4, (za + ha, zb_ + hb), (za + ha + 0.1, zb_ + hb + 0.1), mc2, 1.0)
        objet(f"{nom}_piliers", mb.construire(f"{nom}_piliers"), parent="parc_jardin")
        # Vantaux : origine sur l'axe des gonds, vantail fermé le long de u, ouverture vers l'intérieur (+v).
        for sx, cote in ((-1, "g"), (1, "d")):
            mb = MB(lisse=False)
            mf = mb.mat(m_fer_noir)
            L = w / 2 - 0.03
            sgn = -sx                       # du gond vers le milieu
            def bx(x0, x1, z0_, z1_, e=0.035):
                xa, xb = sorted((x0 * sgn, x1 * sgn))
                boite(mb, xa, -e, z0_, xb, e, z1_, mf)
            bx(0.0, 0.07, 0.05, 2.35)
            bx(L - 0.06, L, 0.05, 2.25)
            for zr in (0.12, 0.95, 2.05):
                bx(0.0, L, zr, zr + 0.06)
            n_b = int(L / 0.13)
            for i in range(1, n_b):
                xb_ = L * i / n_b
                h_b = 2.15 + 0.18 * math.sin(math.pi * i / n_b) if sx < 0 else 2.15 + 0.18 * math.sin(math.pi * (n_b - i) / n_b)
                bx(xb_ - 0.012, xb_ + 0.012, 0.12, h_b, 0.012)
                tour(mb, [(0.0, 0.0), (0.03, 0.0), (0.0, 0.12)], 4, mf, centre=(xb_ * sgn, 0, h_b))
            for i in range(1, 4):
                xc = L * (i - 0.5) / 3
                for k in range(10):
                    t0, t1 = 2 * math.pi * k / 10, 2 * math.pi * (k + 1) / 10
                    pa = Vector((xc * sgn + math.cos(t0) * 0.2, 0, 0.53 + math.sin(t0) * 0.2))
                    pb = Vector((xc * sgn + math.cos(t1) * 0.2, 0, 0.53 + math.sin(t1) * 0.2))
                    tube(mb, [pa, pb], [0.012, 0.012], 4, mf)
            gond = c + u * sx * (w / 2)
            objet(f"{nom}_vantail_{cote}", mb.construire(f"{nom}_vantail_{cote}"), (gond.x, gond.y, z0), a,
                  parent="parc_jardin")

    portail("parc_portail", PLAN["portail"], True)
    portail("parc_portail_nord", PLAN["portail_nord"], False)
    log("portails")

    # --- Plateforme ouest : murs de soutènement à parapet, escaliers vers les cours ---------------
    mb = MB(lisse=False)
    mp_ = mb.mat(m_pierre)
    ouvertures = [(Vector((*es["haut"], 0)), es["largeur"] / 2 + 0.05) for es in ESC_TENNIS]
    bords = [((-16.3, -24.0), (-16.3, -9.45), 1), ((-19.5, 7.6), (-38.0, 7.6), 1)]
    for a, b, _ in bords:
        for run in troncons([a, b], 0.5, lambda x, y: all((Vector((x, y, 0)) - o).length > r for o, r in ouvertures),
                            ferme=False):
            p0, p1 = run[0], run[-1]
            d = (Vector((*p1, 0)) - Vector((*p0, 0))).normalized()
            ext = Vector((d.y, -d.x, 0))      # côté bas (cour)
            if pip(*(Vector((*p0, 0)) + d * 0.2 + ext * 1.0)[:2], PLATEFORME):
                ext = -ext
            for qa, qb in zip(run, run[1:]):
                za = H(*(Vector((*qa, 0)) + ext * 0.8)[:2])
                zb_ = H(*(Vector((*qb, 0)) + ext * 0.8)[:2])
                qa_, qb_ = Vector((*qa, 0)) - ext * 0.22, Vector((*qb, 0)) - ext * 0.22
                pave(mb, qa_[:2], qb_[:2], 0.44, (za - 0.4, zb_ - 0.4), (Z_PLAT + 0.5, Z_PLAT + 0.5), mp_, 0.5)
                pave(mb, qa_[:2], qb_[:2], 0.56, (Z_PLAT + 0.5, Z_PLAT + 0.5), (Z_PLAT + 0.6, Z_PLAT + 0.6), mp_, 1.0)
    objet("parc_plateforme_murs", mb.construire("parc_plateforme_murs"), parent="parc_annexes")
    for es in ESC_TENNIS:
        a, b = Vector((*es["haut"], 0)), Vector((*es["bas"], 0))
        t = (b - a).normalized()
        n_ = Vector((-t.y, t.x, 0))
        L = (b - a).length
        N = es["marches"]
        zb_ = H(b.x + t.x * 0.6, b.y + t.y * 0.6)
        h_m = (es["z_haut"] - zb_) / N
        g = L / (N - 1)
        mb = MB(lisse=False)
        mm_ = mb.mat(m_pierre)
        hl = es["largeur"] / 2
        for k in range(1, N):
            ztop = es["z_haut"] - k * h_m
            q0, q1 = a + t * (g * (k - 1)), a + t * (g * k)
            pave(mb, q0[:2], q1[:2], 2 * hl, (zb_ - 0.3, zb_ - 0.3), (ztop, ztop), mm_, 1.0)
        # échiffres rampants à couvertine
        for sx in (-1, 1):
            o = n_ * sx * (hl + 0.18)
            pa, pb = a + o - t * 0.25, b + o + t * 0.15
            pave(mb, pa[:2], pb[:2], 0.36, (zb_ - 0.4, zb_ - 0.4), (es["z_haut"] + 0.6, zb_ + 0.5), mm_, 0.5)
        objet(f"parc_escalier_tennis_{es['nom']}", mb.construire(f"parc_escalier_tennis_{es['nom']}"),
              parent="parc_annexes")
    log("plateforme et escaliers du tennis")

    # --- Maison du gardien (plain-pied, toit plat, menuiseries rouges) ---------------------------
    m_vitre_b = materiau("parc_vitrage_maison", couleur=(0.05, 0.07, 0.09), rugosite=0.05, metal=0.3)
    m_rouge = materiau("parc_menuiserie_rouge", couleur=(0.5, 0.06, 0.05), rugosite=0.5)
    m_alu = materiau("parc_menuiserie_alu", couleur=(0.75, 0.76, 0.77), rugosite=0.35, metal=0.7)
    m_bois = materiau("parc_bois", TX["ecorce"], couleur=(0.95, 0.75, 0.55), rugosite=0.8)
    m_beton = materiau("parc_beton", TX["enduit"], couleur=(0.62, 0.62, 0.6), rugosite=0.95)
    m_toit_plat = materiau("parc_toit_plat", TX["gravier"], couleur=(0.7, 0.7, 0.68), rugosite=1.0)

    def maison(nom, cle, h, ouvertures, mat_cadre, motif_toit=False):
        """Bâtiment à toit plat : ouvertures = {côté: [(centre, largeur, bas, haut, porte?)]}, côtés s/n/e/o."""
        P_ = PLAN[cle]
        W, D = P_["dimensions"]
        z0 = Z_PAD[cle]
        mb = MB(lisse=False)
        mw, mv, mc3, mt, mbt = mb.mat(m_enduit), mb.mat(m_vitre_b), mb.mat(mat_cadre), mb.mat(m_toit_plat), mb.mat(m_beton)
        ep = 0.25
        boite(mb, -W / 2 - 0.1, -D / 2 - 0.1, -1.2, W / 2 + 0.1, D / 2 + 0.1, 0.15, mbt, 1.0)
        boite(mb, -W / 2 + ep, -D / 2 + ep, 0.15, W / 2 - ep, D / 2 - ep, 0.17, mbt, 1.0)
        portes = []
        # côtés : (axe, coordonnée fixe, longueur, sens extérieur)
        cotes = {"s": ("x", D / 2, W, 1), "n": ("x", -D / 2, W, -1), "e": ("y", W / 2, D, 1), "o": ("y", -W / 2, D, -1)}
        for cote, (axe, fixe, Lc, sg) in cotes.items():
            ops = sorted(ouvertures.get(cote, []))
            bornes = [-Lc / 2]
            for (cx_, lw, zb2, zh2, porte) in ops:
                bornes += [cx_ - lw / 2, cx_ + lw / 2]
            bornes.append(Lc / 2)
            def bloc(u0, u1, za, zb3, mi):
                f0, f1 = (fixe - ep, fixe) if sg > 0 else (fixe, fixe + ep)
                if axe == "x":
                    boite(mb, u0, f0, za, u1, f1, zb3, mi, 0.5)
                else:
                    boite(mb, f0, u0, za, f1, u1, zb3, mi, 0.5)
            for i in range(0, len(bornes), 2):
                if bornes[i + 1] > bornes[i] + 1e-3:
                    bloc(bornes[i], bornes[i + 1], 0.15, h, mw)
            for (cx_, lw, zb2, zh2, porte) in ops:
                bloc(cx_ - lw / 2, cx_ + lw / 2, 0.15, zb2, mw)
                bloc(cx_ - lw / 2, cx_ + lw / 2, zh2, h, mw)
                # cadre + vitrage (ou porte séparée, animable)
                f_ext = fixe - 0.06 * sg
                for (u0, u1, za, zb3) in [(cx_ - lw / 2, cx_ - lw / 2 + 0.07, zb2, zh2), (cx_ + lw / 2 - 0.07, cx_ + lw / 2, zb2, zh2),
                                          (cx_ - lw / 2, cx_ + lw / 2, zh2 - 0.07, zh2), (cx_ - lw / 2, cx_ + lw / 2, zb2, zb2 + 0.06)]:
                    if axe == "x":
                        boite(mb, u0, f_ext - 0.04, za, u1, f_ext + 0.04, zb3, mc3)
                    else:
                        boite(mb, f_ext - 0.04, u0, za, f_ext + 0.04, u1, zb3, mc3)
                if porte:
                    portes.append((axe, f_ext, cx_, lw, zb2, zh2, sg))
                else:
                    if axe == "x":
                        boite(mb, cx_ - lw / 2 + 0.07, f_ext - 0.01, zb2 + 0.06, cx_ + lw / 2 - 0.07, f_ext + 0.01, zh2 - 0.07, mv)
                        boite(mb, cx_ - 0.03, f_ext - 0.03, zb2 + 0.06, cx_ + 0.03, f_ext + 0.03, zh2 - 0.07, mc3)
                    else:
                        boite(mb, f_ext - 0.01, cx_ - lw / 2 + 0.07, zb2 + 0.06, f_ext + 0.01, cx_ + lw / 2 - 0.07, zh2 - 0.07, mv)
                        boite(mb, f_ext - 0.03, cx_ - 0.03, zb2 + 0.06, f_ext + 0.03, cx_ + 0.03, zh2 - 0.07, mc3)
        # plafond / toit plat, acrotère
        boite(mb, -W / 2, -D / 2, h, W / 2, D / 2, h + 0.25, mt, 0.5)
        for (x0, y0, x1, y1) in [(-W / 2, -D / 2, W / 2, -D / 2 + 0.2), (-W / 2, D / 2 - 0.2, W / 2, D / 2),
                                 (-W / 2, -D / 2, -W / 2 + 0.2, D / 2), (W / 2 - 0.2, -D / 2, W / 2, D / 2)]:
            boite(mb, x0 - 0.03, y0 - 0.03, h + 0.25, x1 + 0.03, y1 + 0.03, h + 0.62, mw, 0.5)
        if motif_toit:
            mr = mb.mat(m_regard)
            for R in (2.6, 1.9, 1.2, 0.5):
                for k in range(40):
                    t0, t1 = 2 * math.pi * k / 40, 2 * math.pi * (k + 1) / 40
                    tube(mb, [Vector((math.cos(t0) * R, math.sin(t0) * R, h + 0.27)),
                              Vector((math.cos(t1) * R, math.sin(t1) * R, h + 0.27))], [0.04, 0.04], 4, mr)
        c = P_["centre"]
        a = math.radians(P_["angle_deg"])
        objet(nom, mb.construire(nom), (c[0], c[1], z0), a, parent="parc_annexes")
        # portes animables : origine sur le gond (côté gauche vu de l'extérieur)
        for k, (axe, f_ext, cx_, lw, zb2, zh2, sg) in enumerate(portes):
            mb = MB(lisse=False)
            mp2, mv2 = mb.mat(mat_cadre), mb.mat(m_vitre_b)
            L = lw - 0.14
            boite(mb, 0.0, -0.025, 0.0, L, 0.025, zh2 - zb2 - 0.1, mp2)
            boite(mb, 0.15, -0.03, 1.15, L - 0.15, 0.03, zh2 - zb2 - 0.3, mv2)
            boite(mb, L - 0.14, -0.08, 1.0, L - 0.1, 0.08, 1.04, mb.mat(m_alu))
            if axe == "x":
                gl = Vector((cx_ - lw / 2 + 0.07, f_ext, zb2 + 0.02))
                rot = 0.0
            else:
                gl = Vector((f_ext, cx_ - lw / 2 + 0.07, zb2 + 0.02))
                rot = math.pi / 2
            gw = Matrix.Rotation(a, 4, "Z") @ gl
            objet(f"{nom}_porte" + (f"_{k}" if k else ""), mb.construire(f"{nom}_porte_{k}"),
                  (c[0] + gw.x, c[1] + gw.y, z0 + gw.z), a + rot, parent="parc_annexes")

    maison("parc_maison_gardien", "gardien", 3.1,
           {"s": [(0.0, 1.0, 0.15, 2.3, True), (-2.8, 1.6, 0.9, 2.3, False), (2.8, 1.6, 0.9, 2.3, False)],
            "o": [(-5.0, 2.6, 0.5, 2.4, False), (-1.8, 2.6, 0.5, 2.4, False), (1.4, 2.6, 0.5, 2.4, False),
                  (4.6, 2.0, 0.9, 2.3, False)],
            "e": [(-3.5, 1.2, 0.9, 2.2, False), (3.5, 1.2, 0.9, 2.2, False)],
            "n": [(2.0, 0.9, 0.15, 2.2, True), (-2.2, 1.2, 1.2, 2.2, False)]}, m_rouge)
    maison("parc_local_piscine", "local_piscine", 2.6,
           {"n": [(-2.5, 1.0, 0.15, 2.2, True), (1.5, 1.4, 1.1, 2.0, False)],
            "e": [(0.0, 1.0, 1.2, 2.0, False)]}, m_alu, motif_toit=True)
    # boîte aux lettres et banc devant la maison du gardien
    mb = MB(lisse=False)
    boite(mb, -0.2, -0.15, 0.9, 0.2, 0.15, 1.3, mb.mat(m_fer_vert))
    boite(mb, -0.03, -0.03, 0.0, 0.03, 0.03, 0.9, mb.mat(m_fer_noir))
    pb_ = Vector((*PLAN["gardien"]["centre"], 0)) + Matrix.Rotation(math.radians(PLAN["gardien"]["angle_deg"]), 4, "Z") @ Vector((3.0, 8.6, 0))
    objet("parc_gardien_boite_lettres", mb.construire("parc_gardien_boite_lettres"), (pb_.x, pb_.y, H(pb_.x, pb_.y)),
          math.radians(PLAN["gardien"]["angle_deg"]), parent="parc_annexes")
    log("maison du gardien et local piscine")

    # --- Pétanque derrière la maison du gardien --------------------------------------------------
    P_ = PLAN["petanque"]
    W, D = P_["dimensions"]
    zp = Z_PAD["petanque"]
    m_terrain_p = materiau("parc_terrain_petanque", TX["sable"], couleur=(1.05, 0.95, 0.82), nor=ph("sandy_gravel", "nor_gl"))
    mb = MB(lisse=False)
    mt_, mbo, mfe, mcb = mb.mat(m_terrain_p), mb.mat(m_bois), mb.mat(m_jante), mb.mat(materiau("parc_cochonnet", couleur=(0.8, 0.55, 0.1)))
    boite(mb, -W / 2, -D / 2, -0.3, W / 2, D / 2, 0.04, mt_, 0.5)
    for (x0, y0, x1, y1) in [(-W / 2 - 0.08, -D / 2 - 0.08, W / 2 + 0.08, -D / 2), (-W / 2 - 0.08, D / 2, W / 2 + 0.08, D / 2 + 0.08),
                             (-W / 2 - 0.08, -D / 2, -W / 2, D / 2), (W / 2, -D / 2, W / 2 + 0.08, D / 2)]:
        boite(mb, x0, y0, -0.2, x1, y1, 0.16, mbo, 2.0)
    rp = random.Random(4)
    for k in range(7):
        x, y = rp.uniform(-1.2, 1.2), rp.uniform(2.5, 4.8)
        r_ = 0.0375 if k else 0.015
        tour(mb, [(0.0, 0.0)] + [(r_ * math.sin(math.pi * i / 6), r_ - r_ * math.cos(math.pi * i / 6)) for i in range(1, 6)] + [(0.0, 2 * r_)],
             10, mfe if k else mcb, centre=(x, y, 0.04))
    # banc en bois le long du terrain
    boite(mb, W / 2 + 0.6, -1.0, 0.42, W / 2 + 1.0, 1.0, 0.47, mbo, 2.0)
    for yy in (-0.85, 0.85):
        boite(mb, W / 2 + 0.65, yy - 0.04, 0.0, W / 2 + 0.95, yy + 0.04, 0.42, mbo, 2.0)
    objet("parc_petanque", mb.construire("parc_petanque"), (P_["centre"][0], P_["centre"][1], zp),
          math.radians(P_["angle_deg"]), parent="parc_annexes")
    log("pétanque")

    # --- Grange du jardinier : tôle ondulée rouge, tracteur tondeuse, outils ----------------------
    P_ = PLAN["grange"]
    W, D = P_["dimensions"]
    zg = Z_PAD["grange"]
    hg = P_["hauteur"]
    m_tole = materiau("parc_tole_rouge", couleur=(0.52, 0.12, 0.08), rugosite=0.45, metal=0.5, double=True)
    m_parpaing = materiau("parc_parpaing", TX["enduit"], couleur=(0.78, 0.76, 0.72), rugosite=0.95)
    mb = MB(lisse=False)
    mpp, mto, mbo, mbt = mb.mat(m_parpaing), mb.mat(m_tole), mb.mat(m_bois), mb.mat(m_beton)
    boite(mb, -W / 2, -D / 2, -0.8, W / 2, D / 2, 0.1, mbt, 0.5)
    h_arr, h_av = hg - 0.6, hg            # pente vers l'arrière (est), façade ouverte à l'ouest (-x)
    boite(mb, W / 2 - 0.2, -D / 2, 0.1, W / 2, D / 2, h_arr, mpp, 0.5)
    for sy in (-1, 1):
        y0 = D / 2 - 0.2 if sy > 0 else -D / 2
        # pignon en trapèze
        ids = [mb.sv((-W / 2, y0, 0.1)), mb.sv((W / 2, y0, 0.1)), mb.sv((W / 2, y0, h_arr)), mb.sv((-W / 2, y0, h_av))]
        ids2 = [mb.sv((-W / 2, y0 + 0.2, 0.1)), mb.sv((W / 2, y0 + 0.2, 0.1)), mb.sv((W / 2, y0 + 0.2, h_arr)), mb.sv((-W / 2, y0 + 0.2, h_av))]
        mb.face(ids[::-1], [(0, 0), (0, 1), (1, 1), (1, 0)], mpp)
        mb.face(ids2, [(0, 0), (1, 0), (1, 1), (0, 1)], mpp)
        mb.face([ids[0], ids[3], ids2[3], ids2[0]], [(0, 0), (1, 0), (1, 1), (0, 1)], mpp)
        mb.face([ids[3], ids[2], ids2[2], ids2[3]], [(0, 0), (1, 0), (1, 1), (0, 1)], mpp)
    for yy in (-D / 6, D / 6):
        boite(mb, -W / 2 + 0.05, yy - 0.08, 0.1, -W / 2 + 0.21, yy + 0.08, h_av, mbo, 1.0)
    # tôle ondulée : ondes dans le sens de la pente
    nx_, ny_ = 2, int((D + 0.6) / 0.0475)
    grille = []
    for i in range(nx_ + 1):
        xr = -W / 2 - 0.3 + (W + 0.5) * i / nx_
        zr = h_av + 0.05 + (h_arr - h_av) * (xr + W / 2) / W
        ligne = []
        for j in range(ny_ + 1):
            yr = -D / 2 - 0.3 + (D + 0.6) * j / ny_
            ligne.append(mb.sv((xr, yr, zr + 0.025 * math.sin(2 * math.pi * j / 4))))
        grille.append(ligne)
    for i in range(nx_):
        for j in range(ny_):
            mb.face((grille[i][j], grille[i + 1][j], grille[i + 1][j + 1], grille[i][j + 1]),
                    [(i * 3.0, j * 0.05), ((i + 1) * 3.0, j * 0.05), ((i + 1) * 3.0, (j + 1) * 0.05), (i * 3.0, (j + 1) * 0.05)], mto)
    # établi et râtelier d'outils sur le mur du fond
    boite(mb, W / 2 - 0.9, -D / 2 + 0.3, 0.9, W / 2 - 0.2, -D / 2 + 2.6, 0.95, mbo, 1.0)
    for yy in (-D / 2 + 0.35, -D / 2 + 2.55):
        boite(mb, W / 2 - 0.85, yy - 0.04, 0.1, W / 2 - 0.77, yy + 0.04, 0.9, mbo, 1.0)
    boite(mb, W / 2 - 0.26, -0.5, 1.5, W / 2 - 0.2, 3.5, 1.62, mbo, 1.0)
    mfe = mb.mat(m_jante)
    for k, (yy, tete) in enumerate([(-0.3, "pelle"), (0.3, "rateau"), (0.9, "beche"), (1.5, "fourche"), (2.1, "balai"),
                                    (2.7, "binette"), (3.3, "rateau")]):
        x_ = W / 2 - 0.32
        tube(mb, [Vector((x_, yy, 0.25)), Vector((x_, yy, 1.62))], [0.018, 0.018], 6, mbo)
        if tete == "rateau":
            boite(mb, x_ - 0.03, yy - 0.22, 0.2, x_ + 0.03, yy + 0.22, 0.24, mfe)
            for d_ in range(-5, 6):
                boite(mb, x_ - 0.008, yy + d_ * 0.04 - 0.006, 0.12, x_ + 0.008, yy + d_ * 0.04 + 0.006, 0.2, mfe)
        elif tete == "balai":
            boite(mb, x_ - 0.04, yy - 0.2, 0.05, x_ + 0.04, yy + 0.2, 0.25, mb.mat(materiau("parc_poils_balai", couleur=(0.25, 0.18, 0.1))))
        else:
            boite(mb, x_ - 0.01, yy - 0.11, 0.0, x_ + 0.01, yy + 0.11, 0.28, mfe)
    objet("parc_grange_jardinier", mb.construire("parc_grange_jardinier"), (P_["centre"][0], P_["centre"][1], zg),
          math.radians(P_["angle_deg"]), parent="parc_annexes")
    # tracteur tondeuse (sorti à moitié de la grange, capot vers l'ouest)
    m_vert_tt = materiau("parc_tondeuse_vert", couleur=(0.08, 0.32, 0.1), rugosite=0.35, metal=0.2)
    m_jaune = materiau("parc_tondeuse_jaune", couleur=(0.85, 0.65, 0.05), rugosite=0.4)
    mb = MB(lisse=False)
    mv_, mj_, mn_, mpn = mb.mat(m_vert_tt), mb.mat(m_jaune), mb.mat(m_fer_noir), mb.mat(m_pneu)
    boite(mb, -0.75, -0.42, 0.28, 0.65, 0.42, 0.55, mv_)                      # châssis
    prisme(mb, [(-0.05, 0.55), (-0.85, 0.55), (-0.95, 0.42), (-0.95, 0.3), (-0.75, 0.28), (-0.05, 0.28)], -0.36, 0.36, mv_, mv_)
    boite(mb, -0.55, -0.6, 0.12, 0.25, 0.6, 0.22, mn_)                        # plateau de coupe
    boite(mb, 0.15, -0.25, 0.6, 0.55, 0.25, 0.68, mn_)                        # siège
    boite(mb, 0.5, -0.25, 0.68, 0.58, 0.25, 1.0, mn_)
    tube(mb, [Vector((-0.25, 0, 0.55)), Vector((-0.1, 0, 0.95))], [0.025, 0.025], 6, mn_)
    for k in range(12):
        t0, t1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
        tube(mb, [Vector((-0.1 + math.cos(t0) * 0.03, math.sin(t0) * 0.18, 0.95 + math.cos(t0) * 0.17)),
                  Vector((-0.1 + math.cos(t1) * 0.03, math.sin(t1) * 0.18, 0.95 + math.cos(t1) * 0.17))], [0.015, 0.015], 4, mn_)
    for (xw, rw) in ((-0.7, 0.18), (0.45, 0.27)):
        for sy in (-1, 1):
            nv0 = len(mb.v)
            tour(mb, [(0.0, -0.1), (rw * 0.6, -0.1), (rw, -0.08), (rw, 0.08), (rw * 0.6, 0.1), (0.0, 0.1)], 14, mpn)
            # tour() est vertical : on couche la roue (axe z → axe y)
            for i in range(nv0, len(mb.v)):
                x, y, z = mb.v[i]
                mb.v[i] = (xw + x, sy * 0.48 + z, rw + y)
            boite(mb, xw - rw * 0.4, sy * 0.48 - 0.11, rw - rw * 0.4, xw + rw * 0.4, sy * 0.48 + 0.11, rw + rw * 0.4, mj_)
    pt = Vector((*P_["centre"], 0)) + Matrix.Rotation(math.radians(P_["angle_deg"]), 4, "Z") @ Vector((-1.6, 1.5, 0))
    objet("parc_tracteur_tondeuse", mb.construire("parc_tracteur_tondeuse"), (pt.x, pt.y, zg + 0.1),
          math.radians(P_["angle_deg"]), parent="parc_annexes")
    # benne bleue
    m_bleu = materiau("parc_benne_bleue", couleur=(0.05, 0.22, 0.55), rugosite=0.5, metal=0.4, double=True)
    mb = MB(lisse=False)
    mbl = mb.mat(m_bleu)
    Lb, lb, hb = 1.8, 0.9, 1.15
    boite(mb, -Lb, -lb, 0.1, Lb, lb, 0.18, mbl)
    for sx in (-1, 1):
        pave(mb, (sx * (Lb + 0.2), -lb - 0.1), (sx * (Lb + 0.2), lb + 0.1), 0.06, (0.1, 0.1), (hb, hb), mbl)
    for sy in (-1, 1):
        pave(mb, (-Lb - 0.2, sy * (lb + 0.1)), (Lb + 0.2, sy * (lb + 0.1)), 0.06, (0.1, 0.1), (hb, hb), mbl)
    for sy in (-1, 1):
        boite(mb, -Lb + 0.2, sy * 0.5 - 0.06, 0.0, Lb - 0.2, sy * 0.5 + 0.06, 0.1, mbl)
    pbn = PLAN["benne"]
    objet("parc_benne", mb.construire("parc_benne"), (pbn["centre"][0], pbn["centre"][1], H(*pbn["centre"])),
          math.radians(pbn["angle_deg"]), parent="parc_annexes")
    log("grange, tracteur tondeuse, benne")

    # --- Camionnette blanche du jardinier ----------------------------------------------------------
    m_blanc_u = materiau("parc_carrosserie_utilitaire", couleur=(0.88, 0.88, 0.87), rugosite=0.25, metal=0.3)
    mb = MB(lisse=False)
    mc4, mv4, mpn4, mj4 = mb.mat(m_blanc_u), mb.mat(m_vitre), mb.mat(m_pneu), mb.mat(m_jante)
    prof_v = [(-2.55, 0.42), (2.45, 0.42), (2.6, 0.62), (2.6, 1.0), (2.2, 1.15), (1.55, 1.95), (1.25, 2.3),
              (-2.55, 2.3)]
    prisme(mb, prof_v, -0.98, 0.98, mc4, mc4)
    for sy in (-1, 1):
        q = [(1.25, 1.35), (1.75, 1.35), (1.45, 1.85), (1.25, 2.05)]
        ids = [mb.sv((x, sy * 0.99, z)) for x, z in q]
        mb.face(ids if sy > 0 else ids[::-1], [(0, 0), (1, 0), (1, 1), (0, 1)], mv4)
    ids = [mb.sv((2.21 + 0.005, -0.85, 1.17)), mb.sv((2.21 + 0.005, 0.85, 1.17)), mb.sv((1.56 + 0.005, 0.85, 1.94)),
           mb.sv((1.56 + 0.005, -0.85, 1.94))]
    mb.face(ids, [(0, 0), (1, 0), (1, 1), (0, 1)], mv4)
    for xw in (-1.75, 1.7):
        for sy in (-1, 1):
            nv0 = len(mb.v)
            tour(mb, [(0.0, -0.11), (0.25, -0.11), (0.36, -0.08), (0.36, 0.08), (0.25, 0.11), (0.0, 0.11)], 14,
                 mpn4)
            for i in range(nv0, len(mb.v)):
                x, y, z = mb.v[i]
                mb.v[i] = (xw + x, sy * 0.86 + z, 0.36 + y)
    for sy in (-1, 1):
        boite(mb, 2.58, sy * 0.7 - 0.15, 0.85, 2.62, sy * 0.7 + 0.15, 0.97, mb.mat(m_phare))
        boite(mb, -2.58, sy * 0.85 - 0.08, 0.9, -2.54, sy * 0.85 + 0.08, 1.3, mb.mat(m_feu))
    pc = PLAN["camionnette"]
    objet("parc_camionnette", mb.construire("parc_camionnette"), (pc["centre"][0], pc["centre"][1], H(*pc["centre"]) + 0.02),
          math.radians(pc["angle_deg"]), parent="parc_annexes")
    log("camionnette")

    # --- Massifs : bacs de terre, rocaille NE du tennis (W12), massif rond est (drone) ------------
    def massif(nom, cx, cy, r, z=None, pierres=True):
        zz = H(cx, cy) if z is None else z
        pts = [Vector((cx + math.cos(a) * r, cy + math.sin(a) * r, 0)) for a in
               [2 * math.pi * k / 28 for k in range(28)]]
        o = plan_contour(nom, pts, zz + 0.06, m_terre, 2.0)
        o.parent = groupe("parc_jardin")
        if pierres:
            for k, p in enumerate(pts):
                objet(f"{nom}_pierre_{k:02d}", me_cail, (p.x, p.y, zz + 0.04), rnd.uniform(0, 6.3),
                      (rnd.uniform(0.2, 0.3), rnd.uniform(0.15, 0.22), rnd.uniform(0.18, 0.26)))

    MR = PLAN["massif_rond_est"]
    massif("parc_massif_rond_est", MR["centre"][0], MR["centre"][1], MR["rayon"])
    massif("parc_massif_if_nord", -8.0, -14.0, 3.6, z=Z_COUR_NORD)
    massif("parc_massif_pin_nord", ABORDS["cour_nord_parking"]["arbre_devant_entree"]["x"],
           ABORDS["cour_nord_parking"]["arbre_devant_entree"]["y"], 3.2, z=Z_COUR_NORD)
    massif("parc_massif_palmiers_so", -26.0, 15.5, 3.0, z=Z_COUR_SUD)
    for k, (cx, cy) in enumerate(GAB["perron_sud"]["massifs"]["centres"]):
        massif(f"parc_terre_laurier_perron_{k}", cx, cy, GAB["perron_sud"]["massifs"]["diametre_m"] / 2 - 0.15,
               z=Z_COUR_SUD, pierres=False)
    # Rocaille au pied de l'escalier nord-est du tennis (Google 13 : agaves, cactées)
    massif("parc_rocaille_no", -12.6, -23.4, 2.4, z=Z_COUR_NORD)
    me_ag = None

    # --- Végétation ----------------------------------------------------------
    E = construire_especes(TX)
    log("espèces construites")
    rv = random.Random(99)
    hauteurs = {}
    for k, (esp, x, y, ech, rot, h_vis) in enumerate(P):
        var = E[esp][k % len(E[esp])]
        if h_vis:
            # Hauteur mesurée : échelle = hauteur LiDAR / hauteur du modèle de l'essence.
            if var.name not in hauteurs:
                hauteurs[var.name] = max((v.co.z for v in var.vertices), default=1.0) or 1.0
            ech = max(0.45, min(2.2, h_vis / hauteurs[var.name]))
        z = H(x, y)
        if pip(x, y, COUR_NORD) or abs(x + 8) < 4 and abs(y + 14) < 4:
            z = Z_COUR_NORD
        objet(f"parc_{esp}_{k:03d}", var, (x, y, z + 0.02), rot, ech, parent="parc_vegetation")
    for k in range(9):
        a = 2 * math.pi * k / 9
        x, y = -12.6 + math.cos(a) * 1.6, -23.4 + math.sin(a) * 1.6
        objet(f"parc_agave_{k:02d}", E["agave"][0], (x, y, Z_COUR_NORD + 0.06), rv.uniform(0, 6.3),
              rv.uniform(0.5, 0.9), parent="parc_vegetation")

    # Bordures fleuries le long des allées, à l'intérieur du domaine (Google 11-12) : bande de paillis sablé
    # et petites plantes taillées en deux rangs, des deux côtés de la grande allée et de l'allée est.
    m_paillis = materiau("parc_paillis_bordure", TX["sable"], couleur=(0.92, 0.8, 0.66), nor=ph("sandy_gravel", "nor_gl"))
    def y_ok(q, nom_a):
        return q.y > 20.0 if nom_a == "arc" else -26.0 < q.y < 10.0

    jonctions = [Vector((*ALLEE_SERVICE[0], 0)), Vector((*ALLEE_LOCAL[0], 0)), Vector((*ALLEE_ARC[0], 0))]
    k_b = 0
    for nom_a, pts_a, larg in (("arc", ALLEE_ARC, AL["arc"]["largeur"]), ("est", ALLEE_EST, AL["est"]["largeur"])):
        pts, _ = reechantillonner(catmull(pts_a, pas=12), 0.9)
        T = tangentes(pts)
        for cote in (-1, 1):
            items, bande, bandes = [], [], []
            for i, p in enumerate(pts):
                g = Vector((-T[i].y, T[i].x, 0)) * cote
                q = p + g * (larg / 2 + 0.85)
                ok = (pip(q.x, q.y, LIMITE) and dist_contour(q.x, q.y, LIMITE) > 2.5 and y_ok(q, nom_a)
                      and all((q - j).length > 5.0 for j in jonctions) and not pres_portail(q.x, q.y, 6.0)
                      and not any(pip(q.x, q.y, t) for t in (COUR_NORD, COUR_SUD, PLATEFORME, EMPRISE))
                      and dist_allee(q.x, q.y) > 0.3)
                if ok:
                    bande.append((q.x, q.y))
                    for rang, off in ((0, 0.45), (1, 1.1)):
                        if (i + rang) % 2 == 0 or rv.random() < 0.35:
                            qq = p + g * (larg / 2 + off) + T[i] * rv.uniform(-0.25, 0.25)
                            var = rv.choice(E["bordure"])
                            items.append((var, (qq.x, qq.y, H(qq.x, qq.y) + 0.03), rv.uniform(0, 6.3), rv.uniform(0.75, 1.25)))
                elif len(bande) > 2:
                    bandes.append(bande)
                    bande = []
                else:
                    bande = []
            if len(bande) > 2:
                bandes.append(bande)
            for bd in bandes:
                allee(f"parc_paillis_bordure_{k_b:02d}", bd, 1.5, m_paillis, bordures=False, dz=0.045,
                      parent="parc_vegetation")
                k_b += 1
            for j0 in range(0, len(items), 120):
                fusionner(f"parc_fleurs_bordure_{nom_a}_{'g' if cote < 0 else 'd'}_{j0 // 120:02d}", items[j0:j0 + 120])
    log(f"végétation : {len(P)} plants")


# ---------------------------------------------------------------------------

construire()

if not RENDU_SEUL:
    glb = os.path.join(EXPORT, "parc.glb")
    kw = dict(filepath=glb, export_format="GLB", use_selection=False, export_apply=True, export_yup=True,
              export_image_format="AUTO", export_vertex_color="MATERIAL", export_extras=False)
    while True:
        try:
            bpy.ops.export_scene.gltf(**kw)
            break
        except TypeError as err:
            cle = next((k for k in list(kw) if k in str(err) and k not in ("filepath",)), None)
            if not cle:
                raise
            kw.pop(cle)
    log(f"GLB écrit ({os.path.getsize(glb) / 1e6:.1f} Mo)")

# --- Caméra, soleil, ciel (pour le .blend et le rendu de contrôle) ----------
monde = bpy.data.worlds.new("parc_ciel")
SCENE.world = monde
try:
    monde.use_nodes = True
except Exception:
    pass
bg = next(n for n in monde.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.62, 0.74, 0.92, 1)
bg.inputs["Strength"].default_value = 0.9
soleil = bpy.data.lights.new("parc_soleil", "SUN")
soleil.energy = 4.2
soleil.angle = math.radians(1.5)
o_sol = bpy.data.objects.new("parc_soleil", soleil)
o_sol.rotation_euler = (math.radians(40), 0, math.radians(200))
SCENE.collection.objects.link(o_sol)
cam_d = bpy.data.cameras.new("parc_camera")
cam = bpy.data.objects.new("parc_camera", cam_d)
SCENE.collection.objects.link(cam)
SCENE.camera = cam


def viser(cam, pos, cible, focale):
    cam.location = pos
    d = Vector(cible) - Vector(pos)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = focale
    cam.data.clip_end = 2000


viser(cam, (6.0, 196.0, 118.0), (2.0, 40.0, -8.0), 30)   # ~W18 : depuis le sud, en hauteur
if not RENDU_SEUL:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(EXPORT, "parc.blend"), compress=True)
    log(".blend écrit")

# --- Témoin du château (rendu seulement, ni GLB ni .blend) -------------------
mb = MB(lisse=False)
mt = mb.mat(materiau("temoin_chateau", couleur=(0.82, 0.76, 0.64), rugosite=0.9))
boite(mb, -18, -9.45, -1.5, 18, 9.45, 10.1, mt)
boite(mb, -10.8, -8.75, 10.1, 10.8, 8.75, 15.0, mt)
boite(mb, -3.96, 8.75, -1.5, 3.96, 11.25, 15.0, mt)
boite(mb, -4.0, -12.45, -1.5, 4.0, -8.75, 16.0, mt)
mt2 = mb.mat(materiau("temoin_toit", couleur=(0.62, 0.3, 0.18), rugosite=0.9))
boite(mb, -10.3, -8.3, 15.0, 10.3, 8.3, 16.8, mt2)
mt3 = mb.mat(materiau("temoin_terrasse", couleur=(0.86, 0.83, 0.76), rugosite=0.9))
boite(mb, -19.5, 9.45, -1.3, X_TER_E, Y_TER, -0.05, mt3)
boite(mb, -7.5, Y_TER, -1.3, 7.5, GAB["perron_sud"]["polygone"][0][1], -0.05, mt3)
boite(mb, 18.0, -1.8, -1.3, X_TER_E, 9.45, -0.05, mt3)
boite(mb, -7.5, GAB["perron_sud"]["polygone"][0][1], -1.3, 7.5, Y_BAS_PERRON, -0.6, mt3)
temoin = bpy.data.objects.new("temoin_chateau", mb.construire("temoin_chateau"))
SCENE.collection.objects.link(temoin)

r = SCENE.render
for moteur in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        r.engine = moteur
        break
    except TypeError:
        continue
try:
    SCENE.eevee.taa_render_samples = 16
except Exception:
    pass
r.resolution_x, r.resolution_y = 1600, 1000
r.image_settings.file_format = "PNG"
vues = [("parc", (6.0, 196.0, 118.0), (2.0, 40.0, -8.0), 30)]
if "--vues" in ARGS:
    vues += [("parc_w16", (2.0, 92.0, 42.0), (0.0, 5.0, 4.0), 30),
             ("parc_w12", (0.5, 0.0, 150.0), (0.0, 0.01, 0.0), 28),
             ("parc_w03", (-70.0, 150.0, 70.0), (10.0, 40.0, -4.0), 30)]
if "--plan" in ARGS:
    vues = [("parc_plan", (42.0, 55.0, 300.0), (42.0, 55.01, 0.0), -200.0),
            ("parc_entree", (128.0, 104.0, 12.0), (100.0, 112.0, -10.0), 24),
            ("parc_sud_est", (110.0, 175.0, 70.0), (45.0, 75.0, -6.0), 26),
            ("parc_tennis", (-55.0, -48.0, 30.0), (-22.0, -5.0, -1.0), 26),
            ("parc_grange", (72.0, 66.0, 14.0), (86.0, 95.0, -8.0), 24),
            ("parc_piscine", (-12.0, 40.0, 22.0), (14.0, 80.0, -4.0), 24)]
# vélo cargo au pied du perron nord, avec terrasse.glb (échiffres, dés, lampadaires) pour juger sa place
vues.append(("parc_velo_cargo", (-6.3, -19.7, -0.5), (-4.0, -16.5, -0.85), 30))
for nom, pos, cible, f in vues:
    glb_t = os.path.join(EXPORT, "terrasse.glb")
    if nom == "parc_velo_cargo" and os.path.exists(glb_t):
        bpy.ops.import_scene.gltf(filepath=glb_t)
    cam.data.type = "ORTHO" if f < 0 else "PERSP"
    if f < 0:
        cam.data.ortho_scale = -f
    viser(cam, pos, cible, abs(f))
    r.filepath = os.path.join(RENDUS, nom + ".png")
    bpy.ops.render.render(write_still=True)
    log(f"rendu {r.filepath}")
log("terminé")

"""Combles d'après R18 et R17–R20, repère D-003, avant le miroir D-026.

blender -b --factory-startup --python scripts/composants/piece_combles.py -- --sans-rendus
python3 scripts/composants/piece_combles.py --vue-plan-seule
"""

import argparse
import json
import math
from pathlib import Path
import sys

RACINE = Path(__file__).resolve().parents[2]
RELEVE = RACINE / "travail" / "releve-2026-11-19"
DATA = json.loads((RELEVE / "combles.json").read_text())
Z_BAS = DATA["niveaux"]["etage"]
Z_REPOS = DATA["niveaux"]["demi_palier"]
Z_SOL = DATA["niveaux"]["sol"]
Z_PLAFOND = DATA["niveaux"]["plafond"]
EPAISSEUR_DALLE = DATA["niveaux"]["dalle"]
ESCALIER = DATA["escalier_service"]
TREMIE = ESCALIER["rect_volee_haute"]
MATERIAUX = {
    "tomettes": ((0.29, 0.122, 0.075), 0.56, 0.0),
    "marches": ((0.205, 0.078, 0.046), 0.54, 0.0),
    "nez": ((0.125, 0.059, 0.036), 0.46, 0.0),
    "enduit": ((0.83, 0.79, 0.71), 0.78, 0.0),
    "soubassement": ((0.47, 0.48, 0.45), 0.83, 0.0),
    "plafond": ((0.85, 0.83, 0.77), 0.82, 0.0),
    "laque": ((0.78, 0.75, 0.67), 0.43, 0.0),
    "acier": ((0.043, 0.038, 0.034), 0.44, 0.55),
    "bois": ((0.179, 0.081, 0.038), 0.46, 0.0),
    "bois_cadre": ((0.293, 0.128, 0.061), 0.43, 0.0),
    "linge": ((0.85, 0.85, 0.8), 0.9, 0.0),
    "oreiller": ((0.91, 0.89, 0.83), 0.78, 0.0),
    "tapis": ((0.24, 0.058, 0.045), 0.91, 0.0),
    "tapis_bord": ((0.46, 0.19, 0.115), 0.91, 0.0),
    "porcelaine": ((0.84, 0.88, 0.86), 0.24, 0.0),
    "interieur_bain": ((0.70, 0.75, 0.74), 0.31, 0.0),
    "laiton": ((0.48, 0.30, 0.13), 0.35, 0.68),
    "miroir": ((0.60, 0.67, 0.68), 0.17, 0.85),
    "verre_lampe": ((0.95, 0.82, 0.54), 0.34, 0.0),
}


def intersection(a, b):
    rect = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return rect if rect[0] < rect[2] and rect[1] < rect[3] else None


def decoupe_rect(rect, trou):
    rencontre = intersection(rect, trou)
    if rencontre is None:
        return [rect]
    x0, y0, x1, y1 = rect
    gauche, nord, droite, sud = rencontre
    morceaux = [
        (x0, y0, gauche, y1),
        (droite, y0, x1, y1),
        (gauche, y0, droite, nord),
        (gauche, sud, droite, y1),
    ]
    return [p for p in morceaux if p[2] > p[0] and p[3] > p[1]]


def empreintes():
    rects = [p["rect"] for p in DATA["espaces"].values()]
    return rects + list(DATA["extensions_sol"].values())


def sections_mur(mur):
    """Intervalles rectilignes, en conservant le passage indiqué sur le plan."""
    if "ouverture" not in mur:
        return [(mur["de"], mur["a"])]
    porte_de, porte_a = mur["ouverture"]
    return [(mur["de"], porte_de), (porte_a, mur["a"])]


def bande_mur(mur, de, a, ep=None):
    rayon = (mur["ep"] if ep is None else ep) / 2
    c = mur["fixe"]
    if mur["axe"] == "x":
        return de, c - rayon, a, c + rayon
    return c - rayon, de, c + rayon, a


def verifier_plan():
    rects = empreintes()
    vide = DATA["noyau_coupole"]["rect_reserve"]
    for i, rect in enumerate(rects):
        assert rect[0] < rect[2] and rect[1] < rect[3], rect
        assert intersection(rect, vide) is None, (rect, vide)
        assert all(intersection(rect, autre) is None for autre in rects[:i]), rect
    assert intersection(DATA["espaces"]["75"]["rect"], TREMIE) == tuple(TREMIE)
    assert ESCALIER["arrivee_haute_xyz"][0] == TREMIE[0]
    assert ESCALIER["depart_bas_xyz"][2] == Z_BAS
    assert Z_SOL - EPAISSEUR_DALLE - Z_REPOS >= 2.1
    nombre = ESCALIER["contremarches_par_volee"]
    assert 0.15 < (Z_SOL - Z_REPOS) / nombre < 0.2
    assert 0.15 < (Z_REPOS - Z_BAS) / nombre < 0.2


def sauver_plan():
    facteur = 32
    x_origine, y_origine = 596, 331

    def zone(rect, couleur, bord="none"):
        x0, y0, x1, y1 = rect
        return (f'<rect x="{x_origine + x0*facteur:.1f}" y="{y_origine + y0*facteur:.1f}" '
                f'width="{(x1-x0)*facteur:.1f}" height="{(y1-y0)*facteur:.1f}" '
                f'fill="{couleur}" stroke="{bord}"/>')

    def etiquette(chaine, x, y, taille=16):
        return (f'<text x="{x_origine+x*facteur:.1f}" y="{y_origine+y*facteur:.1f}" '
                f'text-anchor="middle" font-size="{taille}">{chaine}</text>')

    def point(coord):
        x, y = coord
        return f"{x_origine+x*facteur:.1f},{y_origine+y*facteur:.1f}"

    fond = ['<svg xmlns="http://www.w3.org/2000/svg" width="1192" height="596" viewBox="0 0 1192 596">',
            '<rect width="1192" height="596" fill="#f2efe8"/>',
            '<g font-family="sans-serif" fill="#272d31">']
    fond += [etiquette("Château Saint-Victor — combles 75–81", 0, -9.65, 22)]
    contour = " ".join(point(p) for p in DATA["enveloppe"]["nu_exterieur"])
    fond += [f'<polygon points="{contour}" fill="#a29080"/>']
    fond += [zone(rect, "#e6c8ad", "#c19e81") for rect in empreintes()]
    fond += [zone(DATA["noyau_coupole"]["rect_reserve"], "#dde1e3", "#737a80")]
    fond += [zone(TREMIE, "#829eae", "#4a6071")]
    fond += [zone(ESCALIER["rect_volee_basse"], "#b5c6cd", "#82969d")]
    fond += [zone(ESCALIER["rect_demi_palier"], "#b5c6cd", "#82969d")]
    fond += [zone(DATA["trappe_toit"]["rect"], "#b08570")]
    fond += [zone(bande_mur(mur, de, a), "#574a40") for mur in DATA["murs"]
             for de, a in sections_mur(mur)]
    for identifiant, espace in DATA["espaces"].items():
        x0, y0, x1, y1 = espace["rect"]
        texte = identifiant if identifiant.isdigit() else espace["nom"]
        y = (y0 + y1) / 2
        if identifiant == "76":
            y = 3.85
        if identifiant == "81":
            y = -5.25
        fond += [etiquette(texte, (x0 + x1) / 2, y + 0.13)]
    fond += [etiquette("réserve coupole", 0, 0.14), etiquette("volée haute →", 6.95, -1.10, 13)]
    fond += [etiquette("← volée basse (étage)", 7, 0.13, 13)]
    fond += [etiquette("N ↑", 15.2, -7.85, 20)]
    fond += [etiquette("Murs et sol en mètres, emprise et numéros du relevé R18", 0, 7.66, 13), "</g></svg>"]
    fichier = RELEVE / "combles-controle.svg"
    fichier.write_text("\n".join(fond), encoding="utf-8")
    print(fichier)


class Maillage:
    """Un objet maillé par groupe, avec des teintes glTF sans dépendances externes."""

    def __init__(self):
        self.sommets = []
        self.faces = []
        self.indices = []
        self.materiaux = []

    def solide(self, sommets, faces, mat):
        debut = len(self.sommets)
        self.sommets.extend(sommets)
        self.faces.extend(tuple(debut + i for i in face) for face in faces)
        if mat not in self.materiaux:
            self.materiaux.append(mat)
        self.indices.extend([self.materiaux.index(mat)] * len(faces))

    def dalle(self, rect, z0, z1, mat):
        x0, y0, x1, y1 = rect
        self.boite(x0, y0, z0, x1, y1, z1, mat)

    def boite(self, x0, y0, z0, x1, y1, z1, mat):
        assert x1 > x0 and y1 > y0 and z1 > z0, (x0, y0, z0, x1, y1, z1)
        base = [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        faces = [(3,2,1,0), (4,5,6,7), (0,1,5,4), (1,2,6,5), (2,3,7,6), (3,0,4,7)]
        self.solide([(x,y,z) for z in (z0,z1) for x,y in base], faces, mat)

    def cylindre(self, depart, fin, rayon, mat, cotes=10):
        from mathutils import Vector

        a = Vector(depart)
        b = Vector(fin)
        axe = (b-a).normalized()
        u = axe.cross(Vector((0,0,1))).normalized()
        if u.length < 0.1:
            u = Vector((1,0,0))
        v = axe.cross(u)
        angles = [2*math.pi*i/cotes for i in range(cotes)]
        profil = [(rayon*math.cos(t))*u + (rayon*math.sin(t))*v for t in angles]
        sommets = [tuple(p + d) for p in (a,b) for d in profil]
        faces = [tuple(range(cotes-1,-1,-1)), tuple(range(cotes,2*cotes))]
        for i in range(cotes):
            j = (i+1) % cotes
            faces.append((i,j,j+cotes,i+cotes))
        self.solide(sommets, faces, mat)

    def publier(self, nom, collection, materiaux):
        import bpy

        mesh = bpy.data.meshes.new(nom)
        mesh.from_pydata(self.sommets, [], self.faces)
        mesh.update()
        for mat in self.materiaux:
            mesh.materials.append(materiaux[mat])
        for face, index in zip(mesh.polygons, self.indices):
            face.material_index = index
        objet = bpy.data.objects.new(nom, mesh)
        collection.objects.link(objet)
        return objet


def dalle_et_plafond():
    maillage = Maillage()
    for zone in empreintes():
        for morceau in decoupe_rect(zone, TREMIE):
            maillage.dalle(morceau, Z_SOL - EPAISSEUR_DALLE, Z_SOL, "tomettes")
        maillage.dalle(zone, Z_PLAFOND, Z_PLAFOND + 0.07, "plafond")
    return maillage


def cloisons():
    murs = Maillage()
    encadrements = Maillage()

    def panneau(mur, de, a, bas, sommet):
        murs.dalle(bande_mur(mur, de, a), bas, sommet, "enduit")
        if bas == Z_SOL:
            murs.dalle(bande_mur(mur, de, a, mur["ep"] + 0.014), Z_SOL, Z_SOL + 0.84, "soubassement")
            murs.dalle(bande_mur(mur, de, a, mur["ep"] + 0.029), Z_SOL + 0.82, Z_SOL + 0.87, "laque")
            murs.dalle(bande_mur(mur, de, a, mur["ep"] + 0.035), Z_SOL, Z_SOL + 0.08, "laque")

    for mur in DATA["murs"]:
        for de, a in sections_mur(mur):
            panneau(mur, de, a, Z_SOL, Z_PLAFOND)
        if "ouverture" not in mur:
            continue
        de, a = mur["ouverture"]
        haut = Z_SOL + 2.12
        panneau(mur, de, a, haut, Z_PLAFOND)
        ep = mur["ep"] + 0.105
        for debut, fin in ((de - 0.065, de + 0.025), (a - 0.025, a + 0.065)):
            encadrements.dalle(bande_mur(mur, debut, fin, ep), Z_SOL, haut + 0.04, "laque")
        encadrements.dalle(bande_mur(mur, de - 0.065, a + 0.065, ep), haut - 0.025, haut + 0.065, "laque")
    return murs, encadrements


def escalier_service():
    marches = Maillage()
    garde_corps = Maillage()
    x_ouest, x_est = ESCALIER["x_ouest"], ESCALIER["x_est"]
    n = ESCALIER["contremarches_par_volee"]
    largeur_marche = (x_est - x_ouest) / n

    def main_courante(depart, arrivee, hauteur=0.94):
        x0, y0, z0 = depart
        x1, y1, z1 = arrivee
        longueur = math.hypot(x1-x0, y1-y0)
        nombre = max(1, math.ceil(longueur/0.22))
        p0 = (x0, y0, z0+hauteur)
        p1 = (x1, y1, z1+hauteur)
        garde_corps.cylindre(p0, p1, 0.035, "bois")
        for i in range(nombre + 1):
            t = i / nombre
            x = x0 + (x1-x0)*t
            y = y0 + (y1-y0)*t
            z = z0 + (z1-z0)*t
            garde_corps.cylindre((x,y,z-0.09),(x,y,z+hauteur),0.012,"acier")

    def volee(rect, z0, z1, monte_est, y_barre):
        _, nord, _, sud = rect
        hauteur = (z1-z0) / n
        for i in range(n):
            x = x_ouest + largeur_marche*i if monte_est else x_est - largeur_marche*(i+1)
            haut = z0 + hauteur*(i+1)
            marches.boite(x, nord, haut-0.29, x+largeur_marche, sud, haut, "marches")
            bord = x if monte_est else x+largeur_marche-0.031
            marches.boite(bord, nord, haut-0.038, bord+0.031, sud, haut+0.002, "nez")
        depart, arrivee = (x_ouest,x_est) if monte_est else (x_est,x_ouest)
        main_courante((depart,y_barre,z0+hauteur), (arrivee,y_barre,z1))

    # Cage latérale est : volée basse vers l'est, demi-palier contre la façade, volée haute de retour vers l'ouest.
    basse, haute, repos = ESCALIER["rect_volee_basse"], TREMIE, ESCALIER["rect_demi_palier"]
    volee(basse, Z_BAS, Z_REPOS, True, (basse[1] + haute[3]) / 2)
    volee(haute, Z_REPOS, Z_SOL, False, (basse[1] + haute[3]) / 2)
    marches.dalle(repos, Z_REPOS-0.18, Z_REPOS, "marches")
    # garde-corps de la trémie aux combles, côtés sud et est
    main_courante((x_ouest, haute[3], Z_SOL), (x_est, haute[3], Z_SOL))
    main_courante((x_est, haute[1], Z_SOL), (x_est, haute[3], Z_SOL))
    return marches, garde_corps


def garnitures():
    """Quelques détails visibles près du palier et dans les pièces documentées."""
    decor = Maillage()

    def tapis(cx, cy, largeur, longueur):
        x0, x1 = cx-largeur/2, cx+largeur/2
        y0, y1 = cy-longueur/2, cy+longueur/2
        decor.boite(x0,y0,Z_SOL+0.001,x1,y1,Z_SOL+0.009,"tapis_bord")
        decor.boite(x0+0.08,y0+0.08,Z_SOL+0.009,x1-0.08,y1-0.08,Z_SOL+0.013,"tapis")

    def lit(x, y, large, long=2.08, tete_haute=0.89):
        """Tête au nord, montant de lit en bois et linge clair."""
        z = Z_SOL
        decor.boite(x,y,z+0.15,x+large,y+long,z+0.41,"bois")
        decor.boite(x+0.045,y+0.04,z+0.41,x+large-0.045,y+long-0.085,z+0.57,"linge")
        decor.boite(x+0.09,y+0.12,z+0.57,x+large-0.09,y+0.46,z+0.64,"oreiller")
        decor.boite(x,y,z+0.052,x+large,y+0.057,z+tete_haute,"bois_cadre")
        decor.boite(x,y+long-0.055,z+0.045,x+large,y+long,z+0.476,"bois")
        for px in (x+0.035, x+large-0.085):
            for py in (y+0.04,y+long-0.09):
                decor.boite(px,py,z,px+0.05,py+0.05,z+0.19,"bois")

    def armoire(x0, y0, largeur=1.12, profondeur=0.56):
        x1, y1 = x0+largeur, y0+profondeur
        decor.boite(x0,y0,Z_SOL,x1,y1,Z_SOL+1.98,"bois")
        decor.boite(x0-.025,y0-.025,Z_SOL+1.98,x1+.025,y1+.025,Z_SOL+2.04,"bois_cadre")
        for x in (x0+0.048, x0+largeur/2+0.018):
            fin = x+largeur/2-0.064
            decor.boite(x,y1,Z_SOL+0.12,fin,y1+0.026,Z_SOL+1.91,"bois_cadre")
        for x in (x0+largeur/2-0.06, x0+largeur/2+0.06):
            decor.cylindre((x,y1+0.026,Z_SOL+1.03),(x,y1+0.07,Z_SOL+1.03),0.015,"laiton")

    def radiateur(x, y, larg=0.95):
        for i in range(10):
            cx = x + (i+0.5)*larg/10
            decor.boite(cx-0.027,y,Z_SOL+0.14,cx+0.027,y+0.13,Z_SOL+0.79,"laque")

    def lustre(x, y):
        z0 = Z_PLAFOND-0.64
        decor.cylindre((x,y,z0),(x,y,Z_PLAFOND),0.016,"acier")
        for angle in (0, math.tau/5, 2*math.tau/5, 3*math.tau/5, 4*math.tau/5):
            tx, ty = x+0.31*math.cos(angle), y+0.31*math.sin(angle)
            decor.cylindre((x,y,z0),(tx,ty,z0+0.11),0.015,"acier")
            decor.cylindre((tx,ty,z0+0.11),(tx,ty,z0+0.21),0.025,"verre_lampe")

    def baignoire(x, y):
        z = Z_SOL
        decor.boite(x,y,z,x+1.72,y+0.72,z+0.43,"porcelaine")
        decor.boite(x+0.092,y+0.078,z+0.431,x+1.628,y+0.642,z+0.442,"interieur_bain")
        for rect in ((x,y,x+0.09,y+0.72), (x+1.63,y,x+1.72,y+0.72),
                     (x+0.09,y,x+1.63,y+0.076), (x+0.09,y+0.644,x+1.63,y+0.72)):
            decor.dalle(rect,z+0.43,z+0.52,"porcelaine")
        decor.cylindre((x+0.21,y+0.04,z+0.52),(x+0.21,y+0.04,z+0.66),0.017,"laiton")
        decor.cylindre((x+0.21,y+0.04,z+0.66),(x+0.21,y+0.20,z+0.66),0.017,"laiton")

    def lavabo(x, y):
        z = Z_SOL
        decor.boite(x,y,z,x+0.78,y+0.49,z+0.79,"bois_cadre")
        decor.boite(x-0.018,y-0.025,z+0.79,x+0.798,y+0.515,z+0.88,"porcelaine")
        decor.boite(x+0.056,y+0.08,z+0.882,x+0.724,y+0.389,z+0.898,"interieur_bain")
        decor.cylindre((x+0.39,y+0.43,z+0.88),(x+0.39,y+0.43,z+0.99),0.014,"laiton")
        decor.boite(x+0.07,y+0.46,z+1.04,x+0.71,y+0.50,z+1.70,"bois")
        decor.boite(x+0.10,y+0.449,z+1.08,x+0.68,y+0.46,z+1.66,"miroir")

    # Les usages sont observés. Leurs implantations dans les grands espaces R18 sont indicatives.
    lit(5.62, -5.40, 0.99)
    lit(7.10, -5.40, 0.99)
    radiateur(8.14, -5.58)
    lustre(7.10, -3.95)
    lit(-8.45, 2.14, 1.55)
    tapis(-7.67, 3.40, 2.08, 2.80)
    lustre(-7.50, 3.60)
    lit(-7.95, -5.20, 1.61, tete_haute=0.67)
    armoire(-5.70, -5.42)
    radiateur(-9.13, -5.56)
    baignoire(-15.44, 0.86)
    lavabo(-13.04, -1.76)
    # chambre de l'extrémité est : déplacée dans 76, l'escalier occupant désormais 75
    lit(6.20, -1.60, 1.47)
    armoire(8.30, -1.69)
    tapis(6.93, -0.20, 1.72, 2.54)
    lustre(6.93, -0.20)
    return decor


def exporter(blend):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    collection = bpy.data.collections.new("piece_combles")
    scene.collection.children.link(collection)
    materiaux = {}
    for nom, (couleur, rugosite, metal) in MATERIAUX.items():
        mat = bpy.data.materials.new("Combles_" + nom)
        mat.diffuse_color = (*couleur, 1)
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = mat.diffuse_color
        shader.inputs["Roughness"].default_value = rugosite
        shader.inputs["Metallic"].default_value = metal
        if nom == "verre_lampe":
            shader.inputs["Emission Color"].default_value = (*couleur, 1)
            shader.inputs["Emission Strength"].default_value = 0.35
        materiaux[nom] = mat

    murs, chambranles = cloisons()
    marches, garde_corps = escalier_service()
    groupes = {
        "combles_dalle_plafond": dalle_et_plafond(),
        "combles_cloisons": murs,
        "combles_chambranles": chambranles,
        "combles_escalier_service": marches,
        "combles_garde_corps": garde_corps,
        "combles_mobilier": garnitures(),
    }
    for nom, geo in groupes.items():
        geo.publier(nom, collection, materiaux)

    # relevé du 19/11 : contrôlé à part avant de rejoindre export/composants
    dossier = RACINE / "export" / "releve-2026-11-19"
    dossier.mkdir(parents=True, exist_ok=True)
    glb = dossier / "piece_combles.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_apply=True)
    print(glb)
    if blend:
        bpy.ops.wm.save_as_mainfile(filepath=str(dossier / "piece_combles.blend"))


def main(arguments):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vue-plan", action="store_true", help="produit aussi un SVG de contrôle")
    parser.add_argument("--vue-plan-seule", action="store_true", help="aucun import Blender, sortie SVG uniquement")
    parser.add_argument("--sans-rendus", action="store_true", help="export GLB sans rendu Blender")
    parser.add_argument("--blend", action="store_true", help="conserve aussi la scène Blender source")
    args = parser.parse_args(arguments)
    verifier_plan()
    if args.vue_plan or args.vue_plan_seule:
        sauver_plan()
    if not args.vue_plan_seule:
        exporter(args.blend)


if __name__ == "__main__":
    arguments = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
    if Path(sys.argv[0]).name.startswith("blender") and "--" not in sys.argv:
        arguments = []
    main(arguments)

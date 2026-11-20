"""Gabarit commun (P2.emprise) : écrit travail/gabarit.json et rendus/emprise.png.

Repère D-003 : mètres, +X est, +Y sud (façade jardin), Z haut, RDC = 0, origine au centre de l'emprise.
Toutes les cotes sont paramétrées par L (longueur de la façade sud entre faces des pavillons) ; les
proportions viennent de W01/W11/W15/W17, l'échelle absolue de W12 (tennis, voitures) et des marches.
Lancer : python3.13 -I scripts/gabarit_emprise.py <racine du projet>
"""
import json
import math
import sys

from PIL import Image, ImageDraw, ImageFont

RACINE = sys.argv[1] if len(sys.argv) > 1 else "."

L = 36.0                     # façade sud hors tout (pavillons compris)
HX = L / 2                   # 18.0
PAV_L = 7.2                  # largeur des pavillons sur la façade sud (0,20 L, W01)
XP = HX - PAV_L              # 10.8 : limite pavillon / aile
DEMI_P = 8.75                # demi-profondeur du corps principal (N-S), W12
SAIL_PAV = 0.7               # saillie des pavillons sur les ailes (N et S)
YP = DEMI_P + SAIL_PAV       # 9.45
PAV_E = 5.6                  # profondeur des pavillons vue sur les faces est/ouest
AC_S = 3.96                  # demi-largeur avant-corps sud
AC_N = 4.0                   # demi-largeur avant-corps nord
MARCHE = 0.16

def c(v, src, inc, **k):
    d = {"valeur": v, "source": src, "incertitude": inc}
    d.update(k)
    return d

# ---------------------------------------------------------------- emprise du château (RDC, nu des murs)
emprise = [
    (-HX, YP), (-XP, YP), (-XP, DEMI_P), (-AC_S, DEMI_P), (-AC_S, DEMI_P + 0.6), (-3.1, DEMI_P + 0.6),
    (-2.3, DEMI_P + 2.5), (2.3, DEMI_P + 2.5), (3.1, DEMI_P + 0.6), (AC_S, DEMI_P + 0.6), (AC_S, DEMI_P),
    (XP, DEMI_P), (XP, YP), (HX, YP),
    (HX, -YP), (XP, -YP), (XP, -DEMI_P), (AC_N, -DEMI_P), (AC_N, -DEMI_P - 1.2), (-AC_N, -DEMI_P - 1.2),
    (-AC_N, -DEMI_P), (-XP, -DEMI_P), (-XP, -YP), (-HX, -YP),
]
r2 = lambda pts: [[round(x, 2), round(y, 2)] for x, y in pts]

corps = {
    "corps_principal": {"rect": [-XP, -DEMI_P, XP, DEMI_P], "niveaux": "RDC, étage, attique",
                        "note": "ailes entre pavillons, 3 niveaux (W01, W11)"},
    "pavillons": {
        "SO": {"rect": [-HX, YP - PAV_E, -XP, YP]},
        "SE": {"rect": [XP, YP - PAV_E, HX, YP]},
        "NO": {"rect": [-HX, -YP, -XP, -YP + PAV_E]},
        "NE": {"rect": [XP, -YP, HX, -YP + PAV_E]},
        "niveaux": "RDC, étage ; toit en croupe bas au-dessus de la corniche d'étage",
        "source": "W01, W15, W11, W12 (4 croupes d'angle)", "incertitude": "±0,8 m sur chaque côté",
    },
    "blocs_extremites": {
        "ouest": {"rect": [-HX, -YP + PAV_E, -XP, YP - PAV_E]},
        "est": {"rect": [XP, -YP + PAV_E, HX, YP - PAV_E]},
        "niveaux": "RDC, étage, attique (montent comme le corps central), croupe vers l'extérieur",
        "source": "W12 (croupe centrale aux deux bouts), W17 (2 fenêtres d'attique au centre de la face est), W15",
        "incertitude": "±1 m ; affleurement avec les pavillons supposé (W12)",
    },
    "avant_corps_sud": {"rect": [-AC_S, DEMI_P, AC_S, DEMI_P + 0.6],
                        "bow": "pans coupés + portique à 2 colonnes, saillie jusqu'à y=%.2f, face de 4,6 m" % (DEMI_P + 2.5),
                        "balcon_etage": "sur le bow, balustres pierre",
                        "niveaux": "RDC, étage, attique, toit pyramidal/croupe",
                        "source": "W01, W15, W16", "incertitude": "saillie du bow ±0,8 m"},
    "avant_corps_nord": {"rect": [-AC_N, -DEMI_P - 1.2, AC_N, -DEMI_P],
                         "niveaux": "RDC (porte), étage, attique, toit pyramidal",
                         "source": "W11, P38, W12 (D-011)", "incertitude": "saillie ±0,6 m"},
}
for k in ("SO", "SE", "NO", "NE"):
    corps["pavillons"][k]["rect"] = [round(v, 2) for v in corps["pavillons"][k]["rect"]]
for k in ("ouest", "est"):
    corps["blocs_extremites"][k]["rect"] = [round(v, 2) for v in corps["blocs_extremites"][k]["rect"]]

# ---------------------------------------------------------------- terrasse et perrons
# LiDAR HD IGN (outils/donnees_ouvertes.py, travail/plan_mesure.json) : terrasse au niveau du RDC jusqu'à
# y = 12 sur les côtés, palier central (|x| < 7,5) jusqu'à 14,7, perron de 10 marches jusqu'à ~18,05, cour à -1,55.
Y_TER = 12.0                  # bord sud de la terrasse (côtés)
Y_PAL = 14.7                  # bord sud du palier central, haut du perron sud
G_S = 0.335                   # giron du perron sud
MARCHE_S = 0.155              # hauteur de marche du perron sud
X_TER_O, X_TER_E = -HX - 1.5, HX + 5.5
Y_TER_E_N = -1.8              # extrémité nord de la terrasse est
terrasse = [(X_TER_O, Y_TER), (-7.5, Y_TER), (-7.5, Y_PAL), (7.5, Y_PAL), (7.5, Y_TER), (X_TER_E, Y_TER), (X_TER_E, Y_TER_E_N), (HX, Y_TER_E_N), (HX, YP),
            (-HX, YP), (-HX, YP - 3.0), (X_TER_O, YP - 3.0)]
n_s, n_n = 10, 9
perron_sud = {
    "polygone": r2([(-7.5, Y_PAL), (7.5, Y_PAL), (9.5, Y_PAL + n_s * G_S), (-9.5, Y_PAL + n_s * G_S)]),
    "marches": c(n_s, "LiDAR HD : 1,55 m de dénivelé sur 3,4 m (profil d'axe)", "±1 marche"),
    "hauteur_m": c(round(n_s * MARCHE_S, 2), "10 × 15,5 cm, LiDAR HD (terrasse 26,85 m NGF, cour 25,30)", "±0,1 m"),
    "giron_m": c(G_S, "LiDAR HD : perron de y = 14,7 à ~18", "±0,05"),
    "largeur_haut_m": c(15.0, "W01 (rapportée à la façade, correction de distance)", "±2,5 m"),
    "largeur_bas_m": c(19.0, "W01, W15 : marches évasées entre murs d'échiffre courbes", "±3 m"),
    "massifs": {"centres": [[-11.5, Y_PAL + 1.6], [11.5, Y_PAL + 1.6]], "diametre_m": 3.5,
                "nature": "lauriers-roses en massifs ronds bordés de pierre, vasque blanche à côté",
                "source": "W12 (écart 310 px sol), W15, W01", "incertitude": "±1,5 m"},
}
perron_nord = {
    "polygone": r2([(-3.0, -DEMI_P - 1.2), (3.0, -DEMI_P - 1.2), (3.0, -DEMI_P - 1.2 - 1.2 - n_n * 0.33),
                    (-3.0, -DEMI_P - 1.2 - 1.2 - n_n * 0.33)]),
    "palier_m": c(1.2, "P38 (palier devant la porte)", "±0,4"),
    "marches": c(n_n, "P38, fiche P38 (9 ou 10)", "±1 marche"),
    "hauteur_m": c(round(n_n * MARCHE, 2), "9 × 16 cm", "±0,3 m"),
    "largeur_m": c(6.0, "P38, W11 (entre murs d'échiffre bas)", "±1,5 m"),
    "lampadaires": "2 globes blancs sur mâts noirs de part et d'autre du bas du perron (P38)",
}
escalier_terrasse_est = {
    "rect": [HX + 1.0, Y_TER_E_N - 3.0, HX + 5.5, Y_TER_E_N],
    "sens": "descend vers le nord, de la terrasse est vers la cour/parking",
    "marches": c(8, "W12 (bandes de marches x_img 562-612)", "±2"),
    "source": "W12", "incertitude": "±1,5 m en position",
}

# ---------------------------------------------------------------- travées
def axes(lst):
    return [round(v, 2) for v in sorted(lst)]

travees = {
    "sud": {
        "rdc": c(9, "W01, W15, D-011", "sûr"), "etage": c(9, "W01", "sûr"), "attique": c(7, "W01", "sûr"),
        "axes_x": axes([0, -2.73, 2.73, -5.25, 5.25, -8.85, 8.85, -14.4, 14.4]),
        "axes_attique_x": axes([0, -2.73, 2.73, -5.25, 5.25, -8.85, 8.85]),
        "entraxe_ailes_m": c(3.6, "W01 (128 px zoom / façade 1290)", "±0,4"),
        "entraxe_avant_corps_m": c(2.73, "W01", "±0,3"),
        "composition": "pavillon 1 | aile 2 | avant-corps 3 (pans coupés) | aile 2 | pavillon 1",
    },
    "nord": {
        "rdc": c(7, "W11, P39", "±0 (porte au centre)"), "etage": c(7, "W11", "sûr"),
        "attique": c(5, "W11 (2 par aile + axe avant-corps)", "±1"),
        "axes_x": axes([0, -5.1, 5.1, -8.7, 8.7, -14.4, 14.4]),
        "entraxe_ailes_m": c(3.6, "W11 (même rythme que le sud)", "±0,4"),
        "composition": "pavillon 1 | aile 2 | avant-corps 1 (porte, tables nues de part et d'autre) | aile 2 | pavillon 1",
        "soupiraux": "sous les fenêtres RDC des ailes (P39, W11)",
    },
    "est": {
        "rdc": c(4, "W17", "±1"), "etage": c(4, "W17", "±1"), "attique": c(2, "W17 (bloc central)", "±1"),
        "axes_y": [-6.9, -2.3, 2.3, 6.9],
        "entraxe_m": c(4.6, "W17 (perspective corrigée), profondeur 18,9 m", "±0,6"),
        "composition": "pavillon NE 1 | bloc central 2 (3 niveaux) | pavillon SE 1 ; persiennes, frontons triangulaires au RDC",
    },
    "ouest": {
        "rdc": c(4, "symétrie de l'est (aucune vue frontale ; W15 et W11 en biais)", "±1"),
        "axes_y": [-6.9, -2.3, 2.3, 6.9],
        "composition": "comme l'est (supposé)",
    },
}

# ---------------------------------------------------------------- niveaux
niveaux = {
    "cour_sablee_sud": c(round(-n_s * MARCHE_S, 2), "LiDAR HD : 25,30 m NGF, RDC 26,85", "±0,1"),
    "cour_nord_parking": c(round(-n_n * MARCHE, 2), "9 marches du perron nord × 16 cm (P38)", "±0,3"),
    "tennis": c(-1.6, "W15, W11 (en contrebas, mur de soutènement côté parking)", "±1,0"),
    "terrasse_sud": c(-0.05, "W01 : portes-fenêtres de plain-pied", "±0,1"),
    "soubassement": c("de -1,3 (sud) / -1,45 (nord) à 0", "perrons, soupiraux W11/P39", "±0,3"),
    "rdc_sol": c(0.0, "D-003", "référence"),
    "bandeau_rdc_etage": c(5.25, "W01 (rapport hauteur/largeur de façade)", "±0,5"),
    "etage_sol": c(5.35, "bandeau + 0,1", "±0,5"),
    "corniche_etage_pavillons": c(10.1, "W01 (corniche des pavillons au niveau de la base de l'attique)", "±0,8"),
    "attique_sol": c(10.3, "W01", "±0,8"),
    "corniche_attique": c(14.0, "W01 (corniche à modillons)", "±1,0"),
    "balustrade_attique_haut": c(15.0, "W01, W15 (balustrade ≈1 m sur la corniche)", "±0,8"),
    "faitage_pavillons": c(11.9, "croupes basses W15/W10, pente ≈27° sur 5,6 m", "±0,8"),
    "faitage_principal": c(17.3, "W15, W10 : croupes en tuiles canal derrière la balustrade, pente ≈27°", "±1,2"),
    "faitage_avant_corps": c(17.0, "W15 (croupe sud), W11 (pyramide nord)", "±1,2"),
    "verriere_haut": c(18.0, "W15, W11 : lanterne vitrée dépassant le faîtage", "±1,2"),
    "souches_haut": c(17.5, "W01, W15 : ≈2,5 m au-dessus de la balustrade", "±1,0"),
    "hauteurs_sous_plafond_estimees": {"rdc": 4.9, "etage": 4.6, "attique": 3.3,
                                         "note": "planchers ≈0,4 m ; à recouper avec les fiches intérieures"},
}

# ---------------------------------------------------------------- toiture
souches = []
for x in (-10.3, -3.3, 3.3, 10.3):
    for y in (-4.1, 4.1):
        souches.append({"x": x, "y": y, "section_m": [1.1, 1.4], "haut_z": 17.5})
toiture = {
    "souches": souches,
    "souches_source": "W15 (x : ±3,6 / ±11,1), W01 (±3,0 / ±9,3), W12 (2 rangées à ±74 px du centre ≈ ±4,1 m)",
    "souches_incertitude": "x ±1,5 m, y ±1,0 m, section ±0,3 m ; 4 paires symétriques (D-011), chapeau mouluré",
    "conduit_metallique": {"x": 16.0, "y": -5.0, "diametre_m": 0.3, "haut_z": 17.0,
                           "source": "W11, W15 (tuyau sur le bloc NE)", "incertitude": "±2 m"},
    "verriere": {"centre": [0.0, 0.0], "longueur_ns_m": 6.5, "largeur_eo_m": 2.8, "hauteur_m": 1.8,
                 "forme": "lanterne à 4 pans (2 longs pans + croupes vitrées), ossature métallique, épi",
                 "source": "W12 (120×55 px, échelle toit ≈19 px/m), W15, W11 (≈2,5 m vue de face)",
                 "incertitude": "±1 m sur la longueur, ±0,5 m sur la largeur"},
    "pente_tuiles_deg": c(27, "tuiles canal, W15/W10", "±5"),
    "balustrade_attique": "tout le pourtour de l'attique, avec acrotères sous les souches",
    "epi_paratonnerre": {"x": 0.0, "y": 0.5, "haut_z": 22.0, "source": "W01 (mât au-dessus de la verrière)", "incertitude": "±1,5 m"},
}

# ---------------------------------------------------------------- abords
TEN_X0, TEN_X1 = -HX - 2.5 - 17.0, -HX - 2.5
TEN_Y0, TEN_Y1 = -23.5, 10.0
tcx, tcy = (TEN_X0 + TEN_X1) / 2, (TEN_Y0 + TEN_Y1) / 2
abords = {
    "tennis": {
        "enceinte": [round(TEN_X0, 2), TEN_Y0, round(TEN_X1, 2), TEN_Y1],
        "court_double": [round(tcx - 5.485, 2), round(tcy - 11.885, 2), round(tcx + 5.485, 2), round(tcy + 11.885, 2)],
        "court_simple_largeur_m": 8.23, "filet_y": round(tcy, 2), "axe": "N-S",
        "surface": "résine rouge brique, lignes blanches",
        "source": "W12 (lignes : 12,7 px/m sol), W15, W11",
        "incertitude": "position ±3 m (écart au pignon ouest supposé 2,5 m), dimensions de l'enceinte ±1,5 m",
        "abords": "mur bahut + balustrade côté est/terrasse, grillage côté ouest, filet à câble",
    },
    "cour_nord_parking": {
        "polygone": r2([(-20, -YP - 1), (30, -YP - 1), (30, -32), (-20, -32)]),
        "voitures_le_long_facade_nord": {"rect": [10.8, -YP - 4.8, 17.5, -YP], "nombre": 3,
                                          "orientation": "en épi, nez vers la façade"},
        "rangee_nord_est": {"de": [1.0, -21.0], "a": [16.0, -27.0], "nombre": 6,
                            "orientation": "en bataille, axe ≈N-S incliné 20°"},
        "sol": "gravier clair / enrobé",
        "source": "W12 (voitures ≈15 px/m), W11", "incertitude": "±4 m",
        "arbre_devant_entree": {"x": 8.0, "y": -15.5, "diametre_couronne_m": 8, "espece": "pin / cyprès",
                                "source": "W12, W11", "incertitude": "±3 m"},
    },
    "allees": {
        "allee_est": {"axe": [[26, 20], [26, -30]], "largeur_m": 6, "nature": "voie sablée reliant cour sablée sud et cour nord",
                      "source": "W16, W12 (bas droite)", "incertitude": "±4 m"},
        "allee_ouest": {"axe": [[-24, 20], [-42, 20], [-42, -30]], "largeur_m": 5,
                        "nature": "sable, contourne le tennis au sud-ouest (palmiers, massifs ronds)",
                        "source": "W12 (haut gauche), W16", "incertitude": "±5 m"},
        "acces_route": "par le nord-est (W11 : route qui descend vers l'est)",
    },
    "cour_sablee_sud": {
        "polygone": r2([(-36, Y_TER), (34, Y_TER), (34, 30.5), (-36, 30.5)]),
        "platanes": {"alignements_x": [-30, 30], "de_y": 25, "a_y": 55, "entraxe_m": 8,
                     "source": "W16", "incertitude": "±5 m ; nombre exact inconnu"},
        "source": "W16, W12 (gauche)", "incertitude": "±5 m sur les limites",
    },
    "pelouse_bassin": {
        "bassin": {"centre": [5.0, 75.0], "dimensions_m": [22, 15], "forme": "ovale bordé de pierre, jet central",
                   "source": "W10 (au fond, vu du nord)", "incertitude": "±20 m en position, ±6 m en taille"},
        "pelouse": "au sud de la cour sablée (W01, W10)",
    },
    "piscine": {"centre": [-40, -38], "dimensions_m": [12, 6], "source": "W15, W16 (fond gauche)",
                "incertitude": "±15 m ; peut-être hors domaine (fiche W15)"},
    "palmiers": [{"x": -22, "y": 13, "source": "W12, W15"}, {"x": -21, "y": 17, "source": "W16"}],
    "oliviers_haie_est": {"x": 21.5, "de_y": 6, "a_y": -1, "source": "W17, W02", "incertitude": "±2 m"},
}

gabarit = {
    "version": 1,
    "repere": {"ref": "D-003", "unite": "m", "x": "est", "y": "sud (façade jardin)", "z": "haut",
               "origine": "centre de l'emprise du château, RDC = 0 (terrasse sud ≈ 0)"},
    "echelle": {
        "longueur_facade_sud_m": c(L, "W01 (proportions de baies : porte-fenêtre ≈1,4 × 3,8 m) + W12 (toit 355 px pour une demi-façade, voitures 15 px/m au sol, rapport toit/sol ≈1,3)", "±3 m (±8 %) ; toutes les cotes en dépendent"),
        "profondeur_ns_m": c(round(2 * YP, 2), "W12 : rapport profondeur/longueur ≈0,5 au bout est", "±2,5 m"),
        "w12": {"nord": "droite de l'image", "ouest": "haut", "sol_px_par_m": {"tennis": 12.7, "voitures": 15.0},
                "toit_px_par_m_bas_image": 19.7,
                "note": "caméra légèrement inclinée : le haut de l'image (ouest) est comprimé ; déplacement des toits par le relief important"},
        "controles": ["court de tennis 23,77 × 10,97 m (W12)", "voitures ≈4,5 m (W12)",
                      "marches ≈16 cm (W01, W15, P38)", "porte-fenêtre RDC ≈3,8 m (W01)"],
    },
    "emprise": {"polygone": r2(emprise), "note": "nu des murs au RDC, sens anti-horaire depuis l'angle SO"},
    "corps": corps,
    "terrasse": {"polygone": r2(terrasse), "niveau_z": -0.05,
                 "balustrade": "balustres pierre sur mur bahut, tout le pourtour sud et est ; soupiraux grillagés dans le mur de face (W01)",
                 "source": "W12, W15, W01", "incertitude": "bord sud ±2 m, bord est ±1,5 m"},
    "perron_sud": perron_sud,
    "perron_nord": perron_nord,
    "escalier_terrasse_est": escalier_terrasse_est,
    "travees": travees,
    "niveaux": niveaux,
    "toiture": toiture,
    "abords": abords,
}

with open(f"{RACINE}/travail/gabarit.json", "w", encoding="utf-8") as f:
    json.dump(gabarit, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- schéma vu de dessus
S = 9                                  # px par mètre
X0, X1, Y0, Y1 = -50, 45, -36, 82      # emprise du dessin (y vers le sud = vers le bas)
W, H = int((X1 - X0) * S), int((Y1 - Y0) * S)
img = Image.new("RGB", (W, H + 40), (246, 243, 236))
d = ImageDraw.Draw(img)
P = lambda x, y: ((x - X0) * S, (y - Y0) * S)
PL = lambda pts: [P(x, y) for x, y in pts]
R = lambda r: [P(r[0], r[1]), P(r[2], r[3])]
try:
    font = ImageFont.truetype("DejaVuSans.ttf", 13)
    fontb = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)
except OSError:
    font = fontb = ImageFont.load_default()

for g in range(-50, 90, 10):
    d.line([P(g, Y0), P(g, Y1)], fill=(228, 224, 214))
    d.line([P(X0, g), P(X1, g)], fill=(228, 224, 214))
d.polygon(PL([(-36, Y_TER), (34, Y_TER), (34, 30.5), (-36, 30.5)]), fill=(232, 222, 196))
d.polygon(PL([(-50, 55), (45, 55), (45, 82), (-50, 82)]), fill=(196, 222, 176))
d.polygon(PL(abords["cour_nord_parking"]["polygone"]), fill=(222, 218, 210))
for a in ("allee_est",):
    (ax0, ay0), (ax1, ay1) = abords["allees"][a]["axe"]
    d.rectangle(R([ax0 - 3, ay1, ax0 + 3, ay0]), fill=(232, 222, 196))
d.line(PL([(-24, 20), (-42, 20), (-42, -30)]), fill=(232, 222, 196), width=5 * S)
cx, cy = abords["pelouse_bassin"]["bassin"]["centre"]
dx, dy = abords["pelouse_bassin"]["bassin"]["dimensions_m"]
d.ellipse(R([cx - dx / 2, cy - dy / 2, cx + dx / 2, cy + dy / 2]), fill=(170, 205, 220), outline=(120, 120, 110), width=2)
pc = abords["piscine"]
d.rectangle(R([pc["centre"][0] - 6, pc["centre"][1] - 3, pc["centre"][0] + 6, pc["centre"][1] + 3]), fill=(110, 200, 220))
t = abords["tennis"]
d.rectangle(R(t["enceinte"]), fill=(160, 92, 84), outline=(90, 90, 90), width=2)
cd = t["court_double"]
d.rectangle(R(cd), outline="white", width=2)
d.line([P(tcx - 4.115, cd[1]), P(tcx - 4.115, cd[3])], fill="white")
d.line([P(tcx + 4.115, cd[1]), P(tcx + 4.115, cd[3])], fill="white")
for sy in (tcy - 6.4, tcy + 6.4):
    d.line([P(tcx - 4.115, sy), P(tcx + 4.115, sy)], fill="white")
d.line([P(tcx, tcy - 6.4), P(tcx, tcy + 6.4)], fill="white")
d.line([P(cd[0] - 0.9, tcy), P(cd[2] + 0.9, tcy)], fill=(30, 30, 30), width=2)
d.polygon(PL(terrasse), fill=(214, 206, 188), outline=(150, 140, 120))
d.polygon(PL(perron_sud["polygone"]), fill=(205, 198, 182), outline=(150, 140, 120))
for i in range(1, n_s):
    yy = Y_PAL + i * G_S
    w = 7.5 + 2.0 * i / n_s
    d.line([P(-w, yy), P(w, yy)], fill=(160, 150, 130))
d.polygon(PL(perron_nord["polygone"]), fill=(205, 198, 182), outline=(150, 140, 120))
d.rectangle(R(escalier_terrasse_est["rect"]), fill=(205, 198, 182), outline=(150, 140, 120))
for (mx, my) in perron_sud["massifs"]["centres"]:
    d.ellipse(R([mx - 1.75, my - 1.75, mx + 1.75, my + 1.75]), fill=(86, 140, 70))
d.polygon(PL(emprise), fill=(238, 228, 205), outline=(60, 50, 40), width=3)
for k in ("SO", "SE", "NO", "NE"):
    d.rectangle(R(corps["pavillons"][k]["rect"]), outline=(120, 100, 80), width=1)
for k in ("ouest", "est"):
    d.rectangle(R(corps["blocs_extremites"][k]["rect"]), outline=(120, 100, 80), width=1)
vr = toiture["verriere"]
d.rectangle(R([-vr["largeur_eo_m"] / 2, -vr["longueur_ns_m"] / 2, vr["largeur_eo_m"] / 2, vr["longueur_ns_m"] / 2]),
            fill=(170, 200, 215), outline=(60, 80, 100), width=2)
for s in souches:
    a, b = s["section_m"]
    d.rectangle(R([s["x"] - a / 2, s["y"] - b / 2, s["x"] + a / 2, s["y"] + b / 2]), fill=(255, 255, 255), outline=(60, 50, 40))
cm = toiture["conduit_metallique"]
d.ellipse(R([cm["x"] - 0.4, cm["y"] - 0.4, cm["x"] + 0.4, cm["y"] + 0.4]), fill=(90, 90, 90))
for x in travees["sud"]["axes_x"]:
    d.line([P(x, YP + 0.3), P(x, YP + 1.2)], fill=(200, 60, 40), width=2)
for x in travees["nord"]["axes_x"]:
    d.line([P(x, -YP - 0.3), P(x, -YP - 1.2)], fill=(200, 60, 40), width=2)
for y in travees["est"]["axes_y"]:
    d.line([P(HX + 0.3, y), P(HX + 1.2, y)], fill=(200, 60, 40), width=2)
    d.line([P(-HX - 0.3, y), P(-HX - 1.2, y)], fill=(200, 60, 40), width=2)
ar = abords["cour_nord_parking"]
v = ar["voitures_le_long_facade_nord"]["rect"]
for i in range(3):
    x = v[0] + 0.6 + i * 2.3
    d.rectangle(R([x, v[1], x + 1.8, v[1] + 4.5]), fill=(60, 60, 70))
(a0, b0), (a1, b1) = ar["rangee_nord_est"]["de"], ar["rangee_nord_est"]["a"]
for i in range(6):
    u = i / 5
    x, y = a0 + (a1 - a0) * u, b0 + (b1 - b0) * u
    ang = math.radians(20)
    pts = [(-0.9, -2.25), (0.9, -2.25), (0.9, 2.25), (-0.9, 2.25)]
    d.polygon(PL([(x + px * math.cos(ang) - py * math.sin(ang), y + px * math.sin(ang) + py * math.cos(ang)) for px, py in pts]), fill=(60, 60, 70))
ab = ar["arbre_devant_entree"]
d.ellipse(R([ab["x"] - 4, ab["y"] - 4, ab["x"] + 4, ab["y"] + 4]), outline=(60, 110, 60), width=3)
pl = abords["cour_sablee_sud"]["platanes"]
for x in pl["alignements_x"]:
    for y in range(pl["de_y"], pl["a_y"] + 1, pl["entraxe_m"]):
        d.ellipse(R([x - 3, y - 3, x + 3, y + 3]), fill=(120, 165, 95), outline=(80, 120, 60))
for p in abords["palmiers"]:
    d.ellipse(R([p["x"] - 1.5, p["y"] - 1.5, p["x"] + 1.5, p["y"] + 1.5]), fill=(90, 150, 80))
ol = abords["oliviers_haie_est"]
d.rectangle(R([ol["x"] - 1, ol["a_y"], ol["x"] + 1, ol["de_y"]]), fill=(130, 150, 100))

def txt(x, y, s, f=font, col=(40, 35, 30)):
    d.text(P(x, y), s, fill=col, font=f, anchor="mm")

txt(0, 6.0, "CHÂTEAU", fontb)
txt(0, -6.2, "verrière, 8 souches", font, (70, 60, 50))
txt(-14.4, 6.5, "pav. SO", font); txt(14.4, 6.5, "pav. SE", font)
txt(-14.4, -6.5, "pav. NO", font); txt(14.4, -6.5, "pav. NE", font)
txt(0, 14.5, "terrasse sud", font)
txt(21, 12.5, "terr. est", font)
txt(0, Y_PAL + 4.5, "perron sud (10 marches)", font)
txt(-7, -16, "perron nord", font)
txt(tcx, TEN_Y0 + 3, "TENNIS", fontb, (255, 255, 255))
txt(0, 40, "cour sablée", fontb, (120, 100, 60))
txt(-24, 68, "pelouse", font, (60, 100, 50))
txt(cx, cy, "bassin", font)
txt(8, -29, "cour d'entrée / parking", fontb, (90, 90, 90))
txt(26, 30, "allée est", font, (120, 100, 60))
txt(-42, 26, "allée ouest", font, (120, 100, 60))
txt(pc["centre"][0], pc["centre"][1] + 5, "piscine ?", font)
# échelle et nord
d.line([P(25, 77), P(35, 77)], fill=(30, 30, 30), width=3)
txt(30, 79.3, "10 m", font)
nx, ny = P(38, -28)
d.polygon([(nx, ny - 26), (nx - 9, ny + 6), (nx + 9, ny + 6)], fill=(30, 30, 30))
d.text((nx, ny + 18), "N", fill=(30, 30, 30), font=fontb, anchor="mm")
d.text((10, H + 12), "Emprise (W12, W01, W11, W15, W17) — D-003, grille 10 m ; "
       "rouge = axes de travées ; abords lointains ±5 à ±20 m.",
       fill=(60, 55, 50), font=font)
img.save(f"{RACINE}/rendus/emprise.png")
print("ok", W, H)

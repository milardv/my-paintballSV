"""P3 : graphe des pièces (travail/graphe.json) et plans proposés (travail/plan-rdc.svg, plan-etage.svg).

Repère D-003 (+X est, +Y sud, mètres), gabarit P2.emprise (travail/gabarit.json).
Les pièces sont des rectangles calés sur les murs du gabarit et sur les axes de travées des façades.
"""
import json
import math
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TRAVAIL = RACINE / "travail"
G = json.loads((TRAVAIL / "gabarit.json").read_text())

# certitude : "sur" (vu et recoupé), "probable" (vu, position déduite), "incertain" (vu de loin ou déduit),
# "non-vu" (volume du gabarit, aucune photo)
PIECES = [
    # ---------- RDC ----------
    dict(id="R-vestibule", nom="Vestibule", niveau="rdc", rect=(-4, -12.45, 4, -3.5), certitude="sur",
         photos=["P19", "P20", "P21", "P41", "W08"], hsp=5.0,
         fenetres=["nord axe 0 (porte d'entrée)", "retours est et ouest de l'avant-corps nord (rideaux rouges)"]),
    dict(id="R-couloir-ouest", nom="Couloir ouest", niveau="rdc", rect=(-10.8, -8.75, -4, -6.4), certitude="probable",
         photos=["P22"], hsp=4.5, fenetres=["nord x=-8,7", "nord x=-5,1 (balconnets)"]),
    dict(id="R-couloir-est", nom="Couloir est", niveau="rdc", rect=(4, -8.75, 10.8, -6.4), certitude="sur",
         photos=["P36"], hsp=4.5, fenetres=["nord x=5,1", "nord x=8,7 (balconnets)"]),
    dict(id="R-passage-ouest", nom="Passage ouest", niveau="rdc", rect=(-4, -3.5, -2.2, 0.8), certitude="sur",
         photos=["P23", "P24"], hsp=4.0, fenetres=[]),
    dict(id="R-passage-est", nom="Passage est", niveau="rdc", rect=(2.2, -3.5, 4, 0.8), certitude="sur",
         photos=["P42"], hsp=4.0, fenetres=[]),
    dict(id="escalier", nom="Escalier impérial", niveau="rdc+etage", rect=(-2.2, -3.5, 2.2, 0.8), certitude="sur",
         photos=["P14", "P15", "P16", "P17", "P18", "P19", "W09"], hsp=11.0,
         fenetres=["verrière zénithale + 4 oculi de coupole"]),
    dict(id="R-petit-salon", nom="Petit salon (sous le repos)", niveau="rdc", rect=(-4, 0.8, 4, 3.9),
         certitude="sur", photos=["P25", "P26"], hsp=3.2, fenetres=[]),
    dict(id="R-salon", nom="Salon bow-window", niveau="rdc", rect=(-4, 3.9, 4, 9.35), certitude="sur",
         photos=["P27", "P28", "P29", "P30", "P31"], hsp=5.0,
         fenetres=["sud x=-2,73 (pan coupé, porte-fenêtre)", "sud x=0 (fenêtre)", "sud x=2,73 (pan coupé, porte-fenêtre)"]),
    dict(id="R-billard", nom="Billard", niveau="rdc", rect=(4, -1.5, 10.8, 8.75), certitude="probable",
         photos=["P32", "P33", "P34", "P35"], hsp=5.0,
         fenetres=["sud x=5,25 (porte-fenêtre)", "sud x=8,85 (porte-fenêtre)"]),
    dict(id="R-degagement-est", nom="Dégagement est + sanitaires", niveau="rdc", rect=(4, -6.4, 10.8, -1.5),
         certitude="incertain", photos=[], hsp=4.5, fenetres=[]),
    dict(id="R-salon-vert", nom="Salon vert (pavillon SE)", niveau="rdc", rect=(10.8, 3.85, 18, 9.45),
         certitude="incertain", photos=["W07", "W14"], hsp=5.0,
         fenetres=["sud x=14,4", "est y=6,9"]),
    dict(id="R-salon-ouest", nom="Salon ouest", niveau="rdc", rect=(-10.8, -1.5, -4, 8.75), certitude="incertain",
         photos=[], hsp=5.0, fenetres=["sud x=-8,85", "sud x=-5,25"]),
    dict(id="R-piece-no", nom="Pièce nord-ouest", niveau="rdc", rect=(-18, -9.45, -10.8, -3.85),
         certitude="incertain", photos=[], hsp=4.5, fenetres=["nord x=-14,4", "ouest y=-6,9"]),
    dict(id="R-service-ouest", nom="(non vu)", niveau="rdc", rect=(-10.8, -6.4, -4, -1.5), certitude="non-vu",
         photos=[], fenetres=[]),
    dict(id="R-bloc-est", nom="Bloc est (non vu)", niveau="rdc", rect=(10.8, -3.85, 18, 3.85), certitude="non-vu",
         photos=[], fenetres=["est y=-2,3", "est y=2,3"]),
    dict(id="R-bloc-ouest", nom="Bloc ouest (non vu)", niveau="rdc", rect=(-18, -3.85, -10.8, 3.85),
         certitude="non-vu", photos=[], fenetres=["ouest y=-2,3", "ouest y=2,3"]),
    dict(id="R-pavillon-so", nom="Pavillon SO (non vu)", niveau="rdc", rect=(-18, 3.85, -10.8, 9.45),
         certitude="non-vu", photos=[], fenetres=["sud x=-14,4", "ouest y=6,9"]),
    dict(id="R-pavillon-ne", nom="Pavillon NE (non vu)", niveau="rdc", rect=(10.8, -9.45, 18, -3.85),
         certitude="non-vu", photos=[], fenetres=["nord x=14,4", "est y=-6,9"]),
    # ---------- ÉTAGE ----------
    dict(id="E-bibliotheque", nom="Bibliothèque", niveau="etage", rect=(-4, -12.45, 4, -5.3), certitude="sur",
         photos=["P00", "P01", "P02", "P03"], hsp=4.8,
         fenetres=["nord axe 0", "retours est et ouest de l'avant-corps nord"]),
    dict(id="E-palier", nom="Palier, galeries et cage sous coupole", niveau="etage", rect=(-5.6, -5.3, 5.6, 1.0),
         certitude="sur", photos=["P04", "P05", "P06", "P07", "P08", "P09"], hsp=11.0,
         fenetres=["verrière + 4 oculi"]),
    dict(id="E-degagement-no", nom="Dégag. NO", niveau="etage", rect=(-10.8, -5.3, -5.6, -3.5),
         certitude="incertain", photos=["P10", "P11", "P12", "P13"], hsp=4.0, fenetres=[]),
    dict(id="E-salle-a-manger", nom="Salle à manger", niveau="etage", rect=(4, 1.0, 10.8, 8.75), certitude="probable",
         photos=["P43", "P44", "P45", "P46", "P50", "P51"], hsp=4.6,
         fenetres=["sud x=5,25 (porte-fenêtre, balconnet)", "sud x=8,85 (porte-fenêtre, balconnet)"]),
    dict(id="E-chambre-1", nom="Chambre 1 (angle SE)", niveau="etage", rect=(10.8, 3.85, 18, 9.45),
         certitude="probable", photos=["P47", "P48", "P49"], hsp=4.0, fenetres=["sud x=14,4", "est y=6,9"]),
    dict(id="E-chambre-2", nom="Chambre 2 à rayures", niveau="etage", rect=(-4, 3.9, 4, 9.35), certitude="probable",
         photos=["P52", "P53", "P54"], hsp=4.0,
         fenetres=["sud x=-2,73", "sud x=0", "sud x=2,73 (balcon du bow)"]),
    dict(id="E-chambre-3", nom="Chambre 3 (bureau, marine)", niveau="etage", rect=(-10.8, 1.0, -4, 8.75),
         certitude="probable", photos=["P55", "P56", "P57"], hsp=4.0, fenetres=["sud x=-8,85", "sud x=-5,25"]),
    dict(id="E-est", nom="(non vu, porte en niche P05)", niveau="etage", rect=(5.6, -5.3, 10.8, 1.0),
         certitude="non-vu", photos=[], fenetres=[]),
    dict(id="E-ouest", nom="(non vu)", niveau="etage", rect=(-10.8, -3.5, -5.6, 1.0), certitude="non-vu",
         photos=[], fenetres=[]),
    dict(id="E-nord-ouest", nom="(non vu)", niveau="etage", rect=(-10.8, -8.75, -4, -5.3), certitude="non-vu",
         photos=[], fenetres=["nord x=-8,7", "nord x=-5,1"]),
    dict(id="E-nord-est", nom="(non vu)", niveau="etage", rect=(4, -8.75, 10.8, -5.3), certitude="non-vu",
         photos=[], fenetres=["nord x=5,1", "nord x=8,7"]),
    dict(id="E-bloc-est", nom="Bloc est (non vu)", niveau="etage", rect=(10.8, -3.85, 18, 3.85), certitude="non-vu",
         photos=[], fenetres=["est y=-2,3", "est y=2,3"]),
    dict(id="E-bloc-ouest", nom="Bloc ouest (non vu)", niveau="etage", rect=(-18, -3.85, -10.8, 3.85),
         certitude="non-vu", photos=[], fenetres=["ouest y=-2,3", "ouest y=2,3"]),
    dict(id="E-pavillon-so", nom="Pavillon SO (non vu)", niveau="etage", rect=(-18, 3.85, -10.8, 9.45),
         certitude="non-vu", photos=[], fenetres=["sud x=-14,4", "ouest y=6,9"]),
    dict(id="E-pavillon-no", nom="Pavillon NO (non vu)", niveau="etage", rect=(-18, -9.45, -10.8, -3.85),
         certitude="non-vu", photos=[], fenetres=["nord x=-14,4", "ouest y=-6,9"]),
    dict(id="E-pavillon-ne", nom="Pavillon NE (non vu)", niveau="etage", rect=(10.8, -9.45, 18, -3.85),
         certitude="non-vu", photos=[], fenetres=["nord x=14,4", "est y=-6,9"]),
]

# portes : (niveau, x, y, orientation du mur "h"|"v", largeur, de, a, type, preuve, sur)
LIAISONS = [
    ("rdc", 0, -12.45, "h", 1.8, "ext-perron-nord", "R-vestibule", "porte d'entrée", "P37-P41 (porte d'axe, imposte fer forgé)", True),
    ("rdc", -4, -7.6, "v", 1.6, "R-vestibule", "R-couloir-ouest", "porte double", "P21, P22, P41", True),
    ("rdc", 4, -7.6, "v", 1.6, "R-vestibule", "R-couloir-est", "porte double", "P36, P41, W08", True),
    ("rdc", -3.1, -3.5, "h", 1.6, "R-vestibule", "R-passage-ouest", "baie entre colonnes", "P23, P41", True),
    ("rdc", 3.1, -3.5, "h", 1.6, "R-vestibule", "R-passage-est", "baie entre colonnes", "P41, P42", True),
    ("rdc", 0, -3.5, "h", 2.2, "R-vestibule", "escalier", "volée centrale", "P18-P20, P41, W09", True),
    ("rdc", -3.1, 0.8, "h", 1.4, "R-passage-ouest", "R-petit-salon", "baie", "P24 (fontaine au fond)", True),
    ("rdc", 3.1, 0.8, "h", 1.4, "R-passage-est", "R-petit-salon", "baie", "P42", True),
    ("rdc", -2.6, 3.9, "h", 1.4, "R-petit-salon", "R-salon", "porte (NO du salon)", "P25, P27, P30", True),
    ("rdc", 2.6, 3.9, "h", 1.4, "R-petit-salon", "R-salon", "porte blanche (NE du salon)", "P25, P30, P31", True),
    ("rdc", 4, 5.0, "v", 1.6, "R-salon", "R-billard", "porte double noyer", "P28, P29, P31, P32", True),
    ("rdc", -4, 5.0, "v", 1.6, "R-salon", "R-salon-ouest", "porte double vert d'eau", "P27, P28", False),
    ("rdc", -4, -1.0, "v", 1.2, "R-passage-ouest", "R-salon-ouest", "porte vert d'eau", "P23, P24 (même teinte que P27)", False),
    ("rdc", 4, -0.6, "v", 1.2, "R-passage-est", "R-billard", "porte blanche", "P42, P26 (porte double fermée) ; destination non vue", False),
    ("rdc", 10.8, 6.0, "v", 1.3, "R-billard", "R-salon-vert", "porte noyer (à droite de la cheminée)", "P31, P33, W07 (table, chaises rouges)", False),
    ("rdc", 10.8, 1.2, "v", 1.3, "R-billard", "R-bloc-est", "porte noyer fermée (à gauche de la cheminée)", "P33, P34", False),
    ("rdc", 8.4, -1.5, "h", 1.3, "R-billard", "R-degagement-est", "porte noyer « sortie »", "P34, P35 puis P36 8 s après", False),
    ("rdc", 5.6, -1.5, "h", 1.2, "R-billard", "R-degagement-est", "porte noyer fermée « sortie »", "P35", False),
    ("rdc", 7.4, -6.4, "h", 1.2, "R-couloir-est", "R-degagement-est", "porte à pictogramme (toilettes)", "P36", True),
    ("rdc", -10.8, -7.6, "v", 1.4, "R-couloir-ouest", "R-piece-no", "porte au fond du couloir", "P22 (porte-fenêtre au fond)", False),
    ("rdc", -7.4, -6.4, "h", 1.2, "R-couloir-ouest", "R-service-ouest", "porte (mur sud du couloir)", "P22", False),
    ("rdc", 0, 9.9, "h", 0.0, "R-salon", "ext-terrasse-sud", "portes-fenêtres des pans coupés", "P27-P29, W01", True),
    ("rdc", 6.9, 8.75, "h", 0.0, "R-billard", "ext-terrasse-sud", "portes-fenêtres", "P32, P33", True),
    # étage
    ("etage", 0, -5.3, "h", 1.5, "E-palier", "E-bibliotheque", "porte (galerie nord)", "P03, P04, P17, P18", True),
    ("etage", 4.8, 1.0, "h", 1.3, "E-palier", "E-salle-a-manger", "porte (fond de galerie est, angle NO)", "P04, P05, P43, P50, P51", True),
    ("etage", -4.8, 1.0, "h", 1.3, "E-palier", "E-chambre-3", "porte à filets verts (fond de galerie ouest)", "P07-P09, P57 (sol à cabochons, lanterne)", False),
    ("etage", 4, 7.2, "v", 1.2, "E-salle-a-manger", "E-chambre-2", "porte ébrasée (refend 0,6 m)", "P50, P52, P53", True),
    ("etage", 10.8, 6.6, "v", 1.4, "E-salle-a-manger", "E-chambre-1", "porte double", "P44, P45, P47 (8 s)", True),
    ("etage", -4, 7.2, "v", 1.2, "E-chambre-2", "E-chambre-3", "porte d'enfilade", "P52, P54, P55, P57", True),
    ("etage", -5.6, -4.4, "v", 1.5, "E-palier", "E-degagement-no", "arcade (tête de volée ouest)", "P09, P10", False),
    ("etage", -10.8, -4.4, "v", 1.4, "E-degagement-no", "E-bloc-ouest", "porte double cintrée", "P10-P12", False),
    ("etage", -8.0, -3.5, "h", 1.0, "E-degagement-no", "E-ouest", "porte ouverte (pièce claire)", "P12, P13", False),
    ("etage", 5.6, -4.4, "v", 1.5, "E-palier", "E-est", "porte double en niche cintrée", "P05", False),
    ("etage", 10.8, 2.5, "v", 1.2, "E-salle-a-manger", "E-bloc-est", "porte double à panneaux chantournés (placard ?)", "P46, P51", False),
]

# photos : niveau, x, y, cap (0 = nord, 90 = est)
PRISES = {
    "rdc": {
        "P19": (0, -1.8, 0), "P20": (0.3, -3.0, 0), "P21": (-1.8, -4.2, 330), "P41": (0, -11.7, 180),
        "P22": (-3.4, -7.6, 270), "P23": (-3.2, -3.9, 180), "P24": (-3.1, -2.4, 180), "P42": (3.1, -2.8, 180),
        "P25": (0, 1.4, 180), "P26": (2.9, 2.6, 30), "P27": (-2.6, 4.6, 170), "P28": (0, 4.7, 180),
        "P29": (-3.0, 7.0, 80), "P30": (0, 9.0, 0), "P31": (-2.2, 8.6, 40), "P32": (4.8, 7.8, 40),
        "P33": (6.3, 2.0, 90), "P34": (6.0, 6.5, 20), "P35": (7.6, 7.6, 350), "P36": (9.6, -7.6, 270),
        "P37": (-2.4, -16.1, 160), "P38": (0, -16.9, 180), "P39": (2.6, -15.3, 100), "P40": (0, -17.9, 180),
    },
    "etage": {
        "P00": (2.4, -6.4, 90), "P01": (0, -6.0, 0), "P02": (-2.4, -6.4, 270), "P03": (2.8, -11.7, 220),
        "P04": (0, -4.8, 180), "P05": (0.6, -4.5, 100), "P06": (0.9, -4.0, 140), "P07": (-0.9, -4.0, 220),
        "P08": (-2.6, -4.6, 210), "P09": (-3.6, -4.3, 260), "P10": (-6.2, -4.4, 270), "P11": (-7.6, -4.4, 270),
        "P12": (-9.0, -4.4, 240), "P13": (-9.6, -4.0, 200), "P14": (-3.0, -3.0, 180), "P15": (-3.0, -0.2, 190),
        "P16": (-1.0, 2.4, 40), "P17": (0, 2.6, 0), "P18": (0.8, 2.6, 355),
        "P43": (4.8, 1.8, 140), "P44": (6.6, 2.2, 180), "P45": (5.0, 3.2, 90), "P46": (9.4, 6.0, 300),
        "P47": (11.4, 6.6, 120), "P48": (12.2, 5.0, 140), "P49": (13.8, 5.6, 100),
        "P50": (9.6, 3.0, 270), "P51": (7.4, 6.4, 0), "P52": (3.4, 7.2, 270), "P53": (-1.6, 8.4, 0),
        "P54": (2.6, 5.8, 270), "P55": (-5.4, 7.8, 290), "P56": (-4.6, 5.4, 270), "P57": (-7.4, 6.4, 20),
    },
}

QUESTIONS = [
    "Billard : long côté nord-sud (2 portes-fenêtres au sud, cheminée sur le mur est entre 2 portes, porte nord vers le couloir est) — ou long côté est-ouest ?",
    "Salle à manger, chambres 1-2-3 : à l'étage, en enfilade sur la façade jardin (sud), d'est en ouest : chambre 1 (angle SE) / salle à manger / chambre 2 (au-dessus du salon) / chambre 3 ?",
    "Salon vert (W07, pan coupé arrondi) = pièce au fond du billard, dans le pavillon SE ?",
    "Côté ouest du RDC (portes vert d'eau P23/P27, fond du couloir P22) : salon ouest symétrique du billard, pièce nord-ouest au bout du couloir ?",
    "Avant-corps nord : le vestibule et la bibliothèque ont des fenêtres sur les retours est et ouest ; l'avant-corps est-il plus saillant que 1,2 m (gabarit) ?",
    "Dégagement P10-P13 et porte en niche P05 : où mènent-ils (chambres côté nord, blocs est/ouest) ?",
]


def compas(cap):
    r = math.radians(cap)
    return math.sin(r), -math.cos(r)


def graphe():
    pieces = []
    for p in PIECES:
        x0, y0, x1, y1 = p["rect"]
        pieces.append({
            "id": p["id"], "nom": p["nom"], "niveau": p["niveau"], "certitude": p["certitude"],
            "photos": p["photos"], "rect_m": [x0, y0, x1, y1],
            "fenetres_sur_facade": p["fenetres"],
            "dimensions_estimees": {"largeur_eo_m": round(x1 - x0, 2), "profondeur_ns_m": round(y1 - y0, 2),
                                    "hauteur_plafond_m": p.get("hsp")},
        })
    liaisons = [{"de": l[5], "a": l[6], "type": l[7], "preuve": l[8], "niveau": l[0],
                 "certitude": "sur" if l[9] else "incertain", "position_m": [l[1], l[2]]} for l in LIAISONS]
    liaisons += [
        {"de": "R-vestibule", "a": "E-palier", "type": "escalier impérial (volée centrale + 2 volées de retour)",
         "preuve": "P14-P19, W09, D-013/D-014", "niveau": "rdc→etage", "certitude": "sur"},
        {"de": "R-couloir-est", "a": "ext-perron-nord", "type": "parcours photo (sortie par le vestibule)",
         "preuve": "P36 13:49:15 → P37 13:49:38", "niveau": "rdc", "certitude": "sur"},
    ]
    sortie = {
        "version": 1, "repere": "D-003 (+X est, +Y sud, m) ; gabarit P2.emprise",
        "parcours_photo": "P00-P13 étage (bibliothèque, palier, dégagement NO) ; P14-P19 descente ; P20-P36 RDC ; "
                          "P37-P40 perron nord ; P41-P42 RDC ; P43-P57 étage (montée P42→P43 en 28 s)",
        "pieces": pieces, "liaisons": liaisons, "questions": QUESTIONS,
    }
    (TRAVAIL / "graphe.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- SVG
K = 22.0          # px par mètre
OX, OY = 450, 400  # position de l'origine (0, 0)


def px(x, y):
    return OX + x * K, OY + y * K


def svg_plan(niveau):
    t = []
    a = t.append
    W, H = 900, 900
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
      'font-family="DejaVu Sans, Arial, sans-serif">')
    a('<rect width="100%" height="100%" fill="#fff"/>')
    titre = "RDC (niveau 0)" if niveau == "rdc" else "1er étage (+5,35 m)"
    a(f'<text x="20" y="32" font-size="20" font-weight="bold" fill="#222">Château Saint-Victor — plan proposé, {titre}</text>')
    a('<text x="20" y="52" font-size="12" fill="#555">P3 — à valider. Repère D-003, gabarit P2.emprise. '
      'Pointillés = position incertaine ; gris = volume non vu.</text>')

    # terrasse / perrons (RDC)
    if niveau == "rdc":
        pts = " ".join(f"{px(*p)[0]:.1f},{px(*p)[1]:.1f}" for p in G["terrasse"]["polygone"])
        a(f'<polygon points="{pts}" fill="#f4efe4" stroke="#b9ad92" stroke-width="1"/>')
        for cle in ("perron_sud", "perron_nord"):
            pts = " ".join(f"{px(*p)[0]:.1f},{px(*p)[1]:.1f}" for p in G[cle]["polygone"])
            a(f'<polygon points="{pts}" fill="#ece5d3" stroke="#b9ad92" stroke-width="1"/>')
        x, y = px(0, 18.6)
        a(f'<text x="{x}" y="{y}" font-size="11" fill="#8a7d60" text-anchor="middle">perron sud (8 marches) — cour sablée</text>')
        x, y = px(0, 13.5)
        a(f'<text x="{x}" y="{y}" font-size="11" fill="#8a7d60" text-anchor="middle">terrasse jardin</text>')
        x, y = px(5.5, -15.0)
        a(f'<text x="{x}" y="{y}" font-size="11" fill="#8a7d60">perron nord (9 marches)</text>')

    # emprise
    pts = " ".join(f"{px(*p)[0]:.1f},{px(*p)[1]:.1f}" for p in G["emprise"]["polygone"])
    a(f'<polygon points="{pts}" fill="#fbfbfb" stroke="none"/>')

    # pièces
    styles = {"sur": ("#e8f1fb", "#1d3f66", ""), "probable": ("#eaf6ea", "#245c2a", ""),
              "incertain": ("#fff6dd", "#8a6100", 'stroke-dasharray="6 4"'),
              "non-vu": ("#efefef", "#9a9a9a", 'stroke-dasharray="3 3"')}
    for p in PIECES:
        if niveau not in p["niveau"].split("+") or (p["id"] == "escalier" and niveau == "etage"):
            continue
        x0, y0, x1, y1 = p["rect"]
        X0, Y0 = px(x0, y0)
        X1, Y1 = px(x1, y1)
        fond, trait, tiret = styles[p["certitude"]]
        if p["id"] == "R-salon":
            poly = [(-4, 3.9), (4, 3.9), (4, 8.75), (3.96, 9.35), (3.1, 9.35), (2.3, 11.25), (-2.3, 11.25),
                    (-3.1, 9.35), (-3.96, 9.35), (-4, 8.75)]
            pts = " ".join(f"{px(*q)[0]:.1f},{px(*q)[1]:.1f}" for q in poly)
            a(f'<polygon points="{pts}" fill="{fond}" stroke="{trait}" stroke-width="1.6" {tiret}/>')
        elif p["id"] == "E-chambre-2":
            poly = [(-4, 3.9), (4, 3.9), (4, 8.75), (3.96, 9.35), (-3.96, 9.35), (-4, 8.75)]
            pts = " ".join(f"{px(*q)[0]:.1f},{px(*q)[1]:.1f}" for q in poly)
            a(f'<polygon points="{pts}" fill="{fond}" stroke="{trait}" stroke-width="1.6" {tiret}/>')
            bal = [(-3.1, 9.35), (-2.3, 11.25), (2.3, 11.25), (3.1, 9.35)]
            pts = " ".join(f"{px(*q)[0]:.1f},{px(*q)[1]:.1f}" for q in bal)
            a(f'<polyline points="{pts}" fill="none" stroke="#777" stroke-width="1.2" stroke-dasharray="2 2"/>')
            cx, cy = px(0, 10.6)
            a(f'<text x="{cx}" y="{cy}" font-size="9" fill="#777" text-anchor="middle">balcon (bow)</text>')
        else:
            a(f'<rect x="{X0:.1f}" y="{Y0:.1f}" width="{X1 - X0:.1f}" height="{Y1 - Y0:.1f}" fill="{fond}" '
              f'stroke="{trait}" stroke-width="1.6" {tiret}/>')
        cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2
        if p["id"] in ("R-passage-ouest", "R-passage-est"):
            a(f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="9.5" fill="{trait}" text-anchor="middle" '
              f'transform="rotate(-90 {cx:.1f} {cy:.1f})">{p["nom"]}</text>')
            continue
        if p["id"] in ("escalier", "E-palier"):
            continue
        mots = p["nom"].split(" ")
        lignes, cur = [], ""
        lim = max(8, int((X1 - X0) / 6.6))
        for m in mots:
            if len(cur) + len(m) + 1 > lim and cur:
                lignes.append(cur)
                cur = m
            else:
                cur = (cur + " " + m).strip()
        lignes.append(cur)
        fs = 12 if p["certitude"] != "non-vu" else 10
        dy0 = cy - (len(lignes) - 1) * fs * 0.6
        if p["id"] in ("R-vestibule",):
            dy0 = Y0 + 22
        for i, l in enumerate(lignes):
            a(f'<text x="{cx:.1f}" y="{dy0 + i * fs * 1.2:.1f}" font-size="{fs}" font-weight="'
              f'{"bold" if p["certitude"] != "non-vu" else "normal"}" fill="{trait}" text-anchor="middle">{l}</text>')
        if p.get("hsp") and p["certitude"] != "non-vu" and (y1 - y0) > 2.5:
            a(f'<text x="{cx:.1f}" y="{dy0 + len(lignes) * fs * 1.2:.1f}" font-size="9" fill="#666" '
              f'text-anchor="middle">{x1 - x0:.1f} × {y1 - y0:.1f} m · h {p["hsp"]} m</text>')

    # escalier
    if niveau == "rdc":
        for i in range(17):
            y = -3.5 + i * (5.4 / 17)
            X0, Y = px(-1.1, y)
            X1, _ = px(1.1, y)
            a(f'<line x1="{X0:.1f}" y1="{Y:.1f}" x2="{X1:.1f}" y2="{Y:.1f}" stroke="#7a4a2a" stroke-width="0.8"/>')
        X0, Y0 = px(-1.1, -3.5)
        X1, Y1 = px(1.1, 1.9)
        a(f'<rect x="{X0}" y="{Y0}" width="{X1 - X0}" height="{Y1 - Y0}" fill="none" stroke="#7a4a2a" stroke-width="1.2"/>')
        x, y = px(0, -3.2)
        x2, y2 = px(0, 1.4)
        a(f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" stroke="#7a4a2a" stroke-width="1.4" marker-end="url(#fl)"/>')
        x, y = px(0, -0.6)
        a(f'<text x="{x - 32}" y="{y}" font-size="9" fill="#7a4a2a" text-anchor="middle" '
          f'transform="rotate(-90 {x - 32} {y})">volée centrale ↑ repos</text>')
    else:
        # vide de la cage, volées latérales, galeries
        X0, Y0 = px(-4, -3.5)
        X1, Y1 = px(4, 3.9)
        a(f'<rect x="{X0}" y="{Y0}" width="{X1 - X0}" height="{Y1 - Y0}" fill="#f6f0e8" stroke="#7a4a2a" stroke-width="1.2"/>')
        for sx in (-1, 1):
            xa, xb = sorted((sx * 2.2, sx * 4))
            for i in range(17):
                y = 1.9 - i * (5.4 / 17)
                A, Y = px(xa, y)
                B, _ = px(xb, y)
                a(f'<line x1="{A:.1f}" y1="{Y:.1f}" x2="{B:.1f}" y2="{Y:.1f}" stroke="#7a4a2a" stroke-width="0.8"/>')
            x, y = px(sx * 3.1, 1.6)
            x2, y2 = px(sx * 3.1, -3.2)
            a(f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" stroke="#7a4a2a" stroke-width="1.4" marker-end="url(#fl)"/>')
        X0, Y0 = px(-4, 1.9)
        X1, Y1 = px(4, 3.9)
        a(f'<rect x="{X0}" y="{Y0}" width="{X1 - X0}" height="{Y1 - Y0}" fill="#efe3d3" stroke="#7a4a2a" stroke-width="1"/>')
        x, y = px(0, 3.0)
        a(f'<text x="{x}" y="{y + 3}" font-size="9" fill="#7a4a2a" text-anchor="middle">repos (+2,7) — tapisserie au mur sud</text>')
        X0, Y0 = px(-2.2, -3.5)
        X1, Y1 = px(2.2, 1.9)
        a(f'<rect x="{X0}" y="{Y0}" width="{X1 - X0}" height="{Y1 - Y0}" fill="#fff" stroke="#7a4a2a" stroke-width="1" stroke-dasharray="4 3"/>')
        x, y = px(0, -0.6)
        a(f'<text x="{x}" y="{y}" font-size="10" fill="#7a4a2a" text-anchor="middle">vide</text>')
        a(f'<text x="{x}" y="{y + 12}" font-size="8.5" fill="#7a4a2a" text-anchor="middle">(volée centrale</text>')
        a(f'<text x="{x}" y="{y + 23}" font-size="8.5" fill="#7a4a2a" text-anchor="middle">en dessous)</text>')
        a(f'<text x="{x}" y="{y + 36}" font-size="8.5" fill="#666" text-anchor="middle">coupole, verrière</text>')
        x, y = px(0, -3.75)
        a(f'<text x="{x}" y="{y}" font-size="9" fill="#1d3f66" text-anchor="middle" font-weight="bold">galerie nord (pont sur le vestibule)</text>')
        for sx, nom in ((-1, "galerie ouest"), (1, "galerie est")):
            x, y = px(sx * 4.8, -2.0)
            a(f'<text x="{x}" y="{y}" font-size="9.5" fill="#1d3f66" text-anchor="middle" '
              f'transform="rotate(-90 {x} {y})">{nom} (arcades)</text>')

    # fenêtres sur les façades (axes du gabarit)
    tr = G["travees"]
    def fen(x, y, ori, l=1.4):
        if ori == "h":
            A, Y = px(x - l / 2, y)
            B, _ = px(x + l / 2, y)
            a(f'<line x1="{A:.1f}" y1="{Y:.1f}" x2="{B:.1f}" y2="{Y:.1f}" stroke="#3a8fd8" stroke-width="5"/>')
        else:
            X, A = px(x, y - l / 2)
            _, B = px(x, y + l / 2)
            a(f'<line x1="{X:.1f}" y1="{A:.1f}" x2="{X:.1f}" y2="{B:.1f}" stroke="#3a8fd8" stroke-width="5"/>')
    for x in tr["sud"]["axes_x"]:
        if abs(x) < 3:
            continue
        fen(x, 9.45 if abs(x) > 10.8 else 8.75, "h")
    # pans coupés du bow et fenêtre centrale
    fen(0, 11.25, "h", 1.6)
    for s in (-1, 1):
        A, B = px(s * 3.1, 9.35), px(s * 2.3, 11.25)
        ma, mb = ((A[0] * 0.75 + B[0] * 0.25), (A[1] * 0.75 + B[1] * 0.25)), ((A[0] * 0.25 + B[0] * 0.75), (A[1] * 0.25 + B[1] * 0.75))
        a(f'<line x1="{ma[0]:.1f}" y1="{ma[1]:.1f}" x2="{mb[0]:.1f}" y2="{mb[1]:.1f}" stroke="#3a8fd8" stroke-width="5"/>')
    for x in tr["nord"]["axes_x"]:
        if x == 0:
            if niveau == "etage":
                fen(0, -12.45, "h")
            continue
        fen(x, -9.45 if abs(x) > 10.8 else -8.75, "h")
    for y in tr["est"]["axes_y"]:
        fen(18, y, "v")
        fen(-18, y, "v")
    for s in (-1, 1):   # retours de l'avant-corps nord
        fen(s * 4, -10.6, "v", 0.9)

    # portes
    for l in LIAISONS:
        if l[0] != niveau or l[4] == 0:
            continue
        x, y, ori, lg = l[1], l[2], l[3], l[4]
        coul = "#b5651d" if l[9] else "#d9a35f"
        if ori == "h":
            A, Y = px(x - lg / 2, y)
            B, _ = px(x + lg / 2, y)
            a(f'<line x1="{A:.1f}" y1="{Y:.1f}" x2="{B:.1f}" y2="{Y:.1f}" stroke="#fff" stroke-width="6"/>')
            a(f'<line x1="{A:.1f}" y1="{Y - 3:.1f}" x2="{B:.1f}" y2="{Y - 3:.1f}" stroke="{coul}" stroke-width="2"/>')
            a(f'<line x1="{A:.1f}" y1="{Y + 3:.1f}" x2="{B:.1f}" y2="{Y + 3:.1f}" stroke="{coul}" stroke-width="2"/>')
        else:
            X, A = px(x, y - lg / 2)
            _, B = px(x, y + lg / 2)
            a(f'<line x1="{X:.1f}" y1="{A:.1f}" x2="{X:.1f}" y2="{B:.1f}" stroke="#fff" stroke-width="6"/>')
            a(f'<line x1="{X - 3:.1f}" y1="{A:.1f}" x2="{X - 3:.1f}" y2="{B:.1f}" stroke="{coul}" stroke-width="2"/>')
            a(f'<line x1="{X + 3:.1f}" y1="{A:.1f}" x2="{X + 3:.1f}" y2="{B:.1f}" stroke="{coul}" stroke-width="2"/>')

    # cheminées repérées
    chem = {"rdc": [(10.8, 3.6, "v")], "etage": [(4, 4.6, "v"), (0, 3.9, "h")]}
    for x, y, o in chem[niveau]:
        X, Y = px(x, y)
        w, h = (10, 26) if o == "v" else (26, 10)
        a(f'<rect x="{X - w / 2:.1f}" y="{Y - h / 2:.1f}" width="{w}" height="{h}" fill="#555"/>')

    # prises de vue
    a('<defs><marker id="fl" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">'
      '<path d="M0,0 L10,5 L0,10 z" fill="#7a4a2a"/></marker>'
      '<marker id="fp" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto">'
      '<path d="M0,0 L10,5 L0,10 z" fill="#c0262d"/></marker></defs>')
    for pid, (x, y, cap) in PRISES[niveau].items():
        X, Y = px(x, y)
        dx, dy = compas(cap)
        a(f'<line x1="{X:.1f}" y1="{Y:.1f}" x2="{X + dx * 16:.1f}" y2="{Y + dy * 16:.1f}" stroke="#c0262d" '
          f'stroke-width="1.5" marker-end="url(#fp)"/>')
        a(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="2.6" fill="#c0262d"/>')
        a(f'<text x="{X - dx * 4 + (3 if dx <= 0 else -3):.1f}" y="{Y - dy * 6 + 3:.1f}" font-size="8.5" fill="#c0262d" '
          f'text-anchor="{"start" if dx <= 0 else "end"}" font-weight="bold">{pid[1:]}</text>')

    # nord + échelle + légende
    a('<g transform="translate(840,110)"><circle r="22" fill="#fff" stroke="#333"/>'
      '<path d="M0,-18 L7,6 L0,1 L-7,6 z" fill="#333"/><text y="-26" font-size="13" text-anchor="middle" '
      'font-weight="bold">N</text><text y="40" font-size="9" text-anchor="middle" fill="#555">(D-003, supposé)</text></g>')
    x0, y0 = 40, 860
    a(f'<line x1="{x0}" y1="{y0}" x2="{x0 + 10 * K}" y2="{y0}" stroke="#333" stroke-width="2"/>')
    for i in range(0, 11, 5):
        a(f'<line x1="{x0 + i * K}" y1="{y0 - 5}" x2="{x0 + i * K}" y2="{y0 + 5}" stroke="#333" stroke-width="1.5"/>')
        a(f'<text x="{x0 + i * K}" y="{y0 + 18}" font-size="10" text-anchor="middle">{i} m</text>')
    lx, ly = 320, 838
    leg = [("rect", "#e8f1fb", "#1d3f66", "", "vu, sûr"), ("rect", "#eaf6ea", "#245c2a", "", "vu, position probable"),
           ("rect", "#fff6dd", "#8a6100", "6 4", "incertain"), ("rect", "#efefef", "#9a9a9a", "3 3", "non vu")]
    for i, (_, f, s, d, txt) in enumerate(leg):
        xx = lx + (i % 2) * 150
        yy = ly + (i // 2) * 20
        a(f'<rect x="{xx}" y="{yy}" width="18" height="12" fill="{f}" stroke="{s}" stroke-width="1.4" '
          f'{"stroke-dasharray=" + chr(34) + d + chr(34) if d else ""}/>')
        a(f'<text x="{xx + 24}" y="{yy + 10}" font-size="10">{txt}</text>')
    xx = lx + 300
    a(f'<line x1="{xx}" y1="{ly + 6}" x2="{xx + 18}" y2="{ly + 6}" stroke="#3a8fd8" stroke-width="5"/>'
      f'<text x="{xx + 24}" y="{ly + 10}" font-size="10">fenêtre (axe de travée)</text>')
    a(f'<line x1="{xx}" y1="{ly + 23}" x2="{xx + 18}" y2="{ly + 23}" stroke="#b5651d" stroke-width="2"/>'
      f'<line x1="{xx}" y1="{ly + 29}" x2="{xx + 18}" y2="{ly + 29}" stroke="#b5651d" stroke-width="2"/>'
      f'<text x="{xx + 24}" y="{ly + 30}" font-size="10">porte (claire = supposée)</text>')
    a(f'<circle cx="{lx + 4}" cy="{ly + 52}" r="2.6" fill="#c0262d"/><line x1="{lx + 4}" y1="{ly + 52}" '
      f'x2="{lx + 20}" y2="{ly + 52}" stroke="#c0262d" stroke-width="1.5" marker-end="url(#fp)"/>'
      f'<text x="{lx + 26}" y="{ly + 56}" font-size="10">photo P.. et direction de vue</text>'
      f'<rect x="{lx + 210}" y="{ly + 46}" width="14" height="8" fill="#555"/>'
      f'<text x="{lx + 230}" y="{ly + 56}" font-size="10">cheminée</text>')
    a('</svg>')
    return "\n".join(t)


def main():
    graphe()
    for niv, nom in (("rdc", "plan-rdc.svg"), ("etage", "plan-etage.svg")):
        (TRAVAIL / nom).write_text(svg_plan(niv))
    print("graphe.json, plan-rdc.svg, plan-etage.svg")


if __name__ == "__main__":
    main()

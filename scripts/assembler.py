# Assemblage des composants : importe les GLB de export/composants dans une scène commune,
# rend des vues de contrôle proches des photos et écrit export/chateau.blend (+ chateau.glb si --glb).
# blender -b --factory-startup --python scripts/assembler.py -- [--glb] [--rapide] [--sans-rendus] [--sans parc,coque]
# Repère D-003 : les GLB sont exportés en Y vers le haut et reviennent en Z vers le haut à l'import.
import bpy
import math
import os
import sys
import time
from mathutils import Vector

T0 = time.time()
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSANTS = os.path.join(RACINE, "export", "composants")
EXPORT = os.path.join(RACINE, "export")
RENDUS = os.path.join(RACINE, "rendus")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RAPIDE = "--rapide" in ARGS
SANS = set(ARGS[ARGS.index("--sans") + 1].split(",")) if "--sans" in ARGS else set()

ORDRE = ["parc", "terrasse", "bati", "toiture", "coque"]


def log(msg):
    print(f"[assembler {time.time() - T0:6.1f}s] {msg}", flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene

# Composants connus d'abord, puis les pièces P4 (piece_*.glb et autres) par ordre alphabétique.
autres = sorted(f[:-4] for f in os.listdir(COMPOSANTS) if f.endswith(".glb") and f[:-4] not in ORDRE)
presents = []
for nom in ORDRE + autres:
    chemin = os.path.join(COMPOSANTS, nom + ".glb")
    if nom in SANS or not os.path.exists(chemin):
        log(f"{nom} : absent ou exclu")
        continue
    avant = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=chemin)
    nouveaux = [o for o in bpy.data.objects if o not in avant]
    coll = bpy.data.collections.new(nom)
    SC.collection.children.link(coll)
    for o in nouveaux:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    presents.append(nom)
    log(f"{nom} : {len(nouveaux)} objets")

# Miroir Y (D-026) : le repère D-003 est indirect, les composants sont l'image miroir du château.
# Après le miroir, +X est l'est et +Y le nord.
miroir = bpy.data.objects.new("miroir_D026", None)
SC.collection.objects.link(miroir)
miroir.scale = (1.0, -1.0, 1.0)
for o in bpy.data.objects:
    if o.parent is None and o is not miroir and o.type != "CAMERA":
        o.parent = miroir


def m(p):
    return (p[0], -p[1], p[2])

# Ciel et soleil (après-midi, lumière du sud-ouest)
monde = bpy.data.worlds.new("ciel")
SC.world = monde
monde.use_nodes = True
bg = next(n for n in monde.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.62, 0.74, 0.92, 1)
bg.inputs["Strength"].default_value = 0.9
soleil = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", "SUN"))
soleil.data.energy = 4.2
soleil.data.angle = math.radians(1.5)
soleil.rotation_euler = (math.radians(40), 0, math.radians(160))
SC.collection.objects.link(soleil)

cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
SC.collection.objects.link(cam)
SC.camera = cam

R = SC.render
for moteur in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        R.engine = moteur
        break
    except TypeError:
        continue
try:
    SC.eevee.taa_render_samples = 8 if RAPIDE else 32
except Exception:
    pass
R.resolution_x, R.resolution_y = (960, 600) if RAPIDE else (1600, 1000)
R.image_settings.file_format = "PNG"

# (nom, position, cible, focale) en coordonnées D-003, passées au miroir ; photos de référence
VUES = [
    ("assemblage_sud", (2.0, 60.0, 8.0), (0.0, 0.0, 6.0), 30),          # W01 : façade jardin
    ("assemblage_sud_haut", (2.0, 52.0, 47.0), (0.5, 1.5, 8.0), 35),    # W15 : aérienne sud
    ("assemblage_nord", (0.0, -38.0, 31.0), (0.0, -1.0, 8.0), 35),      # W11 : aérienne nord
    ("assemblage_entree", (3.0, -26.0, 0.2), (0.0, -9.0, 4.0), 32),     # P39 : perron nord
    ("assemblage_est", (52.0, 4.0, 6.0), (14.0, 0.0, 6.0), 32),         # W17 : façade est
    ("assemblage_parc", (6.0, 196.0, 118.0), (2.0, 40.0, -8.0), 30),    # W18 : vue d'ensemble
]
for nom, pos, cible, focale in ([] if "--sans-rendus" in ARGS else VUES):
    pos, cible = m(pos), m(cible)
    cam.location = pos
    cam.rotation_euler = (Vector(cible) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = focale
    cam.data.clip_end = 2000
    R.filepath = os.path.join(RENDUS, nom + ".png")
    bpy.ops.render.render(write_still=True)
    log(f"rendu {R.filepath}")

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(EXPORT, "chateau.blend"), compress=True)
if "--glb" in ARGS:
    glb = os.path.join(EXPORT, "chateau.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=False,
                              export_apply=True, export_yup=True)
    log(f"GLB écrit ({os.path.getsize(glb) / 1e6:.1f} Mo)")
log("composants : " + ", ".join(presents))

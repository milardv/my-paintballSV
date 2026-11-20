"""Vues de dessus de contrôle du relevé (coque + décors recalés), plafonds masqués.

blender -b --factory-startup --python scripts/vues_releve.py -- rdc etage [composants…]
→ travail/releve-2026-11-19/vues/<niveau>.png
"""
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "export" / "releve-2026-11-19"
VUES = ROOT / "travail" / "releve-2026-11-19" / "vues"
VUES.mkdir(parents=True, exist_ok=True)
args = sys.argv[sys.argv.index("--") + 1:]
niveaux = [a for a in args if a in ("rdc", "etage", "combles")]
comps = [a for a in args if a not in niveaux] or ["coque", "piece_salons", "piece_reception", "piece_chambres",
                                                     "piece_circulations", "piece_combles"]
bpy.ops.wm.read_factory_settings(use_empty=True)
for c in comps:
    f = OUT / (c + ".glb")
    if f.exists():
        bpy.ops.import_scene.gltf(filepath=str(f))
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "OBJECT"
import random
random.seed(3)
for o in sc.objects:
    n = o.name
    if n.startswith("mur_") or n.startswith("appui"):
        o.color = (0.05, 0.05, 0.05, 1)
    elif n.startswith("sol_") or n.startswith("escalier_repos"):
        o.color = (0.92, 0.92, 0.9, 1)
    elif n.startswith("porte_"):
        o.color = (0.1, 0.4, 0.9, 1)
    elif n.startswith("escalier") or n.startswith("garde_corps"):
        o.color = (0.75, 0.2, 0.2, 1)
    elif "releve_20261119" in o.keys() and str(o["releve_20261119"]).startswith("revetement"):
        o.color = (0.95, 0.75, 0.4, 1)
    else:
        o.color = (random.uniform(.2, .6), random.uniform(.5, .9), random.uniform(.3, .7), 1)
sc.render.resolution_x, sc.render.resolution_y = 2000, 1000
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.data.ortho_scale = 35
sc.camera = cam
coupe = {"rdc": 4.4, "etage": 9.6, "combles": 12.6}
for niv in niveaux:
    z = coupe[niv]
    for o in sc.objects:
        if o.type != "MESH":
            continue
        zs = [(o.matrix_world @ v.co).z for v in o.data.vertices] if len(o.data.vertices) < 20000 else \
            [(o.matrix_world @ __import__("mathutils").Vector(b)).z for b in o.bound_box]
        o.hide_render = min(zs) > z - 0.05 or "plafond" in o.name or "coupole" in o.name
    cam.location = (0, 0, z + 20)
    cam.rotation_euler = (0, 0, 0)
    sc.render.filepath = str(VUES / (niv + ".png"))
    bpy.ops.render.render(write_still=True)
    print("VUE", sc.render.filepath, flush=True)

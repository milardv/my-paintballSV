"""Recalage reproductible des composants historiques vers le relevé des plans.

blender -b --factory-startup --python scripts/recaler_releve.py -- coque bati ...
Lit export/composants, écrit export/releve-2026-11-19, jamais les originaux.
Le recalage d'enveloppe n'est pas une validation des cloisons : voir plan-mesure.json.
Les meubles et œuvres conservent leurs dimensions et proportions, leur centre est déplacé.
"""
import os, sys, json, re
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'export/releve-2026-11-19'
OUT.mkdir(parents=True, exist_ok=True)
CAL = json.loads((ROOT / 'travail/releve-2026-11-19/calibration.json').read_text())
AXES = {a: ([p['ancien'] for p in CAL['reperes_communs'][a]],
            [p['nouveau'] for p in CAL['reperes_communs'][a]]) for a in ('x','y')}

# Repères supplémentaires par composant : la terrasse garde ses bords extérieurs (LiDAR HD, D-039/D-040,
# élargissement du 18/11) ; seule la bande contre la façade suit le château.
ANCRES = {'terrasse': {'x': [(-19.5, -19.5), (22.0, 22.0)], 'y': [(14.0, 14.0)]}}
# « table » sans « tablette » : les tablettes de balustrade suivent la terrasse comme leurs balustres.
RIGIDE_EXT = re.compile(r'parasol|transat|salon|chaise|table(?!tte)|bac_|laurier|lampadaire|fauteuil|coussin|pot_')
COMPOSANT = None


def axes(axis):
    a, b = AXES[axis]
    supp = ANCRES.get(COMPOSANT, {}).get(axis, [])
    if not supp:
        return a, b
    pts = sorted(set(zip(a, b)) | set(supp))
    return [p[0] for p in pts], [p[1] for p in pts]


def interp(v, axis):
    a,b = axes(axis)
    # Au-delà du bâti, translation continue plutôt qu'une déformation du domaine IGN.
    return np.interp(v,a,b) + np.minimum(v-a[0],0) + np.maximum(v-a[-1],0)

def mapped(points):
    out = points.copy()
    out[:,0] = interp(points[:,0], 'x')
    out[:,1] = interp(points[:,1], 'y')
    return out

RIGIDE = re.compile(r'tableau|tapisserie|gravure|statuette|statue|fauteuil|chaise|bergere|cabriolet|canape|'
                    r'commode|petrin|panetiere|gueridon|table_basse|table_ronde|table_travail|'
                    r'piano|lustre|lanterne|lampadaire|lampe_|bouquet|vase|buste|livres|'
                    r'billard_table|canon|applique|televiseur|radiateur|pampas')

def traiter(nom):
    global COMPOSANT
    COMPOSANT = nom
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Source non recalée : export/composants, ou RECALER_SOURCE une fois le relevé intégré au jeu.
    source = Path(os.environ.get('RECALER_SOURCE', ROOT / 'export/composants'))
    bpy.ops.import_scene.gltf(filepath=str(source / (nom+'.glb')))
    bpy.context.view_layer.update()
    objects = list(bpy.context.scene.objects)
    world = {o: o.matrix_world.copy() for o in objects}
    # Les collections exportées contiennent parfois des instances de même mesh à des places différentes.
    # Rendre les meshes indépendants avant modification, et préserver les pivots de porte.
    stats = {'composant':nom, 'calibration':'calibration.json', 'objets':[],
             'limite':'Enveloppe recalée ; cloisonnements et raccords à contrôler contre plan-mesure.json.'}
    for o in objects:
        m = world[o]
        o.parent = None
        o.matrix_world = m
        if o.type == 'MESH':
            mesh = o.data.copy()
            o.data = mesh
            local = np.empty(len(mesh.vertices)*3, dtype=np.float64)
            mesh.vertices.foreach_get('co',local)
            local = local.reshape(-1,3)
            matrix = np.array(m)
            points = local @ matrix[:3,:3].T + matrix[:3,3]
            if not len(points):
                continue
            centre = (points.min(axis=0)+points.max(axis=0))/2
            rigid = (nom.startswith('piece_') and bool(RIGIDE.search(o.name))) or \
                (nom == 'terrasse' and bool(RIGIDE_EXT.search(o.name)))
            if rigid:
                target = points + mapped(centre[None,:])[0] - centre
            else:
                target = mapped(points)
            pivot = mapped(np.array([m.translation]))[0]
            # Le mesh est exprimé autour de son pivot en axes monde; une rotation de porte reste possible.
            o.matrix_world = Matrix.Translation(Vector(pivot))
            mesh.vertices.foreach_set('co',(target-pivot).astype(np.float32).ravel())
            mesh.update()
            o['releve_20261119'] = 'rigide' if rigid else 'enveloppe'
            stats['objets'].append({'nom':o.name,'mode':o['releve_20261119'],
                                    'min':target.min(axis=0).tolist(),'max':target.max(axis=0).tolist()})
        elif o.type == 'LIGHT':
            o.matrix_world.translation = Vector(mapped(np.array([m.translation]))[0])
    # Export indépendant : aucune scène Unity ni composant initial remplacé à cette étape.
    bpy.ops.export_scene.gltf(filepath=str(OUT/(nom+'.glb')), export_format='GLB',
                              export_apply=True, export_yup=True, export_lights=True)
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(nom+'.blend')), compress=True)
    (OUT/(nom+'-controle.json')).write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    print('RELEVE',nom,len(stats['objets']),flush=True)

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['bati','toiture','coque']
    for nom in args:
        if not re.fullmatch(r'[a-z_]+',nom):
            raise ValueError('Nom de composant invalide')
        traiter(nom)

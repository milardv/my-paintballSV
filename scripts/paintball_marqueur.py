# Normalise le Spyder MR100 (Sketchfab, CC BY) pour le jeu : un seul maillage, mètres,
# origine sur la main de la poignée pistolet, canon vers -Y Blender (+Z Unity).
import bpy,sys,mathutils,os
racine=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src=os.path.join(racine,"assets/paintball/spyder-mr100/source-sketchfab.glb")
dst=os.path.join(racine,"unity/Assets/Chateau/Paintball/MarqueurSpyder.glb")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes=[o for o in bpy.data.objects if o.type=='MESH']
for o in meshes:
    m=o.matrix_world.copy();o.parent=None;o.matrix_world=m
bpy.ops.object.select_all(action='DESELECT')
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0]
bpy.ops.object.join();obj=bpy.context.active_object;obj.name="MarqueurSpyder"
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
for o in list(bpy.data.objects):
    if o.type!='MESH': bpy.data.objects.remove(o)
poignee=mathutils.Vector((0,0.09,-0.047))
obj.data.transform(mathutils.Matrix.Translation(-poignee))
ys=[v.co.y for v in obj.data.vertices];zs=[v.co.z for v in obj.data.vertices]
print("MARQUEUR bouche_y",round(min(ys),4),"haut",round(max(zs),4),"bas",round(min(zs),4),"faces",len(obj.data.polygons))
bpy.ops.export_scene.gltf(filepath=dst,export_format='GLB',use_selection=False,export_yup=True,export_apply=True,export_image_format='JPEG',export_jpeg_quality=90)

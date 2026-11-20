using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

public static class TexturesWeb
{
    [Serializable] class Image {public string source,texture,path;}
    [Serializable] class Manifest {public Image[] images;}
    public static void Preparer()
    {
        const string dossier="Assets/Chateau/Paintball/WebTextures";
        var manifest=JsonUtility.FromJson<Manifest>(File.ReadAllText(dossier+"/manifest.json"));
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        var sources=new Dictionary<string,Image>();foreach(var image in manifest.images) sources[image.source+"/"+image.texture]=image;
        var copies=new Dictionary<Material,Material>();var textures=new Dictionary<Texture,Texture>();
        long avant=0,apres=0;int compte=0;
        foreach(var r in UnityEngine.Object.FindObjectsByType<Renderer>())
        {
            var mats=r.sharedMaterials;
            for(int i=0;i<mats.Length;i++)
            {
                var mat=mats[i];if(mat==null) continue;
                if(copies.TryGetValue(mat,out var existante)) {mats[i]=existante;continue;}
                Material copie=null;
                foreach(string propriete in mat.GetTexturePropertyNames())
                {
                    var texture=mat.GetTexture(propriete) as Texture2D;if(texture==null) continue;
                    string source=Path.GetFileNameWithoutExtension(AssetDatabase.GetAssetPath(texture));
                    string nom=texture.name;int sampler=nom.LastIndexOf("_sampler",StringComparison.Ordinal);if(sampler>0) nom=nom.Substring(0,sampler);
                    if(!sources.TryGetValue(source+"/"+nom,out var image)) continue;
                    if(copie==null) copie=new Material(mat);
                    if(!textures.TryGetValue(texture,out var remplace))
                    {
                        var importer=(TextureImporter)AssetImporter.GetAtPath(image.path);
                        importer.textureType=TextureImporterType.Default;importer.sRGBTexture=GraphicsFormatUtility.IsSRGBFormat(texture.graphicsFormat);
                        importer.mipmapEnabled=true;importer.isReadable=false;importer.wrapMode=texture.wrapMode;
                        importer.maxTextureSize=1024;importer.textureCompression=TextureImporterCompression.Compressed;
                        importer.SetPlatformTextureSettings(new TextureImporterPlatformSettings {name="WebGL",overridden=true,maxTextureSize=1024,format=TextureImporterFormat.DXT5,compressionQuality=50});
                        importer.SaveAndReimport();remplace=AssetDatabase.LoadAssetAtPath<Texture2D>(image.path);
                        textures[texture]=remplace;compte++;
                        avant+=UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(texture);apres+=UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(remplace);
                    }
                    copie.SetTexture(propriete,remplace);
                }
                if(copie==null && AssetDatabase.GetAssetPath(mat).EndsWith(".glb",StringComparison.OrdinalIgnoreCase)) copie=new Material(mat);
                if(copie==null) {copies[mat]=mat;continue;}
                string path=dossier+"/Materiau"+copies.Count+".mat";
                if(File.Exists(path)) AssetDatabase.DeleteAsset(path);AssetDatabase.CreateAsset(copie,path);
                copies[mat]=copie;mats[i]=copie;
            }
            r.sharedMaterials=mats;
        }
        // A used glTF mesh pulls its whole imported file into the player, including unused
        // embedded textures. Detach scene meshes and collider meshes from those containers.
        const string maillages="Assets/Chateau/Paintball/WebMeshes";Directory.CreateDirectory(maillages);
        var meshes=new Dictionary<Mesh,Mesh>();
        Mesh Copier(Mesh original)
        {
            if(original==null || !AssetDatabase.GetAssetPath(original).EndsWith(".glb",StringComparison.OrdinalIgnoreCase)) return original;
            if(meshes.TryGetValue(original,out var existant)) return existant;
            var copie=UnityEngine.Object.Instantiate(original);string path=maillages+"/Mesh"+meshes.Count+".asset";
            if(File.Exists(path)) AssetDatabase.DeleteAsset(path);AssetDatabase.CreateAsset(copie,path);meshes[original]=copie;return copie;
        }
        AssetDatabase.StartAssetEditing();
        try
        {
            foreach(var f in UnityEngine.Object.FindObjectsByType<MeshFilter>()) f.sharedMesh=Copier(f.sharedMesh);
            foreach(var c in UnityEngine.Object.FindObjectsByType<MeshCollider>()) c.sharedMesh=Copier(c.sharedMesh);
            foreach(var r in UnityEngine.Object.FindObjectsByType<SkinnedMeshRenderer>()) r.sharedMesh=Copier(r.sharedMesh);
        }
        finally { AssetDatabase.StopAssetEditing(); }
        AssetDatabase.SaveAssets();
        Debug.Log($"PAINTBALL WEB MESHES {meshes.Count} externalises");
        File.WriteAllText("../travail/textures-web.json",$"{{\"textures\":{compte},\"memoireOriginale\":{avant},\"memoireWeb\":{apres}}}");
        Debug.Log($"PAINTBALL TEXTURES {compte}, {avant/1e6:F1} -> {apres/1e6:F1} Mo");
    }
}

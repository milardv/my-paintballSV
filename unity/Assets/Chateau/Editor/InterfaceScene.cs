using System.IO;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

public static class InterfaceScene
{
    const string Dossier="Assets/Chateau/Interface";
    public static void Creer()
    {
        if (!File.Exists("Assets/TextMesh Pro/Resources/TMP Settings.asset"))
        {
            TMP_PackageResourceImporter.ImportResources(true,false,false);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        }
        var interfaceVisite=new GameObject("PresentationChateau").AddComponent<InterfaceVisite>();
        interfaceVisite.titrage=Police("CormorantGaramond");
        interfaceVisite.corps=Police("Manrope");
        AssetDatabase.SaveAssets();
    }
    static TMP_FontAsset Police(string nom)
    {
        string chemin=$"{Dossier}/Polices/{nom}-Regular-SDF.asset";
        var asset=AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(chemin);
        if(asset!=null) return asset;
        var source=AssetDatabase.LoadAssetAtPath<Font>($"{Dossier}/Polices/{nom}.ttf");
        asset=TMP_FontAsset.CreateFontAsset(source,90,9,GlyphRenderMode.SDFAA,2048,2048,AtlasPopulationMode.Dynamic,true);
        if(asset==null) throw new System.Exception("Police illisible : "+nom);
        asset.name=nom+"-SDF";
        AssetDatabase.CreateAsset(asset,chemin);
        asset.TryAddCharacters("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸàâäçéèêëîïôöùûüÿœŒ0123456789 .,;:!?/’'-·()&",out _);
        foreach(var atlas in asset.atlasTextures) { atlas.name=nom+" Atlas"; AssetDatabase.AddObjectToAsset(atlas,asset); }
        asset.material.name=nom+" Material"; AssetDatabase.AddObjectToAsset(asset.material,asset);
        EditorUtility.SetDirty(asset); return asset;
    }
}

using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Publication en deux builds : textures DXT pour les ordinateurs, ASTC pour les téléphones et tablettes
// (iPhone et Android n'ont pas le DXT en WebGL : Unity décompresserait chaque texture en mémoire, ~4 fois
// plus lourde, et Safari fermerait l'onglet). index.html choisit le build selon les extensions WebGL
// disponibles (?mobile=1 force le build mobile).
public static class BuildMobile
{
    const string Manifeste = "Assets/Chateau/Paintball/WebTextures/manifest.json";
    [System.Serializable] class Image { public string path; }
    [System.Serializable] class Liste { public Image[] images; }

    // Publication en mode batch (sans l'éditeur chaud) :
    //   Unity -batchmode -quit -nographics -projectPath unity -buildTarget WebGL -executeMethod BuildMobile.PublierBatch
    public static void PublierBatch()
    {
        UnityEditor.SceneManagement.EditorSceneManager.OpenScene("Assets/Scenes/Chateau.unity");
        PublierDouble("../publication", WebGLCompressionFormat.Brotli);
    }

    public static void PublierDouble(string sortie, WebGLCompressionFormat compression)
    {
        var r = PaintballScene.CompilerWeb(sortie, compression, BuildOptions.None, false);
        if (r.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded) throw new System.Exception("build ordinateur en échec");
        string mobile = Path.GetFullPath(sortie).TrimEnd('/') + "-mobile";
        var avant = EditorUserBuildSettings.webGLBuildSubtarget;
        try
        {
            Formats(TextureImporterFormat.ASTC_6x6, 512);
            EditorUserBuildSettings.webGLBuildSubtarget = WebGLTextureSubtarget.ASTC;
            r = PaintballScene.CompilerWeb(mobile, compression, BuildOptions.None, false);
            if (r.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded) throw new System.Exception("build mobile en échec");
        }
        finally
        {
            EditorUserBuildSettings.webGLBuildSubtarget = avant;
            Formats(TextureImporterFormat.DXT5, 1024);
        }
        // Fichiers du build mobile (sauf le chargeur, commun) à côté de ceux du build ordinateur ; index.html pointe dessus.
        string build = Path.Combine(sortie, "Build"), page = Path.Combine(sortie, "index.html");
        string html = File.ReadAllText(page);
        foreach (var f in Directory.GetFiles(Path.Combine(mobile, "Build")))
        {
            string nom = Path.GetFileName(f);
            string cle = nom.Contains(".data") ? "MOBILE_DATA" : nom.Contains(".framework.js") ? "MOBILE_FRAMEWORK" : nom.Contains(".wasm") ? "MOBILE_CODE" : null;
            if (cle == null) continue;
            File.Copy(f, Path.Combine(build, nom), true);
            html = html.Replace("Build/" + cle, "Build/" + nom);
        }
        File.WriteAllText(page, html);
        Directory.Delete(mobile, true);
        Debug.Log("PAINTBALL MOBILE " + (html.Contains("Build/MOBILE_") ? "INCOMPLET" : "ajouté") + " dans " + sortie);
    }

    // Mobile : textures plafonnées à 512 px (mémoire de l'onglet limitée sur iPhone) ; ordinateur : 1024 px.
    static void Formats(TextureImporterFormat format, int taille)
    {
        var liste = JsonUtility.FromJson<Liste>(File.ReadAllText(Manifeste));
        int n = 0;
        AssetDatabase.StartAssetEditing();
        try
        {
            foreach (var image in liste.images)
            {
                if (AssetImporter.GetAtPath(image.path) is not TextureImporter importer) continue;
                var p = importer.GetPlatformTextureSettings("WebGL");
                if (!p.overridden || p.format == format && p.maxTextureSize == taille) continue;
                p.format = format; p.maxTextureSize = taille; importer.SetPlatformTextureSettings(p); importer.SaveAndReimport(); n++;
            }
        }
        finally { AssetDatabase.StopAssetEditing(); }
        Debug.Log($"PAINTBALL TEXTURES {n} en {format} {taille} px");
    }
}

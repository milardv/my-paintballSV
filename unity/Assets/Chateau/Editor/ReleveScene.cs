using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

// Contrôle du relevé dans l'éditeur, sans build WebGL ni remplacement de la scène publiée.
public static class ReleveScene
{
    const string Modeles = "Assets/Chateau/Releve20261119";
    const string ScenePath = "Assets/Scenes/ChateauReleve.unity";

    [MenuItem("Château/Relevé du 19 novembre/Importer les composants")]
    public static void Importer()
    {
        Directory.CreateDirectory(Modeles);
        foreach (string path in Directory.GetFiles("../export/releve-2026-11-19", "*.glb"))
        {
            string target = Path.Combine(Modeles, Path.GetFileName(path));
            if (!File.Exists(target) || File.GetLastWriteTimeUtc(path) > File.GetLastWriteTimeUtc(target))
                File.Copy(path, target, true);
        }
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
    }

    [MenuItem("Château/Relevé du 19 novembre/Construire la scène de contrôle")]
    public static void Construire()
    {
        if (UnityEngine.SceneManagement.SceneManager.GetActiveScene().isDirty)
            throw new InvalidOperationException("Enregistrer la scène active avant le contrôle du relevé.");
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = new GameObject("ChateauReleve");
        root.transform.localScale = new Vector3(1, 1, -1); // miroir D-026
        int meshes = 0;
        foreach (string path in Directory.GetFiles(Modeles, "*.glb").OrderBy(p => p))
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (model == null) throw new InvalidOperationException("Import manquant : " + path);
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(model, root.transform);
            foreach (var filter in instance.GetComponentsInChildren<MeshFilter>())
            {
                if (filter.sharedMesh == null) continue;
                var collider = filter.GetComponent<MeshCollider>();
                if (collider == null) collider = filter.gameObject.AddComponent<MeshCollider>();
                collider.sharedMesh = filter.sharedMesh;
                meshes++;
            }
            foreach (var light in instance.GetComponentsInChildren<Light>())
            {
                light.intensity = Mathf.Clamp(light.intensity / 5000f, .5f, 3.5f);
                light.range = 9;
                light.shadows = LightShadows.None;
            }
        }
        var sun = new GameObject("Soleil").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.intensity = 1.5f;
        sun.transform.rotation = Quaternion.Euler(40, -160, 0);
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(.62f,.72f,.88f);
        RenderSettings.ambientEquatorColor = new Color(.55f,.55f,.5f);
        RenderSettings.ambientGroundColor = new Color(.3f,.28f,.22f);
        EditorSceneManager.SaveScene(scene, ScenePath);
        Debug.Log("RELEVE scène de contrôle : " + meshes + " maillages, " + ScenePath);
    }

    public static void Capturer(string nom, float x, float y, float z, float cibleX, float cibleY, float cibleZ)
    {
        if (UnityEngine.SceneManagement.SceneManager.GetActiveScene().path != ScenePath)
            throw new InvalidOperationException("Ouvrir ChateauReleve avant une capture.");
        string dir = "../travail/releve-2026-11-19/unity";
        Directory.CreateDirectory(dir);
        var go = new GameObject("CameraControleReleve") { hideFlags = HideFlags.HideAndDontSave };
        var camera = go.AddComponent<Camera>();
        // Import GLTFast + miroir D-026 : (-x, z, y).
        go.transform.position = new Vector3(-x, z, y);
        go.transform.LookAt(new Vector3(-cibleX,cibleZ,cibleY));
        camera.nearClipPlane = .03f;
        camera.farClipPlane = 150;
        camera.fieldOfView = 70;
        var rt = new RenderTexture(1280,720,24);
        var image = new Texture2D(1280,720,TextureFormat.RGB24,false);
        var previous = RenderTexture.active;
        try
        {
            camera.targetTexture = rt;
            camera.Render();
            RenderTexture.active = rt;
            image.ReadPixels(new Rect(0,0,1280,720),0,0);
            image.Apply();
            File.WriteAllBytes(Path.Combine(dir,nom + ".png"),image.EncodeToPNG());
        }
        finally
        {
            RenderTexture.active = previous;
            camera.targetTexture = null;
            UnityEngine.Object.DestroyImmediate(image);
            UnityEngine.Object.DestroyImmediate(rt);
            UnityEngine.Object.DestroyImmediate(go);
        }
    }
}

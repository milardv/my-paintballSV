using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Aperçu sans build : outils/apercu.sh écrit travail/apercu/demande (une vue par ligne :
// « nom x y z cap [tangage] [focale] », repère Blender D-003, pieds, cap 0 = vers le sud) ; l'éditeur chaud
// rend chaque vue de la scène enregistrée dans travail/apercu/<nom>.png (décor seulement : pas d'objets
// créés au lancement du jeu), puis écrit travail/apercu/fini.
[InitializeOnLoad]
static class ApercuRapide
{
    static readonly string Dossier = Path.GetFullPath("../travail/apercu");
    static string Demande => Path.Combine(Dossier, "demande");

    static ApercuRapide() { EditorApplication.update += Surveiller; }

    static void Surveiller()
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlaying || !File.Exists(Demande)) return;
        string[] lignes = File.ReadAllLines(Demande);
        File.Delete(Demande);
        string journal = "";
        try
        {
            if (UnityEngine.SceneManagement.SceneManager.GetActiveScene().path != "Assets/Scenes/Chateau.unity")
                EditorSceneManager.OpenScene("Assets/Scenes/Chateau.unity");
            var racine = GameObject.Find("Chateau").transform;
            var go = new GameObject("CameraApercu") { hideFlags = HideFlags.HideAndDontSave };
            var cam = go.AddComponent<Camera>();
            cam.nearClipPlane = 0.05f; cam.farClipPlane = 2000f;
            var rt = new RenderTexture(1280, 720, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4 };
            var image = new Texture2D(1280, 720, TextureFormat.RGB24, false);
            foreach (string l in lignes)
            {
                var v = l.Split((char[])null, System.StringSplitOptions.RemoveEmptyEntries);
                if (v.Length < 5 || v[0].StartsWith("#")) continue;
                float F(int i, float d) => i < v.Length ? float.Parse(v[i], CultureInfo.InvariantCulture) : d;
                float cap = F(4, 0) * Mathf.Deg2Rad;
                // Blender (x, y, z) → Unity (-x, z, -y), puis le miroir D-026 de la racine (comme Capture).
                Vector3 oeil = racine.TransformPoint(new Vector3(-F(1, 0), F(3, 0) + 1.6f, -F(2, 0)));
                Vector3 dir = racine.TransformVector(new Vector3(-Mathf.Sin(cap), 0f, -Mathf.Cos(cap))).normalized;
                go.transform.SetPositionAndRotation(oeil, Quaternion.LookRotation(dir, Vector3.up) * Quaternion.Euler(-F(5, 0), 0, 0));
                cam.fieldOfView = F(6, 60);
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                image.ReadPixels(new Rect(0, 0, 1280, 720), 0, 0); image.Apply();
                RenderTexture.active = null;
                File.WriteAllBytes(Path.Combine(Dossier, v[0] + ".png"), image.EncodeToPNG());
                journal += v[0] + " ok\n";
            }
            cam.targetTexture = null;
            Object.DestroyImmediate(go); Object.DestroyImmediate(rt); Object.DestroyImmediate(image);
        }
        catch (System.Exception e) { journal += "erreur " + e.Message + "\n"; Debug.LogException(e); }
        File.WriteAllText(Path.Combine(Dossier, "fini"), journal);
    }
}

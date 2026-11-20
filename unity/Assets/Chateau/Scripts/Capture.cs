using System;
using System.Collections;
using System.IO;
using UnityEngine;

// Contrôle du build : ChateauSaintVictor.x86_64 -capture <dossier>
// place l'explorateur sur des points de vue fixes, écrit une capture par point puis quitte.
public class Capture : MonoBehaviour
{
    // (nom, position Blender D-003 des pieds, cap en degrés Blender : 0 = vers +Y D-003, c.-à-d. le sud)
    static readonly (string nom, Vector3 pieds, float cap)[] Points =
    {
        ("entree", new Vector3(0f, -15.75f, -1.44f), 0f),
        ("vestibule", new Vector3(0f, -7.6f, 0f), 0f),
        ("escalier", new Vector3(0f, -4.4f, 0f), 0f),
        ("salon", new Vector3(0f, 5.2f, 0f), 0f),
        ("billard", new Vector3(5f, 1.3f, 0f), 0f),
        ("palier", new Vector3(0f, -2.3f, 5.35f), 0f),
        ("salle_a_manger", new Vector3(5f, 1.6f, 5.35f), 0f),
        ("bibliotheque", new Vector3(0.4f, -4.0f, 5.35f), 180f),
        ("chambre_1", new Vector3(12f, 3.5f, 5.35f), 0f),
        ("chambre_2", new Vector3(-1.8f, 4.2f, 5.35f), 35f),
        ("chambre_3", new Vector3(-5.5f, 3.3f, 5.35f), -45f),
        ("jardin", new Vector3(2f, 34f, -1.28f), 180f),
    };

    string dossier;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Demarrer()
    {
        string[] args = Environment.GetCommandLineArgs();
        int i = Array.IndexOf(args, "-capture");
        if (i < 0 || i + 1 >= args.Length) return;
        var go = new GameObject("Capture");
        go.AddComponent<Capture>().dossier = Path.GetFullPath(args[i + 1]);
    }

    IEnumerator Start()
    {
        Directory.CreateDirectory(dossier);
        var explorateur = FindAnyObjectByType<Explorateur>();
        var racine = GameObject.Find("Chateau").transform;
        var cc = explorateur.GetComponent<CharacterController>();
        explorateur.enabled = false;
        cc.enabled = false;
        yield return new WaitForSeconds(2f);
        foreach (var (nom, pieds, cap) in Points)
        {
            // Blender (x, y, z) → Unity (-x, z, -y), puis le miroir D-026 de la racine.
            Vector3 p = racine.TransformPoint(new Vector3(-pieds.x, pieds.z, -pieds.y));
            Vector3 dirBlender = new Vector3(Mathf.Sin(cap * Mathf.Deg2Rad), Mathf.Cos(cap * Mathf.Deg2Rad), 0f);
            Vector3 dir = racine.TransformVector(new Vector3(-dirBlender.x, 0f, -dirBlender.y));
            explorateur.transform.SetPositionAndRotation(p + Vector3.up * 0.05f, Quaternion.LookRotation(dir, Vector3.up));
            yield return new WaitForSeconds(1.5f);
            yield return new WaitForEndOfFrame();
            Texture2D image = ScreenCapture.CaptureScreenshotAsTexture();
            File.WriteAllBytes(Path.Combine(dossier, nom + ".png"), image.EncodeToPNG());
            Destroy(image);
            Debug.Log($"CAPTURE {nom} {explorateur.transform.position}");
        }
        yield return new WaitForSeconds(0.5f);
        Application.Quit();
    }
}

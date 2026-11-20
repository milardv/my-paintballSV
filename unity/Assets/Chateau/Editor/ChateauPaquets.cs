using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;

public static class ChateauPaquets
{
    static AddAndRemoveRequest requete;

    // Lancé en batch : -executeMethod ChateauPaquets.Installer
    public static void Installer()
    {
        requete = Client.AddAndRemove(new[] { "com.unity.cloud.gltfast", "com.unity.ai.assistant@2.21.0-pre.2" });
        while (!requete.IsCompleted) System.Threading.Thread.Sleep(200);
        if (requete.Status == StatusCode.Success)
            foreach (var p in requete.Result) Debug.Log($"PAQUET {p.name} {p.version}");
        else
            Debug.LogError($"PAQUETS ECHEC {requete.Error?.message}");
        EditorApplication.Exit(requete.Status == StatusCode.Success ? 0 : 1);
    }
}

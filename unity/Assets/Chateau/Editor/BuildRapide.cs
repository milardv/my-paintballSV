using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Debug = UnityEngine.Debug;

// Boucle rapide : un éditeur Unity reste ouvert (outils/editeur.sh) et compile le jeu web à la demande,
// sans redémarrer l'éditeur ni réimporter le projet. outils/build-rapide.sh écrit la demande dans
// travail/build-rapide/demande ; l'éditeur rafraîchit les assets (recompilation des scripts si besoin,
// la demande survit au rechargement), compile, puis écrit travail/build-rapide/resultat.json.
//   web   : scripts et ressources seulement, la scène enregistrée telle quelle (le cas courant) ;
//   scene : réapplique d'abord les étapes de PaintballScene.MiseAJour (marqueur, matériaux, NavMesh,
//           occlusion), à demander quand l'éditeur de scène (PaintballScene, ChateauScene) a changé ;
//   publication : builds ordinateur et mobile en Brotli dans ../publication, à déployer ensuite ;
//   double : les deux builds en local (build/web, non compressés) ;
//   complet : réimport des GLB et reconstruction de la scène, puis build local.
// Build sans compression (le serveur local n'en a pas besoin) ; la livraison reste BuildWebMiseAJour.
[InitializeOnLoad]
static class BuildRapide
{
    static readonly string Dossier = Path.GetFullPath("../travail/build-rapide");
    static string Demande => Path.Combine(Dossier, "demande");
    static string Resultat => Path.Combine(Dossier, "resultat.json");
    static bool enCours;

    static BuildRapide() { EditorApplication.update += Surveiller; }

    [System.Serializable] class Rapport { public string mode, statut, erreur; public float secondes, compilation; public float mo; }

    static void Surveiller()
    {
        if (enCours || EditorApplication.isCompiling || EditorApplication.isUpdating || !File.Exists(Demande)) return;
        string mode = File.ReadAllText(Demande).Trim(); if (mode == "") mode = "web";
        // Rafraîchir d'abord : si des scripts ont changé, Unity recompile et recharge le domaine ;
        // la demande reste sur le disque et sera reprise au prochain passage.
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        if (EditorApplication.isCompiling) return;
        File.Delete(Demande);
        var rapport = new Rapport { mode = mode };
        if (EditorUtility.scriptCompilationFailed) { rapport.statut = "echec"; rapport.erreur = "erreurs de compilation C# (voir la console de l'éditeur)"; Ecrire(rapport); return; }
        enCours = true;
        var chrono = Stopwatch.StartNew();
        try
        {
            // complet : réimporte les GLB des composants et reconstruit toute la scène (ChateauScene.Construire,
            // préparation web des textures), à demander après un changement de modèle Blender.
            if (mode == "complet") { VerificationBalistique.Verifier(); ChateauScene.Construire(); TexturesWeb.Preparer(); }
            else if (mode == "scene") PaintballScene.PreparerScene();
            else if (UnityEngine.SceneManagement.SceneManager.GetActiveScene().path != "Assets/Scenes/Chateau.unity")
                EditorSceneManager.OpenScene("Assets/Scenes/Chateau.unity");
            // publication : copie à livrer (Brotli, ../publication), comme PaintballScene.BuildWebPublication.
            // publication : copie à livrer (Brotli, ../publication), builds ordinateur et mobile (BuildMobile) ;
            // double : les deux builds en local, non compressés (?mobile=1 force le build mobile).
            if (mode == "publication" || mode == "double")
            {
                BuildMobile.PublierDouble(mode == "publication" ? "../publication" : "../build/web",
                    mode == "publication" ? WebGLCompressionFormat.Brotli : WebGLCompressionFormat.Disabled);
                rapport.statut = "ok";
            }
            else
            {
                var r = PaintballScene.CompilerWeb("../build/web", WebGLCompressionFormat.Disabled, BuildOptions.None, false);
                rapport.statut = r.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded ? "ok" : "echec";
                rapport.compilation = (float)r.summary.totalTime.TotalSeconds; rapport.mo = r.summary.totalSize / 1e6f;
            }
        }
        catch (System.Exception e) { rapport.statut = "echec"; rapport.erreur = e.Message; Debug.LogException(e); }
        finally { enCours = false; }
        rapport.secondes = (float)chrono.Elapsed.TotalSeconds;
        Ecrire(rapport);
    }

    static void Ecrire(Rapport r)
    {
        Directory.CreateDirectory(Dossier);
        File.WriteAllText(Resultat + ".tmp", JsonUtility.ToJson(r)); File.Copy(Resultat + ".tmp", Resultat, true); File.Delete(Resultat + ".tmp");
        Debug.Log($"BUILD RAPIDE {r.mode} {r.statut} {r.secondes:F0} s {r.erreur}");
    }
}

using System.Collections.Generic;
using System.Diagnostics;
using Unity.Profiling;
using Unity.Profiling.LowLevel.Unsafe;
using UnityEngine;

// Répartition du temps d'image pour la vérification navigateur (window.paintballState.perf).
// Les marqueurs de temps (thread principal, physique, scripts, rendu) n'existent que dans un
// Development build ; les compteurs de rendu (draw calls, batches) aussi en Release.
// Les sections propres au jeu (billes, bots) sont chronométrées directement.
public class MesuresPerf : MonoBehaviour
{
    // Nom affiché, marqueur ou compteur Unity (cherché par son nom), conversion (ns -> ms ou valeur brute).
    static readonly (string nom, string marqueur, bool temps)[] Definitions =
    {
        ("mainThreadMs", "Main Thread", true),
        ("playerLoopMs", "PlayerLoop", true),
        ("physicsMs", "FixedUpdate.PhysicsFixedUpdate", true),
        ("physicsSimulateMs", "Physics.Simulate", true),
        ("sphereCastMs", "Physics.SphereCast", true),
        ("raycastMs", "Physics.Raycast", true),
        ("physicsQueries", "Physics Queries", false),
        ("fixedScriptsMs", "FixedBehaviourUpdate", true),
        ("updateScriptsMs", "BehaviourUpdate", true),
        ("lateScriptsMs", "LateBehaviourUpdate", true),
        ("animatorsMs", "Animators.Update", true),
        ("skinningMs", "PostLateUpdate.UpdateAllSkinnedMeshes", true),
        ("uiMs", "PostLateUpdate.PlayerUpdateCanvases", true),
        ("renderMs", "PostLateUpdate.FinishFrameRendering", true),
        ("cameraStackMs", "RenderCameraStack", true),
        ("drawCalls", "Draw Calls Count", false),
        ("setPass", "SetPass Calls Count", false),
        ("trianglesK", "Triangles Count", false),
        ("shadowCasters", "Shadow Casters Count", false),
        ("activeBodies", "Active Dynamic Bodies", false),
        ("activeKinematic", "Active Kinematic Bodies", false),
        ("gcAllocKB", "GC Allocated In Frame", false),
    };
    const int Echantillons = 120;
    readonly List<ProfilerRecorder> enregistreurs = new();
    readonly List<int> indices = new();
    public static readonly Stopwatch Billes = new(), Bots = new();
    readonly float[] billesMs = new float[Echantillons], botsMs = new float[Echantillons], pasFixes = new float[Echantillons];
    int index, compte, pasImage;
    public static MesuresPerf Instance { get; private set; }

    void OnEnable()
    {
        Instance = this;
        var poignees = new List<ProfilerRecorderHandle>();
        ProfilerRecorderHandle.GetAvailable(poignees);
        var parNom = new Dictionary<string, ProfilerRecorderHandle>();
        foreach (var h in poignees) parNom[ProfilerRecorderHandle.GetDescription(h).Name] = h;
        for (int i = 0; i < Definitions.Length; i++)
        {
            if (!parNom.TryGetValue(Definitions[i].marqueur, out var h)) continue;
            var r = new ProfilerRecorder(h, Echantillons, ProfilerRecorderOptions.Default);
            r.Start();
            enregistreurs.Add(r); indices.Add(i);
        }
    }

    void OnDisable()
    {
        foreach (var r in enregistreurs) r.Dispose();
        enregistreurs.Clear(); indices.Clear();
    }

    void FixedUpdate() => pasImage++;

    void LateUpdate()
    {
        billesMs[index] = (float)Billes.Elapsed.TotalMilliseconds; Billes.Reset();
        botsMs[index] = (float)Bots.Elapsed.TotalMilliseconds; Bots.Reset();
        pasFixes[index] = pasImage; pasImage = 0;
        index = (index + 1) % Echantillons; compte = Mathf.Min(compte + 1, Echantillons);
    }

    static float Moyenne(float[] t, int n) { float s = 0; for (int i = 0; i < n; i++) s += t[i]; return n == 0 ? 0 : s / n; }

    // Moyennes sur les 120 dernières images, dans l'ordre : noms puis valeurs.
    public void Relever(out string[] noms, out float[] valeurs)
    {
        var n = new List<string> { "billesMs", "botsMs", "fixedStepsPerFrame" };
        var v = new List<float> { Moyenne(billesMs, compte), Moyenne(botsMs, compte), Moyenne(pasFixes, compte) };
        for (int k = 0; k < enregistreurs.Count; k++)
        {
            var r = enregistreurs[k]; var d = Definitions[indices[k]];
            int c = r.Count; if (c == 0) continue;
            double s = 0; for (int i = 0; i < c; i++) s += r.GetSample(i).Value;
            double m = s / c;
            n.Add(d.nom);
            v.Add((float)(d.temps ? m * 1e-6 : d.nom == "trianglesK" ? m / 1000 : d.nom == "gcAllocKB" ? m / 1024 : m));
        }
        noms = n.ToArray(); valeurs = v.ToArray();
    }

    // Noms des marqueurs disponibles dans ce build, filtrés, pour ajuster les définitions.
    public static string Disponibles(string filtre)
    {
        var poignees = new List<ProfilerRecorderHandle>();
        ProfilerRecorderHandle.GetAvailable(poignees);
        var noms = new List<string>();
        foreach (var h in poignees)
        {
            var d = ProfilerRecorderHandle.GetDescription(h);
            if (string.IsNullOrEmpty(filtre) || d.Name.IndexOf(filtre, System.StringComparison.OrdinalIgnoreCase) >= 0) noms.Add(d.Name);
        }
        noms.Sort();
        return string.Join("|", noms);
    }
}

using UnityEngine;
using UnityEngine.Rendering;

// Nuages : dôme bas (240 m au zénith, sous l'horizon au bord) qui suit la caméra, texture de cumulus
// (Resources/Ambiance/Nuages, AmbianceScene) ancrée au monde et poussée par le vent. Teinte selon le soleil
// (blancs le jour, dorés au couchant, sombres la nuit) et grisée quand il neige.
public class Atmosphere : MonoBehaviour
{
    const float Zenith = 240, Rayon = 800, Bord = -40, Echelle = 900;
    static readonly Vector2 Vent = new(.0035f, .0012f);
    Material nuages;
    Transform dome;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        var m = Resources.Load<Material>("Ambiance/Nuages");
        if (m == null || FindAnyObjectByType<Atmosphere>() != null) return;
        var a = new GameObject("Atmosphere").AddComponent<Atmosphere>();
        a.nuages = new Material(m);
        a.dome = new GameObject("DomeNuages").transform; a.dome.SetParent(a.transform, false);
        a.dome.gameObject.AddComponent<MeshFilter>().sharedMesh = Dome();
        var r = a.dome.gameObject.AddComponent<MeshRenderer>(); r.sharedMaterial = a.nuages;
        r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false; r.lightProbeUsage = LightProbeUsage.Off;
    }

    static Mesh Dome()
    {
        const int anneaux = 18, secteurs = 64;
        var v = new Vector3[(anneaux + 1) * (secteurs + 1)]; var t = new int[anneaux * secteurs * 6];
        for (int i = 0; i <= anneaux; i++)
            for (int j = 0; j <= secteurs; j++)
            {
                float r = Rayon * i / anneaux, a = j * Mathf.PI * 2 / secteurs, k = r / Rayon;
                v[i * (secteurs + 1) + j] = new Vector3(Mathf.Cos(a) * r, Zenith + (Bord - Zenith) * k * k, Mathf.Sin(a) * r);
            }
        int n = 0;
        for (int i = 0; i < anneaux; i++)
            for (int j = 0; j < secteurs; j++)
            {
                int a = i * (secteurs + 1) + j, b = a + secteurs + 1;
                t[n++] = a; t[n++] = a + 1; t[n++] = b; t[n++] = a + 1; t[n++] = b + 1; t[n++] = b;
            }
        var m = new Mesh { name = "DomeNuages", vertices = v, triangles = t };
        m.RecalculateNormals(); m.bounds = new Bounds(Vector3.up * 100, Vector3.one * Rayon * 2.2f);
        return m;
    }

    void LateUpdate()
    {
        var cam = Camera.main; if (cam == null || dome == null) return;
        Vector3 c = cam.transform.position;
        dome.position = c;
        // Texture ancrée au monde (pas de nuages qui suivent le joueur), qui dérive avec le vent.
        nuages.SetTextureScale("_BaseMap", Vector2.one * (Rayon * 2 / Echelle));
        nuages.SetTextureOffset("_BaseMap", Vent * Time.time + new Vector2(c.x, c.z) / Echelle);
        float e = MomentJournee.Instance != null ? MomentJournee.Instance.Elevation : 40;
        float jour = Mathf.SmoothStep(0, 1, Mathf.InverseLerp(-6, 10, e)), bas = Mathf.InverseLerp(25, 0, e), g = Neige.Gris;
        Color teinte = Color.Lerp(new Color(.13f, .14f, .2f, .55f), Color.Lerp(new Color(1, 1, 1, .92f), new Color(1f, .74f, .58f, .95f), bas * bas), jour);
        nuages.SetColor("_BaseColor", Color.Lerp(teinte, new Color(.74f * jour + .1f, .76f * jour + .1f, .8f * jour + .12f, 1), g));
    }
}

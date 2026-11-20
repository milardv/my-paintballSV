using UnityEngine;

// Piano droit du petit salon : E pour s'asseoir et jouer, E pour se lever. La musique (pièce originale,
// synthétisée au premier usage) sort du piano en son 3D : on l'entend d'autant moins qu'on s'en éloigne.
// En ligne, les autres joueurs reçoivent « piano » et entendent le même morceau au même endroit.
public class Piano : Vehicule
{
    public static Piano Instance { get; private set; }
    public override string Nom => "le piano";
    public override string Libelle(Explorateur e) => "Jouer du piano";

    AudioSource local, distant;
    Vector3 siege, face;
    int joueursDistants;
    static AudioClip morceau;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        if (GameObject.Find("Chateau") == null || Instance != null) return;
        var r = GameObject.Find("petit_salon_piano");
        if (r == null) { Debug.LogWarning("PIANO absent de la scène"); return; }
        Instance = r.AddComponent<Piano>();
    }

    void Start()
    {
        var b = GetComponentInChildren<Renderer>().bounds;
        // Le clavier est sur un grand côté, du côté libre (l'autre est contre le mur).
        var cotes = b.extents.x > b.extents.z ? new[] { Vector3.forward, Vector3.back } : new[] { Vector3.right, Vector3.left };
        float libre = -1; face = cotes[0];
        foreach (var d in cotes)
        {
            float ext = Mathf.Abs(Vector3.Dot(d, b.extents));
            float dist = Physics.Raycast(b.center + d * (ext + .05f), d, out var h, 3f, Physics.DefaultRaycastLayers,
                QueryTriggerInteraction.Ignore) ? h.distance : 3f;
            if (dist > libre) { libre = dist; face = d; }
        }
        float profondeur = Mathf.Abs(Vector3.Dot(face, b.extents));
        siege = new Vector3(b.center.x, b.min.y, b.center.z) + face * (profondeur + .55f);
        cap = Quaternion.LookRotation(-face).eulerAngles.y;
        // Banquette devant le clavier.
        var banc = GameObject.CreatePrimitive(PrimitiveType.Cube); banc.name = "PianoBanquette";
        Destroy(banc.GetComponent<Collider>());
        banc.transform.SetParent(transform, true);
        banc.transform.SetPositionAndRotation(siege + Vector3.up * .23f, Quaternion.LookRotation(face));
        banc.transform.localScale = Vector3.Scale(new Vector3(.9f, .46f, .36f), new Vector3(1 / transform.lossyScale.x, 1 / transform.lossyScale.y, 1 / Mathf.Abs(transform.lossyScale.z)));
        banc.GetComponent<Renderer>().sharedMaterial = Materiau(new Color(.12f, .06f, .03f), .55f);
        local = Source("PianoLocal"); distant = Source("PianoDistant");
    }

    AudioSource Source(string nom)
    {
        var go = new GameObject(nom); go.transform.SetParent(transform, false);
        go.transform.position = GetComponentInChildren<Renderer>().bounds.center;
        var s = go.AddComponent<AudioSource>();
        s.spatialBlend = 1; s.rolloffMode = AudioRolloffMode.Logarithmic; s.minDistance = 2.5f; s.maxDistance = 45f;
        s.dopplerLevel = 0; s.loop = true; s.playOnAwake = false; s.volume = .9f;
        return s;
    }

    public override Vector3 PositionPilote => siege + Vector3.down * .45f;   // assis : les yeux à 1,2 m
    public override Vector3 PointDescente => siege + face * .5f;

    public override void Interagir(Explorateur e)
    {
        if (Pilote != null) return;
        base.Interagir(e);
        Jouer(local, true);
        ClientReseau.Instance?.EnvoyerPiano(true);
        ObjetsDomaine.Annoncer("Au piano ! (E pour se lever)");
    }

    public override void Liberer()
    {
        base.Liberer();
        Jouer(local, false);
        ClientReseau.Instance?.EnvoyerPiano(false);
    }

    public override void Conduire(Vector2 entree, float dt) { }   // assis : on ne bouge pas, on regarde librement

    public static void Distant(int joueur, bool joue)
    {
        if (Instance == null) return;
        Instance.joueursDistants = Mathf.Max(0, Instance.joueursDistants + (joue ? 1 : -1));
        Instance.Jouer(Instance.distant, Instance.joueursDistants > 0);
    }

    void Jouer(AudioSource s, bool oui)
    {
        if (s == null) return;
        if (!oui) { s.Stop(); return; }
        if (s.isPlaying) return;
        s.clip = Morceau();
        s.time = 0; s.Play();
    }

    // ---------- Synthèse ----------
    // Valse lente originale en la mineur (la, fa, do, mi), main gauche en arpèges, main droite en phrases de quatre
    // mesures. Timbre : partiels légèrement inharmoniques, attaque franche, extinction exponentielle par note.
    static AudioClip Morceau()
    {
        if (morceau != null) return morceau;
        const int frequence = 22050;
        const float noire = .62f;               // ≈ 97 à la noire, mesure à 3 temps
        int[][] accords = { new[] { 45, 52, 57, 60 }, new[] { 41, 48, 53, 57 }, new[] { 48, 55, 60, 64 }, new[] { 40, 47, 52, 56 },
                            new[] { 45, 52, 57, 60 }, new[] { 38, 45, 50, 53 }, new[] { 40, 47, 52, 56 }, new[] { 45, 52, 57, 64 } };
        int[] melodie = { 76, 74, 72, 74, 72, 69, 72, 71, 69, 71, 68, 64,
                          76, 77, 76, 74, 72, 74, 72, 71, 72, 71, 69, 68,
                          69, 72, 76, 79, 77, 76, 74, 72, 74, 76, 71, 68,
                          69, 71, 72, 74, 72, 71, 69, 68, 71, 69, 69, 69 };
        int mesures = accords.Length * 2;
        int n = Mathf.CeilToInt((mesures * 3 * noire + 2f) * frequence);
        var s = new float[n];
        void Note(int midi, float debut, float duree, float force)
        {
            float f0 = 440f * Mathf.Pow(2, (midi - 69) / 12f);
            int i0 = (int)(debut * frequence), longueur = (int)((duree + 1.2f) * frequence);
            float amort = 2.2f + (midi - 40) * .05f;
            for (int k = 0; k < longueur && i0 + k < n; k++)
            {
                float t = (float)k / frequence;
                float env = Mathf.Min(1, t / .004f) * Mathf.Exp(-amort * t) * (t > duree ? Mathf.Exp(-9 * (t - duree)) : 1);
                if (env < .0005f) break;
                float v = 0;
                for (int h = 1; h <= 5; h++)
                {
                    float fh = f0 * h * (1 + .0004f * h * h);
                    v += Mathf.Sin(2 * Mathf.PI * fh * t) * Mathf.Exp(-h * .9f) * Mathf.Exp(-amort * (h - 1) * .35f * t);
                }
                s[i0 + k] += v * env * force;
            }
        }
        for (int m = 0; m < mesures; m++)
        {
            var a = accords[m % accords.Length];
            float t0 = m * 3 * noire;
            Note(a[0] - 12, t0, noire * 2.8f, .32f);
            Note(a[1], t0 + noire, noire * .9f, .2f); Note(a[2], t0 + noire * 1.5f, noire * .9f, .18f);
            Note(a[3], t0 + noire * 2, noire * .9f, .18f); Note(a[2], t0 + noire * 2.5f, noire * .5f, .15f);
            for (int k = 0; k < 3; k++)
            {
                int midi = melodie[(m * 3 + k) % melodie.Length];
                Note(midi, t0 + k * noire, noire * (k == 2 ? 1.3f : .95f), k == 0 ? .34f : .27f);
            }
        }
        float max = .001f; foreach (var x in s) max = Mathf.Max(max, Mathf.Abs(x));
        for (int i = 0; i < n; i++) s[i] = s[i] / max * .8f;
        morceau = AudioClip.Create("ValseDuPetitSalon", n, 1, frequence, false);
        morceau.SetData(s, 0);
        return morceau;
    }

    void OnDestroy() { if (Instance == this) Instance = null; }
}

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

// Neige (option du joueur, Reglages.Neige) : le ciel se couvre, des flocons tombent autour de la caméra (pas à
// l'intérieur), le sol à ciel ouvert blanchit peu à peu (couche précalculée CoucheNeige, AmbianceScene : le seuil
// de découpe descend), l'ambiance devient hivernale et chaque pas sur la neige laisse une empreinte à la couleur
// du joueur — et des bots en partie. Quand on coupe la neige, elle fond.
public class Neige : MonoBehaviour
{
    public static Neige Instance { get; private set; }
    // 0 → 1 : ciel couvert (lumière, brume, nuages) ; couverture du sol.
    public static float Gris => Instance == null ? 0 : Instance.gris;
    public static float Couverture => Instance == null ? 0 : Instance.couverture;

    const int Flocons = 1400, MaxEmpreintes = 600;
    const float Boite = 34, Hauteur = 18, Pas = .72f;
    float gris, couverture, interieur, acceleration = 1;
    public static void Accelerer(float facteur) { if (Instance != null) Instance.acceleration = facteur; }
    public static void Couvrir() { if (Instance != null) { Instance.gris = 1; Instance.couverture = 1; } }
    Material matSol, matFlocon, matEmpreinte;
    readonly List<Renderer> couche = new();
    bool coucheVisible;

    Mesh maillageFlocons; Transform flocons;
    readonly Vector3[] pos = new Vector3[Flocons]; readonly float[] vitesse = new float[Flocons], taille = new float[Flocons], phase = new float[Flocons];
    Vector3[] sommets; Vector2[] uvs;

    Mesh quad;
    readonly Queue<Transform> empreintes = new();
    readonly Dictionary<Color32, Material> parCouleur = new();
    class Marcheur { public Vector3 dernier; public bool gauche; }
    readonly Dictionary<int, Marcheur> marcheurs = new();
    PaintballSolo partie;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        if (Instance != null || Resources.Load<Material>("Ambiance/Flocon") == null) return;
        new GameObject("Neige").AddComponent<Neige>();
    }

    void Awake()
    {
        Instance = this;
        matSol = Resources.Load<Material>("Ambiance/NeigeSol");
        matFlocon = new Material(Resources.Load<Material>("Ambiance/Flocon"));
        matEmpreinte = Resources.Load<Material>("Ambiance/Empreinte");
        var racine = GameObject.Find("CoucheNeige");
        if (racine != null) couche.AddRange(racine.GetComponentsInChildren<Renderer>(true));
        if (matSol != null) matSol.SetFloat("_Cutoff", 1);
        ChargerGrille();
        // Flocons : un seul maillage de quads tournés vers la caméra, recalculé à chaque image.
        flocons = new GameObject("Flocons").transform; flocons.SetParent(transform, false);
        maillageFlocons = new Mesh { name = "Flocons" }; maillageFlocons.MarkDynamic();
        sommets = new Vector3[Flocons * 4]; uvs = new Vector2[Flocons * 4]; var tri = new int[Flocons * 6];
        for (int i = 0; i < Flocons; i++)
        {
            pos[i] = new Vector3(Random.Range(-Boite, Boite) * .5f, Random.Range(0, Hauteur), Random.Range(-Boite, Boite) * .5f);
            vitesse[i] = Random.Range(.7f, 1.5f); taille[i] = Random.Range(.018f, .045f); phase[i] = Random.value * 10;
            uvs[i * 4] = new(0, 0); uvs[i * 4 + 1] = new(1, 0); uvs[i * 4 + 2] = new(1, 1); uvs[i * 4 + 3] = new(0, 1);
            int k = i * 6, s = i * 4; tri[k] = s; tri[k + 1] = s + 2; tri[k + 2] = s + 1; tri[k + 3] = s; tri[k + 4] = s + 3; tri[k + 5] = s + 2;
        }
        maillageFlocons.vertices = sommets; maillageFlocons.uv = uvs; maillageFlocons.triangles = tri;
        flocons.gameObject.AddComponent<MeshFilter>().sharedMesh = maillageFlocons;
        var r = flocons.gameObject.AddComponent<MeshRenderer>(); r.sharedMaterial = matFlocon; r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
        flocons.gameObject.SetActive(false);
        quad = new Mesh { name = "Empreinte", vertices = new[] { new Vector3(-.5f, 0, -.5f), new Vector3(.5f, 0, -.5f), new Vector3(.5f, 0, .5f), new Vector3(-.5f, 0, .5f) },
            uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) }, triangles = new[] { 0, 2, 1, 0, 3, 2 } };
        quad.RecalculateNormals(); quad.RecalculateBounds();
    }

    void Update()
    {
        float dt = Time.deltaTime; bool tombe = Reglages.Neige;
        dt *= acceleration;
        gris = Mathf.MoveTowards(gris, tombe ? 1 : 0, dt / 15f);
        // ~1 min 30 pour couvrir le sol ; elle fond deux fois plus vite.
        couverture = Mathf.MoveTowards(couverture, tombe ? 1 : 0, dt / (tombe ? 90f : 45f));
        if (matSol != null)
        {
            bool visible = couverture > .005f;
            if (visible != coucheVisible) { coucheVisible = visible; foreach (var c in couche) if (c != null) c.enabled = visible; }
            matSol.SetFloat("_Cutoff", Mathf.Lerp(1.02f, .03f, Mathf.SmoothStep(0, 1, couverture)));
        }
        if (Time.time >= prochainTaches) { prochainTaches = Time.time + .5f; LeverTaches(); }
        if (couverture < .2f && empreintes.Count > 0) while (empreintes.Count > 0) { var e = empreintes.Dequeue(); if (e != null) Destroy(e.gameObject); }
        Sons();
        if (partie == null) partie = FindAnyObjectByType<PaintballSolo>();
        if (couverture > .3f && partie != null) Traces();
    }

    void LateUpdate()
    {
        var cam = Camera.main; float force = Gris;
        if (cam == null || force < .01f) { if (flocons.gameObject.activeSelf) flocons.gameObject.SetActive(false); return; }
        if (!flocons.gameObject.activeSelf) flocons.gameObject.SetActive(true);
        Vector3 c = cam.transform.position;
        // À l'intérieur (un plafond au-dessus de la caméra) : pas de flocons.
        bool dedans = Physics.Raycast(c, Vector3.up, 40, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
        interieur = Mathf.MoveTowards(interieur, dedans ? 1 : 0, Time.deltaTime * 2);
        matFlocon.SetColor("_BaseColor", new Color(1, 1, 1, .9f * force * (1 - interieur)));
        flocons.position = c;
        Vector3 droite = cam.transform.right, haut = cam.transform.up; float t = Time.time, dt = Time.deltaTime;
        int actifs = Mathf.RoundToInt(Flocons * Mathf.Clamp01(force * 1.2f));
        for (int i = 0; i < Flocons; i++)
        {
            Vector3 p = pos[i];
            p.y -= vitesse[i] * dt; p.x += Mathf.Sin(t * .9f + phase[i]) * .35f * dt + .25f * dt; p.z += Mathf.Cos(t * .7f + phase[i]) * .3f * dt;
            if (p.y < -2) p.y += Hauteur;
            // Boîte qui suit la caméra : les flocons sortis d'un côté reviennent de l'autre.
            p.x = Mathf.Repeat(p.x + Boite * .5f, Boite) - Boite * .5f; p.z = Mathf.Repeat(p.z + Boite * .5f, Boite) - Boite * .5f;
            pos[i] = p;
            float s = i < actifs ? taille[i] : 0;
            Vector3 d = droite * s, h = haut * s, q = p - Vector3.up * 2;
            sommets[i * 4] = q - d - h; sommets[i * 4 + 1] = q + d - h; sommets[i * 4 + 2] = q + d + h; sommets[i * 4 + 3] = q - d + h;
        }
        maillageFlocons.vertices = sommets;
        maillageFlocons.bounds = new Bounds(Vector3.up * (Hauteur * .5f - 2), new Vector3(Boite + 2, Hauteur + 4, Boite + 2));
    }

    // ---------- Grille d'enneigement (AmbianceScene.GrilleNeige) ----------
    float gx0, gz0, gcase = .5f; int gw, gh; ushort[] ghaut; byte[] galpha;
    float Seuil => matSol != null ? matSol.GetFloat("_Cutoff") : 1.02f;

    void ChargerGrille()
    {
        var texte = Resources.Load<TextAsset>("Ambiance/NeigeGrille");
        if (texte == null) return;
        using var l = new System.IO.BinaryReader(new System.IO.MemoryStream(texte.bytes));
        gx0 = l.ReadSingle(); gz0 = l.ReadSingle(); gcase = l.ReadSingle(); gw = l.ReadInt32(); gh = l.ReadInt32();
        ghaut = new ushort[gw * gh]; galpha = new byte[gw * gh];
        for (int i = 0; i < gw * gh; i++) { ghaut[i] = l.ReadUInt16(); galpha[i] = l.ReadByte(); }
    }

    // Dessus de la couche de neige sous un point (case de 0,5 m) ; visible : la neige s'y voit avec la couverture actuelle.
    public static bool Couche(Vector3 p, out float dessus, out bool visible)
    {
        dessus = 0; visible = false;
        var n = Instance; if (n == null || n.ghaut == null) return false;
        int i = Mathf.RoundToInt((p.x - n.gx0) / n.gcase), j = Mathf.RoundToInt((p.z - n.gz0) / n.gcase);
        if (i < 0 || j < 0 || i >= n.gw || j >= n.gh) return false;
        int k = j * n.gw + i;
        if (n.ghaut[k] == 0) return false;
        dessus = (n.ghaut[k] - 50000) / 1000f;
        if (Mathf.Abs(dessus - .04f - p.y) > .25f) return false;          // autre étage (toit, balcon…)
        visible = n.coucheVisible && n.galpha[k] / 255f >= n.Seuil;
        return true;
    }

    // Taches de peinture au sol : posées sur la neige quand elle les recouvrirait (la couche est 4 cm au-dessus).
    readonly List<(Transform t, Vector3 basePos, Vector3 point)> taches = new();
    float prochainTaches;
    public static void Suivre(Transform tache, Vector3 point)
    {
        if (Instance == null || !Couche(point, out _, out bool visible)) return;
        Instance.taches.Add((tache, tache.position, point));
        if (visible) tache.position += Vector3.up * .045f;
    }
    void LeverTaches()
    {
        for (int i = taches.Count - 1; i >= 0; i--)
        {
            var (t, b, point) = taches[i];
            if (t == null) { taches.RemoveAt(i); continue; }
            Couche(point, out _, out bool visible);
            t.position = b + (visible ? Vector3.up * .045f : Vector3.zero);
        }
    }

    // ---------- Empreintes ----------
    void Traces()
    {
        Pister(-1, partie.transform.position, partie.Couleur, true);
        var bots = partie.Bots;
        if (partie.Active && partie.Mode == PaintballSolo.ModePartie.Bots && bots != null && bots.Match != null)
            foreach (var j in bots.Match.joueurs)
                if (j.id != partie.JoueurId && !j.elimine)
                    Pister(j.id, bots.Position(j.id), PaintballSolo.Couleurs[Mathf.Clamp(j.couleur, 0, PaintballSolo.Couleurs.Length - 1)], false);
    }

    void Pister(int id, Vector3 p, Color couleur, bool joueur)
    {
        if (!marcheurs.TryGetValue(id, out var m)) { marcheurs[id] = new Marcheur { dernier = p }; return; }
        Vector3 d = p - m.dernier; d.y = 0;
        if (d.magnitude > 6) { m.dernier = p; return; }        // téléportation
        if (d.magnitude < Pas) return;
        if (joueur && partie.GetComponent<Explorateur>() is var ex && ex != null && ex.Monture != null) { m.dernier = p; return; }
        m.dernier = p; m.gauche = !m.gauche;
        Vector3 avant = d.normalized, cote = Vector3.Cross(Vector3.up, avant);
        Vector3 pied = p + cote * (m.gauche ? -.11f : .11f);
        if (!Physics.Raycast(pied + Vector3.up * 1.2f, Vector3.down, out var h, 3, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) || h.normal.y < .6f) return;
        if (Physics.Raycast(h.point + Vector3.up * .3f, Vector3.up, 60, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) return;   // abrité
        // Seulement sur la neige visible (pas sur l'herbe, l'eau, ni dans les trous de la couche), posée dessus.
        if (!Couche(h.point, out float dessus, out bool neige) || !neige) return;
        h.point = new Vector3(h.point.x, Mathf.Max(h.point.y, dessus - .04f), h.point.z);
        Empreinte(h.point + h.normal * .05f, Quaternion.LookRotation(Vector3.ProjectOnPlane(avant, h.normal), h.normal), couleur);
        if (joueur) SonsPaintball.Instance?.PasNeige();
    }

    void Empreinte(Vector3 p, Quaternion r, Color couleur)
    {
        if (matEmpreinte == null) return;
        Color32 cle = couleur;
        if (!parCouleur.TryGetValue(cle, out var mat)) { mat = new Material(matEmpreinte); mat.SetColor("_BaseColor", couleur * .9f); parCouleur[cle] = mat; }
        Transform t;
        if (empreintes.Count >= MaxEmpreintes) t = empreintes.Dequeue();
        else
        {
            t = new GameObject("Empreinte").transform; t.SetParent(transform, false); t.gameObject.layer = 2;
            t.gameObject.AddComponent<MeshFilter>().sharedMesh = quad;
            var rd = t.gameObject.AddComponent<MeshRenderer>(); rd.shadowCastingMode = ShadowCastingMode.Off;
        }
        t.GetComponent<MeshRenderer>().sharedMaterial = mat;
        t.SetPositionAndRotation(p, r); t.localScale = new Vector3(.2f, 1, .3f);
        empreintes.Enqueue(t);
    }

    void Sons() => SonsPaintball.Instance?.Hiver(couverture, gris);

    // ---------- Vérification navigateur (?neige=1) ----------
    [System.Serializable] class Rapport { public bool fini, ok, couche, flocons, sol; public int renderers, empreintes; public float couverture, seuil; public string erreur = ""; }
    System.Collections.IEnumerator Start()
    {
        if (!Application.absoluteURL.Contains("neige=1")) yield break;
        var r = new Rapport();
        yield return new WaitForSeconds(3f);
        FindAnyObjectByType<InterfaceVisite>()?.Entrer(0); yield return new WaitForSeconds(1f);
        Reglages.Neige = true; acceleration = 12;
        yield return new WaitForSeconds(9f);
        r.couverture = couverture; r.renderers = couche.Count; r.seuil = matSol != null ? matSol.GetFloat("_Cutoff") : -1;
        r.couche = coucheVisible && r.renderers > 0; r.flocons = flocons.gameObject.activeSelf;
        // Marche en ligne droite sur la cour sablée sud (D-003 x 0 → 10, y 20) : une empreinte tous les 72 cm.
        var ex = partie != null ? partie.GetComponent<CharacterController>() : null;
        if (ex != null)
        {
            ex.enabled = false;
            for (int k = 0; k <= 40; k++)
            {
                partie.transform.position = new Vector3(-k * .25f, 0, 20) + Vector3.up * 3;
                if (Physics.Raycast(partie.transform.position, Vector3.down, out var h, 10)) { partie.transform.position = h.point + Vector3.up * .05f; r.sol = true; }
                yield return null;
            }
            ex.enabled = true;
        }
        r.empreintes = empreintes.Count;
        r.ok = r.couche && r.flocons && r.empreintes >= 8 && r.seuil < .9f;
        r.fini = true; acceleration = 1;
        var json = JsonUtility.ToJson(r); Debug.Log("NEIGE VERIFICATION " + json);
#if UNITY_WEBGL && !UNITY_EDITOR
        VerificationNavigateur(json);
#endif
    }
#if UNITY_WEBGL && !UNITY_EDITOR
    [System.Runtime.InteropServices.DllImport("__Internal")] static extern void VerificationNavigateur(string json);
#endif

    void OnDestroy() { if (Instance == this) Instance = null; if (matSol != null) matSol.SetFloat("_Cutoff", 1); }
}

using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

// Lunette de visée (sur le toit) : une fois fixée sur le marqueur, le clic droit passe en visée lunette, vue à
// hauteur d'œil, zoom ×3 (molette : ×3, ×4,5, ×6). La trajectoire réelle de la bille (BalistiquePaintball, même
// départ et même direction que PaintballSolo.Tirer, sans dispersion) est tracée en pointillés avec son point
// d'impact et la chute affichée ; l'aide à la visée ramène doucement le réticule pour compenser la chute sur
// le bot le plus proche du réticule (moins de 3°). La dispersion est resserrée (PaintballSolo).
[DefaultExecutionOrder(2000)]
public class LunettePaintball : MonoBehaviour
{
    public static LunettePaintball Instance { get; private set; }
    public static bool Equipee => Instance != null;
    public static bool Visee { get; private set; }
    public static bool ForcerVisee;          // contrôle navigateur (VerificationVue)

    static readonly float[] Zooms = { 3f, 4.5f, 6f };
    const int Points = 48;
    PaintballSolo partie;
    Explorateur explorateur;
    Camera cam;
    InputAction viser;
    int zoom;
    float champ;
    readonly List<Transform> points = new();
    Transform impact;
    GameObject interfaceLunette;
    TMP_Text infos;
    Transform montageTPS, montagePOV;

    // ---------- Modèle (ramassable et monté) ----------
    static Material Mat(Color c, float lisse, float metal = 0, bool eclaire = true)
    {
        var m = new Material(Shader.Find(eclaire ? "Universal Render Pipeline/Lit" : "Universal Render Pipeline/Unlit"));
        m.SetColor("_BaseColor", c); if (eclaire) { m.SetFloat("_Smoothness", lisse); m.SetFloat("_Metallic", metal); }
        return m;
    }
    static void Cylindre(Transform parent, Vector3 pos, float diametre, float longueur, Material m)
    {
        var g = GameObject.CreatePrimitive(PrimitiveType.Cylinder); Destroy(g.GetComponent<Collider>());
        g.transform.SetParent(parent, false); g.transform.localPosition = pos; g.transform.localRotation = Quaternion.Euler(90, 0, 0);
        g.transform.localScale = new Vector3(diametre, longueur * .5f, diametre); g.GetComponent<Renderer>().sharedMaterial = m;
    }
    // Lunette le long de +Z local, centrée, embase vers -Y.
    static void Construire(Transform t)
    {
        var noir = Mat(new Color(.04f, .04f, .045f), .45f, .4f);
        var verre = Mat(new Color(.15f, .35f, .5f), .95f, .2f);
        Cylindre(t, Vector3.zero, .036f, .22f, noir);
        Cylindre(t, new Vector3(0, 0, .13f), .05f, .07f, noir);
        Cylindre(t, new Vector3(0, 0, -.12f), .044f, .05f, noir);
        Cylindre(t, new Vector3(0, 0, .166f), .044f, .004f, verre);
        Cylindre(t, new Vector3(0, .026f, .01f), .022f, .03f, noir);                 // tourelle
        foreach (float z in new[] { -.06f, .07f })
        {
            Cylindre(t, new Vector3(0, 0, z), .043f, .016f, noir);                    // colliers
            var pied = GameObject.CreatePrimitive(PrimitiveType.Cube); Destroy(pied.GetComponent<Collider>());
            pied.transform.SetParent(t, false); pied.transform.localPosition = new Vector3(0, -.03f, z); pied.transform.localScale = new Vector3(.02f, .03f, .016f);
            pied.GetComponent<Renderer>().sharedMaterial = noir;
        }
    }
    // Modèle posé sur une caisse (ObjetsDomaine.Poser) : renvoie la hauteur.
    public static float Modele(Transform parent)
    {
        var caisse = GameObject.CreatePrimitive(PrimitiveType.Cube); Destroy(caisse.GetComponent<Collider>());
        caisse.transform.SetParent(parent, false); caisse.transform.localPosition = new Vector3(0, .2f, 0); caisse.transform.localScale = new Vector3(.5f, .4f, .4f);
        caisse.GetComponent<Renderer>().sharedMaterial = Mat(new Color(.4f, .3f, .17f), .2f);
        var l = new GameObject("Lunette").transform; l.SetParent(parent, false); l.localPosition = new Vector3(0, .48f, 0); l.localScale = Vector3.one * 1.6f;
        Construire(l);
        return .6f;
    }

    // Lunette perdue (touché, nouvelle partie) : démontée du marqueur.
    public static void Retirer() { if (Instance != null) { Destroy(Instance); Instance = null; } }

    public static void Equiper(PaintballSolo p)
    {
        if (Instance != null || p == null) return;
        Instance = p.gameObject.AddComponent<LunettePaintball>();
        Instance.partie = p;
        ObjetsDomaine.Annoncer("Lunette fixée ! Clic droit : visée lunette ×3 — molette : ×4,5 et ×6");
    }

    void Start()
    {
        explorateur = GetComponent<Explorateur>();
        cam = GetComponentInChildren<Camera>();
        viser = new InputAction("ViserLunette", InputActionType.Button, "<Mouse>/rightButton"); viser.AddBinding("<Gamepad>/leftTrigger"); viser.Enable();
        champ = cam.fieldOfView;
        montageTPS = Monter(partie.marqueur, partie.bouche, transform.up);
        montagePOV = Monter(partie.marqueurPOV, partie.bouchePOV, cam.transform.up);
        var couleur = Mat(partie.Couleur, 0, 0, false);
        for (int i = 0; i < Points; i++)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Sphere); Destroy(g.GetComponent<Collider>());
            g.name = "TrajectoireLunette"; g.GetComponent<Renderer>().sharedMaterial = couleur; g.SetActive(false); points.Add(g.transform);
        }
        var anneau = GameObject.CreatePrimitive(PrimitiveType.Cylinder); Destroy(anneau.GetComponent<Collider>());
        anneau.name = "ImpactLunette"; anneau.GetComponent<Renderer>().sharedMaterial = Mat(new Color(1f, .25f, .2f), 0, 0, false);
        impact = anneau.transform; impact.gameObject.SetActive(false);
        ConstruireInterface();
    }

    // Lunette fixée au-dessus du canon : de la crosse à la bouche, 7 cm au-dessus de l'axe.
    Transform Monter(Transform marqueur, Transform bouche, Vector3 haut)
    {
        if (marqueur == null || bouche == null) return null;
        Vector3 axe = bouche.position - marqueur.position;
        if (axe.sqrMagnitude < 1e-4f) axe = marqueur.forward;
        var t = new GameObject("LunetteMontee").transform;
        t.SetPositionAndRotation(Vector3.Lerp(marqueur.position, bouche.position, .45f) + haut.normalized * .07f, Quaternion.LookRotation(axe.normalized, haut));
        Construire(t);
        t.SetParent(marqueur, true);
        return t;
    }

    void Update()
    {
        if (partie == null) return;
        bool peut = partie.Active && !partie.EnPause && explorateur.enabled;
        Visee = peut && (viser.IsPressed() || Tactile.Visee || ForcerVisee);
        if (Visee && Mouse.current != null)
        {
            float molette = Mouse.current.scroll.ReadValue().y;
            if (molette > 0) zoom = Mathf.Min(zoom + 1, Zooms.Length - 1);
            else if (molette < 0) zoom = Mathf.Max(zoom - 1, 0);
        }
        Explorateur.FacteurRegard = Visee ? 1f / Zooms[zoom] * 1.3f : 1f;
    }

    void LateUpdate()
    {
        if (partie == null) return;
        interfaceLunette.SetActive(Visee);
        if (!Visee)
        {
            impact.gameObject.SetActive(false);
            foreach (var p in points) p.gameObject.SetActive(false);
            champ = cam.fieldOfView;
            return;
        }
        // Vue à hauteur d'œil (aussi en 3e personne), arme et robot masqués derrière l'oculaire.
        cam.transform.localPosition = new Vector3(0, explorateur.HauteurYeux, 0);
        champ = Mathf.Lerp(champ, Reglages.ChampVision / Zooms[zoom], 1 - Mathf.Exp(-16 * Time.deltaTime));
        cam.fieldOfView = champ;
        if (partie.marqueur != null) partie.marqueur.gameObject.SetActive(false);
        if (partie.marqueurPOV != null) partie.marqueurPOV.gameObject.SetActive(false);
        if (partie.personnage != null) partie.personnage.SetActive(false);
        Tracer();
    }

    // Trajectoire réelle de la prochaine bille, comme PaintballSolo.Tirer.
    void Tracer()
    {
        Vector3 origine = (partie.TroisiemePersonne ? partie.bouche : partie.bouchePOV).position;
        Vector3 cible = cam.transform.position + cam.transform.forward * 120;
        if (Physics.Raycast(cam.transform.position, cam.transform.forward, out var vise, 120, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) cible = vise.point;
        Vector3 pos = origine, v = (cible - origine).normalized * BalistiquePaintball.VitesseInitiale;
        const float dt = 1f / 240f;
        int n = 0; float t = 0, prochainPoint = .02f; bool touche = false; Vector3 point = pos, normale = Vector3.up;
        while (t < 2.5f && !touche)
        {
            Vector3 avant = pos;
            BalistiquePaintball.Avancer(ref pos, ref v, dt); t += dt;
            if (Physics.Linecast(avant, pos, out var h, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) && h.collider.GetComponentInParent<PaintballSolo>() == null)
            { touche = true; point = h.point; normale = h.normal; break; }
            float d = Vector3.Distance(cam.transform.position, pos);
            if (t >= prochainPoint && n < Points && d > 4f)
            {
                points[n].position = pos; points[n].localScale = Vector3.one * Mathf.Clamp(d * .0045f, .015f, .3f);
                points[n].gameObject.SetActive(true); n++;
                prochainPoint += Mathf.Lerp(.012f, .05f, t / 1.2f);
            }
            point = pos;
        }
        for (int i = n; i < Points; i++) points[i].gameObject.SetActive(false);
        impact.gameObject.SetActive(touche);
        if (touche)
        {
            float d = Vector3.Distance(cam.transform.position, point);
            impact.SetPositionAndRotation(point + normale * .02f, Quaternion.FromToRotation(Vector3.up, normale));
            impact.localScale = new Vector3(d * .012f, .003f, d * .012f);
        }
        float distance = Vector3.Distance(cam.transform.position, point);
        Vector3 surAxe = cam.transform.position + cam.transform.forward * distance;
        float chute = Vector3.Dot(surAxe - point, cam.transform.up);
        infos.text = $"×{Zooms[zoom]:0.#}    {distance:0} m    chute {chute * 100:0} cm" + (touche ? "" : "    hors de portée");
        Assister(origine, (cible - origine).normalized);
    }

    // Aide à la visée : bot le plus proche du réticule (≤ 3°) ; on corrige l'écart entre son buste et le point où
    // passe la bille à sa distance, à raison de 5 /s (le joueur garde la main).
    void Assister(Vector3 origine, Vector3 direction)
    {
        if (PartieBots.Instance == null) return;
        BotPaintball meilleur = null; float angle = 3f;
        foreach (var b in PartieBots.Instance.bots)
        {
            if (b == null || !b.gameObject.activeInHierarchy || b.EtatTexte == "Elimine") continue;
            Vector3 buste = b.transform.position + Vector3.up * PartieBots.Torse;
            float a = Vector3.Angle(cam.transform.forward, buste - cam.transform.position);
            if (a >= angle) continue;
            bool libre = !Physics.Linecast(cam.transform.position, buste, out var h, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
                         || h.collider.GetComponentInParent<BotPaintball>() == b;
            if (libre) { angle = a; meilleur = b; }
        }
        if (meilleur == null) return;
        Vector3 c = meilleur.transform.position + Vector3.up * PartieBots.Torse;
        // Point de passage de la bille à la distance horizontale du bot.
        float dh = new Vector2(c.x - origine.x, c.z - origine.z).magnitude;
        Vector3 pos = origine, v = direction * BalistiquePaintball.VitesseInitiale;
        for (float t = 0; t < 2.5f && new Vector2(pos.x - origine.x, pos.z - origine.z).magnitude < dh; t += 1f / 240f)
            BalistiquePaintball.Avancer(ref pos, ref v, 1f / 240f);
        Vector3 ecart = c - pos;
        float distance = Mathf.Max(1, Vector3.Distance(cam.transform.position, c));
        float lacet = Mathf.Atan2(Vector3.Dot(ecart, cam.transform.right), distance) * Mathf.Rad2Deg;
        float haut = Mathf.Atan2(Vector3.Dot(ecart, cam.transform.up), distance) * Mathf.Rad2Deg;
        float k = 1 - Mathf.Exp(-5 * Time.deltaTime);
        explorateur.Corriger(new Vector2(lacet, haut) * k);
    }

    // ---------- Interface : oculaire rond, réticule à graduations, infos ----------
    void ConstruireInterface()
    {
        var canvas = new GameObject("InterfaceLunette").AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay; canvas.sortingOrder = 40;
        var echelle = canvas.gameObject.AddComponent<CanvasScaler>(); echelle.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        echelle.referenceResolution = new Vector2(1600, 900); echelle.matchWidthOrHeight = 1;
        interfaceLunette = canvas.gameObject;
        const int N = 512;
        var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
        var px = new Color32[N * N];
        for (int y = 0; y < N; y++)
            for (int x = 0; x < N; x++)
            {
                float dx = (x + .5f) / N * 2 - 1, dy = (y + .5f) / N * 2 - 1, r = Mathf.Sqrt(dx * dx + dy * dy);
                float a = Mathf.Clamp01((r - .955f) / .02f);                        // bord de l'oculaire
                float ombre = Mathf.Clamp01((r - .8f) / .16f) * .45f;               // vignettage
                px[y * N + x] = new Color32(0, 0, 0, (byte)(255 * Mathf.Max(a, ombre)));
            }
        tex.SetPixels32(px); tex.Apply();
        var oculaire = Image(canvas.transform, "Oculaire", Vector2.zero, new Vector2(900, 900), Color.white);
        oculaire.sprite = Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(.5f, .5f));
        foreach (float sx in new[] { -1f, 1f })    // bandes noires de part et d'autre
        {
            Image(canvas.transform, "Bande", new Vector2(sx * (450 + 1000), 0), new Vector2(2000, 2000), Color.black);
        }
        var trait = new Color(0, 0, 0, .9f);
        Image(canvas.transform, "H", Vector2.zero, new Vector2(860, 2), trait);
        Image(canvas.transform, "V", Vector2.zero, new Vector2(2, 860), trait);
        foreach (float sx in new[] { -1f, 1f })
        {
            Image(canvas.transform, "EpaisH", new Vector2(sx * 300, 0), new Vector2(260, 6), trait);
            Image(canvas.transform, "EpaisV", new Vector2(0, sx * 300), new Vector2(6, 260), trait);
        }
        for (int k = 1; k <= 6; k++)                // graduations de chute
        {
            Image(canvas.transform, "Grad", new Vector2(0, -k * 26), new Vector2(k % 2 == 0 ? 22 : 12, 2), trait);
            Image(canvas.transform, "GradH", new Vector2(k * 26, 0), new Vector2(2, k % 2 == 0 ? 22 : 12), trait);
            Image(canvas.transform, "GradH", new Vector2(-k * 26, 0), new Vector2(2, k % 2 == 0 ? 22 : 12), trait);
        }
        Image(canvas.transform, "Centre", Vector2.zero, new Vector2(5, 5), new Color(1f, .2f, .15f));
        var go = new GameObject("Infos"); go.transform.SetParent(canvas.transform, false);
        infos = go.AddComponent<TextMeshProUGUI>(); infos.fontSize = 26; infos.alignment = TextAlignmentOptions.Center;
        infos.color = new Color(.95f, .95f, .9f); infos.raycastTarget = false;
        infos.rectTransform.anchoredPosition = new Vector2(0, -330); infos.rectTransform.sizeDelta = new Vector2(900, 40);
        interfaceLunette.SetActive(false);
    }

    static Image Image(Transform parent, string nom, Vector2 pos, Vector2 taille, Color c)
    {
        var go = new GameObject(nom); go.transform.SetParent(parent, false);
        var i = go.AddComponent<Image>(); i.color = c; i.raycastTarget = false;
        i.rectTransform.anchoredPosition = pos; i.rectTransform.sizeDelta = taille;
        return i;
    }

    void OnDestroy()
    {
        if (Instance == this) Instance = null;
        Visee = false; Explorateur.FacteurRegard = 1f;
        viser?.Dispose();
        if (interfaceLunette != null) Destroy(interfaceLunette);
        foreach (var p in points) if (p != null) Destroy(p.gameObject);
        if (impact != null) Destroy(impact.gameObject);
        if (montageTPS != null) Destroy(montageTPS.gameObject);
        if (montagePOV != null) Destroy(montagePOV.gameObject);
    }
}

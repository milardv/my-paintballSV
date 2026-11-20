using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering;
using UnityEngine.UI;

// Carte du domaine sur le toit : vue aérienne rendue au lancement (nord en haut, est à droite) et pastilles des
// objets, vertes quand l'objet attend, rouges quand il est pris ; le joueur est le point blanc.
// E devant la carte : carte en grand, avec la position des autres joueurs (E, Échap ou clic pour fermer).
public class CarteDomaine : MonoBehaviour, IInteractif
{
    const float Largeur = 2.4f, Hauteur = 1.6f, Centre = 1.45f, Aspect = 1.5f;
    // Emprise de la propriété (PartieBots.Limite) en repère Unity, avec une marge.
    const float CX = -40.9f, CZ = 54.6f, DemiH = 94f, DemiW = DemiH * Aspect;
    static readonly Color Vert = new(.2f, 1f, .35f), Rouge = new(1f, .2f, .18f);
    Transform moi;
    readonly Dictionary<ObjetsDomaine.Suivi, (Transform pastille, Renderer rendu, TextMeshPro texte)> marques = new();
    Material vert, rouge, blanc, image;
    TextMeshPro liste;
    float prochain;
    RenderTexture vue;
    Texture2D carte;

    public static void Installer(Vector3 sol, Vector3 regardeVers)
    {
        var go = new GameObject("CarteDomaine");
        go.transform.position = sol;
        Vector3 d = regardeVers - sol; d.y = 0;
        go.transform.rotation = Quaternion.LookRotation(d.sqrMagnitude > .01f ? -d.normalized : Vector3.forward);
        go.AddComponent<CarteDomaine>().Construire();
    }

    public string Libelle(Explorateur e) => "Ouvrir la carte en grand";
    public void Interagir(Explorateur e) => Ouvrir(e);

    static Material Mat(Color c, bool eclaire = true)
    {
        var m = new Material(Shader.Find(eclaire ? "Universal Render Pipeline/Lit" : "Universal Render Pipeline/Unlit"));
        m.SetColor("_BaseColor", c); if (eclaire) m.SetFloat("_Smoothness", .3f); return m;
    }

    Transform Bloc(Transform parent, PrimitiveType t, Vector3 pos, Vector3 e, Material m, bool collision = false)
    {
        var g = GameObject.CreatePrimitive(t); if (!collision) Destroy(g.GetComponent<Collider>());
        g.transform.SetParent(parent, false); g.transform.localPosition = pos; g.transform.localScale = e;
        g.GetComponent<Renderer>().sharedMaterial = m; return g.transform;
    }

    void Construire()
    {
        var bois = Mat(new Color(.35f, .22f, .12f)); var fer = Mat(new Color(.08f, .08f, .08f));
        vert = Mat(Vert, false); rouge = Mat(Rouge, false); blanc = Mat(Color.white, false);
        // Pupitre : deux pieds, cadre, plateau incliné vers le lecteur.
        foreach (float x in new[] { -Largeur * .42f, Largeur * .42f }) Bloc(transform, PrimitiveType.Cube, new(x, .55f, 0), new(.07f, 1.1f, .07f), fer);
        var plateau = new GameObject("Plateau").transform; plateau.SetParent(transform, false);
        plateau.localPosition = new Vector3(0, Centre, 0); plateau.localRotation = Quaternion.Euler(15, 0, 0);
        Bloc(plateau, PrimitiveType.Cube, new(0, 0, .03f), new(Largeur + .12f, Hauteur + .12f, .05f), bois, true);

        image = Mat(new Color(.25f, .33f, .22f), false);
        Bloc(plateau, PrimitiveType.Quad, Vector3.zero, new(Largeur, Hauteur, 1), image);
        StartCoroutine(RendreVue());

        var titre = Texte(plateau, "Objets du domaine — E : carte en grand", new(0, Hauteur * .5f + .1f), 1.2f, TextAlignmentOptions.Center, new(Largeur + .6f, .2f));
        titre.color = new Color(1f, .92f, .7f);
        liste = Texte(plateau, "", new(-Largeur * .5f + .02f, -Hauteur * .5f - .02f), .62f, TextAlignmentOptions.TopLeft, new(Largeur, .5f));
        liste.rectTransform.pivot = new Vector2(0, 1);
        foreach (var r in ObjetsDomaine.Registre)
        {
            var pastille = Bloc(plateau, PrimitiveType.Sphere, Vector3.zero, Vector3.one * .055f, vert);
            var t = Texte(plateau, r.nom, Vector3.zero, .55f, TextAlignmentOptions.Left, new(.9f, .1f));
            t.rectTransform.pivot = new Vector2(0, .5f); t.outlineWidth = .25f; t.outlineColor = Color.black;
            marques[r] = (pastille, pastille.GetComponent<Renderer>(), t);
        }
        moi = Bloc(plateau, PrimitiveType.Sphere, Vector3.zero, Vector3.one * .07f, blanc);
    }

    // Vue aérienne rendue une fois par une caméra orthographique (lumière ambiante forte et sans brume pendant
    // ce rendu seulement, pour que la carte reste lisible la nuit).
    IEnumerator RendreVue()
    {
        yield return null; yield return null;
        vue = new RenderTexture(1536, 1024, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 1, name = "CarteDomaine" }; vue.Create();
        var go = new GameObject("CameraCarte");
        var cam = go.AddComponent<Camera>();
        cam.orthographic = true; cam.orthographicSize = DemiH; cam.aspect = Aspect; cam.nearClipPlane = 1; cam.farClipPlane = 600;
        cam.useOcclusionCulling = false; cam.cullingMask = ~(1 << 2); cam.depth = -50; cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(.25f, .33f, .22f); cam.targetTexture = vue; cam.allowHDR = false;
        go.transform.SetPositionAndRotation(new Vector3(CX, 300, CZ), Quaternion.LookRotation(Vector3.down, Vector3.back));
        // Éclairage de jour réservé à ce rendu : ambiance uniforme (sondes SH, lues par URP) et soleil zénithal.
        var soleil = new GameObject("SoleilCarte").AddComponent<Light>(); soleil.type = LightType.Directional; soleil.intensity = 1.25f;
        soleil.color = new Color(1f, .97f, .9f); soleil.shadows = LightShadows.None; soleil.transform.rotation = Quaternion.Euler(70, -30, 0); soleil.enabled = false;
        var jour = new SphericalHarmonicsL2(); jour.AddAmbientLight(new Color(.5f, .5f, .48f));
        bool brume = false; SphericalHarmonicsL2 sonde = default; var eteintes = new List<Light>();
        // Même éclairage de jour quelle que soit l'heure : le soleil du jeu et les lumières de nuit sont coupés.
        void Avant(ScriptableRenderContext c, Camera k)
        {
            if (k != cam) return;
            brume = RenderSettings.fog; sonde = RenderSettings.ambientProbe;
            RenderSettings.fog = false; RenderSettings.ambientProbe = jour;
            eteintes.Clear();
            foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None)) if (l != soleil && l.enabled) { l.enabled = false; eteintes.Add(l); }
            soleil.enabled = true;
        }
        void Apres(ScriptableRenderContext c, Camera k)
        {
            if (k != cam) return;
            RenderSettings.fog = brume; RenderSettings.ambientProbe = sonde; soleil.enabled = false;
            foreach (var l in eteintes) if (l != null) l.enabled = true;
        }
        RenderPipelineManager.beginCameraRendering += Avant; RenderPipelineManager.endCameraRendering += Apres;
        cam.enabled = false;
        try { cam.Render(); } catch (System.Exception e) { Debug.LogWarning("CARTE rendu : " + e.Message); }
        RenderPipelineManager.beginCameraRendering -= Avant; RenderPipelineManager.endCameraRendering -= Apres;
        // Copie dans une texture ordinaire (la texture de rendu échantillonnée directement sort noire sous WebGL).
        var lu = new Texture2D(1536, 1024, TextureFormat.RGB24, false);   // opaque : pas de carte translucide
        var avant = RenderTexture.active; RenderTexture.active = vue;
        lu.ReadPixels(new Rect(0, 0, 1536, 1024), 0, 0); lu.Apply(false, true); RenderTexture.active = avant;
        vue.Release(); Destroy(vue); vue = null; carte = lu;
        Debug.Log("CARTE vue aérienne rendue");
        yield return null;
        Destroy(go); Destroy(soleil.gameObject);
        image.SetTexture("_BaseMap", carte); image.SetColor("_BaseColor", Color.white);
        if (grandeImage != null) { grandeImage.texture = carte; grandeImage.color = Color.white; }
    }

    TextMeshPro Texte(Transform parent, string s, Vector3 pos, float taille, TextAlignmentOptions alignement, Vector2 cadre)
    {
        var go = new GameObject("Texte"); go.transform.SetParent(parent, false);
        var t = go.AddComponent<TextMeshPro>(); t.text = s; t.fontSize = taille; t.alignment = alignement; t.color = Color.white;
        t.rectTransform.sizeDelta = cadre; t.textWrappingMode = TextWrappingModes.NoWrap;
        go.transform.localPosition = pos + new Vector3(0, 0, -.012f);
        return t;
    }

    // Monde → carte (0..1, origine en bas à gauche).
    static Vector2 SurCarte(Vector3 monde) =>
        new(Mathf.Clamp01(.5f - (monde.x - CX) / (2 * DemiW)), Mathf.Clamp01(.5f - (monde.z - CZ) / (2 * DemiH)));
    static Vector3 SurPanneau(Vector3 monde) { var v = SurCarte(monde); return new Vector3((v.x - .5f) * Largeur, (v.y - .5f) * Hauteur, -.012f); }

    static string Duree(float s) => s < 60 ? $"{Mathf.FloorToInt(s)} s" : $"{Mathf.FloorToInt(s / 60)} min";

    void Update()
    {
        if (ouverte) MettreAJourGrande();
        if (liste == null || Time.time < prochain) return;
        prochain = Time.time + .25f;
        var lignes = new List<string>();
        foreach (var kv in marques)
        {
            var r = kv.Key; var (p, rendu, t) = kv.Value;
            p.localPosition = SurPanneau(r.position);
            t.transform.localPosition = p.localPosition + new Vector3(.05f, 0, 0);
            rendu.sharedMaterial = r.pris ? rouge : vert;
            t.color = r.pris ? new Color(1f, .6f, .58f) : new Color(.75f, 1f, .8f);
            t.text = r.pris ? $"{r.nom} — {r.par}" : r.nom;
            lignes.Add(r.pris ? $"<color=#ff7a70>● {r.nom} : pris par {r.par} il y a {Duree(Time.time - r.quand)}{(r.reapparait ? " (revient)" : "")}</color>"
                              : $"<color=#66ff88>● {r.nom} : disponible</color>");
        }
        liste.text = string.Join("    ", lignes.GetRange(0, Mathf.Min(3, lignes.Count))) + "\n" +
                     string.Join("    ", lignes.GetRange(Mathf.Min(3, lignes.Count), Mathf.Max(0, lignes.Count - 3)));
        var joueur = FindAnyObjectByType<Explorateur>();
        if (joueur != null) moi.localPosition = SurPanneau(joueur.transform.position);
    }

    // ---------- Carte en grand ----------
    bool ouverte; float ouvertureA;
    Explorateur lecteur;
    GameObject grande;
    RawImage grandeImage;
    RectTransform cadreCarte;
    Sprite rond;
    readonly List<(Image point, TextMeshProUGUI nom)> pointsUI = new();

    void Ouvrir(Explorateur e)
    {
        if (ouverte) return;
        if (grande == null) ConstruireGrande();
        lecteur = e; ouverte = true; ouvertureA = Time.unscaledTime;
        grande.SetActive(true);
        if (lecteur != null) lecteur.enabled = false;
        MettreAJourGrande();
    }

    void Fermer()
    {
        ouverte = false; if (grande != null) grande.SetActive(false);
        if (lecteur != null) lecteur.enabled = true;
    }

    void ConstruireGrande()
    {
        var tex = new Texture2D(64, 64, TextureFormat.RGBA32, false);
        for (int y = 0; y < 64; y++) for (int x = 0; x < 64; x++)
        {
            float d = Vector2.Distance(new Vector2(x + .5f, y + .5f), new Vector2(32, 32));
            float a = Mathf.Clamp01(31 - d), bord = Mathf.Clamp01(d - 24);
            tex.SetPixel(x, y, new Color(1 - bord * .85f, 1 - bord * .85f, 1 - bord * .85f, a));
        }
        tex.Apply(); rond = Sprite.Create(tex, new Rect(0, 0, 64, 64), new Vector2(.5f, .5f));

        var canvas = new GameObject("CarteEnGrand").AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay; canvas.sortingOrder = 60;
        var echelle = canvas.gameObject.AddComponent<CanvasScaler>(); echelle.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        echelle.referenceResolution = new Vector2(1600, 900); echelle.matchWidthOrHeight = .5f;
        grande = canvas.gameObject;
        var fond = new GameObject("Fond").AddComponent<Image>(); fond.transform.SetParent(canvas.transform, false);
        fond.color = new Color(0, 0, 0, .78f); fond.rectTransform.anchorMin = Vector2.zero; fond.rectTransform.anchorMax = Vector2.one;
        fond.rectTransform.offsetMin = fond.rectTransform.offsetMax = Vector2.zero;
        var zone = new GameObject("Zone", typeof(RectTransform)).GetComponent<RectTransform>(); zone.SetParent(canvas.transform, false);
        zone.anchorMin = new Vector2(.03f, .08f); zone.anchorMax = new Vector2(.97f, .97f); zone.offsetMin = zone.offsetMax = Vector2.zero;
        grandeImage = new GameObject("Vue").AddComponent<RawImage>(); grandeImage.transform.SetParent(zone, false); grandeImage.raycastTarget = false;
        grandeImage.texture = carte; grandeImage.color = carte != null ? Color.white : new Color(.25f, .33f, .22f);
        cadreCarte = grandeImage.rectTransform;
        var ratio = grandeImage.gameObject.AddComponent<AspectRatioFitter>(); ratio.aspectMode = AspectRatioFitter.AspectMode.FitInParent; ratio.aspectRatio = Aspect;
        var aide = Etiquette(canvas.transform, "● vert : objet disponible    ● rouge : objet pris    ● joueurs à leur couleur    —    E, Échap ou clic : fermer", 22);
        aide.rectTransform.anchorMin = new Vector2(0, 0); aide.rectTransform.anchorMax = new Vector2(1, .07f); aide.alignment = TextAlignmentOptions.Center;
        grande.SetActive(false);
    }

    TextMeshProUGUI Etiquette(Transform parent, string s, float taille)
    {
        var t = new GameObject("Etiquette").AddComponent<TextMeshProUGUI>(); t.transform.SetParent(parent, false);
        t.text = s; t.fontSize = taille; t.color = Color.white; t.raycastTarget = false; t.textWrappingMode = TextWrappingModes.NoWrap;
        t.outlineWidth = .25f; t.outlineColor = new Color32(0, 0, 0, 230);
        return t;
    }

    void Point(int i, Vector3 monde, Color c, string nom, float taille)
    {
        while (pointsUI.Count <= i)
        {
            var p = new GameObject("Point").AddComponent<Image>(); p.transform.SetParent(cadreCarte, false); p.sprite = rond; p.raycastTarget = false;
            p.rectTransform.anchorMin = p.rectTransform.anchorMax = Vector2.zero;
            var n = Etiquette(p.transform, "", 18); n.alignment = TextAlignmentOptions.Left;
            n.rectTransform.anchorMin = n.rectTransform.anchorMax = new Vector2(1, .5f); n.rectTransform.pivot = new Vector2(0, .5f);
            n.rectTransform.anchoredPosition = new Vector2(6, 0); n.rectTransform.sizeDelta = new Vector2(300, 30);
            pointsUI.Add((p, n));
        }
        var (img, txt) = pointsUI[i];
        img.gameObject.SetActive(true);
        var v = SurCarte(monde); var r = cadreCarte.rect;
        img.rectTransform.anchoredPosition = new Vector2(v.x * r.width, v.y * r.height);
        img.rectTransform.sizeDelta = Vector2.one * taille; img.color = c; txt.text = nom; txt.color = Color.Lerp(c, Color.white, .45f);
    }

    void MettreAJourGrande()
    {
        bool fermer = Time.unscaledTime - ouvertureA > .2f && (Keyboard.current != null && (Keyboard.current.eKey.wasPressedThisFrame || Keyboard.current.escapeKey.wasPressedThisFrame)
            || Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame
            || Touchscreen.current != null && Touchscreen.current.primaryTouch.press.wasPressedThisFrame);
        if (fermer) { Fermer(); return; }
        int i = 0;
        foreach (var r in ObjetsDomaine.Registre) Point(i++, r.position, r.pris ? Rouge : Vert, r.pris ? $"{r.nom} ({r.par})" : r.nom, 18);
        var hote = PartieBots.Instance; var partie = FindAnyObjectByType<PaintballSolo>();
        if (hote != null && hote.Match != null)
            foreach (var j in hote.Match.joueurs)
            {
                if (j.elimine || partie != null && j.id == partie.JoueurId) continue;
                Point(i++, hote.Position(j.id), PaintballSolo.Couleurs[Mathf.Clamp(j.couleur, 0, PaintballSolo.Couleurs.Length - 1)], j.nom, 26);
            }
        if (lecteur != null) Point(i++, lecteur.transform.position, partie != null && partie.Active ? partie.Couleur : Color.white, "Vous", 30);
        for (; i < pointsUI.Count; i++) pointsUI[i].point.gameObject.SetActive(false);
    }

    void OnDestroy()
    {
        if (ouverte) Fermer();
        if (grande != null) Destroy(grande);
        if (vue != null) vue.Release();
        if (carte != null) Destroy(carte);
    }
}

using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

// Ambiance de la scène, préparée au build (PaintballScene) :
//  - textures procédurales (nuages, flocon, neige, empreinte) et matériaux dans Resources/Ambiance, chargés par
//    Atmosphere et Neige au lancement (les variantes de shaders suivent ainsi dans le build web) ;
//  - couche de neige : copie, 4 cm au-dessus, des triangles tournés vers le ciel et à ciel ouvert (sols, allées,
//    toits, murets, mobilier d'extérieur), cachée tant qu'il ne neige pas ;
//  - post-traitement léger (couleurs, contraste, bloom, vignette), occlusion ambiante (PC) et brouillard.
public static class AmbianceScene
{
    const string Ressources = "Assets/Chateau/Resources/Ambiance", Maillages = "Assets/Chateau/Ambiance";

    public static void Preparer()
    {
        Directory.CreateDirectory(Ressources); Directory.CreateDirectory(Maillages);
        var nuages = Texture("Nuages", 512, TexNuages, true);
        var flocon = Texture("Flocon", 64, TexFlocon, false);
        var neige = Texture("NeigeSol", 256, TexNeige, true);
        var empreinte = Texture("Empreinte", 64, TexEmpreinte, false);
        Transparent("Nuages", nuages, Color.white);
        Transparent("Flocon", flocon, Color.white);
        var matNeige = Decoupe("NeigeSol", neige, new Color(.93f, .95f, .98f), .35f, 1f);
        Decoupe("Empreinte", empreinte, Color.white, .1f, .5f);
        CoucheNeige(matNeige);
        CarteDomaine();
        PostTraitement();
        RenderSettings.fog = true; RenderSettings.fogMode = FogMode.Exponential; RenderSettings.fogDensity = .0016f;
        RenderSettings.fogColor = new Color(.72f, .78f, .86f);
        AssetDatabase.SaveAssets();
    }

    // ---------- Textures ----------
    delegate Color Pixel(float u, float v);

    static Texture2D Texture(string nom, int n, Pixel f, bool repete)
    {
        string chemin = $"{Ressources}/{nom}.png";
        var t = new Texture2D(n, n, TextureFormat.RGBA32, false);
        var px = new Color[n * n];
        for (int y = 0; y < n; y++) for (int x = 0; x < n; x++) px[y * n + x] = f((x + .5f) / n, (y + .5f) / n);
        t.SetPixels(px); t.Apply();
        File.WriteAllBytes(chemin, t.EncodeToPNG()); Object.DestroyImmediate(t);
        AssetDatabase.ImportAsset(chemin, ImportAssetOptions.ForceUpdate);
        var imp = (TextureImporter)AssetImporter.GetAtPath(chemin);
        imp.alphaIsTransparency = true; imp.mipmapEnabled = true; imp.wrapMode = repete ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
        imp.sRGBTexture = true; imp.textureCompression = TextureImporterCompression.Uncompressed; imp.SaveAndReimport();
        return AssetDatabase.LoadAssetAtPath<Texture2D>(chemin);
    }

    // Bruit de valeur périodique (période p cellules), fractal sur 5 octaves : texture qui se répète sans couture.
    static float Hache(int x, int y, int p, int graine)
    {
        x = ((x % p) + p) % p; y = ((y % p) + p) % p;
        uint h = (uint)(x * 374761393 + y * 668265263 + graine * 982451653); h = (h ^ (h >> 13)) * 1274126177u; h ^= h >> 16;
        return (h & 0xffffff) / 16777215f;
    }
    static float Valeur(float u, float v, int p, int graine)
    {
        float x = u * p, y = v * p; int xi = Mathf.FloorToInt(x), yi = Mathf.FloorToInt(y);
        float fx = x - xi, fy = y - yi; fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
        float a = Mathf.Lerp(Hache(xi, yi, p, graine), Hache(xi + 1, yi, p, graine), fx);
        float b = Mathf.Lerp(Hache(xi, yi + 1, p, graine), Hache(xi + 1, yi + 1, p, graine), fx);
        return Mathf.Lerp(a, b, fy);
    }
    static float Fbm(float u, float v, int p, int graine, int octaves = 5)
    {
        float s = 0, a = .5f, total = 0;
        for (int o = 0; o < octaves; o++) { s += a * Valeur(u, v, p << o, graine + o); total += a; a *= .5f; }
        return s / total;
    }

    // Cumulus épars : bords nets en haut, dessous légèrement gris.
    static Color TexNuages(float u, float v)
    {
        float f = Fbm(u, v, 4, 11, 6);
        float a = Mathf.SmoothStep(0, 1, Mathf.InverseLerp(.5f, .72f, f));
        float g = Mathf.Lerp(1f, .78f, Mathf.InverseLerp(.62f, .9f, f));
        return new Color(g, g, g * 1.02f, a);
    }
    static Color TexFlocon(float u, float v)
    {
        float d = Vector2.Distance(new Vector2(u, v), new Vector2(.5f, .5f)) * 2;
        return new Color(1, 1, 1, Mathf.Clamp01(1 - d * d) * Mathf.Clamp01((1 - d) * 3));
    }
    // Neige au sol : blanc légèrement bleuté, alpha = ordre d'apparition (le seuil descend avec la couverture).
    static Color TexNeige(float u, float v)
    {
        float f = Fbm(u, v, 8, 23, 5), grain = Valeur(u, v, 128, 5);
        float l = .93f + .06f * grain;
        return new Color(l * .97f, l * .985f, l, Mathf.Clamp01(.08f + f * .95f));
    }
    // Semelle (pied droit, pointe vers +v) : avant ovale, talon séparé.
    static Color TexEmpreinte(float u, float v)
    {
        float x = (u - .5f) * 2.4f, y = (v - .5f) * 1.05f;
        float avant = Mathf.Pow(x / .82f, 2) + Mathf.Pow((y - .14f) / .3f, 2);
        float talon = Mathf.Pow(x / .66f, 2) + Mathf.Pow((y + .3f) / .17f, 2);
        float a = (avant < 1 || talon < 1) ? 1 : 0;
        float stries = Mathf.Abs(Mathf.Sin(v * 70)) > .55f ? 1 : .75f;
        return new Color(stries, stries, stries, a);
    }

    // ---------- Matériaux ----------
    static Material Charger(string nom, string shader)
    {
        string chemin = $"{Ressources}/{nom}.mat";
        var m = AssetDatabase.LoadAssetAtPath<Material>(chemin);
        if (m == null) { m = new Material(Shader.Find(shader)); AssetDatabase.CreateAsset(m, chemin); }
        else m.shader = Shader.Find(shader);
        return m;
    }

    static Material Transparent(string nom, Texture2D t, Color c)
    {
        var m = Charger(nom, "Universal Render Pipeline/Unlit");
        m.SetTexture("_BaseMap", t); m.SetColor("_BaseColor", c);
        m.SetFloat("_Surface", 1); m.SetFloat("_Blend", 0); m.SetFloat("_ZWrite", 0); m.SetFloat("_Cull", 0);
        m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha); m.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
        m.SetFloat("_SrcBlendAlpha", (float)BlendMode.One); m.SetFloat("_DstBlendAlpha", (float)BlendMode.OneMinusSrcAlpha);
        m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT"); m.SetOverrideTag("RenderType", "Transparent");
        m.renderQueue = (int)RenderQueue.Transparent; EditorUtility.SetDirty(m); return m;
    }

    static Material Decoupe(string nom, Texture2D t, Color c, float lisse, float seuil)
    {
        var m = Charger(nom, "Universal Render Pipeline/Lit");
        m.SetTexture("_BaseMap", t); m.SetColor("_BaseColor", c); m.SetFloat("_Smoothness", lisse); m.SetFloat("_Metallic", 0);
        m.SetFloat("_AlphaClip", 1); m.SetFloat("_Cutoff", seuil); m.EnableKeyword("_ALPHATEST_ON");
        m.SetFloat("_Surface", 0); m.SetOverrideTag("RenderType", "TransparentCutout"); m.renderQueue = (int)RenderQueue.AlphaTest;
        EditorUtility.SetDirty(m); return m;
    }

    // ---------- Couche de neige ----------
    static readonly string[] Exclus = { "feuill", "herbe", "fleur", "eau", "drapeau", "fontaine", "parc_jet", "vitr", "verre", "lumiere",
        "parasol", "peinture", "bille", "cible", "robot", "marqueur", "ciel" };

    static void CoucheNeige(Material mat)
    {
        var ancienne = GameObject.Find("CoucheNeige"); if (ancienne != null) Object.DestroyImmediate(ancienne);
        foreach (var f in Directory.GetFiles(Maillages, "CoucheNeige_*.asset")) AssetDatabase.DeleteAsset(f.Replace('\\', '/'));
        var racine = new GameObject("CoucheNeige");
        var sommets = new List<Vector3>(); var normales = new List<Vector3>(); var uvs = new List<Vector2>(); var indices = new List<int>();
        int morceau = 0, triangles = 0;
        var grille = new List<Vector3>();           // triangles relevés pour la grille d'enneigement
        void Vider()
        {
            if (indices.Count == 0) return;
            var m = new Mesh { name = "CoucheNeige_" + morceau, indexFormat = IndexFormat.UInt32 };
            m.SetVertices(sommets); m.SetNormals(normales); m.SetUVs(0, uvs); m.SetTriangles(indices, 0); m.RecalculateBounds();
            AssetDatabase.CreateAsset(m, $"{Maillages}/CoucheNeige_{morceau}.asset");
            var go = new GameObject("CoucheNeige_" + morceau); go.transform.SetParent(racine.transform, false); go.layer = 2;
            go.AddComponent<MeshFilter>().sharedMesh = m;
            var r = go.AddComponent<MeshRenderer>(); r.sharedMaterial = mat; r.shadowCastingMode = ShadowCastingMode.Off; r.enabled = false;
            morceau++; sommets.Clear(); normales.Clear(); uvs.Clear(); indices.Clear();
        }
        foreach (var filtre in Object.FindObjectsByType<MeshFilter>(FindObjectsSortMode.None))
        {
            var rendu = filtre.GetComponent<MeshRenderer>(); var maillage = filtre.sharedMesh;
            if (rendu == null || maillage == null || !rendu.enabled || filtre.gameObject.layer == 2) continue;
            string nom = filtre.name.ToLowerInvariant();
            if (Exclus.Any(nom.Contains) || rendu.sharedMaterials.Any(m => m != null && Exclus.Any(m.name.ToLowerInvariant().Contains))) continue;
            if (filtre.GetComponentInParent<Porte>() != null || filtre.GetComponentInParent<ObjetMobilePaintball>() != null
                || filtre.GetComponentInParent<PaintballSolo>() != null) continue;
            if (rendu.bounds.size.magnitude < .6f) continue;
            Vector3[] v; Vector3[] n; int[] t;
            try { v = maillage.vertices; n = maillage.normals; t = maillage.triangles; } catch { continue; }
            var m4 = filtre.transform.localToWorldMatrix;
            for (int i = 0; i < t.Length; i += 3)
            {
                Vector3 a = m4.MultiplyPoint3x4(v[t[i]]), b = m4.MultiplyPoint3x4(v[t[i + 1]]), c = m4.MultiplyPoint3x4(v[t[i + 2]]);
                Vector3 nf = Vector3.Cross(b - a, c - a); float aire = nf.magnitude * .5f;
                if (aire < .0004f) continue;
                nf /= aire * 2;
                if (m4.determinant < 0) nf = -nf;            // miroir D-026 : l'ordre des sommets s'inverse
                if (nf.y < .6f) continue;
                Vector3 g = (a + b + c) / 3;
                // À ciel ouvert : rien au-dessus (les feuillages n'ont pas de collision).
                if (Physics.Raycast(g + Vector3.up * .08f, Vector3.up, 300, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) continue;
                int k = sommets.Count;
                foreach (var p in new[] { a, b, c })
                {
                    sommets.Add(p + Vector3.up * .04f); normales.Add(Vector3.Lerp(nf, Vector3.up, .5f).normalized); grille.Add(p + Vector3.up * .04f);
                    uvs.Add(new Vector2(p.x, p.z) / 3.5f);
                }
                if (Vector3.Dot(Vector3.Cross(b - a, c - a), Vector3.up) > 0) { indices.Add(k); indices.Add(k + 1); indices.Add(k + 2); }
                else { indices.Add(k); indices.Add(k + 2); indices.Add(k + 1); }
                triangles++;
                if (sommets.Count > 240000) Vider();
            }
        }
        Vider();
        GrilleNeige(grille);
        Debug.Log($"AMBIANCE couche de neige : {triangles} triangles en {morceau} morceaux");
    }

    // Grille d'enneigement (Resources/Ambiance/NeigeGrille.bytes) lue par Neige : par case de 0,5 m, hauteur du dessus
    // de la couche (mm + 50 000, 0 = pas de neige) et opacité de la texture de neige (empreintes seulement là où la
    // neige se voit, taches de peinture posées dessus).
    const float Case = .5f;
    static void GrilleNeige(List<Vector3> t)
    {
        if (t.Count == 0) return;
        float x0 = float.MaxValue, z0 = float.MaxValue, x1 = float.MinValue, z1 = float.MinValue;
        foreach (var p in t) { x0 = Mathf.Min(x0, p.x); z0 = Mathf.Min(z0, p.z); x1 = Mathf.Max(x1, p.x); z1 = Mathf.Max(z1, p.z); }
        int w = Mathf.CeilToInt((x1 - x0) / Case) + 1, h = Mathf.CeilToInt((z1 - z0) / Case) + 1;
        var haut = new float[w * h]; for (int i = 0; i < haut.Length; i++) haut[i] = float.MinValue;
        for (int k = 0; k + 2 < t.Count; k += 3)
        {
            Vector3 a = t[k], b = t[k + 1], c = t[k + 2];
            int i0 = Mathf.FloorToInt((Mathf.Min(a.x, b.x, c.x) - x0) / Case), i1 = Mathf.CeilToInt((Mathf.Max(a.x, b.x, c.x) - x0) / Case);
            int j0 = Mathf.FloorToInt((Mathf.Min(a.z, b.z, c.z) - z0) / Case), j1 = Mathf.CeilToInt((Mathf.Max(a.z, b.z, c.z) - z0) / Case);
            float d = (b.z - c.z) * (a.x - c.x) + (c.x - b.x) * (a.z - c.z);
            if (Mathf.Abs(d) < 1e-8f) continue;
            for (int j = Mathf.Max(0, j0); j <= Mathf.Min(h - 1, j1); j++)
                for (int i = Mathf.Max(0, i0); i <= Mathf.Min(w - 1, i1); i++)
                {
                    float x = x0 + i * Case, z = z0 + j * Case;
                    float l1 = ((b.z - c.z) * (x - c.x) + (c.x - b.x) * (z - c.z)) / d, l2 = ((c.z - a.z) * (x - c.x) + (a.x - c.x) * (z - c.z)) / d, l3 = 1 - l1 - l2;
                    if (l1 < -.02f || l2 < -.02f || l3 < -.02f) continue;
                    float y = l1 * a.y + l2 * b.y + l3 * c.y;
                    if (y > haut[j * w + i]) haut[j * w + i] = y;
                }
        }
        using var flux = new MemoryStream(); using var e = new BinaryWriter(flux);
        e.Write(x0); e.Write(z0); e.Write(Case); e.Write(w); e.Write(h);
        for (int j = 0; j < h; j++)
            for (int i = 0; i < w; i++)
            {
                float y = haut[j * w + i];
                e.Write(y == float.MinValue ? (ushort)0 : (ushort)Mathf.Clamp(Mathf.RoundToInt(y * 1000) + 50000, 1, 65535));
                float u = (x0 + i * Case) / 3.5f, v = (z0 + j * Case) / 3.5f;
                e.Write((byte)Mathf.RoundToInt(TexNeige(u - Mathf.Floor(u), v - Mathf.Floor(v)).a * 255));
            }
        File.WriteAllBytes($"{Ressources}/NeigeGrille.bytes", flux.ToArray());
        AssetDatabase.ImportAsset($"{Ressources}/NeigeGrille.bytes", ImportAssetOptions.ForceUpdate);
        Debug.Log($"AMBIANCE grille de neige {w} × {h}");
    }

    // Vue aérienne du domaine pour la carte du toit (Scripts/CarteDomaine.cs) : Resources/Ambiance/CarteDomaine.png
    // (nord en haut, est à droite) et CarteDomaine.txt (centre x, z et demi-hauteur en mètres, monde Unity).
    static void CarteDomaine()
    {
        var b = new Bounds(); bool premier = true;
        foreach (var r in Object.FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None))
        {
            if (!r.enabled || r.gameObject.layer == 2 || r.bounds.size.magnitude > 60 || r.bounds.size.magnitude < 1) continue;
            if (premier) { b = r.bounds; premier = false; } else b.Encapsulate(r.bounds);
        }
        const float Aspect = 1.5f;
        float demiH = Mathf.Max(b.extents.z, b.extents.x / Aspect) + 6f;
        var go = new GameObject("CameraCarte") { hideFlags = HideFlags.HideAndDontSave };
        var cam = go.AddComponent<Camera>();
        cam.orthographic = true; cam.orthographicSize = demiH; cam.aspect = Aspect; cam.nearClipPlane = 1; cam.farClipPlane = 600;
        cam.useOcclusionCulling = false;
        go.transform.SetPositionAndRotation(new Vector3(b.center.x, 300, b.center.z), Quaternion.LookRotation(Vector3.down, Vector3.back));
        var rt = new RenderTexture(1536, 1024, 24) { antiAliasing = 4 };
        cam.targetTexture = rt; bool brume = RenderSettings.fog; RenderSettings.fog = false;
        cam.Render();
        RenderSettings.fog = brume;
        RenderTexture.active = rt;
        var t = new Texture2D(1536, 1024, TextureFormat.RGB24, false); t.ReadPixels(new Rect(0, 0, 1536, 1024), 0, 0); t.Apply();
        RenderTexture.active = null; cam.targetTexture = null;
        File.WriteAllBytes($"{Ressources}/CarteDomaine.png", t.EncodeToPNG());
        File.WriteAllText($"{Ressources}/CarteDomaine.txt", string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0} {1} {2} {3}", b.center.x, b.center.z, demiH, Aspect));
        Object.DestroyImmediate(t); Object.DestroyImmediate(rt); Object.DestroyImmediate(go);
        AssetDatabase.ImportAsset($"{Ressources}/CarteDomaine.png", ImportAssetOptions.ForceUpdate);
        AssetDatabase.ImportAsset($"{Ressources}/CarteDomaine.txt", ImportAssetOptions.ForceUpdate);
        Debug.Log($"AMBIANCE carte du domaine {b.center} demi-hauteur {demiH:F0} m");
    }

    // ---------- Post-traitement ----------
    static void PostTraitement()
    {
        string chemin = Maillages + "/ProfilLumiere.asset";
        var profil = AssetDatabase.LoadAssetAtPath<VolumeProfile>(chemin);
        if (profil == null) { profil = ScriptableObject.CreateInstance<VolumeProfile>(); AssetDatabase.CreateAsset(profil, chemin); }
        T Composant<T>() where T : VolumeComponent
        {
            if (!profil.TryGet<T>(out var c)) { c = profil.Add<T>(true); c.name = typeof(T).Name; AssetDatabase.AddObjectToAsset(c, profil); }
            c.active = true; return c;
        }
        var couleurs = Composant<ColorAdjustments>();
        couleurs.postExposure.Override(.08f); couleurs.contrast.Override(14); couleurs.saturation.Override(8);
        var bloom = Composant<Bloom>();
        bloom.threshold.Override(.92f); bloom.intensity.Override(.35f); bloom.scatter.Override(.6f); bloom.highQualityFiltering.Override(false);
        var vignette = Composant<Vignette>(); vignette.intensity.Override(.18f); vignette.smoothness.Override(.45f);
        var blanc = Composant<WhiteBalance>(); blanc.temperature.Override(4); blanc.tint.Override(1);
        var smh = Composant<ShadowsMidtonesHighlights>();
        smh.shadows.Override(new Vector4(.96f, .98f, 1.04f, 0)); smh.highlights.Override(new Vector4(1.03f, 1.01f, .97f, 0));
        EditorUtility.SetDirty(profil);
        var ancien = GameObject.Find("VolumeLumiere"); if (ancien != null) Object.DestroyImmediate(ancien);
        var vol = new GameObject("VolumeLumiere").AddComponent<Volume>(); vol.isGlobal = true; vol.priority = 1; vol.sharedProfile = profil;
        foreach (var cam in Object.FindObjectsByType<Camera>(FindObjectsInactive.Include))
        {
            var d = cam.GetUniversalAdditionalCameraData(); d.renderPostProcessing = true; d.renderShadows = true;
        }
        // Occlusion ambiante sur le rendu PC seulement (le rendu mobile reste léger).
        var donnees = AssetDatabase.LoadAssetAtPath<UniversalRendererData>("Assets/Settings/PC_Renderer.asset");
        if (donnees != null && !donnees.rendererFeatures.Any(f => f is ScreenSpaceAmbientOcclusion))
        {
            var ao = ScriptableObject.CreateInstance<ScreenSpaceAmbientOcclusion>(); ao.name = "OcclusionAmbiante";
            AssetDatabase.AddObjectToAsset(ao, donnees);
            var so = new SerializedObject(ao);
            void Reel(string p, float x) { var sp = so.FindProperty(p); if (sp != null) sp.floatValue = x; }
            void Bool(string p, bool x) { var sp = so.FindProperty(p); if (sp != null) sp.boolValue = x; }
            void Ent(string p, int x) { var sp = so.FindProperty(p); if (sp != null) sp.enumValueIndex = x; }
            Reel("m_Settings.Intensity", .8f); Reel("m_Settings.Radius", .35f); Reel("m_Settings.DirectLightingStrength", .2f);
            Bool("m_Settings.Downsample", true); Ent("m_Settings.Samples", 2); Ent("m_Settings.BlurQuality", 2);
            so.ApplyModifiedPropertiesWithoutUndo();
            donnees.rendererFeatures.Add(ao);
            AssetDatabase.SaveAssets();
            var sd = new SerializedObject(donnees); var carte = sd.FindProperty("m_RendererFeatureMap");
            if (carte != null && AssetDatabase.TryGetGUIDAndLocalFileIdentifier(ao, out _, out long id))
            { carte.InsertArrayElementAtIndex(carte.arraySize); carte.GetArrayElementAtIndex(carte.arraySize - 1).longValue = id; sd.ApplyModifiedPropertiesWithoutUndo(); }
            EditorUtility.SetDirty(donnees);
        }
    }
}

using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.Rendering;

// Décor de nuit, construit à la première tombée de la nuit (MomentJournee) :
// - jardin : guirlandes de guinguette tendues d'arbre en arbre et lanternes japonaises en papier
//   accrochées aux arbres proches du château, quelques lumières chaudes sous les arbres ;
// - intérieur : lustres allumés (couronne d'ampoules), abat-jour des lampes d'appoint lumineux avec
//   leur lumière, bougies des candélabres et appliques, sources existantes renforcées ;
// - tennis : quatre mâts d'éclairage (présents de jour, allumés la nuit).
// Ampoules et papier : shader Chateau/Lumineux (non éclairé) ; auréoles : Chateau/Halo (additif,
// quadrilatères tournés vers la caméra). Un seul maillage par matériau pour tout le décor fixe.
public static class DecorNuit
{
    static readonly Color Chaud = new(1f, .82f, .55f);
    static readonly Color[] Guinguette =
    {
        new(1f, .86f, .6f), new(1f, .64f, .28f), new(1f, .86f, .6f), new(1f, .52f, .56f),
        new(1f, .86f, .6f), new(.6f, 1f, .72f), new(1f, .86f, .6f), new(.58f, .76f, 1f), new(1f, .93f, .45f),
    };
    static readonly Color[] Papiers = { new(1f, .42f, .22f), new(1f, .8f, .5f), new(1f, .6f, .3f), new(1f, .33f, .3f), new(1f, .88f, .66f) };

    static bool construit, tennisConstruit;
    static GameObject racine;
    static Material lumineux, halo, fenetre, verreTennis;
    static readonly List<(Light l, float intensite, float portee)> lumieresChateau = new();
    static readonly List<(Renderer r, Material[] origine, Material[] allume)> abatJours = new();
    static readonly List<Light> projecteurs = new();
    public static int Ampoules { get; private set; }
    public static int Lanternes { get; private set; }
    public static int Guirlandes { get; private set; }

    class Lot
    {
        public readonly List<Vector3> v = new(); public readonly List<Color> c = new(); public readonly List<int> t = new();
        public readonly List<Vector2> uv = new(), uv2 = new();
        public Mesh Maillage(string nom)
        {
            var m = new Mesh { name = nom, indexFormat = v.Count > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
            m.SetVertices(v); m.SetColors(c); if (uv.Count == v.Count) { m.SetUVs(0, uv); m.SetUVs(1, uv2); }
            m.SetTriangles(t, 0); m.RecalculateBounds();
            // Halos : les sommets sont aux centres, la boîte doit couvrir les quadrilatères étendus.
            var b = m.bounds; b.Expand(4); m.bounds = b;
            return m;
        }
    }

    public static void Allumer(bool nuit)
    {
        if (!Charger()) return;
        Tennis();
        if (nuit && !construit) Construire();
        if (racine != null) racine.SetActive(nuit);
        foreach (var v in vantaux) if (v != null) v.SetActive(nuit);
        foreach (var (l, i, p) in lumieresChateau) if (l != null) { l.intensity = nuit ? i * 1.5f : i; l.range = nuit ? Mathf.Max(p, 10) : p; }
        foreach (var (r, origine, allume) in abatJours) if (r != null) r.sharedMaterials = nuit ? allume : origine;
        foreach (var l in projecteurs) if (l != null) l.enabled = nuit;
        if (halosTennis != null) halosTennis.SetActive(nuit);
        if (verreTennis != null) verreTennis.SetColor("_BaseColor", nuit ? new Color(1f, .98f, .9f) : new Color(.22f, .23f, .24f));
    }

    static bool Charger()
    {
        if (lumineux != null && halo != null) return true;
        var l = Resources.Load<Material>("Nuit/Lumineux"); var h = Resources.Load<Material>("Nuit/Halo");
        if (l == null || h == null) { Debug.LogWarning("DecorNuit : matériaux Resources/Nuit absents"); return false; }
        lumineux = new Material(l); halo = new Material(h);
        var f = Resources.Load<Material>("Nuit/Fenetre"); if (f != null) fenetre = new Material(f);
        return true;
    }

    static void Construire()
    {
        construit = true;
        racine = new GameObject("DecorNuit");
        var coeurs = new Lot(); var halos = new Lot();
        Jardin(coeurs, halos);
        Bornes(coeurs, halos);
        Interieur(coeurs, halos);
        Bassin(coeurs, halos);
        Fenetres();
        Objet("Ampoules", coeurs.Maillage("AmpoulesNuit"), lumineux, racine.transform);
        Objet("Halos", halos.Maillage("HalosNuit"), halo, racine.transform);
        Debug.Log($"NUIT décor : {Guirlandes} guirlandes, {Lanternes} lanternes, {Ampoules} ampoules, {lumieresChateau.Count} sources du château, {abatJours.Count} abat-jour");
    }

    static GameObject Objet(string nom, Mesh maillage, Material mat, Transform parent)
    {
        var go = new GameObject(nom); go.transform.SetParent(parent, false); go.layer = 2;
        go.AddComponent<MeshFilter>().sharedMesh = maillage;
        var r = go.AddComponent<MeshRenderer>(); r.sharedMaterial = mat;
        r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false; r.lightProbeUsage = LightProbeUsage.Off;
        return go;
    }

    static Light Lumiere(Transform parent, Vector3 position, float portee, float intensite, Color couleur)
    {
        var go = new GameObject("LumiereNuit"); go.transform.SetParent(parent, false); go.transform.position = position;
        var l = go.AddComponent<Light>(); l.type = LightType.Point; l.range = portee; l.intensity = intensite; l.color = couleur; l.shadows = LightShadows.None;
        return l;
    }

    // ---------- Jardin ----------
    struct Arbre { public Vector3 pied; public float hauteur, rayon; public Collider collider; }

    static void Jardin(Lot coeurs, Lot halos)
    {
        var motif = new Regex(@"^parc_(platane|chene|olivier|alep|feuillu)_\d+$");
        var arbres = new List<Arbre>();
        var centre = new Vector3(0, 0, 18);
        foreach (var r in Object.FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None))
        {
            if (!motif.IsMatch(r.name)) continue;
            var b = r.bounds;
            Vector3 pied = new(b.center.x, b.min.y, b.center.z);
            if (Vector3.Distance(new Vector3(pied.x, 0, pied.z), centre) > 130) continue;
            arbres.Add(new Arbre { pied = pied, hauteur = b.size.y, rayon = Mathf.Min(b.extents.x, b.extents.z), collider = r.GetComponent<Collider>() });
        }
        arbres.Sort((a, b) => Vector3.Distance(a.pied, centre).CompareTo(Vector3.Distance(b.pied, centre)));
        if (arbres.Count > 64) arbres.RemoveRange(64, arbres.Count - 64);
        var hasard = new System.Random(1931);

        // Lanternes japonaises autour de chaque arbre, au bord du houppier.
        for (int i = 0; i < arbres.Count; i++)
        {
            var a = arbres[i];
            int n = a.rayon > 3 ? 5 : a.rayon > 1.8f ? 4 : 3;
            float phase = (float)hasard.NextDouble() * 360;
            float accroche = Mathf.Clamp(a.hauteur * .42f, 2.5f, 4.6f);
            for (int k = 0; k < n; k++)
            {
                float angle = (phase + k * 360f / n + (float)hasard.NextDouble() * 25) * Mathf.Deg2Rad;
                float rr = a.rayon * (.82f + (float)hasard.NextDouble() * .18f);
                Vector3 haut = a.pied + new Vector3(Mathf.Cos(angle) * rr, accroche + (float)hasard.NextDouble() * .5f, Mathf.Sin(angle) * rr);
                float fil = .35f + (float)hasard.NextDouble() * .45f;
                Lanterne(coeurs, halos, haut, fil, Papiers[hasard.Next(Papiers.Length)], .8f + (float)hasard.NextDouble() * .4f);
            }
            if (i < 14) Lumiere(racine.transform, a.pied + Vector3.up * (accroche - .4f), 9, 1.7f, new Color(1f, .7f, .42f));
            // Projecteur au pied de chaque arbre : halo chaud sur le tronc et au sol.
            Halo(halos, a.pied + Vector3.up * .15f, Mathf.Clamp(a.rayon, 1.5f, 3.5f), Chaud * .3f);
        }

        // Guirlandes : chaque arbre relié à ses deux plus proches voisins (entre 5 et 24 m), si rien ne gêne.
        var paires = new HashSet<(int, int)>();
        for (int i = 0; i < arbres.Count; i++)
        {
            var voisins = new List<int>();
            for (int j = 0; j < arbres.Count; j++) if (j != i) voisins.Add(j);
            voisins.Sort((x, y) => Distance2D(arbres[i], arbres[x]).CompareTo(Distance2D(arbres[i], arbres[y])));
            int pris = 0;
            foreach (int j in voisins)
            {
                if (pris >= 2) break;
                float d = Distance2D(arbres[i], arbres[j]);
                if (d < 5 || d > 24) continue;
                var cle = i < j ? (i, j) : (j, i);
                if (paires.Contains(cle)) { pris++; continue; }
                if (Guirlande(coeurs, halos, arbres[i], arbres[j], paires.Count)) { paires.Add(cle); pris++; }
            }
        }

        // Lampadaires de la terrasse et lampe de table.
        foreach (var r in Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None))
        {
            string n = r.name;
            if (n.StartsWith("terrasse_lampadaire") || n.Contains("terrasse_lampe_table"))
            {
                var b = r.bounds; Vector3 p = new(b.center.x, b.max.y - Mathf.Min(.25f, b.size.y * .2f), b.center.z);
                Ampoule(coeurs, halos, p, .06f, Chaud, 1.1f);
                Lumiere(r.transform, p, 6, 1.3f, Chaud);
            }
        }
    }

    // Bornes lumineuses le long des allées : poteau sombre, tête chaude, flaque de lumière au sol ; une vraie
    // source de lumière toutes les quatre bornes (le WebGL limite le nombre de lumières par objet).
    static void Bornes(Lot coeurs, Lot halos)
    {
        var retenues = new List<Vector3>();
        foreach (var r in Object.FindObjectsByType<MeshRenderer>(FindObjectsInactive.Exclude))
        {
            string n = r.name;
            if (!n.StartsWith("parc_allee") && !n.StartsWith("parc_cour") && !n.StartsWith("parc_plateforme_ouest")) continue;
            var f = r.GetComponent<MeshFilter>(); if (f == null || f.sharedMesh == null) continue;
            bool bordure = n.EndsWith("_bordures");
            var sommets = f.sharedMesh.vertices;
            int pas = Mathf.Max(1, sommets.Length / 400);
            for (int i = 0; i < sommets.Length; i += pas)
            {
                Vector3 p = r.transform.TransformPoint(sommets[i]);
                if (!bordure && !n.StartsWith("parc_allee")) { if (i % (pas * 7) != 0) continue; }
                bool proche = false;
                foreach (var q in retenues) if ((q - p).sqrMagnitude < 81f) { proche = true; break; }
                if (proche || retenues.Count >= 90) continue;
                // Pas sur un bâtiment ni dans l'eau.
                if (Physics.CheckSphere(p + Vector3.up * .6f, .3f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) continue;
                retenues.Add(p);
            }
        }
        var poteau = new Color(.06f, .06f, .07f);
        for (int i = 0; i < retenues.Count; i++)
        {
            Vector3 p = retenues[i];
            Cylindre(coeurs, p, p + Vector3.up * .62f, .06f, poteau);
            Ampoule(coeurs, halos, p + Vector3.up * .68f, .07f, Chaud, .8f);
            Halo(halos, p + Vector3.up * .03f, 3.2f, Chaud * .32f);
            if (i % 4 == 0 && i / 4 < 18) Lumiere(racine.transform, p + Vector3.up * .8f, 7, 1.4f, Chaud);
        }
        Ampoules += retenues.Count;
        Debug.Log($"NUIT bornes {retenues.Count}");
    }

    static float Distance2D(Arbre a, Arbre b) => Vector2.Distance(new Vector2(a.pied.x, a.pied.z), new Vector2(b.pied.x, b.pied.z));

    static bool Guirlande(Lot coeurs, Lot halos, Arbre a, Arbre b, int numero)
    {
        Vector3 ab = b.pied - a.pied; ab.y = 0; ab.Normalize();
        float ha = Mathf.Clamp(a.hauteur * .48f, 2.8f, 4.4f), hb = Mathf.Clamp(b.hauteur * .48f, 2.8f, 4.4f);
        Vector3 pa = a.pied + ab * Mathf.Min(a.rayon * .5f, 2.2f) + Vector3.up * ha;
        Vector3 pb = b.pied - ab * Mathf.Min(b.rayon * .5f, 2.2f) + Vector3.up * hb;
        float longueur = Vector3.Distance(pa, pb);
        float fleche = .25f + longueur * .07f;
        // Rien entre les deux arbres (mur, toiture, autre arbre) à la hauteur de la guirlande ni au creux.
        Vector3 milieu = (pa + pb) * .5f + Vector3.down * fleche;
        foreach (var (p, q) in new[] { (pa, milieu), (milieu, pb) })
            foreach (var h in Physics.RaycastAll(p, q - p, Vector3.Distance(p, q), Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                if (h.collider != a.collider && h.collider != b.collider) return false;
        int segments = Mathf.Max(8, Mathf.RoundToInt(longueur / .3f));
        Vector3 Point(float s) => Vector3.Lerp(pa, pb, s) + Vector3.down * (fleche * 4 * s * (1 - s));
        for (int k = 0; k < segments; k++) Fil(coeurs, Point((float)k / segments), Point((float)(k + 1) / segments), .009f, new Color(.05f, .05f, .05f));
        int ampoules = Mathf.Max(4, Mathf.RoundToInt(longueur / .62f));
        for (int k = 1; k < ampoules; k++)
        {
            Vector3 p = Point((float)k / ampoules) + Vector3.down * .06f;
            Fil(coeurs, p, p + Vector3.up * .06f, .006f, new Color(.05f, .05f, .05f));
            Ampoule(coeurs, halos, p, .038f, Guinguette[(k + numero * 3) % Guinguette.Length], .42f);
        }
        Guirlandes++;
        return true;
    }

    // ---------- Primitives ----------
    static void Ampoule(Lot coeurs, Lot halos, Vector3 p, float rayon, Color couleur, float tailleHalo)
    {
        Octaedre(coeurs, p, rayon, Color.Lerp(couleur, Color.white, .45f));
        Halo(halos, p, tailleHalo, couleur * .8f);
        Ampoules++;
    }

    static void Halo(Lot l, Vector3 p, float taille, Color couleur)
    {
        int i = l.v.Count;
        Vector2[] coins = { new(-1, -1), new(1, -1), new(1, 1), new(-1, 1) };
        foreach (var c in coins) { l.v.Add(p); l.c.Add(couleur); l.uv.Add(c); l.uv2.Add(new Vector2(taille, 0)); }
        l.t.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
    }

    static void Octaedre(Lot l, Vector3 p, float r, Color couleur)
    {
        int i = l.v.Count;
        Vector3[] s = { Vector3.up, Vector3.down, Vector3.left, Vector3.right, Vector3.forward, Vector3.back };
        foreach (var d in s) { l.v.Add(p + d * r); l.c.Add(couleur); }
        int[] f = { 0, 2, 4, 0, 4, 3, 0, 3, 5, 0, 5, 2, 1, 4, 2, 1, 3, 4, 1, 5, 3, 1, 2, 5 };
        foreach (int k in f) l.t.Add(i + k);
    }

    // Fil : deux rubans croisés.
    static void Fil(Lot l, Vector3 a, Vector3 b, float largeur, Color couleur)
    {
        Vector3 d = (b - a).normalized; if (d.sqrMagnitude < 1e-6f) return;
        Vector3 u = Vector3.Cross(d, Mathf.Abs(d.y) > .9f ? Vector3.right : Vector3.up).normalized * largeur, w = Vector3.Cross(d, u).normalized * largeur;
        foreach (var e in new[] { u, w })
        {
            int i = l.v.Count;
            l.v.Add(a - e); l.v.Add(a + e); l.v.Add(b + e); l.v.Add(b - e);
            for (int k = 0; k < 4; k++) l.c.Add(couleur);
            l.t.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
        }
    }

    // Lanterne japonaise (chōchin) : corps en papier à côtes, cerclages noirs en haut et en bas, suspendue
    // par un fil sous le point d'accroche.
    static void Lanterne(Lot coeurs, Lot halos, Vector3 accroche, float fil, Color papier, float echelle)
    {
        float hauteur = .44f * echelle, rayon = .17f * echelle;
        Vector3 haut = accroche + Vector3.down * fil;
        Fil(coeurs, accroche, haut, .007f, new Color(.04f, .04f, .04f));
        const int anneaux = 10, cotes = 12;
        Color noir = new(.05f, .04f, .035f);
        int depart = coeurs.v.Count;
        for (int k = 0; k <= anneaux; k++)
        {
            float s = (float)k / anneaux;
            float r = rayon * Mathf.Max(.55f, Mathf.Sin(Mathf.PI * (.08f + .84f * s)));
            float y = -hauteur * s;
            // Côtes de bambou : un anneau sur deux plus sombre ; papier plus clair au ventre.
            Color c = papier * (k % 2 == 0 ? .78f : 1f) * (.82f + .18f * Mathf.Sin(Mathf.PI * s));
            for (int j = 0; j < cotes; j++)
            {
                float a = j * Mathf.PI * 2 / cotes;
                coeurs.v.Add(haut + new Vector3(Mathf.Cos(a) * r, y, Mathf.Sin(a) * r)); c.a = 1; coeurs.c.Add(c);
            }
        }
        for (int k = 0; k < anneaux; k++)
            for (int j = 0; j < cotes; j++)
            {
                int a = depart + k * cotes + j, b = depart + k * cotes + (j + 1) % cotes;
                coeurs.t.AddRange(new[] { a, b, b + cotes, a, b + cotes, a + cotes });
            }
        float rc = rayon * .58f;
        Cylindre(coeurs, haut + Vector3.up * .03f, haut + Vector3.down * .025f, rc, noir);
        Cylindre(coeurs, haut + Vector3.down * (hauteur - .025f), haut + Vector3.down * (hauteur + .03f), rc, noir);
        Halo(halos, haut + Vector3.down * hauteur * .5f, 1.1f * echelle, papier * .55f);
        Lanternes++;
    }

    static void Cylindre(Lot l, Vector3 a, Vector3 b, float r, Color couleur)
    {
        const int n = 12; int i = l.v.Count;
        for (int k = 0; k < n; k++)
        {
            float t = k * Mathf.PI * 2 / n; Vector3 o = new(Mathf.Cos(t) * r, 0, Mathf.Sin(t) * r);
            l.v.Add(a + o); l.v.Add(b + o); l.c.Add(couleur); l.c.Add(couleur);
        }
        l.v.Add(a); l.v.Add(b); l.c.Add(couleur); l.c.Add(couleur);
        int ca = i + 2 * n, cb = ca + 1;
        for (int k = 0; k < n; k++)
        {
            int p = i + 2 * k, q = i + 2 * ((k + 1) % n);
            l.t.AddRange(new[] { p, q, q + 1, p, q + 1, p + 1, ca, q, p, cb, p + 1, q + 1 });
        }
    }

    // ---------- Intérieur ----------
    static void Interieur(Lot coeurs, Lot halos)
    {
        var chateau = GameObject.Find("Chateau");
        if (chateau == null) return;
        foreach (var l in chateau.GetComponentsInChildren<Light>(true))
        {
            if (l.type == LightType.Directional) continue;
            lumieresChateau.Add((l, l.intensity, l.range));
        }
        var allume = new Material(lumineux); allume.SetFloat("_Sommets", 0); allume.SetColor("_BaseColor", new Color(1f, .8f, .55f));
        var renderers = new List<Renderer>(chateau.GetComponentsInChildren<Renderer>(true));
        int lumieresAjoutees = 0;
        foreach (var r in renderers)
        {
            string n = r.name.ToLowerInvariant();
            if (n.StartsWith("lumiere_") || n.StartsWith("terrasse_") || n.StartsWith("parc_") || n.StartsWith("bati_") || n.StartsWith("toiture_") || n.StartsWith("coque_")) continue;
            var b = r.bounds;
            if (n.Contains("lustre") && !n.Contains("tige"))
            {
                // Couronne de huit bougies électriques au niveau des bras du lustre.
                float rayon = Mathf.Max(.15f, Mathf.Min(b.extents.x, b.extents.z) * .78f);
                float y = b.center.y + b.extents.y * .15f;
                for (int k = 0; k < 8; k++)
                {
                    float a = k * Mathf.PI / 4;
                    Ampoule(coeurs, halos, new Vector3(b.center.x + Mathf.Cos(a) * rayon, y, b.center.z + Mathf.Sin(a) * rayon), .028f, Chaud, .38f);
                }
                Halo(halos, new Vector3(b.center.x, y, b.center.z), rayon * 3.2f, Chaud * .25f);
            }
            else if (n.Contains("abat_jour"))
            {
                var mats = r.sharedMaterials; var allumes = new Material[mats.Length];
                for (int i = 0; i < mats.Length; i++) allumes[i] = allume;
                abatJours.Add((r, mats, allumes));
                Halo(halos, b.center, Mathf.Max(b.size.x, b.size.y) * 2.4f, Chaud * .35f);
                if (lumieresAjoutees++ < 18) Lumiere(racine.transform, b.center + Vector3.down * b.extents.y * .3f, 4.5f, 1.6f, Chaud);
            }
            else if (n.Contains("candelabre") || n.Contains("applique") || n.Contains("bouillotte") || n.Contains("lampe_balustre") || n.Contains("lanterne"))
            {
                Vector3 p = n.Contains("candelabre") || n.Contains("bouillotte") || n.Contains("balustre") ? new Vector3(b.center.x, b.max.y - .02f, b.center.z) : b.center;
                Ampoule(coeurs, halos, p, .03f, Chaud, .5f);
                if (n.Contains("bouillotte") || n.Contains("balustre")) Lumiere(racine.transform, p, 3.5f, 1.2f, Chaud);
            }
        }
    }

    // ---------- Fenêtres ----------
    // Toutes les fenêtres du bâti (pièces modélisées ou non, combles compris) : un panneau lumineux additif
    // juste derrière chaque vitrage, tourné vers l'extérieur. Vitrages fixes réunis en un maillage ; vantaux
    // ouvrants : un panneau enfant du vantail, qui le suit.
    public static int NombreFenetres { get; private set; }
    static void Fenetres()
    {
        var chateau = GameObject.Find("Chateau");
        if (chateau == null || fenetre == null) return;
        var fixes = new Lot(); var hasard = new System.Random(1895);
        var centre = new Vector3(0, 0, 1);
        foreach (var r in chateau.GetComponentsInChildren<MeshRenderer>(true))
        {
            string n = r.name;
            if (!n.StartsWith("bati_vitrage") && !n.StartsWith("bati_porte_entree_vitrage")) continue;
            var f = r.GetComponent<MeshFilter>(); if (f == null || f.sharedMesh == null) continue;
            // Axe de la largeur : plus grande dispersion horizontale des sommets (analyse en composantes).
            var sommets = f.sharedMesh.vertices; var m = r.transform.localToWorldMatrix;
            Vector3 c = r.bounds.center; float xx = 0, zz = 0, xz = 0;
            foreach (var v in sommets) { Vector3 p = m.MultiplyPoint3x4(v) - c; xx += p.x * p.x; zz += p.z * p.z; xz += p.x * p.z; }
            float angle = .5f * Mathf.Atan2(2 * xz, xx - zz);
            Vector3 largeur = new(Mathf.Cos(angle), 0, Mathf.Sin(angle));
            Vector3 normale = new(-largeur.z, 0, largeur.x);
            Vector3 dehors = c - centre; dehors.y = 0;
            if (Vector3.Dot(normale, dehors) < 0) normale = -normale;
            float demi = 0, haut = r.bounds.extents.y;
            foreach (var v in sommets) demi = Mathf.Max(demi, Mathf.Abs(Vector3.Dot(m.MultiplyPoint3x4(v) - c, largeur)));
            if (demi < .15f || haut < .2f) continue;
            float eclat = .55f + (float)hasard.NextDouble() * .4f;
            Color teinte = hasard.NextDouble() < .2f ? new Color(1f, .86f, .62f) : new Color(1f, .7f, .4f);
            bool mobile = r.GetComponentInParent<Porte>() != null;
            var lot = mobile ? new Lot() : fixes;
            // Vitrage opaque (combles) : il masquerait un panneau placé derrière ; le panneau passe devant.
            bool opaque = true; foreach (var mm in r.sharedMaterials) if (mm != null && mm.renderQueue >= 2450) opaque = false;
            float avant = 0; foreach (var v in sommets) avant = Mathf.Max(avant, Vector3.Dot(m.MultiplyPoint3x4(v) - c, normale));
            Panneau(lot, c + normale * (opaque ? avant + .015f : -.1f), normale, demi * .96f, haut * .96f, teinte * eclat);
            if (mobile)
            {
                var go = Objet("LumiereFenetre", lot.Maillage("LumiereFenetre"), fenetre, racine.transform);
                go.transform.SetParent(r.transform, true);
                vantaux.Add(go);
            }
            NombreFenetres++;
        }
        Objet("LumieresFenetres", fixes.Maillage("LumieresFenetres"), fenetre, racine.transform);
    }
    static readonly List<GameObject> vantaux = new();

    // Quadrilatère face à normale (sens horaire vu de devant), uv de 0 à 1.
    static void Panneau(Lot l, Vector3 c, Vector3 normale, float demiLargeur, float demiHauteur, Color couleur)
    {
        Vector3 a = Vector3.Cross(normale, Vector3.up).normalized * demiLargeur, h = Vector3.up * demiHauteur;
        int i = l.v.Count;
        l.v.Add(c - a - h); l.v.Add(c - a + h); l.v.Add(c + a + h); l.v.Add(c + a - h);
        l.uv.Add(new Vector2(0, 0)); l.uv.Add(new Vector2(0, 1)); l.uv.Add(new Vector2(1, 1)); l.uv.Add(new Vector2(1, 0));
        for (int k = 0; k < 4; k++) { l.c.Add(couleur); l.uv2.Add(Vector2.zero); }
        l.t.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
    }

    // ---------- Bassin ----------
    // Projecteurs immergés tout autour du bassin, lumière froide sur l'eau et sur le jet de la fontaine.
    static void Bassin(Lot coeurs, Lot halos)
    {
        var eau = GameObject.Find("parc_bassin_eau");
        var re = eau != null ? eau.GetComponentInChildren<Renderer>() : null;
        if (re == null) return;
        var b = re.bounds; Color bleu = new(.55f, .85f, 1f);
        float y = b.max.y + .03f;
        Halo(halos, new Vector3(b.center.x, y, b.center.z), Mathf.Max(b.extents.x, b.extents.z) * 2.2f, bleu * .18f);
        // Projecteurs immergés le long du vrai contour de l'eau (bassin en haricot), sous la surface.
        var f = re.GetComponent<MeshFilter>();
        if (f != null && f.sharedMesh != null)
        {
            var sommets = f.sharedMesh.vertices;
            Vector3 c = b.center;
            var bords = new Vector3[24]; var loin = new float[24];
            foreach (var v0 in sommets)
            {
                Vector3 v = re.transform.TransformPoint(v0);
                Vector2 d = new(v.x - c.x, v.z - c.z);
                int k = Mathf.FloorToInt((Mathf.Atan2(d.y, d.x) / (2 * Mathf.PI) + 1) * 24) % 24;
                if (d.sqrMagnitude > loin[k]) { loin[k] = d.sqrMagnitude; bords[k] = v; }
            }
            int sources = 0;
            for (int k = 0; k < 24; k++)
            {
                if (loin[k] <= 0) continue;
                Vector3 p = Vector3.Lerp(new Vector3(c.x, bords[k].y, c.z), bords[k], .9f) + Vector3.down * .35f;
                Octaedre(coeurs, p, .05f, Color.Lerp(bleu, Color.white, .6f));
                Halo(halos, p + Vector3.up * .36f, 1.4f, bleu * .55f);
                Ampoules++;
                if (k % 6 == 0 && sources++ < 4) Lumiere(racine.transform, p + Vector3.up * .1f, 6, 2.2f, new Color(.55f, .85f, 1f));
            }
        }
        Lumiere(racine.transform, new Vector3(b.center.x, y + .7f, b.center.z), Mathf.Max(b.extents.x, b.extents.z) + 5, 2.4f, new Color(.7f, .88f, 1f));
        var jet = GameObject.Find("parc_fontaine_jet");
        var rj = jet != null ? jet.GetComponentInChildren<Renderer>() : null;
        if (rj != null) Lumiere(racine.transform, rj.bounds.center + Vector3.down * rj.bounds.extents.y * .5f, 5, 2f, new Color(.8f, .92f, 1f));
    }

    // ---------- Tennis ----------
    static void Tennis()
    {
        if (tennisConstruit) return;
        tennisConstruit = true;
        var court = GameObject.Find("parc_tennis_court"); var enceinte = GameObject.Find("parc_tennis_enceinte");
        var rc = court != null ? court.GetComponentInChildren<Renderer>() : null;
        var re = enceinte != null ? enceinte.GetComponentInChildren<Renderer>() : null;
        if (rc == null) return;
        Bounds jeu = rc.bounds, tour = re != null ? re.bounds : rc.bounds;
        var go = new GameObject("EclairageTennis");
        var lit = Shader.Find("Universal Render Pipeline/Lit");
        var mat = new Material(lit); mat.SetColor("_BaseColor", new Color(.16f, .22f, .19f)); mat.SetFloat("_Metallic", .5f); mat.SetFloat("_Smoothness", .45f);
        verreTennis = new Material(lumineux); verreTennis.SetFloat("_Sommets", 0);
        var halos = new Lot();
        Vector3 c = new(jeu.center.x, jeu.max.y, jeu.center.z);
        float dx = Mathf.Max(tour.extents.x - .5f, jeu.extents.x), dz = Mathf.Max(tour.extents.z - .5f, jeu.extents.z);
        const float hauteur = 9;
        for (int i = 0; i < 4; i++)
        {
            Vector3 pied = new(tour.center.x + (i % 2 == 0 ? -dx : dx), jeu.max.y, tour.center.z + (i < 2 ? -dz : dz));
            var mat2 = GameObject.CreatePrimitive(PrimitiveType.Cylinder); mat2.name = "MatTennis" + i; Object.Destroy(mat2.GetComponent<Collider>());
            mat2.transform.SetParent(go.transform, false); mat2.transform.position = pied + Vector3.up * hauteur * .5f;
            mat2.transform.localScale = new Vector3(.16f, hauteur * .5f, .16f); mat2.GetComponent<Renderer>().sharedMaterial = mat;
            Vector3 tete = pied + Vector3.up * hauteur;
            Vector3 vise = Vector3.Lerp(c, new Vector3(pied.x, c.y, pied.z), .35f);
            var rot = Quaternion.LookRotation(vise - tete);
            var boitier = GameObject.CreatePrimitive(PrimitiveType.Cube); boitier.name = "Projecteur"; Object.Destroy(boitier.GetComponent<Collider>());
            boitier.transform.SetParent(go.transform, false); boitier.transform.SetPositionAndRotation(tete, rot);
            boitier.transform.localScale = new Vector3(1.1f, .6f, .22f); boitier.GetComponent<Renderer>().sharedMaterial = mat;
            var verre = GameObject.CreatePrimitive(PrimitiveType.Quad); verre.name = "Verre"; Object.Destroy(verre.GetComponent<Collider>());
            verre.transform.SetParent(go.transform, false);
            verre.transform.SetPositionAndRotation(tete + rot * Vector3.forward * .115f, rot * Quaternion.Euler(0, 180, 0));
            verre.transform.localScale = new Vector3(1f, .5f, 1);
            var rv = verre.GetComponent<Renderer>(); rv.sharedMaterial = verreTennis; rv.shadowCastingMode = ShadowCastingMode.Off;
            Halo(halos, tete + rot * Vector3.forward * .3f, 2.4f, new Color(.85f, .85f, .8f));
            var l = new GameObject("LumiereTennis").AddComponent<Light>(); l.transform.SetParent(go.transform, false);
            l.transform.SetPositionAndRotation(tete + rot * Vector3.forward * .3f, rot);
            l.type = LightType.Spot; l.spotAngle = 105; l.innerSpotAngle = 60; l.range = 34; l.intensity = 7; l.color = new Color(1f, .97f, .9f);
            l.shadows = LightShadows.None; l.renderMode = LightRenderMode.ForcePixel; l.enabled = false;
            projecteurs.Add(l);
        }
        // Halos des projecteurs : la nuit seulement (Allumer).
        halosTennis = Objet("HalosTennis", halos.Maillage("HalosTennis"), halo, go.transform);
        halosTennis.SetActive(false);
    }
    static GameObject halosTennis;
}

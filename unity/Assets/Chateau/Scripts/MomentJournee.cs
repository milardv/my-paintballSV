using System;
using UnityEngine;
using UnityEngine.Rendering;

// Moment de la journée : par défaut celui de la France à l'instant (position réelle du soleil à Marseille,
// calculée depuis l'heure UTC), ou jour / nuit imposés dans les options. Oriente le soleil, règle sa couleur,
// la lumière ambiante et le ciel ; la nuit, la lune prend le relais et le décor de nuit s'allume (DecorNuit).
// Test : ?heure=22:30 dans l'adresse impose une heure de France.
public class MomentJournee : MonoBehaviour
{
    public static readonly string[] NomsModes = { "Heure de France", "Jour", "Nuit" };
    const double Latitude = 43.29, Longitude = 5.37;
    // Repère de la scène (D-026) : nord = -Z, est = -X.
    static readonly Vector3 Nord = Vector3.back, Est = Vector3.left;

    public static MomentJournee Instance { get; private set; }
    public static bool EstNuit => Instance != null && Instance.nuit;
    public float Elevation { get; private set; }
    public float Azimut { get; private set; }
    public DateTime HeureFrance { get; private set; }

    Light soleil;
    Material ciel;
    GameObject etoiles, lune;
    Material materiauLune;
    Material materiauEtoiles;
    bool nuit, premier = true;
    float prochainCalcul;
    double heureImposee = -1;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        if (Instance != null) return;
        new GameObject("MomentJournee").AddComponent<MomentJournee>();
    }

    void Awake()
    {
        Instance = this;
        var go = GameObject.Find("Soleil");
        soleil = go != null ? go.GetComponent<Light>() : null;
        if (soleil == null) foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None)) if (l.type == LightType.Directional) { soleil = l; break; }
        if (RenderSettings.skybox != null) { ciel = new Material(RenderSettings.skybox); RenderSettings.skybox = ciel; }
        if (soleil != null) RenderSettings.sun = soleil;
        LireAdresse();
        Calculer();
    }

    void LireAdresse()
    {
        string url = Application.absoluteURL;
        int i = string.IsNullOrEmpty(url) ? -1 : url.IndexOf("heure=", StringComparison.Ordinal);
        if (i < 0) return;
        string v = url.Substring(i + 6); int fin = v.IndexOfAny(new[] { '&', '#' }); if (fin >= 0) v = v.Substring(0, fin);
        var morceaux = Uri.UnescapeDataString(v).Replace('h', ':').Split(':');
        if (double.TryParse(morceaux[0], out double h))
            heureImposee = h + (morceaux.Length > 1 && double.TryParse(morceaux[1], out double m) ? m / 60 : 0);
    }

    // Appelé par Reglages.Appliquer après un changement d'option.
    public static void Actualiser() { if (Instance != null) { Instance.prochainCalcul = 0; Instance.Calculer(); } }

    float grisApplique;
    void Update()
    {
        // Ciel couvert de la neige : réappliqué au fil de sa montée.
        if (Mathf.Abs(Neige.Gris - grisApplique) > .01f) Appliquer();
        if (Time.unscaledTime < prochainCalcul) return;
        Calculer();
    }

    void Calculer()
    {
        prochainCalcul = Time.unscaledTime + 20;
        DateTime utc = DateTime.UtcNow;
        int mode = Reglages.Moment;
        double heure = heureImposee >= 0 ? heureImposee : mode == 1 ? 15.5 : mode == 2 ? 23 : -1;
        if (heure >= 0)
        {
            // Heure de France imposée, le jour d'aujourd'hui.
            var local = FranceDepuisUtc(utc).Date.AddHours(heure);
            utc = local.AddHours(-DecalageFrance(local.AddHours(-1)));
        }
        HeureFrance = FranceDepuisUtc(utc);
        PositionSoleil(utc, out double el, out double az);
        Elevation = (float)el; Azimut = (float)az;
        Appliquer();
    }

    public static DateTime FranceDepuisUtc(DateTime utc) => utc.AddHours(DecalageFrance(utc));

    // Heure d'été européenne : du dernier dimanche de mars au dernier dimanche d'octobre, à 1 h UTC.
    static int DecalageFrance(DateTime utc)
    {
        DateTime debut = DernierDimanche(utc.Year, 3).AddHours(1), fin = DernierDimanche(utc.Year, 10).AddHours(1);
        return utc >= debut && utc < fin ? 2 : 1;
    }

    static DateTime DernierDimanche(int annee, int mois)
    {
        var d = new DateTime(annee, mois, DateTime.DaysInMonth(annee, mois));
        return d.AddDays(-(int)d.DayOfWeek);
    }

    // Position apparente du soleil (formules simplifiées de l'Astronomical Almanac, ~0,1°) :
    // élévation au-dessus de l'horizon et azimut compté depuis le nord vers l'est, en degrés.
    public static void PositionSoleil(DateTime utc, out double elevation, out double azimut)
    {
        const double rad = Math.PI / 180;
        double n = utc.ToOADate() + 2415018.5 - 2451545.0;
        double L = (280.460 + .9856474 * n) % 360, g = (357.528 + .9856003 * n) % 360 * rad;
        double lambda = (L + 1.915 * Math.Sin(g) + .020 * Math.Sin(2 * g)) * rad;
        double eps = (23.439 - .0000004 * n) * rad;
        double ra = Math.Atan2(Math.Cos(eps) * Math.Sin(lambda), Math.Cos(lambda));
        double dec = Math.Asin(Math.Sin(eps) * Math.Sin(lambda));
        double gmst = (18.697374558 + 24.06570982441908 * n) % 24;
        double H = (gmst * 15 + Longitude) * rad - ra;
        double phi = Latitude * rad;
        elevation = Math.Asin(Math.Sin(phi) * Math.Sin(dec) + Math.Cos(phi) * Math.Cos(dec) * Math.Cos(H)) / rad;
        azimut = (Math.Atan2(-Math.Sin(H), Math.Tan(dec) * Math.Cos(phi) - Math.Sin(phi) * Math.Cos(H)) / rad + 360) % 360;
    }

    static Vector3 Direction(float elevation, float azimut)
    {
        float e = elevation * Mathf.Deg2Rad, a = azimut * Mathf.Deg2Rad;
        return (Mathf.Cos(e) * (Mathf.Cos(a) * Nord + Mathf.Sin(a) * Est) + Mathf.Sin(e) * Vector3.up).normalized;
    }

    void Appliquer()
    {
        float e = Elevation, g = grisApplique = Neige.Gris;
        // jour : 0 la nuit (soleil à plus de 6° sous l'horizon), 1 en plein jour.
        float jour = Mathf.SmoothStep(0, 1, Mathf.InverseLerp(-6, 10, e));
        float bas = Mathf.InverseLerp(25, 0, e); // 1 au lever et au coucher
        bool nouvelleNuit = e < 1.5f;

        if (soleil != null)
        {
            if (e > -3)
            {
                // Soleil : jamais sous 3° pour l'éclairage (sinon tout serait éclairé par en dessous).
                soleil.transform.rotation = Quaternion.LookRotation(-Direction(Mathf.Max(3, e), Azimut));
                soleil.intensity = 1.85f * Mathf.SmoothStep(0, 1, Mathf.InverseLerp(-3, 12, e)) * Mathf.Lerp(1, .35f, g);
                soleil.color = Color.Lerp(Color.Lerp(new Color(1f, .955f, .88f), new Color(1f, .62f, .36f), bas * bas), new Color(.9f, .93f, 1f), g);
                soleil.shadowStrength = Mathf.Lerp(.85f, .45f, g);
            }
            else
            {
                // Lune : à l'opposé du soleil, haute, froide et faible.
                soleil.transform.rotation = Quaternion.LookRotation(-Direction(38, (Azimut + 180) % 360));
                soleil.intensity = .15f * Mathf.InverseLerp(-3, -9, e);
                soleil.color = new Color(.62f, .72f, 1f);
            }
            soleil.shadows = Reglages.Ombres == 0 || nouvelleNuit ? LightShadows.None : LightShadows.Soft;
        }

        // Jour : ciel bleu, horizon chaud, rebond du sable clair ; sous la neige, gris lumineux et sol blanc.
        Color ciel0 = Color.Lerp(new(.58f, .68f, .86f), new(.74f, .77f, .82f), g), equateur0 = Color.Lerp(new(.6f, .58f, .52f), new(.72f, .74f, .78f), g),
            sol0 = Color.Lerp(new(.36f, .31f, .24f), new(.78f, .8f, .84f), g);
        Color cielN = new(.12f, .15f, .26f), equateurN = new(.1f, .1f, .14f), solN = new(.05f, .05f, .06f);
        Color crepuscule = new(.75f, .45f, .32f);
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = Color.Lerp(cielN, ciel0, jour);
        RenderSettings.ambientEquatorColor = Color.Lerp(Color.Lerp(equateurN, equateur0, jour), crepuscule, bas * jour * .35f);
        RenderSettings.ambientGroundColor = Color.Lerp(solN, sol0, jour);

        // Brume lointaine (perspective aérienne), épaissie par la neige.
        RenderSettings.fogColor = Color.Lerp(new Color(.05f, .06f, .1f), Color.Lerp(Color.Lerp(new Color(.74f, .8f, .88f), crepuscule, bas * .45f), new Color(.8f, .82f, .86f), g), jour);
        RenderSettings.fogDensity = Mathf.Lerp(.0016f, .009f, g);
        if (ciel != null)
        {
            if (ciel.HasProperty("_Exposure")) ciel.SetFloat("_Exposure", Mathf.Lerp(.05f, 1.3f, jour) * Mathf.Lerp(1, .85f, g));
            if (ciel.HasProperty("_SkyTint")) ciel.SetColor("_SkyTint", Color.Lerp(new Color(.18f, .24f, .5f), Color.Lerp(new Color(.5f, .5f, .5f), new Color(.62f, .62f, .64f), g), jour));
            // La nuit, pas de disque solaire (il prendrait la place de la lune) : la lune est un halo (Etoiles).
            bool disque = e > -3;
            ciel.DisableKeyword(disque ? "_SUNDISK_NONE" : "_SUNDISK_HIGH_QUALITY");
            ciel.EnableKeyword(disque ? "_SUNDISK_HIGH_QUALITY" : "_SUNDISK_NONE");
            if (ciel.HasProperty("_SunDisk")) ciel.SetFloat("_SunDisk", disque ? 2 : 0);
            if (ciel.HasProperty("_GroundColor")) ciel.SetColor("_GroundColor", Color.Lerp(new Color(.03f, .03f, .04f), new Color(.37f, .35f, .33f), jour));
        }
        Etoiles(1 - jour);

        if (premier || nouvelleNuit != nuit)
        {
            premier = false; nuit = nouvelleNuit;
            DecorNuit.Allumer(nuit);
        }
    }

    // Ciel étoilé : petits points sur une sphère lointaine qui suit la caméra, visibles quand la nuit est faite.
    void Etoiles(float force)
    {
        if (force < .15f) { if (etoiles != null) etoiles.SetActive(false); return; }
        if (etoiles == null)
        {
            var mat = Resources.Load<Material>("Nuit/Lumineux");
            if (mat == null) return;
            materiauEtoiles = new Material(mat);
            etoiles = new GameObject("Etoiles");
            etoiles.AddComponent<MeshFilter>().sharedMesh = MaillageEtoiles();
            var r = etoiles.AddComponent<MeshRenderer>(); r.sharedMaterial = materiauEtoiles;
            r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
        }
        etoiles.SetActive(true);
        materiauEtoiles.SetFloat("_Intensite", Mathf.InverseLerp(.15f, 1, force));
        if (lune == null)
        {
            var h = Resources.Load<Material>("Nuit/Halo");
            if (h != null)
            {
                materiauLune = new Material(h);
                lune = new GameObject("Lune"); lune.transform.SetParent(etoiles.transform, false);
                var m = new Mesh { name = "Lune" };
                m.vertices = new Vector3[4]; m.colors = new[] { Color.white, Color.white, Color.white, Color.white };
                m.uv = new[] { new Vector2(-1, -1), new Vector2(1, -1), new Vector2(1, 1), new Vector2(-1, 1) };
                m.uv2 = new[] { new Vector2(70, 0), new Vector2(70, 0), new Vector2(70, 0), new Vector2(70, 0) };
                m.triangles = new[] { 0, 1, 2, 0, 2, 3 }; m.bounds = new Bounds(Vector3.zero, Vector3.one * 200);
                lune.AddComponent<MeshFilter>().sharedMesh = m;
                var r = lune.AddComponent<MeshRenderer>(); r.sharedMaterial = materiauLune; r.shadowCastingMode = ShadowCastingMode.Off;
            }
        }
        if (lune != null)
        {
            lune.transform.localPosition = Direction(38, (Azimut + 180) % 360) * 1000;
            materiauLune.SetFloat("_Intensite", Mathf.InverseLerp(.15f, 1, force) * .9f);
        }
    }

    static Mesh MaillageEtoiles()
    {
        var aleatoire = new System.Random(1914);
        const int n = 900; const float rayon = 1100;
        var v = new Vector3[n * 4]; var c = new Color[n * 4]; var t = new int[n * 6];
        for (int i = 0; i < n; i++)
        {
            Vector3 d;
            do d = new Vector3((float)aleatoire.NextDouble() * 2 - 1, (float)aleatoire.NextDouble(), (float)aleatoire.NextDouble() * 2 - 1); while (d.sqrMagnitude > 1 || d.sqrMagnitude < .01f || d.y < .06f);
            d.Normalize();
            Vector3 p = d * rayon, a = Vector3.Cross(d, Vector3.up).normalized, b = Vector3.Cross(d, a);
            float taille = (float)(.5 + aleatoire.NextDouble() * aleatoire.NextDouble() * 1.7);
            float k = (float)(.45 + aleatoire.NextDouble() * .55);
            Color couleur = new(k, k, Mathf.Min(1, k * 1.08f));
            for (int j = 0; j < 4; j++)
            {
                float sx = j == 0 || j == 3 ? -1 : 1, sy = j < 2 ? -1 : 1;
                v[4 * i + j] = p + (a * sx + b * sy) * taille; c[4 * i + j] = couleur;
            }
            t[6 * i] = 4 * i; t[6 * i + 1] = 4 * i + 1; t[6 * i + 2] = 4 * i + 2; t[6 * i + 3] = 4 * i; t[6 * i + 4] = 4 * i + 2; t[6 * i + 5] = 4 * i + 3;
        }
        var m = new Mesh { name = "Etoiles" }; m.vertices = v; m.colors = c; m.triangles = t;
        m.bounds = new Bounds(Vector3.zero, Vector3.one * rayon * 2.2f);
        return m;
    }

    void LateUpdate()
    {
        if (etoiles != null && etoiles.activeSelf && Camera.main != null) etoiles.transform.position = Camera.main.transform.position;
    }

    void OnDestroy() { if (Instance == this) Instance = null; }
}

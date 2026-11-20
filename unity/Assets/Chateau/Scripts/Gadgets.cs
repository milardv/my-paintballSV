using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;

// Objets fun du domaine (E pour prendre), en plus de ceux d'ObjetsDomaine :
//  - canon à peinture (terrasse) : 6 boulets, touche C, explosion de peinture comme la boule dorée ;
//  - jetpack (cour nord) : maintenir Espace en l'air, 5 s de poussée qui se rechargent au sol ;
//  - espadrilles (parc) : course ×1,6 pendant 30 s ; chaussures à ressorts (cour sud) : sauts ×3 pendant 30 s ;
//  - cigale porte-bonheur (terrasse ouest) : encaisse une bille ; rosé (terrasse) : vision rose 8 s ;
//  - lunettes de soleil (bord du bassin), chapeau de paille (cour sud) : portés, visibles en vue extérieure ;
//  - feu d'artifice (toit) : bouquet tiré au-dessus du château ;
//  - trois santons cachés dans le château (salon, billard, chambre 1) : la crèche complète tire un feu d'artifice.
public class Gadgets : MonoBehaviour
{
    public static Gadgets Instance { get; private set; }
    public static int Canon { get; private set; }
    public static bool Jetpack { get; private set; }
    public static int Santons { get; private set; }
    const float DureeJetpack = 5f, DureeBonus = 30f;
    float carburant = DureeJetpack, vitesseJusqua, sautJusqua;
    ObjetsDomaine objets;
    PaintballSolo partie;
    Explorateur explorateur;
    CharacterController controleur;
    Transform sacJetpack, flamme;
    static readonly Color Paille = new(.86f, .74f, .42f);

    public static void Installer(ObjetsDomaine objets)
    {
        if (Instance != null) return;
        Instance = new GameObject("Gadgets").AddComponent<Gadgets>();
        Instance.objets = objets;
        Instance.partie = objets.Partie;
        Instance.explorateur = objets.Partie.GetComponent<Explorateur>();
        Instance.controleur = objets.Partie.GetComponent<CharacterController>();
        Instance.Poser();
        ObjetsDomaine.InventaireSup = Instance.Inventaire;
        ObjetsDomaine.ViderSup = Instance.Vider;
    }

    // Repère D-003 (x est, y sud) → monde Unity ; au sol, ou à l'étage si z est donné.
    static Vector3 P(float x, float y, float z = float.NaN)
    {
        var p = new Vector3(-x, float.IsNaN(z) ? 0 : z, y);
        if (float.IsNaN(z)) { p.y = Vehicule.Sol(p); return p; }
        return Physics.Raycast(p + Vector3.up * 1.2f, Vector3.down, out var h, 2.5f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) ? h.point : p;
    }

    void Poser()
    {
        objets.PoserObjet("canon", "Canon à peinture", "Prendre le canon à peinture", P(10f, 11.5f), Modele(ModeleCanon), () =>
        { Canon = 6; ObjetsDomaine.Annoncer("Canon à peinture : 6 boulets, touche C pour tirer"); });
        objets.PoserObjet("jetpack", "Jetpack", "Enfiler le jetpack", P(-6f, -16f), Modele(ModeleJetpack), PrendreJetpack, false);
        objets.PoserObjet("espadrilles", "Espadrilles", "Chausser les espadrilles", P(4f, 30f), Modele(ModeleEspadrilles), () =>
        { vitesseJusqua = Time.time + DureeBonus; ObjetsDomaine.Annoncer("Espadrilles : vous courez plus vite pendant 30 s"); });
        objets.PoserObjet("ressorts", "Chaussures à ressorts", "Chausser les ressorts", P(-12f, 24f), Modele(ModeleRessorts), () =>
        { sautJusqua = Time.time + DureeBonus; ObjetsDomaine.Annoncer("Chaussures à ressorts : sauts géants pendant 30 s"); });
        objets.PoserObjet("cigale", "Cigale porte-bonheur", "Prendre la cigale porte-bonheur", P(-14f, 10f), Modele(ModeleCigale), () =>
        { ObjetsDomaine.Gilet = Mathf.Min(ObjetsDomaine.Gilet + 1, 5); ObjetsDomaine.Annoncer("Cigale porte-bonheur : la prochaine bille est encaissée"); });
        objets.PoserObjet("rose", "Rosé de Provence", "Boire un verre de rosé", P(-4f, 11.5f), Modele(ModeleRose), () =>
        { objets.Griser(8f, new Color(1f, .45f, .62f)); ObjetsDomaine.Annoncer("Un verre de rosé… la vie en rose !"); });
        var eau = GameObject.Find("parc_bassin_eau")?.GetComponentInChildren<Renderer>();
        Vector3 bordBassin = eau != null ? new Vector3(eau.bounds.center.x, 0, eau.bounds.max.z + 1.2f) : P(6f, 48f);
        if (eau != null) bordBassin.y = Vehicule.Sol(bordBassin);
        objets.PoserObjet("lunettes", "Lunettes de soleil", "Mettre les lunettes de soleil", bordBassin, Modele(ModeleLunettes), PrendreLunettes, false);
        objets.PoserObjet("chapeau", "Chapeau de paille", "Mettre le chapeau de paille", P(12f, 25f), Modele(ModeleChapeau), PrendreChapeau, false);
        Vector3 toit = EscalierToit.SortieToit != Vector3.zero ? EscalierToit.SortieToit + new Vector3(1.5f, 0, -1.5f) : P(0, 0, 15f);
        if (EscalierToit.SortieToit != Vector3.zero && Physics.Raycast(toit + Vector3.up * 3, Vector3.down, out var h, 6, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) toit = h.point;
        objets.PoserObjet("feu", "Feu d'artifice", "Allumer le feu d'artifice", toit, Modele(ModeleFusee), () => StartCoroutine(FeuDArtifice(toit, 6)));
        var santons = new[] { ("santon_salon", P(0f, 5.2f, 0f)), ("santon_billard", P(5f, 1.3f, 0f)), ("santon_chambre", P(12f, 3.5f, 5.35f)) };
        foreach (var (cle, pos) in santons)
            objets.PoserObjet(cle, "Santon", "Ramasser le santon", pos, Modele(ModeleSanton), PrendreSanton, false);
    }

    static System.Func<Transform, float> Modele(System.Func<Transform, float> f) => f;
    static Material M(Color c, float lisse = .4f, float metal = 0, Color? emission = null) => ObjetsDomaine.Mat(c, lisse, metal, emission);
    static Transform Prim(Transform t, PrimitiveType p, Vector3 pos, Vector3 e, Material m, Vector3 rot = default) => ObjetsDomaine.Prim(t, p, pos, e, m, rot);

    // ---------- Modèles ----------
    static float ModeleCanon(Transform t)
    {
        var fonte = M(new Color(.12f, .12f, .13f), .6f, .8f); var bois = M(new Color(.42f, .25f, .12f), .3f);
        Prim(t, PrimitiveType.Cylinder, new(0, .42f, 0), new(.22f, .45f, .22f), fonte, new(70, 0, 0));
        Prim(t, PrimitiveType.Cylinder, new(0, .55f, .42f), new(.26f, .04f, .26f), M(new Color(.9f, .2f, .5f), .5f, 0, new Color(.4f, .05f, .2f)), new(70, 0, 0));
        foreach (float x in new[] { -.2f, .2f }) Prim(t, PrimitiveType.Cylinder, new(x, .22f, -.05f), new(.4f, .03f, .4f), bois, new(0, 0, 90));
        Prim(t, PrimitiveType.Cube, new(0, .22f, -.05f), new(.36f, .12f, .55f), bois);
        return .7f;
    }
    static float ModeleJetpack(Transform t)
    {
        var acier = M(new Color(.75f, .76f, .8f), .8f, .9f); var rouge = M(new Color(.8f, .1f, .08f), .5f);
        foreach (float x in new[] { -.12f, .12f })
        {
            Prim(t, PrimitiveType.Cylinder, new(x, .45f, 0), new(.17f, .28f, .17f), acier);
            Prim(t, PrimitiveType.Sphere, new(x, .74f, 0), new(.17f, .12f, .17f), rouge);
            Prim(t, PrimitiveType.Cylinder, new(x, .12f, 0), new(.1f, .06f, .1f), M(new Color(.2f, .2f, .2f), .5f, .8f));
        }
        Prim(t, PrimitiveType.Cube, new(0, .5f, -.1f), new(.4f, .35f, .05f), M(new Color(.15f, .15f, .17f), .3f));
        return .85f;
    }
    static float ModeleEspadrilles(Transform t)
    {
        var toile = M(new Color(.1f, .25f, .6f), .2f); var corde = M(Paille, .2f);
        foreach (float x in new[] { -.07f, .07f })
        {
            Prim(t, PrimitiveType.Cube, new(x, .02f, 0), new(.09f, .03f, .26f), corde);
            Prim(t, PrimitiveType.Sphere, new(x, .06f, .03f), new(.09f, .07f, .2f), toile);
        }
        return .25f;
    }
    static float ModeleRessorts(Transform t)
    {
        var acier = M(new Color(.7f, .7f, .72f), .8f, 1f); var semelle = M(new Color(.9f, .35f, .1f), .4f);
        foreach (float x in new[] { -.08f, .08f })
        {
            for (int k = 0; k < 5; k++) Prim(t, PrimitiveType.Cylinder, new(x, .03f + k * .035f, 0), new(.08f, .006f, .08f), acier);
            Prim(t, PrimitiveType.Cube, new(x, .22f, 0), new(.1f, .05f, .26f), semelle);
        }
        return .3f;
    }
    static float ModeleCigale(Transform t)
    {
        var faience = M(new Color(.95f, .78f, .15f), .8f, .1f, new Color(.2f, .14f, 0)); var aile = M(new Color(.2f, .5f, .35f), .8f);
        Prim(t, PrimitiveType.Sphere, new(0, .12f, 0), new(.12f, .09f, .22f), faience);
        Prim(t, PrimitiveType.Sphere, new(-.06f, .15f, -.02f), new(.06f, .02f, .2f), aile, new(0, 15, 0));
        Prim(t, PrimitiveType.Sphere, new(.06f, .15f, -.02f), new(.06f, .02f, .2f), aile, new(0, -15, 0));
        return .3f;
    }
    static float ModeleRose(Transform t)
    {
        var verre = M(new Color(1f, .55f, .62f), .95f); var pied = M(new Color(.9f, .9f, .92f), .95f);
        Prim(t, PrimitiveType.Cylinder, new(0, .01f, 0), new(.08f, .005f, .08f), pied);
        Prim(t, PrimitiveType.Cylinder, new(0, .07f, 0), new(.012f, .06f, .012f), pied);
        Prim(t, PrimitiveType.Sphere, new(0, .17f, 0), new(.09f, .1f, .09f), verre);
        Prim(t, PrimitiveType.Cylinder, new(.14f, .14f, 0), new(.07f, .13f, .07f), M(new Color(.95f, .6f, .65f), .9f));
        return .35f;
    }
    static float ModeleLunettes(Transform t) { Lunettes(t, 1.6f); return .25f; }
    static void Lunettes(Transform t, float e)
    {
        var noir = M(new Color(.03f, .03f, .03f), .95f, .3f);
        foreach (float x in new[] { -.035f, .035f }) Prim(t, PrimitiveType.Cylinder, new Vector3(x, .04f, 0) * e, new Vector3(.055f, .004f, .045f) * e, noir, new(90, 0, 0));
        Prim(t, PrimitiveType.Cube, new Vector3(0, .045f, 0) * e, new Vector3(.03f, .006f, .006f) * e, noir);
    }
    static float ModeleChapeau(Transform t) { Chapeau(t, 1f); return .3f; }
    static void Chapeau(Transform t, float e)
    {
        var paille = M(Paille, .25f); var ruban = M(new Color(.6f, .1f, .12f), .4f);
        Prim(t, PrimitiveType.Cylinder, new Vector3(0, .02f, 0) * e, new Vector3(.42f, .006f, .42f) * e, paille);
        Prim(t, PrimitiveType.Cylinder, new Vector3(0, .08f, 0) * e, new Vector3(.2f, .06f, .2f) * e, paille);
        Prim(t, PrimitiveType.Cylinder, new Vector3(0, .05f, 0) * e, new Vector3(.205f, .02f, .205f) * e, ruban);
    }
    static float ModeleFusee(Transform t)
    {
        Prim(t, PrimitiveType.Cylinder, new(0, .35f, 0), new(.08f, .3f, .08f), M(new Color(.85f, .1f, .2f), .4f));
        Prim(t, PrimitiveType.Capsule, new(0, .72f, 0), new(.08f, .08f, .08f), M(new Color(.95f, .85f, .2f), .5f, 0, new Color(.4f, .3f, 0)));
        Prim(t, PrimitiveType.Cylinder, new(0, .02f, 0), new(.25f, .02f, .25f), M(new Color(.3f, .3f, .3f), .3f));
        return .85f;
    }
    static float ModeleSanton(Transform t)
    {
        var argile = M(new Color(.75f, .45f, .3f), .3f); var habit = M(new Color(.2f, .3f, .6f), .3f); var fichu = M(new Color(.85f, .2f, .15f), .3f);
        Prim(t, PrimitiveType.Cylinder, new(0, .05f, 0), new(.08f, .05f, .08f), habit);
        Prim(t, PrimitiveType.Capsule, new(0, .14f, 0), new(.06f, .06f, .05f), fichu);
        Prim(t, PrimitiveType.Sphere, new(0, .22f, 0), new(.045f, .045f, .045f), argile);
        return .3f;
    }

    // ---------- Effets ----------
    void PrendreJetpack()
    {
        Jetpack = true; carburant = DureeJetpack;
        if (sacJetpack != null) sacJetpack.gameObject.SetActive(true);
        ObjetsDomaine.Annoncer("Jetpack ! Sauter puis maintenir Espace pour voler");
        if (sacJetpack == null && partie.personnage != null)
            sacJetpack = ObjetsDomaine.Habiller(partie.personnage.transform, new[] { "Torso", "Abdomen", "Body" }, t =>
            {
                var acier = M(new Color(.75f, .76f, .8f), .8f, .9f);
                foreach (float x in new[] { -.09f, .09f }) Prim(t, PrimitiveType.Cylinder, new(x, 0, -.2f), new(.13f, .2f, .13f), acier);
                flamme = Prim(t, PrimitiveType.Sphere, new(0, -.3f, -.2f), new(.12f, .25f, .12f), M(new Color(1f, .55f, .1f), .2f, 0, new Color(4f, 1.6f, .2f)));
            }, 0f);
    }
    Transform lunettesPortees, chapeauPorte;
    void PrendreLunettes()
    {
        ObjetsDomaine.Annoncer("Lunettes de soleil : la classe ! (V pour se voir)");
        if (lunettesPortees == null && partie.personnage != null) lunettesPortees = ObjetsDomaine.Habiller(partie.personnage.transform, new[] { "Head" }, t => Lunettes(t, 2.2f), .12f);
        if (lunettesPortees != null) lunettesPortees.gameObject.SetActive(true);
    }
    void PrendreChapeau()
    {
        ObjetsDomaine.Annoncer("Chapeau de paille, à la provençale ! (V pour se voir)");
        if (chapeauPorte == null && partie.personnage != null) chapeauPorte = ObjetsDomaine.Habiller(partie.personnage.transform, new[] { "Head" }, t => Chapeau(t, 1.3f), .3f);
        if (chapeauPorte != null) chapeauPorte.gameObject.SetActive(true);
    }

    // Objets perdus (touché, nouvelle partie).
    void Vider()
    {
        Canon = 0; Jetpack = false; Santons = 0; vitesseJusqua = sautJusqua = 0; carburant = DureeJetpack;
        foreach (var t in new[] { sacJetpack, lunettesPortees, chapeauPorte }) if (t != null) t.gameObject.SetActive(false);
    }
    void PrendreSanton()
    {
        Santons++;
        if (Santons >= 3)
        {
            ObjetsDomaine.Annoncer("La crèche est complète ! Feu d'artifice !");
            StartCoroutine(FeuDArtifice(partie.transform.position + Vector3.up * 2, 4));
        }
        else ObjetsDomaine.Annoncer($"Santon {Santons}/3 — les autres sont cachés dans le château");
    }

    IEnumerable<string> Inventaire()
    {
        if (Canon > 0) yield return $"C · canon ×{Canon}";
        if (Jetpack) yield return "Jetpack " + new string('▮', Mathf.CeilToInt(carburant)) + new string('▯', Mathf.RoundToInt(DureeJetpack) - Mathf.CeilToInt(carburant));
        if (Time.time < vitesseJusqua) yield return $"Espadrilles {Mathf.CeilToInt(vitesseJusqua - Time.time)} s";
        if (Time.time < sautJusqua) yield return $"Ressorts {Mathf.CeilToInt(sautJusqua - Time.time)} s";
        if (Santons > 0 && Santons < 3) yield return $"Santons {Santons}/3";
    }

    void Update()
    {
        if (partie == null) return;
        Explorateur.BonusVitesse = Time.time < vitesseJusqua ? 1.6f : 1f;
        Explorateur.BonusSaut = Time.time < sautJusqua ? 3f : 1f;
        bool libre = !(partie.Active && partie.EnPause) && explorateur.Monture == null;
        if (Canon > 0 && libre && Keyboard.current != null && Keyboard.current.cKey.wasPressedThisFrame) { Canon--; objets.TirerBoulet(30f); }
        // Jetpack : poussée en l'air tant que le saut est maintenu et qu'il reste du carburant.
        bool pousse = Jetpack && libre && carburant > 0 && explorateur.SautMaintenu && !controleur.isGrounded;
        Explorateur.PousseeJetpack = pousse ? 21f : 0f;
        if (pousse) carburant = Mathf.Max(0, carburant - Time.deltaTime);
        else if (controleur.isGrounded) carburant = Mathf.Min(DureeJetpack, carburant + Time.deltaTime * .8f);
        if (flamme != null) { flamme.gameObject.SetActive(pousse); flamme.localScale = new Vector3(.12f, .25f + .08f * Mathf.Sin(Time.time * 40), .12f); }
    }

    // Feu d'artifice : fusées qui montent puis éclatent en gerbes d'étincelles colorées qui retombent.
    IEnumerator FeuDArtifice(Vector3 depart, int fusees)
    {
        var couleurs = new[] { new Color(1f, .3f, .4f), new Color(.3f, .8f, 1f), new Color(1f, .85f, .2f), new Color(.5f, 1f, .4f), new Color(.9f, .4f, 1f) };
        for (int f = 0; f < fusees; f++)
        {
            StartCoroutine(Fusee(depart + new Vector3(Random.Range(-2f, 2f), 0, Random.Range(-2f, 2f)), couleurs[f % couleurs.Length]));
            yield return new WaitForSeconds(Random.Range(.4f, .9f));
        }
    }

    IEnumerator Fusee(Vector3 depart, Color c)
    {
        var m = M(c, .2f, 0, c * 6f);
        var fusee = Prim(null, PrimitiveType.Sphere, Vector3.zero, Vector3.one * .15f, m); fusee.gameObject.layer = 2;
        float hauteur = Random.Range(18f, 26f);
        for (float t = 0; t < 1.3f; t += Time.deltaTime) { fusee.position = depart + Vector3.up * hauteur * Mathf.Sin(t / 1.3f * Mathf.PI / 2); yield return null; }
        Vector3 centre = fusee.position; Destroy(fusee.gameObject);
        var lumiere = new GameObject("Eclat").AddComponent<Light>(); lumiere.transform.position = centre; lumiere.color = c; lumiere.range = 40; lumiere.intensity = 6;
        var eclats = new List<(Transform t, Vector3 v)>();
        for (int i = 0; i < 70; i++)
        {
            var e = Prim(null, PrimitiveType.Sphere, Vector3.zero, Vector3.one * .18f, m); e.gameObject.layer = 2; e.position = centre;
            e.GetComponent<Renderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            eclats.Add((e, Random.onUnitSphere * Random.Range(7f, 10f)));
        }
        for (float t = 0; t < 2.2f; t += Time.deltaTime)
        {
            for (int i = 0; i < eclats.Count; i++)
            {
                var (e, v) = eclats[i]; v += Physics.gravity * .25f * Time.deltaTime; v *= 1 - 1.2f * Time.deltaTime;
                e.position += v * Time.deltaTime; e.localScale = Vector3.one * .18f * (1 - t / 2.2f); eclats[i] = (e, v);
            }
            lumiere.intensity = 6 * (1 - t / 2.2f);
            yield return null;
        }
        foreach (var (e, _) in eclats) Destroy(e.gameObject);
        Destroy(lumiere.gameObject);
    }

    void OnDestroy() { if (Instance == this) { Instance = null; Explorateur.BonusVitesse = Explorateur.BonusSaut = 1; Explorateur.PousseeJetpack = 0; } }
}

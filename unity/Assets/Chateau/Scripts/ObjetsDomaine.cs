using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

// Objets à ramasser dans le domaine (E pour prendre) :
//  - boule de pétanque dorée (terrain de pétanque) : maintenir G montre la trajectoire, relâcher lance ;
//    explosion de peinture de 4,5 m (gouttes projetées qui tachent là où elles retombent) ;
//  - clés du tracteur tondeuse (établi de la grange) : le tracteur devient pilotable ;
//  - pastis du gardien (devant sa maison) : vision floue et tangage pendant 10 s ;
//  - képi (au pied des mâts de la piscine, rare) : porté par le joueur, visible en vue extérieure (V) ;
//  - gilet pare-balles (sur un tabouret à côté de la maison du gardien) : encaisse 3 billes contre les bots.
// Les objets consommés réapparaissent 45 s plus tard ; clés et képi restent acquis.
[DefaultExecutionOrder(1000)]
public class ObjetsDomaine : MonoBehaviour
{
    public static ObjetsDomaine Instance { get; private set; }
    public static bool ClesTracteur { get; private set; }
    public static bool KepiPorte { get; private set; }
    public static int Boules { get; private set; }
    public static int Gilet { get; set; }
    public static System.Func<IEnumerable<string>> InventaireSup;
    public PaintballSolo Partie => partie;
    public Transform Tete => tete;
    // Pastis, rosé : vision floue et teinte du voile.
    public void Griser(float duree, Color teinte) { flouJusqua = Time.time + duree; teinteFlou = teinte; }
    Color teinteFlou = new(1f, .82f, .25f);
    // Canon à peinture (Gadgets) : même boulet que la boule dorée, tiré tendu.
    public void TirerBoulet(float vitesse)
    {
        var b = Prim(null, PrimitiveType.Sphere, Vector3.zero, Vector3.one * .16f, Mat(partie.Couleur, .6f, 0, partie.Couleur * .5f));
        b.name = "BouletCanon"; b.gameObject.layer = 2;
        b.position = DepartLancer;
        lancers.Add(new Lancer { t = b, v = tete.forward * vitesse + Vector3.up * 1.2f });
        secousse = 1f;
    }
    public static float Flou => Instance == null ? 0 : Mathf.Clamp01((Instance.flouJusqua - Time.time) / 1.5f);

    const float Reapparition = 45f, RayonEclaboussure = 4.5f, VitesseLancer = 15f;
    static readonly Color Or = new(1f, .78f, .2f);
    PaintballSolo partie;
    Explorateur explorateur;
    InterfaceVisite interfaceVisite;
    Transform tete;
    InputAction lancer;
    float flouJusqua;
    Quaternion? derniere; Quaternion avantFlou;
    TMP_Text annonce, inventaire;
    Image voileFlou;
    float annonceJusqua;
    Transform kepiJoueur, giletJoueur;
    readonly List<Lancer> lancers = new();
    class Lancer { public Transform t; public Vector3 v; public float age; }
    readonly List<Goutte> gouttes = new();
    class Goutte { public Transform t; public Vector3 v; public float age; public Color c; }
    readonly List<(Transform t, float age)> souffles = new();
    // Visée : points de trajectoire et cercle de l'explosion au point d'arrivée.
    bool vise;
    Transform visee;
    readonly List<Transform> points = new(), cercle = new();
    float secousse;

    // Registre des objets (carte du toit) : disponible ou pris, par qui et quand.
    public class Suivi { public string cle, nom; public GameObject objet; public Vector3 position; public bool pris, reapparait, garde; public string par = ""; public float quand; public System.Action prendre; }
    // Objets gardés par chaque joueur (le joueur local : JoueurLocal) : perdus à la touche au profit du tireur,
    // et remis en place à chaque nouvelle partie. Pastis, rosé et feu d'artifice se consomment sur place.
    public const int JoueurLocal = int.MinValue;
    public static readonly Dictionary<int, List<string>> Detenus = new();
    static readonly HashSet<string> Consommes = new() { "pastis", "rose", "feu" };
    static List<string> Sac(int j) { if (!Detenus.TryGetValue(j, out var l)) Detenus[j] = l = new List<string>(); return l; }
    public static System.Action ViderSup;
    public static readonly List<Suivi> Registre = new();
    public static Suivi Trouver(string cle) => Registre.Find(r => r.cle == cle);
    static readonly Dictionary<string, string> NomsCourts = new()
        { { "boule", "Boule dorée" }, { "cles", "Clés du tracteur" }, { "pastis", "Pastis du gardien" }, { "gilet", "Gilet pare-balles" },
          { "kepi", "Képi" }, { "lunette", "Lunette de visée" } };

    public static void Noter(string cle, string par)
    {
        var r = Trouver(cle); if (r == null) return;
        r.pris = true; r.par = par; r.quand = Time.time;
    }

    public static void Installer(PaintballSolo partie)
    {
        if (Instance != null) return;
        var go = new GameObject("ObjetsDomaine");
        Instance = go.AddComponent<ObjetsDomaine>();
        Instance.Initialiser(partie);
    }

    public static void Annoncer(string texte)
    {
        if (Instance == null || Instance.annonce == null) return;
        Instance.annonce.text = texte; Instance.annonceJusqua = Time.time + 3.5f;
    }

    // Une bille reçue contre les bots : le gilet l'encaisse tant qu'il lui reste des plaques.
    public static bool Encaisser()
    {
        if (Gilet <= 0) return false;
        Gilet--;
        Annoncer(Gilet > 0 ? $"Le gilet a encaissé la bille ! (encore {Gilet})" : "Le gilet est hors d'usage.");
        if (Gilet == 0 && Instance != null && Instance.giletJoueur != null) Instance.giletJoueur.gameObject.SetActive(false);
        return true;
    }

    void Initialiser(PaintballSolo p)
    {
        partie = p; explorateur = p.GetComponent<Explorateur>(); interfaceVisite = FindAnyObjectByType<InterfaceVisite>();
        tete = p.GetComponentInChildren<Camera>().transform;
        lancer = new InputAction("LancerBoule", InputActionType.Button, "<Keyboard>/g"); lancer.AddBinding("<Gamepad>/rightShoulder"); lancer.Enable();
        ConstruireInterface();
        Tracteur.Installer();
        VeloCargo.Installer();
        // Emplacements relevés sur travail/plan_domaine.json (repère D-003 : centre, angle, décalage local).
        Poser("boule", "Ramasser la boule de pétanque dorée", Local(90.5f, 104.5f, 6, .6f, -4f), ModeleBoule, PrendreBoule);
        Poser("cles", "Prendre les clés du tracteur", Local(83.4f, 88f, 8, 2.25f, -3.55f), ModeleCles, PrendreCles, false);
        Poser("pastis", "Boire le pastis du gardien", Local(104f, 103.5f, 6, 1.6f, 8.7f), ModelePastis, PrendrePastis);
        Poser("gilet", "Enfiler le gilet pare-balles", Local(104f, 103.5f, 6, -6.1f, 5f), ModeleGilet, PrendreGilet);
        Poser("kepi", "Coiffer le képi", Local(22.5f, 68.8f, 0, .9f, .6f), ModeleKepi, PrendreKepi, false);
        // Toit : lunette de visée sur une caisse et carte des objets, de part et d'autre de la trappe.
        if (EscalierToit.SortieToit != Vector3.zero)
        {
            Vector3 t = EscalierToit.SortieToit;
            Poser("lunette", "Fixer la lunette de visée sur le marqueur", SurToit(t + new Vector3(-1.3f, 0, .2f)), LunettePaintball.Modele,
                  () => LunettePaintball.Equiper(partie), false);
            CarteDomaine.Installer(SurToit(t + new Vector3(1.6f, 0, .4f)), t + new Vector3(-.2f, 0, -1.2f));
        }
        Gadgets.Installer(this);
    }

    static Vector3 SurToit(Vector3 p) =>
        Physics.Raycast(p + Vector3.up * 3, Vector3.down, out var h, 6, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) ? h.point : p;

    // Point d'un bâtiment du plan (centre, angle en degrés, décalage local) en coordonnées Unity, au sol.
    public static Vector3 Local(float cx, float cy, float angle, float lx, float ly)
    {
        float a = angle * Mathf.Deg2Rad, x = cx + lx * Mathf.Cos(a) - ly * Mathf.Sin(a), y = cy + lx * Mathf.Sin(a) + ly * Mathf.Cos(a);
        var p = new Vector3(-x, 0, y);
        p.y = Vehicule.Sol(p);
        return p;
    }

    // ---------- Objets ramassables ----------
    public class Ramassable : MonoBehaviour, IInteractif
    {
        public string cle, libelle; public System.Action prendre; public bool reapparait = true; public bool tourne = true;
        Vector3 basePos;
        void Start() => basePos = transform.position;
        public string Libelle(Explorateur e) => libelle;
        public void Interagir(Explorateur e)
        {
            prendre?.Invoke();
            Noter(cle, "Vous");
            if (!Consommes.Contains(cle)) Sac(JoueurLocal).Add(cle);
            gameObject.SetActive(false);
            if (reapparait && Instance != null) Instance.StartCoroutine(Instance.Revenir(gameObject));
        }
        void Update()
        {
            if (!tourne) return;
            transform.position = basePos + Vector3.up * (.06f + .05f * Mathf.Sin(Time.time * 2.2f));
            transform.Rotate(Vector3.up, 50 * Time.deltaTime, Space.World);
        }
    }

    System.Collections.IEnumerator Revenir(GameObject o)
    {
        yield return new WaitForSeconds(Reapparition);
        o.SetActive(true);
        var r = Registry(o); if (r != null) r.pris = false;
    }
    static Suivi Registry(GameObject o) => Registre.Find(r => r.objet == o);

    // Les bots qui passent sur un objet qui revient le prennent (pas les clés ni le képi, ni la lunette).
    float prochainBots;
    void VerifierBots()
    {
        if (Time.time < prochainBots || PartieBots.Instance == null) return;
        prochainBots = Time.time + .5f;
        foreach (var r in Registre)
        {
            if (r.pris || r.objet == null || !r.objet.activeSelf || r.cle.StartsWith("santon") || r.cle == "feu") continue;
            foreach (var b in PartieBots.Instance.bots)
            {
                if (b == null || !b.gameObject.activeInHierarchy || b.EtatTexte == "Elimine") continue;
                Vector3 d = b.transform.position - r.position; d.y *= .5f;
                if (d.sqrMagnitude > 1.6f) continue;
                r.objet.SetActive(false); r.pris = true; r.par = b.Nom; r.quand = Time.time;
                Annoncer($"{b.Nom} a pris : {r.nom.ToLowerInvariant()}");
                if (r.garde) Sac(b.Id).Add(r.cle);
                if (r.reapparait) StartCoroutine(Revenir(r.objet));
                break;
            }
        }
    }

    public void PoserObjet(string nom, string nomCourt, string libelle, Vector3 sol, System.Func<Transform, float> modele, System.Action prendre, bool reapparait = true)
    {
        NomsCourts[nom] = nomCourt;
        Poser(nom, libelle, sol, modele, prendre, reapparait);
    }

    void Poser(string nom, string libelle, Vector3 sol, System.Func<Transform, float> modele, System.Action prendre, bool reapparait = true)
    {
        var go = new GameObject("Objet_" + nom);
        go.transform.position = sol;
        float h = modele(go.transform);
        var c = go.AddComponent<BoxCollider>(); c.center = Vector3.up * h * .5f; c.size = new Vector3(.6f, Mathf.Max(.5f, h), .6f);
        Registre.Add(new Suivi { cle = nom, nom = NomsCourts.TryGetValue(nom, out var court) ? court : nom, objet = go, position = sol, reapparait = reapparait, garde = !Consommes.Contains(nom), prendre = prendre });
        var r = go.AddComponent<Ramassable>(); r.cle = nom; r.libelle = libelle; r.prendre = prendre; r.reapparait = reapparait; r.tourne = nom != "pastis" && nom != "gilet";
    }

    // Touche comptée : le joueur touché perd ses objets, que le tireur récupère.
    public static void Transferer(int touche, int tireur, string nomTireur)
    {
        if (Instance == null) return;
        int de = touche == Instance.partie.JoueurId ? JoueurLocal : touche, vers = tireur == Instance.partie.JoueurId ? JoueurLocal : tireur;
        if (de == vers || !Detenus.TryGetValue(de, out var sac) || sac.Count == 0) return;
        var objets = new List<string>(sac); sac.Clear();
        if (de == JoueurLocal) { Instance.ViderJoueur(); Annoncer($"{nomTireur} vous a pris vos objets !"); }
        var noms = new List<string>();
        foreach (var cle in objets)
        {
            var r = Trouver(cle); if (r == null) continue;
            noms.Add(r.nom.ToLowerInvariant());
            if (vers == JoueurLocal) { r.prendre?.Invoke(); Noter(cle, "Vous"); }
            else { r.par = nomTireur; r.quand = Time.time; }
            Sac(vers).Add(cle);
        }
        if (vers == JoueurLocal && noms.Count > 0) Annoncer("Récupéré : " + string.Join(", ", noms));
    }

    // Nouvelle partie : inventaires vidés, tous les objets de nouveau à leur place.
    public static void NouvellePartie()
    {
        if (Instance == null) return;
        Instance.StopAllCoroutines();
        Instance.ViderJoueur();
        Detenus.Clear();
        foreach (var r in Registre) { r.pris = false; r.par = ""; if (r.objet != null) r.objet.SetActive(true); }
    }

    void ViderJoueur()
    {
        Boules = 0; Gilet = 0; ClesTracteur = false; KepiPorte = false; vise = false;
        if (giletJoueur != null) giletJoueur.gameObject.SetActive(false);
        if (kepiJoueur != null) kepiJoueur.gameObject.SetActive(false);
        LunettePaintball.Retirer();
        ViderSup?.Invoke();
    }

    public static Material Mat(Color c, float lisse = .5f, float metal = 0, Color? emission = null)
    {
        var m = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        m.SetColor("_BaseColor", c); m.SetFloat("_Smoothness", lisse); m.SetFloat("_Metallic", metal);
        if (emission.HasValue) { m.EnableKeyword("_EMISSION"); m.SetColor("_EmissionColor", emission.Value); }
        return m;
    }
    public static Transform Prim(Transform parent, PrimitiveType t, Vector3 pos, Vector3 e, Material m, Vector3 rot = default)
    {
        var g = GameObject.CreatePrimitive(t); Destroy(g.GetComponent<Collider>());
        g.transform.SetParent(parent, false); g.transform.localPosition = pos; g.transform.localScale = e; g.transform.localEulerAngles = rot;
        g.GetComponent<Renderer>().sharedMaterial = m; return g.transform;
    }

    float ModeleBoule(Transform t) { Prim(t, PrimitiveType.Sphere, Vector3.up * .12f, Vector3.one * .16f, Mat(Or, .85f, 1f, Or * .35f)); return .3f; }
    float ModeleCles(Transform t)
    {
        var acier = Mat(new Color(.75f, .76f, .78f), .85f, 1f, new Color(.15f, .15f, .12f));
        Prim(t, PrimitiveType.Cylinder, new(0, .05f, 0), new(.06f, .005f, .06f), acier);
        Prim(t, PrimitiveType.Cube, new(0, .05f, .07f), new(.015f, .006f, .09f), acier);
        Prim(t, PrimitiveType.Cube, new(.03f, .05f, .03f), new(.05f, .02f, .03f), Mat(new Color(.9f, .7f, .05f), .5f, 0, new Color(.3f, .2f, 0)));
        return .2f;
    }
    float ModelePastis(Transform t)
    {
        var fer = Mat(new Color(.12f, .14f, .12f), .5f, .6f);
        Prim(t, PrimitiveType.Cylinder, new(0, .36f, 0), new(.03f, .36f, .03f), fer);
        Prim(t, PrimitiveType.Cylinder, new(0, .73f, 0), new(.5f, .01f, .5f), fer);
        Prim(t, PrimitiveType.Cylinder, new(0, .01f, 0), new(.3f, .01f, .3f), fer);
        Prim(t, PrimitiveType.Cylinder, new(-.08f, .86f, 0), new(.08f, .12f, .08f), Mat(new Color(.95f, .75f, .15f, 1), .9f));
        Prim(t, PrimitiveType.Cylinder, new(-.08f, 1.01f, 0), new(.03f, .04f, .03f), Mat(new Color(.95f, .75f, .15f), .9f));
        Prim(t, PrimitiveType.Cylinder, new(-.08f, .86f, 0), new(.083f, .05f, .083f), Mat(new Color(.1f, .25f, .6f), .4f));
        Prim(t, PrimitiveType.Cylinder, new(.1f, .79f, .05f), new(.06f, .05f, .06f), Mat(new Color(.98f, .92f, .6f), .95f));
        Prim(t, PrimitiveType.Cylinder, new(.12f, .77f, -.1f), new(.07f, .035f, .07f), Mat(new Color(.4f, .55f, .25f), .5f));
        return 1.05f;
    }
    float ModeleGilet(Transform t)
    {
        var bois = Mat(new Color(.45f, .3f, .17f), .3f);
        Prim(t, PrimitiveType.Cylinder, new(0, .45f, 0), new(.4f, .02f, .4f), bois);
        foreach (var (x, z) in new[] { (.13f, .13f), (-.13f, .13f), (.13f, -.13f), (-.13f, -.13f) }) Prim(t, PrimitiveType.Cylinder, new(x, .22f, z), new(.04f, .22f, .04f), bois);
        var tissu = Mat(new Color(.18f, .2f, .14f), .2f);
        Prim(t, PrimitiveType.Cube, new(0, .52f, 0), new(.46f, .1f, .36f), tissu, new(0, 20, 0));
        Prim(t, PrimitiveType.Cube, new(0, .58f, 0), new(.3f, .03f, .2f), Mat(new Color(.9f, .9f, .9f), .3f), new(0, 20, 0));
        return .7f;
    }
    float ModeleKepi(Transform t) { var k = GardesPortail.Kepi(t); k.localPosition = Vector3.up * .05f; k.localScale = Vector3.one * 1.3f; return .4f; }

    // ---------- Effets ----------
    void PrendreBoule() { Boules = Mathf.Min(Boules + 3, 9); Annoncer($"Boule dorée ×{Boules} — maintenir G pour viser, relâcher pour lancer"); }
    void PrendreCles() { ClesTracteur = true; Annoncer("Clés du tracteur tondeuse ! Il attend sous la grange."); }
    void PrendrePastis() { Griser(10f, new Color(1f, .82f, .25f)); Annoncer("Un petit jaune du gardien… ça tangue !"); }
    void PrendreGilet()
    {
        Gilet = 3; Annoncer("Gilet pare-balles : 3 billes encaissées contre les bots");
        if (giletJoueur == null && partie.personnage != null) giletJoueur = GiletSur(partie.personnage);
        if (giletJoueur != null) giletJoueur.gameObject.SetActive(true);
    }
    void PrendreKepi()
    {
        KepiPorte = true; Annoncer("Képi coiffé, garde-à-vous ! (V pour se voir)");
        if (kepiJoueur == null && partie.personnage != null) kepiJoueur = Habiller(partie.personnage.transform, new[] { "Head" }, t => GardesPortail.Kepi(t).localPosition = Vector3.zero, .32f);
        if (kepiJoueur != null) kepiJoueur.gameObject.SetActive(true);
    }

    // Gilet ajusté au torse du robot (maillage rigide « Torso », accroché à l'os Body) : boîte un peu plus large
    // que le torse, dans le repère du maillage (cube unité = boîte englobante du torse).
    public static Transform GiletSur(GameObject robot)
    {
        MeshFilter torse = null;
        foreach (var f in robot.GetComponentsInChildren<MeshFilter>(true)) if (f.name == "Torso" && f.sharedMesh != null) { torse = f; break; }
        if (torse == null) return null;
        var b = torse.sharedMesh.bounds;
        var a = new GameObject("Gilet").transform; a.SetParent(torse.transform, false);
        a.localPosition = b.center; a.localScale = b.size;
        var tissu = Mat(new Color(.18f, .2f, .14f), .2f); var bande = Mat(new Color(.9f, .9f, .9f), .3f);
        Prim(a, PrimitiveType.Cube, new(0, -.08f, 0), new(1.1f, .8f, 1.12f), tissu);
        foreach (float z in new[] { -1f, 1f })
        {
            Prim(a, PrimitiveType.Cube, new(0, -.02f, z * .58f), new(.62f, .5f, .05f), tissu);
            Prim(a, PrimitiveType.Cube, new(0, -.32f, z * .6f), new(.9f, .07f, .03f), bande);
        }
        foreach (float x in new[] { -1f, 1f }) Prim(a, PrimitiveType.Cube, new(x * .32f, .33f, 0), new(.24f, .06f, 1.14f), tissu);
        foreach (var t in a.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = robot.layer;
        return a;
    }

    // Os du squelette (de préférence à un nœud de maillage du même nom).
    static Transform Os(Transform robot, string nom)
    {
        foreach (var s in robot.GetComponentsInChildren<SkinnedMeshRenderer>(true)) foreach (var o in s.bones) if (o != null && o.name == nom) return o;
        foreach (var t in robot.GetComponentsInChildren<Transform>(true)) if (t.name == nom) return t;
        return null;
    }

    // Accessoire posé sur un os du personnage (compense l'échelle de l'os).
    public static Transform Habiller(Transform robot, string[] os, System.Action<Transform> construire, float hauteur)
    {
        Transform cible = null;
        foreach (var n in os) { cible = Os(robot, n); if (cible != null) break; }
        var a = new GameObject("Accessoire").transform; construire(a);
        if (cible == null) { a.SetParent(robot, false); a.localPosition = new Vector3(0, 1.1f, 0); return a; }
        a.SetParent(cible, false); float e = 1f / Mathf.Max(.01f, cible.lossyScale.y); a.localScale = Vector3.one * e; a.localPosition = new Vector3(0, hauteur * e, 0);
        return a;
    }

    bool EnJeu => interfaceVisite == null || interfaceVisite.EcranActuel == InterfaceVisite.Ecran.Visite;

    void Update()
    {
        if (partie == null) return;
        bool pause = partie.Active && partie.EnPause;
        bool peut = Boules > 0 && EnJeu && !pause && explorateur.Monture == null;
        if (peut && lancer.WasPressedThisFrame()) vise = true;
        if (vise && (!peut || lancer.WasReleasedThisFrame())) { if (peut) LancerBoule(); vise = false; }
        AfficherVisee(vise);
        secousse = Mathf.MoveTowards(secousse, 0, Time.deltaTime * 2.5f);
        if (!pause) { AvancerLancers(Time.deltaTime); VerifierBots(); }
        // Interface : annonce, inventaire, voile jaune du pastis.
        if (annonce != null) annonce.alpha = Mathf.Clamp01((annonceJusqua - Time.time) / .6f);
        if (inventaire != null)
        {
            var l = new List<string>();
            if (Boules > 0) l.Add($"G (maintenir) · boule dorée ×{Boules}");
            if (Gilet > 0) l.Add("Gilet " + new string('●', Gilet));
            if (ClesTracteur) l.Add("Clés du tracteur");
            if (KepiPorte) l.Add("Képi");
            if (InventaireSup != null) l.AddRange(InventaireSup());
            inventaire.text = EnJeu ? string.Join("   ·   ", l) : "";
        }
        if (voileFlou != null) { float f = Flou; voileFlou.color = new Color(teinteFlou.r, teinteFlou.g, teinteFlou.b, f * (.16f + .06f * Mathf.Sin(Time.time * 3))); }
    }

    // Pastis : la vue tangue (appliqué après la caméra, retiré à l'image suivante si personne ne l'a réécrite).
    void LateUpdate()
    {
        if (tete == null) return;
        if (derniere.HasValue && tete.localRotation == derniere.Value) tete.localRotation = avantFlou;
        derniere = null;
        float f = Flou, sc = secousse * secousse; if (f <= 0 && sc <= 0) return;
        float t = Time.time;
        avantFlou = tete.localRotation;
        tete.localRotation = avantFlou * Quaternion.Euler(f * 3f * Mathf.Sin(t * 1.3f) + sc * 2.5f * Mathf.Sin(t * 47), f * 4f * Mathf.Sin(t * .9f) + sc * 2f * Mathf.Sin(t * 39), f * 7f * Mathf.Sin(t * .7f));
        derniere = tete.localRotation;
    }

    Vector3 DepartLancer => tete.position + tete.forward * .5f - tete.up * .1f;
    Vector3 VitesseDepart => tete.forward * VitesseLancer + Vector3.up * 2.5f;

    public void LancerBoule()
    {
        Boules--;
        var b = Prim(null, PrimitiveType.Sphere, Vector3.zero, Vector3.one * .12f, Mat(Or, .85f, 1f, Or * .35f));
        b.name = "BouleDoreeLancee"; b.gameObject.layer = 2;
        b.position = DepartLancer;
        lancers.Add(new Lancer { t = b, v = VitesseDepart });
    }

    // Trajectoire en pointillés dorés (même intégration que le vol) et cercle de l'explosion à l'arrivée.
    void AfficherVisee(bool actif)
    {
        if (visee == null)
        {
            if (!actif) return;
            visee = new GameObject("ViseeBoule").transform;
            var or = Mat(Or, .6f, 0, Or * 1.6f); var c = partie.Couleur; var peinture = Mat(c, .4f, 0, c * 1.2f);
            for (int i = 0; i < 40; i++) points.Add(Prim(visee, PrimitiveType.Sphere, Vector3.zero, Vector3.one * .055f, or));
            for (int i = 0; i < 32; i++) cercle.Add(Prim(visee, PrimitiveType.Cube, Vector3.zero, new Vector3(.06f, .03f, .5f), peinture));
            foreach (var r in visee.GetComponentsInChildren<Renderer>()) { r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.gameObject.layer = 2; }
        }
        visee.gameObject.SetActive(actif);
        if (!actif) return;
        Vector3 a = DepartLancer, v = VitesseDepart; const float dt = .03f;
        int n = 0; bool touche = false; RaycastHit h = default; float t = 0;
        for (int k = 0; k < 200 && !touche; k++)
        {
            v += Physics.gravity * dt; Vector3 b = a + v * dt;
            if (Physics.SphereCast(a, .06f, (b - a).normalized, out h, (b - a).magnitude, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) { touche = true; b = h.point; }
            t += (b - a).magnitude;
            // Un point tous les 35 cm, qui défilent doucement vers la cible.
            float pas = .35f, decal = (Time.time * .9f) % pas;
            while (n < points.Count && t > n * pas + decal) { points[n].position = b; points[n].gameObject.SetActive(true); n++; }
            a = b;
        }
        for (int i = n; i < points.Count; i++) points[i].gameObject.SetActive(false);
        for (int i = 0; i < cercle.Count; i++)
        {
            cercle[i].gameObject.SetActive(touche);
            if (!touche) continue;
            Vector3 nrm = h.normal, tg = Vector3.Cross(nrm, Vector3.up); if (tg.sqrMagnitude < .01f) tg = Vector3.Cross(nrm, Vector3.right); tg.Normalize();
            Vector3 bt = Vector3.Cross(nrm, tg); float ang = (i + Time.time * 1.5f) * Mathf.PI * 2 / cercle.Count;
            Vector3 dir = tg * Mathf.Cos(ang) + bt * Mathf.Sin(ang);
            cercle[i].SetPositionAndRotation(h.point + nrm * .05f + dir * RayonEclaboussure, Quaternion.LookRotation(Vector3.Cross(nrm, dir), nrm));
        }
    }

    void AvancerLancers(float dt)
    {
        for (int i = lancers.Count - 1; i >= 0; i--)
        {
            var l = lancers[i]; l.age += dt;
            Vector3 a = l.t.position; l.v += Physics.gravity * dt; Vector3 b = a + l.v * dt;
            if (Physics.SphereCast(a, .06f, (b - a).normalized, out var h, (b - a).magnitude, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) || l.age > 6)
            {
                if (l.age <= 6) Eclabousser(h.point, h.normal);
                Destroy(l.t.gameObject); lancers.RemoveAt(i); continue;
            }
            l.t.position = b; l.t.Rotate(Vector3.right, 720 * dt, Space.Self);
        }
        // Gouttes de l'explosion : tache là où elles retombent.
        for (int i = gouttes.Count - 1; i >= 0; i--)
        {
            var g = gouttes[i]; g.age += dt;
            Vector3 a = g.t.position; g.v += Physics.gravity * dt; Vector3 b = a + g.v * dt;
            bool fin = g.age > 3;
            if (!fin && Physics.Raycast(a, (b - a).normalized, out var h, (b - a).magnitude + .02f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            { if (partie.impacts != null && Random.value < .7f) partie.impacts.Marquer(h, g.c, Random.Range(.6f, 1.3f)); fin = true; }
            if (fin) { Destroy(g.t.gameObject); gouttes.RemoveAt(i); continue; }
            g.t.position = b; g.t.rotation = Quaternion.LookRotation(g.v); g.t.localScale = new Vector3(.09f, .09f, Mathf.Clamp(g.v.magnitude * .03f, .1f, .35f));
        }
        // Souffle : boule de peinture qui gonfle d'un coup puis se résorbe.
        for (int i = souffles.Count - 1; i >= 0; i--)
        {
            var (t, age) = souffles[i]; age += dt; souffles[i] = (t, age);
            float e = age < .12f ? Mathf.Lerp(.3f, 3.2f, age / .12f) : Mathf.Lerp(3.2f, 0, (age - .12f) / .3f);
            if (age > .42f) { Destroy(t.gameObject); souffles.RemoveAt(i); continue; }
            t.localScale = new Vector3(e, e * .55f, e);
        }
    }

    // Explosion : grosse tache centrale, couronne de taches, murs proches, gouttes projetées jusqu'à ~6 m,
    // souffle de peinture, flash, secousse et son ; cibles et bots touchés dans un rayon de 4,5 m.
    void Eclabousser(Vector3 point, Vector3 normale)
    {
        Color c = partie.Couleur;
        Color Teinte() { Color.RGBToHSV(c, out var hh, out var ss, out var vv); return Color.HSVToRGB(hh, Mathf.Clamp01(ss * Random.Range(.8f, 1.1f)), Mathf.Clamp01(vv * Random.Range(.75f, 1.15f))); }
        if (partie.impacts != null)
        {
            for (int k = 0; k < 26; k++)
            {
                float r = k < 6 ? Random.Range(0, .5f) : Random.Range(.4f, RayonEclaboussure * .75f);
                Vector2 d = Random.insideUnitCircle.normalized * r;
                Vector3 o = point + normale * 1.2f + new Vector3(d.x, 0, d.y);
                if (Physics.Raycast(o, Vector3.down + new Vector3(d.x, 0, d.y) * .1f, out var h, 4f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                    partie.impacts.Marquer(h, Teinte(), k < 6 ? Random.Range(2.6f, 3.6f) : Mathf.Lerp(2.2f, .9f, r / RayonEclaboussure));
            }
            for (int k = 0; k < 12; k++)
            {
                Vector3 dir = Quaternion.Euler(Random.Range(-25, 10), k * 30 + Random.Range(0, 20), 0) * Vector3.forward;
                if (Physics.Raycast(point + normale * .5f, dir, out var h, RayonEclaboussure, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) partie.impacts.Marquer(h, Teinte(), Random.Range(1.2f, 2f));
            }
        }
        // Gouttes projetées en corolle autour de la normale.
        var mats = new Material[4]; for (int i = 0; i < mats.Length; i++) { var t = Teinte(); mats[i] = Mat(t, .7f, 0, t * .25f); }
        for (int k = 0; k < 70; k++)
        {
            Vector3 dir = (normale * Random.Range(.35f, 1.1f) + Random.onUnitSphere).normalized; if (Vector3.Dot(dir, normale) < .1f) dir = Vector3.Reflect(dir, normale);
            var g = Prim(null, PrimitiveType.Sphere, Vector3.zero, Vector3.one * .09f, mats[k % mats.Length]);
            g.name = "GouttePeinture"; g.gameObject.layer = 2; g.GetComponent<Renderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            g.position = point + normale * .15f;
            gouttes.Add(new Goutte { t = g, v = dir * Random.Range(4f, 10.5f), c = mats[k % mats.Length].GetColor("_BaseColor") });
        }
        var souffle = Prim(null, PrimitiveType.Sphere, point, Vector3.one * .3f, Mat(c, .8f, 0, c * .8f));
        souffle.name = "SoufflePeinture"; souffle.gameObject.layer = 2; souffle.rotation = Quaternion.FromToRotation(Vector3.up, normale);
        souffles.Add((souffle, 0));
        var flash = new GameObject("FlashPeinture").AddComponent<Light>(); flash.type = LightType.Point; flash.color = Color.Lerp(c, Color.white, .4f);
        flash.range = 9; flash.intensity = 6; flash.transform.position = point + normale * .8f; Destroy(flash.gameObject, .18f);
        float d0 = Vector3.Distance(tete.position, point); secousse = Mathf.Max(secousse, Mathf.Clamp01(1.4f - d0 / 14f));
        SonsPaintball.Instance?.Explosion(point);
        foreach (var cible in FindObjectsByType<CiblePaintball>(FindObjectsSortMode.None))
            if (Vector3.Distance(cible.transform.position, point) < RayonEclaboussure + .5f) cible.Toucher(cible.transform.position, c);
        var bots = partie.Bots;
        if (partie.Active && partie.Mode == PaintballSolo.ModePartie.Bots && bots != null && bots.Match != null)
            foreach (var j in bots.Match.joueurs.ToArray())
            {
                if (j.id == partie.JoueurId || j.elimine) continue;
                Vector3 p = bots.Position(j.id) + Vector3.up * 1.1f;
                if (Vector3.Distance(p, point) < RayonEclaboussure && !Physics.Linecast(point + normale * .2f, p, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                    bots.Touche(partie.JoueurId, j.id, p);
            }
    }

    void ConstruireInterface()
    {
        var canvas = new GameObject("InterfaceObjets").AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay; canvas.sortingOrder = 5;
        var echelle = canvas.gameObject.AddComponent<CanvasScaler>(); echelle.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize; echelle.referenceResolution = new Vector2(1600, 900); echelle.matchWidthOrHeight = .5f;
        canvas.transform.SetParent(transform, false);
        var v = new GameObject("VoilePastis").AddComponent<Image>(); v.transform.SetParent(canvas.transform, false); v.raycastTarget = false;
        var rv = v.rectTransform; rv.anchorMin = Vector2.zero; rv.anchorMax = Vector2.one; rv.offsetMin = rv.offsetMax = Vector2.zero; v.color = Color.clear; voileFlou = v;
        TMP_Text Texte(string nom, Vector2 min, Vector2 max, float taille)
        {
            var t = new GameObject(nom).AddComponent<TextMeshProUGUI>(); t.transform.SetParent(canvas.transform, false);
            t.rectTransform.anchorMin = min; t.rectTransform.anchorMax = max; t.rectTransform.offsetMin = t.rectTransform.offsetMax = Vector2.zero;
            t.fontSize = taille; t.alignment = TextAlignmentOptions.Center; t.color = new Color(.96f, .94f, .9f); t.raycastTarget = false;
            t.outlineWidth = .2f; t.outlineColor = new Color32(20, 30, 25, 220); return t;
        }
        annonce = Texte("Annonce", new(.15f, .72f), new(.85f, .8f), 30); annonce.alpha = 0;
        inventaire = Texte("Inventaire", new(.2f, .085f), new(.8f, .125f), 20);
    }

    void OnDestroy() { if (Instance == this) { Instance = null; Registre.Clear(); Detenus.Clear(); } lancer?.Disable(); if (visee != null) Destroy(visee.gameObject); }
}

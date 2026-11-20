using UnityEngine;

// Scooter (style Vespa, vert d'eau) garé au début de l'allée, près de la cour nord. E pour monter ou descendre.
// Pilotage commun aux véhicules (Vehicule) ; s'incline dans les virages.
// Modèle construit en primitives au chargement, sans asset externe.
public class Scooter : Vehicule
{
    public static Scooter Instance { get; private set; }
    // Début de l'allée est, au nord (repère D-003 : x 30,5 ; y -27) → Unity (-x, z = y).
    static readonly Vector3 Garage = new(-30.5f, 0, -27f);
    const float Cap = 0f;   // nez vers le sud, dans le sens de l'allée
    Transform corps, guidon;
    BoxCollider boite;

    public override string Nom => "le scooter";
    // Pieds du pilote : sous la selle, les yeux arrivent à ~1,4 m au-dessus du sol.
    public override Vector3 PositionPilote => transform.position + transform.up * .05f - transform.forward * .2f;
    protected override void Orienter(Vector2 entree) { if (guidon != null) guidon.localEulerAngles = new(-14, entree.x * 22f, 0); }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        if (Instance != null || Object.FindAnyObjectByType<PaintballSolo>() == null) return;
        var go = new GameObject("Scooter");
        Instance = go.AddComponent<Scooter>();
        Instance.Poser(Garage, Cap);
        Instance.Construire();
    }

    void Construire()
    {
        Material M(Color c, float lisse, float metal = 0) => Materiau(c, lisse, metal);
        var peinture = M(new Color(.62f, .82f, .74f), .78f, .1f);
        var creme = M(new Color(.93f, .9f, .82f), .5f);
        var cuir = M(new Color(.22f, .13f, .08f), .35f);
        var chrome = M(new Color(.82f, .83f, .85f), .9f, 1f);
        var pneu = M(new Color(.04f, .04f, .04f), .15f);
        var phare = M(new Color(1f, .97f, .85f), .95f);
        corps = new GameObject("Corps").transform; corps.SetParent(transform, false);
        Transform Piece(PrimitiveType t, string nom, Vector3 pos, Vector3 echelle, Material m, Transform parent = null, Vector3 rot = default)
            => base.Piece(parent ?? corps, t, nom, pos, echelle, m, rot);
        // Coque arrière bombée, plancher, tablier avant, garde-boue, selle biplace
        Piece(PrimitiveType.Sphere, "CoqueArriere", new(0, .5f, -.38f), new(.58f, .52f, .92f), peinture);
        Piece(PrimitiveType.Cube, "Plancher", new(0, .27f, .12f), new(.36f, .07f, .78f), creme);
        Piece(PrimitiveType.Cube, "Tablier", new(0, .62f, .44f), new(.44f, .72f, .07f), peinture, null, new(-14, 0, 0));
        Piece(PrimitiveType.Sphere, "GardeBoue", new(0, .38f, .6f), new(.2f, .3f, .46f), peinture);
        Piece(PrimitiveType.Capsule, "Selle", new(0, .82f, -.34f), new(.32f, .07f, .36f), cuir, null, new(90, 0, 0));
        Piece(PrimitiveType.Cube, "Porte-bagages", new(0, .82f, -.78f), new(.26f, .02f, .24f), chrome);
        // Colonne de direction, guidon, phare, rétroviseurs
        guidon = new GameObject("Guidon").transform; guidon.SetParent(corps, false); guidon.localPosition = new(0, .5f, .5f); guidon.localEulerAngles = new(-14, 0, 0);
        Piece(PrimitiveType.Cylinder, "Colonne", new(0, .28f, 0), new(.07f, .28f, .07f), peinture, guidon);
        Piece(PrimitiveType.Cube, "TeteGuidon", new(0, .58f, 0), new(.24f, .1f, .14f), peinture, guidon);
        Piece(PrimitiveType.Cylinder, "Guidon", new(0, .6f, -.02f), new(.035f, .32f, .035f), chrome, guidon, new(0, 0, 90));
        Piece(PrimitiveType.Sphere, "Phare", new(0, .6f, .08f), new(.11f, .11f, .06f), phare, guidon);
        foreach (int s in new[] { -1, 1 })
        {
            Piece(PrimitiveType.Cylinder, "Poignee", new(s * .3f, .6f, -.02f), new(.045f, .05f, .045f), pneu, guidon, new(0, 0, 90));
            Piece(PrimitiveType.Cylinder, "TigeRetro", new(s * .2f, .72f, 0), new(.012f, .1f, .012f), chrome, guidon, new(0, 0, s * -20));
            Piece(PrimitiveType.Sphere, "Retro", new(s * .24f, .83f, 0), new(.08f, .06f, .015f), chrome, guidon);
        }
        // Roues : pneu, jante chromée
        Transform Roue(string nom, float z)
        {
            var r = new GameObject(nom).transform; r.SetParent(corps, false); r.localPosition = new(0, .2f, z);
            Piece(PrimitiveType.Cylinder, "Pneu", Vector3.zero, new(.4f, .05f, .4f), pneu, r, new(0, 0, 90));
            Piece(PrimitiveType.Cylinder, "Jante", Vector3.zero, new(.24f, .055f, .24f), chrome, r, new(0, 0, 90));
            return r;
        }
        roues = new[] { Roue("RoueAvant", .6f), Roue("RoueArriere", -.58f) }; rayons = new[] { .2f, .2f };
        foreach (var r in GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
        boite = gameObject.AddComponent<BoxCollider>(); boite.center = new(0, .8f, 0); boite.size = new(.7f, 1.6f, 1.8f);   // haute : visable à hauteur des yeux pour monter
    }

    void OnDestroy() { if (Instance == this) Instance = null; }
}

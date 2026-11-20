using UnityEngine;

// Tracteur tondeuse du jardinier, garé sous sa grange, capot vers l'ouverture : il faut d'abord trouver les clés
// (sur l'établi). Remplace au chargement le modèle immobile du parc (parc_tracteur_tondeuse) par un modèle
// pilotable en primitives.
public class Tracteur : Vehicule
{
    public static Tracteur Instance { get; private set; }
    protected override float VitesseMax => 4.8f;
    protected override float MarcheArriere => 2f;
    protected override float Acceleration => 2.6f;
    protected override float Braquage => 70f;
    protected override float Inclinaison => 2f;
    protected override float Rayon => .5f;
    protected override float Avant => .7f;
    protected override float Arriere => .5f;
    public override string Nom => "le tracteur tondeuse";
    public override Vector3 PositionPilote => transform.position + transform.up * .08f - transform.forward * .3f;
    Transform lame;

    public override string Libelle(Explorateur e) => ObjetsDomaine.ClesTracteur ? "Monter sur le tracteur tondeuse" : "Tracteur tondeuse (clés introuvables)";
    public override void Interagir(Explorateur e)
    {
        if (!ObjetsDomaine.ClesTracteur) { ObjetsDomaine.Annoncer("Pas de clés… Le jardinier les laisse sur l'établi de la grange."); return; }
        base.Interagir(e);
    }
    protected override void Orienter(Vector2 entree)
    {
        if (direction != null) direction.localEulerAngles = new(-35, 0, -entree.x * 60f);
        if (lame != null) lame.Rotate(Vector3.up, 1400f * Time.deltaTime, Space.Self);
    }

    public static void Installer()
    {
        if (Instance != null) return;
        var origine = GameObject.Find("parc_tracteur_tondeuse");
        if (origine == null) return;
        // Capot vers -x local dans Blender, grange orientée à 8° (travail/plan_domaine.json) ; D-003 → Unity (-x, z, y).
        // Entre les deux poteaux de la façade ouverte, loin de l'établi (mur du fond).
        float a = 8f * Mathf.Deg2Rad, lacet = Mathf.Atan2(Mathf.Cos(a), -Mathf.Sin(a)) * Mathf.Rad2Deg;
        origine.SetActive(false); Physics.SyncTransforms();
        Vector3 p = ObjetsDomaine.Local(83.4f, 88f, 8, -.5f, 0);
        var go = new GameObject("TracteurTondeuse");
        Instance = go.AddComponent<Tracteur>();
        Instance.Poser(p, lacet);
        Instance.Construire();
    }

    void Construire()
    {
        var vert = Materiau(new Color(.08f, .32f, .1f), .65f, .2f);
        var jaune = Materiau(new Color(.85f, .65f, .05f), .55f);
        var noir = Materiau(new Color(.03f, .03f, .03f), .4f, .3f);
        var pneu = Materiau(new Color(.04f, .04f, .04f), .15f);
        var phare = Materiau(new Color(1f, .97f, .85f), .95f);
        var corps = new GameObject("Corps").transform; corps.SetParent(transform, false);
        Transform P(PrimitiveType t, string n, Vector3 pos, Vector3 e, Material m, Transform parent = null, Vector3 rot = default) => Piece(parent ?? corps, t, n, pos, e, m, rot);
        P(PrimitiveType.Cube, "Chassis", new(0, .42f, -.05f), new(.84f, .27f, 1.4f), vert);
        P(PrimitiveType.Cube, "Capot", new(0, .45f, .55f), new(.72f, .26f, .8f), vert, null, new(8, 0, 0));
        P(PrimitiveType.Sphere, "NezCapot", new(0, .42f, .92f), new(.7f, .26f, .2f), vert);
        P(PrimitiveType.Sphere, "Phare", new(0, .48f, 1f), new(.18f, .08f, .04f), phare);
        P(PrimitiveType.Cube, "Plateau", new(0, .17f, .15f), new(1.2f, .1f, .8f), noir);
        lame = P(PrimitiveType.Cylinder, "Lame", new(0, .11f, .15f), new(.7f, .01f, .7f), noir);
        P(PrimitiveType.Cube, "Siege", new(0, .64f, -.35f), new(.5f, .08f, .4f), noir);
        P(PrimitiveType.Cube, "Dossier", new(0, .82f, -.54f), new(.5f, .32f, .08f), noir, null, new(-10, 0, 0));
        P(PrimitiveType.Cube, "AileG", new(-.48f, .56f, -.45f), new(.2f, .04f, .5f), vert);
        P(PrimitiveType.Cube, "AileD", new(.48f, .56f, -.45f), new(.2f, .04f, .5f), vert);
        P(PrimitiveType.Cylinder, "Colonne", new(0, .72f, .12f), new(.05f, .2f, .05f), noir, null, new(-35, 0, 0));
        direction = new GameObject("Volant").transform; direction.SetParent(corps, false); direction.localPosition = new(0, .9f, .02f);
        P(PrimitiveType.Cylinder, "Couronne", Vector3.zero, new(.36f, .015f, .36f), noir, direction);
        P(PrimitiveType.Cube, "Rayon", Vector3.zero, new(.34f, .02f, .03f), noir, direction);
        Transform Roue(string n, float x, float z, float rayon)
        {
            var t = new GameObject(n).transform; t.SetParent(corps, false); t.localPosition = new(x, rayon, z);
            P(PrimitiveType.Cylinder, "Pneu", Vector3.zero, new(rayon * 2, .1f, rayon * 2), pneu, t, new(0, 0, 90));
            P(PrimitiveType.Cylinder, "Jante", Vector3.zero, new(rayon * 1.1f, .105f, rayon * 1.1f), jaune, t, new(0, 0, 90));
            return t;
        }
        roues = new[] { Roue("AvantG", -.48f, .7f, .18f), Roue("AvantD", .48f, .7f, .18f), Roue("ArriereG", -.48f, -.45f, .27f), Roue("ArriereD", .48f, -.45f, .27f) };
        rayons = new[] { .18f, .18f, .27f, .27f };
        foreach (var rd in GetComponentsInChildren<Renderer>()) rd.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
        var boite = gameObject.AddComponent<BoxCollider>(); boite.center = new(0, .8f, .1f); boite.size = new(1.1f, 1.6f, 1.9f);
    }

    void OnDestroy() { if (Instance == this) Instance = null; }
}

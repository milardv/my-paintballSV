using System.Collections;
using UnityEngine;

// Tyrolienne du toit au bassin : un mât sur le toit (près de la trappe), un câble tendu au-dessus du parc jusqu'à
// un mât au-delà du bassin. E sous la poulie pour s'accrocher ; la descente accélère avec la pente (16 m/s au plus),
// on vise et on tire pendant le trajet, E pour lâcher où l'on veut ; au-dessus du bassin, on lâche tout seul.
public class Tyrolienne : Vehicule
{
    public static Tyrolienne Instance { get; private set; }
    public override string Nom => "la tyrolienne";
    public override string Libelle(Explorateur e) => "S'accrocher à la tyrolienne";

    Vector3 haut, bas, lacher;
    float longueur, s, v, fleche, retour;
    Transform poulie;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        if (GameObject.Find("Chateau") == null || Object.FindAnyObjectByType<PaintballSolo>() == null || Instance != null) return;
        Instance = new GameObject("Tyrolienne").AddComponent<Tyrolienne>();
    }

    IEnumerator Start()
    {
        yield return null;   // EscalierToit a posé la sortie du toit
        var eau = GameObject.Find("parc_bassin_eau");
        var re = eau != null ? eau.GetComponentInChildren<Renderer>() : null;
        if (re == null || EscalierToit.SortieToit == Vector3.zero) { Debug.LogWarning("TYROLIENNE : toit ou bassin introuvable"); yield break; }
        var bassin = re.bounds;
        Vector3 depart = EscalierToit.SortieToit;
        Vector3 vers = bassin.center - depart; vers.y = 0; vers.Normalize();
        // Mât du toit du château, 2,5 m après la trappe vers le bassin, posé sur la toiture.
        Vector3 pied = depart + vers * 2.5f;
        if (Physics.Raycast(pied + Vector3.up * 5, Vector3.down, out var t, 12, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) pied = t.point;
        haut = pied + Vector3.up * 2.6f;
        // Mât d'arrivée planté dans le bassin, au milieu de l'eau : on y arrive à 2,6 m au-dessus de la surface.
        // (décalé du centre vers le château, pour laisser le jet de la fontaine libre)
        Vector3 piedBas = new Vector3(bassin.center.x, bassin.max.y, bassin.center.z) - vers * Mathf.Min(bassin.extents.x, bassin.extents.z) * .45f;
        if (Physics.Raycast(piedBas + Vector3.up * 2, Vector3.down, out var fond, 8, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) piedBas.y = Mathf.Min(piedBas.y, fond.point.y);
        bas = new Vector3(piedBas.x, bassin.max.y + 2.6f, piedBas.z) + Vector3.up * 1.95f;
        longueur = Vector3.Distance(haut, bas);
        fleche = longueur * .025f;
        Vector3 audessus = new(bassin.center.x, 0, bassin.center.z);
        s = 0;
        float meilleur = float.MaxValue;
        for (float x = 0; x <= longueur; x += .25f)
        {
            Vector3 p = Point(x); float d = new Vector2(p.x - audessus.x, p.z - audessus.z).sqrMagnitude;
            if (d < meilleur) { meilleur = d; lacher = p; }
        }
        transform.position = Point(0);   // avant la construction : mâts et câble sont posés en coordonnées monde
        Construire(pied, piedBas);
        cap = Quaternion.LookRotation(vers).eulerAngles.y;
        Debug.Log($"TYROLIENNE {longueur:0} m, dénivelé {haut.y - bas.y:0.0} m ; haut D-003 ({-haut.x:0.0}, {haut.z:0.0}, {haut.y:0.0}), bas ({-bas.x:0.0}, {bas.z:0.0}, {bas.y:0.0})");
    }

    // Câble en chaînette approchée (parabole), du mât du toit au mât du bassin.
    Vector3 Point(float x)
    {
        float u = Mathf.Clamp01(x / longueur);
        return Vector3.Lerp(haut, bas, u) + Vector3.down * (fleche * 4 * u * (1 - u));
    }

    void Construire(Vector3 pied, Vector3 piedBas)
    {
        var acier = Materiau(new Color(.55f, .56f, .6f), .7f, .9f);
        var bois = Materiau(new Color(.85f, .82f, .74f), .3f);   // mâts peints en blanc cassé, visibles de nuit
        Mat(pied, haut + Vector3.up * .3f, bois);
        Mat(piedBas, bas + Vector3.up * .3f, bois);
        int n = 40;
        for (int i = 0; i < n; i++)
        {
            Vector3 a = Point(longueur * i / n), b = Point(longueur * (i + 1) / n);
            var c = Piece(null, PrimitiveType.Cylinder, "TyrolienneCable", (a + b) / 2, new Vector3(.06f, Vector3.Distance(a, b) / 2, .06f), acier);
            c.up = b - a; c.SetParent(transform, true);
        }
        poulie = new GameObject("TyroliennePoulie").transform; poulie.SetParent(transform, false);
        var jaune = Materiau(new Color(.95f, .72f, .1f), .5f);
        Piece(poulie, PrimitiveType.Cube, "Chariot", Vector3.down * .08f, new Vector3(.12f, .16f, .3f), jaune);
        Piece(poulie, PrimitiveType.Cylinder, "Sangle", Vector3.down * .55f, new Vector3(.03f, .45f, .03f), Materiau(new Color(.1f, .1f, .12f), .2f));
        Piece(poulie, PrimitiveType.Cube, "Poignee", Vector3.down * 1.0f, new Vector3(.5f, .04f, .04f), jaune);
        // Zone d'accroche : le joueur vise la poulie et la sangle.
        var zone = poulie.gameObject.AddComponent<BoxCollider>(); zone.center = Vector3.down * .6f; zone.size = new Vector3(.6f, 1.3f, .6f);
    }

    void Mat(Vector3 pied, Vector3 sommet, Material m)
    {
        var g = GameObject.CreatePrimitive(PrimitiveType.Cylinder); g.name = "TyrolienneMat";
        g.transform.SetParent(transform, true);
        g.transform.position = (pied + sommet) / 2; g.transform.localScale = new Vector3(.22f, Vector3.Distance(pied, sommet) / 2, .22f);
        g.GetComponent<Renderer>().sharedMaterial = m;
    }

    public override Vector3 PositionPilote => (poulie != null ? poulie.position : transform.position) + Vector3.down * 1.95f;
    public override Vector3 PointDescente => (poulie != null ? poulie.position : transform.position) + Vector3.down * 1.85f;

    public override void Interagir(Explorateur e)
    {
        if (Pilote != null || s > .5f) return;
        v = 0;
        base.Interagir(e);
        ObjetsDomaine.Annoncer("Tyrolienne ! E pour lâcher");
    }

    public override void Liberer() { base.Liberer(); retour = Time.time + 2.5f; }

    public override void Conduire(Vector2 entree, float dt)
    {
        if (dt <= 0 || longueur <= 0) return;
        Vector3 pente = (Point(s + .5f) - Point(s)).normalized;
        v = Mathf.Min(16f, v + (-Physics.gravity.y * Mathf.Max(.05f, -pente.y) - .015f * v * v) * dt);
        s = Mathf.Min(longueur, s + v * dt);
        if (poulie != null) poulie.position = Point(s);
        // En bout de câble, au-dessus de l'eau : on lâche dans le bassin.
        if (s >= longueur - .6f) Pilote?.Descendre();
    }

    void Update()
    {
        if (Pilote != null || poulie == null || s <= 0 || Time.time < retour) return;
        s = 0; v = 0; poulie.position = Point(0);    // la poulie revient au départ
    }

    void OnDestroy() { if (Instance == this) Instance = null; }
}

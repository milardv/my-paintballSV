using UnityEngine;

// Véhicule pilotable (scooter, tracteur tondeuse). E pour monter ou descendre.
// Pilotage : Z accélère, S freine puis recule, Q/D braquent ; la souris vise librement et l'on tire comme à
// pied. Suit le relief (rayons sous les roues avant et arrière), s'arrête contre les obstacles.
public abstract class Vehicule : MonoBehaviour, IInteractif
{
    protected virtual float VitesseMax => 11f;
    protected virtual float MarcheArriere => 3f;
    protected virtual float Acceleration => 4.5f;
    protected virtual float Freinage => 9f;
    protected virtual float Roulement => 1.5f;
    protected virtual float Braquage => 75f;
    protected virtual float Inclinaison => 14f;            // roulis dans les virages (deux-roues)
    protected virtual float Rayon => .32f;                 // gabarit pour les obstacles
    protected virtual float Avant => .6f;                  // position des essieux
    protected virtual float Arriere => .58f;
    public abstract string Nom { get; }

    public float Vitesse { get; private set; }
    public string DernierObstacle { get; private set; } = "";
    protected float cap, roulis;
    protected Transform direction;
    protected Transform[] roues = new Transform[0];
    protected float[] rayons = new float[0];
    Explorateur pilote;

    public virtual string Libelle(Explorateur e) => "Monter sur " + Nom;
    public virtual void Interagir(Explorateur e)
    {
        if (pilote != null) return;
        pilote = e; Couche(2); e.Monter(this); e.transform.rotation = Quaternion.Euler(0, cap, 0); e.ReinitialiserRegard();
    }
    public virtual void Liberer() { pilote = null; Vitesse = 0; Couche(0); }
    protected Explorateur Pilote => pilote;
    void Couche(int c) { foreach (Transform t in GetComponentsInChildren<Transform>()) t.gameObject.layer = c; }
    public abstract Vector3 PositionPilote { get; }
    // Point d'où l'on descend (tyrolienne : sous la poulie, pour retomber de là).
    public virtual Vector3 PointDescente => transform.position;

    // Sol praticable sous un point : surface la plus haute à moins de 1,2 m au-dessus du terrain (sol d'un
    // bâtiment, établi), jamais un toit.
    public static float Sol(Vector3 p)
    {
        var touches = Physics.RaycastAll(new Vector3(p.x, p.y + 60, p.z), Vector3.down, 120, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
        if (touches.Length == 0) return p.y;
        float bas = float.MaxValue; foreach (var h in touches) bas = Mathf.Min(bas, h.point.y);
        return Physics.Raycast(new Vector3(p.x, bas + 1.2f, p.z), Vector3.down, out var s, 1.4f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) ? s.point.y : bas;
    }

    protected void Poser(Vector3 p, float lacet)
    {
        p.y = Sol(p);
        cap = lacet; transform.SetPositionAndRotation(p, Quaternion.Euler(0, lacet, 0));
    }

    protected static Material Materiau(Color c, float lisse, float metal = 0)
    {
        var m = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        m.SetColor("_BaseColor", c); m.SetFloat("_Smoothness", lisse); m.SetFloat("_Metallic", metal); return m;
    }

    protected Transform Piece(Transform parent, PrimitiveType t, string nom, Vector3 pos, Vector3 echelle, Material m, Vector3 rot = default)
    {
        var g = GameObject.CreatePrimitive(t); g.name = nom; Destroy(g.GetComponent<Collider>());
        g.transform.SetParent(parent, false); g.transform.localPosition = pos; g.transform.localScale = echelle; g.transform.localEulerAngles = rot;
        g.GetComponent<Renderer>().sharedMaterial = m; return g.transform;
    }

    protected virtual void Orienter(Vector2 entree) { }

    public virtual void Conduire(Vector2 entree, float dt)
    {
        if (dt <= 0) return;
        if (entree.y > .1f) Vitesse = Vitesse < 0 ? Mathf.MoveTowards(Vitesse, 0, Freinage * dt) : Mathf.MoveTowards(Vitesse, VitesseMax * entree.y, Acceleration * dt);
        else if (entree.y < -.1f) Vitesse = Vitesse > 0 ? Mathf.MoveTowards(Vitesse, 0, Freinage * dt) : Mathf.MoveTowards(Vitesse, -MarcheArriere, Acceleration * .6f * dt);
        else Vitesse = Mathf.MoveTowards(Vitesse, 0, Roulement * dt);
        float facteur = Mathf.Clamp01(Mathf.Abs(Vitesse) / 2.5f) * (1 - .45f * Mathf.Clamp01(Mathf.Abs(Vitesse) / VitesseMax));
        cap += entree.x * Braquage * facteur * Mathf.Sign(Vitesse == 0 ? 1 : Vitesse) * dt;
        Vector3 avant = Quaternion.Euler(0, cap, 0) * Vector3.forward;
        Vector3 pas = avant * Vitesse * dt;
        // Les surfaces praticables (sol, pente, bordure basse) ne bloquent pas : seulement murs, troncs, véhicules.
        Vector3 centre = transform.position + Vector3.up * .55f;
        if (pas.sqrMagnitude > 0 && Physics.SphereCast(centre, Rayon, pas.normalized, out var obstacle, pas.magnitude + .55f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
            && obstacle.normal.y < .6f && obstacle.point.y > transform.position.y + .3f)
        { Vitesse = 0; pas = Vector3.zero; DernierObstacle = obstacle.collider.name; }
        Vector3 p = transform.position + pas;
        float Sol(Vector3 q, float defaut) => Physics.Raycast(q + Vector3.up * 1.2f, Vector3.down, out var h, 3f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) ? h.point.y : defaut;
        float ya = Sol(p + avant * Avant, p.y), yr = Sol(p - avant * Arriere, p.y);
        float y = Mathf.Max(ya, yr) - Mathf.Abs(ya - yr) * .5f;
        p.y = Mathf.MoveTowards(transform.position.y, y, 6f * dt);
        float tangage = -Mathf.Atan2(ya - yr, Avant + Arriere) * Mathf.Rad2Deg;
        roulis = Mathf.Lerp(roulis, -entree.x * Inclinaison * Mathf.Clamp01(Mathf.Abs(Vitesse) / 6f), 1 - Mathf.Exp(-5 * dt));
        transform.SetPositionAndRotation(p, Quaternion.Euler(tangage, cap, roulis));
        Orienter(entree);
        for (int i = 0; i < roues.Length; i++) roues[i].Rotate(Vector3.right, Vitesse * dt / (rayons[i] * Mathf.PI * 2) * 360f, Space.Self);
    }
}

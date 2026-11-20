using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

// Perruches à collier (nombreuses à Marseille) : une bille qui traverse le feuillage d'un arbre fait
// s'envoler une volée de 5 à 9 oiseaux, qui s'éloignent en battant des ailes puis disparaissent.
// Un même arbre ne s'envole qu'une fois toutes les 20 secondes.
public class Perruches : MonoBehaviour
{
    static readonly Regex Arbres = new(@"^parc_(chene|cypres|alep|platane|feuillu|olivier|laurier|washingtonia|phoenix|if)_\d+$");
    const float Repos = 20, Vie = 6;
    static Perruches instance;
    public static int NombreArbres => instance != null ? instance.arbres.Count : 0;
    public static int Envols { get; private set; }

    struct Arbre { public Bounds bornes; public float prochain; }
    readonly List<Arbre> arbres = new();
    readonly List<Oiseau> oiseaux = new();
    Material plumes, ventre, bec;

    class Oiseau
    {
        public Transform corps, aileG, aileD;
        public Vector3 vitesse;
        public float age, phase, virage;
    }

    public static void Installer()
    {
        if (instance != null) return;
        instance = new GameObject("Perruches").AddComponent<Perruches>();
    }

    void Start()
    {
        foreach (var t in FindObjectsByType<Transform>(FindObjectsSortMode.None))
        {
            if (!Arbres.IsMatch(t.name)) continue;
            var rendus = t.GetComponentsInChildren<Renderer>();
            if (rendus.Length == 0) continue;
            Bounds b = rendus[0].bounds; foreach (var r in rendus) b.Encapsulate(r.bounds);
            if (b.size.y < 3) continue;
            arbres.Add(new Arbre { bornes = b });
        }
        var lit = Shader.Find("Universal Render Pipeline/Lit");
        plumes = new Material(lit); plumes.SetColor("_BaseColor", new Color(.35f, .78f, .25f));
        ventre = new Material(lit); ventre.SetColor("_BaseColor", new Color(.62f, .9f, .38f));
        bec = new Material(lit); bec.SetColor("_BaseColor", new Color(.85f, .12f, .12f));
    }

    // Segment parcouru par une bille : envol si elle traverse le haut (feuillage) d'un arbre.
    public static void Bille(Vector3 a, Vector3 b)
    {
        if (instance == null) return;
        var liste = instance.arbres;
        for (int i = 0; i < liste.Count; i++)
        {
            var arbre = liste[i];
            if (Time.time < arbre.prochain) continue;
            Bounds bornes = arbre.bornes;
            float bas = bornes.min.y + bornes.size.y * .35f;
            if (b.y < bas && a.y < bas) continue;
            if (!bornes.Contains(b) && !bornes.Contains(a)) continue;
            arbre.prochain = Time.time + Repos; liste[i] = arbre; Envols++;
            instance.Envol(bornes, b);
            return;
        }
    }

    void Envol(Bounds bornes, Vector3 impact)
    {
        int n = Random.Range(5, 10);
        for (int k = 0; k < n; k++)
        {
            Vector3 depart = new(Random.Range(bornes.min.x, bornes.max.x) * .5f + bornes.center.x * .5f,
                Random.Range(bornes.center.y, bornes.max.y), Random.Range(bornes.min.z, bornes.max.z) * .5f + bornes.center.z * .5f);
            Vector3 fuite = depart - impact; fuite.y = 0;
            if (fuite.sqrMagnitude < .01f) fuite = Random.insideUnitSphere; fuite.y = 0;
            fuite = fuite.normalized * Random.Range(6f, 9f) + Vector3.up * Random.Range(2.5f, 4.5f);
            oiseaux.Add(Creer(depart, fuite));
        }
    }

    Oiseau Creer(Vector3 position, Vector3 vitesse)
    {
        var racine = new GameObject("Perruche").transform; racine.SetParent(transform, false);
        racine.SetPositionAndRotation(position, Quaternion.LookRotation(vitesse));
        Transform Piece(Transform parent, Vector3 pos, Vector3 echelle, Material m, PrimitiveType type = PrimitiveType.Sphere)
        {
            var p = GameObject.CreatePrimitive(type); Destroy(p.GetComponent<Collider>());
            p.transform.SetParent(parent, false); p.transform.localPosition = pos; p.transform.localScale = echelle;
            var r = p.GetComponent<Renderer>(); r.sharedMaterial = m; r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.receiveShadows = false;
            return p.transform;
        }
        Piece(racine, Vector3.zero, new Vector3(.09f, .09f, .22f), plumes);
        Piece(racine, new Vector3(0, -.02f, .02f), new Vector3(.07f, .06f, .14f), ventre);
        Piece(racine, new Vector3(0, .03f, .12f), new Vector3(.075f, .075f, .08f), plumes);
        Piece(racine, new Vector3(0, .02f, .17f), new Vector3(.03f, .03f, .035f), bec);
        Piece(racine, new Vector3(0, 0, -.2f), new Vector3(.03f, .012f, .2f), plumes, PrimitiveType.Cube);
        var o = new Oiseau { corps = racine, vitesse = vitesse, phase = Random.value * 6, virage = Random.Range(-40f, 40f) };
        o.aileG = new GameObject("AileG").transform; o.aileG.SetParent(racine, false); o.aileG.localPosition = new Vector3(-.04f, .02f, 0);
        o.aileD = new GameObject("AileD").transform; o.aileD.SetParent(racine, false); o.aileD.localPosition = new Vector3(.04f, .02f, 0);
        Piece(o.aileG, new Vector3(-.1f, 0, 0), new Vector3(.2f, .01f, .09f), plumes, PrimitiveType.Cube);
        Piece(o.aileD, new Vector3(.1f, 0, 0), new Vector3(.2f, .01f, .09f), plumes, PrimitiveType.Cube);
        return o;
    }

    void Update()
    {
        for (int i = oiseaux.Count - 1; i >= 0; i--)
        {
            var o = oiseaux[i];
            o.age += Time.deltaTime;
            if (o.age > Vie) { Destroy(o.corps.gameObject); oiseaux.RemoveAt(i); continue; }
            // Montée puis vol plus horizontal, léger virage propre à chaque oiseau.
            o.vitesse = Quaternion.Euler(0, o.virage * Time.deltaTime, 0) * o.vitesse;
            o.vitesse.y = Mathf.Lerp(o.vitesse.y, .6f, Time.deltaTime * .5f);
            o.corps.position += o.vitesse * Time.deltaTime;
            o.corps.rotation = Quaternion.LookRotation(o.vitesse);
            float battement = Mathf.Sin(o.age * 26 + o.phase) * 55;
            o.aileG.localRotation = Quaternion.Euler(0, 0, battement); o.aileD.localRotation = Quaternion.Euler(0, 0, -battement);
            if (o.age > Vie - 1) o.corps.localScale = Vector3.one * (Vie - o.age);
        }
    }

    void OnDestroy() { if (instance == this) instance = null; }
}

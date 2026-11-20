using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

// Hôte local d'un match contre des bots : crée les bots, constate les touches des billes sur les
// joueurs, les transmet à MatchPaintball et applique ses décisions (réapparition, élimination, fin).
// Un serveur faisant autorité pourra remplacer cet hôte sans toucher aux règles.
[DefaultExecutionOrder(45)]
public class PartieBots : MonoBehaviour
{
    public enum Niveau { Facile, Normal, Difficile }
    public static readonly string[] NomsNiveaux = { "Facile", "Normal", "Difficile" };
    public static readonly string[] NomsBots = { "Aristide", "Bérénice", "Clovis", "Delphine", "Eugène" };
    // Points d'apparition : tirés au hasard sur tout le NavMesh relié au parc (parc, terrasse et
    // intérieur du château, tous étages), avec 1,9 m de hauteur libre et à plus de 50 cm d'un bord.
    // Le parc est dix fois plus grand que le château : 40 % des points sont réservés à l'intérieur.
    // Calculés une fois, réutilisés par toutes les parties.
    const int TaillePool = 240;
    static List<Vector3> reserve;
    public static readonly Vector3 ReferenceParc = new(-12, 0, 44);

    // Corps réduit avec le robot (PaintballSolo.Echelle).
    public const float RayonCorps = .28f, BasCorps = .25f, HautCorps = 1.08f, Torse = .86f;

    public MatchPaintball Match { get; private set; }
    public readonly List<BotPaintball> bots = new();
    public readonly List<Vector3> pointsSurs = new();
    readonly Dictionary<int, Vector3> dernieres = new();
    public Niveau NiveauActuel { get; private set; }
    public int DerniereTouche { get; private set; } = -1;
    public float DegatsRecus { get; private set; }
    public int DernierTireur { get; private set; } = -1;
    // Position du tireur au moment de la dernière touche reçue, et temps écoulé depuis (indicateur du HUD).
    public Vector3 OrigineTouche { get; private set; }
    public float DepuisTouche { get; private set; } = 99;
    public float DistanceTouche { get; private set; }
    public event System.Action Change;
    PaintballSolo partie;
    CharacterController controleur;
    Explorateur explorateur;

    public static PartieBots Instance { get; private set; }

    void Awake()
    {
        Instance = this;
        partie = GetComponent<PaintballSolo>(); controleur = GetComponent<CharacterController>(); explorateur = GetComponent<Explorateur>();
    }

    public void Demarrer(int nombre, Niveau niveau)
    {
        Arreter();
        NiveauActuel = niveau;
        pointsSurs.Clear(); pointsSurs.AddRange(Reserve());
        if (pointsSurs.Count == 0) pointsSurs.Add(transform.position);
        dernieres.Clear();
        // Portes ouvertes : les bots ne savent pas les manœuvrer et l'intérieur fait partie du terrain.
        foreach (var porte in FindObjectsByType<Porte>(FindObjectsSortMode.None)) if (!porte.Ouverte) porte.Basculer(porte.transform.position + porte.transform.forward);
        Match = new MatchPaintball(new ReglesMatch { vies = partie.Vies });
        Match.Evenement += Appliquer;
        Match.Ajouter(partie.JoueurId, "Vous", partie.CouleurIndex, false);
        nombre = Mathf.Clamp(nombre, 1, 5);
        for (int i = 0; i < nombre; i++)
        {
            int couleur = (partie.CouleurIndex + 1 + i) % PaintballSolo.Couleurs.Length;
            var bot = BotPaintball.Creer(partie, this, i + 1, NomsBots[i], couleur, niveau);
            bots.Add(bot);
            Match.Ajouter(bot.Id, bot.Nom, couleur, true);
        }
        // Départs répartis : le joueur au premier point libre, chaque bot sur un point éloigné des autres.
        var pris = new List<Vector3>();
        Placer(partie.JoueurId, PointLibre(pris), pris);
        foreach (var b in bots) Placer(b.Id, PointLibre(pris), pris);
        Match.Demarrer();
        Change?.Invoke();
    }

    void Placer(int id, int point, List<Vector3> pris) { pris.Add(pointsSurs[point]); Teleporter(id, point); }

    // Départ : point au hasard à plus de 15 m des départs déjà pris (sinon le plus éloigné essayé).
    int PointLibre(List<Vector3> pris)
    {
        int meilleur = Random.Range(0, pointsSurs.Count); float distance = -1;
        for (int essai = 0; essai < 40; essai++)
        {
            int i = Random.Range(0, pointsSurs.Count);
            float d = float.MaxValue;
            foreach (var p in pris) d = Mathf.Min(d, Vector3.Distance(p, pointsSurs[i]));
            if (d > 15) return i;
            if (d > distance) { distance = d; meilleur = i; }
        }
        return meilleur;
    }

    public static List<Vector3> Reserve()
    {
        if (reserve != null) return reserve;
        reserve = new List<Vector3>();
        var tri = NavMesh.CalculateTriangulation();
        int n = tri.indices.Length / 3;
        if (n == 0) return reserve;
        var cumul = new float[n]; float total = 0;
        for (int i = 0; i < n; i++)
        {
            Vector3 a = tri.vertices[tri.indices[3 * i]], b = tri.vertices[tri.indices[3 * i + 1]], c = tri.vertices[tri.indices[3 * i + 2]];
            total += Vector3.Cross(b - a, c - a).magnitude * .5f; cumul[i] = total;
        }
        NavMesh.SamplePosition(ReferenceParc, out var reference, 6, NavMesh.AllAreas);
        var chemin = new NavMeshPath();
        int interieurs = 0, exterieurs = 0, maxInterieurs = TaillePool * 2 / 5;
        for (int essai = 0; essai < 30000 && reserve.Count < TaillePool; essai++)
        {
            int t = System.Array.BinarySearch(cumul, Random.value * total); if (t < 0) t = ~t; t = Mathf.Min(t, n - 1);
            Vector3 a = tri.vertices[tri.indices[3 * t]], b = tri.vertices[tri.indices[3 * t + 1]], c = tri.vertices[tri.indices[3 * t + 2]];
            float u = Random.value, v = Random.value; if (u + v > 1) { u = 1 - u; v = 1 - v; }
            Vector3 p = a + (b - a) * u + (c - a) * v;
            bool interieur = DansChateau(p);
            if (!Apparition(p)) continue;
            if (interieur ? interieurs >= maxInterieurs : exterieurs >= TaillePool - maxInterieurs) continue;
            if (!NavMesh.SamplePosition(p, out var h, .5f, NavMesh.AllAreas)) continue;
            if (NavMesh.FindClosestEdge(h.position, out var bord, NavMesh.AllAreas) && bord.distance < .5f) continue;
            if (Physics.CheckCapsule(h.position + Vector3.up * .5f, h.position + Vector3.up * 1.6f, .3f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) continue;
            if (!NavMesh.CalculatePath(reference.position, h.position, NavMesh.AllAreas, chemin) || chemin.status != NavMeshPathStatus.PathComplete) continue;
            reserve.Add(h.position);
            if (interieur) interieurs++; else exterieurs++;
        }
        return reserve;
    }

    public static bool DansChateau(Vector3 p) => Mathf.Abs(p.x) < 18 && p.z > -10 && p.z < 12;

    // Limite de la propriété (travail/plan_domaine.json, repère D-003 : x est, y sud).
    static readonly Vector2[] Limite = {
        new(-33.4f, -29.1f), new(-15.3f, -30.0f), new(11.9f, -31.5f), new(24.0f, -33.5f), new(33.5f, -26.0f), new(37.5f, -6.5f), new(41.0f, 12.0f),
        new(46.0f, 24.0f), new(58.4f, 38.4f), new(72.0f, 61.1f), new(92.1f, 73.2f), new(108.6f, 86.8f), new(116.9f, 96.9f), new(121.5f, 104.0f),
        new(121.5f, 118.0f), new(113.4f, 126.8f), new(100.7f, 139.6f), new(81.9f, 142.8f), new(65.8f, 142.7f), new(53.8f, 141.4f), new(41.9f, 141.1f),
        new(23.8f, 131.8f), new(21.0f, 127.0f), new(16.0f, 121.0f), new(15.0f, 113.0f), new(12.0f, 108.5f), new(2.5f, 107.4f), new(-8.5f, 107.4f),
        new(-19.5f, 105.9f), new(-25.2f, 99.7f), new(-30.2f, 91.1f), new(-33.6f, 76.4f), new(-35.4f, 37.6f), new(-39.6f, -13.0f), new(-39.8f, -22.2f) };

    // Point (Unity) dans la propriété, à plus de « marge » mètres de la limite.
    public static bool DansDomaine(Vector3 p, float marge = 2f)
    {
        var q = new Vector2(-p.x, p.z); bool dedans = false; float d2 = float.MaxValue;
        for (int i = 0, j = Limite.Length - 1; i < Limite.Length; j = i++)
        {
            Vector2 a = Limite[i], b = Limite[j];
            if ((a.y > q.y) != (b.y > q.y) && q.x < (b.x - a.x) * (q.y - a.y) / (b.y - a.y) + a.x) dedans = !dedans;
            Vector2 ab = b - a; float t = Mathf.Clamp01(Vector2.Dot(q - a, ab) / Mathf.Max(1e-6f, ab.sqrMagnitude));
            d2 = Mathf.Min(d2, (a + ab * t - q).sqrMagnitude);
        }
        return dedans && d2 > marge * marge;
    }

    // Combles et toit exclus : on n'en sort que par l'échelle de la trappe.
    public static bool Apparition(Vector3 p) => DansDomaine(p) && p.y < 8f;

    // Liste de points bien répartis (le plus éloigné des précédents à chaque fois) pour le message
    // demarrer du serveur en ligne : [x, y, z, lacet].
    public static List<float[]> PointsApparition(int nombre)
    {
        var pool = Reserve(); var choisis = new List<Vector3>(); var liste = new List<float[]>();
        if (pool.Count == 0) return liste;
        choisis.Add(pool[0]);
        while (choisis.Count < Mathf.Min(nombre, pool.Count))
        {
            Vector3 loin = pool[0]; float max = -1;
            foreach (var p in pool)
            {
                float d = float.MaxValue; foreach (var q in choisis) d = Mathf.Min(d, Vector3.Distance(p, q));
                if (d > max) { max = d; loin = p; }
            }
            choisis.Add(loin);
        }
        foreach (var p in choisis) liste.Add(new[] { Mathf.Round(p.x * 100) / 100, Mathf.Round(p.y * 100) / 100, Mathf.Round(p.z * 100) / 100, Random.Range(0, 360) });
        return liste;
    }

    public void Arreter()
    {
        EffacerTaches(); CorpsTombe.ToutEffacer();
        foreach (var b in bots) if (b != null) Destroy(b.gameObject);
        bots.Clear(); Match = null; DegatsRecus = 0; DepuisTouche = 99; EnLigne = false;
    }

    // ---------- Partie en ligne : le serveur décide, cet hôte applique ----------
    public bool EnLigne { get; private set; }

    public void DemarrerEnLigne(JoueurServeur[] salon, JoueurServeur[] placements, int cible, int vies)
    {
        Arreter();
        EnLigne = true;
        foreach (var porte in FindObjectsByType<Porte>(FindObjectsSortMode.None)) if (!porte.Ouverte) porte.Basculer(porte.transform.position + porte.transform.forward);
        Match = new MatchPaintball(new ReglesMatch { vies = vies, dureeMax = 0, victoireAuxPoints = false, dernierSurvivantGagne = false });
        Match.Evenement += Appliquer;
        foreach (var p in placements)
        {
            var info = System.Array.Find(salon, s => s.j == p.j);
            string nom = info != null && !string.IsNullOrEmpty(info.nom) ? info.nom : "Joueur " + (p.j + 1);
            int couleur = info != null ? Mathf.Clamp(info.c, 0, PaintballSolo.Couleurs.Length - 1) : p.j % PaintballSolo.Couleurs.Length;
            if (p.j == partie.JoueurId) { Match.Ajouter(p.j, "Vous", partie.CouleurIndex, false); continue; }
            var avatar = BotPaintball.CreerDistant(partie, this, p.j, nom, couleur);
            bots.Add(avatar);
            Match.Ajouter(p.j, nom, couleur, false);
        }
        Match.DemarrerMiroir(cible);
        foreach (var p in placements)
            if (p.spawn != null && p.spawn.Length >= 4) Placer(p.j, new Vector3(p.spawn[0], p.spawn[1], p.spawn[2]), p.spawn[3]);
        Change?.Invoke();
    }

    public void AnimerTir(int id) { foreach (var b in bots) if (b.Id == id) b.AnimerTir(); }

    public void EtatServeur(JoueurServeur[] joueurs)
    {
        if (Match == null || joueurs == null) return;
        foreach (var x in joueurs)
        {
            var j = Match.Joueur(x.j); if (j == null) continue;
            j.vies = x.vies; j.points = x.points;
            if (x.elimine && !j.elimine) Match.ImposerElimination(x.j);
        }
        Change?.Invoke();
    }

    public void PoseDistante(int id, long h, Vector3 position, float[] regard, float[] vitesse)
    {
        foreach (var b in bots) if (b.Id == id) b.Pose(h, position, regard != null && regard.Length > 0 ? regard[0] : 0,
            vitesse != null && vitesse.Length == 3 ? new Vector3(vitesse[0], vitesse[1], vitesse[2]) : Vector3.zero);
    }

    public void EntreeServeur(int id, string nom, int couleur, float[] spawn, int cible)
    {
        if (Match == null || Match.Joueur(id) != null) return;
        couleur = Mathf.Clamp(couleur, 0, PaintballSolo.Couleurs.Length - 1);
        var avatar = BotPaintball.CreerDistant(partie, this, id, nom, couleur);
        bots.Add(avatar);
        Match.Ajouter(id, nom, couleur, false);
        Match.ImposerCible(cible);
        if (spawn != null && spawn.Length >= 4) Placer(id, new Vector3(spawn[0], spawn[1], spawn[2]), spawn[3]);
        Change?.Invoke();
    }

    public void ToucheServeur(int tireur, int cible, int vies, int points, bool elimine, float[] spawn, float[] pt, float[] origine)
    {
        if (Match == null) return;
        bool moiTouche = cible == partie.JoueurId;
        var corps = Corps(cible, tireur);
        if (pt != null && pt.Length == 3)
        {
            var t = CalculerTache(cible, tireur, new Vector3(pt[0], pt[1], pt[2]));
            if (t.HasValue) { AjouterTache(cible, t.Value); if (corps != null) PoserTache(corps.gameObject, TacheCorps(t.Value), partie.impacts); }
        }
        if (!elimine && spawn != null && spawn.Length >= 4) Placer(cible, new Vector3(spawn[0], spawn[1], spawn[2]), spawn[3]);
        if (moiTouche) ObjetsDomaine.Transferer(cible, tireur, Match.Joueur(tireur)?.nom ?? "");
        Match.ImposerTouche(tireur, cible, vies, points, elimine);
        // D'où : l'origine du tir donnée par le serveur, plus juste que la position affichée du tireur.
        if (moiTouche && origine != null && origine.Length == 3) OrigineTouche = new Vector3(origine[0], origine[1], origine[2]);
    }

    void Placer(int id, Vector3 p, float lacet)
    {
        dernieres[id] = p;
        var rotation = Quaternion.Euler(0, lacet, 0);
        if (id == partie.JoueurId)
        {
            explorateur.Descendre(); controleur.enabled = false; transform.SetPositionAndRotation(p + Vector3.up * .08f, rotation);
            explorateur.ReinitialiserRegard(); explorateur.Relever(); controleur.enabled = true; Physics.SyncTransforms();
            return;
        }
        foreach (var b in bots) if (b.Id == id) b.Reapparaitre(p, rotation);
    }

    void Update()
    {
        if (Match == null || partie.EnPause && !EnLigne) return;
        Match.Avancer(Time.deltaTime);
        DegatsRecus = Mathf.Max(0, DegatsRecus - Time.deltaTime);
        DepuisTouche += Time.deltaTime;
    }

    public Vector3 Position(int id)
    {
        if (id == partie.JoueurId) return transform.position;
        foreach (var b in bots) if (b.Id == id) return b.transform.position;
        return Vector3.zero;
    }

    public Vector3 Vitesse(int id)
    {
        if (id == partie.JoueurId) return controleur.velocity;
        foreach (var b in bots) if (b.Id == id) return b.Vitesse;
        return Vector3.zero;
    }

    // Hauteur du torse visé par les bots : plus bas quand le joueur local est accroupi.
    public float HauteurTorse(int id) => id == partie.JoueurId ? Torse - Explorateur.BaisseYeux * .7f * explorateur.Accroupissement : Torse;

    public bool Actif(int id) { var j = Match?.Joueur(id); return j != null && !j.elimine && !Match.Termine; }

    // Segment d'une bille contre les corps (capsules verticales) des joueurs touchables.
    public bool Tester(Vector3 a, Vector3 b, int tireur, out int touche, out float distance, out Vector3 point)
    {
        touche = -1; distance = float.MaxValue; point = default;
        if (Match == null || Match.Termine) return false;
        float rayon = RayonCorps + BalistiquePaintball.Diametre * .5f;
        foreach (var j in Match.joueurs)
        {
            if (j.id == tireur || j.elimine) continue;
            Vector3 pieds = Position(j.id);
            // Joueur local accroupi : corps plus bas (les bots ne s'accroupissent pas).
            float haut = j.id == partie.JoueurId ? HautCorps - Explorateur.BaisseYeux * explorateur.Accroupissement : HautCorps;
            if (!Segments(a, b, pieds + Vector3.up * BasCorps, pieds + Vector3.up * haut, out float s, out Vector3 p, out float d) || d > rayon) continue;
            float l = Vector3.Distance(a, b) * s;
            if (l < distance) { distance = l; touche = j.id; point = p; }
        }
        return touche >= 0;
    }

    // Points les plus proches entre [p1,q1] et [p2,q2] ; s : paramètre sur le premier segment.
    static bool Segments(Vector3 p1, Vector3 q1, Vector3 p2, Vector3 q2, out float s, out Vector3 point, out float distance)
    {
        Vector3 d1 = q1 - p1, d2 = q2 - p2, r = p1 - p2;
        float a = Vector3.Dot(d1, d1), e = Vector3.Dot(d2, d2), f = Vector3.Dot(d2, r);
        float c = Vector3.Dot(d1, r), b = Vector3.Dot(d1, d2), den = a * e - b * b;
        s = den > 1e-8f ? Mathf.Clamp01((b * f - c * e) / den) : 0;
        float t = (b * s + f) / e;
        if (t < 0) { t = 0; s = Mathf.Clamp01(-c / a); } else if (t > 1) { t = 1; s = Mathf.Clamp01((b - c) / a); }
        point = p1 + d1 * s;
        distance = Vector3.Distance(point, p2 + d2 * t);
        return a > 1e-10f;
    }

    public void Touche(int tireur, int touche, Vector3 point)
    {
        if (Match == null) return;
        var tache = CalculerTache(touche, tireur, point);
        // Gilet pare-balles ramassé : la bille tache le joueur sans lui coûter de vie.
        if (touche == partie.JoueurId && ObjetsDomaine.Encaisser()) { if (tache.HasValue) AjouterTache(touche, tache.Value); return; }
        // Corps qui tombe, copié avant la réapparition du joueur touché.
        var corps = Corps(touche, tireur);
        if (Match.Toucher(tireur, touche, ChoisirReapparition(touche)))
        {
            ObjetsDomaine.Transferer(touche, tireur, Match.Joueur(tireur)?.nom ?? "");
            if (tache.HasValue) { AjouterTache(touche, tache.Value); if (corps != null) PoserTache(corps.gameObject, TacheCorps(tache.Value), partie.impacts); }
        }
        else if (corps != null) Destroy(corps.gameObject);
    }

    // Sur le corps qui tombe, la tache de la touche est agrandie pour bien se voir avant la chute.
    static Tache TacheCorps(Tache t) { t.taille *= 1.6f; return t; }

    // Les adversaires touchés tombent (pas le joueur local : il voit le voile de touche).
    CorpsTombe Corps(int touche, int tireur) => touche == partie.JoueurId ? null : CorpsTombe.Creer(Robot(touche), Position(tireur));

    // ---------- Taches de peinture sur les corps ----------
    // Chaque touche laisse une tache de la couleur du tireur, accrochée à l'os du robot le plus proche
    // de l'impact (elle suit l'animation) et gardée jusqu'à la fin de la partie, pour le podium aussi.
    // os : indice dans SkinnedMeshRenderer.bones (même squelette pour tous les robots, clones du même modèle).
    public struct Tache { public int couleur, maillage, os; public Vector3 local; public Quaternion rotation; public float taille; }
    public readonly Dictionary<int, List<Tache>> taches = new();
    public static int TachesEnregistrees, TachesPosees, SurfacesTrouvees;

    public GameObject Robot(int id)
    {
        if (id == partie.JoueurId) return partie.personnage;
        foreach (var b in bots) if (b.Id == id) return b.Robot;
        return null;
    }

    // Point d'impact ramené sur le corps : hauteur et côté de l'impact par rapport aux pieds du joueur
    // touché (tel qu'il est affiché ici), puis à la surface autour de l'os le plus proche.
    Tache? CalculerTache(int id, int tireur, Vector3 point)
    {
        var robot = Robot(id); var j = Match?.Joueur(tireur);
        if (robot == null) return null;
        Vector3 pieds = Position(id);
        float h = Mathf.Clamp(point.y - pieds.y, .2f, PaintballSolo.Taille * PaintballSolo.Echelle - .12f);
        Vector3 cote = point - pieds; cote.y = 0;
        if (cote.sqrMagnitude < 1e-4f) cote = Position(tireur) - pieds; cote.y = 0;
        if (cote.sqrMagnitude < 1e-4f) cote = robot.transform.forward;
        cote.Normalize();
        // Surface réelle du corps : rayon venu de l'extérieur, du côté de l'impact, contre le maillage du robot
        // fige dans sa pose actuelle.
        Vector3 axe = pieds + Vector3.up * h;
        Vector3 surface = axe + cote * .12f, normale = cote;
        if (Surface(robot, axe + cote * 1.5f, -cote, out var touche)) { surface = touche.point; normale = touche.normal; SurfacesTrouvees++; }
        if (!OsProche(robot, surface, out int maillage, out int indice)) return null;
        var os = robot.GetComponentsInChildren<SkinnedMeshRenderer>(true)[maillage].bones[indice];
        return new Tache
        {
            couleur = j != null ? j.couleur : 0, maillage = maillage, os = indice, local = os.InverseTransformPoint(surface + normale * .008f),
            rotation = Quaternion.Inverse(os.rotation) * Quaternion.LookRotation(-normale, Vector3.up), taille = Random.Range(.2f, .26f)
        };
    }

    static readonly List<Vector3> sommets = new(), normales = new();
    // Premier point du maillage (figé dans sa pose) rencontré le long du rayon : sommet à moins de 12 cm de
    // la droite, le plus près de l'origine. Pas de collider : rien n'est ajouté à la physique.
    static bool Surface(GameObject robot, Vector3 origine, Vector3 direction, out RaycastHit meilleur)
    {
        meilleur = default; bool trouve = false; float tMin = float.MaxValue;
        // Le robot est fait surtout de pièces rigides (torse, tête, membres) et de deux mains skinnées ;
        // le robot du joueur est inactif en vue subjective : chercher aussi parmi les objets inactifs.
        var pieces = new List<(Mesh mesh, Matrix4x4 repere)>(); var cuits = new List<Mesh>();
        foreach (var f in robot.GetComponentsInChildren<MeshFilter>(true))
        {
            if (f.sharedMesh == null || f.name == "TacheCorps" || f.name != "Torso" && f.name != "Head" && !f.name.StartsWith("Arm") && !f.name.StartsWith("Leg")
                && !f.name.StartsWith("LowerLeg") && !f.name.StartsWith("Foot") && !f.name.StartsWith("Shoulder")) continue;
            if (f.sharedMesh.isReadable) { pieces.Add((f.sharedMesh, f.transform.localToWorldMatrix)); continue; }
            // Maillage non lisible dans le build : la boîte englobante de la pièce sert de surface.
            var l2w = f.transform.localToWorldMatrix; var w2l = l2w.inverse;
            var rayon = new Ray(w2l.MultiplyPoint3x4(origine), w2l.MultiplyVector(direction));
            if (!f.sharedMesh.bounds.IntersectRay(rayon, out float dl)) continue;
            Vector3 pw = l2w.MultiplyPoint3x4(rayon.GetPoint(dl)); float tw = Vector3.Dot(pw - origine, direction);
            if (tw <= 0 || tw >= tMin) continue;
            tMin = tw; trouve = true; meilleur.point = pw; meilleur.normal = -direction;
        }
        foreach (var s in robot.GetComponentsInChildren<SkinnedMeshRenderer>(true))
        {
            var m = new Mesh(); s.BakeMesh(m, true); cuits.Add(m);
            pieces.Add((m, Matrix4x4.TRS(s.transform.position, s.transform.rotation, Vector3.one)));
        }
        foreach (var (mesh, repere) in pieces)
        {
            mesh.GetVertices(sommets); mesh.GetNormals(normales);
            for (int i = 0; i < sommets.Count; i++)
            {
                Vector3 p = repere.MultiplyPoint3x4(sommets[i]);
                float t = Vector3.Dot(p - origine, direction);
                if (t <= 0 || t >= tMin) continue;
                if ((origine + direction * t - p).sqrMagnitude > .12f * .12f) continue;
                tMin = t; trouve = true;
                meilleur.point = p;
                meilleur.normal = i < normales.Count ? repere.MultiplyVector(normales[i]).normalized : -direction;
            }
        }
        foreach (var m in cuits) Destroy(m);
        return trouve;
    }

    static bool OsProche(GameObject robot, Vector3 p, out int maillage, out int indice)
    {
        maillage = indice = -1; float d = float.MaxValue;
        var rendus = robot.GetComponentsInChildren<SkinnedMeshRenderer>(true);
        for (int m = 0; m < rendus.Length; m++)
            for (int i = 0; i < rendus[m].bones.Length; i++)
            {
                var os = rendus[m].bones[i]; if (os == null) continue;
                float e = (os.position - p).sqrMagnitude;
                if (e < d) { d = e; maillage = m; indice = i; }
            }
        return maillage >= 0;
    }

    void AjouterTache(int id, Tache t)
    {
        if (!taches.TryGetValue(id, out var liste)) taches[id] = liste = new List<Tache>();
        liste.Add(t); TachesEnregistrees++;
        var robot = Robot(id); if (robot != null) PoserTache(robot, t, partie.impacts);
    }

    public static void PoserTache(GameObject robot, Tache t, ImpactsPaintball impacts)
    {
        var rendus = robot.GetComponentsInChildren<SkinnedMeshRenderer>(true);
        if (impacts == null || t.maillage >= rendus.Length || t.os >= rendus[t.maillage].bones.Length) return;
        var os = rendus[t.maillage].bones[t.os];
        if (os == null) return;
        var q = GameObject.CreatePrimitive(PrimitiveType.Quad); q.name = "TacheCorps"; q.layer = 2;
        Object.Destroy(q.GetComponent<Collider>());
        q.transform.SetParent(os, false); TachesPosees++;
        q.transform.localPosition = t.local; q.transform.localRotation = t.rotation * Quaternion.Euler(0, 0, Random.Range(0, 360));
        // Taille voulue dans le monde, quelle que soit l'échelle (parfois très grande) des os du squelette.
        Vector3 e = os.lossyScale;
        q.transform.localScale = new Vector3(t.taille / Mathf.Max(1e-5f, Mathf.Abs(e.x)), t.taille / Mathf.Max(1e-5f, Mathf.Abs(e.y)), t.taille / Mathf.Max(1e-5f, Mathf.Abs(e.z)));
        var r = q.GetComponent<Renderer>(); r.sharedMaterial = impacts.Materiau(PaintballSolo.Couleurs[Mathf.Clamp(t.couleur, 0, PaintballSolo.Couleurs.Length - 1)]);
        r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.receiveShadows = false;
    }

    // Nouvelle partie : plus aucune tache (le robot du joueur est conservé d'une partie à l'autre).
    void EffacerTaches()
    {
        taches.Clear();
        if (partie.personnage == null) return;
        foreach (var x in partie.personnage.GetComponentsInChildren<Transform>(true)) if (x.name == "TacheCorps") Destroy(x.gameObject);
    }

    // Réapparition vraiment au hasard dans la réserve : à plus de 8 m des adversaires en vie (comme le
    // serveur) et à plus de 12 m du lieu de la mort ; hors de leur vue si possible.
    int ChoisirReapparition(int id)
    {
        Vector3 ici = Position(id); int repli = -1;
        for (int essai = 0; essai < 60; essai++)
        {
            int i = Random.Range(0, pointsSurs.Count); Vector3 p = pointsSurs[i];
            if (Vector3.Distance(p, ici) < 12 || dernieres.TryGetValue(id, out var avant) && Vector3.Distance(p, avant) < 12) continue;
            bool loin = true, cache = true;
            foreach (var j in Match.joueurs)
            {
                if (j.id == id || j.elimine) continue;
                Vector3 a = Position(j.id);
                if (Vector3.Distance(a, p) < 8) { loin = false; break; }
                if (Physics.Linecast(a + Vector3.up * 1.5f, p + Vector3.up * 1.2f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) == false) cache = false;
            }
            if (!loin) continue;
            if (cache) return i;
            if (repli < 0) repli = i;
        }
        return repli >= 0 ? repli : Random.Range(0, pointsSurs.Count);
    }

    void Appliquer(EvenementMatch e)
    {
        switch (e.type)
        {
            case TypeEvenementMatch.Touche:
                DerniereTouche = e.joueur;
                if (e.joueur == partie.JoueurId) { DegatsRecus = 1; DernierTireur = e.auteur; OrigineTouche = Position(e.auteur); DepuisTouche = 0;
                    Vector3 ecart = OrigineTouche - transform.position; ecart.y = 0; DistanceTouche = ecart.magnitude; }
                else if (e.auteur == partie.JoueurId) partie.AdversaireTouche();
                foreach (var b in bots) if (b.Id == e.joueur) b.Touche(Position(e.auteur));
                break;
            case TypeEvenementMatch.Reapparition: Teleporter(e.joueur, e.point); break;
            case TypeEvenementMatch.Elimination:
                foreach (var b in bots) if (b.Id == e.joueur) b.Eliminer();
                if (e.joueur == partie.JoueurId) partie.FinMatch();
                break;
            case TypeEvenementMatch.Fin: partie.FinMatch(); break;
        }
        Change?.Invoke();
    }

    void Teleporter(int id, int point)
    {
        if (point < 0 || point >= pointsSurs.Count) return;
        Vector3 p = pointsSurs[point];
        dernieres[id] = p;
        var rotation = Quaternion.Euler(0, Random.Range(0f, 360f), 0);
        if (id == partie.JoueurId)
        {
            explorateur.Descendre(); controleur.enabled = false; transform.SetPositionAndRotation(p + Vector3.up * .08f, rotation);
            explorateur.ReinitialiserRegard(); explorateur.Relever(); controleur.enabled = true; Physics.SyncTransforms();
            return;
        }
        foreach (var b in bots) if (b.Id == id) b.Reapparaitre(p, rotation);
    }

    // Peinture principale du robot : matériau glTF « Main », renommé par la préparation web
    // (TexturesWeb) ; reconnu aussi à sa couleur d'origine (0,59 ; 0,29 ; 0,04).
    static readonly Color OrangeRobot = new(.590f, .291f, .038f);
    static bool Principal(Material m)
    {
        if (m.name.StartsWith("Main")) return true;
        Color c = m.HasProperty("baseColorFactor") ? m.GetColor("baseColorFactor") : m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor") : Color.black;
        Color g = OrangeRobot.gamma;
        return Mathf.Abs(c.r - OrangeRobot.r) + Mathf.Abs(c.g - OrangeRobot.g) + Mathf.Abs(c.b - OrangeRobot.b) < .06f
            || Mathf.Abs(c.r - g.r) + Mathf.Abs(c.g - g.g) + Mathf.Abs(c.b - g.b) < .06f;
    }

    // Teinte la peinture principale d'un robot RobotExpressive (matériau « Main »).
    // reutiliser : garder l'instance teinte d'une partie précédente (robot du joueur) ; sinon matériaux
    // neufs, renvoyés pour être détruits avec le robot.
    public static List<Material> Teinter(GameObject robot, Color couleur, bool reutiliser)
    {
        var crees = new List<Material>();
        foreach (var r in robot.GetComponentsInChildren<Renderer>(true))
        {
            var mats = r.sharedMaterials; bool change = false;
            for (int i = 0; i < mats.Length; i++)
            {
                if (mats[i] == null || !Principal(mats[i])) continue;
                // Matériau déjà teint à une partie précédente : le réutiliser.
                bool deja = reutiliser && mats[i].name == "Main (teinte)";
                var m = deja ? mats[i] : new Material(mats[i]) { name = "Main (teinte)" };
                if (!deja) crees.Add(m);
                var c = Color.Lerp(couleur, Color.white, .08f);
                if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
                if (m.HasProperty("baseColorFactor")) m.SetColor("baseColorFactor", c);
                if (m.HasProperty("_Color")) m.SetColor("_Color", c);
                mats[i] = m; change = true;
            }
            if (change) r.sharedMaterials = mats;
        }
        return crees;
    }

    void OnDestroy() { if (Instance == this) Instance = null; }
}

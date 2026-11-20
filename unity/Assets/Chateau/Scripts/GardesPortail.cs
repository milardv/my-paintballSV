using UnityEngine;

// Portail d'entrée du domaine : à chaque arrivée ou départ du joueur, les deux soldats sortent de la maison du
// gardien, se postent de part et d'autre du portail, qui s'ouvre ; quand le joueur s'éloigne, le portail se
// referme et les soldats rentrent. Décor seulement : pas de collision, rien sur le NavMesh.
public class GardesPortail : MonoBehaviour
{
    const float DistanceAppel = 14f, DistanceFin = 22f, Vitesse = 1.6f, AngleVantail = 95f, AnglePorte = 100f;
    static readonly int VitesseAnimation = Animator.StringToHash("Vitesse"), SolAnimation = Animator.StringToHash("AuSol");

    enum Etat { Repos, Sortie, Garde, Retour }
    Etat etat = Etat.Repos;
    Transform joueur, porte;
    readonly Transform[] vantaux = new Transform[2], soldats = new Transform[2];
    readonly Animator[] animateurs = new Animator[2];
    readonly Quaternion[] fermes = new Quaternion[2];
    readonly float[] signes = new float[2];
    Quaternion porteFermee;
    float signePorte, ouvertureVantaux, ouverturePorte;
    Vector3 centre, dedans, dehors, seuilInterieur, seuilExterieur;
    readonly Vector3[] postes = new Vector3[2];
    readonly int[] etapes = new int[2];
    readonly float[] departs = new float[2];
    float horloge;

    public static void Installer(GameObject robot, Transform joueur)
    {
        var g = GameObject.Find("parc_portail_vantail_g"); var d = GameObject.Find("parc_portail_vantail_d");
        var porte = GameObject.Find("parc_maison_gardien_porte"); var maison = GameObject.Find("parc_maison_gardien");
        if (robot == null || joueur == null || g == null || d == null || porte == null || maison == null) return;
        var go = new GameObject("GardesPortail");
        var gp = go.AddComponent<GardesPortail>();
        gp.joueur = joueur; gp.porte = porte.transform;
        gp.vantaux[0] = g.transform; gp.vantaux[1] = d.transform;
        Vector3 cMaison = Centre(maison);
        gp.centre = (g.transform.position + d.transform.position) * .5f;
        Vector3 ligne = d.transform.position - g.transform.position; ligne.y = 0; float demi = ligne.magnitude * .5f; ligne.Normalize();
        Vector3 n = Vector3.Cross(Vector3.up, ligne); Vector3 versMaison = cMaison - gp.centre; versMaison.y = 0;
        gp.dedans = Vector3.Dot(n, versMaison) > 0 ? n : -n; gp.dehors = -gp.dedans;
        for (int i = 0; i < 2; i++)
        {
            gp.fermes[i] = gp.vantaux[i].rotation;
            gp.signes[i] = SensOuverture(gp.vantaux[i], gp.centre + gp.dedans * 2f);
            gp.postes[i] = Sol(gp.centre + ligne * (i == 0 ? -1 : 1) * (demi + 1.1f) + gp.dedans * 1.8f);
        }
        gp.porteFermee = porte.transform.rotation;
        gp.signePorte = SensOuverture(porte.transform, cMaison);
        // Seuils de la porte : 1,2 m à l'intérieur et à l'extérieur, au milieu du vantail.
        Vector3 milieu = Centre(porte); Vector3 sortie = milieu - cMaison; sortie.y = 0;
        Vector3 axePorte = porte.transform.right; axePorte.y = 0; axePorte.Normalize();
        Vector3 normale = Vector3.Cross(Vector3.up, axePorte); if (Vector3.Dot(normale, sortie) < 0) normale = -normale;
        gp.seuilInterieur = Sol(milieu - normale * 1.2f); gp.seuilExterieur = Sol(milieu + normale * 1.2f);
        Color kaki = new(.26f, .3f, .18f);
        for (int i = 0; i < 2; i++)
        {
            var racine = new GameObject("Soldat" + (i + 1)); racine.transform.SetParent(go.transform, false);
            var s = Instantiate(robot, racine.transform, false); s.name = "Robot"; s.SetActive(true);
            s.transform.localPosition = new Vector3(0, robot.transform.localPosition.y, 0); s.transform.localRotation = Quaternion.identity;
            foreach (var c in s.GetComponentsInChildren<Collider>()) Destroy(c);
            PartieBots.Teinter(s, kaki, false);
            Kepi(s.transform);
            gp.soldats[i] = racine.transform; gp.animateurs[i] = s.GetComponentInChildren<Animator>();
            racine.transform.position = gp.seuilInterieur; racine.SetActive(false);
        }
    }

    static Vector3 Centre(GameObject o)
    {
        var rs = o.GetComponentsInChildren<Renderer>(); if (rs.Length == 0) return o.transform.position;
        Bounds b = rs[0].bounds; foreach (var r in rs) b.Encapsulate(r.bounds); return b.center;
    }

    // Signe de rotation (autour de la verticale, au gond) qui rapproche le battant du point visé.
    static float SensOuverture(Transform t, Vector3 vise)
    {
        Vector3 bout = Centre(t.gameObject) - t.position;
        Vector3 a = Quaternion.AngleAxis(60, Vector3.up) * bout, b = Quaternion.AngleAxis(-60, Vector3.up) * bout;
        return (t.position + a - vise).sqrMagnitude < (t.position + b - vise).sqrMagnitude ? 1f : -1f;
    }

    // Point du sol (terrain, allée, dalle) sous p : le plus haut impact parmi les décors du parc hors haies.
    static Vector3 Sol(Vector3 p)
    {
        bool trouve = false; float y = p.y;
        foreach (var h in Physics.RaycastAll(p + Vector3.up * 4f, Vector3.down, 14f, ~0, QueryTriggerInteraction.Ignore))
            if (h.collider.name.StartsWith("parc_") && !h.collider.name.Contains("haie") && !h.collider.name.Contains("portail")
                && (!trouve || h.point.y > y)) { y = h.point.y; trouve = true; }
        p.y = y; return p;
    }

    // Képi : bandeau et calot sombres, visière noire, posés sur la tête du robot.
    public static Transform Kepi(Transform robot)
    {
        Transform tete = null;
        foreach (var t in robot.GetComponentsInChildren<Transform>()) if (t.name == "Head") { tete = t; break; }
        var k = new GameObject("Kepi").transform;
        var lit = Shader.Find("Universal Render Pipeline/Lit");
        var drap = new Material(lit); drap.SetColor("_BaseColor", new Color(.12f, .14f, .1f));
        var noir = new Material(lit); noir.SetColor("_BaseColor", new Color(.03f, .03f, .03f)); noir.SetFloat("_Smoothness", .7f);
        void Piece(PrimitiveType type, Vector3 position, Vector3 echelle, Material m)
        {
            var p = GameObject.CreatePrimitive(type); Destroy(p.GetComponent<Collider>());
            p.transform.SetParent(k, false); p.transform.localPosition = position; p.transform.localScale = echelle;
            p.GetComponent<Renderer>().sharedMaterial = m;
        }
        Piece(PrimitiveType.Cylinder, new Vector3(0, .1f, 0), new Vector3(.34f, .1f, .34f), drap);
        Piece(PrimitiveType.Cylinder, new Vector3(0, .21f, 0), new Vector3(.3f, .01f, .3f), noir);
        Piece(PrimitiveType.Cube, new Vector3(0, .02f, .17f), new Vector3(.24f, .02f, .12f), noir);
        if (tete != null) { k.SetParent(tete, false); float e = 1f / Mathf.Max(.01f, tete.lossyScale.y); k.localScale = Vector3.one * e; k.localPosition = new Vector3(0, .32f * e, 0); }
        else { k.SetParent(robot, false); k.localPosition = new Vector3(0, 1.75f, 0); }
        return k;
    }

    void Update()
    {
        if (joueur == null) return;
        horloge += Time.deltaTime;
        Vector3 dj = joueur.position - centre; dj.y = 0; float dist = dj.magnitude;
        switch (etat)
        {
            case Etat.Repos:
                if (dist < DistanceAppel) Sortir();
                break;
            case Etat.Sortie:
                ouverturePorte = Mathf.MoveTowards(ouverturePorte, 1f, Time.deltaTime * 1.5f);
                bool arrives = true;
                for (int i = 0; i < 2; i++) arrives &= Marcher(i, horloge > departs[i], new[] { seuilInterieur, seuilExterieur, postes[i] }, dehors);
                if (arrives) etat = Etat.Garde;
                break;
            case Etat.Garde:
                ouverturePorte = Mathf.MoveTowards(ouverturePorte, 0f, Time.deltaTime);
                ouvertureVantaux = Mathf.MoveTowards(ouvertureVantaux, 1f, Time.deltaTime * .45f);
                for (int i = 0; i < 2; i++) Immobile(i, dehors);
                if (dist > DistanceFin) Rentrer();
                break;
            case Etat.Retour:
                ouvertureVantaux = Mathf.MoveTowards(ouvertureVantaux, 0f, Time.deltaTime * .45f);
                if (ouvertureVantaux > .01f) { for (int i = 0; i < 2; i++) Immobile(i, dehors); break; }
                ouverturePorte = Mathf.MoveTowards(ouverturePorte, 1f, Time.deltaTime * 1.5f);
                bool rentres = true;
                for (int i = 0; i < 2; i++) rentres &= Marcher(i, horloge > departs[i], new[] { postes[i], seuilExterieur, seuilInterieur }, -dehors);
                if (dist < DistanceAppel) { Sortir(); break; }
                if (rentres)
                {
                    ouverturePorte = Mathf.MoveTowards(ouverturePorte, 0f, Time.deltaTime * 1.5f);
                    for (int i = 0; i < 2; i++) soldats[i].gameObject.SetActive(false);
                    if (ouverturePorte <= 0f) etat = Etat.Repos;
                }
                break;
        }
        float lisse = Mathf.SmoothStep(0, 1, ouvertureVantaux);
        for (int i = 0; i < 2; i++) vantaux[i].rotation = Quaternion.AngleAxis(signes[i] * AngleVantail * lisse, Vector3.up) * fermes[i];
        porte.rotation = Quaternion.AngleAxis(signePorte * AnglePorte * Mathf.SmoothStep(0, 1, ouverturePorte), Vector3.up) * porteFermee;
    }

    void Sortir()
    {
        for (int i = 0; i < 2; i++)
            if (!soldats[i].gameObject.activeSelf) { soldats[i].gameObject.SetActive(true); soldats[i].position = seuilInterieur; etapes[i] = 0; }
            else etapes[i] = 2;                             // demi-tour depuis l'allée : droit vers le poste
        departs[0] = horloge + .5f; departs[1] = horloge + 1.3f;
        etat = Etat.Sortie;
    }

    void Rentrer()
    {
        for (int i = 0; i < 2; i++) etapes[i] = 0;
        departs[0] = horloge + .3f; departs[1] = horloge + .9f;
        etat = Etat.Retour;
    }

    // Avance le soldat i le long des points ; vrai quand il est arrivé au dernier.
    bool Marcher(int i, bool parti, Vector3[] points, Vector3 regardFinal)
    {
        var s = soldats[i];
        if (!parti || !s.gameObject.activeSelf) { Animer(i, 0); return !s.gameObject.activeSelf; }
        while (etapes[i] < points.Length)
        {
            Vector3 cible = points[etapes[i]];
            Vector3 d = cible - s.position; d.y = 0;
            if (d.magnitude < .08f) { etapes[i]++; continue; }
            Vector3 pas = Vector3.ClampMagnitude(d, Vitesse * Time.deltaTime);
            Vector3 p = s.position + pas; p.y = Mathf.Lerp(s.position.y, cible.y, Mathf.Clamp01(pas.magnitude / Mathf.Max(.01f, d.magnitude)));
            s.position = p;
            s.rotation = Quaternion.Slerp(s.rotation, Quaternion.LookRotation(d.normalized), Time.deltaTime * 8f);
            Animer(i, 3.4f);
            return false;
        }
        Immobile(i, regardFinal);
        return true;
    }

    void Immobile(int i, Vector3 regard)
    {
        if (!soldats[i].gameObject.activeSelf) return;
        soldats[i].rotation = Quaternion.Slerp(soldats[i].rotation, Quaternion.LookRotation(regard), Time.deltaTime * 5f);
        Animer(i, 0);
    }

    void Animer(int i, float v)
    {
        if (animateurs[i] == null) return;
        animateurs[i].SetFloat(VitesseAnimation, v, .1f, Time.deltaTime); animateurs[i].SetBool(SolAnimation, true);
    }
}

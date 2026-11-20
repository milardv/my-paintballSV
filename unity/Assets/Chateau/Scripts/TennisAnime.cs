using UnityEngine;

// Deux joueurs de tennis (le robot du jeu, teinté) qui échangent sur le court du parc : la balle suit une
// parabole avec un rebond, le receveur se déplace en fond de court pour la reprendre. Décor seulement :
// pas de collision, pas de touche, rien sur le NavMesh.
public class TennisAnime : MonoBehaviour
{
    const float Rebond = .7f, Duree = 1.35f, HauteurFrappe = .9f;
    static readonly int VitesseAnimation = Animator.StringToHash("Vitesse"), SolAnimation = Animator.StringToHash("AuSol");

    Vector3 centre, axe, cote;
    float sol, demiLongueur, demiLargeur;
    readonly Transform[] joueurs = new Transform[2];
    readonly Animator[] animateurs = new Animator[2];
    readonly Transform[] raquettes = new Transform[2];
    readonly float[] cibles = new float[2], elans = new float[2];
    Transform balle;
    int frappeur;
    float t;
    Vector3 depart, rebond, arrivee;

    public static void Installer(GameObject robot)
    {
        var court = GameObject.Find("parc_tennis_court"); var filet = GameObject.Find("parc_tennis_filet");
        if (robot == null || court == null || filet == null) return;
        var rc = court.GetComponentInChildren<Renderer>(); var rf = filet.GetComponentInChildren<Renderer>();
        if (rc == null || rf == null) return;
        var go = new GameObject("TennisAnime");
        var tennis = go.AddComponent<TennisAnime>();
        Bounds b = rc.bounds;
        bool selonX = b.size.x > b.size.z;
        tennis.axe = selonX ? Vector3.right : Vector3.forward; tennis.cote = selonX ? Vector3.forward : Vector3.right;
        tennis.centre = new Vector3(rf.bounds.center.x, 0, rf.bounds.center.z);
        tennis.sol = b.max.y;
        tennis.demiLongueur = Mathf.Min(11.9f, (selonX ? b.size.x : b.size.z) * .5f - .5f);
        tennis.demiLargeur = Mathf.Min(4.1f, (selonX ? b.size.z : b.size.x) * .5f - .5f);
        Color[] teintes = { new(.95f, .95f, .92f), new(.2f, .45f, .95f) };
        for (int i = 0; i < 2; i++)
        {
            var racine = new GameObject("Joueur" + (i + 1)); racine.transform.SetParent(go.transform, false);
            var j = Instantiate(robot, racine.transform, false); j.name = "Robot"; j.SetActive(true);
            j.transform.localPosition = new Vector3(0, robot.transform.localPosition.y, 0); j.transform.localRotation = Quaternion.identity;
            foreach (var c in j.GetComponentsInChildren<Collider>()) Destroy(c);
            PartieBots.Teinter(j, teintes[i], false);
            tennis.joueurs[i] = racine.transform;
            tennis.animateurs[i] = j.GetComponentInChildren<Animator>();
            tennis.raquettes[i] = Raquette(j.transform);
        }
        var balle = GameObject.CreatePrimitive(PrimitiveType.Sphere); balle.name = "Balle";
        Destroy(balle.GetComponent<Collider>()); balle.transform.SetParent(go.transform, false); balle.transform.localScale = Vector3.one * .09f;
        var mb = new Material(Shader.Find("Universal Render Pipeline/Lit")); mb.SetColor("_BaseColor", new Color(.85f, 1f, .2f));
        balle.GetComponent<Renderer>().sharedMaterial = mb;
        tennis.balle = balle.transform;
        for (int i = 0; i < 2; i++) tennis.Placer(i, 0, 0);
        tennis.Servir(0);
    }

    // Raquette simple (manche, cadre, tamis) tenue par la main droite du robot.
    static Transform Raquette(Transform robot)
    {
        Transform main = null;
        foreach (var t in robot.GetComponentsInChildren<Transform>()) if (t.name == "Hand.R") { main = t; break; }
        var r = new GameObject("Raquette").transform;
        var lit = Shader.Find("Universal Render Pipeline/Lit");
        var cadre = new Material(lit); cadre.SetColor("_BaseColor", new Color(.1f, .1f, .12f));
        var tamis = new Material(lit); tamis.SetColor("_BaseColor", new Color(.9f, .9f, .85f));
        void Piece(PrimitiveType type, Vector3 position, Vector3 echelle, Material m)
        {
            var p = GameObject.CreatePrimitive(type); Destroy(p.GetComponent<Collider>());
            p.transform.SetParent(r, false); p.transform.localPosition = position; p.transform.localScale = echelle;
            var rr = p.GetComponent<Renderer>(); rr.sharedMaterial = m; rr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }
        Piece(PrimitiveType.Cylinder, new Vector3(0, .14f, 0), new Vector3(.03f, .14f, .03f), cadre);
        Piece(PrimitiveType.Sphere, new Vector3(0, .42f, 0), new Vector3(.26f, .3f, .03f), cadre);
        Piece(PrimitiveType.Sphere, new Vector3(0, .42f, 0), new Vector3(.23f, .27f, .035f), tamis);
        if (main != null) { r.SetParent(main, false); float k = 1f / Mathf.Max(.01f, main.lossyScale.y); r.localScale = Vector3.one * k; r.localPosition = Vector3.zero; }
        else { r.SetParent(robot, false); r.localPosition = new Vector3(.35f, .9f, .2f); }
        return r;
    }

    Vector3 Fond(int i, float lateral) => centre + axe * (i == 0 ? -demiLongueur : demiLongueur) + cote * lateral + Vector3.up * sol;

    void Placer(int i, float lateral, float vitesse)
    {
        var p = Fond(i, lateral);
        joueurs[i].SetPositionAndRotation(p, Quaternion.LookRotation(i == 0 ? axe : -axe));
        if (animateurs[i] != null) { animateurs[i].SetFloat(VitesseAnimation, vitesse, .1f, Time.deltaTime); animateurs[i].SetBool(SolAnimation, true); }
    }

    void Servir(int qui)
    {
        frappeur = qui; t = 0; elans[qui] = .3f;
        int receveur = 1 - qui;
        cibles[receveur] = Random.Range(-demiLargeur, demiLargeur);
        depart = joueurs[qui].position + Vector3.up * HauteurFrappe + (qui == 0 ? axe : -axe) * .4f;
        arrivee = Fond(receveur, cibles[receveur]) + Vector3.up * HauteurFrappe - (receveur == 0 ? -axe : axe) * .4f;
        rebond = Vector3.Lerp(depart, arrivee, Rebond); rebond.y = sol + .05f;
    }

    void Update()
    {
        // Loin de la caméra : rien à animer.
        var cam = Camera.main;
        if (cam != null && (cam.transform.position - centre).sqrMagnitude > 160 * 160) return;
        t += Time.deltaTime / Duree;
        Vector3 p;
        if (t < Rebond)
        {
            float k = t / Rebond; p = Vector3.Lerp(depart, rebond, k); p.y = Mathf.Lerp(depart.y, rebond.y, k) + Mathf.Sin(k * Mathf.PI) * 1.6f;
        }
        else
        {
            float k = (t - Rebond) / (1 - Rebond); p = Vector3.Lerp(rebond, arrivee, k); p.y = Mathf.Lerp(rebond.y, arrivee.y, k) + Mathf.Sin(k * Mathf.PI) * .9f;
        }
        balle.position = p;
        for (int i = 0; i < 2; i++)
        {
            Vector3 actuel = joueurs[i].position - centre;
            float lateral = Vector3.Dot(actuel, cote);
            float voulu = i == frappeur ? Mathf.MoveTowards(lateral, 0, 1.5f * Time.deltaTime) : cibles[i];
            float nouveau = Mathf.MoveTowards(lateral, voulu, 4.5f * Time.deltaTime);
            Placer(i, nouveau, Mathf.Abs(nouveau - lateral) / Mathf.Max(.0001f, Time.deltaTime));
            // Coup droit : la raquette pivote un instant à chaque frappe.
            elans[i] = Mathf.Max(0, elans[i] - Time.deltaTime);
            if (raquettes[i] != null) raquettes[i].localRotation = Quaternion.Euler(0, 0, -Mathf.Sin(elans[i] / .3f * Mathf.PI) * 70);
        }
        if (t >= 1) Servir(1 - frappeur);
    }
}

using UnityEngine;
using UnityEngine.AI;

// Adversaire IA : patrouille et chasse sur le NavMesh du parc et de la terrasse, tire de vraies
// billes (PaintballSolo.AjouterBille) visées avec compensation de la chute et une dispersion,
// se met à couvert pour recharger ou après une touche. Visible sous la forme du robot teinté
// portant le marqueur Spyder (AnimationMarqueur).
public class BotPaintball : MonoBehaviour
{
    enum Etat { Chasse, Combat, Couvert, Elimine }
    // Par niveau : temps de réaction (s), dispersion (degrés), rafale, pause entre rafales (s), portée de vue (m).
    static readonly float[] Reactions = { 1.2f, .8f, .45f }, Dispersions = { 5f, 3.2f, 1.8f }, Pauses = { 1.4f, 1f, .6f }, Portees = { 30, 40, 55 };
    static readonly int[] Rafales = { 2, 3, 4 };
    const int Capacite = 20;
    const float Hauteur = PaintballSolo.Yeux - .1f, Cadence = .125f, DureeRecharge = 1.5f;

    public int Id { get; private set; }
    public string Nom { get; private set; }
    public Color Couleur { get; private set; }
    public string EtatTexte => etat.ToString();
    public GameObject Robot { get; private set; }
    public Vector3 Vitesse => distant ? vitesseDistante : agent != null && agent.enabled ? agent.velocity : Vector3.zero;
    // Joueur en ligne : pas d'IA ni de NavMesh, position interpolée d'après les lots du serveur.
    bool distant;
    Vector3 vitesseDistante;
    readonly System.Collections.Generic.List<(double h, Vector3 p, float lacet, Vector3 v)> poses = new();
    const double RetardAffichage = 100;

    PaintballSolo partie;
    PartieBots hote;
    PartieBots.Niveau niveau;
    NavMeshAgent agent;
    Animator animateur;
    AnimationMarqueur pose;
    Transform marqueur, bouche, regard;
    Etat etat;
    int cible = -1, tirsRafale, chargeur = Capacite;
    float vu, prochainePerception, prochainTir, prochaineDestination, recharge = -1, finCouvert;
    Vector3 dernierePosition, pointVise;
    bool cibleVisible;
    System.Collections.Generic.List<Material> teintes;
    static readonly int VitesseAnimation = Animator.StringToHash("Vitesse"), SolAnimation = Animator.StringToHash("AuSol");

    public static BotPaintball Creer(PaintballSolo partie, PartieBots hote, int id, string nom, int couleur, PartieBots.Niveau niveau)
    {
        var go = new GameObject("Bot" + id + "_" + nom); go.layer = 2;
        var bot = go.AddComponent<BotPaintball>();
        bot.partie = partie; bot.hote = hote; bot.Id = id; bot.Nom = nom; bot.niveau = niveau; bot.Couleur = PaintballSolo.Couleurs[couleur];
        var robot = Instantiate(partie.personnage, go.transform, false);
        robot.name = "Robot"; robot.transform.localPosition = new Vector3(0, partie.personnage.transform.localPosition.y, 0);
        // Accessoires ramassés par le joueur (képi, gilet) : pas sur les bots.
        foreach (var t in robot.GetComponentsInChildren<Transform>(true)) if (t.name == "Accessoire") Destroy(t.gameObject);
        robot.transform.localRotation = Quaternion.identity; robot.SetActive(true);
        bot.teintes = PartieBots.Teinter(robot, bot.Couleur, false); bot.Robot = robot;
        bot.animateur = robot.GetComponentInChildren<Animator>();
        bot.animateur.cullingMode = AnimatorCullingMode.CullUpdateTransforms;
        bot.marqueur = Instantiate(partie.marqueur.gameObject, go.transform, false).transform;
        bot.marqueur.gameObject.SetActive(true);
        bot.bouche = bot.marqueur.Find("BoucheCanon");
        bot.regard = new GameObject("Regard").transform; bot.regard.SetParent(go.transform, false); bot.regard.localPosition = Vector3.up * Hauteur;
        // Collision avec le joueur ; hors des balayages des billes (couche Ignore Raycast), testées par capsule.
        var corps = go.AddComponent<CapsuleCollider>(); corps.center = Vector3.up * PaintballSolo.Taille * .5f; corps.height = PaintballSolo.Taille; corps.radius = .3f;
        var rb = go.AddComponent<Rigidbody>(); rb.isKinematic = true;
        bot.agent = go.AddComponent<NavMeshAgent>();
        bot.agent.radius = .3f; bot.agent.height = PaintballSolo.Taille; bot.agent.speed = 3.4f; bot.agent.acceleration = 14; bot.agent.angularSpeed = 540;
        bot.agent.stoppingDistance = .3f; bot.agent.autoBraking = true; bot.agent.avoidancePriority = 40 + id;
        bot.agent.enabled = false;
        bot.pose = go.AddComponent<AnimationMarqueur>(); bot.pose.Initialiser(partie, robot.transform);
        return bot;
    }

    public static BotPaintball CreerDistant(PaintballSolo partie, PartieBots hote, int id, string nom, int couleur)
    {
        var bot = Creer(partie, hote, id, nom, couleur, PartieBots.Niveau.Normal);
        bot.distant = true;
        Destroy(bot.agent); bot.agent = null;
        bot.name = "Joueur" + id + "_" + nom;
        return bot;
    }

    public void Pose(long h, Vector3 position, float lacet, Vector3 vitesse)
    {
        if (poses.Count > 0 && h <= poses[poses.Count - 1].h) return;
        poses.Add((h, position, lacet, vitesse));
        if (poses.Count > 32) poses.RemoveAt(0);
    }

    // Affichage ~100 ms dans le passé du serveur : interpolation entre les deux poses qui encadrent
    // l'instant, extrapolation courte (200 ms au plus) par la vitesse annoncée si le flux s'interrompt.
    void Suivre()
    {
        if (poses.Count == 0 || ClientReseau.Instance == null) { vitesseDistante = Vector3.zero; return; }
        double t = ClientReseau.Instance.HeureServeur - RetardAffichage;
        int i = poses.Count - 1;
        while (i > 0 && poses[i - 1].h > t) i--;
        Vector3 p; float lacet;
        if (i == 0 && poses[0].h >= t) { p = poses[0].p; lacet = poses[0].lacet; vitesseDistante = poses[0].v; }
        else if (i == poses.Count - 1 || poses[i].h <= t)
        {
            var d = poses[poses.Count - 1];
            float ecart = Mathf.Min(.1f, (float)(t - d.h) / 1000f);
            p = d.p + d.v * Mathf.Max(0, ecart); lacet = d.lacet; vitesseDistante = d.v;
        }
        else
        {
            var a = poses[i - 1]; var b = poses[i];
            float k = (float)((t - a.h) / System.Math.Max(1, b.h - a.h));
            p = Vector3.Lerp(a.p, b.p, k); lacet = Mathf.LerpAngle(a.lacet, b.lacet, k); vitesseDistante = Vector3.Lerp(a.v, b.v, k);
        }
        transform.SetPositionAndRotation(p, Quaternion.Euler(0, lacet, 0));
    }

    public void Reapparaitre(Vector3 position, Quaternion rotation)
    {
        if (distant)
        {
            poses.Clear(); transform.SetPositionAndRotation(position, rotation); etat = Etat.Chasse;
            gameObject.SetActive(true); return;
        }
        agent.enabled = false;
        transform.SetPositionAndRotation(position, rotation);
        agent.enabled = true; agent.Warp(position);
        etat = Etat.Chasse; cible = -1; vu = 0; chargeur = Capacite; recharge = -1; prochaineDestination = 0;
        gameObject.SetActive(true);
    }

    public void AnimerTir() { if (pose != null) pose.Tir(); }

    public void Eliminer() { etat = Etat.Elimine; gameObject.SetActive(false); }

    // Touché : retenir d'où venait le tir ; la réapparition qui suit éventuellement remet à zéro.
    public void Touche(Vector3 tireur) { dernierePosition = tireur; }

    void OnDestroy() { if (teintes != null) foreach (var m in teintes) Destroy(m); }

    void Update()
    {
        if (etat == Etat.Elimine || hote.Match == null) return;
        if (distant)
        {
            Suivre();
            animateur.speed = 1;
            animateur.SetFloat(VitesseAnimation, new Vector3(vitesseDistante.x, 0, vitesseDistante.z).magnitude, .12f, Time.deltaTime);
            animateur.SetBool(SolAnimation, true);
            return;
        }
        MesuresPerf.Bots.Start();
        bool pause = partie.EnPause;
        if (agent.enabled && agent.isOnNavMesh) agent.isStopped = pause;
        animateur.speed = pause ? 0 : 1;
        if (!pause) Penser();
        animateur.SetFloat(VitesseAnimation, agent.velocity.magnitude, .12f, Time.deltaTime);
        animateur.SetBool(SolAnimation, true);
        MesuresPerf.Bots.Stop();
    }

    void Penser()
    {
        if (!agent.isOnNavMesh) return;
        if (hote.Match.Termine) { agent.isStopped = true; return; }
        if (Time.time >= prochainePerception) Percevoir();
        if (recharge >= 0)
        {
            recharge += Time.deltaTime / DureeRecharge;
            if (recharge >= 1) { recharge = -1; chargeur = Capacite; }
        }
        Vector3 cibleCorps = cible >= 0 ? hote.Position(cible) : dernierePosition;
        switch (etat)
        {
            case Etat.Chasse:
                agent.speed = 4.4f; agent.updateRotation = true;
                if (cibleVisible) { etat = Etat.Combat; break; }
                if (Time.time >= prochaineDestination || (!agent.pathPending && agent.remainingDistance < 1))
                {
                    // Chercher l'adversaire le plus proche, approché de biais pour ne pas arriver en file.
                    int proie = PlusProche(false);
                    Vector3 but = proie >= 0 ? hote.Position(proie) : hote.pointsSurs[Random.Range(0, hote.pointsSurs.Count)];
                    Aller(but + Random.insideUnitSphere.normalized * Random.Range(4f, 10f));
                    prochaineDestination = Time.time + Random.Range(2.5f, 4.5f);
                }
                break;
            case Etat.Combat:
                agent.speed = 2.6f; agent.updateRotation = false;
                if (!cibleVisible) { vu = 0; etat = Etat.Chasse; prochaineDestination = 0; break; }
                Orienter(cibleCorps);
                vu += Time.deltaTime;
                if (Time.time >= prochaineDestination)
                {
                    // Pas de côté pendant l'échange.
                    Vector3 cote = Vector3.Cross(Vector3.up, cibleCorps - transform.position).normalized * Random.Range(-3f, 3f);
                    Aller(transform.position + cote); prochaineDestination = Time.time + Random.Range(1f, 2f);
                }
                if (vu >= Reactions[(int)niveau] && Time.time >= prochainTir && recharge < 0) Tirer(cibleCorps);
                if (chargeur == 0) ChercherCouvert(cibleCorps);
                break;
            case Etat.Couvert:
                agent.speed = 5.2f; agent.updateRotation = true;
                if (chargeur == 0 && recharge < 0) recharge = 0;
                if (Time.time >= finCouvert && recharge < 0) { etat = cibleVisible ? Etat.Combat : Etat.Chasse; prochaineDestination = 0; vu = 0; }
                else if (cibleVisible && agent.remainingDistance < .5f && recharge < 0 && chargeur > 0) { etat = Etat.Combat; vu = 0; }
                break;
        }
    }

    void Percevoir()
    {
        prochainePerception = Time.time + .15f;
        int vue = PlusProche(true);
        if (vue >= 0) { cible = vue; dernierePosition = hote.Position(vue); }
        cibleVisible = vue >= 0;
    }

    // Adversaire actif le plus proche, éventuellement seulement s'il est en vue directe.
    int PlusProche(bool enVue)
    {
        int meilleur = -1; float distance = Portees[(int)niveau];
        if (!enVue) distance = float.MaxValue;
        Vector3 oeil = transform.position + Vector3.up * Hauteur;
        foreach (var j in hote.Match.joueurs)
        {
            if (j.id == Id || !hote.Actif(j.id) || enVue && !hote.Match.Touchable(j.id)) continue;
            Vector3 p = hote.Position(j.id) + Vector3.up * 1.2f;
            float d = Vector3.Distance(oeil, p);
            if (d >= distance) continue;
            if (enVue && Physics.Linecast(oeil, p, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) continue;
            meilleur = j.id; distance = d;
        }
        return meilleur;
    }

    void Aller(Vector3 but)
    {
        if (!agent.enabled || !agent.isOnNavMesh) return;
        if (NavMesh.SamplePosition(but, out var h, 4, NavMesh.AllAreas)) agent.SetDestination(h.position);
    }

    void Orienter(Vector3 vers)
    {
        Vector3 d = vers - transform.position; d.y = 0;
        if (d.sqrMagnitude < .01f) return;
        transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(d), 360 * Time.deltaTime);
    }

    // Couvert : point du NavMesh proche d'où la menace n'a plus de ligne de vue.
    void ChercherCouvert(Vector3 menace)
    {
        etat = Etat.Couvert; finCouvert = Time.time + Random.Range(2f, 3.5f);
        Vector3 oeil = menace + Vector3.up * 1.5f, meilleur = transform.position; float score = float.MaxValue;
        for (int i = 0; i < 12; i++)
        {
            float a = i * 30 + Random.Range(-10f, 10f);
            Vector3 p = transform.position + Quaternion.Euler(0, a, 0) * Vector3.forward * Random.Range(3f, 9f);
            if (!NavMesh.SamplePosition(p, out var h, 2, NavMesh.AllAreas)) continue;
            bool cache = Physics.Linecast(oeil, h.position + Vector3.up * 1.1f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            float s = Vector3.Distance(transform.position, h.position) + (cache ? 0 : 50) - Vector3.Distance(menace, h.position) * .3f;
            if (s < score) { score = s; meilleur = h.position; }
        }
        Aller(meilleur);
    }

    void Tirer(Vector3 cibleCorps)
    {
        Vector3 origine = bouche.position;
        // Visée au torse avec anticipation du déplacement et compensation de la chute (deux itérations).
        Vector3 vitesseCible = hote.Vitesse(cible); vitesseCible.y = 0;
        Vector3 but = cibleCorps + Vector3.up * (cible >= 0 ? hote.HauteurTorse(cible) : PartieBots.Torse), vise = but;
        for (int k = 0; k < 2; k++)
        {
            float t = Simuler(origine, (vise - origine).normalized, Vector3.Distance(origine, but), out float ecart);
            vise = but + vitesseCible * t * .8f; vise.y += ecart;
        }
        float dispersion = Dispersions[(int)niveau] * (agent.velocity.magnitude > .5f ? 1.4f : 1);
        Vector3 direction = (vise - origine).normalized;
        direction = Quaternion.AngleAxis(Random.Range(-dispersion, dispersion), Vector3.up) * Quaternion.AngleAxis(Random.Range(-dispersion, dispersion) * .6f, transform.right) * direction;
        // Ne pas tirer à travers un mur depuis la bouche.
        if (Physics.Linecast(regard.position, origine, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) origine = regard.position;
        partie.AjouterBille(origine, direction * BalistiquePaintball.VitesseInitiale, Couleur, Id);
        SonsPaintball.Instance?.TirDistant(origine);
        pose.Tir(); chargeur--; pointVise = vise;
        if (++tirsRafale >= Rafales[(int)niveau] + Random.Range(0, 2)) { tirsRafale = 0; prochainTir = Time.time + Pauses[(int)niveau] * Random.Range(.8f, 1.3f); }
        else prochainTir = Time.time + Cadence;
    }

    // Temps de vol jusqu'à la distance horizontale voulue et chute relative à la ligne de tir.
    public static float Simuler(Vector3 origine, Vector3 direction, float distance, out float chute)
    {
        Vector3 p = origine, v = direction * BalistiquePaintball.VitesseInitiale;
        const float dt = 1f / 120f; float t = 0;
        while (Vector3.Distance(origine, p) < distance && t < 2) { BalistiquePaintball.Avancer(ref p, ref v, dt); t += dt; }
        chute = (origine + direction * Vector3.Distance(origine, p)).y - p.y;
        return t;
    }

    void LateUpdate()
    {
        if (etat == Etat.Elimine || hote.Match == null) return;
        Vector3 vers = (cibleVisible ? hote.Position(cible) + Vector3.up * 1.1f : transform.position + transform.forward * 10 + Vector3.up * Hauteur);
        regard.rotation = Quaternion.LookRotation(vers - regard.position);
        pose.Poser(regard, marqueur, null, true, etat == Etat.Combat, etat == Etat.Couvert, recharge, cibleVisible ? pointVise : vers);
    }
}

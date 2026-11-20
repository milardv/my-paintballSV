using UnityEngine;
using UnityEngine.InputSystem;

// Exploration à la première personne : marche, course, saut, regard souris, ouverture des portes.
// Les liaisons clavier du Player map sont des positions physiques : ZQSD sur un clavier AZERTY.
[RequireComponent(typeof(CharacterController))]
public class Explorateur : MonoBehaviour
{
    [SerializeField] Transform tete;
    [SerializeField] float vitesseMarche = 2.2f;
    [SerializeField] float vitesseCourse = 4.5f;
    [SerializeField] float sensibilite = 0.12f;
    [SerializeField] float hauteurSaut = 0.6f;
    [SerializeField] float gravite = -18f;
    [SerializeField] float porteeInteraction = 2.5f;

    CharacterController controleur;
    InputAction deplacer, regarder, sauter, courir, interagir, cliquer;
    float tangage;
    float vitesseVerticale;
    bool suspendu;
    PaintballSolo paintball;
    Porte porteVisee;
    PointHistorique pointVise;
    public event System.Action<Vector3> PositionChangee;
    public event System.Action<Porte> PorteViseeChangee;
    public float Tangage => tangage;
    // Lunette : sensibilité réduite au zoom et petite correction d'aide à la visée (degrés, x = lacet, y = vers le haut).
    public static float FacteurRegard = 1f;
    public static bool Essai;          // contrôles navigateur sans écran : pas de verrouillage du pointeur
    Vector2 correctionRegard;
    public void Corriger(Vector2 degres) => correctionRegard += degres;
    public event System.Action<PointHistorique> PointHistoriqueViseChange;
    public event System.Action<IInteractif> InteractifViseChange;
    IInteractif interactifVise;
    // Véhicule piloté (null à pied) ; Grimpe : déplacement scripté en cours (trappe du toit).
    public Vehicule Monture { get; private set; }
    // Bonus des objets du domaine (Gadgets) : espadrilles, ressorts, jetpack.
    public static float BonusVitesse = 1f, BonusSaut = 1f, PousseeJetpack;
    public bool SautMaintenu => sauter != null && sauter.IsPressed();
    public bool Grimpe { get; private set; }
    public bool EchapGereParInterface { get; set; }
    public bool Court { get; private set; }
    // Accroupi : C bascule, Ctrl maintenu, bouton « Accroupi » en tactile. Accroupissement : 0 debout → 1 accroupi.
    public bool Accroupi { get; private set; }
    public float Accroupissement { get; private set; }
    public const float BaisseYeux = .5f, RapportHauteur = .62f;
    public float HauteurYeux => PaintballSolo.Yeux - BaisseYeux * Accroupissement;
    bool accroupiBascule;
    // Vérification navigateur : entrée de déplacement imposée pendant quelques secondes (« x:y:secondes »).
    Vector2 entreeForcee; float forceeJusqua;
    public void EssaiEntree(string v)
    {
        var a = System.Array.ConvertAll(v.Split(':'), s => float.Parse(s, System.Globalization.CultureInfo.InvariantCulture));
        entreeForcee = new Vector2(a[0], a[1]); forceeJusqua = Time.time + (a.Length > 2 ? a[2] : 2f);
    }

    public void Suspendre(bool valeur)
    {
        suspendu = valeur;
        vitesseVerticale = 0f;
        Verrouiller(!valeur);
        if (valeur) { DefinirPorteVisee(null); DefinirPointVise(null); }
    }

    public void ReinitialiserRegard()
    {
        tangage = 0f;
        vitesseVerticale = 0f;
        tete.localRotation = Quaternion.identity;
    }

    public void RetablirRegard(Quaternion rotation)
    {
        tangage = Mathf.DeltaAngle(0f, rotation.eulerAngles.x);
        tete.localRotation = rotation;
    }

    void Awake()
    {
        controleur = GetComponent<CharacterController>();
        paintball = GetComponent<PaintballSolo>();
        if (tete == null) tete = GetComponentInChildren<Camera>().transform;
        deplacer = InputSystem.actions.FindAction("Player/Move");
        regarder = InputSystem.actions.FindAction("Player/Look");
        sauter = InputSystem.actions.FindAction("Player/Jump");
        courir = InputSystem.actions.FindAction("Player/Sprint");
        interagir = InputSystem.actions.FindAction("Player/Interact");
        cliquer = InputSystem.actions.FindAction("Player/Attack");
    }

    void OnEnable() => Verrouiller(true);

    void Verrouiller(bool oui)
    {
        if (Tactile.Actif) { if (!oui) Tactile.Relacher(); return; }
        Cursor.lockState = oui ? CursorLockMode.Locked : CursorLockMode.None;
        Cursor.visible = !oui;
    }

    void Update()
    {
        if (suspendu || Grimpe) return;
        if (!EchapGereParInterface && Keyboard.current != null && Keyboard.current.escapeKey.wasPressedThisFrame) Verrouiller(false);
        if (!Tactile.Actif && !Essai && Cursor.lockState != CursorLockMode.Locked)
        {
            if (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame) Verrouiller(true);
            return;
        }

        // En tactile, seul le glissé des commandes tactiles tourne la vue (pas tout toucher de l'écran).
        Vector2 regard = Reglages.Regard(Tactile.Actif ? Tactile.LireRegard() : regarder.ReadValue<Vector2>() * sensibilite) * FacteurRegard
            + correctionRegard;
        correctionRegard = Vector2.zero;
        transform.Rotate(0f, regard.x, 0f);
        tangage = Mathf.Clamp(tangage - regard.y, -85f, 85f);
        tete.localRotation = Quaternion.Euler(tangage, 0f, 0f);

        Vector2 entree = deplacer.ReadValue<Vector2>();
        if (Time.time < forceeJusqua) entree = entreeForcee;
        bool course = courir.IsPressed();
        if (Tactile.Actif) { entree = Vector2.ClampMagnitude(entree + Tactile.Deplacement, 1); course |= Tactile.Course; }
        if (Monture != null)
        {
            // En véhicule : ZQSD pilotent (avant, frein et marche arrière, braquage), la souris vise librement.
            Monture.Conduire(entree, Time.deltaTime);
            if (Monture == null) return;   // la monture a pu nous lâcher (tyrolienne au-dessus du bassin)
            controleur.enabled = false;
            transform.position = Monture.PositionPilote;
            PositionChangee?.Invoke(transform.position);
            Court = false;
            if (interagir.WasPressedThisFrame() || (Tactile.Actif && Tactile.Porte())) Descendre();
            return;
        }
        Accroupir();
        if (Accroupi) course = false;
        Court = course && entree.sqrMagnitude > .01f;
        float vitesse = course ? (paintball != null && paintball.Active ? 5.6f : vitesseCourse) : (paintball != null && paintball.Active ? 3.4f : vitesseMarche);
        if (Accroupi) vitesse *= .45f;
        vitesse *= BonusVitesse;
        Vector3 horizontal = (transform.right * entree.x + transform.forward * entree.y) * vitesse;

        float graviteActuelle = paintball != null && paintball.Active ? -9.81f : gravite;
        if (controleur.isGrounded && PousseeJetpack <= 0)
        {
            vitesseVerticale = -2f;
            bool saut = sauter.WasPressedThisFrame() | (Tactile.Actif && Tactile.Saut());
            // Accroupi, le saut relève d'abord (s'il y a la place).
            if (saut && Accroupi) { if (PeutSeRelever()) accroupiBascule = false; }
            else if (saut) vitesseVerticale = Mathf.Sqrt(-2f * graviteActuelle * hauteurSaut * BonusSaut);
        }
        vitesseVerticale += graviteActuelle * Time.deltaTime;
        // Jetpack (Gadgets) : poussée vers le haut tant qu'on maintient le saut, vitesse de montée plafonnée.
        if (PousseeJetpack > 0) vitesseVerticale = Mathf.Min(vitesseVerticale + PousseeJetpack * Time.deltaTime, 6f);
        Vector3 avant = transform.position;
        controleur.Move((horizontal + Vector3.up * vitesseVerticale) * Time.deltaTime);
        if ((transform.position - avant).sqrMagnitude > 0.000001f) PositionChangee?.Invoke(transform.position);

        bool touche = Physics.Raycast(transform.position + Vector3.up * HauteurYeux, tete.forward, out RaycastHit impact, porteeInteraction,
            Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
        Porte cible = touche ? impact.collider.GetComponentInParent<Porte>() : null;
        DefinirInteractif(touche && cible == null ? impact.collider.GetComponentInParent<IInteractif>() : null);
        // Repères d'histoire : déclencheurs, détectés seulement s'ils sont devant le premier obstacle.
        PointHistorique point = null;
        if (Physics.Raycast(transform.position + Vector3.up * HauteurYeux, tete.forward, out RaycastHit repere, touche ? impact.distance + .01f : porteeInteraction,
            Physics.DefaultRaycastLayers, QueryTriggerInteraction.Collide))
            point = repere.collider.GetComponentInParent<PointHistorique>();
        DefinirPorteVisee(cible);
        DefinirPointVise(point);

        bool tactilePorte = Tactile.Actif && Tactile.Porte();
        if (interagir.WasPressedThisFrame() || tactilePorte || (!Tactile.Actif && (paintball == null || !paintball.Active) && cliquer.WasPressedThisFrame())) Interagir();
    }

    float HauteurDebout => paintball != null ? PaintballSolo.Taille : 1.75f;

    // Plafond au-dessus de la tête : impossible de se relever (sous une table, un escalier…).
    bool PeutSeRelever()
    {
        float h = controleur.height, debout = HauteurDebout;
        if (h >= debout - .01f) return true;
        Vector3 bas = transform.position + Vector3.up * (h - controleur.radius);
        return !Physics.SphereCast(bas, controleur.radius * .95f, Vector3.up, out _, debout - h + .05f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
    }

    void Accroupir()
    {
        var k = Keyboard.current;
        if (k != null && k.cKey.wasPressedThisFrame) accroupiBascule = !accroupiBascule;
        if (Tactile.Actif && Tactile.Accroupir()) accroupiBascule = !accroupiBascule;
        bool veut = accroupiBascule || k != null && (k.leftCtrlKey.isPressed || k.rightCtrlKey.isPressed);
        if (!veut && Accroupi && !PeutSeRelever()) veut = true;
        if (!veut && accroupiBascule) accroupiBascule = false;
        Accroupi = veut;
        Accroupissement = Mathf.MoveTowards(Accroupissement, veut ? 1 : 0, 6f * Time.deltaTime);
        float debout = HauteurDebout, h = Mathf.Lerp(debout, debout * RapportHauteur, Accroupissement);
        if (!Mathf.Approximately(h, controleur.height)) { controleur.height = h; controleur.center = Vector3.up * h * .5f; }
        // Hors partie (visite), la tête suit directement ; en partie, PaintballSolo place la caméra.
        if (paintball == null || !paintball.Active) tete.localPosition = new Vector3(0, HauteurYeux, 0);
    }

    // Relevé immédiat (téléportation, réapparition, nouvelle partie).
    public void Relever() { accroupiBascule = false; Accroupi = false; Accroupissement = 0; controleur.height = HauteurDebout; controleur.center = Vector3.up * HauteurDebout * .5f; }

    void Interagir()
    {
        if (porteVisee != null) porteVisee.Basculer(transform.position);
        else if (interactifVise != null) interactifVise.Interagir(this);
        else if (pointVise != null)
        {
            var ui = FindAnyObjectByType<InterfaceVisite>();
            if (ui != null) ui.AfficherHistoire(pointVise);
        }
    }

    void DefinirPorteVisee(Porte porte)
    {
        if (porteVisee == porte) return;
        porteVisee = porte;
        PorteViseeChangee?.Invoke(porte);
    }

    void DefinirInteractif(IInteractif i)
    {
        if (ReferenceEquals(interactifVise, i)) return;
        interactifVise = i;
        InteractifViseChange?.Invoke(i);
    }

    public void Monter(Vehicule s)
    {
        Relever(); Monture = s; controleur.enabled = false; DefinirInteractif(null);
        InteractifViseChange?.Invoke(null);
    }

    // Descente du scooter : à côté de lui (à droite, sinon à gauche, sinon derrière).
    public void Descendre()
    {
        var s = Monture; if (s == null) return;
        Monture = null; s.Liberer();
        Vector3 p = s.PointDescente;
        foreach (var d in new[] { s.transform.right, -s.transform.right, -s.transform.forward })
        {
            Vector3 q = p + d * 1.1f;
            if (!Physics.CheckCapsule(q + Vector3.up * .5f, q + Vector3.up * 1.3f, .3f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) { p = q; break; }
        }
        transform.position = p + Vector3.up * .05f;
        controleur.enabled = true; Physics.SyncTransforms();
        InteractifViseChange?.Invoke(null);
    }

    // Déplacement scripté (trappe du toit) : de la position actuelle à « arrivee » en « duree » secondes, par
    // un point intermédiaire. Vitesse plausible pour le serveur en ligne (< 25 m/s).
    public void GrimperVers(Vector3 passage, Vector3 arrivee, float duree)
    {
        if (Grimpe) return;
        StartCoroutine(Grimper(passage, arrivee, duree));
    }

    System.Collections.IEnumerator Grimper(Vector3 passage, Vector3 arrivee, float duree)
    {
        Grimpe = true; Relever(); controleur.enabled = false;
        Vector3 depart = transform.position;
        for (float t = 0; t < duree; t += Time.deltaTime)
        {
            float k = Mathf.SmoothStep(0, 1, t / duree);
            Vector3 a = Vector3.Lerp(depart, passage, k), b = Vector3.Lerp(passage, arrivee, k);
            transform.position = Vector3.Lerp(a, b, k);
            PositionChangee?.Invoke(transform.position);
            yield return null;
        }
        transform.position = arrivee; vitesseVerticale = 0;
        controleur.enabled = true; Physics.SyncTransforms(); Grimpe = false;
    }

    void DefinirPointVise(PointHistorique point)
    {
        if (pointVise == point) return;
        pointVise = point;
        PointHistoriqueViseChange?.Invoke(point);
    }

    void OnDisable() { DefinirPorteVisee(null); DefinirPointVise(null); DefinirInteractif(null); }
}

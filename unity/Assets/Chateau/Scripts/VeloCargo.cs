using UnityEngine;

// Vélo cargo longtail électrique (pied du perron nord, côté ouest) : E pour monter ; ZQSD pilotent, la souris vise
// et l'on tire comme à pied. Reprend au chargement le modèle du parc (parc_velo_cargo, scripts/composants/velo_cargo.py) :
// une copie dynamique (l'original fait partie de l'occlusion précalculée), direction et roues animées.
public class VeloCargo : Vehicule
{
    public static VeloCargo Instance { get; private set; }
    protected override float VitesseMax => 7f;               // assistance jusqu'à 25 km/h
    protected override float MarcheArriere => 1.2f;
    protected override float Acceleration => 3.2f;
    protected override float Freinage => 7f;
    protected override float Roulement => 1.2f;
    protected override float Braquage => 85f;
    protected override float Inclinaison => 12f;
    protected override float Rayon => .3f;
    protected override float Avant => .66f;
    protected override float Arriere => .66f;
    public override string Nom => "le vélo cargo";
    // Assis sur la selle (0,99 m), un peu en arrière du milieu des roues.
    public override Vector3 PositionPilote => transform.position + transform.up * .38f - transform.forward * .24f;

    Transform guidon, roueAv, roueAr;
    Quaternion guidonRepos;
    Vector3 axeDirection, axeAv, axeAr;
    float rayonAv = .333f, rayonAr = .258f;

    public static void Installer()
    {
        if (Instance != null) return;
        var origine = GameObject.Find("parc_velo_cargo");
        if (origine == null) return;
        Transform Enfant(Transform t, string fin)
        {
            foreach (var c in t.GetComponentsInChildren<Transform>(true)) if (c.name.EndsWith(fin)) return c;
            return null;
        }
        var av = Enfant(origine.transform, "_roue_avant"); var ar = Enfant(origine.transform, "_roue_arriere");
        if (av == null || ar == null) return;
        Vector3 avant = av.position - ar.position; avant.y = 0;
        float lacet = Mathf.Atan2(avant.x, avant.z) * Mathf.Rad2Deg;
        Vector3 sol = origine.transform.position;

        var copie = Instantiate(origine); copie.name = "VeloCargoModele";
        origine.SetActive(false); Physics.SyncTransforms();
        foreach (var c in copie.GetComponentsInChildren<Collider>(true)) Destroy(c);

        var go = new GameObject("VeloCargo");
        Instance = go.AddComponent<VeloCargo>();
        Instance.Poser(sol, lacet);
        copie.transform.SetParent(go.transform, true);
        var boite = go.AddComponent<BoxCollider>(); boite.center = new Vector3(0, .55f, 0); boite.size = new Vector3(.7f, 1.1f, 2.1f);
        Instance.Preparer(copie.transform, Enfant(copie.transform, "_direction"), Enfant(copie.transform, "_roue_avant"), Enfant(copie.transform, "_roue_arriere"));
    }

    void Preparer(Transform modele, Transform direction, Transform av, Transform ar)
    {
        guidon = direction; roueAv = av; roueAr = ar;
        if (guidon != null)
        {
            guidonRepos = guidon.localRotation;
            // Axe de direction : de la roue avant vers le pivot de la douille (incliné d'environ 20°).
            Vector3 axe = guidon.position - roueAv.position;
            if (axe.sqrMagnitude < .01f) axe = Vector3.up;
            axeDirection = transform.InverseTransformDirection(axe.normalized);
        }
        // Axes des roues exprimés dans leur propre repère : ils restent fixes quand elles tournent.
        axeAv = roueAv.InverseTransformDirection(transform.right);
        axeAr = roueAr.InverseTransformDirection(transform.right);
        float echelle = Mathf.Abs(transform.lossyScale.y);
        rayonAv *= echelle; rayonAr *= echelle;
    }

    protected override void Orienter(Vector2 entree)
    {
        float dt = Time.deltaTime;
        if (guidon != null)
        {
            guidon.localRotation = guidonRepos;
            guidon.Rotate(transform.TransformDirection(axeDirection), entree.x * 22f * (1 - .5f * Mathf.Clamp01(Mathf.Abs(Vitesse) / VitesseMax)), Space.World);
        }
        if (roueAv != null) roueAv.Rotate(axeAv, Vitesse * dt / (rayonAv * Mathf.PI * 2) * 360f, Space.Self);
        if (roueAr != null) roueAr.Rotate(axeAr, Vitesse * dt / (rayonAr * Mathf.PI * 2) * 360f, Space.Self);
    }
}

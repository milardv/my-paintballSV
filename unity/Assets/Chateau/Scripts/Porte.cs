using UnityEngine;

// Porte battante : l'objet pivote autour de son origine (placée sur le gond à l'export Blender).
// Elle s'ouvre du côté opposé à l'explorateur pour ne pas le pousser ; les portes-fenêtres et portes de balcon
// s'ouvrent toujours vers l'intérieur du château (comme les vraies).
public class Porte : MonoBehaviour
{
    [SerializeField] float angleOuverture = 100f;
    [SerializeField] float vitesse = 180f;

    Quaternion fermee;
    float angleCible;
    float angle;

    float sensVantail = 1f;
    bool versInterieur;
    public event System.Action<bool> EtatChange;

    void Awake()
    {
        fermee = transform.localRotation;
        versInterieur = name.StartsWith("porte_fenetre_") || name.StartsWith("porte_balcon_etage_");
        // Vantail rabattu contre l'embrasure sans la traverser (gond à 6,5 cm du tableau).
        if (versInterieur) angleOuverture = 88f;
        // Côté où s'étend le vantail depuis le gond (axe X local).
        var maillage = GetComponentInChildren<MeshFilter>();
        if (maillage != null && maillage.sharedMesh != null)
        {
            Vector3 centre = transform.InverseTransformPoint(
                maillage.transform.TransformPoint(maillage.sharedMesh.bounds.center));
            sensVantail = centre.x < 0f ? -1f : 1f;
        }
    }

    public bool Ouverte => !Mathf.Approximately(angleCible, 0f);

    public void Basculer(Vector3 depuis)
    {
        if (Ouverte)
        {
            angleCible = 0f;
            EtatChange?.Invoke(false);
            return;
        }
        // Château centré sur l'origine (repère D-003) : on fait comme si l'on ouvrait depuis l'extérieur.
        if (versInterieur) { Vector3 dehors = transform.position; dehors.y = 0; depuis = transform.position + (dehors.sqrMagnitude > .01f ? dehors.normalized : Vector3.forward) * 3f; }
        Vector3 versExplorateur = transform.InverseTransformPoint(depuis);
        // Une rotation positive autour de Y pousse le bord libre vers -Z * sensVantail.
        angleCible = angleOuverture * sensVantail * (versExplorateur.z > 0f ? 1f : -1f);
        EtatChange?.Invoke(true);
    }

    void Update()
    {
        if (Mathf.Approximately(angle, angleCible)) return;
        angle = Mathf.MoveTowards(angle, angleCible, vitesse * Time.deltaTime);
        transform.localRotation = fermee * Quaternion.Euler(0f, angle, 0f);
    }
}

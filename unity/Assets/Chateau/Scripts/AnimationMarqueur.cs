using UnityEngine;

// Pose procédurale du marqueur Spyder MR100, après l'Animator.
// Troisième personne : arme ancrée au torse animé (suit la marche et la course), buste incliné
// vers la visée, mains placées par IK sur la poignée et le grip avant (main gauche sur le
// réservoir pendant la recharge). Première personne : balancement de marche, inertie du regard,
// visée épaulée, position basse en course, recul et geste de recharge.
[DefaultExecutionOrder(50)]
public class AnimationMarqueur : MonoBehaviour
{
    // Repères du modèle normalisé (scripts/paintball_marqueur.py), en mètres, origine sur la poignée.
    public static readonly Vector3 Poignee = Vector3.zero;
    public static readonly Vector3 GripAvant = new(0, -.043f, .132f);
    public static readonly Vector3 Reservoir = new(0, .2f, .03f);
    public static readonly Vector3 Bouche = new(0, .054f, .47f);

    PaintballSolo partie;
    Transform torse, brasD, coudeD, mainD, brasG, coudeG, mainG;
    float recul, poidsCourse, poidsVisee, phasePas, vitesseLissee, hauteurMoyenne;
    Vector2 inertie;
    Quaternion regardPrecedent, torseAvant, torseApres;
    Vector3 positionPrecedente;

    public void Initialiser(PaintballSolo p, Transform racinePersonnage)
    {
        partie = p;
        foreach (var t in racinePersonnage.GetComponentsInChildren<Transform>(true))
            switch (t.name)
            {
                case "Torso": torse = t; break;
                case "UpperArm.R": brasD = t; break; case "LowerArm.R": coudeD = t; break; case "Palm2.R": mainD = t; break;
                case "UpperArm.L": brasG = t; break; case "LowerArm.L": coudeG = t; break; case "Palm2.L": mainG = t; break;
            }
    }

    public void Tir() => recul = 1;

    public void Poser(Transform cam, Transform marqueur, Transform marqueurPOV, bool troisieme, bool visee, bool course, float recharge, Vector3 pointVise)
    {
        float dt = Time.deltaTime;
        Vector3 deplacement = transform.position - positionPrecedente; deplacement.y = 0;
        positionPrecedente = transform.position;
        float vitesse = dt > 0 ? deplacement.magnitude / dt : 0;
        vitesseLissee = Mathf.Lerp(vitesseLissee, vitesse, 1 - Mathf.Exp(-10 * dt));
        phasePas += vitesseLissee * dt * 1.9f;
        recul = Mathf.MoveTowards(recul, 0, dt * 9);
        poidsCourse = Mathf.MoveTowards(poidsCourse, course && !visee && recharge < 0 && recul <= 0 ? 1 : 0, dt * 5);
        poidsVisee = Mathf.MoveTowards(poidsVisee, visee && recharge < 0 ? 1 : 0, dt * 7);
        // Geste de recharge : montée rapide, tenue, retour (0 hors recharge).
        float r = recharge < 0 ? 0 : Mathf.SmoothStep(0, 1, Mathf.Min(recharge / .18f, (1 - recharge) / .22f, 1));
        float secousse = recharge < 0 ? 0 : Mathf.Sin(recharge * 38) * Mathf.Sin(recharge * Mathf.PI) * .5f;
        float k = 1 - Mathf.Exp(-6 * dt);

        if (!troisieme)
        {
            Quaternion regard = cam.rotation;
            Quaternion delta = Quaternion.Inverse(regardPrecedent) * regard; regardPrecedent = regard;
            Vector3 e = delta.eulerAngles;
            Vector2 cible = new(Mathf.Clamp(Mathf.DeltaAngle(0, e.y), -6, 6), Mathf.Clamp(Mathf.DeltaAngle(0, e.x), -6, 6));
            inertie = Vector2.Lerp(inertie, cible * (1 - poidsVisee * .7f), k * 1.6f);
            float amplitude = Mathf.Clamp01(vitesseLissee / 5.6f) * (1 - poidsVisee * .75f);
            Vector3 pas = new(Mathf.Sin(phasePas * Mathf.PI) * .011f, -Mathf.Abs(Mathf.Cos(phasePas * Mathf.PI)) * .013f, 0);
            Vector3 hanche = new(.25f, -.29f, .33f), epaule = new(.1f, -.2f, .24f), bas = new(.18f, -.36f, .24f);
            Vector3 p = Vector3.Lerp(Vector3.Lerp(hanche, epaule, poidsVisee), bas, poidsCourse) + pas * amplitude;
            p += new Vector3(0, -.11f, -.04f) * r + new Vector3(0, 0, -.045f) * recul;
            Quaternion rot = Quaternion.Euler(-recul * 4.5f + poidsCourse * 22 + r * 26 + secousse * 3 + inertie.y * .6f,
                -2.5f * (1 - poidsVisee) - poidsCourse * 34 + inertie.x * .8f, r * 38 + poidsCourse * 12 - inertie.x * .5f);
            marqueurPOV.localPosition = p;
            marqueurPOV.localRotation = rot;
            return;
        }

        regardPrecedent = cam.rotation;
        float tangage = Mathf.DeltaAngle(0, cam.eulerAngles.x);
        if (torse != null)
        {
            // Si l'Animator n'a pas réécrit le torse cette image, repartir de sa pose sans inclinaison.
            if (torse.localRotation == torseApres) torse.localRotation = torseAvant;
            torseAvant = torse.localRotation;
            torse.rotation = Quaternion.AngleAxis(tangage * .45f * (1 - poidsCourse), transform.right) * torse.rotation;
            torseApres = torse.localRotation;
        }
        // Le robot a une tête de 1,16 m de large entre 0,96 et 1,72 m : l'arme se porte à la hanche,
        // hors du torse, et suit le rebond vertical que l'animation donne au torse.
        float hauteurTorse = torse != null ? torse.position.y - transform.position.y : 0;
        hauteurMoyenne = hauteurMoyenne == 0 ? hauteurTorse : Mathf.Lerp(hauteurMoyenne, hauteurTorse, dt * .8f);
        Quaternion lacet = Quaternion.Euler(0, transform.eulerAngles.y, 0);
        Vector3 position = transform.position + lacet * new Vector3(.62f, .8f + poidsVisee * .08f, .34f) * PaintballSolo.Echelle + Vector3.up * (hauteurTorse - hauteurMoyenne);
        Vector3 viseeDir = pointVise - position;
        if (viseeDir.sqrMagnitude < 4) viseeDir = cam.forward;
        Quaternion orientation = Quaternion.LookRotation(viseeDir, Vector3.up);
        orientation = Quaternion.Slerp(orientation, lacet * Quaternion.Euler(28, -38, 10), poidsCourse);
        orientation *= Quaternion.Euler(-recul * 6 + r * 24 + secousse * 4, 0, r * 40);
        marqueur.SetPositionAndRotation(position - orientation * new Vector3(0, -.02f * r, .05f * recul), orientation);

        Vector3 coudes = -Vector3.up * .6f - transform.forward * .15f;
        PoserBras(brasD, coudeD, mainD, marqueur.TransformPoint(Poignee + new Vector3(0, -.025f, -.01f)), transform.right * .8f + coudes);
        Vector3 gauche = Vector3.Lerp(marqueur.TransformPoint(GripAvant), marqueur.TransformPoint(Reservoir) + Vector3.up * secousse * .03f, r);
        PoserBras(brasG, coudeG, mainG, gauche, -transform.right * .8f + coudes);
    }

    static void PoserBras(Transform bras, Transform coude, Transform main, Vector3 cible, Vector3 pole)
    {
        if (bras == null || coude == null || main == null) return;
        Vector3 origine = bras.position; float a = Vector3.Distance(origine, coude.position), b = Vector3.Distance(coude.position, main.position);
        Vector3 direction = (cible - origine).normalized; float distance = Mathf.Clamp(Vector3.Distance(cible, origine), Mathf.Abs(a - b) + .001f, a + b - .001f);
        float longueur = (a * a - b * b + distance * distance) / (2 * distance), hauteur = Mathf.Sqrt(Mathf.Max(0, a * a - longueur * longueur));
        Vector3 pli = Vector3.ProjectOnPlane(pole, direction).normalized;
        Vector3 butCoude = origine + direction * longueur + pli * hauteur;
        bras.rotation = Quaternion.FromToRotation(coude.position - origine, butCoude - origine) * bras.rotation;
        coude.rotation = Quaternion.FromToRotation(main.position - coude.position, origine + direction * distance - coude.position) * coude.rotation;
    }
}

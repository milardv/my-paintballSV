using System.Collections.Generic;
using UnityEngine;

// Personnage touché : une copie du robot, avec ses taches, reste là où la bille l'a atteint pendant que
// le joueur réapparaît ailleurs. Figée dans la pose du moment de la touche (animateur coupé), elle encaisse
// un instant (la tache se voit), bascule en arrière à l'opposé du tireur comme un corps raide qui tombe,
// rebondit un peu, reste au sol puis s'enfonce et disparaît.
// Le clip « Death » du robot n'est pas utilisé : rejoué sur une copie du squelette dans le build web,
// il ne donnait que la pose de référence (bras en croix).
public class CorpsTombe : MonoBehaviour
{
    const float Encaisse = .3f, Chute = .7f, Rebond = .35f, AuSol = 3.2f, Disparition = 1.1f;
    static readonly List<CorpsTombe> tous = new();
    public static int Nombre => tous.Count;
    public static int Chutes;

    Quaternion rotationDepart;
    Vector3 axe, positionDepart;
    float t;

    // robot : le robot affiché du joueur touché (copié dans sa pose actuelle) ; tireur : d'où venait la bille.
    public static CorpsTombe Creer(GameObject robot, Vector3 tireur)
    {
        if (robot == null || !robot.activeInHierarchy) return null;
        var copie = Instantiate(robot, robot.transform.position, robot.transform.rotation);
        copie.name = "CorpsTombe"; copie.transform.localScale = robot.transform.lossyScale;
        foreach (var x in copie.GetComponentsInChildren<Transform>(true)) x.gameObject.layer = 2;
        foreach (var c in copie.GetComponentsInChildren<Collider>(true)) Destroy(c);
        foreach (var a in copie.GetComponentsInChildren<Animator>(true)) a.enabled = false;
        // Face au tireur : il tombe en arrière, loin de lui.
        Vector3 vers = tireur - copie.transform.position; vers.y = 0;
        if (vers.sqrMagnitude > .01f) copie.transform.rotation = Quaternion.LookRotation(vers);
        var corps = copie.AddComponent<CorpsTombe>();
        corps.rotationDepart = copie.transform.rotation; corps.positionDepart = copie.transform.position;
        corps.axe = copie.transform.right;
        tous.Add(corps); Chutes++;
        return corps;
    }

    void Update()
    {
        t += Time.deltaTime;
        float angle, c = t - Encaisse;
        if (c < 0) angle = -10 * Mathf.Sin(t / Encaisse * Mathf.PI);           // encaisse : léger recul
        else if (c < Chute) { float k = c / Chute; angle = 86 * k * k; }        // chute accélérée
        else if (c < Chute + Rebond) angle = 86 - 9 * Mathf.Sin((c - Chute) / Rebond * Mathf.PI); // petit rebond
        else angle = 86;
        // Rotation autour des pieds ; le dos se pose sur le sol (pas de pénétration au milieu de la chute).
        transform.rotation = Quaternion.AngleAxis(-angle, axe) * rotationDepart;
        float pose = Mathf.Clamp01(angle / 86);
        Vector3 p = positionDepart + Vector3.up * (.16f * pose);
        float fin = c - Chute - Rebond - AuSol;
        if (fin > 0)
        {
            p += Vector3.down * (fin / Disparition) * 1.2f;
            if (fin > Disparition) { Destroy(gameObject); return; }
        }
        transform.position = p;
    }

    public static void ToutEffacer()
    {
        foreach (var c in tous) if (c != null) Destroy(c.gameObject);
        tous.Clear();
    }

    void OnDestroy() => tous.Remove(this);
}

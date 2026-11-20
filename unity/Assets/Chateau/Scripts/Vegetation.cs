using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

// Feuillages vivants : les plantes du parc et de la terrasse s'écartent quand le joueur les traverse, puis
// reviennent en oscillant (ressort amorti). Les buissons ne bloquent plus (ChateauScene ne leur donne pas de
// collision) ; les arbres ne gardent qu'une collision de tronc et ne s'inclinent que légèrement.
public class Vegetation : MonoBehaviour
{
    public static readonly Regex Plantes = new(
        @"^(parc_(olivier|chene|alep|feuillu|cypres|buis|agave|platane|phoenix|laurier|lavande|washingtonia|if|fleurs|massif_[a-z_]+?)(?!_pierre)|terrasse_(laurier_rose|palier_nord_fougere))",
        RegexOptions.Compiled);
    public static readonly Regex Arbres = new(@"^parc_(olivier|chene|alep|feuillu|cypres|platane|phoenix|washingtonia)", RegexOptions.Compiled);

    class Plante { public Transform t; public Quaternion repos; public Vector3 pied; public float rayon, hauteur, inclinaisonMax; public Vector2 angle, vitesse; public bool active; }
    readonly List<Plante> plantes = new();
    Transform joueur;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        var chateau = GameObject.Find("Chateau");
        if (chateau == null) return;
        new GameObject("Vegetation").AddComponent<Vegetation>().Collecter(chateau.transform);
    }

    void Collecter(Transform racine)
    {
        foreach (var r in racine.GetComponentsInChildren<MeshRenderer>())
        {
            if (!Plantes.IsMatch(r.name) || r.name.Contains("_pierre")) continue;
            var b = r.bounds;
            bool arbre = Arbres.IsMatch(r.name);
            float rayon = Mathf.Max(b.extents.x, b.extents.z);
            if (rayon < .15f || rayon > 9f) continue;
            plantes.Add(new Plante
            {
                t = r.transform, repos = r.transform.rotation, pied = r.transform.position, rayon = rayon + .4f, hauteur = b.size.y,
                inclinaisonMax = arbre ? 2.5f : Mathf.Lerp(16f, 7f, Mathf.InverseLerp(.5f, 2.5f, b.size.y)),
            });
        }
        Debug.Log($"VEGETATION {plantes.Count} plantes");
    }

    void Update()
    {
        if (joueur == null) { var e = FindAnyObjectByType<Explorateur>(); if (e == null) return; joueur = e.transform; }
        Vector3 p = joueur.position;
        float dt = Mathf.Min(Time.deltaTime, .05f);
        foreach (var pl in plantes)
        {
            Vector2 d = new(p.x - pl.pied.x, p.z - pl.pied.z);
            float dist = d.magnitude;
            Vector2 cible = Vector2.zero;
            if (dist < pl.rayon && p.y > pl.pied.y - 1 && p.y < pl.pied.y + pl.hauteur)
            {
                float f = 1 - dist / pl.rayon;
                cible = (dist > .01f ? -d / dist : Vector2.up) * pl.inclinaisonMax * f;   // s'écarte du joueur
            }
            if (!pl.active && cible == Vector2.zero) continue;
            // Ressort amorti : on suit la poussée, puis on revient en oscillant.
            pl.vitesse += ((cible - pl.angle) * 55f - pl.vitesse * 5f) * dt;
            pl.angle += pl.vitesse * dt;
            pl.active = pl.angle.sqrMagnitude > .0004f || pl.vitesse.sqrMagnitude > .0004f || cible != Vector2.zero;
            if (!pl.active) { pl.angle = pl.vitesse = Vector2.zero; pl.t.rotation = pl.repos; continue; }
            // Inclinaison autour de l'horizontale perpendiculaire à la poussée (pivot au pied de la plante).
            var axe = new Vector3(pl.angle.y, 0, -pl.angle.x);
            pl.t.rotation = Quaternion.AngleAxis(pl.angle.magnitude, axe.normalized) * pl.repos;
        }
    }
}

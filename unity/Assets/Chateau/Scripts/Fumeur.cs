using System.Collections.Generic;
using UnityEngine;

// Fumeur du coin terrasse est (canapé et cendrier tube, scripts/composants/terrasse.py) : un invité debout à
// côté du cendrier, cigarette à la main ; toutes les quelques secondes il la porte à la bouche (IK à deux os
// sur le bras droit), le bout rougeoie, puis il souffle un nuage de fumée. Décor seulement : pas de collision.
public class Fumeur : MonoBehaviour
{
    static readonly int VitesseAnimation = Animator.StringToHash("Vitesse"), SolAnimation = Animator.StringToHash("AuSol");
    const float Cycle = 7.5f;

    Animator animateur;
    Transform epaule, coude, main, tete, cigarette, braise;
    Material matBraise, matFumee;
    float phase, prochaineVolute;
    bool souffle;
    readonly List<(Transform t, Vector3 v, float age, float duree, float taille)> volutes = new();

    public static void Installer(GameObject robot)
    {
        if (robot == null || GameObject.Find("Fumeur") != null) return;
        // Repère D-003 : à côté du cendrier (21,35 ; 4,95), tourné vers la terrasse ; Unity = (-x, z, y).
        var p = new Vector3(-20.6f, 0, 5.45f);
        // Dallage de la terrasse (en plein air : premier sol touché depuis le haut).
        if (Physics.Raycast(p + Vector3.up * 8, Vector3.down, out var sol, 16, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) p.y = sol.point.y;
        var racine = new GameObject("Fumeur");
        racine.transform.SetPositionAndRotation(p, Quaternion.LookRotation(new Vector3(1f, 0, .45f)));
        var s = Instantiate(robot, racine.transform, false); s.name = "Robot"; s.SetActive(true);
        s.transform.localPosition = new Vector3(0, robot.transform.localPosition.y, 0); s.transform.localRotation = Quaternion.identity;
        foreach (var c in s.GetComponentsInChildren<Collider>()) Destroy(c);
        foreach (Transform t in s.GetComponentsInChildren<Transform>(true)) if (t.name == "Accessoire") Destroy(t.gameObject);
        PartieBots.Teinter(s, new Color(.12f, .16f, .3f), false);
        var f = racine.AddComponent<Fumeur>(); f.animateur = s.GetComponentInChildren<Animator>(); f.Preparer(s.transform);
    }

    static Transform Os(Transform racine, Animator a, HumanBodyBones os, params string[] noms)
    {
        if (a != null && a.isHuman) { var t = a.GetBoneTransform(os); if (t != null) return t; }
        foreach (var n in noms) foreach (var t in racine.GetComponentsInChildren<Transform>(true)) if (t.name.EndsWith(n)) return t;
        return null;
    }

    void Preparer(Transform robot)
    {
        epaule = Os(robot, animateur, HumanBodyBones.RightUpperArm, "RightArm", "UpperArm_R", "upperarm_r");
        coude = Os(robot, animateur, HumanBodyBones.RightLowerArm, "RightForeArm", "LowerArm_R", "lowerarm_r");
        main = Os(robot, animateur, HumanBodyBones.RightHand, "RightHand", "Hand_R", "hand_r");
        tete = Os(robot, animateur, HumanBodyBones.Head, "Head", "head");
        var lit = Shader.Find("Universal Render Pipeline/Lit");
        Material Mat(Color c, float lisse, Color? em = null)
        {
            var m = new Material(lit); m.SetColor("_BaseColor", c); m.SetFloat("_Smoothness", lisse);
            if (em.HasValue) { m.EnableKeyword("_EMISSION"); m.SetColor("_EmissionColor", em.Value); }
            return m;
        }
        cigarette = new GameObject("Cigarette").transform;
        Transform Piece(Vector3 pos, Vector3 e, Material m)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Cylinder); Destroy(g.GetComponent<Collider>());
            g.transform.SetParent(cigarette, false); g.transform.localPosition = pos; g.transform.localScale = e;
            g.transform.localRotation = Quaternion.Euler(90, 0, 0); var r = g.GetComponent<Renderer>(); r.sharedMaterial = m;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; return g.transform;
        }
        Piece(new Vector3(0, 0, .035f), new Vector3(.009f, .028f, .009f), Mat(new Color(.95f, .94f, .9f), .3f));
        Piece(new Vector3(0, 0, -.009f), new Vector3(.0092f, .011f, .0092f), Mat(new Color(.8f, .52f, .26f), .3f));
        matBraise = Mat(new Color(.25f, .05f, 0), .2f, new Color(1f, .3f, .05f));
        braise = Piece(new Vector3(0, 0, .065f), new Vector3(.0088f, .0025f, .0088f), matBraise);
        matFumee = MatFumee();
        phase = Random.value * Cycle;
    }

    // Fumée translucide : copie d'un matériau transparent déjà présent dans la scène (variante de shader incluse
    // dans le build web), sinon gris opaque.
    static Material MatFumee()
    {
        foreach (var r in FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None))
            foreach (var m in r.sharedMaterials)
                if (m != null && m.HasProperty("_Surface") && m.GetFloat("_Surface") > .5f && m.shader.name == "Universal Render Pipeline/Lit")
                {
                    var f = new Material(m); f.SetTexture("_BaseMap", null); f.SetColor("_BaseColor", new Color(.85f, .86f, .88f, .28f));
                    f.SetFloat("_Smoothness", 0); f.SetFloat("_Metallic", 0); f.DisableKeyword("_EMISSION"); return f;
                }
        var o = new Material(Shader.Find("Universal Render Pipeline/Lit")); o.SetColor("_BaseColor", new Color(.8f, .81f, .83f)); return o;
    }

    void Update()
    {
        if (animateur != null) { animateur.SetFloat(VitesseAnimation, 0); animateur.SetBool(SolAnimation, true); }
        phase = (phase + Time.deltaTime) % Cycle;
        float dt = Time.deltaTime;
        for (int i = volutes.Count - 1; i >= 0; i--)
        {
            var (t, v, age, duree, taille) = volutes[i]; age += dt;
            if (age > duree) { Destroy(t.gameObject); volutes.RemoveAt(i); continue; }
            v = Vector3.Lerp(v, new Vector3(.25f, .35f, .1f), dt * .8f);
            t.position += v * dt; float k = age / duree;
            t.localScale = Vector3.one * taille * (1 + 3.5f * k) * (1 - k * k);
            volutes[i] = (t, v, age, duree, taille);
        }
    }

    // Bras : 0 au repos, 1 cigarette aux lèvres (montée 0,8 s, bouffée 1,2 s, descente 0,8 s).
    float Poids => phase < .8f ? Mathf.SmoothStep(0, 1, phase / .8f) : phase < 2f ? 1 : phase < 2.8f ? Mathf.SmoothStep(1, 0, (phase - 2f) / .8f) : 0;

    void LateUpdate()
    {
        if (epaule == null || coude == null || main == null || tete == null) return;
        float w = Poids;
        Vector3 bouche = tete.position + transform.forward * .12f - Vector3.up * .07f + transform.right * .02f;
        // Au repos : main tenue à hauteur de poitrine, avant-bras plié.
        Vector3 repos = epaule.position + transform.forward * .25f - Vector3.up * .25f + transform.right * .05f;
        Deux(Vector3.Lerp(repos, bouche, w));
        // Cigarette entre les doigts, pointée vers l'avant et un peu vers le haut.
        Vector3 avant = Vector3.Slerp(transform.forward + transform.right * .4f, transform.forward + Vector3.up * .2f, w).normalized;
        cigarette.SetPositionAndRotation(main.position + transform.forward * .07f + Vector3.up * .02f, Quaternion.LookRotation(avant, Vector3.up));
        bool tire = phase > .8f && phase < 2f;
        matBraise.SetColor("_EmissionColor", new Color(1f, .3f, .05f) * (tire ? 3.5f + Mathf.Sin(Time.time * 18) : .9f + .3f * Mathf.Sin(Time.time * 3)));
        if (Time.time > prochaineVolute) { prochaineVolute = Time.time + .35f; Volute(braise.position, new Vector3(0, .25f, 0), .025f, 2.6f); }
        // Expiration après la bouffée.
        if (phase > 3.1f && phase < 4.2f && !souffle)
        {
            souffle = true;
            for (int k = 0; k < 7; k++) Volute(bouche + Random.insideUnitSphere * .03f, (transform.forward * .7f + Vector3.up * .25f + Random.insideUnitSphere * .2f) * Random.Range(.6f, 1.1f), .06f, 2.2f);
        }
        if (phase < 3f) souffle = false;
    }

    void Volute(Vector3 p, Vector3 v, float taille, float duree)
    {
        if (matFumee == null) return;
        var g = GameObject.CreatePrimitive(PrimitiveType.Sphere); Destroy(g.GetComponent<Collider>());
        g.name = "Fumee"; g.layer = 2; g.transform.position = p; g.transform.localScale = Vector3.one * taille;
        var r = g.GetComponent<Renderer>(); r.sharedMaterial = matFumee; r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        volutes.Add((g.transform, v, 0, duree, taille));
    }

    // IK à deux os (épaule, coude, main) avec le coude vers le bas et l'extérieur.
    void Deux(Vector3 cible)
    {
        float a = Vector3.Distance(epaule.position, coude.position), b = Vector3.Distance(coude.position, main.position);
        Vector3 vers = cible - epaule.position; float c = Mathf.Clamp(vers.magnitude, Mathf.Abs(a - b) + .01f, a + b - .01f);
        Vector3 dir = vers.normalized;
        Vector3 pole = (-Vector3.up + transform.right * .6f - transform.forward * .2f).normalized;
        Vector3 cote = Vector3.ProjectOnPlane(pole, dir).normalized;
        float cosA = Mathf.Clamp((a * a + c * c - b * b) / (2 * a * c), -1, 1);
        Vector3 coudeVoulu = epaule.position + dir * (a * cosA) + cote * (a * Mathf.Sqrt(1 - cosA * cosA));
        epaule.rotation = Quaternion.FromToRotation(coude.position - epaule.position, coudeVoulu - epaule.position) * epaule.rotation;
        Vector3 mainVoulue = epaule.position + dir * c;
        coude.rotation = Quaternion.FromToRotation(main.position - coude.position, mainVoulue - coude.position) * coude.rotation;
    }

    void OnDestroy() { foreach (var v in volutes) if (v.t != null) Destroy(v.t.gameObject); }
}

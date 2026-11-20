using System.Collections.Generic;
using TMPro;
using UnityEngine;

// Podium de fin de partie (bots et en ligne) : marches 1-2-3 en pierre claire dans la cour sablée devant la
// façade sud, les trois premiers dessus, les autres au pied, chacun teint de sa couleur et couvert des taches
// reçues pendant la partie (PartieBots.taches). Nom et points au-dessus de chaque joueur ; caméra propre
// qui tourne lentement, décalée pour laisser la colonne de résultats à gauche de l'écran.
[DefaultExecutionOrder(200)]
public class PodiumPaintball : MonoBehaviour
{
    static PodiumPaintball actuel;
    static readonly Vector3 Lieu = new(0, 0, 25);
    static readonly float[] Hauteurs = { .9f, .62f, .42f };
    static readonly float[] Decalages = { 0, -1.3f, 1.3f };
    static readonly int VitesseAnimation = Animator.StringToHash("Vitesse"), SolAnimation = Animator.StringToHash("AuSol");

    Camera vue;
    Vector3 centre;
    float angle;
    readonly List<(Transform tete, TextMeshPro texte)> etiquettes = new();
    Transform gagnant; float baseGagnant;

    public static void Cacher()
    {
        if (actuel == null) return;
        // La caméra de jeu reprend sa place dans la tête du joueur.
        if (actuel.vue != null) { actuel.vue.transform.localPosition = new Vector3(0, PaintballSolo.Yeux, 0); actuel.vue.transform.localRotation = Quaternion.identity; actuel.vue.fieldOfView = Reglages.ChampVision; }
        Destroy(actuel.gameObject); actuel = null;
    }

    public static void Montrer(PaintballSolo partie, TMP_FontAsset police)
    {
        Cacher();
        var match = partie.Bots.Match; if (match == null || partie.personnage == null) return;
        var go = new GameObject("Podium"); var p = go.AddComponent<PodiumPaintball>(); actuel = p;
        // Sol de la cour sablée sous le lieu choisi.
        Vector3 c = Lieu;
        if (Physics.Raycast(c + Vector3.up * 30, Vector3.down, out var sol, 60, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) c.y = sol.point.y;
        p.centre = c;
        var lit = Shader.Find("Universal Render Pipeline/Lit");
        var pierre = new Material(lit); pierre.SetColor("_BaseColor", new Color(.93f, .9f, .84f)); pierre.SetFloat("_Smoothness", .25f);
        var bande = new Material(lit); bande.SetColor("_BaseColor", new Color(.68f, .58f, .39f)); bande.SetFloat("_Metallic", .6f); bande.SetFloat("_Smoothness", .6f);

        var classement = match.Classement();
        for (int rang = 0; rang < 3 && rang < classement.Count; rang++)
        {
            float h = Hauteurs[rang]; Vector3 base_ = c + Vector3.right * Decalages[rang];
            Bloc(go.transform, base_ + Vector3.up * h * .5f, new Vector3(1.2f, h, 1.1f), pierre);
            Bloc(go.transform, base_ + new Vector3(0, h - .04f, .555f), new Vector3(1.22f, .08f, .02f), bande);
            if (police != null)
            {
                var n = Texte(go.transform, (rang + 1).ToString(), police, 6, new Color(.68f, .58f, .39f));
                n.transform.position = base_ + new Vector3(0, h * .45f, .56f); n.transform.rotation = Quaternion.LookRotation(Vector3.back);
            }
            p.Placer(partie, classement[rang], base_ + Vector3.up * h, police, rang == 0);
        }
        for (int i = 3; i < classement.Count; i++)
        {
            float x = (i % 2 == 1 ? -1 : 1) * (2.6f + (i - 3) / 2 * .9f);
            p.Placer(partie, classement[i], c + new Vector3(x, 0, .3f), police, false);
        }
        // La caméra de jeu tourne autour du podium le temps de l'écran de fin (ordre d'exécution après le jeu).
        p.vue = partie.GetComponentInChildren<Camera>(); p.angle = 0;
        if (p.vue != null) p.vue.fieldOfView = 40;
        p.LateUpdate();
    }

    void Placer(PaintballSolo partie, JoueurMatch j, Vector3 pieds, TMP_FontAsset police, bool premier)
    {
        var racine = new GameObject("Podium_" + j.nom).transform; racine.SetParent(transform, false);
        racine.SetPositionAndRotation(pieds, Quaternion.LookRotation(Vector3.forward));
        var robot = Instantiate(partie.personnage, racine, false); robot.name = "Robot"; robot.SetActive(true);
        robot.transform.localPosition = new Vector3(0, partie.personnage.transform.localPosition.y, 0); robot.transform.localRotation = Quaternion.identity;
        foreach (var col in robot.GetComponentsInChildren<Collider>()) Destroy(col);
        foreach (var t in robot.GetComponentsInChildren<Transform>(true)) if (t.name == "TacheCorps") Destroy(t.gameObject);
        PartieBots.Teinter(robot, PaintballSolo.Couleurs[Mathf.Clamp(j.couleur, 0, PaintballSolo.Couleurs.Length - 1)], false);
        var anim = robot.GetComponentInChildren<Animator>();
        if (anim != null) { anim.SetFloat(VitesseAnimation, 0); anim.SetBool(SolAnimation, true); }
        if (partie.Bots.taches.TryGetValue(j.id, out var liste)) foreach (var t in liste) PartieBots.PoserTache(robot, t, partie.impacts);
        if (premier) { gagnant = racine; baseGagnant = pieds.y; }
        if (police == null) return;
        Color c = PaintballSolo.Couleurs[Mathf.Clamp(j.couleur, 0, PaintballSolo.Couleurs.Length - 1)];
        string nom = j.id == partie.JoueurId ? "Vous" : j.nom;
        var texte = Texte(transform, $"{nom}\n<size=70%><color=#F4F0E7>{j.points} pt{(j.points > 1 ? "s" : "")}</color></size>", police, 2.2f, c);
        etiquettes.Add((racine, texte));
    }

    static void Bloc(Transform parent, Vector3 centre, Vector3 taille, Material m)
    {
        var b = GameObject.CreatePrimitive(PrimitiveType.Cube); Destroy(b.GetComponent<Collider>());
        b.transform.SetParent(parent, false); b.transform.position = centre; b.transform.localScale = taille;
        b.GetComponent<Renderer>().sharedMaterial = m;
    }

    static TextMeshPro Texte(Transform parent, string contenu, TMP_FontAsset police, float taille, Color couleur)
    {
        var go = new GameObject("Etiquette", typeof(TextMeshPro)); go.transform.SetParent(parent, false);
        var t = go.GetComponent<TextMeshPro>();
        t.font = police; t.text = contenu; t.fontSize = taille; t.color = couleur; t.alignment = TextAlignmentOptions.Center;
        t.textWrappingMode = TextWrappingModes.NoWrap; t.rectTransform.sizeDelta = new Vector2(4, 1);
        return t;
    }

    void LateUpdate()
    {
        if (vue == null) return;
        angle += Time.unscaledDeltaTime * 9;
        float a = angle * Mathf.Deg2Rad * .6f;
        // Balancement autour de l'axe face au podium (±35°), sans passer derrière les marches.
        float balance = Mathf.Sin(a) * 35 * Mathf.Deg2Rad;
        Vector3 oeil = centre + new Vector3(Mathf.Sin(balance) * 7.5f, 2.3f, Mathf.Cos(balance) * 7.5f);
        Vector3 cible = centre + Vector3.up * 1.15f;
        var regard = Quaternion.LookRotation(cible - oeil);
        // Décalage : le podium à droite de l'écran, la colonne de résultats à gauche.
        vue.transform.SetPositionAndRotation(oeil, regard * Quaternion.Euler(0, -12, 0));
        vue.fieldOfView = 40;
        if (gagnant != null)
        {
            float saut = Mathf.Max(0, Mathf.Sin(Time.unscaledTime * 3.2f)) * .18f;
            gagnant.position = new Vector3(gagnant.position.x, baseGagnant + saut, gagnant.position.z);
        }
        // Les personnages tournent lentement sur eux-mêmes : toutes leurs taches passent devant la caméra.
        foreach (var (tete, _) in etiquettes) tete.Rotate(0, 24 * Time.unscaledDeltaTime, 0, Space.World);
        foreach (var (tete, texte) in etiquettes)
        {
            texte.transform.position = tete.position + Vector3.up * (PaintballSolo.Taille * PaintballSolo.Echelle + .35f);
            texte.transform.rotation = Quaternion.LookRotation(texte.transform.position - vue.transform.position);
        }
    }

    void OnDestroy() { if (actuel == this) actuel = null; }
}

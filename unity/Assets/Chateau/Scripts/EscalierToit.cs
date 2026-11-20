using UnityEngine;

// Accès au toit : escalier raide (échelle de meunier, 14 marches) dans le passage nord des combles, contre le
// mur du noyau (combles.json « passage_nord » : x −3,5…3,55 ; y −3,0…−1,45 ; sol 10,3 ; plafond 13,02), qui monte
// vers la trappe relevée (x 0,5…1,37 ; y −2,82…−1,92). En haut des marches accessibles, E fait passer par la trappe : le joueur grimpe (≈1,2 s) jusqu'à une
// sortie de toit posée sur la partie la plus plate de la toiture ; la trappe du toit le ramène sur l'escalier.
// Construit au chargement, sans toucher aux modèles Blender (le plafond n'est pas percé : le passage est scripté).
public class EscalierToit : MonoBehaviour
{
    // Repère Unity : x = −x D-003, z = y D-003, y = altitude (RDC = 0).
    const float Sol = 10.3f, Plafond = 13.02f, X0 = -3.36f, X1 = -0.5f, Z0 = -2.17f, Z1 = -1.53f;
    const int Marches = 14;
    public static Vector3 HautEscalier { get; private set; }
    public static Vector3 SortieToit { get; private set; }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        if (GameObject.Find("Chateau") == null || Object.FindAnyObjectByType<PaintballSolo>() == null) return;
        new GameObject("EscalierToit").AddComponent<EscalierToit>().Construire();
    }

    void Construire()
    {
        var lit = Shader.Find("Universal Render Pipeline/Lit");
        var bois = new Material(lit); bois.SetColor("_BaseColor", new Color(.42f, .27f, .15f)); bois.SetFloat("_Smoothness", .35f);
        var fer = new Material(lit); fer.SetColor("_BaseColor", new Color(.1f, .1f, .1f)); fer.SetFloat("_Smoothness", .5f); fer.SetFloat("_Metallic", .6f);
        var noir = new Material(Shader.Find("Universal Render Pipeline/Unlit")); noir.SetColor("_BaseColor", new Color(.02f, .02f, .02f));
        float giron = (X1 - X0) / Marches, hauteur = (Plafond - Sol) / Marches;
        var combine = new CombineInstance[Marches + 2];
        var cube = Resources.GetBuiltinResource<Mesh>("Cube.fbx");
        for (int i = 0; i < Marches; i++)
        {
            // Marche pleine (du sol à son dessus) : collisions simples et sans vide dessous.
            float h = (i + 1) * hauteur, x = X0 + (i + .5f) * giron;
            var c = gameObject.AddComponent<BoxCollider>();
            c.center = new Vector3(x, Sol + h * .5f, (Z0 + Z1) * .5f); c.size = new Vector3(giron, h, Z1 - Z0);
            combine[i] = new CombineInstance { mesh = cube, transform = Matrix4x4.TRS(new Vector3(x, Sol + h - .025f, (Z0 + Z1) * .5f), Quaternion.identity, new Vector3(giron + .02f, .05f, Z1 - Z0)) };
        }
        // Limons (côtés) le long de la pente
        float longueur = Mathf.Sqrt((X1 - X0) * (X1 - X0) + (Plafond - Sol) * (Plafond - Sol)), pente = Mathf.Atan2(Plafond - Sol, X1 - X0) * Mathf.Rad2Deg;
        Vector3 milieu = new((X0 + X1) * .5f, (Sol + Plafond) * .5f - .1f, 0);
        combine[Marches] = new CombineInstance { mesh = cube, transform = Matrix4x4.TRS(milieu + Vector3.forward * (Z1 + .03f), Quaternion.Euler(0, 0, pente), new Vector3(longueur, .28f, .05f)) };
        combine[Marches + 1] = new CombineInstance { mesh = cube, transform = Matrix4x4.TRS(milieu + Vector3.forward * (Z0 - .02f), Quaternion.Euler(0, 0, pente), new Vector3(longueur, .28f, .04f)) };
        var maillage = new Mesh { name = "EscalierToit" }; maillage.CombineMeshes(combine, true, true);
        var vis = new GameObject("Marches"); vis.transform.SetParent(transform, false);
        vis.AddComponent<MeshFilter>().sharedMesh = maillage; vis.AddComponent<MeshRenderer>().sharedMaterial = bois;
        // Main courante côté libre
        var main = GameObject.CreatePrimitive(PrimitiveType.Cylinder); Destroy(main.GetComponent<Collider>());
        main.transform.SetParent(transform, false); main.transform.position = milieu + new Vector3(0, .9f, Z1 + .05f);
        main.transform.rotation = Quaternion.Euler(0, 0, pente - 90); main.transform.localScale = new Vector3(.04f, longueur * .5f, .04f);
        main.GetComponent<Renderer>().sharedMaterial = fer;
        // Trémie : cadre sombre sous le plafond au-dessus des dernières marches
        var tremie = GameObject.CreatePrimitive(PrimitiveType.Cube); Destroy(tremie.GetComponent<Collider>());
        tremie.transform.SetParent(transform, false); tremie.transform.position = new Vector3(X1 - .75f, Plafond - .03f, (Z0 + Z1) * .5f);
        tremie.transform.localScale = new Vector3(1.4f, .04f, Z1 - Z0 + .1f); tremie.GetComponent<Renderer>().sharedMaterial = noir;

        // Dernière marche où l'on tient debout (tête sous le plafond) : trappe à portée de main.
        int haute = Mathf.Clamp(Mathf.FloorToInt((Plafond - PaintballSolo.Taille - .1f - Sol) / hauteur) - 1, 0, Marches - 1);
        HautEscalier = new Vector3(X0 + (haute + .5f) * giron, Sol + (haute + 1) * hauteur + .05f, (Z0 + Z1) * .5f);
        var poignee = new GameObject("TrappeEscalier"); poignee.transform.SetParent(transform, false);
        poignee.transform.position = new Vector3(X1 - .75f, Plafond - .3f, (Z0 + Z1) * .5f);
        var zone = poignee.AddComponent<BoxCollider>(); zone.size = new Vector3(1.4f, .5f, Z1 - Z0);
        poignee.AddComponent<Trappe>().versToit = true;

        SortieToit = ChercherToit();
        var trappe = GameObject.CreatePrimitive(PrimitiveType.Cube); trappe.name = "TrappeToit";
        trappe.transform.SetParent(transform, false); trappe.transform.position = SortieToit + new Vector3(0, .06f, -1.2f);
        trappe.transform.localScale = new Vector3(.9f, .12f, .9f); trappe.GetComponent<Renderer>().sharedMaterial = bois;
        trappe.AddComponent<Trappe>().versToit = false;
    }

    // Partie la plus plate et la plus haute de la toiture au-dessus du corps central (rayons depuis le ciel).
    static Vector3 ChercherToit()
    {
        Vector3 meilleur = new(0, 17, 0); float score = float.MinValue;
        for (float x = -16; x <= 16; x += 1f)
            for (float z = -8; z <= 8; z += 1f)
            {
                if (!Physics.Raycast(new Vector3(x, 40, z), Vector3.down, out var h, 40, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) continue;
                if (h.point.y < 12) continue;
                // Assez de place à plat autour (1,2 m) pour poser le pied et la trappe.
                bool plat = h.normal.y > .96f;
                foreach (var d in new[] { Vector3.forward, Vector3.back, Vector3.left, Vector3.right })
                    if (!Physics.Raycast(new Vector3(x, 40, z) + d * 1.2f, Vector3.down, out var v, 40) || Mathf.Abs(v.point.y - h.point.y) > .25f) plat = false;
                float s = (plat ? 100 : 0) + h.normal.y * 10 - new Vector2(x + .9f, z + 1.8f).magnitude * .3f;
                if (s > score) { score = s; meilleur = h.point; }
            }
        return meilleur + Vector3.up * .08f;
    }
}

// Trappe (escalier ↔ toit) : E pour passer.
public class Trappe : MonoBehaviour, IInteractif
{
    public bool versToit;
    public string Libelle(Explorateur e) => versToit ? "Monter sur le toit" : "Redescendre par la trappe";
    public void Interagir(Explorateur e)
    {
        if (versToit) e.GrimperVers(new Vector3(e.transform.position.x, EscalierToit.SortieToit.y + .6f, e.transform.position.z), EscalierToit.SortieToit, 1.3f);
        else e.GrimperVers(new Vector3(EscalierToit.HautEscalier.x, EscalierToit.SortieToit.y, EscalierToit.HautEscalier.z), EscalierToit.HautEscalier, 1.3f);
    }
}

using System.Globalization;
using UnityEngine;

// Contrôle visuel navigateur (?vue=1) : unityInstance.SendMessage('VerificationVue', 'Vue', 'x,y,z,cap,tangage')
// fige la caméra à hauteur d'œil sur un point Blender D-003 (pieds), cap en degrés (0 = vers le sud, +Y D-003).
[DefaultExecutionOrder(10000)]
public class VerificationVue : MonoBehaviour
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer() { if (Application.absoluteURL.Contains("vue=1")) new GameObject("VerificationVue").AddComponent<VerificationVue>(); }

    bool actif, entre;
    Vector3 oeil;
    Quaternion regard;

    public void Vue(string arguments)
    {
        // Préréglages du toit (objets créés au lancement) : « carte », « lunette » (équipe la lunette et vise).
        // « portes » : ouvre toutes les portes ; « grandecarte » : ouvre la carte du toit en grand.
        if (arguments == "portes") { foreach (var p in FindObjectsByType<Porte>(FindObjectsSortMode.None)) if (!p.Ouverte) p.Basculer(p.transform.position + p.transform.forward); return; }
        if (arguments == "grandecarte") { FindAnyObjectByType<CarteDomaine>()?.Interagir(FindAnyObjectByType<Explorateur>()); return; }
        if (arguments == "velo" || arguments == "neige") { StartCoroutine(arguments == "velo" ? Velo() : NeigeEssai()); return; }
        if (arguments == "carte" || arguments == "lunette")
        {
            if (!entre) { FindAnyObjectByType<InterfaceVisite>()?.Entrer(0); entre = true; }
            Vector3 t = EscalierToit.SortieToit;
            var j = FindAnyObjectByType<Explorateur>();
            if (arguments == "carte")
            {
                oeil = t + new Vector3(-.2f, 1.6f, -1.2f);
                Vector3 vers = t + new Vector3(1.6f, 1.3f, .4f) - oeil;
                regard = Quaternion.LookRotation(vers.normalized, Vector3.up); actif = true;
                if (j != null) { var c = j.GetComponent<CharacterController>(); if (c != null) c.enabled = false; j.enabled = false; }
                return;
            }
            actif = false;
            if (j != null) StartCoroutine(Lunette(j, t));
            return;
        }
        var v = arguments.Split(',');
        float F(int i) => i < v.Length ? float.Parse(v[i], CultureInfo.InvariantCulture) : 0f;
        if (!entre) { FindAnyObjectByType<InterfaceVisite>()?.Entrer(0); entre = true; }
        var ex = FindAnyObjectByType<Explorateur>();
        if (ex != null)
        {
            var cc = ex.GetComponent<CharacterController>();
            if (cc != null) cc.enabled = false;
            ex.enabled = false;
        }
        var racine = GameObject.Find("Chateau").transform;
        // Blender (x, y, z) → Unity (-x, z, -y), puis le miroir D-026 de la racine (comme Capture).
        oeil = racine.TransformPoint(new Vector3(-F(0), F(2) + 1.6f, -F(1)));
        float cap = F(3) * Mathf.Deg2Rad;
        Vector3 dir = racine.TransformVector(new Vector3(-Mathf.Sin(cap), 0f, -Mathf.Cos(cap))).normalized;
        regard = Quaternion.LookRotation(dir, Vector3.up) * Quaternion.Euler(-F(4), 0f, 0f);
        if (ex != null) ex.transform.position = oeil + Vector3.down * 1.55f;
        actif = true;
    }

    // Partie lancée (le tir n'est actif qu'en partie), joueur posé sur le toit face au sud, lunette en visée.
    System.Collections.IEnumerator Lunette(Explorateur j, Vector3 t)
    {
        var partie = Partie();
        yield return new WaitForSeconds(1f);
        var c = j.GetComponent<CharacterController>(); if (c != null) c.enabled = false;
        j.transform.SetPositionAndRotation(t + Vector3.up * .1f, Quaternion.LookRotation(Vector3.forward));
        j.RetablirRegard(Quaternion.Euler(4, 0, 0));
        if (c != null) c.enabled = true;
        Physics.SyncTransforms();
        LunettePaintball.Equiper(partie);
        LunettePaintball.ForcerVisee = true;
    }

    [System.Serializable] class Rapport { public string essai; public bool ok, monte; public float deplacement, vitesse; public int tirs, empreintes, taches, tachesLevees; }
    void Publier(Rapport r)
    {
        var json = JsonUtility.ToJson(r); Debug.Log("VUE VERIFICATION " + json);
#if UNITY_WEBGL && !UNITY_EDITOR
        VerificationNavigateur(json);
#endif
    }
#if UNITY_WEBGL && !UNITY_EDITOR
    [System.Runtime.InteropServices.DllImport("__Internal")] static extern void VerificationNavigateur(string json);
#endif

    PaintballSolo Partie()
    {
        Explorateur.Essai = true;
        var ex = FindAnyObjectByType<Explorateur>(); if (ex != null) ex.enabled = true;
        if (!entre) { FindAnyObjectByType<InterfaceVisite>()?.Entrer(0); entre = true; }
        var p = FindAnyObjectByType<PaintballSolo>(); if (!p.Active) p.Demarrer(); return p;
    }
    void Teleporter(Explorateur j, Vector3 p, Vector3 regarde)
    {
        var c = j.GetComponent<CharacterController>(); if (c != null) c.enabled = false;
        Vector3 d = regarde - p; d.y = 0;
        j.transform.SetPositionAndRotation(p, Quaternion.LookRotation(d.normalized)); j.RetablirRegard(Quaternion.identity);
        if (c != null) c.enabled = true; Physics.SyncTransforms();
    }

    // Vélo cargo : monter, rouler 3 s, tirer en roulant ; vue en 3e personne.
    System.Collections.IEnumerator Velo()
    {
        actif = false;
        var partie = Partie(); yield return new WaitForSeconds(1f);
        var j = partie.GetComponent<Explorateur>(); var v = VeloCargo.Instance; var r = new Rapport { essai = "velo" };
        if (v != null)
        {
            Teleporter(j, v.transform.position - v.transform.right * 1.2f, v.transform.position);
            yield return null;
            v.Interagir(j); r.monte = j.Monture == v;
            if (!partie.TroisiemePersonne) partie.BasculerVue();
            Vector3 depart = v.transform.position;
            j.EssaiEntree("0.3:1:3");
            for (int k = 0; k < 12; k++) { yield return new WaitForSeconds(.25f); if (partie.Tirer()) r.tirs++; }
            r.vitesse = v.Vitesse; r.deplacement = Vector3.Distance(depart, v.transform.position);
        }
        r.ok = r.monte && r.deplacement > 3 && r.tirs > 0;
        Publier(r);
    }

    // Neige : couverture complète d'emblée, marche (pas forcés image par image) de la cour nord gravillonnée vers la
    // pelouse à l'ouest, quatre tirs au sol, puis vue fixe en surplomb des traces.
    System.Collections.IEnumerator NeigeEssai()
    {
        actif = false;
        var partie = Partie(); yield return new WaitForSeconds(.5f);
        var j = partie.GetComponent<Explorateur>(); var r = new Rapport { essai = "neige" };
        LunettePaintball.ForcerVisee = false;
        if (j.Monture != null) j.Descendre();
        Reglages.Neige = true; Neige.Couvrir();
        yield return null; yield return null;
        var racine = GameObject.Find("Chateau").transform;
        Vector3 P(float x, float y) => racine.TransformPoint(new Vector3(-x, 0, -y));
        Vector3 a = P(2, -21), b = P(-22, -21);
        var c = j.GetComponent<CharacterController>(); c.enabled = false;
        for (int k = 0; k <= 60; k++)
        {
            Vector3 p = Vector3.Lerp(a, b, k / 60f);
            if (Physics.Raycast(p + Vector3.up * 5, Vector3.down, out var h, 12, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) p = h.point;
            j.transform.SetPositionAndRotation(p + Vector3.up * .05f, Quaternion.LookRotation(b - a));
            yield return null;
        }
        c.enabled = true;
        r.empreintes = CompterNoms("Empreinte");
        // Tirs au sol devant soi, en regardant vers le bas.
        for (int k = 0; k < 4; k++)
        {
            j.RetablirRegard(Quaternion.Euler(50, (k - 1.5f) * 15, 0));
            yield return null;
            if (partie.Tirer()) r.tirs++;
            yield return new WaitForSeconds(.3f);
        }
        yield return new WaitForSeconds(1.2f);
        r.taches = CompterNoms("ImpactPeinture");
        foreach (var t in FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None))
            if (t.name == "ImpactPeinture" && Vehicule.Sol(t.bounds.center) < t.bounds.center.y - .03f) r.tachesLevees++;
        r.ok = r.empreintes > 4 && r.taches > 0;
        Publier(r);
        Vector3 m = Vector3.Lerp(a, b, .55f);
        oeil = m + (a - b).normalized * 0f + Vector3.Cross(Vector3.up, (b - a).normalized) * 5f + Vector3.up * 4f;
        regard = Quaternion.LookRotation((m - oeil).normalized);
        j.enabled = false; actif = true;
    }
    static int CompterNoms(string nom) { int n = 0; foreach (var t in FindObjectsByType<Transform>(FindObjectsSortMode.None)) if (t.name == nom && t.gameObject.activeInHierarchy) n++; return n; }

    void LateUpdate()
    {
        if (!actif || Camera.main == null) return;
        Camera.main.transform.SetPositionAndRotation(oeil, regard);
        Camera.main.fieldOfView = 70f;
    }
}

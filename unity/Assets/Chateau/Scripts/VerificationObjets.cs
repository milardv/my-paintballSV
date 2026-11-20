using System;
using System.Collections;
using UnityEngine;

// Vérification navigateur des objets du domaine (?objets=1) : chaque objet est atteignable et ramassé, la boule
// tache, le pastis brouille, le tracteur démarre avec les clés et avance. Rapport dans window.paintballVerification.
public class VerificationObjets : MonoBehaviour
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer() { if (Application.absoluteURL.Contains("objets=1")) new GameObject("VerificationObjets").AddComponent<VerificationObjets>(); }

    [Serializable] class Rapport { public bool fini, ok, cles, kepi, gilet, flou, boules, eclaboussure, tracteurRefuse, tracteurMonte, tracteurAvance; public int objets, visables, impactsAvant, impactsApres; public float deplacement; public string positions = "", erreur = ""; }
    readonly Rapport r = new();

    IEnumerator Start()
    {
        yield return new WaitForSeconds(3f);
        FindAnyObjectByType<InterfaceVisite>().Entrer(0); yield return new WaitForSeconds(1f);
        var ex = FindAnyObjectByType<Explorateur>(); var p = FindAnyObjectByType<PaintballSolo>(); var cc = ex.GetComponent<CharacterController>();
        void Aller(Vector3 cible, float recul)
        {
            Vector3 d = cible - ex.transform.position; d.y = 0; if (d.sqrMagnitude < .01f) d = Vector3.forward; d.Normalize();
            cc.enabled = false; ex.transform.SetPositionAndRotation(cible - d * recul + Vector3.up * .1f, Quaternion.LookRotation(d)); cc.enabled = true; Physics.SyncTransforms();
        }
        var tracteur = Tracteur.Instance;
        if (tracteur != null)
        {
            Aller(tracteur.transform.position, 2f); yield return null;
            tracteur.Interagir(ex); r.tracteurRefuse = ex.Monture == null;
        }
        foreach (var o in FindObjectsByType<ObjetsDomaine.Ramassable>(FindObjectsSortMode.None))
        {
            r.objets++; r.positions += $"{o.name}:{o.transform.position.x:F1},{o.transform.position.y:F2},{o.transform.position.z:F1} ";
            // Approche sous plusieurs angles (l'établi est contre le mur du fond de la grange).
            Vector3 centre = o.GetComponent<BoxCollider>().bounds.center; RaycastHit h = default; bool vu = false;
            for (int k = 0; k < 8 && !vu; k++)
            {
                Vector3 d = Quaternion.Euler(0, k * 45, 0) * Vector3.forward;
                cc.enabled = false; ex.transform.SetPositionAndRotation(o.transform.position - d * 1.4f + Vector3.up * .1f, Quaternion.LookRotation(d)); cc.enabled = true; Physics.SyncTransforms();
                yield return new WaitForSeconds(.15f);
                Vector3 oeil = ex.transform.position + Vector3.up * 1.4f;
                vu = Physics.Raycast(oeil, (centre - oeil).normalized, out h, 3f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) && h.collider.GetComponentInParent<ObjetsDomaine.Ramassable>() == o;
            }
            if (vu) r.visables++;
            else r.positions += $"(cache par {(h.collider != null ? h.collider.name : "rien")}) ";
            o.Interagir(ex);
        }
        r.cles = ObjetsDomaine.ClesTracteur; r.kepi = ObjetsDomaine.KepiPorte; r.gilet = ObjetsDomaine.Gilet == 3;
        yield return new WaitForSeconds(.5f); r.flou = ObjetsDomaine.Flou > 0; r.boules = ObjetsDomaine.Boules == 3;
        r.impactsAvant = p.impacts.Nombre;
        ObjetsDomaine.Instance.LancerBoule();
        yield return new WaitForSeconds(2.5f);
        r.impactsApres = p.impacts.Nombre; r.eclaboussure = r.impactsApres > r.impactsAvant;
        if (tracteur != null)
        {
            Aller(tracteur.transform.position, 2f); yield return null;
            tracteur.Interagir(ex); r.tracteurMonte = ex.Monture == tracteur;
            Vector3 depart = tracteur.transform.position;
            ex.EssaiEntree("0:1:3"); yield return new WaitForSeconds(3.2f);
            r.deplacement = Vector3.Distance(depart, tracteur.transform.position); r.tracteurAvance = r.deplacement > 2f;
            if (r.tracteurAvance == false) r.erreur += "obstacle:" + tracteur.DernierObstacle;
            ex.Descendre();
        }
        r.ok = r.objets == 5 && r.visables == 5 && r.cles && r.kepi && r.gilet && r.flou && r.boules && r.eclaboussure && r.tracteurRefuse && r.tracteurMonte && r.tracteurAvance;
        r.fini = true;
        var json = JsonUtility.ToJson(r); Debug.Log("OBJETS VERIFICATION " + json);
#if UNITY_WEBGL && !UNITY_EDITOR
        VerificationNavigateur(json);
#endif
    }
#if UNITY_WEBGL && !UNITY_EDITOR
    [System.Runtime.InteropServices.DllImport("__Internal")] static extern void VerificationNavigateur(string json);
#endif
}

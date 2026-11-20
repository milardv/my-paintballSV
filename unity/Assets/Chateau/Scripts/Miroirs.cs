using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

// Miroirs réfléchissants : toute surface dont le matériau s'appelle « …miroir… » (vestibule, porte-manteau, chambres).
// Les deux miroirs visibles les plus proches sont rendus chaque image par une caméra posée au symétrique de la caméra
// du joueur, à plan de coupe oblique sur la glace ; les autres gardent leur matériau d'origine. Le corps du joueur,
// masqué en vue subjective, n'est affiché que pendant le rendu du reflet.
public class Miroirs : MonoBehaviour
{
    const int Actifs = 2;
    const float Portee = 14f;

    class Miroir
    {
        public Renderer rendu;
        public Material[] origine, reflet;
        public Vector3 point, normale;
        public RenderTexture cible;
        public bool actif;
    }

    readonly List<Miroir> miroirs = new();
    Camera camReflet;
    Material modele;
    PaintballSolo joueur;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        if (GameObject.Find("Chateau") == null || FindAnyObjectByType<Miroirs>() != null) return;
        new GameObject("Miroirs").AddComponent<Miroirs>();
    }

    void Start() => Preparer();

    // Public pour les contrôles dans l'éditeur (rendu hors lecture).
    public void Preparer()
    {
        var shader = Resources.Load<Material>("Miroirs/MiroirReflet");
        if (shader == null) { enabled = false; return; }
        modele = shader;
        joueur = FindAnyObjectByType<PaintballSolo>();
        foreach (var r in GameObject.Find("Chateau").GetComponentsInChildren<MeshRenderer>(true))
        {
            var mats = r.sharedMaterials;
            int i = System.Array.FindIndex(mats, m => m != null && m.name.ToLowerInvariant().Contains("miroir"));
            var filtre = r.GetComponent<MeshFilter>();
            if (i < 0 || filtre == null || filtre.sharedMesh == null) continue;
            var mesh = filtre.sharedMesh;
            if (i >= mesh.subMeshCount) continue;
            var tri = mesh.GetTriangles(i);
            if (tri.Length < 3) continue;
            var v = mesh.vertices;
            Vector3 a = r.transform.TransformPoint(v[tri[0]]), b = r.transform.TransformPoint(v[tri[1]]), c = r.transform.TransformPoint(v[tri[2]]);
            var n = Vector3.Cross(b - a, c - a).normalized;
            if (n.sqrMagnitude < .5f) continue;
            // La glace regarde vers la pièce : le côté libre, l'autre butant sur le mur ou le fond du meuble.
            Vector3 centre = Vector3.zero;
            foreach (int k in tri) centre += r.transform.TransformPoint(v[k]);
            centre /= tri.Length;
            bool devant = Physics.Raycast(centre + n * .02f, n, .4f, ~0, QueryTriggerInteraction.Ignore);
            bool derriere = Physics.Raycast(centre - n * .02f, -n, .4f, ~0, QueryTriggerInteraction.Ignore);
            if (devant && !derriere) n = -n;
            a = centre;
            var reflet = (Material[])mats.Clone();
            reflet[i] = new Material(modele);
            miroirs.Add(new Miroir { rendu = r, origine = mats, reflet = reflet, point = a, normale = n });
        }
        var go = new GameObject("CameraReflet");
        go.transform.SetParent(transform, false);
        camReflet = go.AddComponent<Camera>();
        camReflet.enabled = false;
        var donnees = go.AddComponent<UniversalAdditionalCameraData>();
        donnees.renderShadows = false;
        donnees.renderPostProcessing = false;
        Debug.Log($"MIROIRS {miroirs.Count}");
    }

    void LateUpdate() => RendreReflets();

    public void RendreReflets()
    {
        var cam = Camera.main;
        if (cam == null || miroirs.Count == 0) return;
        Vector3 oeil = cam.transform.position;
        var choisis = miroirs
            .Where(m => m.rendu.isVisible && Vector3.Dot(oeil - m.point, m.normale) > .05f
                        && (m.rendu.bounds.ClosestPoint(oeil) - oeil).sqrMagnitude < Portee * Portee)
            .OrderBy(m => (m.rendu.bounds.ClosestPoint(oeil) - oeil).sqrMagnitude).Take(Actifs).ToList();
        foreach (var m in miroirs)
            if (!choisis.Contains(m) && m.actif) { m.rendu.sharedMaterials = m.origine; m.actif = false; }
        if (choisis.Count == 0) return;

        bool corpsVisible = joueur != null && joueur.personnage != null && joueur.personnage.activeSelf;
        if (joueur != null && joueur.personnage != null && !corpsVisible) joueur.personnage.SetActive(true);
        try
        {
            foreach (var m in choisis) Rendre(cam, m);
        }
        finally
        {
            if (joueur != null && joueur.personnage != null && !corpsVisible) joueur.personnage.SetActive(false);
        }
    }

    void Rendre(Camera cam, Miroir m)
    {
        int w = Mathf.Max(64, cam.pixelWidth / 2), h = Mathf.Max(64, cam.pixelHeight / 2);
        if (m.cible == null || m.cible.width != w || m.cible.height != h)
        {
            if (m.cible != null) m.cible.Release();
            m.cible = new RenderTexture(w, h, 24, RenderTextureFormat.Default) { name = "Reflet_" + m.rendu.name };
            m.reflet.First(x => x.shader == modele.shader).SetTexture("_ReflectionTex", m.cible);
        }
        Vector3 n = m.normale, p = m.point;
        Vector3 Sym(Vector3 v) => v - 2 * Vector3.Dot(v, n) * n;
        Vector3 pos = cam.transform.position;
        camReflet.CopyFrom(cam);
        camReflet.enabled = false;
        camReflet.targetTexture = m.cible;
        camReflet.transform.SetPositionAndRotation(pos - 2 * Vector3.Dot(pos - p, n) * n,
            Quaternion.LookRotation(Sym(cam.transform.forward), Sym(cam.transform.up)));
        camReflet.ResetProjectionMatrix();
        camReflet.projectionMatrix = cam.projectionMatrix;
        // Plan de coupe oblique sur la glace : rien de ce qui est derrière le miroir n'apparaît.
        Matrix4x4 vue = camReflet.worldToCameraMatrix;
        Vector3 pc = vue.MultiplyPoint(p + n * .01f), nc = vue.MultiplyVector(n).normalized;
        camReflet.projectionMatrix = camReflet.CalculateObliqueMatrix(new Vector4(nc.x, nc.y, nc.z, -Vector3.Dot(pc, nc)));
        var demande = new UniversalRenderPipeline.SingleCameraRequest { destination = m.cible };
        if (RenderPipeline.SupportsRenderRequest(camReflet, demande)) RenderPipeline.SubmitRenderRequest(camReflet, demande);
        else camReflet.Render();
        if (!m.actif) { m.rendu.sharedMaterials = m.reflet; m.actif = true; }
    }

    void OnDestroy()
    {
        foreach (var m in miroirs) if (m.cible != null) m.cible.Release();
    }
}

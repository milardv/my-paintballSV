using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Rend ouvrables les portes-fenêtres du rez-de-chaussée (façade sud, pans coupés, faces est et ouest) et les
// fenêtres de l'étage (pour tirer depuis l'étage) :
// chaque menuiserie et son vitrage sont coupés en dormant fixe (cadre, imposte, seuil) et deux vantaux
// pendus à des gonds « porte_fenetre_<baie>_g/d », qui reçoivent ensuite le composant Porte.
// Cotes des baies et des menuiseries : scripts/composants/bati.py (TYPES, fab_menuiserie).
public static class PortesFenetres
{
    const float Dormant = .065f;

    public static void Preparer(GameObject bati, string dossier)
    {
        var parties = bati.GetComponentsInChildren<MeshFilter>()
            .Where(m => (m.name.StartsWith("bati_menuiserie_") || m.name.StartsWith("bati_vitrage_"))
                && (m.name.Contains("_pf_rdc_") || m.name.Contains("_pf_pan_") || m.name.Contains("_f_etage_")) && !m.name.Contains("_vantail_"))
            .ToArray();
        if (parties.Length == 0) throw new System.InvalidOperationException("Portes-fenêtres du rez-de-chaussée absentes");
        string maillages = dossier + "/PortesFenetres";
        Directory.CreateDirectory(maillages);
        var origines = parties.Where(m => m.name.StartsWith("bati_menuiserie_"))
            .ToDictionary(m => m.name.Substring("bati_menuiserie_".Length), m => m.transform);
        // Bâti recalé (relevé du 19/11) : l'orientation de la baie est dans les sommets ; on la remet dans le transform.
        var reperes = parties.Where(m => m.name.StartsWith("bati_menuiserie_"))
            .ToDictionary(m => m.name.Substring("bati_menuiserie_".Length), m => AxeLargeur(m.sharedMesh));
        // Le recalage peut aussi élargir et décentrer la baie : centre et largeur pris sur la menuiserie.
        // Boîte de chaque menuiserie (dans le repère redressé) : largeur, centre et plan des vantaux.
        var cadres = reperes.ToDictionary(e => e.Key, e =>
        {
            var inverse = Quaternion.Inverse(e.Value);
            var sommets = origines[e.Key].GetComponent<MeshFilter>().sharedMesh.vertices;
            var b = new Bounds(inverse * sommets[0], Vector3.zero);
            foreach (var p in sommets) b.Encapsulate(inverse * p);
            return b;
        });
        var demiLargeurs = cadres.ToDictionary(e => e.Key, e => e.Value.extents.x);
        foreach (var partie in parties)
        {
            string baie = partie.name.Substring(partie.name.IndexOf("_", "bati_".Length) + 1);
            if (cadres.TryGetValue(baie, out var cadre) && (Quaternion.Angle(reperes[baie], Quaternion.identity) > .5f || Mathf.Abs(cadre.center.x) > .01f))
                Redresser(partie, reperes[baie], cadre.center.x);
        }
        int baies = 0;
        foreach (var partie in parties)
        {
            string baie = partie.name.Substring(partie.name.IndexOf("_", "bati_".Length) + 1);
            if (!origines.TryGetValue(baie, out var origine)) continue;
            bool pan = baie.Contains("_pf_pan_"), etage = baie.Contains("_f_etage_"), cote = baie.Contains("_f_etage_ac_");
            // Cotes de bati.py (TYPES) : largeur, hauteur de la menuiserie.
            float largeur = demiLargeurs.TryGetValue(baie, out float demi) ? 2 * demi : pan || cote ? 1.10f : etage ? 1.35f : 1.45f;
            float hauteur = pan ? 3.30f : etage ? 3.10f : 3.70f;
            float xi = largeur / 2 - Dormant;
            float zt = hauteur > 2.6f ? hauteur - .62f - .03f : hauteur - Dormant;
            string cle = baie.Replace(',', '_').Replace('+', 'p').Replace('-', 'm');
            var gonds = new Transform[2];
            for (int c = 0; c < 2; c++)
            {
                string nom = "porte_fenetre_" + cle + (c == 0 ? "_g" : "_d");
                var gond = origine.Find(nom);
                if (gond == null)
                {
                    gond = new GameObject(nom).transform;
                    gond.SetParent(origine, false);
                    // Gond dans le plan des vantaux (la menuiserie n'est pas à z = 0 depuis le relevé du 19/11).
                    float zc = cadres.TryGetValue(baie, out var cb) ? cb.center.z : 0f;
                    gond.localPosition = new Vector3(c == 0 ? -xi : xi, 0f, zc);
                }
                gonds[c] = gond;
            }

            Mesh source = partie.sharedMesh;
            Vector3[] sommets = source.vertices;
            var triangles = new List<int>[3];
            for (int i = 0; i < 3; i++) triangles[i] = new List<int>();
            int[] indices = source.triangles;
            for (int i = 0; i < indices.Length; i += 3)
            {
                Vector3 a = sommets[indices[i]], b = sommets[indices[i + 1]], c = sommets[indices[i + 2]];
                float xMin = Mathf.Min(a.x, b.x, c.x), xMax = Mathf.Max(a.x, b.x, c.x);
                bool dansBaie = Mathf.Min(a.y, b.y, c.y) >= Dormant - .005f && Mathf.Max(a.y, b.y, c.y) <= zt + .005f
                    && Mathf.Max(Mathf.Abs(xMin), Mathf.Abs(xMax)) <= xi + .001f;
                int groupe = 2;
                // Espagnolette (tringle centrale) : avec le vantail droit, sinon elle resterait au milieu du passage.
                if (dansBaie && xMin > -.02f && xMax < .02f && xMax - xMin < .03f) groupe = 1;
                else if (dansBaie && (xMin >= -.001f || xMax <= .001f)) groupe = a.x + b.x + c.x < 0f ? 0 : 1;
                triangles[groupe].AddRange(new[] { indices[i], indices[i + 1], indices[i + 2] });
            }
            if (triangles[0].Count == 0 || triangles[1].Count == 0)
                throw new System.InvalidOperationException("Vantaux introuvables dans " + partie.name);
            for (int groupe = 0; groupe < 3; groupe++)
            {
                Mesh copie = Object.Instantiate(source);
                copie.name = partie.name.Replace('/', '_').Replace(',', '_') + "_" + groupe;
                copie.subMeshCount = 1;
                copie.SetTriangles(triangles[groupe], 0);
                copie.RecalculateBounds();
                string chemin = maillages + "/" + copie.name + ".asset";
                Mesh existant = AssetDatabase.LoadAssetAtPath<Mesh>(chemin);
                if (existant == null) AssetDatabase.CreateAsset(copie, chemin);
                else
                {
                    EditorUtility.CopySerialized(copie, existant);
                    Object.DestroyImmediate(copie);
                    copie = existant;
                    EditorUtility.SetDirty(existant);
                }
                if (groupe == 2) partie.sharedMesh = copie;
                else
                {
                    var feuille = new GameObject(partie.name + "_vantail_" + groupe);
                    feuille.transform.SetPositionAndRotation(partie.transform.position, partie.transform.rotation);
                    feuille.transform.localScale = partie.transform.lossyScale;
                    feuille.transform.SetParent(gonds[groupe], true);
                    feuille.AddComponent<MeshFilter>().sharedMesh = copie;
                    feuille.AddComponent<MeshRenderer>().sharedMaterials = partie.GetComponent<MeshRenderer>().sharedMaterials;
                }
            }
            if (partie.name.StartsWith("bati_menuiserie_")) baies++;
        }
        AssetDatabase.SaveAssets();
        Debug.Log("CHATEAU portes-fenêtres et fenêtres d'étage ouvrables : " + baies);
    }

    // Rotation autour de la verticale qui amène l'axe x local sur la largeur de la baie (axe principal horizontal).
    static Quaternion AxeLargeur(Mesh mesh)
    {
        var v = mesh.vertices;
        float mx = v.Average(p => p.x), mz = v.Average(p => p.z), sxx = 0, szz = 0, sxz = 0;
        foreach (var p in v) { float dx = p.x - mx, dz = p.z - mz; sxx += dx * dx; szz += dz * dz; sxz += dx * dz; }
        float angle = .5f * Mathf.Atan2(2 * sxz, sxx - szz);
        return Quaternion.FromToRotation(Vector3.right, new Vector3(Mathf.Cos(angle), 0, Mathf.Sin(angle)));
    }

    static void Redresser(MeshFilter partie, Quaternion r, float centre)
    {
        Quaternion inverse = Quaternion.Inverse(r);
        Mesh mesh = Object.Instantiate(partie.sharedMesh);
        mesh.name = partie.sharedMesh.name;
        mesh.vertices = mesh.vertices.Select(p => inverse * p - Vector3.right * centre).ToArray();
        if (mesh.normals.Length > 0) mesh.normals = mesh.normals.Select(n => inverse * n).ToArray();
        mesh.RecalculateTangents();
        mesh.RecalculateBounds();
        partie.sharedMesh = mesh;
        partie.transform.SetPositionAndRotation(partie.transform.TransformPoint(r * (Vector3.right * centre)),
            partie.transform.rotation * r);
    }
}

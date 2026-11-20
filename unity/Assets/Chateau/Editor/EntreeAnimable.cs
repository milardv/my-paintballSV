using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Sépare les vantaux du GLB existant, en conservant dormant et imposte fixes.
public static class EntreeAnimable
{
    public static void Preparer(GameObject bati, string dossier)
    {
        var parties = bati.GetComponentsInChildren<MeshFilter>()
            .Where(m => m.name.StartsWith("bati_porte_entree_")).ToArray();
        if (parties.Length == 0) throw new System.InvalidOperationException("Porte d'entrée absente");
        var origine = parties[0].transform;
        // Cotes mesurées sur la menuiserie bois (le relevé du 19/11 a changé largeur et plan de la porte) :
        // vantaux à l'intérieur du dormant de 6,5 cm, gonds dans le plan des vantaux.
        var bois = parties.FirstOrDefault(p => p.name.EndsWith("_bois")) ?? parties[0];
        var cadre = bois.sharedMesh.bounds;
        const float Dormant = .065f;
        float demi = cadre.extents.x - Dormant, haut = cadre.max.y - Dormant;
        var gonds = new Transform[2];
        for (int cote = 0; cote < 2; cote++)
        {
            var gond = new GameObject("porte_entree_" + (cote == 0 ? "g" : "d")).transform;
            gond.SetParent(origine, false);
            gond.localPosition = new Vector3(cadre.center.x + (cote == 0 ? -demi : demi), 0f, cadre.center.z);
            gonds[cote] = gond;
        }
        string maillages = dossier + "/Entree";
        Directory.CreateDirectory(maillages);
        foreach (var partie in parties)
        {
            Mesh source = partie.sharedMesh;
            Vector3[] sommets = source.vertices;
            var triangles = new List<int>[3];
            for (int i = 0; i < 3; i++) triangles[i] = new List<int>();
            int[] indices = source.triangles;
            for (int i = 0; i < indices.Length; i += 3)
            {
                Vector3 a = sommets[indices[i]], b = sommets[indices[i + 1]], c = sommets[indices[i + 2]];
                bool dansVantail = Mathf.Max(a.y, b.y, c.y) <= haut + .001f
                    && Mathf.Max(Mathf.Abs(a.x - cadre.center.x), Mathf.Abs(b.x - cadre.center.x), Mathf.Abs(c.x - cadre.center.x)) <= demi + .001f;
                int groupe = dansVantail ? ((a.x + b.x + c.x) / 3 < cadre.center.x ? 0 : 1) : 2;
                triangles[groupe].AddRange(new[] { indices[i], indices[i + 1], indices[i + 2] });
            }
            for (int groupe = 0; groupe < 3; groupe++)
            {
                Mesh copie = Object.Instantiate(source);
                copie.name = partie.name + "_" + groupe;
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
                    feuille.transform.SetParent(gonds[groupe], false);
                    feuille.transform.localPosition = -gonds[groupe].localPosition;
                    feuille.AddComponent<MeshFilter>().sharedMesh = copie;
                    feuille.AddComponent<MeshRenderer>().sharedMaterials = partie.GetComponent<MeshRenderer>().sharedMaterials;
                }
            }
        }
        AssetDatabase.SaveAssets();
    }
}

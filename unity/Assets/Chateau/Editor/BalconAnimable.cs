using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Sépare les deux ouvrants de la porte-fenêtre d'étage, y compris ses vitrages.
public static class BalconAnimable
{
    public static void Preparer(GameObject bati, string dossier)
    {
        var parties = bati.GetComponentsInChildren<MeshFilter>()
            .Where(m => m.name.StartsWith("bati_menuiserie_S_pf_balcon") || m.name.StartsWith("bati_vitrage_S_pf_balcon"))
            .ToArray();
        if (parties.Length == 0) throw new System.InvalidOperationException("Porte-fenêtre d'étage absente");
        var origine = parties.First(m => m.name.StartsWith("bati_menuiserie_S_pf_balcon")).transform;
        string maillages = dossier + "/Balcon";
        Directory.CreateDirectory(maillages);
        foreach (var partie in parties)
        {
            var gonds = new Transform[2];
            for (int cote = 0; cote < 2; cote++)
            {
                float x = cote == 0 ? -0.635f : 0.635f;
                var gond = origine.Find("porte_balcon_etage_" + (cote == 0 ? "g" : "d"));
                if (gond == null)
                {
                    gond = new GameObject("porte_balcon_etage_" + (cote == 0 ? "g" : "d")).transform;
                    gond.SetParent(origine, false);
                    gond.localPosition = new Vector3(x, 0f, 0f);
                }
                gonds[cote] = gond;
            }

            Mesh source = partie.sharedMesh;
            Vector3[] sommets = source.vertices;
            var triangles = new List<int>[3];
            for (int i = 0; i < triangles.Length; i++) triangles[i] = new List<int>();
            int[] indices = source.triangles;
            for (int i = 0; i < indices.Length; i += 3)
            {
                Vector3 a = sommets[indices[i]], b = sommets[indices[i + 1]], c = sommets[indices[i + 2]];
                bool dansVantail = Mathf.Max(a.y, b.y, c.y) <= 2.64f
                    && Mathf.Max(Mathf.Abs(a.x), Mathf.Abs(b.x), Mathf.Abs(c.x)) <= 0.636f;
                int groupe = dansVantail ? ((a.x + b.x + c.x) < 0f ? 0 : 1) : 2;
                triangles[groupe].AddRange(new[] { indices[i], indices[i + 1], indices[i + 2] });
            }
            for (int groupe = 0; groupe < 3; groupe++)
            {
                Mesh copie = Object.Instantiate(source);
                copie.name = partie.name.Replace('/', '_') + "_" + groupe;
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
        }
        AssetDatabase.SaveAssets();
    }
}

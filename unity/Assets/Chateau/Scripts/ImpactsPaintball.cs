using System.Collections.Generic;
using UnityEngine;

public class ImpactsPaintball : MonoBehaviour
{
    public Texture2D texture;
    public Shader shader;
    public const int Maximum = 256;
    readonly Queue<GameObject> marques = new();
    readonly Dictionary<Color, Material> materiaux = new();
    public int Nombre => marques.Count;
    public void Nettoyer()
    {
        while (marques.Count > 0) Supprimer(marques.Dequeue());
    }
    void Supprimer(GameObject go)
    {
        if (go == null) return;
        Destroy(go.GetComponent<MeshFilter>().sharedMesh); Destroy(go);
    }
    // Matériau de tache partagé par couleur (décor et corps des joueurs).
    public Material Materiau(Color couleur)
    {
        if (!materiaux.TryGetValue(couleur, out var mat))
        {
            mat = new Material(shader); mat.SetTexture("_BaseMap", texture);
            mat.SetColor("_BaseColor", couleur); materiaux[couleur] = mat;
        }
        return mat;
    }
    public void Marquer(RaycastHit hit, Color couleur, float echelle = 1)
    {
        if (marques.Count >= Maximum) Supprimer(marques.Dequeue());
        var mat = Materiau(couleur);
        // Project a small grid onto the actual hit collider. Invalid cells are omitted,
        // preventing a decal from floating across a corner or an adjacent surface.
        Vector3 normal = hit.normal, tangent = Vector3.Cross(normal, Vector3.up);
        if (tangent.sqrMagnitude < .01f) tangent = Vector3.Cross(normal, Vector3.right);
        tangent.Normalize(); tangent = Quaternion.AngleAxis(Random.Range(0,360), normal) * tangent;
        Vector3 vertical = Vector3.Cross(normal, tangent);
        const int n=6; var vertices=new Vector3[(n+1)*(n+1)]; var uv=new Vector2[vertices.Length];
        var valides=new bool[vertices.Length]; var triangles=new List<int>();
        float taille=Random.Range(.25f,.4f)*echelle;
        var go=new GameObject("ImpactPeinture"); go.layer=2;
        go.transform.SetParent(hit.collider.transform,false);
        for(int y=0;y<=n;y++) for(int x=0;x<=n;x++)
        {
            int i=y*(n+1)+x; uv[i]=new Vector2(x/(float)n,y/(float)n);
            Vector3 p=hit.point+(tangent*(uv[i].x-.5f)+vertical*(uv[i].y-.5f))*taille;
            if(hit.collider.Raycast(new Ray(p+normal*.12f,-normal),out var h,.24f) && Vector3.Dot(h.normal,normal)>.5f)
            { vertices[i]=go.transform.InverseTransformPoint(h.point+h.normal*.0025f); valides[i]=true; }
        }
        for(int y=0;y<n;y++) for(int x=0;x<n;x++)
        {
            int a=y*(n+1)+x,b=a+1,c=a+n+1,d=c+1;
            if(valides[a]&&valides[b]&&valides[c]) { triangles.Add(a);triangles.Add(b);triangles.Add(c); }
            if(valides[b]&&valides[c]&&valides[d]) { triangles.Add(b);triangles.Add(d);triangles.Add(c); }
        }
        if(triangles.Count==0) { Destroy(go);return; }
        var mesh=new Mesh { name="ProjectionPeinture" };mesh.vertices=vertices;mesh.uv=uv;mesh.SetTriangles(triangles,0);mesh.RecalculateBounds();
        go.AddComponent<MeshFilter>().sharedMesh=mesh;
        var rendu=go.AddComponent<MeshRenderer>();rendu.sharedMaterial=mat;
        rendu.shadowCastingMode=UnityEngine.Rendering.ShadowCastingMode.Off;rendu.receiveShadows=false;
        marques.Enqueue(go);
        if(normal.y>.6f) Neige.Suivre(go.transform,hit.point);
    }
    void OnDestroy() { Nettoyer();foreach(var m in materiaux.Values) Destroy(m); }
}

using UnityEngine;

// Ondulation discrète par vent régulier, avec attache fixe au mât.
[RequireComponent(typeof(MeshFilter))]
public sealed class DrapeauAnime : MonoBehaviour
{
    [SerializeField] float amplitude = 0.24f;
    [SerializeField] float frequence = 1.15f;
    Mesh mesh;
    Vector3[] repos;
    Vector3[] sommets;
    float phase;

    void Awake()
    {
        var filtre = GetComponent<MeshFilter>();
        mesh = Instantiate(filtre.sharedMesh);
        mesh.name = filtre.sharedMesh.name + "_Vent";
        mesh.MarkDynamic();
        filtre.sharedMesh = mesh;
        repos = mesh.vertices;
        sommets = new Vector3[repos.Length];
        phase = Random.value * Mathf.PI * 2f;
    }

    void Update()
    {
        float t = Time.time * frequence + phase;
        for (int i = 0; i < repos.Length; i++)
        {
            Vector3 p = repos[i];
            float u = Mathf.Clamp01((p.x - 0.05f) / 1.5f);
            float v = Mathf.Clamp01(p.y - 6.85f);
            p.z += amplitude * u * u * (Mathf.Sin(t - u * 3.4f + v * 0.7f) + 0.24f * Mathf.Sin(t * 1.73f + u * 5f));
            p.y += 0.055f * u * Mathf.Sin(t * 0.72f + u * 2.2f);
            sommets[i] = p;
        }
        mesh.vertices = sommets;
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
    }
}

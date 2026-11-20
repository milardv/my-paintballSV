using UnityEngine;

// Respiration du jet d'eau : la base garde son ancrage au niveau du bassin.
public sealed class FontaineAnimee : MonoBehaviour
{
    [SerializeField] float amplitude = 0.10f;
    [SerializeField] float frequence = 1.8f;
    Mesh mesh;
    Vector3[] repos;
    Vector3[] sommets;
    float baseY;
    float phase;

    void Awake()
    {
        var filtre = GetComponent<MeshFilter>();
        if (filtre == null || filtre.sharedMesh == null) { enabled = false; return; }
        mesh = Instantiate(filtre.sharedMesh);
        mesh.name = filtre.sharedMesh.name + "_EauAnimee";
        mesh.MarkDynamic();
        filtre.sharedMesh = mesh;
        repos = mesh.vertices;
        sommets = new Vector3[repos.Length];
        baseY = mesh.bounds.min.y;
        phase = Random.value * Mathf.PI * 2f;
    }

    void Update()
    {
        float pulse = 1f + amplitude * Mathf.Sin(Time.time * frequence + phase);
        for (int i = 0; i < repos.Length; i++)
        {
            sommets[i] = repos[i];
            sommets[i].y = baseY + (repos[i].y - baseY) * pulse;
        }
        mesh.vertices = sommets;
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
    }
}

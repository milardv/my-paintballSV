using UnityEngine;

[RequireComponent(typeof(Rigidbody))]
public class ObjetMobilePaintball : MonoBehaviour
{
    [SerializeField] float seuilFixation;
    Rigidbody corps;
    Vector3 depart;
    Quaternion rotationDepart;
    float effort;
    public bool Fixe => corps.isKinematic;
    void Awake() { corps=GetComponent<Rigidbody>();depart=transform.position;rotationDepart=transform.rotation;if(!corps.isKinematic) corps.Sleep(); }
    public void Initialiser(float masse, float fixation = 0)
    {
        corps = GetComponent<Rigidbody>(); corps.mass = masse; seuilFixation = fixation;
        corps.linearDamping = .15f; corps.angularDamping = .5f;
        corps.interpolation = RigidbodyInterpolation.Interpolate;
        corps.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;
        corps.solverIterations = 8; corps.isKinematic = fixation > 0;
        depart = transform.position; rotationDepart = transform.rotation;
        if (!corps.isKinematic) corps.Sleep();
    }
    // Only finite impulses; mass controls acceleration. A loose fixing accumulates damage.
    public void Impulsion(Vector3 impulsion, Vector3 point)
    {
        if (corps == null) return;
        if (corps.isKinematic)
        {
            effort += impulsion.magnitude;
            if (effort < seuilFixation) return;
            corps.isKinematic = false;
        }
        corps.AddForceAtPosition(impulsion, point, ForceMode.Impulse);
    }
    public void Reinitialiser()
    {
        corps.isKinematic = true; corps.position = depart; corps.rotation = rotationDepart;
        effort = 0; corps.isKinematic = seuilFixation > 0;
        if (!corps.isKinematic) { corps.linearVelocity = Vector3.zero; corps.angularVelocity = Vector3.zero; corps.Sleep(); }
    }
}

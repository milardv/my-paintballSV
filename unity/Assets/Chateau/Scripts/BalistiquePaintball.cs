using UnityEngine;

// SI units. .68 inch sphere, 3.2 g, standard air; constant Cd is a documented approximation.
public static class BalistiquePaintball
{
    public const float Diametre = 0.017272f;
    public const float Masse = 0.0032f;
    public const float VitesseInitiale = 85.344f; // 280 ft/s
    public const float DensiteAir = 1.225f;
    public const float CoefficientTrainee = 0.47f;
    public static Vector3 Vent = Vector3.zero;
    public static Vector3 Acceleration(Vector3 vitesse)
    {
        Vector3 relative = vitesse - Vent;
        float k = .5f * DensiteAir * CoefficientTrainee * Mathf.PI * Diametre * Diametre / (4f * Masse);
        return Vector3.down * 9.81f - k * relative.magnitude * relative;
    }
    // Midpoint integration at 240 Hz, independent of rendering and Unity's rigidbody tick.
    public static void Avancer(ref Vector3 position, ref Vector3 vitesse, float dt)
    {
        Vector3 milieu = vitesse + Acceleration(vitesse) * (dt * .5f);
        position += milieu * dt;
        vitesse += Acceleration(milieu) * dt;
    }
}

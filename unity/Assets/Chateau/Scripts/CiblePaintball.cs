using UnityEngine;

public class CiblePaintball : MonoBehaviour
{
    public PaintballSolo partie;
    public int numero;
    public float disponible;
    Vector3 taille;
    void Start() => taille = transform.localScale;
    public void Toucher(Vector3 point, Color couleur)
    {
        if (Time.time < disponible) return;
        disponible = Time.time + 1.2f;
        partie.CibleTouchee(numero);
        transform.localScale = taille * .88f;
    }
    void Update()
    {
        if (partie != null && !partie.EnPause)
            transform.localScale = Vector3.Lerp(transform.localScale, taille, 1-Mathf.Exp(-10*Time.deltaTime));
    }
}

using UnityEngine;
using UnityEngine.UI;

// Réticule vectoriel : quatre branches à écart dynamique, point central, marqueur de touche
// et anneau de rechargement. Chaque trait a un lisere sombre pour rester lisible sur tout fond.
public class ReticulePaintball : MaskableGraphic
{
    public Color teinte = Color.white;
    float ecart = 9, touche, recharge = -1, opacite = 1;
    bool vide;

    public void Definir(float nouvelEcart, float nouvelleTouche, float nouvelleRecharge, bool chargeurVide, float nouvelleOpacite)
    {
        if (Mathf.Abs(nouvelEcart - ecart) < .05f && Mathf.Abs(nouvelleTouche - touche) < .01f &&
            Mathf.Abs(nouvelleRecharge - recharge) < .004f && chargeurVide == vide && Mathf.Abs(nouvelleOpacite - opacite) < .01f) return;
        ecart = nouvelEcart; touche = nouvelleTouche; recharge = nouvelleRecharge; vide = chargeurVide; opacite = nouvelleOpacite;
        SetVerticesDirty();
    }

    protected override void OnPopulateMesh(VertexHelper vh)
    {
        vh.Clear();
        Color ombre = new(0, 0, 0, .55f * opacite);
        Color clair = teinte; clair.a *= opacite;
        if (vide) clair = new Color(1f, .35f, .3f, .9f * opacite);
        const float longueur = 11f, epaisseur = 2.4f, lisere = 1.4f;
        for (int i = 0; i < 4; i++)
        {
            Vector2 d = i switch { 0 => Vector2.up, 1 => Vector2.right, 2 => Vector2.down, _ => Vector2.left };
            Vector2 a = d * ecart, b = d * (ecart + longueur);
            Trait(vh, a - d * lisere, b + d * lisere, epaisseur + lisere * 2, ombre);
            Trait(vh, a, b, epaisseur, clair);
        }
        Disque(vh, Vector2.zero, 2.9f, ombre, 12);
        Disque(vh, Vector2.zero, 1.7f, clair, 12);
        if (touche > 0)
        {
            Color blanc = new(1, 1, 1, Mathf.Clamp01(touche * 1.4f) * opacite);
            float r0 = 7 + (1 - touche) * 6, r1 = r0 + 9;
            for (int i = 0; i < 4; i++)
            {
                Vector2 d = Quaternion.Euler(0, 0, 45 + 90 * i) * Vector2.up;
                Trait(vh, d * r0, d * r1, 4.2f, new Color(0, 0, 0, blanc.a * .5f));
                Trait(vh, d * r0, d * r1, 2.4f, blanc);
            }
        }
        if (recharge >= 0)
        {
            Anneau(vh, 26, 3.6f, 1, new Color(0, 0, 0, .45f * opacite));
            Anneau(vh, 26, 2.4f, recharge, clair);
        }
    }

    static void Trait(VertexHelper vh, Vector2 a, Vector2 b, float largeur, Color c)
    {
        Vector2 n = Vector2.Perpendicular((b - a).normalized) * largeur * .5f;
        Quad(vh, a - n, a + n, b + n, b - n, c);
    }
    static void Quad(VertexHelper vh, Vector2 p0, Vector2 p1, Vector2 p2, Vector2 p3, Color c)
    {
        int i = vh.currentVertCount;
        vh.AddVert(p0, c, Vector2.zero); vh.AddVert(p1, c, Vector2.zero); vh.AddVert(p2, c, Vector2.zero); vh.AddVert(p3, c, Vector2.zero);
        vh.AddTriangle(i, i + 1, i + 2); vh.AddTriangle(i, i + 2, i + 3);
    }
    static void Disque(VertexHelper vh, Vector2 centre, float rayon, Color c, int segments)
    {
        int i0 = vh.currentVertCount; vh.AddVert(centre, c, Vector2.zero);
        for (int s = 0; s <= segments; s++)
        {
            float a = s * Mathf.PI * 2 / segments;
            vh.AddVert(centre + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * rayon, c, Vector2.zero);
            if (s > 0) vh.AddTriangle(i0, i0 + s, i0 + s + 1);
        }
    }
    static void Anneau(VertexHelper vh, float rayon, float largeur, float part, Color c)
    {
        int segments = Mathf.Max(2, Mathf.CeilToInt(48 * part));
        for (int s = 0; s < segments; s++)
        {
            float a0 = Mathf.PI * .5f - s * Mathf.PI * 2 * part / segments, a1 = Mathf.PI * .5f - (s + 1) * Mathf.PI * 2 * part / segments;
            Vector2 d0 = new(Mathf.Cos(a0), Mathf.Sin(a0)), d1 = new(Mathf.Cos(a1), Mathf.Sin(a1));
            Quad(vh, d0 * (rayon - largeur * .5f), d0 * (rayon + largeur * .5f), d1 * (rayon + largeur * .5f), d1 * (rayon - largeur * .5f), c);
        }
    }
}

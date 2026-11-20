using UnityEngine;
using UnityEngine.UI;

// Rectangle aux coins arrondis (pilule si rayon >= demi-hauteur), plein ou en contour.
// Bords lissés : un liseré d'un pixel écran passe de l'opaque au transparent (l'interface est rendue
// sans anticrénelage) ; nombre de segments des coins proportionnel à leur taille.
public class FormeInterface : MaskableGraphic, ICanvasRaycastFilter
{
    public float rayon = 999;
    public float contour; // 0 = plein, sinon épaisseur du trait en pixels de référence
    public float remplissage = 1; // fraction horizontale remplie (barres de progression)

    public void Remplir(float valeur)
    {
        valeur = Mathf.Clamp01(valeur);
        if (Mathf.Abs(valeur - remplissage) < .001f) return;
        remplissage = valeur; SetVerticesDirty();
    }

    // Un pixel écran en unités de l'interface.
    float Pixel => canvas != null && canvas.scaleFactor > 0 ? 1f / canvas.scaleFactor : 1;

    protected override void OnPopulateMesh(VertexHelper vh)
    {
        vh.Clear();
        Rect r = rectTransform.rect;
        if (remplissage < 1) r.width *= remplissage;
        if (r.width <= 0 || r.height <= 0) return;
        float rr = Mathf.Min(rayon, r.width * .5f, r.height * .5f);
        float f = Pixel * .5f;
        int pas = Mathf.Clamp(Mathf.CeilToInt(rr / Pixel * .6f), 6, 48);
        Color transparent = new(color.r, color.g, color.b, 0);
        if (contour <= 0)
        {
            var dedans = Contour(Agrandir(r, -f), Mathf.Max(0, rr - f), pas);
            var dehors = Contour(Agrandir(r, f), rr + f, pas);
            int c = vh.currentVertCount; vh.AddVert(r.center, color, Vector2.zero);
            for (int i = 0; i < dedans.Length; i++) vh.AddVert(dedans[i], color, Vector2.zero);
            for (int i = 0; i < dedans.Length; i++) vh.AddTriangle(c, c + 1 + i, c + 1 + (i + 1) % dedans.Length);
            Anneau(vh, dedans, color, dehors, transparent);
            return;
        }
        float e = Mathf.Max(contour, Pixel);
        Rect ri = Agrandir(r, -e);
        float ri_r = Mathf.Max(0, rr - e);
        var exterieurFlou = Contour(Agrandir(r, f), rr + f, pas);
        var exterieur = Contour(Agrandir(r, -f), Mathf.Max(0, rr - f), pas);
        var interieur = Contour(Agrandir(ri, f), ri_r + f, pas);
        var interieurFlou = Contour(Agrandir(ri, -f), Mathf.Max(0, ri_r - f), pas);
        Anneau(vh, exterieur, color, exterieurFlou, transparent);
        Anneau(vh, interieur, color, exterieur, color);
        Anneau(vh, interieurFlou, transparent, interieur, color);
    }

    static Rect Agrandir(Rect r, float d) => new(r.x - d, r.y - d, r.width + 2 * d, r.height + 2 * d);

    // Bande entre deux contours de même nombre de points.
    static void Anneau(VertexHelper vh, Vector2[] a, Color ca, Vector2[] b, Color cb)
    {
        int s = vh.currentVertCount;
        for (int i = 0; i < a.Length; i++) { vh.AddVert(a[i], ca, Vector2.zero); vh.AddVert(b[i], cb, Vector2.zero); }
        for (int i = 0; i < a.Length; i++)
        {
            int j = (i + 1) % a.Length;
            vh.AddTriangle(s + i * 2, s + j * 2, s + i * 2 + 1); vh.AddTriangle(s + j * 2, s + j * 2 + 1, s + i * 2 + 1);
        }
    }

    static Vector2[] Contour(Rect r, float rr, int pas)
    {
        var points = new Vector2[pas * 4 + 4];
        Vector2[] centres = { new(r.xMax - rr, r.yMax - rr), new(r.xMin + rr, r.yMax - rr), new(r.xMin + rr, r.yMin + rr), new(r.xMax - rr, r.yMin + rr) };
        int n = 0;
        for (int coin = 0; coin < 4; coin++)
            for (int i = 0; i <= pas; i++)
            {
                float a = (coin * 90 + i * 90f / pas) * Mathf.Deg2Rad;
                points[n++] = centres[coin] + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * rr;
            }
        return points;
    }

    public bool IsRaycastLocationValid(Vector2 point, Camera cam) => true;
}

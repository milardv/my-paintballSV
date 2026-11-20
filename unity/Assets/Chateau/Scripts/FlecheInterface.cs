using UnityEngine;
using UnityEngine.UI;

// Chevron plein pointant vers le haut du rectangle, bords lissés (indicateur de direction d'une touche).
public class FlecheInterface : MaskableGraphic
{
    protected override void OnPopulateMesh(VertexHelper vh)
    {
        vh.Clear(); Rect r = rectTransform.rect;
        float f = canvas != null && canvas.scaleFactor > 0 ? .5f / canvas.scaleFactor : .5f;
        Vector2 haut = new(r.center.x, r.yMax), gauche = new(r.xMin, r.yMin), creux = new(r.center.x, r.yMin + r.height * .32f), droite = new(r.xMax, r.yMin);
        Vector2[] contour = { haut, droite, creux, gauche };
        Vector2 centre = (haut + creux) * .5f;
        Color transparent = new(color.r, color.g, color.b, 0);
        vh.AddVert(centre, color, Vector2.zero);
        foreach (var p in contour) vh.AddVert(p + (centre - p).normalized * f, color, Vector2.zero);
        foreach (var p in contour) vh.AddVert(p - (centre - p).normalized * f, transparent, Vector2.zero);
        for (int i = 0; i < 4; i++)
        {
            int a = 1 + i, b = 1 + (i + 1) % 4;
            vh.AddTriangle(0, a, b);
            vh.AddTriangle(a, b, a + 4); vh.AddTriangle(b, b + 4, a + 4);
        }
    }
}

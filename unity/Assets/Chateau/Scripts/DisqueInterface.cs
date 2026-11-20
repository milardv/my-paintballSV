using UnityEngine;

// Disque (ou ellipse) plein, bord lissé par un liseré d'un pixel écran passant au transparent.
public class DisqueInterface : UnityEngine.UI.MaskableGraphic, ICanvasRaycastFilter
{
    protected override void OnPopulateMesh(UnityEngine.UI.VertexHelper vh)
    {
        vh.Clear(); Rect r = rectTransform.rect; Vector2 centre = r.center;
        if (r.width <= 0 || r.height <= 0) return;
        float pixel = canvas != null && canvas.scaleFactor > 0 ? 1f / canvas.scaleFactor : 1, f = pixel * .5f;
        float rx = r.width * .5f, ry = r.height * .5f;
        int n = Mathf.Clamp(Mathf.CeilToInt(Mathf.Max(rx, ry) / pixel * 1.2f), 32, 160);
        Color transparent = new(color.r, color.g, color.b, 0);
        vh.AddVert(centre, color, new Vector2(.5f, .5f));
        for (int i = 0; i < n; i++)
        {
            float a = i * Mathf.PI * 2 / n; Vector2 d = new(Mathf.Cos(a), Mathf.Sin(a));
            vh.AddVert(centre + new Vector2(d.x * (rx - f), d.y * (ry - f)), color, Vector2.zero);
            vh.AddVert(centre + new Vector2(d.x * (rx + f), d.y * (ry + f)), transparent, Vector2.zero);
        }
        for (int i = 0; i < n; i++)
        {
            int a = 1 + i * 2, b = 1 + (i + 1) % n * 2;
            vh.AddTriangle(0, a, b);
            vh.AddTriangle(a, b, a + 1); vh.AddTriangle(b, b + 1, a + 1);
        }
    }
    public bool IsRaycastLocationValid(Vector2 point, Camera camera)
    {
        RectTransformUtility.ScreenPointToLocalPointInRectangle(rectTransform, point, camera, out var local);
        Rect r = rectTransform.rect; Vector2 d = local - r.center;
        return Mathf.Pow(d.x / (r.width * .5f), 2) + Mathf.Pow(d.y / (r.height * .5f), 2) <= 1;
    }
}

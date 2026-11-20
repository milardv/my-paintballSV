using UnityEngine;

public class VoileInterface : UnityEngine.UI.MaskableGraphic
{
    public Color debut,fin;
    public bool horizontal;
    protected override void OnPopulateMesh(UnityEngine.UI.VertexHelper vh)
    {
        vh.Clear(); Rect r=rectTransform.rect;
        const int bandes=32;
        for(int i=0;i<=bandes;i++)
        {
            float t=(float)i/bandes;
            Color c=Color.Lerp(debut,fin,1-Mathf.Pow(1-t,.35f));
            if(horizontal)
            {
                float x=Mathf.Lerp(r.xMin,r.xMax,t);
                vh.AddVert(new Vector3(x,r.yMin,0),c,Vector2.zero);
                vh.AddVert(new Vector3(x,r.yMax,0),c,Vector2.up);
            }
            else
            {
                float y=Mathf.Lerp(r.yMin,r.yMax,t);
                vh.AddVert(new Vector3(r.xMin,y,0),c,Vector2.zero);
                vh.AddVert(new Vector3(r.xMax,y,0),c,Vector2.right);
            }
            if(i>0)
            {
                int b=(i-1)*2;
                vh.AddTriangle(b,b+1,b+2); vh.AddTriangle(b+2,b+1,b+3);
            }
        }
    }
}

using UnityEngine;

[RequireComponent(typeof(RectTransform))]
public class ZoneSureInterface : MonoBehaviour
{
    Rect precedente;
    Vector2 taille;
    void OnEnable() => Appliquer();
    void OnRectTransformDimensionsChange() => Appliquer();
    void Appliquer()
    {
        if(Screen.width==0 || Screen.height==0) return;
        Rect zone=Screen.safeArea;
        Vector2 dimensions=new(Screen.width,Screen.height);
        if(zone==precedente && dimensions==taille) return;
        precedente=zone; taille=dimensions;
        var rt=(RectTransform)transform;
        rt.anchorMin=zone.position/dimensions;
        rt.anchorMax=(zone.position+zone.size)/dimensions;
        rt.offsetMin=rt.offsetMax=Vector2.zero;
    }
}

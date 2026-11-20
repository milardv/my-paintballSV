using System.Collections;
using UnityEngine;
using UnityEngine.EventSystems;

[RequireComponent(typeof(UnityEngine.UI.Button))]
public class FocusInterface : MonoBehaviour,ISelectHandler,IDeselectHandler,IPointerDownHandler,IPointerUpHandler
{
    UnityEngine.UI.Outline contour;
    GameObject anneau;
    Coroutine mouvement;
    static readonly Color Laiton=new(.74f,.65f,.44f,1f);
    void Awake()
    {
        var cible=GetComponent<UnityEngine.UI.Button>().targetGraphic;
        // Formes arrondies (pilules, disques) : anneau lissé tracé autour de la forme ; l'effet Outline
        // de Unity, qui recopie la forme décalée, en crénelait le bord.
        if(cible is FormeInterface || cible is DisqueInterface)
        {
            var rt=new GameObject("Focus",typeof(RectTransform)).GetComponent<RectTransform>();
            rt.SetParent(cible.transform,false);rt.anchorMin=Vector2.zero;rt.anchorMax=Vector2.one;
            rt.offsetMin=new Vector2(-4,-4);rt.offsetMax=new Vector2(4,4);
            var forme=rt.gameObject.AddComponent<FormeInterface>();forme.contour=2;forme.color=Laiton;forme.raycastTarget=false;
            if(cible is FormeInterface f) forme.rayon=f.rayon>=999?999:f.rayon+4;
            anneau=rt.gameObject;anneau.SetActive(false);
        }
        else
        {
            contour=cible.gameObject.AddComponent<UnityEngine.UI.Outline>();
            contour.effectColor=Laiton;
            contour.effectDistance=new Vector2(1.5f,-1.5f);
            contour.useGraphicAlpha=false; contour.enabled=false;
        }
    }
    void Montrer(bool oui) { if(anneau!=null) anneau.SetActive(oui); if(contour!=null) contour.enabled=oui; }
    public void OnSelect(BaseEventData e)
    {
        Montrer(true);
        bool souris=UnityEngine.InputSystem.Mouse.current!=null && UnityEngine.InputSystem.Mouse.current.leftButton.wasPressedThisFrame;
        if(!souris)
        {
            var bouton=GetComponent<UnityEngine.UI.Button>();
            bouton.targetGraphic.CrossFadeColor(bouton.colors.selectedColor*bouton.colors.colorMultiplier,0f,true,true);
        }
    }
    public void OnDeselect(BaseEventData e) => Montrer(false);
    public void OnPointerDown(PointerEventData e)
    {
        if(!InterfaceVisite.MouvementActif) return;
        if(mouvement!=null) StopCoroutine(mouvement);
        transform.localScale=Vector3.one*.97f;
    }
    public void OnPointerUp(PointerEventData e)
    {
        if(mouvement!=null) StopCoroutine(mouvement);
        mouvement=StartCoroutine(Retablir());
    }
    IEnumerator Retablir()
    {
        Vector3 debut=transform.localScale; float t=0;
        while(t<1)
        {
            t+=Time.unscaledDeltaTime/.14f;
            float progress=1-Mathf.Pow(1-Mathf.Clamp01(t),3);
            transform.localScale=Vector3.LerpUnclamped(debut,Vector3.one,progress);
            yield return null;
        }
        transform.localScale=Vector3.one;
    }
    void OnDisable() { transform.localScale=Vector3.one; mouvement=null; }
}

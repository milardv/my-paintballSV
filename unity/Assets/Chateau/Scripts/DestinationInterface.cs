using UnityEngine;
using UnityEngine.EventSystems;

public class DestinationInterface : MonoBehaviour,IPointerEnterHandler,ISelectHandler
{
    public InterfaceVisite interfaceVisite;
    public int index;
    public void OnPointerEnter(PointerEventData e) => EventSystem.current.SetSelectedGameObject(gameObject);
    public void OnSelect(BaseEventData e) => interfaceVisite.Presenter(index);
}

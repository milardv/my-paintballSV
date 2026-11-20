using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

// Commandes tactiles (navigateur mobile) au schéma courant des tireurs sur téléphone :
// joystick flottant à gauche (bord poussé vers l'avant : course), glisser à droite pour regarder,
// boutons tir (à droite et à gauche), visée, saut, recharge, vue et porte. Le bouton de tir laisse
// aussi orienter le regard en glissant. Explorateur et PaintballSolo lisent cet état.
public static class Tactile
{
    // Téléphone ou tablette, ou ?tactile=1 pour essayer au bureau.
    public static readonly bool Actif = Application.isMobilePlatform || Application.absoluteURL.Contains("tactile=1");
    public static Vector2 Deplacement;
    public static bool Tir, Visee, Course;
    static Vector2 regard;
    static bool saut, recharge, vue, porte, accroupir;

    public static void Regarder(Vector2 pixels) => regard += pixels;
    // Degrés de lacet et de tangage depuis la dernière lecture (0,16 °/px pour 1080 px de haut).
    public static Vector2 LireRegard() { var r = regard * (.16f * 1080f / Mathf.Max(1, Screen.height)); regard = Vector2.zero; return r; }
    public static void Demander(string action) { if (action == "saut") saut = true; else if (action == "recharge") recharge = true; else if (action == "vue") vue = true; else if (action == "porte") porte = true; else if (action == "accroupir") accroupir = true; }
    public static bool Saut() => Lire(ref saut);
    public static bool Recharge() => Lire(ref recharge);
    public static bool Vue() => Lire(ref vue);
    public static bool Porte() => Lire(ref porte);
    public static bool Accroupir() => Lire(ref accroupir);
    static bool Lire(ref bool b) { bool v = b; b = false; return v; }
    public static void Relacher() { Deplacement = Vector2.zero; Tir = Visee = Course = false; regard = Vector2.zero; saut = recharge = vue = porte = accroupir = false; }
}

// Zone du joystick : apparaît sous le doigt, suit le glissé dans un rayon de 110 px de référence.
public class JoystickTactile : Graphic, IPointerDownHandler, IDragHandler, IPointerUpHandler
{
    public RectTransform socle, bouton;
    int doigt = int.MinValue;
    Vector2 centre;
    const float Rayon = 110;

    protected override void OnPopulateMesh(VertexHelper vh) => vh.Clear();

    public void OnPointerDown(PointerEventData e)
    {
        if (doigt != int.MinValue) return;
        doigt = e.pointerId;
        RectTransformUtility.ScreenPointToLocalPointInRectangle(rectTransform, e.position, e.pressEventCamera, out centre);
        socle.anchoredPosition = centre; bouton.anchoredPosition = centre; socle.gameObject.SetActive(true); bouton.gameObject.SetActive(true);
    }

    public void OnDrag(PointerEventData e)
    {
        if (e.pointerId != doigt) return;
        RectTransformUtility.ScreenPointToLocalPointInRectangle(rectTransform, e.position, e.pressEventCamera, out var p);
        Vector2 d = Vector2.ClampMagnitude(p - centre, Rayon);
        bouton.anchoredPosition = centre + d;
        Tactile.Deplacement = d / Rayon;
        Tactile.Course = Tactile.Deplacement.y > .92f;
    }

    public void OnPointerUp(PointerEventData e)
    {
        if (e.pointerId != doigt) return;
        doigt = int.MinValue; Tactile.Deplacement = Vector2.zero; Tactile.Course = false;
        socle.gameObject.SetActive(false); bouton.gameObject.SetActive(false);
    }

    protected override void OnDisable() { base.OnDisable(); doigt = int.MinValue; Tactile.Deplacement = Vector2.zero; Tactile.Course = false; }
}

// Zone de regard : chaque glissé tourne la caméra.
public class RegardTactile : Graphic, IPointerDownHandler, IDragHandler
{
    protected override void OnPopulateMesh(VertexHelper vh) => vh.Clear();
    public void OnPointerDown(PointerEventData e) { }
    public void OnDrag(PointerEventData e) => Tactile.Regarder(e.delta);
}

// Bouton tenu (tir, visée) ou bref (saut, recharge, vue, porte). Un bouton « regard » tourne aussi la caméra au glissé.
public class BoutonTactile : MonoBehaviour, IPointerDownHandler, IDragHandler, IPointerUpHandler
{
    public string action;
    public bool regard;
    Graphic fond;
    Color couleur;
    int appuis;

    void Awake() { fond = GetComponent<Graphic>(); couleur = fond.color; }

    public void OnPointerDown(PointerEventData e)
    {
        appuis++;
        if (action == "tir") Tactile.Tir = true;
        else if (action == "visee") Tactile.Visee = !Tactile.Visee;
        else Tactile.Demander(action);
        fond.color = Color.Lerp(couleur, Color.white, .35f);
    }

    public void OnDrag(PointerEventData e) { if (regard) Tactile.Regarder(e.delta); }

    public void OnPointerUp(PointerEventData e)
    {
        appuis = Mathf.Max(0, appuis - 1);
        if (action == "tir" && appuis == 0 && !AutreTir()) Tactile.Tir = false;
        fond.color = action == "visee" && Tactile.Visee ? Color.Lerp(couleur, Color.white, .25f) : couleur;
    }

    // Les deux boutons de tir peuvent être tenus ensemble.
    bool AutreTir()
    {
        foreach (var b in FindObjectsByType<BoutonTactile>(FindObjectsSortMode.None)) if (b != this && b.action == "tir" && b.appuis > 0) return true;
        return false;
    }

    void OnDisable() { appuis = 0; if (action == "tir") Tactile.Tir = false; }
}

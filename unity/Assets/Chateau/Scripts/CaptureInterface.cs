using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;

// Contrôle dans le player : -capture-interface <dossier>. Actions des véritables boutons uGUI.
public class CaptureInterface : MonoBehaviour
{
    [Serializable] class Resultat { public bool reussi; public List<string> controles = new(); public List<string> erreurs = new(); }
    readonly Resultat resultat=new();
    string dossier;
    InterfaceVisite ui;
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Demarrer()
    {
        Application.runInBackground=true;
        var args=Environment.GetCommandLineArgs(); int i=Array.IndexOf(args,"-capture-interface");
        if(i>=0 && i+1<args.Length) new GameObject("CaptureInterface").AddComponent<CaptureInterface>().dossier=Path.GetFullPath(args[i+1]);
    }
    IEnumerator Photo(string nom)
    {
        yield return new WaitForSeconds(.6f); yield return new WaitForEndOfFrame();
        var image=ScreenCapture.CaptureScreenshotAsTexture();
        File.WriteAllBytes(Path.Combine(dossier,nom+".png"),image.EncodeToPNG()); Destroy(image);
        var problemes=FindObjectsByType<TextMeshProUGUI>().Where(t=>t.isActiveAndEnabled && t.isTextOverflowing).Select(t=>t.name).ToArray();
        if(problemes.Length>0) resultat.erreurs.Add(nom+" : textes débordants "+string.Join(",",problemes));
        if(ui.EcranActuel!=InterfaceVisite.Ecran.Visite && EventSystem.current.currentSelectedGameObject==null)
            resultat.erreurs.Add(nom+" : aucun contrôle focalisé");
        if(FindObjectsByType<UnityEngine.UI.RawImage>().Length>0)
            resultat.erreurs.Add(nom+" : image photographique présente");
        Debug.Log("INTERFACE capture "+nom);
    }
    void Cliquer(string nom)
    {
        Canvas.ForceUpdateCanvases();
        var bouton=FindObjectsByType<UnityEngine.UI.Button>().FirstOrDefault(b=>b.name==nom && b.isActiveAndEnabled);
        if(bouton==null) { resultat.erreurs.Add("Bouton absent : "+nom); return; }
        var position=RectTransformUtility.WorldToScreenPoint(null,bouton.transform.TransformPoint(((RectTransform)bouton.transform).rect.center));
        var evt=new PointerEventData(EventSystem.current) { position=position };
        var impacts=new List<RaycastResult>(); EventSystem.current.RaycastAll(evt,impacts);
        if(impacts.Count==0 || impacts[0].gameObject.GetComponentInParent<UnityEngine.UI.Button>()!=bouton)
            resultat.erreurs.Add("Bouton masqué : "+nom+" ; cible "+(impacts.Count>0?impacts[0].gameObject.name:"aucune"));
        EventSystem.current.SetSelectedGameObject(bouton.gameObject);
        ExecuteEvents.Execute(bouton.gameObject,evt,ExecuteEvents.pointerDownHandler);
        ExecuteEvents.Execute(bouton.gameObject,evt,ExecuteEvents.pointerUpHandler);
        ExecuteEvents.Execute(bouton.gameObject,evt,ExecuteEvents.pointerClickHandler);
        resultat.controles.Add(nom);
    }
    IEnumerator Start()
    {
        Directory.CreateDirectory(dossier); yield return new WaitForSeconds(3f);
        ui=FindAnyObjectByType<InterfaceVisite>();
        yield return Photo("accueil");
        Cliquer("ChoisirEspaces"); yield return Photo("espaces");
        var destination=GameObject.Find("Espace7");
        ExecuteEvents.Execute(destination,new PointerEventData(EventSystem.current),ExecuteEvents.pointerEnterHandler);
        if(ui.EspaceActuel!=7) resultat.erreurs.Add("Survol sans aperçu de destination");
        else resultat.controles.Add("Aperçu au survol et au focus");
        yield return Photo("bassin_apercu");
        Cliquer("EntrerEspace"); yield return Photo("bassin_visite");
        if(ui.EcranActuel!=InterfaceVisite.Ecran.Visite) resultat.erreurs.Add("Entrée en visite impossible");
        ui.AfficherEspaces(7); yield return Photo("menu_reprise");
        Cliquer("ReprendreDepuisEspaces");
        if(Cursor.lockState!=CursorLockMode.Locked) resultat.erreurs.Add("Souris non capturée en visite");
        ui.AfficherAccueil(); yield return new WaitForEndOfFrame();
        Cliquer("OuvrirCommandes"); yield return Photo("commandes");
        Cliquer("RetourCommandes");
        if(EventSystem.current.currentSelectedGameObject?.name!="OuvrirCommandes")
            resultat.erreurs.Add("Focus non restauré au retour du menu");
        yield return new WaitForEndOfFrame();
        Cliquer("CommencerVisite"); yield return Photo("vestibule_visite");
        if(Camera.main.rect!=new Rect(0,0,1,1)) resultat.erreurs.Add("Vue de visite partielle");
        ui.AfficherAccueil();
        yield return new WaitForEndOfFrame();
        EventSystem.current.SetSelectedGameObject(GameObject.Find("CommencerVisite"));
        var mouvement=new AxisEventData(EventSystem.current) { moveDir=MoveDirection.Down, moveVector=Vector2.down };
        ExecuteEvents.Execute(EventSystem.current.currentSelectedGameObject,mouvement,ExecuteEvents.moveHandler);
        if(EventSystem.current.currentSelectedGameObject?.name!="ChoisirEspaces")
            resultat.erreurs.Add("Navigation verticale inattendue");
        else ExecuteEvents.Execute(EventSystem.current.currentSelectedGameObject,new BaseEventData(EventSystem.current),ExecuteEvents.submitHandler);
        if(ui.EcranActuel!=InterfaceVisite.Ecran.Espaces) resultat.erreurs.Add("Validation au clavier impossible");
        else resultat.controles.Add("Navigation directionnelle et validation uGUI");
        yield return new WaitForEndOfFrame();
        Cliquer("Espace3");
        if(ui.EcranActuel!=InterfaceVisite.Ecran.Visite || ui.EspaceActuel!=3)
            resultat.erreurs.Add("Entrée directe dans une destination impossible");
        else resultat.controles.Add("Entrée dans une destination en un clic");
        resultat.reussi=resultat.erreurs.Count==0;
        File.WriteAllText(Path.Combine(dossier,"verification-interface.json"),JsonUtility.ToJson(resultat,true));
        Application.Quit(resultat.reussi?0:1);
    }
}

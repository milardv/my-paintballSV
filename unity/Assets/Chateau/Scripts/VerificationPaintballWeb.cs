using System;
using System.Linq;
using System.Collections;
using UnityEngine;

// Opt-in browser verification. Exercises actual projectiles, colliders and rigidbodies.
public class VerificationPaintballWeb : MonoBehaviour
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Installer()
    {
        if(Application.absoluteURL.Contains("validation=1")) new GameObject("VerificationPaintballWeb").AddComponent<VerificationPaintballWeb>();
    }
    [Serializable] class Rapport
    {
        public bool fini,ok,balles,peinture,couleurs,animation,pause,recharge,masse,fixation,chute,collisionJoueur;
        public int mobilier,cibles,clips,impacts; public float legerDistance,lourdDistance,animationAvant,animationApres; public string erreur;
    }
    readonly Rapport rapport=new();
    IEnumerator Start()
    {
        yield return null;yield return null;
        var ui=FindAnyObjectByType<InterfaceVisite>();var p=FindAnyObjectByType<PaintballSolo>();
        while(!p.Active) yield return null;
        yield return new WaitForSeconds(.5f);
        rapport.mobilier=FindObjectsByType<ObjetMobilePaintball>().Length;
        var cibles=p.terrainEntrainement.GetComponentsInChildren<CiblePaintball>();rapport.cibles=cibles.Length;
        rapport.clips=p.animateur.runtimeAnimatorController.animationClips.Length;
        p.BasculerVue();
        for(int i=0;i<8;i++) yield return null;
        rapport.animationAvant=p.animateur.GetCurrentAnimatorStateInfo(0).normalizedTime;
        for(int i=0;i<8;i++) yield return null;
        rapport.animationApres=p.animateur.GetCurrentAnimatorStateInfo(0).normalizedTime;
        rapport.animation=rapport.clips>=4 && p.personnage.activeInHierarchy && Mathf.Abs(rapport.animationApres-rapport.animationAvant)>.001f;
        var cible=cibles[0];var centre=cible.transform.position;
        // Shoot the real board from a known nearby point, including flight time and sweep.
        p.AjouterBille(centre-Vector3.forward*3,Vector3.forward*BalistiquePaintball.VitesseInitiale,PaintballSolo.Couleurs[1],17);
        for(int i=0;i<18;i++) yield return new WaitForFixedUpdate();
        rapport.balles=p.Touches>0 && p.ImpactsTotal>0;
        rapport.peinture=p.impacts.Nombre>0;
        rapport.couleurs=p.DernierProprietaire==17 && p.DerniereCouleur==PaintballSolo.Couleurs[1];
        // Second owner, another board: existing marks must remain alongside the second colour.
        centre=cibles[2].transform.position;
        p.AjouterBille(centre-Vector3.forward*3,Vector3.forward*BalistiquePaintball.VitesseInitiale,PaintballSolo.Couleurs[2],23);
        for(int i=0;i<18;i++) yield return new WaitForFixedUpdate();
        rapport.couleurs &= p.DernierProprietaire==23 && p.DerniereCouleur==PaintballSolo.Couleurs[2] && p.impacts.Nombre>=2;
        rapport.impacts=p.ImpactsTotal;
        p.Tirer();p.LancerRecharge();
        yield return new WaitForSeconds(1.7f);
        rapport.recharge=p.Chargeur==50 && !p.Recharge;
        float restant=p.TempsRestant;long ticks=p.EtapesPhysiques;ui.AfficherPausePaintball();
        yield return new WaitForSecondsRealtime(.4f);
        rapport.pause=Mathf.Abs(restant-p.TempsRestant)<.001f && ticks==p.EtapesPhysiques;
        ui.Reprendre();
        var obstacle=p.terrainEntrainement.GetComponentsInChildren<ObjetMobilePaintball>().First(o=>o.name=="ObstacleMobile1");
        var cc=p.GetComponent<CharacterController>();var departJoueur=p.transform.position;var departObjet=obstacle.transform.position;
        cc.enabled=false;p.transform.position=departObjet+new Vector3(0,-.3f,-1.4f);cc.enabled=true;Physics.SyncTransforms();
        for(int i=0;i<30;i++) {cc.Move(Vector3.forward*.07f);yield return new WaitForFixedUpdate();}
        rapport.collisionJoueur=Vector3.Distance(obstacle.transform.position,departObjet)>.08f;
        cc.enabled=false;p.transform.position=departJoueur;cc.enabled=true;Physics.SyncTransforms();
        var a=Corps("TestLeger",new Vector3(1000,1000,1000),3,0);
        var b=Corps("TestLourd",new Vector3(1010,1000,1000),30,0);
        var f=Corps("TestFixe",new Vector3(1020,1000,1000),5,10);
        a.Impulsion(Vector3.right*6,a.transform.position);b.Impulsion(Vector3.right*6,b.transform.position);
        f.Impulsion(Vector3.right*4,f.transform.position);bool tient=f.Fixe;
        f.Impulsion(Vector3.right*7,f.transform.position);rapport.fixation=tient&&!f.Fixe;
        for(int i=0;i<30;i++) yield return new WaitForFixedUpdate();
        rapport.legerDistance=a.transform.position.x-1000;rapport.lourdDistance=b.transform.position.x-1010;
        rapport.masse=rapport.legerDistance>rapport.lourdDistance*5;
        rapport.chute=a.transform.position.y<999.5f;
        Destroy(a.gameObject);Destroy(b.gameObject);Destroy(f.gameObject);
        rapport.ok=rapport.balles&&rapport.peinture&&rapport.couleurs&&rapport.animation&&rapport.pause&&rapport.recharge&&rapport.masse&&rapport.fixation&&rapport.chute&&rapport.collisionJoueur&&rapport.mobilier>10;
        rapport.fini=true;
        Debug.Log("PAINTBALL VERIFICATION "+JsonUtility.ToJson(rapport));
        Publier(JsonUtility.ToJson(rapport));
        // Keep the actual impact marks visible for the opt-in visual check.
    }
    ObjetMobilePaintball Corps(string nom,Vector3 pos,float masse,float fixation)
    {
        var go=GameObject.CreatePrimitive(PrimitiveType.Cube);go.name=nom;go.transform.position=pos;
        go.AddComponent<Rigidbody>();var objet=go.AddComponent<ObjetMobilePaintball>();objet.Initialiser(masse,fixation);return objet;
    }
    void Publier(string json)
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        VerificationNavigateur(json);
#endif
    }
#if UNITY_WEBGL && !UNITY_EDITOR
    [System.Runtime.InteropServices.DllImport("__Internal")] static extern void VerificationNavigateur(string json);
#endif
}

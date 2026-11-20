using System;
using System.Collections;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.UI;

// Interface native : vues du domaine en 3D, choix des espaces et visite libre.
public partial class InterfaceVisite : MonoBehaviour
{
    public TMP_FontAsset titrage;
    public TMP_FontAsset corps;
    static readonly Color Ivoire = Hex("F4F0E7"), Vert = Hex("173D34"), Encre = Hex("243830"), Laiton = Hex("AD9464");
    static readonly Color Secondaire = Hex("5A685C");
    public enum Ecran { Accueil, Espaces, Commandes, Visite, Histoire, PausePaintball, Options }
    public Ecran EcranActuel { get; private set; }
    public int EspaceActuel { get; private set; }
    public bool VisiteCommencee { get; private set; }

    struct Lieu
    {
        public string nom, niveau, description;
        public Vector3 pieds;
        public float cap;
        public Lieu(string n, string nv, string d, Vector3 p, float c = 0) { nom=n; niveau=nv; description=d; pieds=p; cap=c; }
    }
    static readonly Lieu[] Lieux = {
        new("Le vestibule", "Rez-de-chaussée", "Le grand escalier et les galeries du château.", new(0,-7.5f,0)),
        new("Le salon bow-window", "Rez-de-chaussée", "Un salon ouvert sur le jardin.", new(0,5.2f,0)),
        new("La salle de billard", "Rez-de-chaussée", "Boiseries, plafond à caissons et cheminée.", new(5f,1.3f,0)),
        new("La bibliothèque", "Premier étage", "Une pièce intime aux boiseries sombres.", new(0.4f,-4f,5.35f),180),
        new("La salle à manger", "Premier étage", "La table, les moulures et les vues sur le parc.", new(5f,1.6f,5.35f)),
        new("Les chambres", "Premier étage", "Les chambres et leur enfilade.", new(12f,3.5f,5.35f)),
        new("La terrasse", "À l’extérieur", "La façade jardin et ses abords.", new(10,11.5f,-0.05f),180),
        new("Le parc et la piscine", "À l’extérieur", "La piscine, sa fontaine et les allées fleuries du parc.", new(6,51,-3.2f))
    };

    Canvas canvas;
    RectTransform contenu;
    Explorateur explorateur;
    CharacterController controleur;
    Camera cameraVisite;
    Vector3 positionSauvee;
    Quaternion rotationSauvee, teteSauvee;
    bool positionMemorisee, automatique;
    TMP_Text lieuHud, porteHud;
    GameObject indicationPorte;
    readonly System.Collections.Generic.Stack<(Ecran ecran, int espace, string focus)> pile = new();
    Porte porteActive;
    PointHistorique pointActuel;
    RectTransform zoneSure;
    TMP_Text titreDestination, detailDestination, niveauDestination;
    public static bool MouvementActif => PlayerPrefs.GetInt("InterfaceMouvement",1)==1;

    static Color Hex(string h) { ColorUtility.TryParseHtmlString("#"+h, out var c); return c; }
    void Start()
    {
        var args = Environment.GetCommandLineArgs();
        automatique = args.Contains("-capture") || args.Contains("-verification");
        if (automatique) { enabled=false; return; }
        explorateur = FindAnyObjectByType<Explorateur>();
        controleur = explorateur.GetComponent<CharacterController>();
        cameraVisite = explorateur.GetComponentInChildren<Camera>();
        explorateur.EchapGereParInterface = true;
        var go = new GameObject("InterfaceChateau", typeof(RectTransform), typeof(Canvas), typeof(UnityEngine.UI.CanvasScaler), typeof(UnityEngine.UI.GraphicRaycaster));
        canvas = go.GetComponent<Canvas>(); canvas.renderMode = RenderMode.ScreenSpaceOverlay; canvas.sortingOrder=100;
        var scaler = go.GetComponent<UnityEngine.UI.CanvasScaler>();
        scaler.uiScaleMode=UnityEngine.UI.CanvasScaler.ScaleMode.ScaleWithScreenSize;
        // Téléphone : interface 1,5 fois plus grande pour rester lisible et touchable.
        scaler.referenceResolution=Tactile.Actif?new(1280,720):new(1920,1080); scaler.matchWidthOrHeight=0.5f;
        if (FindAnyObjectByType<EventSystem>() == null)
        {
            var ev = new GameObject("EvenementsInterface", typeof(EventSystem), typeof(InputSystemUIInputModule));
            ev.GetComponent<InputSystemUIInputModule>().AssignDefaultActions();
        }
        zoneSure=Zone(canvas.transform,"ZoneSure",Vector2.zero,Vector2.one);
        zoneSure.gameObject.AddComponent<ZoneSureInterface>();
        explorateur.PositionChangee += ActualiserLieu;
        explorateur.PorteViseeChangee += ActualiserPorte;
        explorateur.PointHistoriqueViseChange += ActualiserPointHistorique;
        explorateur.InteractifViseChange += ActualiserInteractif;
        InitialiserPaintball();
        AfficherAccueil();
    }

    void Update()
    {
        AnimerAccueil();
        AnimerHud();
        if(partie != null && partie.Active && partie.Terminee) return;
        bool retour = Keyboard.current != null && Keyboard.current.escapeKey.wasPressedThisFrame;
        bool pauseManette = Gamepad.current != null && Gamepad.current.startButton.wasPressedThisFrame;
        bool retourManette = Gamepad.current != null && Gamepad.current.buttonEast.wasPressedThisFrame;
        if (retour || pauseManette || (retourManette && EcranActuel != Ecran.Visite))
        {
            if (EcranActuel == Ecran.Visite) { if (partie != null && partie.Active) AfficherPausePaintball(); else AfficherEspaces(EspaceActuel); }
            else Retour();
        }
    }

    public void Retour()
    {
        if (EcranActuel == Ecran.Options) Reglages.Enregistrer();
        if (pile.Count == 0) { if (VisiteCommencee) Reprendre(); return; }
        var etat=pile.Pop();
        if(etat.ecran==Ecran.Visite) { Reprendre(); return; }
        if(etat.ecran==Ecran.Accueil) AfficherAccueil(false);
        else if(etat.ecran==Ecran.Espaces) AfficherEspaces(etat.espace,false);
        else if(etat.ecran==Ecran.Histoire) Reprendre();
        else if(etat.ecran==Ecran.PausePaintball) AfficherPausePaintball(false);
        else if(etat.ecran==Ecran.Options) AfficherOptions(false);
        else AfficherCommandes(false);
        Canvas.ForceUpdateCanvases();
        var bouton=contenu.GetComponentsInChildren<UnityEngine.UI.Button>().FirstOrDefault(b=>b.name==etat.focus);
        if(bouton!=null) Selectionner(bouton);
    }

    void ActualiserLieu(Vector3 p)
    {
        if(EcranActuel!=Ecran.Visite || lieuHud==null) return;
        string nom = p.z>45 ? "Le parc et la piscine" : p.z>9.2f || Mathf.Abs(p.x)>16.6f || p.z < -8.9f ? "Les jardins" :
            p.y>4.7f ? (p.z< -3.25f && Mathf.Abs(p.x)<3.1f ? "La bibliothèque" : p.z<0.7f ? "Les galeries" :
            -p.x>10.3f || -p.x<3.3f ? "Les chambres" : "La salle à manger") :
            Mathf.Abs(p.x)<3.3f ? (p.z>3.65f ? "Le salon bow-window" : p.z> -3.2f ? "L’escalier d’honneur" : "Le vestibule") :
            p.x< -3.3f && p.x> -10.3f && p.z> -2.9f ? "La salle de billard" : "Les salons";
        if(lieuHud.text!=nom) lieuHud.text=nom;
    }
    void ActualiserPorte(Porte porte)
    {
        if(porteActive!=null) porteActive.EtatChange-=EtatPorte;
        porteActive=porte;
        if(porteActive!=null) porteActive.EtatChange+=EtatPorte;
        if(indicationPorte!=null) indicationPorte.SetActive(EcranActuel==Ecran.Visite && (porte!=null || pointActuel!=null));
        if(porte!=null) EtatPorte(porte.Ouverte);
        else if(pointActuel!=null && porteHud!=null) porteHud.text="E  ·  Découvrir l’histoire";
    }
    // Trappe du toit, scooter : « E · <action> » à la place de l'invite des portes.
    IInteractif interactifActuel;
    void ActualiserInteractif(IInteractif i)
    {
        interactifActuel=i;
        bool montre=EcranActuel==Ecran.Visite && (porteActive!=null || pointActuel!=null || i!=null || explorateur.Monture!=null);
        if(indicationPorte!=null) indicationPorte.SetActive(montre);
        if(porteHud==null || porteActive!=null) return;
        if(explorateur.Monture!=null) porteHud.text="E  ·  Descendre du "+explorateur.Monture.Nom.Replace("le ","");
        else if(i!=null) porteHud.text="E  ·  "+i.Libelle(explorateur);
        else if(pointActuel!=null) porteHud.text="E  ·  Découvrir l’histoire";
    }
    void ActualiserPointHistorique(PointHistorique point)
    {
        pointActuel=point;
        if(indicationPorte!=null) indicationPorte.SetActive(EcranActuel==Ecran.Visite && (porteActive!=null || point!=null));
        if(porteActive==null && point!=null && porteHud!=null) porteHud.text="E  ·  Découvrir l’histoire";
    }
    void EtatPorte(bool ouverte)
    {
        if(porteHud!=null) porteHud.text="E  ·  "+(ouverte?"Fermer la porte":"Ouvrir la porte");
    }
    void OnDestroy()
    {
        if(explorateur!=null) { explorateur.PositionChangee-=ActualiserLieu; explorateur.PorteViseeChangee-=ActualiserPorte; explorateur.PointHistoriqueViseChange-=ActualiserPointHistorique; explorateur.InteractifViseChange-=ActualiserInteractif; }
        if(porteActive!=null) porteActive.EtatChange-=EtatPorte;
    }

    void Nouveau(Ecran ecran, bool empiler=true)
    {
        if (EcranActuel == Ecran.Visite && !positionMemorisee)
        {
            positionSauvee=explorateur.transform.position; rotationSauvee=explorateur.transform.rotation;
            teteSauvee=cameraVisite.transform.localRotation; positionMemorisee=true;
        }
        if(empiler && contenu!=null && ecran!=EcranActuel)
            pile.Push((EcranActuel,EspaceActuel,EventSystem.current.currentSelectedGameObject?.name));
        EcranActuel=ecran;
        Time.timeScale = partie != null && partie.Active && ecran != Ecran.Visite && partie.Mode != PaintballSolo.ModePartie.EnLigne ? 0f : 1f;
        if (contenu != null) { contenu.gameObject.SetActive(false); Destroy(contenu.gameObject); }
        contenu=Zone(zoneSure,"Ecran"+ecran,Vector2.zero,Vector2.one);
        explorateur.Suspendre(ecran != Ecran.Visite);
        if(ecran!=Ecran.Visite) Voile(contenu,"OmbreHaute",new(0,.75f),Vector2.one,Color.clear,new Color(.025f,.06f,.05f,.8f));
    }

    public void AfficherAccueil(bool empiler=true)
    {
        Nouveau(Ecran.Accueil,empiler);
        ApercuScene(new Vector3(0,62,12),new Vector3(0,1,6),0);
        cameraVisite.fieldOfView=45f;
        if(partie!=null) { AfficherAccueilPaintball(); return; }
        Voile(contenu,"OmbreLaterale",Vector2.zero,new(.66f,1),new Color(.025f,.075f,.06f,.93f),Color.clear,true);
        Voile(contenu,"OmbreBasse",Vector2.zero,new(1,.51f),new Color(.025f,.065f,.05f,.91f),Color.clear);
        Texte(contenu,"Signature","Château Saint-Victor",25,new(.045f,.90f),new(.50f,.965f),Ivoire);
        Filet(contenu,new(.045f,.895f),new(.955f,.895f));
        var commandes=Bouton(contenu,"OuvrirCommandes","Les commandes",new(.62f,.91f),new(.82f,.97f),()=>AfficherCommandes(),false,true);
        var quitter=Bouton(contenu,"QuitterApplication","Quitter",new(.845f,.91f),new(.96f,.97f),Application.Quit,false,true);
        Texte(contenu,"TitreAccueil","Saint-Victor",146,new(.04f,.20f),new(.81f,.405f),Ivoire,true);
        Texte(contenu,"Invitation","Le domaine devient votre terrain de jeu.",29,new(.047f,.165f),new(.67f,.23f),Ivoire);
        Texte(contenu,"PiedAccueil","Paintball  ·  Solo  ·  sans limite de temps pour faire le plein de couleurs",19,new(.047f,.065f),new(.62f,.12f),Ivoire);
        var espaces=Bouton(contenu,"ChoisirEspaces","Parcourir les espaces",new(.047f,.125f),new(.31f,.18f),()=>AfficherEspaces(0),false,true);
        var entrer=BoutonRond(contenu,"CommencerPartie","Jouer",new(.83f,.10f),new(.95f,.29f),CommencerPaintball);
        Texte(contenu,"LegendeEntrer","Partie solo",18,new(.80f,.05f),new(.98f,.11f),Ivoire,false,TextAlignmentOptions.Center);
        Relier(entrer,commandes,espaces,espaces,quitter);
        Relier(espaces,entrer,commandes,commandes,entrer);
        Relier(commandes,espaces,entrer,espaces,quitter);
        Relier(quitter,commandes,entrer,commandes,entrer);
        Selectionner(entrer);
    }

    public void AfficherEspaces(int index, bool empiler=true)
    {
        EspaceActuel=Mathf.Clamp(index,0,Lieux.Length-1);
        Nouveau(Ecran.Espaces,empiler);
        cameraVisite.rect=new Rect(0,0,1,1); cameraVisite.fieldOfView=60f;
        Voile(contenu,"OmbreNavigation",Vector2.zero,new(.57f,1),new Color(.025f,.075f,.06f,.97f),Color.clear,true);
        Voile(contenu,"OmbreLegende",Vector2.zero,new(1,.43f),new Color(.025f,.065f,.05f,.95f),Color.clear);
        Bouton(contenu,"RetourAccueil","Accueil",new(.035f,.91f),new(.18f,.97f),()=>AfficherAccueil(),false,true);
        Bouton(contenu,"OuvrirOptions","Options",new(.19f,.91f),new(.31f,.97f),()=>AfficherOptions(),false,true);
        if(VisiteCommencee) Bouton(contenu,"ReprendreDepuisEspaces","Reprendre la visite",new(.73f,.91f),new(.97f,.97f),Reprendre,false,true);
        Texte(contenu,"TitreEspaces","Les espaces",66,new(.045f,.77f),new(.58f,.90f),Ivoire,true);
        var liste=Zone(contenu,"ParcoursEspaces",new(.042f,.14f),new(.365f,.755f));
        var disposition=liste.gameObject.AddComponent<UnityEngine.UI.VerticalLayoutGroup>();
        disposition.spacing=2f; disposition.childControlWidth=true; disposition.childControlHeight=true;
        disposition.childForceExpandWidth=true; disposition.childForceExpandHeight=true;
        var boutons=new UnityEngine.UI.Button[Lieux.Length];
        for(int i=0;i<Lieux.Length;i++)
        {
            int choix=i;
            var ligne=Bouton(liste,"Espace"+i,Lieux[i].nom,Vector2.zero,Vector2.one,()=>Entrer(choix),false,true);
            var dimension=ligne.gameObject.AddComponent<UnityEngine.UI.LayoutElement>();
            dimension.minHeight=64f; dimension.preferredHeight=76f; dimension.flexibleHeight=1f;
            var label=ligne.GetComponentInChildren<TMP_Text>(); label.fontSize=28; label.alignment=TextAlignmentOptions.MidlineLeft;
            label.rectTransform.anchorMin=new(.045f,0); label.rectTransform.anchorMax=new(.97f,1);
            var survol=ligne.gameObject.AddComponent<DestinationInterface>(); survol.interfaceVisite=this; survol.index=i;
            Filet(ligne.transform,Vector2.zero,new Vector2(1,0));
            boutons[i]=ligne;
        }
        Texte(contenu,"InvitationNavigation","Survolez pour découvrir. Cliquez pour entrer.",18,new(.047f,.075f),new(.55f,.13f),Ivoire);
        titreDestination=Texte(contenu,"NomEspace","",68,new(.43f,.22f),new(.92f,.40f),Ivoire,true);
        niveauDestination=Texte(contenu,"NiveauEspace","",20,new(.435f,.17f),new(.89f,.23f),Ivoire);
        detailDestination=Texte(contenu,"DescriptionEspace","",22,new(.435f,.10f),new(.79f,.18f),Ivoire);
        BoutonRond(contenu,"EntrerEspace","Entrer",new(.85f,.065f),new(.97f,.22f),()=>Entrer(EspaceActuel));
        Presenter(EspaceActuel);
        Selectionner(boutons[EspaceActuel]);
    }

    public void Presenter(int index)
    {
        if(EcranActuel!=Ecran.Espaces || titreDestination==null) return;
        EspaceActuel=Mathf.Clamp(index,0,Lieux.Length-1);
        var lieu=Lieux[EspaceActuel];
        Placer(lieu); cameraVisite.rect=new Rect(0,0,1,1); cameraVisite.fieldOfView=60f;
        titreDestination.text=lieu.nom; niveauDestination.text=lieu.niveau; detailDestination.text=lieu.description;
    }

    public void AfficherCommandes(bool empiler=true)
    {
        Nouveau(Ecran.Commandes,empiler);
        ApercuScene(new Vector3(0,62,12),new Vector3(0,1,6),0); cameraVisite.fieldOfView=45f;
        Voile(contenu,"VoileCommandes",Vector2.zero,new(.84f,1),new Color(.025f,.075f,.06f,.98f),Color.clear,true);
        Texte(contenu,"TitreCommandes","Les commandes",78,new(.045f,.78f),new(.76f,.92f),Ivoire,true);
        var panneau=Zone(contenu,"ContenuCommandes",new(.035f,0),new(.56f,1));
        string[] touches={"ZQSD / touches directionnelles","Souris","E ou clic","Majuscule","Espace","C ou Ctrl","Échap"};
        string[] actions={"Se déplacer","Regarder autour de soi","Ouvrir ou fermer une porte","Marcher plus vite","Sauter","S'accroupir (C bascule, Ctrl maintenu)","Ouvrir le menu et reprendre"};
        for(int i=0;i<touches.Length;i++)
        {
            float y=.715f-i*.083f;
            Texte(panneau,"Touche"+i,touches[i],25,new(.025f,y-.04f),new(.98f,y),Ivoire);
            Texte(panneau,"Commande"+i,actions[i],19,new(.025f,y-.072f),new(.98f,y-.04f),Ivoire);
            Filet(panneau,new(.025f,y-.077f),new(.98f,y-.077f));
        }
        Surface(panneau,"FondAideMenu",new(.015f,.11f),new(.99f,.20f),Vert);
        Texte(panneau,"AideMenu","Menus : flèches et Entrée, ou croix directionnelle et bouton de validation à la manette.",19,new(.035f,.115f),new(.97f,.19f),Ivoire);
        Bouton(panneau,"ReglerAnimations","Animations : "+(MouvementActif?"activées":"réduites"),new(.025f,.035f),new(.70f,.105f),()=>
        {
            PlayerPrefs.SetInt("InterfaceMouvement",MouvementActif?0:1); PlayerPrefs.Save(); AfficherCommandes(false);
            Selectionner(contenu.GetComponentsInChildren<UnityEngine.UI.Button>().First(b=>b.name=="ReglerAnimations"));
        },false,true);
        Selectionner(BoutonRond(contenu,"RetourCommandes","Retour",new(.84f,.06f),new(.96f,.23f),Retour));
    }

    public void AfficherHistoire(PointHistorique point)
    {
        if(point==null) return;
        Nouveau(Ecran.Histoire);
        Voile(contenu,"VoileHistoire",Vector2.zero,Vector2.one,new Color(.025f,.06f,.05f,.96f),new Color(.025f,.06f,.05f,.82f));
        Surface(contenu,"PanneauHistoire",new(.13f,.16f),new(.87f,.84f),Ivoire);
        Filet(contenu,new(.19f,.735f),new(.81f,.735f));
        Texte(contenu,"SurtitreHistoire","REPÈRE HISTORIQUE  ·  CHÂTEAU SAINT-VICTOR",18,new(.19f,.77f),new(.81f,.83f),Vert);
        Texte(contenu,"TitreHistoire",point.Titre,62,new(.19f,.62f),new(.81f,.73f),Vert,true);
        Texte(contenu,"TexteHistoire",point.Explication,27,new(.19f,.34f),new(.81f,.60f),Encre);
        Texte(contenu,"SourceHistoire","Source : "+point.Source,17,new(.19f,.24f),new(.81f,.31f),Secondaire);
        Selectionner(BoutonRond(contenu,"FermerHistoire","Reprendre",new(.72f,.07f),new(.84f,.19f),Retour));
    }

    void ApercuScene(Vector3 position, Vector3 cible, float debut)
    {
        controleur.enabled=false;
        Vector3 cameraMonde=new(-position.x,position.z,position.y);
        Vector3 cibleMonde=new(-cible.x,cible.z,cible.y);
        Quaternion vue=Quaternion.LookRotation(cibleMonde-cameraMonde);
        explorateur.transform.SetPositionAndRotation(cameraMonde-Vector3.up*PaintballSolo.Yeux,Quaternion.Euler(0,vue.eulerAngles.y,0));
        explorateur.RetablirRegard(Quaternion.Euler(Mathf.DeltaAngle(0,vue.eulerAngles.x),0,0));
        controleur.enabled=true;
        cameraVisite.rect=new Rect(debut,0,1-debut,1);
    }

    public void Entrer(int index)
    {
        if(partie != null && partie.Active) partie.Arreter();
        EspaceActuel=index; VisiteCommencee=true; positionMemorisee=false;
        Placer(Lieux[index]);
        AfficherVisite();
    }
    public void Reprendre()
    {
        if (positionMemorisee)
        {
            controleur.enabled=false; explorateur.transform.SetPositionAndRotation(positionSauvee,rotationSauvee);
            explorateur.RetablirRegard(teteSauvee); controleur.enabled=true; Physics.SyncTransforms();
        }
        positionMemorisee=false; AfficherVisite();
    }
    void Placer(Lieu lieu)
    {
        controleur.enabled=false;
        // Après le miroir D-026 : Blender (x,y,z) -> Unity (-x,z,y).
        explorateur.transform.SetPositionAndRotation(new(-lieu.pieds.x,lieu.pieds.z+.08f,lieu.pieds.y),Quaternion.Euler(0,-lieu.cap,0));
        explorateur.ReinitialiserRegard(); controleur.enabled=true; Physics.SyncTransforms();
    }
    void AfficherVisite()
    {
        Nouveau(Ecran.Visite,false); pile.Clear(); cameraVisite.rect=new Rect(0,0,1,1); cameraVisite.fieldOfView=Reglages.ChampVision;
        if(partie != null && partie.Active) { AfficherHudPaintball(); return; }
        Voile(contenu,"OmbreHud",Vector2.zero,new(1,.22f),new Color(.025f,.065f,.05f,.78f),Color.clear);
        lieuHud=Texte(contenu,"LieuActuel",Lieux[EspaceActuel].nom,40,new(.035f,.075f),new(.65f,.16f),Ivoire,true);
        Texte(contenu,"SignatureLieu","Château Saint-Victor",18,new(.038f,.03f),new(.60f,.08f),Ivoire);
        var menu=Surface(contenu,"RappelMenu",new(.80f,.915f),new(.975f,.97f),Vert);
        Texte(menu,"RaccourciMenu","Échap  ·  Les espaces",18,new(.04f,0),new(.96f,1),Ivoire, false,TextAlignmentOptions.Center);
        var aide=Surface(contenu,"AideDeplacement",new(.025f,.91f),new(.49f,.97f),Vert);
        Texte(aide,"Commandes","ZQSD  ·  Se déplacer       Souris  ·  Regarder",18,new(.035f,0),new(.97f,1),Ivoire);
        var prompt=Surface(contenu,"InteractionPorte",new(.30f,.14f),new(.70f,.198f),Vert);
        indicationPorte=prompt.gameObject;
        porteHud=Texte(prompt,"ActionPorte","E  ·  Ouvrir la porte",20,Vector2.zero,Vector2.one,Ivoire,false,TextAlignmentOptions.Center);
        indicationPorte.SetActive(false);
        EventSystem.current.SetSelectedGameObject(null);
        ActualiserLieu(explorateur.transform.position);
        if(pointActuel!=null && porteActive==null) porteHud.text="E  ·  Découvrir l’histoire";
        if(Tactile.Actif) { aide.gameObject.SetActive(false); menu.gameObject.SetActive(false); CommandesTactilesHud(false,Vert); }
        StartCoroutine(MasquerAide(aide.gameObject));
    }

    RectTransform Zone(Transform parent,string nom,Vector2 min,Vector2 max)
    {
        var go=new GameObject(nom,typeof(RectTransform)); var rt=go.GetComponent<RectTransform>();
        rt.SetParent(parent,false); rt.anchorMin=min; rt.anchorMax=max; rt.offsetMin=rt.offsetMax=Vector2.zero;
        return rt;
    }
    RectTransform Surface(Transform parent,string nom,Vector2 min,Vector2 max,Color couleur)
    {
        var rt=Zone(parent,nom,min,max); var image=rt.gameObject.AddComponent<UnityEngine.UI.Image>();
        image.color=couleur; image.raycastTarget=false; return rt;
    }
    TMP_Text Texte(Transform parent,string nom,string texte,float taille,Vector2 min,Vector2 max,Color couleur,bool serif=false,TextAlignmentOptions align=TextAlignmentOptions.MidlineLeft)
    {
        var rt=Zone(parent,nom,min,max); var t=rt.gameObject.AddComponent<TextMeshProUGUI>();
        t.font=serif?titrage:corps; t.text=texte; t.fontSize=taille; t.color=couleur; t.alignment=align;
        t.textWrappingMode=TextWrappingModes.Normal; t.overflowMode=TextOverflowModes.Overflow;
        t.raycastTarget=false; return t;
    }
    void Filet(Transform parent,Vector2 min,Vector2 max)
    {
        var rt=Surface(parent,"Filet",min,max,new Color(Laiton.r,Laiton.g,Laiton.b,.45f));
        rt.sizeDelta=new(0,1);
    }
    UnityEngine.UI.Button Bouton(Transform parent,string nom,string texte,Vector2 min,Vector2 max,Action action,bool plein=false,bool surVert=false,bool actif=false)
    {
        Color fond=plein?Vert:actif?Hex("E1E7DD"):new Color(0,0,0,0);
        if(nom=="OuvrirCommandes" || nom=="QuitterApplication" || nom=="ReprendreDepuisEspaces") fond=Vert;
        var rt=Surface(parent,nom,min,max,Color.white); var image=rt.GetComponent<UnityEngine.UI.Image>(); image.raycastTarget=true;
        var b=rt.gameObject.AddComponent<UnityEngine.UI.Button>(); b.targetGraphic=image;
        Color survol=plein?Hex("2D5648"):surVert?Hex("36594B"):Hex("E1E7DD");
        var couleurs=b.colors; couleurs.normalColor=fond; couleurs.highlightedColor=survol; couleurs.selectedColor=plein?Hex("396451"):surVert?Hex("456A55"):Hex("D1DCC6");
        couleurs.pressedColor=plein?Hex("102D25"):surVert?Hex("284C3E"):Hex("D2DBC8"); couleurs.fadeDuration=.16f; b.colors=couleurs;
        b.onClick.AddListener(()=>action()); b.onClick.AddListener(SonsPaintball.Menu);
        rt.gameObject.AddComponent<FocusInterface>();
        Texte(rt,"Libelle",texte,21,new(.045f,0),new(.955f,1),plein||surVert?Ivoire:Encre,false,TextAlignmentOptions.Center);
        return b;
    }
    void Voile(Transform parent,string nom,Vector2 min,Vector2 max,Color debut,Color fin,bool horizontal=false)
    {
        var rt=Zone(parent,nom,min,max); var voile=rt.gameObject.AddComponent<VoileInterface>();
        voile.debut=debut; voile.fin=fin; voile.horizontal=horizontal; voile.raycastTarget=false;
    }
    UnityEngine.UI.Button BoutonRond(Transform parent,string nom,string libelle,Vector2 min,Vector2 max,Action action)
    {
        var rt=Zone(parent,nom,min,max);
        var ratio=rt.gameObject.AddComponent<UnityEngine.UI.AspectRatioFitter>();
        ratio.aspectMode=UnityEngine.UI.AspectRatioFitter.AspectMode.HeightControlsWidth; ratio.aspectRatio=1;
        var disque=Zone(rt,"Disque",Vector2.zero,Vector2.one).gameObject.AddComponent<DisqueInterface>();
        disque.color=Vert;
        var bouton=rt.gameObject.AddComponent<UnityEngine.UI.Button>(); bouton.targetGraphic=disque;
        var c=bouton.colors; c.normalColor=Color.white; c.highlightedColor=new Color(1.3f,1.3f,1.1f); c.selectedColor=new Color(1.4f,1.4f,1.15f); c.pressedColor=new Color(.8f,.8f,.7f); c.fadeDuration=.12f; bouton.colors=c;
        bouton.onClick.AddListener(()=>action()); bouton.onClick.AddListener(SonsPaintball.Menu);
        // Libellé sur une seule ligne, réduit si besoin pour tenir dans le disque.
        var l=Texte(rt,"Libelle",libelle,31,new(.06f,.1f),new(.94f,.9f),Ivoire,false,TextAlignmentOptions.Center);
        l.textWrappingMode=TextWrappingModes.NoWrap; l.enableAutoSizing=true; l.fontSizeMin=14; l.fontSizeMax=31;
        rt.gameObject.AddComponent<FocusInterface>(); return bouton;
    }
    IEnumerator MasquerAide(GameObject aide)
    {
        yield return new WaitForSecondsRealtime(12f);
        if(aide!=null) aide.SetActive(false);
    }
    static void Relier(UnityEngine.UI.Button bouton,UnityEngine.UI.Selectable haut,UnityEngine.UI.Selectable bas,UnityEngine.UI.Selectable gauche,UnityEngine.UI.Selectable droite)
    {
        var nav=bouton.navigation; nav.mode=UnityEngine.UI.Navigation.Mode.Explicit;
        nav.selectOnUp=haut; nav.selectOnDown=bas; nav.selectOnLeft=gauche; nav.selectOnRight=droite; bouton.navigation=nav;
    }
    static void Selectionner(UnityEngine.UI.Button bouton) { if(bouton != null) EventSystem.current.SetSelectedGameObject(bouton.gameObject); }
}

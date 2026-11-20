using System;
using UnityEngine;
using UnityEngine.InputSystem;

[DefaultExecutionOrder(40)]
public class PaintballSolo : MonoBehaviour
{
    public GameObject personnage;
    public Transform marqueur, marqueurPOV, bouche, bouchePOV;
    public Animator animateur;
    public ImpactsPaintball impacts;
    public Material materiauBille, materiauTrainee;
    public GameObject terrainEntrainement;
    public static readonly Color[] Couleurs = { new(.10f,.85f,1f), new(1f,.23f,.53f),new(1f,.72f,.07f),new(.44f,1f,.27f),new(.64f,.33f,1f), new(1f,.42f,.12f) };
    public static readonly string[] NomsCouleurs = { "Cyan", "Framboise", "Soleil", "Citron vert", "Violet", "Mandarine" };
    public enum ModePartie { Entrainement, Bots, EnLigne }
    // Gabarit d'un enfant de 12 ans : 1,50 m, yeux à 1,40 m (le robot est mis à cette taille au démarrage).
    public const float Taille=1.5f,Yeux=1.22f;
    // Robot affiché plus petit que le gabarit de collision (1,20 m au lieu de 1,50 m).
    public const float Echelle=.8f;
    const float TailleRobotScene=1.72f;
    public ModePartie Mode { get; private set; }
    public int NombreBots { get; set; } = 2;
    public PartieBots.Niveau NiveauBots { get; set; } = PartieBots.Niveau.Normal;
    // Vies de chaque joueur contre les bots, gardées dans le navigateur (choix de l'accueil).
    public static readonly int[] ChoixVies = { 1, 2, 3, 5, 10 };
    public int Vies { get => PlayerPrefs.GetInt("PaintballVies", 3); set { PlayerPrefs.SetInt("PaintballVies", Mathf.Clamp(value, 1, 10)); PlayerPrefs.Save(); } }
    public PartieBots Bots { get; private set; }
    public float TempsEcoule { get; private set; }
    public bool Active { get; private set; }
    public bool TroisiemePersonne { get; private set; }
    public bool EnPause => !Active || interfaceVisite.EcranActuel != InterfaceVisite.Ecran.Visite || terminee;
    // En ligne, le monde ne s'arrête pas quand le joueur ouvre un menu : seules ses commandes sont suspendues.
    bool Fige => EnPause && !(Active && Mode==ModePartie.EnLigne);
    public float Tangage => explorateur.Tangage;
    public ClientReseau Reseau { get; private set; }
    public bool Terminee => terminee;
    public int Tirs { get; private set; }
    public int Touches { get; private set; }
    public int Chargeur { get; private set; } = 50;
    public int CouleurIndex { get; private set; }
    public int JoueurId { get; private set; }
    public Color Couleur => Couleurs[CouleurIndex];
    public float TempsRestant { get; private set; } = 90;
    public float DistanceVisee { get; private set; }
    public event Action Actualise;
    public event Action PartieFinie;
    public bool Recharge => rechargement > 0;
    public int ProjectilesActifs { get; private set; }
    public int ImpactsTotal { get; private set; }
    public int DernierProprietaire { get; private set; } = -1;
    public Color DerniereCouleur { get; private set; }
    public int AnimationEtat => animateur != null ? animateur.GetCurrentAnimatorStateInfo(0).shortNameHash : 0;
    public long EtapesPhysiques { get; private set; }
    public float RetourTouche { get; private set; }
    public float Ecart { get; private set; } = 9;
    public float ProgressionRecharge => rechargement > 0 ? 1 - rechargement / DureeRecharge : -1;
    public int MeilleurScore { get; private set; }
    public bool NouveauRecord { get; private set; }
    public Vector3 PointVise { get; private set; }
    const float DureeRecharge = 1.5f;
    Vector3 echelleRobot;
    // Taille d'affichage des billes : la physique garde le vrai diamètre de 17,3 mm.
    const float EchelleVisuelle = 2.1f;
    struct Bille { public bool active; public Vector3 position, vitesse; public Color couleur; public int joueur, tir; public float age; public Transform visuel; public Renderer rendu; public TrailRenderer trainee; }
    readonly Bille[] billes = new Bille[64];
    Camera cameraJeu;
    Explorateur explorateur;
    CharacterController controleur;
    InterfaceVisite interfaceVisite;
    ObjetMobilePaintball[] objets;
    InputAction feu, changerVue, recharger, viser;
    float prochainTir, rechargement, accumulateur;
    bool terminee, etaitVisite, avaitVerrou;
    int secondeHud, distanceHud;
    bool toucheHud;
    SonsPaintball sons;
    AnimationMarqueur pose;
    Material[] materiauxBilles;
    readonly System.Collections.Generic.Dictionary<Color,Material> autresMateriaux=new();
    float chaleur;
    Vector3 positionPrecedente;
    static readonly int VitesseAnimation=Animator.StringToHash("Vitesse");
    static readonly int SautAnimation=Animator.StringToHash("AuSol");
    // Tir et visée : souris, manette ou commandes tactiles (le toucher seul ne tire pas).
    bool Feu => Tactile.Actif ? Tactile.Tir : feu.IsPressed();
    bool Visee => viser.IsPressed() || Tactile.Visee;
    public void ChoisirMode(ModePartie mode) { Mode = mode; Actualise?.Invoke(); }
    public void ChoisirCouleur(int index)
    {
        CouleurIndex=Mathf.Abs(index)%Couleurs.Length; Actualise?.Invoke();
    }
    void Awake()
    {
        explorateur=GetComponent<Explorateur>();controleur=GetComponent<CharacterController>();
        cameraJeu=GetComponentInChildren<Camera>();interfaceVisite=FindAnyObjectByType<InterfaceVisite>();
        feu=InputSystem.actions.FindAction("Player/Attack");
        changerVue=new InputAction("ChangerVue",InputActionType.Button,"<Keyboard>/v");changerVue.AddBinding("<Gamepad>/rightStickPress");
        recharger=new InputAction("Recharger",InputActionType.Button,"<Keyboard>/r");recharger.AddBinding("<Gamepad>/buttonWest");
        viser=new InputAction("Viser",InputActionType.Button,"<Mouse>/rightButton");viser.AddBinding("<Gamepad>/leftTrigger");
        changerVue.Enable();recharger.Enable();viser.Enable();
        sons=SonsPaintball.Installer(gameObject);
        if(GetComponent<ResolutionAdaptative>()==null) gameObject.AddComponent<ResolutionAdaptative>();
        if(GetComponent<MesuresPerf>()==null) gameObject.AddComponent<MesuresPerf>();
        controleur.height=Taille;controleur.center=Vector3.up*Taille*.5f;
        cameraJeu.transform.localPosition=new Vector3(0,Yeux,0);
        if(personnage!=null) { float k=Taille/TailleRobotScene*Echelle;personnage.transform.localScale*=k;personnage.transform.localPosition*=k; }
        Bots=GetComponent<PartieBots>();if(Bots==null) Bots=gameObject.AddComponent<PartieBots>();
        Reseau=ClientReseau.Installer(this);
        MeilleurScore=PlayerPrefs.GetInt("PaintballMeilleurScore",0);
        if (personnage != null) personnage.SetActive(false);
        if (marqueur != null) marqueur.gameObject.SetActive(false);
        if (marqueurPOV != null) marqueurPOV.gameObject.SetActive(false);
        if(terrainEntrainement!=null) terrainEntrainement.SetActive(false);
    }
    void Start()
    {
        objets=FindObjectsByType<ObjetMobilePaintball>(FindObjectsInactive.Include);
        pose=GetComponent<AnimationMarqueur>();if(pose==null) pose=gameObject.AddComponent<AnimationMarqueur>();
        pose.Initialiser(this,personnage.transform);
        // Décor vivant : joueurs de tennis sur le court, perruches dans les arbres du parc.
        TennisAnime.Installer(personnage);Perruches.Installer();GardesPortail.Installer(personnage,transform);Fumeur.Installer(personnage);ObjetsDomaine.Installer(this);
        // Un matériau partagé par couleur : compatible SRP Batcher, contrairement aux MaterialPropertyBlock.
        materiauxBilles=new Material[Couleurs.Length];
        for(int c=0;c<Couleurs.Length;c++)
        { var m=new Material(materiauBille){name="Bille"+NomsCouleurs[c]};m.SetColor("_BaseColor",Couleurs[c]);m.SetFloat("_Smoothness",.88f);materiauxBilles[c]=m; }
        var largeur=new AnimationCurve(new Keyframe(0,1),new Keyframe(1,0));
        for(int i=0;i<billes.Length;i++)
        {
            var v=GameObject.CreatePrimitive(PrimitiveType.Sphere);v.name="BillePaintball";v.layer=2;
            Destroy(v.GetComponent<Collider>());v.transform.localScale=Vector3.one*BalistiquePaintball.Diametre*EchelleVisuelle;
            var r=v.GetComponent<Renderer>();r.sharedMaterial=materiauxBilles[0];r.shadowCastingMode=UnityEngine.Rendering.ShadowCastingMode.Off;r.receiveShadows=false;
            var t=v.AddComponent<TrailRenderer>();t.sharedMaterial=materiauTrainee;t.time=.075f;t.minVertexDistance=.15f;
            t.widthMultiplier=BalistiquePaintball.Diametre*EchelleVisuelle*.9f;t.widthCurve=largeur;t.numCapVertices=2;
            t.shadowCastingMode=UnityEngine.Rendering.ShadowCastingMode.Off;t.receiveShadows=false;t.emitting=false;
            v.SetActive(false);billes[i].visuel=v.transform;billes[i].rendu=r;billes[i].trainee=t;
        }
    }
    public void Demarrer()
    {
        // En ligne, la partie commence au message debut du serveur (DemarrerEnLigne) : ouvrir le salon.
        if(Mode==ModePartie.EnLigne) { Reseau.OuvrirSalon();return; }
        PodiumPaintball.Cacher();
        JoueurId=0;ViderBilles();impacts.Nettoyer();terrainEntrainement.SetActive(false);
        if(objets!=null) foreach(var o in objets) o.Reinitialiser();
        Bots.Arreter();ObjetsDomaine.NouvellePartie();
        Active=true;terminee=false;NouveauRecord=false;Tirs=Touches=ImpactsTotal=0;chaleur=0;Chargeur=50;TempsRestant=90;TempsEcoule=0;
        prochainTir=Time.time+.25f;rechargement=accumulateur=0;TroisiemePersonne=false;RetourTouche=0;
        controleur.enabled=false;transform.SetPositionAndRotation(new Vector3(-12,-1.65f,44),Quaternion.identity);
        // Snap onto the park ground, ignoring the player and the practice props.
        if(Physics.Raycast(new Vector3(-12,5,44),Vector3.down,out var sol,12,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore))
            transform.position=new Vector3(-12,sol.point.y+.08f,44);
        explorateur.ReinitialiserRegard();explorateur.RetablirRegard(Quaternion.Euler(4,0,0));controleur.enabled=true;Physics.SyncTransforms();
        PartieBots.Teinter(personnage,Couleur,true);
        if(Mode==ModePartie.Bots) Bots.Demarrer(NombreBots,NiveauBots);
        else
        {
            PlacerEntrainement();terrainEntrainement.SetActive(true);Physics.SyncTransforms();
            foreach(var cible in terrainEntrainement.GetComponentsInChildren<CiblePaintball>()) cible.disponible=0;
        }
        positionPrecedente=transform.position;Actualise?.Invoke();
    }
    // Début d'une partie en ligne : numéro attribué par le serveur, joueurs du salon, points de départ.
    public void DemarrerEnLigne(int moi,JoueurServeur[] salon,JoueurServeur[] placements,int cible,int vies)
    {
        PodiumPaintball.Cacher();
        ViderBilles();impacts.Nettoyer();terrainEntrainement.SetActive(false);
        if(objets!=null) foreach(var o in objets) o.Reinitialiser();
        Mode=ModePartie.EnLigne;JoueurId=moi;ObjetsDomaine.NouvellePartie();
        var info=System.Array.Find(salon??new JoueurServeur[0],x=>x.j==moi);if(info!=null) ChoisirCouleur(info.c);
        Active=true;terminee=false;NouveauRecord=false;Tirs=Touches=ImpactsTotal=0;chaleur=0;Chargeur=50;TempsRestant=90;TempsEcoule=0;
        prochainTir=Time.time+.25f;rechargement=accumulateur=0;TroisiemePersonne=false;RetourTouche=0;
        PartieBots.Teinter(personnage,Couleur,true);
        Bots.DemarrerEnLigne(salon,placements,cible,vies);
        positionPrecedente=transform.position;
        interfaceVisite.CommencerEnLigne();
        Actualise?.Invoke();
    }
    // Correction du serveur (déplacement refusé) : se replacer à la dernière position acceptée.
    public void Replacer(Vector3 p)
    {
        controleur.enabled=false;transform.position=p;controleur.enabled=true;Physics.SyncTransforms();positionPrecedente=p;
    }
    // Tir d'un autre joueur en ligne : bille affichée et simulée ici, sans effet sur les vies (le serveur décide).
    public void TirDistant(int joueur,Vector3 origine,Vector3 vitesse)
    {
        var j=Bots.Match?.Joueur(joueur);
        AjouterBille(origine,vitesse,j!=null?Couleurs[Mathf.Clamp(j.couleur,0,Couleurs.Length-1)]:Color.white,joueur);
        sons.TirDistant(origine);
        Bots.AnimerTir(joueur);
    }
    public void Arreter()
    {
        if(Mode==ModePartie.EnLigne && Active) Reseau.Quitter();
        PodiumPaintball.Cacher();
        Active=false;ViderBilles();terrainEntrainement.SetActive(false);Bots.Arreter();
        cameraJeu.transform.localPosition=new Vector3(0,Yeux,0);cameraJeu.fieldOfView=Reglages.ChampVision;
        personnage.SetActive(false);marqueur.gameObject.SetActive(false);marqueurPOV.gameObject.SetActive(false);
    }
    void Update()
    {
        if(!Active) return;
        if(EnPause) { avaitVerrou=false;return; }
        if(!Tactile.Actif && Cursor.lockState!=CursorLockMode.Locked)
        {
            if(avaitVerrou) { avaitVerrou=false;interfaceVisite.AfficherPausePaintball(); }
            return;
        }
        avaitVerrou=true;
        TempsEcoule+=Time.deltaTime;
        // Entraînement sans limite de temps : le record se met à jour au fil de la partie.
        if(Mode==ModePartie.Entrainement && Touches*100>MeilleurScore) { MeilleurScore=Touches*100;NouveauRecord=true;PlayerPrefs.SetInt("PaintballMeilleurScore",MeilleurScore);PlayerPrefs.Save(); }
        if(changerVue.WasPressedThisFrame() | (Tactile.Actif && Tactile.Vue())) BasculerVue();
        if(recharger.WasPressedThisFrame() | (Tactile.Actif && Tactile.Recharge())) LancerRecharge();
        if(rechargement>0)
        {
            rechargement-=Time.deltaTime;
            if(rechargement<=0) { rechargement=0;Chargeur=50;Actualise?.Invoke(); }
        }
        if(Feu && Time.time>=prochainTir && rechargement<=0)
        {
            if(Chargeur>0) Tirer(); else { sons.Vide();prochainTir=Time.time+.3f;LancerRecharge(); }
        }
        // Écart du réticule = dispersion réelle : déplacement, saut, cadence soutenue ; la visée le resserre.
        Vector3 v=controleur.velocity;v.y=0;
        chaleur=Mathf.MoveTowards(chaleur,0,Time.deltaTime*2.2f);
        float ecartCible=(7+v.magnitude*1.7f+(controleur.isGrounded?0:9)+chaleur*10)*(Visee?.6f:1)*(LunettePaintball.Visee?.3f:1);
        Ecart=Mathf.Lerp(Ecart,ecartCible,1-Mathf.Exp(-14*Time.deltaTime));
        RetourTouche=Mathf.Max(0,RetourTouche-Time.deltaTime);
        int seconde=Mathf.FloorToInt(TempsEcoule),distance=Mathf.RoundToInt(DistanceVisee);bool touche=RetourTouche>0;
        if(seconde!=secondeHud || distance!=distanceHud || touche!=toucheHud)
        { secondeHud=seconde;distanceHud=distance;toucheHud=touche;Actualise?.Invoke(); }
    }
    public void LancerRecharge()
    {
        if(EnPause || rechargement>0 || Chargeur==50) return;
        rechargement=DureeRecharge;sons.Recharge();Actualise?.Invoke();
    }
    public void BasculerVue() { TroisiemePersonne=!TroisiemePersonne;Actualise?.Invoke(); }
    public bool Tirer()
    {
        if(EnPause || Chargeur<=0 || rechargement>0 || Time.time<prochainTir) return false;
        prochainTir=Time.time+.125f;Chargeur--;Tirs++;chaleur=Mathf.Min(1,chaleur+.16f);
        sons.Tir();pose.Tir();
        Vector3 origine=(TroisiemePersonne?bouche:bouchePOV).position;
        Vector3 cible=cameraJeu.transform.position+cameraJeu.transform.forward*120;
        if(Physics.Raycast(cameraJeu.transform.position,cameraJeu.transform.forward,out var visee,120,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore)) cible=visee.point;
        // Never teleport the projectile through a wall between shoulder and muzzle.
        Vector3 epaule=transform.position+Vector3.up*1.35f;
        if(Physics.Linecast(epaule,origine,out var obstacle,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore))
        { origine=obstacle.point-obstacle.normal*.001f; Impact(obstacle,Couleur,JoueurId,Vector3.forward*BalistiquePaintball.VitesseInitiale); }
        else
        {
            Vector3 direction=(cible-origine).normalized;
            // Dispersion proportionnelle à l'écart affiché du réticule ; ni fausse gravité ni tir instantané.
            Vector2 dispersion=UnityEngine.Random.insideUnitCircle*.0013f*(Ecart/7f);
            direction=(direction+cameraJeu.transform.right*dispersion.x+cameraJeu.transform.up*dispersion.y).normalized;
            int tir=Mode==ModePartie.EnLigne?Reseau.Tir(origine,direction,BalistiquePaintball.VitesseInitiale):0;
            AjouterBille(origine,direction*BalistiquePaintball.VitesseInitiale,Couleur,JoueurId,tir);
        }
        Actualise?.Invoke();return true;
    }
    public void AjouterBille(Vector3 origine,Vector3 vitesse,Color couleur,int joueur,int tir=0)
    {
        for(int i=0;i<billes.Length;i++) if(!billes[i].active)
        {
            var b=billes[i];b.active=true;b.position=origine;b.vitesse=vitesse;b.couleur=couleur;b.joueur=joueur;b.tir=tir;b.age=0;
            b.visuel.position=origine;b.rendu.sharedMaterial=MateriauBille(couleur);
            b.trainee.Clear();b.trainee.startColor=new Color(couleur.r,couleur.g,couleur.b,.95f);b.trainee.endColor=new Color(couleur.r,couleur.g,couleur.b,0);
            b.visuel.gameObject.SetActive(true);b.trainee.emitting=true;
            billes[i]=b;ProjectilesActifs++;break;
        }
    }
    Material MateriauBille(Color couleur)
    {
        for(int c=0;c<Couleurs.Length;c++) if(Couleurs[c]==couleur) return materiauxBilles[c];
        if(!autresMateriaux.TryGetValue(couleur,out var m)) { m=new Material(materiauBille);m.SetColor("_BaseColor",couleur);autresMateriaux[couleur]=m; }
        return m;
    }
    void FixedUpdate()
    {
        if(Fige) return;
        accumulateur+=Time.fixedDeltaTime;
        const float dt=1f/240f;
        MesuresPerf.Billes.Start();
        while(accumulateur>=dt)
        {
            accumulateur-=dt;EtapesPhysiques++;
            for(int i=0;i<billes.Length;i++)
            {
                var b=billes[i];if(!b.active) continue;
                Vector3 avant=b.position;BalistiquePaintball.Avancer(ref b.position,ref b.vitesse,dt);b.age+=dt;
                Vector3 trajet=b.position-avant;
                Perruches.Bille(avant,b.position);
                bool touche=Physics.SphereCast(avant,BalistiquePaintball.Diametre*.5f,trajet.normalized,out var h,trajet.magnitude,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore);
                // Corps des joueurs : capsules testées hors moteur physique (couche Ignore Raycast).
                if(Mode!=ModePartie.Entrainement && Bots.Tester(avant,touche?avant+trajet.normalized*h.distance:b.position,b.joueur,out int joueurTouche,out _,out var point))
                {
                    touche=true;ImpactsTotal++;DernierProprietaire=b.joueur;DerniereCouleur=b.couleur;sons.Impact(point);
                    // En ligne, seul le tireur déclare sa touche ; le serveur la valide et la diffuse.
                    if(Mode==ModePartie.EnLigne) { if(b.joueur==JoueurId && b.tir>0) Reseau.Touche(b.tir,joueurTouche,point); }
                    else Bots.Touche(b.joueur,joueurTouche,point);
                }
                else if(touche) Impact(h,b.couleur,b.joueur,b.vitesse);
                if(touche || b.age>8 || b.position.y < -15) { b.active=false;b.trainee.emitting=false;b.visuel.gameObject.SetActive(false);ProjectilesActifs--; }
                b.visuel.position=b.position;billes[i]=b;
            }
        }
        MesuresPerf.Billes.Stop();
    }
    void Impact(RaycastHit h,Color couleur,int joueur,Vector3 vitesse)
    {
        ImpactsTotal++;DernierProprietaire=joueur;DerniereCouleur=couleur;
        impacts.Marquer(h,couleur);sons.Impact(h.point);
        h.collider.GetComponentInParent<CiblePaintball>()?.Toucher(h.point,couleur);
        h.collider.GetComponentInParent<ObjetMobilePaintball>()?.Impulsion(vitesse*BalistiquePaintball.Masse,h.point);
    }
    public void CibleTouchee(int numero) { Touches++;RetourTouche=.32f;sons.Cible();Actualise?.Invoke(); }
    // Touche validée par le match sur un adversaire.
    public void AdversaireTouche() { Touches++;RetourTouche=.32f;sons.Cible();Actualise?.Invoke(); }
    // Match terminé (victoire de quelqu'un) ou joueur éliminé : écran de fin.
    public void FinMatch()
    {
        if(terminee) return;
        terminee=true;explorateur.Suspendre(true);PartieFinie?.Invoke();
    }
    void LateUpdate()
    {
        if(!Active) return;
        bool visite=interfaceVisite.EcranActuel==InterfaceVisite.Ecran.Visite;
        personnage.SetActive(visite&&TroisiemePersonne);
        // Accroupi : le robot se tasse (pas d'animation d'accroupissement dans le modèle).
        if(echelleRobot==Vector3.zero) echelleRobot=personnage.transform.localScale;
        personnage.transform.localScale=Vector3.Scale(echelleRobot,new Vector3(1,1-.32f*explorateur.Accroupissement,1));
        marqueur.gameObject.SetActive(visite&&TroisiemePersonne);
        marqueurPOV.gameObject.SetActive(visite&&!TroisiemePersonne);
        if(!visite)
        {
            if(etaitVisite) cameraJeu.transform.localPosition=new Vector3(0,Yeux,0);
            etaitVisite=false;return;
        }
        etaitVisite=true;
        Vector3 epaule=transform.position+Vector3.up*Yeux;
        if(TroisiemePersonne)
        {
            // Caméra au-dessus de la grosse tête du robot (1,72 m) pour voir l'arme portée à droite.
            epaule=transform.position+Vector3.up*(1.7f-Explorateur.BaisseYeux*explorateur.Accroupissement);
            Vector3 offset=cameraJeu.transform.right*1f-cameraJeu.transform.forward*(Visee?1.5f:3.0f);
            if(Physics.SphereCast(epaule,.18f,offset.normalized,out var h,offset.magnitude,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore))
                offset=offset.normalized*Mathf.Max(0,h.distance-.08f);
            cameraJeu.transform.position=epaule+offset;
            // At very short distance hide the avatar instead of rendering inside its head.
            personnage.SetActive(offset.magnitude>.65f);
        }
        else cameraJeu.transform.localPosition=new Vector3(0,explorateur.HauteurYeux,0);
        cameraJeu.fieldOfView=Mathf.Lerp(cameraJeu.fieldOfView,Visee?Reglages.ChampVisee:Reglages.ChampVision,1-Mathf.Exp(-14*Time.deltaTime));
        bool vise=Physics.Raycast(cameraJeu.transform.position,cameraJeu.transform.forward,out var visee,150,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore);
        DistanceVisee=vise?visee.distance:150;
        PointVise=vise?visee.point:cameraJeu.transform.position+cameraJeu.transform.forward*150;
        float vitesse=Time.deltaTime>0 ? Vector3.Distance(transform.position,positionPrecedente)/Time.deltaTime : 0;
        if(animateur!=null)
        {
            animateur.SetFloat(VitesseAnimation,vitesse,.12f,Time.deltaTime);animateur.SetBool(SautAnimation,controleur.isGrounded);
            animateur.speed=EnPause?0:1;
        }
        pose.Poser(cameraJeu.transform,marqueur,marqueurPOV,TroisiemePersonne && personnage.activeSelf,Visee,explorateur.Court,ProgressionRecharge,PointVise);
        positionPrecedente=transform.position;
    }
    void PlacerEntrainement()
    {
        Vector3[] positions={new(-12,0,57),new(-20,0,54),new(-7,0,54),new(-25,0,63),new(-3,0,60),new(-20,0,69),new(-11,0,66),new(-28,0,56)};
        float Sol(Vector3 p) => Physics.Raycast(new Vector3(p.x,4,p.z),Vector3.down,out var hit,12,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore)?hit.point.y:-1.9f;
        foreach(var c in terrainEntrainement.GetComponentsInChildren<CiblePaintball>(true))
        {var p=positions[c.numero];p.y=Sol(p)+1.25f;c.transform.position=p;}
        foreach(var o in terrainEntrainement.GetComponentsInChildren<ObjetMobilePaintball>(true))
        {
            if(!int.TryParse(o.name.Replace("ObstacleMobile",""),out int i)) continue;
            Vector3 p=new(-22+(i%3)*2.2f,0,48+(i/3)*3.2f);p.y=Sol(p)+.305f;
            o.transform.localScale=new Vector3(.60f,i%3==0?.30f:.60f,.60f);
            o.transform.position=p;
            o.GetComponent<Rigidbody>().position=p;
        }
    }
    void OnControllerColliderHit(ControllerColliderHit h)
    {
        if(EnPause || h.moveDirection.y<-.4f) return;
        var objet=h.collider.GetComponentInParent<ObjetMobilePaintball>();
        if(objet==null) return;
        Vector3 v=controleur.velocity;v.y=0;
        // 80 kg player, finite contact-time transfer; never changes the object's transform.
        objet.Impulsion(v*80f*Mathf.Min(Time.deltaTime,.04f)*2.5f,h.point);
    }
    void ViderBilles()
    {
        for(int i=0;i<billes.Length;i++) { billes[i].active=false;if(billes[i].visuel!=null) { billes[i].trainee.emitting=false;billes[i].visuel.gameObject.SetActive(false); } }
        ProjectilesActifs=0;
    }
    void OnDestroy()
    {
        changerVue?.Dispose();recharger?.Dispose();viser?.Dispose();
        if(materiauxBilles!=null) foreach(var m in materiauxBilles) if(m!=null) Destroy(m);
        foreach(var b in billes) if(b.visuel!=null) Destroy(b.visuel.gameObject);
    }
    // Vérification navigateur : tourner le regard vers un bot (id, ou le plus proche si vide) en compensant
    // la chute de la bille, puis tirer une bille par le chemin normal. Sans effet hors partie contre les bots.
    public void ViserBot(string id)
    {
        if(Mode==ModePartie.Entrainement || Bots.Match==null || EnPause) return;
        BotPaintball cible=null;float distance=float.MaxValue;
        foreach(var b in Bots.bots)
        {
            if(!b.gameObject.activeSelf || id!="" && id!=b.Id.ToString()) continue;
            float d=Vector3.Distance(b.transform.position,transform.position);
            if(d<distance) { distance=d;cible=b; }
        }
        if(cible==null) return;
        Vector3 oeil=cameraJeu.transform.position,but=cible.transform.position+Vector3.up*1.0f;
        BotPaintball.Simuler(oeil,(but-oeil).normalized,Vector3.Distance(oeil,but),out float chute);
        Vector3 d2=but+Vector3.up*chute-oeil;Vector3 plat=new(d2.x,0,d2.z);
        transform.rotation=Quaternion.LookRotation(plat);
        explorateur.RetablirRegard(Quaternion.Euler(-Mathf.Atan2(d2.y,plat.magnitude)*Mathf.Rad2Deg,0,0));
        Tirer();
    }
    // Vérification en ligne : marcher (15 m/s, sous la limite du serveur) le long du NavMesh jusqu'à
    // distance de l'adversaire id, comme le ferait un joueur pressé.
    public void ApprocherBot(string reglage)
    {
        var r=reglage.Split(':');float garde=r.Length>1 && float.TryParse(r[1],System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out var g)?g:10;
        foreach(var b in Bots.bots) if(b.Id.ToString()==r[0]) { StartCoroutine(Approcher(b.transform,garde));return; }
    }
    System.Collections.IEnumerator Approcher(Transform cible,float garde)
    {
        var chemin=new UnityEngine.AI.NavMeshPath();
        UnityEngine.AI.NavMesh.SamplePosition(transform.position,out var depart,4,UnityEngine.AI.NavMesh.AllAreas);
        UnityEngine.AI.NavMesh.SamplePosition(cible.position,out var arrivee,4,UnityEngine.AI.NavMesh.AllAreas);
        if(!UnityEngine.AI.NavMesh.CalculatePath(depart.position,arrivee.position,UnityEngine.AI.NavMesh.AllAreas,chemin)) yield break;
        controleur.enabled=false;
        foreach(var coin in chemin.corners)
            while(Vector3.Distance(transform.position,coin)>.05f && Vector3.Distance(transform.position,cible.position)>garde)
            {
                transform.position=Vector3.MoveTowards(transform.position,coin+Vector3.up*.08f,15*Time.deltaTime);
                yield return null;
            }
        controleur.enabled=true;Physics.SyncTransforms();
    }
    // Vérification de la chute : place le premier bot à 4 m devant le joueur, face à lui, puis le touche
    // au torse par le chemin normal des touches (tache, chute, réapparition).
    public void EssaiChute(string _)
    {
        if(Bots==null || Bots.Match==null || Bots.bots.Count==0) return;
        var b=Bots.bots[0];Vector3 avant=transform.forward;avant.y=0;avant.Normalize();
        b.Reapparaitre(transform.position+avant*4,Quaternion.LookRotation(-avant));
        StartCoroutine(ToucherPlusTard(b,avant));
    }
    // Deux images d'attente : le squelette du bot doit être animé à sa nouvelle place avant la touche.
    System.Collections.IEnumerator ToucherPlusTard(BotPaintball b,Vector3 avant)
    {
        yield return null;yield return null;
        Bots.Touche(JoueurId,b.Id,b.transform.position+Vector3.up*PartieBots.Torse-avant*.3f);
    }
    // Vérification : se placer en x,y,z,lacet (degrés).
    public void AllerA(string valeurs)
    {
        var v=System.Array.ConvertAll(valeurs.Split(','),s=>float.Parse(s,System.Globalization.CultureInfo.InvariantCulture));
        controleur.enabled=false;transform.SetPositionAndRotation(new Vector3(v[0],v[1],v[2]),Quaternion.Euler(0,v.Length>3?v[3]:0,0));
        explorateur.ReinitialiserRegard();controleur.enabled=true;Physics.SyncTransforms();
    }
    // Browser QA can read real runtime evidence and invoke the same gameplay methods.
    public void LireEtat(string demande)
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        var rapport=new Rapport(this);
        // LireEtat('compteurs[:filtre]') : liste les marqueurs du profileur disponibles dans ce build.
        // LireEtat('apparitions[:n]') : points d'apparition répartis [x,y,z,lacet] pour le message demarrer du serveur.
        if(demande!=null && demande.StartsWith("apparitions"))
        {
            int n=demande.Length>12 && int.TryParse(demande.Substring(12),out var k)?k:64;
            var l=new System.Collections.Generic.List<float>();foreach(var a in PartieBots.PointsApparition(Mathf.Clamp(n,1,64))) l.AddRange(a);
            rapport.spawns=l.ToArray();
        }
        if(demande!=null && demande.StartsWith("compteurs")) rapport.counters=MesuresPerf.Disponibles(demande.Length>10?demande.Substring(10):"");
        EtatNavigateur(JsonUtility.ToJson(rapport));
#endif
    }
    [Serializable] class Rapport
    {
        public bool active,pause,thirdPerson,reload,finished; public int shots,hits,ammo,projectiles,impacts,decals,owner,animation;
        public float seconds,x,y,z,range,frameMs,frameP95Ms,renderScale; public long ticks;
        public string mode,counters; public float[] spawns; public int target=-1,winner=-1; public bool matchOver; public float matchSeconds;
        public int trees=Perruches.NombreArbres,flights=Perruches.Envols;
        public int marks=PartieBots.TachesEnregistrees,marksPlaced=PartieBots.TachesPosees,surfaces=PartieBots.SurfacesTrouvees;
        public bool night=MomentJournee.EstNuit;public float sunElevation=MomentJournee.Instance!=null?MomentJournee.Instance.Elevation:0;
        public string franceTime=MomentJournee.Instance!=null?MomentJournee.Instance.HeureFrance.ToString("yyyy-MM-dd HH:mm"):"";
        public int falls=CorpsTombe.Chutes;public int bodies=CorpsTombe.Nombre,lanterns=DecorNuit.Lanternes,garlands=DecorNuit.Guirlandes,bulbs=DecorNuit.Ampoules,windows=DecorNuit.NombreFenetres;
        public float scooterSpeed=Scooter.Instance!=null?Scooter.Instance.Vitesse:-1;public string scooterObstacle=Scooter.Instance!=null?Scooter.Instance.DernierObstacle:"";public bool riding=UnityEngine.Object.FindAnyObjectByType<Explorateur>()?.Monture!=null;
        public JoueurMatch[] players; public BotEtat[] bots; public string[] perfNames; public float[] perfValues;
        public Rapport(PaintballSolo p)
        { active=p.Active;pause=p.EnPause;thirdPerson=p.TroisiemePersonne;reload=p.Recharge;finished=p.Terminee;shots=p.Tirs;hits=p.Touches;ammo=p.Chargeur;projectiles=p.ProjectilesActifs;impacts=p.ImpactsTotal;decals=p.impacts.Nombre;owner=p.DernierProprietaire;animation=p.AnimationEtat;seconds=p.TempsRestant;x=p.transform.position.x;y=p.transform.position.y;z=p.transform.position.z;range=p.DistanceVisee;ticks=p.EtapesPhysiques;
            var r=p.GetComponent<ResolutionAdaptative>();if(r!=null) { r.Calculer();frameMs=r.MoyenneMs;frameP95Ms=r.P95Ms;renderScale=r.Echelle; }
            mode=p.Mode.ToString();
            var m=p.Bots!=null?p.Bots.Match:null;
            if(m!=null)
            {
                target=m.Cible;winner=m.Gagnant;matchOver=m.Termine;matchSeconds=m.Temps;players=m.joueurs.ToArray();
                bots=new BotEtat[p.Bots.bots.Count];
                for(int i=0;i<bots.Length;i++) { var b=p.Bots.bots[i];bots[i]=new BotEtat{id=b.Id,state=b.EtatTexte,x=b.transform.position.x,y=b.transform.position.y,z=b.transform.position.z,active=b.gameObject.activeSelf}; }
            }
            if(MesuresPerf.Instance!=null) MesuresPerf.Instance.Relever(out perfNames,out perfValues); }
    }
    [Serializable] class BotEtat { public int id; public string state; public float x,y,z; public bool active; }
#if UNITY_WEBGL && !UNITY_EDITOR
    [System.Runtime.InteropServices.DllImport("__Internal")] static extern void EtatNavigateur(string json);
#endif
}

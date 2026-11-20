using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using Unity.AI.Navigation;
using UnityEngine.AI;

public static class PaintballScene
{
    const string Dossier="Assets/Chateau/Paintball";
    static Material Mat(string nom,Color couleur,float metal=0)
    {
        string chemin=$"{Dossier}/{nom}.mat";var mat=AssetDatabase.LoadAssetAtPath<Material>(chemin);
        if(mat!=null) return mat;
        mat=new Material(Shader.Find("Universal Render Pipeline/Lit"));mat.SetColor("_BaseColor",couleur);mat.SetFloat("_Metallic",metal);mat.SetFloat("_Smoothness",.4f);
        AssetDatabase.CreateAsset(mat,chemin);return mat;
    }
    public static void Creer()
    {
        var joueur=Object.FindAnyObjectByType<Explorateur>().gameObject;joueur.layer=2;
        var partie=joueur.AddComponent<PaintballSolo>();
        partie.impacts=new GameObject("Peinture").AddComponent<ImpactsPaintball>();
        partie.impacts.texture=AssetDatabase.LoadAssetAtPath<Texture2D>(Dossier+"/Eclaboussure.png");
        partie.impacts.shader=Shader.Find("Chateau/Peinture");
        partie.materiauBille=Mat("Bille",Color.white,.1f);
        Habiller(partie);
        var source=AssetDatabase.LoadAssetAtPath<GameObject>(Dossier+"/RobotExpressive.glb");
        if(source==null) throw new System.Exception("Personnage GLB absent");
        var modele=(GameObject)PrefabUtility.InstantiatePrefab(source,joueur.transform);
        PrefabUtility.UnpackPrefabInstance(modele,PrefabUnpackMode.Completely,InteractionMode.AutomatedAction);
        modele.name="JoueurRobot";modele.transform.localPosition=Vector3.zero;
        var rendus=modele.GetComponentsInChildren<Renderer>();var b=rendus[0].bounds;foreach(var r in rendus) b.Encapsulate(r.bounds);
        modele.transform.localScale=Vector3.one*(1.72f/b.size.y);
        modele.transform.localPosition=Vector3.up*(-b.min.y+joueur.transform.position.y)*(1.72f/b.size.y);
        foreach(var t in modele.GetComponentsInChildren<Transform>()) t.gameObject.layer=2;
        foreach(var c in modele.GetComponentsInChildren<Collider>()) Object.DestroyImmediate(c);
        var anim=modele.GetComponentInChildren<Animator>();if(anim==null) anim=modele.AddComponent<Animator>();
        var controleur=CreerAnimations();anim.runtimeAnimatorController=controleur;anim.applyRootMotion=false;anim.cullingMode=AnimatorCullingMode.AlwaysAnimate;
        partie.personnage=modele;partie.animateur=anim;
        InstallerMarqueurs(partie);
        partie.terrainEntrainement=CreerTerrain(partie);
        Mobilier();Traversables();Navigation();Optimiser();AmbianceScene.Preparer();Time.fixedDeltaTime=1f/60f;Time.maximumDeltaTime=.1f;
        AssetDatabase.SaveAssets();
        Debug.Log($"PAINTBALL rig {modele.GetComponentsInChildren<SkinnedMeshRenderer>().Length} skins, {controleur.animationClips.Length} clips; mobilier {Object.FindObjectsByType<ObjetMobilePaintball>().Length}");
    }
    static AnimatorController CreerAnimations()
    {
        const string chemin=Dossier+"/Joueur.controller";
        if(File.Exists(chemin)) AssetDatabase.DeleteAsset(chemin);
        var c=AnimatorController.CreateAnimatorControllerAtPath(chemin);
        c.AddParameter("Vitesse",AnimatorControllerParameterType.Float);c.AddParameter("AuSol",AnimatorControllerParameterType.Bool);
        var clips=AssetDatabase.LoadAllAssetsAtPath(Dossier+"/RobotExpressive.glb").OfType<AnimationClip>().ToArray();
        var idle=clips.First(x=>x.name=="Idle");var walk=clips.First(x=>x.name=="Walking");var run=clips.First(x=>x.name=="Running");var jump=clips.First(x=>x.name=="Jump");
        var machine=c.layers[0].stateMachine;
        var etat=machine.AddState("Locomotion");machine.defaultState=etat;
        var blend=new BlendTree {name="Allure",blendType=BlendTreeType.Simple1D,blendParameter="Vitesse",useAutomaticThresholds=false};
        AssetDatabase.AddObjectToAsset(blend,c);blend.AddChild(idle,0);blend.AddChild(walk,3.4f);blend.AddChild(run,5.6f);etat.motion=blend;
        var saut=machine.AddState("Saut");saut.motion=jump;
        var sortir=etat.AddTransition(saut);sortir.hasExitTime=false;sortir.duration=.1f;sortir.AddCondition(AnimatorConditionMode.IfNot,0,"AuSol");
        var rentrer=saut.AddTransition(etat);rentrer.hasExitTime=false;rentrer.duration=.12f;rentrer.AddCondition(AnimatorConditionMode.If,0,"AuSol");
        return c;
    }
    static GameObject Forme(PrimitiveType type,Transform parent,string nom,Vector3 pos,Vector3 taille,Material mat)
    {
        var go=GameObject.CreatePrimitive(type);go.name=nom;go.transform.SetParent(parent,false);go.transform.localPosition=pos;go.transform.localScale=taille;go.GetComponent<Renderer>().sharedMaterial=mat;return go;
    }
    // Spyder MR100 (Sketchfab, CC BY) normalisé par scripts/paintball_marqueur.py :
    // origine sur la poignée, canon vers +Z. Un exemplaire porté (3e personne), un en vue subjective.
    static void InstallerMarqueurs(PaintballSolo partie)
    {
        var joueur=partie.transform;var tete=joueur.GetComponentInChildren<Camera>().transform;
        foreach(var t in joueur.GetComponentsInChildren<Transform>(true).Where(t=>t.name=="MarqueurPaintball").ToArray()) Object.DestroyImmediate(t.gameObject);
        partie.marqueur=Marqueur(joueur,true,out partie.bouche);partie.marqueur.localPosition=new Vector3(.2f,1.25f,.3f);
        partie.marqueurPOV=Marqueur(tete,false,out partie.bouchePOV);partie.marqueurPOV.localPosition=new Vector3(.19f,-.215f,.27f);
    }
    static Transform Marqueur(Transform parent,bool ombre,out Transform bouche)
    {
        var source=AssetDatabase.LoadAssetAtPath<GameObject>(Dossier+"/MarqueurSpyder.glb");
        if(source==null) throw new System.Exception("MarqueurSpyder.glb absent : lancer scripts/paintball_marqueur.py");
        var root=new GameObject("MarqueurPaintball").transform;root.SetParent(parent,false);
        var modele=(GameObject)PrefabUtility.InstantiatePrefab(source,root);
        PrefabUtility.UnpackPrefabInstance(modele,PrefabUnpackMode.Completely,InteractionMode.AutomatedAction);
        modele.transform.localPosition=Vector3.zero;modele.transform.localRotation=Quaternion.identity;modele.transform.localScale=Vector3.one;
        bouche=new GameObject("BoucheCanon").transform;bouche.SetParent(root,false);bouche.localPosition=AnimationMarqueur.Bouche;
        foreach(var t in root.GetComponentsInChildren<Transform>()) t.gameObject.layer=2;
        foreach(var c in root.GetComponentsInChildren<Collider>()) Object.DestroyImmediate(c);
        foreach(var r in root.GetComponentsInChildren<Renderer>())
        { r.shadowCastingMode=ombre?ShadowCastingMode.On:ShadowCastingMode.Off;r.receiveShadows=ombre;r.motionVectorGenerationMode=MotionVectorGenerationMode.ForceNoMotion; }
        return root;
    }
    static void Habiller(PaintballSolo partie)
    {
        string chemin=Dossier+"/Trainee.mat";var mat=AssetDatabase.LoadAssetAtPath<Material>(chemin);
        if(mat==null) { mat=new Material(Shader.Find("Chateau/Trainee"));AssetDatabase.CreateAsset(mat,chemin); }
        partie.materiauTrainee=mat;
        // Matériaux du décor de nuit (MomentJournee, DecorNuit), chargés par Resources.Load.
        const string nuit="Assets/Chateau/Resources/Nuit";Directory.CreateDirectory(nuit);
        foreach(var nom in new[]{"Lumineux","Halo","Fenetre"})
        {
            string cheminNuit=$"{nuit}/{nom}.mat";
            if(AssetDatabase.LoadAssetAtPath<Material>(cheminNuit)==null) AssetDatabase.CreateAsset(new Material(Shader.Find("Chateau/"+nom)),cheminNuit);
        }
        var ui=Object.FindAnyObjectByType<InterfaceVisite>();
        if(ui!=null) ui.eclaboussure=AssetDatabase.LoadAssetAtPath<Texture2D>(Dossier+"/Eclaboussure.png");
    }
    // Gains de FPS sans perte visible :
    // - occlusion culling précalculé (Umbra) : les pièces derrière les murs ne sont plus dessinées ;
    // - petits objets fixes masqués quand ils font moins de 1 % de la hauteur d'écran (LODGroup à un niveau) ;
    // - pas de HDR (aucun post-traitement ne l'utilise) : un tampon intermédiaire et une copie en moins.
    static void Optimiser()
    {
        var chateau=GameObject.Find("Chateau");
        int occulteurs=0,petits=0,sansOmbre=0;
        if(chateau!=null)
            foreach(var r in chateau.GetComponentsInChildren<MeshRenderer>(true))
            {
                if(r.GetComponentInParent<Porte>()!=null || r.GetComponentInParent<ObjetMobilePaintball>()!=null
                   || r.GetComponentInParent<DrapeauAnime>()!=null || r.GetComponentInParent<FontaineAnimee>()!=null) continue;
                string n=r.name.ToLowerInvariant();
                bool transparent=r.sharedMaterials.Any(m=>m!=null && (m.renderQueue>=2450 || m.name.ToLowerInvariant().Contains("vitrage") || m.name.ToLowerInvariant().Contains("verre")));
                bool feuillage=n.Contains("feuill") || n.Contains("herbe") || n.Contains("fleur") || n.Contains("arbre") || n.Contains("haie") || Vegetation.Plantes.IsMatch(r.name);
                var flags=StaticEditorFlags.OccludeeStatic;
                if(!transparent && !feuillage && r.bounds.size.magnitude>1.2f) { flags|=StaticEditorFlags.OccluderStatic;occulteurs++; }
                GameObjectUtility.SetStaticEditorFlags(r.gameObject,GameObjectUtility.GetStaticEditorFlags(r.gameObject)|flags);
                float taille=Mathf.Max(r.bounds.size.x,r.bounds.size.y,r.bounds.size.z);
                // Ombres portées : à l'intérieur, seule l'enveloppe (murs, planchers, plafonds) ombre le soleil ;
                // dehors, les objets de moins de 60 cm n'en portent plus. Allège la passe d'ombre, premier poste du rendu.
                Vector3 c=r.bounds.center;bool interieur=Mathf.Abs(c.x)<18 && c.z>-10 && c.z<12;
                if(r.shadowCastingMode==ShadowCastingMode.On && (taille<.6f || interieur && taille<3f)) { r.shadowCastingMode=ShadowCastingMode.Off;sansOmbre++; }
                if(taille<1.6f && r.GetComponent<LODGroup>()==null && r.GetComponentInParent<LODGroup>()==null)
                {
                    var lod=r.gameObject.AddComponent<LODGroup>();
                    lod.SetLODs(new[]{new LOD(.01f,new Renderer[]{r})});lod.RecalculateBounds();petits++;
                }
            }
        StaticOcclusionCulling.smallestOccluder=1.5f;StaticOcclusionCulling.smallestHole=.2f;StaticOcclusionCulling.backfaceThreshold=100;
        bool calcule=StaticOcclusionCulling.Compute();
        foreach(var cam in Object.FindObjectsByType<Camera>(FindObjectsInactive.Include)) { cam.useOcclusionCulling=true;cam.allowHDR=false;cam.allowMSAA=false; }
        foreach(var nom in new[]{"Assets/Settings/Mobile_RPAsset.asset","Assets/Settings/PC_RPAsset.asset"})
        {
            var urp=AssetDatabase.LoadAssetAtPath<UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset>(nom);
            if(urp==null) continue;urp.supportsHDR=false;EditorUtility.SetDirty(urp);
        }
        Debug.Log($"PAINTBALL OPTIMISATION occulteurs {occulteurs}, petits objets {petits}, sans ombre {sansOmbre}, occlusion {(calcule?"calculee":"ECHEC")}");
    }
    static GameObject CreerTerrain(PaintballSolo partie)
    {
        var root=new GameObject("EntrainementSolo");
        var blanc=Mat("CibleIvoire",new Color(.92f,.88f,.73f));var sombre=Mat("CibleAnneau",new Color(.07f,.15f,.13f));
        var bois=Mat("BoisObstacle",new Color(.38f,.23f,.12f));var metal=Mat("Seau",new Color(.22f,.30f,.33f),.5f);
        // Pelouse sud, hors du bassin mesuré (repère Unity : x = -x D-003, z = y D-003 ; bassin en x -27..0, z 58..95).
        Vector3[] positions={new(3,0,54),new(8,0,59),new(14,0,56),new(-2,0,46),new(19,0,63),new(-10,0,51),new(11,0,74),new(24,0,82)};
        for(int i=0;i<positions.Length;i++)
        {
            Vector3 p=positions[i];p.y=Sol(p)+1.25f;
            var cible=new GameObject("Cible"+(i+1));cible.transform.SetParent(root.transform);cible.transform.position=p;
            var plan=Forme(PrimitiveType.Cylinder,cible.transform,"Disque",Vector3.zero,new(.85f,.035f,.85f),blanc);plan.transform.localRotation=Quaternion.Euler(90,0,0);
            var anneau=Forme(PrimitiveType.Cylinder,cible.transform,"Centre",new(0,0,-.041f),new(.38f,.009f,.38f),sombre);anneau.transform.localRotation=Quaternion.Euler(90,0,0);
            Forme(PrimitiveType.Cube,cible.transform,"Pied",new(0,-.74f,.05f),new(.09f,1.10f,.09f),bois);
            var c=cible.AddComponent<CiblePaintball>();c.partie=partie;c.numero=i;
        }
        for(int i=0;i<9;i++)
        {
            Vector3 p=new Vector3(1+(i%3)*2.1f,0,48+(i/3)*3.2f);p.y=Sol(p)+.33f;
            var boite=Forme(i%3==0?PrimitiveType.Cylinder:PrimitiveType.Cube,root.transform,"ObstacleMobile"+i,p,new(.60f,.60f,.60f),i%3==0?metal:bois);
            boite.AddComponent<Rigidbody>();boite.AddComponent<ObjetMobilePaintball>().Initialiser(i%3==0?3:12,i==8?18:0);
        }
        return root;
    }
    static float Sol(Vector3 p) => Physics.Raycast(new Vector3(p.x,4,p.z),Vector3.down,out var hit,12,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore)?hit.point.y:-1.9f;
    static void Mobilier()
    {
        string dossier=Dossier+"/MaillagesPhysiques";Directory.CreateDirectory(dossier);
        var candidats=Object.FindObjectsByType<MeshRenderer>().Where(r=>
        {string n=r.name.ToLowerInvariant();return n.Contains("chaise") || n.Contains("table_basse") || n=="terrasse_lampe_table";}).ToArray();
        int i=0;
        foreach(var r in candidats)
        {
            var f=r.GetComponent<MeshFilter>();if(f==null || f.sharedMesh==null) continue;
            // Bake the château's mirrored transform into a mesh: dynamic bodies need positive unit scale.
            Vector3 centre=r.bounds.center;var mesh=Object.Instantiate(f.sharedMesh);var v=mesh.vertices;
            for(int j=0;j<v.Length;j++) v[j]=r.transform.TransformPoint(v[j])-centre;
            mesh.vertices=v;
            if(r.transform.localToWorldMatrix.determinant<0)
                for(int sm=0;sm<mesh.subMeshCount;sm++) {var tr=mesh.GetTriangles(sm);for(int k=0;k<tr.Length;k+=3) (tr[k+1],tr[k+2])=(tr[k+2],tr[k+1]);mesh.SetTriangles(tr,sm);}
            mesh.RecalculateNormals();mesh.RecalculateBounds();
            string path=$"{dossier}/Mobilier{i++}.asset";
            if(File.Exists(path)) AssetDatabase.DeleteAsset(path);AssetDatabase.CreateAsset(mesh,path);
            var go=new GameObject("Mobile_"+r.name);go.transform.position=centre;
            go.AddComponent<MeshFilter>().sharedMesh=mesh;go.AddComponent<MeshRenderer>().sharedMaterials=r.sharedMaterials;
            var col=go.AddComponent<MeshCollider>();col.sharedMesh=mesh;col.convex=true;
            go.AddComponent<Rigidbody>();go.AddComponent<ObjetMobilePaintball>().Initialiser(r.name.Contains("lampe")?2:r.name.Contains("table")?20:7);
            Object.DestroyImmediate(r.gameObject);
        }
    }
    public static void BuildWeb()
    {
        VerificationBalistique.Verifier();
        ChateauScene.Construire();
        TexturesWeb.Preparer();
        CompilerWeb();
    }
    // Mise à jour rapide : réapplique le mode paintball (marqueur, matériaux, optimisations)
    // sur la scène web déjà construite, sans réimporter le château.
    public static void BuildWebMiseAJour() => MiseAJour("../build/web",BuildOptions.None);
    // Development build pour les mesures (ProfilerRecorder : thread principal, physique, rendu).
    public static void BuildWebMesure() => MiseAJour("../build/web",BuildOptions.Development);
    static void MiseAJour(string sortie,BuildOptions options)
    {
        VerificationBalistique.Verifier();
        EditorSceneManager.OpenScene("Assets/Scenes/Chateau.unity");
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        var partie=Object.FindAnyObjectByType<PaintballSolo>();
        ChateauScene.PointsDiscrets();
        Habiller(partie);InstallerMarqueurs(partie);Traversables();Navigation();Optimiser();AmbianceScene.Preparer();
        CompilerWeb(sortie,WebGLCompressionFormat.Gzip,options);
    }
    public static void BuildWebExistant()
    {
        VerificationBalistique.Verifier();
        EditorSceneManager.OpenScene("Assets/Scenes/Chateau.unity");
        CompilerWeb();
    }
    // Copie publiable (GitHub Pages) du build web, hors de build/ : ../publication.
    // Brotli : le fichier de données doit rester sous la limite de 100 Mo par fichier de GitHub.
    public static void BuildWebPublication()
    {
        EditorSceneManager.OpenScene("Assets/Scenes/Chateau.unity");
        Traversables();
        CompilerWeb("../publication",WebGLCompressionFormat.Brotli);
    }
    // Parasols de la terrasse sans collision : sinon on reste coincé entre la table et la toile.
    static void Traversables()
    {
        int n=0;
        foreach(var c in Object.FindObjectsByType<Collider>(FindObjectsInactive.Include))
            if(c.name.StartsWith("terrasse_parasol")) { Object.DestroyImmediate(c);n++; }
        Debug.Log("PAINTBALL TRAVERSABLES "+n);
    }
    // NavMesh des bots sur tout le domaine : parc, terrasse et intérieur du château (étages par les
    // escaliers), d'après les colliders. Agent de 0,3 m de rayon pour passer les portes intérieures ;
    // vantaux ignorés (ils sont ouverts en partie contre les bots), joueurs et entraînement exclus.
    static void Navigation()
    {
        var ancien=GameObject.Find("NavigationPaintball");if(ancien!=null) Object.DestroyImmediate(ancien);
        var reglages=new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/NavMeshAreas.asset")[0]);
        var agent=reglages.FindProperty("m_Settings").GetArrayElementAtIndex(0);
        agent.FindPropertyRelative("agentRadius").floatValue=.3f;agent.FindPropertyRelative("agentHeight").floatValue=1.8f;
        agent.FindPropertyRelative("agentClimb").floatValue=.45f;agent.FindPropertyRelative("agentSlope").floatValue=45;
        reglages.ApplyModifiedPropertiesWithoutUndo();
        foreach(var porte in Object.FindObjectsByType<Porte>(FindObjectsInactive.Include))
        { var m=porte.GetComponent<NavMeshModifier>();if(m==null) m=porte.gameObject.AddComponent<NavMeshModifier>();m.ignoreFromBuild=true; }
        var terrain=Object.FindAnyObjectByType<PaintballSolo>().terrainEntrainement;bool actif=terrain!=null && terrain.activeSelf;
        if(terrain!=null) terrain.SetActive(false);
        var go=new GameObject("NavigationPaintball");
        var surface=go.AddComponent<NavMeshSurface>();
        surface.collectObjects=CollectObjects.Volume;surface.center=new Vector3(-40,0,55);surface.size=new Vector3(180,32,200);
        surface.useGeometry=NavMeshCollectGeometry.PhysicsColliders;surface.layerMask=~(1<<2);
        surface.BuildNavMesh();
        if(terrain!=null) terrain.SetActive(actif);
        const string chemin=Dossier+"/NavigationPaintball.asset";
        if(File.Exists(chemin)) AssetDatabase.DeleteAsset(chemin);
        AssetDatabase.CreateAsset(surface.navMeshData,chemin);
        var tri=NavMesh.CalculateTriangulation();
        var points=PartieBots.Reserve();
        int interieur=points.Count(PartieBots.DansChateau),etage=points.Count(p=>PartieBots.DansChateau(p) && p.y>3);
        Debug.Log($"PAINTBALL NAVMESH {tri.vertices.Length} sommets, {tri.indices.Length/3} triangles ; apparitions {points.Count} dont {interieur} dans le château ({etage} à l'étage)");
    }
    // index.html charge reseau.js avec l'empreinte de son contenu (?v=…) : un navigateur ne peut pas garder
    // une ancienne version en cache après une mise à jour.
    static void Versionner(string sortie)
    {
        string page=Path.Combine(sortie,"index.html"),script=Path.Combine(sortie,"reseau.js");
        if(!File.Exists(page) || !File.Exists(script)) return;
        using var sha=System.Security.Cryptography.SHA256.Create();
        string empreinte=System.BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(script))).Replace("-","").Substring(0,12).ToLowerInvariant();
        File.WriteAllText(page,File.ReadAllText(page).Replace("src=\"reseau.js\"",$"src=\"reseau.js?v={empreinte}\""));
        Debug.Log("PAINTBALL RESEAU "+empreinte);
    }
    public static UnityEditor.Build.Reporting.BuildReport CompilerWeb(string sortie="../build/web",WebGLCompressionFormat compression=WebGLCompressionFormat.Gzip,BuildOptions options=BuildOptions.None,bool quitter=true)
    {
        var icone=AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Chateau/Interface/Icone.png");
        if(icone!=null) PlayerSettings.SetIcons(UnityEditor.Build.NamedBuildTarget.Unknown,new[]{icone},IconKind.Any);
        QualitySettings.SetQualityLevel(0,true);QualitySettings.shadowDistance=35;QualitySettings.vSyncCount=0;
        PlayerSettings.WebGL.compressionFormat=compression;
        PlayerSettings.WebGL.decompressionFallback=true;
        PlayerSettings.WebGL.initialMemorySize=256;PlayerSettings.WebGL.maximumMemorySize=2048;
        PlayerSettings.WebGL.memoryGrowthMode=WebGLMemoryGrowthMode.Geometric;
        PlayerSettings.WebGL.template="PROJECT:Paintball";
        PlayerSettings.companyName="Saint-Victor";PlayerSettings.productName="Saint-Victor Paintball";
        PlayerSettings.runInBackground=true;
        EditorSceneManager.MarkSceneDirty(UnityEngine.SceneManagement.SceneManager.GetActiveScene());
        EditorSceneManager.SaveOpenScenes();
        var conteneurs=AssetDatabase.GetDependencies("Assets/Scenes/Chateau.unity",true).Where(p=>p.StartsWith("Assets/Chateau/Modeles/")&&p.EndsWith(".glb")).ToArray();
        Debug.Log("PAINTBALL CONTENEURS ORIGINAUX "+conteneurs.Length+" "+string.Join(",",conteneurs));
        if(conteneurs.Length>0) throw new System.Exception("La scene web depend encore de GLB du decor");
        var rapport=BuildPipeline.BuildPlayer(new BuildPlayerOptions {scenes=new[]{"Assets/Scenes/Chateau.unity"},locationPathName=sortie,target=BuildTarget.WebGL,options=options});
        Debug.Log($"PAINTBALL WEB {rapport.summary.result} {rapport.summary.totalSize/1e6:F1} Mo");
        if(rapport.summary.result==UnityEditor.Build.Reporting.BuildResult.Succeeded) Versionner(sortie);
        if(quitter && Application.isBatchMode) EditorApplication.Exit(rapport.summary.result==UnityEditor.Build.Reporting.BuildResult.Succeeded?0:1);
        return rapport;
    }
    // Étapes de MiseAJour qui modifient la scène (marqueur, matériaux, navigation, occlusion), sans compiler.
    public static void PreparerScene()
    {
        VerificationBalistique.Verifier();
        EditorSceneManager.OpenScene("Assets/Scenes/Chateau.unity");
        var partie=Object.FindAnyObjectByType<PaintballSolo>();
        ChateauScene.PointsDiscrets();
        Habiller(partie);InstallerMarqueurs(partie);Traversables();Navigation();Optimiser();AmbianceScene.Preparer();
    }
}

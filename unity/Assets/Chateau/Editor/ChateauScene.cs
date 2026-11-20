using System.IO;
using System.Linq;
using System.Collections.Generic;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

// Construit la scène d'exploration à partir des GLB copiés dans Assets/Chateau/Modeles,
// puis le build Linux. En batch :
//   -executeMethod ChateauScene.Construire   /   -executeMethod ChateauScene.BuildLinux
public static class ChateauScene
{
    const string Modeles = "Assets/Chateau/Modeles";
    const string Scene = "Assets/Scenes/Chateau.unity";
    const string Materiaux = "Assets/Chateau/Materiaux";
    static readonly string[] Ordre = { "parc", "terrasse", "bati", "toiture", "coque" };
    [System.Serializable] class Coque { public Piece[] pieces; }
    [System.Serializable] class Piece { public Ouverture[] portes; }
    [System.Serializable] class Ouverture { public bool ouvrable; public Vantail[] vantaux; }
    [System.Serializable] class Vantail { public string objet; }
    static HashSet<string> portesOuvrables;

    // Repère Blender (x, y, z) → Unity (-x, z, -y) après export glTF et import glTFast.
    static Vector3 DepuisBlender(float x, float y, float z) => new Vector3(-x, z, -y);

    [MenuItem("Château/Construire la scène")]
    public static void Construire()
    {
        // Le modèle source fait foi ; une reconstruction ne doit pas garder les anciens GLB.
        string composants = Path.GetFullPath("../export/composants");
        Directory.CreateDirectory(Modeles);
        foreach (string fichier in Directory.GetFiles(composants, "*.glb"))
        {
            string destination = Path.Combine(Modeles, Path.GetFileName(fichier));
            if (!File.Exists(destination) || File.GetLastWriteTimeUtc(fichier) > File.GetLastWriteTimeUtc(destination))
                File.Copy(fichier, destination, true);
        }
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        var coque = JsonUtility.FromJson<Coque>(File.ReadAllText("../travail/coque.json"));
        portesOuvrables = new HashSet<string>(coque.pieces.SelectMany(p => p.portes ?? new Ouverture[0])
            .Where(p => p.ouvrable).SelectMany(p => p.vantaux ?? new Vantail[0]).Select(v => v.objet));
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var racine = new GameObject("Chateau");
        // Miroir D-026 : le Y Blender devient -Z dans Unity, d'où l'échelle Z négative.
        racine.transform.localScale = new Vector3(1f, 1f, -1f);

        var autres = Directory.GetFiles(Modeles, "*.glb").Select(Path.GetFileNameWithoutExtension)
            .Where(n => !Ordre.Contains(n)).OrderBy(n => n);
        foreach (string nom in Ordre.Concat(autres))
        {
            var modele = AssetDatabase.LoadAssetAtPath<GameObject>($"{Modeles}/{nom}.glb");
            if (modele == null)
            {
                Debug.Log($"CHATEAU {nom} absent");
                continue;
            }
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(modele, racine.transform);
            PrefabUtility.UnpackPrefabInstance(instance, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            if (nom == "bati")
            {
                EntreeAnimable.Preparer(instance, Materiaux);
                BalconAnimable.Preparer(instance, Materiaux);
                PortesFenetres.Preparer(instance, Materiaux);
            }
            Preparer(instance);
            Debug.Log($"CHATEAU {nom} : {instance.GetComponentsInChildren<MeshRenderer>().Length} maillages");
        }

        CalerTableaux(racine);

        var soleil = new GameObject("Soleil").AddComponent<Light>();
        soleil.type = LightType.Directional;
        soleil.intensity = 1.6f;
        soleil.shadows = LightShadows.Soft;
        soleil.color = new Color(1f, 0.95f, 0.86f);
        soleil.transform.rotation = Quaternion.Euler(40f, -160f, 0f);
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.62f, 0.72f, 0.88f);
        RenderSettings.ambientEquatorColor = new Color(0.55f, 0.55f, 0.5f);
        RenderSettings.ambientGroundColor = new Color(0.3f, 0.28f, 0.22f);

        CreerExplorateur(racine.transform.TransformPoint(DepuisBlender(0f, -15.75f, -1.44f)));
        CreerPointsHistorique(racine.transform);
        PointsDiscrets();
        InterfaceScene.Creer();
        PaintballScene.Creer();

        Directory.CreateDirectory(Path.GetDirectoryName(Scene));
        EditorSceneManager.SaveScene(scene, Scene);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(Scene, true) };
        Debug.Log("CHATEAU scène écrite");
    }

    // Tableaux restés à l'ancienne place d'un mur déplacé par le relevé du 19/11 : plaqués contre le mur le plus
    // proche derrière eux (axe le plus mince), masqués s'il n'y a pas de mur à moins de 1,5 m.
    static void CalerTableaux(GameObject racine)
    {
        Physics.SyncTransforms();
        int cales = 0, masques = 0;
        foreach (var r in racine.GetComponentsInChildren<MeshRenderer>())
        {
            string n = r.name.ToLowerInvariant();
            if (!(n.Contains("tableau") || n.Contains("gravure") || n.EndsWith("_peinture")) || n.Contains("cadres_photo")) continue;
            var b = r.bounds;
            bool minceX = b.extents.x < b.extents.z;
            float demi = minceX ? b.extents.x : b.extents.z;
            if (demi > .15f) continue;
            var propre = r.GetComponent<Collider>(); bool actif = propre != null && propre.enabled; if (propre != null) propre.enabled = false;
            float meilleur = float.MaxValue; Vector3 sens = Vector3.zero;
            foreach (var d in minceX ? new[] { Vector3.right, Vector3.left } : new[] { Vector3.forward, Vector3.back })
                foreach (float h in new[] { -.25f, 0f, .25f })
                    if (Physics.Raycast(b.center + Vector3.up * h * b.extents.y, d, out var t, 1.5f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)
                        && t.distance < meilleur && Mathf.Abs(Vector3.Dot(t.normal, d)) > .8f) { meilleur = t.distance; sens = d; }
            if (propre != null) propre.enabled = actif;
            if (sens == Vector3.zero) { r.enabled = false; if (propre != null) propre.enabled = false; masques++; Debug.Log("CHATEAU tableau sans mur, masqué : " + r.name); continue; }
            float ecart = meilleur - demi - .005f;
            if (ecart < .03f) continue;
            r.transform.position += sens * ecart; cales++;
            Debug.Log($"CHATEAU tableau recalé de {ecart:0.00} m : {r.name}");
        }
        Physics.SyncTransforms();
        Debug.Log($"CHATEAU tableaux recalés {cales}, masqués {masques}");
    }

    static void Preparer(GameObject instance)
    {
        // Le glTF exprime ces sources en candela ; URP utilise ici un multiplicateur.
        foreach (var lumiere in instance.GetComponentsInChildren<Light>())
        {
            lumiere.intensity = Mathf.Clamp(lumiere.intensity / 5000f, 0.5f, 3.5f);
            lumiere.range = 9f;
            lumiere.shadows = LightShadows.None;
        }
        foreach (var inscription in instance.GetComponentsInChildren<Transform>()
            .Where(t => t.name == "bati_inscription_chateau_saint_victor"))
            inscription.localScale = Vector3.Scale(inscription.localScale, new Vector3(-1f, 1f, 1f));
        Material verre = MateriauVerre();
        Material tain = MateriauMiroir();
        foreach (var rendu in instance.GetComponentsInChildren<MeshRenderer>())
        {
            string nom = rendu.gameObject.name.ToLowerInvariant();
            var mats = rendu.sharedMaterials;
            for (int i = 0; i < mats.Length; i++)
            {
                if (mats[i] != null && mats[i].name.ToLowerInvariant().Contains("vitrage")
                    && !mats[i].name.ToLowerInvariant().Contains("vitrage_op")) mats[i] = verre;
                // Glaces : matériau du projet nommé « Miroir », repéré par Miroirs.cs (TexturesWeb renomme les autres).
                else if (mats[i] != null && mats[i].name.ToLowerInvariant().Contains("miroir")) mats[i] = tain;
            }
            rendu.sharedMaterials = mats;

            // Feuillages et herbes : pas de collision ; le reste collisionne au maillage.
            bool traversable = nom.Contains("feuill") || nom.Contains("herbe") || nom.Contains("fleur")
                || nom.Contains("drapeau") || nom.Contains("fontaine") || nom.Contains("parc_jet") || nom.Contains("parc_bassin_eau")
                || nom.StartsWith("terrasse_parasol") || nom.Contains("rideau") || nom.Contains("voilage");
            // Plantes du parc : on les traverse (Vegetation les fait plier) ; les arbres gardent un tronc.
            bool plante = Vegetation.Plantes.IsMatch(rendu.gameObject.name) && !nom.Contains("_pierre");
            if (plante)
            {
                if (Vegetation.Arbres.IsMatch(rendu.gameObject.name)) Tronc(rendu);
                continue;
            }
            if (!traversable && rendu.GetComponent<Collider>() == null)
                rendu.gameObject.AddComponent<MeshCollider>();
        }

        foreach (var t in instance.GetComponentsInChildren<Transform>(true)
            .Where(t => portesOuvrables.Contains(t.name) || t.name.StartsWith("porte_entree_")
                || t.name.StartsWith("porte_balcon_etage_") || t.name.StartsWith("porte_fenetre_")))
            if (t.GetComponent<Porte>() == null) t.gameObject.AddComponent<Porte>();

        foreach (var t in instance.GetComponentsInChildren<Transform>(true).Where(t => t.name.EndsWith("_drapeau")))
            if (t.GetComponent<DrapeauAnime>() == null) t.gameObject.AddComponent<DrapeauAnime>();
        foreach (var t in instance.GetComponentsInChildren<Transform>(true).Where(t => t.name == "parc_fontaine_jet"))
            if (t.GetComponent<FontaineAnimee>() == null) t.gameObject.AddComponent<FontaineAnimee>();

        // Lustres et appliques (objets lumiere_*) : lumière ponctuelle si l'export n'en a pas fourni.
        foreach (var t in instance.GetComponentsInChildren<Transform>(true).Where(t => t.name.StartsWith("lumiere_")))
        {
            if (t.GetComponentInChildren<Light>() != null) continue;
            var lumiere = t.gameObject.AddComponent<Light>();
            lumiere.type = LightType.Point;
            lumiere.range = 9f;
            lumiere.intensity = 2.5f;
            lumiere.color = new Color(1f, 0.85f, 0.65f);
            lumiere.shadows = LightShadows.None;
        }
    }

    // Collision de tronc : capsule verticale au pied de l'arbre (origine de l'objet), 2,5 m de haut.
    static void Tronc(MeshRenderer rendu)
    {
        var t = rendu.transform;
        var c = rendu.gameObject.AddComponent<CapsuleCollider>();
        float e = Mathf.Max(.01f, Mathf.Abs(t.lossyScale.y));
        c.direction = 1;
        c.center = t.InverseTransformPoint(t.position + Vector3.up * 1.25f);
        c.height = 2.5f / e;
        c.radius = Mathf.Clamp(Mathf.Min(rendu.bounds.extents.x, rendu.bounds.extents.z) * .08f, .15f, .35f) / Mathf.Max(.01f, Mathf.Abs(t.lossyScale.x));
    }

    static Material MateriauVerre()
    {
        string chemin = $"{Materiaux}/Vitrage.mat";
        var mat = AssetDatabase.LoadAssetAtPath<Material>(chemin);
        if (mat != null) return mat;
        Directory.CreateDirectory(Materiaux);
        mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetFloat("_Surface", 1f);
        mat.SetFloat("_Blend", 0f);
        mat.SetFloat("_Smoothness", 0.95f);
        mat.SetColor("_BaseColor", new Color(0.75f, 0.85f, 0.9f, 0.18f));
        mat.SetOverrideTag("RenderType", "Transparent");
        mat.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
        mat.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
        mat.SetInt("_ZWrite", 0);
        mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        mat.renderQueue = (int)RenderQueue.Transparent;
        AssetDatabase.CreateAsset(mat, chemin);
        return mat;
    }

    static Material MateriauMiroir()
    {
        string chemin = $"{Materiaux}/Miroir.mat";
        var mat = AssetDatabase.LoadAssetAtPath<Material>(chemin);
        if (mat != null) return mat;
        Directory.CreateDirectory(Materiaux);
        mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetColor("_BaseColor", new Color(0.82f, 0.84f, 0.85f));
        mat.SetFloat("_Metallic", 1f);
        mat.SetFloat("_Smoothness", 0.95f);
        AssetDatabase.CreateAsset(mat, chemin);
        return mat;
    }

    static Material MateriauRepere(string nom, Color couleur, float metal)
    {
        string chemin = $"{Materiaux}/{nom}.mat";
        var mat = AssetDatabase.LoadAssetAtPath<Material>(chemin);
        if (mat != null) return mat;
        Directory.CreateDirectory(Materiaux);
        mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetColor("_BaseColor", couleur);
        mat.SetFloat("_Metallic", metal);
        mat.SetFloat("_Smoothness", 0.64f);
        AssetDatabase.CreateAsset(mat, chemin);
        return mat;
    }

    static void CreerPointsHistorique(Transform racine)
    {
        var fond = MateriauRepere("PlaqueHistoire", new Color(0.08f, 0.16f, 0.13f), 0.28f);
        var laiton = MateriauRepere("LaitonHistoire", new Color(0.59f, 0.43f, 0.22f), 0.76f);
        var police = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>("Assets/Chateau/Interface/Polices/Manrope-Regular-SDF.asset");
        CreerPoint(racine, "Villa Ralli", "La bastide connue aujourd’hui comme le Château Saint-Victor fut construite dans la seconde moitié du XIXe siècle pour le négociant grec Ralli.", "Métropole Aix-Marseille-Provence, PLUi patrimonial, fiche EB-238", fond, laiton, police,
            new Vector3(2.65f, -6.9f, 1.75f), new Vector3(0f, -6.9f, 1.6f));
        CreerPoint(racine, "Une demeure de jardin", "Les façades nord et sud reprennent une composition proche. Au sud, l’avant-corps à trois faces forme une terrasse en surplomb du parc.", "Métropole Aix-Marseille-Provence, PLUi patrimonial, fiche EB-238", fond, laiton, police,
            new Vector3(-2.65f, 0.9f, 1.7f), new Vector3(0f, 0.9f, 1.6f));
        CreerPoint(racine, "Boiseries et gypserie", "Les plafonds à caissons, les cheminées, les boiseries et les décors en gypserie font partie des éléments intérieurs anciens conservés dans la bastide.", "Vieilles Maisons Françaises, visite du Château Saint-Victor, avril 2026", fond, laiton, police,
            new Vector3(-2.6f, -6.5f, 1.8f), new Vector3(0f, -6.5f, 1.8f));
        CreerPoint(racine, "Le château et son parc", "Le château et son parc sont répertoriés dans le volet patrimonial du PLUi pour leurs qualités historiques, architecturales et paysagères.", "Métropole Aix-Marseille-Provence, PLUi patrimonial, fiche EB-238", fond, laiton, police,
            new Vector3(8.65f, 12.15f, 1.5f), new Vector3(2.06f, 7.5f, 1.5f));
    }

    // Repères d'histoire réduits à un petit point blanc (sans ombre ni collision avec le joueur) :
    // le collider est un déclencheur que seul le regard de l'explorateur détecte.
    public static void PointsDiscrets()
    {
        string chemin = $"{Materiaux}/PointInteraction.mat";
        var blanc = AssetDatabase.LoadAssetAtPath<Material>(chemin);
        if (blanc == null)
        {
            Directory.CreateDirectory(Materiaux);
            blanc = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            blanc.SetColor("_BaseColor", Color.white);
            AssetDatabase.CreateAsset(blanc, chemin);
        }
        foreach (var point in Object.FindObjectsByType<PointHistorique>(FindObjectsInactive.Include))
        {
            for (int i = point.transform.childCount - 1; i >= 0; i--) Object.DestroyImmediate(point.transform.GetChild(i).gameObject);
            foreach (var c in point.GetComponents<Collider>()) Object.DestroyImmediate(c);
            var zone = point.gameObject.AddComponent<SphereCollider>(); zone.radius = .3f; zone.isTrigger = true;
            var rond = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            rond.name = "Point"; rond.transform.SetParent(point.transform, false);
            rond.transform.localScale = Vector3.one * .06f;
            Object.DestroyImmediate(rond.GetComponent<Collider>());
            var rendu = rond.GetComponent<MeshRenderer>(); rendu.sharedMaterial = blanc;
            rendu.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; rendu.receiveShadows = false;
        }
    }

    static void CreerPoint(Transform racine, string titre, string texte, string source, Material fond, Material laiton,
        TMP_FontAsset police, Vector3 positionBlender, Vector3 cibleBlender)
    {
        Vector3 position = racine.TransformPoint(DepuisBlender(positionBlender.x, positionBlender.y, positionBlender.z));
        Vector3 cible = racine.TransformPoint(DepuisBlender(cibleBlender.x, cibleBlender.y, cibleBlender.z));
        var racinePlaque = new GameObject("RepereHistorique_" + titre.Replace(' ', '_'));
        racinePlaque.transform.SetPositionAndRotation(position, Quaternion.LookRotation(cible - position, Vector3.up));
        racinePlaque.transform.SetParent(racine, true);
        var collider = racinePlaque.AddComponent<BoxCollider>();
        collider.size = new Vector3(1.05f, 0.36f, 0.12f);
        racinePlaque.AddComponent<PointHistorique>().Initialiser(titre, texte, source);

        var cadre = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cadre.name = "Laiton"; cadre.transform.SetParent(racinePlaque.transform, false);
        cadre.transform.localScale = new Vector3(1.05f, 0.36f, 0.07f);
        cadre.GetComponent<Renderer>().sharedMaterial = laiton;
        Object.DestroyImmediate(cadre.GetComponent<Collider>());
        var face = GameObject.CreatePrimitive(PrimitiveType.Cube);
        face.name = "Plaque"; face.transform.SetParent(racinePlaque.transform, false);
        face.transform.localPosition = new Vector3(0f, 0f, -0.015f);
        face.transform.localScale = new Vector3(1.00f, 0.31f, 0.075f);
        face.GetComponent<Renderer>().sharedMaterial = fond;
        Object.DestroyImmediate(face.GetComponent<Collider>());

        var label = new GameObject("Legende", typeof(TextMeshPro));
        label.transform.SetParent(racinePlaque.transform, false);
        label.transform.localPosition = new Vector3(0f, 0f, 0.03f);
        label.transform.localScale = Vector3.one * 0.02f;
        var tmp = label.GetComponent<TextMeshPro>();
        tmp.font = police; tmp.text = "HISTOIRE  ·  E"; tmp.fontSize = 8f;
        tmp.alignment = TextAlignmentOptions.Center; tmp.color = new Color(0.92f, 0.84f, 0.66f);
        tmp.textWrappingMode = TextWrappingModes.NoWrap; tmp.raycastTarget = false;
    }

    static void CreerExplorateur(Vector3 position)
    {
        var joueur = new GameObject("Explorateur");
        joueur.transform.position = position + Vector3.up * 0.1f;
        var cc = joueur.AddComponent<CharacterController>();
        cc.height = 1.75f;
        cc.radius = 0.3f;
        cc.center = new Vector3(0f, 0.875f, 0f);
        cc.stepOffset = 0.3f;
        cc.slopeLimit = 50f;

        var tete = new GameObject("Tete");
        tete.transform.SetParent(joueur.transform, false);
        tete.transform.localPosition = new Vector3(0f, 1.62f, 0f);
        var cam = tete.AddComponent<Camera>();
        cam.nearClipPlane = 0.05f;
        cam.farClipPlane = 1500f;
        cam.fieldOfView = 70f;
        tete.AddComponent<AudioListener>();
        tete.tag = "MainCamera";

        joueur.AddComponent<Explorateur>();
    }

    public static void BuildLinux()
    {
        Construire();
        var options = new BuildPlayerOptions
        {
            scenes = new[] { Scene },
            locationPathName = "../build/linux/ChateauSaintVictor.x86_64",
            target = BuildTarget.StandaloneLinux64,
            options = BuildOptions.None,
        };
        var rapport = BuildPipeline.BuildPlayer(options);
        Debug.Log($"CHATEAU build {rapport.summary.result} {rapport.summary.totalSize / 1e6:F0} Mo");
        if (Application.isBatchMode) EditorApplication.Exit(rapport.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded ? 0 : 1);
    }
}

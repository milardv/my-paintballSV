using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

// Options du joueur (jeu, graphisme, sons), gardées dans les PlayerPrefs (stockage du navigateur en WebGL)
// et appliquées au démarrage puis à chaque changement. Les valeurs par défaut reprennent le réglage d'origine.
public static class Reglages
{
    public static readonly string[] NomsOmbres = { "Aucune", "Proches", "Étendues" };
    public static readonly string[] NomsResolution = { "Auto", "50 %", "75 %", "100 %" };
    static readonly float[] Echelles = { 0, .5f, .75f, 1 };
    public static readonly string[] NomsAnticrenelage = { "Aucun", "FXAA", "SMAA" };
    public static readonly string[] NomsNeige = { "Non", "Oui" };
    public static readonly string[] NomsImages = { "Écran", "60", "30" };
    static readonly int[] Images = { -1, 60, 30 };

    static float sensibilite = PlayerPrefs.GetFloat("OptionSensibilite", 1);
    static bool inverserY = PlayerPrefs.GetInt("OptionInverserY", 0) == 1;
    static int champVision = PlayerPrefs.GetInt("OptionChampVision", 75), ombres = PlayerPrefs.GetInt("OptionOmbres", 1),
        resolution = PlayerPrefs.GetInt("OptionResolution", 0), anticrenelage = PlayerPrefs.GetInt("OptionAnticrenelage", 0),
        images = PlayerPrefs.GetInt("OptionImages", 0), moment = PlayerPrefs.GetInt("OptionMoment", 0), neige = PlayerPrefs.GetInt("OptionNeige", 0);
    static float volume = PlayerPrefs.GetFloat("OptionVolume", 1), volumeEffets = PlayerPrefs.GetFloat("OptionVolumeEffets", 1),
        volumeAmbiance = PlayerPrefs.GetFloat("OptionVolumeAmbiance", 1);

    public static float Sensibilite { get => sensibilite; set => Ecrire("OptionSensibilite", sensibilite = Mathf.Clamp(value, .25f, 3)); }
    public static bool InverserY { get => inverserY; set { inverserY = value; Ecrire("OptionInverserY", value ? 1 : 0); } }
    public static int ChampVision { get => champVision; set => Ecrire("OptionChampVision", champVision = Mathf.Clamp(value, 60, 100)); }
    public static int Ombres { get => ombres; set => Ecrire("OptionOmbres", ombres = Mathf.Clamp(value, 0, 2)); }
    public static int Resolution { get => resolution; set => Ecrire("OptionResolution", resolution = Mathf.Clamp(value, 0, 3)); }
    public static int Anticrenelage { get => anticrenelage; set => Ecrire("OptionAnticrenelage", anticrenelage = Mathf.Clamp(value, 0, 2)); }
    public static int ImagesParSeconde { get => images; set => Ecrire("OptionImages", images = Mathf.Clamp(value, 0, 2)); }
    // 0 : heure réelle de la France ; 1 : jour ; 2 : nuit (MomentJournee).
    public static int Moment { get => moment; set => Ecrire("OptionMoment", moment = Mathf.Clamp(value, 0, 2)); }
    // Neige : flocons, sol qui blanchit peu à peu, sons d'hiver, empreintes à la couleur du joueur (Neige).
    public static bool Neige { get => neige == 1; set => Ecrire("OptionNeige", neige = value ? 1 : 0); }
    public static float VolumeGeneral { get => volume; set => Ecrire("OptionVolume", volume = Mathf.Clamp01(value)); }
    public static float VolumeEffets { get => volumeEffets; set => Ecrire("OptionVolumeEffets", volumeEffets = Mathf.Clamp01(value)); }
    public static float VolumeAmbiance { get => volumeAmbiance; set => Ecrire("OptionVolumeAmbiance", volumeAmbiance = Mathf.Clamp01(value)); }

    // Échelle de rendu imposée, ou 0 pour la résolution adaptative.
    public static float EchelleFixe => Echelles[Resolution];
    public static float ChampVisee => ChampVision * .7f;

    static float distanceOmbresOrigine = -1;

    static void Ecrire(string cle, float v) { PlayerPrefs.SetFloat(cle, v); Appliquer(); }
    static void Ecrire(string cle, int v) { PlayerPrefs.SetInt(cle, v); Appliquer(); }

    public static void Enregistrer() => PlayerPrefs.Save();

    public static void Retablir()
    {
        foreach (var cle in new[] { "OptionSensibilite", "OptionInverserY", "OptionChampVision", "OptionOmbres", "OptionResolution",
            "OptionAnticrenelage", "OptionImages", "OptionMoment", "OptionNeige", "OptionVolume", "OptionVolumeEffets", "OptionVolumeAmbiance" })
            PlayerPrefs.DeleteKey(cle);
        PlayerPrefs.Save();
        sensibilite = 1; inverserY = false; champVision = 75; ombres = 1; resolution = 0; anticrenelage = 0; images = 0; moment = 0; neige = 0;
        volume = volumeEffets = volumeAmbiance = 1;
        Appliquer();
    }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    public static void Appliquer()
    {
        AudioListener.volume = VolumeGeneral;
        Application.targetFrameRate = Images[ImagesParSeconde];

        var urp = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
        if (urp != null)
        {
            if (distanceOmbresOrigine < 0) distanceOmbresOrigine = urp.shadowDistance;
            urp.shadowDistance = Ombres == 2 ? Mathf.Min(120, distanceOmbresOrigine * 2) : distanceOmbresOrigine;
            if (EchelleFixe > 0) urp.renderScale = EchelleFixe;
        }
        foreach (var lumiere in Object.FindObjectsByType<Light>(FindObjectsInactive.Include))
            if (lumiere.type == LightType.Directional) lumiere.shadows = Ombres == 0 || MomentJournee.EstNuit ? LightShadows.None : LightShadows.Soft;
        var mode = Anticrenelage == 2 ? AntialiasingMode.SubpixelMorphologicalAntiAliasing
            : Anticrenelage == 1 ? AntialiasingMode.FastApproximateAntialiasing : AntialiasingMode.None;
        foreach (var camera in Object.FindObjectsByType<Camera>(FindObjectsInactive.Include))
            camera.GetUniversalAdditionalCameraData().antialiasing = mode;
        MomentJournee.Actualiser();
    }

    // Regard à la souris ou au doigt, en degrés : sensibilité et axe vertical inversé.
    public static Vector2 Regard(Vector2 degres) => new(degres.x * Sensibilite, degres.y * Sensibilite * (InverserY ? -1 : 1));
}

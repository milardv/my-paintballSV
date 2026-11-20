using UnityEngine;
using UnityEngine.Rendering.Universal;

// Résolution adaptative : baisse l'échelle de rendu URP par paliers de 5 % quand l'image dépasse
// ~20 ms pendant une seconde, et la remonte après trois secondes confortables. Plafond à 100 %,
// plancher à 70 %. Mesure aussi les temps d'image (moyenne, p95) pour la vérification navigateur.
public class ResolutionAdaptative : MonoBehaviour
{
    public const float Minimum = .7f, Maximum = 1f;
    readonly float[] temps = new float[240];
    int index, compte;
    float lent, confortable;
    bool flou;
    UniversalRenderPipelineAsset urp;
    public float Echelle => urp != null ? urp.renderScale : 1;
    public float MoyenneMs { get; private set; }
    public float P95Ms { get; private set; }
    readonly float[] tri = new float[240];

    void Start()
    {
        urp = UniversalRenderPipeline.asset;
        if (urp != null) urp.renderScale = Maximum;
        // ?optim=0 : référence de mesure sans occlusion, sans culling par taille ni résolution adaptative.
        if (Application.absoluteURL.Contains("optim=0"))
        {
            urp = null; QualitySettings.lodBias = 1000;
            foreach (var cam in FindObjectsByType<Camera>(FindObjectsInactive.Include)) cam.useOcclusionCulling = false;
        }
    }

    void Update()
    {
        float dt = Time.unscaledDeltaTime;
        if (dt <= 0 || dt > .5f) return;
        temps[index] = dt * 1000; index = (index + 1) % temps.Length; compte = Mathf.Min(compte + 1, temps.Length);
        if (urp == null || Time.timeScale == 0) return;
        // Pastis du gardien : image très sous-échantillonnée (floue), puis retour à la pleine résolution.
        if (ObjetsDomaine.Flou > 0) { urp.renderScale = Mathf.Lerp(Maximum, .22f, ObjetsDomaine.Flou); flou = true; return; }
        if (flou) { flou = false; urp.renderScale = Maximum; }
        // Résolution choisie dans les options : pas d'adaptation.
        if (Reglages.EchelleFixe > 0) { urp.renderScale = Reglages.EchelleFixe; return; }
        if (dt > .0205f) { lent += dt; confortable = 0; }
        else if (dt < .0175f) { confortable += dt; lent = Mathf.Max(0, lent - dt); }
        if (lent > 1 && urp.renderScale > Minimum) { urp.renderScale = Mathf.Max(Minimum, urp.renderScale - .05f); lent = 0; }
        else if (confortable > 3 && urp.renderScale < Maximum) { urp.renderScale = Mathf.Min(Maximum, urp.renderScale + .05f); confortable = 0; }
    }

    public void Calculer()
    {
        if (compte == 0) return;
        float somme = 0;
        for (int i = 0; i < compte; i++) { somme += temps[i]; tri[i] = temps[i]; }
        System.Array.Sort(tri, 0, compte);
        MoyenneMs = somme / compte; P95Ms = tri[Mathf.Min(compte - 1, (int)(compte * .95f))];
    }

    void OnDestroy() { if (urp != null) urp.renderScale = Maximum; }
}

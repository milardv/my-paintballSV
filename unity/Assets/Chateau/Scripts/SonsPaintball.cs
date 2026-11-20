using UnityEngine;

// Sons ElevenLabs (Resources/Sons) : une musique d'ambiance calme en boucle et des effets
// ponctuels (tir, impacts, cible, recharge).
public class SonsPaintball : MonoBehaviour
{
    public static SonsPaintball Instance { get; private set; }
    AudioSource musique, effets, tirs, sourceExplosion, hiver;
    AudioClip pasNeige;
    float facteurMusique = 1;
    readonly AudioSource[] impacts = new AudioSource[6];
    int prochainImpact;
    AudioClip tir, impact, cible, recharge, vide, menu, explosion;

    public static SonsPaintball Installer(GameObject hote)
    {
        if (Instance != null) return Instance;
        return hote.AddComponent<SonsPaintball>();
    }

    void Awake()
    {
        Instance = this;
        musique = Boucle("musique_ambiance", .5f * Reglages.VolumeAmbiance);
        hiver = Boucle("ambiance_neige", 0); pasNeige = Resources.Load<AudioClip>("Sons/pas_neige");
        effets = gameObject.AddComponent<AudioSource>(); effets.playOnAwake = false; effets.spatialBlend = 0;
        tirs = gameObject.AddComponent<AudioSource>(); tirs.playOnAwake = false; tirs.spatialBlend = 0;
        for (int i = 0; i < impacts.Length; i++)
        {
            var go = new GameObject("SonImpact" + i); go.transform.SetParent(transform, false);
            var s = go.AddComponent<AudioSource>(); s.playOnAwake = false; s.spatialBlend = 1; s.rolloffMode = AudioRolloffMode.Logarithmic;
            s.minDistance = 2.5f; s.maxDistance = 60; s.dopplerLevel = 0; impacts[i] = s;
        }
        tir = Resources.Load<AudioClip>("Sons/tir_marqueur"); impact = Resources.Load<AudioClip>("Sons/impact_peinture");
        cible = Resources.Load<AudioClip>("Sons/cible_touchee"); recharge = Resources.Load<AudioClip>("Sons/recharge");
        vide = Resources.Load<AudioClip>("Sons/chargeur_vide"); menu = Resources.Load<AudioClip>("Sons/menu_validation");
        explosion = Resources.Load<AudioClip>("Sons/explosion_peinture");
    }

    AudioSource Boucle(string nom, float volume)
    {
        var s = gameObject.AddComponent<AudioSource>();
        s.clip = Resources.Load<AudioClip>("Sons/" + nom); s.loop = true; s.spatialBlend = 0; s.volume = volume; s.playOnAwake = false;
        s.ignoreListenerPause = true; if (s.clip != null) s.Play();
        return s;
    }

    void Update()
    {
        musique.volume = .5f * Reglages.VolumeAmbiance * facteurMusique;
        float volumeEffets = Reglages.VolumeEffets;
        if (!Mathf.Approximately(effets.volume, volumeEffets))
        {
            effets.volume = tirs.volume = volumeEffets;
            foreach (var s in impacts) s.volume = volumeEffets;
        }
    }

    public void Tir() { tirs.pitch = Random.Range(.94f, 1.06f); tirs.PlayOneShot(tir, .5f); }
    // Tir d'un adversaire : spatialisé, sur les sources des impacts.
    public void TirDistant(Vector3 position)
    {
        var s = impacts[prochainImpact]; prochainImpact = (prochainImpact + 1) % impacts.Length;
        s.transform.position = position; s.pitch = Random.Range(.94f, 1.06f); s.PlayOneShot(tir, .7f);
    }
    public void Cible() => effets.PlayOneShot(cible, .55f);
    public void Recharge() => effets.PlayOneShot(recharge, .6f);
    public void Vide() => effets.PlayOneShot(vide, .5f);
    public void Impact(Vector3 position)
    {
        var s = impacts[prochainImpact]; prochainImpact = (prochainImpact + 1) % impacts.Length;
        s.transform.position = position; s.pitch = Random.Range(.9f, 1.1f); s.PlayOneShot(impact, .8f);
    }
    // Boule dorée : grosse explosion de peinture, spatialisée mais audible de loin.
    public void Explosion(Vector3 position)
    {
        if (explosion == null) return;
        if (sourceExplosion == null)
        {
            var go = new GameObject("SonExplosion"); go.transform.SetParent(transform, false);
            sourceExplosion = go.AddComponent<AudioSource>(); sourceExplosion.playOnAwake = false; sourceExplosion.spatialBlend = .75f;
            sourceExplosion.rolloffMode = AudioRolloffMode.Logarithmic; sourceExplosion.minDistance = 12; sourceExplosion.maxDistance = 120; sourceExplosion.dopplerLevel = 0;
        }
        sourceExplosion.volume = Reglages.VolumeEffets;
        sourceExplosion.transform.position = position; sourceExplosion.pitch = Random.Range(.95f, 1.05f); sourceExplosion.PlayOneShot(explosion, 1f);
    }
    // Neige : vent d'hiver qui monte avec le ciel couvert, musique atténuée.
    public void Hiver(float couverture, float gris)
    {
        if (hiver != null) hiver.volume = .75f * Reglages.VolumeAmbiance * Mathf.Max(gris * .6f, couverture);
        facteurMusique = Mathf.Lerp(1, .35f, gris);
    }
    public void PasNeige()
    {
        if (pasNeige == null) return;
        effets.PlayOneShot(pasNeige, Random.Range(.35f, .5f));
    }
    public static void Menu()
    {
        if (Instance == null || Instance.menu == null) return;
        Instance.effets.PlayOneShot(Instance.menu, .35f);
    }
    void OnDestroy() { if (Instance == this) Instance = null; }
}

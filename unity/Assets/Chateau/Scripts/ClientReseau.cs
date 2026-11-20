using System;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;

// Lien entre le jeu et le serveur en ligne (serveur/PROTOCOLE.md). Le salon (connexion Google, parties,
// invitations, lobby) et la WebSocket vivent dans la page (WebGLTemplates/Paintball/reseau.js) ; ce composant,
// nommé « Reseau » pour SendMessage, reçoit les messages de la partie déjà normalisés (null remplacés
// par -1 ou un tableau vide) et envoie positions, tirs et touches.
public class ClientReseau : MonoBehaviour
{
    public static ClientReseau Instance { get; private set; }
    const float PeriodePosition = 1f / 20;

    PaintballSolo partie;
    int moi = -1, sequence, prochainTir = 1;
    float prochainePosition;
    JoueurServeur[] joueursSalon = new JoueurServeur[0];
    readonly StringBuilder texte = new();

    // Décalage estimé entre l'horloge du serveur et l'horloge locale (ms).
    double decalage = double.NaN;
    public static double MaintenantLocal => Time.realtimeSinceStartupAsDouble * 1000;
    public double HeureServeur => MaintenantLocal + (double.IsNaN(decalage) ? 0 : decalage);
    public float LatenceMs { get; private set; } = -1;

#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void ReseauPret(string apparitions);
    [DllImport("__Internal")] static extern void ReseauOuvrirSalon(int couleur);
    [DllImport("__Internal")] static extern void ReseauEnvoyer(string message);
    [DllImport("__Internal")] static extern void ReseauQuitter();
#else
    static void ReseauPret(string apparitions) { }
    static void ReseauOuvrirSalon(int couleur) { Debug.Log("Salon en ligne : seulement dans le navigateur"); }
    static void ReseauEnvoyer(string message) { }
    static void ReseauQuitter() { }
#endif

    public static ClientReseau Installer(PaintballSolo partie)
    {
        if (Instance != null) return Instance;
        var go = new GameObject("Reseau");
        var c = go.AddComponent<ClientReseau>(); c.partie = partie;
        return c;
    }

    void Awake() { Instance = this; }

    void Start()
    {
        // Points d'apparition de la scène pour le message demarrer de l'hôte (64 au plus, château compris).
        texte.Clear(); texte.Append('[');
        var points = PartieBots.PointsApparition(64);
        for (int i = 0; i < points.Count; i++)
        {
            if (i > 0) texte.Append(',');
            texte.Append('['); Nombres(points[i]); texte.Append(']');
        }
        texte.Append(']');
        ReseauPret(texte.ToString());
    }

    // Salon ouvert : le jeu laisse le clavier aux champs de la page ("0"), puis le reprend ("1").
    public void Clavier(string actif)
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        WebGLInput.captureAllKeyboardInput = actif != "0";
#endif
    }

    public void OuvrirSalon() => ReseauOuvrirSalon(partie.CouleurIndex);
    public void Quitter() { moi = -1; ReseauQuitter(); }

    // ---------- Réception (appelée par la page) ----------
    public void Recevoir(string json)
    {
        MessageServeur m;
        try { m = JsonUtility.FromJson<MessageServeur>(json); } catch (Exception e) { Debug.LogWarning("Message illisible : " + e.Message); return; }
        if (m == null || string.IsNullOrEmpty(m.t)) return;
        if (m.h > 0) Recaler(m.h);
        var bots = partie.Bots;
        switch (m.t)
        {
            case "bienvenue": moi = m.j; break;
            case "etat":
                if (m.joueurs != null) joueursSalon = m.joueurs;
                if (partie.Mode == PaintballSolo.ModePartie.EnLigne && partie.Active) bots.EtatServeur(m.joueurs);
                break;
            case "debut":
                if (moi < 0) return;
                partie.DemarrerEnLigne(moi, joueursSalon, m.joueurs, m.cible, m.vies);
                sequence = 0; prochainTir = 1;
                break;
            case "ps":
                if (m.l == null || !EnPartie) return;
                foreach (var p in m.l) if (p.j != moi && p.p != null && p.p.Length == 3) bots.PoseDistante(p.j, p.h, V(p.p), p.r, p.v);
                break;
            case "corr":
                if (EnPartie && m.p != null && m.p.Length == 3) partie.Replacer(V(m.p));
                break;
            case "tir":
                if (EnPartie && m.o != null && m.d != null && m.j != moi) partie.TirDistant(m.j, V(m.o), V(m.d) * (m.v > 0 ? m.v : BalistiquePaintball.VitesseInitiale));
                break;
            case "touche":
                if (EnPartie) bots.ToucheServeur(m.tireur, m.cible, m.vies, m.points, m.elimine, m.spawn, m.pt, m.o);
                break;
            case "entree":
                // Un joueur entre dans la manche en cours : nouvel adversaire, nouvelle cible.
                if (EnPartie && m.j != moi)
                {
                    var info = Array.Find(joueursSalon, x => x.j == m.j);
                    bots.EntreeServeur(m.j, info != null ? info.nom : "Joueur " + (m.j + 1), info != null ? info.c : m.j % PaintballSolo.Couleurs.Length, m.spawn, m.cible);
                }
                break;
            case "fermeture":
                if (EnPartie) bots.Match?.ImposerFin(-1, "connexion perdue");
                break;
            case "elimine":
                if (EnPartie) bots.Match?.ImposerElimination(m.j);
                break;
            case "fin":
                if (EnPartie) bots.Match?.ImposerFin(m.gagnant, m.raison);
                break;
            case "piano":
                if (m.j != moi) Piano.Distant(m.j, m.on);
                break;
            case "latence": LatenceMs = m.v; break;
            case "refus": Debug.Log($"Refus du serveur ({m.@ref}) : {m.raison}"); break;
        }
    }

    bool EnPartie => partie != null && partie.Active && partie.Mode == PaintballSolo.ModePartie.EnLigne && partie.Bots.Match != null;

    void Recaler(long h)
    {
        // Le plus petit retard observé (message le plus rapide) fait référence ; dérive lente admise.
        double estimation = h - MaintenantLocal;
        decalage = double.IsNaN(decalage) ? estimation : Math.Max(estimation, decalage - 2);
    }

    // ---------- Envoi ----------
    void Update()
    {
        if (!EnPartie || Time.unscaledTime < prochainePosition) return;
        prochainePosition = Time.unscaledTime + PeriodePosition;
        var t = partie.transform; var v = partie.GetComponent<CharacterController>().velocity;
        texte.Clear();
        texte.Append("{\"t\":\"p\",\"q\":").Append(++sequence).Append(",\"p\":[");
        Nombres(t.position.x, t.position.y, t.position.z);
        texte.Append("],\"r\":["); Nombres(t.eulerAngles.y, partie.Tangage);
        texte.Append("],\"v\":["); Nombres(v.x, v.y, v.z);
        texte.Append("]}");
        ReseauEnvoyer(texte.ToString());
    }

    // Tir local : renvoie l'identifiant à rappeler dans une éventuelle touche.
    public int Tir(Vector3 origine, Vector3 direction, float vitesse)
    {
        int id = prochainTir++;
        texte.Clear();
        texte.Append("{\"t\":\"tir\",\"id\":").Append(id).Append(",\"o\":[");
        Nombres(origine.x, origine.y, origine.z);
        texte.Append("],\"d\":["); Nombres(direction.x, direction.y, direction.z);
        texte.Append("],\"v\":"); Nombre(vitesse); texte.Append('}');
        ReseauEnvoyer(texte.ToString());
        return id;
    }

    // Piano : les autres joueurs l'entendent jouer (son 3D au piano, selon leur distance).
    public void EnvoyerPiano(bool joue)
    {
        if (!EnPartie) return;
        ReseauEnvoyer(joue ? "{\"t\":\"piano\",\"on\":true}" : "{\"t\":\"piano\",\"on\":false}");
    }

    public void Touche(int tir, int cible, Vector3 point)
    {
        texte.Clear();
        texte.Append("{\"t\":\"touche\",\"tir\":").Append(tir).Append(",\"cible\":").Append(cible).Append(",\"pt\":[");
        Nombres(point.x, point.y, point.z);
        texte.Append("]}");
        ReseauEnvoyer(texte.ToString());
    }

    void Nombre(float x) => texte.Append(x.ToString("0.###", CultureInfo.InvariantCulture));
    void Nombres(params float[] valeurs) { for (int i = 0; i < valeurs.Length; i++) { if (i > 0) texte.Append(','); Nombre(valeurs[i]); } }
    static Vector3 V(float[] a) => new(a[0], a[1], a[2]);

    void OnDestroy() { if (Instance == this) Instance = null; }
}

// Messages du serveur réunis dans une classe plate (JsonUtility), aiguillée par t.
[Serializable]
public class MessageServeur
{
    public string t, phase, raison, @ref;
    public int j = -1, hote = -1, cible = -1, vies, tireur = -1, tir, points, gagnant = -1, id;
    public bool elimine, on;
    public long h;
    public float v;
    public float[] spawn, pt, o, d, p;
    public JoueurServeur[] joueurs;
    public PoseServeur[] l;
}

[Serializable]
public class JoueurServeur
{
    public int j, c, vies, points;
    public string nom;
    public bool pret, elimine, connecte;
    public float[] spawn;
}

[Serializable]
public class PoseServeur
{
    public int j, q;
    public long h;
    public float[] p, r, v;
}

using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

// Accueil, HUD, pause et résultats du mode paintball. La couleur de peinture choisie
// teinte l'éclaboussure du titre, le bouton Jouer, le réticule et les jauges.
public partial class InterfaceVisite
{
    public Texture2D eclaboussure;
    static readonly Color Nuit = Hex("0B1A15"), NuitClaire = Hex("132A22");
    PaintballSolo partie;
    TMP_Text scorePaintball, statsPaintball, munitionsPaintball, tempsPaintball, vuePaintball, couleurAccueil, gainPaintball, recordAccueil;
    ReticulePaintball reticule;
    FormeInterface jaugeTemps, jaugeMunitions;
    RawImage tacheAccueil;
    DisqueInterface boutonJouerFond;
    RectTransform anneauJouer, selectionCouleur;
    readonly RectTransform[] pastilles = new RectTransform[6];
    int couleurSelectionnee, touchesAffichees;
    float gainTemps, orbiteAccueil;
    // Mode contre les bots : tableau des joueurs, voile de touche reçue.
    TMP_Text degatsPaintball;
    RectTransform pivotTouche; FlecheInterface flecheTouche;
    readonly System.Collections.Generic.List<TMP_Text> lignesJoueurs = new();
    UnityEngine.UI.Image voileDegats;
    readonly System.Collections.Generic.List<DisqueInterface> pastillesJoueurs = new();
    bool ModeBots => partie != null && partie.Mode == PaintballSolo.ModePartie.Bots;
    bool ModeEnLigne => partie != null && partie.Mode == PaintballSolo.ModePartie.EnLigne;
    // Partie à plusieurs joueurs (bots ou en ligne) : tableau des joueurs, vies, touches.
    bool ModeMatch => ModeBots || ModeEnLigne;
    int CibleBots => new ReglesMatch { vies = partie.Vies }.Cible(partie.NombreBots + 1);
    string ViesTexte => partie.Vies + (partie.Vies > 1 ? " vies" : " vie");

    void InitialiserPaintball()
    {
        partie = explorateur.GetComponent<PaintballSolo>();
        if (partie == null) return;
        partie.Actualise += ActualiserPaintball; partie.PartieFinie += FinPaintball;
        if (partie.Bots != null) partie.Bots.Change += ActualiserPaintball;
    }

    Color Peinture => PaintballSolo.Couleurs[couleurSelectionnee];

    // ---------- Accueil ----------
    void AfficherAccueilPaintball(bool garderOrbite = false)
    {
        if (!garderOrbite) orbiteAccueil = 0;
        Voile(contenu, "OmbreLaterale", Vector2.zero, new(.7f, 1), new Color(Nuit.r, Nuit.g, Nuit.b, .96f), Color.clear, true);
        Voile(contenu, "OmbreBasse", Vector2.zero, new(1, .42f), new Color(Nuit.r, Nuit.g, Nuit.b, .9f), Color.clear);

        Texte(contenu, "Signature", "CHÂTEAU SAINT-VICTOR  ·  MARSEILLE", 17, new(.045f, .915f), new(.5f, .965f), Ivoire).characterSpacing = 18;
        var options = BoutonPilule(contenu, "OuvrirOptions", "Options", new(.58f, .912f), new(.692f, .968f), () => AfficherOptions(), false);
        var commandes = BoutonPilule(contenu, "OuvrirCommandes", "Commandes", new(.705f, .912f), new(.835f, .968f), () => AfficherCommandes(), false);
        var quitter = BoutonPilule(contenu, "QuitterApplication", "Quitter", new(.848f, .912f), new(.955f, .968f), Application.Quit, false);

        var zoneTache = Zone(contenu, "Eclaboussure", new(.2f, .6f), new(.2f, .6f)); zoneTache.sizeDelta = new Vector2(560, 560);
        tacheAccueil = zoneTache.gameObject.AddComponent<RawImage>();
        tacheAccueil.texture = eclaboussure; tacheAccueil.color = new Color(Peinture.r, Peinture.g, Peinture.b, .6f); tacheAccueil.raycastTarget = false;
        tacheAccueil.rectTransform.localRotation = Quaternion.Euler(0, 0, -14);

        Texte(contenu, "TitreAccueil", "Saint-Victor", 150, new(.04f, .55f), new(.8f, .78f), Ivoire, true);
        var sous = Texte(contenu, "SousTitre", "PAINTBALL", 54, new(.048f, .475f), new(.6f, .56f), Ivoire);
        sous.fontStyle = FontStyles.Bold; sous.characterSpacing = 42;
        string invitation = ModeEnLigne
            ? "Jouez à plusieurs dans le domaine. Connectez-vous avec Google\npour créer une partie ou rejoindre celle où l'on vous invite."
            : ModeBots
            ? $"Le domaine devient votre terrain de jeu. {partie.NombreBots} robot{(partie.NombreBots > 1 ? "s" : "")}, {ViesTexte} chacun :\nle premier à {CibleBots} touches l'emporte."
            : "Le domaine devient votre terrain de jeu. Sans chrono, huit cibles,\nune seule couleur : la vôtre.";
        Texte(contenu, "Invitation", invitation, 25, new(.048f, .37f), new(.6f, .47f), new Color(Ivoire.r, Ivoire.g, Ivoire.b, .85f));

        Texte(contenu, "CouleurTitre", "VOTRE PEINTURE", 15, new(.048f, .29f), new(.3f, .325f), Laiton).characterSpacing = 20;
        couleurAccueil = Texte(contenu, "CouleurJoueur", PaintballSolo.NomsCouleurs[couleurSelectionnee], 22, new(.235f, .225f), new(.45f, .285f), Ivoire);
        var couleurs = new Button[PaintballSolo.Couleurs.Length];
        selectionCouleur = Zone(contenu, "AnneauSelection", Vector2.zero, Vector2.zero);
        var anneau = selectionCouleur.gameObject.AddComponent<FormeInterface>(); anneau.contour = 3; anneau.color = Ivoire; anneau.raycastTarget = false;
        for (int i = 0; i < couleurs.Length; i++)
        {
            int index = i; float x = .05f + i * .03f;
            couleurs[i] = Pastille(contenu, "Peinture" + i, PaintballSolo.Couleurs[i], new(x, .232f), new(x + .022f, .278f), () => ChoisirCouleur(index));
            pastilles[i] = (RectTransform)couleurs[i].transform;
        }

        var record = partie.MeilleurScore;
        var modeEntrainement = BoutonPilule(contenu, "ModeEntrainement", "Entraînement", new(.048f, .14f), new(.165f, .195f), () => ChoisirModeAccueil(PaintballSolo.ModePartie.Entrainement, "ModeEntrainement"), !ModeMatch);
        var modeBots = BoutonPilule(contenu, "ModeBots", "Contre les bots", new(.173f, .14f), new(.305f, .195f), () => ChoisirModeAccueil(PaintballSolo.ModePartie.Bots, "ModeBots"), ModeBots);
        var modeEnLigne = BoutonPilule(contenu, "ModeEnLigne", "En ligne", new(.313f, .14f), new(.405f, .195f), () => ChoisirModeAccueil(PaintballSolo.ModePartie.EnLigne, "ModeEnLigne"), ModeEnLigne);
        Button nombreBots = null, niveauBots = null, viesBots = null;
        var nombres = new Button[5];
        if (ModeBots)
        {
            // Nombre d'adversaires : une pastille par choix, la sélection est pleine.
            Texte(contenu, "TitreRobots", "ROBOTS", 13, new(.43f, .197f), new(.6f, .222f), Laiton).characterSpacing = 18;
            for (int i = 0; i < nombres.Length; i++)
            {
                int n = i + 1; float x = .43f + i * .037f;
                nombres[i] = BoutonPilule(contenu, "NombreBots" + n, n.ToString(), new(x, .14f), new(x + .031f, .195f),
                    () => { partie.NombreBots = n; RafraichirAccueil("NombreBots" + n); }, partie.NombreBots == n);
            }
            nombreBots = nombres[0];
            niveauBots = BoutonPilule(contenu, "NiveauBots", PartieBots.NomsNiveaux[(int)partie.NiveauBots], new(.622f, .14f), new(.715f, .195f),
                () => { partie.NiveauBots = (PartieBots.Niveau)(((int)partie.NiveauBots + 1) % 3); RafraichirAccueil("NiveauBots"); }, false);
            // Nombre de vies : 1, 2, 3, 5 ou 10, un clic passe au choix suivant.
            Texte(contenu, "TitreVies", "VIES", 13, new(.723f, .197f), new(.8f, .222f), Laiton).characterSpacing = 18;
            viesBots = BoutonPilule(contenu, "ViesBots", ViesTexte, new(.723f, .14f), new(.8f, .195f), () =>
            {
                int i = System.Array.IndexOf(PaintballSolo.ChoixVies, partie.Vies);
                partie.Vies = PaintballSolo.ChoixVies[(i + 1) % PaintballSolo.ChoixVies.Length]; RafraichirAccueil("ViesBots");
            }, false);
        }
        string chips = ModeEnLigne ? "2 à 8 joueurs   ·   3 vies   ·   1 point par touche   ·   connexion Google" : ModeBots ? $"{ViesTexte}   ·   1 point par touche   ·   victoire à {CibleBots} points" : $"Sans chrono   ·   8 cibles   ·   50 billes   ·   Record {record:0000}";
        recordAccueil = Texte(contenu, "Chips", chips, 19, new(.25f, .055f), new(.75f, .115f), new Color(Ivoire.r, Ivoire.g, Ivoire.b, .8f));
        var espaces = BoutonPilule(contenu, "ChoisirEspaces", "Explorer le château", new(.048f, .055f), new(.235f, .115f), () => AfficherEspaces(0), false);

        anneauJouer = Zone(contenu, "AnneauJouer", new(.815f, .095f), new(.945f, .33f));
        var ratio = anneauJouer.gameObject.AddComponent<AspectRatioFitter>(); ratio.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth; ratio.aspectRatio = 1;
        var cercle = Zone(anneauJouer, "Cercle", Vector2.zero, Vector2.one).gameObject.AddComponent<FormeInterface>(); cercle.contour = 2.5f; cercle.raycastTarget = false;
        cercle.color = new Color(Ivoire.r, Ivoire.g, Ivoire.b, .55f);
        var entrer = BoutonRond(contenu, "CommencerPartie", "Jouer", new(.815f, .095f), new(.945f, .33f), CommencerPaintball);
        boutonJouerFond = entrer.GetComponentInChildren<DisqueInterface>(); boutonJouerFond.color = Peinture;
        var libelle = entrer.GetComponentInChildren<TMP_Text>(); libelle.color = Nuit; libelle.fontSize = 40; libelle.fontStyle = FontStyles.Bold;
        Texte(contenu, "LegendeEntrer", ModeEnLigne ? "EN LIGNE" : ModeBots ? "CONTRE LES BOTS" : "PARTIE SOLO", 15, new(.80f, .025f), new(.96f, .065f), Ivoire, false, TextAlignmentOptions.Center).characterSpacing = 20;

        for (int i = 0; i < couleurs.Length; i++) Relier(couleurs[i], commandes, modeEntrainement, i > 0 ? couleurs[i - 1] : entrer, i + 1 < couleurs.Length ? couleurs[i + 1] : entrer);
        Button apresBots = nombreBots != null ? nombreBots : entrer;
        Relier(modeEntrainement, couleurs[0], espaces, entrer, modeBots);
        Relier(modeBots, couleurs[1], espaces, modeEntrainement, modeEnLigne);
        Relier(modeEnLigne, couleurs[2], espaces, modeBots, apresBots);
        if (nombreBots != null)
        {
            for (int i = 0; i < nombres.Length; i++) Relier(nombres[i], couleurs[Mathf.Min(i + 2, couleurs.Length - 1)], espaces, i > 0 ? nombres[i - 1] : modeEnLigne, i + 1 < nombres.Length ? nombres[i + 1] : niveauBots);
            Relier(niveauBots, couleurs[couleurs.Length - 1], espaces, nombres[nombres.Length - 1], viesBots);
            Relier(viesBots, couleurs[couleurs.Length - 1], espaces, niveauBots, entrer);
        }
        Relier(entrer, commandes, espaces, couleurs[couleurs.Length - 1], quitter);
        Relier(espaces, modeEntrainement, entrer, entrer, entrer);
        Relier(options, entrer, couleurs[0], espaces, commandes);
        Relier(commandes, entrer, couleurs[0], options, quitter);
        Relier(quitter, entrer, entrer, commandes, entrer);
        PlacerSelection();
        Selectionner(entrer);
    }

    void ChoisirModeAccueil(PaintballSolo.ModePartie mode, string focus)
    {
        partie.ChoisirMode(mode); RafraichirAccueil(focus);
    }

    // Reconstruit l'accueil sans interrompre le survol, focus rendu au bouton actionné.
    void RafraichirAccueil(string focus)
    {
        float orbite = orbiteAccueil;
        Nouveau(Ecran.Accueil, false);
        cameraVisite.fieldOfView = 45f;
        orbiteAccueil = orbite; AfficherAccueilPaintball(true);
        Canvas.ForceUpdateCanvases();
        foreach (var b in contenu.GetComponentsInChildren<Button>()) if (b.name == focus) Selectionner(b);
    }

    void ChoisirCouleur(int index)
    {
        couleurSelectionnee = index; partie.ChoisirCouleur(index);
        if (couleurAccueil != null) couleurAccueil.text = PaintballSolo.NomsCouleurs[index];
        if (tacheAccueil != null) tacheAccueil.color = new Color(Peinture.r, Peinture.g, Peinture.b, .6f);
        if (boutonJouerFond != null) { boutonJouerFond.color = Peinture; boutonJouerFond.SetVerticesDirty(); }
        PlacerSelection();
    }

    void PlacerSelection()
    {
        if (selectionCouleur == null || pastilles[couleurSelectionnee] == null) return;
        var p = pastilles[couleurSelectionnee];
        selectionCouleur.anchorMin = p.anchorMin; selectionCouleur.anchorMax = p.anchorMax;
        selectionCouleur.offsetMin = new Vector2(-6, -6); selectionCouleur.offsetMax = new Vector2(6, 6);
    }

    Button Pastille(Transform parent, string nom, Color couleur, Vector2 min, Vector2 max, System.Action action)
    {
        var rt = Zone(parent, nom, min, max);
        var ratio = rt.gameObject.AddComponent<AspectRatioFitter>(); ratio.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth; ratio.aspectRatio = 1;
        var disque = rt.gameObject.AddComponent<DisqueInterface>(); disque.color = Color.white;
        var b = rt.gameObject.AddComponent<Button>(); b.targetGraphic = disque;
        var c = b.colors; c.normalColor = couleur; c.highlightedColor = Color.Lerp(couleur, Color.white, .25f); c.selectedColor = Color.Lerp(couleur, Color.white, .2f);
        c.pressedColor = couleur * .8f; c.fadeDuration = .12f; b.colors = c;
        b.onClick.AddListener(() => action()); b.onClick.AddListener(SonsPaintball.Menu);
        rt.gameObject.AddComponent<FocusInterface>();
        return b;
    }

    Button BoutonPilule(Transform parent, string nom, string texte, Vector2 min, Vector2 max, System.Action action, bool plein, Color? remplissage = null)
    {
        var rt = Zone(parent, nom, min, max);
        var forme = rt.gameObject.AddComponent<FormeInterface>(); forme.color = Color.white;
        if (!plein) forme.contour = 1.6f;
        var b = rt.gameObject.AddComponent<Button>(); b.targetGraphic = forme;
        Color fond = plein ? (remplissage ?? Peinture) : new Color(Ivoire.r, Ivoire.g, Ivoire.b, .55f);
        var c = b.colors; c.normalColor = fond; c.highlightedColor = plein ? Color.Lerp(fond, Color.white, .2f) : Ivoire; c.selectedColor = plein ? Color.Lerp(fond, Color.white, .25f) : Ivoire;
        c.pressedColor = fond * .8f; c.fadeDuration = .12f; b.colors = c;
        b.onClick.AddListener(() => action()); b.onClick.AddListener(SonsPaintball.Menu);
        rt.gameObject.AddComponent<FocusInterface>();
        var t = Texte(rt, "Libelle", texte, 20, new(.06f, 0), new(.94f, 1), plein ? Nuit : Ivoire, false, TextAlignmentOptions.Center);
        if (plein) t.fontStyle = FontStyles.Bold;
        return b;
    }

    void AnimerAccueil()
    {
        if (EcranActuel != Ecran.Accueil || partie == null || !MouvementActif) return;
        // Survol lent du domaine : orbite autour du château, cadrage identique au départ.
        orbiteAccueil += Time.unscaledDeltaTime * 2.2f;
        float a = orbiteAccueil * Mathf.Deg2Rad;
        Vector3 depart = new(0, 62, 12), cible = new(0, 1, 6);
        Vector3 rel = depart - cible;
        Vector3 tourne = new(rel.x * Mathf.Cos(a) - rel.y * Mathf.Sin(a), rel.x * Mathf.Sin(a) + rel.y * Mathf.Cos(a), rel.z);
        ApercuScene(cible + tourne, cible, 0);
        if (anneauJouer != null)
        {
            float t = Mathf.Repeat(Time.unscaledTime, 2.2f) / 2.2f;
            anneauJouer.localScale = Vector3.one * (1 + t * .18f);
            var g = anneauJouer.GetComponentInChildren<FormeInterface>(); var c = g.color; c.a = .55f * (1 - t); g.color = c;
        }
    }

    // Mesures navigateur : entrer dans un espace par son numéro (SendMessage passe une chaîne).
    // Vérification navigateur : ouvrir (ou fermer) les portes dont le nom contient le filtre.
    public void BasculerPortes(string filtre)
    {
        foreach (var porte in FindObjectsByType<Porte>(FindObjectsSortMode.None))
            if (porte.name.Contains(filtre)) porte.Basculer(explorateur.transform.position);
    }
    // Vérification navigateur : se placer à d mètres d'un objet de la scène et le regarder ("nom:d").
    public void RegarderObjet(string reglage)
    {
        var r = reglage.Split(':'); var go = GameObject.Find(r[0]); if (go == null) return;
        float d = r.Length > 1 && float.TryParse(r[1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var v) ? v : 12;
        var rendus = go.GetComponentsInChildren<Renderer>(); Bounds b = rendus.Length > 0 ? rendus[0].bounds : new Bounds(go.transform.position, Vector3.one);
        foreach (var x in rendus) b.Encapsulate(x.bounds);
        Vector3 cible = b.center, oeil = cible + new Vector3(.7f, 0, -.7f) * d;
        // Au sol : les yeux à hauteur d'enfant au-dessus du terrain sous ce point.
        if (Physics.Raycast(new Vector3(oeil.x, b.max.y + 20, oeil.z), Vector3.down, out var sol, 200, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
            oeil.y = sol.point.y + PaintballSolo.Yeux;
        if (EcranActuel != Ecran.Visite) Entrer(6);
        controleur.enabled = false;
        explorateur.transform.SetPositionAndRotation(oeil - Vector3.up * PaintballSolo.Yeux, Quaternion.LookRotation(new Vector3(cible.x - oeil.x, 0, cible.z - oeil.z)));
        var dir = cible - oeil; explorateur.RetablirRegard(Quaternion.Euler(-Mathf.Atan2(dir.y, new Vector2(dir.x, dir.z).magnitude) * Mathf.Rad2Deg, 0, 0));
        controleur.enabled = true; Physics.SyncTransforms();
    }
    public void EntrerEspace(string index) { if (int.TryParse(index, out int i)) Entrer(Mathf.Clamp(i, 0, Lieux.Length - 1)); }

    // Vérification navigateur : partie contre n bots ("2" ou "2:Difficile"), sans passer par les menus.
    public void CommencerBots(string reglage)
    {
        if (partie == null) return;
        var r = reglage.Split(':');
        if (int.TryParse(r[0], out int n)) partie.NombreBots = Mathf.Clamp(n, 1, 5);
        if (r.Length > 1 && System.Enum.TryParse(r[1], out PartieBots.Niveau niveau)) partie.NiveauBots = niveau;
        partie.ChoisirMode(PaintballSolo.ModePartie.Bots); CommencerPaintball();
    }

    public void CommencerPaintball()
    {
        if (partie == null) return;
        VisiteCommencee = true; positionMemorisee = false; partie.ChoisirCouleur(couleurSelectionnee);
        // Téléphone : plein écran au premier geste (appliqué par le navigateur pendant ce toucher).
        if (Tactile.Actif) Screen.fullScreen = true;
        touchesAffichees = 0; gainTemps = 0;
        partie.Demarrer();
        // En ligne, Demarrer ouvre le salon de la page ; la partie commence au signal du serveur.
        if (!ModeEnLigne) AfficherVisite();
    }

    // Signal debut du serveur : passer en jeu, quel que soit l'écran affiché.
    public void CommencerEnLigne()
    {
        VisiteCommencee = true; positionMemorisee = false; touchesAffichees = 0; gainTemps = 0;
        AfficherVisite();
    }

    // ---------- HUD ----------
    void AfficherHudPaintball()
    {
        Color teinte = partie.Couleur;
        var haut = Zone(contenu, "Score", new(.025f, .845f), new(.25f, .975f));
        var fondHaut = haut.gameObject.AddComponent<FormeInterface>(); fondHaut.rayon = 18; fondHaut.color = new Color(Nuit.r, Nuit.g, Nuit.b, .72f); fondHaut.raycastTarget = false;
        Texte(haut, "Etiquette", "SCORE", 13, new(.08f, .7f), new(.95f, .92f), Laiton).characterSpacing = 20;
        scorePaintball = Texte(haut, "Valeur", "", 44, new(.08f, .3f), new(.95f, .78f), Ivoire);
        scorePaintball.fontStyle = FontStyles.Bold;
        statsPaintball = Texte(haut, "Stats", "", 15, new(.08f, .06f), new(.95f, .3f), new Color(Ivoire.r, Ivoire.g, Ivoire.b, .8f));

        var chrono = Zone(contenu, "Chrono", new(.43f, .9f), new(.57f, .975f));
        var fondChrono = chrono.gameObject.AddComponent<FormeInterface>(); fondChrono.color = new Color(Nuit.r, Nuit.g, Nuit.b, .72f); fondChrono.raycastTarget = false;
        tempsPaintball = Texte(chrono, "Temps", "", 34, new(0, .12f), new(1, 1), Ivoire, false, TextAlignmentOptions.Center);
        tempsPaintball.fontStyle = FontStyles.Bold;
        var piste = Zone(chrono, "Piste", new(.14f, .1f), new(.86f, .17f)).gameObject.AddComponent<FormeInterface>(); piste.color = new Color(1, 1, 1, .18f); piste.raycastTarget = false;
        jaugeTemps = Zone(chrono, "Jauge", new(.14f, .1f), new(.86f, .17f)).gameObject.AddComponent<FormeInterface>(); jaugeTemps.color = teinte; jaugeTemps.raycastTarget = false;

        var bas = Tactile.Actif ? Zone(contenu, "Munitions", new(.4f, .02f), new(.6f, .155f)) : Zone(contenu, "Munitions", new(.78f, .035f), new(.975f, .17f));
        var fondBas = bas.gameObject.AddComponent<FormeInterface>(); fondBas.rayon = 18; fondBas.color = new Color(Nuit.r, Nuit.g, Nuit.b, .72f); fondBas.raycastTarget = false;
        Texte(bas, "Etiquette", "BILLES", 13, new(.08f, .7f), new(.6f, .92f), Laiton).characterSpacing = 20;
        munitionsPaintball = Texte(bas, "Valeur", "", 40, new(.08f, .3f), new(.92f, .78f), Ivoire);
        munitionsPaintball.fontStyle = FontStyles.Bold;
        var pisteM = Zone(bas, "Piste", new(.08f, .16f), new(.92f, .24f)).gameObject.AddComponent<FormeInterface>(); pisteM.color = new Color(1, 1, 1, .16f); pisteM.raycastTarget = false;
        jaugeMunitions = Zone(bas, "Jauge", new(.08f, .16f), new(.92f, .24f)).gameObject.AddComponent<FormeInterface>(); jaugeMunitions.color = teinte; jaugeMunitions.raycastTarget = false;
        vuePaintball = Texte(contenu, "Vue", "", 16, new(.78f, .175f), new(.975f, .21f), new Color(Ivoire.r, Ivoire.g, Ivoire.b, .75f), false, TextAlignmentOptions.MidlineRight);
        vuePaintball.gameObject.SetActive(!Tactile.Actif);

        var aide = Zone(contenu, "AidePaintball", new(.03f, .035f), new(.55f, .1f));
        aide.gameObject.SetActive(!Tactile.Actif);
        Texte(aide, "Texte", "ZQSD · bouger    Clic · tirer    Clic droit · viser    C · accroupi    V · vue    R · recharger    E · portes    Échap · pause", 16, Vector2.zero, Vector2.one, new Color(Ivoire.r, Ivoire.g, Ivoire.b, .7f));
        StartCoroutine(MasquerAide(aide.gameObject));

        var zoneReticule = Zone(contenu, "Reticule", new(.5f, .5f), new(.5f, .5f)); zoneReticule.sizeDelta = new Vector2(90, 90);
        reticule = zoneReticule.gameObject.AddComponent<ReticulePaintball>(); reticule.teinte = Color.Lerp(teinte, Color.white, .35f); reticule.raycastTarget = false;
        gainPaintball = Texte(contenu, "Gain", "", 30, new(.515f, .515f), new(.62f, .575f), Color.Lerp(teinte, Color.white, .3f));
        gainPaintball.fontStyle = FontStyles.Bold; gainPaintball.alpha = 0;

        if (ModeMatch) HudBots(teinte);

        indicationPorte = Zone(contenu, "InteractionPaintball", new(.38f, .25f), new(.62f, .3f)).gameObject;
        var fondPorte = indicationPorte.AddComponent<FormeInterface>(); fondPorte.color = new Color(Nuit.r, Nuit.g, Nuit.b, .78f); fondPorte.raycastTarget = false;
        porteHud = Texte(indicationPorte.transform, "Action", "E · Ouvrir la porte", 19, Vector2.zero, Vector2.one, Ivoire, false, TextAlignmentOptions.Center);
        indicationPorte.SetActive(false);
        if (Tactile.Actif) CommandesTactilesHud(true, teinte);
        EventSystem.current.SetSelectedGameObject(null); ActualiserPaintball();
    }

    // ---------- Commandes tactiles ----------
    // Disposition des tireurs sur téléphone : joystick à gauche, regard à droite, tir des deux côtés.
    void CommandesTactilesHud(bool paintball, Color teinte)
    {
        Tactile.Relacher();
        var regard = Zone(contenu, "RegardTactile", new(.4f, 0), new(1, .86f)).gameObject.AddComponent<RegardTactile>();
        regard.color = Color.clear; regard.transform.SetAsFirstSibling();
        var zone = Zone(contenu, "JoystickTactile", new(0, 0), new(.4f, .7f));
        var joystick = zone.gameObject.AddComponent<JoystickTactile>(); joystick.color = Color.clear;
        // Socle et bouton ancrés au centre de la zone, comme le point local renvoyé par le toucher.
        joystick.socle = Zone(zone, "Socle", new(.5f, .5f), new(.5f, .5f)); joystick.socle.sizeDelta = new Vector2(240, 240);
        var anneau = joystick.socle.gameObject.AddComponent<FormeInterface>(); anneau.contour = 3; anneau.color = new Color(Ivoire.r, Ivoire.g, Ivoire.b, .45f); anneau.raycastTarget = false;
        joystick.bouton = Zone(zone, "Bouton", new(.5f, .5f), new(.5f, .5f)); joystick.bouton.sizeDelta = new Vector2(110, 110);
        var disque = joystick.bouton.gameObject.AddComponent<DisqueInterface>(); disque.color = new Color(Ivoire.r, Ivoire.g, Ivoire.b, .55f); disque.raycastTarget = false;
        joystick.socle.gameObject.SetActive(false); joystick.bouton.gameObject.SetActive(false);
        Texte(zone, "Indication", "Glisser pour se déplacer", 18, new(.1f, .1f), new(.9f, .2f), new Color(Ivoire.r, Ivoire.g, Ivoire.b, .45f), false, TextAlignmentOptions.Center);

        Color secondaire = new(Ivoire.r, Ivoire.g, Ivoire.b, .16f);
        if (paintball)
        {
            BoutonTactileRond("TirDroit", "Tir", new(.835f, .24f), 170, teinte, "tir", true);
            BoutonTactileRond("TirGauche", "Tir", new(.075f, .64f), 110, teinte, "tir", true);
            BoutonTactileRond("Viser", "Viser", new(.95f, .41f), 100, secondaire, "visee", false);
            BoutonTactileRond("Sauter", "Saut", new(.95f, .2f), 95, secondaire, "saut", false);
            BoutonTactileRond("Vue", "Vue", new(.95f, .6f), 85, secondaire, "vue", false);
            BoutonTactileRond("Recharger", "Recharge", new(.69f, .1f), 90, secondaire, "recharge", false);
            BoutonTactileRond("Porte", "Porte", new(.7f, .42f), 85, secondaire, "porte", false);
            BoutonTactileRond("Accroupir", "Accroupi", new(.83f, .6f), 100, secondaire, "accroupir", false);
            var pause = BoutonPilule(contenu, "PauseTactile", "Pause", new(.6f, .9f), new(.7f, .965f), () => AfficherPausePaintball(), false);
            pause.navigation = new Navigation { mode = Navigation.Mode.None };
        }
        else
        {
            BoutonTactileRond("Sauter", "Saut", new(.93f, .2f), 110, secondaire, "saut", false);
            BoutonTactileRond("Porte", "Ouvrir", new(.8f, .2f), 110, secondaire, "porte", false);
            var espaces = BoutonPilule(contenu, "EspacesTactile", "Les espaces", new(.8f, .91f), new(.97f, .965f), () => AfficherEspaces(EspaceActuel), false);
            espaces.navigation = new Navigation { mode = Navigation.Mode.None };
        }
    }

    void BoutonTactileRond(string nom, string libelle, Vector2 centre, float taille, Color couleur, string action, bool regard)
    {
        var rt = Zone(contenu, nom, centre, centre); rt.sizeDelta = new Vector2(taille, taille);
        var d = rt.gameObject.AddComponent<DisqueInterface>(); d.color = new Color(couleur.r, couleur.g, couleur.b, Mathf.Min(couleur.a, .75f));
        var bord = Zone(rt, "Bord", Vector2.zero, Vector2.one).gameObject.AddComponent<FormeInterface>(); bord.contour = 2.5f; bord.raycastTarget = false;
        bord.color = new Color(Ivoire.r, Ivoire.g, Ivoire.b, .7f);
        var b = rt.gameObject.AddComponent<BoutonTactile>(); b.action = action; b.regard = regard;
        Texte(rt, "Libelle", libelle, taille > 150 ? 30 : libelle.Length > 5 ? 16 : 20, Vector2.zero, Vector2.one, action == "tir" ? Nuit : Ivoire, false, TextAlignmentOptions.Center).fontStyle = FontStyles.Bold;
    }

    // Tableau des joueurs (pastille, nom, vies, points), voile coloré quand on est touché.
    void HudBots(Color teinte)
    {
        var match = partie.Bots.Match; if (match == null) return;
        int n = match.joueurs.Count;
        float rangee = Tactile.Actif ? .04f : .05f;
        var panneau = Zone(contenu, "Joueurs", new(.8f, .975f - rangee * n - .045f), new(.975f, .975f));
        var fond = panneau.gameObject.AddComponent<FormeInterface>(); fond.rayon = 18; fond.color = new Color(Nuit.r, Nuit.g, Nuit.b, .72f); fond.raycastTarget = false;
        Texte(panneau, "Etiquette", $"VICTOIRE À {match.Cible}", 13, new(.08f, 1 - .045f / (rangee * n + .045f)), new(.95f, .98f), Laiton).characterSpacing = 18;
        pastillesJoueurs.Clear(); lignesJoueurs.Clear();
        float h = 1f / (n + .9f);
        for (int i = 0; i < n; i++)
        {
            float y1 = 1 - (.9f + i) * h, y0 = y1 - h;
            var ligne = Zone(panneau, "Joueur" + i, new(0, y0), new(1, y1));
            var p = Zone(ligne, "Pastille", new(.06f, .28f), new(.06f, .72f));
            var ratio = p.gameObject.AddComponent<AspectRatioFitter>(); ratio.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth; ratio.aspectRatio = 1;
            var d = p.gameObject.AddComponent<DisqueInterface>(); d.raycastTarget = false; pastillesJoueurs.Add(d);
            var texte = Texte(ligne, "Texte", "", 17, new(.17f, 0), new(.97f, 1), Ivoire); texte.textWrappingMode = TextWrappingModes.NoWrap;
            lignesJoueurs.Add(texte);
        }
        var plein = Zone(contenu, "VoileDegats", Vector2.zero, Vector2.one);
        voileDegats = plein.gameObject.AddComponent<UnityEngine.UI.Image>(); voileDegats.raycastTarget = false; voileDegats.color = Color.clear;
        plein.SetAsFirstSibling();
        degatsPaintball = Texte(contenu, "Degats", "", 34, new(.3f, .73f), new(.7f, .8f), Ivoire, false, TextAlignmentOptions.Center);
        degatsPaintball.fontStyle = FontStyles.Bold; degatsPaintball.alpha = 0;
        // D'où vient la touche : chevron sur un cercle autour du réticule, tourné vers le tireur.
        pivotTouche = Zone(contenu, "DirectionTouche", new(.5f, .5f), new(.5f, .5f));
        var fleche = Zone(pivotTouche, "Fleche", new(.5f, .5f), new(.5f, .5f));
        fleche.sizeDelta = new Vector2(46, 34); fleche.anchoredPosition = new Vector2(0, 170);
        flecheTouche = fleche.gameObject.AddComponent<FlecheInterface>(); flecheTouche.raycastTarget = false; flecheTouche.color = Color.clear;
    }

    void ActualiserBots()
    {
        var match = partie.Bots.Match; if (match == null) return;
        var moi = match.Joueur(partie.JoueurId);
        float precision = partie.Tirs == 0 ? 0 : 100f * partie.Touches / partie.Tirs;
        if (scorePaintball != null) scorePaintball.text = $"{moi.points}<size=50%><alpha=#99> / {match.Cible}</size>";
        if (statsPaintball != null) statsPaintball.text = $"{moi.vies} vie{(moi.vies > 1 ? "s" : "")}   ·   {partie.Tirs} billes   ·   {precision:0} %";
        int s = Mathf.FloorToInt(partie.TempsEcoule);
        if (tempsPaintball != null) { tempsPaintball.text = $"{s / 60}:{s % 60:00}"; tempsPaintball.color = Ivoire; }
        for (int i = 0; i < match.joueurs.Count && i < lignesJoueurs.Count; i++)
        {
            var j = match.joueurs[i];
            string nom = j.id == partie.JoueurId ? "<b>Vous</b>" : j.nom;
            lignesJoueurs[i].text = j.elimine ? $"<alpha=#66><s>{nom}</s>  éliminé"
                : $"{nom}<pos=52%><color=#{ColorUtility.ToHtmlStringRGB(PaintballSolo.Couleurs[j.couleur])}>{j.vies} vie{(j.vies > 1 ? "s" : "")}</color><pos=82%>{j.points}";
            pastillesJoueurs[i].color = j.elimine ? new Color(1, 1, 1, .25f) : PaintballSolo.Couleurs[j.couleur];
        }
    }

    int TireurDernier()
    {
        var j = partie.Bots.Match?.Joueur(partie.Bots.DernierTireur);
        return j != null ? j.couleur : 0;
    }

    void ActualiserPaintball()
    {
        if (partie == null || EcranActuel != Ecran.Visite) return;
        if (ModeMatch && partie.Active)
        {
            if (partie.Touches > touchesAffichees) { gainTemps = 1; touchesAffichees = partie.Touches; }
            ActualiserBots();
            if (munitionsPaintball != null) munitionsPaintball.text = partie.Recharge ? "<size=60%>Recharge…</size>" : $"{partie.Chargeur}<size=50%><alpha=#99> / 50</size>";
            if (vuePaintball != null) vuePaintball.text = $"{(partie.TroisiemePersonne ? "Vue à l’épaule" : "Première personne")}   ·   {partie.DistanceVisee:0} m";
            return;
        }
        if (partie.Touches > touchesAffichees) { gainTemps = 1; touchesAffichees = partie.Touches; }
        float precision = partie.Tirs == 0 ? 0 : 100f * partie.Touches / partie.Tirs;
        if (scorePaintball != null) scorePaintball.text = $"{partie.Touches * 100:0000}";
        if (statsPaintball != null) statsPaintball.text = $"{partie.Touches} / 8 cibles   ·   {partie.Tirs} billes   ·   {precision:0} %";
        if (munitionsPaintball != null) munitionsPaintball.text = partie.Recharge ? "<size=60%>Recharge…</size>" : $"{partie.Chargeur}<size=50%><alpha=#99> / 50</size>";
        int s = Mathf.FloorToInt(partie.TempsEcoule);
        if (tempsPaintball != null) { tempsPaintball.text = $"{s / 60}:{s % 60:00}"; tempsPaintball.color = Ivoire; }
        if (vuePaintball != null) vuePaintball.text = $"{(partie.TroisiemePersonne ? "Vue à l’épaule" : "Première personne")}   ·   {partie.DistanceVisee:0} m";
    }

    void AnimerHud()
    {
        if (partie == null || !partie.Active || EcranActuel != Ecran.Visite || reticule == null) return;
        reticule.Definir(partie.Ecart, Mathf.Clamp01(partie.RetourTouche / .32f), partie.ProgressionRecharge, partie.Chargeur == 0 && !partie.Recharge, partie.TroisiemePersonne ? .9f : 1);
        if (ModeMatch)
        {
            var m = partie.Bots.Match;
            if (jaugeTemps != null && m != null) { int meilleur = 0; foreach (var j in m.joueurs) meilleur = Mathf.Max(meilleur, j.points); jaugeTemps.Remplir((float)meilleur / Mathf.Max(1, m.Cible)); }
            float d = partie.Bots.DegatsRecus;
            if (voileDegats != null) { var c = PaintballSolo.Couleurs[Mathf.Max(0, TireurDernier())]; voileDegats.color = new Color(c.r, c.g, c.b, .32f * d); }
            // Qui et d'où : nom et couleur du tireur, distance, chevron orienté (3 s, puis fondu).
            float t = partie.Bots.DepuisTouche, visible = Mathf.Clamp01((3.2f - t) / .6f);
            var tireur = m?.Joueur(partie.Bots.DernierTireur);
            Color ct = PaintballSolo.Couleurs[Mathf.Clamp(tireur != null ? tireur.couleur : 0, 0, PaintballSolo.Couleurs.Length - 1)];
            Vector3 vers = partie.Bots.OrigineTouche - partie.transform.position;
            if (degatsPaintball != null)
            {
                degatsPaintball.text = tireur != null
                    ? $"Touché par <color=#{ColorUtility.ToHtmlStringRGB(ct)}>{tireur.nom}</color>  <size=70%>·  {partie.Bots.DistanceTouche:0} m</size>"
                    : "Touché !";
                degatsPaintball.alpha = visible;
            }
            if (pivotTouche != null && flecheTouche != null)
            {
                Vector3 avant = cameraVisite.transform.forward; avant.y = 0;
                float angle = Vector3.SignedAngle(avant, new Vector3(vers.x, 0, vers.z), Vector3.up);
                pivotTouche.localRotation = Quaternion.Euler(0, 0, -angle);
                flecheTouche.color = new Color(ct.r, ct.g, ct.b, visible);
            }
        }
        else if (jaugeTemps != null) jaugeTemps.Remplir(partie.TempsEcoule % 60f / 60f);
        if (jaugeMunitions != null) jaugeMunitions.Remplir(partie.Recharge ? Mathf.Max(0, partie.ProgressionRecharge) : partie.Chargeur / 50f);
        if (gainPaintball != null)
        {
            gainTemps = Mathf.MoveTowards(gainTemps, 0, Time.deltaTime * 1.4f);
            gainPaintball.text = ModeMatch ? "+1" : "+100"; gainPaintball.alpha = Mathf.Clamp01(gainTemps * 2);
            gainPaintball.rectTransform.anchoredPosition = new Vector2(0, (1 - gainTemps) * 40);
        }
    }

    // ---------- Pause et résultats ----------
    RawImage Tache(Vector2 min, Vector2 max, float angle, float alpha)
    {
        var zone = Zone(contenu, "Eclaboussure", (min + max) * .5f, (min + max) * .5f); zone.sizeDelta = Vector2.one * 1080 * (max.y - min.y);
        var img = zone.gameObject.AddComponent<RawImage>();
        img.texture = eclaboussure; img.color = new Color(partie.Couleur.r, partie.Couleur.g, partie.Couleur.b, alpha); img.raycastTarget = false;
        img.rectTransform.localRotation = Quaternion.Euler(0, 0, angle);
        return img;
    }

    void Tuile(string nom, string valeur, string etiquette, float x0, float x1, float y0, float y1)
    {
        var t = Zone(contenu, nom, new(x0, y0), new(x1, y1));
        var f = t.gameObject.AddComponent<FormeInterface>(); f.rayon = 16; f.color = new Color(1, 1, 1, .06f); f.raycastTarget = false;
        Texte(t, "Valeur", valeur, 40, new(.1f, .35f), new(.95f, .92f), Ivoire).fontStyle = FontStyles.Bold;
        Texte(t, "Etiquette", etiquette, 14, new(.1f, .08f), new(.95f, .35f), Laiton).characterSpacing = 18;
    }

    public void AfficherPausePaintball(bool empiler = true)
    {
        Nouveau(Ecran.PausePaintball, empiler);
        Voile(contenu, "PauseFond", Vector2.zero, Vector2.one, new Color(Nuit.r, Nuit.g, Nuit.b, .96f), new Color(Nuit.r, Nuit.g, Nuit.b, .78f));
        Tache(new(.52f, .25f), new(1.02f, 1.02f), 18, .22f);
        Texte(contenu, "Surtitre", "PARTIE EN COURS", 16, new(.085f, .82f), new(.6f, .86f), Laiton).characterSpacing = 20;
        Texte(contenu, "TitrePause", "Pause", 120, new(.08f, .62f), new(.7f, .83f), Ivoire, true);
        float precision = partie.Tirs == 0 ? 0 : 100f * partie.Touches / partie.Tirs;
        int s = Mathf.FloorToInt(partie.TempsEcoule);
        Tuile("TuileScore", ModeMatch && partie.Bots.Match != null ? $"{partie.Bots.Match.Joueur(partie.JoueurId).points} / {partie.Bots.Match.Cible}" : $"{partie.Touches * 100:0000}", ModeMatch ? "TOUCHES" : "POINTS", .085f, .245f, .43f, .58f);
        Tuile("TuileTemps", $"{s / 60}:{s % 60:00}", "ÉCOULÉ", .26f, .42f, .43f, .58f);
        Tuile("TuilePrecision", $"{precision:0} %", "PRÉCISION", .435f, .595f, .43f, .58f);
        Texte(contenu, "ReglesPause", "V : première / troisième personne   ·   R : recharger   ·   Clic droit : viser   ·   E : portes\nLes objets légers se poussent et se renversent.", 19, new(.085f, .3f), new(.9f, .4f), new Color(Ivoire.r, Ivoire.g, Ivoire.b, .75f));
        var reprendre = BoutonPilule(contenu, "ReprendrePaintball", "Reprendre", new(.085f, .15f), new(.26f, .225f), Reprendre, true);
        var recommencer = BoutonPilule(contenu, "RecommencerPaintball", "Recommencer", new(.275f, .15f), new(.43f, .225f), CommencerPaintball, false);
        var accueil = BoutonPilule(contenu, "QuitterPaintball", "Accueil", new(.445f, .15f), new(.56f, .225f), RetourAccueilPaintball, false);
        var options = BoutonPilule(contenu, "OptionsPaintball", "Options", new(.575f, .15f), new(.69f, .225f), () => AfficherOptions(), false);
        Relier(reprendre, reprendre, reprendre, options, recommencer); Relier(recommencer, recommencer, recommencer, reprendre, accueil);
        Relier(accueil, accueil, accueil, recommencer, options); Relier(options, options, options, accueil, reprendre);
        Selectionner(reprendre);
    }

    void RetourAccueilPaintball()
    {
        partie.Arreter(); positionMemorisee = false; VisiteCommencee = false; pile.Clear(); AfficherAccueil(false);
    }

    void FinPaintball()
    {
        if (ModeMatch) { FinBots(); return; }
        Nouveau(Ecran.PausePaintball, false);
        Voile(contenu, "ResultatFond", Vector2.zero, Vector2.one, new Color(Nuit.r, Nuit.g, Nuit.b, .95f), new Color(Nuit.r, Nuit.g, Nuit.b, .8f));
        Tache(new(.45f, .2f), new(1.05f, 1.05f), -10, .35f);
        Texte(contenu, "Surtitre", partie.NouveauRecord ? "NOUVEAU RECORD" : "FIN DE PARTIE", 16, new(.085f, .84f), new(.6f, .88f), partie.NouveauRecord ? partie.Couleur : Laiton).characterSpacing = 20;
        Texte(contenu, "TitreResultat", partie.Touches >= 8 ? "Château repeint !" : partie.Touches > 0 ? "Bien repeint !" : "À vos billes…", 104, new(.08f, .64f), new(.92f, .85f), Ivoire, true);
        var score = Texte(contenu, "Resultat", "0000", 130, new(.08f, .43f), new(.6f, .65f), partie.Couleur);
        score.fontStyle = FontStyles.Bold;
        StartCoroutine(Compter(score, partie.Touches * 100));
        Texte(contenu, "Points", "points", 30, new(.36f, .45f), new(.6f, .52f), Ivoire);
        float precision = partie.Tirs == 0 ? 0 : 100f * partie.Touches / partie.Tirs;
        Tuile("TuileCibles", $"{partie.Touches}/8", "CIBLES", .085f, .225f, .27f, .41f);
        Tuile("TuileBilles", $"{partie.Tirs}", "BILLES", .24f, .38f, .27f, .41f);
        Tuile("TuilePrecision", $"{precision:0} %", "PRÉCISION", .395f, .535f, .27f, .41f);
        Tuile("TuileRecord", $"{partie.MeilleurScore:0000}", "RECORD", .55f, .69f, .27f, .41f);
        var rejouer = BoutonPilule(contenu, "RejouerPaintball", "Rejouer", new(.085f, .13f), new(.26f, .205f), CommencerPaintball, true);
        var accueil = BoutonPilule(contenu, "AccueilResultat", "Accueil", new(.275f, .13f), new(.39f, .205f), RetourAccueilPaintball, false);
        Relier(rejouer, rejouer, rejouer, accueil, accueil); Relier(accueil, accueil, accueil, rejouer, rejouer);
        Selectionner(rejouer);
    }

    // Écran de fin contre les bots : issue, touches du joueur et classement.
    void FinBots()
    {
        var match = partie.Bots.Match;
        var moi = match.Joueur(partie.JoueurId);
        bool victoire = match.Gagnant == partie.JoueurId;
        var gagnant = match.Joueur(match.Gagnant);
        Nouveau(Ecran.PausePaintball, false);
        // Podium 3D à droite (taches de la partie comprises), résultats dans une colonne à gauche.
        PodiumPaintball.Montrer(partie, titrage);
        var fondResultat = Zone(contenu, "ResultatFond", Vector2.zero, new(.42f, 1)).gameObject.AddComponent<UnityEngine.UI.Image>();
        fondResultat.color = new Color(Nuit.r, Nuit.g, Nuit.b, .97f); fondResultat.raycastTarget = false;
        Voile(contenu, "ResultatFondu", new(.42f, 0), new(.62f, 1), new Color(Nuit.r, Nuit.g, Nuit.b, .97f), new Color(Nuit.r, Nuit.g, Nuit.b, 0), true);
        Voile(contenu, "ResultatBas", Vector2.zero, new(1, .2f), new Color(Nuit.r, Nuit.g, Nuit.b, .6f), Color.clear);
        Texte(contenu, "Surtitre", victoire ? "VICTOIRE" : moi.elimine ? "ÉLIMINÉ" : "FIN DE PARTIE", 16, new(.06f, .87f), new(.5f, .91f), victoire ? partie.Couleur : Laiton).characterSpacing = 20;
        string titre = victoire ? "Domaine conquis !" : gagnant != null ? $"{gagnant.nom} l’emporte" : moi.elimine ? "Plus de vies…" : "Égalité";
        Texte(contenu, "TitreResultat", titre, 80, new(.055f, .72f), new(.6f, .87f), Ivoire, true);
        var score = Texte(contenu, "Resultat", "0", 110, new(.06f, .54f), new(.2f, .72f), partie.Couleur);
        score.fontStyle = FontStyles.Bold;
        StartCoroutine(CompterSimple(score, moi.points));
        Texte(contenu, "Points", $"touche{(moi.points > 1 ? "s" : "")} sur {match.Cible}", 28, new(.15f, .57f), new(.48f, .64f), Ivoire);
        float precision = partie.Tirs == 0 ? 0 : 100f * partie.Touches / partie.Tirs;
        int s = Mathf.FloorToInt(partie.TempsEcoule);
        Tuile("TuileVies", $"{moi.vies}", "VIES", .06f, .16f, .4f, .52f);
        Tuile("TuileBilles", $"{partie.Tirs}", "BILLES", .17f, .27f, .4f, .52f);
        Tuile("TuilePrecision", $"{precision:0} %", "PRÉCISION", .28f, .38f, .4f, .52f);
        Tuile("TuileDuree", $"{s / 60}:{s % 60:00}", "DURÉE", .39f, .49f, .4f, .52f);
        var classement = Zone(contenu, "Classement", new(.06f, .15f), new(.49f, .38f));
        var f = classement.gameObject.AddComponent<FormeInterface>(); f.rayon = 16; f.color = new Color(1, 1, 1, .06f); f.raycastTarget = false;
        Texte(classement, "Etiquette", "CLASSEMENT", 14, new(.08f, .86f), new(.95f, .96f), Laiton).characterSpacing = 18;
        var lignes = new System.Text.StringBuilder();
        foreach (var j in match.Classement())
        {
            string nom = j.id == partie.JoueurId ? "<b>Vous</b>" : j.nom;
            int rang = j.rang > 0 ? j.rang : match.Classement().IndexOf(j) + 1;
            lignes.Append($"{rang}.  <color=#{ColorUtility.ToHtmlStringRGB(PaintballSolo.Couleurs[j.couleur])}>{nom}</color><pos=55%>{j.points} pt{(j.points > 1 ? "s" : "")}<pos=76%>{(j.elimine ? "éliminé" : $"{j.vies} vie{(j.vies > 1 ? "s" : "")}")}\n");
        }
        var t = Texte(classement, "Lignes", lignes.ToString(), 17, new(.05f, .04f), new(.97f, .84f), Ivoire);
        t.alignment = TextAlignmentOptions.TopLeft; t.textWrappingMode = TextWrappingModes.NoWrap;
        var rejouer = BoutonPilule(contenu, "RejouerPaintball", "Rejouer", new(.06f, .045f), new(.2f, .11f), CommencerPaintball, true);
        var accueil = BoutonPilule(contenu, "AccueilResultat", "Accueil", new(.21f, .045f), new(.32f, .11f), RetourAccueilPaintball, false);
        Relier(rejouer, rejouer, rejouer, accueil, accueil); Relier(accueil, accueil, accueil, rejouer, rejouer);
        Selectionner(rejouer);
    }

    System.Collections.IEnumerator CompterSimple(TMP_Text texte, int total)
    {
        float t = 0;
        while (t < 1 && texte != null)
        {
            t += Time.unscaledDeltaTime / (MouvementActif ? .8f : .01f);
            texte.text = Mathf.RoundToInt(total * (1 - Mathf.Pow(1 - Mathf.Clamp01(t), 3))).ToString();
            yield return null;
        }
    }

    System.Collections.IEnumerator Compter(TMP_Text texte, int total)
    {
        float t = 0;
        while (t < 1 && texte != null)
        {
            t += Time.unscaledDeltaTime / (MouvementActif ? 1.1f : .01f);
            float e = 1 - Mathf.Pow(1 - Mathf.Clamp01(t), 3);
            texte.text = $"{Mathf.RoundToInt(total * e):0000}";
            yield return null;
        }
    }
}

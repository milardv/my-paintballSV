using System;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

// Écran des options : jeu, graphisme, sons. Chaque réglage est un curseur (les choix discrets aussi :
// flèches gauche et droite au clavier ou à la manette, glissé à la souris ou au doigt), appliqué tout de suite.
// La scène reste visible à droite pour juger des réglages graphiques.
public partial class InterfaceVisite
{
    public void AfficherOptions(bool empiler = true)
    {
        Nouveau(Ecran.Options, empiler);
        Voile(contenu, "FondOptions", Vector2.zero, Vector2.one, new Color(Nuit.r, Nuit.g, Nuit.b, .96f), new Color(Nuit.r, Nuit.g, Nuit.b, .72f), true);
        Texte(contenu, "Surtitre", "RÉGLAGES", 16, new(.045f, .865f), new(.5f, .9f), Laiton).characterSpacing = 20;
        Texte(contenu, "TitreOptions", "Options", 96, new(.04f, .74f), new(.6f, .87f), Ivoire, true);

        var jeu = Colonne("ColonneJeu", "JEU", .045f);
        var graphisme = Colonne("ColonneGraphisme", "GRAPHISME", .365f);
        var sons = Colonne("ColonneSons", "SONS ET AMBIANCE", .685f);
        Slider[][] colonnes =
        {
            new[]
            {
                Reglage(jeu, "Sensibilite", "Sensibilité", 0, .25f, 3, false, Reglages.Sensibilite, v => $"{v:0.00}×".Replace('.', ','), v => Reglages.Sensibilite = v),
                Reglage(jeu, "InverserY", "Axe vertical", 1, 0, 1, true, Reglages.InverserY ? 1 : 0, v => v > .5f ? "Inversé" : "Normal", v => Reglages.InverserY = v > .5f),
                Reglage(jeu, "ChampVision", "Champ de vision", 2, 60, 100, true, Reglages.ChampVision, v => $"{v:0}°", v => Reglages.ChampVision = Mathf.RoundToInt(v)),
                Reglage(jeu, "Animations", "Animations de l'interface", 3, 0, 1, true, MouvementActif ? 1 : 0, v => v > .5f ? "Activées" : "Réduites",
                    v => { PlayerPrefs.SetInt("InterfaceMouvement", v > .5f ? 1 : 0); }),
            },
            new[]
            {
                Choix(graphisme, "Ombres", "Ombres", 0, Reglages.NomsOmbres, Reglages.Ombres, i => Reglages.Ombres = i),
                Choix(graphisme, "Resolution", "Résolution", 1, Reglages.NomsResolution, Reglages.Resolution, i => Reglages.Resolution = i),
                Choix(graphisme, "Anticrenelage", "Anticrénelage", 2, Reglages.NomsAnticrenelage, Reglages.Anticrenelage, i => Reglages.Anticrenelage = i),
                Choix(graphisme, "Images", "Images par seconde", 3, Reglages.NomsImages, Reglages.ImagesParSeconde, i => Reglages.ImagesParSeconde = i),
            },
            new[]
            {
                Reglage(sons, "Volume", "Volume général", 0, 0, 100, true, Reglages.VolumeGeneral * 100, v => $"{v:0} %", v => Reglages.VolumeGeneral = v / 100),
                Reglage(sons, "VolumeEffets", "Effets", 1, 0, 100, true, Reglages.VolumeEffets * 100, v => $"{v:0} %", v => Reglages.VolumeEffets = v / 100),
                Reglage(sons, "VolumeAmbiance", "Musique", 2, 0, 100, true, Reglages.VolumeAmbiance * 100, v => $"{v:0} %", v => Reglages.VolumeAmbiance = v / 100),
                Choix(sons, "Moment", "Moment de la journée", 3, MomentJournee.NomsModes, Reglages.Moment, i => Reglages.Moment = i),
                Choix(sons, "Neige", "Neige", 4, Reglages.NomsNeige, Reglages.Neige ? 1 : 0, i => Reglages.Neige = i == 1),
            },
        };
        Texte(contenu, "AideOptions", Tactile.Actif ? "Faites glisser les curseurs." : "Flèches gauche et droite pour régler, haut et bas pour changer de ligne.",
            18, new(.045f, .135f), new(.62f, .18f), new Color(Ivoire.r, Ivoire.g, Ivoire.b, .7f));
        var retablir = BoutonPilule(contenu, "RetablirOptions", "Rétablir", new(.045f, .06f), new(.165f, .118f), () =>
        {
            Reglages.Retablir(); PlayerPrefs.SetInt("InterfaceMouvement", 1); PlayerPrefs.Save();
            AfficherOptions(false);
            Selectionner(contenu.transform.Find("RetablirOptions")?.GetComponent<Button>());
        }, false);
        var retour = BoutonPilule(contenu, "RetourOptions", "Retour", new(.835f, .06f), new(.955f, .118f), () => { Reglages.Enregistrer(); Retour(); }, true);

        // Haut et bas parcourent les colonnes l'une après l'autre ; gauche et droite règlent le curseur.
        var lignes = new System.Collections.Generic.List<Selectable>();
        foreach (var c in colonnes) lignes.AddRange(c);
        for (int i = 0; i < lignes.Count; i++)
        {
            var nav = lignes[i].navigation; nav.mode = Navigation.Mode.Explicit;
            nav.selectOnUp = i > 0 ? lignes[i - 1] : retablir;
            nav.selectOnDown = i + 1 < lignes.Count ? lignes[i + 1] : retour;
            lignes[i].navigation = nav;
        }
        var derniere = lignes[lignes.Count - 1];
        Relier(retablir, derniere, lignes[0], retour, retour);
        Relier(retour, derniere, lignes[0], retablir, retablir);
        UnityEngine.EventSystems.EventSystem.current.SetSelectedGameObject(lignes[0].gameObject);
    }

    RectTransform Colonne(string nom, string titre, float x)
    {
        var colonne = Zone(contenu, nom, new(x, .2f), new(x + .27f, .72f));
        Texte(colonne, "Titre", titre, 15, new(0, .93f), new(1, 1), Laiton).characterSpacing = 20;
        Filet(colonne, new(0, .925f), new(1, .925f));
        return colonne;
    }

    Slider Choix(RectTransform colonne, string nom, string libelle, int rang, string[] valeurs, int valeur, Action<int> changer) =>
        Reglage(colonne, nom, libelle, rang, 0, valeurs.Length - 1, true, valeur, v => valeurs[Mathf.Clamp(Mathf.RoundToInt(v), 0, valeurs.Length - 1)],
            v => changer(Mathf.RoundToInt(v)));

    // Ligne de réglage : libellé et valeur au-dessus, curseur en dessous.
    Slider Reglage(RectTransform colonne, string nom, string libelle, int rang, float min, float max, bool entiers, float valeur,
        Func<float, string> afficher, Action<float> changer)
    {
        float haut = .88f - rang * (colonne.name == "ColonneSons" ? .176f : .215f);   // 5 lignes dans la colonne des sons
        Texte(colonne, nom + "Libelle", libelle, 21, new(0, haut - .085f), new(.68f, haut), Ivoire);
        var texteValeur = Texte(colonne, nom + "Valeur", afficher(valeur), 21, new(.6f, haut - .085f), new(1, haut), Ivoire, false, TextAlignmentOptions.MidlineRight);
        texteValeur.fontStyle = FontStyles.Bold;

        var zone = Zone(colonne, nom, new(0, haut - .175f), new(1, haut - .095f));
        var cible = zone.gameObject.AddComponent<Image>(); cible.color = Color.clear;
        var piste = Zone(zone, "Piste", new(0, .38f), new(1, .62f)).gameObject.AddComponent<FormeInterface>();
        piste.color = new Color(Ivoire.r, Ivoire.g, Ivoire.b, .2f); piste.raycastTarget = false;
        var aire = Zone(zone, "Aire", new(0, .38f), new(1, .62f));
        var plein = Zone(aire, "Rempli", Vector2.zero, Vector2.one);
        var rempli = plein.gameObject.AddComponent<FormeInterface>(); rempli.color = Laiton; rempli.raycastTarget = false;
        var glissiere = Zone(zone, "Glissiere", Vector2.zero, Vector2.one);
        glissiere.offsetMin = new Vector2(18, 0); glissiere.offsetMax = new Vector2(-18, 0);
        var poignee = Zone(glissiere, "Poignee", Vector2.zero, Vector2.one);
        var ratio = poignee.gameObject.AddComponent<AspectRatioFitter>(); ratio.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth; ratio.aspectRatio = 1;
        var disque = poignee.gameObject.AddComponent<DisqueInterface>(); disque.color = Color.white;

        var curseur = zone.gameObject.AddComponent<Slider>();
        curseur.fillRect = plein; curseur.handleRect = poignee; curseur.targetGraphic = disque;
        curseur.direction = Slider.Direction.LeftToRight; curseur.minValue = min; curseur.maxValue = max; curseur.wholeNumbers = entiers;
        var c = curseur.colors; c.normalColor = Ivoire; c.highlightedColor = Color.white; c.selectedColor = Peinture; c.pressedColor = Peinture; c.fadeDuration = .1f;
        curseur.colors = c;
        curseur.SetValueWithoutNotify(valeur);
        curseur.onValueChanged.AddListener(v => { texteValeur.text = afficher(v); changer(v); });
        return curseur;
    }
}

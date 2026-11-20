using System;
using System.Collections.Generic;
using UnityEngine;

// Règles d'un match, sans moteur ni réseau : ni position, ni physique, ni hasard caché.
// Mêmes règles et mêmes noms d'événements que le serveur (serveur/PROTOCOLE.md, src/regles.rs).
// L'hôte (PartieBots en local, plus tard un serveur faisant autorité) lui transmet les touches
// constatées et applique en retour les événements produits (réapparition, élimination, fin).
[Serializable]
public class ReglesMatch
{
    public int vies = 3;
    // Points nécessaires pour gagner : floor(vies × joueurs × ratio).
    public float ratioCible = .5f;
    public int pointsParTouche = 1;
    public bool eliminationSansVie = true;
    public bool victoireAuxPoints = true;
    public bool dernierSurvivantGagne = true;
    // Protection après chaque apparition, en secondes de match (invulnerabilite_ms du serveur).
    public float immunite = 1.5f;
    // Au-delà, victoire au meilleur score (égalité : pas de gagnant). 0 : sans limite.
    public float dureeMax = 0;   // 0 : sans limite de temps (demande du 19/11)

    public int Cible(int joueurs) => Mathf.FloorToInt(vies * joueurs * ratioCible);
}

[Serializable]
public class JoueurMatch
{
    public int id;
    public string nom;
    public int couleur;
    public bool bot;
    public int vies;
    public int points;
    public bool elimine;
    public float immuniteJusqua;
    public int rang;
}

public enum TypeEvenementMatch { Debut, Touche, Reapparition, Elimination, Fin }

public struct EvenementMatch
{
    public TypeEvenementMatch type;
    public int joueur;      // touché, réapparu, éliminé ou gagnant
    public int auteur;      // tireur pour une touche, -1 sinon
    public int point;       // index du point de réapparition, -1 sinon
    public float temps;
    // Type du message serveur correspondant (PROTOCOLE.md) ; la réapparition y est le champ spawn de touche.
    public string Code => type switch
    {
        TypeEvenementMatch.Debut => "debut", TypeEvenementMatch.Touche or TypeEvenementMatch.Reapparition => "touche",
        TypeEvenementMatch.Elimination => "elimine", _ => "fin"
    };
}

public class MatchPaintball
{
    public readonly ReglesMatch regles;
    public readonly List<JoueurMatch> joueurs = new();
    public int Cible { get; private set; }
    public bool Termine { get; private set; }
    public int Gagnant { get; private set; } = -1;
    // Raison de fin, comme le serveur : points, dernier survivant, aucun survivant, temps.
    public string Raison { get; private set; } = "";
    public float Temps { get; private set; }
    public event Action<EvenementMatch> Evenement;

    public MatchPaintball(ReglesMatch regles = null) { this.regles = regles ?? new ReglesMatch(); }

    public JoueurMatch Ajouter(int id, string nom, int couleur, bool bot)
    {
        var j = new JoueurMatch { id = id, nom = nom, couleur = couleur, bot = bot, vies = regles.vies };
        joueurs.Add(j);
        return j;
    }

    public JoueurMatch Joueur(int id) { foreach (var j in joueurs) if (j.id == id) return j; return null; }

    public void Demarrer()
    {
        Temps = 0; Termine = false; Gagnant = -1; Raison = "";
        foreach (var j in joueurs) { j.vies = regles.vies; j.points = 0; j.elimine = false; j.immuniteJusqua = regles.immunite; j.rang = 0; }
        Cible = regles.Cible(joueurs.Count);
        Emettre(new EvenementMatch { type = TypeEvenementMatch.Debut, joueur = -1, auteur = -1, point = -1 });
    }

    public void Avancer(float dt)
    {
        if (Termine) return;
        Temps += dt;
        if (regles.dureeMax > 0 && Temps >= regles.dureeMax)
        {
            JoueurMatch meilleur = null; bool egalite = false;
            foreach (var j in joueurs)
                if (meilleur == null || j.points > meilleur.points) { meilleur = j; egalite = false; }
                else if (j.points == meilleur.points) egalite = true;
            Terminer(egalite ? null : meilleur, "temps");
        }
    }

    public bool Touchable(int id)
    {
        var j = Joueur(id);
        return j != null && !Termine && !j.elimine && Temps >= j.immuniteJusqua;
    }

    // Touche constatée par l'hôte. Renvoie vrai si elle compte. pointReapparition : choisi par
    // l'hôte parmi ses points sûrs (le match ne connaît pas la carte).
    public bool Toucher(int tireur, int touche, int pointReapparition)
    {
        var a = Joueur(tireur); var c = Joueur(touche);
        if (a == null || c == null || tireur == touche || a.elimine || !Touchable(touche)) return false;
        a.points += regles.pointsParTouche;
        c.vies--;
        Emettre(new EvenementMatch { type = TypeEvenementMatch.Touche, joueur = touche, auteur = tireur, point = -1 });
        if (c.vies <= 0 && regles.eliminationSansVie)
        {
            c.elimine = true;
            Emettre(new EvenementMatch { type = TypeEvenementMatch.Elimination, joueur = touche, auteur = tireur, point = -1 });
        }
        else
        {
            c.immuniteJusqua = Temps + regles.immunite;
            Emettre(new EvenementMatch { type = TypeEvenementMatch.Reapparition, joueur = touche, auteur = -1, point = pointReapparition });
        }
        Verifier();
        return true;
    }

    // Partie en ligne : le serveur fait autorité. Ces méthodes recopient ses décisions (cible, touches,
    // éliminations, fin) et émettent les mêmes événements, sans appliquer les règles localement.
    public void DemarrerMiroir(int cible)
    {
        Demarrer();
        Cible = cible;
    }

    public void ImposerTouche(int tireur, int touche, int viesCible, int pointsTireur, bool elimine)
    {
        var a = Joueur(tireur); var c = Joueur(touche);
        if (c == null || Termine) return;
        if (a != null) a.points = pointsTireur;
        c.vies = viesCible;
        Emettre(new EvenementMatch { type = TypeEvenementMatch.Touche, joueur = touche, auteur = tireur, point = -1 });
        if (elimine)
        {
            c.elimine = true;
            Emettre(new EvenementMatch { type = TypeEvenementMatch.Elimination, joueur = touche, auteur = tireur, point = -1 });
        }
        else
        {
            c.immuniteJusqua = Temps + regles.immunite;
            Emettre(new EvenementMatch { type = TypeEvenementMatch.Reapparition, joueur = touche, auteur = -1, point = -1 });
        }
    }

    public void ImposerCible(int cible) { if (cible > 0) Cible = cible; }

    public void ImposerElimination(int id)
    {
        var j = Joueur(id);
        if (j == null || j.elimine || Termine) return;
        j.elimine = true;
        Emettre(new EvenementMatch { type = TypeEvenementMatch.Elimination, joueur = id, auteur = -1, point = -1 });
    }

    public void ImposerFin(int gagnant, string raison)
    {
        if (!Termine) Terminer(Joueur(gagnant), raison);
    }

    // Abandon (déconnexion) : traité comme une élimination sans auteur.
    public void Retirer(int id)
    {
        var j = Joueur(id);
        if (j == null || j.elimine || Termine) return;
        j.elimine = true; j.vies = 0;
        Emettre(new EvenementMatch { type = TypeEvenementMatch.Elimination, joueur = id, auteur = -1, point = -1 });
        Verifier();
    }

    void Verifier()
    {
        if (Termine) return;
        if (regles.victoireAuxPoints)
            foreach (var j in joueurs) if (!j.elimine && j.points >= Cible) { Terminer(j, "points"); return; }
        if (!regles.dernierSurvivantGagne) return;
        int restants = 0; JoueurMatch dernier = null;
        foreach (var j in joueurs) if (!j.elimine) { restants++; dernier = j; }
        if (restants == 1) Terminer(dernier, "dernier survivant");
        else if (restants == 0) Terminer(null, "aucun survivant");
    }

    void Terminer(JoueurMatch gagnant, string raison)
    {
        Termine = true; Gagnant = gagnant != null ? gagnant.id : -1; Raison = raison;
        var classement = Classement();
        for (int i = 0; i < classement.Count; i++) classement[i].rang = i + 1;
        Emettre(new EvenementMatch { type = TypeEvenementMatch.Fin, joueur = Gagnant, auteur = -1, point = -1 });
    }

    // Gagnant d'abord, puis points, puis vies restantes.
    public List<JoueurMatch> Classement()
    {
        var l = new List<JoueurMatch>(joueurs);
        l.Sort((x, y) => x.id == Gagnant ? -1 : y.id == Gagnant ? 1 : y.points != x.points ? y.points - x.points : y.vies - x.vies);
        return l;
    }

    void Emettre(EvenementMatch e)
    {
        e.temps = Temps;
        Evenement?.Invoke(e);
    }
}

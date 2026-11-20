using UnityEngine;

// Repère cliquable en jeu ; son panneau explique le lieu et donne sa référence.
public sealed class PointHistorique : MonoBehaviour
{
    [SerializeField] string titre;
    [SerializeField, TextArea(3, 8)] string explication;
    [SerializeField] string source;
    public string Titre => titre;
    public string Explication => explication;
    public string Source => source;

    public void Initialiser(string t, string e, string s)
    {
        titre = t;
        explication = e;
        source = s;
    }
}

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

// Contrôle reproductible dans le player : -verification <rapport.json>.
public class VerificationParcours : MonoBehaviour
{
    [Serializable] class Controle { public string nom; public bool reussi; public string detail; }
    [Serializable] class Rapport { public bool reussi; public List<Controle> controles = new(); }
    readonly Rapport rapport = new();
    string destination;
    Transform racine;
    CharacterController joueur;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Demarrer()
    {
        string[] args = Environment.GetCommandLineArgs();
        int i = Array.IndexOf(args, "-verification");
        if (i >= 0 && i + 1 < args.Length)
            new GameObject("VerificationParcours").AddComponent<VerificationParcours>().destination = Path.GetFullPath(args[i + 1]);
    }

    Vector3 Point(float x, float y, float z) => racine.TransformPoint(new Vector3(-x, z, -y));
    void Noter(string nom, bool reussi, string detail)
    {
        rapport.controles.Add(new Controle { nom = nom, reussi = reussi, detail = detail });
        Debug.Log($"VERIFICATION {nom} : {reussi} {detail}");
    }
    void Placer(Vector3 point)
    {
        joueur.enabled = false;
        joueur.transform.position = point + Vector3.up * 0.06f;
        joueur.enabled = true;
        Physics.SyncTransforms();
    }
    IEnumerator Marcher(string nom, Vector3 cible, float secondes = 8f)
    {
        float fin = Time.realtimeSinceStartup + secondes;
        while (Time.realtimeSinceStartup < fin)
        {
            Vector3 delta = cible - joueur.transform.position;
            delta.y = 0f;
            if (delta.magnitude < 0.12f) break;
            joueur.Move((delta.normalized * 2.2f + Vector3.down * 2f) * Time.fixedDeltaTime);
            yield return new WaitForFixedUpdate();
        }
        for (int i = 0; i < 10; i++) { joueur.Move(Vector3.down * 2f * Time.fixedDeltaTime); yield return new WaitForFixedUpdate(); }
        float erreur = Vector3.Distance(joueur.transform.position, cible);
        Vector3 direction = cible - joueur.transform.position;
        direction.y = 0f;
        string obstacles = string.Join(",", Physics.CapsuleCastAll(joueur.transform.position + Vector3.up * 0.4f,
            joueur.transform.position + Vector3.up * 1.45f, 0.25f, direction.normalized, 0.8f)
            .Where(h => h.collider != joueur).Select(h => h.collider.name).Distinct());
        Noter(nom, erreur < 0.3f, $"écart {erreur:F2} m, position {joueur.transform.position}, obstacles {obstacles}");
    }

    IEnumerator Start()
    {
        yield return new WaitForSeconds(1f);
        var explorateur = FindAnyObjectByType<Explorateur>();
        explorateur.enabled = false;
        joueur = explorateur.GetComponent<CharacterController>();
        racine = GameObject.Find("Chateau").transform;
        foreach (string composant in new[] { "piece_chambres", "piece_circulations", "piece_reception", "piece_salons" })
            Noter("import_" + composant, racine.GetComponentsInChildren<Transform>().Any(t => t.name == composant), composant);

        // L'entrée doit bloquer quand elle est fermée, puis laisser passer après ouverture.
        Placer(Point(0f, -9.35f, 0f));
        var vantaux = FindObjectsByType<Porte>().Where(p => p.name.StartsWith("porte_entree_")).ToArray();
        Vector3 direction = (Point(0f, -6.75f, 1.2f) - Point(0f, -9.35f, 1.2f)).normalized;
        bool trouve = Physics.Raycast(joueur.transform.position + Vector3.up * 1.2f, direction, out var impact, 2f)
            && impact.collider.GetComponentInParent<Porte>() != null;
        Noter("entree_interaction", trouve && vantaux.Length == 2, $"{vantaux.Length} vantaux ; cible {impact.collider?.name}");
        foreach (var porte in vantaux) porte.Basculer(joueur.transform.position);
        yield return new WaitForSeconds(1f);
        Physics.SyncTransforms();
        yield return Marcher("entree_passage", Point(0f, -7.2f, 0f));

        // Volée centrale, repos, retour est et galerie : le même CharacterController que le jeu.
        Placer(Point(0.5f, -4.0f, 0f));
        yield return Marcher("escalier_central", Point(0.5f, 1.9f, 3.4f));
        yield return Marcher("repos", Point(2.3f, 1.9f, 3.4f));
        yield return Marcher("escalier_retour", Point(2.3f, -2.2f, 5.35f));
        yield return Marcher("galerie", Point(4.5f, -2.3f, 5.35f));

        rapport.reussi = rapport.controles.All(c => c.reussi);
        Directory.CreateDirectory(Path.GetDirectoryName(destination));
        File.WriteAllText(destination, JsonUtility.ToJson(rapport, true));
        Application.Quit(rapport.reussi ? 0 : 1);
    }
}

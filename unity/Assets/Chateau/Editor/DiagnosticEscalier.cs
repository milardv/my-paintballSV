using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class DiagnosticEscalier
{
    public static void Sonder()
    {
        EditorSceneManager.OpenScene("Assets/Scenes/Chateau.unity");
        Physics.SyncTransforms();
        var sb = new StringBuilder();
        var bloqueurs = new Dictionary<string, int>();
        for (float z = 4.2f; z >= -4.2f; z -= .2f)
        {
            sb.Append($"{z,5:F1} ");
            for (float x = -4.2f; x <= 4.21f; x += .2f)
            {
                var bas = new Vector3(x, .05f + .3f, z); var haut = new Vector3(x, 1.75f - .3f, z);
                var cols = Physics.OverlapCapsule(bas, haut, .28f, ~(1 << 2), QueryTriggerInteraction.Ignore);
                sb.Append(cols.Length == 0 ? '.' : '#');
                foreach (var c in cols) { bloqueurs.TryGetValue(c.name, out int n); bloqueurs[c.name] = n + 1; }
            }
            sb.Append('\n');
        }
        foreach (var q in new[] { new Vector2(-2.5f, 2f), new Vector2(-2f, 1.9f), new Vector2(-3f, 1.7f), new Vector2(-1.6f, 2.2f), new Vector2(-2.8f, 1.3f), new Vector2(2.5f, 2f), new Vector2(3f, 1.6f), new Vector2(1.7f, 2.1f) })
        {
            var c = new Vector3(q.x, 0, q.y);
            var cols = Physics.OverlapCapsule(c + Vector3.up * .7f, c + Vector3.up * 1.37f, .38f, ~(1 << 2), QueryTriggerInteraction.Ignore);
            Debug.Log($"ESCALIER POINT {q} : " + string.Join(", ", cols.Select(k => k.name + " " + k.bounds.center.ToString("F2") + " ext " + k.bounds.extents.ToString("F2"))));
        }
        // Accessibilité depuis le vestibule, capsule du joueur (rayon 0,3 + peau 0,08), sol plat.
        const float pas = .1f; int nx = 120, nz = 200; float x0 = -6, z0 = -9;
        var libre = new bool[nx, nz]; var vu = new bool[nx, nz];
        for (int i = 0; i < nx; i++) for (int k = 0; k < nz; k++)
        {
            var c = new Vector3(x0 + i * pas, 0, z0 + k * pas);
            libre[i, k] = !Physics.CheckCapsule(c + Vector3.up * (.38f + .32f), c + Vector3.up * (1.75f - .38f), .38f, ~(1 << 2), QueryTriggerInteraction.Ignore);
        }
        var file = new Queue<(int, int)>(); int si = 60, sk = 45; vu[si, sk] = true; file.Enqueue((si, sk));
        while (file.Count > 0) { var (i, k) = file.Dequeue(); foreach (var (di, dk) in new[] { (1, 0), (-1, 0), (0, 1), (0, -1) }) { int a = i + di, b = k + dk; if (a < 0 || b < 0 || a >= nx || b >= nz || vu[a, b] || !libre[a, b]) continue; vu[a, b] = true; file.Enqueue((a, b)); } }
        var acc = new StringBuilder();
        for (int k = nz - 1; k >= 0; k -= 2) { acc.Append($"{z0 + k * pas,5:F1} "); for (int i = 0; i < nx; i += 1) acc.Append(vu[i, k] ? 'o' : libre[i, k] ? '.' : '#'); acc.Append('\n'); }
        Debug.Log("ESCALIER ACCES x -6..6, o = accessible depuis le vestibule\n" + acc);
        Debug.Log("ESCALIER CARTE x de -4.2 a 4.2 (gauche->droite), z de 4.2 a -4.2\n" + sb);
        Debug.Log("ESCALIER BLOQUEURS " + string.Join(" | ", bloqueurs.OrderByDescending(k => k.Value).Select(k => k.Key + ":" + k.Value)));
        foreach (var n in new[] { "escalier_volee_centrale", "escalier_volee_retour_est", "escalier_volee_retour_ouest", "escalier_repos", "sol_escalier", "mur_vestibule_escalier", "escalier_limons", "escalier_pampas" })
        {
            var go = GameObject.Find(n);
            if (go == null) { Debug.Log("ESCALIER OBJET " + n + " absent"); continue; }
            var r = go.GetComponent<Renderer>(); var c = go.GetComponent<Collider>();
            Debug.Log($"ESCALIER OBJET {n} rendu {(r ? r.bounds.ToString() : "-")} collider {(c ? c.GetType().Name + " " + c.bounds : "-")}");
        }
        EditorApplication.Exit(0);
    }
}

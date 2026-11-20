using System;
using System.IO;
using UnityEngine;

public static class VerificationBalistique
{
    static Vector3 Simuler(float dt, float duree, out Vector3 vitesse)
    {
        Vector3 p=Vector3.zero;vitesse=Vector3.forward*BalistiquePaintball.VitesseInitiale;
        for(int i=0;i<Mathf.RoundToInt(duree/dt);i++) BalistiquePaintball.Avancer(ref p,ref vitesse,dt);
        return p;
    }
    public static void Verifier()
    {
        Vector3 p=Simuler(1f/240,1,out var v);
        Vector3 reference=Simuler(1f/1920,1,out _);
        if(p.y>=0 || p.y<=-4.905f || p.z>=85.344f || v.z<=0 || v.z>=85.344f)
            throw new Exception("Balistique : gravite ou trainee incorrecte "+p);
        float erreur=Vector3.Distance(p,reference);
        if(erreur>.005f) throw new Exception("Balistique : convergence insuffisante "+erreur);
        // A .01 m wall is far thinner than a 240 Hz travel segment. The sweep must still hit.
        var mur=GameObject.CreatePrimitive(PrimitiveType.Cube);mur.name="VerificationMurFin";
        mur.transform.position=new Vector3(1000,1000,1000.15f);mur.transform.localScale=new Vector3(2,2,.01f);
        Physics.SyncTransforms();
        bool collision=Physics.SphereCast(new Vector3(1000,1000,1000),BalistiquePaintball.Diametre*.5f,Vector3.forward,out var hit,85.344f/240,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Ignore);
        UnityEngine.Object.DestroyImmediate(mur);
        if(!collision) throw new Exception("Balistique : mur fin traverse");
        File.WriteAllText("../travail/verification-balistique.json",JsonUtility.ToJson(new Rapport {distanceUneSeconde=p.z,chuteUneSeconde=-p.y,vitesseUneSeconde=v.magnitude,erreurMetres=erreur,murFin=collision},true));
        Debug.Log($"PAINTBALL BALISTIQUE OK distance={p.z:F3} chute={-p.y:F3} erreur={erreur:F6} m murFin={collision}");
    }
    [Serializable] class Rapport {public float distanceUneSeconde,chuteUneSeconde,vitesseUneSeconde,erreurMetres;public bool murFin;}
}

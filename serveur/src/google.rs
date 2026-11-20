// Vérification d'un ID token OpenID Connect émis par Google (RS256), sans appel réseau :
// les clés publiques (JWKS) sont fournies par l'appelant.
use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64, Engine};
use rsa::pkcs1v15::{Signature as SignatureRsa, VerifyingKey};
use rsa::signature::Verifier;
use rsa::{BigUint, RsaPublicKey};
use serde::Deserialize;
use serde_json::Value;
use sha2::Sha256;

pub const URL_JWKS: &str = "https://www.googleapis.com/oauth2/v3/certs";
pub const URL_AUTORISATION: &str = "https://accounts.google.com/o/oauth2/v2/auth";
pub const URL_JETON: &str = "https://oauth2.googleapis.com/token";
const EMETTEURS: [&str; 2] = ["https://accounts.google.com", "accounts.google.com"];
/// Tolérance d'horloge, en secondes.
const DERIVE: u64 = 60;

#[derive(Deserialize)]
pub struct Jwk {
    pub kid: String,
    pub kty: String,
    pub n: String,
    pub e: String,
}

#[derive(Deserialize)]
pub struct Jwks {
    pub keys: Vec<Jwk>,
}

#[derive(Debug, PartialEq)]
pub struct Identite {
    pub sub: String,
    pub email: String,
    pub nom: Option<String>,
}

#[derive(Debug, PartialEq)]
pub enum ErreurJeton {
    Format,
    Algorithme,
    CleInconnue,
    Signature,
    Emetteur,
    Audience,
    Expire,
    Nonce,
    EmailNonVerifie,
}

pub fn verifier_id_token(
    jeton: &str,
    jwks: &Jwks,
    client_id: &str,
    nonce: &str,
    maintenant_s: u64,
) -> Result<Identite, ErreurJeton> {
    use ErreurJeton::*;
    let mut parties = jeton.split('.');
    let (Some(h), Some(c), Some(s), None) = (parties.next(), parties.next(), parties.next(), parties.next()) else {
        return Err(Format);
    };
    let entete: Value = serde_json::from_slice(&B64.decode(h).map_err(|_| Format)?).map_err(|_| Format)?;
    if entete["alg"] != "RS256" {
        return Err(Algorithme);
    }
    let kid = entete["kid"].as_str().ok_or(Format)?;
    let jwk = jwks.keys.iter().find(|k| k.kid == kid && k.kty == "RSA").ok_or(CleInconnue)?;
    let n = BigUint::from_bytes_be(&B64.decode(&jwk.n).map_err(|_| CleInconnue)?);
    let e = BigUint::from_bytes_be(&B64.decode(&jwk.e).map_err(|_| CleInconnue)?);
    let cle = RsaPublicKey::new(n, e).map_err(|_| CleInconnue)?;
    let sig = SignatureRsa::try_from(B64.decode(s).map_err(|_| Format)?.as_slice()).map_err(|_| Signature)?;
    VerifyingKey::<Sha256>::new(cle)
        .verify(format!("{h}.{c}").as_bytes(), &sig)
        .map_err(|_| Signature)?;

    let r: Value = serde_json::from_slice(&B64.decode(c).map_err(|_| Format)?).map_err(|_| Format)?;
    if !EMETTEURS.contains(&r["iss"].as_str().unwrap_or("")) {
        return Err(Emetteur);
    }
    let aud_ok = match &r["aud"] {
        Value::String(a) => a == client_id,
        Value::Array(a) => a.iter().any(|x| x == client_id),
        _ => false,
    };
    if !aud_ok {
        return Err(Audience);
    }
    let exp = r["exp"].as_u64().ok_or(Format)?;
    if exp + DERIVE < maintenant_s {
        return Err(Expire);
    }
    if r["iat"].as_u64().is_some_and(|iat| iat > maintenant_s + DERIVE) {
        return Err(Expire);
    }
    if r["nonce"].as_str() != Some(nonce) {
        return Err(Nonce);
    }
    let verifie = match &r["email_verified"] {
        Value::Bool(b) => *b,
        Value::String(s) => s == "true",
        _ => false,
    };
    let email = r["email"].as_str().ok_or(EmailNonVerifie)?;
    if !verifie {
        return Err(EmailNonVerifie);
    }
    Ok(Identite {
        sub: r["sub"].as_str().ok_or(Format)?.to_string(),
        email: email.to_string(),
        nom: r["name"].as_str().or(r["given_name"].as_str()).map(str::to_string),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use rsa::pkcs1v15::SigningKey;
    use rsa::signature::{SignatureEncoding, Signer};
    use rsa::traits::PublicKeyParts;
    use rsa::RsaPrivateKey;
    use serde_json::json;
    use std::sync::OnceLock;

    const CLIENT: &str = "client.apps.googleusercontent.com";
    const T: u64 = 1_800_000_000;

    fn cle() -> &'static RsaPrivateKey {
        static CLE: OnceLock<RsaPrivateKey> = OnceLock::new();
        CLE.get_or_init(|| RsaPrivateKey::new(&mut rand::thread_rng(), 2048).unwrap())
    }

    fn jwks() -> Jwks {
        let p = cle().to_public_key();
        Jwks {
            keys: vec![Jwk {
                kid: "k1".into(),
                kty: "RSA".into(),
                n: B64.encode(p.n().to_bytes_be()),
                e: B64.encode(p.e().to_bytes_be()),
            }],
        }
    }

    fn jeton(entete: Value, corps: Value) -> String {
        let h = B64.encode(entete.to_string());
        let c = B64.encode(corps.to_string());
        let sig = SigningKey::<Sha256>::new(cle().clone()).sign(format!("{h}.{c}").as_bytes());
        format!("{h}.{c}.{}", B64.encode(sig.to_bytes()))
    }

    fn corps() -> Value {
        json!({"iss":"https://accounts.google.com","aud":CLIENT,"sub":"123","email":"Val@Gmail.com",
               "email_verified":true,"exp":T+3600,"iat":T,"nonce":"n1","name":"Val"})
    }

    fn entete() -> Value {
        json!({"alg":"RS256","kid":"k1","typ":"JWT"})
    }

    fn avec(cle_: &str, v: Value) -> Value {
        let mut c = corps();
        c[cle_] = v;
        c
    }

    #[test]
    fn jeton_valide() {
        let id = verifier_id_token(&jeton(entete(), corps()), &jwks(), CLIENT, "n1", T).unwrap();
        assert_eq!(id, Identite { sub: "123".into(), email: "Val@Gmail.com".into(), nom: Some("Val".into()) });
    }

    #[test]
    fn refus() {
        use ErreurJeton::*;
        let v = |e: Value, c: Value| verifier_id_token(&jeton(e, c), &jwks(), CLIENT, "n1", T).unwrap_err();
        assert_eq!(v(entete(), avec("aud", json!("autre"))), Audience);
        assert_eq!(v(entete(), avec("iss", json!("https://evil.example"))), Emetteur);
        assert_eq!(v(entete(), avec("exp", json!(T - 3600))), Expire);
        assert_eq!(v(entete(), avec("nonce", json!("n2"))), Nonce);
        assert_eq!(v(entete(), avec("email_verified", json!(false))), EmailNonVerifie);
        assert_eq!(v(json!({"alg":"none","kid":"k1"}), corps()), Algorithme);
        assert_eq!(v(json!({"alg":"HS256","kid":"k1"}), corps()), Algorithme);
        assert_eq!(v(json!({"alg":"RS256","kid":"k9"}), corps()), CleInconnue);
    }

    #[test]
    fn signature_falsifiee() {
        let j = jeton(entete(), corps());
        let mut p: Vec<&str> = j.split('.').collect();
        let autre = B64.encode(avec("email", json!("pirate@gmail.com")).to_string());
        p[1] = &autre;
        assert_eq!(
            verifier_id_token(&p.join("."), &jwks(), CLIENT, "n1", T).unwrap_err(),
            ErreurJeton::Signature
        );
        assert_eq!(verifier_id_token("a.b", &jwks(), CLIENT, "n1", T).unwrap_err(), ErreurJeton::Format);
    }
}

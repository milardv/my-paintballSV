// Jetons signés HMAC-SHA256 : base64url(json) "." base64url(mac).
// L'usage (session, oauth, ticket) entre dans le MAC : un jeton ne sert qu'à un usage.
use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64, Engine};
use hmac::{Hmac, Mac};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

fn mac(cle: &[u8], usage: &str, charge: &str) -> HmacSha256 {
    let mut m = HmacSha256::new_from_slice(cle).expect("toute taille de clé convient");
    m.update(usage.as_bytes());
    m.update(b".");
    m.update(charge.as_bytes());
    m
}

pub fn signer<T: Serialize>(cle: &[u8], usage: &str, contenu: &T) -> String {
    let charge = B64.encode(serde_json::to_vec(contenu).expect("sérialisable"));
    let sig = mac(cle, usage, &charge).finalize().into_bytes();
    format!("{charge}.{}", B64.encode(sig))
}

pub fn verifier<T: DeserializeOwned>(cle: &[u8], usage: &str, jeton: &str) -> Option<T> {
    if jeton.len() > 4096 {
        return None;
    }
    let (charge, sig) = jeton.split_once('.')?;
    let sig = B64.decode(sig).ok()?;
    mac(cle, usage, charge).verify_slice(&sig).ok()?;
    serde_json::from_slice(&B64.decode(charge).ok()?).ok()
}

/// Jeton CSRF lié à la session : HMAC de l'identifiant de session.
pub fn csrf(cle: &[u8], sid: &str) -> String {
    B64.encode(mac(cle, "csrf", sid).finalize().into_bytes())
}

pub fn csrf_valide(cle: &[u8], sid: &str, recu: &str) -> bool {
    match B64.decode(recu) {
        Ok(sig) => mac(cle, "csrf", sid).verify_slice(&sig).is_ok(),
        Err(_) => false,
    }
}

/// Défi PKCE S256 dérivé du vérificateur.
pub fn defi_pkce(verificateur: &str) -> String {
    use sha2::Digest;
    B64.encode(Sha256::digest(verificateur.as_bytes()))
}

pub fn aleatoire_b64(octets: &[u8]) -> String {
    B64.encode(octets)
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct Session {
    pub sid: String,
    pub email: String,
    pub exp: u64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EtatOAuth {
    pub state: String,
    pub nonce: String,
    pub verif: String,
    pub retour: String,
    /// Clé du lien de salon par lequel l'utilisateur est arrivé.
    pub lien: Option<String>,
    pub exp: u64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct Ticket {
    pub email: String,
    /// Salon.
    pub s: String,
    pub exp: u64,
}

pub const USAGE_SESSION: &str = "session";
pub const USAGE_OAUTH: &str = "oauth";
pub const USAGE_TICKET: &str = "ticket";

#[cfg(test)]
mod tests {
    use super::*;

    const CLE: &[u8] = b"cle-de-test-suffisamment-longue-0123456789";

    fn session() -> Session {
        Session { sid: "abc".into(), email: "a@b.fr".into(), exp: 99 }
    }

    #[test]
    fn aller_retour() {
        let j = signer(CLE, USAGE_SESSION, &session());
        assert_eq!(verifier::<Session>(CLE, USAGE_SESSION, &j), Some(session()));
    }

    #[test]
    fn mauvaise_cle_ou_usage() {
        let j = signer(CLE, USAGE_SESSION, &session());
        assert!(verifier::<Session>(b"autre", USAGE_SESSION, &j).is_none());
        assert!(verifier::<Session>(CLE, USAGE_TICKET, &j).is_none());
    }

    #[test]
    fn charge_modifiee() {
        let j = signer(CLE, USAGE_SESSION, &session());
        let (_, sig) = j.split_once('.').unwrap();
        let faux = Session { email: "admin@b.fr".into(), ..session() };
        let charge = B64.encode(serde_json::to_vec(&faux).unwrap());
        assert!(verifier::<Session>(CLE, USAGE_SESSION, &format!("{charge}.{sig}")).is_none());
        assert!(verifier::<Session>(CLE, USAGE_SESSION, "n'importe.quoi").is_none());
        assert!(verifier::<Session>(CLE, USAGE_SESSION, "").is_none());
    }

    #[test]
    fn csrf_lie_a_la_session() {
        let c = csrf(CLE, "s1");
        assert!(csrf_valide(CLE, "s1", &c));
        assert!(!csrf_valide(CLE, "s2", &c));
        assert!(!csrf_valide(CLE, "s1", ""));
    }

    #[test]
    fn pkce_rfc7636() {
        // Exemple de l'annexe B de la RFC 7636.
        assert_eq!(
            defi_pkce("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
            "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        );
    }
}

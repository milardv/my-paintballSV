// Worker : connexion Google, liste autorisée, salons (lien permanent), tickets WebSocket, fichiers du jeu.
use crate::acces::{self, Droit, Situation};
use crate::{google, jeton, qr, regles};
use serde::Deserialize;
use serde_json::{json, Value};
use worker::wasm_bindgen::JsValue;
use worker::*;

const COOKIE_SESSION: &str = "__Host-psv";
const COOKIE_OAUTH: &str = "__Host-psv-oauth";
const DUREE_SESSION_S: u64 = 14 * 24 * 3600;
const DUREE_TICKET_S: u64 = 60;

struct Config {
    cle: Vec<u8>,
    origine: String,
    admin: String,
    client_id: String,
    mode_dev: bool,
}

struct Utilisateur {
    sid: String,
    email: String,
    nom: String,
    droit: Droit,
}

impl Utilisateur {
    fn admin(&self) -> bool {
        self.droit == Droit::Admin
    }
}

fn texte_env(env: &Env, nom: &str) -> Option<String> {
    env.secret(nom).or_else(|_| env.var(nom)).ok().map(|v| v.to_string()).filter(|v| !v.is_empty())
}

fn config(env: &Env) -> Result<Config> {
    let cle = texte_env(env, "CLE_SESSION").ok_or("CLE_SESSION manquante")?;
    if cle.len() < 32 {
        return Err("CLE_SESSION trop courte (32 caractères minimum)".into());
    }
    Ok(Config {
        cle: cle.into_bytes(),
        origine: texte_env(env, "ORIGINE").ok_or("ORIGINE manquante")?.trim_end_matches('/').to_string(),
        admin: texte_env(env, "ADMIN_EMAIL").and_then(|e| acces::normaliser_email(&e)).unwrap_or_default(),
        client_id: texte_env(env, "GOOGLE_CLIENT_ID").unwrap_or_default(),
        mode_dev: texte_env(env, "MODE_DEV").as_deref() == Some("1"),
    })
}

pub fn maintenant_ms() -> u64 {
    Date::now().as_millis()
}

pub fn aleatoire(n: usize) -> Vec<u8> {
    let mut o = vec![0u8; n];
    getrandom::getrandom(&mut o).expect("crypto.getRandomValues");
    o
}

fn identifiant() -> String {
    jeton::aleatoire_b64(&aleatoire(9))
}

// ---------- Réponses ----------

fn entetes_securite(h: &Headers) -> Result<()> {
    h.set("X-Content-Type-Options", "nosniff")?;
    h.set("Referrer-Policy", "same-origin")?;
    h.set("X-Frame-Options", "DENY")?;
    Ok(())
}

fn reponse_json(statut: u16, v: &Value) -> Result<Response> {
    let r = Response::from_json(v)?.with_status(statut);
    r.headers().set("Cache-Control", "no-store")?;
    Ok(r)
}

fn erreur(statut: u16, message: &str) -> Result<Response> {
    reponse_json(statut, &json!({ "erreur": message }))
}

fn echapper(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;").replace('"', "&quot;")
}

fn page(statut: u16, titre: &str, texte: &str) -> Result<Response> {
    let html = format!(
        "<!DOCTYPE html><html lang=\"fr\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\
         <title>{t}</title><body style=\"background:#10251f;color:#f4f0e7;font:18px system-ui;display:grid;place-items:center;min-height:90vh\">\
         <main style=\"max-width:32em;padding:1em\"><h1>{t}</h1><p>{x}</p><p><a style=\"color:#40cee4\" href=\"/\">Accueil</a></p></main>",
        t = echapper(titre),
        x = echapper(texte)
    );
    let r = Response::from_html(html)?.with_status(statut);
    r.headers().set("Cache-Control", "no-store")?;
    Ok(r)
}

/// Page d'entrée (style du panneau en jeu) : bouton vers la connexion Google, retour sur `retour`.
fn page_connexion(statut: u16, titre: &str, texte: &str, bouton: &str, retour: &str) -> Result<Response> {
    let mut cible = Url::parse("https://x/auth/google")?;
    cible.query_pairs_mut().append_pair("retour", retour);
    let lien = format!("/auth/google?{}", cible.query().unwrap_or(""));
    let html = format!(
        "<!DOCTYPE html><html lang=\"fr\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\
         <title>{t}</title><link rel=\"icon\" href=\"data:,\"><body style=\"margin:0;background:#10251f;color:#f4f0e7;font:15px system-ui,sans-serif;\
         display:grid;place-items:center;min-height:100vh\"><main style=\"background:rgba(11,26,21,.82);border:1px solid rgba(173,148,100,.45);\
         border-radius:14px;padding:28px 32px;max-width:26em;margin:16px;box-shadow:0 10px 40px rgba(0,0,0,.45)\">\
         <h1 style=\"font:400 34px Georgia,serif;margin:0 0 6px\">{t}</h1><p style=\"color:#ad9464;margin:0 0 22px\">Paintball au château</p>\
         <p style=\"line-height:1.5\">{x}</p><p style=\"margin:24px 0 0\"><a href=\"{l}\" style=\"display:inline-block;background:#f4f0e7;color:#0b1a15;\
         text-decoration:none;font-weight:600;padding:11px 20px;border-radius:9px\">{b}</a></p></main>",
        t = echapper(titre),
        x = echapper(texte),
        l = echapper(&lien),
        b = echapper(bouton)
    );
    let r = Response::from_html(html)?.with_status(statut);
    r.headers().set("Cache-Control", "no-store")?;
    Ok(r)
}

fn redirection(url: &str, cookies: &[String]) -> Result<Response> {
    let r = Response::empty()?.with_status(303);
    r.headers().set("Location", url)?;
    r.headers().set("Cache-Control", "no-store")?;
    for c in cookies {
        r.headers().append("Set-Cookie", c)?;
    }
    Ok(r)
}

fn cookie(req: &Request, nom: &str) -> Option<String> {
    let brut = req.headers().get("Cookie").ok()??;
    brut.split(';').filter_map(|c| c.trim().split_once('=')).find(|(k, _)| *k == nom).map(|(_, v)| v.to_string())
}

fn poser_cookie(nom: &str, valeur: &str, max_age: u64) -> String {
    format!("{nom}={valeur}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={max_age}")
}

fn ip(req: &Request) -> String {
    req.headers().get("CF-Connecting-IP").ok().flatten().unwrap_or_else(|| "local".into())
}

fn parametre(url: &Url, nom: &str) -> Option<String> {
    url.query_pairs().find(|(k, _)| k == nom).map(|(_, v)| v.into_owned())
}

async fn limite(env: &Env, liaison: &str, cle: String) -> Result<bool> {
    let r: RateLimiter = env.get_binding(liaison)?;
    Ok(r.limit(cle).await?.success)
}

async fn corps_json<T: for<'de> Deserialize<'de>>(req: &mut Request) -> Option<T> {
    let t = req.text().await.ok()?;
    if t.len() > 4096 {
        return None;
    }
    serde_json::from_str(if t.is_empty() { "{}" } else { &t }).ok()
}

fn s(v: &str) -> JsValue {
    JsValue::from_str(v)
}

fn n(v: u64) -> JsValue {
    JsValue::from_f64(v as f64)
}

// ---------- Sessions ----------

async fn utilisateur(req: &Request, env: &Env, cfg: &Config) -> Result<Option<Utilisateur>> {
    let Some(brut) = cookie(req, COOKIE_SESSION) else { return Ok(None) };
    let Some(sess) = jeton::verifier::<jeton::Session>(&cfg.cle, jeton::USAGE_SESSION, &brut) else { return Ok(None) };
    let now = maintenant_ms();
    if sess.exp * 1000 < now {
        return Ok(None);
    }
    #[derive(Deserialize)]
    struct Ligne {
        email: String,
        nom: Option<String>,
        liste: f64,
        membre: f64,
    }
    let ligne: Option<Ligne> = env
        .d1("DB")?
        .prepare(
            "SELECT s.email, c.nom, (a.email IS NOT NULL) AS liste, \
             EXISTS(SELECT 1 FROM membres m WHERE m.email = s.email) AS membre \
             FROM sessions s LEFT JOIN autorises a ON a.email = s.email LEFT JOIN comptes c ON c.email = s.email \
             WHERE s.id = ?1 AND s.revoquee = 0 AND s.expire_le > ?2",
        )
        .bind(&[s(&sess.sid), n(now)])?
        .first(None)
        .await?;
    let Some(l) = ligne else { return Ok(None) };
    let situation = Situation {
        admin_config: l.email == cfg.admin,
        liste: l.liste == 1.0,
        membre_salon: l.membre == 1.0,
        arrive_par_lien: false,
    };
    Ok(acces::droit(situation).map(|droit| Utilisateur {
        sid: sess.sid,
        nom: l.nom.unwrap_or_else(|| if est_invite(&l.email) { "Invité".into() } else { l.email.split('@').next().unwrap_or("").to_string() }),
        email: l.email,
        droit,
    }))
}

/// POST : Origin identique (si présent) et jeton CSRF lié à la session.
fn requete_sure(req: &Request, cfg: &Config, u: &Utilisateur) -> bool {
    let origine_ok = match req.headers().get("Origin").ok().flatten() {
        Some(o) => o == cfg.origine,
        None => true,
    };
    let csrf = req.headers().get("X-CSRF").ok().flatten().unwrap_or_default();
    origine_ok && jeton::csrf_valide(&cfg.cle, &u.sid, &csrf)
}

#[derive(Deserialize)]
struct SalonLien {
    id: String,
}

/// Salon désigné par la clé d'un lien `/s/<cle>` (None si supprimé ou inconnu).
async fn salon_par_cle(env: &Env, cle: &str) -> Result<Option<SalonLien>> {
    if cle.len() > 64 {
        return Ok(None);
    }
    env.d1("DB")?.prepare("SELECT id FROM salons WHERE cle = ?1").bind(&[s(cle)])?.first(None).await
}

/// Inscrit un compte comme membre d'un salon (sans effet s'il l'est déjà).
async fn ajouter_membre(env: &Env, salon: &str, email: &str, nom: &str) -> Result<()> {
    env.d1("DB")?
        .prepare("INSERT OR IGNORE INTO membres (salon_id, email, pseudo, couleur, rejoint_le) VALUES (?1, ?2, ?3, NULL, ?4)")
        .bind(&[s(salon), s(email), s(&regles::pseudo_par_defaut(nom)), n(maintenant_ms())])?
        .run()
        .await?;
    Ok(())
}

const PREFIXE_INVITE: &str = "invite:";
/// Invités au plus par salon (borne les entrées répétées par le lien).
const INVITES_MAX: f64 = 200.0;

/// Identité d'un invité de salon (pas d'e-mail) : `invite:<aléa>`.
fn est_invite(email: &str) -> bool {
    email.starts_with(PREFIXE_INVITE)
}

/// Entrée par le lien sans session : session invité liée au salon, sans Google.
async fn ouvrir_session_invite(env: &Env, cfg: &Config, salon: &str) -> Result<Response> {
    let db = env.d1("DB")?;
    #[derive(Deserialize)]
    struct Compte {
        n: f64,
    }
    let c: Option<Compte> = db
        .prepare("SELECT COUNT(*) AS n FROM membres WHERE salon_id = ?1 AND email LIKE 'invite:%'")
        .bind(&[s(salon)])?
        .first(None)
        .await?;
    if c.is_some_and(|c| c.n >= INVITES_MAX) {
        return page(429, "Salon complet", "Trop d'invités sont déjà entrés dans ce salon. Demandez un nouveau lien à l'organisateur.");
    }
    let email = format!("{PREFIXE_INVITE}{}", jeton::aleatoire_b64(&aleatoire(12)));
    ajouter_membre(env, salon, &email, "Invité").await?;
    let now = maintenant_ms();
    let sid = jeton::aleatoire_b64(&aleatoire(24));
    let exp = now / 1000 + DUREE_SESSION_S;
    db.batch(vec![
        db.prepare("INSERT INTO sessions (id, email, cree_le, expire_le, salon_id) VALUES (?1, ?2, ?3, ?4, ?5)")
            .bind(&[s(&sid), s(&email), n(now), n(exp * 1000), s(salon)])?,
        db.prepare("DELETE FROM sessions WHERE expire_le < ?1").bind(&[n(now)])?,
    ])
    .await?;
    let session = jeton::signer(&cfg.cle, jeton::USAGE_SESSION, &jeton::Session { sid, email, exp });
    redirection(&format!("{}/?salon={salon}", cfg.origine), &[poser_cookie(COOKIE_SESSION, &session, DUREE_SESSION_S)])
}

/// Révoque les invités d'un salon (sessions et adhésions) et ferme leurs connexions.
async fn revoquer_invites(env: &Env, salon: &str) -> Result<()> {
    let db = env.d1("DB")?;
    db.batch(vec![
        db.prepare("UPDATE sessions SET revoquee = 1 WHERE salon_id = ?1").bind(&[s(salon)])?,
        db.prepare("DELETE FROM membres WHERE salon_id = ?1 AND email LIKE 'invite:%'").bind(&[s(salon)])?,
    ])
    .await?;
    Ok(())
}

/// Fin commune des connexions (Google ou mode dev) : contrôle des droits, lien de salon, session.
async fn ouvrir_session(
    env: &Env,
    cfg: &Config,
    email_brut: &str,
    nom: Option<String>,
    lien: Option<String>,
    retour: &str,
) -> Result<Response> {
    let Some(email) = acces::normaliser_email(email_brut) else {
        return page(400, "Adresse invalide", "Cette adresse e-mail n'est pas utilisable.");
    };
    let salon = match lien {
        Some(cle) => salon_par_cle(env, &cle).await?,
        None => None,
    };
    let db = env.d1("DB")?;
    #[derive(Deserialize)]
    struct Ligne {
        liste: f64,
        membre: f64,
    }
    let l: Ligne = db
        .prepare(
            "SELECT EXISTS(SELECT 1 FROM autorises WHERE email = ?1) AS liste, \
             EXISTS(SELECT 1 FROM membres WHERE email = ?1) AS membre",
        )
        .bind(&[s(&email)])?
        .first(None)
        .await?
        .ok_or("lecture des droits")?;
    let situation = Situation {
        admin_config: email == cfg.admin,
        liste: l.liste == 1.0,
        membre_salon: l.membre == 1.0,
        arrive_par_lien: salon.is_some(),
    };
    let droit = acces::droit(situation);
    if droit.is_none() {
        console_log!("connexion refusée (liste) pour un e-mail non autorisé");
        return page_connexion(403, "Accès non autorisé", &format!("Le compte Google {email} n'est pas autorisé. Demandez l'accès à l'organisateur."), "Changer de compte Google", &acces::retour_sur(retour));
    }
    let now = maintenant_ms();
    let nom: String = nom
        .unwrap_or_else(|| email.split('@').next().unwrap_or("joueur").to_string())
        .chars()
        .filter(|c| !c.is_control())
        .take(40)
        .collect();
    let mut retour = acces::retour_sur(retour);
    if let Some(salon) = &salon {
        ajouter_membre(env, &salon.id, &email, &nom).await?;
        retour = format!("/?salon={}", salon.id);
    }
    let sid = jeton::aleatoire_b64(&aleatoire(24));
    let exp = now / 1000 + DUREE_SESSION_S;
    db.batch(vec![
        db.prepare(
            "INSERT INTO comptes (email, nom, premiere_connexion, derniere_connexion) VALUES (?1, ?2, ?3, ?3) \
             ON CONFLICT(email) DO UPDATE SET nom = excluded.nom, derniere_connexion = excluded.derniere_connexion",
        )
        .bind(&[s(&email), s(&nom), n(now)])?,
        db.prepare("INSERT INTO sessions (id, email, cree_le, expire_le) VALUES (?1, ?2, ?3, ?4)")
            .bind(&[s(&sid), s(&email), n(now), n(exp * 1000)])?,
        db.prepare("DELETE FROM sessions WHERE expire_le < ?1").bind(&[n(now)])?,
    ])
    .await?;
    let session = jeton::signer(&cfg.cle, jeton::USAGE_SESSION, &jeton::Session { sid, email, exp });
    redirection(
        &format!("{}{}", cfg.origine, retour),
        &[poser_cookie(COOKIE_SESSION, &session, DUREE_SESSION_S), poser_cookie(COOKIE_OAUTH, "", 0)],
    )
}

// ---------- Google ----------

async fn connexion_google(req: &Request, cfg: &Config) -> Result<Response> {
    if cfg.client_id.is_empty() {
        return page(503, "Connexion indisponible", "Le client OAuth Google n'est pas encore configuré.");
    }
    let url = req.url()?;
    let lien = parametre(&url, "lien").filter(|i| i.len() <= 64);
    let etat = jeton::EtatOAuth {
        state: jeton::aleatoire_b64(&aleatoire(16)),
        nonce: jeton::aleatoire_b64(&aleatoire(16)),
        verif: jeton::aleatoire_b64(&aleatoire(32)),
        retour: acces::retour_sur(&parametre(&url, "retour").unwrap_or_default()),
        lien,
        exp: maintenant_ms() / 1000 + 600,
    };
    let mut cible = Url::parse(google::URL_AUTORISATION)?;
    cible
        .query_pairs_mut()
        .append_pair("client_id", &cfg.client_id)
        .append_pair("redirect_uri", &format!("{}/auth/google/retour", cfg.origine))
        .append_pair("response_type", "code")
        .append_pair("scope", "openid email profile")
        .append_pair("state", &etat.state)
        .append_pair("nonce", &etat.nonce)
        .append_pair("code_challenge", &jeton::defi_pkce(&etat.verif))
        .append_pair("code_challenge_method", "S256")
        .append_pair("prompt", "select_account");
    let signe = jeton::signer(&cfg.cle, jeton::USAGE_OAUTH, &etat);
    redirection(cible.as_str(), &[poser_cookie(COOKIE_OAUTH, &signe, 600)])
}

async fn retour_google(req: &Request, env: &Env, cfg: &Config) -> Result<Response> {
    let url = req.url()?;
    let refus = || page(400, "Connexion interrompue", "La connexion Google a échoué ou a expiré. Recommencez.");
    let Some(etat) = cookie(req, COOKIE_OAUTH).and_then(|c| jeton::verifier::<jeton::EtatOAuth>(&cfg.cle, jeton::USAGE_OAUTH, &c))
    else {
        return refus();
    };
    let (Some(code), Some(state)) = (parametre(&url, "code"), parametre(&url, "state")) else { return refus() };
    if state != etat.state || etat.exp * 1000 < maintenant_ms() {
        return refus();
    }
    let secret = texte_env(env, "GOOGLE_CLIENT_SECRET").ok_or("GOOGLE_CLIENT_SECRET manquant")?;
    let corps = Url::parse("http://x/")?
        .query_pairs_mut()
        .append_pair("code", &code)
        .append_pair("client_id", &cfg.client_id)
        .append_pair("client_secret", &secret)
        .append_pair("redirect_uri", &format!("{}/auth/google/retour", cfg.origine))
        .append_pair("grant_type", "authorization_code")
        .append_pair("code_verifier", &etat.verif)
        .finish()
        .query()
        .unwrap_or_default()
        .to_string();
    let entetes = Headers::new();
    entetes.set("Content-Type", "application/x-www-form-urlencoded")?;
    let mut init = RequestInit::new();
    init.with_method(Method::Post).with_headers(entetes).with_body(Some(s(&corps)));
    let mut rep = Fetch::Request(Request::new_with_init(google::URL_JETON, &init)?).send().await?;
    if rep.status_code() != 200 {
        console_error!("échange du code Google : {}", rep.status_code());
        return refus();
    }
    let jetons: Value = rep.json().await?;
    let Some(id_token) = jetons["id_token"].as_str() else { return refus() };
    let jwks: google::Jwks = Fetch::Url(Url::parse(google::URL_JWKS)?).send().await?.json().await?;
    match google::verifier_id_token(id_token, &jwks, &cfg.client_id, &etat.nonce, maintenant_ms() / 1000) {
        Ok(id) => ouvrir_session(env, cfg, &id.email, id.nom, etat.lien, &etat.retour).await,
        Err(e) => {
            console_error!("ID token refusé : {e:?}");
            refus()
        }
    }
}

// ---------- Routes ----------

#[event(fetch)]
async fn fetch(req: Request, env: Env, ctx: Context) -> Result<Response> {
    let reponse = match router(req, &env, &ctx).await {
        Ok(r) => r,
        Err(e) => {
            console_error!("{e}");
            erreur(500, "erreur interne")?
        }
    };
    if reponse.status_code() != 101 {
        // Les réponses issues du cache ont des en-têtes figés (déjà complets).
        let _ = entetes_securite(reponse.headers());
    }
    Ok(reponse)
}

async fn router(mut req: Request, env: &Env, ctx: &Context) -> Result<Response> {
    let cfg = config(env)?;
    let url = req.url()?;
    let chemin = url.path().to_string();
    let segments: Vec<&str> = chemin.trim_matches('/').split('/').collect();
    let methode = req.method();
    let sensible = chemin.starts_with("/auth/google") || chemin.starts_with("/s/");
    if sensible && !limite(env, "LIMITE_AUTH", format!("auth:{}", ip(&req))).await? {
        return page(429, "Trop de tentatives", "Réessayez dans une minute.");
    }

    match (methode.clone(), segments.as_slice()) {
        (Method::Get, ["auth", "google"]) => return connexion_google(&req, &cfg).await,
        (Method::Get, ["auth", "google", "retour"]) => return retour_google(&req, env, &cfg).await,
        (Method::Get, ["auth", "dev"]) => {
            let local = matches!(url.host_str(), Some("localhost") | Some("127.0.0.1"));
            let email = parametre(&url, "email").unwrap_or_default();
            if !(cfg.mode_dev && local) && !connexion_mesure(&req, env, &email)? {
                return erreur(404, "introuvable");
            }
            let retour = parametre(&url, "retour").unwrap_or_default();
            return ouvrir_session(env, &cfg, &email, parametre(&url, "nom"), parametre(&url, "lien"), &retour).await;
        }
        (Method::Get, ["s", cle]) => {
            let Some(salon) = salon_par_cle(env, cle).await? else {
                return page(410, "Salon fermé", "Ce salon n'existe plus : le lien n'est plus valable.");
            };
            return match utilisateur(&req, env, &cfg).await? {
                Some(u) => {
                    ajouter_membre(env, &salon.id, &u.email, &u.nom).await?;
                    redirection(&format!("{}/?salon={}", cfg.origine, salon.id), &[])
                }
                // Sans session : invité du salon, sans Google.
                None => ouvrir_session_invite(env, &cfg, &salon.id).await,
            };
        }
        (Method::Get, ["api", "salons", id, "ws"]) => return websocket(&req, env, &cfg, id).await,
        _ => {}
    }

    if segments.first() == Some(&"api") || segments.first() == Some(&"auth") {
        let Some(u) = utilisateur(&req, env, &cfg).await? else {
            return erreur(401, "connexion requise");
        };
        if methode != Method::Get {
            if !requete_sure(&req, &cfg, &u) {
                return erreur(403, "jeton CSRF ou origine invalide");
            }
            if !limite(env, "LIMITE_API", format!("api:{}", u.email)).await? {
                return erreur(429, "trop de requêtes");
            }
        }
        return api(&mut req, env, &cfg, &u, methode, &segments).await;
    }

    if methode == Method::Get || methode == Method::Head {
        // Le jeu entier (solo compris) est réservé aux comptes connectés et autorisés.
        if utilisateur(&req, env, &cfg).await?.is_none() {
            if chemin == "/" || chemin == "/index.html" {
                let retour = match url.query() {
                    Some(q) => format!("/?{q}"),
                    None => "/".to_string(),
                };
                return page_connexion(401, "Château Saint-Victor", "Accès réservé : connectez-vous avec un compte Google autorisé.", "Se connecter avec Google", &retour);
            }
            return erreur(401, "connexion requise");
        }
        return servir_jeu(&req, env, ctx, &chemin).await;
    }
    erreur(405, "méthode non autorisée")
}

/// Environnement de mesure déployé (`--env mesure`) : comptes `@charge.test` seulement,
/// sur présentation du secret CLE_MESURE. Sans ce secret, la route n'existe pas.
fn connexion_mesure(req: &Request, env: &Env, email: &str) -> Result<bool> {
    let Some(cle) = texte_env(env, "CLE_MESURE").filter(|c| c.len() >= 32) else { return Ok(false) };
    let recue = req.headers().get("X-Cle-Mesure")?.unwrap_or_default();
    let egal = recue.len() == cle.len() && recue.bytes().zip(cle.bytes()).fold(0u8, |a, (x, y)| a | (x ^ y)) == 0;
    Ok(egal && email.trim().to_lowercase().ends_with("@charge.test"))
}

/// Salon visible par l'utilisateur : tous pour l'admin, sinon ceux dont il est membre.
async fn salon_de(env: &Env, u: &Utilisateur, id: &str) -> Result<Option<Value>> {
    let db = env.d1("DB")?;
    if u.admin() {
        db.prepare("SELECT id, nom, cle, manches, cree_le FROM salons WHERE id = ?1").bind(&[s(id)])?.first(None).await
    } else {
        db.prepare(
            "SELECT sa.id, sa.nom, sa.cle, sa.manches, sa.cree_le FROM salons sa \
             JOIN membres m ON m.salon_id = sa.id AND m.email = ?2 WHERE sa.id = ?1",
        )
        .bind(&[s(id), s(&u.email)])?
        .first(None)
        .await
    }
}

fn lien_salon(cfg: &Config, cle: &str) -> String {
    format!("{}/s/{cle}", cfg.origine)
}

async fn api(req: &mut Request, env: &Env, cfg: &Config, u: &Utilisateur, m: Method, seg: &[&str]) -> Result<Response> {
    let db = env.d1("DB")?;
    let now = maintenant_ms();
    match (m, seg) {
        (Method::Get, ["api", "moi"]) => {
            let invite = est_invite(&u.email);
            reponse_json(
                200,
                &json!({"email": if invite { Value::Null } else { Value::from(u.email.clone()) }, "nom": u.nom,
                        "admin": u.admin(), "droit": format!("{:?}", u.droit).to_lowercase(), "invite": invite,
                        "csrf": jeton::csrf(&cfg.cle, &u.sid)}),
            )
        }
        (Method::Post, ["auth", "deconnexion"]) => {
            db.prepare("UPDATE sessions SET revoquee = 1 WHERE id = ?1").bind(&[s(&u.sid)])?.run().await?;
            let r = reponse_json(200, &json!({"ok": true}))?;
            r.headers().append("Set-Cookie", &poser_cookie(COOKIE_SESSION, "", 0))?;
            Ok(r)
        }

        // Liste autorisée (admin).
        (_, ["api", "autorises", ..]) if !u.admin() => erreur(403, "réservé à l'admin"),
        (Method::Get, ["api", "autorises"]) => {
            let r = db.prepare("SELECT email, ajoute_par, ajoute_le FROM autorises ORDER BY email").all().await?;
            reponse_json(200, &json!({"admin_config": cfg.admin, "autorises": r.results::<Value>()?}))
        }
        (Method::Post, ["api", "autorises"]) => {
            #[derive(Deserialize)]
            struct Corps {
                email: String,
            }
            let Some(c) = corps_json::<Corps>(req).await else { return erreur(400, "corps invalide") };
            let Some(email) = acces::normaliser_email(&c.email) else { return erreur(400, "e-mail invalide") };
            db.prepare(
                "INSERT INTO autorises (email, admin, ajoute_par, ajoute_le) VALUES (?1, 0, ?2, ?3) ON CONFLICT(email) DO NOTHING",
            )
            .bind(&[s(&email), s(&u.email), n(now)])?
            .run()
            .await?;
            reponse_json(200, &json!({"email": email}))
        }
        (Method::Post, ["api", "autorises", "retirer"]) => {
            #[derive(Deserialize)]
            struct Corps {
                email: String,
            }
            let Some(c) = corps_json::<Corps>(req).await else { return erreur(400, "corps invalide") };
            let Some(email) = acces::normaliser_email(&c.email) else { return erreur(400, "e-mail invalide") };
            if email == cfg.admin {
                return erreur(400, "l'admin de configuration ne peut pas être retiré");
            }
            db.batch(vec![
                db.prepare("DELETE FROM autorises WHERE email = ?1").bind(&[s(&email)])?,
                db.prepare("DELETE FROM membres WHERE email = ?1").bind(&[s(&email)])?,
                db.prepare("UPDATE sessions SET revoquee = 1 WHERE email = ?1").bind(&[s(&email)])?,
            ])
            .await?;
            reponse_json(200, &json!({"retire": email}))
        }

        // Salons.
        (Method::Get, ["api", "salons"]) => {
            if u.admin() {
                let r = db
                    .prepare(
                        "SELECT sa.id, sa.nom, sa.cle, sa.manches, sa.cree_le, \
                         (SELECT COUNT(*) FROM membres m WHERE m.salon_id = sa.id) AS membres \
                         FROM salons sa ORDER BY sa.cree_le DESC",
                    )
                    .all()
                    .await?;
                let salons: Vec<Value> = r
                    .results::<Value>()?
                    .into_iter()
                    .map(|mut x| {
                        let cle = x["cle"].as_str().unwrap_or_default().to_string();
                        x["lien"] = Value::from(lien_salon(cfg, &cle));
                        x.as_object_mut().map(|o| o.remove("cle"));
                        x
                    })
                    .collect();
                reponse_json(200, &json!({"salons": salons}))
            } else {
                let r = db
                    .prepare(
                        "SELECT sa.id, sa.nom FROM salons sa JOIN membres m ON m.salon_id = sa.id \
                         WHERE m.email = ?1 ORDER BY m.rejoint_le DESC",
                    )
                    .bind(&[s(&u.email)])?
                    .all()
                    .await?;
                reponse_json(200, &json!({"salons": r.results::<Value>()?}))
            }
        }
        (Method::Post, ["api", "salons"]) => {
            if !u.admin() {
                return erreur(403, "réservé à l'admin");
            }
            #[derive(Deserialize)]
            struct Corps {
                #[serde(default)]
                nom: String,
            }
            let Some(c) = corps_json::<Corps>(req).await else { return erreur(400, "corps invalide") };
            let nom: String = c.nom.split_whitespace().collect::<Vec<_>>().join(" ").chars().filter(|c| !c.is_control()).take(60).collect();
            if nom.is_empty() {
                return erreur(400, "nom requis");
            }
            let id = identifiant();
            let cle = jeton::aleatoire_b64(&aleatoire(16));
            db.batch(vec![
                db.prepare("INSERT INTO salons (id, nom, cle, cree_par, cree_le) VALUES (?1, ?2, ?3, ?4, ?5)")
                    .bind(&[s(&id), s(&nom), s(&cle), s(&u.email), n(now)])?,
            ])
            .await?;
            ajouter_membre(env, &id, &u.email, &u.nom).await?;
            let lien = lien_salon(cfg, &cle);
            reponse_json(201, &json!({"id": id, "nom": nom, "lien": lien, "qr_svg": qr::svg(&lien)}))
        }
        (Method::Get, ["api", "salons", id]) => {
            let Some(sa) = salon_de(env, u, id).await? else { return erreur(404, "salon introuvable") };
            let membres = db
                .prepare("SELECT pseudo, couleur AS c FROM membres WHERE salon_id = ?1 ORDER BY rejoint_le")
                .bind(&[s(id)])?
                .all()
                .await?;
            let manches = db
                .prepare(
                    "SELECT numero, fin, gagnant, raison, classement FROM manches WHERE salon_id = ?1 \
                     ORDER BY numero DESC LIMIT 10",
                )
                .bind(&[s(id)])?
                .all()
                .await?;
            let manches: Vec<Value> = manches
                .results::<Value>()?
                .into_iter()
                .map(|mut m| {
                    let c = m["classement"].as_str().and_then(|c| serde_json::from_str::<Value>(c).ok()).unwrap_or_default();
                    m["classement"] = c;
                    m
                })
                .collect();
            let mut salon = json!({"id": sa["id"], "nom": sa["nom"], "manches": sa["manches"]});
            let mut corps = json!({"salon": salon.take(), "membres": membres.results::<Value>()?, "manches": manches});
            if u.admin() {
                corps["lien"] = Value::from(lien_salon(cfg, sa["cle"].as_str().unwrap_or_default()));
            }
            reponse_json(200, &corps)
        }
        (Method::Get, ["api", "salons", id, "qr.svg"]) => {
            if !u.admin() {
                return erreur(403, "réservé à l'admin");
            }
            let Some(sa) = salon_de(env, u, id).await? else { return erreur(404, "salon introuvable") };
            let lien = lien_salon(cfg, sa["cle"].as_str().unwrap_or_default());
            let r = Response::ok(qr::svg(&lien).unwrap_or_default())?;
            r.headers().set("Content-Type", "image/svg+xml")?;
            r.headers().set("Cache-Control", "private, no-store")?;
            Ok(r)
        }
        (Method::Post, ["api", "salons", id, "supprimer"]) => {
            if !u.admin() {
                return erreur(403, "réservé à l'admin");
            }
            if salon_de(env, u, id).await?.is_none() {
                return erreur(404, "salon introuvable");
            }
            revoquer_invites(env, id).await?;
            db.batch(vec![
                db.prepare("DELETE FROM manches WHERE salon_id = ?1").bind(&[s(id)])?,
                db.prepare("DELETE FROM membres WHERE salon_id = ?1").bind(&[s(id)])?,
                db.prepare("DELETE FROM salons WHERE id = ?1").bind(&[s(id)])?,
            ])
            .await?;
            let stub = env.durable_object("SALLE")?.get_by_name(id)?;
            stub.fetch_with_request(Request::new("https://salle/supprimer", Method::Post)?).await?;
            reponse_json(200, &json!({"supprime": id}))
        }
        (Method::Post, ["api", "salons", id, "lien"]) => {
            if !u.admin() {
                return erreur(403, "réservé à l'admin");
            }
            if salon_de(env, u, id).await?.is_none() {
                return erreur(404, "salon introuvable");
            }
            // Nouveau lien : l'ancien ne marche plus et les invités entrés par lui sont exclus.
            let cle = jeton::aleatoire_b64(&aleatoire(16));
            db.prepare("UPDATE salons SET cle = ?1 WHERE id = ?2").bind(&[s(&cle), s(id)])?.run().await?;
            revoquer_invites(env, id).await?;
            let stub = env.durable_object("SALLE")?.get_by_name(id)?;
            stub.fetch_with_request(Request::new("https://salle/exclure-invites", Method::Post)?).await?;
            let lien = lien_salon(cfg, &cle);
            reponse_json(200, &json!({"lien": lien, "qr_svg": qr::svg(&lien)}))
        }
        (Method::Post, ["api", "salons", id, "ticket"]) => {
            if salon_de(env, u, id).await?.is_none() {
                return erreur(404, "salon introuvable");
            }
            // L'admin entre dans n'importe quel salon : il en devient membre.
            ajouter_membre(env, id, &u.email, &u.nom).await?;
            let ticket = jeton::Ticket { email: u.email.clone(), s: id.to_string(), exp: now / 1000 + DUREE_TICKET_S };
            let signe = jeton::signer(&cfg.cle, jeton::USAGE_TICKET, &ticket);
            let ws = cfg.origine.replacen("https://", "wss://", 1).replacen("http://", "ws://", 1);
            reponse_json(
                200,
                &json!({"ticket": signe, "ws": format!("{ws}/api/salons/{id}/ws?ticket={signe}"), "expire": ticket.exp}),
            )
        }
        _ => erreur(404, "introuvable"),
    }
}

async fn websocket(req: &Request, env: &Env, cfg: &Config, id: &str) -> Result<Response> {
    if req.headers().get("Upgrade")?.map(|u| u.to_lowercase()) != Some("websocket".into()) {
        return erreur(426, "WebSocket attendu");
    }
    if let Some(o) = req.headers().get("Origin")? {
        if o != cfg.origine {
            return erreur(403, "origine refusée");
        }
    }
    let url = req.url()?;
    let Some(t) = parametre(&url, "ticket").and_then(|t| jeton::verifier::<jeton::Ticket>(&cfg.cle, jeton::USAGE_TICKET, &t))
    else {
        return erreur(401, "ticket invalide");
    };
    if t.s != id || t.exp * 1000 < maintenant_ms() {
        return erreur(401, "ticket expiré");
    }
    if !limite(env, "LIMITE_API", format!("ws:{}", t.email)).await? {
        return erreur(429, "trop de connexions");
    }
    #[derive(Deserialize)]
    struct Ligne {
        nom: String,
        pseudo: String,
        couleur: Option<f64>,
    }
    let m: Option<Ligne> = env
        .d1("DB")?
        .prepare(
            "SELECT sa.nom, m.pseudo, m.couleur FROM salons sa JOIN membres m ON m.salon_id = sa.id \
             WHERE sa.id = ?1 AND m.email = ?2",
        )
        .bind(&[s(id), s(&t.email)])?
        .first(None)
        .await?;
    let Some(m) = m else { return erreur(404, "salon introuvable") };
    let h = Headers::new();
    h.set("Upgrade", "websocket")?;
    h.set("X-Salon", id)?;
    h.set("X-Nom-Salon", &urlencoding::encode(&m.nom))?;
    h.set("X-Email", &t.email)?;
    h.set("X-Pseudo", &urlencoding::encode(&m.pseudo))?;
    if let Some(c) = m.couleur {
        h.set("X-Couleur", &(c as u8).to_string())?;
    }
    let mut init = RequestInit::new();
    init.with_headers(h);
    let stub = env.durable_object("SALLE")?.get_by_name(id)?;
    stub.fetch_with_request(Request::new_with_init("https://salle/ws", &init)?).await
}

// ---------- Fichiers du jeu (Static Assets) ----------
//
// `outils/preparer-jeu.mjs` remplit `jeu/` : un manifeste et des morceaux de 20 Mio au plus
// (limite de 25 Mio par fichier des Static Assets). Le Worker sert chaque fichier du manifeste
// en recollant ses morceaux ; la copie se fait entre flux du runtime, sans passer par le WASM.

#[derive(Deserialize)]
struct FichierJeu {
    #[serde(rename = "type")]
    type_mime: String,
    encodage: Option<String>,
    cache: String,
    empreinte: String,
    taille: u64,
    morceaux: Vec<String>,
}

const ASSETS: &str = "https://assets.local/";

async fn servir_jeu(req: &Request, env: &Env, ctx: &Context, chemin: &str) -> Result<Response> {
    let cle = if chemin == "/" { "index.html" } else { chemin.trim_start_matches('/') };
    let assets = env.assets("ASSETS")?;
    let mut manifeste = assets.fetch(format!("{ASSETS}manifeste.json"), None).await?;
    if manifeste.status_code() != 200 {
        if cle == "index.html" {
            return page(404, "Jeu non publié", "Le build WebGL n'a pas encore été préparé (outils/preparer-jeu.mjs).");
        }
        return erreur(404, "introuvable");
    }
    let mut fichiers: std::collections::HashMap<String, FichierJeu> = manifeste.json().await?;
    let Some(f) = fichiers.remove(cle) else {
        return erreur(404, "introuvable");
    };
    let accepte_br = req.headers().get("Accept-Encoding")?.unwrap_or_default().contains("br");
    let etag = format!("\"{}\"", f.empreinte);
    let h = Headers::new();
    h.set("Content-Type", &f.type_mime)?;
    h.set("Cache-Control", &f.cache)?;
    h.set("ETag", &etag)?;
    h.set("Vary", "Accept-Encoding")?;
    entetes_securite(&h)?;
    if req.headers().get("If-None-Match")?.as_deref() == Some(etag.as_str()) {
        return Ok(Response::empty()?.with_status(304).with_headers(h));
    }
    // Fichier déjà compressé : transmis tel quel si le navigateur l'accepte ; sinon octets bruts,
    // que le loader Unity décompresse lui-même (decompressionFallback).
    let manuel = match f.encodage.as_deref() {
        Some("br") if !accepte_br => false,
        Some(e) => {
            h.set("Content-Encoding", e)?;
            true
        }
        None => false,
    };
    if req.method() == Method::Head {
        h.set("Content-Length", &f.taille.to_string())?;
        return Ok(Response::empty()?.with_headers(h));
    }
    let corps = recoller(assets, f.morceaux, f.taille, ctx)?;
    let mut r = Response::from_body(ResponseBody::Stream(corps))?.with_headers(h);
    if manuel {
        r = r.with_encode_body(EncodeBody::Manual);
    }
    Ok(r)
}

/// Flux de longueur fixe (Content-Length connu, utile à la barre de progression du loader)
/// alimenté morceau par morceau par `pipeTo`.
fn recoller(assets: Fetcher, morceaux: Vec<String>, taille: u64, ctx: &Context) -> Result<web_sys::ReadableStream> {
    use worker::js_sys::{Array, Function, Object, Promise, Reflect};
    use worker::wasm_bindgen::JsCast;
    use worker::wasm_bindgen_futures::JsFuture;

    let classe: Function = Reflect::get(&js_sys::global(), &"FixedLengthStream".into())?.dyn_into()?;
    let flux = Reflect::construct(&classe, &Array::of1(&JsValue::from_f64(taille as f64)))?;
    let lecture: web_sys::ReadableStream = Reflect::get(&flux, &"readable".into())?.dyn_into()?;
    let ecriture = Reflect::get(&flux, &"writable".into())?;
    ctx.wait_until(async move {
        let copier = async {
            let options = Object::new();
            Reflect::set(&options, &"preventClose".into(), &JsValue::TRUE)?;
            for m in &morceaux {
                let r = assets.fetch(format!("{ASSETS}{m}"), None).await?;
                let ResponseBody::Stream(source) = r.body() else {
                    return Err(Error::RustError(format!("morceau vide : {m}")));
                };
                let tuyau: Function = Reflect::get(source, &"pipeTo".into())?.dyn_into()?;
                let p: Promise = tuyau.call2(source, &ecriture, &options)?.dyn_into()?;
                JsFuture::from(p).await?;
            }
            // pipeTo a rendu le verrou : on ferme directement l'entrée du flux.
            let fermer: Function = Reflect::get(&ecriture, &"close".into())?.dyn_into()?;
            let p: Promise = fermer.call0(&ecriture)?.dyn_into()?;
            JsFuture::from(p).await?;
            Ok::<(), Error>(())
        };
        if let Err(e) = copier.await {
            console_error!("jeu : {e}");
            if let Ok(abandon) = Reflect::get(&ecriture, &"abort".into()).and_then(|a| a.dyn_into::<Function>().map_err(JsValue::from)) {
                let _ = abandon.call0(&ecriture);
            }
        }
    });
    Ok(lecture)
}

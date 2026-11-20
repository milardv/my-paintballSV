// Durable Object d'un salon : WebSockets hibernables, autorité sur le salon et ses manches (voir regles.rs).
use crate::regles::{Regles, Salon, Sortie};
use crate::web::{aleatoire, maintenant_ms};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::cell::RefCell;
use worker::wasm_bindgen::JsValue;
use worker::*;

const CLE_STOCKAGE: &str = "salon";

#[derive(Serialize, Deserialize)]
struct Attache {
    j: u8,
}

enum Tache {
    Sauver(String),
    Profil(String, String, u8),
    Commencee(u32),
    Terminee { manche: u32, debut: u64, fin: u64, gagnant: Option<String>, raison: String, classement: String },
}

#[durable_object]
pub struct Salle {
    state: State,
    env: Env,
    salon: RefCell<Option<Salon>>,
    /// Sockets acceptées et numéro de joueur, reconstruit au réveil.
    sockets: RefCell<Option<Vec<(u8, WebSocket)>>>,
    alarme: RefCell<Option<u64>>,
    graine: RefCell<u64>,
}

/// xorshift64*, graine tirée par crypto.getRandomValues (évite un appel JS par message).
fn alea(etat: &RefCell<u64>) -> u32 {
    let mut x = *etat.borrow();
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    *etat.borrow_mut() = x;
    (x.wrapping_mul(0x2545_f491_4f6c_dd1d) >> 32) as u32
}

fn js(s: &str) -> JsValue {
    JsValue::from_str(s)
}

fn nb(x: u64) -> JsValue {
    JsValue::from_f64(x as f64)
}

/// Fermeture à l'initiative du serveur : annoncée par un message, l'événement `close` pouvant tarder.
fn fermer_ws(ws: &WebSocket, code: u16, raison: &str) {
    let _ = ws.send_with_str(json!({"t": "fermeture", "code": code, "raison": raison}).to_string());
    let _ = ws.close(Some(code), Some(raison));
}

impl Salle {
    /// Charge l'état durable ; à la première connexion, `entete` (id, nom) crée le salon.
    async fn charger(&self, entete: Option<(&str, &str)>) -> Result<bool> {
        if self.salon.borrow().is_some() {
            return Ok(true);
        }
        let lu: Option<String> = self.state.storage().get(CLE_STOCKAGE).await?;
        let salon = match (lu, entete) {
            (Some(j), _) => {
                let mut s: Salon = serde_json::from_str(&j).map_err(|e| e.to_string())?;
                s.regles = Regles::default();
                s
            }
            (None, Some((id, nom))) => Salon::nouveau(id, nom, Regles::default()),
            (None, None) => return Ok(false),
        };
        *self.salon.borrow_mut() = Some(salon);
        Ok(true)
    }

    fn sockets(&self) -> std::cell::RefMut<'_, Vec<(u8, WebSocket)>> {
        let mut s = self.sockets.borrow_mut();
        if s.is_none() {
            let liste = self
                .state
                .get_websockets()
                .into_iter()
                .filter_map(|ws| ws.deserialize_attachment::<Attache>().ok().flatten().map(|a| (a.j, ws)))
                .collect();
            *s = Some(liste);
        }
        std::cell::RefMut::map(s, |s| s.as_mut().expect("initialisé"))
    }

    /// Envoie les messages et renvoie les écritures à faire.
    fn appliquer(&self, sorties: Vec<Sortie>) -> Vec<Tache> {
        let mut taches = vec![];
        let mut envoyes = 0u64;
        let mut fermer = vec![];
        {
            let sockets = self.sockets();
            for s in &sorties {
                match s {
                    Sortie::Tous(m) => {
                        for (_, ws) in sockets.iter() {
                            envoyes += ws.send_with_str(m).is_ok() as u64;
                        }
                    }
                    Sortie::Sauf(j, m) => {
                        for (_, ws) in sockets.iter().filter(|(k, _)| k != j) {
                            envoyes += ws.send_with_str(m).is_ok() as u64;
                        }
                    }
                    Sortie::A(j, m) => {
                        for (_, ws) in sockets.iter().filter(|(k, _)| k == j) {
                            envoyes += ws.send_with_str(m).is_ok() as u64;
                        }
                    }
                    Sortie::Fermer(j) => fermer.push(*j),
                    Sortie::Profil(email, pseudo, c) => taches.push(Tache::Profil(email.clone(), pseudo.clone(), *c)),
                    _ => {}
                }
            }
        }
        for j in fermer {
            self.sockets().retain(|(k, ws)| {
                if *k == j {
                    fermer_ws(ws, 4008, "trop de messages refusés");
                }
                *k != j
            });
        }
        let mut salon = self.salon.borrow_mut();
        let p = salon.as_mut().expect("chargé");
        p.envoyes += envoyes;
        if sorties.contains(&Sortie::Persister) {
            taches.push(Tache::Sauver(serde_json::to_string(p).expect("sérialisable")));
        }
        if sorties.contains(&Sortie::Commencee) {
            taches.push(Tache::Commencee(p.manche));
        }
        if sorties.contains(&Sortie::Terminee) {
            let classement: Vec<_> = p
                .classement()
                .iter()
                .map(|x| json!({"pseudo": x.pseudo, "points": x.points, "vies": x.vies}))
                .collect();
            let fin = p.fin.clone().expect("fin");
            taches.push(Tache::Terminee {
                manche: p.manche,
                debut: p.debut_ms,
                fin: fin.h,
                gagnant: fin.gagnant.and_then(|g| p.joueur(g)).map(|x| x.pseudo.clone()),
                raison: fin.raison,
                classement: serde_json::Value::from(classement).to_string(),
            });
        }
        taches
    }

    async fn executer(&self, taches: Vec<Tache>) -> Result<()> {
        let id = self.salon.borrow().as_ref().map(|s| s.id.clone()).unwrap_or_default();
        for t in taches {
            match t {
                Tache::Sauver(j) => self.state.storage().put(CLE_STOCKAGE, j).await?,
                Tache::Profil(email, pseudo, c) => {
                    self.env
                        .d1("DB")?
                        .prepare("UPDATE membres SET pseudo = ?1, couleur = ?2 WHERE salon_id = ?3 AND email = ?4")
                        .bind(&[js(&pseudo), nb(c as u64), js(&id), js(&email)])?
                        .run()
                        .await?;
                }
                Tache::Commencee(manche) => {
                    self.env
                        .d1("DB")?
                        .prepare("UPDATE salons SET manches = ?1 WHERE id = ?2")
                        .bind(&[nb(manche as u64), js(&id)])?
                        .run()
                        .await?;
                }
                Tache::Terminee { manche, debut, fin, gagnant, raison, classement } => {
                    self.env
                        .d1("DB")?
                        .prepare(
                            "INSERT OR REPLACE INTO manches (salon_id, numero, debut, fin, gagnant, raison, classement) \
                             SELECT ?1, ?2, ?3, ?4, ?5, ?6, ?7 WHERE EXISTS (SELECT 1 FROM salons WHERE id = ?1)",
                        )
                        .bind(&[
                            js(&id),
                            nb(manche as u64),
                            nb(debut),
                            nb(fin),
                            gagnant.map(|g| js(&g)).unwrap_or(JsValue::NULL),
                            js(&raison),
                            js(&classement),
                        ])?
                        .run()
                        .await?;
                }
            }
        }
        self.programmer().await
    }

    async fn programmer(&self) -> Result<()> {
        let echeance = self.salon.borrow().as_ref().and_then(|p| p.prochaine_echeance());
        if *self.alarme.borrow() == echeance {
            return Ok(());
        }
        *self.alarme.borrow_mut() = echeance;
        match echeance {
            Some(t) => {
                let delai = t.saturating_sub(maintenant_ms()).max(1) as i64;
                self.state.storage().set_alarm(delai).await
            }
            None => self.state.storage().delete_alarm().await,
        }
    }

    async fn traiter(&self, sorties: Vec<Sortie>) -> Result<()> {
        let taches = self.appliquer(sorties);
        self.executer(taches).await
    }

    /// Lien régénéré : les invités connectés sont exclus (leurs sessions sont déjà révoquées).
    async fn exclure_invites(&self) -> Result<Response> {
        if !self.charger(None).await? {
            return Response::ok("");
        }
        let invites: Vec<u8> = {
            let salon = self.salon.borrow();
            salon.as_ref().expect("chargé").joueurs.iter().filter(|x| x.email.starts_with("invite:")).map(|x| x.j).collect()
        };
        self.sockets().retain(|(k, ws)| {
            if invites.contains(k) {
                fermer_ws(ws, 4005, "lien renouvelé");
            }
            !invites.contains(k)
        });
        let mut sorties = vec![];
        for j in invites {
            let mut s = self.salon.borrow_mut();
            sorties.extend(s.as_mut().expect("chargé").deconnecter(j, maintenant_ms()));
        }
        self.traiter(sorties).await?;
        Response::ok("")
    }

    /// Salon supprimé par l'admin : connexions fermées, état effacé.
    async fn supprimer(&self) -> Result<Response> {
        for (_, ws) in self.sockets().drain(..) {
            fermer_ws(&ws, 4004, "salon supprimé");
        }
        *self.salon.borrow_mut() = None;
        *self.alarme.borrow_mut() = None;
        self.state.storage().delete_alarm().await?;
        self.state.storage().delete_all().await?;
        Response::ok("")
    }
}

impl DurableObject for Salle {
    fn new(state: State, env: Env) -> Self {
        Salle {
            state,
            env,
            salon: RefCell::new(None),
            sockets: RefCell::new(None),
            alarme: RefCell::new(None),
            graine: RefCell::new(u64::from_le_bytes(aleatoire(8).try_into().expect("8 octets")) | 1),
        }
    }

    async fn fetch(&self, req: Request) -> Result<Response> {
        if req.path() == "/supprimer" {
            return self.supprimer().await;
        }
        if req.path() == "/exclure-invites" {
            return self.exclure_invites().await;
        }
        let h = req.headers();
        let (Some(id), Some(nom_salon), Some(email), Some(pseudo)) =
            (h.get("X-Salon")?, h.get("X-Nom-Salon")?, h.get("X-Email")?, h.get("X-Pseudo")?)
        else {
            return Response::error("requête incomplète", 400);
        };
        let decoder = |s: String| urlencoding::decode(&s).map(|n| n.into_owned()).unwrap_or(s);
        let (nom_salon, pseudo) = (decoder(nom_salon), decoder(pseudo));
        let couleur = h.get("X-Couleur")?.and_then(|c| c.parse::<u8>().ok());
        self.charger(Some((&id, &nom_salon))).await?;
        let paire = WebSocketPair::new()?;
        let serveur = paire.server;
        let resultat = {
            let mut p = self.salon.borrow_mut();
            let p = p.as_mut().expect("chargé");
            p.nom = nom_salon;
            p.connecter(&email, &pseudo, couleur, maintenant_ms())
        };
        self.state.accept_web_socket(&serveur);
        match resultat {
            Err(raison) => {
                let _ = serveur.send_with_str(json!({"t": "refus", "raison": raison, "ref": "connexion"}).to_string());
                fermer_ws(&serveur, 4003, raison);
            }
            Ok((j, sorties)) => {
                // Une seule connexion par joueur : l'ancienne est fermée.
                self.sockets().retain(|(k, ws)| {
                    if *k == j {
                        fermer_ws(ws, 4001, "connexion remplacée");
                    }
                    *k != j
                });
                serveur.serialize_attachment(Attache { j })?;
                self.sockets().push((j, serveur));
                self.traiter(sorties).await?;
            }
        }
        Response::from_websocket(paire.client)
    }

    async fn websocket_message(&self, ws: WebSocket, message: WebSocketIncomingMessage) -> Result<()> {
        if !self.charger(None).await? {
            fermer_ws(&ws, 4004, "salon supprimé");
            return Ok(());
        }
        // Numéro du joueur : table en mémoire, l'attachement ne sert qu'après un réveil.
        let connu = self.sockets().iter().find(|(_, w)| w == &ws).map(|(j, _)| *j);
        let j = match connu {
            Some(j) => j,
            None => match ws.deserialize_attachment::<Attache>()? {
                Some(a) => a.j,
                None => {
                    let _ = ws.close(Some(4003), Some("inconnu"));
                    return Ok(());
                }
            },
        };
        let texte = match message {
            WebSocketIncomingMessage::String(t) => t,
            WebSocketIncomingMessage::Binary(_) => String::new(),
        };
        let sorties = {
            let mut p = self.salon.borrow_mut();
            let p = p.as_mut().expect("chargé");
            if p.compteurs_depuis == 0 {
                p.compteurs_depuis = maintenant_ms();
            }
            p.recevoir(j, &texte, maintenant_ms(), alea(&self.graine))
        };
        self.traiter(sorties).await
    }

    async fn websocket_close(&self, ws: WebSocket, _code: usize, _raison: String, _propre: bool) -> Result<()> {
        self.fermeture(ws).await
    }

    async fn websocket_error(&self, ws: WebSocket, _erreur: Error) -> Result<()> {
        self.fermeture(ws).await
    }

    async fn alarm(&self) -> Result<Response> {
        if !self.charger(None).await? {
            return Response::ok("");
        }
        *self.alarme.borrow_mut() = None;
        let sorties = self.salon.borrow_mut().as_mut().expect("chargé").echeance(maintenant_ms());
        self.traiter(sorties).await?;
        Response::ok("")
    }
}

impl Salle {
    async fn fermeture(&self, ws: WebSocket) -> Result<()> {
        let Some(a) = ws.deserialize_attachment::<Attache>()? else { return Ok(()) };
        if !self.charger(None).await? {
            return Ok(());
        }
        let encore = {
            let mut sockets = self.sockets();
            let avant = sockets.len();
            sockets.retain(|(_, w)| w != &ws);
            // Si la socket n'était plus suivie, elle a été remplacée : le joueur reste connecté.
            avant != sockets.len() && sockets.iter().any(|(k, _)| *k == a.j) || avant == sockets.len()
        };
        if encore {
            return Ok(());
        }
        let sorties = self.salon.borrow_mut().as_mut().expect("chargé").deconnecter(a.j, maintenant_ms());
        self.traiter(sorties).await
    }
}

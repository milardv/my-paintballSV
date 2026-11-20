// État et règles d'un salon et de ses manches, sans dépendance au runtime : le Durable Object
// lui passe les messages reçus et l'heure, et envoie les sorties qu'il produit.
use crate::balistique::{self, V3};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::VecDeque;

/// Règles modifiables en un seul endroit.
#[derive(Debug, Clone)]
pub struct Regles {
    pub vies: u32,
    pub points_par_touche: u32,
    /// Le premier à atteindre la cible de points gagne.
    pub victoire_aux_points: bool,
    /// Le dernier joueur non éliminé gagne (si au moins deux joueurs sont entrés dans la manche).
    pub victoire_dernier_survivant: bool,
    /// Protection après une apparition.
    pub invulnerabilite_ms: u64,
    /// Au-delà, la manche s'arrête et le meilleur score gagne (égalité possible).
    pub duree_max_ms: Option<u64>,
    /// Un joueur en jeu déconnecté plus longtemps est éliminé.
    pub delai_deconnexion_ms: u64,
    pub joueurs_min: usize,
    /// Joueurs en jeu dans une manche.
    pub joueurs_max: usize,
    /// Connexions simultanées au salon (joueurs et spectateurs).
    pub connexions_max: usize,
}

impl Default for Regles {
    fn default() -> Self {
        Regles {
            vies: 3,
            points_par_touche: 1,
            victoire_aux_points: true,
            victoire_dernier_survivant: true,
            invulnerabilite_ms: 1500,
            duree_max_ms: None,   // parties sans limite de temps (demande du 19/11)
            delai_deconnexion_ms: 30_000,
            joueurs_min: 1,
            joueurs_max: 8,
            connexions_max: 16,
        }
    }
}

impl Regles {
    /// Total des vies = vies × joueurs entrés ; cible = moitié arrondie en dessous (4 pour 3 joueurs).
    pub fn cible(&self, entres: usize) -> u32 {
        self.vies * entres as u32 / 2
    }
}

// Tolérances anti-triche (mètres, millisecondes).
const VITESSE_MAX: f64 = 25.0;
const ECART_ORIGINE_TIR: f64 = 5.0;
const ECART_TRAJECTOIRE: f64 = 0.3;
const RAYON_JOUEUR: f64 = 1.0;
// Point d'impact par rapport aux pieds : gabarit enfant (1,50 m, capsule de 0,30 à 1,30 m) + marge.
const HAUTEUR_JOUEUR: (f64, f64) = (-0.3, 1.8);
const AVANCE_TOUCHE_MS: f64 = 200.0;
const RETARD_TOUCHE_MS: f64 = 1500.0;
const FENETRE_CIBLE_MS: (f64, f64) = (800.0, 200.0);
const HISTORIQUE_MS: u64 = 2500;
const RAFALE_TIRS: f64 = 10.0;
const CADENCE_TIRS: f64 = 9.0;
const TIRS_GARDES: usize = 64;
const INFRACTIONS_MAX: u32 = 50;
const SPAWN_ELOIGNE: f64 = 8.0;
/// Distance minimale entre le lieu de la mort et le point de réapparition (comme le mode bots).
const SPAWN_LOIN_MORT: f64 = 12.0;
/// Les positions sont regroupées et diffusées au plus toutes les 50 ms (20 Hz).
pub const PERIODE_LOT_MS: u64 = 50;
pub const COULEURS: u8 = 6;
const PSEUDO_MIN: usize = 2;
const PSEUDO_MAX: usize = 16;

#[derive(Deserialize, Debug)]
#[serde(tag = "t")]
pub enum Entrant {
    #[serde(rename = "ping")]
    Ping { c: f64 },
    #[serde(rename = "profil")]
    Profil { pseudo: Option<String>, c: Option<u8> },
    #[serde(rename = "lancer")]
    Lancer {
        spawns: Vec<[f32; 4]>,
        #[serde(default)]
        vies: Option<u32>,
    },
    #[serde(rename = "entrer")]
    Entrer {},
    #[serde(rename = "p")]
    Pose {
        #[serde(default)]
        q: u32,
        p: [f32; 3],
        #[serde(default)]
        r: [f32; 2],
        #[serde(default)]
        v: [f32; 3],
    },
    /// Piano du petit salon : les autres joueurs entendent la musique au piano (son 3D côté client).
    #[serde(rename = "piano")]
    Piano { on: bool },
    #[serde(rename = "tir")]
    Tir {
        id: u32,
        o: [f32; 3],
        d: [f32; 3],
        #[serde(default = "vitesse_defaut")]
        v: f32,
    },
    #[serde(rename = "touche")]
    Touche { tir: u32, cible: u8, pt: [f32; 3] },
    #[serde(rename = "stats")]
    Stats {},
}

fn vitesse_defaut() -> f32 {
    balistique::VITESSE_INITIALE
}

#[derive(Debug, PartialEq)]
pub enum Sortie {
    Tous(String),
    Sauf(u8, String),
    A(u8, String),
    Fermer(u8),
    /// L'état durable a changé.
    Persister,
    /// Pseudo ou couleur d'un compte à enregistrer (e-mail, pseudo, couleur).
    Profil(String, String, u8),
    Commencee,
    Terminee,
}

#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    Attente,
    EnCours,
    Fin,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct Fin {
    pub gagnant: Option<u8>,
    pub raison: String,
    pub h: u64,
}

#[derive(Debug, Clone)]
struct TirConnu {
    id: u32,
    t: u64,
    o: V3,
    vitesse: V3,
    utilise: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Joueur {
    pub j: u8,
    pub email: String,
    pub pseudo: String,
    pub couleur: u8,
    pub connecte: bool,
    pub deconnexion: Option<u64>,
    /// Entré dans la manche en cours (reste vrai une fois éliminé).
    pub en_jeu: bool,
    pub vies: u32,
    pub points: u32,
    pub elimine: bool,
    pub respawn_ms: u64,
    pub spawn: Option<[f32; 4]>,
    #[serde(skip)]
    pose: Option<(u64, V3)>,
    #[serde(skip)]
    historique: VecDeque<(u64, V3)>,
    #[serde(skip)]
    tirs: VecDeque<TirConnu>,
    #[serde(skip)]
    jetons_tir: f64,
    #[serde(skip)]
    jetons_ms: u64,
    #[serde(skip)]
    infractions: u32,
}

impl Joueur {
    fn nouveau(j: u8, email: &str, pseudo: String, couleur: u8) -> Self {
        Joueur {
            j,
            email: email.into(),
            pseudo,
            couleur,
            connecte: true,
            deconnexion: None,
            en_jeu: false,
            vies: 0,
            points: 0,
            elimine: false,
            respawn_ms: 0,
            spawn: None,
            pose: None,
            historique: VecDeque::new(),
            tirs: VecDeque::new(),
            jetons_tir: RAFALE_TIRS,
            jetons_ms: 0,
            infractions: 0,
        }
    }

    fn placer(&mut self, t: u64, p: V3) {
        self.pose = Some((t, p));
        self.historique.push_back((t, p));
        while self.historique.front().is_some_and(|(h, _)| *h + HISTORIQUE_MS < t) {
            self.historique.pop_front();
        }
    }

    fn apparaitre(&mut self, s: [f32; 4], t: u64) {
        self.spawn = Some(s);
        self.respawn_ms = t;
        self.historique.clear();
        self.placer(t, v3([s[0], s[1], s[2]]));
    }

    /// En jeu dans la manche et pas encore éliminé.
    fn actif(&self) -> bool {
        self.en_jeu && !self.elimine
    }
}

/// Pseudo accepté : 2 à 16 caractères (lettres, chiffres, espace, - _ ' .), espaces superflus retirés.
pub fn nettoyer_pseudo(brut: &str) -> Option<String> {
    let p = brut.split_whitespace().collect::<Vec<_>>().join(" ");
    let n = p.chars().count();
    let ok = (PSEUDO_MIN..=PSEUDO_MAX).contains(&n) && p.chars().all(|c| c.is_alphanumeric() || " -_'.".contains(c));
    ok.then_some(p)
}

/// Pseudo par défaut à partir du nom Google : caractères non admis retirés, tronqué.
pub fn pseudo_par_defaut(nom: &str) -> String {
    let filtre: String = nom.chars().map(|c| if c.is_alphanumeric() || " -_'.".contains(c) { c } else { ' ' }).collect();
    let court: String = filtre.split_whitespace().collect::<Vec<_>>().join(" ").chars().take(PSEUDO_MAX).collect();
    nettoyer_pseudo(court.trim_end()).unwrap_or_else(|| "Joueur".into())
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Salon {
    #[serde(skip)]
    pub regles: Regles,
    pub id: String,
    pub nom: String,
    pub phase: Phase,
    pub manche: u32,
    pub joueurs: Vec<Joueur>,
    pub spawns: Vec<[f32; 4]>,
    pub cible: u32,
    /// Vies de chaque joueur dans la manche en cours (choisies au lancement, 1 à 10).
    #[serde(default)]
    pub vies: u32,
    /// Joueurs entrés dans la manche (départs et éliminés compris).
    pub entres: u32,
    pub debut_ms: u64,
    pub fin: Option<Fin>,
    #[serde(skip)]
    pub recus: u64,
    #[serde(skip)]
    pub envoyes: u64,
    #[serde(skip)]
    pub compteurs_depuis: u64,
    /// Dernière position de chaque joueur depuis le dernier envoi groupé.
    #[serde(skip)]
    lot: Vec<(u8, String)>,
    #[serde(skip)]
    dernier_lot_ms: u64,
}

fn q2(x: f64) -> f64 {
    (x * 100.0).round() / 100.0
}

fn v3(a: [f32; 3]) -> V3 {
    [a[0] as f64, a[1] as f64, a[2] as f64]
}

fn fini(a: &[f32]) -> bool {
    a.iter().all(|x| x.is_finite() && x.abs() < 10_000.0)
}

fn arr(v: V3) -> [f64; 3] {
    [q2(v[0]), q2(v[1]), q2(v[2])]
}

fn refus(raison: &str, sur: &str) -> String {
    json!({"t": "refus", "raison": raison, "ref": sur}).to_string()
}

impl Salon {
    pub fn nouveau(id: &str, nom: &str, regles: Regles) -> Self {
        Salon {
            regles,
            id: id.into(),
            nom: nom.into(),
            phase: Phase::Attente,
            manche: 0,
            joueurs: vec![],
            spawns: vec![],
            cible: 0,
            vies: 0,
            entres: 0,
            debut_ms: 0,
            fin: None,
            recus: 0,
            envoyes: 0,
            compteurs_depuis: 0,
            lot: vec![],
            dernier_lot_ms: 0,
        }
    }

    /// Vies de la manche en cours (règle par défaut avant le premier lancement).
    fn vies_manche(&self) -> u32 {
        if self.vies == 0 { self.regles.vies } else { self.vies }
    }

    /// Cible de points pour `entres` joueurs, avec les vies de la manche (moitié du total arrondie en dessous).
    fn cible_pour(&self, entres: usize) -> u32 {
        Regles { vies: self.vies_manche(), ..self.regles.clone() }.cible(entres)
    }

    pub fn joueur(&self, j: u8) -> Option<&Joueur> {
        self.joueurs.iter().find(|x| x.j == j)
    }

    fn joueur_mut(&mut self, j: u8) -> Option<&mut Joueur> {
        self.joueurs.iter_mut().find(|x| x.j == j)
    }

    fn pseudo_pris(&self, pseudo: &str, sauf: Option<u8>) -> bool {
        let p = pseudo.to_lowercase();
        self.joueurs.iter().any(|x| Some(x.j) != sauf && x.pseudo.to_lowercase() == p)
    }

    /// Couleur déjà portée par un autre joueur présent, alors qu'il en reste une libre.
    fn couleur_prise(&self, c: u8, sauf: Option<u8>) -> bool {
        let autres: Vec<u8> = self.joueurs.iter().filter(|x| x.connecte && Some(x.j) != sauf).map(|x| x.couleur).collect();
        autres.contains(&c) && (0..COULEURS).any(|k| !autres.contains(&k))
    }

    pub fn etat_json(&self) -> String {
        let joueurs: Vec<_> = self
            .joueurs
            .iter()
            .filter(|x| x.connecte || x.en_jeu)
            .map(|x| {
                json!({"j": x.j, "pseudo": x.pseudo, "c": x.couleur, "connecte": x.connecte, "en_jeu": x.en_jeu,
                       "vies": x.vies, "points": x.points, "elimine": x.elimine})
            })
            .collect();
        json!({"t": "etat", "phase": self.phase, "manche": self.manche, "debut": self.debut_ms, "cible": self.cible,
               "vies": self.vies_manche(), "joueurs": joueurs, "fin": self.fin})
        .to_string()
    }

    /// Connexion (ou retour) d'un membre. `pseudo` et `couleur` : profil enregistré, ou nom Google à la première venue.
    pub fn connecter(
        &mut self,
        email: &str,
        pseudo: &str,
        couleur: Option<u8>,
        maintenant: u64,
    ) -> Result<(u8, Vec<Sortie>), &'static str> {
        if self.joueurs.iter().filter(|x| x.connecte && x.email != email).count() >= self.regles.connexions_max {
            return Err("salon plein");
        }
        let mut sorties = vec![];
        let j = if let Some(x) = self.joueurs.iter_mut().find(|x| x.email == email) {
            x.connecte = true;
            x.deconnexion = None;
            x.j
        } else {
            let j = (0..=u8::MAX).find(|j| self.joueur(*j).is_none()).ok_or("salon plein")?;
            // Pseudo unique : suffixe numéroté si déjà pris.
            let base = pseudo_par_defaut(pseudo);
            let mut p = base.clone();
            let mut k = 2;
            while self.pseudo_pris(&p, None) {
                let suffixe = format!(" {k}");
                p = format!("{}{suffixe}", base.chars().take(PSEUDO_MAX - suffixe.len()).collect::<String>().trim_end());
                k += 1;
            }
            let c = couleur
                .filter(|c| *c < COULEURS && !self.couleur_prise(*c, None))
                .or_else(|| (0..COULEURS).find(|c| !self.couleur_prise(*c, None)))
                .unwrap_or(j % COULEURS);
            if Some(c) != couleur || p != pseudo {
                sorties.push(Sortie::Profil(email.into(), p.clone(), c));
            }
            self.joueurs.push(Joueur::nouveau(j, email, p, c));
            j
        };
        let x = self.joueur(j).expect("présent");
        let bienvenue = json!({"t": "bienvenue", "j": j, "h": maintenant, "salon": {"id": self.id, "nom": self.nom},
            "pseudo": x.pseudo, "c": x.couleur, "en_jeu": x.actif() && self.phase == Phase::EnCours,
            "spawn": if x.actif() && self.phase == Phase::EnCours { x.spawn } else { None },
            "regles": {"vies": self.regles.vies, "points_par_touche": self.regles.points_par_touche,
                       "invulnerabilite_ms": self.regles.invulnerabilite_ms,
                       "duree_max_ms": self.regles.duree_max_ms, "joueurs_max": self.regles.joueurs_max}});
        sorties.extend([Sortie::A(j, bienvenue.to_string()), Sortie::Tous(self.etat_json()), Sortie::Persister]);
        Ok((j, sorties))
    }

    pub fn deconnecter(&mut self, j: u8, maintenant: u64) -> Vec<Sortie> {
        let en_cours = self.phase == Phase::EnCours;
        if let Some(x) = self.joueur_mut(j) {
            x.connecte = false;
            x.deconnexion = (en_cours && x.actif()).then_some(maintenant);
        }
        vec![Sortie::Tous(self.etat_json()), Sortie::Persister]
    }

    pub fn recevoir(&mut self, j: u8, texte: &str, maintenant: u64, alea: u32) -> Vec<Sortie> {
        self.recus += 1;
        if self.joueur(j).is_none() {
            return vec![Sortie::Fermer(j)];
        }
        let msg = match (texte.len() <= 8192).then(|| serde_json::from_str::<Entrant>(texte)) {
            Some(Ok(m)) => m,
            _ => return self.infraction(j, "message invalide", "?"),
        };
        let mut sorties = match msg {
            Entrant::Ping { c } => vec![Sortie::A(j, json!({"t": "pong", "c": c, "h": maintenant}).to_string())],
            Entrant::Profil { pseudo, c } => self.profil(j, pseudo, c),
            Entrant::Lancer { spawns, vies } => self.lancer(j, spawns, vies, maintenant, alea),
            Entrant::Entrer {} => self.entrer(j, maintenant, alea),
            Entrant::Pose { q, p, r, v } => self.pose(j, q, p, r, v, maintenant),
            Entrant::Tir { id, o, d, v } => self.tir(j, id, o, d, v, maintenant),
            Entrant::Piano { on } => vec![Sortie::Tous(json!({"t": "piano", "j": j, "on": on}).to_string())],
            Entrant::Touche { tir, cible, pt } => self.touche(j, tir, cible, pt, maintenant, alea),
            Entrant::Stats {} => {
                let s = json!({"t": "stats", "recus": self.recus, "envoyes": self.envoyes,
                               "depuis": self.compteurs_depuis, "h": maintenant, "joueurs": self.joueurs.len()});
                vec![Sortie::A(j, s.to_string())]
            }
        };
        sorties.extend(self.vider_lot(maintenant, false));
        sorties
    }

    /// Envoi groupé des positions : un seul message pour tous, au plus tous les PERIODE_LOT_MS.
    /// Appelé à chaque message reçu (pas de minuterie : sans message entrant, rien à envoyer).
    pub fn vider_lot(&mut self, maintenant: u64, force: bool) -> Vec<Sortie> {
        if self.lot.is_empty() || (!force && maintenant < self.dernier_lot_ms + PERIODE_LOT_MS) {
            return vec![];
        }
        self.dernier_lot_ms = maintenant;
        let liste: Vec<String> = self.lot.drain(..).map(|(_, m)| m).collect();
        vec![Sortie::Tous(format!(r#"{{"t":"ps","h":{maintenant},"l":[{}]}}"#, liste.join(",")))]
    }

    fn infraction(&mut self, j: u8, raison: &str, sur: &str) -> Vec<Sortie> {
        let mut s = vec![Sortie::A(j, refus(raison, sur))];
        if let Some(x) = self.joueur_mut(j) {
            x.infractions += 1;
            if x.infractions > INFRACTIONS_MAX {
                s.push(Sortie::Fermer(j));
            }
        }
        s
    }

    fn profil(&mut self, j: u8, pseudo: Option<String>, c: Option<u8>) -> Vec<Sortie> {
        let pseudo = match pseudo {
            None => None,
            Some(brut) => match nettoyer_pseudo(&brut) {
                None => return vec![Sortie::A(j, refus("pseudo invalide", "profil"))],
                Some(p) if self.pseudo_pris(&p, Some(j)) => return vec![Sortie::A(j, refus("pseudo pris", "profil"))],
                Some(p) => Some(p),
            },
        };
        if let Some(c) = c {
            if c >= COULEURS {
                return vec![Sortie::A(j, refus("couleur invalide", "profil"))];
            }
            if self.couleur_prise(c, Some(j)) {
                return vec![Sortie::A(j, refus("couleur prise", "profil"))];
            }
        }
        let x = self.joueur_mut(j).expect("présent");
        if let Some(p) = pseudo {
            x.pseudo = p;
        }
        if let Some(c) = c {
            x.couleur = c;
        }
        let profil = Sortie::Profil(x.email.clone(), x.pseudo.clone(), x.couleur);
        vec![profil, Sortie::Tous(self.etat_json()), Sortie::Persister]
    }

    fn lancer(&mut self, j: u8, spawns: Vec<[f32; 4]>, vies: Option<u32>, maintenant: u64, alea: u32) -> Vec<Sortie> {
        if self.phase == Phase::EnCours {
            return vec![Sortie::A(j, refus("manche en cours", "lancer"))];
        }
        if spawns.is_empty() || spawns.len() > 64 || !spawns.iter().all(|s| fini(s)) {
            return self.infraction(j, "points d'apparition invalides", "lancer");
        }
        let presents = self.joueurs.iter().filter(|x| x.connecte).count();
        if presents < self.regles.joueurs_min {
            return vec![Sortie::A(j, refus("pas assez de joueurs", "lancer"))];
        }
        if vies.is_some_and(|v| !(1..=10).contains(&v)) {
            return self.infraction(j, "vies invalides", "lancer");
        }
        self.vies = vies.unwrap_or(self.regles.vies);
        self.spawns = spawns;
        self.manche += 1;
        self.phase = Phase::EnCours;
        self.debut_ms = maintenant;
        self.fin = None;
        let n = self.spawns.len();
        let decalage = alea as usize % n;
        let max = self.regles.joueurs_max;
        let mut placement = vec![];
        let mut i = 0;
        for x in self.joueurs.iter_mut() {
            x.en_jeu = false;
            x.vies = 0;
            x.points = 0;
            x.elimine = false;
            x.spawn = None;
            x.deconnexion = None;
            x.tirs.clear();
            if x.connecte && i < max {
                let s = self.spawns[(decalage + i) % n];
                x.en_jeu = true;
                x.vies = self.vies;
                x.apparaitre(s, maintenant);
                placement.push(json!({"j": x.j, "spawn": s}));
                i += 1;
            }
        }
        self.entres = i as u32;
        self.cible = self.cible_pour(i);
        let debut = json!({"t": "debut", "manche": self.manche, "h": maintenant, "cible": self.cible,
                           "vies": self.vies, "joueurs": placement});
        vec![Sortie::Tous(debut.to_string()), Sortie::Tous(self.etat_json()), Sortie::Commencee, Sortie::Persister]
    }

    /// Entrée dans la manche en cours : 3 vies, 0 point, loin des autres ; la cible ne fait que monter.
    fn entrer(&mut self, j: u8, maintenant: u64, alea: u32) -> Vec<Sortie> {
        if self.phase != Phase::EnCours {
            return vec![Sortie::A(j, refus("hors manche", "entrer"))];
        }
        let x = self.joueur(j).expect("présent");
        if x.en_jeu {
            let raison = if x.elimine { "déjà éliminé" } else { "déjà en jeu" };
            return vec![Sortie::A(j, refus(raison, "entrer"))];
        }
        if self.joueurs.iter().filter(|x| x.en_jeu).count() >= self.regles.joueurs_max {
            return vec![Sortie::A(j, refus("manche complète", "entrer"))];
        }
        let Some(s) = self.choisir_spawn(j, None, alea) else {
            return vec![Sortie::A(j, refus("hors manche", "entrer"))];
        };
        let vies = self.vies_manche();
        let x = self.joueur_mut(j).expect("présent");
        x.en_jeu = true;
        x.vies = vies;
        x.points = 0;
        x.elimine = false;
        x.tirs.clear();
        x.apparaitre(s, maintenant);
        self.entres += 1;
        self.cible = self.cible.max(self.cible_pour(self.entres as usize));
        let entree = json!({"t": "entree", "j": j, "spawn": s, "cible": self.cible, "h": maintenant});
        vec![Sortie::Tous(entree.to_string()), Sortie::Tous(self.etat_json()), Sortie::Persister]
    }

    fn pose(&mut self, j: u8, q: u32, p: [f32; 3], r: [f32; 2], v: [f32; 3], maintenant: u64) -> Vec<Sortie> {
        if !(fini(&p) && fini(&r) && fini(&v)) {
            return self.infraction(j, "pose invalide", "p");
        }
        let en_cours = self.phase == Phase::EnCours;
        let x = self.joueur_mut(j).expect("présent");
        // Pendant une manche, seuls les joueurs en jeu et en vie sont relayés.
        if en_cours && !x.actif() {
            return vec![];
        }
        let p3 = v3(p);
        if let (true, Some((t0, p0))) = (en_cours, x.pose) {
            let dt = maintenant.saturating_sub(t0) as f64 / 1000.0;
            if balistique::distance(p0, p3) > VITESSE_MAX * dt.max(0.25) + 1.0 {
                return vec![Sortie::A(j, json!({"t": "corr", "p": arr(p0)}).to_string())];
            }
        }
        x.placer(maintenant, p3);
        let relais = format!(
            r#"{{"t":"p","j":{j},"q":{q},"p":[{},{},{}],"r":[{},{}],"v":[{},{},{}],"h":{maintenant}}}"#,
            q2(p3[0]), q2(p3[1]), q2(p3[2]),
            (r[0] as f64 * 10.0).round() / 10.0, (r[1] as f64 * 10.0).round() / 10.0,
            q2(v[0] as f64), q2(v[1] as f64), q2(v[2] as f64)
        );
        match self.lot.iter_mut().find(|(k, _)| *k == j) {
            Some(e) => e.1 = relais,
            None => self.lot.push((j, relais)),
        }
        vec![]
    }

    fn tir(&mut self, j: u8, id: u32, o: [f32; 3], d: [f32; 3], v: f32, maintenant: u64) -> Vec<Sortie> {
        if self.phase != Phase::EnCours {
            return vec![Sortie::A(j, refus("hors manche", "tir"))];
        }
        if !(fini(&o) && fini(&d) && v.is_finite()) {
            return self.infraction(j, "tir invalide", "tir");
        }
        let (o, d) = (v3(o), v3(d));
        let n = balistique::norme(d);
        if !(0.9..=1.1).contains(&n) || !(10.0..=95.0).contains(&v) {
            return self.infraction(j, "tir invalide", "tir");
        }
        let x = self.joueur_mut(j).expect("présent");
        if !x.actif() {
            return vec![Sortie::A(j, refus("hors manche", "tir"))];
        }
        if x.pose.is_some_and(|(_, p)| balistique::distance(p, o) > ECART_ORIGINE_TIR) {
            return self.infraction(j, "origine éloignée", "tir");
        }
        let ecoule = maintenant.saturating_sub(x.jetons_ms) as f64 / 1000.0;
        x.jetons_tir = (x.jetons_tir + ecoule * CADENCE_TIRS).min(RAFALE_TIRS);
        x.jetons_ms = maintenant;
        if x.jetons_tir < 1.0 {
            return self.infraction(j, "cadence", "tir");
        }
        if x.tirs.iter().any(|t| t.id == id) {
            return self.infraction(j, "tir déjà connu", "tir");
        }
        x.jetons_tir -= 1.0;
        let d = [d[0] / n, d[1] / n, d[2] / n];
        let vf = v as f64;
        x.tirs.push_back(TirConnu { id, t: maintenant, o, vitesse: [d[0] * vf, d[1] * vf, d[2] * vf], utilise: false });
        while x.tirs.len() > TIRS_GARDES {
            x.tirs.pop_front();
        }
        let relais = json!({"t": "tir", "j": j, "id": id, "o": arr(o),
            "d": [d[0], d[1], d[2]], "v": vf, "h": maintenant});
        vec![Sortie::Sauf(j, relais.to_string())]
    }

    fn touche(&mut self, j: u8, id: u32, c: u8, pt: [f32; 3], maintenant: u64, alea: u32) -> Vec<Sortie> {
        if self.phase != Phase::EnCours {
            return vec![Sortie::A(j, refus("hors manche", "touche"))];
        }
        if !fini(&pt) || c == j {
            return self.infraction(j, "touche invalide", "touche");
        }
        let pt = v3(pt);
        let Some(tir) = self.joueur(j).and_then(|x| x.tirs.iter().find(|t| t.id == id)).cloned() else {
            return self.infraction(j, "tir inconnu", "touche");
        };
        if tir.utilise {
            return self.infraction(j, "tir déjà compté", "touche");
        }
        let Some(cible) = self.joueur(c) else {
            return self.infraction(j, "cible inconnue", "touche");
        };
        if !cible.en_jeu {
            return vec![Sortie::A(j, refus("cible hors manche", "touche"))];
        }
        if cible.elimine {
            return vec![Sortie::A(j, refus("cible éliminée", "touche"))];
        }
        let (ecart, vol) = balistique::approche(tir.o, tir.vitesse, pt, 3.0);
        if ecart > ECART_TRAJECTOIRE {
            return self.infraction(j, "hors trajectoire", "touche");
        }
        let vol_ms = vol * 1000.0;
        let delai = maintenant.saturating_sub(tir.t) as f64;
        if delai + AVANCE_TOUCHE_MS < vol_ms || delai > vol_ms + RETARD_TOUCHE_MS {
            return self.infraction(j, "temps de vol", "touche");
        }
        let impact = tir.t as f64 + vol_ms;
        if (cible.respawn_ms + self.regles.invulnerabilite_ms) as f64 > impact {
            return vec![Sortie::A(j, refus("cible protégée", "touche"))];
        }
        let fenetre = (impact - FENETRE_CIBLE_MS.0)..=(impact + FENETRE_CIBLE_MS.1);
        // Positions annoncées autour de l'impact ; à défaut, la dernière connue avant (joueur muet).
        let recentes = cible.historique.iter().filter(|(t, _)| fenetre.contains(&(*t as f64)));
        let derniere = cible.pose.filter(|(t, _)| (*t as f64) < *fenetre.start());
        let plausible = recentes.chain(derniere.iter()).any(|(_, p)| {
            let h = ((pt[0] - p[0]).powi(2) + (pt[2] - p[2]).powi(2)).sqrt();
            let dy = pt[1] - p[1];
            h <= RAYON_JOUEUR && (HAUTEUR_JOUEUR.0..=HAUTEUR_JOUEUR.1).contains(&dy)
        });
        if !plausible {
            return self.infraction(j, "cible absente", "touche");
        }

        // Touche validée.
        if let Some(t) = self.joueur_mut(j).and_then(|x| x.tirs.iter_mut().find(|t| t.id == id)) {
            t.utilise = true;
        }
        let gain = self.regles.points_par_touche;
        let points = {
            let x = self.joueur_mut(j).expect("présent");
            x.points += gain;
            x.points
        };
        let mort = self.joueur(c).and_then(|x| x.pose.map(|(_, p)| p));
        let spawn = self.choisir_spawn(c, mort, alea);
        let x = self.joueur_mut(c).expect("présente");
        x.vies = x.vies.saturating_sub(1);
        if x.vies == 0 {
            x.elimine = true;
            x.spawn = None;
        } else if let Some(s) = spawn {
            x.apparaitre(s, maintenant);
        }
        let message = json!({"t": "touche", "tireur": j, "cible": c, "tir": id, "pt": arr(pt), "o": arr(tir.o),
            "vies": x.vies, "points": points, "elimine": x.elimine, "spawn": x.spawn, "h": maintenant});
        let mut s = vec![Sortie::Tous(message.to_string()), Sortie::Persister];
        s.extend(self.verifier_fin(maintenant));
        s
    }

    /// Point d'apparition aléatoire, de préférence loin des adversaires en vie et du lieu de la mort.
    fn choisir_spawn(&self, c: u8, mort: Option<V3>, alea: u32) -> Option<[f32; 4]> {
        if self.spawns.is_empty() {
            return None;
        }
        let adversaires: Vec<V3> = self
            .joueurs
            .iter()
            .filter(|x| x.j != c && x.actif())
            .filter_map(|x| x.pose.map(|(_, p)| p))
            .collect();
        let point = |s: &[f32; 4]| v3([s[0], s[1], s[2]]);
        let loin_adversaires = |s: &&[f32; 4]| adversaires.iter().all(|p| balistique::distance(*p, point(s)) >= SPAWN_ELOIGNE);
        let loin_mort = |s: &&[f32; 4]| mort.is_none_or(|m| balistique::distance(m, point(s)) >= SPAWN_LOIN_MORT);
        // Les deux contraintes, sinon les adversaires seuls, sinon n'importe quel point.
        let mut choix: Vec<_> = self.spawns.iter().filter(|s| loin_adversaires(s) && loin_mort(s)).collect();
        if choix.is_empty() {
            choix = self.spawns.iter().filter(loin_adversaires).collect();
        }
        if choix.is_empty() {
            choix = self.spawns.iter().collect();
        }
        Some(*choix[alea as usize % choix.len()])
    }

    fn terminer(&mut self, gagnant: Option<u8>, raison: &str, maintenant: u64) -> Vec<Sortie> {
        self.phase = Phase::Fin;
        self.fin = Some(Fin { gagnant, raison: raison.into(), h: maintenant });
        for x in self.joueurs.iter_mut() {
            x.deconnexion = None;
        }
        let classement: Vec<_> = self
            .classement()
            .iter()
            .map(|x| json!({"j": x.j, "pseudo": x.pseudo, "points": x.points, "vies": x.vies}))
            .collect();
        let fin = json!({"t": "fin", "manche": self.manche, "gagnant": gagnant, "raison": raison, "h": maintenant,
                         "classement": classement});
        vec![Sortie::Tous(fin.to_string()), Sortie::Tous(self.etat_json()), Sortie::Terminee, Sortie::Persister]
    }

    /// Joueurs de la manche, du premier au dernier.
    pub fn classement(&self) -> Vec<&Joueur> {
        let mut c: Vec<_> = self.joueurs.iter().filter(|x| x.en_jeu).collect();
        c.sort_by(|a, b| b.points.cmp(&a.points).then(b.vies.cmp(&a.vies)).then(a.j.cmp(&b.j)));
        c
    }

    fn verifier_fin(&mut self, maintenant: u64) -> Vec<Sortie> {
        if self.phase != Phase::EnCours {
            return vec![];
        }
        if self.regles.victoire_aux_points {
            if let Some(x) = self.joueurs.iter().find(|x| x.en_jeu && x.points >= self.cible) {
                let g = x.j;
                return self.terminer(Some(g), "points", maintenant);
            }
        }
        let vivants: Vec<u8> = self.joueurs.iter().filter(|x| x.actif()).map(|x| x.j).collect();
        if vivants.is_empty() {
            return self.terminer(None, "aucun survivant", maintenant);
        }
        // Seul dans la manche, on se promène et on tire : pas de victoire de « dernier survivant ».
        if self.regles.victoire_dernier_survivant && vivants.len() == 1 && self.entres >= 2 {
            return self.terminer(Some(vivants[0]), "dernier survivant", maintenant);
        }
        vec![]
    }

    /// Instant du prochain contrôle (déconnexions, durée maximale).
    pub fn prochaine_echeance(&self) -> Option<u64> {
        if self.phase != Phase::EnCours {
            return None;
        }
        let deco = self
            .joueurs
            .iter()
            .filter(|x| x.actif())
            .filter_map(|x| x.deconnexion.map(|t| t + self.regles.delai_deconnexion_ms));
        let duree = self.regles.duree_max_ms.map(|d| self.debut_ms + d);
        deco.chain(duree).min()
    }

    pub fn echeance(&mut self, maintenant: u64) -> Vec<Sortie> {
        if self.phase != Phase::EnCours {
            return vec![];
        }
        let mut s = vec![];
        let delai = self.regles.delai_deconnexion_ms;
        for x in self.joueurs.iter_mut() {
            if x.actif() && x.deconnexion.is_some_and(|t| t + delai <= maintenant) {
                x.elimine = true;
                x.vies = 0;
                x.deconnexion = None;
                s.push(Sortie::Tous(json!({"t": "elimine", "j": x.j, "raison": "deconnexion"}).to_string()));
            }
        }
        if !s.is_empty() {
            s.push(Sortie::Tous(self.etat_json()));
            s.push(Sortie::Persister);
            s.extend(self.verifier_fin(maintenant));
        }
        if self.phase == Phase::EnCours && self.regles.duree_max_ms.is_some_and(|d| self.debut_ms + d <= maintenant) {
            let c = self.classement();
            let gagnant = match (c.first(), c.get(1)) {
                (Some(a), Some(b)) if a.points == b.points => None,
                (Some(a), _) => Some(a.j),
                _ => None,
            };
            s.extend(self.terminer(gagnant, "temps", maintenant));
        }
        s
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SPAWNS: &str = "[[0,0,0,0],[50,0,0,0],[0,0,50,0],[50,0,50,0]]";

    fn messages(s: &[Sortie]) -> Vec<serde_json::Value> {
        s.iter()
            .filter_map(|x| match x {
                Sortie::Tous(m) | Sortie::Sauf(_, m) | Sortie::A(_, m) => Some(serde_json::from_str(m).unwrap()),
                _ => None,
            })
            .collect()
    }

    fn type_de(s: &[Sortie], t: &str) -> Option<serde_json::Value> {
        messages(s).into_iter().find(|m| m["t"] == t)
    }

    fn raison(s: &[Sortie]) -> String {
        type_de(s, "refus").expect("refus")["raison"].as_str().unwrap().to_string()
    }

    fn lancer() -> String {
        format!(r#"{{"t":"lancer","spawns":{SPAWNS}}}"#)
    }

    /// Salon avec `n` joueurs connectés, manche lancée par j0 : j0 à (0,0,0), j1 à (10,0,0), j2 à (0,0,10)…
    fn salon(n: usize, regles: Regles) -> Salon {
        let mut p = Salon::nouveau("s1", "Salon", regles);
        for i in 0..n {
            p.connecter(&format!("j{i}@x.fr"), &format!("J{i}"), None, 0).unwrap();
        }
        let s = p.recevoir(0, &lancer(), 1000, 0);
        assert!(s.contains(&Sortie::Commencee), "{s:?}");
        placer_tous(&mut p, 1000);
        p
    }

    fn placer_tous(p: &mut Salon, t: u64) {
        for i in 0..p.joueurs.len() as u8 {
            let pos = [10.0 * (i % 2) as f64, 0.0, 10.0 * (i / 2) as f64];
            p.joueur_mut(i).unwrap().placer(t, pos);
        }
    }

    /// Tir réglementaire de `a` vers la position de `b`, déclaré à l'arrivée de la bille.
    fn toucher(p: &mut Salon, a: u8, b: u8, t: u64, id: u32) -> Vec<Sortie> {
        placer_tous(p, t);
        let o = p.joueur(a).unwrap().pose.unwrap().1;
        let o = [o[0], o[1] + 1.3, o[2]];
        let cible = p.joueur(b).unwrap().pose.unwrap().1;
        let visee = [cible[0], cible[1] + 1.0, cible[2]];
        let d = [visee[0] - o[0], visee[1] - o[1], visee[2] - o[2]];
        let n = balistique::norme(d);
        let tir = json!({"t": "tir", "id": id, "o": o, "d": [d[0] / n, d[1] / n, d[2] / n], "v": 85.344});
        p.recevoir(a, &tir.to_string(), t, 0);
        let v0 = 85.344;
        let (_, vol) = balistique::approche(o, [d[0] / n * v0, d[1] / n * v0, d[2] / n * v0], visee, 3.0);
        let pt = balistique::position_a(o, [d[0] / n * v0, d[1] / n * v0, d[2] / n * v0], vol);
        let msg = json!({"t": "touche", "tir": id, "cible": b, "pt": pt});
        p.recevoir(a, &msg.to_string(), t + (vol * 1000.0) as u64 + 60, 1)
    }

    #[test]
    fn cible_de_victoire() {
        let r = Regles::default();
        assert_eq!((r.cible(2), r.cible(3), r.cible(4), r.cible(8)), (3, 4, 6, 12));
    }

    #[test]
    fn pseudos() {
        assert_eq!(nettoyer_pseudo("  Léa   la  Rapide "), Some("Léa la Rapide".into()));
        assert_eq!(nettoyer_pseudo("a\nb"), Some("a b".into()), "espaces normalisés");
        for p in ["a", "", "   ", "<script>", "abcdefghijklmnopq", "x\u{202e}y"] {
            assert_eq!(nettoyer_pseudo(p), None, "{p:?}");
        }
        assert_eq!(pseudo_par_defaut("Valentin <M>"), "Valentin M");
        assert_eq!(pseudo_par_defaut("🙂"), "Joueur");
        assert_eq!(pseudo_par_defaut("Jean-Baptiste de la Fontaine"), "Jean-Baptiste de");
    }

    #[test]
    fn arrivee_profil_unique() {
        let mut p = Salon::nouveau("s1", "Salon", Regles::default());
        let (a, s) = p.connecter("a@x.fr", "Léa", None, 0).unwrap();
        assert_eq!(type_de(&s, "bienvenue").unwrap()["salon"]["nom"], "Salon");
        assert!(s.contains(&Sortie::Profil("a@x.fr".into(), "Léa".into(), 0)), "couleur attribuée enregistrée");
        // Même prénom, même couleur demandée : pseudo suffixé, couleur libre suivante.
        let (b, _) = p.connecter("b@x.fr", "Léa", Some(0), 0).unwrap();
        assert_eq!(p.joueur(b).unwrap().pseudo, "Léa 2");
        assert_eq!(p.joueur(b).unwrap().couleur, 1);
        // Changement de profil.
        assert_eq!(raison(&p.recevoir(b, r#"{"t":"profil","pseudo":"léa"}"#, 10, 0)), "pseudo pris");
        assert_eq!(raison(&p.recevoir(b, r#"{"t":"profil","c":0}"#, 10, 0)), "couleur prise");
        assert_eq!(raison(&p.recevoir(b, r#"{"t":"profil","pseudo":"<b>"}"#, 10, 0)), "pseudo invalide");
        let s = p.recevoir(b, r#"{"t":"profil","pseudo":" Max ","c":3}"#, 10, 0);
        assert!(s.contains(&Sortie::Profil("b@x.fr".into(), "Max".into(), 3)));
        assert_eq!(type_de(&s, "etat").unwrap()["joueurs"][1]["pseudo"], "Max");
        // Retour : même numéro, profil gardé.
        p.deconnecter(a, 20);
        assert_eq!(p.connecter("a@x.fr", "Autre nom", None, 30).unwrap().0, a);
        assert_eq!(p.joueur(a).unwrap().pseudo, "Léa");
        // Absent : sa couleur se libère.
        p.deconnecter(a, 40);
        assert!(type_de(&p.recevoir(b, r#"{"t":"profil","c":0}"#, 50, 0), "refus").is_none());
    }

    #[test]
    fn couleurs_toutes_prises() {
        let mut p = Salon::nouveau("s1", "Salon", Regles::default());
        for i in 0..7 {
            p.connecter(&format!("j{i}@x.fr"), &format!("J{i}"), None, 0).unwrap();
        }
        // Six couleurs pour sept joueurs : le septième en partage une.
        let couleurs: Vec<u8> = p.joueurs.iter().map(|x| x.couleur).collect();
        assert_eq!(&couleurs[..6], &[0, 1, 2, 3, 4, 5]);
        assert!(type_de(&p.recevoir(6, r#"{"t":"profil","c":2}"#, 10, 0), "refus").is_none());
    }

    #[test]
    fn salon_plein() {
        let regles = Regles { connexions_max: 2, ..Regles::default() };
        let mut p = Salon::nouveau("s1", "Salon", regles);
        p.connecter("a@x.fr", "A", None, 0).unwrap();
        p.connecter("b@x.fr", "B", None, 0).unwrap();
        assert_eq!(p.connecter("c@x.fr", "C", None, 0).unwrap_err(), "salon plein");
        assert!(p.connecter("a@x.fr", "A", None, 0).is_ok(), "reconnexion toujours possible");
    }

    #[test]
    fn lancement_par_tout_membre_et_manches_successives() {
        let mut p = Salon::nouveau("s1", "Salon", Regles::default());
        let (a, _) = p.connecter("a@x.fr", "A", None, 0).unwrap();
        let (b, _) = p.connecter("b@x.fr", "B", None, 0).unwrap();
        assert!(p.recevoir(b, r#"{"t":"lancer","spawns":[]}"#, 10, 0).iter().any(|s| matches!(s, Sortie::A(..))));
        let s = p.recevoir(b, &lancer(), 10, 1);
        let debut = type_de(&s, "debut").unwrap();
        assert_eq!((debut["manche"].as_u64(), debut["cible"].as_u64()), (Some(1), Some(3)));
        assert_eq!(p.phase, Phase::EnCours);
        assert!(p.joueurs.iter().all(|x| x.en_jeu && x.vies == 3 && x.spawn.is_some()));
        assert_ne!(p.joueur(a).unwrap().spawn, p.joueur(b).unwrap().spawn);
        assert_eq!(raison(&p.recevoir(a, &lancer(), 20, 0)), "manche en cours");
        // Fin de manche : n'importe qui relance, tout est remis à zéro.
        placer_tous(&mut p, 10);
        for (k, t) in [3000, 6000, 9000].iter().enumerate() {
            toucher(&mut p, a, b, *t, k as u32);
        }
        assert_eq!(p.phase, Phase::Fin);
        assert_eq!(p.fin.as_ref().unwrap().gagnant, Some(a));
        let s = p.recevoir(b, &lancer(), 20_000, 2);
        assert_eq!(type_de(&s, "debut").unwrap()["manche"], 2);
        assert!(p.joueurs.iter().all(|x| x.points == 0 && x.vies == 3 && !x.elimine));
        assert_eq!(p.fin, None);
    }

    #[test]
    fn vies_choisies_au_lancement() {
        let mut p = Salon::nouveau("s1", "Salon", Regles::default());
        let (a, _) = p.connecter("a@x.fr", "A", None, 0).unwrap();
        let (b, _) = p.connecter("b@x.fr", "B", None, 0).unwrap();
        let s = p.recevoir(a, &format!(r#"{{"t":"lancer","spawns":{SPAWNS},"vies":5}}"#), 10, 0);
        let debut = type_de(&s, "debut").unwrap();
        assert_eq!((debut["vies"].as_u64(), debut["cible"].as_u64()), (Some(5), Some(5)));
        assert!(p.joueurs.iter().all(|x| x.vies == 5));
        let _ = b;
        let mut q = Salon::nouveau("s2", "Salon", Regles::default());
        let (c, _) = q.connecter("c@x.fr", "C", None, 0).unwrap();
        assert!(type_de(&q.recevoir(c, &format!(r#"{{"t":"lancer","spawns":{SPAWNS},"vies":0}}"#), 10, 0), "debut").is_none());
    }

    #[test]
    fn manche_seul_puis_entree() {
        let mut p = Salon::nouveau("s1", "Salon", Regles::default());
        let (a, _) = p.connecter("a@x.fr", "A", None, 0).unwrap();
        assert!(type_de(&p.recevoir(a, &lancer(), 10, 0), "debut").is_some());
        assert_eq!(p.phase, Phase::EnCours);
        // Seul : pas de victoire de dernier survivant, la manche continue.
        assert!(p.verifier_fin(1000).is_empty());
        assert_eq!(p.phase, Phase::EnCours);
        let (b, _) = p.connecter("b@x.fr", "B", None, 2000).unwrap();
        assert!(type_de(&p.recevoir(b, r#"{"t":"entrer"}"#, 2000, 1), "entree").is_some());
        assert_eq!(p.cible, 3);
    }

    #[test]
    fn spectateur_puis_entree_en_cours() {
        let mut p = salon(2, Regles::default());
        assert_eq!(p.cible, 3);
        toucher(&mut p, 0, 1, 5000, 1);
        // C arrive pendant la manche : spectateur, ni relayé ni touchable.
        let (c, s) = p.connecter("c@x.fr", "C", None, 6000).unwrap();
        assert_eq!(type_de(&s, "bienvenue").unwrap()["en_jeu"], false);
        assert!(p.recevoir(c, r#"{"t":"p","q":1,"p":[5,0,5]}"#, 6100, 0).is_empty());
        assert!(p.lot.iter().all(|(k, _)| *k != c));
        assert_eq!(raison(&p.recevoir(c, r#"{"t":"tir","id":1,"o":[5,1.3,5],"d":[1,0,0]}"#, 6200, 0)), "hors manche");
        assert_eq!(raison(&toucher(&mut p, 0, c, 7000, 2)), "cible hors manche");
        // Entrée : 3 vies, 0 point, loin des autres, cible recalculée (3 entrés → 4).
        let s = p.recevoir(c, r#"{"t":"entrer"}"#, 8000, 3);
        let e = type_de(&s, "entree").unwrap();
        assert_eq!((e["j"].as_u64(), e["cible"].as_u64()), (Some(c as u64), Some(4)));
        let x = p.joueur(c).unwrap();
        assert!(x.en_jeu && x.vies == 3 && x.points == 0 && x.respawn_ms == 8000);
        assert_eq!(raison(&p.recevoir(c, r#"{"t":"entrer"}"#, 8100, 0)), "déjà en jeu");
        // Protégé 1,5 s après son entrée, puis touchable.
        assert_eq!(raison(&toucher(&mut p, 0, c, 8200, 4)), "cible protégée");
        assert!(type_de(&toucher(&mut p, 0, c, 10_000, 5), "touche").is_some());
    }

    #[test]
    fn cible_ne_baisse_jamais() {
        let mut p = salon(3, Regles::default());
        assert_eq!(p.cible, 4);
        // Un joueur part et est éliminé : la cible reste 4.
        p.deconnecter(2, 2000);
        p.echeance(32_000);
        assert!(p.joueur(2).unwrap().elimine);
        assert_eq!(p.cible, 4);
        // Il revient : déjà entré dans la manche, il ne repart pas avec des vies neuves.
        p.connecter("j2@x.fr", "J2", None, 33_000).unwrap();
        assert_eq!(raison(&p.recevoir(2, r#"{"t":"entrer"}"#, 33_100, 0)), "déjà éliminé");
    }

    #[test]
    fn manche_complete() {
        let regles = Regles { joueurs_max: 2, ..Regles::default() };
        let mut p = salon(3, regles);
        assert!(!p.joueur(2).unwrap().en_jeu, "troisième présent : spectateur");
        assert_eq!(raison(&p.recevoir(2, r#"{"t":"entrer"}"#, 2000, 0)), "manche complète");
    }

    #[test]
    fn touche_validee() {
        let mut p = salon(3, Regles::default());
        let s = toucher(&mut p, 0, 1, 5000, 1);
        let t = type_de(&s, "touche").expect("touche acceptée");
        assert_eq!((t["vies"].as_u64(), t["points"].as_u64()), (Some(2), Some(1)));
        assert_eq!(t["o"][1].as_f64(), Some(1.3), "origine du tir pour l'indicateur");
        let spawn = p.joueur(1).unwrap().spawn.unwrap();
        assert!(p.spawns.contains(&spawn));
        assert_eq!(p.joueur(1).unwrap().respawn_ms, t["h"].as_u64().unwrap());
    }

    #[test]
    fn reapparition_loin_de_la_mort() {
        let mut p = salon(2, Regles::default());
        // B meurt en (10,0,0) ; A est en (0,0,0). Seul (40,0,0) est à plus de 8 m de A et 12 m de B.
        p.spawns = vec![[0.0, 0.0, 5.0, 0.0], [15.0, 0.0, 0.0, 0.0], [40.0, 0.0, 0.0, 0.0]];
        for t in 0..20u32 {
            assert_eq!(p.choisir_spawn(1, Some([10.0, 0.0, 0.0]), t), Some([40.0, 0.0, 0.0, 0.0]));
        }
    }

    #[test]
    fn touches_refusees() {
        let mut p = salon(2, Regles::default());
        placer_tous(&mut p, 5000);
        let tir = r#"{"t":"tir","id":7,"o":[0,1.3,0],"d":[1,0,0]}"#;
        assert!(type_de(&p.recevoir(0, tir, 5000, 0), "tir").is_some());
        assert_eq!(raison(&p.recevoir(0, tir, 5001, 0)), "tir déjà connu");
        let r = |p: &mut Salon, m: &str, t| type_de(&p.recevoir(0, m, t, 0), "refus").map(|x| x["raison"].clone());
        assert_eq!(r(&mut p, r#"{"t":"touche","tir":99,"cible":1,"pt":[10,1.3,0]}"#, 5200).unwrap(), "tir inconnu");
        assert_eq!(r(&mut p, r#"{"t":"touche","tir":7,"cible":0,"pt":[10,1.3,0]}"#, 5200).unwrap(), "touche invalide");
        assert_eq!(r(&mut p, r#"{"t":"touche","tir":7,"cible":1,"pt":[10,3,0]}"#, 5200).unwrap(), "hors trajectoire");
        let loin = balistique::position_a([0.0, 1.3, 0.0], [85.344, 0.0, 0.0], 0.5);
        let m = json!({"t": "touche", "tir": 7, "cible": 1, "pt": loin}).to_string();
        assert_eq!(r(&mut p, &m, 5010).unwrap(), "temps de vol");
        let pt = balistique::position_a([0.0, 1.3, 0.0], [85.344, 0.0, 0.0], 0.125);
        let m = json!({"t": "touche", "tir": 7, "cible": 1, "pt": pt}).to_string();
        assert_eq!(r(&mut p, &m, 8000).unwrap(), "temps de vol");
        // Cible ailleurs, ou trop haut pour un enfant (point à 2 m au-dessus des pieds).
        p.joueur_mut(1).unwrap().historique.clear();
        p.joueur_mut(1).unwrap().placer(5100, [30.0, 0.0, 30.0]);
        assert_eq!(r(&mut p, &m, 5150).unwrap(), "cible absente");
        p.joueur_mut(1).unwrap().historique.clear();
        p.joueur_mut(1).unwrap().placer(5100, [10.0, -0.7, 0.0]);
        assert_eq!(r(&mut p, &m, 5150).unwrap(), "cible absente");
        // Une touche valide ne compte qu'une fois.
        p.joueur_mut(1).unwrap().placer(5100, [10.0, 0.0, 0.0]);
        assert!(type_de(&p.recevoir(0, &m, 5150, 0), "touche").is_some());
        assert_eq!(r(&mut p, &m, 5160).unwrap(), "tir déjà compté");
        assert_eq!(p.joueur(0).unwrap().points, 1);
    }

    #[test]
    fn cible_muette_reste_touchable() {
        let mut p = salon(2, Regles::default());
        p.joueur_mut(0).unwrap().placer(9000, [0.0, 0.0, 0.0]);
        let o = [0.0, 1.3, 0.0];
        p.recevoir(0, r#"{"t":"tir","id":1,"o":[0,1.3,0],"d":[1,0,0]}"#, 9000, 0);
        let (_, vol) = balistique::approche(o, [85.344, 0.0, 0.0], [10.0, 1.3, 0.0], 3.0);
        let pt = balistique::position_a(o, [85.344, 0.0, 0.0], vol);
        let m = json!({"t": "touche", "tir": 1, "cible": 1, "pt": pt}).to_string();
        assert!(type_de(&p.recevoir(0, &m, 9000 + (vol * 1000.0) as u64 + 20, 0), "touche").is_some());
    }

    #[test]
    fn protection_apres_respawn() {
        let mut p = salon(2, Regles::default());
        assert_eq!(raison(&toucher(&mut p, 0, 1, 1200, 1)), "cible protégée");
        assert!(type_de(&toucher(&mut p, 0, 1, 3000, 2), "touche").is_some());
        assert_eq!(raison(&toucher(&mut p, 0, 1, 3500, 3)), "cible protégée");
    }

    #[test]
    fn victoire_aux_points_a_trois() {
        let mut p = salon(3, Regles::default());
        assert_eq!(p.cible, 4);
        for (i, t) in [(1, 5000), (2, 8000), (3, 11000)] {
            toucher(&mut p, 0, 1, t, i);
        }
        assert!(p.joueur(1).unwrap().elimine);
        assert_eq!(p.phase, Phase::EnCours, "3 points sur 4, deux joueurs en vie");
        let s = toucher(&mut p, 0, 2, 14000, 4);
        let fin = type_de(&s, "fin").unwrap();
        assert_eq!((fin["gagnant"].as_u64(), fin["raison"].as_str(), fin["manche"].as_u64()), (Some(0), Some("points"), Some(1)));
        assert!(s.contains(&Sortie::Terminee));
        assert_eq!(p.classement()[0].j, 0);
        assert_eq!(raison(&toucher(&mut p, 2, 0, 17000, 5)), "hors manche");
    }

    #[test]
    fn dernier_survivant() {
        let regles = Regles { victoire_aux_points: false, ..Regles::default() };
        let mut p = salon(3, regles);
        let mut t = 5000;
        for (cible, id0) in [(1, 0), (2, 10)] {
            for k in 0..3 {
                toucher(&mut p, 0, cible, t, id0 + k);
                t += 3000;
            }
        }
        assert_eq!(p.fin.as_ref().unwrap().gagnant, Some(0));
        assert_eq!(p.fin.as_ref().unwrap().raison, "dernier survivant");
    }

    #[test]
    fn deconnexion_prolongee() {
        let mut p = salon(2, Regles::default());
        p.deconnecter(1, 2000);
        assert_eq!(p.prochaine_echeance(), Some(32_000));
        assert!(p.echeance(10_000).is_empty());
        let s = p.echeance(32_000);
        assert_eq!(type_de(&s, "fin").unwrap()["raison"], "dernier survivant");
        assert_eq!(p.prochaine_echeance(), None);
    }

    #[test]
    fn retour_pendant_la_manche() {
        let mut p = salon(2, Regles::default());
        toucher(&mut p, 0, 1, 5000, 1);
        p.deconnecter(1, 6000);
        let (j, s) = p.connecter("j1@x.fr", "J1", None, 10_000).unwrap();
        let b = type_de(&s, "bienvenue").unwrap();
        assert_eq!((j, b["en_jeu"].as_bool()), (1, Some(true)));
        assert!(b["spawn"].is_array());
        assert_eq!(p.joueur(1).unwrap().vies, 2, "vies conservées");
        assert_eq!(p.prochaine_echeance(), None, "plus d'élimination prévue, pas de limite de temps");
    }

    #[test]
    fn duree_maximale() {
        let mut p = salon(2, Regles { duree_max_ms: Some(600_000), ..Regles::default() });
        toucher(&mut p, 0, 1, 5000, 1);
        let fin_prevue = 1000 + 600_000;
        assert_eq!(p.prochaine_echeance(), Some(fin_prevue));
        let s = p.echeance(fin_prevue);
        let fin = type_de(&s, "fin").unwrap();
        assert_eq!((fin["gagnant"].as_u64(), fin["raison"].as_str()), (Some(0), Some("temps")));
    }

    #[test]
    fn piano_relaye() {
        let mut p = salon(2, Regles::default());
        let m = type_de(&p.recevoir(1, r#"{"t":"piano","on":true}"#, 1100, 0), "piano").expect("relais");
        assert_eq!((m["j"].as_u64(), m["on"].as_bool()), (Some(1), Some(true)));
    }

    #[test]
    fn deplacement_impossible() {
        let mut p = salon(2, Regles::default());
        let ok = p.recevoir(0, r#"{"t":"p","q":1,"p":[2,0,0],"r":[90,0]}"#, 1100, 0);
        let lot = type_de(&ok, "ps").expect("envoi groupé");
        assert_eq!(lot["l"][0]["j"], 0);
        assert_eq!(lot["l"][0]["p"][0].as_f64(), Some(2.0));
        let s = p.recevoir(0, r#"{"t":"p","q":2,"p":[200,0,0],"r":[90,0]}"#, 1200, 0);
        assert_eq!(type_de(&s, "corr").unwrap()["p"][0].as_f64(), Some(2.0));
    }

    #[test]
    fn positions_groupees() {
        let mut p = salon(3, Regles::default());
        let pose = |x: f32| format!(r#"{{"t":"p","q":1,"p":[{x},0,0],"r":[0,0]}}"#);
        assert!(type_de(&p.recevoir(0, &pose(0.5), 2000, 0), "ps").is_some());
        assert!(p.recevoir(1, &pose(10.5), 2010, 0).is_empty());
        assert!(p.recevoir(0, &pose(0.7), 2020, 0).is_empty());
        assert!(p.recevoir(0, &pose(0.9), 2030, 0).is_empty());
        let lot = type_de(&p.recevoir(2, &pose(0.2), 2050, 0), "ps").unwrap();
        let l = lot["l"].as_array().unwrap();
        assert_eq!(l.len(), 3);
        assert_eq!(l.iter().find(|m| m["j"] == 0).unwrap()["p"][0], 0.9);
    }

    #[test]
    fn cadence_et_messages_invalides() {
        let mut p = salon(2, Regles::default());
        let mut refuses = 0;
        for id in 0..15 {
            let m = format!(r#"{{"t":"tir","id":{id},"o":[0,1.3,0],"d":[0,0,1]}}"#);
            refuses += type_de(&p.recevoir(0, &m, 2000, 0), "refus").is_some() as u32;
        }
        assert_eq!(refuses, 5, "rafale de 10 au plus");
        assert!(type_de(&p.recevoir(0, r#"{"t":"tir","id":99,"o":[0,1.3,0],"d":[0,0,9]}"#, 4000, 0), "refus").is_some());
        let mut ferme = false;
        for _ in 0..60 {
            ferme |= p.recevoir(1, "pas du json", 3000, 0).contains(&Sortie::Fermer(1));
        }
        assert!(ferme);
    }

    #[test]
    fn persistance() {
        let p = salon(2, Regles::default());
        let relu: Salon = serde_json::from_str(&serde_json::to_string(&p).unwrap()).unwrap();
        assert_eq!(relu.phase, Phase::EnCours);
        assert_eq!((relu.joueurs.len(), relu.cible, relu.manche, relu.entres), (2, 3, 1, 2));
        assert_eq!(relu.nom, "Salon");
    }
}

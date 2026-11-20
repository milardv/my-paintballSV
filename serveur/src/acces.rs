// Règles d'accès : qui peut se connecter et qui est admin.
// Seul l'admin de configuration (ADMIN_EMAIL) gère la liste et les salons ; le rôle ne se délègue pas.
// Le lien d'un salon rend membre : un membre a accès au jeu entier tant que le salon existe.

pub fn normaliser_email(brut: &str) -> Option<String> {
    let e = brut.trim().to_lowercase();
    let (local, domaine) = e.split_once('@')?;
    let valide = !local.is_empty()
        && e.len() <= 254
        && domaine.contains('.')
        && !domaine.starts_with('.')
        && !domaine.ends_with('.')
        && !domaine.contains('@')
        && e.chars().all(|c| c.is_ascii_alphanumeric() || "@.+-_'".contains(c));
    valide.then_some(e)
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Droit {
    /// ADMIN_EMAIL, et lui seul.
    Admin,
    /// Inscrit sur la liste autorisée.
    Autorise,
    /// Hors liste, membre d'au moins un salon (entré par son lien).
    Membre,
}

/// Ce que la base sait d'un e-mail au moment de la connexion.
#[derive(Debug, Default, Clone, Copy)]
pub struct Situation {
    pub admin_config: bool,
    /// Inscrit sur la liste autorisée.
    pub liste: bool,
    /// Membre d'un salon existant.
    pub membre_salon: bool,
    /// Arrive par le lien valide d'un salon (il en devient membre).
    pub arrive_par_lien: bool,
}

pub fn droit(s: Situation) -> Option<Droit> {
    if s.admin_config {
        Some(Droit::Admin)
    } else if s.liste {
        Some(Droit::Autorise)
    } else if s.membre_salon || s.arrive_par_lien {
        Some(Droit::Membre)
    } else {
        None
    }
}

/// Chemin de retour après connexion : chemin local seulement (pas de redirection ouverte).
pub fn retour_sur(retour: &str) -> String {
    let ok = retour.starts_with('/')
        && !retour.starts_with("//")
        && !retour.contains('\\')
        && retour.len() < 512
        && retour.chars().all(|c| !c.is_control());
    if ok { retour.to_string() } else { "/".to_string() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn emails() {
        assert_eq!(normaliser_email("  Jean.Dupont1@EXEMPLE.fr "), Some("jean.dupont1@exemple.fr".into()));
        for e in ["", "a", "a@b", "@b.fr", "a@@b.fr", "a b@c.fr", "a\n@b.fr", "a@.fr", "a@b.", "<a@b.fr>"] {
            assert_eq!(normaliser_email(e), None, "{e:?}");
        }
    }

    #[test]
    fn liste_blanche() {
        let s = Situation::default();
        assert_eq!(droit(s), None, "inconnu refusé");
        assert_eq!(droit(Situation { admin_config: true, ..s }), Some(Droit::Admin));
        assert_eq!(droit(Situation { liste: true, ..s }), Some(Droit::Autorise), "inscrit, jamais admin");
        assert_eq!(droit(Situation { arrive_par_lien: true, ..s }), Some(Droit::Membre));
        assert_eq!(droit(Situation { membre_salon: true, ..s }), Some(Droit::Membre));
        assert_eq!(droit(Situation { liste: true, membre_salon: true, ..s }), Some(Droit::Autorise));
    }

    #[test]
    fn retour() {
        assert_eq!(retour_sur("/?partie=ab"), "/?partie=ab");
        for r in ["//evil.example", "https://evil.example", "/\\evil", "", "javascript:x"] {
            assert_eq!(retour_sur(r), "/", "{r}");
        }
    }
}

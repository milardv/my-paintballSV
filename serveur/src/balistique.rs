// Même modèle que BalistiquePaintball.cs : bille .68, 3,2 g, Cd 0,47, point milieu à 240 Hz, vent nul.
pub const VITESSE_INITIALE: f32 = 85.344;
const DIAMETRE: f64 = 0.017272;
const MASSE: f64 = 0.0032;
const DENSITE_AIR: f64 = 1.225;
const CD: f64 = 0.47;
const DT: f64 = 1.0 / 240.0;

pub type V3 = [f64; 3];

fn acceleration(v: V3) -> V3 {
    let k = 0.5 * DENSITE_AIR * CD * std::f64::consts::PI * DIAMETRE * DIAMETRE / (4.0 * MASSE);
    let m = norme(v);
    [-k * m * v[0], -9.81 - k * m * v[1], -k * m * v[2]]
}

fn ajoute(a: V3, b: V3, s: f64) -> V3 {
    [a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s]
}

pub fn norme(v: V3) -> f64 {
    (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).sqrt()
}

pub fn distance(a: V3, b: V3) -> f64 {
    norme(ajoute(a, b, -1.0))
}

fn pas(p: V3, v: V3) -> (V3, V3) {
    let milieu = ajoute(v, acceleration(v), DT * 0.5);
    (ajoute(p, milieu, DT), ajoute(v, acceleration(milieu), DT))
}

/// Position de la bille après t secondes (au pas de 240 Hz près, interpolée).
pub fn position_a(origine: V3, vitesse: V3, t: f64) -> V3 {
    let (mut p, mut v, mut ecoule) = (origine, vitesse, 0.0);
    while ecoule + DT <= t {
        (p, v) = pas(p, v);
        ecoule += DT;
    }
    let (suivant, _) = pas(p, v);
    let u = (t - ecoule) / DT;
    ajoute(p, ajoute(suivant, p, -1.0), u)
}

/// Plus courte distance entre la trajectoire et le point, et temps de vol correspondant (s).
pub fn approche(origine: V3, vitesse: V3, point: V3, t_max: f64) -> (f64, f64) {
    let (mut p, mut v, mut t) = (origine, vitesse, 0.0);
    let mut meilleur = (distance(p, point), 0.0);
    while t < t_max {
        let suivant;
        (suivant, v) = pas(p, v);
        // Point du segment [p, suivant] le plus proche.
        let seg = ajoute(suivant, p, -1.0);
        let l2 = seg[0] * seg[0] + seg[1] * seg[1] + seg[2] * seg[2];
        let rel = ajoute(point, p, -1.0);
        let u = if l2 > 0.0 { ((rel[0] * seg[0] + rel[1] * seg[1] + rel[2] * seg[2]) / l2).clamp(0.0, 1.0) } else { 0.0 };
        let d = distance(ajoute(p, seg, u), point);
        if d < meilleur.0 {
            meilleur = (d, t + u * DT);
        }
        p = suivant;
        t += DT;
        if d > meilleur.0 + 5.0 {
            break; // la bille s'éloigne
        }
    }
    meilleur
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tir_horizontal() {
        let v0 = VITESSE_INITIALE as f64;
        // Point sur la trajectoire après 0,2 s : retrouvé à quelques millimètres près.
        let p = position_a([0.0, 1.5, 0.0], [v0, 0.0, 0.0], 0.2);
        let (d, t) = approche([0.0, 1.5, 0.0], [v0, 0.0, 0.0], p, 3.0);
        assert!(d < 0.01 && (t - 0.2).abs() < 0.01, "{d} {t}");
        // La traînée ralentit la bille : moins de 17 m en 0,2 s, et la gravité la fait descendre.
        assert!(p[0] < v0 * 0.2 && p[0] > 12.0 && p[1] < 1.5);
        // Un point à 1 m de côté reste à 1 m.
        let (d, _) = approche([0.0, 1.5, 0.0], [v0, 0.0, 0.0], [10.0, 1.5, 1.0], 3.0);
        assert!((d - 1.0).abs() < 0.05);
    }
}

use qrcode::render::svg;
use qrcode::{EcLevel, QrCode};

/// QR code SVG autonome (fond blanc, zone de silence incluse).
pub fn svg(texte: &str) -> Option<String> {
    let code = QrCode::with_error_correction_level(texte.as_bytes(), EcLevel::M).ok()?;
    Some(code.render::<svg::Color>().min_dimensions(256, 256).quiet_zone(true).build())
}

#[cfg(test)]
mod tests {
    #[test]
    fn qr_svg() {
        let s = super::svg("https://exemple.fr/i/abc.def").unwrap();
        assert!(s.starts_with("<?xml") && s.contains("<svg") && s.contains("<path"));
    }
}

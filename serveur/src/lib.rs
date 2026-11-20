pub mod acces;
pub mod balistique;
pub mod google;
pub mod jeton;
pub mod qr;
pub mod regles;

#[cfg(target_arch = "wasm32")]
mod salle;
#[cfg(target_arch = "wasm32")]
mod web;

// Pont entre le jeu et reseau.js (salon en ligne et WebSocket), voir ClientReseau.cs.
mergeInto(LibraryManager.library, {
  ReseauPret: function (apparitions) { if (window.paintballReseau) window.paintballReseau.unityPret(UTF8ToString(apparitions)); },
  ReseauOuvrirSalon: function (couleur) { if (window.paintballReseau) window.paintballReseau.ouvrir(couleur); },
  ReseauEnvoyer: function (message) { if (window.paintballReseau) window.paintballReseau.envoyer(UTF8ToString(message)); },
  ReseauQuitter: function () { if (window.paintballReseau) window.paintballReseau.quitter(); }
});

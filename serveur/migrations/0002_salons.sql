-- Salons persistants (créés par l'admin, lien permanent) à la place des parties et invitations.
-- Les anciennes parties ne contenaient que des essais : elles ne sont pas reprises.
DROP TABLE IF EXISTS scores;
DROP TABLE IF EXISTS invitations;
DROP TABLE IF EXISTS acces_partie;
DROP TABLE IF EXISTS parties;

CREATE TABLE salons (
  id TEXT PRIMARY KEY,
  nom TEXT NOT NULL,
  -- Secret du lien /s/<cle> (128 bits) ; supprimer le salon invalide le lien.
  cle TEXT NOT NULL UNIQUE,
  cree_par TEXT NOT NULL,
  cree_le INTEGER NOT NULL,
  manches INTEGER NOT NULL DEFAULT 0
);

-- Membres : comptes entrés par le lien (ou l'admin). Donne accès au jeu entier tant que le salon existe.
CREATE TABLE membres (
  salon_id TEXT NOT NULL REFERENCES salons(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  pseudo TEXT NOT NULL,
  couleur INTEGER,
  rejoint_le INTEGER NOT NULL,
  PRIMARY KEY (salon_id, email)
);
CREATE INDEX membres_email ON membres(email);

CREATE TABLE manches (
  salon_id TEXT NOT NULL REFERENCES salons(id) ON DELETE CASCADE,
  numero INTEGER NOT NULL,
  debut INTEGER NOT NULL,
  fin INTEGER NOT NULL,
  gagnant TEXT,
  raison TEXT NOT NULL,
  -- [{pseudo, points, vies}] dans l'ordre du classement.
  classement TEXT NOT NULL,
  PRIMARY KEY (salon_id, numero)
);

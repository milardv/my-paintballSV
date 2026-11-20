-- Liste autorisée. L'admin de configuration (ADMIN_EMAIL) n'a pas besoin d'y figurer.
CREATE TABLE autorises (
  email TEXT PRIMARY KEY,
  admin INTEGER NOT NULL DEFAULT 0,
  ajoute_par TEXT NOT NULL,
  ajoute_le INTEGER NOT NULL
);

CREATE TABLE comptes (
  email TEXT PRIMARY KEY,
  nom TEXT NOT NULL,
  premiere_connexion INTEGER NOT NULL,
  derniere_connexion INTEGER NOT NULL
);

CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  cree_le INTEGER NOT NULL,
  expire_le INTEGER NOT NULL,
  revoquee INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX sessions_email ON sessions(email);

CREATE TABLE parties (
  id TEXT PRIMARY KEY,
  nom TEXT NOT NULL,
  createur TEXT NOT NULL,
  etat TEXT NOT NULL DEFAULT 'lobby' CHECK (etat IN ('lobby', 'en_cours', 'terminee')),
  cree_le INTEGER NOT NULL,
  debut INTEGER,
  fin INTEGER,
  gagnant TEXT,
  raison TEXT
);

-- Qui peut entrer dans quelle partie (créateur, invitation ouverte par un inscrit,
-- ou e-mail autorisé automatiquement par une invitation).
CREATE TABLE acces_partie (
  partie_id TEXT NOT NULL REFERENCES parties(id),
  email TEXT NOT NULL,
  source TEXT NOT NULL,
  ajoute_le INTEGER NOT NULL,
  PRIMARY KEY (partie_id, email)
);
CREATE INDEX acces_partie_email ON acces_partie(email);

CREATE TABLE invitations (
  id TEXT PRIMARY KEY,
  partie_id TEXT NOT NULL REFERENCES parties(id),
  auto INTEGER NOT NULL DEFAULT 0,
  cree_le INTEGER NOT NULL,
  expire_le INTEGER NOT NULL,
  revoquee INTEGER NOT NULL DEFAULT 0,
  utilisations INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE scores (
  partie_id TEXT NOT NULL REFERENCES parties(id),
  email TEXT NOT NULL,
  nom TEXT NOT NULL,
  points INTEGER NOT NULL,
  vies INTEGER NOT NULL,
  elimine INTEGER NOT NULL,
  rang INTEGER NOT NULL,
  PRIMARY KEY (partie_id, email)
);

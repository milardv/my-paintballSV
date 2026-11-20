-- Sessions invité : ouvertes par le lien d'un salon, sans Google, liées à ce salon.
-- Supprimer le salon ou régénérer son lien les révoque.
ALTER TABLE sessions ADD COLUMN salon_id TEXT;
CREATE INDEX sessions_salon ON sessions(salon_id);

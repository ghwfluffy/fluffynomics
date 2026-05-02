ALTER TABLE users
  ADD COLUMN IF NOT EXISTS identity_provider TEXT,
  ADD COLUMN IF NOT EXISTS external_subject TEXT,
  ADD COLUMN IF NOT EXISTS central_avatar_url TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_identity_provider_external_subject
  ON users (identity_provider, external_subject)
  WHERE identity_provider IS NOT NULL AND external_subject IS NOT NULL;

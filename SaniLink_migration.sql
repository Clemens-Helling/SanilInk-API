-- ============================================
-- SaniLink Migration Script
-- Für bestehende Datenbanken (idempotent)
-- ============================================

-- 1. Users Tabelle erweitern (nur wenn Spalten noch nicht existieren)
ALTER TABLE "users" 
ADD COLUMN IF NOT EXISTS "email" varchar(255),
ADD COLUMN IF NOT EXISTS "username" varchar(255);

-- 2. Bestehende User mit Default-Werten füllen
UPDATE "users" 
SET "email" = 'placeholder_' || "User_ID"::text,
    "username" = 'user_' || "User_ID"::text
WHERE "email" IS NULL OR "username" IS NULL;

-- 3. NOT NULL Constraints hinzufügen (nur wenn noch nicht vorhanden)
ALTER TABLE "users"
ALTER COLUMN "email" SET NOT NULL,
ALTER COLUMN "username" SET NOT NULL;

-- 4. UNIQUE Constraints hinzufügen (nur wenn noch nicht vorhanden)
ALTER TABLE "users"
ADD CONSTRAINT uk_users_email UNIQUE ("email") ON CONFLICT DO NOTHING;

ALTER TABLE "users"
ADD CONSTRAINT uk_users_username UNIQUE ("username") ON CONFLICT DO NOTHING;

-- 5. user_sessions Tabelle erstellen (nur wenn nicht vorhanden)
CREATE TABLE IF NOT EXISTS "user_sessions" (
  "session_id" varchar(255) PRIMARY KEY,
  "User_ID" integer NOT NULL,
  "access_token" varchar(500),
  "refresh_token" varchar(500),
  "token_expires_at" timestamp,
  "created_at" timestamp DEFAULT CURRENT_TIMESTAMP,
  "is_active" boolean DEFAULT true,
  FOREIGN KEY ("User_ID") REFERENCES "users" ("User_ID") ON DELETE CASCADE DEFERRABLE INITIALLY IMMEDIATE
);

-- 6. Indexes für Performance (nur wenn nicht vorhanden)
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON "user_sessions"("User_ID");
CREATE INDEX IF NOT EXISTS idx_user_sessions_access_token ON "user_sessions"("access_token");
CREATE INDEX IF NOT EXISTS idx_user_sessions_is_active ON "user_sessions"("is_active");

-- 7. user_keys Tabelle — hmac_verifier Feld hinzufügen (optional, nur wenn nicht vorhanden)
ALTER TABLE "user_keys" 
ADD COLUMN IF NOT EXISTS "hmac_verifier" varchar(64);

-- ============================================
-- Fertig! Die restliche DB-Struktur bleibt unverändert
-- ============================================

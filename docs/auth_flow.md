# Registrierung & Login — Architekturübersicht

Dieses Dokument fasst kurz und präzise zusammen, wie die Registrierung (Onboarding)
und der Login (SCRAM-artiger Challenge/Proof-Flow) in SaniLinkAPI funktionieren sollen.
Es beschreibt welche Daten übertragen werden, welche Funktionen dafür zuständig sind
und welche DB-Felder/Endpoints/Tests empfohlen werden.

Hinweis: Die Implementierung folgt dem Zero‑Knowledge‑Prinzip — der Server darf
keinen Klartext des Private Keys oder des hmac_key kennen.

---

## 1. High‑Level Ablauf

- Registrierung (Client-seitig):
  1. Client erzeugt X25519-Keypair (User).
  2. Client erzeugt GEK (Group Encryption Key) für den Tenant.
  3. Client verschlüsselt den Private Key mit Passwort (Argon2id → SecretBox + HMAC).
  4. Client verpackt den GEK in einen `customer_key_slot` für sich selbst (NaCl Box, ephemeral keypair).
  5. Client sendet an Server nur: `public_key`, `encrypted_private_key`, `argon2_salt`, `hmac_verifier`, `stored_key`, und den `customer_key_slot`.
  6. Server legt Tenant, User, `user_keys` und `customer_key_slots` atomar in einer Transaktion an.

- Login (Challenge/Proof):
  1. Client fordert Challenge an (Server erzeugt `challenge_nonce`).
  2. Server speichert Challenge als single‑use mit TTL.
  3. Client erzeugt `client_proof = hmac_key XOR HMAC(stored_key, challenge_nonce)` und sendet diesen.
  4. Server verifiziert: rekonstruiert `hmac_key` und prüft `sha256(recovered_hmac_key) == stored_key`.
  5. Bei Erfolg: Session/JWT ausgeben.

---

## 2. Zuordnung Funktionen (Codeorte)

- Client‑Hilfsfunktionen (in Tests / Client‑Lib):
  - `generate_keypair()` — erzeugt X25519 Keypair (`tests/client_crypto.py`).
  - `generate_gek()` — erzeugt zufälligen GEK (`tests/client_crypto.py`).
  - `build_client_proof(hmac_key, challenge_nonce)` — erzeugt client proof (`tests/client_crypto.py` oder `app/core/crypto.py` client helper).

- Gemeinsame Crypto‑Utilities (`app/core/crypto.py`):
  - `derive_key_and_hmac(password, salt)` — Argon2id → (encryption_key, hmac_key)
  - `encrypt_private_key_with_password(...)` / `decrypt_private_key_with_password(...)` — SecretBox + HMAC
  - `build_registration_crypto_envelope(...)` — erzeugt `{encrypted_private_key, argon2_salt, hmac_verifier, stored_key}`
  - `build_stored_key(hmac_key)` — `SHA256(hmac_key)`
  - `generate_challenge_nonce()` — erstellt sichere Nonce
  - `build_client_proof(...)` / `verify_client_proof(...)` — Proof‑Logik

---

## 3. Detaillierte Requests / Payloads

Empfohlenes JSON (hex- oder base64-kodierte Binärwerte):

Registration (Client → Server)
```json
POST /auth/register
{
  "tenant_name": "acme-corp",
  "username": "alice",
  "public_key": "<hex>",
  "encrypted_private_key": "<hex>",
  "argon2_salt": "<hex>",
  "hmac_verifier": "<hex>",
  "stored_key": "<hex>",
  "encrypted_gek_slot": "<hex>",
  "ephemeral_pubkey": "<hex>"
}
```

Challenge anfordern (Client → Server)
```json
POST /auth/challenge
{ "username": "alice" }
```

Server → Client (Challenge)
```json
{ "challenge": "<base64url>" }
```

Proof senden (Client → Server)
```json
POST /auth/verify-proof
{ "username": "alice", "client_proof": "<base64url>" }
```

---

## 4. Welche Felder speichert der Server?

Tabelle `user_keys` (empfohlen):
- `user_id` (FK)
- `public_key` (bytea / hex)
- `encrypted_private_key` (bytea / hex)
- `argon2_salt` (bytea / hex)
- `hmac_verifier` (bytea / hex)  // HMAC(hmac_key, encrypted_private_key)
- `stored_key` (bytea / hex)     // SHA256(hmac_key)

Tabelle `customer_key_slots` (empfohlen):
- `tenant_id`, `user_id`
- `encrypted_gek` (bytea / hex)
- `ephemeral_pubkey` (bytea / hex)

Tabelle `login_challenges` (für Login):
- `nonce` (bytea / hex)
- `user_id`
- `used` (bool)
- `expires_at` (timestamp)

Hinweis: Falls Migration aktuell `varchar(64)` für HMAC/Stored-Key vorsieht, speichere `.hex()`; besser wäre `BYTEA`/`BINARY(32)`.

---

## 5. Atomarität & Fehlerfälle

- Registrierung und Anlegen von Tenant/User/KeySlot müssen in einer DB‑Transaktion geschehen — sonst können halbfertige Einträge entstehen.
- Validierungen serverseitig:
  - Längenprüfungen (public_key Länge, salt 16 bytes, hmac_verifier 32 bytes, stored_key 32 bytes)
  - Unique Constraints (z. B. `(tenant_id, user_id)` in `customer_key_slots`)
  - Auf Fehler: Rollback und aussagekräftige HTTP‑Fehler zurückgeben

---

## 6. Security‑Hinweise

- Immer TLS (HTTPS) verwenden.
- Challenge TTL kurz wählen (z. B. 2–5 Minuten) und single‑use erzwingen (atomisch markieren/loeschen).
- Rate‑Limit Registration/Challenge‑Endpoints.
- Keine sensiblen Schlüssel in Logs oder JWTs serialisieren.

---

## 7. Tests (empfohlen)

- Unit Tests:
  - `build_registration_crypto_envelope` liefert korrekte Felder
  - `build_customer_key_slot` / `unwrap_customer_key_slot` Roundtrip
  - `build_client_proof` / `verify_client_proof` positiv/negativ
  - Längen-/TypeError Tests

- Integration Tests:
  - `POST /auth/register` speichert alle Tabellenzeilen atomar
  - Challenge → Proof → Verify → Token flow

---

## 8. Nächste Implementationsschritte (Priorisiert)

1. Implementiere `build_customer_key_slot(gek, recipient_pubkey)` + `unwrap_customer_key_slot(...)` (NaCl Box + ephemeral keypair).
2. Implementiere `auth.service.register_user(...)` (Transaktion: Tenant, User, user_keys, customer_key_slots).
3. Implementiere Endpoints `/auth/register`, `/auth/challenge`, `/auth/verify-proof` + zugehörige Pydantic‑Schemas.
4. Schreibe Unit‑ und Integrationstests für die obigen Punkte.

---

Wenn du möchtest, implementiere ich direkt Punkt 1 (GEK‑Slot Verpackung + Tests) — sag mir nur, ob du die Funktion in `app/core/crypto.py` oder in einer neuen `app/core/encryption.py` haben willst.


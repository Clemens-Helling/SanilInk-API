# SaniLinkAPI – Kontext für GitHub Copilot

## Projektüberblick

**SaniLinkAPI** ist ein self-hosted, multi-tenant FastAPI-Backend zur Verwaltung
verschlüsselter Patientendaten (sensible Felder: Namen, Geburtsdaten). Kernziel ist
eine **Zero-Knowledge Envelope-Encryption-Architektur**: Der Server sieht niemals
Klartext-Passwörter, private Schlüssel oder Patientendaten. Leitprinzipien:
Security-first mit expliziter Tradeoff-Bewertung, sowie "start simple, defer complexity".

## Tech-Stack

- Python, FastAPI
- SQLAlchemy (async), asyncpg, PostgreSQL mit Row-Level Security (RLS)
- PyNaCl / libsodium, argon2-cffi
- Alembic (async-Konfiguration)
- JWT (kurzlebige Access- + Refresh-Tokens) für Session-Auth oberhalb des E2E-Schemas

## Kryptografische Architektur (bestätigte Entscheidungen)

- Ein **GEK (Group Encryption Key)** pro Tenant verschlüsselt alle Patientendaten.
- GEK wird über **per-user encrypted key slots** verteilt (`customer_key_slots`-Tabelle).
- **X25519 + XSalsa20-Poly1305** (NaCl Box, mit Ephemeral-Keypairs) für GEK-Slots.
- **XSalsa20-Poly1305** (NaCl SecretBox, symmetrisch) für Patientenfelder.
- **Argon2id** schützt X25519-Private-Keys at rest; Nonces sind immer im Ciphertext
  eingebettet (keine separaten Nonce-Spalten).
- **SCRAM-artiger HMAC-Login**:
  `stored_key = SHA256(hmac_key)` (serverseitig),
  `ClientProof = hmac_key XOR HMAC(stored_key, challenge_nonce)` –
  bindet den Proof an eine Single-Use-Nonce, replay-sicher. Bewusst gewählt statt
  statischem HMAC oder Speicherung des rohen hmac_key.

## Multi-Tenancy

- PostgreSQL RLS als **Defense-in-Depth**; Verschlüsselung macht Daten auch bei
  Breach unbrauchbar.
- Separate Datenbanken pro Tenant wurden explizit **abgelehnt** zugunsten von
  Shared Schema + RLS (operative Einfachheit).

## DB-Schema (Tabellen)

- `user_keys` – public_key, encrypted_private_key, argon2_salt, hmac_verifier
- `customer_key_slots` – encrypted_gek, ephemeral_pubkey (unique constraint auf
  `tenant_id + user_id`)
- `login_challenges` – single-use Nonces, DB-backed mit atomarem
  `UPDATE ... WHERE used=false RETURNING`
- `patients`
- `user_invitations`

## Projektstruktur

Domain-basiert, jeweils mit `router.py`, `models.py`, `schemas.py`, `service.py`:

```
app/
  auth/
  users/
  tenants/
  patients/
  encryption/
tests/          # liegt NEBEN app/, nicht darin
  client_crypto.py
```

- `client_crypto.py` simuliert reine Client-Krypto-Logik (kein DB-/HTTP-Zugriff).
  Bestätigte Entscheidungen dort:
  - `bytes(box.encrypt(private_key))` für embedded-nonce combined ciphertext ("Option B")
  - `hmac_verifier` bewusst als DB-Feld beibehalten
  - GEK-Wrapping/Unwrapping via NaCl Box mit expliziten Ephemeral-Keypairs
  - Keypair-Generierung und Private-Key-Schutz laufen client-seitig, nie im Server

- **SQLModel wurde explizit abgelehnt** – separate SQLAlchemy-Modelle
  (Ciphertext-Bytes) und Pydantic-Schemas (Klartext-Exposition) passen besser
  zur Architektur.

## Aktuell in Arbeit / als Nächstes

- **User-Onboarding/Invitation-Flow**: Admin erstellt Invitation → neuer User
  registriert sich und übermittelt Public Key → Admin entschlüsselt eigenen GEK
  und verschlüsselt ihn neu für den neuen User. Unique Constraint auf
  `(tenant_id, user_id)` in `customer_key_slots` löst Race Condition bei
  gleichzeitiger Grant-Vergabe durch zwei Admins.
- Rollenbasierte Rechte (admin/member enum) – offene Frage: Rollen direkt auf
  `users` oder in separater `tenant_memberships`-Tabelle?
- **Recovery-Key-Design**: Wird als normaler `customer_key_slots`-Eintrag behandelt.
  High-Entropy-Mnemonic → deterministisches X25519-Keypair via
  `crypto_box_seed_keypair(seed)` (client-seitig). Single-Use-Prinzip (Rotation
  nach Gebrauch). Schneller Hash (SHA-256/BLAKE2b) als Verifier statt Argon2id
  (Entropie bereits hoch). Offen: Scope (persönliche Recovery vs. Tenant-Break-Glass).
- Restliche Bereiche von `client_crypto.py`: vollständiger zweistufiger
  Login-Crypto-Flow, Patient-Field-Encryption-Helpers (deferred phase)
- Alembic async-Konfiguration (`async_engine_from_config` + `run_sync`-Bridge;
  RLS-Policies via manuellem `op.execute`)

## Explizit verschoben (deferred)

- Redis
- Per-Department-GEKs
- Patient-Field-Helpers
- Key Escrow
- Sentry Cloud (stattdessen self-hosted **GlitchTip**, wegen DSGVO/Patientendaten)

## Wichtige Prinzipien & Learnings

- **Zero-Knowledge strikt durchgesetzt**: Server sieht nie Passwörter, private
  Keys im Klartext oder GEK im Klartext – GEK liegt nur kurz im RAM während
  aktiver Sessions. Leak-Vektoren im Blick behalten: Debug-Logging,
  Memory-Extraction, fehlkonfiguriertes TLS, versehentliche Serialisierung in
  JWTs/Redis/Caches.
- **GEK-Offboarding = Slot-Löschung, keine Rotation.** Rotation nur bei aktivem Compromise.
- **Mindestens zwei Admins pro Tenant** organisatorisch durchsetzen, um
  irreversiblen Datenverlust bei Passwortverlust des einzigen Keyholders zu vermeiden.
- **RLS + Verschlüsselung = Defense-in-Depth**, nicht redundant – beide decken
  unterschiedliche Failure-Modes ab.
- SCRAM-artiger Login statt statischem HMAC (replay-anfällig) oder rohem
  hmac_key (sofort nutzbares Credential bei DB-Compromise).
- **SQLite kann nicht für Tests genutzt werden** – RLS braucht echtes PostgreSQL;
  testcontainers-python oder dediziertes docker-compose-Testservice mit
  Per-Test-Transaction-Rollback verwenden.
- Architektur- und Tradeoff-Diskussion kommt vor Implementierungscode.

## Konventionen

- Primäre Arbeitssprache: **Deutsch**; Code-Kommentare auf Deutsch
- Teststrategie: `tests/client_crypto.py` für isolierte Crypto-Unit-Tests +
  pytest + `httpx.AsyncClient` für Integrationstests + dedizierte
  RLS-Tenant-Isolation-Tests
- Antworten/Vorschläge bevorzugt strukturiert, mit Headers

## Tools & Referenzen

- PyNaCl, argon2-cffi, SQLAlchemy 2.0 async (aktuelle Docs, nicht veraltete
  Sync-Tutorials), asyncpg, Alembic, FastAPI
- GlitchTip (self-hosted, Sentry-Protocol-kompatibel; `send_default_pii=False`,
  `max_request_body_size="never"`, custom `before_send`-Scrubber für sensible Felder)
- 1Password (`op` CLI) für Secrets-Injection
- DigitalOcean (GitHub Student Pack) für Staging
- libsodium-Docs, PyNaCl-Docs, *Serious Cryptography* (Aumasson),
  RFC 5802 (SCRAM), RFC 9106 (Argon2-Parameter)
# SaniLinkAPI – Kryptografischer Ablauf (Registrierung, Login, Datenverschlüsselung)

> Referenzdokument für KI-Assistenten, die an der SaniLink-Codebase arbeiten.
> Zero-Knowledge-Architektur: Der Server sieht **niemals** Passwörter, private Schlüssel, den Group Encryption Key (GEK) oder Patienten-Klartext.

---

## 1. Kryptografische Bausteine

| Zweck                                  | Primitive                                                                   |
| -------------------------------------- | --------------------------------------------------------------------------- |
| Schlüsselpaar pro User                 | X25519 (asymmetrisch)                                                       |
| GEK-Verteilung an User (Key Slots)     | NaCl `Box` (X25519 + XSalsa20-Poly1305), ephemerer Sender-Schlüssel         |
| Patientenfeld-Verschlüsselung          | NaCl `SecretBox` (XSalsa20-Poly1305), Nonce wird im Ciphertext mitgeführt   |
| Schutz des privaten Schlüssels at rest | Argon2id → symmetrischer Schlüssel → `SecretBox`                            |
| Login-Proof                            | SCRAM-artiges HMAC-Verfahren (siehe Abschnitt 3)                            |
| Timing-sichere Vergleiche              | `hmac.compare_digest` (Server-seitig, überall wo Secrets verglichen werden) |

**Wichtig – Domain Separation:** Aus dem Passwort werden **zwei unabhängige** Schlüssel abgeleitet, mit unterschiedlichen Argon2id-Parametern/Labels, damit sie sich nicht gegenseitig kompromittieren:

- `key_encryption_key` → verschlüsselt den privaten X25519-Schlüssel at rest
- `hmac_key` → wird für den SCRAM-Login-Proof verwendet

Diese dürfen **nicht** aus derselben Argon2id-Ableitung ohne unterschiedliches Salt/Info-Label stammen.

---

## 2. Registrierung

Alle Schritte mit „Client" laufen ausschließlich im Frontend / in `client_crypto.py` (Test-Simulation). Der Server bekommt nur die als „→ Server" markierten Werte.

1. **Client:** X25519-Schlüsselpaar generieren → `(public_key, private_key)`
2. **Client:** Nutzer gibt Passwort ein
3. **Client:** Argon2id-Ableitung #1 (Salt A, Label „key-enc") → `key_encryption_key`
4. **Client:** `encrypted_private_key = SecretBox(key_encryption_key).encrypt(private_key)`
5. **Client:** Argon2id-Ableitung #2 (Salt B, Label „hmac") → `hmac_key`
6. **Client:** `stored_key = SHA256(hmac_key)`
7. **Client (nur wenn erster User im Tenant):** GEK generieren = 32 zufällige Bytes
8. **Client:** GEK für diesen User verschlüsseln:
   `gek_box = Box(ephemeral_private_key, user.public_key).encrypt(GEK)` (ephemeres Sender-Schlüsselpaar, wird verworfen)
9. **→ Server (persistiert, alles opak):**
   - `public_key`
   - `encrypted_private_key` + Argon2id-Parameter (Salt A, time_cost, memory_cost, parallelism)
   - `stored_key`
   - Argon2id-Parameter für `hmac_key`-Ableitung (Salt B, …)
   - Eintrag in `customer_key_slots`: `{user_id, tenant_id, ephemeral_public_key, encrypted_gek (inkl. Nonce)}`

Der Server kann zu keinem Zeitpunkt `private_key`, `hmac_key`, `key_encryption_key` oder `GEK` im Klartext sehen oder rekonstruieren.

---

## 3. Login (SCRAM-artiger Ablauf)

Ziel: Beweis, dass der Client das Passwort kennt, **ohne** ein statisches, replay-fähiges Geheimnis über die Leitung zu schicken.

1. **Client → Server:** Login-Request mit Username/E-Mail
2. **Server:** generiert `challenge_nonce` (kryptografisch zufällig, single-use, kurzlebig, an Session/Request gebunden) und sendet ihn zusammen mit den gespeicherten Argon2id-Parametern zurück
3. **Client:** leitet `hmac_key` erneut aus Passwort + Salt B ab (Argon2id, Label „hmac")
4. **Client:** berechnet
   ```
   ClientSignature = HMAC(stored_key, challenge_nonce)
   ClientProof     = hmac_key XOR ClientSignature
   ```
5. **Client → Server:** sendet `ClientProof` (+ Referenz auf `challenge_nonce`)
6. **Server:** verifiziert, ohne `hmac_key` je gesehen zu haben:
   ```
   ClientSignature' = HMAC(stored_key, challenge_nonce)   # stored_key ist bekannt
   hmac_key'        = ClientProof XOR ClientSignature'
   gültig           = compare_digest(SHA256(hmac_key'), stored_key)
   ```
7. **Server:** `challenge_nonce` wird nach Verwendung sofort invalidiert (single-use → verhindert Replay)
8. Bei Erfolg: Server stellt Session/JWT aus. Server hat zu keinem Zeitpunkt `hmac_key` gespeichert oder dauerhaft vorgehalten.

---

## 4. Entsperren des privaten Schlüssels & der GEK (nach erfolgreichem Login)

Läuft vollständig client-seitig, direkt im Anschluss an Schritt 3.8:

1. **Client:** Argon2id-Ableitung #1 erneut (Salt A, Label „key-enc") → `key_encryption_key`
2. **Client:** `private_key = SecretBox(key_encryption_key).decrypt(encrypted_private_key)`
3. **Client:** ruft eigenen Eintrag aus `customer_key_slots` ab (`ephemeral_public_key`, `encrypted_gek`)
4. **Client:** `GEK = Box(private_key, ephemeral_public_key).decrypt(encrypted_gek)`
5. `GEK` verbleibt nur im Client-Arbeitsspeicher (nie persistiert, nie an Server gesendet)

---

## 5. Patientendaten – Ver-/Entschlüsselung

- **Schreiben:** Client verschlüsselt jedes sensible Feld einzeln mit `SecretBox(GEK).encrypt(plaintext)`; Nonce wird vorangestellt/eingebettet im Ciphertext-Blob. Server erhält nur den Ciphertext-Blob.
- **Lesen:** Server liefert Ciphertext-Blob aus (nach RLS-Filterung auf `tenant_id`), Client entschlüsselt mit `SecretBox(GEK).decrypt(...)`.
- **Server-Rolle:** rein als verschlüsselter Speicher + Zugriffskontrolle (RLS als Defense-in-Depth zusätzlich zur Verschlüsselung, nicht als Ersatz).

---

## 6. Anonyme Selbstdokumentation (Intake via Sealed Box)

**Use Case:** Eine nicht im System angelegte Person (z. B. Ersthelfer-Fall, "nimmt nur ein Pflaster") dokumentiert einen Vorfall selbst, ohne Login und ohne eigenen Key-Slot – typischerweise via QR-Code am Verbandskasten, auf dem eigenen Handy.

Das GEK-Modell (Abschnitt 4–5) setzt einen eingeloggten User mit Key-Slot voraus und passt hier nicht direkt. Statt eines Single-Use-Tokens (der einen dauerhaft aushängbaren QR-Code unbrauchbar machen würde) wird **NaCl Sealed Box** (`crypto_box_seal`) verwendet: asymmetrische Verschlüsselung, bei der der Sender **keinerlei eigenes Secret** braucht – nur den öffentlichen Schlüssel des Empfängers.

### 6.1 Einmaliges Setup (durch eingeloggten Mitarbeiter, pro Standort/Verbandskasten)

1. **Client:** X25519-Schlüsselpaar generieren (unabhängig vom User-Keypair) → `(intake_public_key, intake_private_key)`
2. **Client:** `encrypted_intake_private_key = SecretBox(GEK).encrypt(intake_private_key)` (GEK liegt in der Session bereits im RAM)
3. **→ Server (persistiert, opak):** Eintrag in `intake_keys`: `{tenant_id, label, intake_public_key (Klartext), encrypted_intake_private_key (inkl. Nonce), created_by}`
4. `intake_public_key` wird als QR-Code/Link ausgegeben – **dauerhaft gültig**, da nicht geheim (kein Single-Use nötig, kein Ablauf erforderlich)

### 6.2 Einreichung durch die betroffene Person (kein Login, kein Key-Slot)

1. QR-Code scannen → Formular öffnet sich im Browser (PWA/Mobile-Web)
2. Person füllt Vorfall-Angaben aus
3. **Client:** `sealed_payload = crypto_box_seal(plaintext, intake_public_key)` – funktioniert ohne jedes Secret auf Client-Seite
4. **→ Server:** Eintrag in `pending_intakes`: `{tenant_id, intake_key_id, sealed_payload, status="pending"}`

Der Server sieht zu keinem Zeitpunkt Klartext, Token oder Schlüssel – identisch zum Grundprinzip aus Abschnitt 5.

### 6.3 Sichtung & Übernahme (durch eingeloggten Mitarbeiter)

1. Nach Login: `GEK` liegt wie gewohnt im RAM (Abschnitt 4)
2. **Client:** ruft offene `pending_intakes` + zugehörige `intake_keys`-Einträge ab
3. **Client:** `intake_private_key = SecretBox(GEK).decrypt(encrypted_intake_private_key)`
4. **Client:** `plaintext = crypto_box_seal_open(sealed_payload, intake_public_key, intake_private_key)`
5. Automatisches Entschlüsseln + Anzeigen als Inbox ("2 offene Selbstmeldungen") ist unkritisch und kann beim Login automatisch laufen
6. **Kein Auto-Save als Patientendatensatz** – Mitarbeiter prüft/ergänzt, bestätigt explizit (Compliance + Missbrauchsrisiko am unauthentifizierten Endpoint)
7. Bei Bestätigung: Client verschlüsselt final regulär mit `SecretBox(GEK)` → neuer `patients`-Eintrag; `pending_intakes.status = "claimed"`, `resulting_patient_id` gesetzt

### 6.4 Sicherheits-/Betriebsaspekte

- **1 Intake-Key pro QR-Code/Standort** (nicht ein globaler Key pro Tenant): ermöglicht Herkunftszuordnung ohne Freitextfeld und granularen Widerruf, falls ein QR-Code kompromittiert wird (`revoked_at` statt Hard-Delete, damit bereits eingereichte `pending_intakes` weiter entschlüsselbar bleiben)
- `POST /intake/{intake_key_id}/submit` ist der einzige unauthentifizierte Schreibendpoint im System → striktes Rate-Limiting (pro IP **und** pro `intake_key_id`) ist Pflicht, kein Redis-Verzicht-Ausnahme diskutiert (siehe Abschnitt 9)
- Automatisches Übernehmen in `patients` **ohne** menschliche Bestätigung ist bewusst ausgeschlossen (Fehlerpotential bei Laien-Angaben + fehlende Authentifizierung des Einreichers)

---

## 7. Betroffene Datenbank-Tabellen (Schema-Ebene)

| Tabelle              | Relevante Felder (opak für Server)                                                                                                                                         |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `users`              | `public_key`, `encrypted_private_key`, Argon2id-Parameter (Salt A/B, time_cost, memory_cost, parallelism), `stored_key`                                                    |
| `customer_key_slots` | `user_id`, `tenant_id`, `slot_type` (`login` \| `personal_recovery` \| `tenant_breakglass`), `ephemeral_public_key`, `encrypted_gek` (inkl. Nonce)                         |
| `patients`           | verschlüsselte Feld-Blobs (SecretBox-Ciphertext inkl. Nonce), `tenant_id` (Klartext, für RLS nötig)                                                                        |
| `intake_keys`        | `tenant_id`, `label`, `public_key` (Klartext, bewusst öffentlich), `encrypted_private_key` (via GEK, inkl. Nonce), `created_by`, `revoked_at`                              |
| `pending_intakes`    | `tenant_id`, `intake_key_id`, `sealed_payload` (Sealed-Box-Ciphertext), `status` (`pending` \| `claimed` \| `rejected` \| `expired`), `claimed_by`, `resulting_patient_id` |

RLS-Policies filtern serverseitig strikt nach `tenant_id`; das ersetzt nicht die Verschlüsselung, sondern ergänzt sie.

---

## 8. Sicherheitsinvarianten (dürfen von keiner Implementierung verletzt werden)

1. Server sieht niemals: Passwort, `hmac_key`, `key_encryption_key`, `private_key`, `GEK`, Patienten-Klartext.
2. Jeder `challenge_nonce` ist single-use – kein statischer Proof-Wert wird je zweimal akzeptiert.
3. Alle Secret-Vergleiche serverseitig laufen über `hmac.compare_digest` (timing-safe).
4. `key_encryption_key` und `hmac_key` werden mit unterschiedlichem Salt/Label abgeleitet (Domain Separation) – niemals derselbe abgeleitete Wert für beide Zwecke.
5. GEK-Offboarding eines Users = Löschen seines Slots in `customer_key_slots`, **keine** GEK-Rotation (Rotation ist reserviert für aktive Kompromittierungsfälle).
6. Kein externes HMAC über SecretBox-Ciphertext (Poly1305 liefert bereits Authentizität – redundant und wurde bewusst entfernt).
7. Automatisches Übernehmen von `pending_intakes` in `patients` ohne explizite menschliche Bestätigung ist untersagt (Auto-Decrypt/Anzeige ist ok, Auto-Promote nicht).

---

## 9. Bewusst noch offene / vertagte Punkte

- **Rollen-Modellierung:** auf `users`-Tabelle direkt oder eigene `tenant_memberships`-Tabelle? (Nicht entschieden – betrifft auch: wer darf Intake-Keys anlegen/widerrufen?)
- **Recovery-Key-Flow:** Scope unklar – persönliche Passwort-Wiederherstellung vs. tenant-weiter Break-Glass-Zugriff. Geplantes Muster (sobald Scope steht): High-Entropy-Mnemonic → deterministisches X25519-Keypair via `crypto_box_seed_keypair(seed)` → normaler Eintrag in `customer_key_slots`; Single-Use-Rotation-Prinzip.
- **Intake-Key-Management:** Rate-Limiting-Strategie für den unauthentifizierten Submit-Endpoint (DB-basiertes Sliding-Window analog zu Login-Nonces, oder doch Ausnahme vom Redis-Verzicht?); Aufbewahrungs-/Löschfrist für unbeanspruchte `pending_intakes`.
- **Explizit out of scope (aktuell):** Redis, Per-Department-GEKs, Key Escrow, vollständige Recovery-Key-Implementierung, Dual-Control für Break-Glass.

---

## 10. Implementierungs-Hinweise für KI-Assistenten

- Separate SQLAlchemy-Models und Pydantic-Schemas (kein SQLModel).
- Async SQLAlchemy 2.0 + asyncpg, Alembic async-kompatibel (`async_engine_from_config`, `run_sync`-Bridge).
- RLS-Policies werden von Alembic-Autogenerate **nicht** erkannt → immer manuell per `op.execute()` ergänzen und Migration-Datei review­en, inkl. Downgrade-Pfad testen.
- Tests gegen echte PostgreSQL (nicht SQLite) – RLS lässt sich mit SQLite nicht validieren. `tests/` liegt auf Projekt-Root-Ebene, nicht in `app/`.
- `tests/client_crypto.py` simuliert alle Client-seitigen Krypto-Operationen aus diesem Dokument für Integrationstests.

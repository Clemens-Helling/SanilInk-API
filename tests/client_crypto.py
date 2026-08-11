from dataclasses import dataclass
import hashlib
import hmac

from argon2.low_level import Type, hash_secret_raw
from nacl.secret import SecretBox
from nacl.utils import random as nacl_random


ARGON2_SALT_SIZE = 16
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 64
KEY_SIZE = 32
HMAC_SIZE = 32
CHALLENGE_NONCE_SIZE = 32


@dataclass(frozen=True, slots=True)
class PrivateKeyEnvelope:
	"""
	Ergebnis der Client-seitigen Verschlüsselung des Private Keys.

	Hinweis: Kein separater Integritäts-MAC über das Ciphertext-Blob nötig -
	SecretBox (XSalsa20-Poly1305) ist bereits authentifizierte Verschlüsselung.
	box.decrypt() schlägt automatisch fehl, wenn das Blob manipuliert wurde.
	"""
	encrypted_private_key: bytes
	argon2_salt: bytes


@dataclass(frozen=True, slots=True)
class ChallengeProofResult:
	valid: bool
	recovered_hmac_key: bytes | None = None


@dataclass(frozen=True, slots=True)
class RegistrationCryptoEnvelope:
	"""
	Alles, was bei der Registrierung an den Server geht.

	stored_key = SHA256(hmac_key) wird serverseitig in user_keys.hmac_verifier
	persistiert und dient ausschließlich dem SCRAM-artigen Login-Beweis.
	"""
	encrypted_private_key: bytes
	argon2_salt: bytes
	stored_key: bytes


def derive_key_and_hmac(password: str, argon2_salt: bytes) -> tuple[bytes, bytes]:
	if not isinstance(password, str):
		raise TypeError("password must be a string")
	if not isinstance(argon2_salt, (bytes, bytearray)):
		raise TypeError("argon2_salt must be bytes")

	raw_key_material = hash_secret_raw(
		secret=password.encode("utf-8"),
		salt=bytes(argon2_salt),
		time_cost=ARGON2_TIME_COST,
		memory_cost=ARGON2_MEMORY_COST,
		parallelism=ARGON2_PARALLELISM,
		hash_len=ARGON2_HASH_LEN,
		type=Type.ID,
	)

	# Domain-Separation: encryption_key und hmac_key sind zwei disjunkte
	# Hälften des Argon2id-Outputs und werden für unterschiedliche Zwecke
	# genutzt (Verschlüsselung vs. Login-Beweis) - keine Wiederverwendung
	# desselben Rohschlüssels in zwei kryptographischen Rollen.
	return raw_key_material[:KEY_SIZE], raw_key_material[KEY_SIZE:ARGON2_HASH_LEN]


def build_stored_key(hmac_key: bytes) -> bytes:
	if not isinstance(hmac_key, (bytes, bytearray)):
		raise TypeError("hmac_key must be bytes")
	if len(hmac_key) != KEY_SIZE:
		raise ValueError(f"hmac_key must be {KEY_SIZE} bytes")
	return sha256_bytes(bytes(hmac_key))


def generate_challenge_nonce(size: int = CHALLENGE_NONCE_SIZE) -> bytes:
	if not isinstance(size, int):
		raise TypeError("size must be an integer")
	if size < 16:
		raise ValueError("size must be at least 16 bytes")
	return nacl_random(size)


def encrypt_private_key_with_password(
	private_key: bytes,
	password: str,
	argon2_salt: bytes | None = None,
) -> PrivateKeyEnvelope:
	if not isinstance(private_key, (bytes, bytearray)):
		raise TypeError("private_key must be bytes")

	if argon2_salt is None:
		argon2_salt = nacl_random(ARGON2_SALT_SIZE)

	encryption_key, _hmac_key = derive_key_and_hmac(password, argon2_salt)

	box = SecretBox(encryption_key)
	packed_encrypted_private_key = bytes(box.encrypt(bytes(private_key)))

	return PrivateKeyEnvelope(
		encrypted_private_key=packed_encrypted_private_key,
		argon2_salt=bytes(argon2_salt),
	)


def build_registration_crypto_envelope(
	private_key: bytes,
	password: str,
	argon2_salt: bytes | None = None,
) -> RegistrationCryptoEnvelope:
	private_key_envelope = encrypt_private_key_with_password(private_key, password, argon2_salt)
	_, hmac_key = derive_key_and_hmac(password, private_key_envelope.argon2_salt)

	return RegistrationCryptoEnvelope(
		encrypted_private_key=private_key_envelope.encrypted_private_key,
		argon2_salt=private_key_envelope.argon2_salt,
		stored_key=build_stored_key(hmac_key),
	)


def decrypt_private_key_with_password(
	encrypted_private_key: bytes,
	password: str,
	argon2_salt: bytes,
) -> bytes:
	if not isinstance(encrypted_private_key, (bytes, bytearray)):
		raise TypeError("encrypted_private_key must be bytes")

	encryption_key, _hmac_key = derive_key_and_hmac(password, argon2_salt)

	box = SecretBox(encryption_key)
	# box.decrypt() wirft nacl.exceptions.CryptoError, falls das Blob
	# manipuliert wurde oder das Passwort falsch ist (Poly1305-Tag-Check).
	return box.decrypt(bytes(encrypted_private_key))


def sha256_bytes(data: bytes) -> bytes:
	if not isinstance(data, (bytes, bytearray)):
		raise TypeError("data must be bytes")
	return hashlib.sha256(bytes(data)).digest()


def build_client_signature(stored_key: bytes, challenge_nonce: bytes) -> bytes:
	if not isinstance(stored_key, (bytes, bytearray)):
		raise TypeError("stored_key must be bytes")
	if not isinstance(challenge_nonce, (bytes, bytearray)):
		raise TypeError("challenge_nonce must be bytes")

	stored_key = bytes(stored_key)
	if len(stored_key) != HMAC_SIZE:
		raise ValueError(f"stored_key must be {HMAC_SIZE} bytes")

	return hmac.new(stored_key, bytes(challenge_nonce), hashlib.sha256).digest()


def build_client_proof(hmac_key: bytes, challenge_nonce: bytes) -> bytes:
	"""
	Client-seitige Hilfsfunktion:
	client_signature = HMAC(stored_key, challenge_nonce)
	client_proof = hmac_key XOR client_signature
	"""
	if not isinstance(hmac_key, (bytes, bytearray)):
		raise TypeError("hmac_key must be bytes")
	if not isinstance(challenge_nonce, (bytes, bytearray)):
		raise TypeError("challenge_nonce must be bytes")
	hmac_key = bytes(hmac_key)
	if len(hmac_key) != KEY_SIZE:
		raise ValueError(f"hmac_key must be {KEY_SIZE} bytes")

	stored_key = build_stored_key(hmac_key)
	client_signature = build_client_signature(stored_key, bytes(challenge_nonce))
	return bytes(a ^ b for a, b in zip(hmac_key, client_signature))


def verify_client_proof(
	stored_key: bytes,
	challenge_nonce: bytes,
	client_proof: bytes,
) -> ChallengeProofResult:
	"""
	Server-seitige Prüfung:
	client_signature = HMAC(stored_key, challenge_nonce)
	recovered_hmac_key = client_proof XOR client_signature
	True, wenn sha256(recovered_hmac_key) == stored_key

	Wichtig: Vergleich MUSS konstant-zeitig sein (hmac.compare_digest),
	da stored_key und der Vergleich Teil des Login-Sicherheitsbeweises
	sind und client_proof vom Angreifer kontrolliert werden kann. Ein
	naiver '==' Vergleich wäre anfällig für Timing-Angriffe.
	"""
	if not isinstance(stored_key, (bytes, bytearray)):
		raise TypeError("stored_key must be bytes")
	if not isinstance(challenge_nonce, (bytes, bytearray)):
		raise TypeError("challenge_nonce must be bytes")
	if not isinstance(client_proof, (bytes, bytearray)):
		raise TypeError("client_proof must be bytes")

	stored_key = bytes(stored_key)
	challenge_nonce = bytes(challenge_nonce)
	client_proof = bytes(client_proof)
	if len(stored_key) != HMAC_SIZE:
		raise ValueError(f"stored_key must be {HMAC_SIZE} bytes")
	if len(client_proof) != KEY_SIZE:
		raise ValueError(f"client_proof must be {KEY_SIZE} bytes")

	client_signature = build_client_signature(stored_key, challenge_nonce)
	recovered_hmac_key = bytes(a ^ b for a, b in zip(client_proof, client_signature))

	if hmac.compare_digest(sha256_bytes(recovered_hmac_key), stored_key):
		return ChallengeProofResult(valid=True, recovered_hmac_key=recovered_hmac_key)

	return ChallengeProofResult(valid=False, recovered_hmac_key=None)
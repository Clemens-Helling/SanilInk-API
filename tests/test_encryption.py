import hashlib
import hmac
import base64

import pytest

from app.core.crypto import (
	CHALLENGE_NONCE_SIZE,
	ChallengeProofResult,
	RegistrationCryptoEnvelope,
	build_registration_crypto_envelope,
	build_stored_key,
	build_client_proof,
	decrypt_private_key_with_password,
	decrypt_gek_with_private_key,
	decrypt_patient_field,
	encrypt_private_key_with_password,
	encrypt_gek_for_user,
	encrypt_patient_field,
	derive_key_and_hmac,
	generate_challenge_nonce,
	generate_ephemeral_keypair,
	generate_keypair,
	sha256_bytes,
	verify_client_proof,
)


def test_derive_key_and_hmac_returns_two_32_byte_keys():
	encryption_key, hmac_key = derive_key_and_hmac("correct horse battery staple", b"0" * 16)

	assert len(encryption_key) == 32
	assert len(hmac_key) == 32


def test_encrypt_and_decrypt_private_key_roundtrip():
	private_key = b"super-secret-private-key-32-bytes!!"
	password = "correct horse battery staple"
	salt = b"0123456789abcdef"

	envelope = encrypt_private_key_with_password(private_key, password, salt)
	_, hmac_key = derive_key_and_hmac(password, envelope.argon2_salt)

	assert len(envelope.argon2_salt) == 16
	assert len(envelope.hmac_verifier) == 32
	assert len(envelope.encrypted_private_key) > len(private_key)
	assert envelope.hmac_verifier == hmac.new(hmac_key, envelope.encrypted_private_key, hashlib.sha256).digest()

	restored = decrypt_private_key_with_password(
		envelope.encrypted_private_key,
		password,
		envelope.argon2_salt,
		envelope.hmac_verifier,
	)

	assert restored == private_key


def test_build_client_proof_matches_requested_formula():
	hmac_key = b"1234567890abcdef1234567890abcdef"
	challenge_nonce = b"challenge-nonce-32-bytes------"

	client_proof = build_client_proof(hmac_key, challenge_nonce)
	stored_key = build_stored_key(hmac_key)
	client_signature = hmac.new(stored_key, challenge_nonce, hashlib.sha256).digest()
	expected = bytes(a ^ b for a, b in zip(hmac_key, client_signature))

	assert client_proof == expected
	assert len(client_proof) == len(hmac_key)


def test_verify_client_proof_accepts_matching_proof():
	hmac_key = b"1234567890abcdef1234567890abcdef"
	challenge_nonce = b"challenge-nonce-32-bytes------"
	stored_key = build_stored_key(hmac_key)
	client_proof = build_client_proof(hmac_key, challenge_nonce)

	result = verify_client_proof(stored_key, challenge_nonce, client_proof)

	assert isinstance(result, ChallengeProofResult)
	assert result.valid is True
	assert result.recovered_hmac_key == hmac_key


def test_verify_client_proof_rejects_tampering():
	hmac_key = b"1234567890abcdef1234567890abcdef"
	challenge_nonce = b"challenge-nonce-32-bytes------"
	stored_key = build_stored_key(hmac_key)
	client_proof = build_client_proof(hmac_key, challenge_nonce)
	tampered_proof = client_proof[:-1] + bytes([client_proof[-1] ^ 0x01])

	result = verify_client_proof(stored_key, challenge_nonce, tampered_proof)

	assert result.valid is False
	assert result.recovered_hmac_key is None


def test_generate_keypair_and_ephemeral_keypair_return_valid_base64_keys():
	public_key_b64, private_key_b64 = generate_keypair()
	ephemeral_public_key_b64, ephemeral_private_key_b64 = generate_ephemeral_keypair()

	assert len(base64.b64decode(public_key_b64)) == 32
	assert len(base64.b64decode(private_key_b64)) == 32
	assert len(base64.b64decode(ephemeral_public_key_b64)) == 32
	assert len(base64.b64decode(ephemeral_private_key_b64)) == 32


def test_encrypt_and_decrypt_gek_roundtrip_for_user():
	user_public_key_b64, user_private_key_b64 = generate_keypair()
	ephemeral_public_key_b64, ephemeral_private_key_b64 = generate_ephemeral_keypair()
	gek = b"g" * 32

	encrypted_gek_b64 = encrypt_gek_for_user(
	    gek,
	    user_public_key_b64,
	    ephemeral_private_key_b64,
	)
	restored_gek = decrypt_gek_with_private_key(
	    encrypted_gek_b64,
	    ephemeral_public_key_b64,
	    user_private_key_b64,
	)

	assert restored_gek == gek


def test_encrypt_and_decrypt_patient_field_roundtrip():
	gek = b"g" * 32
	plaintext = "Alice Example"

	ciphertext_b64 = encrypt_patient_field(plaintext, gek)
	restored = decrypt_patient_field(ciphertext_b64, gek)

	assert restored == plaintext


def test_build_registration_crypto_envelope_contains_stored_key_and_hmac_verifier():
	private_key = b"super-secret-private-key-32-bytes!!"
	password = "correct horse battery staple"
	salt = b"0123456789abcdef"

	envelope = build_registration_crypto_envelope(private_key, password, salt)
	_, hmac_key = derive_key_and_hmac(password, salt)

	assert isinstance(envelope, RegistrationCryptoEnvelope)
	assert envelope.stored_key == sha256_bytes(hmac_key)
	assert envelope.hmac_verifier == hmac.new(
		hmac_key,
		envelope.encrypted_private_key,
		hashlib.sha256,
	).digest()


def test_generate_challenge_nonce_returns_unique_32_byte_nonce():
	nonce_a = generate_challenge_nonce()
	nonce_b = generate_challenge_nonce()

	assert len(nonce_a) == CHALLENGE_NONCE_SIZE
	assert len(nonce_b) == CHALLENGE_NONCE_SIZE
	assert nonce_a != nonce_b


def test_verify_client_proof_rejects_wrong_nonce():
	hmac_key = b"1234567890abcdef1234567890abcdef"
	challenge_nonce = b"challenge-nonce-32-bytes------"
	wrong_nonce = b"wrong-nonce-for-auth-check-0000"
	stored_key = build_stored_key(hmac_key)
	client_proof = build_client_proof(hmac_key, challenge_nonce)

	result = verify_client_proof(stored_key, wrong_nonce, client_proof)

	assert result.valid is False
	assert result.recovered_hmac_key is None


def test_invalid_types_raise_type_error():
	with pytest.raises(TypeError, match="password must be a string"):
		derive_key_and_hmac(123, b"0" * 16)  # type: ignore[arg-type]

	with pytest.raises(TypeError, match="argon2_salt must be bytes"):
		derive_key_and_hmac("pw", "not-bytes")  # type: ignore[arg-type]

	with pytest.raises(TypeError, match="hmac_key must be bytes"):
		build_client_proof("not-bytes", b"nonce")  # type: ignore[arg-type]

	with pytest.raises(TypeError, match="challenge_nonce must be bytes"):
		build_client_proof(b"key", "not-bytes")  # type: ignore[arg-type]

	with pytest.raises(ValueError, match="hmac_key must be 32 bytes"):
		build_client_proof(b"short", b"nonce")

	with pytest.raises(ValueError, match="stored_key must be 32 bytes"):
		verify_client_proof(b"short", b"nonce", b"0" * 32)

	with pytest.raises(ValueError, match="client_proof must be 32 bytes"):
		verify_client_proof(b"0" * 32, b"nonce", b"short")

	with pytest.raises(TypeError, match="size must be an integer"):
		generate_challenge_nonce("32")  # type: ignore[arg-type]

	with pytest.raises(ValueError, match="size must be at least 16 bytes"):
		generate_challenge_nonce(8)

	with pytest.raises(TypeError, match="encrypted_private_key must be bytes"):
		decrypt_private_key_with_password("not-bytes", "pw", b"0" * 16, b"1" * 32)  # type: ignore[arg-type]

	with pytest.raises(TypeError, match="hmac_verifier must be bytes"):
		decrypt_private_key_with_password(b"cipher", "pw", b"0" * 16, "not-bytes")  # type: ignore[arg-type]

	with pytest.raises(TypeError, match="gek must be bytes"):
		encrypt_gek_for_user("not-bytes", "public", "private")  # type: ignore[arg-type]

	with pytest.raises(ValueError, match="gek must be 32 bytes"):
		encrypt_gek_for_user(b"short", "public", "private")

	with pytest.raises(ValueError, match="Invalid key encoding"):
		encrypt_gek_for_user(b"g" * 32, "invalid", "invalid")

	with pytest.raises(TypeError, match="gek must be bytes"):
		encrypt_patient_field("hello", "not-bytes")  # type: ignore[arg-type]

	with pytest.raises(ValueError, match="gek must be 32 bytes"):
		encrypt_patient_field("hello", b"short")

	with pytest.raises(TypeError, match="gek must be bytes"):
		decrypt_patient_field("cipher", "not-bytes")  # type: ignore[arg-type]

	with pytest.raises(ValueError, match="gek must be 32 bytes"):
		decrypt_patient_field("cipher", b"short")

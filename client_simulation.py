
import base64, json
from app.core.crypto import (
    generate_keypair, generate_ephemeral_keypair,
    derive_key_and_hmac, encrypt_private_key_with_password,
    build_stored_key, encrypt_gek_for_user
)

password = "Test1234!"
customer_number = "TENANT-001"

public_key, private_key = generate_keypair()
epub, epriv = generate_ephemeral_keypair()

key_enc, hmac_key = derive_key_and_hmac(password, b"0123456789abcdef")
private_env = encrypt_private_key_with_password(base64.b64decode(private_key), password, b"0123456789abcdef")
stored_key = build_stored_key(hmac_key)

gek = b"0" * 32
encrypted_gek = encrypt_gek_for_user(gek, public_key, epriv)

payload = {
    "customer_number": customer_number,
    "username": "testuser",
    "email": "test@example.com",
    "public_key": public_key,
    "encrypted_private_key": base64.b64encode(private_env.encrypted_private_key).decode(),
    "argon2_salt_a": base64.b64encode(private_env.argon2_salt).decode(),
    "stored_key": base64.b64encode(stored_key).decode(),
    "argon2_salt_b": base64.b64encode(b"fedcba9876543210").decode(),
    "ephemeral_public_key": epub,
    "encrypted_gek": encrypted_gek
}

print(json.dumps(payload))

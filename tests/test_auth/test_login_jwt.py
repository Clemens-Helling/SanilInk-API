import asyncio
import base64
import os
import sys
from pathlib import Path

from httpx import AsyncClient, ASGITransport

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app
from app.core.crypto import (
    derive_key_and_hmac,
    encrypt_private_key_with_password,
    build_stored_key,
    build_client_proof,
    generate_keypair,
    generate_ephemeral_keypair,
    encrypt_gek_for_user,
)


def test_login_and_get_jwt():
    """
    Test that performs full registration and login flow,
    then extracts and returns the JWT token.
    """
    asyncio.run(_test_login_and_get_jwt())


async def _test_login_and_get_jwt():
    """
    Async helper that performs the login flow and extracts JWT.
    """
    password = "Test1234!"
    customer_number = f"TEST-{os.urandom(3).hex()}"
    email = f"test-{os.urandom(3).hex()}@example.com"

    # Generate cryptographic material
    public_key_b64, private_key_b64 = generate_keypair()
    ephemeral_public_key_b64, ephemeral_private_key_b64 = generate_ephemeral_keypair()

    salt_a = os.urandom(16)
    salt_b = os.urandom(16)

    private_env = encrypt_private_key_with_password(
        base64.b64decode(private_key_b64),
        password,
        salt_a,
    )
    _, hmac_key = derive_key_and_hmac(password, salt_b)
    stored_key = build_stored_key(hmac_key)

    gek = os.urandom(32)
    encrypted_gek = encrypt_gek_for_user(gek, public_key_b64, ephemeral_private_key_b64)

    register_payload = {
        "customer_number": customer_number,
        "username": "test-user",
        "email": email,
        "public_key": public_key_b64,
        "encrypted_private_key": base64.b64encode(private_env.encrypted_private_key).decode("utf-8"),
        "argon2_salt_a": base64.b64encode(private_env.argon2_salt).decode("utf-8"),
        "argon2_time_cost_a": 3,
        "argon2_memory_cost_a": 65536,
        "argon2_parallelism_a": 4,
        "stored_key": base64.b64encode(stored_key).decode("utf-8"),
        "argon2_salt_b": base64.b64encode(salt_b).decode("utf-8"),
        "argon2_time_cost_b": 3,
        "argon2_memory_cost_b": 65536,
        "argon2_parallelism_b": 4,
        "ephemeral_public_key": ephemeral_public_key_b64,
        "encrypted_gek": encrypted_gek,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Register
        register_response = await client.post("/auth/register", json=register_payload)
        if register_response.status_code != 201:
            print(f"Registration error: {register_response.status_code}")
            print(f"Response: {register_response.json()}")
        assert register_response.status_code == 201
        print("✓ Registration successful")

        # Step 2: Login Init
        login_init_response = await client.post(
            "/auth/login/init",
            json={"email": email, "customer_number": customer_number},
        )
        assert login_init_response.status_code == 200
        login_init_data = login_init_response.json()
        print("✓ Login init successful")

        # Step 3: Login Verify
        challenge_nonce = base64.b64decode(login_init_data["challenge_nonce"])
        client_proof = build_client_proof(hmac_key, challenge_nonce)

        login_verify_response = await client.post(
            "/auth/login/verify",
            json={
                "email": email,
                "customer_number": customer_number,
                "challenge_nonce": login_init_data["challenge_nonce"],
                "client_proof": base64.b64encode(client_proof).decode("utf-8"),
            },
        )
        assert login_verify_response.status_code == 200
        login_data = login_verify_response.json()
        
        # Extract JWT token
        jwt_token = login_data["access_token"]
        token_type = login_data["token_type"]
        user_id = login_data["user_id"]
        username = login_data["username"]

        print("\n" + "=" * 60)
        print("✓ LOGIN SUCCESSFUL")
        print("=" * 60)
        print(f"User ID:     {user_id}")
        print(f"Username:    {username}")
        print(f"Token Type:  {token_type}")
        print(f"\nJWT Token:\n{jwt_token}")
        print("=" * 60)

        # Assertions
        assert jwt_token, "JWT token should not be empty"
        assert token_type == "bearer", "Token type should be bearer"
        assert user_id > 0, "User ID should be positive"
        assert username == "test-user", "Username should match"

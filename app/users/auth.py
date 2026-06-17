import uuid

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)

from app.users.manager import SECRET, get_user_manager
from app.users.models import AuthUser

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[AuthUser, uuid.UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)

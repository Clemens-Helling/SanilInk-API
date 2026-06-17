from fastapi import FastAPI
from app.database import engine, Base
from app.users.auth import auth_backend, fastapi_users
from app.users.routes import auth_router, router as users_router
from app.users.schemas import AuthUserRead, AuthUserUpdate
from app.patient.routes import router as patient_router
from app.alerts.routes import router as alerts_router

app = FastAPI(
    title="SaniLink API",
    description="API for SaniLink application",
    version="1.0.0",
)

auth_users_router = fastapi_users.get_users_router(AuthUserRead, AuthUserUpdate)
auth_users_router.routes = [
    route
    for route in auth_users_router.routes
    if not (
        route.name == "users:delete_user"
        or ("DELETE" in route.methods and route.path == "/{id}")
    )
]


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Router registrieren
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    auth_users_router,
    prefix="/auth/users",
    tags=["auth-users"],
)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(
    users_router,
    prefix="/users",
    tags=["users"],
)
app.include_router(patient_router, prefix="/patient", tags=["patient"])
app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])

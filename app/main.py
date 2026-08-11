from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.tenants.router import router as tenants_router
from app.patients.router import router as patients_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(tenants_router, prefix="/tenants", tags=["tenants"])
app.include_router(patients_router, prefix="/patients", tags=["patients"])
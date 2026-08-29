from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.tenants.router import router as tenants_router
from app.patients.router import router as patients_router
from app.intake.router import router as intake_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(tenants_router, prefix="/tenants", tags=["tenants"])
app.include_router(patients_router, prefix="/patients", tags=["patients"])
app.include_router(intake_router, prefix="/intake", tags=["intake"])

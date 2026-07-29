from fastapi import APIRouter

from app.api.auth.router import router as auth_router
from app.api.users.router import router as users_router
from app.api.v1.router import router as v1_router

api_router = APIRouter()
api_router.include_router(v1_router, prefix="/v1", tags=["v1"])
api_router.include_router(auth_router)
api_router.include_router(users_router)

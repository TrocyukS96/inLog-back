from fastapi import APIRouter

from app.api.admin.router import router as admin_router
from app.api.auth.router import router as auth_router
from app.api.notifications.router import router as notifications_router
from app.api.organizations.router import router as organizations_router
from app.api.projects.router import members_router, project_router
from app.api.tasks.router import router as tasks_router
from app.api.users.router import router as users_router
from app.api.v1.router import router as v1_router

api_router = APIRouter()
api_router.include_router(v1_router, prefix="/v1", tags=["v1"])
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(notifications_router)
api_router.include_router(organizations_router)
api_router.include_router(project_router)
api_router.include_router(members_router)
api_router.include_router(tasks_router)

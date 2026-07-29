from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserRead
from app.services.user import serialize_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    return serialize_user(current_user)

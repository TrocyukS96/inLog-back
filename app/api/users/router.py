from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ConfirmEmailChangeRequest, ConfirmEmailChangeResponse
from app.schemas.user import UserRead
from app.services.email_change import confirm_email_change, request_email_change
from app.services.user import serialize_user
from app.services.user_update import UPDATABLE_USER_FIELDS, parse_update_me_payload

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    return serialize_user(current_user)


@router.patch("/me/", response_model=UserRead)
async def update_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead | JSONResponse:
    payload = await parse_update_me_payload(request)

    for field, value in payload.items():
        if field not in UPDATABLE_USER_FIELDS:
            continue

        if field == "email":
            if value.lower() != current_user.email:
                try:
                    await request_email_change(db, current_user, value)
                except ValueError as exc:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"email": [str(exc)]},
                    )
            continue

        setattr(current_user, field, value)

    await db.flush()
    await db.refresh(current_user)
    return serialize_user(current_user)


@router.post("/me/confirm-email-change/", response_model=ConfirmEmailChangeResponse)
async def confirm_email_change_endpoint(
    data: ConfirmEmailChangeRequest,
    db: AsyncSession = Depends(get_db),
) -> ConfirmEmailChangeResponse:
    try:
        await confirm_email_change(
            db,
            email=data.email,
            uid=data.uid,
            token=data.token,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ConfirmEmailChangeResponse(detail="Email changed successfully.")

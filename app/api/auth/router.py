from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, verify_password
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    RegistrationRequest,
    RegistrationResponse,
    ResendEmailRequest,
    ResendEmailResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services.auth import authenticate_user, create_tokens_for_user, get_user_by_email, register_user
from app.services.email_verification import resend_verification_email, send_user_verification_email, verify_user_email
from app.services.password_reset import confirm_password_reset, request_password_reset
from app.services.user import serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registration/", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def registration(
    data: RegistrationRequest,
    db: AsyncSession = Depends(get_db),
) -> RegistrationResponse | JSONResponse:
    if data.password1 != data.password2:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"password2": ["Passwords do not match."]},
        )

    existing_user = await get_user_by_email(db, data.email)
    if existing_user is not None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"email": ["A user with this email already exists."]},
        )

    user = await register_user(db, data)
    await send_user_verification_email(db, user)

    return RegistrationResponse(
        email=data.email,
        password1=data.password1,
        password2=data.password2,
        username=data.username,
        receive_notifications=data.receive_notifications,
        receive_advertisement=data.receive_advertisement,
    )


@router.post("/login/", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    user = await get_user_by_email(db, data.email)
    if user is not None and verify_password(data.password, user.hashed_password):
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before logging in.",
            )

    user = await authenticate_user(db, data)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    access_token, refresh_token = create_tokens_for_user(user)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=serialize_user(user),
    )


@router.post("/logout/", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    return None


@router.post("/token/verify/", response_model=TokenVerifyResponse)
async def verify_token(data: TokenVerifyRequest) -> TokenVerifyResponse:
    try:
        payload = decode_token(data.token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    return TokenVerifyResponse(token=data.token)


@router.post("/registration/verify-email/", response_model=VerifyEmailResponse)
async def verify_email(
    data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> VerifyEmailResponse:
    try:
        await verify_user_email(db, key=data.key, uid=data.uid)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return VerifyEmailResponse(
        key=data.key,
        uid=data.uid,
        detail="Email verified successfully.",
    )


@router.post("/registration/resend-email/", response_model=ResendEmailResponse)
async def resend_email(
    data: ResendEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> ResendEmailResponse:
    detail = await resend_verification_email(db, data.email)
    return ResendEmailResponse(email=data.email, detail=detail)


@router.post("/password/reset/", response_model=PasswordResetResponse)
async def password_reset(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> PasswordResetResponse:
    detail = await request_password_reset(db, data.email)
    return PasswordResetResponse(email=data.email, detail=detail)


@router.post("/password/reset/confirm/", response_model=PasswordResetConfirmResponse)
async def password_reset_confirm(
    data: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> PasswordResetConfirmResponse | JSONResponse:
    if data.new_password1 != data.new_password2:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"new_password2": ["Passwords do not match."]},
        )

    try:
        await confirm_password_reset(
            db,
            uid=data.uid,
            token=data.token,
            new_password1=data.new_password1,
            new_password2=data.new_password2,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PasswordResetConfirmResponse(detail="Password has been reset successfully.")

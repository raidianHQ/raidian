"""HTTP transport layer for account registration/login (Step 22). See
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section
5/7.

Thin routes only -- password hashing/verification and the duplicate-email
check live in app/services/auth_service.py; token issuance lives in
app/core/security.py. No ownership/Reading-authorization logic belongs
here (see app/api/dependencies.py instead).

Deliberately does not include: refresh tokens, password reset, email
verification, roles/admin, OAuth/OIDC/social login, or MFA -- none is
required by any governance document
(Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section 7).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.models.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.schemas.auth import LoginRequest, TokenResponse, UserCreateRequest, UserResponse
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_ALREADY_REGISTERED = "Email is already registered"
_INCORRECT_CREDENTIALS = "Incorrect email or password"


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    responses={409: {"description": _EMAIL_ALREADY_REGISTERED}},
)
def register_route(body: UserCreateRequest, session: Session = Depends(get_db)) -> UserResponse:
    try:
        user = register_user(session, email=body.email, password=body.password)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_ALREADY_REGISTERED) from exc
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for an access token",
    responses={401: {"description": _INCORRECT_CREDENTIALS}},
)
def login_route(body: LoginRequest, session: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = authenticate_user(session, email=body.email, password=body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INCORRECT_CREDENTIALS) from exc
    return TokenResponse(access_token=create_access_token(user.id))

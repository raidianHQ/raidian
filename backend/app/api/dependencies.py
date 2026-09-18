"""Shared FastAPI dependencies for authentication and Reading ownership
(Step 22). See
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section 6.

get_current_user resolves *who* is calling (authentication).
get_owned_reading resolves *which Reading* and verifies the caller owns it
(authorization) -- kept as two separate dependencies deliberately, so a
future route that needs "any authenticated user" with no specific Reading
in scope has somewhere to depend on without dragging in a Reading lookup,
and so this remains the single ownership-enforcement boundary rather than
routes duplicating the check by hand.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.reading import Reading
from app.models.user import User

# auto_error=False: a missing token is handled explicitly below so it
# produces the same generic 401 body as every other authentication
# failure (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
# Section 5.8), rather than FastAPI's own default error shape.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_NOT_AUTHENTICATED = "Not authenticated"
_READING_NOT_FOUND = "Reading not found"


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_db),
) -> User:
    """Authentication only -- no Reading/ownership awareness of any kind.
    Rejects (401, identical message in every case): a missing token, a
    malformed/expired/invalid-signature token, a token whose subject
    resolves to no User, and an inactive User.
    """
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_NOT_AUTHENTICATED)

    try:
        user_id = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_NOT_AUTHENTICATED) from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_NOT_AUTHENTICATED)
    return user


def get_owned_reading(
    reading_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Reading:
    """The single Reading-authorization boundary every route touching a
    Reading must depend on. A nonexistent Reading and a Reading owned by
    someone else return the identical 404 (never 403) -- deliberate,
    resource-enumeration-resistant collapsing, grounded in
    docs/PRINCIPLES.md's "Privacy By Design" (see
    Documentation/AUTHENTICATION_OWNERSHIP_DESIGN.md Section 8.4). Runs
    entirely before any orchestration function is ever invoked, since
    FastAPI resolves dependencies before the route body executes.
    """
    reading = session.get(Reading, reading_id)
    if reading is None or reading.reflection_session.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_READING_NOT_FOUND)
    return reading

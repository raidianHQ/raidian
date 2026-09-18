"""Registration and login business logic (Step 22; database-constraint
backstop for the duplicate-email race added in Step 23).

Thin service functions consumed by app/api/auth.py -- mirrors this
project's existing API/service boundary
(app/services/reading_orchestration.py). Never commits; the caller (the
get_db request boundary, app/db/session.py) controls the transaction,
exactly as every other service in this project already does. The one
exception is the narrow IntegrityError catch in register_user() below,
which re-raises a domain error rather than managing the transaction itself
-- get_db()'s own except-Exception branch still performs the actual
rollback, once that domain error (or the HTTPException app/api/auth.py
converts it to) propagates there, unchanged from every other error path.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.models.user import User


def normalize_email(email: str) -> str:
    """Stripped and lowercased -- the whole of this project's identity
    normalization (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 5.3), applied identically at registration and login so the two
    can never disagree about whether an email matches.
    """
    return email.strip().lower()


def _find_existing_user_by_email(session: Session, normalized_email: str) -> User | None:
    """The pre-check -- a fast-path convenience that avoids a doomed insert
    in the common, non-racing case. Extracted into its own function so a
    test can force the race window open (Step 23) by making this
    deliberately blind to an already-committed row, proving
    register_user()'s *real* backstop is the database constraint caught
    below, not merely this query.
    """
    return session.scalars(select(User).where(User.email == normalized_email)).first()


def _is_duplicate_email_violation(exc: IntegrityError) -> bool:
    """Distinguishes the users.email unique-constraint violation from any
    other IntegrityError, so an unrelated constraint failure is never
    silently reinterpreted as "email already registered" (register_user()
    re-raises anything that doesn't match, unchanged). Matches both
    SQLite's message ("UNIQUE constraint failed: users.email") and
    PostgreSQL's ("duplicate key value violates unique constraint
    "ix_users_email""./"Key (email)=...") -- the only two dialects this
    project's stack (ADR-0004) ever runs against.
    """
    message = str(exc.orig if exc.orig is not None else exc).lower()
    return "email" in message and ("unique" in message or "duplicate" in message)


def register_user(session: Session, *, email: str, password: str) -> User:
    """Raises EmailAlreadyRegisteredError if the normalized email is
    already taken -- detected first by a pre-check (the common case, no
    doomed insert attempted), and, as the authoritative backstop for a
    genuine concurrent-registration race the pre-check cannot see
    (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 10.1), by catching the database's own unique-constraint
    violation on the insert itself. Hashes the password before it ever
    touches the User row -- the plaintext argument is never stored or
    returned.
    """
    normalized = normalize_email(email)
    if _find_existing_user_by_email(session, normalized) is not None:
        raise EmailAlreadyRegisteredError(f"email {normalized!r} is already registered")

    user = User(email=normalized, hashed_password=hash_password(password))
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        if not _is_duplicate_email_violation(exc):
            raise
        raise EmailAlreadyRegisteredError(f"email {normalized!r} is already registered") from exc
    return user


def authenticate_user(session: Session, *, email: str, password: str) -> User:
    """Raises InvalidCredentialsError for a nonexistent email, a wrong
    password, or an inactive account -- deliberately the same error for
    all three (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 5.2), so the API layer can return one identical 401 without
    leaking which condition was true.
    """
    normalized = normalize_email(email)
    user = session.scalars(select(User).where(User.email == normalized)).first()
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("incorrect email or password")
    return user

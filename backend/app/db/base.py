import enum
import uuid
from datetime import datetime
from typing import TypeVar

from sqlalchemy import DateTime, Enum, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all Raidian Wise ORM models."""


_E = TypeVar("_E", bound=enum.Enum)


def str_enum_type(enum_cls: type[_E], *, name: str, length: int) -> Enum:
    """A portable (SQLite CHECK-constraint-backed, Postgres-native-enum-free)
    column type for our str-valued enums.

    SQLAlchemy's Enum type stores a Python enum member's *name* (e.g.
    "MAJOR") by default, not its .value (e.g. "major"). Our enums are
    intentionally lowercase snake_case for readability in the database and
    in raw SQL (see docs/NAMING_CONVENTIONS.md), so values_callable is
    required to make the stored representation match .value instead.
    native_enum=False keeps `ALTER ... ADD VALUE` migrations simple later
    (a plain VARCHAR + CHECK constraint) rather than dealing with
    PostgreSQL's native enum type alteration rules.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        length=length,
        values_callable=lambda obj: [member.value for member in obj],
    )


class UUIDPrimaryKeyMixin:
    """Gives a model a UUID primary key, portable across SQLite (dev) and PostgreSQL (prod)."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Adds created_at / updated_at audit timestamps, maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

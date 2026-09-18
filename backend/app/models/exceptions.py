class DuplicateCardError(ValueError):
    """Raised when a card would be drawn twice in a Reading whose Spread
    does not allow duplicate cards (the default -- see Spread.allow_duplicate_cards).
    """


class ReadingNotDraftingError(ValueError):
    """Raised when a CardDraw is added to a Reading whose status is no
    longer DRAFTING (i.e. SPREAD_COMPLETE, INTERPRETED, or SAVED).

    Once a Reading has left DRAFTING, its evidence is immutable
    (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 17 -- "immutable once the
    spread is complete"; see
    Documentation/READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md Section
    5/7). This is checked before any other CardDraw validation.
    """


class ReadingNotSaveableError(ValueError):
    """Raised when Reading.mark_saved() is called against a Reading whose
    status is DRAFTING -- an incomplete spread is not the "completed
    record" Reading History exists to list
    (Documentation/SAVE_READING_DESIGN.md Section 5/6). Not raised for
    SPREAD_COMPLETE or INTERPRETED (both transition to SAVED) or for an
    already-SAVED Reading (mark_saved() is idempotent, not an error).
    """


class EmailAlreadyRegisteredError(ValueError):
    """Raised by app/services/auth_service.py::register_user() when the
    normalized email already belongs to an existing User -- mapped to 409
    at the API layer (app/api/auth.py).
    """


class InvalidCredentialsError(ValueError):
    """Raised by app/services/auth_service.py::authenticate_user() for a
    nonexistent email, a wrong password, or an inactive account -- all
    three collapse into this single error deliberately, so login can
    return one identical 401 response regardless of which is true (no
    account-existence signal leaked; see
    Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
    Section 5.2).
    """


class SpreadNotFoundError(ValueError):
    """Raised by app/services/reading_service.py::create_reading() when
    the client-supplied spread_id does not reference an existing Spread --
    mapped to 404 at the API layer (app/api/reading.py). Spreads are
    pre-seeded reference data (app/seed/seed.py); this route never creates
    one (Documentation/READING_CREATION_API_DESIGN.md Section 10).
    """


class DeckNotFoundError(ValueError):
    """Raised by app/services/reading_service.py::create_reading() when a
    client-supplied deck_id does not reference an existing Deck -- mapped
    to 404 at the API layer. Not raised when deck_id is omitted (that case
    resolves to the seeded default Deck instead -- see
    Documentation/READING_CREATION_API_DESIGN.md Section 5/9).
    """

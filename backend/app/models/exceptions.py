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


class SpreadPositionNotFoundError(ValueError):
    """Raised by app/services/reading_service.py::record_card_draw() when
    a client-supplied position_id does not reference an existing
    SpreadPosition, or references one that exists but does not belong to
    the Reading's own Spread -- both cases collapse into this single
    error, mapped to 404 at the API layer, mirroring the same
    enumeration-resistant collapsing already used for Reading ownership
    (app/api/dependencies.py::get_owned_reading) and for
    SpreadNotFoundError/DeckNotFoundError above (see
    Documentation/CARDDRAW_API_DESIGN.md Section 6).
    """


class CardNotFoundError(ValueError):
    """Raised by app/services/reading_service.py::record_card_draw() when
    a client-supplied card_id does not reference an existing Card, or
    references one that exists but does not belong to the Reading's own
    Deck -- both cases collapse into this single error, mapped to 404 at
    the API layer, for the same reason as SpreadPositionNotFoundError
    above.
    """


class ReadingNotDigitalError(ValueError):
    """Raised by app/services/reading_service.py::record_digital_draw()
    when the target Reading's draw_method is not DIGITAL -- Digital Draw
    is only ever valid against a Reading explicitly configured for it at
    creation time (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section
    8.2/8.4: "Draw method is recorded on the Reading ... and is immutable
    once the spread is complete"). Mapped to 409 at the API layer.
    """


class ReadingAlreadyDrawnError(ValueError):
    """Raised by app/services/reading_service.py::record_digital_draw()
    when the target Reading already has one or more CardDraw rows
    recorded (from a prior digital draw, or from manual entry against a
    Reading whose draw_method happens to be DIGITAL). Digital Draw fills
    every position of the Reading's Spread in a single atomic operation --
    it is not designed to top up a partially-filled Reading, and running
    it against one would otherwise surface as a raw, unhandled
    IntegrityError once it reached an already-occupied position. Mapped
    to 409 at the API layer.
    """


class InsufficientCardsForDigitalDrawError(ValueError):
    """Raised by app/services/reading_service.py::select_digital_cards()
    when the Reading's Deck does not contain enough distinct Cards to
    fill every Spread Position without repeating one, and the Spread does
    not set allow_duplicate_cards
    (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 8.2). Not
    reachable against any MVP-seeded Deck/Spread combination (78 Cards,
    at most 10 Positions) -- a defense-in-depth guard for future,
    smaller custom decks. Mapped to 409 at the API layer.
    """


class PositionAlreadyDrawnError(ValueError):
    """Raised by app/services/reading_service.py::record_card_draw() when
    the requested SpreadPosition already has a CardDraw recorded against
    it in this Reading -- mapped to 409 at the API layer. Detected by an
    in-memory pre-check against the Reading's already-loaded card_draws,
    which reliably catches the ordinary, sequential case (the same
    pre-check technique already proven by
    app/services/auth_service.py::register_user() for the duplicate-email
    race, Step 23). The database's own
    uq_card_draws_reading_id_position_id constraint remains the
    authoritative data-integrity invariant -- no duplicate row for a
    position can ever actually persist -- but this exception is not
    guaranteed to be the externally observed result of a genuine
    concurrent same-position race; see
    _is_position_already_drawn_violation()'s own docstring and
    Documentation/CARDDRAW_CONCURRENCY_RECONCILIATION.md. Distinct from
    DuplicateCardError above: this is about the *position* already being
    filled (by any card), not about the same *card* being drawn twice.
    """

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

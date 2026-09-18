class DuplicateCardError(ValueError):
    """Raised when a card would be drawn twice in a Reading whose Spread
    does not allow duplicate cards (the default -- see Spread.allow_duplicate_cards).
    """

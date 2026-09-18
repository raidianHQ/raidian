import enum


class Arcana(str, enum.Enum):
    """Whether a Card belongs to the Major or Minor Arcana."""

    MAJOR = "major"
    MINOR = "minor"


class Suit(str, enum.Enum):
    """Minor Arcana suit. Null for Major Arcana cards."""

    WANDS = "wands"
    CUPS = "cups"
    SWORDS = "swords"
    PENTACLES = "pentacles"


class Orientation(str, enum.Enum):
    """How a drawn card was oriented."""

    UPRIGHT = "upright"
    REVERSED = "reversed"


class DrawMethod(str, enum.Enum):
    """How the cards in a Reading were drawn.

    Physical is the default and only implemented path. Digital is reserved
    for future functionality (see RAIDIAN_WISE_PRODUCT_SPEC_V1.md, Section 8)
    and must remain represented here so the data model does not need to
    change shape when Digital Draw is implemented.
    """

    PHYSICAL = "physical"
    DIGITAL = "digital"


class ReadingStatus(str, enum.Enum):
    """Lifecycle of a Reading's data entry, independent of interpretation.

    Interpretation-related statuses (e.g. "interpreted") are intentionally
    not included yet -- the Interpretation Engine is a later phase. New
    values can be appended in a future migration without reshaping this table.
    """

    DRAFTING = "drafting"
    SPREAD_COMPLETE = "spread_complete"
    SAVED = "saved"


class SemanticRole(str, enum.Enum):
    """The structural role a Spread Position plays within its Spread.

    This is reference data for a future Interpretation Engine (trajectory,
    blocker detection, advice/clarifier pairing) -- Phase 1 only stores it.
    """

    SIGNIFICATOR = "significator"
    SITUATION = "situation"
    RECENT_PAST = "recent_past"
    INFLUENCE_BLOCKER = "influence_blocker"
    NEAR_FUTURE = "near_future"
    ADVICE = "advice"
    ADVICE_CLARIFIER = "advice_clarifier"
    GENERAL = "general"

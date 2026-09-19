"""API tests for the reference-data resource: Spreads, Cards, Decks
(Step 41, Documentation/REFERENCE_DATA_CORS_DESIGN.md).

Self-contained fixtures, mirroring tests/test_api_reading.py's own
established pattern. Unlike that file, `client` here needs no auth
handling by default -- every route in this module is public -- except
for the dedicated integration tests at the bottom, which authenticate
explicitly to prove a returned reference-data ID is actually usable
against the existing, ownership-gated Reading/CardDraw creation APIs.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Base, Card, Deck, Spread, User
from app.seed.seed import seed_reference_data
from tests.factories import make_user

# --- Fixtures ------------------------------------------------------------------


@pytest.fixture()
def api_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def api_session_factory(api_engine):
    return sessionmaker(bind=api_engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def api_seeded_session(api_session_factory):
    session = api_session_factory()
    seed_reference_data(session)
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def client(api_session_factory):
    def _override_get_db():
        db = api_session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


# =====================================================================================
# GET /spreads
# =====================================================================================


def test_list_spreads_returns_200_with_all_seeded_spreads(api_seeded_session, client):
    response = client.get("/spreads")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert {spread["name"] for spread in body} == {"Celtic Cross", "Single Card", "Three Card"}


def test_spreads_are_ordered_by_name(api_seeded_session, client):
    response = client.get("/spreads")

    names = [spread["name"] for spread in response.json()]
    assert names == sorted(names)


def test_spread_fields_match_the_model(api_seeded_session, client):
    expected = api_seeded_session.scalars(select(Spread).where(Spread.name == "Three Card")).one()

    response = client.get("/spreads")
    three_card = next(s for s in response.json() if s["name"] == "Three Card")

    assert three_card["id"] == str(expected.id)
    assert three_card["description"] == expected.description
    assert three_card["allow_duplicate_cards"] == expected.allow_duplicate_cards
    assert three_card["position_count"] == 3


def test_spread_positions_are_embedded_with_correct_count_and_order(api_seeded_session, client):
    response = client.get("/spreads")
    celtic_cross = next(s for s in response.json() if s["name"] == "Celtic Cross")

    assert len(celtic_cross["positions"]) == 10
    assert celtic_cross["position_count"] == 10
    orders = [p["position_order"] for p in celtic_cross["positions"]]
    assert orders == sorted(orders)


def test_spread_position_fields_match_the_model(api_seeded_session, client):
    expected_spread = api_seeded_session.scalars(select(Spread).where(Spread.name == "Single Card")).one()
    expected_position = expected_spread.positions[0]

    response = client.get("/spreads")
    single_card = next(s for s in response.json() if s["name"] == "Single Card")
    position = single_card["positions"][0]

    assert position["id"] == str(expected_position.id)
    assert position["name"] == expected_position.name
    assert position["semantic_role"] == expected_position.semantic_role.value
    assert position["required"] == expected_position.required
    assert "spread_id" not in position


def test_spreads_response_exposes_no_unexpected_fields(api_seeded_session, client):
    response = client.get("/spreads")
    spread = response.json()[0]

    assert set(spread.keys()) == {
        "id",
        "name",
        "description",
        "position_count",
        "allow_duplicate_cards",
        "positions",
    }
    position = spread["positions"][0]
    assert set(position.keys()) == {
        "id",
        "name",
        "description",
        "position_order",
        "semantic_role",
        "required",
    }


def test_spreads_does_not_require_authentication(api_seeded_session, client):
    response = client.get("/spreads")
    assert response.status_code == 200


# =====================================================================================
# GET /cards
# =====================================================================================


def test_list_cards_returns_200_with_all_78_cards(api_seeded_session, client):
    response = client.get("/cards")

    assert response.status_code == 200
    assert len(response.json()) == 78


def test_card_fields_match_the_model(api_seeded_session, client):
    expected = api_seeded_session.scalars(select(Card).where(Card.name == "The Fool")).one()

    response = client.get("/cards")
    fool = next(c for c in response.json() if c["name"] == "The Fool")

    assert fool["id"] == str(expected.id)
    assert fool["arcana"] == expected.arcana.value
    assert fool["suit"] is None
    assert fool["rank"] == expected.rank
    assert fool["image_ref"] == expected.image_ref
    assert fool["keywords"] == expected.keywords


def test_cards_are_ordered_major_arcana_first_in_rank_order(api_seeded_session, client):
    response = client.get("/cards")
    major = [c for c in response.json() if c["arcana"] == "major"]

    assert [c["rank"] for c in major] == [str(n) for n in range(22)]
    assert major[0]["name"] == "The Fool"
    assert major[-1]["name"] == "The World"


def test_minor_arcana_cards_are_ordered_ace_through_king_within_each_suit(api_seeded_session, client):
    response = client.get("/cards")
    pentacles = [c for c in response.json() if c["suit"] == "pentacles"]

    assert [c["rank"] for c in pentacles] == [
        "ace", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "page", "knight", "queen", "king",
    ]


def test_cards_filtered_by_deck_id_returns_only_that_decks_cards(api_seeded_session, client):
    deck = api_seeded_session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()

    response = client.get("/cards", params={"deck_id": str(deck.id)})

    assert response.status_code == 200
    assert len(response.json()) == 78


def test_cards_with_nonexistent_deck_id_returns_404(api_seeded_session, client):
    response = client.get("/cards", params={"deck_id": str(uuid.uuid4())})

    assert response.status_code == 404


def test_cards_with_malformed_deck_id_returns_422(api_seeded_session, client):
    response = client.get("/cards", params={"deck_id": "not-a-uuid"})

    assert response.status_code == 422


def test_cards_response_exposes_no_unexpected_or_interpretive_fields(api_seeded_session, client):
    response = client.get("/cards")
    card = response.json()[0]

    assert set(card.keys()) == {"id", "name", "arcana", "suit", "rank", "image_ref", "keywords"}
    assert "base_meaning_upright" not in card
    assert "base_meaning_reversed" not in card
    assert "primary_themes" not in card
    assert "secondary_themes" not in card
    assert "deck_id" not in card


def test_cards_does_not_require_authentication(api_seeded_session, client):
    response = client.get("/cards")
    assert response.status_code == 200


# =====================================================================================
# GET /decks
# =====================================================================================


def test_list_decks_returns_200_with_the_seeded_deck(api_seeded_session, client):
    response = client.get("/decks")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Rider-Waite-Smith"


def test_default_deck_is_flagged_correctly(api_seeded_session, client):
    expected = api_seeded_session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()

    response = client.get("/decks")
    deck = response.json()[0]

    assert deck["id"] == str(expected.id)
    assert deck["is_default"] is True


def test_decks_response_exposes_no_unexpected_fields(api_seeded_session, client):
    response = client.get("/decks")
    deck = response.json()[0]

    assert set(deck.keys()) == {"id", "name", "description", "is_default"}


def test_decks_does_not_require_authentication(api_seeded_session, client):
    response = client.get("/decks")
    assert response.status_code == 200


# =====================================================================================
# Integration: reference-data IDs are actually usable against the existing,
# ownership-gated Reading/CardDraw creation APIs
# =====================================================================================


def test_returned_spread_id_can_be_used_to_create_a_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="refdata1@example.com")
    api_seeded_session.commit()
    spread_id = next(s for s in client.get("/spreads").json() if s["name"] == "Three Card")["id"]

    response = client.post(
        "/readings",
        json={"spread_id": spread_id, "question": "What should I focus on?"},
        headers=_auth_header(owner),
    )

    assert response.status_code == 201


def test_returned_deck_id_can_be_used_to_create_a_reading(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="refdata2@example.com")
    api_seeded_session.commit()
    spread_id = next(s for s in client.get("/spreads").json() if s["name"] == "Three Card")["id"]
    deck_id = client.get("/decks").json()[0]["id"]

    response = client.post(
        "/readings",
        json={"spread_id": spread_id, "deck_id": deck_id, "question": "What should I focus on?"},
        headers=_auth_header(owner),
    )

    assert response.status_code == 201


def test_returned_position_id_and_card_id_can_be_used_to_record_a_draw(api_seeded_session, client):
    owner = make_user(api_seeded_session, email="refdata3@example.com")
    api_seeded_session.commit()
    three_card = next(s for s in client.get("/spreads").json() if s["name"] == "Three Card")
    spread_id = three_card["id"]
    position_id = three_card["positions"][0]["id"]
    card_id = client.get("/cards").json()[0]["id"]

    created = client.post(
        "/readings",
        json={"spread_id": spread_id, "question": "What should I focus on?"},
        headers=_auth_header(owner),
    ).json()

    response = client.post(
        f"/readings/{created['id']}/draws",
        json={"position_id": position_id, "card_id": card_id, "orientation": "upright"},
        headers=_auth_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["position_id"] == position_id
    assert response.json()["card_id"] == card_id

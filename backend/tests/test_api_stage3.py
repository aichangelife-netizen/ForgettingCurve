import re

import sqlalchemy as sa

from app.db.database import utc_now
from app.db.enums import TestDesignStatus as DesignStatus
from app.db.models import Participant, TestDesign as Design, VocabularyItem


def seed_vocabulary(db_session, count: int, *, active: bool = True, start: int = 1) -> None:
    for index in range(start, start + count):
        db_session.add(
            VocabularyItem(
                korean=f"단어{index}",
                english_answer=f"word{index}",
                is_active=active,
                created_at=utc_now(),
            )
        )
    db_session.commit()


def create_participant_row(db_session, code: str = "P-EXIST001") -> Participant:
    participant = Participant(participant_code=code, created_at=utc_now())
    db_session.add(participant)
    db_session.commit()
    db_session.refresh(participant)
    return participant


def test_participant_creation_succeeds(api_client) -> None:
    response = api_client.post("/api/participants")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert re.fullmatch(r"P-[A-Z0-9]{8}", body["participant_code"])
    assert body["created_at"]


def test_participant_creation_rejects_identifying_fields(api_client) -> None:
    response = api_client.post("/api/participants", json={"email": "person@example.com"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "participant_request_body_not_allowed"


def test_participant_codes_are_unique(api_client) -> None:
    codes = {api_client.post("/api/participants").json()["participant_code"] for _ in range(20)}

    assert len(codes) == 20


def test_participant_retrieval(api_client) -> None:
    created = api_client.post("/api/participants").json()

    response = api_client.get(f"/api/participants/{created['id']}")

    assert response.status_code == 200
    assert response.json()["participant_code"] == created["participant_code"]


def test_missing_participant_returns_404(api_client) -> None:
    response = api_client.get("/api/participants/999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "participant_not_found"


def test_test_design_creation_succeeds(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 6)

    response = api_client.post(
        "/api/test-designs",
        json={
            "participant_id": participant.id,
            "items_per_group": 2,
            "intervals_seconds": [60, 120, 180],
            "random_seed": 12345,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["participant_id"] == participant.id
    assert body["status"] == "draft"
    assert body["groups"] == [
        {"id": body["groups"][0]["id"], "group_index": 1, "interval_seconds": 60, "status": "pending", "completed_at": None},
        {"id": body["groups"][1]["id"], "group_index": 2, "interval_seconds": 120, "status": "pending", "completed_at": None},
        {"id": body["groups"][2]["id"], "group_index": 3, "interval_seconds": 180, "status": "pending", "completed_at": None},
    ]


def test_group_count_is_derived_from_interval_list(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 3)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10, 20, 30]},
    )

    assert response.status_code == 201
    assert response.json()["group_count"] == 3


def test_required_item_count_is_calculated_correctly(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 12)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 4, "intervals_seconds": [10, 20, 30]},
    )

    assert response.status_code == 201
    assert response.json()["required_item_count"] == 12


def test_groups_are_created_in_same_transaction(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 2)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10, 20]},
    )

    assert response.status_code == 201
    design_count = db_session.scalar(sa.select(sa.func.count()).select_from(Design))
    group_count = db_session.execute(sa.text("SELECT count(*) FROM test_design_groups")).scalar_one()
    assert design_count == 1
    assert group_count == 2


def test_duplicate_intervals_are_rejected(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 2)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10, 10]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "duplicate_intervals"


def test_zero_or_negative_interval_is_rejected(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 2)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10, 0]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_interval"


def test_empty_interval_list_is_rejected(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": []},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "empty_intervals"


def test_zero_or_negative_items_per_group_is_rejected(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 0, "intervals_seconds": [10]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_items_per_group"


def test_missing_participant_is_rejected_for_design_creation(api_client, db_session) -> None:
    seed_vocabulary(db_session, 1)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": 999, "items_per_group": 1, "intervals_seconds": [10]},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "participant_not_found"


def test_insufficient_active_vocabulary_is_rejected(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 2, "intervals_seconds": [10]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "insufficient_active_vocabulary"


def test_second_unfinished_design_is_rejected(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 4)
    request_body = {"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]}

    first_response = api_client.post("/api/test-designs", json=request_body)
    second_response = api_client.post("/api/test-designs", json=request_body)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"]["code"] == "unfinished_design_exists"


def test_random_seed_is_stored(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10], "random_seed": 77},
    )

    assert response.status_code == 201
    assert response.json()["random_seed"] == 77


def test_random_seed_is_generated_when_omitted(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]},
    )

    assert response.status_code == 201
    assert isinstance(response.json()["random_seed"], int)


def test_get_test_design_returns_design(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)
    created = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]},
    ).json()

    response = api_client.get(f"/api/test-designs/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_draft_to_learning_succeeds(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)
    created = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]},
    ).json()

    response = api_client.post(f"/api/test-designs/{created['id']}/start-learning")

    assert response.status_code == 200
    assert response.json()["status"] == "learning"


def test_repeated_start_learning_is_rejected(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)
    created = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]},
    ).json()
    first_response = api_client.post(f"/api/test-designs/{created['id']}/start-learning")
    second_response = api_client.post(f"/api/test-designs/{created['id']}/start-learning")

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"]["code"] == "invalid_design_status_transition"


def test_learning_started_at_is_stored(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)
    created = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]},
    ).json()

    response = api_client.post(f"/api/test-designs/{created['id']}/start-learning")

    assert response.status_code == 200
    assert response.json()["learning_started_at"] is not None


def test_current_design_endpoint_works(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 1)
    created = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]},
    ).json()

    response = api_client.get(f"/api/participants/{participant.id}/test-designs/current")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_current_design_endpoint_returns_404_when_none_exists(api_client, db_session) -> None:
    participant = create_participant_row(db_session)

    response = api_client.get(f"/api/participants/{participant.id}/test-designs/current")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "current_test_design_not_found"


def test_active_only_vocabulary_listing(api_client, db_session) -> None:
    seed_vocabulary(db_session, 2, active=True)
    seed_vocabulary(db_session, 1, active=False, start=3)

    response = api_client.get("/api/vocabulary-items")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["is_active"] for item in body["items"])


def test_optional_inactive_vocabulary_listing(api_client, db_session) -> None:
    seed_vocabulary(db_session, 2, active=True)
    seed_vocabulary(db_session, 1, active=False, start=3)

    response = api_client.get("/api/vocabulary-items?include_inactive=true")

    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_vocabulary_pagination(api_client, db_session) -> None:
    seed_vocabulary(db_session, 5)

    response = api_client.get("/api/vocabulary-items?limit=2&offset=2")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["offset"] == 2
    assert len(body["items"]) == 2
    assert body["total"] == 5


def test_completed_design_does_not_block_new_design(api_client, db_session) -> None:
    participant = create_participant_row(db_session)
    seed_vocabulary(db_session, 2)
    db_session.add(
        Design(
            participant_id=participant.id,
            items_per_group=1,
            group_count=1,
            random_seed=1,
            status=DesignStatus.COMPLETED,
            created_at=utc_now(),
        )
    )
    db_session.commit()

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]},
    )

    assert response.status_code == 201

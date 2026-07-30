import sqlalchemy as sa

from app.db.database import utc_now
from app.db.enums import TestDesignStatus as DesignStatus, VocabularyAttemptType
from app.db.models import (
    Participant,
    TestAssignment as Assignment,
    TestDesign as Design,
    TestDesignItem as DesignItem,
    VocabularyAttempt,
    VocabularyItem,
)
from app.services.learning import select_learning_pool_vocabulary_ids


def seed_vocabulary(db_session, count: int, *, active: bool = True, start: int = 1) -> list[int]:
    items = []
    for index in range(start, start + count):
        item = VocabularyItem(
            korean=f"학습{index}",
            english_answer=f"word{index}",
            is_active=active,
            created_at=utc_now(),
        )
        db_session.add(item)
        items.append(item)
    db_session.commit()
    return [item.id for item in items]


def create_participant(db_session, code: str = "P-STAGE400") -> Participant:
    participant = Participant(participant_code=code, created_at=utc_now())
    db_session.add(participant)
    db_session.commit()
    db_session.refresh(participant)
    return participant


def create_design(api_client, participant_id: int, *, items_per_group: int = 2, intervals=None, random_seed: int = 99) -> dict:
    intervals = intervals or [10, 20]
    response = api_client.post(
        "/api/test-designs",
        json={
            "participant_id": participant_id,
            "items_per_group": items_per_group,
            "intervals_seconds": intervals,
            "random_seed": random_seed,
        },
    )
    assert response.status_code == 201
    return response.json()


def start_learning(api_client, design_id: int) -> dict:
    response = api_client.post(f"/api/test-designs/{design_id}/start-learning")
    assert response.status_code == 200
    return response.json()


def learning_items(db_session, design_id: int) -> list[DesignItem]:
    return list(
        db_session.scalars(
            sa.select(DesignItem).where(DesignItem.test_design_id == design_id).order_by(DesignItem.id)
        )
    )


def answer_for_item(db_session, item: DesignItem) -> str:
    return db_session.get(VocabularyItem, item.vocabulary_item_id).english_answer


def create_started_design(api_client, db_session, *, required_count: int = 4, random_seed: int = 99):
    participant = create_participant(db_session)
    seed_vocabulary(db_session, required_count)
    design = create_design(api_client, participant.id, items_per_group=required_count, intervals=[10], random_seed=random_seed)
    start_learning(api_client, design["id"])
    return participant, design


def submit_attempt(api_client, design_id: int, item_id: int, answer: str, response_time_ms=None):
    return api_client.post(
        f"/api/test-designs/{design_id}/learning-attempts",
        json={
            "test_design_item_id": item_id,
            "user_answer": answer,
            "response_time_ms": response_time_ms,
        },
    )


def test_start_learning_creates_exactly_required_item_count_design_items(api_client, db_session) -> None:
    participant = create_participant(db_session)
    seed_vocabulary(db_session, 6)
    design = create_design(api_client, participant.id, items_per_group=2, intervals=[10, 20, 30])

    response = api_client.post(f"/api/test-designs/{design['id']}/start-learning")

    assert response.status_code == 200
    assert response.json()["status"] == "learning"
    assert len(learning_items(db_session, design["id"])) == 6


def test_start_learning_selects_only_active_vocabulary(api_client, db_session) -> None:
    participant = create_participant(db_session)
    active_ids = seed_vocabulary(db_session, 3, active=True)
    inactive_ids = seed_vocabulary(db_session, 3, active=False, start=10)
    design = create_design(api_client, participant.id, items_per_group=3, intervals=[10])

    start_learning(api_client, design["id"])

    selected_ids = {item.vocabulary_item_id for item in learning_items(db_session, design["id"])}
    assert selected_ids == set(active_ids)
    assert selected_ids.isdisjoint(inactive_ids)


def test_start_learning_selects_no_duplicate_vocabulary_items(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=4)

    selected_ids = [item.vocabulary_item_id for item in learning_items(db_session, design["id"])]

    assert len(selected_ids) == len(set(selected_ids))


def test_same_seed_produces_same_selected_order(db_session) -> None:
    vocabulary_ids = [5, 1, 4, 2, 3]

    first_order = select_learning_pool_vocabulary_ids(vocabulary_ids, random_seed=123, required_count=4)
    second_order = select_learning_pool_vocabulary_ids(list(reversed(vocabulary_ids)), random_seed=123, required_count=4)

    assert first_order == second_order


def test_different_seed_normally_produces_different_selected_order(db_session) -> None:
    vocabulary_ids = list(range(1, 21))

    first_order = select_learning_pool_vocabulary_ids(vocabulary_ids, random_seed=123, required_count=10)
    second_order = select_learning_pool_vocabulary_ids(vocabulary_ids, random_seed=456, required_count=10)

    assert first_order != second_order


def test_insufficient_active_vocabulary_rolls_back_fully(api_client, db_session) -> None:
    participant = create_participant(db_session)
    active_ids = seed_vocabulary(db_session, 2)
    design = create_design(api_client, participant.id, items_per_group=2, intervals=[10])
    db_session.execute(sa.update(VocabularyItem).where(VocabularyItem.id == active_ids[1]).values(is_active=False))
    db_session.commit()

    response = api_client.post(f"/api/test-designs/{design['id']}/start-learning")

    db_session.expire_all()
    stored_design = db_session.get(Design, design["id"])
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "insufficient_active_vocabulary"
    assert stored_design.status == DesignStatus.DRAFT
    assert learning_items(db_session, design["id"]) == []


def test_repeated_start_learning_is_rejected(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)

    response = api_client.post(f"/api/test-designs/{design['id']}/start-learning")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_design_status_transition"
    assert len(learning_items(db_session, design["id"])) == 2


def test_start_learning_creates_no_test_assignments(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)

    assignment_count = db_session.scalar(sa.select(sa.func.count()).select_from(Assignment))

    assert assignment_count == 0


def test_learning_materials_returns_all_fixed_pool_items_and_answers(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=3)

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-materials")

    assert response.status_code == 200
    body = response.json()
    assert body["required_item_count"] == 3
    assert body["mastered_item_count"] == 0
    assert body["remaining_item_count"] == 3
    assert len(body["items"]) == 3
    assert all("english_answer" in item for item in body["items"])


def test_learning_materials_are_ordered_by_design_item_id(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=4)

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-materials")

    ids = [item["test_design_item_id"] for item in response.json()["items"]]
    assert ids == sorted(ids)


def test_learning_materials_rejects_invalid_design_status(api_client, db_session) -> None:
    participant = create_participant(db_session)
    seed_vocabulary(db_session, 1)
    design = create_design(api_client, participant.id, items_per_group=1, intervals=[10])

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-materials")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_not_learning_for_materials"


def test_next_learning_check_returns_unmastered_item_without_answer(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-checks/next")

    assert response.status_code == 200
    body = response.json()
    assert body["test_design_item_id"] in [item.id for item in learning_items(db_session, design["id"])]
    assert "english_answer" not in body


def test_next_learning_check_items_with_no_attempts_come_first(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)
    first_item, second_item = learning_items(db_session, design["id"])
    submit_attempt(api_client, design["id"], first_item.id, "wrong")

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-checks/next")

    assert response.json()["test_design_item_id"] == second_item.id


def test_next_learning_check_least_recently_attempted_ordering_works(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)
    first_item, second_item = learning_items(db_session, design["id"])
    submit_attempt(api_client, design["id"], first_item.id, "wrong")
    submit_attempt(api_client, design["id"], second_item.id, "wrong")

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-checks/next")

    assert response.json()["test_design_item_id"] == first_item.id


def test_next_learning_check_excludes_mastered_items(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)
    first_item, second_item = learning_items(db_session, design["id"])
    first_answer = answer_for_item(db_session, first_item)
    submit_attempt(api_client, design["id"], first_item.id, first_answer)
    submit_attempt(api_client, design["id"], first_item.id, first_answer)

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-checks/next")

    assert response.status_code == 200
    assert response.json()["test_design_item_id"] == second_item.id


def test_next_learning_check_rejects_after_transition_to_assigning(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")
    submit_attempt(api_client, design["id"], item.id, "word1")

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-checks/next")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_not_learning_for_next_check"


def test_learning_attempt_scores_exact_correct_answer(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "word1")

    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_learning_attempt_accepts_outer_whitespace(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, " word1 ")

    assert response.json()["is_correct"] is True


def test_learning_attempt_accepts_case_differences(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "WORD1")

    assert response.json()["is_correct"] is True


def test_learning_attempt_rejects_internal_space_mismatch(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "wo rd1")

    assert response.json()["is_correct"] is False


def test_learning_attempt_rejects_synonym(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "term")

    assert response.json()["is_correct"] is False


def test_blank_answer_is_stored_and_scored_incorrect(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "")

    attempt = db_session.scalar(sa.select(VocabularyAttempt).where(VocabularyAttempt.test_design_item_id == item.id))
    assert response.json()["is_correct"] is False
    assert attempt.user_answer == ""
    assert attempt.normalized_answer == ""


def test_response_time_ms_is_stored(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "wrong", response_time_ms=2500)

    attempt = db_session.get(VocabularyAttempt, response.json()["attempt_id"])
    assert attempt.response_time_ms == 2500


def test_negative_response_time_is_rejected(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "word1", response_time_ms=-1)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "negative_response_time_ms"


def test_learning_attempt_row_uses_learning_check_fields(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "word1")

    attempt = db_session.get(VocabularyAttempt, response.json()["attempt_id"])
    assert attempt.attempt_type == VocabularyAttemptType.LEARNING_CHECK
    assert attempt.test_assignment_id is None
    assert attempt.actual_retention_seconds is None
    assert attempt.is_valid_for_fitting is False


def test_learning_attempt_for_item_from_another_design_is_rejected(api_client, db_session) -> None:
    first_participant = create_participant(db_session, "P-STAGE401")
    second_participant = create_participant(db_session, "P-STAGE402")
    seed_vocabulary(db_session, 4)
    first_design = create_design(api_client, first_participant.id, items_per_group=1, intervals=[10], random_seed=1)
    second_design = create_design(api_client, second_participant.id, items_per_group=1, intervals=[10], random_seed=2)
    start_learning(api_client, first_design["id"])
    start_learning(api_client, second_design["id"])
    other_item = learning_items(db_session, second_design["id"])[0]

    response = submit_attempt(api_client, first_design["id"], other_item.id, "word1")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "test_design_item_wrong_design"


def test_learning_attempt_for_already_mastered_item_is_rejected(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)
    item = learning_items(db_session, design["id"])[0]
    item_answer = answer_for_item(db_session, item)
    submit_attempt(api_client, design["id"], item.id, item_answer)
    submit_attempt(api_client, design["id"], item.id, item_answer)

    response = submit_attempt(api_client, design["id"], item.id, item_answer)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "item_already_mastered"


def test_learning_attempt_after_assigning_is_rejected(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")
    submit_attempt(api_client, design["id"], item.id, "word1")

    response = submit_attempt(api_client, design["id"], item.id, "word1")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_not_learning_for_attempt"


def test_first_correct_answer_does_not_master(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]

    response = submit_attempt(api_client, design["id"], item.id, "word1")

    assert response.json()["is_mastered"] is False
    assert response.json()["consecutive_correct_count"] == 1


def test_second_consecutive_correct_answer_masters(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")

    response = submit_attempt(api_client, design["id"], item.id, "word1")

    assert response.json()["is_mastered"] is True
    assert response.json()["consecutive_correct_count"] == 2


def test_incorrect_answer_resets_consecutive_count(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")

    response = submit_attempt(api_client, design["id"], item.id, "wrong")

    assert response.json()["consecutive_correct_count"] == 0


def test_total_correct_count_is_preserved_after_incorrect_answer(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")

    response = submit_attempt(api_client, design["id"], item.id, "wrong")

    assert response.json()["correct_count"] == 1
    assert response.json()["attempt_count"] == 2


def test_mastered_at_is_set_exactly_once(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)
    item = learning_items(db_session, design["id"])[0]
    item_answer = answer_for_item(db_session, item)
    submit_attempt(api_client, design["id"], item.id, item_answer)
    mastered_response = submit_attempt(api_client, design["id"], item.id, item_answer)
    mastered_at = mastered_response.json()["mastered_at"]

    rejected_response = submit_attempt(api_client, design["id"], item.id, item_answer)
    db_session.expire_all()
    stored_item = db_session.get(DesignItem, item.id)

    assert rejected_response.status_code == 409
    assert mastered_at.startswith(stored_item.mastered_at.isoformat())


def test_mastery_is_item_specific(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)
    first_item, second_item = learning_items(db_session, design["id"])
    first_answer = db_session.get(VocabularyItem, first_item.vocabulary_item_id).english_answer
    second_answer = db_session.get(VocabularyItem, second_item.vocabulary_item_id).english_answer

    first_response = submit_attempt(api_client, design["id"], first_item.id, first_answer)
    second_response = submit_attempt(api_client, design["id"], second_item.id, second_answer)

    assert first_response.json()["is_mastered"] is False
    assert second_response.json()["is_mastered"] is False


def test_final_item_mastery_transitions_design_to_assigning(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")

    response = submit_attempt(api_client, design["id"], item.id, "word1")

    assert response.json()["design_status"] == "assigning"
    assert response.json()["remaining_item_count"] == 0


def test_transition_to_assigning_creates_no_assignments(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")
    submit_attempt(api_client, design["id"], item.id, "word1")

    assignment_count = db_session.scalar(sa.select(sa.func.count()).select_from(Assignment))

    assert assignment_count == 0


def test_mastered_count_never_exceeds_required_count(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")
    final_response = submit_attempt(api_client, design["id"], item.id, "word1")
    rejected_response = submit_attempt(api_client, design["id"], item.id, "word1")

    assert final_response.json()["mastered_item_count"] == final_response.json()["required_item_count"]
    assert rejected_response.status_code == 409


def test_learning_progress_counts_are_calculated(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=2)
    first_item, second_item = learning_items(db_session, design["id"])
    first_answer = db_session.get(VocabularyItem, first_item.vocabulary_item_id).english_answer
    submit_attempt(api_client, design["id"], first_item.id, first_answer)
    submit_attempt(api_client, design["id"], first_item.id, "wrong")
    submit_attempt(api_client, design["id"], second_item.id, "wrong")

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-progress")

    assert response.status_code == 200
    body = response.json()
    assert body["required_item_count"] == 2
    assert body["pool_item_count"] == 2
    assert body["mastered_item_count"] == 0
    assert body["remaining_item_count"] == 2
    assert body["total_attempt_count"] == 3
    assert body["correct_attempt_count"] == 1
    assert body["learning_started_at"] is not None


def test_learning_progress_remains_readable_in_assigning_status(api_client, db_session) -> None:
    _, design = create_started_design(api_client, db_session, required_count=1)
    item = learning_items(db_session, design["id"])[0]
    submit_attempt(api_client, design["id"], item.id, "word1")
    submit_attempt(api_client, design["id"], item.id, "word1")

    response = api_client.get(f"/api/test-designs/{design['id']}/learning-progress")

    assert response.status_code == 200
    assert response.json()["status"] == "assigning"
    assert response.json()["remaining_item_count"] == 0

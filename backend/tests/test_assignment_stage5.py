import sqlalchemy as sa

from app.db.database import utc_now
from app.db.enums import (
    TestAssignmentStatus as AssignmentStatus,
    TestDesignGroupStatus as GroupStatus,
    TestDesignStatus as DesignStatus,
    VocabularyAttemptType,
)
from app.db.models import (
    Participant,
    TestAssignment as Assignment,
    TestDesign as Design,
    TestDesignGroup as DesignGroup,
    TestDesignItem as DesignItem,
    VocabularyAttempt,
    VocabularyItem,
)
from app.services.assignment import GROUP_ASSIGNMENT_NAMESPACE, select_group_assignment_item_ids
from app.services.learning import LEARNING_POOL_NAMESPACE, derive_deterministic_seed


def seed_vocabulary(db_session, count: int, *, start: int | None = None) -> None:
    start_index = start
    if start_index is None:
        existing_count = db_session.scalar(sa.select(sa.func.count()).select_from(VocabularyItem)) or 0
        start_index = existing_count + 1
    for index in range(start_index, start_index + count):
        db_session.add(
            VocabularyItem(
                korean=f"배정{index}",
                english_answer=f"word{index}",
                is_active=True,
                created_at=utc_now(),
            )
        )
    db_session.commit()


def create_participant(db_session, code: str = "P-STAGE500") -> Participant:
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


def design_items(db_session, design_id: int) -> list[DesignItem]:
    return list(
        db_session.scalars(
            sa.select(DesignItem).where(DesignItem.test_design_id == design_id).order_by(DesignItem.id)
        )
    )


def assignments(db_session, design_id: int) -> list[Assignment]:
    return list(
        db_session.scalars(
            sa.select(Assignment)
            .where(Assignment.test_design_id == design_id)
            .order_by(Assignment.assignment_order)
        )
    )


def answer_for_item(db_session, item: DesignItem) -> str:
    return db_session.get(VocabularyItem, item.vocabulary_item_id).english_answer


def create_assigning_design(
    api_client,
    db_session,
    *,
    participant_code: str = "P-STAGE500",
    items_per_group: int = 2,
    intervals=None,
    random_seed: int = 99,
    seed_items: bool = True,
) -> dict:
    intervals = intervals or [10, 20]
    participant = create_participant(db_session, participant_code)
    if seed_items:
        seed_vocabulary(db_session, items_per_group * len(intervals))
    design = create_design(
        api_client,
        participant.id,
        items_per_group=items_per_group,
        intervals=intervals,
        random_seed=random_seed,
    )
    start_response = api_client.post(f"/api/test-designs/{design['id']}/start-learning")
    assert start_response.status_code == 200
    for item in design_items(db_session, design["id"]):
        answer = answer_for_item(db_session, item)
        first_response = api_client.post(
            f"/api/test-designs/{design['id']}/learning-attempts",
            json={"test_design_item_id": item.id, "user_answer": answer},
        )
        second_response = api_client.post(
            f"/api/test-designs/{design['id']}/learning-attempts",
            json={"test_design_item_id": item.id, "user_answer": answer},
        )
        assert first_response.status_code == 200
        assert second_response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Design, design["id"]).status == DesignStatus.ASSIGNING
    return design


def initialize_assignments(api_client, design_id: int) -> dict:
    response = api_client.post(f"/api/test-designs/{design_id}/initialize-assignments")
    assert response.status_code == 200
    return response.json()


def initialize_activation_review_design(api_client, db_session, **kwargs) -> dict:
    design = create_assigning_design(api_client, db_session, **kwargs)
    initialize_assignments(api_client, design["id"])
    db_session.expire_all()
    return design


def complete_assignment(api_client, design_id: int, assignment_id: int):
    return api_client.post(f"/api/test-designs/{design_id}/activation-review/{assignment_id}/complete")


def test_assigning_design_initializes_successfully(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)

    response = api_client.post(f"/api/test-designs/{design['id']}/initialize-assignments")

    assert response.status_code == 200
    assert response.json()["status"] == "activation_review"


def test_exactly_required_item_count_assignments_are_created(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session, items_per_group=2, intervals=[10, 20, 30])

    initialize_assignments(api_client, design["id"])

    assert len(assignments(db_session, design["id"])) == 6


def test_every_design_item_receives_one_assignment(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)

    initialize_assignments(api_client, design["id"])

    assigned_item_ids = [assignment.test_design_item_id for assignment in assignments(db_session, design["id"])]
    assert sorted(assigned_item_ids) == sorted(item.id for item in design_items(db_session, design["id"]))


def test_every_group_receives_exactly_items_per_group_assignments(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session, items_per_group=3, intervals=[10, 20])

    initialize_assignments(api_client, design["id"])

    rows = db_session.execute(
        sa.select(Assignment.test_design_group_id, sa.func.count())
        .where(Assignment.test_design_id == design["id"])
        .group_by(Assignment.test_design_group_id)
    ).all()
    assert sorted(count for _, count in rows) == [3, 3]


def test_no_design_item_appears_in_multiple_groups(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)

    initialize_assignments(api_client, design["id"])

    assigned_item_ids = [assignment.test_design_item_id for assignment in assignments(db_session, design["id"])]
    assert len(assigned_item_ids) == len(set(assigned_item_ids))


def test_assignment_order_is_globally_unique(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session, items_per_group=2, intervals=[10, 20, 30])

    initialize_assignments(api_client, design["id"])

    orders = [assignment.assignment_order for assignment in assignments(db_session, design["id"])]
    assert len(orders) == len(set(orders))


def test_assignment_order_covers_required_range(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session, items_per_group=2, intervals=[10, 20, 30])

    initialize_assignments(api_client, design["id"])

    orders = [assignment.assignment_order for assignment in assignments(db_session, design["id"])]
    assert orders == list(range(1, 7))


def test_same_seed_produces_same_assignment_mapping(api_client, db_session) -> None:
    first_design = create_assigning_design(api_client, db_session, participant_code="P-STAGE501", random_seed=123)
    second_design = create_assigning_design(
        api_client,
        db_session,
        participant_code="P-STAGE502",
        random_seed=123,
        seed_items=False,
    )

    initialize_assignments(api_client, first_design["id"])
    initialize_assignments(api_client, second_design["id"])

    def order_for(design_id: int) -> list[int]:
        return [
            db_session.get(DesignItem, assignment.test_design_item_id).vocabulary_item_id
            for assignment in assignments(db_session, design_id)
        ]

    assert order_for(first_design["id"]) == order_for(second_design["id"])


def test_different_seed_normally_produces_different_assignment_mapping(api_client, db_session) -> None:
    first_design = create_assigning_design(api_client, db_session, participant_code="P-STAGE503", random_seed=123)
    second_design = create_assigning_design(
        api_client,
        db_session,
        participant_code="P-STAGE504",
        random_seed=456,
        seed_items=False,
    )

    initialize_assignments(api_client, first_design["id"])
    initialize_assignments(api_client, second_design["id"])

    first_order = [
        db_session.get(DesignItem, assignment.test_design_item_id).vocabulary_item_id
        for assignment in assignments(db_session, first_design["id"])
    ]
    second_order = [
        db_session.get(DesignItem, assignment.test_design_item_id).vocabulary_item_id
        for assignment in assignments(db_session, second_design["id"])
    ]
    assert first_order != second_order


def test_group_assignment_namespace_is_separate_from_learning_pool() -> None:
    assert derive_deterministic_seed(123, GROUP_ASSIGNMENT_NAMESPACE) != derive_deterministic_seed(
        123, LEARNING_POOL_NAMESPACE
    )
    assert select_group_assignment_item_ids([1, 2, 3, 4, 5], random_seed=123) != [1, 2, 3, 4, 5]


def test_assignments_start_as_awaiting_anchor_with_null_times(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)

    initialize_assignments(api_client, design["id"])

    for assignment in assignments(db_session, design["id"]):
        assert assignment.status == AssignmentStatus.AWAITING_ANCHOR
        assert assignment.anchor_at is None
        assert assignment.scheduled_at is None


def test_assignment_initialization_transitions_design(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)

    response = api_client.post(f"/api/test-designs/{design['id']}/initialize-assignments")

    db_session.expire_all()
    stored_design = db_session.get(Design, design["id"])
    assert response.json()["activation_review_started_at"] is not None
    assert stored_design.status == DesignStatus.ACTIVATION_REVIEW
    assert stored_design.activation_review_started_at is not None


def test_repeated_assignment_initialization_is_rejected(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session)

    response = api_client.post(f"/api/test-designs/{design['id']}/initialize-assignments")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_not_assigning"


def test_assignment_initialization_wrong_design_status_rejected(api_client, db_session) -> None:
    participant = create_participant(db_session)
    seed_vocabulary(db_session, 2)
    design = create_design(api_client, participant.id, items_per_group=1, intervals=[10, 20])

    response = api_client.post(f"/api/test-designs/{design['id']}/initialize-assignments")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_not_assigning"


def test_unmastered_item_causes_full_rollback(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)
    item = design_items(db_session, design["id"])[0]
    item.is_mastered = False
    item.mastered_at = None
    item.consecutive_correct_count = 1
    db_session.commit()

    response = api_client.post(f"/api/test-designs/{design['id']}/initialize-assignments")

    db_session.expire_all()
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "unmastered_design_items"
    assert db_session.get(Design, design["id"]).status == DesignStatus.ASSIGNING
    assert assignments(db_session, design["id"]) == []


def test_design_item_count_mismatch_causes_full_rollback(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)
    item = design_items(db_session, design["id"])[0]
    db_session.execute(sa.delete(VocabularyAttempt).where(VocabularyAttempt.test_design_item_id == item.id))
    db_session.execute(sa.delete(DesignItem).where(DesignItem.id == item.id))
    db_session.commit()

    response = api_client.post(f"/api/test-designs/{design['id']}/initialize-assignments")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_item_count_mismatch"
    assert db_session.get(Design, design["id"]).status == DesignStatus.ASSIGNING
    assert assignments(db_session, design["id"]) == []


def test_group_count_mismatch_causes_full_rollback(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)
    group = db_session.scalar(sa.select(DesignGroup).where(DesignGroup.test_design_id == design["id"]))
    db_session.delete(group)
    db_session.commit()

    response = api_client.post(f"/api/test-designs/{design['id']}/initialize-assignments")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "group_count_mismatch"
    assert db_session.get(Design, design["id"]).status == DesignStatus.ASSIGNING
    assert assignments(db_session, design["id"]) == []


def test_assignment_initialization_creates_no_attempt_rows(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)
    before_count = db_session.scalar(sa.select(sa.func.count()).select_from(VocabularyAttempt))

    initialize_assignments(api_client, design["id"])

    after_count = db_session.scalar(sa.select(sa.func.count()).select_from(VocabularyAttempt))
    delayed_count = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(VocabularyAttempt)
        .where(VocabularyAttempt.attempt_type == VocabularyAttemptType.DELAYED_RECALL)
    )
    assert after_count == before_count
    assert delayed_count == 0


def test_groups_are_assigned_in_group_index_order_and_interleaved(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session, items_per_group=2, intervals=[10, 20, 30])

    initialize_assignments(api_client, design["id"])

    group_indices = [assignment.test_design_group.group_index for assignment in assignments(db_session, design["id"])]
    assert group_indices == [1, 2, 3, 1, 2, 3]


def test_activation_next_returns_lowest_awaiting_order_with_answer_and_interval(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session)
    first_assignment = assignments(db_session, design["id"])[0]

    response = api_client.get(f"/api/test-designs/{design['id']}/activation-review/next")

    assert response.status_code == 200
    body = response.json()
    assert body["assignment_id"] == first_assignment.id
    assert body["assignment_order"] == 1
    assert body["completed_activation_count"] == 0
    assert body["remaining_activation_count"] == 4
    assert body["korean"]
    assert body["english_answer"]
    assert body["interval_seconds"] in {10, 20}


def test_activation_next_rejects_incorrect_design_status(api_client, db_session) -> None:
    design = create_assigning_design(api_client, db_session)

    response = api_client.get(f"/api/test-designs/{design['id']}/activation-review/next")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_not_activation_review"


def test_activation_next_returns_no_item_after_active(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session, items_per_group=1, intervals=[10])
    assignment = assignments(db_session, design["id"])[0]
    complete_assignment(api_client, design["id"], assignment.id)

    response = api_client.get(f"/api/test-designs/{design['id']}/activation-review/next")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_not_activation_review"


def test_activation_completion_records_anchor_and_schedule(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session)
    assignment = assignments(db_session, design["id"])[0]

    response = complete_assignment(api_client, design["id"], assignment.id)

    db_session.expire_all()
    stored_assignment = db_session.get(Assignment, assignment.id)
    assert response.status_code == 200
    assert stored_assignment.status == AssignmentStatus.PENDING
    assert stored_assignment.anchor_at is not None
    assert stored_assignment.scheduled_at is not None
    assert stored_assignment.completed_at is None
    assert (stored_assignment.scheduled_at - stored_assignment.anchor_at).total_seconds() == stored_assignment.test_design_group.interval_seconds
    assert response.json()["remaining_activation_count"] == 3
    assert response.json()["design_status"] == "activation_review"


def test_activation_completion_creates_no_attempt_rows(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session)
    assignment = assignments(db_session, design["id"])[0]
    before_count = db_session.scalar(sa.select(sa.func.count()).select_from(VocabularyAttempt))

    complete_assignment(api_client, design["id"], assignment.id)

    after_count = db_session.scalar(sa.select(sa.func.count()).select_from(VocabularyAttempt))
    assert after_count == before_count


def test_repeated_activation_is_rejected(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session)
    assignment = assignments(db_session, design["id"])[0]
    complete_assignment(api_client, design["id"], assignment.id)

    response = complete_assignment(api_client, design["id"], assignment.id)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "assignment_already_anchored"


def test_assignment_from_another_design_is_rejected(api_client, db_session) -> None:
    first_design = initialize_activation_review_design(api_client, db_session, participant_code="P-STAGE505")
    second_design = initialize_activation_review_design(
        api_client,
        db_session,
        participant_code="P-STAGE506",
        seed_items=False,
    )
    other_assignment = assignments(db_session, second_design["id"])[0]

    response = complete_assignment(api_client, first_design["id"], other_assignment.id)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "assignment_wrong_design"


def test_out_of_order_activation_is_rejected(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session)
    second_assignment = assignments(db_session, design["id"])[1]

    response = complete_assignment(api_client, design["id"], second_assignment.id)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "activation_out_of_order"


def test_final_activation_changes_design_to_active_and_sets_timestamps(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session, items_per_group=1, intervals=[10, 20])
    ordered_assignments = assignments(db_session, design["id"])

    first_response = complete_assignment(api_client, design["id"], ordered_assignments[0].id)
    final_response = complete_assignment(api_client, design["id"], ordered_assignments[1].id)

    db_session.expire_all()
    stored_design = db_session.get(Design, design["id"])
    stored_assignments = assignments(db_session, design["id"])
    assert first_response.json()["design_status"] == "activation_review"
    assert final_response.json()["design_status"] == "active"
    assert final_response.json()["activated_at"] is not None
    assert stored_design.status == DesignStatus.ACTIVE
    assert stored_design.activated_at is not None
    assert all(assignment.status == AssignmentStatus.PENDING for assignment in stored_assignments)
    assert all(assignment.anchor_at is not None for assignment in stored_assignments)
    assert all(assignment.scheduled_at is not None for assignment in stored_assignments)


def test_activation_progress_counts_are_correct(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session)
    first_assignment = assignments(db_session, design["id"])[0]
    complete_assignment(api_client, design["id"], first_assignment.id)

    response = api_client.get(f"/api/test-designs/{design['id']}/activation-review/progress")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "activation_review"
    assert body["total_assignment_count"] == 4
    assert body["anchored_assignment_count"] == 1
    assert body["remaining_activation_count"] == 3
    assert body["activation_review_started_at"] is not None
    assert body["activated_at"] is None


def test_activation_progress_remains_readable_after_active(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session, items_per_group=1, intervals=[10])
    assignment = assignments(db_session, design["id"])[0]
    complete_assignment(api_client, design["id"], assignment.id)

    response = api_client.get(f"/api/test-designs/{design['id']}/activation-review/progress")

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["remaining_activation_count"] == 0
    assert response.json()["activated_at"] is not None


def test_assignment_schedule_groups_are_ordered_and_counts_are_correct(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session, items_per_group=2, intervals=[30, 10])
    ordered_assignments = assignments(db_session, design["id"])
    complete_assignment(api_client, design["id"], ordered_assignments[0].id)
    complete_assignment(api_client, design["id"], ordered_assignments[1].id)

    response = api_client.get(f"/api/test-designs/{design['id']}/assignment-schedule")

    assert response.status_code == 200
    body = response.json()
    groups = body["groups"]
    assert [group["group_index"] for group in groups] == [1, 2]
    assert [group["assignment_count"] for group in groups] == [2, 2]
    assert [group["pending_count"] for group in groups] == [1, 1]
    assert [group["awaiting_anchor_count"] for group in groups] == [1, 1]
    assert [group["completed_count"] for group in groups] == [0, 0]


def test_assignment_schedule_earliest_and_latest_timestamps(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session, items_per_group=2, intervals=[10])
    ordered_assignments = assignments(db_session, design["id"])
    complete_assignment(api_client, design["id"], ordered_assignments[0].id)
    complete_assignment(api_client, design["id"], ordered_assignments[1].id)

    response = api_client.get(f"/api/test-designs/{design['id']}/assignment-schedule")

    group = response.json()["groups"][0]
    assert group["earliest_scheduled_at"] is not None
    assert group["latest_scheduled_at"] is not None
    assert group["earliest_scheduled_at"] <= group["latest_scheduled_at"]


def test_assignment_schedule_does_not_expose_english_answers(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session)

    response = api_client.get(f"/api/test-designs/{design['id']}/assignment-schedule")

    assert "english_answer" not in response.text


def test_test_design_group_remains_pending(api_client, db_session) -> None:
    design = initialize_activation_review_design(api_client, db_session, items_per_group=1, intervals=[10])
    assignment = assignments(db_session, design["id"])[0]
    complete_assignment(api_client, design["id"], assignment.id)

    group_statuses = list(
        db_session.scalars(
            sa.select(DesignGroup.status).where(DesignGroup.test_design_id == design["id"])
        )
    )

    assert group_statuses == [GroupStatus.PENDING]

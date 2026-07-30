from datetime import timedelta

import sqlalchemy as sa

from app.db.database import utc_now
from app.db.enums import (
    TestAssignmentStatus as AssignmentStatus,
    TestDesignGroupStatus as GroupStatus,
    TestDesignStatus as DesignStatus,
    VocabularyAttemptType,
)
from app.db.models import (
    CurveModel,
    Participant,
    TestAssignment as Assignment,
    TestDesign as Design,
    TestDesignGroup as DesignGroup,
    TestDesignItem as DesignItem,
    VocabularyAttempt,
    VocabularyItem,
)


def create_active_design(
    db_session,
    *,
    participant_code: str = "P-STAGE600",
    items_per_group: int = 2,
    intervals: list[int] | None = None,
    due_offsets: list[int] | None = None,
) -> tuple[Participant, Design]:
    intervals = intervals or [10, 20]
    required_count = items_per_group * len(intervals)
    due_offsets = due_offsets or [-60 for _ in range(required_count)]
    participant = Participant(participant_code=participant_code, created_at=utc_now())
    db_session.add(participant)
    db_session.flush()
    design = Design(
        participant_id=participant.id,
        items_per_group=items_per_group,
        group_count=len(intervals),
        random_seed=123,
        status=DesignStatus.ACTIVE,
        created_at=utc_now(),
        learning_started_at=utc_now() - timedelta(hours=1),
        activation_review_started_at=utc_now() - timedelta(minutes=30),
        activated_at=utc_now() - timedelta(minutes=20),
    )
    db_session.add(design)
    db_session.flush()
    groups: list[DesignGroup] = []
    for index, interval in enumerate(intervals, start=1):
        group = DesignGroup(
            test_design_id=design.id,
            group_index=index,
            interval_seconds=interval,
            status=GroupStatus.PENDING,
        )
        db_session.add(group)
        groups.append(group)
    db_session.flush()
    anchor_at = utc_now() - timedelta(minutes=10)
    for index in range(required_count):
        vocabulary = VocabularyItem(
            korean=f"회상{participant_code[-3:]}{index}",
            english_answer=f"word{index + 1}",
            is_active=True,
            created_at=utc_now(),
        )
        db_session.add(vocabulary)
        db_session.flush()
        item = DesignItem(
            test_design_id=design.id,
            vocabulary_item_id=vocabulary.id,
            attempt_count=2,
            correct_count=2,
            consecutive_correct_count=2,
            is_mastered=True,
            mastered_at=utc_now() - timedelta(minutes=40),
            created_at=utc_now() - timedelta(minutes=50),
            updated_at=utc_now() - timedelta(minutes=40),
        )
        db_session.add(item)
        db_session.flush()
        group = groups[index % len(groups)]
        scheduled_at = utc_now() + timedelta(seconds=due_offsets[index])
        db_session.add(
            Assignment(
                test_design_id=design.id,
                test_design_item_id=item.id,
                test_design_group_id=group.id,
                assignment_order=index + 1,
                anchor_at=anchor_at,
                scheduled_at=scheduled_at,
                status=AssignmentStatus.PENDING,
                created_at=utc_now() - timedelta(minutes=30),
                completed_at=None,
            )
        )
    db_session.commit()
    db_session.refresh(participant)
    db_session.refresh(design)
    return participant, design


def assignments(db_session, design_id: int) -> list[Assignment]:
    return list(
        db_session.scalars(
            sa.select(Assignment).where(Assignment.test_design_id == design_id).order_by(Assignment.assignment_order)
        )
    )


def answer_for_assignment(db_session, assignment: Assignment) -> str:
    item = db_session.get(DesignItem, assignment.test_design_item_id)
    return db_session.get(VocabularyItem, item.vocabulary_item_id).english_answer


def submit(api_client, design_id: int, assignment_id: int, answer: str, response_time_ms=None):
    return api_client.post(
        f"/api/test-designs/{design_id}/delayed-recalls/{assignment_id}",
        json={"user_answer": answer, "response_time_ms": response_time_ms},
    )


def complete_group(api_client, db_session, design: Design, group_index: int = 1) -> None:
    for assignment in assignments(db_session, design.id):
        if assignment.test_design_group.group_index == group_index and assignment.status == AssignmentStatus.PENDING:
            response = submit(api_client, design.id, assignment.id, answer_for_assignment(db_session, assignment))
            assert response.status_code == 200


def test_next_due_returns_earliest_due_assignment_and_counts(api_client, db_session) -> None:
    _, design = create_active_design(db_session, due_offsets=[-30, -120, 600, -120])

    response = api_client.get(f"/api/test-designs/{design.id}/delayed-recalls/next")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["due_count"] == 3
    assert body["pending_count"] == 4
    assert body["assignment"]["assignment_id"] == assignments(db_session, design.id)[1].id
    assert "english_answer" not in response.text
    assert "anchor_at" not in response.text


def test_next_due_orders_by_scheduled_at_then_assignment_order(api_client, db_session) -> None:
    _, design = create_active_design(db_session, due_offsets=[-100, -100, -10, -100])

    response = api_client.get(f"/api/test-designs/{design.id}/delayed-recalls/next")

    assert response.json()["assignment"]["assignment_id"] == assignments(db_session, design.id)[0].id


def test_next_due_returns_available_false_for_future_assignments(api_client, db_session) -> None:
    _, design = create_active_design(db_session, due_offsets=[300, 600, 900, 1200])

    response = api_client.get(f"/api/test-designs/{design.id}/delayed-recalls/next")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["due_count"] == 0
    assert body["pending_count"] == 4
    assert body["assignment"] is None
    assert body["next_scheduled_at"] is not None


def test_next_due_rejects_non_active_design_and_is_read_only(api_client, db_session) -> None:
    _, design = create_active_design(db_session)
    design.status = DesignStatus.ACTIVATION_REVIEW
    db_session.commit()
    before = [(assignment.id, assignment.status, assignment.completed_at) for assignment in assignments(db_session, design.id)]

    response = api_client.get(f"/api/test-designs/{design.id}/delayed-recalls/next")

    after = [(assignment.id, assignment.status, assignment.completed_at) for assignment in assignments(db_session, design.id)]
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "design_not_active"
    assert after == before


def test_delayed_submission_exact_answer_and_storage(api_client, db_session) -> None:
    _, design = create_active_design(db_session)
    assignment = assignments(db_session, design.id)[0]

    response = submit(api_client, design.id, assignment.id, answer_for_assignment(db_session, assignment), 3200)

    db_session.expire_all()
    attempt = db_session.scalar(sa.select(VocabularyAttempt).where(VocabularyAttempt.test_assignment_id == assignment.id))
    stored_assignment = db_session.get(Assignment, assignment.id)
    assert response.status_code == 200
    assert attempt.is_correct is True
    assert attempt.response_time_ms == 3200
    assert attempt.attempt_type == VocabularyAttemptType.DELAYED_RECALL
    assert attempt.is_valid_for_fitting is True
    assert attempt.exclusion_reason is None
    assert stored_assignment.status == AssignmentStatus.COMPLETED
    assert stored_assignment.completed_at == attempt.attempted_at
    assert "canonical_answer" not in response.text
    assert "is_correct" not in response.text


def test_delayed_submission_scoring_policy(api_client, db_session) -> None:
    _, design = create_active_design(db_session, items_per_group=3, intervals=[10])
    first, second, third = assignments(db_session, design.id)

    assert submit(api_client, design.id, first.id, f" {answer_for_assignment(db_session, first).upper()} ").status_code == 200
    assert submit(api_client, design.id, second.id, "synonym").status_code == 200
    assert submit(api_client, design.id, third.id, "").status_code == 200

    attempts = list(db_session.scalars(sa.select(VocabularyAttempt).order_by(VocabularyAttempt.id)))
    assert [attempt.is_correct for attempt in attempts] == [True, False, False]
    assert attempts[2].user_answer == ""
    assert attempts[2].normalized_answer == ""


def test_negative_response_time_and_early_submission_are_rejected(api_client, db_session) -> None:
    _, design = create_active_design(db_session, due_offsets=[600, -60, -60, -60])
    first, second = assignments(db_session, design.id)[:2]

    negative_response = submit(api_client, design.id, second.id, answer_for_assignment(db_session, second), -1)
    early_response = submit(api_client, design.id, first.id, answer_for_assignment(db_session, first))

    assert negative_response.status_code == 422
    assert negative_response.json()["detail"]["code"] == "negative_response_time_ms"
    assert early_response.status_code == 409
    assert early_response.json()["detail"]["code"] == "assignment_not_yet_due"
    assert db_session.scalar(sa.select(sa.func.count()).select_from(VocabularyAttempt)) == 0


def test_on_time_and_late_submission_use_actual_retention_not_target(api_client, db_session) -> None:
    _, design = create_active_design(db_session, items_per_group=2, intervals=[1], due_offsets=[0, -600])
    first, second = assignments(db_session, design.id)

    on_time_response = submit(api_client, design.id, first.id, answer_for_assignment(db_session, first))
    late_response = submit(api_client, design.id, second.id, answer_for_assignment(db_session, second))

    assert on_time_response.status_code == 200
    assert late_response.status_code == 200
    assert late_response.json()["lateness_seconds"] > 0
    assert late_response.json()["actual_retention_seconds"] != late_response.json()["target_interval_seconds"]


def test_anchor_and_schedule_are_not_overwritten_and_duplicate_rejected(api_client, db_session) -> None:
    _, design = create_active_design(db_session)
    assignment = assignments(db_session, design.id)[0]
    original_anchor = assignment.anchor_at
    original_schedule = assignment.scheduled_at
    response = submit(api_client, design.id, assignment.id, answer_for_assignment(db_session, assignment))
    duplicate_response = submit(api_client, design.id, assignment.id, answer_for_assignment(db_session, assignment))

    db_session.expire_all()
    stored_assignment = db_session.get(Assignment, assignment.id)
    assert response.status_code == 200
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"]["code"] == "assignment_already_completed"
    assert stored_assignment.anchor_at == original_anchor
    assert stored_assignment.scheduled_at == original_schedule


def test_assignment_from_another_design_and_non_pending_rejected(api_client, db_session) -> None:
    _, first_design = create_active_design(db_session, participant_code="P-STAGE601")
    _, second_design = create_active_design(db_session, participant_code="P-STAGE602")
    other_assignment = assignments(db_session, second_design.id)[0]
    own_assignment = assignments(db_session, first_design.id)[0]
    own_assignment.status = AssignmentStatus.AWAITING_ANCHOR
    own_assignment.anchor_at = None
    own_assignment.scheduled_at = None
    db_session.commit()

    wrong_design_response = submit(api_client, first_design.id, other_assignment.id, "word")
    non_pending_response = submit(api_client, first_design.id, own_assignment.id, "word")

    assert wrong_design_response.status_code == 409
    assert wrong_design_response.json()["detail"]["code"] == "assignment_wrong_design"
    assert non_pending_response.status_code == 409
    assert non_pending_response.json()["detail"]["code"] == "assignment_not_pending"


def test_group_completion_rules(api_client, db_session) -> None:
    _, design = create_active_design(db_session, items_per_group=2, intervals=[10, 20])
    group_one_assignments = [assignment for assignment in assignments(db_session, design.id) if assignment.test_design_group.group_index == 1]
    first_response = submit(api_client, design.id, group_one_assignments[0].id, answer_for_assignment(db_session, group_one_assignments[0]))
    group = db_session.get(DesignGroup, group_one_assignments[0].test_design_group_id)
    first_completed_at = group.completed_at
    second_response = submit(api_client, design.id, group_one_assignments[1].id, answer_for_assignment(db_session, group_one_assignments[1]))
    db_session.refresh(group)

    assert first_response.json()["group_status"] == "pending"
    assert first_completed_at is None
    assert second_response.json()["group_status"] == "completed"
    assert group.status == GroupStatus.COMPLETED
    assert group.completed_at is not None


def test_invalid_fitting_result_prevents_group_completion(api_client, db_session) -> None:
    _, design = create_active_design(db_session, items_per_group=2, intervals=[10])
    first, second = assignments(db_session, design.id)
    submit(api_client, design.id, first.id, answer_for_assignment(db_session, first))
    attempt = db_session.scalar(sa.select(VocabularyAttempt).where(VocabularyAttempt.test_assignment_id == first.id))
    attempt.is_valid_for_fitting = False
    attempt.exclusion_reason = "manual invalidation"
    db_session.commit()

    submit(api_client, design.id, second.id, answer_for_assignment(db_session, second))

    group = db_session.get(DesignGroup, first.test_design_group_id)
    assert group.status == GroupStatus.PENDING


def test_final_completed_group_completes_design_and_no_curve_created(api_client, db_session) -> None:
    _, design = create_active_design(db_session, items_per_group=1, intervals=[10, 20])
    ordered_assignments = assignments(db_session, design.id)
    first_response = submit(api_client, design.id, ordered_assignments[0].id, answer_for_assignment(db_session, ordered_assignments[0]))
    final_response = submit(api_client, design.id, ordered_assignments[1].id, answer_for_assignment(db_session, ordered_assignments[1]))

    db_session.expire_all()
    stored_design = db_session.get(Design, design.id)
    assert first_response.json()["design_status"] == "active"
    assert final_response.json()["design_status"] == "completed"
    assert stored_design.status == DesignStatus.COMPLETED
    assert stored_design.completed_at is not None
    assert db_session.scalar(sa.select(sa.func.count()).select_from(CurveModel)) == 0
    assert submit(api_client, design.id, ordered_assignments[1].id, "word").status_code == 409


def test_participant_can_create_new_draft_after_completed_design(api_client, db_session) -> None:
    participant, design = create_active_design(db_session, items_per_group=1, intervals=[10])
    assignment = assignments(db_session, design.id)[0]
    submit(api_client, design.id, assignment.id, answer_for_assignment(db_session, assignment))
    seed_extra = VocabularyItem(korean="새단어", english_answer="new", is_active=True, created_at=utc_now())
    db_session.add(seed_extra)
    db_session.commit()

    response = api_client.post(
        "/api/test-designs",
        json={"participant_id": participant.id, "items_per_group": 1, "intervals_seconds": [10]},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_delayed_recall_progress_counts_and_completion_readability(api_client, db_session) -> None:
    _, design = create_active_design(db_session, items_per_group=1, intervals=[10, 20], due_offsets=[-60, 600])
    first, second = assignments(db_session, design.id)
    submit(api_client, design.id, first.id, answer_for_assignment(db_session, first))
    active_response = api_client.get(f"/api/test-designs/{design.id}/delayed-recalls/progress")
    second.scheduled_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    submit(api_client, design.id, second.id, answer_for_assignment(db_session, second))
    completed_response = api_client.get(f"/api/test-designs/{design.id}/delayed-recalls/progress")

    assert active_response.status_code == 200
    assert active_response.json()["total_assignment_count"] == 2
    assert active_response.json()["completed_assignment_count"] == 1
    assert active_response.json()["pending_assignment_count"] == 1
    assert active_response.json()["due_assignment_count"] == 0
    assert active_response.json()["completed_group_count"] == 1
    assert active_response.json()["next_scheduled_at"] is not None
    assert completed_response.json()["status"] == "completed"
    assert completed_response.json()["completed_at"] is not None


def test_retention_summary_raw_statistics_and_privacy(api_client, db_session) -> None:
    _, design = create_active_design(db_session, items_per_group=2, intervals=[10, 20])
    group_one_assignments = [assignment for assignment in assignments(db_session, design.id) if assignment.test_design_group.group_index == 1]
    submit(api_client, design.id, group_one_assignments[0].id, answer_for_assignment(db_session, group_one_assignments[0]))
    submit(api_client, design.id, group_one_assignments[1].id, "wrong")

    response = api_client.get(f"/api/test-designs/{design.id}/retention-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["curve_available"] is False
    assert "T" not in body
    assert "c" not in body
    assert "user_answer" not in response.text
    assert "english_answer" not in response.text
    assert [group["group_index"] for group in body["groups"]] == [1, 2]
    completed_group = body["groups"][0]
    empty_group = body["groups"][1]
    assert completed_group["correct_count"] == 1
    assert completed_group["incorrect_count"] == 1
    assert completed_group["observed_accuracy"] == 0.5
    assert completed_group["mean_actual_retention_seconds"] is not None
    assert completed_group["minimum_actual_retention_seconds"] is not None
    assert completed_group["maximum_actual_retention_seconds"] is not None
    assert empty_group["correct_count"] is None
    assert empty_group["observed_accuracy"] is None
    assert body["complete_time_point_count"] == 1


def test_partial_group_visible_but_not_complete_time_point(api_client, db_session) -> None:
    _, design = create_active_design(db_session, items_per_group=2, intervals=[10])
    first_assignment = assignments(db_session, design.id)[0]
    submit(api_client, design.id, first_assignment.id, answer_for_assignment(db_session, first_assignment))

    response = api_client.get(f"/api/test-designs/{design.id}/retention-summary")

    group = response.json()["groups"][0]
    assert group["completed_count"] == 1
    assert group["valid_result_count"] == 1
    assert response.json()["complete_time_point_count"] == 0


def test_participant_retention_history_filters_and_orders_designs(api_client, db_session) -> None:
    participant, first_design = create_active_design(db_session, participant_code="P-STAGE603", items_per_group=1, intervals=[10])
    _, other_design = create_active_design(db_session, participant_code="P-STAGE604", items_per_group=1, intervals=[10])
    first_assignment = assignments(db_session, first_design.id)[0]
    submit(api_client, first_design.id, first_assignment.id, answer_for_assignment(db_session, first_assignment))
    second_design = create_active_design(
        db_session,
        participant_code="P-STAGE605",
        items_per_group=1,
        intervals=[10],
    )[1]
    second_design.participant_id = participant.id
    second_design.created_at = first_design.created_at + timedelta(seconds=1)
    db_session.commit()

    response = api_client.get(f"/api/participants/{participant.id}/retention-history")
    missing_response = api_client.get("/api/participants/999/retention-history")

    assert response.status_code == 200
    body = response.json()
    assert [design["test_design_id"] for design in body["designs"]] == [first_design.id, second_design.id]
    assert other_design.id not in [design["test_design_id"] for design in body["designs"]]
    assert body["designs"][0]["curve_available"] is False
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"]["code"] == "participant_not_found"

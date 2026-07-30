from datetime import timedelta
import math

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
    TestAssignment as Assignment,
    TestDesignItem as DesignItem,
    TestDesignGroup as DesignGroup,
    VocabularyAttempt,
    VocabularyItem,
)
from app.services.delayed_recall import elapsed_seconds


INTERVALS_SECONDS = [60, 180, 300, 600, 1200]
ITEMS_PER_GROUP = 4


def seed_vocabulary(db_session, count: int = 60) -> None:
    timestamp = utc_now()
    db_session.add_all(
        [
            VocabularyItem(
                korean=f"단어{index}",
                english_answer=f"word{index}",
                is_active=True,
                created_at=timestamp,
            )
            for index in range(1, count + 1)
        ]
    )
    db_session.commit()


def make_assignments_due(db_session, test_design_id: int) -> None:
    db_session.rollback()
    base_time = utc_now() - timedelta(minutes=10)
    assignments = list(
        db_session.scalars(
            sa.select(Assignment)
            .where(Assignment.test_design_id == test_design_id)
            .options(sa.orm.selectinload(Assignment.test_design_group))
            .order_by(Assignment.assignment_order)
        )
    )
    for index, assignment in enumerate(assignments, start=1):
        interval_seconds = assignment.test_design_group.interval_seconds
        anchor_at = base_time - timedelta(seconds=interval_seconds + index)
        assignment.anchor_at = anchor_at
        assignment.scheduled_at = anchor_at + timedelta(seconds=interval_seconds)
        assignment.status = AssignmentStatus.PENDING
    db_session.commit()


def assert_assignment_invariants(db_session, test_design_id: int) -> None:
    db_session.rollback()
    groups = list(
        db_session.scalars(
            sa.select(DesignGroup)
            .where(DesignGroup.test_design_id == test_design_id)
            .order_by(DesignGroup.group_index)
        )
    )
    assignments = list(
        db_session.scalars(
            sa.select(Assignment)
            .where(Assignment.test_design_id == test_design_id)
            .options(sa.orm.selectinload(Assignment.test_design_group))
            .order_by(Assignment.assignment_order)
        )
    )
    assert len(assignments) == ITEMS_PER_GROUP * len(INTERVALS_SECONDS)
    assert sorted(assignment.assignment_order for assignment in assignments) == list(range(1, len(assignments) + 1))
    assert len({assignment.test_design_item_id for assignment in assignments}) == len(assignments)
    for group in groups:
        assert sum(1 for assignment in assignments if assignment.test_design_group_id == group.id) == ITEMS_PER_GROUP
    for assignment in assignments:
        assert assignment.anchor_at is not None
        assert assignment.scheduled_at is not None
        assert elapsed_seconds(assignment.scheduled_at, assignment.anchor_at) == assignment.test_design_group.interval_seconds


def assert_completion_invariants(db_session, test_design_id: int) -> None:
    db_session.rollback()
    groups = list(db_session.scalars(sa.select(DesignGroup).where(DesignGroup.test_design_id == test_design_id)))
    assignments = list(
        db_session.scalars(
            sa.select(Assignment)
            .where(Assignment.test_design_id == test_design_id)
            .options(sa.orm.selectinload(Assignment.vocabulary_attempt))
        )
    )
    assert all(group.status == GroupStatus.COMPLETED for group in groups)
    assert all(assignment.status == AssignmentStatus.COMPLETED for assignment in assignments)
    for assignment in assignments:
        attempt = assignment.vocabulary_attempt
        assert attempt is not None
        assert attempt.attempt_type == VocabularyAttemptType.DELAYED_RECALL
        assert attempt.is_valid_for_fitting is True
        assert attempt.actual_retention_seconds == elapsed_seconds(attempt.attempted_at, assignment.anchor_at)
    design_item_count = db_session.scalar(
        sa.select(sa.func.count()).select_from(DesignItem).where(DesignItem.test_design_id == test_design_id)
    )
    learning_fit_count = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(VocabularyAttempt)
        .join(DesignItem, DesignItem.id == VocabularyAttempt.test_design_item_id)
        .where(DesignItem.test_design_id == test_design_id)
        .where(VocabularyAttempt.attempt_type == VocabularyAttemptType.LEARNING_CHECK)
        .where(VocabularyAttempt.is_valid_for_fitting.is_(True))
    )
    assert design_item_count == ITEMS_PER_GROUP * len(INTERVALS_SECONDS)
    assert learning_fit_count == 0


def complete_design(api_client, db_session, participant_id: int) -> int:
    design_response = api_client.post(
        "/api/test-designs",
        json={
            "participant_id": participant_id,
            "items_per_group": ITEMS_PER_GROUP,
            "intervals_seconds": INTERVALS_SECONDS,
        },
    )
    assert design_response.status_code == 201
    design = design_response.json()
    test_design_id = design["id"]
    assert design["required_item_count"] == ITEMS_PER_GROUP * len(INTERVALS_SECONDS)

    start_response = api_client.post(f"/api/test-designs/{test_design_id}/start-learning")
    assert start_response.status_code == 200
    materials_response = api_client.get(f"/api/test-designs/{test_design_id}/learning-materials")
    assert materials_response.status_code == 200
    answer_by_item_id = {
        item["test_design_item_id"]: item["english_answer"]
        for item in materials_response.json()["items"]
    }
    assert len(answer_by_item_id) == ITEMS_PER_GROUP * len(INTERVALS_SECONDS)

    for _ in range(len(answer_by_item_id) * 2):
        next_response = api_client.get(f"/api/test-designs/{test_design_id}/learning-checks/next")
        assert next_response.status_code == 200
        next_item_id = next_response.json()["test_design_item_id"]
        attempt_response = api_client.post(
            f"/api/test-designs/{test_design_id}/learning-attempts",
            json={
                "test_design_item_id": next_item_id,
                "user_answer": answer_by_item_id[next_item_id],
                "response_time_ms": 100,
            },
        )
        assert attempt_response.status_code == 200
        if attempt_response.json()["design_status"] == DesignStatus.ASSIGNING.value:
            break

    progress_response = api_client.get(f"/api/test-designs/{test_design_id}/learning-progress")
    assert progress_response.status_code == 200
    assert progress_response.json()["status"] == DesignStatus.ASSIGNING.value
    assert progress_response.json()["mastered_item_count"] == len(answer_by_item_id)

    initialization_response = api_client.post(f"/api/test-designs/{test_design_id}/initialize-assignments")
    assert initialization_response.status_code == 200
    assert initialization_response.json()["status"] == DesignStatus.ACTIVATION_REVIEW.value
    assert all(group["assignment_count"] == ITEMS_PER_GROUP for group in initialization_response.json()["groups"])

    activation_seen = []
    while True:
        next_activation_response = api_client.get(f"/api/test-designs/{test_design_id}/activation-review/next")
        assert next_activation_response.status_code == 200
        activation_body = next_activation_response.json()
        activation_seen.append(activation_body["assignment_id"])
        completion_response = api_client.post(
            f"/api/test-designs/{test_design_id}/activation-review/{activation_body['assignment_id']}/complete"
        )
        assert completion_response.status_code == 200
        if completion_response.json()["design_status"] == DesignStatus.ACTIVE.value:
            break

    assert len(activation_seen) == len(answer_by_item_id)
    assert_assignment_invariants(db_session, test_design_id)
    make_assignments_due(db_session, test_design_id)

    submitted_correct = 0
    submitted_incorrect = 0
    while True:
        progress_response = api_client.get(f"/api/test-designs/{test_design_id}/delayed-recalls/progress")
        assert progress_response.status_code == 200
        if progress_response.json()["status"] == DesignStatus.COMPLETED.value:
            break
        next_delayed_response = api_client.get(f"/api/test-designs/{test_design_id}/delayed-recalls/next")
        assert next_delayed_response.status_code == 200
        next_body = next_delayed_response.json()
        assert next_body["available"] is True
        assignment = next_body["assignment"]
        correct_answer = answer_by_item_id[assignment["test_design_item_id"]]
        is_correct = assignment["assignment_id"] % 3 != 0
        submission_response = api_client.post(
            f"/api/test-designs/{test_design_id}/delayed-recalls/{assignment['assignment_id']}",
            json={
                "user_answer": correct_answer if is_correct else "incorrect response",
                "response_time_ms": 200,
            },
        )
        assert submission_response.status_code == 200
        submission_body = submission_response.json()
        assert "is_correct" not in submission_body
        assert "canonical_answer" not in submission_body
        submitted_correct += 1 if is_correct else 0
        submitted_incorrect += 0 if is_correct else 1

    assert submitted_correct > 0
    assert submitted_incorrect > 0
    final_progress = api_client.get(f"/api/test-designs/{test_design_id}/delayed-recalls/progress").json()
    assert final_progress["completed_group_count"] == len(INTERVALS_SECONDS)
    assert final_progress["completed_assignment_count"] == len(answer_by_item_id)
    assert_completion_invariants(db_session, test_design_id)
    return test_design_id


def test_complete_mvp_lifecycle_generates_append_only_curve_versions(api_client, db_session) -> None:
    seed_vocabulary(db_session)
    participant_response = api_client.post("/api/participants", json={})
    assert participant_response.status_code == 201
    participant_id = participant_response.json()["id"]

    first_design_id = complete_design(api_client, db_session, participant_id)
    first_eligibility = api_client.get(f"/api/test-designs/{first_design_id}/curve-eligibility")
    assert first_eligibility.status_code == 200
    assert first_eligibility.json()["eligible"] is True

    first_curve_response = api_client.post(f"/api/test-designs/{first_design_id}/curve-model")
    repeated_first_curve_response = api_client.post(f"/api/test-designs/{first_design_id}/curve-model")
    assert first_curve_response.status_code == 200
    assert repeated_first_curve_response.status_code == 200
    first_curve = first_curve_response.json()
    assert first_curve["created"] is True
    assert repeated_first_curve_response.json()["created"] is False
    assert first_curve["curve"]["version"] == 1
    assert first_curve["curve"]["sample_count"] == ITEMS_PER_GROUP * len(INTERVALS_SECONDS)
    assert math.isfinite(first_curve["curve"]["T_seconds"])
    assert math.isfinite(first_curve["curve"]["c"])
    assert first_curve["curve"]["T_seconds"] > 0
    assert first_curve["curve"]["c"] > 0
    first_version_snapshot = api_client.get(f"/api/participants/{participant_id}/curve-models/1").json()

    second_design_id = complete_design(api_client, db_session, participant_id)
    second_curve_response = api_client.post(f"/api/test-designs/{second_design_id}/curve-model")
    assert second_curve_response.status_code == 200
    second_curve = second_curve_response.json()
    assert second_curve["created"] is True
    assert second_curve["curve"]["version"] == 2
    assert second_curve["curve"]["sample_count"] == first_curve["curve"]["sample_count"] * 2
    assert second_curve["curve"]["complete_time_point_count"] == len(INTERVALS_SECONDS) * 2

    later_first_version_snapshot = api_client.get(f"/api/participants/{participant_id}/curve-models/1").json()
    assert later_first_version_snapshot == first_version_snapshot
    assert db_session.scalar(sa.select(sa.func.count()).select_from(CurveModel)) == 2

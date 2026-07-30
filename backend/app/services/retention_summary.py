from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import TestAssignmentStatus, TestDesignGroupStatus, TestDesignStatus, VocabularyAttemptType
from app.db.models import Participant, TestAssignment, TestDesign, TestDesignGroup, VocabularyAttempt
from app.services.exceptions import ConflictError, NotFoundError


REQUIRED_TIME_POINT_COUNT_FOR_CURVE = 5


def _get_design(session: Session, test_design_id: int) -> TestDesign:
    design = session.get(TestDesign, test_design_id)
    if design is None:
        raise NotFoundError("test_design_not_found", "Test design was not found.")
    return design


def _require_summary_design(design: TestDesign) -> None:
    if design.status not in {TestDesignStatus.ACTIVE, TestDesignStatus.COMPLETED}:
        raise ConflictError(
            "design_not_active_or_completed",
            "Retention summary is available only for active or completed designs.",
        )


def group_retention_summary(session: Session, group: TestDesignGroup) -> dict:
    assignments = list(
        session.scalars(
            select(TestAssignment)
            .where(TestAssignment.test_design_group_id == group.id)
            .order_by(TestAssignment.assignment_order)
        )
    )
    assignment_ids = [assignment.id for assignment in assignments]
    valid_attempts = []
    if assignment_ids:
        valid_attempts = list(
            session.scalars(
                select(VocabularyAttempt)
                .where(VocabularyAttempt.test_assignment_id.in_(assignment_ids))
                .where(VocabularyAttempt.attempt_type == VocabularyAttemptType.DELAYED_RECALL)
                .where(VocabularyAttempt.is_valid_for_fitting.is_(True))
            )
        )

    valid_result_count = len(valid_attempts)
    correct_count = sum(1 for attempt in valid_attempts if attempt.is_correct)
    actual_retention_values = [
        attempt.actual_retention_seconds
        for attempt in valid_attempts
        if attempt.actual_retention_seconds is not None
    ]
    return {
        "test_design_group_id": group.id,
        "group_index": group.group_index,
        "target_interval_seconds": group.interval_seconds,
        "status": group.status.value,
        "assignment_count": len(assignments),
        "completed_count": sum(1 for assignment in assignments if assignment.status == TestAssignmentStatus.COMPLETED),
        "valid_result_count": valid_result_count,
        "correct_count": correct_count if valid_result_count else None,
        "incorrect_count": valid_result_count - correct_count if valid_result_count else None,
        "observed_accuracy": correct_count / valid_result_count if valid_result_count else None,
        "mean_actual_retention_seconds": (
            sum(actual_retention_values) / len(actual_retention_values) if actual_retention_values else None
        ),
        "minimum_actual_retention_seconds": min(actual_retention_values) if actual_retention_values else None,
        "maximum_actual_retention_seconds": max(actual_retention_values) if actual_retention_values else None,
    }


def retention_summary_for_design(session: Session, design: TestDesign) -> dict:
    groups = list(
        session.scalars(
            select(TestDesignGroup)
            .where(TestDesignGroup.test_design_id == design.id)
            .order_by(TestDesignGroup.group_index)
        )
    )
    group_summaries = [group_retention_summary(session, group) for group in groups]
    complete_time_point_count = sum(1 for group in groups if group.status == TestDesignGroupStatus.COMPLETED)
    return {
        "test_design_id": design.id,
        "status": design.status.value,
        "complete_time_point_count": complete_time_point_count,
        "required_time_point_count_for_curve": REQUIRED_TIME_POINT_COUNT_FOR_CURVE,
        "curve_available": False,
        "groups": group_summaries,
    }


def get_retention_summary(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    _require_summary_design(design)
    return retention_summary_for_design(session, design)


def get_participant_retention_history(session: Session, participant_id: int) -> dict:
    participant = session.get(Participant, participant_id)
    if participant is None:
        raise NotFoundError("participant_not_found", "Participant was not found.")

    designs = list(
        session.scalars(
            select(TestDesign)
            .where(TestDesign.participant_id == participant_id)
            .where(TestDesign.status.in_([TestDesignStatus.ACTIVE, TestDesignStatus.COMPLETED]))
            .order_by(TestDesign.created_at, TestDesign.id)
        )
    )
    return {
        "participant_id": participant_id,
        "designs": [
            {
                **retention_summary_for_design(session, design),
                "created_at": design.created_at,
                "activated_at": design.activated_at,
                "completed_at": design.completed_at,
            }
            for design in designs
        ],
    }

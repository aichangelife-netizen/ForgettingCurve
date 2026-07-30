from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.database import utc_now
from app.db.enums import TestAssignmentStatus, TestDesignGroupStatus, TestDesignStatus, VocabularyAttemptType
from app.db.models import (
    TestAssignment,
    TestDesign,
    TestDesignGroup,
    TestDesignItem,
    VocabularyAttempt,
)
from app.services.answer_scoring import check_answer, normalize_answer
from app.services.exceptions import ConflictError, NotFoundError, ValidationServiceError


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def elapsed_seconds(later: datetime, earlier: datetime) -> int:
    return int((as_utc(later) - as_utc(earlier)).total_seconds())


def _get_design(session: Session, test_design_id: int) -> TestDesign:
    design = session.get(TestDesign, test_design_id)
    if design is None:
        raise NotFoundError("test_design_not_found", "Test design was not found.")
    return design


def _require_active_design(design: TestDesign) -> None:
    if design.status != TestDesignStatus.ACTIVE:
        raise ConflictError("design_not_active", "Test design must be active.")


def _assignment_details_query(test_design_id: int):
    return (
        select(TestAssignment)
        .where(TestAssignment.test_design_id == test_design_id)
        .options(
            selectinload(TestAssignment.test_design_item).selectinload(TestDesignItem.vocabulary_item),
            selectinload(TestAssignment.test_design_group),
        )
    )


def _pending_count(session: Session, test_design_id: int) -> int:
    return session.scalar(
        select(func.count())
        .select_from(TestAssignment)
        .where(TestAssignment.test_design_id == test_design_id)
        .where(TestAssignment.status == TestAssignmentStatus.PENDING)
    ) or 0


def _due_count(session: Session, test_design_id: int, server_time: datetime) -> int:
    return session.scalar(
        select(func.count())
        .select_from(TestAssignment)
        .where(TestAssignment.test_design_id == test_design_id)
        .where(TestAssignment.status == TestAssignmentStatus.PENDING)
        .where(TestAssignment.scheduled_at.is_not(None))
        .where(TestAssignment.scheduled_at <= server_time)
    ) or 0


def _next_scheduled_at(session: Session, test_design_id: int, server_time: datetime) -> datetime | None:
    return session.scalar(
        select(func.min(TestAssignment.scheduled_at))
        .where(TestAssignment.test_design_id == test_design_id)
        .where(TestAssignment.status == TestAssignmentStatus.PENDING)
        .where(TestAssignment.scheduled_at.is_not(None))
        .where(TestAssignment.scheduled_at > server_time)
    )


def get_next_due_delayed_recall(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    _require_active_design(design)
    server_time = utc_now()
    pending_count = _pending_count(session, test_design_id)
    due_count = _due_count(session, test_design_id, server_time)
    if pending_count == 0:
        raise ConflictError("delayed_recall_integrity_conflict", "Active design has no pending assignments.")

    assignment = session.scalar(
        _assignment_details_query(test_design_id)
        .where(TestAssignment.status == TestAssignmentStatus.PENDING)
        .where(TestAssignment.scheduled_at.is_not(None))
        .where(TestAssignment.scheduled_at <= server_time)
        .order_by(TestAssignment.scheduled_at, TestAssignment.assignment_order, TestAssignment.id)
        .limit(1)
    )
    if assignment is None:
        return {
            "available": False,
            "server_time": server_time,
            "due_count": 0,
            "pending_count": pending_count,
            "assignment": None,
            "next_scheduled_at": _next_scheduled_at(session, test_design_id, server_time),
        }

    return {
        "available": True,
        "server_time": server_time,
        "due_count": due_count,
        "pending_count": pending_count,
        "assignment": {
            "assignment_id": assignment.id,
            "test_design_item_id": assignment.test_design_item_id,
            "vocabulary_item_id": assignment.test_design_item.vocabulary_item_id,
            "korean": assignment.test_design_item.vocabulary_item.korean,
            "group_index": assignment.test_design_group.group_index,
            "target_interval_seconds": assignment.test_design_group.interval_seconds,
            "scheduled_at": assignment.scheduled_at,
        },
        "next_scheduled_at": None,
    }


def submit_delayed_recall(
    session: Session,
    *,
    test_design_id: int,
    assignment_id: int,
    user_answer: str,
    response_time_ms: int | None,
) -> dict:
    if response_time_ms is not None and response_time_ms < 0:
        raise ValidationServiceError("negative_response_time_ms", "response_time_ms must not be negative.")

    try:
        with session.begin():
            design = _get_design(session, test_design_id)
            _require_active_design(design)
            assignment = session.scalar(_assignment_details_query(test_design_id).where(TestAssignment.id == assignment_id))
            if assignment is None:
                exists_for_another_design = session.scalar(select(TestAssignment.id).where(TestAssignment.id == assignment_id))
                if exists_for_another_design is not None:
                    raise ConflictError("assignment_wrong_design", "Assignment belongs to a different test design.")
                raise NotFoundError("assignment_not_found", "Assignment was not found.")
            if assignment.status == TestAssignmentStatus.COMPLETED:
                raise ConflictError("assignment_already_completed", "Assignment is already completed.")
            if assignment.status != TestAssignmentStatus.PENDING:
                raise ConflictError("assignment_not_pending", "Assignment is not pending.")
            if assignment.anchor_at is None:
                raise ConflictError("missing_anchor_at", "Assignment is missing anchor_at.")
            if assignment.scheduled_at is None:
                raise ConflictError("missing_scheduled_at", "Assignment is missing scheduled_at.")

            attempted_at = utc_now()
            if as_utc(assignment.scheduled_at) > attempted_at:
                raise ConflictError("assignment_not_yet_due", "Assignment is not yet due.")
            if as_utc(assignment.anchor_at) > attempted_at:
                raise ConflictError("timestamp_integrity_violation", "Attempt timestamp is before anchor_at.")
            existing_attempt_id = session.scalar(
                select(VocabularyAttempt.id).where(VocabularyAttempt.test_assignment_id == assignment.id)
            )
            if existing_attempt_id is not None:
                raise ConflictError("duplicate_delayed_recall_attempt", "Delayed recall attempt already exists.")

            actual_retention_seconds = elapsed_seconds(attempted_at, assignment.anchor_at)
            is_correct = check_answer(user_answer, assignment.test_design_item.vocabulary_item.english_answer)
            attempt = VocabularyAttempt(
                test_design_item_id=assignment.test_design_item_id,
                test_assignment_id=assignment.id,
                attempt_type=VocabularyAttemptType.DELAYED_RECALL,
                user_answer=user_answer,
                normalized_answer=normalize_answer(user_answer),
                is_correct=is_correct,
                response_time_ms=response_time_ms,
                attempted_at=attempted_at,
                actual_retention_seconds=actual_retention_seconds,
                is_valid_for_fitting=True,
                exclusion_reason=None,
            )
            session.add(attempt)
            assignment.status = TestAssignmentStatus.COMPLETED
            assignment.completed_at = attempted_at
            session.flush()

            group_status = _complete_group_if_ready(session, assignment.test_design_group, attempted_at)
            design_status = _complete_design_if_ready(session, design, attempted_at)
            response = _submission_response(session, assignment, attempt, group_status, design_status)
    except IntegrityError as exc:
        raise ConflictError("delayed_recall_integrity_conflict", "Delayed recall could not be submitted.") from exc

    return response


def _valid_delayed_attempt_count_for_assignment(session: Session, assignment_id: int) -> int:
    return session.scalar(
        select(func.count())
        .select_from(VocabularyAttempt)
        .where(VocabularyAttempt.test_assignment_id == assignment_id)
        .where(VocabularyAttempt.attempt_type == VocabularyAttemptType.DELAYED_RECALL)
        .where(VocabularyAttempt.is_valid_for_fitting.is_(True))
    ) or 0


def _complete_group_if_ready(session: Session, group: TestDesignGroup, completed_at: datetime) -> TestDesignGroupStatus:
    assignments = list(
        session.scalars(select(TestAssignment).where(TestAssignment.test_design_group_id == group.id))
    )
    completed_count = sum(1 for assignment in assignments if assignment.status == TestAssignmentStatus.COMPLETED)
    valid_count = sum(_valid_delayed_attempt_count_for_assignment(session, assignment.id) == 1 for assignment in assignments)
    if (
        len(assignments) == group.test_design.items_per_group
        and completed_count == len(assignments)
        and valid_count == len(assignments)
        and group.status != TestDesignGroupStatus.COMPLETED
    ):
        group.status = TestDesignGroupStatus.COMPLETED
        group.completed_at = completed_at
    return group.status


def _complete_design_if_ready(session: Session, design: TestDesign, completed_at: datetime) -> TestDesignStatus:
    groups = list(session.scalars(select(TestDesignGroup).where(TestDesignGroup.test_design_id == design.id)))
    assignments = list(session.scalars(select(TestAssignment).where(TestAssignment.test_design_id == design.id)))
    every_group_completed = all(group.status == TestDesignGroupStatus.COMPLETED for group in groups)
    every_assignment_completed = all(assignment.status == TestAssignmentStatus.COMPLETED for assignment in assignments)
    every_assignment_has_valid_attempt = all(
        _valid_delayed_attempt_count_for_assignment(session, assignment.id) == 1 for assignment in assignments
    )
    if every_group_completed and every_assignment_completed and every_assignment_has_valid_attempt:
        design.status = TestDesignStatus.COMPLETED
        design.completed_at = completed_at
    return design.status


def _submission_response(
    session: Session,
    assignment: TestAssignment,
    attempt: VocabularyAttempt,
    group_status: TestDesignGroupStatus,
    design_status: TestDesignStatus,
) -> dict:
    group_assignment_count = session.scalar(
        select(func.count()).select_from(TestAssignment).where(TestAssignment.test_design_group_id == assignment.test_design_group_id)
    ) or 0
    group_completed_count = session.scalar(
        select(func.count())
        .select_from(TestAssignment)
        .where(TestAssignment.test_design_group_id == assignment.test_design_group_id)
        .where(TestAssignment.status == TestAssignmentStatus.COMPLETED)
    ) or 0
    overall_assignment_count = session.scalar(
        select(func.count()).select_from(TestAssignment).where(TestAssignment.test_design_id == assignment.test_design_id)
    ) or 0
    overall_completed_count = session.scalar(
        select(func.count())
        .select_from(TestAssignment)
        .where(TestAssignment.test_design_id == assignment.test_design_id)
        .where(TestAssignment.status == TestAssignmentStatus.COMPLETED)
    ) or 0
    return {
        "attempt_id": attempt.id,
        "assignment_id": assignment.id,
        "attempted_at": attempt.attempted_at,
        "actual_retention_seconds": attempt.actual_retention_seconds,
        "target_interval_seconds": assignment.test_design_group.interval_seconds,
        "lateness_seconds": max(0, elapsed_seconds(attempt.attempted_at, assignment.scheduled_at)),
        "assignment_status": assignment.status.value,
        "group_index": assignment.test_design_group.group_index,
        "group_completed_count": group_completed_count,
        "group_assignment_count": group_assignment_count,
        "group_status": group_status.value,
        "overall_completed_count": overall_completed_count,
        "overall_assignment_count": overall_assignment_count,
        "design_status": design_status.value,
    }


def get_delayed_recall_progress(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    if design.status not in {TestDesignStatus.ACTIVE, TestDesignStatus.COMPLETED}:
        raise ConflictError("design_not_active_or_completed", "Delayed recall progress is available only for active or completed designs.")
    server_time = utc_now()
    total_assignment_count = session.scalar(select(func.count()).select_from(TestAssignment).where(TestAssignment.test_design_id == test_design_id)) or 0
    completed_assignment_count = session.scalar(
        select(func.count())
        .select_from(TestAssignment)
        .where(TestAssignment.test_design_id == test_design_id)
        .where(TestAssignment.status == TestAssignmentStatus.COMPLETED)
    ) or 0
    pending_assignment_count = session.scalar(
        select(func.count())
        .select_from(TestAssignment)
        .where(TestAssignment.test_design_id == test_design_id)
        .where(TestAssignment.status == TestAssignmentStatus.PENDING)
    ) or 0
    completed_group_count = session.scalar(
        select(func.count())
        .select_from(TestDesignGroup)
        .where(TestDesignGroup.test_design_id == test_design_id)
        .where(TestDesignGroup.status == TestDesignGroupStatus.COMPLETED)
    ) or 0
    total_group_count = session.scalar(select(func.count()).select_from(TestDesignGroup).where(TestDesignGroup.test_design_id == test_design_id)) or 0
    return {
        "test_design_id": test_design_id,
        "status": design.status.value,
        "total_assignment_count": total_assignment_count,
        "completed_assignment_count": completed_assignment_count,
        "pending_assignment_count": pending_assignment_count,
        "due_assignment_count": _due_count(session, test_design_id, server_time),
        "completed_group_count": completed_group_count,
        "total_group_count": total_group_count,
        "next_scheduled_at": _next_scheduled_at(session, test_design_id, server_time),
        "activated_at": design.activated_at,
        "completed_at": design.completed_at,
    }

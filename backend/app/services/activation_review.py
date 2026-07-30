from datetime import timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.database import utc_now
from app.db.enums import TestAssignmentStatus, TestDesignStatus
from app.db.models import TestAssignment, TestDesign, TestDesignItem
from app.services.exceptions import ConflictError, NotFoundError


def _get_design(session: Session, test_design_id: int) -> TestDesign:
    design = session.get(TestDesign, test_design_id)
    if design is None:
        raise NotFoundError("test_design_not_found", "Test design was not found.")
    return design


def _require_activation_review(design: TestDesign) -> None:
    if design.status != TestDesignStatus.ACTIVATION_REVIEW:
        raise ConflictError(
            "design_not_activation_review",
            "Test design must be in activation_review status.",
        )


def _assignment_with_details_statement(test_design_id: int, assignment_id: int | None = None) -> Select:
    statement = (
        select(TestAssignment)
        .where(TestAssignment.test_design_id == test_design_id)
        .options(
            selectinload(TestAssignment.test_design_item).selectinload(TestDesignItem.vocabulary_item),
            selectinload(TestAssignment.test_design_group),
        )
    )
    if assignment_id is not None:
        statement = statement.where(TestAssignment.id == assignment_id)
    return statement


def _activation_counts(session: Session, test_design_id: int) -> tuple[int, int, int]:
    total = session.scalar(select(func.count()).select_from(TestAssignment).where(TestAssignment.test_design_id == test_design_id)) or 0
    remaining = (
        session.scalar(
            select(func.count())
            .select_from(TestAssignment)
            .where(TestAssignment.test_design_id == test_design_id)
            .where(TestAssignment.status == TestAssignmentStatus.AWAITING_ANCHOR)
        )
        or 0
    )
    anchored = total - remaining
    return total, anchored, remaining


def get_activation_review_next(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    _require_activation_review(design)

    assignment = session.scalar(
        _assignment_with_details_statement(test_design_id)
        .where(TestAssignment.status == TestAssignmentStatus.AWAITING_ANCHOR)
        .order_by(TestAssignment.assignment_order)
        .limit(1)
    )
    if assignment is None:
        raise ConflictError("no_activation_review_assignment", "No activation-review assignment is available.")

    total, anchored, remaining = _activation_counts(session, test_design_id)
    return {
        "assignment_id": assignment.id,
        "assignment_order": assignment.assignment_order,
        "total_assignment_count": total,
        "completed_activation_count": anchored,
        "remaining_activation_count": remaining,
        "vocabulary_item_id": assignment.test_design_item.vocabulary_item_id,
        "korean": assignment.test_design_item.vocabulary_item.korean,
        "english_answer": assignment.test_design_item.vocabulary_item.english_answer,
        "group_index": assignment.test_design_group.group_index,
        "interval_seconds": assignment.test_design_group.interval_seconds,
    }


def complete_activation_review_assignment(
    session: Session,
    *,
    test_design_id: int,
    assignment_id: int,
) -> dict:
    try:
        with session.begin():
            design = _get_design(session, test_design_id)
            _require_activation_review(design)

            assignment = session.scalar(_assignment_with_details_statement(test_design_id, assignment_id))
            if assignment is None:
                exists_for_another_design = session.scalar(
                    select(TestAssignment.id).where(TestAssignment.id == assignment_id)
                )
                if exists_for_another_design is not None:
                    raise ConflictError(
                        "assignment_wrong_design",
                        "Assignment belongs to a different test design.",
                    )
                raise NotFoundError("assignment_not_found", "Assignment was not found.")

            if assignment.status != TestAssignmentStatus.AWAITING_ANCHOR:
                raise ConflictError("assignment_already_anchored", "Assignment is already anchored.")

            next_assignment_id = session.scalar(
                select(TestAssignment.id)
                .where(TestAssignment.test_design_id == test_design_id)
                .where(TestAssignment.status == TestAssignmentStatus.AWAITING_ANCHOR)
                .order_by(TestAssignment.assignment_order)
                .limit(1)
            )
            if next_assignment_id != assignment.id:
                raise ConflictError(
                    "activation_out_of_order",
                    "Activation review assignments must be completed in assignment order.",
                )

            interval_seconds = assignment.test_design_group.interval_seconds
            if interval_seconds is None or interval_seconds <= 0:
                raise ConflictError("missing_group_interval", "Assignment group interval is missing.")

            anchor_at = utc_now()
            scheduled_at = anchor_at + timedelta(seconds=interval_seconds)
            assignment.status = TestAssignmentStatus.PENDING
            assignment.anchor_at = anchor_at
            assignment.scheduled_at = scheduled_at
            assignment.completed_at = None
            session.flush()

            total, anchored, remaining = _activation_counts(session, test_design_id)
            activated_at = None
            if remaining == 0:
                _verify_all_assignments_pending(session, test_design_id)
                activated_at = utc_now()
                design.status = TestDesignStatus.ACTIVE
                design.activated_at = activated_at

            response = {
                "assignment_id": assignment.id,
                "anchor_at": assignment.anchor_at,
                "scheduled_at": assignment.scheduled_at,
                "interval_seconds": interval_seconds,
                "remaining_activation_count": remaining,
                "design_status": design.status.value,
                "activated_at": activated_at,
            }
    except IntegrityError as exc:
        raise ConflictError("activation_integrity_conflict", "Activation review item could not be completed.") from exc

    return response


def _verify_all_assignments_pending(session: Session, test_design_id: int) -> None:
    invalid_count = (
        session.scalar(
            select(func.count())
            .select_from(TestAssignment)
            .where(TestAssignment.test_design_id == test_design_id)
            .where(
                (TestAssignment.status != TestAssignmentStatus.PENDING)
                | (TestAssignment.anchor_at.is_(None))
                | (TestAssignment.scheduled_at.is_(None))
            )
        )
        or 0
    )
    if invalid_count:
        raise ConflictError(
            "activation_integrity_conflict",
            "All assignments must be pending with anchor and schedule timestamps.",
        )


def get_activation_progress(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    if design.status not in {TestDesignStatus.ACTIVATION_REVIEW, TestDesignStatus.ACTIVE}:
        raise ConflictError(
            "design_not_activation_review_or_active",
            "Activation progress is available only during activation review or active status.",
        )

    total, anchored, remaining = _activation_counts(session, test_design_id)
    return {
        "test_design_id": design.id,
        "status": design.status.value,
        "total_assignment_count": total,
        "anchored_assignment_count": anchored,
        "remaining_activation_count": remaining,
        "activation_review_started_at": design.activation_review_started_at,
        "activated_at": design.activated_at,
    }

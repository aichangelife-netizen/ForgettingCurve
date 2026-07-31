from collections import Counter
import random

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.database import utc_now
from app.db.enums import TestAssignmentStatus, TestDesignGroupStatus, TestDesignStatus
from app.db.models import TestAssignment, TestDesign, TestDesignGroup, TestDesignItem
from app.services.exceptions import ConflictError, NotFoundError
from app.services.learning import derive_deterministic_seed
from app.services.test_designs import required_item_count
from app.services.time import as_utc


GROUP_ASSIGNMENT_NAMESPACE = "group_assignment"


def _get_design(session: Session, test_design_id: int) -> TestDesign:
    design = session.get(TestDesign, test_design_id)
    if design is None:
        raise NotFoundError("test_design_not_found", "Test design was not found.")
    return design


def _assignment_count(session: Session, test_design_id: int) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(TestAssignment)
            .where(TestAssignment.test_design_id == test_design_id)
        )
        or 0
    )


def _design_items_statement(test_design_id: int) -> Select:
    return (
        select(TestDesignItem)
        .where(TestDesignItem.test_design_id == test_design_id)
        .order_by(TestDesignItem.id)
    )


def _design_groups_statement(test_design_id: int) -> Select:
    return (
        select(TestDesignGroup)
        .where(TestDesignGroup.test_design_id == test_design_id)
        .order_by(TestDesignGroup.group_index)
    )


def select_group_assignment_item_ids(
    test_design_item_ids: list[int],
    *,
    random_seed: int,
) -> list[int]:
    sorted_ids = sorted(test_design_item_ids)
    rng = random.Random(derive_deterministic_seed(random_seed, GROUP_ASSIGNMENT_NAMESPACE))
    shuffled_ids = list(sorted_ids)
    rng.shuffle(shuffled_ids)
    return shuffled_ids


def _validate_assignment_initialization(
    session: Session,
    design: TestDesign,
    items: list[TestDesignItem],
    groups: list[TestDesignGroup],
) -> int:
    needed_items = required_item_count(design.items_per_group, design.group_count)
    if len(items) != needed_items:
        raise ConflictError(
            "design_item_count_mismatch",
            "Test design item count does not match the required item count.",
        )
    if any(not item.is_mastered or item.mastered_at is None for item in items):
        raise ConflictError(
            "unmastered_design_items",
            "All test design items must be mastered before assignment initialization.",
        )
    if len(groups) != design.group_count:
        raise ConflictError("group_count_mismatch", "Test design group count does not match group_count.")
    if len({group.interval_seconds for group in groups}) != len(groups) or any(
        group.interval_seconds <= 0 for group in groups
    ):
        raise ConflictError("missing_group_interval", "Every group must have a unique positive interval.")
    if any(group.status != TestDesignGroupStatus.PENDING for group in groups):
        raise ConflictError("invalid_group_status", "Every group must be pending before assignment initialization.")
    if _assignment_count(session, design.id) > 0:
        raise ConflictError(
            "assignments_already_initialized",
            "Assignments are already initialized for this test design.",
        )
    return needed_items


def _group_assignment_counts(assignments: list[TestAssignment], groups: list[TestDesignGroup]) -> dict[int, int]:
    counts = Counter(assignment.test_design_group_id for assignment in assignments)
    return {group.id: counts[group.id] for group in groups}


def initialize_assignments(session: Session, test_design_id: int) -> dict:
    try:
        with session.begin():
            design = _get_design(session, test_design_id)
            if design.status != TestDesignStatus.ASSIGNING:
                raise ConflictError(
                    "design_not_assigning",
                    "Test design must be in assigning status before assignment initialization.",
                )

            items = list(session.scalars(_design_items_statement(test_design_id)))
            groups = list(session.scalars(_design_groups_statement(test_design_id)))
            needed_items = _validate_assignment_initialization(session, design, items, groups)
            shuffled_item_ids = select_group_assignment_item_ids(
                [item.id for item in items],
                random_seed=design.random_seed,
            )

            timestamp = utc_now()
            assignments: list[TestAssignment] = []
            for zero_based_position, test_design_item_id in enumerate(shuffled_item_ids):
                group = groups[zero_based_position % design.group_count]
                assignment = TestAssignment(
                    test_design_id=design.id,
                    test_design_item_id=test_design_item_id,
                    test_design_group_id=group.id,
                    assignment_order=zero_based_position + 1,
                    anchor_at=None,
                    scheduled_at=None,
                    status=TestAssignmentStatus.AWAITING_ANCHOR,
                    created_at=timestamp,
                    completed_at=None,
                )
                session.add(assignment)
                assignments.append(assignment)

            _validate_balanced_assignments(assignments, groups, design.items_per_group, needed_items)
            design.status = TestDesignStatus.ACTIVATION_REVIEW
            design.activation_review_started_at = timestamp
            session.flush()

            group_counts = _group_assignment_counts(assignments, groups)
            response = {
                "test_design_id": design.id,
                "status": design.status.value,
                "assignment_count": len(assignments),
                "group_count": design.group_count,
                "items_per_group": design.items_per_group,
                "random_seed": design.random_seed,
                "groups": [
                    {
                        "test_design_group_id": group.id,
                        "group_index": group.group_index,
                        "interval_seconds": group.interval_seconds,
                        "assignment_count": group_counts[group.id],
                    }
                    for group in groups
                ],
                "activation_review_started_at": as_utc(design.activation_review_started_at),
            }
    except IntegrityError as exc:
        raise ConflictError("assignment_integrity_conflict", "Assignments could not be initialized.") from exc

    return response


def _validate_balanced_assignments(
    assignments: list[TestAssignment],
    groups: list[TestDesignGroup],
    items_per_group: int,
    required_count: int,
) -> None:
    if len(assignments) != required_count:
        raise ConflictError("invalid_group_distribution", "Assignment count does not match required item count.")

    item_ids = [assignment.test_design_item_id for assignment in assignments]
    if len(item_ids) != len(set(item_ids)):
        raise ConflictError("invalid_group_distribution", "A design item was assigned more than once.")

    assignment_orders = [assignment.assignment_order for assignment in assignments]
    if sorted(assignment_orders) != list(range(1, required_count + 1)):
        raise ConflictError("invalid_group_distribution", "Assignment order does not cover the required range.")

    counts = _group_assignment_counts(assignments, groups)
    if any(count != items_per_group for count in counts.values()):
        raise ConflictError("invalid_group_distribution", "Assignments are not balanced across groups.")


def _schedule_groups_statement(test_design_id: int) -> Select:
    return (
        select(TestDesignGroup)
        .where(TestDesignGroup.test_design_id == test_design_id)
        .options(selectinload(TestDesignGroup.assignments))
        .order_by(TestDesignGroup.group_index)
    )


def get_assignment_schedule(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    if design.status not in {TestDesignStatus.ACTIVATION_REVIEW, TestDesignStatus.ACTIVE}:
        raise ConflictError(
            "design_not_activation_review_or_active",
            "Assignment schedule is available only during activation review or active status.",
        )

    groups = list(session.scalars(_schedule_groups_statement(test_design_id)))
    return {
        "test_design_id": design.id,
        "status": design.status.value,
        "groups": [_group_schedule_summary(group) for group in groups],
    }


def _group_schedule_summary(group: TestDesignGroup) -> dict:
    assignments = list(group.assignments)
    scheduled_times = [assignment.scheduled_at for assignment in assignments if assignment.scheduled_at is not None]
    return {
        "test_design_group_id": group.id,
        "group_index": group.group_index,
        "interval_seconds": group.interval_seconds,
        "assignment_count": len(assignments),
        "awaiting_anchor_count": sum(
            1 for assignment in assignments if assignment.status == TestAssignmentStatus.AWAITING_ANCHOR
        ),
        "pending_count": sum(1 for assignment in assignments if assignment.status == TestAssignmentStatus.PENDING),
        "completed_count": sum(1 for assignment in assignments if assignment.status == TestAssignmentStatus.COMPLETED),
        "earliest_scheduled_at": as_utc(min(scheduled_times)) if scheduled_times else None,
        "latest_scheduled_at": as_utc(max(scheduled_times)) if scheduled_times else None,
    }

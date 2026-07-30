import random

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.database import utc_now
from app.db.enums import (
    NON_TERMINAL_TEST_DESIGN_STATUSES,
    TestDesignGroupStatus,
    TestDesignStatus,
)
from app.db.models import Participant, TestDesign, TestDesignGroup, VocabularyItem
from app.services.exceptions import ConflictError, NotFoundError, ValidationServiceError


RANDOM_SEED_MIN = 0
RANDOM_SEED_MAX = 2**31 - 1


def required_item_count(items_per_group: int, group_count: int) -> int:
    return items_per_group * group_count


def _active_vocabulary_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(VocabularyItem).where(VocabularyItem.is_active.is_(True))) or 0


def _get_design_with_groups(session: Session, test_design_id: int) -> TestDesign:
    design = session.scalar(
        select(TestDesign)
        .where(TestDesign.id == test_design_id)
        .options(selectinload(TestDesign.groups))
    )
    if design is None:
        raise NotFoundError("test_design_not_found", "Test design was not found.")
    design.groups.sort(key=lambda group: group.group_index)
    return design


def _validate_intervals(intervals_seconds: list[int]) -> None:
    if not intervals_seconds:
        raise ValidationServiceError("empty_intervals", "At least one retention interval is required.")
    if any(not isinstance(interval, int) or interval <= 0 for interval in intervals_seconds):
        raise ValidationServiceError("invalid_interval", "Every retention interval must be an integer greater than zero.")
    if len(set(intervals_seconds)) != len(intervals_seconds):
        raise ValidationServiceError("duplicate_intervals", "Retention intervals must not contain duplicates.")


def create_test_design(
    session: Session,
    *,
    participant_id: int,
    items_per_group: int,
    intervals_seconds: list[int],
    random_seed: int | None,
) -> TestDesign:
    if items_per_group <= 0:
        raise ValidationServiceError("invalid_items_per_group", "items_per_group must be greater than zero.")
    _validate_intervals(intervals_seconds)

    group_count = len(intervals_seconds)
    needed_items = required_item_count(items_per_group, group_count)
    stored_seed = random_seed if random_seed is not None else random.SystemRandom().randint(RANDOM_SEED_MIN, RANDOM_SEED_MAX)

    try:
        with session.begin():
            participant = session.get(Participant, participant_id)
            if participant is None:
                raise NotFoundError("participant_not_found", "Participant was not found.")

            active_count = _active_vocabulary_count(session)
            if active_count < needed_items:
                raise ConflictError(
                    "insufficient_active_vocabulary",
                    "There are not enough active vocabulary items for this test design.",
                )

            existing_design_id = session.scalar(
                select(TestDesign.id)
                .where(TestDesign.participant_id == participant_id)
                .where(TestDesign.status.in_(NON_TERMINAL_TEST_DESIGN_STATUSES))
            )
            if existing_design_id is not None:
                raise ConflictError(
                    "unfinished_design_exists",
                    "Participant already has an unfinished test design.",
                )

            design = TestDesign(
                participant_id=participant_id,
                items_per_group=items_per_group,
                group_count=group_count,
                random_seed=stored_seed,
                status=TestDesignStatus.DRAFT,
                created_at=utc_now(),
            )
            session.add(design)
            session.flush()

            for group_index, interval_seconds in enumerate(intervals_seconds, start=1):
                session.add(
                    TestDesignGroup(
                        test_design_id=design.id,
                        group_index=group_index,
                        interval_seconds=interval_seconds,
                        status=TestDesignGroupStatus.PENDING,
                    )
                )
    except IntegrityError as exc:
        raise ConflictError("test_design_conflict", "Test design could not be created because of a data conflict.") from exc

    return _get_design_with_groups(session, design.id)


def get_test_design(session: Session, test_design_id: int) -> TestDesign:
    return _get_design_with_groups(session, test_design_id)


def get_current_test_design(session: Session, participant_id: int) -> TestDesign:
    participant = session.get(Participant, participant_id)
    if participant is None:
        raise NotFoundError("participant_not_found", "Participant was not found.")

    design = session.scalar(
        select(TestDesign)
        .where(TestDesign.participant_id == participant_id)
        .where(TestDesign.status.in_(NON_TERMINAL_TEST_DESIGN_STATUSES))
        .options(selectinload(TestDesign.groups))
    )
    if design is None:
        raise NotFoundError("current_test_design_not_found", "Participant has no current test design.")
    design.groups.sort(key=lambda group: group.group_index)
    return design


def to_test_design_response_data(design: TestDesign) -> dict:
    ordered_groups = sorted(design.groups, key=lambda group: group.group_index)
    return {
        "id": design.id,
        "participant_id": design.participant_id,
        "items_per_group": design.items_per_group,
        "group_count": design.group_count,
        "required_item_count": required_item_count(design.items_per_group, design.group_count),
        "random_seed": design.random_seed,
        "status": design.status.value,
        "groups": [
            {
                "id": group.id,
                "group_index": group.group_index,
                "interval_seconds": group.interval_seconds,
                "status": group.status.value,
                "completed_at": group.completed_at,
            }
            for group in ordered_groups
        ],
        "created_at": design.created_at,
        "learning_started_at": design.learning_started_at,
        "activation_review_started_at": design.activation_review_started_at,
        "activated_at": design.activated_at,
        "completed_at": design.completed_at,
    }

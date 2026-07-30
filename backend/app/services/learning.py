import hashlib
import random

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.constants import MASTERY_THRESHOLD
from app.db.database import utc_now
from app.db.enums import TestDesignStatus, VocabularyAttemptType
from app.db.models import TestDesign, TestDesignItem, VocabularyAttempt, VocabularyItem
from app.services.answer_scoring import check_answer, normalize_answer
from app.services.exceptions import ConflictError, NotFoundError, ValidationServiceError
from app.services.test_designs import required_item_count


LEARNING_POOL_NAMESPACE = "learning_pool"


def derive_deterministic_seed(random_seed: int, namespace: str) -> int:
    digest = hashlib.sha256(f"{random_seed}:{namespace}".encode("utf-8")).digest()
    return int.from_bytes(digest, byteorder="big")


def select_learning_pool_vocabulary_ids(
    vocabulary_ids: list[int],
    *,
    random_seed: int,
    required_count: int,
) -> list[int]:
    sorted_ids = sorted(vocabulary_ids)
    rng = random.Random(derive_deterministic_seed(random_seed, LEARNING_POOL_NAMESPACE))
    shuffled_ids = list(sorted_ids)
    rng.shuffle(shuffled_ids)
    return shuffled_ids[:required_count]


def _get_design(session: Session, test_design_id: int) -> TestDesign:
    design = session.get(TestDesign, test_design_id)
    if design is None:
        raise NotFoundError("test_design_not_found", "Test design was not found.")
    return design


def _require_learning_design(design: TestDesign, *, action: str) -> None:
    if design.status != TestDesignStatus.LEARNING:
        raise ConflictError(f"design_not_learning_for_{action}", "Test design is not in learning status.")


def _pool_count(session: Session, test_design_id: int) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(TestDesignItem)
            .where(TestDesignItem.test_design_id == test_design_id)
        )
        or 0
    )


def _mastered_count(session: Session, test_design_id: int) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(TestDesignItem)
            .where(TestDesignItem.test_design_id == test_design_id)
            .where(TestDesignItem.is_mastered.is_(True))
        )
        or 0
    )


def _active_vocabulary_ids(session: Session) -> list[int]:
    return list(
        session.scalars(
            select(VocabularyItem.id).where(VocabularyItem.is_active.is_(True)).order_by(VocabularyItem.id)
        )
    )


def initialize_learning(session: Session, test_design_id: int) -> TestDesign:
    try:
        with session.begin():
            design = _get_design(session, test_design_id)
            if design.status != TestDesignStatus.DRAFT:
                raise ConflictError(
                    "invalid_design_status_transition",
                    "Only draft test designs can start learning.",
                )

            if _pool_count(session, test_design_id) > 0:
                raise ConflictError(
                    "learning_pool_already_initialized",
                    "Learning pool is already initialized for this test design.",
                )

            needed_items = required_item_count(design.items_per_group, design.group_count)
            active_ids = _active_vocabulary_ids(session)
            if len(active_ids) < needed_items:
                raise ConflictError(
                    "insufficient_active_vocabulary",
                    "There are not enough active vocabulary items for this test design.",
                )

            selected_ids = select_learning_pool_vocabulary_ids(
                active_ids,
                random_seed=design.random_seed,
                required_count=needed_items,
            )
            timestamp = utc_now()
            for vocabulary_item_id in selected_ids:
                session.add(
                    TestDesignItem(
                        test_design_id=design.id,
                        vocabulary_item_id=vocabulary_item_id,
                        attempt_count=0,
                        correct_count=0,
                        consecutive_correct_count=0,
                        is_mastered=False,
                        mastered_at=None,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )

            design.status = TestDesignStatus.LEARNING
            design.learning_started_at = timestamp
    except IntegrityError as exc:
        raise ConflictError("learning_initialization_conflict", "Learning could not be initialized.") from exc

    return session.scalar(
        select(TestDesign).where(TestDesign.id == test_design_id).options(selectinload(TestDesign.groups))
    )


def _learning_items_statement(test_design_id: int) -> Select:
    return (
        select(TestDesignItem)
        .where(TestDesignItem.test_design_id == test_design_id)
        .options(selectinload(TestDesignItem.vocabulary_item))
        .order_by(TestDesignItem.id)
    )


def get_learning_materials(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    _require_learning_design(design, action="materials")
    items = list(session.scalars(_learning_items_statement(test_design_id)))
    mastered_count = sum(1 for item in items if item.is_mastered)
    needed_items = required_item_count(design.items_per_group, design.group_count)
    return {
        "test_design_id": test_design_id,
        "required_item_count": needed_items,
        "mastered_item_count": mastered_count,
        "remaining_item_count": needed_items - mastered_count,
        "items": [
            {
                "test_design_item_id": item.id,
                "vocabulary_item_id": item.vocabulary_item_id,
                "korean": item.vocabulary_item.korean,
                "english_answer": item.vocabulary_item.english_answer,
                "is_mastered": item.is_mastered,
            }
            for item in items
        ],
    }


def get_next_learning_check(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    _require_learning_design(design, action="next_check")
    item = session.scalar(
        select(TestDesignItem)
        .where(TestDesignItem.test_design_id == test_design_id)
        .where(TestDesignItem.is_mastered.is_(False))
        .options(selectinload(TestDesignItem.vocabulary_item))
        .order_by(TestDesignItem.attempt_count > 0, TestDesignItem.updated_at, TestDesignItem.id)
        .limit(1)
    )
    if item is None:
        raise ConflictError("no_unmastered_learning_item", "No unmastered learning item is available.")
    return {
        "test_design_item_id": item.id,
        "vocabulary_item_id": item.vocabulary_item_id,
        "korean": item.vocabulary_item.korean,
        "attempt_count": item.attempt_count,
        "consecutive_correct_count": item.consecutive_correct_count,
    }


def submit_learning_attempt(
    session: Session,
    *,
    test_design_id: int,
    test_design_item_id: int,
    user_answer: str,
    response_time_ms: int | None,
) -> dict:
    if response_time_ms is not None and response_time_ms < 0:
        raise ValidationServiceError("negative_response_time_ms", "response_time_ms must not be negative.")

    try:
        with session.begin():
            design = _get_design(session, test_design_id)
            _require_learning_design(design, action="attempt")

            item = session.scalar(
                select(TestDesignItem)
                .where(TestDesignItem.id == test_design_item_id)
                .options(selectinload(TestDesignItem.vocabulary_item))
            )
            if item is None:
                raise NotFoundError("test_design_item_not_found", "Test design item was not found.")
            if item.test_design_id != test_design_id:
                raise ConflictError(
                    "test_design_item_wrong_design",
                    "Test design item belongs to a different test design.",
                )
            if item.is_mastered:
                raise ConflictError("item_already_mastered", "Learning item is already mastered.")

            timestamp = utc_now()
            is_correct = check_answer(user_answer, item.vocabulary_item.english_answer)
            attempt = VocabularyAttempt(
                test_design_item_id=item.id,
                test_assignment_id=None,
                attempt_type=VocabularyAttemptType.LEARNING_CHECK,
                user_answer=user_answer,
                normalized_answer=normalize_answer(user_answer),
                is_correct=is_correct,
                response_time_ms=response_time_ms,
                attempted_at=timestamp,
                actual_retention_seconds=None,
                is_valid_for_fitting=False,
                exclusion_reason=None,
            )
            session.add(attempt)

            item.attempt_count += 1
            if is_correct:
                item.correct_count += 1
                item.consecutive_correct_count += 1
            else:
                item.consecutive_correct_count = 0

            if item.consecutive_correct_count >= MASTERY_THRESHOLD and not item.is_mastered:
                item.is_mastered = True
                item.mastered_at = timestamp
            item.updated_at = timestamp
            session.flush()

            needed_items = required_item_count(design.items_per_group, design.group_count)
            mastered_count = _mastered_count(session, test_design_id)
            if mastered_count == needed_items:
                design.status = TestDesignStatus.ASSIGNING
            elif mastered_count > needed_items:
                raise ConflictError("learning_mastery_count_invalid", "Mastered item count exceeds the required item count.")

            response = {
                "attempt_id": attempt.id,
                "test_design_item_id": item.id,
                "is_correct": is_correct,
                "canonical_answer": item.vocabulary_item.english_answer,
                "attempt_count": item.attempt_count,
                "correct_count": item.correct_count,
                "consecutive_correct_count": item.consecutive_correct_count,
                "is_mastered": item.is_mastered,
                "mastered_at": item.mastered_at,
                "mastered_item_count": mastered_count,
                "required_item_count": needed_items,
                "remaining_item_count": needed_items - mastered_count,
                "design_status": design.status.value,
            }
    except IntegrityError as exc:
        raise ConflictError("learning_attempt_conflict", "Learning attempt could not be saved.") from exc

    return response


def get_learning_progress(session: Session, test_design_id: int) -> dict:
    design = _get_design(session, test_design_id)
    if design.status not in {TestDesignStatus.LEARNING, TestDesignStatus.ASSIGNING}:
        raise ConflictError(
            "design_not_learning_or_assigning",
            "Learning progress is available only for learning or assigning test designs.",
        )

    aggregates = session.execute(
        select(
            func.count(TestDesignItem.id),
            func.coalesce(func.sum(TestDesignItem.attempt_count), 0),
            func.coalesce(func.sum(TestDesignItem.correct_count), 0),
            func.coalesce(func.sum(TestDesignItem.is_mastered), 0),
        ).where(TestDesignItem.test_design_id == test_design_id)
    ).one()
    pool_item_count = int(aggregates[0])
    total_attempt_count = int(aggregates[1])
    correct_attempt_count = int(aggregates[2])
    mastered_item_count = int(aggregates[3])
    needed_items = required_item_count(design.items_per_group, design.group_count)
    return {
        "test_design_id": test_design_id,
        "status": design.status.value,
        "required_item_count": needed_items,
        "pool_item_count": pool_item_count,
        "mastered_item_count": mastered_item_count,
        "remaining_item_count": needed_items - mastered_item_count,
        "total_attempt_count": total_attempt_count,
        "correct_attempt_count": correct_attempt_count,
        "learning_started_at": design.learning_started_at,
    }

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.db.enums import (
    CurveFitMethod,
    CurveModelName,
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


def expect_integrity_error(statement, connection) -> None:
    with pytest.raises(IntegrityError):
        connection.execute(statement)


def now() -> datetime:
    return datetime.now(UTC)


def insert_participant(connection, code: str = "P001") -> int:
    return connection.execute(
        sa.insert(Participant).values(participant_code=code, created_at=now())
    ).inserted_primary_key[0]


def insert_vocabulary_item(connection, korean: str = "안녕", english_answer: str = "hello") -> int:
    return connection.execute(
        sa.insert(VocabularyItem).values(
            korean=korean,
            english_answer=english_answer,
            is_active=True,
            created_at=now(),
        )
    ).inserted_primary_key[0]


def insert_design(
    connection,
    participant_id: int,
    *,
    status: DesignStatus = DesignStatus.COMPLETED,
    random_seed: int = 123,
    items_per_group: int = 2,
    group_count: int = 2,
) -> int:
    return connection.execute(
        sa.insert(Design).values(
            participant_id=participant_id,
            items_per_group=items_per_group,
            group_count=group_count,
            random_seed=random_seed,
            status=status.value,
            created_at=now(),
        )
    ).inserted_primary_key[0]


def insert_group(
    connection,
    test_design_id: int,
    *,
    group_index: int = 1,
    interval_seconds: int = 60,
) -> int:
    return connection.execute(
        sa.insert(DesignGroup).values(
            test_design_id=test_design_id,
            group_index=group_index,
            interval_seconds=interval_seconds,
            status=GroupStatus.PENDING.value,
        )
    ).inserted_primary_key[0]


def insert_design_item(
    connection,
    test_design_id: int,
    vocabulary_item_id: int,
    *,
    mastered: bool = False,
) -> int:
    values = {
        "test_design_id": test_design_id,
        "vocabulary_item_id": vocabulary_item_id,
        "attempt_count": 0,
        "correct_count": 0,
        "consecutive_correct_count": 0,
        "is_mastered": False,
        "mastered_at": None,
        "created_at": now(),
        "updated_at": now(),
    }
    if mastered:
        values.update(
            attempt_count=2,
            correct_count=2,
            consecutive_correct_count=2,
            is_mastered=True,
            mastered_at=now(),
        )
    return connection.execute(sa.insert(DesignItem).values(**values)).inserted_primary_key[0]


def insert_assignment(
    connection,
    test_design_id: int,
    test_design_item_id: int,
    test_design_group_id: int,
    *,
    assignment_order: int = 1,
    status: AssignmentStatus = AssignmentStatus.AWAITING_ANCHOR,
) -> int:
    anchor_at = None
    scheduled_at = None
    completed_at = None
    if status in {AssignmentStatus.PENDING, AssignmentStatus.COMPLETED}:
        anchor_at = now()
        scheduled_at = anchor_at + timedelta(seconds=60)
    if status is AssignmentStatus.COMPLETED:
        completed_at = scheduled_at + timedelta(seconds=5)

    return connection.execute(
        sa.insert(Assignment).values(
            test_design_id=test_design_id,
            test_design_item_id=test_design_item_id,
            test_design_group_id=test_design_group_id,
            assignment_order=assignment_order,
            anchor_at=anchor_at,
            scheduled_at=scheduled_at,
            status=status.value,
            created_at=now(),
            completed_at=completed_at,
        )
    ).inserted_primary_key[0]


def insert_curve_model(
    connection,
    participant_id: int,
    trigger_test_design_id: int,
    *,
    version: int = 1,
    T: float = 3600.0,
    c: float = 0.8,
) -> int:
    return connection.execute(
        sa.insert(CurveModel).values(
            participant_id=participant_id,
            trigger_test_design_id=trigger_test_design_id,
            version=version,
            model_name=CurveModelName.EXPONENTIAL_POWER.value,
            fit_method=CurveFitMethod.BERNOULLI_MLE.value,
            T=T,
            c=c,
            sample_count=10,
            complete_time_point_count=5,
            converged=True,
            data_cutoff_at=now(),
            fitted_at=now(),
        )
    ).inserted_primary_key[0]


def design_with_item_group(connection):
    participant_id = insert_participant(connection)
    design_id = insert_design(connection, participant_id)
    vocabulary_item_id = insert_vocabulary_item(connection)
    design_item_id = insert_design_item(connection, design_id, vocabulary_item_id)
    group_id = insert_group(connection, design_id)
    return participant_id, design_id, vocabulary_item_id, design_item_id, group_id


def test_sqlite_foreign_keys_are_enabled(db_engine) -> None:
    with db_engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        expect_integrity_error(
            sa.insert(Design).values(
                participant_id=999,
                items_per_group=1,
                group_count=1,
                random_seed=1,
                status=DesignStatus.DRAFT.value,
                created_at=now(),
            ),
            connection,
        )


def test_participant_code_uniqueness(db_engine) -> None:
    with db_engine.begin() as connection:
        insert_participant(connection, "P001")
        expect_integrity_error(
            sa.insert(Participant).values(participant_code="P001", created_at=now()),
            connection,
        )


def test_korean_vocabulary_uniqueness(db_engine) -> None:
    with db_engine.begin() as connection:
        insert_vocabulary_item(connection, korean="사랑", english_answer="love")
        expect_integrity_error(
            sa.insert(VocabularyItem).values(
                korean="사랑",
                english_answer="affection",
                is_active=True,
                created_at=now(),
            ),
            connection,
        )


def test_nonblank_participant_and_vocabulary_constraints(db_engine) -> None:
    with db_engine.begin() as connection:
        expect_integrity_error(
            sa.insert(Participant).values(participant_code="  ", created_at=now()),
            connection,
        )
        expect_integrity_error(
            sa.insert(VocabularyItem).values(
                korean=" ",
                english_answer="word",
                is_active=True,
                created_at=now(),
            ),
            connection,
        )
        expect_integrity_error(
            sa.insert(VocabularyItem).values(
                korean="단어",
                english_answer=" ",
                is_active=True,
                created_at=now(),
            ),
            connection,
        )


def test_positive_items_per_group_and_group_count(db_engine) -> None:
    with db_engine.begin() as connection:
        participant_id = insert_participant(connection)
        expect_integrity_error(
            sa.insert(Design).values(
                participant_id=participant_id,
                items_per_group=0,
                group_count=1,
                random_seed=1,
                status=DesignStatus.DRAFT.value,
                created_at=now(),
            ),
            connection,
        )
        expect_integrity_error(
            sa.insert(Design).values(
                participant_id=participant_id,
                items_per_group=1,
                group_count=0,
                random_seed=2,
                status=DesignStatus.DRAFT.value,
                created_at=now(),
            ),
            connection,
        )


def test_one_non_terminal_design_per_participant(db_engine) -> None:
    with db_engine.begin() as connection:
        participant_id = insert_participant(connection)
        insert_design(connection, participant_id, status=DesignStatus.DRAFT)
        expect_integrity_error(
            sa.insert(Design).values(
                participant_id=participant_id,
                items_per_group=1,
                group_count=1,
                random_seed=2,
                status=DesignStatus.ACTIVE.value,
                created_at=now(),
            ),
            connection,
        )
        insert_design(
            connection,
            participant_id,
            status=DesignStatus.COMPLETED,
            random_seed=3,
        )


def test_unique_group_index_inside_design(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, _, _, _ = design_with_item_group(connection)
        expect_integrity_error(
            sa.insert(DesignGroup).values(
                test_design_id=design_id,
                group_index=1,
                interval_seconds=120,
                status=GroupStatus.PENDING.value,
            ),
            connection,
        )


def test_unique_interval_inside_design(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, _, _, _ = design_with_item_group(connection)
        expect_integrity_error(
            sa.insert(DesignGroup).values(
                test_design_id=design_id,
                group_index=2,
                interval_seconds=60,
                status=GroupStatus.PENDING.value,
            ),
            connection,
        )


def test_unique_vocabulary_item_inside_design(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, vocabulary_item_id, _, _ = design_with_item_group(connection)
        expect_integrity_error(
            sa.insert(DesignItem).values(
                test_design_id=design_id,
                vocabulary_item_id=vocabulary_item_id,
                attempt_count=0,
                correct_count=0,
                consecutive_correct_count=0,
                is_mastered=False,
                mastered_at=None,
                created_at=now(),
                updated_at=now(),
            ),
            connection,
        )


def test_mastery_state_constraints(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, vocabulary_item_id, _, _ = design_with_item_group(connection)
        second_vocabulary_item_id = insert_vocabulary_item(connection, "물", "water")
        expect_integrity_error(
            sa.insert(DesignItem).values(
                test_design_id=design_id,
                vocabulary_item_id=second_vocabulary_item_id,
                attempt_count=2,
                correct_count=2,
                consecutive_correct_count=2,
                is_mastered=False,
                mastered_at=None,
                created_at=now(),
                updated_at=now(),
            ),
            connection,
        )
        third_vocabulary_item_id = insert_vocabulary_item(connection, "불", "fire")
        expect_integrity_error(
            sa.insert(DesignItem).values(
                test_design_id=design_id,
                vocabulary_item_id=third_vocabulary_item_id,
                attempt_count=2,
                correct_count=2,
                consecutive_correct_count=1,
                is_mastered=True,
                mastered_at=now(),
                created_at=now(),
                updated_at=now(),
            ),
            connection,
        )
        insert_design_item(connection, design_id, insert_vocabulary_item(connection, "나무", "tree"), mastered=True)


def test_assignment_cannot_connect_item_and_group_from_different_designs(db_engine) -> None:
    with db_engine.begin() as connection:
        participant_id = insert_participant(connection)
        design_one_id = insert_design(connection, participant_id, random_seed=1)
        design_two_id = insert_design(connection, participant_id, random_seed=2)
        item_id = insert_design_item(connection, design_one_id, insert_vocabulary_item(connection, "하늘", "sky"))
        group_id = insert_group(connection, design_two_id)
        expect_integrity_error(
            sa.insert(Assignment).values(
                test_design_id=design_one_id,
                test_design_item_id=item_id,
                test_design_group_id=group_id,
                assignment_order=1,
                status=AssignmentStatus.AWAITING_ANCHOR.value,
                created_at=now(),
            ),
            connection,
        )


def test_one_assignment_per_design_item(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, _, item_id, group_id = design_with_item_group(connection)
        insert_assignment(connection, design_id, item_id, group_id)
        second_group_id = insert_group(connection, design_id, group_index=2, interval_seconds=120)
        expect_integrity_error(
            sa.insert(Assignment).values(
                test_design_id=design_id,
                test_design_item_id=item_id,
                test_design_group_id=second_group_id,
                assignment_order=1,
                status=AssignmentStatus.AWAITING_ANCHOR.value,
                created_at=now(),
            ),
            connection,
        )


def test_unique_assignment_order_inside_group(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, _, item_id, group_id = design_with_item_group(connection)
        insert_assignment(connection, design_id, item_id, group_id)
        second_item_id = insert_design_item(
            connection,
            design_id,
            insert_vocabulary_item(connection, "책", "book"),
        )
        expect_integrity_error(
            sa.insert(Assignment).values(
                test_design_id=design_id,
                test_design_item_id=second_item_id,
                test_design_group_id=group_id,
                assignment_order=1,
                status=AssignmentStatus.AWAITING_ANCHOR.value,
                created_at=now(),
            ),
            connection,
        )


def test_learning_check_attempt_constraints(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, _, item_id, group_id = design_with_item_group(connection)
        assignment_id = insert_assignment(connection, design_id, item_id, group_id)
        connection.execute(
            sa.insert(VocabularyAttempt).values(
                test_design_item_id=item_id,
                test_assignment_id=None,
                attempt_type=VocabularyAttemptType.LEARNING_CHECK.value,
                user_answer="",
                normalized_answer="",
                is_correct=False,
                attempted_at=now(),
                is_valid_for_fitting=False,
            )
        )
        expect_integrity_error(
            sa.insert(VocabularyAttempt).values(
                test_design_item_id=item_id,
                test_assignment_id=assignment_id,
                attempt_type=VocabularyAttemptType.LEARNING_CHECK.value,
                user_answer="hello",
                normalized_answer="hello",
                is_correct=True,
                attempted_at=now(),
                is_valid_for_fitting=False,
            ),
            connection,
        )
        expect_integrity_error(
            sa.insert(VocabularyAttempt).values(
                test_design_item_id=item_id,
                test_assignment_id=None,
                attempt_type=VocabularyAttemptType.LEARNING_CHECK.value,
                user_answer="hello",
                normalized_answer="hello",
                is_correct=True,
                attempted_at=now(),
                is_valid_for_fitting=True,
            ),
            connection,
        )


def test_delayed_recall_attempt_constraints(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, _, item_id, group_id = design_with_item_group(connection)
        assignment_id = insert_assignment(connection, design_id, item_id, group_id)
        expect_integrity_error(
            sa.insert(VocabularyAttempt).values(
                test_design_item_id=item_id,
                test_assignment_id=assignment_id,
                attempt_type=VocabularyAttemptType.DELAYED_RECALL.value,
                user_answer="hello",
                normalized_answer="hello",
                is_correct=True,
                attempted_at=now(),
                actual_retention_seconds=None,
                is_valid_for_fitting=True,
            ),
            connection,
        )
        expect_integrity_error(
            sa.insert(VocabularyAttempt).values(
                test_design_item_id=item_id,
                test_assignment_id=assignment_id,
                attempt_type=VocabularyAttemptType.DELAYED_RECALL.value,
                user_answer="hello",
                normalized_answer="hello",
                is_correct=True,
                attempted_at=now(),
                actual_retention_seconds=61,
                is_valid_for_fitting=False,
                exclusion_reason=None,
            ),
            connection,
        )
        connection.execute(
            sa.insert(VocabularyAttempt).values(
                test_design_item_id=item_id,
                test_assignment_id=assignment_id,
                attempt_type=VocabularyAttemptType.DELAYED_RECALL.value,
                user_answer="hello",
                normalized_answer="hello",
                is_correct=True,
                attempted_at=now(),
                actual_retention_seconds=61,
                is_valid_for_fitting=True,
                exclusion_reason=None,
            )
        )


def test_only_one_delayed_recall_per_assignment(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, _, item_id, group_id = design_with_item_group(connection)
        assignment_id = insert_assignment(connection, design_id, item_id, group_id)
        attempt_values = {
            "test_design_item_id": item_id,
            "test_assignment_id": assignment_id,
            "attempt_type": VocabularyAttemptType.DELAYED_RECALL.value,
            "user_answer": "hello",
            "normalized_answer": "hello",
            "is_correct": True,
            "attempted_at": now(),
            "actual_retention_seconds": 61,
            "is_valid_for_fitting": True,
            "exclusion_reason": None,
        }
        connection.execute(sa.insert(VocabularyAttempt).values(**attempt_values))
        expect_integrity_error(sa.insert(VocabularyAttempt).values(**attempt_values), connection)


def test_attempt_cannot_reference_assignment_for_another_design_item(db_engine) -> None:
    with db_engine.begin() as connection:
        _, design_id, _, item_id, group_id = design_with_item_group(connection)
        assignment_id = insert_assignment(connection, design_id, item_id, group_id)
        second_item_id = insert_design_item(
            connection,
            design_id,
            insert_vocabulary_item(connection, "길", "road"),
        )
        expect_integrity_error(
            sa.insert(VocabularyAttempt).values(
                test_design_item_id=second_item_id,
                test_assignment_id=assignment_id,
                attempt_type=VocabularyAttemptType.DELAYED_RECALL.value,
                user_answer="road",
                normalized_answer="road",
                is_correct=True,
                attempted_at=now(),
                actual_retention_seconds=61,
                is_valid_for_fitting=True,
                exclusion_reason=None,
            ),
            connection,
        )


def test_curve_model_positive_T_and_c(db_engine) -> None:
    with db_engine.begin() as connection:
        participant_id = insert_participant(connection)
        design_id = insert_design(connection, participant_id)
        expect_integrity_error(
            sa.insert(CurveModel).values(
                participant_id=participant_id,
                trigger_test_design_id=design_id,
                version=1,
                model_name=CurveModelName.EXPONENTIAL_POWER.value,
                fit_method=CurveFitMethod.BERNOULLI_MLE.value,
                T=0,
                c=0.8,
                sample_count=10,
                complete_time_point_count=5,
                converged=True,
                data_cutoff_at=now(),
                fitted_at=now(),
            ),
            connection,
        )
        expect_integrity_error(
            sa.insert(CurveModel).values(
                participant_id=participant_id,
                trigger_test_design_id=design_id,
                version=1,
                model_name=CurveModelName.EXPONENTIAL_POWER.value,
                fit_method=CurveFitMethod.BERNOULLI_MLE.value,
                T=3600,
                c=0,
                sample_count=10,
                complete_time_point_count=5,
                converged=True,
                data_cutoff_at=now(),
                fitted_at=now(),
            ),
            connection,
        )


def test_curve_model_version_uniqueness(db_engine) -> None:
    with db_engine.begin() as connection:
        participant_id = insert_participant(connection)
        first_design_id = insert_design(connection, participant_id, random_seed=1)
        second_design_id = insert_design(connection, participant_id, random_seed=2)
        insert_curve_model(connection, participant_id, first_design_id, version=1)
        expect_integrity_error(
            sa.insert(CurveModel).values(
                participant_id=participant_id,
                trigger_test_design_id=second_design_id,
                version=1,
                model_name=CurveModelName.EXPONENTIAL_POWER.value,
                fit_method=CurveFitMethod.BERNOULLI_MLE.value,
                T=3600,
                c=0.8,
                sample_count=10,
                complete_time_point_count=5,
                converged=True,
                data_cutoff_at=now(),
                fitted_at=now(),
            ),
            connection,
        )


def test_curve_trigger_design_must_belong_to_same_participant(db_engine) -> None:
    with db_engine.begin() as connection:
        first_participant_id = insert_participant(connection, "P001")
        second_participant_id = insert_participant(connection, "P002")
        first_design_id = insert_design(connection, first_participant_id)
        expect_integrity_error(
            sa.insert(CurveModel).values(
                participant_id=second_participant_id,
                trigger_test_design_id=first_design_id,
                version=1,
                model_name=CurveModelName.EXPONENTIAL_POWER.value,
                fit_method=CurveFitMethod.BERNOULLI_MLE.value,
                T=3600,
                c=0.8,
                sample_count=10,
                complete_time_point_count=5,
                converged=True,
                data_cutoff_at=now(),
                fitted_at=now(),
            ),
            connection,
        )

import json

import pytest
import sqlalchemy as sa

from app.db.database import utc_now
from app.db.models import VocabularyItem
from app.services.exceptions import ValidationServiceError
from app.services.vocabulary_import import import_vocabulary, load_vocabulary_source


def write_source(tmp_path, rows: list[dict[str, str]]):
    path = tmp_path / "vocabulary.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def test_vocabulary_source_import_works(db_session, tmp_path) -> None:
    source_path = write_source(
        tmp_path,
        [
            {"korean": "기억", "english_answer": "memory"},
            {"korean": "하늘", "english_answer": "sky"},
        ],
    )

    result = import_vocabulary(db_session, source_path)

    assert result.inserted == 2
    assert result.skipped == 0
    assert result.updated == 0
    assert db_session.scalar(sa.select(sa.func.count()).select_from(VocabularyItem)) == 2


def test_repeated_vocabulary_import_is_idempotent(db_session, tmp_path) -> None:
    source_path = write_source(tmp_path, [{"korean": "기억", "english_answer": "memory"}])

    first_result = import_vocabulary(db_session, source_path)
    second_result = import_vocabulary(db_session, source_path)

    assert first_result.inserted == 1
    assert second_result.inserted == 0
    assert second_result.skipped == 1
    assert second_result.updated == 0
    assert db_session.scalar(sa.select(sa.func.count()).select_from(VocabularyItem)) == 1


def test_import_updates_existing_answer_only_when_requested(db_session, tmp_path) -> None:
    db_session.add(
        VocabularyItem(
            korean="기억",
            english_answer="memory",
            is_active=True,
            created_at=utc_now(),
        )
    )
    db_session.commit()
    source_path = write_source(tmp_path, [{"korean": "기억", "english_answer": "remembrance"}])

    skipped_result = import_vocabulary(db_session, source_path)
    existing_item = db_session.scalar(sa.select(VocabularyItem).where(VocabularyItem.korean == "기억"))
    assert skipped_result.skipped == 1
    assert existing_item.english_answer == "memory"
    db_session.commit()

    updated_result = import_vocabulary(db_session, source_path, update_existing=True)
    db_session.refresh(existing_item)
    assert updated_result.updated == 1
    assert existing_item.english_answer == "remembrance"


def test_duplicate_korean_entries_in_source_file_are_rejected(tmp_path) -> None:
    source_path = write_source(
        tmp_path,
        [
            {"korean": "기억", "english_answer": "memory"},
            {"korean": "기억", "english_answer": "remembrance"},
        ],
    )

    with pytest.raises(ValidationServiceError) as exc_info:
        load_vocabulary_source(source_path)

    assert exc_info.value.code == "duplicate_korean"


def test_blank_korean_word_is_rejected(tmp_path) -> None:
    source_path = write_source(tmp_path, [{"korean": " ", "english_answer": "memory"}])

    with pytest.raises(ValidationServiceError) as exc_info:
        load_vocabulary_source(source_path)

    assert exc_info.value.code == "blank_korean"


def test_blank_english_answer_is_rejected(tmp_path) -> None:
    source_path = write_source(tmp_path, [{"korean": "기억", "english_answer": " "}])

    with pytest.raises(ValidationServiceError) as exc_info:
        load_vocabulary_source(source_path)

    assert exc_info.value.code == "blank_english_answer"


def test_malformed_vocabulary_import_file_is_rejected(tmp_path) -> None:
    source_path = tmp_path / "vocabulary.json"
    source_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValidationServiceError) as exc_info:
        load_vocabulary_source(source_path)

    assert exc_info.value.code == "malformed_vocabulary_source"


def test_inactive_existing_vocabulary_is_skipped_without_reactivation(db_session, tmp_path) -> None:
    db_session.add(
        VocabularyItem(
            korean="기억",
            english_answer="memory",
            is_active=False,
            created_at=utc_now(),
        )
    )
    db_session.commit()
    source_path = write_source(tmp_path, [{"korean": "기억", "english_answer": "memory"}])

    result = import_vocabulary(db_session, source_path)
    existing_item = db_session.scalar(sa.select(VocabularyItem).where(VocabularyItem.korean == "기억"))

    assert result.skipped == 1
    assert existing_item.is_active is False

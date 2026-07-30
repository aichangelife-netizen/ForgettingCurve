from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import utc_now
from app.db.models import VocabularyItem
from app.services.exceptions import ValidationServiceError


DEFAULT_VOCABULARY_SOURCE_PATH = Path(__file__).resolve().parents[2] / "data" / "vocabulary.json"


@dataclass(frozen=True)
class VocabularySourceItem:
    korean: str
    english_answer: str


@dataclass(frozen=True)
class VocabularyImportResult:
    inserted: int
    skipped: int
    updated: int


def load_vocabulary_source(path: Path = DEFAULT_VOCABULARY_SOURCE_PATH) -> list[VocabularySourceItem]:
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValidationServiceError("vocabulary_source_not_found", "Vocabulary source file was not found.") from exc
    except json.JSONDecodeError as exc:
        raise ValidationServiceError("malformed_vocabulary_source", "Vocabulary source file is not valid JSON.") from exc

    if not isinstance(raw_data, list):
        raise ValidationServiceError("malformed_vocabulary_source", "Vocabulary source must be a JSON array.")

    seen_korean: set[str] = set()
    items: list[VocabularySourceItem] = []
    for index, raw_item in enumerate(raw_data, start=1):
        if not isinstance(raw_item, dict):
            raise ValidationServiceError(
                "malformed_vocabulary_source",
                f"Vocabulary item {index} must be a JSON object.",
            )

        unexpected_keys = set(raw_item) - {"korean", "english_answer"}
        if unexpected_keys:
            raise ValidationServiceError(
                "malformed_vocabulary_source",
                f"Vocabulary item {index} contains unsupported fields.",
            )

        korean = raw_item.get("korean")
        english_answer = raw_item.get("english_answer")
        if not isinstance(korean, str) or not isinstance(english_answer, str):
            raise ValidationServiceError(
                "malformed_vocabulary_source",
                f"Vocabulary item {index} must contain string korean and english_answer fields.",
            )
        if not korean.strip():
            raise ValidationServiceError("blank_korean", f"Vocabulary item {index} has a blank Korean word.")
        if not english_answer.strip():
            raise ValidationServiceError("blank_english_answer", f"Vocabulary item {index} has a blank English answer.")
        if korean in seen_korean:
            raise ValidationServiceError("duplicate_korean", f"Duplicate Korean word in source file: {korean}")

        seen_korean.add(korean)
        items.append(VocabularySourceItem(korean=korean, english_answer=english_answer))

    return items


def import_vocabulary(
    session: Session,
    path: Path = DEFAULT_VOCABULARY_SOURCE_PATH,
    *,
    update_existing: bool = False,
) -> VocabularyImportResult:
    source_items = load_vocabulary_source(path)
    inserted = 0
    skipped = 0
    updated = 0

    with session.begin():
        existing_items = {
            item.korean: item
            for item in session.scalars(
                select(VocabularyItem).where(VocabularyItem.korean.in_([item.korean for item in source_items]))
            )
        }

        for source_item in source_items:
            existing_item = existing_items.get(source_item.korean)
            if existing_item is None:
                session.add(
                    VocabularyItem(
                        korean=source_item.korean,
                        english_answer=source_item.english_answer,
                        is_active=True,
                        created_at=utc_now(),
                    )
                )
                inserted += 1
            elif update_existing and existing_item.english_answer != source_item.english_answer:
                existing_item.english_answer = source_item.english_answer
                updated += 1
            else:
                skipped += 1

    return VocabularyImportResult(inserted=inserted, skipped=skipped, updated=updated)

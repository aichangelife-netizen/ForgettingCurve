from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import VocabularyItem


def list_vocabulary_items(
    session: Session,
    *,
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[VocabularyItem], int]:
    base_statement = select(VocabularyItem)
    count_statement = select(func.count()).select_from(VocabularyItem)
    if not include_inactive:
        base_statement = base_statement.where(VocabularyItem.is_active.is_(True))
        count_statement = count_statement.where(VocabularyItem.is_active.is_(True))

    total = session.scalar(count_statement) or 0
    items = list(
        session.scalars(
            base_statement.order_by(VocabularyItem.korean, VocabularyItem.id).limit(limit).offset(offset)
        )
    )
    return items, total

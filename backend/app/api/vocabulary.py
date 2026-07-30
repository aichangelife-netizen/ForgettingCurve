from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.vocabulary import VocabularyListResponse
from app.services.vocabulary import list_vocabulary_items


router = APIRouter(prefix="/vocabulary-items", tags=["vocabulary"])


@router.get("", response_model=VocabularyListResponse)
def list_vocabulary_items_endpoint(
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> VocabularyListResponse:
    items, total = list_vocabulary_items(
        session,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )
    return VocabularyListResponse(items=items, limit=limit, offset=offset, total=total)

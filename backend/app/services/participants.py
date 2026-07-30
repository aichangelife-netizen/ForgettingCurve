import random
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import utc_now
from app.db.models import Participant
from app.services.exceptions import NotFoundError


PARTICIPANT_CODE_PREFIX = "P-"
PARTICIPANT_CODE_LENGTH = 8
PARTICIPANT_CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_participant_code() -> str:
    suffix = "".join(random.SystemRandom().choice(PARTICIPANT_CODE_ALPHABET) for _ in range(PARTICIPANT_CODE_LENGTH))
    return f"{PARTICIPANT_CODE_PREFIX}{suffix}"


def create_participant(session: Session) -> Participant:
    with session.begin():
        for _ in range(10):
            participant_code = generate_participant_code()
            existing_id = session.scalar(
                select(Participant.id).where(Participant.participant_code == participant_code)
            )
            if existing_id is None:
                participant = Participant(participant_code=participant_code, created_at=utc_now())
                session.add(participant)
                session.flush()
                return participant

    raise RuntimeError("Could not generate a unique participant code.")


def get_participant(session: Session, participant_id: int) -> Participant:
    participant = session.get(Participant, participant_id)
    if participant is None:
        raise NotFoundError("participant_not_found", "Participant was not found.")
    return participant

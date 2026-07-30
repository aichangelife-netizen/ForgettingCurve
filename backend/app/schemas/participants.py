from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participant_code: str
    created_at: datetime

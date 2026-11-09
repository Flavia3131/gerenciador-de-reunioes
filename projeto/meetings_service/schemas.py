from typing import List, Optional

from pydantic import BaseModel


class MeetingIn(BaseModel):
    title: str
    room: Optional[str] = None
    start_time: str  # ISO 8601, ex.: 2026-11-10T14:00
    end_time: str
    recurrence: Optional[str] = None  # None | 'weekly' | 'monthly'
    participant_ids: List[int] = []  # o organizador é incluído automaticamente


class MeetingUpdate(BaseModel):
    """Todos os campos opcionais: só o que for enviado é alterado."""
    title: Optional[str] = None
    room: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    recurrence: Optional[str] = None
    participant_ids: Optional[List[int]] = None

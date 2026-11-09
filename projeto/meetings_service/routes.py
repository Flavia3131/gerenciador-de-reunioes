"""Componente de Rotas do Meetings Service (sem regra de negócio e sem SQL)."""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

import service
from schemas import MeetingIn, MeetingUpdate

router = APIRouter()


def run(fn, *args):
    try:
        return fn(*args)
    except service.ServiceError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


def get_ctx(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    """Contexto da requisição: usuário (injetado pelo gateway) e token (para consultar o Auth Service)."""
    token = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else None
    user = {"id": int(x_user_id)} if x_user_id and x_user_id.isdigit() else None
    return {"user": user, "token": token}


@router.post("/meetings", status_code=201)
def create(m: MeetingIn, ctx: dict = Depends(get_ctx)):
    return run(service.create_meeting, ctx,
               m.title, m.room, m.start_time, m.end_time, m.recurrence, m.participant_ids)


@router.get("/meetings")
def list_all(ctx: dict = Depends(get_ctx)):
    return run(service.list_meetings, ctx)


@router.get("/meetings/{meeting_id}")
def get_one(meeting_id: int, ctx: dict = Depends(get_ctx)):
    return run(service.get_meeting, ctx, meeting_id)


@router.put("/meetings/{meeting_id}")
def update(meeting_id: int, m: MeetingUpdate, ctx: dict = Depends(get_ctx)):
    changes = m.model_dump(exclude_unset=True) if hasattr(m, "model_dump") else m.dict(exclude_unset=True)
    changes = {k: v for k, v in changes.items() if v is not None or k in ("room", "recurrence")}
    return run(service.update_meeting, ctx, meeting_id, changes)


@router.delete("/meetings/{meeting_id}")
def cancel(meeting_id: int, ctx: dict = Depends(get_ctx)):
    return run(service.cancel_meeting, ctx, meeting_id)

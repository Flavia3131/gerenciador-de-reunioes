"""Componente de Regra de Negócio do Meetings Service (não conhece HTTP nem SQL)."""
from datetime import datetime

import auth_client
import database as db

RECURRENCES = (None, "weekly", "monthly")


class ServiceError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def _auth(ctx):
    """Identidade já validada pelo gateway (cabeçalho X-User-Id)."""
    if not ctx or not ctx.get("user"):
        raise ServiceError(401, "Requisição sem identidade. Acesse pela API Gateway.")
    return ctx["user"]


def _parse_time(value, field):
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise ServiceError(400, f"{field} inválido (use ISO 8601, ex.: 2026-11-10T14:00)")
    if dt.tzinfo is not None:
        raise ServiceError(400, f"{field} não deve conter fuso horário")
    return dt


def _normalize_times(start, end):
    s, e = _parse_time(start, "start_time"), _parse_time(end, "end_time")
    if e <= s:
        raise ServiceError(400, "end_time deve ser posterior a start_time")
    return s.isoformat(timespec="seconds"), e.isoformat(timespec="seconds")


def _validate_basic(title, recurrence):
    if not title or not title.strip():
        raise ServiceError(400, "Título é obrigatório")
    if recurrence not in RECURRENCES:
        raise ServiceError(400, "recurrence deve ser null, 'weekly' ou 'monthly'")


def _participants(token, organizer_id, extra):
    """Organizador sempre participa; os demais precisam existir no Auth Service."""
    ids = list(dict.fromkeys([organizer_id] + list(extra or [])))
    for uid in ids[1:]:
        try:
            user = auth_client.get_user(token, uid)
        except auth_client.Unauthorized:
            raise ServiceError(401, "Token ausente, inválido ou expirado")
        except auth_client.AuthUnavailable:
            raise ServiceError(503, "Serviço de autenticação indisponível")
        if not user:
            raise ServiceError(404, f"Usuário {uid} não encontrado")
    return ids


def _names(token, ids):
    out = []
    for uid in ids:
        try:
            user = auth_client.get_user(token, uid)
        except (auth_client.Unauthorized, auth_client.AuthUnavailable):
            user = None
        out.append(user["name"] if user else f"#{uid}")
    return out


def _check_conflicts(token, ids, start, end, exclude_id=None):
    busy = db.find_conflicts(ids, start, end, exclude_id)
    if busy:
        raise ServiceError(409, "Conflito de horário para: " + ", ".join(_names(token, busy)))


def _load(meeting_id):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise ServiceError(404, "Reunião não encontrada")
    return meeting


def create_meeting(ctx, title, room, start_time, end_time, recurrence, participant_ids):
    me = _auth(ctx)
    _validate_basic(title, recurrence)
    start, end = _normalize_times(start_time, end_time)
    ids = _participants(ctx["token"], me["id"], participant_ids)
    _check_conflicts(ctx["token"], ids, start, end)
    meeting_id = db.insert_meeting(me["id"], title.strip(), room, start, end, recurrence)
    db.add_participants(meeting_id, ids)
    return db.get_meeting(meeting_id)


def get_meeting(ctx, meeting_id):
    me = _auth(ctx)
    meeting = _load(meeting_id)
    if me["id"] not in meeting["participant_ids"]:
        raise ServiceError(403, "Você não participa desta reunião")
    return meeting


def list_meetings(ctx):
    """Apenas as reuniões em que o usuário autenticado participa."""
    me = _auth(ctx)
    return db.list_meetings(me["id"])


def _organizer_only(me, meeting):
    if me["id"] != meeting["organizer_id"]:
        raise ServiceError(403, "Apenas o organizador pode alterar esta reunião")


def update_meeting(ctx, meeting_id, changes: dict):
    me = _auth(ctx)
    current = _load(meeting_id)
    _organizer_only(me, current)
    if current["status"] == "cancelled":
        raise ServiceError(409, "Reunião cancelada não pode ser editada")

    title = changes.get("title", current["title"])
    room = changes.get("room", current["room"])
    recurrence = changes.get("recurrence", current["recurrence"])
    _validate_basic(title, recurrence)
    start, end = _normalize_times(changes.get("start_time", current["start_time"]),
                                  changes.get("end_time", current["end_time"]))

    if "participant_ids" in changes:
        ids = _participants(ctx["token"], current["organizer_id"], changes["participant_ids"])
    else:
        ids = current["participant_ids"]
    _check_conflicts(ctx["token"], ids, start, end, exclude_id=meeting_id)

    db.update_meeting(meeting_id, title.strip(), room, start, end, recurrence)
    if "participant_ids" in changes:
        db.replace_participants(meeting_id, ids)
    return db.get_meeting(meeting_id)


def cancel_meeting(ctx, meeting_id):
    me = _auth(ctx)
    meeting = _load(meeting_id)
    _organizer_only(me, meeting)
    db.set_status(meeting_id, "cancelled")  # idempotente
    return db.get_meeting(meeting_id)

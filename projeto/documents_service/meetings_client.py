"""Componente reutilizável: cliente HTTP do Meetings Service (quem pode acessar qual reunião)."""
import os

import httpx

MEETINGS_URL = os.getenv("MEETINGS_URL", "http://localhost:8002")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "dev-internal-key-troque")


class MeetingsUnavailable(Exception):
    pass


class MeetingNotFound(Exception):
    pass


class MeetingForbidden(Exception):
    pass


def _get(path, user_id):
    try:
        return httpx.get(MEETINGS_URL + path, timeout=3,
                         headers={"X-Internal-Key": INTERNAL_KEY, "X-User-Id": str(user_id)})
    except httpx.RequestError:
        raise MeetingsUnavailable()


def get_meeting(user_id, meeting_id):
    """Reunião, vista pelos olhos do usuário: 404 se não existe, 403 se ele não participa."""
    r = _get(f"/meetings/{meeting_id}", user_id)
    if r.status_code == 200:
        return r.json()
    if r.status_code == 404:
        raise MeetingNotFound()
    if r.status_code == 403:
        raise MeetingForbidden()
    raise MeetingsUnavailable()


def list_meeting_ids(user_id):
    r = _get("/meetings", user_id)
    if r.status_code != 200:
        raise MeetingsUnavailable()
    return [m["id"] for m in r.json()]

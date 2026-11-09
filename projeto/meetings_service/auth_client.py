"""Componente reutilizável: cliente HTTP do Auth Service (valida token e consulta usuários)."""
import os

import httpx

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8001")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "dev-internal-key-troque")


class AuthUnavailable(Exception):
    pass


class Unauthorized(Exception):
    pass


def _get(path, token):
    if not token:
        raise Unauthorized()
    try:
        r = httpx.get(AUTH_URL + path, headers={"Authorization": f"Bearer {token}", "X-Internal-Key": INTERNAL_KEY}, timeout=3)
    except httpx.RequestError:
        raise AuthUnavailable()
    if r.status_code == 401:
        raise Unauthorized()
    return r


def get_user(token, user_id):
    """Dados do usuário, ou None se não existir."""
    r = _get(f"/users/{user_id}", token)
    if r.status_code == 200:
        return r.json()
    if r.status_code == 404:
        return None
    raise AuthUnavailable()

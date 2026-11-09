"""Componente de Segurança: hash de senha (PBKDF2-SHA256) e tokens JWT (HS256)."""
import base64
import hashlib
import hmac
import os
import time

import jwt

# Em produção defina AUTH_SECRET com um valor longo e aleatório.
SECRET = os.getenv("AUTH_SECRET", "dev-secret-troque-em-producao-0123456789abcdef")
TOKEN_TTL = int(os.getenv("TOKEN_TTL_SECONDS", "3600"))
ITERATIONS = 200_000


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iters))
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except Exception:
        return False


DUMMY_HASH = hash_password("senha-falsa")  # evita diferença de tempo quando o e-mail não existe


def create_token(user_id: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL}, SECRET, algorithm="HS256")


def decode_token(token: str) -> int:
    """Retorna o id do usuário ou lança jwt.PyJWTError / ValueError."""
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    return int(payload["sub"])

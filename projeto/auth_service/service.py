"""Componente de Regra de Negócio do Auth Service (não conhece HTTP nem SQL)."""
import re

import jwt

import database as db
import security

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ServiceError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def _email(value):
    value = (value or "").strip().lower()
    if not EMAIL_RE.match(value):
        raise ServiceError(400, "E-mail inválido")
    return value


def _name(value):
    if not value or not value.strip():
        raise ServiceError(400, "Nome é obrigatório")
    return value.strip()


def _password(value):
    if not value or len(value) < 8:
        raise ServiceError(400, "A senha deve ter ao menos 8 caracteres")
    return value


def register(name, email, password):
    name, email, password = _name(name), _email(email), _password(password)
    if db.get_user_by_email(email):
        raise ServiceError(409, "E-mail já cadastrado")
    return db.get_user(db.insert_user(name, email, security.hash_password(password)))


def login(email, password):
    row = db.get_credentials_by_email((email or "").strip().lower())
    stored = row["password_hash"] if row else security.DUMMY_HASH
    if not security.verify_password(password or "", stored) or not row:
        raise ServiceError(401, "E-mail ou senha incorretos")
    return {"access_token": security.create_token(row["id"]), "token_type": "bearer",
            "expires_in": security.TOKEN_TTL, "user": db.get_user(row["id"])}


def authenticate(token):
    """Valida o token e devolve o usuário dono dele (401 se inválido/expirado)."""
    if not token:
        raise ServiceError(401, "Token ausente")
    try:
        user_id = security.decode_token(token)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise ServiceError(401, "Token inválido ou expirado")
    user = db.get_user(user_id)
    if not user:
        raise ServiceError(401, "Usuário do token não existe mais")
    return user


def get_user(token, user_id):
    authenticate(token)
    user = db.get_user(user_id)
    if not user:
        raise ServiceError(404, "Usuário não encontrado")
    return user


def list_users(token):
    authenticate(token)
    return db.list_users()


def update_profile(token, name, email):
    me = authenticate(token)
    name, email = _name(name), _email(email)
    other = db.get_user_by_email(email)
    if other and other["id"] != me["id"]:
        raise ServiceError(409, "E-mail já cadastrado")
    db.update_user(me["id"], name, email)
    return db.get_user(me["id"])


def change_password(token, current_password, new_password):
    me = authenticate(token)
    if not security.verify_password(current_password or "", db.get_password_hash(me["id"])):
        raise ServiceError(400, "Senha atual incorreta")
    db.update_password(me["id"], security.hash_password(_password(new_password)))


def delete_account(token):
    me = authenticate(token)
    db.delete_user(me["id"])

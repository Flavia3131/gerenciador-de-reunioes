"""Componente de Rotas do Auth Service (sem regra de negócio e sem SQL)."""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Response

import service
from schemas import LoginIn, PasswordIn, ProfileIn, RegisterIn

router = APIRouter()


def run(fn, *args):
    try:
        return fn(*args)
    except service.ServiceError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


def token_of(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


@router.post("/auth/register", status_code=201)
def register(u: RegisterIn):
    return run(service.register, u.name, u.email, u.password)


@router.post("/auth/login")
def login(c: LoginIn):
    return run(service.login, c.email, c.password)


@router.get("/auth/me")
def me(authorization: Optional[str] = Header(None)):
    return run(service.authenticate, token_of(authorization))


@router.put("/auth/me")
def update_me(p: ProfileIn, authorization: Optional[str] = Header(None)):
    return run(service.update_profile, token_of(authorization), p.name, p.email)


@router.post("/auth/change-password", status_code=204)
def change_password(p: PasswordIn, authorization: Optional[str] = Header(None)):
    run(service.change_password, token_of(authorization), p.current_password, p.new_password)
    return Response(status_code=204)


@router.delete("/auth/me", status_code=204)
def delete_me(authorization: Optional[str] = Header(None)):
    run(service.delete_account, token_of(authorization))
    return Response(status_code=204)


@router.get("/users")
def list_all(authorization: Optional[str] = Header(None)):
    return run(service.list_users, token_of(authorization))


@router.get("/users/{user_id}")
def get_one(user_id: int, authorization: Optional[str] = Header(None)):
    return run(service.get_user, token_of(authorization), user_id)

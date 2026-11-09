from pydantic import BaseModel


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: str
    email: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str

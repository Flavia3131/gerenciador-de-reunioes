"""Componente de Armazenamento: grava arquivos em disco com nome aleatório (nunca o nome enviado)."""
import hashlib
import os
import uuid

STORAGE_DIR = os.getenv("DOCS_STORAGE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage"))
os.makedirs(STORAGE_DIR, exist_ok=True)


def save(data: bytes):
    """Grava os bytes e devolve (nome_interno, sha256)."""
    name = uuid.uuid4().hex
    with open(os.path.join(STORAGE_DIR, name), "wb") as f:
        f.write(data)
    return name, hashlib.sha256(data).hexdigest()


def path(stored_name: str) -> str:
    return os.path.join(STORAGE_DIR, os.path.basename(stored_name))


def delete(stored_name: str):
    try:
        os.remove(path(stored_name))
    except FileNotFoundError:
        pass

"""Componente de Regra de Negócio do Documents Service (não conhece HTTP nem SQL)."""
import mimetypes
import os

import database as db
import meetings_client as mc
import storage

TYPES = ("ata", "processo", "outro")
ALLOWED_EXT = {"pdf", "doc", "docx", "odt", "rtf", "txt", "md", "xls", "xlsx", "csv",
               "ppt", "pptx", "png", "jpg", "jpeg"}
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024


class ServiceError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def _meeting(user_id, meeting_id):
    """Reunião acessível ao usuário (participante). Mapeia falhas para 404/403/503."""
    try:
        return mc.get_meeting(user_id, meeting_id)
    except mc.MeetingNotFound:
        raise ServiceError(404, "Reunião não encontrada")
    except mc.MeetingForbidden:
        raise ServiceError(403, "Você não participa desta reunião")
    except mc.MeetingsUnavailable:
        raise ServiceError(503, "Serviço de reuniões indisponível")


def _not_cancelled(meeting):
    if meeting["status"] == "cancelled":
        raise ServiceError(409, "Reunião cancelada não aceita novos documentos")


def _meta(doc_type, title, description):
    if doc_type not in TYPES:
        raise ServiceError(400, f"Tipo inválido (use: {', '.join(TYPES)})")
    if not title or not title.strip() or len(title) > 200:
        raise ServiceError(400, "Título é obrigatório (máx. 200 caracteres)")
    if len(description or "") > 1000:
        raise ServiceError(400, "Descrição muito longa (máx. 1000 caracteres)")
    return doc_type, title.strip(), (description or "").strip()


def _file(filename, data):
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if not name or ext not in ALLOWED_EXT:
        raise ServiceError(400, "Tipo de arquivo não permitido (aceitos: " + ", ".join(sorted(ALLOWED_EXT)) + ")")
    if not data:
        raise ServiceError(400, "Arquivo vazio")
    if len(data) > MAX_BYTES:
        raise ServiceError(413, f"Arquivo maior que {MAX_BYTES // 1048576} MB")
    return name, mimetypes.guess_type(name)[0] or "application/octet-stream"


def _store(user_id, filename, data):
    name, ctype = _file(filename, data)
    stored, sha = storage.save(data)
    return {"filename": name, "content_type": ctype, "size": len(data), "sha256": sha,
            "stored_name": stored, "uploaded_by": user_id}


def _load(doc_id):
    doc = db.get_document(doc_id)
    if not doc:
        raise ServiceError(404, "Documento não encontrado")
    return doc


def _detail(doc_id):
    doc = _load(doc_id)
    doc["versions"] = db.get_versions(doc_id)
    return doc


def _can_manage(user_id, doc, meeting):
    """Autor do documento ou organizador da reunião."""
    if user_id != doc["created_by"] and user_id != meeting["organizer_id"]:
        raise ServiceError(403, "Apenas o autor do documento ou o organizador da reunião pode fazer isso")


def create_document(user_id, meeting_id, doc_type, title, description, filename, data):
    meeting = _meeting(user_id, meeting_id)
    _not_cancelled(meeting)
    doc_type, title, description = _meta(doc_type, title, description)
    info = _store(user_id, filename, data)
    try:
        doc_id = db.insert_document(meeting_id, doc_type, title, description, user_id, info)
    except Exception:
        storage.delete(info["stored_name"])
        raise
    return _detail(doc_id)


def list_documents(user_id, meeting_id=None, doc_type=None):
    if doc_type and doc_type not in TYPES:
        raise ServiceError(400, f"Tipo inválido (use: {', '.join(TYPES)})")
    if meeting_id is not None:
        _meeting(user_id, meeting_id)
        ids = [meeting_id]
    else:  # todos os documentos das reuniões em que o usuário participa
        try:
            ids = mc.list_meeting_ids(user_id)
        except mc.MeetingsUnavailable:
            raise ServiceError(503, "Serviço de reuniões indisponível")
    return db.list_documents(ids, doc_type)


def get_document(user_id, doc_id):
    doc = _detail(doc_id)
    _meeting(user_id, doc["meeting_id"])
    return doc


def update_document(user_id, doc_id, changes):
    doc = _load(doc_id)
    meeting = _meeting(user_id, doc["meeting_id"])
    _can_manage(user_id, doc, meeting)
    doc_type, title, description = _meta(changes.get("doc_type", doc["doc_type"]),
                                         changes.get("title", doc["title"]),
                                         changes.get("description", doc["description"]))
    db.update_document(doc_id, doc_type, title, description)
    return _detail(doc_id)


def add_version(user_id, doc_id, filename, data):
    """Qualquer participante pode enviar nova versão; o histórico preserva as anteriores."""
    doc = _load(doc_id)
    meeting = _meeting(user_id, doc["meeting_id"])
    _not_cancelled(meeting)
    info = _store(user_id, filename, data)
    try:
        db.add_version(doc_id, info)
    except Exception:
        storage.delete(info["stored_name"])
        raise
    return _detail(doc_id)


def get_download(user_id, doc_id, version=None):
    doc = _load(doc_id)
    _meeting(user_id, doc["meeting_id"])
    row = db.get_version(doc_id, version or doc["current_version"])
    if not row:
        raise ServiceError(404, "Versão não encontrada")
    path = storage.path(row["stored_name"])
    if not os.path.exists(path):
        raise ServiceError(404, "Arquivo não encontrado no armazenamento")
    return row, path


def delete_document(user_id, doc_id):
    doc = _load(doc_id)
    meeting = _meeting(user_id, doc["meeting_id"])
    _can_manage(user_id, doc, meeting)
    for stored in db.delete_document(doc_id):
        storage.delete(stored)

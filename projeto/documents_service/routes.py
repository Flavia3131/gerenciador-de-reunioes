"""Componente de Rotas do Documents Service (sem regra de negócio e sem SQL)."""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

import service
from schemas import DocumentUpdate

router = APIRouter()


def run(fn, *args):
    try:
        return fn(*args)
    except service.ServiceError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


def current_user_id(x_user_id: Optional[str] = Header(None)) -> int:
    """Identidade injetada pelo gateway (X-User-Id)."""
    if x_user_id and x_user_id.isdigit():
        return int(x_user_id)
    raise HTTPException(status_code=401, detail="Requisição sem identidade. Acesse pela API Gateway.")


async def read_upload(file: UploadFile) -> bytes:
    return await file.read(service.MAX_BYTES + 1)  # +1 para detectar excesso


@router.post("/documents", status_code=201)
async def create(meeting_id: int = Form(...), doc_type: str = Form(...), title: str = Form(...),
                 description: str = Form(""), file: UploadFile = File(...), user_id: int = Depends(current_user_id)):
    data = await read_upload(file)
    return await run_in_threadpool(run, service.create_document, user_id, meeting_id, doc_type,
                                   title, description, file.filename, data)


@router.get("/documents")
def list_all(meeting_id: Optional[int] = None, doc_type: Optional[str] = None,
             user_id: int = Depends(current_user_id)):
    return run(service.list_documents, user_id, meeting_id, doc_type)


@router.get("/documents/{doc_id}")
def get_one(doc_id: int, user_id: int = Depends(current_user_id)):
    return run(service.get_document, user_id, doc_id)


@router.put("/documents/{doc_id}")
def update(doc_id: int, d: DocumentUpdate, user_id: int = Depends(current_user_id)):
    changes = d.model_dump(exclude_unset=True) if hasattr(d, "model_dump") else d.dict(exclude_unset=True)
    return run(service.update_document, user_id, doc_id, {k: v for k, v in changes.items() if v is not None})


@router.post("/documents/{doc_id}/versions", status_code=201)
async def new_version(doc_id: int, file: UploadFile = File(...), user_id: int = Depends(current_user_id)):
    data = await read_upload(file)
    return await run_in_threadpool(run, service.add_version, user_id, doc_id, file.filename, data)


@router.get("/documents/{doc_id}/download")
def download(doc_id: int, version: Optional[int] = None, user_id: int = Depends(current_user_id)):
    row, path = run(service.get_download, user_id, doc_id, version)
    return FileResponse(path, media_type=row["content_type"], filename=row["filename"],
                        headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/documents/{doc_id}", status_code=204)
def delete(doc_id: int, user_id: int = Depends(current_user_id)):
    run(service.delete_document, user_id, doc_id)
    return Response(status_code=204)

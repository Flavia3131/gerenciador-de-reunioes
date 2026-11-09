from typing import Optional

from pydantic import BaseModel


class DocumentUpdate(BaseModel):
    """Atualização parcial dos metadados (o arquivo muda por nova versão)."""
    title: Optional[str] = None
    doc_type: Optional[str] = None
    description: Optional[str] = None

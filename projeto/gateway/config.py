"""Configuração do gateway: serviços, tabela de rotas e limites. Tudo ajustável por variáveis de ambiente."""
import os
from typing import NamedTuple, Optional, Tuple

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8001")
MEETINGS_URL = os.getenv("MEETINGS_URL", "http://localhost:8002")
DOCUMENTS_URL = os.getenv("DOCUMENTS_URL", "http://localhost:8003")
# Chave compartilhada entre gateway e serviços: só quem a conhece consegue chamar os serviços.
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "dev-internal-key-troque")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))
# Limite do corpo da requisição (uploads). Um pouco acima do limite de arquivo do Documents Service.
MAX_BODY = int(os.getenv("MAX_BODY_MB", "12")) * 1024 * 1024

SERVICES = {
    "auth": ("Serviço de autenticação", AUTH_URL),
    "meetings": ("Serviço de reuniões", MEETINGS_URL),
    "documents": ("Serviço de documentos", DOCUMENTS_URL),
}


class Route(NamedTuple):
    prefix: str
    service: str
    protected: bool = True                      # exige token válido?
    limit: Optional[Tuple[int, int]] = None     # (requisições, janela em segundos) por IP


# A ordem importa: rotas mais específicas primeiro.
ROUTES = [
    Route("/auth/register", "auth", protected=False, limit=(int(os.getenv("RATE_REGISTER", "10")), 60)),
    Route("/auth/login", "auth", protected=False, limit=(int(os.getenv("RATE_LOGIN", "10")), 60)),
    Route("/auth", "auth"),
    Route("/users", "auth"),
    Route("/meetings", "meetings"),
    Route("/documents", "documents"),
]


def match(path: str) -> Optional[Route]:
    for r in ROUTES:
        if path == r.prefix or path.startswith(r.prefix + "/"):
            return r
    return None

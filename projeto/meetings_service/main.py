import hmac
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from database import init_db
from routes import router

# O serviço só aceita chamadas que carreguem a chave interna (enviada pelo gateway
# ou por outro serviço). CORS é responsabilidade do gateway.
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "dev-internal-key-troque")
OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

app = FastAPI(title="Meetings Service")
init_db()
app.include_router(router)


@app.middleware("http")
async def only_from_gateway(request: Request, call_next):
    key = request.headers.get("x-internal-key", "")
    if request.url.path not in OPEN_PATHS and not hmac.compare_digest(key, INTERNAL_KEY):
        return JSONResponse(status_code=403, content={"detail": "Acesso direto negado. Use a API Gateway."})
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # O documento especifica 400 (e não o 422 padrão) para dados inválidos.
    errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=400, content={"detail": "Dados inválidos", "errors": errors})

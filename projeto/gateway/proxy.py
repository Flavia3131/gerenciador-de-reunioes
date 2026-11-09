"""Núcleo do gateway: roteia, autentica, propaga identidade e repassa a resposta."""
import logging
import time
import uuid

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse

import config
from ratelimit import RateLimiter

log = logging.getLogger("gateway")
client = httpx.AsyncClient()
limiter = RateLimiter()

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
       "trailers", "transfer-encoding", "upgrade", "host", "content-length"}
# Cabeçalhos que o cliente NÃO pode forjar: o gateway é quem define a identidade.
STRIP_IN = HOP | {"x-user-id", "x-internal-key", "x-request-id"}
STRIP_OUT = HOP | {"content-encoding"}


def error(status, detail, rid, extra=None):
    return JSONResponse(status_code=status, content={"detail": detail},
                        headers={"X-Request-ID": rid, **(extra or {})})


async def authenticate(authorization, rid):
    """Valida o token no Auth Service. Devolve (user_id, None) ou (None, resposta_de_erro)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None, error(401, "Token ausente", rid)
    try:
        r = await client.get(config.AUTH_URL + "/auth/me", timeout=config.REQUEST_TIMEOUT,
                             headers={"Authorization": authorization, "X-Internal-Key": config.INTERNAL_KEY})
    except httpx.RequestError:
        return None, error(503, "Serviço de autenticação indisponível", rid)
    if r.status_code == 200:
        return r.json()["id"], None
    if r.status_code == 401:
        return None, error(401, r.json().get("detail", "Token inválido ou expirado"), rid)
    return None, error(503, "Serviço de autenticação indisponível", rid)


async def forward(request: Request) -> Response:
    started, rid = time.monotonic(), uuid.uuid4().hex[:12]
    path = request.url.path
    resp = await _handle(request, path, rid)
    log.info("%s %s -> %s (%.0f ms) rid=%s", request.method, path, resp.status_code,
             (time.monotonic() - started) * 1000, rid)
    return resp


async def _handle(request: Request, path: str, rid: str) -> Response:
    route = config.match(path)
    if not route:
        return error(404, "Rota não encontrada", rid)

    if route.limit:
        ip = request.client.host if request.client else "?"
        wait = limiter.check((ip, route.prefix), *route.limit)
        if wait:
            return error(429, f"Muitas tentativas. Tente de novo em {wait}s.", rid, {"Retry-After": str(wait)})

    headers = {k: v for k, v in request.headers.items() if k.lower() not in STRIP_IN}
    headers["X-Internal-Key"] = config.INTERNAL_KEY
    headers["X-Request-ID"] = rid

    if route.protected:
        user_id, err = await authenticate(request.headers.get("authorization"), rid)
        if err:
            return err
        headers["X-User-Id"] = str(user_id)  # identidade confiável, injetada pelo gateway

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > config.MAX_BODY:
        return error(413, f"Requisição maior que {config.MAX_BODY // 1048576} MB", rid)
    body = await request.body()
    if len(body) > config.MAX_BODY:
        return error(413, f"Requisição maior que {config.MAX_BODY // 1048576} MB", rid)

    label, base = config.SERVICES[route.service]
    try:
        up = await client.request(request.method, base + path, params=request.query_params,
                                  content=body, headers=headers,
                                  timeout=config.REQUEST_TIMEOUT)
    except httpx.TimeoutException:
        return error(504, f"{label} demorou demais para responder", rid)
    except httpx.RequestError:
        return error(503, f"{label} indisponível", rid)

    out = {k: v for k, v in up.headers.items() if k.lower() not in STRIP_OUT}
    out["X-Request-ID"] = rid
    return Response(content=up.content, status_code=up.status_code, headers=out)

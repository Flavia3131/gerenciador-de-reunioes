import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
import proxy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
app = FastAPI(title="API Gateway", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID", "Retry-After"])


@app.on_event("shutdown")
async def close_client():
    await proxy.client.aclose()


@app.get("/health")
async def health():
    services = {}
    for name, (_, url) in config.SERVICES.items():
        try:
            r = await proxy.client.get(url + "/health", timeout=2)
            services[name] = "up" if r.status_code == 200 else "down"
        except httpx.RequestError:
            services[name] = "down"
    ok = all(v == "up" for v in services.values())
    return JSONResponse(status_code=200 if ok else 503,
                        content={"gateway": "up", "status": "ok" if ok else "degraded", "services": services})


@app.get("/routes")
async def routes():
    return [{"prefix": r.prefix, "service": r.service, "auth_required": r.protected,
             "rate_limit": r.limit} for r in config.ROUTES]


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def gateway(request: Request, path: str):
    return await proxy.forward(request)

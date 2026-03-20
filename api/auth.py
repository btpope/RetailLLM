"""
TestGPT — API Key Authentication Middleware
Supports X-API-Key header or ?api_key= query param.
Exempts /health, /docs, /openapi.json, /redoc.
"""

import os
from fastapi import Request
from fastapi.responses import JSONResponse

TESTGPT_API_KEY = os.getenv("TESTGPT_API_KEY", "")
EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/"}
EXEMPT_PREFIXES = ("/static/",)


async def api_key_middleware(request: Request, call_next):
    if request.url.path in EXEMPT_PATHS or any(request.url.path.startswith(p) for p in EXEMPT_PREFIXES):
        return await call_next(request)

    if not TESTGPT_API_KEY:
        # No key configured — open (local dev mode)
        return await call_next(request)

    api_key = (
        request.headers.get("X-API-Key")
        or request.query_params.get("api_key")
    )

    if api_key != TESTGPT_API_KEY:
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized — provide a valid API key via X-API-Key header or ?api_key= query param"},
        )

    return await call_next(request)

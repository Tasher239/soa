import json
import time
import uuid
from datetime import datetime, timezone
from app.infrastructure.security.jwt_service import jwt_service
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import logging

logger = logging.getLogger("marketplace.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        start_ns = time.perf_counter_ns()

        user_id: str | None = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                payload = jwt_service.decode_access_token(auth_header[7:])
                user_id = payload.get("sub")
            except Exception:
                pass

        body_log: dict | None = None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_data = json.loads(body_bytes)
                    body_log = _mask_sensitive(body_data)
            except Exception:
                pass

        response = await call_next(request)

        duration_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)

        log_entry: dict = {
            "request_id": request_id,
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if body_log is not None:
            log_entry["request_body"] = body_log

        logger.info(json.dumps(log_entry))

        response.headers["X-Request-Id"] = request_id
        return response


def _mask_sensitive(data: object) -> object:
    if isinstance(data, dict):
        return {
            k: "***MASKED***" if k in ("password", "refresh_token") else _mask_sensitive(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_mask_sensitive(item) for item in data]
    return data

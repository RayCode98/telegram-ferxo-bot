from __future__ import annotations
import asyncio, json
from datetime import datetime, timezone
from sqlalchemy import text
from app.config import settings
from app.database import SessionLocal
from app.redis_client import redis

_started_at = datetime.now(timezone.utc)
_ready = False
_recovery_summary: dict = {}

def mark_ready(recovery_summary: dict | None = None) -> None:
    global _ready, _recovery_summary
    _ready = True; _recovery_summary = recovery_summary or {}

async def check_components() -> tuple[bool, dict]:
    db_ok = redis_ok = False; errors=[]
    try:
        async with SessionLocal() as session: await session.execute(text("SELECT 1"))
        db_ok=True
    except Exception as exc: errors.append(f"database:{type(exc).__name__}")
    try: redis_ok=bool(await redis.ping())
    except Exception as exc: errors.append(f"redis:{type(exc).__name__}")
    ok=bool(_ready and db_ok and redis_ok)
    return ok, {"status":"ok" if ok else "degraded","ready":_ready,"database":db_ok,"redis":redis_ok,"started_at":_started_at.isoformat(),"recovery":_recovery_summary,"errors":errors}

async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line=await asyncio.wait_for(reader.readline(),timeout=2); path="/"
        if request_line:
            parts=request_line.decode("latin-1",errors="ignore").split()
            if len(parts)>=2: path=parts[1]
        while True:
            line=await asyncio.wait_for(reader.readline(),timeout=2)
            if line in {b"\r\n",b"\n",b""}: break
        if path not in {"/health","/ready"}: status="404 Not Found"; body={"status":"not_found"}
        else:
            ok,body=await check_components(); status="200 OK" if ok else "503 Service Unavailable"
        raw=json.dumps(body,ensure_ascii=False).encode()
        writer.write(f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\nConnection: close\r\n\r\n".encode()+raw)
        await writer.drain()
    except Exception: pass
    finally:
        writer.close()
        try: await writer.wait_closed()
        except Exception: pass

async def run_health_server() -> None:
    server=await asyncio.start_server(_handle,settings.health_host,settings.health_port)
    async with server: await server.serve_forever()

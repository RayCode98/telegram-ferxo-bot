import asyncio
from sqlalchemy import text
from app.config import settings
from app.database import SessionLocal
from app.redis_client import redis
async def main():
    print("environment:",settings.environment)
    async with SessionLocal() as session: print("postgres:","ok" if (await session.execute(text("SELECT 1"))).scalar_one()==1 else "bad")
    print("redis:","ok" if await redis.ping() else "bad")
if __name__=="__main__": asyncio.run(main())

import asyncio,time,uuid
from app.redis_client import redis
async def worker(prefix,operations):
    for i in range(operations):
        key=f"loadtest:{prefix}:{i}"; await redis.set(key,"1",ex=60); await redis.get(key); await redis.delete(key)
async def main(workers=50,operations=100):
    token=uuid.uuid4().hex[:8]; start=time.perf_counter(); await asyncio.gather(*(worker(f"{token}:{i}",operations) for i in range(workers))); elapsed=time.perf_counter()-start; total=workers*operations*3; print(f"operations={total} elapsed={elapsed:.2f}s ops_per_sec={total/elapsed:.0f}")
if __name__=="__main__": asyncio.run(main())

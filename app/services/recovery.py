from __future__ import annotations
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Conversation, RecoveryRun, User
from app.redis_client import redis
from app.services.matchmaking import MODE_KEY, QUEUE_KEY, set_active_pair
logger=logging.getLogger(__name__)

async def _clear_pattern(pattern: str) -> int:
    keys=[]
    async for key in redis.scan_iter(match=pattern,count=500): keys.append(key)
    if keys: await redis.delete(*keys)
    return len(keys)

async def recover_runtime_state() -> dict:
    await redis.delete(QUEUE_KEY, MODE_KEY)
    await _clear_pattern("chat:partner:*"); await _clear_pattern("chat:conversation:*")
    recovered=conflicts=0; claimed:set[str]=set(); now=datetime.now(timezone.utc)
    async with SessionLocal() as session:
        result=await session.execute(select(Conversation).where(Conversation.status=="active").order_by(Conversation.started_at.desc()))
        for conversation in result.scalars():
            if conversation.user1_id in claimed or conversation.user2_id in claimed:
                conversation.status="ended"; conversation.ended_reason="recovery_conflict"; conversation.ended_at=now; conflicts+=1; continue
            user1=await session.get(User,conversation.user1_id); user2=await session.get(User,conversation.user2_id)
            if not user1 or not user2 or user1.is_banned or user2.is_banned or not user1.onboarding_completed or not user2.onboarding_completed:
                conversation.status="ended"; conversation.ended_reason="recovery_invalid"; conversation.ended_at=now; conflicts+=1; continue
            await set_active_pair(user1,user2,conversation.id); claimed.update({user1.id,user2.id}); recovered+=1
        session.add(RecoveryRun(recovered_conversations=recovered,closed_conflicts=conflicts,notes="matchmaking queue cleared; active pairs rebuilt")); await session.commit()
    summary={"recovered_conversations":recovered,"closed_conflicts":conflicts}; logger.info("runtime_recovery_completed",extra=summary); return summary

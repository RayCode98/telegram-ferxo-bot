from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AccountLifecycle, ExperiencePreference, Favorite, User, UserInterest
from app.redis_client import redis
from app.repositories import end_conversation
from app.services.matchmaking import dequeue, get_active_partner, clear_active_pair

async def get_lifecycle(session: AsyncSession,user: User) -> AccountLifecycle:
    result=await session.execute(select(AccountLifecycle).where(AccountLifecycle.user_id==user.id)); lifecycle=result.scalar_one_or_none()
    if lifecycle: return lifecycle
    lifecycle=AccountLifecycle(user_id=user.id,state="active"); session.add(lifecycle); await session.flush(); return lifecycle

async def is_deleted(session: AsyncSession,user: User) -> bool:
    return (await get_lifecycle(session,user)).state == "deleted"

async def delete_account(session: AsyncSession,user: User) -> int | None:
    partner_to_notify=None
    active=await get_active_partner(user.telegram_id)
    if active:
        partner_tg,conversation_id=active; partner_to_notify=partner_tg
        await end_conversation(session,conversation_id,user.id,"account_deleted"); await clear_active_pair(user.telegram_id,partner_tg)
    await dequeue(user.telegram_id)
    await redis.delete(f"presence:active:{user.telegram_id}",f"presence:dbtouch:{user.telegram_id}",f"chat:panel_message:{user.telegram_id}",f"chat:panel_conversation:{user.telegram_id}")
    await session.execute(delete(UserInterest).where(UserInterest.user_id==user.id))
    await session.execute(delete(Favorite).where((Favorite.user_id==user.id)|(Favorite.favorite_user_id==user.id)))
    prefs=(await session.execute(select(ExperiencePreference).where(ExperiencePreference.user_id==user.id))).scalar_one_or_none()
    if prefs: prefs.show_activity_status=False; prefs.smart_notifications=False
    user.alias="Usuario eliminado"; user.bio=None; user.photo_file_id=None; user.latitude=None; user.longitude=None; user.location_updated_at=None; user.gender=None; user.seeking_gender="any"; user.onboarding_completed=False; user.adult_confirmed=False; user.boost_until=None
    lifecycle=await get_lifecycle(session,user); lifecycle.state="deleted"; lifecycle.deleted_at=datetime.now(timezone.utc); lifecycle.deletion_reason="user_requested"
    await session.commit(); return partner_to_notify

async def reactivate_account(session: AsyncSession,user: User) -> None:
    lifecycle=await get_lifecycle(session,user); lifecycle.state="active"; lifecycle.reactivated_at=datetime.now(timezone.utc); lifecycle.deletion_reason=None
    user.alias=None; user.onboarding_completed=False; user.adult_confirmed=False
    await session.commit()

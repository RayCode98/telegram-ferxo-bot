from __future__ import annotations

import math
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.redis_client import redis
from app.repositories import (
    are_blocked,
    create_conversation,
    get_user_by_telegram,
)


QUEUE_KEY = "matchmaking:queue"
MODE_KEY = "matchmaking:mode"
MATCH_LOCK = "matchmaking:lock"


def age_of(birth_date: date | None) -> int | None:
    if not birth_date:
        return None
    today = date.today()
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def accepts(seeking: str, gender: str | None) -> bool:
    return seeking == "any" or seeking == gender


def haversine_km(a: User, b: User) -> float | None:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [a.latitude, a.longitude, b.latitude, b.longitude],
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def base_compatible(a: User, b: User) -> bool:
    if a.id == b.id:
        return False
    if not a.onboarding_completed or not b.onboarding_completed:
        return False
    if a.is_banned or b.is_banned:
        return False

    age_a = age_of(a.birth_date)
    age_b = age_of(b.birth_date)
    if age_a is None or age_b is None:
        return False

    if not (a.min_age <= age_b <= a.max_age):
        return False
    if not (b.min_age <= age_a <= b.max_age):
        return False

    if not accepts(a.seeking_gender, b.gender):
        return False
    if not accepts(b.seeking_gender, a.gender):
        return False

    return True


async def is_premium(user: User) -> bool:
    return bool(
        user.premium_until
        and user.premium_until > datetime.now(timezone.utc)
    )


async def can_search(user: User) -> tuple[bool, int]:
    if await is_premium(user):
        return True, 0

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"searches:{day}:{user.telegram_id}"
    current = int(await redis.get(key) or 0)
    remaining = max(settings.free_daily_search_limit - current, 0)
    return current < settings.free_daily_search_limit, remaining


async def consume_search(user: User) -> None:
    if await is_premium(user):
        return
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"searches:{day}:{user.telegram_id}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 172800)
    await pipe.execute()


async def enqueue(user: User, mode: str) -> None:
    now = datetime.now(timezone.utc).timestamp()
    pipe = redis.pipeline()
    pipe.zadd(QUEUE_KEY, {str(user.telegram_id): now})
    pipe.hset(MODE_KEY, str(user.telegram_id), mode)
    await pipe.execute()


async def dequeue(telegram_id: int) -> None:
    pipe = redis.pipeline()
    pipe.zrem(QUEUE_KEY, str(telegram_id))
    pipe.hdel(MODE_KEY, str(telegram_id))
    await pipe.execute()


async def is_searching(telegram_id: int) -> bool:
    return await redis.zscore(QUEUE_KEY, str(telegram_id)) is not None


async def get_active_partner(telegram_id: int) -> tuple[int, str] | None:
    partner = await redis.get(f"chat:partner:{telegram_id}")
    conversation_id = await redis.get(f"chat:conversation:{telegram_id}")
    if not partner or not conversation_id:
        return None
    return int(partner), conversation_id


async def set_active_pair(
    a: User,
    b: User,
    conversation_id: str,
) -> None:
    pipe = redis.pipeline()
    pipe.set(f"chat:partner:{a.telegram_id}", str(b.telegram_id))
    pipe.set(f"chat:conversation:{a.telegram_id}", conversation_id)
    pipe.set(f"chat:partner:{b.telegram_id}", str(a.telegram_id))
    pipe.set(f"chat:conversation:{b.telegram_id}", conversation_id)
    await pipe.execute()


async def clear_active_pair(a_tg: int, b_tg: int) -> None:
    await redis.delete(
        f"chat:partner:{a_tg}",
        f"chat:conversation:{a_tg}",
        f"chat:partner:{b_tg}",
        f"chat:conversation:{b_tg}",
    )


async def score_candidate(
    seeker: User,
    candidate: User,
    seeker_mode: str,
    candidate_mode: str,
) -> float | None:
    if not base_compatible(seeker, candidate):
        return None

    distance = haversine_km(seeker, candidate)

    if seeker_mode == "nearby":
        if distance is None or distance > seeker.max_distance_km:
            return None

    if candidate_mode == "nearby":
        if distance is None or distance > candidate.max_distance_km:
            return None

    score = 100.0

    if distance is not None:
        score += max(0, 30 - min(distance, 30))

    age_a = age_of(seeker.birth_date) or 99
    age_b = age_of(candidate.birth_date) or 99
    score += max(0, 15 - abs(age_a - age_b))

    now = datetime.now(timezone.utc)
    if candidate.boost_until and candidate.boost_until > now:
        score += 100

    # Mantiene cierta aleatoriedad porque la cola sigue ordenada por tiempo,
    # pero favorece compatibilidad y Boost.
    return score


async def try_match(
    session: AsyncSession,
    seeker: User,
    mode: str,
) -> tuple[User, str] | None:
    async with redis.lock(MATCH_LOCK, timeout=8, blocking_timeout=4):
        if await get_active_partner(seeker.telegram_id):
            return None

        candidate_ids = await redis.zrange(QUEUE_KEY, 0, 99)
        best: tuple[float, User] | None = None

        for candidate_tg_str in candidate_ids:
            candidate_tg = int(candidate_tg_str)
            if candidate_tg == seeker.telegram_id:
                continue
            if await get_active_partner(candidate_tg):
                await dequeue(candidate_tg)
                continue

            candidate = await get_user_by_telegram(session, candidate_tg)
            if not candidate:
                await dequeue(candidate_tg)
                continue
            if await are_blocked(session, seeker, candidate):
                continue

            candidate_mode = await redis.hget(MODE_KEY, candidate_tg_str) or "global"
            candidate_score = await score_candidate(
                seeker,
                candidate,
                mode,
                candidate_mode,
            )
            if candidate_score is None:
                continue

            if best is None or candidate_score > best[0]:
                best = (candidate_score, candidate)

        if best is None:
            await enqueue(seeker, mode)
            return None

        candidate = best[1]
        await dequeue(seeker.telegram_id)
        await dequeue(candidate.telegram_id)

        conversation = await create_conversation(session, seeker, candidate)
        await set_active_pair(seeker, candidate, conversation.id)
        await consume_search(seeker)
        await consume_search(candidate)
        return candidate, conversation.id

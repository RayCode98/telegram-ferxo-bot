from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    GrowthProfile,
    Referral,
    ReferralReward,
    User,
    VirtualGift,
)
from app.repositories import add_consumable, get_or_create_balance
from app.redis_client import redis
from app.services.analytics import track_event


COUNTRIES = {
    "MX": "🇲🇽 México",
    "CO": "🇨🇴 Colombia",
    "AR": "🇦🇷 Argentina",
    "ES": "🇪🇸 España",
    "US": "🇺🇸 Estados Unidos",
    "CL": "🇨🇱 Chile",
    "PE": "🇵🇪 Perú",
    "VE": "🇻🇪 Venezuela",
    "BR": "🇧🇷 Brasil",
    "EC": "🇪🇨 Ecuador",
    "GT": "🇬🇹 Guatemala",
    "SV": "🇸🇻 El Salvador",
    "HN": "🇭🇳 Honduras",
    "CR": "🇨🇷 Costa Rica",
    "PA": "🇵🇦 Panamá",
    "DO": "🇩🇴 Rep. Dominicana",
    "UY": "🇺🇾 Uruguay",
    "PY": "🇵🇾 Paraguay",
    "BO": "🇧🇴 Bolivia",
    "NI": "🇳🇮 Nicaragua",
}


def country_label(code: str | None) -> str:
    if not code:
        return "Sin configurar"
    code = code.upper()
    return COUNTRIES.get(code, f"🌍 {code}")


async def get_growth_profile(
    session: AsyncSession,
    user: User,
) -> GrowthProfile:
    result = await session.execute(
        select(GrowthProfile).where(GrowthProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        return profile

    # Código corto seguro para deep-link, sólo chars admitidos por Telegram.
    while True:
        code = secrets.token_urlsafe(7).replace("-", "").replace("_", "")[:10]
        exists = await session.execute(
            select(GrowthProfile.id).where(GrowthProfile.referral_code == code)
        )
        if exists.scalar_one_or_none() is None:
            break

    profile = GrowthProfile(
        user_id=user.id,
        referral_code=code,
    )
    session.add(profile)
    await session.flush()
    return profile


async def set_home_country(
    session: AsyncSession,
    user: User,
    code: str,
) -> GrowthProfile:
    profile = await get_growth_profile(session, user)
    profile.home_country_code = code.upper()
    await track_event(
        session,
        user,
        "home_country_set",
        {"country": profile.home_country_code},
    )
    await session.commit()
    return profile


async def register_referral(
    session: AsyncSession,
    referred: User,
    referral_code: str,
) -> bool:
    existing = await session.execute(
        select(Referral.id).where(Referral.referred_id == referred.id)
    )
    if existing.scalar_one_or_none():
        return False

    referrer_growth = await session.execute(
        select(GrowthProfile).where(
            GrowthProfile.referral_code == referral_code
        )
    )
    referrer_growth = referrer_growth.scalar_one_or_none()
    if not referrer_growth or referrer_growth.user_id == referred.id:
        return False

    referrer = await session.get(User, referrer_growth.user_id)
    if not referrer or referrer.is_banned:
        return False

    session.add(
        Referral(
            referrer_id=referrer.id,
            referred_id=referred.id,
            status="pending",
        )
    )
    await track_event(
        session,
        referred,
        "referral_registered",
        {"referrer_user_id": referrer.id},
    )
    await session.commit()
    return True


async def _grant_milestone_if_needed(
    session: AsyncSession,
    referrer: User,
    qualified_count: int,
) -> list[str]:
    rewards: list[str] = []

    async def already(milestone: str) -> bool:
        result = await session.execute(
            select(ReferralReward.id).where(
                ReferralReward.user_id == referrer.id,
                ReferralReward.milestone == milestone,
            )
        )
        return result.scalar_one_or_none() is not None

    if qualified_count >= 3 and not await already("referrals_3"):
        session.add(
            ReferralReward(user_id=referrer.id, milestone="referrals_3")
        )
        await add_consumable(session, referrer, "travel_pass", 1)
        await add_consumable(session, referrer, "spotlight_3h", 1)
        rewards.append("🌎 1 Travel Pass + 🔥 1 Spotlight")

    if qualified_count >= 5 and not await already("referrals_5"):
        session.add(
            ReferralReward(user_id=referrer.id, milestone="referrals_5")
        )
        await add_consumable(session, referrer, "boost_30m_credit", 1)
        await add_consumable(session, referrer, "super_interest", 3)
        rewards.append("🚀 1 Boost + 💘 3 Super Intereses")

    return rewards


async def qualify_referral(
    session: AsyncSession,
    referred: User,
) -> tuple[User | None, list[str]]:
    result = await session.execute(
        select(Referral).where(
            Referral.referred_id == referred.id,
            Referral.status == "pending",
        )
    )
    referral = result.scalar_one_or_none()
    if not referral:
        return None, []

    referral.status = "qualified"
    referral.qualified_at = datetime.now(timezone.utc)

    referrer = await session.get(User, referral.referrer_id)
    if not referrer:
        await session.commit()
        return None, []

    # Cada referido que realmente logra su primer match genera un premio.
    await add_consumable(session, referrer, "super_interest", 1)

    count_result = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == referrer.id,
            Referral.status == "qualified",
        )
    )
    qualified_count = int(count_result.scalar_one())

    milestone_rewards = await _grant_milestone_if_needed(
        session,
        referrer,
        qualified_count,
    )
    await track_event(
        session,
        referrer,
        "referral_qualified",
        {
            "qualified_count": qualified_count,
            "referred_user_id": referred.id,
        },
    )
    await session.commit()

    rewards = ["💘 1 Super Interés"] + milestone_rewards
    return referrer, rewards


async def referral_stats(
    session: AsyncSession,
    user: User,
) -> tuple[int, int]:
    pending = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user.id,
            Referral.status == "pending",
        )
    )
    qualified = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user.id,
            Referral.status == "qualified",
        )
    )
    return int(pending.scalar_one()), int(qualified.scalar_one())


async def activate_travel(
    session: AsyncSession,
    user: User,
    country_code: str,
) -> GrowthProfile:
    profile = await get_growth_profile(session, user)
    now = datetime.now(timezone.utc)
    base = (
        profile.travel_until
        if profile.travel_until and profile.travel_until > now
        else now
    )
    profile.travel_country_code = country_code.upper()
    profile.travel_until = base + timedelta(hours=24)

    await track_event(
        session,
        user,
        "travel_activated",
        {
            "country": profile.travel_country_code,
            "hours": 24,
        },
    )
    await session.commit()
    return profile


async def activate_spotlight(
    session: AsyncSession,
    user: User,
) -> GrowthProfile:
    profile = await get_growth_profile(session, user)
    now = datetime.now(timezone.utc)
    base = (
        profile.spotlight_until
        if profile.spotlight_until and profile.spotlight_until > now
        else now
    )
    profile.spotlight_until = base + timedelta(hours=3)
    await track_event(session, user, "spotlight_activated", {"hours": 3})
    await session.commit()

    ttl = max(
        1,
        int((profile.spotlight_until - datetime.now(timezone.utc)).total_seconds()),
    )
    await redis.set(
        f"visibility:spotlight:{user.telegram_id}",
        "1",
        ex=ttl,
    )
    return profile


async def activate_reward_boost(
    session: AsyncSession,
    user: User,
) -> datetime:
    now = datetime.now(timezone.utc)
    base = user.boost_until if user.boost_until and user.boost_until > now else now
    user.boost_until = base + timedelta(minutes=30)
    await track_event(session, user, "reward_boost_activated", {"minutes": 30})
    await session.commit()
    return user.boost_until


def active_travel_country(profile: GrowthProfile) -> str | None:
    now = datetime.now(timezone.utc)
    if (
        profile.travel_country_code
        and profile.travel_until
        and profile.travel_until > now
    ):
        return profile.travel_country_code
    return None


def spotlight_active(profile: GrowthProfile) -> bool:
    return bool(
        profile.spotlight_until
        and profile.spotlight_until > datetime.now(timezone.utc)
    )


async def received_gift_count(
    session: AsyncSession,
    user: User,
) -> int:
    result = await session.execute(
        select(func.count(VirtualGift.id)).where(
            VirtualGift.recipient_id == user.id
        )
    )
    return int(result.scalar_one())

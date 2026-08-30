from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AcquisitionCampaign,
    CampaignAttribution,
    CampaignTouch,
    Referral,
    User,
)
from app.services.analytics import track_event


CAMPAIGN_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,24}$")


@dataclass(slots=True)
class CampaignStats:
    starts: int
    unique_starts: int
    attributed: int
    completed: int
    qualified: int

    @property
    def attribution_rate(self) -> float:
        return (self.attributed / self.unique_starts * 100.0) if self.unique_starts else 0.0

    @property
    def completion_rate(self) -> float:
        return (self.completed / self.attributed * 100.0) if self.attributed else 0.0

    @property
    def qualified_rate(self) -> float:
        return (self.qualified / self.attributed * 100.0) if self.attributed else 0.0


@dataclass(slots=True)
class ReferralAdminStats:
    total: int
    pending: int
    qualified: int
    completed: int

    @property
    def completion_rate(self) -> float:
        return (self.completed / self.total * 100.0) if self.total else 0.0

    @property
    def qualification_rate(self) -> float:
        return (self.qualified / self.total * 100.0) if self.total else 0.0


def normalize_campaign_code(value: str) -> str:
    return value.strip().lower()


def valid_campaign_code(value: str) -> bool:
    return CAMPAIGN_CODE_RE.fullmatch(value.strip()) is not None


async def create_campaign(
    session: AsyncSession,
    *,
    name: str,
    code: str,
    admin_telegram_id: int,
) -> AcquisitionCampaign:
    code = normalize_campaign_code(code)
    existing = (
        await session.execute(
            select(AcquisitionCampaign.id).where(
                AcquisitionCampaign.code == code
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ValueError("campaign_code_exists")

    campaign = AcquisitionCampaign(
        name=name.strip()[:80],
        code=code,
        active=True,
        created_by_telegram_id=admin_telegram_id,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def get_campaign(
    session: AsyncSession,
    code: str,
) -> AcquisitionCampaign | None:
    return (
        await session.execute(
            select(AcquisitionCampaign).where(
                AcquisitionCampaign.code == normalize_campaign_code(code)
            )
        )
    ).scalar_one_or_none()


async def list_campaigns(
    session: AsyncSession,
    limit: int = 20,
) -> list[AcquisitionCampaign]:
    rows = await session.execute(
        select(AcquisitionCampaign)
        .order_by(AcquisitionCampaign.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars().all())


async def set_campaign_active(
    session: AsyncSession,
    campaign: AcquisitionCampaign,
    active: bool,
) -> None:
    campaign.active = active
    await session.commit()


async def register_campaign_start(
    session: AsyncSession,
    user: User,
    campaign_code: str,
) -> tuple[AcquisitionCampaign | None, bool]:
    """Register a Telegram /start touch and first-touch acquisition attribution.

    Every valid campaign start updates start_count. A user is attributed only if
    onboarding is still incomplete and the account has neither a user referral
    nor another campaign attribution. This prevents double attribution.
    """
    campaign = await get_campaign(session, campaign_code)
    if not campaign or not campaign.active:
        return campaign, False

    now = datetime.now(timezone.utc)
    touch = (
        await session.execute(
            select(CampaignTouch).where(
                CampaignTouch.campaign_id == campaign.id,
                CampaignTouch.user_id == user.id,
            )
        )
    ).scalar_one_or_none()

    if touch:
        touch.start_count += 1
        touch.last_started_at = now
    else:
        session.add(
            CampaignTouch(
                campaign_id=campaign.id,
                user_id=user.id,
                start_count=1,
                first_started_at=now,
                last_started_at=now,
            )
        )

    attributed = False
    if not user.onboarding_completed:
        existing_attr = (
            await session.execute(
                select(CampaignAttribution.id).where(
                    CampaignAttribution.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        existing_referral = (
            await session.execute(
                select(Referral.id).where(Referral.referred_id == user.id)
            )
        ).scalar_one_or_none()

        if not existing_attr and not existing_referral:
            session.add(
                CampaignAttribution(
                    campaign_id=campaign.id,
                    user_id=user.id,
                    status="pending",
                )
            )
            attributed = True

    await track_event(
        session,
        user,
        "campaign_start",
        {
            "campaign_id": campaign.id,
            "campaign_code": campaign.code,
            "attributed": attributed,
        },
    )
    await session.commit()
    return campaign, attributed


async def qualify_campaign_attribution(
    session: AsyncSession,
    user: User,
) -> bool:
    attribution = (
        await session.execute(
            select(CampaignAttribution).where(
                CampaignAttribution.user_id == user.id,
                CampaignAttribution.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if not attribution:
        return False

    attribution.status = "qualified"
    attribution.qualified_at = datetime.now(timezone.utc)
    await track_event(
        session,
        user,
        "campaign_qualified",
        {"campaign_id": attribution.campaign_id},
    )
    await session.flush()
    return True


async def campaign_stats(
    session: AsyncSession,
    campaign: AcquisitionCampaign,
) -> CampaignStats:
    touch_row = await session.execute(
        select(
            func.coalesce(func.sum(CampaignTouch.start_count), 0),
            func.count(CampaignTouch.id),
        ).where(CampaignTouch.campaign_id == campaign.id)
    )
    starts, unique_starts = touch_row.one()

    attributed = int(
        (
            await session.execute(
                select(func.count(CampaignAttribution.id)).where(
                    CampaignAttribution.campaign_id == campaign.id
                )
            )
        ).scalar_one()
        or 0
    )

    completed = int(
        (
            await session.execute(
                select(func.count(CampaignAttribution.id))
                .join(User, User.id == CampaignAttribution.user_id)
                .where(
                    CampaignAttribution.campaign_id == campaign.id,
                    User.onboarding_completed.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )

    qualified = int(
        (
            await session.execute(
                select(func.count(CampaignAttribution.id)).where(
                    CampaignAttribution.campaign_id == campaign.id,
                    CampaignAttribution.status == "qualified",
                )
            )
        ).scalar_one()
        or 0
    )

    return CampaignStats(
        starts=int(starts or 0),
        unique_starts=int(unique_starts or 0),
        attributed=attributed,
        completed=completed,
        qualified=qualified,
    )


async def user_referral_admin_stats(
    session: AsyncSession,
    user: User,
) -> ReferralAdminStats:
    status_rows = (
        await session.execute(
            select(Referral.status, func.count(Referral.id))
            .where(Referral.referrer_id == user.id)
            .group_by(Referral.status)
        )
    ).all()
    status_counts = {str(status): int(count) for status, count in status_rows}
    total = sum(status_counts.values())

    completed = int(
        (
            await session.execute(
                select(func.count(Referral.id))
                .join(User, User.id == Referral.referred_id)
                .where(
                    Referral.referrer_id == user.id,
                    User.onboarding_completed.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )

    return ReferralAdminStats(
        total=total,
        pending=status_counts.get("pending", 0),
        qualified=status_counts.get("qualified", 0),
        completed=completed,
    )

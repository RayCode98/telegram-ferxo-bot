from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalyticsEvent, User


async def track_event(
    session: AsyncSession,
    user: User | None,
    event_name: str,
    metadata: dict | None = None,
) -> None:
    session.add(
        AnalyticsEvent(
            user_id=user.id if user else None,
            event_name=event_name,
            metadata_json=(
                json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
                if metadata
                else None
            ),
        )
    )
    await session.flush()

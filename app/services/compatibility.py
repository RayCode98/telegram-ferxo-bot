from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app.services.matchmaking import age_of, haversine_km
from app.services.social_graph import common_interests, interest_labels


async def compatibility_details(session: AsyncSession, a: User, b: User) -> tuple[int, set[str]]:
    common = await common_interests(session, a, b)
    score = 40
    age_a, age_b = age_of(a.birth_date), age_of(b.birth_date)
    if age_a is not None and age_b is not None:
        score += max(0, 20 - min(abs(age_a-age_b)*2, 20))
    distance = haversine_km(a, b)
    if distance is not None:
        score += 15 if distance <= 5 else 12 if distance <= 15 else 8 if distance <= 50 else 4 if distance <= 100 else 0
    score += min(len(common)*7, 25)
    return min(score, 100), common


async def compatibility_text(session: AsyncSession, a: User, b: User) -> str:
    score, common = await compatibility_details(session, a, b)
    label = "🔥 Muy alta" if score >= 85 else "💚 Alta" if score >= 70 else "✨ Buena" if score >= 55 else "🙂 Compatible"
    lines=[f"💞 Compatibilidad FreXo: <b>{score}% · {label}</b>"]
    if common:
        lines.append("🎯 En común: " + ", ".join(interest_labels(common)[:4]))
    return "\n".join(lines)

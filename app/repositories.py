from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Block,
    ConnectionConsent,
    ConsumableBalance,
    Conversation,
    Interest,
    OrderContext,
    Order,
    Report,
    ReconnectRequest,
    StarTransaction,
    User,
)


async def get_user_by_telegram(
    session: AsyncSession, telegram_id: int
) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    language_code: str | None = None,
) -> User:
    user = await get_user_by_telegram(session, telegram_id)
    if user:
        user.last_seen_at = datetime.now(timezone.utc)
        if language_code:
            user.telegram_language = language_code
        await session.commit()
        return user

    user = User(
        telegram_id=telegram_id,
        telegram_language=language_code,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    return await session.get(User, user_id)


async def are_blocked(session: AsyncSession, a: User, b: User) -> bool:
    result = await session.execute(
        select(Block.id).where(
            or_(
                and_(Block.blocker_id == a.id, Block.blocked_id == b.id),
                and_(Block.blocker_id == b.id, Block.blocked_id == a.id),
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def create_conversation(
    session: AsyncSession, a: User, b: User
) -> Conversation:
    conversation = Conversation(user1_id=a.id, user2_id=b.id)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def end_conversation(
    session: AsyncSession,
    conversation_id: str,
    ended_by_id: str | None,
    reason: str,
) -> None:
    conversation = await session.get(Conversation, conversation_id)
    if not conversation or conversation.status != "active":
        return
    conversation.status = "ended"
    conversation.ended_by_id = ended_by_id
    conversation.ended_reason = reason
    conversation.ended_at = datetime.now(timezone.utc)
    await session.commit()


async def add_block(
    session: AsyncSession, blocker: User, blocked: User
) -> None:
    existing = await session.execute(
        select(Block).where(
            Block.blocker_id == blocker.id,
            Block.blocked_id == blocked.id,
        )
    )
    if existing.scalar_one_or_none():
        return
    session.add(Block(blocker_id=blocker.id, blocked_id=blocked.id))
    await session.commit()


async def add_report(
    session: AsyncSession,
    reporter: User,
    reported: User,
    conversation_id: str | None,
    reason: str,
) -> None:
    session.add(
        Report(
            reporter_id=reporter.id,
            reported_id=reported.id,
            conversation_id=conversation_id,
            reason=reason,
        )
    )
    await session.commit()


async def add_interest(
    session: AsyncSession,
    sender: User,
    target: User,
    conversation_id: str | None,
    is_super: bool = False,
) -> tuple[Interest, bool]:
    result = await session.execute(
        select(Interest).where(
            Interest.from_user_id == sender.id,
            Interest.to_user_id == target.id,
        )
    )
    interest = result.scalar_one_or_none()
    if not interest:
        interest = Interest(
            from_user_id=sender.id,
            to_user_id=target.id,
            conversation_id=conversation_id,
            is_super=is_super,
        )
        session.add(interest)
    elif is_super:
        interest.is_super = True

    reciprocal = await session.execute(
        select(Interest.id).where(
            Interest.from_user_id == target.id,
            Interest.to_user_id == sender.id,
        )
    )
    is_match = reciprocal.scalar_one_or_none() is not None

    await session.commit()
    return interest, is_match


async def get_or_create_balance(
    session: AsyncSession, user: User, code: str
) -> ConsumableBalance:
    result = await session.execute(
        select(ConsumableBalance).where(
            ConsumableBalance.user_id == user.id,
            ConsumableBalance.code == code,
        )
    )
    balance = result.scalar_one_or_none()
    if balance:
        return balance

    balance = ConsumableBalance(user_id=user.id, code=code, quantity=0)
    session.add(balance)
    await session.flush()
    return balance


async def add_consumable(
    session: AsyncSession, user: User, code: str, amount: int = 1
) -> None:
    balance = await get_or_create_balance(session, user, code)
    balance.quantity += amount
    await session.commit()


async def consume(
    session: AsyncSession, user: User, code: str, amount: int = 1
) -> bool:
    balance = await get_or_create_balance(session, user, code)
    if balance.quantity < amount:
        await session.rollback()
        return False
    balance.quantity -= amount
    await session.commit()
    return True


async def get_balance(
    session: AsyncSession, user: User, code: str
) -> int:
    result = await session.execute(
        select(ConsumableBalance.quantity).where(
            ConsumableBalance.user_id == user.id,
            ConsumableBalance.code == code,
        )
    )
    return result.scalar_one_or_none() or 0


async def find_order_by_payload(
    session: AsyncSession, payload: str
) -> Order | None:
    result = await session.execute(
        select(Order).where(Order.invoice_payload == payload)
    )
    return result.scalar_one_or_none()


async def transaction_exists(
    session: AsyncSession, charge_id: str
) -> bool:
    result = await session.execute(
        select(StarTransaction.id).where(
            StarTransaction.telegram_payment_charge_id == charge_id
        )
    )
    return result.scalar_one_or_none() is not None



async def get_connection_consent(
    session: AsyncSession,
    conversation_id: str,
) -> ConnectionConsent:
    result = await session.execute(
        select(ConnectionConsent).where(
            ConnectionConsent.conversation_id == conversation_id
        )
    )
    consent = result.scalar_one_or_none()
    if consent:
        return consent

    consent = ConnectionConsent(conversation_id=conversation_id)
    session.add(consent)
    await session.flush()
    return consent


async def set_profile_reveal_consent(
    session: AsyncSession,
    conversation: Conversation,
    user: User,
) -> bool:
    consent = await get_connection_consent(session, conversation.id)

    if user.id == conversation.user1_id:
        consent.user1_profile_reveal = True
    elif user.id == conversation.user2_id:
        consent.user2_profile_reveal = True
    else:
        raise ValueError("User not in conversation")

    mutual = consent.user1_profile_reveal and consent.user2_profile_reveal
    await session.commit()
    return mutual


async def profile_reveal_is_mutual(
    session: AsyncSession,
    conversation_id: str,
) -> bool:
    consent = await get_connection_consent(session, conversation_id)
    return bool(consent.user1_profile_reveal and consent.user2_profile_reveal)


async def set_contact_share_consent(
    session: AsyncSession,
    conversation: Conversation,
    user: User,
) -> bool:
    consent = await get_connection_consent(session, conversation.id)

    if user.id == conversation.user1_id:
        consent.user1_contact_share = True
    elif user.id == conversation.user2_id:
        consent.user2_contact_share = True
    else:
        raise ValueError("User not in conversation")

    mutual = consent.user1_contact_share and consent.user2_contact_share
    await session.commit()
    return mutual


async def received_interests(
    session: AsyncSession,
    user: User,
    limit: int = 10,
) -> list[tuple[Interest, User]]:
    result = await session.execute(
        select(Interest, User)
        .join(User, User.id == Interest.from_user_id)
        .where(Interest.to_user_id == user.id)
        .order_by(Interest.created_at.desc())
        .limit(limit)
    )
    return list(result.all())


async def received_interest_count(
    session: AsyncSession,
    user: User,
) -> int:
    result = await session.execute(
        select(Interest.id).where(Interest.to_user_id == user.id)
    )
    return len(result.scalars().all())


async def get_last_reconnectable_conversation(
    session: AsyncSession,
    user: User,
) -> tuple[Conversation, User] | None:
    result = await session.execute(
        select(Conversation)
        .where(
            and_(
                Conversation.status == "ended",
                or_(
                    Conversation.user1_id == user.id,
                    Conversation.user2_id == user.id,
                ),
                Conversation.ended_reason.notin_(["blocked", "reported"]),
            )
        )
        .order_by(Conversation.ended_at.desc())
        .limit(20)
    )

    for conversation in result.scalars():
        partner_id = (
            conversation.user2_id
            if conversation.user1_id == user.id
            else conversation.user1_id
        )
        partner = await session.get(User, partner_id)
        if not partner or partner.is_banned:
            continue
        if await are_blocked(session, user, partner):
            continue
        return conversation, partner

    return None


async def create_reconnect_request(
    session: AsyncSession,
    conversation: Conversation,
    requester: User,
    target: User,
) -> ReconnectRequest:
    existing = await session.execute(
        select(ReconnectRequest).where(
            ReconnectRequest.source_conversation_id == conversation.id,
            ReconnectRequest.requester_id == requester.id,
            ReconnectRequest.target_id == target.id,
            ReconnectRequest.status == "pending",
            ReconnectRequest.expires_at > datetime.now(timezone.utc),
        )
    )
    request = existing.scalar_one_or_none()
    if request:
        return request

    request = ReconnectRequest(
        source_conversation_id=conversation.id,
        requester_id=requester.id,
        target_id=target.id,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request



async def get_order_context(
    session: AsyncSession,
    order_id: str,
) -> OrderContext | None:
    result = await session.execute(
        select(OrderContext).where(OrderContext.order_id == order_id)
    )
    return result.scalar_one_or_none()

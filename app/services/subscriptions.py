from __future__ import annotations
from datetime import datetime, timezone
from aiogram.types import BotSubscriptionUpdated, SuccessfulPayment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Order, SubscriptionState, User
from app.repositories import find_order_by_payload

async def get_subscription_state(session: AsyncSession, user: User, product_code: str = "premium_monthly") -> SubscriptionState | None:
    result=await session.execute(select(SubscriptionState).where(SubscriptionState.user_id==user.id,SubscriptionState.product_code==product_code))
    return result.scalar_one_or_none()

async def record_successful_subscription_payment(session: AsyncSession,user: User,order: Order,payment: SuccessfulPayment,expiration: datetime | None) -> SubscriptionState:
    state=await get_subscription_state(session,user,order.product_code)
    if not state:
        state=SubscriptionState(user_id=user.id,product_code=order.product_code); session.add(state)
    state.invoice_payload=order.invoice_payload
    if payment.is_first_recurring or not state.telegram_payment_charge_id:
        state.telegram_payment_charge_id=payment.telegram_payment_charge_id
    state.state="active"; state.auto_renew_enabled=True; state.expiration_at=expiration; state.last_event_at=datetime.now(timezone.utc)
    await session.flush(); return state

async def apply_subscription_update(session: AsyncSession,event: BotSubscriptionUpdated) -> tuple[User | None, SubscriptionState | None]:
    order=await find_order_by_payload(session,event.invoice_payload)
    if not order: return None,None
    user=await session.get(User,order.user_id)
    if not user or user.telegram_id != event.user.id: return None,None
    state=await get_subscription_state(session,user,order.product_code)
    if not state:
        state=SubscriptionState(user_id=user.id,product_code=order.product_code,invoice_payload=event.invoice_payload); session.add(state)
    state.state=event.state; state.auto_renew_enabled=event.state=="active"; state.last_event_at=datetime.now(timezone.utc)
    await session.commit(); return user,state

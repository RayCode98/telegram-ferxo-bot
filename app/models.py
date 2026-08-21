from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    telegram_language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    alias: Mapped[str | None] = mapped_column(String(40), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    seeking_gender: Mapped[str] = mapped_column(String(20), default="any")
    bio: Mapped[str | None] = mapped_column(String(300), nullable=True)
    photo_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    min_age: Mapped[int] = mapped_column(Integer, default=18)
    max_age: Mapped[int] = mapped_column(Integer, default=99)
    max_distance_km: Mapped[int] = mapped_column(Integer, default=100)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    adult_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)

    boost_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    premium_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user1_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    user2_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    ended_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    ended_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_block_pair"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    blocker_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    blocked_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reported_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    reason: Mapped[str] = mapped_column(String(40))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Interest(Base):
    __tablename__ = "interests"
    __table_args__ = (
        UniqueConstraint("from_user_id", "to_user_id", name="uq_interest_pair"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    from_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    to_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    is_super: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(40), index=True)
    stars_amount: Mapped[int] = mapped_column(Integer)
    invoice_payload: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StarTransaction(Base):
    __tablename__ = "star_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    telegram_payment_charge_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )
    stars_amount: Mapped[int] = mapped_column(Integer)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_expiration_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConsumableBalance(Base):
    __tablename__ = "consumable_balances"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_user_consumable"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


Index(
    "ix_conversations_users_status",
    Conversation.user1_id,
    Conversation.user2_id,
    Conversation.status,
)



class ConnectionConsent(Base):
    __tablename__ = "connection_consents"
    __table_args__ = (
        UniqueConstraint("conversation_id", name="uq_connection_consent_conversation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), unique=True, index=True
    )
    user1_profile_reveal: Mapped[bool] = mapped_column(Boolean, default=False)
    user2_profile_reveal: Mapped[bool] = mapped_column(Boolean, default=False)
    user1_contact_share: Mapped[bool] = mapped_column(Boolean, default=False)
    user2_contact_share: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReconnectRequest(Base):
    __tablename__ = "reconnect_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))



class UserRestriction(Base):
    __tablename__ = "user_restrictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    restriction_type: Mapped[str] = mapped_column(String(20), default="ban", index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    target_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    admin_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReportReview(Base):
    __tablename__ = "report_reviews"
    __table_args__ = (
        UniqueConstraint("report_id", name="uq_report_review_report"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("reports.id"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="reviewed", index=True)
    admin_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )



class GrowthProfile(Base):
    __tablename__ = "growth_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    referral_code: Mapped[str] = mapped_column(
        String(24), unique=True, index=True
    )
    home_country_code: Mapped[str | None] = mapped_column(
        String(2), nullable=True, index=True
    )
    travel_country_code: Mapped[str | None] = mapped_column(
        String(2), nullable=True, index=True
    )
    travel_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    spotlight_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_id", name="uq_referral_referred"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    referrer_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    referred_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )
    qualified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    __table_args__ = (
        UniqueConstraint("user_id", "milestone", name="uq_referral_reward"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    milestone: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OrderContext(Base):
    __tablename__ = "order_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), unique=True, index=True
    )
    context_type: Mapped[str] = mapped_column(String(30), index=True)
    target_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    context_value: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )


class VirtualGift(Base):
    __tablename__ = "virtual_gifts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    gift_code: Mapped[str] = mapped_column(String(30), index=True)
    stars_amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    event_name: Mapped[str] = mapped_column(String(50), index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )



class RetentionProfile(Base):
    __tablename__ = "retention_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    streak_count: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_daily_claim_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    total_daily_claims: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

"""Acquisition campaigns and campaign attribution.

Revision ID: 0002_acquisition_campaigns
Revises: 0001_production_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_acquisition_campaigns"
down_revision = "0001_production_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "acquisition_campaigns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_acquisition_campaign_code"),
    )
    op.create_index("ix_acquisition_campaigns_code", "acquisition_campaigns", ["code"], unique=True)
    op.create_index("ix_acquisition_campaigns_active", "acquisition_campaigns", ["active"], unique=False)
    op.create_index("ix_acquisition_campaigns_created_at", "acquisition_campaigns", ["created_at"], unique=False)

    op.create_table(
        "campaign_touches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("start_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["campaign_id"], ["acquisition_campaigns.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "user_id", name="uq_campaign_touch_user"),
    )
    op.create_index("ix_campaign_touches_campaign_id", "campaign_touches", ["campaign_id"], unique=False)
    op.create_index("ix_campaign_touches_user_id", "campaign_touches", ["user_id"], unique=False)
    op.create_index("ix_campaign_touches_first_started_at", "campaign_touches", ["first_started_at"], unique=False)
    op.create_index("ix_campaign_touches_last_started_at", "campaign_touches", ["last_started_at"], unique=False)

    op.create_table(
        "campaign_attributions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["campaign_id"], ["acquisition_campaigns.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_campaign_attribution_user"),
    )
    op.create_index("ix_campaign_attributions_campaign_id", "campaign_attributions", ["campaign_id"], unique=False)
    op.create_index("ix_campaign_attributions_user_id", "campaign_attributions", ["user_id"], unique=True)
    op.create_index("ix_campaign_attributions_status", "campaign_attributions", ["status"], unique=False)
    op.create_index("ix_campaign_attributions_created_at", "campaign_attributions", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_campaign_attributions_created_at", table_name="campaign_attributions")
    op.drop_index("ix_campaign_attributions_status", table_name="campaign_attributions")
    op.drop_index("ix_campaign_attributions_user_id", table_name="campaign_attributions")
    op.drop_index("ix_campaign_attributions_campaign_id", table_name="campaign_attributions")
    op.drop_table("campaign_attributions")

    op.drop_index("ix_campaign_touches_last_started_at", table_name="campaign_touches")
    op.drop_index("ix_campaign_touches_first_started_at", table_name="campaign_touches")
    op.drop_index("ix_campaign_touches_user_id", table_name="campaign_touches")
    op.drop_index("ix_campaign_touches_campaign_id", table_name="campaign_touches")
    op.drop_table("campaign_touches")

    op.drop_index("ix_acquisition_campaigns_created_at", table_name="acquisition_campaigns")
    op.drop_index("ix_acquisition_campaigns_active", table_name="acquisition_campaigns")
    op.drop_index("ix_acquisition_campaigns_code", table_name="acquisition_campaigns")
    op.drop_table("acquisition_campaigns")

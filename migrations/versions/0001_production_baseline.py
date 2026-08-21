"""FreXo v1.9 production baseline.

Bridge for installations created before Alembic. A frozen schema snapshot creates
only missing tables. Future changes must use explicit Alembic revisions.
"""
from alembic import op
from migrations.schema_v19 import Base
revision="0001_production_baseline"
down_revision=None
branch_labels=None
depends_on=None

def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(),checkfirst=True)

def downgrade() -> None:
    # Deliberately non-destructive because this baseline can adopt a live DB.
    pass

import sqlalchemy as sa

from alembic import op

revision = "0005_llm_consent"
down_revision = "0004_rate_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("llm_consent_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("llm_consent_providers", sa.String(100)))


def downgrade() -> None:
    op.drop_column("users", "llm_consent_providers")
    op.drop_column("users", "llm_consent_at")

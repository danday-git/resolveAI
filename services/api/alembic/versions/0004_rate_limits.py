import sqlalchemy as sa

from alembic import op

revision = "0004_rate_limits"
down_revision = "0003_ingestion_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limits",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rate_limits")

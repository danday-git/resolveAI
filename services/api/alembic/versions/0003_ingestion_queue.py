import sqlalchemy as sa

from alembic import op

revision = "0003_ingestion_queue"
down_revision = "0002_auth_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("documents", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("documents", sa.Column("locked_at", sa.DateTime(timezone=True)))
    # The worker polls for unfinished documents; keep that scan off the finished ones.
    op.create_index(
        "ix_documents_queue",
        "documents",
        ["created_at"],
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_queue", "documents")
    for column in ("locked_at", "next_attempt_at", "attempts"):
        op.drop_column("documents", column)

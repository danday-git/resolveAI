import sqlalchemy as sa

from alembic import op

revision = "0006_app_settings"
down_revision = "0005_llm_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("llm_provider", sa.String(20), nullable=False),
        sa.Column("llm_model", sa.String(100), nullable=False),
        sa.Column("openai_api_key", sa.Text()),
        sa.Column("anthropic_api_key", sa.Text()),
        sa.Column("updated_by", sa.String(320)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("app_settings")

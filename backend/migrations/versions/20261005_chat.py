"""Persist authenticated ADK conversations and turn retry results."""

from alembic import op
import sqlalchemy as sa

revision = "20261005_chat"
down_revision = "20261002_mcp"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("busy_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("chat_conversations")

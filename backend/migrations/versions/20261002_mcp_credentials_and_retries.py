"""MCP credential scopes and durable retry records."""

from alembic import op
import sqlalchemy as sa

revision = "20261002_mcp"
down_revision = "814fd2d610d8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sessions", sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("sessions", sa.Column("rate_window", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sessions", sa.Column("rate_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("key", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("actor_id", "operation", "key"),
    )


def downgrade():
    op.drop_table("idempotency_records")
    op.drop_column("sessions", "rate_count")
    op.drop_column("sessions", "rate_window")
    op.drop_column("sessions", "scopes")

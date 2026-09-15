"""transaction dedupe constraint

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15

"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE transactions SET merchant_raw = '' WHERE merchant_raw IS NULL")
    op.alter_column(
        "transactions",
        "merchant_raw",
        existing_type=sa.Text(),
        nullable=False,
        server_default="",
    )
    op.create_index(
        "uq_transactions_dedupe",
        "transactions",
        ["account_id", "posted_date", "amount", "merchant_raw"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_dedupe", table_name="transactions")
    op.alter_column(
        "transactions",
        "merchant_raw",
        existing_type=sa.Text(),
        nullable=True,
        server_default=None,
    )

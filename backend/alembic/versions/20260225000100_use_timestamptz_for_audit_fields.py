"""use timestamptz for audit fields

Revision ID: 20260225000100
Revises: 20260224100000
Create Date: 2026-02-25 00:01:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260225000100"
down_revision: Union[str, Sequence[str], None] = "20260224100000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _to_timestamptz(table_name: str, column_name: str, nullable: bool) -> None:
    op.alter_column(
        table_name=table_name,
        column_name=column_name,
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        nullable=nullable,
        postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
    )


def _to_timestamp(table_name: str, column_name: str, nullable: bool) -> None:
    op.alter_column(
        table_name=table_name,
        column_name=column_name,
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        nullable=nullable,
        postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
    )


def upgrade() -> None:
    _to_timestamptz("experiments", "created_at", nullable=False)
    _to_timestamptz("raters", "session_start", nullable=False)
    _to_timestamptz("raters", "session_end", nullable=True)
    _to_timestamptz("ratings", "time_started", nullable=False)
    _to_timestamptz("ratings", "time_submitted", nullable=False)
    _to_timestamptz("uploads", "uploaded_at", nullable=False)


def downgrade() -> None:
    _to_timestamp("uploads", "uploaded_at", nullable=False)
    _to_timestamp("ratings", "time_submitted", nullable=False)
    _to_timestamp("ratings", "time_started", nullable=False)
    _to_timestamp("raters", "session_end", nullable=True)
    _to_timestamp("raters", "session_start", nullable=False)
    _to_timestamp("experiments", "created_at", nullable=False)

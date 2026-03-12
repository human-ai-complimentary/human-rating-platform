"""add_study_rounds

Revision ID: 20260305032434
Revises: faf2ebe67bd9
Create Date: 2026-03-05 03:24:36.430448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = "20260305032434"
down_revision: Union[str, Sequence[str], None] = "faf2ebe67bd9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiment_rounds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("prolific_study_id", sa.String(length=128), nullable=False),
        sa.Column("prolific_study_status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("estimated_completion_time", sa.Integer(), nullable=False),
        sa.Column("reward", sa.Integer(), nullable=False),
        sa.Column("device_compatibility", sa.String(length=256), nullable=False),
        sa.Column("places_requested", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_id",
            "round_number",
            name="uq_experiment_round_number",
        ),
    )


def downgrade() -> None:
    op.drop_table("experiment_rounds")

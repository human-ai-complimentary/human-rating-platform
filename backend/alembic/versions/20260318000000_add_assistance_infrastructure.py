"""add_assistance_infrastructure

Revision ID: 20260318000000
Revises: faf2ebe67bd9
Create Date: 2026-03-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260318000000"
down_revision: Union[str, Sequence[str], None] = "faf2ebe67bd9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add assistance configuration fields to experiments
    op.add_column(
        "experiments",
        sa.Column(
            "assistance_method",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
    )
    op.add_column(
        "experiments",
        sa.Column("assistance_params", sa.Text(), nullable=True),
    )

    # Create assistance_sessions table
    op.create_table(
        "assistance_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rater_id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("method_name", sa.String(length=64), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "is_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rater_id"], ["raters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("assistance_sessions")
    op.drop_column("experiments", "assistance_params")
    op.drop_column("experiments", "assistance_method")

"""add_question_parent_id

Revision ID: 20260505000000
Revises: 20260318000000
Create Date: 2026-05-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260505000000"
down_revision: Union[str, Sequence[str], None] = "20260318000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("parent_question_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_questions_parent_question_id",
        "questions",
        "questions",
        ["parent_question_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_questions_parent_question_id",
        "questions",
        type_="foreignkey",
    )
    op.drop_column("questions", "parent_question_id")

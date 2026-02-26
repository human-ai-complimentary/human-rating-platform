"""add string length constraints

Revision ID: 20260225000200
Revises: 20260225000100
Create Date: 2026-02-25 00:02:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260225000200"
down_revision: Union[str, Sequence[str], None] = "20260225000100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "experiments",
        "name",
        existing_type=sa.String(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "experiments",
        "prolific_completion_url",
        existing_type=sa.String(),
        type_=sa.String(length=2048),
        existing_nullable=True,
    )
    op.alter_column(
        "questions",
        "question_id",
        existing_type=sa.String(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "questions",
        "question_type",
        existing_type=sa.String(),
        type_=sa.String(length=16),
        existing_nullable=False,
        existing_server_default=sa.text("'MC'"),
    )
    op.alter_column(
        "raters",
        "prolific_id",
        existing_type=sa.String(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "raters",
        "study_id",
        existing_type=sa.String(),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
    op.alter_column(
        "raters",
        "session_id",
        existing_type=sa.String(),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
    op.alter_column(
        "uploads",
        "filename",
        existing_type=sa.String(),
        type_=sa.String(length=512),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "uploads",
        "filename",
        existing_type=sa.String(length=512),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.alter_column(
        "raters",
        "session_id",
        existing_type=sa.String(length=128),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "raters",
        "study_id",
        existing_type=sa.String(length=128),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "raters",
        "prolific_id",
        existing_type=sa.String(length=64),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.alter_column(
        "questions",
        "question_type",
        existing_type=sa.String(length=16),
        type_=sa.String(),
        existing_nullable=False,
        existing_server_default=sa.text("'MC'"),
    )
    op.alter_column(
        "questions",
        "question_id",
        existing_type=sa.String(length=255),
        type_=sa.String(),
        existing_nullable=False,
    )
    op.alter_column(
        "experiments",
        "prolific_completion_url",
        existing_type=sa.String(length=2048),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "experiments",
        "name",
        existing_type=sa.String(length=255),
        type_=sa.String(),
        existing_nullable=False,
    )

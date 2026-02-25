"""initial sqlmodel parity

Revision ID: 20260224100000
Revises:
Create Date: 2026-02-24 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260224100000"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "num_ratings_per_question",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column("prolific_completion_url", sa.String(), nullable=True),
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.String(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("gt_answer", sa.Text(), nullable=True),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column(
            "question_type",
            sa.String(),
            nullable=False,
            server_default=sa.text("'MC'"),
        ),
        sa.Column("extra_data", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "raters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("prolific_id", sa.String(), nullable=False),
        sa.Column("study_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column(
            "session_start",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("session_end", sa.DateTime(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "ratings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("rater_id", sa.Integer(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("time_started", sa.DateTime(), nullable=False),
        sa.Column(
            "time_submitted",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rater_id"], ["raters.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "uploads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
    )

    op.create_unique_constraint(
        "uq_rater_prolific_experiment",
        "raters",
        ["prolific_id", "experiment_id"],
    )
    op.create_unique_constraint(
        "uq_rating_question_rater",
        "ratings",
        ["question_id", "rater_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_rating_question_rater", "ratings", type_="unique")
    op.drop_constraint("uq_rater_prolific_experiment", "raters", type_="unique")

    op.drop_table("uploads")
    op.drop_table("ratings")
    op.drop_table("raters")
    op.drop_table("questions")
    op.drop_table("experiments")

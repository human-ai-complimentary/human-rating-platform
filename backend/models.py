"""Database models using SQLModel.

These models are the source of truth for the schema. Database migrations
are generated from these definitions using `alembic revision --autogenerate`,
then reviewed and committed. See README Migrations section for workflow.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel

SESSION_DURATION_MINUTES = 60  # Hard-coded 1 hour per rater


class Experiment(SQLModel, table=True):
    __tablename__ = "experiments"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(255), nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    num_ratings_per_question: int = Field(
        default=3,
        sa_column=Column(Integer, nullable=False, server_default=text("3")),
    )
    prolific_completion_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2048), nullable=True),
    )


class Question(SQLModel, table=True):
    __tablename__ = "questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    experiment_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    question_id: str = Field(sa_column=Column(String(255), nullable=False))
    question_text: str = Field(sa_column=Column(Text, nullable=False))
    gt_answer: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    options: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    question_type: str = Field(
        default="MC",
        sa_column=Column(String(16), nullable=False, server_default=text("'MC'")),
    )
    extra_data: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))


class Rater(SQLModel, table=True):
    __tablename__ = "raters"
    __table_args__ = (
        UniqueConstraint(
            "prolific_id",
            "experiment_id",
            name="uq_rater_prolific_experiment",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    prolific_id: str = Field(sa_column=Column(String(64), nullable=False))
    study_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(128), nullable=True),
    )  # Prolific STUDY_ID
    session_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(128), nullable=True),
    )  # Prolific SESSION_ID
    experiment_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    session_start: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    session_end: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )


class Rating(SQLModel, table=True):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "rater_id",
            name="uq_rating_question_rater",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    rater_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("raters.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    answer: str = Field(sa_column=Column(Text, nullable=False))
    confidence: int = Field(sa_column=Column(Integer, nullable=False))
    time_started: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    time_submitted: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )


class Upload(SQLModel, table=True):
    __tablename__ = "uploads"

    id: Optional[int] = Field(default=None, primary_key=True)
    experiment_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    filename: str = Field(sa_column=Column(String(512), nullable=False))
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    question_count: int = Field(sa_column=Column(Integer, nullable=False))

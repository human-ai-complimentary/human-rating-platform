from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Experiment, Question, Rating, Rater
from schemas import ExperimentCreate, ExperimentResponse
from .mappers import build_experiment_response
from .queries import fetch_experiment_or_404, fetch_total_questions_for_experiment

logger = logging.getLogger(__name__)


async def create_experiment(
    payload: ExperimentCreate,
    db: AsyncSession,
) -> ExperimentResponse:
    db_experiment = Experiment(
        name=payload.name,
        num_ratings_per_question=payload.num_ratings_per_question,
        prolific_completion_url=payload.prolific_completion_url,
    )
    db.add(db_experiment)
    await db.commit()
    await db.refresh(db_experiment)

    logger.info("Created experiment: id=%s, name=%s", db_experiment.id, db_experiment.name)
    return build_experiment_response(db_experiment, question_count=0, rating_count=0)


async def list_experiments(
    skip: int,
    limit: int,
    db: AsyncSession,
) -> list[ExperimentResponse]:
    question_counts = (
        select(
            Question.experiment_id,
            func.count(Question.id).label("question_count"),
        )
        .group_by(Question.experiment_id)
        .subquery()
    )

    rating_counts = (
        select(
            Question.experiment_id,
            func.count(Rating.id).label("rating_count"),
        )
        .join(Rating, Rating.question_id == Question.id)
        .group_by(Question.experiment_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(
                Experiment,
                func.coalesce(question_counts.c.question_count, 0).label("question_count"),
                func.coalesce(rating_counts.c.rating_count, 0).label("rating_count"),
            )
            .outerjoin(question_counts, Experiment.id == question_counts.c.experiment_id)
            .outerjoin(rating_counts, Experiment.id == rating_counts.c.experiment_id)
            .order_by(Experiment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    ).all()

    return [
        build_experiment_response(
            experiment,
            question_count=int(question_count or 0),
            rating_count=int(rating_count or 0),
        )
        for experiment, question_count, rating_count in rows
    ]


async def delete_experiment(
    experiment_id: int,
    db: AsyncSession,
) -> dict[str, str]:
    experiment = await fetch_experiment_or_404(experiment_id, db)
    experiment_name = experiment.name

    await db.delete(experiment)
    await db.commit()

    logger.info("Deleted experiment: id=%s, name=%s", experiment_id, experiment_name)
    return {"message": "Experiment deleted successfully"}


async def get_experiment_stats(
    experiment_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    experiment = await fetch_experiment_or_404(experiment_id, db)

    total_questions = await fetch_total_questions_for_experiment(experiment_id, db)
    total_ratings = (
        await db.execute(
            select(func.count(Rating.id))
            .join(Question, Rating.question_id == Question.id)
            .where(Question.experiment_id == experiment_id)
        )
    ).scalar_one()
    total_raters = (
        await db.execute(select(func.count(Rater.id)).where(Rater.experiment_id == experiment_id))
    ).scalar_one()

    questions_complete = len(
        (
            await db.execute(
                select(Question.id)
                .join(Rating, Rating.question_id == Question.id)
                .where(Question.experiment_id == experiment_id)
                .group_by(Question.id)
                .having(func.count(Rating.id) >= experiment.num_ratings_per_question)
            )
        ).all()
    )

    return {
        "experiment_name": experiment.name,
        "total_questions": total_questions,
        "questions_complete": int(questions_complete),
        "total_ratings": int(total_ratings or 0),
        "total_raters": int(total_raters or 0),
        "target_ratings_per_question": experiment.num_ratings_per_question,
    }

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Experiment, Question, Rating, Rater


async def fetch_experiment_or_404(experiment_id: int, db: AsyncSession) -> Experiment:
    experiment = (
        await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    ).scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


async def fetch_ratings_for_experiment(
    experiment_id: int,
    db: AsyncSession,
) -> list[tuple[Rating, Question, Rater]]:
    return (
        await db.execute(
            select(Rating, Question, Rater)
            .join(Question, Rating.question_id == Question.id)
            .join(Rater, Rating.rater_id == Rater.id)
            .where(Question.experiment_id == experiment_id)
        )
    ).all()


async def fetch_total_questions_for_experiment(
    experiment_id: int,
    db: AsyncSession,
) -> int:
    total_questions = (
        await db.execute(
            select(func.count(Question.id)).where(Question.experiment_id == experiment_id)
        )
    ).scalar_one()
    return int(total_questions or 0)

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .mappers import build_analytics_payload, build_empty_analytics_payload
from .queries import (
    fetch_experiment_or_404,
    fetch_ratings_for_experiment,
    fetch_total_questions_for_experiment,
)


async def get_experiment_analytics(
    experiment_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    experiment = await fetch_experiment_or_404(experiment_id, db)
    ratings = await fetch_ratings_for_experiment(experiment_id, db)
    total_questions = await fetch_total_questions_for_experiment(experiment_id, db)

    if not ratings:
        return build_empty_analytics_payload(
            experiment_name=experiment.name,
            total_questions=total_questions,
        )

    return build_analytics_payload(
        experiment_name=experiment.name,
        total_questions=total_questions,
        ratings=ratings,
    )

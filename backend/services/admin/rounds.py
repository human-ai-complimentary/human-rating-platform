"""Pilot study and study round management.

Implements the iterative pilot → main round workflow:
1. Run a small pilot study to measure actual time-per-question.
2. Use the timing data to calculate how many rater-hours remain.
3. Launch a main round requesting 80% of remaining hours.
4. Repeat until all questions have the required rating count.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

from config import get_settings
from fastapi import HTTPException
from models import Experiment, ProlificStudyStatus, Question, StudyRound
from schemas import (
    PilotStudyCreate,
    RecommendationResponse,
    StudyRoundCreate,
    StudyRoundResponse,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .mappers import PROLIFIC_STUDY_URL_TEMPLATE
from .prolific import build_completion_url, create_study, generate_completion_code
from .queries import fetch_experiment_or_404, fetch_ratings_for_experiment

logger = logging.getLogger(__name__)

SESSION_DURATION_SECONDS = 3600  # 1 hour per Prolific place
ROUND_BUFFER_FACTOR = 0.8


def _build_round_response(round_: StudyRound) -> StudyRoundResponse:
    return StudyRoundResponse(
        id=round_.id,
        round_number=round_.round_number,
        is_pilot=round_.is_pilot,
        prolific_study_id=round_.prolific_study_id,
        prolific_study_status=round_.prolific_study_status,
        places_requested=round_.places_requested,
        created_at=round_.created_at,
        prolific_study_url=PROLIFIC_STUDY_URL_TEMPLATE.format(
            study_id=round_.prolific_study_id
        ),
    )


async def _create_prolific_study_for_experiment(
    experiment: Experiment,
    *,
    description: str,
    estimated_completion_time: int,
    reward: int,
    places: int,
    device_compatibility: list[str],
    settings: Any,
) -> dict:
    completion_code = generate_completion_code()
    completion_url = build_completion_url(completion_code)

    app_settings = get_settings()
    external_study_url = (
        f"{app_settings.app.site_url}/rate"
        f"?experiment_id={experiment.id}"
        f"&PROLIFIC_PID={{{{%PROLIFIC_PID%}}}}"
        f"&STUDY_ID={{{{%STUDY_ID%}}}}"
        f"&SESSION_ID={{{{%SESSION_ID%}}}}"
    )

    result = await create_study(
        settings=settings,
        name=experiment.name,
        description=description,
        external_study_url=external_study_url,
        estimated_completion_time=estimated_completion_time,
        reward=reward,
        total_available_places=places,
        completion_code=completion_code,
        device_compatibility=device_compatibility,
    )

    # Store the completion URL on the experiment (for raters)
    experiment.prolific_completion_url = completion_url
    experiment.prolific_completion_code = completion_code

    return result


async def calculate_recommendation(
    experiment_id: int,
    db: AsyncSession,
) -> RecommendationResponse:
    experiment = await fetch_experiment_or_404(experiment_id, db)
    ratings = await fetch_ratings_for_experiment(experiment_id, db)

    if not ratings:
        return RecommendationResponse(
            avg_time_per_question_seconds=0.0,
            remaining_rating_actions=0,
            total_hours_remaining=0.0,
            recommended_places=0,
            is_complete=False,
        )

    # Compute average time per rating action
    times = [
        (rating.time_submitted - rating.time_started).total_seconds()
        for rating, _, _ in ratings
    ]
    avg_time = sum(times) / len(times)

    # Count remaining rating actions per question
    rating_counts: dict[int, int] = {}
    for rating, question, _ in ratings:
        rating_counts[question.id] = rating_counts.get(question.id, 0) + 1

    # Get all question IDs for this experiment
    all_question_ids = (
        await db.execute(
            select(Question.id).where(Question.experiment_id == experiment_id)
        )
    ).scalars().all()

    target = experiment.num_ratings_per_question
    remaining_actions = sum(
        max(0, target - rating_counts.get(qid, 0)) for qid in all_question_ids
    )

    is_complete = remaining_actions == 0
    total_hours = (remaining_actions * avg_time) / SESSION_DURATION_SECONDS
    recommended_places = math.ceil(total_hours * ROUND_BUFFER_FACTOR) if not is_complete else 0

    return RecommendationResponse(
        avg_time_per_question_seconds=round(avg_time, 2),
        remaining_rating_actions=remaining_actions,
        total_hours_remaining=round(total_hours, 2),
        recommended_places=recommended_places,
        is_complete=is_complete,
    )


async def run_pilot_study(
    experiment_id: int,
    payload: PilotStudyCreate,
    db: AsyncSession,
) -> StudyRoundResponse:
    settings = get_settings()
    if not settings.prolific.enabled:
        raise HTTPException(status_code=400, detail="Prolific integration is not enabled")

    experiment = await fetch_experiment_or_404(experiment_id, db)

    # Prevent launching a second pilot
    existing_pilot = (
        await db.execute(
            select(StudyRound).where(
                StudyRound.experiment_id == experiment_id,
                StudyRound.is_pilot == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if existing_pilot:
        raise HTTPException(
            status_code=400,
            detail="A pilot study has already been run for this experiment",
        )

    try:
        result = await _create_prolific_study_for_experiment(
            experiment,
            description=payload.description,
            estimated_completion_time=payload.estimated_completion_time,
            reward=payload.reward,
            places=payload.pilot_hours,
            device_compatibility=payload.device_compatibility,
            settings=settings.prolific,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create pilot Prolific study for experiment %s", experiment_id)
        raise HTTPException(
            status_code=502,
            detail="Failed to create study on Prolific. Please check your API token and try again.",
        )

    # Persist Prolific config on experiment for reuse in subsequent rounds
    experiment.prolific_description = payload.description
    experiment.prolific_reward = payload.reward
    experiment.prolific_estimated_completion_time = payload.estimated_completion_time
    experiment.prolific_device_compatibility = json.dumps(payload.device_compatibility)
    experiment.prolific_study_id = result["id"]
    experiment.prolific_study_status = ProlificStudyStatus(result.get("status", "UNPUBLISHED"))

    round_ = StudyRound(
        experiment_id=experiment_id,
        round_number=0,
        is_pilot=True,
        prolific_study_id=result["id"],
        prolific_study_status=ProlificStudyStatus(result.get("status", "UNPUBLISHED")),
        places_requested=payload.pilot_hours,
    )
    db.add(round_)
    await db.commit()
    await db.refresh(round_)

    logger.info(
        "Created pilot study for experiment %s: Prolific study_id=%s, places=%s",
        experiment_id,
        result["id"],
        payload.pilot_hours,
    )
    return _build_round_response(round_)


async def run_study_round(
    experiment_id: int,
    payload: StudyRoundCreate,
    db: AsyncSession,
) -> StudyRoundResponse:
    settings = get_settings()
    if not settings.prolific.enabled:
        raise HTTPException(status_code=400, detail="Prolific integration is not enabled")

    experiment = await fetch_experiment_or_404(experiment_id, db)

    # Require a pilot to have been run first
    pilot = (
        await db.execute(
            select(StudyRound).where(
                StudyRound.experiment_id == experiment_id,
                StudyRound.is_pilot == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not pilot:
        raise HTTPException(
            status_code=400,
            detail="Run a pilot study first before launching a main round",
        )

    # Require pilot config to be stored
    if not all([
        experiment.prolific_description,
        experiment.prolific_reward is not None,
        experiment.prolific_estimated_completion_time is not None,
    ]):
        raise HTTPException(
            status_code=400,
            detail="Pilot Prolific config is missing from this experiment",
        )

    device_compatibility = (
        json.loads(experiment.prolific_device_compatibility)
        if experiment.prolific_device_compatibility
        else ["desktop"]
    )

    # Compute next round number
    max_round = (
        await db.execute(
            select(func.max(StudyRound.round_number)).where(
                StudyRound.experiment_id == experiment_id
            )
        )
    ).scalar_one_or_none()
    next_round_number = (max_round or 0) + 1

    try:
        result = await _create_prolific_study_for_experiment(
            experiment,
            description=experiment.prolific_description,
            estimated_completion_time=experiment.prolific_estimated_completion_time,
            reward=experiment.prolific_reward,
            places=payload.places,
            device_compatibility=device_compatibility,
            settings=settings.prolific,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Failed to create round %s Prolific study for experiment %s",
            next_round_number,
            experiment_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to create study on Prolific. Please check your API token and try again.",
        )

    experiment.prolific_study_id = result["id"]
    experiment.prolific_study_status = ProlificStudyStatus(result.get("status", "UNPUBLISHED"))

    round_ = StudyRound(
        experiment_id=experiment_id,
        round_number=next_round_number,
        is_pilot=False,
        prolific_study_id=result["id"],
        prolific_study_status=ProlificStudyStatus(result.get("status", "UNPUBLISHED")),
        places_requested=payload.places,
    )
    db.add(round_)
    await db.commit()
    await db.refresh(round_)

    logger.info(
        "Created round %s for experiment %s: Prolific study_id=%s, places=%s",
        next_round_number,
        experiment_id,
        result["id"],
        payload.places,
    )
    return _build_round_response(round_)


async def list_study_rounds(
    experiment_id: int,
    db: AsyncSession,
) -> list[StudyRoundResponse]:
    await fetch_experiment_or_404(experiment_id, db)
    rounds = (
        await db.execute(
            select(StudyRound)
            .where(StudyRound.experiment_id == experiment_id)
            .order_by(StudyRound.round_number)
        )
    ).scalars().all()
    return [_build_round_response(r) for r in rounds]

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import Rating, Rater
from schemas import (
    QuestionResponse,
    RaterStartResponse,
    RatingResponse,
    RatingSubmit,
    SessionStatusResponse,
)
from .mappers import (
    build_question_response,
    build_rater_start_response,
    build_session_end_time,
)
from .queries import (
    fetch_eligible_questions_with_counts,
    fetch_existing_rater_for_experiment,
    fetch_existing_rating,
    fetch_experiment_or_404,
    fetch_question_or_404,
    fetch_rated_question_ids,
    fetch_rater_completed_count,
    fetch_rater_or_404,
)
from .selectors import build_question_selection_groups, build_selected_question
from .validators import (
    validate_existing_rater_can_resume,
    validate_question_belongs_to_rater_experiment,
    validate_rating_confidence,
    validate_rater_marked_active,
    validate_rater_session_is_active,
)

logger = logging.getLogger(__name__)


def _normalize_to_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def start_session(
    *,
    experiment_id: int,
    prolific_pid: str,
    study_id: Optional[str],
    session_id: Optional[str],
    db: AsyncSession,
) -> RaterStartResponse:
    experiment = await fetch_experiment_or_404(experiment_id, db)

    existing_rater = await fetch_existing_rater_for_experiment(
        prolific_id=prolific_pid,
        experiment_id=experiment_id,
        db=db,
    )

    if existing_rater:
        validate_existing_rater_can_resume(existing_rater)
        return build_rater_start_response(
            rater_id=existing_rater.id,
            session_start=existing_rater.session_start,
            experiment_name=experiment.name,
            completion_url=experiment.prolific_completion_url,
        )

    rater = Rater(
        prolific_id=prolific_pid,
        study_id=study_id,
        session_id=session_id,
        experiment_id=experiment_id,
        session_start=datetime.now(UTC),
        is_active=True,
    )
    db.add(rater)
    await db.commit()
    await db.refresh(rater)

    logger.info(
        "New rater session: rater_id=%s, prolific_id=%s, experiment_id=%s",
        rater.id,
        prolific_pid,
        experiment_id,
    )

    return build_rater_start_response(
        rater_id=rater.id,
        session_start=rater.session_start,
        experiment_name=experiment.name,
        completion_url=experiment.prolific_completion_url,
    )


async def get_next_question(
    *,
    rater_id: int,
    db: AsyncSession,
) -> Optional[QuestionResponse]:
    rater = await fetch_rater_or_404(rater_id, db)
    experiment = await fetch_experiment_or_404(rater.experiment_id, db)

    await validate_rater_session_is_active(rater, db)

    rated_question_ids = await fetch_rated_question_ids(rater_id, db)
    eligible_questions = await fetch_eligible_questions_with_counts(
        experiment_id=rater.experiment_id,
        rated_question_ids=rated_question_ids,
        db=db,
    )

    under_quota, at_quota = build_question_selection_groups(
        eligible_questions=eligible_questions,
        target_ratings_per_question=experiment.num_ratings_per_question,
    )
    selected = build_selected_question(
        under_quota=under_quota,
        at_quota=at_quota,
    )

    if selected is None:
        return None
    return build_question_response(selected)


async def submit_rating(
    *,
    payload: RatingSubmit,
    rater_id: int,
    db: AsyncSession,
) -> RatingResponse:
    rater = await fetch_rater_or_404(rater_id, db)
    validate_rater_marked_active(rater)

    question = await fetch_question_or_404(payload.question_id, db)
    validate_question_belongs_to_rater_experiment(
        question_experiment_id=question.experiment_id,
        rater_experiment_id=rater.experiment_id,
    )

    existing_rating = await fetch_existing_rating(
        rater_id=rater_id,
        question_id=payload.question_id,
        db=db,
    )
    if existing_rating:
        raise HTTPException(status_code=400, detail="Already rated this question")

    validate_rating_confidence(payload.confidence)

    db_rating = Rating(
        question_id=payload.question_id,
        rater_id=rater_id,
        answer=payload.answer,
        confidence=payload.confidence,
        time_started=_normalize_to_utc_aware(payload.time_started),
        time_submitted=datetime.now(UTC),
    )
    db.add(db_rating)
    await db.commit()
    await db.refresh(db_rating)

    logger.info(
        "Rating submitted: rating_id=%s, rater_id=%s, question_id=%s",
        db_rating.id,
        rater_id,
        payload.question_id,
    )

    return RatingResponse(id=db_rating.id, success=True)


async def get_session_status(
    *,
    rater_id: int,
    db: AsyncSession,
) -> SessionStatusResponse:
    rater = await fetch_rater_or_404(rater_id, db)

    time_remaining = (
        build_session_end_time(rater.session_start) - datetime.now(UTC)
    ).total_seconds()
    if time_remaining <= 0:
        rater.is_active = False
        rater.session_end = datetime.now(UTC)
        await db.commit()
        time_remaining = 0

    completed = await fetch_rater_completed_count(rater_id, db)

    return SessionStatusResponse(
        is_active=rater.is_active,
        time_remaining_seconds=max(0, int(time_remaining)),
        questions_completed=completed,
    )


async def end_session(
    *,
    rater_id: int,
    db: AsyncSession,
) -> dict[str, str]:
    rater = await fetch_rater_or_404(rater_id, db)

    rater.is_active = False
    rater.session_end = datetime.now(UTC)
    await db.commit()

    return {"message": "Session ended successfully"}

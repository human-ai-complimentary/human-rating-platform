from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ProlificMode, get_settings
from models import Experiment, StudyRound
from schemas import FakeStudyDetailResponse

from .prolific import build_external_study_url


async def get_fake_study_detail(
    *,
    study_id: str,
    db: AsyncSession,
) -> FakeStudyDetailResponse:
    settings = get_settings()
    if settings.prolific.mode != ProlificMode.FAKE:
        raise HTTPException(status_code=404, detail="Fake study not found")

    row = (
        await db.execute(
            select(StudyRound, Experiment)
            .join(Experiment, StudyRound.experiment_id == Experiment.id)
            .where(StudyRound.prolific_study_id == study_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Fake study not found")

    round_, experiment = row
    device_compatibility = (
        json.loads(experiment.prolific_device_compatibility)
        if experiment.prolific_device_compatibility
        else ["desktop"]
    )

    return FakeStudyDetailResponse(
        study_id=round_.prolific_study_id,
        study_status=round_.prolific_study_status,
        experiment_id=experiment.id,
        experiment_name=experiment.name,
        round_number=round_.round_number,
        is_pilot=round_.is_pilot,
        places_requested=round_.places_requested,
        description=experiment.prolific_description or "",
        estimated_completion_time=experiment.prolific_estimated_completion_time or 0,
        reward=experiment.prolific_reward or 0,
        device_compatibility=device_compatibility,
        external_study_url=build_external_study_url(
            site_url=settings.app.site_url,
            experiment_id=experiment.id,
        ),
        completion_url=experiment.prolific_completion_url,
        created_at=round_.created_at,
    )

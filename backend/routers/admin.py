from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from schemas import ExperimentCreate, ExperimentResponse
from services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/experiments", response_model=ExperimentResponse)
async def create_experiment(
    experiment: ExperimentCreate,
    db: AsyncSession = Depends(get_session),
):
    return await admin_service.create_experiment(experiment, db)


@router.get("/experiments", response_model=list[ExperimentResponse])
async def list_experiments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_session),
):
    return await admin_service.list_experiments(skip=skip, limit=limit, db=db)


@router.post("/experiments/{experiment_id}/upload")
async def upload_questions(
    experiment_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
):
    return await admin_service.upload_questions_csv(
        experiment_id=experiment_id,
        file=file,
        db=db,
    )


@router.get("/experiments/{experiment_id}/uploads")
async def list_uploads(
    experiment_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_session),
):
    return await admin_service.list_uploads(
        experiment_id=experiment_id,
        skip=skip,
        limit=limit,
        db=db,
    )


@router.get("/experiments/{experiment_id}/export")
async def export_ratings(
    experiment_id: int,
    db: AsyncSession = Depends(get_session),
):
    return StreamingResponse(
        admin_service.stream_export_csv_chunks(experiment_id=experiment_id, db=db),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename={admin_service.build_export_filename(experiment_id)}"
            )
        },
    )


@router.delete("/experiments/{experiment_id}")
async def delete_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_session),
):
    return await admin_service.delete_experiment(experiment_id=experiment_id, db=db)


@router.get("/experiments/{experiment_id}/stats")
async def get_experiment_stats(
    experiment_id: int,
    db: AsyncSession = Depends(get_session),
):
    return await admin_service.get_experiment_stats(experiment_id=experiment_id, db=db)


@router.get("/experiments/{experiment_id}/analytics")
async def get_experiment_analytics(
    experiment_id: int,
    db: AsyncSession = Depends(get_session),
):
    return await admin_service.get_experiment_analytics(experiment_id=experiment_id, db=db)

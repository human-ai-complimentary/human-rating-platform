from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from database import get_session
from models import InteractionLog
from questions import QUESTIONS
from schemas import (
    ChatRequest,
    ChatResponse,
    DelegationSubmit,
    DelegationSubmitResponse,
    DelegationTaskResponse,
    SubtaskData,
)
from services.openai_client import get_chat_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delegation", tags=["delegation"])


@router.get("/task/{task_id}", response_model=DelegationTaskResponse)
async def get_task(task_id: str):
    if task_id not in QUESTIONS:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    task = QUESTIONS[task_id]
    return DelegationTaskResponse(
        id=task["id"],
        instructions=task["instructions"],
        question=task["question"],
        delegation_data=[SubtaskData(**s) for s in task["delegation_data"]],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_session)):
    task = QUESTIONS.get(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {request.task_id} not found")

    try:
        messages = [{"role": m.role, "content": m.content} for m in request.message_history]
        ai_response = get_chat_response(messages, task["question"], task["instructions"])
    except Exception:
        logger.exception("OpenAI error for task_id=%s", request.task_id)
        ai_response = "Sorry, I encountered an error processing your request. Please try again."

    full_conversation = [m.model_dump() for m in request.message_history]
    full_conversation.append({"role": "assistant", "content": ai_response})

    # Upsert: one log entry per participant+task
    stmt = (
        select(InteractionLog)
        .where(InteractionLog.prolific_pid == request.pid)
        .where(InteractionLog.task_id == request.task_id)
        .where(InteractionLog.condition == "chat")
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.payload = json.dumps(full_conversation)
        db.add(existing)
    else:
        db.add(
            InteractionLog(
                prolific_pid=request.pid,
                experiment_id=request.experiment_id,
                task_id=request.task_id,
                condition="chat",
                interaction_type="chat_message",
                payload=json.dumps(full_conversation),
            )
        )
    await db.commit()

    return ChatResponse(ai_message=ai_response)


@router.post("/submit", response_model=DelegationSubmitResponse)
async def submit_delegation(request: DelegationSubmit, db: AsyncSession = Depends(get_session)):
    stmt = (
        select(InteractionLog)
        .where(InteractionLog.prolific_pid == request.pid)
        .where(InteractionLog.task_id == request.task_id)
        .where(InteractionLog.condition == "delegation")
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.payload = json.dumps(request.subtask_inputs)
        db.add(existing)
    else:
        db.add(
            InteractionLog(
                prolific_pid=request.pid,
                experiment_id=request.experiment_id,
                task_id=request.task_id,
                condition="delegation",
                interaction_type="delegation_submission",
                payload=json.dumps(request.subtask_inputs),
            )
        )
    await db.commit()

    return DelegationSubmitResponse(status="success")

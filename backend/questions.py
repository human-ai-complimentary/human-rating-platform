"""Load delegation questions from the static JSON file at startup.

QUESTIONS is populated by calling load_questions() in the app lifespan.
Both the delegation router and rater operations import from here.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

QUESTIONS: dict[str, dict] = {}

_DEFAULT_INSTRUCTIONS = "Review the AI's analysis and provide your input where needed."


def load_questions() -> None:
    questions_path = Path(__file__).parent / "questions" / "questions_combined.json"
    if not questions_path.exists():
        logger.warning("Questions file not found: %s", questions_path)
        return

    try:
        with open(questions_path, encoding="utf-8") as f:
            data = json.load(f)

        results = data.get("results", [])
        for item in results:
            qid = str(item["question_id"])
            delegation_data = [
                {
                    "id": subtask["id"],
                    "description": subtask.get("description", ""),
                    "ai_answer": subtask.get("ai_answer", ""),
                    "ai_reasoning": subtask.get("ai_reasoning", ""),
                    "ai_confidence": subtask.get("ai_confidence", 0.5),
                    "needs_human_input": subtask.get("needs_human_input", False),
                }
                for subtask in item.get("subtasks", [])
            ]
            QUESTIONS[qid] = {
                "id": qid,
                "instructions": item.get("instructions", _DEFAULT_INSTRUCTIONS),
                "question": item["question"],
                "delegation_data": delegation_data,
                "ground_truth": item.get("ground_truth"),
            }

        logger.info("Loaded %d delegation questions", len(QUESTIONS))
    except Exception:
        logger.exception("Failed to load questions from %s", questions_path)


def get_random_task_id() -> Optional[str]:
    if not QUESTIONS:
        return None
    return random.choice(list(QUESTIONS.keys()))

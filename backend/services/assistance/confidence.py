"""Confidence estimation for assistance subtasks.

A ConfidenceEstimator takes a question and a list of subtasks (each with a
question and the AI's current best answer) and returns a confidence score
0–100 for each subtask.

The default implementation (LLMConfidenceEstimator) asks the LLM to
self-report. Swap in any other implementation by subclassing
ConfidenceEstimator and passing it to HumanAsAToolMethod.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from config import get_settings

from .llm import complete

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a calibration assistant. Given a question and a list of subtasks with \
the AI's current best answer for each, rate the AI's confidence in each answer \
on a scale of 0–100:

  100 = completely certain, no meaningful chance of being wrong
   75 = fairly confident, minor residual doubt
   50 = uncertain, roughly a coin flip
    0 = completely uncertain, no real basis for the answer

Respond with JSON only — no explanation, no markdown fences:
{{"scores": [<score_for_index_0>, <score_for_index_1>, ...]}}\
"""


class ConfidenceEstimator(ABC):
    @abstractmethod
    async def estimate_batch(self, question_text: str, subtasks: list[dict]) -> list[int]:
        """Return a confidence score (0–100) for each subtask, in order.

        Args:
            question_text: The original question being answered.
            subtasks:      List of subtask dicts, each containing at minimum
                           ``question`` and ``my_answer`` keys.

        Returns:
            List of ints of length ``len(subtasks)``, each clamped to 0–100.
        """


class LLMConfidenceEstimator(ConfidenceEstimator):
    """Asks the LLM to self-report confidence for each subtask."""

    def __init__(self, model: str | None = None) -> None:
        # Default to a fast/cheap model — scoring is a simple numerical task.
        self._model = model or "openrouter/google/gemini-3.1-flash-lite-preview"

    async def estimate_batch(self, question_text: str, subtasks: list[dict]) -> list[int]:
        if not subtasks:
            return []

        settings = get_settings()
        model = self._model or settings.llm.default_model

        subtask_lines = "\n\n".join(
            f"Subtask {st['index']}:\n"
            f"  Question: {st['question']}\n"
            f"  AI's answer: {st.get('my_answer') or '(none)'}"
            for st in subtasks
        )
        user_msg = f"Question: {question_text}\n\n{subtask_lines}"

        raw = await complete(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user_msg}],
            model=model,
            settings=settings.llm,
        )

        try:
            scores = [int(s) for s in json.loads(raw)["scores"]]
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            logger.warning("Failed to parse confidence scores: %r", raw)
            return [50] * len(subtasks)

        if len(scores) != len(subtasks):
            logger.warning(
                "Confidence score count mismatch: got %d, expected %d", len(scores), len(subtasks)
            )
            scores = (scores + [50] * len(subtasks))[: len(subtasks)]

        return [max(0, min(100, s)) for s in scores]

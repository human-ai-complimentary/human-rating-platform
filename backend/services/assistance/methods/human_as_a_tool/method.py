"""Human-as-a-tool assistance method.

The AI decomposes the question into subtasks, attempts to answer each itself,
and delegates only the ones it is genuinely uncertain about (confidence below
the threshold) to the human. It repeats this for up to max_rounds rounds,
incorporating human answers each time, before synthesising a final answer.

assistance_params:
    model:                LLM to use for decomposition (default: settings.llm.default_model)
    confidence_model:     LLM to use for confidence scoring (default: gemini-2.0-flash-lite)
    max_rounds:           Maximum delegation rounds before forced synthesis (default: 5)
    max_subtasks:         Max subtasks to identify per round (default: 5)
    confidence_threshold: Show AI answer pre-filled below this score (default: 75, range 0–100)
"""

from __future__ import annotations

import json
import logging

from config import get_settings
from models import Question

from ...base import AssistanceMethod, InteractionStep, StepType
from ...confidence import ConfidenceEstimator, LLMConfidenceEstimator
from .decomposer import SubtaskDecomposer

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 75


class HumanAsAToolMethod(AssistanceMethod):
    def __init__(self, confidence_estimator: ConfidenceEstimator | None = None) -> None:
        self._decomposer = SubtaskDecomposer()
        self._estimator = confidence_estimator

    async def start(self, question: Question, params: dict) -> InteractionStep:
        settings = get_settings()
        model = params.get("model") or settings.llm.default_model
        max_rounds = int(params.get("max_rounds", 5))
        max_subtasks = int(params.get("max_subtasks", 5))
        confidence_threshold = int(params.get("confidence_threshold", _CONFIDENCE_THRESHOLD))

        question_text = question.question_text
        options = question.options or ""

        result = await self._decomposer.start(question_text, options, max_subtasks, model)

        if result.done:
            return InteractionStep(
                type=StepType.COMPLETE,
                payload={
                    "history": [],
                    "synthesis": {
                        "answer": result.synthesis.get("answer", ""),
                        "reasoning": result.synthesis.get("reasoning", ""),
                    },
                },
                is_terminal=True,
            )

        subtasks = await self._score_subtasks(question_text, result.subtasks, params)

        return InteractionStep(
            type=StepType.ASK_INPUT,
            payload={
                "subtasks": subtasks,
                "iteration": 1,
                "max_rounds": max_rounds,
                "confidence_threshold": confidence_threshold,
            },
            state={
                "question_text": question_text,
                "options": options,
                "iteration": 1,
                "max_rounds": max_rounds,
                "max_subtasks": max_subtasks,
                "confidence_threshold": confidence_threshold,
                "subtasks": subtasks,
                "history": [],
                "model": model,
            },
        )

    async def advance(self, state: dict, human_input: str, params: dict) -> InteractionStep:
        settings = get_settings()
        model = state.get("model") or params.get("model") or settings.llm.default_model

        try:
            answers: dict[str, str] = json.loads(human_input)
        except json.JSONDecodeError:
            logger.warning("Failed to parse human_input as JSON: %r", human_input)
            answers = {}

        iteration = state.get("iteration", 1)
        max_rounds = state.get("max_rounds", 5)
        max_subtasks = state.get("max_subtasks", 5)
        confidence_threshold = state.get("confidence_threshold", _CONFIDENCE_THRESHOLD)
        question_text = state.get("question_text", "")
        options = state.get("options", "")

        history = [
            *state.get("history", []),
            {"subtasks": state.get("subtasks", []), "answers": answers},
        ]

        result = await self._decomposer.advance(
            question_text, options, history,
            iteration=iteration,
            max_rounds=max_rounds,
            model=model,
        )

        if result.done:
            return InteractionStep(
                type=StepType.COMPLETE,
                payload={
                    "history": history,
                    "synthesis": {
                        "answer": result.synthesis.get("answer", ""),
                        "reasoning": result.synthesis.get("reasoning", ""),
                    },
                },
                is_terminal=True,
            )

        subtasks = await self._score_subtasks(question_text, result.subtasks, params)

        return InteractionStep(
            type=StepType.ASK_INPUT,
            payload={
                "subtasks": subtasks,
                "iteration": iteration + 1,
                "max_rounds": max_rounds,
                "confidence_threshold": confidence_threshold,
            },
            state={
                "question_text": question_text,
                "options": options,
                "iteration": iteration + 1,
                "max_rounds": max_rounds,
                "max_subtasks": max_subtasks,
                "confidence_threshold": confidence_threshold,
                "subtasks": subtasks,
                "history": history,
                "model": model,
            },
        )

    def _get_estimator(self, params: dict) -> ConfidenceEstimator:
        if self._estimator is not None:
            return self._estimator
        confidence_model = params.get("confidence_model") or None
        return LLMConfidenceEstimator(model=confidence_model)

    async def _score_subtasks(
        self, question_text: str, subtasks: list[dict], params: dict
    ) -> list[dict]:
        """Return all subtasks with confidence scores merged in."""
        scores = await self._get_estimator(params).estimate_batch(question_text, subtasks)
        return [{**st, "confidence": score} for st, score in zip(subtasks, scores)]

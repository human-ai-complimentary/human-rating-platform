"""Base class and data types for assistance methods."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from models import Question


class StepType(str, Enum):
    NONE = "none"          # method produced no assistance (terminal)
    DISPLAY = "display"    # show static content to the rater (terminal)
    ASK_INPUT = "ask_input"  # ask the rater a sub-question, then call advance()
    COMPLETE = "complete"  # multi-turn interaction finished, show final result (terminal)


@dataclass
class InteractionStep:
    """Represents one step in an assistance interaction.

    content:
        Arbitrary payload interpreted by the matching frontend component.
    is_terminal:
        True when no further advance() call is expected.
    """

    type: StepType
    content: dict = field(default_factory=dict)
    is_terminal: bool = False


class AssistanceMethod(ABC):
    """Interface every assistance method must implement.

    One-shot methods only need to override start(); multi-turn methods
    override both start() and advance().
    """

    @abstractmethod
    async def start(self, question: Question, params: dict) -> InteractionStep:
        """Begin an assistance interaction for the given question."""
        ...

    async def advance(self, state: dict, human_input: str, params: dict) -> InteractionStep:
        """Advance a multi-turn interaction with the rater's latest input.

        The default implementation raises, signalling that this method is
        terminal after start(). Stateful methods should override this.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support multi-turn interactions."
        )

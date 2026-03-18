"""Registry mapping method names to AssistanceMethod classes.

To add a new method:
    1. Create a class in services/assistance/methods/ that extends AssistanceMethod.
    2. Import it here and add an entry to _REGISTRY.
"""

from __future__ import annotations

from .base import AssistanceMethod
from .methods.none import NoAssistance

_REGISTRY: dict[str, type[AssistanceMethod]] = {
    "none": NoAssistance,
}


def get_method(name: str) -> AssistanceMethod:
    """Return an instantiated AssistanceMethod for the given name.

    Raises ValueError for unknown method names so callers get a clear error
    rather than an AttributeError deep in the stack.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown assistance method {name!r}. "
            f"Available: {sorted(_REGISTRY)}"
        )
    return cls()


def register(name: str, cls: type[AssistanceMethod]) -> None:
    """Register a new method at runtime (useful for tests or plugins)."""
    _REGISTRY[name] = cls

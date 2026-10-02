"""Timeline application layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.timeline.application.timeline_builder import TimelineBuilder as TimelineBuilder

__all__ = ["TimelineBuilder"]


def __getattr__(name: str):
    if name == "TimelineBuilder":
        from app.modules.timeline.application.timeline_builder import TimelineBuilder

        return TimelineBuilder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

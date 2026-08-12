"""Workspace HTTP API adapter — thin FastAPI wiring over the application use case."""

from app.modules.workspace.api.router import router

__all__ = ["router"]

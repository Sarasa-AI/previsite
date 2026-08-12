"""HTTP response helpers — forward interface DTO fields; never recompute etags."""

from __future__ import annotations

from fastapi import Response

from app.modules.workspace.interface.dto import CONTRACT_VERSION


def apply_workspace_headers(response: Response, *, plan_etag: str) -> None:
    """
    Attach transport headers from interface DTO values.

    ``plan_etag`` must be the unchanged value from the interface mapper output.
    """
    response.headers["ETag"] = plan_etag
    response.headers["X-Contract-Version"] = CONTRACT_VERSION

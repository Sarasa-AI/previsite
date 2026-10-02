#!/usr/bin/env python3
"""Execute admin-approved account erasure requests (operator-run).

Requires prior patient request, cool-off, and POST /api/admin/privacy/deletion/{id}/approve.
Audit logs are never deleted.

Usage:
  python scripts/execute_account_deletion.py [--request-id ID]

Product owner must confirm LEGAL_RETENTION_* env defaults before production use.
Phone: N/A — users table has no phone column; identity fields are anonymized only.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.database import get_async_session  # noqa: E402
from app.models.account_deletion_request import (  # noqa: E402
    AccountDeletionRequest,
    DeletionRequestStatus,
)
from app.privacy.erasure_service import (  # noqa: E402
    execute_all_approved_deletions,
    execute_approved_deletion,
)
from app.services.audit_service import (  # noqa: E402
    AUDIT_PRIVACY_DELETION_EXECUTE,
    record_audit,
)

logger = logging.getLogger(__name__)


async def _async_main(request_id: int | None) -> int:
    if request_id is not None:
        async with get_async_session() as db:
            user_id = await execute_approved_deletion(db, request_id)
            if user_id is None:
                print(f"No approved deletion executed for request id={request_id}.")
                return 1
            await record_audit(
                db,
                action=AUDIT_PRIVACY_DELETION_EXECUTE,
                user_id=None,
                resource_type="account_deletion_request",
                resource_id=request_id,
            )
            print(f"Erased patient user_id={user_id} (request id={request_id}).")
            return 0

    async with get_async_session() as db:
        pending = await db.execute(
            select(AccountDeletionRequest.id).where(
                AccountDeletionRequest.status == DeletionRequestStatus.APPROVED
            )
        )
        ids = [r[0] for r in pending.all()]
    if not ids:
        print("No approved deletion requests pending execution.")
        return 0

    completed: list[int] = []
    for req_id in ids:
        async with get_async_session() as db:
            user_id = await execute_approved_deletion(db, req_id)
            if user_id is not None:
                await record_audit(
                    db,
                    action=AUDIT_PRIVACY_DELETION_EXECUTE,
                    user_id=None,
                    resource_type="account_deletion_request",
                    resource_id=req_id,
                )
                completed.append(user_id)
                print(f"Erased patient user_id={user_id} (request id={req_id}).")

    print(f"Completed {len(completed)} erasure(s).")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute approved account deletions")
    parser.add_argument(
        "--request-id",
        type=int,
        default=None,
        help="Single deletion request id (default: all approved)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(_async_main(args.request_id)))


if __name__ == "__main__":
    main()

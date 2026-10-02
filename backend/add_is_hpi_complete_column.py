"""Deprecated: Alembic is the only production schema source.

This standalone script previously added summaries.is_hpi_complete outside
migrations. It is now a harmless no-op. Use:

    alembic upgrade head

which applies revision q1r2s3t4u5v6 (existence-guarded).
"""


def add_is_hpi_complete_column() -> None:
    print(
        "No-op: summaries.is_hpi_complete is managed by Alembic "
        "(revision q1r2s3t4u5v6). Run `alembic upgrade head` instead."
    )


if __name__ == "__main__":
    add_is_hpi_complete_column()

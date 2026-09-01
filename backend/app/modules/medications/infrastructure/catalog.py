"""Read-only access to the existing Darooyab SQLite catalog."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from app.modules.medications.domain.models import CatalogMedication
from app.modules.medications.domain.rules import uses_latin_script

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[4] / "data" / "darooyab.db"
CATALOG_PATH_ENV_VARS = (
    "MEDICATION_CATALOG_PATH",
    "DAROOYAB_CATALOG_PATH",
    "DAROOYAB_DB_PATH",
)
REQUIRED_COLUMNS = frozenset(
    {
        "id",
        "brand_name_fa",
        "brand_name_en",
        "generic_name_en",
        "form",
        "strength",
        "manufacturer",
    }
)

_PERSIAN_TO_ASCII_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ARABIC_TO_ASCII_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_QUERY_TOKEN_RE = re.compile(r"[\s,،;]+|\s*[-–—]\s*")


def _normalize_digits(value: str) -> str:
    return value.translate(_PERSIAN_TO_ASCII_DIGITS).translate(_ARABIC_TO_ASCII_DIGITS)


def _search_tokens(query: str) -> list[str]:
    return [token for token in _QUERY_TOKEN_RE.split(query.strip()) if token]


class CatalogUnavailableError(RuntimeError):
    """Raised when the configured real Darooyab catalog cannot be used."""


def configured_catalog_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve constructor override, environment override, then the legacy default."""

    if path is not None:
        return Path(path).expanduser()
    for variable in CATALOG_PATH_ENV_VARS:
        configured = os.getenv(variable, "").strip()
        if configured:
            return Path(configured).expanduser()
    return DEFAULT_CATALOG_PATH


class DarooyabCatalog:
    """Darooyab catalog adapter that never creates or mutates its SQLite file."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = configured_catalog_path(path).resolve()
        self._validate()

    @property
    def available(self) -> bool:
        return True

    def _connection(self) -> sqlite3.Connection:
        uri = f"{self.path.as_uri()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as exc:
            raise CatalogUnavailableError(
                f"Darooyab catalog could not be opened read-only at '{self.path}': {exc}"
            ) from exc
        connection.row_factory = sqlite3.Row
        return connection

    def _validate(self) -> None:
        if not self.path.is_file():
            raise CatalogUnavailableError(
                "Darooyab catalog is unavailable at "
                f"'{self.path}'. Set MEDICATION_CATALOG_PATH to the real darooyab.db file."
            )

        try:
            with self._connection() as connection:
                rows = connection.execute("PRAGMA table_info(drugs)").fetchall()
        except sqlite3.Error as exc:
            raise CatalogUnavailableError(
                f"Darooyab catalog at '{self.path}' could not be inspected: {exc}"
            ) from exc

        columns = {str(row["name"]) for row in rows}
        missing = REQUIRED_COLUMNS - columns
        if missing:
            missing_columns = ", ".join(sorted(missing))
            raise CatalogUnavailableError(
                f"Darooyab catalog at '{self.path}' has an incompatible drugs table; "
                f"missing columns: {missing_columns}."
            )

    def search(self, query: str, limit: int = 20) -> tuple[CatalogMedication, ...]:
        """Bilingual Darooyab substring search with strength-aware tokens.

        The query is split into tokens so strength-containing input such as
        Metformin 500 or متفورمین ۵۰۰ still finds products: every token
        must appear in at least one of the name columns or in strength.
        Persian/Arabic digits are normalized to ASCII for the strength clause.
        """

        normalized_query = query.strip()
        if not normalized_query or limit <= 0:
            return ()

        tokens = _search_tokens(normalized_query)
        if not tokens:
            return ()

        clauses: list[str] = []
        parameters: list[str] = []
        for token in tokens:
            name_pattern = f"%{token}%"
            strength_pattern = f"%{_normalize_digits(token)}%"
            clauses.append(
                "(d.brand_name_fa LIKE ? OR d.brand_name_en LIKE ? "
                "OR d.generic_name_en LIKE ? OR d.strength LIKE ?)"
            )
            parameters.extend((name_pattern, name_pattern, name_pattern, strength_pattern))

        first_token = tokens[0]
        starts_with = f"{first_token}%"
        if uses_latin_script(first_token):
            order_sql = """
                CASE
                    WHEN brand_name_en LIKE ? THEN 0
                    WHEN generic_name_en LIKE ? THEN 1
                    WHEN brand_name_fa LIKE ? THEN 2
                    ELSE 3
                END,
                brand_name_en,
                d.id
            """
        else:
            order_sql = """
                CASE
                    WHEN brand_name_fa LIKE ? THEN 0
                    WHEN brand_name_en LIKE ? THEN 1
                    WHEN generic_name_en LIKE ? THEN 2
                    ELSE 3
                END,
                brand_name_fa,
                d.id
            """
        parameters.extend((starts_with, starts_with, starts_with, limit))

        sql = f"""
            SELECT
                d.id,
                d.brand_name_fa,
                d.brand_name_en,
                d.generic_name_en,
                d.form,
                d.strength,
                d.manufacturer,
                d.brand_slug,
                d.generic_slug,
                d.company_slug,
                c.name AS company_name
            FROM drugs d
            LEFT JOIN companies c ON c.slug = d.company_slug
            WHERE {" AND ".join(clauses)}
            ORDER BY
                {order_sql}
            LIMIT ?
        """

        try:
            with self._connection() as connection:
                rows = connection.execute(sql, parameters).fetchall()
        except sqlite3.Error as exc:
            raise CatalogUnavailableError(
                f"Darooyab catalog search failed at '{self.path}': {exc}"
            ) from exc

        return tuple(CatalogMedication(**dict(row)) for row in rows)


Catalog = DarooyabCatalog

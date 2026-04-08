"""
Safe auto-migration utility for SQLite databases.

Compares ORM model definitions against the actual database schema and
issues ALTER TABLE ADD COLUMN for any missing columns. This avoids
the need for Alembic while preventing the 'no such column' crashes
that occur when new model columns are added but the DB isn't recreated.

IMPORTANT: This only handles ADDING columns. It does NOT handle:
- Renaming columns
- Changing column types
- Removing columns
- Adding constraints or indexes

For those operations, manual migration is still required.
"""

import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db import Base

logger = logging.getLogger(__name__)

# Map SQLAlchemy types to SQLite type affinity
_TYPE_MAP = {
    "INTEGER": "INTEGER",
    "BIGINTEGER": "INTEGER",
    "SMALLINTEGER": "INTEGER",
    "VARCHAR": "TEXT",
    "STRING": "TEXT",
    "TEXT": "TEXT",
    "FLOAT": "REAL",
    "NUMERIC": "REAL",
    "BOOLEAN": "INTEGER",
    "DATETIME": "TEXT",
    "DATE": "TEXT",
    "JSON": "TEXT",
    "BLOB": "BLOB",
}


def _sqla_type_to_sqlite(col_type) -> str:
    """Convert SQLAlchemy column type to SQLite type affinity."""
    type_name = type(col_type).__name__.upper()
    return _TYPE_MAP.get(type_name, "TEXT")


def safe_migrate(engine: Engine) -> list[str]:
    """
    Inspect all ORM models and add any missing columns to existing tables.
    
    Returns a list of ALTER TABLE statements that were executed.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    migrations_run = []

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            # Table doesn't exist yet — create_all() will handle it
            logger.info("Table '%s' does not exist, will be created by create_all()", table_name)
            continue

        # Get existing columns
        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}

        # Check each ORM column
        for col_name, column in table.columns.items():
            if col_name in existing_cols:
                continue

            # Column is missing — add it
            sqlite_type = _sqla_type_to_sqlite(column.type)
            
            # Build DEFAULT clause if column has a server_default or is not nullable
            default_clause = ""
            if column.server_default is not None:
                default_clause = f" DEFAULT {column.server_default.arg}"
            elif not column.nullable and sqlite_type == "INTEGER":
                default_clause = " DEFAULT 0"
            elif not column.nullable and sqlite_type == "REAL":
                default_clause = " DEFAULT 0.0"
            elif not column.nullable and sqlite_type == "TEXT":
                default_clause = " DEFAULT ''"

            sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sqlite_type}{default_clause}"

            try:
                with engine.begin() as conn:
                    conn.execute(text(sql))
                logger.info("MIGRATION: %s", sql)
                migrations_run.append(sql)
            except Exception as e:
                # Column might already exist (race condition) or other issue
                logger.warning("Migration failed for %s.%s: %s", table_name, col_name, e)

    if migrations_run:
        logger.info("Auto-migration complete: %d columns added", len(migrations_run))
    else:
        logger.info("Auto-migration: schema is up to date, no changes needed")

    return migrations_run


def validate_schema(engine: Engine) -> list[str]:
    """
    Validate that all ORM model columns exist in the database.
    Returns a list of missing columns (empty = all good).
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing = []

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            missing.append(f"TABLE MISSING: {table_name}")
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
        for col_name in table.columns.keys():
            if col_name not in existing_cols:
                missing.append(f"COLUMN MISSING: {table_name}.{col_name}")

    return missing

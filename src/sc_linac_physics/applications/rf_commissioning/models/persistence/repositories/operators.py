"""Repositories for RF commissioning operator lists."""

from __future__ import annotations

from sc_linac_physics.applications.rf_commissioning.models.persistence.database_helpers import (
    now_iso,
)

from .base import BaseRepository


class OperatorRepository(BaseRepository):
    """Persistence for approved operator names."""

    def get_operators(self) -> list[str]:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM operators ORDER BY name")
            return [row[0] for row in cursor.fetchall()]

    def add_operator(self, name: str) -> bool:
        clean_name = name.strip()
        if not clean_name:
            return False
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO operators (name, created_at) VALUES (?, ?)",
                (clean_name, now_iso()),
            )
            return cursor.rowcount > 0

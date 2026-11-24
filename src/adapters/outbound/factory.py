"""Selección del adaptador outbound activo según `DATABASE_URL`."""

import os

from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort

DEFAULT_DATABASE_URL = "sqlite:///:memory:"


def get_incident_repository() -> IncidentRepositoryPort:
    """Devuelve el repositorio SQLite configurado por `DATABASE_URL`."""
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if not database_url.startswith("sqlite:///"):
        raise ValueError("DATABASE_URL debe empezar con sqlite:/// en H002")
    return SQLiteIncidentRepository(database_url)

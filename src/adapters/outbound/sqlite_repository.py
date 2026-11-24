"""Adaptador SQLite que implementa `IncidentRepositoryPort`."""

import sqlite3
from datetime import datetime
from typing import Any

from src.application.ports import IncidentRepositoryPort
from src.domain.models import Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE


class SQLiteIncidentRepository(IncidentRepositoryPort):
    """Persistencia SQLite con una sola consulta para listar incidentes activos."""

    def __init__(self, database_url: str = "sqlite:///:memory:") -> None:
        self.database_url = database_url
        self.conn = sqlite3.connect(self._resolve_path(database_url), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    @staticmethod
    def _resolve_path(database_url: str) -> str:
        prefijo = "sqlite:///"
        if not database_url.startswith(prefijo):
            raise ValueError("DATABASE_URL debe empezar con sqlite:/// en H002")
        return database_url[len(prefijo) :] or ":memory:"

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sla_policies (
                    severity TEXT PRIMARY KEY,
                    max_resolution_minutes INTEGER NOT NULL,
                    operates_24x7 INTEGER NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    component TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_duplicates (
                    incident_id TEXT PRIMARY KEY,
                    duplicate_group_key TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incidents_component_status
                ON incidents (component, status)
                """
            )
            for rule in SLA_POLICY_TABLE.values():
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO sla_policies
                    (severity, max_resolution_minutes, operates_24x7)
                    VALUES (?, ?, ?)
                    """,
                    (rule.severity, rule.max_resolution_minutes, int(rule.operates_24x7)),
                )

    def save_incident(
        self, incident: Incident, duplicate_group_key: str | None = None
    ) -> None:
        """Inserta o actualiza un incidente y, si llega, su clave de duplicado."""
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO incidents
                (incident_id, title, component, severity, status, created_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident.incident_id,
                    incident.title,
                    incident.component,
                    incident.severity,
                    incident.status,
                    incident.created_at.isoformat(),
                    incident.resolved_at.isoformat() if incident.resolved_at else None,
                ),
            )
            if duplicate_group_key is not None:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO incident_duplicates
                    (incident_id, duplicate_group_key)
                    VALUES (?, ?)
                    """,
                    (incident.incident_id, duplicate_group_key),
                )

    def get_incident(self, incident_id: str) -> Incident | None:
        """Devuelve el incidente reconstruido o `None` si no existe."""
        fila = self.conn.execute(
            """
            SELECT incident_id, title, component, severity, status, created_at, resolved_at
            FROM incidents WHERE incident_id = ?
            """,
            (incident_id,),
        ).fetchone()
        return self._fila_a_incidente(fila) if fila else None

    def find_open_duplicates(self, duplicate_group_key: str) -> list[Incident]:
        """Devuelve los incidentes activos asociados a una clave de duplicado."""
        filas = self.conn.execute(
            """
            SELECT i.incident_id, i.title, i.component, i.severity,
                   i.status, i.created_at, i.resolved_at
            FROM incident_duplicates AS d
            INNER JOIN incidents AS i ON i.incident_id = d.incident_id
            WHERE d.duplicate_group_key = ?
              AND i.status IN ('OPEN', 'IN_PROGRESS')
            ORDER BY i.created_at ASC, i.incident_id ASC
            """,
            (duplicate_group_key,),
        ).fetchall()
        return [self._fila_a_incidente(fila) for fila in filas]

    def list_active_incidents(
        self, component_filter: str | None = None
    ) -> list[Incident]:
        """Lista activos con `JOIN`, filtro exacto opcional y orden determinista."""
        consulta = """
            SELECT i.incident_id, i.title, i.component, i.severity,
                   i.status, i.created_at, i.resolved_at
            FROM incidents AS i
            INNER JOIN sla_policies AS sp ON sp.severity = i.severity
            WHERE i.status IN ('OPEN', 'IN_PROGRESS')
        """
        parametros: list[Any] = []
        if component_filter is not None:
            consulta += " AND i.component = ?"
            parametros.append(component_filter)
        consulta += " ORDER BY i.created_at ASC, i.incident_id ASC"

        filas = self.conn.execute(consulta, parametros).fetchall()
        return [self._fila_a_incidente(fila) for fila in filas]

    def check_health(self) -> bool:
        """Comprueba que la conexión SQLite responde."""
        fila = self.conn.execute("SELECT 1").fetchone()
        return fila is not None and fila[0] == 1

    def close(self) -> None:
        """Cierra la conexión SQLite."""
        self.conn.close()

    @staticmethod
    def _fila_a_incidente(fila: sqlite3.Row) -> Incident:
        return Incident(
            incident_id=fila["incident_id"],
            title=fila["title"],
            component=fila["component"],
            severity=fila["severity"],
            status=fila["status"],
            created_at=datetime.fromisoformat(fila["created_at"]),
            resolved_at=(
                datetime.fromisoformat(fila["resolved_at"]) if fila["resolved_at"] else None
            ),
        )

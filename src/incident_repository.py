"""Repositorio SQLite de incidentes con un cuello de botella de rendimiento intencional.

NOTA PEDAGÓGICA (Semana 1 — Fase 2):
El método `get_active_incidents_summary` presenta un problema clásico de rendimiento
cuando la tabla supera los 10,000 registros:
1. Carga todos los registros de la tabla `incidents` en memoria sin filtrar en SQL.
2. Ejecuta una consulta SQL individual a `sla_policies` dentro de un bucle por cada
   incidente activo (anti-patrón de consultas N+1).
3. No utiliza índices ni paginación.
"""

import argparse
from datetime import datetime, timedelta
import sqlite3
import time
from typing import Any, Dict, List

from src.models import Incident, SeverityLevel
from src.sla_calculator import SLA_POLICY_TABLE, evaluate_sla_status


class IncidentRepository:
    """Gestiona la persistencia de incidentes y políticas de SLA en SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sla_policies (
                severity TEXT PRIMARY KEY,
                max_resolution_minutes INTEGER NOT NULL,
                operates_24x7 INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
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
        for rule in SLA_POLICY_TABLE.values():
            cursor.execute(
                """
                INSERT OR REPLACE INTO sla_policies (severity, max_resolution_minutes, operates_24x7)
                VALUES (?, ?, ?)
                """,
                (rule.severity, rule.max_resolution_minutes, 1 if rule.operates_24x7 else 0),
            )
        self.conn.commit()

    def seed_synthetic_incidents(self, total_records: int = 10000) -> None:
        """Puebla la base de datos con registros sintéticos para pruebas de rendimiento."""
        components = [
            "payments-gateway",
            "auth-identity",
            "database-cluster",
            "reporting-api",
            "frontend-ui",
        ]
        severities: List[SeverityLevel] = ["P0", "P1", "P2", "P3"]
        statuses = ["RESOLVED", "RESOLVED", "RESOLVED", "OPEN", "IN_PROGRESS"]
        base_time = datetime(2026, 11, 1, 8, 0, 0)

        rows = []
        for idx in range(1, total_records + 1):
            sev = severities[idx % len(severities)]
            status = statuses[(idx * 3 + idx // 5) % len(statuses)]
            comp = components[idx % len(components)]
            created = base_time + timedelta(minutes=((idx - 1) % 10000 + 1) * 2)
            resolved = (created + timedelta(minutes=45)).isoformat() if status == "RESOLVED" else None
            rows.append(
                (
                    f"INC-{idx:05d}",
                    f"Reporte sintético #{idx} en {comp}",
                    comp,
                    sev,
                    status,
                    created.isoformat(),
                    resolved,
                )
            )

        cursor = self.conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO incidents
            (incident_id, title, component, severity, status, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def get_active_incidents_summary(
        self, component_filter: str, reference_time: datetime
    ) -> List[Dict[str, Any]]:
        """Obtiene el resumen de incidentes activos para un componente específico.

        ANTI-PATRÓN INTENCIONAL (Para diagnosticar y refactorizar en la Fase 2):
        - Trae las 10,000 filas con `SELECT * FROM incidents` y filtra en Python.
        - Por cada fila coincidente, ejecuta un `SELECT` separado a `sla_policies` (N+1).
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM incidents")
        all_rows = cursor.fetchall()

        results: List[Dict[str, Any]] = []
        for row in all_rows:
            if row["status"] not in ("OPEN", "IN_PROGRESS"):
                continue
            if row["component"] != component_filter:
                continue

            # Consulta N+1 innecesaria dentro del bucle
            policy_cursor = self.conn.cursor()
            policy_cursor.execute(
                "SELECT max_resolution_minutes FROM sla_policies WHERE severity = ?",
                (row["severity"],),
            )
            _ = policy_cursor.fetchone()

            incident = Incident(
                incident_id=row["incident_id"],
                title=row["title"],
                component=row["component"],
                severity=row["severity"],
                status=row["status"],
                created_at=datetime.fromisoformat(row["created_at"]),
                resolved_at=(
                    datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None
                ),
            )
            sla_eval = evaluate_sla_status(incident, reference_time=reference_time)
            results.append(
                {
                    "incident_id": incident.incident_id,
                    "severity": incident.severity,
                    "status": incident.status,
                    "elapsed_minutes": sla_eval.elapsed_minutes,
                    "is_breached": sla_eval.is_breached,
                }
            )

        return results


def _run_benchmark() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de consultas en IncidentRepository")
    parser.add_argument("--records", type=int, default=10000, help="Cantidad de registros a sembrar")
    parser.add_argument(
        "--iterations", type=int, default=20, help="Número de consultas consecutivas a medir"
    )
    args = parser.parse_args()

    repo = IncidentRepository()
    print(f"Sembrando {args.records} incidentes en SQLite en memoria...")
    repo.seed_synthetic_incidents(total_records=args.records)

    ref_time = datetime(2026, 11, 20, 12, 0, 0)
    start = time.perf_counter()
    found_count = 0
    for _ in range(args.iterations):
        active = repo.get_active_incidents_summary(
            component_filter="payments-gateway", reference_time=ref_time
        )
        found_count = len(active)
    elapsed_ms = (time.perf_counter() - start) * 1000

    print("=== Resultado del Benchmark (Antes de Refactorizar) ===")
    print(f"Incidentes activos encontrados para 'payments-gateway': {found_count}")
    print(f"Tiempo total ({args.iterations} ejecuciones sobre {args.records} filas): {elapsed_ms:.2f} ms")
    print(f"Promedio por consulta: {elapsed_ms / args.iterations:.2f} ms")
    print(
        "Diagnóstico: `get_active_incidents_summary` escanea toda la tabla en memoria "
        "y ejecuta consultas N+1 por cada fila activa."
    )


if __name__ == "__main__":
    _run_benchmark()


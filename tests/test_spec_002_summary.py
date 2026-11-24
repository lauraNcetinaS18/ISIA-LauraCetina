import inspect
import json
import statistics
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import src.application.services as servicios
from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import get_incident_repository
from src.application.services import IncidentService
from src.domain.models import Incident

REFERENCE_TIME = datetime(2026, 11, 24, 12, 0)


class RelojFijo(datetime):
    @classmethod
    def now(cls, tz=None):
        return REFERENCE_TIME


@pytest.fixture
def reloj_fijo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(servicios, "datetime", RelojFijo)


def _make_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.joinpath(name).as_posix()}")
    return get_incident_repository()


def test_bdd_sqlite_repository_cumple_puerto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _make_repository(tmp_path, monkeypatch, "puerto.db")
    metodos = (
        "save_incident",
        "get_incident",
        "find_open_duplicates",
        "list_active_incidents",
        "check_health",
    )

    for metodo in metodos:
        assert callable(getattr(repository, metodo))

    assert list(inspect.signature(repository.save_incident).parameters) == [
        "incident",
        "duplicate_group_key",
    ]
    assert list(inspect.signature(repository.get_incident).parameters) == ["incident_id"]
    assert list(inspect.signature(repository.find_open_duplicates).parameters) == [
        "duplicate_group_key"
    ]
    assert list(inspect.signature(repository.list_active_incidents).parameters) == [
        "component_filter"
    ]
    assert list(inspect.signature(repository.check_health).parameters) == []

    incidente = Incident(
        incident_id="INC-P-001",
        title="Fallo de pasarela",
        component="payments-gateway",
        severity="P0",
        status="OPEN",
        created_at=datetime(2026, 11, 24, 10, 0),
    )
    repository.save_incident(incidente, "payments-gateway:http-502-outage")

    assert repository.get_incident("INC-P-001") == incidente
    assert repository.list_active_incidents() == [incidente]
    assert repository.find_open_duplicates("payments-gateway:http-502-outage") == [incidente]
    assert repository.check_health() is True

    repository.close()


def test_rendimiento_sc_005_repositorio_10k(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _make_repository(tmp_path, monkeypatch, "rendimiento.db")
    service = IncidentService(repository)

    componentes = [
        "payments-gateway",
        "auth-identity",
        "database-cluster",
        "reporting-api",
        "frontend-ui",
    ]
    severidades = ["P0", "P1", "P2", "P3"]
    estados = ["RESOLVED", "RESOLVED", "RESOLVED", "OPEN", "IN_PROGRESS"]
    base = datetime(2026, 11, 1, 8, 0)
    filas = []

    for indice in range(1, 10_001):
        componente = componentes[indice % len(componentes)]
        severidad = severidades[indice % len(severidades)]
        estado = estados[(indice * 3 + indice // 5) % len(estados)]
        creado = base + timedelta(minutes=((indice - 1) % 10_000 + 1) * 2)
        resuelto = (creado + timedelta(minutes=45)).isoformat() if estado == "RESOLVED" else None
        filas.append(
            (
                f"INC-{indice:05d}",
                f"Reporte sintético #{indice} en {componente}",
                componente,
                severidad,
                estado,
                creado.isoformat(),
                resuelto,
            )
        )

    repository.conn.executemany(
        """
        INSERT OR REPLACE INTO incidents
        (incident_id, title, component, severity, status, created_at, resolved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        filas,
    )
    repository.conn.commit()

    service.get_active_incidents_summary("payments-gateway", REFERENCE_TIME)

    mediciones = []
    for _ in range(3):
        inicio = time.perf_counter()
        resultado = service.get_active_incidents_summary("payments-gateway", REFERENCE_TIME)
        mediciones.append(time.perf_counter() - inicio)
        assert resultado["total_active"] > 0

    assert statistics.median(mediciones) < 2.0

    repository.close()


def _sembrar_escenarios(repository) -> None:
    incidentes = [
        Incident(
            "INC-1001",
            "HTTP 502 Bad Gateway en pasarela de pagos",
            "payments-gateway",
            "P0",
            "OPEN",
            datetime(2026, 11, 24, 10, 0),
        ),
        Incident(
            "INC-1002",
            "Saturación de conexiones en base de datos",
            "database-cluster",
            "P1",
            "IN_PROGRESS",
            datetime(2026, 11, 24, 11, 30),
        ),
        Incident(
            "INC-1003",
            "Latencia alta en reportes",
            "reporting-api",
            "P2",
            "OPEN",
            datetime(2026, 11, 24, 8, 0),
        ),
        Incident(
            "INC-1004",
            "Pago resuelto",
            "payments-gateway",
            "P0",
            "RESOLVED",
            datetime(2026, 11, 24, 9, 0),
            datetime(2026, 11, 24, 9, 30),
        ),
        Incident(
            "INC-1005",
            "Pago en escalamiento",
            "payments-gateway",
            "P0",
            "ESCALATION_REQUIRED",
            datetime(2026, 11, 24, 9, 30),
        ),
    ]
    for incidente in incidentes:
        repository.save_incident(incidente)


def test_bdd_resumen_global_excluye_resueltos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloj_fijo: None
) -> None:
    repository = _make_repository(tmp_path, monkeypatch, "global.db")
    _sembrar_escenarios(repository)
    client = TestClient(create_app())

    response = client.get("/api/v1/incidents/summary")

    assert response.status_code == 200
    cuerpo = response.json()
    assert list(cuerpo) == ["total_active", "breached_count", "incidents"]
    assert cuerpo["total_active"] == 3
    assert cuerpo["breached_count"] == 1
    assert [item["incident_id"] for item in cuerpo["incidents"]] == [
        "INC-1003",
        "INC-1001",
        "INC-1002",
    ]
    assert all(
        item["status"] in ("OPEN", "IN_PROGRESS") for item in cuerpo["incidents"]
    )
    assert all(
        list(item)
        == [
            "incident_id",
            "title",
            "component",
            "severity",
            "status",
            "elapsed_minutes",
            "is_breached",
            "requires_escalation",
        ]
        for item in cuerpo["incidents"]
    )
    assert "INC-1004" not in [item["incident_id"] for item in cuerpo["incidents"]]
    assert "INC-1005" not in [item["incident_id"] for item in cuerpo["incidents"]]

    repository.close()


def test_bdd_resumen_filtrado_por_componente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloj_fijo: None
) -> None:
    repository = _make_repository(tmp_path, monkeypatch, "filtro.db")
    _sembrar_escenarios(repository)
    client = TestClient(create_app())

    response = client.get("/api/v1/incidents/summary?component=payments-gateway")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total_active"] == 1
    assert cuerpo["breached_count"] == 1
    assert [item["incident_id"] for item in cuerpo["incidents"]] == ["INC-1001"]
    assert all(
        item["component"] == "payments-gateway" for item in cuerpo["incidents"]
    )

    repository.close()


def test_bdd_resumen_sin_resultados(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloj_fijo: None
) -> None:
    repository = _make_repository(tmp_path, monkeypatch, "vacio.db")
    _sembrar_escenarios(repository)
    client = TestClient(create_app())

    response = client.get("/api/v1/incidents/summary?component=componente-inexistente")

    assert response.status_code == 200
    assert response.json() == {"total_active": 0, "breached_count": 0, "incidents": []}

    repository.close()


def test_bdd_resumen_casos_borde_sla(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloj_fijo: None
) -> None:
    repository = _make_repository(tmp_path, monkeypatch, "bordes.db")
    incidentes = [
        Incident(
            "INC-B-01",
            "Latencia de fin de semana",
            "reporting-api",
            "P3",
            "OPEN",
            datetime(2026, 11, 20, 17, 0),
        ),
        Incident(
            "INC-B-02",
            "Límite exacto de P0",
            "payments-gateway",
            "P0",
            "OPEN",
            datetime(2026, 11, 24, 11, 0),
        ),
        Incident(
            "INC-B-03",
            "Breach estricto de P0",
            "payments-gateway",
            "P0",
            "OPEN",
            datetime(2026, 11, 24, 10, 59),
        ),
    ]
    for incidente in incidentes:
        repository.save_incident(incidente)

    client = TestClient(create_app())
    response = client.get("/api/v1/incidents/summary")

    assert response.status_code == 200
    detalles = {item["incident_id"]: item for item in response.json()["incidents"]}
    assert [item["incident_id"] for item in response.json()["incidents"]] == [
        "INC-B-01",
        "INC-B-03",
        "INC-B-02",
    ]
    assert detalles["INC-B-01"]["elapsed_minutes"] == 900
    assert detalles["INC-B-01"]["is_breached"] is False
    assert detalles["INC-B-01"]["requires_escalation"] is False
    assert detalles["INC-B-02"]["elapsed_minutes"] == 60
    assert detalles["INC-B-02"]["is_breached"] is False
    assert detalles["INC-B-02"]["requires_escalation"] is True
    assert detalles["INC-B-03"]["elapsed_minutes"] == 61
    assert detalles["INC-B-03"]["is_breached"] is True
    assert detalles["INC-B-03"]["requires_escalation"] is True

    repository.close()


def test_bdd_resumen_paridad_rest_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloj_fijo: None
) -> None:
    repository = _make_repository(tmp_path, monkeypatch, "paridad.db")
    _sembrar_escenarios(repository)
    client = TestClient(create_app())
    cli_runner = CliRunner()

    respuesta_http = client.get("/api/v1/incidents/summary")
    respuesta_cli = cli_runner.invoke(
        cli_app,
        ["summary", "--reference-time", REFERENCE_TIME.isoformat()],
    )

    assert respuesta_http.status_code == 200
    assert respuesta_cli.exit_code == 0
    cuerpo_http = respuesta_http.json()
    cuerpo_cli = json.loads(respuesta_cli.output)
    assert cuerpo_cli == cuerpo_http
    assert list(cuerpo_cli) == list(cuerpo_http)
    assert [list(item) for item in cuerpo_cli["incidents"]] == [
        list(item) for item in cuerpo_http["incidents"]
    ]

    repository.close()


def test_bdd_resumen_reference_time_invalido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloj_fijo: None
) -> None:
    repository = _make_repository(tmp_path, monkeypatch, "invalido.db")
    cli_runner = CliRunner()

    resultado = cli_runner.invoke(
        cli_app,
        ["summary", "--reference-time", "no-es-iso"],
    )

    assert resultado.exit_code == 2
    assert "Error:" in resultado.output

    repository.close()

"""Escenarios BDD de la especificación funcional 001."""

import json

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.cli import app as cli_app


def test_escenario_1_caida_critica_pasarela(client: TestClient) -> None:
    response = client.post(
        "/v1/triage",
        json={
            "incident_id": "INC-1001",
            "raw_text": "HTTP 502 Bad Gateway en pasarela de pagos",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "P0"
    assert body["component"] == "payments-gateway"
    assert body["recommended_team"] == "Backend-Core"
    assert body["duplicate_group_key"] == "payments-gateway:http-502-outage"


def test_escenario_2_cuenta_individual_bloqueada(client: TestClient) -> None:
    response = client.post(
        "/v1/triage",
        json={
            "incident_id": "INC-1002",
            "raw_text": "La cuenta está bloqueada hoy y no puedo ingresar",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "P2"
    assert body["recommended_team"] == "Security-IAM"
    assert body["severity"] != "P0"


@pytest.mark.parametrize(
    "payload",
    [
        {"incident_id": "INC-1001", "raw_text": "   "},
        {"incident_id": "", "raw_text": "HTTP 502 Bad Gateway en pasarela de pagos"},
    ],
)
def test_escenario_3_entradas_invalidas(client: TestClient, payload: dict) -> None:
    response = client.post("/v1/triage", json=payload)

    assert response.status_code == 422


def test_escenario_4_paridad_cli(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_app,
        [
            "triage",
            "--incident-id",
            "INC-1001",
            "--raw-text",
            "HTTP 502 Bad Gateway en pasarela de pagos",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["incident_id"] == "INC-1001"
    assert payload["severity"] == "P0"
    assert payload["recommended_team"] == "Backend-Core"
    assert payload["component"] == "payments-gateway"
    assert payload["duplicate_group_key"] == "payments-gateway:http-502-outage"

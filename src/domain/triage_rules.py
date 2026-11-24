"""Motor determinista de clasificación y enrutamiento de incidentes (IncidentOps).

Refactorización de la Semana 1 (Reto 1). Correcciones respecto a la versión legacy:
1. La severidad se decide por IMPACTO REAL (alcance global vs. cuenta individual vs.
   staging), no por palabras sueltas como "hoy" o "urgente".
2. Se añade `recommended_team` restringido a los 4 equipos válidos
   (`Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`).
3. Se añade `duplicate_group_key` normalizada `<component>:<symptom_category>` para
   detectar incidentes duplicados del mismo problema subyacente.

Decisiones de clasificación acordadas por Self-Consistency + Chain-of-Thought
(documentadas en CONTEXT_LOG.md):
- INC-1002 (una sola cuenta bloqueada) -> P2, NO P0 por la palabra "hoy".
- INC-1007 (company_id en URL expone facturas de otra empresa) -> P1 de seguridad, NO P3.
- INC-1009 (export Excel lenta que sí descarga) -> P2 de rendimiento, NO P0 por "hoy".
- INC-1001 / INC-1006 -> mismo grupo `payments-gateway:http-502-outage`.
- INC-1003 / INC-1008 -> mismo grupo `reporting-api:latency-high`.
"""

import json
from pathlib import Path
from typing import Dict, List

from src.domain.models import SeverityLevel, TeamName, TriageResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_incidents.json"

# Enrutamiento determinista: cada componente tiene un único equipo de guardia.
COMPONENT_TEAM: Dict[str, TeamName] = {
    "payments-gateway": "Backend-Core",
    "auth-identity": "Security-IAM",
    "security-authz": "Security-IAM",
    "database-cluster": "Data-DBA",
    "reporting-api": "Data-DBA",
    "infra-certificates": "Platform-SRE",
    "frontend-ui": "Backend-Core",
}


def _detect_component(text_lower: str) -> str:
    """Determina el componente afectado priorizando señales de mayor especificidad."""
    if "company_id" in text_lower or (
        "factura" in text_lower and ("otra" in text_lower or "organiz" in text_lower)
    ):
        return "security-authz"
    if (
        "502" in text_lower
        or "pasarela" in text_lower
        or "gateway de pago" in text_lower
        or "cobro" in text_lower
        or "pagar" in text_lower
        or "tarjeta" in text_lower
    ):
        return "payments-gateway"
    if "cuenta" in text_lower and (
        "bloquead" in text_lower or "ingresar" in text_lower or "acceder" in text_lower
    ):
        return "auth-identity"
    if "postgresql" in text_lower or "conexiones" in text_lower:
        return "database-cluster"
    if "certificado" in text_lower or "tls" in text_lower:
        return "infra-certificates"
    if "color" in text_lower or "botón" in text_lower or "boton" in text_lower:
        return "frontend-ui"
    return "reporting-api"


def _detect_severity(text_lower: str, component: str) -> SeverityLevel:
    """Asigna severidad por impacto real, no por palabras aisladas de urgencia."""
    # Fuga de datos entre organizaciones: riesgo de seguridad amplio -> P1.
    if component == "security-authz":
        return "P1"

    # Caída global de un servicio crítico (pagos indisponibles para todos) -> P0.
    global_outage = (
        "todas las transacciones" in text_lower
        or "ningún comercio" in text_lower
        or "ningun comercio" in text_lower
        or "cayó la pasarela" in text_lower
        or "cayo la pasarela" in text_lower
        or ("502" in text_lower and ("pagar" in text_lower or "cobrar" in text_lower))
        or (
            component == "payments-gateway"
            and ("502" in text_lower or "bad gateway" in text_lower)
        )
    )
    if global_outage:
        return "P0"

    # Cuenta individual bloqueada: acceso degradado, sin outage global -> P2.
    if component == "auth-identity" and "bloquead" in text_lower:
        return "P2"

    # Saturación de recursos / timeouts: degradación grave -> P1.
    if "94%" in text_lower or "timeout" in text_lower:
        return "P1"

    # Lentitud perceptible pero funcional -> P2.
    if (
        "segundos" in text_lower
        or "lenta" in text_lower
        or "tarda" in text_lower
        or "lentitud" in text_lower
    ):
        return "P2"

    # Individual, cosmético o preventivo -> P3.
    return "P3"


def _detect_symptom_category(text_lower: str) -> str:
    """Normaliza la categoría del síntoma para la clave de duplicados."""
    if "502" in text_lower or "bad gateway" in text_lower:
        return "http-502-outage"
    if (
        "lenta" in text_lower
        or "segundos" in text_lower
        or "tarda" in text_lower
        or "lentitud" in text_lower
    ):
        return "latency-high"
    if "bloquead" in text_lower:
        return "account-locked"
    if "company_id" in text_lower:
        return "idor-cross-tenant"
    if "94%" in text_lower or "timeout" in text_lower:
        return "resource-saturation"
    if "certificado" in text_lower or "tls" in text_lower:
        return "cert-expiry"
    if "color" in text_lower or "botón" in text_lower or "boton" in text_lower:
        return "ui-cosmetic"
    return "other"


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte de incidente por impacto real y lo enruta a un equipo.

    Devuelve severidad (P0–P3), componente, equipo recomendado (uno de los 4 válidos)
    y una clave de duplicados `<component>:<symptom_category>`.
    """
    text_lower = raw_text.lower()

    component = _detect_component(text_lower)
    severity = _detect_severity(text_lower, component)
    recommended_team = COMPONENT_TEAM[component]
    symptom_category = _detect_symptom_category(text_lower)
    duplicate_group_key = f"{component}:{symptom_category}"

    rationale = (
        f"Impacto evaluado antes que palabras clave -> severidad={severity}, "
        f"componente={component}, equipo={recommended_team}, "
        f"grupo_duplicados={duplicate_group_key}."
    )

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        rationale=rationale,
        recommended_team=recommended_team,
        duplicate_group_key=duplicate_group_key,
    )


def _run_triage_audit() -> None:
    """Ejecuta el motor refactorizado sobre los 10 incidentes y muestra los duplicados."""
    incidents: List[Dict[str, str]] = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))

    print("=== Motor de Triaje Refactorizado (`src/domain/triage_rules.py`) ===")
    print(f"{'ID':<9}| {'Sev':<4}| {'Componente':<18}| {'Equipo':<13}| {'duplicate_group_key'}")
    print("-" * 92)

    groups: Dict[str, List[str]] = {}
    for item in incidents:
        result = classify_incident_report(item["id"], item["raw_text"])
        groups.setdefault(result.duplicate_group_key or "", []).append(result.incident_id)
        print(
            f"{result.incident_id:<9}| {result.severity:<4}| {result.component:<18}| "
            f"{str(result.recommended_team):<13}| {result.duplicate_group_key}"
        )

    print("-" * 92)
    print("Grupos de duplicados detectados (clave compartida por 2+ incidentes):")
    any_dup = False
    for key, ids in groups.items():
        if len(ids) > 1:
            any_dup = True
            print(f"  {key} -> {ids}")
    if not any_dup:
        print("  (ninguno)")


if __name__ == "__main__":
    _run_triage_audit()

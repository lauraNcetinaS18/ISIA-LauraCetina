"""Módulo determinista para el cálculo y evaluación de acuerdos de nivel de servicio (SLA).

Refactorización de la Semana 1 (Reto 2 — ADR-002). Corrige el bug de horario hábil:
- P0 y P1 (`operates_24x7=True`): tiempo calendario continuo (24/7).
- P2 y P3 (`operates_24x7=False`): solo minutos dentro del horario hábil
  (Lunes a Viernes, 08:00–18:00; máximo 600 min hábiles por día; fines de semana no descuentan).

Escalamiento preventivo: `requires_escalation=True` cuando el incidente no está RESUELTO
y (ya incumplió el SLA) o (alcanzó/superó el 75% de su tiempo permitido).

El algoritmo de minutos hábiles es O(D), donde D es el número de días entre la creación y la
evaluación, y no usa librerías externas (solo `datetime` de la stdlib).
"""

from datetime import datetime, timedelta
from typing import Dict

from src.models import Incident, SLAEvaluation, SLARule, SeverityLevel

WORK_START_HOUR = 8
WORK_END_HOUR = 18
WORK_MINUTES_PER_DAY = (WORK_END_HOUR - WORK_START_HOUR) * 60  # 600

SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}


def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]


def _continuous_minutes_between(start: datetime, end: datetime) -> int:
    """Minutos de calendario continuo (24/7) entre dos marcas de tiempo."""
    return int((end - start).total_seconds() // 60)


def business_minutes_between(start: datetime, end: datetime) -> int:
    """Minutos hábiles (Lunes–Viernes, 08:00–18:00) entre `start` y `end`.

    Recorre día por día desde la creación hasta la evaluación (O(D)). Para cada día
    laborable intersecta el intervalo [start, end] con la ventana [08:00, 18:00].
    Sábados y domingos no suman tiempo. Horas fuera de ventana (p. ej. un viernes a
    las 18:30) tampoco suman.
    """
    if end <= start:
        return 0

    total = 0
    cursor = start
    while cursor < end:
        if cursor.weekday() < 5:  # Lunes=0 ... Viernes=4
            day_open = cursor.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
            day_close = cursor.replace(hour=WORK_END_HOUR, minute=0, second=0, microsecond=0)
            window_start = max(cursor, day_open)
            window_end = min(end, day_close)
            if window_end > window_start:
                total += int((window_end - window_start).total_seconds() // 60)
        # Avanzar al inicio (08:00) del siguiente día de calendario.
        cursor = (cursor + timedelta(days=1)).replace(
            hour=WORK_START_HOUR, minute=0, second=0, microsecond=0
        )
    return total


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Usa tiempo 24/7 para severidades con `operates_24x7=True` (P0/P1) y solo horario
    hábil para las de `operates_24x7=False` (P2/P3).

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    end_time = incident.resolved_at or reference_time

    if end_time < incident.created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    if rule.operates_24x7:
        elapsed_minutes = _continuous_minutes_between(incident.created_at, end_time)
    else:
        elapsed_minutes = business_minutes_between(incident.created_at, end_time)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    # El escalamiento sigue activo aunque el SLA ya se haya incumplido (bug corregido:
    # antes se apagaba con `not is_breached`).
    requires_escalation = incident.status != "RESOLVED" and (
        is_breached or elapsed_minutes >= escalation_limit
    )

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
    )


def _run_demo() -> None:
    """Verifica de forma determinista >=5 casos borde del cálculo de SLA."""
    print("=== Verificación de Cálculo de SLA en Horario Hábil (>=5 casos borde) ===")
    print(f"{'Estado':<7}| {'Caso':<52}| {'elapsed':<8}| {'esperado':<9}| breach | escal")
    print("-" * 100)

    casos = [
        (
            "P2 viernes 17:00 -> lunes 09:00 (1h vie + 1h lun)",
            Incident("INC-A", "lentitud", "reporting-api", "P2", "OPEN",
                     datetime(2026, 11, 6, 17, 0)),
            datetime(2026, 11, 9, 9, 0),
            120,
        ),
        (
            "P2 viernes 18:30 (fuera horario) -> lunes 08:30",
            Incident("INC-B", "lentitud", "reporting-api", "P2", "OPEN",
                     datetime(2026, 11, 6, 18, 30)),
            datetime(2026, 11, 9, 8, 30),
            30,
        ),
        (
            "P3 creado sábado 10:00 -> lunes 10:00 (solo 2h lunes)",
            Incident("INC-C", "preventivo", "reporting-api", "P3", "OPEN",
                     datetime(2026, 11, 7, 10, 0)),
            datetime(2026, 11, 9, 10, 0),
            120,
        ),
        (
            "P0 24/7 viernes 17:00 -> lunes 09:00 (calendario)",
            Incident("INC-D", "pagos", "payments-gateway", "P0", "OPEN",
                     datetime(2026, 11, 6, 17, 0)),
            datetime(2026, 11, 9, 9, 0),
            3840,
        ),
        (
            "P2 cruza 2 fines de semana: viernes -> viernes sig.",
            Incident("INC-E", "lentitud", "reporting-api", "P2", "OPEN",
                     datetime(2026, 11, 6, 17, 0)),
            datetime(2026, 11, 13, 17, 0),
            3000,
        ),
        (
            "P1 24/7 resuelto en 30 min (sin escalar)",
            Incident("INC-F", "saturación", "database-cluster", "P1", "RESOLVED",
                     datetime(2026, 11, 4, 10, 0),
                     resolved_at=datetime(2026, 11, 4, 10, 30)),
            datetime(2026, 11, 4, 12, 0),
            30,
        ),
    ]

    all_ok = True
    for desc, incident, ref, esperado in casos:
        ev = evaluate_sla_status(incident, reference_time=ref)
        ok = ev.elapsed_minutes == esperado
        all_ok = all_ok and ok
        estado = "OK" if ok else "FALLA"
        print(
            f"{estado:<7}| {desc:<52}| {ev.elapsed_minutes:<8}| {esperado:<9}| "
            f"{str(ev.is_breached):<6} | {ev.requires_escalation}"
        )

    print("-" * 100)
    print("RESULTADO:", "TODOS LOS CASOS PASAN" if all_ok else "HAY FALLAS")


if __name__ == "__main__":
    _run_demo()

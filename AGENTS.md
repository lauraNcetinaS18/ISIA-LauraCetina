# AGENTS.md

## Setup / execution

- The repo root **is** the starter project; ignore README's `cd week-1/starter-project` (that path does not exist). Run everything from the repo root as `python -m src...`, not as scripts.
- Python 3.10+ with `uv`; runtime deps are `tiktoken`, `fastapi`, `uvicorn`, `pydantic>=2`, `typer`; dev deps are `pytest`, `httpx`. Always use `uv run` — outside it, `src/context_audit.py` silently falls back to an approximate BPE estimator.
- `pytest` is configured in `pyproject.toml` (`pythonpath = ["."]`, `testpaths = ["tests"]`). No lint/typecheck/codegen/CI config exists.

## Verification

- `uv run pytest` — 5 BDD cases from `specs/001-triage-endpoint-manual.md`; all must pass.
- `uv run python -m src.domain.sla_calculator` — 6 edge cases; require `RESULTADO: TODOS LOS CASOS PASAN`.
- `uv run python -m src.domain.triage_rules` — 10 rows; duplicate groups must include `payments-gateway:http-502-outage` (INC-1001/1006) and `reporting-api:latency-high` (INC-1003/1008/1009).
- `uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "HTTP 502 Bad Gateway en pasarela de pagos"` — JSON with `severity="P0"` and `recommended_team="Backend-Core"`.
- `uv run python -m src.context_audit --symbol evaluate_sla_status` (also `classify_incident_report`, `get_active_incidents_summary`); `uv run python -m src.context_audit --compare-formats` ignores `--symbol`.
- `uv run python -m src.incident_repository` — in-memory SQLite, 10k rows / 20 iterations by default; override with `--records N --iterations N` for quick checks. Full scan + N+1 are intentional and timings are informational; do not refactor unless asked.

## Architecture / invariants

- Hexagonal architecture is accepted in `docs/adr/003-arquitectura-hexagonal.md`: `src/domain/` holds dataclasses, `Literal` unions and pure rules; `src/application/services.py` owns `IncidentService` and `ValidationError`; `src/adapters/inbound/api/` owns FastAPI/Pydantic; `src/adapters/inbound/cli.py` owns Typer; `src/adapters/outbound/` is empty in H001.
- `src/domain/sla_calculator.py` owns `SLA_POLICY_TABLE` and all SLA math; `src/domain/triage_rules.py` reads `data/sample_incidents.json`; `src/incident_repository.py` is the only SQLite writer and remains temporarily in `src/`; `src/context_audit.py` is an AST-based LSP *simulator*, not a real LSP client, and globs `src/**/*.py`.
- SLA (accepted ADR-002): P0/P1 = 24/7; P2/P3 = Mon–Fri 08:00–18:00 only (600 min/day, weekends 0). Breach is `elapsed > max`; escalation requires `status != RESOLVED` and (`is_breached` or `elapsed >= 75%`) and stays on after breach. No holidays/timezones; keep SLA math stdlib-only and O(D).
- Triage: classify by real impact, never by words like `hoy`/`urgente` — INC-1002→P2, INC-1007→P1, INC-1009→P2; HTTP 502 in the payments gateway → P0 and `payments-gateway:http-502-outage`. Teams are only `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`; duplicate key is `<component>:<symptom_category>`.
- No adapter reimplements severity, team or duplicate rules; REST and CLI delegate to `IncidentService` and map `ValidationError` to HTTP 422 / CLI exit 1 (constitution 2.0.0).
- Code/docstrings/console output are in Spanish; preserve that style.

## Docs quirks

- README still describes triage and SLA as buggy legacy versions; the code plus `docs/adr/002-calculo-sla-horario-habil.md` and `specs/001-triage-endpoint-manual.md` are current truth.
- `docs/ROADMAP.md` is aspirational; FastAPI/Typer now exist, but no container runtime does.
- `CONTEXT_LOG.md` is the completed assignment record; `CONTEXT_LOG_TEMPLATE.md` and `docs/adr/000-template.md` are templates — don't overwrite them with generated content unless asked.
- Token counts in `CONTEXT_LOG.md` are historical: adding files under `src/`, `data/`, or `docs/adr/` changes `context_audit` brute-force numbers, so don't chase the old values.

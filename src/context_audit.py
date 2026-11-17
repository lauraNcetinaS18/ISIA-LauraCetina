"""Herramienta de Auditoría de Contexto con `tiktoken`: Fuerza Bruta vs. Grep vs. Semántica (LSP).

Implementa el experimento práctico de la Fase 1 de la Semana 1 basado en:
1. Andrej Karpathy — Context Engineering: llenar la ventana de contexto exactamente
   con la información necesaria para el siguiente paso.
2. Vinodh Thiagarajan — "LSP: The Protocol Your IDE Uses Every Day — And Now Your AI
   Agent Does Too": cómo las operaciones semánticas (`documentSymbol`, `goToDefinition`,
   `findReferences`, `hover`) reducen drásticamente el consumo de tokens frente a `read`/`glob`.
"""

import argparse
import ast
import json
from pathlib import Path
import re
from typing import Dict, List, Tuple

try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def count_tokens(text: str, encoding_name: str = "o200k_base") -> Tuple[int, str]:
    """Calcula la cantidad exacta de tokens usando `tiktoken` (o estimador BPE si no está activo).

    Returns:
        Tupla (cantidad_de_tokens, nombre_del_metodo_usado).
    """
    if not text:
        return 0, encoding_name

    if tiktoken is not None:
        try:
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text)), f"tiktoken ({encoding_name})"
        except Exception:
            pass

    # Respaldo BPE local en caso de ejecutar fuera del entorno virtual de `uv`
    chunks = re.findall(r"[A-Za-z_]+|\d+|\s+|[^\w\s]", text)
    approx = 0
    for chunk in chunks:
        if chunk.isspace():
            approx += max(1, len(chunk) // 4)
        elif len(chunk) > 8:
            approx += 2
        else:
            approx += 1
    return approx, "estimador-bpe-local (ejecuta con `uv run` para tiktoken exacto)"


def collect_brute_force_context() -> Tuple[str, List[str]]:
    """Nivel 1: Simula `glob` + `read` sobre todos los archivos del repositorio."""
    collected_parts: List[str] = []
    included_files: List[str] = []

    for pattern in ("src/*.py", "data/*.json", "docs/adr/*.md"):
        for filepath in sorted(PROJECT_ROOT.glob(pattern)):
            rel = filepath.relative_to(PROJECT_ROOT)
            content = filepath.read_text(encoding="utf-8")
            included_files.append(str(rel))
            collected_parts.append(f"--- FILE: {rel} ---\n{content}\n")

    return "\n".join(collected_parts), included_files


def collect_grep_and_read_context(target_symbol: str) -> Tuple[str, List[str]]:
    """Nivel 2: Simula un agente que hace `grep <symbol>` y luego `read_file` de cada archivo coincidente."""
    collected_parts: List[str] = []
    matched_files: List[str] = []

    for py_file in sorted((PROJECT_ROOT / "src").glob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        if target_symbol in content or py_file.name == "models.py":
            rel = py_file.relative_to(PROJECT_ROOT)
            matched_files.append(str(rel))
            collected_parts.append(f"--- FILE: {rel} ---\n{content}\n")

    return "\n".join(collected_parts), matched_files


def collect_lsp_semantic_context(target_symbol: str) -> str:
    """Nivel 3: Extrae únicamente definición, tipos relacionados y referencias vía AST (emulando LSP).

    Equivale a ejecutar en un servidor LSP:
    1. `workspace/symbol` & `textDocument/definition` para obtener el cuerpo exacto de `target_symbol`.
    2. `textDocument/hover` para extraer las firmas de tipos (`Incident`, `SLARule`, `SLAEvaluation`, `TriageResult`).
    3. `textDocument/references` para ubicar únicamente las líneas donde se invoca `target_symbol`.
    """
    definitions: List[str] = []
    type_signatures: List[str] = []
    references: List[str] = []
    related_types = {"Incident", "SLARule", "SLAEvaluation", "TriageResult", "SLA_POLICY_TABLE"}

    for py_file in sorted((PROJECT_ROOT / "src").glob("*.py")):
        rel_path = py_file.relative_to(PROJECT_ROOT)
        source = py_file.read_text(encoding="utf-8")
        source_lines = source.splitlines()
        tree = ast.parse(source, filename=str(rel_path))

        for node in ast.walk(tree):
            # 1. textDocument/definition del símbolo objetivo o funciones auxiliares directas
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == target_symbol or (
                    target_symbol == "evaluate_sla_status"
                    and node.name == "get_sla_rule_for_severity"
                ):
                    segment = ast.get_source_segment(source, node)
                    definitions.append(
                        f"# [LSP textDocument/definition] {rel_path}:{node.lineno}\n{segment}"
                    )
                elif node.name in related_types:
                    segment = ast.get_source_segment(source, node)
                    type_signatures.append(
                        f"# [LSP textDocument/hover type] {rel_path}:{node.lineno}\n{segment}"
                    )

            # 2. Capturar constantes de política asociadas (ej. SLA_POLICY_TABLE)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in related_types:
                    segment = ast.get_source_segment(source, node)
                    type_signatures.append(
                        f"# [LSP textDocument/hover symbol] {rel_path}:{node.lineno}\n{segment}"
                    )

            # 3. textDocument/references: puntos donde se invoca el símbolo
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == target_symbol and hasattr(node, "lineno"):
                    start = max(0, node.lineno - 2)
                    end = min(len(source_lines), (node.end_lineno or node.lineno) + 1)
                    snippet = "\n".join(
                        f"  L{idx + 1}: {source_lines[idx]}" for idx in range(start, end)
                    )
                    references.append(
                        f"# [LSP textDocument/references] {rel_path}:{node.lineno}\n{snippet}"
                    )

    sections = [
        f"<lsp_context symbol=\"{target_symbol}\">",
        "  <!-- 1. Definiciones de Tipos y Políticas (LSP Hover / Type Definition) -->",
        "\n\n".join(type_signatures),
        "\n  <!-- 2. Definición Exacta del Símbolo (LSP GoToDefinition) -->",
        "\n\n".join(definitions),
        "\n  <!-- 3. Referencias de Invocación en el Proyecto (LSP FindReferences) -->",
        "\n\n".join(references),
        "</lsp_context>",
    ]
    return "\n".join(sections)


def run_symbol_audit(symbol: str) -> None:
    brute_text, all_files = collect_brute_force_context()
    grep_text, grep_files = collect_grep_and_read_context(target_symbol=symbol)
    lsp_text = collect_lsp_semantic_context(target_symbol=symbol)

    brute_tokens, tokenizer_label = count_tokens(brute_text)
    grep_tokens, _ = count_tokens(grep_text)
    lsp_tokens, _ = count_tokens(lsp_text)

    savings_vs_brute = ((brute_tokens - lsp_tokens) / brute_tokens) * 100 if brute_tokens else 0.0
    savings_vs_grep = ((grep_tokens - lsp_tokens) / grep_tokens) * 100 if grep_tokens else 0.0

    print("=" * 84)
    print(f" AUDITORÍA DE CONTEXT ENGINEERING: Símbolo objetivo `{symbol}`")
    print(f" Tokenizador activo: {tokenizer_label}")
    print("=" * 84)
    print(f"{'Estrategia':<38} | {'Alcance':<18} | {'Caracteres':<10} | {'Tokens'}")
    print("-" * 84)
    print(
        f"{'1. Fuerza Bruta (glob + read todo)':<38} | {f'{len(all_files)} archivos':<18} | "
        f"{len(brute_text):<10} | {brute_tokens} tokens"
    )
    print(
        f"{'2. Búsqueda Textual (grep + read .py)':<38} | {f'{len(grep_files)} archivos .py':<18} | "
        f"{len(grep_text):<10} | {grep_tokens} tokens"
    )
    print(
        f"{'3. Semántica vía LSP (AST/Symbols)':<38} | {'Definición+Refs':<18} | "
        f"{len(lsp_text):<10} | {lsp_tokens} tokens"
    )
    print("-" * 84)
    print(f"-> Reducción LSP vs. Fuerza Bruta (`glob` + `read`): {savings_vs_brute:.1f}% menos tokens")
    print(f"-> Reducción LSP vs. Búsqueda (`grep` + `read` .py): {savings_vs_grep:.1f}% menos tokens\n")
    print("=== Payload Semántico Extraído estilo LSP (Listo para inyectar al LLM) ===")
    print(lsp_text)


def run_format_comparison() -> None:
    sample_path = PROJECT_ROOT / "data" / "sample_incidents.json"
    records: List[Dict[str, str]] = json.loads(sample_path.read_text(encoding="utf-8"))

    json_pretty = json.dumps(records, indent=2, ensure_ascii=False)
    json_compact = json.dumps(records, separators=(",", ":"), ensure_ascii=False)

    yaml_lines = []
    for item in records:
        yaml_lines.append(
            f"- id: {item['id']}\n  reporter: {item['reporter']}\n"
            f"  created_at: {item['created_at']}\n  raw_text: {item['raw_text']}"
        )
    yaml_text = "\n".join(yaml_lines)

    csv_lines = ["id|reporter|created_at|raw_text"]
    for item in records:
        csv_lines.append(
            f"{item['id']}|{item['reporter']}|{item['created_at']}|{item['raw_text']}"
        )
    csv_text = "\n".join(csv_lines)

    formats = [
        ("JSON Indentado (indent=2)", json_pretty),
        ("JSON Compacto (minified)", json_compact),
        ("YAML Equivalente", yaml_text),
        ("CSV Delimitado por '|'", csv_text),
    ]

    _, tokenizer_label = count_tokens(json_pretty)
    print("=" * 74)
    print(" IMPACTO DEL FORMATO DE DATOS EN LA VENTANA DE CONTEXTO (10 Incidentes)")
    print(f" Tokenizador activo: {tokenizer_label}")
    print("=" * 74)
    print(f"{'Formato de Serialización':<30} | {'Caracteres':<12} | {'Tokens'}")
    print("-" * 74)
    for label, content in formats:
        tok_count, _ = count_tokens(content)
        print(f"{label:<30} | {len(content):<12} | {tok_count} tokens")
    print("-" * 74)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditoría de Context Engineering: LSP vs Grep+Read vs Fuerza Bruta (glob/read)"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="evaluate_sla_status",
        help="Nombre de la función o clase a inspeccionar semánticamente",
    )
    parser.add_argument(
        "--compare-formats",
        action="store_true",
        help="Compara el consumo de tokens de distintos formatos de datos (JSON, YAML, CSV)",
    )
    args = parser.parse_args()

    if args.compare_formats:
        run_format_comparison()
    else:
        run_symbol_audit(symbol=args.symbol)


if __name__ == "__main__":
    main()

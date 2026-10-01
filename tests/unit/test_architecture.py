import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
PACKAGE = "agentefinanciero"
STDLIB = set(sys.stdlib_module_names)

# Capa -> paquetes del proyecto que puede importar. Cualquier import externo al stdlib
# (FastAPI, LangChain, LangGraph, LangSmith, Pydantic...) solo se permite en adapters/ y config/.
ALLOWED_INTERNAL = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "adapters": {"domain", "application", "adapters"},
}
THIRD_PARTY_ALLOWED = {"adapters", "config"}


def imports_of(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path}: imports relativos no permitidos"
            modules.add(node.module or "")
    return modules


def python_files(layer: str) -> list[Path]:
    return sorted((SRC / PACKAGE / layer).rglob("*.py"))


def test_layers_are_discovered():
    for layer in (*ALLOWED_INTERNAL, "config"):
        assert python_files(layer), f"no se encontraron módulos en {layer}/"


@pytest.mark.parametrize("layer", ALLOWED_INTERNAL)
def test_layer_only_imports_allowed_project_layers(layer):
    violations = []
    for path in python_files(layer):
        for module in imports_of(path):
            parts = module.split(".")
            if parts[0] == PACKAGE and (len(parts) < 2 or parts[1] not in ALLOWED_INTERNAL[layer]):
                violations.append(f"{path.relative_to(SRC)} importa {module}")
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("layer", [layer for layer in ALLOWED_INTERNAL if layer not in THIRD_PARTY_ALLOWED])
def test_core_layers_import_only_stdlib_and_project(layer):
    violations = []
    for path in python_files(layer):
        for module in imports_of(path):
            top = module.split(".")[0]
            if top != PACKAGE and top not in STDLIB:
                violations.append(f"{path.relative_to(SRC)} importa {module}")
    assert not violations, "\n".join(violations)


def test_only_container_and_main_wire_adapters():
    """Fuera de adapters/, solo config/container.py y main.py (router) conocen a los adaptadores."""
    allowed = {SRC / PACKAGE / "config" / "container.py", SRC / PACKAGE / "main.py"}
    files = [*python_files("config"), *python_files("domain"), *python_files("application")]
    files.append(SRC / PACKAGE / "main.py")
    violations = [
        f"{path.relative_to(SRC)} importa {module}"
        for path in files
        if path not in allowed
        for module in imports_of(path)
        if module.startswith(f"{PACKAGE}.adapters")
    ]
    assert not violations, "\n".join(violations)


def test_adapters_do_not_depend_on_config_or_main():
    violations = [
        f"{path.relative_to(SRC)} importa {module}"
        for path in python_files("adapters")
        for module in imports_of(path)
        if module.startswith((f"{PACKAGE}.config", f"{PACKAGE}.main"))
    ]
    assert not violations, "\n".join(violations)

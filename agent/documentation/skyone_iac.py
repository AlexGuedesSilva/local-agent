"""Utilities for interpreting exported Skyone Studio IAC JSON."""

from __future__ import annotations

import html
import json
from html.parser import HTMLParser
from typing import Any


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(value: str) -> str:
    parser = _HTMLText()
    parser.feed(html.unescape(value))
    return " ".join(" ".join(parser.parts).split())


def parse_skyone_iac(content: str) -> list[dict[str, Any]]:
    """Parse and validate the module list used by Skyone Studio IAC exports."""
    try:
        data: Any = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"JSON inválido na linha {error.lineno}, coluna {error.colno}."
        ) from error
    if isinstance(data, dict):
        data = data.get("modules")
    if not isinstance(data, list) or not data:
        raise ValueError("O IAC precisa conter uma lista não vazia de módulos.")

    module_ids: set[str] = set()
    for index, module in enumerate(data, start=1):
        if not isinstance(module, dict):
            raise ValueError(f"O item {index} não é um módulo JSON.")
        module_id = module.get("module_id")
        if not isinstance(module_id, str) or not module_id.strip():
            raise ValueError(f"O módulo {index} não possui module_id.")
        if module_id in module_ids:
            raise ValueError(f"O IAC contém module_id duplicado: {module_id}.")
        module_ids.add(module_id)
        if not isinstance(module.get("name"), str) or not module["name"].strip():
            raise ValueError(f"O módulo {module_id} não possui nome.")
    return data


def module_parameters(module: dict[str, Any]) -> dict[str, Any]:
    parameters = module.get("parameters", [])
    if not isinstance(parameters, list):
        return {}
    return {
        parameter["name"]: parameter.get("value", parameter.get("smop"))
        for parameter in parameters
        if isinstance(parameter, dict) and isinstance(parameter.get("name"), str)
    }


def analyze_skyone_iac(modules: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract source-backed integration facts and flag gaps for human review."""
    triggers = [module for module in modules if module.get("type") == "trigger"]
    connectors = [module for module in modules if module.get("type") == "connector"]
    transforms = [module for module in modules if module.get("subtype") == "transform"]
    xml_modules = [module for module in modules if module.get("subtype") == "xml"]
    returns = [module for module in modules if module.get("subtype") == "return"]
    trigger = triggers[0] if triggers else {}
    trigger_parameters = module_parameters(trigger)
    jsonata = "\n".join(
        str(module_parameters(module).get("jsonata", "")) for module in transforms
    )
    names_and_content = " ".join(
        f"{module.get('name', '')} {module.get('information', '')}"
        for module in modules
    )
    source_hint = "SAP" if "SAP" in (jsonata + names_and_content).upper() else "Não identificado"
    destination_hint = "Nexxa/DHL Chile" if any(
        word in names_and_content.casefold() for word in ("nexxa", "dhl")
    ) else "Não identificado"

    module_ids = {str(module["module_id"]) for module in modules}
    warnings: list[str] = []
    for module in modules:
        origin = module.get("origin")
        if isinstance(origin, str) and origin not in ("", "none") and origin not in module_ids:
            warnings.append(
                f"A origem configurada para {module['name']} é {origin}, que não aparece como módulo neste export."
            )
    description_text = " ".join(
        plain_text(str(module.get("information", ""))) for module in modules
    ).casefold()
    upper_content = (jsonata + names_and_content).upper()
    if "entrega de saída" in description_text and "PRODUCT_MASTER_DATA" in upper_content:
        warnings.append(
            "A descrição do gatilho menciona entrega de saída, enquanto a estrutura indica dados mestres de produto/material."
        )
    if not warnings:
        warnings.append("Nenhuma inconsistência estrutural evidente foi detectada automaticamente.")

    return {
        "modules": modules,
        "trigger": trigger,
        "trigger_parameters": trigger_parameters,
        "endpoint": trigger_parameters.get("url", "Não informado no IAC"),
        "source_hint": source_hint,
        "destination_hint": destination_hint,
        "connectors": connectors,
        "transform_modules": transforms,
        "xml_modules": xml_modules,
        "return_modules": returns,
        "warnings": warnings,
        "jsonata": jsonata,
    }

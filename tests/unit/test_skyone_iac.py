import json

import pytest

from agent.documentation.skyone_iac import analyze_skyone_iac, parse_skyone_iac, plain_text


def test_parse_skyone_iac_accepts_module_array_and_strips_html() -> None:
    modules = [{"module_id": "trigger-1", "name": "API Gateway", "type": "trigger", "information": "<p>Entrada <b>HTTP</b></p>"}]

    parsed = parse_skyone_iac(json.dumps(modules))

    assert parsed == modules
    assert plain_text(modules[0]["information"]) == "Entrada HTTP"


def test_parse_skyone_iac_accepts_modules_envelope() -> None:
    module = {"module_id": "m1", "name": "Passo"}
    assert parse_skyone_iac(json.dumps({"modules": [module]})) == [module]


@pytest.mark.parametrize(
    "content",
    ["{broken", "{}", "[]", json.dumps([{"name": "sem id"}]),
     json.dumps([{"module_id": "m", "name": "um"}, {"module_id": "m", "name": "dois"}])],
)
def test_parse_skyone_iac_rejects_invalid_exports(content: str) -> None:
    with pytest.raises(ValueError):
        parse_skyone_iac(content)


def test_analysis_flags_external_origin_and_business_description_conflict() -> None:
    modules = [
        {"module_id": "tr", "name": "API Gateway", "type": "trigger", "information": "entrega de saída", "parameters": [{"name": "url", "value": "https://example.test/qa"}]},
        {"module_id": "tx", "name": "Transform", "subtype": "transform", "origin": "missing", "parameters": [{"name": "jsonata", "value": "MT_PRODUCT_MASTER_DATA_SAP_REQ"}]},
    ]

    result = analyze_skyone_iac(modules)

    assert result["endpoint"] == "https://example.test/qa"
    assert result["source_hint"] == "SAP"
    assert any("não aparece como módulo" in warning for warning in result["warnings"])
    assert any("enquanto a estrutura indica" in warning for warning in result["warnings"])

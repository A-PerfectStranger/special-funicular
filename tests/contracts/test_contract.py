from pathlib import Path
from unittest.mock import patch

import yaml
from django.db import OperationalError
from django.test import Client
from jsonschema import Draft202012Validator


def test_technical_contract_and_failure_response() -> None:
    spec = yaml.safe_load(Path("tests/contracts/openapi.yaml").read_text())
    client = Client()
    for path in ["/health/live", "/v1/capabilities"]:
        schema = spec["paths"][path]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        Draft202012Validator(schema).validate(client.get(path).json())
    with patch("core.views.connection.cursor", side_effect=OperationalError("private")):
        response = client.get("/health/ready")
    schema = spec["paths"]["/health/ready"]["get"]["responses"]["503"]["content"][
        "application/json"
    ]["schema"]
    Draft202012Validator(schema).validate(response.json())
    assert response.status_code == 503

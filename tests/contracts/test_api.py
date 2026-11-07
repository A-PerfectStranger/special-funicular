import json
from pathlib import Path

import jsonschema
import pytest
from django.test import Client

SPEC = json.loads(Path("tests/contracts/openapi.json").read_text())


@pytest.mark.parametrize(
    "path,schema", [("/health/live", "Live"), ("/v1/capabilities", "Capabilities")]
)
def test_public_contract(client: Client, path: str, schema: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    jsonschema.validate(response.json(), SPEC["components"]["schemas"][schema])
    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_readiness_contract(client: Client) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    jsonschema.validate(response.json(), SPEC["components"]["schemas"]["Ready"])

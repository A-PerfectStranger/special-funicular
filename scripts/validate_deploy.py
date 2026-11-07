"""Fail closed: configuration validation is never a deployment receipt."""

import argparse
import json
import re
from pathlib import Path
from typing import Any


def validate(config: dict[str, Any], target: str) -> list[str]:
    errors = []
    if config.get("environment") != target or target not in {"staging", "production"}:
        errors.append("entorno no coincide")
    if config.get("provider") != "aws":
        errors.append("proveedor debe ser aws")
    if config.get("configured") is not True:
        errors.append("destino bloqueado/no configurado")
    if not re.fullmatch(r"[0-9]{12}", str(config.get("account_id", ""))):
        errors.append("account_id ausente/invalido")
    if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-[0-9]", str(config.get("region", ""))):
        errors.append("region ausente/invalida")
    if not re.fullmatch(
        r"arn:aws:iam::" + str(config.get("account_id", "")) + r":role/[A-Za-z0-9+=,.@_/-]+",
        str(config.get("deploy_role_arn", "")),
    ):
        errors.append("rol OIDC ausente/invalido")
    if not re.fullmatch(r"https://[a-z0-9][a-z0-9.-]+", str(config.get("base_url", ""))):
        errors.append("base_url HTTPS requerida")
    budget = config.get("total_credit_limit_usd")
    if not isinstance(budget, (int, float)) or isinstance(budget, bool) or not 0 < budget <= 150:
        errors.append("limite total debe ser <= USD150")
    if config.get("synthetic_only") is not True:
        errors.append("E0 admite solo datos sinteticos")
    if config.get("pickup_enabled") is not False:
        errors.append("retiro debe permanecer deshabilitado")
    # No permitir que marcar configured=true finja infraestructura existente.
    if config.get("staging_evidence_verified") is not True:
        errors.append("falta evidencia de destino real, TLS, PostgreSQL y permisos")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=["staging", "production"])
    args = parser.parse_args()
    path = Path("infra/environments") / f"{args.environment}.json"
    try:
        config = json.loads(path.read_text())
        errors = validate(config, args.environment)
    except (OSError, ValueError, TypeError, AttributeError):
        errors = ["configuracion ausente o malformada"]
    if errors:
        print("DEPLOY BLOQUEADO: " + "; ".join(errors))
        return 2
    print("Configuracion valida; NO acredita despliegue ni permisos reales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

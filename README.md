# Retiro seguro de estudiantes

Monorepo Django/PostgreSQL y Expo SDK 56. E0 crea la base técnica;
**no autentica usuarios ni permite retiros**. Solo datos sintéticos.
El estado verificable y los bloqueos están en [PROGRESS.md](PROGRESS.md).

## Requisitos y arranque

Python 3.12, uv 0.13.5, Node 24.22.1/npm 11.9.0, Docker Engine con Compose.
OpenSSL 3 en PATH para los ensayos HTTPS locales de aceptación de staging.
Versiones Python en `uv.lock`, npm en `package-lock.json`, imágenes por digest.
No usar SQLite como sustituto de PostgreSQL para las pruebas.

```bash
cp .env.example .env
make install
make db
make migrate
make check
make run
```

En otra terminal: `npm run mobile:start`. Para el emulador Android:
`EXPO_PUBLIC_API_URL=http://10.0.2.2:8000 npm run mobile:start`.
HTTP se limita a desarrollo sintético local; los APK cloud exigen HTTPS.
No poner credenciales en variables `EXPO_PUBLIC_*`.

La base local expone únicamente `127.0.0.1:5432`. `infra/local/init.sql` crea
credenciales sintéticas distintas para migración y runtime; el runtime no es
propietario, superusuario ni BYPASSRLS y no puede crear tablas. La inicialización
solo corre sobre un volumen nuevo. No aplicar ese SQL en AWS. `docker compose down`
detiene la base sin borrar su volumen; no usar `down -v` sobre datos que se deban conservar.

## Comandos de desarrollo y comprobación

| Comando | Función |
| --- | --- |
| `make install` | Instalación congelada Python/npm. |
| `make db` / `make migrate` | PostgreSQL / migraciones con identidad separada. |
| `make lint` | Ruff, formato y ESLint. |
| `make typecheck` | mypy estricto y TypeScript. |
| `make test` | Unitarias, contratos, PostgreSQL/RLS y pruebas móvil. |
| `make check` | Todo lo anterior, checks Django, deriva de migraciones y compatibilidad Expo. |
| `make security` | pip-audit, npm audit y gitleaks 8.30.1 (instalar binario oficial en PATH). |
| `npm run mobile:export` | Compila el bundle Android/Hermes; no es un APK. |
| `make image` | Imagen no privilegiada, compartida por API y futuro worker. |
| `bash scripts/smoke_image.sh retiro-backend:<SHA>` | Probes reales de imagen, runtime sin credencial de migración y diagnóstico worker. |
| `make apk` | APK arm64 de desarrollo firmado con debug key, requiere Android SDK/JDK 21. |

`make security` necesita `work/` (crear con `mkdir -p work`). Instalar gitleaks
desde su release oficial y comprobar el checksum publicado; CI contiene los comandos.
Los escaneos no se sustituyen por mocks ni se ignoran fallos de dependencia.
Los overrides de Zod/glob/minimatch corrigen avisos transitivos sin cambiar SDK 56.
`vendor/deepmerge` conserva una corrección local auditada por regresión porque
GHSA-gcqx-w48m-w2h4 aún no tiene release upstream corregida. Su README explica
procedencia, límites y cuándo retirarla; npm audit no analiza ese código local.

Para APK, instalar SDK `platforms;android-36`, `build-tools;36.0.0`,
`ndk;27.1.12297006` y `cmake;3.22.1`, aceptar sus licencias y exportar
`ANDROID_HOME`. El wrapper fija Gradle y la plantilla Expo se fija a
`expo-template-bare-minimum@56.0.38`. Se compila la variante release con bundle
incluido, **firmada solo con la clave debug/de desarrollo** de la plantilla.
No requiere Metro; sin endpoint configurado muestra servicio no disponible.
**No es una release productiva ni acredita prueba en teléfono**.
Salida: `work/artifacts/mobile-development-<SHA>.apk` y manifiesto SHA-256.
`make apk` y `make image` exigen un árbol limpio para identificar el código real
por su commit. La configuración fija Gradle 8.14.3 con checksum oficial para
evitar la incompatibilidad de Foojay/RN 0.85 con Gradle 9.
`eas.json` define los perfiles futuros; cuenta Expo, firma estable y package IDs cloud
siguen sin configurar. OTA permanece deshabilitado.

## Superficie implementada

| Ruta | Resultado |
| --- | --- |
| `/` | Template informativo, sin login ni datos personales. |
| `/health/live` | `200 {"status":"ok"}`, sin consultar dependencias. |
| `/health/ready` | `200 ready` con `SELECT 1`; `503 unavailable` ante error, sin DSN. |
| `/v1/capabilities` | `pickup_enabled: false`, contrato público mínimo. |

OpenAPI: `tests/contracts/openapi.yaml`. Respuestas `no-store`, sin PII.
Readiness técnico **no autoriza retiros**. `/admin/` y rutas de negocio no existen.
Worker: `python manage.py runworker --check` muestra cero handlers; sin `--check`
falla explícitamente porque los outboxes se implementan en E1/E4.

## CI, artefactos y CD

`.github/workflows/ci.yml` usa los mismos comandos. Checks de PR sin secretos,
acciones por SHA, imagen OCI con digest y manifiestos por commit. El job `required`
exige calidad y ambos builds. Los tests RLS son una sonda de infraestructura E0;
no acreditan las futuras políticas por rol/estudiante ni las suites AT01–AT08.

El repositorio es público. El APK interno no se sube como artefacto público:
se conserva el checksum; el binario solo se sube automáticamente si el repositorio
es privado. Para distribución interna en este repositorio falta conectar un destino privado.
No hay código privilegiado ejecutado desde forks ni `pull_request_target`.

CD conserva una estructura serializada y validación obligatoria. Actualmente **falla
con `BLOCKED/NOT_CONFIGURED`**: OIDC de lectura, cuenta y créditos ya se verificaron,
pero AWS todavía no ofrece datos de gasto. Faltan presupuesto/alertas aplicados,
recursos, identidades de despliegue/migración y aceptación real de staging.
No hay despliegue ni promoción implementados como éxitos ficticios.
Ver [runbook](docs/runbooks/deployment.md) y [presupuesto AWS](infra/aws/README.md).
`scripts/verify_staging.py` prepara los probes públicos E0 sobre HTTPS/TLS 1.3,
con pruebas de fallos mediante un servidor TLS local real. Solo acredita el plano
de datos público al ejecutarlo contra un destino real; no provisiona ni certifica IAM,
presupuesto o procedencia del artefacto. No se ha ejecutado contra AWS.

Los requisitos de producto permanecen en `Requerimientos_retiro_seguro_estudiantes.md`;
`PLAN.md` fija E0–E5 y `AGENTS.md` las convenciones de trabajo.

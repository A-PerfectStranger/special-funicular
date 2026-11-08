# Retiro seguro de estudiantes

Monorepo Django/PostgreSQL y Expo SDK 56 para el retiro escolar seguro.

## Documentación

Cada documento tiene un propósito único:

| Documento | Fuente de referencia para |
| --- | --- |
| [Requisitos](Requerimientos_retiro_seguro_estudiantes.md) | Comportamiento, arquitectura, permisos y criterios de aceptación del producto. |
| [Plan](PLAN.md) | Estado de las entregas, aceptación acreditada y trabajo pendiente. |
| [AGENTS](AGENTS.md) | Reglas de desarrollo, validación e integración. |
| Este README | Instalación, comandos y superficie disponible para desarrollo. |
| [Despliegue](docs/runbooks/deployment.md) | Publicación, diagnóstico y rollback. |
| [Importación y familia](docs/runbooks/e2.md) | Comandos privados, esquema, activación y ensayo E2. |
| [Identidad y evidencia](docs/runbooks/e1.md) | Comisión, ensayos y recuperación sintética de E1. |
| [AWS](infra/aws/README.md) | Infraestructura, presupuesto y bootstrap. |

La configuración de cada destino vive en [infra/environments](infra/environments).
Mantener el estado en el plan y los resultados por commit en Actions; no añadir
bitácoras de sesión ni copias de reportes históricos al repositorio.

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
| `make test` | Unitarias, contratos, PostgreSQL/RLS, móvil y regresión vendor. |
| `node --test tests/staging/native-callback.test.mjs` | Regresión real de Chromium para retorno nativo; requiere navegador Playwright o E1_CHROMIUM_PATH. |
| `make check` | Lint, tipos, migraciones, `make test`, checks Django y compatibilidad Expo. |
| `make security` | pip-audit, npm audit y gitleaks 8.30.1 (instalar binario oficial en PATH). |
| `npm run mobile:export` | Compila el bundle Android/Hermes; no es un APK. |
| `make image` | Imagen no privilegiada, compartida por API y worker de archivo. |
| `bash scripts/smoke_image.sh retiro-backend:<SHA>` | Probes reales de imagen, runtime sin credencial de migración y diagnóstico worker. |
| `make apk` | APK arm64 de desarrollo firmado con debug key, requiere Android SDK/JDK 21. |

Para la regresión de navegador: `npx playwright install chromium` (dependencias
Linux con `--with-deps`), o `E1_CHROMIUM_PATH=/ruta/a/chromium` con un navegador
local. CI instala el navegador oficial y ejecuta la misma prueba sin credenciales.

`make security` crea `work/` para sus archivos temporales. Instalar gitleaks
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
productivos siguen sin configurar. El ensayo E1 fija package ID
`org.retiroseguro.staging`, endpoint y callback; su APK mantiene firma de desarrollo
y manifiesto público, sin binario interno público. OTA permanece deshabilitado.

## Superficie implementada

| Ruta | Resultado |
| --- | --- |
| `/` | Template informativo, sin login ni datos personales. |
| `/health/live` | `200 {"status":"ok"}`, sin consultar dependencias. |
| `/health/ready` | `200 ready` con `SELECT 1`; `503 unavailable` ante error, sin DSN. |
| `/v1/capabilities` | `pickup_enabled: false`, contrato público mínimo. |

OpenAPI: `tests/contracts/openapi.yaml`. Respuestas `no-store`, sin PII.
Readiness técnico **no autoriza retiros**. `/admin/` y rutas de retiro no existen.
Sin seleccionar un handler, `python apps/backend/manage.py runworker --check` muestra cero
handlers activos. E1 añade `runworker --archive` con configuración y credencial
SQL propias; las notificaciones siguen pendientes de E4. La ejecución cloud
acotada usa `python -m archive_worker.runner --max-runtime-seconds 10800`.
Operación: [runbook E1](docs/runbooks/e1.md); aceptación y pendientes: [plan](PLAN.md).

Con `E1_IDENTITY_ENABLED=true` y configuración completa, E1 añade `/auth/login`,
`/auth/callback`, `/auth/logout`, `/portal/`, `/v1/auth/mobile/start`,
`/v1/auth/mobile/exchange`, `/v1/auth/refresh`, `/v1/auth/logout`, `/v1/me` y
`/v1/system/school-access-records`. No añade CRUD de roles/estudiantes/evidencias.
Los callbacks de Cognito y el móvil deben coincidir exactamente por entorno;
el cliente móvil recibe sesiones propias, nunca tokens del IdP. Las consultas
escolares de salidas corresponden a E4 y los retiros a E3.

## CI, artefactos y CD

`.github/workflows/ci.yml` usa los mismos comandos. Checks de PR sin secretos,
acciones por SHA, imagen OCI con digest y manifiestos por commit. El job `required`
exige calidad y ambos builds. Las pruebas locales E1 incluyen roles/familias y RLS
con PostgreSQL real. El [plan](PLAN.md) delimita la aceptación funcional de cada
entrega; pasar los probes técnicos no acredita funciones pendientes.

El repositorio es público. El APK interno no se sube como artefacto público:
se conserva el checksum; el binario solo se sube automáticamente si el repositorio
es privado. Para distribución interna en este repositorio falta conectar un destino privado.
No hay código privilegiado ejecutado desde forks ni `pull_request_target`.

La URL temporal de staging se obtiene de `base_url` en
[su configuración](infra/environments/staging.json) y se contrasta con AWS al
desplegar; recrear Express puede cambiarla. Ventanas, retirada y costes:
[runbook](docs/runbooks/deployment.md) y [AWS](infra/aws/README.md).
CI valida también las plantillas de infraestructura.


Con `E2_FAMILY_ENABLED=true` y E1 configurada, se añaden las rutas familiares
versionadas de OpenAPI: `/v1/students`, activación, cuidadores, fotos autenticadas,
autorizaciones y revocación. `/v1/family/capabilities` existe solo con E2 habilitada;
el móvil consulta esa disponibilidad antes de mostrar activación/gestión familiar.
Los retiros permanecen deshabilitados. El importador y las operaciones técnicas
son `python apps/backend/manage.py family_ops --help`, con credencial importer
privada, aprobación escolar y motivo; no hay CRUD administrativo público.
Comandos, límites, tratamiento de fotos y ensayo CloudShell: [runbook E2](docs/runbooks/e2.md).
El workflow `e2-trial.yml` prepara un candidato acotado. Comparte `e2-checks.yml`
con CD: al habilitar `e2_enabled` exige E1, E2 y WORM independiente. La configuración
revisada de staging habilita ese gate; las cohortes privadas de un solo uso
se preparan como pool acotado mediante CloudShell. Código y mocks no acreditan
aceptación AWS.

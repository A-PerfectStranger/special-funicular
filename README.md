# Retiro seguro de estudiantes

Monorepo Django/PostgreSQL y Expo SDK 56. E0 está aceptada en staging.
E1 incorpora identidad/aislamiento/evidencia en desarrollo, con sus rutas
**desactivadas por defecto; el workflow E1 synthetic trial permite un ensayo acotado antes de la aceptación**.
Los retiros permanecen deshabilitados. Solo datos sintéticos.
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
| `node --test tests/staging/native-callback.test.mjs` | Regresión real de Chromium para retorno nativo; requiere navegador Playwright o E1_CHROMIUM_PATH. |
| `make check` | Todo lo anterior, checks Django, deriva de migraciones y compatibilidad Expo. |
| `make security` | pip-audit, npm audit y gitleaks 8.30.1 (instalar binario oficial en PATH). |
| `npm run mobile:export` | Compila el bundle Android/Hermes; no es un APK. |
| `make image` | Imagen no privilegiada, compartida por API y futuro worker. |
| `bash scripts/smoke_image.sh retiro-backend:<SHA>` | Probes reales de imagen, runtime sin credencial de migración y diagnóstico worker. |
| `make apk` | APK arm64 de desarrollo firmado con debug key, requiere Android SDK/JDK 21. |

Para la regresión de navegador: `npx playwright install chromium` (dependencias
Linux con `--with-deps`), o `E1_CHROMIUM_PATH=/ruta/a/chromium` con un navegador
local. CI instala el navegador oficial y ejecuta la misma prueba sin credenciales.

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
Readiness técnico **no autoriza retiros**. `/admin/` y rutas de negocio no existen.
Sin seleccionar un handler, `python manage.py runworker --check` muestra cero
handlers activos. E1 añade `runworker --archive` con configuración y credencial
SQL propias; las notificaciones siguen pendientes de E4. La ejecución cloud
acotada usa `python -m archive_worker.runner --max-runtime-seconds 10800`.
Guía y estado de aceptación: [runbook E1](docs/runbooks/e1.md).

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
con PostgreSQL real; no sustituyen IdP/WORM/KMS reales ni todos los ensayos AT01–AT08.

El repositorio es público. El APK interno no se sube como artefacto público:
se conserva el checksum; el binario solo se sube automáticamente si el repositorio
es privado. Para distribución interna en este repositorio falta conectar un destino privado.
No hay código privilegiado ejecutado desde forks ni `pull_request_target`.

CD serializado real en AWS: publica el artefacto aprobado de main preservando el
digest, abre la ventana RDS, migra con identidad separada y despliega/verifica
staging con Deploy. Rechaza candidatos obsoletos y serializa migraciones mediante
advisory lock SQL. Datos sintéticos, retiros deshabilitados. Producción permanece
BLOCKED/NOT_CONFIGURED hasta E5, sin aprobación manual rutinaria añadida.

Staging temporal: https://re-ebedcb6688b94b228cd28424e44448c6.ecs.us-east-1.on.aws. API/ALB se retiran a las tres horas de cada despliegue;
RDS se detiene fuera de ensayos, con coste residual reservado. La evidencia de
SHA/digest, TLS/red y ejecución está en [PROGRESS.md](PROGRESS.md).
Ver [runbook](docs/runbooks/deployment.md) y [presupuesto AWS](infra/aws/README.md).
Los probes HTTPS de `scripts/verify_staging.py` se ejecutaron realmente desde CI,
con certificado/hostname verificados y TLS 1.3. El plano de control y el digest
se verifican por separado; no se infieren de una respuesta de health.

Los requisitos de producto permanecen en `Requerimientos_retiro_seguro_estudiantes.md`;
`PLAN.md` fija E0–E5 y `AGENTS.md` las convenciones de trabajo.

La infraestructura y operación sintética se documentan en
[bootstrap de staging](infra/aws/staging-bootstrap.md). Cost Explorer, presupuesto,
base privada, publicación y aceptación de staging tienen evidencia real E0.
CI valida también las plantillas de infraestructura.

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
| [QR y puerta sintética](docs/runbooks/e3.md) | Emisión, escaneo, decisión, archivo, reporte y gate E3. |
| [Identidad y evidencia](docs/runbooks/e1.md) | Comisión, ensayos y recuperación sintética de E1. |
| [Avisos y consulta](docs/runbooks/e4.md) | Expo/FCM, dispositivos, notificador, consultas y comandos técnicos. |
| [Aceptación y activación](docs/runbooks/e5.md) | Pruebas conjuntas Android, recuperación/carga y cierre productivo pendiente. |
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
| `node --test tests/staging/native-callback.test.mjs tests/staging/recovery.test.mjs tests/staging/diagnostics.test.mjs` | Regresión real de Chromium para retorno nativo; requiere navegador Playwright o E1_CHROMIUM_PATH. |
| `make check` | Lint, tipos, migraciones, `make test`, checks Django y compatibilidad Expo. |
| `make security` | pip-audit, npm audit y gitleaks 8.30.1 (instalar binario oficial en PATH). |
| `npm run mobile:export` | Compila el bundle Android/Hermes; no es un APK. |
| `make image` | Imagen no privilegiada, compartida por API y worker de archivo. |
| `bash scripts/smoke_image.sh retiro-backend:<SHA>` | Probes reales de imagen, runtime sin credencial de migración y diagnóstico worker. |
| `make apk` | APK arm64 de desarrollo firmado con debug key, requiere Android SDK/JDK 21. |

Para la regresión de navegador: `npx playwright install chromium` (dependencias
Linux con `--with-deps`), o `E1_CHROMIUM_PATH=/ruta/a/chromium` con un navegador
local. En sus runners Ubuntu 24.04, CI usa `bash scripts/install_ci_chromium.sh`:
descarga la revisión de Chromium fijada por el lockfile y comprueba su arranque
e interacción reales usando las bibliotecas nativas del runner. No instala
paquetes APT ni modifica repositorios del sistema. Después ejecuta la misma
regresión sin credenciales; un fallo de descarga, bibliotecas o navegador bloquea
el job.

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
**No es una release productiva ni acredita prueba en teléfono**. El build inspecciona
el APK compilado con aapt2: exige cámara para QR y ausencia de micrófono.
Salida: `work/artifacts/mobile-development-<SHA>.apk` y manifiesto SHA-256.
`make apk` y `make image` exigen un árbol limpio para identificar el código real
por su commit. La configuración fija Gradle 8.14.3 con checksum oficial para
evitar la incompatibilidad de Foojay/RN 0.85 con Gradle 9. CI obtiene el ZIP
exacto por la API oficial de gradle/gradle-distributions y verifica el mismo
checksum antes de usarlo localmente en el wrapper generado. El token GitHub
solo está presente en el paso de descarga. Para un entorno local afectado por
fallo del redirect de Gradle, `python3 scripts/gradle_archive.py download` y
`RETIRO_GRADLE_ARCHIVE="$PWD/work/native-tools/gradle-8.14.3-bin.zip" make apk`
usan esa misma ruta verificada; requieren GitHub CLI autenticado.
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
Readiness técnico **no autoriza retiros**. `/admin/` no existe; las rutas E3 requieren su bandera sintética explícita.
Sin seleccionar un handler, `python apps/backend/manage.py runworker --check` muestra cero
handlers activos. E1 añade `runworker --archive` con configuración y credencial
SQL propias. E4 añade `--notifications` con credencial SQL y configuración Expo
separadas; no seleccionar ambos handlers en un proceso. La ejecución cloud
acotada usa `python -m archive_worker.runner --max-runtime-seconds 10800`.
Operación: [runbook E1](docs/runbooks/e1.md); aceptación y pendientes: [plan](PLAN.md).

Con `E1_IDENTITY_ENABLED=true` y configuración completa, E1 añade `/auth/login`,
`/auth/callback`, `/auth/logout`, `/portal/`, `/v1/auth/mobile/start`,
`/v1/auth/mobile/exchange`, `/v1/auth/refresh`, `/v1/auth/logout`, `/v1/me` y
`/v1/system/school-access-records`. No añade CRUD de roles/estudiantes/evidencias.
Los callbacks de Cognito y el móvil deben coincidir exactamente por entorno;
el cliente móvil recibe sesiones propias, nunca tokens del IdP. Las consultas
escolares de salidas requieren la bandera E4 y los retiros la bandera E3.

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

La URL temporal de staging se obtiene del reporte de despliegue verificado por
SHA/digest en Actions. `base_url` en
[su configuración](infra/environments/staging.json) es una pista de arranque:
recrear Express puede cambiarla. Los ensayos y el APK reciben el origen verificado
mediante `STAGING_RELEASE_ORIGIN`, después de comprobar el callback. Ventanas, retirada y costes:
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


Con `E3_PICKUP_ENABLED=true`, E1/E2 configuradas y entorno sintético, se añaden
emisión/renovación/reprogramación QR y las rutas de guardia de OpenAPI. El móvil
consulta `/v1/pickup/capabilities`; las capacidades antiguas conservan
`pickup_enabled=false` para APK previos y uso real deshabilitado. E3 no arranca en
producción. Episodio único por estudiante/fecha local; decisión/outbox/consumo
atómicos, recibo WORM <=5 s, permiso 30 s y reporte físico idempotente, con
incidencias durables. QR solo en cuerpo/memoria o imagen compartida temporal;
SecureStore conserva únicamente el UUID para recuperar una operación ambigua.

El archivador observa hora autenticada de S3 y avanza vencimientos sin depender
de un teléfono conectado. `runworker --archive --check` incluye métricas de puerta.
CD exige el protocolo sintético E3 y verificación externa cuando `e3_enabled=true`.
Comandos, recuperación por ID, inyección de archivo tardío y límites: [E3](docs/runbooks/e3.md).
Avisos/consulta escolar se habilitan por E4; pruebas físicas Android y activación real son E5.


## Avisos y consultas E4

El registro del dispositivo del padre está disponible con E2 en
`POST /v1/me/notification-device`; el APK debe incluir su configuración Firebase.
No envía avisos por registrar un dispositivo. Para ello se requiere el notificador
configurado, allowlist de ensayo y un reporte físico protegido.

Con `E4_OPERATIONS_ENABLED=true`, E3 y lector escolar separados, aparecen
`/v1/operations/capabilities`, `/v1/me/pickups`,
`/v1/school/pickup-records` y la consulta de `/portal/`. Historial mínimo propio,
filtros por fecha local/estudiante, paginación y correcciones vinculadas; sin CRUD
administrativo. El administrador de sistema conserva solo accesos escolares.
El estado de aceptación y la bandera de staging se consultan en PLAN/configuración.

```bash
python apps/backend/manage.py runworker --notifications --check
python apps/backend/manage.py notification_ops --help
python apps/backend/manage.py pickup_correction --help
```

El worker aislado usa `notification_worker.runner`; nunca recibe las credenciales
SQL de migración/importación/archivo. Expo usa tickets y recibos HTTPS autenticados,
no un callback público ni una señal de lectura del usuario. Una respuesta perdida
puede duplicar un mensaje externo, conservando un único aviso y hecho lógicos.
Operación, CLI privados, secretos, FCM y ensayos: [E4](docs/runbooks/e4.md).

El proyecto Expo y el paquete de staging están fijados en app.config.ts. El build
cloud recibe `STAGING_GOOGLE_SERVICES_JSON` por secret y valida su app/paquete;
la cuenta FCM v1 se custodia en Expo. La firma actual sigue siendo de desarrollo.
La comisión/aceptación E4 en AWS y la producción E5 no se acreditan por esta
configuración ni por un bundle compilado.

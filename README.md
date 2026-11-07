# Retiro seguro de estudiantes

Base E0, exclusivamente sintética. Django modular con templates y PostgreSQL; móvil Expo SDK56/React Native. AWS seleccionado para futuro despliegue. **No hay identidad, QR, autorizaciones ni retiros habilitados.** Estado verificable y bloqueos: [PROGRESS.md](PROGRESS.md). Contrato de producto: [requisitos](Requerimientos_retiro_seguro_estudiantes.md); [plan](PLAN.md); [criterios E0](docs/E0-acceptance.md).

## Arranque local

Requisitos: Python3.12.14, uv0.13.5, Node24.22.1/npm11.9.0, Docker Engine y Compose v2. Para APK: Linux, JDK17, Android SDK36, build-tools36.0.0, NDK/CMake indicados por la plantilla Expo56 y acceso a repositorios oficiales. Dependencias Python/npm bloqueadas en uv.lock/package-lock.json; imágenes base por digest. No usar SQLite.

Desde la raíz de un checkout:

```sh
cp .env.example .env
uv sync --frozen
npm ci
docker compose up -d --wait db
DB_USER=app_migrator DB_PASSWORD=synthetic-migrator uv run python apps/backend/manage.py migrate --noinput
uv run python apps/backend/manage.py runserver 127.0.0.1:8000
```

Los valores por defecto son sintéticos e iguales a .env.example. Django lee variables del proceso; NO carga .env automáticamente. Si modificas .env, expórtalas antes de ejecutar. No usar esa configuración fuera de local/test. Las migraciones se ejecutan por separado; el runtime no puede crear tablas. Solo existe la migración estándar de sesiones; no hay tablas de negocio/evidencia ni RLS de negocio todavía.

Home: http://127.0.0.1:8000/ . GET `/health/live` comprueba proceso sin acceder a BD; `/health/ready` comprueba PostgreSQL y migraciones aplicadas, responde503 genérico si fallan. GET `/v1/capabilities` publica solo versión de API/fase y `pickup_enabled:false`. Todas las respuestas usan no-store. No hay Django Admin. [OpenAPI E0](tests/contracts/openapi.json) describe las únicas rutas JSON disponibles.

```sh
npm run start --workspace apps/mobile
npm run mobile:export
```

Las vistas padre/guardia son demostraciones explícitas sin autenticación ni permisos. No incluyen expedientes, escaneo ni modo offline. El dispositivo/emulador se verifica por separado de exportar un bundle.

## Verificación

```sh
bash scripts/check.sh
bash scripts/security.sh
```

check.sh ejecuta instalación bloqueada, Ruff, formato, mypy, check/migraciones Django, pytest con PostgreSQL real y rol runtime, ESLint, tsc y pruebas móviles. security.sh ejecuta pip-audit, npm audit y Gitleaks sobre archivos e historial. Cualquier fallo bloquea CI. Las pruebas preparan una base sintética dedicada `test_retiro_synthetic` con migrador; el código de los tests usa `app_runtime`, sin SUPERUSER/BYPASSRLS/CREATEDB/CREATEROLE/CREATE en esquema. No ejecutar tests contra una base real.

Tras cambiar dependencias Python, regenerar requirements.txt para la imagen:

```sh
uv lock
uv export --frozen --no-dev --format requirements-txt -o requirements.txt
```

CI verifica que esa exportación está actualizada. [Overrides npm](docs/dependency-overrides.md): correcciones transitivas auditadas manteniendo SDK56; verificar export/prebuild/build al cambiarlos.

## Imagen y APK de ensayo

Construir solo desde un commit con código limpio para que RELEASE_SHA identifique sus bytes:

```sh
docker build --build-arg RELEASE_SHA=$(git rev-parse HEAD) -t retiro-backend:local .
docker run --rm --network special-funicular_default -p 127.0.0.1:8000:8000 -e DB_HOST=db retiro-backend:local
docker run --rm --network special-funicular_default -e DB_HOST=db retiro-backend:local python manage.py worker --check
```

Adaptar el nombre de red al nombre de proyecto Compose si el directorio difiere. En Codex Cloud con proxy TLS, añadir al build `--secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt`. No deshabilitar verificación TLS. La imagen usa UID10001, misma revisión para API y futuro worker. `worker --check` solo prueba DB; `worker` sin --check falla explícitamente porque outbox aún no está implementado. No hay procesamiento silencioso simulado.

```sh
export ANDROID_HOME=/ruta/al/android-sdk
export RELEASE_SHA=$(git rev-parse HEAD)
bash scripts/build-apk.sh
```

El script descarga una plantilla Expo56 por URL/checksum, regenera solo android ignorado, produce release arm64 con bundle embebido y firma **debug de desarrollo**, y escribe APK/checksum con SHA en artifacts/. Nunca usar esa clave para producción. No requiere cuenta Expo para build nativo local. eas.json prepara perfil interno de desarrollo; EAS real requiere cuenta/proyecto y su CLI/configuración verificadas, todavía pendientes. Package ID provisional sintético `org.retiroseguro.synthetic`; producción tendrá ID/firma custodiados y configuración propia.

CI construye imagen OCI con digest/provenance/SBOM y APK por SHA. Los APK solo se suben como artifacts cuando el repositorio es privado. Este repositorio es público: el job informa distribución privada pendiente, sin publicar APK en enlaces públicos. Publicación no equivale a instalación en teléfonos.

## AWS y CD

[Presupuesto total USD150](docs/aws-budget.md), [setup del Toolkit](docs/runbooks/aws-toolkit.md) y [CD/rollback](docs/runbooks/deployment.md). No hay recursos AWS aprovisionados.

```sh
uv run python scripts/validate_deploy.py staging
```

Devuelve código2 y diagnóstico **DEPLOY BLOQUEADO** con los archivos de destino actuales. El workflow CD se ejecuta después de CI de main; no tiene secretos ni permisos de despliegue. Valida configuración y se bloquea explícitamente hasta integrar el adaptador real. No cuenta como despliegue exitoso. El futuro adaptador deberá promover el mismo digest entre staging/producción, usar OIDC acotado y migrador separado, serializar por entorno, descartar candidatos obsoletos y promover automáticamente tras ensayos reales; no hay aprobación manual rutinaria.

Para detener local sin perder la base sintética: `docker compose stop db`. `docker compose down -v` **borra** el volumen sintético; usar solo cuando se desea reiniciar datos locales. No sirve para rollback ni recuperación productiva.

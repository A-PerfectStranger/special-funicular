# Publicación, diagnóstico y rollback

## Fuentes operativas

Estado y aceptación: [PLAN.md](../../PLAN.md). Parámetros del destino:
[staging](../../infra/environments/staging.json) y
[producción](../../infra/environments/production.json). Infraestructura, bootstrap,
presupuesto y lifecycle: [AWS](../../infra/aws/README.md). Ensayos de identidad y
archivo: [E1](e1.md). No se requieren claves AWS permanentes para CD.

## Publicación rutinaria

1. Abrir PR y completar required: calidad, imagen inmutable y APK. main exige PR/check.
2. Al integrar, E0 CI construye los artefactos del SHA main. workflow_run de CD
   verifica repositorio/evento, conserva checksum/digest y publica en ECR inmutable.
3. Deploy abre la ventana acotada de staging e inicia RDS si está detenido.
4. Migrate ejecuta una tarea Fargate con su secreto SQL separado y migrate_locked;
   el advisory lock PostgreSQL serializa incluso si un runner deja de esperar.
5. Deploy actualiza Express con el mismo digest; espera todas las tareas nuevas,
   verifica índice OCI/manifest amd64, red ALB→tarea y probes TLS según la configuración E3 explícita. Evidencia:
   artefacto staging-deployment del workflow. No importar familias ni enviar avisos.
   Si la retirada programada dejó una descripción INACTIVE, recrea el servicio
   sintético con el digest aprobado y rearma su expiración. DRAINING o un estado
   desconocido bloquean la creación/actualización. Un fallo de lectura o permisos
   nunca demuestra que el servicio no existe. Contrastar el origen resultante con
   los callbacks de E1 antes de aceptar los flujos de identidad.
6. Si `e1_enabled=true`, ejecutar browser/cloud/staging-apk/archive-drill mediante
   `e1-checks.yml`. Todos deben aprobar; un fallo bloquea promoción. Consultar
   resultados y artefactos del commit en Actions, sin copiar reportes al repositorio.
7. Si E2 está habilitada, exigir su activación/permisos familiares; con E3, exigir
   también retiro sintético y WORM independiente hasta la secuencia final.
8. Producción solo se habilita tras configuración/aceptación E5. No añadir una
   aprobación humana rutinaria de promoción. cancel-in-progress=false en CD.

```bash
python3 scripts/validate_deploy.py infra/environments/staging.json
python3 scripts/validate_deploy.py infra/environments/production.json
```

Los validadores comprueban estructura; un archivo válido por sí solo no prueba
IAM, coste, TLS ni despliegue. Un destino incompleto sale 2. Para diagnóstico
público, usar el origen verificado de staging:

```bash
python3 scripts/verify_staging.py https://ORIGEN_STAGING_VERIFICADO --report work/staging-probes.json
```

Con E3 sintética habilitada añadir `--e3-trial`; CD lo deriva de su configuración
revisada, nunca de la respuesta del servidor. Sin E3, la ruta de confirmación debe
estar ausente (404); con E3 debe rechazar GET (405) y su capacidad debe ser
exactamente `pickup_enabled=true, synthetic_only=true`. La capacidad antigua
continúa en false para clientes anteriores.

Exige TLS 1.3/certificado/hostname, live/ready/capabilities, admin ausente,
escrituras rechazadas y cabeceras seguras. Un fallo devuelve 1 y una
configuración inválida, 2. No sigue redirecciones ni registra cuerpos/cookies o
excepciones remotas. El reporte no acredita SHA/digest, IAM, presupuesto ni E1.
Un proxy TLS interceptante impide usar ese cliente como atestación TLS del origen;
los probes de aceptación se ejecutan desde runner sin ese proxy.

## Origen Express y callback existente

La retirada programada puede eliminar Express o dejarlo INACTIVE. Su recreación
cambia el hostname. CD reconoce solo ausencia comprobada (incluido el
`ResourceNotFoundException` específico de DescribeExpressGatewayService);
AccessDenied, DRAINING o resultados ambiguos bloquean sin crear otro servicio.

Si no hay gateway activo o su origen no coincide con el callback registrado, CD
crea/actualiza una puerta stateless con identidad/familia/retiro apagados y sin
iniciar otro archivador. Conserva base, cuentas y evidencia. El reporte contiene
`origin_sync_required=true` y el origen observado, pero `passed=false`:
`GATEWAY_BOOTSTRAP_ONLY` no es aceptación. No revierte esa puerta al código E1
previo con un callback inválido. La ventana de retirada sigue siendo acotada.

`base_url` del archivo de entorno es solo una pista de arranque/diagnóstico; un
hostname efímero no se vuelve una identidad permanente. El servicio/ARN y cuenta
revisados, el SHA/digest aprobado y los metadatos ECS autenticados identifican el
origen del candidato. No se acepta una URL arbitraria por entrada del cliente.

Con el SHA main aprobado y el bootstrap activo, un operador de la cuenta puede
sincronizar únicamente el callback existente desde CloudShell:

```bash
(
  set -euo pipefail
  origin_checkout=$(mktemp -d /tmp/retiro-origin.XXXXXX)
  git clone https://github.com/A-PerfectStranger/special-funicular.git "$origin_checkout"
  cd "$origin_checkout"
  git switch --detach SHA_MAIN_APROBADO
  python3 -m scripts.sync_staging_origin --sha "$(git rev-parse HEAD)"
)
```

El comando rechaza CI/runtime como operador. Obtiene el hostname del servicio
revisado, exige un único origen AWS HTTPS y comprueba que su task definition use
el SHA aprobado y la imagen ECR fijada por el digest del tag inmutable de ese SHA. No depende del hostname viejo
de `base_url` ni acepta otro origen como argumento. Reutiliza la plantilla y los
otros parámetros existentes. Solo ejecuta un
change set que modifica `WebClient.CallbackURLs` sin reemplazo; cualquier otro
recurso/propiedad bloquea antes de ejecutar. Después comprueba que los outputs
persistentes y el callback real de Cognito coincidan. No crea usuarios, accede al
vault, migra SQL ni cambia claves/retención/IAM. Si ya coincide, solo verifica.
Conservar el change set y eventos CloudFormation como evidencia; no borrarlos para
repetir. El comando no acredita aceptación. Repetir staging para inyectar el callback
actualizado y exigir E1/E2/E3/WORM completos del mismo candidato. Tras comprobar
callback, digest y TLS, CD publica `STAGING_RELEASE_ORIGIN` a los ensayos y al build
del APK de staging; esos consumidores rechazan un origen ausente o ajeno a AWS.
El verificador del APK exige ese mismo origen en EXPO_PUBLIC_API_URL y en el
bundle real, además de paquete/callback nativos; la pista de arranque no sustituye
esa comprobación. No se añaden permisos de modificación de Cognito a CI. Los errores del comando
muestran solo motivos fijos/códigos AWS permitidos, nunca excepciones privadas.

El workflow manual `Anonymous staging navigation diagnostic` recibe opcionalmente
`origin` del reporte de despliegue (vacío usa la pista de arranque) y prueba solo página
de ingreso → formulario IdP, sin credenciales. Crea un inicio anónimo acotado,
no una sesión ni una aceptación funcional. Sus reportes conservan fases, estados
HTTP y categorías de red fijas; nunca URLs con códigos ni texto del proveedor.

## Infraestructura y diagnóstico

Ante fallos de creación, permisos, red o expiración, seguir el diagnóstico de
[AWS](../../infra/aws/README.md#lifecycle-red-y-diagnóstico). Contrastar siempre
el origen de Express con configuración/callbacks; un health 200 no demuestra
digest correcto ni login funcional. No borrar base, evidencia, secretos o claves
para recuperar la API. La comisión inicial es una operación de operador distinta
de la publicación rutinaria automática.

## Rollback y recuperación

Rollback de código: volver a un digest compatible conocido sin bajar esquema ni
restaurar BD. Si una migración falla, impedir promoción y corregir hacia delante.
Nunca borrar evidencia ni degradar retención para corregir o reducir costes.

Recuperación de desastres (pendiente E5): suspender retiros, restaurar, invalidar
tokens anteriores al epoch, reconciliar WORM/manifiestos/proyecciones y reabrir
solo tras verificar ausencia de discrepancias. RTO 30 min es objetivo pendiente,
no una medición E0. No hay todavía comandos de recuperación del dominio.

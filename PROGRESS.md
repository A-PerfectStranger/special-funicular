# Estado de ejecución — 7 de noviembre de 2026

## Resultado actual: E0 sigue abierto

Base técnica E0 implementada y verificada. **Identidad AWS de lectura conectada
por OIDC desde GitHub/main**; créditos y vigencia confirmados por AWS.
**Staging aún en comisión, producción no aprovisionada**. Cost Explorer ya
aprobó el preflight completo, repetido con éxito en 42430538070. El presupuesto,
la base privada y la guarda horaria ya se aplicaron; falta aceptar la API real. Los bloqueos históricos de gasto que figuran
abajo ya no son el impedimento actual. No presentar la preparación como deploy.
E1–E5 pendientes; ningún retiro real habilitado. El toolkit interactivo no está
instalado/autenticado; OIDC de CI no se presenta como ese login humano.

## Comisión actual: PostgreSQL privado y ventana limitada

La configuración staging incorpora los identificadores reales devueltos por
Express desde CloudShell (API :1, URL, subredes y security groups), roles ya
creados y repositorio ECR verificado. Esto configura el destino de CD, no lo
acredita como sano: los probes desde el entorno gestionado recibieron 503.
Se reprodujo que CommonMiddleware devuelve 400 a la sonda ALB con Host=IP
privada. Liveness stateless GET/HEAD se atiende antes de esa validación solo
bajo TRUSTED_INGRESS=ecs-express; las demás rutas siguen exigiendo Host permitido.
El cierre depende del nuevo artefacto y del CD real, todavía pendientes.


La comisión del artefacto `9f988a1` completó SQL y creó la API Express, estado
ACTIVE según CloudShell. URL observada:
https://re-ebedcb6688b94b228cd28424e44448c6.ecs.us-east-1.on.aws.
La aceptación falló en el verificador: DescribeServices omite la red y los target
groups en este servicio Express. Se corrige para consultar la revisión activa y
los target groups resueltos. No se marca staging aprobado por estar ACTIVE.


- Publicación OIDC real aprobada: [42430973973](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42430973973).
  Deploy publicó el artefacto de CI main `42430283578` del commit
  `9f988a132ae72812a4d329f97d30ae2265bcd988` en ECR y verificó el digest
  `sha256:bf3e47b155d9c43f07fa1c722f7f263860e290c271ded7fe4e925382f51f132d`.
  Artefacto público de metadatos `13597795597`. Esto acredita publicación,
  no el estado del servicio; comisión SQL/API y aceptación pendientes.


- PR #5 integrado en `9f988a132ae72812a4d329f97d30ae2265bcd988` con todos los
  checks aprobados. [CI de main 42430283578](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42430283578)
  aprobó quality, imagen con smoke real, APK y required. Último `make check`
  local: 62 pruebas Python y 3 JS, todos los checks aprobados.
- El usuario confirmó que el reparador `98fd5b34aeaf1e04f36146a81a90cb64c56ad64a`
  terminó con `Lifecycle configured`. Base y roles Deploy/Migrate existen;
  Scheduler tiene ventana activa inicial de tres horas y guarda horaria de RDS.
  La aplicación de la guarda no acredita aún una invocación de parada real.
- Preflight de facturación repetido después de crear la base:
  [42430538070](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42430538070),
  artefacto `13596459500`: cuenta correcta, acceso IAM ajeno denegado,
  créditos cubren el techo de 150 USD, vigencia hasta 2027-05-06 y gasto mensual
  bruto consultado bajo el techo; `passed=true`, sin errores. Solo booleanos
  en el artefacto público; no publica saldos ni correo de alertas.


El usuario confirmó creación de la base y devolvió los ARN Deploy/Migrate de la
cuenta esperada. El stack independiente lifecycle falló: Scheduler exige
`yyyy-MM-ddTHH:mm:ss.SSSZ`; su estado ROLLBACK_COMPLETE impide actualizarlo.
El reparador genera milisegundos y recrea solo ese stack fallido tras verificar
propiedad y una lista cerrada de recursos IAM/Scheduler. No borra ni modifica
la base retenida. La guarda aún necesita aplicación real antes de aceptar E0.


- Preflight completo aprobado: [42420579085](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42420579085).
  Presupuesto total creado desde CloudShell; no publica correo ni importes de cuenta.
- La cuenta Free Plan rechazó Aurora sin Express Configuration. Ese modo obliga
  a una pasarela de Internet y no admite la VPC privada requerida. Se reemplazó
  por RDS PostgreSQL 17 privado, cifrado, db.t4g.micro/20 GB, sin ampliar el plan.
  Fuente y costes residuales en `infra/aws/staging-bootstrap.md`.
- IaC `0579bf3c330e8861ba3276defc771cc084d82f61` aprobó los checks required,
  quality, backend-image y development-apk del PR #5. El reintento de CloudShell
  está pendiente de resultado; todavía no hay aceptación de staging.
- Guarda horaria de parada de RDS fuera de la ventana activa; retirada del
  servicio Express a tres horas. La base retenida conserva coste de storage,
  backups y secretos: detener compute no acredita coste cero.
- CD separa Deploy/Migrate, verifica SHA/digest y la red ALB→tarea real, y espera
  tareas nuevas antes de aceptar canary. Las migraciones usan un advisory lock
  PostgreSQL bajo la identidad migradora; no se cancelan al llegar otro commit.
- Último `make check`: 59 pruebas Python y 3 JS, PostgreSQL real, lint/tipos,
  cfn-lint, migraciones, Django y Expo aprobados. Esto es evidencia local;
  las pruebas de nube siguen pendientes.
- La API de rama confirmó main protegido y check obligatorio `required`.
  Los 403 históricos al endpoint detallado no significan ausencia de protección.

## Continuación E0 — evidencia actual

- Base inicial: `ebfa16a78dab201d665501d88783a1604c0b2e3e`, PR #2 integrado.
  CI de main aprobada: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42350965332.
- PR #3 integrado en `ab2f360c044a01f8b3dd0a8318ec7c32b0a380c7`, tras CI aprobada:
  https://github.com/A-PerfectStranger/special-funicular/actions/runs/42385253070.
  CI de main también aprobada: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42385848874.
  CD conserva bloqueo real por destinos incompletos, sin deploy ficticio.
- El usuario ejecutó en CloudShell `bootstrap-aws-preflight.sh` y creó el stack
  OIDC de lectura. El primer preflight no asumió el rol:
  https://github.com/A-PerfectStranger/special-funicular/actions/runs/42385863812.
  Se consultó la personalización OIDC real: `use_immutable_subject=true`.
  El prefijo contiene IDs de propietario/repositorio. El usuario aplicó la
  plantilla corregida `c41946ccdcfd2882713a77c7d4c9919c86e3eef0` desde CloudShell;
  las correcciones y diagnóstico están en PR #4, sin ampliar permisos ni wildcards.
- Segundo preflight: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42386350234.
  Artefacto `13579866092`: `account_matches_role=true`,
  `unrelated_iam_access_denied=true`, `credits_cover_150_usd=true` y
  `credits_valid_through_2027_05_06=true`; `gross_usage_read=false` y resultado
  global bloqueado. Sujeto exacto main, audiencia STS y permisos únicamente
  `freetier:GetAccountPlanState` / `ce:GetCostAndUsage`.
- El usuario comprobó la consulta CE desde CloudShell: `DataUnavailableException`.
  Facturas tampoco muestra datos. Cost Explorer confirmó literalmente:
  “Cost Explorer was just enabled - it will take some time to prepare your cost
  and usage data. Please check back in 24 hours”. El retraso no se resuelve dando
  permisos adicionales. Los reportes publican solo booleanos y códigos de error
  AWS; nunca importes, respuestas financieras, credenciales ni correo de alertas.
- El usuario confirmó saldo suficiente, plazo hasta el 6 de mayo de 2027 y correo
  de alertas; los datos privados exactos quedan fuera del repo público. El techo
  del proyecto sigue siendo 150 USD totales. No se aplicó el presupuesto ni se
  crearon recursos de aplicación/BD. El stack IAM sí existe; no afirmar coste
  cero de la cuenta ni que el presupuesto impone un corte rígido.
- No hay dominio y el usuario delegó la elección. Se consultaron tarifas oficiales
  `us-east-1`, incluyendo costes de Fargate/ALB/IP/Aurora/KMS/Secrets. Se registran
  fuentes, SKU y límites en `infra/aws/cost-estimate.md`. App Runner ya no admite
  clientes nuevos; ECS Express ofrece una URL administrada sin comprar dominio.
  Es un candidato pendiente de implementación/verificación, no un staging creado.

## Implementación y comprobaciones de esta continuación

- `scripts/verify_staging.py`: probes públicos E0 (RFS09/13/14, CA-S09/13/14).
  TLS 1.3 y certificado/hostname verificados, sin redirecciones; readiness DB,
  capabilities exactas, rutas de negocio/admin ausentes, escrituras rechazadas,
  cabeceras seguras y ausencia de cookies. No registra cuerpos ni excepciones.
  Sus 16 pruebas usan servidor TLS local real, incluyendo fallo DB, QR habilitado,
  tipo JSON incorrecto, cookies, redirección, falta de cabeceras, TLS 1.2 y CA no
  confiable. No son una aceptación de AWS ni certifican IAM/presupuesto/digest.
- `scripts/aws-env.sh`: CLI/perfil `aesir`/región y caché privada en `work/aws/`.
  CLI oficial 2.39.6 instalada con firma GPG verificada. La variable
  `AWS_VERIFICATION_CODE` llegó a esta instancia, sin imprimirse; el código es de
  otro intento PKCE y no permite iniciar un login nuevo. STS local dio
  `NoCredentials`. El control de navegador falló con
  `the gaas-browser node_repl sandbox cannot be disabled`; se abrió Chromium en
  el escritorio y se observó AWS sign-in, pero el usuario no pudo entrar a Desktop.
  El intento se canceló y se usó CloudShell/OIDC. No se pidieron claves permanentes.
- `github-preflight.yaml`, bootstrap CloudShell y workflow manual de lectura
  (RFS22 / CA-S22). Regresiones de sujeto/audiencia/acciones, aislamiento de
  credenciales temporales, ausencia de saldos en el reporte y códigos de error
  redactados. Las denegaciones y datos ausentes mantienen el bloqueo.
- Validación local final: `make check` con PostgreSQL real, 37 pruebas Python y
  3 JS, lint/typechecks, migraciones, Django y Expo; `make security` sin hallazgos;
  cfn-lint para ambos templates, actionlint 1.7.12 y sintaxis Bash.
  La evidencia de CI por commit se consulta en los PR #3/#4; no atribuir un build
  a otro SHA ni confundir las pruebas TLS locales con despliegue.
- Protección de main: consulta HTTP 403. Los checks se ejecutan, pero no se ha
  acreditado que GitHub imponga la protección de rama.

## Siguiente paso para cerrar E0

1. Cuando AWS publique gasto, repetir `AWS read-only preflight` desde main con el
   mismo ARN de lectura; no cambiar el secreto del código OAuth ni rehacer login.
2. Contrastar gasto/saldo con cotización completa, ajustar reserva entre fases y
   aplicar presupuesto/alertas con el contacto confirmado, sin datos privados en Git.
3. Preparar/aplicar IaC y permisos separados de despliegue/migración/runtime;
   implementar el adaptador live y verificar staging por SHA/digest y probes TLS.
4. Conservar evidencia real por commit antes de marcar staging/E0 terminados.
   No incorporar datos de escuelas ni habilitar funciones E1–E5.

El resto de este documento conserva la evidencia de la entrega anterior. Los
artefactos de sus SHA no se atribuyen a los scripts nuevos ni a un deploy AWS.

Base revisada: `c711ff9`, igual a `origin/main` al comenzar, tras fetch remoto.
Solo existían AGENTS, PLAN y requisitos; se leyeron completos. No había PROGRESS,
código ni pruebas. Rama `feat/e0-foundation`, PR:
https://github.com/A-PerfectStranger/special-funicular/pull/2

## Aceptación y evidencia

| Criterio definido antes de implementar | Estado acreditado |
| --- | --- |
| Checkout limpio y comandos reproducibles | Aprobado en runners GitHub: `make install db check`; locks uv/npm, imágenes por digest y plantilla SDK 56 fijada. |
| Django/templates/móvil/probes sin PII ni retiro parcial | Aprobado por pruebas y smoke de imagen; rutas de negocio/admin ausentes, retiro siempre deshabilitado. |
| CI lint/typecheck, unitarias, contratos, migraciones, PostgreSQL, secretos/dependencias | Aprobado: 15 tests Python, 3 tests JS; Ruff/mypy/ESLint/TypeScript, checks Django/Expo, pip-audit/npm audit/gitleaks sin hallazgos. |
| Imagen API/worker y APK con SHA/checksum/digest | Aprobado en CI y build local. Worker solo tiene diagnóstico; sin handlers E1/E4 falla explícitamente. APK arm64 standalone con clave de desarrollo. |
| Estructura CD y bloqueo honesto sin destino | Aprobado: validadores salen 2 con BLOCKED/NOT_CONFIGURED; workflow no inventa deploy. Adaptador live pendiente. |
| Staging real y kit AWS | BLOQUEADO: login y configuración de cuenta/recursos/dominio aún ausentes. |

Código/artefactos verificados: `586077c9e82e590a3ec586dacae277b217d1a345`.
Push CI aprobado: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42349447096
PR CI aprobado: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42349529509
Ambos aprobaron quality, backend-image, development-apk y required. Los checks de
revisiones posteriores aparecen en el PR; no atribuir estos artefactos a otro SHA.

### Pruebas y artefactos concretos

- PostgreSQL real: runtime sin SUPERUSER/BYPASSRLS/CREATEDB/CREATEROLE/DDL;
  sonda RLS forzada, escuelas separadas y contexto transaccional sin fuga.
  Esto no acredita las políticas futuras del dominio ni AT01–AT08.
- Imagen como 10001:10001, filesystem de solo lectura y /tmp efímero; probes
  aprobados y sin MIGRATION_DATABASE_URL en runtime.
- OCI manifest digest de CI para `586077c`:
  `sha256:9429903cef435dd0f1af5240a60c262f0493cdc35c25f0df19411ea6fb3ac827`.
  Artefacto OCI y manifiesto (retención 7 días):
  https://github.com/A-PerfectStranger/special-funicular/actions/runs/42349447096/artifacts/13564544466
- APK de CI compilado y firma verificada. SHA-256:
  `7b8eeb40a3457288b01e3a192672b1475273f6b5aad7b99941600544212afb18`.
  Solo se publica manifiesto porque el repo es público. Distribución privada del
  binario pendiente de destino autorizado; no se instaló en teléfonos.
- APK local del mismo código, build distinto (no igualdad binaria):
  `work/artifacts/mobile-development-586077c9e82e590a3ec586dacae277b217d1a345.apk`.
  SHA-256 `56ec9e3be09ebdb48062f0cc35d7ee2352593a9ef2c1f628ac1058d99c73c2ac`;
  apksigner aprobado: v2, RSA 2048, clave debug. Manifiesto .apk.json local.
  Archivo ignorado, no garantizado en un contenedor nuevo; reconstruir con make apk.
- cfn-lint y actionlint aprobados; presupuesto validado offline, no aplicado.
  Pruebas físicas en dispositivos pendientes de E5.

### Problemas corregidos y límites

- Docker no leía SQL montado: permisos de lectura corregidos.
- Plantilla nativa fuera del SDK: fijada a 56.0.38. Gradle 9 incompatible con
  Foojay/RN 0.85: plugin fija Gradle 8.14.3 y checksum oficial tras prebuild limpio.
- Dependencias transitivas vulnerables: overrides Zod/glob/minimatch y backport
  local deepmerge con licencia/regresiones porque no hay release upstream corregida.
  npm audit no analiza ese código local; sus pruebas permanecen obligatorias.
- Disco de unos 8 GB: varios intentos Android fallaron por espacio antes del build
  exitoso. Se retiraron cachés/herramientas opcionales locales; CI usó SDK completo.
  Después de verificar firma se eliminaron NDK/cachés Gradle temporales. Reinstalarlos
  según README antes de reconstruir. No se alteró fuente para ocultar fallos.
- gh falló al descargar redirects de artefactos; el conector GitHub recuperó logs y
  manifiesto. El OCI excede el límite de transferencia de 32 MiB del executor:
  conservar referencia GitHub, no afirmar una copia local verificada.
- Protección de rama/permisos de Actions: lectura HTTP 403. No se verificó que
  GitHub imponga E0 CI / required; los checks sí se ejecutaron y revisaron.

## AWS: evidencia de la sesión anterior

Usuario confirmó perfil aesir, experiencia avanzada (sin proyecto), us-east-1 y
máximo TOTAL 150 USD de créditos. Linux/curl/uv/red comprobados. CLI 2.39.6 instalada
con firma GPG verificada en work/bin/aws; perfil en work/aws/config. Rutas temporales
ignoradas, sin secretos en Git; una sesión nueva puede requerir reinstalación.

El navegador compartido falló con `the gaas-browser node_repl sandbox cannot be disabled`;
el usuario no tiene terminal del entorno. Se intentó aws login --remote y entregar
el código mediante secreto privado, sin leerlo/imprimirlo. Usuario confirmó que
secretos nuevos solo llegan a sesiones nuevas. Instancia actual: revisión 1,
secrets vacíos y variable ausente. Se canceló el intento: **login, STS, wizard,
MCP y catálogo NO verificados**. El código temporal guardado no sirve para iniciar
otro flujo: eliminarlo/renovarlo cuando exista canal interactivo, nunca pegarlo en chat.

Siguiente sesión: resolver navegador/terminal compartido o ejecutar el kit en el
equipo del usuario siguiendo infra/aws/README.md. Un login local no autentica este
contenedor. Tras login: STS, wizard humano, perfil env de aws-mcp, catálogo y reglas
oficiales añadidas a AGENTS sin sobrescribirlo. No pedir access keys/secret keys ni
declarar setup completo antes de verificar todos esos pasos.

No se crearon recursos AWS desde esta sesión. Saldo/gastos reales no consultados:
no afirmar gasto cero de la cuenta. Distribución de los 150 USD propuesta:
25 E1 + 35 E2/E3 + 20 E4 + 40 E5/despliegue + 30 reserva. Presupuesto CUSTOM y alertas
preparados, no aplicados; no son un corte rígido. Faltan correo/fechas reales,
saldo/vencimiento de créditos y cotización por horas. No destruir evidencia ni
claves retenidas para ahorrar.

## Continuación

1. Revisar integración y CI en el PR y sincronizar remoto antes de tocar código.
2. Completar autenticación/toolkit AWS; verificar saldo y presupuesto y configurar destinos.
3. Aprovisionar por IaC tras calcular coste y aportar dominio/configuración; implementar
   adaptador live y verificar staging. Mantener bloqueo hasta evidencia real.
4. Configurar custodia/firma estable y destino privado de APK; build no equivale a instalación.
5. Avanzar E1: IdP/MFA, modelos, RLS de dominio, evidencia y WORM/KMS reales sintéticos.
   Ningún requisito E1–E5 queda implementado por esta base E0.

## Reanudación: Cost Explorer disponible

El usuario confirmó disponibilidad y el preflight completo aprobó:
https://github.com/A-PerfectStranger/special-funicular/actions/runs/42420579085.
El presupuesto `retiro-seguro-budget` se creó desde CloudShell. El primer stack
`retiro-staging-base` falló al crear ECS Cluster: no pudo asumir el rol de servicio
ECS. Se preparó recuperación que comprueba/crea AWSServiceRoleForECS y preserva
secretos retenidos; se solicitó ejecutar `ef3f2d0c00e5a459bdd617a9d66204bdce0ab362`.
La base tiene validación estática, pero no se presenta como aprovisionada aún.
Publicador de imagen por digest, CA RDS e ingreso explícito están preparados;
faltan comisión SQL y despliegue/probes reales. E0 permanece abierto.

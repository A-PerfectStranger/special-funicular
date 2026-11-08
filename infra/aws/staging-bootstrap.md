# Bootstrap sintético E0: base administrada

Cost Explorer ya aprobó el preflight en la ejecución
https://github.com/A-PerfectStranger/special-funicular/actions/runs/42420579085.
Este incremento prepara infraestructura; no acredita aún un despliegue.
RFS09/10/22, CA-S09/10/22. No habilita negocio E1–E5.

`scripts/bootstrap-staging.sh <SHA revisado> <correo de alertas>` se ejecuta en
CloudShell porque la identidad existente solo permite leer facturación.
Comprueba cuenta, crédito y gasto sin publicarlos; aplica primero el presupuesto
total de 150 USD con las cinco alertas existentes y después la base CloudFormation:

- VPC dedicada, subredes públicas para tareas/ingreso y privadas para PostgreSQL,
  sin NAT Gateway ni acceso público a la base.
- RDS PostgreSQL 17 privado y cifrado, db.t4g.micro/20 GB, backup de ensayo de
  un día. Motor disponible seleccionado por la API regional y fijado por parámetro.
  Parada programada independiente del stack de datos, para no dejar compute
  encendido tras los ensayos ni después del reinicio automático de siete días.
- Contraseñas/clave Django en Secrets Manager, cifrado KMS administrado por AWS.
  La credencial API solo permite leer su contraseña y clave Django; la credencial
  de migración y el bootstrap inicial tienen permisos separados. No son aún los
  roles funcionales ni los escritores de evidencia de E1.
- ECR privado con tags inmutables, cluster y logs de siete días; roles GitHub
  OIDC separados para publicación/despliegue y migración, sujeto exacto de main.
- Rol de infraestructura Express asumible solo por ECS con la política oficial
  AWS; nunca se entrega al contenedor ni al humano de aplicación.

No crea servicio API/ALB todavía. Eso requiere publicar el artefacto aprobado,
crear roles SQL con la tarea privada de bootstrap, aplicar migraciones y verificar
canal/aislamiento; se completa durante la comisión de staging. La base y secretos
se retienen ante borrado/reemplazo; no hay borrados genéricos ni evidencia WORM.
La protección contra borrado de RDS está habilitada.

## Coste y límites

Tarifas oficiales/SKU en `cost-estimate.md`. RDS db.t4g.micro: 0.016 USD/h
cuando está activo. Detenido no cobra compute, pero sí almacenamiento/backups/secrets.
Con 20 GB y cuatro secretos, el coste residual previsto es aproximadamente 3.90
USD/mes antes de requests, I/O, logs, backup adicional y ECR. Se reserva hasta 27
USD de la reserva existente de 30 USD hasta el vencimiento del crédito; si el
crecimiento/retención lo supera, recalcular antes de continuar. No es garantía
ni corte de gasto. El stop de RDS dura como máximo siete días: la guarda horaria
vuelve a pararlo tras reinicios, salvo durante la ventana activa de staging.

El ensayo inicial de compute/ingreso de E0 debe limitarse a tres horas y 3 USD,
reasignados de la bolsa E1 (25 a 22 USD), conservando total 150 USD. La retirada
verificada del servicio/ALB es necesaria al terminar esa ventana: bajar tareas
solamente no elimina el coste de ALB/IP. La base puede quedar detenida, con su
coste residual reservado y una guarda horaria que cubra el reinicio automático. No afirmar gasto cero por detenerla.

## Validación de preparación

`cfn-lint infra/aws/staging-base.json`, sintaxis Bash y regresiones estáticas de
red privada, cifrado, capacidad y separación de secretos. Estos checks no son
una prueba de IAM/RDS real. El bootstrap valida también la plantilla en AWS antes
de aplicarla y devuelve los ARN de Deploy/Migrate; no devuelve claves.

## Estado de la aplicación inicial

El presupuesto se creó realmente desde CloudShell. El primer stack de base falló
en ECS por ausencia/propagación de `AWSServiceRoleForECS`, antes de publicar API.
`prepare_staging_account.py` comprueba/crea esa identidad de servicio. Solo elimina
un stack `ROLLBACK_COMPLETE` si no conserva recursos RDS; los secretos retenidos
se reutilizan por ARN tras comprobar etiqueta Project y ausencia de borrado
pendiente. No se leen valores ni se destruyen secretos para reintentar.

`staging-publish.yml` publica exclusivamente artefactos OCI de un `E0 CI` aprobado,
disparado por push en main del repositorio esperado. Comprueba SHA/checksum y
conserva/verifica digest en ECR. OIDC efímero bajo el rol Deploy, sin claves en
GitHub. Este workflow manual de comisión publica una imagen; no afirma despliegue.

La imagen incorpora el bundle CA regional oficial de RDS en `/app/rds-ca.pem`.
Las tareas cloud usarán `PGSSLMODE=verify-full` y `PGSSLROOTCERT` con esa ruta.
`TRUSTED_INGRESS=ecs-express` habilita confianza en X-Forwarded-Proto solo tras
restringir ingreso de la tarea al ALB administrado. No habilitarlo con ingreso
directo a la tarea. Liveness se exime de redirect para la sonda privada de ALB;
la entrada pública debe seguir usando TLS 1.3 verificado.

El comando SQL privado de comisión verifica TLS real, RLS forzada con dos escuelas
sintéticas, ausencia de fuga transaccional y denegación de mutaciones/DDL para
runtime. Ejecuta migración con credencial distinta y diagnóstico worker; no
arranca un worker ficticio: los handlers E1/E4 siguen pendientes.

La cuenta Free Plan rechazó la retención automática inicial de siete días. Se
usa un día para esta base sintética E0; no es una política de conservación de
menores/evidencias ni una aceptación de recuperación E5. No se amplía el plan.

## Comisión y despliegue continuo

Después de publicar la imagen aprobada, `commission-staging.sh` descarga el mismo
commit de código, aplica el stack IAM de lifecycle, ejecuta la prueba SQL privada,
crea la API Express y arma retirada automática a las tres horas. Si no puede armar
la retirada, solicita eliminar el servicio recién creado y falla. Publica evidencia
sintética (SHA/digest/URL/tarea/probes); no lee contraseñas. Este script es operación
inicial de CloudShell, no promoción manual rutinaria de producción.

El CD posterior toma el mismo artefacto de CI y digest ECR, migra con el rol Migrate,
despliega con Deploy y comprueba runtime/health/TLS antes de considerar staging
aprobado. Rechaza candidatos que ya no son el último main antes de cada mutación,
y serializa el workflow sin cancelar migraciones. El comando privado
`migrate_locked` exige la identidad SQL migradora y mantiene un advisory lock
de sesión PostgreSQL hasta completar la migración, incluso si otro runner
comienza después de que expire la espera externa. Espera que todas las tareas de
servicio usen la nueva definición; ACTIVE de Express por sí solo no acredita el
final de una canary. Acepta digest de índice OCI o su manifest Linux amd64 solo
tras verificar el hash del índice y la pertenencia criptográfica del hijo.

La retirada programada afecta solo al servicio ECS de staging; RDS/secretos
persisten protegidos con coste residual reservado. Recrear API exige mismo digest
verificado y vuelve a armar expiry. Producción sigue bloqueada hasta configuración
y aceptación E5. Ningún probe E0 acredita OIDC humano, WORM o retiros de negocio.

## Decisión final de base para Free Plan

Aurora Free Plan exige WithExpressConfiguration. La documentación oficial indica
que ese modo no admite VPC y obliga a una pasarela de Internet, por lo que se
rechaza para este contrato. Se usa RDS PostgreSQL privado, documentado para cuentas
Free Plan, sin cambiar el requisito de PostgreSQL administrado ni ampliar el plan.

- https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/CHAP_GettingStartedAurora.AuroraPostgreSQL.ExpressConfig.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_GettingStarted.CreatingConnecting.PostgreSQL.html

La primera limitación observada de backup y el experimento Aurora anteriores son
históricos, no configuración productiva. La retención de un día aquí es un backup
técnico de ensayo; no define conservación de datos personales/evidencia E1–E5.

## Recuperación de lifecycle

`python3 -m scripts.configure_staging_lifecycle --template infra/aws/staging-lifecycle.yaml`
comprueba la cuenta y aplica la ventana de tres horas con fecha UTC que incluye
milisegundos, formato exigido por CloudFormation/Scheduler. Ante ROLLBACK_COMPLETE,
solo recrea `retiro-staging-lifecycle` si pertenece al proyecto y contiene
exclusivamente los recursos IAM/Scheduler previstos; no elimina el stack de datos.
El bootstrap y la comisión inicial utilizan este mismo reparador. RFS22/CA-S22.

## Reanudar una API ya creada

Express puede omitir networkConfiguration/loadBalancers/taskDefinition de
DescribeServices. La comprobación consulta activeConfigurations de Express y
resuelve los target groups de DescribeServiceRevisions; verifica el ALB y los
security groups reales antes de confiar en X-Forwarded-Proto. La política
lifecycle añade solo esa lectura regional, sin acceso a valores de secretos.

`commission-staging.sh SOURCE_SHA IMAGE_SHA DIGEST --existing-service` actualiza
lifecycle, repite las comprobaciones SQL sintéticas y acepta la API existente sin
crearla otra vez. Comprueba el presupuesto real y emite configuración pública de
entorno, digest y probes. La configuración identifica un destino provisionado; no acredita aceptación.
E0 requiere passed=true y verificación del CD con los roles separados. RFS09/13/14/22 y CA-S09/13/14/22.

La sonda interna ALB envía Host=IP privada. Bajo TRUSTED_INGRESS=ecs-express,
LivenessMiddleware responde exclusivamente GET/HEAD de /health/live antes de
CommonMiddleware, conservando cabeceras seguras y sin consulta SQL ni estado.
El resto de rutas y métodos mantiene ALLOWED_HOSTS/CSRF/redirección HTTPS.
La configuración de entorno registra la infraestructura observada; el adaptador
resuelve revisiones, red y URL vigentes desde AWS en cada despliegue. Que el
validador estructural apruebe el destino no acredita probes ni aceptación E0.

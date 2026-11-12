# Comisión técnica de producción

Estado y aceptación: [PLAN](../../PLAN.md). Esta primera ventana despliega el
software con las rutas de negocio apagadas. No acredita E4/E5, distribución
productiva, recuperación integral ni activación escolar. No habilitar banderas
para convertir un despliegue técnico en aceptación funcional.

## Destino y límites

- Cuenta `028364485203`, `us-east-1`; VPC `10.62.0.0/16`, cluster/BD/secretos
  `retiro-production`, separados de staging. PostgreSQL 17 privado, TLS obligatorio,
  KMS propio, backup/PITR de **un día** y protección contra borrado.
  Es la retención aprobada por el responsable para mantener el plan gratuito;
  restaurar un estado anterior a esa ventana requiere otro respaldo disponible.
- Se consume **el mismo digest** del registro inmutable `retiro-staging/backend`.
  Solo se comparte el artefacto: producción no puede leer secretos ni BD de staging,
  y sus roles de promoción no escriben en el registro. No reconstruir la imagen.
- Runtime y migración tienen credenciales distintas. Bootstrap es una tarea
  privada del operador; prepara los roles requeridos por todas las migraciones.
  Lectores, importer, archiver y notifier permanecen NOLOGIN durante esta etapa;
  el escritor es NOLOGIN. No introducir credenciales root en API o Actions.
- La API se retira a las tres horas. La guarda horaria detiene RDS después de la
  ventana, incluso ante reinicios semanales. Conserva datos, backups, claves y
  secretos; no es operación continua de una escuela ni garantiza una URL estable.
  La retirada programada requiere comprobar su ejecución real.

## Preflight de operador, sin crear recursos

CloudShell necesita AWS CLI, Git y Python 3, con identidad humana de la cuenta.
El plan debe permanecer `FREE` y `ACTIVE`. La retención RDS de un día coincide
con la base staging disponible; una restricción adicional de AWS bloquea la
comisión, nunca se solventa cambiando a PAID. El techo total sigue en USD 150,
con preflight de gasto bruto más reservas antes de cada operación.
Consultar [planes AWS](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).
El preflight nunca cambia el plan de cuenta.
El código de comisión debe ser un checkout limpio del **main aprobado por CI**;
no ejecutar bootstrap privilegiado desde una rama pendiente de checks.

1. Obtener SHA y digest del candidato de main con CI y staging aprobados. Usar el
   artefacto `staging-deployment-SHA` de Actions; no confundirlo con el checksum ZIP
   ni deducir la revisión a partir de la última documentación.
2. Preparar una revisión de precios privada:

   ```bash
   mkdir -p work
   chmod 700 work
   cp infra/environments/production-cost-plan.example.json work/production-cost-plan.json
   chmod 600 work/production-cost-plan.json
   ```

   Completar `pricing_checked_at` con la hora UTC real de revisión y
   `custody_until` con la fecha financiada, ambas ISO8601 con zona. La revisión
   debe tener menos de 24 horas y financiar al menos 97 días desde la operación;
   dejar margen para las siguientes ejecuciones. Confirmar
   `operator_verified_official_prices` solo después de contrastar los precios
   [oficiales](../../infra/aws/README.md#presupuesto-y-costes-retenidos) y el
   inventario retenido. Las reservas iniciales son USD 40 nuevos + 50 retenidos
   + 30 contingencia, total USD 120 antes del gasto ya incurrido; deben seguir
   cabiendo en USD 150. No reducirlas para forzar un resultado aprobado.
   Los importes de ejemplo son **reservas de trabajo**,
   no una cotización ni saldo observado. Incluir aprovisionamiento, ventana,
   RDS/almacenamiento/backups, KMS, secretos, ECR, logs, IPv4/ALB y custodia.

   ```bash
   python3 -m scripts.production_preflight --cost-plan work/production-cost-plan.json
   ```

   Lee STS, Budgets, Cost Explorer y el estado FREE. Exige plan activo durante
   **toda** la custodia, coste bruto sin créditos/reembolsos, resultados completos,
   gasto más reservas <= USD 150 y crédito restante suficiente para las reservas.
   Usa el vencimiento del plan gratuito como límite conservador de continuidad;
   no lo presenta como la fecha real de vencimiento del crédito. AWS documenta
   [seis meses de plan y doce de crédito](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-FAQ.html).
   Si el plan caduca antes de la custodia, bloquea; no cambia a PAID ni acorta
   las retenciones de evidencia para superar el control. Resultado público: solo
   booleanos en `work/production-preflight.json`. Un dato ausente o un preflight
   fallido bloquean, no equivalen a gasto cero. No publicar balances ni el plan privado.

## Comisión de infraestructura y servicio

No ejecutar durante otra migración/comisión/despliegue. Actions serializa CD y
SQL usa un lock de migración; antes de operar desde CloudShell comprobar que no
hay otro despliegue ni tarea de migración activos. Sustituir los valores por la
identidad exacta del candidato aprobado; los placeholders no son ejecutables.

```bash
python3 -m scripts.commission_production --step foundation \
  --sha SHA_COMPLETO_APROBADO --digest sha256:DIGEST_APROBADO \
  --cost-plan work/production-cost-plan.json
```

Repite el preflight antes de modificar AWS. Aplica `production-base.json` y
`production-lifecycle.yaml` y almacena la revisión privada en SSM
`/retiro-production/cost-plan` para que CD pueda comprobar presupuesto actualizado
sin aprobación manual de promoción. `foundation` nunca elimina stacks fallidos;
ante ROLLBACK/deriva usar la inspección restringida siguiente. No repetir el
comando sobre `ROLLBACK_COMPLETE` ni eliminar recursos manualmente.

```bash
python3 -m scripts.commission_production --step commission \
  --sha SHA_COMPLETO_APROBADO --digest sha256:DIGEST_APROBADO
```

Arma retirada antes del arranque, comprueba BD/backup/KMS, ejecuta bootstrap y
migración aislados y crea/verifica Express con el mismo digest. Comprueba red
ALB → tarea, TLS 1.3, readiness y rutas de negocio deshabilitadas. Un servicio
existente usa rollback de código compatible y verifica la salud restaurada;
no restaura backups ni toca evidencias. Un inicio ambiguo de tarea no se reintenta;
solo TaskFailedToStart sin ejecución admite un reintento acotado.

Salidas de éxito: `work/production-commission.json` y propuesta pública
`work/production-configuration.json`. El archivo versionado no cambia cuando
falla una operación. Revisar la propuesta contra AWS y llevar **solo esa
configuración pública** a `infra/environments/production.json` mediante PR.
No incorporar planes privados, logs, credenciales ni capturas de consola.

Después de integrar la configuración, CD ejecuta staging/E1/E2/E3 y después
producción: preflight/ventana → migración → despliegue/probes. Usa OIDC
`retiro-production-Deploy` y `retiro-production-Migrate`, sujeto main exacto,
serialización sin cancelación y rechazo de candidatos obsoletos. Artefactos
`production-preflight-SHA`, `production-migration-SHA` y
`production-deployment-SHA`. Un destino todavía incompleto sigue BLOCKED.

La preparación arma la ventana; el despliegue no la prolonga para compensar una
migración lenta. La retirada o cambio de pasarela bloquean el origen anterior:
recomisionar el destino observado y revisar su configuración antes de repetir CD.
No omitir las comprobaciones ni ampliar permisos para reutilizar una URL retirada.

## Recuperación de foundation sin base de datos

Ante `ROLLBACK_COMPLETE`, conservar logs privados y trabajar desde main limpio
aprobado. Inspección **solo lectura**, sin leer valores de secretos:

```bash
python3 -m scripts.production_recovery --plan work/production-recovery-plan.json
```

El plan privado fija el StackId exacto, huella de recursos, clave y secretos.
Exige ausencia de `retiro-production` mediante RDS; ni `CREATE_FAILED` ni
`DELETE_SKIPPED` demuestran ausencia. CloudFormation puede conservar el registro
`Database` como `DELETE_SKIPPED` por `Retain` aunque RDS rechazara su creación.
Ese caso solo se acepta para el identificador exacto `retiro-production`, con
ausencia comprobada por RDS y ambas políticas de retención `Retain` verificadas.
Un error de permisos al consultar RDS bloquea; no equivale a ausencia.
Solo permite los demás recursos eliminados o claves/secretos conocidos con
`DELETE_SKIPPED` y políticas Retain verificadas. Comprueba cuenta, etiquetas,
rotación y política KMS. Una BD existente, permisos insuficientes, un recurso
superviviente inesperado o deriva bloquean. No borrar BD, claves, secretos ni
evidencias para superar el bloqueo.

Con plan FREE activo durante toda la custodia, financiación revisada, main CI
y staging aprobados, y sin otra operación activa:

```bash
python3 -m scripts.commission_production --step recover-foundation \
  --sha SHA_COMPLETO_APROBADO --digest sha256:DIGEST_APROBADO \
  --cost-plan work/production-cost-plan.json \
  --recovery-plan work/production-recovery-plan.json
```

Revalida fuente, presupuesto y plan; compara la inspección actual con la privada.
Solo entonces elimina **el registro del stack fallido por su StackId exacto**,
conservando los recursos Retain. Verifica su conservación y recompone foundation
referenciando esa misma clave y secretos, sin crear otra CMK para sustituirlos.
Este camino no recupera ni restaura datos y no acredita recuperación E5.

Si se interrumpe después de eliminar el registro, comprobar que ese stack ya no
existe y que no hay BD. Conservar el mismo plan privado; continuar con
`--step foundation --recovery-plan work/production-recovery-plan.json` y los demás
argumentos anteriores. No repetir `recover-foundation` contra un stack nuevo.
Si ya existe una BD o el estado es ambiguo, detenerse e inspeccionar; no adoptar
ni eliminar la BD automáticamente.

Los fallos emiten etapa y códigos saneados en
`work/production-operation-failure.json`; los detalles remotos permanecen en logs
privados del operador. No publicar cuerpos de excepciones ni credenciales.
`RECOVERY_UNEXPECTED_SURVIVOR` exige inspeccionar tipo, nombre lógico y estado de
los recursos; no autoriza eliminarlos. `RECOVERY_RETENTION_POLICY_DRIFT` bloquea
ante políticas distintas de `Retain`. Los fallos de lectura AWS indican solo
la operación y un código permitido; no exponen identificadores físicos ni secretos.

## Aceptación de esta etapa y siguiente paso

Comprobar por SHA: preflight real, identidad/secretos/red separados, bootstrap
seguro, migración única, digest en ejecución, sondas TLS, rollback cuando proceda
y retirada real de API/ALB/RDS. Las pruebas PostgreSQL locales no acreditan estos
resultados AWS. Mientras falten, producción no se declara desplegada/verificada.

Para operación escolar siguen siendo necesarios E4, IdP/WORM/KMS productivos,
retención aplicada, recuperación/epoch/carga, APK y firma productivos, distribución
privada y pruebas Android/presenciales de [E5](e5.md). Los bloqueos de Django y de
la configuración productiva se conservan hasta implementar y acreditar esa etapa.

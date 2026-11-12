# Comisión técnica de producción

Estado y aceptación: [PLAN](../../PLAN.md). Esta primera ventana despliega el
software con las rutas de negocio apagadas. No acredita E4/E5, distribución
productiva, recuperación integral ni activación escolar. No habilitar banderas
para convertir un despliegue técnico en aceptación funcional.

## Destino y límites

- Cuenta `028364485203`, `us-east-1`; VPC `10.62.0.0/16`, cluster/BD/secretos
  `retiro-production`, separados de staging. PostgreSQL 17 privado, TLS obligatorio,
  KMS propio, backup/PITR de siete días y protección contra borrado.
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
   inventario retenido. Los importes de ejemplo son **reservas máximas de trabajo**,
   no una cotización ni saldo observado. Incluir aprovisionamiento, ventana,
   RDS/almacenamiento/backups, KMS, secretos, ECR, logs, IPv4/ALB y custodia.

   ```bash
   python3 -m scripts.production_preflight --cost-plan work/production-cost-plan.json
   ```

   Lee STS, Budgets, Cost Explorer y crédito/vigencia. Exige coste bruto sin
   créditos/reembolsos, resultados completos, gasto más reservas <= USD 150 y
   crédito suficiente hasta la custodia financiada. Resultado público: solo
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
sin aprobación manual de promoción. Nunca elimina stacks fallidos ni recursos
retenidos para reintentar; ante ROLLBACK/deriva inspeccionar eventos privados.

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

## Aceptación de esta etapa y siguiente paso

Comprobar por SHA: preflight real, identidad/secretos/red separados, bootstrap
seguro, migración única, digest en ejecución, sondas TLS, rollback cuando proceda
y retirada real de API/ALB/RDS. Las pruebas PostgreSQL locales no acreditan estos
resultados AWS. Mientras falten, producción no se declara desplegada/verificada.

Para operación escolar siguen siendo necesarios E4, IdP/WORM/KMS productivos,
retención aplicada, recuperación/epoch/carga, APK y firma productivos, distribución
privada y pruebas Android/presenciales de [E5](e5.md). Los bloqueos de Django y de
la configuración productiva se conservan hasta implementar y acreditar esa etapa.

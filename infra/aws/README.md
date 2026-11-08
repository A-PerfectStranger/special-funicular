# AWS — infraestructura y operación de staging

AWS `us-east-1`, perfil humano `aesir`. Parámetros del destino en
[staging.json](../environments/staging.json) y
[production.json](../environments/production.json); estado y alcance de aceptación
en [PLAN.md](../../PLAN.md). Las plantillas y scripts son la fuente ejecutable.
La URL de Express es temporal: contrastar el origen observado por AWS con la
configuración y los callbacks antes de usar identidad.

## Presupuesto y costes retenidos

Techo de **150 USD totales** para desarrollo y primer despliegue. El crédito
confirmado vence el 6 de mayo de 2027; verificar saldo, vigencia y gasto antes de
cada sesión cloud, sin publicar balances ni correo de alertas.

| Uso | Máximo reservado USD |
| --- | ---: |
| E0: ventana inicial de staging | 3 |
| E1: ensayos IdP/PostgreSQL/KMS/WORM | 22 |
| E2/E3: integración y concurrencia | 35 |
| E4: avisos, consulta y observabilidad | 20 |
| E5 y primera ventana de despliegue | 40 |
| Reserva: incidentes, retención y variación | 30 |
| Total | 150 |

Son límites de trabajo, no tarifas. `budget.yaml` define un presupuesto total de
coste bruto, sin descontar créditos, con alertas 25/50/75/90/100%; requiere correo y
fechas reales. Budgets tiene demora y no impone un corte rígido. Si faltan datos de
gasto o el saldo no cubre la reserva y el plan restante, no aprovisionar. Cost
Explorer debe estar habilitado y disponer de datos; un resultado ausente no es cero.

La base retenida tiene una reserva de hasta 27 USD dentro de los 30 anteriores.
RDS detenido conserva costes de almacenamiento, backups y secretos, y puede
reiniciarse a los siete días. E1 añade claves KMS, secretos y archivo retenido:
recalcular el inventario completo y sus costes hasta el vencimiento. No eliminar
WORM ni claves necesarias durante su retención para reducir gasto.

Antes de nuevos recursos, consultar precios oficiales vigentes de
[RDS](https://aws.amazon.com/rds/postgresql/pricing/),
[Fargate](https://aws.amazon.com/fargate/pricing/),
[ALB](https://aws.amazon.com/elasticloadbalancing/pricing/),
[VPC/IPv4](https://aws.amazon.com/vpc/pricing/),
[S3](https://aws.amazon.com/s3/pricing/),
[KMS](https://aws.amazon.com/kms/pricing/),
[Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/) y
[Cognito](https://aws.amazon.com/cognito/pricing/).
Incluir horas, almacenamiento, backup/PITR, versiones de claves, requests, logs,
ECR, transferencia e impuestos. Preferir builds locales/CI y ventanas de ensayo;
no dejar NAT Gateway, réplicas o ingreso encendidos sin presupuesto.

## Infraestructura versionada

| Plantilla | Responsabilidad |
| --- | --- |
| `github-preflight.yaml` | OIDC de lectura de facturación; sin despliegue ni secretos. |
| `budget.yaml` | Presupuesto total y alertas. |
| `staging-base.json` | VPC, RDS, ECR, secretos base y roles Deploy/Migrate. |
| `staging-lifecycle.yaml` | Retirada de API/ALB y guarda de RDS. |
| `e1-staging.yaml` | Cognito, WORM/KMS, secretos e identidades separadas E1. |

La base usa RDS PostgreSQL 17 privado y cifrado, db.t4g.micro/20 GB, backup
sintético de un día y protección contra borrado. Aurora Express exige una pasarela
pública sin VPC y no satisface este contrato. No ampliar el plan de cuenta para
sustituir la base. El backup de ensayo no define conservación institucional ni
acredita recuperación productiva.

Tareas/ingreso en subredes públicas, PostgreSQL en privadas y sin NAT Gateway.
ECS Express proporciona URL/certificado administrados, sin comprar dominio.
La entrada a tareas se limita a las SG del ALB real. ECR usa tags inmutables;
logs de ensayo de siete días; datos, secretos y claves tienen políticas de retención.

GitHub OIDC confía en audiencia `sts.amazonaws.com` y sujeto exacto
`repo:A-PerfectStranger@144553443/special-funicular@1449067177:ref:refs/heads/main`.
Si cambia el repositorio o su personalización OIDC, contrastar metadatos y ajustar
plantillas/pruebas; no sustituir por wildcard. Deploy publica/despliega y Migrate
migra con identidad SQL separada. El bootstrap SQL queda en tareas privadas;
CI/runtime no reciben la credencial raíz. No usar claves permanentes.

## Bootstrap con operador CloudShell

Ejecutar desde un checkout limpio del SHA completo revisado, con AWS CLI/Python 3
y sesión de operador de la cuenta. No confundir ese login con la identidad OIDC
limitada de CI. La ruta operativa es CloudShell/OIDC; el toolkit interactivo no
es requisito del repositorio.

1. Preparar el rol de lectura si falta:

   ```bash
   bash scripts/bootstrap-aws-preflight.sh SHA_COMPLETO_REVISADO
   gh workflow run aws-preflight.yml --ref main \
     -f role_arn=ARN_DEVUELTO_POR_BOOTSTRAP
   ```

   Comprueba STS, denegación de IAM ajeno, créditos/vigencia y gasto bruto.
   El reporte público contiene booleanos; el rol no puede desplegar ni leer secretos.
2. Crear o actualizar presupuesto y base:

   ```bash
   bash scripts/bootstrap-staging.sh SHA_COMPLETO_REVISADO CORREO_DE_ALERTAS
   ```

   Valida cuenta/crédito/gasto, aplica presupuesto y base, selecciona una versión
   PostgreSQL 17 disponible y arma lifecycle. La base no crea por sí sola API/ALB.
3. Publicar el OCI de un CI de push main aprobado mediante `staging-publish.yml`.
   Su input es `ci_run_id`; conserva checksum/digest. Publicar no acredita deploy.
4. Comisionar SQL, API y retirada con el mismo artefacto aprobado:

   ```bash
   bash scripts/commission-staging.sh SHA_FUENTE_REVISADO SHA_IMAGEN_APROBADA DIGEST_OCI
   ```

   Añadir `--existing-service` para verificar una API existente sin volver a
   crearla. La comisión comprueba TLS SQL, RLS, permisos, migraciones y probes;
   registra `work/staging-evidence.json`. Validar la configuración pública emitida
   antes de incorporarla al archivo del entorno.
5. Comisionar identidad y archivo con el [runbook E1](../../docs/runbooks/e1.md).
   La publicación rutinaria sigue el [runbook de despliegue](../../docs/runbooks/deployment.md).

Los scripts preparan la identidad de servicio ECS si falta. Solo se recupera un
stack base `ROLLBACK_COMPLETE` cuando no conserva recursos RDS; los secretos
retenidos se reutilizan tras verificar etiquetas y ausencia de borrado pendiente.
No destruir datos o secretos para reintentar un bootstrap.

## Lifecycle, red y diagnóstico

```bash
python3 -m scripts.configure_staging_lifecycle --template infra/aws/staging-lifecycle.yaml
```

El configurador valida cuenta y ventana de tres horas; usa fecha UTC con
milisegundos para Scheduler. Solo recrea un lifecycle `ROLLBACK_COMPLETE` si
pertenece al proyecto y contiene exclusivamente los recursos IAM/Scheduler
previstos. Nunca elimina el stack de datos.

Scheduler retira API/ALB a las tres horas. La guarda horaria detiene RDS fuera de
ventanas, incluidos reinicios automáticos semanales. Bajar tareas solamente no
elimina ALB/IP. Comprobar la retirada real; una programación no prueba ejecución.
El archivador E1 también tiene vida acotada, descrita en su runbook.

Recrear Express requiere `ecs:TagResource` limitado al ARN de `retiro-api`, contexto
de creación y tags Project/Environment del staging. No ampliar a reetiquetado
arbitrario. Referencia:
[autorización de tags ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/supported-iam-actions-tagging.html).

DescribeServices puede omitir red/targets/definición: el adaptador resuelve
activeConfigurations y DescribeServiceRevisions y contrasta ALB/SG reales.
`TRUSTED_INGRESS=ecs-express` solo es válido con acceso limitado al ALB;
`/health/live` permite GET/HEAD stateless con Host=IP privada para su sonda.
Las demás rutas mantienen ALLOWED_HOSTS/CSRF/HTTPS; no abrir un wildcard.
SQL cloud usa `PGSSLMODE=verify-full` y `/app/rds-ca.pem`, incluido en la imagen.

Validación local: `make lint` incluye cfn-lint; CI y pruebas de infraestructura
comprueban las plantillas. Eso no acredita IAM efectivo, coste o despliegue real.
Probes públicos, verificación de digest y límites de un proxy TLS se describen en
el runbook de despliegue. Un fallo se inspecciona privadamente en eventos de
CloudFormation/CloudWatch; publicar solo diagnósticos saneados.

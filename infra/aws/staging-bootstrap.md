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
- Aurora PostgreSQL Serverless v2 cifrado, PITR 7 días, auto-pause a 0 ACU tras
  300 s sin conexiones y máximo 1 ACU; motor seleccionado por la API regional,
  verificado como disponible y fijado como parámetro del stack.
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
La protección contra borrado de Aurora está habilitada.

## Coste y límites

Tarifas oficiales/SKU en `cost-estimate.md`. Hasta 1 ACU activo: 0.12 USD/h;
pausado no cobra ACU, pero sí almacenamiento/backup/secrets. Para planificación,
10 GB de datos y cuatro secretos suman aproximadamente 2.60 USD/mes antes de
requests, I/O, logs, backup adicional y ECR. Se reservan hasta 18 USD de la reserva
existente de 30 USD para esos costes de base hasta el vencimiento del crédito;
si crecimiento/retención lo supera, recalcular antes de continuar. No es garantía
ni corte de gasto. No crear funciones WORM/E1 con esos supuestos por omisión.

El ensayo inicial de compute/ingreso de E0 debe limitarse a tres horas y 3 USD,
reasignados de la bolsa E1 (25 a 22 USD), conservando total 150 USD. La retirada
verificada del servicio/ALB es necesaria al terminar esa ventana: bajar tareas
solamente no elimina el coste de ALB/IP. La base puede quedar pausada, con su
coste residual reservado. No afirmar gasto cero por detenerla.

## Validación de preparación

`cfn-lint infra/aws/staging-base.json`, sintaxis Bash y regresiones estáticas de
red privada, cifrado, capacidad y separación de secretos. Estos checks no son
una prueba de IAM/RDS real. El bootstrap valida también la plantilla en AWS antes
de aplicarla y devuelve los ARN de Deploy/Migrate; no devuelve claves.

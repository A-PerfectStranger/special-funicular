# Publicación y recuperación: estado E0

## Estado real

AWS elegido: región `us-east-1`, perfil humano `aesir`, máximo TOTAL 150 USD
de créditos para desarrollo/despliegue. No equivale a 150 USD mensuales.
Identidades AWS OIDC de lectura, Deploy y Migrate verificadas desde GitHub/main.
Staging real aceptado: https://re-ebedcb6688b94b228cd28424e44448c6.ecs.us-east-1.on.aws. SHA/digest y ejecución concreta en PROGRESS.md.
Producción sigue sin configurar hasta E5; el job production bloquea explícitamente.
La CLI interactiva local/kit no está autenticada; los comandos de bootstrap se
realizaron en CloudShell. No hacen falta claves permanentes para el CD.

## Publicación rutinaria

1. Abrir PR y completar required: calidad, imagen inmutable y APK. main exige PR/check.
2. Al integrar, E0 CI construye los artefactos del SHA main. workflow_run de CD
   verifica repositorio/evento, conserva checksum/digest y publica en ECR inmutable.
3. Deploy abre una ventana de tres horas e inicia solo RDS staging si está detenido.
4. Migrate ejecuta una tarea Fargate con su secreto SQL separado y migrate_locked;
   el advisory lock PostgreSQL serializa incluso si un runner deja de esperar.
5. Deploy actualiza Express con el mismo digest; espera todas las tareas nuevas,
   verifica índice OCI/manifest amd64, red ALB→tarea y ocho probes TLS. Evidencia:
   artefacto staging-deployment del workflow. No importar familias ni enviar avisos.
6. Producción solo se habilita tras configuración/aceptación E5. No añadir una
   aprobación humana rutinaria de promoción. cancel-in-progress=false en CD.

```bash
python3 scripts/validate_deploy.py infra/environments/staging.json
python3 scripts/validate_deploy.py infra/environments/production.json
```

Staging valida estructura; producción sale 2 hasta configurar E5. Un archivo
válido por sí solo no prueba IAM, coste, TLS ni despliegue. Para diagnóstico público:
`python3 scripts/verify_staging.py https://DOMINIO-STAGING --report work/staging-probes.json`.
Un proxy TLS interceptante impide usar ese cliente como atestación TLS del origen;
los probes de aceptación se ejecutan desde runner sin ese proxy.

## Comisión y coste

Infraestructura/recuperación: infra/aws/staging-bootstrap.md. La comisión inicial
CloudShell conserva DB/secretos; --existing-service verifica la API ya creada sin
volver a crearla. DescribeServices puede omitir red/targets: usar la revisión
activa de Express y DescribeServiceRevisions, no asumir campos de servicios clásicos.
La sonda ALB con Host=IP privada solo está exceptuada para GET/HEAD stateless de
/health/live en la configuración explícita ecs-express. Nunca ampliar ALLOWED_HOSTS
a un wildcard general para resolver el healthcheck.

API/ALB se retiran a las tres horas por Scheduler. RDS conserva datos y se detiene
mediante guarda horaria fuera de ventanas, cubriendo reinicios automáticos semanales.
Storage/backups/secretos conservan coste reservado. Comprobar coste y reserva antes
de nuevas sesiones. El presupuesto de 150 USD genera alertas, no un corte rígido.

## Rollback y recuperación

Rollback de código: volver a un digest compatible conocido sin bajar esquema ni
restaurar BD. Si una migración falla, impedir promoción y corregir hacia delante.
Nunca borrar evidencia ni degradar retención para corregir o reducir costes.

Recuperación de desastres (pendiente E5): suspender retiros, restaurar, invalidar
tokens anteriores al epoch, reconciliar WORM/manifiestos/proyecciones y reabrir
solo tras verificar ausencia de discrepancias. RTO 30 min es objetivo pendiente,
no una medición E0. No hay todavía comandos de recuperación del dominio.

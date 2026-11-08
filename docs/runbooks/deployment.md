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
   verifica índice OCI/manifest amd64, red ALB→tarea y ocho probes TLS. Evidencia:
   artefacto staging-deployment del workflow. No importar familias ni enviar avisos.
   Si la retirada programada dejó una descripción INACTIVE, recrea el servicio
   sintético con el digest aprobado y rearma su expiración. DRAINING o un estado
   desconocido bloquean la creación/actualización. Un fallo de lectura o permisos
   nunca demuestra que el servicio no existe. Contrastar el origen resultante con
   los callbacks de E1 antes de aceptar los flujos de identidad.
6. Si `e1_enabled=true`, ejecutar browser/cloud/staging-apk/archive-drill mediante
   `e1-checks.yml`. Todos deben aprobar; un fallo bloquea promoción. Consultar
   resultados y artefactos del commit en Actions, sin copiar reportes al repositorio.
7. Producción solo se habilita tras configuración/aceptación E5. No añadir una
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

Exige TLS 1.3/certificado/hostname, live/ready/capabilities, rutas de negocio/admin
ausentes, escrituras rechazadas y cabeceras seguras. Un fallo devuelve 1 y una
configuración inválida, 2. No sigue redirecciones ni registra cuerpos/cookies o
excepciones remotas. El reporte no acredita SHA/digest, IAM, presupuesto ni E1.
Un proxy TLS interceptante impide usar ese cliente como atestación TLS del origen;
los probes de aceptación se ejecutan desde runner sin ese proxy.

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

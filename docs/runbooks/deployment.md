# Publicación y recuperación: estado E0

## Estado real

AWS elegido: región `us-east-1`, perfil humano `aesir`, máximo TOTAL 150 USD
de créditos para desarrollo/despliegue. No equivale a 150 USD mensuales.
Cuenta no autenticada en este entorno. No se ha aprovisionado staging/producción.
No hay adaptador live de despliegue; el workflow CD se detiene explícitamente.

```bash
uv run python scripts/validate_deploy.py infra/environments/staging.json
uv run python scripts/validate_deploy.py infra/environments/production.json
```

Ambos deben salir con código 2 mientras falten destinos. Un archivo válido solo
acredita estructura; no prueba IAM, coste, TLS, recursos ni despliegue.

## Para conectar AWS sin saltarse controles

1. Completar login/toolkit y verificar identidad (`infra/aws/README.md`). Leer saldo,
   vencimiento de créditos y gastos reales; establecer alertas antes del aprovisionamiento.
2. Completar cuenta, dominio/DNS y destinos privados. Preparar IaC por entorno sin
   secretos en Git; verificar coste frente al saldo antes de crear recursos.
3. Crear identidades GitHub OIDC efímeras restringidas por repositorio, audiencia y
   rama/entorno; identidades separadas de migración y runtime. No dar esas
   credenciales a PR/forks. Probar la denegación de acceso no autorizado.
4. Implementar y probar el adaptador de despliegue contra esos recursos. Reemplazar
   la última barrera explícita de CD únicamente cuando existan pruebas reales.
   Construir una vez y promover el mismo digest, comprobar SHA contra CI, serializar
   migración/despliegue y descartar candidatos obsoletos bajo exclusión mutua.
5. Ejecutar migraciones expand/contract como tarea única con identidad propia.
   No migrar al iniciar cada réplica. Desplegar API/web/workers de la misma revisión.
6. Probar probes y funciones disponibles de la etapa con servicios reales de ensayo.
   Para habilitar negocio se requieren IdP/MFA, KMS/WORM y los controles E1–E5.
   Datos sintéticos siempre; no importar familias ni emitir invitaciones al publicar.
7. Promover automáticamente solo después de staging aprobado; ninguna aprobación
   humana rutinaria nueva. Mantener `cancel-in-progress: false` para migraciones/deploys.

Configurar el check `E0 CI / required` como obligatorio requiere permisos de
administración de GitHub. Esta sesión recibió HTTP 403 al leer protección de rama
y permisos de Actions; no puede afirmar que dicha protección esté configurada.

## Rollback y recuperación

Rollback de código: volver a un digest compatible conocido sin bajar esquema ni
restaurar BD. Si una migración falla, impedir promoción y corregir hacia delante.
Nunca borrar evidencia ni degradar retención para corregir o reducir costes.

Recuperación de desastres (pendiente E5): suspender retiros, restaurar, invalidar
tokens anteriores al epoch, reconciliar WORM/manifiestos/proyecciones y reabrir
solo tras verificar ausencia de discrepancias. RTO 30 min es objetivo pendiente,
no una medición E0. No hay todavía comandos de recuperación del dominio.

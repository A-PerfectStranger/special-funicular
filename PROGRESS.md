# Continuidad E2

Base remota inicial: `775b312`; rama `feat/e2-family-authorization`.
E0/E1 conservan su aceptación según PLAN.md. **E2 no está aceptada ni completa**.
Este archivo se mantiene por instrucción explícita del usuario; el alcance,
criterios y matriz de aceptación permanecen en PLAN.md, sin copiar reportes privados.

Implementación candidata: importador privado/esquema/hash/aprobación/promoción
atómica e idempotente; altas/bajas de personal/principal/políticas auditadas;
invitación 32 bytes/24 h y canje OIDC/PKCE/MFA con email verificado; API/móvil de
familia, cuidadores/fotos/recurrencias/revocación; migraciones con RLS y funciones
restringidas. OpenAPI y docs/runbooks/e2.md describen comandos y límites reales.

Comprobaciones locales finales: make check aprobado, 214 Python y 12 JS;
migración de todos los esquemas desde base PostgreSQL vacía y suite completa
aprobadas con roles separados; tipos/lint/Django/Expo/actionlint aprobados.
Cuatro regresiones Chromium del callback y bundle Android/Hermes aprobados.
Pillow 13.0.0; pip-audit/npm audit sin vulnerabilidades y gitleaks historial/árbol
sin secretos. Se corrigió un test E1 que fijaba el lector a la BD de desarrollo
en vez de PGDATABASE, descubierto al ensayar la migración limpia. Archivos de
trabajo en work/, excluidos de Git. CI, imagen/APK y AWS propios pendientes.

Ensayo preparado: e2-trial.yml, mismo grupo serializado y digest API/archivador,
gate E1/APK antes de E2, cohorte nueva en Secrets Manager y verificación WORM
independiente hasta event_sequence. Scripts nuevos con regresiones locales;
requieren todavía CI y ejecución real. CD habitual mantiene E2 apagada. La
habilitación continua de E2 queda pendiente hasta cerrar el ensayo y su gate.

El usuario eligió comandos revisables de CloudShell, sin enviar códigos de
verificación al chat. Tras integrar un candidato con CI aprobado: actualizar
stack E1 para scope email mediante commission_e1; provision_e2_fixtures con SHA
main y trial-id nuevo; ejecutar E2 synthetic trial con ci_run_id del mismo SHA.
Runbook E2 contiene comandos exactos y controles. No reusar invitaciones usadas,
no resetear subjects/semillas ni borrar eventos para repetir. Verificar origen
Cognito/API si Express recrea la URL. Un fallo bloquea aceptación.

Siguientes pasos: terminar checks locales/seguridad/migración limpia, publicar PR
con E2 desactivada, observar CI/imagen/APK; integrar solo tras checks requeridos,
verificar CD E1 y dar al operador el SHA y comandos de preparación concretos.
Después ejecutar ensayo real, corregir fallos, verificar criterios uno a uno y
actualizar estado. No marcar E2 como terminada por este checkpoint.

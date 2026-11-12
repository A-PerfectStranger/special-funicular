# Continuidad

[PLAN](PLAN.md) concentra aceptación; [README](README.md) y los runbooks contienen
comandos. E0–E3 están aceptadas con sintéticos. **E4, E5 y producción siguen
pendientes.** Solo dispositivos del equipo y datos sintéticos; la escuela real
requiere activación privada aprobada tras todos los gates.

## Código y verificación

Main: `561520f125c0035ec09d112f8712b6adcfb9a472`, con CI aprobado. Incluye E4
notificador Expo, registro propio de dispositivos, historial familiar, consulta
escolar aislada y correcciones técnicas por eventos vinculados. Migraciones:
pickup 0008–0009 y notification_worker 0001–0004, aditivas. `e4_enabled=false`,
`pickup_enabled=false` y `synthetic_only=true`; producción permanece bloqueada.

Rama de corrección: `feat/bounded-cloud-verification`. Verificación local:
461 Python con PostgreSQL/roles reales, tipos, lint y plantillas. Las pruebas
incluyen 1.427 eventos con firmas RSA-PSS, comparación secuencial/paralela,
concurrencia y cola acotadas, alteraciones, deadline y rechazo de cadenas
parciales; el proveedor/almacén local son SIMULATED. CI/CD del nuevo SHA y duración
AWS pendientes; no trasladar al nuevo candidato aceptaciones anteriores.

El verificador cloud usa cuatro lectores y hasta ocho trabajos pendientes;
conserva cada firma KMS, versión/retención/hash y reduce la cadena en orden.
Deadline interno 480 s y SDK acotado; publica progreso numérico y un informe de
fallo al vencer. El APK usa `staging/<SHA>/<SHA256_APK>/`, manifiesto con origen
y descarga contra ECS/ECR activos; conserva variantes sin sobrescribirlas.

## Estado AWS observado

Cuenta `028364485203`, `us-east-1`, techo USD 150, sin dominio propio. El operador
confirmó nuevamente todos los controles de gasto/crédito/reserva de comisión
sintética. No acredita coste ni custodia productiva. Inventario: 1.427 checkpoints;
no borrar, compactar ni reiniciar evidencia para acelerar la verificación.

CD [43088089855](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43088089855)
del main actual: imagen/migraciones y primera ejecución de staging/browser E1
aprobadas; APK privado publicado y leído con checksum. El verificador cloud
agotó diez minutos; E2/E3 no están aceptados para este candidato. Los reintentos
con otra pasarela quedaron cerrados en bootstrap por callback diferente. El
operador confirmó la sincronización exclusiva del WebClient existente al origen
`https://re-af9d1110292c4b379ea6b1076277426c.ecs.us-east-1.on.aws`.
Es una observación efímera: revisar ECS y el reporte del próximo despliegue antes
de usarla. El APK publicado incorpora la URL anterior; falta un APK vigente.

`retiro-staging-operations` está comisionado: bucket
`retiro-internal-mobile-028364485203-us-east-1`, rol
`retiro-staging-MobilePublisher`, tópico `retiro-staging-operations-alerts` con
suscripción confirmada y clave `7f98c09f-49db-48f2-b2bd-72463fd7fbbe` reutilizada,
bajo custodia del operador mediante ExistingOperationsKeyArn. Mantener recursos;
no repetir comisión/recuperación para continuar. La alarma debe probarse realmente.

Expo `43s1r/retiro-seguro`, proyecto `8d55d0cb-2d9f-4a73-bac3-6ad7cab1f04f`;
Firebase `retiro-seguro-2ab03`, Android `org.retiroseguro.staging`. Configuración
Firebase, paquete, callback y firma de desarrollo comprobados en el APK compilado.
El responsable confirmó FCM v1 y enhanced push security; access token en
`retiro-staging/e4/ExpoAccessToken`. Falta AllowedDeviceHashes tras registrar el
Android 13 del equipo. Nunca pedir tokens, TOTP, contraseñas o claves por chat.

## Siguiente trabajo

1. Verificar CI de la corrección; integrar solo con checks aprobados y sin
   recuperación/migración anterior pendiente. Iniciar CI/CD al final y terminar
   la conversación sin esperar ejecuciones largas. Verificar su resultado al volver.
2. Si cambia la pasarela, sincronizar únicamente el callback existente con el
   comando de [despliegue](docs/runbooks/deployment.md), desde main aprobado.
   Reintentar fallidos/dependientes dentro de la ventana, conservando digest y
   evidencia. No rehacer Cognito ni resetear cohortes. Comprobar todos los gates.
3. Obtener el manifiesto del APK vigente de Actions y descargar con operador:
   `private_mobile download --sha SHA --expected-sha256 CHECKSUM_DE_ACTIONS`.
   Transferir por canal privado y probar Android paso a paso según [E5](docs/runbooks/e5.md).
4. Registrar el equipo, obtener hashes auditados y completar allowlist, comisión
   del notificador y gate integrado E4. Solo entonces habilitar avisos. Faltan
   fallo/recuperación Expo, alarma, p95, recibo real y verificador externo final.
5. E5: recuperación integral de retiros/epoch/referencias, carga/RTO, retención
   aplicada, firma/distribución productivas, infraestructura y lote escolar. La
   política seleccionada en retention.json no está aplicada ni acredita RFS17.

## Entorno local

Contenedor `retiro-e4-db`, puerto 5433. Bases `retiro`, `retiro_e4_verify` y
`retiro_bounded_verify` conservadas. Esta última se creó aislada y migró desde cero
para la regresión actual: la base anterior acumuló más de 5.000 eventos y activó
el límite previsto del exportador sintético. Mantener ese control y todas las
bases; no limpiar evidencia ni cambiar .env para apuntar a cloud. Credenciales
locales sintéticas de infra/local; work/ contiene scratch, no aceptación AWS.

Chromium local funciona con el helper fijado; el navegador compartido falló al
iniciar. No confundir pruebas locales con acceso a consolas o teléfono físico.

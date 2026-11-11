# Continuidad

El estado de entregas y su evidencia aceptada están en [PLAN](PLAN.md); comandos
en [README](README.md) y operaciones en los runbooks. E0–E3 están aceptadas con
sintéticos. **E4 aún no está aceptada en AWS; E5 y producción siguen pendientes.**
No cargar datos reales ni activar retiros, invitaciones o avisos a familias reales.

## Candidato actual

Rama `feat/e4-e5-production`, basada en `origin/main` `cfe5dc7`. Implementa
notificador Expo, dispositivos por padre, historial mínimo, consultas escolares
con lector separado y correcciones/reintentos técnicos por eventos vinculados.
Migraciones nuevas: pickup 0008–0009 y notification_worker 0001–0004; no modificar
migraciones E1/E2/E3 ya desplegadas. `e4_enabled=false` en staging; los controles
productivos siguen bloqueando identidad/retiros/archivo sin comisión E5.

Verificación local: 415 Python con PostgreSQL real, 27 JavaScript, diez navegador,
portal Chromium, tipos/lint/bundle/migraciones y auditorías de dependencias. Los
adaptadores/recibos de estas pruebas son simulados. Consultar CI del nuevo commit;
no atribuirle los resultados de E3 ni afirmar imagen/APK/AWS aprobados sin sus jobs.
Chromium usa `scripts/install_ci_chromium.sh`, con descarga fijada y arranque/
interacción obligatorios sin APT. El candidato base `2d7d2ef` pasó ambos CI,
incluidos quality, imagen y APK. Los cambios posteriores de preparación operativa
requieren sus propios checks por SHA. Los runners Ubuntu 24.04 ya incluyen Skopeo;
su presencia se exige antes de federar, sin reinstalarlo mediante APT.
El helper de pruebas nativas cierra su servidor también si Chromium no arranca;
se comprueba el fallo negativo sin dejar la ejecución colgada.

Preparación operativa implementada: `e4-operations.yaml`,
`commission_e4_operations.py` y `private_mobile.py`. Stack separado para SNS,
clave y APK interno con OIDC MobilePublisher. Publicación condicional con lectura
posterior, descarga AWS autenticada y checksum independiente de Actions; sin APK público ni enlace
prefirmado. **Comisión AWS bloqueada por rollback de SNS.** Recuperarla antes de
integrar para que CD pueda entregar el APK configurado de staging.

CloudFormation `retiro-staging-operations`: `ROLLBACK_COMPLETE`. SNS rechazó
`sns:*` en la política del tópico; el candidato corregido usa acciones admitidas
explícitas y diagnóstico JSON por etapa/código. El inventario del operador
confirma la clave `7f98c09f-49db-48f2-b2bd-72463fd7fbbe` en `DELETE_SKIPPED`,
bucket sin identificador físico y recursos SNS eliminados. No asumir ausencia
física del bucket: el modo de recuperación la verifica antes de cualquier cambio.
Recuperar con `--recover-retained-key-id` y ese UUID. Se conserva la clave en
custodia del operador mediante `ExistingOperationsKeyArn`; solo se retira el
registro completamente revertido. La recuperación y la nueva suscripción aún
requieren verificación AWS; no declarar stack comisionado ni E4/E5 aceptadas.

## Decisiones y configuración externa

- AWS actual `028364485203`, región `us-east-1`, techo USD 150, URL administrada sin
  dominio propio. El operador confirmó el preflight de comisión sintética de presupuesto/créditos;
  no acredita cobertura de retención productiva ni comisión E4/E5. El inventario
  del operador no tiene SNS ni bucket interno ni AllowedDeviceHashes. El access
  token Expo está vigente y sin eliminación pendiente.
- Expo `43s1r/retiro-seguro`, proyecto `8d55d0cb-2d9f-4a73-bac3-6ad7cab1f04f`.
  Firebase `retiro-seguro-2ab03`; app Android `org.retiroseguro.staging` creada.
  Firma staging de desarrollo; no usarla como firma productiva.
- El responsable confirmó el identificador Android y FCM v1 con la cuenta
  `retiro-push` en Expo, y guardó `STAGING_GOOGLE_SERVICES_JSON` en GitHub. La carga
  se verificará en el build/ensayo real. También confirmó enhanced push security
  y el secreto `retiro-staging/e4/ExpoAccessToken` en Secrets Manager. Falta
  verificar su inyección/funcionamiento, la allowlist del equipo y el aviso/recibo
  en dispositivo.
- Android físico disponible, Android 13; objetivo: preparar activación escolar. Continuar paso
  a paso con el responsable, sin sustituir la prueba física por unitarias.
- Retención inicial delegada: política seleccionada en retention.json; aplicación,
  coste, denegaciones, ciclo automático y recuperación pendientes de E5.

## Trabajo siguiente

1. Verificar los checks del nuevo SHA. El responsable autorizó expresamente usar
   el mismo correo del presupuesto para SNS. Desde CloudShell ejecutar
   `commission_e4_operations --expected-sha SHA --use-budget-alert-email`
   con el modo de recuperación y UUID retenido descritos arriba,
   aceptar el correo de confirmación y revisar su JSON sin publicar la dirección.
2. Con el stack listo y checks aprobados, integrar y verificar CD por SHA.
   Descargar el APK con `private_mobile download`, transferirlo de forma privada
   al Android e iniciar el ensayo conjunto por instalación/login/registro.
   Obtener hashes auditados del equipo para AllowedDeviceHashes; no inventarlos.
3. Completar Expo/Firebase, comisión E4, bandera y ensayo integrado real según
   [E4](docs/runbooks/e4.md), incluidas alertas, fallos/reintentos y lector WORM.
   El gate automático E4 y su incorporación a promoción siguen pendientes; no
   habilitar producción ni declarar E4 terminada solo por la suite local.
4. Ejecutar [E5](docs/runbooks/e5.md): Android/personal, recuperación integral con
   epoch y referencias, carga/RTO, retención, firma/distribución, producción y lote.

## Invariantes operativas

Conservar cohortes de un solo uso, eventos, outbox, recibos y WORM; nunca limpiar
para reiniciar un ensayo. No hay que repetir commission_e1 ni reemplazar Cognito
por una recreación del gateway: comprobar origen/callback/SHA/digest y sincronizar
solo el callback existente cuando corresponda. El pool puede agotarse y debe
reponerse por operador, no resetearse.

La base original y su volumen no se alteraron para E4. Ensayos locales aislados:
contenedor `retiro-e4-db`, puerto 5433, bases `retiro` y `retiro_e4_verify`;
credenciales sintéticas según infra/local. La segunda se migró desde cero y pasó
la regresión. No cambiar .env para apuntar al staging ni aplicar refresh SQL de
work/ a entornos compartidos. Scratch, capturas y claves públicas de desarrollo
en work/ son prescindibles; no contienen evidencia de aceptación AWS.

El navegador compartido falló al iniciar con «the gaas-browser node_repl sandbox
cannot be disabled». La automatización Chromium local sí funciona; no confundir
esa verificación con acceso a las consolas del usuario. No pedir claves, TOTP,
contraseñas ni JSON de cuenta de servicio por chat.

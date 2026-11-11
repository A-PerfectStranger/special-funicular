# Continuidad

El estado de entregas y su evidencia aceptada están en [PLAN](PLAN.md); comandos
en [README](README.md) y operaciones en los runbooks. E0–E3 están aceptadas con
sintéticos. **E4 aún no está aceptada en AWS; E5 y producción siguen pendientes.**
No cargar datos reales ni activar retiros, invitaciones o avisos a familias reales.

## Candidato actual

Código del incremento integrado en main mediante PR #32:
`4db76539ab6e46d2847bdce5360e13bd2cbcc038`, basado en el candidato aprobado
`3ccf3f6`. Su CI de main está aprobado; CD y publicación del APK siguen
pendientes de aceptación. Implementa
notificador Expo, dispositivos por padre, historial mínimo, consultas escolares
con lector separado y correcciones/reintentos técnicos por eventos vinculados.
Migraciones nuevas: pickup 0008–0009 y notification_worker 0001–0004; no modificar
migraciones E1/E2/E3 ya desplegadas. `e4_enabled=false` en staging; los controles
productivos siguen bloqueando identidad/retiros/archivo sin comisión E5.

Verificación local: 423 Python con PostgreSQL real, 27 JavaScript, diez navegador,
portal Chromium, tipos/lint/bundle/migraciones y auditorías de dependencias. Los
adaptadores/recibos de estas pruebas son simulados. Consultar CI del nuevo commit;
no atribuirle los resultados de E3 ni afirmar imagen/APK/AWS aprobados sin sus jobs.
Chromium usa `scripts/install_ci_chromium.sh`, con descarga fijada y arranque/
interacción obligatorios sin APT. El candidato `3ccf3f6` pasó ambos CI,
incluidos quality, imagen y APK de desarrollo. El SHA integrado y el APK
configurado de staging requieren sus propios checks/CD. Los runners Ubuntu 24.04 ya incluyen Skopeo;
su presencia se exige antes de federar, sin reinstalarlo mediante APT.
El helper de pruebas nativas cierra su servidor también si Chromium no arranca;
se comprueba el fallo negativo sin dejar la ejecución colgada.

Preparación operativa implementada: `e4-operations.yaml`,
`commission_e4_operations.py` y `private_mobile.py`. Stack separado para SNS,
clave y APK interno con OIDC MobilePublisher. Publicación condicional con lectura
posterior, descarga AWS autenticada y checksum independiente de Actions; sin APK público ni enlace
prefirmado. **El operador confirmó la comisión del stack `retiro-staging-operations`
con fuente `3ccf3f69d566fb20d5ee093cc5ecbc4ed77db8e1`.** Presupuesto/créditos:
todos los controles aprobados. Suscripción SNS confirmada y clave retenida
reutilizada; no repetir la recuperación ni crear otra clave.

Recursos comisionados: bucket `retiro-internal-mobile-028364485203-us-east-1`,
rol `retiro-staging-MobilePublisher`, tópico `retiro-staging-operations-alerts`
y clave `7f98c09f-49db-48f2-b2bd-72463fd7fbbe`. La clave permanece bajo custodia
del operador mediante `ExistingOperationsKeyArn`. El JSON confirma
`apk_published=false`, `e4_accepted=false` y `e5_accepted=false`: publicar/leer/
descargar el APK, probar la alarma y completar los ensayos siguen pendientes.
La comisión del notificador `retiro-staging-e4` es otra operación; falta la
allowlist del equipo y el gate integrado E4 antes de habilitarlo.

CD vigente: [43064147478](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43064147478),
del SHA integrado anterior. Imagen, migraciones y staging aprobados. Digest
`sha256:404aaf338a4b1db73fa2fe46f451d6a5b8d9ceb1fe67ddc88d724b2b6a49ddd9`.
Browser y verificación cloud E1 aprobados; archivo/recuperación y E2/E3 necesitan
sus resultados completos. El operador confirmó la sincronización limitada al
callback del WebClient existente para el origen observado
`https://re-ce5a11fd975b4c8f9a0063c8dc78cc33.ecs.us-east-1.on.aws`.
Callback comprobado y recursos persistentes conservados. Ese hostname es efímero: usar el nuevo reporte si
la pasarela vuelve a retirarse; no asumir vigente esta URL por estar documentada.

El APK de staging del SHA integrado compiló y pasó inspección de Firebase,
paquete, origen/callback y firma de desarrollo. La publicación falló antes de
escribir objetos: el validador confundía la propiedad de CloudFormation con
`ApplyServerSideEncryptionByDefault` de S3. El diagnóstico del operador confirma
KMS esperado y prefijo vacío. La corrección en `feat/private-apk-sdk-response`
usa el campo API y respuestas comprobadas por el modelo botocore; mantiene los
controles de destino, cifrado, versionado, política privada y checksum.
El CLI informa errores mediante códigos seguros y operación AWS, sin mensajes
remotos. La corrección requiere sus propios CI, integración y publicación;
no repetir el publicador antiguo ni declarar distribuido el APK compilado.

## Decisiones y configuración externa

- AWS actual `028364485203`, región `us-east-1`, techo USD 150, URL administrada sin
  dominio propio. El operador confirmó el preflight de comisión sintética de presupuesto/créditos;
  no acredita cobertura de retención productiva ni aceptación E4/E5. SNS y el
  bucket interno están comisionados; falta AllowedDeviceHashes. El access
  token Expo está vigente y sin eliminación pendiente.
- Expo `43s1r/retiro-seguro`, proyecto `8d55d0cb-2d9f-4a73-bac3-6ad7cab1f04f`.
  Firebase `retiro-seguro-2ab03`; app Android `org.retiroseguro.staging` creada.
  Firma staging de desarrollo; no usarla como firma productiva.
- El responsable confirmó el identificador Android y FCM v1 con la cuenta
  `retiro-push` en Expo, y guardó `STAGING_GOOGLE_SERVICES_JSON` en GitHub. La
  configuración Firebase quedó comprobada en el APK compilado de staging;
  falta probar Expo/FCM en el teléfono. También confirmó enhanced push security
  y el secreto `retiro-staging/e4/ExpoAccessToken` en Secrets Manager. Falta
  verificar su inyección/funcionamiento, la allowlist del equipo y el aviso/recibo
  en dispositivo.
- Android físico disponible, Android 13; objetivo: preparar activación escolar. Continuar paso
  a paso con el responsable, sin sustituir la prueba física por unitarias.
- Retención inicial delegada: política seleccionada en retention.json; aplicación,
  coste, denegaciones, ciclo automático y recuperación pendientes de E5.

## Trabajo siguiente

1. Verificar los checks de la corrección del SDK. Antes de integrar, comprobar
   que termine el CD actual y que su archivador quede recuperado. Integrar solo
   con checks aprobados y observar CI/CD del nuevo SHA. Conservar el resultado
   de los gates anteriores; no cancelar recuperación ni reiniciar cohortes.
2. Tras CD y custodia privada verificados, descargar el APK con `private_mobile
   download --sha SHA_DESPLEGADO --expected-sha256 CHECKSUM_DE_ACTIONS`, transferirlo de forma privada
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

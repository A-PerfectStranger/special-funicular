# Continuidad E2

E2 NO está cerrada. El backend pasó el ensayo AWS 74297b3, pero el CD habitual
de 855fc2e falló en el gate E1 del guardia; E2 no se ejecutó en ese CD. Este archivo conserva el relevo pedido
por el usuario. PLAN.md contiene criterios/fases, README/runbooks los comandos
y Actions los reportes por commit. No copiar reportes ni secretos al repositorio.

## Estado actual

- Main: `855fc2ec774d6204306370f103eb133d459f2c72`, PR #19 integrada.
  CI main 42534840490 aprobado completo, imagen y APK/firma incluidos.
  CD automático 42535508616 finalizado con fallo E1 guardia; E2 omitido.
- Head integrado ab0fc2d: CI push 42532020326 y PR 42532025015 aprobados,
  234 Python/20 JS, tipos/contrato/migraciones, seguridad, imagen y APK/firma.
  Bundle Android/Hermes local aprobado.
- Ensayo E2 [42529491296](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42529491296)
  aprobado completo sobre `74297b397b992287272fc63745d4ccb9127e2ea6`:
  publicación/preparación/migración/trial, E1 browser/cloud/archive-drill/APK,
  bulk concurrente entre escuelas, activación/contacto/replay Cognito/MFA,
  permisos, idempotencia, cuidadores/versiones/revocación, recurrencia/horarios,
  principal/restricciones y baja online. Protocolo exige secuencia 489; WORM
  independiente verificó 490 eventos sin SQL. Cohorte consumida:
  `85885f69-3c08-581f-adb0-a297198314e2`.
- Digest funcional 74297b3:
  `sha256:7af058a44389aecf2851718d9f976ae96c374ff03006fc868c537f6afd892df2`.
  Runtime/digest y E1/E2=true contrastados. No atribuir ese digest a 855fc2e.
- Operador confirmó pool de cuatro cohortes MFA nuevas para 74297b3. Las
  restantes son independientes del release; CI no escribe vault ni crea IdP.
  No pedir códigos/semillas/contraseñas ni repetir commission_e1 ya confirmada.
- Decisión explícita: cada familia pertenece a una sola escuela. Migración 0005
  serializa UUID de padres en orden global, revalida contacto/escuela bajo lock
  y contrasta bytes almacenados contra aprobación. No editar 0002–0005 aplicadas.

## Cambio integrado en 855fc2e

`e2_enabled=true` en staging exige E1 → E2 → WORM antes de considerar producción.
Solo datos sintéticos y `pickup_enabled=false`; producción sigue NOT_CONFIGURED
por E5, cuyo fallo explícito esperado no acredita despliegue productivo.
Cohortes usadas se detectan por filas durables y se saltan; agotamiento o fallo
real bloquea. Nunca reiniciar invitaciones, subjects, cuentas ni evidencia.

Se corrigió el desmontaje del formulario al abrir galería: retención solo en
memoria bajo máscara sin interacción/accesibilidad durante el picker; retorno
con check online. Segundo plano ordinario, logout/rechazo descartan la vista;
generaciones impiden restauración tardía y carrera con OIDC. Seis regresiones
nuevas y APK aprobados en PR. Teléfono/cámara Android físico siguen en E5.

## Siguientes pasos

1. CI main 42534840490 aprobado; CD 42535508616 en curso. Mantener main sin
   cambios durante sus migraciones/archive-drill. No cancelar migraciones.
2. Exigir staging, todos los jobs E1/APK y `e2-acceptance / family` aprobados con
   otra cohorte del pool. Verificar SHA/digest, min_sequence/high-water y que el
   skip de la cohorte consumida no oculte errores de infraestructura/validación.
3. Solo tras aprobar, cerrar matriz/casillas E2 en PLAN y actualizar este archivo
   con SHA/runs reales. Rama local `feat/e2-final-state`: preparación documental,
   aún sin integrar. PR/checks antes de main, después de terminar el CD actual.
4. El cierre documental dispara otro CD: quedan cohortes para comprobarlo;
   no crear un bucle de commits solo para actualizar el último resultado.
   La aceptación se acredita por SHA funcional y Actions, no se hereda a releases.
5. E3–E5 pendientes: QR/retiro, avisos, validación física y producción deshabilitados.

El CD previo 42529252429 aprobó staging y E1/APK sobre 74297b3; archive_recovered
true y high-water 398 sin SQL. Solo producción falló por NOT_CONFIGURED E5. El
ensayo E2 posterior sí aprobó completo. Scratch/reportes locales en work/, ignorados.

CD 42535508616 de 855fc2e: publicación/preparación/migración/staging y APK
configurado aprobados. Digest verificado en ejecución:
sha256:9b1cc768975aab2e903f392533c6dc9306b805ce409149f0cf4fbf8a6b66223c.
Artefacto 13639228793 confirma SHA 855fc2e, E1=true y E2=true. Browser E1
sigue en curso; faltan cloud/archive-drill y E2 con otra cohorte. No marcar E2.

BLOQUEO REAL: CD 42535508616 falló en browser E1, caso
mobile_guard_mfa_pkce_reauth_refresh_logout. Reporte artefacto 13639583872:
school_three_protected_logins y padre aprobados; guardia false, fase
fixture_status_restore, último HTTP 200. Esa fase NO identifica todavía la
causa: mobile() ejecuta fixtureStatus restore en finally y sobrescribe phase
incluso si falló antes. Restore-all posterior PASS (identidad/roster conservados).
No atribuir a código de negocio ni a infraestructura sin evidencia. No cerrar
E2; la cohorte siguiente no se consumió porque gate E1 bloqueó E2. Se investiga
ECS (exit/status/duración) y se corregirá diagnóstico para conservar primera
fase de fallo; no relajar aserción de access fresco <240000ms ni MFA/revocación.

Corrección diagnóstica local: tests/staging/recovery.mjs conserva el error y la
primera fase antes de ejecutar restauración; reporta por separado si restaurar
también falla. e1-browser.mjs registra fase precisa de frescura tras revoke y
restore, access_age_ms y estado HTTP de refresh. NO cambia aserciones ni límites.
Siete regresiones staging (4 Chromium + 3 recuperación) aprobadas y añadidas al
CI; actionlint/sintaxis aprobados. Nuevo CI del head aún pendiente.

Pregunta de operador pendiente: diagnóstico solo lectura de ECS en CloudShell,
list/describe de tareas y definiciones, filtrado a E1_FIXTURE_CONTROL. Salida
solo action/targets sintéticos/stop_code/exit_codes/duraciones, sin secretos ni
logs. Permite separar fallo de arranque ECS de ventana de access agotada. No
asumir causa; no repetir promoción/identidades ni relajar el umbral 240000ms.
El CD fallido ya terminó y restore-all PASS; no hay archive-drill activo.

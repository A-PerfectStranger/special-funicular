# Continuidad E2

**E2 no está aceptada ni completa.** El candidato está integrado por PR #16:
https://github.com/A-PerfectStranger/special-funicular/pull/16
Main actual: `3085e3698ba15984b68450afb4972618869a775a` (PR #17 integrada).
Base E2 previa: a435750 (PR #16).
Rama local de continuación: `feat/e2-live-acceptance`.
E0/E1 conservan la aceptación de PLAN.md; E2 y retiros siguen apagados en CD normal.
Este archivo se conserva por instrucción explícita del usuario. Criterios y matriz
en PLAN.md; procedimientos en docs/runbooks/e2.md; reportes privados fuera de Git.

## Implementación y comprobaciones acreditadas

Importación privada/esquema/hash/aprobación/promoción atómica e idempotente;
provisioning/baja/principal/políticas auditados; invitación 32 bytes/24 h y canje
OIDC/PKCE/MFA con email firmado/verificado; API/móvil familiar, cuidadores/fotos,
recurrencias/revocación; RLS y comandos SQL restringidos. OpenAPI y runbook actualizados.

Código revisado `ea478376c27fb18beefe6f07189e31c4490c3688`: CI push 42520729966 y PR
42520734551 aprobados completos (calidad, imagen/smoke readonly no root, APK/firma,
required). `make check` local: 216 Python/12 JS. Migración desde PostgreSQL vacío y
suite de 214 pruebas previa a los últimos controles aprobadas; CI final repitió
migraciones/suite completas desde su PostgreSQL nuevo. Cuatro regresiones Chromium,
bundle Android/Hermes, actionlint, pip-audit/npm y gitleaks aprobados. Pillow 13.0.0.
Controles finales: zona IANA válida, hash del comando anclado al evento, vigencia
real del access token revalidada después de esperar el lock del estudiante.

El CI main `42521482367` aprobó todos los checks del merge a435750. CD
`42522245360` está en curso al registrar este punto. No atribuir estos resultados
a la corrección posterior ni a la aceptación funcional E2. El CD previo `42517864495`
(main 775b312) aprobó staging y todos los jobs E1; su fallo es producción E5
bloqueada, no una regresión de staging. No heredar ese resultado al candidato E2.

## Endurecimiento integrado (PR #17)

https://github.com/A-PerfectStranger/special-funicular/pull/17

La continuación conserva el email firmado exacto; migración hacia delante
`authorization.0003` compara literalmente con la precarga. Invitación filtrada +
buzón con capitalización distinta: rechazado sin consumo; contacto exacto: aprobado.
`0004` compara UUID por su valor, evitando que dos padres/contactos distintos se
fusionen por representar el mismo UUID con capitalización diferente. El lote
incorrecto se rechaza completo, sin activar ninguno de los estudiantes.
El móvil limita la limpieza de fotos a copias temporales dentro de su caché;
no borra el archivo original de galería ni rutas externas/traversal/encoded.

Checks locales del contenido final: 218 Python y 14 JS, seguridad, actionlint y
bundle Android/Hermes aprobados. CI push 42522421334 y PR 42522425557 de 0ad8bcd aprobados completos, incluidos
imagen y APK. Integrado en 3085e36. CI main 42523200830 en curso; ese será el
ci_run_id del ensayo E2 si aprueba y main no avanza. No atribuir los resultados
de PR ni de a435750 al nuevo merge. E2 permanece apagada.

## Pendientes y relevo operativo

El usuario eligió comandos revisables de CloudShell en lugar de compartir códigos
de verificación. Se entregó un bloque para checkout limpio de a435750, instalación
hash-pinned del SDK operativo, `commission_e1 --web-origin` con el origen del JSON y
`provision_e2_fixtures --sha a435750... --trial-id UUID_NUEVO --synthetic-only`.
El primer intento se detuvo antes de AWS: estaba en ~, fuera de un repositorio
Git. Se entregó un segundo bloque que clona a un directorio temporal nuevo, fija
a435750 e invoca solo commission_e1. Se espera su resultado saneado; la preparación
de cuentas queda aplazada hasta integrar PR #17. No se recibieron ni solicitaron secretos por chat.
La comisión añade scope email sin cambiar IAM/retención/claves. Las dos cuentas
nuevas usan contactos synthetic.invalid, mensajes suprimidos y TOTP en Secrets Manager.
El operador confirmó después la ejecución completa de commission_e1 sobre
 a435750: identity, billing preflight, CloudFormation y bootstrap privado, con
 `E1 resources and SQL roles commissioned. E1 ACCEPTANCE PENDING.` Esto acredita
 comisión; no reabre ni sustituye la aceptación E1 histórica ni acredita E2.
 El aviso pip sobre aws-sam-cli no detuvo la instalación --target y no se actualizó
 SAM. No se han preparado cuentas E2 en estos bloques; esperar SHA final tras PR #17.
 No se ha ejecutado ni aceptado E2 real todavía.

Siguiente orden:

1. Verificar CI main y CD del merge; E2 permanece false en despliegue normal.
2. Confirmar comisión/MFA del operador. Ante error, diagnosticar antes de repetir;
   no resetear subjects/semillas ni borrar eventos. No usar credenciales CI como operador.
3. Lanzar `e2-trial.yml` en main con ci_run_id 42523200830 solo tras CI aprobado
   y comprobar que main sigue en 3085e36. El usuario confirmó las dos identidades
   sintéticas/MFA preparadas por provision_e2_fixtures para ese SHA (sin secretos
   compartidos). Comisión y cuentas preparadas; aceptación real aún pendiente. Serializa con CD, mismo digest
   API/archivador, primero gate E1/APK, luego lote/activación/roles/cambios familiares
   y principal/políticas; E1Verifier verifica hasta event_sequence de la última mutación.
4. Corregir cualquier fallo y repetir con cohorte nueva (invites usadas no se
   reinician). Registrar resultados por SHA/entorno y cerrar cada criterio de PLAN.
5. Completar gate E2 continuo/cohortes repetibles antes de habilitar E2 en CD normal.
   No declarar E2 completa por este candidato o por mocks. Teléfono/producción E5.

Archivos temporales y resultados locales en work/, fuera de Git. Este checkpoint
se actualiza en la rama de continuación; revisar git status antes de integrar
cualquier corrección. No confundir una aprobación técnica con un recibo WORM.

Actualización: staging del CD a435750 (42522245360) aprobó publicación, migración,
API/archivador/digest y probes; sus suites E1 están en curso. No es aceptación E2.

## Decisión y cierre de concurrencia bulk

El usuario confirmó: una familia pertenece a una sola escuela en esta fase.
El importador ya rechaza reutilización de un padre de otra escuela en ejecución
secuencial. La revisión encontró una carrera pendiente: dos promociones nuevas
de escuelas distintas pueden validar el mismo Parent UUID todavía inexistente y
ON CONFLICT ignoraría el segundo enrollment. Implementada localmente migración hacia delante 0005: locks globales ordenados
por Parent UUID, revalidación de contacto/escuela bajo lock tras insertar/reutilizar
enrollment y hash de bytes almacenados contrastado con la aprobación. La regresión
real retiene escrituras de Parent y enfrenta dos escuelas con orden inverso de
padres: exactamente una promueve. También se rechazan reutilización secuencial
entre escuelas y payload adulterado tras aprobación. make check: 221 Python/14 JS;
seguridad aprobada. Falta CI/integración/AWS propios de 0005.
No aceptar E2 final con 3085 hasta cerrar este caso y el gate continuo.

Ensayo inicial 3085: workflow E2 42524078114 lanzado con CI main 42523200830
aprobado y fixture MFA confirmado por usuario. Ya ejecuta el trial: publish/prepare/migrate aprobados; despliegue E2 en curso.
CD automático 3085 42523948407 fue cancelado pendiente por esa cola, no durante
migraciones. El CD a435750 42522245360 continúa su gate E1. No cancelar migraciones.

El CD a435750 falló en archive-drill al haber avanzado main a 3085e36. El control
pause exige latest main antes de guardar STATE/detener worker; el reporte no llegó
a guardar estado de pausa. No interpretar ese gate obsoleto como aceptación de
archivo, ni como fallo de la comisión del operador. No integrar una nueva main
mientras el ensayo inicial 3085 necesite su guard de latest main en archive-drill.
Después del ensayo inicial todavía hay que integrar/verificar 0005 y completar
el gate E2 continuo con cohortes frescas/repetibles, sin resetear invitaciones
usadas ni ampliar IAM innecesariamente. No declarar E2 completa antes de ello.

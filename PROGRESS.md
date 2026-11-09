# Continuidad E2

**E2 sigue pendiente de cierre.** Este archivo conserva el relevo solicitado por
el usuario; PLAN contiene criterios/fases y Actions los reportes por SHA. No
copiar reportes ni secretos al repositorio.

## Base y evidencia acreditadas

- Main: `5817ef793948209a53dece79d67d15481adc359c`, PR #20 integrada.
  CI main 42539650941 aprobado completo. CD automático 42540357530 falló en migrate; no desplegó este SHA.
  Head e6ca30d: CI push 42538829097 y PR
  42538833463 aprobados completos, 243 Python/20 JS + siete staging, imagen/APK/firma.
  Base 855fc2e/PR #19 tuvo CI main 42534840490 aprobado completo.
- Backend E2: ensayo [42529491296](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42529491296)
  aprobado completo sobre 74297b3: migración, digest, E1/APK, carrera bulk entre
  escuelas, contacto/activación/replay Cognito/MFA, capacidades, cuidadores,
  idempotencia/versiones/revocación, recurrencia/horarios, principal y baja online.
  Secuencia requerida 489; WORM independiente verificó 490 eventos sin SQL.
- Una familia pertenece a una sola escuela, decisión explícita del usuario.
  Migración 0005 serializa UUID de padres y revalida escuela/contacto/hash bajo
  lock. 0002–0005 ya están aplicadas: no editar ni recrear funciones antiguas.
- Pool de cuatro cohortes MFA preparado y confirmado por operador. Solo se usó
  `85885f69-3c08-581f-adb0-a297198314e2`; quedan tres nuevas. No repetir comisión,
  no pedir códigos/semillas/contraseñas ni resetear subjects, canjes o evidencia.
- Staging configura E1/E2=true, synthetic_only=true, pickup_enabled=false.
  Producción sigue NOT_CONFIGURED por E5; no hay mensajes ni uso con datos reales.

## Fallo del CD habitual, causa ya clasificada

CD [42535508616](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42535508616)
de 855fc2e aprobó publicación, preparación, migración, staging/APK y WORM E1,
pero falló el browser E1 del guardia. E2, archive-drill y producción se omitieron.
Digest runtime verificado:
`sha256:9b1cc768975aab2e903f392533c6dc9306b805ce409149f0cf4fbf8a6b66223c`.

El operador entregó metadatos ECS saneados: revoke de e1-b-guard terminó con
TaskFailedToStart, sin startedAt ni exitCode y 72 s desde creación. No se ejecutó
el contenedor/SQL. Restore del guardia y restore-all finalizaron con código 0;
identidades y roster se conservaron. No atribuirlo a fallo de revocación de la
aplicación ni inventar causa interna AWS (red/capacidad/etc.).

El driver además sobrescribía la fase original al restaurar en finally. Se
corrige para conservar la primera fase/error, registrar recuperación fallida
separadamente y medir access_age_ms. Se mantienen todas las aserciones, access
fresco <240000ms, MFA, revocación y restauración obligatoria.

## Corrección integrada en PR #20

https://github.com/A-PerfectStranger/special-funicular/pull/20
Continuación local actual: `feat/e2-migration-diagnostics`.

`fixture_task.py` permite un único reintento (máximo dos tareas) SOLO si ECS
reporta TaskFailedToStart, sin startedAt, sin exitCode y sin contenedor RUNNING.
Reutiliza definición, red e inputs fijos; no añade permisos ni secretos. No
reintenta ejecución incierta, errores SQL, cohortes usadas (42), errores de
creación ni validación. La segunda falla sigue bloqueando. E1 y E2 usan el mismo
control de arranque. Nada de esto altera lógica de negocio o datos históricos.

La corrección de galería ya integrada en 855fc2e conserva formulario solo en
memoria y bajo máscara durante picker; exige check online al volver. Segundo
plano ordinario, logout/rechazo descartan la vista y checks tardíos no la restauran.
Seis regresiones móviles aprobadas en PR #19. Prueba física Android queda en E5.

## Validación y próximos pasos

Head e6ca30d y validación local aprobados: 243 Python/20 JS, tipos/contrato/
migraciones y Expo, más siete staging (4 Chromium + 3 recuperación). Las nueve
regresiones nuevas verifican retry seguro, límite de dos y no retry de SQL/42/
ejecución incierta. Falta CI/CD del merge 5817ef7; no heredar los checks del PR.

1. CI main 42539650941 aprobado; CD automático 42540357530 falló en migrate.
   Antes de reintentar, confirmar metadatos ECS solicitados al operador.
   No avanzar main durante migraciones/archive-drill ni cancelar migraciones.
2. Exigir staging, E1/APK y e2-acceptance/family aprobados con otra cohorte.
   Contrastar SHA/digest, trial distinto, minimum_sequence/high-water externo.
   Si falla, diagnosticar; no relajar controles ni resetear historia.
3. Solo entonces completar casillas/matriz E2 y cierre documental por PR/checks.
   El cierre documental dispara CD; quedan cohortes para verificarlo, sin crear
   bucle de commits solo para actualizar el último resultado. Aceptación por SHA.
4. E3–E5 pendientes: QR/retiro, avisos, Android físico y producción deshabilitados.

Scratch y reportes locales bajo work/, ignorados; evidencias/anclas privadas
fuera de Git. No ejecutar scripts antiguos de refresh de funciones en work/.

BLOQUEO ACTUAL: CD 42540357530 de 5817ef7 aprobó publish/prepare pero falló
en migrate (job 128913916031), 74 s después de iniciar el paso, con
Migration failed; deployment prohibited. No se desplegó 5817ef7 ni se ejecutaron
E1/E2; ninguna cohorte nueva consumida. El log no incluye startedAt/exitCode/
stopCode, por lo que NO se asume ausencia de SQL. Se pidió al operador un
diagnóstico ECS de solo lectura para retiro-staging-migrate: estado, inicio,
exit_codes, categoría de causa y subredes; sin secretos ni logs. No reintentar
una migración ejecutada o incierta. API última verificada sigue en 855fc2e.

Diagnóstico candidato de migración: scripts/task_diagnostics.py limita salida
a stop_code, started, exit_codes y reason_type de lista fija. No incluye razones
crudas, env, task ARN ni logs. deploy_staging.py imprime esa proyección tras
DescribeTasks, sin cambiar ejecución ni reintentos de migración. Dos regresiones
de privacidad/clasificación y mypy aprobados. make check final: 245 Python/20 JS
aprobados; siete staging previos sin cambios. CI del nuevo head pendiente.
Mantener PR en draft y no integrar/activar otro CD de migración hasta conocer
si el contenedor de la tarea anterior llegó a ejecutar el comando.

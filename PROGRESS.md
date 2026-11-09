# Continuidad E2

**E2 sigue pendiente de cierre.** Este archivo conserva el relevo solicitado por
el usuario; PLAN contiene criterios/fases y Actions los reportes por SHA. No
copiar reportes ni secretos al repositorio.

## Base y evidencia acreditadas

- Main: `855fc2ec774d6204306370f103eb133d459f2c72`, PR #19 integrada.
  CI main 42534840490 aprobado completo, 234 Python/20 JS, imagen y APK/firma.
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

## Corrección candidata en PR #20

Rama `feat/e2-final-state`, https://github.com/A-PerfectStranger/special-funicular/pull/20

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

El head anterior bba998c solo corregía diagnóstico y tuvo CI de push aprobado;
no atribuirlo al reintento añadido después. make check local final aprobado:
243 Python/20 JS, tipos/contrato/migraciones y dependencias Expo. Falta CI final
del nuevo head. Siete pruebas staging (4 Chromium + 3 de
recuperación), sintaxis y actionlint aprobados; pruebas de arranque cubren
reintento seguro, límite de dos y no retry de SQL/42/ejecución incierta.

1. make check aprobado; terminar CI final de PR #20 y actualizar descripción con el
   SHA real y resultados. CD anterior terminó, restore-all PASS, sin drill activo.
2. Integrar corrección con checks aprobados; esperar CI main y CD automático.
   No avanzar main durante migraciones/archive-drill ni cancelar migraciones.
3. Exigir staging, E1/APK y e2-acceptance/family aprobados con otra cohorte.
   Contrastar SHA/digest, trial distinto, minimum_sequence/high-water externo.
   Si falla, diagnosticar; no relajar controles ni resetear historia.
4. Solo entonces completar casillas/matriz E2 y cierre documental por PR/checks.
   El cierre documental dispara CD; quedan cohortes para verificarlo, sin crear
   bucle de commits solo para actualizar el último resultado. Aceptación por SHA.
5. E3–E5 pendientes: QR/retiro, avisos, Android físico y producción deshabilitados.

Scratch y reportes locales bajo work/, ignorados; evidencias/anclas privadas
fuera de Git. No ejecutar scripts antiguos de refresh de funciones en work/.

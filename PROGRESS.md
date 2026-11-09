# Continuidad E2

**E2 sigue pendiente de cierre.** Archivo conservado por instrucción explícita
del usuario. PLAN define criterios/fases; Actions conserva resultados por SHA.
No copiar reportes privados ni secretos al repositorio.

## Evidencia acreditada y estado de despliegue

- Main `5817ef793948209a53dece79d67d15481adc359c`, PR #20 integrada.
  CI 42539650941 aprobado completo (243 Python/20 JS + siete staging,
  seguridad, imagen/APK/firma). No se desplegó este SHA por el fallo siguiente.
- CD 42540357530: publish/prepare aprobados; migrate falló y prohibió desplegar.
  El operador confirmó TaskFailedToStart + CannotPullContainerError,
  started=false y exit_codes=[null], en subnet-06e503d053c50cbbe. El contenedor
  no arrancó ni ejecutó SQL; no se infiere una causa interna de ECR/red/capacidad.
- Última API verificada: 855fc2e, digest
  sha256:9b1cc768975aab2e903f392533c6dc9306b805ce409149f0cf4fbf8a6b66223c,
  E1/E2=true, synthetic_only=true, pickup_enabled=false.
- Ensayo funcional backend E2 [42529491296](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42529491296)
  aprobado completo sobre 74297b3: migración/digest, E1/APK, bulk concurrente,
  activación/contacto/replay Cognito/MFA, permisos, cuidadores/idempotencia/
  versiones/revocación, recurrencia/horarios, principal/restricciones y baja.
  Mínimo requerido 489; WORM independiente verificó 490 eventos sin SQL.
- Solo una de cuatro cohortes preparada por operador se consumió:
  85885f69-3c08-581f-adb0-a297198314e2. Quedan tres nuevas; no repetir comisión,
  pedir credenciales/códigos ni resetear subjects, invitaciones o evidencia.
- Decisión del usuario: una familia pertenece a una escuela. Migraciones
  0002–0005 ya aplicadas; no editarlas ni ejecutar scripts viejos de refresh.
- E3–E5, mensajes reales, retiro físico y producción siguen deshabilitados.

## Causas y corrección candidata PR #21

CD anterior 42535508616 de 855fc2e falló en E1 guardia: operador probó que revoke
terminó TaskFailedToStart sin startedAt/exitCode; no corrió SQL. Restore y
restore-all terminaron 0. PR #20 integró retry exclusivo de no arranque para
fixtures y preservación de primera fase/error antes de restaurar, con edad de
access y fallo de recuperación separado. No se relajan <240000ms, MFA ni revocación.

PR #21: https://github.com/A-PerfectStranger/special-funicular/pull/21
Rama `feat/e2-migration-diagnostics`. Se extiende el mismo control conservador
a la migración aislada tras confirmar que su tarea no arrancó. El módulo común
`isolated_task.py` permite un solo reintento, reutilizando definición/red/inputs,
solo si TaskFailedToStart y no hay startedAt, exitCode ni contenedor RUNNING.
No reintenta SQL, ejecución incierta, error de creación ni cohorte usada (42).
Si el segundo intento falla, el gate sigue bloqueado. El comando migrate_locked
y sus locks/transacciones permanecen iguales. Sin permisos adicionales.

`task_diagnostics.py` publica solo stop_code, started, exit_codes y reason_type
de lista fija. Nunca razones crudas, env, task ARN ni logs. El control común
registra cada intento y deploy muestra el resultado final saneado.

El head b18fc55, solo diagnóstico, tuvo CI 42541077254/42541117800 aprobado.
No atribuirlo al head nuevo que incluye reintento de migración. Validación local
del nuevo contenido: make check aprobado, 245 Python/20 JS, tipos/contrato/
migraciones y Expo. Siete staging previos (4 Chromium + 3 recuperación) sin cambios;
nueve regresiones de arranque/no retry y dos de privacidad/clasificación aprobadas.
CI final del nuevo head pendiente. No cerrar E2 por estos checks locales.

La corrección de galería ya integrada conserva formulario solo en memoria y
bajo máscara durante picker; exige validación online al volver. Logout, rechazo
y segundo plano ordinario descartan la vista. Prueba física Android sigue en E5.

## Continuación obligatoria

1. Publicar head final de PR #21, verificar CI completo y actualizar descripción.
   El CD anterior terminó; no hay migración ni archive-drill activo.
2. Integrar con checks aprobados; esperar CI main y CD automático completo.
   No avanzar main durante migración/archive-drill ni cancelar migraciones.
3. Exigir staging, E1/APK y gate E2 aprobado con otra cohorte. Contrastar SHA/
   digest, trial distinto y minimum_sequence/high-water externo. Ante fallo,
   diagnosticar; no relajar controles ni resetear datos para repetir.
4. Solo después cerrar matriz/casillas E2 y actualizar continuidad mediante PR.
   El cierre documental dispara CD: hay cohortes para comprobarlo, sin bucle de
   commits solo para actualizar el último resultado. La aceptación se acredita
   por SHA funcional/Actions, no por una URL temporal ni por un commit posterior.
5. E3–E5 pendientes según PLAN. Producción NOT_CONFIGURED E5 no es éxito ficticio.

Scratch y reportes saneados en work/, ignorados. Custodia privada/anclas fuera de Git.

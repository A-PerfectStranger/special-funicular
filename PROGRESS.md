# Continuidad E2

E2 sigue pendiente de aceptación final. Este archivo conserva el relevo solicitado
explícitamente por el usuario; PLAN.md contiene los criterios y el estado de fases,
README/runbooks los comandos y Actions los reportes por commit. No guardar secretos
ni copias de evidencia histórica en Git.

## Estado verificable

- Main remoto: `74297b397b992287272fc63745d4ccb9127e2ea6`, PR #16/#17/#18 integradas.
  CI del merge 42528545599 aprobado completo, imagen/APK/firma incluidos.
- CI main 42523200830 aprobado completo, imagen y APK incluidos.
- Ensayo real E2 [42524078114](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42524078114)
  aprobado: publicación/digest, preparación RDS, migración, despliegue, gate E1
  browser/cloud/archive-drill/APK y familia con Cognito/MFA y WORM independiente.
  Protocolo familiar exige secuencia 347; verificador externo aprobó 349 eventos
  sin usar SQL. Acredita 3085e36 y su alcance; no las correcciones posteriores.
- El operador confirmó commission_e1 (scope email) y las dos identidades sintéticas
  de ese ensayo. No se compartieron secretos ni se enviaron mensajes reales.
- Decisión explícita: cada familia pertenece a una sola escuela en este MVP.
- E2 continúa apagada en CD habitual; el ensayo habilitó temporalmente staging
  sintético. `pickup_enabled=false`; E3–E5 y producción no están aceptadas.

## Incremento en PR #18

PR integrado desde `feat/e2-live-acceptance`:
https://github.com/A-PerfectStranger/special-funicular/pull/18

La migración hacia delante 0005 serializa por UUID de padres en orden global,
revalida escuela/contacto bajo lock y contrasta los bytes almacenados contra el
hash aprobado. Dos escuelas con padres invertidos y promociones concurrentes:
exactamente una prospera; no hay vínculos entre escuelas ni activación parcial.
No modificar migraciones 0002–0004 ya aplicadas.

Gate compartido `e2-checks.yml` para ensayo/CD, requerido después de E1 cuando
`e2_enabled=true`, con WORM independiente antes de considerar producción. Sigue
false hasta validar el candidato real. Cohortes privadas nuevas en pool acotado
1..8, preparado solo por operador; CI selecciona mediante importación atómica,
salta solo cohortes consumidas y bloquea fallos de infraestructura/validación o
agotamiento. No puede crear identidades Cognito ni escribir el vault. No se
reinician invitaciones, subjects, sesiones ni evidencia. Secretos solo vault/memoria/
stdin; correlación local contiene SHA/trial, tareas ECS solo hashes de invitaciones.

El ensayo ampliado ejecuta carrera bulk privada, replay real de invitación,
recurrencia semanal con dos fechas/UTC y rechazo fuera de horario, baja online y
validación de issuer/sub antes de cambios técnicos. Cambio de principal posterior
es un comando nuevo auditado, no un reset de historia. La última mutación ancla
los eventos anteriores para el verificador externo.

Validación local: make check aprobado con 234 Python/14 JS, roles PostgreSQL reales,
tipos/contrato/migraciones y dependencias Expo; auditorías Python/npm y gitleaks,
actionlint y sintaxis Node aprobados. La regresión del drill usa snapshots nuevos
de pg_stat_activity para observar los locks dentro de su transacción. Se corrigió
el fixture E1 simulado para completar su proyección outbox junto con el recibo;
la prueba de archivo reclama su propio evento. No se cambió archivo productivo.
CI final de 82aa779: push 42527802992 y PR 42527805628 aprobados completos,
imagen/APK/firma incluidos. Merge 74297b3 integrado y CI main 42528545599 aprobado; falta AWS propio.
Continuación local en `feat/e2-acceptance-close`; no avanzar main durante el ensayo.

## Siguientes pasos obligatorios

1. PR #18 integrada con checks completos. No avanzar main durante un
   archive-drill activo cuyo guard exija latest main.
2. CI del merge aprobado y operador confirmó pool nuevo de cuatro cohortes MFA
   para 74297b3 (`E2 synthetic MFA fixtures prepared`), sin secretos compartidos.
   No repetir comisión ya confirmada salvo evidencia de cambio.
3. Ensayo E2 42529491296 lanzado en main 74297b3 con ci_run_id 42528545599
   y latest main confirmado. Está en cola serializada detrás del CD 42529252429,
   que ya migró 0005 y está desplegando. No cancelar migraciones ni avanzar main. Verificar carrera bulk,
   protocolo ampliado, imagen/APK y WORM hasta la última secuencia. Si falla,
   investigar y corregir; nunca saltar controles ni resetear cohortes usadas.
4. Solo tras aprobar, habilitar e2_enabled en staging mediante PR/checks y comprobar
   el CD habitual completo con la siguiente cohorte. Mantener pickup apagado.
5. Contrastar cada criterio de PLAN y registrar SHA/runs exactos antes de marcar E2.
   Instalación/cámara Android física, QR/retiro y producción siguen en E3/E5.

Incidencias ya delimitadas: CloudShell inicial falló por cwd fuera de Git; usar
checkout temporal. Aviso pip SAM/boto no detuvo --target. CD a435750 falló su guard
de latest main antes de pausar worker al avanzar a 3085e36; no fue un fallo de
comisión ni acredita archivo. CD 3085 en cola fue cancelado antes de migrar al
lanzar el ensayo que sí aprobó. Resultados y scratch locales en work/, ignorados.

Handoff actual: bloque CloudShell revisado fija
74297b397b992287272fc63745d4ccb9127e2ea6 en checkout temporal nuevo, instala
SDK --require-hashes en work/e1-sdk y ejecuta provision_e2_fixtures con UUID
nuevo, --pool-size 4 y --synthetic-only. Operador confirmó éxito; ensayo final
42529491296 pendiente. No pedir códigos, contraseñas ni semillas ni repetir commission_e1.
La rama de cierre contiene solo esta actualización de documentación: no está
desplegada y no sustituye la aceptación pendiente del candidato main.

Revisión móvil durante la cola AWS: AppState desmontaba Family al abrir la
galería, con riesgo de perder toda selección. Corrección local en App.tsx,
Family.tsx y sessionVisibility.ts: máscara sin interacción/accesibilidad mientras
la galería conserva el formulario en memoria; vuelta exige check online vigente.
Segundo plano ordinario, logout o rechazo descartan la vista; generaciones
impiden restaurar datos desde checks tardíos o competir con OIDC interactivo.
Seis regresiones nuevas pasan (20 JS totales); 234 Python previas sin cambio de
backend. Bundle Android/Hermes final aprobado; CI propio aún pendiente. No atribuir esta corrección
al APK de 74297b3 ni declarar prueba física Android. Integrar solo después del
ensayo 742 y de sus propios checks; podrá acompañar habilitación de E2 en CD.

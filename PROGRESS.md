# Continuidad E2

**E2 aceptada en staging sintético.** Estado conservado por instrucción explícita
del usuario; PLAN contiene criterios y fases. Evidencia por SHA en Actions y
anclas/recibos privados fuera del repositorio. No copiar reportes ni secretos.

## Base funcional acreditada

- SHA `1a16b85fcc7f8ac25d268c308c1ccf9451c667b1` (PR #16–#21 integradas).
- CI [42543919847](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42543919847)
  aprobado: 245 Python, 20 JavaScript móvil/vendor, siete staging (4 Chromium y
  3 recuperación), tipos/contratos/migraciones, seguridad, imagen/APK/firma.
- CD [42544785382](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42544785382):
  publish/prepare/migrate/staging, E1 browser/cloud/archive-drill/APK y
  e2-acceptance/family aprobados. Solo producción falla por NOT_CONFIGURED E5;
  no afirmar que el pipeline productivo o el MVP real estén aceptados.
- Digest runtime API/archivador contrastado:
  `sha256:3aa74250b1bfe778e2ed8d601e845124087d30ef603bf712e9004d5fafde44eb`.
- Cohorte `52cb10c3-9494-5893-bd8a-ce52d8c11ba3`: mínimo familiar 614;
  WORM independiente verificó 615 eventos sin SQL. Se comprobó SHA y que difiere
  de la cohorte `85885f69-3c08-581f-adb0-a297198314e2` del ensayo 74297b3
  [42529491296](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42529491296),
  aprobado con mínimo 489 y WORM 490. El pool permite repetir en otro release
  sin resetear cuentas, invitaciones ni evidencia.

## Alcance terminado

Importación privada con esquema/bytes/hash/aprobación/promoción atómica e
idempotente; una familia por escuela, incluso entre promociones concurrentes.
Invitaciones 256 bits/24 h, contacto firmado/verificado, OIDC/PKCE/MFA y binding
issuer/sub exclusivo. Consulta familiar/capacidades, cuidador/foto normalizada,
recurrencia finita IANA, horarios/restricciones/revocación y operaciones técnicas
auditadas. SQL/RLS y roles separados; principal anterior/secundario denegados;
baja y cambios sensibles invalidan sesiones/versiones. Contrato, cliente SDK 56,
CLI y runbook integrados. Galería conserva formulario solo bajo máscara y exige
check online al volver; logout/rechazo/segundo plano ordinario lo descartan.

Los fallos previos del control guardia y migración se clasificaron por operador:
TaskFailedToStart sin inicio/exitCode (migración: CannotPullContainerError), sin
SQL ejecutado. `isolated_task.py` permite un único reintento de no arranque
probado, con mismos definición/red/inputs; no reintenta SQL, ejecución incierta,
error de creación ni código 42. Segundo fallo bloquea. Diagnóstico conserva la
primera fase y publica solo categorías saneadas. Límites MFA y access <240000ms
no se relajaron. El CD acreditado completó migración y todas las aserciones.

## Continuación y límites

1. El cierre documental no añade comportamiento funcional. Para comprobar su
   integración, consultar el CI/CD de su SHA en Actions y exigir E1/E2/WORM con
   otra cohorte. No avanzar main durante migración/archive-drill. Tras ese gate,
   la siguiente fase de implementación es E3 según PLAN.
2. No crear un bucle de commits solo para registrar el último resultado: la base
   funcional aceptada y sus runs están arriba; releases posteriores se consultan
   por SHA en Actions. No atribuirles automáticamente esta aceptación.
3. El operador preparó cuatro cohortes; las dos acreditadas arriba ya se usaron.
   El CD del cierre documental consume otra: consultar las ejecuciones posteriores
   antes de contar disponibilidad. No resetear las previas. Ante agotamiento
   preparar pool nuevo según runbook; CI no crea Cognito ni escribe el vault.
4. No repetir commission_e1 ni pedir códigos/contraseñas/semillas. No editar
   migraciones 0002–0005 ya aplicadas ni ejecutar refresh antiguos de work/.
5. E3–E5 siguen pendientes: QR/retiro, avisos, validación Android física,
   retención institucional/firma/distribución y producción. pickup_enabled=false;
   solo sintéticos. No hay importaciones/invitaciones/mensajes reales enviados.

Scratch y reportes saneados en work/, ignorados. Git conserva fuentes/estado,
Actions los checks y la custodia privada las anclas y versiones WORM.
